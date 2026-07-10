#!/usr/bin/env python3
"""Extract selected official Briar SFX from Riot's local WAD and decode them."""

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
        "LOL_BRIAR_WAD",
        r"D:\Riot Games\League of Legends\Game\DATA\FINAL\Champions\Briar.wad.client",
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

WAD_SHA256 = "e4a6ebd191872fe47bd62b173bc6e99938684b98d2ac8b5fe1ef138b06676eeb"
WAD_AUDIO_BANK_OFFSET = 54_249_685
WAD_AUDIO_BANK_SIZE = 1_855_525
AUDIO_BANK_PATH = (
    "assets/sounds/wwise2016/sfx/characters/briar/skins/base/"
    "briar_base_sfx_audio.bnk"
)
AUDIO_BANK_PATH_HASH = "6194934d6152b833"
AUDIO_BANK_SHA256 = "f5dafd23a430dfefb8be9b3d948f95e23641b0e7833ffec10bd8a2e8728984a4"


@dataclass(frozen=True)
class BriarSound:
    output_stem: str
    media_id: int
    event: str
    event_id: int
    event_media_pool: tuple[int, ...]
    expected_duration_seconds: float
    wem_sha256: str


SOUNDS = (
    BriarSound(
        "briar_attack_cast",
        337_039_456,
        "Play_sfx_Briar_BriarBasicAttack_OnCast",
        1_625_124_708,
        (337_039_456, 414_523_161, 275_742_538, 320_610_712),
        0.261473923,
        "4af208c81e9b5f680fdba755116105a67581972e29093eb0fe39cd7f5533adae",
    ),
    BriarSound(
        "briar_attack_hit",
        977_937_509,
        "Play_sfx_Briar_BriarBasicAttack_OnHit",
        1_567_502_092,
        (977_937_509, 346_967_776),
        0.240975057,
        "d341b671d0fa40422f60974809464d9ebb79e0d802cfeeb054a2d863896c218f",
    ),
    BriarSound(
        "briar_frenzy_cast",
        637_934_841,
        "Play_sfx_Briar_BriarBasicAttackFrenzy_OnCast",
        2_869_900_170,
        (637_934_841, 549_156_362, 625_915_167, 111_684_265),
        0.860680272,
        "2e51ffe00ad7790430a9e60d649414b1c5898d686e7e2658ca93577f2a4b8360",
    ),
    BriarSound(
        "briar_frenzy_hit",
        530_919_773,
        "Play_sfx_Briar_BriarBasicAttackFrenzy_OnHit",
        4_041_037_182,
        (530_919_773, 19_611_527, 932_071_851, 989_498_368),
        0.726893424,
        "39dc57fcd5fa3cf1ff727eea825a7f5103d7dd1829fd95050d258bde4fc34065",
    ),
    BriarSound(
        "briar_q_cast",
        278_118_987,
        "Play_sfx_Briar_BriarW_cast_foley_jump",
        2_077_188_739,
        (278_118_987,),
        0.505147392,
        "dd9a78140d228ba3d721ba3414ad9f5f57fa2b7fc329e3952d588719769ebd92",
    ),
    BriarSound(
        "briar_e_cast",
        397_557_461,
        "Play_sfx_Briar_BriarEMisStrong_missilelaunch_charged",
        1_505_478_577,
        (397_557_461,),
        1.764263039,
        "e298570b4022c9f2033c15a1ea7d9db7f919a3090d9e7317e46e4ef78d5be7e4",
    ),
    BriarSound(
        "briar_e_hit",
        980_012_549,
        "Play_sfx_Briar_BriarEMisStrong_OnHit",
        1_269_301_111,
        (980_012_549,),
        1.790136054,
        "3f506a46a0f4014d2706a926057ddcf2670acd3510aa7a1c47dad2d705dd105b",
    ),
    BriarSound(
        "briar_r_cast",
        342_737_364,
        "Play_sfx_Briar_BriarR_OnCast",
        1_265_575_348,
        (342_737_364,),
        1.396235828,
        "cf9bea6f75ce6ed3efec19b4b122f27f3403852404c720a0571d83daae748f33",
    ),
    BriarSound(
        "briar_r_hit",
        699_304_794,
        "Play_sfx_Briar_BriarR_OnHit",
        460_152_284,
        (699_304_794,),
        2.342993197,
        "9e5c796f503350b78cacd0b573da2cacaf8bda123d5ebf34ecc56f7098a1be12",
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
            "Briar WAD hash does not match the pinned local League build; "
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

    with tempfile.TemporaryDirectory(prefix=".briar_audio_", dir=output_dir) as temp_name:
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
                    f"{sound.expected_duration_seconds:.9f}s, got {duration:.9f}s."
                )

            destination = output_dir / wav_path.name
            pending.append((wav_path, destination))
            reports.append(
                {
                    "event_key": sound.output_stem,
                    "event": sound.event,
                    "event_id": sound.event_id,
                    "event_media_pool": list(sound.event_media_pool),
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
        help=f"Path to Briar.wad.client (default: {DEFAULT_WAD})",
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
        raise FileNotFoundError(f"Briar WAD not found: {wad_path}")
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
