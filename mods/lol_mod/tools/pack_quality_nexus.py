from __future__ import annotations

import colorsys
import json
from pathlib import Path
from typing import Any

from PIL import Image, ImageEnhance

from pack_quality_towers import (
    FrameContract,
    alpha_bbox,
    anim_contract_summary,
    build_fanim,
    clear_hidden_rgb,
    file_record,
    fit_effect,
    image_record,
    pixel_values,
    quantize_rgba,
    save_anim,
    split_grid,
    trim_alpha,
)


MOD_ROOT = Path(__file__).resolve().parents[1]
SOURCE = MOD_ROOT / "source" / "imagegen" / "jungle" / "nexus_actor_orb_contact.png"
PROCESSED = (
    MOD_ROOT
    / "source"
    / "processed"
    / "jungle"
    / "nexus_actor_orb_contact_alpha.png"
)
INGAME_ROOT = MOD_ROOT / "aseprite_resources" / "ingame"
QA_PATH = MOD_ROOT / "qa" / "quality_nexus_imagegen_pack.json"

NEXUS_SHEET_SIZE = (836, 81)
NEXUS_ORB_SHEET_SIZE = (526, 81)

NEXUS_IDLE = tuple(
    FrameContract(x, 0, 57, height, 0.120000005)
    for x, height in zip(
        (0, 58, 116, 174, 232, 290, 348, 406),
        (65, 63, 63, 63, 65, 67, 69, 67),
    )
)
NEXUS_ATTACK = tuple(
    FrameContract(x, 0, 57, height, 0.080000006)
    for x, height in zip(
        (464, 522, 580, 638, 696, 754),
        (65, 65, 73, 79, 80, 80),
    )
)
NEXUS_PROJECTILE = FrameContract(812, 0, 3, 3, 0.080000006)
NEXUS_HITS = tuple(
    FrameContract(x, 0, 3, 3, 0.080000006)
    for x in (816, 820, 824, 828, 832)
)

ORB_IDLE = tuple(
    FrameContract(x, 0, 31, height, 0.120000005)
    for x, height in zip(
        (0, 32, 64, 96, 128, 160, 192, 224),
        (65, 63, 61, 63, 65, 67, 69, 67),
    )
)
ORB_ATTACK = tuple(
    FrameContract(x, 0, width, height, 0.080000006)
    for x, width, height in (
        (256, 31, 65),
        (288, 31, 65),
        (320, 39, 73),
        (360, 45, 79),
        (406, 45, 80),
        (452, 49, 80),
    )
)
ORB_PROJECTILE = FrameContract(502, 0, 3, 3, 0.080000006)
ORB_HITS = tuple(
    FrameContract(x, 0, 3, 3, 0.080000006)
    for x in (506, 510, 514, 518, 522)
)

# Native visible bounds, measured from Teamfight Manager 2 v0.5.0. The source
# subject is resized once per family and then copied without per-frame scaling,
# so animation cannot pulse or twitch when the engine advances frames.
NEXUS_VISIBLE_BOXES = (
    (1, 1, 55, 62),
    (59, 1, 113, 61),
    (117, 2, 171, 61),
    (175, 1, 229, 61),
    (233, 1, 287, 62),
    (291, 1, 345, 63),
    (349, 1, 403, 64),
    (407, 1, 461, 63),
    (465, 1, 519, 62),
    (523, 1, 577, 62),
    (581, 1, 635, 66),
    (639, 8, 693, 69),
    (697, 9, 751, 70),
    (755, 9, 809, 70),
)
ORB_VISIBLE_BOXES = (
    (1, 1, 29, 30),
    (33, 1, 61, 30),
    (65, 1, 93, 30),
    (97, 1, 125, 30),
    (129, 1, 157, 30),
    (161, 1, 189, 30),
    (193, 1, 221, 30),
    (225, 1, 253, 30),
    (257, 1, 285, 30),
    (289, 1, 317, 30),
    (321, 1, 357, 38),
    (368, 8, 396, 37),
    (414, 9, 442, 38),
    (462, 9, 490, 38),
)


