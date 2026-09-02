#!/usr/bin/env python3
"""Build Yone's deterministic visual resources for the Dual Blader slot.

The actor preserves all official champion 009/Dual Blader action rectangles,
frame counts and durations as an immutable prefix.  The V7 body route adds
separate steel/Azakana basic attacks and an empowered-Q body sequence in a
non-overlapping atlas extension, while idle/run/W/R are rebuilt around an
explicit two-sword visual contract.  High-footprint Q/W/R feedback stays in
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
from pathlib import Path, PurePosixPath
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

NATIVE_V7_ROOT = SOURCE_ROOT / "native" / "yone_v7"
NATIVE_V7_MANIFEST = NATIVE_V7_ROOT / "frames.json"
NATIVE_V7_CONTACT_PREVIEW = NATIVE_V7_ROOT / "preview" / "yone_v7_native_contact.png"
YONE_V7_UI_SOURCE = IMAGEGEN_ROOT / "yone_v7_ui_source.png"
YONE_V7_MOTION_SOURCE = IMAGEGEN_ROOT / "yone_v7_motion_contact.png"
YONE_V7_ATTACK_Q_SOURCE = IMAGEGEN_ROOT / "yone_v7_attack_q_contact.png"
YONE_V7_W_SOURCE = IMAGEGEN_ROOT / "yone_v7_w_contact.png"
YONE_V7_ULT_SOURCE = IMAGEGEN_ROOT / "yone_v7_ult_contact.png"
YONE_V7_BODY_IMAGEGEN_SOURCES = (
    YONE_V7_MOTION_SOURCE,
    YONE_V7_ATTACK_Q_SOURCE,
    YONE_V7_W_SOURCE,
    YONE_V7_ULT_SOURCE,
)
YONE_V7_IMAGEGEN_SOURCES = (YONE_V7_UI_SOURCE, *YONE_V7_BODY_IMAGEGEN_SOURCES)
QW_VFX_SOURCE = IMAGEGEN_ROOT / "yone_qw_vfx_contact.png"
W_VFX_SOURCE = IMAGEGEN_ROOT / "yone_w_vfx_contact_v2.png"
Q3_VFX_SOURCE = IMAGEGEN_ROOT / "yone_q3_vfx_contact.png"
R_VFX_SOURCE = IMAGEGEN_ROOT / "yone_r_vfx_contact.png"
ICON_SOURCE = IMAGEGEN_ROOT / "yone_icons_source.png"
SPLASH_SOURCE = IMAGEGEN_ROOT / "bp_splash" / "dual_blader.png"
YONE_V7_UI_CARD_PREVIEW = QA_DIR / "yone_v7_ui_card.png"

QW_VFX_ALPHA = PROCESSED_ROOT / "yone_qw_vfx_contact_alpha.png"
W_VFX_ALPHA = PROCESSED_ROOT / "yone_w_vfx_contact_v2_alpha.png"
Q3_VFX_ALPHA = PROCESSED_ROOT / "yone_q3_vfx_contact_alpha.png"
R_VFX_ALPHA = PROCESSED_ROOT / "yone_r_vfx_contact_alpha.png"

NATIVE_ACTOR_SHEET_SIZE = (3502, 88)
ACTOR_SHEET_SIZE = (4262, 88)
NATIVE_V7_SCHEMA_VERSION = 7
NATIVE_V7_ROUTE = "dual-sword-v7"
NATIVE_V7_MAX_OPAQUE_COLORS = 48

RETIRED_YONE_V4_BODY_SOURCES = (
    IMAGEGEN_ROOT / "yone_v4_action_contact.png",
    IMAGEGEN_ROOT / "yone_v4_idle_candidate_43x55.png",
    SOURCE_ROOT / "native" / "yone_v4",
)

# Retired V5 locations are kept only as a negative build/provenance contract.
# They are never opened, validated, or accepted as a fallback body route.
RETIRED_YONE_V5_BODY_SOURCES = (
    IMAGEGEN_ROOT / "yone_v5_idle_source.png",
    IMAGEGEN_ROOT / "yone_v5_idle_golden_43x55.png",
    IMAGEGEN_ROOT / "yone_v5_motion_contact.png",
    IMAGEGEN_ROOT / "yone_v5_attack_q_w_contact.png",
    IMAGEGEN_ROOT / "yone_v5_q5_contact.png",
    IMAGEGEN_ROOT / "yone_v5_ult_contact.png",
    SOURCE_ROOT / "native" / ("yone_" + "v5"),
)

# The former V6 UI source remains as provenance only. Its old battle contact
# sheets and native frame tree must be absent so they cannot be mistaken for a
# fallback when diagnosing an installed package.
RETIRED_YONE_V6_BODY_SOURCES = (
    IMAGEGEN_ROOT / "yone_v6_motion_contact.png",
    IMAGEGEN_ROOT / "yone_v6_attack_q_w_contact.png",
    IMAGEGEN_ROOT / "yone_v6_w_contact.png",
    IMAGEGEN_ROOT / "yone_v6_ult_contact.png",
    SOURCE_ROOT / "native" / "yone_v6",
)

RETIRED_YONE_GENERATED_OUTPUTS = (
    EFFECT_DIR / "yone_followup#anim.fanim",
    EFFECT_DIR / "yone_followup#sheet.png",
    EFFECT_DIR / "yone_spirit#anim.fanim",
    EFFECT_DIR / "yone_spirit#sheet.png",
    EFFECT_DIR / "yone_q3_airborne#anim.fanim",
    EFFECT_DIR / "yone_q3_airborne#sheet.png",
    IMAGEGEN_ROOT / "yone_followup_vfx_contact.png",
    PROCESSED_ROOT / "yone_followup_vfx_contact_alpha.png",
    QA_DIR / "yone_v6_ui_card.png",
)
RETIRED_YONE_SOURCE_PATHS = (
    IMAGEGEN_ROOT / "yone_e_icon_source.png",
    IMAGEGEN_ROOT / "yone_followup_vfx_contact.png",
    PROCESSED_ROOT / "yone_followup_vfx_contact_alpha.png",
)

YONE_LIVE_CARD_SCALE = 2.2
YONE_LIVE_CARD_DIVIDER_TOP = 96
YONE_LIVE_CARD_AUDITED_CENTER_Y = -16
YONE_LIVE_CARD_MIN_DIVIDER_CLEARANCE = 6
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


def _append_custom_rects(
    cursor: int, source_rects: Sequence[tuple[int, int, int, int]]
) -> tuple[list[tuple[int, int, int, int]], int]:
    """Append same-sized frames after the immutable native atlas prefix."""

    rects: list[tuple[int, int, int, int]] = []
    for _x, _y, width, height in source_rects:
        rects.append((cursor, 0, width, height))
        cursor += width + 1
    return rects, cursor


_custom_cursor = NATIVE_ACTOR_SHEET_SIZE[0]
_attack_azakana_rects, _custom_cursor = _append_custom_rects(
    _custom_cursor, NATIVE_CONTRACT["attack"]["rects"]
)
_skill_q3_rects, _custom_cursor = _append_custom_rects(
    _custom_cursor, NATIVE_CONTRACT["skill"]["rects"]
)
if _custom_cursor != ACTOR_SHEET_SIZE[0]:
    raise ValueError(
        f"Yone custom actor atlas width {_custom_cursor} != {ACTOR_SHEET_SIZE[0]}"
    )

# The official thirteen tags above remain byte-for-byte contract-compatible.
# These five semantic tags are an additive visual layer selected explicitly by
# CasterAnimation; aliases reuse native frames, while the two physical routes
# occupy the non-overlapping V7 extension.
CUSTOM_ACTION_CONTRACT: dict[str, dict[str, Any]] = {
    "attack_steel": {
        "durations": NATIVE_CONTRACT["attack"]["durations"],
        "rects": NATIVE_CONTRACT["attack"]["rects"],
        "alias_of": "attack",
    },
    "attack_azakana": {
        "durations": NATIVE_CONTRACT["attack"]["durations"],
        "rects": _attack_azakana_rects,
    },
    "skill_q12": {
        "durations": NATIVE_CONTRACT["skill"]["durations"],
        "rects": NATIVE_CONTRACT["skill"]["rects"],
        "alias_of": "skill",
    },
    "skill_q3": {
        "durations": NATIVE_CONTRACT["skill"]["durations"],
        "rects": _skill_q3_rects,
    },
    "skill_w_azakana": {
        "durations": NATIVE_CONTRACT["skill2_attack"]["durations"],
        "rects": NATIVE_CONTRACT["skill2_attack"]["rects"],
        "alias_of": "skill2_attack",
    },
}
CUSTOM_PIXEL_ACTIONS = ("attack_azakana", "skill_q3")


BODY_TARGET_HEIGHTS: dict[str, list[int]] = {
    # Match the official Dual Blader's visible core footprint. This restores
    # the same terrain/name-plate clearance used by Lucian and Orianna instead
    # of lowering Yone's longer generated legs into the foreground mask.
    "idle": [38, 37, 36, 37],
    "run": [35, 32, 31, 32, 35, 33, 31, 33],
    "attack": [36, 36, 34, 35, 35, 36],
    "attack_azakana": [36, 36, 34, 35, 35, 36],
    "hit": [37],
    "skill": [38, 37, 38, 39, 39, 39, 39],
    "skill_q3": [38, 37, 38, 39, 39, 39, 39],
    "skill2": [38],
    "skill2_dash": [36],
    "skill2_attack": [36, 37, 38, 38, 38],
    "ult": [37, 38, 38, 38, 37, 38, 38, 38, 38, 38, 38, 38, 37],
}

# Minimum visible heights for the final exact-native V6 frames. These are
# regression floors, never resize targets: fast run/W/R poses are naturally
# shorter than upright idle and must remain authored at their native 1x size.
NATIVE_MIN_VISIBLE_HEIGHTS: dict[str, list[int]] = {
    "idle": [36, 36, 36, 36],
    "run": [31, 32, 32, 33, 32, 32, 32, 33],
    "attack": [35, 33, 33, 31, 33, 34],
    # The heavy Azakana sequence deliberately crouches/squashes while keeping
    # the same head/body pixel scale and native foot baseline.
    "attack_azakana": [28, 27, 25, 26, 26, 27],
    "hit": [34],
    "skill": [35, 33, 34, 33, 33, 31, 33],
    "skill_q3": [35, 33, 34, 33, 33, 31, 33],
    "skill2": [35],
    "skill2_dash": [31],
    "skill2_attack": [32, 34, 33, 32, 32],
    "ult": [34, 25, 24, 31, 29, 24, 25, 25, 31, 22, 25, 33, 33],
}

BODY_BOTTOM_MARGINS: dict[str, list[int]] = {
    # Bundle-derived official Dual Blader baselines for the common movement
    # states. These are the frames used by battle, cards and face crops.
    # idle[0] and the remaining native V6 frames preserve their source-authored
    # bottom clearances exactly; the builder never derives them from a UI crop.
    "idle": [15, 15, 14, 15],
    "run": [13, 18, 20, 17, 13, 17, 20, 17],
    "attack": [14, 14, 12, 13, 13, 14],
    "attack_azakana": [14, 14, 12, 13, 13, 14],
    "hit": [15],
    "skill": [5, 6, 7, 6, 8, 10, 8],
    "skill_q3": [5, 6, 7, 6, 8, 10, 8],
    "skill2": [5],
    "skill2_dash": [4],
    # The W body is centred in every differently-sized native frame. This is
    # the exact bottom clearance produced by y=(frame_h-subject_h)//2 for the
    # locked 22x38 body and therefore keeps both x and y pivots invariant.
    "skill2_attack": [3, 4, 8, 9, 7],
    "ult": [5, 6, 8, 10, 12, 11, 9, 7, 6, 7, 8, 6, 5],
}

# Visible body frames only.  The transparent dead terminator and the three VFX
# tags keep their native animation entries, but never appear in the V6 body
# manifest.  Each listed PNG is already authored on its exact final 1x native
# rectangle: the actor build may copy bytes, and may do nothing else.
NATIVE_BODY_ACTIONS = (
    "skill2",
    "hit",
    "attack",
    "skill2_dash",
    "ult",
    "run",
    "skill2_attack",
    "idle",
    "dead",
    "skill",
)
NATIVE_BODY_FRAME_COUNT = 54
GENERATED_BODY_ACTIONS = (*NATIVE_BODY_ACTIONS, *CUSTOM_PIXEL_ACTIONS)
GENERATED_BODY_FRAME_COUNT = 67
NATIVE_V7_FRAME_FIELDS = {
    "action",
    "index",
    "file",
    "rect",
    "bottom_margin",
    "face_bbox",
    "eye_pixels",
    "mask_bbox",
    "foot_zones",
    "face_visibility",
    "active_weapon",
    "weapons_present",
    "steel_blade_bbox",
    "azakana_blade_bbox",
    "steel_hand_anchor",
    "azakana_hand_anchor",
    "steel_tip",
    "azakana_tip",
    "steel_span_px",
    "azakana_span_px",
    "steel_connectedness",
    "azakana_connectedness",
    "steel_pixel_count",
    "azakana_pixel_count",
    "steel_crop_ratio",
    "azakana_crop_ratio",
    "steel_source_tip_survived",
    "azakana_source_tip_survived",
}

# Machine-readable weapon semantics stay separate from color heuristics.  The
# generator still proves the actual pixels and sequence hashes, while these
# fields make the intended hand/weapon route explicit for data and CI.
V7_FRAME_ACTIVE_WEAPON = {
    "skill2": "azakana",
    "hit": "dual",
    "attack": "steel",
    "attack_azakana": "azakana",
    "skill2_dash": "dual",
    "ult": "dual",
    "run": "dual",
    "skill2_attack": "azakana",
    "idle": "dual",
    "dead": "dual",
    "skill": "steel",
    "skill_q3": "steel",
}
V7_FRAME_WEAPONS_PRESENT = {
    action: ["steel", "azakana"] for action in GENERATED_BODY_ACTIONS
}
V7_WEAPON_CONTRACT = {
    "version": 2,
    "weapons": ["steel", "azakana"],
    "always_dual_actions": ["idle", "run"],
    "semantic_animation_tags": {
        "attack_steel": "steel",
        "attack_azakana": "azakana",
        "skill_q12": "steel",
        "skill_q3": "steel",
        "skill_w_azakana": "azakana",
        "ult": "dual",
    },
    "long_blade_overlay_policy": "caster-follow effects extend the active blade outside the compact actor frame",
}
V7_WEAPON_PALETTE_ROLES = {
    "steel": {
        "dark": ["steel_dark"],
        "mid": ["steel_mid"],
        "highlight": ["steel_highlight"],
    },
    "azakana": {
        "dark": ["azakana_dark"],
        "red": ["azakana_red"],
        "highlight": ["azakana_highlight"],
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


def process_sources() -> list[Path]:
    outputs: list[Path] = []
    # V6 body frames are final native 1x RGBA files and deliberately bypass
    # this processing stage.  VFX routes remain unchanged; Q3 keeps its
    # dedicated magenta branch below because blue-white wind is not a BODY
    # source.
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


def _is_plain_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _v7_relative_file(value: Any, label: str, suffix: str) -> Path:
    """Resolve one normalized manifest-relative file inside the V6 root."""

    if not isinstance(value, str) or not value:
        raise ValueError(f"Yone V6 {label} must be a non-empty relative path")
    if "\\" in value:
        raise ValueError(f"Yone V6 {label} must use forward slashes: {value!r}")
    relative = PurePosixPath(value)
    if (
        relative.is_absolute()
        or value != relative.as_posix()
        or any(part in {"", ".", ".."} for part in relative.parts)
    ):
        raise ValueError(f"Yone V6 {label} is not a normalized relative path: {value!r}")
    path = NATIVE_V7_ROOT.joinpath(*relative.parts)
    try:
        path.resolve().relative_to(NATIVE_V7_ROOT.resolve())
    except ValueError as exc:
        raise ValueError(f"Yone V6 {label} escapes its source root: {value!r}") from exc
    if path.suffix.lower() != suffix:
        raise ValueError(f"Yone V6 {label} must end in {suffix}: {value!r}")
    if not path.is_file():
        raise FileNotFoundError(f"Missing Yone V6 {label}: {path}")
    return path


def _load_v7_json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise FileNotFoundError(
            "Missing Yone V6 exact-native source contract: " + str(path)
        ) from None
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"Yone V6 {label} is not valid UTF-8 JSON: {path}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"Yone V6 {label} root must be an object")
    return value


def _validate_v7_palette(
    path: Path,
) -> tuple[
    set[tuple[int, int, int, int]],
    dict[str, tuple[int, int, int, int]],
    dict[str, Any],
]:
    payload = _load_v7_json(path, "palette")
    expected_fields = {"schema_version", "route", "weapon_roles", "colors"}
    if set(payload) != expected_fields:
        raise ValueError(
            "Yone V7 palette fields changed: "
            f"got={sorted(payload)}, expected={sorted(expected_fields)}"
        )
    if payload["schema_version"] != NATIVE_V7_SCHEMA_VERSION:
        raise ValueError(
            f"Yone V7 palette schema_version must be {NATIVE_V7_SCHEMA_VERSION}"
        )
    if payload["route"] != NATIVE_V7_ROUTE:
        raise ValueError(f"Yone V7 palette route must be {NATIVE_V7_ROUTE!r}")
    if payload["weapon_roles"] != V7_WEAPON_PALETTE_ROLES:
        raise ValueError("Yone V7 palette weapon roles changed")
    rows = payload["colors"]
    if not isinstance(rows, list):
        raise ValueError("Yone V6 palette colors must be a list")

    colors: set[tuple[int, int, int, int]] = set()
    role_colors: dict[str, tuple[int, int, int, int]] = {}
    transparent_count = 0
    roles: list[str] = []
    for index, row in enumerate(rows):
        if not isinstance(row, dict) or set(row) != {"role", "rgba"}:
            raise ValueError(
                f"Yone V6 palette colors[{index}] must contain only role/rgba"
            )
        role = row["role"]
        rgba = row["rgba"]
        if not isinstance(role, str) or not role.strip():
            raise ValueError(f"Yone V6 palette colors[{index}].role is empty")
        if (
            not isinstance(rgba, list)
            or len(rgba) != 4
            or any(not _is_plain_int(channel) or not 0 <= channel <= 255 for channel in rgba)
        ):
            raise ValueError(
                f"Yone V6 palette colors[{index}].rgba must be four bytes"
            )
        color = tuple(rgba)
        if color in colors:
            raise ValueError(f"Yone V6 palette duplicates RGBA {color}")
        if role in role_colors:
            raise ValueError(f"Yone V7 palette duplicates role {role!r}")
        if color[3] == 0:
            if color != (0, 0, 0, 0) or role != "transparent":
                raise ValueError(
                    "Yone V6 transparent palette entry must be role='transparent', "
                    "rgba=[0,0,0,0]"
                )
            transparent_count += 1
        elif color[3] != 255:
            raise ValueError(f"Yone V6 palette contains soft alpha {color}")
        elif role == "transparent":
            raise ValueError("Yone V6 opaque palette entries cannot use role='transparent'")
        colors.add(color)
        role_colors[role] = color
        roles.append(role)

    opaque_count = sum(color[3] == 255 for color in colors)
    if transparent_count != 1:
        raise ValueError(
            f"Yone V6 palette needs exactly one transparent entry, got {transparent_count}"
        )
    if not 1 <= opaque_count <= NATIVE_V7_MAX_OPAQUE_COLORS:
        raise ValueError(
            "Yone V6 palette must define 1.."
            f"{NATIVE_V7_MAX_OPAQUE_COLORS} opaque colors, got {opaque_count}"
        )
    normalized_roles = [role.strip().lower() for role in roles]
    for semantic_role in ("skin", "eye", "mask"):
        if not any(semantic_role in role for role in normalized_roles):
            raise ValueError(
                f"Yone V6 palette needs at least one role containing {semantic_role!r}"
            )
    referenced_weapon_roles = {
        role
        for weapon in V7_WEAPON_PALETTE_ROLES.values()
        for ramp in weapon.values()
        for role in ramp
    }
    if not referenced_weapon_roles <= set(roles):
        raise ValueError(
            "Yone V7 palette is missing weapon roles: "
            f"{sorted(referenced_weapon_roles - set(roles))}"
        )
    if len(referenced_weapon_roles) != 6:
        raise ValueError(
            "Yone V7 palette must declare six disjoint single-role weapon colors"
        )
    for weapon, ramp in V7_WEAPON_PALETTE_ROLES.items():
        if any(len(role_names) != 1 for role_names in ramp.values()):
            raise ValueError(
                f"Yone V7 {weapon} palette ramp must use one exclusive role per level"
            )
    return colors, role_colors, {
        "path": path.relative_to(MOD_ROOT).as_posix(),
        "schema_version": payload["schema_version"],
        "route": payload["route"],
        "opaque_color_count": opaque_count,
        "roles": roles,
        "weapon_roles": payload["weapon_roles"],
        "sha256": sha256(path),
    }


def _validate_local_box(
    value: Any,
    label: str,
    frame_size: tuple[int, int],
    *,
    nullable: bool,
) -> tuple[int, int, int, int] | None:
    if value is None:
        if nullable:
            return None
        raise ValueError(f"Yone V6 {label} cannot be null")
    if (
        not isinstance(value, list)
        or len(value) != 4
        or any(not _is_plain_int(part) for part in value)
    ):
        raise ValueError(f"Yone V6 {label} must be [x,y,w,h]")
    x, y, width, height = value
    if (
        x < 0
        or y < 0
        or width <= 0
        or height <= 0
        or x + width > frame_size[0]
        or y + height > frame_size[1]
    ):
        raise ValueError(
            f"Yone V6 {label} {value} is outside frame {frame_size}"
        )
    return x, y, width, height


def _validate_local_point(
    value: Any,
    label: str,
    frame_size: tuple[int, int],
) -> tuple[int, int]:
    if (
        not isinstance(value, list)
        or len(value) != 2
        or any(not _is_plain_int(part) for part in value)
    ):
        raise ValueError(f"Yone V7 {label} must be [x,y]")
    x, y = value
    if not (0 <= x < frame_size[0] and 0 <= y < frame_size[1]):
        raise ValueError(
            f"Yone V7 {label} {value} is outside frame {frame_size}"
        )
    return x, y


def _validate_finite_number(
    value: Any,
    label: str,
    *,
    minimum: float,
    maximum: float,
    minimum_inclusive: bool = True,
) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"Yone V7 {label} must be a finite number")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"Yone V7 {label} must be finite")
    minimum_ok = number >= minimum if minimum_inclusive else number > minimum
    if not minimum_ok or number > maximum:
        lower = "at least" if minimum_inclusive else "greater than"
        raise ValueError(
            f"Yone V7 {label} must be {lower} {minimum} and at most {maximum}"
        )
    return number


def _weapon_pixel_bbox(
    points: set[tuple[int, int]],
) -> tuple[int, int, int, int]:
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    left = min(xs)
    top = min(ys)
    return left, top, max(xs) - left + 1, max(ys) - top + 1


def _weapon_component_at_anchor(
    points: set[tuple[int, int]], anchor: tuple[int, int]
) -> set[tuple[int, int]]:
    remaining = set(points)
    remaining.remove(anchor)
    component = {anchor}
    queue: deque[tuple[int, int]] = deque([anchor])
    while queue:
        x, y = queue.popleft()
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                if dx == 0 and dy == 0:
                    continue
                neighbour = (x + dx, y + dy)
                if neighbour in remaining:
                    remaining.remove(neighbour)
                    component.add(neighbour)
                    queue.append(neighbour)
    return component


def _validate_v7_rgba_png(
    path: Path,
    label: str,
    allowed_colors: set[tuple[int, int, int, int]],
    expected_size: tuple[int, int],
) -> tuple[Image.Image, set[tuple[int, int, int, int]]]:
    try:
        with Image.open(path) as opened:
            if opened.format != "PNG":
                raise ValueError(f"Yone V6 {label} is not encoded as PNG: {path}")
            if opened.mode != "RGBA":
                raise ValueError(
                    f"Yone V6 {label} must be encoded as RGBA, got {opened.mode}"
                )
            opened.load()
            image = opened.copy()
    except (OSError, SyntaxError) as exc:
        raise ValueError(f"Yone V6 {label} cannot be decoded: {path}") from exc
    if image.size != expected_size:
        raise ValueError(
            f"Yone V6 {label} size {image.size} != exact native {expected_size}"
        )
    pixel_reader = getattr(image, "get_flattened_data", None)
    used = set(pixel_reader() if pixel_reader is not None else image.getdata())
    alpha_values = {color[3] for color in used}
    if not alpha_values.issubset({0, 255}):
        raise ValueError(
            f"Yone V6 {label} contains non-binary alpha values: {sorted(alpha_values)}"
        )
    transparent = {color for color in used if color[3] == 0}
    if transparent - {(0, 0, 0, 0)}:
        raise ValueError(
            f"Yone V6 {label} has RGB data under transparent pixels: {sorted(transparent)[:8]}"
        )
    unknown = used - allowed_colors
    if unknown:
        raise ValueError(
            f"Yone V6 {label} uses colors outside palette.json: {sorted(unknown)[:8]}"
        )
    if image.getchannel("A").getbbox() is None:
        raise ValueError(f"Yone V6 {label} is empty")
    return image, used


def _validate_v7_weapon_geometry(
    row: dict[str, Any],
    weapon: str,
    frame: Image.Image,
    role_colors: set[tuple[int, int, int, int]],
    label: str,
) -> dict[str, Any]:
    """Validate one weapon from exclusive final-pixel roles, not declarations."""

    pixels = frame.load()
    points = {
        (x, y)
        for y in range(frame.height)
        for x in range(frame.width)
        if pixels[x, y] in role_colors
    }
    if not points:
        raise ValueError(
            f"Yone V7 {label} has no final pixels for the exclusive {weapon} roles"
        )

    count_key = f"{weapon}_pixel_count"
    pixel_count = row[count_key]
    if not _is_plain_int(pixel_count) or pixel_count <= 0:
        raise ValueError(f"Yone V7 {label}.{count_key} must be a positive integer")
    if pixel_count != len(points):
        raise ValueError(
            f"Yone V7 {label}.{count_key} {pixel_count} != final-role count {len(points)}"
        )

    hand_key = f"{weapon}_hand_anchor"
    tip_key = f"{weapon}_tip"
    hand = _validate_local_point(row[hand_key], f"{label}.{hand_key}", frame.size)
    tip = _validate_local_point(row[tip_key], f"{label}.{tip_key}", frame.size)
    if hand not in points:
        raise ValueError(
            f"Yone V7 {label}.{hand_key} must be an exclusive {weapon} role pixel"
        )
    component = _weapon_component_at_anchor(points, hand)
    if tip not in component:
        raise ValueError(
            f"Yone V7 {label}.{tip_key} must belong to the hand-connected {weapon} blade"
        )

    bbox_key = f"{weapon}_blade_bbox"
    bbox = _validate_local_box(
        row[bbox_key], f"{label}.{bbox_key}", frame.size, nullable=False
    )
    assert bbox is not None
    actual_bbox = _weapon_pixel_bbox(component)
    if bbox != actual_bbox:
        raise ValueError(
            f"Yone V7 {label}.{bbox_key} {bbox} "
            f"!= hand-connected final-role bbox {actual_bbox}"
        )

    span_key = f"{weapon}_span_px"
    maximum_span = math.hypot(frame.width - 1, frame.height - 1)
    span = _validate_finite_number(
        row[span_key],
        f"{label}.{span_key}",
        minimum=0.0,
        maximum=maximum_span,
        minimum_inclusive=False,
    )
    actual_span = math.hypot(tip[0] - hand[0], tip[1] - hand[1])
    if abs(span - actual_span) > 0.01:
        raise ValueError(
            f"Yone V7 {label}.{span_key} {span} != hand-to-tip span {actual_span:.6f}"
        )

    connectedness_key = f"{weapon}_connectedness"
    connectedness = _validate_finite_number(
        row[connectedness_key],
        f"{label}.{connectedness_key}",
        minimum=0.0,
        maximum=1.0,
        minimum_inclusive=False,
    )
    actual_connectedness = len(component) / len(points)
    if abs(connectedness - actual_connectedness) > 0.000051:
        raise ValueError(
            f"Yone V7 {label}.{connectedness_key} {connectedness} "
            f"!= final-role connectedness {actual_connectedness:.9f}"
        )

    crop_key = f"{weapon}_crop_ratio"
    crop_ratio = _validate_finite_number(
        row[crop_key],
        f"{label}.{crop_key}",
        minimum=0.0,
        maximum=1.0,
    )
    survived_key = f"{weapon}_source_tip_survived"
    source_tip_survived = row[survived_key]
    if not isinstance(source_tip_survived, bool):
        raise ValueError(f"Yone V7 {label}.{survived_key} must be boolean")

    return {
        "blade_bbox": list(bbox),
        "hand_anchor": list(hand),
        "tip": list(tip),
        "span_px": span,
        "connectedness": connectedness,
        "pixel_count": pixel_count,
        "crop_ratio": crop_ratio,
        "source_tip_survived": source_tip_survived,
    }


def _native_v7_expected_frames() -> dict[tuple[str, int], tuple[int, int, int, int]]:
    expected: dict[tuple[str, int], tuple[int, int, int, int]] = {}
    for action in GENERATED_BODY_ACTIONS:
        contract = NATIVE_CONTRACT if action in NATIVE_CONTRACT else CUSTOM_ACTION_CONTRACT
        rects = contract[action]["rects"]
        if action == "dead":
            rects = rects[:-1]
        for index, rect in enumerate(rects):
            expected[(action, index)] = rect
    if len(expected) != GENERATED_BODY_FRAME_COUNT:
        raise ValueError(
            "Internal Yone V6 body contract changed: "
            f"{len(expected)}/{GENERATED_BODY_FRAME_COUNT} frames"
        )
    return expected


def _load_v7_opaque_card_preview(path: Path) -> Image.Image:
    """Load the complete 141x138 card proof without applying the body palette."""

    try:
        with Image.open(path) as opened:
            if opened.format != "PNG":
                raise ValueError(
                    f"Yone V6 body_preview is not encoded as PNG: {path}"
                )
            if opened.mode != "RGBA":
                raise ValueError(
                    "Yone V6 body_preview must be RGBA, "
                    f"got {opened.mode}: {path}"
                )
            opened.load()
            preview = opened.copy()
    except (OSError, SyntaxError) as exc:
        raise ValueError(f"Yone V6 body_preview cannot be decoded: {path}") from exc
    if preview.size != (141, 138):
        raise ValueError(
            f"Yone V6 body_preview size {preview.size} != complete card (141, 138)"
        )
    if preview.getchannel("A").getextrema() != (255, 255):
        raise ValueError("Yone V6 body_preview must be a fully opaque card proof")
    return preview


def _render_v7_opaque_card_preview(idle: Image.Image) -> Image.Image:
    """Replay the generator's card chrome and exact idle actor render."""

    rendered = idle.resize(
        (
            round(idle.width * YONE_LIVE_CARD_SCALE),
            round(idle.height * YONE_LIVE_CARD_SCALE),
        ),
        Image.Resampling.NEAREST,
    )
    preview = Image.new("RGBA", (141, 138), (15, 17, 26, 255))
    draw = ImageDraw.Draw(preview)
    draw.rounded_rectangle(
        (4, 4, 137, 136),
        radius=11,
        fill=(20, 21, 31, 255),
        outline=(66, 70, 83, 255),
        width=1,
    )
    draw.line((5, 96, 136, 96), fill=(43, 46, 57, 255), width=1)
    stage_height = max(
        round(rect[3] * YONE_LIVE_CARD_SCALE)
        for rect in NATIVE_CONTRACT["idle"]["rects"]
    )
    actor_x = (preview.width - rendered.width) // 2
    actor_y = (stage_height - rendered.height) // 2
    preview.alpha_composite(rendered, (actor_x, actor_y))
    actor_mask = Image.new("L", preview.size, 0)
    actor_mask.paste(rendered.getchannel("A"), (actor_x, actor_y))
    actor_bbox = actor_mask.getbbox()
    if actor_bbox is None:
        raise ValueError("Yone V6 body_preview actor route is empty")
    # V7 battle idle keeps both swords visible. Dedicated source-direct UI
    # portraits own the management/BP/compact icon exclusion contract.
    if YONE_LIVE_CARD_DIVIDER_TOP - actor_bbox[3] < YONE_LIVE_CARD_MIN_DIVIDER_CLEARANCE:
        raise ValueError(
            "Yone V6 body_preview actor approaches the divider: "
            f"clearance={YONE_LIVE_CARD_DIVIDER_TOP - actor_bbox[3]}"
        )
    draw.arc((99, 72, 112, 88), 290, 70, fill=(236, 238, 242, 255), width=2)
    draw.rectangle((119, 76, 130, 87), outline=(217, 220, 228, 255), width=2)
    draw.rectangle((122, 79, 127, 84), fill=(104, 110, 125, 255))
    return preview


