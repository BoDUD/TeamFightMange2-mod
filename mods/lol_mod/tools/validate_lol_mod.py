#!/usr/bin/env python3
"""Static validation for Shen and same-id Lucian/002 through Kled/006."""

from __future__ import annotations

import array
import ctypes
import hashlib
import json
import math
import subprocess
import sys
import wave
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Iterable

from PIL import Image


MOD_ROOT = Path(__file__).resolve().parents[1]
ERRORS: list[str] = []
EXPECTED_MOD_API_VERSION = 8


def validate_shen_sdk_data_champion() -> None:
    """Ask the exact installed SDK type to deserialize Shen's generated file."""

    script = MOD_ROOT / "tools" / "validate_shen_data_champion_sdk.ps1"
    source = MOD_ROOT / "tools" / "shen_data_champion_sdk_gate.rs"
    check(script.is_file(), "Shen SDK DataChampionInfo gate script is missing")
    check(source.is_file(), "Shen SDK DataChampionInfo gate Rust source is missing")
    sdk = MOD_ROOT.parents[2] / "mod-sdk"
    if not sdk.is_dir() or not script.is_file():
        return
    result = subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(script),
            "-ChampionPath",
            str(MOD_ROOT / "champion" / "lol_shen.data_champion"),
            "-SdkDir",
            str(sdk),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    check(
        result.returncode == 0,
        "official SDK DataChampionInfo rejected Shen: "
        + (result.stderr.strip() or result.stdout.strip() or f"exit {result.returncode}"),
    )

NEXUS_NATIVE_SHEET_SIZES: dict[str, tuple[int, int]] = {
    "nexus": (836, 81),
    "nexus_orb": (526, 81),
}

NEXUS_NATIVE_ANIMATION_CONTRACTS: dict[str, dict[str, dict[str, Any]]] = {
    "nexus": {
        "idle": {
            "durations": [0.120000005] * 8,
            "rects": [
                [0, 0, 57, 65],
                [58, 0, 57, 63],
                [116, 0, 57, 63],
                [174, 0, 57, 63],
                [232, 0, 57, 65],
                [290, 0, 57, 67],
                [348, 0, 57, 69],
                [406, 0, 57, 67],
            ],
        },
        "attack": {
            "durations": [0.080000006] * 6,
            "rects": [
                [464, 0, 57, 65],
                [522, 0, 57, 65],
                [580, 0, 57, 73],
                [638, 0, 57, 79],
                [696, 0, 57, 80],
                [754, 0, 57, 80],
            ],
        },
        "attack_projectile": {
            "durations": [0.080000006],
            "rects": [[812, 0, 3, 3]],
        },
        "hit_effect": {
            "durations": [0.080000006] * 5,
            "rects": [
                [816, 0, 3, 3],
                [820, 0, 3, 3],
                [824, 0, 3, 3],
                [828, 0, 3, 3],
                [832, 0, 3, 3],
            ],
        },
    },
    "nexus_orb": {
        "idle": {
            "durations": [0.120000005] * 8,
            "rects": [
                [0, 0, 31, 65],
                [32, 0, 31, 63],
                [64, 0, 31, 61],
                [96, 0, 31, 63],
                [128, 0, 31, 65],
                [160, 0, 31, 67],
                [192, 0, 31, 69],
                [224, 0, 31, 67],
            ],
        },
        "attack": {
            "durations": [0.080000006] * 6,
            "rects": [
                [256, 0, 31, 65],
                [288, 0, 31, 65],
                [320, 0, 39, 73],
                [360, 0, 45, 79],
                [406, 0, 45, 80],
                [452, 0, 49, 80],
            ],
        },
        "attack_projectile": {
            "durations": [0.080000006],
            "rects": [[502, 0, 3, 3]],
        },
        "hit_effect": {
            "durations": [0.080000006] * 5,
            "rects": [
                [506, 0, 3, 3],
                [510, 0, 3, 3],
                [514, 0, 3, 3],
                [518, 0, 3, 3],
                [522, 0, 3, 3],
            ],
        },
    },
}

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

BRIAR_NATIVE_ANIMATION: dict[str, list[float]] = {
    "idle": [0.18, 0.14, 0.14, 0.14],
    "berserk_idle": [0.18, 0.14, 0.14, 0.14],
    "run": [0.080000006] * 8,
    "berserk_run": [0.080000006] * 8,
    "attack": [0.080000006] * 5,
    "attack2": [0.080000006] * 5,
    "berserk_attack": [0.060000002] * 5,
    "skill1": [0.080000006] * 3,
    "skill2": [0.080000006] * 4,
    "skill2_berserk": [0.080000006] * 4,
    "skill2_effect": [0.080000006] * 4,
    "skill1_effect_old": [0.080000006] * 7,
    "ult": [0.080000006] * 5,
    "berserk_ult": [0.080000006] * 5,
    "ult_pre": [0.080000006],
    "berserk_ult_pre": [0.080000006],
    "ult_dash": [0.080000006],
    "berserk_ult_dash": [0.080000006],
    "ult_attack": [0.080000006] * 3,
    "berserk_ult_attack": [0.080000006] * 3,
    "hit": [0.1],
    "berserk_hit": [0.1],
    "dead": [0.1] * 10,
    "berserk_dead": [0.1] * 10,
}

BRIAR_VIEW_PROJECTILES: dict[str, tuple[str, str, int, bool]] = {
    "lol_briar_e_scream_projectile": (
        "asset/lol_mod/aseprite_resources/effects/briar_e_scream",
        "projectile",
        2,
        False,
    ),
}

BRIAR_VIEW_EFFECTS: dict[str, tuple[str, str, int, bool]] = {
    "lol_briar_bleed_tick_visual": (
        "asset/lol_mod/aseprite_resources/effects/briar_bleed",
        "tick",
        1,
        True,
    ),
    "lol_briar_q_overhead_visual": (
        "asset/lol_mod/aseprite_resources/effects/briar_q_overhead",
        "impact",
        2,
        True,
    ),
    "lol_briar_r_mark_visual": (
        "asset/lol_mod/aseprite_resources/effects/briar_r_mark",
        "mark",
        2,
        True,
    ),
    "lol_briar_r_trail_visual": (
        "asset/lol_mod/aseprite_resources/effects/briar_r_trail",
        "trail",
        1,
        True,
    ),
    "lol_briar_r_arrival_visual": (
        "asset/lol_mod/aseprite_resources/effects/briar_r_arrival",
        "arrival",
        0,
        False,
    ),
}

BRIAR_VIEW_BUFFS: dict[str, tuple[str, str, str, str, int]] = {
    "lol_briar_certain_death_frenzy": (
        "asset/lol_mod/aseprite_resources/effects/briar_frenzy",
        "pre",
        "loop",
        "remove",
        1,
    ),
}

BRIAR_EFFECT_ANIMATION: dict[str, tuple[tuple[int, int], dict[str, list[float]]]] = {
    "briar_bleed": ((384, 48), {"tick": [0.04, 0.05, 0.06, 0.07, 0.06, 0.06, 0.08, 0.10]}),
    "briar_q_overhead": (
        (512, 64),
        {"impact": [0.04, 0.04, 0.05, 0.05, 0.06, 0.06, 0.07, 0.09]},
    ),
    "briar_frenzy": (
        (768, 96),
        {
            "pre": [0.06, 0.07, 0.08, 0.10],
            "loop": [0.22, 0.22],
            "remove": [0.10, 0.14],
        },
    ),
    "briar_e_scream": ((896, 64), {"projectile": [0.04] * 8}),
    "briar_r_mark": ((256, 64), {"mark": [0.10] * 4}),
    "briar_r_trail": ((384, 48), {"trail": [0.045] * 4}),
    "briar_r_arrival": ((384, 96), {"arrival": [0.08, 0.10, 0.12, 0.18]}),
}

BRIAR_AUDIO_EVENTS: dict[str, tuple[str, int]] = {
    "lol_briar_attack_cast": ("Play_sfx_Briar_BriarBasicAttack_OnCast", 1625124708),
    "lol_briar_attack_hit": ("Play_sfx_Briar_BriarBasicAttack_OnHit", 1567502092),
    "lol_briar_frenzy_cast": ("Play_sfx_Briar_BriarBasicAttackFrenzy_OnCast", 2869900170),
    "lol_briar_frenzy_hit": ("Play_sfx_Briar_BriarBasicAttackFrenzy_OnHit", 4041037182),
    "lol_briar_q_cast": ("Play_sfx_Briar_BriarW_cast_foley_jump", 2077188739),
    "lol_briar_e_cast": ("Play_sfx_Briar_BriarEMisStrong_missilelaunch_charged", 1505478577),
    "lol_briar_e_hit": ("Play_sfx_Briar_BriarEMisStrong_OnHit", 1269301111),
    "lol_briar_r_cast": ("Play_sfx_Briar_BriarR_OnCast", 1265575348),
    "lol_briar_r_hit": ("Play_sfx_Briar_BriarR_OnHit", 460152284),
}

SIVIR_NATIVE_ANIMATION: dict[str, list[float]] = {
    "idle": [0.18, 0.14, 0.14, 0.14],
    "big_boomerang": [0.1],
    "boomerang": [0.1],
    "run": [0.080000006] * 8,
    "attack": [0.060000002] * 6,
    "idle_no_boomerang": [0.18, 0.14, 0.14, 0.14],
    "skill": [0.060000002] * 7,
    "skill2": [0.060000002] * 7,
    "ult": [0.060000002] * 6,
    "hit": [0.1],
    "ult_boomerang": [0.060000002],
    "dead": [0.1] * 9,
}

SIVIR_VIEW_PROJECTILES: dict[str, tuple[str, str, int, bool]] = {
    "lol_sivir_attack_blade": (
        "asset/lol_mod/aseprite_resources/effects/sivir_attack",
        "projectile",
        2,
        True,
    ),
    "lol_sivir_q_outgoing": (
        "asset/lol_mod/aseprite_resources/effects/sivir_q",
        "out",
        2,
        True,
    ),
    "lol_sivir_q_return": (
        "asset/lol_mod/aseprite_resources/effects/sivir_q",
        "return",
        2,
        True,
    ),
}

SIVIR_VIEW_EFFECTS: dict[str, tuple[str, str, int, bool]] = {
    "lol_sivir_attack_hit_visual": (
        "asset/lol_mod/aseprite_resources/effects/sivir_attack",
        "hit",
        2,
        True,
    ),
    "lol_sivir_q_hit_visual": (
        "asset/lol_mod/aseprite_resources/effects/sivir_attack",
        "hit",
        2,
        True,
    ),
    "lol_sivir_r_cast_visual": (
        "asset/lol_mod/aseprite_resources/effects/sivir_r_cast",
        "pulse",
        0,
        True,
    ),
}

SIVIR_VIEW_BUFFS: dict[str, tuple[str, str, str, str, int]] = {
    "lol_sivir_spell_shield_window": (
        "asset/lol_mod/aseprite_resources/effects/sivir_e_shield",
        "pre",
        "loop",
        "remove",
        1,
    ),
    "lol_sivir_on_the_hunt_speed": (
        "asset/lol_mod/aseprite_resources/effects/sivir_hunt_buff",
        "pre",
        "loop",
        "remove",
        0,
    ),
}

SIVIR_EFFECT_ANIMATION: dict[str, tuple[tuple[int, int], dict[str, list[float]]]] = {
    "sivir_attack": ((384, 32), {"projectile": [0.04] * 7, "hit": [0.12]}),
    "sivir_q": ((512, 48), {"out": [0.045] * 4, "return": [0.04] * 4}),
    "sivir_e_shield": (
        (512, 64),
        {"pre": [0.08, 0.10], "loop": [0.16] * 4, "remove": [0.10, 0.14]},
    ),
    "sivir_r_cast": (
        (1024, 64),
        {"pulse": [0.06, 0.07, 0.08, 0.09, 0.10, 0.10, 0.12, 0.16]},
    ),
    "sivir_hunt_buff": (
        (512, 32),
        {"pre": [0.08, 0.10], "loop": [0.14] * 4, "remove": [0.10, 0.14]},
    ),
}

SIVIR_AUDIO_EVENTS: dict[str, tuple[str, int]] = {
    "lol_sivir_attack_cast": ("Play_sfx_Sivir_SivirBasicAttack_OnMissileLaunch", 1876638910),
    "lol_sivir_attack_hit": ("Play_sfx_Sivir_SivirBasicAttack_OnHit", 4265286992),
    "lol_sivir_q_out": ("Play_sfx_Sivir_SivirQMissile_OnMissileLaunch", 3385220941),
    "lol_sivir_q_return": ("Play_sfx_Sivir_SivirQMissileReturn_OnMissileLaunch", 1646723331),
    "lol_sivir_q_hit": ("Play_sfx_Sivir_SivirQ_hit", 1419197874),
    "lol_sivir_e_cast": ("Play_sfx_Sivir_SivirE_OnBuffActivate", 4008136820),
    "lol_sivir_r_cast": ("Play_sfx_Sivir_SivirR_OnCast", 546561056),
}
SIVIR_NATIVE_AUDIO_EVENTS = {
    "boomerang_hunter_attack",
    "boomerang_hunter_attacks",
    "boomerang_hunter_skill",
    "boomerang_hunter_skill2",
    "boomerang_hunter_ult",
    "boomerang_hunter_ult1",
    "boomerang_hunter_ult2",
    "boomerang_ult",
}
SIVIR_NATIVE_AUDIO_CLIPS = {
    "boomerang_attack0",
    "boomerang_skill0",
    *(f"boomerang_ult{index}" for index in range(8)),
    "boomerang_hunter_skill_resource1",
    "boomerang_hunter_skill_remix",
    "boomerang_hunter_skill_resource_original",
    "boomerang_hunter_skill2_resource",
    "boomerang_hunter_skill2_resource1",
    "boomerang_hunter_skill2_resource2",
    "boomerang_hunter_ult_resource1",
    "boomerang_hunter_ult_resource2",
}
SIVIR_NATIVE_SILENCE_SHA256 = "73b42ab23be05ebeada04e01d7a8b903a1cdd1753a090c5032983da1066bacc2"

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


def validate_objective_killfeed_names(override: dict[str, Any]) -> None:
    text = load_json("text/ui.i18n")
    expected = {
        "en": ("Baron Nashor", "Infernal Drake"),
        "ko": ("내셔 남작", "화염의 드래곤"),
        "ja": ("バロンナッシャー", "インファーナルドレイク"),
        "zh-hans": ("纳什男爵", "炼狱亚龙"),
        "zh-hant": ("巴龍納什", "赤燄飛龍"),
    }
    for locale, (baron, dragon) in expected.items():
        section = text.get(locale, {})
        match_log = section.get("match", {}).get("log", {})
        ingame = section.get("ingame", {})
        result = section.get("set_result", {})
        values = [
            match_log.get(key, "")
            for key in ("red_epic", "blue_epic", "red_serpen", "blue_serpen")
        ]
        values += [ingame.get(key, "") for key in ("epic", "serpen")]
        values += [
            result.get(key, "")
            for key in (
                "epic",
                "serpen",
                "graph_blue_epic",
                "graph_red_epic",
                "graph_blue_serpen",
                "graph_red_serpen",
            )
        ]
        check(
            len(values) == 12 and all(values),
            f"{locale} objective UI text must define all 12 kill/result labels",
        )
        check(
            sum(baron in value for value in values) == 6,
            f"{locale} objective UI text must use {baron} for every Baron label",
        )
        check(
            sum(dragon in value for value in values) == 6,
            f"{locale} objective UI text must use {dragon} as the safe dragon fallback",
        )
        check(
            not any(
                legacy in value
                for value in values
                for legacy in ("Morgard", "Serpen", "莫尔加德", "双角巨蛇")
            ),
            f"{locale} objective UI text must not retain native Morgard/Serpen names",
        )

    check(
        override.get("asset/base/text/ui")
        == {"remapping": "asset/lol_mod/text/ui", "type": "merge"},
        "objective kill/result labels must merge through asset/base/text/ui",
    )
    source = (MOD_ROOT / "src" / "lib.rs").read_text(encoding="utf-8")
    for token in (
        "rewrite_objective_render_text(ui, state)",
        "RenderCommand::Text { text, .. }",
        "ui_tree_has_match_runner(&ui.root)",
        "current_dragon_variant_index",
        ".active_selection",
        "current_dragon_selection()",
        "dragon_variant_index(selection.seed)",
        "炼狱亚龙",
        "海洋亚龙",
        "山脉亚龙",
        "云端亚龙",
        "海克斯科技亚龙",
    ):
        check(token in source, f"objective render-name runtime is missing {token}")


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


def alpha_component_sizes(image: Image.Image) -> list[int]:
    alpha = image.convert("RGBA").getchannel("A")
    remaining = {
        (x, y)
        for y in range(image.height)
        for x in range(image.width)
        if alpha.getpixel((x, y)) >= 128
    }
    sizes: list[int] = []
    while remaining:
        seed = remaining.pop()
        component = {seed}
        stack = [seed]
        while stack:
            x, y = stack.pop()
            for neighbor in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
                if neighbor in remaining:
                    remaining.remove(neighbor)
                    component.add(neighbor)
                    stack.append(neighbor)
        sizes.append(len(component))
    return sorted(sizes, reverse=True)


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


def direct_effects(effect: Any, effect_type: str) -> list[dict[str, Any]]:
    if not isinstance(effect, dict):
        return []
    return [
        child
        for child in effect.get("effects", [])
        if isinstance(child, dict) and child.get("type") == effect_type
    ]


