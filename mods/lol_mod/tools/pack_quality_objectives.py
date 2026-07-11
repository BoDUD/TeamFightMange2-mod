from __future__ import annotations

import hashlib
import io
import json
import math
import shutil
import struct
from pathlib import Path
from typing import Any

from PIL import Image


MOD_ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = MOD_ROOT / "source" / "imagegen" / "jungle"
PROCESSED_DIR = MOD_ROOT / "source" / "processed" / "jungle"
INGAME_DIR = MOD_ROOT / "aseprite_resources" / "ingame"
VARIANT_DIR = INGAME_DIR / "dragon_variants"
QA_PATH = MOD_ROOT / "qa" / "quality_objectives_imagegen_pack.json"

GRID_COLS = 4
GRID_ROWS = 4
# Runtime actors are positioned against the native animation rectangles, not
# against an arbitrary replacement canvas.  The old quality pack used 218px
# and 115px square cells, which made Baron roughly twice as wide as the native
# actor and made Drake idle frames slide more than twelve pixels side-to-side.
# These caps are the visible alpha envelopes from the bundled native sheets.
BARON_NATIVE_VISIBLE_WIDTH = 106
DRAGON_NATIVE_VISIBLE_WIDTH = 54
CHROMA_KEY = (255, 0, 255)
CHROMA_CLEAR_DISTANCE = 82.0
CHROMA_EDGE_BAND_DEPTH = 3

DRAGON_VARIANTS = (
    "infernal",
    "ocean",
    "mountain",
    "cloud",
    "hextech",
    "elder",
)


def find_bundle_path() -> Path:
    candidates = (
        MOD_ROOT.parents[1] / "bundle.game_data",
        MOD_ROOT.parents[2] / "bundle.game_data",
    )
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    raise FileNotFoundError(
        "Could not locate Teamfight Manager 2 bundle.game_data from the mod tree: "
        + ", ".join(str(candidate) for candidate in candidates)
    )


BUNDLE_PATH = find_bundle_path()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_u32(handle: Any) -> int:
    raw = handle.read(4)
    if len(raw) != 4:
        raise EOFError("Unexpected end of bundle.game_data while reading u32")
    return struct.unpack("<I", raw)[0]


def load_native_animation_contracts(
    runtime_names: tuple[str, ...],
) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    keys = {
        f"asset/base/aseprite_resources/ingame/{name}#anim": name
        for name in runtime_names
    }
    documents: dict[str, dict[str, Any]] = {}
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
            runtime_name = keys[key]
            document = json.loads(payload.decode("utf-8"))
            documents[runtime_name] = document
            records[runtime_name] = {
                "bundle_file": BUNDLE_PATH.name,
                "bundle_size_bytes": BUNDLE_PATH.stat().st_size,
                "asset_key": key,
                "asset_type": asset_type,
                "entry_size_bytes": data_length,
                "entry_sha256": hashlib.sha256(payload).hexdigest(),
                "tag_order": list(document["anims"]),
                "tags": animation_contract_signature(document),
            }
            if len(documents) == len(keys):
                break
    missing = sorted(set(runtime_names) - set(documents))
    if missing:
        raise KeyError(f"Missing native animation contracts in bundle.game_data: {missing}")
    return documents, records


