from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from statistics import median
import struct
from typing import Any

from PIL import Image


MOD_ROOT = Path(__file__).resolve().parents[1]
SOURCE_PATH = MOD_ROOT / "source" / "imagegen" / "ui" / "lol_bp_background_v2_source.png"
RUNTIME_PATH = MOD_ROOT / "ui" / "banpick" / "lol_bp_background.png"
TIMER_PLATE_SOURCE = MOD_ROOT / "source" / "imagegen" / "ui" / "lol_bp_timer_plate_v1_source.png"
TIMER_ICON_SOURCE = MOD_ROOT / "source" / "imagegen" / "ui" / "lol_bp_timer_icon_v1_source.png"
TIMER_PLATE_RUNTIME = MOD_ROOT / "ui" / "banpick" / "lol_bp_timer_plate.png"
TIMER_ICON_RUNTIME = MOD_ROOT / "ui" / "banpick" / "lol_bp_timer_icon.png"
HEADER_CHROME_SOURCE = MOD_ROOT / "source" / "imagegen" / "ui" / "lol_bp_header_chrome_v1_source.png"
BOTTOM_CHROME_SOURCE = MOD_ROOT / "source" / "imagegen" / "ui" / "lol_bp_bottom_chrome_v1_source.png"
CHAMPION_FRAME_SOURCE = MOD_ROOT / "source" / "imagegen" / "ui" / "lol_bp_champion_card_frame_v1_source.png"
PANEL_FRAME_SOURCE = MOD_ROOT / "source" / "imagegen" / "ui" / "lol_bp_panel_frame_v1_source.png"
CONTROL_FRAME_SOURCE = MOD_ROOT / "source" / "imagegen" / "ui" / "lol_bp_control_frame_v1_source.png"
SIDE_PICK_FRAME_SOURCE = MOD_ROOT / "source" / "imagegen" / "ui" / "lol_bp_side_pick_frame_v1_source.png"
HEADER_CHROME_RUNTIME = MOD_ROOT / "ui" / "banpick" / "lol_bp_header_chrome.png"
BOTTOM_CHROME_RUNTIME = MOD_ROOT / "ui" / "banpick" / "lol_bp_bottom_chrome.png"
CHAMPION_FRAME_RUNTIME = MOD_ROOT / "ui" / "banpick" / "lol_bp_champion_card_frame.png"
FILTER_TOOLBAR_RUNTIME = MOD_ROOT / "ui" / "banpick" / "lol_bp_filter_toolbar.png"
CHAMPION_GRID_RUNTIME = MOD_ROOT / "ui" / "banpick" / "lol_bp_champion_grid_frame.png"
STAT_FRAME_RUNTIME = MOD_ROOT / "ui" / "banpick" / "lol_bp_stat_frame.png"
SKILL_FRAME_RUNTIME = MOD_ROOT / "ui" / "banpick" / "lol_bp_skill_frame.png"
SIDE_PICK_FRAME_RUNTIME = MOD_ROOT / "ui" / "banpick" / "lol_bp_side_pick_frame.png"
LAYOUT_PATH = MOD_ROOT / "ui" / "layout" / "banpick" / "layout.ui"
CHAMPION_SLOT_PATH = MOD_ROOT / "ui" / "layout" / "banpick" / "champion_slot.ui"
BLUE_PICK_SLOT_PATH = MOD_ROOT / "ui" / "layout" / "banpick" / "blue_pick_slot.ui"
RED_PICK_SLOT_PATH = MOD_ROOT / "ui" / "layout" / "banpick" / "red_pick_slot.ui"
CONTROL_STYLE_PATH = MOD_ROOT / "style" / "bp_controls.style"
OVERRIDE_PATH = MOD_ROOT / "mod.override_info"
QA_PATH = MOD_ROOT / "qa" / "quality_bp_skin_imagegen_pack.json"
CONTACT_PATH = MOD_ROOT / "qa" / "quality_bp_component_contact.png"

RUNTIME_SIZE = (1920, 1080)
TIMER_PLATE_SIZE = (220, 20)
TIMER_ICON_SIZE = (20, 20)
HEADER_CHROME_SIZE = (1920, 50)
BOTTOM_CHROME_SIZE = (1920, 100)
CHAMPION_FRAME_SIZE = (132, 130)
CHAMPION_ICON_CANVAS_SIZE = (131.4444, 88)
CHAMPION_ICON_SAFE_TOP_PX = 0
CHAMPION_NAME_BAND_HEIGHT_PX = 38
HEADER_CHROME_TARGET_MARGINS = (14, 10, 14, 10)
BOTTOM_CHROME_TARGET_MARGINS = (16, 8, 16, 4)
FILTER_TOOLBAR_SIZE = (1310, 50)
CHAMPION_GRID_SIZE = (1300, 570)
STAT_FRAME_SIZE = (1300, 70)
SKILL_FRAME_SIZE = (427, 200)
SIDE_PICK_FRAME_SIZE = (300, 174)
CHROMA_KEY = (255, 0, 255)
CHROMA_TRANSPARENT_DISTANCE = 42.0
CHROMA_OPAQUE_DISTANCE = 118.0
NATIVE_LAYOUT_SHA256 = "3cf90d1a4ea61b3aa40a2821af969654f37f08bc60d14c70306ef286b1e40522"
NATIVE_LAYOUT_NORMALIZED_SHA256 = (
    "4ca21b5ef930e75602428a1951a68a60fa324e5b5a2b09da1748ed2080b95a93"
)
NATIVE_CHAMPION_SLOT_NORMALIZED_SHA256 = (
    "25b28e532e443bcabb357ec1e223bed55a334f881d4a8a53ab24652de8174d72"
)
NATIVE_BLUE_PICK_SLOT_NORMALIZED_SHA256 = (
    "bce47f951f8d469df30ba6daf35ee577f4a9fd01173793dcd6d8d8b9fe4e9c61"
)
NATIVE_RED_PICK_SLOT_NORMALIZED_SHA256 = (
    "b0f0492d2666d44d582596e965efb0a232c7576daeb2e612d61b37314be7b4c4"
)

BP_LAYOUT_ASSETS = {
    "layout": "asset/base/ui/layout/banpick/layout",
    "blue_pick_slot": "asset/base/ui/layout/banpick/blue_pick_slot",
    "red_pick_slot": "asset/base/ui/layout/banpick/red_pick_slot",
    "champion_slot": "asset/base/ui/layout/banpick/champion_slot",
}

IMAGEGEN_PROMPT = (
    "Original 16:9 restrained fantasy MOBA champion-draft background: nearly black navy "
    "centre, very faint blue and burgundy edge atmosphere, sparse antique-gold hairlines, "
    "no large motifs and enough low-contrast negative space for cards and text. No text, "
    "logos, champions, buttons, icons, or copied game UI."
)

TIMER_IMAGEGEN_PROMPTS = {
    "plate": (
        "Transparent/chroma-key background, one isolated 6:1 dark navy MOBA timer plate, "
        "thin antique-gold bezel and a very subtle cyan inner rim, no text, numbers, icon, "
        "logo, bloom, or cast shadow."
    ),
    "icon": (
        "Transparent/chroma-key background, one isolated front-facing fantasy MOBA hourglass "
        "timer emblem, readable at 20 pixels, pale gold frame with minimal cyan sand, no text, "
        "digits, logo, bloom, or cast shadow."
    ),
}

COMPONENT_IMAGEGEN_PROMPTS = {
    "header_chrome": "Chroma-key background, one wide premium fantasy MOBA draft header chrome, dark navy centre, blue left and muted red right accents, thin antique-gold trim, no text, logo, icon, or character.",
    "bottom_chrome": "Chroma-key background, one wide premium fantasy MOBA draft footer chrome, restrained blue left and muted red right accents, dark centre and thin antique-gold trim, no text, logo, icon, or character.",
    "champion_card_frame": "Chroma-key background, one isolated portrait champion-select card frame, slim dark metal and antique-gold/teal edge, transparent centre, no text, icon, logo, portrait, or shadow.",
}

