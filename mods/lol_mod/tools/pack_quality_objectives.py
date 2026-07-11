from __future__ import annotations

import hashlib
import json
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
BARON_CELL = 218
BARON_BODY_BOTTOM = 215
BARON_EFFECT_CELL = (51, 41)
DRAGON_CELL = 115
DRAGON_BODY_BOTTOM = 112

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


def reference_scale(cell: Image.Image, max_width: int, max_height: int) -> float:
    bbox = cell.getchannel("A").getbbox()
    if not bbox:
        raise ValueError("reference cell is empty")
    width = bbox[2] - bbox[0]
    height = bbox[3] - bbox[1]
    return min(max_width / width, max_height / height)


def paste_clipped(canvas: Image.Image, sprite: Image.Image, x: int, y: int) -> None:
    left = max(0, x)
    top = max(0, y)
    right = min(canvas.width, x + sprite.width)
    bottom = min(canvas.height, y + sprite.height)
    if right <= left or bottom <= top:
        return
    crop = sprite.crop((left - x, top - y, right - x, bottom - y))
    canvas.alpha_composite(crop, (left, top))


def render_body_frame(
    cell: Image.Image,
    *,
    target_size: int,
    bottom: int,
    scale: float,
    opacity: int = 255,
) -> Image.Image:
    frame = Image.new("RGBA", (target_size, target_size), (0, 0, 0, 0))
    bbox = cell.getchannel("A").getbbox()
    if not bbox or opacity <= 0:
        return frame
    trimmed = cell.crop(bbox)
    resized = trimmed.resize(
        (
            max(1, round(trimmed.width * scale)),
            max(1, round(trimmed.height * scale)),
        ),
        Image.Resampling.NEAREST,
    )
    if opacity < 255:
        resized.putalpha(resized.getchannel("A").point(lambda value: value * opacity // 255))

    # Preserve the source cell's authored horizontal anchor. This keeps the
    # monster body stable while allowing mouth-origin breath VFX to extend and
    # clip naturally at the right edge instead of shrinking the whole actor.
    x = round(target_size / 2 + (bbox[0] - cell.width / 2) * scale)
    y = bottom - resized.height
    paste_clipped(frame, resized, x, y)
    return frame


def render_centered_effect(
    cell: Image.Image,
    *,
    target_size: tuple[int, int],
    scale: float,
) -> Image.Image:
    frame = Image.new("RGBA", target_size, (0, 0, 0, 0))
    bbox = cell.getchannel("A").getbbox()
    if not bbox:
        return frame
    trimmed = cell.crop(bbox)
    resized = trimmed.resize(
        (
            max(1, round(trimmed.width * scale)),
            max(1, round(trimmed.height * scale)),
        ),
        Image.Resampling.NEAREST,
    )
    x = round(target_size[0] / 2 + (bbox[0] - cell.width / 2) * scale)
    y = round(target_size[1] / 2 + (bbox[1] - cell.height / 2) * scale)
    paste_clipped(frame, resized, x, y)
    return frame


def anim_frame(x: int, y: int, width: int, height: int, duration: float) -> dict[str, Any]:
    return {
        "duration": duration,
        "data": {
            "x": float(x),
            "y": float(y),
            "w": float(width),
            "h": float(height),
        },
    }


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
) -> dict[str, Any]:
    body_path = PROCESSED_DIR / "baron_action_contact_alpha.png"
    impact_path = PROCESSED_DIR / "baron_target_impact_contact_alpha.png"
    body_source = load_rgba(body_path)
    impact_source = load_rgba(impact_path)

    body_cells = [grid_cell(body_source, index) for index in range(16)]
    body_scale = reference_scale(body_cells[0], BARON_CELL - 10, BARON_BODY_BOTTOM - 5)

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
    body_spec = (
        [(0, 255)]
        + [(index, 255) for index in (0, 1, 2, 3)]
        + [(index, 255) for index in (4, 5, 6, 7, 8)]
        + dead_spec
    )
    if len(body_spec) != 23:
        raise AssertionError("Baron must have 23 unique 218px body cells")

    body_frames = [
        render_body_frame(
            body_cells[source_index],
            target_size=BARON_CELL,
            bottom=BARON_BODY_BOTTOM,
            scale=body_scale,
            opacity=opacity,
        )
        for source_index, opacity in body_spec
    ]

    impact_cells = [
        grid_cell(impact_source, index, cols=4, rows=2)
        for index in range(7)
    ]
    impact_boxes = [cell.getchannel("A").getbbox() for cell in impact_cells]
    if any(bbox is None for bbox in impact_boxes):
        raise ValueError(
            "Baron target-impact source contains an empty required cell: "
            f"{impact_boxes}"
        )
    max_width = max(bbox[2] - bbox[0] for bbox in impact_boxes if bbox)
    max_height = max(bbox[3] - bbox[1] for bbox in impact_boxes if bbox)
    impact_scale = min(
        (BARON_EFFECT_CELL[0] - 2) / max_width,
        (BARON_EFFECT_CELL[1] - 2) / max_height,
    )
    impact_frames = [
        render_centered_effect(
            cell,
            target_size=BARON_EFFECT_CELL,
            scale=impact_scale,
        )
        for cell in impact_cells
    ]

    sheet = Image.new(
        "RGBA",
        (23 * BARON_CELL, BARON_CELL + BARON_EFFECT_CELL[1]),
        (0, 0, 0, 0),
    )
    for index, frame in enumerate(body_frames):
        sheet.alpha_composite(frame, (index * BARON_CELL, 0))
    for index, frame in enumerate(impact_frames):
        sheet.alpha_composite(frame, (index * BARON_EFFECT_CELL[0], BARON_CELL))

    sheet_path = INGAME_DIR / "epic#sheet.png"
    anim_path = INGAME_DIR / "epic#anim.fanim"
    sheet_path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(sheet_path, format="PNG", optimize=False, compress_level=9)

    native_anims = native_document["anims"]
    base_rect = [
        anim_frame(
            0,
            0,
            BARON_CELL,
            BARON_CELL,
            native_anims["base"]["frames"][0]["duration"],
        )
    ]
    idle_rects = [
        anim_frame(index * BARON_CELL, 0, BARON_CELL, BARON_CELL, native_frame["duration"])
        for index, native_frame in zip(
            range(1, 5),
            native_anims["idle"]["frames"],
            strict=True,
        )
    ]
    attack_rects = [
        anim_frame(index * BARON_CELL, 0, BARON_CELL, BARON_CELL, native_frame["duration"])
        for index, native_frame in zip(
            range(5, 10),
            native_anims["attack_left"]["frames"],
            strict=True,
        )
    ]
    attack_right_rects = [
        anim_frame(index * BARON_CELL, 0, BARON_CELL, BARON_CELL, native_frame["duration"])
        for index, native_frame in zip(
            range(5, 10),
            native_anims["attack_right"]["frames"],
            strict=True,
        )
    ]
    dead_rects = [
        anim_frame(index * BARON_CELL, 0, BARON_CELL, BARON_CELL, native_frame["duration"])
        for index, native_frame in zip(
            range(10, 23),
            native_anims["dead"]["frames"],
            strict=True,
        )
    ]
    impact_rects = [
        anim_frame(
            index * BARON_EFFECT_CELL[0],
            BARON_CELL,
            BARON_EFFECT_CELL[0],
            BARON_EFFECT_CELL[1],
            native_frame["duration"],
        )
        for index, native_frame in zip(
            range(7),
            native_anims["attack_target_effect"]["frames"],
            strict=True,
        )
    ]
    generated_by_tag = {
        "base": base_rect,
        "idle": idle_rects,
        "attack_target_effect": impact_rects,
        "attack_right": attack_right_rects,
        "dead": dead_rects,
        "attack_left": attack_rects,
    }
    document = write_anim(
        anim_path,
        {
            tag_name: generated_by_tag[tag_name]
            for tag_name in native_anims
        },
    )
    validate_native_animation_contract("epic", document, native_document)
    bboxes = tag_frame_alpha_bboxes(sheet, document)
    validate_required_nonempty("epic", bboxes, allow_last_dead_empty=True)
    return {
        "body_scale": body_scale,
        "impact_scale": impact_scale,
        "body_bottom_exclusive": BARON_BODY_BOTTOM,
        "body_unique_cells": 23,
        "attack_right_reuses_attack_left_rects": True,
        "native_animation_contract": native_record,
        "native_animation_contract_exact": True,
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
) -> dict[str, Any]:
    processed_path = PROCESSED_DIR / f"dragon_{variant}_action_contact_alpha.png"
    source = load_rgba(processed_path)
    source_cells = [grid_cell(source, index) for index in range(16)]
    body_scale = reference_scale(source_cells[0], DRAGON_CELL - 8, DRAGON_BODY_BOTTOM - 4)

    frame_spec = (
        [(0, 255)]
        + [(index, 255) for index in (0, 1, 2, 3)]
        + [(index, 255) for index in (4, 5, 6, 7, 7)]
        + [
            (12, 255),
            (13, 255),
            (14, 255),
            (15, 255),
            (15, 192),
            (15, 128),
            (15, 64),
            (15, 0),
        ]
    )
    if len(frame_spec) != 18:
        raise AssertionError("Dragon must have 18 unique 115px body cells")
    frames = [
        render_body_frame(
            source_cells[source_index],
            target_size=DRAGON_CELL,
            bottom=DRAGON_BODY_BOTTOM,
            scale=body_scale,
            opacity=opacity,
        )
        for source_index, opacity in frame_spec
    ]
    sheet = Image.new("RGBA", (18 * DRAGON_CELL, DRAGON_CELL), (0, 0, 0, 0))
    for index, frame in enumerate(frames):
        sheet.alpha_composite(frame, (index * DRAGON_CELL, 0))

    sheet_path = VARIANT_DIR / f"{variant}#sheet.png"
    anim_path = VARIANT_DIR / f"{variant}#anim.fanim"
    sheet_path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(sheet_path, format="PNG", optimize=False, compress_level=9)

    native_anims = native_document["anims"]
    tag_ranges = {
        "base": range(0, 1),
        "idle": range(1, 5),
        "attack": range(5, 10),
        "dead": range(10, 18),
    }
    generated_by_tag = {
        tag_name: [
            anim_frame(
                index * DRAGON_CELL,
                0,
                DRAGON_CELL,
                DRAGON_CELL,
                native_frame["duration"],
            )
            for index, native_frame in zip(
                tag_ranges[tag_name],
                native_anims[tag_name]["frames"],
                strict=True,
            )
        ]
        for tag_name in native_anims
    }
    document = write_anim(anim_path, generated_by_tag)
    validate_native_animation_contract("serpen", document, native_document)
    bboxes = tag_frame_alpha_bboxes(sheet, document)
    validate_required_nonempty(variant, bboxes, allow_last_dead_empty=True)
    return {
        "body_scale": body_scale,
        "body_bottom_exclusive": DRAGON_BODY_BOTTOM,
        "native_animation_contract": native_record,
        "native_animation_contract_exact": True,
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
    epic = pack_epic(native_documents["epic"], native_records["epic"])
    dragons = {
        variant: pack_dragon(
            variant,
            native_documents["serpen"],
            native_records["serpen"],
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
        "schema": "lol_mod.quality_objectives_imagegen_pack.v2",
        "processing": {
            "chroma_key_helper": "$CODEX_HOME/skills/.system/imagegen/scripts/remove_chroma_key.py",
            "chroma_key_mode": "auto-key border, hard tolerance 40",
            "hard_key_reason": "Preserves purple Baron/impact pixels that conflict with a magenta soft matte.",
            "action_source_grid": [4, 4],
            "baron_target_impact_source_grid": [4, 2],
            "alpha_trim_before_resize": True,
            "resampling": "Pillow Image.Resampling.NEAREST",
            "non_uniform_stretching": False,
            "body_anchor": "authored horizontal cell anchor with fixed bottom baseline",
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
            "epic_size": epic["sheet"]["size"] == [5014, 259],
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
            "dragon_sizes": all(
                record["sheet"]["size"] == [2070, 115]
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
            "epic_body_baseline_stable": stable_tag_bottoms(
                epic["tag_frame_alpha_bboxes"],
                ("base", "idle", "attack_left", "attack_right", "dead"),
                BARON_BODY_BOTTOM,
            ),
            "dragon_body_baselines_stable": all(
                stable_tag_bottoms(
                    record["tag_frame_alpha_bboxes"],
                    ("base", "idle", "attack", "dead"),
                    DRAGON_BODY_BOTTOM,
                )
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
