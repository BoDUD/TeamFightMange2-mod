from __future__ import annotations

import ast
import hashlib
import json
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


def test_yone_replaces_official_dual_blader_and_uses_q_w_r_slots() -> None:
    champions = [
        (path.name, json.loads(path.read_text(encoding="utf-8")))
        for path in sorted((MOD / "champion").glob("*.data_champion"))
    ]
    assert [
        name for name, champion in champions if champion.get("id") == "dual_blader"
    ] == ["dual_blader.data_champion"]
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
    assert [
        yone[slot]["action_name"] for slot in ("attack", "skill", "skill2", "ult")
    ] == ["attack", "skill", "skill2", "ult"]
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
    assert [
        (hit["damage"], hit["attack_ratio"])
        for hit in find_effect(attack, "Attack")
    ] == [(0, 100), (0, 100)]
    assert len(find_effect(attack["effect"]["effect_none"], "AddCasterBuff")) == 1
    assert len(find_effect(attack["effect"]["effect_buff"], "RemoveCasterBuff")) == 1
    assert {
        effect["name"] for effect in find_effect(attack, "ViewEffect")
    } == {"lol_yone_attack_steel_hit", "lol_yone_attack_azakana_hit"}


def test_soul_unbound_is_not_referenced_or_registered() -> None:
    champion_text = (
        MOD / "champion/dual_blader.data_champion"
    ).read_text(encoding="utf-8")
    assert "lol_yone_e_" not in champion_text
    assert "Soul Unbound" not in champion_text

    rust = (MOD / "src/lib.rs").read_text(encoding="utf-8")
    for retired in (
        "lol_yone_e_",
        "YONE_SOUL_UNBOUND",
        "YoneSoulUnboundStartNativeEffect",
        "YoneSoulUnboundBeginReturnNativeEffect",
        "YoneSoulUnboundDamagePreNativeEffect",
        "YoneSoulUnboundDamagePostNativeEffect",
        "YoneSoulUnboundSettleNativeEffect",
        "YoneSoulUnboundInputGate",
    ):
        assert retired not in rust

    for retired_path in (
        "aseprite_resources/effects/yone_spirit#anim.fanim",
        "aseprite_resources/effects/yone_spirit#sheet.png",
        "aseprite_resources/effects/yone_q3_airborne#anim.fanim",
        "aseprite_resources/effects/yone_q3_airborne#sheet.png",
        "aseprite_resources/effects/yone_followup#anim.fanim",
        "aseprite_resources/effects/yone_followup#sheet.png",
        "source/imagegen/yone_e_icon_source.png",
        "source/imagegen/yone_followup_vfx_contact.png",
        "source/processed/yone_followup_vfx_contact_alpha.png",
    ):
        assert not (MOD / retired_path).exists()


