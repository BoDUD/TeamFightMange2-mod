#!/usr/bin/env python3
"""Deterministically pack the image-gen Xayah art into native TFM2 resources.

This module owns only Xayah's visual and official-audio assets.  Champion
mechanics, localization, UI registration and override routing live elsewhere.
The actor keeps official champion 007/Dancer's exact animation contract while
all large feather effects are packed into independent effect sheets.
"""

from __future__ import annotations

import hashlib
import json
import statistics
import struct
import wave
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
PORTRAIT_DIR = MOD_ROOT / "ui" / "champion_portrait"
SOUND_DIR = MOD_ROOT / "sound" / "sfx"
QA_DIR = MOD_ROOT / "qa"

CORE_BODY_SOURCE = PROCESSED_ROOT / "xayah_core_body_contact_v2_alpha.png"
# The v3 idle is the accepted two-visible-eye source.  It is the single source
# of truth for idle frames and all Xayah portrait surfaces; v2 remains only as
# superseded provenance and must never be packed into runtime art again.
IDLE_BODY_SOURCE = PROCESSED_ROOT / "xayah_idle_contact_v3_alpha.png"
RUN_SOURCE = PROCESSED_ROOT / "xayah_run_contact_v2_alpha.png"
Q_BODY_SOURCE = PROCESSED_ROOT / "xayah_q_body_contact_v2_alpha.png"
E_BODY_SOURCE = PROCESSED_ROOT / "xayah_e_body_contact_v2_alpha.png"
R_BODY_SOURCE = PROCESSED_ROOT / "xayah_r_body_contact_v2_alpha.png"
DEFEAT_SOURCE = PROCESSED_ROOT / "xayah_defeat_contact_v2_alpha.png"
ATTACK_VFX_SOURCE = PROCESSED_ROOT / "xayah_attack_vfx_contact_alpha.png"
Q_VFX_SOURCE = PROCESSED_ROOT / "xayah_q_vfx_contact_v2_alpha.png"
E_VFX_SOURCE = PROCESSED_ROOT / "xayah_e_vfx_contact_v3_alpha.png"
R_VFX_SOURCE = PROCESSED_ROOT / "xayah_r_vfx_contact_v2_alpha.png"
GROUND_FEATHER_VFX_SOURCE = PROCESSED_ROOT / "xayah_ground_feather_contact_v1_alpha.png"
Q_ICON_SOURCE = IMAGEGEN_ROOT / "xayah_q_icon_source.png"
E_ICON_SOURCE = IMAGEGEN_ROOT / "xayah_e_icon_source.png"
R_ICON_SOURCE = IMAGEGEN_ROOT / "xayah_r_icon_source.png"
SPLASH_SOURCE = IMAGEGEN_ROOT / "bp_splash" / "dancer.png"

ACTOR_SHEET_SIZE = (1594, 90)

# Accepted pre-enlargement body heights from the 2026-07-12 v2 runtime build.
# They are retained only as a deterministic QA baseline.  Runtime frames use
# BODY_TARGET_HEIGHTS below, whose median enlargement is approximately 14%.
BASELINE_BODY_HEIGHTS: dict[str, list[int]] = {
    "idle": [34, 33, 32, 33],
    "run": [32, 28, 26, 28, 31, 30, 28, 30],
    "attack": [33, 33, 34, 30, 32],
    "hit": [33],
    "skill1": [34, 34, 34, 34, 34],
    "skill2": [34, 34, 34],
    "ult": [29, 33, 31, 33, 34],
}


# Exact tag order, frame counts, durations and rectangles from native champion
# 007/Dancer. Dict insertion order is a runtime contract and must not be sorted.
NATIVE_CONTRACT: dict[str, dict[str, Any]] = {
    "ult": {
        "durations": [0.080000006] * 5,
        "rects": [
            (1214, 0, 53, 43),
            (1268, 0, 41, 45),
            (1310, 0, 89, 79),
            (1400, 0, 96, 89),
            (1497, 0, 96, 89),
        ],
    },
    "idle": {
        "durations": [0.14] * 4,
        "rects": [(28, 0, 27, 47), (56, 0, 27, 45), (84, 0, 27, 43), (112, 0, 27, 45)],
    },
    "run": {
        "durations": [0.080000006] * 8,
        "rects": [
            (140, 0, 25, 45),
            (166, 0, 23, 47),
            (190, 0, 25, 49),
            (216, 0, 23, 47),
            (240, 0, 25, 45),
            (266, 0, 25, 47),
            (292, 0, 27, 49),
            (320, 0, 25, 47),
        ],
    },
    "projectile": {"durations": [0.05], "rects": [(490, 0, 13, 13)]},
    "hit": {"durations": [0.1], "rects": [(504, 0, 31, 45)]},
    "attack": {
        "durations": [0.080000006] * 5,
        "rects": [
            (346, 0, 27, 45),
            (374, 0, 31, 45),
            (406, 0, 35, 47),
            (442, 0, 23, 45),
            (466, 0, 23, 43),
        ],
    },
    "skill1_projectile": {
        "durations": [0.080000006] * 2,
        "rects": [(1056, 0, 27, 27), (1084, 0, 25, 25)],
    },
    "dead": {
        "durations": [0.1] * 10,
        "rects": [
            (536, 0, 31, 43),
            (568, 0, 31, 41),
            (600, 0, 31, 39),
            (632, 0, 31, 37),
            (664, 0, 31, 33),
            (696, 0, 31, 33),
            (728, 0, 31, 33),
            (760, 0, 31, 33),
            (792, 0, 31, 33),
            (824, 0, 3, 3),
        ],
    },
    "skill1": {
        "durations": [0.080000006] * 5,
        "rects": [
            (828, 0, 41, 45),
            (870, 0, 49, 47),
            (920, 0, 51, 67),
            (972, 0, 39, 49),
            (1012, 0, 43, 57),
        ],
    },
    "skill2": {
        "durations": [0.080000006] * 3,
        "rects": [(1110, 0, 35, 61), (1146, 0, 33, 63), (1180, 0, 33, 67)],
    },
}


# Final-scale actor placement follows the visible native 007/Dancer motion
# profile instead of pinning every replacement pose to the bottom edge.  The
# values are measured from the bundled native sheet at alpha >= 64.
BODY_TARGET_HEIGHTS: dict[str, list[int]] = {
    "idle": [39, 38, 36, 38],
    "run": [36, 32, 30, 32, 35, 34, 32, 34],
    "attack": [38, 38, 39, 34, 36],
    "hit": [38],
    "skill1": [39, 39, 39, 39, 39],
    "skill2": [39, 39, 39],
    # Preserve the crouch/rise/apex/descent/recovery proportions from the
    # dedicated R body contact instead of stretching every pose to one height.
    "ult": [33, 38, 35, 38, 39],
}

BODY_BOTTOM_MARGINS: dict[str, list[int]] = {
    # The larger body expands mostly upward.  Tight native frames also spend
    # part of their old 10-22px blank footer, but every frame retains at least
    # four transparent pixels below the feet.
    "idle": [7, 6, 6, 6],
    "run": [8, 14, 18, 14, 9, 12, 16, 12],
    "attack": [6, 6, 7, 10, 6],
    "hit": [6],
    "skill1": [5, 7, 22, 10, 17],
    "skill2": [19, 20, 21],
    # Distance above the native frame bottom rises to a clear airborne apex,
    # then descends to the landing recovery.  The actor itself proves the
    # jump; the separate guard ring is only supplementary feedback.
    "ult": [4, 6, 26, 18, 4],
}

DEAD_BOTTOM_MARGINS = [10, 9, 8, 7, 5, 5, 5, 5, 5]


