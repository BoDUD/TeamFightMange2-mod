#!/usr/bin/env python3
"""Extract pinned official base-skin Yone SFX from Riot's local WAD files."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import struct
import subprocess
import sys
import tempfile
import wave

from extract_briar_audio import extract_wem_media, inspect_pcm_wav


MOD_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_WAD = Path(
    os.environ.get(
        "LOL_YONE_WAD",
        r"D:\Riot Games\League of Legends\Game\DATA\FINAL\Champions\Yone.wad.client",
    )
)
DEFAULT_LOCALIZED_WAD = Path(
    os.environ.get(
        "LOL_YONE_LOCALIZED_WAD",
        r"D:\Riot Games\League of Legends\Game\DATA\FINAL\Champions\Yone.en_US.wad.client",
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
DEFAULT_REPORT = MOD_ROOT / "qa" / "yone_official_audio_sources.json"

WAD_RELATIVE_PATH = "Game/DATA/FINAL/Champions/Yone.wad.client"
WAD_SIZE = 167_594_017
WAD_SHA256 = "e2ba1213c33e90972369091d3cc5bc9dfc7e05dcf93bd5d2d2ea95f5eb8f2b86"
LOCALIZED_WAD_RELATIVE_PATH = "Game/DATA/FINAL/Champions/Yone.en_US.wad.client"
LOCALIZED_WAD_SIZE = 26_048_051
LOCALIZED_WAD_SHA256 = "1d890a865b381c8bcf23c8152a3fe4eb6527b4746515b3069d75126d33687511"

AUDIO_BANK_PATH = (
    "assets/sounds/wwise2016/sfx/characters/yone/skins/base/"
    "yone_base_sfx_audio.bnk"
)
AUDIO_BANK_PATH_HASH = "11d9e5a6e935a89a"
AUDIO_BANK_OFFSET = 111_244_233
AUDIO_BANK_SIZE = 1_593_203
AUDIO_BANK_MEDIA_COUNT = 78
AUDIO_BANK_SHA256 = "e3f5f4e8334d3779355fb861a9fa8bba284194b4e52a6610bdfc10724169caf5"

EVENT_BANK_PATH = (
    "assets/sounds/wwise2016/sfx/characters/yone/skins/base/"
    "yone_base_sfx_events.bnk"
)
EVENT_BANK_PATH_HASH = "ef999c04f1bf053b"
EVENT_BANK_SIZE = 13_992
EVENT_BANK_SHA256 = "85862cb6095b9c0412be011be4eb567ed380694eaacc424ac00fb1a757a38934"

REGISTRY_PATH = "data/characters/yone/skins/skin0.bin"
REGISTRY_PATH_HASH = "75d1aee7cd24ec51"
REGISTRY_SIZE = 242_465
REGISTRY_SHA256 = "aee952d9f131e420f63d763bf76c280230787cd19e89f43f9f432bd8834b8958"

WADTOOLS_VERSION = "0.5.6"
WADTOOLS_SHA256 = "c11b60cc8016c3d986eceb91c3c9fd74e4440416ba2a215af1135f36bd0fa866"
WWISER_VERSION = "v20250928"
WWISER_SHA256 = "fdcb850ad19d827190a1eb137c2caa02c40671e15c379a6c9a477d2a5237bf53"
VGMSTREAM_SHA256 = "894cff498bbb7d43fcbae63aac9dc19ebbef8f37c9889c4a9e51de407b5f3c07"
HASHTABLE_SIZE = 207_968_174
HASHTABLE_SHA256 = "f7d5e73ff1c4b7b4630cef6d4bafe3d1b7a80a2f51e3bf9d4db4e018954d041b"

SILENCE_STEM = "yone_native_silence"
SILENCE_FRAME_COUNT = 2_205
SILENCE_SHA256 = "73b42ab23be05ebeada04e01d7a8b903a1cdd1753a090c5032983da1066bacc2"

NATIVE_EVENTS = (
    "dual_blader_attack",
    "dual_blader_skill",
    "dual_blader_skill2",
    "dual_blader_ult",
)
NATIVE_CLIPS = (
    "duel_blader_attack0",
    "duel_blader_attack1",
    "duel_blader_skill0",
    "duel_blader_skill1",
    "dual_blader_skill_resource",
    "dual_blader_skill2_resource",
    "duel_blader_ult0",
)
OBSOLETE_OUTPUT_STEMS = (
    "lol_yone_attack_cast",
    "lol_yone_attack_hit",
)


@dataclass(frozen=True)
class YoneSound:
    output_stem: str
    media_id: int
    event: str
    event_id: int
    event_media_pool: tuple[int, ...]
    selection_media_pool: tuple[int, ...]
    wem_sha256: str
    expected_duration_seconds: float
    expected_wav_sha256: str
    dispatch: str
    selection_note: str
    volume: float = 1.0
    trim_frames: int | None = None
    fade_out_frames: int = 0
    expected_output_wav_sha256: str | None = None

    @property
    def output(self) -> str:
        return f"{self.output_stem}_clip.wav"

    @property
    def sound_info(self) -> str:
        return f"{self.output_stem}.sound_info"


ATTACK_HIT_FULL_POOL = (
    4_593_285,
    52_943_608,
    121_056_189,
    32_292_976,
    919_359_318,
    842_472_437,
    281_183_040,
    745_450_098,
    741_852_174,
    1_004_687_225,
    194_476_454,
    828_962_726,
    455_681_162,
    291_043_766,
    174_690_742,
    179_499_491,
    447_192_276,
    1_070_249_125,
    916_548_822,
    286_640_978,
)
ATTACK_HIT_BLADE_POOL = (4_593_285, 52_943_608, 121_056_189, 32_292_976)

SOUNDS = (
    YoneSound(
        "lol_yone_attack_steel_cast",
        71_487_904,
        "Play_sfx_Yone_YoneBasicAttack_OnCast",
        1_242_050_256,
        (71_487_904, 2_465_604, 17_265_215, 504_802_946),
        (71_487_904, 2_465_604, 17_265_215, 504_802_946),
        "881a5e60b368681f43cda756d90ae06652101f59fdf58cabbd1eb8bc2305062e",
        1.197437642,
        "8bfe795a23f2fe047ddc01f2a5b9a7950b77adf8c8df6bbf957274deba25d5eb",
        "top-level Sfx on a committed steel-sword basic attack",
        "first official shared attack-cast variant, deterministically assigned to the steel sword",
    ),
    YoneSound(
        "lol_yone_attack_azakana_cast",
        2_465_604,
        "Play_sfx_Yone_YoneBasicAttack_OnCast",
        1_242_050_256,
        (71_487_904, 2_465_604, 17_265_215, 504_802_946),
        (71_487_904, 2_465_604, 17_265_215, 504_802_946),
        "9658f7b1e5c64afee1bf333cf7913a6514539e851faf3623189ca3bc28367456",
        1.100385488,
        "8329b30c4d4265bb72ff75fc35b1dcd5e55a280ccc6d1e92cd4b2cba79445343",
        "top-level Sfx on a committed Azakana-sword basic attack",
        "second official shared attack-cast variant, deterministically assigned to the Azakana sword",
    ),
    YoneSound(
        "lol_yone_attack_steel_hit",
        4_593_285,
        "Play_sfx_Yone_YoneBasicAttack_OnHit",
        1_731_923_344,
        ATTACK_HIT_FULL_POOL,
        ATTACK_HIT_BLADE_POOL,
        "ab9ac24263500d1046ebfb9046df03b47d1ae23bbc4cce43fa1d5cdf54a0edc4",
        0.915192744,
        "b64ba4ce48bb2f02e2e09abf3df19d12834631ea21f8d5f94fe12ecff22d1552",
        "TargetSfx immediately after steel-sword basic-attack damage",
        "first official common blade-hit variant, deterministically assigned to the steel sword; material layers excluded",
    ),
    YoneSound(
        "lol_yone_attack_azakana_hit",
        52_943_608,
        "Play_sfx_Yone_YoneBasicAttack_OnHit",
        1_731_923_344,
        ATTACK_HIT_FULL_POOL,
        ATTACK_HIT_BLADE_POOL,
        "b0d76ed24a4b4194be23a2987d7001f657376cf7eb0ee23da37e761a1f625e33",
        0.857981859,
        "dc6878f472a213a5bfbe04a729007f5cad071de9558e42e0375bdd64a7f89bf1",
        "TargetSfx immediately after Azakana-sword basic-attack damage",
        "second official common blade-hit variant, deterministically assigned to the Azakana sword; material layers excluded",
    ),
    YoneSound(
        "lol_yone_q_cast",
        115_778_047,
        "Play_sfx_Yone_YoneQ_OnCast",
        2_588_831_761,
        (115_778_047, 924_281_416),
        (115_778_047, 924_281_416),
        "a930ea82bcf32c63ce3f3442007008bb374690aad086fb51f31da1944752035b",
        2.001451247,
        "dd9776d3950ccbb40917f2f822e17eec3b8b91dffebe4ee99c28929205146133",
        "top-level Sfx once when normal Q launches",
        "first official normal-Q cast variant in event order",
    ),
    YoneSound(
        "lol_yone_q_hit",
        200_471_654,
        "Play_sfx_Yone_YoneQ_hit",
        4_255_270_898,
        (200_471_654, 528_184_656),
        (200_471_654, 528_184_656),
        "5a620971be9b7a055dcd63d7f701e4940e56d29178943430cac9263c8992b0ff",
        2.002267574,
        "48c5b1782693c142544a0252b69916b5352d47d83acec9c38f2abe3960139838",
        "TargetSfx only when normal Q hits",
        "first official normal-Q hit variant in event order",
    ),
    YoneSound(
        "lol_yone_q_empowered_cast",
        667_080_352,
        "Play_sfx_Yone_YoneQ3_OnCast",
        1_077_941_672,
        (667_080_352, 992_100_996, 828_184_909, 695_270_834),
        (667_080_352, 992_100_996, 828_184_909, 695_270_834),
        "2a56d3b19c38b0eb4d61ee24f7185c9413b527a086c0bea5836d165c842ef483",
        3.543696145,
        "ecb4bdb8ce1fb302b0aebb81685386b2dca5688a3b73e646fbac5b70937f2f6b",
        "top-level Sfx once when empowered Q launches",
        "first official Q3 cast variant in event order",
    ),
    YoneSound(
        "lol_yone_q_empowered_hit",
        144_577_483,
        "Play_sfx_Yone_YoneQ3_hit",
        4_037_963_813,
        (144_577_483,),
        (144_577_483,),
        "bac25106d5b2812eacf75c2f31871a7d0c3a1a747451bd72b52aaf8b3dc0f0f6",
        1.580816327,
        "8ce74bd60c2d039d8706e37b45a231ba439ee0a81646d1dd94982355fe247ae6",
        "TargetSfx only when empowered Q hits",
        "the official Q3-hit event has one media source",
    ),
    YoneSound(
        "lol_yone_w_cast",
        1_031_367_120,
        "Play_sfx_Yone_YoneW_OnCast",
        2_331_891_575,
        (1_031_367_120,),
        (1_031_367_120,),
        "f2dffea55d2332702698cd9cda4589796f054b04f8f71c83ff3ef6c4ac45cb58",
        2.454625850,
        "e01f668c92c33da10692045988198359b3dbf70e4b831957f280630a41a95e3a",
        "top-level Sfx once when W begins",
        "the official W-cast event has one media source",
    ),
    YoneSound(
        "lol_yone_w_hit",
        117_104_795,
        "Play_sfx_Yone_YoneW_hit",
        3_632_890_860,
        (117_104_795,),
        (117_104_795,),
        "0c85391d1f908de176d593acc7ebd587fbb2c9f0d7e3a147b374f1fe64d64cb7",
        0.822562358,
        "05455d6ed5698e4f662387a83cd50a76a9e5552e1c10d5ab35821173da03d8bf",
        "TargetSfx only when W connects",
        "the official W-hit event has one media source",
    ),
    YoneSound(
        "lol_yone_w_shield",
        197_299_419,
        "Play_sfx_Yone_YonePShield_buffactivate",
        2_897_062_269,
        (197_299_419,),
        (197_299_419,),
        "552f244b4356567481209acb52c494bd59a36d7feb5fc9f3b75a4e5703ded0c6",
        2.373582766,
        "f9dadba4ed24767cae394876d1292634254f7802cfd686ed8d86fe3df8d5ca30",
        "optional CasterSfx when a successful W grants its shield",
        "official base-skin Yone shield activation; retained for complete W-phase coverage",
    ),
    YoneSound(
        "lol_yone_r_cast",
        57_735_016,
        "Play_sfx_Yone_YoneR_OnCast",
        2_470_223_712,
        (57_735_016, 862_736_579),
        (57_735_016, 862_736_579),
        "eba722022d038b467d3cc37e5f1caa1316639f97fc3afdaaa8b3fd1d7f4356ce",
        2.523219955,
        "98de932728df3507df27c8317b2269488356397d0e4531ea9c52b4cc1c1ef6e5",
        "top-level Sfx once when R begins",
        "first official R cast variant in event order",
    ),
    YoneSound(
        "lol_yone_r_arrival",
        583_920_156,
        "Play_sfx_Yone_YoneR_cast_dash",
        2_947_435_290,
        (583_920_156,),
        (583_920_156,),
        "fe252b5bf49d98d47e36f6387f247ef4122e78a5e919b74c2183f0617474ea07",
        3.165306122,
        "5120573f6fbe11652bc942a5ae1e3e230260091bb901f2649eddb8bab65c10a3",
        "TargetSfx once when the R rush reaches its target",
        "the official R dash event has one media source",
    ),
    YoneSound(
        "lol_yone_r_slash_steel",
        976_342_648,
        "Play_sfx_Yone_YoneR_hit_initial",
        3_008_303_652,
        (976_342_648,),
        (976_342_648,),
        "a6853685b743f20b7489f6416d6fe646519436f3dc38d56ab3c828a531eec8a7",
        2.303015873,
        "6528e1455250513702f6320aeae569bcafffb0701b4009a6ba8731d99c70a00e",
        "TargetSfx on the first/steel R strike stage",
        "the official R initial-hit event has one media source; runtime cadence uses a deterministic 0.20-second excerpt with a short click-safe tail",
        volume=0.55,
        trim_frames=8_820,
        fade_out_frames=1_764,
        expected_output_wav_sha256="4db973f0465e87a756b4946d36e1d2b1c445d5c848e1ef980fe247c68465ea40",
    ),
    YoneSound(
        "lol_yone_r_slash_azakana",
        79_035_825,
        "Play_sfx_Yone_YoneR_hit_residual",
        4_287_662_285,
        (79_035_825,),
        (79_035_825,),
        "d5e42b9cc8f0b0f2e18e3f919db9aea82de30856e823816b6b22b5ba92f60d42",
        0.825283447,
        "1a24c5b2808566960a10f2656145a4b31a88903c224c2f186ecd329a6a9bb11a",
        "TargetSfx on residual/Azakana R strike stages",
        "the official R residual-hit event has one media source; runtime cadence uses a deterministic 0.20-second excerpt with a short click-safe tail",
        volume=0.55,
        trim_frames=8_820,
        fade_out_frames=1_764,
        expected_output_wav_sha256="af55b445d6c640c825e3fb1c0ae811d4d3037072cb9e5ee760c849f8c84552d0",
    ),
    YoneSound(
        "lol_yone_r_echo",
        862_736_579,
        "Play_sfx_Yone_YoneR_OnCast",
        2_470_223_712,
        (57_735_016, 862_736_579),
        (57_735_016, 862_736_579),
        "1ebd2986a1a2b9d4a5e143b32a52ebe835bfb0d002b528409110261eec2986d5",
        2.780861678,
        "c1d15b423ace2991a5a1a5ef88a17a1565ce2ddb9714a0247f95de21b3265db9",
        "TargetSfx on the terminal fixed-damage echo",
        "second unused official base-skin R-cast variant, independently pinned and retained with its complete tail for the adapted terminal echo",
        volume=0.55,
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
        raise RuntimeError("wadtools did not extract all three pinned Yone sources")
    return audio, events, registry


def verify_event_registry(registry: Path) -> None:
    payload = registry.read_bytes()
    for sound in SOUNDS:
        if fnv1_lower(sound.event) != sound.event_id:
            raise RuntimeError(f"FNV-1 event ID mismatch for {sound.event}")
        if sound.event.encode("ascii") not in payload:
            raise RuntimeError(f"Yone base registry is missing {sound.event}")


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
        if sound.media_id not in sound.selection_media_pool:
            raise RuntimeError(f"selected media is outside the audited layer for {sound.output_stem}")
    return resolved


def sound_info_payload(stem: str, volume: float = 1.0) -> bytes:
    payload = {
        "plays": [
            {"delay": 0.0, "clip": f"{stem}_clip", "volume": volume},
        ]
    }
    return (json.dumps(payload, separators=(",", ":")) + "\n").encode("utf-8")


def trim_and_fade_pcm16_mono(
    path: Path, target_frames: int, fade_out_frames: int
) -> dict[str, int | float | str]:
    """Apply the pinned runtime-only R cadence transform deterministically."""

    if target_frames <= 0:
        raise RuntimeError("trim target must contain at least one frame")
    if fade_out_frames < 2 or fade_out_frames > target_frames:
        raise RuntimeError("fade-out must contain 2..target_frames samples")

    with wave.open(str(path), "rb") as decoded:
        params = (
            decoded.getnchannels(),
            decoded.getsampwidth(),
            decoded.getframerate(),
            decoded.getcomptype(),
        )
        source_frames = decoded.getnframes()
        raw = decoded.readframes(source_frames)
    if params != (1, 2, 44_100, "NONE"):
        raise RuntimeError(f"cannot trim unsupported WAV format: {params}")
    if source_frames < target_frames:
        raise RuntimeError(
            f"cannot trim {path.name} to {target_frames} frames from {source_frames}"
        )

    samples = list(struct.unpack(f"<{target_frames}h", raw[: target_frames * 2]))
    fade_start = target_frames - fade_out_frames
    denominator = fade_out_frames - 1
    for offset in range(fade_out_frames):
        index = fade_start + offset
        gain_numerator = denominator - offset
        sample = samples[index]
        magnitude = (abs(sample) * gain_numerator + denominator // 2) // denominator
        samples[index] = -magnitude if sample < 0 else magnitude

    with wave.open(str(path), "wb") as encoded:
        encoded.setnchannels(1)
        encoded.setsampwidth(2)
        encoded.setframerate(44_100)
        encoded.writeframes(struct.pack(f"<{target_frames}h", *samples))

    return {
        "kind": "prefix_trim_with_linear_pcm_fade_out",
        "target_frames": target_frames,
        "target_duration_seconds": target_frames / 44_100,
        "fade_out_frames": fade_out_frames,
        "fade_out_duration_seconds": fade_out_frames / 44_100,
        "terminal_sample": samples[-1],
    }


def write_silence(temp: Path) -> tuple[dict[str, object], list[tuple[Path, Path]]]:
    wav_path = temp / f"{SILENCE_STEM}_clip.wav"
    with wave.open(str(wav_path), "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(44_100)
        output.writeframes(b"\0\0" * SILENCE_FRAME_COUNT)
    if sha256_file(wav_path) != SILENCE_SHA256:
        raise RuntimeError("physical silence WAV hash changed")

    sound_info_path = temp / f"{SILENCE_STEM}.sound_info"
    sound_info_path.write_bytes(sound_info_payload(SILENCE_STEM))
    info = {
        "sound_info": {
            "path": f"sound/sfx/{sound_info_path.name}",
            "size_bytes": sound_info_path.stat().st_size,
            "sha256": sha256_file(sound_info_path),
            "clip": f"{SILENCE_STEM}_clip",
            "volume": 1.0,
        },
        "wav": {
            "path": f"sound/sfx/{wav_path.name}",
            "size_bytes": wav_path.stat().st_size,
            "sha256": SILENCE_SHA256,
            **inspect_pcm_wav(wav_path),
            "pcm_contract": "all-zero samples",
        },
    }
    pending = [
        (sound_info_path, DEFAULT_OUTPUT / sound_info_path.name),
        (wav_path, DEFAULT_OUTPUT / wav_path.name),
    ]
    return info, pending


def decode_sounds(
    bank: bytes, vgmstream: Path, output: Path
) -> tuple[list[dict[str, object]], dict[str, object]]:
    media = extract_wem_media(bank)
    if len(media) != AUDIO_BANK_MEDIA_COUNT:
        raise RuntimeError(
            f"Yone audio bank media count mismatch: expected {AUDIO_BANK_MEDIA_COUNT}, "
            f"got {len(media)}"
        )
    output.mkdir(parents=True, exist_ok=True)
    reports: list[dict[str, object]] = []
    with tempfile.TemporaryDirectory(prefix=".yone_audio_", dir=output) as temp_name:
        temp = Path(temp_name)
        pending: list[tuple[Path, Path]] = []
        for sound in SOUNDS:
            wem = media.get(sound.media_id)
            if wem is None:
                raise RuntimeError(f"Yone media id {sound.media_id} is absent")
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
            source_wav = inspect_pcm_wav(wav_path)
            source_wav_size = wav_path.stat().st_size
            duration = float(source_wav["duration_seconds"])
            if abs(duration - sound.expected_duration_seconds) > 0.015:
                raise RuntimeError(
                    f"duration mismatch for {sound.output_stem}: expected about "
                    f"{sound.expected_duration_seconds:.9f}, got {duration:.9f}"
                )
            source_wav_hash = sha256_file(wav_path)
            if source_wav_hash != sound.expected_wav_sha256:
                raise RuntimeError(
                    f"decoded WAV hash mismatch for {sound.output_stem}: expected "
                    f"{sound.expected_wav_sha256}, got {source_wav_hash}"
                )

            transform: dict[str, int | float | str]
            if sound.trim_frames is not None:
                transform = trim_and_fade_pcm16_mono(
                    wav_path, sound.trim_frames, sound.fade_out_frames
                )
            else:
                if sound.fade_out_frames:
                    raise RuntimeError(
                        f"fade-out configured without trim for {sound.output_stem}"
                    )
                transform = {
                    "kind": "none",
                    "retained_source_frames": int(source_wav["frame_count"]),
                }

            wav = inspect_pcm_wav(wav_path)
            actual_wav_hash = sha256_file(wav_path)
            expected_output_hash = (
                sound.expected_output_wav_sha256 or sound.expected_wav_sha256
            )
            if actual_wav_hash != expected_output_hash:
                raise RuntimeError(
                    f"runtime WAV hash mismatch for {sound.output_stem}: expected "
                    f"{expected_output_hash}, got {actual_wav_hash}"
                )

            sound_info_path = temp / sound.sound_info
            sound_info_path.write_bytes(
                sound_info_payload(sound.output_stem, sound.volume)
            )
            pending.extend(
                (
                    (wav_path, output / wav_path.name),
                    (sound_info_path, output / sound_info_path.name),
                )
            )
            reports.append(
                {
                    "event_key": sound.output_stem,
                    "runtime_event": sound.output_stem,
                    "riot_event": sound.event,
                    "riot_event_id": sound.event_id,
                    "event_media_pool": list(sound.event_media_pool),
                    "selection_media_pool": list(sound.selection_media_pool),
                    "media_id": sound.media_id,
                    "source_wem_size_bytes": len(wem),
                    "source_wem_sha256": actual_wem_hash,
                    "selection_note": sound.selection_note,
                    "dispatch_contract": sound.dispatch,
                    "sound_info": {
                        "path": f"sound/sfx/{sound.sound_info}",
                        "size_bytes": sound_info_path.stat().st_size,
                        "sha256": sha256_file(sound_info_path),
                        "clip": f"{sound.output_stem}_clip",
                        "volume": sound.volume,
                    },
                    "source_decoded_wav": {
                        "size_bytes": source_wav_size,
                        "sha256": source_wav_hash,
                        **source_wav,
                    },
                    "runtime_transform": transform,
                    "wav": {
                        "path": f"sound/sfx/{sound.output}",
                        "size_bytes": wav_path.stat().st_size,
                        "sha256": actual_wav_hash,
                        **wav,
                    },
                }
            )

        silence, silence_pending = write_silence(temp)
        pending.extend(
            (source, output / destination.name) for source, destination in silence_pending
        )
        for source, destination in pending:
            source.replace(destination)
    return reports, silence


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wad", type=Path, default=DEFAULT_WAD)
    parser.add_argument("--localized-wad", type=Path, default=DEFAULT_LOCALIZED_WAD)
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
    localized_wad = args.localized_wad.resolve()
    wadtools = args.wadtools.resolve()
    wwiser = args.wwiser.resolve()
    vgmstream = args.vgmstream.resolve()
    hashtable = args.hashtable.resolve()
    output = args.out.resolve()
    report_path = args.report.resolve()

    verify_file(wad, WAD_SIZE, WAD_SHA256, "Yone WAD")
    verify_file(
        localized_wad,
        LOCALIZED_WAD_SIZE,
        LOCALIZED_WAD_SHA256,
        "Yone en_US WAD",
    )
    verify_file(wadtools, None, WADTOOLS_SHA256, "wadtools")
    verify_file(wwiser, None, WWISER_SHA256, "wwiser")
    verify_file(vgmstream, None, VGMSTREAM_SHA256, "vgmstream-cli")
    verify_file(hashtable, HASHTABLE_SIZE, HASHTABLE_SHA256, "hashes.game.txt")

    with tempfile.TemporaryDirectory(prefix="yone_banks_") as temp_name:
        temp = Path(temp_name)
        audio_path, event_path, registry_path = extract_sources(
            wad, wadtools, hashtable, temp
        )
        verify_file(audio_path, AUDIO_BANK_SIZE, AUDIO_BANK_SHA256, "Yone audio bank")
        verify_file(event_path, EVENT_BANK_SIZE, EVENT_BANK_SHA256, "Yone event bank")
        verify_file(registry_path, REGISTRY_SIZE, REGISTRY_SHA256, "Yone base registry")
        verify_event_registry(registry_path)
        resolve_event_media_pools(
            audio_path, event_path, wwiser, temp / "wwiser_txtp"
        )
        sounds, silence = decode_sounds(audio_path.read_bytes(), vgmstream, output)

    for obsolete_stem in OBSOLETE_OUTPUT_STEMS:
        (output / f"{obsolete_stem}.sound_info").unlink(missing_ok=True)
        (output / f"{obsolete_stem}_clip.wav").unlink(missing_ok=True)

    report = {
        "schema_version": 1,
        "champion": "Yone",
        "replacement_id": "dual_blader",
        "source_product": "League of Legends",
        "source_wad": {
            "path": f"{WAD_RELATIVE_PATH} (local League install)",
            "size_bytes": WAD_SIZE,
            "sha256": WAD_SHA256,
            "role": "authoritative base-skin gameplay SFX source",
        },
        "localized_wad": {
            "path": f"{LOCALIZED_WAD_RELATIVE_PATH} (local League install)",
            "size_bytes": LOCALIZED_WAD_SIZE,
            "sha256": LOCALIZED_WAD_SHA256,
            "role": (
                "pinned localized source audited for provenance; no dialogue/VO is "
                "selected because this pass uses gameplay SFX only"
            ),
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
                "contract": (
                    "each pinned Riot event ID resolves to its recorded complete WEM pool; "
                    "attack-hit material switches are audited separately from the selected blade layer"
                ),
            },
            "decoder": {
                "name": "vgmstream-cli",
                "sha256": VGMSTREAM_SHA256,
                "arguments": ["-i", "-W", "1"],
                "output_contract": "mono 16-bit PCM 44100 Hz",
            },
        },
        "dual_sword_attack_identity": {
            "source_event_contract": (
                "Riot's base skin exposes one shared randomized basic-attack cast event and "
                "one shared hit event; neither event labels variants as steel or Azakana."
            ),
            "stable_mod_assignment": {
                "steel_cast": {
                    "runtime_event": "lol_yone_attack_steel_cast",
                    "riot_event": "Play_sfx_Yone_YoneBasicAttack_OnCast",
                    "media_id": 71_487_904,
                },
                "azakana_cast": {
                    "runtime_event": "lol_yone_attack_azakana_cast",
                    "riot_event": "Play_sfx_Yone_YoneBasicAttack_OnCast",
                    "media_id": 2_465_604,
                },
                "steel_hit": {
                    "runtime_event": "lol_yone_attack_steel_hit",
                    "riot_event": "Play_sfx_Yone_YoneBasicAttack_OnHit",
                    "media_id": 4_593_285,
                },
                "azakana_hit": {
                    "runtime_event": "lol_yone_attack_azakana_hit",
                    "riot_event": "Play_sfx_Yone_YoneBasicAttack_OnHit",
                    "media_id": 52_943_608,
                },
            },
            "mod_contract": (
                "The first two distinct official cast variants and first two distinct common "
                "blade-hit variants are pinned to alternating swords so steel and Azakana "
                "always remain audibly different across deterministic rebuilds."
            ),
        },
        "selection_policy": (
            "Verified official base-skin one-shots only: two distinct basic-attack cast "
            "variants plus two distinct common blade-hit variants are assigned to steel and "
            "Azakana; normal Q cast/hit, empowered Q3 cast/hit, W cast/hit/shield, and R "
            "cast/dash/initial/residual stages retain their official events. The terminal "
            "R echo pins the unused second official base-skin R-cast variant as independent "
            "media and retains its complete tail. Continuous "
            "ambience, VO, skin variants, and material-specific attack surface layers are "
            "excluded."
        ),
        "r_runtime_audio_contract": {
            "slash_target_frames": 8_820,
            "slash_target_duration_seconds": 0.2,
            "slash_fade_out_frames": 1_764,
            "slash_fade_out_duration_seconds": 0.04,
            "slash_volume": 0.55,
            "echo_media_id": 862_736_579,
            "echo_retains_complete_source": True,
            "echo_volume": 0.55,
            "reason": (
                "Six rapid adapted R strikes need click-safe 0.20-second one-shots; the "
                "terminal echo instead uses independent official media with its full decay."
            ),
        },
        "native_audio_isolation": {
            "reason": (
                "The same-ID native Dual Blader action layer can auto-dispatch its original "
                "attack/Q/W/R audio in addition to explicit Yone effects."
            ),
            "strategy": (
                "Remap all four native events and every discovered native Dual Blader clip "
                "to one deterministic physical-silence asset."
            ),
            "native_events": list(NATIVE_EVENTS),
            "native_clips": list(NATIVE_CLIPS),
            "silence": silence,
        },
        "outputs": sounds,
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(report_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
