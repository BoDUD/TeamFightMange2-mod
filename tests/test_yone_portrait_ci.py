from __future__ import annotations

import hashlib
import importlib.util
import inspect
import json
import re
from pathlib import Path

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
YONE_ACTOR_ALPHA_SHA256 = (
    "bb67379ae006097a709ee53ae24f91605efe679f6d2ef667725fb976e115fbf7"
)
YONE_FULLBODY_ALPHA_SHA256 = (
    "a2791f76396c85d976c725fb9d6ea8b7e15e0acc328daa828da0414dec47ff8a"
)


def _load_build_yone():
    spec = importlib.util.spec_from_file_location("build_yone", GENERATOR)
    assert spec is not None and spec.loader is not None
    build_yone = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(build_yone)
    return build_yone


def _assert_no_synthetic_face_markers(quality: dict[str, object]) -> None:
    assert quality["semantic_feature_pixels"] == 0, quality
    for key in (
        "eye_positions",
        "pupil_positions",
        "iris_positions",
        "nose_positions",
        "mouth_positions",
    ):
        assert quality[key] == [], quality
    assert quality["retired_template_pixels"] == 0, quality


def _assert_natural_face_quality(quality: dict[str, object]) -> None:
    """Validate the source-authored natural 3/4 face, not painted markers."""

    _assert_no_synthetic_face_markers(quality)
    assert quality["skin_locked_features"] is True, quality
    assert quality["face_skin_bbox"] is not None, quality
    assert quality["minimal_feature_set"] is True, quality
    assert int(quality["natural_dark_feature_pixels"]) >= 1, quality
    assert float(quality["face_contrast"]) >= 30, quality
    assert int(quality["near_white_pixels"]) <= max(
        2, int(quality["face_skin_pixels"]) // 20
    ), quality


def _assert_adult_proportions(quality: dict[str, object]) -> None:
    body = quality["body_bbox"]
    face = quality["face_skin_bbox"]
    assert body is not None and face is not None, quality
    body_height = body[3] - body[1]
    face_height = face[3] - face[1]
    assert body_height >= 30, quality
    assert face_height / body_height <= 0.40, quality


