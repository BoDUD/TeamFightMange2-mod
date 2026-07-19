from __future__ import annotations

import ast
import importlib.util
import inspect
import json
import re
import sys
from pathlib import Path

import pytest
from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
MOD = ROOT / "mods/lol_mod"
VALIDATOR = MOD / "tools/validate_yone_v5.py"
FRAME_MANIFEST = MOD / "source/native/yone_v5/frames.json"
FRAME_SCHEMA = MOD / "qa/yone_v5_frames.schema.json"
PALETTE_SCHEMA = MOD / "qa/yone_v5_palette.schema.json"
RUNTIME = MOD / "src/lib.rs"


def _load_validator():
    spec = importlib.util.spec_from_file_location("validate_yone_v5", VALIDATOR)
    assert spec is not None and spec.loader is not None
    validator = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = validator
    spec.loader.exec_module(validator)
    return validator


def _function_body(source: str, name: str) -> str:
    signature = f"fn {name}"
    start = source.index(signature)
    opening = source.index("{", start)
    depth = 0
    for index in range(opening, len(source)):
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1
            if depth == 0:
                return source[opening + 1 : index]
    raise AssertionError(f"unterminated Rust function: {name}")


def _f32_constant(source: str, name: str) -> float:
    match = re.search(
        rf"const {re.escape(name)}: f32 = ([0-9]+(?:\.[0-9]+)?);", source
    )
    assert match is not None, name
    return float(match.group(1))


def _range_contract(body: str, axis: str) -> tuple[float, float]:
    match = re.search(
        rf"\(([0-9]+(?:\.[0-9]+)?)\.\.="
        rf"([0-9]+(?:\.[0-9]+)?)\)\.contains\(&{axis}\)",
        body,
    )
    assert match is not None, (axis, body)
    return float(match.group(1)), float(match.group(2))


def test_yone_v5_sources_exist_before_visual_validation() -> None:
    assert FRAME_MANIFEST.is_file(), (
        "Yone V5 exact-native source is missing: "
        "mods/lol_mod/source/native/yone_v5/frames.json"
    )
    payload = json.loads(FRAME_MANIFEST.read_text(encoding="utf-8"))
    assert payload.get("schema_version") == 5
    assert payload.get("route") == "exact-native-v5"
    assert payload.get("body_preview"), (
        "Yone V5 needs a real 141x138 actor-card preview, not null"
    )


def test_yone_v5_exact_native_validator_covers_all_54_frames() -> None:
    validator = _load_validator()
    report = validator.validate_v5()
    assert report["schema_version"] == 5
    assert report["route"] == "exact-native-v5"
    assert report["atlas_size"] == [3502, 88]
    assert report["frame_count"] == 54
    assert report["opaque_palette_limit"] == 32
    assert report["body_transform"] == {
        "resampling": "none",
        "quantize": "none",
        "clip": "none",
        "proof": "exact per-frame RGBA byte identity",
    }
    assert report["retired_v3_v4_body_paths_absent"] is True
    assert report["eye_role_policy"] == ["eye_outline", "eye_highlight"]
    assert len(report["frames"]) == 54
    for frame_name, row in report["frames"].items():
        assert row["source_to_atlas_byte_identical"] is True, frame_name
        assert row["hard_alpha"] is True, frame_name
        assert row["zero_resampling"] is True, frame_name
        assert row["zero_quantize"] is True, frame_name
        assert row["zero_clip"] is True, frame_name
        assert row["opaque_palette_colors"] <= 32, frame_name
        assert row["bright_pixels"] >= row["bright_pixel_floor"], frame_name
        assert row["dark_pixels"] >= row["dark_pixel_floor"], frame_name
        if not frame_name.startswith("dead["):
            assert row["bright_pixel_floor"] == 8, frame_name
        assert row["dark_pixel_floor"] == 12, frame_name


