from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from statistics import median
from typing import Any

from PIL import Image


MOD_ROOT = Path(__file__).resolve().parents[1]
SOURCE_PATH = MOD_ROOT / "source" / "imagegen" / "ui" / "lol_bp_background_v2_source.png"
RUNTIME_PATH = MOD_ROOT / "ui" / "banpick" / "lol_bp_background.png"
TIMER_PLATE_SOURCE = MOD_ROOT / "source" / "imagegen" / "ui" / "lol_bp_timer_plate_v1_source.png"
TIMER_ICON_SOURCE = MOD_ROOT / "source" / "imagegen" / "ui" / "lol_bp_timer_icon_v1_source.png"
TIMER_PLATE_RUNTIME = MOD_ROOT / "ui" / "banpick" / "lol_bp_timer_plate.png"
TIMER_ICON_RUNTIME = MOD_ROOT / "ui" / "banpick" / "lol_bp_timer_icon.png"
LAYOUT_PATH = MOD_ROOT / "ui" / "layout" / "banpick" / "layout.ui"
CHAMPION_SLOT_PATH = MOD_ROOT / "ui" / "layout" / "banpick" / "champion_slot.ui"
BLUE_PICK_SLOT_PATH = MOD_ROOT / "ui" / "layout" / "banpick" / "blue_pick_slot.ui"
RED_PICK_SLOT_PATH = MOD_ROOT / "ui" / "layout" / "banpick" / "red_pick_slot.ui"
CONTROL_STYLE_PATH = MOD_ROOT / "style" / "bp_controls.style"
OVERRIDE_PATH = MOD_ROOT / "mod.override_info"
QA_PATH = MOD_ROOT / "qa" / "quality_bp_skin_imagegen_pack.json"

RUNTIME_SIZE = (1920, 1080)
TIMER_PLATE_SIZE = (170, 20)
TIMER_ICON_SIZE = (20, 20)
CHROMA_KEY = (255, 0, 255)
CHROMA_TRANSPARENT_DISTANCE = 42.0
CHROMA_OPAQUE_DISTANCE = 118.0
NATIVE_LAYOUT_SHA256 = "992a454554179402ada48c1dda6bcae470be0f64da00cbd0e9b5308e00ee96dc"
NATIVE_LAYOUT_NORMALIZED_SHA256 = (
    "c8e3e90310f1f72deb401a10be46bd227ef29461522826e5f041b9e608029c05"
)

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

