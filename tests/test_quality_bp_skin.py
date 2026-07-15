from __future__ import annotations

import importlib.util
import json
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
MOD = ROOT / "mods" / "lol_mod"
PACKER_PATH = MOD / "tools" / "pack_quality_bp_skin.py"
LAYOUT_DIR = MOD / "ui" / "layout" / "banpick"


def load_packer():
    spec = importlib.util.spec_from_file_location("quality_bp_skin_packer", PACKER_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def read_layout(name: str) -> str:
    return (LAYOUT_DIR / f"{name}.ui").read_text(encoding="utf-8")


def test_bp_0_5_1_overrides_restore_exact_recorded_native_hashes() -> None:
    packer = load_packer()
    layout = read_layout("layout")
    blue = read_layout("blue_pick_slot")
    red = read_layout("red_pick_slot")
    champion = read_layout("champion_slot")

    assert packer.restored_native_layout_hash(layout) == (
        packer.NATIVE_LAYOUT_NORMALIZED_SHA256
    )
    assert packer.restored_native_pick_slot_hash(blue) == (
        packer.NATIVE_BLUE_PICK_SLOT_NORMALIZED_SHA256
    )
    assert packer.restored_native_pick_slot_hash(red) == (
        packer.NATIVE_RED_PICK_SLOT_NORMALIZED_SHA256
    )
    assert packer.restored_native_champion_slot_hash(champion) == (
        packer.NATIVE_CHAMPION_SLOT_NORMALIZED_SHA256
    )

    # Local/runtime QA additionally proves the checked-in baseline against the
    # current proprietary bundle.  CI without the game install still checks
    # the pinned 0.5.1 normalized hashes above.
    try:
        bundle = packer.find_bundle_path()
    except FileNotFoundError:
        bundle = None
    if bundle is not None:
        native, records = packer.read_native_bp_layouts(bundle)
        assert packer.restored_native_layout(layout) == native["layout"]
        assert packer._strip_exact_blocks(
            blue, (packer.LOL_SIDE_PICK_FRAME_BLOCK,)
        ) == native["blue_pick_slot"]
        assert packer._strip_exact_blocks(
            red, (packer.LOL_SIDE_PICK_FRAME_BLOCK,)
        ) == native["red_pick_slot"]
        assert packer._strip_exact_blocks(
            champion, (packer.LOL_CHAMPION_FRAME_BLOCK,)
        ) == native["champion_slot"]
        assert records["layout"]["normalized_sha256"] == (
            packer.NATIVE_LAYOUT_NORMALIZED_SHA256
        )


def test_bp_0_5_1_required_runtime_nodes_and_types_are_preserved() -> None:
    layout = read_layout("layout")
    blue = read_layout("blue_pick_slot")
    red = read_layout("red_pick_slot")
    champion = read_layout("champion_slot")

    assert "#champion_pool_wait_overlay:color" in layout
    for text_key in ("stat.skill", "stat.skill2", "stat.ult"):
        assert f'#asset/base/text/champion?{text_key}' in layout
    assert "#stat:empty" in layout
    assert "#stat:color" not in layout
    assert "#timer_bar_bg:color" in layout
    assert "#timer_bar_bg:image" not in layout
    for slot in (blue, red):
        assert "#turn_outline:color" in slot
        assert "width: 8px;" in slot
        assert slot.index("#lol_bp_side_pick_frame:image") < slot.index(
            "#turn_outline:color"
        )
    assert "width: 132.4444px;\n  height: 130px;" in champion
    assert "#icon:canvas {\n    width: 131.4444px;\n    height: 88px;" in champion


def test_bp_0_5_1_native_geometry_is_not_rolled_back() -> None:
    layout = read_layout("layout")

    for marker in (
        "#header:color {\n    color: #161721ff;\n    width: 100%;\n    height: 50px;",
        "#bottom:color {\n    color: #161721ff;\n\n    width: 100%;\n    height: 100px;",
        "#blue_picks:empty {\n    y: 60px;\n\n    width: 300px;\n    height: 910px;",
        "#champions_bg:color {\n    width: 1300px;\n    height: 570px;",
        "#champion_info:empty {\n    width: 1300px;\n    height: 280px;",
        "#skill1:color {\n      width: 427px;\n      height: 200px;",
        "#skill2:color {\n      width: 426px;\n      height: 200px;",
        "#ult:color {\n      width: 427px;\n      height: 200px;",
        "#swap:empty {\n    width: 1300px;\n    height: 910px;",
    ):
        assert marker in layout


def test_bp_decorations_are_ignore_event_only_and_keep_native_controls() -> None:
    layout = read_layout("layout")
    champion = read_layout("champion_slot")
    blue = read_layout("blue_pick_slot")
    red = read_layout("red_pick_slot")

    for node, text, expected_count in (
        ("lol_bp_background", layout, 1),
        ("lol_bp_header_chrome", layout, 1),
        ("lol_bp_bottom_chrome", layout, 1),
        ("lol_bp_filter_toolbar", layout, 1),
        ("lol_bp_champion_grid_frame", layout, 1),
        ("lol_bp_stat_frame", layout, 1),
        ("lol_bp_skill_frame", layout, 3),
        ("lol_bp_timer_plate", layout, 1),
        ("lol_bp_timer_icon", layout, 1),
        ("lol_bp_champion_card_frame", champion, 1),
        ("lol_bp_side_pick_frame", blue, 1),
        ("lol_bp_side_pick_frame", red, 1),
    ):
        marker = f"#{node}:image"
        assert text.count(marker) == expected_count
        for suffix in text.split(marker)[1:]:
            assert "ignore_event: true;" in suffix.split("}", 1)[0]

    assert "asset/lol_mod/style/bp_controls" not in layout
    assert layout.index("#timer_bar_bg:color") < layout.index(
        "#lol_bp_timer_plate:image"
    ) < layout.index("#timer_bar:color")
    assert layout.index("#champions:scroll_view") < layout.index(
        "#champion_pool_wait_overlay:color"
    ) < layout.index("#champion_info:empty")


def test_bp_0_5_1_component_assets_have_compatible_dimensions_and_alpha() -> None:
    qa = json.loads(
        (MOD / "qa" / "quality_bp_skin_imagegen_pack.json").read_text(
            encoding="utf-8"
        )
    )
    expected = {
        "header_chrome": (1920, 50),
        "bottom_chrome": (1920, 100),
        "champion_card_frame": (132, 130),
        "filter_toolbar": (1310, 50),
        "champion_grid_frame": (1300, 570),
        "stat_frame": (1300, 70),
        "skill_frame": (427, 200),
        "side_pick_frame": (300, 174),
    }
    for name, size in expected.items():
        record = qa["components"]["imagegen_assets"][name]["runtime"]
        assert tuple(record["dimensions"]) == size
        with Image.open(MOD / record["path"]) as image:
            assert image.size == size
            assert image.mode == "RGBA"
            assert image.getchannel("A").getextrema()[0] == 0
    assert qa["timer_assets"]["plate"]["runtime"]["dimensions"] == [220, 20]
    assert qa["timer_assets"]["icon"]["runtime"]["dimensions"] == [20, 20]
    assert qa["components"]["contact_sheet"]["dimensions"] == [1200, 800]


def test_bp_0_5_1_qa_and_override_contract() -> None:
    qa = json.loads(
        (MOD / "qa" / "quality_bp_skin_imagegen_pack.json").read_text(
            encoding="utf-8"
        )
    )
    override = json.loads((MOD / "mod.override_info").read_text(encoding="utf-8"))

    assert qa["schema"] == "lol_mod.quality_bp_skin_imagegen_pack.v1"
    assert qa["native_bundle"]["base_version"] == "0.5.1"
    assert all(qa["static_checks"].values())
    assert all(qa["geometry_contract"].values())
    assert qa["layout"]["restored_native_sha256"] == qa["layout"][
        "native_baseline_normalized_sha256"
    ]
    for name in ("blue_pick_slot", "red_pick_slot", "champion_slot"):
        record = qa["components"][name]
        assert record["restored_native_sha256"] == record[
            "native_baseline_normalized_sha256"
        ]

    side_geometry = qa["components"]["side_pick_runtime_geometry"]
    assert side_geometry["pick_list"]["slot_top_formula"] == (
        "60 + 184 * slot_index"
    )
    assert side_geometry["native_actor"]["global_top_formula"] == (
        "50 + 184 * slot_index"
    )
    assert side_geometry["dynamic_splash"]["command_y_formula"] == (
        "61 + 184 * slot_index"
    )
    assert side_geometry["dynamic_splash"][
        "rewrite_bp_render_commands_requires_0_5_1_anchor_update"
    ] is True

    for asset_key in (
        "asset/base/ui/layout/banpick/layout",
        "asset/base/ui/layout/banpick/blue_pick_slot",
        "asset/base/ui/layout/banpick/red_pick_slot",
        "asset/base/ui/layout/banpick/champion_slot",
    ):
        assert override[asset_key] == {
            "remapping": asset_key.replace("asset/base/", "asset/lol_mod/", 1),
            "type": "override",
        }


def test_quality_builder_rebuilds_bp_from_the_current_bundle() -> None:
    packer_source = PACKER_PATH.read_text(encoding="utf-8")
    builder_source = (MOD / "tools" / "build_lol_mod.py").read_text(encoding="utf-8")

    assert "read_native_bp_layouts" in packer_source
    assert "bundle.game_data" in packer_source
    assert "restores_exact_native" in packer_source
    assert '"pack_quality_bp_skin.py"' in builder_source
