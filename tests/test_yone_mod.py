from __future__ import annotations

import ast
import hashlib
import json
import re
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
MOD = ROOT / "mods" / "lol_mod"

LEGACY_SAVED_NATIVE_COMPATIBILITY_NAMES = {
    "lol_yone_e_start_native",
    "lol_yone_e_begin_return_native",
    "lol_yone_e_damage_pre_native",
    "lol_yone_e_damage_post_native",
    "lol_yone_e_settle_native",
    "lol_shen_shadow_dash_ai_hint_native",
    "lol_shen_shadow_dash_taunt_native",
}


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


def _python_function_source(source: str, name: str) -> str:
    tree = ast.parse(source)
    function = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == name
    )
    body = ast.get_source_segment(source, function)
    assert body is not None
    return body


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


def test_soul_unbound_is_absent_from_active_data_resources_and_manifest() -> None:
    champion_text = (
        MOD / "champion/dual_blader.data_champion"
    ).read_text(encoding="utf-8")
    assert "lol_yone_e_" not in champion_text
    assert "Soul Unbound" not in champion_text

    manifest = json.loads(
        (MOD / "build_manifest.json").read_text(encoding="utf-8")
    )
    manifest_paths = {row["path"].lower() for row in manifest["files"]}
    assert not any(
        "yone_e" in path or "yone_spirit" in path
        for path in manifest_paths
    )

    for runtime_root in (
        "aseprite_resources",
        "champion",
        "icons",
        "sound",
        "text",
        "ui",
    ):
        assert not any(
            "yone_e" in path.as_posix().lower()
            or "yone_spirit" in path.as_posix().lower()
            for path in (MOD / runtime_root).rglob("*")
        )

    rust = (MOD / "src/lib.rs").read_text(encoding="utf-8")
    for retired_runtime in (
        "YONE_SOUL_UNBOUND",
        "YoneSoulUnboundStartNativeEffect",
        "YoneSoulUnboundBeginReturnNativeEffect",
        "YoneSoulUnboundDamagePreNativeEffect",
        "YoneSoulUnboundDamagePostNativeEffect",
        "YoneSoulUnboundSettleNativeEffect",
        "YoneSoulUnboundInputGate",
    ):
        assert retired_runtime not in rust

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


def test_legacy_saved_native_compatibility_allowlist_is_exact_and_noop() -> None:
    rust = (MOD / "src/lib.rs").read_text(encoding="utf-8")
    discovered_names = set(
        re.findall(r"lol_(?:yone_e|shen_shadow_dash)[a-z0-9_]*", rust)
    )
    assert discovered_names == LEGACY_SAVED_NATIVE_COMPATIBILITY_NAMES
    assert all(rust.count(f'"{name}"') == 1 for name in discovered_names)

    registrations = dict(
        re.findall(
            r'registration\.add_native_effect\(\s*"([^"]+)",\s*'
            r"([A-Za-z0-9_]+),\s*\);",
            rust,
        )
    )
    assert {
        name: registrations.get(name)
        for name in LEGACY_SAVED_NATIVE_COMPATIBILITY_NAMES
    } == {
        name: "LegacySavedNativeCompatibilityEffect"
        for name in LEGACY_SAVED_NATIVE_COMPATIBILITY_NAMES
    }

    compatibility_impl = rust.split(
        "impl ModEffectType for LegacySavedNativeCompatibilityEffect", 1
    )[1].split("\nfn init", 1)[0]
    assert re.search(
        r"fn apply\([^)]*\) \{\}",
        compatibility_impl,
    )
    assert not any(
        token in compatibility_impl
        for token in ("ctx.", "add_buff", "Attack", "Shield", "Rush", "Teleport")
    )


def test_w_uses_one_stateless_native_cone_snapshot_and_one_tiered_shield() -> None:
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
    assert not find_effect(w, "LineRangeProjectile")
    assert not find_effect(w, "RangeProjectile")
    assert not find_effect(w, "Attack")
    assert not find_effect(w, "Delayed")
    top = w["effect"]["effects"]
    assert [effect["type"] for effect in top[:4]] == [
        "CasterAnimation",
        "Sfx",
        "CasterViewEffect",
        "Native",
    ]
    assert top[3] == {
        "type": "Native",
        "effect_ref": "lol_yone_w_cone_native",
    }
    settle = top[4:]
    tiers = [
        (0, 50, 20),
        (1, 100, 40),
        (2, 125, 50),
        (3, 150, 60),
        (4, 175, 70),
        (5, 200, 80),
    ]
    assert len(settle) == 6
    for switch, (tier, amount, attack_ratio) in zip(settle, tiers, strict=True):
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
            {"type": "CasterViewEffect", "name": "lol_yone_w_hit"},
            {"type": "CasterViewEffect", "name": "lol_yone_w_shield"},
            {"type": "Sfx", "name": "lol_yone_w_hit"},
            {"type": "Sfx", "name": "lol_yone_w_shield"},
        ]

    assert len(find_effect(w, "Shield")) == 6
    assert [effect["effect_ref"] for effect in find_effect(w, "Native")] == [
        "lol_yone_w_cone_native",
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
        "YoneSpiritCleaveConeNativeEffect",
        "const YONE_W_RANGE: i128 = 42_000;",
        "const YONE_W_COS_SQ_HALF_ANGLE: i128 = 586_824;",
        "const YONE_W_FLAT_DAMAGE: usize = 35;",
        "const YONE_W_ATTACK_RATIO_PERCENT: usize = 45;",
        "const YONE_W_TARGET_MAX_HP_PERCENT: usize = 6;",
        "YONE_W_MAX_ENEMY_CHAMPIONS: usize = 5",
        "for index in 0..ctx.entity_count()",
        "let Some(target) = ctx.entity_at(index)",
        ".saturating_mul(YONE_W_TARGET_MAX_HP_PERCENT)",
        "champion_hits += usize::from(target.is_champion());",
        "ctx.deal_damage(caster_id, target_id, damage, 0, AttackType::Skill);",
        "champion_hits.min(YONE_W_MAX_ENEMY_CHAMPIONS)",
    ):
        assert proof in rust


