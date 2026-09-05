from __future__ import annotations

import ast
import hashlib
import importlib.util
import json
import re
import sys
from pathlib import Path

import pytest
from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
MOD = ROOT / "mods" / "lol_mod"
YONE_ACTIVE_ANIM = MOD / "aseprite_resources/champions/yone_v7#anim.fanim"
YONE_ACTIVE_SHEET = MOD / "aseprite_resources/champions/yone_v7#sheet.png"
YONE_LEGACY_ANIM = MOD / "aseprite_resources/champions/yone#anim.fanim"
YONE_LEGACY_SHEET = MOD / "aseprite_resources/champions/yone#sheet.png"

LEGACY_SAVED_NATIVE_COMPATIBILITY_NAMES = {
    "lol_shen_shadow_dash_ai_hint_native",
    "lol_shen_shadow_dash_taunt_native",
    "lol_yone_e_start_native",
    "lol_yone_e_begin_return_native",
    "lol_yone_e_damage_pre_native",
    "lol_yone_e_damage_post_native",
    "lol_yone_e_settle_native",
    "lol_yone_w_begin_native",
    "lol_yone_w_collect_hit_native",
    "lol_yone_w_settle_native",
    "lol_yone_w_cone_native",
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


def direct_effects(root: dict, effect_type: str) -> list[dict]:
    return [
        effect
        for effect in root.get("effects", [])
        if effect.get("type") == effect_type
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


def _load_yone_v7_generator():
    tool_dir = MOD / "tools"
    module_path = tool_dir / "generate_yone_v7_native.py"
    sys.path.insert(0, str(tool_dir))
    try:
        spec = importlib.util.spec_from_file_location(
            "test_generate_yone_v7_native", module_path
        )
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path.pop(0)


def test_run_screen_contact_does_not_claim_anatomical_leg_alternation():
    generator = _load_yone_v7_generator()
    frames = MOD / "source/native/yone_v7/frames"
    for index in range(8):
        with Image.open(frames / f"run_{index:02d}.png") as frame:
            geometry = generator.run_foot_geometry(frame.convert("RGBA"), index)
        assert geometry["support_screen_side"] in ("left", "right")
        assert geometry["support_leg"] == geometry["support_screen_side"]
        # Splitting pixels by x cannot establish which hip owns a foot.
        assert geometry["anatomical_leg_identity_verified"] is False


def _component_sizes_8(points: set[tuple[int, int]]) -> list[int]:
    remaining = set(points)
    sizes: list[int] = []
    while remaining:
        stack = [remaining.pop()]
        size = 0
        while stack:
            x, y = stack.pop()
            size += 1
            for delta_y in (-1, 0, 1):
                for delta_x in (-1, 0, 1):
                    if delta_x == 0 and delta_y == 0:
                        continue
                    neighbor = (x + delta_x, y + delta_y)
                    if neighbor in remaining:
                        remaining.remove(neighbor)
                        stack.append(neighbor)
        sizes.append(size)
    return sorted(sizes, reverse=True)


def _assert_yone_run_final_png_contract() -> dict:
    native_root = MOD / "source/native/yone_v7"
    manifest = json.loads((native_root / "frames.json").read_text(encoding="utf-8"))
    palette = json.loads((native_root / "palette.json").read_text(encoding="utf-8"))
    by_role = {
        row["role"]: tuple(row["rgba"])
        for row in palette["colors"]
    }
    weapon_roles = {
        "steel": ("steel_dark", "steel_mid", "steel_highlight"),
        "azakana": ("azakana_dark", "azakana_red", "azakana_highlight"),
    }
    weapon_colors = {
        weapon: {by_role[role] for role in roles}
        for weapon, roles in weapon_roles.items()
    }
    all_weapon_colors = set().union(*weapon_colors.values())
    rows = {
        row["index"]: row
        for row in manifest["frames"]
        if row["action"] == "run"
    }
    assert set(rows) == set(range(8))
    frames = [
        Image.open(native_root / rows[index]["file"]).convert("RGBA")
        for index in range(8)
    ]

    weapon_components = []
    for index, frame in enumerate(frames):
        report = {"index": index}
        for weapon in ("steel", "azakana"):
            points = {
                (x, y)
                for y in range(frame.height)
                for x in range(frame.width)
                if frame.getpixel((x, y)) in weapon_colors[weapon]
            }
            sizes = _component_sizes_8(points)
            assert len(sizes) == 1, (index, weapon, sizes)
            report[weapon] = sizes
        weapon_components.append(report)

    pair_reports = []
    for source_index in range(4):
        mirrored_index = source_index + 4
        source = frames[source_index]
        mirrored = frames[mirrored_index]
        assert source.size == mirrored.size
        source_ground = (
            source.height - rows[source_index]["bottom_margin"] - 1
        )
        mirrored_ground = (
            mirrored.height - rows[mirrored_index]["bottom_margin"] - 1
        )
        source_center = (source.width - 1) // 2
        mirrored_center = (mirrored.width - 1) // 2
        candidates = []
        for source_pelvis in range(source_center - 4, source_center + 5):
            for mirrored_pelvis in range(
                mirrored_center - 4, mirrored_center + 5
            ):
                checked = 0
                mismatches = 0
                for source_y in range(source_ground - 8, source_ground + 1):
                    for source_x in range(
                        max(1, source_pelvis - 11),
                        min(source.width - 1, source_pelvis + 12),
                    ):
                        target_x = mirrored_pelvis - (source_x - source_pelvis)
                        target_y = mirrored_ground - (source_ground - source_y)
                        if not (
                            1 <= target_x < mirrored.width - 1
                            and 1 <= target_y < mirrored.height - 1
                        ):
                            continue
                        source_color = source.getpixel((source_x, source_y))
                        target_color = mirrored.getpixel((target_x, target_y))
                        if (
                            source_color in all_weapon_colors
                            or target_color in all_weapon_colors
                        ):
                            continue
                        if source_color[3] or target_color[3]:
                            checked += 1
                            mismatches += source_color != target_color
                candidates.append(
                    (
                        mismatches,
                        -checked,
                        abs(source_pelvis - source_center)
                        + abs(mirrored_pelvis - mirrored_center),
                        source_pelvis,
                        mirrored_pelvis,
                    )
                )
        best = min(candidates)
        assert best[0] == 0 and -best[1] >= 64, (
            source_index,
            mirrored_index,
            best,
        )
        pair_reports.append(
            {
                "source_index": source_index,
                "mirrored_index": mirrored_index,
                "match": True,
                "checked_pixels": -best[1],
                "source_pelvis": best[3],
                "mirrored_pelvis": best[4],
            }
        )

    frame_hashes = {
        f"run_{index:02d}.png": hashlib.sha256(frames[index].tobytes()).hexdigest()
        for index in range(8)
    }
    assert len(set(frame_hashes.values())) == 8
    return {
        "weapon_components": weapon_components,
        "pair_matches": [row["match"] for row in pair_reports],
        "pair_reports": pair_reports,
        "unlocked_frame_pixel_hashes": frame_hashes,
    }


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
    assert yone["sprite"] == (
        "asset/lol_mod/aseprite_resources/champions/yone_v7"
    )
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
    assert (
        attack["duration"],
        attack["cooltime"],
        attack["start_timing"],
        attack["range"],
    ) == (20, 50, 0, 25000)
    assert attack["effect"]["type"] == "SwitchByBuff"
    assert attack["effect"]["buff_name"] == "lol_yone_azakana_ready"
    steel_branch = attack["effect"]["effect_none"]
    azakana_branch = attack["effect"]["effect_buff"]
    assert find_effect(steel_branch, "CasterAnimation") == [
        {"type": "CasterAnimation", "name": "attack_steel", "tick": 20}
    ]
    assert find_effect(azakana_branch, "CasterAnimation") == [
        {"type": "CasterAnimation", "name": "attack_azakana", "tick": 20}
    ]
    for branch, cast, hit, toggle_type in (
        (
            steel_branch,
            "lol_yone_attack_steel_cast",
            "lol_yone_attack_steel_hit",
            "AddCasterBuff",
        ),
        (
            azakana_branch,
            "lol_yone_attack_azakana_cast",
            "lol_yone_attack_azakana_hit",
            "RemoveCasterBuff",
        ),
    ):
        assert [effect["type"] for effect in branch["effects"]] == [
            "CasterAnimation",
            "Sfx",
            "Delayed",
        ]
        assert branch["effects"][1] == {"type": "Sfx", "name": cast}
        delayed = direct_effects(branch, "Delayed")
        assert len(delayed) == 1 and delayed[0]["tick"] == 13
        assert [effect["type"] for effect in delayed[0]["effects"]] == [
            "Attack",
            "ViewEffect",
            "TargetSfx",
            toggle_type,
        ]
        assert delayed[0]["effects"][1]["name"] == hit
        assert delayed[0]["effects"][2]["name"] == hit
        assert not direct_effects(branch, "Attack")
        assert not direct_effects(branch, toggle_type)
    assert not find_effect(steel_branch, "CasterViewEffect")
    assert not find_effect(azakana_branch, "CasterViewEffect")
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

    cargo = (MOD / "Cargo.toml").read_text(encoding="utf-8")
    assert 'path = "src/stable_runtime.rs"' in cargo
    rust = (MOD / "src/stable_runtime.rs").read_text(encoding="utf-8")
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
    cargo = (MOD / "Cargo.toml").read_text(encoding="utf-8")
    assert 'path = "src/stable_runtime.rs"' in cargo
    rust = (MOD / "src/stable_runtime.rs").read_text(encoding="utf-8")
    loop = re.search(
        r"for retired_name in \[(?P<body>.*?)\]\s*\{",
        rust,
        flags=re.DOTALL,
    )
    assert loop is not None
    loop_names = set(re.findall(r'"([^"]+)"', loop.group("body")))
    direct_names = set(
        re.findall(
            r'registration\.add_native_effect\(\s*"([^"]+)",\s*'
            r"LegacySavedNativeCompatibilityEffect,\s*\);",
            rust,
        )
    )
    discovered_names = loop_names | direct_names
    assert discovered_names == LEGACY_SAVED_NATIVE_COMPATIBILITY_NAMES
    assert all(rust.count(f'"{name}"') == 1 for name in discovered_names)

    compatibility_impl = rust.split(
        "impl StableEffectType for LegacySavedNativeCompatibilityEffect", 1
    )[1].split("\nfn init", 1)[0]
    assert re.search(
        r"fn apply\([^)]*\)\s*\{\s*\}",
        compatibility_impl,
        flags=re.DOTALL,
    )
    assert not any(
        token in compatibility_impl
        for token in ("sim.", "add_buff", "Attack", "Shield", "Rush", "Teleport")
    )


def test_yone_q_w_r_match_the_silverbear_pure_data_contract() -> None:
    yone = load_yone()

    q = yone["skill"]
    assert (
        q["action_name"],
        q["duration"],
        q["cooltime"],
        q["start_timing"],
        q["range"],
        q["casting_type"],
        q["casting_target"],
    ) == (
        "skill",
        20,
        300,
        6,
        25000,
        "Direction",
        "EnemyWithoutTower",
    )
    assert find_effect(q, "CasterAnimation") == [
        {"type": "CasterAnimation", "name": "skill_q3", "tick": 20}
    ]
    q_rushes = find_effect(q, "RushTime")
    assert len(q_rushes) == 1
    q_rush = q_rushes[0]
    assert (
        q_rush["speed"],
        q_rush["tick"],
        q_rush["range"],
        q_rush["casting_target"],
        q_rush["penetrate"],
    ) == (3600, 20, 25000, "EnemyWithoutTower", True)
    assert [
        (hit["damage"], hit["attack_ratio"], hit["hp_ratio"], hit["target_hp_ratio"])
        for hit in find_effect(q_rush, "Attack")
    ] == [(75, 80, 0, 0)]
    assert [cc["duration"] for cc in find_effect(q_rush, "Airborne")] == [45]
    assert find_effect(q_rush, "Heal") == [
        {
            "type": "Heal",
            "amount": 0,
            "attack_ratio": 5,
            "ap_ratio": 0,
            "heal_type": "Caster",
        }
    ]

    w = yone["skill2"]
    assert (
        w["action_name"],
        w["duration"],
        w["cooltime"],
        w["start_timing"],
        w["range"],
        w["casting_type"],
        w["casting_target"],
    ) == (
        "skill2",
        30,
        480,
        0,
        35000,
        "Direction",
        "EnemyWithoutTower",
    )
    assert find_effect(w, "CasterAnimation") == [
        {"type": "CasterAnimation", "name": "skill_w_azakana", "tick": 30}
    ]
    w_projectiles = find_effect(
        w, "LinearProjectile", name="lol_yone_w_sweep_projectile"
    )
    assert len(w_projectiles) == 1
    projectile = w_projectiles[0]
    assert (
        projectile["speed"],
        projectile["range"],
        projectile["penetrate"],
        projectile["shape"],
        projectile["applied_target"],
    ) == (
        4500,
        35000,
        True,
        {"Rect": {"width": 40000, "height": 30000}},
        "EnemyWithoutTower",
    )
    assert [
        (hit["damage"], hit["attack_ratio"], hit["hp_ratio"], hit["target_hp_ratio"])
        for hit in find_effect(projectile, "Attack")
    ] == [(80, 80, 0, 0)]
    assert find_effect(projectile, "Knockback") == [
        {"type": "Knockback", "speed": 2000, "tick": 12}
    ]
    assert find_effect(projectile, "RangeEffect") == [
        {
            "type": "RangeEffect",
            "shape": {"Circle": {"radius": 10000}},
            "target": "AllyOnlySelf",
            "apply_type": "AroundCaster",
            "effects": [
                {
                    "type": "Shield",
                    "amount": 20,
                    "attack_ratio": 20,
                    "ap_ratio": 0,
                    "tick": 180,
                },
                {"type": "ViewEffect", "name": "lol_yone_w_shield"},
                {"type": "TargetSfx", "name": "lol_yone_w_shield"},
            ],
        }
    ]

    r = yone["ult"]
    assert (
        r["duration"],
        r["cooltime"],
        r["range"],
        r["casting_type"],
        r["casting_target"],
    ) == (60, 3000, 55000, "Direction", "EnemyWithoutTower")
    outer_delays = direct_effects(r["effect"], "Delayed")
    assert len(outer_delays) == 1 and outer_delays[0]["tick"] == 35
    r_rushes = find_effect(outer_delays[0], "RushTime")
    assert len(r_rushes) == 1
    r_rush = r_rushes[0]
    assert (
        r_rush["speed"],
        r_rush["tick"],
        r_rush["range"],
        r_rush["casting_target"],
        r_rush["penetrate"],
    ) == (4000, 30, 20000, "EnemyWithoutTower", True)
    assert [
        (hit["damage"], hit["attack_ratio"])
        for hit in find_effect(r_rush, "Attack")
    ] == [(120, 70)]
    assert [cc["duration"] for cc in find_effect(r_rush, "Airborne")] == [45]
    assert find_effect(r_rush, "Pull") == [
        {"type": "Pull", "speed": 3000, "tick": 12}
    ]


def test_yone_active_skill_tree_has_no_staged_q_native_w_or_soul_unbound() -> None:
    yone = load_yone()
    active = {slot: yone[slot] for slot in ("skill", "skill2", "ult")}
    serialized = json.dumps(active, ensure_ascii=False)
    assert not find_effect(active, "Native")
    assert "lol_yone_mortal_steel_stack" not in serialized
    assert "lol_yone_w_shield_tier" not in serialized
    assert "lol_yone_w_cone_native" not in serialized
    assert "lol_yone_e_" not in serialized
    assert "Soul Unbound" not in serialized
    assert "view_buffs" not in yone


def test_yone_active_vfx_audio_and_icons_are_project_owned_and_fully_referenced() -> None:
    yone = load_yone()
    projectiles = {view["name"]: view for view in yone["view_projectiles"]}
    assert projectiles == {
        "lol_yone_w_sweep_projectile": {
            "type": "Animated",
            "name": "lol_yone_w_sweep_projectile",
            "anim": "asset/lol_mod/aseprite_resources/effects/yone_w",
            "tag": "crescent",
            "z": 3,
            "repeat": True,
        }
    }
    views = {view["name"]: view for view in yone["view_effects"]}
    assert set(views) == {
        "lol_yone_attack_steel_hit",
        "lol_yone_attack_azakana_hit",
        "lol_yone_q_hit",
        "lol_yone_q3_airborne_cue",
        "lol_yone_w_hit",
        "lol_yone_w_shield",
        "lol_yone_r_windup",
        "lol_yone_r_launch",
        "lol_yone_r_knockup",
        "lol_yone_r_slash_blue",
        "lol_yone_r_slash_red",
    }
    used_views = {
        effect["name"]
        for slot in ("attack", "skill", "skill2", "ult")
        for effect in walk_effects(yone[slot])
        if effect.get("type")
        in {"ViewEffect", "CasterViewEffect", "LinearProjectile"}
    }
    assert used_views == set(projectiles) | set(views)

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
        "lol_yone_w_cast",
        "lol_yone_w_hit",
        "lol_yone_w_shield",
        "lol_yone_r_cast",
        "lol_yone_r_arrival",
        "lol_yone_r_slash_steel",
        "lol_yone_r_slash_azakana",
        "lol_yone_r_echo",
    }
    assert not any("lol_yone_e_" in name for name in used_audio | used_views)

    icon_paths = [MOD / f"icons/{Path(icon).name}.png" for icon in yone["skill_icons"]]
    assert all(path.is_file() for path in icon_paths)
    assert all(Image.open(path).size == (64, 64) for path in icon_paths)
    icon_hashes = {hashlib.sha256(path.read_bytes()).hexdigest() for path in icon_paths}
    assert len(icon_hashes) == 3

    reference_icon_dir = Path(
        r"D:\steam\steamapps\workshop\content\3009300\3774304166\icons"
    )
    reference_paths = [
        reference_icon_dir / name
        for name in ("yone_skill.png", "yone_skill2.png", "yone_ult.png")
    ]
    if all(path.is_file() for path in reference_paths):
        reference_hashes = {
            hashlib.sha256(path.read_bytes()).hexdigest() for path in reference_paths
        }
        assert icon_hashes.isdisjoint(reference_hashes)


def _retired_w_uses_one_stateless_native_cone_snapshot_and_one_tiered_shield() -> None:
    w = load_yone()["skill2"]
    assert (
        w["cooltime"],
        w["duration"],
        w["start_timing"],
        w["range"],
        w["casting_type"],
        w["casting_target"],
    ) == (480, 30, 0, 42000, "Direction", "EnemyWithoutTower")

    assert find_effect(w, "CasterAnimation") == [
        {"type": "CasterAnimation", "name": "skill_w_azakana", "tick": 30}
    ]
    assert not find_effect(w, "LineRangeProjectile")
    assert not find_effect(w, "RangeProjectile")
    assert not find_effect(w, "Attack")
    top = w["effect"]["effects"]
    assert [effect["type"] for effect in top[:4]] == [
        "CasterAnimation",
        "Sfx",
        "CasterViewEffect",
        "Delayed",
    ]
    delayed = direct_effects(w["effect"], "Delayed")
    assert len(delayed) == 1 and delayed[0]["tick"] == 8
    delayed_effects = delayed[0]["effects"]
    assert delayed_effects[0] == {
        "type": "Native",
        "effect_ref": "lol_yone_w_cone_native",
    }
    assert not direct_effects(w["effect"], "Native")
    settle = delayed_effects[1:]
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


def _retired_w_runtime_is_stateless_and_cannot_cross_game_contexts() -> None:
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


def test_058_stable_runtime_leaves_encyclopedia_to_the_stock_runner() -> None:
    cargo = (MOD / "Cargo.toml").read_text(encoding="utf-8")
    rust = (MOD / "src/stable_runtime.rs").read_text(encoding="utf-8")
    assert 'path = "src/stable_runtime.rs"' in cargo
    assert "declare_stable_mod!(init, requires = mod_api_stable::ABI_LEVEL);" in rust
    assert "registration.set_extension(QualityBpExtension::default());" in rust
    assert rust.count("registration.set_extension(") == 1
    assert "registration.set_server_extension(" not in rust
    for forbidden in (
        "sync_encyclopedia",
        "find_encyclopedia_container",
        "ui_set_champion_icon",
        "encyclopedia_native_icon",
        "lol_fullbody_xayah",
        "lol_fullbody_yone",
    ):
        assert forbidden not in rust
    assert "fn post_render" not in rust
    assert "draw_encyclopedia" not in rust
    assert "encyclopedia_render_proof" not in rust
    assert "draw_sprite(" not in rust
    assert "YoneManagementCardExtension" not in rust
    assert "YoneSpiritCleaveConeNativeEffect" not in rust

    runtime_paths = {
        row["path"]
        for row in json.loads(
            (MOD / "runtime_manifest.json").read_text(encoding="utf-8")
        )["files"]
    }
    assert not any(path.startswith("ui/champion_fullbody/") for path in runtime_paths)
    assert not any(
        path.startswith("ui/layout/champion_info_component/")
        for path in runtime_paths
    )
    assert not any(path.startswith("ui/champion_portrait/") for path in runtime_paths)

    override = json.loads((MOD / "mod.override_info").read_text(encoding="utf-8"))
    assert "asset/base/ui/layout/champion_info_component/champion_slot" not in override
    champion = load_yone()
    assert champion["sprite"] == "asset/lol_mod/aseprite_resources/champions/yone_v7"
    assert override["asset/base/aseprite_resources/champions/dual_blader#sheet"] == {
        "remapping": "asset/lol_mod/aseprite_resources/champions/yone_v7#sheet",
        "type": "override",
    }
    assert override["asset/base/aseprite_resources/champions/dual_blader#anim"] == {
        "remapping": "asset/lol_mod/aseprite_resources/champions/yone_v7#anim",
        "type": "override",
    }



def _retired_q_is_hit_gated_three_stage_and_q3_is_one_real_dash_hit() -> None:
    q = load_yone()["skill"]
    assert (
        q["action_name"],
        q["cooltime"],
        q["duration"],
        q["start_timing"],
        q["range"],
        q["casting_type"],
        q["casting_target"],
    ) == ("skill", 240, 30, 0, 35000, "Targeting", "EnemyChampion")

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
        assert [effect["type"] for effect in stage["effects"]] == [
            "CasterAnimation",
            "Sfx",
            "Delayed",
        ]
        assert find_effect(stage, "CasterAnimation") == [
            {"type": "CasterAnimation", "name": "skill_q12", "tick": 30}
        ]
        assert not find_effect(stage, "CasterViewEffect")
        delayed = direct_effects(stage, "Delayed")
        assert len(delayed) == 1 and delayed[0]["tick"] == 8
        assert [effect["type"] for effect in delayed[0]["effects"]] == [
            "LinearProjectile"
        ]
        assert not direct_effects(stage, "LinearProjectile")
        projectiles = find_effect(
            delayed[0], "LinearProjectile", name="lol_yone_q_projectile"
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
            10000,
            30000,
            {"Circle": {"radius": 6000}},
            "EnemyWithoutTower",
        )
        assert [
            (hit["damage"], hit["attack_ratio"])
            for hit in find_effect(projectile, "Attack")
        ] == [(35, 95)]
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
    assert [effect["type"] for effect in q3["effects"]] == [
        "CasterAnimation",
        "Sfx",
        "Delayed",
    ]
    assert find_effect(q3, "CasterAnimation") == [
        {"type": "CasterAnimation", "name": "skill_q3", "tick": 30}
    ]
    assert not find_effect(q3, "CasterViewEffect")
    q3_delayed = direct_effects(q3, "Delayed")
    assert len(q3_delayed) == 1 and q3_delayed[0]["tick"] == 8
    assert [effect["type"] for effect in q3_delayed[0]["effects"]] == [
        "RemoveCasterBuff",
        "RushTime",
    ]
    assert q3_delayed[0]["effects"][0] == {
        "type": "RemoveCasterBuff",
        "name": "lol_yone_mortal_steel_stack_2",
    }
    assert not direct_effects(q3, "RemoveCasterBuff")
    assert not direct_effects(q3, "RushTime")
    assert not direct_effects(q3, "LinearProjectile")
    rushes = find_effect(q3, "RushTime")
    assert len(rushes) == 1
    rush = rushes[0]
    assert (
        rush["penetrate"],
        rush["speed"],
        rush["tick"],
        rush["range"],
        rush["casting_target"],
    ) == (True, 5000, 12, 30000, "EnemyWithoutTower")
    assert not find_effect(q3, "LinearProjectile")
    assert [
        (hit["damage"], hit["attack_ratio"])
        for hit in find_effect(q3, "Attack")
    ] == [(35, 95)]
    assert [cc["duration"] for cc in find_effect(q3, "Airborne")] == [45]
    projectile_views = {
        view["name"]: view for view in load_yone()["view_projectiles"]
    }
    assert set(projectile_views) == {"lol_yone_q_projectile"}
    assert find_effect(q3, "ViewEffect", name="lol_yone_q3_airborne_cue") == [
        {"type": "ViewEffect", "name": "lol_yone_q3_airborne_cue"}
    ]
    assert [effect["tick"] for effect in find_effect(q, "Delayed")] == [8, 8, 8]


def test_r_is_delayed_penetrating_line_aoe_with_one_damage_and_pull() -> None:
    r = load_yone()["ult"]
    assert (
        r["action_name"],
        r["cooltime"],
        r["duration"],
        r["start_timing"],
        r["range"],
        r["casting_type"],
        r["casting_target"],
    ) == ("ult", 3000, 60, 0, 55000, "Direction", "EnemyWithoutTower")
    assert not find_effect(r, "RushMoveToBack")
    outer_delayed = direct_effects(r["effect"], "Delayed")
    assert len(outer_delayed) == 1 and outer_delayed[0]["tick"] == 35
    rushes = find_effect(outer_delayed[0], "RushTime")
    assert len(rushes) == 1
    rush = rushes[0]
    assert (
        rush["speed"],
        rush["tick"],
        rush["range"],
        rush["casting_target"],
        rush["penetrate"],
    ) == (4000, 30, 20000, "EnemyWithoutTower", True)
    assert [cc["duration"] for cc in find_effect(rush, "Airborne")] == [45]
    assert not find_effect(rush, "Stun")
    assert [
        (hit["damage"], hit["attack_ratio"])
        for hit in find_effect(rush, "Attack")
    ] == [(120, 70)]
    assert not find_effect(r, "FixedAttack")
    assert [view["name"] for view in find_effect(rush, "ViewEffect")] == [
        "lol_yone_r_slash_blue",
        "lol_yone_r_knockup",
        "lol_yone_r_slash_red",
    ]
    pull_delays = find_effect(rush, "Delayed")
    assert [delay["tick"] for delay in pull_delays] == [5, 12]
    pull_delay = next(delay for delay in pull_delays if delay["tick"] == 12)
    assert find_effect(pull_delay, "Pull") == [
        {"type": "Pull", "speed": 3000, "tick": 12}
    ]
    assert find_effect(pull_delay, "TargetSfx") == [
        {"type": "TargetSfx", "name": "lol_yone_r_echo"}
    ]
    assert find_effect(outer_delayed[0], "CasterViewEffect") == [
        {"type": "CasterViewEffect", "name": "lol_yone_r_launch"}
    ]
    assert not find_effect(r, "Native")
    for forbidden in ("RandomTarget", "AutoTargetProjectile", "RangeEffect"):
        assert not find_effect(r, forbidden)


def _retired_yone_effect_and_audio_names_cover_active_w_and_contain_no_e_assets() -> None:
    yone = load_yone()

    projectiles = {view["name"]: view for view in yone["view_projectiles"]}
    assert set(projectiles) == {"lol_yone_q_projectile"}
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
        "lol_yone_r_slash_blue",
        "lol_yone_r_slash_red",
    }
    assert required_views == set(views)
    assert {
        "lol_yone_attack_steel_swing",
        "lol_yone_attack_azakana_swing",
        "lol_yone_q_blade",
        "lol_yone_q3_blade",
    }.isdisjoint(views)
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