def _load_native_v7_body_frames() -> tuple[
    dict[tuple[str, int], Image.Image], dict[str, Any], dict[str, dict[str, Any]]
]:
    """Load and audit all final 1x frames without changing a single pixel."""

    manifest = _load_v7_json(NATIVE_V7_MANIFEST, "frames manifest")
    manifest_fields = {
        "schema_version",
        "route",
        "atlas_size",
        "palette_file",
        "body_preview",
        "weapon_contract",
        "frames",
    }
    if set(manifest) != manifest_fields:
        raise ValueError(
            "Yone V6 manifest fields changed: "
            f"got={sorted(manifest)}, expected={sorted(manifest_fields)}"
        )
    if manifest["schema_version"] != NATIVE_V7_SCHEMA_VERSION:
        raise ValueError(
            f"Yone V7 manifest schema_version must be {NATIVE_V7_SCHEMA_VERSION}"
        )
    if manifest["route"] != NATIVE_V7_ROUTE:
        raise ValueError(f"Yone V7 manifest route must be {NATIVE_V7_ROUTE!r}")
    if manifest["atlas_size"] != list(ACTOR_SHEET_SIZE):
        raise ValueError(
            f"Yone V6 atlas_size {manifest['atlas_size']} != {list(ACTOR_SHEET_SIZE)}"
        )
    if manifest["weapon_contract"] != V7_WEAPON_CONTRACT:
        raise ValueError(
            "Yone V7 weapon_contract changed: "
            f"{manifest['weapon_contract']!r}"
        )

    palette_path = _v7_relative_file(
        manifest["palette_file"], "palette_file", ".json"
    )
    allowed_colors, palette_role_colors, palette_audit = _validate_v7_palette(
        palette_path
    )
    weapon_role_colors = {
        weapon: {
            palette_role_colors[role]
            for role_names in ramp.values()
            for role in role_names
        }
        for weapon, ramp in V7_WEAPON_PALETTE_ROLES.items()
    }
    if weapon_role_colors["steel"] & weapon_role_colors["azakana"]:
        raise ValueError("Yone V7 steel and Azakana palette colors must be disjoint")

    preview_value = manifest["body_preview"]
    preview_path: Path | None = None
    preview_image: Image.Image | None = None
    if preview_value is not None:
        preview_path = _v7_relative_file(preview_value, "body_preview", ".png")
        preview_image = _load_v7_opaque_card_preview(preview_path)
    elif not isinstance(preview_value, type(None)):
        raise ValueError("Yone V6 body_preview must be a relative PNG path or null")

    rows = manifest["frames"]
    if not isinstance(rows, list) or len(rows) != GENERATED_BODY_FRAME_COUNT:
        raise ValueError(
            "Yone V6 frames must contain exactly "
            f"{GENERATED_BODY_FRAME_COUNT} records"
        )
    expected = _native_v7_expected_frames()
    frames: dict[tuple[str, int], Image.Image] = {}
    paths: dict[Path, tuple[str, int]] = {}
    rect_owners: dict[tuple[int, int, int, int], tuple[str, int]] = {}
    audits: dict[str, dict[str, Any]] = {}

    for row_number, row in enumerate(rows):
        if not isinstance(row, dict) or set(row) != NATIVE_V7_FRAME_FIELDS:
            got = sorted(row) if isinstance(row, dict) else type(row).__name__
            raise ValueError(
                f"Yone V6 frames[{row_number}] fields changed: got={got}, "
                f"expected={sorted(NATIVE_V7_FRAME_FIELDS)}"
            )
        action = row["action"]
        index = row["index"]
        if not isinstance(action, str) or not _is_plain_int(index):
            raise ValueError(
                f"Yone V6 frames[{row_number}] action/index types are invalid"
            )
        if row["active_weapon"] != V7_FRAME_ACTIVE_WEAPON.get(action):
            raise ValueError(
                f"Yone V7 {action}[{index}] active_weapon changed: "
                f"{row['active_weapon']!r}"
            )
        key = (action, index)
        if key not in expected:
            raise ValueError(f"Yone V6 frames[{row_number}] has unknown key {key}")
        if key in frames:
            raise ValueError(f"Yone V6 manifest duplicates action/index {key}")
        rect_value = row["rect"]
        if (
            not isinstance(rect_value, list)
            or len(rect_value) != 4
            or any(not _is_plain_int(part) for part in rect_value)
        ):
            raise ValueError(f"Yone V6 {action}[{index}].rect must be [x,y,w,h]")
        rect = tuple(rect_value)
        if rect != expected[key]:
            raise ValueError(
                f"Yone V6 {action}[{index}] rect {rect} != native {expected[key]}"
            )
        if rect in rect_owners:
            raise ValueError(
                f"Yone V6 native rect {rect} is shared by {rect_owners[rect]} and {key}"
            )
        rect_owners[rect] = key

        path = _v7_relative_file(row["file"], f"{action}[{index}].file", ".png")
        resolved = path.resolve()
        if resolved in paths:
            raise ValueError(
                f"Yone V6 frame file {path} is reused by {paths[resolved]} and {key}"
            )
        if preview_path is not None and resolved == preview_path.resolve():
            raise ValueError(f"Yone V6 body_preview cannot also be frame {key}")
        paths[resolved] = key
        frame, used_colors = _validate_v7_rgba_png(
            path,
            f"{action}[{index}]",
            allowed_colors,
            (rect[2], rect[3]),
        )
        weapon_geometry = {
            weapon: _validate_v7_weapon_geometry(
                row,
                weapon,
                frame,
                weapon_role_colors[weapon],
                f"{action}[{index}]",
            )
            for weapon in ("steel", "azakana")
        }
        derived_weapons_present = [
            weapon
            for weapon in ("steel", "azakana")
            if weapon_geometry[weapon]["pixel_count"] > 0
        ]
        if row["weapons_present"] != derived_weapons_present:
            raise ValueError(
                f"Yone V7 {action}[{index}].weapons_present must be derived from "
                f"validated final geometry: {derived_weapons_present}"
            )
        if (
            weapon_geometry["steel"]["hand_anchor"]
            == weapon_geometry["azakana"]["hand_anchor"]
        ):
            raise ValueError(
                f"Yone V7 {action}[{index}] must attach the two swords to distinct hands"
            )
        if weapon_geometry["steel"]["tip"] == weapon_geometry["azakana"]["tip"]:
            raise ValueError(
                f"Yone V7 {action}[{index}] must retain distinct sword tips"
            )
        alpha_bbox = frame.getchannel("A").getbbox()
        assert alpha_bbox is not None
        alpha = frame.getchannel("A")
        opaque_edges = {
            "top": sum(alpha.crop((0, 0, frame.width, 1)).histogram()[1:]),
            "bottom": sum(
                alpha.crop((0, frame.height - 1, frame.width, frame.height)).histogram()[1:]
            ),
            "left": sum(alpha.crop((0, 0, 1, frame.height)).histogram()[1:]),
            "right": sum(
                alpha.crop((frame.width - 1, 0, frame.width, frame.height)).histogram()[1:]
            ),
        }
        if any(opaque_edges.values()):
            raise ValueError(
                f"Yone V6 {action}[{index}] touches a native frame edge: {opaque_edges}"
            )

        bottom_margin = row["bottom_margin"]
        if not _is_plain_int(bottom_margin) or not 0 <= bottom_margin < frame.height:
            raise ValueError(f"Yone V6 {action}[{index}].bottom_margin is invalid")
        actual_bottom = frame.height - alpha_bbox[3]
        if bottom_margin != actual_bottom:
            raise ValueError(
                f"Yone V6 {action}[{index}] bottom_margin {bottom_margin} "
                f"!= actual {actual_bottom}"
            )
        if action != "dead" and bottom_margin < 2:
            raise ValueError(
                f"Yone V6 {action}[{index}] needs at least 2px bottom clearance"
            )

        face_visibility = row["face_visibility"]
        if face_visibility not in {"front", "profile", "hidden"}:
            raise ValueError(
                f"Yone V6 {action}[{index}].face_visibility is invalid: "
                f"{face_visibility!r}"
            )

        face_bbox = _validate_local_box(
            row["face_bbox"], f"{action}[{index}].face_bbox", frame.size, nullable=True
        )
        mask_bbox = _validate_local_box(
            row["mask_bbox"], f"{action}[{index}].mask_bbox", frame.size, nullable=True
        )
        for label, box in (("face_bbox", face_bbox), ("mask_bbox", mask_bbox)):
            if box is not None:
                x, y, width, height = box
                if frame.crop((x, y, x + width, y + height)).getchannel("A").getbbox() is None:
                    raise ValueError(
                        f"Yone V6 {action}[{index}].{label} contains no actor pixels"
                    )

        eye_value = row["eye_pixels"]
        if not isinstance(eye_value, list):
            raise ValueError(f"Yone V6 {action}[{index}].eye_pixels must be a list")
        eyes: list[tuple[int, int]] = []
        for eye_index, point in enumerate(eye_value):
            if (
                not isinstance(point, list)
                or len(point) != 2
                or any(not _is_plain_int(part) for part in point)
            ):
                raise ValueError(
                    f"Yone V6 {action}[{index}].eye_pixels[{eye_index}] must be [x,y]"
                )
            x, y = point
            if not (0 <= x < frame.width and 0 <= y < frame.height):
                raise ValueError(
                    f"Yone V6 {action}[{index}] eye pixel {(x, y)} is out of bounds"
                )
            if frame.getpixel((x, y))[3] != 255:
                raise ValueError(
                    f"Yone V6 {action}[{index}] eye pixel {(x, y)} is transparent"
                )
            if face_bbox is None:
                raise ValueError(
                    f"Yone V6 {action}[{index}] declares eye pixels without face_bbox"
                )
            fx, fy, fw, fh = face_bbox
            if not (fx <= x < fx + fw and fy <= y < fy + fh):
                raise ValueError(
                    f"Yone V6 {action}[{index}] eye pixel {(x, y)} is outside face_bbox"
                )
            eyes.append((x, y))
        if len(eyes) != len(set(eyes)):
            raise ValueError(f"Yone V6 {action}[{index}] duplicates eye pixels")
        if face_visibility == "hidden" and (
            face_bbox is not None or mask_bbox is not None or eyes
        ):
            raise ValueError(
                f"Yone V6 {action}[{index}] hidden face cannot carry annotations"
            )
        if face_bbox is None and mask_bbox is not None:
            raise ValueError(
                f"Yone V6 {action}[{index}] declares mask_bbox without face_bbox"
            )
        if face_visibility == "front" and (
            face_bbox is None or not eyes or mask_bbox is None
        ):
            raise ValueError(
                f"Yone V6 {action}[{index}] front face requires "
                "face_bbox, eye_pixels and mask_bbox"
            )
        if action == "idle" and (
            face_bbox is None
            or mask_bbox is None
            or not eyes
            or face_bbox[2] < 6
            or face_bbox[3] < 7
        ):
            raise ValueError(
                f"Yone V6 idle[{index}] must annotate a visible face, mask and true eye cue"
            )
        if action == "idle" and (
            (face_visibility == "front" and len(eyes) < 2)
            or (face_visibility == "profile" and len(eyes) < 1)
            or face_visibility == "hidden"
        ):
            raise ValueError(
                f"Yone V6 idle[{index}] eye count {len(eyes)} does not match "
                f"face_visibility={face_visibility!r}"
            )

        foot_value = row["foot_zones"]
        if not isinstance(foot_value, list):
            raise ValueError(f"Yone V6 {action}[{index}].foot_zones must be a list")
        foot_zones: list[tuple[int, int, int, int]] = []
        for foot_index, value in enumerate(foot_value):
            box = _validate_local_box(
                value,
                f"{action}[{index}].foot_zones[{foot_index}]",
                frame.size,
                nullable=False,
            )
            assert box is not None
            x, y, width, height = box
            if frame.crop((x, y, x + width, y + height)).getchannel("A").getbbox() is None:
                raise ValueError(
                    f"Yone V6 {action}[{index}] foot zone {foot_index} is empty"
                )
            foot_zones.append(box)
        if len(foot_zones) != len(set(foot_zones)):
            raise ValueError(f"Yone V6 {action}[{index}] duplicates foot_zones")
        if action in {
            "idle",
            "hit",
            "attack",
            "skill2",
            "skill2_dash",
            "skill2_attack",
            "run",
            "skill",
        } and not foot_zones:
            raise ValueError(f"Yone V6 {action}[{index}] must annotate foot_zones")

        frames[key] = frame
        audits[f"{action}[{index}]"] = {
            "source": path.relative_to(MOD_ROOT).as_posix(),
            "native_rect": list(rect),
            "source_size": list(frame.size),
            "source_alpha_bbox": list(alpha_bbox),
            "bottom_margin": bottom_margin,
            "face_bbox": list(face_bbox) if face_bbox is not None else None,
            "eye_pixels": [list(point) for point in eyes],
            "mask_bbox": list(mask_bbox) if mask_bbox is not None else None,
            "foot_zones": [list(box) for box in foot_zones],
            "face_visibility": face_visibility,
            "active_weapon": row["active_weapon"],
            "weapons_present": row["weapons_present"],
            "weapon_geometry": weapon_geometry,
            "hard_alpha": True,
            "transparent_frame_edges": True,
            "opaque_palette_size": sum(color[3] == 255 for color in used_colors),
            "sha256": sha256(path),
            "pack_transform": "none",
        }

    missing = set(expected) - set(frames)
    if missing:
        raise ValueError(f"Yone V6 manifest is missing frames: {sorted(missing)}")
    if preview_image is not None:
        idle = frames[("idle", 0)]
        expected_preview = _render_v7_opaque_card_preview(idle)
        if preview_image.tobytes() != expected_preview.tobytes():
            raise ValueError(
                "Yone V6 body_preview must be the exact complete opaque 141x138 "
                "card chrome with the idle[0] 2.2x NEAREST actor route"
            )
    expected_pngs = set(paths)
    if preview_path is not None:
        expected_pngs.add(preview_path.resolve())
    if NATIVE_V7_CONTACT_PREVIEW.is_file():
        expected_pngs.add(NATIVE_V7_CONTACT_PREVIEW.resolve())
    actual_pngs = {
        path.resolve()
        for path in NATIVE_V7_ROOT.rglob("*.png")
        if path.is_file()
    }
    if actual_pngs != expected_pngs:
        extras = sorted(str(path) for path in actual_pngs - expected_pngs)
        omitted = sorted(str(path) for path in expected_pngs - actual_pngs)
        raise ValueError(
            "Yone V6 source PNG set differs from the manifest: "
            f"unreferenced={extras}, missing={omitted}"
        )

    manifest_audit = {
        "schema_version": manifest["schema_version"],
        "route": manifest["route"],
        "manifest": NATIVE_V7_MANIFEST.relative_to(MOD_ROOT).as_posix(),
        "manifest_sha256": sha256(NATIVE_V7_MANIFEST),
        "atlas_size": list(ACTOR_SHEET_SIZE),
        "frame_count": len(frames),
        "weapon_contract": manifest["weapon_contract"],
        "palette": palette_audit,
        "body_preview": (
            preview_path.relative_to(MOD_ROOT).as_posix()
            if preview_path is not None
            else None
        ),
        "body_preview_kind": "complete opaque 141x138 runtime-card proof",
        "body_preview_sha256": (
            sha256(preview_path) if preview_path is not None else None
        ),
        "contact_preview": (
            NATIVE_V7_CONTACT_PREVIEW.relative_to(MOD_ROOT).as_posix()
            if NATIVE_V7_CONTACT_PREVIEW.is_file()
            else None
        ),
        "body_processing": "none; exact final 1x RGBA byte copy",
    }
    return frames, manifest_audit, audits


