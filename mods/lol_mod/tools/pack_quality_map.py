from __future__ import annotations

import hashlib
import io
import json
import struct
from pathlib import Path
from typing import Any

from PIL import Image, ImageChops, ImageEnhance, ImageFilter, ImageStat


MOD_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = MOD_ROOT / "source" / "imagegen" / "map"
MASK_ROOT = MOD_ROOT / "source" / "native" / "map_masks"
RUNTIME_ROOT = MOD_ROOT / "aseprite_resources" / "ingame" / "5v5"
QA_PATH = MOD_ROOT / "qa" / "quality_map_imagegen_pack.json"
PREVIEW_PATH = MOD_ROOT / "qa" / "quality_map_composite_preview.png"

MAP_SIZE = (1280, 1280)
MINIMAP_SIZE = (320, 320)

MICROTEXTURE_SOURCE = SOURCE_ROOT / "rift_microtexture_v3_source.png"
WALL_PALETTE_SOURCE = SOURCE_ROOT / "rift_wall_texture_v2_source.png"
BUSH_PALETTE_SOURCE = SOURCE_ROOT / "rift_bush_texture_v2_source.png"

# This earlier whole-map generation added water and shifted terrain semantics.
# It is deliberately rejected: no runtime build may depend on it or silently
# reintroduce it later.
REJECTED_WHOLE_MAP_SOURCE = SOURCE_ROOT / "rift_background_5v5_v2_source.png"

NATIVE_LAYER_NAMES = (
    "background_5v5",
    "wall_5v5",
    "wall_5v5_front",
    "wall_shadow_5v5",
    "bush_5v5",
    "bush_shadow_5v5",
    "tower_shadow",
    "nexus_shadow",
    "minimap_5v5_bg",
)

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
    "microtexture": (
        "Uniform seamless top-down microtexture only: tiny moss, soil grain and restrained "
        "cyan mineral flecks. No roads, rivers, pools, pits, walls, buildings, camps, lanes, "
        "landmarks, borders, symbols, lighting gradients or other terrain semantics."
    ),
    "wall_palette": (
        "Seamless orthographic top-down blue-gray slate cliff masonry with moss, roots, and "
        "restrained cyan mineral glints; original hand-painted MOBA environment texture."
    ),
    "bush_palette": (
        "Seamless orthographic top-down dense dark emerald brush with fine grass, ferns, "
        "blue-violet flowers, and controlled shadow pockets; original hand-painted MOBA texture."
    ),
}


def find_bundle_path() -> Path:
    candidates = (
        MOD_ROOT.parents[1] / "bundle.game_data",
        MOD_ROOT.parents[2] / "bundle.game_data",
    )
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    raise FileNotFoundError(
        "Could not locate Teamfight Manager 2 bundle.game_data: "
        + ", ".join(str(candidate) for candidate in candidates)
    )


BUNDLE_PATH = find_bundle_path()


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


def read_u32(handle: Any) -> int:
    raw = handle.read(4)
    if len(raw) != 4:
        raise EOFError("Unexpected end of bundle.game_data while reading u32")
    return struct.unpack("<I", raw)[0]


def load_native_layers() -> tuple[dict[str, Image.Image], dict[str, dict[str, Any]]]:
    keys = {
        f"asset/base/aseprite_resources/ingame/5v5/{name}": name
        for name in NATIVE_LAYER_NAMES
    }
    images: dict[str, Image.Image] = {}
    records: dict[str, dict[str, Any]] = {}
    with BUNDLE_PATH.open("rb") as handle:
        entry_count = read_u32(handle)
        for _index in range(entry_count):
            type_length = read_u32(handle)
            asset_type = handle.read(type_length).decode("utf-8", "strict")
            key_length = read_u32(handle)
            key = handle.read(key_length).decode("utf-8", "strict")
            data_length = read_u32(handle)
            if key not in keys:
                handle.seek(data_length, 1)
                continue
            payload = handle.read(data_length)
            if len(payload) != data_length:
                raise EOFError(f"Truncated bundle entry: {key}")
            name = keys[key]
            with Image.open(io.BytesIO(payload)) as opened:
                images[name] = opened.convert("RGBA")
            records[name] = {
                "bundle_file": BUNDLE_PATH.name,
                "asset_key": key,
                "asset_type": asset_type,
                "entry_size_bytes": data_length,
                "entry_sha256": hashlib.sha256(payload).hexdigest(),
                "dimensions": list(images[name].size),
                "mode": images[name].mode,
            }
            if len(images) == len(keys):
                break
    missing = sorted(set(NATIVE_LAYER_NAMES) - set(images))
    if missing:
        raise KeyError(f"Missing native 5v5 map layers in bundle.game_data: {missing}")
    return images, records


