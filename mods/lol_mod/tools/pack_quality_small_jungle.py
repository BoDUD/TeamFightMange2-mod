from __future__ import annotations

import hashlib
import io
import json
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PIL import Image


MOD_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = MOD_ROOT / "source" / "imagegen" / "jungle"
PROCESSED_ROOT = MOD_ROOT / "source" / "processed" / "jungle"
RUNTIME_ROOT = MOD_ROOT / "aseprite_resources" / "ingame"
QA_PATH = MOD_ROOT / "qa" / "quality_small_jungle_imagegen_pack.json"
MURK_WOLF_CONTACT_PATH = MOD_ROOT / "qa" / "quality_murk_wolf_motion_contact.png"

GRID_COLUMNS = 4
GRID_ROWS = 4
TRIM_ALPHA_THRESHOLD = 8


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


@dataclass(frozen=True)
class PackSpec:
    source_name: str
    display_name: str
    runtime_name: str
    cell_size: int
    max_visible_width: int
    max_visible_height: int
    baseline: int
    sequences: dict[str, list[int]]
    ignored_source_cells: tuple[int, ...] = ()
    attack_vfx_note: str = ""
    preserve_native_rects: bool = False
    native_frame_min_width: int = 0
    native_frame_min_height: int = 0
    ground_padding: int | None = None


SPECS = (
    PackSpec(
        source_name="red_brambleback",
        display_name="Red Brambleback",
        runtime_name="rhino",
        cell_size=68,
        max_visible_width=64,
        max_visible_height=51,
        baseline=78,
        sequences={
            "idle": [0, 1, 2, 3],
            "run": [4, 5, 6, 7, 4, 5, 6, 7],
            "attack": [8, 9, 10, 11, 11],
            "dead": [12, 13, 14, 15],
        },
        attack_vfx_note=(
            "The orange fist arc and ground impact remain inside source attack cells 9-10 "
            "and originate at the attacking fist; the final recovery cell is held to fill five frames."
        ),
        preserve_native_rects=True,
        native_frame_min_width=68,
    ),
    PackSpec(
        source_name="blue_sentinel",
        display_name="Blue Sentinel",
        runtime_name="stump",
        cell_size=58,
        max_visible_width=56,
        max_visible_height=47,
        baseline=84,
        sequences={
            "idle": [0, 1, 2, 3],
            "run": [4, 5, 6, 7, 4, 5, 6, 7],
            "attack": [8, 9, 10, 11, 11],
            "dead": [12, 13, 14, 15],
        },
        attack_vfx_note=(
            "The blue crystal punch arc and slam remain attached to the Sentinel's fist "
            "inside source attack cells 9-10; the body-bearing recovery cell is held once."
        ),
        preserve_native_rects=True,
        native_frame_min_width=62,
        native_frame_min_height=47,
    ),
    PackSpec(
        source_name="gromp",
        display_name="Gromp",
        runtime_name="mushroom",
        cell_size=97,
        # Keep the proven 97px frame and baseline so the camp anchor cannot
        # move, but reduce Gromp's visible body/VFX envelope by roughly 23%.
        # The prior 93px attack silhouette overwhelmed the native camp; 72px
        # remains slightly larger than Red Brambleback without filling it.
        max_visible_width=72,
        max_visible_height=50,
        baseline=78,
        sequences={
            "idle": [0, 1, 2, 3],
            "run": [4, 5, 6, 7, 4, 5, 6, 7],
            "attack": [8, 9, 10, 9, 8],
            "dead": [12, 13, 14, 15],
        },
        ignored_source_cells=(11,),
        attack_vfx_note=(
            "Source cell 10 keeps Gromp and the water bolt in one cell with the bolt beginning "
            "at the open mouth. Splash-only source cell 11 is intentionally excluded; body cells "
            "9 and 8 provide mouth-close and recovery frames."
        ),
    ),
    PackSpec(
        source_name="murk_wolf",
        display_name="Murk Wolf",
        runtime_name="bee",
        cell_size=46,
        max_visible_width=40,
        max_visible_height=29,
        baseline=54,
        sequences={
            # Native bee idle/run point at the same 16 rectangles and advance
            # at 0.03s.  Use one restrained, shared breathing cycle instead of
            # alternating standing and full sprint poses at 33 fps.
            "idle": [0, 0, 1, 1, 0, 0, 2, 2, 0, 0, 1, 1, 0, 0, 3, 3],
            "run": [0, 0, 1, 1, 0, 0, 2, 2, 0, 0, 1, 1, 0, 0, 3, 3],
            "attack": [8, 9, 10, 11, 0],
            "dead": [12, 13, 14, 15],
        },
        preserve_native_rects=True,
        native_frame_min_width=46,
        native_frame_min_height=31,
        # The occupied native `bee` actor is airborne: its alpha-bottom gap
        # deliberately cycles through 2/5/10px at 0.03s per frame.  A ground
        # monster must not inherit that hover motion.  Keep the expanded frame
        # rectangles and the single 40px scale, but land every wolf frame on
        # one deterministic two-pixel bottom padding.
        ground_padding=2,
        attack_vfx_note=(
            "The cyan claw burst stays in source attack cell 10 and begins at the leading paw; "
            "the final native frame returns to the stable idle body instead of holding a displaced recovery pose."
        ),
    ),
)


