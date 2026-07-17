#!/usr/bin/env python3
"""Build Yone's deterministic visual resources for the Dual Blader slot.

The actor preserves official champion 009/Dual Blader's exact 3502x88 atlas
and animation contract.  High-footprint Q/W/R feedback is packed into
independent effect sheets so the battle actor keeps one stable body scale.

This module owns Yone visuals only.  Champion mechanics, localization,
registration, override routing, native code, audio, and manifest/version work
belong to the surrounding mod build.
"""

from __future__ import annotations

import hashlib
import json
import struct
import zlib
from collections import deque
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFilter


MOD_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = MOD_ROOT / "source"
IMAGEGEN_ROOT = SOURCE_ROOT / "imagegen"
PROCESSED_ROOT = SOURCE_ROOT / "processed"
ACTOR_DIR = MOD_ROOT / "aseprite_resources" / "champions"
EFFECT_DIR = MOD_ROOT / "aseprite_resources" / "effects"
ICON_DIR = MOD_ROOT / "icons"
SPLASH_DIR = MOD_ROOT / "BanPickIllust"
FULLBODY_DIR = MOD_ROOT / "ui" / "champion_fullbody"
PORTRAIT_DIR = MOD_ROOT / "ui" / "champion_portrait"
QA_DIR = MOD_ROOT / "qa"

CORE_SOURCE = IMAGEGEN_ROOT / "yone_core_contact.png"
RUN_SOURCE = IMAGEGEN_ROOT / "yone_run_contact.png"
WR_BODY_SOURCE = IMAGEGEN_ROOT / "yone_wr_body_contact.png"
DEFEAT_SOURCE = IMAGEGEN_ROOT / "yone_defeat_contact.png"
QW_VFX_SOURCE = IMAGEGEN_ROOT / "yone_qw_vfx_contact.png"
W_VFX_SOURCE = IMAGEGEN_ROOT / "yone_w_vfx_contact_v2.png"
Q3_VFX_SOURCE = IMAGEGEN_ROOT / "yone_q3_vfx_contact.png"
R_VFX_SOURCE = IMAGEGEN_ROOT / "yone_r_vfx_contact.png"
ICON_SOURCE = IMAGEGEN_ROOT / "yone_icons_source.png"
SPLASH_SOURCE = IMAGEGEN_ROOT / "bp_splash" / "dual_blader.png"

CORE_ALPHA = PROCESSED_ROOT / "yone_core_contact_alpha.png"
RUN_ALPHA = PROCESSED_ROOT / "yone_run_contact_alpha.png"
WR_BODY_ALPHA = PROCESSED_ROOT / "yone_wr_body_contact_alpha.png"
DEFEAT_ALPHA = PROCESSED_ROOT / "yone_defeat_contact_alpha.png"
QW_VFX_ALPHA = PROCESSED_ROOT / "yone_qw_vfx_contact_alpha.png"
W_VFX_ALPHA = PROCESSED_ROOT / "yone_w_vfx_contact_v2_alpha.png"
Q3_VFX_ALPHA = PROCESSED_ROOT / "yone_q3_vfx_contact_alpha.png"
R_VFX_ALPHA = PROCESSED_ROOT / "yone_r_vfx_contact_alpha.png"

ACTOR_SHEET_SIZE = (3502, 88)

RETIRED_YONE_GENERATED_OUTPUTS = (
    EFFECT_DIR / "yone_followup#anim.fanim",
    EFFECT_DIR / "yone_followup#sheet.png",
    EFFECT_DIR / "yone_spirit#anim.fanim",
    EFFECT_DIR / "yone_spirit#sheet.png",
    EFFECT_DIR / "yone_q3_airborne#anim.fanim",
    EFFECT_DIR / "yone_q3_airborne#sheet.png",
    IMAGEGEN_ROOT / "yone_followup_vfx_contact.png",
    PROCESSED_ROOT / "yone_followup_vfx_contact_alpha.png",
)
RETIRED_YONE_SOURCE_PATHS = (
    IMAGEGEN_ROOT / "yone_e_icon_source.png",
    IMAGEGEN_ROOT / "yone_followup_vfx_contact.png",
    PROCESSED_ROOT / "yone_followup_vfx_contact_alpha.png",
)

# Yone's accepted ImageGen body is deliberately kept at the reviewed battle
# scale.  At that scale a face is only a handful of pixels, so the smooth
# source reduction needs one final-scale pixel-art pass.  These colors are
# warm (never ivory white) and the two dark pixels form a stable eye/brow cue.
YONE_FACE_FEATURE_RGBA = (54, 24, 29, 255)
YONE_FACE_SHADOW_RGBA = (169, 96, 79, 255)
YONE_FACE_MID_RGBA = (211, 136, 108, 255)
YONE_FACE_LIGHT_RGBA = (239, 184, 150, 255)
YONE_NEAR_WHITE_MIN = 218

# Normalized against the final alpha bbox, not the native frame rectangle.
# Full-body frames keep the head in the upper/right half; compact/scoreboard
# crops remove the lower body and therefore need a slightly wider focus.
YONE_ACTOR_FACE_WINDOW = (0.18, 0.00, 0.90, 0.58)
YONE_FOCUSED_UI_FACE_WINDOW = (0.35, 0.08, 0.98, 0.70)


# Exact tag insertion order, rectangles, counts, and durations extracted from
# asset/base/aseprite_resources/champions/dual_blader#anim.  Do not reorder.
NATIVE_CONTRACT: dict[str, dict[str, Any]] = {
    "skill2": {"durations": [0.060000002], "rects": [(1970, 0, 31, 49)]},
    "hit": {"durations": [0.1], "rects": [(874, 0, 43, 53)]},
    "attack": {
        "durations": [0.060000002] * 6,
        "rects": [
            (544, 0, 45, 51), (590, 0, 49, 51), (640, 0, 59, 47),
            (700, 0, 59, 49), (760, 0, 61, 49), (822, 0, 51, 51),
        ],
    },
    "skill2_dash": {"durations": [0.060000002], "rects": [(2002, 0, 43, 43)]},
    "ult": {
        "durations": [0.05] * 13,
        "rects": [
            (2288, 0, 49, 51), (2338, 0, 59, 53), (2398, 0, 59, 57),
            (2458, 0, 61, 53), (2520, 0, 51, 51), (2572, 0, 59, 47),
            (2632, 0, 59, 49), (2692, 0, 61, 53), (2754, 0, 55, 57),
            (2810, 0, 59, 53), (2870, 0, 59, 51), (2930, 0, 61, 49),
            (2992, 0, 53, 51),
        ],
    },
    "run": {
        "durations": [0.080000006] * 8,
        "rects": [
            (220, 0, 41, 49), (262, 0, 39, 51), (302, 0, 39, 53),
            (342, 0, 39, 51), (382, 0, 41, 49), (424, 0, 39, 51),
            (464, 0, 39, 53), (504, 0, 39, 51),
        ],
    },
    "ult_hit_effect": {
        "durations": [0.05] * 11,
        "rects": [
            (3046, 0, 27, 59), (3074, 0, 45, 59), (3120, 0, 45, 57),
            (3166, 0, 41, 65), (3208, 0, 41, 65), (3250, 0, 41, 61),
            (3292, 0, 41, 59), (3334, 0, 41, 59), (3376, 0, 41, 55),
            (3418, 0, 41, 49), (3460, 0, 41, 37),
        ],
    },
    "skill2_attack": {
        "durations": [0.060000002] * 5,
        "rects": [
            (2046, 0, 31, 43), (2078, 0, 31, 45), (2110, 0, 59, 53),
            (2170, 0, 59, 55), (2230, 0, 57, 51),
        ],
    },
    "idle": {
        "durations": [0.14] * 4,
        "rects": [(44, 0, 43, 55), (88, 0, 43, 53), (132, 0, 43, 51), (176, 0, 43, 53)],
    },
    # These rectangles intentionally alias ult frames 1..11 in the official
    # atlas.  _paste_unique rejects any attempt to assign different pixels.
    "hit_effect_area": {
        "durations": [0.05] * 11,
        "rects": [
            (2338, 0, 59, 53), (2398, 0, 59, 57), (2458, 0, 61, 53),
            (2520, 0, 51, 51), (2572, 0, 59, 47), (2632, 0, 59, 49),
            (2692, 0, 61, 53), (2754, 0, 55, 57), (2810, 0, 59, 53),
            (2870, 0, 59, 51), (2930, 0, 61, 49),
        ],
    },
    "dead": {
        "durations": [0.1] * 9,
        "rects": [
            (918, 0, 43, 51), (962, 0, 41, 49), (1004, 0, 41, 45),
            (1046, 0, 41, 39), (1088, 0, 41, 39), (1130, 0, 41, 39),
            (1172, 0, 41, 39), (1214, 0, 41, 39), (1256, 0, 3, 3),
        ],
    },
    "skill_projectile": {
        "durations": [0.060000002] * 4,
        "rects": [(1690, 0, 69, 37), (1760, 0, 69, 37), (1830, 0, 69, 39), (1900, 0, 69, 37)],
    },
    "skill": {
        "durations": [0.060000002] * 7,
        "rects": [
            (1260, 0, 31, 49), (1292, 0, 31, 43), (1324, 0, 31, 55),
            (1356, 0, 71, 57), (1428, 0, 83, 67), (1512, 0, 85, 77),
            (1598, 0, 91, 87),
        ],
    },
}


BODY_TARGET_HEIGHTS: dict[str, list[int]] = {
    "idle": [39, 38, 37, 38],
    "run": [35, 34, 33, 34, 35, 34, 33, 34],
    "attack": [38, 38, 37, 38, 38, 38],
    "hit": [38],
    "skill": [38, 37, 38, 39, 39, 39, 39],
    "skill2": [38],
    "skill2_dash": [36],
    "skill2_attack": [36, 37, 38, 38, 38],
    "ult": [37, 38, 38, 38, 37, 38, 38, 38, 38, 38, 38, 38, 37],
}