COMPONENT_IMAGEGEN_REQUESTS = [
    {
        "id": "panel_frame",
        "source_path": "source/imagegen/ui/lol_bp_panel_frame_v1_source.png",
        "runtime_dimensions": [[1300, 570], [1300, 70], [427, 200]],
        "alpha": "keyed exterior; low-contrast dark centre; slim 9-slice-safe frame",
        "layout_reference": "champion grid, #champion_info #stat, and #skill1/#skill2/#ult",
    },
    {
        "id": "control_frame",
        "source_path": "source/imagegen/ui/lol_bp_control_frame_v1_source.png",
        "runtime_dimensions": [[40, 40], [220, 40], [170, 40], [260, 40], [110, 40], [290, 40], [645, 67]],
        "alpha": "keyed exterior; dark centre; 9-slice-safe 1-2px frame",
        "layout_reference": "category/position/search/delegate/swap controls",
    },
    {
        "id": "side_pick_frame",
        "source_path": "source/imagegen/ui/lol_bp_side_pick_frame_v1_source.png",
        "runtime_dimensions": [300, 174],
        "alpha": "keyed exterior; dark centre; restrained 9-slice-safe frame",
        "layout_reference": "blue_pick_slot.ui and red_pick_slot.ui root cards",
    },
]

LOL_BACKGROUND_BLOCK = """\

  #lol_bp_background:image {
    ignore_event: true;
    width: 100%;
    height: 100%;
    source: \"asset/lol_mod/ui/banpick/lol_bp_background\";
  }
"""

LOL_HEADER_CHROME_BLOCK = """\

    #lol_bp_header_chrome:image {
      ignore_event: true;
      width: 100%;
      height: 100%;
      source: "asset/lol_mod/ui/banpick/lol_bp_header_chrome";
    }
"""

LOL_BOTTOM_CHROME_BLOCK = """\

    #lol_bp_bottom_chrome:image {
      ignore_event: true;
      width: 100%;
      height: 100%;
      source: "asset/lol_mod/ui/banpick/lol_bp_bottom_chrome";
    }
"""

LOL_CHAMPION_FRAME_BLOCK = """\

  #lol_bp_champion_card_frame:image {
    ignore_event: true;
    width: 100%;
    height: 100%;
    source: "asset/lol_mod/ui/banpick/lol_bp_champion_card_frame";
  }
"""

LOL_FILTER_TOOLBAR_BLOCK = """\

  #lol_bp_filter_toolbar:image {
    ignore_event: true;
    x: 305px;
    y: 55px;
    width: 1310px;
    height: 50px;
    source: "asset/lol_mod/ui/banpick/lol_bp_filter_toolbar";
  }
"""

LOL_CHAMPION_GRID_BLOCK = """\

    #lol_bp_champion_grid_frame:image {
      ignore_event: true;
      width: 100%;
      height: 100%;
      source: "asset/lol_mod/ui/banpick/lol_bp_champion_grid_frame";
    }
"""

LOL_STAT_FRAME_BLOCK = """\

      #lol_bp_stat_frame:image {
        ignore_event: true;
        width: 100%;
        height: 100%;
        source: "asset/lol_mod/ui/banpick/lol_bp_stat_frame";
      }
"""

def lol_skill_frame_block(width: int) -> str:
    return f"""
      #lol_bp_skill_frame:image {{
        ignore_event: true;
        x: -10px;
        y: -10px;
        width: {width}px;
        height: 200px;
        source: \"asset/lol_mod/ui/banpick/lol_bp_skill_frame\";
      }}
"""


LOL_TIMER_PLATE_BLOCK = """\

      #lol_bp_timer_plate:image {
        ignore_event: true;
        width: 220px;
        height: 20px;
        source: "asset/lol_mod/ui/banpick/lol_bp_timer_plate";
      }
"""

LOL_TIMER_ICON_BLOCK = """\

      #lol_bp_timer_icon:image {
        ignore_event: true;
        width: 20px;
        height: 20px;
        source: "asset/lol_mod/ui/banpick/lol_bp_timer_icon";
      }
"""

LOL_SIDE_PICK_FRAME_BLOCK = """\

  #lol_bp_side_pick_frame:image {
    ignore_event: true;
    width: 100%;
    height: 100%;
    source: "asset/lol_mod/ui/banpick/lol_bp_side_pick_frame";
  }
"""

def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def image_record(path: Path) -> dict[str, Any]:
    with Image.open(path) as image:
        return {
            "path": path.relative_to(MOD_ROOT).as_posix(),
            "size_bytes": path.stat().st_size,
            "sha256": sha256(path),
            "dimensions": list(image.size),
            "mode": image.mode,
        }


def canonical_layout(text: str) -> str:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    return "\n".join(line.rstrip() for line in normalized.splitlines()) + "\n"


def find_bundle_path() -> Path:
    candidates = (
        MOD_ROOT.parents[2] / "bundle.game_data",
        MOD_ROOT.parents[1] / "bundle.game_data",
    )
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    raise FileNotFoundError(
        "Could not locate Teamfight Manager 2 bundle.game_data: "
        + ", ".join(str(candidate) for candidate in candidates)
    )


def _read_u32(handle: Any) -> int:
    raw = handle.read(4)
    if len(raw) != 4:
        raise EOFError("Unexpected end of bundle.game_data while reading u32")
    return struct.unpack("<I", raw)[0]


def read_native_bp_layouts(bundle_path: Path) -> tuple[dict[str, str], dict[str, dict[str, Any]]]:
    wanted = {asset_key: name for name, asset_key in BP_LAYOUT_ASSETS.items()}
    layouts: dict[str, str] = {}
    records: dict[str, dict[str, Any]] = {}
    with bundle_path.open("rb") as handle:
        for _index in range(_read_u32(handle)):
            type_length = _read_u32(handle)
            asset_type = handle.read(type_length).decode("utf-8", "strict")
            key_length = _read_u32(handle)
            key = handle.read(key_length).decode("utf-8", "strict")
            data_length = _read_u32(handle)
            if key not in wanted:
                handle.seek(data_length, 1)
                continue
            payload = handle.read(data_length)
            if len(payload) != data_length:
                raise EOFError(f"Truncated bundle entry: {key}")
            if asset_type != "ui":
                raise ValueError(f"Expected UI payload for {key}, got {asset_type!r}")
            name = wanted[key]
            text = canonical_layout(payload.decode("utf-8-sig", "strict"))
            layouts[name] = text
            records[name] = {
                "asset_key": key,
                "asset_type": asset_type,
                "raw_size_bytes": data_length,
                "raw_sha256": hashlib.sha256(payload).hexdigest(),
                "normalized_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
                "line_count": len(text.splitlines()),
            }
    missing = sorted(set(BP_LAYOUT_ASSETS) - set(layouts))
    if missing:
        raise KeyError(f"Missing native BP layouts in bundle.game_data: {missing}")
    return layouts, records


def _inject_before(text: str, marker: str, block: str, *, start: int = 0) -> str:
    index = text.find(marker, start)
    if index < 0:
        raise ValueError(f"BP 0.5.1 layout anchor not found: {marker!r}")
    return text[:index] + block + text[index:]


def _inject_before_in_node(text: str, node_marker: str, child_marker: str, block: str) -> str:
    node_index = text.find(node_marker)
    if node_index < 0:
        raise ValueError(f"BP 0.5.1 node not found: {node_marker!r}")
    child_index = text.find(child_marker, node_index)
    if child_index < 0:
        raise ValueError(
            f"BP 0.5.1 child anchor {child_marker!r} not found after {node_marker!r}"
        )
    return text[:child_index] + block + text[child_index:]


def _inject_child_before_close(text: str, node_marker: str, block: str) -> str:
    node_index = text.find(node_marker)
    if node_index < 0:
        raise ValueError(f"BP 0.5.1 node not found: {node_marker!r}")
    opening = text.find("{", node_index)
    depth = 0
    for index in range(opening, len(text)):
        if text[index] == "{":
            depth += 1
        elif text[index] == "}":
            depth -= 1
            if depth == 0:
                line_start = text.rfind("\n", opening, index) + 1
                return text[:line_start] + block + text[line_start:]
    raise ValueError(f"Unclosed BP 0.5.1 node: {node_marker!r}")


