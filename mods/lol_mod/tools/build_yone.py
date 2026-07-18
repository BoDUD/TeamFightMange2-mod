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
import math
import struct
import zlib
from collections import deque
from collections.abc import Iterable, Sequence
from itertools import combinations
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
NATIVE_BODY_MASTER = PROCESSED_ROOT / "yone_native_body_master.png"

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

YONE_LIVE_CARD_SCALE = 2.2
YONE_LIVE_CARD_DIVIDER_TOP = 99
YONE_LIVE_CARD_AUDITED_CENTER_Y = -16
YONE_LIVE_CARD_MIN_DIVIDER_CLEARANCE = 10
YONE_NEAR_WHITE_MIN = 218

# Normalized against the final alpha bbox, not the native frame rectangle.
# Full-body frames keep the head in the upper/right half; compact/scoreboard
# crops remove the lower body and therefore need a slightly wider focus.
YONE_ACTOR_FACE_WINDOW = (0.18, 0.00, 0.98, 0.58)
YONE_FOCUSED_UI_FACE_WINDOW = (0.35, 0.08, 0.98, 0.70)
YONE_UI_FACE_WINDOWS = {
    "fullbody": YONE_ACTOR_FACE_WINDOW,
    "compact": YONE_FOCUSED_UI_FACE_WINDOW,
    "scoreboard": YONE_FOCUSED_UI_FACE_WINDOW,
    "grid": YONE_ACTOR_FACE_WINDOW,
}
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
    # Match the official Dual Blader's visible core footprint. This restores
    # the same terrain/name-plate clearance used by Lucian and Orianna instead
    # of lowering Yone's longer generated legs into the foreground mask.
    "idle": [38, 37, 36, 37],
    "run": [35, 32, 31, 32, 35, 33, 31, 33],
    "attack": [36, 36, 34, 35, 35, 36],
    "hit": [37],
    "skill": [38, 37, 38, 39, 39, 39, 39],
    "skill2": [38],
    "skill2_dash": [36],
    "skill2_attack": [36, 37, 38, 38, 38],
    "ult": [37, 38, 38, 38, 37, 38, 38, 38, 38, 38, 38, 38, 37],
}

# Minimum visible heights after the reviewed whole-sheet native raster.  These
# are regression floors, not resize targets: fast run/W/R poses are naturally
# shorter than upright idle and must never be stretched independently.
NATIVE_MIN_VISIBLE_HEIGHTS: dict[str, list[int]] = {
    "idle": [36, 36, 36, 36],
    "run": [31, 32, 32, 33, 32, 32, 32, 33],
    "attack": [35, 33, 33, 31, 33, 34],
    "hit": [34],
    "skill": [35, 33, 34, 33, 33, 31, 33],
    "skill2": [35],
    "skill2_dash": [31],
    "skill2_attack": [32, 34, 33, 32, 32],
    "ult": [34, 25, 24, 31, 29, 24, 26, 25, 31, 22, 25, 33, 33],
}

BODY_BOTTOM_MARGINS: dict[str, list[int]] = {
    # Bundle-derived official Dual Blader baselines for the common movement
    # states. These are the frames used by battle, cards and face crops.
    "idle": [16, 15, 14, 15],
    "run": [13, 18, 21, 18, 13, 17, 21, 17],
    "attack": [14, 14, 12, 13, 13, 14],
    "hit": [15],
    "skill": [5, 4, 7, 6, 8, 10, 8],
    "skill2": [5],
    "skill2_dash": [4],
    # The W body is centred in every differently-sized native frame. This is
    # the exact bottom clearance produced by y=(frame_h-subject_h)//2 for the
    # locked 22x38 body and therefore keeps both x and y pivots invariant.
    "skill2_attack": [3, 4, 8, 9, 7],
    "ult": [5, 6, 8, 10, 12, 11, 9, 7, 6, 7, 8, 6, 5],
}

DEAD_BOTTOM_MARGINS = [4, 4, 3, 3, 2, 2, 2, 2]

# The four accepted high-detail ImageGen body plates are rasterized exactly
# once as complete sheets, so every cell on a plate shares one sampling phase.
# These logical sizes are near-isotropic matches for each source plate and put
# an upright adult Yone at the official actor's 34-37px visible height. Actor
# packing below only translates/crops these final 1x pixels; it never resizes
# an individual pose.
NATIVE_BODY_LOGICAL_SHEETS: dict[str, dict[str, Any]] = {
    "core": {"path": CORE_ALPHA, "grid": (5, 4), "size": (275, 176)},
    "run": {"path": RUN_ALPHA, "grid": (4, 2), "size": (168, 108)},
    "wr": {"path": WR_BODY_ALPHA, "grid": (5, 4), "size": (400, 228)},
    "defeat": {"path": DEFEAT_ALPHA, "grid": (4, 2), "size": (216, 124)},
}

# Every visible actor frame has one explicit native-cell owner.  In
# particular W now uses the five ImageGen WR sweep cells instead of drawing a
# synthetic forearm/blade over a repeated guard pose.  These mappings preserve
# the official action names, frame counts, timing, rectangles and foot anchors.
NATIVE_BODY_FRAME_SOURCES: dict[str, list[tuple[str, int]]] = {
    "idle": [("core", index) for index in range(4)],
    # Rotate the authored loop without reordering it so its shortest passing
    # phases align with the official run rectangles' two shortest body slots.
    "run": [("run", (index + 3) % 8) for index in range(8)],
    "attack": [
        ("core", 5), ("core", 6), ("core", 7),
        ("core", 8), ("core", 11), ("core", 14),
    ],
    "hit": [("core", 4)],
    "skill": [
        ("core", 5), ("wr", 2), ("wr", 5),
        ("core", 6), ("core", 7), ("core", 8), ("core", 11),
    ],
    "skill2": [("core", 5)],
    "skill2_dash": [("core", 16)],
    "skill2_attack": [("wr", index) for index in range(5)],
    "ult": [
        ("wr", 5), ("wr", 6), ("wr", 7), ("wr", 8), ("wr", 10),
        ("wr", 9), ("wr", 11), ("wr", 12), ("wr", 13),
        ("wr", 14), ("wr", 15), ("wr", 17), ("wr", 18),
    ],
    "dead": [("defeat", index) for index in range(8)],
}

# A whole-sheet conversion may differ only by sub-half-percent integer
# rounding between axes.  Anything larger changes the authored proportions
# and must be fixed at the source/logical-sheet contract, never hidden by a
# permissive resize.
NATIVE_RESIZE_MAX_RELATIVE_DELTA = 0.005

# Horizontal clipping is denied by default.  A reviewed pose may opt in one
# side at a time with both a finite pixel budget and a finite ratio budget:
#
#   ("skill", 0): {
#       "right": {
#           "max_lost_opaque_pixels": 6,
#           "max_lost_opaque_ratio": 0.02,
#       },
#   }
#
# Keep this empty until an accepted final-scale source proves that a specific
# native rectangle intentionally trims weapon reach.  In particular, do not
# derive allowances from rejected ImageGen plates.
NATIVE_HORIZONTAL_CLIP_LIMITS: dict[
    tuple[str, int], dict[str, dict[str, int | float]]
] = {
    # Exact, source-audited loss budgets. Every listed pixel is a distant
    # sword/hair extremity outside an inherited narrow native rectangle; body,
    # face, feet and all vertical pixels remain intact.
    ("idle", 0): {
        "left": {"max_lost_opaque_pixels": 1, "max_lost_opaque_ratio": 0.002},
    },
    ("skill", 1): {
        "left": {"max_lost_opaque_pixels": 1, "max_lost_opaque_ratio": 0.0024},
        "right": {"max_lost_opaque_pixels": 1, "max_lost_opaque_ratio": 0.0024},
    },
    ("skill", 2): {
        "left": {"max_lost_opaque_pixels": 1, "max_lost_opaque_ratio": 0.0024},
    },
    ("skill2_attack", 0): {
        "left": {"max_lost_opaque_pixels": 5, "max_lost_opaque_ratio": 0.0111},
        "right": {"max_lost_opaque_pixels": 5, "max_lost_opaque_ratio": 0.0111},
    },
    ("skill2_attack", 1): {
        "left": {"max_lost_opaque_pixels": 11, "max_lost_opaque_ratio": 0.0237},
        "right": {"max_lost_opaque_pixels": 10, "max_lost_opaque_ratio": 0.0216},
    },
    ("skill2_attack", 3): {
        "left": {"max_lost_opaque_pixels": 2, "max_lost_opaque_ratio": 0.0041},
        "right": {"max_lost_opaque_pixels": 1, "max_lost_opaque_ratio": 0.0021},
    },
    ("ult", 9): {
        "left": {"max_lost_opaque_pixels": 5, "max_lost_opaque_ratio": 0.0114},
        "right": {"max_lost_opaque_pixels": 4, "max_lost_opaque_ratio": 0.0091},
    },
    ("ult", 10): {
        "left": {"max_lost_opaque_pixels": 5, "max_lost_opaque_ratio": 0.0105},
        "right": {"max_lost_opaque_pixels": 4, "max_lost_opaque_ratio": 0.0084},
    },
    ("dead", 2): {
        "left": {"max_lost_opaque_pixels": 1, "max_lost_opaque_ratio": 0.003},
    },
    ("dead", 3): {
        "left": {"max_lost_opaque_pixels": 3, "max_lost_opaque_ratio": 0.0097},
        "right": {"max_lost_opaque_pixels": 2, "max_lost_opaque_ratio": 0.0065},
    },
    ("dead", 4): {
        "left": {"max_lost_opaque_pixels": 1, "max_lost_opaque_ratio": 0.0038},
    },
    ("dead", 7): {
        "left": {"max_lost_opaque_pixels": 1, "max_lost_opaque_ratio": 0.0039},
        "right": {"max_lost_opaque_pixels": 1, "max_lost_opaque_ratio": 0.0039},
    },
}


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