def test_w_runtime_is_stateless_and_cannot_cross_game_contexts() -> None:
    rust = (MOD / "src/lib.rs").read_text(encoding="utf-8")
    runtime = rust.split("const YONE_W_RANGE", 1)[1].split(
        "// Saved seasons embed their champion definitions.", 1
    )[0]

    for forbidden in (
        "query_service",
        "register_service",
        "ModService",
        "c_void",
        "context_token",
        "OnceLock",
        "Mutex",
        "static YONE_",
        "started_tick",
        "max_by_key",
        "EntityHandle",
    ):
        assert forbidden not in runtime

    for proof in (
        "InputTarget::Dir { dir_x, dir_y }",
        "InputTarget::Pos { x, y }",
        "InputTarget::Target { target_id }",
        "for index in 0..ctx.entity_count()",
        "target.team() == caster_team",
        "!target.is_targetable()",
        "target.is_tower()",
        "dot * dot * YONE_W_COS_SQ_SCALE",
        "distance_sq * dir_sq * YONE_W_COS_SQ_HALF_ANGLE",
        "hits.push((target_id, damage));",
        "for (target_id, damage) in hits",
        "ctx.add_buff(caster_id, marker);",
    ):
        assert proof in runtime

    # The immutable entity scan completes before combat mutation and the one
    # shield marker is derived from that same local vector. There is no state
    # for a hidden simulation or second GameCtx to observe.
    assert runtime.index("hits.push((target_id, damage));") < runtime.index(
        "for (target_id, damage) in hits"
    )
    assert runtime.count("ctx.add_buff(caster_id, marker);") == 1

    registrations = dict(
        re.findall(
            r'registration\.add_native_effect\(\s*"([^"]+)",\s*'
            r"([A-Za-z0-9_]+),\s*\);",
            rust,
        )
    )
    assert registrations["lol_yone_w_cone_native"] == (
        "YoneSpiritCleaveConeNativeEffect"
    )
    for legacy_name in (
        "lol_yone_w_begin_native",
        "lol_yone_w_collect_hit_native",
        "lol_yone_w_settle_native",
    ):
        assert registrations[legacy_name] == "LegacySavedNativeCompatibilityEffect"


