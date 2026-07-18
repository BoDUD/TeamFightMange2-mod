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

# Yone's accepted source already contains the correct half-mask, hair line and
# narrow exposed cheek.  The live card enlarges native idle frames by 2.2x;
# their several warm-white source pixels otherwise become the rejected white
# cross seen in game.  Retouch only the pre-edit skin component: compress the
# bright skin into three warm tones, then reinforce one two-pixel visible eye,
# one nose point and a one/two-pixel mouth.  Never stamp a rectangular face
# plane and never repaint hair, mask, outline or merely-opaque head pixels.
YONE_FACE_FEATURE_RGBA = (25, 15, 20, 255)
YONE_FACE_IRIS_RGBA = (176, 62, 52, 255)
YONE_FACE_NOSE_RGBA = (145, 76, 68, 255)
YONE_FACE_MOUTH_RGBA = (88, 29, 38, 255)
YONE_FACE_TONE_LIGHT_RGBA = (218, 169, 139, 255)
YONE_FACE_TONE_MID_RGBA = (196, 132, 105, 255)
YONE_FACE_TONE_SHADOW_RGBA = (172, 105, 86, 255)
YONE_FACE_TONE_RGBA = {
    YONE_FACE_TONE_LIGHT_RGBA,
    YONE_FACE_TONE_MID_RGBA,
    YONE_FACE_TONE_SHADOW_RGBA,
}
YONE_FACE_MAX_TONED_SKIN = 32
YONE_FACE_MAX_RETOUCH_PIXELS = 38
YONE_LIVE_CARD_SCALE = 2.2
YONE_LIVE_CARD_DIVIDER_TOP = 99
YONE_LIVE_CARD_AUDITED_CENTER_Y = -16
YONE_LIVE_CARD_MIN_DIVIDER_CLEARANCE = 10
YONE_FORBIDDEN_RETIRED_FACE_RGBA = {
    (54, 27, 30, 255),
    (232, 192, 158, 255),
    (108, 44, 49, 255),
    (154, 84, 69, 255),
    (200, 124, 95, 255),
    (226, 164, 130, 255),
    (54, 24, 29, 255),
    (118, 46, 51, 255),
    (169, 96, 79, 255),
    (211, 136, 108, 255),
    (239, 184, 150, 255),
    # Retired two-dark-eye pass. These colors are negative sentinels only: no
    # current actor or UI face may contain a pixel from this set.
    (250, 224, 188, 255),
    (98, 32, 39, 255),
    (218, 151, 115, 255),
    (24, 14, 19, 255),
    (212, 178, 157, 255),
    (124, 50, 53, 255),
    (18, 16, 23, 255),
    (122, 62, 54, 255),
    (178, 101, 77, 255),
    (202, 129, 98, 255),
}
YONE_NEAR_WHITE_MIN = 218

# Normalized against the final alpha bbox, not the native frame rectangle.
# Full-body frames keep the head in the upper/right half; compact/scoreboard
# crops remove the lower body and therefore need a slightly wider focus.
YONE_ACTOR_FACE_WINDOW = (0.18, 0.00, 0.98, 0.58)
YONE_FOCUSED_UI_FACE_WINDOW = (0.35, 0.08, 0.98, 0.70)
YONE_UI_FACE_RECIPES: dict[str, dict[str, Any]] = {
    # Coordinates are audited against each surface's own natural downsample.
    # They are not transferable templates: the safe primitive may write only
    # the pre-edit skin component and each surface has its own pixel budget.
    "fullbody": {
        "window": YONE_ACTOR_FACE_WINDOW,
        "eye": (34, 20),
        "safe_y": (18, 24),
        "landmarks": {
            "eye": ((33, 20), (34, 20)),
            "nose": (33, 22),
            "mouth": ((32, 23), (33, 23)),
        },
        "tones": 16,
        "budget": 22,
    },
    "compact": {
        "window": YONE_FOCUSED_UI_FACE_WINDOW,
        "eye": (45, 26),
        "tones": 32,
        "budget": 38,
    },
    "scoreboard": {
        "window": YONE_FOCUSED_UI_FACE_WINDOW,
        "eye": (34, 23),
        "tones": 32,
        "budget": 38,
    },
    "grid": {
        "window": YONE_ACTOR_FACE_WINDOW,
        "eye": (49, 28),
        "tones": 32,
        "budget": 38,
    },
}

# Every non-empty native body frame is assigned one reviewed pose so the
# minimal eye/nose/mouth hints stay anchored to the intended head component.
# The last two extreme R frames expose too little face skin for all three
# points, so they retain only one dark visible-eye cue.
YONE_FRONT_FACE_FRAMES = {
    *(('idle', index) for index in range(4)),
    ('attack', 0),
    ('attack', 3),
    ('attack', 5),
    ('skill', 0),
    *(('skill2_attack', index) for index in range(5)),
}
YONE_PROFILE_FACE_FRAMES = {
    *(('run', index) for index in range(8)),
    ('attack', 1),
    ('attack', 2),
    ('attack', 4),
    ('hit', 0),
    *(('skill', index) for index in range(1, 7)),
    ('skill2', 0),
    ('skill2_dash', 0),
    *(('ult', index) for index in range(13) if index not in {5, 7}),
    *(('dead', index) for index in range(8)),
}
YONE_SINGLE_EYE_PROFILE_FRAMES = {
    ("ult", 5),
    ("ult", 7),
}

# Reviewed eye coordinates for poses where automatic component selection can
# lock onto a foreshortened hand or bare chest. These are targets only: the
    # repaint chooses an existing source-skin pixel nearest each point and never
# changes alpha geometry or stamps a synthetic face plane.
YONE_FACE_EYE_OVERRIDES: dict[tuple[str, int], tuple[int, int]] = {
    ("idle", 0): (22, 10),
    ("idle", 2): (20, 9),
    ("run", 2): (26, 6),
    ("run", 3): (26, 8),
    ("run", 4): (29, 11),
    ("run", 5): (27, 9),
    ("run", 7): (27, 9),
    ("attack", 1): (28, 8),
    ("attack", 2): (23, 9),
    ("attack", 4): (25, 10),
    ("skill", 1): (17, 11),
    ("skill", 2): (15, 22),
    ("skill", 4): (36, 29),
    ("skill2", 0): (17, 16),
    ("skill2_dash", 0): (29, 15),
    ("ult", 0): (28, 22),
    ("ult", 2): (28, 19),
    ("ult", 3): (31, 14),
    ("ult", 4): (28, 11),
    ("ult", 5): (35, 12),
    ("ult", 6): (29, 16),
    ("ult", 7): (33, 16),
    ("ult", 9): (28, 15),
    ("dead", 0): (20, 18),
    ("dead", 1): (22, 21),
    ("dead", 3): (29, 22),
    ("dead", 4): (29, 25),
}

