from __future__ import annotations

import hashlib
import json
import math
import wave
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
MOD = ROOT / "mods" / "lol_mod"

NATIVE_XAYAH_RECTS = {
    "ult": [(1214, 0, 53, 43), (1268, 0, 41, 45), (1310, 0, 89, 79), (1400, 0, 96, 89), (1497, 0, 96, 89)],
    "idle": [(28, 0, 27, 47), (56, 0, 27, 45), (84, 0, 27, 43), (112, 0, 27, 45)],
    "run": [(140, 0, 25, 45), (166, 0, 23, 47), (190, 0, 25, 49), (216, 0, 23, 47), (240, 0, 25, 45), (266, 0, 25, 47), (292, 0, 27, 49), (320, 0, 25, 47)],
    "projectile": [(490, 0, 13, 13)],
    "hit": [(504, 0, 31, 45)],
    "attack": [(346, 0, 27, 45), (374, 0, 31, 45), (406, 0, 35, 47), (442, 0, 23, 45), (466, 0, 23, 43)],
    "skill1_projectile": [(1056, 0, 27, 27), (1084, 0, 25, 25)],
    "dead": [(536, 0, 31, 43), (568, 0, 31, 41), (600, 0, 31, 39), (632, 0, 31, 37), (664, 0, 31, 33), (696, 0, 31, 33), (728, 0, 31, 33), (760, 0, 31, 33), (792, 0, 31, 33), (824, 0, 3, 3)],
    "skill1": [(828, 0, 41, 45), (870, 0, 49, 47), (920, 0, 51, 67), (972, 0, 39, 49), (1012, 0, 43, 57)],
    "skill2": [(1110, 0, 35, 61), (1146, 0, 33, 63), (1180, 0, 33, 67)],
}


def load_json(relative: str):
    return json.loads((MOD / relative).read_text(encoding="utf-8"))


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


def added_caster_buff_names(root) -> set[str]:
    return {
        effect["buff_state"]["name"]
        for effect in find_effect(root, "AddCasterBuff")
        if isinstance(effect.get("buff_state"), dict)
        and isinstance(effect["buff_state"].get("name"), str)
    }


def removed_caster_buff_names(root) -> set[str]:
    return {
        effect["name"]
        for effect in find_effect(root, "RemoveCasterBuff")
        if isinstance(effect.get("name"), str)
    }


def test_xayah_replaces_official_007_once_and_exposes_only_q_e_r() -> None:
    champions = [
        (path.name, json.loads(path.read_text(encoding="utf-8")))
        for path in sorted((MOD / "champion").glob("*.data_champion"))
    ]
    assert [name for name, champion in champions if champion.get("id") == "dancer"] == [
        "dancer.data_champion"
    ]
    assert all(champion.get("id") != "lol_xayah" for _, champion in champions)
    assert not (MOD / "champion/lol_xayah.data_champion").exists()

    xayah = load_json("champion/dancer.data_champion")
    assert xayah["id"] == "dancer"
    assert xayah["sprite"] == "asset/lol_mod/aseprite_resources/champions/xayah"
    assert xayah["anim_prefix"] == ""
    assert xayah["category"] == "Range"
    assert set(xayah["tags"]) == {"AD", "Range", "CC"}
    assert xayah["skill_icons"] == [
        "asset/lol_mod/icons/xayah_skill",
        "asset/lol_mod/icons/xayah_skill2",
        "asset/lol_mod/icons/xayah_ult",
    ]
    assert [xayah[key]["action_name"] for key in ("attack", "skill", "skill2", "ult")] == [
        "attack",
        "skill1",
        "skill2",
        "ult",
    ]
    assert not {"w", "skill3", "skill4"}.intersection(xayah)


def test_xayah_stats_and_native_007_action_slots_match_the_contract() -> None:
    xayah = load_json("champion/dancer.data_champion")
    assert xayah["stat"] == {
        "attack": 100,
        "magic_power": 0,
        "hp": 900,
        "defence": 20,
        "magic_resistance": 15,
        "move_speed": 920,
        "hp_regen": 2,
        "stack": 0,
        "crit_chance": 0,
    }
    assert xayah["growth"] == {
        "attack": 18,
        "magic_power": 0,
        "hp": 90,
        "defence": 7,
        "magic_resistance": 3,
        "move_speed": 8,
        "hp_regen": 1,
        "stack": 0,
        "crit_chance": 0,
    }
    assert xayah["attack"]["range"] == 60000
    assert xayah["attack"]["cooltime"] == 60
    for key in ("skill", "skill2", "ult"):
        action = xayah[key]
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
            assert required in action


