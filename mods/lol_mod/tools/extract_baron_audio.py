#!/usr/bin/env python3
"""Extract the pinned official Baron Nashor SFX from a local LoL Map11 WAD."""

from __future__ import annotations

import argparse
from array import array
import hashlib
import json
import os
import subprocess
import tempfile
import wave
from dataclasses import dataclass
from pathlib import Path

from extract_briar_audio import extract_wem_media, inspect_pcm_wav


DEFAULT_WAD = Path(
    os.environ.get(
        "LOL_MAP11_WAD",
        r"D:\Riot Games\League of Legends\Game\DATA\FINAL\Maps\Shipping\Map11.wad.client",
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
DEFAULT_OUTPUT = Path(__file__).resolve().parents[1] / "sound" / "sfx"
DEFAULT_REPORT = Path(__file__).resolve().parents[1] / "qa" / "baron_official_audio_sources.json"

WAD_SHA256 = "e4bdd4d26294c16fd520a17ec9dcb6eb7425564d60a4890a58313a0cd24d6868"
AUDIO_BANK_HASH = "ab0b5d792a5bf2f9"
AUDIO_BANK_PATH = "assets/sounds/wwise2016/sfx/shared/npc_map11_baron_sfx_audio.bnk"
AUDIO_BANK_SHA256 = "28f37899a0e84a18884c5503aca3ce819aa71baa3b562af2dc879ccd60c29fc0"
EVENT_BANK_HASH = "b861f66123020abf"
EVENT_BANK_PATH = "assets/sounds/wwise2016/sfx/shared/npc_map11_baron_sfx_events.bnk"
EVENT_BANK_SHA256 = "cf47d1ec6fcb9bb38748094b644b3bce7f16ff6de2e7a7b8b974111ff4cbb1ba"


@dataclass(frozen=True)
class BaronSound:
    output: str
    media_id: int
    event: str
    event_id: int
    event_media_pool: tuple[int, ...]
    wem_sha256: str
    expected_duration_seconds: float


SOUNDS = (
    BaronSound(
        "baron_attack_left_launch_clip.wav",
        183_644_790,
        "Play_sfx_SRU_Baron_BaronBasicAttack_OnMissileLaunch",
        1_130_521_025,
        (183_644_790, 218_574_885),
        "5076d8750ab1f57d832ac44d4f6d55750dd21e85c1c78ae6864e6807497d63cc",
        1.835759637,
    ),
    BaronSound(
        "baron_attack_right_launch_clip.wav",
        218_574_885,
        "Play_sfx_SRU_Baron_BaronBasicAttack_OnMissileLaunch",
        1_130_521_025,
        (183_644_790, 218_574_885),
        "a189f2cdf28c9d69a3c73b29d22358e9c0b690b1b96fb10b5c97d4b70daf47d4",
        1.785374150,
    ),
    BaronSound(
        "baron_attack_left_hit_clip.wav",
        354_923_442,
        "Play_sfx_SRU_Baron_BaronBasicAttack_OnHit",
        4_168_404_463,
        (354_923_442, 159_616_409),
        "d936b0852f57cb56fbc1064b378bcbbadee25a3e60a73f433c1ee5e7f023f966",
        0.652993197,
    ),
    BaronSound(
        "baron_attack_right_hit_clip.wav",
        159_616_409,
        "Play_sfx_SRU_Baron_BaronBasicAttack_OnHit",
        4_168_404_463,
        (354_923_442, 159_616_409),
        "90e97e571ce1621ab617055b9aa4bc7f8a7f700ca128b0c8f9427924faa923d6",
        0.733015873,
    ),
    BaronSound(
        "baron_death_body_clip.wav",
        805_446_954,
        "Play_sfx_SRU_Baron_Death_cast",
        3_912_207_834,
        (805_446_954, 869_424_594),
        "a34b171250dda77c789a325347a2053802736c63166cef63a718a4224ef96793",
        7.796485261,
    ),
    BaronSound(
        "baron_death_void_clip.wav",
        869_424_594,
        "Play_sfx_SRU_Baron_Death_cast",
        3_912_207_834,
        (805_446_954, 869_424_594),
        "16af78460312736644c458bc73ee093634afd2d55a3b3978f768137ea99ead2e",
        5.482290249,
    ),
)

DEATH_MIX_OUTPUT = "baron_death_mix_clip.wav"
DEATH_BODY_GAIN = 10.0 ** (-2.0 / 20.0)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def extract_banks(wad: Path, wadtools: Path, output: Path) -> tuple[Path, Path]:
    command = [
        str(wadtools),
        "--progress=false",
        "extract",
        "-i",
        str(wad),
        "-o",
        str(output),
        "--hash",
        AUDIO_BANK_HASH,
        EVENT_BANK_HASH,
        "--overwrite",
        "--stats=false",
    ]
    completed = subprocess.run(command, check=False, capture_output=True, text=True)
    if completed.returncode != 0:
        details = (completed.stderr or completed.stdout).strip()
        raise RuntimeError(f"wadtools failed with exit {completed.returncode}: {details}")
    audio = output / Path(AUDIO_BANK_PATH)
    events = output / Path(EVENT_BANK_PATH)
    if not audio.is_file() or not events.is_file():
        raise RuntimeError("wadtools did not extract both pinned Baron banks")
    return audio, events


def decode(bank: bytes, vgmstream: Path, output: Path) -> list[dict[str, object]]:
    media = extract_wem_media(bank)
    output.mkdir(parents=True, exist_ok=True)
    report: list[dict[str, object]] = []
    with tempfile.TemporaryDirectory(prefix=".baron_wem_", dir=output) as temp_name:
        temp = Path(temp_name)
        for sound in SOUNDS:
            wem = media.get(sound.media_id)
            if wem is None:
                raise RuntimeError(f"Baron media id {sound.media_id} is absent")
            if sha256_bytes(wem) != sound.wem_sha256:
                raise RuntimeError(f"Baron media hash mismatch: {sound.media_id}")
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
                raise RuntimeError(f"vgmstream failed for {sound.media_id}: {details}")
            wav = inspect_pcm_wav(wav_path)
            if abs(float(wav["duration_seconds"]) - sound.expected_duration_seconds) > 0.015:
                raise RuntimeError(f"unexpected duration for {sound.media_id}")
            destination = output / sound.output
            wav_path.replace(destination)
            report.append(
                {
                    "output": sound.output,
                    "output_sha256": sha256_file(destination),
                    "output_size_bytes": destination.stat().st_size,
                    "media_id": sound.media_id,
                    "wem_sha256": sound.wem_sha256,
                    "event": sound.event,
                    "event_id": sound.event_id,
                    "event_media_pool": list(sound.event_media_pool),
                    **wav,
                }
            )
    return report


def mix_death_event(output: Path) -> dict[str, object]:
    """Render the two simultaneous Wwise death-event layers into one PCM clip."""

    body_path = output / "baron_death_body_clip.wav"
    void_path = output / "baron_death_void_clip.wav"
    with wave.open(str(body_path), "rb") as body_wave, wave.open(str(void_path), "rb") as void_wave:
        body_format = (
            body_wave.getnchannels(),
            body_wave.getsampwidth(),
            body_wave.getframerate(),
            body_wave.getcomptype(),
        )
        void_format = (
            void_wave.getnchannels(),
            void_wave.getsampwidth(),
            void_wave.getframerate(),
            void_wave.getcomptype(),
        )
        if body_format != (1, 2, 44_100, "NONE") or void_format != body_format:
            raise RuntimeError(f"unexpected Baron death PCM formats: {body_format}, {void_format}")
        body_samples = array("h", body_wave.readframes(body_wave.getnframes()))
        void_samples = array("h", void_wave.readframes(void_wave.getnframes()))

    frame_count = max(len(body_samples), len(void_samples))
    mixed = array("h")
    for index in range(frame_count):
        body = body_samples[index] * DEATH_BODY_GAIN if index < len(body_samples) else 0.0
        void = void_samples[index] if index < len(void_samples) else 0.0
        mixed.append(max(-32_768, min(32_767, round(body + void))))

    destination = output / DEATH_MIX_OUTPUT
    with wave.open(str(destination), "wb") as mixed_wave:
        mixed_wave.setnchannels(1)
        mixed_wave.setsampwidth(2)
        mixed_wave.setframerate(44_100)
        mixed_wave.writeframes(mixed.tobytes())
    return {
        "output": DEATH_MIX_OUTPUT,
        "output_sha256": sha256_file(destination),
        "output_size_bytes": destination.stat().st_size,
        "event": "Play_sfx_SRU_Baron_Death_cast",
        "event_id": 3_912_207_834,
        "mix": [
            {"media_id": 805_446_954, "gain_db": -2.0, "gain_linear": DEATH_BODY_GAIN},
            {"media_id": 869_424_594, "gain_db": 0.0, "gain_linear": 1.0},
        ],
        **inspect_pcm_wav(destination),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wad", type=Path, default=DEFAULT_WAD)
    parser.add_argument("--wadtools", type=Path, default=DEFAULT_WADTOOLS)
    parser.add_argument("--vgmstream", type=Path, default=DEFAULT_VGMSTREAM)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args()

    wad = args.wad.resolve()
    if sha256_file(wad) != WAD_SHA256:
        raise RuntimeError("Map11 WAD hash changed; re-audit the Baron banks before extraction")
    if not args.wadtools.is_file() or not args.vgmstream.is_file():
        raise FileNotFoundError("wadtools and vgmstream are required")

    with tempfile.TemporaryDirectory(prefix="baron_banks_") as temp_name:
        audio_path, event_path = extract_banks(wad, args.wadtools.resolve(), Path(temp_name))
        if sha256_file(audio_path) != AUDIO_BANK_SHA256:
            raise RuntimeError("Baron audio bank hash mismatch")
        if sha256_file(event_path) != EVENT_BANK_SHA256:
            raise RuntimeError("Baron event bank hash mismatch")
        output = args.out.resolve()
        sounds = decode(audio_path.read_bytes(), args.vgmstream.resolve(), output)
        death_mix = mix_death_event(output)

    report = {
        "schema_version": 1,
        "source": "local League of Legends Map11 WAD",
        "wad": str(wad),
        "wad_sha256": WAD_SHA256,
        "audio_bank": AUDIO_BANK_PATH,
        "audio_bank_path_hash": AUDIO_BANK_HASH,
        "audio_bank_sha256": AUDIO_BANK_SHA256,
        "event_bank": EVENT_BANK_PATH,
        "event_bank_path_hash": EVENT_BANK_HASH,
        "event_bank_sha256": EVENT_BANK_SHA256,
        "sounds": sounds,
        "death_mix": death_mix,
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(args.report.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
