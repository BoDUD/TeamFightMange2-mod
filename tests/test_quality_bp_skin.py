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
    # Base 0.5.1 owns the active BP tree. Its layout added required skill-name,
    # turn-outline, and champion-pool-wait nodes that the archived 0.5.0 skin
    # does not contain, so overriding it can crash the host during draft.
    assert all(
        key not in override
        for key in (
            "asset/base/ui/layout/banpick/blue_pick_slot",
            "asset/base/ui/layout/banpick/red_pick_slot",
            "asset/base/ui/layout/banpick/champion_slot",
            "asset/base/ui/layout/banpick/layout",
        )
    )
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
    assert "asset/base/ui/layout/banpick/champion_slot" not in override
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
    assert "z:" not in frame
    assert champion_slot.index("#lol_bp_champion_card_frame:image") < champion_slot.index(
        "#icon:canvas"
    )
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
        "frame_render_order": "before_icon_canvas",
        "frame_uses_native_sibling_order": True,
        "frame_has_explicit_z": False,
        "frame_visible_regression_fix": True,
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
    assert "z:" not in frame
    assert champion_slot.index("#lol_bp_champion_card_frame:image") < champion_slot.index(
        "#icon:canvas"
    )


def test_bp_chrome_safe_fields_enclose_native_controls_without_moving_them() -> None:
    qa = json.loads(
        (MOD / "qa" / "quality_bp_skin_imagegen_pack.json").read_text(
            encoding="utf-8"
        )
    )
    layout = (MOD / "ui/layout/banpick/layout.ui").read_text(encoding="utf-8")
    safe = qa["components"]["chrome_safe_area"]
    header = safe["header"]
    bottom = safe["bottom"]

    assert header["layout_dimensions"] == [1920, 85]
    assert header["target_margins_px"] == [14, 18, 14, 18]
    assert header["runtime_transparent_insets_px"] == [0, 0, 0, 0]
    assert header["full_vertical_coverage"] == [0, 85]
    assert header["native_control_bboxes_px"] == {
        "delegate": [15, 23, 300, 63],
        "step": [335, 0, 549, 85],
        "description": [418, 0, 1502, 85],
        "swap_phase": [1371, 1, 1877, 84],
    }
    assert bottom["layout_dimensions"] == [1920, 150]
    assert bottom["target_margins_px"] == [16, 12, 16, 4]
    assert bottom["runtime_transparent_insets_px"] == [0, 0, 0, 0]
    assert bottom["full_vertical_coverage"] == [0, 150]
    assert bottom["native_side_control_columns_px"] == {
        "blue": [0, 0, 300, 150],
        "red": [1620, 0, 1920, 150],
    }
    assert bottom["bright_side_wings_confined_to_px"] == {
        "left": [0, 16],
        "right": [1904, 1920],
    }
    assert header["straight_dark_backing_under_side_controls"] is True
    assert bottom["straight_dark_backing_under_side_controls"] is True
    assert safe["background_asset_or_layout_rollback"] is False

    # The image nodes still fill the exact native 85px/150px containers.  No
    # native label, timer, team, ban, or button coordinates were moved.
    assert "#header:color {\n    color: #08111dee;\n    width: 100%;\n    height: 85px;" in layout
    assert "#bottom:color {\n    color: #08111dee;\n\n    width: 100%;\n    height: 150px;" in layout
    assert "#delegate_btn:color_icon_button" in layout
    assert "x: 15px;\n      y: 23px;\n      width: 285px;\n      height: 40px;" in layout
    assert "#blue_picks:empty {\n    y: 97px;\n\n    width: 300px;\n    height: 926px;" in layout
    assert "#red_picks:empty {\n    anchor_x: 1;\n    pivot_x: 1;\n    y: 97px;" in layout

    for asset_name, expected_bbox in (
        ("header", (0, 0, 1920, 85)),
        ("bottom", (0, 0, 1920, 150)),
    ):
        with Image.open(
            MOD / "ui/banpick" / f"lol_bp_{asset_name}_chrome.png"
        ) as image:
            alpha = image.convert("RGBA").getchannel("A")
            assert alpha.getbbox() == expected_bbox

    with Image.open(MOD / "ui/banpick/lol_bp_header_chrome.png") as image:
        alpha = image.convert("RGBA").getchannel("A")
        assert alpha.crop((15, 23, 300, 63)).getextrema() == (255, 255)
        assert alpha.crop((1371, 12, 1877, 73)).getextrema() == (255, 255)
    with Image.open(MOD / "ui/banpick/lol_bp_bottom_chrome.png") as image:
        alpha = image.convert("RGBA").getchannel("A")
        assert alpha.crop((15, 12, 300, 138)).getextrema() == (255, 255)
        assert alpha.crop((1620, 12, 1905, 138)).getextrema() == (255, 255)


def test_bp_chrome_edges_have_no_hot_magenta_key_fringe() -> None:
    qa = json.loads(
        (MOD / "qa" / "quality_bp_skin_imagegen_pack.json").read_text(
            encoding="utf-8"
        )
    )
    assets = qa["components"]["imagegen_assets"]
    for name in ("header_chrome", "bottom_chrome"):
        record = assets[name]["edge_defringe"]
        assert record["edge_band_px"] == 8
        assert record["magenta_dominant_partial_pixels_before"] > 0
        assert record["recolored_pixels"] == record[
            "magenta_dominant_partial_pixels_before"
        ]
        assert record["magenta_dominant_partial_pixels_after"] == 0


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
