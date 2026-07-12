#!/usr/bin/env python3
"""Extract the pinned official Kled SFX from Riot's local base-skin banks."""

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
        "LOL_KLED_WAD",
        r"D:\Riot Games\League of Legends\Game\DATA\FINAL\Champions\Kled.wad.client",
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
DEFAULT_REPORT = MOD_ROOT / "qa" / "kled_official_audio_sources.json"

WAD_RELATIVE_PATH = "Game/DATA/FINAL/Champions/Kled.wad.client"
WAD_SIZE = 75_430_449
WAD_SHA256 = "343a644f6f7789a1c9f045487d194676d069a25a2d487c29e8ec67a4890ac08d"

AUDIO_BANK_PATH = (
    "assets/sounds/wwise2016/sfx/characters/kled/skins/base/"
    "kled_base_sfx_audio.bnk"
)
AUDIO_BANK_PATH_HASH = "14aa018fac05d2ee"
AUDIO_BANK_OFFSET = 66_263_216
AUDIO_BANK_SIZE = 4_965_917
AUDIO_BANK_MEDIA_COUNT = 220
AUDIO_BANK_SHA256 = "5efbec758d08b64b61141a93556bcdea026fe5cf883e5e25335a41cb19c095cd"

EVENT_BANK_PATH = (
    "assets/sounds/wwise2016/sfx/characters/kled/skins/base/"
    "kled_base_sfx_events.bnk"
)
EVENT_BANK_PATH_HASH = "b797a4f4c887adfc"
EVENT_BANK_SIZE = 32_718
EVENT_BANK_SHA256 = "353fea9d45cbad815c8f0e14cb7e3143a218726face0ba2fe7ab647e6720d968"

REGISTRY_PATH = "data/characters/kled/skins/skin0.bin"
REGISTRY_PATH_HASH = "6e9063e0b5ae183c"
REGISTRY_SIZE = 59_263
REGISTRY_SHA256 = "676b7da0d480055d0b239f52c0b8b6e488487c7a87e50dcf9d380dc62fa63678"

WADTOOLS_VERSION = "0.5.6"
WADTOOLS_SHA256 = "c11b60cc8016c3d986eceb91c3c9fd74e4440416ba2a215af1135f36bd0fa866"
WWISER_VERSION = "v20250928"
WWISER_SHA256 = "fdcb850ad19d827190a1eb137c2caa02c40671e15c379a6c9a477d2a5237bf53"
VGMSTREAM_SHA256 = "894cff498bbb7d43fcbae63aac9dc19ebbef8f37c9889c4a9e51de407b5f3c07"
HASHTABLE_SIZE = 207_968_174
HASHTABLE_SHA256 = "f7d5e73ff1c4b7b4630cef6d4bafe3d1b7a80a2f51e3bf9d4db4e018954d041b"

SILENCE_OUTPUT = "kled_native_silence_clip.wav"
SILENCE_FRAME_COUNT = 2_205
SILENCE_SHA256 = "73b42ab23be05ebeada04e01d7a8b903a1cdd1753a090c5032983da1066bacc2"

NATIVE_EVENTS = (
    "cavalry_knight_attack",
    "cavalry_knight_skill1",
    "cavalry_knight_skill2",
    "cavalry_knight_ult",
)
NATIVE_CLIPS = (
    "cavalry_knight_attack_resource",
    "cavalry_knight_skill_resource",
    "cavalry_knight_skill2_resource",
    "cavalry_knight_ult_resource",
)