BODY_BOTTOM_MARGINS: dict[str, list[int]] = {
    # Keep the feet above the battle HP/name plate.  The first version used
    # the lower edge of Dual Blader's native rectangles too literally, which
    # put Yone's longer generated legs through the plate while recalling.
    "idle": [11, 10, 9, 10],
    "run": [9, 10, 11, 10, 9, 10, 11, 10],
    "attack": [8, 8, 7, 8, 8, 8],
    "hit": [10],
    "skill": [5, 4, 7, 6, 8, 10, 8],
    "skill2": [5],
    "skill2_dash": [4],
    "skill2_attack": [4, 5, 6, 7, 5],
    "ult": [5, 6, 8, 10, 12, 11, 9, 7, 6, 7, 8, 6, 5],
}

DEAD_BOTTOM_MARGINS = [4, 4, 3, 3, 2, 2, 2, 2]


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # Write canonical LF bytes directly.  Path.write_text uses platform newline
    # translation on Windows, which made the provenance audit record CRLF
    # hashes before build_manifest normalized the same fanim files to LF.
    payload = (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    path.write_bytes(payload)


def _png_chunk(kind: bytes, data: bytes) -> bytes:
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)


def _stored_zlib(data: bytes) -> bytes:
    stream = bytearray(b"\x78\x01")
    offset = 0
    while offset < len(data):
        block = data[offset : offset + 65535]
        offset += len(block)
        stream.append(1 if offset == len(data) else 0)
        stream.extend(struct.pack("<HH", len(block), len(block) ^ 0xFFFF))
        stream.extend(block)
    a, b = 1, 0
    for start in range(0, len(data), 5552):
        for value in data[start : start + 5552]:
            a += value
            b += a
        a %= 65521
        b %= 65521
    stream.extend(struct.pack(">I", (b << 16) | a))
    return bytes(stream)


def save_png(path: Path, image: Image.Image) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rgba = image.convert("RGBA")
    raw = bytearray()
    pixels = rgba.tobytes()
    stride = rgba.width * 4
    for y in range(rgba.height):
        raw.append(0)
        raw.extend(pixels[y * stride : (y + 1) * stride])
    ihdr = struct.pack(">IIBBBBB", rgba.width, rgba.height, 8, 6, 0, 0, 0)
    path.write_bytes(
        b"\x89PNG\r\n\x1a\n"
        + _png_chunk(b"IHDR", ihdr)
        + _png_chunk(b"IDAT", _stored_zlib(bytes(raw)))
        + _png_chunk(b"IEND", b"")
    )


def save_processed_png(path: Path, image: Image.Image) -> None:
    """Store large source derivatives compressed; runtime PNGs stay canonical."""
    path.parent.mkdir(parents=True, exist_ok=True)
    image.convert("RGBA").save(path, format="PNG", optimize=False, compress_level=9)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def split_grid(image: Image.Image, columns: int, rows: int) -> list[Image.Image]:
    xs = [round(i * image.width / columns) for i in range(columns + 1)]
    ys = [round(i * image.height / rows) for i in range(rows + 1)]
    return [
        image.crop((xs[x], ys[y], xs[x + 1], ys[y + 1]))
        for y in range(rows)
        for x in range(columns)
    ]


def remove_chroma_key(image: Image.Image) -> Image.Image:
    """Remove the generated green plate with a deterministic soft matte."""
    rgb = image.convert("RGB")
    output = Image.new("RGBA", rgb.size, (0, 0, 0, 0))
    source_pixels = rgb.load()
    target_pixels = output.load()
    for y in range(rgb.height):
        for x in range(rgb.width):
            red, green, blue = source_pixels[x, y]
            dominance = green - max(red, blue)
            if green < 55 or dominance <= 14:
                alpha = 255
            elif dominance >= 88 and green >= 95:
                alpha = 0
            else:
                alpha = round(255 * (1.0 - (dominance - 14) / 74.0))
                alpha = max(0, min(255, alpha))
            if alpha:
                # Despill only the edge matte; blue/red steel energy is kept.
                green = min(green, max(red, blue) + 12)
                target_pixels[x, y] = (red, green, blue, alpha)
    return output


def process_sources() -> list[Path]:
    outputs: list[Path] = []
    for source, target in (
        (CORE_SOURCE, CORE_ALPHA), (RUN_SOURCE, RUN_ALPHA),
        (WR_BODY_SOURCE, WR_BODY_ALPHA), (DEFEAT_SOURCE, DEFEAT_ALPHA),
        (QW_VFX_SOURCE, QW_VFX_ALPHA),
        (W_VFX_SOURCE, W_VFX_ALPHA),
        (R_VFX_SOURCE, R_VFX_ALPHA),
    ):
        processed = remove_chroma_key(Image.open(source))
        if target == W_VFX_ALPHA:
            pixels = processed.load()
            border = 7
            for y in range(processed.height):
                for x in range(processed.width):
                    if (
                        x < border
                        or y < border
                        or x >= processed.width - border
                        or y >= processed.height - border
                    ):
                        red, green, blue, _ = pixels[x, y]
                        pixels[x, y] = (red, green, blue, 0)
        save_processed_png(target, processed)
        outputs.append(target)
    # The dedicated Q3 plate uses magenta so its blue-white wind cannot be
    # mistaken for the chroma background by the older green-key processor.
    q3 = Image.open(Q3_VFX_SOURCE).convert("RGBA")
    keyed = Image.new("RGBA", q3.size, (0, 0, 0, 0))
    source_pixels = q3.load()
    target_pixels = keyed.load()
    for y in range(q3.height):
        for x in range(q3.width):
            red, green, blue, alpha = source_pixels[x, y]
            magenta_plate = (
                red >= 190 and blue >= 180 and green <= 100
                and abs(red - blue) <= 55
            )
            if magenta_plate:
                continue
            distance = ((red - 255) ** 2 + green**2 + (blue - 255) ** 2) ** 0.5
            if distance <= 14:
                continue
            matte = 255 if distance >= 96 else round(255 * (distance - 14) / 82)
            target_pixels[x, y] = (red, green, blue, min(alpha, max(0, matte)))
    save_processed_png(Q3_VFX_ALPHA, keyed)
    outputs.append(Q3_VFX_ALPHA)
    return outputs


def hard_alpha(image: Image.Image, threshold: int = 64) -> Image.Image:
    rgba = image.convert("RGBA")
    alpha = rgba.getchannel("A").point(lambda value: 255 if value >= threshold else 0)
    rgba.putalpha(alpha)
    pixels = rgba.load()
    for y in range(rgba.height):
        for x in range(rgba.width):
            if pixels[x, y][3] == 0:
                pixels[x, y] = (0, 0, 0, 0)
    return rgba


def alpha_bbox(image: Image.Image) -> tuple[int, int, int, int]:
    bbox = image.getchannel("A").point(lambda value: 255 if value >= 64 else 0).getbbox()
    if bbox is None:
        raise ValueError("Yone source cell has no visible pixels")
    return bbox


def alpha_components(image: Image.Image) -> list[set[tuple[int, int]]]:
    """Return hard-alpha 8-connected components, largest first."""
    alpha = hard_alpha(image).getchannel("A")
    width, height = alpha.size
    occupied = {
        (x, y)
        for y in range(height)
        for x in range(width)
        if alpha.getpixel((x, y))
    }
    components: list[set[tuple[int, int]]] = []
    while occupied:
        seed = occupied.pop()
        component = {seed}
        queue = deque([seed])
        while queue:
            x, y = queue.popleft()
            for yy in range(max(0, y - 1), min(height, y + 2)):
                for xx in range(max(0, x - 1), min(width, x + 2)):
                    point = (xx, yy)
                    if point in occupied:
                        occupied.remove(point)
                        component.add(point)
                        queue.append(point)
        components.append(component)
    return sorted(components, key=len, reverse=True)


def keep_component_near(image: Image.Image, target: tuple[float, float]) -> Image.Image:
    """Keep the generated actor nearest a hand-audited cell-space target.

    Several poses in the 5x4 GPT contact cross a nominal grid boundary.  A
    simple largest-component rule is unsafe here: in core[7] the neighbouring
    actor fragment is larger than the intended pose.  The targets below are
    measured centroids of the accepted actor in each source cell.
    """
    rgba = hard_alpha(image)
    components = alpha_components(rgba)
    if not components:
        raise ValueError("Yone actor component selection received an empty cell")

    target_x, target_y = target
    selected = min(
        components,
        key=lambda component: (
            (sum(x for x, _ in component) / len(component) - target_x) ** 2
            + (sum(y for _, y in component) / len(component) - target_y) ** 2
        ),
    )
    pixels = rgba.load()
    for y in range(rgba.height):
        for x in range(rgba.width):
            if (x, y) not in selected:
                pixels[x, y] = (0, 0, 0, 0)
    return rgba


def remove_tiny_components(image: Image.Image, minimum: int = 10) -> Image.Image:
    """Remove detached chroma crumbs while retaining swords and energy wisps."""
    rgba = hard_alpha(image)
    alpha = rgba.getchannel("A")
    width, height = rgba.size
    occupied = {(x, y) for y in range(height) for x in range(width) if alpha.getpixel((x, y))}
    keep: set[tuple[int, int]] = set()
    while occupied:
        seed = occupied.pop()
        component = {seed}
        queue = deque([seed])
        while queue:
            x, y = queue.popleft()
            for yy in range(max(0, y - 1), min(height, y + 2)):
                for xx in range(max(0, x - 1), min(width, x + 2)):
                    point = (xx, yy)
                    if point in occupied:
                        occupied.remove(point)
                        component.add(point)
                        queue.append(point)
        if len(component) >= minimum:
            keep.update(component)
    pixels = rgba.load()
    for y in range(height):
        for x in range(width):
            if (x, y) not in keep:
                pixels[x, y] = (0, 0, 0, 0)
    return rgba