# The four frames used by the actual roster/card renderer are audited at their
# native sizes.  idle[2]/idle[3] have a skin component connected to the bare
# chest, so their safe seven-row face ranges are mandatory rather than an
# aesthetic hint.  Every landmark is an original source-skin pixel.
YONE_LIVE_IDLE_FACE_RECIPES: dict[tuple[str, int], dict[str, Any]] = {
    ("idle", 0): {
        "safe_y": (8, 15),
        "eye": ((21, 10), (22, 10)),
        "nose": (21, 12),
        "mouth": ((20, 14), (21, 14)),
    },
    ("idle", 1): {
        "safe_y": (8, 15),
        "eye": ((22, 10), (23, 10)),
        "nose": (22, 12),
        "mouth": ((21, 14), (22, 14)),
    },
    ("idle", 2): {
        "safe_y": (8, 14),
        "eye": ((20, 9), (21, 9)),
        "nose": (21, 11),
        "mouth": ((20, 13), (21, 13)),
    },
    ("idle", 3): {
        "safe_y": (8, 15),
        "eye": ((20, 10), (21, 10)),
        "nose": (20, 12),
        "mouth": ((19, 14), (20, 14)),
    },
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


def _is_yone_face_skin_pixel(pixel: tuple[int, int, int, int]) -> bool:
    return _is_yone_warm_face_pixel(pixel) or _is_yone_near_white(pixel)


def _nearest_face_point(
    points: set[tuple[int, int]],
    target: tuple[float, float],
    *,
    minimum_y: int | None = None,
) -> tuple[int, int]:
    eligible = [
        point
        for point in points
        if (minimum_y is None or point[1] >= minimum_y)
    ]
    if not eligible:
        raise ValueError(f"Yone face has no skin point near {target}")
    return min(
        eligible,
        key=lambda point: (
            (point[0] - target[0]) ** 2 + 3.0 * (point[1] - target[1]) ** 2,
            point[1],
            point[0],
        ),
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
    preferred_eye: tuple[int, int] | None = None,
) -> tuple[set[tuple[int, int]], tuple[int, int, int, int]]:
    """Locate the source-derived face skin without accepting the bare chest.

    The generated model exposes a large warm torso, so a bbox-wide skin test
    incorrectly called the chest a 14x19 face.  Candidate scoring is anchored
    near the head, while the final eye/brow cue is placed in the upper part of
    a merged face/neck component when a pose joins those pixels.
    """

    body, (x0, y0, x1, y1) = _face_window_rect(image, window)
    skin = {
        (x, y)
        for y in range(y0, y1)
        for x in range(x0, x1)
        if _is_yone_face_skin_pixel(image.getpixel((x, y)))
    }
    minimum = max(4, round((body[3] - body[1]) * 0.13))
    components = [
        component
        for component in _point_components(skin)
        if len(component) >= minimum
    ]
    if not components:
        raise ValueError(
            f"Yone final frame has no source-skin face candidate in {(x0, y0, x1, y1)}"
        )

    if preferred_eye is None:
        target_x = body[0] + (body[2] - body[0]) * 0.58
        target_y = body[1] + (body[3] - body[1]) * 0.28
    else:
        target_x, target_y = preferred_eye

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
    preferred_eye: tuple[int, int] | None = None,
    variant: str = "front",
    allow_single_eye: bool = False,
    safe_y: tuple[int, int] | None = None,
    landmarks: dict[str, Any] | None = None,
    max_toned_skin: int = YONE_FACE_MAX_TONED_SKIN,
    max_retouch_pixels: int = YONE_FACE_MAX_RETOUCH_PIXELS,
) -> Image.Image:
    """Retone and mark only the source-derived exposed face-skin component."""

    if variant not in {"front", "profile"}:
        raise ValueError(f"Unknown Yone face variant: {variant}")
    if not 0 <= max_toned_skin <= YONE_FACE_MAX_TONED_SKIN:
        raise ValueError(f"Invalid Yone tone budget: {max_toned_skin}")
    if not 1 <= max_retouch_pixels <= YONE_FACE_MAX_RETOUCH_PIXELS:
        raise ValueError(f"Invalid Yone retouch budget: {max_retouch_pixels}")

    source = image.convert("RGBA")
    output = source.copy()
    size_before = output.size
    alpha_before = output.getchannel("A").tobytes()
    _, face_window = _face_window_rect(output, window)
    existing_pupil = {
        (x, y)
        for y in range(face_window[1], face_window[3])
        for x in range(face_window[0], face_window[2])
        if output.getpixel((x, y)) == YONE_FACE_FEATURE_RGBA
    }
    existing_iris = {
        (x, y)
        for y in range(face_window[1], face_window[3])
        for x in range(face_window[0], face_window[2])
        if output.getpixel((x, y)) == YONE_FACE_IRIS_RGBA
    }
    existing_nose = {
        (x, y)
        for y in range(face_window[1], face_window[3])
        for x in range(face_window[0], face_window[2])
        if output.getpixel((x, y)) == YONE_FACE_NOSE_RGBA
    }
    existing_mouth = {
        (x, y)
        for y in range(face_window[1], face_window[3])
        for x in range(face_window[0], face_window[2])
        if output.getpixel((x, y)) == YONE_FACE_MOUTH_RGBA
    }
    existing_eye = existing_pupil | existing_iris
    eye_components = _point_components(existing_eye) if existing_eye else []
    mouth_components = _point_components(existing_mouth) if existing_mouth else []
    existing_minimal = (
        len(existing_pupil) == 1
        and len(existing_iris) <= 1
        and len(existing_eye) <= 2
        and len(eye_components) == 1
        and (
            (
                allow_single_eye
                and not existing_iris
                and not existing_nose
                and not existing_mouth
            )
            or (
                not allow_single_eye
                and len(existing_nose) == 1
                and 1 <= len(existing_mouth) <= 2
                and len(mouth_components) == 1
            )
        )
    )
    if existing_minimal:
        if output.size != size_before or output.getchannel("A").tobytes() != alpha_before:
            raise ValueError("Yone idempotent face pass changed alpha geometry")
        return output
    if existing_eye or existing_nose or existing_mouth:
        raise ValueError(
            "Yone face has a partial minimal-feature set: "
            f"pupil={existing_pupil}, iris={existing_iris}, "
            f"nose={existing_nose}, mouth={existing_mouth}"
        )

    component, (left, top, right, bottom) = _locate_yone_face_component(
        output, window, preferred_eye
    )
    target_x = preferred_eye[0] if preferred_eye is not None else right - 2
    target_y = preferred_eye[1] if preferred_eye is not None else min(bottom - 1, top + 2)
    target_x = max(left, min(right - 1, target_x))
    target_y = max(top, min(bottom - 1, target_y))
    if safe_y is None:
        # The eye-to-mouth distance is four native pixels.  This eye-relative
        # seven-to-nine-row window retains the whole jaw while excluding the
        # connected bare chest in idle[2]/idle[3] and several action poses.
        safe_top = max(top, target_y - 3)
        safe_bottom = min(bottom, target_y + 5)
    else:
        safe_top = max(top, safe_y[0])
        safe_bottom = min(bottom, safe_y[1])
    if safe_top >= safe_bottom:
        raise ValueError(f"Yone face has an empty safe y range: {(safe_top, safe_bottom)}")
    head_points = {
        point
        for point in component
        if safe_top <= point[1] < safe_bottom
        and target_x - 7 <= point[0] <= target_x + 7
    }
    if len(head_points) < (1 if allow_single_eye else 3):
        raise ValueError(
            f"Yone source face is too small for minimal features: {sorted(head_points)}"
        )

    eye_points: tuple[tuple[int, int], ...]
    nose: tuple[int, int] | None = None
    mouth_points: tuple[tuple[int, int], ...] = ()
    if landmarks is not None:
        if allow_single_eye:
            raise ValueError("Yone explicit normal landmarks cannot be single-eye-only")
        eye_points = tuple(tuple(point) for point in landmarks["eye"])
        nose = tuple(landmarks["nose"])
        mouth_points = tuple(tuple(point) for point in landmarks["mouth"])
        explicit = set(eye_points) | {nose} | set(mouth_points)
        if not explicit.issubset(head_points):
            raise ValueError(
                "Yone explicit landmarks escaped the source-skin face: "
                f"{sorted(explicit - head_points)}"
            )
        if len(eye_points) != 2 or not 1 <= len(mouth_points) <= 2:
            raise ValueError(f"Yone explicit landmarks are malformed: {landmarks}")
    elif allow_single_eye:
        eye_points = (_nearest_face_point(head_points, (target_x, target_y)),)
    else:
        rows = sorted({y for _, y in head_points})
        if len(rows) < 3:
            raise ValueError(
                f"Yone source face lacks three semantic rows: {sorted(head_points)}"
            )
        eye_row, nose_row, mouth_row = min(
            combinations(rows, 3),
            key=lambda triple: (
                3.0 * (triple[0] - target_y) ** 2
                + (triple[1] - triple[0] - 2) ** 2
                + (triple[2] - triple[0] - 4) ** 2,
                triple,
            ),
        )
        eye_anchor = _nearest_face_point(
            {point for point in head_points if point[1] == eye_row},
            (target_x, eye_row),
        )
        adjacent_eye = sorted(
            (
                point
                for point in head_points
                if point[1] == eye_row
                and abs(point[0] - eye_anchor[0]) == 1
            ),
            key=lambda point: (
                0 if point[0] < eye_anchor[0] else 1,
                abs(point[0] - target_x),
                point[0],
            ),
        )
        eye_points = (
            (adjacent_eye[0], eye_anchor)
            if adjacent_eye
            else (eye_anchor,)
        )
        nose = _nearest_face_point(
            {point for point in head_points if point[1] == nose_row},
            (eye_anchor[0] - 1, nose_row),
        )
        mouth_anchor = _nearest_face_point(
            {point for point in head_points if point[1] == mouth_row},
            (nose[0], mouth_row),
        )
        adjacent_mouth = sorted(
            (
                point
                for point in head_points
                if point[1] == mouth_row
                and abs(point[0] - mouth_anchor[0]) == 1
            ),
            key=lambda point: (
                0 if point[0] < mouth_anchor[0] else 1,
                abs(point[0] - nose[0]),
                point[0],
            ),
        )
        mouth_points = (
            (adjacent_mouth[0], mouth_anchor)
            if adjacent_mouth
            else (mouth_anchor,)
        )

    feature_points = set(eye_points) | set(mouth_points)
    if nose is not None:
        feature_points.add(nose)

    # Tone every over-bright source-skin pixel in the safe face rows.  Previous
    # code checked only neutral near-white; the rejected cross was mostly warm
    # ivory and therefore survived.  Luminance tiers preserve cheek volume.
    tone_candidates = sorted(
        (point for point in head_points - feature_points),
        key=lambda point: (
            min(
                abs(point[0] - feature[0]) + abs(point[1] - feature[1])
                for feature in feature_points
            ),
            point[1],
            point[0],
        ),
    )
    toned_points: set[tuple[int, int]] = set()
    if not allow_single_eye:
        for point in tone_candidates:
            red, green, blue, alpha = source.getpixel(point)
            luminance = 0.2126 * red + 0.7152 * green + 0.0722 * blue
            tone: tuple[int, int, int, int] | None = None
            if luminance >= 220:
                tone = YONE_FACE_TONE_LIGHT_RGBA
            elif luminance >= 190:
                tone = YONE_FACE_TONE_MID_RGBA
            elif luminance >= 175:
                tone = YONE_FACE_TONE_SHADOW_RGBA
            if tone is not None and tone != source.getpixel(point):
                if len(toned_points) >= max_toned_skin:
                    raise ValueError(
                        f"Yone face needs more than {max_toned_skin} toned skin pixels"
                    )
                output.putpixel(point, tone[:-1] + (alpha,))
                toned_points.add(point)

    output.putpixel(eye_points[0], YONE_FACE_FEATURE_RGBA)
    if len(eye_points) == 2:
        output.putpixel(eye_points[1], YONE_FACE_IRIS_RGBA)
    if nose is not None and mouth_points:
        output.putpixel(nose, YONE_FACE_NOSE_RGBA)
        for point in mouth_points:
            output.putpixel(point, YONE_FACE_MOUTH_RGBA)

    if output.size != size_before or output.getchannel("A").tobytes() != alpha_before:
        raise ValueError("Yone minimal face pass changed alpha geometry")
    changed_points = {
        (x, y)
        for y in range(output.height)
        for x in range(output.width)
        if output.getpixel((x, y)) != source.getpixel((x, y))
    }
    if not changed_points.issubset(component):
        raise ValueError(
            "Yone minimal face pass escaped the original skin component: "
            f"{sorted(changed_points - component)}"
        )
    if len(changed_points) > max_retouch_pixels:
        raise ValueError(
            f"Yone minimal face pass rewrote {len(changed_points)} pixels"
        )
    quality = yone_face_readability(output, window)
    accepted = quality["single_eye_only"] if allow_single_eye else quality["minimal_feature_set"]
    if not accepted or not quality["skin_locked_features"]:
        raise ValueError(f"Yone minimal source-skin face failed: {quality}")
    return output


