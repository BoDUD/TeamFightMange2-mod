#!/usr/bin/env python3
"""Static validation for Shen, Lucian/002, and Orianna/003."""

from __future__ import annotations

import array
import hashlib
import json
import math
import sys
import wave
from pathlib import Path
from typing import Any, Iterable

from PIL import Image


MOD_ROOT = Path(__file__).resolve().parents[1]
ERRORS: list[str] = []

ORIANNA_NATIVE_ANIMATION: dict[str, list[float]] = {
    "skill1": [0.080000006] * 5,
    "run": [0.080000006] * 8,
    "skill2": [0.080000006] * 5,
    "hit": [0.1],
    "ult": [0.080000006] * 4,
    "attack": [0.080000006] * 5,
    "dead": [0.1] * 9,
    "idle": [0.18, 0.14, 0.14, 0.14],
}

ORIANNA_VIEW_PROJECTILES: dict[str, tuple[str, str]] = {
    "lol_orianna_attack_dart": ("asset/lol_mod/aseprite_resources/effects/orianna_attack", "projectile"),
    "lol_orianna_q_ball": ("asset/lol_mod/aseprite_resources/effects/orianna_q_ball", "projectile"),
    "lol_orianna_q_field_visual": ("asset/lol_mod/aseprite_resources/effects/orianna_q_field", "field"),
    "lol_orianna_e_ball": ("asset/lol_mod/aseprite_resources/effects/orianna_e_shield", "projectile"),
    "lol_orianna_r_core": ("asset/lol_mod/aseprite_resources/effects/orianna_q_ball", "projectile"),
}

ORIANNA_VIEW_EFFECTS: dict[str, tuple[str, str, bool]] = {
    "lol_orianna_attack_hit_visual": (
        "asset/lol_mod/aseprite_resources/effects/orianna_attack",
        "impact",
        False,
    ),
    "lol_orianna_q_impact": ("asset/lol_mod/aseprite_resources/effects/orianna_q_field", "impact", False),
    "lol_orianna_r_ring_visual": ("asset/lol_mod/aseprite_resources/effects/orianna_r_ring", "ring", False),
    "lol_orianna_r_burst_visual": ("asset/lol_mod/aseprite_resources/effects/orianna_r_ring", "burst", False),
}

ORIANNA_VIEW_BUFFS: dict[str, tuple[str, str, str, str]] = {
    "lol_orianna_protect": (
        "asset/lol_mod/aseprite_resources/effects/orianna_e_shield",
        "impact",
        "loop",
        "break",
    ),
}


def check(condition: bool, message: str) -> None:
    if not condition:
        ERRORS.append(message)


def load_json(relative: str) -> Any:
    path = MOD_ROOT / relative
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as error:  # pragma: no cover - diagnostic path
        ERRORS.append(f"{relative}: cannot parse JSON: {error}")
        return {}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def opaque_rgb(image: Image.Image) -> list[tuple[int, int, int]]:
    rgba = image.convert("RGBA")
    return [
        (red, green, blue)
        for y in range(rgba.height)
        for x in range(rgba.width)
        for red, green, blue, alpha in [rgba.getpixel((x, y))]
        if alpha >= 128
    ]


