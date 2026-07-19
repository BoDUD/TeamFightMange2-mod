from __future__ import annotations

import hashlib
import json
import shutil
from collections import deque
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw

import build_yone


MOD_ROOT = Path(__file__).resolve().parents[1]
IMAGEGEN_ROOT = MOD_ROOT / "source/imagegen"
GOLDEN_SOURCE = IMAGEGEN_ROOT / "yone_v5_idle_golden_43x55.png"
MOTION_SOURCE = IMAGEGEN_ROOT / "yone_v5_motion_contact.png"
ATTACK_SOURCE = IMAGEGEN_ROOT / "yone_v5_attack_q_w_contact.png"
Q5_SOURCE = IMAGEGEN_ROOT / "yone_v5_q5_contact.png"
ULT_SOURCE = IMAGEGEN_ROOT / "yone_v5_ult_contact.png"

V5_ROOT = MOD_ROOT / "source/native/yone_v5"
FRAME_ROOT = V5_ROOT / "frames"
PREVIEW_ROOT = V5_ROOT / "preview"
FRAME_MANIFEST = V5_ROOT / "frames.json"
PALETTE_PATH = V5_ROOT / "palette.json"
QA_PATH = V5_ROOT / "generation_qa.json"
BODY_PREVIEW = PREVIEW_ROOT / "yone_v5_actor_card.png"
CONTACT_PREVIEW = PREVIEW_ROOT / "yone_v5_native_contact.png"

EXPECTED_SOURCE_SHA256 = {
    "golden": "52ab8e7a6c74591213487f3abd8907e5b1e6481647473fda6c5e144439f99de4",
    "motion": "f20b8a6287729b516078a986b2fe51c8fd8f8bbea6cf8aeaa83bd3174ea4cc89",
    "attack_q_w": "2b0cbbe7cebe320719af33615b4324cf944398aafe008c96488aeb9884ee8de7",
    "q5_single": "2c9fe1578a8b2171cca63c967d47875ee9e2b44df7ba6093b817f383134eb5e0",
    "ult": "66e6d96b6eb1365e03e42f5aac52e662535d37c2c8993a5518fa338a9243d0c4",
}
SOURCE_PATHS = {
    "golden": GOLDEN_SOURCE,
    "motion": MOTION_SOURCE,
    "attack_q_w": ATTACK_SOURCE,
    "q5_single": Q5_SOURCE,
    "ult": ULT_SOURCE,
}

# One transparent entry plus 31 opaque role colors.  The eye role is exact:
# skin_shadow deliberately does not contain the word "eye", unlike V4's
# skin_shadow_eye typo.  Consumers must use EYE_COLORS, never substring-match
# arbitrary role names.
PALETTE_ROWS: tuple[tuple[str, tuple[int, int, int, int]], ...] = (
    ("transparent", (0, 0, 0, 0)),
    ("eye_outline", (2, 4, 10, 255)),
    ("hair_deep", (8, 10, 20, 255)),
    ("hair_shadow", (15, 19, 32, 255)),
    ("cloth_navy", (25, 30, 46, 255)),
    ("cloth_mid", (39, 46, 67, 255)),
    ("cloth_light", (58, 67, 91, 255)),
    ("mask_umber", (67, 24, 18, 255)),
    ("skin_shadow", (105, 55, 31, 255)),
    ("skin_brown", (143, 82, 43, 255)),
    ("skin_mid", (184, 113, 63, 255)),
    ("skin_light", (224, 157, 96, 255)),
    ("skin_highlight", (244, 198, 142, 255)),
    ("mask_deep", (61, 3, 8, 255)),
    ("mask_shadow", (112, 5, 10, 255)),
    ("mask_red", (166, 10, 12, 255)),
    ("mask_light", (221, 28, 18, 255)),
    ("mask_highlight", (244, 70, 20, 255)),
    ("gold_deep", (92, 51, 10, 255)),
    ("gold_shadow", (151, 91, 15, 255)),
    ("gold_mid", (195, 131, 25, 255)),
    ("gold_light", (236, 181, 47, 255)),
    ("steel_deep", (25, 45, 68, 255)),
    ("steel_shadow", (53, 83, 116, 255)),
    ("steel_mid", (85, 151, 205, 255)),
    ("steel_light", (151, 219, 244, 255)),
    ("steel_highlight", (218, 237, 241, 255)),
    ("steel_white", (245, 242, 224, 255)),
    ("neutral_mid", (102, 106, 116, 255)),
    ("neutral_light", (153, 158, 166, 255)),
    ("leather_deep", (61, 45, 27, 255)),
    ("leather_mid", (91, 74, 46, 255)),
)
PALETTE = tuple(color for _role, color in PALETTE_ROWS if color[3] == 255)
ALLOWED_COLORS = {color for _role, color in PALETTE_ROWS}
SKIN_COLORS = {
    color for role, color in PALETTE_ROWS if role.startswith("skin_")
}
EYE_COLORS = {
    color for role, color in PALETTE_ROWS if role == "eye_outline"
}
MASK_COLORS = {
    color for role, color in PALETTE_ROWS if role.startswith("mask_")
}