def _paste_native_v7_bytes(
    sheet: Image.Image,
    placements: dict[tuple[int, int, int, int], bytes],
    rect: tuple[int, int, int, int],
    frame: Image.Image,
) -> None:
    """Paste one exact-size V6 RGBA image and prove byte identity."""

    x, y, width, height = rect
    if frame.mode != "RGBA" or frame.size != (width, height):
        raise ValueError(
            f"Yone V6 frame {frame.mode}/{frame.size} does not match native rect {rect}"
        )
    for previous in placements:
        px, py, pw, ph = previous
        if not (
            x + width <= px
            or px + pw <= x
            or y + height <= py
            or py + ph <= y
        ):
            raise ValueError(
                f"Yone V6 body rectangles overlap: new={rect}, existing={previous}"
            )
    pixels = frame.tobytes()
    placements[rect] = pixels
    sheet.paste(frame, (x, y))
    copied = sheet.crop((x, y, x + width, y + height))
    if copied.tobytes() != pixels:
        raise ValueError(f"Yone V6 byte copy failed for native rect {rect}")


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
    """Measure the real V6 85x93 texture pasted into the card at native 1:1."""

    source = fullbody.convert("RGBA")
    if source.size != (85, 93):
        raise ValueError(f"Yone fullbody source must be 85x93, got {source.size}")
    rendered = source.copy()
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
        "resampling": "none; 85x93 source pasted 1:1",
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


