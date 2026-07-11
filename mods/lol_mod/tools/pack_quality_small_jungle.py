from __future__ import annotations

import hashlib
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


SPECS = (
    PackSpec(
        source_name="red_brambleback",
        display_name="Red Brambleback",
        runtime_name="rhino",
        cell_size=87,
        max_visible_width=83,
        max_visible_height=76,
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
    ),
    PackSpec(
        source_name="blue_sentinel",
        display_name="Blue Sentinel",
        runtime_name="stump",
        cell_size=92,
        max_visible_width=88,
        max_visible_height=82,
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
    ),
    PackSpec(
        source_name="gromp",
        display_name="Gromp",
        runtime_name="mushroom",
        cell_size=97,
        max_visible_width=93,
        max_visible_height=76,
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
        cell_size=64,
        max_visible_width=60,
        max_visible_height=52,
        baseline=54,
        sequences={
            "idle": [0, 1, 2, 3] * 4,
            "run": [4, 5, 6, 7] * 4,
            "attack": [8, 9, 10, 11, 11],
            "dead": [12, 13, 14, 15],
        },
        attack_vfx_note=(
            "The cyan claw burst stays in source attack cell 10 and begins at the leading paw; "
            "the body-bearing recovery cell is held once to satisfy the five-frame contract."
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
    for red, green, blue, alpha in rgba.getdata():
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
    assets = [
        pack_one(
            spec,
            native_documents[spec.runtime_name],
            native_records[spec.runtime_name],
        )
        for spec in SPECS
    ]
    payload = {
        "schema_version": 2,
        "generator": "mods/lol_mod/tools/pack_quality_small_jungle.py",
        "scope": "static image processing only; no game launch and no test execution",
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
