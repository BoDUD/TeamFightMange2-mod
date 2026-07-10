#!/usr/bin/env python3
"""Extract selected official Sivir SFX from Riot's local WAD and decode them."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile

from extract_briar_audio import extract_wem_media, inspect_pcm_wav, sha256_bytes, sha256_file


DEFAULT_WAD = Path(
    os.environ.get(
        "LOL_SIVIR_WAD",
        r"D:\Riot Games\League of Legends\Game\DATA\FINAL\Champions\Sivir.wad.client",
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

WAD_SHA256 = "f028e616c97a7a90fbf2036aed21cdb09746680e2087962d4702ebdf9b6e57c9"
WAD_AUDIO_BANK_OFFSET = 64_981_320
WAD_AUDIO_BANK_SIZE = 1_323_705
AUDIO_BANK_PATH = (
    "assets/sounds/wwise2016/sfx/characters/sivir/skins/base/"
    "sivir_base_sfx_audio.bnk"
)
AUDIO_BANK_SHA256 = "9e0b69783e479cf977f3a7b2ed14341ea4f2904134c3e6a32e20ec59ce3e253d"
EVENT_BANK_SHA256 = "b79803332df820dd30c34d5c55c7bf6411c1211e47cbcbe9b3ac66108a5da4e5"


@dataclass(frozen=True)
class SivirSound:
    output_stem: str
    media_id: int
    event: str
    event_id: int
    event_media_pool: tuple[int, ...]
    wem_sha256: str


SOUNDS = (
    SivirSound(
        "sivir_attack_cast",
        313_782_301,
        "Play_sfx_Sivir_SivirBasicAttack_OnMissileLaunch",
        1_876_638_910,
        (313_782_301, 127_817_854, 241_769_197, 126_834_791, 123_447_395, 21_412_024, 37_501_807, 29_991_347),
        "6d9c0b0b10057da1014b60311aa1415474340d7e570015cb19886df13105f33f",
    ),
    SivirSound(
        "sivir_attack_hit",
        127_195_855,
        "Play_sfx_Sivir_SivirBasicAttack_OnHit",
        4_265_286_992,
        (127_195_855, 63_357_982, 66_488_402, 208_765_832, 250_296_633, 221_898_617, 225_601_963),
        "c4f39d11af887d6022487e90ad10d654457bc168b49bb57f13b18be6360497f7",
    ),
    SivirSound(
        "sivir_q_out",
        388_184_696,
        "Play_sfx_Sivir_SivirQMissile_OnMissileLaunch",
        3_385_220_941,
        (388_184_696, 636_809_438, 45_977_684),
        "6baa312d6459d7886d20a10ca2880c40eba44b23b90584ff02915e0032762c42",
    ),
    SivirSound(
        "sivir_q_return",
        758_922_626,
        "Play_sfx_Sivir_SivirQMissileReturn_OnMissileLaunch",
        1_646_723_331,
        (758_922_626, 790_270_116, 555_029_523),
        "6f76f766bfc67644e39cdf71f511e1d35bf369a4b191b5055623ebf3fb1d7f41",
    ),
    SivirSound(
        "sivir_q_hit",
        941_838_837,
        "Play_sfx_Sivir_SivirQ_hit",
        1_419_197_874,
        (941_838_837, 423_248_603, 700_051_508, 526_778_842, 676_240_343, 30_310_186),
        "4b6f5d4fa40b8b1cbeaa9b64c613b9a85296ddeb770665abcea6cb05d480925a",
    ),
    SivirSound(
        "sivir_e_cast",
        530_898_384,
        "Play_sfx_Sivir_SivirE_OnBuffActivate",
        4_008_136_820,
        (530_898_384, 1_059_050_639),
        "6497defa527da2ba40068571b7e2ce25f6e67cb1aa4454b2b1b7bd60d2d86d35",
    ),
    SivirSound(
        "sivir_r_cast",
        790_477_901,
        "Play_sfx_Sivir_SivirR_OnCast",
        546_561_056,
        (790_477_901, 1_015_579_061, 366_106_789),
        "75d4e91980a603fc3fb374908f577a17020658899c43f55f3ed6e7741d464ef7",
    ),
)


def load_pinned_audio_bank(wad_path: Path) -> bytes:
    actual_wad_hash = sha256_file(wad_path)
    if actual_wad_hash != WAD_SHA256:
        raise RuntimeError(
            "Sivir WAD hash does not match the pinned local League build; "
            f"expected {WAD_SHA256}, got {actual_wad_hash}."
        )
    with wad_path.open("rb") as wad:
        wad.seek(WAD_AUDIO_BANK_OFFSET)
        bank = wad.read(WAD_AUDIO_BANK_SIZE)
    if len(bank) != WAD_AUDIO_BANK_SIZE:
        raise RuntimeError(
            f"Audio bank is truncated: expected {WAD_AUDIO_BANK_SIZE}, got {len(bank)}."
        )
    actual_bank_hash = sha256_bytes(bank)
    if actual_bank_hash != AUDIO_BANK_SHA256:
        raise RuntimeError(
            f"Audio bank hash mismatch: expected {AUDIO_BANK_SHA256}, got {actual_bank_hash}."
        )
    return bank


def decode_sounds(bank: bytes, vgmstream_path: Path, output_dir: Path) -> list[dict[str, object]]:
    media = extract_wem_media(bank)
    output_dir.mkdir(parents=True, exist_ok=True)
    reports: list[dict[str, object]] = []
    with tempfile.TemporaryDirectory(prefix=".sivir_audio_", dir=output_dir) as temp_name:
        temp_dir = Path(temp_name)
        pending: list[tuple[Path, Path]] = []
        for sound in SOUNDS:
            wem = media.get(sound.media_id)
            if wem is None:
                raise RuntimeError(f"Media id {sound.media_id} is missing from DIDX.")
            actual_wem_hash = sha256_bytes(wem)
            if actual_wem_hash != sound.wem_sha256:
                raise RuntimeError(
                    f"WEM hash mismatch for {sound.output_stem}: expected "
                    f"{sound.wem_sha256}, got {actual_wem_hash}."
                )
            wem_path = temp_dir / f"{sound.media_id}.wem"
            wav_path = temp_dir / f"{sound.output_stem}_clip.wav"
            wem_path.write_bytes(wem)
            conversion = subprocess.run(
                [str(vgmstream_path), "-i", "-W", "1", "-o", str(wav_path), str(wem_path)],
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
    parser.add_argument("--wad", type=Path, default=DEFAULT_WAD)
    parser.add_argument("--vgmstream", type=Path, default=DEFAULT_VGMSTREAM)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    wad_path = args.wad.resolve()
    vgmstream_path = args.vgmstream.resolve()
    output_dir = args.out.resolve()
    if not wad_path.is_file():
        raise FileNotFoundError(f"Sivir WAD not found: {wad_path}")
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
                "internal_bank_offset": WAD_AUDIO_BANK_OFFSET,
                "internal_bank_size": WAD_AUDIO_BANK_SIZE,
                "internal_bank_sha256": AUDIO_BANK_SHA256,
                "event_bank_sha256": EVENT_BANK_SHA256,
                "output_directory": str(output_dir),
                "sounds": sounds,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
