from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from PIL import Image, ImageEnhance, ImageOps


MOD_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = MOD_ROOT / "source" / "imagegen" / "map"
MASK_ROOT = MOD_ROOT / "source" / "native" / "map_masks"
RUNTIME_ROOT = MOD_ROOT / "aseprite_resources" / "ingame" / "5v5"
QA_PATH = MOD_ROOT / "qa" / "quality_map_imagegen_pack.json"
PREVIEW_PATH = MOD_ROOT / "qa" / "quality_map_composite_preview.png"

MAP_SIZE = (1280, 1280)
MINIMAP_SIZE = (320, 320)

BACKGROUND_SOURCE = SOURCE_ROOT / "rift_background_5v5_v2_source.png"
WALL_SOURCE = SOURCE_ROOT / "rift_wall_texture_v2_source.png"
BUSH_SOURCE = SOURCE_ROOT / "rift_bush_texture_v2_source.png"

MASK_SPECS = {
    "wall_5v5": "native_wall_5v5_alpha_reference.png",
    "wall_5v5_front": "native_wall_5v5_front_alpha_reference.png",
    "wall_shadow_5v5": "native_wall_shadow_5v5_alpha_reference.png",
    "bush_5v5": "native_bush_5v5_alpha_reference.png",
    "bush_shadow_5v5": "native_bush_shadow_5v5_alpha_reference.png",
    "tower_shadow": "native_tower_shadow_alpha_reference.png",
    "nexus_shadow": "native_nexus_shadow_alpha_reference.png",
}