def test_w_uses_one_target_set_and_one_tiered_shield_settle() -> None:
    w = load_yone()["skill2"]
    assert (
        w["cooltime"],
        w["duration"],
        w["start_timing"],
        w["range"],
        w["casting_type"],
        w["casting_target"],
    ) == (480, 30, 8, 42000, "Direction", "EnemyWithoutTower")

    assert find_effect(w, "CasterAnimation") == [
        {"type": "CasterAnimation", "name": "skill2_attack", "tick": 30}
    ]
    hitboxes = find_effect(
        w, "LineRangeProjectile", name="lol_yone_w_hitbox"
    )
    assert len(hitboxes) == 1
    hitbox = hitboxes[0]
    assert (
        hitbox["width"],
        hitbox["length"],
        hitbox["delay"],
        hitbox["apply"],
        hitbox["applied_target"],
    ) == (
        36000,
        42000,
        0,
        1,
        "EnemyWithoutTower",
    )
    payload = hitbox["applied_effects"]
    assert len(payload) == 1
    ordered = payload[0]["effect"]["effects"]
    assert [effect["type"] for effect in ordered] == [
        "Native",
        "Attack",
        "ViewEffect",
        "TargetSfx",
    ]
    assert ordered[0] == {
        "type": "Native",
        "effect_ref": "lol_yone_w_collect_hit_native",
    }
    assert ordered[1] == {"type": "Attack", "damage": 50, "attack_ratio": 90}

    delayed = find_effect(w, "Delayed")
    assert len(delayed) == 1
    assert delayed[0]["tick"] == 2
    settle = delayed[0]["effects"]
    assert settle[0] == {
        "type": "Native",
        "effect_ref": "lol_yone_w_settle_native",
    }
    tiers = [
        (0, 50, 20),
        (1, 100, 40),
        (2, 125, 50),
        (3, 150, 60),
        (4, 175, 70),
        (5, 200, 80),
    ]
    assert len(settle[1:]) == 6
    for switch, (tier, amount, attack_ratio) in zip(settle[1:], tiers, strict=True):
        marker = f"lol_yone_w_shield_tier_{tier}"
        assert switch["type"] == "SwitchByBuff"
        assert switch["buff_name"] == marker
        assert switch["effect_none"] == {"type": "Combine", "effects": []}
        branch = switch["effect_buff"]["effects"]
        assert branch[0] == {
            "type": "WithSelf",
            "effects": [
                {
                    "type": "Shield",
                    "amount": amount,
                    "attack_ratio": attack_ratio,
                    "ap_ratio": 0,
                    "tick": 90,
                }
            ],
        }
        assert branch[1] == {"type": "RemoveCasterBuff", "name": marker}
        assert branch[2:] == [
            {"type": "CasterViewEffect", "name": "lol_yone_w_shield"},
            {"type": "Sfx", "name": "lol_yone_w_shield"},
        ]

    assert len(find_effect(w, "Shield")) == 6
    assert [effect["effect_ref"] for effect in find_effect(w, "Native")] == [
        "lol_yone_w_begin_native",
        "lol_yone_w_collect_hit_native",
        "lol_yone_w_settle_native",
    ]
    forbidden = {
        "Rush",
        "RushTime",
        "RushMoveToBack",
        "Teleport",
        "BackToCasterLinearProjectile",
        "AddCasterBuffWithCasterTarget",
    }
    assert not {effect["type"] for effect in walk_effects(w)}.intersection(forbidden)
    assert find_effect(
        w, "CasterViewEffect", name="lol_yone_w_crescent_cast"
    ) == [{"type": "CasterViewEffect", "name": "lol_yone_w_crescent_cast"}]
    assert not find_effect(w, "LinearProjectile")

    rust = (MOD / "src/lib.rs").read_text(encoding="utf-8")
    for proof in (
        "YoneSpiritCleaveBeginNativeEffect",
        "YoneSpiritCleaveCollectHitNativeEffect",
        "YoneSpiritCleaveSettleNativeEffect",
        "YONE_W_MAX_ENEMY_CHAMPIONS: usize = 5",
        "hit.target_id == target_id && hit.target == target",
        ".min(YONE_W_MAX_ENEMY_CHAMPIONS)",
    ):
        assert proof in rust


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
        projectiles = find_effect(
            stage, "LinearProjectile", name="lol_yone_q_projectile"
        )
        assert len(projectiles) == 1
        projectile = projectiles[0]
        assert (
            projectile["penetrate"],
            projectile["speed"],
            projectile["range"],
            projectile["shape"],
            projectile["applied_target"],
        ) == (
            True,
            8000,
            60000,
            {"Circle": {"radius": 8000}},
            "EnemyWithoutTower",
        )
        assert [
            (hit["damage"], hit["attack_ratio"])
            for hit in find_effect(projectile, "Attack")
        ] == [(25, 80)]
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
                    {
                        "type": "RemoveCasterBuff",
                        "name": "lol_yone_mortal_steel_stack_1",
                    },
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
    # The stack transitions exist only inside successful projectile-hit payloads.
    # Their same-state guards prevent later penetrated targets from transitioning
    # the caster a second time during the same cast.
    for stage in (q1, q2):
        assert not [
            effect
            for effect in stage["effects"]
            if effect.get("type") == "AddCasterBuff"
        ]

    ready_wind = {
        view["name"]: view for view in load_yone().get("view_buffs", [])
    }["lol_yone_mortal_steel_stack_2"]
    assert ready_wind["type"] == "ThreePhase"
    assert ready_wind["anim"].endswith("/yone_q3_ready_wind")
    assert set(ready_wind) >= {
        "type",
        "name",
        "anim",
        "pre_tag",
        "loop_tag",
        "remove_tag",
        "z",
    }

    q3 = stack2_switch["effect_buff"]
    assert q3["effects"][0] == {
        "type": "RemoveCasterBuff",
        "name": "lol_yone_mortal_steel_stack_2",
    }
    assert find_effect(q3, "RushTime") == [
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
    projectiles = find_effect(
        q3, "LinearProjectile", name="lol_yone_q_empowered_projectile"
    )
    assert len(projectiles) == 1
    empowered_projectile = projectiles[0]
    assert (
        empowered_projectile["penetrate"],
        empowered_projectile["range"],
        empowered_projectile["shape"],
    ) == (True, 65000, {"Circle": {"radius": 9000}})
    assert [
        (hit["damage"], hit["attack_ratio"])
        for hit in find_effect(q3, "Attack")
    ] == [(25, 80)]
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

    delayed = [
        effect
        for effect in rush["applied_effects"]
        if effect.get("type") == "Delayed"
    ]
    assert [effect["tick"] for effect in delayed] == [8, 16, 24, 32, 40, 48, 60]
    for index, effect in enumerate(delayed[:6]):
        assert [
            (hit["damage"], hit["attack_ratio"])
            for hit in find_effect(effect, "Attack")
        ] == [(12, 16)]
        assert not find_effect(effect, "FixedAttack")
        expected_view = (
            "lol_yone_r_slash_blue" if index % 2 == 0 else "lol_yone_r_slash_red"
        )
        assert [
            view["name"] for view in find_effect(effect, "ViewEffect")
        ] == [expected_view]
    assert not find_effect(delayed[-1], "Attack")
    assert [
        (hit["damage"], hit["attack_ratio"])
        for hit in find_effect(delayed[-1], "FixedAttack")
    ] == [(30, 25)]
    assert len(find_effect(r, "Attack")) == 6
    assert len(find_effect(r, "FixedAttack")) == 1
    assert not find_effect(r, "Native")
    for forbidden in ("RandomTarget", "AutoTargetProjectile", "RangeEffect"):
        assert not find_effect(r, forbidden)
    max_travel = (r["range"] + rush["speed"] - 1) // rush["speed"]
    assert (
        r["start_timing"]
        + max_travel
        + max(effect["tick"] for effect in delayed)
        < r["duration"]
    )


def test_yone_effect_and_audio_names_cover_active_w_and_contain_no_e_assets() -> None:
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
        "lol_yone_w_crescent_cast",
        "lol_yone_w_hit",
        "lol_yone_w_shield",
        "lol_yone_r_windup",
        "lol_yone_r_arrival",
        "lol_yone_r_slash_blue",
        "lol_yone_r_slash_red",
        "lol_yone_r_echo",
    }
    assert required_views == set(views)
    assert not any("lol_yone_e_" in name.lower() for name in views)
    assert {
        name: (views[name]["tag"], views[name]["z"])
        for name in (
            "lol_yone_q3_airborne_cue",
            "lol_yone_w_crescent_cast",
            "lol_yone_w_hit",
            "lol_yone_w_shield",
        )
    } == {
        "lol_yone_q3_airborne_cue": ("cue", 2),
        "lol_yone_w_crescent_cast": ("crescent", 3),
        "lol_yone_w_hit": ("impact", 2),
        "lol_yone_w_shield": ("shield", 2),
    }
    assert views["lol_yone_q3_airborne_cue"]["anim"].endswith(
        "/yone_q3_tornado"
    )
    assert all(
        views[name]["anim"].endswith("/yone_w")
        for name in (
            "lol_yone_w_crescent_cast",
            "lol_yone_w_hit",
            "lol_yone_w_shield",
        )
    )
    view_buffs = {view["name"]: view for view in yone["view_buffs"]}
    assert set(view_buffs) == {"lol_yone_mortal_steel_stack_2"}
    assert view_buffs["lol_yone_mortal_steel_stack_2"]["anim"].endswith(
        "/yone_q3_ready_wind"
    )

    used_view_names = {
        effect["name"]
        for slot in ("attack", "skill", "skill2", "ult")
        for effect in walk_effects(yone[slot])
        if effect.get("type")
        in {
            "ViewEffect",
            "CasterViewEffect",
            "LinearProjectile",
            "BackToCasterLinearProjectile",
        }
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
        "lol_yone_w_cast",
        "lol_yone_w_hit",
        "lol_yone_w_shield",
        "lol_yone_r_cast",
        "lol_yone_r_arrival",
        "lol_yone_r_slash_steel",
        "lol_yone_r_slash_azakana",
        "lol_yone_r_echo",
    }
    assert used_audio == required_audio
    assert {
        effect["name"]
        for effect in walk_effects(yone["skill2"])
        if effect.get("type") in {"Sfx", "TargetSfx"}
    } == {"lol_yone_w_cast", "lol_yone_w_hit", "lol_yone_w_shield"}
    assert not any("lol_yone_e_" in name.lower() for name in used_audio)

    w_audio = ("lol_yone_w_cast", "lol_yone_w_hit", "lol_yone_w_shield")
    for name in w_audio:
        assert (MOD / f"sound/sfx/{name}.sound_info").is_file()
        assert (MOD / f"sound/sfx/{name}_clip.wav").is_file()
    assert not any(
        "lol_yone_e_" in path.name.lower()
        for path in (MOD / "sound/sfx").glob("lol_yone_*")
    )

    overrides = json.loads(
        (MOD / "mod.override_info").read_text(encoding="utf-8")
    )
    for name in w_audio:
        for suffix in ("", "_clip"):
            asset = f"{name}{suffix}"
            key = f"asset/base/sound/sfx/{asset}"
            assert overrides[key] == {
                "remapping": f"asset/lol_mod/sound/sfx/{asset}",
                "type": "override",
            }
    assert not any("lol_yone_e_" in key.lower() for key in overrides)

    extractor = (MOD / "tools/extract_yone_audio.py").read_text(encoding="utf-8")
    for name in w_audio:
        assert f'"{name}"' in extractor
    assert "lol_yone_e_" not in extractor