def load_native_sheets(
    runtime_names: tuple[str, ...],
) -> tuple[dict[str, Image.Image], dict[str, dict[str, Any]]]:
    keys = {
        f"asset/base/aseprite_resources/ingame/{name}#sheet": name
        for name in runtime_names
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
            runtime_name = keys[key]
            with Image.open(io.BytesIO(payload)) as opened:
                images[runtime_name] = opened.convert("RGBA")
            records[runtime_name] = {
                "bundle_file": BUNDLE_PATH.name,
                "bundle_size_bytes": BUNDLE_PATH.stat().st_size,
                "asset_key": key,
                "asset_type": asset_type,
                "entry_size_bytes": data_length,
                "entry_sha256": hashlib.sha256(payload).hexdigest(),
                "dimensions": list(images[runtime_name].size),
            }
            if len(images) == len(keys):
                break
    missing = sorted(set(runtime_names) - set(images))
    if missing:
        raise KeyError(f"Missing native sheets in bundle.game_data: {missing}")
    return images, records


def animation_contract_signature(document: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        tag_name: {
            "frame_count": len(tag["frames"]),
            "durations": [frame["duration"] for frame in tag["frames"]],
        }
        for tag_name, tag in document["anims"].items()
    }


def validate_native_animation_contract(
    runtime_name: str,
    generated: dict[str, Any],
    native: dict[str, Any],
) -> None:
    generated_order = list(generated["anims"])
    native_order = list(native["anims"])
    if generated_order != native_order:
        raise ValueError(
            f"{runtime_name}: tag order/name mismatch; "
            f"generated={generated_order}, native={native_order}"
        )
    generated_signature = animation_contract_signature(generated)
    native_signature = animation_contract_signature(native)
    if generated_signature != native_signature:
        raise ValueError(
            f"{runtime_name}: frame-count/duration contract mismatch; "
            f"generated={generated_signature}, native={native_signature}"
        )


def validate_native_frame_rect_contract(
    runtime_name: str,
    generated: dict[str, Any],
    native: dict[str, Any],
) -> None:
    validate_native_animation_contract(runtime_name, generated, native)
    if generated != native:
        raise ValueError(
            f"{runtime_name}: native frame rectangles changed; replacements must "
            "keep every bundled x/y/w/h value exactly"
        )


def frame_rect(frame: dict[str, Any]) -> tuple[int, int, int, int]:
    data = frame["data"]
    return (
        int(data["x"]),
        int(data["y"]),
        int(data["w"]),
        int(data["h"]),
    )


def frame_crop(sheet: Image.Image, frame: dict[str, Any]) -> Image.Image:
    x, y, width, height = frame_rect(frame)
    return sheet.crop((x, y, x + width, y + height))


def weighted_alpha_centroid_x(image: Image.Image) -> float:
    alpha = image.getchannel("A")
    total = 0
    weighted_x = 0
    for y in range(alpha.height):
        for x in range(alpha.width):
            value = alpha.getpixel((x, y))
            total += value
            weighted_x += x * value
    if total <= 0:
        return (image.width - 1) / 2
    return weighted_x / total


def ground_anchor_x(image: Image.Image) -> float:
    alpha = image.getchannel("A")
    bbox = alpha.getbbox()
    if bbox is None:
        return (image.width - 1) / 2
    band_height = max(2, round((bbox[3] - bbox[1]) * 0.12))
    band_top = max(bbox[1], bbox[3] - band_height)
    total = 0
    weighted_x = 0
    for y in range(band_top, bbox[3]):
        for x in range(bbox[0], bbox[2]):
            value = alpha.getpixel((x, y))
            total += value
            weighted_x += x * value
    if total <= 0:
        return weighted_alpha_centroid_x(image)
    return weighted_x / total


def normalize_hard_alpha(image: Image.Image) -> Image.Image:
    rgba = image.convert("RGBA")
    output = Image.new("RGBA", rgba.size, (0, 0, 0, 0))
    output.putdata(
        [
            (0, 0, 0, 0) if alpha == 0 else (red, green, blue, 255)
            for red, green, blue, alpha in getattr(
                rgba, "get_flattened_data", rgba.getdata
            )()
        ]
    )
    return output


def magenta_score(red: int, green: int, blue: int) -> float:
    return min(red, blue) - green - abs(red - blue) * 0.65


def chroma_distance(red: int, green: int, blue: int) -> float:
    return math.sqrt(
        (red - CHROMA_KEY[0]) ** 2
        + (green - CHROMA_KEY[1]) ** 2
        + (blue - CHROMA_KEY[2]) ** 2
    )


def clean_edge_connected_magenta(image: Image.Image) -> Image.Image:
    """Remove opaque magenta-key fringe without globally erasing purple art.

    The image-gen sources intentionally used a #ff00ff plate.  The first hard
    key removed the plate but left an opaque one-to-three-pixel pink outline.
    Limit the cleanup to the alpha boundary band, clear only pixels still very
    close to the key, and replace the remaining spill with the nearest opaque
    non-magenta interior colour.
    """

    rgba = normalize_hard_alpha(image)
    pixels = rgba.load()
    width, height = rgba.size
    opaque = {
        (x, y)
        for y in range(height)
        for x in range(width)
        if pixels[x, y][3] != 0
    }
    boundary = {
        (x, y)
        for x, y in opaque
        if any(
            nx < 0
            or ny < 0
            or nx >= width
            or ny >= height
            or pixels[nx, ny][3] == 0
            for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1))
        )
    }
    band = set(boundary)
    frontier = set(boundary)
    for _depth in range(1, CHROMA_EDGE_BAND_DEPTH):
        expanded = {
            (nx, ny)
            for x, y in frontier
            for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1))
            if (nx, ny) in opaque and (nx, ny) not in band
        }
        band.update(expanded)
        frontier = expanded

    clear: set[tuple[int, int]] = set()
    spill: set[tuple[int, int]] = set()
    for x, y in band:
        red, green, blue, _alpha = pixels[x, y]
        score = magenta_score(red, green, blue)
        distance = chroma_distance(red, green, blue)
        if distance <= CHROMA_CLEAR_DISTANCE:
            clear.add((x, y))
        elif score >= 42 and red >= 70 and blue >= 65:
            spill.add((x, y))

    for x, y in clear:
        pixels[x, y] = (0, 0, 0, 0)

    searchable = opaque - clear - spill
    for x, y in spill:
        replacement: tuple[int, int, int] | None = None
        for radius in range(1, 7):
            candidates: list[tuple[int, int, int, int]] = []
            for ny in range(max(0, y - radius), min(height, y + radius + 1)):
                for nx in range(max(0, x - radius), min(width, x + radius + 1)):
                    if (nx, ny) not in searchable:
                        continue
                    red, green, blue, alpha = pixels[nx, ny]
                    if alpha == 0 or magenta_score(red, green, blue) >= 32:
                        continue
                    candidates.append(
                        (abs(nx - x) + abs(ny - y), red, green, blue)
                    )
            if candidates:
                _distance, red, green, blue = min(candidates)
                replacement = (red, green, blue)
                break
        if replacement is None:
            red, green, blue, _alpha = pixels[x, y]
            neutral = max(green, min(red, blue) // 3)
            replacement = (red, neutral, min(blue, max(neutral, red // 2)))
        pixels[x, y] = (*replacement, 255)
    return normalize_hard_alpha(rgba)


def render_native_actor_frame(
    source_cell: Image.Image,
    native_frame: Image.Image,
    *,
    scale: float,
    opacity: int = 255,
    mirror: bool = False,
    anchor_mode: str = "centroid",
) -> Image.Image:
    output = Image.new("RGBA", native_frame.size, (0, 0, 0, 0))
    source_bbox = source_cell.getchannel("A").getbbox()
    native_bbox = native_frame.getchannel("A").getbbox()
    if source_bbox is None or opacity <= 0:
        return output
    source = source_cell.crop(source_bbox)
    source = source.resize(
        (
            max(1, round(source.width * scale)),
            max(1, round(source.height * scale)),
        ),
        Image.Resampling.NEAREST,
    )
    source = normalize_hard_alpha(source)
    if mirror:
        source = source.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
    if opacity < 255:
        source.putalpha(
            source.getchannel("A").point(lambda value: value * opacity // 255)
        )

    if native_bbox is None:
        target_bottom = native_frame.height - 2
        target_anchor = (native_frame.width - 1) / 2
    else:
        target_bottom = native_bbox[3]
        if anchor_mode == "ground":
            target_anchor = ground_anchor_x(native_frame)
        else:
            target_anchor = weighted_alpha_centroid_x(native_frame)
    if anchor_mode == "ground":
        source_anchor = ground_anchor_x(source)
    else:
        source_anchor = weighted_alpha_centroid_x(source)
    x = round(target_anchor - source_anchor)
    y = target_bottom - source.height
    paste_clipped(output, source, x, y)
    return output


def render_native_effect_frame(
    source_cell: Image.Image,
    native_frame: Image.Image,
) -> Image.Image:
    output = Image.new("RGBA", native_frame.size, (0, 0, 0, 0))
    source_bbox = source_cell.getchannel("A").getbbox()
    native_bbox = native_frame.getchannel("A").getbbox()
    if source_bbox is None:
        return output
    source = normalize_hard_alpha(source_cell.crop(source_bbox))
    if native_bbox is None:
        target_width = max(1, native_frame.width - 2)
        target_height = max(1, native_frame.height - 2)
        target_center = ((native_frame.width - 1) / 2, (native_frame.height - 1) / 2)
    else:
        target_width = native_bbox[2] - native_bbox[0]
        target_height = native_bbox[3] - native_bbox[1]
        target_center = (
            (native_bbox[0] + native_bbox[2] - 1) / 2,
            (native_bbox[1] + native_bbox[3] - 1) / 2,
        )
    scale = min(target_width / source.width, target_height / source.height)
    source = source.resize(
        (
            max(1, round(source.width * scale)),
            max(1, round(source.height * scale)),
        ),
        Image.Resampling.NEAREST,
    )
    source = normalize_hard_alpha(source)
    x = round(target_center[0] - (source.width - 1) / 2)
    y = round(target_center[1] - (source.height - 1) / 2)
    paste_clipped(output, source, x, y)
    return output


def place_frame(
    sheet: Image.Image,
    frame_image: Image.Image,
    frame: dict[str, Any],
) -> None:
    x, y, width, height = frame_rect(frame)
    if frame_image.size != (width, height):
        raise ValueError(
            f"Frame image {frame_image.size} does not match native rect {(width, height)}"
        )
    sheet.alpha_composite(frame_image, (x, y))


def native_reference_scale(
    source_cell: Image.Image,
    native_frame: Image.Image,
    *,
    visible_width_cap: int,
) -> float:
    source_bbox = source_cell.getchannel("A").getbbox()
    native_bbox = native_frame.getchannel("A").getbbox()
    if source_bbox is None or native_bbox is None:
        raise ValueError("Reference source/native frame must both be visible")
    source_width = source_bbox[2] - source_bbox[0]
    source_height = source_bbox[3] - source_bbox[1]
    native_width = min(visible_width_cap, native_bbox[2] - native_bbox[0])
    native_height = native_bbox[3] - native_bbox[1]
    return min(native_width / source_width, native_height / source_height)


def horizontal_centroid_span(
    sheet: Image.Image,
    document: dict[str, Any],
    tag: str,
) -> float:
    values = [
        weighted_alpha_centroid_x(frame_crop(sheet, frame))
        - int(frame["data"]["w"]) / 2
        for frame in document["anims"][tag]["frames"]
        if frame_crop(sheet, frame).getchannel("A").getbbox() is not None
    ]
    return max(values) - min(values) if values else 0.0


def hot_magenta_edge_stats(image: Image.Image) -> dict[str, Any]:
    rgba = image.convert("RGBA")
    pixels = rgba.load()
    edge_count = 0
    hot_count = 0
    for y in range(rgba.height):
        for x in range(rgba.width):
            red, green, blue, alpha = pixels[x, y]
            if alpha == 0:
                continue
            if not any(
                nx < 0
                or ny < 0
                or nx >= rgba.width
                or ny >= rgba.height
                or pixels[nx, ny][3] == 0
                for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1))
            ):
                continue
            edge_count += 1
            if (
                red > 150
                and blue > 100
                and green < 0.45 * min(red, blue)
                and abs(red - blue) < 100
            ):
                hot_count += 1
    return {
        "edge_pixels": edge_count,
        "hot_magenta_edge_pixels": hot_count,
        "hot_magenta_edge_ratio": round(hot_count / edge_count, 6)
        if edge_count
        else 0.0,
    }


def alpha_bbox(image: Image.Image) -> list[int] | None:
    bbox = image.getchannel("A").getbbox()
    return list(bbox) if bbox else None


def artifact_record(path: Path) -> dict[str, Any]:
    with Image.open(path) as opened:
        image = opened.convert("RGBA")
        mode = opened.mode
    return {
        "path": path.relative_to(MOD_ROOT).as_posix(),
        "sha256": sha256_file(path),
        "bytes": path.stat().st_size,
        "mode": mode,
        "size": list(image.size),
        "alpha_bbox": alpha_bbox(image),
        "transparent_corners": all(
            image.getpixel(point)[3] == 0
            for point in (
                (0, 0),
                (image.width - 1, 0),
                (0, image.height - 1),
                (image.width - 1, image.height - 1),
            )
        ),
    }


def file_record(path: Path) -> dict[str, Any]:
    return {
        "path": path.relative_to(MOD_ROOT).as_posix(),
        "sha256": sha256_file(path),
        "bytes": path.stat().st_size,
    }


def has_hard_alpha(path: Path) -> bool:
    image = load_rgba(path)
    histogram = image.getchannel("A").histogram()
    return sum(histogram[1:255]) == 0


def stable_tag_bottoms(
    tag_bboxes: dict[str, list[list[int] | None]],
    tags: tuple[str, ...],
    expected_bottom: int,
) -> bool:
    for tag in tags:
        boxes = tag_bboxes[tag]
        for index, bbox in enumerate(boxes):
            if tag == "dead" and index == len(boxes) - 1 and bbox is None:
                continue
            if bbox is None or bbox[3] != expected_bottom:
                return False
    return True


def tag_bottoms_match_native(
    generated_sheet: Image.Image,
    native_sheet: Image.Image,
    document: dict[str, Any],
    tags: tuple[str, ...],
) -> bool:
    for tag_name in tags:
        frames = document["anims"][tag_name]["frames"]
        for index, frame in enumerate(frames):
            generated_bbox = frame_crop(generated_sheet, frame).getchannel("A").getbbox()
            native_bbox = frame_crop(native_sheet, frame).getchannel("A").getbbox()
            if generated_bbox is None:
                if tag_name == "dead" and index == len(frames) - 1:
                    continue
                return False
            if native_bbox is None or generated_bbox[3] != native_bbox[3]:
                return False
    return True


def tag_visible_widths_at_most(
    sheet: Image.Image,
    document: dict[str, Any],
    tags: tuple[str, ...],
    maximum: int,
) -> bool:
    for tag_name in tags:
        for frame in document["anims"][tag_name]["frames"]:
            bbox = frame_crop(sheet, frame).getchannel("A").getbbox()
            if bbox is not None and bbox[2] - bbox[0] > maximum:
                return False
    return True


def non_dead_tags_have_hard_alpha(sheet_path: Path, anim_path: Path) -> bool:
    sheet = load_rgba(sheet_path)
    document = json.loads(anim_path.read_text(encoding="utf-8"))
    for tag_name, tag in document["anims"].items():
        if tag_name == "dead":
            continue
        for frame in tag["frames"]:
            data = frame["data"]
            left = int(data["x"])
            top = int(data["y"])
            crop = sheet.crop(
                (
                    left,
                    top,
                    left + int(data["w"]),
                    top + int(data["h"]),
                )
            )
            if sum(crop.getchannel("A").histogram()[1:255]) != 0:
                return False
    return True


def load_rgba(path: Path) -> Image.Image:
    with Image.open(path) as opened:
        return opened.convert("RGBA")


def grid_cell(
    image: Image.Image,
    index: int,
    *,
    cols: int = GRID_COLS,
    rows: int = GRID_ROWS,
) -> Image.Image:
    if index < 0 or index >= cols * rows:
        raise ValueError(f"grid index out of range: {index}")
    col = index % cols
    row = index // cols
    left = col * image.width // cols
    right = (col + 1) * image.width // cols
    top = row * image.height // rows
    bottom = (row + 1) * image.height // rows
    cell = image.crop((left, top, right, bottom))
    # Chroma-key outputs are hard alpha. Clear hidden RGB so nearest-neighbor
    # downsampling cannot revive keyed pixels around a frame edge.
    pixels = cell.load()
    for y in range(cell.height):
        for x in range(cell.width):
            red, green, blue, alpha = pixels[x, y]
            if alpha == 0:
                pixels[x, y] = (0, 0, 0, 0)
            else:
                pixels[x, y] = (red, green, blue, 255)
    return cell


def paste_clipped(canvas: Image.Image, sprite: Image.Image, x: int, y: int) -> None:
    left = max(0, x)
    top = max(0, y)
    right = min(canvas.width, x + sprite.width)
    bottom = min(canvas.height, y + sprite.height)
    if right <= left or bottom <= top:
        return
    crop = sprite.crop((left - x, top - y, right - x, bottom - y))
    canvas.alpha_composite(crop, (left, top))


def write_anim(path: Path, anims: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    document = {
        "anims": {
            name: {"frames": frames}
            for name, frames in anims.items()
        }
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(document, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return document


def tag_frame_alpha_bboxes(sheet: Image.Image, document: dict[str, Any]) -> dict[str, list[list[int] | None]]:
    result: dict[str, list[list[int] | None]] = {}
    for name, tag in document["anims"].items():
        result[name] = []
        for frame in tag["frames"]:
            data = frame["data"]
            left = int(data["x"])
            top = int(data["y"])
            right = left + int(data["w"])
            bottom = top + int(data["h"])
            result[name].append(alpha_bbox(sheet.crop((left, top, right, bottom))))
    return result


def validate_required_nonempty(
    name: str,
    frame_bboxes: dict[str, list[list[int] | None]],
    *,
    allow_last_dead_empty: bool,
) -> None:
    for tag, boxes in frame_bboxes.items():
        for index, bbox in enumerate(boxes):
            if allow_last_dead_empty and tag == "dead" and index == len(boxes) - 1:
                continue
            if bbox is None:
                raise ValueError(f"{name}: empty required frame {tag}[{index}]")


def pack_epic(
    native_document: dict[str, Any],
    native_record: dict[str, Any],
    native_sheet: Image.Image,
    native_sheet_record: dict[str, Any],
) -> dict[str, Any]:
    body_path = PROCESSED_DIR / "baron_action_contact_alpha.png"
    impact_path = PROCESSED_DIR / "baron_target_impact_contact_alpha.png"
    body_source = load_rgba(body_path)
    impact_source = load_rgba(impact_path)

    body_cells = [normalize_hard_alpha(grid_cell(body_source, index)) for index in range(16)]
    impact_cells = [
        normalize_hard_alpha(grid_cell(impact_source, index, cols=4, rows=2))
        for index in range(7)
    ]
    native_anims = native_document["anims"]
    native_base = frame_crop(native_sheet, native_anims["base"]["frames"][0])
    body_scale = native_reference_scale(
        body_cells[0],
        native_base,
        visible_width_cap=BARON_NATIVE_VISIBLE_WIDTH,
    )

    dead_spec = [
        (12, 255),
        (12, 255),
        (13, 255),
        (13, 255),
        (13, 255),
        (14, 255),
        (14, 255),
        (14, 255),
        (15, 255),
        (15, 192),
        (15, 128),
        (15, 64),
        (15, 0),
    ]
    source_by_tag: dict[str, list[tuple[int, int, bool, str]]] = {
        "base": [(0, 255, False, "centroid")],
        "idle": [
            (index, 255, False, "centroid")
            for index in (0, 1, 2, 3)
        ],
        "attack_left": [
            (index, 255, True, "ground")
            for index in (4, 5, 6, 7, 8)
        ],
        "attack_right": [
            (index, 255, False, "ground")
            for index in (4, 5, 6, 7, 8)
        ],
        "dead": [
            (source_index, opacity, False, "centroid")
            for source_index, opacity in dead_spec
        ],
    }
    sheet = Image.new("RGBA", native_sheet.size, (0, 0, 0, 0))
    for tag_name, specs in source_by_tag.items():
        native_frames = native_anims[tag_name]["frames"]
        if len(specs) != len(native_frames):
            raise ValueError(
                f"epic.{tag_name}: {len(specs)} sources for {len(native_frames)} native frames"
            )
        for native_frame_spec, (source_index, opacity, mirror, anchor_mode) in zip(
            native_frames,
            specs,
            strict=True,
        ):
            native_frame = frame_crop(native_sheet, native_frame_spec)
            rendered = render_native_actor_frame(
                body_cells[source_index],
                native_frame,
                scale=body_scale,
                opacity=opacity,
                mirror=mirror,
                anchor_mode=anchor_mode,
            )
            place_frame(sheet, rendered, native_frame_spec)

    impact_scales: list[float] = []
    for source_cell, native_frame_spec in zip(
        impact_cells,
        native_anims["attack_target_effect"]["frames"],
        strict=True,
    ):
        native_frame = frame_crop(native_sheet, native_frame_spec)
        source_bbox = source_cell.getchannel("A").getbbox()
        native_bbox = native_frame.getchannel("A").getbbox()
        if source_bbox is None:
            raise ValueError("Baron target-impact source contains an empty required cell")
        target_width = (
            native_bbox[2] - native_bbox[0]
            if native_bbox
            else native_frame.width - 2
        )
        target_height = (
            native_bbox[3] - native_bbox[1]
            if native_bbox
            else native_frame.height - 2
        )
        impact_scales.append(
            min(
                target_width / (source_bbox[2] - source_bbox[0]),
                target_height / (source_bbox[3] - source_bbox[1]),
            )
        )
        place_frame(
            sheet,
            render_native_effect_frame(source_cell, native_frame),
            native_frame_spec,
        )

    sheet_path = INGAME_DIR / "epic#sheet.png"
    anim_path = INGAME_DIR / "epic#anim.fanim"
    sheet_path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(sheet_path, format="PNG", optimize=False, compress_level=9)
    document = write_anim(
        anim_path,
        {
            tag_name: native_tag["frames"]
            for tag_name, native_tag in native_anims.items()
        },
    )
    validate_native_frame_rect_contract("epic", document, native_document)
    bboxes = tag_frame_alpha_bboxes(sheet, document)
    validate_required_nonempty("epic", bboxes, allow_last_dead_empty=True)
    idle_centroid_span = horizontal_centroid_span(sheet, document, "idle")
    return {
        "body_scale": body_scale,
        "impact_scales": impact_scales,
        "visible_width_cap": BARON_NATIVE_VISIBLE_WIDTH,
        "native_sheet_contract": native_sheet_record,
        "native_animation_contract": native_record,
        "native_animation_contract_exact": True,
        "native_frame_rect_contract_exact": True,
        "idle_horizontal_centroid_span_px": round(idle_centroid_span, 6),
        "attack_directions_use_mirrored_body_art": True,
        "sheet": artifact_record(sheet_path),
        "animation": file_record(anim_path),
        "tag_frame_counts": {
            name: len(tag["frames"])
            for name, tag in document["anims"].items()
        },
        "tag_frame_alpha_bboxes": bboxes,
    }


def pack_dragon(
    variant: str,
    native_document: dict[str, Any],
    native_record: dict[str, Any],
    native_sheet: Image.Image,
    native_sheet_record: dict[str, Any],
) -> dict[str, Any]:
    processed_path = PROCESSED_DIR / f"dragon_{variant}_action_contact_alpha.png"
    source = load_rgba(processed_path)
    source_cells = [
        clean_edge_connected_magenta(grid_cell(source, index))
        for index in range(16)
    ]
    native_anims = native_document["anims"]
    native_base = frame_crop(native_sheet, native_anims["base"]["frames"][0])
    body_scale = native_reference_scale(
        source_cells[0],
        native_base,
        visible_width_cap=DRAGON_NATIVE_VISIBLE_WIDTH,
    )
    idle_source_width = max(
        source_cells[index].getchannel("A").getbbox()[2]
        - source_cells[index].getchannel("A").getbbox()[0]
        for index in range(4)
    )
    body_scale = min(
        body_scale,
        DRAGON_NATIVE_VISIBLE_WIDTH / idle_source_width,
    )

    dead_spec = [
            (12, 255),
            (13, 255),
            (14, 255),
            (15, 255),
            (15, 192),
            (15, 128),
            (15, 64),
            (15, 0),
    ]
    source_by_tag: dict[str, list[tuple[int, int, str]]] = {
        "base": [(0, 255, "centroid")],
        "idle": [
            (index, 255, "centroid")
            for index in (0, 1, 2, 3)
        ],
        "attack": [
            (index, 255, "ground")
            for index in (4, 5, 6, 7, 7)
        ],
        "dead": [
            (source_index, opacity, "centroid")
            for source_index, opacity in dead_spec
        ],
    }
    sheet = Image.new("RGBA", native_sheet.size, (0, 0, 0, 0))
    for tag_name, specs in source_by_tag.items():
        native_frames = native_anims[tag_name]["frames"]
        if len(specs) != len(native_frames):
            raise ValueError(
                f"serpen.{tag_name}: {len(specs)} sources for {len(native_frames)} native frames"
            )
        for native_frame_spec, (source_index, opacity, anchor_mode) in zip(
            native_frames,
            specs,
            strict=True,
        ):
            native_frame = frame_crop(native_sheet, native_frame_spec)
            place_frame(
                sheet,
                render_native_actor_frame(
                    source_cells[source_index],
                    native_frame,
                    scale=body_scale,
                    opacity=opacity,
                    anchor_mode=anchor_mode,
                ),
                native_frame_spec,
            )

    sheet_path = VARIANT_DIR / f"{variant}#sheet.png"
    anim_path = VARIANT_DIR / f"{variant}#anim.fanim"
    sheet_path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(sheet_path, format="PNG", optimize=False, compress_level=9)
    document = write_anim(
        anim_path,
        {
            tag_name: native_tag["frames"]
            for tag_name, native_tag in native_anims.items()
        },
    )
    validate_native_frame_rect_contract("serpen", document, native_document)
    bboxes = tag_frame_alpha_bboxes(sheet, document)
    validate_required_nonempty(variant, bboxes, allow_last_dead_empty=True)
    idle_centroid_span = horizontal_centroid_span(sheet, document, "idle")
    fringe_stats = hot_magenta_edge_stats(sheet)
    return {
        "body_scale": body_scale,
        "visible_width_cap": DRAGON_NATIVE_VISIBLE_WIDTH,
        "native_sheet_contract": native_sheet_record,
        "native_animation_contract": native_record,
        "native_animation_contract_exact": True,
        "native_frame_rect_contract_exact": True,
        "idle_horizontal_centroid_span_px": round(idle_centroid_span, 6),
        "edge_connected_magenta_cleanup": {
            "edge_band_depth_px": CHROMA_EDGE_BAND_DEPTH,
            "clear_distance": CHROMA_CLEAR_DISTANCE,
            **fringe_stats,
        },
        "sheet": artifact_record(sheet_path),
        "animation": file_record(anim_path),
        "tag_frame_counts": {
            name: len(tag["frames"])
            for name, tag in document["anims"].items()
        },
        "tag_frame_alpha_bboxes": bboxes,
    }


def source_pair_record(source_name: str, processed_name: str) -> dict[str, Any]:
    return {
        "source": artifact_record(SOURCE_DIR / source_name),
        "processed": artifact_record(PROCESSED_DIR / processed_name),
    }


def main() -> int:
    INGAME_DIR.mkdir(parents=True, exist_ok=True)
    VARIANT_DIR.mkdir(parents=True, exist_ok=True)
    QA_PATH.parent.mkdir(parents=True, exist_ok=True)

    native_documents, native_records = load_native_animation_contracts(("epic", "serpen"))
    native_sheets, native_sheet_records = load_native_sheets(("epic", "serpen"))
    epic = pack_epic(
        native_documents["epic"],
        native_records["epic"],
        native_sheets["epic"],
        native_sheet_records["epic"],
    )
    dragons = {
        variant: pack_dragon(
            variant,
            native_documents["serpen"],
            native_records["serpen"],
            native_sheets["serpen"],
            native_sheet_records["serpen"],
        )
        for variant in DRAGON_VARIANTS
    }

    infernal_sheet = VARIANT_DIR / "infernal#sheet.png"
    infernal_anim = VARIANT_DIR / "infernal#anim.fanim"
    serpen_sheet = INGAME_DIR / "serpen#sheet.png"
    serpen_anim = INGAME_DIR / "serpen#anim.fanim"
    shutil.copyfile(infernal_sheet, serpen_sheet)
    shutil.copyfile(infernal_anim, serpen_anim)

    qa = {
        "schema": "lol_mod.quality_objectives_imagegen_pack.v3",
        "processing": {
            "chroma_key_helper": "$CODEX_HOME/skills/.system/imagegen/scripts/remove_chroma_key.py",
            "chroma_key_mode": "auto-key border, hard tolerance 40",
            "edge_connected_dragon_cleanup": {
                "band_depth_px": CHROMA_EDGE_BAND_DEPTH,
                "clear_distance": CHROMA_CLEAR_DISTANCE,
                "despill": "nearest non-magenta opaque interior colour",
            },
            "action_source_grid": [4, 4],
            "baron_target_impact_source_grid": [4, 2],
            "alpha_trim_before_resize": True,
            "resampling": "Pillow Image.Resampling.NEAREST",
            "non_uniform_stretching": False,
            "body_anchor": "native alpha centroid for idle/body, native ground anchor for attacks, native per-frame alpha bottom",
            "native_sheet_dimensions_preserved": True,
            "native_frame_rectangles_preserved": True,
        },
        "sources": {
            "baron_action": source_pair_record(
                "baron_action_contact.png",
                "baron_action_contact_alpha.png",
            ),
            "baron_target_impact": source_pair_record(
                "baron_target_impact_contact.png",
                "baron_target_impact_contact_alpha.png",
            ),
            "dragons": {
                variant: source_pair_record(
                    f"dragon_{variant}_action_contact.png",
                    f"dragon_{variant}_action_contact_alpha.png",
                )
                for variant in DRAGON_VARIANTS
            },
        },
        "runtime": {
            "epic": epic,
            "dragon_variants": dragons,
            "serpen_infernal_default": {
                "dynamic_rotation_owned_by": "main objective runtime task",
                "sheet": artifact_record(serpen_sheet),
                "animation": file_record(serpen_anim),
                "matches_infernal_sheet_sha256": sha256_file(serpen_sheet) == sha256_file(infernal_sheet),
                "matches_infernal_anim_sha256": sha256_file(serpen_anim) == sha256_file(infernal_anim),
                "tag_frame_counts": dragons["infernal"]["tag_frame_counts"],
                "tag_frame_alpha_bboxes": dragons["infernal"]["tag_frame_alpha_bboxes"],
            },
        },
        "static_checks": {
            "epic_size_matches_native": epic["sheet"]["size"]
            == epic["native_sheet_contract"]["dimensions"],
            "epic_tag_counts": epic["tag_frame_counts"]
            == {
                "base": 1,
                "idle": 4,
                "attack_target_effect": 7,
                "attack_right": 5,
                "dead": 13,
                "attack_left": 5,
            },
            "epic_native_animation_contract_exact": epic[
                "native_animation_contract_exact"
            ],
            "epic_native_frame_rect_contract_exact": epic[
                "native_frame_rect_contract_exact"
            ],
            "dragon_sizes_match_native": all(
                record["sheet"]["size"]
                == record["native_sheet_contract"]["dimensions"]
                for record in dragons.values()
            ),
            "dragon_tag_counts": all(
                record["tag_frame_counts"]
                == {"base": 1, "idle": 4, "attack": 5, "dead": 8}
                for record in dragons.values()
            ),
            "dragon_native_animation_contracts_exact": all(
                record["native_animation_contract_exact"]
                for record in dragons.values()
            ),
            "dragon_native_frame_rect_contracts_exact": all(
                record["native_frame_rect_contract_exact"]
                for record in dragons.values()
            ),
            "epic_body_bottoms_match_native": tag_bottoms_match_native(
                Image.open(INGAME_DIR / "epic#sheet.png").convert("RGBA"),
                native_sheets["epic"],
                native_documents["epic"],
                ("base", "idle", "attack_left", "attack_right", "dead"),
            ),
            "dragon_body_bottoms_match_native": all(
                tag_bottoms_match_native(
                    Image.open(VARIANT_DIR / f"{variant}#sheet.png").convert("RGBA"),
                    native_sheets["serpen"],
                    native_documents["serpen"],
                    ("base", "idle", "attack", "dead"),
                )
                for variant in DRAGON_VARIANTS
            ),
            "epic_idle_centroid_stable": epic[
                "idle_horizontal_centroid_span_px"
            ]
            <= 2.0,
            "dragon_idle_centroids_stable": all(
                record["idle_horizontal_centroid_span_px"] <= 2.0
                for record in dragons.values()
            ),
            "epic_base_idle_visible_width_native_class": tag_visible_widths_at_most(
                Image.open(INGAME_DIR / "epic#sheet.png").convert("RGBA"),
                native_documents["epic"],
                ("base", "idle"),
                BARON_NATIVE_VISIBLE_WIDTH,
            ),
            "dragon_base_idle_visible_width_native_class": all(
                tag_visible_widths_at_most(
                    Image.open(VARIANT_DIR / f"{variant}#sheet.png").convert("RGBA"),
                    native_documents["serpen"],
                    ("base", "idle"),
                    DRAGON_NATIVE_VISIBLE_WIDTH,
                )
                for variant in DRAGON_VARIANTS
            ),
            "dragon_hot_magenta_edge_removed": all(
                record["edge_connected_magenta_cleanup"][
                    "hot_magenta_edge_ratio"
                ]
                <= 0.05
                for record in dragons.values()
            ),
            "dragon_breath_frames_extend_right": all(
                record["tag_frame_alpha_bboxes"]["attack"][-1][2]
                >= record["tag_frame_alpha_bboxes"]["attack"][0][2]
                for record in dragons.values()
            ),
            "epic_target_effect_frames_nonempty": all(
                bbox is not None
                for bbox in epic["tag_frame_alpha_bboxes"]["attack_target_effect"]
            ),
            "all_processed_corners_transparent": all(
                pair["processed"]["transparent_corners"]
                for pair in (
                    [
                        source_pair_record(
                            "baron_action_contact.png",
                            "baron_action_contact_alpha.png",
                        ),
                        source_pair_record(
                            "baron_target_impact_contact.png",
                            "baron_target_impact_contact_alpha.png",
                        ),
                    ]
                    + [
                        source_pair_record(
                            f"dragon_{variant}_action_contact.png",
                            f"dragon_{variant}_action_contact_alpha.png",
                        )
                        for variant in DRAGON_VARIANTS
                    ]
                )
            ),
            "all_processed_alpha_is_hard": all(
                has_hard_alpha(PROCESSED_DIR / name)
                for name in (
                    "baron_action_contact_alpha.png",
                    "baron_target_impact_contact_alpha.png",
                    *(
                        f"dragon_{variant}_action_contact_alpha.png"
                        for variant in DRAGON_VARIANTS
                    ),
                )
            ),
            "non_dead_runtime_alpha_is_hard": non_dead_tags_have_hard_alpha(
                INGAME_DIR / "epic#sheet.png",
                INGAME_DIR / "epic#anim.fanim",
            )
            and non_dead_tags_have_hard_alpha(
                INGAME_DIR / "serpen#sheet.png",
                INGAME_DIR / "serpen#anim.fanim",
            )
            and all(
                non_dead_tags_have_hard_alpha(
                    VARIANT_DIR / f"{variant}#sheet.png",
                    VARIANT_DIR / f"{variant}#anim.fanim",
                )
                for variant in DRAGON_VARIANTS
            ),
            "serpen_matches_infernal": sha256_file(serpen_sheet) == sha256_file(infernal_sheet)
            and sha256_file(serpen_anim) == sha256_file(infernal_anim),
        },
    }
    if not all(qa["static_checks"].values()):
        failed = [name for name, value in qa["static_checks"].items() if not value]
        raise ValueError(f"quality objective static checks failed: {failed}")

    QA_PATH.write_text(
        json.dumps(qa, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(f"Wrote {QA_PATH.relative_to(MOD_ROOT)}")
    print(f"Epic sheet: {epic['sheet']['size']} {epic['sheet']['sha256']}")
    for variant, record in dragons.items():
        print(f"Dragon {variant}: {record['sheet']['size']} {record['sheet']['sha256']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