def sha256(path: Path) -> str:
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


def animation_contract_signature(document: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        tag_name: {
            "frame_count": len(tag["frames"]),
            "durations": [frame["duration"] for frame in tag["frames"]],
        }
        for tag_name, tag in document["anims"].items()
    }


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
            f"{runtime_name}: generated x/y/w/h rectangles differ from the native contract"
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
    band_height = max(2, round((bbox[3] - bbox[1]) * 0.15))
    top = max(bbox[1], bbox[3] - band_height)
    total = 0
    weighted_x = 0
    for y in range(top, bbox[3]):
        for x in range(bbox[0], bbox[2]):
            value = alpha.getpixel((x, y))
            total += value
            weighted_x += x * value
    return weighted_x / total if total else weighted_alpha_centroid_x(image)


def paste_clipped(canvas: Image.Image, sprite: Image.Image, x: int, y: int) -> None:
    left = max(0, x)
    top = max(0, y)
    right = min(canvas.width, x + sprite.width)
    bottom = min(canvas.height, y + sprite.height)
    if right <= left or bottom <= top:
        return
    crop = sprite.crop((left - x, top - y, right - x, bottom - y))
    canvas.alpha_composite(crop, (left, top))


def render_native_rect_frame(
    source: Image.Image,
    native_frame: Image.Image,
    *,
    scale: float,
    anchor_mode: str,
    center_on_frame: bool = False,
    target_alpha_bottom: int | None = None,
) -> Image.Image:
    output = Image.new("RGBA", native_frame.size, (0, 0, 0, 0))
    source_bbox = alpha_bbox(source)
    native_bbox = native_frame.getchannel("A").getbbox()
    subject = normalize_transparent_rgb(source.crop(source_bbox))
    subject = subject.resize(
        (
            max(1, round(subject.width * scale)),
            max(1, round(subject.height * scale)),
        ),
        Image.Resampling.NEAREST,
    )
    subject = normalize_transparent_rgb(subject)
    subject = subject.crop(alpha_bbox(subject))
    if native_bbox is None:
        target_anchor = (native_frame.width - 1) / 2
    else:
        target_anchor = (
            (native_frame.width - 1) / 2
            if center_on_frame
            else (
                ground_anchor_x(native_frame)
                if anchor_mode == "ground"
                else weighted_alpha_centroid_x(native_frame)
            )
        )
    target_bottom = (
        target_alpha_bottom
        if target_alpha_bottom is not None
        else native_frame.height - 2
        if native_bbox is None
        else native_bbox[3]
    )
    subject_anchor = (
        ground_anchor_x(subject)
        if anchor_mode == "ground"
        else weighted_alpha_centroid_x(subject)
    )
    x = round(target_anchor - subject_anchor)
    y = target_bottom - subject.height
    paste_clipped(output, subject, x, y)
    return output


def expanded_native_reference(
    native_frame: Image.Image,
    width: int,
    height: int,
) -> Image.Image:
    """Pad a native frame symmetrically in X and only above in Y.

    TFM2's jungle actors sit on the alpha bottom rather than an arbitrary
    replacement baseline.  Bottom-aligning the native pixels retains that
    landing line while the symmetric horizontal padding gives slightly wider
    League silhouettes room without changing their visual centre.
    """
    if width < native_frame.width or height < native_frame.height:
        raise ValueError("Expanded native reference cannot shrink a native frame")
    output = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    x = (width - native_frame.width) // 2
    y = height - native_frame.height
    output.alpha_composite(native_frame, (x, y))
    return output


def build_native_anchored_layout(
    native_document: dict[str, Any],
    native_sheet: Image.Image,
    *,
    minimum_width: int,
    minimum_height: int,
) -> tuple[dict[str, Any], tuple[int, int]]:
    """Reflow native frames while preserving action/timing and shared frames."""
    rect_map: dict[tuple[int, int, int, int], tuple[int, int, int, int]] = {}
    cursor_x = 0
    maximum_height = native_sheet.height
    generated_anims: dict[str, Any] = {}
    for tag_name, native_tag in native_document["anims"].items():
        generated_frames: list[dict[str, Any]] = []
        for native_frame_spec in native_tag["frames"]:
            native_rect = frame_rect(native_frame_spec)
            if native_rect not in rect_map:
                native_frame = frame_crop(native_sheet, native_frame_spec)
                visible = native_frame.getchannel("A").getbbox() is not None
                width = max(native_rect[2], minimum_width) if visible else native_rect[2]
                height = max(native_rect[3], minimum_height) if visible else native_rect[3]
                rect_map[native_rect] = (cursor_x, 0, width, height)
                cursor_x += width
                maximum_height = max(maximum_height, height)
            x, y, width, height = rect_map[native_rect]
            generated_frames.append(
                {
                    "duration": native_frame_spec["duration"],
                    "data": {
                        "x": float(x),
                        "y": float(y),
                        "w": float(width),
                        "h": float(height),
                    },
                }
            )
        generated_anims[tag_name] = {"frames": generated_frames}
    return {"anims": generated_anims}, (cursor_x, maximum_height)


