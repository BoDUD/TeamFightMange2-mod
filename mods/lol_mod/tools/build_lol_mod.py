#!/usr/bin/env python3
"""Build Shen and Lucian runtime assets from accepted image-gen sources."""

from __future__ import annotations

import argparse
import binascii
import hashlib
import json
from pathlib import Path
import struct

from PIL import Image, ImageDraw


MOD_ROOT = Path(__file__).resolve().parents[1]
SOURCE = MOD_ROOT / "source" / "processed"
ACTOR_DIR = MOD_ROOT / "aseprite_resources" / "champions"
EFFECT_DIR = MOD_ROOT / "aseprite_resources" / "effects"
ICON_DIR = MOD_ROOT / "icons"
UI_ASEPRITE_DIR = MOD_ROOT / "aseprite_resources" / "UI_aseprite"
SETTING_DIR = MOD_ROOT / "setting"
QA_DIR = MOD_ROOT / "qa"
BASE_SOURCE = MOD_ROOT / "source" / "base"

ACTOR_SOURCE = SOURCE / "shen_actor_contact_alpha.png"
RUN_SOURCE = SOURCE / "shen_run_contact_alpha.png"
ICON_SOURCES = {
    "shen_skill.png": SOURCE / "shen_q_icon_source_alpha.png",
    "shen_skill2.png": SOURCE / "shen_w_icon_source_alpha.png",
    "shen_ult.png": SOURCE / "shen_r_icon_source_alpha.png",
}
VFX_SOURCES = {
    "shen_q": (SOURCE / "shen_q_vfx_contact_alpha.png", 4, 2, (64, 64), (58, 48)),
    "shen_w": (SOURCE / "shen_w_vfx_contact_alpha.png", 3, 2, (112, 64), (104, 30)),
    "shen_r": (SOURCE / "shen_r_vfx_contact_alpha.png", 4, 2, (112, 112), (100, 100)),
}