def test_clean_cuts_is_a_three_attack_state_machine_and_leaves_one_feather() -> None:
    xayah = load_json("champion/dancer.data_champion")
    attack = xayah["attack"]
    switch_names = {
        effect["buff_name"]
        for effect in find_effect(attack, "SwitchByBuff")
        if isinstance(effect.get("buff_name"), str)
    }
    assert {"lol_xayah_clean_cuts_3", "lol_xayah_clean_cuts_2", "lol_xayah_clean_cuts_1"}.issubset(
        switch_names
    )
    assert {f"lol_xayah_feathers_{count}" for count in range(1, 6)}.issubset(switch_names)

    targeted_ratios = sorted(
        effect["attack_ratio"]
        for projectile in find_effect(attack, "TargetProjectile", name="lol_xayah_attack_feather")
        for effect in find_effect(projectile, "Attack")
    )
    assert targeted_ratios == [65, 65, 65, 100]
    clean_cut_lines = find_effect(attack, "LinearProjectile", name="lol_xayah_clean_cut_feather")
    assert len(clean_cut_lines) == 3
    for projectile in clean_cut_lines:
        assert (projectile["penetrate"], projectile["range"], projectile["shape"]) == (
            True,
            72000,
            {"Circle": {"radius": 6500}},
        )
        assert [(hit["damage"], hit["attack_ratio"]) for hit in find_effect(projectile, "Attack")] == [
            (0, 35)
        ]
        assert projectile["end_effects"] == []

    added = added_caster_buff_names(attack)
    removed = removed_caster_buff_names(attack)
    assert {f"lol_xayah_feathers_{count}" for count in range(1, 6)}.issubset(added)
    assert {f"lol_xayah_feathers_{count}" for count in range(1, 6)}.issubset(removed)
    assert {"lol_xayah_clean_cuts_2", "lol_xayah_clean_cuts_1"}.issubset(added)
    assert {"lol_xayah_clean_cuts_3", "lol_xayah_clean_cuts_2", "lol_xayah_clean_cuts_1"}.issubset(
        removed
    )


def test_q_is_exactly_two_penetrating_feathers_and_second_is_delayed_six_ticks() -> None:
    q = load_json("champion/dancer.data_champion")["skill"]
    assert (
        q["action_name"],
        q["cooltime"],
        q["duration"],
        q["start_timing"],
        q["range"],
        q["casting_type"],
        q["casting_target"],
    ) == ("skill1", 360, 28, 8, 72000, "Direction", "EnemyWithoutTower")
    projectiles = find_effect(q, "LinearProjectile", name="lol_xayah_q_feather")
    assert len(projectiles) == 2
    for projectile in projectiles:
        assert (
            projectile["penetrate"],
            projectile["speed"],
            projectile["range"],
            projectile["shape"],
            projectile["applied_target"],
        ) == (True, 8000, 72000, {"Circle": {"radius": 7000}}, "EnemyWithoutTower")
        assert [(hit["damage"], hit["attack_ratio"]) for hit in find_effect(projectile, "Attack")] == [
            (25, 45)
        ]
        ground = find_effect(projectile.get("end_effects", []), "RangePeriodProjectile")
        assert len(ground) == 1
        assert ground[0] == {
            "type": "RangePeriodProjectile",
            "name": "lol_xayah_ground_single",
            "tick": 180,
            "period": 180,
            "first_delay": 0,
            "shape": {"Circle": {"radius": 1000}},
            "applied_target": "EnemyWithoutTower",
            "applied_effects": [],
            "end_effects": [],
        }
    delayed = find_effect(q, "Delayed")
    assert len(delayed) == 1 and delayed[0]["tick"] == 6
    assert len(find_effect(delayed[0], "LinearProjectile", name="lol_xayah_q_feather")) == 1
    # Q ground markers are visual-only and bounded. Q itself must never contain
    # E's recall/root primitives or dispatch any E/R sound event.
    assert not find_effect(q, "BackToCasterLinearProjectile")
    assert not find_effect(q, "Bind")
    q_named_effects = {
        effect.get("name")
        for effect in walk_effects(q)
        if isinstance(effect.get("name"), str)
    }
    assert not {name for name in q_named_effects if name.startswith("lol_xayah_e_")}
    assert not {name for name in q_named_effects if name.startswith("lol_xayah_r_")}
    assert "lol_xayah_clean_cuts_3" in added_caster_buff_names(q)
    assert {f"lol_xayah_feathers_{count}" for count in range(1, 6)}.issubset(
        added_caster_buff_names(q) | removed_caster_buff_names(q)
    )