def decorate_native_layout(native: str) -> str:
    layout = canonical_layout(native)
    layout = _inject_before(layout, "\n  #header:color {", LOL_BACKGROUND_BLOCK)
    layout = _inject_before_in_node(
        layout, "#header:color {", "\n    #step:label {", LOL_HEADER_CHROME_BLOCK
    )
    layout = _inject_before_in_node(
        layout, "#bottom:color {", "\n    #matchup:label {", LOL_BOTTOM_CHROME_BLOCK
    )
    layout = _inject_before(
        layout, "\n  #prev_champion_category:color_icon_button {", LOL_FILTER_TOOLBAR_BLOCK
    )
    layout = _inject_child_before_close(
        layout, "#champions_bg:color {", LOL_CHAMPION_GRID_BLOCK
    )
    layout = _inject_before_in_node(
        layout, "#stat:empty {", "\n      #header:color {", LOL_STAT_FRAME_BLOCK
    )
    for skill_id, width in (("skill1", 427), ("skill2", 426), ("ult", 427)):
        layout = _inject_before_in_node(
            layout,
            f"#{skill_id}:color {{",
            "\n      #data:empty {",
            lol_skill_frame_block(width),
        )
    layout = _inject_before_in_node(
        layout,
        "#timer_bar_bg:color {",
        "\n      #timer_bar:color {",
        LOL_TIMER_PLATE_BLOCK,
    )
    layout = _inject_child_before_close(
        layout, "#timer_icon:image {", LOL_TIMER_ICON_BLOCK
    )
    return layout


def decorate_native_champion_slot(native: str) -> str:
    return _inject_before(
        canonical_layout(native), "\n  #icon:canvas {", LOL_CHAMPION_FRAME_BLOCK
    )


def decorate_native_pick_slot(native: str) -> str:
    return _inject_before(
        canonical_layout(native), "\n  #wait:empty {", LOL_SIDE_PICK_FRAME_BLOCK
    )


def _strip_exact_blocks(text: str, blocks: tuple[str, ...]) -> str:
    restored = text
    for block in blocks:
        if block not in restored:
            raise ValueError("Expected audited BP decoration block is missing")
        restored = restored.replace(block, "")
    return canonical_layout(restored)


def has_transparency(path: Path) -> bool:
    with Image.open(path) as image:
        alpha = image.convert("RGBA").getchannel("A")
        low, high = alpha.getextrema()
        return low == 0 and high > 0


