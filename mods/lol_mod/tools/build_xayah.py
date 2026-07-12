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
import struct
import wave
import zlib
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from PIL import Image


MOD_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = MOD_ROOT / "source"
PROCESSED_ROOT = SOURCE_ROOT / "processed"
IMAGEGEN_ROOT = SOURCE_ROOT / "imagegen"
ACTOR_DIR = MOD_ROOT / "aseprite_resources" / "champions"
EFFECT_DIR = MOD_ROOT / "aseprite_resources" / "effects"
ICON_DIR = MOD_ROOT / "icons"
SPLASH_DIR = MOD_ROOT / "BanPickIllust"
FULLBODY_DIR = MOD_ROOT / "ui" / "champion_fullbody"
SOUND_DIR = MOD_ROOT / "sound" / "sfx"
QA_DIR = MOD_ROOT / "qa"

ACTOR_SOURCE = PROCESSED_ROOT / "xayah_actor_contact_alpha.png"
RUN_SOURCE = PROCESSED_ROOT / "xayah_run_contact_alpha.png"
DEFEAT_SOURCE = PROCESSED_ROOT / "xayah_defeat_contact_alpha.png"
ATTACK_VFX_SOURCE = PROCESSED_ROOT / "xayah_attack_vfx_contact_alpha.png"
Q_VFX_SOURCE = PROCESSED_ROOT / "xayah_q_vfx_contact_alpha.png"
E_VFX_SOURCE = PROCESSED_ROOT / "xayah_e_vfx_contact_alpha.png"
R_VFX_SOURCE = PROCESSED_ROOT / "xayah_r_vfx_contact_alpha.png"
Q_ICON_SOURCE = IMAGEGEN_ROOT / "xayah_q_icon_source.png"
E_ICON_SOURCE = IMAGEGEN_ROOT / "xayah_e_icon_source.png"
R_ICON_SOURCE = IMAGEGEN_ROOT / "xayah_r_icon_source.png"
SPLASH_SOURCE = IMAGEGEN_ROOT / "bp_splash" / "dancer.png"

