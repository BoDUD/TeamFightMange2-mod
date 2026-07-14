#!/usr/bin/env python3
"""Pack the approved ImageGen Urgot art and W contract into TFM2 resources.

The native DLL still owns Urgot's stateful checks, but this builder also owns
the data-driven W pulse tree so a later visual rebuild cannot silently restore
the broken same-tick marker gate. Official champion 008 uses the ``demon``
actor contract, so every original tag, frame count and duration is copied
verbatim. Native Demon rectangles are deliberately replaced with a stable HD
frame contract; their narrow normal-form boxes reduce Urgot to a 25px blob. A
six-frame ``skill2`` body-only cast is appended for E.
"""

from __future__ import annotations

import hashlib
import json
import struct
import zlib
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from PIL import Image, ImageEnhance, ImageFilter


MOD_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = MOD_ROOT / "source"
IMAGEGEN_ROOT = SOURCE_ROOT / "imagegen"
PROCESSED_ROOT = SOURCE_ROOT / "processed"
NATIVE_CONTRACT_PATH = SOURCE_ROOT / "native" / "demon_actor_contract.json"

ACTOR_SOURCE = PROCESSED_ROOT / "urgot_actor_contact_v1_alpha.png"
RUN_SOURCE = PROCESSED_ROOT / "urgot_run_contact_v1_alpha.png"
VFX_SOURCE = PROCESSED_ROOT / "urgot_combat_vfx_v2_alpha.png"
E_VFX_SOURCE = PROCESSED_ROOT / "urgot_vfx_contact_v1_alpha.png"
ICON_SOURCE = IMAGEGEN_ROOT / "urgot_icons_v1.png"
SPLASH_SOURCE = IMAGEGEN_ROOT / "bp_splash" / "demon.png"

ACTOR_DIR = MOD_ROOT / "aseprite_resources" / "champions"
EFFECT_DIR = MOD_ROOT / "aseprite_resources" / "effects"
ICON_DIR = MOD_ROOT / "icons"
SPLASH_DIR = MOD_ROOT / "BanPickIllust"
FULLBODY_DIR = MOD_ROOT / "ui" / "champion_fullbody"
PORTRAIT_DIR = MOD_ROOT / "ui" / "champion_portrait"
QA_DIR = MOD_ROOT / "qa"
DATA_PATH = MOD_ROOT / "champion" / "demon.data_champion"

