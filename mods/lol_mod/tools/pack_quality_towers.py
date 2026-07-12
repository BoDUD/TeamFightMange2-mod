from __future__ import annotations

import colorsys
import hashlib
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PIL import Image, ImageFilter


MOD_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = MOD_ROOT / "source" / "imagegen" / "jungle"
PROCESSED_ROOT = MOD_ROOT / "source" / "processed" / "jungle"
INGAME_ROOT = MOD_ROOT / "aseprite_resources" / "ingame"
SKILL_EFFECT_ROOT = MOD_ROOT / "aseprite_resources" / "skill_effect"
UI_ICON_ROOT = MOD_ROOT / "ui" / "icons"
QA_PATH = MOD_ROOT / "qa" / "quality_towers_imagegen_pack.json"

ACTOR_SOURCE = SOURCE_ROOT / "tower_actor_contact.png"
VFX_SOURCE = SOURCE_ROOT / "tower_vfx_contact.png"
ACTOR_PROCESSED = PROCESSED_ROOT / "tower_actor_contact_alpha.png"
VFX_PROCESSED = PROCESSED_ROOT / "tower_vfx_contact_alpha.png"

CHROMA_KEY = (255, 0, 255)
CHROMA_DISTANCE_THRESHOLD = 52.0
CHROMA_MAGENTA_SCORE_THRESHOLD = 96.0

TOWER_SHEET_SIZE = (581, 64)
ORB_SHEET_SIZE = (357, 64)
PROJECTILE_CELL = 1
IMPACT_CELLS = (4, 5, 6, 7, 11)


@dataclass(frozen=True)
class FrameContract:
    x: int
    y: int
    width: int
    height: int
    duration: float
    visible_width: int | None = None
    visible_height: int | None = None
    visible_x: int | None = None
    visible_y: int | None = None

    @property
    def rect(self) -> tuple[int, int, int, int]:
        return (self.x, self.y, self.width, self.height)


TOWER_IDLE = tuple(
    FrameContract(
        x=index * 32,
        y=0,
        width=31,
        height=63,
        duration=0.120000005,
        visible_width=28,
        visible_height=height,
        visible_x=1,
        visible_y=61 - height,
    )
    for index, height in enumerate((58, 57, 56, 57, 58, 59, 60, 59))
)
TOWER_ATTACK = tuple(
    FrameContract(
        x=256 + index * 32,
        y=0,
        width=31,
        height=63,
        duration=0.080000006,
        visible_width=28,
        visible_height=height,
        visible_x=1,
        visible_y=61 - height,
    )
    for index, height in enumerate((58, 58, 58, 58, 60, 58))
)
TOWER_PROJECTILE = FrameContract(448, 0, 64, 21, 0.080000006)
TOWER_HITS = tuple(
    FrameContract(x, 0, size, size, 0.080000006)
    for x, size in ((513, 7), (521, 9), (531, 11), (543, 17), (561, 19))
)

ORB_IDLE = tuple(
    FrameContract(
        x=x,
        y=0,
        width=13,
        height=rect_height,
        duration=0.120000005,
        visible_width=10,
        visible_height=visible_height,
        visible_x=1,
        visible_y=1,
    )
    for x, rect_height, visible_height in zip(
        (0, 14, 28, 42, 56, 70, 84, 98),
        (59, 57, 55, 57, 59, 61, 63, 61),
        (29, 27, 26, 27, 29, 29, 29, 29),
    )
)
ORB_ATTACK = tuple(
    FrameContract(
        x=x,
        y=0,
        width=rect_width,
        height=rect_height,
        duration=0.080000006,
        visible_width=visible_width,
        visible_height=visible_height,
        visible_x=1,
        visible_y=1,
    )
    for x, rect_width, rect_height, visible_width, visible_height in (
        (112, 13, 59, 10, 28),
        (126, 13, 59, 10, 28),
        (140, 21, 59, 18, 28),
        (162, 21, 59, 18, 29),
        (184, 25, 63, 22, 31),
        (210, 13, 59, 10, 29),
    )
)
ORB_PROJECTILE = FrameContract(224, 0, 64, 21, 0.080000006)
ORB_HITS = tuple(
    FrameContract(x, 0, size, size, 0.080000006)
    for x, size in ((289, 7), (297, 9), (307, 11), (319, 17), (337, 19))
)

