from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MOD = ROOT / "mods" / "lol_mod"


def load_yone() -> dict:
    return json.loads(
        (MOD / "champion/dual_blader.data_champion").read_text(encoding="utf-8")
    )


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


def test_yone_replaces_official_009_once_and_exposes_only_q_w_r() -> None:
    champions = [
        (path.name, json.loads(path.read_text(encoding="utf-8")))
        for path in sorted((MOD / "champion").glob("*.data_champion"))
    ]
    assert [name for name, champion in champions if champion.get("id") == "dual_blader"] == [
        "dual_blader.data_champion"
    ]
    assert all(champion.get("id") != "lol_yone" for _, champion in champions)
    assert not (MOD / "champion/lol_yone.data_champion").exists()

    yone = load_yone()
    assert yone["id"] == "dual_blader"
    assert yone["category"] == "Assassin"
    assert set(yone["tags"]) == {"AD", "Melee", "CC"}
    assert yone["sprite"] == "asset/lol_mod/aseprite_resources/champions/yone"
    assert yone["skill_icons"] == [
        "asset/lol_mod/icons/yone_skill",
        "asset/lol_mod/icons/yone_skill2",
        "asset/lol_mod/icons/yone_ult",
    ]
    assert [yone[slot]["action_name"] for slot in ("attack", "skill", "skill2", "ult")] == [
        "attack",
        "skill",
        "skill2",
        "ult",
    ]
    assert not {"skill3", "skill4", "e"}.intersection(yone)


def test_yone_stats_and_alternating_basic_attacks_match_the_contract() -> None:
    yone = load_yone()
    assert yone["stat"] == {
        "attack": 110,
        "magic_power": 0,
        "hp": 900,
        "defence": 25,
        "magic_resistance": 15,
        "move_speed": 1100,
        "hp_regen": 2,
        "stack": 0,
        "crit_chance": 0,
    }
    assert yone["growth"] == {
        "attack": 20,
        "magic_power": 0,
        "hp": 100,
        "defence": 7,
        "magic_resistance": 3,
        "move_speed": 10,
        "hp_regen": 1,
        "stack": 0,
        "crit_chance": 0,
    }
    attack = yone["attack"]
    assert (attack["cooltime"], attack["range"]) == (50, 25000)
    assert attack["effect"]["type"] == "SwitchByBuff"
    assert attack["effect"]["buff_name"] == "lol_yone_azakana_ready"
    assert [(hit["damage"], hit["attack_ratio"]) for hit in find_effect(attack, "Attack")] == [
        (0, 100),
        (0, 100),
    ]
    assert len(find_effect(attack["effect"]["effect_none"], "AddCasterBuff")) == 1
    assert len(find_effect(attack["effect"]["effect_buff"], "RemoveCasterBuff")) == 1
    assert {
        effect["name"] for effect in find_effect(attack, "ViewEffect")
    } == {"lol_yone_attack_steel_hit", "lol_yone_attack_azakana_hit"}


def test_q_is_hit_gated_two_stage_and_empowered_dash_cannot_double_damage() -> None:
    q = load_yone()["skill"]
    assert (
        q["action_name"],
        q["cooltime"],
        q["duration"],
        q["start_timing"],
        q["range"],
        q["casting_type"],
        q["casting_target"],
    ) == ("skill", 240, 30, 8, 65000, "Direction", "EnemyChampion")

    switch = q["effect"]
    assert switch["type"] == "SwitchByBuff"
    assert switch["buff_name"] == "lol_yone_gathering_storm"

    normal = switch["effect_none"]
    normal_projectiles = find_effect(normal, "LinearProjectile", name="lol_yone_q_projectile")
    assert len(normal_projectiles) == 1
    normal_projectile = normal_projectiles[0]
    assert (
        normal_projectile["penetrate"],
        normal_projectile["speed"],
        normal_projectile["range"],
        normal_projectile["shape"],
        normal_projectile["applied_target"],
    ) == (True, 8000, 60000, {"Circle": {"radius": 8000}}, "EnemyWithoutTower")
    assert [(hit["damage"], hit["attack_ratio"]) for hit in find_effect(normal, "Attack")] == [
        (25, 80)
    ]
    assert not find_effect(normal, "Airborne")
    assert not find_effect(normal, "RemoveCasterBuff", name="lol_yone_gathering_storm")
    normal_buffs = find_effect(normal_projectile, "AddCasterBuff")
    assert len(normal_buffs) == 1
    assert set(normal_buffs[0]) == {"type", "buff_state"}
    assert normal_buffs[0]["buff_state"] == {
        "name": "lol_yone_gathering_storm",
        "duration": {"Time": {"tick": 360}},
    }
    # The state application is nested in the projectile hit payload, not at cast time.
    assert not [effect for effect in normal["effects"] if effect.get("type") == "AddCasterBuff"]

    empowered = switch["effect_buff"]
    assert empowered["effects"][0] == {
        "type": "RemoveCasterBuff",
        "name": "lol_yone_gathering_storm",
    }
    rushes = find_effect(empowered, "RushTime")
    assert rushes == [
        {
            "type": "RushTime",
            "speed": 4000,
            "tick": 8,
            "range": 0,
            "casting_target": "None",
            "penetrate": True,
            "applied_effects": [],
        }
    ]
    empowered_projectiles = find_effect(
        empowered, "LinearProjectile", name="lol_yone_q_empowered_projectile"
    )
    assert len(empowered_projectiles) == 1
    empowered_projectile = empowered_projectiles[0]
    assert (
        empowered_projectile["penetrate"],
        empowered_projectile["range"],
        empowered_projectile["shape"],
    ) == (True, 65000, {"Circle": {"radius": 9000}})
    assert [(hit["damage"], hit["attack_ratio"]) for hit in find_effect(empowered, "Attack")] == [
        (25, 80)
    ]
    assert [cc["duration"] for cc in find_effect(empowered, "Airborne")] == [45]
    assert not find_effect(q, "Native")
    assert not find_effect(q, "Delayed")


