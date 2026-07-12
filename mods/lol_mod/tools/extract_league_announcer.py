#!/usr/bin/env python3
"""Extract pinned League multikill announcer takes from the local EN-US WAD.

Teamfight Manager 2 already dispatches four native multikill sound keys from
its own ``play_kill_count_sound`` path.  This script supplies deterministic
League takes for those 2/3/4/5-kill keys without replacing the game's timing
or adding a second announcement layer.  First Blood is audited in the report,
but deliberately not emitted because the public mod API has no proven global
first-kill sound trigger.
"""

from __future__ import annotations

import argparse
import json
import struct
import tempfile
from dataclasses import dataclass
from pathlib import Path

from extract_league_music import (
    Chunk,
    DEFAULT_RIOT_GAME,
    DEFAULT_VGMSTREAM,
    DEFAULT_WADTOOLS,
    MAP11_WAD,
    MOD_ROOT,
    VGMSTREAM_SHA256,
    WADTOOLS_SHA256,
    Wad,
    decode,
    extract_wad,
    extract_wpk,
    inspect_wav,
    sha256_file,
    verify_file,
    verify_media,
)


DEFAULT_OUTPUT = MOD_ROOT / "sound" / "sfx"
DEFAULT_REPORT = MOD_ROOT / "qa" / "league_announcer_source_qa.json"

ANNOUNCER_WAD = Wad(
    "map11_en_us_announcer",
    "DATA/FINAL/Maps/Shipping/Map11.en_US.wad.client",
    "92bda6eb08cebfa1aedb0c42ab3e227e5cf8aa0bf4aac8e0d245fcb529ac1d84",
    (
        Chunk(
            "audio_bank",
            "assets/sounds/wwise2016/vo/en_us/shared/announcer_global_female1_vo_audio.bnk",
            "5abee840d3887a17",
            "5e565cf5654f1c5886cfa5533799b49aa11005023828179112fd1165b17f38b5",
        ),
        Chunk(
            "audio_package",
            "assets/sounds/wwise2016/vo/en_us/shared/announcer_global_female1_vo_audio.wpk",
            "ccdbafd023095999",
            "774a9a4790e2254816d346973563e6d33245a3836209a8c624227465b19cdefa",
        ),
        Chunk(
            "events_bank",
            "assets/sounds/wwise2016/vo/en_us/shared/announcer_global_female1_vo_events.bnk",
            "71ad34977c070d95",
            "3e299bccb00bf87a3efaecb143d34684cdf0c07c94c57b555a8c920f49d752e6",
        ),
    ),
)

MAP11_BIN_WAD = Wad(
    "map11_event_registry",
    MAP11_WAD.relative_path,
    MAP11_WAD.sha256,
    (
        Chunk(
            "map11_bin",
            "data/maps/shipping/map11/map11.bin",
            "4081e5c462798b73",
            "5c7d6b51183b3eb794a6c56152d09d8a8aec9c2a6db6c5ce895c9a263ec93030",
        ),
    ),
)


@dataclass(frozen=True)
class Announcement:
    name: str
    event_name: str
    event_id: int
    action_id: int
    container_id: int
    pool: tuple[int, ...]
    media_id: int
    wem_sha256: str
    wav_sha256: str
    frame_count: int
    runtime_key: str | None


