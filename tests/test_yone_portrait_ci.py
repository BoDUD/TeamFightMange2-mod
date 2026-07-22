from __future__ import annotations

import ast
import hashlib
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
VALIDATOR = MOD / "tools/validate_yone_v7.py"
FRAME_MANIFEST = MOD / "source/native/yone_v7/frames.json"
FRAME_SCHEMA = MOD / "qa/yone_v7_frames.schema.json"
PALETTE_SCHEMA = MOD / "qa/yone_v7_palette.schema.json"
GENERATION_QA = MOD / "source/native/yone_v7/generation_qa.json"
RUNTIME = MOD / "src/lib.rs"
ACTOR_ANIM = MOD / "aseprite_resources/champions/yone_v7#anim.fanim"
ACTOR_SHEET = MOD / "aseprite_resources/champions/yone_v7#sheet.png"
LEGACY_ACTOR_ANIM = MOD / "aseprite_resources/champions/yone#anim.fanim"
LEGACY_ACTOR_SHEET = MOD / "aseprite_resources/champions/yone#sheet.png"


def _load_validator():
    spec = importlib.util.spec_from_file_location("validate_yone_v7", VALIDATOR)
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
        rf"const {re.escape(name)}: f32 = (-?[0-9]+(?:\.[0-9]+)?);", source
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


