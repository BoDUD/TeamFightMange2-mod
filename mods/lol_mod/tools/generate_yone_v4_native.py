from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from PIL import Image

import build_yone


MOD_ROOT = Path(__file__).resolve().parents[1]
CONTACT_SOURCE = MOD_ROOT / "source/imagegen/yone_v4_action_contact.png"
IDLE0_SOURCE = MOD_ROOT / "source/imagegen/yone_v4_idle_candidate_43x55.png"
V4_ROOT = MOD_ROOT / "source/native/yone_v4"
FRAME_ROOT = V4_ROOT / "frames"
PREVIEW_ROOT = V4_ROOT / "preview"
FRAME_MANIFEST = V4_ROOT / "frames.json"
PALETTE_PATH = V4_ROOT / "palette.json"
BODY_PREVIEW = PREVIEW_ROOT / "yone_v4_actor_card.png"

EXPECTED_CONTACT_SHA256 = (
    "211f3f5145e413639f08af96718dc5f92ae67f615043b95d2cf8fc0096eec86c"
)
EXPECTED_IDLE0_SHA256 = (
    "e85e04135e545492255844a343ffc4116ac7af88f6aef878c9158e4b0875f980"
)
EXPECTED_IDLE0_PIXEL_SHA256 = (
    "4946f0af134be0657d19617215ea76be7fefb869943c7f49e201dd11a83da74c"
)