ANNOUNCEMENTS = (
    Announcement(
        "first_blood",
        "Play_vo_Announcer_Female1_FirstBloodYouYourTeam",
        1_941_092_771,
        946_464_929,
        285_619_036,
        (835_992_869,),
        835_992_869,
        "66955b127e96ec37660b3035c66fb54105e2ad74724fe6563276a7681433e1bd",
        "04866584faff88ddb06123180eb314a5d27e5c5a12ffa6f18dd7be707e347346",
        93_335,
        None,
    ),
    Announcement(
        "double_kill",
        "Play_vo_Announcer_Female1_DoubleKillYouYourTeam",
        3_743_703_056,
        705_523_733,
        233_586_721,
        (38_776_155, 655_441_407, 247_555_986),
        38_776_155,
        "3227ba68011f2fd83661e4d9cf9b789205c1c1717effeadd80f7b39a8a802503",
        "33ded903792be89b2ba9ccb5b265f490f1e828955019b1bbf95a42cf91451bbb",
        66_645,
        "asset/base/sound/sfx/dual_takedown",
    ),
    Announcement(
        "triple_kill",
        "Play_vo_Announcer_Female1_TripleKillYouYourTeam",
        627_773_033,
        315_400_013,
        709_383_474,
        (457_215_657, 411_304_003),
        457_215_657,
        "756e6bd7450beaac84512e9391e3327fc61966a89ed59b165d149ae0f597eef0",
        "654b67b6ee94f218286f60d06948f0f9c0360fc26e28d1998927c603f8558e3e",
        81_394,
        "asset/base/sound/sfx/triple_takedown",
    ),
    Announcement(
        "quadra_kill",
        "Play_vo_Announcer_Female1_QuadraKillYouYourTeam",
        3_159_104_195,
        784_095_126,
        330_617_342,
        (688_775_583, 391_206_161),
        391_206_161,
        "4e858cd401dc1beeab36e428d42c0684aeda58a6296b2c95b707fd852620073c",
        "b139bdb76b5f3a678d053b4bce96c1b32dcafd0e754fd3acb2bb6353226b3365",
        87_771,
        "asset/base/sound/sfx/devastation",
    ),
    Announcement(
        "penta_kill",
        "Play_vo_Announcer_Female1_PentaKillYouYourTeam",
        2_402_155_913,
        63_859_497,
        1_006_520_571,
        (177_689_956, 963_502_603),
        963_502_603,
        "a57f6825015ab183452abd945757b7248aca693a10f24a5909fbc99b60d06e1f",
        "4ac46721472862f4007116a58d7a96fbde11291b9298d70e207d9340d293e383",
        97_616,
        "asset/base/sound/sfx/annihilation",
    ),
)


def wwise_hash(text: str) -> int:
    value = 2_166_136_261
    for byte in text.lower().encode("ascii"):
        value = (value * 16_777_619) & 0xFFFF_FFFF
        value ^= byte
    return value


def verify_registry_and_bank(map11_bin: Path, events_bank: Path) -> None:
    registry = map11_bin.read_bytes()
    bank = events_bank.read_bytes()
    required_registry_strings = (
        b"Announcer_Global_Female1_VO",
        b"Play_vo_Announcer_@voice@_FirstBlood",
        b"Play_vo_Announcer_@voice@_DoubleKill",
        b"Play_vo_Announcer_@voice@_TripleKill",
        b"Play_vo_Announcer_@voice@_QuadraKill",
        b"Play_vo_Announcer_@voice@_PentaKill",
    )
    for token in required_registry_strings:
        if token not in registry:
            raise RuntimeError(f"Map11 registry is missing {token!r}.")

    for item in ANNOUNCEMENTS:
        if wwise_hash(item.event_name) != item.event_id:
            raise RuntimeError(f"FNV-1 mismatch for {item.event_name}.")
        if item.event_name.encode("ascii") not in registry:
            raise RuntimeError(f"Map11 registry omits {item.event_name}.")
        for value, label in (
            (item.event_id, "event"),
            (item.action_id, "action"),
            (item.container_id, "container"),
        ):
            if struct.pack("<I", value) not in bank:
                raise RuntimeError(
                    f"Pinned {label} id {value} for {item.name} is absent from the event bank."
                )


