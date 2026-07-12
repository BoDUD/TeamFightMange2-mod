#!/usr/bin/env python3
"""Deterministically pack the image-gen Kled art into native TFM2 resources.

This module intentionally owns only Kled's visual assets.  It does not import
``build_lol_mod`` so the main builder can call :func:`build_all` without a
circular dependency.
"""

from __future__ import annotations

import hashlib
import json
import struct
import zlib
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw


MOD_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = MOD_ROOT / "source"
PROCESSED_ROOT = SOURCE_ROOT / "processed"
IMAGEGEN_ROOT = SOURCE_ROOT / "imagegen"
ACTOR_DIR = MOD_ROOT / "aseprite_resources" / "champions"
EFFECT_DIR = MOD_ROOT / "aseprite_resources" / "effects"
ICON_DIR = MOD_ROOT / "icons"
SPLASH_DIR = MOD_ROOT / "BanPickIllust"
FULLBODY_DIR = MOD_ROOT / "ui" / "champion_fullbody"
QA_DIR = MOD_ROOT / "qa"

ACTOR_SOURCE = PROCESSED_ROOT / "kled_actor_contact_alpha.png"
RUN_SOURCE = PROCESSED_ROOT / "kled_run_contact_alpha.png"
DEFEAT_SOURCE = PROCESSED_ROOT / "kled_defeat_contact_alpha.png"
Q_VFX_SOURCE = PROCESSED_ROOT / "kled_q_vfx_contact_v2_alpha.png"
E_VFX_SOURCE = PROCESSED_ROOT / "kled_e_vfx_contact_alpha.png"
R_VFX_SOURCE = PROCESSED_ROOT / "kled_r_vfx_contact_v2_alpha.png"
Q_ICON_SOURCE = IMAGEGEN_ROOT / "kled_q_icon_source_v2.png"
E_ICON_SOURCE = IMAGEGEN_ROOT / "kled_e_icon_source.png"
R_ICON_SOURCE = IMAGEGEN_ROOT / "kled_r_icon_source.png"
SPLASH_SOURCE = IMAGEGEN_ROOT / "bp_splash" / "cavalry_knight.png"

ACTOR_SHEET_SIZE = (4096, 189)


