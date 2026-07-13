from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import wave

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
MOD = ROOT / "mods" / "lol_mod"


KLED_NATIVE_ANIMATION: dict[str, list[float]] = {
    "fire_skill1_pre": [0.080000006] * 2,
    "ult_self_effect_back": [0.040000003] * 14,
    "skill1_dash": [0.080000006],
    "ult_road_effect": [0.080000006] * 9,
    "fire_skill1": [0.080000006] * 3,
    "skill1": [0.080000006] * 3,
    "skill2": [0.080000006] * 3,
    "fire_attack": [0.080000006] * 4,
    "fire_run": [0.060000002] * 8,
    "fire_skill1_end": [0.080000006],
    "fire_skill1_effect": [0.080000006] * 4,
    "run": [0.060000002] * 8,
    "idle": [0.14] * 4,
    "attack": [0.080000006] * 4,
    "dead": [0.1] * 10,
    "fire_skill1_dash": [0.080000006],
    "skill1_effect": [0.080000006] * 4,
    "fire_dead": [0.1] * 11,
    "ult_self_effect": [0.040000003] * 14,
    "ult": [0.080000006] * 4,
    "hit": [0.1],
    "skill1_end": [0.080000006],
    "fire_idle": [0.14] * 4,
    "skill1_pre": [0.080000006] * 2,
}

KLED_NATIVE_AUDIO_EVENTS = {
    "cavalry_knight_attack",
    "cavalry_knight_skill1",
    "cavalry_knight_skill2",
    "cavalry_knight_ult",
}
KLED_NATIVE_AUDIO_CLIPS = {
    "cavalry_knight_attack_resource",
    "cavalry_knight_skill_resource",
    "cavalry_knight_skill2_resource",
    "cavalry_knight_ult_resource",
}
KLED_NATIVE_SILENCE_SHA256 = "73b42ab23be05ebeada04e01d7a8b903a1cdd1753a090c5032983da1066bacc2"


