from __future__ import annotations

import hashlib
import json
from collections import deque
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw

import build_yone


MOD_ROOT = Path(__file__).resolve().parents[1]
IMAGEGEN_ROOT = MOD_ROOT / "source/imagegen"
MOTION_SOURCE = IMAGEGEN_ROOT / "yone_v6_motion_contact.png"
ATTACK_SOURCE = IMAGEGEN_ROOT / "yone_v6_attack_q_w_contact.png"
W_SOURCE = IMAGEGEN_ROOT / "yone_v6_w_contact.png"
ULT_SOURCE = IMAGEGEN_ROOT / "yone_v6_ult_contact.png"

V6_ROOT = MOD_ROOT / "source/native/yone_v6"
FRAME_ROOT = V6_ROOT / "frames"
PREVIEW_ROOT = V6_ROOT / "preview"
FRAME_MANIFEST = V6_ROOT / "frames.json"
PALETTE_PATH = V6_ROOT / "palette.json"
QA_PATH = V6_ROOT / "generation_qa.json"
BODY_PREVIEW = PREVIEW_ROOT / "yone_v6_actor_card.png"
CONTACT_PREVIEW = PREVIEW_ROOT / "yone_v6_native_contact.png"

EXPECTED_SOURCE_SHA256 = {
    "motion": "8b66ef3e9dc334c774ef9e4557102d37889f02ad6fea35ce6d5a0229f5396cbb",
    "attack_q_w": "900e357f6905d86020bd26c53841360ddcb2ceb27e690830e21fd9b9c4725849",
    "w": "84ac11c0512a76d5c269cf9c94bd8e6dfa084536b6bcff845cad22434944d765",
    "ult": "2f943fb3a16017abaa1b264fc63ed4f25de3df9335a593c1559e85d45300c3bc",
}
SOURCE_PATHS = {
    "motion": MOTION_SOURCE,
    "attack_q_w": ATTACK_SOURCE,
    "w": W_SOURCE,
    "ult": ULT_SOURCE,
}

# The V6 palette is derived deterministically from the three hash-locked source
# sheets.  Eight semantic anchors preserve the light face, real dark eye cues,
# red mask/sword, gold trim, and steel highlights after LANCZOS reduction.
PALETTE_ANCHORS: tuple[tuple[int, int, int, int], ...] = (
    (5, 7, 14, 255),
    (18, 22, 38, 255),
    (92, 48, 29, 255),
    (218, 132, 73, 255),
    (248, 190, 122, 255),
    (191, 27, 22, 255),
    (224, 157, 35, 255),
    (224, 238, 246, 255),
)
PALETTE: tuple[tuple[int, int, int, int], ...] = PALETTE_ANCHORS
PALETTE_ROWS: tuple[tuple[str, tuple[int, int, int, int]], ...] = (
    ("transparent", (0, 0, 0, 0)),
    *((f"anchor_{index:02d}", color) for index, color in enumerate(PALETTE_ANCHORS)),
)
ALLOWED_COLORS = {color for _role, color in PALETTE_ROWS}
SKIN_COLORS: set[tuple[int, int, int, int]] = set()
EYE_COLORS: set[tuple[int, int, int, int]] = set()
MASK_COLORS: set[tuple[int, int, int, int]] = set()

# Cell indices are zero-based.  The action map is intentionally explicit so
# no later contact-sheet reorder can silently change the model or motion.
ACTION_SOURCES: dict[str, tuple[tuple[str, int | None], ...]] = {
    "skill2": (("w", 5),),
    "hit": (("motion", 4),),
    "attack": tuple(("attack_q_w", index) for index in (1, 2, 3, 4, 7, 8)),
    "skill2_dash": (("attack_q_w", 9),),
    "ult": tuple(("ult", index) for index in range(13)),
    "run": tuple(("motion", index) for index in range(5, 13)),
    "skill2_attack": tuple(("w", index) for index in range(5)),
    "idle": tuple(("motion", index) for index in range(4)),
    "dead": tuple(("motion", index) for index in range(13, 20))
    + (("motion", 19),),
    "skill": tuple(("attack_q_w", index) for index in (6, 7, 8, 9, 10, 11, 5)),
}

X_SHIFTS: dict[str, tuple[int, ...]] = {
    "skill2": (0,),
    "hit": (-1,),
    "attack": (-1, 0, 1, 1, 0, -1),
    "skill2_dash": (0,),
    "ult": (-1, 0, 1, 1, 1, 0, -1, -1, 0, 1, 1, 0, -1),
    "run": (-1, 0, 1, 0, -1, 0, 1, 0),
    "skill2_attack": (-1, 0, 1, 0, -1),
    "idle": (0, 0, 1, 0),
    "dead": (-1, 0, 1, 1, 0, -1, 0, 1),
    "skill": (-1, 0, 1, 1, 0, -1, 0),
}
DEAD_TARGET_HEIGHTS = (34, 28, 24, 12, 12, 12, 12, 12)
DEAD_BOTTOM_MARGINS = (6, 6, 5, 4, 4, 4, 4, 4)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def pixel_sha256(image: Image.Image) -> str:
    return hashlib.sha256(image.convert("RGBA").tobytes()).hexdigest()


