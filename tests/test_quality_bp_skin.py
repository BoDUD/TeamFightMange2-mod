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
    assert "width: 118px;\n    height: 88px;\n    y: 4px;" in champion_slot
    assert "normal: #29475cff;" in champion_slot
    assert "hover: #c8aa6eff;" in champion_slot
    for token in ("text_edit:", "tertiary_button:", "primary_button:", "secondary_button:", "dropdown:"):
        assert token in style
    assert qa["imagegen_asset_requests"] == []
    assert len(qa["component_source_contracts"]) == 3
    assert qa["components"]["champion_slot"]["restored_native_sha256"] == qa[
        "components"
    ]["champion_slot"]["native_baseline_normalized_sha256"]


def test_bp_imagegen_component_chrome_is_sized_and_noninteractive() -> None:
    qa = json.loads(
        (MOD / "qa" / "quality_bp_skin_imagegen_pack.json").read_text(encoding="utf-8")
    )
    layout = (MOD / "ui/layout/banpick/layout.ui").read_text(encoding="utf-8")
    champion_slot = (MOD / "ui/layout/banpick/champion_slot.ui").read_text(encoding="utf-8")
    expected = {
        "header_chrome": (1920, 85),
        "bottom_chrome": (1920, 150),
        "champion_card_frame": (119, 130),
        "filter_toolbar": (1260, 50),
        "champion_grid_frame": (1250, 377),
        "stat_frame": (549, 371),
        "skill_frame": (687, 115),
        "side_pick_frame": (300, 174),
    }
    for name, size in expected.items():
        record = qa["components"]["imagegen_assets"][name]["runtime"]
        assert tuple(record["dimensions"]) == size
        path = MOD / record["path"]
        with Image.open(path) as image:
            assert image.size == size
            assert image.mode == "RGBA"
            assert image.getchannel("A").getextrema()[0] == 0

    for node in (
        "lol_bp_header_chrome",
        "lol_bp_bottom_chrome",
        "lol_bp_filter_toolbar",
        "lol_bp_champion_grid_frame",
        "lol_bp_stat_frame",
        "lol_bp_skill_frame",
    ):
        block = layout.split(f"#{node}:image", 1)[1].split("}", 1)[0]
        assert "ignore_event: true;" in block
    frame = champion_slot.split("#lol_bp_champion_card_frame:image", 1)[1].split("}", 1)[0]
    assert "ignore_event: true;" in frame
    assert "z: 2;" in frame
    assert qa["components"]["contact_sheet"]["dimensions"] == [1200, 800]


def test_bp_champion_preview_has_a_safe_top_inset_without_changing_card_input() -> None:
    qa = json.loads(
        (MOD / "qa" / "quality_bp_skin_imagegen_pack.json").read_text(encoding="utf-8")
    )
    champion_slot = (MOD / "ui/layout/banpick/champion_slot.ui").read_text(
        encoding="utf-8"
    )
    safe = qa["components"]["champion_slot"]["preview_safe_area"]

    assert safe == {
        "root_dimensions": [119, 130],
        "icon_canvas_dimensions": [118, 88],
        "top_inset_px": 4,
        "name_band_height_px": 38,
        "icon_bottom_px": 92,
        "name_band_top_px": 92,
        "icon_stops_before_name_band": True,
        "frame_overlay_z": 2,
        "icon_z": 0,
        "frame_overlays_actor": True,
        "root_and_click_geometry_unchanged": True,
        "render_camera_and_actor_contract_unchanged": True,
        "purpose": (
            "keep tall weapons and head silhouettes below the ornate top rim without "
            "changing the 119x130 card hit target or actor animation"
        ),
    }
    assert champion_slot.startswith(
        "champion_slot:banpick_champion_slot {\n  width: 119px;\n  height: 130px;"
    )
    icon = champion_slot.split("#icon:canvas", 1)[1].split("}", 1)[0]
    assert "width: 118px;" in icon
    assert "height: 88px;" in icon
    assert "y: 4px;" in icon
    assert "ignore_event: true;" in icon
    assert safe["top_inset_px"] + safe["icon_canvas_dimensions"][1] <= (
        safe["root_dimensions"][1] - safe["name_band_height_px"]
    )
    frame = champion_slot.split("#lol_bp_champion_card_frame:image", 1)[1].split(
        "}", 1
    )[0]
    assert "ignore_event: true;" in frame
    assert safe["frame_overlay_z"] > safe["icon_z"]
    assert f'z: {safe["frame_overlay_z"]};' in frame


def test_bp_pick_card_skin_preserves_geometry_and_uses_noninteractive_frame() -> None:
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
        frame = slot.split("#lol_bp_side_pick_frame:image", 1)[1].split("}", 1)[0]
        assert "ignore_event: true;" in frame
        assert 'source: "asset/lol_mod/ui/banpick/lol_bp_side_pick_frame";' in frame
    assert "back_color: #07131ff2;" in blue
    assert "color: #294f6aff;" in blue
    assert "back_color: #180a0ff2;" in red
    assert "color: #6b3442ff;" in red


def test_quality_builder_rebuilds_the_bp_skin() -> None:
    source = (MOD / "tools" / "build_lol_mod.py").read_text(encoding="utf-8")
    assert '"pack_quality_bp_skin.py"' in source