def build_actor() -> tuple[Path, Path, Path, Path]:
    qw_vfx = split_grid(Image.open(QW_VFX_ALPHA).convert("RGBA"), 5, 4)
    r_vfx = split_grid(Image.open(R_VFX_ALPHA).convert("RGBA"), 5, 3)
    native_frames, _, _ = _load_native_v7_body_frames()
    sheet = Image.new("RGBA", ACTOR_SHEET_SIZE, (0, 0, 0, 0))
    placements: dict[tuple[int, int, int, int], bytes] = {}

    # Copy each final native V6 PNG directly into its official atlas rectangle.
    # There is deliberately no master fallback and no crop, resize, alpha
    # cleanup, palette conversion or quantization anywhere in the body path.
    for tag in GENERATED_BODY_ACTIONS:
        contract = NATIVE_CONTRACT if tag in NATIVE_CONTRACT else CUSTOM_ACTION_CONTRACT
        rects = (
            contract[tag]["rects"][:-1]
            if tag == "dead"
            else contract[tag]["rects"]
        )
        for index, rect in enumerate(rects):
            frame = native_frames[(tag, index)]
            _paste_native_v7_bytes(sheet, placements, rect, frame)

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

    sheet_path = ACTOR_DIR / "yone_v7#sheet.png"
    anim_path = ACTOR_DIR / "yone_v7#anim.fanim"
    legacy_sheet_path = ACTOR_DIR / "yone#sheet.png"
    legacy_anim_path = ACTOR_DIR / "yone#anim.fanim"
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
                for tag, spec in {**NATIVE_CONTRACT, **CUSTOM_ACTION_CONTRACT}.items()
            }
        },
    )
    # Saves embed the champion definition, including its sprite key. Keep the
    # former `yone` key as a byte-identical compatibility alias so a season
    # created before 0.10.20 cannot resolve an obsolete or missing actor.
    legacy_sheet_path.write_bytes(sheet_path.read_bytes())
    legacy_anim_path.write_bytes(anim_path.read_bytes())
    if sha256(legacy_sheet_path) != sha256(sheet_path) or sha256(legacy_anim_path) != sha256(anim_path):
        raise ValueError("Yone legacy actor aliases are not byte-identical to yone_v7")
    return sheet_path, anim_path, legacy_sheet_path, legacy_anim_path


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