COMPONENT_IMAGEGEN_REQUESTS = [
    {
        "id": "champion_card_frame",
        "source_path": "source/imagegen/ui/lol_bp_champion_card_frame_v1_source.png",
        "runtime_dimensions": [119, 130],
        "alpha": "transparent centre and exterior; frame pixels only",
        "layout_reference": "asset/base/ui/layout/banpick/champion_slot root frame overlay",
    },
    {
        "id": "skill_card_frame",
        "source_path": "source/imagegen/ui/lol_bp_skill_card_frame_v1_source.png",
        "runtime_dimensions": [687, 115],
        "alpha": "transparent centre and exterior; border plus weak left icon-divider ornament",
        "layout_reference": "layout.ui #champion_info #skill1/#skill2/#ult background overlay",
    },
    {
        "id": "square_control_frame",
        "source_path": "source/imagegen/ui/lol_bp_square_control_frame_v1_source.png",
        "runtime_dimensions": [40, 40],
        "alpha": "transparent centre; 1-2px frame only",
        "layout_reference": "40x40 category/position/search-clear controls",
    },
    {
        "id": "delegate_button_frame",
        "source_path": "source/imagegen/ui/lol_bp_delegate_button_frame_v1_source.png",
        "runtime_dimensions": [285, 40],
        "alpha": "transparent centre; frame only",
        "layout_reference": "layout.ui #header #delegate_btn",
    },
    {
        "id": "swap_confirm_button_frame",
        "source_path": "source/imagegen/ui/lol_bp_swap_confirm_button_frame_v1_source.png",
        "runtime_dimensions": [639, 67],
        "alpha": "transparent centre; frame only",
        "layout_reference": "layout.ui #swap #bottom #confirm",
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

ALLOWED_COLOR_RESTORES = {
    "#03070eff": "#07080bff",
    "#08111dee": "#161721ff",
    "#0a121fed": "#161721ff",
    "#07101bf4": "#0f1016ff",
    "#0a121ff0": "#161721ff",
    "#163b64f5": "#192880ff",
    "#642638f5": "#78221cff",
    "#08111df5": "#161721ff",
    "#9b7b42ff": "#4a4c56ff",
    "#07131ff2": "#161721ff",
    "#0ac8b9ff": "#37d5b3ff",
    "#66e6d8ff": "#ecfbf8ff",
    "#203848ff": "#4a4c56ff",
    "#0b2130f8": "#0f1016ff",
    "#0d1b29f5": "#1d1f2cff",
    "#101f2cff": "#0f1016ff",
    "#08131ef7": "#161721ff",
    "#132435ff": "#1d1f2cff",
    "#385266ff": "#4a4c56ff",
}

STYLE_REFERENCE_RESTORES = {
    "asset/lol_mod/style/bp_controls#secondary_button": "asset/base/style/main#secondary_button",
    "asset/lol_mod/style/bp_controls#tertiary_button": "asset/base/style/main#tertiary_button",
    "asset/lol_mod/style/bp_controls#primary_button": "asset/base/style/main#primary_button",
    "asset/lol_mod/style/bp_controls#dropdown": "asset/base/style/main#dropdown",
    "asset/lol_mod/style/bp_controls#text_edit": "asset/base/style/main#text_edit",
}


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


def restored_native_layout(layout: str) -> str:
    restored = layout.replace(LOL_BACKGROUND_BLOCK, "")
    restored = restored.replace(
        """    #timer_icon:image {
      width: 20px;
      height: 20px;
      y: 10px;
      source: \"asset/lol_mod/ui/banpick/lol_bp_timer_icon\";
      color: #ffffffff;
""",
        """    #timer_icon:image {
      width: 20px;
      height: 20px;
      y: 10px;
      source: \"asset/base/ui/icons/time\";
      color: #e8e8e8ff;
""",
    )
    restored = restored.replace(
        """      size: 20;
      color: #f0e6d2ff;
      align_y: Center;
""",
        """      size: 20;
      align_y: Center;
""",
        1,
    )
    restored = restored.replace(
        """    #timer_bar_bg:image {
      width: 170px;
      height: 20px;
      y: 10px;
      source: \"asset/lol_mod/ui/banpick/lol_bp_timer_plate\";
""",
        """    #timer_bar_bg:color {
      width: 170px;
      height: 20px;
      y: 10px;
      color: #4a4c56ff;
""",
    )
    for styled, native in STYLE_REFERENCE_RESTORES.items():
        restored = restored.replace(styled, native)
    for styled, native in ALLOWED_COLOR_RESTORES.items():
        restored = restored.replace(styled, native)
    restored = restored.replace(
        """  #champions_bg:color {
    width: 1250px;
    height: 377px;

    x: 335px;
    y: 145px;

    color: #161721ff;

    rounding: Uniform {
      rounding: 6;
""",
        """  #champions_bg:color {
    width: 1250px;
    height: 377px;

    x: 335px;
    y: 145px;

    color: #161721ff;

    rounding: Uniform {
      rounding: 12;
""",
    )
    restored = restored.replace(
        """    #stat:color {
      color: #161721ff;
      rounding: Uniform {
        rounding: 6;
""",
        """    #stat:color {
      color: #161721ff;
      rounding: Uniform {
        rounding: 12;
""",
    )
    restored = restored.replace(
        """      #header:color {
        color: #0f1016ff;

        rounding: Individual {
          top_left: 6;
          top_right: 6;
          bottom_left: 0;
          bottom_right: 0;
        }
        width: 549px;
""",
        """      #header:color {
        color: #0f1016ff;

        rounding: Individual {
          top_left: 12;
          top_right: 12;
          bottom_left: 0;
          bottom_right: 0;
        }
        width: 549px;
""",
    )
    for skill_id in ("skill1", "skill2", "ult"):
        restored = restored.replace(
            f"""    #{skill_id}:color {{
      width: 687px;
      height: 115px;
"""
            + ("      x: 563px;\n" if skill_id == "skill1" else ""),
            f"""    #{skill_id}:color {{
      width: 687px;
      height: 115px;
"""
            + ("      x: 563px;\n" if skill_id == "skill1" else ""),
        )
    restored = restored.replace(
        """      color: #161721ff;
      rounding: Uniform {
        rounding: 6;
""",
        """      color: #161721ff;
      rounding: Uniform {
        rounding: 12;
""",
        3,
    )
    # The bundle text contains whitespace-only padding on a few blank lines.
    # Canonicalize it so the audit still proves the native UI tree/geometry
    # while keeping the checked-in layout clean for git diff --check.
    canonical = "\n".join(line.rstrip() for line in restored.splitlines()) + "\n"
    return canonical


def restored_native_layout_hash(layout: str) -> str:
    return hashlib.sha256(restored_native_layout(layout).encode("utf-8")).hexdigest()


def main() -> int:
    required_files = (
        SOURCE_PATH,
        TIMER_PLATE_SOURCE,
        TIMER_ICON_SOURCE,
        LAYOUT_PATH,
        CHAMPION_SLOT_PATH,
        BLUE_PICK_SLOT_PATH,
        RED_PICK_SLOT_PATH,
        CONTROL_STYLE_PATH,
    )
    for required in required_files:
        if not required.is_file():
            raise FileNotFoundError(required)

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
            and "#icon:canvas {\n    width: 118px;\n    height: 88px;" in champion_slot
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
        "champion_slot_override_registered": override.get(
            "asset/base/ui/layout/banpick/champion_slot"
        )
        == {
            "remapping": "asset/lol_mod/ui/layout/banpick/champion_slot",
            "type": "override",
        },
        "component_palette_is_lol_style": (
            "normal: #29475cff;" in champion_slot
            and "hover: #c8aa6eff;" in champion_slot
            and "back_color: #07131ff2;" in champion_slot
            and "back_color: #07131ff2;" in blue_pick_slot
            and "back_color: #180a0ff2;" in red_pick_slot
            and "color: #08131ef7;" in layout
        ),
        "native_layout_restores_after_skin_delta": (
            restored_native_layout_hash(layout) == NATIVE_LAYOUT_NORMALIZED_SHA256
        ),
        "layout_override_registered": override.get("asset/base/ui/layout/banpick/layout")
        == {
            "remapping": "asset/lol_mod/ui/layout/banpick/layout",
            "type": "override",
        },
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
                "plate replaces #timer_bar_bg inside native #timer_area; no independent "
                "always-visible root sibling"
            ),
        },
        "components": {
            "control_style": {
                "path": CONTROL_STYLE_PATH.relative_to(MOD_ROOT).as_posix(),
                "sha256": sha256(CONTROL_STYLE_PATH),
            },
            "champion_slot": {
                "path": CHAMPION_SLOT_PATH.relative_to(MOD_ROOT).as_posix(),
                "sha256": sha256(CHAMPION_SLOT_PATH),
            },
            "blue_pick_slot": {
                "path": BLUE_PICK_SLOT_PATH.relative_to(MOD_ROOT).as_posix(),
                "sha256": sha256(BLUE_PICK_SLOT_PATH),
            },
            "red_pick_slot": {
                "path": RED_PICK_SLOT_PATH.relative_to(MOD_ROOT).as_posix(),
                "sha256": sha256(RED_PICK_SLOT_PATH),
            },
        },
        "imagegen_asset_requests": COMPONENT_IMAGEGEN_REQUESTS,
        "layout": {
            "path": LAYOUT_PATH.relative_to(MOD_ROOT).as_posix(),
            "sha256": sha256(LAYOUT_PATH),
            "native_baseline_sha256": NATIVE_LAYOUT_SHA256,
            "native_baseline_normalized_sha256": NATIVE_LAYOUT_NORMALIZED_SHA256,
            "restored_native_sha256": restored_native_layout_hash(layout),
            "allowed_changes": [
                "one ignore_event image node",
                "BP-local background/panel/border color values",
                "BP-local style references",
                "ImageGen timer plate/icon sources inside the native timer geometry",
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
