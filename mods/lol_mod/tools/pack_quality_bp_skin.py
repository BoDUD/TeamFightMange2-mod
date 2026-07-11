from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from PIL import Image


MOD_ROOT = Path(__file__).resolve().parents[1]
SOURCE_PATH = MOD_ROOT / "source" / "imagegen" / "ui" / "lol_bp_background_v1_source.png"
RUNTIME_PATH = MOD_ROOT / "ui" / "banpick" / "lol_bp_background.png"
LAYOUT_PATH = MOD_ROOT / "ui" / "layout" / "banpick" / "layout.ui"
OVERRIDE_PATH = MOD_ROOT / "mod.override_info"
QA_PATH = MOD_ROOT / "qa" / "quality_bp_skin_imagegen_pack.json"

RUNTIME_SIZE = (1920, 1080)
NATIVE_LAYOUT_SHA256 = "992a454554179402ada48c1dda6bcae470be0f64da00cbd0e9b5308e00ee96dc"
NATIVE_LAYOUT_NORMALIZED_SHA256 = (
    "c8e3e90310f1f72deb401a10be46bd227ef29461522826e5f041b9e608029c05"
)

IMAGEGEN_PROMPT = (
    "Original 16:9 premium fantasy MOBA champion-draft background plate: deep navy-black "
    "rift stone and mist, cool blue far-left edge, muted crimson far-right edge, thin antique-"
    "gold outer accents, and a quiet low-contrast centre. No text, logos, champions, cards, "
    "buttons, icons, or copied game UI."
)

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


def restored_native_layout_hash(layout: str) -> str:
    restored = layout.replace(LOL_BACKGROUND_BLOCK, "")
    for styled, native in ALLOWED_COLOR_RESTORES.items():
        restored = restored.replace(styled, native)
    # The bundle text contains whitespace-only padding on a few blank lines.
    # Canonicalize it so the audit still proves the native UI tree/geometry
    # while keeping the checked-in layout clean for git diff --check.
    canonical = "\n".join(line.rstrip() for line in restored.splitlines()) + "\n"
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def main() -> int:
    if not SOURCE_PATH.is_file():
        raise FileNotFoundError(SOURCE_PATH)
    if not LAYOUT_PATH.is_file():
        raise FileNotFoundError(LAYOUT_PATH)

    with Image.open(SOURCE_PATH) as opened:
        background = opened.convert("RGBA").resize(RUNTIME_SIZE, Image.Resampling.LANCZOS)
    RUNTIME_PATH.parent.mkdir(parents=True, exist_ok=True)
    background.save(RUNTIME_PATH, optimize=True)

    layout = LAYOUT_PATH.read_text(encoding="utf-8")
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
        "layout": {
            "path": LAYOUT_PATH.relative_to(MOD_ROOT).as_posix(),
            "sha256": sha256(LAYOUT_PATH),
            "native_baseline_sha256": NATIVE_LAYOUT_SHA256,
            "native_baseline_normalized_sha256": NATIVE_LAYOUT_NORMALIZED_SHA256,
            "restored_native_sha256": restored_native_layout_hash(layout),
            "allowed_changes": [
                "one ignore_event image node",
                "BP-local background/panel/border color values",
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
