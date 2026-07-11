from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PIL import Image


MOD_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = MOD_ROOT / "source" / "imagegen" / "jungle"
PROCESSED_ROOT = MOD_ROOT / "source" / "processed" / "jungle"
RUNTIME_ROOT = MOD_ROOT / "aseprite_resources" / "ingame" / "lol_camp_variants"
QA_PATH = MOD_ROOT / "qa" / "quality_missing_lol_camps_imagegen_pack.json"

GRID_COLUMNS = 4
GRID_ROWS = 4
CHROMA_KEY = (255, 0, 255)
CHROMA_DISTANCE_THRESHOLD = 52.0
CHROMA_MAGENTA_SCORE_THRESHOLD = 96.0


@dataclass(frozen=True)
class CampSpec:
    source_name: str
    display_name: str
    runtime_name: str
    cell_size: int
    max_visible_width: int
    max_visible_height: int
    baseline: int


SPECS = (
    CampSpec(
        source_name="raptor",
        display_name="Crimson Raptor",
        runtime_name="raptor",
        cell_size=76,
        max_visible_width=72,
        max_visible_height=66,
        baseline=69,
    ),
    CampSpec(
        source_name="krug",
        display_name="Ancient Krug",
        runtime_name="krug",
        cell_size=92,
        max_visible_width=88,
        max_visible_height=82,
        baseline=84,
    ),
)

