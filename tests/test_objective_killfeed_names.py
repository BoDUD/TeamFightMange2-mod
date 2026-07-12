from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MOD = ROOT / "mods" / "lol_mod"


def test_objective_ui_text_replaces_native_names_in_all_maintained_locales() -> None:
    text = json.loads((MOD / "text" / "ui.i18n").read_text(encoding="utf-8"))
    expected = {
        "en": ("Baron Nashor", "Infernal Drake"),
        "ko": ("내셔 남작", "화염의 드래곤"),
        "ja": ("バロンナッシャー", "インファーナルドレイク"),
        "zh-hans": ("纳什男爵", "炼狱亚龙"),
        "zh-hant": ("巴龍納什", "赤燄飛龍"),
    }
    for locale, (baron, dragon) in expected.items():
        section = text[locale]
        values = [
            section["match"]["log"][key]
            for key in ("red_epic", "blue_epic", "red_serpen", "blue_serpen")
        ]
        values += [section["ingame"][key] for key in ("epic", "serpen")]
        values += [
            section["set_result"][key]
            for key in (
                "epic",
                "serpen",
                "graph_blue_epic",
                "graph_red_epic",
                "graph_blue_serpen",
                "graph_red_serpen",
            )
        ]
        assert len(values) == 12
        assert sum(baron in value for value in values) == 6
        assert sum(dragon in value for value in values) == 6
        assert not any(
            legacy in value
            for value in values
            for legacy in ("Morgard", "Serpen", "莫尔加德", "双角巨蛇")
        )


def test_objective_ui_text_is_merged_and_dragon_name_tracks_the_seeded_model() -> None:
    override = json.loads((MOD / "mod.override_info").read_text(encoding="utf-8"))
    assert override["asset/base/text/ui"] == {
        "remapping": "asset/lol_mod/text/ui",
        "type": "merge",
    }

    source = (MOD / "src" / "lib.rs").read_text(encoding="utf-8")
    assert "rewrite_objective_render_text(ui, state)" in source
    assert "RenderCommand::Text { text, .. }" in source
    assert "ui_tree_has_match_runner(&ui.root)" in source
    assert "current_dragon_variant_index" in source
    assert ".active_selection" in source
    assert "current_dragon_selection()" in source
    assert "dragon_variant_index(selection.seed)" in source
    for name in (
        "Infernal Drake",
        "Ocean Drake",
        "Mountain Drake",
        "Cloud Drake",
        "Hextech Drake",
        "炼狱亚龙",
        "海洋亚龙",
        "山脉亚龙",
        "云端亚龙",
        "海克斯科技亚龙",
    ):
        assert name in source


def test_objective_ui_text_is_part_of_the_built_manifest() -> None:
    manifest = json.loads((MOD / "build_manifest.json").read_text(encoding="utf-8"))
    paths = {entry["path"] for entry in manifest["files"]}
    assert "text/ui.i18n" in paths
