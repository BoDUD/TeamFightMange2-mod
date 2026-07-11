#!/usr/bin/env python3
"""Extract the pinned League BP and Summoner's Rift music from a local install.

The script intentionally accepts only the audited Riot WAD build below.  It
extracts chunks by their WAD path hashes, verifies every bank/package/WEM
fingerprint, resolves the Map11 music event through wwiser, decodes through
vgmstream, and writes deterministic PCM16 WAV assets for the mod.
"""

from __future__ import annotations

import argparse
import array
import hashlib
import json
import math
import os
import shutil
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


PREGAME_WAD = Wad(
    "pregame_ui_default",
    "DATA/FINAL/UI.wad.client",
    "613ddbacA45c4dc2c578f46e9e929754acfa49393fa20c7e55be2b9ba1f1d156".lower(),
    (
        Chunk(
            "audio_bank",
            "assets/sounds/wwise2016/sfx/shared/mus_client_pregameui_default_audio.bnk",
            "7da9bd7a2f87a1e7",
            "d6c4453c1b48690686b32f503a7cc430acc4ba6c2f4b80b55bf01832db4dac53",
        ),
        Chunk(
            "audio_package",
            "assets/sounds/wwise2016/sfx/shared/mus_client_pregameui_default_audio.wpk",
            "f4e176db72e53676",
            "f068f68df6d579bb1b242d4ce84c45144dc8f1d4b794c979fce6bd5ed254e5a8",
        ),
        Chunk(
            "events_bank",
            "assets/sounds/wwise2016/sfx/shared/mus_client_pregameui_default_events.bnk",
            "63fed30d9a9310a6",
            "ae9af6b8934ba93d17892c21041b1321d478bdb98c97d871b263f8eb15dcff3e",
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

PREGAME_EVENT_ID = 3_696_965_764
PREGAME_MEDIA_ID = 888_629_231
PREGAME_WEM_SHA256 = "426dcf4fda8e8f1d8bd7cbf76e6f94f566b11daa30572330e358a0a89a5b98e9"
PREGAME_TXTP_TOKEN = f"event-{PREGAME_EVENT_ID} {{m}}.txtp"

MAP11_EVENT_ID = 3_832_820_115
MAP11_STATE_GROUP_ID = 3_133_338_805
MAP11_STATE_VALUE_ID = 1_129_718_747
MAP11_TXTP_TOKEN = (
    f"event-{MAP11_EVENT_ID} ({MAP11_STATE_GROUP_ID}={MAP11_STATE_VALUE_ID})"
)
MAP11_MEDIA = {
    15_424_654: "163a69376a87e91bf9c89078be1db556ca8822d2774f41ff8df7bd2ceaec3b7a",
    141_256_618: "459ad3f086831f98b249a3f17dbafa483d85649de2c823da494e49fd80f91696",
    177_267_501: "f6742b04729e26932a11dabb61edfbDC1e8e9eb599239319692a594d32733dfb".lower(),
    204_917_839: "f42a1578244bc720b455049ba7f405d846f5c9c641f62b2c209093eb26b038b7",
    834_478_730: "2aeac5b31416eabc1189562340ec9bfd36e6d570cbf140fb6591b9e54c5d54a0",
}
MAP11_LOOP_START_FRAME = 817_151
MAP11_LOOP_END_FRAME = 13_268_915

OUTPUT_SPECS = {
    "lol_banpick": {
        "frame_count": 5_700_928,
        "duration_seconds": 129.27274376417233,
        "sha256": "5e021cd71bb998f32d2ae39580d84f387a296d250f10b3d1b7963799b79cba0f",
        "runtime_keys": (
            "asset/base/sound/bgm/banpick",
            "asset/base/sound/bgm/banpick2",
            "asset/base/sound/bgm/banpick_match5_lastgame",
        ),
    },
    "lol_match": {
        "frame_count": MAP11_LOOP_END_FRAME - MAP11_LOOP_START_FRAME,
        "duration_seconds": (MAP11_LOOP_END_FRAME - MAP11_LOOP_START_FRAME) / 44_100,
        "sha256": "4de34d2a92da90086b2d563c6b38f14c0cc6d2f112e3c4a1da3a318ab1b6db85",
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


def generate_pregame_txtp(
    wwiser: Path,
    audio_bank: Path,
    events_bank: Path,
    wem_dir: Path,
    output_dir: Path,
) -> Path:
    # This event references one tiny internal-bank layer as well as the WPK
    # music source, so wwiser's generated TXTP expects the bank beside WEMs.
    shutil.copy2(audio_bank, wem_dir / audio_bank.name)
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
        ],
        "wwiser PregameUI event resolution",
    )
    matches = [
        path for path in output_dir.rglob("*.txtp") if path.name.endswith(PREGAME_TXTP_TOKEN)
    ]
    if len(matches) != 1:
        raise RuntimeError(
            f"Expected one default PregameUI TXTP ending in "
            f"{PREGAME_TXTP_TOKEN!r}, found {len(matches)}."
        )
    text = matches[0].read_text(encoding="utf-8").replace("\\", "/")
    if f"/{PREGAME_MEDIA_ID}.wem" not in text or audio_bank.name not in text:
        raise RuntimeError("Resolved PregameUI TXTP omits a pinned source layer.")
    return matches[0]


def build_music(
    riot_game: Path,
    wadtools: Path,
    vgmstream: Path,
    wwiser: Path,
    output_dir: Path,
) -> dict[str, object]:
    output_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".league_music_", dir=output_dir) as name:
        temp = Path(name)
        pregame_chunks = extract_wad(PREGAME_WAD, riot_game, wadtools, temp)
        map_chunks = extract_wad(MAP11_WAD, riot_game, wadtools, temp)

        pregame_media = extract_wpk(
            pregame_chunks["audio_package"], temp / "pregame_wems"
        )
        verify_media(
            pregame_media,
            {PREGAME_MEDIA_ID: PREGAME_WEM_SHA256},
            "PregameUI",
        )
        map_media = extract_wpk(map_chunks["audio_package"], temp / "map11_wems")
        verify_media(map_media, MAP11_MEDIA, "Map11")

        pregame_txtp = generate_pregame_txtp(
            wwiser,
            pregame_chunks["audio_bank"],
            pregame_chunks["events_bank"],
            temp / "pregame_wems",
            temp / "pregame_txtp",
        )
        raw_banpick = temp / "lol_banpick_raw.wav"
        decode(vgmstream, pregame_txtp, raw_banpick)

        map_txtp = generate_map11_txtp(
            wwiser,
            map_chunks["audio_bank"],
            map_chunks["events_bank"],
            temp / "map11_wems",
            temp / "map11_txtp",
        )
        raw_match = temp / "lol_match_raw.wav"
        decode(vgmstream, map_txtp, raw_match)

        outputs: dict[str, object] = {}
        for stem, raw, frame_window in (
            ("lol_banpick", raw_banpick, (0, None)),
            (
                "lol_match",
                raw_match,
                (MAP11_LOOP_START_FRAME, MAP11_LOOP_END_FRAME),
            ),
        ):
            destination = output_dir / f"{stem}.wav"
            staged = temp / f"{stem}.wav"
            apply_runtime_gain(
                raw,
                staged,
                start_frame=frame_window[0],
                end_frame=frame_window[1],
            )
            info = inspect_wav(staged)
            expected = OUTPUT_SPECS[stem]
            if info["frame_count"] != expected["frame_count"]:
                raise RuntimeError(
                    f"{stem} frame count mismatch: expected "
                    f"{expected['frame_count']}, got {info['frame_count']}."
                )
            if info["sha256"] != expected["sha256"]:
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
        "schema_version": 1,
        "policy": {
            "source": "local official League of Legends installation only",
            "network_downloads": False,
            "image_generation": False,
            "edit": (
                f"PCM decode plus a fixed {RUNTIME_GAIN_DB:.1f} dB runtime gain; "
                "Map11 is bounded by its official Wwise loop markers; no EQ, "
                "compression, arbitrary cut, or remix"
            ),
        },
        "tools": {
            "wadtools": {"sha256": WADTOOLS_SHA256, "version": "0.5.6"},
            "vgmstream": {"sha256": VGMSTREAM_SHA256, "version": "r2117-116-g4021c853"},
            "wwiser": {"sha256": WWISER_SHA256, "version": "v20250928"},
        },
        "pregame": {
            "wad": PREGAME_WAD.relative_path,
            "wad_sha256": PREGAME_WAD.sha256,
            "chunks": [chunk.__dict__ for chunk in PREGAME_WAD.chunks],
            "event_id": PREGAME_EVENT_ID,
            "media_id": PREGAME_MEDIA_ID,
            "wem_sha256": PREGAME_WEM_SHA256,
            "selection": "resolved default PregameUI event cycle used when no mode state is supplied",
        },
        "match": {
            "wad": MAP11_WAD.relative_path,
            "wad_sha256": MAP11_WAD.sha256,
            "chunks": [chunk.__dict__ for chunk in MAP11_WAD.chunks],
            "event_id": MAP11_EVENT_ID,
            "state_group_id": MAP11_STATE_GROUP_ID,
            "state_value_id": MAP11_STATE_VALUE_ID,
            "media": {str(key): value for key, value in MAP11_MEDIA.items()},
            "resolved_cycle_frames": 13_268_915,
            "official_loop_start_frame": MAP11_LOOP_START_FRAME,
            "official_loop_end_frame": MAP11_LOOP_END_FRAME,
            "selection": "official loop body from one resolved Summoner's Rift Map11 music cycle",
        },
        "outputs": outputs,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--riot-game", type=Path, default=DEFAULT_RIOT_GAME)
    parser.add_argument("--wadtools", type=Path, default=DEFAULT_WADTOOLS)
    parser.add_argument("--vgmstream", type=Path, default=DEFAULT_VGMSTREAM)
    parser.add_argument("--wwiser", type=Path, default=DEFAULT_WWISER)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    riot_game = args.riot_game.resolve()
    wadtools = args.wadtools.resolve()
    vgmstream = args.vgmstream.resolve()
    wwiser = args.wwiser.resolve()
    output = args.out.resolve()
    report_path = args.report.resolve()

    verify_file(wadtools, WADTOOLS_SHA256, "wadtools")
    verify_file(vgmstream, VGMSTREAM_SHA256, "vgmstream")
    verify_file(wwiser, WWISER_SHA256, "wwiser")
    report = build_music(riot_game, wadtools, vgmstream, wwiser, output)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