def fit_constant_subject(
    source: Image.Image,
    maximum: tuple[int, int],
    *,
    colors: int,
) -> Image.Image:
    trimmed = trim_alpha(source)
    scale = min(maximum[0] / trimmed.width, maximum[1] / trimmed.height)
    resized = trimmed.resize(
        (
            max(1, round(trimmed.width * scale)),
            max(1, round(trimmed.height * scale)),
        ),
        Image.Resampling.LANCZOS,
    )
    return trim_alpha(quantize_rgba(resized, colors))


def paste_constant_frames(
    sheet: Image.Image,
    subject: Image.Image,
    boxes: tuple[tuple[int, int, int, int], ...],
) -> None:
    for left, top, right, bottom in boxes:
        x = left + (right - left - subject.width) // 2
        y = bottom - subject.height
        sheet.alpha_composite(subject, (x, y))


def colored_tiny_effect(source: Image.Image, brightness: float) -> Image.Image:
    tiny = fit_effect(source, (3, 3), margin=0, colors=6)
    return clear_hidden_rgb(ImageEnhance.Brightness(tiny).enhance(brightness))


def recolor_blue_team_to_red(image: Image.Image) -> tuple[Image.Image, int]:
    converted: list[tuple[int, int, int, int]] = []
    changed = 0
    for red, green, blue, alpha in pixel_values(image.convert("RGBA")):
        if alpha == 0:
            converted.append((0, 0, 0, 0))
            continue
        if blue >= 65 and blue >= red + 18 and blue >= green - 18:
            _hue, saturation, value = colorsys.rgb_to_hsv(
                red / 255,
                green / 255,
                blue / 255,
            )
            out_red, out_green, out_blue = colorsys.hsv_to_rgb(
                0.015,
                max(0.5, saturation),
                value,
            )
            converted.append(
                (
                    round(out_red * 255),
                    round(out_green * 255),
                    round(out_blue * 255),
                    alpha,
                )
            )
            changed += 1
        else:
            converted.append((red, green, blue, alpha))
    output = Image.new("RGBA", image.size, (0, 0, 0, 0))
    output.putdata(converted)
    return clear_hidden_rgb(output), changed


def paste_contract(sheet: Image.Image, frame: Image.Image, contract: FrameContract) -> None:
    if frame.size != (contract.width, contract.height):
        raise ValueError(f"effect frame does not match contract: {frame.size} vs {contract.rect}")
    sheet.alpha_composite(frame, (contract.x, contract.y))


def build_actor_sheet(actor: Image.Image, effect_source: Image.Image) -> Image.Image:
    sheet = Image.new("RGBA", NEXUS_SHEET_SIZE, (0, 0, 0, 0))
    stable_actor = fit_constant_subject(actor, (52, 58), colors=48)
    paste_constant_frames(sheet, stable_actor, NEXUS_VISIBLE_BOXES)
    paste_contract(sheet, colored_tiny_effect(effect_source, 1.0), NEXUS_PROJECTILE)
    for index, contract in enumerate(NEXUS_HITS):
        paste_contract(sheet, colored_tiny_effect(effect_source, 0.72 + index * 0.1), contract)
    return clear_hidden_rgb(sheet)


def build_orb_sheet(orb: Image.Image) -> Image.Image:
    sheet = Image.new("RGBA", NEXUS_ORB_SHEET_SIZE, (0, 0, 0, 0))
    # The imagegen orb is intentionally normalized to a square before the
    # native upper-anchor placement, preserving a compact LoL-like core.
    stable_orb = trim_alpha(
        quantize_rgba(
            trim_alpha(orb).resize((25, 25), Image.Resampling.LANCZOS),
            32,
        )
    )
    paste_constant_frames(sheet, stable_orb, ORB_VISIBLE_BOXES)
    paste_contract(sheet, colored_tiny_effect(orb, 1.0), ORB_PROJECTILE)
    for index, contract in enumerate(ORB_HITS):
        paste_contract(sheet, colored_tiny_effect(orb, 0.72 + index * 0.1), contract)
    return clear_hidden_rgb(sheet)


