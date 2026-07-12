#!/usr/bin/env python3
"""Extract pinned League draft and Summoner's Rift music from a local install.

The draft source is the real League Client champ-select plug-in, not the
in-game ``mus_client_pregameui_default`` bank.  Its shipped JavaScript is
fingerprinted and used as the authority for the representative pick-layer
mix.  The match source is the base/master layer reached by Map11's official
``phase_01`` Wwise state.  TFM2 only exposes one looping BGM key per surface,
so dynamic client pick progression and Map11 accent layers are deliberately
not flattened into a fabricated full-state cycle.
"""

from __future__ import annotations

import argparse
import array
import hashlib
import json
import math
import os
import struct
import subprocess
import sys
import tempfile
import wave
from dataclasses import dataclass
from pathlib import Path


MOD_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RIOT_GAME = Path(
    os.environ.get("LOL_GAME_ROOT", r"D:\Riot Games\League of Legends\Game")
)
DEFAULT_RIOT_INSTALL = Path(
    os.environ.get("LOL_INSTALL_ROOT", str(DEFAULT_RIOT_GAME.parent))
)
DEFAULT_WADTOOLS = Path(
    os.environ.get(
        "WADTOOLS_EXE",
        str(
            Path(os.environ.get("LOCALAPPDATA", Path.home()))
            / "CodexTools"
            / "wadtools-0.5.6"
            / "wadtools.exe"
        ),
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
DEFAULT_WWISER = Path(
    os.environ.get(
        "WWISER_PYZ",
        str(
            Path(os.environ.get("LOCALAPPDATA", Path.home()))
            / "CodexTools"
            / "wwiser-v20250928"
            / "wwiser.pyz"
        ),
    )
)
DEFAULT_OUTPUT = MOD_ROOT / "sound" / "bgm"
DEFAULT_REPORT = MOD_ROOT / "qa" / "league_music_source_qa.json"

WADTOOLS_SHA256 = "c11b60cc8016c3d986eceb91c3c9fd74e4440416ba2a215af1135f36bd0fa866"
VGMSTREAM_SHA256 = "894cff498bbb7d43fcbae63aac9dc19ebbef8f37c9889c4a9e51de407b5f3c07"
WWISER_SHA256 = "fdcb850ad19d827190a1eb137c2caa02c40671e15c379a6c9a477d2a5237bf53"

RUNTIME_GAIN_DB = 4.0
RUNTIME_GAIN = 10.0 ** (RUNTIME_GAIN_DB / 20.0)


@dataclass(frozen=True)
class Chunk:
    logical_name: str
    internal_path: str
    path_hash: str
    sha256: str


@dataclass(frozen=True)
class Wad:
    logical_name: str
    relative_path: str
    sha256: str
    chunks: tuple[Chunk, ...]


CHAMPSELECT_WAD = Wad(
    "league_client_champ_select",
    "Plugins/rcp-fe-lol-champ-select/assets.wad",
    "be5fef5b37c7293c1eceababcac7a57d8ce4a00894d5ee22f16963a0815066b7",
    (
        Chunk(
            "client_javascript",
            "plugins/rcp-fe-lol-champ-select/global/default/rcp-fe-lol-champ-select.js",
            "3e2f7f1cfed3f682",
            "495d75811e30ba475aae75df3f16ec5e84e2f68cdd47e9d5fe58cb3813bb5a16",
        ),
        Chunk(
            "pick_base",
            "plugins/rcp-fe-lol-champ-select/global/default/sounds/music-cs-draft-pick-base-layer-01.ogg",
            "15d77cee38650431",
            "1ce657ca416cb534e60a4b99a224db8de682e4daa13539f5a68d7cf8d5dbb1e9",
        ),
        Chunk(
            "pick_intensity_01",
            "plugins/rcp-fe-lol-champ-select/global/default/sounds/music-cs-draft-pick-intensity-layer-01.ogg",
            "0acf0acbb18f901f",
            "1a11b56b207bd52710943f92d2f2f3fda41f7dd0882d1b55db67723a629af957",
        ),
        Chunk(
            "pick_intensity_02",
            "plugins/rcp-fe-lol-champ-select/global/default/sounds/music-cs-draft-pick-intensity-layer-02.ogg",
            "0eeebf0e2203459a",
            "ec2455d34173c0b589fe9b75d20281b568f4f86f9c6560d43388305f9fa3029b",
        ),
        Chunk(
            "pick_intensity_03",
            "plugins/rcp-fe-lol-champ-select/global/default/sounds/music-cs-draft-pick-intensity-layer-03.ogg",
            "0709724782099009",
            "cfcc8efae2d86d472c4e847b3c72dddf900eec05621e94f97138b1104011ab31",
        ),
        Chunk(
            "pick_intensity_04",
            "plugins/rcp-fe-lol-champ-select/global/default/sounds/music-cs-draft-pick-intensity-layer-04.ogg",
            "92220d0be54b807a",
            "9b2510d5d0051a63326976df3a63c0cab7c16109ddf0afcc0bf6ecf9f3125beb",
        ),
    ),
)

MAP11_WAD = Wad(
    "summoners_rift_map11",
    "DATA/FINAL/Maps/Shipping/Map11.wad.client",
    "e4bdd4d26294c16fd520a17ec9dcb6eb7425564d60a4890a58313a0cd24d6868",
    (
        Chunk(
            "audio_bank",
            "assets/sounds/wwise2016/sfx/shared/mus_map11_audio.bnk",
            "a69ecbdb71ee8f40",
            "243bfcdc8ff6f9519e9a7c9f4151aac7c56e63c70f99718684a9ab740c2b3f9d",
        ),
        Chunk(
            "audio_package",
            "assets/sounds/wwise2016/sfx/shared/mus_map11_audio.wpk",
            "ee1e7b734bc4b38e",
            "3704a0abb31dd51432b7c3ca2d36fa4106e84494c375929ecc32ad740bae38fc",
        ),
        Chunk(
            "events_bank",
            "assets/sounds/wwise2016/sfx/shared/mus_map11_events.bnk",
            "95670f552c39823e",
            "e47258c722241a227f43125f5632eebbadd7e6c7f386541a3f7a7eb5d92cf364",
        ),
    ),
)

PICK_REPRESENTATIVE_COMPLETED_PICKS = 6
PICK_REPRESENTATIVE_MIX = (
    ("pick_base", 0.37),
    ("pick_intensity_01", 0.37),
    ("pick_intensity_02", 0.37),
    ("pick_intensity_03", 0.2775),
    ("pick_intensity_04", 0.185),
)
CLIENT_DRAFT_RULE = {
    "duplicate_path_resolution": (
        "later completed-action thresholds replace earlier volume entries for "
        "the same synchronized layer"
    ),
    "planning": {"pickintent": 0.37},
    "ban_completed_actions": {
        "0": {"base": 0.37},
        "1": {"base": 0.37, "intensity_01": 0.185},
        "2": {"base": 0.37, "intensity_01": 0.2775, "intensity_02": 0.185},
        "3": {"base": 0.37, "intensity_01": 0.37, "intensity_02": 0.2775},
        "4": {"base": 0.37, "intensity_01": 0.37, "intensity_02": 0.37},
    },
    "pick_completed_actions": {
        "0": {"base": 0.37},
        "1": {"base": 0.37, "intensity_01": 0.185},
        "2": {"base": 0.37, "intensity_01": 0.185, "intensity_02": 0.185},
        "3": {"base": 0.37, "intensity_01": 0.2775, "intensity_02": 0.185},
        "4": {
            "base": 0.37,
            "intensity_01": 0.2775,
            "intensity_02": 0.2775,
            "intensity_03": 0.185,
        },
        "5": {
            "base": 0.37,
            "intensity_01": 0.37,
            "intensity_02": 0.2775,
            "intensity_03": 0.185,
        },
        "6": {
            "base": 0.37,
            "intensity_01": 0.37,
            "intensity_02": 0.37,
            "intensity_03": 0.2775,
            "intensity_04": 0.185,
        },
        "7": {
            "base": 0.37,
            "intensity_01": 0.37,
            "intensity_02": 0.37,
            "intensity_03": 0.37,
            "intensity_04": 0.2775,
        },
        "8": {
            "base": 0.37,
            "intensity_01": 0.37,
            "intensity_02": 0.37,
            "intensity_03": 0.37,
            "intensity_04": 0.37,
        },
    },
    "finalization": {"finalization_60sec": 0.37, "loop": False},
}

MAP11_EVENT_ID = 3_832_820_115
MAP11_STATE_GROUP_ID = 3_133_338_805
MAP11_STATE_VALUE_ID = 2_002_117_580  # Wwise hash of phase_01
MAP11_SECONDARY_STATE_GROUP_ID = 3_007_119_416
MAP11_SECONDARY_STATE_VALUE_ID = 3_024_907_506
MAP11_TXTP_TOKEN = (
    f"event-{MAP11_EVENT_ID} ({MAP11_STATE_GROUP_ID}={MAP11_STATE_VALUE_ID}) "
    f"({MAP11_SECONDARY_STATE_GROUP_ID}={MAP11_SECONDARY_STATE_VALUE_ID})"
)
MAP11_MEDIA = {
    54_102_751: "c99fd163baadd85cb6497d66703eb262378e38e6074466c67ff4e0eacc24c4db",
    133_573_449: "f1400c12d10cc38807533c5b4a6b2de08f1ef935f6966dd5f7b2b376e8705f0d",
    729_866_822: "8c1be087f0f9110beb963e8b9e5f6e0a264c4f2bdfa0960ddabb6c1719a8649c",
    877_430_847: "fb007cef4772c4221f983f1b4c336e22658e25d6ff3a1199e0f91d2aaa5ed694",
}
MAP11_MASTER_MEDIA_ID = 54_102_751
MAP11_MASTER_FRAME_COUNT = 13_230_000

OUTPUT_SPECS = {
    "lol_banpick": {
        "frame_count": 8_077_263,
        "duration_seconds": 8_077_263 / 44_100,
        "sha256": "be1d02b96702f7a375bc21e4dc5c5dc46408ebb4ba9a896469d68ddef5dc4d57",
        "runtime_keys": (
            "asset/base/sound/bgm/banpick",
            "asset/base/sound/bgm/banpick2",
            "asset/base/sound/bgm/banpick_match5_lastgame",
        ),
    },
    "lol_match": {
        "frame_count": MAP11_MASTER_FRAME_COUNT,
        "duration_seconds": MAP11_MASTER_FRAME_COUNT / 44_100,
        "sha256": "b72626393c9dee33cfc78c82a0aed1015dd669c7b582621ea1d9c3fd560148e2",
        "runtime_keys": (
            "asset/base/sound/bgm/match",
            "asset/base/sound/bgm/match2",
            "asset/base/sound/bgm/match3",
            "asset/base/sound/bgm/match4",
            "asset/base/sound/bgm/match5",
            "asset/base/sound/bgm/match6",
        ),
    },
}


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def verify_file(path: Path, expected: str, label: str) -> None:
    if not path.is_file():
        raise FileNotFoundError(f"{label} is missing: {path}")
    actual = sha256_file(path)
    if actual != expected:
        raise RuntimeError(
            f"{label} hash mismatch: expected {expected}, got {actual}. "
            "Re-audit the current local League build before changing pins."
        )


def run(command: list[str], label: str) -> None:
    result = subprocess.run(command, check=False, capture_output=True, text=True)
    if result.returncode:
        details = (result.stderr or result.stdout).strip()
        raise RuntimeError(f"{label} failed ({result.returncode}): {details}")


def extract_wad(
    wad: Wad, riot_game: Path, wadtools: Path, temp_root: Path
) -> dict[str, Path]:
    wad_path = riot_game / wad.relative_path
    verify_file(wad_path, wad.sha256, f"{wad.logical_name} WAD")
    output = temp_root / wad.logical_name
    output.mkdir(parents=True, exist_ok=True)
    run(
        [
            str(wadtools),
            "--progress=false",
            "extract",
            "-i",
            str(wad_path),
            "-o",
            str(output),
            "--hash",
            *[chunk.path_hash for chunk in wad.chunks],
            "--overwrite",
            "--stats=false",
        ],
        f"wadtools extraction for {wad.logical_name}",
    )

    extracted = [path for path in output.rglob("*") if path.is_file()]
    by_hash = {sha256_file(path): path for path in extracted}
    result: dict[str, Path] = {}
    for chunk in wad.chunks:
        path = by_hash.get(chunk.sha256)
        if path is None:
            raise RuntimeError(
                f"Pinned chunk {chunk.logical_name} ({chunk.path_hash}) was not "
                f"extracted from {wad.logical_name}."
            )
        result[chunk.logical_name] = path
    return result


def extract_wpk(package_path: Path, output_dir: Path) -> dict[int, Path]:
    data = package_path.read_bytes()
    if data[:4] != b"r3d2":
        raise RuntimeError(f"Unsupported WPK header in {package_path.name}.")
    if len(data) < 12:
        raise RuntimeError(f"Truncated WPK header in {package_path.name}.")
    count = struct.unpack_from("<I", data, 8)[0]
    table_end = 12 + count * 4
    if table_end > len(data):
        raise RuntimeError(f"Truncated WPK record table in {package_path.name}.")
    record_offsets = struct.unpack_from(f"<{count}I", data, 12)
    output_dir.mkdir(parents=True, exist_ok=True)
    media: dict[int, Path] = {}
    for record_offset in record_offsets:
        if record_offset + 12 > len(data):
            raise RuntimeError(f"WPK record offset {record_offset} is out of range.")
        payload_offset, payload_size, name_length = struct.unpack_from(
            "<III", data, record_offset
        )
        name_end = record_offset + 12 + name_length * 2
        if name_end > len(data) or payload_offset + payload_size > len(data):
            raise RuntimeError(f"Truncated WPK record at {record_offset}.")
        name = data[record_offset + 12 : name_end].decode("utf-16le").rstrip("\0")
        try:
            media_id = int(Path(name).stem)
        except ValueError as error:
            raise RuntimeError(f"Unexpected non-numeric WPK media name: {name}") from error
        if media_id in media:
            raise RuntimeError(f"Duplicate WPK media id {media_id}.")
        payload = data[payload_offset : payload_offset + payload_size]
        if not (payload.startswith(b"RIFF") and payload[8:12] == b"WAVE"):
            raise RuntimeError(f"WPK media {media_id} is not a RIFF/WAVE WEM.")
        destination = output_dir / f"{media_id}.wem"
        destination.write_bytes(payload)
        media[media_id] = destination
    return media


def verify_media(media: dict[int, Path], expected: dict[int, str], label: str) -> None:
    for media_id, expected_hash in expected.items():
        path = media.get(media_id)
        if path is None:
            raise RuntimeError(f"{label} media {media_id} is missing.")
        actual = sha256_file(path)
        if actual != expected_hash:
            raise RuntimeError(
                f"{label} media {media_id} hash mismatch: expected "
                f"{expected_hash}, got {actual}."
            )


def decode(vgmstream: Path, source: Path, destination: Path) -> None:
    run(
        [
            str(vgmstream),
            "-i",
            "-W",
            "1",
            "-o",
            str(destination),
            str(source),
        ],
        f"vgmstream decode for {source.name}",
    )
    if not destination.is_file():
        raise RuntimeError(f"vgmstream did not create {destination}.")


def apply_runtime_gain(
    source: Path,
    destination: Path,
    *,
    start_frame: int = 0,
    end_frame: int | None = None,
) -> None:
    with wave.open(str(source), "rb") as reader:
        params = (
            reader.getnchannels(),
            reader.getsampwidth(),
            reader.getframerate(),
            reader.getcomptype(),
        )
        if params != (2, 2, 44_100, "NONE"):
            raise RuntimeError(f"Unexpected music WAV format for {source.name}: {params}")
        if end_frame is None:
            end_frame = reader.getnframes()
        if not (0 <= start_frame < end_frame <= reader.getnframes()):
            raise RuntimeError(
                f"Invalid frame window {start_frame}:{end_frame} for {source.name}."
            )
        reader.setpos(start_frame)
        remaining = end_frame - start_frame
        with wave.open(str(destination), "wb") as writer:
            writer.setnchannels(2)
            writer.setsampwidth(2)
            writer.setframerate(44_100)
            while remaining:
                frames = reader.readframes(min(44_100, remaining))
                if not frames:
                    raise RuntimeError(f"Truncated PCM stream in {source.name}.")
                frame_count = len(frames) // 4
                remaining -= frame_count
                samples = array.array("h")
                samples.frombytes(frames)
                if sys.byteorder != "little":
                    samples.byteswap()
                for index, sample in enumerate(samples):
                    gained = round(sample * RUNTIME_GAIN)
                    samples[index] = max(-32_768, min(32_767, gained))
                if sys.byteorder != "little":
                    samples.byteswap()
                writer.writeframesraw(samples.tobytes())


def mix_pcm16(
    sources: tuple[tuple[Path, float], ...],
    destination: Path,
) -> None:
    """Mix synchronized League Client layers using their shipped JS weights."""

    readers = [wave.open(str(path), "rb") for path, _weight in sources]
    try:
        expected = (2, 2, 44_100, "NONE")
        frame_count: int | None = None
        for (path, _weight), reader in zip(sources, readers):
            params = (
                reader.getnchannels(),
                reader.getsampwidth(),
                reader.getframerate(),
                reader.getcomptype(),
            )
            if params != expected:
                raise RuntimeError(f"Unexpected layer WAV format for {path.name}: {params}")
            if frame_count is None:
                frame_count = reader.getnframes()
            elif reader.getnframes() != frame_count:
                raise RuntimeError("Champ-select music layers are not sample-aligned.")
        if frame_count is None:
            raise RuntimeError("No champ-select music layers were provided.")

        remaining = frame_count
        with wave.open(str(destination), "wb") as writer:
            writer.setnchannels(2)
            writer.setsampwidth(2)
            writer.setframerate(44_100)
            while remaining:
                block_frames = min(44_100, remaining)
                decoded: list[array.array[int]] = []
                for reader in readers:
                    payload = reader.readframes(block_frames)
                    samples = array.array("h")
                    samples.frombytes(payload)
                    if sys.byteorder != "little":
                        samples.byteswap()
                    if len(samples) != block_frames * 2:
                        raise RuntimeError("Truncated champ-select PCM layer.")
                    decoded.append(samples)

                mixed = array.array("h")
                weights = [weight for _path, weight in sources]
                for values in zip(*decoded):
                    sample = round(
                        sum(value * weight for value, weight in zip(values, weights))
                        * RUNTIME_GAIN
                    )
                    if not -32_768 <= sample <= 32_767:
                        raise RuntimeError(
                            "Audited champ-select mix clipped; re-audit source weights."
                        )
                    mixed.append(sample)
                if sys.byteorder != "little":
                    mixed.byteswap()
                writer.writeframesraw(mixed.tobytes())
                remaining -= block_frames
    finally:
        for reader in readers:
            reader.close()


def verify_champselect_javascript(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    required = (
        'music-cs-draft-ban-base-layer-01.ogg",volume:.37,delay:1578,isMasterTrack:!0',
        'music-cs-draft-pick-base-layer-01.ogg",volume:.37,isMasterTrack:!0',
        's>=5&&c.push({path:"/fe/lol-champ-select/sounds/music-cs-draft-pick-intensity-layer-01.ogg",volume:.37})',
        'music-cs-draft-pick-intensity-layer-02.ogg",volume:.37}),c.push({path:"/fe/lol-champ-select/sounds/music-cs-draft-pick-intensity-layer-03.ogg",volume:.27749999999999997}),c.push({path:"/fe/lol-champ-select/sounds/music-cs-draft-pick-intensity-layer-04.ogg",volume:.185}))',
        'music-cs-draft-finalization-60sec-01.ogg',
        'c.push({path:t,volume:.37,loop:!1,offset:e,isMasterTrack:!0})',
    )
    missing = [token for token in required if token not in text]
    if missing:
        raise RuntimeError(
            "Pinned League Client draft-music rules changed; re-audit assets.wad."
        )


def inspect_wav(path: Path) -> dict[str, int | float | str]:
    with wave.open(str(path), "rb") as audio:
        channels = audio.getnchannels()
        sample_width = audio.getsampwidth()
        sample_rate = audio.getframerate()
        frames = audio.getnframes()
        compression = audio.getcomptype()
    if (channels, sample_width, sample_rate, compression) != (2, 2, 44_100, "NONE"):
        raise RuntimeError(f"Unexpected output WAV format for {path.name}.")
    with wave.open(str(path), "rb") as audio:
        first = array.array("h")
        first.frombytes(audio.readframes(1))
        audio.setpos(frames - 1)
        last = array.array("h")
        last.frombytes(audio.readframes(1))
    if sys.byteorder != "little":
        first.byteswap()
        last.byteswap()
    boundary_delta = max(abs(a - b) for a, b in zip(first, last))
    boundary_dbfs = 20.0 * math.log10(max(1, boundary_delta) / 32_768)
    return {
        "channels": channels,
        "sample_width_bytes": sample_width,
        "sample_rate_hz": sample_rate,
        "frame_count": frames,
        "duration_seconds": frames / sample_rate,
        "compression": compression,
        "size_bytes": path.stat().st_size,
        "sha256": sha256_file(path),
        "loop_boundary_max_delta": boundary_delta,
        "loop_boundary_max_delta_dbfs": boundary_dbfs,
    }


def generate_map11_txtp(
    wwiser: Path,
    audio_bank: Path,
    events_bank: Path,
    wem_dir: Path,
    output_dir: Path,
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    run(
        [
            sys.executable,
            str(wwiser),
            str(audio_bank),
            str(events_bank),
            "-g",
            "-gu",
            "-go",
            str(output_dir),
            "-gw",
            str(wem_dir),
            "-gnw",
            "-gxni",
            "-gd",
        ],
        "wwiser Map11 event resolution",
    )
    matches = [
        path
        for path in output_dir.rglob("*.txtp")
        if MAP11_TXTP_TOKEN in path.name
    ]
    if len(matches) != 1:
        raise RuntimeError(
            f"Expected one Map11 TXTP containing {MAP11_TXTP_TOKEN!r}, "
            f"found {len(matches)}."
        )
    txtp = matches[0]
    text = txtp.read_text(encoding="utf-8")
    for media_id in MAP11_MEDIA:
        if f"/{media_id}.wem" not in text.replace("\\", "/"):
            raise RuntimeError(f"Resolved Map11 TXTP omits pinned media {media_id}.")
    return txtp


def build_music(
    riot_install: Path,
    riot_game: Path,
    wadtools: Path,
    vgmstream: Path,
    wwiser: Path,
    output_dir: Path,
) -> dict[str, object]:
    output_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".league_music_", dir=output_dir) as name:
        temp = Path(name)
        champselect_chunks = extract_wad(
            CHAMPSELECT_WAD, riot_install, wadtools, temp
        )
        verify_champselect_javascript(champselect_chunks["client_javascript"])
        map_chunks = extract_wad(MAP11_WAD, riot_game, wadtools, temp)

        map_media = extract_wpk(map_chunks["audio_package"], temp / "map11_wems")
        verify_media(map_media, MAP11_MEDIA, "Map11")

        decoded_pick_layers: dict[str, Path] = {}
        for logical_name, _weight in PICK_REPRESENTATIVE_MIX:
            decoded = temp / f"{logical_name}.wav"
            decode(vgmstream, champselect_chunks[logical_name], decoded)
            decoded_pick_layers[logical_name] = decoded

        map_txtp = generate_map11_txtp(
            wwiser,
            map_chunks["audio_bank"],
            map_chunks["events_bank"],
            temp / "map11_wems",
            temp / "map11_txtp",
        )
        if f"/{MAP11_MASTER_MEDIA_ID}.wem" not in map_txtp.read_text(
            encoding="utf-8"
        ).replace("\\", "/"):
            raise RuntimeError("Resolved phase_01 event omits the base gameplay layer.")
        raw_match = temp / "lol_match_raw.wav"
        decode(vgmstream, map_media[MAP11_MASTER_MEDIA_ID], raw_match)

        outputs: dict[str, object] = {}
        staged_banpick = temp / "lol_banpick.wav"
        mix_pcm16(
            tuple(
                (decoded_pick_layers[logical_name], weight)
                for logical_name, weight in PICK_REPRESENTATIVE_MIX
            ),
            staged_banpick,
        )
        staged_match = temp / "lol_match.wav"
        apply_runtime_gain(raw_match, staged_match)

        for stem, staged in (
            ("lol_banpick", staged_banpick),
            ("lol_match", staged_match),
        ):
            destination = output_dir / f"{stem}.wav"
            info = inspect_wav(staged)
            expected = OUTPUT_SPECS[stem]
            if info["frame_count"] != expected["frame_count"]:
                raise RuntimeError(
                    f"{stem} frame count mismatch: expected "
                    f"{expected['frame_count']}, got {info['frame_count']}."
                )
            if expected["sha256"] and info["sha256"] != expected["sha256"]:
                raise RuntimeError(
                    f"{stem} deterministic hash mismatch: expected "
                    f"{expected['sha256']}, got {info['sha256']}."
                )
            staged.replace(destination)
            info = inspect_wav(destination)
            outputs[stem] = {
                "path": destination.relative_to(MOD_ROOT).as_posix(),
                "runtime_gain_db": RUNTIME_GAIN_DB,
                "runtime_keys": list(expected["runtime_keys"]),
                **info,
            }

    return {
        "schema_version": 2,
        "policy": {
            "source": "local official League of Legends installation only",
            "network_downloads": False,
            "image_generation": False,
            "edit": (
                "League Client draft layers are sample-aligned with their exact "
                f"shipped weights, then both outputs receive a fixed {RUNTIME_GAIN_DB:.1f} "
                "dB TFM2 playback gain; no EQ, compression, arbitrary timeline, "
                "or unrelated source remix"
            ),
        },
        "tools": {
            "wadtools": {"sha256": WADTOOLS_SHA256, "version": "0.5.6"},
            "vgmstream": {"sha256": VGMSTREAM_SHA256, "version": "r2117-116-g4021c853"},
            "wwiser": {"sha256": WWISER_SHA256, "version": "v20250928"},
        },
        "champselect": {
            "wad": CHAMPSELECT_WAD.relative_path,
            "wad_sha256": CHAMPSELECT_WAD.sha256,
            "chunks": [chunk.__dict__ for chunk in CHAMPSELECT_WAD.chunks],
            "client_rule": CLIENT_DRAFT_RULE,
            "representative_completed_picks": PICK_REPRESENTATIVE_COMPLETED_PICKS,
            "representative_mix": [
                {"logical_name": logical_name, "volume": volume}
                for logical_name, volume in PICK_REPRESENTATIVE_MIX
            ],
            "selection": (
                "the exact completed-pick-count 6 stack from the shipped client "
                "rule; TFM2 exposes one BP loop and cannot switch layers per pick"
            ),
        },
        "match": {
            "wad": MAP11_WAD.relative_path,
            "wad_sha256": MAP11_WAD.sha256,
            "chunks": [chunk.__dict__ for chunk in MAP11_WAD.chunks],
            "event_id": MAP11_EVENT_ID,
            "state_group_id": MAP11_STATE_GROUP_ID,
            "state_value_id": MAP11_STATE_VALUE_ID,
            "state_value_name": "phase_01",
            "secondary_state_group_id": MAP11_SECONDARY_STATE_GROUP_ID,
            "secondary_state_value_id": MAP11_SECONDARY_STATE_VALUE_ID,
            "media": {str(key): value for key, value in MAP11_MEDIA.items()},
            "selected_master_media_id": MAP11_MASTER_MEDIA_ID,
            "selected_master_frames": MAP11_MASTER_FRAME_COUNT,
            "selection": (
                "official phase_01 base/master gameplay layer; the 105-second "
                "side intro and minute accent layers remain event-driven in LoL "
                "and are omitted from TFM2's single static match loop"
            ),
        },
        "outputs": outputs,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--riot-install", type=Path, default=DEFAULT_RIOT_INSTALL)
    parser.add_argument("--riot-game", type=Path, default=DEFAULT_RIOT_GAME)
    parser.add_argument("--wadtools", type=Path, default=DEFAULT_WADTOOLS)
    parser.add_argument("--vgmstream", type=Path, default=DEFAULT_VGMSTREAM)
    parser.add_argument("--wwiser", type=Path, default=DEFAULT_WWISER)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    riot_install = args.riot_install.resolve()
    riot_game = args.riot_game.resolve()
    wadtools = args.wadtools.resolve()
    vgmstream = args.vgmstream.resolve()
    wwiser = args.wwiser.resolve()
    output = args.out.resolve()
    report_path = args.report.resolve()

    verify_file(wadtools, WADTOOLS_SHA256, "wadtools")
    verify_file(vgmstream, VGMSTREAM_SHA256, "vgmstream")
    verify_file(wwiser, WWISER_SHA256, "wwiser")
    report = build_music(
        riot_install, riot_game, wadtools, vgmstream, wwiser, output
    )
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
