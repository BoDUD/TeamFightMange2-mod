from __future__ import annotations

import importlib.util
import json
import warnings
from pathlib import Path

from PIL import Image, ImageChops, ImageOps


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


def load_committed_runtime_layers() -> dict[str, Image.Image]:
    """Load a bundle-free fixture for pure compositor tests.

    The runtime layers preserve the official alpha/geometry contract and are
    committed to the mod.  Reapplying a deliberately loud landmark source to
    them is sufficient to prove that the compositor cannot leak outside its
    audited masks; extracting proprietary bundle data is a pack-time concern.
    """

    layers: dict[str, Image.Image] = {}
    for name in MAP_NAMES:
        path = MOD / "aseprite_resources" / "ingame" / "5v5" / f"{name}.png"
        with Image.open(path) as opened:
            layers[name] = opened.convert("RGBA")
    return layers


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
    assert qa["schema"] == "lol_mod.quality_map_imagegen_pack.v3"
    assert qa["imagegen_mode"].endswith("official-mask landmark decals")
    assert set(qa["sources"]) == {"microdetail", "wall_palette", "bush_palette"}
    assert all((MOD / record["path"]).is_file() for record in qa["sources"].values())
    assert set(qa["native_bundle_layers"]) == set(MAP_NAMES)
    assert all(qa["mask_checks"].values())
    assert all(qa["native_alpha_checks"].values())
    assert all(qa["rgb_delta_checks"].values())
    assert all(qa["static_checks"].values())
    assert qa["contracts"]["collision_and_spawns"].endswith("map_setting")
    assert qa["contracts"]["runtime_structure_source"] == "native bundle 5v5 layers only"
    assert qa["contracts"]["wall_and_bush_geometry"].startswith("native RGBA contours")
    assert qa["source_usage"]["microdetail"]["strength"] <= 0.05
    assert not qa["source_usage"]["microdetail"]["spatial_terrain_semantics_copied"]
    assert all(
        not record.get("spatial_pixels_copied", True)
        for name, record in qa["source_usage"].items()
        if name.endswith("palette")
    )

    rejected = qa["rejected_routes"]
    assert len(rejected) == 1 and rejected[0]["status"] == "deleted"
    assert not (MOD / rejected[0]["path"]).exists()

    runtime = qa["runtime"]
    assert runtime["background_5v5"]["dimensions"] == [1280, 1280]
    assert runtime["minimap_5v5_bg"]["dimensions"] == [320, 320]
    for name in MAP_NAMES:
        path = MOD / runtime[name]["path"]
        assert path.is_file()
        assert runtime[name]["sha256"]

    landmarks = qa["landmarks"]
    mask_audit = landmarks["mask_audit"]
    application = landmarks["application"]
    assert mask_audit["coordinate_space"].endswith("xyxy bounds are half-open")
    assert mask_audit["landmark_type_count"] == 9
    assert mask_audit["landmark_instance_count"] == 30
    assert mask_audit["union_nonzero_pixels"] > 0
    assert mask_audit["inter_landmark_overlap_pixels"] == 0
    assert mask_audit["wall_or_bush_overlap_pixels_after_exclusion"] == 0
    assert mask_audit["objective_pit_water_like_overlap_pixels"] == {
        "baron_pit": 0,
        "dragon_pit": 0,
    }
    assert set(mask_audit["inventory"]) == {
        "baron_pit",
        "dragon_pit",
        "jungle_camp_large",
        "jungle_camp_small",
        "tower_pad",
        "blue_nexus_pad",
        "red_nexus_pad",
        "blue_spawn_platform",
        "red_spawn_platform",
    }
    assert len(mask_audit["inventory"]["tower_pad"]["instances"]) == 16
    assert len(mask_audit["inventory"]["jungle_camp_large"]["instances"]) == 4
    assert len(mask_audit["inventory"]["jungle_camp_small"]["instances"]) == 4
    assert mask_audit["inventory"]["baron_pit"]["instances"][0][
        "bbox_xyxy_half_open"
    ] == [336, 352, 528, 544]
    assert mask_audit["inventory"]["dragon_pit"]["instances"][0][
        "bbox_xyxy_half_open"
    ] == [736, 736, 928, 928]
    assert application["sources_expected"] == 9
    assert application["sources_available"] <= application["sources_expected"]
    assert application["changed_pixels_outside_allowed_union"] == 0
    assert application["alpha_preserved"] and application["size_preserved"]
    assert all(
        record["status"] in {"applied", "awaiting_imagegen"}
        for record in application["source_records"].values()
    )
    assert all((MOD / record["path"]).is_file() for record in landmarks["mask_files"].values())
    assert (MOD / landmarks["union_mask"]["path"]).is_file()
    assert (MOD / landmarks["preview"]["path"]).is_file()
    assert (MOD / landmarks["detail_preview"]["path"]).is_file()


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


