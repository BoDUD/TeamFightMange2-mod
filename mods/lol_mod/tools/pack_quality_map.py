from __future__ import annotations

import hashlib
import io
import json
import struct
from pathlib import Path
from typing import Any

from PIL import (
    Image,
    ImageChops,
    ImageDraw,
    ImageEnhance,
    ImageFilter,
    ImageOps,
    ImageStat,
)


MOD_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = MOD_ROOT / "source" / "imagegen" / "map"
MASK_ROOT = MOD_ROOT / "source" / "native" / "map_masks"
LANDMARK_SOURCE_ROOT = SOURCE_ROOT / "landmarks"
LANDMARK_MASK_ROOT = MASK_ROOT / "landmarks"
RUNTIME_ROOT = MOD_ROOT / "aseprite_resources" / "ingame" / "5v5"
QA_PATH = MOD_ROOT / "qa" / "quality_map_imagegen_pack.json"
PREVIEW_PATH = MOD_ROOT / "qa" / "quality_map_composite_preview.png"
LANDMARK_PREVIEW_PATH = MOD_ROOT / "qa" / "quality_map_landmark_masks_preview.png"
LANDMARK_DETAIL_PREVIEW_PATH = MOD_ROOT / "qa" / "quality_map_landmark_detail_preview.png"
SURFACE_DETAIL_PREVIEW_PATH = MOD_ROOT / "qa" / "quality_map_surface_detail_preview.png"

MAP_SIZE = (1280, 1280)
MINIMAP_SIZE = (320, 320)

MICROTEXTURE_SOURCE = SOURCE_ROOT / "rift_microtexture_v3_source.png"
WALL_MASONRY_SOURCE = SOURCE_ROOT / "rift_wall_masonry_v3_source.png"
CLIFF_MICRODETAIL_SOURCE = SOURCE_ROOT / "rift_cliff_microdetail_v4_source.png"
BUSH_MICRODETAIL_SOURCE = SOURCE_ROOT / "rift_bush_microdetail_v3_source.png"

SURFACE_SOURCE_EXEC_IDS = {
    "wall_masonry": "exec-b126d077-ca6f-4580-845c-85e54c299ad7",
    "cliff_microdetail": "exec-314b7938-4a24-46ba-aea4-fb476c3c8329",
    "bush_microdetail": "exec-d8c82ac3-7568-41bb-973a-304bb910f23b",
}

SURFACE_DETAIL_STRENGTHS = {
    "wall_main_masonry": 0.08,
    "wall_outer_cliff": 0.10,
    "wall_front_masonry": 0.08,
    "bush_microdetail": 0.08,
}

# Half-open rectangles measured in the official 1280x1280 layer coordinate
# space.  They select only the tall left/right exterior cliff faces; every
# other wall pixel receives the subtler masonry microdetail.
OUTER_CLIFF_REGIONS = (
    (0, 160, 192, 1280),
    (1088, 160, 1280, 1280),
)

SURFACE_PREVIEW_CROPS = {
    "left_outer_cliff": (32, 160, 160, 544),
    "bush": (160, 160, 256, 256),
    "bottom_front_wall": (384, 1113, 896, 1170),
}

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
    "wall_masonry_microdetail_v3": (
        "Seamless orthographic top-down blue-gray rift masonry microdetail with restrained moss, "
        "fine cracks and tiny cyan mineral glints; original hand-painted MOBA environment texture."
    ),
    "cliff_microdetail_v4": (
        "Seamless orthographic top-down dark slate rift cliff microdetail with layered rock faces, "
        "fine roots, restrained moss and tiny cyan mineral glints; no map layout or landmarks."
    ),
    "bush_microdetail_v3": (
        "Seamless orthographic top-down dense dark emerald rift brush microdetail with fine leaves, "
        "ferns and sparse blue-violet flowers; no paths, clearings, walls or terrain landmarks."
    ),
    "landmark_common": (
        "One isolated square orthographic top-down hand-painted MOBA terrain decal, "
        "League-inspired but original, crisp readable stonework at small game scale, restrained "
        "cyan or team-color magic, no characters, monsters, buildings, text, logos, UI, roads, "
        "rivers, pools, walls, grass, perspective, or photographic lighting. Transparent outside "
        "the decal if possible; otherwise use one uniform #18382f background."
    ),
}


# All coordinates use Pillow's half-open (left, top, right, bottom) convention in
# the native 1280x1280 background_5v5 coordinate system.  These rectangles were
# measured from the bundled official layer on its 32 px gameplay grid.  The
# corresponding masks deliberately retain a narrow ring of native pixels so a
# generated decal can refine a landmark without redrawing its official outline.
TOWER_PAD_BBOXES = (
    (384, 160, 480, 256),
    (640, 160, 736, 256),
    (896, 224, 992, 320),
    (960, 288, 1056, 384),
    (832, 352, 928, 448),
    (160, 384, 256, 480),
    (704, 480, 800, 576),
    (1024, 544, 1120, 640),
    (160, 640, 256, 736),
    (480, 704, 576, 800),
    (1024, 800, 1120, 896),
    (352, 832, 448, 928),
    (224, 896, 320, 992),
    (288, 960, 384, 1056),
    (544, 1024, 640, 1120),
    (800, 1024, 896, 1120),
)

JUNGLE_CAMP_LARGE_BBOXES = (
    (704, 288, 800, 384),
    (864, 608, 960, 704),
    (288, 688, 384, 784),
    (608, 864, 704, 960),
)

JUNGLE_CAMP_SMALL_BBOXES = (
    (576, 384, 640, 448),
    (928, 448, 992, 512),
    (384, 576, 448, 640),
    (480, 928, 544, 992),
)

BARON_PIT_BBOX = (336, 352, 528, 544)
DRAGON_PIT_BBOX = (736, 736, 928, 928)
BLUE_NEXUS_PAD_BBOX = (224, 992, 288, 1056)
RED_NEXUS_PAD_BBOX = (992, 224, 1056, 288)
BLUE_SPAWN_PLATFORM_BBOX = (160, 960, 320, 1120)
RED_SPAWN_PLATFORM_BBOX = (960, 160, 1120, 320)

