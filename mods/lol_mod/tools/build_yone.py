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
FOLLOWUP_VFX_SOURCE = IMAGEGEN_ROOT / "yone_followup_vfx_contact.png"
R_VFX_SOURCE = IMAGEGEN_ROOT / "yone_r_vfx_contact.png"
ICON_SOURCE = IMAGEGEN_ROOT / "yone_icons_source.png"
SPLASH_SOURCE = IMAGEGEN_ROOT / "bp_splash" / "dual_blader.png"

CORE_ALPHA = PROCESSED_ROOT / "yone_core_contact_alpha.png"
RUN_ALPHA = PROCESSED_ROOT / "yone_run_contact_alpha.png"
WR_BODY_ALPHA = PROCESSED_ROOT / "yone_wr_body_contact_alpha.png"
DEFEAT_ALPHA = PROCESSED_ROOT / "yone_defeat_contact_alpha.png"
QW_VFX_ALPHA = PROCESSED_ROOT / "yone_qw_vfx_contact_alpha.png"
FOLLOWUP_VFX_ALPHA = PROCESSED_ROOT / "yone_followup_vfx_contact_alpha.png"
R_VFX_ALPHA = PROCESSED_ROOT / "yone_r_vfx_contact_alpha.png"

ACTOR_SHEET_SIZE = (3502, 88)


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
        (FOLLOWUP_VFX_SOURCE, FOLLOWUP_VFX_ALPHA),
        (R_VFX_SOURCE, R_VFX_ALPHA),
    ):
        save_processed_png(target, remove_chroma_key(Image.open(source)))
        outputs.append(target)
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
    return fit_subject(
        source,
        frame_size,
        max_subject=(max(1, frame_size[0] - 2), min(target_height, frame_size[1] - bottom_margin - 1)),
        anchor_bottom=frame_size[1] - bottom_margin,
        colors=48,
        component_minimum=24,
        final_component_minimum=3,
    )


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
        "skill2_attack": [wr[14], wr[19], wr[2], wr[3], wr[4]],
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


