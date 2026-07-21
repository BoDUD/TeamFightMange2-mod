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
VALIDATOR = MOD / "tools/validate_yone_v6.py"
FRAME_MANIFEST = MOD / "source/native/yone_v6/frames.json"
FRAME_SCHEMA = MOD / "qa/yone_v6_frames.schema.json"
PALETTE_SCHEMA = MOD / "qa/yone_v6_palette.schema.json"
GENERATION_QA = MOD / "source/native/yone_v6/generation_qa.json"
RUNTIME = MOD / "src/lib.rs"


def _load_validator():
    spec = importlib.util.spec_from_file_location("validate_yone_v6", VALIDATOR)
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


def test_yone_v6_sources_exist_and_hashes_match_before_visual_validation() -> None:
    assert FRAME_MANIFEST.is_file(), (
        "Yone V6 exact-native source is missing: "
        "mods/lol_mod/source/native/yone_v6/frames.json"
    )
    payload = json.loads(FRAME_MANIFEST.read_text(encoding="utf-8"))
    assert payload.get("schema_version") == 6
    assert payload.get("route") == "exact-native-v6"
    assert payload.get("body_preview"), (
        "Yone V6 needs a real 141x138 actor-card preview, not null"
    )

    generation = json.loads(GENERATION_QA.read_text(encoding="utf-8"))
    assert generation.get("route") == "exact-native-v6"
    source_hashes = generation.get("source_hashes")
    assert isinstance(source_hashes, dict)
    source_paths = {
        "motion": MOD / "source/imagegen/yone_v6_motion_contact.png",
        "attack_q_w": MOD / "source/imagegen/yone_v6_attack_q_w_contact.png",
        "w": MOD / "source/imagegen/yone_v6_w_contact.png",
        "ult": MOD / "source/imagegen/yone_v6_ult_contact.png",
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
    ui_source = MOD / "source/imagegen/yone_v6_idle_source.png"
    assert ui_rows[0].get("path") == ui_source.relative_to(MOD).as_posix()
    assert ui_rows[0].get("role") == (
        "UI provenance only; never a native battle-frame input"
    )
    assert ui_rows[0].get("sha256") == hashlib.sha256(
        ui_source.read_bytes()
    ).hexdigest()


def test_yone_v6_exact_native_validator_covers_all_54_frames() -> None:
    validator = _load_validator()
    report = validator.validate_v6(
        verify_runtime_atlas=True,
        verify_retired_paths=True,
    )
    assert report["schema_version"] == 6
    assert report["route"] == "exact-native-v6"
    assert report["atlas_size"] == [3502, 88]
    assert report["frame_count"] == 54
    assert report["opaque_palette_limit"] >= 8
    assert len(report["frames"]) == 54
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
    }
    anims = json.loads(
        (MOD / "aseprite_resources/champions/yone#anim.fanim").read_text(
            encoding="utf-8"
        )
    )["anims"]
    assert len(anims) == 13
    assert len(anims["dead"]["frames"]) == 9
    for row in payload["frames"]:
        native = anims[row["action"]]["frames"][row["index"]]["data"]
        assert row["rect"] == [
            native["x"],
            native["y"],
            native["w"],
            native["h"],
        ]


def test_yone_v6_visible_idle_faces_use_dynamic_coordinate_annotations() -> None:
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
        with pytest.raises(validator.V6ValidationError):
            validator.validate_frame_annotations(
                damaged, source, palette, label=label
            )

    # Pick a valid front-facing V6 row from the manifest instead of assuming
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


def test_yone_v6_real_actor_card_preview_keeps_feet_and_icons_clear() -> None:
    validator = _load_validator()
    report = validator.validate_v6(
        verify_runtime_atlas=True,
        verify_retired_paths=True,
    )["body_preview"]
    assert report["size"] == [141, 138]
    assert report["fully_opaque_complete_card"] is True
    assert report["actor_pixels_exact"] is True
    assert report["card_pixels_exact"] is True
    assert report["divider_clearance"] >= 6
    assert report["ui_icon_safe_rect"] == [98, 70, 141, 100]
    assert report["actor_alpha_bbox"][3] <= 96 - 6


def test_yone_v3_v4_and_v5_body_routes_are_physically_and_manifest_retired() -> None:
    validator = _load_validator()
    validator._validate_retired_paths(MOD)
    retired_tokens = {
        *validator.RETIRED_BODY_PATHS,
        *validator.RETIRED_BODY_PREFIXES,
    }
    assert any("yone_v5" in token.casefold() for token in retired_tokens)
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