ACTOR_FRAME_SIZE = (80, 64)
ACTOR_VISIBLE_HEIGHT = 46
# The native Demon idle frame is 39-43px tall and places its feet roughly
# 21px below the frame centre.  Keep Urgot's 80x64 wide-body canvas, but use
# the same vertical foot offset so the battle HP/name plate stays below all
# six legs instead of cutting through them.
ACTOR_BASELINE = 53
SKILL2_DURATION = 0.060000002
GRID_NAME_BAND_Y = 96
GRID_ALPHA_BOTTOM = 86


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(
        (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    )


def _png_chunk(kind: bytes, data: bytes) -> bytes:
    return (
        struct.pack(">I", len(data))
        + kind
        + data
        + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
    )


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
    """Write canonical RGBA PNG bytes independent of Pillow/zlib version."""

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
    bbox = image.getchannel("A").getbbox()
    if bbox is None:
        raise ValueError("Urgot source cell has no visible pixels")
    return bbox


def keep_components(image: Image.Image, min_pixels: int = 5) -> Image.Image:
    """Remove only isolated matte flecks; keep bolts, chains and muzzle sparks."""

    rgba = hard_alpha(image)
    alpha = rgba.getchannel("A")
    remaining = {
        (x, y)
        for y in range(rgba.height)
        for x in range(rgba.width)
        if alpha.getpixel((x, y)) == 255
    }
    kept: set[tuple[int, int]] = set()
    while remaining:
        seed = remaining.pop()
        component = {seed}
        stack = [seed]
        while stack:
            x, y = stack.pop()
            for neighbor in (
                (x - 1, y),
                (x + 1, y),
                (x, y - 1),
                (x, y + 1),
                (x - 1, y - 1),
                (x + 1, y - 1),
                (x - 1, y + 1),
                (x + 1, y + 1),
            ):
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


def isolate_warm_shot(image: Image.Image, *, outline_px: int = 2) -> Image.Image:
    """Keep one compact orange cannon burst without the source's cyan W ring.

    The approved W contact sheet combines the gun, a large cyan stabiliser ring
    and several orange rounds in the same cells.  Runtime muzzle effects follow
    the caster, so keeping that ring makes every 20-tick shot look like a giant
    persistent shield around Urgot.  Seed a mask only from warm shot pixels,
    then expand it slightly to retain their dark mechanical outline and white
    cores.  This preserves the generated source art without carrying the ring.
    """

    rgba = image.convert("RGBA")
    source_alpha = rgba.getchannel("A")
    warm_mask = Image.new("L", rgba.size, 0)
    mask_pixels = warm_mask.load()
    for y in range(rgba.height):
        for x in range(rgba.width):
            red, green, blue, alpha = rgba.getpixel((x, y))
            if alpha < 48:
                continue
            is_orange = red >= 112 and red >= green * 1.18 and red >= blue * 1.45
            is_hot_core = red >= 205 and green >= 125 and blue <= 175
            if is_orange or is_hot_core:
                mask_pixels[x, y] = 255

    if outline_px:
        warm_mask = warm_mask.filter(ImageFilter.MaxFilter(outline_px * 2 + 1))
    output = Image.new("RGBA", rgba.size, (0, 0, 0, 0))
    output_pixels = output.load()
    mask_pixels = warm_mask.load()
    alpha_pixels = source_alpha.load()
    for y in range(rgba.height):
        for x in range(rgba.width):
            if mask_pixels[x, y] and alpha_pixels[x, y]:
                output_pixels[x, y] = rgba.getpixel((x, y))
    return keep_components(output, min_pixels=3)


def palette_finish(image: Image.Image, colors: int = 96) -> Image.Image:
    opaque = hard_alpha(image)
    quantized = opaque.quantize(
        colors=colors, method=Image.Quantize.FASTOCTREE
    ).convert("RGBA")
    quantized.putalpha(opaque.getchannel("A"))
    return hard_alpha(quantized, 128)


def source_subject(source: Image.Image, *, min_pixels: int = 5) -> Image.Image:
    cleaned = keep_components(source, min_pixels=min_pixels)
    return cleaned.crop(alpha_bbox(cleaned))


def fit_subject(
    source: Image.Image,
    canvas_size: tuple[int, int],
    *,
    padding: int = 1,
    desired_width: int | None = None,
    desired_height: int | None = None,
    baseline: int | None = None,
    colors: int = 96,
) -> Image.Image:
    """Uniformly scale one subject; x-only/y-only compression is forbidden."""

    subject = source_subject(source)
    max_width = max(1, canvas_size[0] - padding * 2)
    max_height = max(1, canvas_size[1] - padding * 2)
    if desired_width is not None:
        max_width = min(max_width, desired_width)
    if desired_height is not None:
        max_height = min(max_height, desired_height)
    scale = min(max_width / subject.width, max_height / subject.height)
    size = (
        max(1, round(subject.width * scale)),
        max(1, round(subject.height * scale)),
    )
    resized = subject.resize(size, Image.Resampling.LANCZOS)
    resized = palette_finish(resized, colors=colors)
    resized = keep_components(resized, min_pixels=2)
    output = Image.new("RGBA", canvas_size, (0, 0, 0, 0))
    x = (canvas_size[0] - resized.width) // 2
    exclusive_bottom = baseline if baseline is not None else canvas_size[1] - padding
    y = max(padding, min(canvas_size[1] - padding - resized.height, exclusive_bottom - resized.height))
    output.alpha_composite(resized, (x, y))
    return output


def _contract() -> dict[str, Any]:
    return json.loads(NATIVE_CONTRACT_PATH.read_text(encoding="utf-8"))["anims"]


def _actor_frame(source: Image.Image, width: int, height: int) -> Image.Image:
    # Urgot's accepted model is intentionally wide.  An 80x64 action frame
    # preserves all six legs at 46px visible height without x-only squeezing.
    return fit_subject(
        source,
        (width, height),
        padding=2,
        desired_width=76,
        desired_height=ACTOR_VISIBLE_HEIGHT,
        baseline=ACTOR_BASELINE,
        colors=96,
    )


def _rotate_pose(source: Image.Image, degrees: float) -> Image.Image:
    subject = source_subject(source)
    return subject.rotate(
        degrees, resample=Image.Resampling.BICUBIC, expand=True, fillcolor=(0, 0, 0, 0)
    )


def build_actor() -> tuple[Path, Path, list[Image.Image]]:
    actor_cells = split_grid(Image.open(ACTOR_SOURCE).convert("RGBA"), 4, 3)
    run_cells = split_grid(Image.open(RUN_SOURCE).convert("RGBA"), 3, 3)
    native = _contract()

    source_map: dict[str, list[Image.Image | None]] = {
        "normal": [actor_cells[0]],
        "archfiend_base": [actor_cells[0]],
        "idle": actor_cells[0:4],
        "archfiend_idle": [actor_cells[index] for index in (0, 1, 2, 3, 2, 1, 0)],
        "run": run_cells[:8],
        "archfiend_run": run_cells[:6],
        "attack": [actor_cells[index] for index in (4, 5, 6, 6, 5, 7)],
        "archfiend_attack": [actor_cells[index] for index in (4, 5, 6, 6, 5, 7)],
        # W occupies the skill/skill1 engine slot. Use firing poses here;
        # previously these were accidentally assigned to skill2, which made
        # W look like a neutral idle cycle even when its projectiles fired.
        "skill1": [actor_cells[index] for index in (4, 5, 6, 5, 6, 7)],
        "archfiend_skill1": [actor_cells[index] for index in (4, 5, 6, 5, 6, 7)],
        "hit": [actor_cells[3]],
        "archfiend_hit": [actor_cells[3]],
        # R has a distinct heavy launch pose; chain/pull/execute stay separate.
        "ult": [actor_cells[index] for index in (4, 10, 11, 10, 7)],
        "archfiend_ult": [actor_cells[index] for index in (4, 10, 11, 10, 7)],
        "transform": [
            actor_cells[index]
            for index in (0, 1, 2, 3, 8, 1, 2, 3, 2, 1, 0)
        ],
        "dead": [
            _rotate_pose(actor_cells[0], degrees)
            for degrees in (0, -8, -16, -25, -34, -43, -52, -61, -70)
        ]
        + [None],
    }

    total_native_frames = sum(len(spec["frames"]) for spec in native.values())
    total_frames = total_native_frames + 6
    sheet = Image.new(
        "RGBA", (ACTOR_FRAME_SIZE[0] * total_frames, ACTOR_FRAME_SIZE[1]), (0, 0, 0, 0)
    )
    representative: list[Image.Image] = []
    output_anims: dict[str, Any] = {}
    cursor = 0
    for tag, spec in native.items():
        sources = source_map[tag]
        frames = spec["frames"]
        if len(sources) != len(frames):
            raise ValueError(f"{tag}: {len(sources)} sources for {len(frames)} frames")
        packed_rows: list[dict[str, Any]] = []
        for source, row in zip(sources, frames, strict=True):
            x, y = cursor * ACTOR_FRAME_SIZE[0], 0
            width, height = ACTOR_FRAME_SIZE
            if source is None:
                frame = Image.new("RGBA", (width, height), (0, 0, 0, 0))
            else:
                frame = _actor_frame(source, width, height)
                representative.append(frame)
            sheet.alpha_composite(frame, (x, y))
            packed_rows.append(
                {
                    "duration": row["duration"],
                    "data": {"x": x, "y": y, "w": width, "h": height},
                }
            )
            cursor += 1
        output_anims[tag] = {"frames": packed_rows}

    # E occupies the skill2 slot; its shield/dash/flip read is supplied by the
    # separate urgot_e_disdain effect while the actor keeps a stable body.
    skill2_sources = [actor_cells[index] for index in (0, 1, 2, 3, 1, 0)]
    skill2_frames: list[dict[str, Any]] = []
    for source in skill2_sources:
        x, y = cursor * ACTOR_FRAME_SIZE[0], 0
        frame = _actor_frame(source, *ACTOR_FRAME_SIZE)
        sheet.alpha_composite(frame, (x, y))
        representative.append(frame)
        skill2_frames.append(
            {
                "duration": SKILL2_DURATION,
                "data": {
                    "x": x,
                    "y": y,
                    "w": ACTOR_FRAME_SIZE[0],
                    "h": ACTOR_FRAME_SIZE[1],
                },
            }
        )
        cursor += 1

    output_anims["skill2"] = {"frames": skill2_frames}
    sheet_path = ACTOR_DIR / "demon#sheet.png"
    anim_path = ACTOR_DIR / "demon#anim.fanim"
    save_png(sheet_path, sheet)
    write_json(anim_path, {"anims": output_anims})
    return sheet_path, anim_path, representative


def _vary_effect(
    source: Image.Image,
    canvas_size: tuple[int, int],
    *,
    scale_factor: float,
    opacity: float,
    tint: tuple[float, float, float] | None = None,
) -> Image.Image:
    subject = source_subject(source, min_pixels=2)
    if tint is not None:
        pixels = subject.load()
        for y in range(subject.height):
            for x in range(subject.width):
                red, green, blue, alpha = pixels[x, y]
                if alpha:
                    pixels[x, y] = (
                        min(255, round(red * tint[0])),
                        min(255, round(green * tint[1])),
                        min(255, round(blue * tint[2])),
                        alpha,
                    )
    max_width = max(1, round((canvas_size[0] - 8) * scale_factor))
    max_height = max(1, round((canvas_size[1] - 8) * scale_factor))
    scale = min(max_width / subject.width, max_height / subject.height)
    resized = subject.resize(
        (
            max(1, round(subject.width * scale)),
            max(1, round(subject.height * scale)),
        ),
        Image.Resampling.LANCZOS,
    )
    resized = palette_finish(resized, colors=96)
    # Keep VFX alpha hard.  Scale progression supplies the fade-in/out read
    # without semi-transparent corner/halo residue in the game renderer.
    alpha = resized.getchannel("A").point(lambda value: 255 if value else 0)
    resized.putalpha(alpha)
    output = Image.new("RGBA", canvas_size, (0, 0, 0, 0))
    output.alpha_composite(
        resized,
        ((canvas_size[0] - resized.width) // 2, (canvas_size[1] - resized.height) // 2),
    )
    return output


def _build_effect(
    resource: str,
    frame_size: tuple[int, int],
    tag_sources: dict[
        str, tuple[Image.Image, tuple[float, float, float] | None, float]
    ],
) -> tuple[Path, Path, dict[str, list[Image.Image]]]:
    variants = ((0.74, 0.68), (0.9, 1.0), (1.0, 1.0), (0.86, 0.86))
    total_frames = len(tag_sources) * len(variants)
    sheet = Image.new(
        "RGBA", (frame_size[0] * total_frames, frame_size[1]), (0, 0, 0, 0)
    )
    anims: dict[str, Any] = {}
    built: dict[str, list[Image.Image]] = {}
    cursor = 0
    for tag, (source, tint, base_scale) in tag_sources.items():
        tag_frames: list[dict[str, Any]] = []
        built[tag] = []
        for frame_index, (scale_factor, opacity) in enumerate(variants):
            frame = _vary_effect(
                source,
                frame_size,
                scale_factor=scale_factor * base_scale,
                opacity=opacity,
                tint=tint,
            )
            x = cursor * frame_size[0]
            sheet.alpha_composite(frame, (x, 0))
            built[tag].append(frame)
            tag_frames.append(
                {
                    "duration": (0.045, 0.055, 0.07, 0.09)[frame_index],
                    "data": {
                        "x": x,
                        "y": 0,
                        "w": frame_size[0],
                        "h": frame_size[1],
                    },
                }
            )
            cursor += 1
        anims[tag] = {"frames": tag_frames}
    sheet_path = EFFECT_DIR / f"{resource}#sheet.png"
    anim_path = EFFECT_DIR / f"{resource}#anim.fanim"
    save_png(sheet_path, sheet)
    write_json(anim_path, {"anims": anims})
    return sheet_path, anim_path, built


def build_effects() -> tuple[list[Path], dict[str, dict[str, list[Image.Image]]]]:
    cells = split_grid(Image.open(VFX_SOURCE).convert("RGBA"), 4, 3)
    e_cells = split_grid(Image.open(E_VFX_SOURCE).convert("RGBA"), 4, 3)
    # V2 uses three explicit chronological rows: basic attack, sustained W,
    # and R.  Crop weapon-context pixels out of moving projectiles so only the
    # caster-follow muzzle/purge layer ever overlaps Urgot's own cannon.
    attack_muzzle = cells[0].crop((205, 55, 362, 305))
    attack_projectile = cells[1]
    attack_impact = cells[2]
    # Purge is a stream of compact rounds, not a persistent body aura.  The
    # engine cannot anchor an independent caster effect to the moving weapon
    # muzzle, so bake the firing motion into the actor and render only one
    # travelling round plus a compact contact spark here.
    w_projectile = isolate_warm_shot(cells[6].crop((245, 138, 307, 168)), outline_px=1)
    w_impact = cells[2].crop((102, 112, 316, 320))
    specs: list[
        tuple[
            str,
            tuple[int, int],
            dict[
                str,
                tuple[Image.Image, tuple[float, float, float] | None, float],
            ],
        ]
    ] = [
        (
            "urgot_attack",
            (96, 64),
            {
                "muzzle": (attack_muzzle, None, 0.72),
                "projectile": (attack_projectile, None, 0.88),
                "impact": (attack_impact, None, 0.72),
            },
        ),
        (
            "urgot_w_cannon",
            (64, 40),
            {
                "projectile": (w_projectile, None, 0.46),
                "impact": (w_impact, None, 0.48),
            },
        ),
        (
            "urgot_e_disdain",
            (96, 96),
            {
                "shield": (e_cells[4], None, 0.88),
                "dash": (e_cells[5], None, 0.94),
                "impact": (e_cells[6], None, 0.9),
                "flip": (e_cells[7], None, 0.88),
            },
        ),
        (
            "urgot_r_chain",
            (128, 96),
            {
                "launch": (cells[8], None, 0.70),
                "projectile": (cells[8], None, 0.92),
                "latch": (cells[9], None, 0.94),
                "pull": (cells[10], None, 0.96),
            },
        ),
        (
            "urgot_r_execute",
            (128, 128),
            {
                "execute": (cells[11], None, 0.94),
                "fear": (cells[11], (1.55, 0.42, 0.48), 0.98),
            },
        ),
    ]
    output_paths: list[Path] = []
    built: dict[str, dict[str, list[Image.Image]]] = {}
    for resource, frame_size, tags in specs:
        sheet_path, anim_path, frames = _build_effect(resource, frame_size, tags)
        output_paths.extend((sheet_path, anim_path))
        built[resource] = frames
    return output_paths, built


def _cover(source: Image.Image, size: tuple[int, int]) -> Image.Image:
    scale = max(size[0] / source.width, size[1] / source.height)
    resized = source.resize(
        (round(source.width * scale), round(source.height * scale)),
        Image.Resampling.LANCZOS,
    )
    left = (resized.width - size[0]) // 2
    top = (resized.height - size[1]) // 2
    return resized.crop((left, top, left + size[0], top + size[1])).convert("RGBA")


def build_icons() -> list[Path]:
    cells = split_grid(Image.open(ICON_SOURCE).convert("RGBA"), 3, 1)
    outputs: list[Path] = []
    for name, cell in zip(("urgot_w", "urgot_e", "urgot_r"), cells, strict=True):
        icon = _cover(cell, (64, 64))
        icon = ImageEnhance.Contrast(icon).enhance(1.06)
        icon = palette_finish(icon, colors=128)
        path = ICON_DIR / f"{name}.png"
        save_png(path, icon)
        outputs.append(path)
    return outputs


def build_gameplay_data() -> Path:
    """Rebuild W as one short, target-bound, data-only Purge burst.

    Four different multishot implementations froze real matches: projectile
    callbacks near 00:30, AddCasted/Bleed near 02:22, linear projectiles near
    00:43, and the native entity-scan implementation at first contact (00:25).
    The last failure emitted three engine ``Option::unwrap(None)`` panics.

    This stability baseline intentionally compresses the twelve intended shots
    into one ordinary data ``Attack``. It has no Delayed/Native callback, no
    projectile, no actor/body overlay and no view effect. The short,
    non-cancelable action also prevents queued callbacks or AI re-entry from
    outliving the original target.
    """

    data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    data["skill"] = {
        # The former skill1 action automatically drew the oversized machine-gun
        # pose over Urgot's body. Reuse the compact basic-fire body contract and
        # do not restart any animation from the delayed pulse effects.
        "action_name": "attack",
        "description": "#asset/base/text/champion?description.demon.skill",
        "duration": 16,
        "cooltime": 600,
        "start_timing": 1,
        "cancelable": False,
        "range": 60000,
        "growth_range": 0,
        "casting_type": "Targeting",
        "casting_target": "EnemyWithoutTower",
        "attack_type": "Skill",
        "can_use_with_move": False,
        "effect": {
            "type": "Combine",
            "effects": [
                {"type": "Sfx", "name": "lol_urgot_w_cast"},
                {
                    "type": "AddCasterBuff",
                    "buff_state": {
                        "name": "lol_urgot_w_purge",
                        "duration": {"Time": {"tick": 240}},
                        "move_speed_mult": -12,
                        "defence": 20,
                        "magic_resistance": 10,
                    },
                },
                {"type": "Sfx", "name": "lol_urgot_w_shot"},
                {"type": "Attack", "damage": 96, "attack_ratio": 240},
            ],
        },
    }

    # E must finish its displacement through engine-owned data effects.  The
    # old order applied a native Stun before Knockback, which could freeze the
    # victim in place and turn Disdain into a caster-only cross-through.  The
    # proven Kled/Briar collision contract resolves Knockback first and keeps
    # the victim disabled with Airborne while it travels.  Combined with
    # RushMoveToBack, this leaves Urgot beyond the target and throws the target
    # away from Urgot toward the side from which he charged.
    e_rushes = [
        effect
        for effect in data["skill2"]["effect"]["effects"]
        if effect.get("type") == "RushMoveToBack"
    ]
    if len(e_rushes) != 1:
        raise ValueError("Urgot E must contain exactly one RushMoveToBack")
    e_rushes[0]["applied_effects"] = [
        {"type": "Attack", "damage": 70, "attack_ratio": 90},
        {"type": "Knockback", "speed": 2600, "tick": 8},
        {"type": "Airborne", "duration": 60},
        {"type": "ViewEffect", "name": "lol_urgot_e_flip_visual"},
        {"type": "TargetSfx", "name": "lol_urgot_e_hit"},
    ]

    # W now has no rendered projectile or impact. Remove both runtime bindings
    # so stale data cannot resurrect the rejected cannon/body overlay even
    # though the historical source sheet remains available for QA evidence.
    data["view_projectiles"] = [
        binding
        for binding in data.get("view_projectiles", [])
        if binding.get("name") != "lol_urgot_w_cannon_projectile"
    ]
    data["view_effects"] = [
        binding
        for binding in data.get("view_effects", [])
        if binding.get("name") != "lol_urgot_w_impact_visual"
    ]

    # Removed experimental channel markers/native cleanup must not survive in R.
    data["ult"]["effect"]["effects"] = [
        effect
        for effect in data["ult"]["effect"]["effects"]
        if not (
            (
                effect.get("type") == "RemoveCasterBuff"
                and effect.get("name") == "lol_urgot_w_shot_ready"
            )
            or (
                effect.get("type") == "Native"
                and effect.get("effect_ref") == "lol_urgot_w_cancel_native"
            )
        )
    ]
    write_json(DATA_PATH, data)
    return DATA_PATH


def _focus_crop(
    source: Image.Image,
    *,
    left_ratio: float,
    top_ratio: float,
    right_ratio: float,
    bottom_ratio: float,
) -> Image.Image:
    subject = source_subject(source)
    return subject.crop(
        (
            round(subject.width * left_ratio),
            round(subject.height * top_ratio),
            round(subject.width * right_ratio),
            round(subject.height * bottom_ratio),
        )
    )


def build_presentation() -> list[Path]:
    source = split_grid(Image.open(ACTOR_SOURCE).convert("RGBA"), 4, 3)[0]
    subject = source_subject(source)

    splash_path = SPLASH_DIR / "demon.png"
    save_png(splash_path, _cover(Image.open(SPLASH_SOURCE).convert("RGBA"), (1420, 860)))

    fullbody_path = FULLBODY_DIR / "demon.png"
    save_png(
        fullbody_path,
        fit_subject(subject, (64, 64), padding=3, desired_width=56, desired_height=58, baseline=60),
    )

    compact_source = _focus_crop(
        source, left_ratio=0.34, top_ratio=0.01, right_ratio=0.66, bottom_ratio=0.39
    )
    compact_path = PORTRAIT_DIR / "demon_compact.png"
    save_png(
        compact_path,
        fit_subject(
            compact_source,
            (64, 64),
            padding=4,
            desired_width=52,
            desired_height=50,
            baseline=58,
        ),
    )

    scoreboard_source = _focus_crop(
        # The 14-38px match-scoreboard route is smaller than the 39-52px
        # battle-sidebar route, but it must retain the same readable head and
        # shoulders composition.  Keep this source focus equal to compact;
        # only the dedicated scoreboard output below is allowed to scale it.
        source, left_ratio=0.34, top_ratio=0.01, right_ratio=0.66, bottom_ratio=0.39
    )
    scoreboard_path = PORTRAIT_DIR / "demon_scoreboard.png"
    save_png(
        scoreboard_path,
        fit_subject(
            scoreboard_source,
            (64, 64),
            padding=4,
            desired_width=52,
            desired_height=50,
            baseline=58,
        ),
    )

    grid_path = PORTRAIT_DIR / "demon_grid.png"
    save_png(
        grid_path,
        fit_subject(
            subject,
            (90, 122),
            padding=4,
            desired_width=82,
            desired_height=80,
            baseline=GRID_ALPHA_BOTTOM,
        ),
    )
    return [splash_path, fullbody_path, compact_path, scoreboard_path, grid_path]


def _contact_sheet(
    frames: Iterable[Image.Image],
    *,
    cell_size: tuple[int, int],
    columns: int,
    background: tuple[int, int, int, int] = (13, 17, 25, 255),
) -> Image.Image:
    frames = list(frames)
    rows = max(1, (len(frames) + columns - 1) // columns)
    output = Image.new(
        "RGBA", (cell_size[0] * columns, cell_size[1] * rows), background
    )
    for index, frame in enumerate(frames):
        scale = min(
            (cell_size[0] - 8) / frame.width, (cell_size[1] - 8) / frame.height
        )
        resized = frame.resize(
            (max(1, round(frame.width * scale)), max(1, round(frame.height * scale))),
            Image.Resampling.NEAREST,
        )
        x = index % columns * cell_size[0] + (cell_size[0] - resized.width) // 2
        y = index // columns * cell_size[1] + (cell_size[1] - resized.height) // 2
        output.alpha_composite(resized, (x, y))
    return output


def _bbox_or_none(image: Image.Image) -> list[int] | None:
    bbox = image.getchannel("A").getbbox()
    return list(bbox) if bbox else None


def build_qa(
    actor_frames: list[Image.Image], effect_frames: dict[str, dict[str, list[Image.Image]]]
) -> list[Path]:
    actor_contact = QA_DIR / "urgot_actor_contact_final.png"
    save_png(actor_contact, _contact_sheet(actor_frames[:32], cell_size=(96, 96), columns=8))

    flattened_effects = [
        frame
        for resource in effect_frames.values()
        for tag in resource.values()
        for frame in tag
    ]
    vfx_contact = QA_DIR / "urgot_vfx_contact_final.png"
    save_png(vfx_contact, _contact_sheet(flattened_effects, cell_size=(144, 136), columns=8))

    icon_contact = QA_DIR / "urgot_skill_icons_final.png"
    icons = [Image.open(ICON_DIR / f"urgot_{slot}.png").convert("RGBA") for slot in "wer"]
    save_png(icon_contact, _contact_sheet(icons, cell_size=(80, 80), columns=3))

    portrait_contact = QA_DIR / "urgot_portrait_surface_final.png"
    portrait_contact_specs = [
        ("encyclopedia", FULLBODY_DIR / "demon.png", 64),
        ("compact_40", PORTRAIT_DIR / "demon_compact.png", 40),
        ("compact_46", PORTRAIT_DIR / "demon_compact.png", 46),
        ("scoreboard_18", PORTRAIT_DIR / "demon_scoreboard.png", 18),
        ("scoreboard_26", PORTRAIT_DIR / "demon_scoreboard.png", 26),
        ("scoreboard_30", PORTRAIT_DIR / "demon_scoreboard.png", 30),
        ("scoreboard_34", PORTRAIT_DIR / "demon_scoreboard.png", 34),
        ("bp_grid", PORTRAIT_DIR / "demon_grid.png", 90),
    ]
    portraits = [
        Image.open(path)
        .convert("RGBA")
        .resize((size, size if name != "bp_grid" else 122), Image.Resampling.NEAREST)
        for name, path, size in portrait_contact_specs
    ]
    save_png(portrait_contact, _contact_sheet(portraits, cell_size=(112, 144), columns=7))

    native = _contract()
    built_anim = json.loads(
        (ACTOR_DIR / "demon#anim.fanim").read_text(encoding="utf-8")
    )["anims"]
    portrait_paths = {
        "encyclopedia": FULLBODY_DIR / "demon.png",
        "compact": PORTRAIT_DIR / "demon_compact.png",
        "scoreboard": PORTRAIT_DIR / "demon_scoreboard.png",
        "grid": PORTRAIT_DIR / "demon_grid.png",
    }
    portrait_runtime_metrics: dict[str, dict[str, Any]] = {}
    for (name, path, _size), image in zip(portrait_contact_specs, portraits):
        if name not in {"compact_40", "scoreboard_30"}:
            continue
        bbox = _bbox_or_none(image)
        if bbox is None:
            raise ValueError(f"Urgot {name} runtime portrait is empty")
        portrait_runtime_metrics[name] = {
            "asset": str(path.relative_to(MOD_ROOT)).replace("\\", "/"),
            "runtime_size": list(image.size),
            "alpha_bbox": bbox,
            "subject_size": [bbox[2] - bbox[0], bbox[3] - bbox[1]],
        }
    qa = {
        "schema_version": 1,
        "champion": "Urgot",
        "native_id": "demon",
        "source_route": "approved ImageGen actor/run/VFX-v2/icon/splash set",
        "sources": {
            str(path.relative_to(MOD_ROOT)).replace("\\", "/"): sha256(path)
            for path in (
                ACTOR_SOURCE,
                RUN_SOURCE,
                VFX_SOURCE,
                E_VFX_SOURCE,
                ICON_SOURCE,
                SPLASH_SOURCE,
            )
        },
        "actor_contract": {
            "original_tag_order": list(native),
            "output_tag_order": list(built_anim),
            "original_frame_counts": {
                tag: len(value["frames"]) for tag, value in native.items()
            },
            "skill2_appended_frames": len(built_anim["skill2"]["frames"]),
            "native_rectangles_repacked_for_hd": True,
            "frame_size": list(ACTOR_FRAME_SIZE),
            "visible_body_height_px": ACTOR_VISIBLE_HEIGHT,
            "foot_baseline_exclusive_y": ACTOR_BASELINE,
            "uniform_xy_scale": True,
            "body_effects_separated": True,
        },
        "effects": {
            resource: {tag: len(frames) for tag, frames in tags.items()}
            for resource, tags in effect_frames.items()
        },
        "surfaces": {
            name: {
                "path": str(path.relative_to(MOD_ROOT)).replace("\\", "/"),
                "dimensions": list(Image.open(path).size),
                "alpha_bbox": _bbox_or_none(Image.open(path).convert("RGBA")),
                "sha256": sha256(path),
            }
            for name, path in portrait_paths.items()
        },
        "portrait_focus": {
            "compact": {"left": 0.34, "top": 0.01, "right": 0.66, "bottom": 0.39},
            "scoreboard": {"left": 0.34, "top": 0.01, "right": 0.66, "bottom": 0.39},
        },
        "portrait_surface_routing": {
            "screenshot_1_match_scoreboard": {
                "runtime_square_px": [14, 38],
                "asset": "ui/champion_portrait/demon_scoreboard.png",
                "crop_contract": "same_head_shoulders_focus_as_battle_sidebar",
            },
            "screenshot_2_battle_sidebar": {
                "runtime_square_px": [39, 52],
                "asset": "ui/champion_portrait/demon_compact.png",
                "preserved_sha256": sha256(PORTRAIT_DIR / "demon_compact.png"),
            },
        },
        "portrait_contact_actual_sizes": {
            name: list(image.size)
            for (name, _path, _size), image in zip(portrait_contact_specs, portraits)
        },
        "portrait_runtime_metrics": portrait_runtime_metrics,
        "bp_grid": {
            "name_band_y": GRID_NAME_BAND_Y,
            "max_alpha_bottom": GRID_ALPHA_BOTTOM,
            "clearance": GRID_NAME_BAND_Y - GRID_ALPHA_BOTTOM,
        },
    }
    qa_path = QA_DIR / "urgot_visual_qa.json"
    write_json(qa_path, qa)
    return [actor_contact, vfx_contact, icon_contact, portrait_contact, qa_path]


def build_all() -> list[Path]:
    required = (
        ACTOR_SOURCE,
        RUN_SOURCE,
        VFX_SOURCE,
        ICON_SOURCE,
        SPLASH_SOURCE,
        NATIVE_CONTRACT_PATH,
        DATA_PATH,
    )
    missing = [path for path in required if not path.is_file()]
    if missing:
        raise FileNotFoundError("missing Urgot source(s): " + ", ".join(map(str, missing)))
    actor_sheet, actor_anim, actor_frames = build_actor()
    gameplay_data = build_gameplay_data()
    effect_paths, effect_frames = build_effects()
    icon_paths = build_icons()
    presentation_paths = build_presentation()
    qa_paths = build_qa(actor_frames, effect_frames)
    return [
        actor_sheet,
        actor_anim,
        gameplay_data,
        *effect_paths,
        *icon_paths,
        *presentation_paths,
        *qa_paths,
    ]


if __name__ == "__main__":
    paths = build_all()
    print(f"built {len(paths)} Urgot visual resources")
    for path in paths:
        print(path.relative_to(MOD_ROOT))
