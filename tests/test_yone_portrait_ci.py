from __future__ import annotations

import importlib.util
import json
import re
from pathlib import Path

from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parents[1]
MOD = ROOT / "mods" / "lol_mod"
RUNTIME = MOD / "src" / "lib.rs"
GENERATOR = MOD / "tools" / "build_yone.py"
COMPACT = MOD / "ui" / "champion_portrait" / "dual_blader_compact.png"
SCOREBOARD = MOD / "ui" / "champion_portrait" / "dual_blader_scoreboard.png"
GRID = MOD / "ui" / "champion_portrait" / "dual_blader_grid.png"
ACTOR_SHEET = MOD / "aseprite_resources/champions/yone#sheet.png"
ACTOR_ANIM = MOD / "aseprite_resources/champions/yone#anim.fanim"
CHAMPION_VIEW = MOD / "style/champion_view.champion_view"
YONE_FACE_FEATURE_RGBA = (24, 14, 19, 255)
YONE_FACE_SCLERA_RGBA = (212, 178, 157, 255)
YONE_FACE_MOUTH_RGBA = (124, 50, 53, 255)
YONE_FACE_OUTLINE_RGBA = (18, 16, 23, 255)
YONE_FACE_SHADOW_RGBA = (122, 62, 54, 255)
YONE_FACE_MID_RGBA = (178, 101, 77, 255)
YONE_FACE_LIGHT_RGBA = (202, 129, 98, 255)
YONE_LIVE_CARD_SCALE = 2.2
YONE_LIVE_CARD_DIVIDER_TOP = 99
YONE_LIVE_CARD_MIN_DIVIDER_CLEARANCE = 10
YONE_ACTOR_FACE_WINDOW = (0.18, 0.00, 0.98, 0.58)
YONE_FOCUSED_UI_FACE_WINDOW = (0.35, 0.08, 0.98, 0.70)


def _pixel_components(
    points: set[tuple[int, int]],
) -> list[set[tuple[int, int]]]:
    remaining = set(points)
    components: list[set[tuple[int, int]]] = []
    while remaining:
        seed = remaining.pop()
        component = {seed}
        queue = [seed]
        while queue:
            x, y = queue.pop()
            for yy in range(y - 1, y + 2):
                for xx in range(x - 1, x + 2):
                    point = (xx, yy)
                    if point in remaining:
                        remaining.remove(point)
                        component.add(point)
                        queue.append(point)
        components.append(component)
    return components


def _component_bbox(
    component: set[tuple[int, int]],
) -> tuple[int, int, int, int]:
    return (
        min(x for x, _ in component),
        min(y for _, y in component),
        max(x for x, _ in component) + 1,
        max(y for _, y in component) + 1,
    )