def _retired_w_runtime_visuals_are_compact_and_have_separate_shield_tag() -> None:
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
    assert YONE_ACTIVE_ANIM.is_file()
    assert YONE_ACTIVE_SHEET.is_file()
    assert YONE_LEGACY_ANIM.is_file()
    assert YONE_LEGACY_SHEET.is_file()
    assert YONE_LEGACY_ANIM.read_bytes() == YONE_ACTIVE_ANIM.read_bytes()
    assert YONE_LEGACY_SHEET.read_bytes() == YONE_ACTIVE_SHEET.read_bytes()
    overrides = json.loads(
        (MOD / "mod.override_info").read_text(encoding="utf-8")
    )
    assert overrides[
        "asset/base/aseprite_resources/champions/dual_blader#sheet"
    ]["remapping"] == (
        "asset/lol_mod/aseprite_resources/champions/yone_v7#sheet"
    )
    assert overrides[
        "asset/base/aseprite_resources/champions/dual_blader#anim"
    ]["remapping"] == (
        "asset/lol_mod/aseprite_resources/champions/yone_v7#anim"
    )
    rust = (MOD / "src/lib.rs").read_text(encoding="utf-8")
    actor_textures = rust.split(
        "const YONE_ACTOR_SHEET_TEXTURES", 1
    )[1].split("];", 1)[0]
    for route in (
        "asset/base/aseprite_resources/champions/dual_blader#sheet",
        "asset/lol_mod/aseprite_resources/champions/yone_v7#sheet",
        "asset/lol_mod/aseprite_resources/champions/yone#sheet",
    ):
        assert route in actor_textures
    actor_anim = json.loads(
        YONE_ACTIVE_ANIM.read_text(encoding="utf-8")
    )["anims"]
    assert "skill2_attack" in actor_anim
    assert len(actor_anim["skill2_attack"]["frames"]) == 5
    actor_sheet = Image.open(YONE_ACTIVE_SHEET).convert("RGBA")
    assert actor_sheet.size == (4262, 88)
    assert list(actor_anim)[:13] == [
        "skill2", "hit", "attack", "skill2_dash", "ult", "run",
        "ult_hit_effect", "skill2_attack", "idle", "hit_effect_area",
        "dead", "skill_projectile", "skill",
    ]
    assert list(actor_anim)[13:] == [
        "attack_steel", "attack_azakana", "skill_q12", "skill_q3",
        "skill_w_azakana", "ult_fate_sealed",
    ]
    fate_sealed = actor_anim["ult_fate_sealed"]["frames"]
    assert sum(frame["duration"] for frame in fate_sealed) == pytest.approx(1.0)
    assert sum(frame["duration"] for frame in fate_sealed[:7]) == pytest.approx(0.58)
    fate_sealed_metrics: list[tuple[int, int, int]] = []
    for frame in fate_sealed:
        data = frame["data"]
        rendered = actor_sheet.crop(
            (
                data["x"],
                data["y"],
                data["x"] + data["w"],
                data["y"] + data["h"],
            )
        )
        alpha = rendered.getchannel("A")
        bbox = alpha.getbbox()
        assert bbox is not None
        opaque_pixels = sum(1 for value in alpha.get_flattened_data() if value)
        fate_sealed_metrics.append(
            (bbox[2] - bbox[0], bbox[3] - bbox[1], opaque_pixels)
        )
    assert all(height >= 34 for _width, height, _opaque in fate_sealed_metrics)
    assert all(opaque >= 560 for _width, _height, opaque in fate_sealed_metrics)
    fate_heights = [height for _width, height, _opaque in fate_sealed_metrics]
    assert max(
        abs(fate_heights[index] - fate_heights[index - 1])
        for index in range(len(fate_heights))
    ) <= 4
    assert fate_sealed_metrics[5][0] >= 24
    assert fate_sealed_metrics[5][1] >= 34
    assert fate_sealed_metrics[5][2] >= 560
    assert fate_sealed_metrics[6][0] >= 50
    assert fate_sealed_metrics[6][1] >= 37
    assert fate_sealed_metrics[6][2] >= 850

    r_effect_anim = json.loads(
        (MOD / "aseprite_resources/effects/yone_r#anim.fanim").read_text(
            encoding="utf-8"
        )
    )["anims"]
    assert list(r_effect_anim) == [
        "windup",
        "launch",
        "knockup",
        "slash_blue",
        "slash_red",
    ]
    assert "arrival" not in r_effect_anim
    assert Image.open(
        MOD / "aseprite_resources/effects/yone_r#sheet.png"
    ).size == (864, 352)
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
    assert 70 <= fullbody_bbox[2] - fullbody_bbox[0] <= 76
    assert 76 <= fullbody_bbox[3] - fullbody_bbox[1] <= 84
    assert fullbody_bbox[3] == 88
    assert fullbody.height - fullbody_bbox[3] == 5
    assert abs(fullbody_bbox[0] - (fullbody.width - fullbody_bbox[2])) <= 1
    fullbody_alpha = fullbody.getchannel("A")
    fullbody_pixels = (
        fullbody_alpha.get_flattened_data()
        if hasattr(fullbody_alpha, "get_flattened_data")
        else fullbody_alpha.getdata()
    )
    assert sum(1 for alpha in fullbody_pixels if alpha) >= 2300


