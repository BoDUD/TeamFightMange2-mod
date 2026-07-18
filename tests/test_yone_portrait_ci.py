from __future__ import annotations

import hashlib
import importlib.util
import inspect
import json
import re
from pathlib import Path

import pytest
from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
MOD = ROOT / "mods" / "lol_mod"
RUNTIME = MOD / "src" / "lib.rs"
GENERATOR = MOD / "tools" / "build_yone.py"
COMPACT = MOD / "ui" / "champion_portrait" / "dual_blader_compact.png"
SCOREBOARD = MOD / "ui" / "champion_portrait" / "dual_blader_scoreboard.png"
GRID = MOD / "ui" / "champion_portrait" / "dual_blader_grid.png"
FULLBODY = MOD / "ui" / "champion_fullbody" / "dual_blader.png"
ACTOR_SHEET = MOD / "aseprite_resources/champions/yone#sheet.png"
ACTOR_ANIM = MOD / "aseprite_resources/champions/yone#anim.fanim"
CHAMPION_VIEW = MOD / "style/champion_view.champion_view"
CHAMPION_SLOT = MOD / "ui" / "layout" / "champion_info_component" / "champion_slot.ui"
YONE_LIVE_CARD_SCALE = 2.2
YONE_LIVE_CARD_DIVIDER_TOP = 99
YONE_LIVE_CARD_MIN_DIVIDER_CLEARANCE = 10


def _load_build_yone():
    spec = importlib.util.spec_from_file_location("build_yone", GENERATOR)
    assert spec is not None and spec.loader is not None
    build_yone = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(build_yone)
    return build_yone


def test_yone_native_grid_crop_rejects_visible_edge_strips() -> None:
    build_yone = _load_build_yone()
    source = Image.new("RGBA", (11, 10), (0, 0, 0, 0))
    source.putpixel((10, 4), (180, 40, 30, 64))
    with pytest.raises(ValueError, match="crop alpha>=64 pixels"):
        build_yone._center_crop_divisible_grid(source, (2, 2))

    source.putpixel((10, 4), (180, 40, 30, 63))
    cropped = build_yone._center_crop_divisible_grid(source, (2, 2))
    assert cropped.size == (10, 10)


def test_yone_whole_sheet_resize_requires_near_isotropic_scale() -> None:
    build_yone = _load_build_yone()
    source = Image.new("RGBA", (100, 100), (30, 40, 50, 255))
    logical, contract = build_yone._whole_sheet_native_raster(
        "unit", source, (1, 1), (20, 20)
    )
    assert logical.size == (20, 20)
    assert contract["scale_x"] == contract["scale_y"] == 0.2
    assert contract["scale_relative_delta"] == 0.0
    assert contract["near_isotropic"] is True

    # One-pixel whole-plate rounding below 0.5% is accepted and recorded.
    rounded_source = Image.new("RGBA", (200, 201), (30, 40, 50, 255))
    _, rounded_contract = build_yone._whole_sheet_native_raster(
        "unit_rounding", rounded_source, (1, 1), (20, 20)
    )
    assert 0 < rounded_contract["scale_relative_delta"] < 0.005

    with pytest.raises(ValueError, match="not near-isotropic"):
        build_yone._whole_sheet_native_raster(
            "unit_bad", source, (1, 1), (20, 21)
        )


def test_yone_native_frame_clip_is_vertical_zero_and_horizontal_opt_in() -> None:
    build_yone = _load_build_yone()

    vertical = Image.new("RGBA", (4, 8), (50, 60, 70, 255))
    with pytest.raises(ValueError, match="clips vertical opaque pixels"):
        build_yone._native_frame_from_cell(
            vertical, (4, 6), 0, ("unit_vertical", 0)
        )

    horizontal = Image.new("RGBA", (8, 6), (50, 60, 70, 255))
    key = ("unit_horizontal", 0)
    with pytest.raises(ValueError, match="explicit limit"):
        build_yone._native_frame_from_cell(horizontal, (6, 10), 2, key)

    build_yone.NATIVE_HORIZONTAL_CLIP_LIMITS[key] = {
        "left": {
            "max_lost_opaque_pixels": 6,
            "max_lost_opaque_ratio": 0.125,
        },
        "right": {
            "max_lost_opaque_pixels": 6,
            "max_lost_opaque_ratio": 0.125,
        },
    }
    try:
        frame, audit = build_yone._native_frame_from_cell(
            horizontal, (6, 10), 2, key
        )
    finally:
        del build_yone.NATIVE_HORIZONTAL_CLIP_LIMITS[key]
    assert frame.size == (6, 10)
    assert audit["clip_sides_lost_opaque"] == {
        "top": 0,
        "bottom": 0,
        "left": 6,
        "right": 6,
    }
    assert audit["lost_opaque_pixels"] == 12
    assert audit["lost_opaque_ratio"] == 0.25