def _portrait_face_metrics(
    image: Image.Image,
    window: tuple[float, float, float, float],
) -> dict[str, object]:
    body = image.getchannel("A").getbbox()
    assert body is not None
    left, top, right, bottom = body
    width = right - left
    height = bottom - top
    roi = (
        left + round(width * window[0]),
        top + round(height * window[1]),
        left + round(width * window[2]),
        top + round(height * window[3]),
    )
    feature = {
        (x, y)
        for y in range(roi[1], roi[3])
        for x in range(roi[0], roi[2])
        if image.getpixel((x, y)) == YONE_FACE_FEATURE_RGBA
    }
    assert feature
    sclera = {
        (x, y)
        for y in range(roi[1], roi[3])
        for x in range(roi[0], roi[2])
        if image.getpixel((x, y)) == YONE_FACE_SCLERA_RGBA
    }
    eye = feature | sclera
    feature_box = (
        min(x for x, _ in eye),
        min(y for _, y in eye),
        max(x for x, _ in eye) + 1,
        max(y for _, y in eye) + 1,
    )
    local = (
        max(roi[0], feature_box[0] - 5),
        max(roi[1], feature_box[1] - 4),
        min(roi[2], feature_box[2] + 5),
        min(image.height, feature_box[3] + 6),
    )
    warm = {
        (x, y)
        for y in range(local[1], local[3])
        for x in range(local[0], local[2])
        if (
            (pixel := image.getpixel((x, y)))[3] >= 128
            and pixel[0] >= 135
            and pixel[1] >= 70
            and pixel[2] >= 45
            and pixel[0] > pixel[1]
            and pixel[1] >= pixel[2] * 0.72
        )
    }
    components: list[set[tuple[int, int]]] = []
    while warm:
        seed = warm.pop()
        component = {seed}
        queue = [seed]
        while queue:
            x, y = queue.pop()
            for yy in range(y - 1, y + 2):
                for xx in range(x - 1, x + 2):
                    point = (xx, yy)
                    if point in warm:
                        warm.remove(point)
                        component.add(point)
                        queue.append(point)
        components.append(component)
    largest_warm = max(components, key=len) if components else set()
    warm_bbox = (
        None
        if not largest_warm
        else (
            min(x for x, _ in largest_warm),
            min(y for _, y in largest_warm),
            max(x for x, _ in largest_warm) + 1,
            max(y for _, y in largest_warm) + 1,
        )
    )
    horizontal_pair = len(feature) == 2 and len({y for _, y in feature}) == 1
    horizontal_separation = (
        max(x for x, _ in feature) - min(x for x, _ in feature)
        if horizontal_pair
        else 0
    )
    ordered_feature = sorted(feature)
    ordered_sclera = sorted(sclera)
    front_eye_pair = (
        horizontal_pair
        and horizontal_separation == 3
        and len(ordered_sclera) == 1
        and len({y for _, y in (*ordered_feature, *ordered_sclera)}) == 1
        and ordered_sclera[0][0] == ordered_feature[1][0] - 1
    )
    profile_eye_pair = (
        len(ordered_feature) == 1
        and len(ordered_sclera) == 1
        and ordered_feature[0][1] == ordered_sclera[0][1]
        and ordered_sclera[0][0] == ordered_feature[0][0] - 1
    )
    warm_gray_near_eye_pair = front_eye_pair or profile_eye_pair
    eye_orientation = "front" if front_eye_pair else "profile"
    mouth = {
        (x, y)
        for y in range(local[1], local[3])
        for x in range(local[0], local[2])
        if image.getpixel((x, y)) == YONE_FACE_MOUTH_RGBA
    }
    template_row_counts: list[int] = []
    nose_highlight_offset = False
    template_bounds = local
    if front_eye_pair or profile_eye_pair:
        if front_eye_pair:
            left_eye = ordered_feature[0]
            anchor_x = left_eye[0] - 2
            anchor_y = left_eye[1] - 2
        else:
            near_pupil = ordered_feature[0]
            anchor_x = near_pupil[0] - 5
            anchor_y = near_pupil[1] - 2
        nose_point = (anchor_x + 3, anchor_y + 3)
        template_bounds = (
            max(0, anchor_x),
            max(0, anchor_y),
            min(image.width, anchor_x + 7),
            min(image.height, anchor_y + 7),
        )
        template_palette = {
            YONE_FACE_SHADOW_RGBA,
            YONE_FACE_MID_RGBA,
            YONE_FACE_LIGHT_RGBA,
            YONE_FACE_FEATURE_RGBA,
            YONE_FACE_SCLERA_RGBA,
            YONE_FACE_MOUTH_RGBA,
        }
        template_row_counts = [
            sum(
                1
                for x in range(anchor_x, anchor_x + 7)
                if 0 <= x < image.width
                and 0 <= y < image.height
                and image.getpixel((x, y)) in template_palette
            )
            for y in range(anchor_y, anchor_y + 7)
        ]
        nose_highlight_offset = (
            0 <= nose_point[0] < image.width
            and 0 <= nose_point[1] < image.height
            and image.getpixel(nose_point) == YONE_FACE_LIGHT_RGBA
        )
    template_three_quarter = (
        len(template_row_counts) == 7
        and 0 <= template_row_counts[0] <= 3
        and 3 <= template_row_counts[1] <= 6
        and 5 <= template_row_counts[2] <= 7
        and 5 <= template_row_counts[3] <= 7
        and 3 <= template_row_counts[4] <= 5
        and 2 <= template_row_counts[5] <= 4
        and 1 <= template_row_counts[6] <= 3
        and 22 <= sum(template_row_counts) <= 35
        and nose_highlight_offset
    )
    eye_warm_neighbor_counts = [
        sum(
            1
            for point in (
                (x - 1, y),
                (x + 1, y),
                (x, y - 1),
                (x, y + 1),
            )
            if point in largest_warm
        )
        for x, y in sorted(feature)
    ]
    light = {
        (x, y)
        for y in range(template_bounds[1], template_bounds[3])
        for x in range(template_bounds[0], template_bounds[2])
        if image.getpixel((x, y))
        in {YONE_FACE_LIGHT_RGBA, YONE_FACE_SCLERA_RGBA}
    }
    max_vertical_light_run = 0
    for x in {point[0] for point in light}:
        run = 0
        previous_y: int | None = None
        for y in sorted(point[1] for point in light if point[0] == x):
            run = run + 1 if previous_y is not None and y == previous_y + 1 else 1
            previous_y = y
            max_vertical_light_run = max(max_vertical_light_run, run)
    return {
        "feature_pixels": len(feature),
        "feature_pair": any(
            (x + 1, y) in feature or (x, y + 1) in feature
            for x, y in feature
        ),
        "sclera_pixels": len(sclera),
        "sclera_positions": sorted(sclera),
        "feature_horizontal_pair": horizontal_pair,
        "feature_horizontal_separation": horizontal_separation,
        "near_eye_pair": warm_gray_near_eye_pair,
        "warm_gray_near_eye_pair": warm_gray_near_eye_pair,
        "front_eye_pair": front_eye_pair,
        "profile_eye_pair": profile_eye_pair,
        "dark_eye_pair": front_eye_pair,
        "eye_orientation": eye_orientation,
        "eye_warm_neighbor_counts": eye_warm_neighbor_counts,
        "eye_under_skin": bool(feature)
        and all((x, y + 1) in largest_warm for x, y in feature),
        "mouth_pixels": len(mouth),
        "mouth_positions": sorted(mouth),
        "mouth_below_eyes": len(mouth) == 1
        and bool(feature)
        and next(iter(mouth))[1] >= max(y for _, y in feature) + 3,
        "template_row_counts": template_row_counts,
        "template_three_quarter": template_three_quarter,
        "nose_highlight_offset": nose_highlight_offset,
        "max_vertical_light_run": max_vertical_light_run,
        "cross_junction": max_vertical_light_run > 1,
        "warm_component": len(largest_warm),
        "warm_bbox": warm_bbox,
        "near_white": sum(
            1
            for y in range(local[1], local[3])
            for x in range(local[0], local[2])
            if (pixel := image.getpixel((x, y)))[3] >= 128
            and min(pixel[:3]) >= 218
            and max(pixel[:3]) - min(pixel[:3]) <= 45
        ),
    }


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