# One transparent entry plus 31 opaque role colors.  The body source and all
# final frames use this fixed palette; the generator never asks Pillow to
# quantize an already-authored V4 frame.
PALETTE_ROWS: tuple[tuple[str, tuple[int, int, int, int]], ...] = (
    ("transparent", (0, 0, 0, 0)),
    ("eye_outline", (2, 4, 10, 255)),
    ("hair_deep", (8, 10, 20, 255)),
    ("hair_shadow", (15, 19, 32, 255)),
    ("cloth_navy", (25, 30, 46, 255)),
    ("cloth_mid", (39, 46, 67, 255)),
    ("cloth_light", (58, 67, 91, 255)),
    ("mask_umber", (67, 24, 18, 255)),
    ("skin_shadow_eye", (105, 55, 31, 255)),
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
SKIN_COLORS = {
    color for role, color in PALETTE_ROWS if "skin" in role
}
EYE_COLORS = {
    color for role, color in PALETTE_ROWS if "eye" in role
}
MASK_COLORS = {
    color for role, color in PALETTE_ROWS if "mask" in role
}

# Twenty unified adult poses from the single accepted ImageGen contact.  Core
# animations use different source poses; repeated phases may shift by one
# pixel but are never replaced with a code-drawn body.
POSE_SEQUENCE: dict[str, tuple[int, ...]] = {
    "skill2": (14,),
    "hit": (13,),
    "attack": (5, 6, 7, 8, 9, 10),
    "skill2_dash": (4,),
    "ult": (8, 9, 15, 16, 4, 5, 6, 10, 12, 13, 15, 16, 14),
    "run": (2, 3, 15, 3, 2, 4, 15, 4),
    "skill2_attack": (0, 14, 5, 10, 8),
    "idle": (0, 1, 14, 1),
    "dead": (13, 17, 18, 19, 19, 19, 19, 19),
    "skill": (0, 14, 1, 6, 10, 15, 16),
}

# Small horizontal shifts add readable phase motion when an animation returns
# to an adjacent pose.  They do not alter the fixed bottom anchor.
X_SHIFTS: dict[str, tuple[int, ...]] = {
    "skill2": (0,),
    "hit": (-1,),
    "attack": (-1, 0, 1, 1, 0, -1),
    "skill2_dash": (1,),
    "ult": (-1, 0, 1, 1, 1, 0, -1, -1, 0, 1, 1, 0, -1),
    "run": (-1, 0, 1, 0, -1, 0, 1, 0),
    "skill2_attack": (-1, 0, 1, 0, -1),
    "idle": (0, 0, 0, 1),
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


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(
        (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    )


def save_png(path: Path, image: Image.Image) -> None:
    if image.mode != "RGBA":
        raise ValueError(f"V4 PNG must be RGBA: {path} {image.mode}")
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, format="PNG", optimize=False, compress_level=9)


def keyed(source: Image.Image) -> Image.Image:
    """Remove only the contact's saturated-magenta field."""

    rgba = source.convert("RGBA")
    result = Image.new("RGBA", rgba.size, (0, 0, 0, 0))
    source_pixels = rgba.load()
    output_pixels = result.load()
    for y in range(rgba.height):
        for x in range(rgba.width):
            red, green, blue, _alpha = source_pixels[x, y]
            if (
                red > 180
                and blue > 105
                and green < 135
                and red - green > 75
                and blue - green > 35
            ):
                continue
            output_pixels[x, y] = (red, green, blue, 255)
    return result


def palette_finish(image: Image.Image) -> Image.Image:
    """Map the high-resolution contact once into the locked role palette."""

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


def contact_pose(sheet: Image.Image, pose_index: int) -> Image.Image:
    if not 0 <= pose_index < 20:
        raise ValueError(f"invalid V4 contact pose {pose_index}")
    row, column = divmod(pose_index, 5)
    left = round(column * sheet.width / 5)
    right = round((column + 1) * sheet.width / 5)
    top = round(row * sheet.height / 4)
    bottom = round((row + 1) * sheet.height / 4)
    cell = keyed(sheet.crop((left, top, right, bottom)))
    bbox = cell.getchannel("A").getbbox()
    if bbox is None:
        raise ValueError(f"empty V4 contact pose {pose_index}")
    subject = cell.crop(bbox)
    native = subject.resize(
        (
            max(1, round(subject.width / 5)),
            max(1, round(subject.height / 5)),
        ),
        Image.Resampling.NEAREST,
    )
    native.putalpha(
        native.getchannel("A").point(lambda value: 255 if value >= 128 else 0)
    )
    bbox = native.getchannel("A").getbbox()
    if bbox is None:
        raise ValueError(f"empty reduced V4 contact pose {pose_index}")
    return palette_finish(native.crop(bbox))


def fit_pose(
    pose: Image.Image,
    frame_size: tuple[int, int],
    *,
    visible_height: int,
    bottom_margin: int,
    x_shift: int,
) -> Image.Image:
    """Raster one contact pose into its final native rectangle."""

    frame_width, frame_height = frame_size
    if not 1 <= bottom_margin < frame_height - 1:
        raise ValueError((frame_size, bottom_margin))
    maximum_width = frame_width - 2
    maximum_height = frame_height - bottom_margin - 1
    scale = min(
        visible_height / pose.height,
        maximum_width / pose.width,
        maximum_height / pose.height,
    )
    target = (
        max(1, round(pose.width * scale)),
        max(1, round(pose.height * scale)),
    )
    fitted = pose.resize(target, Image.Resampling.NEAREST)
    fitted.putalpha(
        fitted.getchannel("A").point(lambda value: 255 if value >= 128 else 0)
    )
    fitted_bbox = fitted.getchannel("A").getbbox()
    if fitted_bbox is None:
        raise ValueError("empty fitted V4 pose")
    fitted = fitted.crop(fitted_bbox)
    output = Image.new("RGBA", frame_size, (0, 0, 0, 0))
    x = (frame_width - fitted.width) // 2 + x_shift
    x = min(max(1, x), frame_width - fitted.width - 1)
    y = frame_height - bottom_margin - fitted.height
    if y < 1:
        raise ValueError(
            f"V4 pose {fitted.size} cannot fit {frame_size} with bottom {bottom_margin}"
        )
    output.alpha_composite(fitted, (x, y))
    bbox = output.getchannel("A").getbbox()
    if bbox is None or frame_height - bbox[3] != bottom_margin:
        raise ValueError(
            f"V4 bottom anchor changed: {frame_size}, bbox={bbox}, expected={bottom_margin}"
        )
    return output


def alpha_bbox(image: Image.Image) -> tuple[int, int, int, int]:
    bbox = image.getchannel("A").getbbox()
    if bbox is None:
        raise ValueError("empty V4 frame")
    return bbox


def _box_pixels(
    image: Image.Image, box: tuple[int, int, int, int]
) -> list[tuple[int, int, tuple[int, int, int, int]]]:
    x, y, width, height = box
    return [
        (px, py, image.getpixel((px, py)))
        for py in range(y, y + height)
        for px in range(x, x + width)
    ]


def idle_face_annotation(
    image: Image.Image,
    *,
    idle_index: int,
) -> tuple[list[int], list[list[int]], list[int]]:
    """Record explicit face, eye and rear-mask coordinates for idle frames."""

    if idle_index == 0:
        face = (21, 9, 7, 7)
        eyes = [(23, 10), (25, 10), (26, 10)]
        mask = (12, 4, 9, 12)
    else:
        body = alpha_bbox(image)
        body_height = body[3] - body[1]
        top_limit = min(image.height, body[1] + max(10, round(body_height * 0.48)))
        best: tuple[int, int, int, int] | None = None
        best_score = -1
        # A fixed 7x7 native audit window matches the accepted idle face and
        # is large enough to preserve two clear eye cues at 2.2x.
        for y in range(max(0, body[1] - 1), max(body[1], top_limit - 6)):
            for x in range(max(0, body[0]), min(image.width - 6, body[2])):
                box = (x, y, 7, 7)
                pixels = _box_pixels(image, box)
                skin_count = sum(color in SKIN_COLORS for _px, _py, color in pixels)
                # Yone faces screen-right; prefer the upper-right skin group
                # over the larger exposed torso.
                score = skin_count * 100 + x * 2 - y
                if skin_count >= 14 and score > best_score:
                    best = box
                    best_score = score
        if best is None:
            raise ValueError(f"idle[{idle_index}] has no explicit 7x7 face window")
        face = best
        eye_candidates = [
            (x, y)
            for x, y, color in _box_pixels(image, face)
            if color in EYE_COLORS
        ]
        eyes = []
        for point in eye_candidates:
            if point not in eyes:
                eyes.append(point)
        separated: tuple[tuple[int, int], tuple[int, int]] | None = None
        for first in eyes:
            for second in eyes:
                if abs(first[0] - second[0]) >= 2:
                    separated = first, second
                    break
            if separated is not None:
                break
        if separated is None:
            raise ValueError(f"idle[{idle_index}] has no two separated eye-role pixels")
        eyes = [separated[0], separated[1]]

        fx, fy, fw, fh = face
        mask_search = (
            max(0, fx - 11),
            max(0, fy - 6),
            min(image.width, fx + 2) - max(0, fx - 11),
            min(image.height, fy + fh + 5) - max(0, fy - 6),
        )
        mask_points = [
            (x, y)
            for x, y, color in _box_pixels(image, mask_search)
            if color in MASK_COLORS
        ]
        if not mask_points:
            raise ValueError(f"idle[{idle_index}] has no rear-mask pixels")
        left = min(x for x, _y in mask_points)
        top = min(y for _x, y in mask_points)
        right = max(x for x, _y in mask_points) + 1
        bottom = max(y for _x, y in mask_points) + 1
        mask = (left, top, right - left, bottom - top)

    # Fail here rather than emit plausible-looking but false coordinates.
    skin_count = sum(
        color in SKIN_COLORS for _x, _y, color in _box_pixels(image, face)
    )
    if skin_count < 14:
        raise ValueError(f"idle[{idle_index}] face has only {skin_count} skin pixels")
    if any(image.getpixel(point) not in EYE_COLORS for point in eyes):
        raise ValueError(f"idle[{idle_index}] eye metadata does not point to eye colors")
    mask_count = sum(
        color in MASK_COLORS for _x, _y, color in _box_pixels(image, mask)
    )
    if mask_count < 4:
        raise ValueError(f"idle[{idle_index}] mask has only {mask_count} pixels")
    return list(face), [list(point) for point in eyes], list(mask)


def foot_zones(image: Image.Image, action: str) -> list[list[int]]:
    if action in {"dead", "ult"}:
        return []
    bbox = alpha_bbox(image)
    left, top, right, bottom = bbox
    zone_top = max(image.height // 2, bottom - 4)
    zone = (left, zone_top, right - left, bottom - zone_top)
    if not any(color[3] for _x, _y, color in _box_pixels(image, zone)):
        raise ValueError(f"{action} generated an empty foot zone")
    return [list(zone)]


def frame_rects() -> dict[tuple[str, int], tuple[int, int, int, int]]:
    result: dict[tuple[str, int], tuple[int, int, int, int]] = {}
    for action in build_yone.NATIVE_BODY_ACTIONS:
        rects = build_yone.NATIVE_CONTRACT[action]["rects"]
        if action == "dead":
            rects = rects[:-1]
        for index, rect in enumerate(rects):
            result[(action, index)] = tuple(rect)
    if len(result) != 54:
        raise ValueError(f"V4 native contract changed: {len(result)}/54")
    return result


def build_frames() -> tuple[list[dict[str, Any]], dict[tuple[str, int], Image.Image]]:
    if not CONTACT_SOURCE.is_file() or not IDLE0_SOURCE.is_file():
        raise FileNotFoundError(
            f"missing accepted V4 source: {CONTACT_SOURCE} / {IDLE0_SOURCE}"
        )
    if sha256(CONTACT_SOURCE) != EXPECTED_CONTACT_SHA256:
        raise ValueError("accepted Yone V4 contact source hash changed")
    if sha256(IDLE0_SOURCE) != EXPECTED_IDLE0_SHA256:
        raise ValueError("accepted Yone V4 idle[0] candidate hash changed")

    contact = Image.open(CONTACT_SOURCE).convert("RGBA")
    poses = [contact_pose(contact, index) for index in range(20)]
    accepted_idle = Image.open(IDLE0_SOURCE).convert("RGBA")
    if accepted_idle.size != (43, 55):
        raise ValueError(f"accepted idle[0] size changed: {accepted_idle.size}")
    if hashlib.sha256(accepted_idle.tobytes()).hexdigest() != EXPECTED_IDLE0_PIXEL_SHA256:
        raise ValueError("accepted idle[0] pixels changed")
    if set(accepted_idle.getdata()) - {color for _role, color in PALETTE_ROWS}:
        raise ValueError("accepted idle[0] uses colors outside the V4 palette")

    rects = frame_rects()
    rows: list[dict[str, Any]] = []
    frames: dict[tuple[str, int], Image.Image] = {}
    for action in build_yone.NATIVE_BODY_ACTIONS:
        sequence = POSE_SEQUENCE[action]
        shifts = X_SHIFTS[action]
        if len(sequence) != len(shifts):
            raise ValueError(f"V4 pose/shift length mismatch for {action}")
        expected_count = sum(1 for frame_action, _index in rects if frame_action == action)
        if len(sequence) != expected_count:
            raise ValueError(
                f"V4 {action} sequence has {len(sequence)}/{expected_count} poses"
            )
        for index, (pose_index, x_shift) in enumerate(zip(sequence, shifts, strict=True)):
            x, y, width, height = rects[(action, index)]
            if (action, index) == ("idle", 0):
                image = accepted_idle.copy()
                bottom_margin = height - alpha_bbox(image)[3]
            else:
                if action == "dead":
                    bottom_margin = DEAD_BOTTOM_MARGINS[index]
                    target_height = DEAD_TARGET_HEIGHTS[index]
                    minimum_height = 1
                else:
                    bottom_margin = build_yone.BODY_BOTTOM_MARGINS[action][index]
                    target_height = max(
                        build_yone.BODY_TARGET_HEIGHTS[action][index],
                        build_yone.NATIVE_MIN_VISIBLE_HEIGHTS[action][index],
                    )
                    minimum_height = build_yone.NATIVE_MIN_VISIBLE_HEIGHTS[action][index]
                # A hard-alpha frame needs at least one transparent row above
                # the actor.  Two inherited native rows (run[2]/run[6]) asked
                # for 32 visible pixels plus a 21px bottom margin in a 53px
                # frame, which mathematically forces alpha onto y=0.  V4 keeps
                # the visible-height and zero-edge contracts, so the authored
                # source uses the nearest safe bottom margin instead.
                bottom_margin = min(
                    bottom_margin,
                    height - minimum_height - 1,
                )
                image = fit_pose(
                    poses[pose_index],
                    (width, height),
                    visible_height=target_height,
                    bottom_margin=bottom_margin,
                    x_shift=x_shift,
                )
                # Nearest reduction can discard a one-pixel extreme row even
                # when the requested raster height equals the regression floor.
                # Retry a few native sizes upward; this is still source authoring,
                # not a build/atlas transform.
                for requested_height in range(target_height + 1, target_height + 5):
                    if alpha_bbox(image)[3] - alpha_bbox(image)[1] >= minimum_height:
                        break
                    image = fit_pose(
                        poses[pose_index],
                        (width, height),
                        visible_height=requested_height,
                        bottom_margin=bottom_margin,
                        x_shift=x_shift,
                    )
            bbox = alpha_bbox(image)
            visible_height = bbox[3] - bbox[1]
            if action != "dead" and visible_height < build_yone.NATIVE_MIN_VISIBLE_HEIGHTS[action][index]:
                raise ValueError(
                    f"{action}[{index}] visible height {visible_height} below native floor "
                    f"{build_yone.NATIVE_MIN_VISIBLE_HEIGHTS[action][index]}"
                )
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

            if action == "idle":
                face, eyes, mask = idle_face_annotation(image, idle_index=index)
            else:
                face, eyes, mask = None, [], None
            relative = f"frames/{action}_{index:02d}.png"
            save_png(V4_ROOT / relative, image)
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
            }
            rows.append(row)
            frames[(action, index)] = image
    if len(rows) != 54 or len(frames) != 54:
        raise ValueError(f"generated {len(rows)}/54 V4 frames")
    return rows, frames


def build_preview(idle: Image.Image) -> Image.Image:
    rendered = idle.resize(
        (
            round(idle.width * build_yone.YONE_LIVE_CARD_SCALE),
            round(idle.height * build_yone.YONE_LIVE_CARD_SCALE),
        ),
        Image.Resampling.NEAREST,
    )
    preview = Image.new("RGBA", (141, 138), (0, 0, 0, 0))
    stage_height = max(
        round(rect[3] * build_yone.YONE_LIVE_CARD_SCALE)
        for rect in build_yone.NATIVE_CONTRACT["idle"]["rects"]
    )
    x = (preview.width - rendered.width) // 2
    y = (stage_height - rendered.height) // 2
    preview.alpha_composite(rendered, (x, y))
    bbox = alpha_bbox(preview)
    if bbox != (38, 4, 98, 90):
        raise ValueError(f"V4 real card preview bbox changed: {bbox}")
    if preview.getchannel("A").crop((98, 70, 141, 100)).getbbox() is not None:
        raise ValueError("V4 card actor overlaps the right-side UI icons")
    if 96 - bbox[3] < 6:
        raise ValueError(f"V4 card divider clearance regressed: {96 - bbox[3]}")
    return preview


def main() -> int:
    FRAME_ROOT.mkdir(parents=True, exist_ok=True)
    PREVIEW_ROOT.mkdir(parents=True, exist_ok=True)
    # Remove only this generator's exact output classes so deleted actions
    # cannot survive a rebuild as unreferenced V4 PNGs.
    for path in FRAME_ROOT.glob("*.png"):
        path.unlink()
    if BODY_PREVIEW.exists():
        BODY_PREVIEW.unlink()

    rows, frames = build_frames()
    preview = build_preview(frames[("idle", 0)])
    save_png(BODY_PREVIEW, preview)
    write_json(
        PALETTE_PATH,
        {
            "schema_version": 4,
            "route": "exact-native-v4",
            "colors": [
                {"role": role, "rgba": list(color)}
                for role, color in PALETTE_ROWS
            ],
        },
    )
    write_json(
        FRAME_MANIFEST,
        {
            "schema_version": 4,
            "route": "exact-native-v4",
            "atlas_size": list(build_yone.ACTOR_SHEET_SIZE),
            "palette_file": "palette.json",
            "body_preview": "preview/yone_v4_actor_card.png",
            "frames": rows,
        },
    )
    print(
        "generated Yone V4 exact-native source: "
        f"{len(rows)} frames, palette={len(PALETTE)} opaque colors, "
        f"preview_bbox={alpha_bbox(preview)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