ACTOR_SHEET_SIZE = (1594, 90)


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
    baseline: int | None = None,
    preserve_aspect: bool = False,
) -> Image.Image:
    """Fit one full-body pose at a stable actor height inside native 007 boxes."""
    source = hard_alpha(source)
    subject = source.crop(alpha_bbox(source))
    target_height = min(target_height, frame_size[1] - 2)
    width = max(1, round(subject.width * target_height / subject.height))
    max_width = max(1, frame_size[0] - 2)
    if preserve_aspect and width > max_width:
        scale = max_width / subject.width
        target_height = max(1, min(target_height, round(subject.height * scale)))
        width = max_width
    else:
        # Long cape/stride poses need x-only compression to preserve battle scale.
        width = min(width, max_width)
    resized = subject.resize((width, target_height), Image.Resampling.LANCZOS)
    resized = palette_finish(resized, 48)
    output = Image.new("RGBA", frame_size, (0, 0, 0, 0))
    x = (frame_size[0] - resized.width) // 2
    anchor = frame_size[1] - 1 if baseline is None else min(baseline, frame_size[1] - 1)
    y = max(0, min(frame_size[1] - resized.height, anchor - resized.height))
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
        Image.Resampling.LANCZOS,
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
    actor_cells = split_grid(Image.open(ACTOR_SOURCE).convert("RGBA"), 4, 3)
    run_cells = split_grid(Image.open(RUN_SOURCE).convert("RGBA"), 4, 2)
    defeat_cells = split_grid(Image.open(DEFEAT_SOURCE).convert("RGBA"), 3, 3)
    attack_vfx = split_grid(Image.open(ATTACK_VFX_SOURCE).convert("RGBA"), 4, 2)
    q_vfx = split_grid(Image.open(Q_VFX_SOURCE).convert("RGBA"), 4, 2)

    sheet = Image.new("RGBA", ACTOR_SHEET_SIZE, (0, 0, 0, 0))
    placements: dict[tuple[int, int, int, int], bytes] = {}
    representative: list[Image.Image] = []

    sequences = {
        "idle": actor_cells[0:4],
        "run": run_cells,
        "attack": [actor_cells[index] for index in (0, 4, 5, 5, 0)],
        "hit": [actor_cells[11]],
        "skill1": [actor_cells[index] for index in (4, 5, 6, 7, 7)],
        "skill2": [actor_cells[index] for index in (8, 9, 8)],
        # R keeps the same compact actor scale; the large fan lives in xayah_r.
        "ult": [actor_cells[index] for index in (8, 8, 9, 8, 0)],
    }
    target_heights = {"idle": 44, "run": 39, "attack": 39, "hit": 38, "skill1": 40, "skill2": 40, "ult": 40}
    for tag in ("ult", "idle", "run", "hit", "attack", "skill1", "skill2"):
        sources = sequences[tag]
        rects = NATIVE_CONTRACT[tag]["rects"]
        if len(sources) != len(rects):
            raise ValueError(f"{tag}: {len(sources)} sources for {len(rects)} native frames")
        for rect, source in zip(rects, sources, strict=True):
            frame = fit_actor(source, (rect[2], rect[3]), target_height=target_heights[tag])
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
    for rect, source in zip(NATIVE_CONTRACT["skill1_projectile"]["rects"], q_vfx[1:3], strict=True):
        _paste_unique(sheet, placements, rect, fit_effect(source, (rect[2], rect[3]), padding=1))

    # Nine generated fall/grounded poses exactly fill the nine visible native
    # frames; the mandatory final 3x3 terminal frame remains transparent.
    for rect, source in zip(NATIVE_CONTRACT["dead"]["rects"][:-1], defeat_cells, strict=True):
        frame = fit_actor(
            source,
            (rect[2], rect[3]),
            target_height=max(18, rect[3] - 4),
            preserve_aspect=True,
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
    crop_top_half_tags: frozenset[str] = frozenset(),
) -> list[Path]:
    cells = split_grid(Image.open(source_path).convert("RGBA"), 4, 2)
    sheet_width = max(len(indexes) * size[0] for _, indexes, size, _ in tag_specs)
    sheet_height = sum(size[1] for _, _, size, _ in tag_specs)
    sheet = Image.new("RGBA", (sheet_width, sheet_height), (0, 0, 0, 0))
    y = 0
    anims: dict[str, Any] = {}
    for tag, indexes, frame_size, duration in tag_specs:
        frames: list[dict[str, Any]] = []
        for frame_index, source_index in enumerate(indexes):
            source = cells[source_index]
            if tag in crop_top_half_tags:
                # Q's generated contact cell contains a display pair.  The
                # gameplay data launches two separate projectiles, so each
                # runtime projectile frame must contain exactly one feather.
                source = source.crop((0, 0, source.width, source.height // 2))
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
            crop_top_half_tags=frozenset({"projectile"}),
        )
    )
    outputs.extend(
        _build_effect(
            "xayah_e",
            E_VFX_SOURCE,
            [
                ("return", [0, 1, 2, 3], (96, 48), 0.06),
                ("root", [4, 5, 6, 7], (96, 96), 0.07),
                ("hit", [4, 5, 6, 7], (64, 64), 0.06),
            ],
        )
    )
    outputs.extend(
        _build_effect(
            "xayah_r",
            R_VFX_SOURCE,
            [
                ("fan", [0, 1, 2, 3], (128, 96), 0.07),
                ("hit", [4, 5, 6, 7], (128, 96), 0.07),
                ("guard", [4, 5, 6, 7], (96, 96), 0.07),
            ],
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


def build_splash_and_fullbody(actor_sheet: Path) -> list[Path]:
    splash = cover_crop(Image.open(SPLASH_SOURCE).convert("RGBA"), (1420, 860))
    splash_path = SPLASH_DIR / "dancer.png"
    save_png(splash_path, splash)

    idle_rect = NATIVE_CONTRACT["idle"]["rects"][0]
    actor = Image.open(actor_sheet).convert("RGBA")
    x, y, width, height = idle_rect
    idle = actor.crop((x, y, x + width, y + height))
    idle = idle.crop(alpha_bbox(idle))
    scale = min(58 / idle.width, 60 / idle.height)
    idle = idle.resize(
        (max(1, round(idle.width * scale)), max(1, round(idle.height * scale))),
        Image.Resampling.NEAREST,
    )
    portrait = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    portrait.alpha_composite(idle, ((64 - idle.width) // 2, 63 - idle.height))
    portrait_path = FULLBODY_DIR / "dancer.png"
    save_png(portrait_path, portrait)
    return [splash_path, portrait_path]


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


def build_imagegen_provenance(runtime_paths: Iterable[Path]) -> Path:
    source_specs = [
        ("actor_contact", IMAGEGEN_ROOT / "xayah_actor_contact.png"),
        ("run_contact", IMAGEGEN_ROOT / "xayah_run_contact.png"),
        ("defeat_contact", IMAGEGEN_ROOT / "xayah_defeat_contact.png"),
        ("q_icon", Q_ICON_SOURCE),
        ("e_icon", E_ICON_SOURCE),
        ("r_icon", R_ICON_SOURCE),
        ("attack_vfx", IMAGEGEN_ROOT / "xayah_attack_vfx_contact.png"),
        ("q_vfx", IMAGEGEN_ROOT / "xayah_q_vfx_contact.png"),
        ("e_vfx", IMAGEGEN_ROOT / "xayah_e_vfx_contact.png"),
        ("r_vfx", IMAGEGEN_ROOT / "xayah_r_vfx_contact.png"),
        ("bp_splash", SPLASH_SOURCE),
    ]
    processed_specs = [
        ("actor_contact_alpha", ACTOR_SOURCE),
        ("run_contact_alpha", RUN_SOURCE),
        ("defeat_contact_alpha", DEFEAT_SOURCE),
        ("attack_vfx_alpha", ATTACK_VFX_SOURCE),
        ("q_vfx_alpha", Q_VFX_SOURCE),
        ("e_vfx_alpha", E_VFX_SOURCE),
        ("r_vfx_alpha", R_VFX_SOURCE),
    ]
    path = QA_DIR / "xayah_imagegen_sources.json"
    write_json(
        path,
        {
            "schema_version": 1,
            "champion": "Xayah",
            "generator": "built-in image_gen",
            "generated_images_batch": "019f4bd8-30d3-7b60-98fa-58403cf263c7",
            "generated_on": "2026-07-12",
            "prompt_record": "source/imagegen/PROMPTS.md#xayah-image-gen-prompts",
            "background_removal": "remove_chroma_key.py border auto-key, soft matte, thresholds 12/220, despill; builder hardens final actor/VFX alpha",
            "native_actor_contract": {
                "base_champion": "dancer",
                "sheet_size": list(ACTOR_SHEET_SIZE),
                "tag_order": list(NATIVE_CONTRACT),
                "frame_counts": {tag: len(spec["rects"]) for tag, spec in NATIVE_CONTRACT.items()},
                "large_vfx_policy": "xayah_attack, xayah_q, xayah_e and xayah_r are separate effect sheets",
            },
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
    idle_rect = NATIVE_CONTRACT["idle"]["rects"][0]
    x, y, width, height = idle_rect
    idle_bbox = sheet.crop((x, y, x + width, y + height)).getchannel("A").getbbox()
    if idle_bbox is None or idle_bbox[1] > 5 or idle_bbox[3] < height - 2:
        raise ValueError(f"Xayah first idle frame is not full head-to-feet: {idle_bbox}")
    if Image.open(SPLASH_DIR / "dancer.png").size != (1420, 860):
        raise ValueError("Xayah BP splash size changed")
    if Image.open(FULLBODY_DIR / "dancer.png").size != (64, 64):
        raise ValueError("Xayah encyclopedia portrait size changed")
    missing = [path for path in outputs if not path.is_file()]
    if missing:
        raise FileNotFoundError("Missing Xayah outputs:\n" + "\n".join(str(path) for path in missing))


def build_all() -> list[Path]:
    required = [
        ACTOR_SOURCE, RUN_SOURCE, DEFEAT_SOURCE,
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
    imagegen_provenance = build_imagegen_provenance(runtime_visuals)
    audio_provenance = build_audio_provenance()
    outputs = [*runtime_visuals, *audio, imagegen_provenance, audio_provenance]
    validate_outputs(actor_sheet, actor_anim, outputs)
    return outputs


def main() -> int:
    for path in build_all():
        print(path.relative_to(MOD_ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