def test_w_runtime_visuals_are_compact_and_have_separate_shield_tag() -> None:
    yone = load_yone()
    projectiles = {row["name"]: row for row in yone["view_projectiles"]}
    effects = {row["name"]: row for row in yone["view_effects"]}
    assert "lol_yone_w_sweep_projectile" not in projectiles
    assert effects["lol_yone_w_crescent_cast"] == {
        "type": "Animation",
        "name": "lol_yone_w_crescent_cast",
        "anim": "asset/lol_mod/aseprite_resources/effects/yone_w",
        "tag": "crescent",
        "z": 3,
        "is_follow": True,
    }
    assert effects["lol_yone_w_hit"]["tag"] == "impact"
    assert effects["lol_yone_w_shield"]["tag"] == "shield"
    assert effects["lol_yone_w_shield"]["z"] == 2

    anim = json.loads(
        (MOD / "aseprite_resources/effects/yone_w#anim.fanim").read_text(
            encoding="utf-8"
        )
    )["anims"]
    assert list(anim) == ["crescent", "impact", "shield"]
    assert len(anim["crescent"]["frames"]) == 6
    assert len(anim["impact"]["frames"]) == 4
    assert len(anim["shield"]["frames"]) == 6
    assert {
        (frame["data"]["w"], frame["data"]["h"])
        for frame in anim["crescent"]["frames"]
    } == {(96, 56)}
    assert {
        (frame["data"]["w"], frame["data"]["h"])
        for frame in anim["shield"]["frames"]
    } == {(44, 44)}


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
                or (
                    max(red, green, blue) - min(red, green, blue) <= 38
                    and blue >= 150
                )
            )
        )
        red_dominant = sum(
            1
            for red, _green, blue, _alpha in visible
            if red >= 100 and red > blue * 1.25
        )
        assert blue_white / len(visible) >= 0.70, relative
        assert red_dominant / len(visible) <= 0.03, relative