# Exact frame rectangles and durations from native champion 006/Cavalry Knight.
# Dict insertion order is the runtime tag contract and must never be sorted.
NATIVE_CONTRACT: dict[str, dict[str, Any]] = {
    "fire_skill1_pre": {
        "durations": [0.080000006] * 2,
        "rects": [(3056, 0, 43, 57), (3100, 0, 47, 63)],
    },
    "ult_self_effect_back": {
        "durations": [0.040000003] * 14,
        "rects": [(672 + index * 4, 119, 3, 3) for index in range(14)],
    },
    "skill1_dash": {
        "durations": [0.080000006],
        "rects": [(1314, 0, 53, 55)],
    },
    "ult_road_effect": {
        "durations": [0.080000006] * 9,
        "rects": [(728 + index * 36, 119, 35, 69) for index in range(9)],
    },
    "fire_skill1": {
        "durations": [0.080000006] * 3,
        "rects": [(3056, 0, 43, 57), (3100, 0, 47, 63), (3148, 0, 55, 55)],
    },
    "skill1": {
        "durations": [0.080000006] * 3,
        "rects": [(1224, 0, 43, 57), (1268, 0, 45, 63), (1314, 0, 53, 55)],
    },
    "skill2": {
        "durations": [0.080000006] * 3,
        "rects": [(1744, 0, 45, 69), (1790, 0, 45, 67), (1836, 0, 45, 67)],
    },
    "fire_attack": {
        "durations": [0.080000006] * 4,
        "rects": [(2430, 0, 43, 61), (2474, 0, 47, 63), (2522, 0, 67, 55), (2590, 0, 61, 55)],
    },
    "fire_run": {
        "durations": [0.060000002] * 8,
        "rects": [
            (2066, 0, 47, 53),
            (2114, 0, 45, 55),
            (2160, 0, 45, 57),
            (2206, 0, 43, 57),
            (2250, 0, 41, 57),
            (2292, 0, 43, 55),
            (2336, 0, 45, 55),
            (2382, 0, 47, 55),
        ],
    },
    "fire_skill1_end": {
        "durations": [0.080000006],
        "rects": [(3204, 0, 53, 55)],
    },
    "fire_skill1_effect": {
        "durations": [0.080000006] * 4,
        "rects": [(3258, 0, 83, 19), (3342, 0, 81, 25), (3424, 0, 79, 25), (3504, 0, 77, 25)],
    },
    "run": {
        "durations": [0.060000002] * 8,
        "rects": [
            (230, 0, 47, 53),
            (278, 0, 45, 55),
            (324, 0, 45, 57),
            (370, 0, 43, 57),
            (414, 0, 41, 57),
            (456, 0, 43, 55),
            (500, 0, 45, 55),
            (546, 0, 47, 55),
        ],
    },
    "idle": {
        "durations": [0.14] * 4,
        "rects": [(46, 0, 45, 61), (92, 0, 45, 59), (138, 0, 45, 57), (184, 0, 45, 59)],
    },
    "attack": {
        "durations": [0.080000006] * 4,
        "rects": [(594, 0, 43, 61), (638, 0, 45, 63), (684, 0, 77, 55), (762, 0, 57, 55)],
    },
    "dead": {
        "durations": [0.1] * 10,
        "rects": [
            (860, 0, 39, 57),
            (900, 0, 39, 55),
            (940, 0, 39, 53),
            (980, 0, 39, 51),
            (1020, 0, 39, 49),
            (1060, 0, 39, 49),
            (1100, 0, 39, 49),
            (1140, 0, 39, 49),
            (1180, 0, 39, 49),
            (1220, 0, 3, 3),
        ],
    },
    "fire_skill1_dash": {
        "durations": [0.080000006],
        "rects": [(3148, 0, 55, 55)],
    },
    "skill1_effect": {
        "durations": [0.080000006] * 4,
        "rects": [(1420, 0, 83, 19), (1504, 0, 81, 25), (1586, 0, 79, 25), (1666, 0, 77, 25)],
    },
    "fire_dead": {
        "durations": [0.1] * 11,
        "rects": [
            (2652, 0, 39, 59),
            (2692, 0, 39, 57),
            (2732, 0, 39, 55),
            (2772, 0, 39, 53),
            (2812, 0, 39, 51),
            (2852, 0, 39, 49),
            (2892, 0, 39, 49),
            (2932, 0, 39, 49),
            (2972, 0, 39, 49),
            (3012, 0, 39, 49),
            (3052, 0, 3, 3),
        ],
    },
    "ult_self_effect": {
        "durations": [0.040000003] * 14,
        "rects": [
            (3938, 0, 55, 67),
            (3994, 0, 55, 67),
            *[(index * 56, 119, 55, 67) for index in range(12)],
        ],
    },
    "ult": {
        "durations": [0.080000006] * 4,
        "rects": [(3582, 0, 65, 61), (3648, 0, 83, 77), (3732, 0, 107, 103), (3840, 0, 97, 119)],
    },
    "hit": {
        "durations": [0.1],
        "rects": [(820, 0, 39, 59)],
    },
    "skill1_end": {
        "durations": [0.080000006],
        "rects": [(1368, 0, 51, 55)],
    },
    "fire_idle": {
        "durations": [0.14] * 4,
        "rects": [(1882, 0, 45, 61), (1928, 0, 45, 59), (1974, 0, 45, 57), (2020, 0, 45, 59)],
    },
    "skill1_pre": {
        "durations": [0.080000006] * 2,
        "rects": [(1224, 0, 43, 57), (1268, 0, 45, 63)],
    },
}


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


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
    adler_a = 1
    adler_b = 0
    for start in range(0, len(data), 5552):
        for value in data[start : start + 5552]:
            adler_a += value
            adler_b += adler_a
        adler_a %= 65521
        adler_b %= 65521
    stream.extend(struct.pack(">I", (adler_b << 16) | adler_a))
    return bytes(stream)


def save_png(path: Path, image: Image.Image) -> None:
    """Write canonical RGBA PNG bytes independent of Pillow's zlib build."""
    path.parent.mkdir(parents=True, exist_ok=True)
    rgba = image.convert("RGBA")
    raw = bytearray()
    pixels = rgba.tobytes()
    stride = rgba.width * 4
    for y in range(rgba.height):
        raw.append(0)
        raw.extend(pixels[y * stride : (y + 1) * stride])
    ihdr = struct.pack(">IIBBBBB", rgba.width, rgba.height, 8, 6, 0, 0, 0)
    encoded = (
        b"\x89PNG\r\n\x1a\n"
        + _png_chunk(b"IHDR", ihdr)
        + _png_chunk(b"IDAT", _stored_zlib(bytes(raw)))
        + _png_chunk(b"IEND", b"")
    )
    path.write_bytes(encoded)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def split_grid(image: Image.Image, columns: int, rows: int) -> list[Image.Image]:
    xs = [round(index * image.width / columns) for index in range(columns + 1)]
    ys = [round(index * image.height / rows) for index in range(rows + 1)]
    return [
        image.crop((xs[column], ys[row], xs[column + 1], ys[row + 1]))
        for row in range(rows)
        for column in range(columns)
    ]


def hard_alpha(image: Image.Image, threshold: int = 56) -> Image.Image:
    rgba = image.convert("RGBA")
    alpha = rgba.getchannel("A").point(lambda value: 255 if value >= threshold else 0)
    rgba.putalpha(alpha)
    pixels = rgba.load()
    for y in range(rgba.height):
        for x in range(rgba.width):
            if pixels[x, y][3] == 0:
                pixels[x, y] = (0, 0, 0, 0)
    return rgba


