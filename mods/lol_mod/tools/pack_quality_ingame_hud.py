#!/usr/bin/env python3
"""Build a deterministic, visual-only League-style in-game HUD skin.

The native UI payloads are read directly from ``bundle.game_data``.  This
packer only inserts ``ignore_event`` image children and proves that removing
those exact children restores every official payload byte-for-byte after line
ending normalization.  No native node, geometry, source, text, event, or game
logic is edited.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
import re
from statistics import median
import struct
from typing import Any

from PIL import Image, ImageDraw


MOD_ROOT = Path(__file__).resolve().parents[1]
PANEL_SOURCE = MOD_ROOT / "source/imagegen/ui/lol_bp_panel_frame_v1_source.png"
CONTROL_SOURCE = MOD_ROOT / "source/imagegen/ui/lol_bp_control_frame_v1_source.png"
RUNTIME_DIR = MOD_ROOT / "ui/ingame"
LAYOUT_DIR = MOD_ROOT / "ui/layout/ingame_component"
QA_PATH = MOD_ROOT / "qa/quality_ingame_hud_imagegen_pack.json"
CONTACT_PATH = MOD_ROOT / "qa/quality_ingame_hud_contact.png"
OVERRIDE_PATH = MOD_ROOT / "mod.override_info"

CHROMA_TRANSPARENT_DISTANCE = 42.0
CHROMA_OPAQUE_DISTANCE = 118.0
NODE_PATTERN = re.compile(r"(?m)^\s*(#[A-Za-z0-9_-]+):[A-Za-z0-9_-]+\s+\{")


@dataclass(frozen=True)
class RuntimeSpec:
    name: str
    size: tuple[int, int]
    source_kind: str
    tint: tuple[int, int, int]
    tint_strength: float
    opacity: float


@dataclass(frozen=True)
class OverlaySpec:
    asset: str
    container: str
    native_size: tuple[str, str]
    after_node: str | None = None


RUNTIME_SPECS = (
    RuntimeSpec("player_info_blue", (412, 40), "panel", (28, 92, 145), 0.18, 0.78),
    RuntimeSpec("player_info_red", (352, 40), "panel", (132, 42, 55), 0.18, 0.78),
    RuntimeSpec("wide_player_info_blue", (272, 30), "panel", (28, 92, 145), 0.18, 0.76),
    RuntimeSpec("wide_player_info_red", (272, 30), "panel", (132, 42, 55), 0.18, 0.76),
    RuntimeSpec("camera_info_blue", (449, 60), "panel", (28, 92, 145), 0.16, 0.72),
    RuntimeSpec("camera_info_red", (449, 60), "panel", (132, 42, 55), 0.16, 0.72),
    RuntimeSpec("wide_camera_info_blue", (300, 60), "panel", (28, 92, 145), 0.16, 0.72),
    RuntimeSpec("wide_camera_info_red", (300, 60), "panel", (132, 42, 55), 0.16, 0.72),
    RuntimeSpec("player_detail_blue", (393, 40), "panel", (28, 92, 145), 0.17, 0.75),
    RuntimeSpec("player_detail_red", (393, 40), "panel", (132, 42, 55), 0.17, 0.75),
    RuntimeSpec("kill_log", (130, 48), "control", (63, 73, 88), 0.08, 0.68),
    RuntimeSpec("center_kill", (600, 45), "panel", (78, 69, 89), 0.07, 0.68),
    RuntimeSpec("center_notify", (600, 45), "panel", (45, 78, 103), 0.08, 0.66),
    RuntimeSpec("detail_slot", (36, 36), "control", (56, 83, 112), 0.10, 0.62),
    RuntimeSpec("chat_icon", (30, 30), "control", (42, 67, 88), 0.08, 0.62),
)

LAYOUT_SPECS: dict[str, tuple[OverlaySpec, ...]] = {
    "player_info": (
        OverlaySpec("player_info_blue", "#blue_player:empty", ("412", "40")),
        OverlaySpec("player_info_red", "#red_player:empty", ("352", "40")),
    ),
    "wide_player_info": (
        OverlaySpec("wide_player_info_blue", "#blue_player:empty", ("272", "30")),
        OverlaySpec("wide_player_info_red", "#red_player:empty", ("272", "30")),
    ),
    "camera_info": (
        OverlaySpec("camera_info_blue", "#blue_player:color_icon_button", ("449", "60")),
        OverlaySpec("camera_info_red", "#red_player:color_icon_button", ("449", "60")),
    ),
    "wide_camera_info": (
        OverlaySpec("wide_camera_info_blue", "#blue_player:color_icon_button", ("300", "60")),
        OverlaySpec("wide_camera_info_red", "#red_player:color_icon_button", ("300", "60")),
    ),
    "kill_log": (
        OverlaySpec("kill_log", "kill_log:empty", ("130", "48"), "#bg:color"),
    ),
    "center_kill": (
        OverlaySpec("center_kill", "message:empty", ("600", "45")),
    ),
    "center_notify": (
        OverlaySpec("center_notify", "notify:empty", ("600", "45")),
    ),
    "player_detail": (
        OverlaySpec("player_detail_blue", "#blue_player:empty", ("392.5", "40")),
        OverlaySpec("player_detail_red", "#red_player:empty", ("392.5", "40")),
    ),
    "detail_slot": (
        OverlaySpec("detail_slot", "#icon_slot:color", ("36", "36"), "#bg:color"),
    ),
    "chat": (
        # The chat root uses LeftToRight flow.  A root overlay would become a
        # layout participant and shift native content, so only the existing
        # fixed-size icon slot receives a nested decorative frame.
        OverlaySpec("chat_icon", "#icon_slot:color", ("30", "30")),
    ),
}

SKIPPED_CONTRACTS = (
    {
        "asset_key": "asset/base/ui/layout/ingame",
        "reason": "large dynamic battle root; replacing it would risk camera, scoreboard, replay, and minimap logic",
    },
    {
        "asset_key": "asset/base/aseprite_resources/ingame/minimap_5v5#sheet",
        "reason": "atlas contains dynamic semantic markers rather than decorative chrome",
    },
    {
        "asset_key": "asset/base/aseprite_resources/ingame/minimap_5v5#data",
        "reason": "animation/atlas data controls marker semantics and frame addressing",
    },
    {
        "asset_key": "asset/base/ui/ingame/icon_atlases",
        "reason": "small icons carry gameplay meaning and event feedback",
    },
    {
        "asset_key": "runtime/kill_and_notification_logic",
        "reason": "gameplay and timing logic is outside the visual-only contract",
    },
)


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


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical(text: str) -> str:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    return "\n".join(line.rstrip() for line in normalized.splitlines()) + "\n"


def file_record(path: Path) -> dict[str, Any]:
    return {
        "path": path.relative_to(MOD_ROOT).as_posix(),
        "size_bytes": path.stat().st_size,
        "sha256": sha256(path),
    }


def image_record(path: Path) -> dict[str, Any]:
    record = file_record(path)
    with Image.open(path) as image:
        rgba = image.convert("RGBA")
        alpha = rgba.getchannel("A")
        histogram = alpha.histogram()
        record.update(
            {
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
        )
    return record


def read_u32(handle: Any) -> int:
    raw = handle.read(4)
    if len(raw) != 4:
        raise EOFError("Unexpected end of bundle.game_data while reading u32")
    return struct.unpack("<I", raw)[0]


def read_official_layouts(bundle_path: Path) -> dict[str, dict[str, Any]]:
    wanted = {
        f"asset/base/ui/layout/ingame_component/{name}": name
        for name in LAYOUT_SPECS
    }
    result: dict[str, dict[str, Any]] = {}
    with bundle_path.open("rb") as handle:
        for _index in range(read_u32(handle)):
            type_length = read_u32(handle)
            asset_type = handle.read(type_length).decode("utf-8", "strict")
            key_length = read_u32(handle)
            key = handle.read(key_length).decode("utf-8", "strict")
            data_length = read_u32(handle)
            if key not in wanted:
                handle.seek(data_length, 1)
                continue
            payload = handle.read(data_length)
            if len(payload) != data_length:
                raise EOFError(f"Truncated bundle entry: {key}")
            if asset_type != "ui":
                raise ValueError(f"Expected UI payload for {key}, got {asset_type!r}")
            name = wanted[key]
            result[name] = {
                "asset_key": key,
                "asset_type": asset_type,
                "entry_size_bytes": data_length,
                "entry_sha256": sha256_bytes(payload),
                "text": canonical(payload.decode("utf-8-sig", "strict")),
            }
    missing = sorted(set(LAYOUT_SPECS) - set(result))
    if missing:
        raise KeyError(f"Missing official in-game HUD layouts: {missing}")
    return result


def _sample_border_key(image: Image.Image) -> tuple[int, int, int]:
    rgb = image.convert("RGB")
    width, height = rgb.size
    pixels = rgb.load()
    band = max(2, min(width, height) // 100)
    step = max(1, min(width, height) // 256)
    samples: list[tuple[int, int, int]] = []
    for x in range(0, width, step):
        for y in range(band):
            samples.extend((pixels[x, y], pixels[x, height - 1 - y]))
    for y in range(0, height, step):
        for x in range(band):
            samples.extend((pixels[x, y], pixels[width - 1 - x, y]))
    return tuple(int(round(median(sample[c] for sample in samples))) for c in range(3))


def _smoothstep(value: float) -> float:
    value = max(0.0, min(1.0, value))
    return value * value * (3.0 - 2.0 * value)


def remove_magenta_key(image: Image.Image) -> tuple[Image.Image, dict[str, Any]]:
    rgba = image.convert("RGBA")
    key = _sample_border_key(rgba)
    pixels = rgba.load()
    transparent = 0
    partial = 0
    for y in range(rgba.height):
        for x in range(rgba.width):
            red, green, blue, _ = pixels[x, y]
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
            alpha = max(1, min(254, int(round(255 * _smoothstep(ratio)))))
            matte = 1.0 - alpha / 255.0
            foreground = tuple(
                max(0, min(255, int(round((value - matte * key_value) / (alpha / 255.0)))))
                for value, key_value in zip((red, green, blue), key)
            )
            pixels[x, y] = (*foreground, alpha)
            partial += 1
    bbox = rgba.getchannel("A").getbbox()
    if bbox is None:
        raise ValueError("ImageGen HUD source became empty after magenta-key removal")
    return rgba.crop(bbox), {
        "sampled_key": list(key),
        "source_bbox": list(bbox),
        "transparent_pixels": transparent,
        "partial_alpha_pixels": partial,
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
        raise ValueError(f"Invalid nine-slice margins for {size}")
    sx = (0, sl, sw - sr, sw)
    sy = (0, st, sh - sb, sh)
    tx = (0, tl, tw - tr, tw)
    ty = (0, tt, th - tb, th)
    output = Image.new("RGBA", size, (0, 0, 0, 0))
    for row in range(3):
        for column in range(3):
            piece = source.crop((sx[column], sy[row], sx[column + 1], sy[row + 1]))
            target_size = (tx[column + 1] - tx[column], ty[row + 1] - ty[row])
            output.alpha_composite(
                piece.resize(target_size, Image.Resampling.LANCZOS),
                (tx[column], ty[row]),
            )
    return output


def tint_and_fade(
    image: Image.Image,
    tint: tuple[int, int, int],
    tint_strength: float,
    opacity: float,
) -> Image.Image:
    rgba = image.convert("RGBA")
    alpha = rgba.getchannel("A")
    tinted_rgb = Image.blend(
        rgba.convert("RGB"), Image.new("RGB", rgba.size, tint), tint_strength
    )
    result = tinted_rgb.convert("RGBA")
    result.putalpha(alpha.point(lambda value: int(round(value * opacity))))
    return result


def build_runtime_assets() -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    for path in (PANEL_SOURCE, CONTROL_SOURCE):
        if not path.is_file():
            raise FileNotFoundError(f"Missing existing ImageGen HUD source: {path}")
    keyed: dict[str, Image.Image] = {}
    key_records: dict[str, dict[str, Any]] = {}
    for kind, path in (("panel", PANEL_SOURCE), ("control", CONTROL_SOURCE)):
        with Image.open(path) as opened:
            keyed[kind], key_records[kind] = remove_magenta_key(opened)

    runtime: dict[str, dict[str, Any]] = {}
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    stale_chat_bar = RUNTIME_DIR / "lol_hud_chat.png"
    if stale_chat_bar.exists():
        stale_chat_bar.unlink()
    for spec in RUNTIME_SPECS:
        source = keyed[spec.source_kind]
        source_ratio = (0.08, 0.18) if spec.source_kind == "panel" else (0.09, 0.28)
        source_x = max(1, int(round(source.width * source_ratio[0])))
        source_y = max(1, int(round(source.height * source_ratio[1])))
        target_x = max(2, min(12, spec.size[0] // 5))
        target_y = max(2, min(8, spec.size[1] // 4))
        packed = nine_slice_resize(
            source,
            spec.size,
            (source_x, source_y, source_x, source_y),
            (target_x, target_y, target_x, target_y),
        )
        packed = tint_and_fade(packed, spec.tint, spec.tint_strength, spec.opacity)
        path = RUNTIME_DIR / f"lol_hud_{spec.name}.png"
        packed.save(path, optimize=True)
        runtime[spec.name] = {
            "source_id": spec.source_kind,
            "packing_method": "alpha_bbox_nine_slice_tint",
            "tint_rgb": list(spec.tint),
            "tint_strength": spec.tint_strength,
            "opacity": spec.opacity,
            "runtime": image_record(path),
        }
    return runtime, key_records


def find_node(text: str, token: str, start: int = 0, end: int | None = None) -> tuple[int, int, int]:
    marker = f"{token} {{"
    marker_index = text.find(marker, start, len(text) if end is None else end)
    if marker_index < 0:
        raise ValueError(f"Missing native UI node: {token}")
    open_index = marker_index + len(marker) - 1
    depth = 0
    for index in range(open_index, len(text) if end is None else end):
        if text[index] == "{":
            depth += 1
        elif text[index] == "}":
            depth -= 1
            if depth == 0:
                return marker_index, open_index, index + 1
    raise ValueError(f"Unclosed native UI node: {token}")


def first_child_position(text: str, container: str) -> tuple[int, str]:
    marker, open_index, close_index = find_node(text, container)
    line_start = text.rfind("\n", 0, marker) + 1
    parent_indent = text[line_start:marker]
    cursor = open_index + 1
    depth = 1
    while cursor < close_index:
        line_end = text.find("\n", cursor, close_index)
        if line_end < 0:
            line_end = close_index
        line = text[cursor:line_end]
        if depth == 1 and re.match(r"^\s*#[A-Za-z0-9_-]+:[A-Za-z0-9_-]+\s+\{\s*$", line):
            return cursor, parent_indent + "  "
        depth += line.count("{") - line.count("}")
        cursor = line_end + 1
    raise ValueError(f"Container has no native child insertion boundary: {container}")


def render_overlay(indent: str, asset: str) -> str:
    node = f"lol_hud_{asset}"
    source = f"asset/lol_mod/ui/ingame/lol_hud_{asset}"
    return (
        f"{indent}#{node}:image {{\n"
        f"{indent}  ignore_event: true;\n"
        f"{indent}  width: 100%;\n"
        f"{indent}  height: 100%;\n"
        f"{indent}  source: \"{source}\";\n"
        f"{indent}}}"
    )


def insert_overlay(text: str, spec: OverlaySpec) -> tuple[str, str]:
    marker, _open_index, close_index = find_node(text, spec.container)
    line_start = text.rfind("\n", 0, marker) + 1
    parent_indent = text[line_start:marker]
    container_text = text[marker:close_index]
    width, height = spec.native_size
    if f"width: {width}px;" not in container_text or f"height: {height}px;" not in container_text:
        raise ValueError(
            f"Native geometry changed for {spec.container}; expected {width}x{height}"
        )
    if spec.after_node is None:
        position, indent = first_child_position(text, spec.container)
        chunk = render_overlay(indent, spec.asset) + "\n\n"
    else:
        _after_marker, _after_open, position = find_node(
            text, spec.after_node, marker, close_index
        )
        chunk = "\n\n" + render_overlay(parent_indent + "  ", spec.asset)
    return text[:position] + chunk + text[position:], chunk


def build_layouts(
    official: dict[str, dict[str, Any]]
) -> tuple[dict[str, dict[str, Any]], dict[str, str]]:
    records: dict[str, dict[str, Any]] = {}
    generated_texts: dict[str, str] = {}
    LAYOUT_DIR.mkdir(parents=True, exist_ok=True)
    for name, overlays in LAYOUT_SPECS.items():
        native = official[name]["text"]
        generated = native
        chunks: list[str] = []
        for overlay in overlays:
            generated, chunk = insert_overlay(generated, overlay)
            chunks.append(chunk)
        restored = generated
        for chunk in reversed(chunks):
            restored = restored.replace(chunk, "", 1)
        native_hash = sha256_bytes(native.encode("utf-8"))
        restored_hash = sha256_bytes(canonical(restored).encode("utf-8"))
        if restored_hash != native_hash:
            raise ValueError(f"{name}: exact overlay removal did not restore official UI")
        native_nodes = Counter(NODE_PATTERN.findall(native))
        generated_nodes = Counter(NODE_PATTERN.findall(generated))
        native_ids_preserved = all(
            generated_nodes[node] == count for node, count in native_nodes.items()
        )
        if not native_ids_preserved:
            raise ValueError(f"{name}: a native node ID was changed or duplicated")
        path = LAYOUT_DIR / f"{name}.ui"
        path.write_text(generated, encoding="utf-8", newline="\n")
        records[name] = {
            "asset_key": official[name]["asset_key"],
            "official_bundle": {
                "file": "bundle.game_data",
                "asset_type": official[name]["asset_type"],
                "entry_size_bytes": official[name]["entry_size_bytes"],
                "entry_sha256": official[name]["entry_sha256"],
            },
            "path": path.relative_to(MOD_ROOT).as_posix(),
            "size_bytes": path.stat().st_size,
            "sha256": sha256(path),
            "native_baseline_normalized_sha256": native_hash,
            "restored_native_sha256": restored_hash,
            "native_node_count": sum(native_nodes.values()),
            "native_node_ids_preserved": native_ids_preserved,
            "overlay_nodes": [f"lol_hud_{overlay.asset}" for overlay in overlays],
            "allowed_changes": ["ignore_event decorative image child insertion"],
        }
        generated_texts[name] = generated
    return records, generated_texts


def build_contact() -> None:
    canvas = Image.new("RGBA", (1200, 700), (4, 10, 18, 255))
    draw = ImageDraw.Draw(canvas)
    draw.text((24, 16), "League-style in-game HUD / visual-only component preview", fill=(225, 210, 170, 255))

    def composite(name: str, xy: tuple[int, int]) -> None:
        with Image.open(RUNTIME_DIR / f"lol_hud_{name}.png") as opened:
            canvas.alpha_composite(opened.convert("RGBA"), xy)

    draw.text((24, 56), "player_info", fill=(160, 190, 210, 255))
    composite("player_info_blue", (24, 78))
    composite("player_info_red", (824, 78))
    draw.text((24, 140), "camera_info", fill=(160, 190, 210, 255))
    composite("camera_info_blue", (24, 162))
    composite("camera_info_red", (727, 162))
    draw.text((24, 246), "wide_player_info / player_detail", fill=(160, 190, 210, 255))
    composite("wide_player_info_blue", (24, 268))
    composite("wide_player_info_red", (904, 268))
    composite("player_detail_blue", (24, 320))
    composite("player_detail_red", (783, 320))
    draw.text((24, 386), "center notices", fill=(160, 190, 210, 255))
    composite("center_kill", (300, 408))
    composite("center_notify", (300, 468))
    draw.text((24, 542), "kill log / chat icon / detail slots", fill=(160, 190, 210, 255))
    composite("kill_log", (24, 566))
    composite("chat_icon", (220, 575))
    draw.rounded_rectangle((258, 575, 705, 605), radius=6, fill=(18, 24, 34, 220))
    draw.text((270, 583), "native chat text flow remains untouched", fill=(145, 165, 180, 255))
    for x in range(760, 1000, 48):
        composite("detail_slot", (x, 570))
    draw.text(
        (24, 648),
        "Native dimensions, positions, text, icons, events and logic are restored exactly after removing overlays.",
        fill=(125, 150, 170, 255),
    )
    CONTACT_PATH.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(CONTACT_PATH, optimize=True)


def main() -> int:
    bundle_path = find_bundle_path()
    official = read_official_layouts(bundle_path)
    runtime, key_records = build_runtime_assets()
    layouts, generated_texts = build_layouts(official)
    build_contact()
    override = json.loads(OVERRIDE_PATH.read_text(encoding="utf-8"))

    expected_overrides = {
        f"asset/base/ui/layout/ingame_component/{name}": {
            "remapping": f"asset/lol_mod/ui/layout/ingame_component/{name}",
            "type": "override",
        }
        for name in LAYOUT_SPECS
    }
    runtime_dimensions = {
        spec.name: list(spec.size) for spec in RUNTIME_SPECS
    }
    static_checks = {
        "all_safe_component_overrides_registered": all(
            override.get(key) == value for key, value in expected_overrides.items()
        ),
        "all_official_layouts_restore_exactly": all(
            record["restored_native_sha256"]
            == record["native_baseline_normalized_sha256"]
            for record in layouts.values()
        ),
        "all_native_node_ids_preserved": all(
            record["native_node_ids_preserved"] for record in layouts.values()
        ),
        "all_overlays_ignore_events": all(
            all(
                "ignore_event: true;"
                in text.split(f"#{node}:image", 1)[1].split("}", 1)[0]
                for node in record["overlay_nodes"]
            )
            for name, (record, text) in (
                (name, (layouts[name], generated_texts[name])) for name in layouts
            )
        ),
        "all_layout_sources_are_packed_runtime_assets": all(
            "source/imagegen/" not in text
            and all(
                f'source: "asset/lol_mod/ui/ingame/{node}";' in text
                for node in record["overlay_nodes"]
            )
            for name, (record, text) in (
                (name, (layouts[name], generated_texts[name])) for name in layouts
            )
        ),
        "runtime_dimensions_match_native_containers": all(
            runtime[name]["runtime"]["dimensions"] == dimensions
            for name, dimensions in runtime_dimensions.items()
        ),
        "runtime_assets_are_translucent": all(
            record["runtime"]["alpha"]["max"] < 255
            and record["runtime"]["alpha"]["partial_pixels"] > 0
            for record in runtime.values()
        ),
        "dynamic_ingame_root_not_overridden": "asset/base/ui/layout/ingame" not in override,
        "dynamic_minimap_contract_not_overridden": all(
            item["asset_key"] not in override for item in SKIPPED_CONTRACTS[1:3]
        ),
        "qa_contact_generated": CONTACT_PATH.is_file(),
    }
    if not all(static_checks.values()):
        raise ValueError(f"In-game HUD visual-only checks failed: {static_checks}")

    report = {
        "schema": "lol_mod.quality_ingame_hud_imagegen_pack.v1",
        "generator": "mods/lol_mod/tools/pack_quality_ingame_hud.py",
        "imagegen_mode": "reuse of existing built-in image generation sources",
        "contracts": {
            "scope": "decorative visual-only overlays in audited ingame_component layouts",
            "official_payload_source": "bundle.game_data",
            "native_contract_preserved": [
                "node IDs and counts",
                "widths, heights, anchors, pivots, and positions",
                "events, hover/active definitions, visibility, text, and icon sources",
                "gameplay, camera, scoreboard, kill, notification, and minimap logic",
            ],
            "runtime_source_rule": "UI layouts reference asset/lol_mod runtime PNGs only; source/imagegen is never referenced by runtime UI",
        },
        "imagegen_sources": {
            "panel": {**image_record(PANEL_SOURCE), "chroma_key": key_records["panel"]},
            "control": {**image_record(CONTROL_SOURCE), "chroma_key": key_records["control"]},
        },
        "runtime_assets": runtime,
        "layouts": layouts,
        "overrides": expected_overrides,
        "skipped_contracts": list(SKIPPED_CONTRACTS),
        "contact_sheet": image_record(CONTACT_PATH),
        "static_checks": static_checks,
    }
    QA_PATH.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        f"In-game HUD: {len(layouts)} native layouts, {len(runtime)} runtime assets, visual-only"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