def pixels(image: Image.Image) -> Any:
    getter = getattr(image, "get_flattened_data", None)
    return getter() if getter is not None else image.getdata()


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(
        (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    )


def save_png(path: Path, image: Image.Image) -> None:
    if image.mode != "RGBA":
        raise ValueError(f"V6 PNG must be RGBA: {path} {image.mode}")
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, format="PNG", optimize=False, compress_level=9)


def alpha_bbox(image: Image.Image) -> tuple[int, int, int, int]:
    bbox = image.getchannel("A").getbbox()
    if bbox is None:
        raise ValueError("empty V6 image")
    return bbox


def keyed(source: Image.Image) -> Image.Image:
    """Clear the saturated-magenta field and harden all retained alpha."""

    rgba = source.convert("RGBA")
    result = Image.new("RGBA", rgba.size, (0, 0, 0, 0))
    source_pixels = rgba.load()
    output_pixels = result.load()
    for y in range(rgba.height):
        for x in range(rgba.width):
            red, green, blue, alpha = source_pixels[x, y]
            is_magenta = (
                red > 155
                and blue > 115
                and green < 165
                and red - green > 55
                and blue - green > 35
            )
            if alpha < 24 or is_magenta:
                continue
            output_pixels[x, y] = (red, green, blue, 255)
    return result


def largest_component(image: Image.Image) -> Image.Image:
    """Keep one 8-connected actor component and clear rejected debris."""

    alpha = image.getchannel("A")
    remaining = {
        (x, y)
        for y in range(image.height)
        for x in range(image.width)
        if alpha.getpixel((x, y)) != 0
    }
    best: set[tuple[int, int]] = set()
    while remaining:
        start = remaining.pop()
        component = {start}
        queue: deque[tuple[int, int]] = deque((start,))
        while queue:
            x, y = queue.popleft()
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    if dx == 0 and dy == 0:
                        continue
                    point = (x + dx, y + dy)
                    if point in remaining:
                        remaining.remove(point)
                        component.add(point)
                        queue.append(point)
        if len(component) > len(best):
            best = component
    if not best:
        raise ValueError("source has no actor component after chroma key")
    output = Image.new("RGBA", image.size, (0, 0, 0, 0))
    source_pixels = image.load()
    output_pixels = output.load()
    for x, y in best:
        output_pixels[x, y] = source_pixels[x, y]
    return output


def prepare_subject(source: Image.Image) -> Image.Image:
    cleaned = largest_component(keyed(source))
    return cleaned.crop(alpha_bbox(cleaned))


def split_cell(sheet: Image.Image, columns: int, rows: int, index: int) -> Image.Image:
    if not 0 <= index < columns * rows:
        raise ValueError(f"cell index {index} outside {columns}x{rows}")
    row, column = divmod(index, columns)
    left = round(column * sheet.width / columns)
    right = round((column + 1) * sheet.width / columns)
    top = round(row * sheet.height / rows)
    bottom = round((row + 1) * sheet.height / rows)
    return prepare_subject(sheet.crop((left, top, right, bottom)))


def luminance(color: tuple[int, int, int, int]) -> float:
    return 0.2126 * color[0] + 0.7152 * color[1] + 0.0722 * color[2]


def is_skin_color(color: tuple[int, int, int, int]) -> bool:
    red, green, blue, alpha = color
    return (
        alpha == 255
        and red >= 112
        and red - green >= 20
        and green - blue >= 12
        and blue * 4 >= green
        and blue <= 165
        and luminance(color) >= 82
    )


def is_eye_color(color: tuple[int, int, int, int]) -> bool:
    red, green, blue, alpha = color
    return alpha == 255 and max(red, green, blue) <= 72 and luminance(color) <= 52


def is_mask_color(color: tuple[int, int, int, int]) -> bool:
    red, green, blue, alpha = color
    return (
        alpha == 255
        and red >= 98
        and red - green >= 48
        and red - blue >= 28
        and green <= 112
    )


