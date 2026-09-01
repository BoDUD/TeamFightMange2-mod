#!/usr/bin/env python3
"""Build champion assets and optionally rebuild the quality-upgrade runtime pack."""

from __future__ import annotations

import argparse
import binascii
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import sys
import wave

from PIL import Image, ImageDraw

from build_kled import build_all as build_kled_assets
from build_urgot import build_all as build_urgot_assets
from build_xayah import build_all as build_xayah_assets
from build_yone import build_all as build_yone_assets
from qa_legacy_battle_actor_scale import (
    build_all as build_legacy_battle_actor_scale_qa,
)


MOD_ROOT = Path(__file__).resolve().parents[1]
SOURCE = MOD_ROOT / "source" / "processed"
ACTOR_DIR = MOD_ROOT / "aseprite_resources" / "champions"
EFFECT_DIR = MOD_ROOT / "aseprite_resources" / "effects"
ICON_DIR = MOD_ROOT / "icons"
UI_ASEPRITE_DIR = MOD_ROOT / "aseprite_resources" / "UI_aseprite"
CHAMPION_FULLBODY_DIR = MOD_ROOT / "ui" / "champion_fullbody"
CHAMPION_PORTRAIT_DIR = MOD_ROOT / "ui" / "champion_portrait"
SETTING_DIR = MOD_ROOT / "setting"
QA_DIR = MOD_ROOT / "qa"
BASE_SOURCE = MOD_ROOT / "source" / "base"
QUALITY_BUILDERS = (
    "pack_quality_items.py",
    "pack_quality_objectives.py",
    "pack_quality_small_jungle.py",
    "pack_quality_missing_lol_camps.py",
    "pack_quality_objective_ui.py",
    "pack_quality_towers.py",
    "pack_quality_nexus.py",
    "pack_quality_map.py",
    "pack_quality_bp_skin.py",
    "pack_quality_ingame_hud.py",
)

ACTOR_SOURCE = SOURCE / "shen_actor_contact_alpha.png"
RUN_SOURCE = SOURCE / "shen_run_contact_alpha.png"
ICON_SOURCES = {
    "shen_skill.png": SOURCE / "shen_q_icon_source_alpha.png",
    "shen_skill2.png": SOURCE / "shen_e_icon_source_alpha.png",
    "shen_ult.png": SOURCE / "shen_r_icon_source_alpha.png",
}
VFX_SOURCES = {
    "shen_q": (SOURCE / "shen_q_vfx_contact_alpha.png", 4, 2, (64, 64), (58, 48)),
    "shen_e": (SOURCE / "shen_e_vfx_contact_alpha.png", 3, 2, (96, 64), (88, 40)),
    "shen_r": (SOURCE / "shen_r_vfx_contact_alpha.png", 4, 2, (112, 112), (100, 100)),
}

LUCIAN_ACTOR_SOURCE = SOURCE / "lucian_actor_master_v3_alpha.png"
LUCIAN_RUN_SOURCE = SOURCE / "lucian_run_master_v2_alpha.png"
LUCIAN_ICON_SOURCES = {
    "lucian_skill.png": SOURCE / "lucian_q_icon_source_alpha.png",
    "lucian_skill2.png": SOURCE / "lucian_e_icon_source_alpha.png",
    "lucian_ult.png": SOURCE / "lucian_r_icon_source_alpha.png",
}
LUCIAN_VFX_SOURCES = {
    "lucian_attack": (SOURCE / "lucian_attack_vfx_contact_alpha.png", 4, 2, (64, 32), (52, 16)),
    "lucian_q": (SOURCE / "lucian_q_vfx_contact_v3_alpha.png", 4, 2, (192, 32), (80, 18)),
    "lucian_r": (SOURCE / "lucian_r_vfx_contact_alpha.png", 4, 2, (64, 32), (48, 18)),
}
LUCIAN_ACTOR_KEEP_BOXES: list[tuple[int, int, int, int] | None] = [
    None,
    None,
    (40, 85, 272, 340),
    (20, 90, 250, 340),
    (100, 50, 328, 300),
    (80, 45, 312, 300),
    None,
    None,
    None,
    (75, 40, 297, 290),
    None,
    None,
]

ORIANNA_ACTOR_SOURCE = SOURCE / "orianna_actor_contact_alpha.png"
ORIANNA_RUN_SOURCE = SOURCE / "orianna_run_contact_alpha.png"
ORIANNA_ICON_SOURCES = {
    "orianna_skill.png": SOURCE / "orianna_q_icon_source_alpha.png",
    "orianna_skill2.png": SOURCE / "orianna_e_icon_source_alpha.png",
    "orianna_ult.png": SOURCE / "orianna_r_icon_source_alpha.png",
}
ORIANNA_VFX_SOURCES = {
    "orianna_attack": SOURCE / "orianna_attack_vfx_contact_alpha.png",
    "orianna_q": SOURCE / "orianna_q_vfx_contact_alpha.png",
    "orianna_e_shield": SOURCE / "orianna_e_vfx_contact_alpha.png",
    "orianna_r_ring": SOURCE / "orianna_r_vfx_contact_alpha.png",
}

BRIAR_ACTOR_SOURCE = SOURCE / "briar_actor_contact_alpha.png"
BRIAR_RUN_SOURCE = SOURCE / "briar_run_contact_alpha.png"
BRIAR_ICON_SOURCES = {
    "briar_skill.png": MOD_ROOT / "source" / "imagegen" / "briar_q_icon_source.png",
    "briar_skill2.png": MOD_ROOT / "source" / "imagegen" / "briar_e_icon_source.png",
    "briar_ult.png": MOD_ROOT / "source" / "imagegen" / "briar_r_icon_source.png",
}
BRIAR_VFX_SOURCES = {
    "briar_bleed": SOURCE / "briar_bleed_vfx_contact_alpha.png",
    "briar_q_overhead": SOURCE
    / "champions"
    / "004_briar"
    / "briar_q_overhead_v1_alpha.png",
    "briar_frenzy": SOURCE / "briar_frenzy_vfx_contact_alpha.png",
    "briar_e_scream": SOURCE / "briar_e_vfx_contact_alpha.png",
    "briar_r": SOURCE / "briar_r_vfx_contact_alpha.png",
}

SIVIR_ACTOR_SOURCE = SOURCE / "sivir_actor_contact_alpha.png"
SIVIR_RUN_SOURCE = SOURCE / "sivir_run_contact_alpha.png"
SIVIR_ICON_SOURCES = {
    "sivir_skill.png": MOD_ROOT / "source" / "imagegen" / "sivir_q_icon_source.png",
    "sivir_skill2.png": MOD_ROOT / "source" / "imagegen" / "sivir_e_icon_source.png",
    "sivir_ult.png": MOD_ROOT / "source" / "imagegen" / "sivir_r_icon_source.png",
}
SIVIR_VFX_SOURCES = {
    "sivir_attack": SOURCE / "sivir_attack_vfx_contact_alpha.png",
    "sivir_q": SOURCE / "sivir_q_vfx_contact_alpha.png",
    "sivir_e_shield": SOURCE / "sivir_e_vfx_contact_alpha.png",
    "sivir_r_cast": SOURCE / "sivir_r_cast_vfx_contact_alpha.png",
    "sivir_hunt_buff": SOURCE / "sivir_hunt_buff_vfx_contact_alpha.png",
}
SIVIR_ACTOR_KEEP_BOXES: list[tuple[int, int, int, int]] = [
    (25, 25, 260, 285),
    (325, 25, 560, 285),
    (600, 45, 870, 285),
    (895, 45, 1122, 285),
    (20, 315, 290, 585),
    (345, 330, 610, 585),
    (620, 315, 890, 585),
    (950, 285, 1175, 590),
    (15, 625, 280, 880),
    (340, 625, 550, 880),
    (575, 645, 875, 875),
    (885, 625, 1175, 880),
    (15, 900, 285, 1165),
    (300, 970, 625, 1170),
    (640, 915, 875, 1160),
    (885, 925, 1175, 1160),
]

# Battle actors are sized independently from source-direct UI portraits.  The
# five legacy 64x64 atlases previously drifted into a 38-44px scale class even
# though their occupied native actors and the accepted Yone/Kled references
# sit mostly in the mid/high 30s.  Keep explicit per-champion targets: weapons,
# hair and body proportions differ too much for one roster-wide multiplier.
SHEN_BATTLE_IDLE_HEIGHT = 36
SHEN_BATTLE_FOOT_BASELINE = 45
SHEN_BATTLE_MAX_SIZE = (40, 38)
LUCIAN_BATTLE_IDLE_HEIGHT = 36
LUCIAN_BATTLE_FOOT_BASELINE = 45
LUCIAN_BATTLE_MAX_SIZE = (36, 40)
ORIANNA_BATTLE_IDLE_HEIGHT = 36
ORIANNA_BATTLE_FOOT_BASELINE = 42
ORIANNA_BATTLE_MAX_SIZE = (36, 36)
BRIAR_BATTLE_IDLE_HEIGHT = 38
BRIAR_BATTLE_FOOT_BASELINE = 45
BRIAR_BATTLE_MAX_SIZE = (42, 40)
SIVIR_BATTLE_IDLE_HEIGHT = 36
SIVIR_BATTLE_FOOT_BASELINE = 45
SIVIR_BATTLE_MAX_SIZE = (44, 38)

CHAMPION_FULLBODY_SHEETS = {
    "lol_shen": ACTOR_DIR / "shen#sheet.png",
    "archer": ACTOR_DIR / "lucian#sheet.png",
    "barrier_magician": ACTOR_DIR / "orianna#sheet.png",
    "berserker": ACTOR_DIR / "briar#sheet.png",
    "boomerang_hunter": ACTOR_DIR / "sivir#sheet.png",
    "cavalry_knight": ACTOR_DIR / "kled#sheet.png",
    "dancer": ACTOR_DIR / "xayah#sheet.png",
    "dual_blader": ACTOR_DIR / "yone_v7#sheet.png",
}
BASE_SKILL_ICON_SOURCE = BASE_SOURCE / "skill_icon_base.png"
BASE_CHAMPION_INFO_SOURCE = BASE_SOURCE / "champion_info_base.champion_info_sheet"
ARCHER_SKILL_ICON_BOXES = {
    "archer_0": (25, 0, 49, 24),
    "archer_1": (1625, 0, 1649, 24),
    "archer_2": (3225, 0, 3249, 24),
    "archer_3": (750, 24, 774, 48),
    "archer_4": (2350, 24, 2374, 48),
}

# These masks remove the large VFX already separated into dedicated sheets while
# retaining the exact accepted image-gen actor model and its compact spirit blade.
ACTOR_KEEP_BOXES = [
    (70, 45, 310, 350),
    (70, 45, 310, 350),
    (55, 65, 315, 350),
    (55, 75, 315, 350),
    (55, 20, 330, 325),
    (45, 45, 325, 345),
    (35, 45, 305, 345),
    (45, 45, 290, 345),
    (45, 20, 285, 335),
    (55, 45, 265, 335),
    (70, 25, 280, 275),
    (25, 35, 295, 335),
]


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes((json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))


def _png_chunk(chunk_type: bytes, data: bytes) -> bytes:
    checksum = binascii.crc32(chunk_type + data) & 0xFFFFFFFF
    return struct.pack(">I", len(data)) + chunk_type + data + struct.pack(">I", checksum)


def _stored_zlib(data: bytes) -> bytes:
    """Encode a deterministic RFC 1950 stream using uncompressed DEFLATE blocks."""
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
    """Write canonical RGBA PNG bytes independent of Pillow/zlib platform builds."""
    rgba = image.convert("RGBA")
    raw = bytearray()
    pixels = rgba.tobytes()
    stride = rgba.width * 4
    for y in range(rgba.height):
        raw.append(0)  # PNG filter type None.
        raw.extend(pixels[y * stride : (y + 1) * stride])
    ihdr = struct.pack(">IIBBBBB", rgba.width, rgba.height, 8, 6, 0, 0, 0)
    encoded = (
        b"\x89PNG\r\n\x1a\n"
        + _png_chunk(b"IHDR", ihdr)
        + _png_chunk(b"IDAT", _stored_zlib(bytes(raw)))
        + _png_chunk(b"IEND", b"")
    )
    path.write_bytes(encoded)


def split_grid(image: Image.Image, columns: int, rows: int) -> list[Image.Image]:
    width, height = image.size
    xs = [round(index * width / columns) for index in range(columns + 1)]
    ys = [round(index * height / rows) for index in range(rows + 1)]
    return [
        image.crop((xs[column], ys[row], xs[column + 1], ys[row + 1]))
        for row in range(rows)
        for column in range(columns)
    ]


def render_source_direct_ui_subject(
    source: Image.Image,
    size: tuple[int, int],
    *,
    max_subject: tuple[int, int],
    bottom: int,
    colors: int,
) -> Image.Image:
    """Render a UI surface directly from accepted high-resolution actor art.

    UI portraits must never enlarge the already reduced 36-40px battle atlas.
    This helper keeps one uniform x/y scale, then gives compact and grid assets
    explicit transparent safety margins for their real runtime geometries.
    """

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
        raise ValueError(
            f"UI subject {subject.size} does not fit {size} with bottom={bottom}"
        )
    output.alpha_composite(subject, (x, y))
    return output


def source_direct_actor_cell(
    source_path: Path,
    *,
    columns: int,
    rows: int,
    index: int,
    keep_box: tuple[int, int, int, int] | None,
) -> Image.Image:
    source = Image.open(source_path).convert("RGBA")
    cell = hard_alpha(split_grid(source, columns, rows)[index])
    if keep_box is not None:
        masked = Image.new("RGBA", cell.size, (0, 0, 0, 0))
        masked.alpha_composite(cell.crop(keep_box), (keep_box[0], keep_box[1]))
        cell = masked
    return cell.crop(alpha_bbox(cell))


def build_source_direct_portrait_set(
    champion_id: str,
    full_body: Image.Image,
    *,
    compact_focus: tuple[float, float, float, float],
    scoreboard_focus: tuple[float, float, float, float] | None = None,
) -> list[Path]:
    """Build encyclopedia, compact-row, and BP-grid art as separate assets."""

    CHAMPION_FULLBODY_DIR.mkdir(parents=True, exist_ok=True)
    CHAMPION_PORTRAIT_DIR.mkdir(parents=True, exist_ok=True)
    full_body = hard_alpha(full_body).crop(alpha_bbox(hard_alpha(full_body)))

    encyclopedia = render_source_direct_ui_subject(
        full_body,
        (64, 64),
        max_subject=(54, 58),
        bottom=60,
        colors=128,
    )
    encyclopedia_path = CHAMPION_FULLBODY_DIR / f"{champion_id}.png"
    save_png(encyclopedia_path, encyclopedia)

    width, height = full_body.size
    left, top, right, bottom = compact_focus
    focus = full_body.crop(
        (
            round(width * left),
            round(height * top),
            round(width * right),
            round(height * bottom),
        )
    )
    compact = render_source_direct_ui_subject(
        focus,
        (64, 64),
        max_subject=(50, 50),
        bottom=58,
        colors=128,
    )
    compact_path = CHAMPION_PORTRAIT_DIR / f"{champion_id}_compact.png"
    save_png(compact_path, compact)

    scoreboard_focus = scoreboard_focus or compact_focus
    left, top, right, bottom = scoreboard_focus
    scoreboard_source = full_body.crop(
        (
            round(width * left),
            round(height * top),
            round(width * right),
            round(height * bottom),
        )
    )
    scoreboard = render_source_direct_ui_subject(
        scoreboard_source,
        (64, 64),
        max_subject=(50, 50),
        bottom=58,
        colors=128,
    )
    scoreboard_path = CHAMPION_PORTRAIT_DIR / f"{champion_id}_scoreboard.png"
    save_png(scoreboard_path, scoreboard)

    # The reusable 90x122 BP surface reserves y=86..121 for its name/icon
    # band. Ending visible pixels at y<=86 leaves ten clear pixels before the
    # native y=96 label boundary and prevents feet/weapons touching the name.
    grid = render_source_direct_ui_subject(
        full_body,
        (90, 122),
        max_subject=(72, 82),
        bottom=86,
        colors=128,
    )
    grid_path = CHAMPION_PORTRAIT_DIR / f"{champion_id}_grid.png"
    save_png(grid_path, grid)
    return [encyclopedia_path, compact_path, scoreboard_path, grid_path]


