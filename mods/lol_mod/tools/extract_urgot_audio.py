#!/usr/bin/env python3
"""Extract pinned official base-skin Urgot SFX from the local Riot WAD."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import wave

from extract_briar_audio import extract_wem_media, inspect_pcm_wav


MOD_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_WAD = Path(
    os.environ.get(
        "LOL_URGOT_WAD",
        r"D:\Riot Games\League of Legends\Game\DATA\FINAL\Champions\Urgot.wad.client",
    )
)
DEFAULT_WADTOOLS = Path(
    os.environ.get(
        "WADTOOLS",
        Path(os.environ.get("LOCALAPPDATA", Path.home()))
        / "CodexTools"
        / "wadtools-0.5.6"
        / "wadtools.exe",
    )
)
DEFAULT_WWISER = Path(
    os.environ.get(
        "WWISER_PYZ",
        Path(os.environ.get("LOCALAPPDATA", Path.home()))
        / "CodexTools"
        / "wwiser-v20250928"
        / "wwiser.pyz",
    )
)
DEFAULT_VGMSTREAM = Path(
    os.environ.get(
        "VGMSTREAM_CLI",
        Path(os.environ.get("LOCALAPPDATA", Path.home()))
        / "CodexTools"
        / "vgmstream-nightly"
        / "bin"
        / "vgmstream-cli.exe",
    )
)
DEFAULT_HASHTABLE = Path(
    os.environ.get(
        "LOL_GAME_HASHTABLE",
        Path.home() / "Documents" / "LeagueToolkit" / "wad_hashtables" / "hashes.game.txt",
    )
)
DEFAULT_OUTPUT = MOD_ROOT / "sound" / "sfx"
DEFAULT_REPORT = MOD_ROOT / "qa" / "urgot_official_audio_sources.json"

WAD_RELATIVE_PATH = "Game/DATA/FINAL/Champions/Urgot.wad.client"
WAD_SIZE = 69_170_675
WAD_SHA256 = "7feab1a2c2994e1f68a213fc6133fca80e29c88799c62bdeb0e82afde4b46975"

AUDIO_BANK_PATH = (
    "assets/sounds/wwise2016/sfx/characters/urgot/skins/base/"
    "urgot_base_sfx_audio.bnk"
)
AUDIO_BANK_PATH_HASH = "b1f399b349a7bacc"
AUDIO_BANK_SIZE = 2_122_959
AUDIO_BANK_MEDIA_COUNT = 152
AUDIO_BANK_SHA256 = "675a67d8d46aaf0e71f87c876e19b57b4a2cf2bad1a8f331647071df12f90eef"

EVENT_BANK_PATH = (
    "assets/sounds/wwise2016/sfx/characters/urgot/skins/base/"
    "urgot_base_sfx_events.bnk"
)
EVENT_BANK_PATH_HASH = "1956fe8fb8973c9f"
EVENT_BANK_SIZE = 20_901
EVENT_BANK_SHA256 = "4ac6f2dff665c8f80fc8ef5a967f73c9b0d1de4e1c59ab6267da9aa68bdb69dc"

REGISTRY_PATH = "data/characters/urgot/skins/skin0.bin"
REGISTRY_PATH_HASH = "4ce892ac40ca773f"
REGISTRY_SIZE = 78_740
REGISTRY_SHA256 = "2ec2a2e0d668e9ddc45eb78d3a0beb2dc33baebbc2edc6b390212eaddcf5cdab"

WADTOOLS_VERSION = "0.5.6"
WADTOOLS_SHA256 = "c11b60cc8016c3d986eceb91c3c9fd74e4440416ba2a215af1135f36bd0fa866"
WWISER_VERSION = "v20250928"
WWISER_SHA256 = "fdcb850ad19d827190a1eb137c2caa02c40671e15c379a6c9a477d2a5237bf53"
VGMSTREAM_SHA256 = "894cff498bbb7d43fcbae63aac9dc19ebbef8f37c9889c4a9e51de407b5f3c07"
HASHTABLE_SIZE = 207_968_174
HASHTABLE_SHA256 = "f7d5e73ff1c4b7b4630cef6d4bafe3d1b7a80a2f51e3bf9d4db4e018954d041b"

SILENCE_OUTPUT = "urgot_native_silence_clip.wav"
SILENCE_FRAME_COUNT = 2_205
SILENCE_SHA256 = "73b42ab23be05ebeada04e01d7a8b903a1cdd1753a090c5032983da1066bacc2"

# These are every Demon sound_info/clip entry actually present in this build's
# bundle.  The compatibility skill2 keys are also silenced in mod.override_info
# because the Urgot replacement owns that action slot even though the bundled
# Demon bank has no standalone demon_skill2 asset.
BUNDLED_NATIVE_EVENTS = (
    "demon_attack",
    "demon_attack_ult",
    "demon_skill1",
    "demon_transform",
    "demon_ult",
)
BUNDLED_NATIVE_CLIPS = (
    "demon_attack0",
    "demon_attack_ult0",
    "demon_skill0",
    "demon_skill1_resource",
    "demon_ult0",
    "demon_ult1",
    "demon_ult_resource",
)
COMPATIBILITY_NATIVE_EVENTS = ("demon_skill2",)
COMPATIBILITY_NATIVE_CLIPS = ("demon_skill2_resource",)


@dataclass(frozen=True)
class UrgotSound:
    output_stem: str
    media_id: int
    event: str
    event_id: int
    event_media_pool: tuple[int, ...]
    wem_sha256: str
    expected_duration_seconds: float
    expected_wav_sha256: str
    dispatch: str
    selection_note: str

    @property
    def output(self) -> str:
        return f"{self.output_stem}_clip.wav"

    @property
    def runtime_event(self) -> str:
        return f"lol_{self.output_stem}"


SOUNDS = (
    UrgotSound(
        "urgot_attack_cast",
        70_663_045,
        "Play_sfx_Urgot_UrgotBasicAttack_cast",
        3_992_445_123,
        (70_663_045, 69_321_891, 270_506_805, 77_833_467, 40_240_153),
        "ce0f1a2b38f62d6307193075ca94c4750130be3e8132f63acf40cd54332ce314",
        1.093900227,
        "c12b5f6da7bf6240ce788e254dae9011d89408e16c3607e683d58dc1c7e91682",
        "top-level Sfx when the basic cannon attack commits",
        "first variant in Riot's base attack-cast random container",
    ),
    UrgotSound(
        "urgot_attack_hit",
        261_711_048,
        "Play_sfx_Urgot_UrgotBasicAttack_OnHit",
        2_866_133_468,
        (
            261_711_048, 309_248_895, 165_551_459, 2_474_448, 26_122_873,
            30_175_078, 173_710_541, 101_938_678, 77_645_252, 186_772_506,
            146_596_911, 76_602_174, 179_112_175, 65_669_815, 126_561_859,
            253_076_287, 11_788_806, 83_999_309, 250_552_409, 169_167_817,
        ),
        "c5ec076f6130e60bf023f0e7541389d958311204c5e4279d555346fbf7016e3a",
        0.371133787,
        "219ac122f5e1ff0cfe0b10d212e4880b0dd022c116b80cc09f0b7474c3643c2f",
        "TargetSfx after basic-attack damage",
        "first variant in Riot's default non-Metal/Stone/Wood surface switch",
    ),
    UrgotSound(
        "urgot_w_cast",
        264_170_470,
        "Play_sfx_Urgot_UrgotW_OnCast",
        3_093_759_059,
        (264_170_470, 215_941_130, 316_564_949),
        "7577534b3e187b6d9e57a81ce632567755cd0a38e6667c85f42ba711da903b32",
        1.240929705,
        "6f4b0d9964a07f117971d48de9a97166b7448e580b288988d9fa2a5b2f642d8b",
        "top-level Sfx once when Purge starts",
        "first variant in Riot's W cast random container",
    ),
    UrgotSound(
        "urgot_w_shot",
        691_841_699,
        "Play_sfx_Urgot_UrgotWMissileExtra_OnMissileLaunch",
        1_737_283_661,
        (691_841_699, 83_006_034, 210_443_025, 520_358_027, 1_023_839_766),
        "bc521c68bb25e1e2105814a37df6e4c041a875758586da0d79e320886c01b63f",
        0.556848073,
        "7e99f5346efa97cc1e8a90ccc031078b2c38dd78568d98310b1b97cc9f964bca",
        "Sfx on each paced W projectile launch",
        "first variant in Riot's W missile-launch random container",
    ),
    UrgotSound(
        "urgot_e_cast",
        982_720_132,
        "Play_sfx_Urgot_UrgotE_OnCast",
        3_773_826_833,
        (982_720_132, 889_334_460, 583_277_064, 499_364_099),
        "428e4c333d2951cf85142e8dea8d42c8018882a4262798077fa79118d651bec1",
        1.370884354,
        "c86b79295ef7736323c6bf17b624e590662937a6237c49c41f0ea06de236bacc",
        "top-level Sfx when Disdain's shield-charge starts",
        "first variant in Riot's E cast random container",
    ),
    UrgotSound(
        "urgot_e_hit",
        520_331_676,
        "Play_sfx_Urgot_UrgotE_OnHitLocation",
        898_916_462,
        (520_331_676, 882_848_098, 668_812_023),
        "76f196a6a8b24ecb7b15419f93916de513b096c1268172c60c9cd8012ec7dc10",
        1.009750567,
        "40b4c3f8c1b4223b04b114e1499b28c7c3bd5f6e002bca8dc6fd09d7b50a3726",
        "TargetSfx on the champion caught and flipped by E",
        "first variant in Riot's E hit-location random container",
    ),
    UrgotSound(
        "urgot_r_cast",
        985_284_682,
        "Play_sfx_Urgot_UrgotR_OnCast",
        481_345_476,
        (985_284_682, 924_147_906, 508_537_866),
        "31c017ab72a8c15b0611260ff0f0d8c709089054a5d9c290a40afe19b55ff037",
        1.808730159,
        "96f5d69d8ca23ccd8a73ae76151fd8d3b2d589ead79395f20184f134bf313cc3",
        "top-level Sfx once when Fear Beyond Death is fired",
        "first variant in Riot's R cast random container",
    ),
    UrgotSound(
        "urgot_r_latch",
        365_431_487,
        "Play_sfx_Urgot_UrgotR_OnHit",
        2_034_822_636,
        (365_431_487, 433_580_542, 828_708_047),
        "7d16b36e8e84e3fdc3336e2d938ed53f6d0b973d0913e970382f7befec3be275",
        2.246802721,
        "697419f718207ad09b357be09d7430808dd4a91c85234a1be1961c63f8b03674",
        "TargetSfx when the R drill latches onto its victim",
        "first variant in Riot's R on-hit random container",
    ),
    UrgotSound(
        "urgot_r_pull",
        859_097_235,
        "Play_sfx_Urgot_UrgotRRecastMissile_OnMissileLaunch",
        1_981_392_254,
        (859_097_235,),
        "5e5f68b805f4ae2a8a07a889d69e36ec1b76ff6934102c3428512a93f2e98019",
        2.223764172,
        "c7d6dade9dd9198d3e242ecad0fb0ea60babcdabf4d8ff9da30b64f9c8850ff2",
        "TargetSfx only when the R chain starts reeling the victim in",
        "Riot event has one deterministic media source",
    ),
    UrgotSound(
        "urgot_r_execute",
        861_007_347,
        "Play_sfx_Urgot_UrgotRGrind_cast",
        3_223_246_003,
        (861_007_347, 837_423_464, 383_713_124, 1_012_422_835),
        "34f0aa9c1d1524a1451d1b7b2759a9e8199a4882bdf01a361dc1c0696e93200f",
        3.012426304,
        "4412a880c536005136a45056f30e23d247eee776af41e847c754dadc48985d48",
        "TargetSfx only after the native 25-percent execute succeeds",
        "first variant in Riot's R grinder-cast random container",
    ),
    UrgotSound(
        "urgot_r_fear",
        1_019_572_390,
        "Play_sfx_Urgot_UrgotRGrind_fear_hit",
        2_871_514_954,
        (1_019_572_390, 545_639_051, 1_004_693_697),
        "d86a35ee7052e3d99a41f37edca369783697fb62a9a1e435e0c8f5115f9e0a82",
        2.903718821,
        "7134ab49788fffb2f5b477d941e234d5bda38729473028aa4df525cc02d1c74b",
        "Sfx with the successful-execute fear pulse",
        "first variant in Riot's R fear-hit random container",
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


def verify_file(path: Path, expected_size: int | None, expected_hash: str, name: str) -> None:
    if not path.is_file():
        raise FileNotFoundError(f"{name} not found: {path}")
    if expected_size is not None and path.stat().st_size != expected_size:
        raise RuntimeError(
            f"{name} size mismatch: expected {expected_size}, got {path.stat().st_size}"
        )
    actual = sha256_file(path)
    if actual != expected_hash:
        raise RuntimeError(f"{name} SHA-256 mismatch: expected {expected_hash}, got {actual}")


def fnv1_lower(value: str) -> int:
    result = 2_166_136_261
    for byte in value.lower().encode("utf-8"):
        result = ((result * 16_777_619) & 0xFFFF_FFFF) ^ byte
    return result


def extract_sources(
    wad: Path, wadtools: Path, hashtable: Path, output: Path
) -> tuple[Path, Path, Path]:
    command = [
        str(wadtools), "--progress=false", "extract", "-i", str(wad),
        "-o", str(output), "--hashtable", str(hashtable), "--hash",
        AUDIO_BANK_PATH_HASH, EVENT_BANK_PATH_HASH, REGISTRY_PATH_HASH,
        "--overwrite", "--stats=false",
    ]
    completed = subprocess.run(command, check=False, capture_output=True, text=True)
    if completed.returncode != 0:
        details = (completed.stderr or completed.stdout).strip()
        raise RuntimeError(f"wadtools failed with exit {completed.returncode}: {details}")
    paths = (
        output / Path(AUDIO_BANK_PATH),
        output / Path(EVENT_BANK_PATH),
        output / Path(REGISTRY_PATH),
    )
    if not all(path.is_file() for path in paths):
        raise RuntimeError("wadtools did not extract all three pinned Urgot sources")
    return paths


def verify_event_registry(registry: Path) -> None:
    payload = registry.read_bytes()
    for sound in SOUNDS:
        if fnv1_lower(sound.event) != sound.event_id:
            raise RuntimeError(f"FNV-1 event ID mismatch for {sound.event}")
        if sound.event.encode("ascii") not in payload:
            raise RuntimeError(f"Urgot base registry is missing {sound.event}")


def resolve_event_media_pools(
    audio_bank: Path, event_bank: Path, wwiser: Path, output: Path
) -> None:
    output.mkdir(parents=True, exist_ok=True)
    event_ids = sorted({sound.event_id for sound in SOUNDS})
    command = [
        sys.executable, str(wwiser), str(audio_bank), str(event_bank),
        "-g", "-gu", "-go", str(output), "-gw", str(audio_bank.parent),
        "-gf", *[str(event_id) for event_id in event_ids],
        "-gnw", "-gnv", "-gxni",
    ]
    completed = subprocess.run(command, check=False, capture_output=True, text=True)
    if completed.returncode != 0:
        details = (completed.stderr or completed.stdout).strip()
        raise RuntimeError(f"wwiser failed with exit {completed.returncode}: {details}")
    resolved = {event_id: set() for event_id in event_ids}
    for txtp in output.rglob("*.txtp"):
        match = re.search(r"event-(\d+)(?:\D|$)", txtp.name)
        if match is None:
            continue
        event_id = int(match.group(1))
        if event_id not in resolved:
            continue
        payload = txtp.read_text(encoding="utf-8", errors="strict")
        resolved[event_id].update(
            int(media.group(1)) for media in re.finditer(r"##(\d+)\.wem", payload)
        )
    for sound in SOUNDS:
        if resolved[sound.event_id] != set(sound.event_media_pool):
            raise RuntimeError(
                f"wwiser media-pool mismatch for {sound.event}: expected "
                f"{sorted(sound.event_media_pool)}, got {sorted(resolved[sound.event_id])}"
            )


def write_sound_info(path: Path, clip: str) -> None:
    path.write_text(
        json.dumps(
            {"plays": [{"delay": 0.0, "clip": clip, "volume": 1.0}]},
            separators=(",", ":"),
        )
        + "\n",
        encoding="utf-8",
    )


def write_silence(path: Path) -> dict[str, object]:
    with wave.open(str(path), "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(44_100)
        output.writeframes(b"\0\0" * SILENCE_FRAME_COUNT)
    if sha256_file(path) != SILENCE_SHA256:
        raise RuntimeError("physical silence WAV hash changed")
    return {
        "path": f"sound/sfx/{SILENCE_OUTPUT}",
        "size_bytes": path.stat().st_size,
        "sha256": SILENCE_SHA256,
        **inspect_pcm_wav(path),
        "pcm_contract": "all-zero samples",
    }


def decode_sounds(
    bank: bytes, vgmstream: Path, output: Path
) -> tuple[list[dict[str, object]], dict[str, object]]:
    media = extract_wem_media(bank)
    if len(media) != AUDIO_BANK_MEDIA_COUNT:
        raise RuntimeError(
            f"Urgot bank media count mismatch: expected {AUDIO_BANK_MEDIA_COUNT}, got {len(media)}"
        )
    output.mkdir(parents=True, exist_ok=True)
    reports: list[dict[str, object]] = []
    with tempfile.TemporaryDirectory(prefix=".urgot_audio_", dir=output) as temp_name:
        temp = Path(temp_name)
        pending: list[tuple[Path, Path]] = []
        for sound in SOUNDS:
            wem = media.get(sound.media_id)
            if wem is None:
                raise RuntimeError(f"Urgot media id {sound.media_id} is absent")
            wem_hash = sha256_bytes(wem)
            if wem_hash != sound.wem_sha256:
                raise RuntimeError(
                    f"WEM hash mismatch for {sound.output_stem}: expected "
                    f"{sound.wem_sha256}, got {wem_hash}"
                )
            wem_path = temp / f"{sound.media_id}.wem"
            wav_path = temp / sound.output
            wem_path.write_bytes(wem)
            completed = subprocess.run(
                [str(vgmstream), "-i", "-W", "1", "-o", str(wav_path), str(wem_path)],
                check=False, capture_output=True, text=True,
            )
            if completed.returncode != 0 or not wav_path.is_file():
                details = (completed.stderr or completed.stdout).strip()
                raise RuntimeError(
                    f"vgmstream failed for {sound.output_stem} "
                    f"(exit {completed.returncode}): {details}"
                )
            wav = inspect_pcm_wav(wav_path)
            duration = float(wav["duration_seconds"])
            if abs(duration - sound.expected_duration_seconds) > 0.000_001:
                raise RuntimeError(
                    f"duration mismatch for {sound.output_stem}: expected about "
                    f"{sound.expected_duration_seconds:.9f}, got {duration:.9f}"
                )
            wav_hash = sha256_file(wav_path)
            if wav_hash != sound.expected_wav_sha256:
                raise RuntimeError(
                    f"decoded WAV hash mismatch for {sound.output_stem}: expected "
                    f"{sound.expected_wav_sha256}, got {wav_hash}"
                )
            pending.append((wav_path, output / sound.output))
            info_path = temp / f"{sound.output_stem}.sound_info"
            write_sound_info(info_path, f"{sound.output_stem}_clip")
            pending.append((info_path, output / info_path.name))
            reports.append(
                {
                    "event_key": sound.output_stem,
                    "runtime_event": sound.runtime_event,
                    "riot_event": sound.event,
                    "riot_event_id": sound.event_id,
                    "event_media_pool": list(sound.event_media_pool),
                    "media_id": sound.media_id,
                    "source_wem_size_bytes": len(wem),
                    "source_wem_sha256": wem_hash,
                    "selection_note": sound.selection_note,
                    "dispatch_contract": sound.dispatch,
                    "sound_info": f"sound/sfx/{sound.output_stem}.sound_info",
                    "clip": f"{sound.output_stem}_clip",
                    "volume": 1.0,
                    "wav": {
                        "path": f"sound/sfx/{sound.output}",
                        "size_bytes": wav_path.stat().st_size,
                        "sha256": wav_hash,
                        **wav,
                    },
                }
            )
        silence_path = temp / SILENCE_OUTPUT
        silence = write_silence(silence_path)
        pending.append((silence_path, output / SILENCE_OUTPUT))
        silence_info = temp / "urgot_native_silence.sound_info"
        write_sound_info(silence_info, "urgot_native_silence_clip")
        pending.append((silence_info, output / silence_info.name))
        for source, destination in pending:
            source.replace(destination)
    return reports, silence


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wad", type=Path, default=DEFAULT_WAD)
    parser.add_argument("--wadtools", type=Path, default=DEFAULT_WADTOOLS)
    parser.add_argument("--wwiser", type=Path, default=DEFAULT_WWISER)
    parser.add_argument("--vgmstream", type=Path, default=DEFAULT_VGMSTREAM)
    parser.add_argument("--hashtable", type=Path, default=DEFAULT_HASHTABLE)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    wad = args.wad.resolve()
    wadtools = args.wadtools.resolve()
    wwiser = args.wwiser.resolve()
    vgmstream = args.vgmstream.resolve()
    hashtable = args.hashtable.resolve()
    output = args.out.resolve()
    report_path = args.report.resolve()

    verify_file(wad, WAD_SIZE, WAD_SHA256, "Urgot WAD")
    verify_file(wadtools, None, WADTOOLS_SHA256, "wadtools")
    verify_file(wwiser, None, WWISER_SHA256, "wwiser")
    verify_file(vgmstream, None, VGMSTREAM_SHA256, "vgmstream-cli")
    verify_file(hashtable, HASHTABLE_SIZE, HASHTABLE_SHA256, "hashes.game.txt")

    with tempfile.TemporaryDirectory(prefix="urgot_banks_") as temp_name:
        temp = Path(temp_name)
        audio_path, event_path, registry_path = extract_sources(
            wad, wadtools, hashtable, temp
        )
        verify_file(audio_path, AUDIO_BANK_SIZE, AUDIO_BANK_SHA256, "Urgot audio bank")
        verify_file(event_path, EVENT_BANK_SIZE, EVENT_BANK_SHA256, "Urgot event bank")
        verify_file(registry_path, REGISTRY_SIZE, REGISTRY_SHA256, "Urgot base registry")
        verify_event_registry(registry_path)
        resolve_event_media_pools(audio_path, event_path, wwiser, temp / "wwiser_txtp")
        sounds, silence = decode_sounds(audio_path.read_bytes(), vgmstream, output)

    report = {
        "schema_version": 1,
        "champion": "Urgot",
        "source_product": "League of Legends",
        "source_wad": {
            "path": f"{WAD_RELATIVE_PATH} (local League install)",
            "size_bytes": WAD_SIZE,
            "sha256": WAD_SHA256,
        },
        "base_registry": {
            "virtual_path": REGISTRY_PATH,
            "wad_path_hash": REGISTRY_PATH_HASH,
            "size_bytes": REGISTRY_SIZE,
            "sha256": REGISTRY_SHA256,
            "role": "authoritative source of exact Riot event-name strings",
        },
        "internal_audio_bank": {
            "virtual_path": AUDIO_BANK_PATH,
            "wad_path_hash": AUDIO_BANK_PATH_HASH,
            "size_bytes": AUDIO_BANK_SIZE,
            "media_count": AUDIO_BANK_MEDIA_COUNT,
            "sha256": AUDIO_BANK_SHA256,
        },
        "internal_event_bank": {
            "virtual_path": EVENT_BANK_PATH,
            "wad_path_hash": EVENT_BANK_PATH_HASH,
            "size_bytes": EVENT_BANK_SIZE,
            "sha256": EVENT_BANK_SHA256,
        },
        "mapping_tools": {
            "wad_reader": {
                "name": "LeagueToolkit wadtools",
                "version": WADTOOLS_VERSION,
                "sha256": WADTOOLS_SHA256,
            },
            "path_hashtable": {
                "name": "CommunityDragon hashes.game.txt",
                "size_bytes": HASHTABLE_SIZE,
                "sha256": HASHTABLE_SHA256,
            },
            "event_resolver": {
                "name": "wwiser",
                "version": WWISER_VERSION,
                "sha256": WWISER_SHA256,
                "contract": "every pinned Riot event ID resolves to exactly its recorded WEM pool",
            },
            "decoder": {
                "name": "vgmstream-cli",
                "sha256": VGMSTREAM_SHA256,
                "arguments": ["-i", "-W", "1"],
                "output_contract": "mono 16-bit PCM 44100 Hz",
            },
        },
        "selection_policy": (
            "One verified official mono base-skin media variant per runtime event. "
            "The route covers attack cast/hit, W cast/shot, E cast/hit, and R "
            "cast/latch/pull/execute/fear without adding voice-over or skin audio."
        ),
        "native_audio_isolation": {
            "reason": (
                "The occupied Demon slot can auto-dispatch its original attack, "
                "transform, skill and ultimate audio beside explicit Urgot effects."
            ),
            "strategy": (
                "Remap every bundled Demon sound event/clip plus skill2 compatibility "
                "keys to one deterministic physical-silence asset."
            ),
            "bundled_native_events": list(BUNDLED_NATIVE_EVENTS),
            "bundled_native_clips": list(BUNDLED_NATIVE_CLIPS),
            "compatibility_native_events": list(COMPATIBILITY_NATIVE_EVENTS),
            "compatibility_native_clips": list(COMPATIBILITY_NATIVE_CLIPS),
            "silence_sound_info": "sound/sfx/urgot_native_silence.sound_info",
            "silence_wav": silence,
        },
        "outputs": sounds,
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(report_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
