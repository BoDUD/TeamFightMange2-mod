from __future__ import annotations

import json
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
MOD = ROOT / "mods" / "lol_mod"


MAP_NAMES = (
    "background_5v5",
    "wall_5v5",
    "wall_5v5_front",
    "wall_shadow_5v5",
    "bush_5v5",
    "bush_shadow_5v5",
    "tower_shadow",
    "nexus_shadow",
    "minimap_5v5_bg",
)


def test_quality_map_overrides_only_visual_layers() -> None:
    override = json.loads((MOD / "mod.override_info").read_text(encoding="utf-8"))
    for name in MAP_NAMES:
        key = f"asset/base/aseprite_resources/ingame/5v5/{name}"
        assert override[key] == {
            "remapping": key.replace("asset/base/", "asset/lol_mod/", 1),
            "type": "override",
        }

    # Pathing, collisions, brush mechanics, spawns and objective locations live
    # in map_setting and must remain native. Dynamic minimap markers stay native.
    assert "asset/base/setting/map_setting" not in override
    assert "asset/base/aseprite_resources/ingame/minimap_5v5#sheet" not in override
    assert "asset/base/aseprite_resources/ingame/minimap_5v5#data" not in override


def test_quality_map_imagegen_sources_and_native_masks_are_audited() -> None:
    qa = json.loads(
        (MOD / "qa" / "quality_map_imagegen_pack.json").read_text(encoding="utf-8")
    )
    assert qa["schema"] == "lol_mod.quality_map_imagegen_pack.v1"
    assert qa["imagegen_mode"] == "built-in image generation/editing"
    assert set(qa["sources"]) == {"background", "wall", "bush"}
    assert all((MOD / record["path"]).is_file() for record in qa["sources"].values())
    assert all(qa["mask_checks"].values())
    assert all(qa["static_checks"].values())
    assert qa["contracts"]["collision_and_spawns"].endswith("map_setting")
    assert qa["contracts"]["wall_and_bush_geometry"] == "byte-exact native alpha masks"

    runtime = qa["runtime"]
    assert runtime["background_5v5"]["dimensions"] == [1280, 1280]
    assert runtime["minimap_5v5_bg"]["dimensions"] == [320, 320]
    for name in MAP_NAMES:
        path = MOD / runtime[name]["path"]
        assert path.is_file()
        assert runtime[name]["sha256"]


def test_quality_map_runtime_alpha_footprints_match_native_masks() -> None:
    qa = json.loads(
        (MOD / "qa" / "quality_map_imagegen_pack.json").read_text(encoding="utf-8")
    )
    for name, mask_record in qa["native_alpha_masks"].items():
        with Image.open(MOD / mask_record["path"]) as opened_mask:
            mask = (
                opened_mask.getchannel("A")
                if "A" in opened_mask.getbands()
                else opened_mask.convert("L")
            )
            expected = mask.tobytes()
        with Image.open(MOD / qa["runtime"][name]["path"]) as runtime:
            actual = runtime.convert("RGBA").getchannel("A").tobytes()
        assert actual == expected, name


def test_gromp_is_reduced_without_moving_its_runtime_frame_anchor() -> None:
    qa = json.loads(
        (MOD / "qa" / "quality_small_jungle_imagegen_pack.json").read_text(
            encoding="utf-8"
        )
    )
    gromp = next(record for record in qa["assets"] if record["runtime_asset"] == "mushroom")
    assert gromp["pack"]["max_runtime_visible_envelope"] == [72, 50]
    assert gromp["pack"]["cell_size"] == 97
    assert gromp["pack"]["baseline_exclusive"] == 78
    assert gromp["runtime"]["sheet"]["dimensions"] == [2037, 97]

    assert {name: tag["frame_count"] for name, tag in gromp["runtime"]["tags"].items()} == {
        "idle": 4,
        "dead": 4,
        "attack": 5,
        "run": 8,
    }
    visible_sizes = [
        frame["visible_dimensions"]
        for tag in gromp["runtime"]["tags"].values()
        for frame in tag["frames"]
    ]
    assert max(width for width, _height in visible_sizes) <= 72
    assert max(height for _width, height in visible_sizes) <= 50
    assert all(
        frame["bottom_matches_baseline"] and not frame["touches_cell_edge"]
        for tag in gromp["runtime"]["tags"].values()
        for frame in tag["frames"]
    )


def test_quality_builder_rebuilds_the_map_pack() -> None:
    source = (MOD / "tools" / "build_lol_mod.py").read_text(encoding="utf-8")
    assert '"pack_quality_map.py"' in source