def palette_finish(image: Image.Image, colors: int = 48) -> Image.Image:
    opaque = hard_alpha(image)
    quantized = opaque.quantize(colors=colors, method=Image.Quantize.FASTOCTREE).convert("RGBA")
    quantized.putalpha(opaque.getchannel("A"))
    return hard_alpha(quantized, 128)


def prune_tiny_alpha_components(image: Image.Image, min_pixels: int = 3) -> Image.Image:
    """Drop isolated resampling flecks while retaining weapons and limbs."""
    rgba = hard_alpha(image)
    alpha = rgba.getchannel("A")
    remaining = {
        (x, y)
        for y in range(rgba.height)
        for x in range(rgba.width)
        if alpha.getpixel((x, y)) >= 128
    }
    kept: set[tuple[int, int]] = set()
    while remaining:
        seed = remaining.pop()
        component = {seed}
        stack = [seed]
        while stack:
            x, y = stack.pop()
            for neighbor in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
                if neighbor in remaining:
                    remaining.remove(neighbor)
                    component.add(neighbor)
                    stack.append(neighbor)
        if len(component) >= min_pixels:
            kept.update(component)
    output = Image.new("RGBA", rgba.size, (0, 0, 0, 0))
    source_pixels = rgba.load()
    output_pixels = output.load()
    for x, y in kept:
        output_pixels[x, y] = source_pixels[x, y]
    return output


def alpha_bbox(image: Image.Image) -> tuple[int, int, int, int]:
    bbox = image.getchannel("A").point(lambda value: 255 if value >= 64 else 0).getbbox()
    if bbox is None:
        raise ValueError("Kled source cell has no visible pixels")
    return bbox


def fit_actor(
    source: Image.Image,
    frame_size: tuple[int, int],
    *,
    target_height: int,
    baseline: int,
    max_width: int | None = None,
) -> Image.Image:
    """Fit one mounted pose while keeping a stable 36-40px battle scale.

    Long spears and Skaarl's tail make several generated poses wider than the
    narrow native 006 cells.  Height is therefore fixed first and only the x
    axis is compressed when necessary; this keeps the actor from visibly
    shrinking between idle/run/attack frames.
    """
    source = hard_alpha(source)
    subject = source.crop(alpha_bbox(source))
    target_height = min(target_height, frame_size[1] - 2, baseline)
    width = max(1, round(subject.width * target_height / subject.height))
    width = min(width, max_width or frame_size[0] - 2, frame_size[0] - 2)
    resized = subject.resize((width, target_height), Image.Resampling.LANCZOS)
    resized = palette_finish(resized, 48)
    resized = prune_tiny_alpha_components(resized)
    output = Image.new("RGBA", frame_size, (0, 0, 0, 0))
    x = (frame_size[0] - resized.width) // 2
    y = max(0, min(frame_size[1] - resized.height, baseline - resized.height))
    output.alpha_composite(resized, (x, y))
    return output


def fit_effect(
    source: Image.Image,
    frame_size: tuple[int, int],
    *,
    padding: int = 3,
    bottom_anchor: bool = False,
) -> Image.Image:
    source = hard_alpha(source)
    subject = source.crop(alpha_bbox(source))
    max_width = max(1, frame_size[0] - padding * 2)
    max_height = max(1, frame_size[1] - padding * 2)
    scale = min(max_width / subject.width, max_height / subject.height)
    resized = subject.resize(
        (max(1, round(subject.width * scale)), max(1, round(subject.height * scale))),
        Image.Resampling.LANCZOS,
    )
    resized = palette_finish(resized, 56)
    output = Image.new("RGBA", frame_size, (0, 0, 0, 0))
    x = (frame_size[0] - resized.width) // 2
    y = frame_size[1] - padding - resized.height if bottom_anchor else (frame_size[1] - resized.height) // 2
    output.alpha_composite(resized, (x, y))
    return output


def _paste_unique(
    sheet: Image.Image,
    placements: dict[tuple[int, int, int, int], bytes],
    rect: tuple[int, int, int, int],
    frame: Image.Image,
) -> None:
    x, y, width, height = rect
    if frame.size != (width, height):
        raise ValueError(f"frame {frame.size} does not match native rect {rect}")
    pixels = frame.tobytes()
    previous = placements.get(rect)
    if previous is not None:
        if previous != pixels:
            raise ValueError(f"overlapping native rect {rect} was assigned two different frames")
        return
    placements[rect] = pixels
    sheet.alpha_composite(frame, (x, y))


def _rects(tag: str) -> list[tuple[int, int, int, int]]:
    return NATIVE_CONTRACT[tag]["rects"]


