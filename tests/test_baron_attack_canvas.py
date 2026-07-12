from __future__ import annotations

import hashlib
import json
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
MOD = ROOT / "mods" / "lol_mod"
QA_PATH = MOD / "qa" / "quality_objectives_imagegen_pack.json"
SHEET_PATH = MOD / "aseprite_resources" / "ingame" / "epic#sheet.png"
ANIM_PATH = MOD / "aseprite_resources" / "ingame" / "epic#anim.fanim"
RUNTIME_SOURCE_PATH = MOD / "src" / "lib.rs"
PACKER_PATH = MOD / "tools" / "pack_quality_objectives.py"

ATTACK_SOURCE_INDICES = [4, 5, 6, 7, 10]
ATTACK_FRAME_WIDTHS = [141, 127, 187, 215, 139]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def frame_rect(frame: dict[str, object]) -> tuple[int, int, int, int]:
    data = frame["data"]
    assert isinstance(data, dict)
    return tuple(int(data[key]) for key in ("x", "y", "w", "h"))


def test_baron_attack_canvas_preserves_timing_and_prevents_clipping() -> None:
    qa = json.loads(QA_PATH.read_text(encoding="utf-8"))
    epic = qa["runtime"]["epic"]
    document = json.loads(ANIM_PATH.read_text(encoding="utf-8"))

    actual_contract = {
        tag_name: {
            "frame_count": len(tag["frames"]),
            "durations": [frame["duration"] for frame in tag["frames"]],
        }
        for tag_name, tag in document["anims"].items()
    }
    assert actual_contract == epic["native_animation_contract"]["tags"]
    assert epic["native_animation_contract_exact"] is True
    assert epic["native_frame_rect_contract_exact"] is False
    assert epic["native_frame_rect_contract_attack_safe_expanded"] is True
    assert epic["non_attack_frame_sizes_match_native"] is True
    assert epic["target_effect_frame_sizes_match_native"] is True

    assert epic["attack_source_indices"] == ATTACK_SOURCE_INDICES
    assert epic["attack_frame_widths"] == ATTACK_FRAME_WIDTHS
    assert epic["maximum_attack_alpha_clip_loss_pixels"] == 0
    assert epic["minimum_attack_side_clearance_px"] >= 2
    assert epic["maximum_attack_anchor_offset_delta_px"] <= 0.75
    assert epic["maximum_attack_bottom_delta_to_native_px"] == 0
    assert epic["minimum_target_effect_frame_clearance_px"] >= 1

    with Image.open(SHEET_PATH) as opened:
        sheet = opened.convert("RGBA")
    assert sheet.size == (4050, 150)
    assert epic["sheet"]["size"] == list(sheet.size)
    assert epic["sheet"]["sha256"] == sha256(SHEET_PATH)

    metrics = epic["attack_frame_metrics"]
    assert len(metrics) == 10
    by_tag = {
        tag: sorted(
            (metric for metric in metrics if metric["tag"] == tag),
            key=lambda metric: metric["frame_index"],
        )
        for tag in ("attack_left", "attack_right")
    }
    for tag_name, tag_metrics in by_tag.items():
        assert [metric["source_index"] for metric in tag_metrics] == ATTACK_SOURCE_INDICES
        frames = document["anims"][tag_name]["frames"]
        assert [frame_rect(frame)[2] for frame in frames] == ATTACK_FRAME_WIDTHS
        for metric, frame in zip(tag_metrics, frames, strict=True):
            x, y, width, height = frame_rect(frame)
            crop = sheet.crop((x, y, x + width, y + height))
            bbox = crop.getchannel("A").getbbox()
            assert bbox is not None
            assert bbox[0] >= 2
            assert width - bbox[2] >= 2
            assert metric["alpha_clip_loss_pixels"] == 0
            assert metric["bottom_delta_to_native_px"] == 0
            assert metric["ground_anchor_offset_delta_px"] <= 0.75


def test_baron_attack_contact_sheet_and_target_layer_are_recorded() -> None:
    qa = json.loads(QA_PATH.read_text(encoding="utf-8"))
    epic = qa["runtime"]["epic"]
    contact_record = epic["attack_contact_sheet"]
    contact_path = MOD / contact_record["path"]

    assert contact_path.is_file()
    assert contact_record["sha256"] == sha256(contact_path)
    with Image.open(contact_path) as opened:
        assert opened.size == (1610, 540)
        assert opened.getchannel("A").getbbox() is not None

    assert len(epic["tag_frame_alpha_bboxes"]["attack_target_effect"]) == 7
    assert all(
        bbox is not None
        for bbox in epic["tag_frame_alpha_bboxes"]["attack_target_effect"]
    )
    assert epic["target_effect_frame_sizes_match_native"] is True


def test_objectives_use_native_actual_target_facing_without_mod_override() -> None:
    qa = json.loads(QA_PATH.read_text(encoding="utf-8"))
    facing = qa["runtime"]["objective_attack_facing"]
    native = facing["native_game_setting"]

    # Epic's second atlas tag is not a simulation direction switch: the
    # bundled game_setting only ever dispatches attack_left. Serpen has one
    # attack tag. Both therefore use the renderer's real action-target flip;
    # a mod-side nearest-enemy approximation is intentionally forbidden.
    assert native["epic_action_name"] == "attack_left"
    assert native["serpen_action_name"] == "attack"
    assert native["epic_attack_right_reachable_from_game_setting"] is False
    assert facing["canonical_art_direction"] == "right"
    assert facing["native_action_flip_method"] == "game_view::GameView::get_action_flip_x"
    assert facing["native_render_consumer"] == "game_view::EntityView::render"
    assert facing["actual_action_target_drives_flip_x"] is True
    assert facing["mod_writes_entity_flip_x"] is False
    assert set(facing["variants"]) == {
        "epic",
        "infernal",
        "ocean",
        "mountain",
        "cloud",
        "hextech",
        "elder",
    }

    epic = qa["runtime"]["epic"]
    assert epic["attack_tags_use_canonical_right_facing_art"] is True
    assert epic["runtime_direction_owned_by_native_action_flip_x"] is True
    for dragon in qa["runtime"]["dragon_variants"].values():
        assert dragon["attack_art_canonical_direction"] == "right"
        assert dragon["runtime_direction_owned_by_native_action_flip_x"] is True

    packer = PACKER_PATH.read_text(encoding="utf-8")
    epic_source_map = packer.split(
        'source_by_tag: dict[str, list[tuple[int, int, bool, str]]] = {', 1
    )[1].split("    sheet =", 1)[0]
    assert epic_source_map.count('(index, 255, False, "ground")') == 2
    assert '(index, 255, True, "ground")' not in epic_source_map

    runtime = RUNTIME_SOURCE_PATH.read_text(encoding="utf-8")
    assert "fn sync_objective_attack_facing()" not in runtime
    assert "sync_objective_attack_facing();" not in runtime
    assert ".nearest_enemy" not in runtime
    assert "entity.flip_x =" not in runtime