def test_yone_v7_sources_exist_and_hashes_match_before_visual_validation() -> None:
    assert FRAME_MANIFEST.is_file(), (
        "Yone V7 dual-sword source is missing: "
        "mods/lol_mod/source/native/yone_v7/frames.json"
    )
    payload = json.loads(FRAME_MANIFEST.read_text(encoding="utf-8"))
    assert payload.get("schema_version") == 7
    assert payload.get("route") == "dual-sword-v7"
    assert payload.get("body_preview"), (
        "Yone V7 needs a real 141x138 actor-card preview, not null"
    )

    generation = json.loads(GENERATION_QA.read_text(encoding="utf-8"))
    assert generation.get("route") == "dual-sword-v7"
    source_hashes = generation.get("source_hashes")
    assert isinstance(source_hashes, dict)
    source_paths = {
        "motion": MOD / "source/imagegen/yone_v7_motion_contact.png",
        "attack_q": MOD / "source/imagegen/yone_v7_attack_q_contact.png",
        "w": MOD / "source/imagegen/yone_v7_w_contact.png",
        "ult": MOD / "source/imagegen/yone_v7_ult_contact.png",
    }
    assert set(source_hashes) == set(source_paths)
    for label, path in source_paths.items():
        assert path.is_file(), path
        assert source_hashes[label] == hashlib.sha256(path.read_bytes()).hexdigest()

    provenance = json.loads(
        (MOD / "qa/yone_imagegen_sources.json").read_text(encoding="utf-8")
    )
    expected_inputs = {
        path.relative_to(MOD).as_posix() for path in source_paths.values()
    }
    input_rows = provenance.get("body_imagegen_inputs")
    assert isinstance(input_rows, list)
    assert {row.get("path") for row in input_rows} == expected_inputs
    for row in input_rows:
        path = MOD / row["path"]
        assert row["sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()

    ui_rows = provenance.get("ui_only_imagegen_inputs")
    assert isinstance(ui_rows, list) and len(ui_rows) == 1
    ui_source = MOD / "source/imagegen/yone_v7_ui_source.png"
    assert ui_rows[0].get("path") == ui_source.relative_to(MOD).as_posix()
    assert ui_rows[0].get("role") == (
        "UI provenance only; never a native battle-frame input"
    )
    assert ui_rows[0].get("sha256") == hashlib.sha256(
        ui_source.read_bytes()
    ).hexdigest()


def test_yone_v7_validator_covers_all_67_frames_and_five_extension_tags() -> None:
    validator = _load_validator()
    report = validator.validate_v7(
        verify_runtime_atlas=True,
        verify_retired_paths=False,
    )
    assert report["schema_version"] == 7
    assert report["route"] == "dual-sword-v7"
    assert report["atlas_size"] == [4262, 88]
    assert report["frame_count"] == 67
    assert report["opaque_palette_limit"] >= 8
    assert len(report["frames"]) == 67
    assert report["animation_contract"]["native_tag_prefix"] == list(
        validator.NATIVE_TAG_PREFIX
    )
    assert report["animation_contract"]["extension_tags"] == [
        "attack_steel",
        "attack_azakana",
        "skill_q12",
        "skill_q3",
        "skill_w_azakana",
    ]
    assert all(report["animation_contract"]["distinct_sequences"].values())
    assert report["dual_sword"]["distinct_attack_sequences"] is True
    assert report["dual_sword"]["distinct_q_sequences"] is True
    assert report["weapon_contract"] == validator.EXPECTED_WEAPON_CONTRACT
    for frame_name, row in report["frames"].items():
        assert row["source_to_atlas_byte_identical"] is True, frame_name
        assert row["hard_alpha"] is True, frame_name
        assert row["zero_resampling"] is True, frame_name
        assert row["zero_quantize"] is True, frame_name
        assert row["zero_clip"] is True, frame_name
        assert row["opaque_palette_colors"] <= report["opaque_palette_limit"], frame_name
        assert row["bright_pixels"] >= row["bright_pixel_floor"], frame_name
        assert row["dark_pixels"] >= row["dark_pixel_floor"], frame_name
        assert row["bright_pixel_floor"] >= 0, frame_name
        assert row["dark_pixel_floor"] >= 0, frame_name

    payload = json.loads(FRAME_MANIFEST.read_text(encoding="utf-8"))
    action_counts: dict[str, int] = {}
    for row in payload["frames"]:
        assert row["weapons_present"] == ["steel", "azakana"]
        assert row["active_weapon"] == validator.ACTIVE_WEAPON_BY_ACTION[
            row["action"]
        ]
        action_counts[row["action"]] = action_counts.get(row["action"], 0) + 1
    assert action_counts == {
        "skill2": 1,
        "hit": 1,
        "attack": 6,
        "skill2_dash": 1,
        "ult": 13,
        "run": 8,
        "skill2_attack": 5,
        "idle": 4,
        "dead": 8,
        "skill": 7,
        "attack_azakana": 6,
        "skill_q3": 7,
    }
    assert ACTOR_ANIM.read_bytes() == LEGACY_ACTOR_ANIM.read_bytes()
    assert ACTOR_SHEET.read_bytes() == LEGACY_ACTOR_SHEET.read_bytes()
    anims = json.loads(ACTOR_ANIM.read_text(encoding="utf-8"))["anims"]
    assert list(anims) == [
        *validator.NATIVE_TAG_PREFIX,
        "attack_steel",
        "attack_azakana",
        "skill_q12",
        "skill_q3",
        "skill_w_azakana",
    ]
    assert len(anims["dead"]["frames"]) == 9
    for row in payload["frames"]:
        native = anims[row["action"]]["frames"][row["index"]]["data"]
        assert row["rect"] == [
            native["x"],
            native["y"],
            native["w"],
            native["h"],
        ]


def test_yone_v7_visible_idle_faces_use_dynamic_coordinate_annotations() -> None:
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

        # Prove the gate consumes the manifest coordinates without baking one
        # V5 pixel location into CI.  Select an in-frame point outside this
        # row's declared face box and require the annotation mutation to fail.
        face_x, face_y, face_width, face_height = row["face_bbox"]
        outside = next(
            [x, y]
            for y in range(source.height)
            for x in range(source.width)
            if not (
                face_x <= x < face_x + face_width
                and face_y <= y < face_y + face_height
            )
        )
        damaged = dict(row)
        damaged["eye_pixels"] = [outside, *row["eye_pixels"][1:]]
        with pytest.raises(validator.V7ValidationError):
            validator.validate_frame_annotations(
                damaged, source, palette, label=label
            )

    # Pick a valid front-facing V7 row from the manifest instead of assuming
    # that a specific action/index or source color must carry the test face.
    annotated = next(
        row
        for row in idle
        if row["face_visibility"] == "front"
        and row["face_bbox"] is not None
        and row["eye_pixels"]
    )
    annotated_source = Image.open(FRAME_MANIFEST.parent / annotated["file"])
    label = f"{annotated['action']}[{annotated['index']}]"
    annotated_stats = validator.validate_frame_annotations(
        annotated, annotated_source, palette, label=label
    )
    assert annotated_stats["connected_skin_pixels"] > 0
    assert annotated_stats["clear_interior_eye_pixels"] >= 1

    validator_source = inspect.getsource(validator.validate_frame_annotations)
    assert "eye_pixels" in validator_source
    assert "clear_eye_points" in validator_source


def test_yone_v7_real_actor_card_preview_keeps_feet_clear_from_name_band() -> None:
    validator = _load_validator()
    report = validator.validate_v7(
        verify_runtime_atlas=True,
        verify_retired_paths=False,
    )["body_preview"]
    assert report["size"] == [141, 138]
    assert report["fully_opaque_complete_card"] is True
    assert report["actor_pixels_exact"] is True
    assert report["card_pixels_exact"] is True
    assert report["divider_clearance"] >= 6
    assert report["ui_icon_safe_rect"] == [98, 70, 141, 100]
    assert report["ui_portrait_route_is_separate"] is True
    assert report["actor_alpha_bbox"][3] <= 96 - 6


def test_yone_v3_through_v6_battle_routes_are_physically_and_manifest_retired() -> None:
    validator = _load_validator()
    validator._validate_retired_paths(MOD)
    retired_tokens = {
        *validator.RETIRED_BODY_PATHS,
        *validator.RETIRED_BODY_PREFIXES,
    }
    assert any("yone_v5" in token.casefold() for token in retired_tokens)
    assert any("yone_v6" in token.casefold() for token in retired_tokens)
    assert "source/imagegen/yone_v7_ui_source.png" not in retired_tokens
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


def test_yone_v7_json_schemas_lock_dual_sword_shape_and_palette() -> None:
    frame_schema = json.loads(FRAME_SCHEMA.read_text(encoding="utf-8"))
    palette_schema = json.loads(PALETTE_SCHEMA.read_text(encoding="utf-8"))
    assert frame_schema["properties"]["schema_version"]["const"] == 7
    assert frame_schema["properties"]["route"]["const"] == "dual-sword-v7"
    assert frame_schema["properties"]["atlas_size"]["const"] == [4262, 88]
    assert frame_schema["properties"]["frames"]["minItems"] == 67
    assert frame_schema["properties"]["frames"]["maxItems"] == 67
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
        "active_weapon",
        "weapons_present",
        "steel_blade_bbox",
        "azakana_blade_bbox",
        "steel_hand_anchor",
        "azakana_hand_anchor",
        "steel_tip",
        "azakana_tip",
        "steel_span_px",
        "azakana_span_px",
        "steel_connectedness",
        "azakana_connectedness",
        "steel_pixel_count",
        "azakana_pixel_count",
        "steel_crop_ratio",
        "azakana_crop_ratio",
        "steel_source_tip_survived",
        "azakana_source_tip_survived",
    }
    weapon_contract = frame_schema["properties"]["weapon_contract"]
    assert weapon_contract == {"$ref": "#/$defs/weaponContract"}
    assert frame_schema["$defs"]["weaponContract"]["properties"][
        "always_dual_actions"
    ]["const"] == ["idle", "run"]
    assert palette_schema["properties"]["schema_version"]["const"] == 7
    assert palette_schema["properties"]["route"]["const"] == "dual-sword-v7"
    assert palette_schema["properties"]["colors"]["maxItems"] >= 9