def _body_corner_plate(image: Image.Image) -> tuple[str, tuple[int, int, int]]:
    """Classify the generated BODY plate from its four corner pixels only."""

    rgb = image.convert("RGB")
    corners = (
        rgb.getpixel((0, 0)),
        rgb.getpixel((rgb.width - 1, 0)),
        rgb.getpixel((0, rgb.height - 1)),
        rgb.getpixel((rgb.width - 1, rgb.height - 1)),
    )
    plate = tuple(sorted(pixel[channel] for pixel in corners)[len(corners) // 2]
                  for channel in range(3))
    red, green, blue = plate
    green_dominance = green - max(red, blue)
    # min(red, blue), rather than max(red, blue), is intentional: it rejects
    # red-only/blue-only steel and sword pixels while recognizing a magenta
    # plate even when its red and blue channels are not perfectly balanced.
    magenta_dominance = min(red, blue) - green
    if green >= 60 and green_dominance >= 20:
        return "green", plate
    if min(red, blue) >= 60 and magenta_dominance >= 20:
        return "magenta", plate
    raise ValueError(
        "Yone body source corners must be a near-green or near-magenta chroma "
        f"plate, got corners={corners} median={plate}"
    )


def remove_body_chroma_key(image: Image.Image) -> Image.Image:
    """Key a BODY source's corner plate with hard alpha and soft despill.

    This route deliberately does not serve VFX: those sources retain their
    established green/Q3-magenta handling below.
    """

    rgb = image.convert("RGB")
    plate_kind, _plate = _body_corner_plate(rgb)
    output = Image.new("RGBA", rgb.size, (0, 0, 0, 0))
    source_pixels = rgb.load()
    target_pixels = output.load()
    for y in range(rgb.height):
        for x in range(rgb.width):
            red, green, blue = source_pixels[x, y]
            dominance = (
                green - max(red, blue)
                if plate_kind == "green"
                else min(red, blue) - green
            )
            if dominance <= 14:
                alpha = 255
            elif dominance >= 88:
                alpha = 0
            else:
                alpha = round(255 * (1.0 - (dominance - 14) / 74.0))
            if not alpha:
                continue
            if alpha < 255:
                if plate_kind == "green":
                    green = min(green, max(red, blue) + 12)
                else:
                    # Despill only a partially keyed magenta edge. Fully
                    # opaque red-only/blue-only weapons are never altered.
                    red = min(red, green + 20)
                    blue = min(blue, green + 20)
            target_pixels[x, y] = (red, green, blue, alpha)
    return output


def process_sources() -> list[Path]:
    outputs: list[Path] = []
    for source, target in (
        (CORE_SOURCE, CORE_ALPHA), (RUN_SOURCE, RUN_ALPHA),
        (WR_BODY_SOURCE, WR_BODY_ALPHA), (DEFEAT_SOURCE, DEFEAT_ALPHA),
    ):
        processed = remove_body_chroma_key(Image.open(source))
        save_processed_png(target, processed)
        outputs.append(target)
    # VFX routes are intentionally unchanged; Q3 keeps its dedicated magenta
    # branch below because blue-white wind is not a BODY source.
    for source, target in (
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
    # Body plates are converted into one final-scale master before actor
    # packing.  Keeping this derivative in the processed set makes the exact
    # source-of-truth auditable and prevents a future per-frame resize from
    # slipping back into build_actor().
    outputs.append(build_native_body_master())
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


def _center_crop_divisible_grid(
    image: Image.Image,
    grid: tuple[int, int],
) -> Image.Image:
    """Remove only transparent non-divisible edges; never crop source art."""

    columns, rows = grid
    width = image.width - image.width % columns
    height = image.height - image.height % rows
    if width <= 0 or height <= 0:
        raise ValueError(f"Yone native source {image.size} cannot hold grid {grid}")
    left = (image.width - width) // 2
    top = (image.height - height) // 2

    # Generated plates are often one or two pixels off the requested grid.
    # Those pixels may be discarded only when they are truly background.  A
    # visible sword/hair pixel on an edge means the source framing is invalid;
    # silently trimming it here would make later per-frame loss accounting lie.
    alpha = image.convert("RGBA").getchannel("A")
    strip_boxes = {
        "left": (0, 0, left, image.height),
        "right": (left + width, 0, image.width, image.height),
        "top": (left, 0, left + width, top),
        "bottom": (left, top + height, left + width, image.height),
    }
    lost_by_side = {
        side: sum(alpha.crop(box).histogram()[64:])
        for side, box in strip_boxes.items()
        if box[2] > box[0] and box[3] > box[1]
    }
    lost_by_side = {side: count for side, count in lost_by_side.items() if count}
    if lost_by_side:
        raise ValueError(
            "Yone native grid normalization would crop alpha>=64 pixels: "
            f"source={image.size}, grid={grid}, lost={lost_by_side}"
        )
    return image.crop((left, top, left + width, top + height))


def _whole_sheet_native_raster(
    name: str,
    source: Image.Image,
    grid: tuple[int, int],
    logical_size: tuple[int, int],
) -> tuple[Image.Image, dict[str, Any]]:
    """Rasterize one full plate and return its audited scale contract."""

    if logical_size[0] % grid[0] or logical_size[1] % grid[1]:
        raise ValueError(
            f"Yone {name} logical sheet {logical_size} is not divisible by {grid}"
        )
    source_size = source.size
    cropped = _center_crop_divisible_grid(source, grid)
    scale_x = logical_size[0] / cropped.width
    scale_y = logical_size[1] / cropped.height
    scale_delta = abs(scale_x - scale_y) / max(scale_x, scale_y)
    if not (
        math.isfinite(scale_x)
        and math.isfinite(scale_y)
        and math.isfinite(scale_delta)
    ):
        raise ValueError(
            f"Yone {name} whole-sheet resize produced a non-finite scale"
        )
    if scale_delta >= NATIVE_RESIZE_MAX_RELATIVE_DELTA:
        raise ValueError(
            f"Yone {name} whole-sheet resize is not near-isotropic: "
            f"source={cropped.size}, logical={logical_size}, "
            f"scale_x={scale_x:.12f}, scale_y={scale_y:.12f}, "
            f"relative_delta={scale_delta:.6%} (must be <"
            f" {NATIVE_RESIZE_MAX_RELATIVE_DELTA:.3%})"
        )

    # This is the one and only spatial conversion for battle bodies.  It
    # occurs across the complete plate, not per bbox/frame, so every hard
    # source block lands on a consistent native-pixel phase.
    logical = cropped.resize(logical_size, Image.Resampling.NEAREST)
    logical = palette_finish(hard_alpha(logical, 96), 40)
    crop_left = (source_size[0] - cropped.width) // 2
    crop_top = (source_size[1] - cropped.height) // 2
    contract = {
        "source_size": list(source_size),
        "cropped_size": list(cropped.size),
        "crop_margins": {
            "left": crop_left,
            "top": crop_top,
            "right": source_size[0] - cropped.width - crop_left,
            "bottom": source_size[1] - cropped.height - crop_top,
        },
        "crop_lost_opaque_pixels": 0,
        "grid": list(grid),
        "logical_size": list(logical_size),
        "scale_x": round(scale_x, 12),
        "scale_y": round(scale_y, 12),
        "scale_relative_delta": round(scale_delta, 12),
        "scale_relative_delta_limit_exclusive": NATIVE_RESIZE_MAX_RELATIVE_DELTA,
        "near_isotropic": True,
        "resampling": "one whole-sheet NEAREST conversion",
    }
    return logical, contract


def _native_body_cells() -> tuple[
    dict[str, list[Image.Image]], dict[str, dict[str, Any]]
]:
    """Convert complete ImageGen plates to final 1x cells exactly once."""

    result: dict[str, list[Image.Image]] = {}
    contracts: dict[str, dict[str, Any]] = {}
    for name, spec in NATIVE_BODY_LOGICAL_SHEETS.items():
        source = Image.open(spec["path"]).convert("RGBA")
        grid = tuple(spec["grid"])
        logical_size = tuple(spec["size"])
        logical, contract = _whole_sheet_native_raster(
            name, source, grid, logical_size
        )
        contract["source"] = spec["path"].relative_to(MOD_ROOT).as_posix()
        cells = [hard_alpha(cell, 128) for cell in split_grid(logical, *grid)]
        expected = grid[0] * grid[1]
        if len(cells) != expected:
            raise ValueError(f"Yone {name} yielded {len(cells)}/{expected} native cells")
        result[name] = cells
        contracts[name] = contract
    return result, contracts


def _opaque_pixel_count(image: Image.Image) -> int:
    return sum(image.convert("RGBA").getchannel("A").histogram()[128:])


def _resolved_horizontal_clip_limits(
    frame_key: tuple[str, int],
) -> dict[str, dict[str, int | float]]:
    configured = NATIVE_HORIZONTAL_CLIP_LIMITS.get(frame_key, {})
    unknown = set(configured) - {"left", "right"}
    if unknown:
        raise ValueError(
            f"Yone {frame_key} horizontal clip whitelist has invalid sides: "
            f"{sorted(unknown)}"
        )
    result: dict[str, dict[str, int | float]] = {}
    for side in ("left", "right"):
        raw = configured.get(side)
        if raw is None:
            result[side] = {
                "max_lost_opaque_pixels": 0,
                "max_lost_opaque_ratio": 0.0,
            }
            continue
        pixels = raw.get("max_lost_opaque_pixels")
        ratio = raw.get("max_lost_opaque_ratio")
        if (
            not isinstance(pixels, int)
            or isinstance(pixels, bool)
            or pixels < 0
            or not isinstance(ratio, (int, float))
            or isinstance(ratio, bool)
            or not math.isfinite(float(ratio))
            or not 0.0 <= float(ratio) <= 1.0
        ):
            raise ValueError(
                f"Yone {frame_key} {side} clip limit must contain finite, "
                f"non-negative pixel/ratio budgets: {raw}"
            )
        result[side] = {
            "max_lost_opaque_pixels": pixels,
            "max_lost_opaque_ratio": float(ratio),
        }
    return result


def _native_frame_from_cell(
    cell: Image.Image,
    frame_size: tuple[int, int],
    bottom_margin: int,
    frame_key: tuple[str, int],
) -> tuple[Image.Image, dict[str, Any]]:
    """Translate/crop final 1x pixels into a native rect without resampling."""

    source = hard_alpha(cell, 128)
    source_bbox = alpha_bbox(source)
    subject = source.crop(source_bbox)
    source_opaque_pixels = _opaque_pixel_count(subject)
    x = (frame_size[0] - subject.width) // 2
    y = frame_size[1] - bottom_margin - subject.height

    # A reviewed narrow native rectangle may intentionally clip distant weapon
    # reach, but only through the exact per-frame whitelist enforced below.
    # Body pixels that remain are byte-identical to the logical source cell;
    # no scale/filter/pixel repaint is allowed here.
    src_left = max(0, -x)
    src_top = max(0, -y)
    src_right = min(subject.width, frame_size[0] - x)
    src_bottom = min(subject.height, frame_size[1] - y)
    if src_left >= src_right or src_top >= src_bottom:
        raise ValueError(
            f"Yone {frame_key} native subject {subject.size} misses frame {frame_size}"
        )

    # Partition discarded pixels by side.  Top/bottom are always fatal because
    # they change the head/foot silhouette and anchor.  Left/right are also
    # fatal unless this exact frame key and side has an explicit finite budget.
    lost_sides = {
        "top": _opaque_pixel_count(subject.crop((0, 0, subject.width, src_top))),
        "bottom": _opaque_pixel_count(
            subject.crop((0, src_bottom, subject.width, subject.height))
        ),
        "left": _opaque_pixel_count(
            subject.crop((0, src_top, src_left, src_bottom))
        ),
        "right": _opaque_pixel_count(
            subject.crop((src_right, src_top, subject.width, src_bottom))
        ),
    }
    if lost_sides["top"] or lost_sides["bottom"]:
        raise ValueError(
            f"Yone {frame_key} native placement clips vertical opaque pixels: "
            f"{lost_sides}"
        )
    limits = _resolved_horizontal_clip_limits(frame_key)
    for side in ("left", "right"):
        lost = lost_sides[side]
        ratio = lost / source_opaque_pixels
        limit = limits[side]
        if (
            lost > int(limit["max_lost_opaque_pixels"])
            or ratio > float(limit["max_lost_opaque_ratio"])
        ):
            raise ValueError(
                f"Yone {frame_key} clips {lost} opaque pixels ({ratio:.6%}) "
                f"on {side}; explicit limit is {limit}"
            )

    visible = subject.crop((src_left, src_top, src_right, src_bottom))
    visible_opaque_pixels = _opaque_pixel_count(visible)
    lost_opaque_pixels = source_opaque_pixels - visible_opaque_pixels
    if lost_opaque_pixels != sum(lost_sides.values()):
        raise ValueError(
            f"Yone {frame_key} clip accounting mismatch: total={lost_opaque_pixels}, "
            f"sides={lost_sides}"
        )
    output = Image.new("RGBA", frame_size, (0, 0, 0, 0))
    output.alpha_composite(visible, (max(0, x), max(0, y)))
    bbox = output.getchannel("A").getbbox()
    if bbox is None:
        raise ValueError(f"Yone {frame_key} native frame is empty")
    actual_bottom = frame_size[1] - bbox[3]
    if actual_bottom != bottom_margin:
        raise ValueError(
            f"Yone {frame_key} native bottom {actual_bottom} != {bottom_margin}"
        )
    audit = {
        "source_cell_size": list(source.size),
        "source_alpha_bbox": list(source_bbox),
        "source_subject_size": list(subject.size),
        "source_opaque_pixels": source_opaque_pixels,
        "placement_origin": [x, y],
        "visible_source_bbox": [src_left, src_top, src_right, src_bottom],
        "destination_alpha_bbox": list(bbox),
        "clip_sides_lost_opaque": lost_sides,
        "lost_opaque_pixels": lost_opaque_pixels,
        "lost_opaque_ratio": round(
            lost_opaque_pixels / source_opaque_pixels, 12
        ),
        "horizontal_clip_limits": limits,
    }
    return output, audit


def _compose_native_body_master() -> tuple[
    Image.Image, dict[str, dict[str, Any]], dict[str, dict[str, Any]]
]:
    """Compose the final body master plus source/scale/clip QA contracts."""

    cells, sheet_contracts = _native_body_cells()
    mapped_frame_keys = {
        (tag, index)
        for tag, sources in NATIVE_BODY_FRAME_SOURCES.items()
        for index in range(len(sources))
    }
    unknown_clip_keys = set(NATIVE_HORIZONTAL_CLIP_LIMITS) - mapped_frame_keys
    if unknown_clip_keys:
        raise ValueError(
            "Yone horizontal clip whitelist references unmapped frames: "
            f"{sorted(unknown_clip_keys)}"
        )
    master = Image.new("RGBA", ACTOR_SHEET_SIZE, (0, 0, 0, 0))
    placements: dict[tuple[int, int, int, int], bytes] = {}
    frame_contracts: dict[str, dict[str, Any]] = {}

    for tag, sources in NATIVE_BODY_FRAME_SOURCES.items():
        if tag == "dead":
            rects = NATIVE_CONTRACT[tag]["rects"][:-1]
            bottoms = DEAD_BOTTOM_MARGINS
        else:
            rects = NATIVE_CONTRACT[tag]["rects"]
            bottoms = BODY_BOTTOM_MARGINS[tag]
        if not (len(sources) == len(rects) == len(bottoms)):
            raise ValueError(
                f"Yone {tag} native mapping has {len(sources)} cells for "
                f"{len(rects)} rects/{len(bottoms)} anchors"
            )
        for index, ((plate, cell_index), rect, bottom) in enumerate(
            zip(sources, rects, bottoms, strict=True)
        ):
            try:
                source = cells[plate][cell_index]
            except (KeyError, IndexError) as exc:
                raise ValueError(
                    f"Yone {tag}[{index}] references missing {plate}[{cell_index}]"
                ) from exc
            frame, audit = _native_frame_from_cell(
                source,
                (rect[2], rect[3]),
                bottom,
                (tag, index),
            )
            frame_name = f"{tag}[{index}]"
            if frame_name in frame_contracts:
                raise ValueError(f"Duplicate Yone native frame key: {frame_name}")
            frame_contracts[frame_name] = {
                "source_mapping": {
                    "sheet": plate,
                    "cell_index": cell_index,
                },
                "native_rect": list(rect),
                **audit,
            }
            _paste_unique(master, placements, rect, frame)

    if len(frame_contracts) != 54:
        raise ValueError(
            f"Yone native source audit covered {len(frame_contracts)}/54 body frames"
        )
    return master, sheet_contracts, frame_contracts


def build_native_body_master() -> Path:
    """Build all 54 visible bodies as final pixels on the native atlas grid."""

    master, _, _ = _compose_native_body_master()
    save_processed_png(NATIVE_BODY_MASTER, master)
    return NATIVE_BODY_MASTER


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
        raise ValueError("Yone face QA received an empty frame")
    left, top, right, bottom = body
    width = right - left
    height = bottom - top
    return body, (
        left + round(width * window[0]),
        top + round(height * window[1]),
        left + round(width * window[2]),
        top + round(height * window[3]),
    )


def _locate_yone_face_component(
    image: Image.Image,
    window: FaceWindow,
) -> tuple[set[tuple[int, int]], tuple[int, int, int, int]]:
    """Find an upper-body warm-skin component; white alone is never a face."""

    body, (x0, y0, x1, y1) = _face_window_rect(image, window)
    warm_skin = {
        (x, y)
        for y in range(y0, y1)
        for x in range(x0, x1)
        if _is_yone_warm_face_pixel(image.getpixel((x, y)))
    }
    minimum = max(4, round((body[3] - body[1]) * 0.13))
    components = [
        component for component in _point_components(warm_skin) if len(component) >= minimum
    ]
    if not components:
        raise ValueError(
            f"Yone frame has no warm-skin face candidate in {(x0, y0, x1, y1)}"
        )

    target_x = body[0] + (body[2] - body[0]) * 0.58
    target_y = body[1] + (body[3] - body[1]) * 0.28

    def score(component: set[tuple[int, int]]) -> tuple[float, int]:
        left, top, right, bottom = _component_bbox(component)
        center_x = (left + right) / 2.0
        center_y = (top + bottom) / 2.0
        position = (
            ((center_y - target_y) / max(1, body[3] - body[1])) ** 2
            + 0.35 * ((center_x - target_x) / max(1, body[2] - body[0])) ** 2
        )
        return position, -len(component)

    selected = min(components, key=score)
    return selected, _component_bbox(selected)


def _adjacent_dark_eye_cues(
    image: Image.Image,
    warm_skin: set[tuple[int, int]],
    face_bbox: tuple[int, int, int, int] | None,
) -> set[tuple[int, int]]:
    """Return dark, non-mask pixels touching the upper warm-skin component."""

    if face_bbox is None:
        return set()
    left, top, right, bottom = face_bbox
    upper_limit = top + max(3, (bottom - top) * 2 // 3)
    cues: set[tuple[int, int]] = set()
    for skin_x, skin_y in warm_skin:
        for y in range(max(top, skin_y - 1), min(upper_limit, skin_y + 2)):
            for x in range(max(left - 1, skin_x - 1), min(right + 1, skin_x + 2)):
                if (x, y) in warm_skin:
                    continue
                red, green, blue, alpha = image.getpixel((x, y))
                luminance = 0.2126 * red + 0.7152 * green + 0.0722 * blue
                red_mask = red >= 90 and red > green * 1.55 and red > blue * 1.35
                if alpha >= 128 and luminance <= 72 and not red_mask:
                    cues.add((x, y))
    return cues


# Face QA is measurement-only. Generated source pixels are never repainted,
# retouched, or used to draw face, arm, or weapon detail in this builder.
def _minimal_yone_face_metrics(
    image: Image.Image,
    window: FaceWindow,
) -> dict[str, Any]:
    body, (x0, y0, x1, y1) = _face_window_rect(image, window)
    try:
        warm_skin, face_bbox = _locate_yone_face_component(image, window)
    except ValueError:
        warm_skin, face_bbox = set(), None
    dark_eye_cues = _adjacent_dark_eye_cues(image, warm_skin, face_bbox)
    red_mask = {
        (x, y)
        for y in range(y0, y1)
        for x in range(x0, x1)
        if (
            image.getpixel((x, y))[3] >= 128
            and image.getpixel((x, y))[0] >= 90
            and image.getpixel((x, y))[0] > image.getpixel((x, y))[1] * 1.55
            and image.getpixel((x, y))[0] > image.getpixel((x, y))[2] * 1.35
        )
    }
    luminance = [
        0.2126 * image.getpixel(point)[0]
        + 0.7152 * image.getpixel(point)[1]
        + 0.0722 * image.getpixel(point)[2]
        for point in warm_skin
    ]
    near_white = sum(
        1 for point in warm_skin if _is_yone_near_white(image.getpixel(point))
    )
    face_contrast = max(luminance) - min(luminance) if luminance else 0.0
    face_width = 0 if face_bbox is None else face_bbox[2] - face_bbox[0]
    face_height = 0 if face_bbox is None else face_bbox[3] - face_bbox[1]
    warm_skin_present = bool(warm_skin)
    adjacent_dark_eye_cue = bool(dark_eye_cues)
    readable_geometry = (
        face_width >= 2
        and face_height >= 2
        and len(warm_skin) >= 4
        and face_contrast >= 12
    )
    minimal_feature_set = (
        readable_geometry
        and warm_skin_present
        and adjacent_dark_eye_cue
        and near_white <= max(2, len(warm_skin) // 20)
    )
    return {
        "body_bbox": list(body),
        "face_window": [x0, y0, x1, y1],
        "face_skin_pixels": len(warm_skin),
        "warm_skin_pixels": len(warm_skin),
        "face_skin_bbox": list(face_bbox) if face_bbox else None,
        "warm_skin_component_present": warm_skin_present,
        "near_white_pixels": near_white,
        "face_contrast": round(face_contrast, 3),
        "adjacent_dark_eye_cue": adjacent_dark_eye_cue,
        "adjacent_dark_eye_cue_pixels": len(dark_eye_cues),
        "adjacent_dark_eye_cue_positions": [list(point) for point in sorted(dark_eye_cues)],
        "natural_dark_feature_pixels": len(dark_eye_cues),
        "natural_dark_feature_positions": [list(point) for point in sorted(dark_eye_cues)],
        "minimal_feature_set": minimal_feature_set,
        "red_mask_pixels": len(red_mask),
        "red_mask_bbox": list(_component_bbox(red_mask)) if red_mask else None,
    }


def yone_face_readability(
    image: Image.Image,
    window: FaceWindow = YONE_ACTOR_FACE_WINDOW,
) -> dict[str, Any]:
    """Measure the actual local face cue, not upper-body skin/chest pixels."""

    return _minimal_yone_face_metrics(image, window)


def _scaled_minimal_face_metrics(
    source: Image.Image,
    rendered: Image.Image,
) -> dict[str, Any]:
    """Verify that source-authored face geometry survives nearest scaling."""

    source_quality = yone_face_readability(source)
    try:
        source_face, _ = _locate_yone_face_component(source, YONE_ACTOR_FACE_WINDOW)
    except ValueError:
        source_face = set()
    face_mask = Image.new("L", source.size, 0)
    for point in source_face:
        face_mask.putpixel(point, 255)
    rendered_face_mask = face_mask.resize(rendered.size, Image.Resampling.NEAREST)
    rendered_face_bbox = rendered_face_mask.getbbox()
    rendered_face_pixels = sum(
        1
        for value in getattr(
            rendered_face_mask,
            "get_flattened_data",
            rendered_face_mask.getdata,
        )()
        if value
    )
    source_eye_cues = {
        tuple(point)
        for point in source_quality["adjacent_dark_eye_cue_positions"]
    }
    eye_mask = Image.new("L", source.size, 0)
    for point in source_eye_cues:
        eye_mask.putpixel(point, 255)
    rendered_eye_mask = eye_mask.resize(rendered.size, Image.Resampling.NEAREST)
    rendered_eye_pixels = sum(
        1
        for value in getattr(
            rendered_eye_mask,
            "get_flattened_data",
            rendered_eye_mask.getdata,
        )()
        if value
    )
    return {
        "source_face_skin_bbox": source_quality["face_skin_bbox"],
        "rendered_face_skin_bbox": (
            list(rendered_face_bbox) if rendered_face_bbox else None
        ),
        "rendered_face_skin_pixels": rendered_face_pixels,
        "source_warm_skin_component_present": source_quality[
            "warm_skin_component_present"
        ],
        "source_adjacent_dark_eye_cue": source_quality["adjacent_dark_eye_cue"],
        "source_adjacent_dark_eye_cue_pixels": source_quality[
            "adjacent_dark_eye_cue_pixels"
        ],
        # Project the exact source component/cue masks through the renderer's
        # NEAREST transform. Re-running a face locator after scaling can choose
        # a different nearby skin component even though every authored eye
        # pixel survived byte-for-byte.
        "rendered_warm_skin_component_present": rendered_face_pixels > 0,
        "rendered_adjacent_dark_eye_cue": rendered_eye_pixels > 0,
        "rendered_adjacent_dark_eye_cue_pixels": rendered_eye_pixels,
        "source_near_white_pixels": source_quality["near_white_pixels"],
        "source_face_contrast": source_quality["face_contrast"],
        "source_red_mask_pixels": source_quality["red_mask_pixels"],
        "source_red_mask_bbox": source_quality["red_mask_bbox"],
    }


def yone_fullbody_card_contract(fullbody: Image.Image) -> dict[str, Any]:
    """Replay the real 64x64 -> 85x93 card texture route from live captures."""

    source = fullbody.convert("RGBA")
    if source.size != (64, 64):
        raise ValueError(f"Yone fullbody source must be 64x64, got {source.size}")
    rendered = source.resize((85, 93), Image.Resampling.NEAREST)
    source_bbox = source.getchannel("A").getbbox()
    rendered_bbox = rendered.getchannel("A").getbbox()
    if source_bbox is None or rendered_bbox is None:
        raise ValueError("Yone fullbody card route is empty")

    def last_alpha_row(image: Image.Image, bbox: tuple[int, int, int, int]) -> list[int]:
        y = bbox[3] - 1
        occupied = [x for x in range(image.width) if image.getpixel((x, y))[3]]
        return [y, min(occupied), max(occupied) + 1]

    return {
        "source_size": list(source.size),
        "rendered_size": list(rendered.size),
        "resampling": "nearest",
        "source_alpha_bbox": list(source_bbox),
        "rendered_alpha_bbox": list(rendered_bbox),
        "source_bottom_margin": source.height - source_bbox[3],
        "rendered_bottom_margin": rendered.height - rendered_bbox[3],
        "source_last_alpha_row": last_alpha_row(source, source_bbox),
        "rendered_last_alpha_row": last_alpha_row(rendered, rendered_bbox),
        **_scaled_minimal_face_metrics(source, rendered),
    }


def yone_live_card_idle_metrics(
    image: Image.Image,
    *,
    stage_height: int,
    center_y: int,
    variant: str = "front",
) -> dict[str, Any]:
    """Measure one body frame at the uniform scale proven by live capture.

    The game does not stretch every idle rectangle to one fixed 86x121 box.
    It scales each native rectangle by about 2.2x and vertically centers the
    result on the tallest idle stage.  Measuring that route keeps idle[0]
    (the frame exactly matched to the rejected screenshot) in the gate instead of
    accidentally proving only idle[0].
    """

    source = image.convert("RGBA")
    rendered = source.resize(
        (
            round(source.width * YONE_LIVE_CARD_SCALE),
            round(source.height * YONE_LIVE_CARD_SCALE),
        ),
        Image.Resampling.NEAREST,
    )
    alpha_bbox = rendered.getchannel("A").getbbox()
    if alpha_bbox is None:
        raise ValueError("Yone live-card idle frame is empty")
    if rendered.height > stage_height:
        raise ValueError(
            f"Yone live-card frame height {rendered.height} exceeds stage {stage_height}"
        )
    scaled_face = _scaled_minimal_face_metrics(source, rendered)
    stage_y = (
        (stage_height - rendered.height) // 2
        + center_y
        - YONE_LIVE_CARD_AUDITED_CENTER_Y
    )
    projected_bbox = (
        alpha_bbox[0],
        alpha_bbox[1] + stage_y,
        alpha_bbox[2],
        alpha_bbox[3] + stage_y,
    )
    return {
        "source_size": list(source.size),
        "rendered_size": list(rendered.size),
        "stage_y": stage_y,
        "alpha_bbox": list(alpha_bbox),
        "projected_alpha_bbox": list(projected_bbox),
        "divider_clearance": YONE_LIVE_CARD_DIVIDER_TOP - projected_bbox[3],
        "source_bottom_clearance": source.height - source.getchannel("A").getbbox()[3],
        "rendered_bottom_clearance": rendered.height - alpha_bbox[3],
        "face_variant": variant,
        **scaled_face,
    }


def yone_live_idle_card_contract(
    sheet: Image.Image,
    anims: dict[str, Any],
    *,
    center_y: int,
) -> dict[str, Any]:
    idle_entries = anims["idle"]["frames"]
    stage_height = max(
        round(entry["data"]["h"] * YONE_LIVE_CARD_SCALE)
        for entry in idle_entries
    )
    frames: dict[str, dict[str, Any]] = {}
    for index, entry in enumerate(idle_entries):
        data = entry["data"]
        frame = sheet.crop(
            (
                data["x"],
                data["y"],
                data["x"] + data["w"],
                data["y"] + data["h"],
            )
        )
        frames[f"idle[{index}]"] = yone_live_card_idle_metrics(
            frame,
            stage_height=stage_height,
            center_y=center_y,
            variant="front",
        )
    return {
        "scale": YONE_LIVE_CARD_SCALE,
        "resampling": "nearest",
        "stage_height": stage_height,
        "audited_center_y": YONE_LIVE_CARD_AUDITED_CENTER_Y,
        "divider_top": YONE_LIVE_CARD_DIVIDER_TOP,
        "minimum_divider_clearance": YONE_LIVE_CARD_MIN_DIVIDER_CLEARANCE,
        "frames": frames,
    }


def yone_live_run_profile_contract(
    sheet: Image.Image,
    anims: dict[str, Any],
) -> dict[str, Any]:
    """Replay the live 2.2x transform for every battle run profile."""

    run_entries = anims["run"]["frames"]
    stage_height = max(
        round(entry["data"]["h"] * YONE_LIVE_CARD_SCALE)
        for entry in run_entries
    )
    frames: dict[str, dict[str, Any]] = {}
    for index, entry in enumerate(run_entries):
        data = entry["data"]
        frame = sheet.crop(
            (
                data["x"],
                data["y"],
                data["x"] + data["w"],
                data["y"] + data["h"],
            )
        )
        frames[f"run[{index}]"] = yone_live_card_idle_metrics(
            frame,
            stage_height=stage_height,
            center_y=YONE_LIVE_CARD_AUDITED_CENTER_Y,
            variant="profile",
        )
    return {
        "scale": YONE_LIVE_CARD_SCALE,
        "resampling": "nearest",
        "stage_height": stage_height,
        "frames": frames,
    }


def fit_subject(
    source: Image.Image,
    frame_size: tuple[int, int],
    *,
    max_subject: tuple[int, int],
    anchor_bottom: int | None = None,
    colors: int = 64,
    lanczos: bool = True,
    resampling: Image.Resampling | None = None,
    component_minimum: int = 10,
    final_component_minimum: int = 1,
) -> Image.Image:
    source = remove_tiny_components(source, minimum=component_minimum)
    subject = source.crop(alpha_bbox(source))
    scale = min(max_subject[0] / subject.width, max_subject[1] / subject.height)
    resample = (
        resampling
        if resampling is not None
        else (Image.Resampling.LANCZOS if lanczos else Image.Resampling.NEAREST)
    )
    subject = subject.resize(
        (max(1, round(subject.width * scale)), max(1, round(subject.height * scale))),
        resample,
    )
    if resample == Image.Resampling.LANCZOS:
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
    for previous_rect, previous_pixels in placements.items():
        previous_x, previous_y, previous_width, previous_height = previous_rect
        intersects = not (
            x + width <= previous_x
            or previous_x + previous_width <= x
            or y + height <= previous_y
            or previous_y + previous_height <= y
        )
        if not intersects:
            continue
        if rect == previous_rect:
            if pixels != previous_pixels:
                raise ValueError(
                    f"Yone exact native alias {rect} was assigned different pixels"
                )
            return
        raise ValueError(
            "Yone native rectangles partially intersect: "
            f"new={rect}, existing={previous_rect}"
        )
    placements[rect] = pixels
    sheet.alpha_composite(frame, (x, y))


def build_actor() -> tuple[Path, Path]:
    qw_vfx = split_grid(Image.open(QW_VFX_ALPHA).convert("RGBA"), 5, 4)
    r_vfx = split_grid(Image.open(R_VFX_ALPHA).convert("RGBA"), 5, 3)
    native_master = Image.open(NATIVE_BODY_MASTER).convert("RGBA")
    if native_master.size != ACTOR_SHEET_SIZE:
        raise ValueError(
            f"Yone native body master is {native_master.size}, expected {ACTOR_SHEET_SIZE}"
        )
    sheet = Image.new("RGBA", ACTOR_SHEET_SIZE, (0, 0, 0, 0))
    placements: dict[tuple[int, int, int, int], bytes] = {}

    # Copy each final native frame byte-for-byte.  Any resize or palette pass
    # in this function is a build-contract violation and is caught again by
    # the master-to-atlas identity audit.
    for tag in NATIVE_BODY_FRAME_SOURCES:
        rects = (
            NATIVE_CONTRACT[tag]["rects"][:-1]
            if tag == "dead"
            else NATIVE_CONTRACT[tag]["rects"]
        )
        for rect in rects:
            x, y, width, height = rect
            frame = native_master.crop((x, y, x + width, y + height))
            if frame.getchannel("A").getbbox() is None:
                raise ValueError(f"Yone native body master has empty {tag} rect {rect}")
            _paste_unique(sheet, placements, rect, frame)

    # Official hit_effect_area aliases ult[1:12]; assigning the same bytes is
    # deliberate and proves the overlap remains contract-safe.
    for source_rect, alias_rect in zip(NATIVE_CONTRACT["ult"]["rects"][1:12], NATIVE_CONTRACT["hit_effect_area"]["rects"], strict=True):
        if source_rect != alias_rect:
            raise ValueError("Dual Blader ult/hit_effect_area alias contract changed")

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
    return output


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
    )
    fullbody_path = FULLBODY_DIR / "dual_blader.png"
    save_png(fullbody_path, fullbody)

    # Compact uses the upper 62% of the accepted high-resolution idle source,
    # preserving the tapered face, horned mask, shoulders, and a transparent
    # border at 18/26/34/46px runtime sizes.
    width, height = full_body.size
    face_focus = full_body.crop((round(width * 0.12), 0, round(width * 0.88), round(height * 0.62)))
    compact = render_ui_subject(
        face_focus,
        (64, 64),
        max_subject=(50, 50),
        bottom=58,
        colors=112,
    )
    compact_path = PORTRAIT_DIR / "dual_blader_compact.png"
    save_png(compact_path, compact)

    # The native Dual Blader scoreboard surfaces are portrait rectangles
    # (observed at 18x26 and 30x38), not squares.  Build a source-direct
    # 48x64 texture whose aspect ratio sits between those two destinations so
    # the runtime can preserve the original x/y/w/h without stretching a
    # square crop or enlarging Yone's reduced battle actor.  This tighter
    # crop retains the red azakana mask, tapered face, hair and shoulders while
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


def native_pixel_quality(image: Image.Image) -> dict[str, Any]:
    """Measure final-scale pixel construction without enlarging the frame."""

    rgba = image.convert("RGBA")
    alpha_channel = rgba.getchannel("A")
    alpha_values = set(
        getattr(alpha_channel, "get_flattened_data", alpha_channel.getdata)()
    )
    bbox = rgba.getchannel("A").getbbox()
    if bbox is None:
        return {
            "hard_alpha": alpha_values.issubset({0, 255}),
            "alpha_values": sorted(alpha_values),
            "opaque_palette_size": 0,
            "bbox_fill_ratio": 0.0,
            "color_edge24_ratio": 0.0,
            "alpha_bbox": None,
        }
    left, top, right, bottom = bbox
    opaque_points = {
        (x, y)
        for y in range(top, bottom)
        for x in range(left, right)
        if rgba.getpixel((x, y))[3] == 255
    }
    palette = {rgba.getpixel(point)[:3] for point in opaque_points}
    comparable_edges = 0
    color_edges = 0
    for x, y in opaque_points:
        for neighbour in ((x + 1, y), (x, y + 1)):
            if neighbour not in opaque_points:
                continue
            comparable_edges += 1
            first = rgba.getpixel((x, y))
            second = rgba.getpixel(neighbour)
            if max(abs(first[channel] - second[channel]) for channel in range(3)) >= 24:
                color_edges += 1
    bbox_area = (right - left) * (bottom - top)
    return {
        "hard_alpha": alpha_values.issubset({0, 255}),
        "alpha_values": sorted(alpha_values),
        "opaque_palette_size": len(palette),
        "bbox_fill_ratio": round(len(opaque_points) / max(1, bbox_area), 4),
        "color_edge24_ratio": round(color_edges / max(1, comparable_edges), 4),
        "alpha_bbox": [left, top, right, bottom],
    }


def build_qa(
    processed: Sequence[Path],
    actor_sheet: Path,
    actor_anim: Path,
    runtime_visuals: Sequence[Path],
) -> list[Path]:
    sheet = Image.open(actor_sheet).convert("RGBA")
    native_master = Image.open(NATIVE_BODY_MASTER).convert("RGBA")
    audited_master, native_sheet_contracts, native_frame_source_contracts = (
        _compose_native_body_master()
    )
    if audited_master.tobytes() != native_master.tobytes():
        raise ValueError(
            "Yone saved native body master differs from its audited source mapping"
        )
    anims = json.loads(actor_anim.read_text(encoding="utf-8"))["anims"]
    body_frames: dict[str, list[dict[str, Any]]] = {}
    for tag in (*BODY_TARGET_HEIGHTS, "dead"):
        rows: list[dict[str, Any]] = []
        for index, frame in enumerate(anims[tag]["frames"]):
            data = frame["data"]
            image = sheet.crop((data["x"], data["y"], data["x"] + data["w"], data["y"] + data["h"]))
            bbox = image.getchannel("A").getbbox()
            pixel_quality = native_pixel_quality(image)
            rows.append({
                "frame": index,
                "native_rect": [data[k] for k in ("x", "y", "w", "h")],
                "alpha_bbox": list(bbox) if bbox else None,
                "visible_size": [bbox[2] - bbox[0], bbox[3] - bbox[1]] if bbox else None,
                "bottom_clearance": data["h"] - bbox[3] if bbox else None,
                "hard_alpha": pixel_quality["hard_alpha"],
                "opaque_palette_size": pixel_quality["opaque_palette_size"],
                "bbox_fill_ratio": pixel_quality["bbox_fill_ratio"],
                "color_edge24_ratio": pixel_quality["color_edge24_ratio"],
            })
        body_frames[tag] = rows

    actor_face_readability: dict[str, dict[str, Any]] = {}
    native_body_identity: dict[str, dict[str, Any]] = {}
    native_body_pixel_quality: dict[str, dict[str, Any]] = {}
    for tag, index, entry in iter_actor_body_frames(anims):
        data = entry["data"]
        rect = (
            data["x"], data["y"],
            data["x"] + data["w"], data["y"] + data["h"],
        )
        frame = sheet.crop(rect)
        master_frame = native_master.crop(rect)
        frame_name = f"{tag}[{index}]"
        identical = frame.tobytes() == master_frame.tobytes()
        native_body_identity[frame_name] = {
            "master_to_atlas_byte_identical": identical,
            "sha256": hashlib.sha256(frame.tobytes()).hexdigest(),
        }
        native_body_pixel_quality[frame_name] = native_pixel_quality(frame)
        actor_face_readability[frame_name] = yone_face_readability(frame)
    if len(actor_face_readability) != 54:
        raise ValueError(
            f"Yone face QA must cover 54 visible body frames, got {len(actor_face_readability)}"
        )

    fullbody = Image.open(FULLBODY_DIR / "dual_blader.png").convert("RGBA")
    ui_face_readability = {
        "fullbody": yone_face_readability(fullbody, YONE_ACTOR_FACE_WINDOW),
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
    style = json.loads(
        (MOD_ROOT / "style/champion_view.champion_view").read_text(encoding="utf-8")
    )["entries"]["dual_blader"]
    live_idle_card = yone_live_idle_card_contract(
        sheet,
        anims,
        center_y=style["center"]["y"],
    )
    live_run_profile = yone_live_run_profile_contract(sheet, anims)
    fullbody_card = yone_fullbody_card_contract(fullbody)

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
                "body_master": NATIVE_BODY_MASTER.relative_to(MOD_ROOT).as_posix(),
                "body_logical_sheets": native_sheet_contracts,
                "body_frame_sources": native_frame_source_contracts,
                "horizontal_clip_whitelist": {
                    f"{tag}[{index}]": sides
                    for (tag, index), sides in NATIVE_HORIZONTAL_CLIP_LIMITS.items()
                },
                "pack_time_resampling": "none; 54 body crops are copied byte-for-byte from the native master",
                "master_to_atlas_identity": native_body_identity,
                "pixel_quality": {
                    "contract": {
                        "hard_alpha": True,
                        "maximum_opaque_palette_size": 48,
                        "metrics_are_measured_at": "native 1x",
                    },
                    "frames": native_body_pixel_quality,
                },
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
                "shape": "one stationary caster-following crescent plus one stateless native 80-degree, 42000-range forward cone scan",
                "damage": "35 + 45% Attack + 6% target maximum HP physical damage from the same cone snapshot",
                "shield": "the same native cone snapshot grants one 90-tick 50 + 20% Attack shield after any enemy hit, then scales through every enemy champion hit up to the normal five-champion team limit",
                "state": "no process-global W ledger; hit collection, damage, champion count, and shield tier resolve in one GameCtx callback",
                "attack_speed_limitation": "Mod API 0.8 exposes neither aggregate attack speed nor per-skill dynamic cast/cooldown mutation, so the disclosed 30/480-tick values remain fixed",
            },
            "face_readability": {
                "policy": "complete adult-proportioned ImageGen body-model replacement rasterized once as whole-sheet native 1x pixel art; no per-frame resize, post-scale face repaint, or synthetic feature overlay",
                "body_source_paths": [
                    CORE_SOURCE.relative_to(MOD_ROOT).as_posix(),
                    RUN_SOURCE.relative_to(MOD_ROOT).as_posix(),
                    WR_BODY_SOURCE.relative_to(MOD_ROOT).as_posix(),
                    DEFEAT_SOURCE.relative_to(MOD_ROOT).as_posix(),
                ],
                "actor_resampling": "whole-sheet NEAREST once; pack-time NONE",
                "idle_face_contract": {
                    "source_authored": True,
                    "post_scale_repaint": False,
                    "view": "natural 3/4 profile with one dominant eye cue",
                    "alpha_geometry_changes": 0,
                },
                "all_battle_body_frames": actor_face_readability,
                "ui_surfaces": ui_face_readability,
                "fullbody_card_85x93": fullbody_card,
                "live_idle_card": live_idle_card,
                "live_run_profile": live_run_profile,
            },
            "large_vfx_policy": "Q3 tornado/knockup, compact W crescent/shield, and R feedback are isolated in dedicated sheets; no large effect replaces Yone's actor body.",
            "portrait_policy": {
                "default_runtime": "ABI-safe actor-atlas path: idle[0] plus champion_view face/center/banpick_center cameras",
                "compact": "64x64 face focus, <=50x50 alpha bbox, >=6px border",
                "scoreboard": "48x64 fallback portrait; default runtime scales every native idle frame uniformly by about 2.2x and centers it on the 121px idle stage",
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
            "generated_on": "2026-07-18",
            "processing": "four complete ImageGen adult body contact-sheet replacements, deterministic corner-detected green/magenta body-key despill, one fixed whole-sheet native 1x conversion, hard alpha and <=40-color logical plates, byte-identical master-to-atlas packing with no per-frame resampling or face repaint, and official Dual Blader foot baselines",
            "sources": [image_record(path) for path in (CORE_SOURCE, RUN_SOURCE, WR_BODY_SOURCE, DEFEAT_SOURCE, QW_VFX_SOURCE, W_VFX_SOURCE, Q3_VFX_SOURCE, R_VFX_SOURCE, ICON_SOURCE, SPLASH_SOURCE)],
            "processed": [image_record(path) for path in processed],
            "runtime": [image_record(path) if path.suffix == ".png" else {"path": path.relative_to(MOD_ROOT).as_posix(), "size_bytes": path.stat().st_size, "sha256": sha256(path)} for path in runtime_visuals],
        },
    )

    visual_md = QA_DIR / "yone_visual_qa.md"
    visual_md.write_bytes((
        "# Yone visual QA\n\n"
        "- [x] Same-ID visual replacement targets `dual_blader` (official project hero 009).\n"
        "- [x] Actor canvas is exactly `3502x88`; all 13 native tags, frame counts, durations, rectangles, and insertion order are preserved.\n"
        "- [x] `hit_effect_area` reuses the official `ult[1..11]` atlas rectangles without conflicting pixels.\n"
        "- [x] Idle/run/attack/Q/W/R/dead bodies retain one stable battle scale.\n"
        "- [x] The retired Yone body model was replaced end-to-end with four new ImageGen contact sheets (core, run, Q/W/R body and defeat); Q/W/R effect sheets remain unchanged.\n"
        "- [x] Each complete body plate is rasterized once to a reviewed native 1x grid; all 54 visible body frames are copied byte-for-byte from the native master with no pack-time resize.\n"
        "- [x] The new adult-proportioned natural 3/4 face preserves source-authored eye, jaw and hair clusters without any post-scale face repaint.\n"
        "- [x] Idle/run/attack/hit keep the official Dual Blader bottom clearances, and the card/BP center camera is raised to y=-16 so legs and weapons keep a visible gap above the black divider.\n"
        "- [x] Q3 uses a dedicated horizontal tornado, a vertical blue-white airborne cue, and a small ready-wind state.\n"
        "- [x] Active champion data and release resources do not reference Soul Unbound. Exactly five retired Yone E names plus two retired Shen dash names remain registered only as no-op saved-season compatibility aliases.\n"
        "- [x] W has no process-global ledger: one native callback scans only its current `GameCtx`, resolves an 80-degree forward cone, damages that snapshot, counts champion hits, and emits one shield tier marker.\n"
        "- [x] W keeps Yone planted, plays one full caster-following crescent, and uses five generated WR sweep poses; no code-drawn body, arm or blade is added during packing.\n"
        "- [x] Minions and monsters qualify for the base shield; every enemy champion hit increases its tier through the normal five-champion team limit.\n"
        "- [x] W has no dash, spirit clone, anchor, tether, forced return, recall override, or teleport path.\n"
        "- [x] Compact portrait is face-focused with transparent safety margins.\n"
        "- [x] QA replays the user's exact idle[0] 2.2x nearest-neighbor actor path, compares all idle/run frames, rejects near-white face blocks, and preserves source foot/card-bottom clearances.\n"
        "- [x] BP-grid portrait is full body and ends at `y<=86`, ten pixels above the native name band.\n"
        "- [x] BP illustration is `1420x860`; the three active-slot icons are independent `64x64` assets.\n"
        "\nRuntime effect IDs and sheet tags are recorded in `qa/yone_visual_contract.json`.\n"
    ).encode("utf-8"))

    contact = Image.new("RGBA", (1180, 540), (8, 15, 27, 255))
    draw = ImageDraw.Draw(contact)
    draw.text((18, 12), "YONE ACTOR / UI / EFFECT QA", fill=(222, 232, 242, 255))
    draw.text(
        (18, 34),
        "BATTLE: native 1x pixels (left) / live 2.2x NEAREST preview (right)",
        fill=(130, 188, 220, 255),
    )
    for column, tag in enumerate(("idle", "run", "attack", "skill", "skill2_attack", "ult")):
        frames = anims[tag]["frames"]
        frame = frames[min(1, len(frames) - 1)]["data"]
        crop = sheet.crop((frame["x"], frame["y"], frame["x"] + frame["w"], frame["y"] + frame["h"]))
        live_size = (
            round(crop.width * YONE_LIVE_CARD_SCALE),
            round(crop.height * YONE_LIVE_CARD_SCALE),
        )
        live = crop.resize(live_size, Image.Resampling.NEAREST)
        x = 18 + column * 190
        draw.text((x, 56), tag, fill=(196, 210, 225, 255))
        native_origin = (x, 82)
        live_origin = (x + 66, 82)
        draw.rectangle(
            (
                native_origin[0] - 1,
                native_origin[1] - 1,
                native_origin[0] + crop.width,
                native_origin[1] + crop.height,
            ),
            outline=(56, 74, 94, 255),
        )
        draw.rectangle(
            (
                live_origin[0] - 1,
                live_origin[1] - 1,
                live_origin[0] + live.width,
                live_origin[1] + live.height,
            ),
            outline=(56, 74, 94, 255),
        )
        contact.alpha_composite(crop, native_origin)
        contact.alpha_composite(live, live_origin)
        draw.text((x, 180), "native 1x", fill=(122, 140, 158, 255))
        draw.text((x + 66, 180), "live 2.2x", fill=(122, 140, 158, 255))
    draw.line((18, 214, 1162, 214), fill=(45, 61, 78, 255), width=1)
    draw.text(
        (18, 230),
        "UI: independent high-resolution surfaces at their own native 1x (not enlarged battle frames)",
        fill=(130, 188, 220, 255),
    )
    portraits = [
        ("compact 64x64", PORTRAIT_DIR / "dual_blader_compact.png", (18, 286)),
        ("scoreboard 48x64", PORTRAIT_DIR / "dual_blader_scoreboard.png", (152, 286)),
        ("fullbody 64x64", FULLBODY_DIR / "dual_blader.png", (286, 286)),
        ("grid 90x122", PORTRAIT_DIR / "dual_blader_grid.png", (420, 286)),
    ]
    for label, path, position in portraits:
        draw.text((position[0], position[1] - 18), label, fill=(196, 210, 225, 255))
        image = Image.open(path).convert("RGBA")
        contact.alpha_composite(image, position)
    for index, (label, path) in enumerate((
        ("Q", ICON_DIR / "yone_skill.png"), ("W", ICON_DIR / "yone_skill2.png"), ("R", ICON_DIR / "yone_ult.png"),
    )):
        x = 650 + index * 150
        draw.text((x, 268), f"{label} icon 64x64", fill=(196, 210, 225, 255))
        icon = Image.open(path).convert("RGBA")
        contact.alpha_composite(icon, (x, 286))
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
    native_master = Image.open(NATIVE_BODY_MASTER).convert("RGBA")
    if native_master.size != ACTOR_SHEET_SIZE:
        raise ValueError(
            f"Yone native body master is {native_master.size}, expected {ACTOR_SHEET_SIZE}"
        )

    native_edge_ratios: list[float] = []
    native_fill_ratios: list[float] = []
    native_identity_count = 0
    for tag, index, entry in iter_actor_body_frames(payload):
        data = entry["data"]
        rect = (
            data["x"], data["y"],
            data["x"] + data["w"], data["y"] + data["h"],
        )
        frame = sheet.crop(rect)
        master_frame = native_master.crop(rect)
        if frame.tobytes() != master_frame.tobytes():
            raise ValueError(
                f"Yone {tag}[{index}] was changed after native-master packing"
            )
        native_identity_count += 1
        quality = native_pixel_quality(frame)
        if not quality["hard_alpha"]:
            raise ValueError(
                f"Yone {tag}[{index}] contains non-binary alpha: {quality['alpha_values']}"
            )
        if quality["opaque_palette_size"] > 48:
            raise ValueError(
                f"Yone {tag}[{index}] uses {quality['opaque_palette_size']} opaque colors"
            )
        # Ground/death poses deliberately become very flat; keep their metrics
        # in QA but do not compare them to upright silhouette density.
        if tag != "dead":
            native_edge_ratios.append(quality["color_edge24_ratio"])
            native_fill_ratios.append(quality["bbox_fill_ratio"])
            if quality["bbox_fill_ratio"] < 0.20:
                raise ValueError(
                    f"Yone {tag}[{index}] native silhouette is too sparse: {quality}"
                )
            if quality["color_edge24_ratio"] < 0.16:
                raise ValueError(
                    f"Yone {tag}[{index}] native color construction is too flat: {quality}"
                )
    if native_identity_count != 54:
        raise ValueError(
            f"Yone native identity audit covered {native_identity_count}/54 body frames"
        )
    median_edge = sorted(native_edge_ratios)[len(native_edge_ratios) // 2]
    median_fill = sorted(native_fill_ratios)[len(native_fill_ratios) // 2]
    if median_edge < 0.36 or median_fill < 0.34:
        raise ValueError(
            "Yone native body construction regressed below the crispness baseline: "
            f"median edge24={median_edge:.4f}, bbox fill={median_fill:.4f}"
        )

    for tag, expected_bottoms in BODY_BOTTOM_MARGINS.items():
        for index, (row, expected_bottom, minimum_height) in enumerate(
            zip(
                payload[tag]["frames"],
                expected_bottoms,
                NATIVE_MIN_VISIBLE_HEIGHTS[tag],
                strict=True,
            )
        ):
            data = row["data"]
            frame = sheet.crop((data["x"], data["y"], data["x"] + data["w"], data["y"] + data["h"]))
            bbox = frame.getchannel("A").getbbox()
            if bbox is None:
                raise ValueError(f"Yone {tag}[{index}] is empty")
            actual_bottom = data["h"] - bbox[3]
            if actual_bottom != expected_bottom or (
                tag != "skill2_attack" and actual_bottom < 4
            ):
                raise ValueError(f"Yone {tag}[{index}] bottom anchor {actual_bottom} != {expected_bottom}")
            visible_height = bbox[3] - bbox[1]
            if visible_height < minimum_height:
                raise ValueError(
                    f"Yone {tag}[{index}] body shrank below its stable scale: "
                    f"{visible_height}px vs minimum {minimum_height}px"
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

    expected_w_sources = [("wr", index) for index in range(5)]
    if NATIVE_BODY_FRAME_SOURCES["skill2_attack"] != expected_w_sources:
        raise ValueError(
            "Yone W must use the five generated WR native cells, got "
            f"{NATIVE_BODY_FRAME_SOURCES['skill2_attack']}"
        )
    w_pose_hashes: set[str] = set()
    for row in payload["skill2_attack"]["frames"]:
        data = row["data"]
        frame = sheet.crop(
            (
                data["x"],
                data["y"],
                data["x"] + data["w"],
                data["y"] + data["h"],
            )
        )
        w_pose_hashes.add(hashlib.sha256(frame.tobytes()).hexdigest())
    if len(w_pose_hashes) < 4:
        raise ValueError(
            f"Yone generated W lost sweep motion: {len(w_pose_hashes)}/5 unique native poses"
        )

    native_core_bottoms = {
        "idle": [16, 15, 14, 15],
        "run": [13, 18, 21, 18, 13, 17, 21, 17],
        "attack": [14, 14, 12, 13, 13, 14],
        "hit": [15],
    }
    actual_core_bottoms = {
        tag: BODY_BOTTOM_MARGINS[tag]
        for tag in native_core_bottoms
    }
    if actual_core_bottoms != native_core_bottoms:
        raise ValueError(
            "Yone core foot anchors diverged from the official Dual Blader: "
            f"{actual_core_bottoms}"
        )

    # Inspect all 54 visible body frames from the rebuilt ImageGen model.  The
    # face is now source-authored, so validate its natural skin component,
    # contrast and dark feature cue instead of retired palette-marker counts.
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
        if tag == "dead":
            bbox = frame.getchannel("A").getbbox()
            visible_height = 0 if bbox is None else bbox[3] - bbox[1]
            required_mask = max(1, min(6, visible_height // 4))
            if face["red_mask_pixels"] < required_mask:
                raise ValueError(f"Yone dead[{index}] lost the rebuilt mask silhouette: {face}")
            continue
        face_bbox = face["face_skin_bbox"]
        if tag == "idle":
            minimum_width, minimum_height, minimum_skin, minimum_contrast = (
                4, 5, 10, 18
            )
        elif tag == "run":
            # The accepted corrective run plate keeps a real native face in
            # every phase.  This deliberately rejects the former 2x2/4-pixel
            # proxy that passed automation while looking like a mask blob.
            minimum_width, minimum_height, minimum_skin, minimum_contrast = (
                4, 3, 6, 50
            )
        else:
            minimum_width, minimum_height, minimum_skin, minimum_contrast = (
                3, 2, 4, 12
            )
        native_face_readable = (
            face_bbox is not None
            and face_bbox[2] - face_bbox[0] >= minimum_width
            and face_bbox[3] - face_bbox[1] >= minimum_height
            and face["warm_skin_component_present"]
            and face["warm_skin_pixels"] >= minimum_skin
            and face["adjacent_dark_eye_cue"]
            and face["face_contrast"] >= minimum_contrast
            and face["near_white_pixels"]
            <= max(2, face["face_skin_pixels"] // 20)
            and face["minimal_feature_set"]
        )
        if not native_face_readable:
            raise ValueError(f"Yone {tag}[{index}] face is not readable: {face}")
    if face_frame_count != 54:
        raise ValueError(f"Yone face validation covered {face_frame_count}/54 frames")

    # Replay the measured renderer route from the user's screenshots.  Every
    # idle rectangle is scaled uniformly by about 2.2x, then centered on the
    # tallest idle stage.  The rejected screenshot exactly matched idle[0], so proving
    # a stretched idle[0]-only 86x121 helper would miss the real regression.
    style = json.loads(
        (MOD_ROOT / "style/champion_view.champion_view").read_text(encoding="utf-8")
    )["entries"]["dual_blader"]
    expected_style = {
        "face": {"x": 2, "y": -32},
        "center": {"x": 0, "y": -16},
        "banpick_center": {"x": 0, "y": -16},
    }
    if style != expected_style:
        raise ValueError(f"Yone card/BP camera changed: {style} != {expected_style}")
    live_idle_card = yone_live_idle_card_contract(
        sheet,
        payload,
        center_y=style["center"]["y"],
    )
    if set(live_idle_card["frames"]) != {
        "idle[0]",
        "idle[1]",
        "idle[2]",
        "idle[3]",
    }:
        raise ValueError(
            f"Yone live-card idle coverage changed: {set(live_idle_card['frames'])}"
        )
    for frame_name, quality in live_idle_card["frames"].items():
        if not (
            quality["source_face_skin_bbox"] is not None
            and quality["rendered_face_skin_bbox"] is not None
            and quality["source_warm_skin_component_present"]
            and quality["rendered_warm_skin_component_present"]
            and quality["source_adjacent_dark_eye_cue"]
            and quality["rendered_adjacent_dark_eye_cue"]
            and quality["source_near_white_pixels"] <= 1
        ):
            raise ValueError(
                f"Yone {frame_name} minimal face is unreadable at 2.2x: {quality}"
            )
        if quality["divider_clearance"] < YONE_LIVE_CARD_MIN_DIVIDER_CLEARANCE:
            raise ValueError(
                f"Yone {frame_name} feet/weapon enter the card divider: "
                f"clearance={quality['divider_clearance']}"
            )

    live_run_profile = yone_live_run_profile_contract(sheet, payload)
    expected_run_frames = {f"run[{index}]" for index in range(8)}
    if set(live_run_profile["frames"]) != expected_run_frames:
        raise ValueError(
            "Yone live run-profile coverage changed: "
            f"{set(live_run_profile['frames'])}"
        )
    readable_run_eye_cues = 0
    for index, (frame_name, quality) in enumerate(
        live_run_profile["frames"].items()
    ):
        profile_geometry = (
            quality["source_face_skin_bbox"] is not None
            and quality["rendered_face_skin_bbox"] is not None
            and quality["source_red_mask_pixels"] >= 20
            and quality["source_near_white_pixels"] <= 2
        )
        if quality["source_adjacent_dark_eye_cue"]:
            readable_run_eye_cues += 1
        if (
            quality["face_variant"] != "profile"
            or not profile_geometry
            or not quality["source_warm_skin_component_present"]
            or not quality["rendered_warm_skin_component_present"]
            or not quality["source_adjacent_dark_eye_cue"]
            or not quality["rendered_adjacent_dark_eye_cue"]
        ):
            raise ValueError(
                f"Yone {frame_name} profile face is unreadable at 2.2x: {quality}"
            )
        if (
            quality["source_bottom_clearance"] != BODY_BOTTOM_MARGINS["run"][index]
            or quality["rendered_bottom_clearance"] <= 0
        ):
            raise ValueError(
                f"Yone {frame_name} lost its run-foot clearance at 2.2x: {quality}"
            )
    if readable_run_eye_cues < 7:
        raise ValueError(
            f"Yone run loop kept a visible eye cue in only {readable_run_eye_cues}/8 frames"
        )

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

    fullbody = Image.open(FULLBODY_DIR / "dual_blader.png").convert("RGBA")
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
    for label, image in (
        ("fullbody", fullbody),
        ("compact", compact),
        ("scoreboard", scoreboard),
        ("grid", grid),
    ):
        face = yone_face_readability(image, YONE_UI_FACE_WINDOWS[label])
        face_bbox = face["face_skin_bbox"]
        minimum_width, minimum_height, minimum_skin = (
            (5, 6, 14) if label == "fullbody" else (6, 8, 20)
        )
        if (
            face_bbox is None
            or face_bbox[2] - face_bbox[0] < minimum_width
            or face_bbox[3] - face_bbox[1] < minimum_height
            or not face["warm_skin_component_present"]
            or face["warm_skin_pixels"] < minimum_skin
            or not face["adjacent_dark_eye_cue"]
            or face["near_white_pixels"] > max(4, face["face_skin_pixels"] // 10)
        ):
            raise ValueError(f"Yone {label} portrait face is not readable: {face}")
    if fullbody.size != (64, 64):
        raise ValueError("Yone encyclopedia portrait is not 64x64")
    fullbody_card = yone_fullbody_card_contract(fullbody)
    if (
        fullbody_card["rendered_size"] != [85, 93]
        or fullbody_card["source_alpha_bbox"] is None
        or fullbody_card["rendered_alpha_bbox"] is None
        or fullbody_card["source_bottom_margin"] < 3
        or fullbody_card["rendered_bottom_margin"] < 4
        or fullbody_card["rendered_face_skin_bbox"] is None
        or fullbody_card["source_red_mask_pixels"] < 20
    ):
        raise ValueError(
            f"Yone real 64x64 -> 85x93 fullbody card route failed: {fullbody_card}"
        )
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