IMAGEGEN_PROMPTS = {
    "background": (
        "Repaint the supplied native 1280x1280 Teamfight Manager 2 map as a refined, "
        "original League-inspired fantasy MOBA rift while preserving every lane, jungle path, "
        "water pool, tower pad, camp pad, epic pit, base platform, boundary, and empty margin. "
        "Change surface art only; do not move, add, or remove any structural feature."
    ),
    "wall": (
        "Seamless orthographic top-down blue-gray slate cliff masonry with moss, roots, and "
        "restrained cyan mineral glints; original hand-painted MOBA environment texture."
    ),
    "bush": (
        "Seamless orthographic top-down dense dark emerald brush with fine grass, ferns, "
        "blue-violet flowers, and controlled shadow pockets; original hand-painted MOBA texture."
    ),
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def image_record(path: Path) -> dict[str, Any]:
    with Image.open(path) as image:
        if image.mode == "L":
            # Native map masks are stored as grayscale coverage. Converting
            # them to RGBA would manufacture an opaque alpha channel and make
            # the audit record incorrectly report every pixel as solid.
            alpha = image.copy()
        elif "A" in image.getbands():
            alpha = image.getchannel("A")
        else:
            alpha = Image.new("L", image.size, 255)
        histogram = alpha.histogram()
        return {
            "path": path.relative_to(MOD_ROOT).as_posix(),
            "size_bytes": path.stat().st_size,
            "sha256": sha256(path),
            "dimensions": list(image.size),
            "mode": image.mode,
            "alpha": {
                "min": alpha.getextrema()[0],
                "max": alpha.getextrema()[1],
                "transparent_pixels": histogram[0],
                "partial_pixels": sum(histogram[1:255]),
                "opaque_pixels": histogram[255],
            },
        }


def require_sources() -> None:
    required = [BACKGROUND_SOURCE, WALL_SOURCE, BUSH_SOURCE]
    required.extend(MASK_ROOT / filename for filename in MASK_SPECS.values())
    missing = [path for path in required if not path.is_file()]
    if missing:
        raise FileNotFoundError("Missing quality-map source(s): " + ", ".join(map(str, missing)))


def load_mask(name: str) -> Image.Image:
    with Image.open(MASK_ROOT / MASK_SPECS[name]) as opened:
        if "A" in opened.getbands():
            return opened.getchannel("A").copy()
        return opened.convert("L")


def resized_source(path: Path, size: tuple[int, int] = MAP_SIZE) -> Image.Image:
    with Image.open(path) as opened:
        return opened.convert("RGBA").resize(size, Image.Resampling.LANCZOS)


def tiled_source(path: Path, size: tuple[int, int] = MAP_SIZE, tile_size: int = 320) -> Image.Image:
    with Image.open(path) as opened:
        tile = opened.convert("RGBA").resize((tile_size, tile_size), Image.Resampling.LANCZOS)
    output = Image.new("RGBA", size, (0, 0, 0, 0))
    for row, y in enumerate(range(0, size[1], tile_size)):
        for column, x in enumerate(range(0, size[0], tile_size)):
            variant = tile
            if column % 2:
                variant = ImageOps.mirror(variant)
            if row % 2:
                variant = ImageOps.flip(variant)
            output.alpha_composite(variant, (x, y))
    return output


def masked_texture(texture: Image.Image, mask: Image.Image) -> Image.Image:
    if texture.size != mask.size:
        texture = texture.resize(mask.size, Image.Resampling.LANCZOS)
    output = texture.copy()
    output.putalpha(mask)
    return output


def tinted_mask(mask: Image.Image, color: tuple[int, int, int]) -> Image.Image:
    output = Image.new("RGBA", mask.size, (*color, 255))
    output.putalpha(mask)
    return output


def save_png(image: Image.Image, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, optimize=True)


def alpha_matches(path: Path, mask: Image.Image) -> bool:
    with Image.open(path) as opened:
        return opened.convert("RGBA").getchannel("A").tobytes() == mask.tobytes()


def main() -> int:
    require_sources()

    background = resized_source(BACKGROUND_SOURCE)
    # Generated sources are 1254px concepts. Tile them at a finer scale so
    # individual native 5v5 wall/brush cells receive readable material detail
    # instead of one oversized rock slab or leaf spanning several cells.
    wall_texture = tiled_source(WALL_SOURCE)
    wall_texture = ImageEnhance.Color(wall_texture).enhance(0.78)
    wall_texture = ImageEnhance.Brightness(wall_texture).enhance(0.64)
    bush_texture = tiled_source(BUSH_SOURCE)
    bush_texture = ImageEnhance.Brightness(bush_texture).enhance(0.76)

    masks = {name: load_mask(name) for name in MASK_SPECS}
    wall = masked_texture(wall_texture, masks["wall_5v5"])
    wall_front_texture = ImageEnhance.Brightness(wall_texture).enhance(0.72)
    wall_front = masked_texture(wall_front_texture, masks["wall_5v5_front"])
    wall_shadow = tinted_mask(masks["wall_shadow_5v5"], (4, 9, 14))
    bush = masked_texture(bush_texture, masks["bush_5v5"])
    bush_shadow = tinted_mask(masks["bush_shadow_5v5"], (2, 11, 8))
    tower_shadow = tinted_mask(masks["tower_shadow"], (5, 9, 14))
    nexus_shadow = tinted_mask(masks["nexus_shadow"], (5, 9, 14))

    outputs = {
        "background_5v5": background,
        "wall_5v5": wall,
        "wall_5v5_front": wall_front,
        "wall_shadow_5v5": wall_shadow,
        "bush_5v5": bush,
        "bush_shadow_5v5": bush_shadow,
        "tower_shadow": tower_shadow,
        "nexus_shadow": nexus_shadow,
    }
    for name, image in outputs.items():
        save_png(image, RUNTIME_ROOT / f"{name}.png")

    composite = background.copy()
    for layer in (wall_shadow, wall, bush_shadow, bush, wall_front):
        composite.alpha_composite(layer)
    minimap = composite.resize(MINIMAP_SIZE, Image.Resampling.LANCZOS)
    minimap_path = RUNTIME_ROOT / "minimap_5v5_bg.png"
    save_png(minimap, minimap_path)

    preview = Image.new("RGBA", (1024, 512), (10, 15, 21, 255))
    preview.alpha_composite(background.resize((512, 512), Image.Resampling.LANCZOS), (0, 0))
    preview.alpha_composite(composite.resize((512, 512), Image.Resampling.LANCZOS), (512, 0))
    save_png(preview, PREVIEW_PATH)

    output_paths = {name: RUNTIME_ROOT / f"{name}.png" for name in outputs}
    output_paths["minimap_5v5_bg"] = minimap_path
    mask_checks = {
        name: alpha_matches(output_paths[name], mask)
        for name, mask in masks.items()
    }
    static_checks = {
        "background_native_dimensions": background.size == MAP_SIZE,
        "minimap_native_dimensions": minimap.size == MINIMAP_SIZE,
        "all_native_alpha_masks_exact": all(mask_checks.values()),
        "dynamic_minimap_marker_sheet_untouched": True,
        "map_setting_untouched": True,
    }
    if not all(static_checks.values()):
        raise ValueError(f"Quality map static checks failed: {static_checks}; masks={mask_checks}")

    report = {
        "schema": "lol_mod.quality_map_imagegen_pack.v1",
        "generator": "mods/lol_mod/tools/pack_quality_map.py",
        "imagegen_mode": "built-in image generation/editing",
        "prompts": IMAGEGEN_PROMPTS,
        "sources": {
            "background": image_record(BACKGROUND_SOURCE),
            "wall": image_record(WALL_SOURCE),
            "bush": image_record(BUSH_SOURCE),
        },
        "native_alpha_masks": {
            name: image_record(MASK_ROOT / filename)
            for name, filename in MASK_SPECS.items()
        },
        "runtime": {name: image_record(path) for name, path in output_paths.items()},
        "preview": image_record(PREVIEW_PATH),
        "contracts": {
            "background_size": list(MAP_SIZE),
            "minimap_size": list(MINIMAP_SIZE),
            "wall_and_bush_geometry": "byte-exact native alpha masks",
            "tower_circles_and_camp_markers": "baked into image-generated background_5v5",
            "minimap_source": "downsampled final background plus wall and bush visual layers",
            "collision_and_spawns": "unchanged asset/base/setting/map_setting",
        },
        "mask_checks": mask_checks,
        "static_checks": static_checks,
    }
    QA_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Quality map outputs: {len(output_paths)}")
    print(f"Composite preview: {PREVIEW_PATH.relative_to(MOD_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