LUCIAN_ACTOR_SOURCE = SOURCE / "lucian_actor_contact_alpha.png"
LUCIAN_RUN_SOURCE = SOURCE / "lucian_run_contact_alpha.png"
LUCIAN_ICON_SOURCES = {
    "lucian_skill.png": SOURCE / "lucian_q_icon_source_alpha.png",
    "lucian_skill2.png": SOURCE / "lucian_e_icon_source_alpha.png",
    "lucian_ult.png": SOURCE / "lucian_r_icon_source_alpha.png",
}
LUCIAN_VFX_SOURCES = {
    "lucian_q": (SOURCE / "lucian_q_vfx_contact_alpha.png", 4, 2, (96, 48), (84, 24)),
    "lucian_e": (SOURCE / "lucian_e_vfx_contact_alpha.png", 4, 2, (112, 64), (100, 42)),
    "lucian_r": (SOURCE / "lucian_r_vfx_contact_alpha.png", 4, 2, (64, 32), (48, 18)),
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


def build_actor() -> tuple[Path, Path, list[Image.Image]]:
    source = Image.open(ACTOR_SOURCE).convert("RGBA")
    cells = split_grid(source, 4, 3)
    base_frames: list[Image.Image] = []
    # A proven 64x64 additive actor (Galio) occupies about 35 pixels in idle.
    # Keep Shen in that same battle/UI scale class instead of letting the large
    # image-gen source fill the full frame and get cropped in compact cards.
    actor_scale = 0.145
    for cell, keep_box in zip(cells, ACTOR_KEEP_BOXES, strict=True):
        masked = Image.new("RGBA", cell.size, (0, 0, 0, 0))
        kept = cell.crop(keep_box)
        masked.alpha_composite(kept, (keep_box[0], keep_box[1]))
        masked = hard_alpha(masked)
        subject = masked.crop(alpha_bbox(masked))
        resized = subject.resize(
            (max(1, round(subject.width * actor_scale)), max(1, round(subject.height * actor_scale))),
            Image.Resampling.LANCZOS,
        )
        resized = palette_finish(resized, 40)
        frame = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
        x = (64 - resized.width) // 2
        # The proven 64x64 additive contract keeps the actor's foot baseline at
        # y=45. Bottom-aligning at y=62 makes the same model sit 17 px too low in
        # encyclopedia cards, compact portraits, and the battle map.
        y = 45 - resized.height
        frame.alpha_composite(resized, (x, y))
        base_frames.append(frame)

    # The original contact sheet only supplied three broad run poses. A second
    # image-gen pass supplies nine unique gait phases so the reduced sprite keeps
    # readable left/right contacts and two real passing (cross-step) silhouettes.
    run_source = Image.open(RUN_SOURCE).convert("RGBA")
    run_frames: list[Image.Image] = []
    for cell in split_grid(run_source, 3, 3):
        cell = hard_alpha(cell)
        subject = cell.crop(alpha_bbox(cell))
        scale = min(36 / subject.height, 58 / subject.width)
        resized = subject.resize(
            (max(1, round(subject.width * scale)), max(1, round(subject.height * scale))),
            Image.Resampling.LANCZOS,
        )
        resized = palette_finish(resized, 40)
        frame = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
        frame.alpha_composite(resized, ((64 - resized.width) // 2, 45 - resized.height))
        run_frames.append(frame)

    # Runtime atlas order: two idles, nine generated run phases, then the seven
    # non-run actions from the accepted 4x3 actor source.
    frames = [base_frames[0], base_frames[1], *run_frames, *base_frames[5:12]]

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
    """Pack Lucian into the exact native Archer animation-key/frame contract."""
    source = Image.open(LUCIAN_ACTOR_SOURCE).convert("RGBA")
    base_frames: list[Image.Image] = []
    for cell in split_grid(source, 4, 3):
        cell = hard_alpha(cell)
        subject = cell.crop(alpha_bbox(cell))
        scale = min(0.124, 58 / subject.width)
        resized = subject.resize(
            (max(1, round(subject.width * scale)), max(1, round(subject.height * scale))),
            Image.Resampling.LANCZOS,
        )
        resized = palette_finish(resized, 48)
        frame = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
        frame.alpha_composite(resized, ((64 - resized.width) // 2, 45 - resized.height))
        base_frames.append(frame)

    run_frames: list[Image.Image] = []
    run_source = Image.open(LUCIAN_RUN_SOURCE).convert("RGBA")
    for cell in split_grid(run_source, 3, 3):
        cell = hard_alpha(cell)
        subject = cell.crop(alpha_bbox(cell))
        scale = min(36 / subject.height, 58 / subject.width)
        resized = subject.resize(
            (max(1, round(subject.width * scale)), max(1, round(subject.height * scale))),
            Image.Resampling.LANCZOS,
        )
        resized = palette_finish(resized, 48)
        frame = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
        frame.alpha_composite(resized, ((64 - resized.width) // 2, 45 - resized.height))
        run_frames.append(frame)

    transparent = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    r_source = Image.open(LUCIAN_VFX_SOURCES["lucian_r"][0]).convert("RGBA")
    r_projectile = fit_cell(split_grid(r_source, 4, 2)[0], (64, 64), (48, 18))

    # Source pose aliases: 0/1 idle, 2/3 right/left shot, 4 double shot,
    # 5 Q, 6/7 E, 8/9 R, 10 hit, 11 dead.
    sequences: dict[str, tuple[list[Image.Image], list[float]]] = {
        "ult_old": (
            [base_frames[index] for index in [0, 8, 8, 9, 9, 9, 9, 9, 9, 8, 0]],
            [0.080000006] * 7 + [0.1] * 4,
        ),
        "skill": (
            [base_frames[index] for index in [6, 7, 7, 4, 2, 0]],
            [0.080000006] * 6,
        ),
        "ult_end": ([base_frames[index] for index in [9, 8, 0]], [0.080000006] * 3),
        "ult_projectile": ([r_projectile], [0.080000006]),
        "hit": ([base_frames[10]], [0.1]),
        "run": (run_frames[:8], [0.080000006] * 8),
        "ult_loop": ([base_frames[9]] * 4, [0.030000001] * 4),
        "skill2": (
            [base_frames[index] for index in [0, 5, 5, 5, 5, 1, 0]],
            [0.080000006] * 7,
        ),
        "ult_pre": ([base_frames[index] for index in [0, 8, 8]], [0.080000006] * 3),
        "dead": (
            [base_frames[10], *([base_frames[11]] * 7), transparent],
            [0.1] * 4 + [0.15] * 5,
        ),
        "old_ult_buff_effect": ([base_frames[9], base_frames[9], base_frames[8], base_frames[0]], [0.1] * 4),
        "skill_attack": ([base_frames[index] for index in [4, 2, 0]], [0.080000006] * 3),
        "idle": ([base_frames[index] for index in [0, 1, 0, 1]], [0.18, 0.14, 0.14, 0.14]),
        "skill_dash": ([base_frames[index] for index in [6, 7, 7]], [0.080000006] * 3),
        "attack": ([base_frames[index] for index in [0, 2, 2, 3, 3, 0]], [0.060000002] * 6),
        "old_ult_pre": (
            [base_frames[index] for index in [0, 8, 8, 9, 9, 9, 9]],
            [0.080000006] * 7,
        ),
    }

    packed_frames: list[Image.Image] = []
    anims: dict[str, object] = {}
    for name, (sequence_frames, durations) in sequences.items():
        start = len(packed_frames)
        packed_frames.extend(sequence_frames)
        anims[name] = {
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
    sheet_path = ACTOR_DIR / "archer#sheet.png"
    anim_path = ACTOR_DIR / "archer#anim.fanim"
    save_png(sheet_path, atlas)
    write_json(anim_path, {"anims": anims})

    preview_frames = [base_frames[0], base_frames[1], *run_frames, *base_frames[2:12]]
    return sheet_path, anim_path, preview_frames


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
        if name == "shen_w":
            frames = []
            for cell in split_grid(source, columns, rows):
                cell = hard_alpha(cell)
                subject = cell.crop(alpha_bbox(cell)).resize(max_visible, Image.Resampling.LANCZOS)
                subject = palette_finish(subject)
                centered = Image.new("RGBA", frame_size, (0, 0, 0, 0))
                x = (frame_size[0] - subject.width) // 2
                y = round(44 - subject.height / 2)
                centered.alpha_composite(subject, (x, y))
                frames.append(centered)
        else:
            frames = [fit_cell(cell, frame_size, max_visible) for cell in split_grid(source, columns, rows)]
        atlas = Image.new("RGBA", (frame_size[0] * len(frames), frame_size[1]), (0, 0, 0, 0))
        for index, frame in enumerate(frames):
            atlas.alpha_composite(frame, (index * frame_size[0], 0))
        sheet = EFFECT_DIR / f"{name}#sheet.png"
        anim = EFFECT_DIR / f"{name}#anim.fanim"
        save_png(sheet, atlas)
        if name == "shen_q":
            anims = {"projectile": effect_anim(64, 64, list(range(8)), [0.06] * 8)}
        elif name == "shen_w":
            anims = {"field": effect_anim(112, 64, list(range(6)), [0.42] * 6)}
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
        for cell in split_grid(source, columns, rows):
            cell = hard_alpha(cell)
            subject = cell.crop(alpha_bbox(cell))
            scale = min(max_visible[0] / subject.width, max_visible[1] / subject.height)
            resized = subject.resize(
                (max(1, round(subject.width * scale)), max(1, round(subject.height * scale))),
                Image.Resampling.LANCZOS,
            )
            resized = palette_finish(resized, 48)
            frame = Image.new("RGBA", frame_size, (0, 0, 0, 0))
            x = (frame_size[0] - resized.width) // 2
            if name == "lucian_e":
                # Fixed y=45 actor baseline keeps the dash echo behind Lucian's
                # centered runtime model instead of pulling the composite down.
                y = 45 - resized.height
            else:
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
        tag = {"lucian_q": "projectile", "lucian_e": "dash", "lucian_r": "projectile"}[name]
        duration = {"lucian_q": 0.05, "lucian_e": 0.045, "lucian_r": 0.035}[name]
        write_json(
            anim,
            {"anims": {tag: effect_anim(frame_size[0], frame_size[1], list(range(8)), [duration] * 8)}},
        )
        outputs.extend([sheet, anim])
    return outputs


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
        "id": "lol_lucian",
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
            "description": "#asset/base/text/champion?description.lol_lucian.attack",
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
            "description": "#asset/base/text/champion?description.lol_lucian.skill",
            "duration": 24,
            "cooltime": 300,
            "start_timing": 10,
            "cancelable": True,
            "range": 65000,
            "casting_type": "Targeting",
            "casting_target": "EnemyChampion",
            "attack_type": "Skill",
            "effect": {
                "type": "Combine",
                "effects": [
                    {"type": "Sfx", "name": "lol_lucian_q_cast"},
                    {"type": "CasterAnimation", "name": "skill", "tick": 20},
                    {
                        "type": "Delayed",
                        "tick": 10,
                        "effects": [
                            {
                                "type": "LinearProjectile",
                                "penetrate": True,
                                "speed": 15000,
                                "range": 76000,
                                "name": "lol_lucian_piercing_light",
                                "shape": {"Rect": {"width": 12000, "height": 76000}},
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
                            }
                        ],
                    },
                    lucian_lightslinger_buff(),
                ],
            },
            "can_use_with_move": False,
        },
        "skill2": {
            "action_name": "skill2",
            "description": "#asset/base/text/champion?description.lol_lucian.skill2",
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
                    {"type": "CasterViewEffect", "name": "lol_lucian_dash_visual"},
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
            "description": "#asset/base/text/champion?description.lol_lucian.ult",
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
                "anim": "asset/lol_mod/aseprite_resources/effects/lucian_r",
                "tag": "projectile",
                "z": 2,
                "repeat": True,
            },
            {
                "type": "Animated",
                "name": "lol_lucian_piercing_light",
                "anim": "asset/lol_mod/aseprite_resources/effects/lucian_q",
                "tag": "projectile",
                "z": 3,
                "repeat": True,
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
        "view_effects": [
            {
                "type": "Animation",
                "name": "lol_lucian_dash_visual",
                "anim": "asset/lol_mod/aseprite_resources/effects/lucian_e",
                "tag": "dash",
                "z": 1,
                "is_follow": True,
            }
        ],
        "view_buffs": [],
    }
    path = MOD_ROOT / "champion" / "lol_lucian.data_champion"
    write_json(path, champion)
    return path


def build_qa_contacts(actor_frames: list[Image.Image], icons: list[Path]) -> list[Path]:
    QA_DIR.mkdir(parents=True, exist_ok=True)
    actor_contact = Image.new("RGBA", (6 * 128, 3 * 144), (20, 18, 28, 255))
    draw = ImageDraw.Draw(actor_contact)
    labels = [
        "idle A", "idle B", *[f"run {index}" for index in range(1, 10)],
        "attack A", "attack B", "attack C", "Q cast", "W cast", "R cast", "hit/dead",
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
    for index, (path, label) in enumerate(zip(icons, ["Q", "W", "R"], strict=True)):
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
        ("lucian_q", (96, 48), "Q beam"),
        ("lucian_e", (112, 64), "E afterimage"),
        ("lucian_r", (64, 32), "R / attack bullet"),
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


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def build_manifest() -> Path:
    runtime_roots = [
        MOD_ROOT / "mod.mod_info",
        MOD_ROOT / "mod.override_info",
        MOD_ROOT / "champion",
        MOD_ROOT / "icons",
        MOD_ROOT / "aseprite_resources",
        MOD_ROOT / "setting",
        MOD_ROOT / "style",
        MOD_ROOT / "text",
        MOD_ROOT / "sound",
    ]
    files: list[Path] = []
    for root in runtime_roots:
        if root.is_file():
            files.append(root)
        elif root.is_dir():
            files.extend(path for path in root.rglob("*") if path.is_file())
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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skip-manifest", action="store_true", help="Build art only")
    args = parser.parse_args()
    required_sources = [
        ACTOR_SOURCE,
        RUN_SOURCE,
        *ICON_SOURCES.values(),
        *(entry[0] for entry in VFX_SOURCES.values()),
        LUCIAN_ACTOR_SOURCE,
        LUCIAN_RUN_SOURCE,
        *LUCIAN_ICON_SOURCES.values(),
        *(entry[0] for entry in LUCIAN_VFX_SOURCES.values()),
        BASE_SKILL_ICON_SOURCE,
        BASE_CHAMPION_INFO_SOURCE,
    ]
    missing = [path for path in required_sources if not path.exists()]
    if missing:
        raise SystemExit("Missing processed image-gen sources:\n" + "\n".join(str(path) for path in missing))
    actor_sheet, actor_anim, actor_frames = build_actor()
    icons = build_icons()
    vfx = build_vfx()
    qa = build_qa_contacts(actor_frames, icons)
    archer_setting = build_archer_override()
    lucian_sheet, lucian_anim, lucian_frames = build_lucian_actor()
    lucian_icons = build_lucian_icons()
    archer_icon_atlas = build_archer_skill_icon_atlas(lucian_icons)
    lucian_vfx = build_lucian_vfx()
    lucian_qa = build_lucian_qa_contacts(lucian_frames, lucian_icons)
    manifest = None if args.skip_manifest else build_manifest()
    for path in [
        actor_sheet,
        actor_anim,
        *icons,
        *vfx,
        *qa,
        archer_setting,
        lucian_sheet,
        lucian_anim,
        *lucian_icons,
        archer_icon_atlas,
        *lucian_vfx,
        *lucian_qa,
        *([manifest] if manifest else []),
    ]:
        print(path.relative_to(MOD_ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