@dataclass(frozen=True)
class KledSound:
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
    KledSound(
        "kled_attack_cast",
        21_147_659,
        "Play_sfx_Kled_KledBasicAttack_OnCast",
        614_054_878,
        (21_147_659, 304_822_030, 289_578_442, 662_420_373),
        "09aa3fdeacd043b135595d5fe40754c2376783aa93c7b8b782e2b6cf144c103d",
        0.792857143,
        "16fd3a29dc284076f54844c371d9cf8597c2bfaafbd55b81854bee7a28a208c9",
        "top-level Sfx on a committed basic attack",
        "first verified official random variant",
    ),
    KledSound(
        "kled_attack_hit",
        63_644_041,
        "Play_sfx_Kled_KledBasicAttack_OnHit",
        2_087_708_778,
        (
            63_644_041,
            381_578_354,
            722_662_972,
            82_553_652,
            21_523_865,
            259_892_625,
            168_126_585,
            177_381_556,
            215_418_368,
            13_175_684,
            51_196_262,
            342_377_734,
        ),
        "18cc1c090124202d3ec8ff0a7edd566a7a8fcffe94fbd51bafa1bb4281c9ce01",
        0.886394558,
        "39be91248916c1336c5c2c5bb007928c5e0c57e8ee1b50ab72c0df27288bae22",
        "TargetSfx after basic-attack damage",
        "first variant in the registry event's default non-Metal/Stone/Wood switch",
    ),
    KledSound(
        "kled_q_cast",
        424_442_923,
        "Play_sfx_Kled_KledQMissile_OnMissileLaunch",
        4_172_382_407,
        (424_442_923, 548_505_374),
        "551d1346a70a36a7876c00d4f0bbb9ed234217ad941d64717eb84a4560bf48e1",
        1.037165533,
        "a5a9a8dd86d83d571f9a7376556c456d2d2ffae68b7e31519be3ddb9a6e2cde9",
        "top-level Sfx once when Q's tether projectile launches",
        "first verified official missile-launch variant",
    ),
    KledSound(
        "kled_e_cast",
        710_520_340,
        "Play_sfx_Kled_KledEDash_OnCast",
        1_674_234_959,
        (710_520_340, 496_277_959, 421_766_018),
        "479780b4756fbe6e78c032e3ccef024f8d13d1a80ca0fca71c8110334690a625",
        1.011065760,
        "9683f33775376ddd3792548c1cd0669a18ce6e486e02e4aaa57691dc445afba4",
        "top-level Sfx when E's rush starts",
        "first verified E-dash cast variant",
    ),
    KledSound(
        "kled_e_hit",
        106_322_629,
        "Play_sfx_Kled_KledEDash_hit",
        3_194_949_684,
        (106_322_629, 3_549_207, 410_629_194),
        "ab1462ca1f851f73beaeee6cd7ef3a6fa0ca28616072d781a7624a2c873121d0",
        0.459183673,
        "dd1c1546c73c43a99fb120a67fb438867bc1086485d39cc657188fe5d0ac4a13",
        "TargetSfx on the first champion hit",
        "first verified E-dash hit variant",
    ),
    KledSound(
        "kled_q_tether_on",
        924_850_781,
        "Play_sfx_Kled_KledQMark_OnBuffActivate",
        628_191_751,
        (924_850_781,),
        "f2fb74701f7becc2295c80fa4dd481fa7a33830d8f983e800e8b69b23ce7d70f",
        1.889682540,
        "7538eff20d0632182d99c92df2774eab9e6c42f45e577b8e03b1ed93bcc5b25e",
        "TargetSfx once when the tether mark is attached",
        "the event has one official media source",
    ),
    KledSound(
        "kled_q_pull",
        251_183_905,
        "Play_sfx_Kled_KledQMark_buffdeactivate",
        3_440_948_969,
        (251_183_905,),
        "e89b8362928110b34f715ddbcf59747d35e12a480faa6bc50b9ff1d8b95e0187",
        1.432517007,
        "e99807a667fd5598f24977b87ec5ad4f083ec1b27714852e86c11c0eb14526e3",
        "TargetSfx only in Q's delayed pull stage",
        "the event has one official media source",
    ),
    KledSound(
        "kled_r_cast",
        784_135_814,
        "Play_sfx_Kled_KledRDash_cast",
        1_823_908_737,
        (784_135_814,),
        "d7877dfb3b8a058a8bdfa436a9e002071f4fc3d619f927ba1fccdcaabf21ca91",
        1.748752834,
        "0cbd97fdf6a13888643e549c59dbf4ffbc466a874f189ab64f29b3c75682a6fa",
        "top-level Sfx once when the R rush starts",
        "deterministic mono one-shot; avoids KledR_cast's 3.2-3.8s stereo sequence",
    ),
    KledSound(
        "kled_r_impact",
        1_050_508_665,
        "Play_sfx_Kled_KledRDash_hit",
        273_852_443,
        (1_050_508_665,),
        "129822a918be8f4b24e33f671d4e8806d9b390083538557963787feef238445d",
        2.546235828,
        "f73a745601d5498223b1db2aa6a5c165a6574567fcc5b02ec6fbbe5064a21081",
        "TargetSfx once on the first R collision",
        "the event has one official media source",
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


def verify_file(path: Path, expected_size: int | None, expected_sha256: str, name: str) -> None:
    if not path.is_file():
        raise FileNotFoundError(f"{name} not found: {path}")
    if expected_size is not None and path.stat().st_size != expected_size:
        raise RuntimeError(
            f"{name} size mismatch: expected {expected_size}, got {path.stat().st_size}"
        )
    actual_hash = sha256_file(path)
    if actual_hash != expected_sha256:
        raise RuntimeError(
            f"{name} SHA-256 mismatch: expected {expected_sha256}, got {actual_hash}"
        )


def fnv1_lower(value: str) -> int:
    result = 2_166_136_261
    for byte in value.lower().encode("utf-8"):
        result = ((result * 16_777_619) & 0xFFFF_FFFF) ^ byte
    return result


def extract_sources(
    wad: Path, wadtools: Path, hashtable: Path, output: Path
) -> tuple[Path, Path, Path]:
    command = [
        str(wadtools),
        "--progress=false",
        "extract",
        "-i",
        str(wad),
        "-o",
        str(output),
        "--hashtable",
        str(hashtable),
        "--hash",
        AUDIO_BANK_PATH_HASH,
        EVENT_BANK_PATH_HASH,
        REGISTRY_PATH_HASH,
        "--overwrite",
        "--stats=false",
    ]
    completed = subprocess.run(command, check=False, capture_output=True, text=True)
    if completed.returncode != 0:
        details = (completed.stderr or completed.stdout).strip()
        raise RuntimeError(f"wadtools failed with exit {completed.returncode}: {details}")
    audio = output / Path(AUDIO_BANK_PATH)
    events = output / Path(EVENT_BANK_PATH)
    registry = output / Path(REGISTRY_PATH)
    if not audio.is_file() or not events.is_file() or not registry.is_file():
        raise RuntimeError("wadtools did not extract all three pinned Kled sources")
    return audio, events, registry


def verify_event_registry(registry: Path) -> None:
    payload = registry.read_bytes()
    for sound in SOUNDS:
        if fnv1_lower(sound.event) != sound.event_id:
            raise RuntimeError(f"FNV-1 event ID mismatch for {sound.event}")
        if sound.event.encode("ascii") not in payload:
            raise RuntimeError(f"Kled base registry is missing {sound.event}")


def resolve_event_media_pools(
    audio_bank: Path, event_bank: Path, wwiser: Path, output: Path
) -> dict[int, set[int]]:
    output.mkdir(parents=True, exist_ok=True)
    event_ids = sorted({sound.event_id for sound in SOUNDS})
    command = [
        sys.executable,
        str(wwiser),
        str(audio_bank),
        str(event_bank),
        "-g",
        "-gu",
        "-go",
        str(output),
        "-gw",
        str(audio_bank.parent),
        "-gf",
        *[str(event_id) for event_id in event_ids],
        "-gnw",
        "-gnv",
        "-gxni",
    ]
    completed = subprocess.run(command, check=False, capture_output=True, text=True)
    if completed.returncode != 0:
        details = (completed.stderr or completed.stdout).strip()
        raise RuntimeError(f"wwiser failed with exit {completed.returncode}: {details}")

    resolved = {event_id: set() for event_id in event_ids}
    for txtp in output.rglob("*.txtp"):
        event_match = re.search(r"event-(\d+)(?:\D|$)", txtp.name)
        if event_match is None:
            continue
        event_id = int(event_match.group(1))
        if event_id not in resolved:
            continue
        payload = txtp.read_text(encoding="utf-8", errors="strict")
        resolved[event_id].update(
            int(match.group(1)) for match in re.finditer(r"##(\d+)\.wem", payload)
        )

    for sound in SOUNDS:
        expected = set(sound.event_media_pool)
        actual = resolved[sound.event_id]
        if actual != expected:
            raise RuntimeError(
                f"wwiser media-pool mismatch for {sound.event}: "
                f"expected {sorted(expected)}, got {sorted(actual)}"
            )
    return resolved


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
            f"Kled audio bank media count mismatch: expected {AUDIO_BANK_MEDIA_COUNT}, "
            f"got {len(media)}"
        )
    output.mkdir(parents=True, exist_ok=True)
    reports: list[dict[str, object]] = []
    with tempfile.TemporaryDirectory(prefix=".kled_audio_", dir=output) as temp_name:
        temp = Path(temp_name)
        pending: list[tuple[Path, Path]] = []
        for sound in SOUNDS:
            wem = media.get(sound.media_id)
            if wem is None:
                raise RuntimeError(f"Kled media id {sound.media_id} is absent")
            actual_wem_hash = sha256_bytes(wem)
            if actual_wem_hash != sound.wem_sha256:
                raise RuntimeError(
                    f"WEM hash mismatch for {sound.output_stem}: expected "
                    f"{sound.wem_sha256}, got {actual_wem_hash}"
                )
            wem_path = temp / f"{sound.media_id}.wem"
            wav_path = temp / sound.output
            wem_path.write_bytes(wem)
            completed = subprocess.run(
                [str(vgmstream), "-i", "-W", "1", "-o", str(wav_path), str(wem_path)],
                check=False,
                capture_output=True,
                text=True,
            )
            if completed.returncode != 0 or not wav_path.is_file():
                details = (completed.stderr or completed.stdout).strip()
                raise RuntimeError(
                    f"vgmstream failed for {sound.output_stem} "
                    f"(exit {completed.returncode}): {details}"
                )
            wav = inspect_pcm_wav(wav_path)
            duration = float(wav["duration_seconds"])
            if abs(duration - sound.expected_duration_seconds) > 0.015:
                raise RuntimeError(
                    f"duration mismatch for {sound.output_stem}: expected about "
                    f"{sound.expected_duration_seconds:.9f}, got {duration:.9f}"
                )
            actual_wav_hash = sha256_file(wav_path)
            if actual_wav_hash != sound.expected_wav_sha256:
                raise RuntimeError(
                    f"decoded WAV hash mismatch for {sound.output_stem}: expected "
                    f"{sound.expected_wav_sha256}, got {actual_wav_hash}"
                )
            destination = output / sound.output
            pending.append((wav_path, destination))
            reports.append(
                {
                    "event_key": sound.output_stem,
                    "runtime_event": sound.runtime_event,
                    "riot_event": sound.event,
                    "riot_event_id": sound.event_id,
                    "event_media_pool": list(sound.event_media_pool),
                    "media_id": sound.media_id,
                    "source_wem_size_bytes": len(wem),
                    "source_wem_sha256": actual_wem_hash,
                    "selection_note": sound.selection_note,
                    "dispatch_contract": sound.dispatch,
                    "sound_info": f"sound/sfx/{sound.output_stem}.sound_info",
                    "clip": f"{sound.output_stem}_clip",
                    "volume": 1.0,
                    "wav": {
                        "path": f"sound/sfx/{sound.output}",
                        "size_bytes": wav_path.stat().st_size,
                        "sha256": actual_wav_hash,
                        **wav,
                    },
                }
            )
        silence_path = temp / SILENCE_OUTPUT
        silence = write_silence(silence_path)
        pending.append((silence_path, output / SILENCE_OUTPUT))
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

    verify_file(wad, WAD_SIZE, WAD_SHA256, "Kled WAD")
    verify_file(wadtools, None, WADTOOLS_SHA256, "wadtools")
    verify_file(wwiser, None, WWISER_SHA256, "wwiser")
    verify_file(vgmstream, None, VGMSTREAM_SHA256, "vgmstream-cli")
    verify_file(hashtable, HASHTABLE_SIZE, HASHTABLE_SHA256, "hashes.game.txt")

    with tempfile.TemporaryDirectory(prefix="kled_banks_") as temp_name:
        temp = Path(temp_name)
        audio_path, event_path, registry_path = extract_sources(
            wad, wadtools, hashtable, temp
        )
        verify_file(audio_path, AUDIO_BANK_SIZE, AUDIO_BANK_SHA256, "Kled audio bank")
        verify_file(event_path, EVENT_BANK_SIZE, EVENT_BANK_SHA256, "Kled event bank")
        verify_file(registry_path, REGISTRY_SIZE, REGISTRY_SHA256, "Kled base registry")
        verify_event_registry(registry_path)
        resolve_event_media_pools(
            audio_path, event_path, wwiser, temp / "wwiser_txtp"
        )
        sounds, silence = decode_sounds(audio_path.read_bytes(), vgmstream, output)

    report = {
        "schema_version": 1,
        "champion": "Kled",
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
            "role": "authoritative source of the exact Riot event-name strings",
        },
        "internal_audio_bank": {
            "virtual_path": AUDIO_BANK_PATH,
            "wad_path_hash": AUDIO_BANK_PATH_HASH,
            "wad_offset": AUDIO_BANK_OFFSET,
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
            "Q uses one missile-launch event plus mark attach/release; E uses its dash "
            "cast/hit events; R uses deterministic one-shot dash cast/hit events and "
            "deliberately omits "
            "all continuous or stereo sequence events."
        ),
        "native_audio_isolation": {
            "reason": (
                "The same-ID native Cavalry action layer can auto-dispatch its original "
                "attack/Q/E/R audio in addition to explicit Kled effects."
            ),
            "strategy": (
                "Remap all four native events and all four source clips to one deterministic "
                "physical-silence asset."
            ),
            "native_events": list(NATIVE_EVENTS),
            "native_clips": list(NATIVE_CLIPS),
            "silence_sound_info": "sound/sfx/kled_native_silence.sound_info",
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
