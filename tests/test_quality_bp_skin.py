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
    assert qa["source"]["path"].endswith("lol_bp_background_v2_source.png")
    assert not (MOD / "source/imagegen/ui/lol_bp_background_v1_source.png").exists()

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


def test_bp_timer_uses_imagegen_assets_inside_native_visibility_scope() -> None:
    qa = json.loads(
        (MOD / "qa" / "quality_bp_skin_imagegen_pack.json").read_text(encoding="utf-8")
    )
    layout = (MOD / "ui/layout/banpick/layout.ui").read_text(encoding="utf-8")
    timer = qa["timer_assets"]
    assert timer["plate"]["runtime"]["dimensions"] == [170, 20]
    assert timer["icon"]["runtime"]["dimensions"] == [20, 20]
    assert timer["plate"]["chroma_key"]["transparent_pixels"] > 0
    assert timer["icon"]["chroma_key"]["transparent_pixels"] > 0
    assert "#lol_bp_timer_plate:image" not in layout
    assert "#timer_bar_bg:image" in layout
    assert 'source: "asset/lol_mod/ui/banpick/lol_bp_timer_plate";' in layout
    assert 'source: "asset/lol_mod/ui/banpick/lol_bp_timer_icon";' in layout
    for path, size in (
        (MOD / "ui/banpick/lol_bp_timer_plate.png", (170, 20)),
        (MOD / "ui/banpick/lol_bp_timer_icon.png", (20, 20)),
    ):
        with Image.open(path) as image:
            assert image.size == size
            assert image.mode == "RGBA"
            assert image.getchannel("A").getextrema()[0] == 0


def test_bp_component_skin_is_local_and_preserves_component_geometry() -> None:
    qa = json.loads(
        (MOD / "qa" / "quality_bp_skin_imagegen_pack.json").read_text(encoding="utf-8")
    )
    override = json.loads((MOD / "mod.override_info").read_text(encoding="utf-8"))
    layout = (MOD / "ui/layout/banpick/layout.ui").read_text(encoding="utf-8")
    champion_slot = (MOD / "ui/layout/banpick/champion_slot.ui").read_text(encoding="utf-8")
    style = (MOD / "style/bp_controls.style").read_text(encoding="utf-8")
    assert override["asset/base/ui/layout/banpick/champion_slot"] == {
        "remapping": "asset/lol_mod/ui/layout/banpick/champion_slot",
        "type": "override",
    }
    assert "asset/base/style/main" not in override
    assert 'asset/lol_mod/style/bp_controls#dropdown' in layout
    assert 'asset/lol_mod/style/bp_controls#text_edit' in layout
    assert "width: 119px;\n  height: 130px;" in champion_slot
    assert "width: 118px;\n    height: 88px;" in champion_slot
    assert "normal: #29475cff;" in champion_slot
    assert "hover: #c8aa6eff;" in champion_slot
    for token in ("text_edit:", "tertiary_button:", "primary_button:", "secondary_button:", "dropdown:"):
        assert token in style
    assert len(qa["imagegen_asset_requests"]) == 5


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
    assert "back_color: #07131ff2;" in blue
    assert "color: #294f6aff;" in blue
    assert "back_color: #180a0ff2;" in red
    assert "color: #6b3442ff;" in red


def test_quality_builder_rebuilds_the_bp_skin() -> None:
    source = (MOD / "tools" / "build_lol_mod.py").read_text(encoding="utf-8")
    assert '"pack_quality_bp_skin.py"' in source
