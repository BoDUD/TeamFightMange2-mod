from __future__ import annotations

import array
import hashlib
import json
import math
import sys
import wave
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MOD = ROOT / "mods" / "lol_mod"

MUSIC_KEYS = {
    "asset/base/sound/bgm/banpick": "asset/lol_mod/sound/bgm/lol_banpick",
    "asset/base/sound/bgm/banpick2": "asset/lol_mod/sound/bgm/lol_banpick",
    "asset/base/sound/bgm/banpick_match5_lastgame": "asset/lol_mod/sound/bgm/lol_banpick",
    "asset/base/sound/bgm/match": "asset/lol_mod/sound/bgm/lol_match",
    "asset/base/sound/bgm/match2": "asset/lol_mod/sound/bgm/lol_match",
    "asset/base/sound/bgm/match3": "asset/lol_mod/sound/bgm/lol_match",
    "asset/base/sound/bgm/match4": "asset/lol_mod/sound/bgm/lol_match",
    "asset/base/sound/bgm/match5": "asset/lol_mod/sound/bgm/lol_match",
    "asset/base/sound/bgm/match6": "asset/lol_mod/sound/bgm/lol_match",
}

ANNOUNCER_KEYS = {
    "asset/base/sound/sfx/dual_takedown": "asset/lol_mod/sound/sfx/lol_announcer_double_kill",
    "asset/base/sound/sfx/triple_takedown": "asset/lol_mod/sound/sfx/lol_announcer_triple_kill",
    "asset/base/sound/sfx/devastation": "asset/lol_mod/sound/sfx/lol_announcer_quadra_kill",
    "asset/base/sound/sfx/annihilation": "asset/lol_mod/sound/sfx/lol_announcer_penta_kill",
}


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def inspect_wav(path: Path) -> dict[str, int | float | str]:
    with wave.open(str(path), "rb") as audio:
        return {
            "channels": audio.getnchannels(),
            "sample_width_bytes": audio.getsampwidth(),
            "sample_rate_hz": audio.getframerate(),
            "frame_count": audio.getnframes(),
            "duration_seconds": audio.getnframes() / audio.getframerate(),
            "compression": audio.getcomptype(),
        }


def peak_and_clipped(path: Path) -> tuple[int, int]:
    peak = 0
    clipped = 0
    with wave.open(str(path), "rb") as audio:
        while True:
            payload = audio.readframes(44_100)
            if not payload:
                break
            samples = array.array("h")
            samples.frombytes(payload)
            if sys.byteorder != "little":
                samples.byteswap()
            peak = max(peak, max(map(abs, samples), default=0))
            clipped += sum(abs(sample) >= 32_767 for sample in samples)
    return peak, clipped


def test_all_native_bp_and_match_music_keys_use_two_audited_league_tracks() -> None:
    overrides = load_json(MOD / "mod.override_info")
    for key, remapping in MUSIC_KEYS.items():
        assert overrides[key] == {"remapping": remapping, "type": "override"}

    unrelated = {
        "asset/base/sound/bgm/management",
        "asset/base/sound/bgm/management2",
        "asset/base/sound/bgm/management3",
        "asset/base/sound/bgm/match_result",
        "asset/base/sound/bgm/match_result_win",
        "asset/base/sound/bgm/match_result_lose",
        "asset/base/sound/bgm/title",
        "asset/base/sound/bgm/new_game",
        "asset/base/sound/bgm/tutorial",
    }
    assert unrelated.isdisjoint(overrides)

    report = load_json(MOD / "qa" / "league_music_source_qa.json")
    assert report["policy"]["source"] == "local official League of Legends installation only"
    assert report["policy"]["network_downloads"] is False
    assert report["pregame"]["event_id"] == 3_696_965_764
    assert report["match"]["event_id"] == 3_832_820_115
    assert report["match"]["state_group_id"] == 3_133_338_805
    assert report["match"]["state_value_id"] == 1_129_718_747

    expected_keys = set(MUSIC_KEYS)
    reported_keys = {
        key
        for output in report["outputs"].values()
        for key in output["runtime_keys"]
    }
    assert reported_keys == expected_keys