def remove_distant_fragments(image: Image.Image, minimum: int = 12, distance: int = 2) -> Image.Image:
    """Remove small isolated final-scale crumbs without deleting nearby limbs."""
    rgba = hard_alpha(image)
    alpha = rgba.getchannel("A")
    width, height = rgba.size
    occupied = {(x, y) for y in range(height) for x in range(width) if alpha.getpixel((x, y))}
    components: list[set[tuple[int, int]]] = []
    while occupied:
        seed = occupied.pop()
        component = {seed}
        queue = deque([seed])
        while queue:
            x, y = queue.popleft()
            for yy in range(max(0, y - 1), min(height, y + 2)):
                for xx in range(max(0, x - 1), min(width, x + 2)):
                    point = (xx, yy)
                    if point in occupied:
                        occupied.remove(point)
                        component.add(point)
                        queue.append(point)
        components.append(component)
    if not components:
        return rgba
    anchor = max(components, key=len)
    anchor_box = (
        min(x for x, _ in anchor) - distance,
        min(y for _, y in anchor) - distance,
        max(x for x, _ in anchor) + 1 + distance,
        max(y for _, y in anchor) + 1 + distance,
    )
    keep: set[tuple[int, int]] = set()
    for component in components:
        box = (
            min(x for x, _ in component), min(y for _, y in component),
            max(x for x, _ in component) + 1, max(y for _, y in component) + 1,
        )
        near_anchor = not (
            box[2] <= anchor_box[0] or box[0] >= anchor_box[2]
            or box[3] <= anchor_box[1] or box[1] >= anchor_box[3]
        )
        if len(component) >= minimum or near_anchor:
            keep.update(component)
    pixels = rgba.load()
    for y in range(height):
        for x in range(width):
            if (x, y) not in keep:
                pixels[x, y] = (0, 0, 0, 0)
    return rgba


def palette_finish(image: Image.Image, colors: int) -> Image.Image:
    opaque = hard_alpha(image)
    quantized = opaque.quantize(colors=colors, method=Image.Quantize.FASTOCTREE).convert("RGBA")
    quantized.putalpha(opaque.getchannel("A"))
    return hard_alpha(quantized, 128)


FaceWindow = tuple[float, float, float, float]


def _is_yone_warm_face_pixel(pixel: tuple[int, int, int, int]) -> bool:
    red, green, blue, alpha = pixel
    return (
        alpha >= 128
        and red >= 135
        and green >= 70
        and blue >= 45
        and red > green
        and green >= blue * 0.72
    )


def _is_yone_near_white(pixel: tuple[int, int, int, int]) -> bool:
    red, green, blue, alpha = pixel
    return (
        alpha >= 128
        and min(red, green, blue) >= YONE_NEAR_WHITE_MIN
        and max(red, green, blue) - min(red, green, blue) <= 45
    )


def _feature_local_rect(
    points: set[tuple[int, int]] | tuple[tuple[int, int], ...],
    bounds: tuple[int, int, int, int],
) -> tuple[int, int, int, int]:
    if not points:
        return bounds
    left, top, right, bottom = bounds
    return (
        max(left, min(x for x, _ in points) - 3),
        max(top, min(y for _, y in points) - 2),
        min(right, max(x for x, _ in points) + 5),
        min(bottom, max(y for _, y in points) + 6),
    )


def _point_components(points: set[tuple[int, int]]) -> list[set[tuple[int, int]]]:
    remaining = set(points)
    components: list[set[tuple[int, int]]] = []
    while remaining:
        seed = remaining.pop()
        component = {seed}
        queue = deque([seed])
        while queue:
            x, y = queue.popleft()
            for yy in range(y - 1, y + 2):
                for xx in range(x - 1, x + 2):
                    point = (xx, yy)
                    if point in remaining:
                        remaining.remove(point)
                        component.add(point)
                        queue.append(point)
        components.append(component)
    return components


def _component_bbox(component: set[tuple[int, int]]) -> tuple[int, int, int, int]:
    return (
        min(x for x, _ in component),
        min(y for _, y in component),
        max(x for x, _ in component) + 1,
        max(y for _, y in component) + 1,
    )


def _face_window_rect(
    image: Image.Image,
    window: FaceWindow,
) -> tuple[tuple[int, int, int, int], tuple[int, int, int, int]]:
    body = image.getchannel("A").getbbox()
    if body is None:
        raise ValueError("Yone face pass received an empty final frame")
    left, top, right, bottom = body
    width = right - left
    height = bottom - top
    x0 = left + round(width * window[0])
    y0 = top + round(height * window[1])
    x1 = left + round(width * window[2])
    y1 = top + round(height * window[3])
    return body, (x0, y0, x1, y1)


def _locate_yone_face_component(
    image: Image.Image,
    window: FaceWindow,
) -> tuple[set[tuple[int, int]], tuple[int, int, int, int]]:
    """Locate the upper warm face plane without accepting the bare chest.

    The generated model exposes a large warm torso, so a bbox-wide skin test
    incorrectly called the chest a 14x19 face.  Candidate scoring is anchored
    near the head, while the final eye/brow cue is placed in the upper part of
    a merged face/neck component when a pose joins those pixels.
    """

    body, (x0, y0, x1, y1) = _face_window_rect(image, window)
    warm = {
        (x, y)
        for y in range(y0, y1)
        for x in range(x0, x1)
        if _is_yone_warm_face_pixel(image.getpixel((x, y)))
    }
    minimum = max(4, round((body[3] - body[1]) * 0.13))
    components = [
        component
        for component in _point_components(warm)
        if len(component) >= minimum
    ]
    if not components:
        raise ValueError(
            f"Yone final frame has no warm face candidate in {(x0, y0, x1, y1)}"
        )

    target_x = body[0] + (body[2] - body[0]) * 0.58
    target_y = body[1] + (body[3] - body[1]) * 0.28

    def score(component: set[tuple[int, int]]) -> tuple[float, int]:
        left, top, right, bottom = _component_bbox(component)
        width = right - left
        height = bottom - top
        center_x = (left + right) / 2.0
        center_y = (top + bottom) / 2.0
        position = (
            ((center_y - target_y) / (body[3] - body[1])) ** 2
            + 0.35 * ((center_x - target_x) / (body[2] - body[0])) ** 2
        )
        # Position is more reliable than aspect here: the three-quarter face
        # can be wider than it is tall, while an upraised hand is a neat 3x3.
        # A strong square-shape preference previously selected that hand in
        # one R frame and painted an eye onto it.
        shape = 0.01 * abs(width / max(1, height) - 0.85)
        return position + shape, -len(component)

    selected = min(components, key=score)
    return selected, _component_bbox(selected)