def build_effects() -> list[Path]:
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
            ("empowered_projectile", [10, 11, 12, 13, 14, None], (104, 64), 0.06),
            ("hit", [6, 7, 8, 9, None], (64, 48), 0.05),
            ("empowered_hit", [11, 12, 13, 14, None], (80, 64), 0.06),
        ],
    )
    # W / Sealed Pursuit owns a compact follow-up sheet.  It deliberately
    # avoids the old Q-atlas crescents and full circular shield that obscured
    # Yone's actor and made the pursuit read like a duplicate spirit body.
    outputs += build_effect_sheet(
        "yone_followup", FOLLOWUP_VFX_ALPHA, (5, 5),
        [
            ("lock", [0, 1, 2, 3, None], (64, 40), 0.05),
            ("dash", [5, 6, 7, 8, 9, None], (112, 56), 0.05),
            ("cross", [10, 11, 12, 13, None], (96, 64), 0.05),
            ("airborne", [15, 16, 17, 18, None], (48, 64), 0.05),
            ("guard", [20, 21, 22, 23, None], (64, 56), 0.06),
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
    for filename, cell in zip(("yone_skill.png", "yone_skill2.png", "yone_ult.png"), cells, strict=True):
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

    fullbody = render_ui_subject(full_body, (64, 64), max_subject=(54, 56), bottom=60, colors=96)
    fullbody_path = FULLBODY_DIR / "dual_blader.png"
    save_png(fullbody_path, fullbody)

    # Compact uses the upper 62% of the accepted high-resolution idle source,
    # preserving face, both eyes, horned mask, shoulders, and a transparent
    # border at 18/26/34/46px runtime sizes.
    width, height = full_body.size
    face_focus = full_body.crop((round(width * 0.12), 0, round(width * 0.88), round(height * 0.62)))
    compact = render_ui_subject(face_focus, (64, 64), max_subject=(50, 50), bottom=58, colors=112)
    compact_path = PORTRAIT_DIR / "dual_blader_compact.png"
    save_png(compact_path, compact)

    # The native 90x122 grid texture reserves y=96..121 for the name band.
    # End the silhouette by y=86 to leave ten transparent pixels above it.
    grid = render_ui_subject(full_body, (90, 122), max_subject=(76, 82), bottom=86, colors=128)
    grid_path = PORTRAIT_DIR / "dual_blader_grid.png"
    save_png(grid_path, grid)
    return [splash_path, fullbody_path, compact_path, grid_path]


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
    "lol_yone_q_empowered_projectile": ["yone_q", "empowered_projectile"],
    "lol_yone_q_hit": ["yone_q", "hit"],
    "lol_yone_q_empowered_hit": ["yone_q", "empowered_hit"],
    "lol_yone_w_lock": ["yone_followup", "lock"],
    "lol_yone_w_dash_visual": ["yone_followup", "dash"],
    "lol_yone_w_cross": ["yone_followup", "cross"],
    "lol_yone_w_airborne": ["yone_followup", "airborne"],
    "lol_yone_w_guard": ["yone_followup", "guard"],
    "lol_yone_r_windup": ["yone_r", "windup"],
    "lol_yone_r_arrival": ["yone_r", "arrival"],
    "lol_yone_r_slash_blue": ["yone_r", "slash_blue"],
    "lol_yone_r_slash_red": ["yone_r", "slash_red"],
    "lol_yone_r_echo": ["yone_r", "echo"],
}


def build_qa(
    processed: Sequence[Path],
    actor_sheet: Path,
    actor_anim: Path,
    runtime_visuals: Sequence[Path],
) -> list[Path]:
    sheet = Image.open(actor_sheet).convert("RGBA")
    anims = json.loads(actor_anim.read_text(encoding="utf-8"))["anims"]
    body_frames: dict[str, list[dict[str, Any]]] = {}
    for tag in BODY_TARGET_HEIGHTS:
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
            "large_vfx_policy": "Q/W/R feedback is isolated in yone_q/yone_followup/yone_r sheets; W uses narrow target, trail, cross, airborne and open guard cues instead of an enclosing ring.",
            "portrait_policy": {
                "compact": "64x64 face focus, <=50x50 alpha bbox, >=6px border",
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
            "generated_on": "2026-07-14",
            "processing": "deterministic green-screen soft matte, despill, hard-alpha final packing, palette reduction, no generated repaint",
            "sources": [image_record(path) for path in (CORE_SOURCE, RUN_SOURCE, WR_BODY_SOURCE, DEFEAT_SOURCE, QW_VFX_SOURCE, FOLLOWUP_VFX_SOURCE, R_VFX_SOURCE, ICON_SOURCE, SPLASH_SOURCE)],
            "processed": [image_record(path) for path in processed],
            "runtime": [image_record(path) if path.suffix == ".png" else {"path": path.relative_to(MOD_ROOT).as_posix(), "size_bytes": path.stat().st_size, "sha256": sha256(path)} for path in runtime_visuals],
        },
    )

    visual_md = QA_DIR / "yone_visual_qa.md"
    visual_md.write_text(
        """# Yone visual QA\n\n"
        "- [x] Same-ID visual replacement targets `dual_blader` (official project hero 009).\n"
        "- [x] Actor canvas is exactly `3502x88`; all 13 native tags, frame counts, durations, rectangles, and insertion order are preserved.\n"
        "- [x] `hit_effect_area` reuses the official `ult[1..11]` atlas rectangles without conflicting pixels.\n"
        "- [x] Idle/run/attack/Q/W/R/dead bodies use independent generated pose groups while retaining one stable battle scale.\n"
        "- [x] Q/W/R feedback is packed into separate `yone_q`, `yone_followup`, and `yone_r` sheets. W uses a short target lock, narrow dual trail, compact cross, airborne cue and open guard instead of a full circular overlay.\n"
        "- [x] Compact portrait is face-focused with transparent safety margins.\n"
        "- [x] BP-grid portrait is full body and ends at `y<=86`, ten pixels above the native name band.\n"
        "- [x] BP illustration is `1420x860`; Q/W/R icons are independent `64x64` assets.\n"
        "\nRuntime effect IDs and sheet tags are recorded in `qa/yone_visual_contract.json`.\n""",
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
        ("fullbody", FULLBODY_DIR / "dual_blader.png", (210, 300)),
        ("grid", PORTRAIT_DIR / "dual_blader_grid.png", (402, 278)),
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

    idle_data = payload["idle"]["frames"][0]["data"]
    idle = sheet.crop(
        (
            idle_data["x"], idle_data["y"],
            idle_data["x"] + idle_data["w"], idle_data["y"] + idle_data["h"],
        )
    )
    idle_bbox = idle.getchannel("A").getbbox()
    skin: list[tuple[int, int]] = []
    if idle_bbox is not None:
        face_limit = idle_bbox[1] + round((idle_bbox[3] - idle_bbox[1]) * 0.62)
        for y in range(idle_bbox[1], face_limit):
            for x in range(idle_bbox[0], idle_bbox[2]):
                red, green, blue, alpha = idle.getpixel((x, y))
                if alpha and red >= 135 and green >= 70 and blue >= 45 and red > green:
                    skin.append((x, y))
    if not skin:
        raise ValueError("Yone idle lost readable face colors")
    face_bbox = (
        min(x for x, _ in skin), min(y for _, y in skin),
        max(x for x, _ in skin) + 1, max(y for _, y in skin) + 1,
    )
    if face_bbox[2] - face_bbox[0] < 5 or face_bbox[3] - face_bbox[1] < 5:
        raise ValueError(f"Yone idle face opening is below 5x5 pixels: {face_bbox}")

    terminal_rect = NATIVE_CONTRACT["dead"]["rects"][-1]
    terminal = sheet.crop((terminal_rect[0], terminal_rect[1], terminal_rect[0] + terminal_rect[2], terminal_rect[1] + terminal_rect[3]))
    if terminal.getchannel("A").getbbox() is not None:
        raise ValueError("Yone dead terminal 3x3 frame must stay transparent")

    for effect, required_tags in {
        "yone_attack": ["steel_hit", "azakana_hit"],
        "yone_q": ["projectile", "empowered_projectile", "hit", "empowered_hit"],
        "yone_followup": ["lock", "dash", "cross", "airborne", "guard"],
        "yone_r": ["windup", "arrival", "slash_blue", "slash_red", "echo"],
    }.items():
        anims = json.loads((EFFECT_DIR / f"{effect}#anim.fanim").read_text(encoding="utf-8"))["anims"]
        if list(anims) != required_tags:
            raise ValueError(f"Yone {effect} tags changed: {list(anims)}")
        effect_sheet = Image.open(EFFECT_DIR / f"{effect}#sheet.png").convert("RGBA")
        for tag in required_tags:
            final = anims[tag]["frames"][-1]["data"]
            image = effect_sheet.crop((final["x"], final["y"], final["x"] + final["w"], final["y"] + final["h"]))
            if image.getchannel("A").getbbox() is not None:
                raise ValueError(f"Yone {effect}:{tag} must terminate transparent")

    compact = Image.open(PORTRAIT_DIR / "dual_blader_compact.png").convert("RGBA")
    compact_bbox = compact.getchannel("A").getbbox()
    if compact.size != (64, 64) or compact_bbox is None:
        raise ValueError("Yone compact portrait is missing")
    if compact_bbox[2] - compact_bbox[0] > 50 or compact_bbox[3] - compact_bbox[1] > 50:
        raise ValueError(f"Yone compact portrait subject exceeds 50x50: {compact_bbox}")
    if min(compact_bbox[0], compact_bbox[1], 64 - compact_bbox[2], 64 - compact_bbox[3]) < 6:
        raise ValueError(f"Yone compact portrait lacks 6px transparent margin: {compact_bbox}")

    grid = Image.open(PORTRAIT_DIR / "dual_blader_grid.png").convert("RGBA")
    grid_bbox = grid.getchannel("A").getbbox()
    if grid.size != (90, 122) or grid_bbox is None or grid_bbox[3] > 86:
        raise ValueError(f"Yone BP-grid portrait overlaps name band: {grid_bbox}")
    if Image.open(FULLBODY_DIR / "dual_blader.png").size != (64, 64):
        raise ValueError("Yone encyclopedia portrait is not 64x64")
    if Image.open(SPLASH_DIR / "dual_blader.png").size != (1420, 860):
        raise ValueError("Yone BP splash is not 1420x860")
    for icon in ("yone_skill.png", "yone_skill2.png", "yone_ult.png"):
        if Image.open(ICON_DIR / icon).size != (64, 64):
            raise ValueError(f"Yone icon {icon} is not 64x64")
    for processed in (CORE_ALPHA, RUN_ALPHA, WR_BODY_ALPHA, DEFEAT_ALPHA, QW_VFX_ALPHA, FOLLOWUP_VFX_ALPHA, R_VFX_ALPHA):
        alpha = Image.open(processed).convert("RGBA").getchannel("A")
        corners = [alpha.getpixel((0, 0)), alpha.getpixel((alpha.width - 1, 0)), alpha.getpixel((0, alpha.height - 1)), alpha.getpixel((alpha.width - 1, alpha.height - 1))]
        if any(corners):
            raise ValueError(f"Yone processed chroma plate has opaque corner pixels: {processed.name} {corners}")
    missing = [path for path in outputs if not path.is_file()]
    if missing:
        raise FileNotFoundError("Missing Yone outputs:\n" + "\n".join(str(path) for path in missing))


def build_all() -> list[Path]:
    required = [CORE_SOURCE, RUN_SOURCE, WR_BODY_SOURCE, DEFEAT_SOURCE, QW_VFX_SOURCE, FOLLOWUP_VFX_SOURCE, R_VFX_SOURCE, ICON_SOURCE, SPLASH_SOURCE]
    missing = [path for path in required if not path.is_file()]
    if missing:
        raise FileNotFoundError("Missing Yone image-gen sources:\n" + "\n".join(str(path) for path in missing))
    processed = process_sources()
    actor_sheet, actor_anim = build_actor()
    effects = build_effects()
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