def direct_buff_states(effect: Any, effect_type: str) -> list[dict[str, Any]]:
    return [
        child.get("buff_state", {})
        for child in direct_effects(effect, effect_type)
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
        "skill icon order must be Q/E/R",
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
    q_switches = find_effect(attack, "SwitchByBuff")
    check(
        [effect.get("buff_name") for effect in q_switches]
        == [
            "lol_shen_twilight_assault_through_charge_3",
            "lol_shen_twilight_assault_through_charge_2",
            "lol_shen_twilight_assault_through_charge_1",
            "lol_shen_twilight_assault_charge_3",
            "lol_shen_twilight_assault_charge_2",
            "lol_shen_twilight_assault_charge_1",
        ],
        "Q basic-attack state must prefer through-blade 3 -> 2 -> 1, then normal 3 -> 2 -> 1",
    )
    empowered_hits = find_effect(attack, "ApAttack")
    check(
        [(effect.get("damage"), effect.get("attack_ratio")) for effect in empowered_hits]
        == [(35, 30)] * 3 + [(20, 20)] * 3,
        "Q must expose three 35+30% AP through-blade hits and three 20+20% AP normal hits",
    )
    for switch in q_switches:
        buff_branch = switch.get("effect_buff", {})
        delayed = [effect for effect in buff_branch.get("effects", []) if effect.get("type") == "Delayed"]
        check(len(delayed) == 1, f"Q {switch.get('buff_name')} branch must have one direct delayed hit")
        if delayed:
            removed = [
                effect.get("name")
                for effect in delayed[0].get("effects", [])
                if effect.get("type") == "RemoveCasterBuff"
            ]
            check(
                removed == [switch.get("buff_name")],
                f"Q {switch.get('buff_name')} branch must consume exactly its own marker",
            )
    check(not find_effect(attack, "AddCasterBuff"), "Q attacks must consume, not refresh, the shared charge window")

    q = champion.get("skill", {})
    check(
        (
            q.get("action_name"), q.get("cooltime"), q.get("duration"),
            q.get("start_timing"), q.get("range"), q.get("casting_type"),
            q.get("casting_target"),
        )
        == ("skill", 360, 28, 8, 55000, "Direction", "EnemyChampion"),
        "Q must use a stock-AI enemy-gated direction cast instead of self-casting into empty space",
    )
    for unsafe_type in ("RangeProjectile", "Attack", "ApAttack", "Shield"):
        check(not find_effect(q, unsafe_type), f"Q cast must not contain {unsafe_type}")
    outbound = find_effect(q, "LinearProjectile", name="lol_shen_twilight_assault_blade_outbound")
    check(len(outbound) == 1, "Q must own exactly one stable outbound spirit-blade anchor")
    returns = find_effect(outbound[0], "BackToCasterLinearProjectile", name="lol_shen_twilight_assault_blade_return") if outbound else []
    check(len(returns) == 1, "Q outbound anchor must own exactly one return-to-caster blade")
    if outbound:
        check(
            (
                outbound[0].get("penetrate"), outbound[0].get("speed"),
                outbound[0].get("range"), outbound[0].get("shape"),
                outbound[0].get("applied_target"), outbound[0].get("applied_effects"),
            )
            == (True, 10000, 65000, {"Circle": {"radius": 4000}}, "EnemyChampion", []),
            "Q outbound spirit-blade anchor contract mismatch",
        )
    if returns:
        blade_return = returns[0]
        check(
            outbound[0].get("end_effects") == [blade_return],
            "Q return blade must be the outbound projectile's single direct end_effect",
        )
        check(
            (
                blade_return.get("penetrate"), blade_return.get("speed"),
                blade_return.get("range"), blade_return.get("shape"),
                blade_return.get("applied_target"), blade_return.get("end_effects"),
            )
            == (True, 12000, 130000, {"Circle": {"radius": 7500}}, "EnemyChampion", []),
            "Q return spirit-blade path contract mismatch",
        )
    direct_q_effects = q.get("effect", {}).get("effects", [])
    q_grants = [effect for effect in direct_q_effects if effect.get("type") == "AddCasterBuff"]
    q_windows = {
        effect.get("buff_state", {}).get("name"): effect.get("buff_state", {}).get("duration")
        for effect in q_grants
    }
    check(
        q_windows
        == {
            "lol_shen_twilight_assault_charge_3": {"Time": {"tick": 480}},
            "lol_shen_twilight_assault_charge_2": {"Time": {"tick": 480}},
            "lol_shen_twilight_assault_charge_1": {"Time": {"tick": 480}},
        },
        "Q cast must grant three normal markers with one shared 480-tick window",
    )
    direct_q_removals = {
        effect.get("name")
        for effect in direct_q_effects
        if effect.get("type") == "RemoveCasterBuff"
    }
    check(
        direct_q_removals
        == {
            *(f"lol_shen_twilight_assault_charge_{charge}" for charge in (3, 2, 1)),
            *(f"lol_shen_twilight_assault_through_charge_{charge}" for charge in (3, 2, 1)),
            "lol_shen_twilight_assault_return_resolved",
        },
        "Q cast must clear both charge families and its once-per-cast return guard",
    )
    if returns:
        return_effect = returns[0].get("applied_effects", [{}])[0].get("effect", {})
        guard_state = {
            "name": "lol_shen_twilight_assault_return_resolved",
            "duration": {"Time": {"tick": 480}},
        }
        check(
            return_effect.get("type") == "SwitchByBuff"
            and return_effect.get("buff_name") == guard_state["name"]
            and return_effect.get("effect_buff")
            == {"type": "AddCasterBuff", "buff_state": guard_state},
            "Q return must begin with an inert once-per-cast resolved guard",
        )
        remaining_switch = return_effect.get("effect_none", {})
        all_charge_names = {
            *(f"lol_shen_twilight_assault_charge_{charge}" for charge in (3, 2, 1)),
            *(f"lol_shen_twilight_assault_through_charge_{charge}" for charge in (3, 2, 1)),
        }
        for remaining, normal_marker in zip(
            (3, 2, 1),
            (f"lol_shen_twilight_assault_charge_{charge}" for charge in (3, 2, 1)),
            strict=True,
        ):
            check(
                remaining_switch.get("type") == "SwitchByBuff"
                and remaining_switch.get("buff_name") == normal_marker,
                f"Q return remaining-charge branch mismatch for {normal_marker}",
            )
            branch = remaining_switch.get("effect_buff", {})
            direct = branch.get("effects", []) if branch.get("type") == "Combine" else []
            removed = {
                effect.get("name")
                for effect in direct
                if effect.get("type") == "RemoveCasterBuff"
            }
            check(
                removed == all_charge_names,
                f"Q {remaining}-charge return branch must replace, not append to, old charge markers",
            )
            caster_states = [
                effect.get("buff_state", {})
                for effect in direct
                if effect.get("type") == "AddCasterBuff"
            ]
            upgraded = {
                state.get("name")
                for state in caster_states
                if str(state.get("name", "")).startswith(
                    "lol_shen_twilight_assault_through_charge_"
                )
            }
            check(
                upgraded
                == {
                    f"lol_shen_twilight_assault_through_charge_{charge}"
                    for charge in range(remaining, 0, -1)
                },
                f"Q return must upgrade exactly the {remaining} still-unused charges",
            )
            check(guard_state in caster_states, "Q upgrade branch must set its once-per-cast guard")
            check(
                {
                    "name": "lol_shen_twilight_assault_through_attack_speed",
                    "duration": {"Time": {"tick": 120}},
                    "attack_speed_mult": 35,
                }
                in caster_states,
                "Q return-through must grant the short attack-speed branch",
            )
            pull_slows = [
                effect.get("buff_state", {})
                for effect in direct
                if effect.get("type") == "AddBuff"
            ]
            check(
                pull_slows
                == [{
                    "name": "lol_shen_twilight_assault_pull_slow",
                    "duration": {"Time": {"tick": 90}},
                    "move_speed_mult": -30,
                }],
                f"Q {remaining}-charge return branch must slow only its first crossed target",
            )
            remaining_switch = remaining_switch.get("effect_none", {})
        check(
            remaining_switch == {"type": "AddCasterBuff", "buff_state": guard_state},
            "Q return with no charges remaining must only close the once-per-cast guard",
        )

    e = champion.get("skill2", {})
    check(
        (
            e.get("action_name"), e.get("cooltime"), e.get("duration"),
            e.get("start_timing"), e.get("range"), e.get("casting_type"),
            e.get("casting_target"),
        )
        == ("skill2", 720, 30, 4, 60000, "Direction", "EnemyChampion"),
        "E direction-dash timing or target contract mismatch",
    )
    rushes = find_effect(e, "Rush")
    check(len(rushes) == 1, "E must contain exactly one Rush")
    if rushes:
        rush = rushes[0]
        check(
            (
                rush.get("speed"), rush.get("move_speed_ratio"), rush.get("range"),
                rush.get("casting_target"), rush.get("penetrate"),
            )
            == (4000, 100, 10000, "EnemyChampion", True),
            "E Rush speed, 10,000 swept collision radius, target or penetration mismatch",
        )
        applied = rush.get("applied_effects", [])
        check(
            len(applied) == 1 and applied[0].get("casting_type") == "Targeting",
            "E Rush must own exactly one direct Targeting collision payload",
        )
        rush_payload = applied[0].get("effect", {}) if applied else {}
        direct_payload = (
            rush_payload.get("effects", []) if rush_payload.get("type") == "Combine" else []
        )
        check(
            [effect.get("type") for effect in direct_payload]
            == ["Attack", "Native", "AddBuff", "ViewEffect", "TargetSfx"],
            "E collision payload order must keep the native taunt directly on Rush hit",
        )
        check(
            len(direct_payload) > 1
            and direct_payload[1]
            == {"type": "Native", "effect_ref": "lol_shen_shadow_dash_taunt_native"},
            "E Native taunt must be the direct second effect of the Rush collision payload",
        )
        check(bool(find_effect(rush, "Attack", damage=60, attack_ratio=0)), "E physical hit mismatch")
        check(not find_effect(rush, "Taunt"), "E must not duplicate the native taunt with a data Taunt")
        check(
            bool(find_effect(rush, "Native", effect_ref="lol_shen_shadow_dash_taunt_native")),
            "E must call the native taunt effect on every crossed champion",
        )
        taunt_markers = [
            effect
            for effect in find_effect(rush, "AddBuff")
            if effect.get("buff_state", {}).get("name") == "lol_shen_shadow_dash_taunted"
        ]
        check(len(taunt_markers) == 1, "E named taunt marker is missing")
    trail_windows = [
        effect.get("buff_state", {})
        for effect in find_effect(e, "AddCasterBuff")
        if effect.get("buff_state", {}).get("name") == "lol_shen_shadow_dash_trail_window"
    ]
    check(
        trail_windows == [{"name": "lol_shen_shadow_dash_trail_window", "duration": {"Time": {"tick": 30}}}],
        "E must keep a dash-length trail marker",
    )
    check(not find_effect(e, "RangeEffect"), "E must not retain W's caster-centered field")
    check(not find_effect(e, "Shield"), "E must not retain W's ally shield")

    ult = champion.get("ult", {})
    check(ult.get("range") == 960000, "R range must be 960000")
    check(ult.get("cooltime") == 3000, "R cooldown must be 3000 ticks")
    check(ult.get("casting_target") == "AllyNotSelf", "R must target AllyNotSelf")
    check(bool(find_effect(ult, "Shield", amount=900, ap_ratio=80, tick=180)), "R shield contract mismatch")
    delayed = [effect for effect in find_effect(ult, "Delayed", tick=48)]
    check(len(delayed) == 1, "R must have one 48-tick arrival delay")
    if delayed:
        check(bool(find_effect(delayed[0], "Teleport")), "R delayed arrival must contain a real Teleport")
        check(not find_effect(delayed[0], "Taunt"), "R arrival must not carry E's taunt")
        arrive_sfx = [effect.get("name") for effect in find_effect(delayed[0], "Sfx")]
        check("lol_shen_r_arrive" in arrive_sfx, "R arrival SFX must be inside the 48-tick delay")
    enemy_arrival_ranges = [
        effect
        for effect in find_effect(ult, "RangeEffect")
        if effect.get("target") == "EnemyChampion"
    ]
    check(not enemy_arrival_ranges, "R must not retain the old circular arrival taunt")

    serialized = json.dumps(champion, ensure_ascii=False)
    for retired in ("spirit_refuge", "lol_shen_w_", "shen_w"):
        check(retired not in serialized, f"retired W payload remains active: {retired}")
    required_markers = {
        "lol_shen_twilight_assault_charge_3",
        "lol_shen_twilight_assault_charge_2",
        "lol_shen_twilight_assault_charge_1",
        "lol_shen_twilight_assault_through_charge_3",
        "lol_shen_twilight_assault_through_charge_2",
        "lol_shen_twilight_assault_through_charge_1",
        "lol_shen_twilight_assault_return_resolved",
        "lol_shen_twilight_assault_through_attack_speed",
        "lol_shen_twilight_assault_pull_slow",
        "lol_shen_shadow_dash_trail_window",
        "lol_shen_shadow_dash_taunted",
        "lol_shen_stand_united_channel",
        "lol_shen_stand_united_shield_window",
    }
    for marker in required_markers:
        check(marker in serialized, f"named state marker missing: {marker}")
    projectile_views = champion.get("view_projectiles", [])
    check(
        projectile_views
        == [
            {
                "type": "Animated",
                "name": "lol_shen_twilight_assault_blade_outbound",
                "anim": "asset/lol_mod/aseprite_resources/effects/shen_q",
                "tag": "outbound",
                "z": 2,
                "repeat": True,
            },
            {
                "type": "Animated",
                "name": "lol_shen_twilight_assault_blade_return",
                "anim": "asset/lol_mod/aseprite_resources/effects/shen_q",
                "tag": "return",
                "z": 2,
                "repeat": True,
            },
        ],
        "Shen Q outbound/return projectile visuals are not registered independently",
    )
    view_effects = champion.get("view_effects", [])
    check(
        view_effects
        == [
            {
                "type": "Animation",
                "name": "lol_shen_twilight_assault_empowered_hit",
                "anim": "asset/lol_mod/aseprite_resources/effects/shen_q",
                "tag": "empowered_hit",
                "z": 2,
                "is_follow": True,
            },
            {
                "type": "Animation",
                "name": "lol_shen_twilight_assault_through_empowered_hit",
                "anim": "asset/lol_mod/aseprite_resources/effects/shen_q",
                "tag": "through_hit",
                "z": 2,
                "is_follow": True,
            },
            {
                "type": "Animation",
                "name": "lol_shen_twilight_assault_pass_through_visual",
                "anim": "asset/lol_mod/aseprite_resources/effects/shen_q",
                "tag": "pass_through",
                "z": 2,
                "is_follow": True,
            },
            {
                "type": "Animation",
                "name": "lol_shen_shadow_dash_impact",
                "anim": "asset/lol_mod/aseprite_resources/effects/shen_e",
                "tag": "impact",
                "z": 2,
                "is_follow": True,
            },
            {
                "type": "Animation",
                "name": "lol_shen_stand_united_guard_visual",
                "anim": "asset/lol_mod/aseprite_resources/effects/shen_r",
                "tag": "guard",
                "z": 1,
                "is_follow": True,
            },
            {
                "type": "Animation",
                "name": "lol_shen_stand_united_arrival_visual",
                "anim": "asset/lol_mod/aseprite_resources/effects/shen_r",
                "tag": "arrival",
                "z": 1,
                "is_follow": False,
            },
        ],
        "Shen Q/E/R view-effect registration mismatch",
    )
    check(
        champion.get("view_buffs", [])
        == [
            {
                "type": "ThreePhase",
                "name": "lol_shen_shadow_dash_trail_window",
                "anim": "asset/lol_mod/aseprite_resources/effects/shen_e",
                "pre_tag": "trail_pre",
                "loop_tag": "trail_loop",
                "remove_tag": "trail_remove",
                "z": -1,
            },
            {
                "type": "ThreePhase",
                "name": "lol_shen_shadow_dash_taunted",
                "anim": "asset/lol_mod/aseprite_resources/effects/shen_e",
                "pre_tag": "taunt_pre",
                "loop_tag": "taunt_loop",
                "remove_tag": "taunt_remove",
                "z": 2,
            },
        ],
        "Shen E dash-trail/taunt marker visuals are not registered",
    )
    runtime = (MOD_ROOT / "src/lib.rs").read_text(encoding="utf-8")
    for marker in (
        "struct ShenShadowDashTauntNativeEffect;",
        "CCState::Taunt {",
        "target: caster_id",
        "fn expected_cc_time(&self) -> Option<usize>",
        "Some(SHEN_SHADOW_DASH_TAUNT_TICKS as usize)",
        '"lol_shen_shadow_dash_taunt_native"',
    ):
        check(marker in runtime, f"Shen native E runtime proof is missing: {marker}")
    check("ShenShadowDashInput" not in runtime, "Shen E must not restore a custom input-AI validator")
    if "impl ModEffectType for ShenShadowDashTauntNativeEffect {" in runtime:
        shen_native = runtime.split(
            "impl ModEffectType for ShenShadowDashTauntNativeEffect {", 1
        )[1].split("\nfn init(", 1)[0]
        check(".unwrap(" not in shen_native, "Shen E native effect must not unwrap stale entities")
        check(
            ".get_entity(caster_id)" in shen_native
            and ".get_entity(target_id)" in shen_native
            and shen_native.count(".is_some_and(|") == 2,
            "Shen E native effect must revalidate both live entities before applying taunt",
        )
        check(
            shen_native.count("ctx.apply_cc(") == 1
            and "ctx.apply_cc(\n            target_id,\n            CCState::Taunt {" in shen_native
            and shen_native.count("tick: SHEN_SHADOW_DASH_TAUNT_TICKS") == 1
            and shen_native.count("target: caster_id") == 1,
            "Shen E runtime impl must contain exactly one caster-targeted native taunt",
        )


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


def validate_briar_replacement_uniqueness() -> None:
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

    berserker_files = [filename for champion_id, filename in ids if champion_id == "berserker"]
    check(
        berserker_files == ["berserker.data_champion"],
        "Briar must replace official 004 exactly once through champion/berserker.data_champion",
    )
    check(
        all(champion_id != "lol_briar" for champion_id, _ in ids),
        "lol_briar must not be registered as an additive duplicate champion",
    )
    check(
        not (MOD_ROOT / "champion/lol_briar.data_champion").exists(),
        "champion/lol_briar.data_champion must be absent in same-ID replacement mode",
    )


def validate_briar_data_contract(champion: dict[str, Any]) -> None:
    check(champion.get("id") == "berserker", "Briar must rework official 004 with id berserker")
    check(
        champion.get("sprite") == "asset/lol_mod/aseprite_resources/champions/briar",
        "same-ID Briar must bind the custom Briar actor",
    )
    check(champion.get("anim_prefix") == "", "Briar must preserve native Berserker animation tags")
    check(champion.get("category") == "Melee", "Briar category must be Melee")
    check(
        set(champion.get("tags", [])) == {"AD", "Melee", "Heal", "Dot", "CC"},
        "Briar role tags must be AD/Melee/Heal/Dot/CC",
    )
    check(
        champion.get("skill_icons")
        == [
            "asset/lol_mod/icons/briar_skill",
            "asset/lol_mod/icons/briar_skill2",
            "asset/lol_mod/icons/briar_ult",
        ],
        "Briar active icon order must be Q/E/R",
    )
    check(len(champion.get("skill_icons", [])) == 3, "Briar must expose exactly three active icons")
    for unsupported_slot in ("w", "skill3", "skill4"):
        check(unsupported_slot not in champion, f"Briar must not add unsupported active slot {unsupported_slot}")

    check(
        champion.get("stat")
        == {
            "attack": 115,
            "magic_power": 0,
            "hp": 950,
            "defence": 25,
            "magic_resistance": 18,
            "move_speed": 1100,
            "hp_regen": 0,
            "stack": 0,
            "crit_chance": 0,
        },
        "Briar base stats do not match the approved design",
    )
    check(
        champion.get("growth")
        == {
            "attack": 20,
            "magic_power": 0,
            "hp": 100,
            "defence": 7,
            "magic_resistance": 4,
            "move_speed": 10,
            "hp_regen": 0,
            "stack": 0,
            "crit_chance": 0,
        },
        "Briar growth stats do not match the approved design",
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
        == ("attack", 25000, 50, 24, 12, True, "Targeting", "Enemy", "BaseAttack", False),
        "Briar basic-attack slot/timing/targeting mismatch",
    )
    attack_switch = attack.get("effect", {})
    check(attack_switch.get("type") == "SwitchByBuff", "Briar attack must branch through SwitchByBuff")
    check(
        attack_switch.get("buff_name") == "lol_briar_snack_ready",
        "Briar attack must branch on the one-use Snack marker",
    )
    normal_attack = attack_switch.get("effect_none", {})
    snack_attack = attack_switch.get("effect_buff", {})
    normal_damage = sorted(
        (effect.get("damage"), effect.get("attack_ratio"), effect.get("target_hp_ratio"))
        for effect in find_effect(normal_attack, "Attack")
    )
    check(
        normal_damage == [(0, 100, None), (4, 3, None)],
        "Briar normal attack must deal 100% Attack once plus one Crimson Curse tick payload",
    )
    snack_damage = sorted(
        (effect.get("damage"), effect.get("attack_ratio"), effect.get("target_hp_ratio"))
        for effect in find_effect(snack_attack, "Attack")
    )
    check(
        snack_damage == [(0, 100, None), (4, 3, None), (25, 40, 2)],
        "Briar empowered bite must add 25 + 40% Attack + 2% target max-HP damage exactly once",
    )
    snack_heals = find_effect(snack_attack, "Heal", amount=40, attack_ratio=15, ap_ratio=0, heal_type="Caster")
    check(len(snack_heals) == 1, "Briar empowered bite must heal 40 + 15% Attack exactly once")
    check(
        len(find_effect(snack_attack, "CasterAnimation", name="attack2", tick=24)) == 1,
        "Briar empowered bite must use the native attack2 action for 24 ticks",
    )
    check(
        len(find_effect(snack_attack, "RemoveCasterBuff", name="lol_briar_snack_ready")) == 1,
        "Briar empowered bite must consume the Snack marker exactly once",
    )

    # Crimson Curse is data-driven rather than a ModPassive.  It must be
    # attached exactly to normal attack, Snack, E and R, with identical ticks.
    bleeds = find_effect(champion, "AddCasted", casted_type="Bleed")
    check(len(bleeds) == 4, "Crimson Curse must be attached exactly to attack, Snack, E and R")
    for index, bleed in enumerate(bleeds):
        check(
            (bleed.get("duration"), bleed.get("period")) == (120, 60),
            f"Crimson Curse payload {index} must tick twice over 120 ticks",
        )
        bleed_damage = find_effect(bleed, "Attack")
        check(
            len(bleed_damage) == 1
            and (bleed_damage[0].get("damage"), bleed_damage[0].get("attack_ratio")) == (4, 3),
            f"Crimson Curse payload {index} damage must be 4 + 3% Attack",
        )
        bleed_heal = find_effect(bleed, "Heal")
        check(
            len(bleed_heal) == 1
            and (
                bleed_heal[0].get("amount"),
                bleed_heal[0].get("attack_ratio"),
                bleed_heal[0].get("ap_ratio"),
                bleed_heal[0].get("heal_type"),
            )
            == (2, 1, 0, "Caster"),
            f"Crimson Curse payload {index} sustain must be 2 + 1% Attack to the caster",
        )
        check(
            len(find_effect(bleed, "ViewEffect", name="lol_briar_bleed_tick_visual")) == 1,
            f"Crimson Curse payload {index} must trigger the bleed-tick visual",
        )
    curse_markers = [
        effect
        for effect in find_effect(champion, "AddBuff")
        if effect.get("buff_state", {}).get("name") == "lol_briar_crimson_curse"
    ]
    check(len(curse_markers) == 4, "Crimson Curse named marker must accompany all four bleed applications")
    for marker in curse_markers:
        check(
            marker.get("buff_state", {}).get("duration", {}).get("Time", {}).get("tick") == 120,
            "Crimson Curse marker must last 120 ticks",
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
        == ("skill1", 45000, 360, 20, 8, False, "Targeting", "EnemyChampion", "Skill", False),
        "Briar Q Blood Frenzy slot/timing/targeting mismatch",
    )
    check(len(find_effect(q, "Sfx", name="lol_briar_q_cast")) == 1, "Briar Q cast SFX is missing")
    check(
        len(find_effect(q, "CasterAnimation", name="skill1", tick=20)) == 1,
        "Briar Q must preserve the native skill1 action for 20 ticks",
    )
    check(
        len(find_effect(q, "ViewEffect", name="lol_briar_q_overhead_visual")) == 1,
        "Briar Q must trigger one target-following overhead impact visual",
    )
    q_views = [
        view
        for view in champion.get("view_effects", [])
        if view.get("name") == "lol_briar_q_overhead_visual"
    ]
    check(
        q_views
        == [
            {
                "type": "Animation",
                "name": "lol_briar_q_overhead_visual",
                "anim": "asset/lol_mod/aseprite_resources/effects/briar_q_overhead",
                "tag": "impact",
                "z": 2,
                "is_follow": True,
            }
        ],
        "Briar Q overhead impact must follow the target at foreground z=2",
    )
    check(
        not [
            buff
            for buff in champion.get("view_buffs", [])
            if buff.get("name") == "lol_briar_blood_frenzy"
        ],
        "Briar Q must not enclose the caster in the old persistent frenzy ring",
    )
    q_switches = find_effect(q, "SwitchByBuff", buff_name="lol_briar_certain_death_frenzy")
    check(len(q_switches) == 1, "Briar Q must branch once around the enhanced R frenzy")
    if q_switches:
        normal_branch = q_switches[0].get("effect_none", {})
        enhanced_branch = q_switches[0].get("effect_buff", {})
        normal_adds = {
            effect.get("buff_state", {}).get("name"): effect.get("buff_state", {})
            for effect in find_effect(normal_branch, "AddCasterBuff")
        }
        check(
            set(normal_adds) == {"lol_briar_blood_frenzy", "lol_briar_snack_ready"},
            "Briar Q normal branch must add only Blood Frenzy and one Snack marker",
        )
        frenzy = normal_adds.get("lol_briar_blood_frenzy", {})
        check(
            (
                frenzy.get("duration", {}).get("Time", {}).get("tick"),
                frenzy.get("attack_speed_mult"),
                frenzy.get("move_speed_mult"),
                frenzy.get("vamp"),
            )
            == (180, 60, 18, 25),
            "Briar Q Blood Frenzy must last 180 ticks with 60 AS/18 MS/25 Vamp",
        )
        check(
            normal_adds.get("lol_briar_snack_ready", {}).get("duration", {}).get("Time", {}).get("tick") == 180,
            "Briar Q Snack marker must last 180 ticks",
        )
        normal_removes = {effect.get("name") for effect in find_effect(normal_branch, "RemoveCasterBuff")}
        check(
            normal_removes == {"lol_briar_blood_frenzy", "lol_briar_snack_ready"},
            "Briar Q must clear stale normal frenzy/Snack state before applying a fresh window",
        )
        enhanced_adds = find_effect(enhanced_branch, "AddCasterBuff")
        check(
            len(enhanced_adds) == 1
            and enhanced_adds[0].get("buff_state", {}).get("name") == "lol_briar_snack_ready"
            and enhanced_adds[0].get("buff_state", {}).get("duration", {}).get("Time", {}).get("tick") == 180,
            "Briar Q during Certain Death must refresh only the 180-tick Snack marker",
        )
        check(
            not [
                effect
                for effect in find_effect(enhanced_branch, "AddCasterBuff")
                if effect.get("buff_state", {}).get("name") == "lol_briar_blood_frenzy"
            ],
            "Briar Q must not downgrade or replace the enhanced R frenzy",
        )

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
        == ("skill2", 50000, 480, 54, 1, False, "Direction", "EnemyWithoutTower", "Skill", False),
        "Briar E Chilling Scream slot/timing/direction mismatch",
    )
    check(
        len(find_effect(e, "CasterAnimation", name="skill2", tick=54)) == 1,
        "Briar E must hold the native skill2 actor action for the full 54 ticks",
    )
    guard = [
        effect
        for effect in find_effect(e, "AddCasterBuff")
        if effect.get("buff_state", {}).get("name") == "lol_briar_chilling_scream_guard"
    ]
    check(len(guard) == 1, "Briar E charge damage-reduction marker is missing")
    if guard:
        guard_state = guard[0].get("buff_state", {})
        check(
            (
                guard_state.get("duration", {}).get("Time", {}).get("tick"),
                guard_state.get("damaged_reduce"),
            )
            == (30, 35),
            "Briar E charge guard must last 30 ticks and reduce damage by 35%",
        )
    check(
        len(find_effect(e, "Heal", amount=50, attack_ratio=15, ap_ratio=0, heal_type="Caster")) == 1,
        "Briar E must heal 50 + 15% Attack exactly once per cast",
    )
    e_delays = find_effect(e, "Delayed", tick=30)
    check(len(e_delays) == 1, "Briar E must release after one fixed 30-tick charge")
    if e_delays:
        release = e_delays[0]
        check(len(find_effect(release, "Sfx", name="lol_briar_e_cast")) == 1, "Briar E release SFX must occur after the charge")
        visual_projectiles = find_effect(release, "LinearProjectile", name="lol_briar_e_scream_projectile")
        check(len(visual_projectiles) == 1, "Briar E must launch one forward scream visual")
        if visual_projectiles:
            visual = visual_projectiles[0]
            check(
                (
                    visual.get("penetrate"),
                    visual.get("speed"),
                    visual.get("range"),
                    visual.get("shape", {}).get("Circle", {}).get("radius"),
                    visual.get("applied_target"),
                    visual.get("applied_effects"),
                )
                == (True, 12000, 50000, 12000, "EnemyWithoutTower", []),
                "Briar E scream visual flight contract mismatch",
            )
        hitboxes = find_effect(release, "LineRangeProjectile", name="lol_briar_e_hitbox")
        check(len(hitboxes) == 1, "Briar E must create one narrow line hitbox")
        if hitboxes:
            hitbox = hitboxes[0]
            check(
                (
                    hitbox.get("width"),
                    hitbox.get("length"),
                    hitbox.get("delay"),
                    hitbox.get("apply"),
                    hitbox.get("applied_target"),
                )
                == (24000, 50000, 0, 1, "EnemyWithoutTower"),
                "Briar E hitbox width/length/timing/target mismatch",
            )
            e_damage = find_effect(hitbox, "Attack", damage=75, attack_ratio=100)
            check(len(e_damage) == 1, "Briar E must deal 75 + 100% Attack exactly once")
            check(
                len(find_effect(hitbox, "Knockback", speed=3000, tick=12)) == 1,
                "Briar E must knock enemies back at speed 3000 for 12 ticks",
            )
            check(len(find_effect(hitbox, "Airborne", duration=18)) == 1, "Briar E must knock enemies airborne for 18 ticks")
            check(len(find_effect(hitbox, "TargetSfx", name="lol_briar_e_hit")) == 1, "Briar E hit SFX is missing")

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
        == ("ult", 80000, 3600, 48, 1, False, "Targeting", "EnemyChampion", "Skill", False),
        "Briar R Certain Death slot/timing/targeting mismatch",
    )
    check(len(find_effect(ult, "Sfx", name="lol_briar_r_cast")) == 1, "Briar R cast SFX is missing")
    check(len(find_effect(ult, "ViewEffect", name="lol_briar_r_mark_visual")) == 1, "Briar R warning mark is missing")
    check(
        len(find_effect(ult, "CasterAnimation", name="ult_pre", tick=18)) == 1,
        "Briar R must warn/channel in ult_pre for 18 ticks",
    )
    r_delays = find_effect(ult, "Delayed", tick=18)
    check(len(r_delays) == 1, "Briar R must begin its chase after one 18-tick warning")
    if r_delays:
        chase = r_delays[0]
        check(
            len(find_effect(chase, "CasterAnimation", name="ult_dash", tick=30)) == 1,
            "Briar R chase must switch to the native ult_dash action",
        )
        check(
            len(find_effect(chase, "CasterViewEffect", name="lol_briar_r_trail_visual")) == 1,
            "Briar R chase trail must follow the caster",
        )
        moves = find_effect(chase, "MoveToTarget")
        check(len(moves) == 1, "Briar R must contain exactly one target-locked chase")
        if moves:
            move = moves[0]
            check(
                (move.get("speed"), move.get("range")) == (6000, 80000),
                "Briar R MoveToTarget speed/range mismatch",
            )
            arrival = move.get("end_effects", [])
            check(isinstance(arrival, list), "Briar R arrival effects must be a list")
            if not isinstance(arrival, list):
                arrival = []
            check(
                len(find_effect(arrival, "CasterAnimation", name="ult_attack", tick=24)) == 1,
                "Briar R arrival must use the native ult_attack action for 24 ticks",
            )
            check(len(find_effect(arrival, "Sfx", name="lol_briar_r_hit")) == 1, "Briar R arrival SFX is missing")
            check(
                len(find_effect(arrival, "ViewEffect", name="lol_briar_r_arrival_visual")) == 1,
                "Briar R arrival/fear visual is missing",
            )
            arrival_damage = find_effect(arrival, "Attack", damage=100, attack_ratio=120)
            check(len(arrival_damage) == 1, "Briar R arrival must deal 100 + 120% Attack exactly once")
            fear_zones = find_effect(arrival, "RangeEffect")
            check(len(fear_zones) == 1, "Briar R arrival must create exactly one fear zone")
            if fear_zones:
                fear_zone = fear_zones[0]
                check(
                    (
                        fear_zone.get("shape", {}).get("Circle", {}).get("radius"),
                        fear_zone.get("target"),
                        fear_zone.get("apply_type"),
                    )
                    == (30000, "EnemyChampion", "AroundCaster"),
                    "Briar R fear radius/target/origin mismatch",
                )
                check(len(find_effect(fear_zone, "Fear", tick=30)) == 1, "Briar R fear must last 30 ticks")
            removes = {effect.get("name") for effect in find_effect(arrival, "RemoveCasterBuff")}
            check(
                removes == {
                    "lol_briar_blood_frenzy",
                    "lol_briar_certain_death_frenzy",
                    "lol_briar_snack_ready",
                },
                "Briar R arrival must clear stale frenzy and Snack state",
            )
            arrival_buffs = {
                effect.get("buff_state", {}).get("name"): effect.get("buff_state", {})
                for effect in find_effect(arrival, "AddCasterBuff")
            }
            check(
                set(arrival_buffs) == {"lol_briar_certain_death_frenzy", "lol_briar_snack_ready"},
                "Briar R arrival must add only enhanced frenzy and one Snack marker",
            )
            enhanced = arrival_buffs.get("lol_briar_certain_death_frenzy", {})
            check(
                (
                    enhanced.get("duration", {}).get("Time", {}).get("tick"),
                    enhanced.get("attack_speed_mult"),
                    enhanced.get("move_speed_mult"),
                    enhanced.get("vamp"),
                    enhanced.get("defence"),
                    enhanced.get("magic_resistance"),
                    enhanced.get("toughness"),
                )
                == (240, 50, 25, 30, 20, 20, 20),
                "Briar R enhanced frenzy stats/duration mismatch",
            )
            check(
                arrival_buffs.get("lol_briar_snack_ready", {}).get("duration", {}).get("Time", {}).get("tick") == 240,
                "Briar R Snack marker must last 240 ticks",
            )
    check(not find_effect(ult, "LinearProjectile"), "Briar R v0.5 must remain a documented targeted chase, not a fake projectile")

    projectile_views = champion.get("view_projectiles", [])
    projectile_map = {view.get("name"): view for view in projectile_views}
    check(len(projectile_map) == len(projectile_views), "Briar projectile view names must be unique")
    check(set(projectile_map) == set(BRIAR_VIEW_PROJECTILES), "Briar projectile view binding set is incomplete")
    for name, (asset, tag, z, repeat) in BRIAR_VIEW_PROJECTILES.items():
        binding = projectile_map.get(name, {})
        check(
            (
                binding.get("type"),
                binding.get("anim"),
                binding.get("tag"),
                binding.get("z"),
                binding.get("repeat"),
            )
            == ("Animated", asset, tag, z, repeat),
            f"Briar projectile view binding mismatch: {name}",
        )

    effect_views = champion.get("view_effects", [])
    effect_map = {view.get("name"): view for view in effect_views}
    check(len(effect_map) == len(effect_views), "Briar effect view names must be unique")
    check(set(effect_map) == set(BRIAR_VIEW_EFFECTS), "Briar effect view binding set is incomplete")
    for name, (asset, tag, z, is_follow) in BRIAR_VIEW_EFFECTS.items():
        binding = effect_map.get(name, {})
        check(
            (
                binding.get("type"),
                binding.get("anim"),
                binding.get("tag"),
                binding.get("z"),
                binding.get("is_follow"),
            )
            == ("Animation", asset, tag, z, is_follow),
            f"Briar effect view binding mismatch: {name}",
        )
    triggered_visuals = {
        effect.get("name")
        for effect in walk_effects(champion)
        if effect.get("type") in {"ViewEffect", "CasterViewEffect"}
    }
    check(triggered_visuals == set(BRIAR_VIEW_EFFECTS), "Briar passive/Q/E/R visual trigger set is incomplete")
    check("lol_briar_e_hitbox" not in effect_map, "Briar E logic hitbox must not spawn a duplicate visual")

    buff_views = champion.get("view_buffs", [])
    buff_map = {view.get("name"): view for view in buff_views}
    check(len(buff_map) == len(buff_views), "Briar buff view names must be unique")
    check(set(buff_map) == set(BRIAR_VIEW_BUFFS), "Briar frenzy buff view binding set is incomplete")
    for name, (asset, pre_tag, loop_tag, remove_tag, z) in BRIAR_VIEW_BUFFS.items():
        binding = buff_map.get(name, {})
        check(
            (
                binding.get("type"),
                binding.get("anim"),
                binding.get("pre_tag"),
                binding.get("loop_tag"),
                binding.get("remove_tag"),
                binding.get("z"),
            )
            == ("ThreePhase", asset, pre_tag, loop_tag, remove_tag, z),
            f"Briar frenzy buff view binding mismatch: {name}",
        )

    actual_sfx = {
        effect.get("name")
        for effect in walk_effects(champion)
        if effect.get("type") in {"Sfx", "TargetSfx"}
    }
    check(actual_sfx == set(BRIAR_AUDIO_EVENTS), "Briar must wire exactly nine attack/Q/E/R audio events")


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

    # The first two idle poses use Orianna's native-like 34px battle class.
    # Source-direct portrait assets remain independent, while the actor keeps
    # two complete boots on the y=42 exclusive foot baseline.
    for index, frame in enumerate(idle_frames[:2]):
        alpha = frame.getchannel("A")
        bbox = alpha.getbbox()
        check(bbox is not None, f"Orianna primary idle {index} is empty")
        if bbox is None:
            continue
        width = bbox[2] - bbox[0]
        height = bbox[3] - bbox[1]
        check(height == 36, f"Orianna primary idle {index} must retain the reviewed 36px battle height")
        check(bbox[3] == 42, f"Orianna primary idle {index} must end at the exclusive y=42 foot baseline")
        check(17 <= width <= 26, f"Orianna primary idle {index} no longer has the compact full-body width")

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

    # All live upright commands use the final 34-36px state-stable class and
    # y=42 baseline. The old 28px lower bound admitted the visible attack/hit
    # shrink that prompted this full-frame repair.
    for tag in ("idle", "attack", "skill1", "skill2"):
        for index, frame in enumerate(frames_for(tag)):
            bbox = frame.getchannel("A").getbbox()
            check(bbox is not None, f"Orianna {tag} frame {index} is empty")
            if bbox is None:
                continue
            height = bbox[3] - bbox[1]
            check(34 <= height <= 36, f"Orianna {tag} frame {index} left the reviewed 34-36px actor scale class")
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
        check(height == 36, f"Orianna run frame {index} must retain the reviewed 36px visible height")
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
    required_manifest_paths = {
        "champion/barrier_magician.data_champion",
        "ui/champion_fullbody/barrier_magician.png",
        "ui/champion_portrait/barrier_magician_compact.png",
        "ui/champion_portrait/barrier_magician_scoreboard.png",
        "ui/champion_portrait/barrier_magician_grid.png",
    }
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


def validate_briar_native_animation_and_actor(champion: dict[str, Any]) -> None:
    sprite = champion.get("sprite", "")
    check(
        sprite == "asset/lol_mod/aseprite_resources/champions/briar",
        "Briar actor must use the local Briar animated asset",
    )
    sheet_path = MOD_ROOT / "aseprite_resources/champions/briar#sheet.png"
    anim_path = MOD_ROOT / "aseprite_resources/champions/briar#anim.fanim"
    check(sheet_path.is_file(), "missing Briar actor sheet")
    check(anim_path.is_file(), "missing Briar actor animation")
    if not sheet_path.is_file() or not anim_path.is_file():
        return

    sheet = Image.open(sheet_path).convert("RGBA")
    anims = load_json("aseprite_resources/champions/briar#anim.fanim").get("anims", {})
    check(sheet.size == (1792, 64), f"Briar actor atlas must be 28 64x64 cells (1792x64), got {sheet.size}")
    check(
        set(anims) == set(BRIAR_NATIVE_ANIMATION),
        "Briar actor must preserve all 24 native Berserker animation tags exactly",
    )

    for tag, expected_durations in BRIAR_NATIVE_ANIMATION.items():
        frames = anims.get(tag, {}).get("frames", [])
        check(len(frames) == len(expected_durations), f"Briar native tag {tag} frame count changed")
        for index, (frame, expected_duration) in enumerate(zip(frames, expected_durations)):
            try:
                duration = float(frame.get("duration", -1))
            except (TypeError, ValueError):
                duration = -1.0
            check(
                math.isclose(duration, expected_duration, rel_tol=0.0, abs_tol=1e-9),
                f"Briar native tag {tag} frame {index} duration changed from {expected_duration!r}",
            )
            data = frame.get("data", {})
            x = int(data.get("x", -1))
            y = int(data.get("y", -1))
            width = int(data.get("w", 0))
            height = int(data.get("h", 0))
            check(
                y == 0 and width == 64 and height == 64 and x >= 0 and x % 64 == 0,
                f"Briar native tag {tag} frame {index} must use one aligned 64x64 actor cell",
            )
            check(x + 64 <= sheet.width, f"Briar native tag {tag} frame {index} is out of bounds")

    cells = [sheet.crop((index * 64, 0, (index + 1) * 64, 64)) for index in range(28)]
    empty_cells = [index for index, cell in enumerate(cells) if cell.getchannel("A").getbbox() is None]
    check(empty_cells == [27], f"Briar actor atlas must contain only the native terminal transparent cell, got {empty_cells}")
    for tag in ("skill1_effect_old", "dead", "berserk_dead"):
        frames = anims.get(tag, {}).get("frames", [])
        check(bool(frames), f"Briar {tag} must retain its terminal transparent frame")
        if frames:
            data = frames[-1].get("data", {})
            x = int(data.get("x", -1))
            frame = sheet.crop((x, 0, x + 64, 64)) if 0 <= x <= sheet.width - 64 else Image.new("RGBA", (64, 64))
            check(x == 27 * 64 and frame.getchannel("A").getbbox() is None, f"Briar {tag} terminal frame must be fully transparent")

    def frame_images(tag: str) -> list[Image.Image]:
        result: list[Image.Image] = []
        for frame in anims.get(tag, {}).get("frames", []):
            data = frame.get("data", {})
            x = int(data.get("x", -1))
            if 0 <= x <= sheet.width - 64:
                result.append(sheet.crop((x, 0, x + 64, 64)))
        return result

    primary_idle = frame_images("idle")[:2]
    check(len(primary_idle) == 2, "Briar visual QA requires two primary idle identity frames")
    for index, frame in enumerate(primary_idle):
        alpha = frame.getchannel("A")
        bbox = alpha.getbbox()
        check(bbox is not None, f"Briar primary idle {index} is empty")
        if bbox is None:
            continue
        width = bbox[2] - bbox[0]
        height = bbox[3] - bbox[1]
        check(height == 38, f"Briar primary idle {index} must retain the native-like 38px actor height")
        check(bbox[3] == 45, f"Briar primary idle {index} must end on the exclusive y=45 foot baseline")
        check(20 <= width <= 28, f"Briar primary idle {index} left the 20-28px terrain-safe footprint")
        check(bbox[0] >= 2 and bbox[2] <= 62, f"Briar primary idle {index} touches a side edge")
        foot_x = [x for x in range(64) if alpha.getpixel((x, 44)) >= 128]
        foot_segments: list[list[int]] = []
        for x in foot_x:
            if not foot_segments or x > foot_segments[-1][-1] + 1:
                foot_segments.append([x])
            else:
                foot_segments[-1].append(x)
        check(
            len(foot_segments) == 2
            and min(len(segment) for segment in foot_segments) >= 5
            and foot_segments[1][0] - foot_segments[0][-1] >= 3,
            f"Briar primary idle {index} must show two complete separated feet",
        )

    run_frames = frame_images("run")
    check(len(run_frames) == 8, "Briar must keep eight native run phases")
    run_hashes: list[str] = []
    run_areas: list[int] = []
    lower_sets: list[set[tuple[int, int]]] = []
    for index, frame in enumerate(run_frames):
        alpha = frame.getchannel("A")
        bbox = alpha.getbbox()
        check(bbox is not None, f"Briar run frame {index} is empty")
        if bbox is None:
            continue
        width = bbox[2] - bbox[0]
        height = bbox[3] - bbox[1]
        check(height == 38, f"Briar run frame {index} must retain the native-like 38px actor height")
        check(bbox[3] == 45, f"Briar run frame {index} must retain the y=44 foot pixels")
        check(27 <= width <= 38, f"Briar run frame {index} left the 27-38px terrain-safe footprint")
        area = sum(alpha.getpixel((x, y)) >= 128 for y in range(64) for x in range(64))
        check(area >= 520, f"Briar run frame {index} loses too much body/lower-leg detail")
        run_areas.append(area)
        run_hashes.append(hashlib.sha256(frame.tobytes()).hexdigest())
        lower_sets.append({(x, y) for y in range(30, 46) for x in range(64) if alpha.getpixel((x, y)) >= 128})
    check(len(set(run_hashes)) == 8, "Briar run cycle must contain eight distinct image-generated gait phases")
    if run_areas:
        mean_area = sum(run_areas) / len(run_areas)
        area_cv = (sum((area - mean_area) ** 2 for area in run_areas) / len(run_areas)) ** 0.5 / mean_area
        check(area_cv <= 0.10, f"Briar run body area jumps too much between frames: CV={area_cv:.1%}")
    differences: list[float] = []
    for current, following in zip(lower_sets, lower_sets[1:] + lower_sets[:1], strict=True):
        union = current | following
        differences.append(len(current ^ following) / len(union) if union else 0.0)
    if differences:
        check(min(differences) >= 0.20, "Briar adjacent run frames are too similar to show a gait phase")
        check(max(differences) <= 0.75, "Briar adjacent run frames change too abruptly")

    for tag in ("idle", "berserk_idle", "attack", "attack2", "berserk_attack", "skill1", "skill2", "skill2_berserk", "hit"):
        for index, frame in enumerate(frame_images(tag)):
            bbox = frame.getchannel("A").getbbox()
            check(bbox is not None, f"Briar core actor {tag} frame {index} is empty")
            if bbox is not None:
                check(bbox[3] == 45, f"Briar core actor {tag} frame {index} changed the y=44 foot baseline")
                check(bbox[0] >= 2 and bbox[2] <= 62, f"Briar core actor {tag} frame {index} touches a side edge")


