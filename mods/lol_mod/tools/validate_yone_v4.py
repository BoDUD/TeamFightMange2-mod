from __future__ import annotations

import json
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from PIL import Image


MOD_ROOT = Path(__file__).resolve().parents[1]
FRAME_MANIFEST = MOD_ROOT / "source/native/yone_v4/frames.json"
ACTOR_ATLAS = MOD_ROOT / "aseprite_resources/champions/yone#sheet.png"
ACTOR_ANIM = MOD_ROOT / "aseprite_resources/champions/yone#anim.fanim"
RELEASE_MANIFEST = MOD_ROOT / "build_manifest.json"

EXPECTED_ATLAS_SIZE = (3502, 88)
EXPECTED_ROUTE = "exact-native-v4"
EXPECTED_BODY_FRAME_COUNT = 54
CARD_PREVIEW_SIZE = (141, 138)
CARD_STAGE_HEIGHT = 121
CARD_SCALE = 2.2
# The rejected 141x138 capture changes from the actor-stage fill (22,23,33)
# to the divider/name-band fill (15,16,22) at y=96.  The former y=99 probe
# measured inside the band and let feet sit visibly on its top edge.
CARD_DIVIDER_Y = 96
CARD_DIVIDER_CLEARANCE = 6
CARD_UI_ICON_SAFE_RECT = (98, 70, 141, 100)
MAX_OPAQUE_PALETTE_COLORS = 32

# These are the rejected V3 body route, not active W/Q/R VFX sources.  Keeping
# this list exact prevents an old model plate from being silently reused while
# allowing the independently accepted effect pipeline to remain in place.
RETIRED_V3_BODY_PATHS = {
    "source/imagegen/yone_core_contact.png",
    "source/imagegen/yone_run_contact.png",
    "source/imagegen/yone_wr_body_contact.png",
    "source/imagegen/yone_defeat_contact.png",
    "source/processed/yone_core_contact_alpha.png",
    "source/processed/yone_run_contact_alpha.png",
    "source/processed/yone_wr_body_contact_alpha.png",
    "source/processed/yone_defeat_contact_alpha.png",
    "source/processed/yone_native_body_master.png",
}

BODY_ACTION_COUNTS = {
    "skill2": 1,
    "hit": 1,
    "attack": 6,
    "skill2_dash": 1,
    "ult": 13,
    "run": 8,
    "skill2_attack": 5,
    "idle": 4,
    # The native ninth dead frame is a transparent terminal and is not a body
    # source frame.
    "dead": 8,
    "skill": 7,
}
FRONT_FACE_ACTIONS = {"idle"}
FOOT_REQUIRED_ACTIONS = {
    "idle",
    "hit",
    "attack",
    "skill2",
    "skill2_dash",
    "skill2_attack",
    "run",
    "skill",
}


class V4ValidationError(ValueError):
    pass


@dataclass(frozen=True)
class Palette:
    colors: frozenset[tuple[int, int, int, int]]
    by_role: dict[str, frozenset[tuple[int, int, int, int]]]

    def colors_for(self, fragment: str) -> frozenset[tuple[int, int, int, int]]:
        matched: set[tuple[int, int, int, int]] = set()
        for role, colors in self.by_role.items():
            if fragment in role:
                matched.update(colors)
        return frozenset(matched)


def _fail(message: str) -> None:
    raise V4ValidationError(message)