# Cell indices are zero-based.  B12 is the broken sword-only source cell and
# is intentionally absent; skill[5] comes from the independent Q5 source.
ACTION_SOURCES: dict[str, tuple[tuple[str, int | None], ...]] = {
    "skill2": (("attack_q_w", 19),),
    "hit": (("motion", 4),),
    "attack": tuple(("attack_q_w", index) for index in range(1, 7)),
    "skill2_dash": (("attack_q_w", 19),),
    "ult": tuple(("ult", index) for index in range(1, 14)),
    "run": tuple(("motion", index) for index in range(5, 13)),
    "skill2_attack": tuple(("attack_q_w", index) for index in range(14, 19)),
    "idle": (
        ("golden", None),
        ("golden", None),
        ("golden", None),
        ("golden", None),
    ),
    "dead": tuple(("motion", index) for index in range(13, 20))
    + (("motion", 19),),
    "skill": (
        ("attack_q_w", 7),
        ("attack_q_w", 8),
        ("attack_q_w", 9),
        ("attack_q_w", 10),
        ("attack_q_w", 11),
        ("q5_single", None),
        ("attack_q_w", 13),
    ),
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


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(
        (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    )


def save_png(path: Path, image: Image.Image) -> None:
    if image.mode != "RGBA":
        raise ValueError(f"V5 PNG must be RGBA: {path} {image.mode}")
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, format="PNG", optimize=False, compress_level=9)


def alpha_bbox(image: Image.Image) -> tuple[int, int, int, int]:
    bbox = image.getchannel("A").getbbox()
    if bbox is None:
        raise ValueError("empty V5 image")
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
    """Resize the high-resolution source exactly once into a native frame."""

    frame_width, frame_height = frame_size
    if visible_height + bottom_margin >= frame_height:
        visible_height = frame_height - bottom_margin - 1
    if visible_height < 1:
        raise ValueError((frame_size, visible_height, bottom_margin))

    original_core_x = core_center_x(subject)
    target_width = max(1, round(subject.width * visible_height / subject.height))
    # This is the only source resize in the route: cell -> final native scale.
    fitted = subject.resize(
        (target_width, visible_height), Image.Resampling.NEAREST
    )
    fitted.putalpha(
        fitted.getchannel("A").point(lambda value: 255 if value >= 128 else 0)
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
            f"V5 pose {fitted.size} cannot fit {frame_size} at bottom {bottom_margin}"
        )

    # Clip weapons to the transparent one-pixel inner viewport.  Cropping is
    # performed after the one direct resize and cannot shrink the actor body.
    source_left = max(0, 1 - paste_x)
    source_right = min(fitted.width, frame_width - 1 - paste_x)
    source_top = max(0, 1 - paste_y)
    source_bottom = min(fitted.height, frame_height - 1 - paste_y)
    if source_right <= source_left or source_bottom <= source_top:
        raise ValueError("V5 pose lies outside its native frame")
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


def idle_annotations(
    image: Image.Image, idle_index: int
) -> tuple[list[int], list[list[int]], list[int], str]:
    if idle_index == 0:
        face = (16, 10, 9, 10)
        eyes = [(17, 13), (19, 13)]
        mask = (9, 5, 9, 18)
        if any(image.getpixel(point) not in EYE_COLORS for point in eyes):
            raise ValueError("idle[0] true-eye coordinates changed")
        if image.getpixel((18, 13)) != (245, 242, 224, 255):
            raise ValueError("idle[0] white eye highlight changed")
        return list(face), [list(point) for point in eyes], list(mask), "front"

    visibility, face, _detected_eyes = detect_face(image)
    if visibility != "front" or face is None:
        raise ValueError(f"idle[{idle_index}] does not retain a readable front face")
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
    if not eye_candidates:
        raise ValueError(f"idle[{idle_index}] has no true interior eye beside skin")
    # Prefer the lowest upper-face cue (actual eye row) over hair/brow pixels.
    eye_candidates.sort(key=lambda point: (-point[1], point[0]))
    eyes = [eye_candidates[0]]
    for point in eye_candidates[1:]:
        if abs(point[0] - eyes[0][0]) >= 2:
            eyes.append(point)
            break
    search = (
        max(0, fx - 14),
        max(0, fy - 8),
        min(image.width, fx + 2),
        min(image.height, fy + fh + 3),
    )
    mask_points = [
        (x, y)
        for y in range(search[1], search[3])
        for x in range(search[0], search[2])
        if image.getpixel((x, y)) in MASK_COLORS
    ]
    if len(mask_points) < 4:
        raise ValueError(f"idle[{idle_index}] has no readable rear mask")
    mask = (
        min(x for x, _y in mask_points),
        min(y for _x, y in mask_points),
        max(x for x, _y in mask_points) - min(x for x, _y in mask_points) + 1,
        max(y for _x, y in mask_points) - min(y for _x, y in mask_points) + 1,
    )
    # The final interior-eye filter is stricter than the coarse face detector.
    # Describe one-eye 3/4 frames honestly as profile; never label a hair/brow
    # pair as a second readable eye merely to satisfy metadata.
    visibility = "front" if len(eyes) >= 2 else "profile"
    return list(face), [list(point) for point in eyes], list(mask), visibility


def foot_zones(image: Image.Image, action: str) -> list[list[int]]:
    if action in {"dead", "ult"}:
        return []
    left, _top, right, bottom = alpha_bbox(image)
    zone_top = max(image.height // 2, bottom - 4)
    return [[left, zone_top, right - left, bottom - zone_top]]


def frame_rects() -> dict[tuple[str, int], tuple[int, int, int, int]]:
    result: dict[tuple[str, int], tuple[int, int, int, int]] = {}
    for action in build_yone.NATIVE_BODY_ACTIONS:
        rects = build_yone.NATIVE_CONTRACT[action]["rects"]
        if action == "dead":
            rects = rects[:-1]
        for index, rect in enumerate(rects):
            result[(action, index)] = tuple(rect)
    if len(result) != 54:
        raise ValueError(f"V5 native contract changed: {len(result)}/54")
    return result


def load_subjects() -> tuple[
    dict[tuple[str, int], Image.Image], Image.Image, dict[str, str]
]:
    hashes: dict[str, str] = {}
    for label, path in SOURCE_PATHS.items():
        if not path.is_file():
            raise FileNotFoundError(path)
        hashes[label] = sha256(path)
        if hashes[label] != EXPECTED_SOURCE_SHA256[label]:
            raise ValueError(f"accepted Yone V5 source hash changed: {label}")

    motion = Image.open(MOTION_SOURCE).convert("RGBA")
    attack = Image.open(ATTACK_SOURCE).convert("RGBA")
    ult = Image.open(ULT_SOURCE).convert("RGBA")
    subjects: dict[tuple[str, int], Image.Image] = {}
    for index in range(20):
        subjects[("motion", index)] = split_cell(motion, 5, 4, index)
        subjects[("attack_q_w", index)] = split_cell(attack, 5, 4, index)
    for index in range(15):
        subjects[("ult", index)] = split_cell(ult, 5, 3, index)
    subjects[("q5_single", 0)] = prepare_subject(
        Image.open(Q5_SOURCE).convert("RGBA")
    )
    golden = Image.open(GOLDEN_SOURCE).convert("RGBA")
    if golden.size != (43, 55):
        raise ValueError(f"golden idle size changed: {golden.size}")
    if set(golden.getdata()) - ALLOWED_COLORS:
        raise ValueError("golden idle uses colors outside the fixed V5 palette")
    if set(golden.getchannel("A").getdata()) - {0, 255}:
        raise ValueError("golden idle alpha is not hard")
    return subjects, golden, hashes


def golden_variant(
    golden: Image.Image,
    frame_size: tuple[int, int],
    target_height: int,
    bottom_margin: int,
    x_shift: int,
) -> tuple[Image.Image, dict[str, Any]]:
    subject = golden.crop(alpha_bbox(golden))
    image, audit = fit_pose(
        subject,
        frame_size,
        visible_height=target_height,
        bottom_margin=bottom_margin,
        x_shift=x_shift,
    )
    audit["idle_fallback"] = "golden-native"
    return image, audit


def build_frames() -> tuple[
    list[dict[str, Any]],
    dict[tuple[str, int], Image.Image],
    list[dict[str, Any]],
    dict[str, str],
]:
    subjects, golden, source_hashes = load_subjects()
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
                f"V5 {action} mapping mismatch: {len(assignments)}/{expected_count}"
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

            if (action, index) == ("idle", 0):
                image = golden.copy()
                fit_audit = {
                    "source_subject_size": list(golden.size),
                    "direct_resize_size": None,
                    "pelvis_center_x": None,
                    "paste_xy": None,
                    "horizontal_crop": False,
                    "cropped_source_columns": 0,
                    "alpha_bbox": list(alpha_bbox(image)),
                    "idle_fallback": "byte-exact-golden",
                }
            else:
                if source_kind == "golden":
                    image, fit_audit = golden_variant(
                        golden,
                        (width, height),
                        target_height,
                        bottom_margin,
                        x_shift,
                    )
                else:
                    subject_key = (
                        (source_kind, 0)
                        if source_kind == "q5_single"
                        else (source_kind, int(cell_index))
                    )
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
            if set(image.getdata()) - ALLOWED_COLORS:
                raise ValueError(f"{action}[{index}] escaped the fixed palette")
            if set(image.getchannel("A").getdata()) - {0, 255}:
                raise ValueError(f"{action}[{index}] alpha is not hard")

            visibility, _detected_face, _detected_eyes = detect_face(image)
            if action == "idle":
                face, eyes, mask, visibility = idle_annotations(image, index)
            else:
                face, eyes, mask = None, [], None

            relative = f"frames/{action}_{index:02d}.png"
            path = V5_ROOT / relative
            if (action, index) == ("idle", 0):
                path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(GOLDEN_SOURCE, path)
            else:
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
                        {color for color in image.getdata() if color[3] == 255}
                    ),
                    **fit_audit,
                }
            )

    if len(rows) != 54 or len(frames) != 54:
        raise ValueError(f"generated {len(rows)}/54 V5 frames")
    if pixel_sha256(frames[("idle", 0)]) != pixel_sha256(golden):
        raise ValueError("idle[0] is not byte-exact to the golden pixel buffer")
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
        raise ValueError("V5 card preview lost the actor")
    if actor_mask.crop((98, 70, 141, 100)).getbbox() is not None:
        raise ValueError("V5 card actor overlaps the right-side UI icon region")
    if 96 - actor_bbox[3] < 6:
        raise ValueError(f"V5 card divider clearance regressed: {96 - actor_bbox[3]}")
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
            "schema_version": 5,
            "route": "exact-native-v5",
            "colors": [
                {"role": role, "rgba": list(color)} for role, color in PALETTE_ROWS
            ],
        },
    )
    write_json(
        FRAME_MANIFEST,
        {
            "schema_version": 5,
            "route": "exact-native-v5",
            "atlas_size": list(build_yone.ACTOR_SHEET_SIZE),
            "palette_file": "palette.json",
            "body_preview": "preview/yone_v5_actor_card.png",
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
    if any(audit["opaque_colors"] > 31 for audit in audits):
        failures.append("palette_over_31")
    write_json(
        QA_PATH,
        {
            "schema_version": 1,
            "route": "exact-native-v5",
            "frame_count": len(rows),
            "contact_preview": "preview/yone_v5_native_contact.png",
            "source_hashes": source_hashes,
            "face_visibility_values": ["front", "profile", "hidden"],
            "idle0_pixel_sha256": pixel_sha256(frames[("idle", 0)]),
            "golden_pixel_sha256": pixel_sha256(
                Image.open(GOLDEN_SOURCE).convert("RGBA")
            ),
            "card_alpha_bbox": list(alpha_bbox(card_preview)),
            "failures": failures,
            "frames": audits,
        },
    )
    if failures:
        raise ValueError(f"V5 generation QA failed: {failures}")
    hidden = sum(row["face_visibility"] == "hidden" for row in rows)
    profile = sum(row["face_visibility"] == "profile" for row in rows)
    front = len(rows) - hidden - profile
    cropped = sum(audit["horizontal_crop"] for audit in audits)
    print(
        "generated Yone V5 exact-native source: "
        f"54 frames, face front/profile/hidden={front}/{profile}/{hidden}, "
        f"horizontal_weapon_crops={cropped}, failures=0, "
        f"card_bbox={alpha_bbox(card_preview)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