def validate_briar_resources_and_manifest(champion: dict[str, Any]) -> None:
    prefix = "asset/lol_mod/"
    required_manifest_paths = {
        "champion/berserker.data_champion",
        "aseprite_resources/champions/briar#sheet.png",
        "aseprite_resources/champions/briar#anim.fanim",
        "ui/champion_fullbody/berserker.png",
        "ui/champion_portrait/berserker_compact.png",
        "ui/champion_portrait/berserker_scoreboard.png",
        "ui/champion_portrait/berserker_grid.png",
        "style/champion_view.champion_view",
        "text/champion.i18n",
    }

    for icon_asset in champion.get("skill_icons", []):
        check(isinstance(icon_asset, str) and icon_asset.startswith(prefix), "Briar icon must use a local lol_mod asset")
        if not isinstance(icon_asset, str) or not icon_asset.startswith(prefix):
            continue
        relative = f"{icon_asset.removeprefix(prefix)}.png"
        required_manifest_paths.add(relative)
        path = MOD_ROOT / relative
        check(path.is_file(), f"missing Briar icon: {relative}")
        if path.is_file():
            icon = Image.open(path).convert("RGBA")
            check(icon.size == (64, 64), f"{relative} must be 64x64")
            check(icon.getchannel("A").getbbox() == (0, 0, 64, 64), f"{relative} must be full-bleed")
    icon_files = [MOD_ROOT / f"icons/briar_{suffix}.png" for suffix in ("skill", "skill2", "ult")]
    if all(path.is_file() for path in icon_files):
        check(len({sha256(path) for path in icon_files}) == 3, "Briar Q/E/R icons must be visually distinct files")

    for effect_name, (expected_size, expected_tags) in BRIAR_EFFECT_ANIMATION.items():
        sheet_relative = f"aseprite_resources/effects/{effect_name}#sheet.png"
        anim_relative = f"aseprite_resources/effects/{effect_name}#anim.fanim"
        required_manifest_paths.update({sheet_relative, anim_relative})
        sheet_path = MOD_ROOT / sheet_relative
        anim_path = MOD_ROOT / anim_relative
        check(sheet_path.is_file(), f"missing Briar VFX sheet: {sheet_relative}")
        check(anim_path.is_file(), f"missing Briar VFX animation: {anim_relative}")
        if not sheet_path.is_file() or not anim_path.is_file():
            continue
        sheet = Image.open(sheet_path).convert("RGBA")
        anims = load_json(anim_relative).get("anims", {})
        check(sheet.size == expected_size, f"{sheet_relative} must be {expected_size}, got {sheet.size}")
        check(set(anims) == set(expected_tags), f"{anim_relative} has the wrong Briar VFX tag set")
        all_hashes: list[str] = []
        for tag, expected_durations in expected_tags.items():
            frames = anims.get(tag, {}).get("frames", [])
            check(len(frames) == len(expected_durations), f"{anim_relative}: tag {tag} frame count changed")
            for index, (frame, expected_duration) in enumerate(zip(frames, expected_durations)):
                duration = float(frame.get("duration", -1))
                check(
                    math.isclose(duration, expected_duration, rel_tol=0.0, abs_tol=1e-9),
                    f"{anim_relative}: tag {tag} frame {index} duration changed",
                )
                data = frame.get("data", {})
                x = int(data.get("x", -1))
                y = int(data.get("y", -1))
                width = int(data.get("w", 0))
                height = int(data.get("h", 0))
                check(x >= 0 and y >= 0 and width > 0 and height > 0, f"{anim_relative}: invalid frame in {tag}")
                check(x + width <= sheet.width and y + height <= sheet.height, f"{anim_relative}: out-of-bounds frame in {tag}")
                if x >= 0 and y >= 0 and width > 0 and height > 0 and x + width <= sheet.width and y + height <= sheet.height:
                    image = sheet.crop((x, y, x + width, y + height))
                    check(image.getchannel("A").getbbox() is not None, f"{anim_relative}: empty {tag} frame {index}")
                    all_hashes.append(hashlib.sha256(image.tobytes()).hexdigest())
        check(len(all_hashes) == len(set(all_hashes)), f"{effect_name} VFX must keep distinct generated phases")

    manifest = load_json("build_manifest.json")
    manifest_paths = {row.get("path") for row in manifest.get("files", [])}
    missing_manifest_paths = sorted(required_manifest_paths - manifest_paths)
    check(
        not missing_manifest_paths,
        "Briar runtime resources are missing from build_manifest.json: " + ", ".join(missing_manifest_paths),
    )


def validate_orianna_briar_hd_surfaces() -> None:
    runtime_path = MOD_ROOT / "src/lib.rs"
    check(runtime_path.is_file(), "portrait runtime source is missing")
    runtime = runtime_path.read_text(encoding="utf-8") if runtime_path.is_file() else ""
    check(
        "rewrite_orianna_briar_portrait_render_commands(state);" in runtime,
        "Orianna/Briar source-direct UI portrait router is not active",
    )

    specs = (
        (
            "Orianna",
            "barrier_magician",
            "orianna_actor_contact_alpha.png",
            "orianna_hd_surface_qa.json",
            "orianna_portrait_surface_final.png",
            [23, 6, 40, 42],
            "ORIANNA_SCOREBOARD_PORTRAIT_TEXTURE",
        ),
        (
            "Briar",
            "berserker",
            "briar_actor_contact_alpha.png",
            "briar_hd_surface_qa.json",
            "briar_portrait_surface_final.png",
            [21, 7, 43, 45],
            "BRIAR_SCOREBOARD_PORTRAIT_TEXTURE",
        ),
    )
    for (
        champion,
        champion_id,
        source_name,
        qa_name,
        contact_name,
        expected_idle_bbox,
        runtime_constant,
    ) in specs:
        check(runtime_constant in runtime, f"{champion} scoreboard portrait route is missing")
        qa_path = MOD_ROOT / "qa" / qa_name
        contact_path = MOD_ROOT / "qa" / contact_name
        check(qa_path.is_file(), f"{champion} HD surface QA record is missing")
        check(contact_path.is_file(), f"{champion} HD surface contact is missing")
        if not qa_path.is_file():
            continue
        qa = load_json(f"qa/{qa_name}")
        check(qa.get("champion") == champion, f"{champion} HD surface QA identity changed")
        check(qa.get("native_id") == champion_id, f"{champion} HD native-id route changed")
        expected_source = f"source/processed/{source_name}"
        check(
            qa.get("accepted_source") == expected_source,
            f"{champion} portraits must use the accepted high-resolution actor source",
        )
        source_path = MOD_ROOT / expected_source
        check(source_path.is_file(), f"{champion} accepted portrait source is missing")
        if source_path.is_file():
            check(
                qa.get("accepted_source_sha256") == sha256(source_path),
                f"{champion} accepted portrait source hash changed",
            )

        battle = qa.get("battle_actor", {})
        check(battle.get("uniform_xy_scale") is True, f"{champion} actor must use uniform x/y scale")
        check(battle.get("x_only_compression") is False, f"{champion} actor must forbid x-only compression")
        check(
            battle.get("first_idle_alpha_bbox") == expected_idle_bbox,
            f"{champion} primary battle idle bbox changed",
        )
        face = battle.get("face_readability", {})
        check(face.get("opaque_pixels", 0) >= 120, f"{champion} battle face area became too small")
        check(
            face.get("luminance_dynamic_range", 0) >= 140,
            f"{champion} battle face contrast regressed",
        )

        surfaces = qa.get("surfaces", {})
        expected_surfaces = {
            "side_card": (f"BanPickIllust/{champion_id}.png", [1420, 860]),
            "encyclopedia": (f"ui/champion_fullbody/{champion_id}.png", [64, 64]),
            "sidebar": (f"ui/champion_portrait/{champion_id}_compact.png", [64, 64]),
            "scoreboard": (
                f"ui/champion_portrait/{champion_id}_scoreboard.png",
                [64, 64],
            ),
            "bp_grid": (f"ui/champion_portrait/{champion_id}_grid.png", [90, 122]),
        }
        for surface, (relative, dimensions) in expected_surfaces.items():
            record = surfaces.get(surface, {})
            path = MOD_ROOT / relative
            check(record.get("path") == relative, f"{champion} {surface} route changed")
            check(record.get("dimensions") == dimensions, f"{champion} {surface} dimensions changed")
            check(path.is_file(), f"{champion} {surface} image is missing")
            if not path.is_file():
                continue
            image = Image.open(path).convert("RGBA")
            bbox = image.getchannel("A").getbbox()
            expected_bbox = list(bbox) if bbox else None
            check(
                record.get("alpha_bbox") == expected_bbox,
                f"{champion} {surface} bbox record is stale",
            )
            check(record.get("sha256") == sha256(path), f"{champion} {surface} hash record is stale")
            if surface != "side_card":
                check(
                    record.get("hard_alpha") is True,
                    f"{champion} {surface} must use hard alpha",
                )

        grid_bbox = surfaces.get("bp_grid", {}).get("alpha_bbox")
        check(
            isinstance(grid_bbox, list) and grid_bbox[3] <= 86,
            f"{champion} BP-grid alpha must end at or before y=86",
        )
        check(
            surfaces.get("bp_grid", {}).get("name_band_clearance", -1) >= 10,
            f"{champion} BP-grid needs ten transparent pixels before name-band y=96",
        )
        check(
            surfaces.get("sidebar", {}).get("sha256")
            != surfaces.get("scoreboard", {}).get("sha256"),
            f"{champion} sidebar and scoreboard must remain independent crops",
        )


def validate_sivir_replacement_uniqueness() -> None:
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
    files = [filename for champion_id, filename in ids if champion_id == "boomerang_hunter"]
    check(
        files == ["boomerang_hunter.data_champion"],
        "Sivir must replace official 005 exactly once through champion/boomerang_hunter.data_champion",
    )
    check(
        all(champion_id != "lol_sivir" for champion_id, _ in ids),
        "lol_sivir must not be registered as an additive duplicate champion",
    )
    check(
        not (MOD_ROOT / "champion/lol_sivir.data_champion").exists(),
        "champion/lol_sivir.data_champion must be absent in same-ID replacement mode",
    )


def validate_sivir_data_contract(champion: dict[str, Any]) -> None:
    check(champion.get("id") == "boomerang_hunter", "Sivir must retain native id boomerang_hunter")
    check(
        champion.get("sprite") == "asset/lol_mod/aseprite_resources/champions/sivir",
        "same-ID Sivir must bind the custom Sivir actor",
    )
    check(champion.get("anim_prefix") == "", "Sivir must preserve native animation tags")
    check(champion.get("category") == "Range", "Sivir category must be Range")
    check(set(champion.get("tags", [])) == {"AD", "Range", "Heal"}, "Sivir tags must be AD/Range/Heal")
    check(
        champion.get("skill_icons")
        == [
            "asset/lol_mod/icons/sivir_skill",
            "asset/lol_mod/icons/sivir_skill2",
            "asset/lol_mod/icons/sivir_ult",
        ],
        "Sivir active icon order must be Q/E/R",
    )
    check(len(champion.get("skill_icons", [])) == 3, "Sivir must expose exactly three active icons")
    for unsupported_slot in ("w", "skill3", "skill4"):
        check(unsupported_slot not in champion, f"Sivir must not add unsupported active slot {unsupported_slot}")

    check(
        champion.get("stat")
        == {
            "attack": 100,
            "magic_power": 0,
            "hp": 900,
            "defence": 20,
            "magic_resistance": 20,
            "move_speed": 900,
            "hp_regen": 2,
            "stack": 0,
            "crit_chance": 0,
        },
        "Sivir base stats do not match the approved design",
    )
    check(
        champion.get("growth")
        == {
            "attack": 18,
            "magic_power": 0,
            "hp": 90,
            "defence": 7,
            "magic_resistance": 3,
            "move_speed": 9,
            "hp_regen": 1,
            "stack": 0,
            "crit_chance": 0,
        },
        "Sivir growth stats do not match the approved design",
    )

    attack = champion.get("attack", {})
    check(
        (
            attack.get("action_name"), attack.get("range"), attack.get("cooltime"),
            attack.get("duration"), attack.get("start_timing"), attack.get("casting_type"),
            attack.get("casting_target"), attack.get("attack_type"),
        )
        == ("attack", 60000, 60, 26, 20, "Targeting", "Enemy", "BaseAttack"),
        "Sivir basic-attack slot/timing/targeting mismatch",
    )
    attack_projectiles = find_effect(attack, "TargetProjectile", name="lol_sivir_attack_blade")
    check(len(attack_projectiles) == 1, "Sivir attack must create exactly one crossblade projectile")
    if attack_projectiles:
        projectile = attack_projectiles[0]
        check((projectile.get("speed"), projectile.get("applied_target")) == (6000, "Enemy"), "Sivir attack projectile contract mismatch")
        check(len(find_effect(projectile, "Attack", damage=0, attack_ratio=100)) == 1, "Sivir attack must deal 100% Attack once")
        fleet = [effect for effect in find_effect(projectile, "AddCasterBuff") if effect.get("buff_state", {}).get("name") == "lol_sivir_fleet_of_foot"]
        check(len(fleet) == 1, "Sivir attack must add one Fleet of Foot buff")
        if fleet:
            state = fleet[0].get("buff_state", {})
            check((state.get("duration", {}).get("Time", {}).get("tick"), state.get("move_speed_mult")) == (90, 12), "Fleet of Foot must grant 12% Move Speed for 90 ticks")
    check(len(find_effect(attack, "Sfx", name="lol_sivir_attack_cast")) == 1, "Sivir attack cast SFX is missing")
    check(len(find_effect(attack, "TargetSfx", name="lol_sivir_attack_hit")) == 1, "Sivir attack hit SFX is missing")

    q = champion.get("skill", {})
    check(
        (
            q.get("action_name"), q.get("range"), q.get("cooltime"), q.get("duration"),
            q.get("start_timing"), q.get("casting_type"), q.get("casting_target"), q.get("attack_type"),
        )
        == ("skill", 75000, 360, 26, 18, "Direction", "EnemyWithoutTower", "Skill"),
        "Sivir Q slot/timing/direction mismatch",
    )
    outgoing = find_effect(q, "LinearProjectile", name="lol_sivir_q_outgoing")
    check(len(outgoing) == 1, "Sivir Q must contain one outbound LinearProjectile")
    returns = find_effect(q, "BackToCasterLinearProjectile", name="lol_sivir_q_return")
    check(len(returns) == 1, "Sivir Q must contain one nested return projectile")
    if outgoing:
        out = outgoing[0]
        check(
            (out.get("penetrate"), out.get("speed"), out.get("range"), out.get("shape", {}).get("Circle", {}).get("radius"), out.get("applied_target"))
            == (True, 4200, 75000, 7000, "EnemyWithoutTower"),
            "Sivir Q outbound projectile contract mismatch",
        )
        nested_returns = [effect for effect in out.get("end_effects", []) if effect.get("type") == "BackToCasterLinearProjectile"]
        check(len(nested_returns) == 1 and nested_returns[0] is returns[0], "Sivir Q return must be nested inside outbound end_effects")
        out_damage = find_effect(out.get("applied_effects", []), "Attack")
        check(len(out_damage) == 1 and (out_damage[0].get("damage"), out_damage[0].get("attack_ratio")) == (30, 55), "Sivir Q outbound damage must be 30 + 55% Attack")
    if returns:
        returning = returns[0]
        check(
            (returning.get("penetrate"), returning.get("speed"), returning.get("range"), returning.get("shape", {}).get("Circle", {}).get("radius"), returning.get("applied_target"))
            == (True, 5200, 120000, 7000, "EnemyWithoutTower"),
            "Sivir Q return projectile contract mismatch",
        )
        return_damage = find_effect(returning.get("applied_effects", []), "Attack")
        check(len(return_damage) == 1 and (return_damage[0].get("damage"), return_damage[0].get("attack_ratio")) == (30, 55), "Sivir Q return damage must be 30 + 55% Attack")
    check(len(find_effect(q, "CasterAnimation", name="idle_no_boomerang", tick=42)) == 1, "Sivir Q must hide the held weapon while the boomerang is in flight")
    check(len(find_effect(q, "Sfx", name="lol_sivir_q_out")) == 1, "Sivir Q outbound SFX must play once")
    check(len(find_effect(q, "Sfx", name="lol_sivir_q_return")) == 1, "Sivir Q return SFX must play once")
    check(len(find_effect(q, "TargetSfx", name="lol_sivir_q_hit")) == 2, "Sivir Q hit SFX must exist once per pass")

    e = champion.get("skill2", {})
    check(
        (
            e.get("action_name"), e.get("range"), e.get("cooltime"), e.get("duration"),
            e.get("start_timing"), e.get("casting_type"), e.get("casting_target"), e.get("attack_type"),
        )
        == ("skill2", 0, 720, 25, 20, "None", "AllyOnlySelf", "Skill"),
        "Sivir E slot/timing/self-target mismatch",
    )
    window = [effect for effect in find_effect(e, "AddCasterBuff") if effect.get("buff_state", {}).get("name") == "lol_sivir_spell_shield_window"]
    speed = [effect for effect in find_effect(e, "AddCasterBuff") if effect.get("buff_state", {}).get("name") == "lol_sivir_spell_shield_speed"]
    check(len(window) == 1, "Sivir E must add one named spell-shield window")
    if window:
        state = window[0].get("buff_state", {})
        check((state.get("duration", {}).get("Time", {}).get("tick"), state.get("skill_damaged_reduce")) == (90, 100), "Sivir E must reduce skill damage by 100% for 90 ticks")
    check(len(speed) == 1, "Sivir E must add one speed buff")
    if speed:
        state = speed[0].get("buff_state", {})
        check((state.get("duration", {}).get("Time", {}).get("tick"), state.get("move_speed_mult")) == (120, 20), "Sivir E speed must be 20% for 120 ticks")
    check(len(find_effect(e, "Heal", amount=60, attack_ratio=15, ap_ratio=0, heal_type="Caster")) == 1, "Sivir E must heal 60 + 15% Attack once")
    check(not find_effect(e, "Attack") and not find_effect(e, "ApAttack") and not find_effect(e, "FixedAttack"), "Sivir E must not deal damage")
    check(not find_effect(e, "Shield"), "Sivir E must not fake a normal absorb shield")
    check(len(find_effect(e, "Sfx", name="lol_sivir_e_cast")) == 1, "Sivir E cast SFX must play once")

    ult = champion.get("ult", {})
    check(
        (
            ult.get("action_name"), ult.get("range"), ult.get("cooltime"), ult.get("duration"),
            ult.get("start_timing"), ult.get("casting_type"), ult.get("casting_target"), ult.get("attack_type"),
        )
        == ("ult", 85000, 3000, 28, 20, "Targeting", "EnemyChampion", "Skill"),
        "Sivir R slot/timing/combat trigger mismatch",
    )
    ranges = find_effect(ult, "RangeEffect")
    check(len(ranges) == 1, "Sivir R must contain exactly one ally RangeEffect")
    if ranges:
        zone = ranges[0]
        check((zone.get("shape", {}).get("Circle", {}).get("radius"), zone.get("target"), zone.get("apply_type")) == (100000, "AllyChampion", "AroundCaster"), "Sivir R radius/target/origin mismatch")
        buffs = find_effect(zone, "AddBuff")
        check(len(buffs) == 1, "Sivir R ally zone must apply exactly one buff")
        if buffs:
            state = buffs[0].get("buff_state", {})
            check((state.get("name"), state.get("duration", {}).get("Time", {}).get("tick"), state.get("move_speed_mult")) == ("lol_sivir_on_the_hunt_speed", 300, 25), "Sivir R speed buff must be 25% for 300 ticks")
        check(not find_effect(zone, "Sfx"), "Sivir R cast SFX must not repeat per ally")
    check(not find_effect(ult, "AddCasterBuff"), "Sivir R must not add a second self-only speed buff")
    check(not find_effect(ult, "Attack") and not find_effect(ult, "ApAttack") and not find_effect(ult, "FixedAttack"), "Sivir R must deal no damage")
    check(not find_effect(ult, "Shield"), "Sivir R must provide no shield")
    check(len(find_effect(ult, "Sfx", name="lol_sivir_r_cast")) == 1, "Sivir R command SFX must play once")
    check(len(find_effect(ult, "CasterViewEffect", name="lol_sivir_r_cast_visual")) == 1, "Sivir R cast pulse is missing")

    projectile_map = {view.get("name"): view for view in champion.get("view_projectiles", [])}
    check(set(projectile_map) == set(SIVIR_VIEW_PROJECTILES), "Sivir projectile view binding set is incomplete")
    for name, (asset, tag, z, repeat) in SIVIR_VIEW_PROJECTILES.items():
        view = projectile_map.get(name, {})
        check((view.get("type"), view.get("anim"), view.get("tag"), view.get("z"), view.get("repeat")) == ("Animated", asset, tag, z, repeat), f"Sivir projectile view mismatch: {name}")
    effect_map = {view.get("name"): view for view in champion.get("view_effects", [])}
    check(set(effect_map) == set(SIVIR_VIEW_EFFECTS), "Sivir effect view binding set is incomplete")
    for name, (asset, tag, z, is_follow) in SIVIR_VIEW_EFFECTS.items():
        view = effect_map.get(name, {})
        check((view.get("type"), view.get("anim"), view.get("tag"), view.get("z"), view.get("is_follow")) == ("Animation", asset, tag, z, is_follow), f"Sivir effect view mismatch: {name}")
    buff_map = {view.get("name"): view for view in champion.get("view_buffs", [])}
    check(set(buff_map) == set(SIVIR_VIEW_BUFFS), "Sivir buff view binding set is incomplete")
    for name, (asset, pre, loop, remove, z) in SIVIR_VIEW_BUFFS.items():
        view = buff_map.get(name, {})
        check((view.get("type"), view.get("anim"), view.get("pre_tag"), view.get("loop_tag"), view.get("remove_tag"), view.get("z")) == ("ThreePhase", asset, pre, loop, remove, z), f"Sivir buff view mismatch: {name}")


def validate_sivir_native_animation_and_resources(champion: dict[str, Any]) -> None:
    sheet_path = MOD_ROOT / "aseprite_resources/champions/sivir#sheet.png"
    anim = load_json("aseprite_resources/champions/sivir#anim.fanim").get("anims", {})
    check(sheet_path.is_file(), "Sivir actor sheet is missing")
    if not sheet_path.is_file():
        return
    sheet = Image.open(sheet_path).convert("RGBA")
    check(sheet.size == (1984, 64), f"Sivir actor sheet must be 1984x64, got {sheet.size}")
    check(set(anim) == set(SIVIR_NATIVE_ANIMATION), "Sivir must preserve all 12 native Boomerang Hunter tags")
    core_tags = {"idle", "run", "attack", "idle_no_boomerang", "skill", "skill2", "ult", "hit"}
    run_hashes: list[str] = []
    attack_hashes: list[str] = []
    for tag, expected_durations in SIVIR_NATIVE_ANIMATION.items():
        frames = anim.get(tag, {}).get("frames", [])
        check(len(frames) == len(expected_durations), f"Sivir native tag {tag} frame count changed")
        for index, (frame, expected_duration) in enumerate(zip(frames, expected_durations)):
            check(math.isclose(float(frame.get("duration", -1)), expected_duration, rel_tol=0.0, abs_tol=1e-9), f"Sivir native tag {tag} frame {index} duration changed")
            data = frame.get("data", {})
            x, y, width, height = (int(data.get("x", -1)), int(data.get("y", -1)), int(data.get("w", 0)), int(data.get("h", 0)))
            check(x >= 0 and y >= 0 and width > 0 and height > 0 and x + width <= sheet.width and y + height <= sheet.height, f"Sivir native tag {tag} frame {index} is out of bounds")
            if not (x >= 0 and y >= 0 and width > 0 and height > 0 and x + width <= sheet.width and y + height <= sheet.height):
                continue
            image = sheet.crop((x, y, x + width, y + height))
            bbox = image.getchannel("A").getbbox()
            if tag == "dead" and index == len(frames) - 1:
                check(bbox is None, "Sivir dead final frame must remain transparent")
                continue
            check(bbox is not None, f"Sivir native tag {tag} frame {index} is empty")
            if bbox is None:
                continue
            if tag in core_tags:
                visible_width = bbox[2] - bbox[0]
                visible_height = bbox[3] - bbox[1]
                check(bbox[3] == 45, f"Sivir core {tag} frame {index} must retain the exclusive y=45 foot baseline")
                check(27 <= visible_height <= 38, f"Sivir core {tag} frame {index} left the native-like actor scale")
                check(18 <= visible_width <= 58 and bbox[0] >= 2 and bbox[2] <= 62, f"Sivir core {tag} frame {index} left the battle-safe width")
            if tag == "run":
                run_hashes.append(hashlib.sha256(image.tobytes()).hexdigest())
                check(35 <= bbox[3] - bbox[1] <= 37, f"Sivir run frame {index} must remain in the 35..37px terrain-safe band")
            if tag == "attack":
                attack_hashes.append(hashlib.sha256(image.tobytes()).hexdigest())
                check(len(alpha_component_sizes(image)) == 1, f"Sivir attack frame {index} contains detached pixels or a duplicate weapon")
                mirrored = image.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
                check(len(alpha_component_sizes(mirrored)) == 1, f"Sivir mirrored attack frame {index} contains detached pixels")
                mirrored_bbox = mirrored.getchannel("A").getbbox()
                check(mirrored_bbox is not None and mirrored_bbox[0] >= 2 and mirrored_bbox[2] <= 62, f"Sivir mirrored attack frame {index} leaves the battle-safe width")
                check(
                    all(
                        image.getpixel((pixel_x, pixel_y)) == (0, 0, 0, 0)
                        for pixel_y in range(image.height)
                        for pixel_x in range(image.width)
                        if image.getpixel((pixel_x, pixel_y))[3] == 0
                    ),
                    f"Sivir attack frame {index} has hidden RGB in transparent pixels",
                )
            if tag == "idle_no_boomerang":
                check(
                    bbox[3] - bbox[1] >= 29,
                    "Sivir idle_no_boomerang must retain the full-scale empty-hand body",
                )
    check(len(set(run_hashes)) == 8, "Sivir must keep eight distinct generated run phases")
    check(len(set(attack_hashes)) >= 4, "Sivir attack must retain at least four distinct clean poses")

    required_manifest_paths = {
        "champion/boomerang_hunter.data_champion",
        "aseprite_resources/champions/sivir#sheet.png",
        "aseprite_resources/champions/sivir#anim.fanim",
        "style/champion_view.champion_view",
        "text/champion.i18n",
    }
    icon_paths: list[Path] = []
    for asset in champion.get("skill_icons", []):
        relative = asset.removeprefix("asset/lol_mod/") + ".png"
        required_manifest_paths.add(relative)
        path = MOD_ROOT / relative
        icon_paths.append(path)
        check(path.is_file(), f"missing Sivir icon: {relative}")
        if path.is_file():
            icon = Image.open(path).convert("RGBA")
            check(icon.size == (64, 64) and icon.getchannel("A").getbbox() == (0, 0, 64, 64), f"{relative} must be a full-bleed 64x64 icon")
    if all(path.is_file() for path in icon_paths):
        check(len({sha256(path) for path in icon_paths}) == 3, "Sivir Q/E/R icons must be distinct")

    for effect_name, (expected_size, expected_tags) in SIVIR_EFFECT_ANIMATION.items():
        sheet_relative = f"aseprite_resources/effects/{effect_name}#sheet.png"
        anim_relative = f"aseprite_resources/effects/{effect_name}#anim.fanim"
        required_manifest_paths.update({sheet_relative, anim_relative})
        effect_sheet_path = MOD_ROOT / sheet_relative
        effect_anim = load_json(anim_relative).get("anims", {})
        check(effect_sheet_path.is_file(), f"missing Sivir VFX sheet: {sheet_relative}")
        if not effect_sheet_path.is_file():
            continue
        effect_sheet = Image.open(effect_sheet_path).convert("RGBA")
        check(effect_sheet.size == expected_size, f"{sheet_relative} must be {expected_size}, got {effect_sheet.size}")
        check(set(effect_anim) == set(expected_tags), f"{anim_relative} has the wrong tag set")
        hashes: list[str] = []
        for tag, expected_durations in expected_tags.items():
            frames = effect_anim.get(tag, {}).get("frames", [])
            check(len(frames) == len(expected_durations), f"{anim_relative}: {tag} frame count changed")
            for index, (frame, duration) in enumerate(zip(frames, expected_durations)):
                check(math.isclose(float(frame.get("duration", -1)), duration, rel_tol=0.0, abs_tol=1e-9), f"{anim_relative}: {tag} duration changed")
                data = frame.get("data", {})
                x, y, width, height = (int(data.get("x", -1)), int(data.get("y", -1)), int(data.get("w", 0)), int(data.get("h", 0)))
                image = effect_sheet.crop((x, y, x + width, y + height))
                bbox = image.getchannel("A").getbbox()
                check(bbox is not None, f"{anim_relative}: empty {tag} frame {index}")
                if bbox is not None and effect_name == "sivir_e_shield" and tag == "loop":
                    check(bbox[2] - bbox[0] >= 52 and bbox[3] - bbox[1] >= 52, f"Sivir E loop frame {index} must fully surround the actor")
                if bbox is not None and effect_name == "sivir_hunt_buff":
                    check(bbox[1] >= 22 and bbox[3] == 32 and bbox[3] - bbox[1] <= 10, f"Sivir R speed frame {index} must remain a foot-only trail")
                hashes.append(hashlib.sha256(image.tobytes()).hexdigest())
        check(len(hashes) == len(set(hashes)), f"{effect_name} must retain distinct generated phases")

    for event_name in SIVIR_AUDIO_EVENTS:
        local = event_name.removeprefix("lol_")
        required_manifest_paths.update({f"sound/sfx/{local}.sound_info", f"sound/sfx/{local}_clip.wav"})
    required_manifest_paths.update({
        "sound/sfx/sivir_native_silence.sound_info",
        "sound/sfx/sivir_native_silence_clip.wav",
        "BanPickIllust/boomerang_hunter.png",
        "ui/champion_fullbody/boomerang_hunter.png",
        "ui/champion_portrait/boomerang_hunter_compact.png",
        "ui/champion_portrait/boomerang_hunter_scoreboard.png",
        "ui/champion_portrait/boomerang_hunter_grid.png",
    })
    manifest_paths = {row.get("path") for row in load_json("build_manifest.json").get("files", [])}
    missing = sorted(required_manifest_paths - manifest_paths)
    check(not missing, "Sivir runtime resources are missing from build_manifest.json: " + ", ".join(missing))


def validate_sivir_hd_surfaces() -> None:
    runtime_path = MOD_ROOT / "src/lib.rs"
    runtime = runtime_path.read_text(encoding="utf-8") if runtime_path.is_file() else ""
    for marker in (
        "SIVIR_COMPACT_PORTRAIT_TEXTURE",
        "SIVIR_SCOREBOARD_PORTRAIT_TEXTURE",
        "SIVIR_BP_GRID_PORTRAIT_TEXTURE",
        "asset/base/aseprite_resources/champions/boomerang_hunter#sheet",
        "asset/lol_mod/aseprite_resources/champions/sivir#sheet",
    ):
        check(marker in runtime, f"Sivir source-direct portrait route is missing: {marker}")

    qa_path = MOD_ROOT / "qa/sivir_hd_surface_qa.json"
    contact_path = MOD_ROOT / "qa/sivir_portrait_surface_final.png"
    check(qa_path.is_file(), "Sivir HD surface QA record is missing")
    check(contact_path.is_file(), "Sivir HD surface contact is missing")
    if not qa_path.is_file():
        return
    qa = load_json("qa/sivir_hd_surface_qa.json")
    check(qa.get("champion") == "Sivir", "Sivir HD surface QA identity changed")
    check(qa.get("native_id") == "boomerang_hunter", "Sivir HD native-id route changed")
    check(qa.get("skill_logic_changed") is False, "Sivir HD pass must not change skill logic")
    expected_source = "source/processed/sivir_actor_contact_alpha.png"
    check(
        qa.get("accepted_source") == expected_source,
        "Sivir portraits must use the accepted high-resolution ImageGen actor source",
    )
    source_path = MOD_ROOT / expected_source
    check(source_path.is_file(), "Sivir accepted portrait source is missing")
    if source_path.is_file():
        check(
            qa.get("accepted_source_sha256") == sha256(source_path),
            "Sivir accepted portrait source hash changed",
        )

    battle = qa.get("battle_actor", {})
    check(battle.get("uniform_xy_scale") is True, "Sivir actor must use uniform x/y scale")
    check(battle.get("x_only_compression") is False, "Sivir actor must forbid x-only compression")
    check(
        battle.get("first_idle_alpha_bbox") == [17, 9, 47, 45],
        "Sivir primary battle idle bbox changed",
    )
    face = battle.get("face_readability", {})
    check(face.get("opaque_pixels", 0) >= 120, "Sivir battle face area became too small")
    check(face.get("gold_accent_pixels", 0) >= 2, "Sivir circlet/armor face accents disappeared")
    check(
        face.get("luminance_dynamic_range", 0) >= 140,
        "Sivir battle face contrast regressed",
    )

    surfaces = qa.get("surfaces", {})
    expected_surfaces = {
        "side_card": ("BanPickIllust/boomerang_hunter.png", [1420, 860]),
        "encyclopedia": ("ui/champion_fullbody/boomerang_hunter.png", [64, 64]),
        "sidebar": ("ui/champion_portrait/boomerang_hunter_compact.png", [64, 64]),
        "scoreboard": (
            "ui/champion_portrait/boomerang_hunter_scoreboard.png",
            [64, 64],
        ),
        "bp_grid": ("ui/champion_portrait/boomerang_hunter_grid.png", [90, 122]),
    }
    for surface, (relative, dimensions) in expected_surfaces.items():
        record = surfaces.get(surface, {})
        path = MOD_ROOT / relative
        check(record.get("path") == relative, f"Sivir {surface} route changed")
        check(record.get("dimensions") == dimensions, f"Sivir {surface} dimensions changed")
        check(path.is_file(), f"Sivir {surface} image is missing")
        if not path.is_file():
            continue
        image = Image.open(path).convert("RGBA")
        bbox = image.getchannel("A").getbbox()
        check(
            record.get("alpha_bbox") == (list(bbox) if bbox else None),
            f"Sivir {surface} bbox record is stale",
        )
        check(record.get("sha256") == sha256(path), f"Sivir {surface} hash record is stale")
        if surface != "side_card":
            check(record.get("hard_alpha") is True, f"Sivir {surface} must use hard alpha")

    grid_bbox = surfaces.get("bp_grid", {}).get("alpha_bbox")
    check(
        isinstance(grid_bbox, list) and grid_bbox[3] <= 86,
        "Sivir BP-grid alpha must end at or before y=86",
    )
    check(
        surfaces.get("bp_grid", {}).get("name_band_clearance", -1) >= 10,
        "Sivir BP-grid needs ten transparent pixels before name-band y=96",
    )
    check(
        surfaces.get("sidebar", {}).get("sha256")
        != surfaces.get("scoreboard", {}).get("sha256"),
        "Sivir sidebar and scoreboard must remain independent crops",
    )