def build_actor() -> tuple[Path, Path, list[Image.Image]]:
    actor_cells = split_grid(Image.open(ACTOR_SOURCE).convert("RGBA"), 4, 4)
    run_cells = split_grid(Image.open(RUN_SOURCE).convert("RGBA"), 3, 3)
    defeat_cells = split_grid(Image.open(DEFEAT_SOURCE).convert("RGBA"), 2, 2)
    q_cells = split_grid(Image.open(Q_VFX_SOURCE).convert("RGBA"), 4, 2)
    e_cells = split_grid(Image.open(E_VFX_SOURCE).convert("RGBA"), 4, 2)
    r_cells = split_grid(Image.open(R_VFX_SOURCE).convert("RGBA"), 4, 2)

    sheet = Image.new("RGBA", ACTOR_SHEET_SIZE, (0, 0, 0, 0))
    placements: dict[tuple[int, int, int, int], bytes] = {}
    representative_frames: list[Image.Image] = []

    def place_actor_sequence(
        tag: str,
        sources: Iterable[Image.Image],
        *,
        target_height: int,
        baseline: int,
    ) -> None:
        source_rows = list(sources)
        rect_rows = _rects(tag)
        if len(source_rows) != len(rect_rows):
            raise ValueError(f"{tag}: {len(source_rows)} sources for {len(rect_rows)} native frames")
        for rect, source in zip(rect_rows, source_rows, strict=True):
            frame = fit_actor(
                source,
                (rect[2], rect[3]),
                target_height=target_height,
                baseline=min(baseline, rect[3] - 1),
            )
            _paste_unique(sheet, placements, rect, frame)
            representative_frames.append(frame)

    idle = actor_cells[0:4]
    attack = actor_cells[4:8]
    skill1 = [actor_cells[index] for index in (8, 9, 10)]
    skill2 = [actor_cells[index] for index in (12, 13, 14)]
    run = run_cells[:8]

    place_actor_sequence("idle", idle, target_height=40, baseline=45)
    place_actor_sequence("fire_idle", idle, target_height=40, baseline=45)
    place_actor_sequence("run", run, target_height=38, baseline=43)
    place_actor_sequence("fire_run", run, target_height=38, baseline=43)
    place_actor_sequence("attack", attack, target_height=40, baseline=45)
    place_actor_sequence("fire_attack", attack, target_height=40, baseline=45)
    place_actor_sequence("skill1", skill1, target_height=39, baseline=45)
    place_actor_sequence("fire_skill1", skill1, target_height=39, baseline=45)
    place_actor_sequence("skill2", skill2, target_height=40, baseline=45)
    place_actor_sequence("hit", [actor_cells[15]], target_height=38, baseline=44)
    place_actor_sequence("skill1_end", [actor_cells[7]], target_height=39, baseline=45)
    place_actor_sequence("fire_skill1_end", [actor_cells[7]], target_height=39, baseline=45)
    place_actor_sequence("ult", [run_cells[index] for index in (3, 4, 5, 6)], target_height=40, baseline=46)

    # Dead rows retain native frame counts and finish with the mandatory empty
    # 3x3 terminal frame. Repeated late poses make the fall settle instead of
    # snapping back to a standing contact.
    dead_sources = [defeat_cells[index] for index in (0, 0, 1, 1, 2, 2, 3, 3, 3)]
    for tag, visible_sources in (
        ("dead", dead_sources),
        ("fire_dead", [*dead_sources, defeat_cells[3]]),
    ):
        for index, (rect, source) in enumerate(zip(_rects(tag), visible_sources, strict=False)):
            frame = fit_actor(
                source,
                (rect[2], rect[3]),
                target_height=max(28, 36 - index),
                baseline=min(44, rect[3] - 1),
            )
            _paste_unique(sheet, placements, rect, frame)
            representative_frames.append(frame)
        # The final native rect is intentionally left transparent.

    # Reused pre/dash rects already contain the corresponding skill1 bodies.
    # Validate the aliases rather than repainting them with subtly different
    # resampling results.
    for alias, owner, owner_indexes in (
        ("skill1_pre", "skill1", (0, 1)),
        ("skill1_dash", "skill1", (2,)),
        ("fire_skill1_pre", "fire_skill1", (0, 1)),
        ("fire_skill1_dash", "fire_skill1", (2,)),
    ):
        expected = [_rects(owner)[index] for index in owner_indexes]
        if _rects(alias) != expected:
            raise ValueError(f"native alias {alias} no longer matches {owner}")

    def place_effect_sequence(tag: str, cells: list[Image.Image]) -> None:
        if len(cells) != len(_rects(tag)):
            raise ValueError(f"{tag}: incorrect effect frame count")
        for rect, cell in zip(_rects(tag), cells, strict=True):
            frame = fit_effect(cell, (rect[2], rect[3]), padding=1, bottom_anchor=True)
            _paste_unique(sheet, placements, rect, frame)

    place_effect_sequence("skill1_effect", [q_cells[index] for index in (1, 2, 3, 5)])
    place_effect_sequence("fire_skill1_effect", [e_cells[index] for index in (0, 1, 2, 3)])
    place_effect_sequence("ult_road_effect", [r_cells[index] for index in (0, 1, 2, 3, 4, 5, 6, 7, 6)])
    place_effect_sequence(
        "ult_self_effect",
        [r_cells[index] for index in (4, 5, 6, 7, 6, 5, 4, 5, 6, 7, 6, 5, 4, 7)],
    )

    sheet_path = ACTOR_DIR / "kled#sheet.png"
    anim_path = ACTOR_DIR / "kled#anim.fanim"
    save_png(sheet_path, sheet)
    anims: dict[str, Any] = {}
    for tag, spec in NATIVE_CONTRACT.items():
        anims[tag] = {
            "frames": [
                {
                    "duration": duration,
                    "data": {"x": x, "y": y, "w": width, "h": height},
                }
                for duration, (x, y, width, height) in zip(
                    spec["durations"], spec["rects"], strict=True
                )
            ]
        }
    write_json(anim_path, {"anims": anims})
    return sheet_path, anim_path, representative_frames


