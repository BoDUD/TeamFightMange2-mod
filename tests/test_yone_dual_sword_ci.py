from __future__ import annotations

import copy
import importlib.util
import json
import math
import sys
from pathlib import Path
from typing import Any, Iterable

import pytest
from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
MOD = ROOT / "mods/lol_mod"
VALIDATOR_PATH = MOD / "tools/validate_yone_v7.py"
FRAME_MANIFEST = MOD / "source/native/yone_v7/frames.json"
ACTOR_ANIM = MOD / "aseprite_resources/champions/yone_v7#anim.fanim"
ACTOR_SHEET = MOD / "aseprite_resources/champions/yone_v7#sheet.png"
LEGACY_ACTOR_ANIM = MOD / "aseprite_resources/champions/yone#anim.fanim"
LEGACY_ACTOR_SHEET = MOD / "aseprite_resources/champions/yone#sheet.png"
DATA_CHAMPION = MOD / "champion/dual_blader.data_champion"

WEAPON_GEOMETRY_SUFFIXES = (
    "blade_bbox",
    "hand_anchor",
    "tip",
    "span_px",
    "connectedness",
    "pixel_count",
    "crop_ratio",
    "source_tip_survived",
)
WEAPON_GEOMETRY_FIELDS = {
    f"{weapon}_{suffix}"
    for weapon in ("steel", "azakana")
    for suffix in WEAPON_GEOMETRY_SUFFIXES
}
EXCLUSIVE_WEAPON_ROLES = {
    "steel_dark",
    "steel_mid",
    "steel_highlight",
    "azakana_dark",
    "azakana_red",
    "azakana_highlight",
}
GEOMETRY_ACTIONS = {
    "skill2",
    "hit",
    "idle",
    "run",
    "attack",
    "attack_azakana",
    "skill2_dash",
    "skill",
    "skill_q3",
    "skill2_attack",
    "ult",
    "dead",
}
EXPECTED_WEAPON_PALETTE_ROLES = {
    "steel": {
        "dark": ["steel_dark"],
        "mid": ["steel_mid"],
        "highlight": ["steel_highlight"],
    },
    "azakana": {
        "dark": ["azakana_dark"],
        "red": ["azakana_red"],
        "highlight": ["azakana_highlight"],
    },
}
EXPECTED_WEAPON_CONTRACT = {
    "version": 2,
    "weapons": ["steel", "azakana"],
    "always_dual_actions": ["idle", "run"],
    "semantic_animation_tags": {
        "attack_steel": "steel",
        "attack_azakana": "azakana",
        "skill_q12": "steel",
        "skill_q3": "steel",
        "skill_w_azakana": "azakana",
        "ult": "dual",
    },
    "long_blade_overlay_policy": (
        "caster-follow effects extend the active blade outside the compact actor frame"
    ),
}
EXPECTED_ACTIVE_WEAPON_BY_ACTION = {
    "skill2": "azakana",
    "hit": "dual",
    "attack": "steel",
    "attack_azakana": "azakana",
    "skill2_dash": "dual",
    "ult": "dual",
    "run": "dual",
    "skill2_attack": "azakana",
    "idle": "dual",
    "dead": "dual",
    "skill": "steel",
    "skill_q3": "steel",
}