def test_e_is_its_own_slot_with_five_branches_and_roots_only_at_three_or_more() -> None:
    e = load_json("champion/dancer.data_champion")["skill2"]
    assert (
        e["action_name"],
        e["cooltime"],
        e["range"],
        e["casting_type"],
        e["casting_target"],
    ) == ("skill2", 720, 90000, "Direction", "EnemyWithoutTower")
    switches = [
        effect["buff_name"]
        for effect in find_effect(e, "SwitchByBuff")
        if isinstance(effect.get("buff_name"), str)
    ]
    assert switches[:5] == [f"lol_xayah_feathers_{count}" for count in (5, 4, 3, 2, 1)]

    anchors = find_effect(e, "LinearProjectile", name="lol_xayah_e_anchor")
    assert len(anchors) == 5
    assert all(anchor["speed"] == 30000 and anchor["applied_effects"] == [] for anchor in anchors)
    recalls = [
        projectile
        for projectile in find_effect(e, "BackToCasterLinearProjectile")
        if str(projectile.get("name", "")).startswith("lol_xayah_e_recall_")
    ]
    roots = find_effect(e, "BackToCasterLinearProjectile", name="lol_xayah_e_third_feather_root")
    assert len(recalls) == 5
    assert len(roots) == 3
    assert [projectile["name"] for projectile in recalls] == [
        "lol_xayah_e_recall_cluster",
        "lol_xayah_e_recall_cluster",
        "lol_xayah_e_recall_cluster",
        "lol_xayah_e_recall_double",
        "lol_xayah_e_recall_single",
    ]
    assert [
        (find_effect(recall, "Attack")[0]["damage"], find_effect(recall, "Attack")[0]["attack_ratio"])
        for recall in recalls
    ] == [(80, 65), (65, 55), (50, 45), (35, 35), (20, 25)]
    assert all(root["shape"] == {"Circle": {"radius": 6500}} for root in roots)
    assert all(root["applied_target"] == "EnemyWithoutTower" for root in roots)
    assert [bind["duration"] for root in roots for bind in find_effect(root, "Bind")] == [45, 45, 45]
    assert len(find_effect(e, "Sfx", name="lol_xayah_e_cast")) == 1
    assert len(find_effect(e, "Sfx", name="lol_xayah_e_launch")) == 1
    assert len(find_effect(e, "Sfx", name="lol_xayah_e_catch")) == 5
    assert len(find_effect(e, "TargetSfx", name="lol_xayah_e_root")) == 3
    assert len(find_effect(e, "CasterViewEffect", name="lol_xayah_e_call_visual")) == 1
    # E has no Q projectile or R fan. It only recalls after this separate
    # skill2 action is selected.
    assert not find_effect(e, "LinearProjectile", name="lol_xayah_q_feather")
    assert not find_effect(e, "LinearProjectile", name="lol_xayah_r_fan")
    assert not find_effect(e, "Sfx", name="lol_xayah_q_cast")
    assert not find_effect(e, "Sfx", name="lol_xayah_r_cast")
    assert not find_effect(e, "RangePeriodProjectile")
    assert not find_effect(e, "Native", effect_ref="lol_xayah_ai_feather_add_1")
    assert not find_effect(e, "Native", effect_ref="lol_xayah_ai_feather_add_2")
    assert not find_effect(e, "Native", effect_ref="lol_xayah_ai_feather_set_5")
    assert len(find_effect(e, "Native", effect_ref="lol_xayah_ai_feather_clear")) == 1
    assert {f"lol_xayah_feathers_{count}" for count in range(1, 6)}.issubset(
        removed_caster_buff_names(e)
    )
    assert "lol_xayah_clean_cuts_3" in added_caster_buff_names(e)


def test_r_is_outbound_only_sets_five_feathers_leaves_bounded_fan_and_never_auto_recalls() -> None:
    r = load_json("champion/dancer.data_champion")["ult"]
    assert (
        r["action_name"],
        r["cooltime"],
        r["duration"],
        r["range"],
        r["casting_type"],
    ) == ("ult", 3000, 60, 80000, "Direction")
    cast_visuals = find_effect(r, "CasterViewEffect", name="lol_xayah_r_guard_visual")
    assert cast_visuals == [
        {"type": "CasterViewEffect", "name": "lol_xayah_r_guard_visual"}
    ]
    delayed = find_effect(r, "Delayed")
    assert len(delayed) == 1 and delayed[0]["tick"] == 12
    assert len(find_effect(delayed[0], "LinearProjectile", name="lol_xayah_r_fan")) == 1
    fans = find_effect(r, "LinearProjectile", name="lol_xayah_r_fan")
    assert len(fans) == 1
    assert (fans[0]["penetrate"], fans[0]["shape"], fans[0]["applied_target"]) == (
        True,
        {"Circle": {"radius": 18000}},
        "EnemyWithoutTower",
    )
    assert [(hit["damage"], hit["attack_ratio"]) for hit in find_effect(fans[0], "Attack")] == [
        (80, 70)
    ]
    ground = find_effect(fans[0].get("end_effects", []), "RangePeriodProjectile")
    assert ground == [
        {
            "type": "RangePeriodProjectile",
            "name": "lol_xayah_ground_fan",
            "tick": 180,
            "period": 180,
            "first_delay": 0,
            "shape": {"Circle": {"radius": 1000}},
            "applied_target": "EnemyWithoutTower",
            "applied_effects": [],
            "end_effects": [],
        }
    ]
    guards = [
        effect["buff_state"]
        for effect in find_effect(r, "AddCasterBuff")
        if effect.get("buff_state", {}).get("name") == "lol_xayah_r_safety_window"
    ]
    assert guards == [
        {
            "name": "lol_xayah_r_safety_window",
            "duration": {"Time": {"tick": 60}},
            "damaged_reduce": 100,
            "skill_damaged_reduce": 100,
            "cc_immune": True,
        }
    ]
    assert "lol_xayah_feathers_5" in added_caster_buff_names(r)
    assert "lol_xayah_clean_cuts_3" in added_caster_buff_names(r)
    assert not find_effect(r, "BackToCasterLinearProjectile")
    assert not find_effect(r, "Bind")
    assert not find_effect(r, "Sfx", name="lol_xayah_e_cast")
    assert not find_effect(r, "Sfx", name="lol_xayah_e_launch")
    assert len(find_effect(r, "Sfx", name="lol_xayah_r_cast")) == 1
    assert not find_effect(r, "TargetSfx", name="lol_xayah_r_hit")
    assert len(find_effect(r, "Native", effect_ref="lol_xayah_ai_feather_set_5")) == 1