def test_broad_legacy_extensions_require_an_explicit_env_value_of_one() -> None:
    rust = (MOD / "src/lib.rs").read_text(encoding="utf-8")
    assert "const LEGACY_INTERNAL_EXTENSIONS_ENV: &str =" in rust
    init = rust.split("fn init(_ctx: &GameCtx) -> ModRegistration", 1)[1].split(
        "declare_mod!(init);", 1
    )[0]
    guard = re.search(
        r"if\s+std::env::var\(LEGACY_INTERNAL_EXTENSIONS_ENV\)"
        r"\s*\.is_ok_and\(\|value\| value == \"1\"\)\s*\{"
        r"(?P<body>.*?)\n    \}",
        init,
        flags=re.DOTALL,
    )
    assert guard is not None
    guard_body = guard.group("body")
    assert "registration.set_extension(LolModExtension);" in guard_body
    assert "registration.set_server_extension(LolDragonServerExtension" in guard_body
    assert "registration.set_extension(YoneManagementCardExtension);" not in guard_body
    assert "} else {" in init
    assert "registration.set_extension(YoneManagementCardExtension);" in init
    assert init.count("registration.set_extension(") == 2
    assert init.count("registration.set_server_extension(") == 1

    minimal_impl = rust.split(
        "impl ModExtension for YoneManagementCardExtension", 1
    )[1].split("impl ModExtension for LolModExtension", 1)[0]
    assert minimal_impl.count("fn post_update(") == 1
    assert "sync_yone_encyclopedia_portrait(&mut ui.root);" in minimal_impl
    assert minimal_impl.count("fn post_render(") == 1
    assert "trace_yone_render_commands(state);" in minimal_impl
    assert "rewrite_yone_management_card_render_commands(state);" in minimal_impl
    assert "rewrite_yone_portrait_render_commands(state);" in minimal_impl
    assert minimal_impl.count("rewrite_") == 2
    assert minimal_impl.index("trace_yone_render_commands(state);") < minimal_impl.index(
        "rewrite_yone_management_card_render_commands(state);"
    ) < minimal_impl.index("rewrite_yone_portrait_render_commands(state);")
    for forbidden in (
        "match_ui_database",
        "MatchUIRunner",
        "ClientDatabase",
        "RenderCommand",
        "sync_deterministic_dragon",
        "rewrite_bp_render_commands",
        "rewrite_dragon_render_commands",
        "rewrite_kled_portrait_render_commands",
        "rewrite_xayah_portrait_render_commands",
        "ChampionInfoUIRunner",
    ):
        assert forbidden not in minimal_impl

    assert "get_mut::<ChampionInfoUIRunner>" not in rust
    assert "get::<ChampionInfoUIRunner>" not in rust
    assert "fn is_ban_pick_render_pass" not in rust
    slot_sync = rust.split("fn sync_yone_encyclopedia_portrait", 1)[1].split(
        "fn is_yone_management_slot", 1
    )[0]
    for required in (
        'root.id == "champion_slot"',
        "is_yone_management_slot(root)",
        'root.query_mut("icon")',
        'root.query_mut("lol_fullbody_yone")',
        "icon.visible = false;",
        "portrait.visible = true;",
        "for child in &mut root.child",
        "sync_yone_encyclopedia_portrait(child);",
    ):
        assert required in slot_sync
    slot_identity = rust.split("fn is_yone_management_slot", 1)[1].split(
        "enum BpRenderSide", 1
    )[0]
    for required in (
        "runner_as::<LabelRunner>()",
        'matches!(text, "永恩" | "Yone")',
        'text.contains("dual_blader")',
        "runner_as::<ImageRunner>()",
        "runner.style.normal.source.as_str()",
        'source.contains("dual_blader")',
        'source.contains("/champions/yone")',
        "by_name || by_source",
    ):
        assert required in slot_identity
    slot_ui = (MOD / "ui/layout/champion_info_component/champion_slot.ui").read_text(
        encoding="utf-8"
    )
    icon_node = slot_ui.split("#icon:image", 1)[1].split("}", 1)[0]
    assert "width: 85px;" in icon_node
    assert "height: 93px;" in icon_node
    management_geometry = rust.split(
        "fn is_yone_management_card_geometry", 1
    )[1].split("fn rewrite_yone_management_card_render_commands", 1)[0]
    assert "(width - 85.0).abs() <= 1.0" in management_geometry
    assert "(height - 93.0).abs() <= 1.0" in management_geometry
    management_rewrite = rust.split(
        "fn rewrite_yone_management_card_render_commands", 1
    )[1].split("fn rewrite_yone_portrait_render_commands", 1)[0]
    assert "RenderCommand::NinePatch" in management_rewrite
    assert "RenderCommand::Sprite" not in management_rewrite
    assert "is_yone_management_card_geometry(*w, *h)" in management_rewrite
    assert "YONE_MANAGEMENT_CARD_PORTRAIT_TEXTURE" in management_rewrite
    for preserved_axis in ("*x =", "*y =", "*w =", "*h ="):
        assert preserved_axis not in management_rewrite
    for required in (
        "texture_rect.x = 0.0;",
        "texture_rect.y = 0.0;",
        "texture_rect.w = 1.0;",
        "texture_rect.h = 1.0;",
        "*left = 0.0;",
        "*right = 0.0;",
        "*top = 0.0;",
        "*bottom = 0.0;",
        "*sample_nearest = true;",
        '"yone_management_card_render_hook"',
        "version=0.10.16",
    ):
        assert required in management_rewrite


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
        flattened_reader = getattr(image, "get_flattened_data", None)
        pixels = list(
            flattened_reader()
            if flattened_reader is not None
            else image.getdata()
        )
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
    actor_sheet = Image.open(
        MOD / "aseprite_resources/champions/yone#sheet.png"
    ).convert("RGBA")
    assert actor_sheet.size == (3502, 88)
    actor_bbox = actor_sheet.getchannel("A").getbbox()
    assert actor_bbox is not None
    assert 0 <= actor_bbox[0] < actor_bbox[2] <= actor_sheet.width
    assert 0 <= actor_bbox[1] < actor_bbox[3] <= actor_sheet.height

    portrait_dir = MOD / "ui/champion_portrait"
    compact = Image.open(
        portrait_dir / "dual_blader_compact.png"
    ).convert("RGBA")
    assert compact.size == (64, 64)
    compact_bbox = compact.getchannel("A").getbbox()
    assert compact_bbox is not None
    assert compact_bbox[2] - compact_bbox[0] <= 50
    assert compact_bbox[3] - compact_bbox[1] <= 50
    assert min(
        compact_bbox[0],
        compact_bbox[1],
        compact.width - compact_bbox[2],
        compact.height - compact_bbox[3],
    ) >= 6

    scoreboard = Image.open(
        portrait_dir / "dual_blader_scoreboard.png"
    ).convert("RGBA")
    assert scoreboard.size == (48, 64)
    scoreboard_bbox = scoreboard.getchannel("A").getbbox()
    assert scoreboard_bbox is not None
    assert 36 <= scoreboard_bbox[2] - scoreboard_bbox[0] <= 40
    assert 50 <= scoreboard_bbox[3] - scoreboard_bbox[1] <= 54
    assert min(
        scoreboard_bbox[0],
        scoreboard_bbox[1],
        scoreboard.width - scoreboard_bbox[2],
        scoreboard.height - scoreboard_bbox[3],
    ) >= 4

    grid = Image.open(portrait_dir / "dual_blader_grid.png").convert("RGBA")
    assert grid.size == (90, 122)
    grid_bbox = grid.getchannel("A").getbbox()
    assert grid_bbox is not None and grid_bbox[3] <= 86
    assert grid.crop((0, 96, grid.width, grid.height)).getchannel("A").getbbox() is None

    fullbody = Image.open(
        MOD / "ui/champion_fullbody/dual_blader.png"
    ).convert("RGBA")
    assert fullbody.size == (85, 93)
    fullbody_bbox = fullbody.getchannel("A").getbbox()
    assert fullbody_bbox is not None
    assert 40 <= fullbody_bbox[2] - fullbody_bbox[0] <= 70
    assert 55 <= fullbody_bbox[3] - fullbody_bbox[1] <= 82
    assert fullbody_bbox[3] <= 86
    assert fullbody.height - fullbody_bbox[3] >= 7


