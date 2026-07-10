#!/usr/bin/env python3
"""Extract selected official Shen SFX from Riot's local WAD and decode them."""

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
        "LOL_SHEN_WAD",
        r"D:\Riot Games\League of Legends\Game\DATA\FINAL\Champions\Shen.wad.client",
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

WAD_SHA256 = "57351c440ba5a831ee45ab736a2dbf935b9736892d624c409f64963bb18a21e3"
WAD_AUDIO_BANK_OFFSET = 60_655_435
WAD_AUDIO_BANK_SIZE = 2_066_108
AUDIO_BANK_PATH = (
    "assets/sounds/wwise2016/sfx/characters/shen/skins/base/"
    "shen_base_sfx_audio.bnk"
)
AUDIO_BANK_PATH_HASH = "f92988de7021cabe"
AUDIO_BANK_SHA256 = "2e6c999482ec16ea7dfe22706a6634555c8b4a45bd53b2104985545def754fdc"


@dataclass(frozen=True)
class ShenSound:
    output_stem: str
    media_id: int
    event: str
    expected_duration_seconds: float
    wem_sha256: str


SOUNDS = (
    ShenSound(
        "shen_attack_cast",
        703_618_444,
        "Play_sfx_Shen_ShenBasicAttack_OnCast",
        0.923,
        "31c995a417bb062fc8425e0ca6a483d04f8b925e7427aa42fb32928d544cf580",
    ),
    ShenSound(
        "shen_attack_hit",
        82_842_219,
        "Play_sfx_Shen_ShenBasicAttack_OnHit",
        0.606,
        "55ae03d2a36fde25420077ee2c8a4d9b29455ffaf8bba8022cb923f27f8fcd71",
    ),
    ShenSound(
        "shen_q_cast",
        525_347_176,
        "Play_sfx_Shen_ShenQ_OnCast",
        1.199,
        "743e298254bd21f40d1e4113811ad6f693be5686e261cc73c2945253202bd3d0",
    ),
    ShenSound(
        "shen_w_cast",
        770_437_314,
        "Play_sfx_Shen_ShenW_OnCast",
        2.209,
        "55a9c3f1b0e37b27982211e67ade9e1dc8ed98db74b5a167114868a8b0100a5e",
    ),
    ShenSound(
        "shen_w_block",
        186_296_924,
        "Play_sfx_Shen_ShenW_hit_block",
        0.829,
        "ea23aee5eb76269fb5bb4e310b929b817517359df9237ae2e1dbecf339728399",
    ),
    ShenSound(
        "shen_r_cast",
        180_519_866,
        "Play_sfx_Shen_ShenR_OnCast",
        1.000,
        "42d603de199592c6cc270c929465e8c73c307eaaa80863908fccd2a4ef141b0e",
    ),
    ShenSound(
        "shen_r_arrive",
        438_315_696,
        "Play_sfx_Shen_ShenR_foley",
        3.082,
        "0711fe38732b963b4a21658bf55b540afec224e81acfb09ce12936ea208aefd2",
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
            "Shen WAD hash does not match the pinned local League build; "
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

    with tempfile.TemporaryDirectory(prefix=".shen_audio_", dir=output_dir) as temp_name:
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
        help=f"Path to Shen.wad.client (default: {DEFAULT_WAD})",
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
        raise FileNotFoundError(f"Shen WAD not found: {wad_path}")
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