def test_xayah_ai_e_gate_tracks_bounded_counts_and_blocks_only_empty_bladecaller() -> None:
    xayah = load_json("champion/dancer.data_champion")
    assert len(find_effect(xayah["attack"], "Native", effect_ref="lol_xayah_ai_feather_add_1")) == 3
    assert len(find_effect(xayah["skill"], "Native", effect_ref="lol_xayah_ai_feather_add_2")) == 1
    assert len(find_effect(xayah["ult"], "Native", effect_ref="lol_xayah_ai_feather_set_5")) == 1
    assert len(find_effect(xayah["skill2"], "Native", effect_ref="lol_xayah_ai_feather_clear")) == 1

    runtime = (MOD / "src/lib.rs").read_text(encoding="utf-8")
    for native_event in (
        "lol_xayah_ai_feather_add_1",
        "lol_xayah_ai_feather_add_2",
        "lol_xayah_ai_feather_set_5",
        "lol_xayah_ai_feather_clear",
    ):
        assert f'registration.add_native_effect(\n        "{native_event}"' in runtime
    assert "const XAYAH_FEATHER_STATE_TTL_TICKS: usize = 600;" in runtime
    assert "const XAYAH_AI_MIN_RECALL_FEATHERS: u8 = 2;" in runtime
    assert "struct XayahFeatherUnitState" in runtime
    assert "unit: EntityHandle" in runtime
    assert "count: u8" in runtime and "expiry_tick: usize" in runtime
    assert "state.count.saturating_add(amount).min(5)" in runtime
    assert "if state.expiry_tick <= now" in runtime
    assert "states.retain(|state| state.expiry_tick > now);" in runtime
    assert '"lol_xayah_feather_input_gate"' in runtime
    assert "let Some(Input::Skill2 { target }) = base_input else" in runtime
    assert "if feather_count >= XAYAH_AI_MIN_RECALL_FEATHERS" in runtime
    assert "PlayerInputDecision::Replace(attack)" in runtime
    assert "registration.add_player_input_ai(XayahFeatherInputGate);" in runtime

    qa = load_json("qa/xayah_replacement_qa.json")
    assert qa["ground_feather_limit"] == {
        "visual_markers_shipped": True,
        "independently_addressable": False,
        "q_endpoint_markers": 2,
        "r_endpoint_fan_markers": 1,
        "ttl_ticks": 180,
        "non_repeating": True,
        "terminal_frame_transparent": True,
        "removed_immediately_by_e": False,
        "reason": qa["ground_feather_limit"]["reason"],
        "audit": "qa/xayah_ground_feather_api_limitations.md",
    }
    assert qa["ai_bladecaller_gate"]["minimum_feathers"] == 2
    assert qa["ai_bladecaller_gate"]["state_ttl_ticks"] == 600
    assert qa["ai_bladecaller_gate"]["running_id_available"] is False
    assert "does not claim strict running-id isolation" in qa["ai_bladecaller_gate"]["limitation"]


