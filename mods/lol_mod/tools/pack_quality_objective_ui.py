from __future__ import annotations

import colorsys
import hashlib
import json
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter


MOD_ROOT = Path(__file__).resolve().parents[1]
INGAME_ROOT = MOD_ROOT / "aseprite_resources" / "ingame"
UI_INGAME_ROOT = MOD_ROOT / "ui" / "ingame"
UI_ICON_ROOT = MOD_ROOT / "ui" / "icons"
QA_PATH = MOD_ROOT / "qa" / "quality_objective_ui_assets.json"

BARON_SHEET = INGAME_ROOT / "epic#sheet.png"
DRAGON_SHEET = INGAME_ROOT / "serpen#sheet.png"

BARON_IDLE_RECT = (218, 0, 436, 218)
DRAGON_IDLE_RECT = (115, 0, 230, 115)

TEAM_BLUE = (91, 115, 255)
TEAM_RED = (239, 100, 113)

NATIVE_CONTRACTS: dict[str, dict[str, Any]] = {
    "asset/base/ui/ingame/epic": {
        "type": "png",
        "dimensions": [90, 90],
        "base_sha256": "f1b674b78dc6f0e44b1484f0c2dc7d16d1bba9dc6fb4cfa92c6cc9e8e122c9be",
    },
    "asset/base/ui/icons/morgard": {
        "type": "svg",
        "view_box": [0, 0, 24, 24],
        "base_sha256": "1d7519f2ee55893b71b4284c98dafcb2c8ae542e1de067242eec5d0a6e16982f",
    },
    "asset/base/ui/icons/morgard_sticker_blue": {
        "type": "svg",
        "view_box": [0, 0, 24, 24],
        "base_sha256": "b0d8929d63453f29ba5f20d7eb90b07853e77f18c0c2a2d306d14e1041e28d7c",
    },
    "asset/base/ui/icons/morgard_sticker_red": {
        "type": "svg",
        "view_box": [0, 0, 24, 24],
        "base_sha256": "6d93dcf495ce6f94ce789d5ca8bf68c52e482bbb231ed61996b82c00aebc1b1e",
    },
    "asset/base/ui/icons/serpen": {
        "type": "svg",
        "view_box": [0, 0, 24, 24],
        "base_sha256": "745dab9e9fa729b5edd49d4f715b1a1bfd481928c052baacd908b0c054806d89",
    },
    "asset/base/ui/icons/serpen_sticker_blue": {
        "type": "svg",
        "view_box": [0, 0, 25, 24],
        "base_sha256": "3f5b4999b861751e1059614139fc9f3a425218f1e40c397ae91df5484ec30022",
    },
    "asset/base/ui/icons/serpen_sticker_red": {
        "type": "svg",
        "view_box": [0, 0, 25, 24],
        "base_sha256": "0e49116fd322d6c8789be1673066055581ff496afe09ecd7475a5b8251358f5b",
    },
    "asset/base/aseprite_resources/ingame/epic_buff_animation#sheet": {
        "type": "png",
        "dimensions": [60, 10],
        "base_sha256": "74f58a3fa2ec38991876622152dc01d2c97fafd444d13fc941beef528f0e2955",
    },
    "asset/base/aseprite_resources/ingame/epic_buff_animation#anim": {
        "type": "fanim",
        "tag": "buff",
        "frame_count": 6,
        "base_sha256": "66691ac0aeb43d31aa1d5e45f51e36a119bbea252108fce62418b5921271cf53",
    },
    "asset/base/aseprite_resources/ingame/epic_monster_hp_guage#sheet": {
        "type": "png",
        "dimensions": [206, 10],
        "base_sha256": "b3055b2c731f49dcaf4c78c0eb8179f40710cdc677330abab07e65a7fa60eae1",
    },
    "asset/base/aseprite_resources/ingame/epic_monster_hp_guage#data": {
        "type": "sprite_sheet",
        "rect_keys": ["bg_0", "hp_bar_0", "slot_line_0"],
        "base_sha256": "64e94a2e99bf69bc5ce22b9c9808413c29092ccde8cea54e3f1778e179fb38e6",
    },
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


def load_runtime_crop(path: Path, rect: tuple[int, int, int, int]) -> Image.Image:
    with Image.open(path) as opened:
        crop = opened.convert("RGBA").crop(rect)
    bbox = crop.getchannel("A").getbbox()
    if bbox is None:
        raise ValueError(f"runtime objective crop is empty: {path}")
    return crop.crop(bbox)


def clear_hidden_rgb(image: Image.Image, alpha_threshold: int = 28) -> Image.Image:
    rgba = image.convert("RGBA")
    output = Image.new("RGBA", rgba.size, (0, 0, 0, 0))
    pixels: list[tuple[int, int, int, int]] = []
    for red, green, blue, alpha in pixel_values(rgba):
        if alpha < alpha_threshold:
            pixels.append((0, 0, 0, 0))
        else:
            pixels.append((red, green, blue, 255))
    output.putdata(pixels)
    return output


def quantize_rgba(image: Image.Image, colors: int = 10) -> Image.Image:
    rgba = clear_hidden_rgb(image)
    alpha = rgba.getchannel("A")
    quantized = rgba.quantize(colors=colors, method=Image.Quantize.FASTOCTREE).convert("RGBA")
    quantized.putalpha(alpha)
    return clear_hidden_rgb(quantized)


def fit_model(
    model: Image.Image,
    canvas_size: tuple[int, int],
    *,
    margin: int,
    colors: int = 10,
    resample: Image.Resampling = Image.Resampling.LANCZOS,
) -> Image.Image:
    max_width = canvas_size[0] - margin * 2
    max_height = canvas_size[1] - margin * 2
    scale = min(max_width / model.width, max_height / model.height)
    fitted = model.resize(
        (max(1, round(model.width * scale)), max(1, round(model.height * scale))),
        resample,
    )
    fitted = quantize_rgba(fitted, colors=colors)
    canvas = Image.new("RGBA", canvas_size, (0, 0, 0, 0))
    x = (canvas.width - fitted.width) // 2
    y = (canvas.height - fitted.height) // 2
    canvas.alpha_composite(fitted, (x, y))
    return canvas


def add_outline(image: Image.Image, color: tuple[int, int, int], radius: int = 1) -> Image.Image:
    if radius != 1:
        raise ValueError("only the one-pixel UI outline is supported")
    alpha = image.getchannel("A")
    expanded = alpha.filter(ImageFilter.MaxFilter(3))
    outline = Image.new("RGBA", image.size, (*color, 0))
    outline.putalpha(expanded)
    outline.alpha_composite(image)
    return clear_hidden_rgb(outline)


def base_icon_thumbnail(
    model: Image.Image,
    size: tuple[int, int],
    outline_color: tuple[int, int, int] = (18, 8, 29),
) -> Image.Image:
    icon = fit_model(model, size, margin=2, colors=10)
    return add_outline(icon, outline_color)


def sticker_thumbnail(
    model: Image.Image,
    size: tuple[int, int],
    team_color: tuple[int, int, int],
) -> Image.Image:
    fitted = fit_model(model, size, margin=2, colors=4)
    alpha = fitted.getchannel("A")
    outline_alpha = alpha.filter(ImageFilter.MaxFilter(3))
    result = Image.new("RGBA", size, (255, 255, 255, 0))
    result.putalpha(outline_alpha)

    luminance = fitted.convert("L")
    body = Image.new("RGBA", size, (*team_color, 0))
    body.putalpha(alpha)
    result.alpha_composite(body)

    visible_luminance = sorted(
        lightness
        for alpha_value, lightness in zip(pixel_values(alpha), pixel_values(luminance))
        if alpha_value
    )
    shadow_cutoff = visible_luminance[len(visible_luminance) * 35 // 100]
    highlight_cutoff = visible_luminance[len(visible_luminance) * 76 // 100]
    shadow_color = tuple(max(8, round(channel * 0.42)) for channel in team_color)
    shadow_mask = Image.new("L", size, 0)
    shadow_mask.putdata(
        [
            255 if alpha_value and lightness <= shadow_cutoff else 0
            for alpha_value, lightness in zip(pixel_values(alpha), pixel_values(luminance))
        ]
    )
    shadow = Image.new("RGBA", size, (*shadow_color, 0))
    shadow.putalpha(shadow_mask)
    result.alpha_composite(shadow)

    highlight_color = tuple(min(255, channel + 58) for channel in team_color)
    highlight_mask = Image.new("L", size, 0)
    highlight_mask.putdata(
        [
            255 if alpha_value and lightness >= highlight_cutoff else 0
            for alpha_value, lightness in zip(pixel_values(alpha), pixel_values(luminance))
        ]
    )
    highlight = Image.new("RGBA", size, (*highlight_color, 0))
    highlight.putalpha(highlight_mask)
    result.alpha_composite(highlight)
    return clear_hidden_rgb(result)


def svg_rect_runs(image: Image.Image) -> list[tuple[int, int, int, tuple[int, int, int]]]:
    rgba = clear_hidden_rgb(image)
    runs: list[tuple[int, int, int, tuple[int, int, int]]] = []
    for y in range(rgba.height):
        x = 0
        while x < rgba.width:
            red, green, blue, alpha = rgba.getpixel((x, y))
            if alpha == 0:
                x += 1
                continue
            color = (red, green, blue)
            end = x + 1
            while end < rgba.width:
                next_pixel = rgba.getpixel((end, y))
                if next_pixel[3] == 0 or next_pixel[:3] != color:
                    break
                end += 1
            runs.append((x, y, end - x, color))
            x = end
    return runs


def write_svg(path: Path, image: Image.Image) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    runs = svg_rect_runs(image)
    lines = [
        (
            f'<svg width="{image.width}" height="{image.height}" '
            f'viewBox="0 0 {image.width} {image.height}" fill="none" '
            'shape-rendering="crispEdges" xmlns="http://www.w3.org/2000/svg">'
        ),
        "<!-- Pixel runs are mechanically derived from the generated objective model. -->",
    ]
    for x, y, width, (red, green, blue) in runs:
        lines.append(
            f'<rect x="{x}" y="{y}" width="{width}" height="1" '
            f'fill="#{red:02X}{green:02X}{blue:02X}"/>'
        )
    lines.append("</svg>")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def build_large_epic_icon(baron: Image.Image) -> Image.Image:
    logical = base_icon_thumbnail(baron, (15, 15), (182, 100, 229))
    return logical.resize((90, 90), Image.Resampling.NEAREST)


def build_buff_sheet(baron: Image.Image) -> tuple[Image.Image, dict[str, Any]]:
    sheet = Image.new("RGBA", (60, 10), (0, 0, 0, 0))
    sizes = (5, 6, 7, 7, 6, 5)
    brightness = (0.62, 0.82, 1.0, 1.18, 0.82, 0.62)
    frames: list[dict[str, Any]] = []
    frame_bboxes: list[list[int]] = []
    for index, (size, light) in enumerate(zip(sizes, brightness)):
        model = fit_model(baron, (size, size), margin=0, colors=5)
        model = ImageEnhance.Brightness(model).enhance(light)
        model = add_outline(clear_hidden_rgb(model), (58, 15, 84))
        frame = Image.new("RGBA", (9, 9), (0, 0, 0, 0))
        frame.alpha_composite(model, ((9 - size) // 2, (9 - size) // 2))
        bbox = frame.getchannel("A").getbbox()
        if bbox is None:
            raise ValueError(f"empty Baron buff frame: {index}")
        frame_bboxes.append(list(bbox))
        sheet.alpha_composite(frame, (index * 10, 0))
        frames.append(
            {
                "duration": 0.1,
                "data": {
                    "x": float(index * 10),
                    "y": 0.0,
                    "w": 9.0,
                    "h": 9.0,
                },
            }
        )
    return sheet, {"anims": {"buff": {"frames": frames}}}, frame_bboxes


def choose_baron_palette(baron: Image.Image) -> dict[str, tuple[int, int, int]]:
    quantized = quantize_rgba(baron.resize((64, 64), Image.Resampling.LANCZOS), colors=24)
    counts = quantized.getcolors(maxcolors=4096) or []
    colors = [
        (count, rgba[:3])
        for count, rgba in counts
        if rgba[3] > 0
    ]
    if len(colors) < 4:
        raise ValueError("Baron source did not provide a usable UI palette")

    def hsv(rgb: tuple[int, int, int]) -> tuple[float, float, float]:
        return colorsys.rgb_to_hsv(*(channel / 255 for channel in rgb))

    purple = [entry for entry in colors if 0.68 <= hsv(entry[1])[0] <= 0.92 and hsv(entry[1])[1] >= 0.35]
    cyan = [entry for entry in colors if 0.45 <= hsv(entry[1])[0] <= 0.62 and hsv(entry[1])[1] >= 0.35]
    if not purple:
        purple = colors
    if not cyan:
        cyan = purple

    dark = min(colors, key=lambda entry: sum(entry[1]))[1]
    mid = max(purple, key=lambda entry: entry[0] * (0.5 + hsv(entry[1])[1]))[1]
    bright = max(purple, key=lambda entry: hsv(entry[1])[2] + hsv(entry[1])[1])[1]
    accent = max(cyan, key=lambda entry: hsv(entry[1])[2] + hsv(entry[1])[1])[1]
    return {"dark": dark, "mid": mid, "bright": bright, "accent": accent}


def build_hp_gauge(
    palette: dict[str, tuple[int, int, int]],
) -> tuple[Image.Image, dict[str, Any]]:
    sheet = Image.new("RGBA", (206, 10), (0, 0, 0, 0))
    draw = ImageDraw.Draw(sheet)
    dark = palette["dark"]
    mid = palette["mid"]
    bright = palette["bright"]
    accent = palette["accent"]

    # bg_0: 76 x 9 at (0, 0)
    draw.rectangle((0, 1, 75, 7), fill=(*mid, 255))
    draw.rectangle((1, 2, 74, 6), fill=(*dark, 255))
    draw.point((0, 0), fill=(*accent, 255))
    draw.point((75, 8), fill=(*bright, 255))

    # hp_bar_0: 66 x 3 at (77, 0)
    draw.rectangle((77, 0, 142, 2), fill=(*mid, 255))
    draw.line((77, 0, 142, 0), fill=(*bright, 255))
    draw.point((77, 1), fill=(*accent, 255))

    # slot_line_0: 61 x 3 at (144, 0)
    draw.line((144, 1, 204, 1), fill=(*mid, 255))
    for x in range(144, 205, 5):
        draw.point((x, 0), fill=(*accent, 255))
        draw.point((x, 2), fill=(*bright, 255))

    data = {
        "images": {
            "hp_bar_0": {"x": 0.37378642, "y": 0.0, "w": 0.32038835, "h": 0.3},
            "slot_line_0": {"x": 0.69902915, "y": 0.0, "w": 0.2961165, "h": 0.3},
            "bg_0": {"x": 0.0, "y": 0.0, "w": 0.36893204, "h": 0.9},
        }
    }
    return sheet, data


def png_record(path: Path) -> dict[str, Any]:
    with Image.open(path) as opened:
        image = opened.convert("RGBA")
    alpha = image.getchannel("A")
    histogram = alpha.histogram()
    return {
        "path": path.relative_to(MOD_ROOT).as_posix(),
        "sha256": sha256_file(path),
        "bytes": path.stat().st_size,
        "dimensions": list(image.size),
        "mode": "RGBA",
        "alpha_bbox": list(alpha.getbbox()) if alpha.getbbox() else None,
        "partial_alpha_pixels": sum(histogram[1:255]),
    }


def text_record(path: Path) -> dict[str, Any]:
    return {
        "path": path.relative_to(MOD_ROOT).as_posix(),
        "sha256": sha256_file(path),
        "bytes": path.stat().st_size,
    }


def main() -> int:
    for source in (BARON_SHEET, DRAGON_SHEET):
        if not source.is_file():
            raise FileNotFoundError(source)

    UI_INGAME_ROOT.mkdir(parents=True, exist_ok=True)
    UI_ICON_ROOT.mkdir(parents=True, exist_ok=True)
    INGAME_ROOT.mkdir(parents=True, exist_ok=True)
    QA_PATH.parent.mkdir(parents=True, exist_ok=True)

    baron = load_runtime_crop(BARON_SHEET, BARON_IDLE_RECT)
    dragon = load_runtime_crop(DRAGON_SHEET, DRAGON_IDLE_RECT)

    epic_icon_path = UI_INGAME_ROOT / "epic.png"
    build_large_epic_icon(baron).save(epic_icon_path, format="PNG", compress_level=9)

    svg_specs = (
        ("morgard.svg", base_icon_thumbnail(baron, (24, 24), (182, 100, 229))),
        ("morgard_sticker_blue.svg", sticker_thumbnail(baron, (24, 24), TEAM_BLUE)),
        ("morgard_sticker_red.svg", sticker_thumbnail(baron, (24, 24), TEAM_RED)),
        ("serpen.svg", base_icon_thumbnail(dragon, (24, 24), (255, 132, 48))),
        ("serpen_sticker_blue.svg", sticker_thumbnail(dragon, (25, 24), TEAM_BLUE)),
        ("serpen_sticker_red.svg", sticker_thumbnail(dragon, (25, 24), TEAM_RED)),
    )
    for filename, image in svg_specs:
        write_svg(UI_ICON_ROOT / filename, image)

    buff_sheet, buff_anim, buff_bboxes = build_buff_sheet(baron)
    buff_sheet_path = INGAME_ROOT / "epic_buff_animation#sheet.png"
    buff_anim_path = INGAME_ROOT / "epic_buff_animation#anim.fanim"
    buff_sheet.save(buff_sheet_path, format="PNG", compress_level=9)
    buff_anim_path.write_text(
        json.dumps(buff_anim, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )

    palette = choose_baron_palette(baron)
    hp_sheet, hp_data = build_hp_gauge(palette)
    hp_sheet_path = INGAME_ROOT / "epic_monster_hp_guage#sheet.png"
    hp_data_path = INGAME_ROOT / "epic_monster_hp_guage#data.sprite_data"
    hp_sheet.save(hp_sheet_path, format="PNG", compress_level=9)
    hp_data_path.write_text(
        json.dumps(hp_data, separators=(",", ":"), ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )

    svg_outputs = {
        filename: text_record(UI_ICON_ROOT / filename)
        for filename, _image in svg_specs
    }
    output_paths = {
        "asset/base/ui/ingame/epic": epic_icon_path,
        "asset/base/ui/icons/morgard": UI_ICON_ROOT / "morgard.svg",
        "asset/base/ui/icons/morgard_sticker_blue": UI_ICON_ROOT / "morgard_sticker_blue.svg",
        "asset/base/ui/icons/morgard_sticker_red": UI_ICON_ROOT / "morgard_sticker_red.svg",
        "asset/base/ui/icons/serpen": UI_ICON_ROOT / "serpen.svg",
        "asset/base/ui/icons/serpen_sticker_blue": UI_ICON_ROOT / "serpen_sticker_blue.svg",
        "asset/base/ui/icons/serpen_sticker_red": UI_ICON_ROOT / "serpen_sticker_red.svg",
        "asset/base/aseprite_resources/ingame/epic_buff_animation#sheet": buff_sheet_path,
        "asset/base/aseprite_resources/ingame/epic_buff_animation#anim": buff_anim_path,
        "asset/base/aseprite_resources/ingame/epic_monster_hp_guage#sheet": hp_sheet_path,
        "asset/base/aseprite_resources/ingame/epic_monster_hp_guage#data": hp_data_path,
    }

    expected_hp_data = {
        "bg_0": {"x": 0.0, "y": 0.0, "w": 0.36893204, "h": 0.9},
        "hp_bar_0": {"x": 0.37378642, "y": 0.0, "w": 0.32038835, "h": 0.3},
        "slot_line_0": {"x": 0.69902915, "y": 0.0, "w": 0.2961165, "h": 0.3},
    }
    parsed_buff = json.loads(buff_anim_path.read_text(encoding="utf-8"))
    parsed_hp = json.loads(hp_data_path.read_text(encoding="utf-8"))
    static_checks = {
        "epic_png_preserves_90x90_contract": png_record(epic_icon_path)["dimensions"] == [90, 90],
        "baron_icons_are_distinct_from_base_payload": all(
            sha256_file(path) != NATIVE_CONTRACTS[key]["base_sha256"]
            for key, path in output_paths.items()
        ),
        "all_six_svg_icons_nonempty": len(svg_outputs) == 6
        and all(record["bytes"] > 300 for record in svg_outputs.values()),
        "team_stickers_are_distinct": sha256_file(UI_ICON_ROOT / "morgard_sticker_blue.svg")
        != sha256_file(UI_ICON_ROOT / "morgard_sticker_red.svg")
        and sha256_file(UI_ICON_ROOT / "serpen_sticker_blue.svg")
        != sha256_file(UI_ICON_ROOT / "serpen_sticker_red.svg"),
        "buff_sheet_preserves_60x10_contract": png_record(buff_sheet_path)["dimensions"] == [60, 10],
        "buff_animation_preserves_tag_and_six_rects": list(parsed_buff.get("anims", {})) == ["buff"]
        and len(parsed_buff["anims"]["buff"]["frames"]) == 6
        and all(frame["duration"] == 0.1 for frame in parsed_buff["anims"]["buff"]["frames"]),
        "buff_frames_nonempty": len(buff_bboxes) == 6,
        "hp_sheet_preserves_206x10_contract": png_record(hp_sheet_path)["dimensions"] == [206, 10],
        "hp_sprite_rect_keys_and_values_preserved": parsed_hp.get("images") == {
            "hp_bar_0": expected_hp_data["hp_bar_0"],
            "slot_line_0": expected_hp_data["slot_line_0"],
            "bg_0": expected_hp_data["bg_0"],
        },
        "png_outputs_use_hard_alpha": all(
            png_record(path)["partial_alpha_pixels"] == 0
            for path in (epic_icon_path, buff_sheet_path, hp_sheet_path)
        ),
    }
    if not all(static_checks.values()):
        failed = [name for name, passed in static_checks.items() if not passed]
        raise ValueError(f"objective UI static checks failed: {failed}")

    qa = {
        "schema": "lol_mod.quality_objective_ui_assets.v1",
        "generator": "mods/lol_mod/tools/pack_quality_objective_ui.py",
        "scope": "Static objective UI derivation only; no game launch and no runtime test execution.",
        "source_route": {
            "baron": {
                "sheet": text_record(BARON_SHEET),
                "idle_rect": list(BARON_IDLE_RECT),
                "derived_outputs": [
                    "ui/ingame/epic.png",
                    "ui/icons/morgard*.svg",
                    "aseprite_resources/ingame/epic_buff_animation#*",
                    "aseprite_resources/ingame/epic_monster_hp_guage#*",
                ],
            },
            "infernal_dragon": {
                "sheet": text_record(DRAGON_SHEET),
                "idle_rect": list(DRAGON_IDLE_RECT),
                "derived_outputs": ["ui/icons/serpen*.svg"],
            },
            "original_game_payload_copied": False,
        },
        "native_contracts": NATIVE_CONTRACTS,
        "derived_palette": {name: list(color) for name, color in palette.items()},
        "outputs": {
            key: {
                **(
                    png_record(path)
                    if path.suffix.lower() == ".png"
                    else text_record(path)
                ),
                "override_target": key,
                "mod_asset_key": f"asset/lol_mod/{path.relative_to(MOD_ROOT).with_suffix('').as_posix()}",
            }
            for key, path in output_paths.items()
        },
        "buff_frame_alpha_bboxes": buff_bboxes,
        "static_checks": static_checks,
        "result": {
            "output_count": len(output_paths),
            "all_static_checks_passed": all(static_checks.values()),
        },
    }
    QA_PATH.write_text(
        json.dumps(qa, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(f"Wrote {QA_PATH.relative_to(MOD_ROOT)}")
    print(f"Objective UI outputs: {len(output_paths)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
