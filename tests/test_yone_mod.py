from __future__ import annotations

import hashlib
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


def test_yone_replaces_official_009_once_and_exposes_only_q_e_w_r_three_slots() -> None:
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


def test_q_is_hit_gated_three_stage_and_q3_cannot_double_damage() -> None:
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

    stack2_switch = q["effect"]
    assert (stack2_switch["type"], stack2_switch["buff_name"]) == (
        "SwitchByBuff",
        "lol_yone_mortal_steel_stack_2",
    )
    stack1_switch = stack2_switch["effect_none"]
    assert (stack1_switch["type"], stack1_switch["buff_name"]) == (
        "SwitchByBuff",
        "lol_yone_mortal_steel_stack_1",
    )

    q1 = stack1_switch["effect_none"]
    q2 = stack1_switch["effect_buff"]
    for stage in (q1, q2):
        projectiles = find_effect(stage, "LinearProjectile", name="lol_yone_q_projectile")
        assert len(projectiles) == 1
        projectile = projectiles[0]
        assert (
            projectile["penetrate"],
            projectile["speed"],
            projectile["range"],
            projectile["shape"],
            projectile["applied_target"],
        ) == (True, 8000, 60000, {"Circle": {"radius": 8000}}, "EnemyWithoutTower")
        assert [(hit["damage"], hit["attack_ratio"]) for hit in find_effect(projectile, "Attack")] == [
            (25, 80)
        ]
        assert not find_effect(stage, "Airborne")

    q1_hit_guards = find_effect(
        q1, "SwitchByBuff", buff_name="lol_yone_mortal_steel_stack_1"
    )
    assert q1_hit_guards == [
        {
            "type": "SwitchByBuff",
            "buff_name": "lol_yone_mortal_steel_stack_1",
            "effect_none": {
                "type": "AddCasterBuff",
                "buff_state": {
                    "name": "lol_yone_mortal_steel_stack_1",
                    "duration": {"Time": {"tick": 360}},
                },
            },
            "effect_buff": {"type": "Combine", "effects": []},
        }
    ]
    assert not find_effect(q1, "RemoveCasterBuff")
    q2_hit_guards = find_effect(
        q2, "SwitchByBuff", buff_name="lol_yone_mortal_steel_stack_2"
    )
    assert q2_hit_guards == [
        {
            "type": "SwitchByBuff",
            "buff_name": "lol_yone_mortal_steel_stack_2",
            "effect_none": {
                "type": "Combine",
                "effects": [
                    {"type": "RemoveCasterBuff", "name": "lol_yone_mortal_steel_stack_1"},
                    {
                        "type": "AddCasterBuff",
                        "buff_state": {
                            "name": "lol_yone_mortal_steel_stack_2",
                            "duration": {"Time": {"tick": 360}},
                        },
                    },
                ],
            },
            "effect_buff": {"type": "Combine", "effects": []},
        }
    ]
    # Both named stages are earned only inside a successful projectile hit payload,
    # and each penetrating projectile has an inner same-state guard so later
    # targets cannot execute the transition again.
    for stage in (q1, q2):
        assert not [effect for effect in stage["effects"] if effect.get("type") == "AddCasterBuff"]

    q3 = stack2_switch["effect_buff"]
    assert q3["effects"][0] == {
        "type": "RemoveCasterBuff",
        "name": "lol_yone_mortal_steel_stack_2",
    }
    rushes = find_effect(q3, "RushTime")
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
    q3_projectiles = find_effect(q3, "LinearProjectile", name="lol_yone_q_empowered_projectile")
    assert len(q3_projectiles) == 1
    empowered_projectile = q3_projectiles[0]
    assert (
        empowered_projectile["penetrate"],
        empowered_projectile["range"],
        empowered_projectile["shape"],
    ) == (True, 65000, {"Circle": {"radius": 9000}})
    assert [(hit["damage"], hit["attack_ratio"]) for hit in find_effect(q3, "Attack")] == [
        (25, 80)
    ]
    assert [cc["duration"] for cc in find_effect(q3, "Airborne")] == [45]
    assert find_effect(q3, "ViewEffect", name="lol_yone_q3_airborne_cue") == [
        {"type": "ViewEffect", "name": "lol_yone_q3_airborne_cue"}
    ]
    assert not find_effect(q, "Native")
    assert not find_effect(q, "Delayed")