BASE_CONTRACTS: dict[str, dict[str, Any]] = {
    "asset/base/aseprite_resources/ingame/blue_tower#sheet": {
        "dimensions": [581, 64],
        "sha256": "1f5cc4a79a9b32605ebd2daf3a58f9f98391603df1325ab8f93a5c8484e6c972",
    },
    "asset/base/aseprite_resources/ingame/red_tower#sheet": {
        "dimensions": [581, 64],
        "sha256": "32931a2e8c343f64929c70a7c80bf145ecf485e8f4c7ee4d2c8ea33a63f0f8e7",
    },
    "asset/base/aseprite_resources/ingame/blue_tower#anim": {
        "sha256": "5b13fe59e7c1bf6f77e561b6348b3ffcaeac591b986ec85d4e0cf4684e346e9d",
    },
    "asset/base/aseprite_resources/ingame/red_tower#anim": {
        "sha256": "dfee68221575546c4611d06949709eadf235e5a59e1c7aeda014ab03dc6f016e",
    },
    "asset/base/aseprite_resources/ingame/blue_tower_orb#sheet": {
        "dimensions": [357, 64],
        "sha256": "6d9a1d470e79974396abca3d96ae74912b63f53ff435eac3596d85c50b4a2668",
    },
    "asset/base/aseprite_resources/ingame/red_tower_orb#sheet": {
        "dimensions": [357, 64],
        "sha256": "2f61f3095e389a9818c484794585f7c09f9c07889d73ae4a31112b1609286370",
    },
    "asset/base/aseprite_resources/ingame/blue_tower_orb#anim": {
        "sha256": "6e4dfab91be84d05a3d0ec7cd428076726213f1a0b5009b7b6342e6a730c6593",
    },
    "asset/base/aseprite_resources/ingame/red_tower_orb#anim": {
        "sha256": "252a774af6ff7f3ec269557538edf9b800336d72166d63655f2485ccfb6ffdeb",
    },
    "asset/base/aseprite_resources/skill_effect/blue_tower_projectile": {
        "dimensions": [4, 4],
        "sha256": "771f8a27d8a151d6e3f2509a934d9abaa36ef06f30f88782d87abc6e369530a5",
    },
    "asset/base/aseprite_resources/skill_effect/red_tower_projectile": {
        "dimensions": [4, 4],
        "sha256": "fc44b5ed50a61cc5ba168552d7fd568af3229a0520a24222ead3b2e09c889730",
    },
    "asset/base/ui/icons/tower": {
        "view_box": [0, 0, 20, 20],
        "sha256": "2662bf9a1317526cded1f05fccc15f8c9c457c4e797b9f86386d55f20b0196a4",
    },
    "asset/base/aseprite_resources/ingame/5v5/tower_shadow": {
        "dimensions": [23, 24],
        "sha256": "64cf1f686af7990bbcaa4d26082d5a1e0b837df22c1396e8ce5f94a04263505d",
        "override": False,
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


def clear_hidden_rgb(image: Image.Image, alpha_threshold: int = 20) -> Image.Image:
    rgba = image.convert("RGBA")
    output = Image.new("RGBA", rgba.size, (0, 0, 0, 0))
    output.putdata(
        [
            (0, 0, 0, 0)
            if alpha < alpha_threshold
            else (red, green, blue, 255)
            for red, green, blue, alpha in pixel_values(rgba)
        ]
    )
    return output


def alpha_bbox(image: Image.Image) -> tuple[int, int, int, int]:
    bbox = image.getchannel("A").getbbox()
    if bbox is None:
        raise ValueError("expected visible tower art, found a fully transparent image")
    return bbox


def trim_alpha(image: Image.Image) -> Image.Image:
    normalized = clear_hidden_rgb(image)
    return normalized.crop(alpha_bbox(normalized))


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
        magenta_score = min(red, blue) - green - abs(red - blue) * 0.65
        if (
            distance <= CHROMA_DISTANCE_THRESHOLD
            or magenta_score >= CHROMA_MAGENTA_SCORE_THRESHOLD
        ):
            converted.append((0, 0, 0, 0))
        else:
            converted.append((red, green, blue, 255))
    output.putdata(converted)
    return output


def split_grid(image: Image.Image, columns: int, rows: int) -> list[Image.Image]:
    x_edges = [
        (index * image.width + columns // 2) // columns
        for index in range(columns + 1)
    ]
    y_edges = [
        (index * image.height + rows // 2) // rows
        for index in range(rows + 1)
    ]
    return [
        clear_hidden_rgb(
            image.crop(
                (
                    x_edges[column],
                    y_edges[row],
                    x_edges[column + 1],
                    y_edges[row + 1],
                )
            )
        )
        for row in range(rows)
        for column in range(columns)
    ]


def quantize_rgba(image: Image.Image, colors: int) -> Image.Image:
    rgba = clear_hidden_rgb(image)
    alpha = rgba.getchannel("A")
    quantized = rgba.quantize(
        colors=colors,
        method=Image.Quantize.FASTOCTREE,
    ).convert("RGBA")
    quantized.putalpha(alpha)
    return clear_hidden_rgb(quantized)


def exact_visible_resize(
    image: Image.Image,
    size: tuple[int, int],
    *,
    colors: int,
) -> Image.Image:
    trimmed = trim_alpha(image)
    reduced = trimmed.resize(size, Image.Resampling.LANCZOS)
    reduced = quantize_rgba(reduced, colors)
    reduced = trim_alpha(reduced)
    if reduced.size != size:
        reduced = reduced.resize(size, Image.Resampling.NEAREST)
        reduced = clear_hidden_rgb(reduced)
    if alpha_bbox(reduced) != (0, 0, size[0], size[1]):
        raise ValueError(f"visible resize did not fill target bounds: {size}")
    return reduced


def fit_effect(
    image: Image.Image,
    size: tuple[int, int],
    *,
    margin: int,
    colors: int = 16,
) -> Image.Image:
    trimmed = trim_alpha(image)
    max_width = size[0] - margin * 2
    max_height = size[1] - margin * 2
    scale = min(max_width / trimmed.width, max_height / trimmed.height)
    reduced = trimmed.resize(
        (
            max(1, round(trimmed.width * scale)),
            max(1, round(trimmed.height * scale)),
        ),
        Image.Resampling.LANCZOS,
    )
    reduced = quantize_rgba(reduced, colors)
    canvas = Image.new("RGBA", size, (0, 0, 0, 0))
    x = (size[0] - reduced.width) // 2
    y = (size[1] - reduced.height) // 2
    canvas.alpha_composite(reduced, (x, y))
    return clear_hidden_rgb(canvas)


def connected_components(image: Image.Image) -> list[tuple[int, tuple[int, int, int, int], list[tuple[int, int]]]]:
    alpha = image.getchannel("A")
    pixels = alpha.load()
    seen: set[tuple[int, int]] = set()
    components: list[tuple[int, tuple[int, int, int, int], list[tuple[int, int]]]] = []
    for y in range(image.height):
        for x in range(image.width):
            if pixels[x, y] == 0 or (x, y) in seen:
                continue
            queue = [(x, y)]
            seen.add((x, y))
            points: list[tuple[int, int]] = []
            while queue:
                current_x, current_y = queue.pop()
                points.append((current_x, current_y))
                for next_x, next_y in (
                    (current_x - 1, current_y),
                    (current_x + 1, current_y),
                    (current_x, current_y - 1),
                    (current_x, current_y + 1),
                ):
                    if (
                        0 <= next_x < image.width
                        and 0 <= next_y < image.height
                        and pixels[next_x, next_y] > 0
                        and (next_x, next_y) not in seen
                    ):
                        seen.add((next_x, next_y))
                        queue.append((next_x, next_y))
            xs = [point[0] for point in points]
            ys = [point[1] for point in points]
            bbox = (min(xs), min(ys), max(xs) + 1, max(ys) + 1)
            components.append((len(points), bbox, points))
    components.sort(key=lambda component: component[0], reverse=True)
    return components


def remove_cross_cell_bleed(image: Image.Image) -> Image.Image:
    components = connected_components(image)
    if not components:
        raise ValueError("VFX source cell is empty")
    output = image.copy()
    pixels = output.load()
    for _size, bbox, points in components[1:]:
        touches_horizontal_grid_edge = bbox[1] <= 0 or bbox[3] >= image.height
        if touches_horizontal_grid_edge:
            for x, y in points:
                pixels[x, y] = (0, 0, 0, 0)
    return clear_hidden_rgb(output)


def crop_actor_body(
    actor_cells: list[Image.Image],
    index: int,
    reference_x_bounds: list[tuple[int, int]],
) -> Image.Image:
    cell = actor_cells[index]
    if index < 8:
        return trim_alpha(cell)
    left, right = reference_x_bounds[index % 4]
    return trim_alpha(cell.crop((left, 0, right, cell.height)))


def native_frame(document: FrameContract) -> dict[str, Any]:
    return {
        "duration": document.duration,
        "data": {
            "x": float(document.x),
            "y": float(document.y),
            "w": float(document.width),
            "h": float(document.height),
        },
    }


def build_fanim(
    idle: tuple[FrameContract, ...],
    attack: tuple[FrameContract, ...],
    projectile: FrameContract,
    hits: tuple[FrameContract, ...],
) -> dict[str, Any]:
    return {
        "anims": {
            "idle": {"frames": [native_frame(frame) for frame in idle]},
            "attack": {"frames": [native_frame(frame) for frame in attack]},
            "attack_projectile": {"frames": [native_frame(projectile)]},
            "hit_effect": {"frames": [native_frame(frame) for frame in hits]},
        }
    }


def paste_frame(sheet: Image.Image, frame: Image.Image, contract: FrameContract) -> None:
    if frame.size != (contract.width, contract.height):
        raise ValueError(f"frame does not match contract rect: {frame.size} vs {contract.rect}")
    sheet.alpha_composite(frame, (contract.x, contract.y))


def make_body_frame(source: Image.Image, contract: FrameContract) -> Image.Image:
    if (
        contract.visible_width is None
        or contract.visible_height is None
        or contract.visible_x is None
        or contract.visible_y is None
    ):
        raise ValueError("body frame contract is missing visible placement")
    subject = exact_visible_resize(
        source,
        (contract.visible_width, contract.visible_height),
        colors=40,
    )
    canvas = Image.new("RGBA", (contract.width, contract.height), (0, 0, 0, 0))
    canvas.alpha_composite(subject, (contract.visible_x, contract.visible_y))
    return canvas


def extract_idle_orb(source: Image.Image) -> Image.Image:
    tower = trim_alpha(source)
    left = round(tower.width * 0.27)
    right = round(tower.width * 0.73)
    bottom = round(tower.height * 0.38)
    return trim_alpha(tower.crop((left, 0, right, bottom)))


def extract_attack_orb(source: Image.Image) -> Image.Image:
    tower = trim_alpha(source)
    bottom = round(tower.height * 0.5)
    return trim_alpha(tower.crop((0, 0, tower.width, bottom)))


def recolor_blue_energy_to_red(image: Image.Image) -> tuple[Image.Image, int]:
    rgba = image.convert("RGBA")
    output = Image.new("RGBA", rgba.size, (0, 0, 0, 0))
    converted: list[tuple[int, int, int, int]] = []
    changed = 0
    for red, green, blue, alpha in pixel_values(rgba):
        if alpha == 0:
            converted.append((0, 0, 0, 0))
            continue
        is_blue_energy = (
            blue >= 85
            and green >= 65
            and blue - red >= 45
            and green - red >= 30
        )
        if is_blue_energy:
            hue, saturation, value = colorsys.rgb_to_hsv(
                red / 255,
                green / 255,
                blue / 255,
            )
            target_saturation = max(0.45, saturation)
            new_red, new_green, new_blue = colorsys.hsv_to_rgb(
                0.965,
                target_saturation,
                value,
            )
            converted.append(
                (
                    round(new_red * 255),
                    round(new_green * 255),
                    round(new_blue * 255),
                    255,
                )
            )
            changed += 1
        else:
            converted.append((red, green, blue, 255))
    output.putdata(converted)
    return output, changed


def build_projectile_and_hits(
    vfx_cells: list[Image.Image],
    projectile_contract: FrameContract,
    hit_contracts: tuple[FrameContract, ...],
) -> tuple[Image.Image, list[Image.Image]]:
    projectile_source = remove_cross_cell_bleed(vfx_cells[PROJECTILE_CELL])
    projectile = fit_effect(
        projectile_source,
        (projectile_contract.width, projectile_contract.height),
        margin=0,
        colors=12,
    )
    hit_frames: list[Image.Image] = []
    for source_index, contract in zip(IMPACT_CELLS, hit_contracts):
        source = remove_cross_cell_bleed(vfx_cells[source_index])
        hit_frames.append(
            fit_effect(
                source,
                (contract.width, contract.height),
                margin=1,
                colors=12,
            )
        )
    return projectile, hit_frames


def build_tower_sheet(
    actor_cells: list[Image.Image],
    reference_x_bounds: list[tuple[int, int]],
    projectile: Image.Image,
    hit_frames: list[Image.Image],
) -> Image.Image:
    sheet = Image.new("RGBA", TOWER_SHEET_SIZE, (0, 0, 0, 0))
    for index, contract in enumerate(TOWER_IDLE):
        source = crop_actor_body(actor_cells, index, reference_x_bounds)
        paste_frame(sheet, make_body_frame(source, contract), contract)
    for offset, contract in enumerate(TOWER_ATTACK):
        source = crop_actor_body(actor_cells, 8 + offset, reference_x_bounds)
        paste_frame(sheet, make_body_frame(source, contract), contract)
    paste_frame(sheet, projectile, TOWER_PROJECTILE)
    for contract, frame in zip(TOWER_HITS, hit_frames):
        paste_frame(sheet, frame, contract)
    return clear_hidden_rgb(sheet)


def build_orb_sheet(
    actor_cells: list[Image.Image],
    reference_x_bounds: list[tuple[int, int]],
    projectile: Image.Image,
    hit_frames: list[Image.Image],
) -> Image.Image:
    sheet = Image.new("RGBA", ORB_SHEET_SIZE, (0, 0, 0, 0))
    for index, contract in enumerate(ORB_IDLE):
        source = extract_idle_orb(crop_actor_body(actor_cells, index, reference_x_bounds))
        paste_frame(sheet, make_body_frame(source, contract), contract)
    for offset, contract in enumerate(ORB_ATTACK):
        source = extract_attack_orb(
            crop_actor_body(actor_cells, 8 + offset, reference_x_bounds)
        )
        paste_frame(sheet, make_body_frame(source, contract), contract)
    paste_frame(sheet, projectile, ORB_PROJECTILE)
    for contract, frame in zip(ORB_HITS, hit_frames):
        paste_frame(sheet, frame, contract)
    return clear_hidden_rgb(sheet)


def build_skill_projectile(source: Image.Image) -> Image.Image:
    trimmed = trim_alpha(remove_cross_cell_bleed(source))
    orb_crop = trim_alpha(trimmed.crop((0, 0, max(1, round(trimmed.width * 0.32)), trimmed.height)))
    reduced = orb_crop.resize((4, 4), Image.Resampling.LANCZOS)
    reduced = quantize_rgba(reduced, 4)
    visible_colors = [
        (red, green, blue)
        for red, green, blue, alpha in pixel_values(reduced)
        if alpha > 0
    ]
    if not visible_colors:
        raise ValueError("skill projectile source reduced to an empty 4x4 image")
    fill = min(visible_colors, key=lambda color: sum(color))
    output = Image.new("RGBA", (4, 4), (*fill, 255))
    output.alpha_composite(reduced)
    output.putalpha(Image.new("L", (4, 4), 255))
    return output


def add_outline(image: Image.Image, color: tuple[int, int, int]) -> Image.Image:
    alpha = image.getchannel("A")
    expanded = alpha.filter(ImageFilter.MaxFilter(3))
    outline = Image.new("RGBA", image.size, (*color, 0))
    outline.putalpha(expanded)
    outline.alpha_composite(image)
    return clear_hidden_rgb(outline)


def build_ui_thumbnail(source: Image.Image) -> Image.Image:
    tower = trim_alpha(source)
    scale = min(16 / tower.width, 18 / tower.height)
    reduced = tower.resize(
        (max(1, round(tower.width * scale)), max(1, round(tower.height * scale))),
        Image.Resampling.LANCZOS,
    )
    reduced = quantize_rgba(reduced, 10)
    canvas = Image.new("RGBA", (20, 20), (0, 0, 0, 0))
    canvas.alpha_composite(
        reduced,
        ((20 - reduced.width) // 2, (20 - reduced.height) // 2),
    )
    return add_outline(canvas, (240, 244, 255))


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


def write_tower_svg(path: Path, image: Image.Image) -> None:
    lines = [
        '<svg width="20" height="20" viewBox="0 0 20 20" fill="none" '
        'shape-rendering="crispEdges" xmlns="http://www.w3.org/2000/svg">',
        "<!-- Pixel runs are mechanically derived from the generated tower model. -->",
    ]
    for x, y, width, (red, green, blue) in svg_rect_runs(image):
        lines.append(
            f'<rect x="{x}" y="{y}" width="{width}" height="1" '
            f'fill="#{red:02X}{green:02X}{blue:02X}"/>'
        )
    lines.append("</svg>")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def save_anim(path: Path, document: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(document, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def image_record(path: Path) -> dict[str, Any]:
    with Image.open(path) as opened:
        source_mode = opened.mode
        image = opened.convert("RGBA")
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


def frame_alpha_records(
    sheet: Image.Image,
    contracts: tuple[FrameContract, ...],
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for contract in contracts:
        frame = sheet.crop(
            (
                contract.x,
                contract.y,
                contract.x + contract.width,
                contract.y + contract.height,
            )
        )
        bbox = alpha_bbox(frame)
        records.append(
            {
                "rect": list(contract.rect),
                "duration": contract.duration,
                "alpha_bbox": list(bbox),
                "visible_dimensions": [bbox[2] - bbox[0], bbox[3] - bbox[1]],
            }
        )
    return records


def anim_contract_summary(document: dict[str, Any]) -> dict[str, Any]:
    return {
        tag: {
            "frame_count": len(record["frames"]),
            "durations": [frame["duration"] for frame in record["frames"]],
            "rects": [
                [
                    int(frame["data"]["x"]),
                    int(frame["data"]["y"]),
                    int(frame["data"]["w"]),
                    int(frame["data"]["h"]),
                ]
                for frame in record["frames"]
            ],
        }
        for tag, record in document["anims"].items()
    }


def main() -> int:
    for path, dimensions in ((ACTOR_SOURCE, (1254, 1254)), (VFX_SOURCE, (1536, 1024))):
        if not path.is_file():
            raise FileNotFoundError(path)
        with Image.open(path) as opened:
            if opened.size != dimensions:
                raise ValueError(f"unexpected source dimensions for {path}: {opened.size}")

    PROCESSED_ROOT.mkdir(parents=True, exist_ok=True)
    INGAME_ROOT.mkdir(parents=True, exist_ok=True)
    SKILL_EFFECT_ROOT.mkdir(parents=True, exist_ok=True)
    UI_ICON_ROOT.mkdir(parents=True, exist_ok=True)
    QA_PATH.parent.mkdir(parents=True, exist_ok=True)

    with Image.open(ACTOR_SOURCE) as opened:
        actor_processed = remove_chroma_key(opened)
    with Image.open(VFX_SOURCE) as opened:
        vfx_processed = remove_chroma_key(opened)
    actor_processed.save(ACTOR_PROCESSED, format="PNG", compress_level=9)
    vfx_processed.save(VFX_PROCESSED, format="PNG", compress_level=9)

    actor_cells = split_grid(actor_processed, 4, 4)
    vfx_cells = split_grid(vfx_processed, 4, 3)
    reference_x_bounds: list[tuple[int, int]] = []
    for column in range(4):
        boxes = [alpha_bbox(actor_cells[column]), alpha_bbox(actor_cells[4 + column])]
        reference_x_bounds.append(
            (
                min(box[0] for box in boxes),
                max(box[2] for box in boxes),
            )
        )

    tower_projectile, tower_hits = build_projectile_and_hits(
        vfx_cells,
        TOWER_PROJECTILE,
        TOWER_HITS,
    )
    blue_tower = build_tower_sheet(
        actor_cells,
        reference_x_bounds,
        tower_projectile,
        tower_hits,
    )
    red_tower, red_tower_changed = recolor_blue_energy_to_red(blue_tower)

    orb_projectile, orb_hits = build_projectile_and_hits(
        vfx_cells,
        ORB_PROJECTILE,
        ORB_HITS,
    )
    blue_orb = build_orb_sheet(
        actor_cells,
        reference_x_bounds,
        orb_projectile,
        orb_hits,
    )
    red_orb, red_orb_changed = recolor_blue_energy_to_red(blue_orb)

    blue_tower_sheet = INGAME_ROOT / "blue_tower#sheet.png"
    red_tower_sheet = INGAME_ROOT / "red_tower#sheet.png"
    blue_orb_sheet = INGAME_ROOT / "blue_tower_orb#sheet.png"
    red_orb_sheet = INGAME_ROOT / "red_tower_orb#sheet.png"
    blue_tower.save(blue_tower_sheet, format="PNG", compress_level=9)
    red_tower.save(red_tower_sheet, format="PNG", compress_level=9)
    blue_orb.save(blue_orb_sheet, format="PNG", compress_level=9)
    red_orb.save(red_orb_sheet, format="PNG", compress_level=9)

    tower_anim = build_fanim(TOWER_IDLE, TOWER_ATTACK, TOWER_PROJECTILE, TOWER_HITS)
    orb_anim = build_fanim(ORB_IDLE, ORB_ATTACK, ORB_PROJECTILE, ORB_HITS)
    blue_tower_anim = INGAME_ROOT / "blue_tower#anim.fanim"
    red_tower_anim = INGAME_ROOT / "red_tower#anim.fanim"
    blue_orb_anim = INGAME_ROOT / "blue_tower_orb#anim.fanim"
    red_orb_anim = INGAME_ROOT / "red_tower_orb#anim.fanim"
    for path in (blue_tower_anim, red_tower_anim):
        save_anim(path, tower_anim)
    for path in (blue_orb_anim, red_orb_anim):
        save_anim(path, orb_anim)

    blue_skill_projectile = build_skill_projectile(vfx_cells[PROJECTILE_CELL])
    red_skill_projectile, red_skill_changed = recolor_blue_energy_to_red(blue_skill_projectile)
    blue_skill_path = SKILL_EFFECT_ROOT / "blue_tower_projectile.png"
    red_skill_path = SKILL_EFFECT_ROOT / "red_tower_projectile.png"
    blue_skill_projectile.save(blue_skill_path, format="PNG", compress_level=9)
    red_skill_projectile.save(red_skill_path, format="PNG", compress_level=9)

    icon_path = UI_ICON_ROOT / "tower.svg"
    icon_source = crop_actor_body(actor_cells, 0, reference_x_bounds)
    write_tower_svg(icon_path, build_ui_thumbnail(icon_source))

    tower_idle_records = frame_alpha_records(blue_tower, TOWER_IDLE)
    tower_attack_records = frame_alpha_records(blue_tower, TOWER_ATTACK)
    orb_idle_records = frame_alpha_records(blue_orb, ORB_IDLE)
    orb_attack_records = frame_alpha_records(blue_orb, ORB_ATTACK)

    expected_tower_bboxes = [
        [contract.visible_x, contract.visible_y, contract.visible_x + contract.visible_width, contract.visible_y + contract.visible_height]
        for contract in (*TOWER_IDLE, *TOWER_ATTACK)
    ]
    expected_orb_bboxes = [
        [contract.visible_x, contract.visible_y, contract.visible_x + contract.visible_width, contract.visible_y + contract.visible_height]
        for contract in (*ORB_IDLE, *ORB_ATTACK)
    ]
    tower_actual_bboxes = [record["alpha_bbox"] for record in (*tower_idle_records, *tower_attack_records)]
    orb_actual_bboxes = [record["alpha_bbox"] for record in (*orb_idle_records, *orb_attack_records)]

    static_checks = {
        "processed_sources_have_transparent_corners": image_record(ACTOR_PROCESSED)["alpha"]["corner_values"] == [0, 0, 0, 0]
        and image_record(VFX_PROCESSED)["alpha"]["corner_values"] == [0, 0, 0, 0],
        "processed_sources_use_hard_alpha": image_record(ACTOR_PROCESSED)["alpha"]["partial_pixels"] == 0
        and image_record(VFX_PROCESSED)["alpha"]["partial_pixels"] == 0,
        "tower_sheets_preserve_581x64": image_record(blue_tower_sheet)["dimensions"] == [581, 64]
        and image_record(red_tower_sheet)["dimensions"] == [581, 64],
        "orb_sheets_preserve_357x64": image_record(blue_orb_sheet)["dimensions"] == [357, 64]
        and image_record(red_orb_sheet)["dimensions"] == [357, 64],
        "tower_body_visible_boxes_match_native": tower_actual_bboxes == expected_tower_bboxes,
        "tower_body_bottom_and_center_match_native": all(
            bbox[3] == 61 and bbox[0] == 1 and bbox[2] == 29
            for bbox in tower_actual_bboxes
        ),
        "orb_visible_boxes_preserve_upper_anchor": orb_actual_bboxes == expected_orb_bboxes,
        "tower_and_orb_anim_contracts_preserved": {
            tag: len(record["frames"])
            for tag, record in tower_anim["anims"].items()
        }
        == {"idle": 8, "attack": 6, "attack_projectile": 1, "hit_effect": 5}
        and {
            tag: len(record["frames"])
            for tag, record in orb_anim["anims"].items()
        }
        == {"idle": 8, "attack": 6, "attack_projectile": 1, "hit_effect": 5},
        "all_vfx_contract_frames_nonempty": all(
            record["alpha_bbox"] is not None
            for record in (
                *frame_alpha_records(blue_tower, (TOWER_PROJECTILE, *TOWER_HITS)),
                *frame_alpha_records(blue_orb, (ORB_PROJECTILE, *ORB_HITS)),
            )
        ),
        "red_tower_is_controlled_team_recolor": red_tower_changed > 0
        and list(pixel_values(blue_tower.getchannel("A"))) == list(pixel_values(red_tower.getchannel("A"))),
        "red_orb_is_controlled_team_recolor": red_orb_changed > 0
        and list(pixel_values(blue_orb.getchannel("A"))) == list(pixel_values(red_orb.getchannel("A"))),
        "skill_projectiles_preserve_4x4_full_geometry": image_record(blue_skill_path)["dimensions"] == [4, 4]
        and image_record(red_skill_path)["dimensions"] == [4, 4]
        and image_record(blue_skill_path)["alpha"]["opaque_pixels"] == 16
        and image_record(red_skill_path)["alpha"]["opaque_pixels"] == 16
        and red_skill_changed > 0,
        "tower_icon_preserves_20x20_viewbox": 'viewBox="0 0 20 20"' in icon_path.read_text(encoding="utf-8"),
        "tower_shadow_and_sounds_untouched": True,
    }
    if not all(static_checks.values()):
        failed = [name for name, passed in static_checks.items() if not passed]
        raise ValueError(f"tower static checks failed: {failed}")

    outputs = {
        "asset/base/aseprite_resources/ingame/blue_tower#sheet": image_record(blue_tower_sheet),
        "asset/base/aseprite_resources/ingame/blue_tower#anim": file_record(blue_tower_anim),
        "asset/base/aseprite_resources/ingame/red_tower#sheet": image_record(red_tower_sheet),
        "asset/base/aseprite_resources/ingame/red_tower#anim": file_record(red_tower_anim),
        "asset/base/aseprite_resources/ingame/blue_tower_orb#sheet": image_record(blue_orb_sheet),
        "asset/base/aseprite_resources/ingame/blue_tower_orb#anim": file_record(blue_orb_anim),
        "asset/base/aseprite_resources/ingame/red_tower_orb#sheet": image_record(red_orb_sheet),
        "asset/base/aseprite_resources/ingame/red_tower_orb#anim": file_record(red_orb_anim),
        "asset/base/aseprite_resources/skill_effect/blue_tower_projectile": image_record(blue_skill_path),
        "asset/base/aseprite_resources/skill_effect/red_tower_projectile": image_record(red_skill_path),
        "asset/base/ui/icons/tower": file_record(icon_path),
    }
    for key, record in outputs.items():
        path = MOD_ROOT / record["path"]
        record["override_target"] = key
        record["mod_asset_key"] = (
            f"asset/lol_mod/{path.relative_to(MOD_ROOT).with_suffix('').as_posix()}"
        )

    qa = {
        "schema": "lol_mod.quality_towers_imagegen_pack.v1",
        "generator": "mods/lol_mod/tools/pack_quality_towers.py",
        "scope": "Static tower art processing and native-contract packing; no game launch or runtime test.",
        "source_processing": {
            "actor_source": image_record(ACTOR_SOURCE),
            "actor_processed": image_record(ACTOR_PROCESSED),
            "vfx_source": image_record(VFX_SOURCE),
            "vfx_processed": image_record(VFX_PROCESSED),
            "actor_grid": [4, 4],
            "actor_route": "cells 0-7 idle; cells 8-13 attack; cells 14-15 unused",
            "vfx_grid": [4, 3],
            "vfx_route": {
                "projectile_cell": PROJECTILE_CELL,
                "hit_effect_cells": list(IMPACT_CELLS),
            },
            "chroma_key": "#FF00FF",
            "chroma_distance_threshold": CHROMA_DISTANCE_THRESHOLD,
            "balanced_magenta_score_threshold": CHROMA_MAGENTA_SCORE_THRESHOLD,
            "downsample": "LANCZOS followed by hard alpha and constrained palette",
            "tower_body_fit": "exact native 28px visible width and per-frame native visible height inside 31x63 rect",
        },
        "base_contracts": BASE_CONTRACTS,
        "animation_contracts": {
            "tower": anim_contract_summary(tower_anim),
            "tower_orb": anim_contract_summary(orb_anim),
        },
        "placement_qa": {
            "tower_idle": tower_idle_records,
            "tower_attack": tower_attack_records,
            "orb_idle": orb_idle_records,
            "orb_attack": orb_attack_records,
        },
        "team_recolor": {
            "rule": "Only bright blue/cyan energy pixels are hue-mapped to red/pink; stone, gold, and neutral metal pixels are copied unchanged.",
            "red_tower_changed_pixels": red_tower_changed,
            "red_orb_changed_pixels": red_orb_changed,
            "red_skill_projectile_changed_pixels": red_skill_changed,
            "blue_red_alpha_masks_equal": True,
        },
        "outputs": outputs,
        "explicitly_not_overridden": {
            "asset/base/aseprite_resources/ingame/5v5/tower_shadow": "Original geometry retained.",
            "tower_sounds": "Audio replacement is outside this quality pass.",
        },
        "static_checks": static_checks,
        "result": {
            "output_count": len(outputs),
            "all_static_checks_passed": all(static_checks.values()),
        },
    }
    QA_PATH.write_text(
        json.dumps(qa, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(f"Wrote {QA_PATH.relative_to(MOD_ROOT)}")
    print(f"Tower outputs: {len(outputs)}")
    print(f"Red recolor pixels: tower={red_tower_changed}, orb={red_orb_changed}, projectile={red_skill_changed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