def _read_json(path: Path) -> Any:
    if not path.is_file():
        _fail(f"missing required V4 file: {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        _fail(f"invalid JSON at {path}: {error}")


def _safe_relative_file(base: Path, raw: object, *, label: str) -> Path:
    if not isinstance(raw, str) or not raw or "\\" in raw:
        _fail(f"{label} must be a non-empty POSIX relative path")
    relative = Path(raw)
    if relative.is_absolute() or any(part in {"", ".", ".."} for part in relative.parts):
        _fail(f"{label} escapes the V4 source root: {raw!r}")
    resolved = (base / relative).resolve()
    try:
        resolved.relative_to(base.resolve())
    except ValueError:
        _fail(f"{label} escapes the V4 source root: {raw!r}")
    if not resolved.is_file():
        _fail(f"{label} does not exist: {resolved}")
    return resolved


def _rect(value: object, *, label: str, size: tuple[int, int]) -> tuple[int, int, int, int]:
    if (
        not isinstance(value, list)
        or len(value) != 4
        or any(type(component) is not int for component in value)
    ):
        _fail(f"{label} must be [x,y,w,h] integers")
    x, y, width, height = value
    if width <= 0 or height <= 0:
        _fail(f"{label} must have positive width and height: {value}")
    if x < 0 or y < 0 or x + width > size[0] or y + height > size[1]:
        _fail(f"{label} is outside {size}: {value}")
    return x, y, width, height


def _bbox_to_pillow(rect: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
    x, y, width, height = rect
    return x, y, x + width, y + height


def _rgba_pixels(image: Image.Image) -> list[tuple[int, int, int, int]]:
    if image.mode != "RGBA":
        _fail(f"V4 source must be RGBA, got {image.mode}")
    return list(image.getdata())


def _luminance(color: tuple[int, int, int, int]) -> float:
    red, green, blue, _alpha = color
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue


def load_palette(path: Path) -> Palette:
    if path.suffix.lower() != ".json":
        _fail(f"palette_file must end in .json: {path}")
    payload = _read_json(path)
    if not isinstance(payload, dict):
        _fail("palette.json must be an object")
    if payload.get("schema_version") != 4 or payload.get("route") != EXPECTED_ROUTE:
        _fail("palette.json must declare schema_version=4 and exact-native-v4")
    rows = payload.get("colors")
    if not isinstance(rows, list) or not rows:
        _fail("palette.json colors must be a non-empty list")

    rgba_seen: set[tuple[int, int, int, int]] = set()
    by_role: dict[str, set[tuple[int, int, int, int]]] = {}
    transparent_rows = 0
    opaque_rows = 0
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            _fail(f"palette colors[{index}] must be an object")
        role = row.get("role")
        rgba = row.get("rgba")
        if not isinstance(role, str) or not role.strip():
            _fail(f"palette colors[{index}].role must be non-empty")
        if (
            not isinstance(rgba, list)
            or len(rgba) != 4
            or any(type(channel) is not int or not 0 <= channel <= 255 for channel in rgba)
        ):
            _fail(f"palette colors[{index}].rgba must contain four bytes")
        color = tuple(rgba)
        if color in rgba_seen:
            _fail(f"palette RGBA is duplicated: {rgba}")
        rgba_seen.add(color)
        normalized_role = role.strip().lower()
        by_role.setdefault(normalized_role, set()).add(color)
        if color[3] == 0:
            transparent_rows += 1
            if color != (0, 0, 0, 0):
                _fail("transparent palette color must clear RGB to [0,0,0,0]")
        elif color[3] == 255:
            opaque_rows += 1
        else:
            _fail(f"palette alpha must be hard 0/255, got {rgba}")

    if transparent_rows != 1:
        _fail(f"palette must contain exactly one transparent RGBA, got {transparent_rows}")
    if opaque_rows > MAX_OPAQUE_PALETTE_COLORS:
        _fail(
            f"palette has {opaque_rows} opaque colors; maximum is "
            f"{MAX_OPAQUE_PALETTE_COLORS}"
        )
    frozen_roles = {role: frozenset(colors) for role, colors in by_role.items()}
    palette = Palette(frozenset(rgba_seen), frozen_roles)
    for semantic_role in ("skin", "eye", "mask"):
        if not palette.colors_for(semantic_role):
            _fail(f"palette must include a role containing {semantic_role!r}")
    return palette


def _expected_actor_frames(anim_payload: dict[str, Any]) -> dict[tuple[str, int], list[int]]:
    anims = anim_payload.get("anims")
    if not isinstance(anims, dict):
        _fail("Yone actor anim is missing anims")
    expected: dict[tuple[str, int], list[int]] = {}
    for action, count in BODY_ACTION_COUNTS.items():
        frames = anims.get(action, {}).get("frames")
        if not isinstance(frames, list) or len(frames) < count:
            _fail(f"Yone native action {action!r} has fewer than {count} body frames")
        for index in range(count):
            data = frames[index].get("data")
            if not isinstance(data, dict):
                _fail(f"Yone native {action}[{index}] has no data rect")
            expected[(action, index)] = [
                data.get("x"),
                data.get("y"),
                data.get("w"),
                data.get("h"),
            ]
    if len(expected) != EXPECTED_BODY_FRAME_COUNT:
        _fail(f"internal body frame contract is {len(expected)}, expected 54")
    return expected


def _validate_binary_palette(image: Image.Image, palette: Palette, *, label: str) -> dict[str, Any]:
    pixels = _rgba_pixels(image)
    unknown = set(pixels) - set(palette.colors)
    if unknown:
        examples = sorted(unknown)[:5]
        _fail(f"{label} contains RGBA outside fixed palette: {examples}")
    alpha_values = {color[3] for color in pixels}
    if not alpha_values <= {0, 255}:
        _fail(f"{label} contains soft alpha values: {sorted(alpha_values)}")
    contaminated = {color for color in pixels if color[3] == 0 and color[:3] != (0, 0, 0)}
    if contaminated:
        _fail(f"{label} has RGB under transparent pixels: {sorted(contaminated)[:5]}")
    visible = [color for color in pixels if color[3] == 255]
    if not visible:
        _fail(f"{label} is empty")
    bright_pixels = sum(_luminance(color) >= 150 for color in visible)
    dark_pixels = sum(_luminance(color) <= 60 for color in visible)
    if bright_pixels < 8:
        _fail(f"{label} has only {bright_pixels} bright pixels; minimum is 8")
    if dark_pixels < 12:
        _fail(f"{label} has only {dark_pixels} dark pixels; minimum is 12")
    return {
        "visible_pixels": len(visible),
        "bright_pixels": bright_pixels,
        "dark_pixels": dark_pixels,
        "opaque_palette_colors": len(set(visible)),
    }


def _validate_zero_clip(image: Image.Image, *, label: str) -> None:
    alpha = image.getchannel("A")
    edge = Counter()
    for x in range(image.width):
        edge["top"] += alpha.getpixel((x, 0)) != 0
        edge["bottom"] += alpha.getpixel((x, image.height - 1)) != 0
    for y in range(image.height):
        edge["left"] += alpha.getpixel((0, y)) != 0
        edge["right"] += alpha.getpixel((image.width - 1, y)) != 0
    if any(edge.values()):
        _fail(f"{label} touches a native frame edge (clip risk): {dict(edge)}")


def _pixels_in_rect(
    image: Image.Image,
    rect: tuple[int, int, int, int],
) -> Iterable[tuple[int, int, tuple[int, int, int, int]]]:
    x, y, width, height = rect
    for local_y in range(y, y + height):
        for local_x in range(x, x + width):
            yield local_x, local_y, image.getpixel((local_x, local_y))


def validate_frame_annotations(
    row: dict[str, Any],
    image: Image.Image,
    palette: Palette,
    *,
    label: str,
) -> dict[str, Any]:
    """Validate only explicit V4 coordinates; never infer an eye by adjacency."""

    action = row["action"]
    face_raw = row.get("face_bbox")
    mask_raw = row.get("mask_bbox")
    eyes_raw = row.get("eye_pixels")
    feet_raw = row.get("foot_zones")
    if not isinstance(eyes_raw, list):
        _fail(f"{label}.eye_pixels must be a list")
    if not isinstance(feet_raw, list):
        _fail(f"{label}.foot_zones must be a list")

    face_required = action in FRONT_FACE_ACTIONS
    if face_required and (face_raw is None or mask_raw is None or not eyes_raw):
        _fail(f"{label} is a front-facing frame and needs explicit face/eyes/mask")
    if face_raw is not None and (mask_raw is None or not eyes_raw):
        _fail(f"{label} declares a visible face but lacks explicit eyes/mask")
    if face_raw is None:
        if eyes_raw:
            _fail(f"{label} cannot declare eye pixels without a face_bbox")
        if mask_raw is not None:
            _fail(f"{label} cannot declare mask_bbox without a face_bbox")
        face_stats: dict[str, Any] = {
            "face_skin_pixels": 0,
            "eye_pixels": 0,
            "mask_pixels": 0,
        }
    else:
        face = _rect(face_raw, label=f"{label}.face_bbox", size=image.size)
        if face_required and (face[2] < 6 or face[3] < 7):
            _fail(f"{label}.face_bbox is too small for a readable front face: {face_raw}")
        skin_colors = palette.colors_for("skin")
        skin_pixels = [
            color
            for _x, _y, color in _pixels_in_rect(image, face)
            if color in skin_colors
        ]
        minimum_skin = 14 if face_required else 4
        if len(skin_pixels) < minimum_skin:
            _fail(
                f"{label}.face_bbox contains {len(skin_pixels)} explicit skin-role pixels; "
                f"minimum is {minimum_skin}"
            )
        mean_skin_luma = sum(_luminance(color) for color in skin_pixels) / len(skin_pixels)
        if mean_skin_luma < 120:
            _fail(f"{label} face is too dark: mean skin luminance={mean_skin_luma:.1f}")

        eye_colors = palette.colors_for("eye")
        eye_points: list[tuple[int, int]] = []
        for eye_index, point in enumerate(eyes_raw):
            if (
                not isinstance(point, list)
                or len(point) != 2
                or any(type(value) is not int for value in point)
            ):
                _fail(f"{label}.eye_pixels[{eye_index}] must be [x,y]")
            x, y = point
            if not (0 <= x < image.width and 0 <= y < image.height):
                _fail(f"{label}.eye_pixels[{eye_index}] is out of bounds: {point}")
            if not (face[0] <= x < face[0] + face[2] and face[1] <= y < face[1] + face[3]):
                _fail(f"{label}.eye_pixels[{eye_index}] is outside face_bbox: {point}")
            if image.getpixel((x, y)) not in eye_colors:
                _fail(f"{label}.eye_pixels[{eye_index}] does not point to an eye-role pixel")
            eye_points.append((x, y))
        if face_required:
            if len(set(eye_points)) < 2 or max(x for x, _y in eye_points) - min(
                x for x, _y in eye_points
            ) < 2:
                _fail(f"{label} needs two visibly separated explicit eye pixels")

        mask_pixels = 0
        if mask_raw is not None:
            mask = _rect(mask_raw, label=f"{label}.mask_bbox", size=image.size)
            mask_colors = palette.colors_for("mask")
            mask_pixels = sum(
                color in mask_colors for _x, _y, color in _pixels_in_rect(image, mask)
            )
            if mask_pixels < (4 if face_required else 1):
                _fail(f"{label}.mask_bbox does not contain enough mask-role pixels")
            intersection_width = max(
                0, min(face[0] + face[2], mask[0] + mask[2]) - max(face[0], mask[0])
            )
            intersection_height = max(
                0, min(face[1] + face[3], mask[1] + mask[3]) - max(face[1], mask[1])
            )
            if face_required and intersection_width * intersection_height > face[2] * face[3] // 3:
                _fail(f"{label} mask covers more than one third of the readable face box")

        face_stats = {
            "face_skin_pixels": len(skin_pixels),
            "face_mean_luminance": round(mean_skin_luma, 2),
            "eye_pixels": len(set(eye_points)),
            "mask_pixels": mask_pixels,
        }

    foot_zones: list[tuple[int, int, int, int]] = []
    for zone_index, zone_raw in enumerate(feet_raw):
        zone = _rect(zone_raw, label=f"{label}.foot_zones[{zone_index}]", size=image.size)
        if zone[1] < image.height // 2:
            _fail(f"{label}.foot_zones[{zone_index}] is above the lower body")
        if not any(color[3] for _x, _y, color in _pixels_in_rect(image, zone)):
            _fail(f"{label}.foot_zones[{zone_index}] contains no actor pixels")
        foot_zones.append(zone)
    if action in FOOT_REQUIRED_ACTIONS and not foot_zones:
        _fail(f"{label} needs at least one explicit foot zone")

    return {**face_stats, "foot_zone_count": len(foot_zones)}


def _validate_card_preview(
    preview_path: Path,
    idle_source: Image.Image,
    idle_row: dict[str, Any],
    palette: Palette,
) -> dict[str, Any]:
    preview = Image.open(preview_path)
    if (
        preview.format != "PNG"
        or preview.mode != "RGBA"
        or preview.size != CARD_PREVIEW_SIZE
    ):
        _fail(
            f"V4 body_preview must be RGBA {CARD_PREVIEW_SIZE}, got "
            f"{preview.format} {preview.mode} {preview.size}"
        )
    # The preview is an actor-only transparent replay of the real card route:
    # native idle[0] -> 2.2x nearest -> horizontally centered in 141px and
    # vertically centered in the 121px actor stage.
    rendered = idle_source.resize(
        (
            round(idle_source.width * CARD_SCALE),
            round(idle_source.height * CARD_SCALE),
        ),
        Image.Resampling.NEAREST,
    )
    expected = Image.new("RGBA", CARD_PREVIEW_SIZE, (0, 0, 0, 0))
    x = (CARD_PREVIEW_SIZE[0] - rendered.width) // 2
    y = (CARD_STAGE_HEIGHT - rendered.height) // 2
    expected.alpha_composite(rendered, (x, y))
    if preview.tobytes() != expected.tobytes():
        _fail("V4 body_preview is not the exact real 141x138 idle[0] actor-card route")

    bbox = preview.getchannel("A").getbbox()
    if bbox is None:
        _fail("V4 body_preview is empty")
    divider_clearance = CARD_DIVIDER_Y - bbox[3]
    if divider_clearance < CARD_DIVIDER_CLEARANCE:
        _fail(
            f"V4 actor feet/weapon approach the card divider: clearance={divider_clearance}px"
        )
    if preview.getchannel("A").crop(CARD_UI_ICON_SAFE_RECT).getbbox() is not None:
        _fail(f"V4 actor overlaps the card UI icon safe rect {CARD_UI_ICON_SAFE_RECT}")
    if preview.getchannel("A").crop((0, CARD_DIVIDER_Y, 141, 138)).getbbox() is not None:
        _fail("V4 actor enters the divider/name band")

    frame_stats = _validate_binary_palette(preview, palette, label="body_preview")
    face = _rect(
        idle_row["face_bbox"],
        label="idle[0].face_bbox",
        size=idle_source.size,
    )
    rendered_face = (
        x + round(face[0] * CARD_SCALE),
        y + round(face[1] * CARD_SCALE),
        max(1, round(face[2] * CARD_SCALE)),
        max(1, round(face[3] * CARD_SCALE)),
    )
    rendered_face = _rect(
        list(rendered_face), label="body_preview rendered face", size=preview.size
    )
    skin_colors = palette.colors_for("skin")
    rendered_skin = sum(
        color in skin_colors for _x, _y, color in _pixels_in_rect(preview, rendered_face)
    )
    if rendered_skin < 50:
        _fail(f"V4 card face has only {rendered_skin} rendered skin pixels; minimum is 50")
    return {
        "size": list(preview.size),
        "alpha_bbox": list(bbox),
        "divider_clearance": divider_clearance,
        "ui_icon_safe_rect": list(CARD_UI_ICON_SAFE_RECT),
        "rendered_face_skin_pixels": rendered_skin,
        **frame_stats,
    }


def _validate_retired_paths(mod_root: Path) -> None:
    existing = sorted(path for path in RETIRED_V3_BODY_PATHS if (mod_root / path).exists())
    if existing:
        _fail("retired V3 body paths still exist:\n" + "\n".join(existing))
    manifest_path = mod_root / RELEASE_MANIFEST.relative_to(MOD_ROOT)
    manifest = _read_json(manifest_path)
    rows = manifest.get("files") if isinstance(manifest, dict) else None
    if not isinstance(rows, list):
        _fail("release build_manifest.json has no files list")
    manifest_paths = {
        row.get("path").replace("\\", "/")
        for row in rows
        if isinstance(row, dict) and isinstance(row.get("path"), str)
    }
    leaked = sorted(RETIRED_V3_BODY_PATHS & manifest_paths)
    if leaked:
        _fail("retired V3 body paths entered release manifest:\n" + "\n".join(leaked))


def validate_v4(
    manifest_path: Path = FRAME_MANIFEST,
    *,
    mod_root: Path = MOD_ROOT,
) -> dict[str, Any]:
    manifest_path = manifest_path.resolve()
    payload = _read_json(manifest_path)
    if not isinstance(payload, dict):
        _fail("frames.json must be an object")
    if payload.get("schema_version") != 4 or payload.get("route") != EXPECTED_ROUTE:
        _fail("frames.json must declare schema_version=4 and exact-native-v4")
    if payload.get("atlas_size") != list(EXPECTED_ATLAS_SIZE):
        _fail(f"frames.json atlas_size must be {list(EXPECTED_ATLAS_SIZE)}")
    source_root = manifest_path.parent
    palette_path = _safe_relative_file(
        source_root, payload.get("palette_file"), label="palette_file"
    )
    palette = load_palette(palette_path)
    preview_path = _safe_relative_file(
        source_root, payload.get("body_preview"), label="body_preview"
    )
    if preview_path.suffix.lower() != ".png":
        _fail(f"body_preview must end in .png: {preview_path}")

    atlas_path = mod_root / ACTOR_ATLAS.relative_to(MOD_ROOT)
    anim_path = mod_root / ACTOR_ANIM.relative_to(MOD_ROOT)
    if not atlas_path.is_file() or not anim_path.is_file():
        _fail("V4 runtime actor atlas/anim is missing")
    atlas = Image.open(atlas_path)
    if (
        atlas.format != "PNG"
        or atlas.mode != "RGBA"
        or atlas.size != EXPECTED_ATLAS_SIZE
    ):
        _fail(
            f"V4 actor atlas must be RGBA {EXPECTED_ATLAS_SIZE}, got "
            f"{atlas.format} {atlas.mode} {atlas.size}"
        )
    expected = _expected_actor_frames(_read_json(anim_path))
    rows = payload.get("frames")
    if not isinstance(rows, list) or len(rows) != EXPECTED_BODY_FRAME_COUNT:
        actual_count = len(rows) if isinstance(rows, list) else None
        _fail(f"frames.json must contain exactly 54 body frames, got {actual_count}")

    seen_keys: set[tuple[str, int]] = set()
    seen_files: set[str] = set()
    reports: dict[str, Any] = {}
    sources: dict[tuple[str, int], Image.Image] = {}
    rows_by_key: dict[tuple[str, int], dict[str, Any]] = {}
    for position, row in enumerate(rows):
        if not isinstance(row, dict):
            _fail(f"frames[{position}] must be an object")
        required = {
            "action",
            "index",
            "file",
            "rect",
            "bottom_margin",
            "face_bbox",
            "eye_pixels",
            "mask_bbox",
            "foot_zones",
        }
        missing = required - set(row)
        if missing:
            _fail(f"frames[{position}] is missing fields: {sorted(missing)}")
        action = row.get("action")
        index = row.get("index")
        if not isinstance(action, str) or type(index) is not int:
            _fail(f"frames[{position}] action/index types are invalid")
        key = (action, index)
        label = f"{action}[{index}]"
        if key in seen_keys:
            _fail(f"duplicate V4 frame key: {label}")
        seen_keys.add(key)
        if key not in expected:
            _fail(f"unexpected V4 body frame: {label}")
        if row.get("rect") != expected[key]:
            _fail(f"{label}.rect {row.get('rect')} != native exact rect {expected[key]}")
        atlas_rect = _rect(row["rect"], label=f"{label}.rect", size=atlas.size)

        file_raw = row.get("file")
        if not isinstance(file_raw, str):
            _fail(f"{label}.file must be a relative PNG path")
        if file_raw in seen_files:
            _fail(f"source frame path is reused: {file_raw}")
        seen_files.add(file_raw)
        source_path = _safe_relative_file(source_root, file_raw, label=f"{label}.file")
        if source_path.suffix.lower() != ".png":
            _fail(f"{label}.file must be PNG")
        source = Image.open(source_path)
        if (
            source.format != "PNG"
            or source.mode != "RGBA"
            or source.size != (atlas_rect[2], atlas_rect[3])
        ):
            _fail(
                f"{label} source must be exact RGBA native rect "
                f"{(atlas_rect[2], atlas_rect[3])}, got "
                f"{source.format} {source.mode} {source.size}"
            )
        source_stats = _validate_binary_palette(source, palette, label=label)
        _validate_zero_clip(source, label=label)
        alpha_bbox = source.getchannel("A").getbbox()
        assert alpha_bbox is not None
        bottom_margin = source.height - alpha_bbox[3]
        if type(row.get("bottom_margin")) is not int or row["bottom_margin"] != bottom_margin:
            _fail(
                f"{label}.bottom_margin {row.get('bottom_margin')} != exact {bottom_margin}"
            )
        if action != "dead" and bottom_margin < 2:
            _fail(f"{label} has only {bottom_margin}px bottom safety margin")

        atlas_frame = atlas.crop(_bbox_to_pillow(atlas_rect))
        if atlas_frame.tobytes() != source.tobytes():
            _fail(
                f"{label} source->atlas bytes differ (resample/quantize/clip is forbidden)"
            )
        annotation_stats = validate_frame_annotations(
            row, source, palette, label=label
        )
        reports[label] = {
            "file": file_raw,
            "rect": list(atlas_rect),
            "source_to_atlas_byte_identical": True,
            "hard_alpha": True,
            "zero_resampling": True,
            "zero_quantize": True,
            "zero_clip": True,
            "bottom_margin": bottom_margin,
            **source_stats,
            **annotation_stats,
        }
        sources[key] = source.copy()
        rows_by_key[key] = row

    if seen_keys != set(expected):
        missing = sorted(set(expected) - seen_keys)
        _fail(f"frames.json does not cover exact 54-frame contract: missing={missing}")

    preview_report = _validate_card_preview(
        preview_path,
        sources[("idle", 0)],
        rows_by_key[("idle", 0)],
        palette,
    )
    _validate_retired_paths(mod_root)
    return {
        "schema_version": 4,
        "route": EXPECTED_ROUTE,
        "atlas_size": list(atlas.size),
        "frame_count": len(reports),
        "palette_file": payload["palette_file"],
        "opaque_palette_limit": MAX_OPAQUE_PALETTE_COLORS,
        "body_transform": {
            "resampling": "none",
            "quantize": "none",
            "clip": "none",
            "proof": "exact per-frame RGBA byte identity",
        },
        "frames": reports,
        "body_preview": preview_report,
        "retired_v3_paths_absent": True,
    }


def main() -> int:
    try:
        report = validate_v4()
    except V4ValidationError as error:
        print(f"Yone V4 exact-native validation FAILED: {error}", file=sys.stderr)
        return 1
    print(
        "Yone V4 exact-native validation passed: "
        f"{report['frame_count']} frames, {report['body_preview']['divider_clearance']}px "
        "card-divider clearance"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
