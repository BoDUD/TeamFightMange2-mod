from __future__ import annotations

import json
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
MOD = ROOT / "mods" / "lol_mod"


def test_bp_skin_uses_an_imagegen_background_without_replacing_interactions() -> None:
    qa = json.loads(
        (MOD / "qa" / "quality_bp_skin_imagegen_pack.json").read_text(
            encoding="utf-8"
        )
    )
    layout = (MOD / "ui" / "layout" / "banpick" / "layout.ui").read_text(
        encoding="utf-8"
    )
    override = json.loads((MOD / "mod.override_info").read_text(encoding="utf-8"))

    assert qa["schema"] == "lol_mod.quality_bp_skin_imagegen_pack.v1"
    assert qa["imagegen_mode"] == "built-in image generation"
    assert all(qa["static_checks"].values())
    assert all(qa["geometry_contract"].values())
    assert qa["layout"]["restored_native_sha256"] == qa["layout"][
        "native_baseline_normalized_sha256"
    ]
    assert override["asset/base/ui/layout/banpick/layout"] == {
        "remapping": "asset/lol_mod/ui/layout/banpick/layout",
        "type": "override",
    }

    node = layout.split("#lol_bp_background:image", 1)[1].split("}", 1)[0]
    assert "ignore_event: true;" in node
    assert 'source: "asset/lol_mod/ui/banpick/lol_bp_background";' in node
    assert "/champions/" not in node
    for forbidden in (
        "bp_settings",
        "bp_skin_cycle",
        "bp_illust_cycle",
        "bp_redflip_toggle",
        "bp_hoverbg_toggle",
    ):
        assert forbidden not in layout


def test_bp_skin_keeps_native_geometry_and_runtime_size() -> None:
    layout = (MOD / "ui" / "layout" / "banpick" / "layout.ui").read_text(
        encoding="utf-8"
    )
    assert "height: 85px;" in layout
    assert "height: 150px;" in layout
    assert "#blue_picks:empty {\n    y: 97px;" in layout
    assert "#red_picks:empty {\n    anchor_x: 1;\n    pivot_x: 1;\n    y: 97px;" in layout
    assert "#champions_bg:color {\n    width: 1250px;\n    height: 377px;" in layout
    assert "x: 335px;\n    y: 145px;" in layout
    assert "#champion_info:empty {\n    width: 1250px;\n    height: 371px;" in layout
    assert "#swap:empty {\n    width: 1290px;\n    height: 738px;" in layout

    with Image.open(MOD / "ui" / "banpick" / "lol_bp_background.png") as image:
        assert image.size == (1920, 1080)


def test_bp_pick_card_skin_changes_colors_only_not_card_geometry() -> None:
    blue = (MOD / "ui" / "layout" / "banpick" / "blue_pick_slot.ui").read_text(
        encoding="utf-8"
    )
    red = (MOD / "ui" / "layout" / "banpick" / "red_pick_slot.ui").read_text(
        encoding="utf-8"
    )
    for slot in (blue, red):
        assert "width: 300px;" in slot
        assert "height: 174px;" in slot
        assert "width: 15px;" in slot
        assert "height: 172px;" in slot
        assert "z: 50;" in slot
    assert "back_color: #07121ee8;" in blue
    assert "color: #315b7dff;" in blue
    assert "back_color: #19090ee8;" in red
    assert "color: #78404cff;" in red


def test_quality_builder_rebuilds_the_bp_skin() -> None:
    source = (MOD / "tools" / "build_lol_mod.py").read_text(encoding="utf-8")
    assert '"pack_quality_bp_skin.py"' in source