def build_champion_fullbody_portraits() -> list[Path]:
    """Export per-surface portraits without upscaling packed battle pixels."""
    CHAMPION_FULLBODY_DIR.mkdir(parents=True, exist_ok=True)
    outputs: list[Path] = []
    for champion_id, sheet_path in CHAMPION_FULLBODY_SHEETS.items():
        # Kled, Xayah and Yone retain tight native atlas geometry whose first idle
        # frame is not the sheet's top-left 64x64 cell. Their dedicated
        # builders export portraits from each exact native idle rectangle.
        if champion_id in {"cavalry_knight", "dancer", "dual_blader"}:
            continue
        if champion_id == "lol_shen":
            source = source_direct_actor_cell(
                ACTOR_SOURCE,
                columns=4,
                rows=3,
                index=0,
                keep_box=ACTOR_KEEP_BOXES[0],
            )
            outputs.extend(
                build_source_direct_portrait_set(
                    champion_id,
                    source,
                    # Drop the detached spirit blade and keep helmet,
                    # shoulders, eyeslit and upper torso in compact rows.
                    compact_focus=(0.25, 0.0, 1.0, 0.60),
                    scoreboard_focus=(0.28, 0.0, 0.98, 0.48),
                )
            )
            continue
        if champion_id == "archer":
            source = source_direct_actor_cell(
                LUCIAN_ACTOR_SOURCE,
                columns=4,
                rows=3,
                index=0,
                keep_box=LUCIAN_ACTOR_KEEP_BOXES[0],
            )
            outputs.extend(
                build_source_direct_portrait_set(
                    champion_id,
                    source,
                    # Preserve hair, both eyes, shoulders and coat collar;
                    # omit lower legs that made 18px rows unreadably tiny.
                    compact_focus=(0.04, 0.0, 0.96, 0.60),
                    scoreboard_focus=(0.08, 0.0, 0.92, 0.48),
                )
            )
            continue
        if champion_id == "barrier_magician":
            source = source_direct_actor_cell(
                ORIANNA_ACTOR_SOURCE,
                columns=4,
                rows=4,
                index=0,
                keep_box=None,
            )
            outputs.extend(
                build_source_direct_portrait_set(
                    champion_id,
                    source,
                    # Sidebar/HUD keeps face, crown, shoulders and enough
                    # clockwork torso to remain recognizably Orianna.
                    compact_focus=(0.0, 0.0, 1.0, 0.65),
                    # The 18/26/34px report and scoreboard rows need a tighter
                    # porcelain-face crop than the 46px side list.
                    scoreboard_focus=(0.08, 0.0, 0.92, 0.52),
                )
            )
            continue
        if champion_id == "berserker":
            source = source_direct_actor_cell(
                BRIAR_ACTOR_SOURCE,
                columns=4,
                rows=4,
                index=0,
                keep_box=None,
            )
            outputs.extend(
                build_source_direct_portrait_set(
                    champion_id,
                    source,
                    # Preserve white hair, red eyes, shoulders and pillory in
                    # the larger battle-side list without shrinking to feet.
                    compact_focus=(0.0, 0.0, 1.0, 0.68),
                    # Scoreboard rows prioritize both eyes and the red crystal.
                    scoreboard_focus=(0.03, 0.0, 0.97, 0.52),
                )
            )
            continue
        if champion_id == "boomerang_hunter":
            # Sivir's accepted source is a hand-spaced 1254x1254 contact
            # sheet rather than an evenly divided grid.  Pull the complete
            # first idle pose directly from its source keep-box so none of the
            # UI surfaces ever enlarge the reduced battle atlas.
            source = hard_alpha(Image.open(SIVIR_ACTOR_SOURCE).convert("RGBA"))
            source = keep_alpha_components(
                source.crop(SIVIR_ACTOR_KEEP_BOXES[0]), 200
            )
            source = source.crop(alpha_bbox(source))
            outputs.extend(
                build_source_direct_portrait_set(
                    champion_id,
                    source,
                    # The side list keeps the face, circlet, shoulders and
                    # crossed blade.  The first source pose looks to screen
                    # right, so the tiny scoreboard must keep the complete
                    # right edge of the head instead of cutting through the
                    # second eye/cheek at 18-34px rendering.
                    compact_focus=(0.14, 0.0, 0.92, 0.73),
                    scoreboard_focus=(0.42, 0.0, 1.0, 0.53),
                )
            )
            continue
        with Image.open(sheet_path) as opened:
            sheet = opened.convert("RGBA")
            if sheet.width < 64 or sheet.height < 64:
                raise ValueError(f"Champion sheet is smaller than one 64px frame: {sheet_path}")
            idle_frame = sheet.crop((0, 0, 64, 64))
            subject = idle_frame.crop(alpha_bbox(idle_frame))
            scale = min(54 / subject.width, 58 / subject.height)
            subject = subject.resize(
                (max(1, round(subject.width * scale)), max(1, round(subject.height * scale))),
                Image.Resampling.NEAREST,
            )
            portrait = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
            portrait.alpha_composite(subject, ((64 - subject.width) // 2, 62 - subject.height))
        output = CHAMPION_FULLBODY_DIR / f"{champion_id}.png"
        save_png(output, portrait)
        outputs.append(output)
    return outputs


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
    image = hard_alpha(image)
    quantized = image.quantize(colors=colors, method=Image.Quantize.FASTOCTREE).convert("RGBA")
    quantized.putalpha(image.getchannel("A"))
    return hard_alpha(quantized, 128)


def alpha_bbox(image: Image.Image) -> tuple[int, int, int, int]:
    bbox = image.getchannel("A").point(lambda value: 255 if value >= 64 else 0).getbbox()
    if bbox is None:
        raise ValueError("Generated cell has no visible pixels")
    return bbox


def keep_largest_alpha_component(image: Image.Image) -> Image.Image:
    """Remove detached image-gen particles without repainting actor pixels."""
    rgba = hard_alpha(image)
    alpha = rgba.getchannel("A")
    remaining = {
        (x, y)
        for y in range(rgba.height)
        for x in range(rgba.width)
        if alpha.getpixel((x, y)) >= 128
    }
    largest: set[tuple[int, int]] = set()
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
        if len(component) > len(largest):
            largest = component

    cleaned = Image.new("RGBA", rgba.size, (0, 0, 0, 0))
    source_pixels = rgba.load()
    output_pixels = cleaned.load()
    for x, y in largest:
        output_pixels[x, y] = source_pixels[x, y]
    return cleaned


def keep_alpha_components(image: Image.Image, min_pixels: int) -> Image.Image:
    """Keep intentional actor/weapon components while dropping tiny particles."""

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

    cleaned = Image.new("RGBA", rgba.size, (0, 0, 0, 0))
    source_pixels = rgba.load()
    output_pixels = cleaned.load()
    for x, y in kept:
        output_pixels[x, y] = source_pixels[x, y]
    return cleaned


def fit_cell(
    cell: Image.Image,
    frame_size: tuple[int, int],
    max_visible: tuple[int, int],
    *,
    bottom_anchor: bool = False,
) -> Image.Image:
    cell = hard_alpha(cell)
    subject = cell.crop(alpha_bbox(cell))
    scale = min(max_visible[0] / subject.width, max_visible[1] / subject.height)
    resized = subject.resize(
        (max(1, round(subject.width * scale)), max(1, round(subject.height * scale))),
        Image.Resampling.LANCZOS,
    )
    resized = palette_finish(resized)
    output = Image.new("RGBA", frame_size, (0, 0, 0, 0))
    x = (frame_size[0] - resized.width) // 2
    y = frame_size[1] - resized.height - 2 if bottom_anchor else (frame_size[1] - resized.height) // 2
    output.alpha_composite(resized, (x, y))
    return output


def pack_stable_actor_pose(
    subject: Image.Image,
    *,
    target_height: int,
    max_visible: tuple[int, int],
    foot_baseline: int,
    palette_colors: int = 96,
) -> Image.Image:
    """Pack one live actor pose with a stable visible-height contract.

    The earlier battle-only resize used one source-space multiplier. That keeps
    geometry proportional, but it does not keep generated poses in one runtime
    scale class: crouch/cast cells with a shorter source bbox became visibly
    15-25% smaller in the 64x64 atlas. This helper normalizes the authored pose
    height, preserves x/y aspect ratio, applies the champion footprint cap, and
    keeps the same exclusive foot anchor. Death/fade and weapon-only frames stay
    on their dedicated paths.
    """

    scale = min(
        target_height / subject.height,
        max_visible[0] / subject.width,
        max_visible[1] / subject.height,
    )
    resized = subject.resize(
        (max(1, round(subject.width * scale)), max(1, round(subject.height * scale))),
        Image.Resampling.LANCZOS,
    )
    resized = palette_finish(resized, palette_colors)
    frame = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    frame.alpha_composite(
        resized,
        ((64 - resized.width) // 2, foot_baseline - resized.height),
    )
    return frame


def build_actor() -> tuple[Path, Path, list[Image.Image]]:
    source = Image.open(ACTOR_SOURCE).convert("RGBA")
    cells = split_grid(source, 4, 3)
    base_frames: list[Image.Image] = []
    # The accepted high-resolution source already contains a clean face and
    # silhouette. Normalize every pose to Shen's narrow live-body height band
    # with one aspect-preserving x/y scale. UI surfaces are source-direct and
    # therefore do not constrain the battle actor scale.
    masked_subjects: list[Image.Image] = []
    for cell, keep_box in zip(cells, ACTOR_KEEP_BOXES, strict=True):
        masked = Image.new("RGBA", cell.size, (0, 0, 0, 0))
        kept = cell.crop(keep_box)
        masked.alpha_composite(kept, (keep_box[0], keep_box[1]))
        masked = hard_alpha(masked)
        # Preserve Shen's detached spirit blade (roughly 2k+ source pixels),
        # but discard smaller generated Q/E sparks that otherwise enlarge the
        # crop and shrink only those actor poses during packing.
        masked = keep_alpha_components(masked, 2000)
        masked_subjects.append(masked.crop(alpha_bbox(masked)))
    # Keep standing/cast poses inside a narrow 33-36px band. The final hit pose
    # remains compressed as a recoil, but no longer swaps to a tiny scale class.
    base_pose_heights = (36, 36, 36, 36, 36, 35, 35, 35, 35, 35, 36, 33)
    for subject, target_height in zip(
        masked_subjects, base_pose_heights, strict=True
    ):
        base_frames.append(
            pack_stable_actor_pose(
                subject,
                target_height=target_height,
                max_visible=SHEN_BATTLE_MAX_SIZE,
                foot_baseline=SHEN_BATTLE_FOOT_BASELINE,
            )
        )

    # The original contact sheet only supplied three broad run poses. A second
    # image-gen pass supplies nine unique gait phases so the reduced sprite keeps
    # readable left/right contacts and two real passing (cross-step) silhouettes.
    run_source = Image.open(RUN_SOURCE).convert("RGBA")
    run_frames: list[Image.Image] = []
    for cell in split_grid(run_source, 3, 3):
        cell = hard_alpha(cell)
        cell = keep_alpha_components(cell, 2000)
        subject = cell.crop(alpha_bbox(cell))
        run_frames.append(
            pack_stable_actor_pose(
                subject,
                target_height=SHEN_BATTLE_IDLE_HEIGHT,
                max_visible=SHEN_BATTLE_MAX_SIZE,
                foot_baseline=SHEN_BATTLE_FOOT_BASELINE,
            )
        )

    # Runtime atlas order: two idles, nine generated run phases, then the seven
    # non-run actions from the accepted 4x3 actor source.
    frames = [
        base_frames[0],
        base_frames[1],
        *run_frames,
        *base_frames[5:10],
        # The authored R body cell has a connected ground ring. Shen already
        # owns a separate R VFX sheet, so keep the clean channel pose here.
        base_frames[9],
        base_frames[11],
    ]

    atlas = Image.new("RGBA", (64 * len(frames), 64), (0, 0, 0, 0))
    for index, frame in enumerate(frames):
        atlas.alpha_composite(frame, (index * 64, 0))

    ACTOR_DIR.mkdir(parents=True, exist_ok=True)
    sheet_path = ACTOR_DIR / "shen#sheet.png"
    anim_path = ACTOR_DIR / "shen#anim.fanim"
    save_png(sheet_path, atlas)

    sequences: dict[str, tuple[list[int], list[float]]] = {
        "idle": ([0, 1, 0, 1, 0, 1, 0], [0.12] * 7),
        "run": (list(range(2, 11)), [0.08] * 9),
        "attack": ([11, 12, 12, 13, 0, 0], [0.05, 0.05, 0.05, 0.08, 0.08, 0.09]),
        "skill": ([11, 14, 14, 14, 13, 1, 0], [0.06, 0.07, 0.08, 0.09, 0.10, 0.10, 0.10]),
        "skill2": ([0, 15, 15, 1, 0], [0.08, 0.12, 0.12, 0.09, 0.09]),
        "ult": ([0, 16, 16, 16, 0], [0.12, 0.18, 0.48, 0.22, 0.20]),
        "hit": ([17], [0.12]),
        "dead": ([17], [0.60]),
    }
    anims: dict[str, object] = {}
    for name, (indexes, durations) in sequences.items():
        anims[name] = {
            "frames": [
                {
                    "duration": duration,
                    "data": {"x": index * 64, "y": 0, "w": 64, "h": 64},
                }
                for index, duration in zip(indexes, durations, strict=True)
            ]
        }
    write_json(anim_path, {"anims": anims})
    return sheet_path, anim_path, frames


def build_lucian_actor() -> tuple[Path, Path, list[Image.Image]]:
    """Pack Lucian at his native-like 64x64 scale from actor/run masters."""
    source = Image.open(LUCIAN_ACTOR_SOURCE).convert("RGBA")
    source_cells: list[Image.Image] = []
    for index, (cell, keep_box) in enumerate(
        zip(split_grid(source, 4, 3), LUCIAN_ACTOR_KEEP_BOXES, strict=True)
    ):
        cell = hard_alpha(cell)
        if keep_box is not None:
            masked = Image.new("RGBA", cell.size, (0, 0, 0, 0))
            kept = cell.crop(keep_box)
            masked.alpha_composite(kept, (keep_box[0], keep_box[1]))
            cell = masked
        # Actor flashes and isolated source-edge pixels belong to the dedicated
        # projectile/VFX sheets. They must not influence Lucian's body crop.
        cell = keep_largest_alpha_component(cell)
        source_cells.append(cell)
    source_subjects = [cell.crop(alpha_bbox(cell)) for cell in source_cells]

    # Native Archer idles are about 31-33px high. Keep a small readability
    # allowance for the accepted high-resolution Lucian model, then normalize
    # every combat/run pose to the same narrow live-body height band. Wide gun
    # poses remain aspect-preserving and never get a separate x/y multiplier.
    # The two dash cells came from a shorter source crop and the raised-guns R
    # cell from a taller one. Normalize those authored postures explicitly so
    # E no longer shrinks Lucian and R no longer enlarges him on state entry.
    base_pose_heights = (36, 36, 36, 36, 36, 36, 34, 34, 39, 36, 35, 14)
    base_frames = [
        pack_stable_actor_pose(
            subject,
            target_height=target_height,
            max_visible=LUCIAN_BATTLE_MAX_SIZE,
            foot_baseline=LUCIAN_BATTLE_FOOT_BASELINE,
        )
        for subject, target_height in zip(
            source_subjects, base_pose_heights, strict=True
        )
    ]

    # A dedicated image-gen 3x3 run loop supplies nine distinct alternating
    # contact/passing phases. It uses Shen's height, compact width and foot
    # baseline instead of the rejected horizontal flying/split-stride route.
    run_source = Image.open(LUCIAN_RUN_SOURCE).convert("RGBA")
    run_frames: list[Image.Image] = []
    for cell in split_grid(run_source, 3, 3):
        cell = hard_alpha(cell)
        cell = keep_largest_alpha_component(cell)
        subject = cell.crop(alpha_bbox(cell))
        run_frames.append(
            pack_stable_actor_pose(
                subject,
                target_height=LUCIAN_BATTLE_IDLE_HEIGHT,
                max_visible=LUCIAN_BATTLE_MAX_SIZE,
                foot_baseline=LUCIAN_BATTLE_FOOT_BASELINE,
            )
        )

    # Runtime contract: two idles, nine run phases, then ten actor actions.
    # Q stays a normal 64x64 pose; its direction-aware beam is a projectile
    # binding, so mirroring the actor can no longer put the beam behind him.
    frames = [base_frames[0], base_frames[1], *run_frames, *base_frames[2:12]]
    r_source = Image.open(LUCIAN_VFX_SOURCES["lucian_r"][0]).convert("RGBA")
    r_projectile = fit_cell(split_grid(r_source, 4, 2)[0], (64, 64), (48, 18))
    atlas_frames = [*frames, r_projectile]
    atlas = Image.new("RGBA", (64 * len(atlas_frames), 64), (0, 0, 0, 0))
    for index, frame in enumerate(atlas_frames):
        atlas.alpha_composite(frame, (index * 64, 0))

    ACTOR_DIR.mkdir(parents=True, exist_ok=True)
    sheet_path = ACTOR_DIR / "lucian#sheet.png"
    anim_path = ACTOR_DIR / "lucian#anim.fanim"
    save_png(sheet_path, atlas)

    sequences: dict[str, tuple[list[int], list[float]]] = {
        "idle": ([0, 1, 0, 1, 0, 1, 0], [0.12] * 7),
        "run": (list(range(2, 11)), [0.075] * 9),
        "attack": ([11, 11, 0], [0.10, 0.10, 0.20]),
        "attack_right": ([0, 11, 11, 0], [0.06, 0.08, 0.08, 0.18]),
        "attack_left": ([0, 12, 12, 0], [0.06, 0.08, 0.08, 0.18]),
        "attack_double": ([0, 13, 13, 11, 12, 0], [0.04, 0.06, 0.06, 0.08, 0.08, 0.16]),
        "skill": ([0, 14, 14, 14, 14, 14, 14, 14, 14, 0], [0.04, 0.03, 0.03, 0.04, 0.04, 0.04, 0.04, 0.04, 0.05, 0.08]),
        "skill2": ([15, 16, 16, 16, 1], [0.05, 0.06, 0.07, 0.07, 0.05]),
        "ult": ([17, *([18] * 15), 0], [0.12, *([0.14] * 15), 0.22]),
        # Lucian replaces the native Archer by ID, so engine-owned presentation
        # paths can still request these Archer tags directly.  Missing any one
        # eventually unwraps a nonexistent animation during hidden simulation or
        # Ban/Pick.  Reuse the accepted Lucian poses while preserving the native
        # frame counts and durations exactly.
        "ult_old": (
            [0, 17, 17, 18, 18, 18, 18, 18, 18, 17, 0],
            [0.080000006] * 7 + [0.1] * 4,
        ),
        "ult_pre": ([0, 17, 17], [0.080000006] * 3),
        "ult_loop": ([18, 18, 18, 18], [0.030000001] * 4),
        "ult_end": ([18, 17, 0], [0.080000006] * 3),
        "ult_projectile": ([21], [0.080000006]),
        "old_ult_buff_effect": ([18, 18, 17, 0], [0.1] * 4),
        "skill_attack": ([13, 11, 0], [0.080000006] * 3),
        "skill_dash": ([15, 16, 16], [0.080000006] * 3),
        "old_ult_pre": (
            [0, 17, 17, 18, 18, 18, 18],
            [0.080000006] * 7,
        ),
        "hit": ([19], [0.12]),
        "dead": ([20], [0.60]),
    }
    anims: dict[str, object] = {}
    for name, (indexes, durations) in sequences.items():
        anims[name] = {
            "frames": [
                {
                    "duration": duration,
                    "data": {
                        "x": index * 64,
                        "y": 0,
                        "w": 64,
                        "h": 64,
                    },
                }
                for index, duration in zip(indexes, durations, strict=True)
            ]
        }
    write_json(anim_path, {"anims": anims})
    return sheet_path, anim_path, frames


def build_orianna_actor() -> tuple[Path, Path, list[Image.Image]]:
    """Pack Orianna with the exact native Barrier Magician action contract."""
    source = Image.open(ORIANNA_ACTOR_SOURCE).convert("RGBA")
    # Several attack/hit cells contain opaque two-pixel strips on the top cell
    # edge. They are invisible at source preview size but expand the alpha bbox
    # by ~60px and make only those runtime bodies 20% smaller. Keep the actual
    # connected actor silhouette; Orianna's ball and spell read live in VFX.
    cells = [
        keep_largest_alpha_component(hard_alpha(cell))
        for cell in split_grid(source, 4, 4)
    ]
    subjects = [cell.crop(alpha_bbox(cell)) for cell in cells]

    # Native Barrier Magician idles occupy roughly 32-34px. Keep Orianna in
    # that native-like class while preserving the reviewed y=42 exclusive foot
    # baseline. One scale is derived from all idle poses and kept for every
    # action; compact UI art is sourced independently.
    idle_height = max(subject.height for subject in subjects[:4])
    actor_scale = ORIANNA_BATTLE_IDLE_HEIGHT / idle_height

    def actor_frame(subject: Image.Image, *, target_height: int | None = None) -> Image.Image:
        scale = actor_scale if target_height is None else target_height / subject.height
        scale = min(
            scale,
            ORIANNA_BATTLE_MAX_SIZE[0] / subject.width,
            ORIANNA_BATTLE_MAX_SIZE[1] / subject.height,
        )
        resized = subject.resize(
            (max(1, round(subject.width * scale)), max(1, round(subject.height * scale))),
            Image.Resampling.LANCZOS,
        )
        # Retain the higher palette budget so porcelain shading, cyan eyes and
        # brass joints do not collapse into muddy blocks at native-like scale.
        resized = palette_finish(resized, 96)
        frame = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
        frame.alpha_composite(
            resized,
            ((64 - resized.width) // 2, ORIANNA_BATTLE_FOOT_BASELINE - resized.height),
        )
        return frame

    # Generated attack/hit cells are visibly shorter than the idle model, while
    # the wide second R pose hits the horizontal cap and shrinks the whole body.
    # Normalize every live pose; keep only true death/ground poses on the source
    # scale path. R's large silhouette remains in its separate ring VFX.
    base_pose_heights: tuple[int | None, ...] = (
        36,
        36,
        36,
        36,
        35,
        35,
        34,
        None,
        36,
        36,
        36,
        36,
        36,
        36,
        None,
        None,
    )
    base_frames = [
        actor_frame(subject, target_height=target_height)
        for subject, target_height in zip(subjects, base_pose_heights, strict=True)
    ]
    run_source = Image.open(ORIANNA_RUN_SOURCE).convert("RGBA")
    run_subjects: list[Image.Image] = []
    for cell in split_grid(run_source, 3, 3):
        cleaned = keep_largest_alpha_component(hard_alpha(cell))
        run_subjects.append(cleaned.crop(alpha_bbox(cleaned)))
    run_frames = [
        actor_frame(subject, target_height=ORIANNA_BATTLE_IDLE_HEIGHT)
        for subject in run_subjects
    ]

    def shifted(frame: Image.Image, dx: int, dy: int) -> Image.Image:
        result = Image.new("RGBA", frame.size, (0, 0, 0, 0))
        result.alpha_composite(frame, (dx, dy))
        return result

    def faded(frame: Image.Image, opacity: float) -> Image.Image:
        result = frame.copy()
        result.putalpha(result.getchannel("A").point(lambda value: round(value * opacity)))
        return result

    transparent = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    sequences: dict[str, tuple[list[Image.Image], list[float]]] = {
        "idle": (base_frames[0:4], [0.18, 0.14, 0.14, 0.14]),
        "run": (run_frames[:8], [0.080000006] * 8),
        "attack": (
            [base_frames[4], shifted(base_frames[4], 1, 0), base_frames[5], shifted(base_frames[5], -1, 0), base_frames[0]],
            [0.080000006] * 5,
        ),
        "hit": ([base_frames[6]], [0.1]),
        "dead": (
            [
                base_frames[6],
                base_frames[7],
                base_frames[14],
                shifted(base_frames[14], 0, 1),
                base_frames[15],
                shifted(base_frames[15], 0, 1),
                faded(base_frames[15], 0.72),
                faded(base_frames[15], 0.40),
                transparent,
            ],
            [0.1] * 9,
        ),
        "skill1": (
            [base_frames[8], shifted(base_frames[8], 1, 0), base_frames[9], shifted(base_frames[9], -1, 0), base_frames[0]],
            [0.080000006] * 5,
        ),
        "skill2": (
            [base_frames[10], shifted(base_frames[10], 1, 0), base_frames[11], shifted(base_frames[11], -1, 0), base_frames[0]],
            [0.080000006] * 5,
        ),
        "ult": (
            [
                base_frames[12],
                shifted(base_frames[12], 0, -1),
                base_frames[12],
                shifted(base_frames[12], 0, -1),
            ],
            [0.080000006] * 4,
        ),
    }

    packed_frames: list[Image.Image] = []
    anims: dict[str, object] = {}
    for tag, (frames, durations) in sequences.items():
        start = len(packed_frames)
        packed_frames.extend(frames)
        anims[tag] = {
            "frames": [
                {
                    "duration": duration,
                    "data": {"x": (start + index) * 64, "y": 0, "w": 64, "h": 64},
                }
                for index, duration in enumerate(durations)
            ]
        }

    atlas = Image.new("RGBA", (64 * len(packed_frames), 64), (0, 0, 0, 0))
    for index, frame in enumerate(packed_frames):
        atlas.alpha_composite(frame, (index * 64, 0))

    ACTOR_DIR.mkdir(parents=True, exist_ok=True)
    sheet_path = ACTOR_DIR / "orianna#sheet.png"
    anim_path = ACTOR_DIR / "orianna#anim.fanim"
    save_png(sheet_path, atlas)
    write_json(anim_path, {"anims": anims})
    return sheet_path, anim_path, packed_frames


def build_briar_actor() -> tuple[Path, Path, list[Image.Image]]:
    """Pack Briar while retaining every native Berserker animation tag."""

    actor_cells = [
        # Q/R projectiles and generated bottom-edge fragments are separate from
        # Briar's connected body. Leaving them in the source bbox shrank only E
        # charge and R throw even though the actor used the same nominal scale.
        keep_largest_alpha_component(hard_alpha(cell))
        for cell in split_grid(Image.open(BRIAR_ACTOR_SOURCE).convert("RGBA"), 4, 4)
    ]
    actor_subjects = [cell.crop(alpha_bbox(cell)) for cell in actor_cells]
    idle_height = max(subject.height for subject in actor_subjects[:2])
    # Native Berserker and the accepted Yone/Kled references establish a 38px
    # body class. Reuse Briar's own 38px scale for every source pose; x and y
    # are never resized independently and compact UI art remains source-direct.
    actor_scale = BRIAR_BATTLE_IDLE_HEIGHT / idle_height

    def actor_frame(subject: Image.Image, *, fixed_height: int | None = None) -> Image.Image:
        scale = actor_scale if fixed_height is None else fixed_height / subject.height
        scale = min(
            scale,
            BRIAR_BATTLE_MAX_SIZE[0] / subject.width,
            BRIAR_BATTLE_MAX_SIZE[1] / subject.height,
        )
        resized = subject.resize(
            (max(1, round(subject.width * scale)), max(1, round(subject.height * scale))),
            Image.Resampling.LANCZOS,
        )
        resized = palette_finish(resized, 96)
        frame = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
        frame.alpha_composite(
            resized,
            ((64 - resized.width) // 2, BRIAR_BATTLE_FOOT_BASELINE - resized.height),
        )
        return frame

    # Normalize live upright/lunge poses without touching the genuine fall,
    # grounded and defeated silhouettes. The R chase cell remains a horizontal
    # dive at the shared source scale and is assessed by silhouette area rather
    # than incorrectly stretched to standing height.
    base_pose_heights: tuple[int | None, ...] = (
        38,
        38,
        38,
        37,
        35,
        37,
        37,
        37,
        38,
        36,
        35,
        None,
        36,
        None,
        None,
        None,
    )
    base_frames = [
        actor_frame(subject, fixed_height=target_height)
        for subject, target_height in zip(
            actor_subjects, base_pose_heights, strict=True
        )
    ]

    # The accepted Q-break pose contains a handful of generated yellow/orange
    # pixels outside Briar's body. At runtime those isolated pixels read as a
    # square bracket around the actor. Keep the exact pose and 64x64 frame, but
    # remove only that generated VFX color family; Q's feedback now lives in a
    # separate target-following overhead effect.
    q_break = base_frames[6].copy()
    q_pixels = q_break.load()
    for y in range(q_break.height):
        for x in range(q_break.width):
            red, green, blue, alpha = q_pixels[x, y]
            if (
                alpha
                and red >= 110
                and green >= 55
                and blue <= 80
                and green * 100 >= red * 35
            ):
                q_pixels[x, y] = (0, 0, 0, 0)
    base_frames[6] = q_break
    run_cells = [
        keep_largest_alpha_component(hard_alpha(cell))
        for cell in split_grid(Image.open(BRIAR_RUN_SOURCE).convert("RGBA"), 3, 3)
    ]
    run_frames = [
        actor_frame(
            cell.crop(alpha_bbox(cell)), fixed_height=BRIAR_BATTLE_IDLE_HEIGHT
        )
        for cell in run_cells
    ]

    def faded(frame: Image.Image, opacity: float) -> Image.Image:
        result = frame.copy()
        result.putalpha(result.getchannel("A").point(lambda value: round(value * opacity)))
        return result

    transparent = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    frames = [
        *base_frames,
        *run_frames,
        faded(base_frames[14], 0.58),
        faded(base_frames[14], 0.28),
        transparent,
    ]
    atlas = Image.new("RGBA", (64 * len(frames), 64), (0, 0, 0, 0))
    for index, frame in enumerate(frames):
        atlas.alpha_composite(frame, (index * 64, 0))

    ACTOR_DIR.mkdir(parents=True, exist_ok=True)
    sheet_path = ACTOR_DIR / "briar#sheet.png"
    anim_path = ACTOR_DIR / "briar#anim.fanim"
    save_png(sheet_path, atlas)

    native_sequences: dict[str, tuple[list[int], list[float]]] = {
        "idle": ([0, 1, 0, 1], [0.18, 0.14, 0.14, 0.14]),
        "berserk_idle": ([7, 7, 6, 7], [0.18, 0.14, 0.14, 0.14]),
        "run": (list(range(16, 24)), [0.080000006] * 8),
        "berserk_run": (list(range(17, 25)), [0.080000006] * 8),
        "attack": ([2, 2, 3, 3, 0], [0.080000006] * 5),
        "attack2": ([4, 4, 5, 5, 0], [0.080000006] * 5),
        "berserk_attack": ([2, 3, 4, 5, 7], [0.060000002] * 5),
        "skill1": ([6, 6, 7], [0.080000006] * 3),
        "skill2": ([8, 8, 9, 0], [0.080000006] * 4),
        "skill2_berserk": ([8, 9, 9, 7], [0.080000006] * 4),
        "skill2_effect": ([8, 9, 9, 7], [0.080000006] * 4),
        "skill1_effect_old": ([6, 6, 7, 7, 6, 7, 27], [0.080000006] * 7),
        "ult": ([10, 10, 11, 11, 7], [0.080000006] * 5),
        "berserk_ult": ([10, 10, 11, 11, 7], [0.080000006] * 5),
        "ult_pre": ([10], [0.080000006]),
        "berserk_ult_pre": ([10], [0.080000006]),
        "ult_dash": ([11], [0.080000006]),
        "berserk_ult_dash": ([11], [0.080000006]),
        "ult_attack": ([11, 4, 5], [0.080000006] * 3),
        "berserk_ult_attack": ([11, 4, 5], [0.080000006] * 3),
        "hit": ([12], [0.1]),
        "berserk_hit": ([12], [0.1]),
        "dead": ([12, 13, 13, 14, 14, 14, 25, 26, 26, 27], [0.1] * 10),
        "berserk_dead": (
            [12, 13, 13, 14, 14, 14, 25, 26, 26, 27],
            [0.1] * 10,
        ),
    }
    anims: dict[str, object] = {}
    for tag, (indexes, durations) in native_sequences.items():
        anims[tag] = {
            "frames": [
                {
                    "duration": duration,
                    "data": {"x": index * 64, "y": 0, "w": 64, "h": 64},
                }
                for index, duration in zip(indexes, durations, strict=True)
            ]
        }
    write_json(anim_path, {"anims": anims})
    return sheet_path, anim_path, frames


def build_sivir_actor() -> tuple[Path, Path, list[Image.Image]]:
    """Pack Sivir while preserving the complete native Boomerang Hunter contract."""

    actor_source = hard_alpha(Image.open(SIVIR_ACTOR_SOURCE).convert("RGBA"))
    # The accepted contact sheet is not evenly divisible by four and 12 poses
    # touch nominal grid boundaries. Full-image keep boxes prevent neighboring
    # poses from bleeding into one another. Components below 200 source pixels
    # are generated motion dust; the larger intentional dropped weapons remain.
    if actor_source.size != (1254, 1254):
        raise ValueError(f"Unexpected Sivir actor source size: {actor_source.size}")
    actor_cells = [
        keep_alpha_components(actor_source.crop(box), 200)
        for box in SIVIR_ACTOR_KEEP_BOXES
    ]
    actor_subjects = [cell.crop(alpha_bbox(cell)) for cell in actor_cells]
    # Pose 7 holds the crossblade high above Sivir's head.  Keeping the whole
    # weapon inside the actor texture forced that one R frame to shrink by
    # almost half.  The dedicated R cast sheet already carries the readable
    # ability flourish, so trim only the oversized overhead blade region and
    # preserve Sivir's body at the same scale as every other action.
    r_subject = actor_subjects[7]
    actor_subjects[7] = r_subject.crop((0, 55, r_subject.width, r_subject.height))
    idle_height = max(subject.height for subject in actor_subjects[:2])
    # Native Boomerang Hunter idles occupy 33-35px. A 36px Sivir target keeps
    # the face/crossblade readable without returning to the oversized 44px
    # legacy-HD body. Run poses are independently source-normalized to that same
    # final live-body height.
    actor_scale = SIVIR_BATTLE_IDLE_HEIGHT / idle_height

    def actor_frame(
        subject: Image.Image,
        *,
        target_height: int | None = None,
        source_scale: float | None = None,
    ) -> Image.Image:
        if target_height is not None:
            scale = target_height / subject.height
        elif source_scale is not None:
            scale = source_scale
        else:
            raise ValueError("Sivir actor pose needs target_height or source_scale")
        scale = min(
            scale,
            SIVIR_BATTLE_MAX_SIZE[0] / subject.width,
            SIVIR_BATTLE_MAX_SIZE[1] / subject.height,
        )
        resized = subject.resize(
            (max(1, round(subject.width * scale)), max(1, round(subject.height * scale))),
            Image.Resampling.LANCZOS,
        )
        resized = palette_finish(resized, 96)
        if (
            resized.width > SIVIR_BATTLE_MAX_SIZE[0]
            or resized.height > SIVIR_BATTLE_MAX_SIZE[1]
        ):
            raise ValueError(
                f"Sivir actor subject {resized.size} exceeds the stable 64x64 contract"
            )
        frame = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
        frame.alpha_composite(
            resized,
            ((64 - resized.width) // 2, SIVIR_BATTLE_FOOT_BASELINE - resized.height),
        )
        return frame

    # Normalize every live pose into the same visible class. Horizontal fall,
    # defeated, kneel and seated cells preserve their authored source scale.
    base_pose_heights: tuple[int | None, ...] = (
        36,
        36,
        34,
        34,
        36,
        33,
        35,
        36,
        35,
        35,
        33,
        35,
        None,
        None,
        None,
        None,
    )
    base_frames = [
        actor_frame(
            subject,
            target_height=target_height,
            source_scale=actor_scale if target_height is None else None,
        )
        for subject, target_height in zip(
            actor_subjects, base_pose_heights, strict=True
        )
    ]
    run_cells = [
        keep_largest_alpha_component(hard_alpha(cell))
        for cell in split_grid(Image.open(SIVIR_RUN_SOURCE).convert("RGBA"), 3, 3)
    ]
    run_subjects = [cell.crop(alpha_bbox(cell)) for cell in run_cells]
    # The dedicated run source was authored at mixed crop heights; normalize its
    # eight runtime phases to one visible height while preserving every pose's
    # aspect ratio and the native frame timing.
    run_frames = [
        actor_frame(subject, target_height=SIVIR_BATTLE_IDLE_HEIGHT)
        for subject in run_subjects
    ]

    def faded(frame: Image.Image, opacity: float) -> Image.Image:
        result = frame.copy()
        result.putalpha(result.getchannel("A").point(lambda value: round(value * opacity)))
        return result

    transparent = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    weapon_cell = split_grid(
        Image.open(SIVIR_VFX_SOURCES["sivir_attack"]).convert("RGBA"), 4, 2
    )[2]
    weapon_cell = keep_largest_alpha_component(weapon_cell)
    weapon_small = fit_cell(weapon_cell, (64, 64), (22, 22))
    weapon_big = fit_cell(weapon_cell, (64, 64), (38, 38))
    weapon_ult = fit_cell(weapon_cell, (64, 64), (34, 34))

    # 0..15 actor poses, 16..24 generated run poses, 25..27 death fade,
    # 28..30 weapon-only frames required by the native special tags.
    frames = [
        *base_frames,
        *run_frames,
        faded(base_frames[13], 0.58),
        faded(base_frames[13], 0.28),
        transparent,
        weapon_small,
        weapon_big,
        weapon_ult,
    ]
    atlas = Image.new("RGBA", (64 * len(frames), 64), (0, 0, 0, 0))
    for index, frame in enumerate(frames):
        atlas.alpha_composite(frame, (index * 64, 0))

    ACTOR_DIR.mkdir(parents=True, exist_ok=True)
    sheet_path = ACTOR_DIR / "sivir#sheet.png"
    anim_path = ACTOR_DIR / "sivir#anim.fanim"
    save_png(sheet_path, atlas)

    native_sequences: dict[str, tuple[list[int], list[float]]] = {
        "idle": ([0, 1, 0, 1], [0.18, 0.14, 0.14, 0.14]),
        "big_boomerang": ([29], [0.1]),
        "boomerang": ([28], [0.1]),
        "run": (list(range(16, 24)), [0.080000006] * 8),
        "attack": ([2, 2, 3, 3, 5, 0], [0.060000002] * 6),
        # Pose 5 is the accepted empty-hand follow-through. Reusing it avoids
        # the native double-weapon failure while the custom Q is in flight.
        "idle_no_boomerang": ([5, 5, 5, 5], [0.18, 0.14, 0.14, 0.14]),
        "skill": ([4, 4, 5, 5, 10, 1, 0], [0.060000002] * 7),
        "skill2": ([6, 6, 6, 11, 1, 0, 0], [0.060000002] * 7),
        "ult": ([7, 7, 7, 7, 1, 0], [0.060000002] * 6),
        "hit": ([8], [0.1]),
        "ult_boomerang": ([30], [0.060000002]),
        "dead": ([12, 12, 13, 13, 13, 13, 25, 26, 27], [0.1] * 9),
    }
    anims: dict[str, object] = {}
    for tag, (indexes, durations) in native_sequences.items():
        anims[tag] = {
            "frames": [
                {
                    "duration": duration,
                    "data": {"x": index * 64, "y": 0, "w": 64, "h": 64},
                }
                for index, duration in zip(indexes, durations, strict=True)
            ]
        }
    write_json(anim_path, {"anims": anims})
    return sheet_path, anim_path, frames


def build_icons() -> list[Path]:
    ICON_DIR.mkdir(parents=True, exist_ok=True)
    outputs: list[Path] = []
    for output_name, source_path in ICON_SOURCES.items():
        source = Image.open(source_path).convert("RGBA")
        icon = fit_cell(source, (64, 64), (58, 58))
        output = ICON_DIR / output_name
        save_png(output, icon)
        outputs.append(output)
    return outputs


def build_lucian_icons() -> list[Path]:
    ICON_DIR.mkdir(parents=True, exist_ok=True)
    outputs: list[Path] = []
    for output_name, source_path in LUCIAN_ICON_SOURCES.items():
        source = Image.open(source_path).convert("RGBA")
        # Lucian icons were generated as full-bleed opaque squares.
        icon = palette_finish(source.resize((64, 64), Image.Resampling.LANCZOS), 64)
        output = ICON_DIR / output_name
        save_png(output, icon)
        outputs.append(output)
    return outputs


def build_orianna_icons() -> list[Path]:
    ICON_DIR.mkdir(parents=True, exist_ok=True)
    outputs: list[Path] = []
    for output_name, source_path in ORIANNA_ICON_SOURCES.items():
        source = Image.open(source_path).convert("RGBA")
        icon = fit_cell(source, (64, 64), (58, 58))
        output = ICON_DIR / output_name
        save_png(output, icon)
        outputs.append(output)
    return outputs


def build_briar_icons() -> list[Path]:
    ICON_DIR.mkdir(parents=True, exist_ok=True)
    outputs: list[Path] = []
    for output_name, source_path in BRIAR_ICON_SOURCES.items():
        source = Image.open(source_path).convert("RGBA")
        icon = palette_finish(source.resize((64, 64), Image.Resampling.LANCZOS), 64)
        output = ICON_DIR / output_name
        save_png(output, icon)
        outputs.append(output)
    return outputs


def build_sivir_icons() -> list[Path]:
    ICON_DIR.mkdir(parents=True, exist_ok=True)
    outputs: list[Path] = []
    for output_name, source_path in SIVIR_ICON_SOURCES.items():
        source = Image.open(source_path).convert("RGBA")
        icon = palette_finish(source.resize((64, 64), Image.Resampling.LANCZOS), 64)
        output = ICON_DIR / output_name
        save_png(output, icon)
        outputs.append(output)
    return outputs


def build_archer_skill_icon_atlas(lucian_icons: list[Path]) -> Path:
    """Patch only Archer's five native icon cells in the original 24px atlas."""
    atlas = Image.open(BASE_SKILL_ICON_SOURCE).convert("RGBA")
    q_icon, e_icon, r_icon = [Image.open(path).convert("RGBA") for path in lucian_icons]
    replacements = {
        "archer_0": e_icon,
        "archer_1": q_icon,
        "archer_2": r_icon,
        "archer_3": q_icon,
        "archer_4": r_icon,
    }
    for key, icon in replacements.items():
        box = ARCHER_SKILL_ICON_BOXES[key]
        resized = icon.resize((box[2] - box[0], box[3] - box[1]), Image.Resampling.LANCZOS)
        atlas.alpha_composite(resized, (box[0], box[1]))
    UI_ASEPRITE_DIR.mkdir(parents=True, exist_ok=True)
    output = UI_ASEPRITE_DIR / "skill_icon#sheet.png"
    save_png(output, atlas)
    return output


def build_archer_override() -> Path:
    """Replace native champion 002 while preserving the complete required base sheet."""
    payload = json.loads(BASE_CHAMPION_INFO_SOURCE.read_text(encoding="utf-8"))
    payload["archer"] = {
            "stat": {
                "attack": 100,
                "magic_power": 0,
                "hp": 900,
                "defence": 20,
                "magic_resistance": 15,
                "move_speed": 900,
                "hp_regen": 2,
                "stack": 0,
                "crit_chance": 0,
            },
            "growth": {
                "attack": 13,
                "magic_power": 0,
                "hp": 90,
                "defence": 6,
                "magic_resistance": 3,
                "move_speed": 9,
                "hp_regen": 1,
                "stack": 0,
                "crit_chance": 0,
            },
            "attack": {
                "name": "archer_attack",
                "action_name": "attack",
                "attack": 0,
                "attack_ratio": 100,
                "range": 62000,
                "speed": 6500,
                "cooltime": 60,
                "duration": 24,
                "start_timing": 10,
                "cancelable": True,
                "y_offset": 0,
                "can_use_with_move": False,
                "attack_type": "BaseAttack",
            },
            # Native Archer skill is the 002 direction dash followed by a shot.
            # It is the replacement-compatible E + Lightslinger approximation.
            "skill": {
                "attack": 0,
                "attack_ratio": 45,
                "range": 62000,
                "projectile_speed": 6500,
                "move_range": 30000,
                "speed": 3000,
                "cooltime": 420,
                "duration": 18,
                "start_timing": 4,
                "cancelable": False,
            },
            # Native Archer skill2 is a targeted shot. Zero move_range removes
            # its old backstep; the hard-coded brief interrupt is documented.
            "skill2": {
                "attack": 55,
                "attack_ratio": 85,
                "range": 65000,
                "projectile_speed": 15000,
                "move_range": 0,
                "move_tick": 10,
                "cooltime": 300,
                "duration": 24,
                "start_timing": 10,
                "cancelable": True,
            },
            "ult": {
                "name": "archer_ult",
                "attack": 8,
                "attack_ratio": 18,
                "range": 120000,
                "attack_range": 4500,
                "interval": 8,
                "total_shots": 15,
                "speed": 9000,
                "cooltime": 3600,
                "duration": 150,
                "start_timing": 12,
                "cancelable": True,
                "y_offset": 0,
            },
            "category": "Range",
            "tags": ["AD", "Range"],
    }
    path = SETTING_DIR / "champion_info.champion_info_sheet"
    write_json(path, payload)
    return path


def effect_anim(frame_width: int, frame_height: int, indexes: list[int], durations: list[float]) -> dict:
    return {
        "frames": [
            {
                "duration": duration,
                "data": {"x": index * frame_width, "y": 0, "w": frame_width, "h": frame_height},
            }
            for index, duration in zip(indexes, durations, strict=True)
        ]
    }


def build_vfx() -> list[Path]:
    EFFECT_DIR.mkdir(parents=True, exist_ok=True)
    outputs: list[Path] = []
    for name, (source_path, columns, rows, frame_size, max_visible) in VFX_SOURCES.items():
        source = Image.open(source_path).convert("RGBA")
        frames: list[Image.Image] = []
        for index, cell in enumerate(split_grid(source, columns, rows)):
            visible_size = (80, 52) if name == "shen_e" and index >= 3 else max_visible
            frame = fit_cell(cell, frame_size, visible_size)
            if name == "shen_q":
                # Twilight Assault must remain readable against the Rift's
                # dark river and wall tiles.  The generated source contains a
                # few almost-black outline/fade cells; a top-level return can
                # otherwise render only those pixels before disappearing.
                # Keep the source silhouette, but lift every opaque spirit
                # blade pixel into a restrained cyan-blue emissive range.
                pixels = frame.load()
                for y in range(frame.height):
                    for x in range(frame.width):
                        red, green, blue, alpha = pixels[x, y]
                        if alpha == 0:
                            continue
                        energy = max(red, green, blue)
                        pixels[x, y] = (
                            max(red, min(170, round(energy * 0.62))),
                            max(green, min(255, energy + 76)),
                            max(blue, min(255, energy + 112)),
                            alpha,
                        )
            if name == "shen_e" and index < 3:
                # The dash wake is a cast/readability cue, not terrain shadow.
                # Lift the formerly near-black first phase so even the first
                # rendered tick is visibly cyan before the looping wake begins.
                pixels = frame.load()
                for y in range(frame.height):
                    for x in range(frame.width):
                        red, green, blue, alpha = pixels[x, y]
                        if alpha == 0:
                            continue
                        energy = max(red, green, blue)
                        pixels[x, y] = (
                            max(red, min(144, max(28, round(energy * 0.46)))),
                            max(green, min(255, max(150, energy + 110))),
                            max(blue, min(255, max(210, energy + 150))),
                            alpha,
                        )
            if name == "shen_e" and index >= 3:
                # Shadow Dash itself stays cyan-violet, while its target-bound
                # crowd-control read is deliberately red-magenta.  The color
                # separation plus the larger foreground mask makes the full
                # 90-tick taunt unmistakable in a crowded fight.
                pixels = frame.load()
                for y in range(frame.height):
                    for x in range(frame.width):
                        red, green, blue, alpha = pixels[x, y]
                        if alpha == 0:
                            continue
                        if max(red, green, blue) >= 205 and max(red, green, blue) - min(red, green, blue) <= 70:
                            pixels[x, y] = (255, max(155, min(225, green)), 255, alpha)
                            continue
                        energy = max(red, green, blue)
                        pixels[x, y] = (
                            max(red, min(255, energy + 72)),
                            min(112, round(green * 0.38)),
                            max(blue, min(255, round(energy * 0.90))),
                            alpha,
                        )
            frames.append(frame)
        if name == "shen_e":
            # The bottom row is impact/taunt feedback, not a second dash wake.
            # Keep any unusually wide generated spark compact so the collision
            # reads at the target instead of looking like another projectile.
            for index in range(3, len(frames)):
                frame = frames[index]
                bbox = frame.getchannel("A").getbbox()
                if bbox is None:
                    continue
                width = bbox[2] - bbox[0]
                height = bbox[3] - bbox[1]
                if width <= height * 2:
                    continue
                subject = frame.crop(bbox).resize(
                    (height * 2, height), Image.Resampling.LANCZOS
                )
                compact = Image.new("RGBA", frame_size, (0, 0, 0, 0))
                compact.alpha_composite(
                    subject,
                    ((frame_size[0] - subject.width) // 2, bbox[1]),
                )
                frames[index] = compact
        if name == "shen_q":
            # Projectile effects are looked up by name when their first frame
            # is rendered.  The invisible endpoint helper still needs a valid
            # view record, otherwise base 0.5.1 can unwrap a missing view and
            # stall the whole simulation.  Reserve one truly transparent cell
            # instead of relying on an unregistered "no-view" projectile.
            frames.append(Image.new("RGBA", frame_size, (0, 0, 0, 0)))
        atlas = Image.new("RGBA", (frame_size[0] * len(frames), frame_size[1]), (0, 0, 0, 0))
        for index, frame in enumerate(frames):
            atlas.alpha_composite(frame, (index * frame_size[0], 0))
        sheet = EFFECT_DIR / f"{name}#sheet.png"
        anim = EFFECT_DIR / f"{name}#anim.fanim"
        save_png(sheet, atlas)
        if name == "shen_q":
            anims = {
                "anchor": effect_anim(64, 64, [len(frames) - 1], [0.01]),
                # Skip the source's nearly empty opening cell in the moving
                # recall.  Fade-only cells remain reserved for arrival/remove.
                "recall": effect_anim(64, 64, [1, 2, 3, 4, 5, 4, 3, 2], [0.05] * 8),
                "empowered_hit": effect_anim(64, 64, [3, 4, 5, 4], [0.05, 0.06, 0.08, 0.10]),
                "recall_arrival": effect_anim(64, 64, [4, 5, 6, 7], [0.05, 0.06, 0.08, 0.10]),
                "empower_pre": effect_anim(64, 64, [1, 2], [0.06, 0.08]),
                "empower_loop": effect_anim(64, 64, [2, 3, 4, 3], [0.09, 0.09, 0.10, 0.09]),
                "empower_remove": effect_anim(64, 64, [6, 7], [0.06, 0.10]),
            }
        elif name == "shen_e":
            anims = {
                "dash": effect_anim(96, 64, [0, 1, 2], [0.06, 0.06, 0.08]),
                "dash_start": effect_anim(96, 64, [0, 1, 2], [0.05, 0.06, 0.08]),
                "impact": effect_anim(96, 64, [3, 4, 5], [0.06, 0.08, 0.12]),
                "trail_pre": effect_anim(96, 64, [0], [0.04]),
                "trail_loop": effect_anim(96, 64, [1, 2], [0.05, 0.06]),
                "trail_remove": effect_anim(96, 64, [2], [0.08]),
                "taunt_pre": effect_anim(96, 64, [3], [0.05]),
                "taunt_loop": effect_anim(96, 64, [4], [0.08]),
                "taunt_remove": effect_anim(96, 64, [5], [0.12]),
            }
        else:
            anims = {
                "guard": effect_anim(112, 112, [0, 1, 2, 3, 4], [0.08, 0.10, 0.14, 0.22, 0.26]),
                "arrival": effect_anim(112, 112, [4, 5, 6, 7], [0.10, 0.10, 0.12, 0.18]),
            }
        write_json(anim, {"anims": anims})
        outputs.extend([sheet, anim])
    return outputs


def build_lucian_vfx() -> list[Path]:
    EFFECT_DIR.mkdir(parents=True, exist_ok=True)
    outputs: list[Path] = []
    for name, (source_path, columns, rows, frame_size, max_visible) in LUCIAN_VFX_SOURCES.items():
        source = Image.open(source_path).convert("RGBA")
        frames: list[Image.Image] = []
        cells = split_grid(source, columns, rows)
        if name == "lucian_q":
            # Keep the full beam from the first visible tick and never finish
            # on the tiny residual spark that previously looked like a second
            # tracking skill. The 192px projectile canvas uses x=96 as its
            # rotation pivot; placing the beam wholly on the forward half makes
            # its first pixels line up with the pistol muzzle, not Lucian's body.
            cells = [cells[index] for index in (2, 3, 4, 5, 4, 3, 2, 1)]
        for cell in cells:
            cell = hard_alpha(cell)
            subject = cell.crop(alpha_bbox(cell))
            scale = min(max_visible[0] / subject.width, max_visible[1] / subject.height)
            resized = subject.resize(
                (max(1, round(subject.width * scale)), max(1, round(subject.height * scale))),
                Image.Resampling.LANCZOS,
            )
            resized = palette_finish(resized, 48)
            frame = Image.new("RGBA", frame_size, (0, 0, 0, 0))
            if name == "lucian_q":
                x = frame_size[0] // 2 + 8
            else:
                x = (frame_size[0] - resized.width) // 2
            y = (frame_size[1] - resized.height) // 2
            frame.alpha_composite(resized, (x, y))
            frames.append(frame)

        atlas = Image.new(
            "RGBA", (frame_size[0] * len(frames), frame_size[1]), (0, 0, 0, 0)
        )
        for index, frame in enumerate(frames):
            atlas.alpha_composite(frame, (index * frame_size[0], 0))
        sheet = EFFECT_DIR / f"{name}#sheet.png"
        anim = EFFECT_DIR / f"{name}#anim.fanim"
        save_png(sheet, atlas)
        tag = {
            "lucian_attack": "projectile",
            "lucian_q": "projectile",
            "lucian_r": "projectile",
        }[name]
        duration = {
            "lucian_attack": 0.04,
            "lucian_q": 0.012,
            "lucian_r": 0.035,
        }[name]
        write_json(
            anim,
            {"anims": {tag: effect_anim(frame_size[0], frame_size[1], list(range(8)), [duration] * 8)}},
        )
        outputs.extend([sheet, anim])
    return outputs


def build_orianna_vfx() -> list[Path]:
    """Build separate ball, field, shield, and shockwave effect resources."""
    EFFECT_DIR.mkdir(parents=True, exist_ok=True)
    outputs: list[Path] = []

    def write_effect(
        name: str,
        frames: list[Image.Image],
        frame_size: tuple[int, int],
        anims: dict[str, object],
    ) -> None:
        atlas = Image.new(
            "RGBA", (frame_size[0] * len(frames), frame_size[1]), (0, 0, 0, 0)
        )
        for index, frame in enumerate(frames):
            atlas.alpha_composite(frame, (index * frame_size[0], 0))
        sheet = EFFECT_DIR / f"{name}#sheet.png"
        anim = EFFECT_DIR / f"{name}#anim.fanim"
        save_png(sheet, atlas)
        write_json(anim, {"anims": anims})
        outputs.extend([sheet, anim])

    attack_cells = split_grid(
        Image.open(ORIANNA_VFX_SOURCES["orianna_attack"]).convert("RGBA"), 4, 2
    )
    attack_frames = [
        fit_cell(cell, (32, 32), (28, 14)) for cell in attack_cells[:4]
    ] + [fit_cell(cell, (32, 32), (24, 24)) for cell in attack_cells[4:]]
    write_effect(
        "orianna_attack",
        attack_frames,
        (32, 32),
        {
            "projectile": effect_anim(32, 32, list(range(4)), [0.04] * 4),
            "impact": effect_anim(32, 32, list(range(4, 8)), [0.04, 0.06, 0.08, 0.10]),
        },
    )

    q_cells = split_grid(
        Image.open(ORIANNA_VFX_SOURCES["orianna_q"]).convert("RGBA"), 4, 3
    )
    q_ball_frames = [fit_cell(cell, (40, 40), (34, 24)) for cell in q_cells[:4]]
    write_effect(
        "orianna_q_ball",
        q_ball_frames,
        (40, 40),
        {"projectile": effect_anim(40, 40, list(range(4)), [0.06] * 4)},
    )
    q_field_frames = [fit_cell(cell, (112, 64), (64, 54)) for cell in q_cells[4:8]]
    q_field_frames.extend(fit_cell(cell, (112, 64), (104, 44)) for cell in q_cells[8:12])
    write_effect(
        "orianna_q_field",
        q_field_frames,
        (112, 64),
        {
            "impact": effect_anim(112, 64, list(range(4)), [0.08] * 4),
            "field": effect_anim(112, 64, list(range(4, 8)), [0.15] * 4),
        },
    )

    e_cells = split_grid(
        Image.open(ORIANNA_VFX_SOURCES["orianna_e_shield"]).convert("RGBA"), 4, 3
    )
    e_frames = [fit_cell(cell, (80, 80), (38, 26)) for cell in e_cells[:4]]
    e_frames.extend(fit_cell(cell, (80, 80), (72, 72)) for cell in e_cells[4:])
    write_effect(
        "orianna_e_shield",
        e_frames,
        (80, 80),
        {
            "projectile": effect_anim(80, 80, list(range(4)), [0.06] * 4),
            "loop": effect_anim(80, 80, list(range(4, 8)), [0.15] * 4),
            "impact": effect_anim(80, 80, [8, 9], [0.08, 0.12]),
            "break": effect_anim(80, 80, [10, 11], [0.10, 0.14]),
        },
    )

    # Resize whole source cells rather than each visible subject so the eight
    # generated ring phases retain their intended decreasing relative radius.
    r_cells = [
        hard_alpha(cell)
        for cell in split_grid(
            Image.open(ORIANNA_VFX_SOURCES["orianna_r_ring"]).convert("RGBA"), 4, 3
        )
    ]
    r_frames: list[Image.Image] = []
    for cell in r_cells:
        scale = min(150 / cell.width, 150 / cell.height)
        resized = cell.resize(
            (max(1, round(cell.width * scale)), max(1, round(cell.height * scale))),
            Image.Resampling.LANCZOS,
        )
        resized = palette_finish(resized, 64)
        frame = Image.new("RGBA", (160, 160), (0, 0, 0, 0))
        frame.alpha_composite(
            resized, ((160 - resized.width) // 2, (160 - resized.height) // 2)
        )
        r_frames.append(frame)
    write_effect(
        "orianna_r_ring",
        r_frames,
        (160, 160),
        {
            "ring": effect_anim(160, 160, list(range(8)), [0.125] * 8),
            "burst": effect_anim(160, 160, list(range(8, 12)), [0.08, 0.08, 0.12, 0.12]),
        },
    )
    return outputs


def build_briar_vfx() -> list[Path]:
    """Build Briar's curse, Q overhead hit, frenzy, scream, and R VFX."""

    EFFECT_DIR.mkdir(parents=True, exist_ok=True)
    outputs: list[Path] = []

    def write_effect(
        name: str,
        frames: list[Image.Image],
        frame_size: tuple[int, int],
        anims: dict[str, object],
    ) -> None:
        atlas = Image.new(
            "RGBA", (frame_size[0] * len(frames), frame_size[1]), (0, 0, 0, 0)
        )
        for index, frame in enumerate(frames):
            atlas.alpha_composite(frame, (index * frame_size[0], 0))
        sheet = EFFECT_DIR / f"{name}#sheet.png"
        anim = EFFECT_DIR / f"{name}#anim.fanim"
        save_png(sheet, atlas)
        write_json(anim, {"anims": anims})
        outputs.extend([sheet, anim])

    bleed_cells = split_grid(
        Image.open(BRIAR_VFX_SOURCES["briar_bleed"]).convert("RGBA"), 4, 2
    )
    bleed_frames = [fit_cell(cell, (48, 48), (34, 34)) for cell in bleed_cells]
    write_effect(
        "briar_bleed",
        bleed_frames,
        (48, 48),
        {
            "tick": effect_anim(
                48,
                48,
                list(range(8)),
                [0.04, 0.05, 0.06, 0.07, 0.06, 0.06, 0.08, 0.10],
            )
        },
    )

    q_overhead_cells = []
    for cell in split_grid(
        Image.open(BRIAR_VFX_SOURCES["briar_q_overhead"]).convert("RGBA"), 4, 2
    ):
        # The accepted ImageGen contact sheet has white gutters between cells.
        # Remove the per-cell edge band before alpha bounding so no separator
        # can survive as a visible square/line in the runtime effect.
        inset = min(18, (min(cell.size) - 1) // 4)
        q_overhead_cells.append(
            hard_alpha(cell.crop((inset, inset, cell.width - inset, cell.height - inset)))
        )
    q_overhead_subjects = [cell.crop(alpha_bbox(cell)) for cell in q_overhead_cells]
    q_overhead_scale = min(
        30 / max(subject.width for subject in q_overhead_subjects),
        22 / max(subject.height for subject in q_overhead_subjects),
    )
    q_overhead_frames: list[Image.Image] = []
    for subject in q_overhead_subjects:
        resized = subject.resize(
            (
                max(1, round(subject.width * q_overhead_scale)),
                max(1, round(subject.height * q_overhead_scale)),
            ),
            Image.Resampling.LANCZOS,
        )
        resized = palette_finish(resized, 32)
        frame = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
        # The entity-following effect shares the actor's 64x64 screen anchor.
        # Reserve the lower 40 pixels so the sigil stays above the target's
        # hair/health-bar region rather than enclosing the body.
        frame.alpha_composite(
            resized,
            ((64 - resized.width) // 2, 2 + (22 - resized.height) // 2),
        )
        q_overhead_frames.append(frame)
    write_effect(
        "briar_q_overhead",
        q_overhead_frames,
        (64, 64),
        {
            "impact": effect_anim(
                64,
                64,
                list(range(8)),
                [0.04, 0.04, 0.05, 0.05, 0.06, 0.06, 0.07, 0.09],
            )
        },
    )

    frenzy_cells = split_grid(
        Image.open(BRIAR_VFX_SOURCES["briar_frenzy"]).convert("RGBA"), 4, 2
    )
    frenzy_frames: list[Image.Image] = []
    for cell in frenzy_cells:
        cell = hard_alpha(cell)
        subject = cell.crop(alpha_bbox(cell))
        scale = min(88 / subject.width, 84 / subject.height)
        resized = subject.resize(
            (max(1, round(subject.width * scale)), max(1, round(subject.height * scale))),
            Image.Resampling.LANCZOS,
        )
        resized = palette_finish(resized, 48)
        frame = Image.new("RGBA", (96, 96), (0, 0, 0, 0))
        # The first live pass put the ring around Briar's hair and health bar.
        # Grow it mostly downward: the top edge stays stable while the hollow
        # center moves six pixels toward her chest/feet.
        x = (96 - resized.width) // 2
        y = min(96 - resized.height, (96 - resized.height) // 2 + 6)
        frame.alpha_composite(resized, (x, y))
        frenzy_frames.append(frame)
    write_effect(
        "briar_frenzy",
        frenzy_frames,
        (96, 96),
        {
            "pre": effect_anim(96, 96, [0, 1, 2, 3], [0.06, 0.07, 0.08, 0.10]),
            "loop": effect_anim(96, 96, [4, 5], [0.22, 0.22]),
            "remove": effect_anim(96, 96, [6, 7], [0.10, 0.14]),
        },
    )

    scream_cells = split_grid(
        Image.open(BRIAR_VFX_SOURCES["briar_e_scream"]).convert("RGBA"), 4, 2
    )
    scream_frames = [fit_cell(cell, (112, 64), (104, 42)) for cell in scream_cells]
    write_effect(
        "briar_e_scream",
        scream_frames,
        (112, 64),
        {"projectile": effect_anim(112, 64, list(range(8)), [0.04] * 8)},
    )

    r_cells = split_grid(
        Image.open(BRIAR_VFX_SOURCES["briar_r"]).convert("RGBA"), 4, 3
    )
    mark_frames = [fit_cell(cell, (64, 64), (48, 48)) for cell in r_cells[:4]]
    write_effect(
        "briar_r_mark",
        mark_frames,
        (64, 64),
        {"mark": effect_anim(64, 64, list(range(4)), [0.10] * 4)},
    )
    trail_frames = [fit_cell(cell, (96, 48), (88, 30)) for cell in r_cells[4:8]]
    write_effect(
        "briar_r_trail",
        trail_frames,
        (96, 48),
        {"trail": effect_anim(96, 48, list(range(4)), [0.045] * 4)},
    )
    arrival_frames = [fit_cell(cell, (96, 96), (88, 72)) for cell in r_cells[8:12]]
    write_effect(
        "briar_r_arrival",
        arrival_frames,
        (96, 96),
        {"arrival": effect_anim(96, 96, list(range(4)), [0.08, 0.10, 0.12, 0.18])},
    )
    return outputs


def build_sivir_vfx() -> list[Path]:
    """Build separate Sivir attack, Q, E, R-cast, and R-buff effects."""

    EFFECT_DIR.mkdir(parents=True, exist_ok=True)
    outputs: list[Path] = []

    def write_effect(
        name: str,
        frames: list[Image.Image],
        frame_size: tuple[int, int],
        anims: dict[str, object],
    ) -> None:
        atlas = Image.new(
            "RGBA", (frame_size[0] * len(frames), frame_size[1]), (0, 0, 0, 0)
        )
        for index, frame in enumerate(frames):
            atlas.alpha_composite(frame, (index * frame_size[0], 0))
        sheet = EFFECT_DIR / f"{name}#sheet.png"
        anim = EFFECT_DIR / f"{name}#anim.fanim"
        save_png(sheet, atlas)
        write_json(anim, {"anims": anims})
        outputs.extend([sheet, anim])

    def preserve_cell(
        cell: Image.Image,
        frame_size: tuple[int, int],
        resized_cell: tuple[int, int],
    ) -> Image.Image:
        cell = hard_alpha(cell)
        resized = cell.resize(resized_cell, Image.Resampling.LANCZOS)
        resized = palette_finish(resized, 64)
        frame = Image.new("RGBA", frame_size, (0, 0, 0, 0))
        frame.alpha_composite(
            resized,
            ((frame_size[0] - resized.width) // 2, (frame_size[1] - resized.height) // 2),
        )
        return frame

    attack_cells = split_grid(
        Image.open(SIVIR_VFX_SOURCES["sivir_attack"]).convert("RGBA"), 4, 2
    )
    attack_frames = [
        fit_cell(cell, (48, 32), (42, 22)) for cell in attack_cells[:7]
    ] + [fit_cell(attack_cells[7], (48, 32), (18, 18))]
    write_effect(
        "sivir_attack",
        attack_frames,
        (48, 32),
        {
            "projectile": effect_anim(48, 32, list(range(7)), [0.04] * 7),
            "hit": effect_anim(48, 32, [7], [0.12]),
        },
    )

    q_cells = split_grid(
        Image.open(SIVIR_VFX_SOURCES["sivir_q"]).convert("RGBA"), 4, 2
    )
    q_frames = [fit_cell(cell, (64, 48), (58, 40)) for cell in q_cells]
    write_effect(
        "sivir_q",
        q_frames,
        (64, 48),
        {
            # The generated lower row trails to the left (screen-right travel),
            # while the upper row trails to the right for the return trip.
            "out": effect_anim(64, 48, [4, 5, 6, 7], [0.045] * 4),
            "return": effect_anim(64, 48, [0, 1, 2, 3], [0.04] * 4),
        },
    )

    shield_cells = split_grid(
        Image.open(SIVIR_VFX_SOURCES["sivir_e_shield"]).convert("RGBA"), 4, 2
    )
    # Crop each generated phase before fitting it. Preserving the large empty
    # source-cell margin made the old ring too small to surround the actor.
    shield_frames = [fit_cell(cell, (64, 64), (58, 58)) for cell in shield_cells]
    write_effect(
        "sivir_e_shield",
        shield_frames,
        (64, 64),
        {
            "pre": effect_anim(64, 64, [0, 1], [0.08, 0.10]),
            "loop": effect_anim(64, 64, [2, 3, 4, 5], [0.16] * 4),
            "remove": effect_anim(64, 64, [6, 7], [0.10, 0.14]),
        },
    )

    r_cast_cells = split_grid(
        Image.open(SIVIR_VFX_SOURCES["sivir_r_cast"]).convert("RGBA"), 4, 2
    )
    r_cast_frames = [
        preserve_cell(cell, (128, 64), (120, 60)) for cell in r_cast_cells
    ]
    write_effect(
        "sivir_r_cast",
        r_cast_frames,
        (128, 64),
        {
            "pulse": effect_anim(
                128,
                64,
                list(range(8)),
                [0.06, 0.07, 0.08, 0.09, 0.10, 0.10, 0.12, 0.16],
            )
        },
    )

    hunt_cells = split_grid(
        Image.open(SIVIR_VFX_SOURCES["sivir_hunt_buff"]).convert("RGBA"), 4, 2
    )

    def foot_trail_frame(cell: Image.Image) -> Image.Image:
        subject = hard_alpha(cell).crop(alpha_bbox(hard_alpha(cell)))
        scale = min(58 / subject.width, 10 / subject.height)
        resized = subject.resize(
            (max(1, round(subject.width * scale)), max(1, round(subject.height * scale))),
            Image.Resampling.LANCZOS,
        )
        resized = palette_finish(resized, 48)
        frame = Image.new("RGBA", (64, 32), (0, 0, 0, 0))
        frame.alpha_composite(resized, ((64 - resized.width) // 2, 32 - resized.height))
        return frame

    # Keep On The Hunt strictly at the unit's feet. A 64x32 effect frame is
    # center-aligned with the 64x64 actor, so its bottom edge maps to y=48.
    hunt_frames = [foot_trail_frame(cell) for cell in hunt_cells]
    write_effect(
        "sivir_hunt_buff",
        hunt_frames,
        (64, 32),
        {
            "pre": effect_anim(64, 32, [0, 1], [0.08, 0.10]),
            "loop": effect_anim(64, 32, [2, 3, 4, 5], [0.14] * 4),
            "remove": effect_anim(64, 32, [6, 7], [0.10, 0.14]),
        },
    )
    return outputs


def build_sivir_native_silence() -> list[Path]:
    """Create a deterministic silent target for native 005 auto-SFX remaps."""

    sound_dir = MOD_ROOT / "sound" / "sfx"
    sound_dir.mkdir(parents=True, exist_ok=True)
    clip_path = sound_dir / "sivir_native_silence_clip.wav"
    with wave.open(str(clip_path), "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(44100)
        output.writeframes(b"\x00\x00" * 2205)
    info_path = sound_dir / "sivir_native_silence.sound_info"
    write_json(
        info_path,
        {
            "plays": [
                {
                    "delay": 0.0,
                    "clip": "sivir_native_silence_clip",
                    "volume": 1.0,
                }
            ]
        },
    )
    return [info_path, clip_path]


def lucian_lightslinger_buff() -> dict[str, object]:
    return {
        "type": "AddCasterBuff",
        "buff_state": {
            "name": "lol_lucian_lightslinger_ready",
            "duration": {"Time": {"tick": 240}},
        },
    }


def lucian_target_projectile(attack_ratio: int, hit_sfx: str) -> dict[str, object]:
    return {
        "type": "TargetProjectile",
        "speed": 6500,
        "name": "lol_lucian_light_bolt",
        "y_offset": 0,
        "applied_target": "Enemy",
        "applied_effects": [
            {
                "effect": {
                    "type": "Combine",
                    "effects": [
                        {"type": "Attack", "damage": 0, "attack_ratio": attack_ratio},
                        {"type": "TargetSfx", "name": hit_sfx},
                    ],
                },
                "casting_type": "Targeting",
            }
        ],
    }


def lucian_culling_projectile() -> dict[str, object]:
    return {
        "type": "LinearProjectile",
        "penetrate": False,
        "speed": 9000,
        "range": 120000,
        "name": "lol_lucian_culling_shot",
        "shape": {"Circle": {"radius": 4500}},
        "applied_target": "EnemyWithoutTower",
        "applied_effects": [
            {
                "effect": {"type": "Attack", "damage": 8, "attack_ratio": 18},
                "casting_type": "Targeting",
            }
        ],
        "end_effects": [],
    }


def shen_timed_buff(name: str, tick: int, **stats: int) -> dict[str, object]:
    return {
        "name": name,
        "duration": {"Time": {"tick": tick}},
        **stats,
    }


SHEN_Q_MARKERS = tuple(
    f"lol_shen_twilight_assault_charge_{charge}" for charge in (3, 2, 1)
)
SHEN_Q_ANCHOR_NAME = "lol_shen_twilight_assault_blade_anchor"
SHEN_Q_EMPOWERED_WINDOW = "lol_shen_twilight_assault_empowered_window"
SHEN_SHADOW_DASH_DISTANCE = 60000
# Rush.range is the swept collision radius, not the distance travelled.  The
# action's top-level range owns Shadow Dash's travel distance.
SHEN_SHADOW_DASH_COLLISION_RADIUS = 10000
SHEN_SHADOW_DASH_AI_HINT_NATIVE = "lol_shen_shadow_dash_ai_hint_native"
SHEN_SHADOW_DASH_CAST_FLASH = "lol_shen_shadow_dash_cast_flash"


def shen_attack_branch(
    buff_name: str,
) -> dict[str, object]:
    consume_effects: list[dict[str, object]] = [
        {"type": "Attack", "damage": 0, "attack_ratio": 100},
        {"type": "ApAttack", "damage": 20, "attack_ratio": 20},
        {
            "type": "ViewEffect",
            "name": "lol_shen_twilight_assault_empowered_hit",
        },
        {"type": "TargetSfx", "name": "lol_shen_attack_hit"},
        {"type": "RemoveCasterBuff", "name": buff_name},
    ]
    if buff_name == SHEN_Q_MARKERS[-1]:
        # The separate presentation marker survives the first two empowered
        # attacks and disappears with the final charge.
        consume_effects.append(
            {"type": "RemoveCasterBuff", "name": SHEN_Q_EMPOWERED_WINDOW}
        )
    return {
        "type": "Combine",
        "effects": [
            {"type": "Sfx", "name": "lol_shen_attack_cast"},
            {
                "type": "Delayed",
                "tick": 10,
                "effects": consume_effects,
            },
        ],
    }


def build_shen_attack() -> dict[str, object]:
    normal_attack: dict[str, object] = {
        "type": "Combine",
        "effects": [
            {"type": "Sfx", "name": "lol_shen_attack_cast"},
            {
                "type": "Delayed",
                "tick": 10,
                "effects": [
                    {"type": "Attack", "damage": 0, "attack_ratio": 100},
                    {"type": "TargetSfx", "name": "lol_shen_attack_hit"},
                ],
            },
        ],
    }
    branches = list(SHEN_Q_MARKERS)
    effect = normal_attack
    for buff_name in reversed(branches):
        effect = {
            "type": "SwitchByBuff",
            "buff_name": buff_name,
            "effect_buff": shen_attack_branch(buff_name),
            "effect_none": effect,
        }
    return {
        "action_name": "attack",
        "description": "#asset/base/text/champion?description.lol_shen.attack",
        "duration": 24,
        "cooltime": 70,
        "start_timing": 10,
        "cancelable": True,
        "range": 25000,
        "casting_type": "Targeting",
        "casting_target": "Enemy",
        "attack_type": "BaseAttack",
        "effect": effect,
    }


def build_shen_q() -> dict[str, object]:
    return {
        "action_name": "skill",
        "description": "#asset/base/text/champion?description.lol_shen.skill",
        "duration": 28,
        "cooltime": 360,
        "start_timing": 8,
        "cancelable": True,
        "range": 55000,
        "casting_type": "Direction",
        "casting_target": "EnemyChampion",
        "attack_type": "Skill",
        "can_use_with_move": False,
        "effect": {
            "type": "Combine",
            "effects": [
                {"type": "Sfx", "name": "lol_shen_q_cast"},
                {"type": "CasterAnimation", "name": "skill", "tick": 28},
                *(
                    {"type": "RemoveCasterBuff", "name": name}
                    for name in SHEN_Q_MARKERS
                ),
                {"type": "RemoveCasterBuff", "name": SHEN_Q_EMPOWERED_WINDOW},
                {
                    # BackToCaster requires a projectile endpoint.  This
                    # transparent-view, no-damage anchor reaches the selected
                    # direction first; its endpoint then becomes the spirit
                    # blade's one and only visible return origin.
                    "type": "LinearProjectile",
                    "penetrate": False,
                    "speed": 60000,
                    "range": 55000,
                    "name": SHEN_Q_ANCHOR_NAME,
                    "shape": {"Circle": {"radius": 1000}},
                    "applied_target": "EnemyChampion",
                    "applied_effects": [],
                    "end_effects": [
                        {
                            "type": "BackToCasterLinearProjectile",
                            "penetrate": True,
                            "speed": 12000,
                            "range": 130000,
                            "name": "lol_shen_twilight_assault_blade_recall",
                            "shape": {"Circle": {"radius": 7500}},
                            "applied_target": "EnemyChampion",
                            "applied_effects": [],
                            "end_effects": [
                                {
                                    "type": "ViewEffect",
                                    "name": "lol_shen_twilight_assault_recall_arrival",
                                },
                                *(
                                    {
                                        "type": "AddCasterBuff",
                                        "buff_state": shen_timed_buff(name, 480),
                                    }
                                    for name in SHEN_Q_MARKERS
                                ),
                                {
                                    "type": "AddCasterBuff",
                                    "buff_state": shen_timed_buff(
                                        SHEN_Q_EMPOWERED_WINDOW, 480
                                    ),
                                },
                            ],
                        }
                    ],
                },
            ],
        },
    }


def build_shen_e() -> dict[str, object]:
    return {
        "action_name": "skill2",
        "description": "#asset/base/text/champion?description.lol_shen.skill2",
        "duration": 30,
        "cooltime": 720,
        "start_timing": 4,
        "cancelable": False,
        "range": SHEN_SHADOW_DASH_DISTANCE,
        "casting_type": "Direction",
        "casting_target": "EnemyChampion",
        "attack_type": "Skill",
        "can_use_with_move": False,
        "effect": {
            "type": "Combine",
            "effects": [
                {"type": "Sfx", "name": "lol_shen_attack_cast"},
                {"type": "CasterAnimation", "name": "run", "tick": 30},
                {
                    "type": "CasterViewEffect",
                    "name": SHEN_SHADOW_DASH_CAST_FLASH,
                },
                {
                    "type": "AddCasterBuff",
                    "buff_state": shen_timed_buff("lol_shen_shadow_dash_trail_window", 30),
                },
                {
                    # RushEffect does not propagate expected_cc_time from its
                    # collision payload.  Rust registers this no-op effect so
                    # the root Combine exposes Shadow Dash's 90-tick taunt to
                    # the stock AI without applying CC before a real hit.
                    "type": "Native",
                    "effect_ref": SHEN_SHADOW_DASH_AI_HINT_NATIVE,
                },
                {
                    "type": "Rush",
                    "speed": 4000,
                    "move_speed_ratio": 100,
                    "range": SHEN_SHADOW_DASH_COLLISION_RADIUS,
                    "casting_target": "EnemyChampion",
                    "penetrate": True,
                    "applied_effects": [
                        {
                            "casting_type": "Targeting",
                            "effect": {
                                "type": "Combine",
                                "effects": [
                                    {"type": "Attack", "damage": 60, "attack_ratio": 0},
                                    {
                                        "type": "Native",
                                        "effect_ref": "lol_shen_shadow_dash_taunt_native",
                                    },
                                    {
                                        "type": "AddBuff",
                                        "buff_state": shen_timed_buff(
                                            "lol_shen_shadow_dash_taunted", 90
                                        ),
                                    },
                                    {"type": "ViewEffect", "name": "lol_shen_shadow_dash_impact"},
                                    {"type": "TargetSfx", "name": "lol_shen_attack_hit"},
                                ],
                            },
                        }
                    ],
                },
            ],
        },
    }


def build_shen_ult() -> dict[str, object]:
    return {
        "action_name": "ult",
        "description": "#asset/base/text/champion?description.lol_shen.ult",
        "duration": 72,
        "cooltime": 3000,
        "start_timing": 1,
        "range": 960000,
        "casting_type": "Position",
        "casting_target": "AllyNotSelf",
        "attack_type": "Skill",
        "cancelable": False,
        "can_use_with_move": False,
        "effect": {
            "type": "Combine",
            "effects": [
                {"type": "Sfx", "name": "lol_shen_r_cast"},
                {
                    "type": "AddCasterBuff",
                    "buff_state": shen_timed_buff("lol_shen_stand_united_channel", 48),
                },
                {
                    "type": "RangeProjectile",
                    "name": "lol_shen_stand_united_guard",
                    "delay": 1,
                    "apply": 1,
                    "shape": {"Circle": {"radius": 6000}},
                    "applied_target": "AllyNotSelf",
                    "applied_effects": [
                        {
                            "effect": {
                                "type": "Shield",
                                "amount": 900,
                                "attack_ratio": 0,
                                "ap_ratio": 80,
                                "tick": 180,
                            },
                            "casting_type": "Targeting",
                        },
                        {
                            "effect": {
                                "type": "AddBuff",
                                "buff_state": shen_timed_buff(
                                    "lol_shen_stand_united_shield_window", 180
                                ),
                            },
                            "casting_type": "Targeting",
                        },
                        {
                            "effect": {
                                "type": "ViewEffect",
                                "name": "lol_shen_stand_united_guard_visual",
                            },
                            "casting_type": "Targeting",
                        },
                    ],
                    "end_effects": [],
                },
                {
                    "type": "Delayed",
                    "tick": 48,
                    "effects": [
                        {"type": "Teleport"},
                        {"type": "Sfx", "name": "lol_shen_r_arrive"},
                        {
                            "type": "CasterViewEffect",
                            "name": "lol_shen_stand_united_arrival_visual",
                        },
                    ],
                },
            ],
        },
    }


def build_shen_data() -> Path:
    path = MOD_ROOT / "champion" / "lol_shen.data_champion"
    # Construct from an immutable in-code template.  Never read the generated
    # output as the next build's input: that made stale view records and test
    # contamination survive otherwise clean rebuilds.
    champion: dict[str, object] = {
        "id": "lol_shen",
        "category": "Melee",
        "tags": ["Melee", "Tank", "Shield", "CC", "Magic"],
        "sprite": "asset/lol_mod/aseprite_resources/champions/shen",
        "anim_prefix": "",
        "skill_icons": [
            "asset/lol_mod/icons/shen_skill",
            "asset/lol_mod/icons/shen_skill2",
            "asset/lol_mod/icons/shen_ult",
        ],
        "stat": {
            "attack": 75,
            "magic_power": 20,
            "hp": 1100,
            "defence": 40,
            "magic_resistance": 35,
            "move_speed": 1000,
            "hp_regen": 3,
            "stack": 0,
            "crit_chance": 0,
        },
        "growth": {
            "attack": 4,
            "magic_power": 8,
            "hp": 120,
            "defence": 7,
            "magic_resistance": 6,
            "move_speed": 5,
            "hp_regen": 1,
            "stack": 0,
            "crit_chance": 0,
        },
        "attack": build_shen_attack(),
        "skill": build_shen_q(),
        "skill2": build_shen_e(),
        "ult": build_shen_ult(),
        "view_projectiles": [
            {
                "type": "Animated",
                "name": SHEN_Q_ANCHOR_NAME,
                "anim": "asset/lol_mod/aseprite_resources/effects/shen_q",
                "tag": "anchor",
                "z": 0,
                "repeat": True,
            },
            {
                "type": "Animated",
                "name": "lol_shen_twilight_assault_blade_recall",
                "anim": "asset/lol_mod/aseprite_resources/effects/shen_q",
                "tag": "recall",
                "z": 3,
                "repeat": True,
            },
        ],
        "view_effects": [
        {
            "type": "Animation",
            "name": "lol_shen_twilight_assault_empowered_hit",
            "anim": "asset/lol_mod/aseprite_resources/effects/shen_q",
            "tag": "empowered_hit",
            "z": 2,
            "is_follow": True,
        },
        {
            "type": "Animation",
            "name": "lol_shen_twilight_assault_recall_arrival",
            "anim": "asset/lol_mod/aseprite_resources/effects/shen_q",
            "tag": "recall_arrival",
            "z": 2,
            "is_follow": True,
        },
        {
            "type": "Animation",
            "name": SHEN_SHADOW_DASH_CAST_FLASH,
            "anim": "asset/lol_mod/aseprite_resources/effects/shen_e",
            "tag": "dash_start",
            "z": 3,
            "is_follow": True,
        },
        {
            "type": "Animation",
            "name": "lol_shen_shadow_dash_impact",
            "anim": "asset/lol_mod/aseprite_resources/effects/shen_e",
            "tag": "impact",
            "z": 2,
            "is_follow": True,
        },
        {
            "type": "Animation",
            "name": "lol_shen_stand_united_guard_visual",
            "anim": "asset/lol_mod/aseprite_resources/effects/shen_r",
            "tag": "guard",
            "z": 1,
            "is_follow": True,
        },
        {
            "type": "Animation",
            "name": "lol_shen_stand_united_arrival_visual",
            "anim": "asset/lol_mod/aseprite_resources/effects/shen_r",
            "tag": "arrival",
            "z": 1,
            "is_follow": False,
        },
        ],
        "view_buffs": [
        {
            "type": "ThreePhase",
            "name": SHEN_Q_EMPOWERED_WINDOW,
            "anim": "asset/lol_mod/aseprite_resources/effects/shen_q",
            "pre_tag": "empower_pre",
            "loop_tag": "empower_loop",
            "remove_tag": "empower_remove",
            "z": 3,
        },
        {
            "type": "ThreePhase",
            "name": "lol_shen_shadow_dash_trail_window",
            "anim": "asset/lol_mod/aseprite_resources/effects/shen_e",
            "pre_tag": "trail_pre",
            "loop_tag": "trail_loop",
            "remove_tag": "trail_remove",
            "z": 3,
        },
        {
            "type": "ThreePhase",
            "name": "lol_shen_shadow_dash_taunted",
            "anim": "asset/lol_mod/aseprite_resources/effects/shen_e",
            "pre_tag": "taunt_pre",
            "loop_tag": "taunt_loop",
            "remove_tag": "taunt_remove",
            "z": 3,
        },
        ],
    }
    write_json(path, champion)
    return path


def build_lucian_data() -> Path:
    culling_shots = [
        {
            "type": "Delayed",
            "tick": 12 + index * 8,
            "effects": [lucian_culling_projectile()],
        }
        for index in range(15)
    ]
    champion = {
        "id": "archer",
        "category": "Range",
        "tags": ["AD", "Range"],
        "sprite": "asset/lol_mod/aseprite_resources/champions/lucian",
        "anim_prefix": "",
        "skill_icons": [
            "asset/lol_mod/icons/lucian_skill",
            "asset/lol_mod/icons/lucian_skill2",
            "asset/lol_mod/icons/lucian_ult",
        ],
        "stat": {
            "attack": 100,
            "magic_power": 0,
            "hp": 900,
            "defence": 20,
            "magic_resistance": 15,
            "move_speed": 900,
            "hp_regen": 2,
            "stack": 0,
            "crit_chance": 0,
        },
        "growth": {
            "attack": 13,
            "magic_power": 0,
            "hp": 90,
            "defence": 6,
            "magic_resistance": 3,
            "move_speed": 9,
            "hp_regen": 1,
            "stack": 0,
            "crit_chance": 0,
        },
        "attack": {
            "action_name": "attack",
            "description": "#asset/base/text/champion?description.archer.attack",
            "duration": 24,
            "cooltime": 60,
            "start_timing": 10,
            "cancelable": True,
            "range": 62000,
            "casting_type": "Targeting",
            "casting_target": "Enemy",
            "attack_type": "BaseAttack",
            "effect": {
                "type": "SwitchByBuff",
                "buff_name": "lol_lucian_lightslinger_ready",
                "effect_none": {
                    "type": "Combine",
                    "effects": [
                        {"type": "Sfx", "name": "lol_lucian_attack_cast"},
                        {"type": "CasterAnimation", "name": "attack_right", "tick": 18},
                        {
                            "type": "Delayed",
                            "tick": 5,
                            "effects": [
                                lucian_target_projectile(100, "lol_lucian_attack_hit")
                            ],
                        },
                    ],
                },
                "effect_buff": {
                    "type": "Combine",
                    "effects": [
                        {"type": "Sfx", "name": "lol_lucian_passive_cast"},
                        {"type": "CasterAnimation", "name": "attack_double", "tick": 22},
                        {
                            "type": "Delayed",
                            "tick": 4,
                            "effects": [
                                lucian_target_projectile(100, "lol_lucian_attack_hit")
                            ],
                        },
                        {
                            "type": "Delayed",
                            "tick": 10,
                            "effects": [
                                lucian_target_projectile(45, "lol_lucian_passive_hit")
                            ],
                        },
                        {
                            "type": "RemoveCasterBuff",
                            "name": "lol_lucian_lightslinger_ready",
                        },
                    ],
                },
            },
        },
        "skill": {
            "action_name": "skill",
            "description": "#asset/base/text/champion?description.archer.skill",
            "duration": 24,
            "cooltime": 300,
            "start_timing": 10,
            "cancelable": True,
            "range": 65000,
            "casting_type": "Targeting",
            "casting_target": "EnemyWithoutTower",
            "attack_type": "Skill",
            "effect": {
                "type": "Combine",
                "effects": [
                    {"type": "Sfx", "name": "lol_lucian_q_cast"},
                    {
                        "type": "LinearProjectile",
                        "penetrate": True,
                        "speed": 16000,
                        "range": 76000,
                        "name": "lol_lucian_q_piercing_light",
                        "shape": {"Circle": {"radius": 10000}},
                        "applied_target": "EnemyWithoutTower",
                        "applied_effects": [
                            {
                                "effect": {
                                    "type": "Attack",
                                    "damage": 55,
                                    "attack_ratio": 85,
                                },
                                "casting_type": "Targeting",
                            }
                        ],
                        "end_effects": [],
                    },
                    lucian_lightslinger_buff(),
                ],
            },
            "can_use_with_move": False,
        },
        "skill2": {
            "action_name": "skill2",
            "description": "#asset/base/text/champion?description.archer.skill2",
            "duration": 18,
            "cooltime": 420,
            "start_timing": 4,
            "cancelable": False,
            "range": 30000,
            "casting_type": "Direction",
            "casting_target": "AllyOnlySelf",
            "attack_type": "Skill",
            "effect": {
                "type": "Combine",
                "effects": [
                    {"type": "Sfx", "name": "lol_lucian_e_cast"},
                    {"type": "CasterAnimation", "name": "skill2", "tick": 18},
                    {
                        "type": "RushTime",
                        "speed": 3000,
                        "tick": 10,
                        "range": 0,
                        "casting_target": "Enemy",
                        "penetrate": True,
                        "applied_effects": [],
                    },
                    lucian_lightslinger_buff(),
                ],
            },
            "can_use_with_move": False,
        },
        "ult": {
            "action_name": "ult",
            "description": "#asset/base/text/champion?description.archer.ult",
            "duration": 150,
            "cooltime": 3600,
            "start_timing": 12,
            "cancelable": True,
            "range": 120000,
            "casting_type": "Direction",
            "casting_target": "EnemyWithoutTower",
            "attack_type": "Skill",
            "effect": {
                "type": "Combine",
                "effects": [
                    {"type": "Sfx", "name": "lol_lucian_r_cast"},
                    {"type": "CasterAnimation", "name": "ult", "tick": 148},
                    {
                        "type": "Delayed",
                        "tick": 8,
                        "effects": [{"type": "Sfx", "name": "lol_lucian_r_channel"}],
                    },
                    *culling_shots,
                    {
                        "type": "Delayed",
                        "tick": 132,
                        "effects": [lucian_lightslinger_buff()],
                    },
                ],
            },
            "can_use_with_move": False,
        },
        "view_projectiles": [
            {
                "type": "Animated",
                "name": "lol_lucian_light_bolt",
                "anim": "asset/lol_mod/aseprite_resources/effects/lucian_attack",
                "tag": "projectile",
                "z": 2,
                "repeat": True,
            },
            {
                "type": "Animated",
                "name": "lol_lucian_q_piercing_light",
                "anim": "asset/lol_mod/aseprite_resources/effects/lucian_q",
                "tag": "projectile",
                "z": 3,
                "repeat": False,
            },
            {
                "type": "Animated",
                "name": "lol_lucian_culling_shot",
                "anim": "asset/lol_mod/aseprite_resources/effects/lucian_r",
                "tag": "projectile",
                "z": 3,
                "repeat": True,
            },
        ],
        "view_effects": [],
        "view_buffs": [],
    }
    path = MOD_ROOT / "champion" / "archer.data_champion"
    write_json(path, champion)
    return path


def build_orianna_data() -> Path:
    """Replace native Barrier Magician (project 003) with Q/E/R Orianna."""

    def timed_buff(name: str, field: str, value: int) -> dict[str, object]:
        return {
            "type": "AddBuff",
            "buff_state": {
                "name": name,
                "duration": {"Time": {"tick": 40}},
                field: value,
            },
        }

    def level_three_buff(name: str, value: int) -> dict[str, object]:
        return {
            "type": "SwitchByLevel3",
            "effect_start": {"type": "Combine", "effects": []},
            "effect_level3": timed_buff(name, "attack_speed_mult", value),
        }

    champion = {
        "id": "barrier_magician",
        "category": "Magician",
        "tags": ["AP", "Range", "Shield", "CC", "Magic"],
        "sprite": "asset/lol_mod/aseprite_resources/champions/orianna",
        "anim_prefix": "",
        "skill_icons": [
            "asset/lol_mod/icons/orianna_skill",
            "asset/lol_mod/icons/orianna_skill2",
            "asset/lol_mod/icons/orianna_ult",
        ],
        "stat": {
            "attack": 80,
            "magic_power": 30,
            "hp": 900,
            "defence": 20,
            "magic_resistance": 20,
            "move_speed": 1000,
            "hp_regen": 2,
            "stack": 0,
            "crit_chance": 0,
        },
        "growth": {
            "attack": 6,
            "magic_power": 15,
            "hp": 100,
            "defence": 8,
            "magic_resistance": 4,
            "move_speed": 5,
            "hp_regen": 1,
            "stack": 0,
            "crit_chance": 0,
        },
        "attack": {
            "action_name": "attack",
            "description": "#asset/base/text/champion?description.barrier_magician.attack",
            "duration": 30,
            "cooltime": 90,
            "start_timing": 24,
            "cancelable": True,
            "range": 60000,
            "growth_range": 0,
            "casting_type": "Targeting",
            "casting_target": "Enemy",
            "attack_type": "BaseAttack",
            "can_use_with_move": False,
            "effect": {
                "type": "Combine",
                "effects": [
                    {"type": "Sfx", "name": "lol_orianna_attack_cast"},
                    {
                        "type": "TargetProjectile",
                        "speed": 4800,
                        "name": "lol_orianna_attack_dart",
                        "y_offset": 0,
                        "applied_target": "Enemy",
                        "applied_effects": [
                            {
                                "effect": {
                                    "type": "Combine",
                                    "effects": [
                                        {"type": "Attack", "damage": 0, "attack_ratio": 100},
                                        {"type": "ApAttack", "damage": 10, "attack_ratio": 15},
                                        {
                                            "type": "ViewEffect",
                                            "name": "lol_orianna_attack_hit_visual",
                                        },
                                        {
                                            "type": "TargetSfx",
                                            "name": "lol_orianna_attack_hit",
                                        },
                                    ],
                                },
                                "casting_type": "Targeting",
                            }
                        ],
                    },
                ],
            },
        },
        "skill": {
            "action_name": "skill1",
            "description": "#asset/base/text/champion?description.barrier_magician.skill",
            "duration": 30,
            "cooltime": 360,
            "start_timing": 24,
            "cancelable": False,
            "range": 70000,
            "growth_range": 0,
            "casting_type": "Targeting",
            "casting_target": "EnemyChampion",
            "attack_type": "Skill",
            "can_use_with_move": False,
            "effect": {
                "type": "Combine",
                "effects": [
                    {"type": "Sfx", "name": "lol_orianna_q_cast"},
                    {
                        "type": "ParabolicProjectile",
                        "name": "lol_orianna_q_ball",
                        "travel_time": 15,
                        "range": 70000,
                        "shape": {"Circle": {"radius": 26000}},
                        "applied_target": "EnemyWithoutTower",
                        "applied_effects": [
                            {
                                "effect": {
                                    "type": "ApAttack",
                                    "damage": 50,
                                    "attack_ratio": 55,
                                },
                                "casting_type": "Targeting",
                            }
                        ],
                        "end_effects": [
                            {"type": "ViewEffect", "name": "lol_orianna_q_impact"},
                            {"type": "TargetSfx", "name": "lol_orianna_q_hit"},
                            {
                                "type": "RangePeriodProjectile",
                                "name": "lol_orianna_q_field_visual",
                                "tick": 180,
                                "period": 30,
                                "first_delay": 0,
                                "shape": {"Circle": {"radius": 30000}},
                                "applied_target": "AllyChampion",
                                "applied_effects": [
                                    {
                                        "effect": {
                                            "type": "Combine",
                                            "effects": [
                                                timed_buff(
                                                    "lol_orianna_q_ally_move",
                                                    "move_speed_mult",
                                                    18,
                                                ),
                                                level_three_buff(
                                                    "lol_orianna_q_ally_attack_speed", 15
                                                ),
                                            ],
                                        },
                                        "casting_type": "Targeting",
                                    }
                                ],
                                "end_effects": [],
                            },
                            {
                                "type": "RangePeriodProjectile",
                                "name": "lol_orianna_q_field_enemy_logic",
                                "tick": 180,
                                "period": 30,
                                "first_delay": 0,
                                "shape": {"Circle": {"radius": 30000}},
                                "applied_target": "EnemyWithoutTower",
                                "applied_effects": [
                                    {
                                        "effect": {
                                            "type": "Combine",
                                            "effects": [
                                                timed_buff(
                                                    "lol_orianna_q_enemy_move",
                                                    "move_speed_mult",
                                                    -22,
                                                ),
                                                level_three_buff(
                                                    "lol_orianna_q_enemy_attack_speed", -15
                                                ),
                                            ],
                                        },
                                        "casting_type": "Targeting",
                                    }
                                ],
                                "end_effects": [],
                            },
                        ],
                    },
                ],
            },
        },
        "skill2": {
            "action_name": "skill2",
            "description": "#asset/base/text/champion?description.barrier_magician.skill2",
            "duration": 30,
            "cooltime": 480,
            "start_timing": 24,
            "cancelable": False,
            "range": 70000,
            "growth_range": 0,
            "casting_type": "Targeting",
            "casting_target": "AllyChampion",
            "attack_type": "Skill",
            "can_use_with_move": False,
            "effect": {
                "type": "Combine",
                "effects": [
                    {"type": "Sfx", "name": "lol_orianna_e_cast"},
                    {
                        "type": "TargetProjectile",
                        "speed": 6000,
                        "name": "lol_orianna_e_ball",
                        "y_offset": 0,
                        "applied_target": "AllyChampion",
                        "applied_effects": [
                            {
                                "effect": {
                                    "type": "Combine",
                                    "effects": [
                                        {
                                            "type": "Shield",
                                            "amount": 180,
                                            "attack_ratio": 0,
                                            "ap_ratio": 55,
                                            "tick": 180,
                                        },
                                        {
                                            "type": "AddBuff",
                                            "buff_state": {
                                                "name": "lol_orianna_protect",
                                                "duration": "WithShield",
                                                "defence": 12,
                                                "magic_resistance": 12,
                                                "skill_damaged_reduce": 15,
                                                "base_attack_damaged_reduce": 10,
                                            },
                                        },
                                        {"type": "TargetSfx", "name": "lol_orianna_e_hit"},
                                    ],
                                },
                                "casting_type": "Targeting",
                            }
                        ],
                    },
                ],
            },
        },
        "ult": {
            "action_name": "ult",
            "description": "#asset/base/text/champion?description.barrier_magician.ult",
            "duration": 30,
            "cooltime": 3000,
            "start_timing": 24,
            "cancelable": False,
            "range": 75000,
            "growth_range": 0,
            "casting_type": "Targeting",
            "casting_target": "EnemyChampion",
            "attack_type": "Skill",
            "can_use_with_move": False,
            "effect": {
                "type": "Combine",
                "effects": [
                    {"type": "Sfx", "name": "lol_orianna_r_cast"},
                    {
                        "type": "ParabolicProjectile",
                        "name": "lol_orianna_r_core",
                        "travel_time": 1,
                        "range": 75000,
                        "shape": {"Circle": {"radius": 1}},
                        "applied_target": "EnemyChampion",
                        "applied_effects": [],
                        "end_effects": [
                            {
                                "type": "ViewEffect",
                                "name": "lol_orianna_r_ring_visual",
                            },
                            {
                                "type": "ShrinkingBarrier",
                                "name": "lol_orianna_r_ring_logic",
                                "start_radius": 60000,
                                "end_radius": 18000,
                                "shrink_per_tick": 700,
                                "tick": 60,
                                "edge_thickness": 6000,
                                "applied_effects": [
                                    {
                                        "effect": {"type": "Bind", "duration": 8},
                                        "casting_type": "Targeting",
                                    }
                                ],
                            },
                            {
                                "type": "Delayed",
                                "tick": 60,
                                "effects": [
                                    {
                                        "type": "ViewEffect",
                                        "name": "lol_orianna_r_burst_visual",
                                    },
                                    {"type": "TargetSfx", "name": "lol_orianna_r_hit"},
                                    {
                                        "type": "RangeProjectile",
                                        "name": "lol_orianna_r_burst_hitbox",
                                        "delay": 0,
                                        "apply": 1,
                                        "shape": {"Circle": {"radius": 42000}},
                                        "applied_target": "EnemyWithoutTower",
                                        "applied_effects": [
                                            {
                                                "effect": {
                                                    "type": "ApAttack",
                                                    "damage": 130,
                                                    "attack_ratio": 100,
                                                },
                                                "casting_type": "Targeting",
                                            },
                                            {
                                                "effect": {
                                                    "type": "Pull",
                                                    "speed": 3200,
                                                    "tick": 12,
                                                },
                                                "casting_type": "Targeting",
                                            },
                                            {
                                                "effect": {
                                                    "type": "Airborne",
                                                    "duration": 24,
                                                },
                                                "casting_type": "Targeting",
                                            },
                                        ],
                                        "end_effects": [],
                                    },
                                ],
                            },
                        ],
                    },
                ],
            },
        },
        "view_projectiles": [
            {
                "type": "Animated",
                "name": "lol_orianna_attack_dart",
                "anim": "asset/lol_mod/aseprite_resources/effects/orianna_attack",
                "tag": "projectile",
                "z": 2,
                "repeat": True,
            },
            {
                "type": "Animated",
                "name": "lol_orianna_q_ball",
                "anim": "asset/lol_mod/aseprite_resources/effects/orianna_q_ball",
                "tag": "projectile",
                "z": 2,
                "repeat": True,
            },
            {
                "type": "Animated",
                "name": "lol_orianna_q_field_visual",
                "anim": "asset/lol_mod/aseprite_resources/effects/orianna_q_field",
                "tag": "field",
                "z": -1,
                "repeat": True,
            },
            {
                "type": "Animated",
                "name": "lol_orianna_e_ball",
                "anim": "asset/lol_mod/aseprite_resources/effects/orianna_e_shield",
                "tag": "projectile",
                "z": 2,
                "repeat": True,
            },
            {
                "type": "Animated",
                "name": "lol_orianna_r_core",
                "anim": "asset/lol_mod/aseprite_resources/effects/orianna_q_ball",
                "tag": "projectile",
                "z": 2,
                "repeat": True,
            },
        ],
        "view_effects": [
            {
                "type": "Animation",
                "name": "lol_orianna_attack_hit_visual",
                "anim": "asset/lol_mod/aseprite_resources/effects/orianna_attack",
                "tag": "impact",
                "z": 1,
                "is_follow": False,
            },
            {
                "type": "Animation",
                "name": "lol_orianna_q_impact",
                "anim": "asset/lol_mod/aseprite_resources/effects/orianna_q_field",
                "tag": "impact",
                "z": 0,
                "is_follow": False,
            },
            {
                "type": "Animation",
                "name": "lol_orianna_r_ring_visual",
                "anim": "asset/lol_mod/aseprite_resources/effects/orianna_r_ring",
                "tag": "ring",
                "z": -1,
                "is_follow": False,
            },
            {
                "type": "Animation",
                "name": "lol_orianna_r_burst_visual",
                "anim": "asset/lol_mod/aseprite_resources/effects/orianna_r_ring",
                "tag": "burst",
                "z": 1,
                "is_follow": False,
            },
        ],
        "view_buffs": [
            {
                "type": "ThreePhase",
                "name": "lol_orianna_protect",
                "anim": "asset/lol_mod/aseprite_resources/effects/orianna_e_shield",
                "pre_tag": "impact",
                "loop_tag": "loop",
                "remove_tag": "break",
                "z": 1,
            }
        ],
    }
    path = MOD_ROOT / "champion" / "barrier_magician.data_champion"
    write_json(path, champion)
    return path


def build_briar_data() -> Path:
    """Replace native Berserker (project champion 004) with Q/E/R Briar."""

    def crimson_curse() -> dict[str, object]:
        return {
            "type": "Combine",
            "effects": [
                {
                    "type": "AddCasted",
                    "duration": 120,
                    "period": 60,
                    "casted_type": "Bleed",
                    "effects": [
                        {"type": "Attack", "damage": 4, "attack_ratio": 3},
                        {
                            "type": "Heal",
                            "amount": 2,
                            "attack_ratio": 1,
                            "ap_ratio": 0,
                            "heal_type": "Caster",
                        },
                        {"type": "ViewEffect", "name": "lol_briar_bleed_tick_visual"},
                    ],
                },
                {
                    "type": "AddBuff",
                    "buff_state": {
                        "name": "lol_briar_crimson_curse",
                        "duration": {"Time": {"tick": 120}},
                    },
                },
            ],
        }

    def caster_buff(name: str, tick: int, **stats: int) -> dict[str, object]:
        return {
            "type": "AddCasterBuff",
            "buff_state": {
                "name": name,
                "duration": {"Time": {"tick": tick}},
                **stats,
            },
        }

    snack_buff_180 = caster_buff("lol_briar_snack_ready", 180)
    snack_buff_240 = caster_buff("lol_briar_snack_ready", 240)
    base_frenzy = caster_buff(
        "lol_briar_blood_frenzy",
        180,
        attack_speed_mult=60,
        move_speed_mult=18,
        vamp=25,
    )
    certain_death_frenzy = caster_buff(
        "lol_briar_certain_death_frenzy",
        240,
        attack_speed_mult=50,
        move_speed_mult=25,
        vamp=30,
        defence=20,
        magic_resistance=20,
        toughness=20,
    )

    champion = {
        "id": "berserker",
        "category": "Melee",
        "tags": ["AD", "Melee", "Heal", "Dot", "CC"],
        "sprite": "asset/lol_mod/aseprite_resources/champions/briar",
        "anim_prefix": "",
        "skill_icons": [
            "asset/lol_mod/icons/briar_skill",
            "asset/lol_mod/icons/briar_skill2",
            "asset/lol_mod/icons/briar_ult",
        ],
        "stat": {
            "attack": 115,
            "magic_power": 0,
            "hp": 950,
            "defence": 25,
            "magic_resistance": 18,
            "move_speed": 1100,
            "hp_regen": 0,
            "stack": 0,
            "crit_chance": 0,
        },
        "growth": {
            "attack": 20,
            "magic_power": 0,
            "hp": 100,
            "defence": 7,
            "magic_resistance": 4,
            "move_speed": 10,
            "hp_regen": 0,
            "stack": 0,
            "crit_chance": 0,
        },
        "attack": {
            "action_name": "attack",
            "description": "#asset/base/text/champion?description.berserker.attack",
            "duration": 24,
            "cooltime": 50,
            "start_timing": 12,
            "cancelable": True,
            "range": 25000,
            "growth_range": 0,
            "casting_type": "Targeting",
            "casting_target": "Enemy",
            "attack_type": "BaseAttack",
            "can_use_with_move": False,
            "effect": {
                "type": "SwitchByBuff",
                "buff_name": "lol_briar_snack_ready",
                "effect_none": {
                    "type": "Combine",
                    "effects": [
                        {"type": "Sfx", "name": "lol_briar_attack_cast"},
                        {"type": "Attack", "damage": 0, "attack_ratio": 100},
                        crimson_curse(),
                        {"type": "TargetSfx", "name": "lol_briar_attack_hit"},
                    ],
                },
                "effect_buff": {
                    "type": "Combine",
                    "effects": [
                        {"type": "Sfx", "name": "lol_briar_frenzy_cast"},
                        {"type": "CasterAnimation", "name": "attack2", "tick": 24},
                        {"type": "Attack", "damage": 0, "attack_ratio": 100},
                        {
                            "type": "Attack",
                            "damage": 25,
                            "attack_ratio": 40,
                            "target_hp_ratio": 2,
                        },
                        {
                            "type": "Heal",
                            "amount": 40,
                            "attack_ratio": 15,
                            "ap_ratio": 0,
                            "heal_type": "Caster",
                        },
                        crimson_curse(),
                        {"type": "TargetSfx", "name": "lol_briar_frenzy_hit"},
                        {"type": "RemoveCasterBuff", "name": "lol_briar_snack_ready"},
                    ],
                },
            },
        },
        "skill": {
            "action_name": "skill1",
            "description": "#asset/base/text/champion?description.berserker.skill",
            "duration": 20,
            "cooltime": 360,
            "start_timing": 8,
            "cancelable": False,
            "range": 45000,
            "growth_range": 0,
            "casting_type": "Targeting",
            "casting_target": "EnemyChampion",
            "attack_type": "Skill",
            "can_use_with_move": False,
            "effect": {
                "type": "Combine",
                "effects": [
                    {"type": "Sfx", "name": "lol_briar_q_cast"},
                    {"type": "CasterAnimation", "name": "skill1", "tick": 20},
                    {
                        "type": "ViewEffect",
                        "name": "lol_briar_q_overhead_visual",
                    },
                    {
                        "type": "SwitchByBuff",
                        "buff_name": "lol_briar_certain_death_frenzy",
                        "effect_none": {
                            "type": "Combine",
                            "effects": [
                                {
                                    "type": "RemoveCasterBuff",
                                    "name": "lol_briar_blood_frenzy",
                                },
                                {
                                    "type": "RemoveCasterBuff",
                                    "name": "lol_briar_snack_ready",
                                },
                                base_frenzy,
                                snack_buff_180,
                            ],
                        },
                        "effect_buff": {
                            "type": "Combine",
                            "effects": [
                                {
                                    "type": "RemoveCasterBuff",
                                    "name": "lol_briar_snack_ready",
                                },
                                snack_buff_180,
                            ],
                        },
                    },
                ],
            },
        },
        "skill2": {
            "action_name": "skill2",
            "description": "#asset/base/text/champion?description.berserker.skill2",
            "duration": 54,
            "cooltime": 480,
            "start_timing": 1,
            "cancelable": False,
            "range": 50000,
            "growth_range": 0,
            "casting_type": "Direction",
            "casting_target": "EnemyWithoutTower",
            "attack_type": "Skill",
            "can_use_with_move": False,
            "effect": {
                "type": "Combine",
                "effects": [
                    {"type": "CasterAnimation", "name": "skill2", "tick": 54},
                    caster_buff(
                        "lol_briar_chilling_scream_guard", 30, damaged_reduce=35
                    ),
                    {
                        "type": "Heal",
                        "amount": 50,
                        "attack_ratio": 15,
                        "ap_ratio": 0,
                        "heal_type": "Caster",
                    },
                    {
                        "type": "Delayed",
                        "tick": 30,
                        "effects": [
                            {"type": "Sfx", "name": "lol_briar_e_cast"},
                            {
                                "type": "LinearProjectile",
                                "penetrate": True,
                                "speed": 12000,
                                "range": 50000,
                                "name": "lol_briar_e_scream_projectile",
                                "shape": {"Circle": {"radius": 12000}},
                                "applied_target": "EnemyWithoutTower",
                                "applied_effects": [],
                                "end_effects": [],
                            },
                            {
                                "type": "LineRangeProjectile",
                                "width": 24000,
                                "length": 50000,
                                "delay": 0,
                                "apply": 1,
                                "name": "lol_briar_e_hitbox",
                                "applied_target": "EnemyWithoutTower",
                                "applied_effects": [
                                    {
                                        "effect": {
                                            "type": "Combine",
                                            "effects": [
                                                {
                                                    "type": "Attack",
                                                    "damage": 75,
                                                    "attack_ratio": 100,
                                                },
                                                crimson_curse(),
                                                {
                                                    "type": "Knockback",
                                                    "speed": 3000,
                                                    "tick": 12,
                                                },
                                                {"type": "Airborne", "duration": 18},
                                                {
                                                    "type": "TargetSfx",
                                                    "name": "lol_briar_e_hit",
                                                },
                                            ],
                                        },
                                        "casting_type": "Targeting",
                                    }
                                ],
                            },
                        ],
                    },
                ],
            },
        },
        "ult": {
            "action_name": "ult",
            "description": "#asset/base/text/champion?description.berserker.ult",
            "duration": 48,
            "cooltime": 3600,
            "start_timing": 1,
            "cancelable": False,
            "range": 80000,
            "growth_range": 0,
            "casting_type": "Targeting",
            "casting_target": "EnemyChampion",
            "attack_type": "Skill",
            "can_use_with_move": False,
            "effect": {
                "type": "Combine",
                "effects": [
                    {"type": "Sfx", "name": "lol_briar_r_cast"},
                    {"type": "ViewEffect", "name": "lol_briar_r_mark_visual"},
                    {"type": "CasterAnimation", "name": "ult_pre", "tick": 18},
                    {
                        "type": "Delayed",
                        "tick": 18,
                        "effects": [
                            {"type": "CasterAnimation", "name": "ult_dash", "tick": 30},
                            {
                                "type": "CasterViewEffect",
                                "name": "lol_briar_r_trail_visual",
                            },
                            {
                                "type": "MoveToTarget",
                                "speed": 6000,
                                "range": 80000,
                                "end_effects": [
                                    {
                                        "type": "CasterAnimation",
                                        "name": "ult_attack",
                                        "tick": 24,
                                    },
                                    {"type": "Sfx", "name": "lol_briar_r_hit"},
                                    {
                                        "type": "ViewEffect",
                                        "name": "lol_briar_r_arrival_visual",
                                    },
                                    {"type": "Attack", "damage": 100, "attack_ratio": 120},
                                    crimson_curse(),
                                    {
                                        "type": "RangeEffect",
                                        "shape": {"Circle": {"radius": 30000}},
                                        "target": "EnemyChampion",
                                        "apply_type": "AroundCaster",
                                        "effects": [{"type": "Fear", "tick": 30}],
                                    },
                                    {
                                        "type": "RemoveCasterBuff",
                                        "name": "lol_briar_blood_frenzy",
                                    },
                                    {
                                        "type": "RemoveCasterBuff",
                                        "name": "lol_briar_certain_death_frenzy",
                                    },
                                    {
                                        "type": "RemoveCasterBuff",
                                        "name": "lol_briar_snack_ready",
                                    },
                                    certain_death_frenzy,
                                    snack_buff_240,
                                ],
                            },
                        ],
                    },
                ],
            },
        },
        "view_projectiles": [
            {
                "type": "Animated",
                "name": "lol_briar_e_scream_projectile",
                "anim": "asset/lol_mod/aseprite_resources/effects/briar_e_scream",
                "tag": "projectile",
                "z": 2,
                "repeat": False,
            }
        ],
        "view_effects": [
            {
                "type": "Animation",
                "name": "lol_briar_bleed_tick_visual",
                "anim": "asset/lol_mod/aseprite_resources/effects/briar_bleed",
                "tag": "tick",
                "z": 1,
                "is_follow": True,
            },
            {
                "type": "Animation",
                "name": "lol_briar_q_overhead_visual",
                "anim": "asset/lol_mod/aseprite_resources/effects/briar_q_overhead",
                "tag": "impact",
                "z": 2,
                "is_follow": True,
            },
            {
                "type": "Animation",
                "name": "lol_briar_r_mark_visual",
                "anim": "asset/lol_mod/aseprite_resources/effects/briar_r_mark",
                "tag": "mark",
                "z": 2,
                "is_follow": True,
            },
            {
                "type": "Animation",
                "name": "lol_briar_r_trail_visual",
                "anim": "asset/lol_mod/aseprite_resources/effects/briar_r_trail",
                "tag": "trail",
                "z": 1,
                "is_follow": True,
            },
            {
                "type": "Animation",
                "name": "lol_briar_r_arrival_visual",
                "anim": "asset/lol_mod/aseprite_resources/effects/briar_r_arrival",
                "tag": "arrival",
                "z": 0,
                "is_follow": False,
            },
        ],
        "view_buffs": [
            {
                "type": "ThreePhase",
                "name": "lol_briar_certain_death_frenzy",
                "anim": "asset/lol_mod/aseprite_resources/effects/briar_frenzy",
                "pre_tag": "pre",
                "loop_tag": "loop",
                "remove_tag": "remove",
                "z": 1,
            },
        ],
    }
    path = MOD_ROOT / "champion" / "berserker.data_champion"
    write_json(path, champion)
    return path


def build_sivir_data() -> Path:
    """Replace native Boomerang Hunter (project champion 005) with Q/E/R Sivir."""

    def q_hit_effect() -> dict[str, object]:
        return {
            "effect": {
                "type": "Combine",
                "effects": [
                    {"type": "Attack", "damage": 30, "attack_ratio": 55},
                    {"type": "ViewEffect", "name": "lol_sivir_q_hit_visual"},
                    {"type": "TargetSfx", "name": "lol_sivir_q_hit"},
                ],
            },
            "casting_type": "Targeting",
        }

    champion = {
        "id": "boomerang_hunter",
        "category": "Range",
        "tags": ["AD", "Range", "Heal"],
        "sprite": "asset/lol_mod/aseprite_resources/champions/sivir",
        "anim_prefix": "",
        "skill_icons": [
            "asset/lol_mod/icons/sivir_skill",
            "asset/lol_mod/icons/sivir_skill2",
            "asset/lol_mod/icons/sivir_ult",
        ],
        "stat": {
            "attack": 100,
            "magic_power": 0,
            "hp": 900,
            "defence": 20,
            "magic_resistance": 20,
            "move_speed": 900,
            "hp_regen": 2,
            "stack": 0,
            "crit_chance": 0,
        },
        "growth": {
            "attack": 18,
            "magic_power": 0,
            "hp": 90,
            "defence": 7,
            "magic_resistance": 3,
            "move_speed": 9,
            "hp_regen": 1,
            "stack": 0,
            "crit_chance": 0,
        },
        "attack": {
            "action_name": "attack",
            "description": "#asset/base/text/champion?description.boomerang_hunter.attack",
            "duration": 26,
            "cooltime": 60,
            "start_timing": 20,
            "cancelable": True,
            "range": 60000,
            "growth_range": 0,
            "casting_type": "Targeting",
            "casting_target": "Enemy",
            "attack_type": "BaseAttack",
            "can_use_with_move": False,
            "effect": {
                "type": "Combine",
                "effects": [
                    {"type": "Sfx", "name": "lol_sivir_attack_cast"},
                    {
                        "type": "TargetProjectile",
                        "speed": 6000,
                        "name": "lol_sivir_attack_blade",
                        "y_offset": 0,
                        "applied_target": "Enemy",
                        "applied_effects": [
                            {
                                "effect": {
                                    "type": "Combine",
                                    "effects": [
                                        {
                                            "type": "Attack",
                                            "damage": 0,
                                            "attack_ratio": 100,
                                        },
                                        {
                                            "type": "AddCasterBuff",
                                            "buff_state": {
                                                "name": "lol_sivir_fleet_of_foot",
                                                "duration": {"Time": {"tick": 90}},
                                                "move_speed_mult": 12,
                                            },
                                        },
                                        {
                                            "type": "ViewEffect",
                                            "name": "lol_sivir_attack_hit_visual",
                                        },
                                        {
                                            "type": "TargetSfx",
                                            "name": "lol_sivir_attack_hit",
                                        },
                                    ],
                                },
                                "casting_type": "Targeting",
                            }
                        ],
                    },
                ],
            },
        },
        "skill": {
            "action_name": "skill",
            "description": "#asset/base/text/champion?description.boomerang_hunter.skill",
            "duration": 26,
            "cooltime": 360,
            "start_timing": 18,
            "cancelable": False,
            "range": 75000,
            "growth_range": 0,
            "casting_type": "Direction",
            "casting_target": "EnemyWithoutTower",
            "attack_type": "Skill",
            "can_use_with_move": False,
            "effect": {
                "type": "Combine",
                "effects": [
                    {"type": "Sfx", "name": "lol_sivir_q_out"},
                    {
                        "type": "CasterAnimation",
                        "name": "idle_no_boomerang",
                        "tick": 42,
                    },
                    {
                        "type": "LinearProjectile",
                        "penetrate": True,
                        "speed": 4200,
                        "range": 75000,
                        "name": "lol_sivir_q_outgoing",
                        "shape": {"Circle": {"radius": 7000}},
                        "applied_target": "EnemyWithoutTower",
                        "applied_effects": [q_hit_effect()],
                        "end_effects": [
                            {"type": "Sfx", "name": "lol_sivir_q_return"},
                            {
                                "type": "BackToCasterLinearProjectile",
                                "penetrate": True,
                                "speed": 5200,
                                "range": 120000,
                                "name": "lol_sivir_q_return",
                                "shape": {"Circle": {"radius": 7000}},
                                "applied_target": "EnemyWithoutTower",
                                "applied_effects": [q_hit_effect()],
                                "end_effects": [],
                            },
                        ],
                    },
                ],
            },
        },
        "skill2": {
            "action_name": "skill2",
            "description": "#asset/base/text/champion?description.boomerang_hunter.skill2",
            "duration": 25,
            "cooltime": 720,
            "start_timing": 20,
            "cancelable": False,
            "range": 0,
            "growth_range": 0,
            "casting_type": "None",
            "casting_target": "AllyOnlySelf",
            "attack_type": "Skill",
            "can_use_with_move": False,
            "effect": {
                "type": "Combine",
                "effects": [
                    {"type": "Sfx", "name": "lol_sivir_e_cast"},
                    {
                        "type": "AddCasterBuff",
                        "buff_state": {
                            "name": "lol_sivir_spell_shield_window",
                            "duration": {"Time": {"tick": 90}},
                            "skill_damaged_reduce": 100,
                        },
                    },
                    {
                        "type": "AddCasterBuff",
                        "buff_state": {
                            "name": "lol_sivir_spell_shield_speed",
                            "duration": {"Time": {"tick": 120}},
                            "move_speed_mult": 20,
                        },
                    },
                    {
                        "type": "Heal",
                        "amount": 60,
                        "attack_ratio": 15,
                        "ap_ratio": 0,
                        "heal_type": "Caster",
                    },
                ],
            },
        },
        "ult": {
            "action_name": "ult",
            "description": "#asset/base/text/champion?description.boomerang_hunter.ult",
            "duration": 28,
            "cooltime": 3000,
            "start_timing": 20,
            "cancelable": False,
            "range": 85000,
            "growth_range": 0,
            "casting_type": "Targeting",
            "casting_target": "EnemyChampion",
            "attack_type": "Skill",
            "can_use_with_move": False,
            "effect": {
                "type": "Combine",
                "effects": [
                    {"type": "Sfx", "name": "lol_sivir_r_cast"},
                    {"type": "CasterViewEffect", "name": "lol_sivir_r_cast_visual"},
                    {
                        "type": "RangeEffect",
                        "shape": {"Circle": {"radius": 100000}},
                        "target": "AllyChampion",
                        "apply_type": "AroundCaster",
                        "effects": [
                            {
                                "type": "AddBuff",
                                "buff_state": {
                                    "name": "lol_sivir_on_the_hunt_speed",
                                    "duration": {"Time": {"tick": 300}},
                                    "move_speed_mult": 25,
                                },
                            }
                        ],
                    },
                ],
            },
        },
        "view_projectiles": [
            {
                "type": "Animated",
                "name": "lol_sivir_attack_blade",
                "anim": "asset/lol_mod/aseprite_resources/effects/sivir_attack",
                "tag": "projectile",
                "z": 2,
                "repeat": True,
            },
            {
                "type": "Animated",
                "name": "lol_sivir_q_outgoing",
                "anim": "asset/lol_mod/aseprite_resources/effects/sivir_q",
                "tag": "out",
                "z": 2,
                "repeat": True,
            },
            {
                "type": "Animated",
                "name": "lol_sivir_q_return",
                "anim": "asset/lol_mod/aseprite_resources/effects/sivir_q",
                "tag": "return",
                "z": 2,
                "repeat": True,
            },
        ],
        "view_effects": [
            {
                "type": "Animation",
                "name": "lol_sivir_attack_hit_visual",
                "anim": "asset/lol_mod/aseprite_resources/effects/sivir_attack",
                "tag": "hit",
                "z": 2,
                "is_follow": True,
            },
            {
                "type": "Animation",
                "name": "lol_sivir_q_hit_visual",
                "anim": "asset/lol_mod/aseprite_resources/effects/sivir_attack",
                "tag": "hit",
                "z": 2,
                "is_follow": True,
            },
            {
                "type": "Animation",
                "name": "lol_sivir_r_cast_visual",
                "anim": "asset/lol_mod/aseprite_resources/effects/sivir_r_cast",
                "tag": "pulse",
                "z": 0,
                "is_follow": True,
            },
        ],
        "view_buffs": [
            {
                "type": "ThreePhase",
                "name": "lol_sivir_spell_shield_window",
                "anim": "asset/lol_mod/aseprite_resources/effects/sivir_e_shield",
                "pre_tag": "pre",
                "loop_tag": "loop",
                "remove_tag": "remove",
                "z": 1,
            },
            {
                "type": "ThreePhase",
                "name": "lol_sivir_on_the_hunt_speed",
                "anim": "asset/lol_mod/aseprite_resources/effects/sivir_hunt_buff",
                "pre_tag": "pre",
                "loop_tag": "loop",
                "remove_tag": "remove",
                "z": 0,
            },
        ],
    }
    path = MOD_ROOT / "champion" / "boomerang_hunter.data_champion"
    write_json(path, champion)
    return path


def build_qa_contacts(actor_frames: list[Image.Image], icons: list[Path]) -> list[Path]:
    QA_DIR.mkdir(parents=True, exist_ok=True)
    actor_contact = Image.new("RGBA", (6 * 128, 3 * 144), (20, 18, 28, 255))
    draw = ImageDraw.Draw(actor_contact)
    labels = [
        "idle A", "idle B", *[f"run {index}" for index in range(1, 10)],
        "attack A", "attack B", "attack C", "Q cast", "E cast", "R cast", "hit/dead",
    ]
    for index, (frame, label) in enumerate(zip(actor_frames, labels, strict=True)):
        x = (index % 6) * 128
        y = (index // 6) * 144
        zoom = frame.resize((128, 128), Image.Resampling.NEAREST)
        actor_contact.alpha_composite(zoom, (x, y))
        draw.text((x + 4, y + 128), label, fill=(255, 255, 255, 255))
    actor_path = QA_DIR / "shen_actor_contact_final.png"
    save_png(actor_path, actor_contact)

    icon_contact = Image.new("RGBA", (3 * 192, 208), (20, 18, 28, 255))
    draw = ImageDraw.Draw(icon_contact)
    for index, (path, label) in enumerate(zip(icons, ["Q", "E", "R"], strict=True)):
        icon = Image.open(path).convert("RGBA").resize((192, 192), Image.Resampling.NEAREST)
        icon_contact.alpha_composite(icon, (index * 192, 0))
        draw.text((index * 192 + 8, 192), label, fill=(255, 255, 255, 255))
    icon_path = QA_DIR / "shen_skill_icons_final.png"
    save_png(icon_path, icon_contact)
    return [actor_path, icon_path]


def build_lucian_qa_contacts(actor_frames: list[Image.Image], icons: list[Path]) -> list[Path]:
    QA_DIR.mkdir(parents=True, exist_ok=True)
    actor_contact = Image.new("RGBA", (7 * 128, 3 * 144), (20, 18, 28, 255))
    draw = ImageDraw.Draw(actor_contact)
    labels = [
        "idle A",
        "idle B",
        *[f"run {index}" for index in range(1, 10)],
        "attack right",
        "attack left",
        "passive double",
        "Q cast",
        "E start",
        "E travel",
        "R start",
        "R fire",
        "hit",
        "dead",
    ]
    for index, (frame, label) in enumerate(zip(actor_frames, labels, strict=True)):
        x = (index % 7) * 128
        y = (index // 7) * 144
        actor_contact.alpha_composite(frame.resize((128, 128), Image.Resampling.NEAREST), (x, y))
        draw.text((x + 4, y + 128), label, fill=(255, 255, 255, 255))
    actor_path = QA_DIR / "lucian_actor_contact_final.png"
    save_png(actor_path, actor_contact)

    icon_contact = Image.new("RGBA", (3 * 192, 208), (20, 18, 28, 255))
    draw = ImageDraw.Draw(icon_contact)
    for index, (path, label) in enumerate(zip(icons, ["Q", "E", "R"], strict=True)):
        icon = Image.open(path).convert("RGBA").resize((192, 192), Image.Resampling.NEAREST)
        icon_contact.alpha_composite(icon, (index * 192, 0))
        draw.text((index * 192 + 8, 192), label, fill=(255, 255, 255, 255))
    icon_path = QA_DIR / "lucian_skill_icons_final.png"
    save_png(icon_path, icon_contact)

    panels = [
        ("lucian_attack", (64, 32), "attack / passive bolt"),
        ("lucian_q", (192, 32), "Q muzzle-pivot straight beam"),
        ("lucian_r", (64, 32), "R bullet"),
    ]
    vfx_contact = Image.new("RGBA", (8 * 128, 3 * 96), (20, 18, 28, 255))
    draw = ImageDraw.Draw(vfx_contact)
    for row, (name, frame_size, label) in enumerate(panels):
        sheet = Image.open(EFFECT_DIR / f"{name}#sheet.png").convert("RGBA")
        for index in range(8):
            frame = sheet.crop(
                (index * frame_size[0], 0, (index + 1) * frame_size[0], frame_size[1])
            )
            zoom = frame.resize((128, 80), Image.Resampling.NEAREST)
            vfx_contact.alpha_composite(zoom, (index * 128, row * 96))
        draw.text((4, row * 96 + 80), label, fill=(255, 255, 255, 255))
    vfx_path = QA_DIR / "lucian_vfx_contact_final.png"
    save_png(vfx_path, vfx_contact)
    return [actor_path, icon_path, vfx_path]


def build_orianna_qa_contacts(
    actor_frames: list[Image.Image], icons: list[Path]
) -> list[Path]:
    QA_DIR.mkdir(parents=True, exist_ok=True)
    action_counts = [
        ("idle", 4),
        ("run", 8),
        ("attack", 5),
        ("hit", 1),
        ("dead", 9),
        ("skill1/Q", 5),
        ("skill2/E", 5),
        ("ult/R", 4),
    ]
    labels = [
        f"{action} {index + 1}"
        for action, count in action_counts
        for index in range(count)
    ]
    actor_contact = Image.new("RGBA", (7 * 128, 6 * 144), (20, 18, 28, 255))
    draw = ImageDraw.Draw(actor_contact)
    for index, (frame, label) in enumerate(zip(actor_frames, labels, strict=True)):
        x = (index % 7) * 128
        y = (index // 7) * 144
        actor_contact.alpha_composite(
            frame.resize((128, 128), Image.Resampling.NEAREST), (x, y)
        )
        draw.text((x + 4, y + 128), label, fill=(255, 255, 255, 255))
    actor_path = QA_DIR / "orianna_actor_contact_final.png"
    save_png(actor_path, actor_contact)

    icon_contact = Image.new("RGBA", (3 * 192, 208), (20, 18, 28, 255))
    draw = ImageDraw.Draw(icon_contact)
    for index, (path, label) in enumerate(zip(icons, ["Q", "E", "R"], strict=True)):
        icon = Image.open(path).convert("RGBA").resize((192, 192), Image.Resampling.NEAREST)
        icon_contact.alpha_composite(icon, (index * 192, 0))
        draw.text((index * 192 + 8, 192), label, fill=(255, 255, 255, 255))
    icon_path = QA_DIR / "orianna_skill_icons_final.png"
    save_png(icon_path, icon_contact)

    panels = [
        ("orianna_attack", (32, 32), 8, "attack energy dart + impact"),
        ("orianna_q_ball", (40, 40), 4, "Q ball"),
        ("orianna_q_field", (112, 64), 8, "Q impact + field"),
        ("orianna_e_shield", (80, 80), 12, "E projectile + shield + break"),
        ("orianna_r_ring", (160, 160), 12, "R shrink + shockwave"),
    ]
    vfx_contact = Image.new("RGBA", (12 * 128, 5 * 148), (20, 18, 28, 255))
    draw = ImageDraw.Draw(vfx_contact)
    for row, (name, frame_size, count, label) in enumerate(panels):
        sheet = Image.open(EFFECT_DIR / f"{name}#sheet.png").convert("RGBA")
        for index in range(count):
            frame = sheet.crop(
                (index * frame_size[0], 0, (index + 1) * frame_size[0], frame_size[1])
            )
            frame.thumbnail((124, 124), Image.Resampling.NEAREST)
            x = index * 128 + (128 - frame.width) // 2
            y = row * 148 + (124 - frame.height) // 2
            vfx_contact.alpha_composite(frame, (x, y))
        draw.text((4, row * 148 + 128), label, fill=(255, 255, 255, 255))
    vfx_path = QA_DIR / "orianna_vfx_contact_final.png"
    save_png(vfx_path, vfx_contact)
    return [actor_path, icon_path, vfx_path]


def build_briar_qa_contacts(
    actor_frames: list[Image.Image], icons: list[Path]
) -> list[Path]:
    QA_DIR.mkdir(parents=True, exist_ok=True)
    labels = [
        "idle A",
        "idle B",
        "attack windup",
        "attack strike",
        "snack lunge",
        "snack bite",
        "Q crack",
        "Q frenzy",
        "E charge",
        "E release",
        "R throw",
        "R chase",
        "hit",
        "fall",
        "grounded",
        "defeated",
        *[f"run {index}" for index in range(1, 10)],
        "fade 58%",
        "fade 28%",
        "transparent",
    ]
    actor_contact = Image.new("RGBA", (7 * 128, 4 * 144), (20, 18, 28, 255))
    draw = ImageDraw.Draw(actor_contact)
    for index, (frame, label) in enumerate(zip(actor_frames, labels, strict=True)):
        x = (index % 7) * 128
        y = (index // 7) * 144
        actor_contact.alpha_composite(
            frame.resize((128, 128), Image.Resampling.NEAREST), (x, y)
        )
        draw.text((x + 4, y + 128), label, fill=(255, 255, 255, 255))
    actor_path = QA_DIR / "briar_actor_contact_final.png"
    save_png(actor_path, actor_contact)

    icon_contact = Image.new("RGBA", (3 * 192, 208), (20, 18, 28, 255))
    draw = ImageDraw.Draw(icon_contact)
    for index, (path, label) in enumerate(zip(icons, ["Q", "E", "R"], strict=True)):
        icon = Image.open(path).convert("RGBA").resize((192, 192), Image.Resampling.NEAREST)
        icon_contact.alpha_composite(icon, (index * 192, 0))
        draw.text((index * 192 + 8, 192), label, fill=(255, 255, 255, 255))
    icon_path = QA_DIR / "briar_skill_icons_final.png"
    save_png(icon_path, icon_contact)

    panels = [
        ("briar_bleed", (48, 48), 8, "passive bleed tick"),
        ("briar_q_overhead", (64, 64), 8, "Q target-follow overhead impact"),
        ("briar_frenzy", (96, 96), 8, "R frenzy aura"),
        ("briar_e_scream", (112, 64), 8, "E forward scream"),
        ("briar_r_mark", (64, 64), 4, "R target mark"),
        ("briar_r_trail", (96, 48), 4, "R chase trail"),
        ("briar_r_arrival", (96, 96), 4, "R arrival/fear"),
    ]
    vfx_contact = Image.new(
        "RGBA", (8 * 128, len(panels) * 148), (20, 18, 28, 255)
    )
    draw = ImageDraw.Draw(vfx_contact)
    for row, (name, frame_size, count, label) in enumerate(panels):
        sheet = Image.open(EFFECT_DIR / f"{name}#sheet.png").convert("RGBA")
        for index in range(count):
            frame = sheet.crop(
                (index * frame_size[0], 0, (index + 1) * frame_size[0], frame_size[1])
            )
            frame.thumbnail((124, 124), Image.Resampling.NEAREST)
            x = index * 128 + (128 - frame.width) // 2
            y = row * 148 + (124 - frame.height) // 2
            vfx_contact.alpha_composite(frame, (x, y))
        draw.text((4, row * 148 + 128), label, fill=(255, 255, 255, 255))
    vfx_path = QA_DIR / "briar_vfx_contact_final.png"
    save_png(vfx_path, vfx_contact)
    return [actor_path, icon_path, vfx_path]


def build_sivir_qa_contacts(
    actor_frames: list[Image.Image], icons: list[Path]
) -> list[Path]:
    QA_DIR.mkdir(parents=True, exist_ok=True)
    labels = [
        "idle A",
        "idle B",
        "attack windup",
        "attack release",
        "Q windup",
        "Q follow-through",
        "E shield cast",
        "R command",
        "hit A",
        "hit B",
        "crouch recover",
        "ready",
        "fall",
        "defeated",
        "kneel",
        "seated",
        *[f"run {index}" for index in range(1, 10)],
        "fade 58%",
        "fade 28%",
        "transparent",
        "boomerang",
        "big boomerang",
        "ult boomerang",
    ]
    actor_contact = Image.new("RGBA", (8 * 128, 4 * 144), (20, 18, 28, 255))
    draw = ImageDraw.Draw(actor_contact)
    for index, (frame, label) in enumerate(zip(actor_frames, labels, strict=True)):
        x = (index % 8) * 128
        y = (index // 8) * 144
        actor_contact.alpha_composite(
            frame.resize((128, 128), Image.Resampling.NEAREST), (x, y)
        )
        draw.text((x + 4, y + 128), label, fill=(255, 255, 255, 255))
    actor_path = QA_DIR / "sivir_actor_contact_final.png"
    save_png(actor_path, actor_contact)

    icon_contact = Image.new("RGBA", (3 * 192, 208), (20, 18, 28, 255))
    draw = ImageDraw.Draw(icon_contact)
    for index, (path, label) in enumerate(zip(icons, ["Q", "E", "R"], strict=True)):
        icon = Image.open(path).convert("RGBA").resize((192, 192), Image.Resampling.NEAREST)
        icon_contact.alpha_composite(icon, (index * 192, 0))
        draw.text((index * 192 + 8, 192), label, fill=(255, 255, 255, 255))
    icon_path = QA_DIR / "sivir_skill_icons_final.png"
    save_png(icon_path, icon_contact)

    panels = [
        ("sivir_attack", (48, 32), 8, "basic attack blade + hit"),
        ("sivir_q", (64, 48), 8, "Q outbound + return"),
        ("sivir_e_shield", (64, 64), 8, "E shield pre/loop/remove"),
        ("sivir_r_cast", (128, 64), 8, "R command pulse"),
        ("sivir_hunt_buff", (64, 32), 8, "R ally speed buff"),
    ]
    vfx_contact = Image.new("RGBA", (8 * 128, 5 * 120), (20, 18, 28, 255))
    draw = ImageDraw.Draw(vfx_contact)
    for row, (name, frame_size, count, label) in enumerate(panels):
        sheet = Image.open(EFFECT_DIR / f"{name}#sheet.png").convert("RGBA")
        for index in range(count):
            frame = sheet.crop(
                (index * frame_size[0], 0, (index + 1) * frame_size[0], frame_size[1])
            )
            frame.thumbnail((124, 96), Image.Resampling.NEAREST)
            x = index * 128 + (128 - frame.width) // 2
            y = row * 120 + (96 - frame.height) // 2
            vfx_contact.alpha_composite(frame, (x, y))
        draw.text((4, row * 120 + 100), label, fill=(255, 255, 255, 255))
    vfx_path = QA_DIR / "sivir_vfx_contact_final.png"
    save_png(vfx_path, vfx_contact)
    return [actor_path, icon_path, vfx_path]


def _hd_surface_record(path: Path) -> dict[str, object]:
    image = Image.open(path).convert("RGBA")
    alpha = image.getchannel("A")
    bbox = alpha.getbbox()
    histogram = alpha.histogram()
    return {
        "path": path.relative_to(MOD_ROOT).as_posix(),
        "dimensions": list(image.size),
        "alpha_bbox": list(bbox) if bbox else None,
        "hard_alpha": sum(histogram[1:255]) == 0,
        "opaque_pixels": histogram[255],
        "sha256": sha256(path),
    }


def _hd_actor_record(
    champion: str,
    actor_sheet: Path,
    actor_anim: Path,
    core_tags: tuple[str, ...],
    *,
    foot_baseline: int,
    expected_idle_height: int,
    accent: str,
    max_visible_width: int = 58,
    max_visible_height: int = 44,
) -> dict[str, object]:
    sheet = Image.open(actor_sheet).convert("RGBA")
    anims = json.loads(actor_anim.read_text(encoding="utf-8"))["anims"]
    action_records: dict[str, object] = {}
    for tag in core_tags:
        bboxes: list[list[int]] = []
        for frame_row in anims[tag]["frames"]:
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
                raise ValueError(f"{champion} HD actor {tag} contains an empty frame")
            if (
                bbox[2] - bbox[0] > max_visible_width
                or bbox[3] - bbox[1] > max_visible_height
            ):
                raise ValueError(
                    f"{champion} HD actor {tag} exceeds "
                    f"{max_visible_width}x{max_visible_height}: {bbox}"
                )
            if bbox[3] > foot_baseline:
                raise ValueError(
                    f"{champion} HD actor {tag} crosses y={foot_baseline}: {bbox}"
                )
            bboxes.append(list(bbox))
        action_records[tag] = {
            "frame_count": len(bboxes),
            "alpha_bboxes": bboxes,
            "visible_height_range": [
                min(row[3] - row[1] for row in bboxes),
                max(row[3] - row[1] for row in bboxes),
            ],
            "visible_width_range": [
                min(row[2] - row[0] for row in bboxes),
                max(row[2] - row[0] for row in bboxes),
            ],
            "bottom_range": [min(row[3] for row in bboxes), max(row[3] for row in bboxes)],
        }

    idle_data = anims["idle"]["frames"][0]["data"]
    idle = sheet.crop(
        (
            idle_data["x"],
            idle_data["y"],
            idle_data["x"] + idle_data["w"],
            idle_data["y"] + idle_data["h"],
        )
    )
    idle_bbox = idle.getchannel("A").getbbox()
    if idle_bbox is None:
        raise ValueError(f"{champion} HD primary idle is empty")
    if idle_bbox[3] - idle_bbox[1] != expected_idle_height:
        raise ValueError(
            f"{champion} HD idle height changed: {idle_bbox}, expected {expected_idle_height}"
        )
    margin = max(1, round((idle_bbox[2] - idle_bbox[0]) * 0.08))
    face_box = (
        idle_bbox[0] + margin,
        idle_bbox[1],
        idle_bbox[2] - margin,
        idle_bbox[1] + round((idle_bbox[3] - idle_bbox[1]) * 0.56),
    )
    opaque_luma: list[float] = []
    accent_pixels = 0
    for y in range(face_box[1], face_box[3]):
        for x in range(face_box[0], face_box[2]):
            red, green, blue, alpha = idle.getpixel((x, y))
            if alpha < 128:
                continue
            opaque_luma.append((299 * red + 587 * green + 114 * blue) / 1000)
            if accent == "cyan":
                accent_pixels += (
                    green >= 100
                    and blue >= 115
                    and blue >= red + 20
                    and green >= red + 10
                )
            elif accent == "gold":
                accent_pixels += (
                    red >= 120
                    and green >= 70
                    and red >= green + 12
                    and green >= blue + 24
                )
            else:
                accent_pixels += red >= 100 and green <= 70 and blue <= 90
    dynamic_range = max(opaque_luma) - min(opaque_luma) if opaque_luma else 0.0
    if len(opaque_luma) < 120 or accent_pixels < 2 or dynamic_range < 140:
        raise ValueError(
            f"{champion} battle face is not readable: opaque={len(opaque_luma)}, "
            f"accent={accent_pixels}, range={dynamic_range:.1f}"
        )
    return {
        "sheet": actor_sheet.relative_to(MOD_ROOT).as_posix(),
        "animation": actor_anim.relative_to(MOD_ROOT).as_posix(),
        "uniform_xy_scale": True,
        "x_only_compression": False,
        "resampling": "LANCZOS source fit, hard alpha, 96-color final palette",
        "foot_baseline_exclusive_y": foot_baseline,
        "first_idle_alpha_bbox": list(idle_bbox),
        "face_readability": {
            "sample_box": list(face_box),
            "opaque_pixels": len(opaque_luma),
            f"{accent}_accent_pixels": accent_pixels,
            "luminance_dynamic_range": round(dynamic_range, 2),
        },
        "core_actions": action_records,
    }


def _build_hd_surface_contact(
    champion: str,
    champion_id: str,
    actor_sheet: Path,
    output_path: Path,
) -> None:
    contact = Image.new("RGBA", (1120, 300), (10, 18, 31, 255))
    draw = ImageDraw.Draw(contact)
    label = (212, 226, 238, 255)
    draw.text((16, 10), f"{champion.upper()} HD / SOURCE-DIRECT UI SURFACES", fill=label)

    idle = Image.open(actor_sheet).convert("RGBA").crop((0, 0, 64, 64))
    draw.text((16, 42), "battle idle 64", fill=label)
    contact.alpha_composite(idle.resize((128, 128), Image.Resampling.NEAREST), (16, 62))

    surface_specs = (
        ("sidebar 46", CHAMPION_PORTRAIT_DIR / f"{champion_id}_compact.png", 46),
        (
            "scoreboard 34",
            CHAMPION_PORTRAIT_DIR / f"{champion_id}_scoreboard.png",
            34,
        ),
    )
    for index, (surface_label, path, runtime_size) in enumerate(surface_specs):
        x = 170 + index * 150
        draw.text((x, 42), surface_label, fill=label)
        tile = Image.new("RGBA", (128, 128), (7, 13, 23, 255))
        portrait = Image.open(path).convert("RGBA")
        runtime = portrait.resize((runtime_size, runtime_size), Image.Resampling.NEAREST)
        zoom = runtime.resize((runtime_size * 2, runtime_size * 2), Image.Resampling.NEAREST)
        tile.alpha_composite(runtime, ((128 - runtime.width) // 2, 8))
        tile.alpha_composite(zoom, ((128 - zoom.width) // 2, 128 - zoom.height))
        contact.alpha_composite(tile, (x, 62))

    grid_x = 470
    draw.text((grid_x, 42), "BP grid 90x122 / name y=96", fill=label)
    grid_tile = Image.new("RGBA", (110, 142), (7, 13, 23, 255))
    grid = Image.open(CHAMPION_PORTRAIT_DIR / f"{champion_id}_grid.png").convert("RGBA")
    grid_tile.alpha_composite(grid, (10, 10))
    grid_draw = ImageDraw.Draw(grid_tile)
    grid_draw.rectangle((10, 106, 99, 131), fill=(34, 46, 64, 255))
    grid_draw.text((31, 111), "NAME", fill=(166, 181, 196, 255))
    contact.alpha_composite(grid_tile, (grid_x, 62))

    full_x = 650
    draw.text((full_x, 42), "encyclopedia 64", fill=label)
    full_tile = Image.new("RGBA", (142, 142), (7, 13, 23, 255))
    fullbody = Image.open(CHAMPION_FULLBODY_DIR / f"{champion_id}.png").convert("RGBA")
    full_tile.alpha_composite(fullbody.resize((128, 128), Image.Resampling.NEAREST), (7, 7))
    contact.alpha_composite(full_tile, (full_x, 62))

    splash_x = 820
    draw.text((splash_x, 42), "BP side card / 1420x860", fill=label)
    splash = Image.open(MOD_ROOT / "BanPickIllust" / f"{champion_id}.png").convert("RGBA")
    splash.thumbnail((284, 172), Image.Resampling.LANCZOS)
    contact.alpha_composite(splash, (splash_x, 62))
    draw.text(
        (16, 254),
        "Battle keeps one aspect-preserving scale; UI crops come directly from the accepted HD idle source.",
        fill=label,
    )
    save_png(output_path, contact)


def build_orianna_briar_hd_surface_qa() -> list[Path]:
    specs = (
        {
            "champion": "Shen",
            "champion_id": "lol_shen",
            "source": ACTOR_SOURCE,
            "actor_sheet": ACTOR_DIR / "shen#sheet.png",
            "actor_anim": ACTOR_DIR / "shen#anim.fanim",
            "tags": ("idle", "run", "attack", "skill", "skill2", "ult", "hit"),
            "baseline": SHEN_BATTLE_FOOT_BASELINE,
            "idle_height": SHEN_BATTLE_IDLE_HEIGHT,
            "max_visible_width": SHEN_BATTLE_MAX_SIZE[0],
            "max_visible_height": SHEN_BATTLE_MAX_SIZE[1],
            "accent": "cyan",
            "qa": QA_DIR / "shen_hd_surface_qa.json",
            "contact": QA_DIR / "shen_portrait_surface_final.png",
        },
        {
            "champion": "Lucian",
            "champion_id": "archer",
            "source": LUCIAN_ACTOR_SOURCE,
            "actor_sheet": ACTOR_DIR / "lucian#sheet.png",
            "actor_anim": ACTOR_DIR / "lucian#anim.fanim",
            "tags": (
                "idle",
                "run",
                "attack_right",
                "attack_left",
                "attack_double",
                "skill",
                "skill2",
                "ult",
                "hit",
            ),
            "baseline": LUCIAN_BATTLE_FOOT_BASELINE,
            "idle_height": LUCIAN_BATTLE_IDLE_HEIGHT,
            "max_visible_width": LUCIAN_BATTLE_MAX_SIZE[0],
            "max_visible_height": LUCIAN_BATTLE_MAX_SIZE[1],
            "accent": "cyan",
            "qa": QA_DIR / "lucian_hd_surface_qa.json",
            "contact": QA_DIR / "lucian_portrait_surface_final.png",
        },
        {
            "champion": "Orianna",
            "champion_id": "barrier_magician",
            "source": ORIANNA_ACTOR_SOURCE,
            "actor_sheet": ACTOR_DIR / "orianna#sheet.png",
            "actor_anim": ACTOR_DIR / "orianna#anim.fanim",
            "tags": ("idle", "run", "attack", "skill1", "skill2", "ult", "hit"),
            "baseline": ORIANNA_BATTLE_FOOT_BASELINE,
            "idle_height": ORIANNA_BATTLE_IDLE_HEIGHT,
            "max_visible_width": ORIANNA_BATTLE_MAX_SIZE[0],
            "max_visible_height": ORIANNA_BATTLE_MAX_SIZE[1],
            "accent": "cyan",
            "qa": QA_DIR / "orianna_hd_surface_qa.json",
            "contact": QA_DIR / "orianna_portrait_surface_final.png",
        },
        {
            "champion": "Briar",
            "champion_id": "berserker",
            "source": BRIAR_ACTOR_SOURCE,
            "actor_sheet": ACTOR_DIR / "briar#sheet.png",
            "actor_anim": ACTOR_DIR / "briar#anim.fanim",
            "tags": (
                "idle",
                "berserk_idle",
                "run",
                "berserk_run",
                "attack",
                "attack2",
                "berserk_attack",
                "skill1",
                "skill2",
                "skill2_berserk",
                "ult",
                "hit",
            ),
            "baseline": BRIAR_BATTLE_FOOT_BASELINE,
            "idle_height": BRIAR_BATTLE_IDLE_HEIGHT,
            "max_visible_width": BRIAR_BATTLE_MAX_SIZE[0],
            "max_visible_height": BRIAR_BATTLE_MAX_SIZE[1],
            "accent": "red",
            "qa": QA_DIR / "briar_hd_surface_qa.json",
            "contact": QA_DIR / "briar_portrait_surface_final.png",
        },
        {
            "champion": "Sivir",
            "champion_id": "boomerang_hunter",
            "source": SIVIR_ACTOR_SOURCE,
            "actor_sheet": ACTOR_DIR / "sivir#sheet.png",
            "actor_anim": ACTOR_DIR / "sivir#anim.fanim",
            "tags": ("idle", "run", "attack", "skill", "skill2", "ult", "hit"),
            "baseline": SIVIR_BATTLE_FOOT_BASELINE,
            "idle_height": SIVIR_BATTLE_IDLE_HEIGHT,
            "max_visible_width": SIVIR_BATTLE_MAX_SIZE[0],
            "max_visible_height": SIVIR_BATTLE_MAX_SIZE[1],
            "accent": "gold",
            "qa": QA_DIR / "sivir_hd_surface_qa.json",
            "contact": QA_DIR / "sivir_portrait_surface_final.png",
        },
    )
    outputs: list[Path] = []
    for spec in specs:
        champion_id = str(spec["champion_id"])
        surface_paths = {
            "side_card": MOD_ROOT / "BanPickIllust" / f"{champion_id}.png",
            "encyclopedia": CHAMPION_FULLBODY_DIR / f"{champion_id}.png",
            "sidebar": CHAMPION_PORTRAIT_DIR / f"{champion_id}_compact.png",
            "scoreboard": CHAMPION_PORTRAIT_DIR / f"{champion_id}_scoreboard.png",
            "bp_grid": CHAMPION_PORTRAIT_DIR / f"{champion_id}_grid.png",
        }
        records = {name: _hd_surface_record(path) for name, path in surface_paths.items()}
        grid_bbox = records["bp_grid"]["alpha_bbox"]
        if not isinstance(grid_bbox, list) or grid_bbox[3] > 86:
            raise ValueError(f"{spec['champion']} BP-grid alpha enters the name band")
        records["bp_grid"]["name_band_y"] = 96
        records["bp_grid"]["name_band_clearance"] = 96 - grid_bbox[3]
        for name in ("sidebar", "scoreboard"):
            bbox = records[name]["alpha_bbox"]
            if not isinstance(bbox, list):
                raise ValueError(f"{spec['champion']} {name} portrait is empty")
            if (
                bbox[2] - bbox[0] > 50
                or bbox[3] - bbox[1] > 50
                or min(bbox[0], bbox[1], 64 - bbox[2], 64 - bbox[3]) < 6
            ):
                raise ValueError(f"{spec['champion']} {name} portrait is unsafe: {bbox}")
        if records["sidebar"]["sha256"] == records["scoreboard"]["sha256"]:
            raise ValueError(f"{spec['champion']} sidebar and scoreboard crops are not independent")

        battle_actor = _hd_actor_record(
            str(spec["champion"]),
            Path(spec["actor_sheet"]),
            Path(spec["actor_anim"]),
            tuple(spec["tags"]),
            foot_baseline=int(spec["baseline"]),
            expected_idle_height=int(spec["idle_height"]),
            accent=str(spec["accent"]),
            max_visible_width=int(spec.get("max_visible_width", 58)),
            max_visible_height=int(spec.get("max_visible_height", 44)),
        )
        payload = {
            "schema_version": 1,
            "champion": spec["champion"],
            "native_id": champion_id,
            "accepted_source": Path(spec["source"]).relative_to(MOD_ROOT).as_posix(),
            "accepted_source_sha256": sha256(Path(spec["source"])),
            "source_route": "existing processed high-resolution ImageGen idle; no new generation",
            "skill_logic_changed": False,
            "battle_actor": battle_actor,
            "surfaces": records,
            "runtime_routing": {
                "scoreboard_square_px": [14, 38],
                "sidebar_square_px": [39, 52],
                "bp_native_grid_px": [124, 132],
                "bp_replacement_dimensions": [90, 122],
                "battle_sprite_commands_untouched": True,
            },
        }
        write_json(Path(spec["qa"]), payload)
        _build_hd_surface_contact(
            str(spec["champion"]),
            champion_id,
            Path(spec["actor_sheet"]),
            Path(spec["contact"]),
        )
        outputs.extend([Path(spec["qa"]), Path(spec["contact"])])
    return outputs


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def build_sivir_imagegen_audit() -> Path:
    def image_record(role: str, path: Path) -> dict[str, object]:
        with Image.open(path) as opened:
            image = opened.convert("RGBA")
            alpha = image.getchannel("A")
            histogram = alpha.histogram()
            record: dict[str, object] = {
                "role": role,
                "path": path.relative_to(MOD_ROOT).as_posix(),
                "sha256": sha256(path),
                "size_bytes": path.stat().st_size,
                "dimensions": list(opened.size),
                "mode": opened.mode,
                "alpha": {
                    "present": "A" in opened.getbands(),
                    "min": alpha.getextrema()[0],
                    "max": alpha.getextrema()[1],
                    "transparent_pixels": histogram[0],
                    "partial_pixels": sum(histogram[1:255]),
                    "opaque_pixels": histogram[255],
                    "nonzero_bbox": list(alpha.getbbox()) if alpha.getbbox() else None,
                },
            }
        return record

    source_specs = [
        ("actor_model", MOD_ROOT / "source/imagegen/sivir_actor_contact.png"),
        ("run_cycle_nine_phase_source", MOD_ROOT / "source/imagegen/sivir_run_contact.png"),
        ("q_icon", MOD_ROOT / "source/imagegen/sivir_q_icon_source.png"),
        ("e_icon", MOD_ROOT / "source/imagegen/sivir_e_icon_source.png"),
        ("r_icon", MOD_ROOT / "source/imagegen/sivir_r_icon_source.png"),
        ("basic_attack_vfx", MOD_ROOT / "source/imagegen/sivir_attack_vfx_contact.png"),
        ("q_out_return_vfx", MOD_ROOT / "source/imagegen/sivir_q_vfx_contact.png"),
        ("e_spell_shield_vfx", MOD_ROOT / "source/imagegen/sivir_e_vfx_contact.png"),
        ("r_cast_vfx", MOD_ROOT / "source/imagegen/sivir_r_cast_vfx_contact.png"),
        ("r_ally_buff_vfx", MOD_ROOT / "source/imagegen/sivir_hunt_buff_vfx_contact.png"),
    ]
    processed_specs = [
        ("actor_model_alpha", SIVIR_ACTOR_SOURCE),
        ("run_cycle_alpha", SIVIR_RUN_SOURCE),
        ("basic_attack_vfx_alpha", SIVIR_VFX_SOURCES["sivir_attack"]),
        ("q_out_return_vfx_alpha", SIVIR_VFX_SOURCES["sivir_q"]),
        ("e_spell_shield_vfx_alpha", SIVIR_VFX_SOURCES["sivir_e_shield"]),
        ("r_cast_vfx_alpha", SIVIR_VFX_SOURCES["sivir_r_cast"]),
        ("r_ally_buff_vfx_alpha", SIVIR_VFX_SOURCES["sivir_hunt_buff"]),
    ]
    runtime_paths = [
        ACTOR_DIR / "sivir#sheet.png",
        ACTOR_DIR / "sivir#anim.fanim",
        *(ICON_DIR / name for name in SIVIR_ICON_SOURCES),
        *(EFFECT_DIR / f"{name}#{suffix}" for name in SIVIR_VFX_SOURCES for suffix in ("sheet.png", "anim.fanim")),
        MOD_ROOT / "champion/boomerang_hunter.data_champion",
        QA_DIR / "sivir_actor_contact_final.png",
        QA_DIR / "sivir_skill_icons_final.png",
        QA_DIR / "sivir_vfx_contact_final.png",
    ]
    payload = {
        "schema_version": 1,
        "generator": "built-in image_gen",
        "generated_on": "2026-07-11",
        "audited_on": "2026-07-11",
        "prompt_record": "source/imagegen/PROMPTS.md",
        "generated_images_batch": "019f4bd8-30d3-7b60-98fa-58403cf263c7",
        "background_removal": "remove_chroma_key.py with border auto-key, soft matte, thresholds 12/220 and despill; icons are packed directly from opaque generated sources",
        "sources": [image_record(role, path) for role, path in source_specs],
        "processed": [image_record(role, path) for role, path in processed_specs],
        "runtime_files": [
            {
                "path": path.relative_to(MOD_ROOT).as_posix(),
                "size_bytes": path.stat().st_size,
                "sha256": sha256(path),
            }
            for path in runtime_paths
        ],
    }
    path = QA_DIR / "sivir_imagegen_sources.json"
    write_json(path, payload)
    return path


MANIFEST_TEXT_SUFFIXES = {
    ".champion_view",
    ".data_champion",
    ".fanim",
    ".i18n",
    ".json",
    ".md",
    ".mod_info",
    ".override_info",
    ".sound_info",
    ".sprite_sheet",
    ".style",
    ".svg",
    ".txt",
    ".ui",
}


def normalize_manifest_text_lf(path: Path) -> None:
    """Make generated/runtime text hashes independent of Windows checkout EOLs.

    Git stores these files as LF, while Python generators on Windows can leave
    CRLF bytes in the working tree.  The manifest hashes installed bytes, so a
    CRLF-only local hash would drift after GitHub checks out the same blob as
    LF.  Canonicalize every manifest-owned text file before hashing/copying.
    """
    if path.suffix.lower() not in MANIFEST_TEXT_SUFFIXES:
        return
    raw = path.read_bytes()
    if b"\0" in raw:
        raise ValueError(f"manifest text candidate contains NUL bytes: {path}")
    normalized = raw.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    if normalized != raw:
        path.write_bytes(normalized)


def build_manifest(yone_outputs: list[Path]) -> Path:
    runtime_roots = [
        MOD_ROOT / "mod.mod_info",
        MOD_ROOT / "mod.override_info",
        MOD_ROOT / "champion",
        MOD_ROOT / "icons",
        MOD_ROOT / "aseprite_resources",
        MOD_ROOT / "BanPickIllust",
        MOD_ROOT / "ui",
        MOD_ROOT / "style",
        MOD_ROOT / "text",
        MOD_ROOT / "sound",
        MOD_ROOT / "lol_mod.dll",
        # Keep compact provenance records available to an installed test mod,
        # but never copy contact sheets, previews, or other bulky QA images
        # into the active game directory.
        QA_DIR / "xayah_imagegen_sources.json",
        QA_DIR / "xayah_official_audio_sources.json",
        QA_DIR / "xayah_ui_scale_qa.json",
        QA_DIR / "urgot_visual_qa.json",
        QA_DIR / "urgot_official_audio_sources.json",
        QA_DIR / "yone_visual_contract.json",
        QA_DIR / "yone_imagegen_sources.json",
        QA_DIR / "yone_visual_qa.md",
        QA_DIR / "yone_skill_contract_qa.md",
        QA_DIR / "yone_official_audio_sources.json",
    ]
    files: list[Path] = []
    for root in runtime_roots:
        if root.is_file():
            files.append(root)
        elif root.is_dir():
            files.extend(path for path in root.rglob("*") if path.is_file())

    # Most of the historical pack predates builder-owned output inventories,
    # so its runtime roots are still scanned above.  Yone is stricter: only
    # files returned by build_yone plus the explicitly pinned data/audio
    # inputs below may enter the release.  This turns an unknown leftover E
    # asset into a build failure instead of silently republishing it.
    declared_yone_paths = {
        path.relative_to(MOD_ROOT).as_posix()
        for path in yone_outputs
        if path.is_relative_to(MOD_ROOT)
    }
    declared_yone_paths.update(
        {
            "champion/dual_blader.data_champion",
            "qa/yone_official_audio_sources.json",
            "qa/yone_skill_contract_qa.md",
            "sound/sfx/yone_native_silence.sound_info",
            "sound/sfx/yone_native_silence_clip.wav",
        }
    )
    yone_audio_audit = json.loads(
        (QA_DIR / "yone_official_audio_sources.json").read_text(encoding="utf-8")
    )
    for output in yone_audio_audit.get("outputs", []):
        for record_key in ("sound_info", "wav"):
            relative = output.get(record_key, {}).get("path")
            if relative:
                declared_yone_paths.add(relative)

    def is_yone_release_path(relative: str) -> bool:
        folded = relative.casefold()
        return "yone" in folded or "dual_blader" in folded

    undeclared_yone_paths = sorted(
        path.relative_to(MOD_ROOT).as_posix()
        for path in files
        if is_yone_release_path(path.relative_to(MOD_ROOT).as_posix())
        and path.relative_to(MOD_ROOT).as_posix() not in declared_yone_paths
    )
    if undeclared_yone_paths:
        raise RuntimeError(
            "Undeclared Yone files would enter the release manifest:\n"
            + "\n".join(undeclared_yone_paths)
        )
    for path in files:
        normalize_manifest_text_lf(path)
    payload = {
        "schema_version": 1,
        "generator": "mods/lol_mod/tools/build_lol_mod.py",
        "files": [
            {
                "path": path.relative_to(MOD_ROOT).as_posix(),
                "size": path.stat().st_size,
                "sha256": sha256(path),
            }
            for path in sorted(files)
        ],
    }
    path = MOD_ROOT / "build_manifest.json"
    write_json(path, payload)
    return path


def rebuild_quality_upgrade() -> None:
    for script_name in QUALITY_BUILDERS:
        script = MOD_ROOT / "tools" / script_name
        if not script.is_file():
            raise FileNotFoundError(f"Missing quality-upgrade builder: {script}")
        subprocess.run([sys.executable, str(script)], cwd=MOD_ROOT, check=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skip-manifest", action="store_true", help="Build art only")
    parser.add_argument(
        "--rebuild-quality",
        action="store_true",
        help="rebuild item, objective, jungle, tower, and auxiliary UI outputs",
    )
    args = parser.parse_args()
    if args.rebuild_quality:
        rebuild_quality_upgrade()
    required_sources = [
        ACTOR_SOURCE,
        RUN_SOURCE,
        *ICON_SOURCES.values(),
        *(entry[0] for entry in VFX_SOURCES.values()),
        LUCIAN_ACTOR_SOURCE,
        LUCIAN_RUN_SOURCE,
        *LUCIAN_ICON_SOURCES.values(),
        *(entry[0] for entry in LUCIAN_VFX_SOURCES.values()),
        ORIANNA_ACTOR_SOURCE,
        ORIANNA_RUN_SOURCE,
        *ORIANNA_ICON_SOURCES.values(),
        *ORIANNA_VFX_SOURCES.values(),
        BRIAR_ACTOR_SOURCE,
        BRIAR_RUN_SOURCE,
        *BRIAR_ICON_SOURCES.values(),
        *BRIAR_VFX_SOURCES.values(),
        SIVIR_ACTOR_SOURCE,
        SIVIR_RUN_SOURCE,
        *SIVIR_ICON_SOURCES.values(),
        *SIVIR_VFX_SOURCES.values(),
    ]
    missing = [path for path in required_sources if not path.exists()]
    if missing:
        raise SystemExit("Missing processed image-gen sources:\n" + "\n".join(str(path) for path in missing))
    actor_sheet, actor_anim, actor_frames = build_actor()
    icons = build_icons()
    vfx = build_vfx()
    shen_champion = build_shen_data()
    qa = build_qa_contacts(actor_frames, icons)
    lucian_sheet, lucian_anim, lucian_frames = build_lucian_actor()
    lucian_icons = build_lucian_icons()
    lucian_vfx = build_lucian_vfx()
    lucian_champion = build_lucian_data()
    lucian_qa = build_lucian_qa_contacts(lucian_frames, lucian_icons)
    orianna_sheet, orianna_anim, orianna_frames = build_orianna_actor()
    orianna_icons = build_orianna_icons()
    orianna_vfx = build_orianna_vfx()
    orianna_champion = build_orianna_data()
    orianna_qa = build_orianna_qa_contacts(orianna_frames, orianna_icons)
    briar_sheet, briar_anim, briar_frames = build_briar_actor()
    briar_icons = build_briar_icons()
    briar_vfx = build_briar_vfx()
    briar_champion = build_briar_data()
    briar_qa = build_briar_qa_contacts(briar_frames, briar_icons)
    sivir_sheet, sivir_anim, sivir_frames = build_sivir_actor()
    sivir_icons = build_sivir_icons()
    sivir_vfx = build_sivir_vfx()
    sivir_champion = build_sivir_data()
    sivir_silence = build_sivir_native_silence()
    sivir_qa = build_sivir_qa_contacts(sivir_frames, sivir_icons)
    sivir_imagegen_audit = build_sivir_imagegen_audit()
    kled_outputs = build_kled_assets()
    xayah_outputs = build_xayah_assets()
    urgot_outputs = build_urgot_assets()
    yone_outputs = build_yone_assets()
    champion_fullbody_portraits = build_champion_fullbody_portraits()
    orianna_briar_hd_surface_qa = build_orianna_briar_hd_surface_qa()
    legacy_battle_actor_scale_qa = build_legacy_battle_actor_scale_qa()
    manifest = None if args.skip_manifest else build_manifest(yone_outputs)
    for path in [
        actor_sheet,
        actor_anim,
        *icons,
        *vfx,
        shen_champion,
        *qa,
        lucian_sheet,
        lucian_anim,
        *lucian_icons,
        *lucian_vfx,
        lucian_champion,
        *lucian_qa,
        orianna_sheet,
        orianna_anim,
        *orianna_icons,
        *orianna_vfx,
        orianna_champion,
        *orianna_qa,
        briar_sheet,
        briar_anim,
        *briar_icons,
        *briar_vfx,
        briar_champion,
        *briar_qa,
        sivir_sheet,
        sivir_anim,
        *sivir_icons,
        *sivir_vfx,
        sivir_champion,
        *sivir_silence,
        *sivir_qa,
        sivir_imagegen_audit,
        *kled_outputs,
        *xayah_outputs,
        *urgot_outputs,
        *yone_outputs,
        *champion_fullbody_portraits,
        *orianna_briar_hd_surface_qa,
        *legacy_battle_actor_scale_qa,
        *([manifest] if manifest else []),
    ]:
        print(path.relative_to(MOD_ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
