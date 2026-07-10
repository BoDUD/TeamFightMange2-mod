#!/usr/bin/env python3
"""Extract selected official Lucian SFX from Riot's local WAD and decode them."""

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
        "LOL_LUCIAN_WAD",
        r"D:\Riot Games\League of Legends\Game\DATA\FINAL\Champions\Lucian.wad.client",
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

WAD_SHA256 = "cb3c292af057e206ce3460892d18b19bd6fa453fde97bc2d5c0bf3786437e7b6"
WAD_AUDIO_BANK_OFFSET = 53_713_801
WAD_AUDIO_BANK_SIZE = 1_080_886
AUDIO_BANK_PATH = (
    "assets/sounds/wwise2016/sfx/characters/lucian/skins/base/"
    "lucian_base_sfx_audio.bnk"
)
AUDIO_BANK_PATH_HASH = "85c8063dea11583c"
AUDIO_BANK_SHA256 = "100d1f20103f93a7af5e2136622cd001d70b7eeb6d56503f1488d9aaf83885ca"


@dataclass(frozen=True)
class LucianSound:
    output_stem: str
    media_id: int
    event: str
    expected_duration_seconds: float
    wem_sha256: str


SOUNDS = (
    LucianSound(
        "lucian_attack_cast",
        119_804_074,
        "Play_sfx_Lucian_LucianBasicAttack_OnMissileLaunch",
        0.998,
        "368354b87361197c210dea504b2fe06b924d43e5c0b6f14f1cc8179589c0b9b2",
    ),
    LucianSound(
        "lucian_attack_hit",
        655_387_061,
        "Play_sfx_Lucian_LucianBasicAttack_OnHit",
        0.738,
        "028022425eee93b6d4dc80fc3130f6d5b4cb1ea6339653632593feb6f5e3985f",
    ),
    LucianSound(
        "lucian_passive_cast",
        288_975_061,
        "Play_sfx_Lucian_LucianPassiveAttack_OnMissileLaunch",
        1.139,
        "7af9f6ddafb7903fe75331f9a3bc514526c1ca9baa53d022eabb30f8ad8b7123",
    ),
    LucianSound(
        "lucian_passive_hit",
        368_178_684,
        "Play_sfx_Lucian_LucianPassiveAttack_OnHit",
        0.680,
        "caf64c5d5e6e7e8d219d3893e2ee7dc703b03dbd68996288d96a171df65b9a3f",
    ),
    LucianSound(
        "lucian_q_cast",
        264_429_047,
        "Play_sfx_Lucian_LucianQ_OnCast",
        0.606,
        "c987e7106258ca951568b544829366922fc8724d4edb759559d6507919fc94d4",
    ),
    LucianSound(
        "lucian_e_cast",
        268_159_856,
        "Play_sfx_Lucian_LucianE_OnCast",
        2.103,
        "0247426d1b19970f5481c50a2e6269dd1cb32015da670f3f68eb8d82c0550596",
    ),
    LucianSound(
        "lucian_r_cast",
        335_009_448,
        "Play_sfx_Lucian_LucianR_OnCast",
        1.602,
        "aad092010f37fe0f0edbf3c64511154e4c226c0ac2d7d016e18d83865da48c49",
    ),
    LucianSound(
        "lucian_r_channel",
        134_398_349,
        "Play_sfx_Lucian_LucianR_OnBuffActivate",
        4.183,
        "5aa3fffa55fde172c1f51be482b3bf0c6d56bbf9b5183f4e4285712992abd785",
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
            "Lucian WAD hash does not match the pinned local League build; "
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

    with tempfile.TemporaryDirectory(prefix=".lucian_audio_", dir=output_dir) as temp_name:
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
        help=f"Path to Lucian.wad.client (default: {DEFAULT_WAD})",
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
        raise FileNotFoundError(f"Lucian WAD not found: {wad_path}")
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