def test_xayah_visual_registry_is_distinct_for_attack_q_e_and_r() -> None:
    xayah = load_json("champion/dancer.data_champion")
    projectiles = {view["name"]: view for view in xayah["view_projectiles"]}
    assert projectiles["lol_xayah_e_anchor"] == {
        "type": "Animated",
        "name": "lol_xayah_e_anchor",
        "anim": "asset/lol_mod/aseprite_resources/effects/xayah_e",
        "tag": "anchor",
        "z": 0,
        "repeat": True,
    }
    assert projectiles["lol_xayah_attack_feather"]["anim"].endswith("/xayah_attack")
    assert projectiles["lol_xayah_q_feather"]["anim"].endswith("/xayah_q")
    for name, tag in {
        "lol_xayah_e_recall_single": "return_single",
        "lol_xayah_e_recall_double": "return_double",
        "lol_xayah_e_recall_cluster": "return_cluster",
    }.items():
        assert projectiles[name]["anim"].endswith("/xayah_e")
        assert projectiles[name]["tag"] == tag
    assert projectiles["lol_xayah_e_third_feather_root"]["tag"] == "root"
    assert projectiles["lol_xayah_r_fan"] == {
        "type": "Animated",
        "name": "lol_xayah_r_fan",
        "anim": "asset/lol_mod/aseprite_resources/effects/xayah_r",
        "tag": "fan",
        "z": 3,
        "repeat": False,
    }
    assert projectiles["lol_xayah_ground_single"] == {
        "type": "Animated",
        "name": "lol_xayah_ground_single",
        "anim": "asset/lol_mod/aseprite_resources/effects/xayah_ground_feather",
        "tag": "ground_single",
        "z": 1,
        "repeat": False,
    }
    assert projectiles["lol_xayah_ground_fan"] == {
        "type": "Animated",
        "name": "lol_xayah_ground_fan",
        "anim": "asset/lol_mod/aseprite_resources/effects/xayah_ground_feather",
        "tag": "ground_fan",
        "z": 1,
        "repeat": False,
    }
    views = {view["name"]: view for view in xayah["view_effects"]}
    assert views["lol_xayah_attack_hit_visual"]["tag"] == "hit"
    assert views["lol_xayah_q_hit_visual"]["anim"].endswith("/xayah_q")
    assert views["lol_xayah_e_hit_visual"]["anim"].endswith("/xayah_e")
    assert views["lol_xayah_e_call_visual"]["tag"] == "root"
    assert views["lol_xayah_e_root_visual"]["tag"] == "root"
    assert views["lol_xayah_r_guard_visual"] == {
        "type": "Animation",
        "name": "lol_xayah_r_guard_visual",
        "anim": "asset/lol_mod/aseprite_resources/effects/xayah_r",
        "tag": "guard",
        "z": 1,
        "is_follow": True,
    }
    assert views["lol_xayah_r_hit_visual"]["tag"] == "hit"


def test_xayah_localization_style_encyclopedia_and_audio_isolation_are_registered() -> None:
    text = load_json("text/champion.i18n")
    expected_names = {
        "en": "Xayah",
        "zh-hans": "霞",
        "zh-hant": "剎雅",
        "ja": "ザヤ",
        "ko": "자야",
    }
    for locale, expected_name in expected_names.items():
        description = text[locale]["description"]["dancer"]
        assert description["name"] == expected_name
        assert description["skill"].startswith("Q")
        assert description["skill2"].startswith("E")
        assert description["ult"].startswith("R")
        assert "lol_xayah" not in text[locale]["description"]

    style = load_json("style/champion_view.champion_view")["entries"]["dancer"]
    assert style == {"face": {"x": 2, "y": -32}, "center": {"x": 0, "y": -12}}
    assert style["face"] != style["center"]

    champion_slot = (MOD / "ui/layout/champion_info_component/champion_slot.ui").read_text(
        encoding="utf-8"
    )
    assert "#lol_fullbody_xayah:image" in champion_slot
    assert 'source: "asset/lol_mod/ui/champion_fullbody/dancer";' in champion_slot

    override = load_json("mod.override_info")
    assert override["asset/base/aseprite_resources/champions/dancer#sheet"]["remapping"] == (
        "asset/lol_mod/aseprite_resources/champions/xayah#sheet"
    )
    assert override["asset/base/aseprite_resources/champions/dancer#anim"]["remapping"] == (
        "asset/lol_mod/aseprite_resources/champions/xayah#anim"
    )

    custom_events = {
        "attack_cast",
        "attack_hit",
        "q_cast",
        "q_hit",
        "e_cast",
        "e_launch",
        "e_hit",
        "e_catch",
        "e_root",
        "r_cast",
    }
    for suffix in custom_events:
        key = f"asset/base/sound/sfx/lol_xayah_{suffix}"
        assert override[key] == {
            "remapping": f"asset/lol_mod/sound/sfx/xayah_{suffix}",
            "type": "override",
        }
        clip = f"asset/base/sound/sfx/xayah_{suffix}_clip"
        assert override[clip] == {
            "remapping": f"asset/lol_mod/sound/sfx/xayah_{suffix}_clip",
            "type": "override",
        }
    assert "asset/base/sound/sfx/lol_xayah_r_hit" not in override
    assert "asset/base/sound/sfx/xayah_r_hit_clip" not in override

    for native_event in ("dancer_attack", "dancer_skill1", "dancer_skill2", "dancer_ult"):
        assert override[f"asset/base/sound/sfx/{native_event}"]["remapping"] == (
            "asset/lol_mod/sound/sfx/xayah_native_silence"
        )
    for native_clip in (
        "dancer_attack0",
        "dancer_skill_resource",
        "dancer_skill2_resource",
        "dancer_ult_resource",
    ):
        assert override[f"asset/base/sound/sfx/{native_clip}"]["remapping"] == (
            "asset/lol_mod/sound/sfx/xayah_native_silence_clip"
        )


