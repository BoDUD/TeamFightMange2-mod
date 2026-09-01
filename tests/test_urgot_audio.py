from __future__ import annotations

import hashlib
import json
from pathlib import Path
import wave


ROOT = Path(__file__).resolve().parents[1]
MOD = ROOT / "mods" / "lol_mod"

EXPECTED_WAD_SHA256 = "7feab1a2c2994e1f68a213fc6133fca80e29c88799c62bdeb0e82afde4b46975"
EXPECTED_AUDIO_BANK_SHA256 = "675a67d8d46aaf0e71f87c876e19b57b4a2cf2bad1a8f331647071df12f90eef"
EXPECTED_EVENT_BANK_SHA256 = "4ac6f2dff665c8f80fc8ef5a967f73c9b0d1de4e1c59ab6267da9aa68bdb69dc"
EXPECTED_REGISTRY_SHA256 = "2ec2a2e0d668e9ddc45eb78d3a0beb2dc33baebbc2edc6b390212eaddcf5cdab"
EXPECTED_SILENCE_SHA256 = "73b42ab23be05ebeada04e01d7a8b903a1cdd1753a090c5032983da1066bacc2"

EXPECTED_EVENTS = {
    "urgot_attack_cast": "Play_sfx_Urgot_UrgotBasicAttack_cast",
    "urgot_attack_hit": "Play_sfx_Urgot_UrgotBasicAttack_OnHit",
    "urgot_w_cast": "Play_sfx_Urgot_UrgotW_OnCast",
    "urgot_w_shot": "Play_sfx_Urgot_UrgotWMissileExtra_OnMissileLaunch",
    "urgot_e_cast": "Play_sfx_Urgot_UrgotE_OnCast",
    "urgot_e_hit": "Play_sfx_Urgot_UrgotE_OnHitLocation",
    "urgot_r_cast": "Play_sfx_Urgot_UrgotR_OnCast",
    "urgot_r_latch": "Play_sfx_Urgot_UrgotR_OnHit",
    "urgot_r_pull": "Play_sfx_Urgot_UrgotRRecastMissile_OnMissileLaunch",
    "urgot_r_execute": "Play_sfx_Urgot_UrgotRGrind_cast",
    "urgot_r_fear": "Play_sfx_Urgot_UrgotRGrind_fear_hit",
}

EXPECTED_WAV_SHA256 = {
    "urgot_attack_cast": "c12b5f6da7bf6240ce788e254dae9011d89408e16c3607e683d58dc1c7e91682",
    "urgot_attack_hit": "219ac122f5e1ff0cfe0b10d212e4880b0dd022c116b80cc09f0b7474c3643c2f",
    "urgot_w_cast": "6f4b0d9964a07f117971d48de9a97166b7448e580b288988d9fa2a5b2f642d8b",
    "urgot_w_shot": "7e99f5346efa97cc1e8a90ccc031078b2c38dd78568d98310b1b97cc9f964bca",
    "urgot_e_cast": "c86b79295ef7736323c6bf17b624e590662937a6237c49c41f0ea06de236bacc",
    "urgot_e_hit": "40b4c3f8c1b4223b04b114e1499b28c7c3bd5f6e002bca8dc6fd09d7b50a3726",
    "urgot_r_cast": "96f5d69d8ca23ccd8a73ae76151fd8d3b2d589ead79395f20184f134bf313cc3",
    "urgot_r_latch": "697419f718207ad09b357be09d7430808dd4a91c85234a1be1961c63f8b03674",
    "urgot_r_pull": "c7d6dade9dd9198d3e242ecad0fb0ea60babcdabf4d8ff9da30b64f9c8850ff2",
    "urgot_r_execute": "4412a880c536005136a45056f30e23d247eee776af41e847c754dadc48985d48",
    "urgot_r_fear": "7134ab49788fffb2f5b477d941e234d5bda38729473028aa4df525cc02d1c74b",
}

BUNDLED_DEMON_EVENTS = {
    "demon_attack",
    "demon_attack_ult",
    "demon_skill1",
    "demon_transform",
    "demon_ult",
}
BUNDLED_DEMON_CLIPS = {
    "demon_attack0",
    "demon_attack_ult0",
    "demon_skill0",
    "demon_skill1_resource",
    "demon_ult0",
    "demon_ult1",
    "demon_ult_resource",
}