def _load_validator():
    spec = importlib.util.spec_from_file_location(
        "validate_yone_v7_dual_sword_ci", VALIDATOR_PATH
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _rect_signature(animation: dict[str, object]) -> list[tuple[int, int, int, int]]:
    return [
        (
            frame["data"]["x"],
            frame["data"]["y"],
            frame["data"]["w"],
            frame["data"]["h"],
        )
        for frame in animation["frames"]
    ]


def _walk_effects(value: object) -> Iterable[dict[str, Any]]:
    if isinstance(value, dict):
        if isinstance(value.get("type"), str):
            yield value
        for child in value.values():
            yield from _walk_effects(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_effects(child)


def _load_raw_contract() -> tuple[dict[str, Any], dict[str, Any]]:
    payload = json.loads(FRAME_MANIFEST.read_text(encoding="utf-8"))
    palette_payload = json.loads(
        (FRAME_MANIFEST.parent / payload["palette_file"]).read_text(encoding="utf-8")
    )
    return payload, palette_payload


def _load_geometry_contract():
    validator = _load_validator()
    payload, palette_payload = _load_raw_contract()
    palette_path = FRAME_MANIFEST.parent / payload["palette_file"]
    palette = validator.load_palette(palette_path)
    rows_by_key = {
        (row["action"], row["index"]): copy.deepcopy(row)
        for row in payload["frames"]
    }
    sources: dict[tuple[str, int], Image.Image] = {}
    for row in payload["frames"]:
        with Image.open(FRAME_MANIFEST.parent / row["file"]) as opened:
            sources[(row["action"], row["index"])] = opened.convert("RGBA")
    return validator, payload, palette_payload, palette, rows_by_key, sources


def _weapon_colors(
    validator: Any, palette: Any, weapon: str
) -> frozenset[tuple[int, int, int, int]]:
    assert validator.EXPECTED_WEAPON_PALETTE_ROLES == EXPECTED_WEAPON_PALETTE_ROLES
    roles = EXPECTED_WEAPON_PALETTE_ROLES[weapon]
    return frozenset(
        color
        for ramp_roles in roles.values()
        for role in ramp_roles
        for color in palette.exact_role(role)
    )


def _erase_colors(
    image: Image.Image, colors: frozenset[tuple[int, int, int, int]]
) -> None:
    for y in range(image.height):
        for x in range(image.width):
            if image.getpixel((x, y)) in colors:
                image.putpixel((x, y), (0, 0, 0, 0))


def _count_colors(
    image: Image.Image, colors: frozenset[tuple[int, int, int, int]]
) -> int:
    getter = getattr(image, "get_flattened_data", None)
    pixels = getter() if getter is not None else image.getdata()
    return sum(pixel in colors for pixel in pixels)


def _copy_sources(
    sources: dict[tuple[str, int], Image.Image],
) -> dict[tuple[str, int], Image.Image]:
    return {key: image.copy() for key, image in sources.items()}


def test_v7_keeps_native_prefix_and_adds_semantic_dual_sword_tags() -> None:
    validator = _load_validator()
    assert ACTOR_ANIM.read_bytes() == LEGACY_ACTOR_ANIM.read_bytes()
    assert ACTOR_SHEET.read_bytes() == LEGACY_ACTOR_SHEET.read_bytes()
    payload = json.loads(ACTOR_ANIM.read_text(encoding="utf-8"))
    anims = payload["anims"]
    assert list(anims) == list(validator.EXPECTED_TAG_ORDER)

    assert _rect_signature(anims["attack_steel"]) == _rect_signature(
        anims["attack"]
    )
    assert _rect_signature(anims["skill_q12"]) == _rect_signature(anims["skill"])
    assert _rect_signature(anims["skill_w_azakana"]) == _rect_signature(
        anims["skill2_attack"]
    )
    assert _rect_signature(anims["attack_steel"]) != _rect_signature(
        anims["attack_azakana"]
    )
    assert _rect_signature(anims["skill_q12"]) != _rect_signature(
        anims["skill_q3"]
    )

    damaged = copy.deepcopy(payload)
    damaged["anims"]["attack_azakana"]["frames"] = copy.deepcopy(
        damaged["anims"]["attack_steel"]["frames"]
    )
    with pytest.raises(validator.V7ValidationError, match="distinct rectangles"):
        validator._validate_animation_contract(damaged)


def test_v7_manifest_has_67_frames_and_16_exact_weapon_geometry_fields() -> None:
    payload, palette_payload = _load_raw_contract()
    assert payload["weapon_contract"] == EXPECTED_WEAPON_CONTRACT
    assert payload["weapon_contract"]["version"] == 2
    assert payload["weapon_contract"]["always_dual_actions"] == ["idle", "run"]
    assert payload["weapon_contract"]["long_blade_overlay_policy"].startswith(
        "caster-follow effects"
    )
    assert len(payload["frames"]) == 67
    assert len(WEAPON_GEOMETRY_FIELDS) == 16

    for row in payload["frames"]:
        assert WEAPON_GEOMETRY_FIELDS <= set(row)
        assert row["weapons_present"] == ["steel", "azakana"]
        assert row["active_weapon"] == EXPECTED_ACTIVE_WEAPON_BY_ACTION[
            row["action"]
        ]
        for weapon in ("steel", "azakana"):
            assert len(row[f"{weapon}_blade_bbox"]) == 4
            assert len(row[f"{weapon}_hand_anchor"]) == 2
            assert len(row[f"{weapon}_tip"]) == 2
            assert row[f"{weapon}_span_px"] > 0
            assert 0 < row[f"{weapon}_connectedness"] <= 1
            assert row[f"{weapon}_pixel_count"] > 0
            assert 0 <= row[f"{weapon}_crop_ratio"] <= 1
            assert isinstance(row[f"{weapon}_source_tip_survived"], bool)

    assert palette_payload["weapon_roles"] == EXPECTED_WEAPON_PALETTE_ROLES


def test_v7_weapon_palette_roles_are_exclusive_from_body_mask_and_source_roles() -> None:
    _payload, palette_payload = _load_raw_contract()
    declared_roles = {
        role
        for weapon in palette_payload["weapon_roles"].values()
        for ramp in weapon.values()
        for role in ramp
    }
    body_roles = {
        row["role"]
        for row in palette_payload["colors"]
        if row["role"] == "mask"
        or row["role"].startswith("mask_")
        or row["role"] == "source"
        or row["role"].startswith("source_")
    }
    assert declared_roles == EXCLUSIVE_WEAPON_ROLES
    assert declared_roles.isdisjoint(body_roles)

    colors_by_role = {
        row["role"]: tuple(row["rgba"]) for row in palette_payload["colors"]
    }
    weapon_colors = {
        weapon: frozenset(
            colors_by_role[role]
            for ramp in EXPECTED_WEAPON_PALETTE_ROLES[weapon].values()
            for role in ramp
        )
        for weapon in ("steel", "azakana")
    }
    body_colors = frozenset(
        tuple(row["rgba"])
        for row in palette_payload["colors"]
        if row["role"] in body_roles
    )
    assert len(weapon_colors["steel"]) == 3
    assert len(weapon_colors["azakana"]) == 3
    assert weapon_colors["steel"].isdisjoint(weapon_colors["azakana"])
    assert (weapon_colors["steel"] | weapon_colors["azakana"]).isdisjoint(
        body_colors
    )


def test_v7_actor_owns_active_attack_q_w_and_r_blades_without_duplicate_overlays() -> None:
    payload = json.loads(DATA_CHAMPION.read_text(encoding="utf-8"))
    effects = list(
        _walk_effects(
            {
                "attack": payload["attack"]["effect"],
                "skill": payload["skill"]["effect"],
                "skill2": payload["skill2"]["effect"],
                "ult": payload["ult"]["effect"],
            }
        )
    )
    animation_names = {
        effect["name"]
        for effect in effects
        if effect["type"] == "CasterAnimation"
    }
    assert {
        "attack_steel",
        "attack_azakana",
        "skill_q3",
        "skill_w_azakana",
        "ult",
    } <= animation_names
    assert "skill_q12" not in animation_names

    caster_overlay_names = {
        effect["name"]
        for effect in effects
        if effect["type"] == "CasterViewEffect"
    }
    duplicate_blade_overlays = {
        "lol_yone_attack_steel_swing",
        "lol_yone_attack_azakana_swing",
        "lol_yone_q_blade",
        "lol_yone_q3_blade",
    }
    assert caster_overlay_names.isdisjoint(duplicate_blade_overlays)
    assert duplicate_blade_overlays.isdisjoint(
        {row["name"] for row in payload["view_effects"]}
    )
    assert "lol_yone_r_windup" in caster_overlay_names
    assert "lol_yone_w_crescent_cast" not in caster_overlay_names

    view_effects = {row["name"]: row for row in payload["view_effects"]}
    expected_overlays = {
        "lol_yone_q3_airborne_cue": ("cue", 2),
        "lol_yone_r_windup": ("windup", 1),
        "lol_yone_r_slash_blue": ("slash_blue", 2),
        "lol_yone_r_slash_red": ("slash_red", 2),
    }
    assert "lol_yone_w_crescent_cast" not in view_effects
    for name, (tag, z) in expected_overlays.items():
        assert view_effects[name]["tag"] == tag
        assert view_effects[name]["z"] == z
        assert view_effects[name]["is_follow"] is True


def test_v7_final_pixels_pass_exclusive_dual_sword_geometry_for_all_routes() -> None:
    validator, _payload, _palette_payload, palette, rows, sources = (
        _load_geometry_contract()
    )
    report = validator._validate_dual_sword_cues(sources, palette, rows)
    assert set(report["actions"]) == GEOMETRY_ACTIONS
    assert report["sequence_sha256"]["attack"] != report["sequence_sha256"][
        "attack_azakana"
    ]
    assert report["sequence_sha256"]["skill"] != report["sequence_sha256"][
        "skill_q3"
    ]


def test_v7_erasing_azakana_blade_cannot_be_hidden_by_mask_or_belt_red() -> None:
    validator, _payload, _palette_payload, palette, rows, sources = (
        _load_geometry_contract()
    )
    damaged = _copy_sources(sources)
    key = ("idle", 0)
    frame = damaged[key]
    azakana_colors = _weapon_colors(validator, palette, "azakana")
    body_mask_colors = palette.semantic_colors("mask")
    mask_pixels_before = _count_colors(frame, body_mask_colors)
    assert mask_pixels_before > 0

    _erase_colors(frame, azakana_colors)
    assert _count_colors(frame, azakana_colors) == 0
    assert _count_colors(frame, body_mask_colors) == mask_pixels_before
    with pytest.raises(
        validator.V7ValidationError,
        match=r"(?i)idle\[0\].*exclusive azakana pixels",
    ):
        validator._validate_dual_sword_cues(damaged, palette, rows)


def test_v7_azakana_exclusive_color_on_waist_away_from_hand_is_not_a_sword() -> None:
    validator, _payload, _palette_payload, palette, rows, sources = (
        _load_geometry_contract()
    )
    damaged = _copy_sources(sources)
    key = ("idle", 0)
    frame = damaged[key]
    row = rows[key]
    azakana_colors = _weapon_colors(validator, palette, "azakana")
    _erase_colors(frame, azakana_colors)

    face_x, face_y, face_w, face_h = row["face_bbox"]
    fake_x = max(2, face_x + face_w // 2 - 5)
    fake_y = min(frame.height - 3, face_y + face_h + 8)
    fake_points = [(fake_x + offset, fake_y) for offset in range(3)]
    hand = tuple(row["azakana_hand_anchor"])
    assert min(math.dist(point, hand) for point in fake_points) >= 7
    for point, color in zip(fake_points, sorted(azakana_colors)):
        frame.putpixel(point, color)
    assert _count_colors(frame, azakana_colors) == 3

    with pytest.raises(
        validator.V7ValidationError,
        match=r"(?i)idle\[0\].*(hand_anchor.*exclusive|hand-connected component)",
    ):
        validator._validate_dual_sword_cues(damaged, palette, rows)


def test_v7_disconnected_hilt_fails_even_when_blade_and_tip_pixels_remain() -> None:
    validator, _payload, _palette_payload, palette, rows, sources = (
        _load_geometry_contract()
    )
    damaged = _copy_sources(sources)
    key = ("idle", 0)
    frame = damaged[key]
    row = rows[key]
    steel_colors = _weapon_colors(validator, palette, "steel")
    hand_x, hand_y = row["steel_hand_anchor"]
    tip = tuple(row["steel_tip"])
    assert frame.getpixel((hand_x, hand_y)) in steel_colors
    assert frame.getpixel(tip) in steel_colors

    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            point = (hand_x + dx, hand_y + dy)
            if point == (hand_x, hand_y):
                continue
            if frame.getpixel(point) in steel_colors:
                frame.putpixel(point, (0, 0, 0, 0))
    assert frame.getpixel((hand_x, hand_y)) in steel_colors
    assert frame.getpixel(tip) in steel_colors

    with pytest.raises(
        validator.V7ValidationError,
        match=r"(?i)idle\[0\].*(hand-connected|tip)",
    ):
        validator._validate_dual_sword_cues(damaged, palette, rows)


def test_v7_cropped_tip_fails_geometry_even_when_the_rest_of_blade_remains() -> None:
    validator, _payload, _palette_payload, palette, rows, sources = (
        _load_geometry_contract()
    )
    damaged = _copy_sources(sources)
    key = ("idle", 0)
    frame = damaged[key]
    steel_colors = _weapon_colors(validator, palette, "steel")
    tip = tuple(rows[key]["steel_tip"])
    assert frame.getpixel(tip) in steel_colors
    frame.putpixel(tip, (0, 0, 0, 0))
    assert _count_colors(frame, steel_colors) > 0

    with pytest.raises(
        validator.V7ValidationError,
        match=r"(?i)idle\[0\].*tip",
    ):
        validator._validate_dual_sword_cues(damaged, palette, rows)


@pytest.mark.parametrize(
    ("field", "message"),
    (
        ("hand_anchor", r"different hand anchors"),
        ("tip", r"tips are merged|different.*tips"),
    ),
)
def test_v7_two_swords_cannot_share_a_hand_or_tip(field: str, message: str) -> None:
    validator, _payload, _palette_payload, palette, rows, sources = (
        _load_geometry_contract()
    )
    damaged_rows = copy.deepcopy(rows)
    key = ("idle", 0)
    damaged_rows[key][f"azakana_{field}"] = copy.deepcopy(
        damaged_rows[key][f"steel_{field}"]
    )
    with pytest.raises(
        validator.V7ValidationError,
        match=rf"(?i)idle\[0\].*({message})",
    ):
        validator._validate_dual_sword_cues(sources, palette, damaged_rows)


def test_v7_weapon_exclusive_pixel_may_not_touch_native_frame_edge() -> None:
    validator, _payload, _palette_payload, palette, rows, sources = (
        _load_geometry_contract()
    )
    damaged = _copy_sources(sources)
    key = ("idle", 0)
    frame = damaged[key]
    steel_color = next(iter(_weapon_colors(validator, palette, "steel")))
    frame.putpixel((0, frame.height // 2), steel_color)

    with pytest.raises(
        validator.V7ValidationError,
        match=r"(?i)idle\[0\].*2px edge margin",
    ):
        validator._validate_dual_sword_cues(damaged, palette, rows)


def test_v7_short_connected_color_blob_cannot_claim_a_full_steel_blade() -> None:
    validator, _payload, _palette_payload, palette, rows, sources = (
        _load_geometry_contract()
    )
    damaged = _copy_sources(sources)
    damaged_rows = copy.deepcopy(rows)
    key = ("idle", 0)
    frame = damaged[key]
    row = damaged_rows[key]
    steel_colors = _weapon_colors(validator, palette, "steel")
    _erase_colors(frame, steel_colors)

    hand_x, hand_y = row["steel_hand_anchor"]
    blob_points = [
        (hand_x + dx, hand_y + dy)
        for dy in range(3)
        for dx in range(3)
    ]
    role_colors = sorted(steel_colors)
    for index, point in enumerate(blob_points):
        frame.putpixel(point, role_colors[index % len(role_colors)])
    tip = (hand_x + 2, hand_y + 2)
    row.update(
        {
            "steel_blade_bbox": [hand_x, hand_y, 3, 3],
            "steel_tip": list(tip),
            "steel_span_px": round(math.dist((hand_x, hand_y), tip), 3),
            "steel_connectedness": 1.0,
            "steel_pixel_count": len(blob_points),
            "steel_crop_ratio": 0.0,
            "steel_source_tip_survived": True,
        }
    )

    with pytest.raises(
        validator.V7ValidationError,
        match=r"(?i)idle\[0\].*steel.*span.*below",
    ):
        validator._validate_dual_sword_cues(damaged, palette, damaged_rows)