def test_yone_v5_visible_idle_faces_use_explicit_coordinate_annotations() -> None:
    validator = _load_validator()
    payload = json.loads(FRAME_MANIFEST.read_text(encoding="utf-8"))
    palette = validator.load_palette(
        FRAME_MANIFEST.parent / payload["palette_file"]
    )
    idle = [row for row in payload["frames"] if row["action"] == "idle"]
    assert len(idle) == 4
    for row in idle:
        label = f"{row['action']}[{row['index']}]"
        source = Image.open(FRAME_MANIFEST.parent / row["file"])
        stats = validator.validate_frame_annotations(
            row, source, palette, label=label
        )
        assert row["face_bbox"] is not None, label
        assert row["face_visibility"] in {"front", "profile"}, label
        assert len(row["eye_pixels"]) >= 1, label
        assert row["mask_bbox"] is not None, label
        assert stats["face_skin_pixels"] >= 4, label
        assert stats["face_mean_luminance"] >= 120, label
        assert stats["eye_pixels"] >= 1, label
        assert stats["mask_pixels"] >= 4, label

        # Prove the gate consumes declared coordinates.  Moving an eye marker
        # to a transparent pixel must fail; the validator may not search for a
        # nearby dark pixel and silently accept a different feature.
        damaged = dict(row)
        damaged["eye_pixels"] = [[0, 0], *row["eye_pixels"][1:]]
        with pytest.raises(
            validator.V5ValidationError,
            match="must point to exact eye_outline or eye_highlight|outside face_bbox",
        ):
            validator.validate_frame_annotations(
                damaged, source, palette, label=label
            )

    golden = idle[0]
    assert golden["face_visibility"] == "front"
    golden_source = Image.open(FRAME_MANIFEST.parent / golden["file"])
    golden_stats = validator.validate_frame_annotations(
        golden, golden_source, palette, label="idle[0]"
    )
    assert golden_stats["connected_skin_pixels"] >= 24
    assert golden_stats["clear_interior_eye_pixels"] >= 1

    # A skin color whose role merely contains the substring ``eye`` must not
    # become a valid eye.  This is the exact false-positive that let V4 accept
    # face-shadow/hair pixels as facial features.
    fake_eye_color = golden_source.getpixel((19, 11))
    fake_roles = dict(palette.by_role)
    fake_roles["skin_shadow_eye"] = frozenset({fake_eye_color})
    fake_palette = validator.Palette(palette.colors, fake_roles)
    fake_skin_eye = dict(golden)
    fake_skin_eye["eye_pixels"] = [[19, 11]]
    with pytest.raises(
        validator.V5ValidationError,
        match="must point to exact eye_outline or eye_highlight",
    ):
        validator.validate_frame_annotations(
            fake_skin_eye, golden_source, fake_palette, label="idle[0]"
        )

    # Likewise, a real outline color on the top edge of the face box is hair /
    # forehead silhouette, not a readable eye.
    boundary_eye = dict(golden)
    boundary_eye["eye_pixels"] = [[21, 10]]
    with pytest.raises(
        validator.V5ValidationError,
        match="clear interior eye point|outer hair/face-box border",
    ):
        validator.validate_frame_annotations(
            boundary_eye, golden_source, palette, label="idle[0]"
        )

    validator_source = inspect.getsource(validator.validate_frame_annotations)
    palette_source = inspect.getsource(validator.Palette.semantic_colors)
    assert "eye_pixels" in validator_source
    assert "clear_eye_points" in validator_source
    assert '{"eye_outline", "eye_highlight"}' in palette_source
    assert "skin_shadow_eye" in palette_source


def test_yone_v5_real_actor_card_preview_keeps_feet_and_icons_clear() -> None:
    validator = _load_validator()
    report = validator.validate_v5()["body_preview"]
    assert report["size"] == [141, 138]
    assert report["fully_opaque_complete_card"] is True
    assert report["actor_pixels_exact"] is True
    assert report["card_pixels_exact"] is True
    assert report["divider_clearance"] >= 6
    assert report["ui_icon_safe_rect"] == [98, 70, 141, 100]
    assert report["rendered_skin_pixels"] >= 96
    assert report["actor_alpha_bbox"][3] <= 96 - 6


def test_yone_v3_and_v4_body_routes_are_physically_and_manifest_retired() -> None:
    validator = _load_validator()
    validator._validate_retired_paths(MOD)
    for relative in validator.RETIRED_BODY_PATHS:
        assert not (MOD / relative).exists(), relative
    for prefix in validator.RETIRED_BODY_PREFIXES:
        assert not (MOD / prefix.rstrip("/")).exists(), prefix

    manifest = json.loads(
        (MOD / "build_manifest.json").read_text(encoding="utf-8")
    )
    paths = {
        row["path"].replace("\\", "/")
        for row in manifest["files"]
        if isinstance(row, dict) and isinstance(row.get("path"), str)
    }
    assert paths.isdisjoint(validator.RETIRED_BODY_PATHS)
    assert not any(
        path.startswith(prefix)
        for path in paths
        for prefix in validator.RETIRED_BODY_PREFIXES
    )