def walk_effects(value: Any) -> Iterable[dict[str, Any]]:
    if isinstance(value, dict):
        if isinstance(value.get("type"), str):
            yield value
        for child in value.values():
            yield from walk_effects(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk_effects(child)


def find_effect(root: Any, effect_type: str, **fields: Any) -> list[dict[str, Any]]:
    return [
        effect
        for effect in walk_effects(root)
        if effect.get("type") == effect_type and all(effect.get(key) == value for key, value in fields.items())
    ]


def validate_data_contract(champion: dict[str, Any]) -> None:
    check(champion.get("id") == "lol_shen", "champion id must be lol_shen")
    check(champion.get("category") == "Melee", "Shen category must be Melee")
    check({"Melee", "Tank", "Shield", "CC"}.issubset(set(champion.get("tags", []))), "Shen role tags are incomplete")
    check(
        champion.get("skill_icons")
        == [
            "asset/lol_mod/icons/shen_skill",
            "asset/lol_mod/icons/shen_skill2",
            "asset/lol_mod/icons/shen_ult",
        ],
        "skill icon order must be Q/W/R",
    )
    expected_stats = {
        "hp": 1100,
        "attack": 75,
        "magic_power": 20,
        "defence": 40,
        "magic_resistance": 35,
        "move_speed": 1000,
    }
    for key, value in expected_stats.items():
        check(champion.get("stat", {}).get(key) == value, f"base stat {key} must be {value}")

    attack = champion.get("attack", {})
    check(attack.get("range") == 25000, "basic attack range must use engine units (25000)")
    check(attack.get("cooltime") == 70, "basic attack cooltime must be 70 ticks")

    q = champion.get("skill", {})
    check(q.get("range") == 60000 and q.get("cooltime") == 360, "Q range/cooltime mismatch")
    projectiles = find_effect(q, "LinearProjectile")
    check(len(projectiles) == 1, "Q must contain exactly one LinearProjectile")
    if projectiles:
        check(projectiles[0].get("penetrate") is True, "Q projectile must penetrate")
        check(projectiles[0].get("range") == 60000, "Q projectile range mismatch")
    q_slow = [
        effect
        for effect in find_effect(q, "AddBuff")
        if effect.get("buff_state", {}).get("name") == "lol_shen_twilight_assault_slow"
    ]
    check(bool(q_slow), "Q named slow marker is missing")
    if q_slow:
        check(q_slow[0]["buff_state"].get("move_speed_mult") == -25, "Q slow must be -25%")
        check(q_slow[0]["buff_state"].get("duration", {}).get("Time", {}).get("tick") == 90, "Q slow must last 90 ticks")
    q_shields = find_effect(q, "Shield", amount=120, tick=120)
    check(bool(q_shields), "Q on-hit self shield must be 120 for 120 ticks")

    w = champion.get("skill2", {})
    check(w.get("cooltime") == 480, "W cooldown must be 480 ticks")
    w_ranges = find_effect(w, "RangeEffect")
    ally_ranges = [effect for effect in w_ranges if effect.get("target") == "AllyChampion"]
    enemy_ranges = [effect for effect in w_ranges if effect.get("target") == "EnemyChampion"]
    check(len(ally_ranges) == 1 and len(enemy_ranges) == 1, "W must have one ally and one enemy range effect")
    for effect in w_ranges:
        check(effect.get("shape", {}).get("Circle", {}).get("radius") == 35000, "W radius must be 35000")
        check(effect.get("apply_type") == "AroundCaster", "W must apply around caster")
    w_shields = find_effect(ally_ranges, "Shield", amount=150, ap_ratio=40, tick=150)
    check(bool(w_shields), "W ally shield contract mismatch")
    w_slows = [
        effect
        for effect in find_effect(enemy_ranges, "AddBuff")
        if effect.get("buff_state", {}).get("name") == "lol_shen_spirit_refuge_as_slow"
    ]
    check(bool(w_slows), "W named attack-speed debuff is missing")
    if w_slows:
        check(w_slows[0]["buff_state"].get("attack_speed_mult") == -30, "W attack-speed debuff must be -30%")

    ult = champion.get("ult", {})
    check(ult.get("range") == 960000, "R range must be 960000")
    check(ult.get("cooltime") == 3000, "R cooldown must be 3000 ticks")
    check(ult.get("casting_target") == "AllyNotSelf", "R must target AllyNotSelf")
    check(bool(find_effect(ult, "Shield", amount=900, ap_ratio=80, tick=180)), "R shield contract mismatch")
    delayed = [effect for effect in find_effect(ult, "Delayed", tick=48)]
    check(len(delayed) == 1, "R must have one 48-tick arrival delay")
    if delayed:
        check(bool(find_effect(delayed[0], "Teleport")), "R delayed arrival must contain a real Teleport")
        check(bool(find_effect(delayed[0], "Taunt", duration=45)), "R delayed arrival must taunt for 45 ticks")
        arrive_sfx = [effect.get("name") for effect in find_effect(delayed[0], "Sfx")]
        check("lol_shen_r_arrive" in arrive_sfx, "R arrival SFX must be inside the 48-tick delay")

    serialized = json.dumps(champion, ensure_ascii=False)
    required_markers = {
        "lol_shen_twilight_assault_slow",
        "lol_shen_twilight_assault_guard",
        "lol_shen_spirit_refuge_shield_window",
        "lol_shen_spirit_refuge_as_slow",
        "lol_shen_stand_united_channel",
        "lol_shen_stand_united_shield_window",
        "lol_shen_stand_united_arrival_cc",
    }
    for marker in required_markers:
        check(marker in serialized, f"named state marker missing: {marker}")


def validate_orianna_replacement_uniqueness() -> None:
    ids: list[tuple[str, str]] = []
    for path in sorted((MOD_ROOT / "champion").glob("*.data_champion")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception as error:  # pragma: no cover - diagnostic path
            ERRORS.append(f"{path.relative_to(MOD_ROOT).as_posix()}: cannot parse JSON: {error}")
            continue
        champion_id = payload.get("id")
        if isinstance(champion_id, str):
            ids.append((champion_id, path.name))

    barrier_files = [filename for champion_id, filename in ids if champion_id == "barrier_magician"]
    check(
        barrier_files == ["barrier_magician.data_champion"],
        "Orianna must replace native 003 exactly once through champion/barrier_magician.data_champion",
    )
    check(
        all(champion_id != "lol_orianna" for champion_id, _ in ids),
        "lol_orianna must not be registered as an additive duplicate champion",
    )
    check(
        not (MOD_ROOT / "champion/lol_orianna.data_champion").exists(),
        "champion/lol_orianna.data_champion must be absent in same-ID replacement mode",
    )


def validate_orianna_data_contract(champion: dict[str, Any]) -> None:
    check(champion.get("id") == "barrier_magician", "Orianna must rework native champion 003 with id barrier_magician")
    check(
        champion.get("sprite") == "asset/lol_mod/aseprite_resources/champions/orianna",
        "same-ID Orianna must bind the custom Orianna actor",
    )
    check(champion.get("anim_prefix") == "", "Orianna must preserve native animation tags without a prefix")
    check(champion.get("category") == "Magician", "Orianna category must be Magician")
    check(
        set(champion.get("tags", [])) == {"AP", "Range", "Shield", "CC", "Magic"},
        "Orianna role tags must be AP/Range/Shield/CC/Magic",
    )
    check(
        champion.get("skill_icons")
        == [
            "asset/lol_mod/icons/orianna_skill",
            "asset/lol_mod/icons/orianna_skill2",
            "asset/lol_mod/icons/orianna_ult",
        ],
        "Orianna active icon order must be Q/E/R",
    )
    check(len(champion.get("skill_icons", [])) == 3, "Orianna must expose exactly three active icons")
    for unsupported_slot in ("w", "skill3", "skill4"):
        check(unsupported_slot not in champion, f"Orianna must not add unsupported active slot {unsupported_slot}")

    check(
        champion.get("stat")
        == {
            "attack": 80,
            "magic_power": 30,
            "hp": 900,
            "defence": 20,
            "magic_resistance": 20,
            "move_speed": 1000,
            "hp_regen": 2,
            "stack": 0,
            "crit_chance": 0,
        },
        "Orianna base stats do not match the approved design",
    )
    check(
        champion.get("growth")
        == {
            "attack": 6,
            "magic_power": 15,
            "hp": 100,
            "defence": 8,
            "magic_resistance": 4,
            "move_speed": 5,
            "hp_regen": 1,
            "stack": 0,
            "crit_chance": 0,
        },
        "Orianna growth stats do not match the approved design",
    )

    attack = champion.get("attack", {})
    check(
        (
            attack.get("action_name"),
            attack.get("range"),
            attack.get("cooltime"),
            attack.get("duration"),
            attack.get("start_timing"),
            attack.get("cancelable"),
            attack.get("casting_type"),
            attack.get("casting_target"),
            attack.get("attack_type"),
            attack.get("can_use_with_move"),
        )
        == ("attack", 60000, 90, 30, 24, True, "Targeting", "Enemy", "BaseAttack", False),
        "Orianna attack slot/timing/targeting mismatch",
    )
    attack_projectiles = find_effect(attack, "TargetProjectile", name="lol_orianna_attack_dart")
    check(len(attack_projectiles) == 1, "Orianna attack must fire exactly one named target projectile")
    if attack_projectiles:
        check(attack_projectiles[0].get("speed") == 4800, "Orianna attack projectile speed must be 4800")
    physical_attacks = find_effect(attack, "Attack")
    magic_attacks = find_effect(attack, "ApAttack")
    check(
        len(physical_attacks) == 1
        and physical_attacks[0].get("damage") == 0
        and physical_attacks[0].get("attack_ratio") == 100,
        "Orianna attack physical component must be 100% Attack",
    )
    check(
        len(magic_attacks) == 1
        and magic_attacks[0].get("damage") == 10
        and magic_attacks[0].get("attack_ratio") == 15,
        "Orianna attack magic component must be 10 + 15% Ability Power",
    )

    q = champion.get("skill", {})
    check(
        (
            q.get("action_name"),
            q.get("range"),
            q.get("cooltime"),
            q.get("duration"),
            q.get("start_timing"),
            q.get("cancelable"),
            q.get("casting_type"),
            q.get("casting_target"),
            q.get("attack_type"),
            q.get("can_use_with_move"),
        )
        == ("skill1", 70000, 360, 30, 24, False, "Targeting", "EnemyChampion", "Skill", False),
        "Orianna Q/W slot must preserve native skill1 timing and enemy-champion targeting",
    )
    q_projectiles = find_effect(q, "ParabolicProjectile", name="lol_orianna_q_ball")
    check(len(q_projectiles) == 1, "Orianna Q must contain exactly one parabolic command-ball projectile")
    check(not find_effect(q, "RangeProjectile"), "Orianna Q flight must not regress to a non-moving RangeProjectile")
    if q_projectiles:
        projectile = q_projectiles[0]
        check(
            (
                projectile.get("travel_time"),
                projectile.get("range"),
                projectile.get("shape", {}).get("Circle", {}).get("radius"),
                projectile.get("applied_target"),
            )
            == (15, 70000, 26000, "EnemyWithoutTower"),
            "Orianna Q ball travel/range/impact contract mismatch",
        )
    q_damage = find_effect(q, "ApAttack")
    check(
        len(q_damage) == 1 and q_damage[0].get("damage") == 50 and q_damage[0].get("attack_ratio") == 55,
        "Orianna Q impact damage must be 50 + 55% Ability Power exactly once",
    )
    q_fields = find_effect(q, "RangePeriodProjectile")
    check(len(q_fields) == 2, "Orianna Q/W must create exactly one ally field and one enemy field")
    fields_by_target = {field.get("applied_target"): field for field in q_fields}
    check(set(fields_by_target) == {"AllyChampion", "EnemyWithoutTower"}, "Orianna Q/W field targets are incorrect")
    for field in q_fields:
        check(
            (
                field.get("tick"),
                field.get("period"),
                field.get("first_delay"),
                field.get("shape", {}).get("Circle", {}).get("radius"),
            )
            == (180, 30, 0, 30000),
            "Orianna Q/W periodic field timing/radius mismatch",
        )
        check(field.get("end_effects") == [], "Orianna Q/W field must not add an unplanned expiry effect")

    ally_field = fields_by_target.get("AllyChampion", {})
    enemy_field = fields_by_target.get("EnemyWithoutTower", {})
    check(ally_field.get("name") == "lol_orianna_q_field_visual", "ally field must own the single ground visual")
    check(enemy_field.get("name") == "lol_orianna_q_field_enemy_logic", "enemy field must use a logic-only name")
    ally_move = [
        effect
        for effect in find_effect(ally_field, "AddBuff")
        if effect.get("buff_state", {}).get("name") == "lol_orianna_q_ally_move"
    ]
    enemy_move = [
        effect
        for effect in find_effect(enemy_field, "AddBuff")
        if effect.get("buff_state", {}).get("name") == "lol_orianna_q_enemy_move"
    ]
    check(len(ally_move) == 1, "Orianna Q/W ally move-speed buff is missing")
    check(len(enemy_move) == 1, "Orianna Q/W enemy slow is missing")
    if ally_move:
        state = ally_move[0].get("buff_state", {})
        check(state.get("move_speed_mult") == 18, "Orianna Q/W ally move speed must be +18%")
        check(state.get("duration", {}).get("Time", {}).get("tick") == 40, "Orianna Q/W ally refresh must last 40 ticks")
    if enemy_move:
        state = enemy_move[0].get("buff_state", {})
        check(state.get("move_speed_mult") == -22, "Orianna Q/W enemy move speed must be -22%")
        check(state.get("duration", {}).get("Time", {}).get("tick") == 40, "Orianna Q/W enemy refresh must last 40 ticks")

    ally_switches = find_effect(ally_field, "SwitchByLevel3")
    enemy_switches = find_effect(enemy_field, "SwitchByLevel3")
    check(len(ally_switches) == 1 and len(enemy_switches) == 1, "both Q/W fields must branch exactly once at level 3")
    for label, switches, buff_name, value in (
        ("ally", ally_switches, "lol_orianna_q_ally_attack_speed", 15),
        ("enemy", enemy_switches, "lol_orianna_q_enemy_attack_speed", -15),
    ):
        if not switches:
            continue
        switch = switches[0]
        check(
            switch.get("effect_start") == {"type": "Combine", "effects": []},
            f"Orianna Q/W {label} pre-level-3 branch must not add attack speed",
        )
        level3_buffs = [
            effect
            for effect in find_effect(switch.get("effect_level3", {}), "AddBuff")
            if effect.get("buff_state", {}).get("name") == buff_name
        ]
        check(len(level3_buffs) == 1, f"Orianna Q/W {label} level-3 attack-speed buff is missing")
        if level3_buffs:
            state = level3_buffs[0].get("buff_state", {})
            check(state.get("attack_speed_mult") == value, f"Orianna Q/W {label} attack-speed value mismatch")
            check(state.get("duration", {}).get("Time", {}).get("tick") == 40, f"Orianna Q/W {label} attack-speed refresh must last 40 ticks")

    e = champion.get("skill2", {})
    check(
        (
            e.get("action_name"),
            e.get("range"),
            e.get("cooltime"),
            e.get("duration"),
            e.get("start_timing"),
            e.get("cancelable"),
            e.get("casting_type"),
            e.get("casting_target"),
            e.get("attack_type"),
            e.get("can_use_with_move"),
        )
        == ("skill2", 70000, 480, 30, 24, False, "Targeting", "AllyChampion", "Skill", False),
        "Orianna E slot/timing/ally targeting mismatch",
    )
    e_projectiles = find_effect(e, "TargetProjectile", name="lol_orianna_e_ball")
    check(len(e_projectiles) == 1, "Orianna E must fire exactly one ball to the selected ally")
    if e_projectiles:
        check(
            e_projectiles[0].get("speed") == 6000 and e_projectiles[0].get("applied_target") == "AllyChampion",
            "Orianna E projectile speed/target mismatch",
        )
    e_shields = find_effect(e, "Shield")
    check(
        len(e_shields) == 1
        and (
            e_shields[0].get("amount"),
            e_shields[0].get("attack_ratio"),
            e_shields[0].get("ap_ratio"),
            e_shields[0].get("tick"),
        )
        == (180, 0, 55, 180),
        "Orianna E shield must be 180 + 55% Ability Power for 180 ticks",
    )
    protect = [
        effect
        for effect in find_effect(e, "AddBuff")
        if effect.get("buff_state", {}).get("name") == "lol_orianna_protect"
    ]
    check(len(protect) == 1, "Orianna E WithShield protection buff is missing")
    if protect:
        state = protect[0].get("buff_state", {})
        check(state.get("duration") == "WithShield", "Orianna E resistance buff must end WithShield")
        check(state.get("defence") == 12 and state.get("magic_resistance") == 12, "Orianna E must grant +12 armour and magic resistance")
        check(state.get("skill_damaged_reduce") == 15, "Orianna E skill damage reduction must be 15%")
        check(state.get("base_attack_damaged_reduce") == 10, "Orianna E base-attack damage reduction must be 10%")

    ult = champion.get("ult", {})
    check(
        (
            ult.get("action_name"),
            ult.get("range"),
            ult.get("cooltime"),
            ult.get("duration"),
            ult.get("start_timing"),
            ult.get("cancelable"),
            ult.get("casting_type"),
            ult.get("casting_target"),
            ult.get("attack_type"),
            ult.get("can_use_with_move"),
        )
        == ("ult", 75000, 3000, 30, 24, False, "Targeting", "EnemyChampion", "Skill", False),
        "Orianna R slot/timing/enemy targeting mismatch",
    )
    r_cores = find_effect(ult, "ParabolicProjectile", name="lol_orianna_r_core")
    check(len(r_cores) == 1, "Orianna R must establish exactly one fixed target-point core")
    r_core = r_cores[0] if r_cores else {}
    check(
        (
            r_core.get("travel_time"),
            r_core.get("range"),
            r_core.get("shape", {}).get("Circle", {}).get("radius"),
            r_core.get("applied_target"),
            r_core.get("applied_effects"),
        )
        == (1, 75000, 1, "EnemyChampion", []),
        "Orianna R core must capture the selected enemy position after a one-tick landing",
    )
    r_core_end = r_core.get("end_effects", [])
    check(isinstance(r_core_end, list), "Orianna R target-point core end_effects must be a list")
    if not isinstance(r_core_end, list):
        r_core_end = []
    barriers = [
        effect
        for effect in r_core_end
        if effect.get("type") == "ShrinkingBarrier" and effect.get("name") == "lol_orianna_r_ring_logic"
    ]
    check(len(barriers) == 1, "Orianna R must contain exactly one shrinking barrier")
    if barriers:
        barrier = barriers[0]
        check(
            (
                barrier.get("start_radius"),
                barrier.get("end_radius"),
                barrier.get("shrink_per_tick"),
                barrier.get("tick"),
                barrier.get("edge_thickness"),
            )
            == (60000, 18000, 700, 60, 6000),
            "Orianna R shrinking barrier values mismatch",
        )
        check("barrier_tick" not in barrier, "data-only ShrinkingBarrier must use tick, not native barrier_tick")
        check(bool(find_effect(barrier, "Bind", duration=8)), "Orianna R edge must apply an eight-tick bind")
    r_delays = [
        effect for effect in r_core_end if effect.get("type") == "Delayed" and effect.get("tick") == 60
    ]
    check(
        len(r_delays) == 1,
        "Orianna R barrier and tick-60 burst must be direct siblings at the same fixed Ball landing point",
    )
    delayed_effects = r_delays[0].get("effects", []) if r_delays else []
    burst_zones = [
        effect
        for effect in delayed_effects
        if effect.get("type") == "RangeProjectile" and effect.get("name") == "lol_orianna_r_burst_hitbox"
    ]
    check(len(burst_zones) == 1, "Orianna R final burst must use one delayed-position RangeProjectile")
    if burst_zones:
        burst = burst_zones[0]
        check(
            (
                burst.get("name"),
                burst.get("delay"),
                burst.get("apply"),
                burst.get("shape", {}).get("Circle", {}).get("radius"),
                burst.get("applied_target"),
            )
            == ("lol_orianna_r_burst_hitbox", 0, 1, 42000, "EnemyWithoutTower"),
            "Orianna R final hitbox timing/radius/target mismatch",
        )
        burst_damage = find_effect(burst, "ApAttack")
        check(
            len(burst_damage) == 1
            and burst_damage[0].get("damage") == 130
            and burst_damage[0].get("attack_ratio") == 100,
            "Orianna R must deal 130 + 100% Ability Power exactly once",
        )
        pulls = find_effect(burst, "Pull")
        check(
            len(pulls) == 1 and pulls[0].get("speed") == 3200 and pulls[0].get("tick") == 12,
            "Orianna R Pull must resolve inside the final hitbox at speed 3200 for 12 ticks",
        )
        check(bool(find_effect(burst, "Airborne", duration=24)), "Orianna R final hitbox must knock targets up for 24 ticks")
    check(len(find_effect(ult, "Pull")) == 1, "Orianna R must not contain an extra caster-directed Pull")

    projectile_views = champion.get("view_projectiles", [])
    projectile_names = [view.get("name") for view in projectile_views]
    check(len(projectile_names) == len(set(projectile_names)), "Orianna projectile view names must be unique")
    projectile_map = {view.get("name"): view for view in projectile_views}
    check(set(projectile_map) == set(ORIANNA_VIEW_PROJECTILES), "Orianna projectile view binding set is incomplete")
    for name, (anim_path, tag) in ORIANNA_VIEW_PROJECTILES.items():
        binding = projectile_map.get(name, {})
        check(
            binding.get("type") == "Animated"
            and binding.get("anim") == anim_path
            and binding.get("tag") == tag
            and binding.get("repeat") is True,
            f"Orianna projectile view binding mismatch: {name}",
        )
    for logic_only_name in ("lol_orianna_q_field_enemy_logic", "lol_orianna_r_ring_logic", "lol_orianna_r_burst_hitbox"):
        check(logic_only_name not in projectile_map, f"logic-only effect must not spawn a duplicate visual: {logic_only_name}")

    effect_views = champion.get("view_effects", [])
    effect_names = [view.get("name") for view in effect_views]
    check(len(effect_names) == len(set(effect_names)), "Orianna effect view names must be unique")
    effect_map = {view.get("name"): view for view in effect_views}
    triggered_effects = {effect.get("name") for effect in find_effect(champion, "ViewEffect")}
    check(triggered_effects == set(ORIANNA_VIEW_EFFECTS), "Orianna Q/E/R ViewEffect trigger set is incomplete")
    for name, (anim_path, tag, is_follow) in ORIANNA_VIEW_EFFECTS.items():
        binding = effect_map.get(name, {})
        check(
            binding.get("type") == "Animation"
            and binding.get("anim") == anim_path
            and binding.get("tag") == tag
            and binding.get("is_follow") is is_follow,
            f"Orianna effect view binding mismatch: {name}",
        )
    ring_binding = effect_map.get("lol_orianna_r_ring_visual", {})
    check(ring_binding.get("type") != "LoopAnimation", "Orianna R ring cannot use LoopAnimation because follow is ignored")

    buff_views = champion.get("view_buffs", [])
    buff_names = [view.get("name") for view in buff_views]
    check(len(buff_names) == len(set(buff_names)), "Orianna buff view names must be unique")
    buff_map = {view.get("name"): view for view in buff_views}
    check(set(buff_map) == set(ORIANNA_VIEW_BUFFS), "Orianna buff view binding set is incomplete")
    for name, (anim_path, pre_tag, loop_tag, remove_tag) in ORIANNA_VIEW_BUFFS.items():
        binding = buff_map.get(name, {})
        check(
            binding.get("type") == "ThreePhase"
            and binding.get("anim") == anim_path
            and binding.get("pre_tag") == pre_tag
            and binding.get("loop_tag") == loop_tag
            and binding.get("remove_tag") == remove_tag,
            f"Orianna buff view binding mismatch: {name}",
        )


def validate_lucian_data_contract(champion: dict[str, Any]) -> None:
    check(champion.get("id") == "archer", "Lucian must rework native champion 002 with id archer")
    check(
        champion.get("sprite") == "asset/lol_mod/aseprite_resources/champions/lucian",
        "same-id Lucian must bind the custom Lucian actor",
    )
    check(champion.get("category") == "Range", "Lucian category must be Range")
    check(set(champion.get("tags", [])) == {"AD", "Range"}, "Lucian role tags must be AD/Range")
    check(
        champion.get("skill_icons")
        == [
            "asset/lol_mod/icons/lucian_skill",
            "asset/lol_mod/icons/lucian_skill2",
            "asset/lol_mod/icons/lucian_ult",
        ],
        "Lucian skill icon order must be Q/E/R",
    )
    expected_stats = {
        "attack": 100,
        "magic_power": 0,
        "hp": 900,
        "defence": 20,
        "magic_resistance": 15,
        "move_speed": 900,
        "hp_regen": 2,
        "stack": 0,
        "crit_chance": 0,
    }
    expected_growth = {
        "attack": 13,
        "magic_power": 0,
        "hp": 90,
        "defence": 6,
        "magic_resistance": 3,
        "move_speed": 9,
        "hp_regen": 1,
        "stack": 0,
        "crit_chance": 0,
    }
    check(champion.get("stat") == expected_stats, "Lucian base stats do not match the design")
    check(champion.get("growth") == expected_growth, "Lucian growth stats do not match the design")

    attack = champion.get("attack", {})
    check(
        (attack.get("range"), attack.get("cooltime"), attack.get("duration"), attack.get("start_timing"))
        == (62000, 60, 24, 10),
        "Lucian attack range/timing mismatch",
    )
    switch = attack.get("effect", {})
    check(switch.get("type") == "SwitchByBuff", "Lucian attack must branch with SwitchByBuff")
    check(
        switch.get("buff_name") == "lol_lucian_lightslinger_ready",
        "Lucian attack must consume the Lightslinger marker",
    )
    empowered = switch.get("effect_buff", {})
    empowered_projectiles = find_effect(empowered, "TargetProjectile")
    check(len(empowered_projectiles) == 2, "Lightslinger must fire exactly two target projectiles")
    empowered_attacks = find_effect(empowered, "Attack")
    check(
        sorted(effect.get("attack_ratio") for effect in empowered_attacks) == [45, 100],
        "Lightslinger ratios must be 100% then 45% Attack",
    )
    empowered_delays = sorted(effect.get("tick") for effect in find_effect(empowered, "Delayed"))
    check(empowered_delays == [4, 10], "Lightslinger shots must be six ticks apart at ticks 4 and 10")
    check(
        bool(find_effect(empowered, "RemoveCasterBuff", name="lol_lucian_lightslinger_ready")),
        "Lightslinger empowered attack must consume its marker",
    )
    normal_projectiles = find_effect(switch.get("effect_none", {}), "TargetProjectile")
    check(len(normal_projectiles) == 1, "normal Lucian attack must fire one generated light bolt")
    projectile_views = {
        view.get("name"): view for view in champion.get("view_projectiles", [])
    }
    light_bolt = projectile_views.get("lol_lucian_light_bolt", {})
    check(
        light_bolt.get("anim") == "asset/lol_mod/aseprite_resources/effects/lucian_attack"
        and light_bolt.get("tag") == "projectile",
        "basic attack and Lightslinger must use the dedicated image-gen Lucian bolt",
    )

    q = champion.get("skill", {})
    check(
        (
            q.get("casting_type"),
            q.get("casting_target"),
            q.get("range"),
            q.get("cooltime"),
            q.get("start_timing"),
        )
        == ("Targeting", "EnemyWithoutTower", 65000, 300, 10),
        "Lucian Q targeting/range/timing mismatch",
    )
    check(not find_effect(q, "Delayed"), "Lucian Q must launch on the locked target direction without a delayed one-tick collision")
    check(not find_effect(q, "CasterAnimation"), "Lucian Q action must not restart its actor animation from inside the effect")
    q_projectiles = find_effect(q, "LinearProjectile", name="lol_lucian_q_piercing_light")
    check(len(q_projectiles) == 1, "Lucian Q must contain exactly one straight piercing projectile")
    check(not find_effect(q, "TargetProjectile"), "Lucian Q must not use a target-following projectile")
    check(
        not find_effect(q, "LineRangeProjectile"),
        "Lucian Q must not retain the direction-divergent delayed line area",
    )
    if q_projectiles:
        piercing_light = q_projectiles[0]
        check(
            (
                piercing_light.get("penetrate"),
                piercing_light.get("speed"),
                piercing_light.get("range"),
                piercing_light.get("shape", {}).get("Circle", {}).get("radius"),
            )
            == (True, 16000, 76000, 10000),
            "Lucian Q must be a fast 760-range non-homing line with a 100-radius hit lane",
        )
        check(piercing_light.get("applied_target") == "EnemyWithoutTower", "Lucian Q must hit champions/minions and exclude towers")
    q_attacks = find_effect(q, "Attack")
    check(
        len(q_attacks) == 1
        and q_attacks[0].get("damage") == 55
        and q_attacks[0].get("attack_ratio") == 85,
        "Lucian Q damage must be 55 + 85% Attack",
    )
    check(not find_effect(q, "CasterViewEffect"), "Lucian Q must not use a direction-blind caster-only beam")
    q_view = projectile_views.get("lol_lucian_q_piercing_light", {})
    check(
        q_view.get("anim") == "asset/lol_mod/aseprite_resources/effects/lucian_q"
        and q_view.get("tag") == "projectile"
        and q_view.get("repeat") is False,
        "Lucian Q damage and image-gen beam must share one projectile name and direction",
    )

    e = champion.get("skill2", {})
    check(
        (e.get("casting_type"), e.get("range"), e.get("cooltime"), e.get("duration"), e.get("start_timing"))
        == ("Direction", 30000, 420, 18, 4),
        "Lucian E direction/range/timing mismatch",
    )
    rush = find_effect(e, "RushTime")
    check(
        len(rush) == 1 and rush[0].get("speed") == 3000 and rush[0].get("tick") == 10,
        "Lucian E must dash 30000 units through RushTime",
    )
    check(not find_effect(e, "Attack") and not find_effect(e, "ApAttack"), "Lucian E must deal no damage")
    check(
        not find_effect(e, "CasterViewEffect"),
        "Lucian E must not spawn a release VFX",
    )
    check(
        not any(view.get("name") == "lol_lucian_dash_visual" for view in champion.get("view_effects", [])),
        "Lucian E retired afterimage must not remain in view_effects",
    )

    for action_name, action in (("Q", q), ("E", e)):
        ready = [
            effect
            for effect in find_effect(action, "AddCasterBuff")
            if effect.get("buff_state", {}).get("name") == "lol_lucian_lightslinger_ready"
        ]
        check(len(ready) == 1, f"Lucian {action_name} must activate Lightslinger exactly once")
        if ready:
            check(
                ready[0].get("buff_state", {}).get("duration", {}).get("Time", {}).get("tick") == 240,
                f"Lucian {action_name} Lightslinger duration must be 240 ticks",
            )

    ult = champion.get("ult", {})
    check(
        (ult.get("range"), ult.get("cooltime"), ult.get("duration"), ult.get("start_timing"))
        == (120000, 3600, 150, 12),
        "Lucian R range/timing mismatch",
    )
    check(ult.get("casting_type") == "Direction", "Lucian R must be a direction cast")
    check(ult.get("cancelable") is True, "Lucian R must be interruptible")
    check(ult.get("can_use_with_move") is False, "Lucian R must keep Lucian stationary")
    shot_delays = [
        effect
        for effect in find_effect(ult, "Delayed")
        if find_effect(effect, "LinearProjectile", name="lol_lucian_culling_shot")
    ]
    check(len(shot_delays) == 15, "Lucian R must fire exactly 15 projectiles")
    check(
        sorted(effect.get("tick") for effect in shot_delays) == list(range(12, 125, 8)),
        "Lucian R shots must run from tick 12 to 124 at eight-tick intervals",
    )
    for projectile in find_effect(ult, "LinearProjectile", name="lol_lucian_culling_shot"):
        check(projectile.get("penetrate") is False, "Lucian R bullets must not penetrate")
        check(projectile.get("speed") == 9000 and projectile.get("range") == 120000, "Lucian R projectile speed/range mismatch")
        check(projectile.get("shape", {}).get("Circle", {}).get("radius") == 4500, "Lucian R bullet radius must be 4500")
        attacks = find_effect(projectile, "Attack")
        check(
            len(attacks) == 1 and attacks[0].get("damage") == 8 and attacks[0].get("attack_ratio") == 18,
            "Lucian R bullet damage must be 8 + 18% Attack",
        )
    completion = [effect for effect in find_effect(ult, "Delayed", tick=132)]
    check(len(completion) == 1, "Lucian R must activate Lightslinger at tick 132")
    if completion:
        check(
            bool(
                [
                    effect
                    for effect in find_effect(completion[0], "AddCasterBuff")
                    if effect.get("buff_state", {}).get("name") == "lol_lucian_lightslinger_ready"
                ]
            ),
            "Lucian R completion marker is missing",
        )


def validate_archer_replacement(setting: dict[str, Any]) -> None:
    archer = setting.get("archer", {})
    base = load_json("source/base/champion_info_base.champion_info_sheet")
    check(set(setting) == set(base), "native replacement sheet must preserve every required base champion key")
    check(
        all(setting.get(key) == value for key, value in base.items() if key != "archer"),
        "native replacement sheet changed a base champion other than Archer/002",
    )
    check(not (MOD_ROOT / "champion/lol_lucian.data_champion").exists(), "unregistered lol_lucian data file must be removed")
    check(archer.get("category") == "Range", "Archer replacement category must remain Range")
    check(set(archer.get("tags", [])) == {"AD", "Range"}, "Archer replacement tags must be AD/Range")
    check(
        archer.get("stat")
        == {
            "attack": 100,
            "magic_power": 0,
            "hp": 900,
            "defence": 20,
            "magic_resistance": 15,
            "move_speed": 900,
            "hp_regen": 2,
            "stack": 0,
            "crit_chance": 0,
        },
        "Archer replacement base stats do not match Lucian v0.2",
    )
    check(
        archer.get("growth")
        == {
            "attack": 13,
            "magic_power": 0,
            "hp": 90,
            "defence": 6,
            "magic_resistance": 3,
            "move_speed": 9,
            "hp_regen": 1,
            "stack": 0,
            "crit_chance": 0,
        },
        "Archer replacement growth stats do not match Lucian v0.2",
    )
    attack = archer.get("attack", {})
    check(
        (attack.get("range"), attack.get("speed"), attack.get("cooltime"), attack.get("duration"), attack.get("start_timing"))
        == (62000, 6500, 60, 24, 10),
        "native Lucian attack values mismatch",
    )
    e = archer.get("skill", {})
    check(
        (
            e.get("attack"),
            e.get("attack_ratio"),
            e.get("move_range"),
            e.get("speed"),
            e.get("cooltime"),
            e.get("duration"),
            e.get("start_timing"),
        )
        == (0, 45, 30000, 3000, 420, 18, 4),
        "native Lucian E/Lightslinger approximation mismatch",
    )
    q = archer.get("skill2", {})
    check(
        (
            q.get("attack"),
            q.get("attack_ratio"),
            q.get("range"),
            q.get("projectile_speed"),
            q.get("move_range"),
            q.get("cooltime"),
            q.get("duration"),
            q.get("start_timing"),
        )
        == (55, 85, 65000, 15000, 0, 300, 24, 10),
        "native Lucian Q approximation mismatch",
    )
    ult = archer.get("ult", {})
    check(
        (
            ult.get("attack"),
            ult.get("attack_ratio"),
            ult.get("range"),
            ult.get("attack_range"),
            ult.get("interval"),
            ult.get("total_shots"),
            ult.get("speed"),
            ult.get("cooltime"),
            ult.get("duration"),
            ult.get("start_timing"),
            ult.get("cancelable"),
        )
        == (8, 18, 120000, 4500, 8, 15, 9000, 3600, 150, 12, True),
        "native Lucian R must be an interruptible 15-shot Archer channel",
    )


def validate_native_setting_override(override: dict[str, Any]) -> None:
    entry = override.get("asset/base/setting/champion_info", {})
    check(entry.get("type") == "override", "complete champion_info sheet must use override, not merge")
    check(
        entry.get("remapping") == "asset/lol_mod/setting/champion_info",
        "native champion_info override remapping is incorrect",
    )


def validate_native_archer_animation() -> None:
    sheet_path = MOD_ROOT / "aseprite_resources/champions/archer#sheet.png"
    anim = load_json("aseprite_resources/champions/archer#anim.fanim")
    sheet = Image.open(sheet_path).convert("RGBA")
    expected = {
        "ult_old": [0.080000006] * 7 + [0.1] * 4,
        "skill": [0.080000006] * 6,
        "ult_end": [0.080000006] * 3,
        "ult_projectile": [0.080000006],
        "hit": [0.1],
        "run": [0.080000006] * 8,
        "ult_loop": [0.030000001] * 4,
        "skill2": [0.080000006] * 7,
        "ult_pre": [0.080000006] * 3,
        "dead": [0.1] * 4 + [0.15] * 5,
        "old_ult_buff_effect": [0.1] * 4,
        "skill_attack": [0.080000006] * 3,
        "idle": [0.18, 0.14, 0.14, 0.14],
        "skill_dash": [0.080000006] * 3,
        "attack": [0.060000002] * 6,
        "old_ult_pre": [0.080000006] * 7,
    }
    check(set(anim.get("anims", {})) == set(expected), "Lucian must preserve every native Archer animation key")
    total_frames = sum(len(durations) for durations in expected.values())
    check(sheet.size == (total_frames * 64, 64), f"native Archer sheet must be {total_frames * 64}x64, got {sheet.size}")
    for tag, durations in expected.items():
        frames = anim.get("anims", {}).get(tag, {}).get("frames", [])
        check(len(frames) == len(durations), f"native Archer tag {tag} frame count changed")
        for frame, duration in zip(frames, durations):
            check(abs(float(frame.get("duration", -1)) - duration) < 1e-8, f"native Archer tag {tag} duration changed")
            data = frame.get("data", {})
            check(data.get("w") == 64 and data.get("h") == 64, f"native Archer tag {tag} must use 64x64 safe frames")
            check(data.get("x", -1) + 64 <= sheet.width, f"native Archer tag {tag} frame is out of bounds")

    run_frames = []
    for frame in anim.get("anims", {}).get("run", {}).get("frames", []):
        data = frame["data"]
        run_frames.append(sheet.crop((data["x"], 0, data["x"] + 64, 64)))
    hashes = [hashlib.sha256(frame.tobytes()).hexdigest() for frame in run_frames]
    check(len(set(hashes)) == 8, "native Archer run contract must contain eight unique Lucian phases")
    lower_sets = []
    for frame in run_frames:
        alpha = frame.getchannel("A")
        lower_sets.append({(x, y) for y in range(31, 46) for x in range(64) if alpha.getpixel((x, y)) >= 128})
    differences = []
    for current, following in zip(lower_sets, lower_sets[1:] + lower_sets[:1], strict=True):
        union = current | following
        differences.append(len(current ^ following) / len(union) if union else 0.0)
    if differences:
        check(min(differences) >= 0.06, "native Archer run phases are too similar to show crossing steps")

    idle = anim.get("anims", {}).get("idle", {}).get("frames", [])[0]["data"]
    idle_frame = sheet.crop((idle["x"], 0, idle["x"] + 64, 64))
    bbox = idle_frame.getchannel("A").getbbox()
    check(bbox is not None and 34 <= bbox[3] - bbox[1] <= 37, "native Archer idle is outside the 34-37px Lucian scale")
    if bbox:
        check(bbox[3] <= 46 and bbox[0] >= 2 and bbox[2] <= 62, "native Archer idle violates the safe frame/baseline")


def validate_orianna_native_animation(champion: dict[str, Any]) -> None:
    sprite = champion.get("sprite", "")
    prefix = "asset/lol_mod/"
    check(isinstance(sprite, str) and sprite.startswith(prefix), "Orianna sprite must be a local lol_mod animated asset")
    if not isinstance(sprite, str) or not sprite.startswith(prefix):
        return

    base = sprite.removeprefix(prefix)
    sheet_relative = f"{base}#sheet.png"
    anim_relative = f"{base}#anim.fanim"
    sheet_path = MOD_ROOT / sheet_relative
    check(sheet_path.is_file(), f"missing Orianna actor sheet: {sheet_relative}")
    anim = load_json(anim_relative)
    if not sheet_path.is_file():
        return
    sheet = Image.open(sheet_path).convert("RGBA")
    animations = anim.get("anims", {})
    check(
        set(animations) == set(ORIANNA_NATIVE_ANIMATION),
        "Orianna actor must preserve the exact native Barrier Mage animation tag set",
    )
    for tag, durations in ORIANNA_NATIVE_ANIMATION.items():
        frames = animations.get(tag, {}).get("frames", [])
        check(len(frames) == len(durations), f"Orianna native tag {tag} frame count changed")
        for index, (frame, duration) in enumerate(zip(frames, durations)):
            check(
                abs(float(frame.get("duration", -1)) - duration) < 1e-6,
                f"Orianna native tag {tag} frame {index} duration changed",
            )
            data = frame.get("data", {})
            x = int(data.get("x", -1))
            y = int(data.get("y", -1))
            width = int(data.get("w", 0))
            height = int(data.get("h", 0))
            check(x >= 0 and y >= 0 and width > 0 and height > 0, f"Orianna native tag {tag} has an invalid frame rectangle")
            check(x + width <= sheet.width and y + height <= sheet.height, f"Orianna native tag {tag} frame is out of bounds")


def validate_orianna_v2_visual_contract() -> None:
    """Keep the reviewed v2 face, feet, scale and non-Ball attack read."""

    style = load_json("style/champion_view.champion_view")
    compact_view = style.get("entries", {}).get("barrier_magician", {})
    check(
        compact_view.get("face") == {"x": 0, "y": -34},
        "Orianna compact portrait offset must remain face x=0/y=-34",
    )
    check(
        compact_view.get("center") == {"x": 0, "y": -12},
        "Orianna card/battle center offset must remain center x=0/y=-12",
    )

    actor_path = MOD_ROOT / "aseprite_resources/champions/orianna#sheet.png"
    check(actor_path.is_file(), "missing Orianna actor sheet for v2 visual QA")
    if not actor_path.is_file():
        return

    actor = Image.open(actor_path).convert("RGBA")
    animations = load_json("aseprite_resources/champions/orianna#anim.fanim").get("anims", {})
    check(actor.size == (2624, 64), f"Orianna actor sheet must remain 2624x64, got {actor.size}")

    def frames_for(tag: str) -> list[Image.Image]:
        result: list[Image.Image] = []
        for frame in animations.get(tag, {}).get("frames", []):
            data = frame.get("data", {})
            x = int(data.get("x", -1))
            y = int(data.get("y", -1))
            width = int(data.get("w", 0))
            height = int(data.get("h", 0))
            if x >= 0 and y >= 0 and width > 0 and height > 0 and x + width <= actor.width and y + height <= actor.height:
                result.append(actor.crop((x, y, x + width, y + height)))
        return result

    idle_frames = frames_for("idle")
    run_frames = frames_for("run")
    check(len(idle_frames) == 4, "Orianna v2 visual QA requires four idle frames")
    check(len(run_frames) == 8, "Orianna v2 visual QA requires eight run frames")

    # The first two idle poses are the compact-card identity frames.  Their
    # 38px body height and y=42 exclusive foot baseline keep the face large
    # enough to read while leaving two complete boots above the UI crop.
    for index, frame in enumerate(idle_frames[:2]):
        alpha = frame.getchannel("A")
        bbox = alpha.getbbox()
        check(bbox is not None, f"Orianna primary idle {index} is empty")
        if bbox is None:
            continue
        width = bbox[2] - bbox[0]
        height = bbox[3] - bbox[1]
        check(height == 38, f"Orianna primary idle {index} must retain the reviewed 38px visible height")
        check(bbox[3] == 42, f"Orianna primary idle {index} must end at the exclusive y=42 foot baseline")
        check(16 <= width <= 24, f"Orianna primary idle {index} no longer has the compact full-body width")

        bottom_rows = range(max(bbox[1], bbox[3] - 3), bbox[3])
        bottom_x = sorted(
            {
                x
                for y in bottom_rows
                for x in range(bbox[0], bbox[2])
                if alpha.getpixel((x, y)) >= 128
            }
        )
        segments: list[list[int]] = []
        for x in bottom_x:
            if not segments or x > segments[-1][-1] + 1:
                segments.append([x])
            else:
                segments[-1].append(x)
        bottom_area = sum(
            alpha.getpixel((x, y)) >= 128
            for y in bottom_rows
            for x in range(bbox[0], bbox[2])
        )
        check(
            len(segments) >= 2 and sum(len(segment) >= 4 for segment in segments) >= 2 and bottom_area >= 24,
            f"Orianna primary idle {index} must keep two complete, separated boots above the baseline",
        )

        # Measure a bbox-relative upper-face area instead of pinning exact eye
        # coordinates.  The gate requires sizeable porcelain/light and
        # hair/outline clusters, a spatial cyan-eye cluster and strong local
        # luminance edges, so a muddy downsample cannot pass on one lucky pixel.
        margin = max(1, round(width * 0.10))
        face_box = (
            bbox[0] + margin,
            bbox[1],
            bbox[2] - margin,
            min(bbox[3], bbox[1] + max(8, round(height * 0.50))),
        )
        face_pixels: list[tuple[int, int, int, int]] = []
        cyan_positions: list[tuple[int, int]] = []
        for y in range(face_box[1], face_box[3]):
            for x in range(face_box[0], face_box[2]):
                red, green, blue, alpha_value = frame.getpixel((x, y))
                if alpha_value < 128:
                    continue
                face_pixels.append((red, green, blue, alpha_value))
                if green >= 100 and blue >= 115 and blue >= red + 20 and green >= red + 10:
                    cyan_positions.append((x, y))

        porcelain = sum(
            max(red, green, blue) >= 150 and max(red, green, blue) - min(red, green, blue) <= 90
            for red, green, blue, _ in face_pixels
        )
        dark_outline = sum(max(red, green, blue) <= 90 for red, green, blue, _ in face_pixels)
        luminances = [
            (299 * red + 587 * green + 114 * blue) / 1000
            for red, green, blue, _ in face_pixels
        ]
        strong_edges = 0
        opaque_pairs = 0
        for y in range(face_box[1], face_box[3]):
            for x in range(face_box[0], face_box[2]):
                red, green, blue, alpha_value = frame.getpixel((x, y))
                if alpha_value < 128:
                    continue
                luminance = (299 * red + 587 * green + 114 * blue) / 1000
                for dx, dy in ((1, 0), (0, 1)):
                    if x + dx >= face_box[2] or y + dy >= face_box[3]:
                        continue
                    other = frame.getpixel((x + dx, y + dy))
                    if other[3] < 128:
                        continue
                    other_luminance = (299 * other[0] + 587 * other[1] + 114 * other[2]) / 1000
                    opaque_pairs += 1
                    strong_edges += abs(luminance - other_luminance) >= 35

        cyan_span = (
            max(x for x, _ in cyan_positions) - min(x for x, _ in cyan_positions)
            if cyan_positions
            else 0
        )
        dynamic_range = max(luminances) - min(luminances) if luminances else 0
        edge_ratio = strong_edges / opaque_pairs if opaque_pairs else 0
        check(len(face_pixels) >= 160, f"Orianna primary idle {index} face area became too small")
        check(porcelain >= 25, f"Orianna primary idle {index} lost its readable porcelain face plane")
        check(dark_outline >= 70, f"Orianna primary idle {index} lost its dark hair/outline separation")
        check(
            len(cyan_positions) >= 3 and cyan_span >= 2,
            f"Orianna primary idle {index} must retain a multi-pixel cyan eye cluster",
        )
        check(dynamic_range >= 170, f"Orianna primary idle {index} face contrast regressed")
        check(edge_ratio >= 0.25, f"Orianna primary idle {index} face edges became too soft or muddy")

    # Upright commands may squash slightly, but must stay in the same readable
    # actor class and share the corrected exclusive y=42 baseline.
    for tag in ("idle", "attack", "skill1", "skill2"):
        for index, frame in enumerate(frames_for(tag)):
            bbox = frame.getchannel("A").getbbox()
            check(bbox is not None, f"Orianna {tag} frame {index} is empty")
            if bbox is None:
                continue
            height = bbox[3] - bbox[1]
            check(34 <= height <= 39, f"Orianna {tag} frame {index} left the reviewed 34-39px actor scale class")
            check(bbox[3] == 42, f"Orianna {tag} frame {index} changed the exclusive y=42 foot baseline")

    run_hashes: list[str] = []
    run_areas: list[int] = []
    for index, frame in enumerate(run_frames):
        alpha = frame.getchannel("A")
        bbox = alpha.getbbox()
        check(bbox is not None, f"Orianna run frame {index} is empty")
        if bbox is None:
            continue
        width = bbox[2] - bbox[0]
        height = bbox[3] - bbox[1]
        check(height == 38, f"Orianna run frame {index} must retain the reviewed 38px visible height")
        check(bbox[3] == 42, f"Orianna run frame {index} must end at the exclusive y=42 foot baseline")
        check(18 <= width <= 30, f"Orianna run frame {index} left the compact 18-30px footprint")
        lower_area = sum(
            alpha.getpixel((x, y)) >= 128
            for y in range(max(bbox[1], bbox[3] - 10), bbox[3])
            for x in range(bbox[0], bbox[2])
        )
        contact_area = sum(
            alpha.getpixel((x, y)) >= 128
            for y in range(max(bbox[1], bbox[3] - 3), bbox[3])
            for x in range(bbox[0], bbox[2])
        )
        check(lower_area >= 60 and contact_area >= 8, f"Orianna run frame {index} loses boot/lower-leg detail")
        run_areas.append(
            sum(
                alpha.getpixel((x, y)) >= 128
                for y in range(frame.height)
                for x in range(frame.width)
            )
        )
        run_hashes.append(hashlib.sha256(frame.tobytes()).hexdigest())

    check(len(set(run_hashes)) == len(run_frames), "Orianna run cycle must keep eight distinct v2 gait phases")
    if run_areas:
        mean_area = sum(run_areas) / len(run_areas)
        area_cv = (
            sum((area - mean_area) ** 2 for area in run_areas) / len(run_areas)
        ) ** 0.5 / mean_area
        check(area_cv <= 0.10, f"Orianna run body area jumps too much between frames: CV={area_cv:.1%}")

    attack_path = MOD_ROOT / "aseprite_resources/effects/orianna_attack#sheet.png"
    check(attack_path.is_file(), "missing Orianna basic-attack energy-dart sheet")
    if not attack_path.is_file():
        return
    attack = Image.open(attack_path).convert("RGBA")
    attack_anims = load_json("aseprite_resources/effects/orianna_attack#anim.fanim").get("anims", {})
    check(attack.size == (256, 32), f"Orianna attack VFX sheet must remain 256x32, got {attack.size}")

    def attack_frames_for(tag: str) -> list[Image.Image]:
        result: list[Image.Image] = []
        for frame in attack_anims.get(tag, {}).get("frames", []):
            data = frame.get("data", {})
            x = int(data.get("x", -1))
            y = int(data.get("y", -1))
            width = int(data.get("w", 0))
            height = int(data.get("h", 0))
            if x >= 0 and y >= 0 and width > 0 and height > 0 and x + width <= attack.width and y + height <= attack.height:
                result.append(attack.crop((x, y, x + width, y + height)))
        return result

    projectiles = attack_frames_for("projectile")
    impacts = attack_frames_for("impact")
    check(len(projectiles) == 4, "Orianna basic attack must keep four energy-dart travel phases")
    check(len(impacts) == 4, "Orianna basic attack must keep four impact/fade phases")
    projectile_hashes: list[str] = []
    for index, frame in enumerate(projectiles):
        projectile_hashes.append(hashlib.sha256(frame.tobytes()).hexdigest())
        bbox = frame.getchannel("A").getbbox()
        check(bbox is not None, f"Orianna attack energy dart {index} is empty")
        if bbox is None:
            continue
        width = bbox[2] - bbox[0]
        height = bbox[3] - bbox[1]
        check(
            24 <= width <= 30 and 10 <= height <= 15 and width / height >= 1.70,
            f"Orianna attack travel frame {index} must remain a large elongated energy dart, not a Ball",
        )
        pixels = opaque_rgb(frame)
        cyan = sum(blue >= red + 20 and green >= red + 10 and blue >= 110 for red, green, blue in pixels)
        brass = sum(red >= blue + 25 and green >= blue + 5 and red >= 120 for red, green, blue in pixels)
        bright = sum(max(red, green, blue) >= 180 for red, green, blue in pixels)
        check(
            len(pixels) >= 120
            and bright >= 55
            and cyan / len(pixels) >= 0.15
            and brass / len(pixels) >= 0.12,
            f"Orianna attack travel frame {index} lost its cyan/brass energy identity",
        )
    check(len(set(projectile_hashes)) == 4, "Orianna attack must keep four distinct ImageGen travel phases")
    for index, frame in enumerate(impacts):
        bbox = frame.getchannel("A").getbbox()
        check(bbox is not None, f"Orianna attack impact frame {index} is empty")
        if bbox is None:
            continue
        width = bbox[2] - bbox[0]
        height = bbox[3] - bbox[1]
        check(
            width >= 22 and height >= (16 if index == 3 else 22) and 0.85 <= width / height <= 1.50,
            f"Orianna attack impact frame {index} must remain a readable compact contact spark",
        )


def validate_orianna_resources_and_manifest(champion: dict[str, Any]) -> None:
    prefix = "asset/lol_mod/"
    required_manifest_paths = {"champion/barrier_magician.data_champion"}
    animation_cache: dict[str, dict[str, Any]] = {}

    def require_animation(asset: Any, tag: Any, label: str) -> None:
        check(isinstance(asset, str) and asset.startswith(prefix), f"{label} must use a local lol_mod animation asset")
        if not isinstance(asset, str) or not asset.startswith(prefix):
            return
        base = asset.removeprefix(prefix)
        sheet_relative = f"{base}#sheet.png"
        anim_relative = f"{base}#anim.fanim"
        required_manifest_paths.update({sheet_relative, anim_relative})
        sheet_path = MOD_ROOT / sheet_relative
        anim_path = MOD_ROOT / anim_relative
        check(sheet_path.is_file(), f"missing {label} sheet: {sheet_relative}")
        check(anim_path.is_file(), f"missing {label} animation: {anim_relative}")
        if not anim_path.is_file():
            return
        if anim_relative not in animation_cache:
            animation_cache[anim_relative] = load_json(anim_relative)
        check(
            isinstance(tag, str) and tag in animation_cache[anim_relative].get("anims", {}),
            f"{label} references missing animation tag {tag!r}",
        )

    require_animation(champion.get("sprite"), "idle", "Orianna actor")

    for icon_asset in champion.get("skill_icons", []):
        check(isinstance(icon_asset, str) and icon_asset.startswith(prefix), "Orianna icon must use a local lol_mod asset")
        if not isinstance(icon_asset, str) or not icon_asset.startswith(prefix):
            continue
        relative = f"{icon_asset.removeprefix(prefix)}.png"
        required_manifest_paths.add(relative)
        path = MOD_ROOT / relative
        check(path.is_file(), f"missing Orianna icon: {relative}")
        if path.is_file():
            icon = Image.open(path).convert("RGBA")
            check(icon.size == (64, 64), f"{relative} must be 64x64")
            check(icon.getchannel("A").getbbox() is not None, f"{relative} must not be empty")

    for view in champion.get("view_projectiles", []):
        if view.get("type") == "Animated":
            require_animation(view.get("anim"), view.get("tag"), f"Orianna projectile {view.get('name')}")
    for view in champion.get("view_effects", []):
        if view.get("type") in {"Animation", "LoopAnimation"}:
            require_animation(view.get("anim"), view.get("tag"), f"Orianna effect {view.get('name')}")
    for view in champion.get("view_buffs", []):
        if view.get("type") == "Animated":
            require_animation(view.get("anim"), view.get("tag"), f"Orianna buff {view.get('name')}")
        elif view.get("type") == "ThreePhase":
            for field in ("pre_tag", "loop_tag", "remove_tag"):
                require_animation(
                    view.get("anim"),
                    view.get(field),
                    f"Orianna buff {view.get('name')} {field}",
                )

    manifest = load_json("build_manifest.json")
    manifest_paths = {row.get("path") for row in manifest.get("files", [])}
    missing_manifest_paths = sorted(required_manifest_paths - manifest_paths)
    check(
        not missing_manifest_paths,
        "Orianna runtime resources are missing from build_manifest.json: " + ", ".join(missing_manifest_paths),
    )


def validate_archer_skill_icon_atlas() -> None:
    atlas = Image.open(MOD_ROOT / "aseprite_resources/UI_aseprite/skill_icon#sheet.png").convert("RGBA")
    check(atlas.size == (4096, 49), f"patched native skill icon atlas must remain 4096x49, got {atlas.size}")
    icon_paths = {
        "archer_0": "icons/lucian_skill2.png",
        "archer_1": "icons/lucian_skill.png",
        "archer_2": "icons/lucian_ult.png",
        "archer_3": "icons/lucian_skill.png",
        "archer_4": "icons/lucian_ult.png",
    }
    boxes = {
        "archer_0": (25, 0, 49, 24),
        "archer_1": (1625, 0, 1649, 24),
        "archer_2": (3225, 0, 3249, 24),
        "archer_3": (750, 24, 774, 48),
        "archer_4": (2350, 24, 2374, 48),
    }
    for key, relative in icon_paths.items():
        expected = Image.open(MOD_ROOT / relative).convert("RGBA").resize((24, 24), Image.Resampling.LANCZOS)
        actual = atlas.crop(boxes[key])
        check(actual.tobytes() == expected.tobytes(), f"native skill icon cell {key} does not contain generated Lucian art")


def validate_animation(sheet_relative: str, anim_relative: str, required: dict[str, int]) -> None:
    sheet_path = MOD_ROOT / sheet_relative
    anim = load_json(anim_relative)
    check(sheet_path.is_file(), f"missing sheet: {sheet_relative}")
    if not sheet_path.is_file():
        return
    image = Image.open(sheet_path).convert("RGBA")
    for tag, minimum_frames in required.items():
        frames = anim.get("anims", {}).get(tag, {}).get("frames", [])
        check(len(frames) >= minimum_frames, f"{anim_relative}: tag {tag} has too few frames")
        for frame in frames:
            data = frame.get("data", {})
            x, y, width, height = (data.get("x", -1), data.get("y", -1), data.get("w", 0), data.get("h", 0))
            check(x >= 0 and y >= 0 and width > 0 and height > 0, f"{anim_relative}: invalid frame rectangle in {tag}")
            check(x + width <= image.width and y + height <= image.height, f"{anim_relative}: out-of-bounds frame in {tag}")


def validate_actor_and_icons(champion: dict[str, Any]) -> None:
    actor_path = MOD_ROOT / "aseprite_resources/champions/shen#sheet.png"
    actor = Image.open(actor_path).convert("RGBA")
    check(actor.size == (1152, 64), f"actor sheet must be 1152x64, got {actor.size}")
    bboxes = []
    hashes = []
    for index in range(18):
        frame = actor.crop((index * 64, 0, (index + 1) * 64, 64))
        bbox = frame.getchannel("A").getbbox()
        check(bbox is not None, f"actor frame {index} is empty")
        if bbox:
            bboxes.append(bbox)
            check(bbox[3] <= 46, f"actor frame {index} crosses the official y=45 foot baseline")
            check(bbox[0] >= 2 and bbox[2] <= 62, f"actor frame {index} touches a side edge")
        hashes.append(hashlib.sha256(frame.tobytes()).hexdigest())
    if bboxes:
        core_heights = [bbox[3] - bbox[1] for bbox in bboxes[:17]]
        check(max(core_heights) / min(core_heights) <= 1.22, "core actor body scale varies by more than 22%")
        first = bboxes[0]
        check(first[1] <= 12 and 44 <= first[3] <= 46 and first[3] - first[1] >= 34, "first idle frame does not match the official full-body baseline")
    check(len(set(hashes[2:11])) == 9, "run cycle must contain nine unique image-gen poses")
    check(hashes[2] != hashes[10], "run cycle first and last poses must not be identical")
    check(len(set(hashes[11:14])) == 3, "attack source poses must be visually distinct")

    run_frames = [actor.crop((index * 64, 0, (index + 1) * 64, 64)) for index in range(2, 11)]
    lower_sets: list[set[tuple[int, int]]] = []
    lower_counts: list[int] = []
    for frame in run_frames:
        alpha = frame.getchannel("A")
        pixels = {(x, y) for y in range(32, 46) for x in range(64) if alpha.getpixel((x, y)) >= 128}
        lower_sets.append(pixels)
        lower_counts.append(len(pixels))
    if lower_counts:
        check(min(lower_counts) >= max(lower_counts) * 0.45, "a run frame loses too much lower-body/leg detail")
    differences = []
    for current, following in zip(lower_sets, lower_sets[1:] + lower_sets[:1], strict=True):
        union = current | following
        differences.append(len(current ^ following) / len(union) if union else 0.0)
    if differences:
        check(min(differences) >= 0.08, "adjacent run frames are too similar to show a gait phase")
        check(max(differences) <= 0.85, "adjacent run frames change too abruptly")

    for icon_path in champion.get("skill_icons", []):
        relative = icon_path.removeprefix("asset/lol_mod/") + ".png"
        path = MOD_ROOT / relative
        check(path.is_file(), f"missing icon: {relative}")
        if path.is_file():
            icon = Image.open(path)
            check(icon.size == (64, 64), f"{relative} must be 64x64")
            check(icon.convert("RGBA").getchannel("A").getbbox() is not None, f"{relative} is empty")


def validate_lucian_actor_and_icons(champion: dict[str, Any]) -> None:
    actor_path = MOD_ROOT / "aseprite_resources/champions/lucian#sheet.png"
    actor = Image.open(actor_path).convert("RGBA")
    check(actor.size == (1344, 64), f"Lucian actor sheet must be 1344x64, got {actor.size}")
    actor_anim = load_json("aseprite_resources/champions/lucian#anim.fanim").get("anims", {})
    skill_frames = actor_anim.get("skill", {}).get("frames", [])
    check(
        len(skill_frames) == 10
        and all(frame.get("data", {}).get("w") == 64 for frame in skill_frames),
        "Lucian Q actor animation must remain body-only 64px frames",
    )
    bboxes: list[tuple[int, int, int, int]] = []
    hashes: list[str] = []
    for index in range(21):
        frame = actor.crop((index * 64, 0, (index + 1) * 64, 64))
        bbox = frame.getchannel("A").getbbox()
        check(bbox is not None, f"Lucian actor frame {index} is empty")
        if bbox:
            bboxes.append(bbox)
            check(bbox[3] <= 46, f"Lucian actor frame {index} crosses the y=45 foot baseline")
            check(bbox[0] >= 2 and bbox[2] <= 62, f"Lucian actor frame {index} touches a side edge")
        hashes.append(hashlib.sha256(frame.tobytes()).hexdigest())
    if bboxes:
        idle = bboxes[0]
        idle_height = idle[3] - idle[1]
        idle_width = idle[2] - idle[0]
        idle_center = (idle[0] + idle[2] - 1) / 2
        check(idle_height == 36, "Lucian idle must match Shen's 36px native visible height")
        check(22 <= idle_width <= 25, "Lucian idle must retain the rebuilt full-body gunslinger width")
        check(44 <= idle[3] <= 46, "Lucian idle does not use the y=45 foot baseline")
        check(29 <= idle_center <= 34, "Lucian idle is not horizontally centered")
    for idle_index in (0, 1):
        idle_frame = actor.crop((idle_index * 64, 0, (idle_index + 1) * 64, 64))
        alpha = idle_frame.getchannel("A")
        face_pixels = [
            idle_frame.getpixel((x, y))
            for y in range(8, 25)
            for x in range(22, 42)
        ]
        warm_skin = sum(
            alpha_value >= 128 and red >= green + 25 and green >= blue + 5
            for red, green, blue, alpha_value in face_pixels
        )
        cool_eye = sum(
            alpha_value >= 128 and max(red, green, blue) >= 160 and blue >= red + 5
            for red, green, blue, alpha_value in face_pixels
        )
        dark_hair = sum(
            alpha_value >= 128 and max(red, green, blue) <= 80
            for red, green, blue, alpha_value in face_pixels
        )
        check(
            warm_skin >= 30 and cool_eye >= 6 and dark_hair >= 40,
            f"Lucian idle {idle_index} face must retain readable skin, eye and hair clusters without pixel injection",
        )
        boot_x = [x for x in range(64) if alpha.getpixel((x, 44)) >= 128]
        boot_segments: list[list[int]] = []
        for x in boot_x:
            if not boot_segments or x > boot_segments[-1][-1] + 1:
                boot_segments.append([x])
            else:
                boot_segments[-1].append(x)
        check(
            len(boot_segments) == 2
            and min(len(segment) for segment in boot_segments) >= 4
            and boot_segments[1][0] - boot_segments[0][-1] >= 3,
            f"Lucian idle {idle_index} must show two complete separated boots",
        )
    check(len(set(hashes[2:11])) == 9, "Lucian run cycle must contain nine unique frames")
    check(hashes[2] != hashes[10], "Lucian run cycle endpoints must be visually distinct")
    check(len(set(hashes[11:14])) == 3, "Lucian right/left/double shots must be distinct")
    check(
        bboxes[19][2] - bboxes[19][0] <= 28,
        "Lucian hit/fall frame must not widen back into the rejected two-pistol pose",
    )
    check(
        bboxes[20][2] - bboxes[20][0] <= 40,
        "Lucian defeated frame must keep a compact one-pistol silhouette",
    )

    run_frames = [actor.crop((index * 64, 0, (index + 1) * 64, 64)) for index in range(2, 11)]
    run_bboxes = [frame.getchannel("A").getbbox() for frame in run_frames]
    run_areas: list[int] = []
    for index, bbox in enumerate(run_bboxes, start=1):
        if bbox:
            width = bbox[2] - bbox[0]
            height = bbox[3] - bbox[1]
            check(27 <= width <= 32, f"Lucian run {index} must stay inside Shen's compact 27-32px footprint")
            check(height == 36, f"Lucian run {index} must keep Shen's 36px visible height")
            check(bbox[3] == 45, f"Lucian run {index} must keep Shen's y=44 foot pixels")
        alpha = run_frames[index - 1].getchannel("A")
        run_areas.append(
            sum(
                alpha.getpixel((x, y)) >= 128
                for y in range(run_frames[index - 1].height)
                for x in range(run_frames[index - 1].width)
            )
        )
    if run_areas:
        mean_area = sum(run_areas) / len(run_areas)
        area_cv = (
            sum((area - mean_area) ** 2 for area in run_areas) / len(run_areas)
        ) ** 0.5 / mean_area
        check(area_cv <= 0.08, f"Lucian run body area jumps too much between frames: CV={area_cv:.1%}")
    lower_sets: list[set[tuple[int, int]]] = []
    for frame in run_frames:
        alpha = frame.getchannel("A")
        lower_sets.append(
            {(x, y) for y in range(31, 46) for x in range(64) if alpha.getpixel((x, y)) >= 128}
        )
    lower_counts = [len(pixels) for pixels in lower_sets]
    if lower_counts:
        check(
            min(lower_counts) >= max(lower_counts) * 0.75,
            "Lucian run must not contain a residual-anchored or missing-lower-body frame",
        )
    differences = []
    for current, following in zip(lower_sets, lower_sets[1:] + lower_sets[:1], strict=True):
        union = current | following
        differences.append(len(current ^ following) / len(union) if union else 0.0)
    if differences:
        check(min(differences) >= 0.15, "Lucian adjacent run frames are too similar to show cross-steps")
        check(max(differences) <= 0.60, "Lucian adjacent run frames change too abruptly")

    for icon_path in champion.get("skill_icons", []):
        relative = icon_path.removeprefix("asset/lol_mod/") + ".png"
        path = MOD_ROOT / relative
        check(path.is_file(), f"missing Lucian icon: {relative}")
        if path.is_file():
            icon = Image.open(path).convert("RGBA")
            check(icon.size == (64, 64), f"{relative} must be 64x64")
            check(icon.getchannel("A").getbbox() == (0, 0, 64, 64), f"{relative} must be full-bleed")


def validate_compact_view_and_w_layout() -> None:
    style = load_json("style/champion_view.champion_view")
    shen = style.get("entries", {}).get("lol_shen", {})
    check(shen.get("face") == {"x": 6, "y": -34}, "compact portrait must center Shen's head at face x=6/y=-34")
    check(shen.get("center") == {"x": 0, "y": -12}, "battle/card center offset must remain x=0/y=-12")

    w_path = MOD_ROOT / "aseprite_resources/effects/shen_w#sheet.png"
    w_sheet = Image.open(w_path).convert("RGBA")
    check(w_sheet.size == (672, 64), f"W sheet must be 672x64, got {w_sheet.size}")
    for index in range(6):
        frame = w_sheet.crop((index * 112, 0, (index + 1) * 112, 64))
        bbox = frame.getchannel("A").getbbox()
        check(bbox is not None, f"W frame {index} is empty")
        if not bbox:
            continue
        width = bbox[2] - bbox[0]
        height = bbox[3] - bbox[1]
        center_x = (bbox[0] + bbox[2] - 1) / 2
        center_y = (bbox[1] + bbox[3] - 1) / 2
        check(96 <= width <= 106, f"W frame {index} must span a readable 96-106px field width")
        check(24 <= height <= 34, f"W frame {index} must be a flat 24-34px ground ellipse")
        check(54 <= center_x <= 57, f"W frame {index} is not horizontally centered")
        check(42 <= center_y <= 45, f"W frame {index} is not centered on Shen's y=44 foot point")
        check(bbox[0] >= 2 and bbox[2] <= 110 and bbox[1] >= 2 and bbox[3] <= 62, f"W frame {index} touches an atlas edge")

    lucian = style.get("entries", {}).get("archer", {})
    check(lucian.get("face") == {"x": 0, "y": -34}, "Lucian compact portrait offset must be x=0/y=-34")
    check(lucian.get("center") == {"x": 0, "y": -12}, "Lucian battle/card center offset must be x=0/y=-12")

def validate_localization() -> None:
    text = load_json("text/champion.i18n")
    for locale in ("en", "zh-hans", "zh-hant"):
        descriptions = text.get(locale, {}).get("description", {})
        for champion_id in ("lol_shen", "lol_lucian"):
            description = descriptions.get(champion_id, {})
            check(
                set(description) == {"name", "attack", "skill", "skill2", "ult"},
                f"{locale} {champion_id} localization is incomplete",
            )
    check(text.get("zh-hans", {}).get("description", {}).get("lol_shen", {}).get("name") == "慎", "zh-hans name must be 慎")
    check(text.get("zh-hant", {}).get("description", {}).get("lol_shen", {}).get("name") == "慎", "zh-hant name must be 慎")
    check(text.get("zh-hans", {}).get("description", {}).get("lol_lucian", {}).get("name") == "卢锡安", "zh-hans Lucian name must be 卢锡安")
    check(text.get("zh-hant", {}).get("description", {}).get("lol_lucian", {}).get("name") == "路西恩", "zh-hant Lucian name must be 路西恩")
    check("lowest-health" in text.get("en", {}).get("description", {}).get("lol_shen", {}).get("ult", ""), "English R text must disclose the target-selection limitation")
    lucian_en = text.get("en", {}).get("description", {}).get("lol_lucian", {})
    check("15 shots" in lucian_en.get("ult", ""), "English Lucian R text must disclose 15 shots")
    check("45%" in lucian_en.get("attack", ""), "English Lucian passive text must disclose the 45% second shot")


def validate_audio(champion: dict[str, Any], override: dict[str, Any]) -> None:
    sfx_names = sorted({effect.get("name") for effect in walk_effects(champion) if effect.get("type") in {"Sfx", "TargetSfx"}})
    check(len(sfx_names) == 7, f"expected 7 wired Shen sound events, got {len(sfx_names)}")
    for name in sfx_names:
        source_key = f"asset/base/sound/sfx/{name}"
        event_override = override.get(source_key, {})
        check(event_override.get("type") == "override", f"missing sound event remap: {source_key}")
        remapping = event_override.get("remapping", "")
        relative = remapping.removeprefix("asset/lol_mod/") + ".sound_info"
        event_path = MOD_ROOT / relative
        check(event_path.is_file(), f"missing sound_info for {name}: {relative}")
        if not event_path.is_file():
            continue
        sound_info = load_json(relative)
        plays = sound_info.get("plays", [])
        check(bool(plays), f"{relative} must contain plays")
        for play in plays:
            check(float(play.get("volume", 0)) >= 0.85, f"{relative} volume is below 0.85")
            clip = play.get("clip", "")
            clip_source = f"asset/base/sound/sfx/{clip}"
            clip_override = override.get(clip_source, {})
            check(clip_override.get("type") == "override", f"missing clip remap: {clip_source}")
            clip_relative = clip_override.get("remapping", "").removeprefix("asset/lol_mod/") + ".wav"
            clip_path = MOD_ROOT / clip_relative
            check(clip_path.is_file() and clip_path.stat().st_size > 1000, f"missing/empty clip: {clip_relative}")
            if clip_path.is_file():
                with wave.open(str(clip_path), "rb") as decoded:
                    check(decoded.getnchannels() == 1, f"{clip_relative} must be mono")
                    check(decoded.getsampwidth() == 2, f"{clip_relative} must be 16-bit PCM")
                    check(decoded.getframerate() == 44100, f"{clip_relative} must be 44.1 kHz")

    audio_manifest = load_json("qa/shen_official_audio_sources.json")
    check(len(audio_manifest.get("outputs", [])) == 7, "official audio QA manifest must cover 7 clips")
    for output in audio_manifest.get("outputs", []):
        wav = output.get("wav", {})
        path = MOD_ROOT / wav.get("path", "missing")
        check(path.is_file(), f"audio QA manifest references missing WAV: {wav.get('path')}")
        if path.is_file():
            check(sha256(path) == wav.get("sha256"), f"audio QA hash mismatch: {wav.get('path')}")


def validate_lucian_audio(champion: dict[str, Any], override: dict[str, Any]) -> None:
    sfx_names = sorted(
        {
            effect.get("name")
            for effect in walk_effects(champion)
            if effect.get("type") in {"Sfx", "TargetSfx"}
        }
    )
    check(len(sfx_names) == 8, f"expected 8 wired Lucian sound events, got {len(sfx_names)}")
    for name in sfx_names:
        source_key = f"asset/base/sound/sfx/{name}"
        event_override = override.get(source_key, {})
        check(event_override.get("type") == "override", f"missing Lucian sound event remap: {source_key}")
        remapping = event_override.get("remapping", "")
        relative = remapping.removeprefix("asset/lol_mod/") + ".sound_info"
        event_path = MOD_ROOT / relative
        check(event_path.is_file(), f"missing sound_info for {name}: {relative}")
        if not event_path.is_file():
            continue
        sound_info = load_json(relative)
        plays = sound_info.get("plays", [])
        check(bool(plays), f"{relative} must contain plays")
        for play in plays:
            check(float(play.get("volume", 0)) >= 0.85, f"{relative} volume is below 0.85")
            clip = play.get("clip", "")
            clip_source = f"asset/base/sound/sfx/{clip}"
            clip_override = override.get(clip_source, {})
            check(clip_override.get("type") == "override", f"missing Lucian clip remap: {clip_source}")
            clip_relative = clip_override.get("remapping", "").removeprefix("asset/lol_mod/") + ".wav"
            clip_path = MOD_ROOT / clip_relative
            check(clip_path.is_file() and clip_path.stat().st_size > 1000, f"missing/empty clip: {clip_relative}")
            if clip_path.is_file():
                with wave.open(str(clip_path), "rb") as decoded:
                    check(decoded.getnchannels() == 1, f"{clip_relative} must be mono")
                    check(decoded.getsampwidth() == 2, f"{clip_relative} must be 16-bit PCM")
                    check(decoded.getframerate() == 44100, f"{clip_relative} must be 44.1 kHz")

    audio_manifest = load_json("qa/lucian_official_audio_sources.json")
    check(len(audio_manifest.get("outputs", [])) == 8, "Lucian official audio QA manifest must cover 8 clips")
    for output in audio_manifest.get("outputs", []):
        wav = output.get("wav", {})
        path = MOD_ROOT / wav.get("path", "missing")
        check(path.is_file(), f"Lucian audio QA manifest references missing WAV: {wav.get('path')}")
        if path.is_file():
                check(sha256(path) == wav.get("sha256"), f"Lucian audio QA hash mismatch: {wav.get('path')}")


def validate_native_lucian_localization() -> None:
    text = load_json("text/champion.i18n")
    for locale in ("en", "zh-hans", "zh-hant"):
        descriptions = text.get(locale, {}).get("description", {})
        for champion_id in ("lol_shen", "archer"):
            description = descriptions.get(champion_id, {})
            check(
                set(description) == {"name", "attack", "skill", "skill2", "ult"},
                f"{locale} {champion_id} localization is incomplete",
            )
    check(
        text.get("zh-hans", {}).get("description", {}).get("archer", {}).get("name") == "卢锡安",
        "zh-hans native Archer name must be 卢锡安",
    )
    check(
        text.get("zh-hant", {}).get("description", {}).get("archer", {}).get("name") == "路西恩",
        "zh-hant native Archer name must be 路西恩",
    )
    lucian_en = text.get("en", {}).get("description", {}).get("archer", {})
    check("15 shots" in lucian_en.get("ult", ""), "English Lucian R text must disclose 15 shots")
    check("45%" in lucian_en.get("attack", ""), "English Lucian passive text must disclose the 45% second shot")
    check(lucian_en.get("skill", "").startswith("Q"), "first Lucian active must be labeled Q")
    check(lucian_en.get("skill2", "").startswith("E"), "second Lucian active must be labeled E, not W")
    check(lucian_en.get("ult", "").startswith("R"), "Lucian ultimate must be labeled R")


def validate_orianna_localization() -> None:
    text = load_json("text/champion.i18n")
    expected_names = {
        "en": "Orianna",
        "zh-hans": "奥利安娜",
        "zh-hant": "奧利安娜",
        "ja": "オリアナ",
        "ko": "오리아나",
    }
    for locale, expected_name in expected_names.items():
        description = (
            text.get(locale, {}).get("description", {}).get("barrier_magician", {})
        )
        check(
            set(description) == {"name", "attack", "skill", "skill2", "ult"},
            f"{locale} barrier_magician localization is incomplete",
        )
        check(
            description.get("name") == expected_name,
            f"{locale} Orianna encyclopedia search name must be {expected_name}",
        )
        check(description.get("skill", "").startswith("Q"), f"{locale} Orianna Q must be labeled Q")
        check(description.get("skill2", "").startswith("E"), f"{locale} Orianna E must be labeled E")
        check(description.get("ult", "").startswith("R"), f"{locale} Orianna R must be labeled R")
    check(
        "Dissonance" in text["en"]["description"]["barrier_magician"]["skill"],
        "English Orianna Q must disclose the merged Dissonance field",
    )
    check(
        "固定" in text["zh-hans"]["description"]["barrier_magician"]["ult"],
        "Simplified Chinese Orianna R must disclose its fixed landing point",
    )


def validate_orianna_audio(champion: dict[str, Any], override: dict[str, Any]) -> None:
    expected = {
        "lol_orianna_attack_cast",
        "lol_orianna_attack_hit",
        "lol_orianna_q_cast",
        "lol_orianna_q_hit",
        "lol_orianna_e_cast",
        "lol_orianna_e_hit",
        "lol_orianna_r_cast",
        "lol_orianna_r_hit",
    }
    actual = {
        effect.get("name")
        for effect in walk_effects(champion)
        if effect.get("type") in {"Sfx", "TargetSfx"}
    }
    check(actual == expected, f"Orianna must wire the eight official attack/Q/E/R sound events, got {sorted(actual)}")

    attack_cast_plays = load_json("sound/sfx/orianna_attack_cast.sound_info").get("plays", [])
    check(
        attack_cast_plays
        == [
            {"delay": 0.0, "clip": "orianna_attack_oncast_clip", "volume": 1.0},
            {"delay": 0.04, "clip": "orianna_attack_cast_clip", "volume": 1.0},
        ],
        "Orianna basic attack cast must layer the official OnCast windup and delayed missile-launch clips",
    )
    for name in sorted(expected):
        source_key = f"asset/base/sound/sfx/{name}"
        event_override = override.get(source_key, {})
        check(event_override.get("type") == "override", f"missing Orianna sound event remap: {source_key}")
        relative = event_override.get("remapping", "").removeprefix("asset/lol_mod/") + ".sound_info"
        event_path = MOD_ROOT / relative
        check(event_path.is_file(), f"missing Orianna sound_info for {name}: {relative}")
        if not event_path.is_file():
            continue
        plays = load_json(relative).get("plays", [])
        check(bool(plays), f"{relative} must contain plays")
        for play in plays:
            check(float(play.get("volume", 0)) >= 0.85, f"{relative} volume is below 0.85")
            clip = play.get("clip", "")
            clip_override = override.get(f"asset/base/sound/sfx/{clip}", {})
            check(clip_override.get("type") == "override", f"missing Orianna clip remap: {clip}")
            clip_relative = clip_override.get("remapping", "").removeprefix("asset/lol_mod/") + ".wav"
            clip_path = MOD_ROOT / clip_relative
            check(clip_path.is_file() and clip_path.stat().st_size > 1000, f"missing/empty clip: {clip_relative}")
            if clip_path.is_file():
                with wave.open(str(clip_path), "rb") as decoded:
                    check(decoded.getnchannels() == 1, f"{clip_relative} must be mono")
                    check(decoded.getsampwidth() == 2, f"{clip_relative} must be 16-bit PCM")
                    check(decoded.getframerate() == 44100, f"{clip_relative} must be 44.1 kHz")
                    frame_count = decoded.getnframes()
                    sample_rate = decoded.getframerate()
                    pcm = decoded.readframes(frame_count)
                if clip == "orianna_attack_oncast_clip":
                    samples = array.array("h")
                    samples.frombytes(pcm)
                    if sys.byteorder != "little":
                        samples.byteswap()
                    peak = max((abs(sample) for sample in samples), default=0)
                    rms = math.sqrt(sum(sample * sample for sample in samples) / len(samples)) if samples else 0.0
                    onset = next((index for index, sample in enumerate(samples) if abs(sample) >= 328), len(samples))
                    duration = frame_count / sample_rate if sample_rate else 0.0
                    peak_dbfs = 20 * math.log10(max(peak, 1) / 32768)
                    rms_dbfs = 20 * math.log10(max(rms, 1) / 32768)
                    check(0.44 <= duration <= 0.47, "Orianna attack OnCast duration must remain the pinned official clip")
                    check(onset / sample_rate < 0.02, "Orianna attack OnCast must begin within 20 ms")
                    check(peak_dbfs >= -6.0, f"Orianna attack OnCast peak is too quiet: {peak_dbfs:.2f} dBFS")
                    check(rms_dbfs >= -22.0, f"Orianna attack OnCast RMS is too quiet: {rms_dbfs:.2f} dBFS")

    audio_manifest = load_json("qa/orianna_official_audio_sources.json")
    outputs = audio_manifest.get("outputs", [])
    check(len(outputs) == 9, "Orianna official audio QA manifest must cover 9 clips")
    oncast = next((output for output in outputs if output.get("event_key") == "orianna_attack_oncast"), {})
    check(
        oncast.get("riot_event") == "Play_sfx_Orianna_OriannaBasicAttack_OnCast"
        and oncast.get("riot_event_id") == 2743591656
        and oncast.get("event_media_pool") == [10486779, 50362070, 172325572, 17107848]
        and oncast.get("media_id") == 10486779
        and oncast.get("source_wem_sha256") == "44e171e9fa39515829b6236edcaab23bb4aac2a1d358e2cff7d8bd5b7d611120",
        "Orianna basic-attack OnCast official event mapping drifted",
    )
    for output in outputs:
        wav = output.get("wav", {})
        path = MOD_ROOT / wav.get("path", "missing")
        check(path.is_file(), f"Orianna audio QA manifest references missing WAV: {wav.get('path')}")
        if path.is_file():
            check(sha256(path) == wav.get("sha256"), f"Orianna audio QA hash mismatch: {wav.get('path')}")


def validate_native_lucian_audio(override: dict[str, Any]) -> None:
    native_events = {
        "archer_attack": "lucian_attack_cast",
        "archer_skill_attack": "lucian_passive_cast",
        "archer_skill": "lucian_e_cast",
        "archer_skill2": "lucian_q_cast",
        "archer_ult_pre": "lucian_r_cast",
        "archer_ult_loop": "lucian_r_channel",
    }
    for native_name, lucian_name in native_events.items():
        source_key = f"asset/base/sound/sfx/{native_name}"
        event_override = override.get(source_key, {})
        check(event_override.get("type") == "override", f"missing native Lucian event remap: {source_key}")
        expected = f"asset/lol_mod/sound/sfx/{lucian_name}"
        check(event_override.get("remapping") == expected, f"wrong native Lucian event target: {source_key}")
        event_path = MOD_ROOT / f"sound/sfx/{lucian_name}.sound_info"
        check(event_path.is_file(), f"missing native Lucian sound_info: {event_path.name}")
        if not event_path.is_file():
            continue
        plays = load_json(f"sound/sfx/{lucian_name}.sound_info").get("plays", [])
        check(bool(plays), f"{lucian_name}.sound_info must contain plays")
        for play in plays:
            clip = play.get("clip", "")
            clip_override = override.get(f"asset/base/sound/sfx/{clip}", {})
            check(clip_override.get("type") == "override", f"missing native Lucian clip remap: {clip}")
            clip_relative = clip_override.get("remapping", "").removeprefix("asset/lol_mod/") + ".wav"
            clip_path = MOD_ROOT / clip_relative
            check(clip_path.is_file() and clip_path.stat().st_size > 1000, f"missing/empty clip: {clip_relative}")

    audio_manifest = load_json("qa/lucian_official_audio_sources.json")
    check(len(audio_manifest.get("outputs", [])) == 8, "Lucian official audio QA manifest must cover 8 clips")
    for output in audio_manifest.get("outputs", []):
        wav = output.get("wav", {})
        path = MOD_ROOT / wav.get("path", "missing")
        check(path.is_file(), f"Lucian audio QA manifest references missing WAV: {wav.get('path')}")
        if path.is_file():
            check(sha256(path) == wav.get("sha256"), f"Lucian audio QA hash mismatch: {wav.get('path')}")


def validate_imagegen_sources() -> None:
    expected = {
        "qa/shen_imagegen_sources.json": {"actor_model", "run_cycle", "q_icon", "w_icon", "r_icon", "q_vfx", "w_vfx", "r_vfx"},
        "qa/lucian_imagegen_sources.json": {"actor_model", "run_cycle", "attack_vfx", "q_icon", "e_icon", "r_icon", "q_vfx", "r_vfx"},
        "qa/orianna_imagegen_sources.json": {
            "actor_model",
            "run_cycle",
            "attack_vfx",
            "q_icon",
            "e_icon",
            "r_icon",
            "q_vfx",
            "e_vfx",
            "r_vfx",
        },
    }
    for manifest_path, expected_roles in expected.items():
        manifest = load_json(manifest_path)
        roles = {source.get("role") for source in manifest.get("sources", [])}
        check(roles == expected_roles, f"{manifest_path}: image-gen source roles are incomplete")
        for source in manifest.get("sources", []):
            path = MOD_ROOT / source.get("path", "missing")
            check(path.is_file(), f"missing image-gen source: {source.get('path')}")
            if path.is_file():
                check(sha256(path) == source.get("sha256"), f"image-gen source hash mismatch: {source.get('path')}")
            processed_path = source.get("processed_path")
            if processed_path:
                processed = MOD_ROOT / processed_path
                check(processed.is_file(), f"missing processed image-gen source: {processed_path}")
                if processed.is_file():
                    check(
                        sha256(processed) == source.get("processed_sha256"),
                        f"processed image-gen source hash mismatch: {processed_path}",
                    )
    processed = sorted((MOD_ROOT / "source/processed").glob("*_alpha.png"))
    expected_processed = sum(len(roles) for roles in expected.values())
    check(
        len(processed) == expected_processed,
        f"processed image-gen source set must contain {expected_processed} active PNGs",
    )
    for path in processed:
        image = Image.open(path).convert("RGBA")
        corners = [image.getpixel((0, 0)), image.getpixel((image.width - 1, 0)), image.getpixel((0, image.height - 1)), image.getpixel((image.width - 1, image.height - 1))]
        if "icon" not in path.name:
            check(all(pixel[3] == 0 for pixel in corners), f"processed source has a non-transparent corner: {path.name}")
    check((MOD_ROOT / "source/imagegen/PROMPTS.md").is_file(), "final image-gen prompt record is missing")
    retired_lucian_models = [
        "source/imagegen/lucian_actor_contact_v10.png",
        "source/processed/lucian_actor_contact_v10_alpha.png",
        "source/imagegen/lucian_actor_master_v1.png",
        "source/processed/lucian_actor_master_v1_alpha.png",
        "source/imagegen/lucian_run_master_v1.png",
        "source/processed/lucian_run_master_v1_alpha.png",
        "source/imagegen/lucian_actor_master_v2.png",
        "source/processed/lucian_actor_master_v2_alpha.png",
        "qa/lucian_v10_live_card.png",
    ]
    for relative in retired_lucian_models:
        check(not (MOD_ROOT / relative).exists(), f"retired low-quality Lucian model must be deleted: {relative}")


def validate_manifest() -> None:
    path = MOD_ROOT / "build_manifest.json"
    check(path.is_file(), "build_manifest.json is missing; run build_lol_mod.py")
    if not path.is_file():
        return
    manifest = load_json("build_manifest.json")
    for row in manifest.get("files", []):
        file_path = MOD_ROOT / row.get("path", "missing")
        check(file_path.is_file(), f"build manifest references missing file: {row.get('path')}")
        if file_path.is_file():
            check(file_path.stat().st_size == row.get("size"), f"build manifest size mismatch: {row.get('path')}")
            check(sha256(file_path) == row.get("sha256"), f"build manifest hash mismatch: {row.get('path')}")


def main() -> int:
    champion = load_json("champion/lol_shen.data_champion")
    lucian = load_json("champion/archer.data_champion")
    orianna = load_json("champion/barrier_magician.data_champion")
    override = load_json("mod.override_info")
    mod_info = load_json("mod.mod_info")
    check(mod_info.get("version") == "0.4.1", "lol_mod version must be 0.4.1")
    validate_data_contract(champion)
    validate_lucian_data_contract(lucian)
    validate_orianna_replacement_uniqueness()
    validate_orianna_data_contract(orianna)
    validate_orianna_native_animation(orianna)
    validate_orianna_v2_visual_contract()
    validate_orianna_resources_and_manifest(orianna)
    validate_animation(
        "aseprite_resources/champions/shen#sheet.png",
        "aseprite_resources/champions/shen#anim.fanim",
        {"idle": 7, "run": 9, "attack": 6, "skill": 7, "skill2": 5, "ult": 5, "hit": 1, "dead": 1},
    )
    validate_animation("aseprite_resources/effects/shen_q#sheet.png", "aseprite_resources/effects/shen_q#anim.fanim", {"projectile": 8})
    validate_animation("aseprite_resources/effects/shen_w#sheet.png", "aseprite_resources/effects/shen_w#anim.fanim", {"field": 6})
    validate_animation("aseprite_resources/effects/shen_r#sheet.png", "aseprite_resources/effects/shen_r#anim.fanim", {"guard": 5, "arrival": 4})
    validate_animation(
        "aseprite_resources/champions/lucian#sheet.png",
        "aseprite_resources/champions/lucian#anim.fanim",
        {
            "idle": 7,
            "run": 9,
            "attack": 3,
            "attack_right": 4,
            "attack_left": 4,
            "attack_double": 6,
            "skill": 10,
            "skill2": 5,
            "ult": 17,
            "hit": 1,
            "dead": 1,
        },
    )
    validate_animation("aseprite_resources/effects/lucian_attack#sheet.png", "aseprite_resources/effects/lucian_attack#anim.fanim", {"projectile": 8})
    attack_sheet = Image.open(MOD_ROOT / "aseprite_resources/effects/lucian_attack#sheet.png").convert("RGBA")
    attack_pixels = opaque_rgb(attack_sheet)
    attack_cyan_ratio = sum(blue >= red + 25 and green >= red + 10 for red, green, blue in attack_pixels) / max(1, len(attack_pixels))
    check(attack_cyan_ratio >= 0.65, f"Lucian basic attack must retain its cyan-blue identity, got {attack_cyan_ratio:.1%}")
    validate_animation("aseprite_resources/effects/lucian_q#sheet.png", "aseprite_resources/effects/lucian_q#anim.fanim", {"projectile": 8})
    q_sheet = Image.open(MOD_ROOT / "aseprite_resources/effects/lucian_q#sheet.png").convert("RGBA")
    check(q_sheet.size == (1536, 32), f"Lucian Q muzzle-pivot sheet must be 1536x32, got {q_sheet.size}")
    for index in range(8):
        bbox = q_sheet.crop((index * 192, 0, (index + 1) * 192, 32)).getchannel("A").getbbox()
        check(bbox is not None, f"Lucian Q image-gen frame {index} is empty")
        if bbox:
            check(bbox[0] == 104, f"Lucian Q frame {index} must begin eight pixels beyond the x=96 muzzle pivot")
            check(60 <= bbox[2] - bbox[0] <= 80, f"Lucian Q frame {index} must remain a beam, not a trailing mini projectile")
            check(bbox[2] <= 184, f"Lucian Q frame {index} crosses the forward projectile canvas edge")
    q_pixels = opaque_rgb(q_sheet)
    q_gold_ratio = sum(red >= blue + 25 and green >= blue + 5 for red, green, blue in q_pixels) / max(1, len(q_pixels))
    check(q_gold_ratio >= 0.65, f"Lucian Q must retain its gold-white identity, got {q_gold_ratio:.1%}")
    check(not (MOD_ROOT / "aseprite_resources/effects/lucian_e#sheet.png").exists(), "retired Lucian E VFX sheet must be absent")
    check(not (MOD_ROOT / "aseprite_resources/effects/lucian_e#anim.fanim").exists(), "retired Lucian E VFX animation must be absent")
    validate_animation("aseprite_resources/effects/lucian_r#sheet.png", "aseprite_resources/effects/lucian_r#anim.fanim", {"projectile": 8})
    validate_actor_and_icons(champion)
    validate_lucian_actor_and_icons(lucian)
    validate_compact_view_and_w_layout()
    validate_native_lucian_localization()
    validate_orianna_localization()
    validate_audio(champion, override)
    validate_lucian_audio(lucian, override)
    validate_orianna_audio(orianna, override)
    validate_imagegen_sources()
    validate_manifest()
    if ERRORS:
        print("League champion pack validation failed:")
        for error in ERRORS:
            print(f"- {error}")
        return 1
    print("League champion pack validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