def alpha_sizes(
    sheet: Image.Image,
    boxes: tuple[tuple[int, int, int, int], ...],
) -> list[list[int]]:
    sizes: list[list[int]] = []
    for left, top, right, bottom in boxes:
        frame = sheet.crop((left, top, right, bottom))
        bbox = alpha_bbox(frame)
        sizes.append([bbox[2] - bbox[0], bbox[3] - bbox[1]])
    return sizes


def output_records(paths: dict[str, Path]) -> dict[str, dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    for key, path in paths.items():
        record = image_record(path) if path.suffix == ".png" else file_record(path)
        record["override_target"] = key
        record["mod_asset_key"] = (
            f"asset/lol_mod/{path.relative_to(MOD_ROOT).with_suffix('').as_posix()}"
        )
        records[key] = record
    return records


def main() -> int:
    for path in (SOURCE, PROCESSED):
        if not path.is_file():
            raise FileNotFoundError(path)
        if Image.open(path).size != (1254, 1254):
            raise ValueError(f"unexpected nexus imagegen source size: {path}")

    with Image.open(PROCESSED) as opened:
        processed = clear_hidden_rgb(opened.convert("RGBA"))
    if [processed.getchannel("A").getpixel(point) for point in ((0, 0), (1253, 0), (0, 1253), (1253, 1253))] != [0, 0, 0, 0]:
        raise ValueError("processed nexus source must have transparent corners")

    blue_actor, _red_actor_reference, blue_orb, _red_orb_reference = [
        trim_alpha(cell) for cell in split_grid(processed, 2, 2)
    ]
    blue_actor_sheet = build_actor_sheet(blue_actor, blue_orb)
    blue_orb_sheet = build_orb_sheet(blue_orb)
    red_actor_sheet, red_actor_changed = recolor_blue_team_to_red(blue_actor_sheet)
    red_orb_sheet, red_orb_changed = recolor_blue_team_to_red(blue_orb_sheet)

    INGAME_ROOT.mkdir(parents=True, exist_ok=True)
    paths = {
        "asset/base/aseprite_resources/ingame/blue_nexus#sheet": INGAME_ROOT / "blue_nexus#sheet.png",
        "asset/base/aseprite_resources/ingame/blue_nexus#anim": INGAME_ROOT / "blue_nexus#anim.fanim",
        "asset/base/aseprite_resources/ingame/red_nexus#sheet": INGAME_ROOT / "red_nexus#sheet.png",
        "asset/base/aseprite_resources/ingame/red_nexus#anim": INGAME_ROOT / "red_nexus#anim.fanim",
        "asset/base/aseprite_resources/ingame/blue_nexus_orb#sheet": INGAME_ROOT / "blue_nexus_orb#sheet.png",
        "asset/base/aseprite_resources/ingame/blue_nexus_orb#anim": INGAME_ROOT / "blue_nexus_orb#anim.fanim",
        "asset/base/aseprite_resources/ingame/red_nexus_orb#sheet": INGAME_ROOT / "red_nexus_orb#sheet.png",
        "asset/base/aseprite_resources/ingame/red_nexus_orb#anim": INGAME_ROOT / "red_nexus_orb#anim.fanim",
    }
    for key, sheet in (
        ("asset/base/aseprite_resources/ingame/blue_nexus#sheet", blue_actor_sheet),
        ("asset/base/aseprite_resources/ingame/red_nexus#sheet", red_actor_sheet),
        ("asset/base/aseprite_resources/ingame/blue_nexus_orb#sheet", blue_orb_sheet),
        ("asset/base/aseprite_resources/ingame/red_nexus_orb#sheet", red_orb_sheet),
    ):
        sheet.save(paths[key], format="PNG", compress_level=9)

    nexus_anim = build_fanim(NEXUS_IDLE, NEXUS_ATTACK, NEXUS_PROJECTILE, NEXUS_HITS)
    orb_anim = build_fanim(ORB_IDLE, ORB_ATTACK, ORB_PROJECTILE, ORB_HITS)
    for key in (
        "asset/base/aseprite_resources/ingame/blue_nexus#anim",
        "asset/base/aseprite_resources/ingame/red_nexus#anim",
    ):
        save_anim(paths[key], nexus_anim)
    for key in (
        "asset/base/aseprite_resources/ingame/blue_nexus_orb#anim",
        "asset/base/aseprite_resources/ingame/red_nexus_orb#anim",
    ):
        save_anim(paths[key], orb_anim)

    nexus_sizes = alpha_sizes(blue_actor_sheet, NEXUS_VISIBLE_BOXES)
    orb_sizes = alpha_sizes(blue_orb_sheet, ORB_VISIBLE_BOXES)
    static_checks = {
        "source_is_builtin_imagegen_contact_sheet": Image.open(SOURCE).size == (1254, 1254),
        "processed_source_has_alpha_and_transparent_corners": image_record(PROCESSED)["alpha"]["corner_values"] == [0, 0, 0, 0],
        "native_sheet_dimensions_preserved": blue_actor_sheet.size == red_actor_sheet.size == NEXUS_SHEET_SIZE
        and blue_orb_sheet.size == red_orb_sheet.size == NEXUS_ORB_SHEET_SIZE,
        "actor_frames_use_one_stable_size": len({tuple(size) for size in nexus_sizes}) == 1,
        "orb_frames_use_one_stable_size": len({tuple(size) for size in orb_sizes}) == 1,
        "team_actor_alpha_masks_match": list(pixel_values(blue_actor_sheet.getchannel("A")))
        == list(pixel_values(red_actor_sheet.getchannel("A"))),
        "team_orb_alpha_masks_match": list(pixel_values(blue_orb_sheet.getchannel("A")))
        == list(pixel_values(red_orb_sheet.getchannel("A"))),
        "controlled_red_team_recolor_changed_pixels": red_actor_changed > 0 and red_orb_changed > 0,
        "native_anim_tag_counts_preserved": {
            tag: len(record["frames"]) for tag, record in nexus_anim["anims"].items()
        }
        == {"idle": 8, "attack": 6, "attack_projectile": 1, "hit_effect": 5}
        and {tag: len(record["frames"]) for tag, record in orb_anim["anims"].items()}
        == {"idle": 8, "attack": 6, "attack_projectile": 1, "hit_effect": 5},
    }
    if not all(static_checks.values()):
        raise ValueError(
            "nexus static checks failed: "
            + ", ".join(name for name, passed in static_checks.items() if not passed)
        )

    QA_PATH.parent.mkdir(parents=True, exist_ok=True)
    qa = {
        "schema": "lol_mod.quality_nexus_imagegen_pack.v1",
        "generator": "mods/lol_mod/tools/pack_quality_nexus.py",
        "image_generation": {
            "tool": "built-in imagegen",
            "source": image_record(SOURCE),
            "processed": image_record(PROCESSED),
            "contact_grid": [2, 2],
            "cell_order": ["blue_nexus", "red_nexus", "blue_orb", "red_orb"],
            "prompt_record": "source/imagegen/QUALITY_UPGRADE_PROMPTS.md",
            "runtime_team_pairing": "Blue imagegen cells are the geometry authority; blue energy pixels are hue-mapped to red so both runtime alpha masks are byte-identical.",
            "red_actor_changed_pixels": red_actor_changed,
            "red_orb_changed_pixels": red_orb_changed,
        },
        "animation_contracts": {
            "nexus": anim_contract_summary(nexus_anim),
            "nexus_orb": anim_contract_summary(orb_anim),
        },
        "placement": {
            "nexus_visible_boxes": [list(box) for box in NEXUS_VISIBLE_BOXES],
            "nexus_stable_frame_sizes": nexus_sizes,
            "orb_visible_boxes": [list(box) for box in ORB_VISIBLE_BOXES],
            "orb_stable_frame_sizes": orb_sizes,
        },
        "outputs": output_records(paths),
        "explicitly_not_overridden": {
            "asset/base/aseprite_resources/ingame/5v5/nexus_shadow": "Native position-locked shadow retained.",
            "nexus_destroy_effect": "Native destruction timing/effect retained.",
            "nexus_audio": "Audio is outside this visual replacement pass.",
        },
        "static_checks": static_checks,
    }
    QA_PATH.write_text(
        json.dumps(qa, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(f"Wrote {QA_PATH.relative_to(MOD_ROOT)}")
    print(f"Nexus outputs: {len(paths)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
