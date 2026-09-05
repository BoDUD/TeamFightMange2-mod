from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest
from PIL import Image


REPO = Path(__file__).resolve().parents[1]
MOD = REPO / "mods" / "lol_mod"
BUILDER = MOD / "tools" / "build_urgot.py"
NATIVE_CONTRACT = MOD / "source" / "native" / "demon_actor_contract.json"
ACCEPTED_URGOT_COMPACT_SHA256 = (
    "ccf00544d2cdd12e8683b5cd95b1a7573d73ebc973fc69d59f26ce95dde2dc7d"
)

EFFECT_TAGS = {
    "urgot_attack": {"muzzle", "projectile", "impact"},
    "urgot_w_cannon": {"projectile", "impact"},
    "urgot_e_disdain": {"shield", "dash", "impact", "flip"},
    "urgot_r_chain": {"launch", "projectile", "latch", "pull"},
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


def test_urgot_builder_emits_manifest_stable_lf_json() -> None:
    generated_json = [
        MOD / "aseprite_resources/champions/demon#anim.fanim",
        *(MOD / "aseprite_resources/effects" / f"{name}#anim.fanim" for name in EFFECT_TAGS),
        MOD / "qa/urgot_visual_qa.json",
    ]
    for path in generated_json:
        assert b"\r" not in path.read_bytes(), f"{path.name} must use canonical LF"


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
            assert bottom == 53, f"{tag}[{index}] baseline drift"
            assert bottom - frame.height // 2 <= 21, (
                f"{tag}[{index}] extends below the native Demon foot anchor"
            )
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


def test_w_uses_firing_body_pose_and_e_keeps_stable_dash_body() -> None:
    sheet = Image.open(MOD / "aseprite_resources/champions/demon#sheet.png").convert(
        "RGBA"
    )
    anims = load_json("aseprite_resources/champions/demon#anim.fanim")["anims"]

    def first_hash(tag: str) -> str:
        frame = crop_anim_frame(sheet, anims[tag]["frames"][0])
        return hashlib.sha256(frame.tobytes()).hexdigest()

    def sequence_hashes(tag: str) -> list[str]:
        return [
            hashlib.sha256(crop_anim_frame(sheet, row).tobytes()).hexdigest()
            for row in anims[tag]["frames"]
        ]

    # W is the engine skill/skill1 slot and must visibly fire its cannon.
    assert first_hash("skill1") == first_hash("attack")
    # E is the appended skill2 slot and begins from the stable dash body.
    assert first_hash("skill2") == first_hash("normal")
    assert first_hash("skill1") != first_hash("skill2")
    assert sequence_hashes("skill1") != sequence_hashes("attack")
    assert sequence_hashes("ult") != sequence_hashes("idle")


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


def test_w_visual_is_only_compact_warm_rounds_and_contact_sparks() -> None:
    anims = load_json("aseprite_resources/effects/urgot_w_cannon#anim.fanim")[
        "anims"
    ]
    assert set(anims) == {"projectile", "impact"}
    sheet = Image.open(
        MOD / "aseprite_resources/effects/urgot_w_cannon#sheet.png"
    ).convert("RGBA")
    assert sheet.size == (64 * 8, 40)

    for row in anims["projectile"]["frames"]:
        frame = crop_anim_frame(sheet, row)
        bbox = alpha_bbox(frame)
        assert bbox is not None
        width, height = bbox[2] - bbox[0], bbox[3] - bbox[1]
        assert width <= 30 and height <= 14
        visible = [pixel for pixel in pixel_data(frame) if pixel[3] > 0]
        cyan = sum(
            green >= 80
            and blue >= 80
            and blue > red * 1.15
            and green > red * 1.15
            for red, green, blue, _alpha in visible
        )
        assert cyan / len(visible) <= 0.01

    for row in anims["impact"]["frames"]:
        frame = crop_anim_frame(sheet, row)
        bbox = alpha_bbox(frame)
        assert bbox is not None
        width, height = bbox[2] - bbox[0], bbox[3] - bbox[1]
        assert width <= 34 and height <= 28


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
    # Compact and scoreboard intentionally share one approved head/shoulders
    # asset contract; encyclopedia and BP grid remain dedicated surfaces.
    assert len(hashes) == 3