def test_yone_v6_ui_is_source_direct_and_never_enlarges_the_43x55_battle_idle() -> None:
    source_path = MOD / "source/imagegen/yone_v6_idle_source.png"
    with Image.open(source_path) as opened:
        assert opened.width >= 800
        assert opened.height >= 1000

    builder_source = (MOD / "tools/build_yone.py").read_text(encoding="utf-8")
    build_ui = _python_function_source(builder_source, "build_splash_and_portraits")
    assert "load_yone_v6_ui_subject()" in build_ui
    assert "render_source_direct_ui_subject(" in build_ui
    assert "(85, 93)" in build_ui
    assert "_load_native_v6_body_frames" not in build_ui
    assert "Image.Resampling.NEAREST" not in build_ui

    card_contract = _python_function_source(
        builder_source, "yone_fullbody_card_contract"
    )
    assert "source.size != (85, 93)" in card_contract
    assert "rendered = source.copy()" in card_contract
    assert ".resize(" not in card_contract

    card_preview = Image.open(MOD / "qa/yone_v6_ui_card.png").convert("RGBA")
    assert card_preview.size == (141, 138)
    assert card_preview.getchannel("A").getextrema() == (255, 255)


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
        for disclosed_value in ("80", "6%", "1.5", "0.5", "8"):
            assert disclosed_value in skill2