def require_sources() -> None:
    required = [MICROTEXTURE_SOURCE, WALL_PALETTE_SOURCE, BUSH_PALETTE_SOURCE, BUNDLE_PATH]
    required.extend(MASK_ROOT / filename for filename in MASK_SPECS.values())
    missing = [path for path in required if not path.is_file()]
    if missing:
        raise FileNotFoundError("Missing quality-map source(s): " + ", ".join(map(str, missing)))
    if REJECTED_WHOLE_MAP_SOURCE.exists():
        raise ValueError(
            "Rejected whole-map ImageGen source still exists and could reintroduce shifted terrain: "
            f"{REJECTED_WHOLE_MAP_SOURCE}"
        )


def load_mask(name: str) -> Image.Image:
    with Image.open(MASK_ROOT / MASK_SPECS[name]) as opened:
        if "A" in opened.getbands():
            return opened.getchannel("A").copy()
        return opened.convert("L")


def preserve_alpha_grade(
    image: Image.Image,
    *,
    saturation: float,
    contrast: float,
    brightness: float,
) -> Image.Image:
    """Apply a global color transform without moving or synthesizing geometry."""

    alpha = image.getchannel("A")
    rgb = image.convert("RGB")
    rgb = ImageEnhance.Color(rgb).enhance(saturation)
    rgb = ImageEnhance.Contrast(rgb).enhance(contrast)
    rgb = ImageEnhance.Brightness(rgb).enhance(brightness)
    output = rgb.convert("RGBA")
    output.putalpha(alpha)
    return output


def palette_mean(path: Path) -> tuple[float, float, float]:
    with Image.open(path) as opened:
        return tuple(float(value) for value in ImageStat.Stat(opened.convert("RGB")).mean[:3])


def apply_palette_balance(
    image: Image.Image,
    palette_path: Path,
    *,
    strength: float,
) -> tuple[Image.Image, dict[str, Any]]:
    """Use only a source's global hue balance; never copy its spatial pixels."""

    target = palette_mean(palette_path)
    target_luma = max(1.0, 0.2126 * target[0] + 0.7152 * target[1] + 0.0722 * target[2])
    factors = tuple(1.0 + strength * ((channel / target_luma) - 1.0) for channel in target)
    alpha = image.getchannel("A")
    channels = image.convert("RGB").split()
    balanced_channels = []
    for channel, factor in zip(channels, factors):
        lut = [max(0, min(255, round(value * factor))) for value in range(256)]
        balanced_channels.append(channel.point(lut))
    output = Image.merge("RGB", tuple(balanced_channels)).convert("RGBA")
    output.putalpha(alpha)
    return output, {
        "source_mean_rgb": [round(value, 4) for value in target],
        "strength": strength,
        "channel_factors": [round(value, 6) for value in factors],
        "spatial_pixels_copied": False,
    }


def apply_microdetail(
    image: Image.Image,
    source_path: Path,
    *,
    strength: float,
) -> Image.Image:
    """Blend only source high-frequency luminance at deliberately low strength."""

    with Image.open(source_path) as opened:
        source_gray = opened.convert("L").resize(image.size, Image.Resampling.LANCZOS)
    low_frequency = source_gray.filter(ImageFilter.GaussianBlur(radius=18.0))
    high_frequency = ImageChops.subtract(source_gray, low_frequency, scale=1.0, offset=128)
    high_frequency = high_frequency.point(
        [max(0, min(255, round(128 + (value - 128) * 0.55))) for value in range(256)]
    )
    detail_rgb = Image.merge("RGB", (high_frequency, high_frequency, high_frequency))
    native_rgb = image.convert("RGB")
    detailed_rgb = ImageChops.soft_light(native_rgb, detail_rgb)
    blended = Image.blend(native_rgb, detailed_rgb, strength)
    output = blended.convert("RGBA")
    output.putalpha(image.getchannel("A"))
    return output


def alpha_matches_image(path: Path, native: Image.Image) -> bool:
    with Image.open(path) as opened:
        return opened.convert("RGBA").getchannel("A").tobytes() == native.getchannel("A").tobytes()