def test_compact_and_scoreboard_crops_keep_urgots_face_readable_at_runtime_sizes() -> None:
    def upper_highlight_count(path: Path, size: int) -> int:
        image = Image.open(path).convert("RGBA").resize(
            (size, size), Image.Resampling.NEAREST
        )
        upper = image.crop((0, 0, size, size // 2))
        return sum(
            alpha > 0 and max(red, green, blue) >= 112
            for red, green, blue, alpha in pixel_data(upper)
        )

    compact = MOD / "ui/champion_portrait/demon_compact.png"
    scoreboard = MOD / "ui/champion_portrait/demon_scoreboard.png"
    assert upper_highlight_count(compact, 40) >= 80
    # The smallest routed scoreboard icon must retain a lit face without
    # reverting to the rejected face-only zoom.  Sixteen highlights are still
    # readable at 18px; the normalized head/shoulders guard below enforces the
    # wider composition seen in the accepted battle sidebar.
    assert upper_highlight_count(scoreboard, 18) >= 16


def test_match_scoreboard_matches_battle_sidebar_head_shoulders_without_changing_compact() -> None:
    compact = MOD / "ui/champion_portrait/demon_compact.png"
    scoreboard = MOD / "ui/champion_portrait/demon_scoreboard.png"

    # Screenshot 2's battle-sidebar crop is the accepted reference surface.
    # This hard pin prevents a scoreboard-only repair from silently changing it.
    assert file_hash(compact) == ACCEPTED_URGOT_COMPACT_SHA256
    assert file_hash(scoreboard) == ACCEPTED_URGOT_COMPACT_SHA256

    def normalized_subject_size(path: Path, runtime_size: int) -> tuple[float, float]:
        runtime = Image.open(path).convert("RGBA").resize(
            (runtime_size, runtime_size), Image.Resampling.NEAREST
        )
        bbox = alpha_bbox(runtime)
        assert bbox is not None
        return (
            (bbox[2] - bbox[0]) / runtime_size,
            (bbox[3] - bbox[1]) / runtime_size,
        )

    # The user's 1920px battle surface renders these commands at 30px and
    # 40px respectively. Compare the real surfaces, not the old 26/46 proxy.
    scoreboard_ratio = normalized_subject_size(scoreboard, 30)
    sidebar_ratio = normalized_subject_size(compact, 40)
    assert abs(scoreboard_ratio[0] - sidebar_ratio[0]) <= 0.02
    assert abs(scoreboard_ratio[1] - sidebar_ratio[1]) <= 0.02

    runtime = (MOD / "src/lib.rs").read_text(encoding="utf-8")
    assert "let is_scoreboard_square = (14.0..=38.0).contains(w);" in runtime
    assert "let is_compact_square = (39.0..=52.0).contains(w);" in runtime
    assert re.search(
        r"let replacement = if is_scoreboard_square \{\s*scoreboard\s*"
        r"\} else if is_compact_square \{\s*compact",
        runtime,
    )


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
    assert qa["actor_contract"]["foot_baseline_exclusive_y"] == 53
    assert set(qa["effects"]) == set(EFFECT_TAGS)
    assert qa["portrait_focus"] == {
        "compact": {"left": 0.34, "top": 0.01, "right": 0.66, "bottom": 0.39},
        "scoreboard": {"left": 0.34, "top": 0.01, "right": 0.66, "bottom": 0.39},
    }
    assert qa["portrait_surface_routing"] == {
        "screenshot_1_match_scoreboard": {
            "runtime_square_px": [14, 38],
            "asset": "ui/champion_portrait/demon_scoreboard.png",
            "crop_contract": "same_head_shoulders_focus_as_battle_sidebar",
        },
        "screenshot_2_battle_sidebar": {
            "runtime_square_px": [39, 52],
            "asset": "ui/champion_portrait/demon_compact.png",
            "preserved_sha256": ACCEPTED_URGOT_COMPACT_SHA256,
        },
    }
    assert qa["portrait_contact_actual_sizes"] == {
        "encyclopedia": [64, 64],
        "compact_40": [40, 40],
        "compact_46": [46, 46],
        "scoreboard_18": [18, 18],
        "scoreboard_26": [26, 26],
        "scoreboard_30": [30, 30],
        "scoreboard_34": [34, 34],
        "bp_grid": [90, 122],
    }
    assert qa["portrait_runtime_metrics"] == {
        "compact_40": {
            "asset": "ui/champion_portrait/demon_compact.png",
            "runtime_size": [40, 40],
            "alpha_bbox": [4, 5, 35, 36],
            "subject_size": [31, 31],
        },
        "scoreboard_30": {
            "asset": "ui/champion_portrait/demon_scoreboard.png",
            "runtime_size": [30, 30],
            "alpha_bbox": [3, 4, 26, 27],
            "subject_size": [23, 23],
        },
    }
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


def test_urgot_visuals_are_wired_into_the_full_builder_and_every_ui_surface() -> None:
    builder = (MOD / "tools/build_lol_mod.py").read_text(encoding="utf-8")
    assert "from build_urgot import build_all as build_urgot_assets" in builder
    assert "urgot_outputs = build_urgot_assets()" in builder
    assert "*urgot_outputs" in builder

    runtime = (MOD / "src/lib.rs").read_text(encoding="utf-8")
    assert '("demon", "asset/lol_mod/BanPickIllust/demon")' in runtime
    assert '"urgot" | "demon" => Some("demon")' in runtime
    assert '("demon", "lol_fullbody_urgot")' in runtime
    for asset in ("demon_compact", "demon_scoreboard", "demon_grid"):
        assert f"asset/lol_mod/ui/champion_portrait/{asset}" in runtime

    overrides = load_json("mod.override_info")
    assert "asset/base/ui/layout/champion_info_component/champion_slot" not in overrides
    manifest_paths = {row["path"] for row in load_json("runtime_manifest.json")["files"]}
    assert not any(path.startswith("ui/champion_fullbody/") for path in manifest_paths)
    assert not any(path.startswith("ui/layout/champion_info_component/") for path in manifest_paths)
    stable_runtime = (MOD / "src/stable_runtime.rs").read_text(encoding="utf-8")
    assert "sync_encyclopedia" not in stable_runtime
    assert "lol_fullbody_" not in stable_runtime
    assert overrides["asset/base/aseprite_resources/champions/demon#sheet"] == {
        "remapping": "asset/lol_mod/aseprite_resources/champions/demon#sheet",
        "type": "override",
    }
    assert overrides["asset/base/aseprite_resources/champions/demon#anim"] == {
        "remapping": "asset/lol_mod/aseprite_resources/champions/demon#anim",
        "type": "override",
    }