def write_json(path: Path, value: Any, *, compact: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if compact:
        payload = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    else:
        payload = json.dumps(value, ensure_ascii=False, indent=2)
    path.write_text(payload + "\n", encoding="utf-8")


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
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


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


def remove_small_border_fragments(image: Image.Image, max_pixels: int = 256) -> Image.Image:
    """Drop isolated contact-sheet bleed without cropping the real silhouette."""
    rgba = image.convert("RGBA").copy()
    alpha = rgba.getchannel("A")
    alpha_pixels = alpha.load()
    width, height = rgba.size
    boundary = [
        *((x, 0) for x in range(width)),
        *((x, height - 1) for x in range(width)),
        *((0, y) for y in range(1, height - 1)),
        *((width - 1, y) for y in range(1, height - 1)),
    ]
    visited: set[tuple[int, int]] = set()
    remove: list[tuple[int, int]] = []
    for seed in boundary:
        if seed in visited or alpha_pixels[seed] == 0:
            continue
        component: list[tuple[int, int]] = []
        stack = [seed]
        visited.add(seed)
        while stack:
            x, y = stack.pop()
            component.append((x, y))
            for next_y in range(max(0, y - 1), min(height, y + 2)):
                for next_x in range(max(0, x - 1), min(width, x + 2)):
                    point = (next_x, next_y)
                    if point not in visited and alpha_pixels[point] != 0:
                        visited.add(point)
                        stack.append(point)
        if len(component) <= max_pixels:
            remove.extend(component)
    if not remove:
        return rgba
    pixels = rgba.load()
    for point in remove:
        pixels[point] = (0, 0, 0, 0)
    return rgba


def palette_finish(image: Image.Image, colors: int = 48) -> Image.Image:
    opaque = hard_alpha(image)
    quantized = opaque.quantize(colors=colors, method=Image.Quantize.FASTOCTREE).convert("RGBA")
    quantized.putalpha(opaque.getchannel("A"))
    return hard_alpha(quantized, 128)


def alpha_bbox(image: Image.Image) -> tuple[int, int, int, int]:
    bbox = image.getchannel("A").point(lambda value: 255 if value >= 64 else 0).getbbox()
    if bbox is None:
        raise ValueError("Xayah source cell has no visible pixels")
    return bbox


def fit_actor(
    source: Image.Image,
    frame_size: tuple[int, int],
    *,
    target_height: int,
    bottom_margin: int,
) -> Image.Image:
    """Uniformly fit one final-scale pose onto the native 007 body anchor.

    Xayah v1 independently clamped the resized width after choosing height.
    Wide run/attack poses therefore lost up to 44% of their horizontal scale
    and collapsed into a cape-shaped blob.  Body art must now remain uniform:
    if a pose is too wide, the entire pose gets smaller or the visual gate
    rejects the source; x-only compression is never allowed.
    """
    source = remove_small_border_fragments(hard_alpha(source))
    subject = source.crop(alpha_bbox(source))
    # Use the complete native width when a wide run/throw pose needs it.  This
    # is still a hard native-frame cap (no spill or crop), and the one uniform
    # scale below means a narrow rect can reduce the whole pose but can never
    # squeeze only its x axis.  Most frames keep 1px+ side clearance; the few
    # stride extremes that exactly fill their native rect are recorded in the
    # scale QA instead of being horizontally compressed.
    max_width = max(1, frame_size[0])
    max_height = max(1, frame_size[1] - bottom_margin - 1)
    scale = min(target_height / subject.height, max_width / subject.width, max_height / subject.height)
    width = max(1, round(subject.width * scale))
    height = max(1, round(subject.height * scale))
    resized = subject.resize((width, height), Image.Resampling.NEAREST)
    resized = palette_finish(resized, 48)
    resized = resized.crop(alpha_bbox(resized))
    output = Image.new("RGBA", frame_size, (0, 0, 0, 0))
    x = (frame_size[0] - resized.width) // 2
    y = frame_size[1] - bottom_margin - resized.height
    if y < 0:
        raise ValueError(
            f"Xayah body {resized.size} cannot preserve bottom margin {bottom_margin} "
            f"inside native frame {frame_size}"
        )
    output.alpha_composite(resized, (x, y))
    return output


def fit_effect(source: Image.Image, frame_size: tuple[int, int], *, padding: int = 2) -> Image.Image:
    source = hard_alpha(source)
    subject = source.crop(alpha_bbox(source))
    max_width = max(1, frame_size[0] - padding * 2)
    max_height = max(1, frame_size[1] - padding * 2)
    scale = min(max_width / subject.width, max_height / subject.height)
    resized = subject.resize(
        (max(1, round(subject.width * scale)), max(1, round(subject.height * scale))),
        Image.Resampling.NEAREST,
    )
    resized = palette_finish(resized, 64)
    output = Image.new("RGBA", frame_size, (0, 0, 0, 0))
    output.alpha_composite(
        resized,
        ((frame_size[0] - resized.width) // 2, (frame_size[1] - resized.height) // 2),
    )
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
    if previous is not None and previous != pixels:
        raise ValueError(f"overlapping native rect {rect} was assigned two different frames")
    if previous is None:
        placements[rect] = pixels
        sheet.alpha_composite(frame, (x, y))


def build_actor() -> tuple[Path, Path, list[Image.Image]]:
    core_cells = split_grid(Image.open(CORE_BODY_SOURCE).convert("RGBA"), 5, 2)
    idle_cells = split_grid(Image.open(IDLE_BODY_SOURCE).convert("RGBA"), 4, 1)
    run_cells = split_grid(Image.open(RUN_SOURCE).convert("RGBA"), 4, 2)
    q_body_cells = split_grid(Image.open(Q_BODY_SOURCE).convert("RGBA"), 5, 1)
    e_body_cells = split_grid(Image.open(E_BODY_SOURCE).convert("RGBA"), 3, 1)
    r_body_cells = split_grid(Image.open(R_BODY_SOURCE).convert("RGBA"), 5, 1)
    defeat_cells = split_grid(Image.open(DEFEAT_SOURCE).convert("RGBA"), 3, 3)
    attack_vfx = split_grid(Image.open(ATTACK_VFX_SOURCE).convert("RGBA"), 4, 2)
    q_vfx = split_grid(Image.open(Q_VFX_SOURCE).convert("RGBA"), 4, 2)

    sheet = Image.new("RGBA", ACTOR_SHEET_SIZE, (0, 0, 0, 0))
    placements: dict[tuple[int, int, int, int], bytes] = {}
    representative: list[Image.Image] = []

    sequences = {
        "idle": idle_cells,
        "run": run_cells,
        "attack": core_cells[5:10],
        "hit": [core_cells[4]],
        "skill1": q_body_cells,
        "skill2": e_body_cells,
        # Q, E and R have disjoint body contacts.  Large effects remain in the
        # independent xayah_q/xayah_e/xayah_r sheets.
        "ult": r_body_cells,
    }
    for tag in ("ult", "idle", "run", "hit", "attack", "skill1", "skill2"):
        sources = sequences[tag]
        rects = NATIVE_CONTRACT[tag]["rects"]
        heights = BODY_TARGET_HEIGHTS[tag]
        bottoms = BODY_BOTTOM_MARGINS[tag]
        if not (len(sources) == len(rects) == len(heights) == len(bottoms)):
            raise ValueError(f"{tag}: {len(sources)} sources for {len(rects)} native frames")
        for rect, source, target_height, bottom_margin in zip(
            rects, sources, heights, bottoms, strict=True
        ):
            frame = fit_actor(
                source,
                (rect[2], rect[3]),
                target_height=target_height,
                bottom_margin=bottom_margin,
            )
            _paste_unique(sheet, placements, rect, frame)
            representative.append(frame)

    # Native actor-owned projectile slots stay compact; gameplay uses the
    # independent xayah_attack/xayah_q effect sheets for readable VFX.
    projectile_rect = NATIVE_CONTRACT["projectile"]["rects"][0]
    _paste_unique(
        sheet,
        placements,
        projectile_rect,
        fit_effect(attack_vfx[1], (projectile_rect[2], projectile_rect[3]), padding=1),
    )
    for rect, source in zip(NATIVE_CONTRACT["skill1_projectile"]["rects"], q_vfx[0:2], strict=True):
        _paste_unique(sheet, placements, rect, fit_effect(source, (rect[2], rect[3]), padding=1))

    # Nine generated fall/grounded poses exactly fill the nine visible native
    # frames; the mandatory final 3x3 terminal frame remains transparent.
    for rect, source, bottom_margin in zip(
        NATIVE_CONTRACT["dead"]["rects"][:-1],
        defeat_cells,
        DEAD_BOTTOM_MARGINS,
        strict=True,
    ):
        frame = fit_actor(
            source,
            (rect[2], rect[3]),
            target_height=max(1, rect[3] - bottom_margin - 1),
            bottom_margin=bottom_margin,
        )
        _paste_unique(sheet, placements, rect, frame)
        representative.append(frame)

    sheet_path = ACTOR_DIR / "xayah#sheet.png"
    anim_path = ACTOR_DIR / "xayah#anim.fanim"
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
    return sheet_path, anim_path, representative


def _build_effect(
    name: str,
    source_path: Path,
    tag_specs: list[tuple[str, list[int], tuple[int, int], float]],
    *,
    grid: tuple[int, int] = (4, 2),
    transparent_terminal_tags: frozenset[str] = frozenset(),
) -> list[Path]:
    cells = split_grid(Image.open(source_path).convert("RGBA"), *grid)
    sheet_width = max(len(indexes) * size[0] for _, indexes, size, _ in tag_specs)
    sheet_height = sum(size[1] for _, _, size, _ in tag_specs)
    sheet = Image.new("RGBA", (sheet_width, sheet_height), (0, 0, 0, 0))
    y = 0
    anims: dict[str, Any] = {}
    for tag, indexes, frame_size, duration in tag_specs:
        frames: list[dict[str, Any]] = []
        for frame_index, source_index in enumerate(indexes):
            source = cells[source_index]
            if tag in transparent_terminal_tags and frame_index == len(indexes) - 1:
                # RangePeriodProjectile cannot be removed early through API
                # 0.8.  Ending on a truly transparent frame bounds any
                # visible post-E ghost even while the harmless entity waits
                # for its fixed TTL to expire.
                frame = Image.new("RGBA", frame_size, (0, 0, 0, 0))
            else:
                frame = fit_effect(source, frame_size)
            x = frame_index * frame_size[0]
            sheet.alpha_composite(frame, (x, y))
            frames.append(
                {"duration": duration, "data": {"x": x, "y": y, "w": frame_size[0], "h": frame_size[1]}}
            )
        anims[tag] = {"frames": frames}
        y += frame_size[1]
    sheet_path = EFFECT_DIR / f"{name}#sheet.png"
    anim_path = EFFECT_DIR / f"{name}#anim.fanim"
    save_png(sheet_path, sheet)
    write_json(anim_path, {"anims": anims})
    return [sheet_path, anim_path]


def build_vfx() -> list[Path]:
    outputs: list[Path] = []
    outputs.extend(
        _build_effect(
            "xayah_attack",
            ATTACK_VFX_SOURCE,
            [("projectile", [0, 1, 2, 3], (64, 32), 0.05), ("hit", [4, 5, 6, 7], (64, 48), 0.06)],
        )
    )
    outputs.extend(
        _build_effect(
            "xayah_q",
            Q_VFX_SOURCE,
            [("projectile", [0, 1, 2, 3], (96, 48), 0.06), ("hit", [4, 5, 6, 7], (96, 64), 0.06)],
        )
    )
    outputs.extend(
        _build_effect(
            "xayah_e",
            E_VFX_SOURCE,
            [
                # Live review found the original recall art body-sized.  The
                # smaller native footprints keep the feathers readable as
                # thin return streaks without enclosing the champion.
                ("return_single", [0, 1, 2, 3], (64, 32), 0.06),
                ("return_double", [4, 5, 6, 7], (72, 36), 0.06),
                ("return_cluster", [8, 9, 10, 11], (80, 44), 0.06),
                ("root", [12, 13, 14, 15], (72, 72), 0.07),
                ("hit", [12, 13, 14, 15], (48, 48), 0.06),
            ],
            grid=(4, 4),
        )
    )
    outputs.extend(
        _build_effect(
            "xayah_r",
            R_VFX_SOURCE,
            [
                ("fan", [0, 1, 2, 3], (104, 72), 0.07),
                ("hit", [4, 5, 6, 7], (96, 72), 0.07),
                ("guard", [8, 9, 10, 11], (72, 72), 0.07),
            ],
            grid=(4, 3),
        )
    )
    outputs.extend(
        _build_effect(
            "xayah_ground_feather",
            GROUND_FEATHER_VFX_SOURCE,
            [
                ("ground_single", [0, 1, 2, 3], (48, 40), 0.55),
                ("ground_fan", [4, 5, 6, 7], (72, 48), 0.55),
            ],
            transparent_terminal_tags=frozenset({"ground_single", "ground_fan"}),
        )
    )
    return outputs


def cover_crop(source: Image.Image, size: tuple[int, int]) -> Image.Image:
    scale = max(size[0] / source.width, size[1] / source.height)
    resized = source.resize(
        (max(1, round(source.width * scale)), max(1, round(source.height * scale))),
        Image.Resampling.LANCZOS,
    )
    left = (resized.width - size[0]) // 2
    top = (resized.height - size[1]) // 2
    return resized.crop((left, top, left + size[0], top + size[1])).convert("RGBA")


def build_icons() -> list[Path]:
    outputs: list[Path] = []
    for output_name, source_path in (
        ("xayah_skill.png", Q_ICON_SOURCE),
        ("xayah_skill2.png", E_ICON_SOURCE),
        ("xayah_ult.png", R_ICON_SOURCE),
    ):
        icon = cover_crop(Image.open(source_path).convert("RGBA"), (64, 64))
        icon = icon.quantize(colors=128, method=Image.Quantize.FASTOCTREE).convert("RGBA")
        output = ICON_DIR / output_name
        save_png(output, icon)
        outputs.append(output)
    return outputs


def build_splash_and_fullbody(_actor_sheet: Path) -> list[Path]:
    splash = cover_crop(Image.open(SPLASH_SOURCE).convert("RGBA"), (1420, 860))
    splash_path = SPLASH_DIR / "dancer.png"
    save_png(splash_path, splash)

    # UI portraits are independent surfaces.  Enlarging the already packed
    # 39px actor would only magnify final-scale pixels and recreate the cropped
    # one-eye avatar.  Derive full-body, compact, and BP-grid art directly from
    # the accepted high-resolution v3 idle source instead.
    idle_source = split_grid(Image.open(IDLE_BODY_SOURCE).convert("RGBA"), 4, 1)[0]
    idle_source = hard_alpha(idle_source)
    full_body = idle_source.crop(alpha_bbox(idle_source))

    def render_subject(
        source: Image.Image,
        size: tuple[int, int],
        *,
        max_subject: tuple[int, int],
        bottom: int,
        colors: int,
    ) -> Image.Image:
        source = hard_alpha(source)
        subject = source.crop(alpha_bbox(source))
        scale = min(max_subject[0] / subject.width, max_subject[1] / subject.height)
        subject = subject.resize(
            (max(1, round(subject.width * scale)), max(1, round(subject.height * scale))),
            Image.Resampling.LANCZOS,
        )
        subject = palette_finish(subject, colors)
        subject = subject.crop(alpha_bbox(subject))
        output = Image.new("RGBA", size, (0, 0, 0, 0))
        x = (size[0] - subject.width) // 2
        y = min(size[1] - subject.height, bottom - subject.height)
        if x < 0 or y < 0:
            raise ValueError(f"Xayah UI subject {subject.size} does not fit {size}")
        output.alpha_composite(subject, (x, y))
        return output

    portrait = render_subject(
        full_body,
        (64, 64),
        max_subject=(54, 56),
        bottom=60,
        colors=96,
    )
    portrait_path = FULLBODY_DIR / "dancer.png"
    save_png(portrait_path, portrait)

    # Compact report/scoreboard/HUD portrait: preserve both visible eyes,
    # feather ears, shoulders, and the upper torso while giving the square
    # surface a transparent border for 18/26/34/46px runtime downscales.
    body_width, body_height = full_body.size
    face_focus = full_body.crop(
        (
            round(body_width * 0.02),
            0,
            round(body_width * 0.98),
            round(body_height * 0.60),
        )
    )
    compact = render_subject(
        face_focus,
        (64, 64),
        max_subject=(50, 50),
        bottom=58,
        colors=96,
    )
    compact_path = PORTRAIT_DIR / "dancer_compact.png"
    save_png(compact_path, compact)

    # The lower 26px of the standard 90x122 BP texture are reserved for the
    # hero-name band.  Live review proved that merely ending at y=96 still lets
    # the feet visually merge into the dark band.  Reserve another 10px of
    # transparent breathing room so the complete silhouette clearly floats
    # above the label after the native 54x94 command is expanded to 90x122.
    grid = render_subject(
        full_body,
        (90, 122),
        max_subject=(72, 82),
        bottom=86,
        colors=128,
    )
    grid_path = PORTRAIT_DIR / "dancer_grid.png"
    save_png(grid_path, grid)
    return [splash_path, portrait_path, compact_path, grid_path]


AUDIO_SPECS: tuple[dict[str, Any], ...] = (
    {
        "stem": "xayah_attack_cast", "media_id": 1013698442,
        "riot_event": "Play_sfx_Xayah_XayahBasicAttack_OnCast", "riot_event_id": 2399062020,
        "pool": [11873463, 259875172, 886609448, 961904137, 1013698442],
        "wem_size": 11225, "wem_sha": "2b8bd1524f7cb1ec531c024d65e5e184d6b0ecb881ff8bef0d7d1ca94e1fda8e",
        "wav_size": 116760, "wav_sha": "77696dc22aaf76d5650c4df249d437ae555b2db8f55ae46808ce8c687b44c6d6",
        "frames": 58358, "duration": 1.3233106575963718, "volume": 1.0,
    },
    {
        "stem": "xayah_attack_hit", "media_id": 10841184,
        "riot_event": "Play_sfx_Xayah_XayahBasicAttack_OnHit", "riot_event_id": 2111622188,
        "pool": [9507949, 10841184, 263171907, 277551594, 283971483],
        "wem_size": 3704, "wem_sha": "1a96d050ec75239fe265a6b33be3fdb35e290f650d3ff13a31d8921cb4b8f37e",
        "wav_size": 27718, "wav_sha": "a303e3afaeab139b25275ba3122985c0f737cfe4944a60f4ca7145aff4f37a22",
        "frames": 13837, "duration": 0.3137641723356009, "volume": 1.0,
    },
    {
        "stem": "xayah_q_cast", "media_id": 947407279,
        "riot_event": "Play_sfx_Xayah_XayahQ_OnCast", "riot_event_id": 768036005,
        "pool": [947407279], "wem_size": 14724,
        "wem_sha": "66a406dadb5a47b32ce9c5ceb8877a24e12aef283379d9c6f416e705a5bb78bf",
        "wav_size": 169110, "wav_sha": "1beab97f7dc53df3586e33765081a7e235bf60c05c5c94b29d5ae6e51fe0e22f",
        "frames": 84533, "duration": 1.9168480725623582, "volume": 1.0,
    },
    {
        "stem": "xayah_q_hit", "media_id": 115312720,
        "riot_event": "Play_sfx_Xayah_XayahQMissile1_OnHitLocation", "riot_event_id": 3218441131,
        "pool": [34093138, 115312720, 195416324, 308882689, 775008110],
        "wem_size": 8405, "wem_sha": "2d6340908946af56359f1dab2511670aed023748f42242fd21d2d5e44080c443",
        "wav_size": 97062, "wav_sha": "f4e1de7d4233c9d1a160867820fcc8977cc24e158859440aa1391317427da52f",
        "frames": 48509, "duration": 1.0999773242630386, "volume": 1.0,
    },
    {
        "stem": "xayah_e_cast", "media_id": 482031824,
        "riot_event": "Play_sfx_Xayah_XayahE_cast", "riot_event_id": 2427398726,
        "pool": [482031824], "wem_size": 10307,
        "wem_sha": "6b12fca9dd80d5d810dfdfcd0bef83537b11581ccf8e6912527bb491b7aa8a79",
        "wav_size": 125030, "wav_sha": "a8158ae96d4db5fdab5a7f13b901bc1ea422d0644bfa874867267b4b10f1b2a3",
        "frames": 62493, "duration": 1.4170748299319729, "volume": 1.0,
    },
    {
        "stem": "xayah_e_launch", "media_id": 193591456,
        "riot_event": "Play_sfx_Xayah_XayahE_feather_launch", "riot_event_id": 3072767302,
        "pool": [193591456], "wem_size": 5157,
        "wem_sha": "9a238f6595de3a52a567516d4d94800ac449b542d5f6b11323bb317c1355134c",
        "wav_size": 50596, "wav_sha": "4e8d581dbc8d4d26c91576afcb3ce009ac2cab147e5657aed071051165d107e6",
        "frames": 25276, "duration": 0.5731519274376418, "volume": 1.0,
    },
    {
        "stem": "xayah_e_hit", "media_id": 11416379,
        "riot_event": "Play_sfx_Xayah_XayahE_feather_hit", "riot_event_id": 2766149514,
        "pool": [11416379, 24169822, 453799481, 494387490, 613451275],
        "wem_size": 2834, "wem_sha": "033c9af80ae903f541ebb9b9d5904c9e2e0d87fb7dd3f27c4bc5738b2c4bcdb1",
        "wav_size": 25446, "wav_sha": "01db1a38dd4d99f009e753a4015c121dec32995da0d427ba7d54b9465fb107b7",
        "frames": 12701, "duration": 0.28800453514739227, "volume": 1.0,
    },
    {
        "stem": "xayah_e_catch", "media_id": 720384227,
        "riot_event": "Play_sfx_Xayah_XayahE_feather_catch", "riot_event_id": 3517893168,
        "pool": [720384227], "wem_size": 1928,
        "wem_sha": "576621f64b7313facdacba661c5d1576144751b0dbae5e0788d06914dba93175",
        "wav_size": 13570, "wav_sha": "6bee83ed149d2abfc317ceef37dba4add77efece6ac4bab41c9b07c34a32a7ad",
        "frames": 6763, "duration": 0.15335600907029479, "volume": 1.0,
    },
    {
        "stem": "xayah_e_root", "media_id": 425209492,
        "riot_event": "Play_sfx_Xayah_XayahE_root_hit", "riot_event_id": 1913447281,
        "pool": [66955044, 425209492, 731834587, 863365552, 958966887],
        "wem_size": 19137, "wem_sha": "2942a08bcdf8f1c250b78d46099d1f3e66875da9b00184fcf4f75ef3850d4ba3",
        "wav_size": 215248, "wav_sha": "eb611f7d83157bb216f684bbaadfed9c282ff4bddb4aa2ee820aff7c61d6f377",
        "frames": 107602, "duration": 2.439954648526077, "volume": 1.0,
    },
    {
        "stem": "xayah_r_cast", "media_id": 979219185,
        "riot_event": "Play_sfx_Xayah_XayahR_OnCast", "riot_event_id": 3899263444,
        "pool": [979219185], "wem_size": 23088,
        "wem_sha": "b1745b2d6cbe7d7e069210e1dac3dd580c2bb07b2032be40ae088521638f2d8d",
        "wav_size": 259386, "wav_sha": "342decee02b53317a7bd81384bf67b70ab0d669ce7de38d7eb3be11032980f56",
        "frames": 129671, "duration": 2.940385487528345, "volume": 1.0,
    },
)


def inspect_pcm_wav(path: Path) -> dict[str, Any]:
    with wave.open(str(path), "rb") as opened:
        return {
            "channels": opened.getnchannels(),
            "sample_width_bytes": opened.getsampwidth(),
            "sample_rate_hz": opened.getframerate(),
            "frame_count": opened.getnframes(),
            "duration_seconds": opened.getnframes() / opened.getframerate(),
            "compression": opened.getcomptype(),
        }


def build_audio_assets() -> list[Path]:
    outputs: list[Path] = []
    SOUND_DIR.mkdir(parents=True, exist_ok=True)
    for spec in AUDIO_SPECS:
        wav_path = SOUND_DIR / f"{spec['stem']}_clip.wav"
        if not wav_path.is_file():
            raise FileNotFoundError(f"Missing decoded official Xayah WAV: {wav_path}")
        info = inspect_pcm_wav(wav_path)
        if (info["channels"], info["sample_width_bytes"], info["sample_rate_hz"], info["compression"]) != (1, 2, 44100, "NONE"):
            raise ValueError(f"{wav_path.name} is not mono PCM16 44100 Hz")
        if wav_path.stat().st_size != spec["wav_size"] or sha256(wav_path) != spec["wav_sha"]:
            raise ValueError(f"{wav_path.name} differs from the audited Riot decode")
        if info["frame_count"] != spec["frames"]:
            raise ValueError(f"{wav_path.name} frame count changed")
        sound_info = SOUND_DIR / f"{spec['stem']}.sound_info"
        write_json(
            sound_info,
            {"plays": [{"delay": 0.0, "clip": f"{spec['stem']}_clip", "volume": spec["volume"]}]},
            compact=True,
        )
        outputs.extend([sound_info, wav_path])

    silence_wav = SOUND_DIR / "xayah_native_silence_clip.wav"
    with wave.open(str(silence_wav), "wb") as opened:
        opened.setnchannels(1)
        opened.setsampwidth(2)
        opened.setframerate(44100)
        opened.writeframes(b"\0\0" * 2205)
    silence_info = SOUND_DIR / "xayah_native_silence.sound_info"
    write_json(
        silence_info,
        {"plays": [{"delay": 0.0, "clip": "xayah_native_silence_clip", "volume": 1.0}]},
        compact=True,
    )
    outputs.extend([silence_info, silence_wav])
    return outputs


def _image_record(role: str, path: Path) -> dict[str, Any]:
    with Image.open(path) as opened:
        rgba = opened.convert("RGBA")
        alpha = rgba.getchannel("A")
        histogram = alpha.histogram()
        return {
            "role": role,
            "path": path.relative_to(MOD_ROOT).as_posix(),
            "size_bytes": path.stat().st_size,
            "sha256": sha256(path),
            "dimensions": list(opened.size),
            "mode": opened.mode,
            "alpha": {
                "min": alpha.getextrema()[0],
                "max": alpha.getextrema()[1],
                "transparent_pixels": histogram[0],
                "partial_pixels": sum(histogram[1:255]),
                "opaque_pixels": histogram[255],
                "nonzero_bbox": list(alpha.getbbox()) if alpha.getbbox() else None,
            },
        }


def build_ui_scale_qa(actor_sheet: Path, actor_anim: Path) -> list[Path]:
    """Record the accepted actor enlargement and source-direct UI surfaces."""
    sheet = Image.open(actor_sheet).convert("RGBA")
    anims = json.loads(actor_anim.read_text(encoding="utf-8"))["anims"]
    ratios: list[float] = []
    action_records: dict[str, list[dict[str, Any]]] = {}
    for tag, baseline_heights in BASELINE_BODY_HEIGHTS.items():
        action_records[tag] = []
        for index, (frame_row, baseline_height, target_height) in enumerate(
            zip(anims[tag]["frames"], baseline_heights, BODY_TARGET_HEIGHTS[tag], strict=True)
        ):
            data = frame_row["data"]
            frame = sheet.crop(
                (
                    data["x"],
                    data["y"],
                    data["x"] + data["w"],
                    data["y"] + data["h"],
                )
            )
            bbox = frame.getchannel("A").getbbox()
            if bbox is None:
                raise ValueError(f"Xayah {tag}[{index}] is empty during scale QA")
            visible_width = bbox[2] - bbox[0]
            visible_height = bbox[3] - bbox[1]
            ratio = visible_height / baseline_height
            ratios.append(ratio)
            action_records[tag].append(
                {
                    "frame": index,
                    "native_rect": [data[key] for key in ("w", "h")],
                    "visible_bbox": list(bbox),
                    "visible_size": [visible_width, visible_height],
                    "baseline_height": baseline_height,
                    "target_height": target_height,
                    "height_scale_ratio": round(ratio, 4),
                    "bottom_clearance": data["h"] - bbox[3],
                    "left_clearance": bbox[0],
                    "right_clearance": data["w"] - bbox[2],
                    "native_width_limited": visible_height + 1 < target_height,
                }
            )

    median_ratio = statistics.median(ratios)
    mean_ratio = statistics.fmean(ratios)
    min_bottom = min(
        row["bottom_clearance"] for records in action_records.values() for row in records
    )
    if not 1.12 <= median_ratio <= 1.16 or not 1.12 <= mean_ratio <= 1.15:
        raise ValueError(
            f"Xayah actor enlargement left the 12-15% class: median={median_ratio:.4f}, mean={mean_ratio:.4f}"
        )
    if min_bottom < 4:
        raise ValueError(f"Xayah enlarged actor lost foot clearance: {min_bottom}px")

    portrait_specs = {
        "encyclopedia": (FULLBODY_DIR / "dancer.png", [64, 64]),
        "compact": (PORTRAIT_DIR / "dancer_compact.png", [64, 64]),
        "bp_grid": (PORTRAIT_DIR / "dancer_grid.png", [90, 122]),
    }
    portrait_records: dict[str, dict[str, Any]] = {}
    for surface, (path, expected_size) in portrait_specs.items():
        image = Image.open(path).convert("RGBA")
        bbox = image.getchannel("A").getbbox()
        if list(image.size) != expected_size or bbox is None:
            raise ValueError(f"Xayah {surface} portrait is invalid: size={image.size}, bbox={bbox}")
        portrait_records[surface] = {
            "path": path.relative_to(MOD_ROOT).as_posix(),
            "dimensions": list(image.size),
            "alpha_bbox": list(bbox),
            "hard_alpha": image.getchannel("A").getextrema() == (0, 255),
        }
    if portrait_records["bp_grid"]["alpha_bbox"][3] > 86:
        raise ValueError("Xayah BP-grid portrait overlaps its bottom name band")
    compact_bbox = portrait_records["compact"]["alpha_bbox"]
    if (
        compact_bbox[2] - compact_bbox[0] > 50
        or compact_bbox[3] - compact_bbox[1] > 50
        or min(
            compact_bbox[0],
            compact_bbox[1],
            64 - compact_bbox[2],
            64 - compact_bbox[3],
        ) < 6
    ):
        raise ValueError(f"Xayah compact portrait lacks 6px safety margins: {compact_bbox}")

    qa_path = QA_DIR / "xayah_ui_scale_qa.json"
    write_json(
        qa_path,
        {
            "schema_version": 1,
            "champion": "Xayah",
            "accepted_idle_and_portrait_source": "source/processed/xayah_idle_contact_v3_alpha.png",
            "actor_scale": {
                "policy": "one uniform nearest-neighbor resize per frame; native width may cap the whole pose; no x-only compression, crop, or atlas spill",
                "requested_scale_class": "approximately 12-15 percent larger",
                "mean_height_scale_ratio": round(mean_ratio, 4),
                "median_height_scale_ratio": round(median_ratio, 4),
                "minimum_bottom_clearance": min_bottom,
                "actions": action_records,
                "q_e_r_sources": {
                    "Q": Q_BODY_SOURCE.relative_to(MOD_ROOT).as_posix(),
                    "E": E_BODY_SOURCE.relative_to(MOD_ROOT).as_posix(),
                    "R": R_BODY_SOURCE.relative_to(MOD_ROOT).as_posix(),
                },
            },
            "portraits": portrait_records,
            "bp_geometry": {
                "side_card_stable": [81, 141],
                "side_card_transition": {"width": [80, 82], "height": [124, 142]},
                "stable_center_matches_standard_actor": True,
                "center_grid_native_geometry": [54, 94],
                "center_grid_isolation": "54x94 is routed only to dancer_grid; side-card replacement requires the left/right edge gate and 81x125-141 geometry",
                "name_band": {
                    "texture_y_start": 96,
                    "texture_height": 26,
                    "minimum_subject_clearance": 10,
                },
            },
        },
    )

    # One compact visual audit makes the 18/26/34/46px avatar and the reserved
    # BP name strip reviewable without launching a match.
    contact = Image.new("RGBA", (880, 260), (10, 18, 31, 255))
    draw = ImageDraw.Draw(contact)
    label = (212, 226, 238, 255)
    draw.text((16, 10), "XAYAH UI PORTRAIT SURFACES / IDLE V3 SOURCE", fill=label)
    compact = Image.open(PORTRAIT_DIR / "dancer_compact.png").convert("RGBA")
    for index, runtime_size in enumerate((18, 26, 34, 46)):
        tile_x = 16 + index * 130
        draw.text((tile_x, 42), f"compact {runtime_size}px", fill=label)
        tile = Image.new("RGBA", (112, 112), (7, 13, 23, 255))
        runtime = compact.resize((runtime_size, runtime_size), Image.Resampling.NEAREST)
        tile.alpha_composite(runtime, ((112 - runtime_size) // 2, (112 - runtime_size) // 2))
        zoom = runtime.resize((runtime_size * 2, runtime_size * 2), Image.Resampling.NEAREST)
        tile.alpha_composite(zoom, ((112 - zoom.width) // 2, 112 - zoom.height))
        contact.alpha_composite(tile, (tile_x, 62))

    grid = Image.open(PORTRAIT_DIR / "dancer_grid.png").convert("RGBA")
    grid_tile = Image.new("RGBA", (110, 142), (7, 13, 23, 255))
    grid_tile.alpha_composite(grid, (10, 10))
    grid_draw = ImageDraw.Draw(grid_tile)
    grid_draw.rectangle((10, 106, 99, 131), fill=(34, 46, 64, 255))
    grid_draw.text((31, 111), "NAME", fill=(166, 181, 196, 255))
    draw.text((548, 42), "BP grid 90x122", fill=label)
    contact.alpha_composite(grid_tile, (548, 62))

    fullbody = Image.open(FULLBODY_DIR / "dancer.png").convert("RGBA")
    fullbody_tile = Image.new("RGBA", (142, 142), (7, 13, 23, 255))
    fullbody_zoom = fullbody.resize((128, 128), Image.Resampling.NEAREST)
    fullbody_tile.alpha_composite(fullbody_zoom, (7, 7))
    draw.text((700, 42), "encyclopedia 64", fill=label)
    contact.alpha_composite(fullbody_tile, (700, 62))
    draw.text((16, 226), "Compact = face focus; BP grid / encyclopedia = complete body.", fill=label)
    contact_path = QA_DIR / "xayah_portrait_surface_final.png"
    save_png(contact_path, contact)
    return [qa_path, contact_path]


def build_imagegen_provenance(runtime_paths: Iterable[Path]) -> Path:
    source_specs = [
        ("core_body_contact_v2", IMAGEGEN_ROOT / "xayah_core_body_contact_v2.png"),
        ("idle_body_contact_v3_two_eyes", IMAGEGEN_ROOT / "xayah_idle_contact_v3.png"),
        ("run_contact_v2", IMAGEGEN_ROOT / "xayah_run_contact_v2.png"),
        ("q_body_contact_v2", IMAGEGEN_ROOT / "xayah_q_body_contact_v2.png"),
        ("e_body_contact_v2", IMAGEGEN_ROOT / "xayah_e_body_contact_v2.png"),
        ("r_body_contact_v2", IMAGEGEN_ROOT / "xayah_r_body_contact_v2.png"),
        ("defeat_contact_v2", IMAGEGEN_ROOT / "xayah_defeat_contact_v2.png"),
        ("q_icon", Q_ICON_SOURCE),
        ("e_icon", E_ICON_SOURCE),
        ("r_icon", R_ICON_SOURCE),
        ("attack_vfx", IMAGEGEN_ROOT / "xayah_attack_vfx_contact.png"),
        ("q_vfx_v2", IMAGEGEN_ROOT / "xayah_q_vfx_contact_v2.png"),
        ("e_vfx_v3", IMAGEGEN_ROOT / "xayah_e_vfx_contact_v3.png"),
        ("r_vfx_v2", IMAGEGEN_ROOT / "xayah_r_vfx_contact_v2.png"),
        ("ground_feather_vfx_v1", IMAGEGEN_ROOT / "xayah_ground_feather_contact_v1.png"),
        ("bp_splash", SPLASH_SOURCE),
    ]
    processed_specs = [
        ("core_body_contact_v2_alpha", CORE_BODY_SOURCE),
        ("idle_body_contact_v3_alpha_two_eyes", IDLE_BODY_SOURCE),
        ("run_contact_v2_alpha", RUN_SOURCE),
        ("q_body_contact_v2_alpha", Q_BODY_SOURCE),
        ("e_body_contact_v2_alpha", E_BODY_SOURCE),
        ("r_body_contact_v2_alpha", R_BODY_SOURCE),
        ("defeat_contact_v2_alpha", DEFEAT_SOURCE),
        ("attack_vfx_alpha", ATTACK_VFX_SOURCE),
        ("q_vfx_v2_alpha", Q_VFX_SOURCE),
        ("e_vfx_v3_alpha", E_VFX_SOURCE),
        ("r_vfx_v2_alpha", R_VFX_SOURCE),
        ("ground_feather_vfx_v1_alpha", GROUND_FEATHER_VFX_SOURCE),
    ]
    path = QA_DIR / "xayah_imagegen_sources.json"
    write_json(
        path,
        {
            "schema_version": 1,
            "champion": "Xayah",
            "generator": "built-in image_gen",
            "generated_images_batch": "019f560d-2e11-70e1-a2b8-60cdebabc3ba",
            "additional_generated_images": [
                {
                    "role": "idle_body_contact_v3_two_eyes",
                    "execution_id": "exec-14c8a307-6e2b-4821-859a-9f62c5e391ef",
                },
                {
                    "role": "ground_feather_vfx_v1",
                    "execution_id": "exec-178182ff-7735-4228-b339-62352f37295c",
                }
            ],
            "generated_on": "2026-07-12",
            "prompt_record": "source/imagegen/PROMPTS.md#xayah-image-gen-prompts",
            "background_removal": "remove_chroma_key.py border auto-key, soft matte, thresholds 12/220, despill; builder hardens final actor/VFX alpha",
            "native_actor_contract": {
                "base_champion": "dancer",
                "sheet_size": list(ACTOR_SHEET_SIZE),
                "tag_order": list(NATIVE_CONTRACT),
                "frame_counts": {tag: len(spec["rects"]) for tag, spec in NATIVE_CONTRACT.items()},
                "body_source_policy": "idle and all portrait surfaces use the accepted two-eye v3 contact; attack/hit, run, Q, E, R and dead use independent locked-model contacts; Q/E/R source sets are disjoint",
                "placement_policy": "approximately 12-15% larger uniform nearest-neighbor scale plus per-frame foot-safe bottom margins; x-only compression is forbidden",
                "large_vfx_policy": "xayah_attack, xayah_q, xayah_e, xayah_r and bounded xayah_ground_feather markers are separate effect sheets; E/R runtime footprints are reduced after live scale review",
            },
            "rejected_runtime_sources": [
                {
                    "path": "source/processed/xayah_idle_contact_v2_alpha.png",
                    "status": "removed",
                    "reason": "superseded by the accepted v3 idle because the old compact face did not keep both eyes readable; both v2 source and alpha derivative were deleted",
                },
                {
                    "path": "source/processed/xayah_actor_contact_alpha.png",
                    "reason": "high-detail 320px bodies became unreadable at native size and reused E poses for R",
                },
                {
                    "path": "source/processed/xayah_run_contact_alpha.png",
                    "reason": "wide cape poses required 9.6%-43.7% horizontal compression and deformed in motion",
                },
                {
                    "path": "source/processed/xayah_q_vfx_contact_alpha.png",
                    "reason": "each projectile cell contained a pair and required unsafe half-cell cropping",
                },
                {
                    "path": "source/processed/xayah_r_vfx_contact_alpha.png",
                    "reason": "guard reused the landing row and did not provide a distinct empty-center afterimage ring",
                },
            ],
            "sources": [_image_record(role, item) for role, item in source_specs],
            "processed": [_image_record(role, item) for role, item in processed_specs],
            "runtime_files": [
                {"path": item.relative_to(MOD_ROOT).as_posix(), "size_bytes": item.stat().st_size, "sha256": sha256(item)}
                for item in runtime_paths
            ],
        },
    )
    return path


def build_audio_provenance() -> Path:
    outputs: list[dict[str, Any]] = []
    for spec in AUDIO_SPECS:
        wav_path = SOUND_DIR / f"{spec['stem']}_clip.wav"
        info = inspect_pcm_wav(wav_path)
        outputs.append(
            {
                "event_key": spec["stem"],
                "runtime_event": f"lol_{spec['stem']}",
                "riot_event": spec["riot_event"],
                "riot_event_id": spec["riot_event_id"],
                "event_media_pool": spec["pool"],
                "media_id": spec["media_id"],
                "source_wem_size_bytes": spec["wem_size"],
                "source_wem_sha256": spec["wem_sha"],
                "sound_info": f"sound/sfx/{spec['stem']}.sound_info",
                "clip": f"{spec['stem']}_clip",
                "volume": spec["volume"],
                "wav": {
                    "path": f"sound/sfx/{spec['stem']}_clip.wav",
                    "size_bytes": wav_path.stat().st_size,
                    "sha256": sha256(wav_path),
                    **info,
                },
            }
        )
    silence = SOUND_DIR / "xayah_native_silence_clip.wav"
    path = QA_DIR / "xayah_official_audio_sources.json"
    write_json(
        path,
        {
            "schema_version": 1,
            "champion": "Xayah",
            "source_product": "League of Legends",
            "source_wad": {
                "path": "Game/DATA/FINAL/Champions/Xayah.wad.client (local League install)",
                "size_bytes": 145872939,
                "sha256": "58a4f5cf7ba3ec2ef525d41c8c017a1f255d11ea8f2c82d05ed0a20c16df069e",
            },
            "internal_sources": {
                "audio_bank": {
                    "virtual_path": "assets/sounds/wwise2016/sfx/characters/xayah/skins/base/xayah_base_sfx_audio.bnk",
                    "path_hash": "6125bc30b3eb7ab2", "wad_offset": 99072831, "size_bytes": 1553257,
                    "media_count": 124, "sha256": "df185383564d23bf47d5821c5ad137be772274ef00187edd2e78a7127e028c36",
                },
                "event_bank": {
                    "virtual_path": "assets/sounds/wwise2016/sfx/characters/xayah/skins/base/xayah_base_sfx_events.bnk",
                    "path_hash": "c3a1b9da425b1491", "size_bytes": 21207,
                    "sha256": "ce3d5980de2e6ef1a095eb76e39ada1f1211ab8d3df6a665cffcd56950823c70",
                },
                "base_registry": {
                    "virtual_path": "data/characters/xayah/skins/skin0.bin", "path_hash": "3c1cb7d7ef7cff09",
                    "size_bytes": 188359, "sha256": "234180ef61de94d91e8e064e7390ea6e3c5b64414ecc0fbb094733d176a6b93a",
                },
            },
            "event_mapping_audit": {
                "resolver": "base registry Riot event strings + lowercase FNV-1 IDs + wwiser v20250928 event-bank media pools",
                "selection_policy": "One verified official base-skin media variant per event; material-specific attack-hit pools are excluded.",
            },
            "tools": {
                "wadtools": {"version": "0.5.6", "sha256": "c11b60cc8016c3d986eceb91c3c9fd74e4440416ba2a215af1135f36bd0fa866"},
                "wwiser": {"version": "v20250928", "sha256": "fdcb850ad19d827190a1eb137c2caa02c40671e15c379a6c9a477d2a5237bf53"},
                "vgmstream_cli": {"sha256": "894cff498bbb7d43fcbae63aac9dc19ebbef8f37c9889c4a9e51de407b5f3c07"},
                "game_hashtable": {"size_bytes": 207968174, "sha256": "f7d5e73ff1c4b7b4630cef6d4bafe3d1b7a80a2f51e3bf9d4db4e018954d041b"},
            },
            "decoder": {"name": "vgmstream-cli", "arguments": ["-i", "-W", "1"], "output_contract": "mono PCM16 44100 Hz"},
            "native_audio_isolation": {
                "strategy": "same-ID Dancer native events/clips are remapped by mod.override_info to one deterministic physical-silence asset",
                "silence_sound_info": "sound/sfx/xayah_native_silence.sound_info",
                "silence_wav": {"path": "sound/sfx/xayah_native_silence_clip.wav", "size_bytes": silence.stat().st_size, "sha256": sha256(silence), **inspect_pcm_wav(silence), "pcm_contract": "all-zero samples"},
            },
            "outputs": outputs,
        },
    )
    return path


def validate_outputs(actor_sheet: Path, actor_anim: Path, outputs: Iterable[Path]) -> None:
    if Image.open(actor_sheet).size != ACTOR_SHEET_SIZE:
        raise ValueError("Xayah actor sheet changed native 007 canvas size")
    payload = json.loads(actor_anim.read_text(encoding="utf-8"))
    if list(payload["anims"]) != list(NATIVE_CONTRACT):
        raise ValueError("Xayah actor tag order changed native 007 contract")
    for tag, spec in NATIVE_CONTRACT.items():
        frames = payload["anims"][tag]["frames"]
        if len(frames) != len(spec["rects"]):
            raise ValueError(f"Xayah {tag} frame count changed")
        if [frame["duration"] for frame in frames] != spec["durations"]:
            raise ValueError(f"Xayah {tag} frame duration changed")
        actual_rects = [
            tuple(frame["data"][key] for key in ("x", "y", "w", "h"))
            for frame in frames
        ]
        if actual_rects != spec["rects"]:
            raise ValueError(f"Xayah {tag} frame rectangles changed")
    sheet = Image.open(actor_sheet).convert("RGBA")
    visible_records: dict[str, list[dict[str, Any]]] = {}
    for tag, target_heights in BODY_TARGET_HEIGHTS.items():
        visible_records[tag] = []
        for index, (frame_data, target_height, expected_bottom) in enumerate(
            zip(
                payload["anims"][tag]["frames"],
                target_heights,
                BODY_BOTTOM_MARGINS[tag],
                strict=True,
            )
        ):
            rect = frame_data["data"]
            frame = sheet.crop(
                (
                    rect["x"],
                    rect["y"],
                    rect["x"] + rect["w"],
                    rect["y"] + rect["h"],
                )
            )
            bbox = frame.getchannel("A").point(lambda value: 255 if value >= 64 else 0).getbbox()
            if bbox is None:
                raise ValueError(f"Xayah {tag}[{index}] body frame is empty")
            visible_height = bbox[3] - bbox[1]
            bottom = rect["h"] - bbox[3]
            native_width_limited = (
                visible_height < target_height
                and bbox[0] <= 1
                and rect["w"] - bbox[2] <= 1
            )
            if abs(visible_height - target_height) > 2 and not native_width_limited:
                raise ValueError(
                    f"Xayah {tag}[{index}] changed scale class: {visible_height}px vs {target_height}px"
                )
            if bottom != expected_bottom:
                raise ValueError(
                    f"Xayah {tag}[{index}] bottom anchor {bottom}px != native profile {expected_bottom}px"
                )
            if bottom < 4:
                raise ValueError(f"Xayah {tag}[{index}] touches the label/ground edge")
            visible_records[tag].append(
                {
                    "bbox": list(bbox),
                    "visible_size": [bbox[2] - bbox[0], visible_height],
                    "bottom_margin": bottom,
                    "frame_sha256": hashlib.sha256(frame.tobytes()).hexdigest(),
                }
            )

    if len({row["frame_sha256"] for row in visible_records["run"]}) != 8:
        raise ValueError("Xayah run must keep eight distinct final-scale gait phases")

    # R must visibly rise, reach an apex and descend in the actor sheet itself;
    # the independent guard ring cannot be the only airborne cue.
    r_altitudes = []
    for frame_data, record in zip(payload["anims"]["ult"]["frames"], visible_records["ult"], strict=True):
        bbox = record["bbox"]
        r_altitudes.append(frame_data["data"]["h"] - (bbox[1] + bbox[3]) / 2)
    if not (r_altitudes[0] < r_altitudes[1] < r_altitudes[2] > r_altitudes[3] > r_altitudes[4]):
        raise ValueError(f"Xayah R actor does not rise/apex/descend: {r_altitudes}")

    if len({Q_BODY_SOURCE, E_BODY_SOURCE, R_BODY_SOURCE}) != 3:
        raise ValueError("Xayah Q, E and R body contacts must be disjoint")

    idle_rect = NATIVE_CONTRACT["idle"]["rects"][0]
    x, y, width, height = idle_rect
    idle_frame = sheet.crop((x, y, x + width, y + height))
    idle_bbox = idle_frame.getchannel("A").point(lambda value: 255 if value >= 64 else 0).getbbox()
    if idle_bbox is None or height - idle_bbox[3] < 4:
        raise ValueError(f"Xayah first idle frame lacks bottom-label clearance: {idle_bbox}")

    # Coarse skin-color proxy inside the upper body verifies that the final
    # sprite retained a readable face opening instead of a two-pixel blur.
    skin_points: list[tuple[int, int]] = []
    max_face_y = idle_bbox[1] + round((idle_bbox[3] - idle_bbox[1]) * 0.55)
    for pixel_y in range(idle_bbox[1], max_face_y):
        for pixel_x in range(idle_bbox[0], idle_bbox[2]):
            red, green, blue, alpha = idle_frame.getpixel((pixel_x, pixel_y))
            if alpha >= 64 and red >= 150 and green >= 80 and blue >= 45 and red > green:
                skin_points.append((pixel_x, pixel_y))
    if not skin_points:
        raise ValueError("Xayah first idle frame lost its face colors")
    face_bbox = (
        min(point[0] for point in skin_points),
        min(point[1] for point in skin_points),
        max(point[0] for point in skin_points) + 1,
        max(point[1] for point in skin_points) + 1,
    )
    if face_bbox[2] - face_bbox[0] < 6 or face_bbox[3] - face_bbox[1] < 6:
        raise ValueError(f"Xayah final face opening is below 6x6 pixels: {face_bbox}")

    e_anim = json.loads((EFFECT_DIR / "xayah_e#anim.fanim").read_text(encoding="utf-8"))["anims"]
    if list(e_anim) != ["return_single", "return_double", "return_cluster", "root", "hit"]:
        raise ValueError(f"Xayah E VFX tags are not independently packed: {list(e_anim)}")
    r_anim = json.loads((EFFECT_DIR / "xayah_r#anim.fanim").read_text(encoding="utf-8"))["anims"]
    if list(r_anim) != ["fan", "hit", "guard"]:
        raise ValueError(f"Xayah R guard tag is missing: {list(r_anim)}")
    ground_sheet = Image.open(EFFECT_DIR / "xayah_ground_feather#sheet.png").convert("RGBA")
    ground_anim = json.loads(
        (EFFECT_DIR / "xayah_ground_feather#anim.fanim").read_text(encoding="utf-8")
    )["anims"]
    if list(ground_anim) != ["ground_single", "ground_fan"]:
        raise ValueError(f"Xayah ground Feather tags changed: {list(ground_anim)}")
    for tag, animation in ground_anim.items():
        terminal_data = animation["frames"][-1]["data"]
        terminal = ground_sheet.crop(
            (
                terminal_data["x"],
                terminal_data["y"],
                terminal_data["x"] + terminal_data["w"],
                terminal_data["y"] + terminal_data["h"],
            )
        )
        if terminal.getchannel("A").getbbox() is not None:
            raise ValueError(f"Xayah {tag} marker must end on a transparent frame")

    if Image.open(SPLASH_DIR / "dancer.png").size != (1420, 860):
        raise ValueError("Xayah BP splash size changed")
    portrait = Image.open(FULLBODY_DIR / "dancer.png").convert("RGBA")
    if portrait.size != (64, 64):
        raise ValueError("Xayah encyclopedia portrait size changed")
    portrait_bbox = portrait.getchannel("A").point(lambda value: 255 if value >= 64 else 0).getbbox()
    if portrait_bbox is None or portrait_bbox[3] != 60 or portrait_bbox[3] - portrait_bbox[1] > 56:
        raise ValueError(f"Xayah full-body portrait lost its 4px bottom safety margin: {portrait_bbox}")
    compact = Image.open(PORTRAIT_DIR / "dancer_compact.png").convert("RGBA")
    compact_bbox = compact.getchannel("A").getbbox()
    if (
        compact.size != (64, 64)
        or compact_bbox is None
        or compact_bbox[2] - compact_bbox[0] > 50
        or compact_bbox[3] - compact_bbox[1] > 50
        or min(
            compact_bbox[0],
            compact_bbox[1],
            64 - compact_bbox[2],
            64 - compact_bbox[3],
        ) < 6
    ):
        raise ValueError(f"Xayah compact portrait is invalid: size={compact.size}, bbox={compact_bbox}")
    grid = Image.open(PORTRAIT_DIR / "dancer_grid.png").convert("RGBA")
    grid_bbox = grid.getchannel("A").getbbox()
    if grid.size != (90, 122) or grid_bbox is None or grid_bbox[3] > 86:
        raise ValueError(f"Xayah BP-grid portrait overlaps the name band: size={grid.size}, bbox={grid_bbox}")
    missing = [path for path in outputs if not path.is_file()]
    if missing:
        raise FileNotFoundError("Missing Xayah outputs:\n" + "\n".join(str(path) for path in missing))


def build_all() -> list[Path]:
    required = [
        CORE_BODY_SOURCE, IDLE_BODY_SOURCE, RUN_SOURCE, Q_BODY_SOURCE, E_BODY_SOURCE, R_BODY_SOURCE, DEFEAT_SOURCE,
        ATTACK_VFX_SOURCE, Q_VFX_SOURCE, E_VFX_SOURCE, R_VFX_SOURCE,
        Q_ICON_SOURCE, E_ICON_SOURCE, R_ICON_SOURCE, SPLASH_SOURCE,
        *(SOUND_DIR / f"{spec['stem']}_clip.wav" for spec in AUDIO_SPECS),
    ]
    missing = [path for path in required if not path.is_file()]
    if missing:
        raise FileNotFoundError("Missing Xayah source assets:\n" + "\n".join(str(path) for path in missing))
    actor_sheet, actor_anim, _ = build_actor()
    icons = build_icons()
    vfx = build_vfx()
    splash = build_splash_and_fullbody(actor_sheet)
    audio = build_audio_assets()
    runtime_visuals = [actor_sheet, actor_anim, *icons, *vfx, *splash]
    ui_scale_qa = build_ui_scale_qa(actor_sheet, actor_anim)
    imagegen_provenance = build_imagegen_provenance(runtime_visuals)
    audio_provenance = build_audio_provenance()
    outputs = [
        *runtime_visuals,
        *audio,
        *ui_scale_qa,
        imagegen_provenance,
        audio_provenance,
    ]
    validate_outputs(actor_sheet, actor_anim, outputs)
    return outputs


def main() -> int:
    for path in build_all():
        print(path.relative_to(MOD_ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
