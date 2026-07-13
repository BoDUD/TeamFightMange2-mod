from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest
from PIL import Image


REPO = Path(__file__).resolve().parents[1]
MOD = REPO / "mods" / "lol_mod"
BUILDER = MOD / "tools" / "build_urgot.py"
NATIVE_CONTRACT = MOD / "source" / "native" / "demon_actor_contract.json"

EFFECT_TAGS = {
    "urgot_w_cannon": {"muzzle", "projectile", "impact"},
    "urgot_e_disdain": {"shield", "dash", "impact", "flip"},
    "urgot_r_chain": {"projectile", "latch", "pull"},
    "urgot_r_execute": {"execute", "fear"},
}


@pytest.fixture(scope="module", autouse=True)
def rebuild_urgot_visuals() -> None:
    subprocess.run([sys.executable, str(BUILDER)], cwd=REPO, check=True)


def load_json(relative: str) -> dict:
    return json.loads((MOD / relative).read_text(encoding="utf-8"))


def alpha_bbox(image: Image.Image) -> tuple[int, int, int, int] | None:
    return image.convert("RGBA").getchannel("A").getbbox()


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def crop_anim_frame(sheet: Image.Image, row: dict) -> Image.Image:
    data = row["data"]
    x, y, width, height = (
        int(data["x"]),
        int(data["y"]),
        int(data["w"]),
        int(data["h"]),
    )
    return sheet.crop((x, y, x + width, y + height)).convert("RGBA")


def pixel_data(image: Image.Image):
    flattened = getattr(image, "get_flattened_data", None)
    return flattened() if flattened is not None else image.getdata()


def assert_hard_alpha(image: Image.Image) -> None:
    values = set(pixel_data(image.convert("RGBA").getchannel("A")))
    assert values.issubset({0, 255})


def assert_no_chroma_key(image: Image.Image) -> None:
    key_pixels = [
        pixel
        for pixel in pixel_data(image.convert("RGBA"))
        if pixel[3] and pixel[0] < 25 and pixel[1] > 230 and pixel[2] < 25
    ]
    assert not key_pixels


def test_actor_preserves_native_demon_timing_and_appends_skill2() -> None:
    native = json.loads(NATIVE_CONTRACT.read_text(encoding="utf-8"))["anims"]
    output = load_json("aseprite_resources/champions/demon#anim.fanim")["anims"]

    assert list(output) == [*native, "skill2"]
    for tag, native_spec in native.items():
        native_frames = native_spec["frames"]
        output_frames = output[tag]["frames"]
        assert len(output_frames) == len(native_frames)
        assert [row["duration"] for row in output_frames] == [
            row["duration"] for row in native_frames
        ]
        assert all(row["data"]["w"] == 80 for row in output_frames)
        assert all(row["data"]["h"] == 64 for row in output_frames)

    skill2 = output["skill2"]["frames"]
    assert len(skill2) == 6
    assert [row["duration"] for row in skill2] == [0.060000002] * 6
    all_rows = [row for spec in output.values() for row in spec["frames"]]
    assert [row["data"] for row in all_rows] == [
        {"x": index * 80, "y": 0, "w": 80, "h": 64}
        for index in range(len(all_rows))
    ]


def test_actor_frames_are_clean_body_only_and_native_safe() -> None:
    sheet = Image.open(MOD / "aseprite_resources/champions/demon#sheet.png").convert(
        "RGBA"
    )
    anims = load_json("aseprite_resources/champions/demon#anim.fanim")["anims"]
    frame_count = sum(len(spec["frames"]) for spec in anims.values())
    assert sheet.size == (80 * frame_count, 64)
    assert_hard_alpha(sheet)
    assert_no_chroma_key(sheet)

    core_heights: list[int] = []
    for tag, spec in anims.items():
        hashes: set[str] = set()
        for index, row in enumerate(spec["frames"]):
            frame = crop_anim_frame(sheet, row)
            bbox = alpha_bbox(frame)
            if tag == "dead" and index == len(spec["frames"]) - 1:
                assert bbox is None
                continue
            assert bbox is not None, f"{tag}[{index}] is empty"
            left, top, right, bottom = bbox
            assert left >= 1 and right <= frame.width - 1
            assert top >= 1 and bottom <= frame.height - 1
            assert bottom == 60, f"{tag}[{index}] baseline drift"
            if tag in {
                "normal",
                "archfiend_base",
                "idle",
                "archfiend_idle",
                "run",
                "archfiend_run",
                "attack",
                "archfiend_attack",
                "skill1",
                "archfiend_skill1",
                "skill2",
                "ult",
                "archfiend_ult",
                "hit",
                "archfiend_hit",
            }:
                visible_height = bottom - top
                assert 42 <= visible_height <= 48, (
                    f"{tag}[{index}] HD body height {visible_height} is outside 42..48"
                )
                core_heights.append(visible_height)
            hashes.add(hashlib.sha256(frame.tobytes()).hexdigest())
        if tag in {"idle", "run", "attack", "skill1", "skill2"}:
            assert len(hashes) >= 2, f"{tag} collapsed to one static actor frame"
    assert max(core_heights) - min(core_heights) <= 6


