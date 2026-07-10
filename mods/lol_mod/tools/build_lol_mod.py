#!/usr/bin/env python3
"""Build Shen's runtime pixel assets from the accepted image-gen sources."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from PIL import Image, ImageDraw


MOD_ROOT = Path(__file__).resolve().parents[1]
SOURCE = MOD_ROOT / "source" / "processed"
ACTOR_DIR = MOD_ROOT / "aseprite_resources" / "champions"
EFFECT_DIR = MOD_ROOT / "aseprite_resources" / "effects"
ICON_DIR = MOD_ROOT / "icons"
QA_DIR = MOD_ROOT / "qa"

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
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


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
    atlas.save(sheet_path, optimize=True)

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


def build_icons() -> list[Path]:
    ICON_DIR.mkdir(parents=True, exist_ok=True)
    outputs: list[Path] = []
    for output_name, source_path in ICON_SOURCES.items():
        source = Image.open(source_path).convert("RGBA")
        icon = fit_cell(source, (64, 64), (58, 58))
        output = ICON_DIR / output_name
        icon.save(output, optimize=True)
        outputs.append(output)
    return outputs


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
        atlas.save(sheet, optimize=True)
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
    actor_contact.save(actor_path, optimize=True)

    icon_contact = Image.new("RGBA", (3 * 192, 208), (20, 18, 28, 255))
    draw = ImageDraw.Draw(icon_contact)
    for index, (path, label) in enumerate(zip(icons, ["Q", "W", "R"], strict=True)):
        icon = Image.open(path).convert("RGBA").resize((192, 192), Image.Resampling.NEAREST)
        icon_contact.alpha_composite(icon, (index * 192, 0))
        draw.text((index * 192 + 8, 192), label, fill=(255, 255, 255, 255))
    icon_path = QA_DIR / "shen_skill_icons_final.png"
    icon_contact.save(icon_path, optimize=True)
    return [actor_path, icon_path]


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
    missing = [path for path in [ACTOR_SOURCE, RUN_SOURCE, *ICON_SOURCES.values(), *(entry[0] for entry in VFX_SOURCES.values())] if not path.exists()]
    if missing:
        raise SystemExit("Missing processed image-gen sources:\n" + "\n".join(str(path) for path in missing))
    actor_sheet, actor_anim, actor_frames = build_actor()
    icons = build_icons()
    vfx = build_vfx()
    qa = build_qa_contacts(actor_frames, icons)
    manifest = None if args.skip_manifest else build_manifest()
    for path in [actor_sheet, actor_anim, *icons, *vfx, *qa, *([manifest] if manifest else [])]:
        print(path.relative_to(MOD_ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