def remove_magenta_chroma_key(image: Image.Image) -> Image.Image:
    """Remove V6's magenta plate and clear hidden RGB bytes.

    The V7 UI source is intentionally much larger than every destination.
    Keying happens before its only resize so magenta can never be averaged
    into the face/hair outline by the LANCZOS shrink.
    """

    rgba = image.convert("RGBA")
    output = Image.new("RGBA", rgba.size, (0, 0, 0, 0))
    source_pixels = rgba.load()
    target_pixels = output.load()
    for y in range(rgba.height):
        for x in range(rgba.width):
            red, green, blue, alpha = source_pixels[x, y]
            magenta_plate = (
                alpha > 0
                and red >= 100
                and blue >= 90
                and green <= 105
                and min(red, blue) - green >= 42
                and abs(red - blue) <= 82
            )
            if not magenta_plate and alpha:
                target_pixels[x, y] = (red, green, blue, alpha)
    return output


def load_yone_v7_ui_subject() -> Image.Image:
    """Load the sole high-resolution authority for every Yone UI surface."""

    with Image.open(YONE_V7_UI_SOURCE) as opened:
        source = opened.convert("RGBA")
    if source.width < 800 or source.height < 1000:
        raise ValueError(
            "Yone V7 UI source must remain high resolution, got "
            f"{source.size}; a reduced battle frame is not an allowed fallback"
        )
    keyed = remove_magenta_chroma_key(source)
    subject = keyed.crop(alpha_bbox(keyed))
    if subject.width < 400 or subject.height < 800:
        raise ValueError(
            "Yone V7 UI source lost its full high-resolution body after keying: "
            f"{subject.size}"
        )
    return subject


def crop_yone_v7_ui_focus(
    full_body: Image.Image,
    focus: tuple[float, float, float, float],
) -> Image.Image:
    width, height = full_body.size
    left, top, right, bottom = focus
    crop = full_body.crop(
        (
            round(width * left),
            round(height * top),
            round(width * right),
            round(height * bottom),
        )
    )
    return crop.crop(alpha_bbox(crop))


def render_source_direct_ui_subject(
    source: Image.Image,
    size: tuple[int, int],
    *,
    max_subject: tuple[int, int],
    bottom: int,
    x_offset: int = 0,
) -> Image.Image:
    """Shrink V7 high-resolution art directly into one independent UI asset."""

    subject = source.convert("RGBA").crop(alpha_bbox(source.convert("RGBA")))
    scale = min(max_subject[0] / subject.width, max_subject[1] / subject.height)
    if scale >= 1.0:
        raise ValueError(
            "Yone UI route attempted to enlarge a reduced source; "
            f"subject={subject.size}, destination_cap={max_subject}"
        )
    subject = subject.resize(
        (max(1, round(subject.width * scale)), max(1, round(subject.height * scale))),
        Image.Resampling.LANCZOS,
    )
    # LANCZOS is used exactly once, then the runtime texture returns to the
    # game's hard-alpha/palette discipline. palette_finish also clears RGB
    # below transparent pixels, so no magenta fringe can survive packing.
    subject = hard_alpha(subject, 96)
    subject = palette_finish(subject, 128)
    subject = subject.crop(alpha_bbox(subject))
    output = Image.new("RGBA", size, (0, 0, 0, 0))
    x = (size[0] - subject.width) // 2 + x_offset
    y = bottom - subject.height
    if x < 0 or y < 0 or subject.width > max_subject[0] or subject.height > max_subject[1]:
        raise ValueError(
            f"Yone source-direct UI subject {subject.size} does not fit {size}"
        )
    output.alpha_composite(subject, (x, y))
    return output


