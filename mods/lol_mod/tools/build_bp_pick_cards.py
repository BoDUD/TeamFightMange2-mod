"""Add fixed-source illustrations to the verified native 0.5.8 side cards.

Do not replace the complete draft layout or its custom champion-grid runner.
Only two leaf templates are augmented; stripping our one block must recover
the exact bundled native template. This avoids late-spawned 0x0 image nodes.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pack_quality_bp_skin as native

MOD = Path(__file__).resolve().parents[1]
HEROES = (
    "lol_shen", "archer", "barrier_magician", "berserker", "boomerang_hunter",
    "cavalry_knight", "dancer", "demon", "dual_blader",
)
OUTPUT = MOD / "ui" / "bp_pick_cards"


def illustration_block(side: str) -> str:
    assert side in ("blue", "red")
    # LAST child of #done: the opaque illustration covers the native name,
    # position, mastery badge, favourite heroes and centre divider. Their
    # native paths/visibility remain intact for non-mod cards and swap fallback.
    # No negative z, global overlay, or left-side darkening tint.
    rows = ["\n    #lol_bp_illustrations:empty {",
            "      width: 300px; height: 174px; ignore_event: true; visible: false;", "",
            "      #opaque_backing:color {",
            "        x: 8px; y: 1px; width: 284px; height: 172px;",
            "        ignore_event: true; color: #07080bff;",
            "      }"]
    for hero in HEROES:
        rows += [f"      #{hero}:image {{",
                 "        x: 8px; y: 1px; width: 284px; height: 172px;",
                 "        ignore_event: true; visible: false; sample_linear: true;",
                 f'        source: "asset/lol_mod/ui/banpick/champion_illustration/{hero}_{side}";',
                 "      }"]
    rows += ["    }\n"]
    return "\n".join(rows)


def base_template(side: str) -> str:
    text = (native.MOD_ROOT / "ui" / "layout" / "banpick" / f"{side}_pick_slot.ui").read_text(encoding="utf-8")
    base = native._strip_exact_blocks(text, (native.LOL_SIDE_PICK_FRAME_BLOCK,))
    expected = getattr(native, f"NATIVE_{side.upper()}_PICK_SLOT_NORMALIZED_SHA256")
    if hashlib.sha256(base.encode()).hexdigest() != expected:
        raise ValueError(f"Unverified native {side} side-card template")
    return base


def build_template(side: str) -> str:
    base = base_template(side)
    # Verified boundary immediately after the done card's final native child.
    marker = "\n  }\n\n  #player_tooltip:color {"
    assert base.count(marker) == 1
    return base.replace(marker, illustration_block(side) + marker, 1)


def build() -> list[Path]:
    try:
        bundle = native.find_bundle_path()
    except FileNotFoundError:
        bundle = None
    if bundle is not None:
        current, _ = native.read_native_bp_layouts(bundle)
        for side in ("blue", "red"):
            if base_template(side) != current[f"{side}_pick_slot"]:
                raise ValueError(f"Installed game changed native {side} card; audit before rebuilding")
    OUTPUT.mkdir(parents=True, exist_ok=True)
    outputs = []
    for side in ("blue", "red"):
        path = OUTPUT / f"{side}_pick_slot.ui"
        path.write_text(build_template(side), encoding="utf-8", newline="\n")
        outputs.append(path)
    override_path = MOD / "mod.override_info"
    overrides = json.loads(override_path.read_text(encoding="utf-8"))
    for side in ("blue", "red"):
        overrides[f"asset/base/ui/layout/banpick/{side}_pick_slot"] = {
            "remapping": f"asset/lol_mod/ui/bp_pick_cards/{side}_pick_slot",
            "type": "override",
        }
    override_path.write_text(json.dumps(overrides, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    return outputs


if __name__ == "__main__":
    for output in build():
        print(output.relative_to(MOD))