def _retired_v3_visual_qa_records_the_stateless_cone_contract() -> None:
    contract = json.loads(
        (MOD / "qa/yone_visual_contract.json").read_text(encoding="utf-8")
    )
    assert "runtime_e_resolution" not in contract
    assert contract["runtime_w_resolution"] == {
        "action_duration_ticks": 30,
        "cooldown_ticks": 480,
        "movement": "none",
        "shape": "one stationary caster-following crescent plus one stateless native 80-degree, 42000-range forward cone scan",
        "damage": "35 + 45% Attack + 6% target maximum HP physical damage from the same cone snapshot",
        "shield": "the same native cone snapshot grants one 90-tick 50 + 20% Attack shield after any enemy hit, then scales through every enemy champion hit up to the normal five-champion team limit",
        "state": "no process-global W ledger; hit collection, damage, champion count, and shield tier resolve in one GameCtx callback",
        "attack_speed_limitation": "Mod API 0.8 exposes neither aggregate attack speed nor per-skill dynamic cast/cooldown mutation, so the disclosed 30/480-tick values remain fixed",
    }
    runtime = contract["runtime_effect_map"]
    assert runtime["lol_yone_w_crescent_cast"] == ["yone_w", "crescent"]
    assert runtime["lol_yone_w_hit"] == ["yone_w", "impact"]
    assert runtime["lol_yone_w_shield"] == ["yone_w", "shield"]
    assert not any(name.startswith("lol_yone_e_") for name in runtime)

    def assert_bbox(
        bbox: object,
        canvas: tuple[int, int] | list[int] | None = None,
    ) -> list[int]:
        assert isinstance(bbox, list) and len(bbox) == 4, bbox
        assert all(isinstance(value, int) for value in bbox), bbox
        left, top, right, bottom = bbox
        assert left < right and top < bottom, bbox
        if canvas is not None:
            assert 0 <= left < right <= canvas[0], (bbox, canvas)
            assert 0 <= top < bottom <= canvas[1], (bbox, canvas)
        return bbox

    face_contract = contract["face_readability"]
    faces = face_contract["all_battle_body_frames"]
    assert len(faces) == 54
    assert face_contract["policy"] == (
        "complete adult-proportioned ImageGen body-model replacement rasterized "
        "once as whole-sheet native 1x pixel art; no per-frame resize, "
        "post-scale face repaint, or synthetic feature overlay"
    )
    assert face_contract["body_source_paths"] == [
        "source/imagegen/yone_core_contact.png",
        "source/imagegen/yone_run_contact.png",
        "source/imagegen/yone_wr_body_contact.png",
        "source/imagegen/yone_defeat_contact.png",
    ]
    assert face_contract["actor_resampling"] == "whole-sheet NEAREST once; pack-time NONE"
    assert face_contract["idle_face_contract"] == {
        "source_authored": True,
        "post_scale_repaint": False,
        "view": "natural 3/4 profile with one dominant eye cue",
        "alpha_geometry_changes": 0,
    }
    for frame_name, row in faces.items():
        body_bbox = assert_bbox(row["body_bbox"])
        assert row["red_mask_pixels"] >= 1, (frame_name, row)
        assert_bbox(row["red_mask_bbox"])
        if frame_name.startswith("dead["):
            # Foreshortened defeat poses may no longer expose a measurable
            # cheek; their authored half-mask is the stable identity cue.
            if row["warm_skin_component_present"]:
                assert row["warm_skin_pixels"] > 0, (frame_name, row)
                assert_bbox(row["face_skin_bbox"])
            continue

        bbox = assert_bbox(row["face_skin_bbox"])
        if frame_name.startswith("idle["):
            minimum_width, minimum_height, minimum_skin, minimum_contrast = (
                4,
                5,
                10,
                18,
            )
        elif frame_name.startswith("run["):
            minimum_width, minimum_height, minimum_skin, minimum_contrast = (
                4,
                3,
                6,
                50,
            )
        else:
            minimum_width, minimum_height, minimum_skin, minimum_contrast = (
                3,
                2,
                4,
                12,
            )
        face_width = bbox[2] - bbox[0]
        face_height = bbox[3] - bbox[1]
        body_width = body_bbox[2] - body_bbox[0]
        body_height = body_bbox[3] - body_bbox[1]
        assert face_width >= minimum_width, (frame_name, row)
        assert face_height >= minimum_height, (frame_name, row)
        assert face_width / body_width <= 1 / 3, (frame_name, row)
        assert face_height / body_height <= 1 / 3, (frame_name, row)
        assert row["warm_skin_component_present"] is True, (frame_name, row)
        assert row["warm_skin_pixels"] == row["face_skin_pixels"], (
            frame_name,
            row,
        )
        assert row["warm_skin_pixels"] >= minimum_skin, (frame_name, row)
        assert row["adjacent_dark_eye_cue"] is True, (frame_name, row)
        assert row["adjacent_dark_eye_cue_pixels"] >= 1, (frame_name, row)
        assert row["face_contrast"] >= minimum_contrast, (frame_name, row)
        assert row["near_white_pixels"] <= max(
            2, row["warm_skin_pixels"] // 20
        ), (frame_name, row)

    assert set(face_contract["ui_surfaces"]) == {
        "fullbody",
        "compact",
        "scoreboard",
        "grid",
    }
    for surface, row in face_contract["ui_surfaces"].items():
        bbox = assert_bbox(row["face_skin_bbox"])
        minimum_width, minimum_height, minimum_skin = (
            (5, 6, 14) if surface == "fullbody" else (6, 8, 20)
        )
        assert bbox[2] - bbox[0] >= minimum_width
        assert bbox[3] - bbox[1] >= minimum_height
        assert row["warm_skin_component_present"] is True, (surface, row)
        assert row["warm_skin_pixels"] == row["face_skin_pixels"], (surface, row)
        assert row["warm_skin_pixels"] >= minimum_skin, (surface, row)
        assert row["adjacent_dark_eye_cue"] is True, (surface, row)
        assert row["adjacent_dark_eye_cue_pixels"] >= 1, (surface, row)
        assert row["face_contrast"] >= 18, (surface, row)
        assert row["near_white_pixels"] <= max(
            4, row["warm_skin_pixels"] // 10
        ), (surface, row)
        assert row["red_mask_pixels"] >= 1, (surface, row)
        assert_bbox(row["red_mask_bbox"])

    native_actor = contract["native_actor"]
    assert native_actor["body_master"] == "source/processed/yone_native_body_master.png"
    assert native_actor["pack_time_resampling"].startswith("none;")

    adult_min_visible_heights = {
        "idle": [36, 36, 36, 36],
        "run": [31, 32, 32, 33, 32, 32, 32, 33],
        "attack": [35, 33, 33, 31, 33, 34],
        "hit": [34],
        "skill": [35, 33, 34, 33, 33, 31, 33],
        "skill2": [35],
        "skill2_dash": [31],
        "skill2_attack": [32, 34, 33, 32, 32],
        "ult": [34, 25, 24, 31, 29, 24, 26, 25, 31, 22, 25, 33, 33],
    }
    body_frames = native_actor["body_frames"]
    assert set(body_frames) == {*adult_min_visible_heights, "dead"}
    for tag, minimum_heights in adult_min_visible_heights.items():
        rows = body_frames[tag]
        assert len(rows) == len(minimum_heights), tag
        for row, minimum_height in zip(rows, minimum_heights, strict=True):
            visible_size = row["visible_size"]
            assert isinstance(visible_size, list) and len(visible_size) == 2, row
            assert minimum_height <= visible_size[1] <= 42, (tag, row)

    logical_sheets = native_actor["body_logical_sheets"]
    assert set(logical_sheets) == {"core", "run", "wr", "defeat"}
    for name, row in logical_sheets.items():
        assert row["near_isotropic"] is True, (name, row)
        assert row["crop_lost_opaque_pixels"] == 0, (name, row)
        assert row["scale_relative_delta"] < row[
            "scale_relative_delta_limit_exclusive"
        ] == 0.005, (name, row)
        assert abs(row["scale_x"] - row["scale_y"]) / max(
            row["scale_x"], row["scale_y"]
        ) < 0.005, (name, row)

    identity = native_actor["master_to_atlas_identity"]
    assert len(identity) == 54
    assert all(row["master_to_atlas_byte_identical"] for row in identity.values())
    frame_sources = native_actor["body_frame_sources"]
    assert set(frame_sources) == set(identity) == set(faces)
    clip_whitelist = native_actor["horizontal_clip_whitelist"]
    assert "run[3]" not in clip_whitelist
    for frame_name, row in frame_sources.items():
        assert set(row["source_mapping"]) == {"sheet", "cell_index"}, row
        assert row["source_mapping"]["sheet"] in logical_sheets, row
        assert_bbox(row["source_alpha_bbox"])
        assert_bbox(row["destination_alpha_bbox"])
        assert row["source_opaque_pixels"] > 0, row
        sides = row["clip_sides_lost_opaque"]
        assert sides["top"] == sides["bottom"] == 0, (frame_name, row)
        assert row["lost_opaque_pixels"] == sum(sides.values()), row
        if sides["left"] or sides["right"]:
            assert frame_name in clip_whitelist, (frame_name, row)
        for side in ("left", "right"):
            limit = row["horizontal_clip_limits"][side]
            assert sides[side] <= limit["max_lost_opaque_pixels"], row
            assert sides[side] / row["source_opaque_pixels"] <= limit[
                "max_lost_opaque_ratio"
            ], row
    assert frame_sources["run[3]"]["clip_sides_lost_opaque"] == {
        "top": 0,
        "bottom": 0,
        "left": 0,
        "right": 0,
    }
    pixel_frames = native_actor["pixel_quality"]["frames"]
    assert len(pixel_frames) == 54
    assert all(row["hard_alpha"] for row in pixel_frames.values())
    assert max(row["opaque_palette_size"] for row in pixel_frames.values()) <= 48

    fullbody_card = face_contract["fullbody_card_85x93"]
    assert fullbody_card["source_size"] == [64, 64]
    assert fullbody_card["rendered_size"] == [85, 93]
    assert fullbody_card["resampling"] == "nearest"
    source_alpha_bbox = assert_bbox(
        fullbody_card["source_alpha_bbox"], fullbody_card["source_size"]
    )
    rendered_alpha_bbox = assert_bbox(
        fullbody_card["rendered_alpha_bbox"], fullbody_card["rendered_size"]
    )
    assert source_alpha_bbox[2] - source_alpha_bbox[0] >= 40
    assert source_alpha_bbox[3] - source_alpha_bbox[1] >= 40
    assert rendered_alpha_bbox[2] - rendered_alpha_bbox[0] >= 54
    assert rendered_alpha_bbox[3] - rendered_alpha_bbox[1] >= 58
    assert fullbody_card["source_bottom_margin"] >= 3
    assert fullbody_card["rendered_bottom_margin"] >= 4
    for last_row, bbox in (
        (fullbody_card["source_last_alpha_row"], source_alpha_bbox),
        (fullbody_card["rendered_last_alpha_row"], rendered_alpha_bbox),
    ):
        assert len(last_row) == 3
        assert last_row[0] == bbox[3] - 1
        assert bbox[0] <= last_row[1] < last_row[2] <= bbox[2]

    source_face_bbox = assert_bbox(
        fullbody_card["source_face_skin_bbox"], fullbody_card["source_size"]
    )
    assert source_face_bbox[2] - source_face_bbox[0] >= 5
    assert source_face_bbox[3] - source_face_bbox[1] >= 6
    rendered_face_bbox = assert_bbox(
        fullbody_card["rendered_face_skin_bbox"], fullbody_card["rendered_size"]
    )
    assert rendered_face_bbox[2] - rendered_face_bbox[0] >= 6
    assert rendered_face_bbox[3] - rendered_face_bbox[1] >= 9
    assert fullbody_card["rendered_face_skin_pixels"] >= 20
    assert fullbody_card["source_warm_skin_component_present"] is True
    assert fullbody_card["rendered_warm_skin_component_present"] is True
    assert fullbody_card["source_adjacent_dark_eye_cue"] is True
    assert fullbody_card["rendered_adjacent_dark_eye_cue"] is True
    assert fullbody_card["source_adjacent_dark_eye_cue_pixels"] >= 1
    assert fullbody_card["source_face_contrast"] >= 18
    assert fullbody_card["source_near_white_pixels"] <= max(
        4, face_contract["ui_surfaces"]["fullbody"]["warm_skin_pixels"] // 10
    )
    assert fullbody_card["source_red_mask_pixels"] >= 20
    assert_bbox(fullbody_card["source_red_mask_bbox"], fullbody_card["source_size"])

    layout = (
        MOD / "ui/layout/champion_info_component/champion_slot.ui"
    ).read_text(encoding="utf-8")
    node_match = re.search(
        r"#lol_fullbody_yone:image\s*\{(?P<body>.*?)\n\s*\}",
        layout,
        re.DOTALL,
    )
    assert node_match is not None
    node = node_match.group("body")
    assert "width: 85px;" in node
    assert "height: 93px;" in node
    assert 'source: "asset/lol_mod/ui/champion_fullbody/dual_blader";' in node
    assert "sample_linear: false;" in node

    live_card = face_contract["live_idle_card"]
    assert {
        key: live_card[key]
        for key in (
            "scale",
            "resampling",
            "stage_height",
            "audited_center_y",
            "divider_top",
            "minimum_divider_clearance",
        )
    } == {
        "scale": 2.2,
        "resampling": "nearest",
        "stage_height": 121,
        "audited_center_y": -16,
        "divider_top": 99,
        "minimum_divider_clearance": 10,
    }
    live_frames = live_card["frames"]
    assert set(live_frames) == {"idle[0]", "idle[1]", "idle[2]", "idle[3]"}
    for frame_name, row in live_frames.items():
        source_size = row["source_size"]
        rendered_size = row["rendered_size"]
        assert rendered_size == [
            round(source_size[0] * live_card["scale"]),
            round(source_size[1] * live_card["scale"]),
        ], (frame_name, row)
        assert rendered_size[1] <= live_card["stage_height"]
        assert row["stage_y"] == (
            live_card["stage_height"] - rendered_size[1]
        ) // 2
        alpha_bbox = assert_bbox(row["alpha_bbox"], rendered_size)
        projected_bbox = assert_bbox(
            row["projected_alpha_bbox"],
            (rendered_size[0], live_card["stage_height"]),
        )
        assert projected_bbox == [
            alpha_bbox[0],
            alpha_bbox[1] + row["stage_y"],
            alpha_bbox[2],
            alpha_bbox[3] + row["stage_y"],
        ]
        assert row["divider_clearance"] == (
            live_card["divider_top"] - projected_bbox[3]
        )
        assert row["source_bottom_clearance"] > 0, (frame_name, row)
        assert row["rendered_bottom_clearance"] > 0, (frame_name, row)
        assert abs(
            row["rendered_bottom_clearance"]
            - round(row["source_bottom_clearance"] * live_card["scale"])
        ) <= 1, (frame_name, row)
        assert row["face_variant"] == "front", (frame_name, row)
        source_face_bbox = assert_bbox(row["source_face_skin_bbox"], source_size)
        rendered_face_bbox = assert_bbox(
            row["rendered_face_skin_bbox"], rendered_size
        )
        assert source_face_bbox[2] - source_face_bbox[0] >= 4
        assert source_face_bbox[3] - source_face_bbox[1] >= 5
        assert rendered_face_bbox[2] - rendered_face_bbox[0] >= 8
        assert rendered_face_bbox[3] - rendered_face_bbox[1] >= 11
        assert row["rendered_face_skin_pixels"] >= 1, (frame_name, row)
        assert row["source_warm_skin_component_present"] is True, (
            frame_name,
            row,
        )
        assert row["rendered_warm_skin_component_present"] is True, (
            frame_name,
            row,
        )
        assert row["source_adjacent_dark_eye_cue"] is True, (frame_name, row)
        assert row["rendered_adjacent_dark_eye_cue"] is True, (frame_name, row)
        assert row["source_adjacent_dark_eye_cue_pixels"] >= 1, (frame_name, row)
        assert row["source_face_contrast"] >= 18, (frame_name, row)
        assert row["source_near_white_pixels"] <= 1, (frame_name, row)
        assert row["source_red_mask_pixels"] >= 1, (frame_name, row)
        assert_bbox(row["source_red_mask_bbox"], source_size)
        assert row["divider_clearance"] >= live_card["minimum_divider_clearance"], (
            frame_name,
            row,
        )

    live_run = face_contract["live_run_profile"]
    assert {
        key: live_run[key] for key in ("scale", "resampling", "stage_height")
    } == {"scale": 2.2, "resampling": "nearest", "stage_height": 117}
    run_frames = live_run["frames"]
    assert set(run_frames) == {f"run[{index}]" for index in range(8)}
    expected_run_bottom_clearances = [13, 18, 21, 18, 13, 17, 21, 17]
    visible_run_eye_cues = 0
    for index, (frame_name, row) in enumerate(run_frames.items()):
        source_size = row["source_size"]
        rendered_size = row["rendered_size"]
        assert rendered_size == [
            round(source_size[0] * live_run["scale"]),
            round(source_size[1] * live_run["scale"]),
        ], (frame_name, row)
        assert rendered_size[1] <= live_run["stage_height"]
        assert row["stage_y"] == (
            live_run["stage_height"] - rendered_size[1]
        ) // 2
        alpha_bbox = assert_bbox(row["alpha_bbox"], rendered_size)
        projected_bbox = assert_bbox(
            row["projected_alpha_bbox"],
            (rendered_size[0], live_run["stage_height"]),
        )
        assert projected_bbox == [
            alpha_bbox[0],
            alpha_bbox[1] + row["stage_y"],
            alpha_bbox[2],
            alpha_bbox[3] + row["stage_y"],
        ]
        assert row["divider_clearance"] == live_card["divider_top"] - projected_bbox[3]
        assert row["source_bottom_clearance"] == expected_run_bottom_clearances[index]
        assert row["rendered_bottom_clearance"] > 0, (frame_name, row)
        assert abs(
            row["rendered_bottom_clearance"]
            - round(row["source_bottom_clearance"] * live_run["scale"])
        ) <= 1, (frame_name, row)
        assert row["face_variant"] == "profile", (frame_name, row)
        source_face_bbox = assert_bbox(row["source_face_skin_bbox"], source_size)
        rendered_face_bbox = assert_bbox(
            row["rendered_face_skin_bbox"], rendered_size
        )
        assert source_face_bbox[2] - source_face_bbox[0] >= 4
        assert source_face_bbox[3] - source_face_bbox[1] >= 3
        assert rendered_face_bbox[2] - rendered_face_bbox[0] >= 8
        assert rendered_face_bbox[3] - rendered_face_bbox[1] >= 6
        assert row["rendered_face_skin_pixels"] >= 24, (frame_name, row)
        assert row["source_warm_skin_component_present"] is True, (
            frame_name,
            row,
        )
        assert row["rendered_warm_skin_component_present"] is True, (
            frame_name,
            row,
        )
        assert row["source_adjacent_dark_eye_cue"] is True, (frame_name, row)
        assert row["rendered_adjacent_dark_eye_cue"] is True, (frame_name, row)
        assert row["source_adjacent_dark_eye_cue_pixels"] >= 1, (frame_name, row)
        assert row["rendered_adjacent_dark_eye_cue_pixels"] >= 1, (
            frame_name,
            row,
        )
        assert row["source_near_white_pixels"] <= 2, (frame_name, row)
        assert row["source_face_contrast"] >= 50, (frame_name, row)
        assert row["source_red_mask_pixels"] >= 20, (frame_name, row)
        assert_bbox(row["source_red_mask_bbox"], source_size)
        if row["source_adjacent_dark_eye_cue"]:
            visible_run_eye_cues += 1
        assert row["divider_clearance"] >= live_card["minimum_divider_clearance"], (
            frame_name,
            row,
        )
    assert visible_run_eye_cues == len(run_frames)