def _effect_anim(
    frame_size: tuple[int, int], indexes: Iterable[int], durations: Iterable[float]
) -> dict[str, Any]:
    indexes = list(indexes)
    durations = list(durations)
    if len(indexes) != len(durations):
        raise ValueError("effect animation index/duration mismatch")
    return {
        "frames": [
            {
                "duration": duration,
                "data": {
                    "x": index * frame_size[0],
                    "y": 0,
                    "w": frame_size[0],
                    "h": frame_size[1],
                },
            }
            for index, duration in zip(indexes, durations, strict=True)
        ]
    }


EFFECT_SPECS: dict[str, dict[str, Any]] = {
    "kled_q_tether": {
        "source": Q_VFX_SOURCE,
        "frame_size": (96, 48),
        "source_indexes": list(range(8)),
        "tags": {
            "projectile": ([1, 2, 3], [0.05, 0.06, 0.08]),
            "latch": ([3, 4], [0.07, 0.11]),
            "pull": ([5, 6, 7], [0.05, 0.07, 0.12]),
            "tether_pre": ([3, 4], [0.07, 0.09]),
            "tether_loop": ([4, 5, 4, 5], [0.16, 0.16, 0.16, 0.16]),
            "tether_remove": ([5, 6, 7], [0.07, 0.09, 0.13]),
        },
    },
    "kled_e_joust": {
        "source": E_VFX_SOURCE,
        "frame_size": (96, 48),
        "source_indexes": list(range(8)),
        "tags": {
            "dash": ([0, 1, 2, 3], [0.05, 0.06, 0.07, 0.09]),
            "impact": ([4, 5, 6, 7], [0.04, 0.06, 0.08, 0.12]),
        },
    },
    "kled_r_trail": {
        "source": R_VFX_SOURCE,
        "frame_size": (96, 64),
        "source_indexes": list(range(8)),
        "tags": {
            "trail": ([0, 1, 2, 3], [0.08, 0.08, 0.08, 0.08]),
            "charge": ([4, 5, 6, 7], [0.05, 0.06, 0.07, 0.10]),
            "charge_pre": ([0, 4], [0.06, 0.08]),
            "charge_loop": ([4, 5, 6, 7], [0.10, 0.10, 0.10, 0.10]),
            "charge_remove": ([6, 7, 3], [0.07, 0.09, 0.14]),
            "ally_pre": ([0, 1], [0.07, 0.09]),
            "ally_loop": ([1, 2, 3, 2], [0.14, 0.14, 0.14, 0.14]),
            "ally_remove": ([3, 2, 0], [0.07, 0.09, 0.14]),
        },
    },
    "kled_r_impact": {
        "source": R_VFX_SOURCE,
        "frame_size": (96, 64),
        "source_indexes": list(range(8)),
        "tags": {"impact": (list(range(8)), [0.04, 0.05, 0.06, 0.07, 0.08, 0.09, 0.11, 0.16])},
    },
}


def build_effects() -> tuple[list[Path], dict[str, list[Image.Image]]]:
    outputs: list[Path] = []
    contacts: dict[str, list[Image.Image]] = {}
    for name, spec in EFFECT_SPECS.items():
        source_cells = split_grid(Image.open(spec["source"]).convert("RGBA"), 4, 2)
        frame_size = spec["frame_size"]
        frames = [
            fit_effect(source_cells[index], frame_size, padding=5, bottom_anchor=name == "kled_r_trail")
            for index in spec["source_indexes"]
        ]
        atlas = Image.new("RGBA", (frame_size[0] * len(frames), frame_size[1]), (0, 0, 0, 0))
        for index, frame in enumerate(frames):
            atlas.alpha_composite(frame, (index * frame_size[0], 0))
        sheet_path = EFFECT_DIR / f"{name}#sheet.png"
        anim_path = EFFECT_DIR / f"{name}#anim.fanim"
        save_png(sheet_path, atlas)
        anims = {
            tag: _effect_anim(frame_size, indexes, durations)
            for tag, (indexes, durations) in spec["tags"].items()
        }
        write_json(anim_path, {"anims": anims})
        outputs.extend([sheet_path, anim_path])
        contacts[name] = frames
    return outputs, contacts