def _assert_scaled_source_face_quality(
    quality: dict[str, object], *, near_white_budget: int, require_dark: bool = True
) -> None:
    assert quality["marker_projection_valid"] is True, quality
    assert quality["marker_spans_valid"] is True, quality
    assert quality["rendered_feature_order"] is True, quality
    assert quality["source_face_skin_bbox"] is not None, quality
    assert quality["rendered_face_skin_bbox"] is not None, quality
    assert quality["eye_component_boxes"] == [], quality
    assert quality["pupil_component_boxes"] == [], quality
    assert quality["iris_component_boxes"] == [], quality
    assert quality["nose_component_boxes"] == [], quality
    assert quality["mouth_component_boxes"] == [], quality
    assert int(quality["source_near_white_pixels"]) <= near_white_budget, quality
    assert float(quality["source_face_contrast"]) >= 30, quality
    if require_dark:
        assert int(quality["source_natural_dark_feature_pixels"]) >= 1, quality


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
    assert set(surfaces) == set(build_yone.YONE_UI_FACE_RECIPES)
    for name, image in surfaces.items():
        recipe = build_yone.YONE_UI_FACE_RECIPES[name]
        quality = build_yone.yone_face_readability(image, recipe["window"])
        _assert_natural_face_quality(quality)
        assert quality["eye_pixels"] == quality["nose_pixels"] == 0, (name, quality)
        assert quality["mouth_pixels"] == 0, (name, quality)

    generator = GENERATOR.read_text(encoding="utf-8")
    assert "YONE_UI_FACE_RECIPES" in generator
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
        "complete adult-proportioned ImageGen body-model replacement with a "
        "source-authored 3/4-view face and NEAREST native sampling; no "
        "post-scale face repaint or synthetic feature overlay"
    )
    assert contract["actor_resampling"] == "NEAREST"
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
    assert (
        hashlib.sha256(fullbody.getchannel("A").tobytes()).hexdigest()
        == YONE_FULLBODY_ALPHA_SHA256
    )

    route = build_yone.yone_fullbody_card_contract(fullbody)
    assert route["source_size"] == [64, 64]
    assert route["rendered_size"] == [85, 93]
    assert route["resampling"] == "nearest"
    assert route["source_alpha_bbox"] == [5, 6, 59, 60]
    assert route["rendered_alpha_bbox"] == [7, 9, 78, 87]
    assert route["source_bottom_margin"] == 4
    assert route["rendered_bottom_margin"] == 6
    assert route["source_last_alpha_row"] == [59, 19, 43]
    assert route["rendered_last_alpha_row"] == [86, 25, 57]
    assert route["source_toned_skin_pixels"] == 0
    assert route["source_red_mask_pixels"] >= 60
    assert route["source_red_mask_bbox"] == [18, 9, 42, 37]
    _assert_scaled_source_face_quality(route, near_white_budget=4)
    source_face = route["source_face_skin_bbox"]
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
    anims = json.loads(ACTOR_ANIM.read_text(encoding="utf-8"))["anims"]
    frames = list(build_yone.iter_actor_body_frames(anims))
    assert len(frames) == 54
    observed: set[tuple[str, int]] = set()
    occluded_run_profiles = 0
    normalized_w_frames: list[Image.Image] = []
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
        quality = build_yone.yone_face_readability(frame)
        _assert_no_synthetic_face_markers(quality)
        if tag == "dead":
            assert quality["red_mask_pixels"] >= 10, (tag, index, quality)
            continue
        if tag == "skill2_attack":
            normalized = Image.new("RGBA", (61, 55), (0, 0, 0, 0))
            normalized.alpha_composite(
                frame,
                ((61 - data["w"]) // 2, (55 - data["h"]) // 2),
            )
            normalized_w_frames.append(normalized)
            continue

        face_bbox = quality["face_skin_bbox"]
        if not quality["minimal_feature_set"]:
            assert tag == "run" and face_bbox is not None, (tag, index, quality)
            assert face_bbox[2] - face_bbox[0] >= 3, (tag, index, quality)
            assert face_bbox[3] - face_bbox[1] >= 5, (tag, index, quality)
            assert quality["face_skin_pixels"] >= 8, (tag, index, quality)
            assert quality["face_contrast"] >= 30, (tag, index, quality)
            assert quality["red_mask_pixels"] >= 20, (tag, index, quality)
            assert quality["near_white_pixels"] <= 2, (tag, index, quality)
            occluded_run_profiles += 1
        else:
            _assert_natural_face_quality(quality)
            _assert_adult_proportions(quality)

    assert len(observed) == 54
    assert occluded_run_profiles <= 1
    assert len(normalized_w_frames) == 5
    common_body = normalized_w_frames[0].copy()
    for y in range(common_body.height):
        for x in range(common_body.width):
            pixel = common_body.getpixel((x, y))
            if pixel[3] < 128 or any(
                frame.getpixel((x, y)) != pixel
                for frame in normalized_w_frames[1:]
            ):
                common_body.putpixel((x, y), (0, 0, 0, 0))
    common_bbox = common_body.getchannel("A").getbbox()
    assert common_bbox is not None and common_bbox[3] - common_bbox[1] >= 30
    common_alpha = common_body.getchannel("A")
    common_alpha_values = (
        common_alpha.get_flattened_data()
        if hasattr(common_alpha, "get_flattened_data")
        else common_alpha.getdata()
    )
    assert sum(1 for alpha in common_alpha_values if alpha) >= 250
    common_face = build_yone.yone_face_readability(common_body)
    _assert_natural_face_quality(common_face)
    _assert_adult_proportions(common_face)


def test_yone_idle0_is_nearest_sampled_without_post_scale_face_repaint() -> None:
    """The packed idle is the accepted source model, not a synthetic face pass."""

    build_yone = _load_build_yone()
    first_idle = build_yone.split_grid(
        Image.open(build_yone.CORE_ALPHA).convert("RGBA"),
        5,
        4,
    )[0]
    rect = build_yone.NATIVE_CONTRACT["idle"]["rects"][0]
    expected = build_yone.fit_actor(
        first_idle,
        (rect[2], rect[3]),
        build_yone.BODY_TARGET_HEIGHTS["idle"][0],
        build_yone.BODY_BOTTOM_MARGINS["idle"][0],
        ("idle", 0),
    )
    sheet = Image.open(ACTOR_SHEET).convert("RGBA")
    final_idle = sheet.crop(
        (rect[0], rect[1], rect[0] + rect[2], rect[1] + rect[3])
    )
    assert expected.tobytes() == final_idle.tobytes()
    fit_actor_source = inspect.getsource(build_yone.fit_actor)
    actor_source = inspect.getsource(build_yone.build_actor)
    assert "Image.Resampling.NEAREST" in fit_actor_source
    assert "Image.Resampling.BOX" not in fit_actor_source
    assert "finish_imagegen_yone_idle_face" not in GENERATOR.read_text(
        encoding="utf-8"
    )
    assert "repaint_yone_face(" not in actor_source

    quality = build_yone.yone_face_readability(final_idle)
    _assert_natural_face_quality(quality)
    _assert_adult_proportions(quality)
    assert quality["body_bbox"] == [2, 1, 40, 39]
    assert quality["face_skin_bbox"] == [18, 8, 24, 17]
    assert quality["natural_dark_feature_positions"] == [[19, 9], [21, 10]]


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
    assert smallest["opaque"] >= 220
    assert smallest["colors"] >= 50
    assert smallest["contrast"] >= 180
    assert smallest["red_mask"] >= 30
    assert smallest["skin"] >= 18

    regular = _runtime_scoreboard_metrics((30, 38))
    assert regular["opaque"] >= 520
    assert regular["colors"] >= 80
    assert regular["contrast"] >= 180
    assert regular["red_mask"] >= 80
    assert regular["skin"] >= 55

    recipe = build_yone.YONE_UI_FACE_RECIPES["scoreboard"]
    for size in ((18, 26), (30, 38)):
        rendered = scoreboard.resize(size, Image.Resampling.NEAREST)
        quality = build_yone.yone_face_readability(rendered, recipe["window"])
        _assert_natural_face_quality(quality)
        assert quality["face_contrast"] >= 100, (size, quality)
        assert quality["red_mask_pixels"] >= (13 if size == (18, 26) else 30)

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
    assert (
        hashlib.sha256(sheet.getchannel("A").tobytes()).hexdigest()
        == YONE_ACTOR_ALPHA_SHA256
    )

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

    # Replay the actual renderer route inferred from the user's rejected live
    # capture: each native idle rectangle is uniformly enlarged by about 2.2x
    # and vertically centered on the tallest idle stage.  The latest rejected
    # screenshot exactly matched idle[0], while all four animation frames must
    # retain the same source-authored 3/4 face and foot gap.
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
        _assert_natural_face_quality(source_quality)
        _assert_adult_proportions(source_quality)
        scaled_quality = build_yone.yone_live_card_idle_metrics(
            idle_frame,
            stage_height=stage_height,
            center_y=style["center"]["y"],
            variant="front",
        )
        scaled_idle_metrics.append(scaled_quality)
        _assert_scaled_source_face_quality(scaled_quality, near_white_budget=1)
        assert scaled_quality["rendered_size"] == list(live_idle.size)
        assert scaled_quality["stage_y"] == stage_y
        assert scaled_quality["projected_alpha_bbox"][3] == projected_bottom
        assert scaled_quality["divider_clearance"] == divider_clearance
        assert scaled_quality["source_toned_skin_pixels"] <= 32

    assert rendered_sizes == [(95, 121), (95, 117), (95, 112), (95, 117)]
    assert stage_offsets == [0, 2, 4, 2]
    assert projected_bottoms == [86, 86, 85, 86]
    assert divider_clearances == [13, 13, 14, 13]

    # This is the exact source/render path matched against the user's card.
    # Lock the accepted adult body and natural face component.  Synthetic eye,
    # nose and mouth marker boxes must remain absent after NEAREST projection.
    idle0 = scaled_idle_metrics[0]
    assert idle0["source_size"] == [43, 55]
    assert idle0["rendered_size"] == [95, 121]
    assert idle0["stage_y"] == 0
    assert idle0["alpha_bbox"] == [4, 2, 88, 86]
    assert idle0["projected_alpha_bbox"] == [4, 2, 88, 86]
    assert idle0["source_bottom_clearance"] == 16
    assert idle0["rendered_bottom_clearance"] == 35
    assert idle0["divider_clearance"] == 13
    assert idle0["source_face_skin_bbox"] == [18, 8, 24, 17]
    assert idle0["rendered_face_skin_bbox"] == [40, 18, 53, 37]
    assert idle0["eye_component_boxes"] == []
    assert idle0["pupil_component_boxes"] == []
    assert idle0["iris_component_boxes"] == []
    assert idle0["nose_component_boxes"] == []
    assert idle0["mouth_component_boxes"] == []
    assert idle0["source_toned_skin_pixels"] == 0
    assert idle0["source_bright_face_skin_pixels"] == 11
    assert idle0["source_max_face_skin_luminance"] == 215.324

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
        _assert_no_synthetic_face_markers(source_quality)
        face_bbox = source_quality["face_skin_bbox"]
        assert face_bbox is not None
        assert face_bbox[2] - face_bbox[0] >= 3
        assert face_bbox[3] - face_bbox[1] >= 5
        assert source_quality["face_skin_pixels"] >= 8
        assert source_quality["face_contrast"] >= 30
        assert source_quality["red_mask_pixels"] >= 20
        assert source_quality["near_white_pixels"] <= 2
        if source_quality["natural_dark_feature_pixels"] >= 1:
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
            require_dark=source_quality["natural_dark_feature_pixels"] >= 1,
        )
        assert scaled_quality["rendered_size"] == list(live_run.size)
        assert scaled_quality["stage_y"] == stage_y
        assert scaled_quality["source_bottom_clearance"] == run_source_bottoms[-1]
        assert scaled_quality["rendered_bottom_clearance"] == run_rendered_bottoms[-1]
        assert scaled_quality["divider_clearance"] == run_divider_clearances[-1]
        assert scaled_quality["source_toned_skin_pixels"] <= 32

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
    assert visible_run_eye_cues >= 7


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