def test_generated_qa_contact_labels_second_slot_as_w() -> None:
    source = (MOD / "tools/build_yone.py").read_text(encoding="utf-8")
    assert '("W", ICON_DIR / "yone_skill2.png")' in source
    assert "icon_sources = [cells[0], cells[1], cells[2]]" in source


def _retired_v3_w_actor_sequence_uses_generated_wr_native_cells_without_code_drawing() -> None:
    source = (MOD / "tools/build_yone.py").read_text(encoding="utf-8")
    assert '"skill2_attack": [("wr", index) for index in range(5)]' in source
    for forbidden in (
        "def fit_actor(",
        "def repaint_yone_face(",
        "def finalize_yone_battle_face(",
        "def retouch_yone_ui_surface(",
        "def add_yone_w_weapon_pose(",
        "w_master_subject",
    ):
        assert forbidden not in source
    assert "NATIVE_BODY_FRAME_SOURCES" in source
    assert "_compose_native_body_master()" in source

    anim = json.loads(
        (MOD / "aseprite_resources/champions/yone#anim.fanim").read_text(
            encoding="utf-8"
        )
    )["anims"]["skill2_attack"]["frames"]
    sheet = Image.open(
        MOD / "aseprite_resources/champions/yone#sheet.png"
    ).convert("RGBA")
    master = Image.open(
        MOD / "source/processed/yone_native_body_master.png"
    ).convert("RGBA")
    visible_poses = []
    relative_foot_anchors = []
    bottom_clearances = []
    visible_heights = []
    for frame in anim:
        data = frame["data"]
        image = sheet.crop(
            (
                data["x"],
                data["y"],
                data["x"] + data["w"],
                data["y"] + data["h"],
            )
        )
        assert image.tobytes() == master.crop(
            (
                data["x"],
                data["y"],
                data["x"] + data["w"],
                data["y"] + data["h"],
            )
        ).tobytes()
        normalized = Image.new("RGBA", (61, 55), (0, 0, 0, 0))
        normalized.alpha_composite(
            image,
            ((61 - data["w"]) // 2, (55 - data["h"]) // 2),
        )
        visible_poses.append(hashlib.sha256(normalized.tobytes()).hexdigest())
        bbox = image.getchannel("A").getbbox()
        assert bbox is not None
        visible_heights.append(bbox[3] - bbox[1])
        relative_foot_anchors.append(bbox[3] - data["h"] / 2)
        bottom_clearances.append(data["h"] - bbox[3])

    # Five generated WR poses share the official planted pivot while retaining
    # source-authored arm, blade, face and body pixels.
    assert len(set(visible_poses)) >= 4
    assert max(relative_foot_anchors) - min(relative_foot_anchors) == 0
    assert bottom_clearances == [3, 4, 8, 9, 7]
    assert min(visible_heights) >= 32


def _retired_v3_yone_w_release_docs_version_and_manifest_are_atomic() -> None:
    mod_info = json.loads((MOD / "mod.mod_info").read_text(encoding="utf-8"))
    assert mod_info["version"] == "0.10.16"
    assert "Q/W/R" in mod_info["description"]
    assert "E-only Soul Unbound" not in mod_info["description"]
    assert "0.5.1" in mod_info["description"]
    assert "saved" in mod_info["description"].casefold()
    assert "no process-global ledger" in mod_info["description"]
    assert "save first created on 0.10.5 or later" in mod_info["description"]
    assert mod_info["dependencies"] == [
        {"mod_id": "base", "version": ">=0.5.1"}
    ]

    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "v0.10.5" in readme
    assert "0.5.1" in readme
    assert "新建 `0.10.5` 存档" in readme
    assert "80°" in readme
    assert "35 + 45% Attack + 6%" in readme
    assert "全套 ImageGen 人物重制" in readme
    assert "整张动作表一次性栅格化为最终原生 `1x` 像素" in readme
    assert "逐矩形逐字节复制到战斗图集" in readme
    assert "不再用代码补画脸、手臂或武器" in readme

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


def test_yone_v6_release_keeps_q_w_r_and_exact_native_body_atomic() -> None:
    mod_info = json.loads((MOD / "mod.mod_info").read_text(encoding="utf-8"))
    assert mod_info["version"] == "0.10.16"
    assert "Q/W/R" in mod_info["description"]
    assert "E-only Soul Unbound" not in mod_info["description"]

    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "Q/W/R" in readme
    assert "Soul Unbound" not in readme

    champion_payload = (MOD / "champion/dual_blader.data_champion").read_text(
        encoding="utf-8"
    )
    for ability_runtime_prefix in (
        "lol_yone_q_",
        "lol_yone_w_",
        "lol_yone_r_",
    ):
        assert ability_runtime_prefix in champion_payload

    v6 = json.loads(
        (MOD / "source/native/yone_v6/frames.json").read_text(encoding="utf-8")
    )
    assert v6["schema_version"] == 6
    assert v6["route"] == "exact-native-v6"
    assert v6["atlas_size"] == [3502, 88]
    assert len(v6["frames"]) == 54
    assert all("face_visibility" in row for row in v6["frames"])

    manifest = json.loads(
        (MOD / "build_manifest.json").read_text(encoding="utf-8")
    )
    paths = {row["path"].replace("\\", "/") for row in manifest["files"]}
    assert {
        "aseprite_resources/effects/yone_q#anim.fanim",
        "aseprite_resources/effects/yone_q#sheet.png",
        "aseprite_resources/effects/yone_w#anim.fanim",
        "aseprite_resources/effects/yone_w#sheet.png",
        "aseprite_resources/effects/yone_r#anim.fanim",
        "aseprite_resources/effects/yone_r#sheet.png",
        "sound/sfx/lol_yone_w_cast.sound_info",
        "sound/sfx/lol_yone_w_hit.sound_info",
        "sound/sfx/lol_yone_w_shield.sound_info",
    } <= paths
    assert not {
        "source/imagegen/yone_core_contact.png",
        "source/imagegen/yone_run_contact.png",
        "source/imagegen/yone_wr_body_contact.png",
        "source/imagegen/yone_defeat_contact.png",
        "source/processed/yone_native_body_master.png",
        "source/imagegen/yone_v4_action_contact.png",
        "source/imagegen/yone_v4_idle_candidate_43x55.png",
        "source/imagegen/yone_v5_idle_source.png",
        "source/imagegen/yone_v5_idle_golden_43x55.png",
        "source/imagegen/yone_v5_motion_contact.png",
        "source/imagegen/yone_v5_attack_q_w_contact.png",
        "source/imagegen/yone_v5_q5_contact.png",
        "source/imagegen/yone_v5_ult_contact.png",
    }.intersection(paths)
    assert not any(path.startswith("source/native/yone_v4/") for path in paths)
    assert not any(path.startswith("source/native/yone_v5/") for path in paths)
    assert not any("yone_v4" in path.casefold() for path in paths)
    assert not any("yone_v5" in path.casefold() for path in paths)
    physical_retired_files = sorted(
        path.relative_to(MOD).as_posix()
        for path in MOD.rglob("*")
        if path.is_file()
        and any(
            token in path.name.casefold()
            for token in ("yone_v4", "yone_v5")
        )
    )
    assert physical_retired_files == []


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