def test_skill2_splits_w_damage_from_champion_only_shield_counting() -> None:
    skill2 = load_yone()["skill2"]
    assert (
        skill2["action_name"],
        skill2["cooltime"],
        skill2["duration"],
        skill2["start_timing"],
        skill2["range"],
        skill2["casting_type"],
        skill2["casting_target"],
    ) == ("skill2", 720, 42, 4, 48000, "Targeting", "EnemyChampion")

    assert find_effect(skill2, "CasterAnimation") == [
        {"type": "CasterAnimation", "name": "skill2_attack", "tick": 42}
    ]
    actor_anims = json.loads(
        (MOD / "aseprite_resources/champions/yone#anim.fanim").read_text(encoding="utf-8")
    )["anims"]
    assert len(actor_anims["skill2_attack"]["frames"]) == 5
    assert len(actor_anims["skill2"]["frames"]) == 1
    visual_contract = json.loads(
        (MOD / "qa/yone_visual_contract.json").read_text(encoding="utf-8")
    )
    assert visual_contract["runtime_body_actions"]["skill2"] == {
        "animation_tag": "skill2_attack",
        "frame_count": 5,
        "qa_contact_tag": "skill2_attack",
    }
    assert visual_contract["runtime_w_resolution"] == {
        "shared_geometry": {"width": 42000, "length": 48000, "delay": 0, "apply": 1},
        "damage_hitbox": {
            "name": "lol_yone_w_sweep_hitbox",
            "applied_target": "EnemyWithoutTower",
            "attack_count": 1,
            "hit_sfx_count": 1,
        },
        "champion_shield_probe": {
            "name": "lol_yone_w_champion_shield_probe",
            "applied_target": "EnemyChampion",
            "attack_count": 0,
            "shield_tiers": 2,
        },
    }

    for forbidden in ("RushMoveToBack", "Rush", "RushTime", "Airborne", "Knockback"):
        assert not find_effect(skill2, forbidden)

    outbound = find_effect(skill2, "LinearProjectile", name="lol_yone_e_spirit_outbound")
    assert len(outbound) == 1
    assert (
        outbound[0]["penetrate"], outbound[0]["speed"], outbound[0]["range"],
        outbound[0]["shape"], outbound[0]["applied_target"], outbound[0]["applied_effects"],
    ) == (True, 6500, 70000, {"Circle": {"radius": 7000}}, "EnemyWithoutTower", [])
    returns = find_effect(outbound[0], "BackToCasterLinearProjectile", name="lol_yone_e_spirit_return")
    assert len(returns) == 1
    assert (
        returns[0]["penetrate"], returns[0]["speed"], returns[0]["range"],
        returns[0]["shape"], returns[0]["applied_target"], returns[0]["applied_effects"],
    ) == (True, 9000, 110000, {"Circle": {"radius": 7000}}, "EnemyWithoutTower", [])
    assert not find_effect(outbound[0], "Attack")
    assert find_effect(returns[0], "CasterViewEffect", name="lol_yone_e_return_burst")

    line_ranges = find_effect(skill2, "LineRangeProjectile")
    assert [hitbox["name"] for hitbox in line_ranges] == [
        "lol_yone_w_sweep_hitbox",
        "lol_yone_w_champion_shield_probe",
    ]
    damage_hitbox, shield_probe = line_ranges
    for hitbox in line_ranges:
        assert (hitbox["width"], hitbox["length"], hitbox["delay"], hitbox["apply"]) == (
            42000, 48000, 0, 1
        )
        assert skill2["range"] == hitbox["length"]

    assert damage_hitbox["applied_target"] == "EnemyWithoutTower"
    assert [(hit["damage"], hit["attack_ratio"]) for hit in find_effect(damage_hitbox, "Attack")] == [
        (45, 90)
    ]
    assert find_effect(damage_hitbox, "TargetSfx") == [
        {"type": "TargetSfx", "name": "lol_yone_w_hit"}
    ]
    assert not find_effect(damage_hitbox, "Shield")
    assert not find_effect(damage_hitbox, "AddCasterBuff")
    assert not find_effect(damage_hitbox, "CasterViewEffect")

    assert shield_probe["applied_target"] == "EnemyChampion"
    assert not find_effect(shield_probe, "Attack")
    assert not find_effect(shield_probe, "TargetSfx")
    shields = find_effect(shield_probe, "Shield")
    assert shields == [
        {"type": "Shield", "amount": 70, "attack_ratio": 20, "ap_ratio": 0, "tick": 90},
        {"type": "Shield", "amount": 35, "attack_ratio": 10, "ap_ratio": 0, "tick": 90},
    ]
    assert len(find_effect(shield_probe, "WithSelf")) == 2
    assert len(find_effect(skill2, "Attack")) == 1
    assert {
        effect["name"]
        for effect in walk_effects(skill2)
        if effect.get("type") in {"ViewEffect", "CasterViewEffect"}
    } == {
        "lol_yone_e_body_anchor",
        "lol_yone_e_return_burst",
        "lol_yone_w_crescent",
        "lol_yone_w_shield_visual",
    }
    assert [effect["name"] for effect in skill2["effect"]["effects"][:2]] == [
        "lol_yone_w_shield_hit_1", "lol_yone_w_shield_hit_2"
    ]
    assert {
        buff["buff_state"]["name"] for buff in find_effect(shield_probe, "AddCasterBuff")
    } == {"lol_yone_w_shield_hit_1", "lol_yone_w_shield_hit_2"}
    assert not find_effect(skill2, "Delayed")
    assert not find_effect(skill2, "Native")


