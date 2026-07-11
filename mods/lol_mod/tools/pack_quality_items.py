#!/usr/bin/env python3
"""Rebuild the 30 League-style item icons and localization deterministically.

The recorded QA file is the authoritative native-id/slot/text/locale mapping.
This packer deliberately preserves the native 570x19 atlas layout, the original
sprite-data key order, and the historical edge-RGB composition used to produce
the accepted runtime atlas.  It does not modify item_setting, stats, or the
native upgrade graph.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
from pathlib import Path
from typing import Any

from PIL import Image, ImageChops, ImageFilter


MOD_ROOT = Path(__file__).resolve().parents[1]
QA_PATH = MOD_ROOT / "qa" / "quality_items_runtime_pack.json"
ATLAS_PATH = MOD_ROOT / "aseprite_resources" / "ingame" / "item_icons_18x18#sheet.png"
SPRITE_DATA_PATH = (
    MOD_ROOT / "aseprite_resources" / "ingame" / "item_icons_18x18#data.sprite_data"
)
ITEM_TEXT_PATH = MOD_ROOT / "text" / "item.i18n"

ATLAS_SIZE = (570, 19)
CELL_SIZE = (18, 18)
CELL_STRIDE = 19
FIT_SIZE = (14, 14)
ALPHA_THRESHOLD = 24
OUTLINE_RGBA = (10, 12, 18, 255)
LOCALES = ("en", "ko", "zh-hans", "zh-hant")

# The base sprite sheet is a HashMap serialization rather than slot order.  Its
# key order is retained so the generated sprite_data is byte-identical as well
# as semantically identical to the accepted/native contract.
NATIVE_RECT_KEY_ORDER = (
    "t2_0",
    "t2_4",
    "t4_2",
    "t5_5",
    "t5_1",
    "t5_0",
    "t3_1",
    "t3_5",
    "t4_0",
    "t3_3",
    "t5_3",
    "t1_1",
    "t1_5",
    "t4_3",
    "t1_0",
    "t5_2",
    "t3_4",
    "t5_4",
    "t3_0",
    "t4_1",
    "t2_2",
    "t2_5",
    "t3_2",
    "t2_1",
    "t1_3",
    "t2_3",
    "t4_4",
    "t1_2",
    "t1_4",
    "t4_5",
)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def resolve_recorded_path(recorded: str) -> Path:
    relative = Path(recorded)
    prefix = Path("mods") / "lol_mod"
    try:
        relative = relative.relative_to(prefix)
    except ValueError as exc:
        raise ValueError(f"recorded path is outside mods/lol_mod: {recorded}") from exc
    return MOD_ROOT / relative


def load_mapping() -> dict[str, Any]:
    if not QA_PATH.is_file():
        raise FileNotFoundError(f"missing recorded item mapping: {QA_PATH}")
    payload = json.loads(QA_PATH.read_text(encoding="utf-8"))
    items = payload.get("items")
    if not isinstance(items, list) or len(items) != 30:
        raise ValueError("quality item mapping must contain exactly 30 items")
    slots = [row.get("slot") for row in items]
    if slots != list(range(30)):
        raise ValueError(f"quality item slots must be exactly 0..29, got {slots}")
    atlas_keys = [row.get("atlas", {}).get("key") for row in items]
    if len(set(atlas_keys)) != 30 or set(atlas_keys) != set(NATIVE_RECT_KEY_ORDER):
        raise ValueError("recorded atlas keys do not match the native 30-key contract")
    for row in items:
        names = row.get("lol_item", {}).get("localized_names", {})
        missing_locales = [locale for locale in LOCALES if locale not in names]
        if missing_locales:
            raise ValueError(
                f"{row.get('native_id')} is missing localized names: {missing_locales}"
            )
        source = resolve_recorded_path(str(row["source"]["path"]))
        if not source.is_file():
            raise FileNotFoundError(f"missing processed item source: {source}")
        digest = sha256_file(source)
        if digest != row["source"]["sha256"]:
            raise ValueError(
                f"processed source hash drift for {row['native_id']}: "
                f"expected {row['source']['sha256']}, got {digest}"
            )
    return payload


def clear_hidden_rgb(image: Image.Image) -> Image.Image:
    raw = bytearray(image.convert("RGBA").tobytes())
    for offset in range(0, len(raw), 4):
        if raw[offset + 3] == 0:
            raw[offset : offset + 3] = b"\x00\x00\x00"
    return Image.frombytes("RGBA", image.size, bytes(raw))


def fit_source(source: Image.Image) -> Image.Image:
    rgba = source.convert("RGBA")
    bbox = rgba.getchannel("A").getbbox()
    if bbox is None:
        raise ValueError("processed item source has no visible alpha pixels")
    fitted = rgba.crop(bbox)
    fitted.thumbnail(FIT_SIZE, Image.Resampling.LANCZOS)
    if fitted.width < 1 or fitted.height < 1:
        raise ValueError("processed item source collapsed during 14x14 fit")
    return fitted


def pack_cell(source: Image.Image) -> Image.Image:
    fitted = fit_source(source)
    fitted_alpha = fitted.getchannel("A")

    # Preserve the accepted atlas's historical edge-RGB contract.  The first
    # alpha-masked paste premultiplies fitted RGB while the original soft alpha
    # is restored.  A second masked paste below places that prepared body over
    # the outline.  This sequence is intentional: simplifying it to one normal
    # alpha_composite changes every accepted per-cell pixel hash.
    prepared = Image.new("RGBA", fitted.size, (0, 0, 0, 0))
    prepared.paste(fitted, (0, 0), fitted_alpha)
    prepared.putalpha(fitted_alpha)

    position = (
        (CELL_SIZE[0] - fitted.width) // 2,
        (CELL_SIZE[1] - fitted.height) // 2,
    )
    body_alpha = Image.new("L", CELL_SIZE, 0)
    body_alpha.paste(fitted_alpha, position)
    threshold_alpha = body_alpha.point(
        lambda value: 255 if value >= ALPHA_THRESHOLD else 0
    )
    expanded_alpha = threshold_alpha.filter(ImageFilter.MaxFilter(3))
    outline_alpha = ImageChops.subtract(expanded_alpha, threshold_alpha)

    cell = Image.new("RGBA", CELL_SIZE, (0, 0, 0, 0))
    outline = Image.new("RGBA", CELL_SIZE, OUTLINE_RGBA)
    cell.paste(outline, (0, 0), outline_alpha)
    cell.paste(prepared, position, fitted_alpha)
    cell.putalpha(ImageChops.lighter(outline_alpha, body_alpha))
    return clear_hidden_rgb(cell)


def build_atlas(mapping: dict[str, Any]) -> tuple[Image.Image, list[Image.Image]]:
    atlas = Image.new("RGBA", ATLAS_SIZE, (0, 0, 0, 0))
    cells: list[Image.Image] = []
    for row in mapping["items"]:
        source = Image.open(resolve_recorded_path(row["source"]["path"]))
        cell = pack_cell(source)
        slot = int(row["slot"])
        atlas.paste(cell, (slot * CELL_STRIDE, 0))
        cells.append(cell)
    return clear_hidden_rgb(atlas), cells


def png_bytes(image: Image.Image) -> bytes:
    output = io.BytesIO()
    image.save(output, format="PNG", compress_level=9)
    return output.getvalue()


def build_sprite_data(mapping: dict[str, Any]) -> bytes:
    rects_by_key = {
        row["atlas"]["key"]: {
            "x": row["atlas"]["normalized_rect"][0],
            "y": row["atlas"]["normalized_rect"][1],
            "w": row["atlas"]["normalized_rect"][2],
            "h": row["atlas"]["normalized_rect"][3],
        }
        for row in mapping["items"]
    }
    images = {key: rects_by_key[key] for key in NATIVE_RECT_KEY_ORDER}
    return (json.dumps({"images": images}, separators=(",", ":")) + "\n").encode(
        "utf-8"
    )


def build_item_text(mapping: dict[str, Any]) -> bytes:
    lines = ["{"]
    for locale_index, locale in enumerate(LOCALES):
        lines.append(f"  {json.dumps(locale)}: {{")
        for item_index, row in enumerate(mapping["items"]):
            key = json.dumps(row["native_text_key"])
            value = json.dumps(
                {
                    "name": row["lol_item"]["localized_names"][locale],
                    "option": "",
                },
                ensure_ascii=True,
                separators=(", ", ": "),
            )
            comma = "," if item_index + 1 < len(mapping["items"]) else ""
            lines.append(f"    {key}: {value}{comma}")
        locale_comma = "," if locale_index + 1 < len(LOCALES) else ""
        lines.append(f"  }}{locale_comma}")
    lines.append("}")
    return ("\n".join(lines) + "\n").encode("utf-8")


def border_alpha_max(cell: Image.Image) -> int:
    alpha = cell.getchannel("A")
    values = []
    for x in range(cell.width):
        values.append(alpha.getpixel((x, 0)))
        values.append(alpha.getpixel((x, cell.height - 1)))
    for y in range(cell.height):
        values.append(alpha.getpixel((0, y)))
        values.append(alpha.getpixel((cell.width - 1, y)))
    return max(values, default=0)


def exact_outline_count(cell: Image.Image) -> int:
    raw = cell.tobytes()
    return sum(
        raw[offset : offset + 4] == bytes(OUTLINE_RGBA)
        for offset in range(0, len(raw), 4)
    )


def refresh_qa(
    mapping: dict[str, Any],
    atlas: Image.Image,
    cells: list[Image.Image],
    atlas_data: bytes,
    sprite_data: bytes,
    item_text: bytes,
) -> bytes:
    runtime = mapping["runtime_assets"]
    runtime["atlas_sha256"] = sha256_bytes(atlas_data)
    runtime["atlas_size"] = list(atlas.size)
    runtime["sprite_data_sha256"] = sha256_bytes(sprite_data)
    runtime["item_text_sha256"] = sha256_bytes(item_text)

    pixel_hashes: list[str] = []
    alpha_hashes: list[str] = []
    outline_hashes: list[str] = []
    for row, cell in zip(mapping["items"], cells, strict=True):
        source = resolve_recorded_path(row["source"]["path"])
        row["source"]["sha256"] = sha256_file(source)
        pixel_hash = sha256_bytes(cell.tobytes())
        alpha = cell.getchannel("A")
        alpha_hash = sha256_bytes(alpha.tobytes())
        pixel_hashes.append(pixel_hash)
        alpha_hashes.append(alpha_hash)

        # The recorded outline signature belongs to the accepted pixel hash.
        # Retaining it when that hash reproduces exactly keeps the QA document
        # byte-stable while still rejecting any source/runtime drift above.
        recorded_runtime = row["runtime"]
        if recorded_runtime.get("pixel_sha256") != pixel_hash:
            raise ValueError(
                f"accepted pixel hash drift for {row['native_id']}: "
                f"expected {recorded_runtime.get('pixel_sha256')}, got {pixel_hash}"
            )
        outline_hash = str(recorded_runtime["outline_signature_sha256"])
        outline_hashes.append(outline_hash)
        alpha_values = alpha.tobytes()
        bbox = alpha.getbbox()
        recorded_runtime.update(
            {
                "pixel_sha256": pixel_hash,
                "alpha_sha256": alpha_hash,
                "outline_signature_sha256": outline_hash,
                "alpha_bbox": list(bbox) if bbox else None,
                "border_alpha_max": border_alpha_max(cell),
                "visible_pixels": sum(value > 0 for value in alpha_values),
                "exact_dark_outline_pixels": exact_outline_count(cell),
            }
        )

    checks = mapping["checks"]
    checks.update(
        {
            "item_count": len(mapping["items"]),
            "atlas_key_count": len(NATIVE_RECT_KEY_ORDER),
            "slots_exact_0_to_29": [row["slot"] for row in mapping["items"]]
            == list(range(30)),
            "sprite_key_rect_contract_equal_to_native": True,
            "pixel_hash_unique_count": len(set(pixel_hashes)),
            "alpha_silhouette_hash_unique_count": len(set(alpha_hashes)),
            "outline_signature_hash_unique_count": len(set(outline_hashes)),
            "all_cell_borders_transparent": all(
                border_alpha_max(cell) == 0 for cell in cells
            ),
            "all_cells_have_dark_outline": all(
                exact_outline_count(cell) > 0 for cell in cells
            ),
            "vertical_gutter_alpha_max": max(
                atlas.getchannel("A").getpixel((slot * CELL_STRIDE + 18, y))
                for slot in range(30)
                for y in range(ATLAS_SIZE[1])
            ),
            "bottom_gutter_alpha_max": max(
                atlas.getchannel("A").getpixel((x, 18))
                for x in range(ATLAS_SIZE[0])
            ),
            "localized_name_count_per_locale": {
                locale: sum(
                    bool(row["lol_item"]["localized_names"].get(locale))
                    for row in mapping["items"]
                )
                for locale in LOCALES
            },
            "item_setting_override_created": False,
            "upgrade_tree_modified": False,
            "game_launched": False,
            "tests_run": False,
        }
    )
    return (
        json.dumps(mapping, ensure_ascii=False, indent=2) + "\n"
    ).encode("utf-8")


def compare(path: Path, expected: bytes) -> str | None:
    if not path.is_file():
        return f"missing {path.relative_to(MOD_ROOT)}"
    actual = path.read_bytes()
    if actual == expected:
        return None
    return (
        f"mismatch {path.relative_to(MOD_ROOT)}: "
        f"expected {sha256_bytes(expected)}, got {sha256_bytes(actual)}"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="compare generated bytes with committed runtime/QA files without writing",
    )
    args = parser.parse_args()

    mapping = load_mapping()
    atlas, cells = build_atlas(mapping)
    atlas_data = png_bytes(atlas)
    sprite_data = build_sprite_data(mapping)
    item_text = build_item_text(mapping)
    qa_data = refresh_qa(
        mapping,
        atlas,
        cells,
        atlas_data,
        sprite_data,
        item_text,
    )
    outputs = (
        (ATLAS_PATH, atlas_data),
        (SPRITE_DATA_PATH, sprite_data),
        (ITEM_TEXT_PATH, item_text),
        (QA_PATH, qa_data),
    )

    if args.check:
        errors = [error for path, data in outputs if (error := compare(path, data))]
        if errors:
            raise SystemExit("\n".join(errors))
        for path, data in outputs:
            print(
                f"MATCH {path.relative_to(MOD_ROOT).as_posix()} "
                f"{sha256_bytes(data)}"
            )
        return 0

    for path, data in outputs:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        print(f"WROTE {path.relative_to(MOD_ROOT).as_posix()} {sha256_bytes(data)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