def test_yone_ui_faces_use_a_lucian_style_warm_gray_near_eye_plane() -> None:
    surfaces = {
        "compact": (
            Image.open(COMPACT).convert("RGBA"),
            YONE_FOCUSED_UI_FACE_WINDOW,
            12,
        ),
        "scoreboard": (
            Image.open(SCOREBOARD).convert("RGBA"),
            YONE_FOCUSED_UI_FACE_WINDOW,
            12,
        ),
        "grid": (
            Image.open(GRID).convert("RGBA"),
            YONE_ACTOR_FACE_WINDOW,
            12,
        ),
    }
    for name, (image, window, minimum_warm) in surfaces.items():
        metrics = _portrait_face_metrics(image, window)
        assert metrics["feature_pixels"] == 2, (name, metrics)
        assert metrics["sclera_pixels"] == 1, (name, metrics)
        assert metrics["feature_pair"] is False, (name, metrics)
        assert metrics["feature_horizontal_pair"] is True, (name, metrics)
        assert metrics["feature_horizontal_separation"] == 3, (name, metrics)
        assert metrics["near_eye_pair"] is True, (name, metrics)
        assert metrics["warm_gray_near_eye_pair"] is True, (name, metrics)
        assert metrics["front_eye_pair"] is True, (name, metrics)
        assert metrics["profile_eye_pair"] is False, (name, metrics)
        assert metrics["dark_eye_pair"] is True, (name, metrics)
        assert metrics["eye_orientation"] == "front", (name, metrics)
        assert metrics["mouth_pixels"] == 1, (name, metrics)
        assert metrics["mouth_below_eyes"] is True, (name, metrics)
        assert metrics["eye_under_skin"] is True, (name, metrics)
        assert min(metrics["eye_warm_neighbor_counts"]) >= 2, (name, metrics)
        assert metrics["template_three_quarter"] is True, (name, metrics)
        assert metrics["nose_highlight_offset"] is True, (name, metrics)
        assert len(metrics["template_row_counts"]) == 7, (name, metrics)
        assert metrics["max_vertical_light_run"] <= 1, (name, metrics)
        assert metrics["cross_junction"] is False, (name, metrics)
        assert metrics["warm_component"] >= minimum_warm, (name, metrics)
        assert isinstance(metrics["warm_bbox"], tuple), (name, metrics)
        assert metrics["near_white"] == 0, (name, metrics)

    generator = GENERATOR.read_text(encoding="utf-8")
    assert "return repaint_yone_face(output, face_window)" in generator
    assert "stamp_yone_face_template" not in generator
    assert "YONE_FACE_REPAIR_TEMPLATE" not in generator
    assert "face repair changed alpha geometry" in generator
    assert "YONE_FOCUSED_UI_FACE_WINDOW" in generator
    assert "_paint_yone_face_plane" in generator
    assert "YONE_FACE_FRONT_TEMPLATE" in generator
    assert "YONE_FACE_PROFILE_TEMPLATE" in generator
    assert "YONE_FACE_MOUTH_RGBA" in generator