def load_json(relative: str) -> dict:
    return json.loads((MOD / relative).read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fnv1_lower(value: str) -> int:
    result = 2_166_136_261
    for byte in value.lower().encode("utf-8"):
        result = ((result * 16_777_619) & 0xFFFF_FFFF) ^ byte
    return result


def test_urgot_audio_report_pins_local_riot_wad_banks_events_and_tools() -> None:
    report = load_json("qa/urgot_official_audio_sources.json")
    assert report["schema_version"] == 1
    assert report["champion"] == "Urgot"
    assert report["source_product"] == "League of Legends"
    assert report["source_wad"]["sha256"] == EXPECTED_WAD_SHA256
    assert report["internal_audio_bank"]["sha256"] == EXPECTED_AUDIO_BANK_SHA256
    assert report["internal_audio_bank"]["media_count"] == 152
    assert report["internal_event_bank"]["sha256"] == EXPECTED_EVENT_BANK_SHA256
    assert report["base_registry"]["sha256"] == EXPECTED_REGISTRY_SHA256

    tools = report["mapping_tools"]
    assert tools["wad_reader"]["version"] == "0.5.6"
    assert tools["event_resolver"]["version"] == "v20250928"
    for key in ("wad_reader", "event_resolver", "decoder"):
        assert len(tools[key]["sha256"]) == 64

    outputs = {row["event_key"]: row for row in report["outputs"]}
    assert set(outputs) == set(EXPECTED_EVENTS)
    for stem, riot_event in EXPECTED_EVENTS.items():
        row = outputs[stem]
        assert row["runtime_event"] == f"lol_{stem}"
        assert row["riot_event"] == riot_event
        assert row["riot_event_id"] == fnv1_lower(riot_event)
        assert row["media_id"] in row["event_media_pool"]
        assert len(row["source_wem_sha256"]) == 64
        assert row["wav"]["sha256"] == EXPECTED_WAV_SHA256[stem]


def test_urgot_official_wavs_and_sound_info_are_deterministic_and_audible() -> None:
    report = load_json("qa/urgot_official_audio_sources.json")
    for row in report["outputs"]:
        stem = row["event_key"]
        assert load_json(f"sound/sfx/{stem}.sound_info") == {
            "plays": [{"delay": 0.0, "clip": f"{stem}_clip", "volume": 1.0}]
        }
        wav_path = MOD / row["wav"]["path"]
        assert wav_path.stat().st_size == row["wav"]["size_bytes"]
        assert sha256(wav_path) == row["wav"]["sha256"]
        with wave.open(str(wav_path), "rb") as decoded:
            assert (decoded.getnchannels(), decoded.getsampwidth(), decoded.getframerate()) == (
                1,
                2,
                44_100,
            )
            frames = decoded.readframes(decoded.getnframes())
        assert any(frames), f"official {stem} WAV unexpectedly contains only silence"


def test_urgot_override_maps_every_runtime_event_clip_and_silences_demon() -> None:
    report = load_json("qa/urgot_official_audio_sources.json")
    override = load_json("mod.override_info")
    for row in report["outputs"]:
        stem = row["event_key"]
        assert override[f"asset/base/sound/sfx/lol_{stem}"] == {
            "remapping": f"asset/lol_mod/sound/sfx/{stem}",
            "type": "override",
        }
        assert override[f"asset/base/sound/sfx/{stem}_clip"] == {
            "remapping": f"asset/lol_mod/sound/sfx/{stem}_clip",
            "type": "override",
        }

    isolation = report["native_audio_isolation"]
    assert set(isolation["bundled_native_events"]) == BUNDLED_DEMON_EVENTS
    assert set(isolation["bundled_native_clips"]) == BUNDLED_DEMON_CLIPS
    assert isolation["compatibility_native_events"] == ["demon_skill2"]
    assert isolation["compatibility_native_clips"] == ["demon_skill2_resource"]
    for event in BUNDLED_DEMON_EVENTS | {"demon_skill2"}:
        assert override[f"asset/base/sound/sfx/{event}"] == {
            "remapping": "asset/lol_mod/sound/sfx/urgot_native_silence",
            "type": "override",
        }
    for clip in BUNDLED_DEMON_CLIPS | {"demon_skill2_resource"}:
        assert override[f"asset/base/sound/sfx/{clip}"] == {
            "remapping": "asset/lol_mod/sound/sfx/urgot_native_silence_clip",
            "type": "override",
        }

    assert load_json("sound/sfx/urgot_native_silence.sound_info") == {
        "plays": [{"delay": 0.0, "clip": "urgot_native_silence_clip", "volume": 1.0}]
    }
    silence_path = MOD / "sound/sfx/urgot_native_silence_clip.wav"
    assert silence_path.stat().st_size == 4_454
    assert sha256(silence_path) == EXPECTED_SILENCE_SHA256
    with wave.open(str(silence_path), "rb") as silence:
        assert silence.readframes(silence.getnframes()) == b"\0\0" * 2_205


def test_urgot_audio_extractor_is_the_only_reproducible_source_route() -> None:
    source = (MOD / "tools/extract_urgot_audio.py").read_text(encoding="utf-8")
    assert "Urgot.wad.client" in source
    assert "verify_event_registry" in source
    assert "resolve_event_media_pools" in source
    assert "decoded WAV hash mismatch" in source
    assert "physical silence WAV hash changed" in source
    for stem, event in EXPECTED_EVENTS.items():
        assert f'"{stem}"' in source
        assert f'"{event}"' in source