def test_league_music_outputs_are_pinned_pcm16_without_clipping() -> None:
    report = load_json(MOD / "qa" / "league_music_source_qa.json")
    for output in report["outputs"].values():
        path = MOD / output["path"]
        assert path.is_file()
        assert sha256(path) == output["sha256"]
        actual = inspect_wav(path)
        assert actual["channels"] == 2
        assert actual["sample_width_bytes"] == 2
        assert actual["sample_rate_hz"] == 44_100
        assert actual["compression"] == "NONE"
        assert actual["frame_count"] == output["frame_count"]
        assert math.isclose(
            actual["duration_seconds"], output["duration_seconds"], abs_tol=1e-9
        )
        peak, clipped = peak_and_clipped(path)
        assert 0 < peak < 32_767
        assert clipped == 0
        assert output["loop_boundary_max_delta_dbfs"] <= -30.0


def test_native_multikill_dispatch_maps_to_verified_female1_takes() -> None:
    overrides = load_json(MOD / "mod.override_info")
    for key, remapping in ANNOUNCER_KEYS.items():
        assert overrides[key] == {"remapping": remapping, "type": "override"}

    report = load_json(MOD / "qa" / "league_announcer_source_qa.json")
    assert report["policy"]["locale"] == "en_US"
    assert report["policy"]["network_downloads"] is False
    assert report["native_runtime_contract"]["count_to_key"] == {
        "2": "asset/base/sound/sfx/dual_takedown",
        "3": "asset/base/sound/sfx/triple_takedown",
        "4": "asset/base/sound/sfx/devastation",
        "5": "asset/base/sound/sfx/annihilation",
    }

    runtime = [
        item for item in report["announcements"] if item["status"] == "runtime_mapped"
    ]
    assert [item["name"] for item in runtime] == [
        "double_kill",
        "triple_kill",
        "quadra_kill",
        "penta_kill",
    ]
    for item in runtime:
        assert item["runtime_key"] in ANNOUNCER_KEYS
        assert item["pool_weights"] == [50_000] * len(item["pool"])
        assert item["selected_media_id"] in item["pool"]
        path = MOD / item["output"]
        assert path.is_file()
        assert sha256(path) == item["decoded_wav_sha256"]
        actual = inspect_wav(path)
        assert actual == {
            "channels": 2,
            "sample_width_bytes": 2,
            "sample_rate_hz": 44_100,
            "frame_count": item["frame_count"],
            "duration_seconds": item["duration_seconds"],
            "compression": "NONE",
        }


def test_first_blood_is_audited_but_not_faked_without_a_public_trigger() -> None:
    report = load_json(MOD / "qa" / "league_announcer_source_qa.json")
    first = next(
        item for item in report["announcements"] if item["name"] == "first_blood"
    )
    assert first["event_name"] == "Play_vo_Announcer_Female1_FirstBloodYouYourTeam"
    assert first["event_id"] == 1_941_092_771
    assert first["selected_media_id"] == 835_992_869
    assert first["status"] == "audited_no_public_trigger"
    assert first["runtime_key"] is None
    assert first["output"] is None
    assert not (MOD / "sound" / "sfx" / "lol_announcer_first_blood.wav").exists()

    overrides = load_json(MOD / "mod.override_info")
    assert all("first_blood" not in key.lower() for key in overrides)
    assert "guessed callback" in report["native_runtime_contract"]["first_blood_boundary"]


def test_center_kill_native_nodes_remain_the_only_visual_announcement_layer() -> None:
    layout = (MOD / "ui" / "layout" / "ingame_component" / "center_kill.ui").read_text(
        encoding="utf-8"
    )
    assert "#text:label" in layout
    assert "#kills:empty" in layout
    for index in range(1, 6):
        assert f"#icon{index}:image" in layout
    assert layout.count("message:empty") == 1
