from __future__ import annotations

import copy
import importlib.util
import json
import sys
from pathlib import Path

import pytest
from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
MOD = ROOT / "mods/lol_mod"
VALIDATOR_PATH = MOD / "tools/validate_yone_v7.py"
FRAME_MANIFEST = MOD / "source/native/yone_v7/frames.json"
ACTOR_ANIM = MOD / "aseprite_resources/champions/yone#anim.fanim"


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


def test_v7_keeps_native_prefix_and_adds_semantic_dual_sword_tags() -> None:
    validator = _load_validator()
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


def test_v7_manifest_declares_the_dual_sword_semantic_contract() -> None:
    validator = _load_validator()
    payload = json.loads(FRAME_MANIFEST.read_text(encoding="utf-8"))
    palette_payload = json.loads(
        (FRAME_MANIFEST.parent / payload["palette_file"]).read_text(encoding="utf-8")
    )
    assert payload["weapon_contract"] == validator.EXPECTED_WEAPON_CONTRACT
    assert (
        palette_payload["weapon_roles"]
        == validator.EXPECTED_WEAPON_PALETTE_ROLES
    )
    assert payload["weapon_contract"]["always_dual_actions"] == ["idle", "run"]
    assert payload["weapon_contract"]["long_blade_overlay_policy"].startswith(
        "caster-follow effects"
    )

    for row in payload["frames"]:
        assert row["weapons_present"] == ["steel", "azakana"]
        assert row["active_weapon"] == validator.ACTIVE_WEAPON_BY_ACTION[
            row["action"]
        ]


def test_v7_final_pixels_prove_dual_sword_cues_for_every_combat_route() -> None:
    validator = _load_validator()
    payload = json.loads(FRAME_MANIFEST.read_text(encoding="utf-8"))
    palette = validator.load_palette(FRAME_MANIFEST.parent / payload["palette_file"])
    sources = {
        (row["action"], row["index"]): Image.open(
            FRAME_MANIFEST.parent / row["file"]
        ).convert("RGBA")
        for row in payload["frames"]
    }
    rows_by_key = {
        (row["action"], row["index"]): row for row in payload["frames"]
    }
    report = validator._validate_dual_sword_cues(sources, palette, rows_by_key)
    assert all(
        row["steel_lower_left_pixels"] >= 1
        and row["azakana_lower_right_pixels"] >= 4
        for row in report["idle"].values()
    )
    assert all(
        row["steel"]["pixels"] >= 5
        and row["steel"]["farthest_from_face"] >= 25
        and row["azakana"]["farthest_from_face"] >= 17
        for row in report["actions"]["run"]
    )
    assert set(report["actions"]) == {
        "idle",
        "run",
        "attack",
        "attack_azakana",
        "skill",
        "skill_q3",
        "skill2_attack",
        "ult",
    }
    assert all(
        result["actual"] >= result["minimum"]
        for result in report["sequence_requirements"].values()
    )
    assert report["sequence_sha256"]["attack"] != report["sequence_sha256"][
        "attack_azakana"
    ]
    assert report["sequence_sha256"]["skill"] != report["sequence_sha256"][
        "skill_q3"
    ]

    # Prove the gate reads actual pixels rather than trusting weapons_present.
    damaged = {key: image.copy() for key, image in sources.items()}
    idle_zero = damaged[("idle", 0)]
    steel_colors = palette.exact_role("source_03")
    for y in range(idle_zero.height // 2, idle_zero.height):
        for x in range(0, min(15, idle_zero.width)):
            if idle_zero.getpixel((x, y)) in steel_colors:
                idle_zero.putpixel((x, y), (0, 0, 0, 0))
    with pytest.raises(
        validator.V7ValidationError, match=r"idle\[0\].*steel cue"
    ):
        validator._validate_dual_sword_cues(damaged, palette, rows_by_key)

    damaged_attack = {key: image.copy() for key, image in sources.items()}
    steel_attack = damaged_attack[("attack", 0)]
    steel_cue_colors = palette.exact_role("source_03") | palette.exact_role(
        "source_04"
    )
    for y in range(steel_attack.height):
        for x in range(steel_attack.width):
            if steel_attack.getpixel((x, y)) in steel_cue_colors:
                steel_attack.putpixel((x, y), (0, 0, 0, 0))
    with pytest.raises(validator.V7ValidationError, match=r"attack\[0\].*steel cue"):
        validator._validate_dual_sword_cues(
            damaged_attack, palette, rows_by_key
        )

    damaged_w = {key: image.copy() for key, image in sources.items()}
    w_frame = damaged_w[("skill2_attack", 2)]
    azakana_cue_colors = palette.semantic_colors("mask")
    for y in range(w_frame.height):
        for x in range(w_frame.width):
            if w_frame.getpixel((x, y)) in azakana_cue_colors:
                w_frame.putpixel((x, y), (0, 0, 0, 0))
    with pytest.raises(
        validator.V7ValidationError, match=r"skill2_attack\[2\].*Azakana cue"
    ):
        validator._validate_dual_sword_cues(damaged_w, palette, rows_by_key)