def test_yone_builder_uses_v7_and_cannot_reprocess_native_pixels() -> None:
    builder_path = MOD / "tools/build_yone.py"
    source = builder_path.read_text(encoding="utf-8")
    assert 'NATIVE_V7_ROUTE = "dual-sword-v7"' in source
    assert 'SOURCE_ROOT / "native" / "yone_v7"' in source
    assert "NATIVE_V5_" not in source
    assert 'SOURCE_ROOT / "native" / "yone_v5"' not in source
    assert "RETIRED_YONE_V4_BODY_SOURCES" in source
    assert "RETIRED_YONE_V5_BODY_SOURCES" in source
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
    assert 'ACTOR_DIR / "yone_v7#sheet.png"' in body_source
    assert 'ACTOR_DIR / "yone_v7#anim.fanim"' in body_source
    assert 'ACTOR_DIR / "yone#sheet.png"' in body_source
    assert 'ACTOR_DIR / "yone#anim.fanim"' in body_source
    for forbidden_transform in (
        "palette_finish(",
        "fit_subject(",
        "fit_actor(",
        "_native_frame_from_cell(",
    ):
        assert forbidden_transform not in body_source


def test_yone_runtime_routes_live_bp_and_compact_surfaces_only() -> None:
    source = RUNTIME.read_text(encoding="utf-8")
    scoreboard_body = _function_body(source, "is_yone_scoreboard_portrait_geometry")
    compact_body = _function_body(source, "is_yone_compact_portrait_geometry")
    grid_body = _function_body(source, "is_yone_bp_grid_geometry")
    central_position_body = _function_body(
        source, "is_yone_central_bp_grid_position"
    )
    context_body = _function_body(source, "detect_yone_portrait_ui_context")

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
    for live_geometry in ((95.0, 88.0), (94.0, 88.0), (96.0, 89.0)):
        assert is_grid(*live_geometry)
    for excluded_geometry in (
        (85.0, 93.0),
        (90.0, 122.0),
        (95.0, 112.0),
        (114.4, 134.1),
        (129.0, 165.0),
    ):
        assert not is_grid(*excluded_geometry)
    assert not is_compact(95.0, 88.0)

    assert _f32_constant(source, "YONE_BP_PORTRAIT_SOURCE_HEIGHT") == 122.0
    assert _f32_constant(source, "YONE_BP_GRID_SAMPLE_HEIGHT") == 88.0
    assert _f32_constant(source, "YONE_ASSIGNMENT_Y_OFFSET") == -9.0
    assert _f32_constant(source, "YONE_BP_GRID_VIEWPORT_LEFT") == 335.0
    assert _f32_constant(source, "YONE_BP_GRID_VIEWPORT_RIGHT") == 1585.0
    assert _f32_constant(source, "YONE_BP_GRID_VIEWPORT_TOP") == 145.0
    assert _f32_constant(source, "YONE_BP_GRID_VIEWPORT_BOTTOM") == 522.0
    for required in (
        "let center_x = x + width * 0.5;",
        "let center_y = y + height * 0.5;",
        "YONE_BP_GRID_VIEWPORT_LEFT..=YONE_BP_GRID_VIEWPORT_RIGHT",
        "YONE_BP_GRID_VIEWPORT_TOP..=YONE_BP_GRID_VIEWPORT_BOTTOM",
        ".contains(&center_x)",
        ".contains(&center_y)",
    ):
        assert required in central_position_body

    # `header.swap_phase` is a persistent label and therefore diagnostic-only.
    # The default-hidden root `swap` container is the real assignment-stage
    # gate, while the central grid additionally requires the champions viewport.
    for required in (
        'yone_ui_node_is_visible(ui, &["swap", "main.swap"])',
        ' &["header.swap_phase", "main.header.swap_phase"],',
        'yone_ui_node_is_visible(ui, &["champions", "main.champions"])',
        "let surface = if swap_visible {",
        "YonePortraitSurface::PlayerChampionAssignment",
        "else if champion_grid_visible",
        "YonePortraitSurface::CentralBpGrid",
        "swap_phase_visible,",
    ):
        assert required in context_body
    assert "if swap_phase_visible" not in context_body

    rewrite = _function_body(source, "rewrite_yone_portrait_render_commands")
    assert "is_yone_scoreboard_portrait_geometry(*w, *h)" in rewrite
    assert "is_yone_compact_portrait_geometry(*w, *h)" in rewrite
    assert "is_yone_bp_grid_geometry(*w, *h)" in rewrite
    assert rewrite.index("YONE_SCOREBOARD_PORTRAIT_TEXTURE") < rewrite.index(
        "YONE_COMPACT_PORTRAIT_TEXTURE"
    ) < rewrite.index("YONE_BP_GRID_PORTRAIT_TEXTURE")
    for forbidden in (
        "let side =",
        "*w = side",
        "*h = side",
        "let center_x = *x + *w * 0.5;",
        "*w = 90.0;",
        "*h = 122.0;",
        "*x = center_x - *w * 0.5;",
        '"center_x_and_top_y_preserved"',
    ):
        assert forbidden not in rewrite
    for required in (
        'pass.to_string() == "UI"',
        "let central_position = is_yone_central_bp_grid_position(*x, *y, *w, *h);",
        "let is_bp_grid = is_shared_bp_geometry",
        "&& !context.swap_visible",
        "&& context.champion_grid_visible",
        "&& central_position;",
        "let is_assignment = is_shared_bp_geometry && context.swap_visible;",
        "let is_side_card = is_shared_bp_geometry",
        "&& !central_position;",
        "else if is_bp_grid || is_assignment || is_side_card",
        "YONE_BP_GRID_SAMPLE_HEIGHT / YONE_BP_PORTRAIT_SOURCE_HEIGHT",
        '"top_88_of_122"',
        "if is_assignment || is_side_card",
        "*y += YONE_ASSIGNMENT_Y_OFFSET;",
        '"yone_bp_grid_replace"',
        '"yone_assignment_replace"',
        '"yone_bp_side_card_replace"',
        "size_mode=preserved",
        "baseline_offset={baseline_offset:.0}",
    ):
        assert required in rewrite
    assert "allow_bp_grid && is_bp_grid" not in rewrite
    for preserved_axis in ("*x =", "*w =", "*h ="):
        assert preserved_axis not in rewrite
    assert "*y =" not in rewrite
    assert rewrite.count("*y += YONE_ASSIGNMENT_Y_OFFSET;") == 1