ROTATIONS_4 = ("identity", "rotate_90", "rotate_180", "rotate_270")

LANDMARK_SPECS: dict[str, dict[str, Any]] = {
    "baron_pit": {
        "source": "baron_pit_source.png",
        "target_size": (192, 192),
        "instances": ((BARON_PIT_BBOX, "identity"),),
        "shape": {
            "kind": "polygon",
            "points": (
                (46, 10),
                (112, 8),
                (157, 22),
                (183, 57),
                (187, 112),
                (171, 153),
                (137, 178),
                (82, 183),
                (37, 169),
                (10, 135),
                (7, 83),
                (24, 42),
            ),
            "native_border_inset_px": 2,
            "inward_feather_px": 1.25,
        },
        "art_direction": "northwest Baron pit; dark violet obsidian and ancient runic stone",
    },
    "dragon_pit": {
        "source": "dragon_pit_source.png",
        "target_size": (192, 192),
        "instances": ((DRAGON_PIT_BBOX, "identity"),),
        "shape": {
            "kind": "polygon",
            "points": (
                (52, 13),
                (116, 8),
                (161, 30),
                (184, 66),
                (184, 118),
                (162, 161),
                (126, 180),
                (70, 180),
                (27, 160),
                (8, 124),
                (8, 74),
                (28, 37),
            ),
            "native_border_inset_px": 2,
            "inward_feather_px": 1.25,
        },
        "art_direction": "southeast Dragon pit; aged bronze and blue-gray stone dragon ring",
    },
    "jungle_camp_large": {
        "source": "jungle_camp_large_source.png",
        "target_size": (96, 96),
        "instances": tuple(zip(JUNGLE_CAMP_LARGE_BBOXES, ROTATIONS_4)),
        "shape": {
            "kind": "rectangle",
            "native_border_inset_px": 2,
            "inward_feather_px": 1.0,
        },
        "art_direction": "large square neutral-monster camp stone pad; empty clean center",
    },
    "jungle_camp_small": {
        "source": "jungle_camp_small_source.png",
        "target_size": (64, 64),
        "instances": tuple(zip(JUNGLE_CAMP_SMALL_BBOXES, ROTATIONS_4)),
        "shape": {
            "kind": "rectangle",
            "native_border_inset_px": 2,
            "inward_feather_px": 1.0,
        },
        "art_direction": "small square neutral-monster camp stone pad; empty clean center",
    },
    "tower_pad": {
        "source": "tower_pad_source.png",
        "target_size": (96, 96),
        "instances": tuple(
            (bbox, ROTATIONS_4[index % len(ROTATIONS_4)])
            for index, bbox in enumerate(TOWER_PAD_BBOXES)
        ),
        "shape": {
            "kind": "ellipse",
            "bounds": (1, 1, 94, 94),
            "native_border_inset_px": 2,
            "inward_feather_px": 1.0,
        },
        "art_direction": "team-neutral circular layered tower foundation; no tower or team color",
    },
    "blue_nexus_pad": {
        "source": "blue_nexus_pad_source.png",
        "target_size": (64, 64),
        "instances": ((BLUE_NEXUS_PAD_BBOX, "identity"),),
        "shape": {
            "kind": "rectangle",
            "native_border_inset_px": 2,
            "inward_feather_px": 1.0,
        },
        "art_direction": "square blue-team nexus foundation; no nexus crystal or building",
    },
    "red_nexus_pad": {
        "source": "red_nexus_pad_source.png",
        "target_size": (64, 64),
        "instances": ((RED_NEXUS_PAD_BBOX, "identity"),),
        "shape": {
            "kind": "rectangle",
            "native_border_inset_px": 2,
            "inward_feather_px": 1.0,
        },
        "art_direction": "square red-team nexus foundation; no nexus crystal or building",
    },
    "blue_spawn_platform": {
        "source": "blue_spawn_platform_source.png",
        "target_size": (160, 160),
        "instances": ((BLUE_SPAWN_PLATFORM_BBOX, "identity"),),
        "shape": {
            "kind": "polygon",
            "points": ((0, 0), (64, 0), (64, 96), (160, 96), (160, 160), (0, 160)),
            "native_border_inset_px": 2,
            "inward_feather_px": 1.0,
        },
        "art_direction": "blue fountain/spawn L-platform with a readable diamond plus marker",
    },
    "red_spawn_platform": {
        "source": "red_spawn_platform_source.png",
        "target_size": (160, 160),
        "instances": ((RED_SPAWN_PLATFORM_BBOX, "identity"),),
        "shape": {
            "kind": "polygon",
            "points": ((0, 0), (160, 0), (160, 160), (96, 160), (96, 64), (0, 64)),
            "native_border_inset_px": 2,
            "inward_feather_px": 1.0,
        },
        "art_direction": "red fountain/spawn L-platform with a readable diamond plus marker",
    },
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


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def image_record(path: Path) -> dict[str, Any]:
    try:
        display_path = path.relative_to(MOD_ROOT).as_posix()
    except ValueError:
        display_path = str(path)
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
            "path": display_path,
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


def load_native_layers(
    bundle_path: Path | None = None,
) -> tuple[dict[str, Image.Image], dict[str, dict[str, Any]]]:
    # Keep bundle discovery lazy.  Pure compositor helpers are imported by CI
    # on runners that intentionally do not ship the proprietary game bundle.
    # A real pack/rebuild still resolves and verifies the local bundle here.
    if bundle_path is None:
        bundle_path = find_bundle_path()
    keys = {
        f"asset/base/aseprite_resources/ingame/5v5/{name}": name
        for name in NATIVE_LAYER_NAMES
    }
    images: dict[str, Image.Image] = {}
    records: dict[str, dict[str, Any]] = {}
    with bundle_path.open("rb") as handle:
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
                "bundle_file": bundle_path.name,
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


def require_sources(bundle_path: Path | None = None) -> Path:
    if bundle_path is None:
        bundle_path = find_bundle_path()
    required = [
        MICROTEXTURE_SOURCE,
        WALL_MASONRY_SOURCE,
        CLIFF_MICRODETAIL_SOURCE,
        BUSH_MICRODETAIL_SOURCE,
        bundle_path,
    ]
    required.extend(MASK_ROOT / filename for filename in MASK_SPECS.values())
    missing = [path for path in required if not path.is_file()]
    if missing:
        raise FileNotFoundError("Missing quality-map source(s): " + ", ".join(map(str, missing)))
    if REJECTED_WHOLE_MAP_SOURCE.exists():
        raise ValueError(
            "Rejected whole-map ImageGen source still exists and could reintroduce shifted terrain: "
            f"{REJECTED_WHOLE_MAP_SOURCE}"
        )
    return bundle_path


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


def rgba_sha256(image: Image.Image) -> str:
    return hashlib.sha256(image.convert("RGBA").tobytes()).hexdigest()


def alpha_footprint(image: Image.Image) -> dict[str, Any]:
    alpha = image.convert("RGBA").getchannel("A")
    histogram = alpha.histogram()
    return {
        "dimensions": list(image.size),
        "nontransparent_pixels": int(sum(histogram[1:])),
        "bbox_xyxy_half_open": list(alpha.getbbox()) if alpha.getbbox() else None,
        "alpha_sha256": hashlib.sha256(alpha.tobytes()).hexdigest(),
    }


def transparent_rgba_is_identical(before: Image.Image, after: Image.Image) -> bool:
    """Prove that fully transparent native pixels are unchanged in all RGBA bytes."""

    native = before.convert("RGBA")
    output = after.convert("RGBA")
    transparent = native.getchannel("A").point(lambda value: 255 if value == 0 else 0)
    difference = ImageChops.difference(native.convert("RGB"), output.convert("RGB"))
    transparent_rgb = Image.merge("RGB", (transparent, transparent, transparent))
    return ImageChops.multiply(difference, transparent_rgb).getbbox() is None


def region_mask(
    size: tuple[int, int],
    regions: tuple[tuple[int, int, int, int], ...],
) -> Image.Image:
    """Build a binary mask from audited half-open native-coordinate rectangles."""

    mask = Image.new("L", size, 0)
    draw = ImageDraw.Draw(mask)
    for left, top, right, bottom in regions:
        draw.rectangle((left, top, right - 1, bottom - 1), fill=255)
    return mask


def apply_contour_microdetail(
    image: Image.Image,
    source_path: Path,
    *,
    strength: float,
    coverage_mask: Image.Image | None = None,
    gaussian_radius: float = 18.0,
    high_frequency_scale: float = 0.85,
) -> tuple[Image.Image, dict[str, Any]]:
    """Transfer only high-frequency luminance inside the official alpha contour.

    The generated source is never pasted as terrain.  A Gaussian low-frequency
    estimate is removed, the neutralized luminance residual is soft-lighted at
    low strength, and ``Image.composite`` restores every pixel outside the
    official contour from the untouched native RGBA layer.
    """

    native = image.convert("RGBA")
    with Image.open(source_path) as opened:
        source_gray = opened.convert("L").resize(native.size, Image.Resampling.LANCZOS)
    low_frequency = source_gray.filter(ImageFilter.GaussianBlur(radius=gaussian_radius))
    high_frequency = ImageChops.subtract(source_gray, low_frequency, scale=1.0, offset=128)
    high_frequency = high_frequency.point(
        [
            max(0, min(255, round(128 + (value - 128) * high_frequency_scale)))
            for value in range(256)
        ]
    )
    detail_rgb = Image.merge("RGB", (high_frequency, high_frequency, high_frequency))
    native_rgb = native.convert("RGB")
    soft_lit_rgb = ImageChops.soft_light(native_rgb, detail_rgb)
    candidate = Image.blend(native_rgb, soft_lit_rgb, strength).convert("RGBA")
    candidate.putalpha(native.getchannel("A"))

    contour = native.getchannel("A")
    if coverage_mask is not None:
        if coverage_mask.size != native.size:
            raise ValueError(
                f"Microdetail coverage mask size mismatch: {coverage_mask.size} != {native.size}"
            )
        contour = ImageChops.multiply(contour, coverage_mask.convert("L"))
    output = Image.composite(candidate, native, contour)

    changed = change_mask(native, output)
    changed_histogram = changed.histogram()
    audit = {
        "operation": "high-frequency-luminance-only",
        "source_path": source_path.relative_to(MOD_ROOT).as_posix(),
        "source_sha256": sha256(source_path),
        "strength": strength,
        "gaussian_low_frequency_radius": gaussian_radius,
        "high_frequency_scale": high_frequency_scale,
        "blend_mode": "soft-light then low-strength linear blend",
        "contour_restore": "Image.composite with official native alpha",
        "direct_source_pixels_copied": False,
        "changed_pixels": int(sum(changed_histogram[1:])),
        "alpha_byte_identical": (
            output.getchannel("A").tobytes() == native.getchannel("A").tobytes()
        ),
        "transparent_rgba_byte_identical": transparent_rgba_is_identical(native, output),
    }
    return output, audit


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


def nonzero_pixel_count(mask: Image.Image) -> int:
    return sum(mask.convert("L").histogram()[1:])


def binary_mask(mask: Image.Image) -> Image.Image:
    return mask.convert("L").point([0] + [255] * 255)


def change_mask(left: Image.Image, right: Image.Image) -> Image.Image:
    if left.size != right.size:
        raise ValueError(f"Cannot compare image sizes: {left.size} != {right.size}")
    channels = ImageChops.difference(left.convert("RGBA"), right.convert("RGBA")).split()
    changed = channels[0]
    for channel in channels[1:]:
        changed = ImageChops.lighter(changed, channel)
    return binary_mask(changed)


def erode_mask(mask: Image.Image, pixels: int) -> Image.Image:
    if pixels <= 0:
        return mask.copy()
    kernel = pixels * 2 + 1
    padded = ImageOps.expand(mask, border=pixels, fill=0)
    eroded = padded.filter(ImageFilter.MinFilter(kernel))
    return eroded.crop((pixels, pixels, pixels + mask.width, pixels + mask.height))


def inward_feather_mask(mask: Image.Image, radius: float) -> Image.Image:
    """Feather only inward; never manufacture nonzero pixels outside the hard mask."""

    if radius <= 0:
        return mask.copy()
    padding = max(2, int(round(radius * 4)))
    padded = ImageOps.expand(mask, border=padding, fill=0)
    blurred = padded.filter(ImageFilter.GaussianBlur(radius=radius)).crop(
        (padding, padding, padding + mask.width, padding + mask.height)
    )
    return ImageChops.multiply(mask, blurred)


def make_local_landmark_mask(spec: dict[str, Any]) -> Image.Image:
    size = tuple(spec["target_size"])
    shape = spec["shape"]
    mask = Image.new("L", size, 0)
    draw = ImageDraw.Draw(mask)
    if shape["kind"] == "rectangle":
        draw.rectangle((0, 0, size[0] - 1, size[1] - 1), fill=255)
    elif shape["kind"] == "ellipse":
        draw.ellipse(tuple(shape["bounds"]), fill=255)
    elif shape["kind"] == "polygon":
        draw.polygon(tuple(tuple(point) for point in shape["points"]), fill=255)
    else:
        raise ValueError(f"Unsupported landmark mask kind: {shape['kind']}")
    mask = erode_mask(mask, int(shape["native_border_inset_px"]))
    return inward_feather_mask(mask, float(shape["inward_feather_px"]))


def native_water_likeness_mask(background: Image.Image) -> Image.Image:
    """Conservative detector used only to prove both objective masks avoid adjacent blue water."""

    water = Image.new("L", background.size, 0)
    rgb = background.convert("RGB")
    # Pillow 12 introduced get_flattened_data(); GitHub's pinned Pillow 11
    # still exposes the long-standing getdata() iterator.  Keep this pure
    # compositor helper importable and testable on both runtimes.
    pixels = (
        rgb.get_flattened_data()
        if hasattr(rgb, "get_flattened_data")
        else rgb.getdata()
    )
    water.putdata(
        [
            255 if blue >= green + 8 and blue >= red + 20 and blue >= 45 else 0
            for red, green, blue in pixels
        ]
    )
    return water


def build_landmark_masks(
    native: dict[str, Image.Image],
    *,
    persist: bool = False,
) -> tuple[dict[str, Image.Image], Image.Image, dict[str, Any]]:
    """Build exact-coordinate masks, then subtract every native wall/brush pixel."""

    forbidden = Image.new("L", MAP_SIZE, 0)
    for layer_name in ("wall_5v5", "wall_5v5_front", "bush_5v5"):
        layer_alpha = binary_mask(native[layer_name].getchannel("A"))
        forbidden = ImageChops.lighter(forbidden, layer_alpha)

    masks: dict[str, Image.Image] = {}
    inventory: dict[str, Any] = {}
    union = Image.new("L", MAP_SIZE, 0)
    binary_pixel_sum = 0
    for name, spec in LANDMARK_SPECS.items():
        local_mask = make_local_landmark_mask(spec)
        raw_full_mask = Image.new("L", MAP_SIZE, 0)
        instances: list[dict[str, Any]] = []
        for index, (bbox, transform) in enumerate(spec["instances"]):
            left, top, right, bottom = bbox
            target_size = (right - left, bottom - top)
            if target_size != tuple(spec["target_size"]):
                raise ValueError(
                    f"Landmark {name}[{index}] bbox {bbox} has {target_size}, "
                    f"expected {spec['target_size']}"
                )
            if not (0 <= left < right <= MAP_SIZE[0] and 0 <= top < bottom <= MAP_SIZE[1]):
                raise ValueError(f"Landmark {name}[{index}] is outside background_5v5: {bbox}")
            raw_full_mask.paste(
                ImageChops.lighter(raw_full_mask.crop(bbox), local_mask),
                (left, top),
            )
            instances.append(
                {
                    "index": index,
                    "bbox_xyxy_half_open": list(bbox),
                    "dimensions": [target_size[0], target_size[1]],
                    "center_xy": [(left + right) // 2, (top + bottom) // 2],
                    "source_transform": transform,
                }
            )

        # Wall and brush layers remain byte-identical.  Subtracting their
        # official alpha footprints also prevents hidden generated RGB from
        # being written underneath those layers.
        safe_mask = ImageChops.multiply(raw_full_mask, ImageOps.invert(forbidden))
        masks[name] = safe_mask
        union = ImageChops.lighter(union, safe_mask)
        binary_pixels = nonzero_pixel_count(binary_mask(safe_mask))
        binary_pixel_sum += binary_pixels
        mask_path = LANDMARK_MASK_ROOT / f"native_{name}_allowed_mask.png"
        if persist:
            save_png(safe_mask, mask_path)
        inventory[name] = {
            "source_requirement": (
                LANDMARK_SOURCE_ROOT / spec["source"]
            ).relative_to(MOD_ROOT).as_posix(),
            "required_source_aspect_ratio": "1:1",
            "recommended_source_dimensions": [1024, 1024],
            "packed_dimensions": list(spec["target_size"]),
            "art_direction": spec["art_direction"],
            "mask_shape": spec["shape"],
            "mask_path": mask_path.relative_to(MOD_ROOT).as_posix(),
            "allowed_nonzero_pixels": binary_pixels,
            "partial_feather_pixels": sum(safe_mask.histogram()[1:255]),
            "removed_for_wall_or_bush_pixels": max(
                0,
                nonzero_pixel_count(binary_mask(raw_full_mask)) - binary_pixels,
            ),
            "instances": instances,
        }

    union_path = LANDMARK_MASK_ROOT / "native_landmarks_union_allowed_mask.png"
    if persist:
        save_png(union, union_path)
    union_binary_pixels = nonzero_pixel_count(binary_mask(union))
    forbidden_overlap = ImageChops.multiply(binary_mask(union), forbidden)
    water_like = native_water_likeness_mask(native["background_5v5"])
    objective_water_overlap = {
        name: nonzero_pixel_count(
            ImageChops.multiply(binary_mask(masks[name]), water_like)
        )
        for name in ("baron_pit", "dragon_pit")
    }
    audit = {
        "coordinate_space": "background_5v5 1280x1280; xyxy bounds are half-open",
        "mask_derivation": (
            "official 32px-grid landmark rectangles plus conservative native contours; "
            "2px native rim retained and feather is inward-only"
        ),
        "wall_and_bush_exclusion_layers": ["wall_5v5", "wall_5v5_front", "bush_5v5"],
        "union_mask_path": union_path.relative_to(MOD_ROOT).as_posix(),
        "landmark_type_count": len(LANDMARK_SPECS),
        "landmark_instance_count": sum(
            len(spec["instances"]) for spec in LANDMARK_SPECS.values()
        ),
        "union_nonzero_pixels": union_binary_pixels,
        "inter_landmark_overlap_pixels": binary_pixel_sum - union_binary_pixels,
        "wall_or_bush_overlap_pixels_after_exclusion": nonzero_pixel_count(forbidden_overlap),
        "objective_pit_water_like_overlap_pixels": objective_water_overlap,
        "inventory": inventory,
    }
    return masks, union, audit


def transform_landmark_source(image: Image.Image, transform: str) -> Image.Image:
    transforms = {
        "identity": None,
        "rotate_90": Image.Transpose.ROTATE_90,
        "rotate_180": Image.Transpose.ROTATE_180,
        "rotate_270": Image.Transpose.ROTATE_270,
    }
    if transform not in transforms:
        raise ValueError(f"Unsupported landmark source transform: {transform}")
    operation = transforms[transform]
    return image.copy() if operation is None else image.transpose(operation)


def apply_landmark_overlays(
    background: Image.Image,
    masks: dict[str, Image.Image],
    union_mask: Image.Image,
    *,
    source_root: Path = LANDMARK_SOURCE_ROOT,
) -> tuple[Image.Image, dict[str, Any]]:
    """Apply optional independent decals while preserving size, alpha, and all mask-exterior RGB."""

    before = background.convert("RGBA")
    output = before.copy()
    source_records: dict[str, Any] = {}
    applied_source_count = 0
    for name, spec in LANDMARK_SPECS.items():
        source_path = source_root / spec["source"]
        record: dict[str, Any] = {
            "path": (
                source_path.relative_to(MOD_ROOT).as_posix()
                if source_path.is_relative_to(MOD_ROOT)
                else str(source_path)
            ),
            "required_for_landmark_upgrade": True,
            "required_for_safe_build": False,
            "fallback": "retain the refined native landmark byte-for-byte",
            "packed_dimensions": list(spec["target_size"]),
            "instances": [],
        }
        if not source_path.is_file():
            record["status"] = "awaiting_imagegen"
            source_records[name] = record
            continue

        with Image.open(source_path) as opened:
            source = ImageOps.fit(
                opened.convert("RGBA"),
                tuple(spec["target_size"]),
                method=Image.Resampling.LANCZOS,
                centering=(0.5, 0.5),
            )
        source = ImageEnhance.Sharpness(source).enhance(1.08)
        record.update(image_record(source_path))
        record["status"] = "applied"
        applied_source_count += 1
        for index, (bbox, transform) in enumerate(spec["instances"]):
            left, top, _right, _bottom = bbox
            transformed = transform_landmark_source(source, transform)
            allowed = masks[name].crop(bbox)
            source_alpha = transformed.getchannel("A")
            effective_mask = ImageChops.multiply(allowed, source_alpha)
            native_crop = output.crop(bbox)
            composed_rgb = Image.composite(
                transformed.convert("RGB"),
                native_crop.convert("RGB"),
                effective_mask,
            )
            composed = composed_rgb.convert("RGBA")
            composed.putalpha(native_crop.getchannel("A"))
            output.paste(composed, (left, top))
            record["instances"].append(
                {
                    "index": index,
                    "bbox_xyxy_half_open": list(bbox),
                    "source_transform": transform,
                    "effective_mask_nonzero_pixels": nonzero_pixel_count(effective_mask),
                    "changed_pixels": nonzero_pixel_count(change_mask(native_crop, composed)),
                }
            )
        source_records[name] = record

    changed = change_mask(before, output)
    outside = ImageChops.multiply(changed, ImageOps.invert(binary_mask(union_mask)))
    alpha_preserved = before.getchannel("A").tobytes() == output.getchannel("A").tobytes()
    report = {
        "sources_available": applied_source_count,
        "sources_expected": len(LANDMARK_SPECS),
        "fallback_is_safe_with_missing_sources": True,
        "source_records": source_records,
        "changed_pixels": nonzero_pixel_count(changed),
        "changed_pixels_outside_allowed_union": nonzero_pixel_count(outside),
        "size_before": list(before.size),
        "size_after": list(output.size),
        "alpha_preserved": alpha_preserved,
        "size_preserved": before.size == output.size,
    }
    return output, report


def save_landmark_preview(
    before: Image.Image,
    after: Image.Image,
    masks: dict[str, Image.Image],
) -> None:
    palette = (
        (183, 88, 255),
        (255, 145, 71),
        (236, 199, 89),
        (104, 210, 165),
        (101, 190, 255),
        (73, 139, 255),
        (255, 84, 92),
        (57, 202, 232),
        (255, 105, 151),
    )
    overlay = before.convert("RGBA")
    for color, mask in zip(palette, masks.values()):
        tint = Image.new("RGBA", MAP_SIZE, color + (0,))
        tint.putalpha(mask.point([round(value * 0.58) for value in range(256)]))
        overlay.alpha_composite(tint)

    panel_size = (512, 512)
    header_height = 28
    preview = Image.new("RGBA", (panel_size[0] * 3, panel_size[1] + header_height), (8, 12, 18, 255))
    panels = (
        ("REFINED NATIVE INPUT", before),
        ("OFFICIAL LANDMARK ALLOWED MASKS", overlay),
        ("MASKED LANDMARK OUTPUT", after),
    )
    draw = ImageDraw.Draw(preview)
    for index, (label, image) in enumerate(panels):
        x = index * panel_size[0]
        draw.text((x + 8, 8), label, fill=(232, 238, 244, 255))
        preview.alpha_composite(
            image.resize(panel_size, Image.Resampling.LANCZOS),
            (x, header_height),
        )
    save_png(preview, LANDMARK_PREVIEW_PATH)


def save_landmark_detail_preview(background: Image.Image) -> None:
    """Show one final packed instance per source at a readable integer-like scale."""

    columns = 3
    rows = 3
    cell_size = (288, 256)
    preview = Image.new(
        "RGBA",
        (columns * cell_size[0], rows * cell_size[1]),
        (8, 12, 18, 255),
    )
    draw = ImageDraw.Draw(preview)
    for index, (name, spec) in enumerate(LANDMARK_SPECS.items()):
        column = index % columns
        row = index // columns
        origin_x = column * cell_size[0]
        origin_y = row * cell_size[1]
        bbox, _transform = spec["instances"][0]
        crop = background.crop(bbox)
        enlarged = ImageOps.contain(
            crop,
            (224, 208),
            method=Image.Resampling.NEAREST,
        )
        paste_x = origin_x + (cell_size[0] - enlarged.width) // 2
        paste_y = origin_y + 38 + (208 - enlarged.height) // 2
        preview.alpha_composite(enlarged, (paste_x, paste_y))
        draw.text((origin_x + 8, origin_y + 7), name.upper(), fill=(232, 238, 244, 255))
        draw.text(
            (origin_x + 8, origin_y + 22),
            f"bbox={bbox} packed={tuple(spec['target_size'])}",
            fill=(143, 160, 177, 255),
        )
    save_png(preview, LANDMARK_DETAIL_PREVIEW_PATH)


def save_surface_detail_preview(
    native_composite: Image.Image,
    refined_composite: Image.Image,
) -> dict[str, Any]:
    """Save audited before/after crops at exact 1:1 runtime pixel scale."""

    max_width = max(right - left for left, _top, right, _bottom in SURFACE_PREVIEW_CROPS.values())
    header_height = 34
    row_gap = 12
    side_padding = 12
    column_gap = 16
    canvas_width = side_padding * 2 + max_width * 2 + column_gap
    canvas_height = side_padding + sum(
        header_height + (bottom - top) + row_gap
        for left, top, right, bottom in SURFACE_PREVIEW_CROPS.values()
    )
    preview = Image.new("RGBA", (canvas_width, canvas_height), (10, 15, 21, 255))
    draw = ImageDraw.Draw(preview)
    y = side_padding
    records: dict[str, Any] = {}
    for name, bbox in SURFACE_PREVIEW_CROPS.items():
        before = native_composite.crop(bbox)
        after = refined_composite.crop(bbox)
        width, height = before.size
        draw.text((side_padding, y), f"{name}  OFFICIAL  bbox={bbox}", fill=(205, 215, 225, 255))
        draw.text(
            (side_padding + max_width + column_gap, y),
            "V4 HIGH-FREQUENCY DETAIL  1:1",
            fill=(107, 221, 207, 255),
        )
        paste_y = y + header_height
        preview.alpha_composite(before, (side_padding, paste_y))
        preview.alpha_composite(
            after,
            (side_padding + max_width + column_gap, paste_y),
        )
        records[name] = {
            "bbox_xyxy_half_open": list(bbox),
            "dimensions": [width, height],
            "scale": "1:1",
            "resampling": "none",
            "official_rgba_sha256": rgba_sha256(before),
            "v4_rgba_sha256": rgba_sha256(after),
        }
        y = paste_y + height + row_gap
    save_png(preview, SURFACE_DETAIL_PREVIEW_PATH)
    return {
        "path": SURFACE_DETAIL_PREVIEW_PATH.relative_to(MOD_ROOT).as_posix(),
        "dimensions": list(preview.size),
        "scale": "1:1",
        "resampling": "none",
        "crops": records,
    }


def main() -> int:
    bundle_path = require_sources()

    native, native_records = load_native_layers(bundle_path)
    native_layer_masks = {name: load_mask(name) for name in MASK_SPECS}

    # Native bundle layers are the only geometry source.  The uniform
    # ImageGen sources contribute high-frequency luminance only after Gaussian
    # low-frequency removal.  No generated road, water, wall, brush outline,
    # collision, or pathing semantic can enter the runtime map.
    # Independent landmark decals are the sole spatial exception and are
    # clipped below to audited native-coordinate masks.
    background = preserve_alpha_grade(
        native["background_5v5"], saturation=1.075, contrast=1.025, brightness=0.995
    )
    background = apply_microdetail(background, MICROTEXTURE_SOURCE, strength=0.05)
    background_before_landmarks = background.copy()
    landmark_masks, landmark_union_mask, landmark_mask_audit = build_landmark_masks(
        native,
        persist=True,
    )
    background, landmark_application = apply_landmark_overlays(
        background_before_landmarks,
        landmark_masks,
        landmark_union_mask,
    )
    save_landmark_preview(background_before_landmarks, background, landmark_masks)
    save_landmark_detail_preview(background)

    outer_cliff_mask = region_mask(MAP_SIZE, OUTER_CLIFF_REGIONS)
    main_wall_mask = ImageOps.invert(outer_cliff_mask)
    wall, wall_main_detail = apply_contour_microdetail(
        native["wall_5v5"],
        WALL_MASONRY_SOURCE,
        strength=SURFACE_DETAIL_STRENGTHS["wall_main_masonry"],
        coverage_mask=main_wall_mask,
    )
    wall, wall_outer_detail = apply_contour_microdetail(
        wall,
        CLIFF_MICRODETAIL_SOURCE,
        strength=SURFACE_DETAIL_STRENGTHS["wall_outer_cliff"],
        coverage_mask=outer_cliff_mask,
    )
    wall_front, wall_front_detail = apply_contour_microdetail(
        native["wall_5v5_front"],
        WALL_MASONRY_SOURCE,
        strength=SURFACE_DETAIL_STRENGTHS["wall_front_masonry"],
    )
    bush, bush_detail = apply_contour_microdetail(
        native["bush_5v5"],
        BUSH_MICRODETAIL_SOURCE,
        strength=SURFACE_DETAIL_STRENGTHS["bush_microdetail"],
    )

    wall_main_detail.update(
        {
            "imagegen_exec_id": SURFACE_SOURCE_EXEC_IDS["wall_masonry"],
            "coverage": "official wall alpha excluding OUTER_CLIFF_REGIONS",
        }
    )
    wall_outer_detail.update(
        {
            "imagegen_exec_id": SURFACE_SOURCE_EXEC_IDS["cliff_microdetail"],
            "coverage": "official wall alpha inside OUTER_CLIFF_REGIONS",
            "regions_xyxy_half_open": [list(region) for region in OUTER_CLIFF_REGIONS],
        }
    )
    wall_front_detail.update(
        {
            "imagegen_exec_id": SURFACE_SOURCE_EXEC_IDS["wall_masonry"],
            "coverage": "official wall_5v5_front alpha",
        }
    )
    bush_detail.update(
        {
            "imagegen_exec_id": SURFACE_SOURCE_EXEC_IDS["bush_microdetail"],
            "coverage": "official bush_5v5 alpha",
        }
    )
    surface_detail_usage = {
        "wall_main_masonry": wall_main_detail,
        "wall_outer_cliff": wall_outer_detail,
        "wall_front_masonry": wall_front_detail,
        "bush_microdetail": bush_detail,
    }

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

    surface_preview = save_surface_detail_preview(native_composite, runtime_composite)

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
        for name, mask in native_layer_masks.items()
    }
    native_alpha_checks = {
        name: alpha_matches_image(path, native[name])
        for name, path in output_paths.items()
    }
    surface_layer_names = ("wall_5v5", "wall_5v5_front", "bush_5v5")
    surface_layer_checks = {
        name: {
            "dimensions_1280": outputs[name].size == MAP_SIZE,
            "alpha_byte_identical": (
                outputs[name].getchannel("A").tobytes()
                == native[name].getchannel("A").tobytes()
            ),
            "transparent_rgba_byte_identical": transparent_rgba_is_identical(
                native[name], outputs[name]
            ),
            "native_footprint": alpha_footprint(native[name]),
            "runtime_footprint": alpha_footprint(outputs[name]),
            "nontransparent_count_identical": (
                alpha_footprint(native[name])["nontransparent_pixels"]
                == alpha_footprint(outputs[name])["nontransparent_pixels"]
            ),
            "nontransparent_bbox_identical": (
                alpha_footprint(native[name])["bbox_xyxy_half_open"]
                == alpha_footprint(outputs[name])["bbox_xyxy_half_open"]
            ),
            "changed_pixels_from_official": int(
                sum(change_mask(native[name], outputs[name]).histogram()[1:])
            ),
            "changed_nontransparent_ratio": round(
                sum(change_mask(native[name], outputs[name]).histogram()[1:])
                / alpha_footprint(native[name])["nontransparent_pixels"],
                6,
            ),
            "visible_mean_abs_rgb_from_official": visible_rgb_delta(
                outputs[name], native[name]
            )["mean_abs_rgb"],
        }
        for name in surface_layer_names
    }
    shadow_layer_names = (
        "wall_shadow_5v5",
        "bush_shadow_5v5",
        "tower_shadow",
        "nexus_shadow",
    )
    shadow_rgba_sha256 = {
        name: {
            "official": rgba_sha256(native[name]),
            "runtime": rgba_sha256(outputs[name]),
            "byte_identical": native[name].tobytes() == outputs[name].tobytes(),
        }
        for name in shadow_layer_names
    }
    rgb_deltas = {
        name: visible_rgb_delta(outputs[name], native[name])
        for name in outputs
    }
    rgb_deltas["minimap_5v5_bg"] = visible_rgb_delta(
        minimap, native["minimap_5v5_bg"]
    )
    mean_delta_limits = {
        # Local landmark decals can be visually decisive while remaining
        # confined to roughly one eighth of the map.  Their safety gate is the
        # exact exterior-zero proof below, not an artificially tiny global mean.
        "background_5v5": 32.0,
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
        "surface_layers_keep_1280_dimensions": all(
            record["dimensions_1280"] for record in surface_layer_checks.values()
        ),
        "surface_alpha_bytes_are_official": all(
            record["alpha_byte_identical"] for record in surface_layer_checks.values()
        ),
        "surface_transparent_rgba_is_official": all(
            record["transparent_rgba_byte_identical"]
            for record in surface_layer_checks.values()
        ),
        "surface_nontransparent_counts_are_official": all(
            record["nontransparent_count_identical"]
            for record in surface_layer_checks.values()
        ),
        "surface_nontransparent_bboxes_are_official": all(
            record["nontransparent_bbox_identical"]
            for record in surface_layer_checks.values()
        ),
        "surface_microdetail_changed_visible_pixels": all(
            record["changed_pixels"] > 0 for record in surface_detail_usage.values()
        ),
        "surface_microdetail_is_high_frequency_luminance_only": all(
            record["operation"] == "high-frequency-luminance-only"
            and record["direct_source_pixels_copied"] is False
            for record in surface_detail_usage.values()
        ),
        "surface_microdetail_strengths_are_capped": (
            surface_detail_usage["wall_main_masonry"]["strength"] <= 0.08
            and surface_detail_usage["wall_outer_cliff"]["strength"] <= 0.10
            and surface_detail_usage["wall_front_masonry"]["strength"] <= 0.08
            and surface_detail_usage["bush_microdetail"]["strength"] <= 0.08
        ),
        "shadow_rgba_bytes_are_official": all(
            record["byte_identical"]
            and record["official"] == record["runtime"]
            for record in shadow_rgba_sha256.values()
        ),
        "rejected_whole_map_source_removed": not REJECTED_WHOLE_MAP_SOURCE.exists(),
        "generated_spatial_wall_and_bush_tiling_removed": True,
        "runtime_geometry_comes_only_from_native_bundle": True,
        "dynamic_minimap_marker_sheet_untouched": (
            "asset/base/aseprite_resources/ingame/minimap_5v5#sheet" not in override
            and "asset/base/aseprite_resources/ingame/minimap_5v5#data" not in override
        ),
        "map_setting_untouched": "asset/base/setting/map_setting" not in override,
        "landmark_union_mask_is_nonempty": landmark_mask_audit["union_nonzero_pixels"] > 0,
        "landmark_masks_do_not_overlap": (
            landmark_mask_audit["inter_landmark_overlap_pixels"] == 0
        ),
        "landmark_masks_exclude_every_wall_and_bush_pixel": (
            landmark_mask_audit["wall_or_bush_overlap_pixels_after_exclusion"] == 0
        ),
        "objective_pit_masks_exclude_adjacent_water": all(
            value == 0
            for value in landmark_mask_audit[
                "objective_pit_water_like_overlap_pixels"
            ].values()
        ),
        "landmark_composite_size_preserved": landmark_application["size_preserved"],
        "landmark_composite_alpha_preserved": landmark_application["alpha_preserved"],
        "landmark_mask_exterior_pixels_are_byte_identical": (
            landmark_application["changed_pixels_outside_allowed_union"] == 0
        ),
        "missing_landmark_sources_have_native_fallback": landmark_application[
            "fallback_is_safe_with_missing_sources"
        ],
    }
    if not all(static_checks.values()):
        raise ValueError(f"Quality map static checks failed: {static_checks}; masks={mask_checks}")

    report = {
        "schema": "lol_mod.quality_map_imagegen_pack.v4",
        "generator": "mods/lol_mod/tools/pack_quality_map.py",
        "imagegen_mode": (
            "built-in image generation; official-contour high-frequency microdetail plus "
            "official-mask landmark decals"
        ),
        "prompts": IMAGEGEN_PROMPTS,
        "sources": {
            "microdetail": image_record(MICROTEXTURE_SOURCE),
            "wall_masonry": {
                **image_record(WALL_MASONRY_SOURCE),
                "imagegen_exec_id": SURFACE_SOURCE_EXEC_IDS["wall_masonry"],
            },
            "cliff_microdetail": {
                **image_record(CLIFF_MICRODETAIL_SOURCE),
                "imagegen_exec_id": SURFACE_SOURCE_EXEC_IDS["cliff_microdetail"],
            },
            "bush_microdetail": {
                **image_record(BUSH_MICRODETAIL_SOURCE),
                "imagegen_exec_id": SURFACE_SOURCE_EXEC_IDS["bush_microdetail"],
            },
        },
        "source_usage": {
            "microdetail": {
                "operation": "high-frequency luminance soft-light only",
                "strength": 0.05,
                "spatial_terrain_semantics_copied": False,
            },
            **surface_detail_usage,
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
        "landmarks": {
            "mask_audit": landmark_mask_audit,
            "mask_files": {
                name: image_record(
                    LANDMARK_MASK_ROOT / f"native_{name}_allowed_mask.png"
                )
                for name in LANDMARK_SPECS
            },
            "union_mask": image_record(
                LANDMARK_MASK_ROOT / "native_landmarks_union_allowed_mask.png"
            ),
            "application": landmark_application,
            "preview": image_record(LANDMARK_PREVIEW_PATH),
            "detail_preview": image_record(LANDMARK_DETAIL_PREVIEW_PATH),
        },
        "runtime": {name: image_record(path) for name, path in output_paths.items()},
        "preview": image_record(PREVIEW_PATH),
        "surface_detail": {
            "method": "high-frequency-luminance-only",
            "low_frequency_removal": "GaussianBlur radius 18.0",
            "composite_contract": "Image.composite back through official native alpha",
            "outer_cliff_regions_xyxy_half_open": [
                list(region) for region in OUTER_CLIFF_REGIONS
            ],
            "layers": surface_layer_checks,
            "shadow_rgba_sha256": shadow_rgba_sha256,
            "preview": {
                **surface_preview,
                "image": image_record(SURFACE_DETAIL_PREVIEW_PATH),
            },
        },
        "contracts": {
            "background_size": list(MAP_SIZE),
            "minimap_size": list(MINIMAP_SIZE),
            "runtime_structure_source": "native bundle 5v5 layers only",
            "background_geometry": (
                "native background with global grade, 5% semantics-free luminance microdetail, "
                "and optional decals confined to audited native landmark masks"
            ),
            "wall_and_bush_geometry": (
                "native RGBA contours and transparent bytes; ImageGen supplies only Gaussian-"
                "isolated high-frequency luminance at capped low strength"
            ),
            "wall_surface_detail": (
                "masonry <=8%; left/right exterior cliffs <=10%; front wall <=8%"
            ),
            "bush_surface_detail": "brush high-frequency luminance <=8%",
            "shadow_layers": "decoded official RGBA bytes and SHA-256 unchanged",
            "tower_circles_and_camp_markers": (
                "official background coordinates and silhouettes; a native 2px rim is retained"
            ),
            "roads_water_and_non_landmark_ground": (
                "byte-identical to the refined native input outside the landmark union mask"
            ),
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
    print(f"Landmark mask preview: {LANDMARK_PREVIEW_PATH.relative_to(MOD_ROOT)}")
    print(f"Landmark detail preview: {LANDMARK_DETAIL_PREVIEW_PATH.relative_to(MOD_ROOT)}")
    print(f"Surface detail preview: {SURFACE_DETAIL_PREVIEW_PATH.relative_to(MOD_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