def test_yone_v6_json_schemas_lock_exact_native_shape_and_palette() -> None:
    frame_schema = json.loads(FRAME_SCHEMA.read_text(encoding="utf-8"))
    palette_schema = json.loads(PALETTE_SCHEMA.read_text(encoding="utf-8"))
    assert frame_schema["properties"]["schema_version"]["const"] == 6
    assert frame_schema["properties"]["route"]["const"] == "exact-native-v6"
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
    assert palette_schema["properties"]["schema_version"]["const"] == 6
    assert palette_schema["properties"]["route"]["const"] == "exact-native-v6"
    assert palette_schema["properties"]["colors"]["maxItems"] >= 9


def test_yone_builder_physically_retires_v3_v4_v5_and_cannot_reprocess_native_pixels() -> None:
    builder_path = MOD / "tools/build_yone.py"
    source = builder_path.read_text(encoding="utf-8")
    assert 'NATIVE_V6_ROUTE = "exact-native-v6"' in source
    assert 'SOURCE_ROOT / "native" / "yone_v6"' in source
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
    grid_ratio_floor_match = re.search(r"height / width >= ([0-9.]+)", grid_body)
    grid_ratio_limit_match = re.search(r"height / width <= ([0-9.]+)", grid_body)
    assert grid_ratio_floor_match is not None and grid_ratio_limit_match is not None
    grid_ratio_floor = float(grid_ratio_floor_match.group(1))
    grid_ratio_limit = float(grid_ratio_limit_match.group(1))

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
            and grid_ratio_floor <= height / width <= grid_ratio_limit
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
    assert is_grid(94.6, 121.0)
    for excluded_geometry in (
        (85.0, 93.0),
        (95.0, 112.0),
        (114.4, 134.1),
        (129.0, 165.0),
    ):
        assert not is_grid(*excluded_geometry)
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


def test_yone_fullbody_card_sync_is_default_reachable_and_minimal() -> None:
    source = RUNTIME.read_text(encoding="utf-8")
    minimal_impl = source.split(
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
        '"version=0.10.15;logical_contract=85x93"',
        '"version=0.10.15;from_size=',
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
        '"version=0.10.15;management_contract=85x93;bp_grid_contract=90x122"',
        "RenderCommand::NinePatch",
        "RenderCommand::Sprite",
        '"yone_ui_render_command"',
        "kind=NinePatch",
        "kind=Sprite",
        "route={route}",
        "geometry={:.0}x{:.0}",
    ):
        assert required in trace
    for forbidden in (
        "iter_mut()",
        "values_mut()",
        "command_index",
        "texture_rect.x",
        "texture_rect.y",
        "*texture =",
    ):
        assert forbidden not in trace

    portrait_rewrite = _function_body(source, "rewrite_yone_portrait_render_commands")
    for required in (
        '"yone_bp_grid_replace"',
        "YONE_BP_GRID_PORTRAIT_TEXTURE",
        "geometry_preserved=true",
        "texture_rect.x = 0.0;",
        "texture_rect.y = 0.0;",
        "texture_rect.w = 1.0;",
        "texture_rect.h = 1.0;",
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
    ) < portrait_rewrite.index("let is_bp_grid = is_yone_bp_grid_geometry(*w, *h);")
    for preserved_axis in ("*x =", "*y =", "*w =", "*h ="):
        assert preserved_axis not in portrait_rewrite

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

    preview = Image.open(MOD / "qa/yone_v6_ui_card.png").convert("RGBA")
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
    assert len(opaque_matches) == 2706
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

    def opaque_runs(y: int) -> list[list[int]]:
        runs: list[list[int]] = []
        for x in range(bbox[0], bbox[2]):
            if alpha.getpixel((x, y)) < 128:
                continue
            if not runs or x > runs[-1][-1] + 1:
                runs.append([x])
            else:
                runs[-1].append(x)
        return runs

    lower_start = bbox[1] + round((bbox[3] - bbox[1]) * 0.70)
    separated_rows = 0
    for y in range(lower_start, bbox[3]):
        substantial = [run for run in opaque_runs(y) if len(run) >= 7]
        if len(substantial) < 2:
            continue
        if any(
            right[0] - left[-1] >= 3
            for left, right in zip(substantial, substantial[1:], strict=False)
        ):
            separated_rows += 1
    assert separated_rows >= 8

    boot_runs = opaque_runs(bbox[3] - 1)
    assert len(boot_runs) == 2
    assert min(len(run) for run in boot_runs) >= 7
    assert boot_runs[1][0] - boot_runs[0][-1] >= 6


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
