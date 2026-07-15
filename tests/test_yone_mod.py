from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from pathlib import Path

from PIL import Image


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


def estimated_skill_panel_lines(text: str) -> int:
    """Conservative wrap estimate for the native 624x95 skill row.

    The icon, level/cooldown column, separator, and margins consume roughly
    112px, leaving 512px for description text.  The row has room for four
    23px lines.  This deliberately estimates wide CJK glyphs at 18px and
    wraps Latin text on words so CI catches the overlap seen in-game.
    """

    content_width = 624 - 112

    def glyph_width(char: str) -> int:
        if char.isspace():
            return 5
        if unicodedata.east_asian_width(char) in {"W", "F"}:
            return 18
        if unicodedata.east_asian_width(char) == "A":
            return 16
        return 9

    lines = 0
    for paragraph in text.splitlines() or [""]:
        line_width = 0
        for token in re.findall(r"\S+|\s+", paragraph):
            if token.isspace():
                if line_width:
                    line_width += glyph_width(" ")
                continue
            token_width = sum(glyph_width(char) for char in token)
            if line_width and line_width + token_width > content_width:
                lines += 1
                line_width = 0
            for char in token:
                width = glyph_width(char)
                if line_width and line_width + width > content_width:
                    lines += 1
                    line_width = 0
                line_width += width
        lines += 1
    return lines


def assert_yone_damage_payloads_are_e_tracked(root: dict) -> int:
    damage_types = {"Attack", "FixedAttack", "ApAttack"}
    damage_effects = [
        effect for effect in walk_effects(root) if effect.get("type") in damage_types
    ]
    wrapped_effect_ids: set[int] = set()

    def visit(value) -> None:
        if isinstance(value, list):
            for index, child in enumerate(value):
                if isinstance(child, dict) and child.get("type") in damage_types:
                    assert index > 0 and index + 1 < len(value)
                    assert value[index - 1] == {
                        "type": "Native",
                        "effect_ref": "lol_yone_e_damage_pre_native",
                    }
                    assert value[index + 1] == {
                        "type": "Native",
                        "effect_ref": "lol_yone_e_damage_post_native",
                    }
                    wrapped_effect_ids.add(id(child))
                visit(child)
        elif isinstance(value, dict):
            for child in value.values():
                visit(child)

    visit(root)
    assert len(wrapped_effect_ids) == len(damage_effects)
    return len(damage_effects)


def test_yone_replaces_official_009_once_and_exposes_only_q_e_r_three_slots() -> None:
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

    # The second hit-earned stack is also the persistent, visible Q3-ready wind
    # state.  It must not be granted on cast or on a miss.
    ready_wind = {
        view["name"]: view for view in load_yone().get("view_buffs", [])
    }["lol_yone_mortal_steel_stack_2"]
    assert ready_wind["type"] == "ThreePhase"
    assert ready_wind["anim"].endswith("/yone_q3_ready_wind")
    assert set(ready_wind) >= {
        "type", "name", "anim", "pre_tag", "loop_tag", "remove_tag", "z"
    }

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
    projectile_views = {
        view["name"]: view for view in load_yone()["view_projectiles"]
    }
    normal_wind = projectile_views["lol_yone_q_projectile"]
    q3_tornado = projectile_views["lol_yone_q_empowered_projectile"]
    assert q3_tornado["anim"].endswith("/yone_q3_tornado")
    assert q3_tornado["anim"] != normal_wind["anim"]
    assert q3_tornado["tag"] == "tornado"
    assert find_effect(q3, "ViewEffect", name="lol_yone_q3_airborne_cue") == [
        {"type": "ViewEffect", "name": "lol_yone_q3_airborne_cue"}
    ]
    assert not find_effect(q, "Delayed")