def load_json(relative: str):
    return json.loads((MOD / relative).read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def walk_effects(value):
    if isinstance(value, dict):
        if isinstance(value.get("type"), str):
            yield value
        for child in value.values():
            yield from walk_effects(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk_effects(child)


def find_effect(root, effect_type: str, **fields):
    return [
        effect
        for effect in walk_effects(root)
        if effect.get("type") == effect_type
        and all(effect.get(key) == value for key, value in fields.items())
    ]


def direct_effects(effect: dict, effect_type: str) -> list[dict]:
    return [
        child
        for child in effect.get("effects", [])
        if isinstance(child, dict) and child.get("type") == effect_type
    ]


def direct_buff_states(effect: dict, effect_type: str) -> list[dict]:
    return [child["buff_state"] for child in direct_effects(effect, effect_type)]


def frame_crop(sheet: Image.Image, row: dict) -> Image.Image:
    data = row["data"]
    x, y, width, height = (int(data[key]) for key in ("x", "y", "w", "h"))
    assert x >= 0 and y >= 0 and width > 0 and height > 0
    assert x + width <= sheet.width and y + height <= sheet.height
    return sheet.crop((x, y, x + width, y + height))


def asset_runtime_paths(asset: str) -> set[str]:
    prefix = "asset/lol_mod/"
    assert asset.startswith(prefix)
    relative = asset.removeprefix(prefix)
    return {f"{relative}#sheet.png", f"{relative}#anim.fanim"}


def test_kled_replaces_official_006_once_and_exposes_only_q_e_r() -> None:
    champions = [
        (path.name, json.loads(path.read_text(encoding="utf-8")))
        for path in sorted((MOD / "champion").glob("*.data_champion"))
    ]
    assert [name for name, champion in champions if champion.get("id") == "cavalry_knight"] == [
        "cavalry_knight.data_champion"
    ]
    assert all(champion.get("id") != "lol_kled" for _, champion in champions)
    assert not (MOD / "champion/lol_kled.data_champion").exists()
    assert load_json("mod.mod_info")["version"] == "0.10.9"

    kled = load_json("champion/cavalry_knight.data_champion")
    assert kled["id"] == "cavalry_knight"
    assert kled["sprite"] == "asset/lol_mod/aseprite_resources/champions/kled"
    assert kled["anim_prefix"] == ""
    assert kled["category"] == "Melee"
    assert set(kled["tags"]) == {"AD", "Melee", "CC"}
    assert kled["skill_icons"] == [
        "asset/lol_mod/icons/kled_skill",
        "asset/lol_mod/icons/kled_skill2",
        "asset/lol_mod/icons/kled_ult",
    ]
    assert [kled[key]["action_name"] for key in ("attack", "skill", "skill2", "ult")] == [
        "attack",
        "skill1",
        "skill2",
        "ult",
    ]
    assert not {"w", "skill3", "skill4"}.intersection(kled)


def test_kled_stats_and_action_slots_match_the_approved_006_contract() -> None:
    kled = load_json("champion/cavalry_knight.data_champion")
    assert kled["stat"] == {
        "attack": 90,
        "magic_power": 0,
        "hp": 950,
        "defence": 25,
        "magic_resistance": 18,
        "move_speed": 1200,
        "hp_regen": 3,
        "stack": 0,
        "crit_chance": 0,
    }
    assert kled["growth"] == {
        "attack": 18,
        "magic_power": 0,
        "hp": 95,
        "defence": 7,
        "magic_resistance": 3,
        "move_speed": 15,
        "hp_regen": 1,
        "stack": 0,
        "crit_chance": 0,
    }
    assert kled["attack"]["range"] == 27000
    assert kled["attack"]["cooltime"] == 50
    for key, letter in (("skill", "Q"), ("skill2", "E"), ("ult", "R")):
        action = kled[key]
        for required in (
            "action_name",
            "description",
            "duration",
            "cooltime",
            "start_timing",
            "cancelable",
            "range",
            "casting_type",
            "casting_target",
            "attack_type",
            "effect",
        ):
            assert required in action, f"{letter} is missing {required}"


def test_kled_basic_attack_is_plain_and_has_no_retired_w_state_machine() -> None:
    kled = load_json("champion/cavalry_knight.data_champion")
    attack = kled["attack"]
    assert attack["effect"]["type"] == "Combine"
    assert direct_effects(attack["effect"], "Attack") == [
        {"type": "Attack", "damage": 0, "attack_ratio": 100}
    ]
    assert not find_effect(kled, "SwitchByBuff")
    serialized = json.dumps(kled, ensure_ascii=False)
    assert "lol_kled_violent_" not in serialized
    assert "kled_w_" not in serialized


def test_kled_q_is_one_nonpenetrating_beartrap_projectile_with_delayed_tether() -> None:
    skill = load_json("champion/cavalry_knight.data_champion")["skill"]
    assert (
        skill["action_name"],
        skill["range"],
        skill["cooltime"],
        skill["duration"],
        skill["start_timing"],
        skill["casting_type"],
        skill["casting_target"],
    ) == ("skill1", 65000, 360, 36, 8, "Direction", "EnemyChampion")
    assert not find_effect(skill, "Rush")
    projectiles = find_effect(skill, "LinearProjectile", name="lol_kled_q_beartrap_projectile")
    assert len(projectiles) == 1
    projectile = projectiles[0]
    assert (
        projectile["penetrate"],
        projectile["speed"],
        projectile["range"],
        projectile["shape"],
        projectile["applied_target"],
    ) == (False, 6500, 72000, {"Circle": {"radius": 10000}}, "EnemyChampion")
    assert len(projectile["applied_effects"]) == 1
    assert projectile["end_effects"] == []
    hit = projectile["applied_effects"][0]
    assert hit["casting_type"] == "Targeting"
    hit_effect = hit["effect"]
    assert direct_effects(hit_effect, "Attack") == [
        {"type": "Attack", "damage": 30, "attack_ratio": 80}
    ]
    assert direct_buff_states(hit_effect, "AddBuff") == [
        {
            "name": "lol_kled_q_tethered",
            "duration": {"Time": {"tick": 45}},
            "move_speed_mult": -20,
        }
    ]
    assert not direct_buff_states(hit_effect, "AddCasterBuff")
    delayed = direct_effects(hit_effect, "Delayed")
    assert len(delayed) == 1 and delayed[0]["tick"] == 45
    assert direct_effects(delayed[0], "Attack") == [
        {"type": "Attack", "damage": 20, "attack_ratio": 40}
    ]
    assert direct_effects(delayed[0], "Grab") == [
        {"type": "Grab", "speed": 2200, "tick": 8}
    ]
    assert direct_effects(delayed[0], "Bind") == [{"type": "Bind", "duration": 30}]
    assert [(effect["damage"], effect["attack_ratio"]) for effect in find_effect(projectile, "Attack")] == [
        (30, 80),
        (20, 40),
    ]
    assert len(find_effect(skill, "Sfx", name="lol_kled_q_cast")) == 1
    assert not find_effect(skill, "Sfx", name="lol_kled_e_cast")

    kled = load_json("champion/cavalry_knight.data_champion")
    projectile_view = {
        view["name"]: view for view in kled["view_projectiles"]
    }["lol_kled_q_beartrap_projectile"]
    assert projectile_view == {
        "type": "Animated",
        "name": "lol_kled_q_beartrap_projectile",
        "anim": "asset/lol_mod/aseprite_resources/effects/kled_q_tether",
        "tag": "projectile",
        "z": 2,
        "repeat": True,
    }
    q_effects = {
        view["name"]: view
        for view in kled["view_effects"]
        if view["name"].startswith("lol_kled_q_")
    }
    assert {name: view["tag"] for name, view in q_effects.items()} == {
        "lol_kled_q_latch_visual": "latch",
        "lol_kled_q_pull_visual": "pull",
    }
    q_buff = {view["name"]: view for view in kled["view_buffs"]}["lol_kled_q_tethered"]
    assert (
        q_buff["anim"],
        q_buff["pre_tag"],
        q_buff["loop_tag"],
        q_buff["remove_tag"],
    ) == (
        "asset/lol_mod/aseprite_resources/effects/kled_q_tether",
        "tether_pre",
        "tether_loop",
        "tether_remove",
    )


def test_kled_e_is_an_independent_nonpenetrating_joust_rush() -> None:
    skill2 = load_json("champion/cavalry_knight.data_champion")["skill2"]
    assert (
        skill2["action_name"],
        skill2["cooltime"],
        skill2["duration"],
        skill2["start_timing"],
        skill2["range"],
        skill2["casting_type"],
        skill2["casting_target"],
    ) == ("skill2", 480, 13, 11, 55000, "Direction", "EnemyChampion")
    rushes = find_effect(skill2, "Rush")
    assert len(rushes) == 1
    rush = rushes[0]
    assert (
        rush["speed"],
        rush["move_speed_ratio"],
        rush["range"],
        rush["casting_target"],
        rush["penetrate"],
    ) == (3200, 100, 12000, "EnemyChampion", False)
    assert len(rush["applied_effects"]) == 1
    hit = rush["applied_effects"][0]
    assert hit["casting_type"] == "Targeting"
    payload = hit["effect"]
    assert direct_effects(payload, "Attack") == [
        {"type": "Attack", "damage": 30, "attack_ratio": 80}
    ]
    assert direct_buff_states(payload, "AddCasterBuff") == [
        {
            "name": "lol_kled_e_hit_speed",
            "duration": {"Time": {"tick": 60}},
            "move_speed_mult": 20,
        }
    ]
    assert not find_effect(skill2, "LinearProjectile")
    assert not find_effect(skill2, "Delayed")
    assert not find_effect(skill2, "Grab")
    assert not find_effect(skill2, "Bind")
    assert len(find_effect(skill2, "Sfx", name="lol_kled_e_cast")) == 1
    assert len(find_effect(skill2, "TargetSfx", name="lol_kled_e_hit")) == 1
    serialized = json.dumps(skill2, ensure_ascii=False)
    assert "lol_kled_q_" not in serialized
    assert "lol_kled_violent_" not in serialized

    kled = load_json("champion/cavalry_knight.data_champion")
    e_effects = {
        view["name"]: view
        for view in kled["view_effects"]
        if view["name"].startswith("lol_kled_e_")
    }
    assert {name: (view["anim"], view["tag"]) for name, view in e_effects.items()} == {
        "lol_kled_e_dash_visual": (
            "asset/lol_mod/aseprite_resources/effects/kled_e_joust",
            "dash",
        ),
        "lol_kled_e_impact_visual": (
            "asset/lol_mod/aseprite_resources/effects/kled_e_joust",
            "impact",
        ),
    }


def test_kled_r_has_one_ally_only_route_one_self_package_and_one_first_hit_rush() -> None:
    ult = load_json("champion/cavalry_knight.data_champion")["ult"]
    assert (
        ult["action_name"],
        ult["range"],
        ult["cooltime"],
        ult["duration"],
        ult["start_timing"],
        ult["casting_type"],
        ult["casting_target"],
    ) == ("ult", 120000, 3600, 120, 1, "Position", "EnemyChampion")

    routes = find_effect(ult, "LineRangeProjectile")
    assert len(routes) == 1
    route = routes[0]
    assert (
        route["width"],
        route["length"],
        route["delay"],
        route["apply"],
        route["applied_target"],
    ) == (22000, 120000, 0, 240, "AllyNotSelf")
    route_buffs = [effect["buff_state"] for effect in find_effect(route["applied_effects"], "AddBuff")]
    assert route_buffs == [
        {
            "name": "lol_kled_r_trail_speed",
            "duration": {"Time": {"tick": 30}},
            "move_speed_mult": 25,
        }
    ]
    assert not find_effect(route, "Attack") and not find_effect(route, "Shield")

    self_packages = find_effect(ult, "WithSelf")
    assert len(self_packages) == 1
    self_package = self_packages[0]
    assert find_effect(self_package, "Shield", amount=200, attack_ratio=80, ap_ratio=0, tick=180)
    self_buffs = {state["name"]: state for state in direct_buff_states(self_package, "AddCasterBuff")}
    assert self_buffs == {
        "lol_kled_r_charge_speed": {
            "name": "lol_kled_r_charge_speed",
            "duration": {"Time": {"tick": 120}},
            "move_speed_mult": 50,
        },
        "lol_kled_r_cc_immune": {
            "name": "lol_kled_r_cc_immune",
            "duration": {"Time": {"tick": 90}},
            "cc_immune": True,
        },
    }
    assert "lol_kled_r_trail_speed" not in self_buffs
    assert not [
        effect
        for effect in find_effect(ult, "AddCasterBuff")
        if effect.get("buff_state", {}).get("name") == "lol_kled_r_trail_speed"
    ]

    rushes = find_effect(ult, "Rush")
    assert len(rushes) == 1
    rush = rushes[0]
    assert (
        rush["speed"],
        rush["move_speed_ratio"],
        rush["range"],
        rush["casting_target"],
        rush["penetrate"],
    ) == (4200, 150, 14000, "EnemyChampion", False)
    assert len(rush["applied_effects"]) == 1
    impact = rush["applied_effects"][0]["effect"]
    assert direct_effects(impact, "Attack") == [
        {
            "type": "Attack",
            "damage": 80,
            "attack_ratio": 100,
            "target_hp_ratio": 2,
        }
    ]
    assert direct_effects(impact, "Knockback") == [
        {"type": "Knockback", "speed": 2400, "tick": 8}
    ]
    assert direct_effects(impact, "Airborne") == [{"type": "Airborne", "duration": 18}]
    assert len(find_effect(rush, "Attack")) == 1


def test_kled_preserves_the_exact_native_cavalry_24_tag_contract() -> None:
    anim = load_json("aseprite_resources/champions/kled#anim.fanim")["anims"]
    assert list(anim) == list(KLED_NATIVE_ANIMATION)
    assert len(anim) == 24
    assert not {"attack_w1", "attack_w2", "attack_w3", "attack_w4", "skill", "run_fast"}.intersection(anim)

    sheet = Image.open(MOD / "aseprite_resources/champions/kled#sheet.png").convert("RGBA")
    for tag, expected_durations in KLED_NATIVE_ANIMATION.items():
        rows = anim[tag]["frames"]
        actual_durations = [float(row["duration"]) for row in rows]
        assert len(rows) == len(expected_durations), tag
        assert all(
            math.isclose(actual, expected, rel_tol=0.0, abs_tol=1e-9)
            for actual, expected in zip(actual_durations, expected_durations, strict=True)
        ), tag
        for row in rows:
            frame_crop(sheet, row)

    first_idle = frame_crop(sheet, anim["idle"]["frames"][0])
    idle_bbox = first_idle.getchannel("A").getbbox()
    assert idle_bbox is not None
    assert idle_bbox[2] - idle_bbox[0] <= 58
    assert 36 <= idle_bbox[3] - idle_bbox[1] <= 44
    assert idle_bbox[3] <= 46

    run_hashes = [
        hashlib.sha256(frame_crop(sheet, row).tobytes()).hexdigest()
        for row in anim["run"]["frames"]
    ]
    assert len(set(run_hashes)) >= 6
    for tag in ("dead", "fire_dead"):
        last = frame_crop(sheet, anim[tag]["frames"][-1])
        assert last.getchannel("A").getbbox() is None


def test_kled_localization_compact_style_encyclopedia_and_bp_are_registered() -> None:
    text = load_json("text/champion.i18n")
    expected_names = {
        "en": "Kled",
        "zh-hans": "克烈",
        "zh-hant": "克烈",
        "ja": "クレッド",
        "ko": "클레드",
    }
    for locale, expected_name in expected_names.items():
        descriptions = text[locale]["description"]
        assert "lol_kled" not in descriptions
        description = descriptions["cavalry_knight"]
        assert description["name"] == expected_name
        assert description["skill"].startswith("Q")
        assert description["skill2"].startswith("E")
        assert description["ult"].startswith("R")
        combined = " ".join(description[key] for key in ("attack", "skill", "skill2"))
        assert "Q+E" not in combined and "Q + E" not in combined
        assert "W mapping" not in combined and "承载W" not in combined

    style = load_json("style/champion_view.champion_view")["entries"]["cavalry_knight"]
    assert style["center"] == {"x": 0, "y": -12}
    assert style["face"] == {"x": 1, "y": -36}
    assert style["face"] != style["center"]

    # Keep the Kled-only camera as a fallback.  The runtime portrait router
    # below supplies source-direct art because an offset cannot add face
    # pixels to an 18px full-mounted icon.
    anim = load_json("aseprite_resources/champions/kled#anim.fanim")["anims"]
    sheet = Image.open(MOD / "aseprite_resources/champions/kled#sheet.png").convert("RGBA")
    first_idle = frame_crop(sheet, anim["idle"]["frames"][0])
    compact_bbox = first_idle.getchannel("A").getbbox()
    assert compact_bbox is not None
    assert 36 <= compact_bbox[2] - compact_bbox[0] <= 44
    assert 36 <= compact_bbox[3] - compact_bbox[1] <= 44
    assert compact_bbox[1] <= 6
    assert compact_bbox[3] <= 46

    builder = (MOD / "tools/build_lol_mod.py").read_text(encoding="utf-8")
    assert '"cavalry_knight": ACTOR_DIR / "kled#sheet.png"' in builder

    champion_slot = (MOD / "ui/layout/champion_info_component/champion_slot.ui").read_text(
        encoding="utf-8"
    )
    assert "#lol_fullbody_kled:image" in champion_slot
    assert 'source: "asset/lol_mod/ui/champion_fullbody/cavalry_knight";' in champion_slot

    runtime = (MOD / "src/lib.rs").read_text(encoding="utf-8")
    assert '"asset/lol_mod/BanPickIllust/cavalry_knight"' in runtime
    assert '("cavalry_knight", "lol_fullbody_kled")' in runtime
    assert '"kled" | "cavalry_knight" => Some("cavalry_knight")' in runtime
    assert "rewrite_kled_portrait_render_commands(state);" in runtime
    assert "KLED_COMPACT_PORTRAIT_TEXTURE" in runtime
    assert "KLED_BP_GRID_PORTRAIT_TEXTURE" in runtime
    assert '"asset/base/aseprite_resources/champions/cavalry_knight#sheet"' in runtime
    assert '"asset/lol_mod/aseprite_resources/champions/kled#sheet"' in runtime
    assert "let is_compact_square" in runtime
    assert "let is_bp_grid" in runtime
    assert "texture_rect.w = 1.0" in runtime
    assert "*sample_nearest = true" in runtime

    fullbody = Image.open(MOD / "ui/champion_fullbody/cavalry_knight.png").convert("RGBA")
    assert fullbody.size == (64, 64)
    assert fullbody.getchannel("A").getbbox() is not None
    compact = Image.open(MOD / "ui/champion_portrait/cavalry_knight_compact.png").convert("RGBA")
    grid = Image.open(MOD / "ui/champion_portrait/cavalry_knight_grid.png").convert("RGBA")
    assert compact.size == (64, 64)
    assert grid.size == (90, 122)
    compact_ui_bbox = compact.getchannel("A").getbbox()
    assert compact_ui_bbox is not None
    assert compact_ui_bbox[2] - compact_ui_bbox[0] <= 50
    assert compact_ui_bbox[3] - compact_ui_bbox[1] <= 50
    assert min(
        compact_ui_bbox[0],
        compact_ui_bbox[1],
        64 - compact_ui_bbox[2],
        64 - compact_ui_bbox[3],
    ) >= 6
    grid_bbox = grid.getchannel("A").getbbox()
    assert grid_bbox is not None
    assert grid_bbox[3] <= 86
    assert grid_bbox[1] <= 20
    assert compact.getchannel("A").getextrema() == (0, 255)
    assert grid.getchannel("A").getextrema() == (0, 255)
    assert sha256(MOD / "ui/champion_portrait/cavalry_knight_compact.png") != sha256(
        MOD / "ui/champion_fullbody/cavalry_knight.png"
    )
    assert (MOD / "qa/kled_portrait_surface_final.png").is_file()

    source_splash = MOD / "source/imagegen/bp_splash/cavalry_knight.png"
    runtime_splash = MOD / "BanPickIllust/cavalry_knight.png"
    assert source_splash.is_file()
    with Image.open(source_splash) as source_image:
        source_ratio = source_image.width / source_image.height
        assert abs(source_ratio - 284 / 172) <= 0.02
    with Image.open(runtime_splash) as splash:
        assert splash.size == (1420, 860)


def test_kled_audio_replaces_custom_events_and_isolates_native_cavalry_audio() -> None:
    kled = load_json("champion/cavalry_knight.data_champion")
    override = load_json("mod.override_info")
    events = {
        effect["name"]
        for effect in walk_effects(kled)
        if effect.get("type") in {"Sfx", "TargetSfx"}
        and isinstance(effect.get("name"), str)
    }
    assert {"lol_kled_q_cast", "lol_kled_e_cast", "lol_kled_r_cast"}.issubset(events)
    assert len(events) >= 4
    assert all(event.startswith("lol_kled_") for event in events)

    for event in events:
        mapping = override[f"asset/base/sound/sfx/{event}"]
        assert mapping["type"] == "override"
        remapping = mapping["remapping"]
        assert remapping.startswith("asset/lol_mod/sound/sfx/kled_")
        local = remapping.removeprefix("asset/lol_mod/sound/sfx/")
        sound_info = load_json(f"sound/sfx/{local}.sound_info")
        assert sound_info["plays"]
        for play in sound_info["plays"]:
            assert play["volume"] >= 0.85
            clip = play["clip"]
            clip_mapping = override[f"asset/base/sound/sfx/{clip}"]
            assert clip_mapping == {
                "remapping": f"asset/lol_mod/sound/sfx/{clip}",
                "type": "override",
            }
            wav_path = MOD / f"sound/sfx/{clip}.wav"
            with wave.open(str(wav_path), "rb") as decoded:
                assert (decoded.getnchannels(), decoded.getsampwidth(), decoded.getframerate()) == (
                    1,
                    2,
                    44100,
                )

    for event in KLED_NATIVE_AUDIO_EVENTS:
        assert override[f"asset/base/sound/sfx/{event}"] == {
            "remapping": "asset/lol_mod/sound/sfx/kled_native_silence",
            "type": "override",
        }
    for clip in KLED_NATIVE_AUDIO_CLIPS:
        assert override[f"asset/base/sound/sfx/{clip}"] == {
            "remapping": "asset/lol_mod/sound/sfx/kled_native_silence_clip",
            "type": "override",
        }
    assert load_json("sound/sfx/kled_native_silence.sound_info") == {
        "plays": [{"delay": 0.0, "clip": "kled_native_silence_clip", "volume": 1.0}]
    }
    silence = MOD / "sound/sfx/kled_native_silence_clip.wav"
    assert silence.stat().st_size == 4454
    assert sha256(silence) == KLED_NATIVE_SILENCE_SHA256


def test_kled_runtime_assets_are_current_in_the_build_manifest() -> None:
    kled = load_json("champion/cavalry_knight.data_champion")
    manifest = load_json("build_manifest.json")
    files = {row["path"]: row for row in manifest["files"]}
    required = {
        "champion/cavalry_knight.data_champion",
        "aseprite_resources/champions/kled#sheet.png",
        "aseprite_resources/champions/kled#anim.fanim",
        "icons/kled_skill.png",
        "icons/kled_skill2.png",
        "icons/kled_ult.png",
        "BanPickIllust/cavalry_knight.png",
        "ui/champion_fullbody/cavalry_knight.png",
        "ui/champion_portrait/cavalry_knight_compact.png",
        "ui/champion_portrait/cavalry_knight_grid.png",
        "sound/sfx/kled_native_silence.sound_info",
        "sound/sfx/kled_native_silence_clip.wav",
    }
    for view_key in ("view_projectiles", "view_effects", "view_buffs"):
        for view in kled.get(view_key, []):
            required.update(asset_runtime_paths(view["anim"]))
    for effect in walk_effects(kled):
        if effect.get("type") not in {"Sfx", "TargetSfx"}:
            continue
        event = effect.get("name")
        if not isinstance(event, str) or not event.startswith("lol_kled_"):
            continue
        mapping = load_json("mod.override_info")[f"asset/base/sound/sfx/{event}"]
        local = mapping["remapping"].removeprefix("asset/lol_mod/")
        required.add(f"{local}.sound_info")
        for play in load_json(f"{local}.sound_info")["plays"]:
            required.add(f"sound/sfx/{play['clip']}.wav")

    assert required.issubset(files)
    for relative in required:
        path = MOD / relative
        assert path.is_file(), relative
        assert path.stat().st_size == files[relative]["size"], relative
        assert sha256(path) == files[relative]["sha256"], relative