def install_source_palette(subjects: dict[tuple[str, int], Image.Image]) -> None:
    """Install one deterministic source-derived palette for every V6 frame."""

    global PALETTE, PALETTE_ROWS, ALLOWED_COLORS
    global SKIN_COLORS, EYE_COLORS, MASK_COLORS

    samples: list[tuple[int, int, int]] = []
    for key in sorted(subjects):
        subject = subjects[key]
        pixels = subject.load()
        # Sampling every fourth source pixel preserves the source distribution
        # while keeping median-cut deterministic and inexpensive.
        for y in range(0, subject.height, 4):
            for x in range(0, subject.width, 4):
                red, green, blue, alpha = pixels[x, y]
                if alpha == 255:
                    samples.append((red, green, blue))
    if len(samples) < 256:
        raise ValueError(f"too few V6 opaque source samples: {len(samples)}")

    width = 1024
    height = (len(samples) + width - 1) // width
    sample_image = Image.new("RGB", (width, height), samples[-1])
    sample_image.putdata(samples + [samples[-1]] * (width * height - len(samples)))
    quantized = sample_image.quantize(
        colors=40,
        method=Image.Quantize.MEDIANCUT,
        dither=Image.Dither.NONE,
    )
    raw_palette = quantized.getpalette() or []
    used_indices = sorted(index for _count, index in (quantized.getcolors() or []))
    derived = [
        (raw_palette[index * 3], raw_palette[index * 3 + 1], raw_palette[index * 3 + 2], 255)
        for index in used_indices
    ]
    opaque: list[tuple[int, int, int, int]] = []
    for color in (*PALETTE_ANCHORS, *derived):
        if color not in opaque:
            opaque.append(color)
    opaque = opaque[:48]
    if not 16 <= len(opaque) <= 48:
        raise ValueError(f"unexpected V6 palette size: {len(opaque)}")

    PALETTE = tuple(opaque)
    semantic_counts = {"skin": 0, "mask": 0, "source": 0}
    rows: list[tuple[str, tuple[int, int, int, int]]] = [
        ("transparent", (0, 0, 0, 0))
    ]
    for index, color in enumerate(PALETTE):
        if color == PALETTE_ANCHORS[0]:
            role = "eye_outline"
        elif is_skin_color(color):
            role = f"skin_{semantic_counts['skin']:02d}"
            semantic_counts["skin"] += 1
        elif is_mask_color(color):
            role = f"mask_{semantic_counts['mask']:02d}"
            semantic_counts["mask"] += 1
        else:
            role = f"source_{semantic_counts['source']:02d}"
            semantic_counts["source"] += 1
        rows.append((role, color))
    PALETTE_ROWS = tuple(rows)
    ALLOWED_COLORS = {color for _role, color in PALETTE_ROWS}
    SKIN_COLORS = {color for color in PALETTE if is_skin_color(color)}
    EYE_COLORS = {color for color in PALETTE if is_eye_color(color)}
    MASK_COLORS = {color for color in PALETTE if is_mask_color(color)}
    if len(SKIN_COLORS) < 3 or not EYE_COLORS or len(MASK_COLORS) < 2:
        raise ValueError(
            "V6 semantic palette coverage failed: "
            f"skin={len(SKIN_COLORS)} eye={len(EYE_COLORS)} mask={len(MASK_COLORS)}"
        )


def palette_finish(image: Image.Image) -> Image.Image:
    result = image.convert("RGBA")
    pixels = result.load()
    for y in range(result.height):
        for x in range(result.width):
            red, green, blue, alpha = pixels[x, y]
            if alpha == 0:
                pixels[x, y] = (0, 0, 0, 0)
                continue
            pixels[x, y] = min(
                PALETTE,
                key=lambda color: (
                    2 * (red - color[0]) ** 2
                    + 3 * (green - color[1]) ** 2
                    + (blue - color[2]) ** 2
                ),
            )
    return result


def core_center_x(subject: Image.Image) -> float:
    """Estimate pelvis/root x without letting long sword tips steer packing."""

    bbox = alpha_bbox(subject)
    top = bbox[1] + round((bbox[3] - bbox[1]) * 0.38)
    bottom = bbox[1] + round((bbox[3] - bbox[1]) * 0.88)
    alpha = subject.getchannel("A")
    alpha_pixels = alpha.load()
    xs = [
        x
        for y in range(top, max(top + 1, bottom))
        for x in range(bbox[0], bbox[2])
        if alpha_pixels[x, y]
    ]
    if not xs:
        return (bbox[0] + bbox[2] - 1) / 2
    xs.sort()
    middle = len(xs) // 2
    if len(xs) % 2:
        return float(xs[middle])
    return (xs[middle - 1] + xs[middle]) / 2