def validate_kled_replacement_uniqueness() -> None:
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

    files = [filename for champion_id, filename in ids if champion_id == "cavalry_knight"]
    check(
        files == ["cavalry_knight.data_champion"],
        "Kled must replace official 006 exactly once through champion/cavalry_knight.data_champion",
    )
    check(
        all(champion_id != "lol_kled" for champion_id, _ in ids),
        "lol_kled must not be registered as an additive duplicate champion",
    )
    check(
        not (MOD_ROOT / "champion/lol_kled.data_champion").exists(),
        "champion/lol_kled.data_champion must be absent in same-ID replacement mode",
    )


def validate_kled_data_contract(champion: dict[str, Any]) -> None:
    check(champion.get("id") == "cavalry_knight", "Kled must retain native id cavalry_knight")
    check(
        champion.get("sprite") == "asset/lol_mod/aseprite_resources/champions/kled",
        "same-ID Kled must bind the custom Kled actor",
    )
    check(champion.get("anim_prefix") == "", "Kled must preserve native Cavalry animation tags")
    check(champion.get("category") == "Melee", "Kled category must be Melee")
    check(set(champion.get("tags", [])) == {"AD", "Melee", "CC"}, "Kled tags must be AD/Melee/CC")
    check(
        champion.get("skill_icons")
        == [
            "asset/lol_mod/icons/kled_skill",
            "asset/lol_mod/icons/kled_skill2",
            "asset/lol_mod/icons/kled_ult",
        ],
        "Kled active icon order must be Q/E/R",
    )
    check(len(champion.get("skill_icons", [])) == 3, "Kled must expose exactly three active icons")
    for unsupported_slot in ("w", "skill3", "skill4"):
        check(unsupported_slot not in champion, f"Kled must not add unsupported active slot {unsupported_slot}")

    check(
        champion.get("stat")
        == {
            "attack": 90,
            "magic_power": 0,
            "hp": 950,
            "defence": 25,
            "magic_resistance": 18,
            "move_speed": 1200,
            "hp_regen": 3,
            "stack": 0,
            "crit_chance": 0,
        },
        "Kled base stats do not match the approved 006 design",
    )
    check(
        champion.get("growth")
        == {
            "attack": 18,
            "magic_power": 0,
            "hp": 95,
            "defence": 7,
            "magic_resistance": 3,
            "move_speed": 15,
            "hp_regen": 1,
            "stack": 0,
            "crit_chance": 0,
        },
        "Kled growth stats do not match the approved 006 design",
    )

    action_names = {
        "attack": "attack",
        "skill": "skill1",
        "skill2": "skill2",
        "ult": "ult",
    }
    required_fields = {
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
    }
    for slot, expected_action in action_names.items():
        action = champion.get(slot, {})
        check(action.get("action_name") == expected_action, f"Kled {slot} must use native action {expected_action}")
        missing = sorted(required_fields - set(action))
        check(not missing, f"Kled {slot} is missing required data fields: {', '.join(missing)}")
        check(
            action.get("description") == f"#asset/base/text/champion?description.cavalry_knight.{slot}",
            f"Kled {slot} must use the cavalry_knight localization key",
        )
    attack = champion.get("attack", {})
    check((attack.get("range"), attack.get("cooltime")) == (27000, 50), "Kled basic attack must retain the 006 range/cooldown")
    check(
        direct_effects(attack.get("effect", {}), "Attack")
        == [{"type": "Attack", "damage": 0, "attack_ratio": 100}],
        "Kled basic attack must be one plain 100% Attack hit",
    )
    check(not find_effect(champion, "SwitchByBuff"), "Kled Q/E/R contract must not contain SwitchByBuff")
    serialized = json.dumps(champion, ensure_ascii=False)
    check("lol_kled_violent_" not in serialized, "Kled retired Violent Tendencies markers must be absent")
    check("kled_w_" not in serialized, "Kled data must not reference retired W audio or VFX")

    skill = champion.get("skill", {})
    check(
        (
            skill.get("action_name"),
            skill.get("range"),
            skill.get("cooltime"),
            skill.get("duration"),
            skill.get("start_timing"),
            skill.get("casting_type"),
            skill.get("casting_target"),
        )
        == ("skill1", 65000, 360, 36, 8, "Direction", "EnemyChampion"),
        "Kled Q action timing or targeting changed",
    )
    check(not find_effect(skill, "Rush"), "Kled Q must never move the caster through Rush")
    q_projectiles = find_effect(skill, "LinearProjectile", name="lol_kled_q_beartrap_projectile")
    check(len(q_projectiles) == 1, "Kled Q must contain exactly one bear-trap LinearProjectile")
    if q_projectiles:
        projectile = q_projectiles[0]
        check(
            (
                projectile.get("penetrate"),
                projectile.get("speed"),
                projectile.get("range"),
                projectile.get("shape"),
                projectile.get("applied_target"),
            )
            == (False, 6500, 72000, {"Circle": {"radius": 10000}}, "EnemyChampion"),
            "Kled Q projectile speed/range/shape/target/non-penetration contract changed",
        )
        check(projectile.get("end_effects") == [], "Kled Q projectile must not launch a second end projectile")
        applied = projectile.get("applied_effects", [])
        check(len(applied) == 1, "Kled Q projectile must have one first-hit payload")
        hit = applied[0] if applied else {}
        check(hit.get("casting_type") == "Targeting", "Kled Q hit payload must target the first enemy champion")
        hit_effect = hit.get("effect", {})
        check(
            direct_effects(hit_effect, "Attack")
            == [{"type": "Attack", "damage": 30, "attack_ratio": 80}],
            "Kled Q first hit must deal 30 + 80% Attack exactly once",
        )
        check(
            direct_buff_states(hit_effect, "AddBuff")
            == [
                {
                    "name": "lol_kled_q_tethered",
                    "duration": {"Time": {"tick": 45}},
                    "move_speed_mult": -20,
                }
            ],
            "Kled Q tether must slow the target by 20% for 45 ticks",
        )
        check(
            not direct_buff_states(hit_effect, "AddCasterBuff"),
            "Kled Q must not inherit E's self Move Speed buff",
        )
        delayed = direct_effects(hit_effect, "Delayed")
        check(len(delayed) == 1 and delayed[0].get("tick") == 45, "Kled Q pull must resolve after exactly 45 ticks")
        if delayed:
            pull = delayed[0]
            check(
                direct_effects(pull, "Attack")
                == [{"type": "Attack", "damage": 20, "attack_ratio": 40}],
                "Kled Q pull must deal 20 + 40% Attack exactly once",
            )
            check(
                direct_effects(pull, "Grab")
                == [{"type": "Grab", "speed": 2200, "tick": 8}],
                "Kled Q pull must use Grab 2200 for 8 ticks",
            )
            check(
                direct_effects(pull, "Bind")
                == [{"type": "Bind", "duration": 30}],
                "Kled Q pull must bind for 30 ticks",
            )
        check(
            [(effect.get("damage"), effect.get("attack_ratio")) for effect in find_effect(projectile, "Attack")]
            == [(30, 80), (20, 40)],
            "Kled Q projectile must resolve exactly two damage instances",
        )
    check(len(find_effect(skill, "Sfx", name="lol_kled_q_cast")) == 1, "Kled Q cast audio must play once")
    check(not find_effect(skill, "Sfx", name="lol_kled_e_cast"), "Kled Q must not play E cast audio")

    skill2 = champion.get("skill2", {})
    check(
        (
            skill2.get("action_name"),
            skill2.get("cooltime"),
            skill2.get("duration"),
            skill2.get("start_timing"),
            skill2.get("range"),
            skill2.get("casting_type"),
            skill2.get("casting_target"),
        )
        == ("skill2", 480, 13, 11, 55000, "Direction", "EnemyChampion"),
        "Kled E action timing or targeting changed",
    )
    e_rushes = find_effect(skill2, "Rush")
    check(len(e_rushes) == 1, "Kled E must contain exactly one non-penetrating Rush")
    if e_rushes:
        rush = e_rushes[0]
        check(
            (
                rush.get("speed"),
                rush.get("move_speed_ratio"),
                rush.get("range"),
                rush.get("casting_target"),
                rush.get("penetrate"),
            )
            == (3200, 100, 12000, "EnemyChampion", False),
            "Kled E Rush speed/scaling/hit radius/target/non-penetration contract changed",
        )
        applied = rush.get("applied_effects", [])
        check(len(applied) == 1, "Kled E Rush must have one first-hit payload")
        hit = applied[0] if applied else {}
        check(hit.get("casting_type") == "Targeting", "Kled E hit payload must target the first enemy champion")
        payload = hit.get("effect", {})
        check(
            direct_effects(payload, "Attack")
            == [{"type": "Attack", "damage": 30, "attack_ratio": 80}],
            "Kled E first hit must deal 30 + 80% Attack exactly once",
        )
        check(
            direct_buff_states(payload, "AddCasterBuff")
            == [
                {
                    "name": "lol_kled_e_hit_speed",
                    "duration": {"Time": {"tick": 60}},
                    "move_speed_mult": 20,
                }
            ],
            "Kled E hit must grant 20% self Move Speed for 60 ticks",
        )
    check(not find_effect(skill2, "LinearProjectile"), "Kled E must not reuse Q's projectile")
    check(not find_effect(skill2, "Delayed"), "Kled E must not reuse Q's delayed tether")
    check(not find_effect(skill2, "Grab") and not find_effect(skill2, "Bind"), "Kled E must not pull or bind")
    check(len(find_effect(skill2, "Sfx", name="lol_kled_e_cast")) == 1, "Kled E cast audio must play once")
    check(len(find_effect(skill2, "TargetSfx", name="lol_kled_e_hit")) == 1, "Kled E hit audio must play once")
    skill2_serialized = json.dumps(skill2, ensure_ascii=False)
    check("lol_kled_q_" not in skill2_serialized, "Kled E must not contain Q tether state")
    check("lol_kled_violent_" not in skill2_serialized, "Kled E must not contain retired W state")

    projectile_views = {
        view.get("name"): view for view in champion.get("view_projectiles", [])
    }
    check(
        projectile_views.get("lol_kled_q_beartrap_projectile")
        == {
            "type": "Animated",
            "name": "lol_kled_q_beartrap_projectile",
            "anim": "asset/lol_mod/aseprite_resources/effects/kled_q_tether",
            "tag": "projectile",
            "z": 2,
            "repeat": True,
        },
        "Kled Q projectile view must use the independent projectile tag",
    )
    effect_views = {view.get("name"): view for view in champion.get("view_effects", [])}
    for name, asset, tag in (
        ("lol_kled_q_latch_visual", "asset/lol_mod/aseprite_resources/effects/kled_q_tether", "latch"),
        ("lol_kled_q_pull_visual", "asset/lol_mod/aseprite_resources/effects/kled_q_tether", "pull"),
        ("lol_kled_e_dash_visual", "asset/lol_mod/aseprite_resources/effects/kled_e_joust", "dash"),
        ("lol_kled_e_impact_visual", "asset/lol_mod/aseprite_resources/effects/kled_e_joust", "impact"),
    ):
        view = effect_views.get(name, {})
        check(
            (view.get("anim"), view.get("tag"), view.get("is_follow"))
            == (asset, tag, True),
            f"Kled view {name} must use {asset}#{tag} as a following effect",
        )
    buff_views = {view.get("name"): view for view in champion.get("view_buffs", [])}
    tether_view = buff_views.get("lol_kled_q_tethered", {})
    check(
        (
            tether_view.get("anim"),
            tether_view.get("pre_tag"),
            tether_view.get("loop_tag"),
            tether_view.get("remove_tag"),
        )
        == (
            "asset/lol_mod/aseprite_resources/effects/kled_q_tether",
            "tether_pre",
            "tether_loop",
            "tether_remove",
        ),
        "Kled Q tether buff must bind the independent three-phase rope tags",
    )

    ult = champion.get("ult", {})
    check(
        (
            ult.get("action_name"),
            ult.get("range"),
            ult.get("cooltime"),
            ult.get("duration"),
            ult.get("start_timing"),
            ult.get("casting_type"),
            ult.get("casting_target"),
        )
        == ("ult", 120000, 3600, 120, 1, "Position", "EnemyChampion"),
        "Kled R action timing, range, or targeting changed",
    )
    routes = find_effect(ult, "LineRangeProjectile")
    check(len(routes) == 1, "Kled R must create exactly one ally route")
    if routes:
        route = routes[0]
        check(
            (
                route.get("width"),
                route.get("length"),
                route.get("delay"),
                route.get("apply"),
                route.get("applied_target"),
            )
            == (22000, 120000, 0, 240, "AllyNotSelf"),
            "Kled R route width/length/lifetime/ally-only contract changed",
        )
        route_buffs = [effect.get("buff_state", {}) for effect in find_effect(route.get("applied_effects", []), "AddBuff")]
        check(
            route_buffs
            == [
                {
                    "name": "lol_kled_r_trail_speed",
                    "duration": {"Time": {"tick": 30}},
                    "move_speed_mult": 25,
                }
            ],
            "Kled R route must grant other allies 25% speed",
        )
        check(not find_effect(route, "Attack") and not find_effect(route, "Shield"), "Kled R route must not damage or shield allies")
    self_packages = find_effect(ult, "WithSelf")
    check(len(self_packages) == 1, "Kled R must contain one self-only defensive package")
    if self_packages:
        self_package = self_packages[0]
        check(
            len(find_effect(self_package, "Shield", amount=200, attack_ratio=80, ap_ratio=0, tick=180)) == 1,
            "Kled R self shield must be 200 + 80% Attack for 180 ticks",
        )
        self_buffs = {
            state.get("name"): state
            for state in direct_buff_states(self_package, "AddCasterBuff")
        }
        check(
            self_buffs
            == {
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
            },
            "Kled R self package must grant only +50% speed and 90-tick CC immunity",
        )
        check("lol_kled_r_trail_speed" not in self_buffs, "Kled must not receive the ally route buff")
    route_self_buffs = [
        effect
        for effect in find_effect(ult, "AddCasterBuff")
        if effect.get("buff_state", {}).get("name") == "lol_kled_r_trail_speed"
    ]
    check(not route_self_buffs, "Kled R route speed must never be added to the caster")
    ult_rushes = find_effect(ult, "Rush")
    check(len(ult_rushes) == 1, "Kled R must contain exactly one first-hit Rush")
    if ult_rushes:
        rush = ult_rushes[0]
        check(
            (
                rush.get("speed"),
                rush.get("move_speed_ratio"),
                rush.get("range"),
                rush.get("casting_target"),
                rush.get("penetrate"),
            )
            == (4200, 150, 14000, "EnemyChampion", False),
            "Kled R Rush speed/scaling/hit radius/non-penetration contract changed",
        )
        applied = rush.get("applied_effects", [])
        check(len(applied) == 1, "Kled R Rush must resolve one first-hit payload")
        impact = applied[0].get("effect", {}) if applied else {}
        check(
            direct_effects(impact, "Attack")
            == [
                {
                    "type": "Attack",
                    "damage": 80,
                    "attack_ratio": 100,
                    "target_hp_ratio": 2,
                }
            ],
            "Kled R first hit must deal 80 + 100% Attack + 2% max-health exactly once",
        )
        check(
            direct_effects(impact, "Knockback")
            == [{"type": "Knockback", "speed": 2400, "tick": 8}],
            "Kled R impact Knockback contract changed",
        )
        check(
            direct_effects(impact, "Airborne")
            == [{"type": "Airborne", "duration": 18}],
            "Kled R impact Airborne contract changed",
        )
        check(len(find_effect(rush, "Attack")) == 1, "Kled R Rush must damage only the first enemy once")


def validate_kled_native_animation_and_resources(champion: dict[str, Any]) -> None:
    sheet_path = MOD_ROOT / "aseprite_resources/champions/kled#sheet.png"
    anim_path = MOD_ROOT / "aseprite_resources/champions/kled#anim.fanim"
    check(sheet_path.is_file(), "Kled actor sheet is missing")
    check(anim_path.is_file(), "Kled actor animation is missing")
    if not sheet_path.is_file() or not anim_path.is_file():
        return

    sheet = Image.open(sheet_path).convert("RGBA")
    anim = load_json("aseprite_resources/champions/kled#anim.fanim").get("anims", {})
    check(
        list(anim) == list(KLED_NATIVE_ANIMATION),
        "Kled must preserve the exact ordered 24-tag native Cavalry animation contract",
    )
    forbidden_tags = {"attack_w1", "attack_w2", "attack_w3", "attack_w4", "skill", "run_fast"}
    check(not forbidden_tags.intersection(anim), "Kled must not add design-only animation tags outside the native 006 contract")

    run_hashes: list[str] = []
    first_idle_bbox: tuple[int, int, int, int] | None = None
    for tag, expected_durations in KLED_NATIVE_ANIMATION.items():
        frames = anim.get(tag, {}).get("frames", [])
        check(len(frames) == len(expected_durations), f"Kled native tag {tag} frame count changed")
        for index, (frame, expected_duration) in enumerate(zip(frames, expected_durations)):
            check(
                math.isclose(
                    float(frame.get("duration", -1)),
                    expected_duration,
                    rel_tol=0.0,
                    abs_tol=1e-9,
                ),
                f"Kled native tag {tag} frame {index} duration changed",
            )
            data = frame.get("data", {})
            x, y, width, height = (
                int(data.get("x", -1)),
                int(data.get("y", -1)),
                int(data.get("w", 0)),
                int(data.get("h", 0)),
            )
            in_bounds = (
                x >= 0
                and y >= 0
                and width > 0
                and height > 0
                and x + width <= sheet.width
                and y + height <= sheet.height
            )
            check(in_bounds, f"Kled native tag {tag} frame {index} is out of bounds")
            if not in_bounds:
                continue
            image = sheet.crop((x, y, x + width, y + height))
            bbox = image.getchannel("A").getbbox()
            if tag in {"dead", "fire_dead"} and index == len(frames) - 1:
                check(bbox is None, f"Kled {tag} final frame must remain transparent")
                continue
            if tag in {"idle", "run", "attack", "skill1", "skill2", "ult", "hit"}:
                check(bbox is not None, f"Kled core {tag} frame {index} is empty")
            if tag == "idle" and index == 0:
                first_idle_bbox = bbox
            if tag == "run" and bbox is not None:
                run_hashes.append(hashlib.sha256(image.tobytes()).hexdigest())

    check(first_idle_bbox is not None, "Kled first idle frame must show the mounted full body")
    if first_idle_bbox is not None:
        visible_width = first_idle_bbox[2] - first_idle_bbox[0]
        visible_height = first_idle_bbox[3] - first_idle_bbox[1]
        check(visible_width <= 58, "Kled first idle frame exceeds the 58px battle-safe width")
        check(36 <= visible_height <= 44, "Kled first idle frame must remain in the 36-44px mounted scale class")
        check(first_idle_bbox[3] <= 46, "Kled first idle frame is below the accepted y=45/46 foot baseline")
    check(len(set(run_hashes)) >= 6, "Kled must keep at least six distinct native-timed run phases")

    required_manifest_paths = {
        "champion/cavalry_knight.data_champion",
        "aseprite_resources/champions/kled#sheet.png",
        "aseprite_resources/champions/kled#anim.fanim",
        "style/champion_view.champion_view",
        "text/champion.i18n",
        "BanPickIllust/cavalry_knight.png",
        "ui/champion_fullbody/cavalry_knight.png",
        "ui/champion_portrait/cavalry_knight_compact.png",
        "ui/champion_portrait/cavalry_knight_grid.png",
        "sound/sfx/kled_native_silence.sound_info",
        "sound/sfx/kled_native_silence_clip.wav",
    }
    icon_paths: list[Path] = []
    for asset in champion.get("skill_icons", []):
        relative = asset.removeprefix("asset/lol_mod/") + ".png"
        required_manifest_paths.add(relative)
        path = MOD_ROOT / relative
        icon_paths.append(path)
        check(path.is_file(), f"missing Kled icon: {relative}")
        if path.is_file():
            check(Image.open(path).size == (64, 64), f"{relative} must be 64x64")
    if all(path.is_file() for path in icon_paths) and len(icon_paths) == 3:
        check(len({sha256(path) for path in icon_paths}) == 3, "Kled Q/E/R icons must be distinct")

    for view_key in ("view_projectiles", "view_effects", "view_buffs"):
        for view in champion.get(view_key, []):
            asset = view.get("anim")
            check(isinstance(asset, str) and asset.startswith("asset/lol_mod/"), f"Kled {view_key} has an invalid anim binding")
            if not isinstance(asset, str) or not asset.startswith("asset/lol_mod/"):
                continue
            relative = asset.removeprefix("asset/lol_mod/")
            for suffix in ("#sheet.png", "#anim.fanim"):
                runtime_path = f"{relative}{suffix}"
                required_manifest_paths.add(runtime_path)
                check((MOD_ROOT / runtime_path).is_file(), f"missing Kled view resource: {runtime_path}")

    manifest_paths = {row.get("path") for row in load_json("build_manifest.json").get("files", [])}
    missing = sorted(required_manifest_paths - manifest_paths)
    check(not missing, "Kled runtime resources are missing from build_manifest.json: " + ", ".join(missing))


def validate_kled_localization_style_and_surfaces() -> None:
    text = load_json("text/champion.i18n")
    expected_names = {
        "en": "Kled",
        "zh-hans": "克烈",
        "zh-hant": "克烈",
        "ja": "クレッド",
        "ko": "클레드",
    }
    for locale, expected_name in expected_names.items():
        descriptions = text.get(locale, {}).get("description", {})
        check("lol_kled" not in descriptions, f"{locale} must not register an additive lol_kled entry")
        description = descriptions.get("cavalry_knight", {})
        check(description.get("name") == expected_name, f"{locale} Kled encyclopedia name must be {expected_name}")
        for key, letter in (("skill", "Q"), ("skill2", "E"), ("ult", "R")):
            check(str(description.get(key, "")).startswith(letter), f"{locale} Kled {key} must be labeled {letter}")
        combined = " ".join(str(description.get(key, "")) for key in ("attack", "skill", "skill2"))
        check("Q+E" not in combined and "Q + E" not in combined, f"{locale} Kled text must not merge Q and E")
        check("W mapping" not in combined and "承载W" not in combined, f"{locale} Kled text must not expose the retired W mapping")

    style = load_json("style/champion_view.champion_view").get("entries", {}).get("cavalry_knight", {})
    check(style.get("center") == {"x": 0, "y": -12}, "Kled center camera must start at (0,-12)")
    check(
        style.get("face") == {"x": 1, "y": -36},
        "Kled compact rows must keep the Kled-only fallback camera at (1,-36)",
    )
    check(style.get("face") != style.get("center"), "Kled compact face and full-body center cameras must remain independent")

    actor_path = MOD_ROOT / "aseprite_resources/champions/kled#sheet.png"
    anim_path = MOD_ROOT / "aseprite_resources/champions/kled#anim.fanim"
    if actor_path.is_file() and anim_path.is_file():
        actor = Image.open(actor_path).convert("RGBA")
        idle_frames = (
            load_json("aseprite_resources/champions/kled#anim.fanim")
            .get("anims", {})
            .get("idle", {})
            .get("frames", [])
        )
        check(bool(idle_frames), "Kled compact portrait source must expose an idle frame")
        if idle_frames:
            data = idle_frames[0].get("data", {})
            x, y, width, height = (int(data.get(key, 0)) for key in ("x", "y", "w", "h"))
            in_bounds = (
                x >= 0
                and y >= 0
                and width > 0
                and height > 0
                and x + width <= actor.width
                and y + height <= actor.height
            )
            check(in_bounds, "Kled compact portrait idle frame is outside the actor sheet")
            if in_bounds:
                bbox = actor.crop((x, y, x + width, y + height)).getchannel("A").getbbox()
                check(bbox is not None, "Kled compact portrait idle frame is empty")
                if bbox is not None:
                    visible_width = bbox[2] - bbox[0]
                    visible_height = bbox[3] - bbox[1]
                    check(
                        36 <= visible_width <= 44,
                        "Kled compact portrait mounted width left the accepted 36-44px class",
                    )
                    check(
                        36 <= visible_height <= 44,
                        "Kled compact portrait mounted height left the accepted 36-44px class",
                    )
                    check(
                        bbox[1] <= 6 and bbox[3] <= 46,
                        "Kled compact portrait body no longer fits the center-camera vertical window",
                    )

    builder_path = MOD_ROOT / "tools/build_lol_mod.py"
    builder = builder_path.read_text(encoding="utf-8") if builder_path.is_file() else ""
    check(
        '"cavalry_knight": ACTOR_DIR / "kled#sheet.png"' in builder,
        "Kled must be registered in CHAMPION_FULLBODY_SHEETS",
    )

    slot_path = MOD_ROOT / "ui/layout/champion_info_component/champion_slot.ui"
    slot = slot_path.read_text(encoding="utf-8") if slot_path.is_file() else ""
    check("#lol_fullbody_kled:image" in slot, "Kled encyclopedia full-body node is missing")
    check(
        'source: "asset/lol_mod/ui/champion_fullbody/cavalry_knight";' in slot,
        "Kled encyclopedia node must use the stable cavalry_knight portrait asset",
    )

    rust_path = MOD_ROOT / "src/lib.rs"
    rust = rust_path.read_text(encoding="utf-8") if rust_path.is_file() else ""
    rust_compact = " ".join(rust.split())
    check(
        '"asset/lol_mod/BanPickIllust/cavalry_knight"' in rust,
        "Kled BP splash is missing from the runtime splash list",
    )
    check(
        '("cavalry_knight", "lol_fullbody_kled")' in rust_compact,
        "Kled is missing from runtime encyclopedia portrait synchronization",
    )
    check(
        '"kled" | "cavalry_knight" => Some("cavalry_knight")' in rust,
        "Kled actor/native-id BP alias is missing",
    )
    for required_source in (
        "rewrite_kled_portrait_render_commands(state);",
        "KLED_COMPACT_PORTRAIT_TEXTURE",
        "KLED_BP_GRID_PORTRAIT_TEXTURE",
        '"asset/base/aseprite_resources/champions/cavalry_knight#sheet"',
        '"asset/lol_mod/aseprite_resources/champions/kled#sheet"',
        "let is_compact_square",
        "let is_bp_grid",
        "texture_rect.w = 1.0",
        "*sample_nearest = true",
    ):
        check(required_source in rust, f"Kled portrait runtime route is missing: {required_source}")

    fullbody_path = MOD_ROOT / "ui/champion_fullbody/cavalry_knight.png"
    check(fullbody_path.is_file(), "Kled encyclopedia full-body portrait is missing")
    if fullbody_path.is_file():
        fullbody = Image.open(fullbody_path).convert("RGBA")
        check(fullbody.size == (64, 64), f"Kled full-body portrait must be 64x64, got {fullbody.size}")
        check(fullbody.getchannel("A").getbbox() is not None, "Kled full-body portrait is empty")

    compact_path = MOD_ROOT / "ui/champion_portrait/cavalry_knight_compact.png"
    grid_path = MOD_ROOT / "ui/champion_portrait/cavalry_knight_grid.png"
    check(compact_path.is_file(), "Kled rider-focused compact portrait is missing")
    check(grid_path.is_file(), "Kled source-direct BP-grid portrait is missing")
    if compact_path.is_file():
        compact = Image.open(compact_path).convert("RGBA")
        check(compact.size == (64, 64), f"Kled compact portrait must be 64x64, got {compact.size}")
        compact_bbox = compact.getchannel("A").getbbox()
        check(compact_bbox is not None, "Kled compact portrait is empty")
        if compact_bbox is not None:
            check(compact_bbox[2] - compact_bbox[0] <= 50, f"Kled compact portrait is too wide: {compact_bbox}")
            check(compact_bbox[3] - compact_bbox[1] <= 50, f"Kled compact portrait is too tall: {compact_bbox}")
            check(
                min(
                    compact_bbox[0],
                    compact_bbox[1],
                    64 - compact_bbox[2],
                    64 - compact_bbox[3],
                ) >= 6,
                f"Kled compact portrait lacks 6px safety margins: {compact_bbox}",
            )
        check(compact.getchannel("A").getextrema() == (0, 255), "Kled compact portrait must use hard alpha")
    if grid_path.is_file():
        grid = Image.open(grid_path).convert("RGBA")
        check(grid.size == (90, 122), f"Kled BP-grid portrait must be 90x122, got {grid.size}")
        grid_bbox = grid.getchannel("A").getbbox()
        check(grid_bbox is not None, "Kled BP-grid portrait is empty")
        if grid_bbox is not None:
            check(grid_bbox[1] <= 20, f"Kled BP-grid portrait is too low: {grid_bbox}")
            check(grid_bbox[3] <= 86, f"Kled BP-grid portrait lacks the 10px hero-name-band gap: {grid_bbox}")
        check(grid.getchannel("A").getextrema() == (0, 255), "Kled BP-grid portrait must use hard alpha")
    if compact_path.is_file() and fullbody_path.is_file():
        check(
            sha256(compact_path) != sha256(fullbody_path),
            "Kled compact rider portrait must stay distinct from the full-mount encyclopedia art",
        )

    source_splash_path = MOD_ROOT / "source/imagegen/bp_splash/cavalry_knight.png"
    runtime_splash_path = MOD_ROOT / "BanPickIllust/cavalry_knight.png"
    check(source_splash_path.is_file(), "Kled generated BP source illustration is missing")
    if source_splash_path.is_file():
        with Image.open(source_splash_path) as source_splash:
            ratio_error = abs(source_splash.width / source_splash.height - 284 / 172)
            check(ratio_error <= 0.02, "Kled generated BP source must use the 284:172 card composition")
    check(runtime_splash_path.is_file(), "Kled runtime BP illustration is missing")
    if runtime_splash_path.is_file():
        with Image.open(runtime_splash_path) as runtime_splash:
            check(runtime_splash.size == (1420, 860), f"Kled runtime BP illustration must be 1420x860, got {runtime_splash.size}")

    required_qa = {
        "qa/kled_actor_contact_final.png",
        "qa/kled_portrait_surface_final.png",
        "qa/kled_skill_icons_final.png",
        "qa/kled_vfx_contact_final.png",
        "qa/kled_imagegen_sources.json",
        "qa/kled_official_audio_sources.json",
        "qa/kled_skill_contract_qa.md",
        "qa/kled_visual_qa.md",
        "qa/kled_live_qa.md",
        "qa/kled_compact_portrait_qa.md",
        "qa/kled_q_tether_qa.md",
        "qa/kled_e_joust_qa.md",
        "qa/kled_r_trail_qa.md",
    }
    missing_qa = sorted(relative for relative in required_qa if not (MOD_ROOT / relative).is_file())
    check(not missing_qa, "Kled QA evidence is incomplete: " + ", ".join(missing_qa))