def test_all_54_yone_battle_faces_are_clear_and_repaint_is_idempotent() -> None:
    spec = importlib.util.spec_from_file_location("build_yone", GENERATOR)
    assert spec is not None and spec.loader is not None
    build_yone = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(build_yone)

    sheet = Image.open(
        ACTOR_SHEET
    ).convert("RGBA")
    anims = json.loads(
        ACTOR_ANIM.read_text(
            encoding="utf-8"
        )
    )["anims"]
    frames = list(build_yone.iter_actor_body_frames(anims))
    assert len(frames) == 54
    front_frames = set(build_yone.YONE_FRONT_FACE_FRAMES)
    profile_frames = set(build_yone.YONE_PROFILE_FACE_FRAMES)
    single_eye_frames = set(build_yone.YONE_SINGLE_EYE_PROFILE_FRAMES)
    assert len(front_frames) == 13
    assert len(profile_frames) == 39
    assert len(single_eye_frames) == 2
    assert not (front_frames & profile_frames)
    assert not (front_frames & single_eye_frames)
    assert not (profile_frames & single_eye_frames)
    assert front_frames | profile_frames | single_eye_frames == {
        (tag, index) for tag, index, _ in frames
    }
    observed_front_frames: set[tuple[str, int]] = set()
    observed_profile_frames: set[tuple[str, int]] = set()
    observed_single_eye_frames: set[tuple[str, int]] = set()
    for tag, index, entry in frames:
        data = entry["data"]
        frame = sheet.crop(
            (
                data["x"],
                data["y"],
                data["x"] + data["w"],
                data["y"] + data["h"],
            )
        )
        metrics = _portrait_face_metrics(frame, YONE_ACTOR_FACE_WINDOW)
        frame_key = (tag, index)
        if frame_key in single_eye_frames:
            assert metrics["feature_pixels"] == 1, (tag, index, metrics)
            assert metrics["sclera_pixels"] == 0, (tag, index, metrics)
            assert metrics["near_eye_pair"] is False, (tag, index, metrics)
            assert metrics["eye_orientation"] == "profile", (tag, index, metrics)
            observed_single_eye_frames.add(frame_key)
        elif frame_key in front_frames:
            assert metrics["feature_pixels"] == 2, (tag, index, metrics)
            assert metrics["sclera_pixels"] == 1, (tag, index, metrics)
            assert metrics["feature_pair"] is False, (tag, index, metrics)
            assert metrics["feature_horizontal_pair"] is True, (tag, index, metrics)
            assert metrics["feature_horizontal_separation"] == 3, (tag, index, metrics)
            assert metrics["warm_gray_near_eye_pair"] is True, (tag, index, metrics)
            assert metrics["front_eye_pair"] is True, (tag, index, metrics)
            assert metrics["profile_eye_pair"] is False, (tag, index, metrics)
            assert metrics["dark_eye_pair"] is True, (tag, index, metrics)
            assert metrics["eye_orientation"] == "front", (tag, index, metrics)
            observed_front_frames.add(frame_key)
        else:
            assert frame_key in profile_frames
            assert metrics["feature_pixels"] == 1, (tag, index, metrics)
            assert metrics["sclera_pixels"] == 1, (tag, index, metrics)
            assert metrics["feature_pair"] is False, (tag, index, metrics)
            assert metrics["feature_horizontal_pair"] is False, (tag, index, metrics)
            assert metrics["near_eye_pair"] is True, (tag, index, metrics)
            assert metrics["warm_gray_near_eye_pair"] is True, (tag, index, metrics)
            assert metrics["front_eye_pair"] is False, (tag, index, metrics)
            assert metrics["profile_eye_pair"] is True, (tag, index, metrics)
            assert metrics["dark_eye_pair"] is False, (tag, index, metrics)
            assert metrics["eye_orientation"] == "profile", (tag, index, metrics)
            sclera_x, sclera_y = metrics["sclera_positions"][0]
            pupil_x, pupil_y = next(
                (x, y)
                for y in range(frame.height)
                for x in range(frame.width)
                if frame.getpixel((x, y)) == YONE_FACE_FEATURE_RGBA
            )
            assert (sclera_x + 1, sclera_y) == (pupil_x, pupil_y)
            observed_profile_frames.add(frame_key)
        if frame_key not in single_eye_frames:
            assert metrics["mouth_pixels"] == 1, (tag, index, metrics)
            assert metrics["mouth_below_eyes"] is True, (tag, index, metrics)
            assert metrics["eye_under_skin"] is True, (tag, index, metrics)
            assert min(metrics["eye_warm_neighbor_counts"]) >= 2, (
                tag,
                index,
                metrics,
            )
            assert metrics["template_three_quarter"] is True, (tag, index, metrics)
            assert metrics["nose_highlight_offset"] is True, (tag, index, metrics)
            assert metrics["max_vertical_light_run"] <= 1, (tag, index, metrics)
            assert metrics["cross_junction"] is False, (tag, index, metrics)
        assert metrics["warm_component"] >= (
            1 if frame_key in single_eye_frames else 2
        ), (tag, index, metrics)
        assert isinstance(metrics["warm_bbox"], tuple), (tag, index, metrics)
        assert metrics["near_white"] == 0, (tag, index, metrics)
        assert build_yone.finalize_yone_battle_face(
            frame, (tag, index)
        ).tobytes() == frame.tobytes(), (
            tag,
            index,
        )
    assert observed_front_frames == front_frames
    assert observed_profile_frames == profile_frames
    assert observed_single_eye_frames == single_eye_frames


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
    assert smallest["skin"] >= 35

    regular = _runtime_scoreboard_metrics((30, 38))
    assert regular["opaque"] >= 520
    assert regular["colors"] >= 80
    assert regular["contrast"] >= 180
    assert regular["red_mask"] >= 80
    assert regular["skin"] >= 80

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

    # Replay the actual renderer route inferred from the user's rejected live
    # capture: each native idle rectangle is uniformly enlarged by about 2.2x
    # and vertically centered on the tallest idle stage.  The screenshot was
    # idle[2], so all four animation frames must retain the face and foot gap.
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
    idle_frames: list[Image.Image] = []
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
        idle_frames.append(idle_frame)
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

        live_eye_pixels = {
            (x, y)
            for y in range(live_idle.height)
            for x in range(live_idle.width)
            if live_idle.getpixel((x, y)) == YONE_FACE_FEATURE_RGBA
        }
        eye_boxes = sorted(
            (_component_bbox(component) for component in _pixel_components(live_eye_pixels)),
            key=lambda box: box[0],
        )
        assert len(eye_boxes) == 2, (index, eye_boxes)
        left_eye_box, right_eye_box = eye_boxes
        assert left_eye_box[1] == right_eye_box[1], (index, eye_boxes)
        assert left_eye_box[3] == right_eye_box[3], (index, eye_boxes)
        assert all(
            2 <= box[2] - box[0] <= 3 and 2 <= box[3] - box[1] <= 3
            for box in eye_boxes
        ), (index, eye_boxes)
        assert right_eye_box[0] - left_eye_box[2] >= 2, (index, eye_boxes)
        live_sclera_pixels = {
            (x, y)
            for y in range(live_idle.height)
            for x in range(live_idle.width)
            if live_idle.getpixel((x, y)) == YONE_FACE_SCLERA_RGBA
        }
        sclera_boxes = [
            _component_bbox(component)
            for component in _pixel_components(live_sclera_pixels)
        ]
        assert len(sclera_boxes) == 1, (index, sclera_boxes)
        sclera_box = sclera_boxes[0]
        assert sclera_box[1] == right_eye_box[1]
        assert sclera_box[3] == right_eye_box[3]
        assert 2 <= sclera_box[2] - sclera_box[0] <= 3
        assert 2 <= sclera_box[3] - sclera_box[1] <= 3
        assert sclera_box[2] == right_eye_box[0]

        live_mouth_pixels = {
            (x, y)
            for y in range(live_idle.height)
            for x in range(live_idle.width)
            if live_idle.getpixel((x, y)) == YONE_FACE_MOUTH_RGBA
        }
        mouth_boxes = [_component_bbox(component) for component in _pixel_components(live_mouth_pixels)]
        assert len(mouth_boxes) == 1, (index, mouth_boxes)
        mouth_box = mouth_boxes[0]
        assert mouth_box[1] >= max(left_eye_box[3], right_eye_box[3]) + 4
        assert (
            left_eye_box[0] - 3
            <= (mouth_box[0] + mouth_box[2]) / 2
            <= right_eye_box[2] + 3
        )

        source_eyes = sorted(
            (x, y)
            for y in range(idle_frame.height)
            for x in range(idle_frame.width)
            if idle_frame.getpixel((x, y)) == YONE_FACE_FEATURE_RGBA
        )
        source_sclera = sorted(
            (x, y)
            for y in range(idle_frame.height)
            for x in range(idle_frame.width)
            if idle_frame.getpixel((x, y)) == YONE_FACE_SCLERA_RGBA
        )
        assert len(source_eyes) == 2 and source_eyes[1][0] - source_eyes[0][0] == 3
        assert source_sclera == [(source_eyes[1][0] - 1, source_eyes[1][1])]
        anchor_x = source_eyes[0][0] - 2
        anchor_y = source_eyes[0][1] - 2
        nose_point = (anchor_x + 3, anchor_y + 3)
        nose_mask = Image.new("L", idle_frame.size, 0)
        nose_mask.putpixel(nose_point, 255)
        live_nose_mask = nose_mask.resize(live_idle.size, Image.Resampling.NEAREST)
        nose_box = live_nose_mask.getbbox()
        assert nose_box is not None
        assert all(
            live_idle.getpixel((x, y)) == YONE_FACE_LIGHT_RGBA
            for y in range(live_idle.height)
            for x in range(live_idle.width)
            if live_nose_mask.getpixel((x, y))
        ), (index, nose_box)
        eye_group = (*eye_boxes, *sclera_boxes)
        assert nose_box[1] >= max(box[3] for box in eye_group), (
            index,
            eye_group,
            nose_box,
        )
        assert (
            min(box[0] for box in eye_group) - 3
            <= (nose_box[0] + nose_box[2]) / 2
            <= max(box[2] for box in eye_group) + 3
        )

        template_mask = Image.new("L", idle_frame.size, 0)
        ImageDraw.Draw(template_mask).rectangle(
            (anchor_x, anchor_y, anchor_x + 6, anchor_y + 6),
            fill=255,
        )
        live_template_box = template_mask.resize(
            live_idle.size,
            Image.Resampling.NEAREST,
        ).getbbox()
        assert live_template_box is not None
        max_rendered_light_run = 0
        for x in range(live_template_box[0], live_template_box[2]):
            run = 0
            for y in range(live_template_box[1], live_template_box[3]):
                if live_idle.getpixel((x, y)) in {
                    YONE_FACE_LIGHT_RGBA,
                    YONE_FACE_SCLERA_RGBA,
                }:
                    run += 1
                    max_rendered_light_run = max(max_rendered_light_run, run)
                else:
                    run = 0
        assert max_rendered_light_run <= 3, (index, max_rendered_light_run)

    assert rendered_sizes == [(95, 121), (95, 117), (95, 112), (95, 117)]
    assert stage_offsets == [0, 2, 4, 2]
    assert projected_bottoms == [86, 86, 85, 86]
    assert divider_clearances == [13, 13, 14, 13]

    # Run frames are profile poses in battle.  At the same 2.2x scale, every
    # frame must preserve one adjacent warm-gray/pupil bar, its offset nose
    # and mouth, and positive projected foot clearance.
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

        pupil_pixels = {
            (x, y)
            for y in range(live_run.height)
            for x in range(live_run.width)
            if live_run.getpixel((x, y)) == YONE_FACE_FEATURE_RGBA
        }
        sclera_pixels = {
            (x, y)
            for y in range(live_run.height)
            for x in range(live_run.width)
            if live_run.getpixel((x, y)) == YONE_FACE_SCLERA_RGBA
        }
        pupil_boxes = [
            _component_bbox(component) for component in _pixel_components(pupil_pixels)
        ]
        sclera_boxes = [
            _component_bbox(component) for component in _pixel_components(sclera_pixels)
        ]
        assert len(pupil_boxes) == len(sclera_boxes) == 1, (
            index,
            pupil_boxes,
            sclera_boxes,
        )
        pupil_box, sclera_box = pupil_boxes[0], sclera_boxes[0]
        assert pupil_box[1] == sclera_box[1]
        assert pupil_box[3] == sclera_box[3]
        assert sclera_box[2] == pupil_box[0]
        assert all(
            2 <= box[2] - box[0] <= 3 and 2 <= box[3] - box[1] <= 3
            for box in (sclera_box, pupil_box)
        )

        source_pupils = sorted(
            (x, y)
            for y in range(run_frame.height)
            for x in range(run_frame.width)
            if run_frame.getpixel((x, y)) == YONE_FACE_FEATURE_RGBA
        )
        source_sclera = sorted(
            (x, y)
            for y in range(run_frame.height)
            for x in range(run_frame.width)
            if run_frame.getpixel((x, y)) == YONE_FACE_SCLERA_RGBA
        )
        assert len(source_pupils) == len(source_sclera) == 1
        assert (source_sclera[0][0] + 1, source_sclera[0][1]) == source_pupils[0]
        anchor_x = source_pupils[0][0] - 5
        anchor_y = source_pupils[0][1] - 2

        mouth_pixels = {
            (x, y)
            for y in range(live_run.height)
            for x in range(live_run.width)
            if live_run.getpixel((x, y)) == YONE_FACE_MOUTH_RGBA
        }
        mouth_boxes = [
            _component_bbox(component) for component in _pixel_components(mouth_pixels)
        ]
        assert len(mouth_boxes) == 1
        mouth_box = mouth_boxes[0]
        eye_left = sclera_box[0]
        eye_right = pupil_box[2]
        assert mouth_box[1] >= max(sclera_box[3], pupil_box[3]) + 4
        assert eye_left - 3 <= (mouth_box[0] + mouth_box[2]) / 2 <= eye_right + 3

        nose_point = (anchor_x + 3, anchor_y + 3)
        nose_mask = Image.new("L", run_frame.size, 0)
        nose_mask.putpixel(nose_point, 255)
        live_nose_mask = nose_mask.resize(live_run.size, Image.Resampling.NEAREST)
        nose_box = live_nose_mask.getbbox()
        assert nose_box is not None
        assert all(
            live_run.getpixel((x, y)) == YONE_FACE_LIGHT_RGBA
            for y in range(live_run.height)
            for x in range(live_run.width)
            if live_nose_mask.getpixel((x, y))
        )
        assert nose_box[1] >= max(sclera_box[3], pupil_box[3])
        assert eye_left - 3 <= (nose_box[0] + nose_box[2]) / 2 <= eye_right + 3

        template_mask = Image.new("L", run_frame.size, 0)
        ImageDraw.Draw(template_mask).rectangle(
            (anchor_x, anchor_y, anchor_x + 6, anchor_y + 6),
            fill=255,
        )
        template_box = template_mask.resize(
            live_run.size,
            Image.Resampling.NEAREST,
        ).getbbox()
        assert template_box is not None
        max_light_run = 0
        for x in range(template_box[0], template_box[2]):
            run = 0
            for y in range(template_box[1], template_box[3]):
                if live_run.getpixel((x, y)) in {
                    YONE_FACE_LIGHT_RGBA,
                    YONE_FACE_SCLERA_RGBA,
                }:
                    run += 1
                    max_light_run = max(max_light_run, run)
                else:
                    run = 0
        assert max_light_run <= 3, (index, max_light_run)

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

    idle_frame = idle_frames[0]

    # Pixel-perfect source crop used by the live card. The far pupil remains
    # one pixel while the near eye is a muted warm-gray/pupil pair.
    face_crop = idle_frame.crop((15, 4, 30, 19))
    crop_metrics = _portrait_face_metrics(face_crop, (0.0, 0.0, 1.0, 1.0))
    assert crop_metrics["feature_pixels"] == 2
    assert crop_metrics["sclera_pixels"] == 1
    assert crop_metrics["feature_pair"] is False
    assert crop_metrics["feature_horizontal_pair"] is True
    assert crop_metrics["feature_horizontal_separation"] == 3
    assert crop_metrics["near_eye_pair"] is True
    assert crop_metrics["warm_gray_near_eye_pair"] is True
    assert crop_metrics["front_eye_pair"] is True
    assert crop_metrics["profile_eye_pair"] is False
    assert crop_metrics["dark_eye_pair"] is True
    assert crop_metrics["eye_orientation"] == "front"
    assert crop_metrics["warm_component"] >= 18
    warm_bbox = crop_metrics["warm_bbox"]
    assert isinstance(warm_bbox, tuple)
    assert warm_bbox[2] - warm_bbox[0] >= 5
    assert warm_bbox[3] - warm_bbox[1] >= 5
    eyes = [
        (x, y)
        for y in range(face_crop.height)
        for x in range(face_crop.width)
        if face_crop.getpixel((x, y)) == YONE_FACE_FEATURE_RGBA
    ]
    sclera = [
        (x, y)
        for y in range(face_crop.height)
        for x in range(face_crop.width)
        if face_crop.getpixel((x, y)) == YONE_FACE_SCLERA_RGBA
    ]
    assert sclera == [(7, 5)]
    assert eyes == [(5, 5), (8, 5)]
    assert crop_metrics["mouth_positions"] == [(6, 8)]
    assert crop_metrics["mouth_below_eyes"] is True
    assert crop_metrics["eye_under_skin"] is True
    assert crop_metrics["eye_warm_neighbor_counts"] == [4, 2]
    assert crop_metrics["template_three_quarter"] is True
    assert crop_metrics["nose_highlight_offset"] is True
    assert crop_metrics["template_row_counts"] == [3, 5, 7, 7, 5, 3, 3]
    assert crop_metrics["max_vertical_light_run"] == 1
    assert crop_metrics["cross_junction"] is False

    pixels = list(
        face_crop.get_flattened_data()
        if hasattr(face_crop, "get_flattened_data")
        else face_crop.getdata()
    )
    assert pixels.count(YONE_FACE_SHADOW_RGBA) == 12
    assert pixels.count(YONE_FACE_MID_RGBA) == 16
    assert pixels.count(YONE_FACE_LIGHT_RGBA) == 1
    assert pixels.count(YONE_FACE_SCLERA_RGBA) == 1
    assert pixels.count(YONE_FACE_FEATURE_RGBA) == 2
    assert pixels.count(YONE_FACE_MOUTH_RGBA) == 1
    assert pixels.count(YONE_FACE_OUTLINE_RGBA) >= 4

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