def test_yone_v5_json_schemas_lock_exact_native_shape_and_palette() -> None:
    frame_schema = json.loads(FRAME_SCHEMA.read_text(encoding="utf-8"))
    palette_schema = json.loads(PALETTE_SCHEMA.read_text(encoding="utf-8"))
    assert frame_schema["properties"]["schema_version"]["const"] == 5
    assert frame_schema["properties"]["route"]["const"] == "exact-native-v5"
    assert frame_schema["properties"]["atlas_size"]["const"] == [3502, 88]
    assert frame_schema["properties"]["frames"]["minItems"] == 54
    assert frame_schema["properties"]["frames"]["maxItems"] == 54
    assert set(frame_schema["$defs"]["frame"]["required"]) == {
        "action",
        "index",
        "file",
        "rect",
        "bottom_margin",
        "face_bbox",
        "eye_pixels",
        "mask_bbox",
        "foot_zones",
        "face_visibility",
    }
    assert palette_schema["properties"]["schema_version"]["const"] == 5
    assert palette_schema["properties"]["route"]["const"] == "exact-native-v5"
    assert palette_schema["properties"]["colors"]["maxItems"] == 33


def test_yone_builder_physically_retires_v3_v4_and_cannot_transform_body_pixels() -> None:
    builder_path = MOD / "tools/build_yone.py"
    source = builder_path.read_text(encoding="utf-8")
    assert 'NATIVE_V5_ROUTE = "exact-native-v5"' in source
    assert 'SOURCE_ROOT / "native" / "yone_v5"' in source
    assert "RETIRED_YONE_V4_BODY_SOURCES" in source
    for retired_symbol in (
        "_whole_sheet_native_raster",
        "NATIVE_BODY_FRAME_SOURCES",
        "_compose_native_body_master",
        "NATIVE_BODY_MASTER",
        "yone_core_contact.png",
        "yone_run_contact.png",
        "yone_wr_body_contact.png",
        "yone_defeat_contact.png",
    ):
        assert retired_symbol not in source, retired_symbol

    tree = ast.parse(source)
    build_actor = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "build_actor"
    )
    body_source = ast.get_source_segment(source, build_actor)
    assert body_source is not None
    assert ".resize(" not in body_source
    assert ".quantize(" not in body_source
    for forbidden_transform in (
        "palette_finish(",
        "fit_subject(",
        "fit_actor(",
        "_native_frame_from_cell(",
    ):
        assert forbidden_transform not in body_source


def test_yone_runtime_routes_rectangular_and_square_compact_surfaces_only() -> None:
    source = RUNTIME.read_text(encoding="utf-8")
    scoreboard_body = _function_body(source, "is_yone_scoreboard_portrait_geometry")
    compact_body = _function_body(source, "is_yone_compact_portrait_geometry")
    grid_body = _function_body(source, "is_yone_bp_grid_geometry")

    scoreboard_width = _range_contract(scoreboard_body, "width")
    scoreboard_height = _range_contract(scoreboard_body, "height")
    ratio_floor_match = re.search(r"height / width >= ([0-9.]+)", scoreboard_body)
    ratio_limit_match = re.search(r"height / width <= ([0-9.]+)", scoreboard_body)
    assert ratio_floor_match is not None and ratio_limit_match is not None
    ratio_floor = float(ratio_floor_match.group(1))
    ratio_limit = float(ratio_limit_match.group(1))

    compact_width = _range_contract(compact_body, "width")
    compact_height = _range_contract(compact_body, "height")
    square_delta_match = re.search(
        r"\(width - height\)\.abs\(\) <= ([0-9.]+)", compact_body
    )
    assert square_delta_match is not None
    square_delta = float(square_delta_match.group(1))
    grid_width = _range_contract(grid_body, "width")
    grid_height = _range_contract(grid_body, "height")

    def is_scoreboard(width: float, height: float) -> bool:
        return (
            scoreboard_width[0] <= width <= scoreboard_width[1]
            and scoreboard_height[0] <= height <= scoreboard_height[1]
            and ratio_floor <= height / width <= ratio_limit
        )

    def is_compact(width: float, height: float) -> bool:
        return (
            compact_width[0] <= width <= compact_width[1]
            and compact_height[0] <= height <= compact_height[1]
            and abs(width - height) <= square_delta
        )

    def is_grid(width: float, height: float) -> bool:
        return (
            grid_width[0] <= width <= grid_width[1]
            and grid_height[0] <= height <= grid_height[1]
        )

    scoreboard_surfaces = ((18.0, 26.0), (30.0, 38.0))
    assert all(is_scoreboard(*geometry) for geometry in scoreboard_surfaces)
    assert all(not is_compact(*geometry) for geometry in scoreboard_surfaces)
    assert all(not is_grid(*geometry) for geometry in scoreboard_surfaces)
    assert is_compact(34.0, 34.0)
    assert not is_scoreboard(34.0, 34.0)
    assert is_compact(18.0, 18.0)
    assert not is_scoreboard(18.0, 18.0)
    assert is_compact(46.0, 46.0)
    assert not is_scoreboard(46.0, 46.0)
    assert is_grid(90.0, 122.0)
    assert not is_compact(90.0, 122.0)

    rewrite = _function_body(source, "rewrite_yone_portrait_render_commands")
    assert "is_yone_scoreboard_portrait_geometry(*w, *h)" in rewrite
    assert "is_yone_compact_portrait_geometry(*w, *h)" in rewrite
    assert "is_yone_bp_grid_geometry(*w, *h)" in rewrite
    assert rewrite.index("YONE_SCOREBOARD_PORTRAIT_TEXTURE") < rewrite.index(
        "YONE_COMPACT_PORTRAIT_TEXTURE"
    ) < rewrite.index("YONE_BP_GRID_PORTRAIT_TEXTURE")
    for forbidden in ("let side =", "*w = side", "*h = side"):
        assert forbidden not in rewrite
    assert "else if is_bp_grid" in rewrite
    assert "allow_bp_grid && is_bp_grid" not in rewrite
    assert "let center_x" not in rewrite
    assert "let center_y" not in rewrite
    assert "*w =" not in rewrite
    assert "*h =" not in rewrite


