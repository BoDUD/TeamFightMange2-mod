from __future__ import annotations

import importlib.util
import hashlib
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

SURFACE_ALPHA_CONTRACTS = {
    "wall_5v5": {
        "dimensions": (1280, 1280),
        "nontransparent_pixels": 291274,
        "bbox_xyxy_half_open": (0, 103, 1280, 1152),
    },
    "wall_5v5_front": {
        "dimensions": (1280, 1280),
        "nontransparent_pixels": 56022,
        "bbox_xyxy_half_open": (0, 1113, 1280, 1170),
    },
    "bush_5v5": {
        "dimensions": (1280, 1280),
        "nontransparent_pixels": 62287,
        "bbox_xyxy_half_open": (160, 160, 1120, 1120),
    },
}

OFFICIAL_SHADOW_RGBA_SHA256 = {
    "wall_shadow_5v5": "85c8719c5d65ef25467adbdc615c97014f28151ced34878db69c53b8324d8f52",
    "bush_shadow_5v5": "63eaec2162170c9316700bd988e78972d37948cbfd52132efdb54d32308a7b25",
    "tower_shadow": "8943beb4a06f650f36d6a558f9b425aaaf104745cdb69a9c3b8bcf222ed45fbd",
    "nexus_shadow": "db3dc507c336a45400494fbb89061b1382eb8e4f8256b3b60d4310cca6672829",
}


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
    assert qa["schema"] == "lol_mod.quality_map_imagegen_pack.v4"
    assert qa["imagegen_mode"].endswith("official-mask landmark decals")
    assert set(qa["sources"]) == {
        "microdetail",
        "wall_masonry",
        "cliff_microdetail",
        "bush_microdetail",
    }
    assert all((MOD / record["path"]).is_file() for record in qa["sources"].values())
    assert {
        name: qa["sources"][name]["imagegen_exec_id"]
        for name in ("wall_masonry", "cliff_microdetail", "bush_microdetail")
    } == {
        "wall_masonry": "exec-b126d077-ca6f-4580-845c-85e54c299ad7",
        "cliff_microdetail": "exec-314b7938-4a24-46ba-aea4-fb476c3c8329",
        "bush_microdetail": "exec-d8c82ac3-7568-41bb-973a-304bb910f23b",
    }
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
    surface_usage = {
        name: qa["source_usage"][name]
        for name in (
            "wall_main_masonry",
            "wall_outer_cliff",
            "wall_front_masonry",
            "bush_microdetail",
        )
    }
    assert all(
        record["operation"] == "high-frequency-luminance-only"
        and record["direct_source_pixels_copied"] is False
        and record["source_sha256"]
        and record["changed_pixels"] > 0
        and record["alpha_byte_identical"]
        and record["transparent_rgba_byte_identical"]
        for record in surface_usage.values()
    )
    assert surface_usage["wall_main_masonry"]["strength"] <= 0.08
    assert surface_usage["wall_outer_cliff"]["strength"] <= 0.10
    assert surface_usage["wall_front_masonry"]["strength"] <= 0.08
    assert surface_usage["bush_microdetail"]["strength"] <= 0.08

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


def test_quality_map_surface_microdetail_keeps_official_geometry_and_transparency() -> None:
    qa = json.loads(
        (MOD / "qa" / "quality_map_imagegen_pack.json").read_text(encoding="utf-8")
    )
    for name, contract in SURFACE_ALPHA_CONTRACTS.items():
        runtime_path = MOD / qa["runtime"][name]["path"]
        with Image.open(runtime_path) as opened:
            runtime = opened.convert("RGBA")
        alpha = runtime.getchannel("A")
        histogram = alpha.histogram()
        assert runtime.size == contract["dimensions"]
        assert sum(histogram[1:]) == contract["nontransparent_pixels"]
        assert alpha.getbbox() == contract["bbox_xyxy_half_open"]

        # Official transparent pixels are RGBA (0,0,0,0).  Multiplying each
        # runtime RGB channel by the fully-transparent selector must therefore
        # remain empty, which catches hidden RGB contamination behind alpha 0.
        transparent = alpha.point(lambda value: 255 if value == 0 else 0)
        for channel in runtime.convert("RGB").split():
            assert ImageChops.multiply(channel, transparent).getbbox() is None

        report = qa["surface_detail"]["layers"][name]
        assert report["dimensions_1280"]
        assert report["alpha_byte_identical"]
        assert report["transparent_rgba_byte_identical"]
        assert report["nontransparent_count_identical"]
        assert report["nontransparent_bbox_identical"]
        assert report["native_footprint"] == report["runtime_footprint"]
        assert 0.25 <= report["changed_nontransparent_ratio"] <= 1.0
        assert report["changed_pixels_from_official"] > 0
        assert 0.0 < max(report["visible_mean_abs_rgb_from_official"]) <= 1.0


def test_quality_map_shadow_rgba_sha_is_official() -> None:
    qa = json.loads(
        (MOD / "qa" / "quality_map_imagegen_pack.json").read_text(encoding="utf-8")
    )
    reported = qa["surface_detail"]["shadow_rgba_sha256"]
    for name, expected_sha in OFFICIAL_SHADOW_RGBA_SHA256.items():
        runtime_path = MOD / qa["runtime"][name]["path"]
        with Image.open(runtime_path) as opened:
            actual_sha = hashlib.sha256(opened.convert("RGBA").tobytes()).hexdigest()
        assert actual_sha == expected_sha
        assert reported[name] == {
            "official": expected_sha,
            "runtime": expected_sha,
            "byte_identical": True,
        }


def test_quality_map_surface_preview_uses_requested_one_to_one_crops() -> None:
    qa = json.loads(
        (MOD / "qa" / "quality_map_imagegen_pack.json").read_text(encoding="utf-8")
    )
    preview = qa["surface_detail"]["preview"]
    assert preview["scale"] == "1:1" and preview["resampling"] == "none"
    expected = {
        "left_outer_cliff": ([32, 160, 160, 544], [128, 384]),
        "bush": ([160, 160, 256, 256], [96, 96]),
        "bottom_front_wall": ([384, 1113, 896, 1170], [512, 57]),
    }
    assert set(preview["crops"]) == set(expected)
    for name, (bbox, dimensions) in expected.items():
        record = preview["crops"][name]
        assert record["bbox_xyxy_half_open"] == bbox
        assert record["dimensions"] == dimensions
        assert record["scale"] == "1:1" and record["resampling"] == "none"
        assert record["official_rgba_sha256"] != record["v4_rgba_sha256"]
    preview_path = MOD / preview["path"]
    assert preview_path.is_file()
    assert preview["image"]["sha256"]


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
    assert "apply_contour_microdetail" in source
    assert "ImageFilter.GaussianBlur" in source
    assert "ImageChops.soft_light" in source
    assert "Image.composite(candidate, native, contour)" in source
    assert '"operation": "high-frequency-luminance-only"' in source