SEQUENCES: dict[str, tuple[list[int], float]] = {
    "idle": ([0, 1, 2, 3], 0.14),
    "run": ([4, 5, 6, 7, 4, 5, 6, 7], 0.080000006),
    "attack": ([8, 9, 10, 11, 11], 0.080000006),
    "dead": ([12, 13, 14, 15], 0.15),
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def pixel_values(image: Image.Image) -> Any:
    getter = getattr(image, "get_flattened_data", None)
    if getter is not None:
        return getter()
    return image.getdata()


def remove_chroma_key(source: Image.Image) -> Image.Image:
    rgb = source.convert("RGB")
    output = Image.new("RGBA", rgb.size, (0, 0, 0, 0))
    converted: list[tuple[int, int, int, int]] = []
    key_red, key_green, key_blue = CHROMA_KEY
    for red, green, blue in pixel_values(rgb):
        distance = math.sqrt(
            (red - key_red) ** 2
            + (green - key_green) ** 2
            + (blue - key_blue) ** 2
        )
        # Generated pixel contacts can contain darker, anti-aliased mixtures of
        # the magenta plate that are far from #FF00FF in Euclidean RGB space.
        # Balanced red/blue dominance distinguishes those plate remnants from
        # the raptor's red-orange attack trails and dark plum feathers.
        magenta_score = min(red, blue) - green - abs(red - blue) * 0.65
        if (
            distance <= CHROMA_DISTANCE_THRESHOLD
            or magenta_score >= CHROMA_MAGENTA_SCORE_THRESHOLD
        ):
            converted.append((0, 0, 0, 0))
        else:
            if (
                red >= 170
                and blue >= 100
                and green <= 120
                and blue > green * 1.2
            ):
                # Retain authored attack sparks while removing the keyed plate's
                # hot-pink spill. Both camps use warm fire/stone impact accents.
                green = max(green, round(red * 0.32))
                blue = min(blue, round(green * 0.45))
            converted.append((red, green, blue, 255))
    output.putdata(converted)
    return output


def normalize_transparent_rgb(image: Image.Image) -> Image.Image:
    rgba = image.convert("RGBA")
    output = Image.new("RGBA", rgba.size, (0, 0, 0, 0))
    output.putdata(
        [
            (0, 0, 0, 0) if alpha == 0 else (red, green, blue, 255)
            for red, green, blue, alpha in pixel_values(rgba)
        ]
    )
    return output


def alpha_bbox(image: Image.Image) -> tuple[int, int, int, int]:
    bbox = image.getchannel("A").getbbox()
    if bbox is None:
        raise ValueError("expected visible camp art, found an empty image")
    return bbox


def split_grid(image: Image.Image) -> list[Image.Image]:
    x_edges = [
        (index * image.width + GRID_COLUMNS // 2) // GRID_COLUMNS
        for index in range(GRID_COLUMNS + 1)
    ]
    y_edges = [
        (index * image.height + GRID_ROWS // 2) // GRID_ROWS
        for index in range(GRID_ROWS + 1)
    ]
    return [
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
        for row in range(GRID_ROWS)
        for column in range(GRID_COLUMNS)
    ]


def image_record(path: Path) -> dict[str, Any]:
    with Image.open(path) as opened:
        image = opened.convert("RGBA")
        source_mode = opened.mode
    alpha = image.getchannel("A")
    histogram = alpha.histogram()
    bbox = alpha.getbbox()
    return {
        "path": path.relative_to(MOD_ROOT).as_posix(),
        "sha256": sha256_file(path),
        "bytes": path.stat().st_size,
        "dimensions": list(image.size),
        "source_mode": source_mode,
        "alpha_bbox": list(bbox) if bbox else None,
        "alpha": {
            "transparent_pixels": histogram[0],
            "partial_pixels": sum(histogram[1:255]),
            "opaque_pixels": histogram[255],
            "corner_values": [
                alpha.getpixel((0, 0)),
                alpha.getpixel((image.width - 1, 0)),
                alpha.getpixel((0, image.height - 1)),
                alpha.getpixel((image.width - 1, image.height - 1)),
            ],
        },
    }


def file_record(path: Path) -> dict[str, Any]:
    return {
        "path": path.relative_to(MOD_ROOT).as_posix(),
        "sha256": sha256_file(path),
        "bytes": path.stat().st_size,
    }


def frame_record(
    frame: Image.Image,
    *,
    source_cell: int,
    atlas_index: int,
    spec: CampSpec,
    duration: float,
) -> dict[str, Any]:
    bbox = alpha_bbox(frame)
    return {
        "source_cell": source_cell,
        "atlas_index": atlas_index,
        "duration": duration,
        "rect": [atlas_index * spec.cell_size, 0, spec.cell_size, spec.cell_size],
        "alpha_bbox": list(bbox),
        "visible_dimensions": [bbox[2] - bbox[0], bbox[3] - bbox[1]],
        "bottom_matches_baseline": bbox[3] == spec.baseline,
        "has_transparent_margin": bbox[0] > 0
        and bbox[1] > 0
        and bbox[2] < spec.cell_size
        and bbox[3] < spec.cell_size,
    }


def process_source(spec: CampSpec) -> tuple[Path, Path]:
    source_path = SOURCE_ROOT / f"{spec.source_name}_action_contact.png"
    processed_path = PROCESSED_ROOT / f"{spec.source_name}_action_contact_alpha.png"
    if not source_path.is_file():
        raise FileNotFoundError(source_path)
    with Image.open(source_path) as opened:
        if opened.size != (1254, 1254):
            raise ValueError(f"unexpected {spec.source_name} source dimensions: {opened.size}")
        processed = remove_chroma_key(opened)
    PROCESSED_ROOT.mkdir(parents=True, exist_ok=True)
    processed.save(processed_path, format="PNG", compress_level=9)
    return source_path, processed_path


def pack_camp(spec: CampSpec) -> dict[str, Any]:
    source_path, processed_path = process_source(spec)
    with Image.open(processed_path) as opened:
        processed = opened.convert("RGBA")
    cells = split_grid(processed)
    trimmed = [cell.crop(alpha_bbox(cell)) for cell in cells]

    max_source_width = max(frame.width for frame in trimmed)
    max_source_height = max(frame.height for frame in trimmed)
    scale = min(
        spec.max_visible_width / max_source_width,
        spec.max_visible_height / max_source_height,
        1.0,
    )
    if scale >= 1.0:
        raise ValueError(f"{spec.runtime_name} unexpectedly does not require downsampling")

    resized: list[Image.Image] = []
    for frame in trimmed:
        width = max(1, round(frame.width * scale))
        height = max(1, round(frame.height * scale))
        reduced = frame.resize((width, height), Image.Resampling.NEAREST)
        reduced = normalize_transparent_rgb(reduced)
        resized.append(reduced.crop(alpha_bbox(reduced)))

    packed_frames: list[Image.Image] = []
    anims: dict[str, Any] = {}
    qa_tags: dict[str, Any] = {}
    for tag, (source_cells, duration) in SEQUENCES.items():
        anim_frames: list[dict[str, Any]] = []
        qa_frames: list[dict[str, Any]] = []
        for source_cell in source_cells:
            subject = resized[source_cell]
            frame = Image.new("RGBA", (spec.cell_size, spec.cell_size), (0, 0, 0, 0))
            x = (spec.cell_size - subject.width) // 2
            y = spec.baseline - subject.height
            if x <= 0 or y <= 0 or x + subject.width >= spec.cell_size:
                raise ValueError(
                    f"{spec.runtime_name} source cell {source_cell} lacks a transparent margin"
                )
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
                frame_record(
                    frame,
                    source_cell=source_cell,
                    atlas_index=atlas_index,
                    spec=spec,
                    duration=duration,
                )
            )
        anims[tag] = {"frames": anim_frames}
        qa_tags[tag] = {
            "frame_count": len(anim_frames),
            "source_sequence": source_cells,
            "duration": duration,
            "frames": qa_frames,
        }

    sheet = Image.new(
        "RGBA",
        (len(packed_frames) * spec.cell_size, spec.cell_size),
        (0, 0, 0, 0),
    )
    for index, frame in enumerate(packed_frames):
        sheet.alpha_composite(frame, (index * spec.cell_size, 0))

    RUNTIME_ROOT.mkdir(parents=True, exist_ok=True)
    sheet_path = RUNTIME_ROOT / f"{spec.runtime_name}#sheet.png"
    anim_path = RUNTIME_ROOT / f"{spec.runtime_name}#anim.fanim"
    sheet.save(sheet_path, format="PNG", compress_level=9)
    anim_path.write_text(
        json.dumps({"anims": anims}, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )

    static_checks = {
        "source_is_1254_square_contact_sheet": image_record(source_path)["dimensions"] == [1254, 1254],
        "processed_has_rgba_and_transparent_corners": image_record(processed_path)["source_mode"] == "RGBA"
        and image_record(processed_path)["alpha"]["corner_values"] == [0, 0, 0, 0],
        "processed_uses_hard_alpha": image_record(processed_path)["alpha"]["partial_pixels"] == 0,
        "runtime_sheet_dimensions_match_contract": image_record(sheet_path)["dimensions"]
        == [21 * spec.cell_size, spec.cell_size],
        "tag_counts_are_4_8_5_4": {
            tag: record["frame_count"] for tag, record in qa_tags.items()
        }
        == {"idle": 4, "run": 8, "attack": 5, "dead": 4},
        "all_frames_share_one_scale": True,
        "all_frames_match_baseline": all(
            frame["bottom_matches_baseline"]
            for record in qa_tags.values()
            for frame in record["frames"]
        ),
        "all_frames_keep_transparent_margin": all(
            frame["has_transparent_margin"]
            for record in qa_tags.values()
            for frame in record["frames"]
        ),
        "all_attack_frames_keep_visible_subject": all(
            frame["visible_dimensions"][0] > 0 and frame["visible_dimensions"][1] > 0
            for frame in qa_tags["attack"]["frames"]
        ),
    }
    if not all(static_checks.values()):
        failed = [name for name, passed in static_checks.items() if not passed]
        raise ValueError(f"{spec.runtime_name} static checks failed: {failed}")

    return {
        "display_name": spec.display_name,
        "runtime_name": spec.runtime_name,
        "runtime_status": "art_ready_unmapped",
        "source": image_record(source_path),
        "processed": image_record(processed_path),
        "packing": {
            "source_grid": [GRID_COLUMNS, GRID_ROWS],
            "chroma_key": "#FF00FF",
            "chroma_distance_threshold": CHROMA_DISTANCE_THRESHOLD,
            "balanced_magenta_score_threshold": CHROMA_MAGENTA_SCORE_THRESHOLD,
            "magenta_despill": "hot-pink opaque remnants shifted to warm orange attack accents",
            "resampling": "Pillow Image.Resampling.NEAREST",
            "uniform_scale": round(scale, 10),
            "max_source_visible_dimensions": [max_source_width, max_source_height],
            "cell_size": spec.cell_size,
            "max_runtime_visible_envelope": [spec.max_visible_width, spec.max_visible_height],
            "baseline_exclusive": spec.baseline,
        },
        "runtime_art": {
            "sheet": image_record(sheet_path),
            "animation": file_record(anim_path),
            "tags": qa_tags,
        },
        "static_checks": static_checks,
    }


def main() -> int:
    assets = [pack_camp(spec) for spec in SPECS]
    payload = {
        "schema": "lol_mod.quality_missing_lol_camps_imagegen_pack.v1",
        "generator": "mods/lol_mod/tools/pack_quality_missing_lol_camps.py",
        "scope": "Static art processing and standby actor packing only; no game launch or runtime test.",
        "runtime_status": "art_ready_unmapped",
        "engine_slot_audit": {
            "tfm2_normal_jungle_actor_slots": ["rhino", "stump", "mushroom", "bee"],
            "normal_actor_slot_count": 4,
            "missing_lol_camp_identities": ["raptor", "krug"],
            "standby_variant_directory": "aseprite_resources/ingame/lol_camp_variants",
            "registered_in_mod_override": False,
            "included_in_build_manifest": False,
            "runtime_refresh_claimed": False,
            "limitation": (
                "TFM2 exposes four ordinary jungle actor resource contracts. These two LoL camp "
                "actors are complete standby art but do not create two additional spawn slots."
            ),
        },
        "assets": assets,
        "result": {
            "asset_count": len(assets),
            "all_static_checks_passed": all(
                all(asset["static_checks"].values()) for asset in assets
            ),
            "runtime_mapping_complete": False,
        },
    }
    QA_PATH.parent.mkdir(parents=True, exist_ok=True)
    QA_PATH.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(f"Wrote {QA_PATH.relative_to(MOD_ROOT)}")
    for asset in assets:
        sheet = asset["runtime_art"]["sheet"]
        print(
            f"{asset['runtime_name']}: {sheet['dimensions']} "
            f"status={asset['runtime_status']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