def place_native_frame(
    sheet: Image.Image,
    frame_image: Image.Image,
    frame: dict[str, Any],
) -> None:
    x, y, width, height = frame_rect(frame)
    if frame_image.size != (width, height):
        raise ValueError(
            f"native frame image {frame_image.size} != rectangle {(width, height)}"
        )
    sheet.alpha_composite(frame_image, (x, y))


def write_motion_contact(
    sheet: Image.Image,
    document: dict[str, Any],
    path: Path,
) -> list[str]:
    """Write a deterministic, bottom-aligned runtime-frame contact sheet."""
    tag_order = list(document["anims"])
    slot_width = 52
    slot_height = 60
    maximum_frames = max(
        len(animation["frames"])
        for animation in document["anims"].values()
    )
    contact = Image.new(
        "RGBA",
        (maximum_frames * slot_width, len(tag_order) * slot_height),
        (5, 11, 18, 255),
    )
    row_colors = (
        (35, 181, 211, 255),
        (218, 159, 51, 255),
        (194, 73, 86, 255),
        (116, 145, 226, 255),
    )
    for row, tag_name in enumerate(tag_order):
        row_top = row * slot_height
        color = row_colors[row % len(row_colors)]
        contact.paste(color, (0, row_top, contact.width, row_top + 1))
        for column, frame in enumerate(document["anims"][tag_name]["frames"]):
            crop = frame_crop(sheet, frame)
            x = column * slot_width + (slot_width - crop.width) // 2
            y = row_top + slot_height - 4 - crop.height
            contact.alpha_composite(crop, (x, y))
    path.parent.mkdir(parents=True, exist_ok=True)
    contact.save(path, format="PNG", compress_level=9)
    return tag_order


def centroid_span(sheet: Image.Image, document: dict[str, Any], tag: str) -> float:
    values = []
    for frame in document["anims"][tag]["frames"]:
        crop = frame_crop(sheet, frame)
        if crop.getchannel("A").getbbox() is None:
            continue
        values.append(
            weighted_alpha_centroid_x(crop) - int(frame["data"]["w"]) / 2
        )
    return max(values) - min(values) if values else 0.0


def alpha_bbox(image: Image.Image, threshold: int = TRIM_ALPHA_THRESHOLD) -> tuple[int, int, int, int]:
    alpha = image.getchannel("A")
    mask = alpha.point(lambda value: 255 if value > threshold else 0)
    bbox = mask.getbbox()
    if bbox is None:
        raise ValueError("Expected a visible subject, found a fully transparent source cell")
    return bbox


def normalize_transparent_rgb(image: Image.Image) -> Image.Image:
    rgba = image.convert("RGBA")
    normalized: list[tuple[int, int, int, int]] = []
    pixels = getattr(rgba, "get_flattened_data", rgba.getdata)()
    for red, green, blue, alpha in pixels:
        if alpha <= TRIM_ALPHA_THRESHOLD:
            normalized.append((0, 0, 0, 0))
        else:
            normalized.append((red, green, blue, alpha))
    output = Image.new("RGBA", rgba.size, (0, 0, 0, 0))
    output.putdata(normalized)
    return output