def test_xayah_actor_preserves_every_native_dancer_animation_rect_and_timing() -> None:
    sheet_path = MOD / "aseprite_resources/champions/xayah#sheet.png"
    anim = load_json("aseprite_resources/champions/xayah#anim.fanim")["anims"]
    assert Image.open(sheet_path).size == (1594, 90)
    assert list(anim) == list(NATIVE_XAYAH_RECTS)

    sheet = Image.open(sheet_path).convert("RGBA")
    run_hashes: set[str] = set()
    for tag, rects in NATIVE_XAYAH_RECTS.items():
        frames = anim[tag]["frames"]
        assert len(frames) == len(rects)
        expected_duration = 0.14 if tag == "idle" else 0.1 if tag in {"hit", "dead"} else 0.05 if tag == "projectile" else 0.080000006
        for index, (frame, expected_rect) in enumerate(zip(frames, rects, strict=True)):
            assert tuple(frame["data"][key] for key in ("x", "y", "w", "h")) == expected_rect
            assert math.isclose(frame["duration"], expected_duration, rel_tol=0, abs_tol=1e-9)
            x, y, width, height = expected_rect
            crop = sheet.crop((x, y, x + width, y + height))
            bbox = crop.getchannel("A").getbbox()
            if tag == "dead" and index == len(rects) - 1:
                assert bbox is None
            else:
                assert bbox is not None, (tag, index)
            if tag == "run":
                run_hashes.add(hashlib.sha256(crop.tobytes()).hexdigest())
    assert len(run_hashes) >= 6


def test_xayah_imagegen_icons_vfx_splash_and_portrait_are_runtime_ready() -> None:
    icon_paths = [MOD / f"icons/xayah_{suffix}.png" for suffix in ("skill", "skill2", "ult")]
    assert all(Image.open(path).size == (64, 64) for path in icon_paths)
    assert len({hashlib.sha256(path.read_bytes()).hexdigest() for path in icon_paths}) == 3

    expected_tags = {
        "xayah_attack": {"projectile": 4, "hit": 4},
        "xayah_q": {"projectile": 4, "hit": 4},
        "xayah_e": {
            "return_single": 4,
            "return_double": 4,
            "return_cluster": 4,
            "root": 4,
            "hit": 4,
            "anchor": 1,
        },
        "xayah_r": {"fan": 4, "hit": 4, "guard": 4},
        "xayah_ground_feather": {"ground_single": 4, "ground_fan": 4},
    }
    expected_frame_sizes = {
        "xayah_e": {
            "return_single": (64, 32),
            "return_double": (72, 36),
            "return_cluster": (80, 44),
            "root": (72, 72),
            "hit": (48, 48),
            "anchor": (1, 1),
        },
        "xayah_r": {"fan": (104, 72), "hit": (96, 72), "guard": (72, 72)},
        "xayah_ground_feather": {
            "ground_single": (48, 40),
            "ground_fan": (72, 48),
        },
    }
    for name, tags in expected_tags.items():
        sheet = Image.open(MOD / f"aseprite_resources/effects/{name}#sheet.png").convert("RGBA")
        anims = load_json(f"aseprite_resources/effects/{name}#anim.fanim")["anims"]
        assert {tag: len(value["frames"]) for tag, value in anims.items()} == tags
        for tag, value in anims.items():
            if name in expected_frame_sizes:
                assert {
                    (frame["data"]["w"], frame["data"]["h"])
                    for frame in value["frames"]
                } == {expected_frame_sizes[name][tag]}
            for frame_index, frame in enumerate(value["frames"]):
                data = frame["data"]
                crop = sheet.crop((data["x"], data["y"], data["x"] + data["w"], data["y"] + data["h"]))
                bbox = crop.getchannel("A").getbbox()
                if (
                    name == "xayah_ground_feather"
                    and frame_index == len(value["frames"]) - 1
                ) or (name == "xayah_e" and tag == "anchor"):
                    assert bbox is None, (name, tag, "terminal frame must hide bounded-TTL ghosts")
                else:
                    assert bbox is not None, (name, tag, frame_index)

    builder = (MOD / "tools/build_xayah.py").read_text(encoding="utf-8")
    assert 'IDLE_BODY_SOURCE = PROCESSED_ROOT / "xayah_idle_contact_v3_alpha.png"' in builder
    assert 'IDLE_BODY_SOURCE = PROCESSED_ROOT / "xayah_idle_contact_v2_alpha.png"' not in builder
    assert 'xayah_q_vfx_contact_v2_alpha.png' in builder
    assert 'xayah_e_vfx_contact_v3_alpha.png' in builder
    assert "crop_top_half_tags" not in builder
    assert Image.open(MOD / "BanPickIllust/dancer.png").size == (1420, 860)
    portrait = Image.open(MOD / "ui/champion_fullbody/dancer.png").convert("RGBA")
    assert portrait.size == (64, 64) and portrait.getchannel("A").getbbox() is not None
    compact = Image.open(MOD / "ui/champion_portrait/dancer_compact.png").convert("RGBA")
    grid = Image.open(MOD / "ui/champion_portrait/dancer_grid.png").convert("RGBA")
    assert compact.size == (64, 64)
    assert grid.size == (90, 122)
    compact_bbox = compact.getchannel("A").getbbox()
    grid_bbox = grid.getchannel("A").getbbox()
    assert compact_bbox is not None
    assert compact_bbox[2] - compact_bbox[0] <= 50
    assert compact_bbox[3] - compact_bbox[1] <= 50
    assert min(compact_bbox[0], compact_bbox[1], 64 - compact_bbox[2], 64 - compact_bbox[3]) >= 6
    assert grid_bbox is not None and grid_bbox[1] <= 8 and grid_bbox[3] <= 86
    assert compact.getchannel("A").getextrema() == (0, 255)
    assert grid.getchannel("A").getextrema() == (0, 255)
    assert (MOD / "qa/xayah_portrait_surface_final.png").is_file()

    provenance = load_json("qa/xayah_imagegen_sources.json")
    assert len(provenance["sources"]) == 16
    assert len(provenance["processed"]) == 12
    assert all("xayah_idle_contact_v2" not in row["path"] for row in provenance["sources"])
    assert all("xayah_idle_contact_v2" not in row["path"] for row in provenance["processed"])
    assert provenance["additional_generated_images"] == [
        {
            "role": "idle_body_contact_v3_two_eyes",
            "execution_id": "exec-14c8a307-6e2b-4821-859a-9f62c5e391ef",
        },
        {
            "role": "ground_feather_vfx_v1",
            "execution_id": "exec-178182ff-7735-4228-b339-62352f37295c",
        },
    ]
    active_idle = next(row for row in provenance["processed"] if row["role"] == "idle_body_contact_v3_alpha_two_eyes")
    assert active_idle["path"] == "source/processed/xayah_idle_contact_v3_alpha.png"