def test_yone_actor_contract_and_portraits_remain_native_safe() -> None:
    actor_anim = json.loads(
        (MOD / "aseprite_resources/champions/yone#anim.fanim").read_text(
            encoding="utf-8"
        )
    )["anims"]
    assert "skill2_attack" in actor_anim
    assert len(actor_anim["skill2_attack"]["frames"]) == 5
    assert Image.open(MOD / "aseprite_resources/champions/yone#sheet.png").size == (
        3502,
        88,
    )
    portrait_dir = MOD / "ui/champion_portrait"
    assert Image.open(portrait_dir / "dual_blader_compact.png").size == (64, 64)
    assert Image.open(portrait_dir / "dual_blader_scoreboard.png").size == (48, 64)
    grid = Image.open(portrait_dir / "dual_blader_grid.png").convert("RGBA")
    assert grid.size == (90, 122)
    assert grid.getchannel("A").getbbox()[3] <= 86


def test_localized_copy_describes_w_and_removes_soul_unbound() -> None:
    payload = json.loads(
        (MOD / "text/champion.i18n").read_text(encoding="utf-8")
    )
    for locale in ("en", "zh-hans", "zh-hant", "ja", "ko"):
        skill2 = payload[locale]["description"]["dual_blader"]["skill2"]
        assert skill2.startswith("W")
        assert "E—" not in skill2 and "E —" not in skill2
        assert "Soul Unbound" not in skill2
        assert "灵体" not in skill2 and "靈體" not in skill2