def test_yone_fullbody_card_sync_is_default_reachable_and_minimal() -> None:
    source = RUNTIME.read_text(encoding="utf-8")
    minimal_impl = source.split(
        "impl ModExtension for YoneManagementCardExtension", 1
    )[1].split("impl ModExtension for LolModExtension", 1)[0]
    assert minimal_impl.count("fn post_update(") == 1
    assert "sync_yone_encyclopedia_portrait(&mut ui.root);" in minimal_impl
    assert minimal_impl.count("fn post_render(") == 1
    assert "let context = detect_yone_portrait_ui_context(ui);" in minimal_impl
    assert "trace_yone_render_commands(ui, assets, state, context);" in minimal_impl
    assert "rewrite_yone_management_card_render_commands(state);" in minimal_impl
    assert "rewrite_yone_portrait_render_commands(state, context);" in minimal_impl
    assert minimal_impl.count("rewrite_") == 2
    assert minimal_impl.index(
        "let context = detect_yone_portrait_ui_context(ui);"
    ) < minimal_impl.index(
        "trace_yone_render_commands(ui, assets, state, context);"
    ) < minimal_impl.index(
        "rewrite_yone_management_card_render_commands(state);"
    ) < minimal_impl.index("rewrite_yone_portrait_render_commands(state, context);")
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

    assert "get_mut::<ChampionInfoUIRunner>" not in source
    assert "get::<ChampionInfoUIRunner>" not in source
    assert "fn is_ban_pick_render_pass" not in source

    slot_sync = _function_body(source, "sync_yone_encyclopedia_portrait")
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
    slot_identity = _function_body(source, "is_yone_management_slot")
    for required in (
        '.query("name")',
        "runner_as::<LabelRunner>()",
        'matches!(text, "永恩" | "Yone")',
        'text.contains("dual_blader")',
        '.query("icon")',
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

    management_geometry = _function_body(
        source, "is_yone_management_card_geometry"
    )
    assert "(width - 85.0).abs() <= 1.0" in management_geometry
    assert "(height - 93.0).abs() <= 1.0" in management_geometry

    def is_management_card(width: float, height: float) -> bool:
        return abs(width - 85.0) <= 1.0 and abs(height - 93.0) <= 1.0

    assert all(
        is_management_card(*geometry)
        for geometry in (
            (85.0, 93.0),
            (84.0, 92.0),
            (84.0, 94.0),
            (86.0, 92.0),
            (86.0, 94.0),
        )
    )
    assert not is_management_card(90.0, 122.0)
    assert not is_management_card(95.0, 112.0)

    rewrite = _function_body(
        source, "rewrite_yone_management_card_render_commands"
    )
    assert "RenderCommand::NinePatch" in rewrite
    assert "RenderCommand::Sprite" not in rewrite
    assert "is_yone_actor_sheet_texture(texture.as_str())" in rewrite
    assert "is_yone_management_card_geometry(*w, *h)" in rewrite
    assert "YONE_MANAGEMENT_CARD_PORTRAIT_TEXTURE" in rewrite
    for preserved_axis in ("*x =", "*y =", "*w =", "*h ="):
        assert preserved_axis not in rewrite
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
        '"version=0.10.20;logical_contract=85x93"',
        '"version=0.10.20;from_size=',
    ):
        assert required in rewrite
    assert (
        'const YONE_MANAGEMENT_CARD_PORTRAIT_TEXTURE: &str =\n'
        '    "asset/lol_mod/ui/champion_fullbody/dual_blader";'
        in source
    )

    trace = _function_body(source, "trace_yone_render_commands")
    for required in (
        '"yone_ui_render_hook"',
        '"version=0.10.20;management_contract=85x93;shared_bp_source=95x88;bp_grid_output=source_geometry;bp_grid_sample=top88of122;assignment_sample=top88of122;assignment_y_offset=-9;root={};surface={};swap_visible={};swap_phase_label_visible={};champion_grid_visible={}"',
        "RenderCommand::NinePatch",
        "RenderCommand::Sprite",
        'pass.to_string() == "Game"',
        "is_yone_actor_sheet_texture(texture.as_str())",
        '"yone_ui_render_command"',
        '"yone_game_sprite_atlas"',
        '"yone_game_sprite_sample"',
        '"yone_game_sprite_v7_frame"',
        "kind=NinePatch",
        "kind=Sprite",
        '"player_assignment"',
        '"bp_grid"',
        '"bp_side_card"',
        "central_position={central_position}",
        "root={}",
        "route={route}",
        "geometry={:.0},{:.0},{:.0},{:.0}",
        "uv={:.4},{:.4},{:.4},{:.4}",
        "atlas={atlas_detail}",
        "expected_atlas=4262x88",
        "atlas_missing={}",
        "source_px={},{},{},{}",
        "inferred_action={}",
        "tag_candidates={}",
        "frame={}",
        ".get::<Box<dyn ImageHandle>>(texture)",
        "game_tick=unavailable",
    ):
        assert required in trace
    assert "const YONE_GAME_TELEMETRY_ROW_LIMIT: usize = 96;" in source
    assert "static YONE_GAME_TELEMETRY_SEEN" in source
    telemetry_writer = _function_body(source, "write_bp_render_telemetry_once")
    assert 'event.starts_with("yone_game_sprite_")' in telemetry_writer
    assert "YONE_GAME_TELEMETRY_SEEN.get_or_init" in telemetry_writer
    assert "assets: &Assets" in source[source.index("fn trace_yone_render_commands") :]
    assert 'tag_candidates: "attack_azakana"' in source
    assert 'tag_candidates: "skill_q3"' in source
    assert 'tag_candidates: "skill_w_azakana|skill2_attack"' in source
    assert 'tag_candidates: "attack_azakana|skill_q3"' not in source
    assert source.count('tag_candidates: "attack_azakana"') == 6
    assert source.count('tag_candidates: "skill_q3"') == 7
    assert source.count(
        'tag_candidates: "skill_w_azakana|skill2_attack"'
    ) == 5
    anims = json.loads(ACTOR_ANIM.read_text(encoding="utf-8"))["anims"]
    for tag in ("attack_azakana", "skill_q3", "skill_w_azakana"):
        for frame in anims[tag]["frames"]:
            data = frame["data"]
            rect = (data["x"], data["y"], data["w"], data["h"])
            assert f"rect: {rect}" in source, (tag, rect)
    for forbidden in (
        "iter_mut()",
        "values_mut()",
        "command_index",
        "texture_rect.x =",
        "texture_rect.y =",
        "*texture =",
    ):
        assert forbidden not in trace

    portrait_rewrite = _function_body(source, "rewrite_yone_portrait_render_commands")
    for required in (
        '"yone_bp_grid_replace"',
        '"yone_assignment_replace"',
        '"yone_bp_side_card_replace"',
        "YONE_BP_GRID_PORTRAIT_TEXTURE",
        "from_geometry={:.0},{:.0},{:.0},{:.0}",
        "to_geometry={:.0},{:.0},{:.0},{:.0}",
        "size_mode=preserved",
        "baseline_offset={baseline_offset:.0}",
        "sample_mode={sample_mode}",
        "texture_rect.x = 0.0;",
        "texture_rect.y = 0.0;",
        "texture_rect.w = 1.0;",
        "YONE_BP_GRID_SAMPLE_HEIGHT / YONE_BP_PORTRAIT_SOURCE_HEIGHT",
        '"top_88_of_122"',
        "texture_rect.h = 1.0;",
        "*y += YONE_ASSIGNMENT_Y_OFFSET;",
        "*left = 0.0;",
        "*right = 0.0;",
        "*top = 0.0;",
        "*bottom = 0.0;",
        "*sample_nearest = true;",
    ):
        assert required in portrait_rewrite
    assert "RenderCommand::Sprite" not in portrait_rewrite
    assert portrait_rewrite.index(
        "if !is_yone_actor_sheet_texture(texture.as_str())"
    ) < portrait_rewrite.index("let is_shared_bp_geometry =")
    for required in (
        'pass.to_string() == "UI"',
        "is_yone_central_bp_grid_position(*x, *y, *w, *h)",
        "context.swap_visible",
        "context.champion_grid_visible",
    ):
        assert required in portrait_rewrite
    for preserved_axis in ("*x =", "*w =", "*h ="):
        assert preserved_axis not in portrait_rewrite
    assert "*y =" not in portrait_rewrite
    assert portrait_rewrite.count("*y += YONE_ASSIGNMENT_Y_OFFSET;") == 1

    bp_slot = (MOD / "ui/layout/banpick/champion_slot.ui").read_text(
        encoding="utf-8"
    )
    icon_canvas = bp_slot.split("#icon:canvas", 1)[1].split("}", 1)[0]
    assert "height: 88px;" in icon_canvas
    assert "y: 4px;" in icon_canvas
    grid_portrait = Image.open(
        MOD / "ui/champion_portrait/dual_blader_grid.png"
    ).convert("RGBA")
    assert grid_portrait.size == (90, 122)
    source_bbox = grid_portrait.getchannel("A").getbbox()
    assert source_bbox is not None
    assert source_bbox[2] - source_bbox[0] <= 72
    assert source_bbox[3] - source_bbox[1] <= 82
    assert min(source_bbox[0], grid_portrait.width - source_bbox[2]) >= 4
    assert source_bbox[3] <= 86
    sample_height = int(_f32_constant(source, "YONE_BP_GRID_SAMPLE_HEIGHT"))
    assignment_y_offset = int(_f32_constant(source, "YONE_ASSIGNMENT_Y_OFFSET"))
    assert source_bbox[3] <= sample_height
    assert sample_height - source_bbox[3] == 2
    assert sample_height - (source_bbox[3] + assignment_y_offset) == 11

    telemetry_writer = _function_body(source, "write_bp_render_telemetry_once")
    for required in (
        'event.ends_with("_replace")',
        "BP_TELEMETRY_CRITICAL_ROW_LIMIT",
        "BP_TELEMETRY_ROW_LIMIT",
        "seen.len() >= row_limit",
    ):
        assert required in telemetry_writer

    visual_contract = json.loads(
        (MOD / "qa/yone_visual_contract.json").read_text(encoding="utf-8")
    )
    idle_zero = visual_contract["face_readability"]["live_idle_card"]["frames"][
        "idle[0]"
    ]
    assert idle_zero["rendered_size"] == [95, 121]
    assert not is_management_card(*idle_zero["rendered_size"])

    preview = Image.open(MOD / "qa/yone_v7_ui_card.png").convert("RGBA")
    fullbody = Image.open(MOD / "ui/champion_fullbody/dual_blader.png").convert(
        "RGBA"
    )
    preview_crop = preview.crop((28, 0, 113, 93))
    preview_pixels = preview_crop.load()
    fullbody_pixels = fullbody.load()
    assert preview_pixels is not None and fullbody_pixels is not None
    opaque_matches = [
        preview_pixels[x, y] == fullbody_pixels[x, y]
        for y in range(fullbody.height)
        for x in range(fullbody.width)
        if fullbody_pixels[x, y][3] > 0
    ]
    assert len(opaque_matches) >= 500
    assert all(opaque_matches)

    init = source.split("fn init(_ctx: &GameCtx) -> ModRegistration", 1)[1]
    init = init.split("declare_mod!(init);", 1)[0]
    assert "} else {" in init
    assert "registration.set_extension(YoneManagementCardExtension);" in init

    sync_body = _function_body(source, "sync_yone_encyclopedia_portrait")
    assert "dual_blader" in sync_body
    assert "lol_fullbody_yone" in sync_body
    assert "lol_fullbody_shen" not in sync_body
    assert 'root.id == "champion_slot"' in sync_body
    assert "is_yone_management_slot(root)" in sync_body
    assert 'root.query_mut("icon")' in sync_body
    assert "icon.visible = false;" in sync_body
    assert 'root.query_mut("lol_fullbody_yone")' in sync_body
    assert "portrait.visible = true;" in sync_body
    assert "sync_yone_encyclopedia_portrait(child);" in sync_body

    legacy_impl = source.split("impl ModExtension for LolModExtension", 1)[1]
    legacy_impl = legacy_impl.split("fn rewrite_kled_portrait_render_commands", 1)[0]
    legacy_post_update = _function_body(legacy_impl, "post_update")
    legacy_sync_call = "sync_encyclopedia_portraits(&mut ui.root);"
    assert legacy_post_update.count(legacy_sync_call) == 1
    assert legacy_post_update.index("remember_database(database);") < (
        legacy_post_update.index(legacy_sync_call)
    )