def test_landmark_compositor_cannot_change_mask_exterior_or_alpha(tmp_path: Path) -> None:
    packer_path = MOD / "tools" / "pack_quality_map.py"
    spec = importlib.util.spec_from_file_location("quality_map_packer_test", packer_path)
    assert spec and spec.loader
    packer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(packer)

    native = load_committed_runtime_layers()
    masks, union, mask_audit = packer.build_landmark_masks(native, persist=False)
    for index, landmark in enumerate(packer.LANDMARK_SPECS.values()):
        # Deliberately loud opaque sources make a one-pixel mask leak easy to detect.
        color = ((53 + index * 37) % 256, (211 - index * 19) % 256, 247, 255)
        Image.new("RGBA", (257, 257), color).save(tmp_path / landmark["source"])

    before = native["background_5v5"].copy()
    after, audit = packer.apply_landmark_overlays(
        before,
        masks,
        union,
        source_root=tmp_path,
    )
    assert audit["sources_available"] == audit["sources_expected"] == 9
    assert audit["changed_pixels"] > 0
    assert audit["changed_pixels_outside_allowed_union"] == 0
    assert audit["alpha_preserved"] and audit["size_preserved"]
    assert mask_audit["inter_landmark_overlap_pixels"] == 0
    assert mask_audit["wall_or_bush_overlap_pixels_after_exclusion"] == 0
    # The committed runtime background already contains the objective decals,
    # whose blue accents can look water-like to the conservative detector.  The
    # official-input water exclusion remains pinned by the committed QA test
    # above; this bundle-free test isolates compositor containment and alpha.

    difference = packer.change_mask(before, after)
    outside = ImageChops.multiply(difference, ImageOps.invert(packer.binary_mask(union)))
    assert outside.getbbox() is None
    assert before.getchannel("A").tobytes() == after.getchannel("A").tobytes()


def test_quality_map_packer_import_does_not_discover_the_local_bundle() -> None:
    source = (MOD / "tools" / "pack_quality_map.py").read_text(encoding="utf-8")
    assert "BUNDLE_PATH = find_bundle_path()" not in source
    assert "bundle_path = require_sources()" in source


def test_quality_map_water_detector_supports_pillow_11(monkeypatch) -> None:
    packer_path = MOD / "tools" / "pack_quality_map.py"
    spec = importlib.util.spec_from_file_location("quality_map_pillow11_test", packer_path)
    assert spec and spec.loader
    packer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(packer)

    # Pillow 11 has getdata() but not the Pillow 12 get_flattened_data() alias.
    monkeypatch.delattr(Image.Image, "get_flattened_data", raising=False)
    source = Image.new("RGBA", (2, 1), (20, 30, 70, 255))
    source.putpixel((1, 0), (70, 70, 70, 255))
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        water = packer.native_water_likeness_mask(source)
    assert water.tobytes() == bytes((255, 0))


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


def test_quality_map_packer_cannot_reintroduce_whole_map_or_tiled_layers() -> None:
    source = (MOD / "tools" / "pack_quality_map.py").read_text(encoding="utf-8")
    assert "tiled_source" not in source
    assert "masked_texture" not in source
    assert "rift_background_5v5_v2_source.png" in source
    assert "REJECTED_WHOLE_MAP_SOURCE.exists()" in source
    assert '"runtime_structure_source": "native bundle 5v5 layers only"' in source
    assert '"changed_pixels_outside_allowed_union"' in source
