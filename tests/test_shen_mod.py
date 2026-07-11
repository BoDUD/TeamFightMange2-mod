from __future__ import annotations

import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MOD = ROOT / "mods" / "lol_mod"


def load_validator():
    path = MOD / "tools" / "validate_lol_mod.py"
    spec = importlib.util.spec_from_file_location("validate_lol_mod", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_static_validator_passes() -> None:
    validator = load_validator()
    validator.ERRORS.clear()
    assert validator.main() == 0


def test_lucian_replaces_native_archer_002_and_is_localized() -> None:
    shen = json.loads((MOD / "champion" / "lol_shen.data_champion").read_text(encoding="utf-8"))
    lucian = json.loads((MOD / "champion" / "archer.data_champion").read_text(encoding="utf-8"))
    mod_info = json.loads((MOD / "mod.mod_info").read_text(encoding="utf-8"))
    text = json.loads((MOD / "text" / "champion.i18n").read_text(encoding="utf-8"))
    assert shen["id"] == "lol_shen"
    assert lucian["id"] == "archer"
    assert lucian["sprite"] == "asset/lol_mod/aseprite_resources/champions/lucian"
    assert lucian["skill_icons"] == [
        "asset/lol_mod/icons/lucian_skill",
        "asset/lol_mod/icons/lucian_skill2",
        "asset/lol_mod/icons/lucian_ult",
    ]
    assert not (MOD / "champion" / "lol_lucian.data_champion").exists()
    assert mod_info["mod_id"] == "lol_mod"
    assert mod_info["version"] == "0.7.5"
    assert text["zh-hans"]["description"]["archer"]["name"] == "卢锡安"
    assert text["zh-hant"]["description"]["archer"]["name"] == "路西恩"


def test_generated_sources_and_official_audio_are_auditable() -> None:
    shen_imagegen = json.loads((MOD / "qa" / "shen_imagegen_sources.json").read_text(encoding="utf-8"))
    shen_audio = json.loads((MOD / "qa" / "shen_official_audio_sources.json").read_text(encoding="utf-8"))
    lucian_imagegen = json.loads((MOD / "qa" / "lucian_imagegen_sources.json").read_text(encoding="utf-8"))
    lucian_audio = json.loads((MOD / "qa" / "lucian_official_audio_sources.json").read_text(encoding="utf-8"))
    assert len(shen_imagegen["sources"]) == 8
    assert {entry["role"] for entry in shen_imagegen["sources"]} == {
        "actor_model",
        "run_cycle",
        "q_icon",
        "w_icon",
        "r_icon",
        "q_vfx",
        "w_vfx",
        "r_vfx",
    }
    assert len(lucian_imagegen["sources"]) == 8
    assert {entry["role"] for entry in lucian_imagegen["sources"]} == {
        "actor_model",
        "run_cycle",
        "attack_vfx",
        "q_icon",
        "e_icon",
        "r_icon",
        "q_vfx",
        "r_vfx",
    }
    assert len(shen_audio["outputs"]) == 7
    assert len(lucian_audio["outputs"]) == 8
    assert all(entry["volume"] >= 0.85 for entry in [*shen_audio["outputs"], *lucian_audio["outputs"]])


def test_quality_runtime_uses_live_ui_paths_and_seeded_dragon_variants() -> None:
    source = (MOD / "src" / "lib.rs").read_text(encoding="utf-8")
    override = json.loads((MOD / "mod.override_info").read_text(encoding="utf-8"))

    assert "top.right.champion_info.data.champions.contents" in source
    assert "match_ui_database_from_node" in source
    assert "fn post_render(" in source
    assert "rewrite_bp_render_commands(ui, state)" in source
    assert "RenderCommand::NinePatch" in source
    assert 'ui.query("main.blue_picks")' in source
    assert 'ui.query("main.red_picks")' in source
    assert 'let marker = "/champions/"' in source
    assert "source.find(marker)? + marker.len()" in source
    assert '.strip_suffix("#sheet")' in source
    assert "for (pass, commands) in &mut state.commands" in source
    assert ".map_size" in source and ".get(pass)" in source
    assert "map_width - 335.0" in source
    assert '"candidate_skip"' in source
    assert '"asset/lol_mod/BanPickIllust/lol_shen"' in source
    assert not any(
        key.startswith("asset/base/ui/banpick/illust/") for key in override
    )
    assert "splash_id_from_source" in source
    assert "texture_rect.w = 1420.0" in source
    assert "texture_rect.h = 860.0" in source
    assert "original_geometry.1 + 11.0" in source
    assert "*w = 284.0" in source and "*h = 172.0" in source
    assert "*z = 200" in source
    assert "*flip_x = side == BpRenderSide::Red" in source
    assert "done.champion.icon" not in source
    assert "sync_side(" not in source
    assert "quality_bp_runtime_telemetry.tsv" in source

    for filename in ("blue_pick_slot.ui", "red_pick_slot.ui"):
        slot_ui = (MOD / "ui" / "layout" / "banpick" / filename).read_text(
            encoding="utf-8"
        )
        assert "lol_splash_" not in slot_ui
        assert "lol_bp_illustration" not in slot_ui
        assert "#champion:empty" in slot_ui
        assert "width: 137px" in slot_ui and "height: 172px" in slot_ui

    build_script = (MOD / "tools" / "build_native_dll.ps1").read_text(encoding="utf-8")
    assert '"--extern", "engine_ui=$($engineUi.FullName)"' not in build_script
    assert '"--extern", "engine_core=$($engineCore.FullName)"' in build_script

    variants = ["infernal", "ocean", "mountain", "cloud", "hextech"]
    assert "snapshot.seed" in source
    assert "registration.set_server_extension" in source
    assert "dragon_variant_index" in source
    for variant in variants:
        assert f'"dragon_variants/{variant}"' in source
        for suffix in ("sheet", "anim"):
            key = (
                "asset/base/aseprite_resources/ingame/"
                f"dragon_variants/{variant}#{suffix}"
            )
            assert override[key] == {
                "remapping": key.replace("asset/base/", "asset/lol_mod/", 1),
                "type": "override",
            }


def test_override_metadata_uses_registered_sprite_sheet_extension() -> None:
    assert not list(MOD.rglob("*.sprite_data"))
    for relative in (
        "aseprite_resources/ingame/epic_monster_hp_guage#data.sprite_sheet",
        "aseprite_resources/ingame/item_icons_18x18#data.sprite_sheet",
    ):
        assert (MOD / relative).is_file()


def test_lucian_q_locks_an_enemy_unit_and_shares_one_piercing_projectile() -> None:
    lucian = json.loads((MOD / "champion" / "archer.data_champion").read_text(encoding="utf-8"))
    actor_anim = json.loads(
        (MOD / "aseprite_resources" / "champions" / "lucian#anim.fanim").read_text(encoding="utf-8")
    )
    q = lucian["skill"]

    def walk(value):
        if isinstance(value, dict):
            if "type" in value:
                yield value
            for nested in value.values():
                yield from walk(nested)
        elif isinstance(value, list):
            for nested in value:
                yield from walk(nested)

    effects = list(walk(q["effect"]))
    assert q["casting_type"] == "Targeting"
    assert q["casting_target"] == "EnemyWithoutTower"
    assert not [effect for effect in effects if effect["type"] == "Delayed"]
    assert not [effect for effect in effects if effect["type"] == "LineRangeProjectile"]
    assert not [effect for effect in effects if effect["type"] == "TargetProjectile"]
    assert not [effect for effect in effects if effect["type"] == "CasterAnimation"]

    projectiles = [
        effect
        for effect in effects
        if effect["type"] == "LinearProjectile"
        and effect.get("name") == "lol_lucian_q_piercing_light"
    ]
    assert len(projectiles) == 1
    projectile = projectiles[0]
    assert projectile["penetrate"] is True
    assert projectile["speed"] == 16000
    assert projectile["range"] == 76000
    assert projectile["shape"] == {"Circle": {"radius": 10000}}
    assert projectile["applied_target"] == "EnemyWithoutTower"

    q_views = [
        view
        for view in lucian["view_projectiles"]
        if view.get("name") == "lol_lucian_q_piercing_light"
    ]
    assert len(q_views) == 1
    assert q_views[0]["anim"] == "asset/lol_mod/aseprite_resources/effects/lucian_q"
    assert q_views[0]["tag"] == "projectile"
    assert q_views[0]["repeat"] is False
    assert all(
        frame["data"]["w"] == 64
        for frame in actor_anim["anims"]["skill"]["frames"]
    )

    from PIL import Image

    q_sheet = Image.open(MOD / "aseprite_resources" / "effects" / "lucian_q#sheet.png").convert("RGBA")
    assert q_sheet.size == (1536, 32)
    for index in range(8):
        bbox = q_sheet.crop((index * 192, 0, (index + 1) * 192, 32)).getchannel("A").getbbox()
        assert bbox is not None
        assert bbox[0] == 104
        assert 60 <= bbox[2] - bbox[0] <= 80

    actor_sheet = Image.open(MOD / "aseprite_resources" / "champions" / "lucian#sheet.png").convert("RGBA")
    hit_bbox = actor_sheet.crop((19 * 64, 0, 20 * 64, 64)).getchannel("A").getbbox()
    dead_bbox = actor_sheet.crop((20 * 64, 0, 21 * 64, 64)).getchannel("A").getbbox()
    assert hit_bbox is not None and hit_bbox[2] - hit_bbox[0] <= 28
    assert dead_bbox is not None and dead_bbox[2] - dead_bbox[0] <= 40