def repaint_yone_face(
    image: Image.Image,
    window: FaceWindow = YONE_ACTOR_FACE_WINDOW,
) -> Image.Image:
    """Repaint only opaque final-scale facial pixels; geometry is unchanged."""

    output = image.convert("RGBA").copy()
    size_before = output.size
    alpha_before = output.getchannel("A").tobytes()
    _, face_window = _face_window_rect(output, window)
    existing_feature = {
        (x, y)
        for y in range(face_window[1], face_window[3])
        for x in range(face_window[0], face_window[2])
        if output.getpixel((x, y)) == YONE_FACE_FEATURE_RGBA
    }
    existing_adjacent = len(existing_feature) == 2 and any(
        (x + 1, y) in existing_feature or (x, y + 1) in existing_feature
        for x, y in existing_feature
    )
    if existing_adjacent:
        local = _feature_local_rect(existing_feature, face_window)
        for y in range(local[1], local[3]):
            for x in range(local[0], local[2]):
                red, green, blue, alpha = output.getpixel((x, y))
                if _is_yone_near_white((red, green, blue, alpha)):
                    output.putpixel((x, y), (*YONE_FACE_LIGHT_RGBA[:3], alpha))
        for x, y in existing_feature:
            output.putpixel((x, y), YONE_FACE_FEATURE_RGBA)
        if output.size != size_before or output.getchannel("A").tobytes() != alpha_before:
            raise ValueError("Yone final-scale face repaint changed actor alpha geometry")
        quality = yone_face_readability(output, window)
        if quality["near_white_pixels"] != 0 or quality["warm_pixels"] < 2:
            raise ValueError(f"Yone idempotent face repaint failed: {quality}")
        return output

    # Make the pass idempotent: a previously planted cue must participate in
    # face-component detection as warm shadow pixels, not accumulate another
    # pair each time deterministic assets are rebuilt.
    for y in range(face_window[1], face_window[3]):
        for x in range(face_window[0], face_window[2]):
            red, green, blue, alpha = output.getpixel((x, y))
            if (red, green, blue, alpha) == YONE_FACE_FEATURE_RGBA:
                output.putpixel((x, y), (*YONE_FACE_SHADOW_RGBA[:3], alpha))
    component, (left, top, right, bottom) = _locate_yone_face_component(
        output, window
    )
    width = right - left
    height = bottom - top
    merged_with_torso = width >= 9 or height >= 10
    face_fraction = 0.48 if merged_with_torso else 0.85
    face_bottom = min(bottom, top + max(3, round(height * face_fraction)))

    # Compress ivory highlights into three warm tones.  The accepted source
    # already owns the silhouette; this pass changes RGB only and cannot make
    # the actor larger or move its foot anchor.
    for x, y in component:
        if y >= face_bottom:
            continue
        red, green, blue, alpha = output.getpixel((x, y))
        luminance = 0.299 * red + 0.587 * green + 0.114 * blue
        existing_tone = (red, green, blue)
        if existing_tone in {
            YONE_FACE_SHADOW_RGBA[:3],
            YONE_FACE_MID_RGBA[:3],
            YONE_FACE_LIGHT_RGBA[:3],
        }:
            color = (*existing_tone, 255)
        elif luminance >= 205:
            color = YONE_FACE_LIGHT_RGBA
        elif luminance >= 150:
            color = YONE_FACE_MID_RGBA
        else:
            color = YONE_FACE_SHADOW_RGBA
        output.putpixel((x, y), (*color[:3], alpha))

    # Lanczos + unsharp can overshoot the small face to near-white even when
    # those pixels fall just outside the warm component.  Clamp only inside
    # the located face plane; hair, swords and the rest of the actor stay put.
    for y in range(top, face_bottom):
        for x in range(left, right):
            red, green, blue, alpha = output.getpixel((x, y))
            if _is_yone_near_white((red, green, blue, alpha)):
                output.putpixel((x, y), (*YONE_FACE_LIGHT_RGBA[:3], alpha))

    face_points = {(x, y) for x, y in component if y < face_bottom}
    if len(face_points) < 2:
        raise ValueError(f"Yone face plane is too small for an eye cue: {face_points}")

    # A merged face/neck component is wider; its actual eye sits in the upper
    # right.  A face-only component uses the left-middle pair visible in the
    # accepted three-quarter pose.
    target_fraction_x = 0.72 if merged_with_torso else 0.38
    target_fraction_y = 0.28 if merged_with_torso else 0.42
    target_x = left + width * target_fraction_x
    target_y = top + (face_bottom - top) * target_fraction_y
    pairs: list[
        tuple[tuple[int, int], tuple[int, int], float]
    ] = []
    for x, y in face_points:
        for adjacent in ((x + 1, y), (x, y + 1)):
            if adjacent not in face_points:
                continue
            midpoint_x = (x + adjacent[0]) / 2.0
            midpoint_y = (y + adjacent[1]) / 2.0
            vertical_penalty = 0.35 if adjacent[1] != y else 0.0
            pairs.append(
                (
                    (x, y),
                    adjacent,
                    (midpoint_x - target_x) ** 2
                    + (midpoint_y - target_y) ** 2
                    + vertical_penalty,
                )
            )
    if not pairs:
        nearest = sorted(
            face_points,
            key=lambda point: (
                (point[0] - target_x) ** 2 + (point[1] - target_y) ** 2
            ),
        )[:2]
        feature_pair = (nearest[0], nearest[1])
    else:
        first, second, _ = min(pairs, key=lambda row: row[2])
        feature_pair = (first, second)
    # Some poses leave one or two Lanczos-white pixels just beyond the warm
    # component (usually on the cheek edge).  At native battle scale those
    # isolated pixels read as a blurred white face.  Clamp the same compact
    # neighborhood used by the readability gate while still changing RGB
    # only; the actor silhouette and every native rectangle remain untouched.
    cue_left, cue_top, cue_right, cue_bottom = _feature_local_rect(
        feature_pair, face_window
    )
    for y in range(cue_top, cue_bottom):
        for x in range(cue_left, cue_right):
            red, green, blue, alpha = output.getpixel((x, y))
            if _is_yone_near_white((red, green, blue, alpha)):
                output.putpixel((x, y), (*YONE_FACE_LIGHT_RGBA[:3], alpha))

    # Draw after the white clamp so the cue remains exactly two pixels.
    for x, y in feature_pair:
        output.putpixel((x, y), YONE_FACE_FEATURE_RGBA)

    if output.size != size_before or output.getchannel("A").tobytes() != alpha_before:
        raise ValueError("Yone final-scale face repaint changed actor alpha geometry")
    quality = yone_face_readability(output, window)
    if (
        quality["dark_feature_pixels"] != 2
        or not quality["dark_feature_adjacent_pair"]
        or quality["near_white_pixels"] != 0
        or quality["warm_pixels"] < 2
    ):
        raise ValueError(f"Yone final-scale face repaint failed: {quality}")
    return output


def yone_face_readability(
    image: Image.Image,
    window: FaceWindow = YONE_ACTOR_FACE_WINDOW,
) -> dict[str, Any]:
    """Measure the actual local face cue, not upper-body skin/chest pixels."""

    body, (x0, y0, x1, y1) = _face_window_rect(image, window)
    feature = {
        (x, y)
        for y in range(y0, y1)
        for x in range(x0, x1)
        if image.getpixel((x, y)) == YONE_FACE_FEATURE_RGBA
    }
    adjacent_pair = any(
        (x + 1, y) in feature or (x, y + 1) in feature
        for x, y in feature
    )
    local = _feature_local_rect(feature, (x0, y0, x1, y1))
    warm = {
        (x, y)
        for y in range(local[1], local[3])
        for x in range(local[0], local[2])
        if _is_yone_warm_face_pixel(image.getpixel((x, y)))
    }
    warm_components = _point_components(warm)
    warm_component = max(warm_components, key=len) if warm_components else set()
    warm_box = _component_bbox(warm_component) if warm_component else None
    near_white = sum(
        1
        for y in range(local[1], local[3])
        for x in range(local[0], local[2])
        if _is_yone_near_white(image.getpixel((x, y)))
    )
    return {
        "body_bbox": list(body),
        "face_window": [x0, y0, x1, y1],
        "local_face_bbox": list(local),
        "warm_pixels": len(warm_component),
        "warm_bbox": list(warm_box) if warm_box else None,
        "dark_feature_pixels": len(feature),
        "dark_feature_adjacent_pair": adjacent_pair,
        "near_white_pixels": near_white,
    }


def fit_subject(
    source: Image.Image,
    frame_size: tuple[int, int],
    *,
    max_subject: tuple[int, int],
    anchor_bottom: int | None = None,
    colors: int = 64,
    lanczos: bool = True,
    component_minimum: int = 10,
    final_component_minimum: int = 1,
) -> Image.Image:
    source = remove_tiny_components(source, minimum=component_minimum)
    subject = source.crop(alpha_bbox(source))
    scale = min(max_subject[0] / subject.width, max_subject[1] / subject.height)
    resample = Image.Resampling.LANCZOS if lanczos else Image.Resampling.NEAREST
    subject = subject.resize(
        (max(1, round(subject.width * scale)), max(1, round(subject.height * scale))),
        resample,
    )
    if lanczos:
        subject = subject.filter(ImageFilter.UnsharpMask(radius=0.7, percent=135, threshold=2))
    subject = palette_finish(subject, colors)
    if final_component_minimum > 1:
        subject = remove_distant_fragments(subject, minimum=final_component_minimum)
    subject = subject.crop(alpha_bbox(subject))
    output = Image.new("RGBA", frame_size, (0, 0, 0, 0))
    x = (frame_size[0] - subject.width) // 2
    if anchor_bottom is None:
        y = (frame_size[1] - subject.height) // 2
    else:
        y = anchor_bottom - subject.height
    if x < 0 or y < 0 or x + subject.width > frame_size[0] or y + subject.height > frame_size[1]:
        raise ValueError(f"Yone subject {subject.size} does not fit frame {frame_size} at {(x, y)}")
    output.alpha_composite(subject, (x, y))
    return output


def fit_actor(source: Image.Image, frame_size: tuple[int, int], target_height: int, bottom_margin: int) -> Image.Image:
    frame = fit_subject(
        source,
        frame_size,
        max_subject=(max(1, frame_size[0] - 2), min(target_height, frame_size[1] - bottom_margin - 1)),
        anchor_bottom=frame_size[1] - bottom_margin,
        colors=48,
        component_minimum=24,
        final_component_minimum=3,
    )
    return repaint_yone_face(frame)


def fit_effect(source: Image.Image, frame_size: tuple[int, int], padding: int = 2) -> Image.Image:
    return fit_subject(
        source,
        frame_size,
        max_subject=(frame_size[0] - padding * 2, frame_size[1] - padding * 2),
        colors=72,
        component_minimum=1,
    )


def _paste_unique(
    sheet: Image.Image,
    placements: dict[tuple[int, int, int, int], bytes],
    rect: tuple[int, int, int, int],
    frame: Image.Image,
) -> None:
    x, y, width, height = rect
    if frame.size != (width, height):
        raise ValueError(f"Yone frame {frame.size} does not match native rect {rect}")
    pixels = frame.tobytes()
    previous = placements.get(rect)
    if previous is not None and previous != pixels:
        raise ValueError(f"Yone overlapping native rect {rect} was assigned different pixels")
    if previous is None:
        placements[rect] = pixels
        sheet.alpha_composite(frame, (x, y))


