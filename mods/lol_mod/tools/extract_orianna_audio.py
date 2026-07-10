#!/usr/bin/env python3
"""Extract selected official Orianna SFX from Riot's local WAD and decode them."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import struct
import subprocess
import tempfile
import wave
from dataclasses import dataclass
from pathlib import Path


DEFAULT_WAD = Path(
    os.environ.get(
        "LOL_ORIANNA_WAD",
        r"D:\Riot Games\League of Legends\Game\DATA\FINAL\Champions\Orianna.wad.client",
    )
)
DEFAULT_VGMSTREAM = Path(
    os.environ.get(
        "VGMSTREAM_CLI",
        str(
            Path(os.environ.get("LOCALAPPDATA", Path.home()))
            / "CodexTools"
            / "vgmstream-nightly"
            / "bin"
            / "vgmstream-cli.exe"
        ),
    )
)
DEFAULT_OUTPUT = Path(__file__).resolve().parents[1] / "sound" / "sfx"

WAD_SHA256 = "8b6507bf5e23bc8e46b49ffdcbdf02bc703d5110a082444ae8c57427225bc596"
WAD_AUDIO_BANK_OFFSET = 68_623_222
WAD_AUDIO_BANK_SIZE = 1_106_293
AUDIO_BANK_PATH = (
    "assets/sounds/wwise2016/sfx/characters/orianna/skins/base/"
    "orianna_base_sfx_audio.bnk"
)
AUDIO_BANK_PATH_HASH = "9843d800f2532dff"
AUDIO_BANK_SHA256 = "4e73b53d06961792c3f9d40518ddaab588f1c74f635d945c15bc6cca3449865d"


@dataclass(frozen=True)
class OriannaSound:
    output_stem: str
    media_id: int
    event: str
    expected_duration_seconds: float
    wem_sha256: str


SOUNDS = (
    OriannaSound(
        "orianna_attack_oncast",
        10_486_779,
        "Play_sfx_Orianna_OriannaBasicAttack_OnCast",
        0.456,
        "44e171e9fa39515829b6236edcaab23bb4aac2a1d358e2cff7d8bd5b7d611120",
    ),
    OriannaSound(
        "orianna_attack_cast",
        107_968_075,
        "Play_sfx_Orianna_OriannaBasicAttack_OnMissileLaunch",
        0.590,
        "874ac5216b57624c6a3dd82041aa2590fe10a690a66e40e1127be9640f2ed03f",
    ),
    OriannaSound(
        "orianna_attack_hit",
        88_465_727,
        "Play_sfx_Orianna_OriannaBasicAttack_OnHit",
        0.763,
        "057373ec5c5be545f224263e81eb06e3ce53be06172232421a89733b96343ec4",
    ),
    OriannaSound(
        "orianna_q_cast",
        115_694_724,
        "Play_sfx_OrianaIzunaCommand_OnCast",
        0.638,
        "90571b3d158dc13bf7594d25683b70bdf5fac7817ee81e19963d9b706513e2c1",
    ),
    OriannaSound(
        "orianna_q_hit",
        791_749_679,
        "Play_sfx_Orianna_OriannaIzuna_hit",
        0.622,
        "d2d650ce0ac9f605776d3f774be59a9ced1471cdf6bf79e02de0b8ac963447d9",
    ),
    OriannaSound(
        "orianna_e_cast",
        36_982_805,
        "Play_sfx_OrianaRedactCommand_OnCast",
        0.608,
        "465b2943e06bcf2e7955c9f660efde7aafb69dadfad6fb31c4e9f474fc51881b",
    ),
    OriannaSound(
        "orianna_e_hit",
        350_706_451,
        "Play_sfx_OrianaRedactShield_OnBuffActivate",
        0.913,
        "bed33119f3b0b0824e58df425a0d662248fc0ed1edc4736a5d234f5e9d19d1bd",
    ),
    OriannaSound(
        "orianna_r_cast",
        249_237_419,
        "Play_sfx_OrianaDetonateCommand_OnCast",
        0.790,
        "871946155faf9c60d199244f4998b93c1d46cf05f8e7e60fc235e75e19c2aa2b",
    ),
    OriannaSound(
        "orianna_r_hit",
        648_642_925,
        "Play_sfx_Orianna_OriannaDetonateCommand_hit",
        2.202,
        "79938f8d719f984201b62b445bcd5589e7a4ec82cd656c0ce543b92b5590d090",
    ),
)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_pinned_audio_bank(wad_path: Path) -> bytes:
    actual_wad_hash = sha256_file(wad_path)
    if actual_wad_hash != WAD_SHA256:
        raise RuntimeError(
            "Orianna WAD hash does not match the pinned local League build; "
            f"expected {WAD_SHA256}, got {actual_wad_hash}. "
            "The bank offset must be re-audited before extraction."
        )

    with wad_path.open("rb") as wad:
        wad.seek(WAD_AUDIO_BANK_OFFSET)
        bank = wad.read(WAD_AUDIO_BANK_SIZE)

    if len(bank) != WAD_AUDIO_BANK_SIZE:
        raise RuntimeError(
            f"Audio bank is truncated: expected {WAD_AUDIO_BANK_SIZE} bytes, "
            f"read {len(bank)}."
        )
    actual_bank_hash = sha256_bytes(bank)
    if actual_bank_hash != AUDIO_BANK_SHA256:
        raise RuntimeError(
            f"Audio bank hash mismatch: expected {AUDIO_BANK_SHA256}, "
            f"got {actual_bank_hash}."
        )
    return bank


def parse_bnk_sections(bank: bytes) -> dict[bytes, tuple[int, int]]:
    sections: dict[bytes, tuple[int, int]] = {}
    cursor = 0
    while cursor < len(bank):
        if cursor + 8 > len(bank):
            raise RuntimeError(f"Incomplete BNK section header at offset {cursor}.")
        section_id = bank[cursor : cursor + 4]
        section_size = struct.unpack_from("<I", bank, cursor + 4)[0]
        payload_start = cursor + 8
        payload_end = payload_start + section_size
        if payload_end > len(bank):
            name = section_id.decode("ascii", errors="replace")
            raise RuntimeError(f"BNK section {name} extends past the bank boundary.")
        if section_id in sections:
            name = section_id.decode("ascii", errors="replace")
            raise RuntimeError(f"Duplicate BNK section {name}.")
        sections[section_id] = (payload_start, section_size)
        cursor = payload_end

    for required in (b"BKHD", b"DIDX", b"DATA"):
        if required not in sections:
            raise RuntimeError(f"Required BNK section {required.decode()} is missing.")
    return sections


def extract_wem_media(bank: bytes) -> dict[int, bytes]:
    sections = parse_bnk_sections(bank)
    didx_start, didx_size = sections[b"DIDX"]
    data_start, data_size = sections[b"DATA"]
    if didx_size % 12:
        raise RuntimeError(f"DIDX size {didx_size} is not divisible by 12.")

    media: dict[int, bytes] = {}
    for row in range(didx_size // 12):
        media_id, relative_offset, media_size = struct.unpack_from(
            "<III", bank, didx_start + row * 12
        )
        if relative_offset + media_size > data_size:
            raise RuntimeError(f"Media {media_id} extends past the DATA section.")
        if media_id in media:
            raise RuntimeError(f"Duplicate media id {media_id} in DIDX.")
        start = data_start + relative_offset
        media[media_id] = bank[start : start + media_size]
    return media


def inspect_pcm_wav(path: Path) -> dict[str, int | float | str]:
    with wave.open(str(path), "rb") as decoded:
        channels = decoded.getnchannels()
        sample_width = decoded.getsampwidth()
        sample_rate = decoded.getframerate()
        frame_count = decoded.getnframes()
        compression = decoded.getcomptype()

    if (channels, sample_width, sample_rate, compression) != (1, 2, 44_100, "NONE"):
        raise RuntimeError(
            f"Unexpected WAV format for {path.name}: channels={channels}, "
            f"sample_width={sample_width}, sample_rate={sample_rate}, "
            f"compression={compression}."
        )
    return {
        "channels": channels,
        "sample_width_bytes": sample_width,
        "sample_rate_hz": sample_rate,
        "frame_count": frame_count,
        "duration_seconds": frame_count / sample_rate,
        "compression": compression,
    }


def decode_sounds(
    bank: bytes, vgmstream_path: Path, output_dir: Path
) -> list[dict[str, object]]:
    media = extract_wem_media(bank)
    output_dir.mkdir(parents=True, exist_ok=True)
    reports: list[dict[str, object]] = []

    with tempfile.TemporaryDirectory(prefix=".orianna_audio_", dir=output_dir) as temp_name:
        temp_dir = Path(temp_name)
        pending: list[tuple[Path, Path]] = []

        for sound in SOUNDS:
            if sound.media_id not in media:
                raise RuntimeError(f"Media id {sound.media_id} is missing from DIDX.")
            wem = media[sound.media_id]
            actual_wem_hash = sha256_bytes(wem)
            if actual_wem_hash != sound.wem_sha256:
                raise RuntimeError(
                    f"WEM hash mismatch for {sound.output_stem}: expected "
                    f"{sound.wem_sha256}, got {actual_wem_hash}."
                )
            if not (wem.startswith(b"RIFF") and wem[8:12] == b"WAVE"):
                raise RuntimeError(f"Media {sound.media_id} is not a RIFF/WAVE WEM.")

            wem_path = temp_dir / f"{sound.media_id}.wem"
            wav_path = temp_dir / f"{sound.output_stem}_clip.wav"
            wem_path.write_bytes(wem)
            conversion = subprocess.run(
                [
                    str(vgmstream_path),
                    "-i",
                    "-W",
                    "1",
                    "-o",
                    str(wav_path),
                    str(wem_path),
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            if conversion.returncode != 0 or not wav_path.is_file():
                details = (conversion.stderr or conversion.stdout).strip()
                raise RuntimeError(
                    f"vgmstream failed for {sound.output_stem} "
                    f"(exit {conversion.returncode}): {details}"
                )

            wav_info = inspect_pcm_wav(wav_path)
            duration = float(wav_info["duration_seconds"])
            if abs(duration - sound.expected_duration_seconds) > 0.015:
                raise RuntimeError(
                    f"Unexpected duration for {sound.output_stem}: expected about "
                    f"{sound.expected_duration_seconds:.3f}s, got {duration:.6f}s."
                )

            destination = output_dir / wav_path.name
            pending.append((wav_path, destination))
            reports.append(
                {
                    "event_key": sound.output_stem,
                    "event": sound.event,
                    "media_id": sound.media_id,
                    "wem_sha256": actual_wem_hash,
                    "output": destination.name,
                    **wav_info,
                }
            )

        for temporary, destination in pending:
            temporary.replace(destination)

    for report in reports:
        output_path = output_dir / str(report["output"])
        report["output_sha256"] = sha256_file(output_path)
        report["output_size_bytes"] = output_path.stat().st_size
    return reports


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--wad",
        type=Path,
        default=DEFAULT_WAD,
        help=f"Path to Orianna.wad.client (default: {DEFAULT_WAD})",
    )
    parser.add_argument(
        "--vgmstream",
        type=Path,
        default=DEFAULT_VGMSTREAM,
        help=f"Path to vgmstream-cli.exe (default: {DEFAULT_VGMSTREAM})",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"Output sound/sfx directory (default: {DEFAULT_OUTPUT})",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    wad_path = args.wad.resolve()
    vgmstream_path = args.vgmstream.resolve()
    output_dir = args.out.resolve()

    if not wad_path.is_file():
        raise FileNotFoundError(f"Orianna WAD not found: {wad_path}")
    if not vgmstream_path.is_file():
        raise FileNotFoundError(f"vgmstream CLI not found: {vgmstream_path}")

    bank = load_pinned_audio_bank(wad_path)
    sounds = decode_sounds(bank, vgmstream_path, output_dir)
    print(
        json.dumps(
            {
                "wad": str(wad_path),
                "wad_sha256": WAD_SHA256,
                "internal_bank": AUDIO_BANK_PATH,
                "internal_bank_path_hash": AUDIO_BANK_PATH_HASH,
                "internal_bank_offset": WAD_AUDIO_BANK_OFFSET,
                "internal_bank_size": WAD_AUDIO_BANK_SIZE,
                "internal_bank_sha256": AUDIO_BANK_SHA256,
                "output_directory": str(output_dir),
                "sounds": sounds,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