def test_uniform_scaling_helper_does_not_stretch_urgot() -> None:
    import importlib.util

    spec = importlib.util.spec_from_file_location("build_urgot_visual", BUILDER)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    source = module.split_grid(
        Image.open(MOD / "source/processed/urgot_actor_contact_v1_alpha.png").convert(
            "RGBA"
        ),
        4,
        3,
    )[0]
    subject = module.source_subject(source)
    packed = module.fit_subject(
        source,
        (64, 64),
        padding=3,
        desired_width=56,
        desired_height=58,
        baseline=60,
    )
    target_bbox = alpha_bbox(packed)
    assert target_bbox is not None
    target_ratio = (target_bbox[2] - target_bbox[0]) / (
        target_bbox[3] - target_bbox[1]
    )
    source_ratio = subject.width / subject.height
    assert abs(target_ratio / source_ratio - 1.0) <= 0.06


@pytest.mark.parametrize("resource,expected_tags", EFFECT_TAGS.items())
def test_wer_effect_resources_have_distinct_clean_tags(
    resource: str, expected_tags: set[str]
) -> None:
    sheet_path = MOD / "aseprite_resources" / "effects" / f"{resource}#sheet.png"
    anim_path = MOD / "aseprite_resources" / "effects" / f"{resource}#anim.fanim"
    assert sheet_path.is_file() and anim_path.is_file()
    sheet = Image.open(sheet_path).convert("RGBA")
    assert_hard_alpha(sheet)
    assert_no_chroma_key(sheet)
    anims = json.loads(anim_path.read_text(encoding="utf-8"))["anims"]
    assert set(anims) == expected_tags

    tag_hashes: dict[str, str] = {}
    for tag, spec in anims.items():
        assert len(spec["frames"]) == 4
        frames = [crop_anim_frame(sheet, row) for row in spec["frames"]]
        for frame in frames:
            bbox = alpha_bbox(frame)
            assert bbox is not None
            left, top, right, bottom = bbox
            assert left >= 4 and top >= 4
            assert right <= frame.width - 4 and bottom <= frame.height - 4
            for point in (
                (0, 0),
                (frame.width - 1, 0),
                (0, frame.height - 1),
                (frame.width - 1, frame.height - 1),
            ):
                assert frame.getpixel(point)[3] == 0
        tag_hashes[tag] = hashlib.sha256(
            b"".join(frame.tobytes() for frame in frames)
        ).hexdigest()
    assert len(set(tag_hashes.values())) == len(tag_hashes)


def test_icons_are_independent_64px_wer_assets() -> None:
    paths = [MOD / "icons" / f"urgot_{slot}.png" for slot in "wer"]
    hashes = set()
    for path in paths:
        image = Image.open(path).convert("RGBA")
        assert image.size == (64, 64)
        assert alpha_bbox(image) == (0, 0, 64, 64)
        assert len(set(pixel_data(image))) >= 48
        assert_no_chroma_key(image)
        hashes.add(file_hash(path))
    assert len(hashes) == 3


def test_bp_splash_and_ui_portraits_use_dedicated_safe_surfaces() -> None:
    splash = Image.open(MOD / "BanPickIllust/demon.png").convert("RGBA")
    assert splash.size == (1420, 860)
    assert alpha_bbox(splash) == (0, 0, 1420, 860)

    paths = {
        "encyclopedia": MOD / "ui/champion_fullbody/demon.png",
        "compact": MOD / "ui/champion_portrait/demon_compact.png",
        "scoreboard": MOD / "ui/champion_portrait/demon_scoreboard.png",
        "grid": MOD / "ui/champion_portrait/demon_grid.png",
    }
    expected_sizes = {
        "encyclopedia": (64, 64),
        "compact": (64, 64),
        "scoreboard": (64, 64),
        "grid": (90, 122),
    }
    hashes = set()
    for surface, path in paths.items():
        image = Image.open(path).convert("RGBA")
        assert image.size == expected_sizes[surface]
        assert_hard_alpha(image)
        assert_no_chroma_key(image)
        bbox = alpha_bbox(image)
        assert bbox is not None
        left, top, right, bottom = bbox
        assert left >= 3 and right <= image.width - 3
        assert top >= 1
        if surface == "grid":
            assert bottom <= 86
            assert image.crop((0, 96, 90, 122)).getchannel("A").getbbox() is None
            assert 96 - bottom >= 10
        else:
            assert bottom <= 60
        hashes.add(file_hash(path))
    assert len(hashes) == 4


def test_visual_qa_records_contract_effects_and_grid_clearance() -> None:
    qa = load_json("qa/urgot_visual_qa.json")
    assert qa["champion"] == "Urgot"
    assert qa["native_id"] == "demon"
    assert qa["actor_contract"]["uniform_xy_scale"] is True
    assert qa["actor_contract"]["body_effects_separated"] is True
    assert qa["actor_contract"]["skill2_appended_frames"] == 6
    assert qa["actor_contract"]["native_rectangles_repacked_for_hd"] is True
    assert qa["actor_contract"]["frame_size"] == [80, 64]
    assert qa["actor_contract"]["visible_body_height_px"] == 46
    assert qa["actor_contract"]["foot_baseline_exclusive_y"] == 60
    assert set(qa["effects"]) == set(EFFECT_TAGS)
    assert qa["bp_grid"] == {
        "name_band_y": 96,
        "max_alpha_bottom": 86,
        "clearance": 10,
    }
    for source_relative, expected_hash in qa["sources"].items():
        assert file_hash(MOD / source_relative) == expected_hash


def test_required_qa_contacts_exist_and_are_nonempty() -> None:
    for name in (
        "urgot_actor_contact_final.png",
        "urgot_vfx_contact_final.png",
        "urgot_skill_icons_final.png",
        "urgot_portrait_surface_final.png",
    ):
        image = Image.open(MOD / "qa" / name).convert("RGBA")
        assert image.width >= 240 and image.height >= 80
        assert alpha_bbox(image) is not None