def test_visual_qa_records_the_w_fallback_contract() -> None:
    contract = json.loads(
        (MOD / "qa/yone_visual_contract.json").read_text(encoding="utf-8")
    )
    assert "runtime_e_resolution" not in contract
    assert contract["runtime_w_resolution"] == {
        "action_duration_ticks": 30,
        "cooldown_ticks": 480,
        "movement": "none",
        "shape": "one stationary caster-following crescent plus one instant 36000x42000 forward hitbox",
        "damage": "50 + 90% Attack physical damage",
        "shield": "one unified settle grants a 90-tick 50 + 20% Attack shield after any enemy hit, then scales through every enemy champion hit up to the normal five-champion team limit",
    }
    runtime = contract["runtime_effect_map"]
    assert runtime["lol_yone_w_crescent_cast"] == ["yone_w", "crescent"]
    assert runtime["lol_yone_w_hit"] == ["yone_w", "impact"]
    assert runtime["lol_yone_w_shield"] == ["yone_w", "shield"]
    assert not any(name.startswith("lol_yone_e_") for name in runtime)
    faces = contract["face_readability"]["all_battle_body_frames"]
    assert len(faces) == 54
    assert all(
        row["dark_feature_pixels"] == 2
        and row["dark_feature_adjacent_pair"]
        and row["warm_pixels"] >= 2
        and row["near_white_pixels"] == 0
        for row in faces.values()
    )


def test_generated_qa_contact_labels_second_slot_as_w() -> None:
    source = (MOD / "tools/build_yone.py").read_text(encoding="utf-8")
    assert '("W", ICON_DIR / "yone_skill2.png")' in source
    assert "icon_sources = [cells[0], cells[1], cells[2]]" in source


def test_w_actor_sequence_is_planted_and_does_not_reuse_retired_e_lunges() -> None:
    source = (MOD / "tools/build_yone.py").read_text(encoding="utf-8")
    body_sequences = source.split("body_sequences:", 1)[1]
    sequence = body_sequences.split('"skill2_attack": [', 1)[1].split('"ult":', 1)[0]
    assert "wr[9]" in sequence
    assert "wr[8]" in sequence
    assert "wr[17]" in sequence
    assert "wr[4]" in sequence
    assert "wr[1]" not in sequence
    assert "wr[11]" not in sequence