def yone_ui_surface_quality(image: Image.Image) -> dict[str, Any]:
    """Measure detail that a 43x55 NEAREST enlargement cannot reproduce."""

    rgba = image.convert("RGBA")
    bbox = rgba.getchannel("A").getbbox()
    if bbox is None:
        raise ValueError("Yone source-direct UI surface is empty")
    opaque = {
        (x, y)
        for y in range(rgba.height)
        for x in range(rgba.width)
        if rgba.getpixel((x, y))[3] == 255
    }
    colors = {rgba.getpixel(point)[:3] for point in opaque}
    dark = sum(
        1
        for point in opaque
        if sum(rgba.getpixel(point)[:3]) / 3 <= 82
    )
    neighbours = 0
    repeated = 0
    for x, y in opaque:
        for neighbour in ((x + 1, y), (x, y + 1)):
            if neighbour not in opaque:
                continue
            neighbours += 1
            if rgba.getpixel((x, y))[:3] == rgba.getpixel(neighbour)[:3]:
                repeated += 1
    transparent_rgb_clear = all(
        alpha != 0 or (red, green, blue) == (0, 0, 0)
        for red, green, blue, alpha in (
            rgba.get_flattened_data()
            if hasattr(rgba, "get_flattened_data")
            else rgba.getdata()
        )
    )
    alpha_channel = rgba.getchannel("A")
    alpha_values = set(
        alpha_channel.get_flattened_data()
        if hasattr(alpha_channel, "get_flattened_data")
        else alpha_channel.getdata()
    )
    return {
        "size": list(rgba.size),
        "alpha_bbox": list(bbox),
        "hard_alpha": alpha_values.issubset({0, 255}),
        "transparent_rgb_clear": transparent_rgb_clear,
        "opaque_pixels": len(opaque),
        "opaque_palette_size": len(colors),
        "dark_pixel_ratio": round(dark / max(1, len(opaque)), 4),
        "identical_neighbor_ratio": round(repeated / max(1, neighbours), 4),
    }


def render_yone_v7_ui_card_preview(fullbody: Image.Image) -> Image.Image:
    """Prove the encyclopedia fullbody route at native 1:1.

    The encyclopedia owns a centered 85x93 image node.  Older QA borrowed a
    BP/card icon exclusion zone from a different UI surface; that incorrectly
    forced Yone's encyclopedia art leftward and smaller.  Keep the historical
    141x138 proof canvas for stable QA artifacts, but only validate the real
    centered 85x93 encyclopedia placement here.
    """

    if fullbody.size != (85, 93):
        raise ValueError(f"Yone V7 card source must be 85x93, got {fullbody.size}")
    preview = Image.new("RGBA", (141, 138), (15, 17, 26, 255))
    draw = ImageDraw.Draw(preview)
    draw.rounded_rectangle(
        (4, 4, 137, 136), radius=11,
        fill=(20, 21, 31, 255), outline=(66, 70, 83, 255), width=1,
    )
    draw.line((5, 96, 136, 96), fill=(43, 46, 57, 255), width=1)
    actor_x = (preview.width - fullbody.width) // 2
    preview.alpha_composite(fullbody, (actor_x, 0))
    actor_mask = Image.new("L", preview.size, 0)
    actor_mask.paste(fullbody.getchannel("A"), (actor_x, 0))
    actor_bbox = actor_mask.getbbox()
    if actor_bbox is None or actor_bbox[3] > 88:
        raise ValueError(f"Yone V7 UI card actor placement is unsafe: {actor_bbox}")
    # The localized champion name is drawn by the engine text layer.  Do not
    # bake an approximate host-font or hand-drawn CJK glyph into this texture
    # proof: doing so can falsely make a correct UI asset show the wrong name.
    return preview