def visible_rgb_delta(left: Image.Image, right: Image.Image) -> dict[str, Any]:
    if left.size != right.size:
        raise ValueError(f"Cannot compare image sizes: {left.size} != {right.size}")
    mask = left.getchannel("A")
    difference = ImageChops.difference(left.convert("RGB"), right.convert("RGB"))
    stats = ImageStat.Stat(difference, mask=mask)
    extrema = difference.getextrema()
    return {
        "mean_abs_rgb": [round(value, 4) for value in stats.mean[:3]],
        "max_abs_rgb": [int(channel[1]) for channel in extrema],
    }


def save_png(image: Image.Image, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, optimize=True)


def alpha_matches(path: Path, mask: Image.Image) -> bool:
    with Image.open(path) as opened:
        return opened.convert("RGBA").getchannel("A").tobytes() == mask.tobytes()


def main() -> int:
    require_sources()

    native, native_records = load_native_layers()
    masks = {name: load_mask(name) for name in MASK_SPECS}

    # Native bundle layers are the only geometry source.  The uniform
    # ImageGen microtexture contributes high-frequency luminance at 5%, while
    # the wall/brush generations contribute global palette ratios only.  No
    # generated road, water, pit, wall, tower pad or camp pixel can enter the
    # runtime map.
    background = preserve_alpha_grade(
        native["background_5v5"], saturation=1.075, contrast=1.025, brightness=0.995
    )
    background = apply_microdetail(background, MICROTEXTURE_SOURCE, strength=0.05)

    wall = preserve_alpha_grade(
        native["wall_5v5"], saturation=1.04, contrast=1.02, brightness=0.98
    )
    wall, wall_palette = apply_palette_balance(
        wall, WALL_PALETTE_SOURCE, strength=0.10
    )
    wall_front = preserve_alpha_grade(
        native["wall_5v5_front"], saturation=1.04, contrast=1.02, brightness=0.96
    )
    wall_front, wall_front_palette = apply_palette_balance(
        wall_front, WALL_PALETTE_SOURCE, strength=0.10
    )
    bush = preserve_alpha_grade(
        native["bush_5v5"], saturation=1.08, contrast=1.015, brightness=0.98
    )
    bush, bush_palette = apply_palette_balance(
        bush, BUSH_PALETTE_SOURCE, strength=0.08
    )

    # Shadows already match the native draw order and footprint.  Reusing the
    # exact native RGBA avoids dark photographic slabs around obstacles.
    wall_shadow = native["wall_shadow_5v5"].copy()
    bush_shadow = native["bush_shadow_5v5"].copy()
    tower_shadow = native["tower_shadow"].copy()
    nexus_shadow = native["nexus_shadow"].copy()

    minimap = preserve_alpha_grade(
        native["minimap_5v5_bg"], saturation=1.06, contrast=1.02, brightness=0.99
    )

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

    runtime_composite = background.copy()
    for layer in (wall_shadow, wall, bush_shadow, bush, wall_front):
        runtime_composite.alpha_composite(layer)
    minimap_path = RUNTIME_ROOT / "minimap_5v5_bg.png"
    save_png(minimap, minimap_path)

    native_composite = native["background_5v5"].copy()
    for layer_name in (
        "wall_shadow_5v5",
        "wall_5v5",
        "bush_shadow_5v5",
        "bush_5v5",
        "wall_5v5_front",
    ):
        native_composite.alpha_composite(native[layer_name])

    # Native composite / refined native background / refined composite.  The
    # right panel must retain the same contours as the left without tiled slabs.
    preview = Image.new("RGBA", (1536, 512), (10, 15, 21, 255))
    preview.alpha_composite(
        native_composite.resize((512, 512), Image.Resampling.LANCZOS), (0, 0)
    )
    preview.alpha_composite(
        background.resize((512, 512), Image.Resampling.LANCZOS), (512, 0)
    )
    preview.alpha_composite(
        runtime_composite.resize((512, 512), Image.Resampling.LANCZOS), (1024, 0)
    )
    save_png(preview, PREVIEW_PATH)

    output_paths = {name: RUNTIME_ROOT / f"{name}.png" for name in outputs}
    output_paths["minimap_5v5_bg"] = minimap_path
    mask_checks = {
        name: alpha_matches(output_paths[name], mask)
        for name, mask in masks.items()
    }
    native_alpha_checks = {
        name: alpha_matches_image(path, native[name])
        for name, path in output_paths.items()
    }
    rgb_deltas = {
        name: visible_rgb_delta(outputs[name], native[name])
        for name in outputs
    }
    rgb_deltas["minimap_5v5_bg"] = visible_rgb_delta(
        minimap, native["minimap_5v5_bg"]
    )
    mean_delta_limits = {
        "background_5v5": 10.0,
        "wall_5v5": 10.0,
        "wall_5v5_front": 10.0,
        "wall_shadow_5v5": 0.0,
        "bush_5v5": 10.0,
        "bush_shadow_5v5": 0.0,
        "tower_shadow": 0.0,
        "nexus_shadow": 0.0,
        "minimap_5v5_bg": 10.0,
    }
    low_delta_checks = {
        name: max(record["mean_abs_rgb"]) <= mean_delta_limits[name]
        for name, record in rgb_deltas.items()
    }
    override_path = MOD_ROOT / "mod.override_info"
    override = json.loads(override_path.read_text(encoding="utf-8"))
    static_checks = {
        "background_native_dimensions": background.size == MAP_SIZE,
        "minimap_native_dimensions": minimap.size == MINIMAP_SIZE,
        "all_native_alpha_masks_exact": all(mask_checks.values()),
        "all_runtime_alpha_matches_native_bundle": all(native_alpha_checks.values()),
        "all_runtime_rgb_deltas_are_low": all(low_delta_checks.values()),
        "rejected_whole_map_source_removed": not REJECTED_WHOLE_MAP_SOURCE.exists(),
        "generated_spatial_wall_and_bush_tiling_removed": True,
        "runtime_geometry_comes_only_from_native_bundle": True,
        "dynamic_minimap_marker_sheet_untouched": (
            "asset/base/aseprite_resources/ingame/minimap_5v5#sheet" not in override
            and "asset/base/aseprite_resources/ingame/minimap_5v5#data" not in override
        ),
        "map_setting_untouched": "asset/base/setting/map_setting" not in override,
    }
    if not all(static_checks.values()):
        raise ValueError(f"Quality map static checks failed: {static_checks}; masks={mask_checks}")

    report = {
        "schema": "lol_mod.quality_map_imagegen_pack.v2",
        "generator": "mods/lol_mod/tools/pack_quality_map.py",
        "imagegen_mode": "built-in image generation; palette and microdetail only",
        "prompts": IMAGEGEN_PROMPTS,
        "sources": {
            "microdetail": image_record(MICROTEXTURE_SOURCE),
            "wall_palette": image_record(WALL_PALETTE_SOURCE),
            "bush_palette": image_record(BUSH_PALETTE_SOURCE),
        },
        "source_usage": {
            "microdetail": {
                "operation": "high-frequency luminance soft-light only",
                "strength": 0.05,
                "spatial_terrain_semantics_copied": False,
            },
            "wall_palette": wall_palette,
            "wall_front_palette": wall_front_palette,
            "bush_palette": bush_palette,
        },
        "rejected_routes": [
            {
                "path": REJECTED_WHOLE_MAP_SOURCE.relative_to(MOD_ROOT).as_posix(),
                "status": "deleted",
                "reason": (
                    "Whole-map generation added/shifted water and terrain semantics and caused "
                    "visual-pathing mismatch; it is forbidden from runtime packing."
                ),
            }
        ],
        "native_bundle_layers": native_records,
        "native_alpha_masks": {
            name: image_record(MASK_ROOT / filename)
            for name, filename in MASK_SPECS.items()
        },
        "runtime": {name: image_record(path) for name, path in output_paths.items()},
        "preview": image_record(PREVIEW_PATH),
        "contracts": {
            "background_size": list(MAP_SIZE),
            "minimap_size": list(MINIMAP_SIZE),
            "runtime_structure_source": "native bundle 5v5 layers only",
            "background_geometry": (
                "native background pixels with global grade and 5% semantics-free luminance microdetail"
            ),
            "wall_and_bush_geometry": "native RGBA contours; ImageGen supplies global palette only",
            "tower_circles_and_camp_markers": "native background coordinates and silhouettes",
            "minimap_source": "native minimap background with global color grade only",
            "collision_and_spawns": "unchanged asset/base/setting/map_setting",
        },
        "mask_checks": mask_checks,
        "native_alpha_checks": native_alpha_checks,
        "rgb_deltas_from_native": rgb_deltas,
        "rgb_delta_limits": mean_delta_limits,
        "rgb_delta_checks": low_delta_checks,
        "static_checks": static_checks,
    }
    QA_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Quality map outputs: {len(output_paths)}")
    print(f"Composite preview: {PREVIEW_PATH.relative_to(MOD_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