def validate_kled_audio(champion: dict[str, Any], override: dict[str, Any]) -> None:
    required_manifest_paths = {
        "sound/sfx/kled_native_silence.sound_info",
        "sound/sfx/kled_native_silence_clip.wav",
    }
    events = {
        effect.get("name")
        for effect in walk_effects(champion)
        if effect.get("type") in {"Sfx", "TargetSfx"}
        and isinstance(effect.get("name"), str)
    }
    check(
        {"lol_kled_q_cast", "lol_kled_e_cast", "lol_kled_r_cast"}.issubset(events),
        "Kled Q/E/R cast audio events are incomplete",
    )
    check(len(events) >= 4, "Kled must declare at least four custom combat audio events")
    check(all(event.startswith("lol_kled_") for event in events), "Kled data must not call native Cavalry audio events")

    for event in sorted(events):
        source_key = f"asset/base/sound/sfx/{event}"
        mapping = override.get(source_key, {})
        check(mapping.get("type") == "override", f"missing Kled sound override: {source_key}")
        remapping = mapping.get("remapping", "")
        check(remapping.startswith("asset/lol_mod/sound/sfx/kled_"), f"Kled event {event} has the wrong local mapping")
        if not remapping.startswith("asset/lol_mod/sound/sfx/"):
            continue
        local = remapping.removeprefix("asset/lol_mod/sound/sfx/")
        info_path = MOD_ROOT / f"sound/sfx/{local}.sound_info"
        required_manifest_paths.add(f"sound/sfx/{local}.sound_info")
        check(info_path.is_file(), f"missing Kled sound_info: {info_path.name}")
        if not info_path.is_file():
            continue
        sound_info = load_json(f"sound/sfx/{local}.sound_info")
        plays = sound_info.get("plays", [])
        check(bool(plays), f"{local}.sound_info must contain at least one play")
        for play in plays:
            check(float(play.get("volume", 0.0)) >= 0.85, f"{local} volume must be at least 0.85")
            clip = play.get("clip")
            check(isinstance(clip, str) and bool(clip), f"{local} has an invalid clip")
            if not isinstance(clip, str) or not clip:
                continue
            check(
                override.get(f"asset/base/sound/sfx/{clip}")
                == {
                    "remapping": f"asset/lol_mod/sound/sfx/{clip}",
                    "type": "override",
                },
                f"Kled clip override is missing: {clip}",
            )
            wav_path = MOD_ROOT / f"sound/sfx/{clip}.wav"
            required_manifest_paths.add(f"sound/sfx/{clip}.wav")
            check(wav_path.is_file(), f"missing Kled WAV: {clip}.wav")
            if wav_path.is_file():
                try:
                    with wave.open(str(wav_path), "rb") as decoded:
                        check(
                            (decoded.getnchannels(), decoded.getsampwidth(), decoded.getframerate())
                            == (1, 2, 44100),
                            f"{clip}.wav must be mono 16-bit 44.1kHz",
                        )
                except wave.Error as error:
                    check(False, f"{clip}.wav cannot be decoded: {error}")

    for event in KLED_NATIVE_AUDIO_EVENTS:
        check(
            override.get(f"asset/base/sound/sfx/{event}")
            == {
                "remapping": "asset/lol_mod/sound/sfx/kled_native_silence",
                "type": "override",
            },
            f"native Cavalry event must be isolated: {event}",
        )
    for clip in KLED_NATIVE_AUDIO_CLIPS:
        check(
            override.get(f"asset/base/sound/sfx/{clip}")
            == {
                "remapping": "asset/lol_mod/sound/sfx/kled_native_silence_clip",
                "type": "override",
            },
            f"native Cavalry clip must be isolated: {clip}",
        )
    silence_info_path = MOD_ROOT / "sound/sfx/kled_native_silence.sound_info"
    silence_clip_path = MOD_ROOT / "sound/sfx/kled_native_silence_clip.wav"
    check(silence_info_path.is_file(), "Kled native silence sound_info is missing")
    if silence_info_path.is_file():
        check(
            load_json("sound/sfx/kled_native_silence.sound_info")
            == {"plays": [{"delay": 0.0, "clip": "kled_native_silence_clip", "volume": 1.0}]},
            "Kled native silence sound_info changed",
        )
    check(silence_clip_path.is_file(), "Kled native silence clip is missing")
    if silence_clip_path.is_file():
        check(silence_clip_path.stat().st_size == 4454, "Kled native silence clip size changed")
        check(sha256(silence_clip_path) == KLED_NATIVE_SILENCE_SHA256, "Kled native silence clip hash changed")
    manifest_paths = {row.get("path") for row in load_json("build_manifest.json").get("files", [])}
    missing_manifest_paths = sorted(required_manifest_paths - manifest_paths)
    check(
        not missing_manifest_paths,
        "Kled audio resources are missing from build_manifest.json: " + ", ".join(missing_manifest_paths),
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
        check(idle_height == 36, "Lucian idle must use the reference-aligned 36px visible height")
        check(20 <= idle_width <= 24, "Lucian idle must retain the compact full-body gunslinger width")
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
        bboxes[19][2] - bboxes[19][0] <= 32,
        "Lucian hit/fall frame must not widen back into the rejected two-pistol pose",
    )
    check(
        bboxes[20][2] - bboxes[20][0] <= 44,
        "Lucian defeated frame must keep a compact one-pistol silhouette",
    )

    run_frames = [actor.crop((index * 64, 0, (index + 1) * 64, 64)) for index in range(2, 11)]
    run_bboxes = [frame.getchannel("A").getbbox() for frame in run_frames]
    run_areas: list[int] = []
    for index, bbox in enumerate(run_bboxes, start=1):
        if bbox:
            width = bbox[2] - bbox[0]
            height = bbox[3] - bbox[1]
            check(27 <= width <= 31, f"Lucian run {index} must stay inside the 27-31px terrain-safe footprint")
            check(height == 36, f"Lucian run {index} must keep the state-stable 36px pose height")
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


def validate_compact_view_and_e_layout() -> None:
    style = load_json("style/champion_view.champion_view")
    shen = style.get("entries", {}).get("lol_shen", {})
    check(shen.get("face") == {"x": 6, "y": -34}, "compact portrait must center Shen's head at face x=6/y=-34")
    check(shen.get("center") == {"x": 0, "y": -12}, "battle/card center offset must remain x=0/y=-12")

    e_path = MOD_ROOT / "aseprite_resources/effects/shen_e#sheet.png"
    check(e_path.is_file(), "Shen E sheet is missing")
    if not e_path.is_file():
        return
    e_sheet = Image.open(e_path).convert("RGBA")
    check(e_sheet.size == (576, 64), f"E sheet must be 576x64, got {e_sheet.size}")
    for index in range(6):
        frame = e_sheet.crop((index * 96, 0, (index + 1) * 96, 64))
        bbox = frame.getchannel("A").getbbox()
        check(bbox is not None, f"E frame {index} is empty")
        if not bbox:
            continue
        width = bbox[2] - bbox[0]
        height = bbox[3] - bbox[1]
        check(12 <= width <= 88, f"E frame {index} left the 12-88px readable width")
        check(8 <= height <= 40, f"E frame {index} left the 8-40px readable height")
        check(bbox[0] >= 2 and bbox[2] <= 94 and bbox[1] >= 2 and bbox[3] <= 62, f"E frame {index} touches an atlas edge")
        if index < 3:
            check(width >= height * 2, f"E dash frame {index} is not a horizontal wake")
        else:
            check(width <= height * 2, f"E impact frame {index} does not read as a compact collision")
    e_anim = load_json("aseprite_resources/effects/shen_e#anim.fanim")
    check(
        set(e_anim.get("anims", {}))
        == {
            "dash", "impact", "trail_pre", "trail_loop", "trail_remove",
            "taunt_pre", "taunt_loop", "taunt_remove",
        },
        "E animation must expose distinct dash, impact, trail and sustained-taunt tags",
    )
    check(len(e_anim.get("anims", {}).get("dash", {}).get("frames", [])) == 3, "E dash tag must have three frames")
    check(len(e_anim.get("anims", {}).get("impact", {}).get("frames", [])) == 3, "E impact tag must have three frames")

    lucian = style.get("entries", {}).get("archer", {})
    check(lucian.get("face") == {"x": 0, "y": -34}, "Lucian compact portrait offset must be x=0/y=-34")
    check(lucian.get("center") == {"x": 0, "y": -12}, "Lucian battle/card center offset must be x=0/y=-12")

    portrait_specs = {
        "lol_shen": {
            "fullbody": ("ui/champion_fullbody/lol_shen.png", (64, 64)),
            "compact": ("ui/champion_portrait/lol_shen_compact.png", (64, 64)),
            "scoreboard": ("ui/champion_portrait/lol_shen_scoreboard.png", (64, 64)),
            "grid": ("ui/champion_portrait/lol_shen_grid.png", (90, 122)),
        },
        "archer": {
            "fullbody": ("ui/champion_fullbody/archer.png", (64, 64)),
            "compact": ("ui/champion_portrait/archer_compact.png", (64, 64)),
            "scoreboard": ("ui/champion_portrait/archer_scoreboard.png", (64, 64)),
            "grid": ("ui/champion_portrait/archer_grid.png", (90, 122)),
        },
    }
    for champion_id, surfaces in portrait_specs.items():
        hashes: set[str] = set()
        for surface, (relative, expected_size) in surfaces.items():
            path = MOD_ROOT / relative
            check(path.is_file(), f"{champion_id} missing source-direct {surface} portrait")
            if not path.is_file():
                continue
            image = Image.open(path).convert("RGBA")
            bbox = image.getchannel("A").getbbox()
            check(image.size == expected_size, f"{champion_id} {surface} size mismatch: {image.size}")
            check(bbox is not None, f"{champion_id} {surface} portrait is empty")
            if bbox:
                check(
                    bbox[0] >= 6 and bbox[1] >= 2 and image.width - bbox[2] >= 6,
                    f"{champion_id} {surface} portrait lacks transparent side/top safety",
                )
                if surface in {"compact", "scoreboard"}:
                    check(
                        bbox[2] - bbox[0] <= 50 and bbox[3] - bbox[1] <= 50,
                        f"{champion_id} {surface} portrait exceeds the 50px compact-safe subject",
                    )
                if surface == "grid":
                    check(bbox[3] <= 86, f"{champion_id} grid art touches the BP name band")
            hashes.add(hashlib.sha256(image.tobytes()).hexdigest())
        check(
            len(hashes) == len(surfaces),
            f"{champion_id} UI surfaces must be independently cropped, not duplicate files",
        )

    source = (MOD_ROOT / "src/lib.rs").read_text(encoding="utf-8")
    check(
        "rewrite_shen_lucian_portrait_render_commands(state);" in source,
        "Shen/Lucian source-direct portraits are not wired into post_render",
    )
    for marker in (
        "SHEN_COMPACT_PORTRAIT_TEXTURE",
        "SHEN_SCOREBOARD_PORTRAIT_TEXTURE",
        "SHEN_BP_GRID_PORTRAIT_TEXTURE",
        "LUCIAN_COMPACT_PORTRAIT_TEXTURE",
        "LUCIAN_SCOREBOARD_PORTRAIT_TEXTURE",
        "LUCIAN_BP_GRID_PORTRAIT_TEXTURE",
        "let is_scoreboard_square = (14.0..=38.0)",
        "let is_compact_square = (39.0..=52.0)",
        "let is_bp_grid = (124.0..=132.0)",
    ):
        check(marker in source, f"missing Shen/Lucian portrait routing proof: {marker}")


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
    shen_en = text.get("en", {}).get("description", {}).get("lol_shen", {})
    shen_zh_hans = text.get("zh-hans", {}).get("description", {}).get("lol_shen", {})
    shen_zh_hant = text.get("zh-hant", {}).get("description", {}).get("lol_shen", {})
    check("Twilight Assault" in shen_en.get("skill", ""), "English Q text must name Twilight Assault")
    check("next 3 basic attacks" in shen_en.get("skill", ""), "English Q text must disclose three empowered attacks")
    check("only the empowered attacks still unused" in shen_en.get("skill", ""), "English Q text must disclose remaining-charge-only upgrade")
    check("does not retain an independently positioned blade" in shen_en.get("skill", ""), "English Q text must disclose the persistent-blade limitation")
    check("Shadow Dash" in shen_en.get("skill2", ""), "English second slot must be Shadow Dash")
    check("taunted for 1.5 seconds" in shen_en.get("skill2", ""), "English E text must disclose the 1.5-second taunt")
    check("奥义！暮临" in shen_zh_hans.get("skill", ""), "zh-hans Q must use the localized Twilight Assault name")
    check("仅将尚未使用的强化升级" in shen_zh_hans.get("skill", ""), "zh-hans Q must disclose remaining-charge-only upgrade")
    check("奥义！影缚" in shen_zh_hans.get("skill2", ""), "zh-hans second slot must be Shadow Dash")
    check("奧義！暮臨" in shen_zh_hant.get("skill", ""), "zh-hant Q must use the localized Twilight Assault name")
    check("奧義！影縛" in shen_zh_hant.get("skill2", ""), "zh-hant second slot must be Shadow Dash")
    check("lowest-health" in shen_en.get("ult", ""), "English R text must disclose the target-selection limitation")
    check("taunt" not in shen_en.get("ult", "").lower(), "English R text must not retain the old arrival taunt")
    lucian_en = text.get("en", {}).get("description", {}).get("lol_lucian", {})
    check("15 shots" in lucian_en.get("ult", ""), "English Lucian R text must disclose 15 shots")
    check("45%" in lucian_en.get("attack", ""), "English Lucian passive text must disclose the 45% second shot")


def validate_audio(champion: dict[str, Any], override: dict[str, Any]) -> None:
    sfx_names = sorted({effect.get("name") for effect in walk_effects(champion) if effect.get("type") in {"Sfx", "TargetSfx"}})
    check(len(sfx_names) == 5, f"expected 5 active Shen sound events after W retirement, got {len(sfx_names)}")
    check("lol_shen_w_cast" not in sfx_names and "lol_shen_w_block" not in sfx_names, "retired W audio events remain active")
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


def validate_briar_localization_and_style() -> None:
    style = load_json("style/champion_view.champion_view")
    briar_view = style.get("entries", {}).get("berserker", {})
    check(
        briar_view.get("face") == {"x": 5, "y": -32},
        "Briar compact portrait offset must remain face x=5/y=-32",
    )
    check(
        briar_view.get("center") == {"x": 0, "y": -12},
        "Briar card/battle center offset must remain center x=0/y=-12",
    )

    text = load_json("text/champion.i18n")
    expected_names = {
        "en": "Briar",
        "zh-hans": "贝蕾亚",
        "zh-hant": "貝蕾亞",
        "ja": "ブライアー",
        "ko": "브라이어",
    }
    for locale, expected_name in expected_names.items():
        descriptions = text.get(locale, {}).get("description", {})
        description = descriptions.get("berserker", {})
        check(
            set(description) == {"name", "attack", "skill", "skill2", "ult"},
            f"{locale} berserker/Briar localization is incomplete",
        )
        check(description.get("name") == expected_name, f"{locale} Briar encyclopedia name must be {expected_name}")
        check(description.get("skill", "").startswith("Q"), f"{locale} Briar first active must be labeled Q")
        check(description.get("skill2", "").startswith("E"), f"{locale} Briar second active must be labeled E")
        check(description.get("ult", "").startswith("R"), f"{locale} Briar ultimate must be labeled R")
        check("lol_briar" not in descriptions, f"{locale} must not register an additive lol_briar encyclopedia entry")

    english = text.get("en", {}).get("description", {}).get("berserker", {})
    check("Crimson Curse" in english.get("attack", ""), "English Briar passive text must name Crimson Curse")
    check("2% target maximum-health" in english.get("attack", ""), "English Briar Snack text must disclose its max-HP damage")
    check("Blood Frenzy" in english.get("skill", ""), "English Briar Q text must name Blood Frenzy")
    check("one empowered bite" in english.get("skill", ""), "English Briar Q text must disclose the one-use bite")
    check("Chilling Scream" in english.get("skill2", ""), "English Briar E text must name Chilling Scream")
    check("fixed 0.5-second charge" in english.get("skill2", ""), "English Briar E text must disclose the fixed charge")
    check("Certain Death" in english.get("ult", ""), "English Briar R text must name Certain Death")
    check("targeted chase" in english.get("ult", ""), "English Briar R text must disclose the data-only targeted chase")


def validate_sivir_localization_and_style() -> None:
    style = load_json("style/champion_view.champion_view")
    view = style.get("entries", {}).get("boomerang_hunter", {})
    check(view.get("face") == {"x": 5, "y": -34}, "Sivir compact portrait offset must remain face x=5/y=-34")
    check(view.get("center") == {"x": 0, "y": -12}, "Sivir center offset must remain x=0/y=-12")

    text = load_json("text/champion.i18n")
    expected_names = {
        "en": "Sivir",
        "zh-hans": "希维尔",
        "zh-hant": "希維爾",
        "ja": "シヴィア",
        "ko": "시비르",
    }
    for locale, expected_name in expected_names.items():
        descriptions = text.get(locale, {}).get("description", {})
        description = descriptions.get("boomerang_hunter", {})
        check(set(description) == {"name", "attack", "skill", "skill2", "ult"}, f"{locale} Sivir localization is incomplete")
        check(description.get("name") == expected_name, f"{locale} Sivir encyclopedia name must be {expected_name}")
        check(description.get("skill", "").startswith("Q"), f"{locale} Sivir first active must be labeled Q")
        check(description.get("skill2", "").startswith("E"), f"{locale} Sivir second active must be labeled E")
        check(description.get("ult", "").startswith("R"), f"{locale} Sivir ultimate must be labeled R")
        check("lol_sivir" not in descriptions, f"{locale} must not register an additive lol_sivir entry")
    english = text.get("en", {}).get("description", {}).get("boomerang_hunter", {})
    check("outbound and returning" in english.get("skill", ""), "English Sivir Q must disclose both passes")
    check("timed damage guard" in english.get("skill2", ""), "English Sivir E must disclose its data-only approximation")
    check("not consumed by the first spell" in english.get("skill2", ""), "English Sivir E must not claim exact one-spell consumption")
    check("deals no damage" in english.get("ult", ""), "English Sivir R must disclose that it deals no damage")


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


def validate_briar_audio(champion: dict[str, Any], override: dict[str, Any]) -> None:
    actual_events = {
        effect.get("name")
        for effect in walk_effects(champion)
        if effect.get("type") in {"Sfx", "TargetSfx"}
    }
    check(
        actual_events == set(BRIAR_AUDIO_EVENTS),
        f"Briar must wire exactly nine official attack/Q/E/R sound events, got {sorted(actual_events)}",
    )

    audio_manifest = load_json("qa/briar_official_audio_sources.json")
    check(audio_manifest.get("schema_version") == 1, "Briar official audio manifest schema must be 1")
    check(audio_manifest.get("champion") == "Briar", "Briar official audio manifest champion is incorrect")
    outputs = audio_manifest.get("outputs", [])
    check(len(outputs) == 9, "Briar official audio QA manifest must cover 9 clips")
    outputs_by_key = {output.get("event_key"): output for output in outputs}
    expected_output_keys = {name.removeprefix("lol_") for name in BRIAR_AUDIO_EVENTS}
    check(set(outputs_by_key) == expected_output_keys, "Briar official audio manifest event set is incomplete")
    check(len(outputs_by_key) == len(outputs), "Briar official audio manifest event keys must be unique")

    for event_name, (riot_event, riot_event_id) in BRIAR_AUDIO_EVENTS.items():
        local_name = event_name.removeprefix("lol_")
        expected_clip = f"{local_name}_clip"
        source_key = f"asset/base/sound/sfx/{event_name}"
        event_override = override.get(source_key, {})
        check(event_override.get("type") == "override", f"missing Briar sound event remap: {source_key}")
        check(
            event_override.get("remapping") == f"asset/lol_mod/sound/sfx/{local_name}",
            f"wrong Briar sound event target: {source_key}",
        )

        sound_relative = f"sound/sfx/{local_name}.sound_info"
        sound_path = MOD_ROOT / sound_relative
        check(sound_path.is_file(), f"missing Briar sound_info: {sound_relative}")
        if sound_path.is_file():
            plays = load_json(sound_relative).get("plays", [])
            check(
                plays == [{"delay": 0.0, "clip": expected_clip, "volume": 1.0}],
                f"{sound_relative} must play its single verified official clip at delay 0/volume 1",
            )

        clip_source = f"asset/base/sound/sfx/{expected_clip}"
        clip_override = override.get(clip_source, {})
        check(clip_override.get("type") == "override", f"missing Briar clip remap: {clip_source}")
        check(
            clip_override.get("remapping") == f"asset/lol_mod/sound/sfx/{expected_clip}",
            f"wrong Briar clip target: {clip_source}",
        )
        clip_relative = f"sound/sfx/{expected_clip}.wav"
        clip_path = MOD_ROOT / clip_relative
        check(clip_path.is_file() and clip_path.stat().st_size > 1000, f"missing/empty Briar clip: {clip_relative}")

        output = outputs_by_key.get(local_name, {})
        check(
            output.get("riot_event") == riot_event and output.get("riot_event_id") == riot_event_id,
            f"Briar official Riot event mapping drifted: {local_name}",
        )
        check(
            output.get("sound_info") == sound_relative
            and output.get("clip") == expected_clip
            and output.get("volume") == 1.0,
            f"Briar audio manifest runtime mapping mismatch: {local_name}",
        )
        check(
            isinstance(output.get("media_id"), int)
            and output.get("media_id") in output.get("event_media_pool", []),
            f"Briar audio manifest selected media is not in its event pool: {local_name}",
        )
        check(
            isinstance(output.get("source_wem_sha256"), str)
            and len(output.get("source_wem_sha256", "")) == 64,
            f"Briar audio manifest must pin the source WEM hash: {local_name}",
        )

        wav = output.get("wav", {})
        check(wav.get("path") == clip_relative, f"Briar audio manifest WAV path mismatch: {local_name}")
        if not clip_path.is_file():
            continue
        check(clip_path.stat().st_size == wav.get("size_bytes"), f"Briar audio WAV size mismatch: {clip_relative}")
        check(sha256(clip_path) == wav.get("sha256"), f"Briar audio WAV hash mismatch: {clip_relative}")
        try:
            with wave.open(str(clip_path), "rb") as decoded:
                channels = decoded.getnchannels()
                sample_width = decoded.getsampwidth()
                sample_rate = decoded.getframerate()
                frame_count = decoded.getnframes()
        except (wave.Error, EOFError) as error:
            ERRORS.append(f"{clip_relative}: cannot decode PCM WAV: {error}")
            continue
        check(channels == 1, f"{clip_relative} must be mono")
        check(sample_width == 2, f"{clip_relative} must be 16-bit PCM")
        check(sample_rate == 44100, f"{clip_relative} must be 44.1 kHz")
        check(
            (
                wav.get("channels"),
                wav.get("sample_width_bytes"),
                wav.get("sample_rate_hz"),
                wav.get("frame_count"),
            )
            == (channels, sample_width, sample_rate, frame_count),
            f"Briar audio manifest WAV format metadata mismatch: {clip_relative}",
        )
        duration = frame_count / sample_rate if sample_rate else 0.0
        check(
            math.isclose(float(output.get("duration_seconds", -1)), duration, rel_tol=0.0, abs_tol=1e-9),
            f"Briar audio manifest duration mismatch: {clip_relative}",
        )

    slot_adaptation = audio_manifest.get("event_mapping_audit", {}).get("slot_adaptation", {})
    check(
        slot_adaptation.get("q_slot_gameplay") == "Blood Frenzy / Snack"
        and slot_adaptation.get("q_cast_source_event") == "Play_sfx_Briar_BriarW_cast_foley_jump"
        and slot_adaptation.get("snack_runtime_proxy") == "Play_sfx_Briar_BriarBasicAttackFrenzy_OnHit",
        "Briar audio QA must document the Q-slot/W-event and Snack proxy adaptation",
    )


def validate_sivir_audio(champion: dict[str, Any], override: dict[str, Any]) -> None:
    actual_events = {
        effect.get("name")
        for effect in walk_effects(champion)
        if effect.get("type") in {"Sfx", "TargetSfx"}
    }
    check(actual_events == set(SIVIR_AUDIO_EVENTS), f"Sivir must wire exactly seven official sound events, got {sorted(actual_events)}")
    audio_manifest = load_json("qa/sivir_official_audio_sources.json")
    check(audio_manifest.get("schema_version") == 1 and audio_manifest.get("champion") == "Sivir", "Sivir official audio manifest identity is invalid")
    outputs = audio_manifest.get("outputs", [])
    outputs_by_key = {output.get("event_key"): output for output in outputs}
    expected_keys = {name.removeprefix("lol_") for name in SIVIR_AUDIO_EVENTS}
    check(set(outputs_by_key) == expected_keys and len(outputs_by_key) == len(outputs), "Sivir official audio event set is incomplete")
    for event_name, (riot_event, riot_event_id) in SIVIR_AUDIO_EVENTS.items():
        local_name = event_name.removeprefix("lol_")
        expected_clip = f"{local_name}_clip"
        event_source = f"asset/base/sound/sfx/{event_name}"
        event_override = override.get(event_source, {})
        check(event_override.get("type") == "override", f"missing Sivir sound event remap: {event_source}")
        check(event_override.get("remapping") == f"asset/lol_mod/sound/sfx/{local_name}", f"wrong Sivir sound event target: {event_source}")
        sound_relative = f"sound/sfx/{local_name}.sound_info"
        plays = load_json(sound_relative).get("plays", [])
        check(len(plays) == 1, f"{sound_relative} must play one verified official clip")
        if plays:
            check(plays[0].get("delay") == 0.0 and plays[0].get("clip") == expected_clip, f"{sound_relative} clip/delay mismatch")
            check(float(plays[0].get("volume", 0)) >= 0.70, f"{sound_relative} volume is too quiet")
        clip_source = f"asset/base/sound/sfx/{expected_clip}"
        clip_override = override.get(clip_source, {})
        check(clip_override.get("type") == "override", f"missing Sivir clip remap: {clip_source}")
        check(clip_override.get("remapping") == f"asset/lol_mod/sound/sfx/{expected_clip}", f"wrong Sivir clip target: {clip_source}")
        clip_relative = f"sound/sfx/{expected_clip}.wav"
        clip_path = MOD_ROOT / clip_relative
        check(clip_path.is_file() and clip_path.stat().st_size > 1000, f"missing/empty Sivir clip: {clip_relative}")

        output = outputs_by_key.get(local_name, {})
        check(output.get("riot_event") == riot_event and output.get("riot_event_id") == riot_event_id, f"Sivir Riot event mapping drifted: {local_name}")
        check(output.get("sound_info") == sound_relative and output.get("clip") == expected_clip, f"Sivir runtime audio mapping mismatch: {local_name}")
        check(isinstance(output.get("media_id"), int) and output.get("media_id") in output.get("event_media_pool", []), f"Sivir selected media is outside its event pool: {local_name}")
        check(isinstance(output.get("source_wem_sha256"), str) and len(output.get("source_wem_sha256", "")) == 64, f"Sivir source WEM hash is not pinned: {local_name}")
        wav = output.get("wav", {})
        check(wav.get("path") == clip_relative, f"Sivir WAV path mismatch: {local_name}")
        if not clip_path.is_file():
            continue
        check(clip_path.stat().st_size == wav.get("size_bytes"), f"Sivir WAV size mismatch: {clip_relative}")
        check(sha256(clip_path) == wav.get("sha256"), f"Sivir WAV hash mismatch: {clip_relative}")
        try:
            with wave.open(str(clip_path), "rb") as decoded:
                channels = decoded.getnchannels()
                sample_width = decoded.getsampwidth()
                sample_rate = decoded.getframerate()
                frame_count = decoded.getnframes()
        except (wave.Error, EOFError) as error:
            ERRORS.append(f"{clip_relative}: cannot decode PCM WAV: {error}")
            continue
        check((channels, sample_width, sample_rate) == (1, 2, 44100), f"{clip_relative} must be mono 16-bit PCM 44.1 kHz")
        check((wav.get("channels"), wav.get("sample_width_bytes"), wav.get("sample_rate_hz"), wav.get("frame_count")) == (channels, sample_width, sample_rate, frame_count), f"Sivir WAV metadata mismatch: {clip_relative}")
        duration = frame_count / sample_rate if sample_rate else 0.0
        check(math.isclose(float(output.get("duration_seconds", -1)), duration, rel_tol=0.0, abs_tol=1e-9), f"Sivir WAV duration mismatch: {clip_relative}")
        check(float(output.get("volume", -1)) == float(plays[0].get("volume", -2)) if plays else False, f"Sivir manifest volume mismatch: {local_name}")

    isolation = audio_manifest.get("native_audio_isolation", {})
    check(set(isolation.get("native_events", [])) == SIVIR_NATIVE_AUDIO_EVENTS, "Sivir native event isolation audit is incomplete")
    check(set(isolation.get("native_clips", [])) == SIVIR_NATIVE_AUDIO_CLIPS, "Sivir native clip isolation audit is incomplete")
    silence_event = "asset/lol_mod/sound/sfx/sivir_native_silence"
    silence_clip = "asset/lol_mod/sound/sfx/sivir_native_silence_clip"
    for native_event in SIVIR_NATIVE_AUDIO_EVENTS:
        source = f"asset/base/sound/sfx/{native_event}"
        mapping = override.get(source, {})
        check(mapping == {"remapping": silence_event, "type": "override"}, f"Sivir native event is not isolated: {source}")
    for native_clip in SIVIR_NATIVE_AUDIO_CLIPS:
        source = f"asset/base/sound/sfx/{native_clip}"
        mapping = override.get(source, {})
        check(mapping == {"remapping": silence_clip, "type": "override"}, f"Sivir native clip is not isolated: {source}")
    check(
        override.get("asset/base/sound/sfx/sivir_native_silence_clip")
        == {"remapping": silence_clip, "type": "override"},
        "Sivir silence clip self-remap is missing",
    )
    silence_info = load_json("sound/sfx/sivir_native_silence.sound_info")
    check(
        silence_info.get("plays")
        == [{"delay": 0.0, "clip": "sivir_native_silence_clip", "volume": 1.0}],
        "Sivir native silence sound_info contract changed",
    )
    silence_path = MOD_ROOT / "sound/sfx/sivir_native_silence_clip.wav"
    check(silence_path.is_file(), "Sivir native silence WAV is missing")
    if silence_path.is_file():
        check(silence_path.stat().st_size == 4454, "Sivir native silence WAV size changed")
        check(sha256(silence_path) == SIVIR_NATIVE_SILENCE_SHA256, "Sivir native silence WAV hash changed")
        try:
            with wave.open(str(silence_path), "rb") as decoded:
                silence_format = (
                    decoded.getnchannels(),
                    decoded.getsampwidth(),
                    decoded.getframerate(),
                    decoded.getnframes(),
                )
                silence_pcm = decoded.readframes(decoded.getnframes())
        except (wave.Error, EOFError) as error:
            ERRORS.append(f"Sivir native silence WAV cannot be decoded: {error}")
        else:
            check(silence_format == (1, 2, 44100, 2205), "Sivir native silence WAV format changed")
            check(silence_pcm == b"\x00" * 4410, "Sivir native silence WAV must contain only zero PCM")
    check(len(find_effect(champion.get("ult", {}), "Sfx", name="lol_sivir_r_cast")) == 1, "Sivir R command audio must be top-level and play once")
    r_ranges = find_effect(champion.get("ult", {}), "RangeEffect")
    if r_ranges:
        check(not find_effect(r_ranges[0], "Sfx"), "Sivir R command audio must not repeat once per ally")


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