def test_xayah_actor_is_uniformly_about_fourteen_percent_larger_with_foot_clearance() -> None:
    qa = load_json("qa/xayah_ui_scale_qa.json")
    actor = qa["actor_scale"]
    assert 1.12 <= actor["mean_height_scale_ratio"] <= 1.15
    assert 1.12 <= actor["median_height_scale_ratio"] <= 1.16
    assert actor["minimum_bottom_clearance"] >= 4
    assert "no x-only compression" in actor["policy"]
    assert actor["q_e_r_sources"] == {
        "Q": "source/processed/xayah_q_body_contact_v2_alpha.png",
        "E": "source/processed/xayah_e_body_contact_v2_alpha.png",
        "R": "source/processed/xayah_r_body_contact_v2_alpha.png",
    }
    assert set(actor["actions"]) == {"idle", "run", "attack", "hit", "skill1", "skill2", "ult"}
    assert all(
        row["bottom_clearance"] >= 4
        and row["visible_size"][0] <= row["native_rect"][0]
        and row["visible_size"][1] <= row["native_rect"][1]
        for rows in actor["actions"].values()
        for row in rows
    )
    assert qa["accepted_idle_and_portrait_source"].endswith("xayah_idle_contact_v3_alpha.png")
    assert qa["bp_geometry"]["side_card_stable"] == [81, 141]
    assert qa["bp_geometry"]["center_grid_native_geometry"] == [54, 94]


def test_xayah_v3_compact_and_grid_portraits_are_source_direct_and_name_safe() -> None:
    builder = (MOD / "tools/build_xayah.py").read_text(encoding="utf-8")
    assert 'IDLE_BODY_SOURCE = PROCESSED_ROOT / "xayah_idle_contact_v3_alpha.png"' in builder
    assert 'IDLE_BODY_SOURCE = PROCESSED_ROOT / "xayah_idle_contact_v2_alpha.png"' not in builder
    assert not (MOD / "source/imagegen/xayah_idle_contact_v2.png").exists()
    assert not (MOD / "source/processed/xayah_idle_contact_v2_alpha.png").exists()

    compact = Image.open(MOD / "ui/champion_portrait/dancer_compact.png").convert("RGBA")
    grid = Image.open(MOD / "ui/champion_portrait/dancer_grid.png").convert("RGBA")
    compact_bbox = compact.getchannel("A").getbbox()
    grid_bbox = grid.getchannel("A").getbbox()
    assert compact.size == (64, 64) and compact_bbox is not None
    assert compact_bbox[2] - compact_bbox[0] <= 50
    assert compact_bbox[3] - compact_bbox[1] <= 50
    assert min(compact_bbox[0], compact_bbox[1], 64 - compact_bbox[2], 64 - compact_bbox[3]) >= 6
    assert grid.size == (90, 122) and grid_bbox is not None
    assert grid_bbox[3] <= 86

    provenance = load_json("qa/xayah_imagegen_sources.json")
    assert len(provenance["sources"]) == 16
    assert len(provenance["processed"]) == 12
    assert all("xayah_idle_contact_v2" not in row["path"] for row in provenance["sources"])
    assert all("xayah_idle_contact_v2" not in row["path"] for row in provenance["processed"])
    assert provenance["additional_generated_images"][0]["execution_id"] == (
        "exec-14c8a307-6e2b-4821-859a-9f62c5e391ef"
    )