def trim_actor_width(source: Image.Image, fraction: float, center: float = 0.5) -> Image.Image:
    """Shorten generated blade reach without squeezing the actor body.

    Dual Blader's first Q/W native rectangles are only 31px wide.  Scaling a
    complete long-sword pose into those slots would shrink Yone's body by
    roughly 25 percent.  The large slash/projectile art already lives in an
    independent effect sheet, so these three windup frames may safely clip the
    distant blade tips while retaining the torso, face, hands, and hilts.
    """
    source = hard_alpha(source)
    left, top, right, bottom = alpha_bbox(source)
    target_width = max(1, round((right - left) * fraction))
    midpoint = left + round((right - left) * center)
    crop_left = max(left, min(right - target_width, midpoint - target_width // 2))
    return source.crop((crop_left, top, crop_left + target_width, bottom))


def build_actor() -> tuple[Path, Path]:
    core = split_grid(Image.open(CORE_ALPHA).convert("RGBA"), 5, 4)
    run = split_grid(Image.open(RUN_ALPHA).convert("RGBA"), 4, 2)
    wr = split_grid(Image.open(WR_BODY_ALPHA).convert("RGBA"), 5, 4)
    defeat = split_grid(Image.open(DEFEAT_ALPHA).convert("RGBA"), 4, 2)
    qw_vfx = split_grid(Image.open(QW_VFX_ALPHA).convert("RGBA"), 5, 4)
    r_vfx = split_grid(Image.open(R_VFX_ALPHA).convert("RGBA"), 5, 3)

    # The generated attack row crosses its nominal 5-column grid boundaries.
    # Keep the intended actor by its audited component centroid instead of
    # allowing adjacent half-bodies to survive the generic crumb filter.
    attack_sources = [
        keep_component_near(source, target)
        for source, target in zip(
            core[5:10],
            ((130, 149), (87, 146), (41, 142), (141, 146), (99, 153)),
            strict=True,
        )
    ]

    body_sequences: dict[str, list[Image.Image]] = {
        "idle": [core[0], trim_actor_width(core[1], 0.88), core[2], core[3]],
        "hit": [core[4]],
        "attack": [*attack_sources, core[19]],
        "run": run,
        # The first three native Q windup slots are only 31px wide.  Use
        # clean narrow guard/thrust poses instead of shrinking a long blade
        # and leaving detached tip pixels inside the actor atlas.
        "skill": [
            core[19],
            trim_actor_width(wr[0], 0.70),
            trim_actor_width(wr[3], 0.70),
            *core[13:17],
        ],
        "skill2": [trim_actor_width(wr[0], 0.70)],
        "skill2_dash": [wr[5]],
        # W is a planted dual-blade sweep.  Keep both feet around the native
        # actor anchor and avoid the retired E/run poses that visually looked
        # like the AI had teleported even though the entity never moved.
        "skill2_attack": [
            trim_actor_width(wr[9], 0.72),
            trim_actor_width(wr[8], 0.62),
            wr[17],
            wr[4],
            wr[9],
        ],
        "ult": wr[7:20],
    }

    sheet = Image.new("RGBA", ACTOR_SHEET_SIZE, (0, 0, 0, 0))
    placements: dict[tuple[int, int, int, int], bytes] = {}
    for tag in ("idle", "run", "attack", "hit", "skill", "skill2", "skill2_dash", "skill2_attack", "ult"):
        sources = body_sequences[tag]
        rects = NATIVE_CONTRACT[tag]["rects"]
        heights = BODY_TARGET_HEIGHTS[tag]
        bottoms = BODY_BOTTOM_MARGINS[tag]
        if not (len(sources) == len(rects) == len(heights) == len(bottoms)):
            raise ValueError(f"Yone {tag}: {len(sources)} source poses for {len(rects)} frames")
        for source, rect, height, bottom in zip(sources, rects, heights, bottoms, strict=True):
            _paste_unique(sheet, placements, rect, fit_actor(source, (rect[2], rect[3]), height, bottom))

    # Official hit_effect_area aliases ult[1:12]; assigning the same bytes is
    # deliberate and proves the overlap remains contract-safe.
    for source_rect, alias_rect in zip(NATIVE_CONTRACT["ult"]["rects"][1:12], NATIVE_CONTRACT["hit_effect_area"]["rects"], strict=True):
        if source_rect != alias_rect:
            raise ValueError("Dual Blader ult/hit_effect_area alias contract changed")

    # Eight generated fall/ground poses feed the eight visible dead frames;
    # the mandatory final 3x3 terminal frame remains transparent.
    for source, rect, bottom in zip(defeat, NATIVE_CONTRACT["dead"]["rects"][:-1], DEAD_BOTTOM_MARGINS, strict=True):
        target = min(37, rect[3] - bottom - 1)
        _paste_unique(sheet, placements, rect, fit_actor(source, (rect[2], rect[3]), target, bottom))

    # Compact native projectile slots remain readable, while full Q variants
    # live in the independent yone_q sheet.
    for source, rect in zip(qw_vfx[5:9], NATIVE_CONTRACT["skill_projectile"]["rects"], strict=True):
        _paste_unique(sheet, placements, rect, fit_effect(source, (rect[2], rect[3]), padding=1))

    # The native ult-hit tag receives only a small impact cue.  Runtime data
    # uses the independent yone_r effect sheet for all large R feedback.
    impact_sources = [r_vfx[index] for index in (9, 10, 11, 12, 13, 14, 13, 12, 11, 10, 9)]
    for source, rect in zip(impact_sources, NATIVE_CONTRACT["ult_hit_effect"]["rects"], strict=True):
        _paste_unique(sheet, placements, rect, fit_effect(source, (rect[2], rect[3]), padding=1))

    sheet_path = ACTOR_DIR / "yone#sheet.png"
    anim_path = ACTOR_DIR / "yone#anim.fanim"
    save_png(sheet_path, sheet)
    write_json(
        anim_path,
        {
            "anims": {
                tag: {
                    "frames": [
                        {"duration": duration, "data": {"x": x, "y": y, "w": width, "h": height}}
                        for duration, (x, y, width, height) in zip(spec["durations"], spec["rects"], strict=True)
                    ]
                }
                for tag, spec in NATIVE_CONTRACT.items()
            }
        },
    )
    return sheet_path, anim_path


EffectFrame = int | None


def build_effect_sheet(
    name: str,
    source_path: Path,
    grid: tuple[int, int],
    specs: Sequence[tuple[str, Sequence[EffectFrame], tuple[int, int], float]],
) -> list[Path]:
    cells = split_grid(Image.open(source_path).convert("RGBA"), *grid)
    if name == "yone_w":
        # Remove ImageGen's white contact-sheet separators without touching
        # the white-hot center of the actual sword crescent.
        border = 6
        for cell in cells:
            pixels = cell.load()
            for y in range(cell.height):
                for x in range(cell.width):
                    if (
                        x < border
                        or y < border
                        or x >= cell.width - border
                        or y >= cell.height - border
                    ):
                        red, green, blue, _ = pixels[x, y]
                        pixels[x, y] = (red, green, blue, 0)
    width = max(len(indexes) * size[0] for _, indexes, size, _ in specs)
    height = sum(size[1] for _, _, size, _ in specs)
    sheet = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    animations: dict[str, Any] = {}
    y = 0
    for tag, indexes, frame_size, duration in specs:
        frames: list[dict[str, Any]] = []
        for frame_index, source_index in enumerate(indexes):
            frame = (
                Image.new("RGBA", frame_size, (0, 0, 0, 0))
                if source_index is None
                else fit_effect(cells[source_index], frame_size)
            )
            x = frame_index * frame_size[0]
            sheet.alpha_composite(frame, (x, y))
            frames.append({"duration": duration, "data": {"x": x, "y": y, "w": frame_size[0], "h": frame_size[1]}})
        animations[tag] = {"frames": frames}
        y += frame_size[1]
    sheet_path = EFFECT_DIR / f"{name}#sheet.png"
    anim_path = EFFECT_DIR / f"{name}#anim.fanim"
    save_png(sheet_path, sheet)
    write_json(anim_path, {"anims": animations})
    return [sheet_path, anim_path]


def build_effects(actor_sheet_path: Path) -> list[Path]:
    outputs: list[Path] = []
    outputs += build_effect_sheet(
        "yone_attack", QW_VFX_ALPHA, (5, 4),
        [
            ("steel_hit", [0, 2, 4, None], (56, 48), 0.05),
            ("azakana_hit", [1, 3, 4, None], (56, 48), 0.05),
        ],
    )
    outputs += build_effect_sheet(
        "yone_q", QW_VFX_ALPHA, (5, 4),
        [
            ("projectile", [5, 6, 7, 8, None], (96, 40), 0.055),
            ("hit", [6, 7, 8, 9, None], (64, 48), 0.05),
            ("empowered_hit", [11, 12, 13, 14, None], (80, 64), 0.06),
        ],
    )
    outputs += build_effect_sheet(
        "yone_q3_tornado", Q3_VFX_ALPHA, (5, 2),
        [
            ("tornado", [0, 1, 2, 3, 4, None], (112, 72), 0.06),
            ("cue", [5, 6, 7, 8, 9, None], (56, 80), 0.055),
        ],
    )
    outputs += build_effect_sheet(
        "yone_q3_ready_wind", Q3_VFX_ALPHA, (5, 2),
        [
            ("pre", [5, 6], (48, 56), 0.06),
            ("loop", [6, 7, 6], (48, 56), 0.08),
            ("remove", [8, 9, None], (48, 56), 0.06),
        ],
    )
    outputs += build_effect_sheet(
        "yone_w", W_VFX_ALPHA, (5, 2),
        [
            ("crescent", [0, 1, 2, 3, 4, None], (96, 56), 0.055),
            ("impact", [2, 3, 4, None], (64, 56), 0.06),
            ("shield", [5, 6, 7, 8, 9, None], (44, 44), 0.07),
        ],
    )
    outputs += build_effect_sheet(
        "yone_r", R_VFX_ALPHA, (5, 3),
        [
            # Fate Sealed reads as one forward lane followed by converging
            # steel/Azakana cuts and an upward pull.  The previous circular
            # vortex and cracked-ground explosion were visually misleading.
            ("windup", [0, 1, 2, 3, None], (144, 48), 0.065),
            ("arrival", [5, 6, 7, 8, 9, None], (128, 64), 0.065),
            ("slash_blue", [5, 7, 9, None], (120, 56), 0.055),
            ("slash_red", [6, 8, 9, None], (120, 56), 0.055),
            ("echo", [10, 11, 12, 13, 14, None], (120, 72), 0.065),
        ],
    )
    return outputs


def cover_crop(source: Image.Image, size: tuple[int, int], *, center: tuple[float, float] = (0.5, 0.5)) -> Image.Image:
    scale = max(size[0] / source.width, size[1] / source.height)
    resized = source.resize(
        (max(1, round(source.width * scale)), max(1, round(source.height * scale))),
        Image.Resampling.LANCZOS,
    )
    left = round((resized.width - size[0]) * center[0])
    top = round((resized.height - size[1]) * center[1])
    left = max(0, min(resized.width - size[0], left))
    top = max(0, min(resized.height - size[1], top))
    return resized.crop((left, top, left + size[0], top + size[1])).convert("RGBA")


def build_icons() -> list[Path]:
    cells = split_grid(Image.open(ICON_SOURCE).convert("RGBA"), 3, 1)
    outputs: list[Path] = []
    icon_sources = [cells[0], cells[1], cells[2]]
    for filename, cell in zip(("yone_skill.png", "yone_skill2.png", "yone_ult.png"), icon_sources, strict=True):
        # The source has deliberate dark framing; a centered square crop keeps
        # each emblem intact and readable at the game's 24px presentation.
        icon = cover_crop(cell, (64, 64), center=(0.5, 0.49))
        icon = icon.quantize(colors=128, method=Image.Quantize.FASTOCTREE).convert("RGBA")
        output = ICON_DIR / filename
        save_png(output, icon)
        outputs.append(output)
    return outputs


def render_ui_subject(
    source: Image.Image,
    size: tuple[int, int],
    *,
    max_subject: tuple[int, int],
    bottom: int,
    colors: int,
    face_window: FaceWindow,
) -> Image.Image:
    source = remove_tiny_components(source)
    subject = source.crop(alpha_bbox(source))
    scale = min(max_subject[0] / subject.width, max_subject[1] / subject.height)
    subject = subject.resize(
        (max(1, round(subject.width * scale)), max(1, round(subject.height * scale))),
        Image.Resampling.LANCZOS,
    ).filter(ImageFilter.UnsharpMask(radius=0.8, percent=150, threshold=2))
    subject = palette_finish(subject, colors)
    subject = subject.crop(alpha_bbox(subject))
    output = Image.new("RGBA", size, (0, 0, 0, 0))
    x = (size[0] - subject.width) // 2
    y = bottom - subject.height
    if x < 0 or y < 0:
        raise ValueError(f"Yone UI subject {subject.size} does not fit {size}")
    output.alpha_composite(subject, (x, y))
    return repaint_yone_face(output, face_window)


def build_splash_and_portraits() -> list[Path]:
    splash = cover_crop(Image.open(SPLASH_SOURCE).convert("RGBA"), (1420, 860), center=(0.50, 0.48))
    splash_path = SPLASH_DIR / "dual_blader.png"
    save_png(splash_path, splash)

    first_idle = split_grid(Image.open(CORE_ALPHA).convert("RGBA"), 5, 4)[0]
    full_body = first_idle.crop(alpha_bbox(first_idle))

    fullbody = render_ui_subject(
        full_body,
        (64, 64),
        max_subject=(54, 56),
        bottom=60,
        colors=96,
        face_window=YONE_ACTOR_FACE_WINDOW,
    )
    fullbody_path = FULLBODY_DIR / "dual_blader.png"
    save_png(fullbody_path, fullbody)

    # Compact uses the upper 62% of the accepted high-resolution idle source,
    # preserving face, both eyes, horned mask, shoulders, and a transparent
    # border at 18/26/34/46px runtime sizes.
    width, height = full_body.size
    face_focus = full_body.crop((round(width * 0.12), 0, round(width * 0.88), round(height * 0.62)))
    compact = render_ui_subject(
        face_focus,
        (64, 64),
        max_subject=(50, 50),
        bottom=58,
        colors=112,
        face_window=YONE_FOCUSED_UI_FACE_WINDOW,
    )
    compact_path = PORTRAIT_DIR / "dual_blader_compact.png"
    save_png(compact_path, compact)

    # The native Dual Blader scoreboard surfaces are portrait rectangles
    # (observed at 18x26 and 30x38), not squares.  Build a source-direct
    # 48x64 texture whose aspect ratio sits between those two destinations so
    # the runtime can preserve the original x/y/w/h without stretching a
    # square crop or enlarging Yone's reduced battle actor.  This tighter
    # crop retains the red azakana mask, both eyes, hair and shoulders while
    # removing the swords and lower body that turn into noise below 30px.
    scoreboard_focus = full_body.crop(
        (
            round(width * 0.19),
            0,
            round(width * 0.67),
            round(height * 0.70),
        )
    )
    scoreboard = render_ui_subject(
        scoreboard_focus,
        (48, 64),
        max_subject=(40, 54),
        bottom=60,
        colors=112,
        face_window=YONE_FOCUSED_UI_FACE_WINDOW,
    )
    scoreboard_path = PORTRAIT_DIR / "dual_blader_scoreboard.png"
    save_png(scoreboard_path, scoreboard)

    # The native 90x122 grid texture reserves y=96..121 for the name band.
    # End the silhouette by y=86 to leave ten transparent pixels above it.
    grid = render_ui_subject(
        full_body,
        (90, 122),
        max_subject=(76, 82),
        bottom=86,
        colors=128,
        face_window=YONE_ACTOR_FACE_WINDOW,
    )
    grid_path = PORTRAIT_DIR / "dual_blader_grid.png"
    save_png(grid_path, grid)
    return [splash_path, fullbody_path, compact_path, scoreboard_path, grid_path]


def image_record(path: Path) -> dict[str, Any]:
    image = Image.open(path).convert("RGBA")
    alpha = image.getchannel("A")
    return {
        "path": path.relative_to(MOD_ROOT).as_posix(),
        "dimensions": list(image.size),
        "size_bytes": path.stat().st_size,
        "sha256": sha256(path),
        "alpha_bbox": list(alpha.getbbox()) if alpha.getbbox() else None,
        "alpha_extrema": list(alpha.getextrema()),
    }


RUNTIME_EFFECT_MAP = {
    "lol_yone_attack_steel_hit": ["yone_attack", "steel_hit"],
    "lol_yone_attack_azakana_hit": ["yone_attack", "azakana_hit"],
    "lol_yone_q_projectile": ["yone_q", "projectile"],
    "lol_yone_q_empowered_projectile": ["yone_q3_tornado", "tornado"],
    "lol_yone_q_hit": ["yone_q", "hit"],
    "lol_yone_q_empowered_hit": ["yone_q", "empowered_hit"],
    "lol_yone_q3_airborne_cue": ["yone_q3_tornado", "cue"],
    "lol_yone_mortal_steel_stack_2": ["yone_q3_ready_wind", "loop"],
    "lol_yone_w_crescent_cast": ["yone_w", "crescent"],
    "lol_yone_w_hit": ["yone_w", "impact"],
    "lol_yone_w_shield": ["yone_w", "shield"],
    "lol_yone_r_windup": ["yone_r", "windup"],
    "lol_yone_r_arrival": ["yone_r", "arrival"],
    "lol_yone_r_slash_blue": ["yone_r", "slash_blue"],
    "lol_yone_r_slash_red": ["yone_r", "slash_red"],
    "lol_yone_r_echo": ["yone_r", "echo"],
}


def iter_actor_body_frames(
    anims: dict[str, Any],
) -> Iterable[tuple[str, int, dict[str, Any]]]:
    """Yield all 54 visible battle-body frames, excluding the dead terminator."""

    for tag in BODY_TARGET_HEIGHTS:
        for index, entry in enumerate(anims[tag]["frames"]):
            yield tag, index, entry
    for index, entry in enumerate(anims["dead"]["frames"][:-1]):
        yield "dead", index, entry


def build_qa(
    processed: Sequence[Path],
    actor_sheet: Path,
    actor_anim: Path,
    runtime_visuals: Sequence[Path],
) -> list[Path]:
    sheet = Image.open(actor_sheet).convert("RGBA")
    anims = json.loads(actor_anim.read_text(encoding="utf-8"))["anims"]
    body_frames: dict[str, list[dict[str, Any]]] = {}
    for tag in (*BODY_TARGET_HEIGHTS, "dead"):
        rows: list[dict[str, Any]] = []
        for index, frame in enumerate(anims[tag]["frames"]):
            data = frame["data"]
            image = sheet.crop((data["x"], data["y"], data["x"] + data["w"], data["y"] + data["h"]))
            bbox = image.getchannel("A").getbbox()
            rows.append({
                "frame": index,
                "native_rect": [data[k] for k in ("x", "y", "w", "h")],
                "alpha_bbox": list(bbox) if bbox else None,
                "visible_size": [bbox[2] - bbox[0], bbox[3] - bbox[1]] if bbox else None,
                "bottom_clearance": data["h"] - bbox[3] if bbox else None,
            })
        body_frames[tag] = rows

    actor_face_readability: dict[str, dict[str, Any]] = {}
    for tag, index, entry in iter_actor_body_frames(anims):
        data = entry["data"]
        frame = sheet.crop(
            (
                data["x"],
                data["y"],
                data["x"] + data["w"],
                data["y"] + data["h"],
            )
        )
        actor_face_readability[f"{tag}[{index}]"] = yone_face_readability(frame)
    if len(actor_face_readability) != 54:
        raise ValueError(
            f"Yone face QA must cover 54 visible body frames, got {len(actor_face_readability)}"
        )

    ui_face_readability = {
        "compact": yone_face_readability(
            Image.open(PORTRAIT_DIR / "dual_blader_compact.png").convert("RGBA"),
            YONE_FOCUSED_UI_FACE_WINDOW,
        ),
        "scoreboard": yone_face_readability(
            Image.open(PORTRAIT_DIR / "dual_blader_scoreboard.png").convert("RGBA"),
            YONE_FOCUSED_UI_FACE_WINDOW,
        ),
        "grid": yone_face_readability(
            Image.open(PORTRAIT_DIR / "dual_blader_grid.png").convert("RGBA"),
            YONE_ACTOR_FACE_WINDOW,
        ),
    }

    contract_path = QA_DIR / "yone_visual_contract.json"
    write_json(
        contract_path,
        {
            "schema_version": 1,
            "champion": "Yone",
            "replacement_id": "dual_blader",
            "native_actor": {
                "sheet_size": list(ACTOR_SHEET_SIZE),
                "tag_order": list(NATIVE_CONTRACT),
                "frame_counts": {tag: len(spec["rects"]) for tag, spec in NATIVE_CONTRACT.items()},
                "durations": {tag: spec["durations"] for tag, spec in NATIVE_CONTRACT.items()},
                "rects": {tag: spec["rects"] for tag, spec in NATIVE_CONTRACT.items()},
                "overlap": "hit_effect_area aliases ult frames 1..11 exactly",
                "body_frames": body_frames,
            },
            "runtime_effect_map": RUNTIME_EFFECT_MAP,
            "runtime_body_actions": {
                "skill2": {
                    "animation_tag": "skill2_attack",
                    "frame_count": 5,
                    "qa_contact_tag": "skill2_attack",
                }
            },
            "runtime_w_resolution": {
                "action_duration_ticks": 30,
                "cooldown_ticks": 480,
                "movement": "none",
                "shape": "one stationary caster-following crescent plus one instant 36000x42000 forward hitbox",
                "damage": "50 + 90% Attack physical damage",
                "shield": "one unified settle grants a 90-tick 50 + 20% Attack shield after any enemy hit, then scales through every enemy champion hit up to the normal five-champion team limit",
            },
            "face_readability": {
                "policy": "final-scale RGB-only face repaint; actor alpha/native rectangles and body scale are unchanged",
                "feature_rgba": list(YONE_FACE_FEATURE_RGBA),
                "all_battle_body_frames": actor_face_readability,
                "ui_surfaces": ui_face_readability,
            },
            "large_vfx_policy": "Q3 tornado/knockup, compact W crescent/shield, and R feedback are isolated in dedicated sheets; no large effect replaces Yone's actor body.",
            "portrait_policy": {
                "compact": "64x64 face focus, <=50x50 alpha bbox, >=6px border",
                "scoreboard": "48x64 source-direct portrait crop for unchanged native 18x26 and 30x38 rectangles",
                "grid": "90x122 full body, alpha ends at or before y=86, name band begins y=96",
            },
        },
    )

    provenance_path = QA_DIR / "yone_imagegen_sources.json"
    write_json(
        provenance_path,
        {
            "schema_version": 1,
            "champion": "Yone",
            "generator": "built-in image_gen",
            "generated_on": "2026-07-17",
            "processing": "deterministic green-screen soft matte, despill, hard-alpha final packing, palette reduction, and an idempotent RGB-only final-scale face repaint with unchanged alpha geometry",
            "sources": [image_record(path) for path in (CORE_SOURCE, RUN_SOURCE, WR_BODY_SOURCE, DEFEAT_SOURCE, QW_VFX_SOURCE, W_VFX_SOURCE, Q3_VFX_SOURCE, R_VFX_SOURCE, ICON_SOURCE, SPLASH_SOURCE)],
            "processed": [image_record(path) for path in processed],
            "runtime": [image_record(path) if path.suffix == ".png" else {"path": path.relative_to(MOD_ROOT).as_posix(), "size_bytes": path.stat().st_size, "sha256": sha256(path)} for path in runtime_visuals],
        },
    )

    visual_md = QA_DIR / "yone_visual_qa.md"
    visual_md.write_text(
        "# Yone visual QA\n\n"
        "- [x] Same-ID visual replacement targets `dual_blader` (official project hero 009).\n"
        "- [x] Actor canvas is exactly `3502x88`; all 13 native tags, frame counts, durations, rectangles, and insertion order are preserved.\n"
        "- [x] `hit_effect_area` reuses the official `ult[1..11]` atlas rectangles without conflicting pixels.\n"
        "- [x] Idle/run/attack/Q/W/R/dead bodies retain one stable battle scale.\n"
        "- [x] All 54 visible battle-body frames plus the focused UI faces use a warm three-tone plane and exactly one two-pixel eye/brow cue; the idempotent pass changes RGB only and preserves every alpha bbox.\n"
        "- [x] Q3 uses a dedicated horizontal tornado, a vertical blue-white airborne cue, and a small ready-wind state.\n"
        "- [x] Active champion data and release resources do not reference Soul Unbound. Exactly five retired Yone E names plus two retired Shen dash names remain registered only as no-op saved-season compatibility aliases.\n"
        "- [x] W keeps at most 128 ledgers, matches caster/player/team/position to the nearest eligible `started_tick`, and does not call opaque `ModService` APIs across the base 0.5.0 SDK / base 0.5.1 host boundary.\n"
        "- [x] W keeps Yone planted, plays one full caster-following crescent, resolves one instant wide forward hitbox, and settles exactly one shield from that same deduplicated target set.\n"
        "- [x] Minions and monsters qualify for the base shield; every enemy champion hit increases its tier through the normal five-champion team limit.\n"
        "- [x] W has no dash, spirit clone, anchor, tether, forced return, recall override, or teleport path.\n"
        "- [x] Compact portrait is face-focused with transparent safety margins.\n"
        "- [x] Scoreboard portrait is an independent source-direct `48x64` crop for native `18x26` and `30x38` rectangles; runtime geometry must remain unchanged.\n"
        "- [x] BP-grid portrait is full body and ends at `y<=86`, ten pixels above the native name band.\n"
        "- [x] BP illustration is `1420x860`; the three active-slot icons are independent `64x64` assets.\n"
        "\nRuntime effect IDs and sheet tags are recorded in `qa/yone_visual_contract.json`.\n",
        encoding="utf-8",
    )

    contact = Image.new("RGBA", (1180, 520), (8, 15, 27, 255))
    draw = ImageDraw.Draw(contact)
    draw.text((18, 12), "YONE ACTOR / UI / EFFECT QA", fill=(222, 232, 242, 255))
    for column, tag in enumerate(("idle", "run", "attack", "skill", "skill2_attack", "ult")):
        frames = anims[tag]["frames"]
        frame = frames[min(1, len(frames) - 1)]["data"]
        crop = sheet.crop((frame["x"], frame["y"], frame["x"] + frame["w"], frame["y"] + frame["h"]))
        zoom = crop.resize((crop.width * 4, crop.height * 4), Image.Resampling.NEAREST)
        x = 18 + column * 180
        draw.text((x, 42), tag, fill=(196, 210, 225, 255))
        contact.alpha_composite(zoom, (x, 64))
    portraits = [
        ("compact", PORTRAIT_DIR / "dual_blader_compact.png", (18, 300)),
        ("scoreboard", PORTRAIT_DIR / "dual_blader_scoreboard.png", (160, 300)),
        ("fullbody", FULLBODY_DIR / "dual_blader.png", (278, 300)),
        ("grid", PORTRAIT_DIR / "dual_blader_grid.png", (430, 278)),
    ]
    for label, path, position in portraits:
        draw.text((position[0], position[1] - 18), label, fill=(196, 210, 225, 255))
        image = Image.open(path).convert("RGBA")
        contact.alpha_composite(image.resize((image.width * 2, image.height * 2), Image.Resampling.NEAREST), position)
    for index, (label, path) in enumerate((
        ("Q", ICON_DIR / "yone_skill.png"), ("W", ICON_DIR / "yone_skill2.png"), ("R", ICON_DIR / "yone_ult.png"),
    )):
        x = 650 + index * 160
        draw.text((x, 282), label, fill=(196, 210, 225, 255))
        icon = Image.open(path).convert("RGBA").resize((128, 128), Image.Resampling.NEAREST)
        contact.alpha_composite(icon, (x, 306))
    contact_path = QA_DIR / "yone_visual_final.png"
    save_png(contact_path, contact)
    return [contract_path, provenance_path, visual_md, contact_path]


def validate_outputs(outputs: Iterable[Path]) -> None:
    actor_sheet = ACTOR_DIR / "yone#sheet.png"
    actor_anim = ACTOR_DIR / "yone#anim.fanim"
    if Image.open(actor_sheet).size != ACTOR_SHEET_SIZE:
        raise ValueError("Yone actor canvas is not the native 3502x88 size")
    payload = json.loads(actor_anim.read_text(encoding="utf-8"))["anims"]
    if list(payload) != list(NATIVE_CONTRACT):
        raise ValueError("Yone actor tag insertion order changed native Dual Blader contract")
    for tag, spec in NATIVE_CONTRACT.items():
        frames = payload[tag]["frames"]
        if [row["duration"] for row in frames] != spec["durations"]:
            raise ValueError(f"Yone {tag} durations changed")
        rects = [tuple(row["data"][key] for key in ("x", "y", "w", "h")) for row in frames]
        if rects != spec["rects"]:
            raise ValueError(f"Yone {tag} rectangles changed")

    sheet = Image.open(actor_sheet).convert("RGBA")
    for tag, expected_bottoms in BODY_BOTTOM_MARGINS.items():
        for index, (row, expected_bottom, target_height) in enumerate(
            zip(payload[tag]["frames"], expected_bottoms, BODY_TARGET_HEIGHTS[tag], strict=True)
        ):
            data = row["data"]
            frame = sheet.crop((data["x"], data["y"], data["x"] + data["w"], data["y"] + data["h"]))
            bbox = frame.getchannel("A").getbbox()
            if bbox is None:
                raise ValueError(f"Yone {tag}[{index}] is empty")
            actual_bottom = data["h"] - bbox[3]
            if actual_bottom != expected_bottom or actual_bottom < 4:
                raise ValueError(f"Yone {tag}[{index}] bottom anchor {actual_bottom} != {expected_bottom}")
            visible_height = bbox[3] - bbox[1]
            if visible_height < target_height - 3:
                raise ValueError(
                    f"Yone {tag}[{index}] body shrank below its stable scale: "
                    f"{visible_height}px vs target {target_height}px"
                )

    # A source-grid regression previously packed a second half-body into
    # attack[1..3].  Body height/bbox checks alone cannot detect that failure,
    # so require one significant connected subject, only tiny residual edge
    # specks, and real pose variation across the six native attack frames.
    attack_hashes: set[str] = set()
    for index, row in enumerate(payload["attack"]["frames"]):
        data = row["data"]
        frame = sheet.crop(
            (
                data["x"], data["y"],
                data["x"] + data["w"], data["y"] + data["h"],
            )
        )
        component_sizes = [len(component) for component in alpha_components(frame)]
        significant = [size for size in component_sizes if size > 16]
        if len(significant) != 1:
            raise ValueError(
                f"Yone attack[{index}] must contain one actor, got components {component_sizes[:6]}"
            )
        stray_area = sum(component_sizes[1:])
        if stray_area > 24:
            raise ValueError(
                f"Yone attack[{index}] retained {stray_area}px of detached source-grid debris"
            )
        attack_hashes.add(hashlib.sha256(frame.tobytes()).hexdigest())
    if len(attack_hashes) < 5:
        raise ValueError(
            f"Yone attack lost pose variation: only {len(attack_hashes)}/6 unique frames"
        )

    core_foot_anchors = [
        bottom
        for tag in ("idle", "run", "attack", "hit")
        for bottom in BODY_BOTTOM_MARGINS[tag]
    ]
    if min(core_foot_anchors) < 7 or max(core_foot_anchors) > 11:
        raise ValueError(f"Yone core foot anchors left the battle-safe 7..11px band: {core_foot_anchors}")
    if max(BODY_BOTTOM_MARGINS["idle"]) - min(BODY_BOTTOM_MARGINS["run"]) > 2:
        raise ValueError("Yone idle/run foot anchors diverged by more than 2px")

    # The old check counted Yone's exposed chest as a face. Inspect every
    # battle body frame at final atlas scale instead: each one must retain the
    # planted two-pixel eye/brow cue and must not regress to an ivory blur.
    representative_faces = {
        ("idle", 0),
        ("run", 1),
        ("attack", 1),
        ("skill2_attack", 2),
        ("ult", 4),
    }
    face_frame_count = 0
    for tag, index, entry in iter_actor_body_frames(payload):
        face_frame_count += 1
        data = entry["data"]
        frame = sheet.crop(
            (
                data["x"],
                data["y"],
                data["x"] + data["w"],
                data["y"] + data["h"],
            )
        )
        face = yone_face_readability(frame)
        warm_bbox = face["warm_bbox"]
        is_representative = (tag, index) in representative_faces
        if (
            face["dark_feature_pixels"] != 2
            or not face["dark_feature_adjacent_pair"]
            or face["warm_pixels"] < (5 if is_representative else 2)
            or face["near_white_pixels"] != 0
            or warm_bbox is None
            or (
                is_representative
                and (
                    warm_bbox[2] - warm_bbox[0] < 2
                    or warm_bbox[3] - warm_bbox[1] < 2
                )
            )
        ):
            raise ValueError(f"Yone {tag}[{index}] face is not readable: {face}")
        if repaint_yone_face(frame).tobytes() != frame.tobytes():
            raise ValueError(f"Yone {tag}[{index}] face repaint is not idempotent")
    if face_frame_count != 54:
        raise ValueError(f"Yone face validation covered {face_frame_count}/54 frames")

    terminal_rect = NATIVE_CONTRACT["dead"]["rects"][-1]
    terminal = sheet.crop((terminal_rect[0], terminal_rect[1], terminal_rect[0] + terminal_rect[2], terminal_rect[1] + terminal_rect[3]))
    if terminal.getchannel("A").getbbox() is not None:
        raise ValueError("Yone dead terminal 3x3 frame must stay transparent")

    for effect, required_tags in {
        "yone_attack": ["steel_hit", "azakana_hit"],
        "yone_q": ["projectile", "hit", "empowered_hit"],
        "yone_q3_tornado": ["tornado", "cue"],
        "yone_q3_ready_wind": ["pre", "loop", "remove"],
        "yone_w": ["crescent", "impact", "shield"],
        "yone_r": ["windup", "arrival", "slash_blue", "slash_red", "echo"],
    }.items():
        anims = json.loads((EFFECT_DIR / f"{effect}#anim.fanim").read_text(encoding="utf-8"))["anims"]
        if list(anims) != required_tags:
            raise ValueError(f"Yone {effect} tags changed: {list(anims)}")
        effect_sheet = Image.open(EFFECT_DIR / f"{effect}#sheet.png").convert("RGBA")
        for tag in required_tags:
            final = anims[tag]["frames"][-1]["data"]
            image = effect_sheet.crop((final["x"], final["y"], final["x"] + final["w"], final["y"] + final["h"]))
            persistent_terminal = (
                effect == "yone_q3_ready_wind" and tag in {"pre", "loop"}
            )
            if not persistent_terminal and image.getchannel("A").getbbox() is not None:
                raise ValueError(f"Yone {effect}:{tag} must terminate transparent")

    compact = Image.open(PORTRAIT_DIR / "dual_blader_compact.png").convert("RGBA")
    compact_bbox = compact.getchannel("A").getbbox()
    if compact.size != (64, 64) or compact_bbox is None:
        raise ValueError("Yone compact portrait is missing")
    if compact_bbox[2] - compact_bbox[0] > 50 or compact_bbox[3] - compact_bbox[1] > 50:
        raise ValueError(f"Yone compact portrait subject exceeds 50x50: {compact_bbox}")
    if min(compact_bbox[0], compact_bbox[1], 64 - compact_bbox[2], 64 - compact_bbox[3]) < 6:
        raise ValueError(f"Yone compact portrait lacks 6px transparent margin: {compact_bbox}")

    scoreboard = Image.open(PORTRAIT_DIR / "dual_blader_scoreboard.png").convert("RGBA")
    scoreboard_bbox = scoreboard.getchannel("A").getbbox()
    if scoreboard.size != (48, 64) or scoreboard_bbox is None:
        raise ValueError("Yone scoreboard portrait is missing")
    scoreboard_width = scoreboard_bbox[2] - scoreboard_bbox[0]
    scoreboard_height = scoreboard_bbox[3] - scoreboard_bbox[1]
    if not (36 <= scoreboard_width <= 40 and 50 <= scoreboard_height <= 54):
        raise ValueError(
            f"Yone scoreboard portrait subject is not portrait-safe: {scoreboard_bbox}"
        )
    if min(
        scoreboard_bbox[0],
        scoreboard_bbox[1],
        48 - scoreboard_bbox[2],
        64 - scoreboard_bbox[3],
    ) < 4:
        raise ValueError(
            f"Yone scoreboard portrait lacks 4px transparent margin: {scoreboard_bbox}"
        )

    grid = Image.open(PORTRAIT_DIR / "dual_blader_grid.png").convert("RGBA")
    grid_bbox = grid.getchannel("A").getbbox()
    if grid.size != (90, 122) or grid_bbox is None or grid_bbox[3] > 86:
        raise ValueError(f"Yone BP-grid portrait overlaps name band: {grid_bbox}")
    for label, image, window, minimum_warm in (
        ("compact", compact, YONE_FOCUSED_UI_FACE_WINDOW, 10),
        ("scoreboard", scoreboard, YONE_FOCUSED_UI_FACE_WINDOW, 8),
        ("grid", grid, YONE_ACTOR_FACE_WINDOW, 16),
    ):
        face = yone_face_readability(image, window)
        if (
            face["dark_feature_pixels"] < 2
            or not face["dark_feature_adjacent_pair"]
            or face["warm_pixels"] < minimum_warm
            or face["near_white_pixels"] != 0
        ):
            raise ValueError(f"Yone {label} portrait face is not readable: {face}")
    if Image.open(FULLBODY_DIR / "dual_blader.png").size != (64, 64):
        raise ValueError("Yone encyclopedia portrait is not 64x64")
    if Image.open(SPLASH_DIR / "dual_blader.png").size != (1420, 860):
        raise ValueError("Yone BP splash is not 1420x860")
    for icon in ("yone_skill.png", "yone_skill2.png", "yone_ult.png"):
        if Image.open(ICON_DIR / icon).size != (64, 64):
            raise ValueError(f"Yone icon {icon} is not 64x64")
    for processed in (
        CORE_ALPHA, RUN_ALPHA, WR_BODY_ALPHA, DEFEAT_ALPHA,
        QW_VFX_ALPHA, W_VFX_ALPHA, Q3_VFX_ALPHA, R_VFX_ALPHA,
    ):
        alpha = Image.open(processed).convert("RGBA").getchannel("A")
        corners = [alpha.getpixel((0, 0)), alpha.getpixel((alpha.width - 1, 0)), alpha.getpixel((0, alpha.height - 1)), alpha.getpixel((alpha.width - 1, alpha.height - 1))]
        if any(corners):
            raise ValueError(f"Yone processed chroma plate has opaque corner pixels: {processed.name} {corners}")
    missing = [path for path in outputs if not path.is_file()]
    if missing:
        raise FileNotFoundError("Missing Yone outputs:\n" + "\n".join(str(path) for path in missing))


def build_all() -> list[Path]:
    # The release manifest scans the physical mod tree. Remove the exact known
    # retired generated outputs before rebuilding so an old mixed Q/E/R install
    # cannot silently republish Soul Unbound or the superseded Q3 cue sheet.
    for path in RETIRED_YONE_GENERATED_OUTPUTS:
        path.unlink(missing_ok=True)
    stale_sources = [path for path in RETIRED_YONE_SOURCE_PATHS if path.exists()]
    if stale_sources:
        raise ValueError(
            "Retired Yone E sources must be removed:\n"
            + "\n".join(str(path) for path in stale_sources)
        )
    required = [
        CORE_SOURCE, RUN_SOURCE, WR_BODY_SOURCE, DEFEAT_SOURCE,
        QW_VFX_SOURCE, W_VFX_SOURCE, Q3_VFX_SOURCE, R_VFX_SOURCE,
        ICON_SOURCE, SPLASH_SOURCE,
    ]
    missing = [path for path in required if not path.is_file()]
    if missing:
        raise FileNotFoundError("Missing Yone image-gen sources:\n" + "\n".join(str(path) for path in missing))
    processed = process_sources()
    actor_sheet, actor_anim = build_actor()
    effects = build_effects(actor_sheet)
    icons = build_icons()
    portraits = build_splash_and_portraits()
    runtime = [actor_sheet, actor_anim, *effects, *icons, *portraits]
    qa = build_qa(processed, actor_sheet, actor_anim, runtime)
    outputs = [*processed, *runtime, *qa]
    validate_outputs(outputs)
    return outputs


def main() -> int:
    outputs = build_all()
    for path in outputs:
        print(path.relative_to(MOD_ROOT).as_posix())
    print(f"validated {len(outputs)} Yone visual outputs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