def test_w_targets_enemy_champions_and_keeps_one_hit_knockup_and_self_shield() -> None:
    w = load_yone()["skill2"]
    assert (
        w["action_name"],
        w["cooltime"],
        w["duration"],
        w["start_timing"],
        w["range"],
        w["casting_type"],
        w["casting_target"],
    ) == ("skill2", 480, 36, 4, 90000, "Targeting", "EnemyChampion")
    rushes = find_effect(w, "RushMoveToBack")
    assert len(rushes) == 1
    rush = rushes[0]
    assert rush["speed"] == 5000
    assert [(hit["damage"], hit["attack_ratio"]) for hit in find_effect(rush, "Attack")] == [
        (45, 90)
    ]
    assert [cc["duration"] for cc in find_effect(rush, "Airborne")] == [45]
    shields = find_effect(rush, "Shield")
    assert shields == [
        {
            "type": "Shield",
            "amount": 90,
            "attack_ratio": 30,
            "ap_ratio": 0,
            "tick": 90,
        }
    ]
    assert len(find_effect(rush, "WithSelf")) == 1
    assert len(find_effect(w, "ViewEffect", name="lol_yone_w_lock")) == 1
    assert len(find_effect(w, "CasterViewEffect", name="lol_yone_w_dash_visual")) == 1
    assert len(find_effect(rush, "ViewEffect", name="lol_yone_w_cross")) == 1
    assert len(find_effect(rush, "ViewEffect", name="lol_yone_w_airborne")) == 1
    assert len(find_effect(rush, "CasterViewEffect", name="lol_yone_w_guard")) == 1
    assert {
        effect["name"]
        for effect in walk_effects(w)
        if effect.get("type") in {"ViewEffect", "CasterViewEffect"}
    } == {
        "lol_yone_w_lock",
        "lol_yone_w_dash_visual",
        "lol_yone_w_cross",
        "lol_yone_w_airborne",
        "lol_yone_w_guard",
    }
    assert not find_effect(w, "Delayed")
    assert not find_effect(w, "Native")
    assert w["start_timing"] + ((w["range"] + rush["speed"] - 1) // rush["speed"]) < w["duration"]


def test_yone_w_uses_stock_ai_without_unsafe_target_revalidation() -> None:
    source = (MOD / "src/lib.rs").read_text(encoding="utf-8")
    for retired_token in (
        "struct YoneWInputGate",
        "impl ModPlayerInputAi for YoneWInputGate",
        '"lol_yone_w_input_gate"',
        "registration.add_player_input_ai(YoneWInputGate);",
        "let sealed_pursuit = Input::Skill2 { target };",
        "ctx.is_valid_input(&sealed_pursuit)",
    ):
        assert retired_token not in source


def test_r_has_one_knockup_six_physical_slashes_and_one_fixed_echo() -> None:
    r = load_yone()["ult"]
    assert (
        r["action_name"],
        r["cooltime"],
        r["duration"],
        r["start_timing"],
        r["range"],
        r["casting_type"],
        r["casting_target"],
    ) == ("ult", 3000, 96, 4, 40000, "Targeting", "EnemyChampion")
    rushes = find_effect(r, "RushMoveToBack")
    assert len(rushes) == 1
    rush = rushes[0]
    assert rush["speed"] == 5000
    assert [cc["duration"] for cc in find_effect(rush, "Airborne")] == [60]
    assert not find_effect(rush, "Stun")

    delayed = [effect for effect in rush["applied_effects"] if effect.get("type") == "Delayed"]
    assert [effect["tick"] for effect in delayed] == [8, 16, 24, 32, 40, 48, 60]
    for index, effect in enumerate(delayed[:6]):
        assert [(hit["damage"], hit["attack_ratio"]) for hit in find_effect(effect, "Attack")] == [
            (12, 16)
        ]
        assert not find_effect(effect, "FixedAttack")
        expected_view = "lol_yone_r_slash_blue" if index % 2 == 0 else "lol_yone_r_slash_red"
        assert [view["name"] for view in find_effect(effect, "ViewEffect")] == [expected_view]
    assert not find_effect(delayed[-1], "Attack")
    assert [(hit["damage"], hit["attack_ratio"]) for hit in find_effect(delayed[-1], "FixedAttack")] == [
        (30, 25)
    ]
    assert len(find_effect(r, "Attack")) == 6
    assert len(find_effect(r, "FixedAttack")) == 1
    for forbidden in ("Native", "RandomTarget", "AutoTargetProjectile", "RangeEffect"):
        assert not find_effect(r, forbidden)
    max_travel = (r["range"] + rush["speed"] - 1) // rush["speed"]
    assert r["start_timing"] + max_travel + max(effect["tick"] for effect in delayed) < r["duration"]


def test_yone_effect_and_audio_names_are_distinct_and_data_only() -> None:
    yone = load_yone()
    assert not find_effect({slot: yone[slot] for slot in ("attack", "skill", "skill2", "ult")}, "Native")

    projectiles = {view["name"]: view for view in yone["view_projectiles"]}
    assert set(projectiles) == {"lol_yone_q_projectile", "lol_yone_q_empowered_projectile"}
    views = {view["name"]: view for view in yone["view_effects"]}
    assert set(views) == {
        "lol_yone_attack_steel_hit",
        "lol_yone_attack_azakana_hit",
        "lol_yone_q_hit",
        "lol_yone_q_empowered_hit",
        "lol_yone_w_lock",
        "lol_yone_w_dash_visual",
        "lol_yone_w_cross",
        "lol_yone_w_airborne",
        "lol_yone_w_guard",
        "lol_yone_r_windup",
        "lol_yone_r_arrival",
        "lol_yone_r_slash_blue",
        "lol_yone_r_slash_red",
        "lol_yone_r_echo",
    }
    assert {
        name: (views[name]["tag"], views[name]["z"])
        for name in (
            "lol_yone_w_lock",
            "lol_yone_w_dash_visual",
            "lol_yone_w_cross",
            "lol_yone_w_airborne",
            "lol_yone_w_guard",
        )
    } == {
        "lol_yone_w_lock": ("lock", 1),
        "lol_yone_w_dash_visual": ("dash", 1),
        "lol_yone_w_cross": ("cross", 2),
        "lol_yone_w_airborne": ("airborne", 2),
        "lol_yone_w_guard": ("guard", 2),
    }
    assert all(
        views[name]["anim"]
        == "asset/lol_mod/aseprite_resources/effects/yone_followup"
        for name in (
            "lol_yone_w_lock",
            "lol_yone_w_dash_visual",
            "lol_yone_w_cross",
            "lol_yone_w_airborne",
            "lol_yone_w_guard",
        )
    )
    used_view_names = {
        effect["name"]
        for slot in ("attack", "skill", "skill2", "ult")
        for effect in walk_effects(yone[slot])
        if effect.get("type") in {"ViewEffect", "CasterViewEffect", "LinearProjectile"}
    }
    assert used_view_names == set(projectiles) | set(views)

    used_audio = {
        effect["name"]
        for slot in ("attack", "skill", "skill2", "ult")
        for effect in walk_effects(yone[slot])
        if effect.get("type") in {"Sfx", "TargetSfx"}
    }
    assert used_audio == {
        "lol_yone_attack_steel_cast",
        "lol_yone_attack_azakana_cast",
        "lol_yone_attack_steel_hit",
        "lol_yone_attack_azakana_hit",
        "lol_yone_q_cast",
        "lol_yone_q_hit",
        "lol_yone_q_empowered_cast",
        "lol_yone_q_empowered_hit",
        "lol_yone_w_cast",
        "lol_yone_w_hit",
        "lol_yone_w_shield",
        "lol_yone_r_cast",
        "lol_yone_r_arrival",
        "lol_yone_r_slash_steel",
        "lol_yone_r_slash_azakana",
        "lol_yone_r_echo",
    }


def test_yone_safety_qa_records_target_death_and_no_native_gates() -> None:
    qa = (MOD / "qa/yone_skill_contract_qa.md").read_text(encoding="utf-8")
    assert "start 4 + travel 8 + delayed 60 = 72 < duration 96" in qa
    assert "零 `Native`" in qa
    assert "目标死亡" in qa
    assert "50–100" in qa
    assert "17:49:58.857" in qa
    assert "YoneWInputGate" in qa
    assert "过期实体" in qa
    assert "原生 AI" in qa