def validate_briar_imagegen_and_qa_files() -> None:
    required_qa_files = {
        "qa/briar_actor_contact_final.png",
        "qa/briar_skill_icons_final.png",
        "qa/briar_vfx_contact_final.png",
        "qa/briar_imagegen_sources.json",
        "qa/briar_skill_contract_qa.md",
        "qa/briar_visual_qa.md",
        "qa/briar_live_qa.md",
        "qa/briar_audio_source_qa.md",
        "qa/briar_official_audio_sources.json",
    }
    for relative in sorted(required_qa_files):
        path = MOD_ROOT / relative
        check(path.is_file() and path.stat().st_size > 100, f"missing/empty Briar QA artifact: {relative}")

    contact_specs = {
        "qa/briar_actor_contact_final.png": (896, 576),
        "qa/briar_skill_icons_final.png": (576, 208),
        "qa/briar_vfx_contact_final.png": (1024, 1036),
    }
    for relative, expected_size in contact_specs.items():
        path = MOD_ROOT / relative
        if not path.is_file():
            continue
        image = Image.open(path).convert("RGBA")
        check(image.size == expected_size, f"{relative} must be {expected_size}, got {image.size}")
        check(image.getchannel("A").getbbox() is not None, f"{relative} must not be empty")

    q_sheet_path = MOD_ROOT / "aseprite_resources/effects/briar_q_overhead#sheet.png"
    q_anim_path = MOD_ROOT / "aseprite_resources/effects/briar_q_overhead#anim.fanim"
    check(q_sheet_path.is_file(), "Briar Q overhead effect sheet is missing")
    check(q_anim_path.is_file(), "Briar Q overhead effect animation is missing")
    if q_sheet_path.is_file():
        q_sheet = Image.open(q_sheet_path).convert("RGBA")
        check(q_sheet.size == (512, 64), "Briar Q overhead sheet must be eight 64x64 frames")
        for index in range(8):
            frame = q_sheet.crop((index * 64, 0, (index + 1) * 64, 64))
            bbox = frame.getchannel("A").getbbox()
            check(bbox is not None, f"Briar Q overhead frame {index} is empty")
            if bbox is not None:
                check(
                    bbox[2] - bbox[0] <= 30 and bbox[3] - bbox[1] <= 22,
                    f"Briar Q overhead frame {index} exceeds the compact 30x22 marker",
                )
                check(
                    bbox[1] >= 2 and bbox[3] <= 24,
                    f"Briar Q overhead frame {index} must stay in the top 24 pixels",
                )
    if q_anim_path.is_file():
        q_frames = load_json(
            "aseprite_resources/effects/briar_q_overhead#anim.fanim"
        ).get("anims", {}).get("impact", {}).get("frames", [])
        check(len(q_frames) == 8, "Briar Q overhead impact tag must contain eight frames")
        check(
            [frame.get("duration") for frame in q_frames]
            == [0.04, 0.04, 0.05, 0.05, 0.06, 0.06, 0.07, 0.09],
            "Briar Q overhead impact timing must remain a short 0.46-second burst",
        )

    for relative in ("qa/briar_skill_contract_qa.md", "qa/briar_visual_qa.md", "qa/briar_live_qa.md"):
        path = MOD_ROOT / relative
        if not path.is_file():
            continue
        body = path.read_text(encoding="utf-8")
        check("Briar" in body or "贝蕾亚" in body, f"{relative} must explicitly identify Briar")
    audio_qa = MOD_ROOT / "qa/briar_audio_source_qa.md"
    if audio_qa.is_file():
        body = audio_qa.read_text(encoding="utf-8")
        check("nine" in body.lower(), "Briar audio source QA must disclose all nine runtime clips")
        check("Snack" in body and "proxy" in body.lower(), "Briar audio source QA must disclose the Snack proxy")

    expected_sources = {
        "actor_model": "source/imagegen/briar_actor_contact.png",
        "run_cycle_nine_phase_source": "source/imagegen/briar_run_contact.png",
        "q_icon": "source/imagegen/briar_q_icon_source.png",
        "e_icon": "source/imagegen/briar_e_icon_source.png",
        "r_icon": "source/imagegen/briar_r_icon_source.png",
        "passive_bleed_vfx": "source/imagegen/briar_bleed_vfx_contact.png",
        "q_overhead_hit_vfx": "source/imagegen/champions/004_briar/briar_q_overhead_v1_source.png",
        "q_frenzy_vfx": "source/imagegen/briar_frenzy_vfx_contact.png",
        "e_vfx": "source/imagegen/briar_e_vfx_contact.png",
        "r_vfx": "source/imagegen/briar_r_vfx_contact.png",
    }
    expected_processed = {
        "actor_model_alpha": "source/processed/briar_actor_contact_alpha.png",
        "run_cycle_alpha": "source/processed/briar_run_contact_alpha.png",
        "passive_bleed_vfx_alpha": "source/processed/briar_bleed_vfx_contact_alpha.png",
        "q_overhead_hit_vfx_alpha": "source/processed/champions/004_briar/briar_q_overhead_v1_alpha.png",
        "q_frenzy_vfx_alpha": "source/processed/briar_frenzy_vfx_contact_alpha.png",
        "e_vfx_alpha": "source/processed/briar_e_vfx_contact_alpha.png",
        "r_vfx_alpha": "source/processed/briar_r_vfx_contact_alpha.png",
    }
    manifest_path = MOD_ROOT / "qa/briar_imagegen_sources.json"
    if manifest_path.is_file():
        manifest = load_json("qa/briar_imagegen_sources.json")
        check(manifest.get("schema_version") == 1, "Briar image-gen source manifest schema must be 1")
        check(manifest.get("generator") == "built-in image_gen", "Briar art must record built-in image_gen as its generator")
        check(manifest.get("prompt_record") == "source/imagegen/PROMPTS.md", "Briar image-gen manifest prompt record is incorrect")
        sources = manifest.get("sources", [])
        source_map = {source.get("role"): source for source in sources}
        check(len(source_map) == len(sources), "Briar image-gen source roles must be unique")
        check(set(source_map) == set(expected_sources), "Briar image-gen source roles are incomplete")
        for role, expected_path in expected_sources.items():
            source = source_map.get(role, {})
            check(source.get("path") == expected_path, f"Briar image-gen source path mismatch for {role}")
            raw_path = MOD_ROOT / expected_path
            check(raw_path.is_file(), f"missing Briar image-gen source: {expected_path}")
            if raw_path.is_file():
                check(sha256(raw_path) == source.get("sha256"), f"Briar image-gen source hash mismatch: {expected_path}")
                image = Image.open(raw_path)
                check(list(image.size) == source.get("dimensions"), f"Briar image-gen source dimensions mismatch: {expected_path}")
                check(image.mode == source.get("mode"), f"Briar image-gen source mode mismatch: {expected_path}")
                check(raw_path.stat().st_size == source.get("size_bytes"), f"Briar image-gen source size mismatch: {expected_path}")

        processed = manifest.get("processed", [])
        processed_map = {source.get("role"): source for source in processed}
        check(len(processed_map) == len(processed), "Briar processed image-gen source roles must be unique")
        check(set(processed_map) == set(expected_processed), "Briar processed image-gen source roles are incomplete")
        for role, expected_path in expected_processed.items():
            source = processed_map.get(role, {})
            check(source.get("path") == expected_path, f"Briar processed source path mismatch for {role}")
            processed_path = MOD_ROOT / expected_path
            check(processed_path.is_file(), f"missing Briar processed source: {expected_path}")
            if processed_path.is_file():
                check(sha256(processed_path) == source.get("sha256"), f"Briar processed source hash mismatch: {expected_path}")
                check(processed_path.stat().st_size == source.get("size_bytes"), f"Briar processed source size mismatch: {expected_path}")
                processed_image = Image.open(processed_path).convert("RGBA")
                check(list(processed_image.size) == source.get("dimensions"), f"Briar processed source dimensions mismatch: {expected_path}")
                corners = [
                    processed_image.getpixel((0, 0)),
                    processed_image.getpixel((processed_image.width - 1, 0)),
                    processed_image.getpixel((0, processed_image.height - 1)),
                    processed_image.getpixel((processed_image.width - 1, processed_image.height - 1)),
                ]
                check(all(pixel[3] == 0 for pixel in corners), f"Briar processed source has a non-transparent corner: {expected_path}")

    prompt_path = MOD_ROOT / "source/imagegen/PROMPTS.md"
    check(prompt_path.is_file(), "final image-gen prompt record is missing")
    if prompt_path.is_file():
        prompt_record = prompt_path.read_text(encoding="utf-8")
        check("Briar" in prompt_record or "贝蕾亚" in prompt_record, "image-gen prompt record must include the final Briar prompt set")
        for expected_path in expected_sources.values():
            check(Path(expected_path).name in prompt_record, f"image-gen prompt record omits Briar source {Path(expected_path).name}")


def validate_sivir_imagegen_and_qa_files() -> None:
    manifest = load_json("qa/sivir_imagegen_sources.json")
    check(manifest.get("schema_version") == 1, "Sivir image-gen audit schema must be 1")
    check(manifest.get("generator") == "built-in image_gen", "Sivir art must record built-in image_gen mode")
    expected_source_roles = {
        "actor_model",
        "run_cycle_nine_phase_source",
        "q_icon",
        "e_icon",
        "r_icon",
        "basic_attack_vfx",
        "q_out_return_vfx",
        "e_spell_shield_vfx",
        "r_cast_vfx",
        "r_ally_buff_vfx",
    }
    sources = manifest.get("sources", [])
    check({row.get("role") for row in sources} == expected_source_roles, "Sivir image-gen source roles are incomplete")
    for row in [*sources, *manifest.get("processed", [])]:
        path = MOD_ROOT / row.get("path", "missing")
        check(path.is_file(), f"missing Sivir image-gen source: {row.get('path')}")
        if path.is_file():
            check(path.stat().st_size == row.get("size_bytes"), f"Sivir image-gen size mismatch: {row.get('path')}")
            check(sha256(path) == row.get("sha256"), f"Sivir image-gen hash mismatch: {row.get('path')}")
            if row in manifest.get("processed", []):
                image = Image.open(path).convert("RGBA")
                corners = [image.getpixel((0, 0)), image.getpixel((image.width - 1, 0)), image.getpixel((0, image.height - 1)), image.getpixel((image.width - 1, image.height - 1))]
                check(all(pixel[3] == 0 for pixel in corners), f"Sivir processed source has an opaque corner: {row.get('path')}")
    for row in manifest.get("runtime_files", []):
        path = MOD_ROOT / row.get("path", "missing")
        check(path.is_file(), f"missing Sivir runtime audit file: {row.get('path')}")
        if path.is_file():
            check(path.stat().st_size == row.get("size_bytes") and sha256(path) == row.get("sha256"), f"Sivir runtime audit hash mismatch: {row.get('path')}")
    prompt_path = MOD_ROOT / manifest.get("prompt_record", "missing")
    check(prompt_path.is_file(), "Sivir final image-gen prompt record is missing")
    if prompt_path.is_file():
        prompts = prompt_path.read_text(encoding="utf-8")
        for marker in ("# Sivir image-gen prompts", "Sivir actor contact sheet", "Sivir nine-frame run cycle", "Sivir Q VFX", "Sivir E VFX", "Sivir R ally-buff VFX"):
            check(marker in prompts, f"Sivir prompt record is missing: {marker}")
    required_qa = [
        "qa/sivir_actor_contact_final.png",
        "qa/sivir_skill_icons_final.png",
        "qa/sivir_vfx_contact_final.png",
        "qa/sivir_skill_contract_qa.md",
        "qa/sivir_visual_qa.md",
        "qa/sivir_live_qa.md",
        "qa/sivir_audio_source_qa.md",
        "qa/sivir_official_audio_sources.json",
    ]
    for relative in required_qa:
        path = MOD_ROOT / relative
        check(path.is_file() and path.stat().st_size > 0, f"missing Sivir QA artifact: {relative}")