def _sample_border_key(image: Image.Image) -> tuple[int, int, int]:
    rgb = image.convert("RGB")
    width, height = rgb.size
    pixels = rgb.load()
    band = max(2, min(width, height) // 100)
    step = max(1, min(width, height) // 256)
    samples: list[tuple[int, int, int]] = []
    for x in range(0, width, step):
        for y in range(band):
            samples.append(pixels[x, y])
            samples.append(pixels[x, height - 1 - y])
    for y in range(0, height, step):
        for x in range(band):
            samples.append(pixels[x, y])
            samples.append(pixels[width - 1 - x, y])
    return tuple(int(round(median(sample[channel] for sample in samples))) for channel in range(3))


def _smoothstep(value: float) -> float:
    value = max(0.0, min(1.0, value))
    return value * value * (3.0 - 2.0 * value)


def remove_magenta_key(image: Image.Image) -> tuple[Image.Image, dict[str, Any]]:
    rgba = image.convert("RGBA")
    key = _sample_border_key(rgba)
    pixels = rgba.load()
    width, height = rgba.size
    transparent = 0
    partial = 0
    for y in range(height):
        for x in range(width):
            red, green, blue, _alpha = pixels[x, y]
            distance = math.sqrt(
                (red - key[0]) ** 2 + (green - key[1]) ** 2 + (blue - key[2]) ** 2
            )
            if distance <= CHROMA_TRANSPARENT_DISTANCE:
                pixels[x, y] = (0, 0, 0, 0)
                transparent += 1
                continue
            if distance >= CHROMA_OPAQUE_DISTANCE:
                pixels[x, y] = (red, green, blue, 255)
                continue
            ratio = (distance - CHROMA_TRANSPARENT_DISTANCE) / (
                CHROMA_OPAQUE_DISTANCE - CHROMA_TRANSPARENT_DISTANCE
            )
            alpha = max(1, min(254, int(round(255.0 * _smoothstep(ratio)))))
            matte = 1.0 - alpha / 255.0
            foreground = []
            for value, key_value in zip((red, green, blue), key):
                foreground.append(
                    max(0, min(255, int(round((value - matte * key_value) / (alpha / 255.0)))))
                )
            pixels[x, y] = (*foreground, alpha)
            partial += 1
    bbox = rgba.getchannel("A").getbbox()
    if bbox is None:
        raise ValueError("ImageGen timer source became empty after magenta-key removal")
    return rgba.crop(bbox), {
        "sampled_key": list(key),
        "source_bbox": list(bbox),
        "transparent_pixels": transparent,
        "partial_alpha_pixels": partial,
    }


def pack_timer_asset(source: Path, runtime: Path, size: tuple[int, int], *, fit: bool) -> dict[str, Any]:
    with Image.open(source) as opened:
        keyed, key_record = remove_magenta_key(opened)
    if fit:
        scale = min((size[0] - 2) / keyed.width, (size[1] - 2) / keyed.height)
        fitted_size = (
            max(1, int(round(keyed.width * scale))),
            max(1, int(round(keyed.height * scale))),
        )
        fitted = keyed.resize(fitted_size, Image.Resampling.LANCZOS)
        packed = Image.new("RGBA", size, (0, 0, 0, 0))
        packed.alpha_composite(
            fitted,
            ((size[0] - fitted.width) // 2, (size[1] - fitted.height) // 2),
        )
    else:
        packed = keyed.resize(size, Image.Resampling.LANCZOS)
    runtime.parent.mkdir(parents=True, exist_ok=True)
    packed.save(runtime, optimize=True)
    return {
        "source": image_record(source),
        "runtime": image_record(runtime),
        "chroma_key": key_record,
    }


def nine_slice_resize(
    image: Image.Image,
    size: tuple[int, int],
    source_margins: tuple[int, int, int, int],
    target_margins: tuple[int, int, int, int],
) -> Image.Image:
    source = image.convert("RGBA")
    sw, sh = source.size
    tw, th = size
    sl, st, sr, sb = source_margins
    tl, tt, tr, tb = target_margins
    if sl + sr >= sw or st + sb >= sh or tl + tr >= tw or tt + tb >= th:
        raise ValueError("Invalid nine-slice margins")
    sx = (0, sl, sw - sr, sw)
    sy = (0, st, sh - sb, sh)
    tx = (0, tl, tw - tr, tw)
    ty = (0, tt, th - tb, th)
    output = Image.new("RGBA", size, (0, 0, 0, 0))
    for row in range(3):
        for col in range(3):
            piece = source.crop((sx[col], sy[row], sx[col + 1], sy[row + 1]))
            target_size = (tx[col + 1] - tx[col], ty[row + 1] - ty[row])
            piece = piece.resize(target_size, Image.Resampling.LANCZOS)
            output.alpha_composite(piece, (tx[col], ty[row]))
    return output


def decontaminate_magenta_edge_fringe(
    image: Image.Image,
    *,
    edge_band_px: int = 8,
) -> tuple[Image.Image, dict[str, int]]:
    """Re-hue only semi-transparent key spill at the outer chrome edge.

    The ImageGen sources use a hot-magenta matte.  Lanczos/nine-slice packing
    can leave a thin purple line even after alpha unmatting.  Keep the alpha
    and authored blue/red accents, but push spill pixels toward blue on the
    left, red on the right, and muted antique gold around the centre notch.
    """

    output = image.convert("RGBA")
    pixels = output.load()
    width, height = output.size
    candidates = 0
    recolored = 0
    for y in range(height):
        for x in range(width):
            if not (
                x < edge_band_px
                or x >= width - edge_band_px
                or y < edge_band_px
                or y >= height - edge_band_px
            ):
                continue
            red, green, blue, alpha = pixels[x, y]
            high = max(red, blue)
            low = min(red, blue)
            magenta_dominant = (
                0 < alpha < 255
                and high >= 55
                and low >= high * 0.68
                and green <= low * 0.65
            )
            if not magenta_dominant:
                continue
            candidates += 1
            if x < width * 0.45:
                pixels[x, y] = (
                    min(red, int(round(blue * 0.42))),
                    max(green, int(round(blue * 0.25))),
                    blue,
                    alpha,
                )
            elif x > width * 0.55:
                pixels[x, y] = (
                    red,
                    max(green, int(round(red * 0.25))),
                    min(blue, int(round(red * 0.42))),
                    alpha,
                )
            else:
                value = max(green, int(round((red + blue) * 0.26)))
                pixels[x, y] = (
                    min(255, int(round(value * 1.12))),
                    value,
                    int(round(value * 0.62)),
                    alpha,
                )
            recolored += 1

    remaining = 0
    for y in range(height):
        for x in range(width):
            if not (
                x < edge_band_px
                or x >= width - edge_band_px
                or y < edge_band_px
                or y >= height - edge_band_px
            ):
                continue
            red, green, blue, alpha = pixels[x, y]
            high = max(red, blue)
            low = min(red, blue)
            if (
                0 < alpha < 255
                and high >= 55
                and low >= high * 0.68
                and green <= low * 0.65
            ):
                remaining += 1
    return output, {
        "edge_band_px": edge_band_px,
        "magenta_dominant_partial_pixels_before": candidates,
        "recolored_pixels": recolored,
        "magenta_dominant_partial_pixels_after": remaining,
    }


def pack_component_asset(
    source: Path,
    runtime: Path,
    size: tuple[int, int],
    *,
    source_margin_ratio: tuple[float, float] | None = None,
    target_margins: tuple[int, int, int, int] | None = None,
    horizontal_backing_strip: tuple[int, int] | None = None,
    decontaminate_magenta_fringe: bool = False,
) -> dict[str, Any]:
    with Image.open(source) as opened:
        keyed, key_record = remove_magenta_key(opened)
    if source_margin_ratio is None:
        packed = keyed.resize(size, Image.Resampling.LANCZOS)
        method = "alpha_bbox_direct_resize"
    else:
        mx = max(1, int(round(keyed.width * source_margin_ratio[0])))
        my = max(1, int(round(keyed.height * source_margin_ratio[1])))
        assert target_margins is not None
        packed = nine_slice_resize(
            keyed,
            size,
            (mx, my, mx, my),
            target_margins,
        )
        method = "alpha_bbox_nine_slice"
    if horizontal_backing_strip is not None:
        strip_left, strip_right = horizontal_backing_strip
        if not (0 <= strip_left < strip_right <= packed.width):
            raise ValueError("Invalid horizontal backing strip")
        original_corner_pixels = {
            (0, 0): packed.getpixel((0, 0)),
            (packed.width - 1, 0): packed.getpixel((packed.width - 1, 0)),
            (0, packed.height - 1): packed.getpixel((0, packed.height - 1)),
            (packed.width - 1, packed.height - 1): packed.getpixel(
                (packed.width - 1, packed.height - 1)
            ),
        }
        backing = packed.crop((strip_left, 0, strip_right, packed.height)).resize(
            packed.size,
            Image.Resampling.LANCZOS,
        )
        backing.alpha_composite(packed)
        packed = backing
        for point, pixel in original_corner_pixels.items():
            packed.putpixel(point, pixel)
        method += "_horizontal_backing"
    fringe_record: dict[str, int] | None = None
    if decontaminate_magenta_fringe:
        packed, fringe_record = decontaminate_magenta_edge_fringe(packed)
        method += "_edge_defringe"
    runtime.parent.mkdir(parents=True, exist_ok=True)
    packed.save(runtime, optimize=True)
    return {
        "source": image_record(source),
        "runtime": image_record(runtime),
        "chroma_key": key_record,
        "packing_method": method,
        "target_margins_px": list(target_margins) if target_margins else None,
        "runtime_safe_insets_px": [0, 0, 0, 0],
        "horizontal_backing_strip_px": (
            list(horizontal_backing_strip) if horizontal_backing_strip else None
        ),
        "edge_defringe": fringe_record,
    }


def build_component_contact() -> None:
    canvas = Image.new("RGBA", (1200, 800), (5, 12, 20, 255))
    with Image.open(HEADER_CHROME_RUNTIME) as header:
        canvas.alpha_composite(header.convert("RGBA").resize((1200, 53), Image.Resampling.LANCZOS), (0, 0))
    with Image.open(FILTER_TOOLBAR_RUNTIME) as toolbar:
        canvas.alpha_composite(toolbar.convert("RGBA").resize((1008, 40), Image.Resampling.LANCZOS), (96, 65))
    with Image.open(CHAMPION_GRID_RUNTIME) as grid:
        canvas.alpha_composite(grid.convert("RGBA").resize((600, 181), Image.Resampling.LANCZOS), (20, 120))
    with Image.open(STAT_FRAME_RUNTIME) as stat:
        canvas.alpha_composite(stat.convert("RGBA").resize((350, 237), Image.Resampling.LANCZOS), (625, 120))
    with Image.open(SKILL_FRAME_RUNTIME) as skill:
        canvas.alpha_composite(skill.convert("RGBA").resize((600, 100), Image.Resampling.LANCZOS), (20, 320))
    with Image.open(SIDE_PICK_FRAME_RUNTIME) as side:
        canvas.alpha_composite(side.convert("RGBA").resize((450, 261), Image.Resampling.LANCZOS), (20, 440))
    with Image.open(BOTTOM_CHROME_RUNTIME) as bottom:
        canvas.alpha_composite(bottom.convert("RGBA").resize((1200, 94), Image.Resampling.LANCZOS), (0, 706))
    with Image.open(CHAMPION_FRAME_RUNTIME) as frame:
        canvas.alpha_composite(frame.convert("RGBA").resize((238, 260), Image.Resampling.NEAREST), (500, 440))
    with Image.open(TIMER_PLATE_RUNTIME) as plate:
        canvas.alpha_composite(plate.convert("RGBA").resize((340, 40), Image.Resampling.NEAREST), (800, 455))
    with Image.open(TIMER_ICON_RUNTIME) as icon:
        canvas.alpha_composite(icon.convert("RGBA").resize((80, 80), Image.Resampling.NEAREST), (930, 525))
    CONTACT_PATH.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(CONTACT_PATH, optimize=True)


def restored_native_champion_slot_hash(layout: str) -> str:
    restored = _strip_exact_blocks(layout, (LOL_CHAMPION_FRAME_BLOCK,))
    return hashlib.sha256(restored.encode("utf-8")).hexdigest()


def restored_native_layout(layout: str) -> str:
    return _strip_exact_blocks(
        layout,
        (
            LOL_BACKGROUND_BLOCK,
            LOL_HEADER_CHROME_BLOCK,
            LOL_BOTTOM_CHROME_BLOCK,
            LOL_FILTER_TOOLBAR_BLOCK,
            LOL_CHAMPION_GRID_BLOCK,
            LOL_STAT_FRAME_BLOCK,
            lol_skill_frame_block(427),
            lol_skill_frame_block(426),
            LOL_TIMER_PLATE_BLOCK,
            LOL_TIMER_ICON_BLOCK,
        ),
    )


def restored_native_layout_hash(layout: str) -> str:
    return hashlib.sha256(restored_native_layout(layout).encode("utf-8")).hexdigest()


def restored_native_pick_slot_hash(layout: str) -> str:
    restored = _strip_exact_blocks(layout, (LOL_SIDE_PICK_FRAME_BLOCK,))
    return hashlib.sha256(restored.encode("utf-8")).hexdigest()


def main() -> int:
    required_files = (
        SOURCE_PATH,
        TIMER_PLATE_SOURCE,
        TIMER_ICON_SOURCE,
        HEADER_CHROME_SOURCE,
        BOTTOM_CHROME_SOURCE,
        CHAMPION_FRAME_SOURCE,
        PANEL_FRAME_SOURCE,
        CONTROL_FRAME_SOURCE,
        SIDE_PICK_FRAME_SOURCE,
        CONTROL_STYLE_PATH,
    )
    for required in required_files:
        if not required.is_file():
            raise FileNotFoundError(required)

    bundle_path = find_bundle_path()
    native_layouts, native_records = read_native_bp_layouts(bundle_path)
    expected_native_hashes = {
        "layout": NATIVE_LAYOUT_NORMALIZED_SHA256,
        "blue_pick_slot": NATIVE_BLUE_PICK_SLOT_NORMALIZED_SHA256,
        "red_pick_slot": NATIVE_RED_PICK_SLOT_NORMALIZED_SHA256,
        "champion_slot": NATIVE_CHAMPION_SLOT_NORMALIZED_SHA256,
    }
    for name, expected_hash in expected_native_hashes.items():
        actual_hash = native_records[name]["normalized_sha256"]
        if actual_hash != expected_hash:
            raise ValueError(
                f"Unsupported BP native layout for {name}: {actual_hash}; "
                f"expected Teamfight Manager 2 base 0.5.1 hash {expected_hash}"
            )

    generated_layouts = {
        "layout": decorate_native_layout(native_layouts["layout"]),
        "blue_pick_slot": decorate_native_pick_slot(native_layouts["blue_pick_slot"]),
        "red_pick_slot": decorate_native_pick_slot(native_layouts["red_pick_slot"]),
        "champion_slot": decorate_native_champion_slot(native_layouts["champion_slot"]),
    }
    for name, text in generated_layouts.items():
        target = MOD_ROOT / "ui" / "layout" / "banpick" / f"{name}.ui"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8", newline="\n")

    with Image.open(SOURCE_PATH) as opened:
        background = opened.convert("RGBA").resize(RUNTIME_SIZE, Image.Resampling.LANCZOS)
    RUNTIME_PATH.parent.mkdir(parents=True, exist_ok=True)
    background.save(RUNTIME_PATH, optimize=True)

    timer_plate = pack_timer_asset(
        TIMER_PLATE_SOURCE, TIMER_PLATE_RUNTIME, TIMER_PLATE_SIZE, fit=False
    )
    timer_icon = pack_timer_asset(
        TIMER_ICON_SOURCE, TIMER_ICON_RUNTIME, TIMER_ICON_SIZE, fit=True
    )
    header_chrome = pack_component_asset(
        HEADER_CHROME_SOURCE,
        HEADER_CHROME_RUNTIME,
        HEADER_CHROME_SIZE,
        source_margin_ratio=(0.11, 0.24),
        target_margins=HEADER_CHROME_TARGET_MARGINS,
        # Reuse the generated quiet centre field as a straight backing.  The
        # original ImageGen crop has tapered/open ends, while the native
        # delegate and swap controls reach into both 320px side regions.
        horizontal_backing_strip=(700, 820),
        decontaminate_magenta_fringe=True,
    )
    bottom_chrome = pack_component_asset(
        BOTTOM_CHROME_SOURCE,
        BOTTOM_CHROME_RUNTIME,
        BOTTOM_CHROME_SIZE,
        # The footer source's diagonal wedges occupy roughly the outer
        # quarter of the keyed artwork.  Capture the whole wedge in the
        # nine-slice corner before compressing it to the 16px viewport rim.
        source_margin_ratio=(0.25, 0.24),
        # The generated source has deep centre notches.  Compress only those
        # decorative top/bottom bands so the native team row, match label,
        # ban slots, and corner tools remain inside a quiet footer field.
        target_margins=BOTTOM_CHROME_TARGET_MARGINS,
        # Give the native outer 300px pick/coach columns a continuous dark
        # field.  With 16px side margins, the generated diagonal wings stay
        # at the viewport edge instead of crossing those columns.
        horizontal_backing_strip=(700, 820),
        decontaminate_magenta_fringe=True,
    )
    champion_frame = pack_component_asset(
        CHAMPION_FRAME_SOURCE,
        CHAMPION_FRAME_RUNTIME,
        CHAMPION_FRAME_SIZE,
    )
    filter_toolbar = pack_component_asset(
        CONTROL_FRAME_SOURCE,
        FILTER_TOOLBAR_RUNTIME,
        FILTER_TOOLBAR_SIZE,
        source_margin_ratio=(0.09, 0.28),
        target_margins=(20, 8, 20, 8),
    )
    champion_grid_frame = pack_component_asset(
        PANEL_FRAME_SOURCE,
        CHAMPION_GRID_RUNTIME,
        CHAMPION_GRID_SIZE,
        source_margin_ratio=(0.08, 0.18),
        target_margins=(18, 14, 18, 14),
    )
    stat_frame = pack_component_asset(
        PANEL_FRAME_SOURCE,
        STAT_FRAME_RUNTIME,
        STAT_FRAME_SIZE,
        source_margin_ratio=(0.08, 0.18),
        target_margins=(16, 14, 16, 14),
    )
    skill_frame = pack_component_asset(
        PANEL_FRAME_SOURCE,
        SKILL_FRAME_RUNTIME,
        SKILL_FRAME_SIZE,
        source_margin_ratio=(0.08, 0.18),
        target_margins=(16, 10, 16, 10),
    )
    side_pick_frame = pack_component_asset(
        SIDE_PICK_FRAME_SOURCE,
        SIDE_PICK_FRAME_RUNTIME,
        SIDE_PICK_FRAME_SIZE,
        source_margin_ratio=(0.10, 0.16),
        target_margins=(14, 14, 14, 14),
    )
    build_component_contact()

    layout = LAYOUT_PATH.read_text(encoding="utf-8")
    champion_slot = CHAMPION_SLOT_PATH.read_text(encoding="utf-8")
    blue_pick_slot = BLUE_PICK_SLOT_PATH.read_text(encoding="utf-8")
    red_pick_slot = RED_PICK_SLOT_PATH.read_text(encoding="utf-8")
    control_style = CONTROL_STYLE_PATH.read_text(encoding="utf-8")
    override = json.loads(OVERRIDE_PATH.read_text(encoding="utf-8"))
    forbidden_bvp_ids = (
        "bp_settings",
        "bp_skin_cycle",
        "bp_illust_cycle",
        "bp_redflip_toggle",
        "bp_hoverbg_toggle",
    )
    geometry_contract = {
        "header_85": "height: 85px;" in layout,
        "bottom_150": "height: 150px;" in layout,
        "blue_picks_native": "#blue_picks:empty {\n    y: 97px;\n\n    width: 300px;" in layout,
        "red_picks_native": "#red_picks:empty {\n    anchor_x: 1;\n    pivot_x: 1;\n    y: 97px;" in layout,
        "champion_grid_native": (
            "#champions_bg:color {\n    width: 1250px;\n    height: 377px;"
            in layout
            and "x: 335px;\n    y: 145px;" in layout
        ),
        "champion_info_native": (
            "#champion_info:empty {\n    width: 1250px;\n    height: 371px;" in layout
            and "y:536px;" in layout
        ),
        "swap_native": (
            "#swap:empty {\n    width: 1290px;\n    height: 738px;" in layout
            and "x: 315px;\n    y: 97px;" in layout
        ),
        "timer_area_native": (
            "#timer_area:empty {\n    visible: false;\n    x: 1345px;\n    y: 95px;\n    width: 240px;\n    height: 40px;"
            in layout
            and "child_type: LeftToRight {\n      spacing: 4px;" in layout
        ),
        "timer_bar_native": (
            "#timer_bar_bg:image {\n      width: 170px;\n      height: 20px;\n      y: 10px;"
            in layout
        ),
        "champion_slot_native": (
            "width: 119px;\n  height: 130px;" in champion_slot
            and "#icon:canvas {\n    width: 118px;\n    height: 88px;\n    y: 4px;"
            in champion_slot
            and "down_height: 38;" in champion_slot
        ),
        "pick_slots_native": all(
            "width: 300px;" in slot
            and "height: 174px;" in slot
            and "width: 15px;" in slot
            and "height: 172px;" in slot
            for slot in (blue_pick_slot, red_pick_slot)
        ),
        "skill_cards_native": all(
            marker in layout
            for marker in (
                "#skill1:color {\n      width: 687px;\n      height: 115px;\n      x: 563px;",
                "#skill2:color {\n      width: 687px;\n      height: 115px;\n      x: 563px;\n      y: 128px;",
                "#ult:color {\n      width: 687px;\n      height: 115px;\n      x: 563px;\n      y: 256px;",
            )
        ),
    }
    static_checks = {
        "runtime_dimensions_1920x1080": background.size == RUNTIME_SIZE,
        "decorative_node_is_noninteractive": (
            "#lol_bp_background:image" in layout
            and "ignore_event: true;" in layout.split("#lol_bp_background:image", 1)[1].split("}", 1)[0]
        ),
        "decorative_source_is_mod_local": (
            'source: "asset/lol_mod/ui/banpick/lol_bp_background";' in layout
        ),
        "decorative_source_not_champion_scan_candidate": "/champions/" not in LOL_BACKGROUND_BLOCK,
        "native_geometry_contract": all(geometry_contract.values()),
        "bvp_runtime_nodes_absent": not any(marker in layout for marker in forbidden_bvp_ids),
        "v1_background_source_removed": not (
            MOD_ROOT / "source/imagegen/ui/lol_bp_background_v1_source.png"
        ).exists(),
        "timer_plate_is_visibility_scoped": (
            "#lol_bp_timer_plate:image" not in layout
            and "#timer_bar_bg:image" in layout
            and 'source: "asset/lol_mod/ui/banpick/lol_bp_timer_plate";' in layout
        ),
        "timer_icon_is_imagegen_asset": (
            'source: "asset/lol_mod/ui/banpick/lol_bp_timer_icon";' in layout
        ),
        "timer_runtime_dimensions": (
            timer_plate["runtime"]["dimensions"] == list(TIMER_PLATE_SIZE)
            and timer_icon["runtime"]["dimensions"] == list(TIMER_ICON_SIZE)
        ),
        "timer_runtime_has_alpha": (
            has_transparency(TIMER_PLATE_RUNTIME) and has_transparency(TIMER_ICON_RUNTIME)
        ),
        "bp_controls_use_local_style_only": (
            'asset/lol_mod/style/bp_controls#tertiary_button' in layout
            and 'asset/lol_mod/style/bp_controls#dropdown' in layout
            and 'asset/lol_mod/style/bp_controls#text_edit' in layout
            and "tertiary_button:" in control_style
            and "primary_button:" in control_style
            and "secondary_button:" in control_style
            and "dropdown:" in control_style
            and "text_edit:" in control_style
            and "asset/base/style/main" not in override
        ),
        "legacy_bp_component_overrides_disabled_for_base_0_5_1": all(
            key not in override
            for key in (
                "asset/base/ui/layout/banpick/blue_pick_slot",
                "asset/base/ui/layout/banpick/red_pick_slot",
                "asset/base/ui/layout/banpick/champion_slot",
            )
        ),
        "champion_preview_uses_safe_top_inset": (
            f"width: {CHAMPION_ICON_CANVAS_SIZE[0]}px;\n"
            f"    height: {CHAMPION_ICON_CANVAS_SIZE[1]}px;\n"
            f"    y: {CHAMPION_ICON_SAFE_TOP_PX}px;"
            in champion_slot
        ),
        "champion_preview_stops_before_name_band": (
            CHAMPION_ICON_SAFE_TOP_PX + CHAMPION_ICON_CANVAS_SIZE[1]
            <= CHAMPION_FRAME_SIZE[1] - CHAMPION_NAME_BAND_HEIGHT_PX
        ),
        "champion_frame_uses_proven_native_sibling_order": (
            champion_slot.index("#lol_bp_champion_card_frame:image")
            < champion_slot.index("#icon:canvas")
            and "z:" not in champion_slot.split(
                "#lol_bp_champion_card_frame:image", 1
            )[1].split("}", 1)[0]
            and "ignore_event: true;" in champion_slot.split(
                "#lol_bp_champion_card_frame:image", 1
            )[1].split("}", 1)[0]
        ),
        "header_footer_chrome_uses_control_safe_margins_and_backing": (
            header_chrome["target_margins_px"]
            == list(HEADER_CHROME_TARGET_MARGINS)
            and bottom_chrome["target_margins_px"]
            == list(BOTTOM_CHROME_TARGET_MARGINS)
            and header_chrome["runtime_safe_insets_px"] == [0, 0, 0, 0]
            and bottom_chrome["runtime_safe_insets_px"] == [0, 0, 0, 0]
            and header_chrome["horizontal_backing_strip_px"] == [700, 820]
            and bottom_chrome["horizontal_backing_strip_px"] == [700, 820]
        ),
        "header_footer_chrome_has_no_magenta_key_fringe": (
            header_chrome["edge_defringe"] is not None
            and bottom_chrome["edge_defringe"] is not None
            and header_chrome["edge_defringe"][
                "magenta_dominant_partial_pixels_before"
            ]
            > 0
            and bottom_chrome["edge_defringe"][
                "magenta_dominant_partial_pixels_before"
            ]
            > 0
            and header_chrome["edge_defringe"][
                "magenta_dominant_partial_pixels_after"
            ]
            == 0
            and bottom_chrome["edge_defringe"][
                "magenta_dominant_partial_pixels_after"
            ]
            == 0
        ),
        "component_palette_is_lol_style": (
            "normal: #29475cff;" in champion_slot
            and "hover: #c8aa6eff;" in champion_slot
            and "back_color: #07131ff2;" in champion_slot
            and "back_color: #07131ff2;" in blue_pick_slot
            and "back_color: #180a0ff2;" in red_pick_slot
            and "color: #08131ef7;" in layout
        ),
        "component_imagegen_runtime_dimensions": (
            header_chrome["runtime"]["dimensions"] == list(HEADER_CHROME_SIZE)
            and bottom_chrome["runtime"]["dimensions"] == list(BOTTOM_CHROME_SIZE)
            and champion_frame["runtime"]["dimensions"] == list(CHAMPION_FRAME_SIZE)
            and filter_toolbar["runtime"]["dimensions"] == list(FILTER_TOOLBAR_SIZE)
            and champion_grid_frame["runtime"]["dimensions"] == list(CHAMPION_GRID_SIZE)
            and stat_frame["runtime"]["dimensions"] == list(STAT_FRAME_SIZE)
            and skill_frame["runtime"]["dimensions"] == list(SKILL_FRAME_SIZE)
            and side_pick_frame["runtime"]["dimensions"] == list(SIDE_PICK_FRAME_SIZE)
        ),
        "component_imagegen_runtime_has_alpha": all(
            has_transparency(path)
            for path in (
                HEADER_CHROME_RUNTIME,
                BOTTOM_CHROME_RUNTIME,
                CHAMPION_FRAME_RUNTIME,
                FILTER_TOOLBAR_RUNTIME,
                CHAMPION_GRID_RUNTIME,
                STAT_FRAME_RUNTIME,
                SKILL_FRAME_RUNTIME,
                SIDE_PICK_FRAME_RUNTIME,
            )
        ),
        "component_overlays_are_noninteractive": all(
            f"#{node}:image" in text
            and "ignore_event: true;" in text.split(f"#{node}:image", 1)[1].split("}", 1)[0]
            for node, text in (
                ("lol_bp_header_chrome", layout),
                ("lol_bp_bottom_chrome", layout),
                ("lol_bp_filter_toolbar", layout),
                ("lol_bp_champion_grid_frame", layout),
                ("lol_bp_stat_frame", layout),
                ("lol_bp_skill_frame", layout),
                ("lol_bp_champion_card_frame", champion_slot),
                ("lol_bp_side_pick_frame", blue_pick_slot),
                ("lol_bp_side_pick_frame", red_pick_slot),
            )
        ),
        "champion_slot_restores_after_skin_delta": (
            restored_native_champion_slot_hash(champion_slot)
            == NATIVE_CHAMPION_SLOT_NORMALIZED_SHA256
        ),
        "component_contact_generated": (
            CONTACT_PATH.is_file()
            and image_record(CONTACT_PATH)["dimensions"] == [1200, 800]
        ),
        "native_layout_restores_after_skin_delta": (
            restored_native_layout_hash(layout) == NATIVE_LAYOUT_NORMALIZED_SHA256
        ),
        "legacy_bp_layout_override_disabled_for_base_0_5_1": (
            "asset/base/ui/layout/banpick/layout" not in override
        ),
    }

    # Base 0.5.1 replaced most Ban/Pick geometry.  The compatibility contract
    # below intentionally supersedes the archived 0.5.0 checks above: every
    # generated file is the current bundle payload plus audited ignore-event
    # image children only.
    geometry_contract = {
        "header_50": "#header:color {\n    color: #161721ff;\n    width: 100%;\n    height: 50px;" in layout,
        "bottom_100": "#bottom:color {\n    color: #161721ff;\n\n    width: 100%;\n    height: 100px;" in layout,
        "blue_picks_0_5_1": "#blue_picks:empty {\n    y: 60px;\n\n    width: 300px;\n    height: 910px;" in layout,
        "red_picks_0_5_1": "#red_picks:empty {\n    anchor_x: 1;\n    pivot_x: 1;\n    y: 60px;" in layout,
        "champion_grid_0_5_1": (
            "#champions_bg:color {\n    width: 1300px;\n    height: 570px;" in layout
            and "#champions:scroll_view {\n    width: 1300px;\n    height: 570px;\n\n    x: 310px;\n    y: 110px;" in layout
        ),
        "champion_info_0_5_1": (
            "#champion_info:empty {\n    width: 1300px;\n    height: 280px;" in layout
            and "#stat:empty {" in layout
            and "#stat:color {" not in layout
        ),
        "skill_cards_0_5_1": all(
            marker in layout
            for marker in (
                "#skill1:color {\n      width: 427px;\n      height: 200px;\n      x: 0px;\n      y: 80px;",
                "#skill2:color {\n      width: 426px;\n      height: 200px;\n      x: 437px;\n      y: 80px;",
                "#ult:color {\n      width: 427px;\n      height: 200px;\n      x: 873px;\n      y: 80px;",
            )
        ),
        "timer_0_5_1": (
            "#timer_area:empty {\n    visible: false;\n    x: 1310px;\n    y: 60px;\n    width: 290px;" in layout
            and "#timer_bar_bg:color {\n      width: 220px;" in layout
        ),
        "swap_0_5_1": (
            "#swap:empty {\n    width: 1300px;\n    height: 910px;\n\n    x: 310px;\n    y: 60px;" in layout
        ),
        "champion_slot_0_5_1": (
            "width: 132.4444px;\n  height: 130px;" in champion_slot
            and "#icon:canvas {\n    width: 131.4444px;\n    height: 88px;" in champion_slot
        ),
        "pick_slots_0_5_1": all(
            "width: 300px;" in slot
            and "height: 174px;" in slot
            and "width: 8px;" in slot
            and "#turn_outline:color" in slot
            for slot in (blue_pick_slot, red_pick_slot)
        ),
    }
    expected_overrides = {
        asset_key: {
            "remapping": asset_key.replace("asset/base/", "asset/lol_mod/", 1),
            "type": "override",
        }
        for asset_key in BP_LAYOUT_ASSETS.values()
    }
    static_checks = {
        "bundle_is_current_base_0_5_1": all(
            native_records[name]["normalized_sha256"] == expected_hash
            for name, expected_hash in expected_native_hashes.items()
        ),
        "native_geometry_contract": all(geometry_contract.values()),
        "required_0_5_1_runtime_nodes_present": (
            "#champion_pool_wait_overlay:color" in layout
            and 'text: "#asset/base/text/champion?stat.skill";' in layout
            and 'text: "#asset/base/text/champion?stat.skill2";' in layout
            and 'text: "#asset/base/text/champion?stat.ult";' in layout
            and "#turn_outline:color" in blue_pick_slot
            and "#turn_outline:color" in red_pick_slot
        ),
        "native_node_types_preserved": (
            "#stat:empty" in layout
            and "#stat:color" not in layout
            and "#timer_bar_bg:color" in layout
            and "#timer_bar_bg:image" not in layout
        ),
        "layout_restores_exact_native": restored_native_layout(layout) == native_layouts["layout"],
        "champion_slot_restores_exact_native": (
            _strip_exact_blocks(champion_slot, (LOL_CHAMPION_FRAME_BLOCK,))
            == native_layouts["champion_slot"]
        ),
        "blue_pick_slot_restores_exact_native": (
            _strip_exact_blocks(blue_pick_slot, (LOL_SIDE_PICK_FRAME_BLOCK,))
            == native_layouts["blue_pick_slot"]
        ),
        "red_pick_slot_restores_exact_native": (
            _strip_exact_blocks(red_pick_slot, (LOL_SIDE_PICK_FRAME_BLOCK,))
            == native_layouts["red_pick_slot"]
        ),
        "all_four_overrides_registered": all(
            override.get(asset_key) == expected
            for asset_key, expected in expected_overrides.items()
        ),
        "decorative_nodes_are_noninteractive": all(
            all(
                "ignore_event: true;" in block.split("}", 1)[0]
                for block in text.split(f"#{node}:image")[1:]
            )
            and text.count(f"#{node}:image") == expected_count
            for node, text, expected_count in (
                ("lol_bp_background", layout, 1),
                ("lol_bp_header_chrome", layout, 1),
                ("lol_bp_bottom_chrome", layout, 1),
                ("lol_bp_filter_toolbar", layout, 1),
                ("lol_bp_champion_grid_frame", layout, 1),
                ("lol_bp_stat_frame", layout, 1),
                ("lol_bp_skill_frame", layout, 3),
                ("lol_bp_timer_plate", layout, 1),
                ("lol_bp_timer_icon", layout, 1),
                ("lol_bp_champion_card_frame", champion_slot, 1),
                ("lol_bp_side_pick_frame", blue_pick_slot, 1),
                ("lol_bp_side_pick_frame", red_pick_slot, 1),
            )
        ),
        "native_control_styles_preserved": "asset/lol_mod/style/bp_controls" not in layout,
        "turn_outline_draws_above_side_frame": all(
            slot.index("#lol_bp_side_pick_frame:image")
            < slot.index("#turn_outline:color")
            for slot in (blue_pick_slot, red_pick_slot)
        ),
        "wait_overlay_keeps_native_order": (
            layout.index("#champions:scroll_view")
            < layout.index("#champion_pool_wait_overlay:color")
            < layout.index("#champion_info:empty")
        ),
        "timer_decoration_keeps_native_dynamic_bar": (
            layout.index("#timer_bar_bg:color")
            < layout.index("#lol_bp_timer_plate:image")
            < layout.index("#timer_bar:color")
        ),
        "component_imagegen_runtime_dimensions": (
            header_chrome["runtime"]["dimensions"] == list(HEADER_CHROME_SIZE)
            and bottom_chrome["runtime"]["dimensions"] == list(BOTTOM_CHROME_SIZE)
            and champion_frame["runtime"]["dimensions"] == list(CHAMPION_FRAME_SIZE)
            and filter_toolbar["runtime"]["dimensions"] == list(FILTER_TOOLBAR_SIZE)
            and champion_grid_frame["runtime"]["dimensions"] == list(CHAMPION_GRID_SIZE)
            and stat_frame["runtime"]["dimensions"] == list(STAT_FRAME_SIZE)
            and skill_frame["runtime"]["dimensions"] == list(SKILL_FRAME_SIZE)
            and side_pick_frame["runtime"]["dimensions"] == list(SIDE_PICK_FRAME_SIZE)
            and timer_plate["runtime"]["dimensions"] == list(TIMER_PLATE_SIZE)
            and timer_icon["runtime"]["dimensions"] == list(TIMER_ICON_SIZE)
        ),
        "component_imagegen_runtime_has_alpha": all(
            has_transparency(path)
            for path in (
                HEADER_CHROME_RUNTIME,
                BOTTOM_CHROME_RUNTIME,
                CHAMPION_FRAME_RUNTIME,
                FILTER_TOOLBAR_RUNTIME,
                CHAMPION_GRID_RUNTIME,
                STAT_FRAME_RUNTIME,
                SKILL_FRAME_RUNTIME,
                SIDE_PICK_FRAME_RUNTIME,
                TIMER_PLATE_RUNTIME,
                TIMER_ICON_RUNTIME,
            )
        ),
        "header_footer_chrome_has_no_magenta_key_fringe": (
            header_chrome["edge_defringe"]["magenta_dominant_partial_pixels_after"] == 0
            and bottom_chrome["edge_defringe"]["magenta_dominant_partial_pixels_after"] == 0
        ),
        "component_contact_generated": (
            CONTACT_PATH.is_file()
            and image_record(CONTACT_PATH)["dimensions"] == [1200, 800]
        ),
        "bvp_runtime_nodes_absent": not any(marker in layout for marker in forbidden_bvp_ids),
    }
    if not all(static_checks.values()):
        raise ValueError(
            f"BP skin static checks failed: {static_checks}; geometry={geometry_contract}; "
            f"restored_sha={restored_native_layout_hash(layout)}"
        )

    report = {
        "schema": "lol_mod.quality_bp_skin_imagegen_pack.v1",
        "generator": "mods/lol_mod/tools/pack_quality_bp_skin.py",
        "imagegen_mode": "built-in image generation",
        "prompt": IMAGEGEN_PROMPT,
        "source": image_record(SOURCE_PATH),
        "runtime": image_record(RUNTIME_PATH),
        "timer_assets": {
            "prompts": TIMER_IMAGEGEN_PROMPTS,
            "plate": timer_plate,
            "icon": timer_icon,
            "visibility_contract": (
                "ignore-event plate is a child of native #timer_bar_bg:color and remains "
                "behind native dynamic #timer_bar; the icon overlay is nested in the native "
                "timer icon without adding a LeftToRight layout participant"
            ),
        },
        "components": {
            "imagegen_prompts": COMPONENT_IMAGEGEN_PROMPTS,
            "imagegen_assets": {
                "header_chrome": header_chrome,
                "bottom_chrome": bottom_chrome,
                "champion_card_frame": champion_frame,
                "filter_toolbar": filter_toolbar,
                "champion_grid_frame": champion_grid_frame,
                "stat_frame": stat_frame,
                "skill_frame": skill_frame,
                "side_pick_frame": side_pick_frame,
            },
            "control_style": {
                "path": CONTROL_STYLE_PATH.relative_to(MOD_ROOT).as_posix(),
                "sha256": sha256(CONTROL_STYLE_PATH),
                "active_in_layout": False,
                "reason": "base 0.5.1 native control style and interaction contract preserved",
            },
            "champion_slot": {
                "path": CHAMPION_SLOT_PATH.relative_to(MOD_ROOT).as_posix(),
                "sha256": sha256(CHAMPION_SLOT_PATH),
                "native_baseline_normalized_sha256": NATIVE_CHAMPION_SLOT_NORMALIZED_SHA256,
                "restored_native_sha256": restored_native_champion_slot_hash(champion_slot),
                "preview_safe_area": {
                    "layout_root_dimensions": [132.4444, 130],
                    "runtime_frame_dimensions": list(CHAMPION_FRAME_SIZE),
                    "icon_canvas_dimensions": list(CHAMPION_ICON_CANVAS_SIZE),
                    "top_inset_px": CHAMPION_ICON_SAFE_TOP_PX,
                    "name_band_height_px": CHAMPION_NAME_BAND_HEIGHT_PX,
                    "icon_bottom_px": (
                        CHAMPION_ICON_SAFE_TOP_PX + CHAMPION_ICON_CANVAS_SIZE[1]
                    ),
                    "name_band_top_px": (
                        CHAMPION_FRAME_SIZE[1] - CHAMPION_NAME_BAND_HEIGHT_PX
                    ),
                    "icon_stops_before_name_band": (
                        CHAMPION_ICON_SAFE_TOP_PX + CHAMPION_ICON_CANVAS_SIZE[1]
                        <= CHAMPION_FRAME_SIZE[1] - CHAMPION_NAME_BAND_HEIGHT_PX
                    ),
                    "frame_render_order": "before_icon_canvas",
                    "frame_uses_native_sibling_order": True,
                    "frame_has_explicit_z": False,
                    "frame_visible_regression_fix": True,
                    "root_and_click_geometry_unchanged": True,
                    "render_camera_and_actor_contract_unchanged": True,
                    "purpose": (
                        "draw the ornate frame behind the exact base 0.5.1 132.4444x130 "
                        "card hit target without moving its native icon canvas"
                    ),
                },
            },
            "chrome_safe_area": {
                "header": {
                    "layout_dimensions": list(HEADER_CHROME_SIZE),
                    "target_margins_px": list(HEADER_CHROME_TARGET_MARGINS),
                    "runtime_transparent_insets_px": [0, 0, 0, 0],
                    "native_control_bboxes_px": {
                        "delegate": [10, 5, 300, 45],
                        "step": [310, 0, 524, 50],
                        "description": [418, 0, 1502, 50],
                        "swap_phase": [1371, 0, 1877, 50],
                    },
                    "straight_dark_backing_under_side_controls": True,
                    "full_vertical_coverage": [0, 50],
                    "native_header_control_geometry_unchanged": True,
                },
                "bottom": {
                    "layout_dimensions": list(BOTTOM_CHROME_SIZE),
                    "target_margins_px": list(BOTTOM_CHROME_TARGET_MARGINS),
                    "runtime_transparent_insets_px": [0, 0, 0, 0],
                    "native_side_control_columns_px": {
                        "blue": [0, 0, 300, 100],
                        "red": [1620, 0, 1920, 100],
                    },
                    "native_central_control_bboxes_px": {
                        "blue_name": [500, 5, 816, 35],
                        "blue_logo": [888, 40, 940, 92],
                        "red_logo": [980, 40, 1032, 92],
                        "red_name": [1104, 5, 1420, 35],
                        "blue_bans": [515, 40, 801, 94],
                        "red_bans": [1119, 40, 1405, 94],
                        "need_win": [929, 69, 991, 89],
                        "versus": [950, 43, 970, 63],
                        "matchup": [826, 5, 1094, 35],
                    },
                    "bright_side_wings_confined_to_px": {
                        "left": [0, 16],
                        "right": [1904, 1920],
                    },
                    "straight_dark_backing_under_side_controls": True,
                    "full_vertical_coverage": [0, 100],
                    "native_footer_control_geometry_unchanged": True,
                },
                "background_asset_or_layout_rollback": False,
                "purpose": (
                    "keep generated chrome inside the viewport and behind native labels, "
                    "timer, team information, and corner buttons without moving their "
                    "interaction geometry"
                ),
            },
            "side_pick_runtime_geometry": {
                "base_version": "0.5.1",
                "pick_list": {
                    "top_px": 60,
                    "width_px": 300,
                    "height_px": 910,
                    "slot_width_px": 300,
                    "slot_height_px": 174,
                    "slot_spacing_px": 10,
                    "slot_step_y_px": 184,
                    "slot_top_formula": "60 + 184 * slot_index",
                },
                "native_actor": {
                    "blue_local_x_px": 160,
                    "red_local_x_px": 6,
                    "red_global_x_formula": "map_width - 294",
                    "local_y_px": -10,
                    "width_px": 137,
                    "height_px": 184,
                    "icon_height_px": 172,
                    "global_top_formula": "50 + 184 * slot_index",
                },
                "dynamic_splash": {
                    "render_width_px": 284,
                    "render_height_px": 172,
                    "blue_command_x_px": 15,
                    "red_command_x_formula": "map_width - 15",
                    "red_flip_x": True,
                    "command_y_formula": "61 + 184 * slot_index",
                    "replaces_legacy_y_formula": "98 + 188 * slot_index",
                    "rewrite_bp_render_commands_requires_0_5_1_anchor_update": True,
                },
                "derivation": (
                    "native #blue_picks/#red_picks start at y=60; five 300x174 slots use "
                    "TopToBottom spacing=10. Native #done/#champion is y=-10, while the "
                    "284x172 splash stays one pixel inside each 174px card."
                ),
            },
            "blue_pick_slot": {
                "path": BLUE_PICK_SLOT_PATH.relative_to(MOD_ROOT).as_posix(),
                "sha256": sha256(BLUE_PICK_SLOT_PATH),
                "native_baseline_normalized_sha256": NATIVE_BLUE_PICK_SLOT_NORMALIZED_SHA256,
                "restored_native_sha256": restored_native_pick_slot_hash(blue_pick_slot),
            },
            "red_pick_slot": {
                "path": RED_PICK_SLOT_PATH.relative_to(MOD_ROOT).as_posix(),
                "sha256": sha256(RED_PICK_SLOT_PATH),
                "native_baseline_normalized_sha256": NATIVE_RED_PICK_SLOT_NORMALIZED_SHA256,
                "restored_native_sha256": restored_native_pick_slot_hash(red_pick_slot),
            },
            "contact_sheet": image_record(CONTACT_PATH),
        },
        "component_source_contracts": COMPONENT_IMAGEGEN_REQUESTS,
        "imagegen_asset_requests": [],
        "native_bundle": {
            "path": str(bundle_path),
            "base_version": "0.5.1",
            "layouts": native_records,
            "generation_contract": (
                "each active BP override is generated from the current bundle payload; "
                "stripping exact ignore-event decoration blocks restores the normalized "
                "native payload byte-for-byte"
            ),
        },
        "layout": {
            "path": LAYOUT_PATH.relative_to(MOD_ROOT).as_posix(),
            "sha256": sha256(LAYOUT_PATH),
            "native_baseline_sha256": NATIVE_LAYOUT_SHA256,
            "native_baseline_normalized_sha256": NATIVE_LAYOUT_NORMALIZED_SHA256,
            "restored_native_sha256": restored_native_layout_hash(layout),
            "allowed_changes": [
                "ignore_event image decoration nodes only",
                "no native node ids, types, geometry, events, visibility, text, or sources changed",
            ],
        },
        "geometry_contract": geometry_contract,
        "static_checks": static_checks,
    }
    QA_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"BP skin: {RUNTIME_PATH.relative_to(MOD_ROOT)} {background.size}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