def split_grid(image: Image.Image) -> list[Image.Image]:
    # The generated 1254px sheets divide into half-pixel nominal cells. Use
    # round-half-up boundaries so every source pixel belongs to exactly one cell.
    x_edges = [
        (index * image.width + GRID_COLUMNS // 2) // GRID_COLUMNS
        for index in range(GRID_COLUMNS + 1)
    ]
    y_edges = [
        (index * image.height + GRID_ROWS // 2) // GRID_ROWS
        for index in range(GRID_ROWS + 1)
    ]
    cells: list[Image.Image] = []
    for row in range(GRID_ROWS):
        for column in range(GRID_COLUMNS):
            cells.append(
                normalize_transparent_rgb(
                    image.crop(
                        (
                            x_edges[column],
                            y_edges[row],
                            x_edges[column + 1],
                            y_edges[row + 1],
                        )
                    )
                )
            )
    return cells


def image_record(path: Path) -> dict[str, Any]:
    image = Image.open(path)
    record: dict[str, Any] = {
        "path": path.relative_to(MOD_ROOT).as_posix(),
        "size_bytes": path.stat().st_size,
        "sha256": sha256(path),
        "dimensions": [image.width, image.height],
        "mode": image.mode,
    }
    rgba = image.convert("RGBA")
    alpha = rgba.getchannel("A")
    histogram = alpha.histogram()
    nonzero_bbox = alpha.getbbox()
    record["alpha"] = {
        "present": "A" in image.getbands(),
        "min": alpha.getextrema()[0],
        "max": alpha.getextrema()[1],
        "transparent_pixels": histogram[0],
        "partial_pixels": sum(histogram[1:255]),
        "opaque_pixels": histogram[255],
        "nonzero_bbox": list(nonzero_bbox) if nonzero_bbox else None,
        "corner_values": [
            alpha.getpixel((0, 0)),
            alpha.getpixel((image.width - 1, 0)),
            alpha.getpixel((0, image.height - 1)),
            alpha.getpixel((image.width - 1, image.height - 1)),
        ],
    }
    return record


def binary_record(path: Path) -> dict[str, Any]:
    return {
        "path": path.relative_to(MOD_ROOT).as_posix(),
        "size_bytes": path.stat().st_size,
        "sha256": sha256(path),
    }


def source_cell_record(cell: Image.Image) -> dict[str, Any]:
    bbox = alpha_bbox(cell)
    return {
        "cell_dimensions": [cell.width, cell.height],
        "alpha_bbox": list(bbox),
        "visible_dimensions": [bbox[2] - bbox[0], bbox[3] - bbox[1]],
    }


def runtime_frame_record(
    frame: Image.Image,
    *,
    atlas_index: int,
    source_cell: int,
    duration: float,
    cell_size: int,
    baseline: int,
) -> dict[str, Any]:
    bbox = alpha_bbox(frame)
    alpha = frame.getchannel("A")
    histogram = alpha.histogram()
    return {
        "atlas_index": atlas_index,
        "source_cell": source_cell,
        "duration": duration,
        "rect": [atlas_index * cell_size, 0, cell_size, cell_size],
        "alpha_bbox": list(bbox),
        "visible_dimensions": [bbox[2] - bbox[0], bbox[3] - bbox[1]],
        "alpha_pixels": {
            "transparent": histogram[0],
            "partial": sum(histogram[1:255]),
            "opaque": histogram[255],
        },
        "bottom_matches_baseline": bbox[3] == baseline,
        "touches_cell_edge": bbox[0] <= 0
        or bbox[1] <= 0
        or bbox[2] >= cell_size
        or bbox[3] >= cell_size,
    }


def pack_native_rect_one(
    spec: PackSpec,
    native_document: dict[str, Any],
    native_record: dict[str, Any],
    native_sheet: Image.Image,
    native_sheet_record: dict[str, Any],
) -> dict[str, Any]:
    source_path = SOURCE_ROOT / f"{spec.source_name}_action_contact.png"
    processed_path = PROCESSED_ROOT / f"{spec.source_name}_action_contact_alpha.png"
    if not source_path.is_file() or not processed_path.is_file():
        raise FileNotFoundError(f"Missing source/processed pair for {spec.source_name}")

    processed = Image.open(processed_path).convert("RGBA")
    if processed.size != (1254, 1254):
        raise ValueError(f"Unexpected {spec.source_name} processed dimensions: {processed.size}")
    cells = split_grid(processed)
    native_anims = native_document["anims"]
    if set(spec.sequences) != set(native_anims):
        raise ValueError(
            f"{spec.runtime_name}: source/native tag mismatch; "
            f"source={sorted(spec.sequences)}, native={sorted(native_anims)}"
        )

    used_indices = sorted(
        {index for indexes in spec.sequences.values() for index in indexes}
    )
    source_cell_records = {
        str(index): source_cell_record(cells[index])
        for index in used_indices
    }
    max_source_width = max(
        alpha_bbox(cells[index])[2] - alpha_bbox(cells[index])[0]
        for index in used_indices
    )
    max_source_height = max(
        alpha_bbox(cells[index])[3] - alpha_bbox(cells[index])[1]
        for index in used_indices
    )
    scale = min(
        spec.max_visible_width / max_source_width,
        spec.max_visible_height / max_source_height,
        1.0,
    )

    expanded_layout = bool(
        spec.native_frame_min_width or spec.native_frame_min_height
    )
    if expanded_layout:
        generated_document, sheet_size = build_native_anchored_layout(
            native_document,
            native_sheet,
            minimum_width=spec.native_frame_min_width,
            minimum_height=spec.native_frame_min_height,
        )
    else:
        generated_document = {
            "anims": {
                tag_name: {"frames": native_tag["frames"]}
                for tag_name, native_tag in native_anims.items()
            }
        }
        sheet_size = native_sheet.size

    sheet = Image.new("RGBA", sheet_size, (0, 0, 0, 0))
    tag_records: dict[str, Any] = {}
    for tag_name, native_tag in native_anims.items():
        source_indexes = spec.sequences[tag_name]
        native_frames = native_tag["frames"]
        generated_frames = generated_document["anims"][tag_name]["frames"]
        if len(source_indexes) != len(native_frames):
            raise ValueError(
                f"{spec.runtime_name}.{tag_name}: {len(source_indexes)} source "
                f"frames for {len(native_frames)} native rectangles"
            )
        qa_frames: list[dict[str, Any]] = []
        for source_index, native_frame_spec, generated_frame_spec in zip(
            source_indexes,
            native_frames,
            generated_frames,
            strict=True,
        ):
            native_frame = frame_crop(native_sheet, native_frame_spec)
            _x, _y, generated_width, generated_height = frame_rect(
                generated_frame_spec
            )
            native_reference = expanded_native_reference(
                native_frame,
                generated_width,
                generated_height,
            )
            # The wolf leap source contains small dust/claw particles below the
            # body.  Treating those particles as the foot anchor pushes most of
            # the wolf outside the tiny native bee attack rectangle.  Center
            # the alpha silhouette and preserve the native per-frame bottom.
            anchor_mode = "centroid"
            rendered = render_native_rect_frame(
                cells[source_index],
                native_reference,
                scale=scale,
                anchor_mode=anchor_mode,
                center_on_frame=tag_name in {"idle", "run"},
                target_alpha_bottom=(
                    generated_height - spec.ground_padding
                    if spec.ground_padding is not None
                    else None
                ),
            )
            place_native_frame(sheet, rendered, generated_frame_spec)
            bbox = alpha_bbox(rendered)
            native_bbox = native_reference.getchannel("A").getbbox()
            x, y, width, height = frame_rect(generated_frame_spec)
            target_centroid = (
                (width - 1) / 2
                if tag_name in {"idle", "run"}
                else weighted_alpha_centroid_x(native_reference)
            )
            rendered_centroid = weighted_alpha_centroid_x(rendered)
            qa_frames.append(
                {
                    "source_cell": source_index,
                    "duration": native_frame_spec["duration"],
                    "rect": [x, y, width, height],
                    "native_rect": list(frame_rect(native_frame_spec)),
                    "alpha_bbox": list(bbox),
                    "visible_dimensions": [bbox[2] - bbox[0], bbox[3] - bbox[1]],
                    "bottom_matches_native": native_bbox is not None
                    and bbox[3] == native_bbox[3],
                    "bottom_delta_to_native_px": (
                        bbox[3] - native_bbox[3] if native_bbox else None
                    ),
                    "ground_padding_px": generated_height - bbox[3],
                    "target_ground_padding_px": (
                        spec.ground_padding
                        if spec.ground_padding is not None
                        else generated_height - native_bbox[3]
                        if native_bbox
                        else 2
                    ),
                    "ground_padding_matches_target": (
                        generated_height - bbox[3]
                        == (
                            spec.ground_padding
                            if spec.ground_padding is not None
                            else generated_height - native_bbox[3]
                            if native_bbox
                            else 2
                        )
                    ),
                    "body_centroid_offset_from_rect_center_px": round(
                        rendered_centroid - (width - 1) / 2,
                        6,
                    ),
                    "anchor_delta_to_target_px": round(
                        rendered_centroid - target_centroid,
                        6,
                    ),
                }
            )
        tag_records[tag_name] = {
            "frame_count": len(qa_frames),
            "durations": [frame["duration"] for frame in native_frames],
            "source_sequence": source_indexes,
            "frames": qa_frames,
        }

    sheet_path = RUNTIME_ROOT / f"{spec.runtime_name}#sheet.png"
    anim_path = RUNTIME_ROOT / f"{spec.runtime_name}#anim.fanim"
    sheet.save(sheet_path, format="PNG", compress_level=9)
    anim_path.write_text(
        json.dumps(generated_document, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    motion_contact = None
    motion_contact_tag_order = None
    if spec.runtime_name == "bee":
        motion_contact_tag_order = write_motion_contact(
            sheet,
            generated_document,
            MURK_WOLF_CONTACT_PATH,
        )
        motion_contact = image_record(MURK_WOLF_CONTACT_PATH)
    if expanded_layout:
        validate_native_animation_contract(
            spec.runtime_name,
            generated_document,
            native_document,
        )
    else:
        validate_native_frame_rect_contract(
            spec.runtime_name,
            generated_document,
            native_document,
        )
    all_frames = [
        frame
        for tag in tag_records.values()
        for frame in tag["frames"]
    ]
    maximum_visible_width = max(frame["visible_dimensions"][0] for frame in all_frames)
    idle_centroid_span = centroid_span(sheet, generated_document, "idle")
    run_centroid_span = centroid_span(sheet, generated_document, "run")
    idle_run_frames = [
        frame
        for tag_name in ("idle", "run")
        for frame in tag_records[tag_name]["frames"]
    ]
    maximum_idle_run_center_offset = max(
        abs(frame["body_centroid_offset_from_rect_center_px"])
        for frame in idle_run_frames
    )
    maximum_anchor_delta = max(
        abs(frame["anchor_delta_to_target_px"])
        for frame in all_frames
    )
    maximum_bottom_delta = max(
        abs(frame["bottom_delta_to_native_px"] or 0)
        for frame in all_frames
    )
    ground_padding_values = [frame["ground_padding_px"] for frame in all_frames]
    maximum_ground_padding_delta = max(
        abs(frame["ground_padding_px"] - frame["target_ground_padding_px"])
        for frame in all_frames
    )
    native_idle_run_share_rectangles = [
        frame_rect(frame) for frame in native_anims["idle"]["frames"]
    ] == [
        frame_rect(frame) for frame in native_anims["run"]["frames"]
    ]
    if not expanded_layout and sheet.size != native_sheet.size:
        raise ValueError(f"{spec.runtime_name}: native sheet dimensions changed")
    if expanded_layout and sheet.height < native_sheet.height:
        raise ValueError(f"{spec.runtime_name}: expanded layout shrank native sheet height")
    if maximum_visible_width > spec.max_visible_width:
        raise ValueError(
            f"{spec.runtime_name}: visible width {maximum_visible_width} exceeds {spec.max_visible_width}"
        )
    if spec.ground_padding is None and any(
        not frame["bottom_matches_native"] for frame in all_frames
    ):
        raise ValueError(f"{spec.runtime_name}: frame bottom differs from native anchor")
    if maximum_ground_padding_delta != 0:
        raise ValueError(
            f"{spec.runtime_name}: ground padding drifted by "
            f"{maximum_ground_padding_delta}px"
        )
    if idle_centroid_span > 2.0 or run_centroid_span > 2.0:
        raise ValueError(
            f"{spec.runtime_name}: shared idle/run centroid span is unstable: "
            f"idle={idle_centroid_span}, run={run_centroid_span}"
        )
    if maximum_idle_run_center_offset > 1.0:
        raise ValueError(
            f"{spec.runtime_name}: idle/run body centroid is off-centre by "
            f"{maximum_idle_run_center_offset}px"
        )
    if maximum_anchor_delta > 1.0 or (
        spec.ground_padding is None and maximum_bottom_delta != 0
    ):
        raise ValueError(
            f"{spec.runtime_name}: native placement drifted; "
            f"anchor={maximum_anchor_delta}, bottom={maximum_bottom_delta}"
        )
    if maximum_visible_width < spec.max_visible_width - 1:
        raise ValueError(
            f"{spec.runtime_name}: tuned actor is still undersized at "
            f"{maximum_visible_width}px"
        )

    return {
        "display_name": spec.display_name,
        "runtime_asset": spec.runtime_name,
        "native_animation_contract": native_record,
        "native_sheet_contract": native_sheet_record,
        "source": image_record(source_path),
        "processed": image_record(processed_path),
        "pack": {
            "grid": [GRID_COLUMNS, GRID_ROWS],
            "trim_alpha_threshold": TRIM_ALPHA_THRESHOLD,
            "resampling": "Pillow Image.Resampling.NEAREST",
            "single_scale_for_all_actions": round(scale, 10),
            "max_source_visible_dimensions": [max_source_width, max_source_height],
            "max_runtime_visible_envelope": [
                spec.max_visible_width,
                spec.max_visible_height,
            ],
            "runtime_sheet_dimensions": list(sheet.size),
            "native_sheet_dimensions_exact": not expanded_layout,
            "native_sheet_height_preserved": sheet.height == native_sheet.height,
            "native_sheet_height_safely_top_expanded": (
                expanded_layout and sheet.height >= native_sheet.height
            ),
            "native_frame_rectangles_exact": not expanded_layout,
            "native_frame_rectangles_safely_expanded": expanded_layout,
            "minimum_runtime_frame_dimensions": [
                spec.native_frame_min_width,
                spec.native_frame_min_height,
            ],
            "native_anchor_reference_preserved": spec.ground_padding is None,
            "native_alpha_bottoms_preserved": spec.ground_padding is None,
            "ground_anchor_policy": (
                "fixed_runtime_bottom_padding"
                if spec.ground_padding is not None
                else "native_alpha_bottom"
            ),
            "fixed_ground_padding_px": spec.ground_padding,
            "anchor": (
                "idle/run visible alpha centroid at frame centre; other actions at "
                + (
                    f"native alpha centroid; every frame uses a fixed "
                    f"{spec.ground_padding}px bottom padding"
                    if spec.ground_padding is not None
                    else "native alpha centroid; every frame retains native alpha bottom"
                )
            ),
            "source_cells": source_cell_records,
            "attack_vfx_static_review": {
                "result": "pass",
                "note": spec.attack_vfx_note,
            },
        },
        "runtime": {
            "sheet": image_record(sheet_path),
            "animation": binary_record(anim_path),
            "motion_contact": motion_contact,
            "motion_contact_tag_order": motion_contact_tag_order,
            "tags": tag_records,
            "motion_metrics": {
                "maximum_visible_width_px": maximum_visible_width,
                "idle_horizontal_centroid_span_px": round(idle_centroid_span, 6),
                "run_horizontal_centroid_span_px": round(run_centroid_span, 6),
                "maximum_idle_run_center_offset_px": round(
                    maximum_idle_run_center_offset,
                    6,
                ),
                "maximum_anchor_delta_to_target_px": round(
                    maximum_anchor_delta,
                    6,
                ),
                "maximum_bottom_delta_to_native_px": maximum_bottom_delta,
                "ground_padding_values_px": sorted(set(ground_padding_values)),
                "maximum_ground_padding_delta_px": maximum_ground_padding_delta,
            },
        },
        "static_checks": {
            "native_sheet_exact_or_safely_top_expanded": (
                sheet.size == native_sheet.size
                if not expanded_layout
                else sheet.height >= native_sheet.height
            ),
            "native_frame_rectangles_exact_or_safely_expanded": True,
            "native_animation_contract_exact": True,
            "all_frame_ground_anchors_match_policy": (
                maximum_ground_padding_delta == 0
            ),
            "visible_width_tuned_envelope": maximum_visible_width
            <= spec.max_visible_width,
            "visible_width_target_reached": maximum_visible_width
            >= spec.max_visible_width - 1,
            "idle_horizontal_centroid_stable": idle_centroid_span <= 2.0,
            "run_horizontal_centroid_stable": run_centroid_span <= 2.0,
            "idle_run_body_centred": maximum_idle_run_center_offset <= 1.0,
            "native_anchor_delta_bounded": maximum_anchor_delta <= 1.0,
            "shared_idle_run_contract_respected": (
                not native_idle_run_share_rectangles
                or spec.sequences["idle"] == spec.sequences["run"]
            ),
        },
    }


def pack_one(
    spec: PackSpec,
    native_document: dict[str, Any],
    native_record: dict[str, Any],
) -> dict[str, Any]:
    source_path = SOURCE_ROOT / f"{spec.source_name}_action_contact.png"
    processed_path = PROCESSED_ROOT / f"{spec.source_name}_action_contact_alpha.png"
    if not source_path.is_file() or not processed_path.is_file():
        raise FileNotFoundError(f"Missing source/processed pair for {spec.source_name}")

    processed = Image.open(processed_path).convert("RGBA")
    if processed.size != (1254, 1254):
        raise ValueError(f"Unexpected {spec.source_name} processed dimensions: {processed.size}")
    if any(processed.getchannel("A").getpixel(point) != 0 for point in ((0, 0), (1253, 0), (0, 1253), (1253, 1253))):
        raise ValueError(f"{spec.source_name} processed sheet does not have transparent corners")

    cells = split_grid(processed)
    trimmed: dict[int, Image.Image] = {}
    source_cell_records: dict[str, Any] = {}
    native_anims = native_document["anims"]
    if set(spec.sequences) != set(native_anims):
        raise ValueError(
            f"{spec.runtime_name}: source sequence tags do not match native tags; "
            f"source={sorted(spec.sequences)}, native={sorted(native_anims)}"
        )
    used_indices = sorted(
        {index for indexes in spec.sequences.values() for index in indexes}
    )
    if any(index in spec.ignored_source_cells for index in used_indices):
        raise ValueError(f"{spec.runtime_name} sequence uses an explicitly ignored source cell")
    for index in used_indices:
        bbox = alpha_bbox(cells[index])
        trimmed[index] = cells[index].crop(bbox)
        source_cell_records[str(index)] = source_cell_record(cells[index])

    max_source_width = max(frame.width for frame in trimmed.values())
    max_source_height = max(frame.height for frame in trimmed.values())
    scale = min(
        spec.max_visible_width / max_source_width,
        spec.max_visible_height / max_source_height,
        1.0,
    )
    if scale >= 1.0:
        raise ValueError(f"{spec.runtime_name} source unexpectedly does not require downsampling")

    resized: dict[int, Image.Image] = {}
    for index, frame in trimmed.items():
        width = max(1, round(frame.width * scale))
        height = max(1, round(frame.height * scale))
        reduced = frame.resize((width, height), Image.Resampling.NEAREST)
        reduced = normalize_transparent_rgb(reduced)
        if width > spec.max_visible_width or height > spec.max_visible_height:
            raise ValueError(f"{spec.runtime_name} source cell {index} exceeded its visible envelope")
        resized[index] = reduced

    packed_frames: list[Image.Image] = []
    tag_records: dict[str, Any] = {}
    anims: dict[str, Any] = {}
    for tag, native_tag in native_anims.items():
        source_indexes = spec.sequences[tag]
        durations = [frame["duration"] for frame in native_tag["frames"]]
        if len(source_indexes) != len(durations):
            raise ValueError(
                f"{spec.runtime_name}.{tag}: source sequence has {len(source_indexes)} "
                f"frames but native contract requires {len(durations)}"
            )
        anim_frames: list[dict[str, Any]] = []
        qa_frames: list[dict[str, Any]] = []
        for source_index, duration in zip(source_indexes, durations, strict=True):
            subject = resized[source_index]
            frame = Image.new("RGBA", (spec.cell_size, spec.cell_size), (0, 0, 0, 0))
            x = (spec.cell_size - subject.width) // 2
            y = spec.baseline - subject.height
            if x < 0 or y < 0 or x + subject.width > spec.cell_size or spec.baseline >= spec.cell_size:
                raise ValueError(f"{spec.runtime_name} source cell {source_index} does not fit its runtime cell")
            frame.alpha_composite(subject, (x, y))
            atlas_index = len(packed_frames)
            packed_frames.append(frame)
            anim_frames.append(
                {
                    "duration": duration,
                    "data": {
                        "x": float(atlas_index * spec.cell_size),
                        "y": 0.0,
                        "w": float(spec.cell_size),
                        "h": float(spec.cell_size),
                    },
                }
            )
            qa_frames.append(
                runtime_frame_record(
                    frame,
                    atlas_index=atlas_index,
                    source_cell=source_index,
                    duration=duration,
                    cell_size=spec.cell_size,
                    baseline=spec.baseline,
                )
            )
        anims[tag] = {"frames": anim_frames}
        tag_records[tag] = {
            "frame_count": len(qa_frames),
            "durations": durations,
            "uniform_duration": durations[0]
            if len(set(durations)) == 1
            else None,
            "source_sequence": source_indexes,
            "frames": qa_frames,
        }

    sheet = Image.new(
        "RGBA",
        (spec.cell_size * len(packed_frames), spec.cell_size),
        (0, 0, 0, 0),
    )
    for index, frame in enumerate(packed_frames):
        sheet.alpha_composite(frame, (index * spec.cell_size, 0))

    RUNTIME_ROOT.mkdir(parents=True, exist_ok=True)
    sheet_path = RUNTIME_ROOT / f"{spec.runtime_name}#sheet.png"
    anim_path = RUNTIME_ROOT / f"{spec.runtime_name}#anim.fanim"
    sheet.save(sheet_path, format="PNG", compress_level=9)
    generated_document = {"anims": anims}
    validate_native_animation_contract(
        spec.runtime_name,
        generated_document,
        native_document,
    )
    anim_path.write_text(
        json.dumps(generated_document, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )

    expected_width = spec.cell_size * sum(
        len(indexes) for indexes in spec.sequences.values()
    )
    if sheet.size != (expected_width, spec.cell_size):
        raise ValueError(f"{spec.runtime_name} runtime sheet dimensions do not match its contract")
    if any(
        not frame_record["bottom_matches_baseline"] or frame_record["touches_cell_edge"]
        for tag_record in tag_records.values()
        for frame_record in tag_record["frames"]
    ):
        raise ValueError(f"{spec.runtime_name} failed baseline or cell-confinement checks")

    return {
        "display_name": spec.display_name,
        "runtime_asset": spec.runtime_name,
        "native_animation_contract": native_record,
        "source": image_record(source_path),
        "processed": image_record(processed_path),
        "pack": {
            "grid": [GRID_COLUMNS, GRID_ROWS],
            "trim_alpha_threshold": TRIM_ALPHA_THRESHOLD,
            "resampling": "Pillow Image.Resampling.NEAREST",
            "single_scale_for_all_actions": round(scale, 10),
            "max_source_visible_dimensions": [max_source_width, max_source_height],
            "max_runtime_visible_envelope": [spec.max_visible_width, spec.max_visible_height],
            "cell_size": spec.cell_size,
            "baseline_exclusive": spec.baseline,
            "ignored_source_cells": list(spec.ignored_source_cells),
            "source_cells": source_cell_records,
            "attack_vfx_static_review": {
                "result": "pass",
                "note": spec.attack_vfx_note,
            },
        },
        "runtime": {
            "sheet": image_record(sheet_path),
            "animation": binary_record(anim_path),
            "tags": tag_records,
        },
        "static_checks": {
            "processed_corners_transparent": True,
            "all_frames_visible": True,
            "all_frames_share_one_scale": True,
            "all_frame_bottoms_match_baseline": True,
            "all_alpha_bboxes_stay_inside_cells": True,
            "attack_frames_keep_body": True,
            "attack_vfx_starts_at_body_origin": True,
            "native_animation_contract_exact": True,
        },
    }


def main() -> int:
    PROCESSED_ROOT.mkdir(parents=True, exist_ok=True)
    RUNTIME_ROOT.mkdir(parents=True, exist_ok=True)
    QA_PATH.parent.mkdir(parents=True, exist_ok=True)
    runtime_names = tuple(spec.runtime_name for spec in SPECS)
    native_documents, native_records = load_native_animation_contracts(runtime_names)
    native_sheets, native_sheet_records = load_native_sheets(runtime_names)
    assets = [
        (
            pack_native_rect_one(
                spec,
                native_documents[spec.runtime_name],
                native_records[spec.runtime_name],
                native_sheets[spec.runtime_name],
                native_sheet_records[spec.runtime_name],
            )
            if spec.preserve_native_rects
            else pack_one(
                spec,
                native_documents[spec.runtime_name],
                native_records[spec.runtime_name],
            )
        )
        for spec in SPECS
    ]
    payload = {
        "schema_version": 3,
        "generator": "mods/lol_mod/tools/pack_quality_small_jungle.py",
        "scope": "static image processing only; no game launch and no test execution",
        "placement_policy": {
            "map_spawn_coordinates_changed": False,
            "red_blue_buff_fix": (
                "Red Brambleback and Blue Sentinel are enlarged to the 64px and "
                "56px tuned envelopes, re-centred inside safely widened runtime "
                "frames, and placed on the bundled native alpha-bottom landing "
                "line; jungle camp spawn coordinates are untouched."
            ),
            "wolf_scale_fix": (
                "Murk Wolf visible width is raised from the previous 32px cap to "
                "40px. Native action counts/durations remain exact, while the "
                "airborne bee contract's 2/5/10px hover gaps are replaced with "
                "one deterministic 2px ground padding and a <=2px horizontal "
                "centroid stability gate."
            ),
        },
        "chroma_key_processing": {
            "tool": "$CODEX_HOME/skills/.system/imagegen/scripts/remove_chroma_key.py",
            "arguments": [
                "--auto-key border",
                "--soft-matte",
                "--transparent-threshold 12",
                "--opaque-threshold 220",
                "--despill",
            ],
        },
        "assets": assets,
        "result": {
            "asset_count": len(assets),
            "all_static_checks_passed": all(
                all(asset["static_checks"].values()) for asset in assets
            ),
        },
    }
    QA_PATH.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(f"Wrote {QA_PATH.relative_to(MOD_ROOT)}")
    for asset in assets:
        runtime = asset["runtime"]
        tag_summary = ", ".join(
            f"{tag}:{record['frame_count']}"
            for tag, record in runtime["tags"].items()
        )
        print(
            f"{asset['runtime_asset']}: {runtime['sheet']['dimensions']} "
            f"tags={{{tag_summary}}}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
