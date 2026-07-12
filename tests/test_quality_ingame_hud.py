from __future__ import annotations

import json
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
MOD = ROOT / "mods/lol_mod"


def load_qa() -> dict:
    return json.loads(
        (MOD / "qa/quality_ingame_hud_imagegen_pack.json").read_text(encoding="utf-8")
    )


def test_ingame_hud_is_a_visual_only_safe_component_pack() -> None:
    qa = load_qa()
    override = json.loads((MOD / "mod.override_info").read_text(encoding="utf-8"))
    expected = {
        "player_info",
        "wide_player_info",
        "camera_info",
        "wide_camera_info",
        "kill_log",
        "center_kill",
        "center_notify",
        "player_detail",
        "detail_slot",
        "chat",
    }
    assert qa["schema"] == "lol_mod.quality_ingame_hud_imagegen_pack.v1"
    assert set(qa["layouts"]) == expected
    assert all(qa["static_checks"].values())
    for name in expected:
        key = f"asset/base/ui/layout/ingame_component/{name}"
        assert override[key] == {
            "remapping": f"asset/lol_mod/ui/layout/ingame_component/{name}",
            "type": "override",
        }
        layout = (MOD / f"ui/layout/ingame_component/{name}.ui").read_text(
            encoding="utf-8"
        )
        assert "source/imagegen/" not in layout
        for node in qa["layouts"][name]["overlay_nodes"]:
            block = layout.split(f"#{node}:image", 1)[1].split("}", 1)[0]
            assert "ignore_event: true;" in block
            assert f'source: "asset/lol_mod/ui/ingame/{node}";' in block

    for forbidden in (
        "asset/base/ui/layout/ingame",
        "asset/base/aseprite_resources/ingame/minimap_5v5#sheet",
        "asset/base/aseprite_resources/ingame/minimap_5v5#data",
    ):
        assert forbidden not in override


def test_ingame_hud_exactly_restores_official_layout_contracts() -> None:
    qa = load_qa()
    for name, record in qa["layouts"].items():
        assert record["official_bundle"]["file"] == "bundle.game_data"
        assert record["official_bundle"]["asset_type"] == "ui"
        assert len(record["official_bundle"]["entry_sha256"]) == 64
        assert record["native_node_ids_preserved"] is True
        assert record["restored_native_sha256"] == record[
            "native_baseline_normalized_sha256"
        ], name
        assert record["allowed_changes"] == [
            "ignore_event decorative image child insertion"
        ]


def test_ingame_hud_runtime_assets_are_local_sized_and_translucent() -> None:
    qa = load_qa()
    expected_sizes = {
        "player_info_blue": (412, 40),
        "player_info_red": (352, 40),
        "wide_player_info_blue": (272, 30),
        "wide_player_info_red": (272, 30),
        "camera_info_blue": (449, 60),
        "camera_info_red": (449, 60),
        "wide_camera_info_blue": (300, 60),
        "wide_camera_info_red": (300, 60),
        "player_detail_blue": (393, 40),
        "player_detail_red": (393, 40),
        "kill_log": (130, 48),
        "center_kill": (600, 45),
        "center_notify": (600, 45),
        "detail_slot": (36, 36),
        "chat_icon": (30, 30),
    }
    assert set(qa["runtime_assets"]) == set(expected_sizes)
    for name, size in expected_sizes.items():
        record = qa["runtime_assets"][name]["runtime"]
        assert tuple(record["dimensions"]) == size
        assert record["path"].startswith("ui/ingame/lol_hud_")
        assert "source/imagegen/" not in record["path"]
        path = MOD / record["path"]
        with Image.open(path) as image:
            assert image.size == size
            assert image.mode == "RGBA"
            assert image.getchannel("A").getextrema()[1] < 255
    assert not (MOD / "ui/ingame/lol_hud_chat.png").exists()


def test_chat_skin_does_not_join_or_shift_the_native_left_to_right_flow() -> None:
    chat = (MOD / "ui/layout/ingame_component/chat.ui").read_text(encoding="utf-8")
    assert "child_type: LeftToRight" in chat
    assert "#lol_hud_chat:image" not in chat
    icon_slot = chat.split("#icon_slot:color", 1)[1].split("#text:label", 1)[0]
    assert "#lol_hud_chat_icon:image" in icon_slot
    assert icon_slot.index("#lol_hud_chat_icon:image") < icon_slot.index("#icon:image")


def test_ingame_hud_documents_every_intentionally_skipped_unstable_contract() -> None:
    qa = load_qa()
    skipped = {row["asset_key"]: row["reason"] for row in qa["skipped_contracts"]}
    for key in (
        "asset/base/ui/layout/ingame",
        "asset/base/aseprite_resources/ingame/minimap_5v5#sheet",
        "asset/base/aseprite_resources/ingame/minimap_5v5#data",
        "asset/base/ui/ingame/icon_atlases",
        "runtime/kill_and_notification_logic",
    ):
        assert key in skipped
        assert skipped[key]
    assert qa["contact_sheet"]["dimensions"] == [1200, 700]
    assert (MOD / qa["contact_sheet"]["path"]).is_file()


def test_quality_build_and_manifest_cover_the_ingame_hud() -> None:
    builder = (MOD / "tools/build_lol_mod.py").read_text(encoding="utf-8")
    manifest = json.loads((MOD / "build_manifest.json").read_text(encoding="utf-8"))
    paths = {row["path"] for row in manifest["files"]}
    qa = load_qa()
    assert '"pack_quality_ingame_hud.py"' in builder
    required = {record["path"] for record in qa["layouts"].values()}
    required |= {
        record["runtime"]["path"] for record in qa["runtime_assets"].values()
    }
    assert required <= paths