def test_yone_e_w_combo_uses_stock_ai_without_unsafe_target_revalidation() -> None:
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
    assert set(projectiles) == {
        "lol_yone_q_projectile",
        "lol_yone_q_empowered_projectile",
        "lol_yone_e_spirit_outbound",
        "lol_yone_e_spirit_return",
    }
    views = {view["name"]: view for view in yone["view_effects"]}
    assert set(views) == {
        "lol_yone_attack_steel_hit",
        "lol_yone_attack_azakana_hit",
        "lol_yone_q_hit",
        "lol_yone_q_empowered_hit",
        "lol_yone_q3_airborne_cue",
        "lol_yone_e_body_anchor",
        "lol_yone_e_return_burst",
        "lol_yone_w_crescent",
        "lol_yone_w_shield_visual",
        "lol_yone_r_windup",
        "lol_yone_r_arrival",
        "lol_yone_r_slash_blue",
        "lol_yone_r_slash_red",
        "lol_yone_r_echo",
    }
    assert {
        name: (views[name]["tag"], views[name]["z"])
        for name in (
            "lol_yone_q3_airborne_cue",
            "lol_yone_e_body_anchor",
            "lol_yone_e_return_burst",
            "lol_yone_w_crescent",
            "lol_yone_w_shield_visual",
        )
    } == {
        "lol_yone_q3_airborne_cue": ("cue", 2),
        "lol_yone_e_body_anchor": ("anchor", 0),
        "lol_yone_e_return_burst": ("return_burst", 2),
        "lol_yone_w_crescent": ("crescent", 2),
        "lol_yone_w_shield_visual": ("shield", 2),
    }
    assert views["lol_yone_q3_airborne_cue"]["anim"].endswith("/yone_q3_airborne")
    assert views["lol_yone_e_body_anchor"]["anim"].endswith("/yone_spirit")
    assert views["lol_yone_e_return_burst"]["anim"].endswith("/yone_spirit")
    assert views["lol_yone_w_crescent"]["anim"].endswith("/yone_w")
    assert views["lol_yone_w_shield_visual"]["anim"].endswith("/yone_followup")
    used_view_names = {
        effect["name"]
        for slot in ("attack", "skill", "skill2", "ult")
        for effect in walk_effects(yone[slot])
        if effect.get("type")
        in {"ViewEffect", "CasterViewEffect", "LinearProjectile", "BackToCasterLinearProjectile"}
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


def test_yone_skill_qa_records_three_stage_q_and_documented_e_w_approximation() -> None:
    qa = (MOD / "qa/yone_skill_contract_qa.md").read_text(encoding="utf-8")
    assert "Q1 → Q2 → Q3" in qa
    assert "lol_yone_mortal_steel_stack_1" in qa
    assert "lol_yone_mortal_steel_stack_2" in qa
    assert "内层 `SwitchByBuff`" in qa
    assert "BackToCasterLinearProjectile" in qa
    assert "真实英雄坐标不会被伪造回溯" in qa
    assert "W 月牙" in qa
    assert "lol_yone_w_sweep_hitbox" in qa
    assert "lol_yone_w_champion_shield_probe" in qa
    assert "EnemyWithoutTower" in qa
    assert "EnemyChampion" in qa
    assert "48000" in qa
    assert "skill2_attack" in qa
    assert "无击飞" in qa
    assert "YoneWInputGate" in qa
    assert "ctx.is_valid_input" in qa


def test_yone_runtime_provenance_matches_final_lf_files() -> None:
    audit = json.loads(
        (MOD / "qa/yone_imagegen_sources.json").read_text(encoding="utf-8")
    )
    rows = audit["runtime"]
    assert len({row["path"] for row in rows}) == len(rows)
    for row in rows:
        path = MOD / row["path"]
        assert path.is_file(), row["path"]
        payload = path.read_bytes()
        assert row["size_bytes"] == len(payload), row["path"]
        assert row["sha256"] == hashlib.sha256(payload).hexdigest(), row["path"]
        if path.suffix == ".fanim":
            assert b"\r" not in payload, row["path"]