def test_yone_w_release_docs_version_and_manifest_are_atomic() -> None:
    mod_info = json.loads((MOD / "mod.mod_info").read_text(encoding="utf-8"))
    assert mod_info["version"] == "0.10.3"
    assert "Q/W/R" in mod_info["description"]
    assert "E-only Soul Unbound" not in mod_info["description"]

    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "v0.10.3" in readme
    assert "skill2=W 凛神斩" in readme
    assert "54个可见战斗身体帧" in readme

    manifest = json.loads(
        (MOD / "build_manifest.json").read_text(encoding="utf-8")
    )
    paths = {row["path"] for row in manifest["files"]}
    assert {
        "aseprite_resources/effects/yone_w#anim.fanim",
        "aseprite_resources/effects/yone_w#sheet.png",
        "sound/sfx/lol_yone_w_cast.sound_info",
        "sound/sfx/lol_yone_w_hit.sound_info",
        "sound/sfx/lol_yone_w_shield.sound_info",
    } <= paths
    assert not {
        "aseprite_resources/effects/yone_spirit#anim.fanim",
        "aseprite_resources/effects/yone_spirit#sheet.png",
        "aseprite_resources/effects/yone_q3_airborne#anim.fanim",
        "aseprite_resources/effects/yone_q3_airborne#sheet.png",
        "aseprite_resources/effects/yone_followup#anim.fanim",
        "aseprite_resources/effects/yone_followup#sheet.png",
        "source/imagegen/yone_e_icon_source.png",
        "source/imagegen/yone_followup_vfx_contact.png",
        "source/processed/yone_followup_vfx_contact_alpha.png",
    }.intersection(paths)


def test_yone_manifest_uses_explicit_builder_outputs_and_fails_closed() -> None:
    source = (MOD / "tools/build_lol_mod.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    manifest_builder = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "build_manifest"
    )
    assert [argument.arg for argument in manifest_builder.args.args] == [
        "yone_outputs"
    ]

    declared_assignment = next(
        node
        for node in manifest_builder.body
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Name) and target.id == "declared_yone_paths"
            for target in node.targets
        )
    )
    assert any(
        isinstance(node, ast.SetComp)
        and any(
            isinstance(name, ast.Name) and name.id == "yone_outputs"
            for name in ast.walk(node)
        )
        for node in ast.walk(declared_assignment.value)
    )

    manifest_source = ast.get_source_segment(source, manifest_builder)
    assert manifest_source is not None
    for pinned_path in (
        "champion/dual_blader.data_champion",
        "qa/yone_official_audio_sources.json",
        "sound/sfx/yone_native_silence.sound_info",
        "sound/sfx/yone_native_silence_clip.wav",
    ):
        assert pinned_path in manifest_source
    assert 'yone_audio_audit.get("outputs", [])' in manifest_source
    assert 'for record_key in ("sound_info", "wav")' in manifest_source
    assert "declared_yone_paths.add(relative)" in manifest_source

    release_path_predicate = next(
        node
        for node in manifest_builder.body
        if isinstance(node, ast.FunctionDef)
        and node.name == "is_yone_release_path"
    )
    predicate_constants = {
        node.value
        for node in ast.walk(release_path_predicate)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    }
    assert {"yone", "dual_blader"} <= predicate_constants

    undeclared_assignment = next(
        node
        for node in manifest_builder.body
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Name) and target.id == "undeclared_yone_paths"
            for target in node.targets
        )
    )
    undeclared_names = {
        node.id
        for node in ast.walk(undeclared_assignment.value)
        if isinstance(node, ast.Name)
    }
    assert {
        "files",
        "is_yone_release_path",
        "declared_yone_paths",
    } <= undeclared_names
    fail_closed_guard = next(
        node
        for node in manifest_builder.body
        if isinstance(node, ast.If)
        and isinstance(node.test, ast.Name)
        and node.test.id == "undeclared_yone_paths"
    )
    assert any(isinstance(node, ast.Raise) for node in fail_closed_guard.body)
    assert "Undeclared Yone files would enter the release manifest" in ast.get_source_segment(
        source, fail_closed_guard
    )

    assert any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "build_manifest"
        and len(node.args) == 1
        and isinstance(node.args[0], ast.Name)
        and node.args[0].id == "yone_outputs"
        for node in ast.walk(tree)
    )


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