def fit_pose(
    subject: Image.Image,
    frame_size: tuple[int, int],
    *,
    visible_height: int,
    bottom_margin: int,
    x_shift: int,
) -> tuple[Image.Image, dict[str, Any]]:
    """Smoothly reduce one high-resolution pose into its native frame."""

    frame_width, frame_height = frame_size
    if visible_height + bottom_margin >= frame_height:
        visible_height = frame_height - bottom_margin - 1
    if visible_height < 1:
        raise ValueError((frame_size, visible_height, bottom_margin))

    original_core_x = core_center_x(subject)
    target_width = max(1, round(subject.width * visible_height / subject.height))
    # Clear chroma RGB before this single source-to-native resize, then use
    # LANCZOS so facial features survive instead of becoming blocky mosaics.
    fitted = subject.resize(
        (target_width, visible_height), Image.Resampling.LANCZOS
    )
    fitted.putalpha(
        fitted.getchannel("A").point(lambda value: 255 if value >= 96 else 0)
    )
    fitted = palette_finish(fitted)
    fitted_bbox = alpha_bbox(fitted)
    left_trim = fitted_bbox[0]
    fitted = fitted.crop(fitted_bbox)
    scaled_core_x = original_core_x * target_width / subject.width - left_trim

    desired_core_x = (frame_width - 1) / 2 + x_shift
    paste_x = round(desired_core_x - scaled_core_x)
    paste_y = frame_height - bottom_margin - fitted.height
    if paste_y < 1:
        raise ValueError(
            f"V6 pose {fitted.size} cannot fit {frame_size} at bottom {bottom_margin}"
        )

    # Clip weapons to the transparent one-pixel inner viewport.  Cropping is
    # performed after the one direct resize and cannot shrink the actor body.
    source_left = max(0, 1 - paste_x)
    source_right = min(fitted.width, frame_width - 1 - paste_x)
    source_top = max(0, 1 - paste_y)
    source_bottom = min(fitted.height, frame_height - 1 - paste_y)
    if source_right <= source_left or source_bottom <= source_top:
        raise ValueError("V6 pose lies outside its native frame")
    visible = fitted.crop((source_left, source_top, source_right, source_bottom))
    output = Image.new("RGBA", frame_size, (0, 0, 0, 0))
    output.alpha_composite(
        visible, (paste_x + source_left, paste_y + source_top)
    )
    bbox = alpha_bbox(output)
    return output, {
        "source_subject_size": list(subject.size),
        "direct_resize_size": [target_width, visible_height],
        "pelvis_center_x": round(original_core_x, 3),
        "paste_xy": [paste_x, paste_y],
        "horizontal_crop": source_left > 0 or source_right < fitted.width,
        "cropped_source_columns": source_left + fitted.width - source_right,
        "horizontal_crop_ratio": round(
            (source_left + fitted.width - source_right) / max(1, fitted.width), 4
        ),
        "alpha_bbox": list(bbox),
    }


def _components_for_colors(
    image: Image.Image,
    colors: set[tuple[int, int, int, int]],
    search_box: tuple[int, int, int, int],
) -> list[set[tuple[int, int]]]:
    left, top, right, bottom = search_box
    remaining = {
        (x, y)
        for y in range(max(0, top), min(image.height, bottom))
        for x in range(max(0, left), min(image.width, right))
        if image.getpixel((x, y)) in colors
    }
    result: list[set[tuple[int, int]]] = []
    while remaining:
        start = remaining.pop()
        component = {start}
        queue = deque((start,))
        while queue:
            x, y = queue.popleft()
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    point = (x + dx, y + dy)
                    if point in remaining:
                        remaining.remove(point)
                        component.add(point)
                        queue.append(point)
        result.append(component)
    return result


def detect_face(
    image: Image.Image,
) -> tuple[str, tuple[int, int, int, int] | None, list[tuple[int, int]]]:
    body = alpha_bbox(image)
    body_height = body[3] - body[1]
    search = (body[0], body[1], body[2], body[1] + round(body_height * 0.62))
    components = _components_for_colors(image, SKIN_COLORS, search)
    if not components:
        return "hidden", None, []
    component = max(
        components,
        key=lambda points: (
            len(points) * 8
            - min(y for _x, y in points) * 2
            + round(sum(x for x, _y in points) / len(points))
        ),
    )
    left = min(x for x, _y in component)
    top = min(y for _x, y in component)
    right = max(x for x, _y in component) + 1
    bottom = max(y for _x, y in component) + 1
    face = (left, top, right - left, bottom - top)
    if len(component) < 6 or face[2] < 3 or face[3] < 4:
        return "hidden", None, []

    eye_candidates: list[tuple[int, int]] = []
    for y in range(top, bottom):
        for x in range(left, right):
            if image.getpixel((x, y)) not in EYE_COLORS:
                continue
            adjacent_skin = any(
                0 <= x + dx < image.width
                and 0 <= y + dy < image.height
                and image.getpixel((x + dx, y + dy)) in SKIN_COLORS
                for dy in (-1, 0, 1)
                for dx in (-1, 0, 1)
                if dx or dy
            )
            if adjacent_skin:
                eye_candidates.append((x, y))
    pair: list[tuple[int, int]] = []
    for first in eye_candidates:
        for second in eye_candidates:
            if abs(first[0] - second[0]) >= 2:
                pair = [first, second]
                break
        if pair:
            break
    if len(component) >= 14 and face[2] >= 6 and face[3] >= 7 and pair:
        return "front", face, pair
    return "profile", face, pair[:1]


