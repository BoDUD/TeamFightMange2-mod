from __future__ import annotations

import json
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
MOD = ROOT / "mods" / "lol_mod"


def load_wolf_qa() -> dict:
    qa = json.loads(
        (MOD / "qa" / "quality_small_jungle_imagegen_pack.json").read_text(
            encoding="utf-8"
        )
    )
    return next(asset for asset in qa["assets"] if asset["runtime_asset"] == "bee")


def test_murk_wolf_uses_one_ground_anchor_without_changing_animation_timing() -> None:
    wolf = load_wolf_qa()
    pack = wolf["pack"]
    motion = wolf["runtime"]["motion_metrics"]

    assert pack["ground_anchor_policy"] == "fixed_runtime_bottom_padding"
    assert pack["fixed_ground_padding_px"] == 2
    assert pack["single_scale_for_all_actions"] > 0
    assert motion["ground_padding_values_px"] == [2]
    assert motion["maximum_ground_padding_delta_px"] == 0
    assert motion["maximum_visible_width_px"] == 40
    assert wolf["runtime"]["motion_contact"]["dimensions"] == [832, 240]
    assert wolf["runtime"]["motion_contact_tag_order"] == [
        "idle",
        "attack",
        "dead",
        "run",
    ]

    native_tags = wolf["native_animation_contract"]["tags"]
    runtime_tags = wolf["runtime"]["tags"]
    assert set(runtime_tags) == set(native_tags) == {"idle", "run", "attack", "dead"}
    for tag, native in native_tags.items():
        runtime = runtime_tags[tag]
        assert runtime["frame_count"] == native["frame_count"]
        assert runtime["durations"] == native["durations"]
        assert all(frame["ground_padding_matches_target"] for frame in runtime["frames"])
        assert {frame["ground_padding_px"] for frame in runtime["frames"]} == {2}


def test_murk_wolf_runtime_pixels_match_the_recorded_two_pixel_ground_padding() -> None:
    wolf = load_wolf_qa()
    sheet_path = MOD / wolf["runtime"]["sheet"]["path"]
    anim_path = MOD / wolf["runtime"]["animation"]["path"]
    document = json.loads(anim_path.read_text(encoding="utf-8"))

    widths: list[int] = []
    ground_paddings: list[int] = []
    with Image.open(sheet_path) as opened:
        sheet = opened.convert("RGBA")
        for animation in document["anims"].values():
            for frame in animation["frames"]:
                data = frame["data"]
                x = int(data["x"])
                y = int(data["y"])
                width = int(data["w"])
                height = int(data["h"])
                bbox = sheet.crop((x, y, x + width, y + height)).getchannel("A").getbbox()
                assert bbox is not None
                widths.append(bbox[2] - bbox[0])
                ground_paddings.append(height - bbox[3])

    assert sheet.size == (1150, 54)
    assert min(widths) > 0
    assert 39 <= max(widths) <= 40
    assert set(ground_paddings) == {2}


def test_murk_wolf_packer_documents_the_airborne_bee_regression() -> None:
    source = (MOD / "tools" / "pack_quality_small_jungle.py").read_text(
        encoding="utf-8"
    )
    assert "ground_padding=2" in source
    assert "airborne bee contract's 2/5/10px hover gaps" in source