def test_yone_native_paste_rejects_every_partial_intersection() -> None:
    build_yone = _load_build_yone()
    sheet = Image.new("RGBA", (20, 20), (0, 0, 0, 0))
    placements: dict[tuple[int, int, int, int], bytes] = {}
    red = Image.new("RGBA", (4, 4), (255, 0, 0, 255))
    build_yone._paste_unique(sheet, placements, (1, 1, 4, 4), red)
    # Exact same rectangle and bytes is the sole permitted alias.
    build_yone._paste_unique(sheet, placements, (1, 1, 4, 4), red.copy())

    with pytest.raises(ValueError, match="assigned different pixels"):
        build_yone._paste_unique(
            sheet,
            placements,
            (1, 1, 4, 4),
            Image.new("RGBA", (4, 4), (0, 0, 255, 255)),
        )
    with pytest.raises(ValueError, match="partially intersect"):
        build_yone._paste_unique(sheet, placements, (4, 1, 4, 4), red)


def _assert_no_synthetic_face_markers(quality: dict[str, object]) -> None:
    assert quality["warm_skin_component_present"] is True, quality
    assert quality["adjacent_dark_eye_cue"] is True, quality


def _assert_natural_face_quality(
    quality: dict[str, object],
    *,
    minimum_width: int = 2,
    minimum_height: int = 2,
    minimum_skin: int = 4,
    minimum_contrast: float = 12,
    near_white_budget: int | None = None,
) -> None:
    """Validate measured source-authored facial cues, not a source-model hash."""

    _assert_no_synthetic_face_markers(quality)
    face = quality["face_skin_bbox"]
    assert face is not None, quality
    assert face[2] - face[0] >= minimum_width, quality
    assert face[3] - face[1] >= minimum_height, quality
    face_skin_pixels = int(quality["face_skin_pixels"])
    assert int(quality["warm_skin_pixels"]) == face_skin_pixels, quality
    assert face_skin_pixels >= minimum_skin, quality
    assert int(quality["adjacent_dark_eye_cue_pixels"]) >= 1, quality
    assert float(quality["face_contrast"]) >= minimum_contrast, quality
    if near_white_budget is None:
        near_white_budget = max(2, face_skin_pixels // 20)
    assert int(quality["near_white_pixels"]) <= near_white_budget, quality


def _assert_adult_proportions(quality: dict[str, object]) -> None:
    body = quality["body_bbox"]
    face = quality["face_skin_bbox"]
    assert body is not None and face is not None, quality
    body_height = body[3] - body[1]
    face_height = face[3] - face[1]
    assert body_height >= 30, quality
    assert face_height / body_height <= 0.40, quality


def _assert_scaled_source_face_quality(
    quality: dict[str, object],
    *,
    near_white_budget: int,
    minimum_contrast: float = 12,
    require_dark: bool = True,
) -> None:
    assert quality["source_face_skin_bbox"] is not None, quality
    assert quality["rendered_face_skin_bbox"] is not None, quality
    assert quality["source_warm_skin_component_present"] is True, quality
    assert quality["rendered_warm_skin_component_present"] is True, quality
    assert int(quality["rendered_face_skin_pixels"]) >= 1, quality
    assert int(quality["source_near_white_pixels"]) <= near_white_budget, quality
    assert float(quality["source_face_contrast"]) >= minimum_contrast, quality
    if require_dark:
        assert quality["source_adjacent_dark_eye_cue"] is True, quality
        assert quality["rendered_adjacent_dark_eye_cue"] is True, quality
        assert int(quality["source_adjacent_dark_eye_cue_pixels"]) >= 1, quality
        assert int(quality["rendered_adjacent_dark_eye_cue_pixels"]) >= 1, quality


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
    match = re.search(rf"const {re.escape(name)}: f32 = ([0-9]+(?:\.[0-9]+)?);", source)
    assert match is not None, name
    return float(match.group(1))


def _range_contract(body: str, axis: str) -> tuple[float, float]:
    match = re.search(
        rf"\(([0-9]+(?:\.[0-9]+)?)\.\.=([0-9]+(?:\.[0-9]+)?)\)"
        rf"\.contains\(&{axis}\)",
        body,
    )
    assert match is not None, (axis, body)
    return float(match.group(1)), float(match.group(2))


def test_yone_compact_is_head_shoulders_and_grid_keeps_the_name_band_clear() -> None:
    compact = Image.open(COMPACT).convert("RGBA")
    grid = Image.open(GRID).convert("RGBA")
    assert compact.size == (64, 64)
    assert grid.size == (90, 122)

    compact_bbox = compact.getchannel("A").getbbox()
    assert compact_bbox is not None
    left, top, right, bottom = compact_bbox
    width = right - left
    height = bottom - top
    assert 42 <= width <= 52
    assert 48 <= height <= 52
    assert min(left, top, 64 - right, 64 - bottom) >= 6

    grid_alpha = grid.getchannel("A")
    grid_bbox = grid_alpha.getbbox()
    assert grid_bbox is not None
    assert grid_bbox[3] <= 86
    assert grid_alpha.crop((0, 96, 90, 122)).getbbox() is None


def test_yone_ui_faces_keep_the_natural_imagegen_face_component() -> None:
    build_yone = _load_build_yone()
    surfaces = {
        "fullbody": Image.open(FULLBODY).convert("RGBA"),
        "compact": Image.open(COMPACT).convert("RGBA"),
        "scoreboard": Image.open(SCOREBOARD).convert("RGBA"),
        "grid": Image.open(GRID).convert("RGBA"),
    }
    assert set(surfaces) == set(build_yone.YONE_UI_FACE_WINDOWS)
    for name, image in surfaces.items():
        quality = build_yone.yone_face_readability(
            image, build_yone.YONE_UI_FACE_WINDOWS[name]
        )
        minimum_width, minimum_height, minimum_skin = (
            (5, 6, 14) if name == "fullbody" else (6, 8, 20)
        )
        _assert_natural_face_quality(
            quality,
            minimum_width=minimum_width,
            minimum_height=minimum_height,
            minimum_skin=minimum_skin,
            near_white_budget=max(4, int(quality["face_skin_pixels"]) // 10),
        )

    generator = GENERATOR.read_text(encoding="utf-8")
    assert "YONE_UI_FACE_WINDOWS" in generator
    assert "yone_fullbody_card_contract" in generator
    assert "save_png(fullbody_path, fullbody)" in generator
    assert "save_png(compact_path, compact)" in generator
    assert "save_png(scoreboard_path, scoreboard)" in generator
    assert "save_png(grid_path, grid)" in generator
    assert "stamp_yone_face_template" not in generator
    assert "YONE_FACE_REPAIR_TEMPLATE" not in generator
    assert "_paint_yone_face_plane" not in generator
    assert "YONE_FACE_FRONT_TEMPLATE" not in generator
    assert "YONE_FACE_PROFILE_TEMPLATE" not in generator
    assert "YONE_FACE_SCLERA_RGBA" not in generator
    assert "finish_imagegen_yone_idle_face" not in generator
    assert "Rebuilt Yone idle face finishing changed alpha geometry" not in generator
    assert "retouch_yone_ui_surface(" not in inspect.getsource(
        build_yone.build_splash_and_portraits
    )
    assert "repaint_yone_face(" not in inspect.getsource(build_yone.build_actor)

    contract = json.loads(
        (MOD / "qa/yone_visual_contract.json").read_text(encoding="utf-8")
    )["face_readability"]
    assert contract["policy"] == (
        "complete adult-proportioned ImageGen body-model replacement rasterized "
        "once as whole-sheet native 1x pixel art; no per-frame resize, "
        "post-scale face repaint, or synthetic feature overlay"
    )
    assert contract["actor_resampling"] == "whole-sheet NEAREST once; pack-time NONE"
    assert contract["idle_face_contract"] == {
        "source_authored": True,
        "post_scale_repaint": False,
        "view": "natural 3/4 profile with one dominant eye cue",
        "alpha_geometry_changes": 0,
    }


def test_yone_fullbody_uses_the_real_64x64_to_85x93_encyclopedia_route() -> None:
    build_yone = _load_build_yone()
    fullbody = Image.open(FULLBODY).convert("RGBA")
    assert fullbody.size == (64, 64)
    assert fullbody.getchannel("A").getbbox() is not None

    route = build_yone.yone_fullbody_card_contract(fullbody)
    assert route["source_size"] == [64, 64]
    assert route["rendered_size"] == [85, 93]
    assert route["resampling"] == "nearest"
    source_alpha = route["source_alpha_bbox"]
    rendered_alpha = route["rendered_alpha_bbox"]
    assert source_alpha is not None and rendered_alpha is not None
    assert 0 <= source_alpha[0] < source_alpha[2] <= 64
    assert 0 <= source_alpha[1] < source_alpha[3] <= 64
    assert source_alpha[2] - source_alpha[0] >= 40
    assert source_alpha[3] - source_alpha[1] >= 40
    assert 0 <= rendered_alpha[0] < rendered_alpha[2] <= 85
    assert 0 <= rendered_alpha[1] < rendered_alpha[3] <= 93
    assert rendered_alpha[2] - rendered_alpha[0] >= 54
    assert rendered_alpha[3] - rendered_alpha[1] >= 58
    assert route["source_bottom_margin"] >= 3
    assert route["rendered_bottom_margin"] >= 4
    for prefix, alpha_bbox in (
        ("source", source_alpha),
        ("rendered", rendered_alpha),
    ):
        last_row = route[f"{prefix}_last_alpha_row"]
        assert last_row[0] == alpha_bbox[3] - 1
        assert alpha_bbox[0] <= last_row[1] < last_row[2] <= alpha_bbox[2]
    assert route["source_red_mask_pixels"] >= 20
    source_red_mask = route["source_red_mask_bbox"]
    assert source_red_mask is not None
    assert 0 <= source_red_mask[0] < source_red_mask[2] <= 64
    assert 0 <= source_red_mask[1] < source_red_mask[3] <= 64
    _assert_scaled_source_face_quality(
        route, near_white_budget=4, minimum_contrast=18
    )
    source_face = route["source_face_skin_bbox"]
    rendered_face = route["rendered_face_skin_bbox"]
    assert source_face[2] - source_face[0] >= 5
    assert source_face[3] - source_face[1] >= 6
    assert rendered_face[2] - rendered_face[0] >= 6
    assert rendered_face[3] - rendered_face[1] >= 9
    assert route["rendered_face_skin_pixels"] >= 20
    assert source_face[3] - source_face[1] <= (
        route["source_alpha_bbox"][3] - route["source_alpha_bbox"][1]
    ) // 3

    ui = CHAMPION_SLOT.read_text(encoding="utf-8")
    match = re.search(
        r"#lol_fullbody_yone:image\s*\{(?P<body>.*?)\n\s*\}",
        ui,
        re.DOTALL,
    )
    assert match is not None
    node = match.group("body")
    assert re.search(r"\bwidth:\s*85px;", node)
    assert re.search(r"\bheight:\s*93px;", node)
    assert 'source: "asset/lol_mod/ui/champion_fullbody/dual_blader";' in node
    assert re.search(r"\bsample_linear:\s*false;", node)

    runtime = RUNTIME.read_text(encoding="utf-8")
    assert '("dual_blader", "lol_fullbody_yone")' in runtime


def test_all_54_yone_battle_faces_follow_the_rebuilt_model_contract() -> None:
    build_yone = _load_build_yone()
    sheet = Image.open(ACTOR_SHEET).convert("RGBA")
    master = Image.open(build_yone.NATIVE_BODY_MASTER).convert("RGBA")
    anims = json.loads(ACTOR_ANIM.read_text(encoding="utf-8"))["anims"]
    frames = list(build_yone.iter_actor_body_frames(anims))
    assert len(frames) == 54
    assert build_yone.NATIVE_MIN_VISIBLE_HEIGHTS["run"] == [
        31,
        32,
        32,
        33,
        32,
        32,
        32,
        33,
    ]
    assert ("run", 3) not in build_yone.NATIVE_HORIZONTAL_CLIP_LIMITS
    observed: set[tuple[str, int]] = set()
    w_hashes: set[str] = set()
    for tag, index, entry in frames:
        observed.add((tag, index))
        data = entry["data"]
        frame = sheet.crop(
            (
                data["x"],
                data["y"],
                data["x"] + data["w"],
                data["y"] + data["h"],
            )
        )
        assert frame.getchannel("A").getbbox() is not None, (tag, index)
        assert frame.tobytes() == master.crop(
            (
                data["x"],
                data["y"],
                data["x"] + data["w"],
                data["y"] + data["h"],
            )
        ).tobytes(), (tag, index)
        pixel_quality = build_yone.native_pixel_quality(frame)
        assert pixel_quality["hard_alpha"], (tag, index, pixel_quality)
        assert pixel_quality["opaque_palette_size"] <= 48, (
            tag,
            index,
            pixel_quality,
        )
        quality = build_yone.yone_face_readability(frame)
        body_bbox = quality["body_bbox"]
        assert body_bbox is not None, (tag, index, quality)
        visible_height = body_bbox[3] - body_bbox[1]
        if tag in build_yone.NATIVE_MIN_VISIBLE_HEIGHTS:
            assert visible_height >= build_yone.NATIVE_MIN_VISIBLE_HEIGHTS[tag][index], (
                tag,
                index,
                quality,
            )
        if tag == "dead":
            assert quality["red_mask_pixels"] >= 1, (tag, index, quality)
            continue
        if tag == "skill2_attack":
            w_hashes.add(hashlib.sha256(frame.tobytes()).hexdigest())
        if tag == "idle":
            minimum_width, minimum_height, minimum_skin, minimum_contrast = (
                4,
                5,
                10,
                18,
            )
        elif tag == "run":
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
        _assert_natural_face_quality(
            quality,
            minimum_width=minimum_width,
            minimum_height=minimum_height,
            minimum_skin=minimum_skin,
            minimum_contrast=minimum_contrast,
        )
        assert quality["minimal_feature_set"] is True, (tag, index, quality)
        face_bbox = quality["face_skin_bbox"]
        assert (face_bbox[3] - face_bbox[1]) / visible_height <= 0.40, (
            tag,
            index,
            quality,
        )

    assert len(observed) == 54
    assert len(w_hashes) >= 4


def test_yone_idle0_is_copied_from_native_master_without_pack_time_resampling() -> None:
    """The packed idle is byte-identical to the final native 1x master."""

    build_yone = _load_build_yone()
    rect = build_yone.NATIVE_CONTRACT["idle"]["rects"][0]
    master = Image.open(build_yone.NATIVE_BODY_MASTER).convert("RGBA")
    expected = master.crop(
        (rect[0], rect[1], rect[0] + rect[2], rect[1] + rect[3])
    )
    sheet = Image.open(ACTOR_SHEET).convert("RGBA")
    final_idle = sheet.crop(
        (rect[0], rect[1], rect[0] + rect[2], rect[1] + rect[3])
    )
    assert expected.tobytes() == final_idle.tobytes()
    actor_source = inspect.getsource(build_yone.build_actor)
    native_source = inspect.getsource(build_yone._whole_sheet_native_raster)
    assert "Image.Resampling.NEAREST" in native_source
    assert ".resize(" not in actor_source
    assert not hasattr(build_yone, "fit_actor")
    assert not hasattr(build_yone, "add_yone_w_weapon_pose")
    assert "finish_imagegen_yone_idle_face" not in GENERATOR.read_text(
        encoding="utf-8"
    )
    assert "repaint_yone_face(" not in actor_source

    quality = build_yone.yone_face_readability(final_idle)
    _assert_natural_face_quality(
        quality,
        minimum_width=4,
        minimum_height=5,
        minimum_skin=10,
        minimum_contrast=18,
    )
    _assert_adult_proportions(quality)
    body_bbox = quality["body_bbox"]
    face_bbox = quality["face_skin_bbox"]
    assert body_bbox[3] - body_bbox[1] >= build_yone.NATIVE_MIN_VISIBLE_HEIGHTS[
        "idle"
    ][0]
    assert 0 <= body_bbox[0] < body_bbox[2] <= final_idle.width
    assert 0 <= body_bbox[1] < body_bbox[3] <= final_idle.height
    assert 0 <= face_bbox[0] < face_bbox[2] <= final_idle.width
    assert 0 <= face_bbox[1] < face_bbox[3] <= final_idle.height
    assert quality["adjacent_dark_eye_cue"] is True
    assert quality["adjacent_dark_eye_cue_pixels"] >= 1


def _runtime_scoreboard_metrics(size: tuple[int, int]) -> dict[str, int]:
    portrait = Image.open(SCOREBOARD).convert("RGBA")
    rendered = portrait.resize(size, Image.Resampling.NEAREST)
    # Pillow 14 renamed getdata() to get_flattened_data(), while GitHub's
    # Python 3.12 image still carries the older Pillow API.  Keep the regression
    # gate executable on both versions until the CI dependency floor moves.
    pixels = list(
        rendered.get_flattened_data()
        if hasattr(rendered, "get_flattened_data")
        else rendered.getdata()
    )
    opaque = [pixel for pixel in pixels if pixel[3] >= 128]
    luminance = [round(0.299 * red + 0.587 * green + 0.114 * blue) for red, green, blue, _ in opaque]
    red_mask = [
        pixel
        for pixel in opaque
        if pixel[0] >= 70
        and pixel[0] >= pixel[1] * 1.35
        and pixel[0] >= pixel[2] * 1.18
    ]
    skin = [
        pixel
        for pixel in opaque
        if pixel[0] >= 110
        and pixel[1] >= 60
        and pixel[2] >= 45
        and pixel[0] > pixel[1]
        and pixel[1] >= pixel[2] * 0.80
    ]
    return {
        "opaque": len(opaque),
        "colors": len(set(opaque)),
        "contrast": max(luminance) - min(luminance),
        "red_mask": len(red_mask),
        "skin": len(skin),
    }


def test_yone_scoreboard_is_source_direct_portrait_geometry_with_clear_face() -> None:
    build_yone = _load_build_yone()
    scoreboard = Image.open(SCOREBOARD).convert("RGBA")
    assert scoreboard.size == (48, 64)
    bbox = scoreboard.getchannel("A").getbbox()
    assert bbox is not None
    left, top, right, bottom = bbox
    assert 36 <= right - left <= 40
    assert 50 <= bottom - top <= 54
    assert min(left, top, 48 - right, 64 - bottom) >= 4

    # The 48:64 source aspect lies between both observed native destination
    # rectangles.  The runtime can therefore keep their x/y/w/h unchanged
    # instead of squaring either command and shifting the portrait row.
    assert 18 / 26 <= scoreboard.width / scoreboard.height <= 30 / 38

    smallest = _runtime_scoreboard_metrics((18, 26))
    assert smallest["opaque"] >= 210
    assert smallest["colors"] >= 50
    assert smallest["contrast"] >= 180
    assert smallest["red_mask"] >= 30
    assert smallest["skin"] >= 16

    regular = _runtime_scoreboard_metrics((30, 38))
    assert regular["opaque"] >= 520
    assert regular["colors"] >= 70
    assert regular["contrast"] >= 180
    assert regular["red_mask"] >= 60
    assert regular["skin"] >= 35

    for size in ((18, 26), (30, 38)):
        rendered = scoreboard.resize(size, Image.Resampling.NEAREST)
        quality = build_yone.yone_face_readability(
            rendered, build_yone.YONE_UI_FACE_WINDOWS["scoreboard"]
        )
        _assert_natural_face_quality(
            quality,
            minimum_width=2,
            minimum_height=2,
            minimum_skin=4,
            minimum_contrast=10,
            near_white_budget=2,
        )
        assert quality["red_mask_pixels"] >= 3, (size, quality)

    # Scoreboard and side-list art are independent crops, so later tuning one
    # surface cannot silently reintroduce Yone's muddy face on the other.
    assert SCOREBOARD.read_bytes() != COMPACT.read_bytes()

    source = GENERATOR.read_text(encoding="utf-8")
    assert "first_idle = split_grid(Image.open(CORE_ALPHA)" in source
    assert "scoreboard_focus = full_body.crop(" in source
    assert "scoreboard = render_ui_subject(" in source
    assert "render_ui_subject(" in source
    assert 'scoreboard_path = PORTRAIT_DIR / "dual_blader_scoreboard.png"' in source
    assert source.index("scoreboard_focus = full_body.crop(") < source.index(
        "scoreboard = render_ui_subject("
    )
    assert "stamp_yone_face_template" not in source
    assert "compact.resize" not in source


def test_yone_default_actor_crop_centers_the_face_and_restores_native_feet() -> None:
    """Replay the user's real Sprite crop instead of testing dead UI PNG routes."""

    build_yone = _load_build_yone()
    style = json.loads(CHAMPION_VIEW.read_text(encoding="utf-8"))["entries"][
        "dual_blader"
    ]
    assert style == {
        "face": {"x": 2, "y": -32},
        "center": {"x": 0, "y": -16},
        "banpick_center": {"x": 0, "y": -16},
    }

    anims = json.loads(ACTOR_ANIM.read_text(encoding="utf-8"))["anims"]
    sheet = Image.open(ACTOR_SHEET).convert("RGBA")

    native_bottoms = {
        "idle": [16, 15, 14, 15],
        "run": [13, 18, 21, 18, 13, 17, 21, 17],
        "attack": [14, 14, 12, 13, 13, 14],
        "hit": [15],
    }
    for tag, expected in native_bottoms.items():
        actual = []
        for entry in anims[tag]["frames"]:
            data = entry["data"]
            frame = sheet.crop(
                (
                    data["x"],
                    data["y"],
                    data["x"] + data["w"],
                    data["y"] + data["h"],
                )
            )
            bbox = frame.getchannel("A").getbbox()
            assert bbox is not None
            actual.append(data["h"] - bbox[3])
        assert actual == expected, tag

    # Replay the actual renderer route: each native idle rectangle is uniformly
    # enlarged by about 2.2x and vertically centered on the tallest idle stage.
    # All four animation frames must retain the accepted source-authored face
    # cues and foot gap.
    idle_entries = anims["idle"]["frames"]
    stage_height = max(
        round(entry["data"]["h"] * YONE_LIVE_CARD_SCALE)
        for entry in idle_entries
    )
    assert stage_height == 121
    rendered_sizes: list[tuple[int, int]] = []
    stage_offsets: list[int] = []
    projected_bottoms: list[int] = []
    divider_clearances: list[int] = []
    scaled_idle_metrics: list[dict[str, object]] = []
    for index, entry in enumerate(idle_entries):
        data = entry["data"]
        idle_frame = sheet.crop(
            (
                data["x"],
                data["y"],
                data["x"] + data["w"],
                data["y"] + data["h"],
            )
        )
        live_idle = idle_frame.resize(
            (
                round(data["w"] * YONE_LIVE_CARD_SCALE),
                round(data["h"] * YONE_LIVE_CARD_SCALE),
            ),
            Image.Resampling.NEAREST,
        )
        rendered_sizes.append(live_idle.size)
        live_bbox = live_idle.getchannel("A").getbbox()
        assert live_bbox is not None
        stage_y = (stage_height - live_idle.height) // 2
        stage_offsets.append(stage_y)
        projected_bottom = stage_y + live_bbox[3]
        projected_bottoms.append(projected_bottom)
        divider_clearance = YONE_LIVE_CARD_DIVIDER_TOP - projected_bottom
        divider_clearances.append(divider_clearance)
        assert stage_y + live_bbox[1] >= 0, index
        assert divider_clearance >= YONE_LIVE_CARD_MIN_DIVIDER_CLEARANCE, index
        source_quality = build_yone.yone_face_readability(idle_frame)
        _assert_natural_face_quality(
            source_quality,
            minimum_width=4,
            minimum_height=5,
            minimum_skin=10,
            minimum_contrast=18,
            near_white_budget=1,
        )
        _assert_adult_proportions(source_quality)
        scaled_quality = build_yone.yone_live_card_idle_metrics(
            idle_frame,
            stage_height=stage_height,
            center_y=style["center"]["y"],
            variant="front",
        )
        scaled_idle_metrics.append(scaled_quality)
        _assert_scaled_source_face_quality(
            scaled_quality, near_white_budget=1, minimum_contrast=18
        )
        rendered_face = scaled_quality["rendered_face_skin_bbox"]
        assert rendered_face[2] - rendered_face[0] >= 8
        assert rendered_face[3] - rendered_face[1] >= 11
        assert scaled_quality["rendered_size"] == list(live_idle.size)
        assert scaled_quality["stage_y"] == stage_y
        assert scaled_quality["projected_alpha_bbox"][3] == projected_bottom
        assert scaled_quality["divider_clearance"] == divider_clearance

    assert rendered_sizes == [(95, 121), (95, 117), (95, 112), (95, 117)]
    assert stage_offsets == [0, 2, 4, 2]
    assert projected_bottoms == [86, 86, 85, 86]
    assert divider_clearances == [13, 13, 14, 13]

    # Validate the accepted adult body and natural face component after NEAREST
    # projection; the builder measures it and never paints facial markers.
    idle0 = scaled_idle_metrics[0]
    assert idle0["source_size"] == [43, 55]
    assert idle0["rendered_size"] == [95, 121]
    assert idle0["stage_y"] == 0
    alpha_bbox = idle0["alpha_bbox"]
    projected_alpha_bbox = idle0["projected_alpha_bbox"]
    assert 0 <= alpha_bbox[0] < alpha_bbox[2] <= idle0["rendered_size"][0]
    assert 0 <= alpha_bbox[1] < alpha_bbox[3] <= idle0["rendered_size"][1]
    assert projected_alpha_bbox == [
        alpha_bbox[0],
        alpha_bbox[1] + idle0["stage_y"],
        alpha_bbox[2],
        alpha_bbox[3] + idle0["stage_y"],
    ]
    assert idle0["source_bottom_clearance"] == 16
    assert idle0["rendered_bottom_clearance"] == 35
    assert idle0["divider_clearance"] == 13
    source_face = idle0["source_face_skin_bbox"]
    rendered_face = idle0["rendered_face_skin_bbox"]
    assert source_face[2] - source_face[0] >= 4
    assert source_face[3] - source_face[1] >= 5
    assert rendered_face[2] - rendered_face[0] >= 8
    assert rendered_face[3] - rendered_face[1] >= 11
    assert idle0["rendered_face_skin_pixels"] >= 20
    assert idle0["source_warm_skin_component_present"] is True
    assert idle0["rendered_warm_skin_component_present"] is True
    assert idle0["source_adjacent_dark_eye_cue"] is True
    assert idle0["rendered_adjacent_dark_eye_cue"] is True
    assert idle0["source_adjacent_dark_eye_cue_pixels"] >= 1
    assert idle0["rendered_adjacent_dark_eye_cue_pixels"] >= 1
    assert idle0["source_face_contrast"] >= 18

    # Run frames are profile poses in battle. At the same 2.2x scale, every
    # frame must retain its natural face component and positive foot clearance.
    run_entries = anims["run"]["frames"]
    run_stage_height = max(
        round(entry["data"]["h"] * YONE_LIVE_CARD_SCALE)
        for entry in run_entries
    )
    assert run_stage_height == 117
    run_sizes: list[tuple[int, int]] = []
    run_stage_offsets: list[int] = []
    run_divider_clearances: list[int] = []
    run_source_bottoms: list[int] = []
    run_rendered_bottoms: list[int] = []
    visible_run_eye_cues = 0
    for index, entry in enumerate(run_entries):
        data = entry["data"]
        run_frame = sheet.crop(
            (
                data["x"],
                data["y"],
                data["x"] + data["w"],
                data["y"] + data["h"],
            )
        )
        live_run = run_frame.resize(
            (
                round(data["w"] * YONE_LIVE_CARD_SCALE),
                round(data["h"] * YONE_LIVE_CARD_SCALE),
            ),
            Image.Resampling.NEAREST,
        )
        run_sizes.append(live_run.size)
        run_bbox = live_run.getchannel("A").getbbox()
        source_bbox = run_frame.getchannel("A").getbbox()
        assert run_bbox is not None and source_bbox is not None
        stage_y = (run_stage_height - live_run.height) // 2
        run_stage_offsets.append(stage_y)
        run_divider_clearances.append(
            YONE_LIVE_CARD_DIVIDER_TOP - (stage_y + run_bbox[3])
        )
        run_source_bottoms.append(run_frame.height - source_bbox[3])
        run_rendered_bottoms.append(live_run.height - run_bbox[3])
        source_quality = build_yone.yone_face_readability(run_frame)
        _assert_natural_face_quality(
            source_quality,
            minimum_width=4,
            minimum_height=3,
            minimum_skin=6,
            minimum_contrast=50,
            near_white_budget=2,
        )
        assert source_quality["red_mask_pixels"] >= 20
        visible_run_eye_cues += 1
        scaled_quality = build_yone.yone_live_card_idle_metrics(
            run_frame,
            stage_height=run_stage_height,
            center_y=build_yone.YONE_LIVE_CARD_AUDITED_CENTER_Y,
            variant="profile",
        )
        _assert_scaled_source_face_quality(
            scaled_quality,
            near_white_budget=2,
            minimum_contrast=50,
        )
        rendered_face = scaled_quality["rendered_face_skin_bbox"]
        assert rendered_face[2] - rendered_face[0] >= 8
        assert rendered_face[3] - rendered_face[1] >= 6
        assert scaled_quality["rendered_face_skin_pixels"] >= 24
        assert scaled_quality["rendered_size"] == list(live_run.size)
        assert scaled_quality["stage_y"] == stage_y
        assert scaled_quality["source_bottom_clearance"] == run_source_bottoms[-1]
        assert scaled_quality["rendered_bottom_clearance"] == run_rendered_bottoms[-1]
        assert scaled_quality["divider_clearance"] == run_divider_clearances[-1]

    assert run_sizes == [
        (90, 108),
        (86, 112),
        (86, 117),
        (86, 112),
        (90, 108),
        (86, 112),
        (86, 117),
        (86, 112),
    ]
    assert run_stage_offsets == [4, 2, 0, 2, 4, 2, 0, 2]
    assert run_source_bottoms == native_bottoms["run"]
    assert all(clearance >= YONE_LIVE_CARD_MIN_DIVIDER_CLEARANCE for clearance in run_divider_clearances)
    assert all(bottom > 0 for bottom in run_rendered_bottoms)
    assert visible_run_eye_cues == len(run_entries)


def test_yone_runtime_routes_rectangular_and_square_compact_surfaces_only() -> None:
    source = RUNTIME.read_text(encoding="utf-8")
    scoreboard_body = _function_body(source, "is_yone_scoreboard_portrait_geometry")
    compact_body = _function_body(source, "is_yone_compact_portrait_geometry")
    grid_body = _function_body(source, "is_yone_bp_grid_geometry")

    scoreboard_width = _range_contract(scoreboard_body, "width")
    scoreboard_height = _range_contract(scoreboard_body, "height")
    ratio_floor_match = re.search(r"height / width >= ([0-9.]+)", scoreboard_body)
    ratio_limit_match = re.search(r"height / width <= ([0-9.]+)", scoreboard_body)
    assert ratio_floor_match is not None
    assert ratio_limit_match is not None
    ratio_floor = float(ratio_floor_match.group(1))
    ratio_limit = float(ratio_limit_match.group(1))

    compact_width = _range_contract(compact_body, "width")
    compact_height = _range_contract(compact_body, "height")
    square_delta_match = re.search(r"\(width - height\)\.abs\(\) <= ([0-9.]+)", compact_body)
    assert square_delta_match is not None
    square_delta = float(square_delta_match.group(1))

    grid_width = _range_contract(grid_body, "width")
    grid_height = _range_contract(grid_body, "height")

    def is_scoreboard(width: float, height: float) -> bool:
        if not (scoreboard_width[0] <= width <= scoreboard_width[1]):
            return False
        if not (scoreboard_height[0] <= height <= scoreboard_height[1]):
            return False
        return width >= scoreboard_width[0] and ratio_floor <= height / width <= ratio_limit

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
    ) < rewrite.index(
        "YONE_BP_GRID_PORTRAIT_TEXTURE"
    )
    for forbidden in ("let side =", "*w = side", "*h = side"):
        assert forbidden not in rewrite
    # All three portrait surfaces preserve native command geometry; only the
    # texture and full UV are replaced, so row alignment cannot shift.
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
    dual_blader_branch = contract[contract.index('champion_id == "dual_blader"') :]
    assert "width: BP_DUAL_BLADER_ACTOR_WIDTH" in dual_blader_branch
    assert "height: BP_DUAL_BLADER_ACTOR_HEIGHT" in dual_blader_branch
    assert "min_width: BP_DUAL_BLADER_TRANSITION_MIN_WIDTH" in dual_blader_branch
    assert "max_width: BP_DUAL_BLADER_TRANSITION_MAX_WIDTH" in dual_blader_branch
    assert "min_height: BP_DUAL_BLADER_TRANSITION_MIN_HEIGHT" in dual_blader_branch
    assert "max_height: BP_DUAL_BLADER_TRANSITION_MAX_HEIGHT" in dual_blader_branch