def test_xayah_official_audio_is_pinned_mono_pcm16_and_full_volume() -> None:
    audit = load_json("qa/xayah_official_audio_sources.json")
    assert audit["source_wad"]["sha256"] == "58a4f5cf7ba3ec2ef525d41c8c017a1f255d11ea8f2c82d05ed0a20c16df069e"
    assert len(audit["outputs"]) == 10
    assert {row["event_key"] for row in audit["outputs"]} == {
        "xayah_attack_cast", "xayah_attack_hit", "xayah_q_cast", "xayah_q_hit",
        "xayah_e_cast", "xayah_e_launch", "xayah_e_hit", "xayah_e_catch",
        "xayah_e_root", "xayah_r_cast",
    }
    for row in audit["outputs"]:
        assert row["volume"] == 1.0
        assert row["media_id"] in row["event_media_pool"]
        wav_path = MOD / row["wav"]["path"]
        assert hashlib.sha256(wav_path.read_bytes()).hexdigest() == row["wav"]["sha256"]
        with wave.open(str(wav_path), "rb") as decoded:
            assert (decoded.getnchannels(), decoded.getsampwidth(), decoded.getframerate(), decoded.getcomptype()) == (1, 2, 44100, "NONE")
        info = load_json(row["sound_info"])
        assert info["plays"] == [{"delay": 0.0, "clip": row["clip"], "volume": 1.0}]

    silence = MOD / "sound/sfx/xayah_native_silence_clip.wav"
    with wave.open(str(silence), "rb") as decoded:
        assert decoded.readframes(decoded.getnframes()).strip(b"\0") == b""


def test_xayah_runtime_bp_fullbody_builder_and_manifest_wiring() -> None:
    runtime = (MOD / "src/lib.rs").read_text(encoding="utf-8")
    assert 'const SPLASH_SPECS: [(&str, &str); 9]' in runtime
    assert '("dancer", "asset/lol_mod/BanPickIllust/dancer")' in runtime
    assert '("dancer", "lol_fullbody_xayah")' in " ".join(runtime.split())
    assert '"xayah" | "dancer" => Some("dancer")' in runtime
    assert "rewrite_xayah_portrait_render_commands(state);" in runtime
    assert "XAYAH_COMPACT_PORTRAIT_TEXTURE" in runtime
    assert "XAYAH_BP_GRID_PORTRAIT_TEXTURE" in runtime
    builder = (MOD / "tools/build_lol_mod.py").read_text(encoding="utf-8")
    assert 'from build_xayah import build_all as build_xayah_assets' in builder
    assert '"dancer": ACTOR_DIR / "xayah#sheet.png"' in builder
    installer = (MOD / "tools/install_lol_mod.ps1").read_text(encoding="utf-8")
    assert "manifest-owned file" in installer
    assert "Copy-Item -LiteralPath $source -Destination $installed -Force" in installer

    manifest = load_json("build_manifest.json")
    manifest_paths = {row["path"] for row in manifest["files"]}
    required = {
        "champion/dancer.data_champion",
        "aseprite_resources/champions/xayah#sheet.png",
        "aseprite_resources/champions/xayah#anim.fanim",
        "icons/xayah_skill.png", "icons/xayah_skill2.png", "icons/xayah_ult.png",
        "BanPickIllust/dancer.png", "ui/champion_fullbody/dancer.png",
        "ui/champion_portrait/dancer_compact.png", "ui/champion_portrait/dancer_grid.png",
        "qa/xayah_ui_scale_qa.json", "qa/xayah_portrait_surface_final.png",
        "qa/xayah_imagegen_sources.json", "qa/xayah_official_audio_sources.json",
    }
    for name in ("xayah_attack", "xayah_q", "xayah_e", "xayah_r", "xayah_ground_feather"):
        required.update({f"aseprite_resources/effects/{name}#sheet.png", f"aseprite_resources/effects/{name}#anim.fanim"})
    assert required <= manifest_paths