def annotations_for_frame(
    image: Image.Image, action: str, index: int
) -> tuple[list[int] | None, list[list[int]], list[int] | None, str]:
    """Describe only facial pixels that really survived final-scale packing."""

    _coarse_visibility, face, _coarse_eyes = detect_face(image)
    if face is None:
        if action == "idle":
            raise ValueError(f"idle[{index}] lost its warm face at native scale")
        return None, [], None, "hidden"
    fx, fy, fw, fh = face
    skin_points = {
        (x, y)
        for y in range(fy, fy + fh)
        for x in range(fx, fx + fw)
        if image.getpixel((x, y)) in SKIN_COLORS
    }
    interior_bottom = fy + max(2, (fh * 2) // 3)
    eye_candidates = [
        (x, y)
        for y in range(fy + 1, interior_bottom)
        for x in range(fx + 1, fx + fw - 1)
        if image.getpixel((x, y)) in EYE_COLORS
        and any(
            (x + dx, y + dy) in skin_points
            for dy in (-1, 0, 1)
            for dx in (-1, 0, 1)
            if dx or dy
        )
    ]
    # Prefer a same-row pair in the middle of the face.  A single surviving
    # cue is recorded honestly as profile; no coordinate or color is injected.
    eye_candidates.sort(key=lambda point: (abs(point[1] - (fy + fh * 0.42)), point[0]))
    eyes: list[tuple[int, int]] = []
    if eye_candidates:
        eyes = [eye_candidates[0]]
        compatible = [
            point
            for point in eye_candidates[1:]
            if abs(point[0] - eyes[0][0]) >= 2
            and abs(point[1] - eyes[0][1]) <= 1
        ]
        if compatible:
            compatible.sort(key=lambda point: (abs(point[1] - eyes[0][1]), point[0]))
            eyes.append(compatible[0])

    if action == "idle" and not eyes:
        raise ValueError(f"idle[{index}] has no real dark eye cue beside warm skin")
    search = (
        max(0, fx - 14),
        max(0, fy - 8),
        min(image.width, fx + max(2, fw // 3)),
        min(image.height, fy + fh + 1),
    )
    mask_points = [
        (x, y)
        for y in range(search[1], search[3])
        for x in range(search[0], search[2])
        if image.getpixel((x, y)) in MASK_COLORS
    ]
    mask: tuple[int, int, int, int] | None = None
    if mask_points:
        mask = (
            min(x for x, _y in mask_points),
            min(y for _x, y in mask_points),
            max(x for x, _y in mask_points) - min(x for x, _y in mask_points) + 1,
            max(y for _x, y in mask_points) - min(y for _x, y in mask_points) + 1,
        )
    visibility = "front" if len(eyes) >= 2 else "profile"
    return (
        list(face),
        [list(point) for point in eyes],
        list(mask) if mask is not None else None,
        visibility,
    )


def foot_zones(image: Image.Image, action: str) -> list[list[int]]:
    if action in {"dead", "ult"}:
        return []
    left, _top, right, bottom = alpha_bbox(image)
    zone_top = max(image.height // 2, bottom - 4)
    return [[left, zone_top, right - left, bottom - zone_top]]


def frame_quality(image: Image.Image) -> dict[str, float | int]:
    bbox = alpha_bbox(image)
    opaque = [color for color in pixels(image) if color[3] == 255]
    if not opaque:
        raise ValueError("V6 quality audit received an empty frame")
    lumas = sorted(luminance(color) for color in opaque)
    low = lumas[len(lumas) // 10]
    high = lumas[min(len(lumas) - 1, (len(lumas) * 9) // 10)]
    area = (bbox[2] - bbox[0]) * (bbox[3] - bbox[1])
    core_top = bbox[1] + (bbox[3] - bbox[1]) // 4
    core_bottom = bbox[1] + ((bbox[3] - bbox[1]) * 3) // 4
    alpha = image.getchannel("A")
    row_widths: list[int] = []
    for y in range(core_top, max(core_top + 1, core_bottom)):
        xs = [x for x in range(bbox[0], bbox[2]) if alpha.getpixel((x, y))]
        if xs:
            row_widths.append(max(xs) - min(xs) + 1)
    row_widths.sort()
    return {
        "opaque_pixels": len(opaque),
        "bbox_width": bbox[2] - bbox[0],
        "bbox_height": bbox[3] - bbox[1],
        "core_width_p50": row_widths[len(row_widths) // 2] if row_widths else 0,
        "body_density": round(len(opaque) / max(1, area), 4),
        "luminance_contrast_p80": round(high - low, 2),
        "dark_ratio": round(
            sum(luma <= 60 for luma in lumas) / len(lumas), 4
        ),
        "bright_ratio": round(
            sum(luma >= 160 for luma in lumas) / len(lumas), 4
        ),
    }


def frame_rects() -> dict[tuple[str, int], tuple[int, int, int, int]]:
    result: dict[tuple[str, int], tuple[int, int, int, int]] = {}
    for action in build_yone.NATIVE_BODY_ACTIONS:
        rects = build_yone.NATIVE_CONTRACT[action]["rects"]
        if action == "dead":
            rects = rects[:-1]
        for index, rect in enumerate(rects):
            result[(action, index)] = tuple(rect)
    if len(result) != 54:
        raise ValueError(f"V6 native contract changed: {len(result)}/54")
    return result


def load_subjects() -> tuple[dict[tuple[str, int], Image.Image], dict[str, str]]:
    hashes: dict[str, str] = {}
    for label, path in SOURCE_PATHS.items():
        if not path.is_file():
            raise FileNotFoundError(path)
        hashes[label] = sha256(path)
        if hashes[label] != EXPECTED_SOURCE_SHA256[label]:
            raise ValueError(f"accepted Yone V6 source hash changed: {label}")

    motion = Image.open(MOTION_SOURCE).convert("RGBA")
    attack = Image.open(ATTACK_SOURCE).convert("RGBA")
    w_sheet = Image.open(W_SOURCE).convert("RGBA")
    ult = Image.open(ULT_SOURCE).convert("RGBA")
    subjects: dict[tuple[str, int], Image.Image] = {}
    for index in range(20):
        subjects[("motion", index)] = split_cell(motion, 5, 4, index)
    for index in range(24):
        subjects[("attack_q_w", index)] = split_cell(attack, 6, 4, index)
    for index in range(6):
        subjects[("w", index)] = split_cell(w_sheet, 3, 2, index)
    for index in range(15):
        subjects[("ult", index)] = split_cell(ult, 5, 3, index)
    install_source_palette(subjects)
    return subjects, hashes


def build_frames() -> tuple[
    list[dict[str, Any]],
    dict[tuple[str, int], Image.Image],
    list[dict[str, Any]],
    dict[str, str],
]:
    subjects, source_hashes = load_subjects()
    rects = frame_rects()
    rows: list[dict[str, Any]] = []
    frames: dict[tuple[str, int], Image.Image] = {}
    audits: list[dict[str, Any]] = []

    for action in build_yone.NATIVE_BODY_ACTIONS:
        assignments = ACTION_SOURCES[action]
        shifts = X_SHIFTS[action]
        expected_count = sum(1 for frame_action, _index in rects if frame_action == action)
        if len(assignments) != expected_count or len(shifts) != expected_count:
            raise ValueError(
                f"V6 {action} mapping mismatch: {len(assignments)}/{expected_count}"
            )
        for index, ((source_kind, cell_index), x_shift) in enumerate(
            zip(assignments, shifts, strict=True)
        ):
            x, y, width, height = rects[(action, index)]
            if action == "dead":
                target_height = DEAD_TARGET_HEIGHTS[index]
                bottom_margin = DEAD_BOTTOM_MARGINS[index]
            else:
                target_height = build_yone.BODY_TARGET_HEIGHTS[action][index]
                bottom_margin = build_yone.BODY_BOTTOM_MARGINS[action][index]
                minimum_height = build_yone.NATIVE_MIN_VISIBLE_HEIGHTS[action][index]
                target_height = max(target_height, minimum_height)
                bottom_margin = min(bottom_margin, height - minimum_height - 1)

            subject_key = (source_kind, int(cell_index))
            subject = subjects[subject_key]
            image, fit_audit = fit_pose(
                subject,
                (width, height),
                visible_height=target_height,
                bottom_margin=bottom_margin,
                x_shift=x_shift,
            )

            bbox = alpha_bbox(image)
            if any(
                image.getchannel("A").getpixel(point)
                for point in (
                    *((x_pos, 0) for x_pos in range(image.width)),
                    *((x_pos, image.height - 1) for x_pos in range(image.width)),
                    *((0, y_pos) for y_pos in range(image.height)),
                    *((image.width - 1, y_pos) for y_pos in range(image.height)),
                )
            ):
                raise ValueError(f"{action}[{index}] touches a native edge")
            if set(pixels(image)) - ALLOWED_COLORS:
                raise ValueError(f"{action}[{index}] escaped the V6 palette")
            if set(pixels(image.getchannel("A"))) - {0, 255}:
                raise ValueError(f"{action}[{index}] alpha is not hard")

            face, eyes, mask, visibility = annotations_for_frame(image, action, index)

            relative = f"frames/{action}_{index:02d}.png"
            path = V6_ROOT / relative
            save_png(path, image)
            row = {
                "action": action,
                "index": index,
                "file": relative,
                "rect": [x, y, width, height],
                "bottom_margin": height - bbox[3],
                "face_bbox": face,
                "eye_pixels": eyes,
                "mask_bbox": mask,
                "foot_zones": foot_zones(image, action),
                "face_visibility": visibility,
            }
            rows.append(row)
            frames[(action, index)] = image
            quality = frame_quality(image)
            audits.append(
                {
                    "action": action,
                    "index": index,
                    "source": source_kind,
                    "cell": cell_index,
                    "size": [width, height],
                    "visible_size": [bbox[2] - bbox[0], bbox[3] - bbox[1]],
                    "bottom_margin": height - bbox[3],
                    "face_visibility": visibility,
                    "hard_alpha": True,
                    "transparent_edges": True,
                    "opaque_colors": len(
                        {color for color in pixels(image) if color[3] == 255}
                    ),
                    **quality,
                    **fit_audit,
                }
            )

    if len(rows) != 54 or len(frames) != 54:
        raise ValueError(f"generated {len(rows)}/54 V6 frames")
    return rows, frames, audits, source_hashes


def build_card_preview(idle: Image.Image) -> Image.Image:
    rendered = idle.resize(
        (
            round(idle.width * build_yone.YONE_LIVE_CARD_SCALE),
            round(idle.height * build_yone.YONE_LIVE_CARD_SCALE),
        ),
        Image.Resampling.NEAREST,
    )
    # Reconstruct the complete opaque card surface.  The actor route itself is
    # still the exact engine route below: full 43x55 idle frame, 2.2x NEAREST,
    # centered at (23, 0), with divider y=96 and right icon region untouched.
    preview = Image.new("RGBA", (141, 138), (15, 17, 26, 255))
    draw = ImageDraw.Draw(preview)
    draw.rounded_rectangle(
        (4, 4, 137, 136), radius=11, fill=(20, 21, 31, 255),
        outline=(66, 70, 83, 255), width=1,
    )
    draw.line((5, 96, 136, 96), fill=(43, 46, 57, 255), width=1)
    stage_height = max(
        round(rect[3] * build_yone.YONE_LIVE_CARD_SCALE)
        for rect in build_yone.NATIVE_CONTRACT["idle"]["rects"]
    )
    actor_x = (preview.width - rendered.width) // 2
    actor_y = (stage_height - rendered.height) // 2
    preview.alpha_composite(rendered, (actor_x, actor_y))
    actor_mask = Image.new("L", preview.size, 0)
    actor_mask.paste(rendered.getchannel("A"), (actor_x, actor_y))
    actor_bbox = actor_mask.getbbox()
    if actor_bbox is None:
        raise ValueError("V6 card preview lost the actor")
    if actor_mask.crop((98, 70, 141, 100)).getbbox() is not None:
        raise ValueError("V6 card actor overlaps the right-side UI icon region")
    if 96 - actor_bbox[3] < 6:
        raise ValueError(f"V6 card divider clearance regressed: {96 - actor_bbox[3]}")
    # Compact neutral placeholders make the icon-safe area visible in review;
    # they are card chrome, never part of the actor alpha audit.
    draw.arc((99, 72, 112, 88), 290, 70, fill=(236, 238, 242, 255), width=2)
    draw.rectangle((119, 76, 130, 87), outline=(217, 220, 228, 255), width=2)
    draw.rectangle((122, 79, 127, 84), fill=(104, 110, 125, 255))
    return preview


def build_contact_preview(
    rows: list[dict[str, Any]], frames: dict[tuple[str, int], Image.Image]
) -> Image.Image:
    columns = 6
    scale = 3
    maximum_width = max(frame.width for frame in frames.values())
    maximum_height = max(frame.height for frame in frames.values())
    cell_width = maximum_width * scale + 10
    cell_height = maximum_height * scale + 26
    total_rows = (len(rows) + columns - 1) // columns
    preview = Image.new(
        "RGBA", (columns * cell_width, total_rows * cell_height), (8, 13, 23, 255)
    )
    draw = ImageDraw.Draw(preview)
    for order, row in enumerate(rows):
        column = order % columns
        contact_row = order // columns
        left = column * cell_width
        top = contact_row * cell_height
        frame = frames[(row["action"], row["index"])]
        rendered = frame.resize(
            (frame.width * scale, frame.height * scale), Image.Resampling.NEAREST
        )
        x = left + (cell_width - rendered.width) // 2
        y = top + 18 + (maximum_height * scale - rendered.height)
        preview.alpha_composite(rendered, (x, y))
        draw.text(
            (left + 2, top + 2),
            f"{row['action']}[{row['index']}] {row['face_visibility'][0]}",
            fill=(225, 230, 239, 255),
        )
    return preview


def main() -> int:
    FRAME_ROOT.mkdir(parents=True, exist_ok=True)
    PREVIEW_ROOT.mkdir(parents=True, exist_ok=True)
    for path in FRAME_ROOT.glob("*.png"):
        path.unlink()
    for path in (BODY_PREVIEW, CONTACT_PREVIEW, FRAME_MANIFEST, PALETTE_PATH, QA_PATH):
        if path.exists():
            path.unlink()

    rows, frames, audits, source_hashes = build_frames()
    card_preview = build_card_preview(frames[("idle", 0)])
    contact_preview = build_contact_preview(rows, frames)
    save_png(BODY_PREVIEW, card_preview)
    save_png(CONTACT_PREVIEW, contact_preview)
    write_json(
        PALETTE_PATH,
        {
            "schema_version": 6,
            "route": "exact-native-v6",
            "colors": [
                {"role": role, "rgba": list(color)} for role, color in PALETTE_ROWS
            ],
        },
    )
    write_json(
        FRAME_MANIFEST,
        {
            "schema_version": 6,
            "route": "exact-native-v6",
            "atlas_size": list(build_yone.ACTOR_SHEET_SIZE),
            "palette_file": "palette.json",
            "body_preview": "preview/yone_v6_actor_card.png",
            "frames": rows,
        },
    )
    failures: list[str] = []
    if len(rows) != 54:
        failures.append(f"frame_count={len(rows)}")
    if any(not audit["hard_alpha"] for audit in audits):
        failures.append("soft_alpha")
    if any(not audit["transparent_edges"] for audit in audits):
        failures.append("opaque_edge")
    if len(PALETTE) > 48 or any(audit["opaque_colors"] > 48 for audit in audits):
        failures.append("palette_over_48")
    for audit in audits:
        label = f"{audit['action']}[{audit['index']}]"
        if audit["luminance_contrast_p80"] < 58:
            failures.append(f"low_contrast:{label}")
        if not 0.06 <= audit["dark_ratio"] <= 0.84:
            failures.append(f"dark_ratio:{label}")
        if audit["body_density"] < 0.10:
            failures.append(f"low_density:{label}")
        core_frame = audit["action"] in {
            "idle", "run", "hit", "skill2", "skill2_dash", "skill2_attack"
        }
        if core_frame and audit["bbox_width"] < 13:
            failures.append(f"abnormally_narrow_bbox:{label}")
        if core_frame and audit["core_width_p50"] < 8:
            failures.append(f"abnormally_narrow_core:{label}")
        if (
            audit["action"] in {"idle", "run", "hit"}
            and audit["horizontal_crop_ratio"] > 0.08
        ):
            failures.append(f"core_horizontal_crop:{label}")
        if core_frame and audit["horizontal_crop_ratio"] > 0.40:
            failures.append(f"excessive_horizontal_crop:{label}")
    for row in rows:
        if row["action"] != "idle":
            continue
        label = f"idle[{row['index']}]"
        face = row["face_bbox"]
        if face is None or face[2] < 5 or face[3] < 5:
            failures.append(f"small_face:{label}")
            continue
        if not row["eye_pixels"]:
            failures.append(f"missing_eye:{label}")
        frame = frames[("idle", row["index"])]
        fx, fy, fw, fh = face
        warm_pixels = sum(
            frame.getpixel((x, y)) in SKIN_COLORS
            for y in range(fy, fy + fh)
            for x in range(fx, fx + fw)
        )
        if warm_pixels < 8:
            failures.append(f"weak_warm_face:{label}")
    write_json(
        QA_PATH,
        {
            "schema_version": 6,
            "route": "exact-native-v6",
            "frame_count": len(rows),
            "contact_preview": "preview/yone_v6_native_contact.png",
            "source_hashes": source_hashes,
            "source_layouts": {
                "motion": [5, 4],
                "attack_q_w": [6, 4],
                "w": [3, 2],
                "ult": [5, 3],
            },
            "source_to_native_resampling": "LANCZOS",
            "hard_alpha_threshold": 96,
            "opaque_palette_size": len(PALETTE),
            "face_visibility_values": ["front", "profile", "hidden"],
            "idle0_pixel_sha256": pixel_sha256(frames[("idle", 0)]),
            "card_alpha_bbox": list(alpha_bbox(card_preview)),
            "failures": failures,
            "frames": audits,
        },
    )
    if failures:
        raise ValueError(f"V6 generation QA failed: {failures}")
    hidden = sum(row["face_visibility"] == "hidden" for row in rows)
    profile = sum(row["face_visibility"] == "profile" for row in rows)
    front = len(rows) - hidden - profile
    cropped = sum(audit["horizontal_crop"] for audit in audits)
    print(
        "generated Yone V6 exact-native source: "
        f"54 frames, face front/profile/hidden={front}/{profile}/{hidden}, "
        f"palette={len(PALETTE)}, horizontal_weapon_crops={cropped}, failures=0, "
        f"card_bbox={alpha_bbox(card_preview)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
