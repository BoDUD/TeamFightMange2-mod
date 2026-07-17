from __future__ import annotations

import importlib.util
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
ACTOR_SHEET = MOD / "aseprite_resources/champions/yone#sheet.png"
ACTOR_ANIM = MOD / "aseprite_resources/champions/yone#anim.fanim"
CHAMPION_VIEW = MOD / "style/champion_view.champion_view"
YONE_FACE_FEATURE_RGBA = (54, 24, 29, 255)
YONE_ACTOR_FACE_WINDOW = (0.18, 0.00, 0.98, 0.58)
YONE_FOCUSED_UI_FACE_WINDOW = (0.35, 0.08, 0.98, 0.70)


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
    feature_box = (
        min(x for x, _ in feature),
        min(y for _, y in feature),
        max(x for x, _ in feature) + 1,
        max(y for _, y in feature) + 1,
    )
    local = (
        max(roi[0], feature_box[0] - 3),
        max(roi[1], feature_box[1] - 2),
        min(roi[2], feature_box[2] + 4),
        min(roi[3], feature_box[3] + 5),
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
    return {
        "feature_pixels": len(feature),
        "feature_pair": any(
            (x + 1, y) in feature or (x, y + 1) in feature
            for x, y in feature
        ),
        "feature_horizontal_pair": (
            len(feature) == 2 and len({y for _, y in feature}) == 1
        ),
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


def test_yone_ui_faces_use_one_profile_eye_and_a_tapered_warm_plane() -> None:
    surfaces = {
        "compact": (
            Image.open(COMPACT).convert("RGBA"),
            YONE_FOCUSED_UI_FACE_WINDOW,
            18,
        ),
        "scoreboard": (
            Image.open(SCOREBOARD).convert("RGBA"),
            YONE_FOCUSED_UI_FACE_WINDOW,
            18,
        ),
        "grid": (
            Image.open(GRID).convert("RGBA"),
            YONE_ACTOR_FACE_WINDOW,
            18,
        ),
    }
    for name, (image, window, minimum_warm) in surfaces.items():
        metrics = _portrait_face_metrics(image, window)
        assert metrics["feature_pixels"] == 1, (name, metrics)
        assert metrics["feature_pair"] is False, (name, metrics)
        assert metrics["warm_component"] >= minimum_warm, (name, metrics)
        warm_bbox = metrics["warm_bbox"]
        assert isinstance(warm_bbox, tuple), (name, metrics)
        assert warm_bbox[2] - warm_bbox[0] >= 5, (name, metrics)
        assert warm_bbox[3] - warm_bbox[1] >= 5, (name, metrics)
        assert metrics["near_white"] == 0, (name, metrics)

    generator = GENERATOR.read_text(encoding="utf-8")
    assert "return repaint_yone_face(output, face_window)" in generator
    assert "stamp_yone_face_template(" in generator
    assert "YONE_FOCUSED_UI_FACE_WINDOW" in generator


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
        assert metrics["feature_pixels"] == 1, (tag, index, metrics)
        assert metrics["feature_pair"] is False, (tag, index, metrics)
        assert metrics["warm_component"] >= 18, (tag, index, metrics)
        warm_bbox = metrics["warm_bbox"]
        assert isinstance(warm_bbox, tuple), (tag, index, metrics)
        assert warm_bbox[2] - warm_bbox[0] >= 5, (tag, index, metrics)
        assert warm_bbox[3] - warm_bbox[1] >= 5, (tag, index, metrics)
        assert metrics["near_white"] == 0, (tag, index, metrics)
        assert build_yone.finalize_yone_battle_face(
            frame, (tag, index)
        ).tobytes() == frame.tobytes(), (
            tag,
            index,
        )


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
    assert "scoreboard = stamp_yone_face_template(" in source
    assert "render_ui_subject(" in source
    assert 'scoreboard_path = PORTRAIT_DIR / "dual_blader_scoreboard.png"' in source
    assert source.index("scoreboard_focus = full_body.crop(") < source.index(
        "scoreboard = stamp_yone_face_template("
    )
    assert "compact.resize" not in source


def test_yone_default_actor_crop_centers_the_face_and_restores_native_feet() -> None:
    """Replay the user's real Sprite crop instead of testing dead UI PNG routes."""

    style = json.loads(CHAMPION_VIEW.read_text(encoding="utf-8"))["entries"][
        "dual_blader"
    ]
    assert style == {
        "face": {"x": 2, "y": -32},
        "center": {"x": 0, "y": -8},
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

    idle = anims["idle"]["frames"][0]["data"]
    idle_frame = sheet.crop(
        (
            idle["x"],
            idle["y"],
            idle["x"] + idle["w"],
            idle["y"] + idle["h"],
        )
    )
    # Pixel-perfect reconstruction of the 30x30 screenshot surface: the game
    # crops this 15x15 source window and displays it at 2x nearest-neighbor.
    face_crop = idle_frame.crop((15, 4, 30, 19))
    crop_metrics = _portrait_face_metrics(face_crop, (0.0, 0.0, 1.0, 1.0))
    assert crop_metrics["feature_pixels"] == 1
    assert crop_metrics["warm_component"] >= 18
    warm_bbox = crop_metrics["warm_bbox"]
    assert isinstance(warm_bbox, tuple)
    assert warm_bbox[2] - warm_bbox[0] >= 5
    assert warm_bbox[3] - warm_bbox[1] >= 6
    eye = [
        (x, y)
        for y in range(face_crop.height)
        for x in range(face_crop.width)
        if face_crop.getpixel((x, y)) == YONE_FACE_FEATURE_RGBA
    ]
    assert len(eye) == 1
    assert 5 <= eye[0][0] <= 9 and 5 <= eye[0][1] <= 10

    rendered = face_crop.resize((30, 30), Image.Resampling.NEAREST)
    eye_pixels = sum(
        1
        for pixel in (
            rendered.get_flattened_data()
            if hasattr(rendered, "get_flattened_data")
            else rendered.getdata()
        )
        if pixel == YONE_FACE_FEATURE_RGBA
    )
    assert eye_pixels == 4


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