def test_yone_v7_ui_is_source_direct_and_never_enlarges_battle_frames() -> None:
    source_path = MOD / "source/imagegen/yone_v7_ui_source.png"
    with Image.open(source_path) as opened:
        assert opened.width >= 800
        assert opened.height >= 1000

    builder_source = (MOD / "tools/build_yone.py").read_text(encoding="utf-8")
    build_ui = _python_function_source(builder_source, "build_splash_and_portraits")
    assert "load_yone_v7_ui_subject()" in build_ui
    assert "render_source_direct_ui_subject(" in build_ui
    assert "(85, 93)" in build_ui
    assert "_load_native_v7_body_frames" not in build_ui
    assert "Image.Resampling.NEAREST" not in build_ui

    card_contract = _python_function_source(
        builder_source, "yone_fullbody_card_contract"
    )
    assert "source.size != (85, 93)" in card_contract
    assert "rendered = source.copy()" in card_contract
    assert ".resize(" not in card_contract

    card_preview = Image.open(MOD / "qa/yone_v7_ui_card.png").convert("RGBA")
    assert card_preview.size == (141, 138)
    assert card_preview.getchannel("A").getextrema() == (255, 255)


def test_localized_copy_matches_reference_q_w_r_and_removes_soul_unbound() -> None:
    payload = json.loads(
        (MOD / "text/champion.i18n").read_text(encoding="utf-8")
    )
    for locale in ("en", "zh-hans", "zh-hant", "ja", "ko"):
        description = payload[locale]["description"]["dual_blader"]
        skill = description["skill"]
        skill2 = description["skill2"]
        ult = description["ult"]
        assert skill.startswith("Q")
        assert skill2.startswith("W")
        assert "E—" not in skill2 and "E —" not in skill2
        assert "Soul Unbound" not in skill2
        assert "灵体" not in skill2 and "靈體" not in skill2
        assert not any(stage in skill for stage in ("Q1", "Q2", "Q3"))
        for disclosed_value in ("25000", "75", "80", "0.75", "5%", "5"):
            assert disclosed_value in skill
        for disclosed_value in ("35000", "80", "20", "3", "8"):
            assert disclosed_value in skill2
        for disclosed_value in ("120", "70", "0.75", "50"):
            assert disclosed_value in ult


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

    # These full-body images are offline art audits, not runtime card overlays.
    # The stock ChampionInfoUIRunner exclusively resolves the actor idle frame.
    override = json.loads((MOD / "mod.override_info").read_text(encoding="utf-8"))
    runtime_manifest = json.loads(
        (MOD / "runtime_manifest.json").read_text(encoding="utf-8")
    )
    assert "asset/base/ui/layout/champion_info_component/champion_slot" not in override
    assert not any(
        row["path"].startswith(("ui/champion_fullbody/", "ui/layout/champion_info_component/"))
        for row in runtime_manifest["files"]
    )

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
    expected_run_bottom_clearances = [13, 14, 15, 14, 13, 14, 15, 14]
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

    generated_run_poses = []
    for index in range(8):
        frame = Image.open(
            MOD / f"source/native/yone_v7/frames/run_{index:02d}.png"
        ).convert("RGBA")
        normalized = Image.new("RGBA", (61, 55), (0, 0, 0, 0))
        normalized.alpha_composite(
            frame,
            ((normalized.width - frame.width) // 2, normalized.height - frame.height),
        )
        generated_run_poses.append(hashlib.sha256(normalized.tobytes()).hexdigest())
    assert len(set(generated_run_poses)) == 8

    generator = (MOD / "tools/generate_yone_v7_native.py").read_text(
        encoding="utf-8"
    )
    assert '"run": tuple(("motion", index) for index in range(5, 13))' in generator
    assert '"run_pose"' not in generator
    assert "RUN_POSE_SOURCES" not in generator
    assert "recompose_run_articulated_pair" not in generator
    assert "canonical_forward_lean_ratio" not in generator
    assert 'preserve_authored_weapon_geometry=action == "run"' in generator
    assert '"authored_transformed_mask_only"' in generator
    assert "straighten_run_subject" not in generator
    for required in (
        "RUN_LOWER_BODY_DONORS",
        "RUN_LOWER_BODY_MIRRORED",
        "RUN_SUPPORT_LEGS",
        "compose_authored_run_lower_body",
        "authored_run_pair_mirror_match",
        '"authored_lower_body_half_cycle_mirror"',
        "authored_weapon_pixels_unchanged_after_lower_body_edit",
        "source_pixel_only",
    ):
        assert required in generator
    for forbidden in (
        "RUN_FOOT_TARGETS",
        "repair_run_lower_body",
        "_draw_native_run_leg",
        "draw.line(path",
        '"final_native_roi_two_leg_cycle"',
    ):
        assert forbidden not in generator


@pytest.mark.parametrize("weapon", ["steel", "azakana"])
def test_yone_run_weapon_recolour_cannot_add_afterimage_pixels(weapon: str) -> None:
    generator = _load_yone_v7_generator()
    image = Image.new("RGBA", (9, 9), (0, 0, 0, 0))
    image.putpixel((1, 1), (33, 44, 55, 255))
    mask = Image.new("L", image.size, 0)
    mask_points = {(3, 6), (4, 5), (5, 4), (6, 3)}
    for point in mask_points:
        mask.putpixel(point, 255)
        image.putpixel(point, (123, 111, 99, 255))

    before_alpha = image.getchannel("A").tobytes()
    before_outside = {
        (x, y): image.getpixel((x, y))
        for y in range(image.height)
        for x in range(image.width)
        if (x, y) not in mask_points
    }
    generator._paint_native_weapon(
        image,
        weapon,
        mask,
        hand=(3, 6),
        tip=(6, 3),
        preserve_authored_geometry=True,
    )

    assert image.getchannel("A").tobytes() == before_alpha
    assert {
        (x, y): image.getpixel((x, y))
        for y in range(image.height)
        for x in range(image.width)
        if (x, y) not in mask_points
    } == before_outside
    assert {
        image.getpixel(point) for point in mask_points
    } <= set(generator.WEAPON_COLORS[weapon])


def _yone_run_validator_inputs():
    module_path = MOD / "tools/validate_yone_v7.py"
    spec = importlib.util.spec_from_file_location("test_validate_yone_v7", module_path)
    assert spec is not None and spec.loader is not None
    validator = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = validator
    spec.loader.exec_module(validator)
    native_root = MOD / "source/native/yone_v7"
    manifest = json.loads((native_root / "frames.json").read_text(encoding="utf-8"))
    rows = {
        (row["action"], row["index"]): row
        for row in manifest["frames"]
        if row["action"] == "run"
    }
    frames = {
        key: Image.open(native_root / row["file"]).convert("RGBA")
        for key, row in rows.items()
    }
    palette = validator.load_palette(native_root / "palette.json")
    return validator, frames, palette, rows


def test_yone_run_final_pngs_have_grounded_even_support_and_moving_legs() -> None:
    validator, frames, palette, rows = _yone_run_validator_inputs()
    report = validator._validate_run_png_gait(frames, palette, rows)
    assert report["source"] == "final native PNG pixels; generator audit not consulted"
    assert report["support_leg_sequence"] == ["right"] * 4 + ["left"] * 4
    assert report["lower_body_unique_poses_per_half"] == [4, 4]
    for row in report["lower_body_reports"]:
        assert row["ground_clearance_px"][row["support_leg"]] == 0
        assert min(row["leg_pixel_counts"].values()) >= 24


def test_yone_run_final_png_gate_rejects_floating_but_still_mirrored_legs() -> None:
    validator, frames, palette, rows = _yone_run_validator_inputs()
    report = validator._validate_run_png_gait(frames, palette, rows)
    anchors = {
        index: pair[field]
        for pair in report["pair_reports"]
        for index, field in (
            (pair["source_index"], "source_pelvis"),
            (pair["mirrored_index"], "mirrored_pelvis"),
        )
    }
    weapon_colors = frozenset(
        color
        for ramp in validator.EXPECTED_WEAPON_PALETTE_ROLES.values()
        for role_names in ramp.values()
        for role in role_names
        for color in palette.exact_role(role)
    )
    for key, original in frames.items():
        index = key[1]
        pelvis = anchors[index]
        ground = original.height - rows[key]["bottom_margin"] - 1
        moved = original.copy()
        points = {
            (x, y): original.getpixel((x, y))
            for y in range(ground - 8, ground + 1)
            for x in range(max(1, pelvis - 11), min(original.width - 1, pelvis + 12))
            if original.getpixel((x, y))[3]
            and original.getpixel((x, y)) not in weapon_colors
        }
        for point in points:
            moved.putpixel(point, (0, 0, 0, 0))
        for (x, y), color in points.items():
            if original.getpixel((x, y - 1)) not in weapon_colors:
                moved.putpixel((x, y - 1), color)
        frames[key] = moved
    with pytest.raises(validator.V7ValidationError, match="ungrounded support"):
        validator._validate_run_png_gait(frames, palette, rows)


def test_yone_run_guard_and_basic_attacks_have_pixel_semantic_motion() -> None:
    qa = json.loads(
        (MOD / "source/native/yone_v7/generation_qa.json").read_text(
            encoding="utf-8"
        )
    )
    assert qa["failures"] == []
    contract = qa["motion_attack_contract"]
    assert contract["reference"]["workshop_item"] == "3774304166"
    assert contract["reference"]["usage"] == (
        "measurement-only; zero reference pixels copied"
    )
    assert contract["native_contract_preserved"] == {
        "run_frames": 8,
        "run_durations_seconds": [0.080000006] * 8,
        "attack_frames": 6,
        "attack_durations_seconds": [0.060000002] * 6,
    }

    run = contract["run"]
    assert run["pose_sources"] == [
        ["motion", index] for index in range(5, 13)
    ]
    assert sum(run["stride_pose_counts"].values()) == 8
    foot_separations = run["foot_separations_px"]
    assert len(foot_separations) == 8
    assert run["ground_anchor_range_px"] == 0
    assert run["torso_height_range_px"] <= 1
    assert run["body_visible_height_range_px"] <= 2
    assert run["upper_guard_lean_range_px"] <= 1.5
    assert run["canonical_art_direction"] == "right"
    assert run["runtime_direction_owner"] == (
        "native GameView flip_x; one canonical run action"
    )
    assert 1 <= run["mean_authored_forward_lean_px"] <= 2.5
    assert "mean_upper_guard_forward_lean_px" not in run
    assert run["hand_anchor_ranges_px"]["steel"]["x"] >= 2.5
    assert run["hand_anchor_ranges_px"]["steel"]["y"] >= 1.5
    assert run["hand_anchor_ranges_px"]["azakana"]["x"] >= 1.5
    assert run["hand_anchor_ranges_px"]["azakana"]["y"] >= 1
    assert max(run["maximum_adjacent_hand_step_px"].values()) <= 4
    assert max(run["maximum_adjacent_tip_step_px"].values()) <= 8
    assert max(run["maximum_adjacent_blade_angle_step_radians"].values()) <= 0.45
    assert min(run["minimum_blade_pixel_ratio"].values()) >= 0.4
    assert max(run["maximum_adjacent_blade_span_ratio"].values()) <= 2
    assert max(run["maximum_adjacent_blade_pixel_ratio"].values()) <= 1.9
    assert run["unique_body_pose_count"] == 8
    assert run["weapon_render_route"] == "authored_transformed_mask_only"
    assert run["authored_weapon_mask_identity"] == {
        "steel": True,
        "azakana": True,
    }
    assert run["authored_alpha_mask_unchanged"] is True
    assert run["leg_edit_route"] == "authored_lower_body_half_cycle_mirror"
    assert run["lower_body_donor_indices"] == [4, 5, 6, 7, 4, 5, 6, 7]
    assert run["lower_body_mirrored"] == [
        False, False, False, False, True, True, True, True
    ]
    assert run["outside_lower_body_roi_rgba_unchanged"] is True
    assert run[
        "authored_weapon_pixels_unchanged_after_lower_body_edit"
    ] is True
    assert run["source_pixel_only"] is True
    assert run["new_rgba_pixel_count"] == 0
    assert run["half_cycle_pair_mirror_match"] == [True, True, True, True]
    assert run["support_leg_sequence"] == [
        "right", "right", "right", "right", "left", "left", "left", "left"
    ]
    assert "four complete authored lower-body phases" in run["source"]
    assert "no drawn leg, resize, shear, hand-to-tip redraw, or afterimage" in run["source"]

    run_rows = sorted(
        (row for row in qa["frames"] if row["action"] == "run"),
        key=lambda row: row["index"],
    )
    assert len(run_rows) == 8
    assert [row["source"] for row in run_rows] == ["motion"] * 8
    assert [row["cell"] for row in run_rows] == list(range(5, 13))
    assert {row["body_visible_height_px"] for row in run_rows} == {35}
    assert {row["weapon_render_route"] for row in run_rows} == {
        "authored_transformed_mask_only"
    }
    assert all(
        row["authored_weapon_mask_identity"]
        == {"steel": True, "azakana": True}
        for row in run_rows
    )
    assert all(row["authored_alpha_mask_unchanged"] is True for row in run_rows)
    assert [row["lower_body_donor_index"] for row in run_rows] == [
        4, 5, 6, 7, 4, 5, 6, 7
    ]
    assert [row["lower_body_mirrored"] for row in run_rows] == [
        False, False, False, False, True, True, True, True
    ]
    assert all(
        row["leg_edit_route"] == "authored_lower_body_half_cycle_mirror"
        and row["outside_lower_body_roi_rgba_unchanged"] is True
        and row[
            "authored_weapon_pixels_unchanged_after_lower_body_edit"
        ] is True
        and row["source_pixel_only"] is True
        and row["new_rgba_pixel_count"] == 0
        and len(row["foot_zones"]) == 2
        for row in run_rows
    )
    assert [row["support_leg"] for row in run_rows] == run["support_leg_sequence"]
    png_contract = _assert_yone_run_final_png_contract()
    assert png_contract["pair_matches"] == [True, True, True, True]

    attacks = contract["attacks"]
    assert attacks["attack"]["source_cells"] == [0, 1, 3, 10, 11, 5]
    assert attacks["attack_azakana"]["source_cells"] == [0, 1, 2, 10, 6, 5]
    for action in ("attack", "attack_azakana"):
        row = attacks[action]
        assert row["pose_phases"] == [
            "windup",
            "windup",
            "contact",
            "contact",
            "recovery",
            "recovery",
        ]
        assert row["unique_body_pose_count"] == 6
        assert row["body_turn_span_px"] >= 1.25
        assert row["phase_unique_pose_counts"] == {
            "windup": 2,
            "contact": 2,
            "recovery": 2,
        }
        assert not ({12, 13, 14, 15, 16, 17} & set(row["source_cells"]))

    preview = Image.open(MOD / "qa/yone_motion_attack_qa.png").convert("RGBA")
    assert preview.size == (2080, 705)

    generator = (MOD / "tools/generate_yone_v7_native.py").read_text(
        encoding="utf-8"
    )
    assert "workshop\\content" not in generator.casefold()
    assert "workshop/content" not in generator.casefold()

    anims = json.loads(YONE_ACTIVE_ANIM.read_text(encoding="utf-8"))["anims"]
    runtime_sheet = Image.open(YONE_ACTIVE_SHEET).convert("RGBA")
    for action, count, duration in (
        ("run", 8, 0.080000006),
        ("attack", 6, 0.060000002),
        ("attack_azakana", 6, 0.060000002),
    ):
        runtime_frames = anims[action]["frames"]
        assert len(runtime_frames) == count
        assert [frame["duration"] for frame in runtime_frames] == [duration] * count
        for index, frame in enumerate(runtime_frames):
            data = frame["data"]
            runtime = runtime_sheet.crop(
                (
                    data["x"],
                    data["y"],
                    data["x"] + data["w"],
                    data["y"] + data["h"],
                )
            )
            source = Image.open(
                MOD / f"source/native/yone_v7/frames/{action}_{index:02d}.png"
            ).convert("RGBA")
            assert runtime.size == source.size
            assert runtime.tobytes() == source.tobytes()


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

    anim = json.loads(YONE_ACTIVE_ANIM.read_text(encoding="utf-8"))[
        "anims"
    ]["skill2_attack"]["frames"]
    sheet = Image.open(YONE_ACTIVE_SHEET).convert("RGBA")
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
    assert mod_info["version"] == "0.10.19"
    assert all(
        token in mod_info["description"]
        for token in ("Q1/Q2", "Q3", "W uses", "R keeps")
    )
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


def test_yone_v7_release_keeps_q_w_r_and_dual_sword_body_atomic() -> None:
    mod_info = json.loads((MOD / "mod.mod_info").read_text(encoding="utf-8"))
    assert mod_info["version"] == "0.12.17"
    assert all(
        token in mod_info["description"]
        for token in (
            "grounded authored lower-body phases",
            "pure-data Q/W/R",
            "no active E",
            "no-op saved-season compatibility shims",
        )
    )
    assert "E-only Soul Unbound" not in mod_info["description"]

    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert all(token in readme for token in ("Q1/Q2", "Q3", "W", "R"))
    assert all(
        token in readme
        for token in (
            "motion 5×4",
            "attack/Q 6×4",
            "steel_dark/mid/highlight",
            "azakana_dark/red/highlight",
            "手柄到刀尖",
            "v0.10.18：双剑动作结构已接入，但像素合同未完成",
        )
    )
    assert "Soul Unbound" not in readme

    assert 'version = "0.12.17"' in (MOD / "Cargo.toml").read_text(
        encoding="utf-8"
    )
    assert 'version = "0.12.17"' in (MOD / "Cargo.lock").read_text(
        encoding="utf-8"
    )
    quality_scope = json.loads(
        (MOD / "qa/quality_upgrade_scope.json").read_text(encoding="utf-8")
    )
    assert quality_scope["release"] == "0.12.17"
    pixel_contract = quality_scope["runtime_implemented"]["yone_official_009"][
        "dual_sword_pixel_contract"
    ]
    assert pixel_contract["release"] == "0.10.20"
    assert pixel_contract["strict_source_grids"] == {
        "motion": "5x4",
        "attack_q": "6x4",
        "w": "3x2",
        "ult": "5x3",
    }
    assert "failed pixel contract" in pixel_contract["historical_0_10_18"]

    champion_payload = (MOD / "champion/dual_blader.data_champion").read_text(
        encoding="utf-8"
    )
    for ability_runtime_prefix in (
        "lol_yone_q_",
        "lol_yone_w_",
        "lol_yone_r_",
    ):
        assert ability_runtime_prefix in champion_payload

    v7 = json.loads(
        (MOD / "source/native/yone_v7/frames.json").read_text(encoding="utf-8")
    )
    assert v7["schema_version"] == 7
    assert v7["route"] == "dual-sword-v7"
    assert v7["atlas_size"] == [4262, 88]
    assert len(v7["frames"]) == 67
    assert v7["weapon_contract"]["always_dual_actions"] == ["idle", "run"]
    assert all(
        row["face_visibility"] in {"front", "profile", "hidden"}
        and row["active_weapon"] in {"steel", "azakana", "dual"}
        and row["weapons_present"] == ["steel", "azakana"]
        for row in v7["frames"]
    )

    manifest = json.loads(
        (MOD / "build_manifest.json").read_text(encoding="utf-8")
    )
    paths = {row["path"].replace("\\", "/") for row in manifest["files"]}
    assert {
        "aseprite_resources/champions/yone_v7#anim.fanim",
        "aseprite_resources/champions/yone_v7#sheet.png",
        "aseprite_resources/champions/yone#anim.fanim",
        "aseprite_resources/champions/yone#sheet.png",
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
        "source/imagegen/yone_v6_motion_contact.png",
        "source/imagegen/yone_v6_attack_q_w_contact.png",
        "source/imagegen/yone_v6_w_contact.png",
        "source/imagegen/yone_v6_ult_contact.png",
    }.intersection(paths)
    assert not any(path.startswith("source/native/yone_v4/") for path in paths)
    assert not any(path.startswith("source/native/yone_v5/") for path in paths)
    assert not any(path.startswith("source/native/yone_v6/") for path in paths)
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
    for retired_v6_body in (
        "source/native/yone_v6",
        "source/imagegen/yone_v6_motion_contact.png",
        "source/imagegen/yone_v6_attack_q_w_contact.png",
        "source/imagegen/yone_v6_w_contact.png",
        "source/imagegen/yone_v6_ult_contact.png",
    ):
        assert not (MOD / retired_v6_body).exists(), retired_v6_body


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