def cover_crop(image: Image.Image, size: tuple[int, int]) -> Image.Image:
    scale = max(size[0] / image.width, size[1] / image.height)
    resized = image.resize(
        (max(size[0], round(image.width * scale)), max(size[1], round(image.height * scale))),
        Image.Resampling.LANCZOS,
    )
    left = (resized.width - size[0]) // 2
    top = (resized.height - size[1]) // 2
    return resized.crop((left, top, left + size[0], top + size[1])).convert("RGBA")


def build_icons() -> list[Path]:
    outputs: list[Path] = []
    for output_name, source_path in (
        ("kled_skill.png", Q_ICON_SOURCE),
        ("kled_skill2.png", E_ICON_SOURCE),
        ("kled_ult.png", R_ICON_SOURCE),
    ):
        icon = cover_crop(Image.open(source_path).convert("RGBA"), (64, 64))
        icon = palette_finish(icon, 64)
        output = ICON_DIR / output_name
        save_png(output, icon)
        outputs.append(output)
    return outputs


def normalize_splash_source() -> None:
    """Normalize the generated card source to the documented 284:172 ratio."""
    source = Image.open(SPLASH_SOURCE).convert("RGBA")
    target_ratio = 284 / 172
    if abs(source.width / source.height - target_ratio) <= 0.002:
        return
    if source.width / source.height < target_ratio:
        target_height = max(1, round(source.width / target_ratio))
        top = max(0, (source.height - target_height) // 2)
        source = source.crop((0, top, source.width, top + target_height))
    else:
        target_width = max(1, round(source.height * target_ratio))
        left = max(0, (source.width - target_width) // 2)
        source = source.crop((left, 0, left + target_width, source.height))
    save_png(SPLASH_SOURCE, source)


def build_splash_and_fullbody(actor_sheet: Path, actor_anim: Path) -> list[Path]:
    normalize_splash_source()
    splash = cover_crop(Image.open(SPLASH_SOURCE).convert("RGBA"), (1420, 860))
    splash = palette_finish(splash, 256)
    splash_path = SPLASH_DIR / "cavalry_knight.png"
    save_png(splash_path, splash)

    sheet = Image.open(actor_sheet).convert("RGBA")
    anim = json.loads(actor_anim.read_text(encoding="utf-8"))["anims"]
    row = anim["idle"]["frames"][0]["data"]
    frame = sheet.crop((row["x"], row["y"], row["x"] + row["w"], row["y"] + row["h"]))
    subject = frame.crop(alpha_bbox(frame))
    scale = min(54 / subject.width, 58 / subject.height)
    subject = subject.resize(
        (max(1, round(subject.width * scale)), max(1, round(subject.height * scale))),
        Image.Resampling.NEAREST,
    )
    portrait = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    portrait.alpha_composite(subject, ((64 - subject.width) // 2, 62 - subject.height))
    portrait_path = FULLBODY_DIR / "cavalry_knight.png"
    save_png(portrait_path, portrait)
    return [splash_path, portrait_path]


def _contact_background(size: tuple[int, int]) -> Image.Image:
    return Image.new("RGBA", size, (10, 18, 31, 255))


def build_qa_contacts(
    actor_sheet_path: Path,
    actor_anim_path: Path,
    icon_paths: list[Path],
    effect_frames: dict[str, list[Image.Image]],
) -> list[Path]:
    outputs: list[Path] = []
    draw_color = (212, 226, 238, 255)

    sheet = Image.open(actor_sheet_path).convert("RGBA")
    anim = json.loads(actor_anim_path.read_text(encoding="utf-8"))["anims"]
    actor_tags = ("idle", "run", "attack", "skill1", "skill2", "ult", "hit", "dead")
    actor_contact = _contact_background((960, 560))
    draw = ImageDraw.Draw(actor_contact)
    draw.text((16, 10), "KLED / NATIVE 006 ACTOR CONTRACT", fill=draw_color)
    for row_index, tag in enumerate(actor_tags):
        draw.text((16, 48 + row_index * 62), tag, fill=draw_color)
        rows = anim[tag]["frames"]
        for column, frame_row in enumerate(rows[:10]):
            data = frame_row["data"]
            frame = sheet.crop((data["x"], data["y"], data["x"] + data["w"], data["y"] + data["h"]))
            preview = Image.new("RGBA", (72, 56), (7, 13, 23, 255))
            if frame.getchannel("A").getbbox() is not None:
                subject = frame.crop(alpha_bbox(frame))
                scale = min(64 / subject.width, 52 / subject.height, 2.0)
                subject = subject.resize(
                    (max(1, round(subject.width * scale)), max(1, round(subject.height * scale))),
                    Image.Resampling.NEAREST,
                )
                preview.alpha_composite(subject, ((72 - subject.width) // 2, 54 - subject.height))
            actor_contact.alpha_composite(preview, (96 + column * 82, 38 + row_index * 62))
    actor_contact_path = QA_DIR / "kled_actor_contact_final.png"
    save_png(actor_contact_path, actor_contact)
    outputs.append(actor_contact_path)

    icon_contact = _contact_background((640, 220))
    draw = ImageDraw.Draw(icon_contact)
    draw.text((16, 12), "KLED Q / E / R ICONS", fill=draw_color)
    for index, (label, path) in enumerate(zip(("Q", "E", "R"), icon_paths, strict=True)):
        icon = Image.open(path).convert("RGBA").resize((144, 144), Image.Resampling.NEAREST)
        x = 40 + index * 200
        icon_contact.alpha_composite(icon, (x, 48))
        draw.text((x + 66, 198), label, fill=draw_color)
    icon_contact_path = QA_DIR / "kled_skill_icons_final.png"
    save_png(icon_contact_path, icon_contact)
    outputs.append(icon_contact_path)

    vfx_contact = _contact_background((1080, 720))
    draw = ImageDraw.Draw(vfx_contact)
    draw.text((16, 10), "KLED INDEPENDENT Q / E / R EFFECT SHEETS", fill=draw_color)
    for row_index, (name, frames) in enumerate(effect_frames.items()):
        y = 48 + row_index * 132
        draw.text((16, y + 50), name, fill=draw_color)
        for column, frame in enumerate(frames):
            preview = frame.resize((112, 112), Image.Resampling.NEAREST)
            vfx_contact.alpha_composite(preview, (190 + column * 110, y))
    vfx_contact_path = QA_DIR / "kled_vfx_contact_final.png"
    save_png(vfx_contact_path, vfx_contact)
    outputs.append(vfx_contact_path)
    return outputs


def frame_crop(sheet: Image.Image, row: dict[str, Any]) -> Image.Image:
    data = row["data"]
    return sheet.crop((data["x"], data["y"], data["x"] + data["w"], data["y"] + data["h"]))


def self_check(outputs: list[Path]) -> None:
    missing = [path for path in outputs if not path.is_file()]
    if missing:
        raise AssertionError(f"Kled builder did not create: {missing}")

    sheet_path = ACTOR_DIR / "kled#sheet.png"
    anim_path = ACTOR_DIR / "kled#anim.fanim"
    sheet = Image.open(sheet_path).convert("RGBA")
    if sheet.size != ACTOR_SHEET_SIZE:
        raise AssertionError(f"Kled native sheet is {sheet.size}, expected {ACTOR_SHEET_SIZE}")
    anim = json.loads(anim_path.read_text(encoding="utf-8"))["anims"]
    if list(anim) != list(NATIVE_CONTRACT):
        raise AssertionError("Kled native 24-tag order changed")

    for tag, spec in NATIVE_CONTRACT.items():
        rows = anim[tag]["frames"]
        if len(rows) != len(spec["durations"]):
            raise AssertionError(f"{tag} frame count changed")
        for row, expected_duration, expected_rect in zip(
            rows, spec["durations"], spec["rects"], strict=True
        ):
            if float(row["duration"]) != expected_duration:
                raise AssertionError(f"{tag} duration changed")
            data = row["data"]
            actual_rect = (data["x"], data["y"], data["w"], data["h"])
            if actual_rect != expected_rect:
                raise AssertionError(f"{tag} native frame rectangle changed")
            x, y, width, height = expected_rect
            if x < 0 or y < 0 or x + width > sheet.width or y + height > sheet.height:
                raise AssertionError(f"{tag} frame is out of bounds")

    first_idle = frame_crop(sheet, anim["idle"]["frames"][0])
    idle_bbox = first_idle.getchannel("A").getbbox()
    if idle_bbox is None:
        raise AssertionError("Kled first idle is empty")
    idle_width = idle_bbox[2] - idle_bbox[0]
    idle_height = idle_bbox[3] - idle_bbox[1]
    if idle_width > 58 or not 36 <= idle_height <= 44 or idle_bbox[3] > 46:
        raise AssertionError(f"Kled idle battle scale is unsafe: bbox={idle_bbox}")

    run_hashes: set[str] = set()
    for row in anim["run"]["frames"]:
        frame = frame_crop(sheet, row)
        if frame.getchannel("A").getbbox() is None:
            raise AssertionError("Kled run contains an empty frame")
        run_hashes.add(hashlib.sha256(frame.tobytes()).hexdigest())
    if len(run_hashes) < 6:
        raise AssertionError("Kled run must contain at least six distinct phases")

    for tag in ("idle", "run", "attack", "skill1", "skill2", "ult", "hit"):
        for row in anim[tag]["frames"]:
            if frame_crop(sheet, row).getchannel("A").getbbox() is None:
                raise AssertionError(f"Kled core tag {tag} contains an empty frame")
    for tag in ("dead", "fire_dead"):
        if frame_crop(sheet, anim[tag]["frames"][-1]).getchannel("A").getbbox() is not None:
            raise AssertionError(f"Kled {tag} final 3x3 frame must be transparent")
    for row in anim["ult_self_effect_back"]["frames"]:
        if frame_crop(sheet, row).getchannel("A").getbbox() is not None:
            raise AssertionError("Kled ult_self_effect_back must remain transparent")

    for name, spec in EFFECT_SPECS.items():
        effect_sheet = Image.open(EFFECT_DIR / f"{name}#sheet.png").convert("RGBA")
        frame_size = spec["frame_size"]
        expected_size = (frame_size[0] * len(spec["source_indexes"]), frame_size[1])
        if effect_sheet.size != expected_size:
            raise AssertionError(f"{name} sheet is {effect_sheet.size}, expected {expected_size}")
        effect_anim = json.loads((EFFECT_DIR / f"{name}#anim.fanim").read_text(encoding="utf-8"))["anims"]
        if list(effect_anim) != list(spec["tags"]):
            raise AssertionError(f"{name} tag contract changed")
        if effect_sheet.getchannel("A").getbbox() is None:
            raise AssertionError(f"{name} effect sheet is empty")

    for icon in ("kled_skill.png", "kled_skill2.png", "kled_ult.png"):
        if Image.open(ICON_DIR / icon).size != (64, 64):
            raise AssertionError(f"{icon} is not 64x64")
    if len({sha256(ICON_DIR / name) for name in ("kled_skill.png", "kled_skill2.png", "kled_ult.png")}) != 3:
        raise AssertionError("Kled Q/W/R icons are not distinct")
    if Image.open(SPLASH_DIR / "cavalry_knight.png").size != (1420, 860):
        raise AssertionError("Kled BP splash is not 1420x860")
    if Image.open(FULLBODY_DIR / "cavalry_knight.png").size != (64, 64):
        raise AssertionError("Kled encyclopedia portrait is not 64x64")


def build_audit(outputs: list[Path]) -> Path:
    source_paths = [
        ACTOR_SOURCE,
        RUN_SOURCE,
        DEFEAT_SOURCE,
        Q_VFX_SOURCE,
        E_VFX_SOURCE,
        R_VFX_SOURCE,
        Q_ICON_SOURCE,
        E_ICON_SOURCE,
        R_ICON_SOURCE,
        SPLASH_SOURCE,
    ]
    audit = {
        "schema": 1,
        "champion": "Kled",
        "native_id": "cavalry_knight",
        "native_contract": {
            "sheet_size": list(ACTOR_SHEET_SIZE),
            "tag_order": list(NATIVE_CONTRACT),
            "tags": {
                tag: {
                    "frame_count": len(spec["rects"]),
                    "durations": spec["durations"],
                    "rects": [list(rect) for rect in spec["rects"]],
                }
                for tag, spec in NATIVE_CONTRACT.items()
            },
            "transparent_contract": {
                "ult_self_effect_back": "all 14 native 3x3 frames",
                "dead": "final native 3x3 frame",
                "fire_dead": "final native 3x3 frame",
            },
        },
        "sources": [
            {
                "path": path.relative_to(MOD_ROOT).as_posix(),
                "size_bytes": path.stat().st_size,
                "sha256": sha256(path),
                "image_size": list(Image.open(path).size),
            }
            for path in source_paths
        ],
        "outputs": [
            {
                "path": path.relative_to(MOD_ROOT).as_posix(),
                "size_bytes": path.stat().st_size,
                "sha256": sha256(path),
                **({"image_size": list(Image.open(path).size)} if path.suffix.lower() == ".png" else {}),
            }
            for path in outputs
        ],
        "independent_effects": {
            name: {
                "frame_size": list(spec["frame_size"]),
                "tags": list(spec["tags"]),
            }
            for name, spec in EFFECT_SPECS.items()
        },
        "deterministic_png": "canonical RGBA, filter=None, stored DEFLATE",
    }
    path = QA_DIR / "kled_imagegen_sources.json"
    write_json(path, audit)
    return path


def build_all() -> list[Path]:
    """Build every Kled visual resource and return generated paths."""
    for required in (
        ACTOR_SOURCE,
        RUN_SOURCE,
        DEFEAT_SOURCE,
        Q_VFX_SOURCE,
        E_VFX_SOURCE,
        R_VFX_SOURCE,
        Q_ICON_SOURCE,
        E_ICON_SOURCE,
        R_ICON_SOURCE,
        SPLASH_SOURCE,
    ):
        if not required.is_file():
            raise FileNotFoundError(required)

    actor_sheet, actor_anim, _ = build_actor()
    effect_outputs, effect_frames = build_effects()
    icon_outputs = build_icons()
    surface_outputs = build_splash_and_fullbody(actor_sheet, actor_anim)
    qa_outputs = build_qa_contacts(actor_sheet, actor_anim, icon_outputs, effect_frames)
    outputs = [actor_sheet, actor_anim, *effect_outputs, *icon_outputs, *surface_outputs, *qa_outputs]
    self_check(outputs)
    audit = build_audit(outputs)
    outputs.append(audit)
    return outputs


def main() -> int:
    outputs = build_all()
    print(f"built {len(outputs)} deterministic Kled visual resources")
    for path in outputs:
        print(path.relative_to(MOD_ROOT).as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