def validate_imagegen_sources() -> None:
    expected = {
        "qa/shen_imagegen_sources.json": {"actor_model", "run_cycle", "q_icon", "e_icon", "r_icon", "q_vfx", "e_vfx", "r_vfx"},
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
        "qa/briar_imagegen_sources.json": {
            "actor_model",
            "run_cycle_nine_phase_source",
            "q_icon",
            "e_icon",
            "r_icon",
            "passive_bleed_vfx",
            "q_overhead_hit_vfx",
            "q_frenzy_vfx",
            "e_vfx",
            "r_vfx",
        },
        "qa/sivir_imagegen_sources.json": {
            "actor_model",
            "run_cycle_nine_phase_source",
            "q_icon",
            "e_icon",
            "r_icon",
            "basic_attack_vfx",
            "q_out_return_vfx",
            "e_spell_shield_vfx",
            "r_cast_vfx",
            "r_ally_buff_vfx",
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
    # Shen/Lucian/Orianna contribute 25 active alpha sources. Briar adds six;
    # Sivir adds actor, run, and five distinct VFX contacts. Kled adds actor,
    # run, defeat, and three independent VFX contacts. Xayah's corrective
    # route adds seven disjoint body contacts plus attack/Q/E/R VFX contacts.
    # Later champions may add more processed sources, so this is a minimum;
    # every discovered source still receives the full alpha-corner audit.
    minimum_processed = 56
    check(
        len(processed) >= minimum_processed,
        f"processed image-gen source set must contain at least {minimum_processed} active PNGs",
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


def override_asset_extensions(source_key: str) -> tuple[str, ...]:
    """Return the on-disk extension(s) accepted by the source asset type."""
    if source_key.startswith("asset/base/text/"):
        return (".i18n",)
    if source_key.startswith("asset/base/style/"):
        return (".champion_view",)
    if source_key.startswith("asset/base/ui/layout/"):
        return (".ui",)
    if source_key.startswith("asset/base/ui/icons/"):
        return (".svg",)
    if source_key.startswith(("asset/base/ui/banpick/illust/", "asset/base/ui/ingame/")):
        return (".png",)
    if source_key.startswith("asset/base/sound/"):
        # The source bundle fixes whether an event is SoundInfo or a raw clip.
        # Both are valid sound asset classes, but a remapping target must resolve
        # to exactly one of them.
        return (".sound_info", ".wav")
    if source_key.startswith("asset/base/aseprite_resources/"):
        if source_key.endswith("#sheet"):
            return (".png",)
        if source_key.endswith("#anim"):
            return (".fanim",)
        if source_key.endswith("#data"):
            return (".sprite_sheet",)
        return (".png",)
    return ()


def asset_file_is_loadable(path: Path) -> bool:
    try:
        if path.suffix == ".png":
            with Image.open(path) as image:
                image.verify()
        elif path.suffix in {".i18n", ".champion_view", ".sound_info", ".fanim", ".sprite_sheet"}:
            document = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(document, dict):
                raise ValueError("root value must be an object")
        elif path.suffix == ".wav":
            with wave.open(str(path), "rb") as stream:
                if (
                    stream.getnchannels() <= 0
                    or stream.getsampwidth() <= 0
                    or stream.getframerate() <= 0
                    or stream.getnframes() <= 0
                ):
                    raise ValueError("invalid or empty PCM stream")
        elif path.suffix == ".svg":
            ET.fromstring(path.read_text(encoding="utf-8"))
        elif path.suffix == ".ui":
            source = path.read_text(encoding="utf-8")
            if not source.strip() or "\0" in source:
                raise ValueError("empty or NUL-containing UI source")
        else:
            raise ValueError(f"unsupported asset extension {path.suffix}")
    except Exception as error:
        check(False, f"override source is not loadable: {path.relative_to(MOD_ROOT).as_posix()}: {error}")
        return False
    return True


def validate_override_asset_discoverability(
    override: dict[str, Any],
    *,
    require_manifest: bool = True,
) -> tuple[int, int]:
    """Model the loader's typed extension lookup for every override remapping."""
    sprite_data_files = sorted(MOD_ROOT.rglob("*.sprite_data"))
    check(
        not sprite_data_files,
        "legacy .sprite_data files are not loadable and must be removed: "
        + ", ".join(path.relative_to(MOD_ROOT).as_posix() for path in sprite_data_files),
    )

    required_sprite_sheets = {
        "asset/base/aseprite_resources/ingame/item_icons_18x18#data": (
            "asset/lol_mod/aseprite_resources/ingame/item_icons_18x18#data",
            "aseprite_resources/ingame/item_icons_18x18#data.sprite_sheet",
        ),
        "asset/base/aseprite_resources/ingame/epic_monster_hp_guage#data": (
            "asset/lol_mod/aseprite_resources/ingame/epic_monster_hp_guage#data",
            "aseprite_resources/ingame/epic_monster_hp_guage#data.sprite_sheet",
        ),
    }
    for source_key, (target_key, relative) in required_sprite_sheets.items():
        check(
            override.get(source_key) == {"remapping": target_key, "type": "override"},
            f"typed sprite-sheet remapping changed: {source_key}",
        )
        check((MOD_ROOT / relative).is_file(), f"required sprite-sheet metadata is missing: {relative}")

    manifest_paths: set[str] = set()
    if require_manifest:
        manifest_path = MOD_ROOT / "build_manifest.json"
        check(manifest_path.is_file(), "build_manifest.json is missing for override discoverability validation")
        if manifest_path.is_file():
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                manifest_paths = {
                    row.get("path", "")
                    for row in manifest.get("files", [])
                    if isinstance(row, dict)
                }
                check("mod.override_info" in manifest_paths, "build manifest must contain mod.override_info")
            except Exception as error:
                check(False, f"build_manifest.json cannot be read for override validation: {error}")

    discovered = 0
    total = len(override)
    for source_key, row in override.items():
        check(isinstance(row, dict), f"override row must be an object: {source_key}")
        if not isinstance(row, dict):
            continue
        check(row.get("type") in {"override", "merge"}, f"override row has the wrong type: {source_key}")
        target_key = row.get("remapping")
        check(isinstance(target_key, str), f"override remapping is missing: {source_key}")
        if not isinstance(target_key, str):
            continue
        prefix = "asset/lol_mod/"
        check(target_key.startswith(prefix), f"override target must stay inside asset/lol_mod: {source_key}")
        if not target_key.startswith(prefix):
            continue
        relative_stem = target_key.removeprefix(prefix)
        extensions = override_asset_extensions(source_key)
        check(bool(extensions), f"override source uses an unsupported asset type: {source_key}")
        if not extensions:
            continue
        candidates = [MOD_ROOT / f"{relative_stem}{extension}" for extension in extensions]
        candidates = [path for path in candidates if path.is_file()]
        check(
            len(candidates) == 1,
            f"override target must resolve to exactly one typed source: {source_key} -> {relative_stem} "
            f"(found {len(candidates)})",
        )
        if len(candidates) != 1:
            continue
        path = candidates[0]
        try:
            relative = path.resolve().relative_to(MOD_ROOT.resolve()).as_posix()
        except ValueError:
            check(False, f"override target escapes the mod root: {source_key}")
            continue
        loadable = asset_file_is_loadable(path)
        if require_manifest:
            check(relative in manifest_paths, f"override source is absent from build_manifest.json: {relative}")
        if loadable:
            discovered += 1

    check(
        discovered == total,
        f"only {discovered}/{total} override asset source(s) are typed, present, and loadable",
    )
    return discovered, total


def normalized_animation_contract(document: dict[str, Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for tag, animation in document.get("anims", {}).items():
        frames = animation.get("frames", [])
        result[tag] = {
            "durations": [frame.get("duration") for frame in frames],
            "rects": [
                [
                    int(round(frame.get("data", {}).get(axis, -1)))
                    for axis in ("x", "y", "w", "h")
                ]
                for frame in frames
            ],
        }
    return result


def frame_crop(sheet: Image.Image, frame: dict[str, Any]) -> Image.Image:
    data = frame.get("data", {})
    x, y, width, height = (
        int(round(data.get("x", -1))),
        int(round(data.get("y", -1))),
        int(round(data.get("w", 0))),
        int(round(data.get("h", 0))),
    )
    return sheet.crop((x, y, x + width, y + height))


def weighted_alpha_centroid_x(image: Image.Image) -> float:
    alpha = image.convert("RGBA").getchannel("A")
    total = 0
    weighted = 0
    pixels = getattr(alpha, "get_flattened_data", alpha.getdata)()
    for index, value in enumerate(pixels):
        total += value
        weighted += (index % alpha.width) * value
    return weighted / total if total else alpha.width / 2


def tag_motion_metrics(
    sheet: Image.Image,
    document: dict[str, Any],
    tag: str,
) -> tuple[list[int], float]:
    widths: list[int] = []
    centroids: list[float] = []
    for frame in document.get("anims", {}).get(tag, {}).get("frames", []):
        crop = frame_crop(sheet, frame)
        bbox = crop.getchannel("A").getbbox()
        if bbox is None:
            continue
        widths.append(bbox[2] - bbox[0])
        centroids.append(weighted_alpha_centroid_x(crop) - crop.width / 2)
    span = max(centroids) - min(centroids) if centroids else 0.0
    return widths, span


def validate_recorded_file(record: dict[str, Any], label: str) -> Path | None:
    relative = record.get("path")
    check(isinstance(relative, str), f"{label}: QA file path is missing")
    if not isinstance(relative, str):
        return None
    path = MOD_ROOT / relative
    check(path.is_file(), f"{label}: recorded file is missing: {relative}")
    if not path.is_file():
        return None
    expected_size = record.get("bytes", record.get("size_bytes"))
    if expected_size is not None:
        check(path.stat().st_size == expected_size, f"{label}: recorded byte size changed: {relative}")
    expected_hash = record.get("sha256")
    if expected_hash is not None:
        check(sha256(path) == expected_hash, f"{label}: recorded hash changed: {relative}")
    return path


def validate_quality_nexus_assets(override: dict[str, Any]) -> None:
    qa_path = MOD_ROOT / "qa/quality_nexus_imagegen_pack.json"
    check(qa_path.is_file(), "Nexus ImageGen QA record is missing")
    if not qa_path.is_file():
        return
    qa = load_json("qa/quality_nexus_imagegen_pack.json")
    check(qa.get("schema") == "lol_mod.quality_nexus_imagegen_pack.v1", "Nexus QA schema changed")
    static_checks = qa.get("static_checks", {})
    check(
        bool(static_checks) and all(value is True for value in static_checks.values()),
        "Nexus QA contains a failed static check",
    )

    image_generation = qa.get("image_generation", {})
    for source_kind in ("source", "processed"):
        record = image_generation.get(source_kind, {})
        path = validate_recorded_file(record, f"Nexus {source_kind} ImageGen source")
        if path is not None and source_kind == "processed":
            with Image.open(path) as opened:
                processed = opened.convert("RGBA")
            corners = (
                (0, 0),
                (processed.width - 1, 0),
                (0, processed.height - 1),
                (processed.width - 1, processed.height - 1),
            )
            check(all(processed.getpixel(point)[3] == 0 for point in corners), "Nexus processed source corners must be transparent")

    expected_outputs: dict[str, tuple[str, str, str]] = {}
    for team in ("blue", "red"):
        for asset_kind, contract_kind in (("nexus", "nexus"), ("nexus_orb", "nexus_orb")):
            stem = f"{team}_{asset_kind}"
            for suffix, extension in (("sheet", ".png"), ("anim", ".fanim")):
                source_key = f"asset/base/aseprite_resources/ingame/{stem}#{suffix}"
                relative = f"aseprite_resources/ingame/{stem}#{suffix}{extension}"
                expected_outputs[source_key] = (relative, contract_kind, suffix)

    outputs = qa.get("outputs", {})
    check(set(outputs) == set(expected_outputs), "Nexus QA must contain exactly eight runtime resources")
    sheets: dict[str, Image.Image] = {}
    animations: dict[str, dict[str, Any]] = {}
    for source_key, (relative, contract_kind, suffix) in expected_outputs.items():
        target_key = source_key.replace("asset/base/", "asset/lol_mod/", 1)
        check(
            override.get(source_key) == {"remapping": target_key, "type": "override"},
            f"Nexus override mapping changed: {source_key}",
        )
        record = outputs.get(source_key, {})
        check(record.get("path") == relative, f"Nexus QA output path changed: {source_key}")
        check(record.get("override_target") == source_key, f"Nexus QA override target changed: {source_key}")
        check(record.get("mod_asset_key") == target_key, f"Nexus QA mod asset key changed: {source_key}")
        path = validate_recorded_file(record, f"Nexus output {source_key}")
        if path is None:
            continue
        stem = Path(relative).name.split("#", 1)[0]
        if suffix == "sheet":
            with Image.open(path) as opened:
                sheet = opened.convert("RGBA")
            sheets[stem] = sheet
            check(sheet.size == NEXUS_NATIVE_SHEET_SIZES[contract_kind], f"{stem} native sheet dimensions changed: {sheet.size}")
            check(record.get("dimensions") == list(sheet.size), f"{stem} QA sheet dimensions are stale")
            corners = ((0, 0), (sheet.width - 1, 0), (0, sheet.height - 1), (sheet.width - 1, sheet.height - 1))
            check(all(sheet.getpixel(point)[3] == 0 for point in corners), f"{stem} sheet corners must be transparent")
        else:
            document = load_json(relative)
            animations[stem] = document
            actual_contract = normalized_animation_contract(document)
            expected_contract = NEXUS_NATIVE_ANIMATION_CONTRACTS[contract_kind]
            check(actual_contract == expected_contract, f"{stem} no longer matches the native Nexus animation contract")
            expected_qa_contract = {
                tag: {
                    "frame_count": len(contract["durations"]),
                    "durations": contract["durations"],
                    "rects": contract["rects"],
                }
                for tag, contract in expected_contract.items()
            }
            check(
                qa.get("animation_contracts", {}).get(contract_kind) == expected_qa_contract,
                f"{contract_kind} QA animation contract is stale",
            )

    for asset_kind, expected_body_size in (("nexus", (52, 53)), ("nexus_orb", (25, 25))):
        blue_stem = f"blue_{asset_kind}"
        red_stem = f"red_{asset_kind}"
        if blue_stem not in sheets or red_stem not in sheets:
            continue
        check(
            sheets[blue_stem].getchannel("A").tobytes() == sheets[red_stem].getchannel("A").tobytes(),
            f"blue/red {asset_kind} alpha masks must remain byte-identical",
        )
        if blue_stem in animations and red_stem in animations:
            check(
                animations[blue_stem].get("anims") == animations[red_stem].get("anims"),
                f"blue/red {asset_kind} animation documents must match",
            )
        for stem in (blue_stem, red_stem):
            if stem not in animations:
                continue
            visible_sizes: set[tuple[int, int]] = set()
            for tag in ("idle", "attack"):
                for frame in animations[stem].get("anims", {}).get(tag, {}).get("frames", []):
                    bbox = frame_crop(sheets[stem], frame).getchannel("A").getbbox()
                    check(bbox is not None, f"{stem} {tag} contains an empty body frame")
                    if bbox is not None:
                        visible_sizes.add((bbox[2] - bbox[0], bbox[3] - bbox[1]))
            check(visible_sizes == {expected_body_size}, f"{stem} body size is unstable: {sorted(visible_sizes)}")


def validate_objective_and_wolf_motion_qa() -> None:
    objective_path = MOD_ROOT / "qa/quality_objectives_imagegen_pack.json"
    check(objective_path.is_file(), "objective ImageGen QA record is missing")
    if objective_path.is_file():
        qa = load_json("qa/quality_objectives_imagegen_pack.json")
        check(qa.get("schema") == "lol_mod.quality_objectives_imagegen_pack.v3", "objective QA schema changed")
        static_checks = qa.get("static_checks", {})
        check(
            bool(static_checks) and all(value is True for value in static_checks.values()),
            "objective QA contains a failed static check",
        )
        runtime = qa.get("runtime", {})
        facing = runtime.get("objective_attack_facing", {})
        native_facing = facing.get("native_game_setting", {})
        check(
            native_facing.get("epic_action_name") == "attack_left",
            "Baron: bundled game_setting attack action is not recorded as attack_left",
        )
        check(
            native_facing.get("serpen_action_name") == "attack",
            "Dragon: bundled game_setting attack action is not recorded as attack",
        )
        check(
            native_facing.get("epic_attack_right_reachable_from_game_setting") is False,
            "Baron: QA must not claim the unused attack_right tag is a live direction",
        )
        check(
            facing.get("canonical_art_direction") == "right"
            and facing.get("native_action_flip_method")
            == "game_view::GameView::get_action_flip_x"
            and facing.get("native_render_consumer") == "game_view::EntityView::render"
            and facing.get("actual_action_target_drives_flip_x") is True,
            "Objectives: canonical-art/native actual-target flip contract is incomplete",
        )
        check(
            facing.get("mod_writes_entity_flip_x") is False,
            "Objectives: the mod must not override the native action-target flip",
        )
        check(
            set(facing.get("variants", []))
            == {"epic", "infernal", "ocean", "mountain", "cloud", "hextech", "elder"},
            "Objectives: runtime facing does not cover Baron, five elemental dragons, and Elder",
        )
        runtime_source = (MOD_ROOT / "src/lib.rs").read_text(encoding="utf-8")
        for forbidden in (
            "fn sync_objective_attack_facing()",
            "sync_objective_attack_facing();",
            ".nearest_enemy",
            "entity.flip_x =",
        ):
            check(
                forbidden not in runtime_source,
                f"Objectives: mod-side facing override must stay absent: {forbidden!r}",
            )

        def validate_runtime_monster(
            label: str,
            record: dict[str, Any],
            native_dimensions_expected: tuple[int, int],
            runtime_dimensions_expected: tuple[int, int],
            maximum_visible_width: int,
            *,
            minimum_visible_width: int | None = None,
            exact_native_frame_rectangles: bool,
            attack_only_safe_expansion: bool = False,
        ) -> tuple[Path | None, Path | None]:
            native_dimensions = record.get("native_sheet_contract", {}).get("dimensions")
            check(native_dimensions == list(native_dimensions_expected), f"{label}: native sheet dimensions changed in QA")
            check(record.get("visible_width_cap") <= maximum_visible_width, f"{label}: visible-width cap regressed")
            check(record.get("native_animation_contract_exact") is True, f"{label}: native animation contract is not exact")
            if exact_native_frame_rectangles:
                check(record.get("native_frame_rect_contract_exact") is True, f"{label}: native frame rectangles are not exact")
            elif attack_only_safe_expansion:
                check(
                    record.get("native_frame_rect_contract_attack_safe_expanded") is True,
                    f"{label}: attack-safe frame expansion contract is missing",
                )
                check(
                    record.get("non_attack_frame_sizes_match_native") is True,
                    f"{label}: non-attack frame sizes changed",
                )
                check(
                    record.get("target_effect_frame_sizes_match_native") is True,
                    f"{label}: target-effect frame sizes changed",
                )
            else:
                check(
                    record.get("native_frame_rect_contract_safely_expanded") is True,
                    f"{label}: widened body-frame contract is missing",
                )
            sheet_path = validate_recorded_file(record.get("sheet", {}), f"{label} sheet")
            anim_path = validate_recorded_file(record.get("animation", {}), f"{label} animation")
            if sheet_path is None or anim_path is None:
                return sheet_path, anim_path
            with Image.open(sheet_path) as opened:
                sheet = opened.convert("RGBA")
            document = json.loads(anim_path.read_text(encoding="utf-8"))
            check(sheet.size == runtime_dimensions_expected, f"{label}: runtime sheet dimensions changed: {sheet.size}")
            check(record.get("sheet", {}).get("size") == list(sheet.size), f"{label}: runtime sheet QA dimensions are stale")
            widths: list[int] = []
            for tag in ("base", "idle"):
                tag_widths, _ = tag_motion_metrics(sheet, document, tag)
                widths.extend(tag_widths)
            check(bool(widths), f"{label}: base/idle frames are empty")
            if widths:
                check(max(widths) <= maximum_visible_width, f"{label}: visible body width regressed to {max(widths)}px")
                if minimum_visible_width is not None:
                    check(max(widths) >= minimum_visible_width, f"{label}: visible body is undersized at {max(widths)}px")
            _, idle_span = tag_motion_metrics(sheet, document, "idle")
            recorded_span = record.get("idle_horizontal_centroid_span_px")
            check(isinstance(recorded_span, (int, float)), f"{label}: idle centroid QA is missing")
            if isinstance(recorded_span, (int, float)):
                check(math.isclose(idle_span, recorded_span, abs_tol=1e-6), f"{label}: idle centroid QA is stale")
            check(idle_span <= 2.0, f"{label}: idle horizontal centroid drifts by {idle_span:.3f}px")
            if not exact_native_frame_rectangles and not attack_only_safe_expansion:
                check(record.get("maximum_idle_center_offset_px", 99) <= 1.0, f"{label}: idle body is not centred")
                check(
                    record.get("maximum_attack_ground_anchor_offset_px", 99) <= 1.0,
                    f"{label}: attack body walks away from the entity centre",
                )
                check(
                    record.get("attack_ground_offset_from_frame_center_target_px") == 35.0,
                    f"{label}: attack ground target changed",
                )
                check(
                    record.get("maximum_attack_ground_offset_error_px", 99) <= 0.5,
                    f"{label}: attack body drifts in map depth",
                )
                check(
                    record.get("attack_body_bbox_center_y_span_px", 99) <= 5.0,
                    f"{label}: attack body vertical pose span is unstable",
                )
                check(record.get("maximum_anchor_delta_to_target_px", 99) <= 1.0, f"{label}: runtime anchor drifted")
                check(record.get("maximum_bottom_delta_to_native_px") == 0, f"{label}: native landing line drifted")
            return sheet_path, anim_path

        epic = runtime.get("epic", {})
        validate_runtime_monster(
            "Baron",
            epic,
            (3538, 150),
            (4050, 150),
            106,
            exact_native_frame_rectangles=False,
            attack_only_safe_expansion=True,
        )
        check(
            epic.get("attack_source_indices") == [4, 5, 6, 7, 10],
            "Baron: attack source sequence must end on the clean recovery pose",
        )
        check(
            epic.get("attack_tags_use_canonical_right_facing_art") is True
            and epic.get("runtime_direction_owned_by_native_action_flip_x") is True,
            "Baron: attack art is not canonical for native actual-target flipping",
        )
        check(
            epic.get("attack_frame_widths") == [141, 127, 187, 215, 139],
            "Baron: attack-safe canvas widths changed",
        )
        check(
            epic.get("maximum_attack_alpha_clip_loss_pixels") == 0,
            "Baron: attack pixels are clipped by the runtime canvas",
        )
        check(
            epic.get("minimum_attack_side_clearance_px", -1) >= 2,
            "Baron: attack artwork touches a runtime frame side",
        )
        check(
            epic.get("maximum_attack_anchor_offset_delta_px", 99) <= 0.75,
            "Baron: attack ground anchor moved relative to the native frame centre",
        )
        check(
            epic.get("maximum_attack_bottom_delta_to_native_px") == 0,
            "Baron: attack landing line moved",
        )
        check(
            epic.get("minimum_target_effect_frame_clearance_px", -1) >= 1,
            "Baron: target-impact VFX touches its runtime canvas edge",
        )
        attack_metrics = epic.get("attack_frame_metrics", [])
        check(len(attack_metrics) == 10, "Baron: expected five frames per attack direction")
        for metric in attack_metrics:
            label = f"Baron {metric.get('tag')}[{metric.get('frame_index')}]"
            check(metric.get("alpha_clip_loss_pixels") == 0, f"{label}: alpha was clipped")
            check(metric.get("left_clearance_px", -1) >= 2, f"{label}: left edge is clipped")
            check(metric.get("right_clearance_px", -1) >= 2, f"{label}: right edge is clipped")
            check(metric.get("bottom_delta_to_native_px") == 0, f"{label}: landing line drifted")
        contact_path = validate_recorded_file(
            epic.get("attack_contact_sheet", {}),
            "Baron attack contact sheet",
        )
        if contact_path is not None:
            with Image.open(contact_path) as opened:
                check(
                    opened.size == (1610, 540),
                    f"Baron attack contact sheet dimensions changed: {opened.size}",
                )

        dragon_variants = runtime.get("dragon_variants", {})
        expected_dragons = {"infernal", "ocean", "mountain", "cloud", "hextech", "elder"}
        check(set(dragon_variants) == expected_dragons, "objective QA must contain five elemental dragons and Elder")
        variant_paths: dict[str, tuple[Path | None, Path | None]] = {}
        for name in sorted(expected_dragons):
            record = dragon_variants.get(name, {})
            variant_paths[name] = validate_runtime_monster(
                f"{name} dragon",
                record,
                (1498, 226),
                (1861, 226),
                80,
                minimum_visible_width=67,
                exact_native_frame_rectangles=False,
            )
            edge_ratio = record.get("edge_connected_magenta_cleanup", {}).get("hot_magenta_edge_ratio")
            check(isinstance(edge_ratio, (int, float)), f"{name} dragon: magenta-edge QA is missing")
            if isinstance(edge_ratio, (int, float)):
                check(edge_ratio <= 0.011, f"{name} dragon: magenta edge ratio regressed to {edge_ratio:.2%}")
            check(
                record.get("attack_art_canonical_direction") == "right"
                and record.get("runtime_direction_owned_by_native_action_flip_x") is True,
                f"{name} dragon: native attack-facing contract is missing",
            )

        serpen = runtime.get("serpen_infernal_default", {})
        serpen_sheet = validate_recorded_file(serpen.get("sheet", {}), "default Serpen sheet")
        serpen_anim = validate_recorded_file(serpen.get("animation", {}), "default Serpen animation")
        infernal_sheet, infernal_anim = variant_paths.get("infernal", (None, None))
        if serpen_sheet is not None and infernal_sheet is not None:
            check(sha256(serpen_sheet) == sha256(infernal_sheet), "default Serpen sheet must match Infernal Dragon")
        if serpen_anim is not None and infernal_anim is not None:
            check(sha256(serpen_anim) == sha256(infernal_anim), "default Serpen animation must match Infernal Dragon")

    wolf_path = MOD_ROOT / "qa/quality_small_jungle_imagegen_pack.json"
    check(wolf_path.is_file(), "small-jungle ImageGen QA record is missing")
    if not wolf_path.is_file():
        return
    qa = load_json("qa/quality_small_jungle_imagegen_pack.json")
    check(qa.get("schema_version") == 3, "small-jungle QA schema changed")
    check(qa.get("result", {}).get("all_static_checks_passed") is True, "small-jungle QA has failed checks")
    assets = qa.get("assets", [])
    for record in assets:
        static_checks = record.get("static_checks", {})
        check(
            bool(static_checks) and all(value is True for value in static_checks.values()),
            f"{record.get('runtime_asset', 'unknown')}: small-jungle QA contains a failed check",
        )

    gromp_records = [record for record in assets if record.get("runtime_asset") == "mushroom"]
    check(len(gromp_records) == 1, "small-jungle QA must contain exactly one Gromp/mushroom record")
    if len(gromp_records) == 1:
        gromp = gromp_records[0]
        check(
            gromp.get("pack", {}).get("max_runtime_visible_envelope") == [72, 50],
            "Gromp must use the reduced 72x50 visible envelope",
        )
        check(gromp.get("pack", {}).get("cell_size") == 97, "Gromp 97px frame anchor changed")
        check(
            gromp.get("pack", {}).get("baseline_exclusive") == 78,
            "Gromp baseline anchor changed",
        )
        runtime_tags = gromp.get("runtime", {}).get("tags", {})
        check(
            {name: tag.get("frame_count") for name, tag in runtime_tags.items()}
            == {"idle": 4, "dead": 4, "attack": 5, "run": 8},
            "Gromp native action counts changed",
        )
    by_runtime = {
        record.get("runtime_asset"): record
        for record in assets
    }
    for runtime_name, native_dimensions, runtime_dimensions, width_cap in (
        ("rhino", [1372, 52], [1435, 52], 64),
        ("stump", [782, 42], [1302, 47], 56),
    ):
        record = by_runtime.get(runtime_name, {})
        check(bool(record), f"{runtime_name}: small-jungle QA record is missing")
        if not record:
            continue
        check(record.get("native_sheet_contract", {}).get("dimensions") == native_dimensions, f"{runtime_name}: native sheet dimensions changed")
        check(record.get("runtime", {}).get("sheet", {}).get("dimensions") == runtime_dimensions, f"{runtime_name}: runtime sheet dimensions changed")
        check(record.get("pack", {}).get("native_anchor_reference_preserved") is True, f"{runtime_name}: native anchor reference is missing")
        motion = record.get("runtime", {}).get("motion_metrics", {})
        check(motion.get("maximum_visible_width_px", 99) <= width_cap, f"{runtime_name}: visible width exceeds tuned envelope")
        check(motion.get("maximum_visible_width_px", 0) >= width_cap - 1, f"{runtime_name}: actor is undersized for tuned envelope")
        check(motion.get("maximum_idle_run_center_offset_px", 99) <= 1.0, f"{runtime_name}: idle/run body is off-centre")
        check(motion.get("maximum_anchor_delta_to_target_px", 99) <= 1.0, f"{runtime_name}: placement anchor drifted")
        check(motion.get("maximum_bottom_delta_to_native_px") == 0, f"{runtime_name}: native landing line drifted")

    wolves = [record for record in assets if record.get("runtime_asset") == "bee"]
    check(len(wolves) == 1, "small-jungle QA must contain exactly one Murk Wolf/bee runtime record")
    if len(wolves) != 1:
        return
    wolf = wolves[0]
    check(
        wolf.get("native_sheet_contract", {}).get("dimensions") == [714, 54],
        "Murk Wolf native sheet dimensions changed in QA",
    )
    check(wolf.get("pack", {}).get("native_sheet_height_preserved") is True, "Murk Wolf native sheet height is not preserved")
    check(wolf.get("pack", {}).get("native_frame_rectangles_safely_expanded") is True, "Murk Wolf widened frame contract is missing")
    check(
        wolf.get("pack", {}).get("ground_anchor_policy")
        == "fixed_runtime_bottom_padding",
        "Murk Wolf fixed-ground anchor policy is missing",
    )
    check(
        wolf.get("pack", {}).get("fixed_ground_padding_px") == 2,
        "Murk Wolf ground padding must stay at two pixels",
    )
    runtime = wolf.get("runtime", {})
    sheet_path = validate_recorded_file(runtime.get("sheet", {}), "Murk Wolf sheet")
    anim_path = validate_recorded_file(runtime.get("animation", {}), "Murk Wolf animation")
    contact_path = validate_recorded_file(
        runtime.get("motion_contact", {}),
        "Murk Wolf motion contact",
    )
    check(
        runtime.get("motion_contact", {}).get("dimensions") == [832, 240],
        "Murk Wolf motion contact dimensions changed",
    )
    check(
        runtime.get("motion_contact_tag_order") == ["idle", "attack", "dead", "run"],
        "Murk Wolf motion contact tag order changed",
    )
    check(contact_path is not None, "Murk Wolf motion contact is unavailable")
    if sheet_path is None or anim_path is None:
        return
    with Image.open(sheet_path) as opened:
        sheet = opened.convert("RGBA")
    document = json.loads(anim_path.read_text(encoding="utf-8"))
    check(sheet.size == (1150, 54), f"Murk Wolf runtime sheet dimensions changed: {sheet.size}")
    motion = runtime.get("motion_metrics", {})
    maximum_visible_width = motion.get("maximum_visible_width_px")
    check(maximum_visible_width == 40, f"Murk Wolf QA visible-width target changed: {maximum_visible_width}")
    actual_widths: list[int] = []
    actual_ground_paddings: list[int] = []
    for tag in document.get("anims", {}):
        widths, _ = tag_motion_metrics(sheet, document, tag)
        actual_widths.extend(widths)
        for frame in document["anims"][tag]["frames"]:
            data = frame["data"]
            x = int(data["x"])
            y = int(data["y"])
            width = int(data["w"])
            height = int(data["h"])
            bbox = sheet.crop((x, y, x + width, y + height)).getchannel("A").getbbox()
            if bbox is not None:
                actual_ground_paddings.append(height - bbox[3])
    check(bool(actual_widths), "Murk Wolf runtime animation has no visible frames")
    if actual_widths:
        check(max(actual_widths) <= 40, f"Murk Wolf visible width regressed to {max(actual_widths)}px")
        check(max(actual_widths) >= 39, f"Murk Wolf is undersized at {max(actual_widths)}px")
    check(motion.get("maximum_idle_run_center_offset_px", 99) <= 1.0, "Murk Wolf idle/run body is off-centre")
    check(motion.get("maximum_anchor_delta_to_target_px", 99) <= 1.0, "Murk Wolf placement anchor drifted")
    check(
        motion.get("ground_padding_values_px") == [2],
        "Murk Wolf QA contains more than one ground padding",
    )
    check(
        motion.get("maximum_ground_padding_delta_px") == 0,
        "Murk Wolf fixed-ground placement drifted",
    )
    check(
        bool(actual_ground_paddings) and set(actual_ground_paddings) == {2},
        f"Murk Wolf runtime frames do not share the 2px ground anchor: {sorted(set(actual_ground_paddings))}",
    )
    for tag in ("idle", "run"):
        _, actual_span = tag_motion_metrics(sheet, document, tag)
        recorded_span = motion.get(f"{tag}_horizontal_centroid_span_px")
        check(isinstance(recorded_span, (int, float)), f"Murk Wolf {tag} centroid QA is missing")
        if isinstance(recorded_span, (int, float)):
            check(math.isclose(actual_span, recorded_span, abs_tol=1e-6), f"Murk Wolf {tag} centroid QA is stale")
        check(actual_span <= 2.0, f"Murk Wolf {tag} horizontal centroid drifts by {actual_span:.3f}px")
    native_tags = wolf.get("native_animation_contract", {}).get("tags", {})
    for tag, native in native_tags.items():
        frames = document.get("anims", {}).get(tag, {}).get("frames", [])
        check(len(frames) == native.get("frame_count"), f"Murk Wolf {tag} native frame count changed")
        check(
            [frame.get("duration") for frame in frames] == native.get("durations"),
            f"Murk Wolf {tag} native frame durations changed",
        )


def validate_quality_map_and_bp_skin(override: dict[str, Any]) -> None:
    map_qa_path = MOD_ROOT / "qa/quality_map_imagegen_pack.json"
    check(map_qa_path.is_file(), "quality-map ImageGen QA record is missing")
    if map_qa_path.is_file():
        map_qa = load_json("qa/quality_map_imagegen_pack.json")
        check(map_qa.get("schema") == "lol_mod.quality_map_imagegen_pack.v4", "quality-map QA schema changed")
        static_checks = map_qa.get("static_checks", {})
        check(bool(static_checks) and all(static_checks.values()), "quality-map QA contains a failed check")
        check(all(map_qa.get("mask_checks", {}).values()), "quality-map native alpha footprint changed")
        check(
            all(map_qa.get("native_alpha_checks", {}).values()),
            "quality-map runtime alpha differs from the native bundle",
        )
        landmarks = map_qa.get("landmarks", {})
        landmark_masks = landmarks.get("mask_audit", {})
        landmark_application = landmarks.get("application", {})
        check(
            landmark_masks.get("landmark_type_count") == 9
            and landmark_masks.get("landmark_instance_count") == 30,
            "quality-map landmark inventory changed",
        )
        check(
            landmark_masks.get("inter_landmark_overlap_pixels") == 0
            and landmark_masks.get("wall_or_bush_overlap_pixels_after_exclusion") == 0,
            "quality-map landmark masks overlap another landmark, wall, or brush",
        )
        check(
            landmark_application.get("changed_pixels_outside_allowed_union") == 0
            and landmark_application.get("alpha_preserved") is True
            and landmark_application.get("size_preserved") is True,
            "quality-map landmark compositor escaped its native masks",
        )
        check(
            all(map_qa.get("rgb_delta_checks", {}).values()),
            "quality-map runtime color delta exceeds the low-intensity native limit",
        )
        contracts = map_qa.get("contracts", {})
        check(
            contracts.get("runtime_structure_source") == "native bundle 5v5 layers only",
            "quality-map runtime structure must come only from native bundle layers",
        )
        check(
            contracts.get("minimap_source") == "native minimap background with global color grade only",
            "quality-map minimap must preserve the native map layout",
        )
        source_usage = map_qa.get("source_usage", {})
        check(
            source_usage.get("microdetail", {}).get("strength", 1.0) <= 0.05,
            "quality-map ImageGen microdetail strength is too high",
        )
        check(
            not source_usage.get("microdetail", {}).get(
                "spatial_terrain_semantics_copied", True
            ),
            "quality-map ImageGen source must not copy terrain semantics",
        )
        surface_strength_caps = {
            "wall_main_masonry": 0.08,
            "wall_outer_cliff": 0.10,
            "wall_front_masonry": 0.08,
            "bush_microdetail": 0.08,
        }
        for surface_name, strength_cap in surface_strength_caps.items():
            record = source_usage.get(surface_name, {})
            check(
                record.get("operation") == "high-frequency-luminance-only"
                and record.get("direct_source_pixels_copied") is False,
                f"quality-map {surface_name} must use isolated high-frequency luminance only",
            )
            check(
                0 < record.get("strength", 1.0) <= strength_cap,
                f"quality-map {surface_name} strength exceeds its audited cap",
            )
            check(
                record.get("changed_pixels", 0) > 0
                and record.get("alpha_byte_identical") is True
                and record.get("transparent_rgba_byte_identical") is True,
                f"quality-map {surface_name} changed no visible pixels or escaped native alpha",
            )

        surface_detail = map_qa.get("surface_detail", {})
        surface_layers = surface_detail.get("layers", {})
        for surface_name in ("wall_5v5", "wall_5v5_front", "bush_5v5"):
            record = surface_layers.get(surface_name, {})
            check(
                record.get("dimensions_1280") is True
                and record.get("alpha_byte_identical") is True
                and record.get("transparent_rgba_byte_identical") is True
                and record.get("nontransparent_count_identical") is True
                and record.get("nontransparent_bbox_identical") is True
                and record.get("native_footprint") == record.get("runtime_footprint"),
                f"quality-map {surface_name} geometry or transparent RGBA changed",
            )
            mean_delta = record.get("visible_mean_abs_rgb_from_official", [])
            check(
                record.get("changed_pixels_from_official", 0) > 0
                and isinstance(mean_delta, list)
                and len(mean_delta) == 3
                and 0 < max(mean_delta) <= 1.0,
                f"quality-map {surface_name} microdetail is missing or too strong",
            )

        shadow_records = surface_detail.get("shadow_rgba_sha256", {})
        for shadow_name in (
            "wall_shadow_5v5",
            "bush_shadow_5v5",
            "tower_shadow",
            "nexus_shadow",
        ):
            record = shadow_records.get(shadow_name, {})
            check(
                record.get("byte_identical") is True
                and record.get("official") == record.get("runtime"),
                f"quality-map {shadow_name} must remain official RGBA byte-for-byte",
            )

        preview = surface_detail.get("preview", {})
        check(
            preview.get("scale") == "1:1"
            and preview.get("resampling") == "none"
            and set(preview.get("crops", {}))
            == {"left_outer_cliff", "bush", "bottom_front_wall"},
            "quality-map surface preview must retain the three audited 1:1 crops",
        )
        validate_recorded_file(preview.get("image", {}), "quality-map surface-detail preview")
        rejected_map_path = MOD_ROOT / "source/imagegen/map/rift_background_5v5_v2_source.png"
        check(
            not rejected_map_path.exists(),
            "rejected whole-map ImageGen source must stay deleted",
        )
        runtime = map_qa.get("runtime", {})
        expected_map_assets = {
            "background_5v5": [1280, 1280],
            "wall_5v5": [1280, 1280],
            "wall_5v5_front": [1280, 1280],
            "wall_shadow_5v5": [1280, 1280],
            "bush_5v5": [1280, 1280],
            "bush_shadow_5v5": [1280, 1280],
            "tower_shadow": [23, 24],
            "nexus_shadow": [54, 30],
            "minimap_5v5_bg": [320, 320],
        }
        for name, dimensions in expected_map_assets.items():
            record = runtime.get(name, {})
            check(record.get("dimensions") == dimensions, f"{name}: quality-map dimensions changed")
            validate_recorded_file(record, f"quality-map {name}")
            key = f"asset/base/aseprite_resources/ingame/5v5/{name}"
            check(
                override.get(key)
                == {
                    "remapping": key.replace("asset/base/", "asset/lol_mod/", 1),
                    "type": "override",
                },
                f"{name}: quality-map override is missing or incorrect",
            )
    check("asset/base/setting/map_setting" not in override, "quality map must never override map_setting")
    check(
        "asset/base/aseprite_resources/ingame/minimap_5v5#sheet" not in override,
        "quality map must preserve dynamic minimap markers",
    )
    check(
        "asset/base/aseprite_resources/ingame/minimap_5v5#data" not in override,
        "quality map must preserve dynamic minimap marker data",
    )

    bp_qa_path = MOD_ROOT / "qa/quality_bp_skin_imagegen_pack.json"
    check(bp_qa_path.is_file(), "BP-skin ImageGen QA record is missing")
    if bp_qa_path.is_file():
        bp_qa = load_json("qa/quality_bp_skin_imagegen_pack.json")
        check(bp_qa.get("schema") == "lol_mod.quality_bp_skin_imagegen_pack.v1", "BP-skin QA schema changed")
        checks = bp_qa.get("static_checks", {})
        check(bool(checks) and all(checks.values()), "BP-skin QA contains a failed check")
        check(all(bp_qa.get("geometry_contract", {}).values()), "BP-skin native layout geometry changed")
        validate_recorded_file(bp_qa.get("source", {}), "BP-skin ImageGen source")
        runtime = bp_qa.get("runtime", {})
        check(runtime.get("dimensions") == [1920, 1080], "BP-skin runtime background must be 1920x1080")
        validate_recorded_file(runtime, "BP-skin runtime background")
        layout = bp_qa.get("layout", {})
        check(
            layout.get("restored_native_sha256") == layout.get("native_baseline_normalized_sha256"),
            "BP-skin layout contains changes outside the audited skin delta",
        )
        components = bp_qa.get("components", {})
        expected_component_sizes = {
            "header_chrome": [1920, 85],
            "bottom_chrome": [1920, 150],
            "champion_card_frame": [119, 130],
            "filter_toolbar": [1260, 50],
            "champion_grid_frame": [1250, 377],
            "stat_frame": [549, 371],
            "skill_frame": [687, 115],
            "side_pick_frame": [300, 174],
        }
        imagegen_assets = components.get("imagegen_assets", {})
        for name, dimensions in expected_component_sizes.items():
            asset = imagegen_assets.get(name, {})
            validate_recorded_file(asset.get("source", {}), f"BP-skin {name} ImageGen source")
            runtime_record = asset.get("runtime", {})
            check(
                runtime_record.get("dimensions") == dimensions,
                f"BP-skin {name} runtime dimensions changed",
            )
            validate_recorded_file(runtime_record, f"BP-skin {name} runtime")
        champion_slot = components.get("champion_slot", {})
        check(
            champion_slot.get("restored_native_sha256")
            == champion_slot.get("native_baseline_normalized_sha256"),
            "BP-skin champion-slot contains changes outside the audited visual delta",
        )
        contact = components.get("contact_sheet", {})
        check(
            contact.get("dimensions") == [1200, 800],
            "BP-skin component contact dimensions changed",
        )
        validate_recorded_file(contact, "BP-skin component contact")
        check(
            bp_qa.get("imagegen_asset_requests") == [],
            "BP-skin still lists unfulfilled ImageGen component requests",
        )


def validate_quality_ingame_hud(override: dict[str, Any]) -> None:
    qa_path = MOD_ROOT / "qa/quality_ingame_hud_imagegen_pack.json"
    check(qa_path.is_file(), "in-game HUD ImageGen QA record is missing")
    if not qa_path.is_file():
        return
    qa = load_json("qa/quality_ingame_hud_imagegen_pack.json")
    check(
        qa.get("schema") == "lol_mod.quality_ingame_hud_imagegen_pack.v1",
        "in-game HUD QA schema changed",
    )
    static_checks = qa.get("static_checks", {})
    check(bool(static_checks) and all(static_checks.values()), "in-game HUD QA contains a failed check")

    expected_layouts = {
        "player_info",
        "wide_player_info",
        "camera_info",
        "wide_camera_info",
        "kill_log",
        "center_kill",
        "center_notify",
        "player_detail",
        "detail_slot",
        "chat",
    }
    layouts = qa.get("layouts", {})
    check(set(layouts) == expected_layouts, "in-game HUD safe component inventory changed")
    for name in expected_layouts:
        record = layouts.get(name, {})
        validate_recorded_file(record, f"in-game HUD layout {name}")
        check(
            record.get("restored_native_sha256")
            == record.get("native_baseline_normalized_sha256"),
            f"in-game HUD {name} contains changes outside exact decorative insertions",
        )
        check(record.get("native_node_ids_preserved") is True, f"in-game HUD {name} changed a native node ID")
        expected_override = {
            "remapping": f"asset/lol_mod/ui/layout/ingame_component/{name}",
            "type": "override",
        }
        key = f"asset/base/ui/layout/ingame_component/{name}"
        check(override.get(key) == expected_override, f"in-game HUD override is missing or incorrect: {name}")
        path = MOD_ROOT / record.get("path", "missing")
        if path.is_file():
            source = path.read_text(encoding="utf-8")
            check("source/imagegen/" not in source, f"in-game HUD {name} references source-tree art")
            for node in record.get("overlay_nodes", []):
                marker = f"#{node}:image"
                check(marker in source, f"in-game HUD {name} is missing overlay {node}")
                if marker in source:
                    block = source.split(marker, 1)[1].split("}", 1)[0]
                    check("ignore_event: true;" in block, f"in-game HUD overlay accepts events: {node}")
                    check(
                        f'source: "asset/lol_mod/ui/ingame/{node}";' in block,
                        f"in-game HUD overlay does not use its packed runtime asset: {node}",
                    )

    expected_runtime_sizes = {
        "player_info_blue": [412, 40],
        "player_info_red": [352, 40],
        "wide_player_info_blue": [272, 30],
        "wide_player_info_red": [272, 30],
        "camera_info_blue": [449, 60],
        "camera_info_red": [449, 60],
        "wide_camera_info_blue": [300, 60],
        "wide_camera_info_red": [300, 60],
        "player_detail_blue": [393, 40],
        "player_detail_red": [393, 40],
        "kill_log": [130, 48],
        "center_kill": [600, 45],
        "center_notify": [600, 45],
        "detail_slot": [36, 36],
        "chat_icon": [30, 30],
    }
    runtime_assets = qa.get("runtime_assets", {})
    check(set(runtime_assets) == set(expected_runtime_sizes), "in-game HUD runtime asset inventory changed")
    for name, dimensions in expected_runtime_sizes.items():
        runtime = runtime_assets.get(name, {}).get("runtime", {})
        check(runtime.get("dimensions") == dimensions, f"in-game HUD {name} dimensions changed")
        validate_recorded_file(runtime, f"in-game HUD runtime {name}")
        check(
            str(runtime.get("path", "")).startswith("ui/ingame/lol_hud_")
            and "source/imagegen/" not in str(runtime.get("path", "")),
            f"in-game HUD {name} is not a packed runtime asset",
        )
        alpha = runtime.get("alpha", {})
        check(alpha.get("max", 255) < 255 and alpha.get("partial_pixels", 0) > 0, f"in-game HUD {name} lost translucency")

    sources = qa.get("imagegen_sources", {})
    for name in ("panel", "control"):
        validate_recorded_file(sources.get(name, {}), f"in-game HUD ImageGen source {name}")
    contact = qa.get("contact_sheet", {})
    check(contact.get("dimensions") == [1200, 700], "in-game HUD contact dimensions changed")
    validate_recorded_file(contact, "in-game HUD contact")

    skipped = {row.get("asset_key") for row in qa.get("skipped_contracts", [])}
    check("asset/base/ui/layout/ingame" in skipped, "dynamic in-game root skip is undocumented")
    check(
        "asset/base/aseprite_resources/ingame/minimap_5v5#sheet" in skipped
        and "asset/base/aseprite_resources/ingame/minimap_5v5#data" in skipped,
        "dynamic minimap skips are undocumented",
    )
    for key in (
        "asset/base/ui/layout/ingame",
        "asset/base/aseprite_resources/ingame/minimap_5v5#sheet",
        "asset/base/aseprite_resources/ingame/minimap_5v5#data",
    ):
        check(key not in override, f"visual-only HUD must not override unstable contract: {key}")

    manifest_path = MOD_ROOT / "build_manifest.json"
    if manifest_path.is_file():
        manifest_paths = {
            row.get("path") for row in load_json("build_manifest.json").get("files", [])
        }
        required_manifest_paths = {
            record.get("path") for record in layouts.values()
        } | {
            row.get("runtime", {}).get("path") for row in runtime_assets.values()
        }
        missing = sorted(path for path in required_manifest_paths if path not in manifest_paths)
        check(not missing, "in-game HUD runtime files are missing from build_manifest.json: " + ", ".join(missing))


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


def validate_native_dll() -> None:
    path = MOD_ROOT / "lol_mod.dll"
    check(path.is_file(), "lol_mod.dll is missing; run tools/build_native_dll.ps1")
    if not path.is_file() or sys.platform != "win32":
        return
    try:
        library = ctypes.WinDLL(str(path))
        api_version = library.tfm2_mod_api_version
        api_version.restype = ctypes.c_uint32
        exported = int(api_version())
    except (AttributeError, OSError) as error:
        check(False, f"failed to read lol_mod.dll API version: {error}")
        return
    check(
        exported == EXPECTED_MOD_API_VERSION,
        f"lol_mod.dll must export Mod API 0.{EXPECTED_MOD_API_VERSION}, got raw version 0x{exported:08x}",
    )


def validate_xayah_release(champion: dict[str, Any], override: dict[str, Any]) -> None:
    check(champion.get("id") == "dancer", "Xayah must retain official 007 id dancer")
    check(
        champion.get("sprite") == "asset/lol_mod/aseprite_resources/champions/xayah",
        "same-ID Xayah must bind the custom actor",
    )
    check(champion.get("anim_prefix") == "", "Xayah must preserve native Dancer animation tags")
    check(
        champion.get("skill_icons")
        == [
            "asset/lol_mod/icons/xayah_skill",
            "asset/lol_mod/icons/xayah_skill2",
            "asset/lol_mod/icons/xayah_ult",
        ],
        "Xayah active icon order must be Q/E/R",
    )
    check(
        [champion.get(slot, {}).get("action_name") for slot in ("attack", "skill", "skill2", "ult")]
        == ["attack", "skill1", "skill2", "ult"],
        "Xayah must map only attack/Q/E/R to native Dancer actions",
    )
    for unsupported in ("w", "skill3", "skill4"):
        check(unsupported not in champion, f"Xayah must not expose unsupported slot {unsupported}")
    check(not (MOD_ROOT / "champion/lol_xayah.data_champion").exists(), "Xayah must not register an additive duplicate")

    q = champion.get("skill", {})
    q_projectiles = find_effect(q, "LinearProjectile", name="lol_xayah_q_feather")
    check(len(q_projectiles) == 2, "Xayah Q must launch exactly two feather projectiles")
    for projectile in q_projectiles:
        check(
            (
                projectile.get("penetrate"),
                projectile.get("speed"),
                projectile.get("range"),
                projectile.get("shape"),
                projectile.get("applied_target"),
            )
            == (True, 8000, 72000, {"Circle": {"radius": 7000}}, "EnemyWithoutTower"),
            "Xayah Q projectile contract changed",
        )
        check(
            [(effect.get("damage"), effect.get("attack_ratio")) for effect in find_effect(projectile, "Attack")]
            == [(25, 45)],
            "each Xayah Q feather must deal 25 + 45% Attack once",
        )
        ground = find_effect(projectile.get("end_effects", []), "RangePeriodProjectile")
        check(
            ground
            == [{
                "type": "RangePeriodProjectile",
                "name": "lol_xayah_ground_single",
                "tick": 180,
                "period": 180,
                "first_delay": 0,
                "shape": {"Circle": {"radius": 1000}},
                "applied_target": "EnemyWithoutTower",
                "applied_effects": [],
                "end_effects": [],
            }],
            "each Xayah Q endpoint must leave one bounded visual-only Feather marker",
        )
    delayed = find_effect(q, "Delayed")
    check(len(delayed) == 1 and delayed[0].get("tick") == 6, "Xayah Q second feather must be delayed 6 ticks")
    check(
        not find_effect(q, "BackToCasterLinearProjectile")
        and not find_effect(q, "Bind")
        and not any(
            str(effect.get("name", "")).startswith(("lol_xayah_e_", "lol_xayah_r_"))
            for effect in walk_effects(q)
        ),
        "Xayah Q must stay outbound-only and must not embed E/R behavior",
    )

    e = champion.get("skill2", {})
    anchors = find_effect(e, "LinearProjectile", name="lol_xayah_e_anchor")
    recalls = [
        projectile
        for projectile in find_effect(e, "BackToCasterLinearProjectile")
        if str(projectile.get("name", "")).startswith("lol_xayah_e_recall_")
    ]
    roots = find_effect(e, "BackToCasterLinearProjectile", name="lol_xayah_e_third_feather_root")
    check(len(anchors) == 5 and all(anchor.get("applied_effects") == [] for anchor in anchors), "Xayah E must use five invisible no-damage anchors")
    check(len(recalls) == 5, "Xayah E must expose one recall branch for each feather tier")
    check(len(roots) == 3, "Xayah E must root only the 3/4/5-feather branches")
    check(
        all(root.get("applied_target") == "EnemyWithoutTower" for root in roots),
        "Xayah E third-Feather root must affect champions, minions, and monsters but not towers",
    )
    check(
        [projectile.get("name") for projectile in recalls]
        == [
            "lol_xayah_e_recall_cluster",
            "lol_xayah_e_recall_cluster",
            "lol_xayah_e_recall_cluster",
            "lol_xayah_e_recall_double",
            "lol_xayah_e_recall_single",
        ],
        "Xayah E 1/2/3+ Feather branches must keep distinct return silhouettes",
    )
    check(
        [bind.get("duration") for root in roots for bind in find_effect(root, "Bind")]
        == [45, 45, 45],
        "Xayah E center roots must last 45 ticks",
    )
    check(not find_effect(e, "RangePeriodProjectile"), "Xayah E must not own or respawn Q/R ground markers")
    check(
        len(find_effect(e, "Native", effect_ref="lol_xayah_ai_feather_clear")) == 1,
        "Xayah E must clear the native AI Feather-count mirror after an admitted cast",
    )

    ult = champion.get("ult", {})
    fans = find_effect(ult, "LinearProjectile", name="lol_xayah_r_fan")
    check(len(fans) == 1, "Xayah R must contain exactly one outbound fan collision")
    check(not find_effect(ult, "BackToCasterLinearProjectile") and not find_effect(ult, "Bind"), "Xayah R must not auto-cast Bladecaller")
    if len(fans) == 1:
        ground = find_effect(fans[0].get("end_effects", []), "RangePeriodProjectile")
        check(
            ground
            == [{
                "type": "RangePeriodProjectile",
                "name": "lol_xayah_ground_fan",
                "tick": 180,
                "period": 180,
                "first_delay": 0,
                "shape": {"Circle": {"radius": 1000}},
                "applied_target": "EnemyWithoutTower",
                "applied_effects": [],
                "end_effects": [],
            }],
            "Xayah R endpoint must leave one bounded visual-only aggregate five-Feather fan",
        )
    safety = [
        effect.get("buff_state", {})
        for effect in find_effect(ult, "AddCasterBuff")
        if effect.get("buff_state", {}).get("name") == "lol_xayah_r_safety_window"
    ]
    check(
        safety
        == [{
            "name": "lol_xayah_r_safety_window",
            "duration": {"Time": {"tick": 60}},
            "damaged_reduce": 100,
            "skill_damaged_reduce": 100,
            "cc_immune": True,
        }],
        "Xayah R safety-window approximation changed",
    )

    check(
        len(find_effect(champion.get("attack", {}), "Native", effect_ref="lol_xayah_ai_feather_add_1")) == 3
        and len(find_effect(q, "Native", effect_ref="lol_xayah_ai_feather_add_2")) == 1
        and len(find_effect(ult, "Native", effect_ref="lol_xayah_ai_feather_set_5")) == 1,
        "Xayah Q/R/Clean Cuts must update the bounded native AI Feather-count mirror",
    )
    runtime_source = (MOD_ROOT / "src/lib.rs").read_text(encoding="utf-8")
    for token in (
        "const XAYAH_AI_MIN_RECALL_FEATHERS: u8 = 2;",
        "struct XayahFeatherUnitState",
        "unit: EntityHandle",
        "state.count.saturating_add(amount).min(5)",
        "let Some(Input::Skill2 { target }) = base_input else",
        "if feather_count >= XAYAH_AI_MIN_RECALL_FEATHERS",
        "registration.add_player_input_ai(XayahFeatherInputGate);",
    ):
        check(token in runtime_source, f"Xayah AI Bladecaller gate is missing: {token}")

    actor_path = MOD_ROOT / "aseprite_resources/champions/xayah#sheet.png"
    anim_path = MOD_ROOT / "aseprite_resources/champions/xayah#anim.fanim"
    check(actor_path.is_file() and anim_path.is_file(), "Xayah actor resources are missing")
    if actor_path.is_file() and anim_path.is_file():
        actor = Image.open(actor_path).convert("RGBA")
        anims = load_json("aseprite_resources/champions/xayah#anim.fanim").get("anims", {})
        expected_counts = {
            "ult": 5, "idle": 4, "run": 8, "projectile": 1, "hit": 1,
            "attack": 5, "skill1_projectile": 2, "dead": 10, "skill1": 5, "skill2": 3,
        }
        check(actor.size == (1594, 90), f"Xayah actor must preserve native 1594x90 canvas, got {actor.size}")
        check(list(anims) == list(expected_counts), "Xayah actor tag order changed native Dancer contract")
        run_hashes: set[str] = set()
        for tag, expected_count in expected_counts.items():
            frames = anims.get(tag, {}).get("frames", [])
            check(len(frames) == expected_count, f"Xayah native tag {tag} frame count changed")
            for index, frame in enumerate(frames):
                data = frame.get("data", {})
                x, y, width, height = (int(data.get(key, 0)) for key in ("x", "y", "w", "h"))
                in_bounds = width > 0 and height > 0 and x >= 0 and y >= 0 and x + width <= actor.width and y + height <= actor.height
                check(in_bounds, f"Xayah {tag} frame {index} is out of bounds")
                if not in_bounds:
                    continue
                frame_image = actor.crop((x, y, x + width, y + height))
                bbox = frame_image.getchannel("A").getbbox()
                if tag == "dead" and index == expected_count - 1:
                    check(bbox is None, "Xayah dead terminal frame must remain transparent")
                else:
                    check(bbox is not None, f"Xayah {tag} frame {index} is empty")
                if tag == "run":
                    run_hashes.add(hashlib.sha256(frame_image.tobytes()).hexdigest())
        check(len(run_hashes) >= 6, "Xayah run must retain at least six distinct phases")

    for relative in ("icons/xayah_skill.png", "icons/xayah_skill2.png", "icons/xayah_ult.png"):
        path = MOD_ROOT / relative
        check(path.is_file() and Image.open(path).size == (64, 64), f"{relative} must be a 64x64 icon")
    for effect_name, tags in {
        "xayah_attack": {"projectile": 4, "hit": 4},
        "xayah_q": {"projectile": 4, "hit": 4},
        "xayah_e": {
            "return_single": 4,
            "return_double": 4,
            "return_cluster": 4,
            "root": 4,
            "hit": 4,
        },
        "xayah_r": {"fan": 4, "hit": 4, "guard": 4},
        "xayah_ground_feather": {"ground_single": 4, "ground_fan": 4},
    }.items():
        check((MOD_ROOT / f"aseprite_resources/effects/{effect_name}#sheet.png").is_file(), f"missing {effect_name} VFX sheet")
        fanim = MOD_ROOT / f"aseprite_resources/effects/{effect_name}#anim.fanim"
        check(fanim.is_file(), f"missing {effect_name} VFX animation")
        if fanim.is_file():
            actual = {tag: len(value.get("frames", [])) for tag, value in load_json(f"aseprite_resources/effects/{effect_name}#anim.fanim").get("anims", {}).items()}
            check(actual == tags, f"{effect_name} VFX tag/frame contract changed")
            expected_sizes = {
                "xayah_e": {
                    "return_single": (64, 32), "return_double": (72, 36),
                    "return_cluster": (80, 44), "root": (72, 72), "hit": (48, 48),
                },
                "xayah_r": {"fan": (104, 72), "hit": (96, 72), "guard": (72, 72)},
                "xayah_ground_feather": {"ground_single": (48, 40), "ground_fan": (72, 48)},
            }.get(effect_name, {})
            if expected_sizes:
                animations = load_json(f"aseprite_resources/effects/{effect_name}#anim.fanim").get("anims", {})
                for tag, expected_size in expected_sizes.items():
                    sizes = {
                        (int(frame.get("data", {}).get("w", 0)), int(frame.get("data", {}).get("h", 0)))
                        for frame in animations.get(tag, {}).get("frames", [])
                    }
                    check(sizes == {expected_size}, f"{effect_name}/{tag} VFX footprint changed: {sizes}")
            if effect_name == "xayah_ground_feather":
                sheet = Image.open(MOD_ROOT / f"aseprite_resources/effects/{effect_name}#sheet.png").convert("RGBA")
                for tag, value in load_json(f"aseprite_resources/effects/{effect_name}#anim.fanim").get("anims", {}).items():
                    frames = value.get("frames", [])
                    if not frames:
                        continue
                    data = frames[-1].get("data", {})
                    x, y, width, height = (int(data.get(key, 0)) for key in ("x", "y", "w", "h"))
                    terminal = sheet.crop((x, y, x + width, y + height))
                    check(terminal.getchannel("A").getbbox() is None, f"Xayah {tag} marker must end transparent")

    projectiles = {view.get("name"): view for view in champion.get("view_projectiles", [])}
    for name, tag in {
        "lol_xayah_e_recall_single": "return_single",
        "lol_xayah_e_recall_double": "return_double",
        "lol_xayah_e_recall_cluster": "return_cluster",
    }.items():
        view = projectiles.get(name, {})
        check(
            view.get("anim") == "asset/lol_mod/aseprite_resources/effects/xayah_e"
            and view.get("tag") == tag,
            f"{name} must use the dedicated Xayah E {tag} visual",
        )
    for name, tag in {
        "lol_xayah_ground_single": "ground_single",
        "lol_xayah_ground_fan": "ground_fan",
    }.items():
        view = projectiles.get(name, {})
        check(
            view.get("anim") == "asset/lol_mod/aseprite_resources/effects/xayah_ground_feather"
            and view.get("tag") == tag
            and view.get("repeat") is False,
            f"{name} must use a non-repeating bounded ground-Feather animation",
        )
    views = {view.get("name"): view for view in champion.get("view_effects", [])}
    check(
        views.get("lol_xayah_r_guard_visual", {}).get("anim")
        == "asset/lol_mod/aseprite_resources/effects/xayah_r"
        and views.get("lol_xayah_r_guard_visual", {}).get("tag") == "guard",
        "Xayah R safety window must use the dedicated guard visual, not the outbound fan",
    )

    text = load_json("text/champion.i18n")
    for locale, name in {"en": "Xayah", "zh-hans": "霞", "zh-hant": "剎雅", "ja": "ザヤ", "ko": "자야"}.items():
        description = text.get(locale, {}).get("description", {}).get("dancer", {})
        check(description.get("name") == name, f"{locale} Xayah name is missing")
        for key, letter in (("skill", "Q"), ("skill2", "E"), ("ult", "R")):
            check(str(description.get(key, "")).startswith(letter), f"{locale} Xayah {key} must be labeled {letter}")
    style = load_json("style/champion_view.champion_view").get("entries", {}).get("dancer", {})
    check(style == {"face": {"x": 2, "y": -32}, "center": {"x": 0, "y": -12}}, "Xayah compact/card camera contract changed")
    check(Image.open(MOD_ROOT / "BanPickIllust/dancer.png").size == (1420, 860), "Xayah BP splash must be 1420x860")
    check(Image.open(MOD_ROOT / "ui/champion_fullbody/dancer.png").size == (64, 64), "Xayah encyclopedia portrait must be 64x64")
    rust = (MOD_ROOT / "src/lib.rs").read_text(encoding="utf-8")
    for required_route in (
        "rewrite_xayah_portrait_render_commands(state);",
        "XAYAH_COMPACT_PORTRAIT_TEXTURE",
        "XAYAH_BP_GRID_PORTRAIT_TEXTURE",
        '"asset/base/aseprite_resources/champions/dancer#sheet"',
        '"asset/lol_mod/aseprite_resources/champions/xayah#sheet"',
        "(50.0..=58.0).contains(w)",
        "(88.0..=100.0).contains(h)",
    ):
        check(required_route in rust, f"Xayah portrait runtime route is missing: {required_route}")
    for relative, expected_size in (
        ("ui/champion_portrait/dancer_compact.png", (64, 64)),
        ("ui/champion_portrait/dancer_grid.png", (90, 122)),
    ):
        portrait_path = MOD_ROOT / relative
        check(portrait_path.is_file(), f"Xayah portrait is missing: {relative}")
        if portrait_path.is_file():
            portrait = Image.open(portrait_path).convert("RGBA")
            bbox = portrait.getchannel("A").getbbox()
            check(portrait.size == expected_size, f"Xayah portrait size changed: {relative}={portrait.size}")
            check(bbox is not None, f"Xayah portrait is empty: {relative}")
            check(portrait.getchannel("A").getextrema() == (0, 255), f"Xayah portrait must use hard alpha: {relative}")
            if relative.endswith("dancer_compact.png") and bbox is not None:
                check(bbox[2] - bbox[0] <= 50, f"Xayah compact portrait is too wide: {bbox}")
                check(bbox[3] - bbox[1] <= 50, f"Xayah compact portrait is too tall: {bbox}")
                check(
                    min(bbox[0], bbox[1], 64 - bbox[2], 64 - bbox[3]) >= 6,
                    f"Xayah compact portrait lacks 6px safety margins: {bbox}",
                )
            if relative.endswith("dancer_grid.png") and bbox is not None:
                check(bbox[3] <= 86, f"Xayah BP-grid portrait lacks the 10px hero-name-band gap: {bbox}")

    scale_qa = load_json("qa/xayah_ui_scale_qa.json")
    actor_scale = scale_qa.get("actor_scale", {})
    mean_ratio = float(actor_scale.get("mean_height_scale_ratio", 0.0))
    median_ratio = float(actor_scale.get("median_height_scale_ratio", 0.0))
    check(1.12 <= mean_ratio <= 1.15, f"Xayah mean actor enlargement changed: {mean_ratio}")
    check(1.12 <= median_ratio <= 1.16, f"Xayah median actor enlargement changed: {median_ratio}")
    check(int(actor_scale.get("minimum_bottom_clearance", 0)) >= 4, "Xayah actor lost foot clearance")
    check(
        actor_scale.get("q_e_r_sources")
        == {
            "Q": "source/processed/xayah_q_body_contact_v2_alpha.png",
            "E": "source/processed/xayah_e_body_contact_v2_alpha.png",
            "R": "source/processed/xayah_r_body_contact_v2_alpha.png",
        },
        "Xayah Q/E/R actor contacts are no longer independent",
    )

    audit = load_json("qa/xayah_official_audio_sources.json")
    outputs = audit.get("outputs", [])
    check(len(outputs) == 10, "Xayah official audio audit must pin ten events")
    required_manifest_paths = {
        "champion/dancer.data_champion", "aseprite_resources/champions/xayah#sheet.png",
        "aseprite_resources/champions/xayah#anim.fanim", "icons/xayah_skill.png",
        "icons/xayah_skill2.png", "icons/xayah_ult.png", "BanPickIllust/dancer.png",
        "ui/champion_fullbody/dancer.png", "ui/champion_portrait/dancer_compact.png",
        "ui/champion_portrait/dancer_grid.png", "qa/xayah_ui_scale_qa.json",
        "qa/xayah_portrait_surface_final.png", "qa/xayah_imagegen_sources.json",
        "qa/xayah_official_audio_sources.json", "sound/sfx/xayah_native_silence.sound_info",
        "sound/sfx/xayah_native_silence_clip.wav",
    }
    for row in outputs:
        event_key = row.get("event_key", "")
        check(float(row.get("volume", 0.0)) == 1.0, f"{event_key} must use the audited full volume")
        check(row.get("media_id") in row.get("event_media_pool", []), f"{event_key} selected media is outside its event pool")
        sound_info = MOD_ROOT / row.get("sound_info", "missing")
        wav_info = row.get("wav", {})
        wav_path = MOD_ROOT / wav_info.get("path", "missing")
        check(sound_info.is_file() and wav_path.is_file(), f"missing Xayah audio output for {event_key}")
        required_manifest_paths.update({row.get("sound_info", ""), wav_info.get("path", "")})
        if wav_path.is_file():
            check(sha256(wav_path) == wav_info.get("sha256"), f"{event_key} WAV hash changed")
            try:
                with wave.open(str(wav_path), "rb") as decoded:
                    check((decoded.getnchannels(), decoded.getsampwidth(), decoded.getframerate()) == (1, 2, 44100), f"{event_key} WAV must be mono PCM16 44.1kHz")
            except wave.Error as error:
                check(False, f"{event_key} WAV cannot be decoded: {error}")
        runtime_event = row.get("runtime_event", "")
        if runtime_event:
            check(f"asset/base/sound/sfx/{runtime_event}" in override, f"missing Xayah event override {runtime_event}")
    for native in ("dancer_attack", "dancer_skill1", "dancer_skill2", "dancer_ult"):
        check(override.get(f"asset/base/sound/sfx/{native}", {}).get("remapping") == "asset/lol_mod/sound/sfx/xayah_native_silence", f"native Dancer event is not isolated: {native}")
    for native in ("dancer_attack0", "dancer_skill_resource", "dancer_skill2_resource", "dancer_ult_resource"):
        check(override.get(f"asset/base/sound/sfx/{native}", {}).get("remapping") == "asset/lol_mod/sound/sfx/xayah_native_silence_clip", f"native Dancer clip is not isolated: {native}")

    imagegen = load_json("qa/xayah_imagegen_sources.json")
    check(imagegen.get("generator") == "built-in image_gen", "Xayah ImageGen provenance is missing")
    check(imagegen.get("prompt_record") == "source/imagegen/PROMPTS.md#xayah-image-gen-prompts", "Xayah prompt record is missing")
    check(len(imagegen.get("sources", [])) == 16 and len(imagegen.get("processed", [])) == 12, "Xayah ImageGen source set is incomplete")
    check(
        all("xayah_idle_contact_v2" not in row.get("path", "") for row in imagegen.get("sources", [])),
        "removed Xayah idle v2 source must not remain active provenance",
    )
    check(
        all("xayah_idle_contact_v2" not in row.get("path", "") for row in imagegen.get("processed", [])),
        "removed Xayah idle v2 alpha must not remain active provenance",
    )
    check(
        imagegen.get("additional_generated_images")
        == [
            {
                "role": "idle_body_contact_v3_two_eyes",
                "execution_id": "exec-14c8a307-6e2b-4821-859a-9f62c5e391ef",
            },
            {
                "role": "ground_feather_vfx_v1",
                "execution_id": "exec-178182ff-7735-4228-b339-62352f37295c",
            },
        ],
        "Xayah corrective ImageGen executions are not pinned",
    )
    for row in [*imagegen.get("sources", []), *imagegen.get("processed", [])]:
        path = MOD_ROOT / row.get("path", "missing")
        check(path.is_file(), f"missing Xayah ImageGen source: {row.get('path')}")
        if path.is_file():
            check(sha256(path) == row.get("sha256"), f"Xayah ImageGen source hash changed: {row.get('path')}")

    for effect_name in ("xayah_attack", "xayah_q", "xayah_e", "xayah_r", "xayah_ground_feather"):
        required_manifest_paths.update({f"aseprite_resources/effects/{effect_name}#sheet.png", f"aseprite_resources/effects/{effect_name}#anim.fanim"})
    manifest_paths = {row.get("path") for row in load_json("build_manifest.json").get("files", [])}
    missing = sorted(path for path in required_manifest_paths if path and path not in manifest_paths)
    check(not missing, "Xayah runtime resources are missing from build_manifest.json: " + ", ".join(missing))


def validate_urgot_w(champion: dict[str, Any]) -> None:
    """Gate crash-safe Urgot W and the pure-data E flip implementation."""

    w = champion.get("skill", {})
    check(
        (
            w.get("action_name"),
            w.get("cooltime"),
            w.get("duration"),
            w.get("start_timing"),
            w.get("cancelable"),
            w.get("range"),
            w.get("casting_type"),
            w.get("casting_target"),
            w.get("can_use_with_move"),
        )
        == ("attack", 600, 16, 1, False, 60000, "Targeting", "EnemyWithoutTower", False),
        "Urgot W must be a non-cancelable 16-tick targeted pure-data action",
    )
    w_effects = list(walk_effects(w))
    w_types = [str(effect.get("type", "")) for effect in w_effects]
    check(not any("Projectile" in effect_type for effect_type in w_types), "Urgot W must contain no projectile variant")
    check("RangePeriod" not in w_types and "RangePeriodProjectile" not in w_types, "Urgot W must contain no periodic range entity")
    check("AddCasted" not in w_types, "Urgot W must not reuse AddCasted/Bleed")
    check("Delayed" not in w_types, "Urgot W must contain no delayed scheduler callback")
    check("Native" not in w_types, "Urgot W must contain no native callback")
    for visual_type in ("CasterAnimation", "CasterViewEffect", "ViewEffect", "TargetSfx"):
        check(visual_type not in w_types, f"Urgot W must not render the rejected body/target visual: {visual_type}")

    attacks = find_effect(w, "Attack")
    check(
        attacks == [{"type": "Attack", "damage": 96, "attack_ratio": 240}],
        "Urgot W must compress the rejected twelve-pulse route into one 96 + 240% Attack hit",
    )
    check(
        find_effect(w, "Sfx")
        == [
            {"type": "Sfx", "name": "lol_urgot_w_cast"},
            {"type": "Sfx", "name": "lol_urgot_w_shot"},
        ],
        "Urgot W must retain exactly one cast cue and one immediate shot cue",
    )
    caster_buffs = find_effect(w, "AddCasterBuff")
    check(
        len(caster_buffs) == 1
        and caster_buffs[0].get("buff_state")
        == {
            "name": "lol_urgot_w_purge",
            "duration": {"Time": {"tick": 240}},
            "move_speed_mult": -12,
            "defence": 20,
            "magic_resistance": 10,
        },
        "Urgot W must retain only the four-second Purge self buff",
    )

    runtime_views = [*champion.get("view_projectiles", []), *champion.get("view_effects", [])]
    check(
        all(not str(view.get("name", "")).startswith("lol_urgot_w_") for view in runtime_views),
        "Urgot W runtime projectile/impact bindings must be removed",
    )
    check(
        all("urgot_w_cannon" not in str(view.get("anim", "")) for view in runtime_views),
        "Urgot W cannon sheet must not be reachable from runtime champion bindings",
    )
    check(not champion.get("view_buffs"), "Urgot W must not add a body-covering view buff")

    e = champion.get("skill2", {})
    check(
        (
            e.get("action_name"),
            e.get("cooltime"),
            e.get("duration"),
            e.get("range"),
            e.get("casting_type"),
            e.get("casting_target"),
        )
        == ("transform", 420, 30, 45000, "Targeting", "EnemyChampion"),
        "Urgot E timing or targeted champion contract changed",
    )
    e_rushes = find_effect(e, "RushMoveToBack")
    check(len(e_rushes) == 1, "Urgot E must contain exactly one RushMoveToBack")
    if e_rushes:
        rush = e_rushes[0]
        check(rush.get("speed") == 4500, "Urgot E RushMoveToBack speed must be 4500")
        check(
            rush.get("applied_effects")
            == [
                {"type": "Attack", "damage": 70, "attack_ratio": 90},
                {"type": "Knockback", "speed": 2600, "tick": 8},
                {"type": "Airborne", "duration": 60},
                {"type": "ViewEffect", "name": "lol_urgot_e_flip_visual"},
                {"type": "TargetSfx", "name": "lol_urgot_e_hit"},
            ],
            "Urgot E must cross the target, then use the proven Knockback/Airborne flip order",
        )
    check(not find_effect(e, "Native"), "Urgot E must not apply native Stun before displacement")
    check(not find_effect(e, "Delayed"), "Urgot E flip must not retain a delayed target callback")
    check(not find_effect(e, "Grab"), "Urgot E must throw past Urgot instead of pulling onto his body")

    rust = (MOD_ROOT / "src/lib.rs").read_text(encoding="utf-8")
    for retired_rust_token in (
        "struct UrgotAbilityInputGate",
        "impl ModPlayerInputAi for UrgotAbilityInputGate",
        "registration.add_player_input_ai(UrgotAbilityInputGate);",
        '"lol_urgot_ability_input_gate"',
        "struct UrgotWPulseNativeEffect",
        "impl ModEffectType for UrgotWPulseNativeEffect",
        '"lol_urgot_w_pulse_native"',
        "URGOT_W_RANGE",
        "URGOT_W_FLAT_DAMAGE",
        "URGOT_W_ATTACK_RATIO_PERCENT",
        "struct UrgotENativeEffect",
        "impl ModEffectType for UrgotENativeEffect",
        '"lol_urgot_e_native"',
        "URGOT_E_STUN_TICKS",
    ):
        check(retired_rust_token not in rust, f"Urgot crash route must be removed from Rust: {retired_rust_token}")

    def urgot_impl_block(start_marker: str, end_marker: str, label: str) -> str:
        start = rust.find(start_marker)
        end = rust.find(end_marker, start + len(start_marker)) if start >= 0 else -1
        check(start >= 0 and end > start, f"Urgot {label} native implementation is missing")
        return rust[start:end] if start >= 0 and end > start else ""

    passive_rust = urgot_impl_block(
        "impl ModEffectType for UrgotPassiveNativeEffect {",
        "struct UrgotRCheckNativeEffect;",
        "passive",
    )
    passive_tokens = (
        ".map(|caster| (caster.handle(), caster.stat().attack, caster.is_alive()))",
        "if !caster_alive",
        ".map(|target| (target.hp().max, target.is_alive()))",
        "if !target_alive || target_max_hp == 0",
    )
    passive_positions = [passive_rust.find(token) for token in passive_tokens]
    check(
        all(position >= 0 for position in passive_positions)
        and passive_positions == sorted(passive_positions),
        "Urgot passive must reacquire alive caster/target snapshots after the base Attack",
    )
    if passive_positions and all(position >= 0 for position in passive_positions):
        guards_end = passive_positions[-1]
        for mutation in (
            "cooldown.ready_tick = now.saturating_add",
            "cooldowns.push(UrgotPassiveCooldown",
            "ctx.deal_damage(caster_id, target_id, damage, 0, AttackType::Skill);",
        ):
            check(
                passive_rust.find(mutation) > guards_end,
                f"Urgot passive must validate both live entities before {mutation}",
            )

    r_check_rust = urgot_impl_block(
        "impl ModEffectType for UrgotRCheckNativeEffect {",
        "struct UrgotRExecuteNativeEffect;",
        "R threshold check",
    )
    r_check_positions = [
        r_check_rust.find("if target_hp.current > execute_limit"),
        r_check_rust.find(".get_entity(caster_id)"),
        r_check_rust.find(".is_some_and(|caster| caster.is_alive())"),
        r_check_rust.find('ready.name = "lol_urgot_r_execute_ready"'),
        r_check_rust.find("ctx.add_buff(caster_id, ready);"),
    ]
    check(
        all(position >= 0 for position in r_check_positions)
        and r_check_positions == sorted(r_check_positions),
        "Urgot R check must verify a live caster immediately before its ready marker",
    )

    r_execute_rust = urgot_impl_block(
        "impl ModEffectType for UrgotRExecuteNativeEffect {",
        "\nconst SHEN_SHADOW_DASH_TAUNT_TICKS",
        "R execute",
    )
    caster_lookup = ".get_entity(caster_id)"
    caster_alive = ".is_some_and(|caster| caster.is_alive())"
    first_lookup = r_execute_rust.find(caster_lookup)
    second_lookup = r_execute_rust.find(caster_lookup, first_lookup + 1)
    first_alive = r_execute_rust.find(caster_alive)
    second_alive = r_execute_rust.find(caster_alive, first_alive + 1)
    r_execute_positions = [
        first_lookup,
        first_alive,
        r_execute_rust.find(
            "ctx.deal_damage(caster_id, target_id, lethal_damage, 0, AttackType::Skill);"
        ),
        r_execute_rust.find(".is_some_and(|target| !target.is_alive())"),
        r_execute_rust.find("if !executed"),
        second_lookup,
        second_alive,
        r_execute_rust.find('success.name = "lol_urgot_r_execute_success"'),
        r_execute_rust.find("ctx.add_buff(caster_id, success);"),
    ]
    check(
        r_execute_rust.count(caster_lookup) == 2
        and r_execute_rust.count(caster_alive) == 2
        and all(position >= 0 for position in r_execute_positions)
        and r_execute_positions == sorted(r_execute_positions),
        "Urgot R execute must verify the caster before damage and again before its success marker",
    )

    text = load_json("text/champion.i18n")
    required_copy = {
        "en": ("one valid non-tower enemy", "96 + 240% Attack", "chosen direction", "reacquires", "12 rapid pulses"),
        "zh-hans": ("一个合法的非防御塔敌人", "96 + 240%攻击力", "选定方向", "重新搜寻", "快速攻击12次"),
        "zh-hant": ("一個合法的非防禦塔敵人", "96 + 240%攻擊力", "選定方向", "重新搜尋", "快速攻擊12次"),
        "ja": ("有効なタワー以外の敵1体", "96 + 攻撃力の240%", "指定方向", "探し直す", "計12回"),
        "ko": ("유효한 포탑이 아닌 적 하나", "96 + 공격력의 240%", "지정한 방향", "다시 찾습니다", "총 12회의"),
    }
    for locale, (target_copy, damage_copy, retired_direction_copy, retired_reacquire_copy, retired_pulse_copy) in required_copy.items():
        skill_copy = str(text.get(locale, {}).get("description", {}).get("demon", {}).get("skill", ""))
        check(target_copy in skill_copy and damage_copy in skill_copy, f"Urgot W {locale} copy must describe the compressed single hit")
        check(retired_direction_copy not in skill_copy, f"Urgot W {locale} copy still describes the rejected direction route")
        check(retired_pulse_copy not in skill_copy and retired_reacquire_copy not in skill_copy, f"Urgot W {locale} copy still describes the rejected pulse scheduler")


def main() -> int:
    champion = load_json("champion/lol_shen.data_champion")
    lucian = load_json("champion/archer.data_champion")
    orianna = load_json("champion/barrier_magician.data_champion")
    briar = load_json("champion/berserker.data_champion")
    sivir = load_json("champion/boomerang_hunter.data_champion")
    kled = load_json("champion/cavalry_knight.data_champion")
    xayah = load_json("champion/dancer.data_champion")
    urgot = load_json("champion/demon.data_champion")
    override = load_json("mod.override_info")
    mod_info = load_json("mod.mod_info")
    check(mod_info.get("version") == "0.10.9", "lol_mod version must be 0.10.9")
    validate_objective_killfeed_names(override)
    discovered_overrides, total_overrides = validate_override_asset_discoverability(override)
    validate_quality_nexus_assets(override)
    validate_objective_and_wolf_motion_qa()
    validate_quality_map_and_bp_skin(override)
    validate_quality_ingame_hud(override)
    validate_data_contract(champion)
    validate_shen_sdk_data_champion()
    validate_lucian_data_contract(lucian)
    validate_orianna_replacement_uniqueness()
    validate_orianna_data_contract(orianna)
    validate_orianna_native_animation(orianna)
    validate_orianna_v2_visual_contract()
    validate_orianna_resources_and_manifest(orianna)
    validate_briar_replacement_uniqueness()
    validate_briar_data_contract(briar)
    validate_briar_native_animation_and_actor(briar)
    validate_briar_resources_and_manifest(briar)
    validate_orianna_briar_hd_surfaces()
    validate_sivir_replacement_uniqueness()
    validate_sivir_data_contract(sivir)
    validate_sivir_native_animation_and_resources(sivir)
    validate_sivir_hd_surfaces()
    validate_kled_replacement_uniqueness()
    validate_kled_data_contract(kled)
    validate_kled_native_animation_and_resources(kled)
    validate_kled_localization_style_and_surfaces()
    validate_animation(
        "aseprite_resources/champions/shen#sheet.png",
        "aseprite_resources/champions/shen#anim.fanim",
        {"idle": 7, "run": 9, "attack": 6, "skill": 7, "skill2": 5, "ult": 5, "hit": 1, "dead": 1},
    )
    validate_animation(
        "aseprite_resources/effects/shen_q#sheet.png",
        "aseprite_resources/effects/shen_q#anim.fanim",
        {"outbound": 8, "return": 8, "empowered_hit": 4, "through_hit": 5, "pass_through": 4},
    )
    validate_animation(
        "aseprite_resources/effects/shen_e#sheet.png",
        "aseprite_resources/effects/shen_e#anim.fanim",
        {
            "dash": 3,
            "impact": 3,
            "trail_pre": 1,
            "trail_loop": 2,
            "trail_remove": 1,
            "taunt_pre": 1,
            "taunt_loop": 1,
            "taunt_remove": 1,
        },
    )
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
    validate_compact_view_and_e_layout()
    validate_native_lucian_localization()
    validate_orianna_localization()
    validate_briar_localization_and_style()
    validate_sivir_localization_and_style()
    validate_audio(champion, override)
    validate_lucian_audio(lucian, override)
    validate_orianna_audio(orianna, override)
    validate_briar_audio(briar, override)
    validate_sivir_audio(sivir, override)
    validate_kled_audio(kled, override)
    validate_xayah_release(xayah, override)
    validate_urgot_w(urgot)
    validate_briar_imagegen_and_qa_files()
    validate_sivir_imagegen_and_qa_files()
    validate_imagegen_sources()
    validate_native_dll()
    validate_manifest()
    if ERRORS:
        print(f"Override asset discoverability: {discovered_overrides}/{total_overrides}")
        print("League champion pack validation failed:")
        for error in ERRORS:
            print(f"- {error}")
        return 1
    print(f"Override asset discoverability: {discovered_overrides}/{total_overrides}")
    print("League champion pack validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
