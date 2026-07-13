from __future__ import annotations

import importlib.util
import json
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
MOD = ROOT / "mods" / "lol_mod"


def load_validator():
    path = MOD / "tools" / "validate_lol_mod.py"
    spec = importlib.util.spec_from_file_location("validate_lol_mod_orianna", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def load_json(relative: str):
    return json.loads((MOD / relative).read_text(encoding="utf-8"))


def test_orianna_replaces_native_barrier_magician_003_without_duplicate_or_w() -> None:
    data_files = sorted((MOD / "champion").glob("*.data_champion"))
    champions = [(path.name, json.loads(path.read_text(encoding="utf-8"))) for path in data_files]
    barrier_files = [name for name, champion in champions if champion.get("id") == "barrier_magician"]

    assert barrier_files == ["barrier_magician.data_champion"]
    assert all(champion.get("id") != "lol_orianna" for _, champion in champions)
    assert not (MOD / "champion" / "lol_orianna.data_champion").exists()

    orianna = load_json("champion/barrier_magician.data_champion")
    assert orianna["id"] == "barrier_magician"
    assert orianna["sprite"] == "asset/lol_mod/aseprite_resources/champions/orianna"
    assert orianna["skill_icons"] == [
        "asset/lol_mod/icons/orianna_skill",
        "asset/lol_mod/icons/orianna_skill2",
        "asset/lol_mod/icons/orianna_ult",
    ]
    assert len(orianna["skill_icons"]) == 3
    assert orianna["skill"]["action_name"] == "skill1"
    assert orianna["skill2"]["action_name"] == "skill2"
    assert orianna["ult"]["action_name"] == "ult"
    assert not {"w", "skill3", "skill4"}.intersection(orianna)

    text = load_json("text/champion.i18n")
    assert text["zh-hans"]["description"]["barrier_magician"]["name"] == "奥利安娜"
    assert text["zh-hant"]["description"]["barrier_magician"]["name"] == "奧利安娜"
    assert text["en"]["description"]["barrier_magician"]["name"] == "Orianna"


def test_orianna_q_e_r_data_effect_contract() -> None:
    validator = load_validator()
    orianna = load_json("champion/barrier_magician.data_champion")

    q = orianna["skill"]
    assert (q["range"], q["cooltime"], q["duration"], q["start_timing"]) == (70000, 360, 30, 24)
    q_balls = validator.find_effect(q, "ParabolicProjectile", name="lol_orianna_q_ball")
    assert len(q_balls) == 1
    assert not validator.find_effect(q, "RangeProjectile")
    q_ball = q_balls[0]
    assert (q_ball["travel_time"], q_ball["range"], q_ball["shape"]["Circle"]["radius"]) == (15, 70000, 26000)
    assert q_ball["applied_target"] == "EnemyWithoutTower"
    q_damage = validator.find_effect(q, "ApAttack")
    assert [(effect["damage"], effect["attack_ratio"]) for effect in q_damage] == [(50, 55)]

    fields = validator.find_effect(q, "RangePeriodProjectile")
    assert len(fields) == 2
    fields_by_target = {field["applied_target"]: field for field in fields}
    assert set(fields_by_target) == {"AllyChampion", "EnemyWithoutTower"}
    assert fields_by_target["AllyChampion"]["name"] == "lol_orianna_q_field_visual"
    assert fields_by_target["EnemyWithoutTower"]["name"] == "lol_orianna_q_field_enemy_logic"
    for field in fields:
        assert (field["tick"], field["period"], field["first_delay"], field["shape"]["Circle"]["radius"]) == (
            180,
            30,
            0,
            30000,
        )
        switches = validator.find_effect(field, "SwitchByLevel3")
        assert len(switches) == 1
        assert switches[0]["effect_start"] == {"type": "Combine", "effects": []}

    e = orianna["skill2"]
    assert e["casting_target"] == "AllyChampion"
    assert (e["range"], e["cooltime"], e["duration"], e["start_timing"]) == (70000, 480, 30, 24)
    e_balls = validator.find_effect(e, "TargetProjectile", name="lol_orianna_e_ball")
    assert len(e_balls) == 1
    assert e_balls[0]["applied_target"] == "AllyChampion"
    shields = validator.find_effect(e, "Shield")
    assert [(effect["amount"], effect["ap_ratio"], effect["tick"]) for effect in shields] == [(180, 55, 180)]
    protect = [
        effect
        for effect in validator.find_effect(e, "AddBuff")
        if effect["buff_state"]["name"] == "lol_orianna_protect"
    ]
    assert len(protect) == 1
    assert protect[0]["buff_state"]["duration"] == "WithShield"
    assert protect[0]["buff_state"]["defence"] == 12
    assert protect[0]["buff_state"]["magic_resistance"] == 12

    ult = orianna["ult"]
    r_cores = validator.find_effect(ult, "ParabolicProjectile", name="lol_orianna_r_core")
    assert len(r_cores) == 1
    r_core = r_cores[0]
    assert (
        r_core["travel_time"],
        r_core["range"],
        r_core["shape"]["Circle"]["radius"],
        r_core["applied_target"],
        r_core["applied_effects"],
    ) == (1, 75000, 1, "EnemyChampion", [])
    barriers = [
        effect
        for effect in r_core["end_effects"]
        if effect.get("type") == "ShrinkingBarrier" and effect.get("name") == "lol_orianna_r_ring_logic"
    ]
    assert len(barriers) == 1
    barrier = barriers[0]
    assert (
        barrier["start_radius"],
        barrier["end_radius"],
        barrier["shrink_per_tick"],
        barrier["tick"],
        barrier["edge_thickness"],
    ) == (60000, 18000, 700, 60, 6000)
    assert "barrier_tick" not in barrier

    final_delays = [
        effect
        for effect in r_core["end_effects"]
        if effect.get("type") == "Delayed" and effect.get("tick") == 60
    ]
    assert len(final_delays) == 1
    bursts = [
        effect
        for effect in final_delays[0]["effects"]
        if effect.get("type") == "RangeProjectile" and effect.get("name") == "lol_orianna_r_burst_hitbox"
    ]
    assert len(bursts) == 1
    burst = bursts[0]
    assert (burst["delay"], burst["apply"], burst["shape"]["Circle"]["radius"], burst["applied_target"]) == (
        0,
        1,
        42000,
        "EnemyWithoutTower",
    )
    assert [(effect["speed"], effect["tick"]) for effect in validator.find_effect(burst, "Pull")] == [(3200, 12)]
    assert [effect["duration"] for effect in validator.find_effect(burst, "Airborne")] == [24]
    assert len(validator.find_effect(ult, "Pull")) == 1


def test_orianna_preserves_native_animation_and_packages_every_view_resource() -> None:
    validator = load_validator()
    orianna = load_json("champion/barrier_magician.data_champion")
    anim = load_json("aseprite_resources/champions/orianna#anim.fanim")
    assert set(anim["anims"]) == set(validator.ORIANNA_NATIVE_ANIMATION)
    for tag, expected_durations in validator.ORIANNA_NATIVE_ANIMATION.items():
        frames = anim["anims"][tag]["frames"]
        assert len(frames) == len(expected_durations)
        assert all(abs(float(frame["duration"]) - duration) < 1e-6 for frame, duration in zip(frames, expected_durations))

    projectile_map = {view["name"]: view for view in orianna["view_projectiles"]}
    effect_map = {view["name"]: view for view in orianna["view_effects"]}
    buff_map = {view["name"]: view for view in orianna["view_buffs"]}
    assert set(validator.ORIANNA_VIEW_PROJECTILES) == set(projectile_map)
    assert set(validator.ORIANNA_VIEW_EFFECTS) == set(effect_map)
    assert set(validator.ORIANNA_VIEW_BUFFS) == set(buff_map)
    assert effect_map["lol_orianna_r_ring_visual"]["type"] == "Animation"
    assert effect_map["lol_orianna_r_ring_visual"]["is_follow"] is False
    assert buff_map["lol_orianna_protect"]["type"] == "ThreePhase"
    assert (
        buff_map["lol_orianna_protect"]["pre_tag"],
        buff_map["lol_orianna_protect"]["loop_tag"],
        buff_map["lol_orianna_protect"]["remove_tag"],
    ) == ("impact", "loop", "break")
    assert "lol_orianna_q_field_enemy_logic" not in projectile_map
    assert "lol_orianna_r_ring_logic" not in projectile_map
    assert "lol_orianna_r_burst_hitbox" not in projectile_map

    manifest = load_json("build_manifest.json")
    manifest_paths = {row["path"] for row in manifest["files"]}
    required = {
        "champion/barrier_magician.data_champion",
        "aseprite_resources/champions/orianna#sheet.png",
        "aseprite_resources/champions/orianna#anim.fanim",
        "icons/orianna_skill.png",
        "icons/orianna_skill2.png",
        "icons/orianna_ult.png",
        "ui/champion_fullbody/barrier_magician.png",
        "ui/champion_portrait/barrier_magician_compact.png",
        "ui/champion_portrait/barrier_magician_scoreboard.png",
        "ui/champion_portrait/barrier_magician_grid.png",
    }
    for binding in [*orianna["view_projectiles"], *orianna["view_effects"], *orianna["view_buffs"]]:
        anim_path = binding.get("anim")
        if isinstance(anim_path, str) and anim_path.startswith("asset/lol_mod/"):
            base = anim_path.removeprefix("asset/lol_mod/")
            required.update({f"{base}#sheet.png", f"{base}#anim.fanim"})
    assert required.issubset(manifest_paths)

    validator.ERRORS.clear()
    validator.validate_orianna_replacement_uniqueness()
    validator.validate_orianna_data_contract(orianna)
    validator.validate_orianna_native_animation(orianna)
    validator.validate_orianna_resources_and_manifest(orianna)
    assert validator.ERRORS == []


def test_orianna_v2_actor_face_feet_run_and_attack_dart_visual_gates() -> None:
    validator = load_validator()

    validator.ERRORS.clear()
    validator.validate_orianna_v2_visual_contract()

    assert validator.ERRORS == []


def test_orianna_hd_portraits_are_source_direct_surface_specific_and_bp_safe() -> None:
    surfaces = {
        "encyclopedia": ("ui/champion_fullbody/barrier_magician.png", (64, 64)),
        "sidebar": ("ui/champion_portrait/barrier_magician_compact.png", (64, 64)),
        "scoreboard": (
            "ui/champion_portrait/barrier_magician_scoreboard.png",
            (64, 64),
        ),
        "bp_grid": ("ui/champion_portrait/barrier_magician_grid.png", (90, 122)),
    }
    bboxes: dict[str, tuple[int, int, int, int]] = {}
    for surface, (relative, expected_size) in surfaces.items():
        image = Image.open(MOD / relative).convert("RGBA")
        bbox = image.getchannel("A").getbbox()
        assert image.size == expected_size, surface
        assert bbox is not None, surface
        assert image.getchannel("A").getextrema() == (0, 255), surface
        bboxes[surface] = bbox

    assert bboxes["bp_grid"][3] <= 86
    assert 96 - bboxes["bp_grid"][3] >= 10
    assert bboxes["bp_grid"][1] <= 8
    for surface in ("sidebar", "scoreboard"):
        bbox = bboxes[surface]
        assert bbox[2] - bbox[0] <= 50
        assert bbox[3] - bbox[1] <= 50
        assert min(bbox[0], bbox[1], 64 - bbox[2], 64 - bbox[3]) >= 6
    assert (MOD / surfaces["sidebar"][0]).read_bytes() != (
        MOD / surfaces["scoreboard"][0]
    ).read_bytes()

    qa = load_json("qa/orianna_hd_surface_qa.json")
    assert qa["champion"] == "Orianna"
    assert qa["native_id"] == "barrier_magician"
    assert qa["accepted_source"] == "source/processed/orianna_actor_contact_alpha.png"
    assert qa["battle_actor"]["uniform_xy_scale"] is True
    assert qa["battle_actor"]["x_only_compression"] is False
    assert qa["surfaces"]["bp_grid"]["alpha_bbox"][3] <= 86
    assert qa["surfaces"]["bp_grid"]["name_band_clearance"] >= 10
    assert (MOD / "qa/orianna_portrait_surface_final.png").is_file()

    runtime = (MOD / "src/lib.rs").read_text(encoding="utf-8")
    assert "rewrite_orianna_briar_portrait_render_commands(state);" in runtime
    assert "ORIANNA_SCOREBOARD_PORTRAIT_TEXTURE" in runtime
    assert "ORIANNA_BP_GRID_PORTRAIT_TEXTURE" in runtime


def test_orianna_attack_audio_restores_official_oncast_launch_and_hit_identity() -> None:
    validator = load_validator()
    orianna = load_json("champion/barrier_magician.data_champion")
    override = load_json("mod.override_info")
    attack_cast = load_json("sound/sfx/orianna_attack_cast.sound_info")
    audio_sources = load_json("qa/orianna_official_audio_sources.json")

    assert attack_cast["plays"] == [
        {"delay": 0.0, "clip": "orianna_attack_oncast_clip", "volume": 1.0},
        {"delay": 0.04, "clip": "orianna_attack_cast_clip", "volume": 1.0},
    ]
    assert {output["event_key"] for output in audio_sources["outputs"]} >= {
        "orianna_attack_oncast",
        "orianna_attack_cast",
        "orianna_attack_hit",
    }
    assert override["asset/base/sound/sfx/orianna_attack_oncast_clip"] == {
        "remapping": "asset/lol_mod/sound/sfx/orianna_attack_oncast_clip",
        "type": "override",
    }

    validator.ERRORS.clear()
    validator.validate_orianna_audio(orianna, override)
    assert validator.ERRORS == []