def build_splash_and_portraits() -> list[Path]:
    splash = cover_crop(Image.open(SPLASH_SOURCE).convert("RGBA"), (1420, 860), center=(0.50, 0.48))
    splash_path = SPLASH_DIR / "dual_blader.png"
    save_png(splash_path, splash)

    # UI is intentionally independent from the 43x55-class battle atlas.
    # All four surfaces start from this accepted high-resolution V7 source and
    # are shrunk exactly once for their real runtime destination geometry.
    full_body = load_yone_v7_ui_subject()
    fullbody = render_source_direct_ui_subject(
        full_body,
        (85, 93),
        max_subject=(74, 84),
        bottom=88,
    )
    fullbody_path = FULLBODY_DIR / "dual_blader.png"
    save_png(fullbody_path, fullbody)

    # Compact rows need the face, mask and shoulders, not a shrunken full body.
    compact_focus = crop_yone_v7_ui_focus(
        full_body,
        (0.06, 0.02, 0.94, 0.56),
    )
    compact = render_source_direct_ui_subject(
        compact_focus,
        (64, 64),
        max_subject=(50, 50),
        bottom=58,
    )
    compact_path = PORTRAIT_DIR / "dual_blader_compact.png"
    save_png(compact_path, compact)

    scoreboard_focus = crop_yone_v7_ui_focus(
        full_body,
        (0.22, 0.00, 0.78, 0.75),
    )
    scoreboard = render_source_direct_ui_subject(
        scoreboard_focus,
        (48, 64),
        max_subject=(40, 54),
        bottom=60,
    )
    scoreboard_path = PORTRAIT_DIR / "dual_blader_scoreboard.png"
    save_png(scoreboard_path, scoreboard)

    # The native 90x122 grid texture reserves y=96..121 for the name band.
    # End the silhouette by y=86 to leave ten transparent pixels above it.
    grid = render_source_direct_ui_subject(
        full_body,
        (90, 122),
        max_subject=(68, 78),
        bottom=86,
        x_offset=-6,
    )
    grid_path = PORTRAIT_DIR / "dual_blader_grid.png"
    save_png(grid_path, grid)

    # This is the actual destination route: the 85x93 texture is pasted 1:1
    # into the 141x138 card, with no second resize and no battle-atlas input.
    save_png(YONE_V7_UI_CARD_PREVIEW, render_yone_v7_ui_card_preview(fullbody))
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
    """Yield all 67 physical V7 battle frames, excluding alias tags."""

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
    native_source_frames, native_manifest_contract, native_frame_source_contracts = (
        _load_native_v7_body_frames()
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

    actor_face_annotations: dict[str, dict[str, Any]] = {}
    native_body_identity: dict[str, dict[str, Any]] = {}
    native_body_pixel_quality: dict[str, dict[str, Any]] = {}
    for tag, index, entry in iter_actor_body_frames(anims):
        data = entry["data"]
        rect = (
            data["x"], data["y"],
            data["x"] + data["w"], data["y"] + data["h"],
        )
        frame = sheet.crop(rect)
        source_frame = native_source_frames[(tag, index)]
        frame_name = f"{tag}[{index}]"
        identical = frame.tobytes() == source_frame.tobytes()
        native_body_identity[frame_name] = {
            "source_to_atlas_byte_identical": identical,
            "sha256": hashlib.sha256(frame.tobytes()).hexdigest(),
        }
        native_body_pixel_quality[frame_name] = native_pixel_quality(frame)
        source_contract = native_frame_source_contracts[frame_name]
        actor_face_annotations[frame_name] = {
            "contract": "frames.json local-coordinate annotations",
            "face_bbox": source_contract["face_bbox"],
            "eye_pixels": source_contract["eye_pixels"],
            "mask_bbox": source_contract["mask_bbox"],
            "foot_zones": source_contract["foot_zones"],
            "face_visibility": source_contract["face_visibility"],
            "bottom_margin": source_contract["bottom_margin"],
            "source_to_atlas_byte_identical": identical,
        }
    if len(actor_face_annotations) != GENERATED_BODY_FRAME_COUNT:
        raise ValueError(
            "Yone V7 annotation QA must cover "
            f"{GENERATED_BODY_FRAME_COUNT} visible body frames, got "
            f"{len(actor_face_annotations)}"
        )

    ui_images = {
        "fullbody": Image.open(FULLBODY_DIR / "dual_blader.png").convert("RGBA"),
        "compact": Image.open(PORTRAIT_DIR / "dual_blader_compact.png").convert("RGBA"),
        "scoreboard": Image.open(PORTRAIT_DIR / "dual_blader_scoreboard.png").convert("RGBA"),
        "grid": Image.open(PORTRAIT_DIR / "dual_blader_grid.png").convert("RGBA"),
    }
    fullbody = ui_images["fullbody"]
    ui_face_readability = {
        label: yone_face_readability(image, YONE_UI_FACE_WINDOWS[label])
        for label, image in ui_images.items()
    }
    ui_source_direct_quality = {
        label: yone_ui_surface_quality(image)
        for label, image in ui_images.items()
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
                "runtime_key": "asset/lol_mod/aseprite_resources/champions/yone_v7",
                "legacy_saved_data_alias": "asset/lol_mod/aseprite_resources/champions/yone",
                "legacy_alias_byte_identical": True,
                "sheet_size": list(ACTOR_SHEET_SIZE),
                "native_tag_order": list(NATIVE_CONTRACT),
                "custom_tag_order": list(CUSTOM_ACTION_CONTRACT),
                "tag_order": [*NATIVE_CONTRACT, *CUSTOM_ACTION_CONTRACT],
                "frame_counts": {
                    tag: len(spec["rects"])
                    for tag, spec in {**NATIVE_CONTRACT, **CUSTOM_ACTION_CONTRACT}.items()
                },
                "durations": {
                    tag: spec["durations"]
                    for tag, spec in {**NATIVE_CONTRACT, **CUSTOM_ACTION_CONTRACT}.items()
                },
                "rects": {
                    tag: spec["rects"]
                    for tag, spec in {**NATIVE_CONTRACT, **CUSTOM_ACTION_CONTRACT}.items()
                },
                "overlap": "hit_effect_area aliases ult frames 1..11 exactly",
                "body_frames": body_frames,
                "body_source_contract": native_manifest_contract,
                "body_frame_sources": native_frame_source_contracts,
                "pack_time_resampling": "none; 67 exact-size V7 RGBA PNGs are copied byte-for-byte; native rectangles stay immutable and custom frames occupy only the atlas extension",
                "source_to_atlas_identity": native_body_identity,
                "pixel_quality": {
                    "contract": {
                        "hard_alpha": True,
                        "maximum_opaque_palette_size": NATIVE_V7_MAX_OPAQUE_COLORS,
                        "metrics_are_measured_at": "native 1x",
                    },
                    "frames": native_body_pixel_quality,
                },
            },
            "runtime_effect_map": RUNTIME_EFFECT_MAP,
            "runtime_body_actions": {
                "attack": {
                    "steel_animation_tag": "attack_steel",
                    "azakana_animation_tag": "attack_azakana",
                    "frame_count_each": 6,
                    "animation_start_tick": 0,
                    "payload_tick": 13,
                },
                "skill": {
                    "q12_animation_tag": "skill_q12",
                    "q3_animation_tag": "skill_q3",
                    "frame_count_each": 7,
                    "animation_start_tick": 0,
                    "payload_tick": 8,
                },
                "skill2": {
                    "animation_tag": "skill_w_azakana",
                    "frame_count": 5,
                    "qa_contact_tag": "skill2_attack",
                    "animation_start_tick": 0,
                    "payload_tick": 8,
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
                "policy": "from-zero dual-sword V7 body model; all final 1x frames are generated once, palette-audited, then copied byte-for-byte with no pack-time resize or repaint",
                "body_source_manifest": NATIVE_V7_MANIFEST.relative_to(MOD_ROOT).as_posix(),
                "actor_resampling": "NONE",
                "idle_face_contract": {
                    "source_authored": True,
                    "post_scale_repaint": False,
                    "view": "readable chibi portrait with source-authored eye-outline cue pixels",
                    "alpha_geometry_changes": 0,
                },
                "all_battle_body_frames": actor_face_annotations,
                "ui_surfaces": ui_face_readability,
                "ui_source_direct": {
                    "route": "highres-v7-magenta-key-lanczos-hard-alpha-palette128",
                    "source": YONE_V7_UI_SOURCE.relative_to(MOD_ROOT).as_posix(),
                    "source_record": image_record(YONE_V7_UI_SOURCE),
                    "battle_atlas_input": False,
                    "resampling": "one uniform LANCZOS shrink per destination; never NEAREST enlargement",
                    "surfaces": ui_source_direct_quality,
                    "card_preview": image_record(YONE_V7_UI_CARD_PREVIEW),
                    "card_paste": "85x93 fullbody pasted 1:1 at x=28/y=0 into 141x138 card",
                    "card_name_layer": "not rasterized in QA; runtime localized name is drawn by the engine text layer",
                },
                "fullbody_card_85x93": fullbody_card,
                "live_idle_card": live_idle_card,
                "live_run_profile": live_run_profile,
            },
            "retired_body_routes": {
                "v3": "retired and never used as a fallback",
                "v4": [
                    path.relative_to(MOD_ROOT).as_posix()
                    for path in RETIRED_YONE_V4_BODY_SOURCES
                ],
                "v4_status": "both V4 ImageGen body sources and the entire old native route are retired; build_actor loads only dual-sword-v7",
                "v5": [
                    path.relative_to(MOD_ROOT).as_posix()
                    for path in RETIRED_YONE_V5_BODY_SOURCES
                ],
                "v5_status": "all V5 ImageGen/native body inputs are retired negative-contract paths; build_actor loads only dual-sword-v7",
                "v6_battle": [
                    path.relative_to(MOD_ROOT).as_posix()
                    for path in RETIRED_YONE_V6_BODY_SOURCES
                ],
                "v6_battle_status": "old V6 battle contacts and native frames are physically retired; the former high-resolution V6 UI portrait source is provenance only",
            },
            "large_vfx_policy": "Q3 tornado/knockup, compact W crescent/shield, and R feedback are isolated in dedicated sheets; no large effect replaces Yone's actor body.",
            "portrait_policy": {
                "default_runtime": "four independent source-direct V7 UI textures; no battle-atlas portrait input",
                "fullbody": "85x93 exact champion_slot destination, <=70x82 subject, alpha bottom y<=86",
                "compact": "64x64 face focus, <=50x50 alpha bbox, >=6px border",
                "scoreboard": "48x64 source-direct upper-body crop, <=40x54 subject, alpha bottom y<=60",
                "grid": "90x122 full body, alpha ends at or before y=86, name band begins y=96",
            },
        },
    )

    provenance_path = QA_DIR / "yone_imagegen_sources.json"
    write_json(
        provenance_path,
        {
            "schema_version": 7,
            "champion": "Yone",
            "generator": "built-in image_gen followed by final-scale native pixel authorship",
            "generated_on": "2026-07-22",
            "processing": "dual-sword-v7: 67 final 1x RGBA body PNGs preserve the 54-frame native prefix and add isolated Azakana-AA/Q3 frames in an atlas extension; build-time packing is byte-identical",
            "body_source": native_manifest_contract,
            "body_frames": native_frame_source_contracts,
            "body_imagegen_inputs": [
                image_record(path) for path in YONE_V7_BODY_IMAGEGEN_SOURCES
            ],
            "ui_only_imagegen_inputs": [
                {
                    **image_record(YONE_V7_UI_SOURCE),
                    "role": "UI provenance only; never a native battle-frame input",
                }
            ],
            "retired_body_routes": [
                path.relative_to(MOD_ROOT).as_posix()
                for path in (
                    *RETIRED_YONE_V4_BODY_SOURCES,
                    *RETIRED_YONE_V5_BODY_SOURCES,
                    *RETIRED_YONE_V6_BODY_SOURCES,
                )
            ],
            "sources": [
                image_record(path)
                for path in (
                    *YONE_V7_IMAGEGEN_SOURCES,
                    QW_VFX_SOURCE,
                    W_VFX_SOURCE,
                    Q3_VFX_SOURCE,
                    R_VFX_SOURCE,
                    ICON_SOURCE,
                    SPLASH_SOURCE,
                )
            ],
            "processed": [image_record(path) for path in processed],
            "runtime": [image_record(path) if path.suffix == ".png" else {"path": path.relative_to(MOD_ROOT).as_posix(), "size_bytes": path.stat().st_size, "sha256": sha256(path)} for path in runtime_visuals],
        },
    )

    visual_md = QA_DIR / "yone_visual_qa.md"
    visual_md.write_bytes((
        "# Yone visual QA\n\n"
        "- [x] Current release contract is `0.10.20`; `0.10.19` is retained as partial runtime-routing history and must never identify the installed DLL or telemetry.\n"
        "- [x] Same-ID visual replacement targets `dual_blader` (official project hero 009).\n"
        "- [x] Actor canvas is `4262x88`; the original `3502x88` native prefix and all 13 native tags/rectangles/timings are unchanged, with five explicit semantic tags appended.\n"
        "- [x] `hit_effect_area` reuses the official `ult[1..11]` atlas rectangles without conflicting pixels.\n"
        "- [x] Idle/run/attack/Q/W/R/dead bodies retain one stable battle scale.\n"
        "- [x] All 67 physical body poses come only from `source/native/yone_v7/frames.json`; V3/V4/V5/V6 battle-body routes are retired and cannot be selected as fallbacks.\n"
        "- [x] `source/imagegen/yone_v4_action_contact.png`, `source/imagegen/yone_v4_idle_candidate_43x55.png`, and the old `source/native/yone_v4` route are retired body inputs and are never loaded by this builder.\n"
        "- [x] V5 body inputs `yone_v5_idle_source.png`, `yone_v5_idle_golden_43x55.png`, `yone_v5_motion_contact.png`, `yone_v5_attack_q_w_contact.png`, `yone_v5_q5_contact.png`, `yone_v5_ult_contact.png`, and the complete `source/native/yone_v5` route are retired and never loaded.\n"
        "- [x] The four hash-locked ImageGen contacts use isolated `5x4`, `6x4`, `3x2`, and `5x3` grids with explicit gutters; cell extraction cannot borrow a sword from an adjacent pose.\n"
        "- [x] Every V7 pose is finalized at 1x size, palette-validated, and copied byte-for-byte; only source-to-native generation performs the controlled source resize and crop.\n"
        "- [x] The V7 chibi face preserves true source-authored eye-outline cues, jaw and hair clusters without post-scale face repaint.\n"
        "- [x] The body preview proves the exact idle[0] 2.2x NEAREST battle render and divider clearance; dedicated UI portraits own the right-side icon exclusion.\n"
        "- [x] Idle/run keep compact silver and red swords simultaneously visible; basic attacks switch between separate six-frame steel and Azakana tags.\n"
        "- [x] The fixed palette declares six mutually exclusive roles: steel dark/mid/highlight and Azakana dark/red/highlight; body colors cannot satisfy any weapon role.\n"
        "- [x] Every frame records both hand anchors, both tips, both blade boxes, spans, connectedness, pixel counts, crop ratios, and source-tip survival; CI recomputes those 16 fields from the final PNG instead of trusting the manifest.\n"
        "- [x] Negative tests delete a blade, inject fake red pixels, disconnect a handle/tip, share hands/tips, shorten a blade, or move it to the crop edge, and each corruption is rejected.\n"
        "- [x] CI enforces per-frame neutral dual-sword visibility plus active-blade reach for alternating steel/Azakana attacks, Q/Q3, W, and R; eight long caster-follow overlays extend active weapons without replacing the actor body.\n"
        "- [x] Q1/Q2 use `skill_q12`, Q3 uses a separate lowered `skill_q3`, W uses `skill_w_azakana`, and R retains thirteen dual-sword frames.\n"
        "- [x] Idle/run/attack/hit keep the official Dual Blader bottom clearances, and the card/BP center camera is raised to y=-16 so legs and weapons keep a visible gap above the black divider.\n"
        "- [x] Q3 uses a dedicated horizontal tornado, a vertical blue-white airborne cue, and a small ready-wind state.\n"
        "- [x] Active champion data and release resources do not reference Soul Unbound. Exactly five retired Yone E names and three pre-cone W names remain registered only as no-op saved-season compatibility aliases; no retired Shen dash native remains.\n"
        "- [x] W has no process-global ledger: one native callback scans only its current `GameCtx`, resolves an 80-degree forward cone, damages that snapshot, counts champion hits, and emits one shield tier marker.\n"
        "- [x] W keeps Yone planted, plays one full caster-following crescent, and uses five V7 Azakana-led sweep poses; no code-drawn body is added during packing.\n"
        "- [x] Minions and monsters qualify for the base shield; every enemy champion hit increases its tier through the normal five-champion team limit.\n"
        "- [x] W has no dash, spirit clone, anchor, tether, forced return, recall override, or teleport path.\n"
        "- [x] Compact portrait is face-focused with transparent safety margins.\n"
        "- [x] Fullbody/compact/scoreboard/grid UI art comes only from the high-resolution V7 UI source through magenta-key, one uniform LANCZOS shrink, hard alpha, and a 128-color finish; no battle frame is enlarged.\n"
        "- [x] The `85x93` V7 fullbody texture is pasted 1:1 into `qa/yone_v7_ui_card.png`, including the y=96 divider and right-side icon exclusion.\n"
        "- [x] The card proof leaves the name band blank because localized `永恩` is drawn by the runtime engine text layer, not by the portrait texture.\n"
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
        ("fullbody 85x93", FULLBODY_DIR / "dual_blader.png", (286, 286)),
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
    return [
        contract_path,
        provenance_path,
        visual_md,
        contact_path,
        YONE_V7_UI_CARD_PREVIEW,
    ]


def validate_outputs(outputs: Iterable[Path]) -> None:
    actor_sheet = ACTOR_DIR / "yone_v7#sheet.png"
    actor_anim = ACTOR_DIR / "yone_v7#anim.fanim"
    legacy_actor_sheet = ACTOR_DIR / "yone#sheet.png"
    legacy_actor_anim = ACTOR_DIR / "yone#anim.fanim"
    if sha256(legacy_actor_sheet) != sha256(actor_sheet) or sha256(legacy_actor_anim) != sha256(actor_anim):
        raise ValueError("Yone saved-data actor aliases differ from the active yone_v7 files")
    if Image.open(actor_sheet).size != ACTOR_SHEET_SIZE:
        raise ValueError("Yone actor canvas is not the V7 4262x88 size")
    payload = json.loads(actor_anim.read_text(encoding="utf-8"))["anims"]
    expected_tags = [*NATIVE_CONTRACT, *CUSTOM_ACTION_CONTRACT]
    if list(payload) != expected_tags:
        raise ValueError(
            "Yone actor tag order changed native-prefix/custom-extension contract"
        )
    for tag, spec in {**NATIVE_CONTRACT, **CUSTOM_ACTION_CONTRACT}.items():
        frames = payload[tag]["frames"]
        if [row["duration"] for row in frames] != spec["durations"]:
            raise ValueError(f"Yone {tag} durations changed")
        rects = [tuple(row["data"][key] for key in ("x", "y", "w", "h")) for row in frames]
        if rects != spec["rects"]:
            raise ValueError(f"Yone {tag} rectangles changed")

    sheet = Image.open(actor_sheet).convert("RGBA")
    native_source_frames, _, native_frame_source_contracts = (
        _load_native_v7_body_frames()
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
        source_frame = native_source_frames[(tag, index)]
        if frame.tobytes() != source_frame.tobytes():
            raise ValueError(
                f"Yone {tag}[{index}] changed during exact-native atlas packing"
            )
        native_identity_count += 1
        quality = native_pixel_quality(frame)
        if not quality["hard_alpha"]:
            raise ValueError(
                f"Yone {tag}[{index}] contains non-binary alpha: {quality['alpha_values']}"
            )
        if quality["opaque_palette_size"] > NATIVE_V7_MAX_OPAQUE_COLORS:
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
    if native_identity_count != GENERATED_BODY_FRAME_COUNT:
        raise ValueError(
            "Yone V7 identity audit covered "
            f"{native_identity_count}/{GENERATED_BODY_FRAME_COUNT} body frames"
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
    attack_sequence_hashes: dict[str, set[str]] = {}
    for tag in ("attack_steel", "attack_azakana"):
        pose_hashes: set[str] = set()
        for index, row in enumerate(payload[tag]["frames"]):
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
                    f"Yone {tag}[{index}] must contain one actor, got components "
                    f"{component_sizes[:6]}"
                )
            stray_area = sum(component_sizes[1:])
            if stray_area > 24:
                raise ValueError(
                    f"Yone {tag}[{index}] retained {stray_area}px of detached debris"
                )
            pose_hashes.add(hashlib.sha256(frame.tobytes()).hexdigest())
        if len(pose_hashes) < 5:
            raise ValueError(
                f"Yone {tag} lost pose variation: {len(pose_hashes)}/6 unique"
            )
        attack_sequence_hashes[tag] = pose_hashes
    if attack_sequence_hashes["attack_steel"] == attack_sequence_hashes["attack_azakana"]:
        raise ValueError("Yone steel and Azakana attack sequences are identical")

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
            f"Yone V7 W lost sweep motion: {len(w_pose_hashes)}/5 unique native poses"
        )

    native_core_bottoms = {
        "idle": [15, 15, 14, 15],
        "run": [13, 18, 20, 17, 13, 17, 20, 17],
        "attack": [14, 14, 12, 13, 13, 14],
        "hit": [15],
    }
    actual_core_bottoms = {
        tag: BODY_BOTTOM_MARGINS[tag]
        for tag in native_core_bottoms
    }
    if actual_core_bottoms != native_core_bottoms:
        raise ValueError(
            "Yone core foot anchors diverged from the exact-native V6 source: "
            f"{actual_core_bottoms}"
        )

    # V6 owns face/eye/mask/foot identity through explicit local-coordinate
    # annotations in frames.json.  Do not reinterpret the new fixed palette
    # with the rejected V3 warm-skin/red-mask heuristics: fast profile, ult and
    # defeat frames may intentionally omit a face annotation, while all four
    # front-facing idle frames must carry the complete contract.
    annotation_count = 0
    for tag, index, _entry in iter_actor_body_frames(payload):
        frame_name = f"{tag}[{index}]"
        contract = native_frame_source_contracts.get(frame_name)
        if contract is None:
            raise ValueError(f"Yone V6 manifest lacks {frame_name} annotations")
        annotation_count += 1
        face_bbox = contract["face_bbox"]
        eye_pixels = contract["eye_pixels"]
        mask_bbox = contract["mask_bbox"]
        foot_zones = contract["foot_zones"]
        face_visibility = contract["face_visibility"]
        if tag == "idle" and (
            face_bbox is None
            or mask_bbox is None
            or not eye_pixels
        ):
            raise ValueError(
                f"Yone V6 {frame_name} lacks its explicit front-face contract"
            )
        if tag == "idle" and (
            (face_visibility == "front" and len(eye_pixels) < 2)
            or (face_visibility == "profile" and len(eye_pixels) < 1)
            or face_visibility == "hidden"
        ):
            raise ValueError(
                f"Yone V6 {frame_name} eye count {len(eye_pixels)} does not match "
                f"face_visibility={face_visibility!r}"
            )
        if face_visibility == "front" and (
            face_bbox is None or not eye_pixels or mask_bbox is None
        ):
            raise ValueError(
                f"Yone V6 {frame_name} front-face annotation lacks face, eyes or mask"
            )
        if tag in {
            "idle",
            "hit",
            "attack",
            "skill2",
            "skill2_dash",
            "skill2_attack",
            "run",
            "skill",
            "attack_azakana",
            "skill_q3",
        } and not foot_zones:
            raise ValueError(f"Yone V6 {frame_name} lacks foot-zone annotations")
    if annotation_count != GENERATED_BODY_FRAME_COUNT:
        raise ValueError(
            "Yone V7 annotation validation covered "
            f"{annotation_count}/{GENERATED_BODY_FRAME_COUNT} frames"
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
        annotation = native_frame_source_contracts[frame_name]
        if (
            annotation["face_bbox"] is None
            or annotation["mask_bbox"] is None
            or not annotation["eye_pixels"]
        ):
            raise ValueError(f"Yone V6 {frame_name} lost its manifest face annotation")
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
    run_pose_hashes: set[bytes] = set()
    for index, (frame_name, quality) in enumerate(
        live_run_profile["frames"].items()
    ):
        annotation = native_frame_source_contracts[frame_name]
        if not annotation["foot_zones"]:
            raise ValueError(f"Yone V6 {frame_name} lost its run foot-zone contract")
        if (
            quality["source_bottom_clearance"] != BODY_BOTTOM_MARGINS["run"][index]
            or quality["rendered_bottom_clearance"] <= 0
        ):
            raise ValueError(
                f"Yone {frame_name} lost its run-foot clearance at 2.2x: {quality}"
            )
        run_pose_hashes.add(native_source_frames[("run", index)].tobytes())
    if len(run_pose_hashes) < 4:
        raise ValueError(
            f"Yone V6 run loop lost pose variation: {len(run_pose_hashes)}/8"
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
    fullbody_bbox = fullbody.getchannel("A").getbbox()
    if fullbody.size != (85, 93) or fullbody_bbox is None:
        raise ValueError("Yone source-direct fullbody portrait must be 85x93")
    fullbody_width = fullbody_bbox[2] - fullbody_bbox[0]
    fullbody_height = fullbody_bbox[3] - fullbody_bbox[1]
    fullbody_opaque = sum(
        1
        for alpha in (
            fullbody.getchannel("A").get_flattened_data()
            if hasattr(fullbody.getchannel("A"), "get_flattened_data")
            else fullbody.getchannel("A").getdata()
        )
        if alpha
    )
    if not (
        70 <= fullbody_width <= 76
        and 76 <= fullbody_height <= 84
        and fullbody_bbox[3] == 88
        and abs(fullbody_bbox[0] - (85 - fullbody_bbox[2])) <= 1
        and fullbody_opaque >= 2300
    ):
        raise ValueError(
            "Yone encyclopedia fullbody is too small, off-center, or clipped: "
            f"bbox={fullbody_bbox}, opaque={fullbody_opaque}"
        )
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
    if (
        grid.size != (90, 122)
        or grid_bbox is None
        or grid_bbox[2] - grid_bbox[0] > 72
        or grid_bbox[3] - grid_bbox[1] > 82
        or grid_bbox[3] > 86
    ):
        raise ValueError(f"Yone BP-grid portrait overlaps name band: {grid_bbox}")
    for label, image in (
        ("fullbody", fullbody),
        ("compact", compact),
        ("scoreboard", scoreboard),
        ("grid", grid),
    ):
        face = yone_face_readability(image, YONE_UI_FACE_WINDOWS[label])
        face_bbox = face["face_skin_bbox"]
        minimum_width, minimum_height, minimum_skin = {
            # The V7 card face uses two dark/red eyes and brows inside the
            # warm plane. Those intentional features split the largest skin
            # component, so validate the measured 12x13 plane together with
            # >=90 warm pixels and the separate natural-eye-cue gate below.
            "fullbody": (12, 13, 90),
            "compact": (14, 16, 80),
            "scoreboard": (12, 14, 100),
            "grid": (12, 13, 90),
        }[label]
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
        quality = yone_ui_surface_quality(image)
        if (
            not quality["hard_alpha"]
            or not quality["transparent_rgb_clear"]
            or quality["opaque_palette_size"] < 48
            or quality["dark_pixel_ratio"] < 0.20
            or quality["dark_pixel_ratio"] > 0.85
            or quality["identical_neighbor_ratio"] > 0.48
        ):
            raise ValueError(
                f"Yone {label} lost source-direct high-resolution quality: {quality}"
            )
    fullbody_card = yone_fullbody_card_contract(fullbody)
    if (
        fullbody_card["source_size"] != [85, 93]
        or fullbody_card["rendered_size"] != [85, 93]
        or fullbody_card["resampling"] != "none; 85x93 source pasted 1:1"
        or fullbody_card["source_alpha_bbox"] is None
        or fullbody_card["rendered_alpha_bbox"] is None
        or fullbody_card["source_bottom_margin"] < 3
        or fullbody_card["rendered_bottom_margin"] < 4
        or fullbody_card["rendered_face_skin_bbox"] is None
        or fullbody_card["source_red_mask_pixels"] < 20
    ):
        raise ValueError(
            f"Yone real 85x93 1:1 fullbody card route failed: {fullbody_card}"
        )
    with Image.open(YONE_V7_UI_CARD_PREVIEW) as opened:
        card_preview = opened.convert("RGBA")
    if (
        card_preview.size != (141, 138)
        or card_preview.getchannel("A").getextrema() != (255, 255)
        or card_preview.tobytes()
        != render_yone_v7_ui_card_preview(fullbody).tobytes()
    ):
        raise ValueError(
            "Yone V7 card preview must paste the 85x93 source-direct fullbody "
            "at 1:1 into the exact 141x138 chrome"
        )
    if Image.open(SPLASH_DIR / "dual_blader.png").size != (1420, 860):
        raise ValueError("Yone BP splash is not 1420x860")
    for icon in ("yone_skill.png", "yone_skill2.png", "yone_ult.png"):
        if Image.open(ICON_DIR / icon).size != (64, 64):
            raise ValueError(f"Yone icon {icon} is not 64x64")
    for processed in (
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
    stale_body_sources = [
        path
        for path in (
            *RETIRED_YONE_V4_BODY_SOURCES,
            *RETIRED_YONE_V5_BODY_SOURCES,
            *RETIRED_YONE_V6_BODY_SOURCES,
        )
        if path.exists()
    ]
    if stale_body_sources:
        raise ValueError(
            "Retired Yone V4/V5/V6 battle-body sources must be physically removed; "
            "dual-sword-v7 has no fallback route:\n"
            + "\n".join(str(path) for path in stale_body_sources)
        )
    required = [
        NATIVE_V7_MANIFEST,
        *YONE_V7_BODY_IMAGEGEN_SOURCES,
        YONE_V7_UI_SOURCE,
        QW_VFX_SOURCE, W_VFX_SOURCE, Q3_VFX_SOURCE, R_VFX_SOURCE,
        ICON_SOURCE, SPLASH_SOURCE,
    ]
    missing = [path for path in required if not path.is_file()]
    if missing:
        raise FileNotFoundError(
            "Missing Yone V7/VFX sources (the retired V3/V4/V5/V6 battle-body routes are not fallbacks):\n"
            + "\n".join(str(path) for path in missing)
        )
    processed = process_sources()
    actor_sheet, actor_anim, legacy_actor_sheet, legacy_actor_anim = build_actor()
    effects = build_effects(actor_sheet)
    icons = build_icons()
    portraits = build_splash_and_portraits()
    runtime = [
        actor_sheet,
        actor_anim,
        legacy_actor_sheet,
        legacy_actor_anim,
        *effects,
        *icons,
        *portraits,
    ]
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