def test_yone_bp_transition_contract_covers_observed_and_settled_geometry() -> None:
    source = RUNTIME.read_text(encoding="utf-8")
    constants = {
        name: _f32_constant(source, name)
        for name in (
            "BP_DUAL_BLADER_ACTOR_WIDTH",
            "BP_DUAL_BLADER_ACTOR_HEIGHT",
            "BP_DUAL_BLADER_TRANSITION_MIN_WIDTH",
            "BP_DUAL_BLADER_TRANSITION_MAX_WIDTH",
            "BP_DUAL_BLADER_TRANSITION_MIN_HEIGHT",
            "BP_DUAL_BLADER_TRANSITION_MAX_HEIGHT",
        )
    }
    assert constants == {
        "BP_DUAL_BLADER_ACTOR_WIDTH": 129.0,
        "BP_DUAL_BLADER_ACTOR_HEIGHT": 165.0,
        "BP_DUAL_BLADER_TRANSITION_MIN_WIDTH": 112.0,
        "BP_DUAL_BLADER_TRANSITION_MAX_WIDTH": 132.0,
        "BP_DUAL_BLADER_TRANSITION_MIN_HEIGHT": 132.0,
        "BP_DUAL_BLADER_TRANSITION_MAX_HEIGHT": 168.0,
    }
    assert "114.4x134.1" in source

    def covered(width: float, height: float) -> bool:
        return (
            constants["BP_DUAL_BLADER_TRANSITION_MIN_WIDTH"]
            <= width
            <= constants["BP_DUAL_BLADER_TRANSITION_MAX_WIDTH"]
            and constants["BP_DUAL_BLADER_TRANSITION_MIN_HEIGHT"]
            <= height
            <= constants["BP_DUAL_BLADER_TRANSITION_MAX_HEIGHT"]
        )

    assert covered(114.4, 134.1)
    assert covered(
        constants["BP_DUAL_BLADER_ACTOR_WIDTH"],
        constants["BP_DUAL_BLADER_ACTOR_HEIGHT"],
    )

    contract = _function_body(source, "bp_actor_contract")
    dual_blader = contract[contract.index('champion_id == "dual_blader"') :]
    assert "width: BP_DUAL_BLADER_ACTOR_WIDTH" in dual_blader
    assert "height: BP_DUAL_BLADER_ACTOR_HEIGHT" in dual_blader
    assert "min_width: BP_DUAL_BLADER_TRANSITION_MIN_WIDTH" in dual_blader
    assert "max_width: BP_DUAL_BLADER_TRANSITION_MAX_WIDTH" in dual_blader
    assert "min_height: BP_DUAL_BLADER_TRANSITION_MIN_HEIGHT" in dual_blader
    assert "max_height: BP_DUAL_BLADER_TRANSITION_MAX_HEIGHT" in dual_blader