def test_skill2_uses_the_real_caster_as_a_free_spirit_with_one_lunge_and_bounded_return() -> None:
    skill2 = load_yone()["skill2"]
    assert (
        skill2["action_name"],
        skill2["cooltime"],
        skill2["duration"],
        skill2["start_timing"],
        skill2["range"],
        skill2["casting_type"],
        skill2["casting_target"],
    ) == ("skill2", 720, 24, 4, 60000, "Direction", "EnemyChampion")
    assert skill2["duration"] < 240
    assert 0 <= skill2["start_timing"] < skill2["duration"]

    assert find_effect(skill2, "CasterAnimation") == [
        {"type": "CasterAnimation", "name": "skill2_attack", "tick": 24}
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
    assert "runtime_w_resolution" not in visual_contract

    # The real caster becomes the controllable spirit.  Only the initial
    # direction lunge may move it at the data layer; no fake humanoid projectile
    # or second damage payload may stand in for a spirit entity.
    assert find_effect(skill2, "RushTime") == [
        {
            "type": "RushTime",
            "penetrate": True,
            "speed": 4500,
            "tick": 8,
            "range": 0,
            "casting_target": "None",
            "applied_effects": [],
        }
    ]
    for forbidden in (
        "RushMoveToBack", "Rush", "Teleport", "Airborne", "Knockback",
        "LineRangeProjectile", "LinearProjectile", "BackToCasterLinearProjectile",
        "Shield", "Attack", "FixedAttack", "ApAttack",
    ):
        assert not find_effect(skill2, forbidden)

    native_refs = [effect["effect_ref"] for effect in find_effect(skill2, "Native")]
    assert native_refs == [
        "lol_yone_e_start_native",
        "lol_yone_e_begin_return_native",
        "lol_yone_e_settle_native",
    ]

    top = skill2["effect"]
    assert top["type"] == "Combine"
    top_effects = top["effects"]
    start_index = next(
        index
        for index, effect in enumerate(top_effects)
        if effect == {"type": "Native", "effect_ref": "lol_yone_e_start_native"}
    )
    anchor_index = next(
        index
        for index, effect in enumerate(top_effects)
        if effect == {"type": "CasterViewEffect", "name": "lol_yone_e_body_anchor"}
    )
    rush_index = next(
        index
        for index, effect in enumerate(top_effects)
        if effect.get("type") == "RushTime"
    )
    delayed = [effect for effect in top_effects if effect.get("type") == "Delayed"]
    assert [effect["tick"] for effect in delayed] == [240, 300]
    assert start_index < anchor_index < rush_index < top_effects.index(delayed[0])

    assert find_effect(delayed[0], "Native") == [
        {"type": "Native", "effect_ref": "lol_yone_e_begin_return_native"}
    ]
    assert find_effect(delayed[0], "RemoveCasterBuff") == [
        {"type": "RemoveCasterBuff", "name": "lol_yone_e_spirit_form"}
    ]
    returning = [
        effect["buff_state"]
        for effect in find_effect(delayed[0], "AddCasterBuff")
        if effect["buff_state"]["name"] == "lol_yone_e_returning"
    ]
    assert returning == [
        {
            "name": "lol_yone_e_returning",
            "duration": {"Time": {"tick": 60}},
            "move_speed_mult": 300,
            "cc_immune": True,
        }
    ]
    assert find_effect(delayed[1], "Native") == [
        {"type": "Native", "effect_ref": "lol_yone_e_settle_native"}
    ]
    assert find_effect(delayed[1], "RemoveCasterBuff") == [
        {"type": "RemoveCasterBuff", "name": "lol_yone_e_returning"}
    ]
    assert find_effect(delayed[1], "CasterViewEffect") == [
        {"type": "CasterViewEffect", "name": "lol_yone_e_return_burst"}
    ]
    skill2_view_names = {
        effect["name"]
        for effect in walk_effects(skill2)
        if effect.get("type") in {"ViewEffect", "CasterViewEffect"}
    }
    assert {
        "lol_yone_e_body_anchor",
        "lol_yone_e_return_burst",
    } <= skill2_view_names
    assert all("yone_w" not in name.lower() for name in skill2_view_names)
    payload = json.dumps(skill2, ensure_ascii=False).lower()
    for forbidden_token in (
        "yone_w", "crescent", "shield", "sweep_hitbox",
        "lol_yone_e_spirit_outbound", "lol_yone_e_spirit_return",
    ):
        assert forbidden_token not in payload


def test_yone_e_native_state_is_context_isolated_and_return_ai_is_bounded() -> None:
    source = (MOD / "src/lib.rs").read_text(encoding="utf-8")
    for effect_ref in (
        "lol_yone_e_start_native",
        "lol_yone_e_begin_return_native",
        "lol_yone_e_damage_pre_native",
        "lol_yone_e_damage_post_native",
        "lol_yone_e_settle_native",
    ):
        assert f'"{effect_ref}"' in source
    for retired_token in (
        "struct YoneWInputGate",
        "impl ModPlayerInputAi for YoneWInputGate",
        '"lol_yone_w_input_gate"',
        "registration.add_player_input_ai(YoneWInputGate);",
        "let sealed_pursuit = Input::Skill2 { target };",
        "ctx.is_valid_input(&sealed_pursuit)",
    ):
        assert retired_token not in source
    assert "struct YoneSoulUnboundReturnInputAi" in source
    assert "const YONE_SOUL_UNBOUND_RETURN_TICKS: usize = 60;" in source
    assert "registration.add_player_input_ai(YoneSoulUnboundReturnInputAi);" in source
    assert "YONE_SOUL_UNBOUND_SERVICE_ID" in source
    assert "ctx.query_service(" in source
    assert "ctx.register_service(" in source
    assert "context_token: usize" in source
    assert "last_tick_by_context: HashMap<usize, usize>" in source
    assert "fn prepare_for_tick(&mut self, context_token: usize, now: usize)" in source
    assert "state.context_token != context_token" in source
    assert "self.states.clear()" not in source


def test_every_real_yone_damage_payload_is_wrapped_for_the_e_damage_ledger() -> None:
    yone = load_yone()
    expected_damage_counts = {"attack": 2, "skill": 3, "ult": 7}
    for slot, expected_count in expected_damage_counts.items():
        assert assert_yone_damage_payloads_are_e_tracked(yone[slot]) == expected_count

    assert not find_effect(yone["skill2"], "Attack")
    assert not find_effect(yone["skill2"], "FixedAttack")
    assert not find_effect(yone["skill2"], "ApAttack")
    assert not find_effect(
        yone["skill2"], "Native", effect_ref="lol_yone_e_damage_pre_native"
    )
    assert not find_effect(
        yone["skill2"], "Native", effect_ref="lol_yone_e_damage_post_native"
    )


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
    for forbidden in ("RandomTarget", "AutoTargetProjectile", "RangeEffect"):
        assert not find_effect(r, forbidden)
    max_travel = (r["range"] + rush["speed"] - 1) // rush["speed"]
    assert r["start_timing"] + max_travel + max(effect["tick"] for effect in delayed) < r["duration"]


def test_yone_effect_and_audio_names_are_distinct_and_contain_no_retired_w_assets() -> None:
    yone = load_yone()

    projectiles = {view["name"]: view for view in yone["view_projectiles"]}
    assert set(projectiles) == {
        "lol_yone_q_projectile",
        "lol_yone_q_empowered_projectile",
    }
    views = {view["name"]: view for view in yone["view_effects"]}
    required_views = {
        "lol_yone_attack_steel_hit",
        "lol_yone_attack_azakana_hit",
        "lol_yone_q_hit",
        "lol_yone_q_empowered_hit",
        "lol_yone_q3_airborne_cue",
        "lol_yone_e_body_anchor",
        "lol_yone_e_return_burst",
        "lol_yone_r_windup",
        "lol_yone_r_arrival",
        "lol_yone_r_slash_blue",
        "lol_yone_r_slash_red",
        "lol_yone_r_echo",
    }
    assert required_views <= set(views)
    assert all("yone_w" not in name.lower() for name in views)
    assert {
        name: (views[name]["tag"], views[name]["z"])
        for name in (
            "lol_yone_q3_airborne_cue",
            "lol_yone_e_body_anchor",
            "lol_yone_e_return_burst",
        )
    } == {
        "lol_yone_q3_airborne_cue": ("cue", 2),
        "lol_yone_e_body_anchor": ("anchor", 1),
        "lol_yone_e_return_burst": ("return_burst", 2),
    }
    assert views["lol_yone_q3_airborne_cue"]["anim"].endswith("/yone_q3_tornado")
    assert views["lol_yone_e_body_anchor"]["anim"].endswith("/yone_spirit")
    assert views["lol_yone_e_return_burst"]["anim"].endswith("/yone_spirit")
    view_buffs = {view["name"]: view for view in yone["view_buffs"]}
    assert "lol_yone_mortal_steel_stack_2" in view_buffs
    assert all("yone_w" not in name.lower() for name in view_buffs)
    assert view_buffs["lol_yone_mortal_steel_stack_2"]["anim"].endswith(
        "/yone_q3_ready_wind"
    )
    assert {
        name: (
            view_buffs[name]["pre_tag"],
            view_buffs[name]["loop_tag"],
            view_buffs[name]["remove_tag"],
            view_buffs[name]["z"],
        )
        for name in ("lol_yone_e_spirit_form", "lol_yone_e_returning")
    } == {
        "lol_yone_e_spirit_form": (
            "spirit_pre", "spirit_loop", "spirit_remove", 2,
        ),
        "lol_yone_e_returning": (
            "return_pre", "return_loop", "return_remove", 2,
        ),
    }
    assert all(
        view_buffs[name]["anim"].endswith("/yone_spirit")
        for name in ("lol_yone_e_spirit_form", "lol_yone_e_returning")
    )
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
    required_audio = {
        "lol_yone_attack_steel_cast",
        "lol_yone_attack_azakana_cast",
        "lol_yone_attack_steel_hit",
        "lol_yone_attack_azakana_hit",
        "lol_yone_q_cast",
        "lol_yone_q_hit",
        "lol_yone_q_empowered_cast",
        "lol_yone_q_empowered_hit",
        "lol_yone_r_cast",
        "lol_yone_r_arrival",
        "lol_yone_r_slash_steel",
        "lol_yone_r_slash_azakana",
        "lol_yone_r_echo",
    }
    assert required_audio <= used_audio
    assert all("yone_w" not in name.lower() for name in used_audio)
    skill2_audio = {
        effect["name"]
        for effect in walk_effects(yone["skill2"])
        if effect.get("type") in {"Sfx", "TargetSfx"}
    }
    assert all(name.startswith("lol_yone_e_") for name in skill2_audio)


def test_yone_e_spirit_sheet_keeps_an_opaque_body_anchor_and_only_sparse_mobile_aura() -> None:
    anim_path = MOD / "aseprite_resources/effects/yone_spirit#anim.fanim"
    sheet_path = MOD / "aseprite_resources/effects/yone_spirit#sheet.png"
    anims = json.loads(anim_path.read_text(encoding="utf-8"))["anims"]
    assert set(anims) == {
        "anchor",
        "return_burst",
        "spirit_pre",
        "spirit_loop",
        "spirit_remove",
        "return_pre",
        "return_loop",
        "return_remove",
    }
    with Image.open(sheet_path) as opened:
        sheet = opened.convert("RGBA")

    def frame(tag: str, index: int) -> Image.Image:
        frames = anims[tag]["frames"]
        data = frames[index]["data"]
        return sheet.crop(
            (
                data["x"],
                data["y"],
                data["x"] + data["w"],
                data["y"] + data["h"],
            )
        )

    def flattened(image: Image.Image):
        return (
            image.get_flattened_data()
            if hasattr(image, "get_flattened_data")
            else image.getdata()
        )

    anchor_frames = anims["anchor"]["frames"]
    assert abs(sum(item["duration"] for item in anchor_frames) - 5.0) < 0.001
    for index in range(len(anchor_frames) - 1):
        alpha = list(flattened(frame("anchor", index).getchannel("A")))
        assert any(alpha)
        assert {value for value in alpha if value} == {255}
    assert frame("anchor", -1).getchannel("A").getbbox() is None

    anchor_visible = sum(
        value > 0
        for value in flattened(frame("anchor", 0).getchannel("A"))
    )
    for tag in ("spirit_pre", "spirit_loop", "return_pre", "return_loop"):
        for index, _item in enumerate(anims[tag]["frames"]):
            aura = frame(tag, index).getchannel("A")
            bbox = aura.getbbox()
            assert bbox is not None, (tag, index)
            visible = sum(value > 0 for value in flattened(aura))
            bbox_area = (bbox[2] - bbox[0]) * (bbox[3] - bbox[1])
            assert visible < anchor_visible * 0.58, (tag, index)
            assert visible < bbox_area * 0.48, (tag, index)

    for tag in ("spirit_remove", "return_remove", "return_burst"):
        assert frame(tag, -1).getchannel("A").getbbox() is None


def test_yone_q3_runtime_wind_sheets_are_transparent_blue_white_and_sparse() -> None:
    for relative in (
        "aseprite_resources/effects/yone_q3_tornado#sheet.png",
        "aseprite_resources/effects/yone_q3_ready_wind#sheet.png",
    ):
        with Image.open(MOD / relative) as opened:
            image = opened.convert("RGBA")
        pixels = list(image.getdata())
        visible = [(r, g, b, a) for r, g, b, a in pixels if a >= 64]
        assert visible, relative
        assert len(visible) < len(pixels) * 0.60, relative
        blue_white = sum(
            1
            for red, green, blue, _alpha in visible
            if (
                (blue >= red and blue >= 90)
                or (max(red, green, blue) - min(red, green, blue) <= 38 and blue >= 150)
            )
        )
        red_dominant = sum(
            1
            for red, _green, blue, _alpha in visible
            if red >= 100 and red > blue * 1.25
        )
        assert blue_white / len(visible) >= 0.70, relative
        assert red_dominant / len(visible) <= 0.03, relative


def test_yone_localized_skill_copy_fits_native_rows_and_never_exposes_w_or_api_notes() -> None:
    text = json.loads((MOD / "text/champion.i18n").read_text(encoding="utf-8"))
    assert set(text) == {"en", "zh-hans", "zh-hant", "ja", "ko"}

    internal_terms = (
        "backtocaster", "mod_api", "public data", "stock ai", "data-only",
        "data approximation", "composite approximation", "engine", "native", "tick",
        "公开数据", "公開資料", "原生ai", "原生 AI", "坐标", "座標",
        "公開データ", "標準ai", "データ版", "근사", "데이터 api", "기본 ai",
    )
    retired_w_terms = (
        "spirit cleave", "crescent", "shield", "凛神斩", "凜神斬", "月牙",
        "护盾", "護盾", "霊断刀", "三日月", "シールド", "영혼 가르기",
        "초승달", "보호막",
    )

    for locale, locale_data in text.items():
        yone_text = locale_data["description"]["dual_blader"]
        for slot in ("skill", "skill2", "ult"):
            description = yone_text[slot]
            assert "\n" not in description, (locale, slot)
            assert estimated_skill_panel_lines(description) <= 4, (
                locale, slot, estimated_skill_panel_lines(description), description
            )
            lowered = description.casefold()
            assert not any(term.casefold() in lowered for term in internal_terms), (
                locale, slot, description
            )
            assert not re.search(r"(?<![A-Za-z])API(?![A-Za-z])", description), (
                locale, slot, description
            )

        e_copy = yone_text["skill2"]
        assert not re.search(r"(?<![A-Za-z])W(?![A-Za-z])", e_copy), (locale, e_copy)
        assert "E+W" not in e_copy and "E + W" not in e_copy
        lowered_e = e_copy.casefold()
        assert not any(term.casefold() in lowered_e for term in retired_w_terms), (
            locale, e_copy
        )


def test_yone_skill_qa_records_hit_gated_q3_tornado_and_e_only_limits() -> None:
    qa = (MOD / "qa/yone_skill_contract_qa.md").read_text(encoding="utf-8")
    assert "Q1 → Q2 → Q3" in qa
    assert "lol_yone_mortal_steel_stack_1" in qa
    assert "lol_yone_mortal_steel_stack_2" in qa
    assert "命中后才" in qa
    assert "lol_yone_q3_ready_wind" in qa
    assert "lol_yone_q3_tornado" in qa
    assert "45 tick `Airborne`" in qa
    assert "BackToCasterLinearProjectile" not in qa
    assert "真实施法者" in qa
    assert "不透明本体" in qa
    assert "稀疏轮廓" in qa
    assert "60 tick" in qa
    assert "300 tick" in qa
    assert "GameCtx" in qa
    assert "不能直接写英雄坐标" in qa
    assert "E-only" in qa
    assert "恰好执行一次无伤害 `RushTime`" in qa
    for effect_ref in (
        "lol_yone_e_start_native",
        "lol_yone_e_begin_return_native",
        "lol_yone_e_damage_pre_native",
        "lol_yone_e_damage_post_native",
        "lol_yone_e_settle_native",
    ):
        assert effect_ref in qa
    assert "skill2_attack" in qa
    assert "624x95" in qa
    assert "最多 4 行" in qa
    for retired in (
        "E+W", "lol_yone_w_sweep_hitbox", "lol_yone_w_champion_shield_probe",
        "W 月牙", "护盾档位", "lol_yone_e_spirit_outbound",
        "lol_yone_e_spirit_return",
    ):
        assert retired not in qa


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