def build_announcer(
    riot_game: Path, wadtools: Path, vgmstream: Path, output_dir: Path
) -> dict[str, object]:
    output_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".league_announcer_", dir=output_dir) as name:
        temp = Path(name)
        chunks = extract_wad(ANNOUNCER_WAD, riot_game, wadtools, temp)
        registry_chunks = extract_wad(MAP11_BIN_WAD, riot_game, wadtools, temp)
        verify_registry_and_bank(
            registry_chunks["map11_bin"], chunks["events_bank"]
        )

        media = extract_wpk(chunks["audio_package"], temp / "wems")
        verify_media(
            media,
            {item.media_id: item.wem_sha256 for item in ANNOUNCEMENTS},
            "Female1 announcer",
        )

        records: list[dict[str, object]] = []
        for item in ANNOUNCEMENTS:
            temporary = temp / f"lol_announcer_{item.name}.wav"
            decode(vgmstream, media[item.media_id], temporary)
            info = inspect_wav(temporary)
            if info["frame_count"] != item.frame_count:
                raise RuntimeError(
                    f"{item.name} frame count mismatch: expected {item.frame_count}, "
                    f"got {info['frame_count']}."
                )
            if info["sha256"] != item.wav_sha256:
                raise RuntimeError(
                    f"{item.name} decoded hash mismatch: expected {item.wav_sha256}, "
                    f"got {info['sha256']}."
                )

            output_path: str | None = None
            if item.runtime_key is not None:
                destination = output_dir / temporary.name
                temporary.replace(destination)
                info = inspect_wav(destination)
                output_path = destination.relative_to(MOD_ROOT).as_posix()

            records.append(
                {
                    "name": item.name,
                    "event_name": item.event_name,
                    "event_id": item.event_id,
                    "action_id": item.action_id,
                    "random_shuffle_container_id": item.container_id,
                    "pool": list(item.pool),
                    "pool_weights": [50_000 for _ in item.pool],
                    "selected_media_id": item.media_id,
                    "selected_wem_sha256": item.wem_sha256,
                    "decoded_wav_sha256": item.wav_sha256,
                    "frame_count": item.frame_count,
                    "duration_seconds": item.frame_count / 44_100,
                    "runtime_key": item.runtime_key,
                    "output": output_path,
                    "status": "runtime_mapped" if item.runtime_key else "audited_no_public_trigger",
                }
            )

    return {
        "schema_version": 1,
        "policy": {
            "source": "local official League of Legends installation only",
            "locale": "en_US",
            "locale_reason": (
                "Map11.zh_CN.wad.client and Map11.zh_MY.wad.client are absent; "
                "the installed Global.zh_MY WAD contains no Female1 announcer chunks"
            ),
            "network_downloads": False,
            "selection": (
                "one deterministic take from each official equal-weight Random/Shuffle pool"
            ),
            "audio_edit": "vgmstream PCM16 decode only; no gain, cut, EQ, or remix",
        },
        "source": {
            "announcer_wad": ANNOUNCER_WAD.relative_path,
            "announcer_wad_sha256": ANNOUNCER_WAD.sha256,
            "announcer_chunks": [chunk.__dict__ for chunk in ANNOUNCER_WAD.chunks],
            "map11_registry_wad": MAP11_BIN_WAD.relative_path,
            "map11_registry_wad_sha256": MAP11_BIN_WAD.sha256,
            "map11_registry_chunk": MAP11_BIN_WAD.chunks[0].__dict__,
        },
        "native_runtime_contract": {
            "implementation": "game_view::ui::ingame_ui::play_kill_count_sound",
            "count_to_key": {
                "2": "asset/base/sound/sfx/dual_takedown",
                "3": "asset/base/sound/sfx/triple_takedown",
                "4": "asset/base/sound/sfx/devastation",
                "5": "asset/base/sound/sfx/annihilation",
            },
            "visual_layer": (
                "reuse native center_kill #text and #kills/#icon1..#icon5 timing"
            ),
            "first_blood_boundary": (
                "The base bundle and public mod API expose no proven global first-kill "
                "sound dispatch key. The official source is audited but no dead asset or "
                "guessed callback is shipped."
            ),
        },
        "announcements": records,
        "tools": {
            "wadtools_sha256": WADTOOLS_SHA256,
            "vgmstream_sha256": VGMSTREAM_SHA256,
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--riot-game", type=Path, default=DEFAULT_RIOT_GAME)
    parser.add_argument("--wadtools", type=Path, default=DEFAULT_WADTOOLS)
    parser.add_argument("--vgmstream", type=Path, default=DEFAULT_VGMSTREAM)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    riot_game = args.riot_game.resolve()
    wadtools = args.wadtools.resolve()
    vgmstream = args.vgmstream.resolve()
    output = args.out.resolve()
    report_path = args.report.resolve()

    verify_file(wadtools, WADTOOLS_SHA256, "wadtools")
    verify_file(vgmstream, VGMSTREAM_SHA256, "vgmstream")
    report = build_announcer(riot_game, wadtools, vgmstream, output)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