def _minimal_yone_face_metrics(
    image: Image.Image,
    window: FaceWindow,
) -> dict[str, Any]:
    body, (x0, y0, x1, y1) = _face_window_rect(image, window)
    pupil = {
        (x, y)
        for y in range(y0, y1)
        for x in range(x0, x1)
        if image.getpixel((x, y)) == YONE_IMAGEGEN_EYE_RGBA
    }
    iris = {
        (x, y)
        for y in range(y0, y1)
        for x in range(x0, x1)
        if image.getpixel((x, y)) == YONE_IMAGEGEN_IRIS_RGBA
    }
    eye = pupil | iris
    nose = {
        (x, y)
        for y in range(y0, y1)
        for x in range(x0, x1)
        if image.getpixel((x, y)) == YONE_IMAGEGEN_NOSE_RGBA
    }
    mouth = {
        (x, y)
        for y in range(y0, y1)
        for x in range(x0, x1)
        if image.getpixel((x, y)) == YONE_IMAGEGEN_MOUTH_RGBA
    }
    semantic = eye | nose | mouth
    try:
        source_skin, face_bbox = _locate_yone_face_component(image, window, None)
    except ValueError:
        source_skin, face_bbox = set(), None
    face_component = source_skin | semantic
    feature_bbox = _component_bbox(semantic) if semantic else None
    skin_locked_features = bool(face_component) and all(
        face_bbox is not None
        and face_bbox[0] <= x < face_bbox[2]
        and face_bbox[1] <= y < face_bbox[3]
        for x, y in semantic
    )
    ordered_eye = sorted(eye)
    ordered_nose = sorted(nose)
    ordered_mouth = sorted(mouth)
    eye_components = _point_components(eye) if eye else []
    mouth_components = _point_components(mouth) if mouth else []
    paired_eye_shape = (
        len(pupil) == 2
        and len(iris) == 2
        and len(eye_components) == 2
        and len({y for _, y in eye}) == 1
        and all(len(component) == 2 for component in eye_components)
    )
    mouth_shape = (
        1 <= len(mouth) <= 2
        and len(mouth_components) == 1
        and (
            len(mouth) == 1
            or (
                len({y for _, y in mouth}) == 1
                and max(x for x, _ in mouth) - min(x for x, _ in mouth) == 1
            )
        )
    )
    feature_order = (
        paired_eye_shape
        and len(nose) == 1
        and mouth_shape
        and max(y for _, y in eye) < next(iter(nose))[1] < min(y for _, y in mouth)
        and min(y for _, y in mouth) >= min(y for _, y in eye) + 2
    )
    compact_feature_bbox = (
        feature_bbox is not None
        and feature_bbox[2] - feature_bbox[0] <= 10
        and feature_bbox[3] - feature_bbox[1] <= 9
    )
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
    audited_skin = face_component - semantic
    audited_luminance = [
        0.2126 * image.getpixel(point)[0]
        + 0.7152 * image.getpixel(point)[1]
        + 0.0722 * image.getpixel(point)[2]
        for point in audited_skin
    ]
    near_white = sum(
        1 for point in audited_skin if _is_yone_near_white(image.getpixel(point))
    )
    toned_skin = sum(
        1 for point in audited_skin if image.getpixel(point) == YONE_IMAGEGEN_FACE_LIGHT_RGBA
    )
    bright_face_skin = sum(value >= 205 for value in audited_luminance)
    face_contrast = (
        max(audited_luminance) - min(audited_luminance)
        if audited_luminance
        else 0.0
    )
    natural_dark_features: set[tuple[int, int]] = set()
    if face_bbox is not None:
        left, top, right, bottom = face_bbox
        for y in range(top + 1, min(bottom, top + max(4, (bottom - top) * 2 // 3))):
            for x in range(left + 1, max(left + 1, right - 1)):
                red, green, blue, alpha = image.getpixel((x, y))
                luminance = 0.2126 * red + 0.7152 * green + 0.0722 * blue
                red_mask_pixel = red >= 90 and red > green * 1.55 and red > blue * 1.35
                if alpha >= 128 and luminance <= 72 and not red_mask_pixel:
                    natural_dark_features.add((x, y))
    retired_pixels = sum(
        1
        for y in range(y0, y1)
        for x in range(x0, x1)
        if image.getpixel((x, y)) in YONE_FORBIDDEN_RETIRED_FACE_RGBA
    )
    face_width = 0 if face_bbox is None else face_bbox[2] - face_bbox[0]
    face_height = 0 if face_bbox is None else face_bbox[3] - face_bbox[1]
    readable_geometry = (
        face_width >= 4
        and face_height >= 5
        and len(audited_skin) >= 8
        and face_contrast >= 18
        and len(natural_dark_features | eye) >= 1
    )
    minimal_feature_set = (
        readable_geometry
        and skin_locked_features
        and near_white <= max(2, len(audited_skin) // 20)
    )
    single_eye_only = False
    return {
        "body_bbox": list(body),
        "face_window": [x0, y0, x1, y1],
        "face_skin_pixels": len(face_component - semantic),
        "face_skin_bbox": list(face_bbox) if face_bbox else None,
        "eye_pixels": len(eye),
        "eye_positions": [list(point) for point in ordered_eye],
        "pupil_pixels": len(pupil),
        "pupil_positions": [list(point) for point in sorted(pupil)],
        "iris_pixels": len(iris),
        "iris_positions": [list(point) for point in sorted(iris)],
        "eye_component_count": len(eye_components),
        "eye_shape_valid": paired_eye_shape or (not eye and bool(natural_dark_features)),
        "nose_pixels": len(nose),
        "nose_positions": [list(point) for point in ordered_nose],
        "mouth_pixels": len(mouth),
        "mouth_positions": [list(point) for point in ordered_mouth],
        "mouth_component_count": len(mouth_components),
        "mouth_shape_valid": mouth_shape,
        "semantic_feature_pixels": len(semantic),
        "semantic_feature_bbox": list(feature_bbox) if feature_bbox else None,
        "feature_order": feature_order,
        "compact_feature_bbox": compact_feature_bbox,
        "skin_locked_features": skin_locked_features,
        "minimal_feature_set": minimal_feature_set,
        "single_eye_only": single_eye_only,
        "toned_skin_pixels": toned_skin,
        "bright_face_skin_pixels": bright_face_skin,
        "max_face_skin_luminance": (
            round(max(audited_luminance), 3) if audited_luminance else 0.0
        ),
        "near_white_pixels": near_white,
        "natural_dark_feature_pixels": len(natural_dark_features),
        "natural_dark_feature_positions": [list(point) for point in sorted(natural_dark_features)],
        "face_contrast": round(face_contrast, 3),
        "red_mask_pixels": len(red_mask),
        "red_mask_bbox": list(_component_bbox(red_mask)) if red_mask else None,
        "retired_template_pixels": retired_pixels,
    }


def yone_face_readability(
    image: Image.Image,
    window: FaceWindow = YONE_ACTOR_FACE_WINDOW,
) -> dict[str, Any]:
    """Measure the actual local face cue, not upper-body skin/chest pixels."""

    return _minimal_yone_face_metrics(image, window)


def _marker_boxes(
    image: Image.Image,
    colors: tuple[int, int, int, int] | set[tuple[int, int, int, int]],
) -> list[tuple[int, int, int, int]]:
    palette = {colors} if isinstance(colors, tuple) else colors
    points = {
        (x, y)
        for y in range(image.height)
        for x in range(image.width)
        if image.getpixel((x, y)) in palette
    }
    return sorted(
        (_component_bbox(component) for component in _point_components(points)),
        key=lambda box: (box[1], box[0]),
    )


def _point_mask(
    size: tuple[int, int],
    points: Iterable[tuple[int, int]],
) -> Image.Image:
    mask = Image.new("L", size, 0)
    for point in points:
        mask.putpixel(point, 255)
    return mask


def _scaled_minimal_face_metrics(
    source: Image.Image,
    rendered: Image.Image,
    *,
    minimum_marker_span: int | None = None,
    maximum_marker_span: int | None = None,
) -> dict[str, Any]:
    source_quality = yone_face_readability(source)
    # Keep recording geometry even when one fast 3/4 run phase naturally hides
    # its eye under the fringe. Callers enforce the stricter idle contract and
    # allow at most one explicitly audited occluded profile in the run loop.
    eye_palette = {YONE_IMAGEGEN_EYE_RGBA, YONE_IMAGEGEN_IRIS_RGBA}
    eye_boxes = _marker_boxes(rendered, eye_palette)
    pupil_boxes = _marker_boxes(rendered, YONE_IMAGEGEN_EYE_RGBA)
    iris_boxes = _marker_boxes(rendered, YONE_IMAGEGEN_IRIS_RGBA)
    nose_boxes = _marker_boxes(rendered, YONE_IMAGEGEN_NOSE_RGBA)
    mouth_boxes = _marker_boxes(rendered, YONE_IMAGEGEN_MOUTH_RGBA)

    source_groups = {
        "eye": {tuple(point) for point in source_quality["eye_positions"]},
        "nose": {tuple(point) for point in source_quality["nose_positions"]},
        "mouth": {tuple(point) for point in source_quality["mouth_positions"]},
    }
    rendered_palettes = {
        "eye": eye_palette,
        "nose": {YONE_IMAGEGEN_NOSE_RGBA},
        "mouth": {YONE_IMAGEGEN_MOUTH_RGBA},
    }
    marker_projection_valid = True
    for name, source_points in source_groups.items():
        if not source_points:
            continue
        projected = _point_mask(source.size, source_points).resize(
            rendered.size,
            Image.Resampling.NEAREST,
        )
        actual_points = {
            (x, y)
            for y in range(rendered.height)
            for x in range(rendered.width)
            if rendered.getpixel((x, y)) in rendered_palettes[name]
        }
        actual = _point_mask(rendered.size, actual_points)
        marker_projection_valid &= projected.tobytes() == actual.tobytes()

    has_semantic_markers = any(source_groups.values())
    if has_semantic_markers:
        marker_projection_valid &= (
            len(eye_boxes) == 2
            and len(pupil_boxes) == 2
            and len(iris_boxes) == 2
            and len(nose_boxes) == 1
            and len(mouth_boxes) == 1
        )
        rendered_feature_order = (
            marker_projection_valid
            and max(box[1] for box in eye_boxes) < nose_boxes[0][1] < mouth_boxes[0][1]
        )
    else:
        rendered_feature_order = True

    try:
        source_face_component, _source_face_bbox = _locate_yone_face_component(
            source,
            YONE_ACTOR_FACE_WINDOW,
            None,
        )
    except ValueError:
        source_face_component = set()
    face_mask = Image.new("L", source.size, 0)
    for point in source_face_component:
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
    max_row_fill_ratio = 0.0
    if rendered_face_bbox is not None:
        face_width = rendered_face_bbox[2] - rendered_face_bbox[0]
        for y in range(rendered_face_bbox[1], rendered_face_bbox[3]):
            occupied = sum(
                1
                for x in range(rendered_face_bbox[0], rendered_face_bbox[2])
                if rendered_face_mask.getpixel((x, y))
            )
            max_row_fill_ratio = max(max_row_fill_ratio, occupied / max(1, face_width))
    return {
        "eye_component_boxes": [list(box) for box in eye_boxes],
        "pupil_component_boxes": [list(box) for box in pupil_boxes],
        "iris_component_boxes": [list(box) for box in iris_boxes],
        "nose_component_boxes": [list(box) for box in nose_boxes],
        "mouth_component_boxes": [list(box) for box in mouth_boxes],
        "marker_projection_valid": marker_projection_valid,
        # Retain the public QA key while changing it from a brittle fixed-span
        # assertion to exact nearest-neighbour mask projection.
        "marker_spans_valid": marker_projection_valid,
        "rendered_feature_order": rendered_feature_order,
        "source_face_skin_bbox": source_quality["face_skin_bbox"],
        "rendered_face_skin_bbox": list(rendered_face_bbox) if rendered_face_bbox else None,
        "rendered_face_skin_pixels": rendered_face_pixels,
        "max_face_row_fill_ratio": round(max_row_fill_ratio, 4),
        "source_toned_skin_pixels": source_quality["toned_skin_pixels"],
        "source_bright_face_skin_pixels": source_quality["bright_face_skin_pixels"],
        "source_max_face_skin_luminance": source_quality["max_face_skin_luminance"],
        "source_near_white_pixels": source_quality["near_white_pixels"],
        "source_face_contrast": source_quality["face_contrast"],
        "source_natural_dark_feature_pixels": source_quality["natural_dark_feature_pixels"],
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
        **_scaled_minimal_face_metrics(
            source,
            rendered,
            minimum_marker_span=1,
            maximum_marker_span=2,
        ),
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


def finalize_yone_battle_face(
    image: Image.Image,
    frame_key: tuple[str, int],
) -> Image.Image:
    """Finish one native battle face without changing its source silhouette."""

    classified = (
        YONE_FRONT_FACE_FRAMES
        | YONE_PROFILE_FACE_FRAMES
        | YONE_SINGLE_EYE_PROFILE_FRAMES
    )
    if frame_key not in classified:
        raise ValueError(f"Yone {frame_key} has no reviewed face-pose assignment")
    variant = "front" if frame_key in YONE_FRONT_FACE_FRAMES else "profile"
    alpha_before = image.convert("RGBA").getchannel("A").tobytes()
    live_recipe = YONE_LIVE_IDLE_FACE_RECIPES.get(frame_key)
    try:
        output = repaint_yone_face(
            image,
            preferred_eye=YONE_FACE_EYE_OVERRIDES.get(frame_key),
            variant=variant,
            allow_single_eye=frame_key in YONE_SINGLE_EYE_PROFILE_FRAMES,
            safe_y=(None if live_recipe is None else live_recipe["safe_y"]),
            landmarks=live_recipe,
        )
    except ValueError as exc:
        raise ValueError(f"Yone {frame_key} face repair failed: {exc}") from exc
    if output.getchannel("A").tobytes() != alpha_before:
        raise ValueError(f"Yone {frame_key} face repair changed alpha geometry")
    quality = yone_face_readability(output)
    accepted = (
        quality["single_eye_only"]
        if frame_key in YONE_SINGLE_EYE_PROFILE_FRAMES
        else quality["minimal_feature_set"]
    )
    if not accepted or not quality["skin_locked_features"]:
        raise ValueError(f"Yone {frame_key} source-preserving face repair failed: {quality}")
    return output


YONE_IMAGEGEN_EYE_RGBA = (26, 15, 20, 255)
YONE_IMAGEGEN_IRIS_RGBA = (216, 154, 102, 255)
YONE_IMAGEGEN_NOSE_RGBA = (145, 78, 62, 255)
YONE_IMAGEGEN_MOUTH_RGBA = (79, 27, 34, 255)
YONE_IMAGEGEN_FACE_MID_RGBA = (181, 109, 81, 255)
YONE_IMAGEGEN_FACE_LIGHT_RGBA = (203, 136, 98, 255)


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


def fit_actor(
    source: Image.Image,
    frame_size: tuple[int, int],
    target_height: int,
    bottom_margin: int,
    frame_key: tuple[str, int],
) -> Image.Image:
    return fit_subject(
        source,
        frame_size,
        max_subject=(max(1, frame_size[0] - 2), min(target_height, frame_size[1] - bottom_margin - 1)),
        anchor_bottom=frame_size[1] - bottom_margin,
        colors=48,
        # The accepted adult model is authored from hard pixel clusters. BOX
        # averaged its tiny 3/4-view eye and jaw into a muddy face, while the
        # same nearest-neighbour route used by the live card preserves them.
        resampling=Image.Resampling.NEAREST,
        component_minimum=24,
        final_component_minimum=3,
    )


def add_yone_w_weapon_pose(
    frame: Image.Image,
    pose_index: int,
    body_origin: tuple[int, int],
) -> Image.Image:
    """Animate W's forearm/azakana blade without moving the planted body."""

    output = frame.copy()
    draw = ImageDraw.Draw(output)
    body_x, body_y = body_origin
    shoulder = (body_x + 14, body_y + 13)
    pivots = (
        (body_x + 23, body_y + 15),
        (body_x + 23, body_y + 13),
        (body_x + 23, body_y + 14),
        (body_x + 23, body_y + 16),
        (body_x + 23, body_y + 18),
    )
    endpoints = (
        (body_x - 2, body_y + 5),
        (body_x - 1, max(1, body_y - 2)),
        (frame.width - 4, body_y + 7),
        (frame.width - 3, body_y + 18),
        (frame.width - 5, min(frame.height - 4, body_y + 31)),
    )
    pivot = pivots[pose_index]
    endpoint = endpoints[pose_index]

    arm_outline = (35, 25, 31, 255)
    arm_mid = (151, 89, 73, 255)
    blade_outline = (35, 8, 16, 255)
    blade_red = (198, 25, 29, 255)
    blade_light = (244, 65, 48, 255)
    draw.line((shoulder, pivot), fill=arm_outline, width=3)
    draw.line((shoulder, pivot), fill=arm_mid, width=1)
    draw.line((pivot, endpoint), fill=blade_outline, width=3)
    draw.line((pivot, endpoint), fill=blade_red, width=1)
    highlight_end = (
        endpoint[0] - (1 if endpoint[0] >= pivot[0] else -1),
        endpoint[1],
    )
    draw.line((pivot, highlight_end), fill=blade_light, width=1)
    draw.rectangle(
        (pivot[0] - 1, pivot[1] - 1, pivot[0] + 1, pivot[1] + 1),
        fill=blade_outline,
    )
    draw.point(pivot, fill=(214, 160, 92, 255))
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

    # The rebuilt ImageGen model keeps every pose inside its own grid cell.
    # Do not apply the retired component-centroid salvage from the old sheet.
    attack_sources = core[5:10]
    # Q/W have three 31px-wide native windup slots.  Crop only the long sword
    # reach from the new neutral master so the rebuilt head, torso and feet can
    # retain their normal height instead of shrinking with the blade tips.
    narrow_guard = trim_actor_width(core[0], 0.52)

    body_sequences: dict[str, list[Image.Image]] = {
        # Use the same accepted neutral model in all four idle slots.  The
        # generated alternates carry different sword reach and would shrink
        # the body in the fixed 43px native cell, causing card-scale jitter.
        "idle": [core[0], core[0], core[0], core[0]],
        "hit": [core[4]],
        "attack": [*attack_sources, core[19]],
        "run": run,
        # The first three native Q windup slots are only 31px wide.  Use
        # clean narrow guard/thrust poses instead of shrinking a long blade
        # and leaving detached tip pixels inside the actor atlas.
        "skill": [
            narrow_guard,
            narrow_guard,
            narrow_guard,
            *core[13:17],
        ],
        "skill2": [narrow_guard],
        "skill2_dash": [wr[5]],
        # W is a planted dual-blade sweep. Reuse one reviewed upright guard
        # source so feet, torso and face cannot jump between incompatible
        # lunge/crouch poses. A final 1x forearm/azakana overlay below supplies
        # guard -> windup -> impact -> recovery motion while the independent
        # crescent sheet carries the broad sweep.
        "skill2_attack": [
            narrow_guard,
            narrow_guard,
            narrow_guard,
            narrow_guard,
            narrow_guard,
        ],
        # The generated wr[13] overhead pose is wider than the native ult[6]
        # rectangle and would shrink the whole body. Reuse the adjacent
        # airborne cross-slash phase here; the independent R sheet carries the
        # large slash while the actor retains a stable 37-38px scale.
        "ult": [*wr[7:13], wr[12], *wr[14:20]],
    }

    sheet = Image.new("RGBA", ACTOR_SHEET_SIZE, (0, 0, 0, 0))
    placements: dict[tuple[int, int, int, int], bytes] = {}
    # Pack W from one already-finished 1x pixel subject. Re-running the same
    # source through five slightly different native rectangles made the face
    # component detector choose different skin clusters and produced a 6px
    # apparent vertical jump. A single final-scale subject preserves every
    # facial/body pixel; only transparent padding changes per native slot.
    # Build against the narrowest native W slot so the same rebuilt body can
    # be centered in all five rectangles without cropping feet or head.
    w_master_rect = NATIVE_CONTRACT["skill2_attack"]["rects"][0]
    w_master = fit_actor(
        body_sequences["skill2_attack"][0],
        (w_master_rect[2], w_master_rect[3]),
        BODY_TARGET_HEIGHTS["skill2_attack"][0],
        BODY_BOTTOM_MARGINS["skill2_attack"][0],
        ("skill2_attack", 0),
    )
    w_master_subject = w_master.crop(alpha_bbox(w_master))
    for tag in ("idle", "run", "attack", "hit", "skill", "skill2", "skill2_dash", "skill2_attack", "ult"):
        sources = body_sequences[tag]
        rects = NATIVE_CONTRACT[tag]["rects"]
        heights = BODY_TARGET_HEIGHTS[tag]
        bottoms = BODY_BOTTOM_MARGINS[tag]
        if not (len(sources) == len(rects) == len(heights) == len(bottoms)):
            raise ValueError(f"Yone {tag}: {len(sources)} source poses for {len(rects)} frames")
        if tag == "skill2_attack":
            for index, rect in enumerate(rects):
                frame = Image.new("RGBA", (rect[2], rect[3]), (0, 0, 0, 0))
                x = (rect[2] - w_master_subject.width) // 2
                y = (
                    rect[3]
                    - BODY_BOTTOM_MARGINS["skill2_attack"][index]
                    - w_master_subject.height
                )
                if x < 0 or y < 0:
                    raise ValueError(
                        f"Yone planted W subject {w_master_subject.size} does not fit {rect}"
                    )
                frame = add_yone_w_weapon_pose(frame, index, (x, y))
                # The planted body is composited last so the animated rear
                # azakana blade can never paint across Yone's face or torso.
                frame.alpha_composite(w_master_subject, (x, y))
                _paste_unique(sheet, placements, rect, frame)
            continue
        for index, (source, rect, height, bottom) in enumerate(
            zip(sources, rects, heights, bottoms, strict=True)
        ):
            _paste_unique(
                sheet,
                placements,
                rect,
                fit_actor(
                    source,
                    (rect[2], rect[3]),
                    height,
                    bottom,
                    (tag, index),
                ),
            )

    # Official hit_effect_area aliases ult[1:12]; assigning the same bytes is
    # deliberate and proves the overlap remains contract-safe.
    for source_rect, alias_rect in zip(NATIVE_CONTRACT["ult"]["rects"][1:12], NATIVE_CONTRACT["hit_effect_area"]["rects"], strict=True):
        if source_rect != alias_rect:
            raise ValueError("Dual Blader ult/hit_effect_area alias contract changed")

    # Eight generated fall/ground poses feed the eight visible dead frames;
    # the mandatory final 3x3 terminal frame remains transparent.
    for index, (source, rect, bottom) in enumerate(
        zip(
            defeat,
            NATIVE_CONTRACT["dead"]["rects"][:-1],
            DEAD_BOTTOM_MARGINS,
            strict=True,
        )
    ):
        target = min(37, rect[3] - bottom - 1)
        _paste_unique(
            sheet,
            placements,
            rect,
            fit_actor(
                source,
                (rect[2], rect[3]),
                target,
                bottom,
                ("dead", index),
            ),
        )

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


def retouch_yone_ui_surface(image: Image.Image, surface: str) -> Image.Image:
    recipe = YONE_UI_FACE_RECIPES.get(surface)
    if recipe is None:
        raise ValueError(f"Unknown Yone UI face surface: {surface}")
    before = image.convert("RGBA")
    output = repaint_yone_face(
        before,
        recipe["window"],
        preferred_eye=recipe["eye"],
        variant="front",
        safe_y=recipe.get("safe_y"),
        landmarks=recipe.get("landmarks"),
        max_toned_skin=recipe["tones"],
        max_retouch_pixels=recipe["budget"],
    )
    if output.getchannel("A").tobytes() != before.getchannel("A").tobytes():
        raise ValueError(f"Yone {surface} retouch changed UI alpha geometry")
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
                "policy": "complete adult-proportioned ImageGen body-model replacement with a source-authored 3/4-view face and NEAREST native sampling; no post-scale face repaint or synthetic feature overlay",
                "body_source_paths": [
                    CORE_SOURCE.relative_to(MOD_ROOT).as_posix(),
                    RUN_SOURCE.relative_to(MOD_ROOT).as_posix(),
                    WR_BODY_SOURCE.relative_to(MOD_ROOT).as_posix(),
                    DEFEAT_SOURCE.relative_to(MOD_ROOT).as_posix(),
                ],
                "actor_resampling": "NEAREST",
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
            "processing": "four complete ImageGen adult body contact-sheet replacements, deterministic green-screen soft matte/despill, hard-alpha packing, NEAREST native actor sampling with no face repaint, and official Dual Blader foot baselines",
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
        "- [x] The retired Yone body model was replaced end-to-end with four new ImageGen contact sheets (core, run, Q/W/R body and defeat); Q/W/R effect sheets remain unchanged.\n"
        "- [x] The new adult-proportioned natural 3/4 face is packed with NEAREST sampling, preserving the source eye, jaw and hair pixels without any post-scale face repaint.\n"
        "- [x] Idle/run/attack/hit keep the official Dual Blader bottom clearances, and the card/BP center camera is raised to y=-16 so legs and weapons keep a visible gap above the black divider.\n"
        "- [x] Q3 uses a dedicated horizontal tornado, a vertical blue-white airborne cue, and a small ready-wind state.\n"
        "- [x] Active champion data and release resources do not reference Soul Unbound. Exactly five retired Yone E names plus two retired Shen dash names remain registered only as no-op saved-season compatibility aliases.\n"
        "- [x] W has no process-global ledger: one native callback scans only its current `GameCtx`, resolves an 80-degree forward cone, damages that snapshot, counts champion hits, and emits one shield tier marker.\n"
        "- [x] W keeps Yone planted, plays one full caster-following crescent, and reuses one final-scale actor subject across all five native frames so transparent padding cannot create an E-like body jump.\n"
        "- [x] Minions and monsters qualify for the base shield; every enemy champion hit increases its tier through the normal five-champion team limit.\n"
        "- [x] W has no dash, spirit clone, anchor, tether, forced return, recall override, or teleport path.\n"
        "- [x] Compact portrait is face-focused with transparent safety margins.\n"
        "- [x] QA replays the user's exact idle[0] 2.2x nearest-neighbor actor path, compares all idle/run frames, rejects near-white face blocks, and preserves source foot/card-bottom clearances.\n"
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
            if actual_bottom != expected_bottom or (
                tag != "skill2_attack" and actual_bottom < 4
            ):
                raise ValueError(f"Yone {tag}[{index}] bottom anchor {actual_bottom} != {expected_bottom}")
            visible_height = bbox[3] - bbox[1]
            if visible_height < max(24, target_height - 6):
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

    w_pose_hashes: set[str] = set()
    normalized_w_frames: list[Image.Image] = []
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
        normalized = Image.new("RGBA", (61, 55), (0, 0, 0, 0))
        normalized.alpha_composite(
            frame,
            ((61 - data["w"]) // 2, (55 - data["h"]) // 2),
        )
        normalized_w_frames.append(normalized)
        w_pose_hashes.add(hashlib.sha256(normalized.tobytes()).hexdigest())
    if len(w_pose_hashes) < 3:
        raise ValueError("Yone W must show at least three forearm/blade poses")
    # The planted actor is composited from one final-scale subject. Isolate the
    # pixels that are byte-identical in all five normalized W frames; this
    # proves the body/head pivot directly without letting the changing blade
    # widen the face detector's relative search window.
    common_w_body = normalized_w_frames[0].copy()
    for y in range(common_w_body.height):
        for x in range(common_w_body.width):
            pixel = common_w_body.getpixel((x, y))
            if pixel[3] < 128 or any(
                frame.getpixel((x, y)) != pixel for frame in normalized_w_frames[1:]
            ):
                common_w_body.putpixel((x, y), (0, 0, 0, 0))
    common_bbox = common_w_body.getchannel("A").getbbox()
    common_face = yone_face_readability(common_w_body)
    if (
        common_bbox is None
        or common_bbox[3] - common_bbox[1] < 30
        or common_face["face_skin_bbox"] is None
        or common_face["face_contrast"] < 18
        or common_face["natural_dark_feature_pixels"] < 1
    ):
        raise ValueError(
            f"Yone planted W body/face is not stable: bbox={common_bbox}, face={common_face}"
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
    occluded_run_profiles = 0
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
            if face["red_mask_pixels"] < 10:
                raise ValueError(f"Yone dead[{index}] lost the rebuilt mask silhouette: {face}")
            continue
        if tag == "skill2_attack":
            # W uses one byte-identical planted body under five changing blade
            # silhouettes. The normalized common-body audit above validates
            # its actual face; per-frame relative windows can lock onto the
            # animated forearm when the blade widens the alpha bbox.
            continue
        face_bbox = face["face_skin_bbox"]
        profile_face = (
            tag == "run"
            and face_bbox is not None
            and face_bbox[2] - face_bbox[0] >= 3
            and face_bbox[3] - face_bbox[1] >= 5
            and face["face_skin_pixels"] >= 8
            and face["face_contrast"] >= 30
            and face["red_mask_pixels"] >= 20
            and face["near_white_pixels"] <= 2
        )
        if not face["minimal_feature_set"] and profile_face:
            occluded_run_profiles += 1
        elif (
            not face["minimal_feature_set"]
            or not face["skin_locked_features"]
            or face_bbox is None
            or face["near_white_pixels"] > max(2, face["face_skin_pixels"] // 20)
        ):
            raise ValueError(f"Yone {tag}[{index}] face is not readable: {face}")
    if face_frame_count != 54:
        raise ValueError(f"Yone face validation covered {face_frame_count}/54 frames")
    if occluded_run_profiles > 1:
        raise ValueError(
            f"Yone run loop has {occluded_run_profiles} eye-occluded profiles; expected at most one"
        )

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
            quality["marker_spans_valid"]
            and quality["marker_projection_valid"]
            and quality["rendered_feature_order"]
            and quality["source_face_skin_bbox"] is not None
            and quality["rendered_face_skin_bbox"] is not None
            and quality["source_toned_skin_pixels"] <= YONE_FACE_MAX_TONED_SKIN
            and quality["source_near_white_pixels"] <= 1
            and quality["source_natural_dark_feature_pixels"] >= 1
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
            and quality["source_face_contrast"] >= 30
            and quality["source_red_mask_pixels"] >= 20
            and quality["source_near_white_pixels"] <= 2
        )
        if quality["source_natural_dark_feature_pixels"] >= 1:
            readable_run_eye_cues += 1
        if (
            quality["face_variant"] != "profile"
            or not quality["marker_spans_valid"]
            or not quality["marker_projection_valid"]
            or not quality["rendered_feature_order"]
            or not profile_geometry
            or quality["source_toned_skin_pixels"] > YONE_FACE_MAX_TONED_SKIN
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
        recipe = YONE_UI_FACE_RECIPES[label]
        face = yone_face_readability(image, recipe["window"])
        if (
            not face["minimal_feature_set"]
            or not face["skin_locked_features"]
            or face["face_skin_bbox"] is None
            or face["near_white_pixels"] > max(2, face["face_skin_pixels"] // 20)
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