def test_yone_fullbody_card_keeps_two_readable_legs_and_boots() -> None:
    image = Image.open(MOD / "ui/champion_fullbody/dual_blader.png").convert("RGBA")
    alpha = image.getchannel("A")
    bbox = alpha.getbbox()
    assert bbox is not None

    body_left = bbox[0] + round((bbox[2] - bbox[0]) * 0.28)
    body_right = bbox[2] - round((bbox[2] - bbox[0]) * 0.24)

    def opaque_runs(y: int) -> list[list[int]]:
        runs: list[list[int]] = []
        for x in range(body_left, body_right):
            if alpha.getpixel((x, y)) < 128:
                continue
            if not runs or x > runs[-1][-1] + 1:
                runs.append([x])
            else:
                runs[-1].append(x)
        return runs

    lower_start = bbox[1] + round((bbox[3] - bbox[1]) * 0.68)
    separated_rows = 0
    for y in range(lower_start, bbox[3]):
        substantial = [run for run in opaque_runs(y) if len(run) >= 4]
        if len(substantial) < 2:
            continue
        if any(
            right[0] - left[-1] >= 2
            for left, right in zip(substantial, substantial[1:], strict=False)
        ):
            separated_rows += 1
    assert separated_rows >= 12

    boot_top = bbox[1] + round((bbox[3] - bbox[1]) * 0.80)
    remaining = {
        (x, y)
        for y in range(boot_top, bbox[3])
        for x in range(body_left, body_right)
        if alpha.getpixel((x, y)) >= 128
    }
    components: list[set[tuple[int, int]]] = []
    while remaining:
        frontier = [remaining.pop()]
        component = set(frontier)
        while frontier:
            x, y = frontier.pop()
            for neighbor in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
                if neighbor in remaining:
                    remaining.remove(neighbor)
                    component.add(neighbor)
                    frontier.append(neighbor)
        if len(component) >= 40:
            components.append(component)
    assert len(components) == 2
    boot_boxes = sorted(
        (
            min(x for x, _y in component),
            min(y for _x, y in component),
            max(x for x, _y in component) + 1,
            max(y for _x, y in component) + 1,
        )
        for component in components
    )
    assert all(right - left >= 8 for left, _top, right, _bottom in boot_boxes)
    assert all(bottom - top >= 12 for _left, top, _right, bottom in boot_boxes)
    assert boot_boxes[1][0] - boot_boxes[0][2] >= 1


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
