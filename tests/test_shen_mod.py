from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
MOD = ROOT / "mods" / "lol_mod"


def load_validator():
    path = MOD / "tools" / "validate_lol_mod.py"
    spec = importlib.util.spec_from_file_location("validate_lol_mod", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def walk_effects(value):
    if isinstance(value, dict):
        if isinstance(value.get("type"), str):
            yield value
        for child in value.values():
            yield from walk_effects(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk_effects(child)


def find_effect(value, effect_type: str, **fields):
    return [
        effect
        for effect in walk_effects(value)
        if effect.get("type") == effect_type
        and all(effect.get(key) == expected for key, expected in fields.items())
    ]


def test_static_validator_passes() -> None:
    validator = load_validator()
    validator.ERRORS.clear()
    assert validator.main() == 0


def test_manifest_owned_runtime_text_is_canonical_lf() -> None:
    builder = (MOD / "tools/build_lol_mod.py").read_text(encoding="utf-8")
    assert "def normalize_manifest_text_lf(path: Path) -> None:" in builder
    manifest = json.loads((MOD / "build_manifest.json").read_text(encoding="utf-8"))
    text_suffixes = {
        ".champion_view", ".data_champion", ".fanim", ".i18n", ".json",
        ".md", ".mod_info", ".override_info", ".sound_info",
        ".sprite_sheet", ".style", ".svg", ".txt", ".ui",
    }
    for row in manifest["files"]:
        path = MOD / row["path"]
        if path.suffix.lower() in text_suffixes:
            assert b"\r" not in path.read_bytes(), row["path"]


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
    assert mod_info["version"] == "0.10.9"
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
        "e_icon",
        "r_icon",
        "q_vfx",
        "e_vfx",
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


def test_shen_q_e_r_contract_uses_return_path_empowerment_and_native_taunt() -> None:
    shen = json.loads((MOD / "champion/lol_shen.data_champion").read_text(encoding="utf-8"))

    attack = shen["attack"]
    switches = find_effect(attack, "SwitchByBuff")
    assert [switch["buff_name"] for switch in switches] == [
        "lol_shen_twilight_assault_through_charge_3",
        "lol_shen_twilight_assault_through_charge_2",
        "lol_shen_twilight_assault_through_charge_1",
        "lol_shen_twilight_assault_charge_3",
        "lol_shen_twilight_assault_charge_2",
        "lol_shen_twilight_assault_charge_1",
    ]
    empowered = find_effect(attack, "ApAttack")
    assert [(effect["damage"], effect["attack_ratio"]) for effect in empowered] == [
        (35, 30), (35, 30), (35, 30), (20, 20), (20, 20), (20, 20),
    ]
    removed = {effect["name"] for effect in find_effect(attack, "RemoveCasterBuff")}
    assert removed == {
        "lol_shen_twilight_assault_through_charge_3",
        "lol_shen_twilight_assault_through_charge_2",
        "lol_shen_twilight_assault_through_charge_1",
        "lol_shen_twilight_assault_charge_3",
        "lol_shen_twilight_assault_charge_2",
        "lol_shen_twilight_assault_charge_1",
    }
    for switch in switches:
        delayed = [
            effect
            for effect in switch["effect_buff"]["effects"]
            if effect.get("type") == "Delayed"
        ]
        assert len(delayed) == 1
        assert [
            effect["name"]
            for effect in delayed[0]["effects"]
            if effect.get("type") == "RemoveCasterBuff"
        ] == [switch["buff_name"]]
    assert not find_effect(attack, "AddCasterBuff")

    q = shen["skill"]
    assert (
        q["action_name"], q["cooltime"], q["duration"], q["start_timing"],
        q["range"], q["casting_type"], q["casting_target"],
    ) == ("skill", 360, 28, 8, 55000, "Direction", "EnemyChampion")
    outbound = find_effect(q, "LinearProjectile", name="lol_shen_twilight_assault_blade_outbound")
    assert len(outbound) == 1
    assert (
        outbound[0]["penetrate"], outbound[0]["speed"], outbound[0]["range"],
        outbound[0]["shape"], outbound[0]["applied_target"], outbound[0]["applied_effects"],
    ) == (True, 10000, 65000, {"Circle": {"radius": 4000}}, "EnemyChampion", [])
    returns = find_effect(outbound[0], "BackToCasterLinearProjectile", name="lol_shen_twilight_assault_blade_return")
    assert len(returns) == 1
    blade_return = returns[0]
    assert outbound[0]["end_effects"] == [blade_return]
    assert (
        blade_return["penetrate"], blade_return["speed"], blade_return["range"],
        blade_return["shape"], blade_return["applied_target"], blade_return["end_effects"],
    ) == (True, 12000, 130000, {"Circle": {"radius": 7500}}, "EnemyChampion", [])
    assert not find_effect(q, "RangeProjectile")
    assert not find_effect(q, "Attack")
    assert not find_effect(q, "ApAttack")
    assert not find_effect(q, "Shield")
    direct_q_effects = q["effect"]["effects"]
    q_grants = [effect for effect in direct_q_effects if effect.get("type") == "AddCasterBuff"]
    assert {
        effect["buff_state"]["name"]: effect["buff_state"]["duration"]
        for effect in q_grants
    } == {
        "lol_shen_twilight_assault_charge_3": {"Time": {"tick": 480}},
        "lol_shen_twilight_assault_charge_2": {"Time": {"tick": 480}},
        "lol_shen_twilight_assault_charge_1": {"Time": {"tick": 480}},
    }
    direct_removals = {
        effect["name"] for effect in direct_q_effects if effect.get("type") == "RemoveCasterBuff"
    }
    assert direct_removals == {
        "lol_shen_twilight_assault_charge_3",
        "lol_shen_twilight_assault_charge_2",
        "lol_shen_twilight_assault_charge_1",
        "lol_shen_twilight_assault_through_charge_3",
        "lol_shen_twilight_assault_through_charge_2",
        "lol_shen_twilight_assault_through_charge_1",
        "lol_shen_twilight_assault_return_resolved",
    }
    return_effect = blade_return["applied_effects"][0]["effect"]
    assert return_effect["type"] == "SwitchByBuff"
    assert return_effect["buff_name"] == "lol_shen_twilight_assault_return_resolved"
    assert return_effect["effect_buff"] == {
        "type": "AddCasterBuff",
        "buff_state": {
            "name": "lol_shen_twilight_assault_return_resolved",
            "duration": {"Time": {"tick": 480}},
        },
    }
    remaining_switch = return_effect["effect_none"]
    expected_normal = [
        "lol_shen_twilight_assault_charge_3",
        "lol_shen_twilight_assault_charge_2",
        "lol_shen_twilight_assault_charge_1",
    ]
    all_charge_names = {
        *(f"lol_shen_twilight_assault_charge_{charge}" for charge in (3, 2, 1)),
        *(f"lol_shen_twilight_assault_through_charge_{charge}" for charge in (3, 2, 1)),
    }
    for remaining, normal_marker in zip((3, 2, 1), expected_normal, strict=True):
        assert remaining_switch["type"] == "SwitchByBuff"
        assert remaining_switch["buff_name"] == normal_marker
        branch = remaining_switch["effect_buff"]
        assert branch["type"] == "Combine"
        direct = branch["effects"]
        assert {
            effect["name"] for effect in direct if effect.get("type") == "RemoveCasterBuff"
        } == all_charge_names
        direct_grants = [
            effect["buff_state"] for effect in direct if effect.get("type") == "AddCasterBuff"
        ]
        assert {
            state["name"]
            for state in direct_grants
            if state["name"].startswith("lol_shen_twilight_assault_through_charge_")
        } == {
            f"lol_shen_twilight_assault_through_charge_{charge}"
            for charge in range(remaining, 0, -1)
        }
        assert {
            "name": "lol_shen_twilight_assault_return_resolved",
            "duration": {"Time": {"tick": 480}},
        } in direct_grants
        assert {
            "name": "lol_shen_twilight_assault_through_attack_speed",
            "duration": {"Time": {"tick": 120}},
            "attack_speed_mult": 35,
        } in direct_grants
        assert [
            effect["buff_state"] for effect in direct if effect.get("type") == "AddBuff"
        ] == [{
            "name": "lol_shen_twilight_assault_pull_slow",
            "duration": {"Time": {"tick": 90}},
            "move_speed_mult": -30,
        }]
        remaining_switch = remaining_switch["effect_none"]
    assert remaining_switch == {
        "type": "AddCasterBuff",
        "buff_state": {
            "name": "lol_shen_twilight_assault_return_resolved",
            "duration": {"Time": {"tick": 480}},
        },
    }

    e = shen["skill2"]
    assert (
        e["action_name"], e["cooltime"], e["duration"], e["start_timing"],
        e["range"], e["casting_type"], e["casting_target"],
    ) == ("skill2", 720, 30, 4, 60000, "Direction", "EnemyChampion")
    rushes = find_effect(e, "Rush")
    assert len(rushes) == 1
    rush = rushes[0]
    assert (
        rush["speed"], rush["move_speed_ratio"], rush["range"],
        rush["casting_target"], rush["penetrate"],
    ) == (4000, 100, 10000, "EnemyChampion", True)
    assert len(rush["applied_effects"]) == 1
    assert rush["applied_effects"][0]["casting_type"] == "Targeting"
    rush_payload = rush["applied_effects"][0]["effect"]
    assert rush_payload["type"] == "Combine"
    assert [effect["type"] for effect in rush_payload["effects"]] == [
        "Attack", "Native", "AddBuff", "ViewEffect", "TargetSfx",
    ]
    assert rush_payload["effects"][1] == {
        "type": "Native",
        "effect_ref": "lol_shen_shadow_dash_taunt_native",
    }
    assert find_effect(rush, "Attack", damage=60, attack_ratio=0)
    assert not find_effect(rush, "Taunt")
    assert find_effect(rush, "Native", effect_ref="lol_shen_shadow_dash_taunt_native")
    taunt_markers = find_effect(rush, "AddBuff")
    assert len(taunt_markers) == 1
    assert taunt_markers[0]["buff_state"] == {
        "name": "lol_shen_shadow_dash_taunted",
        "duration": {"Time": {"tick": 90}},
    }
    trail_markers = [
        effect["buff_state"]
        for effect in find_effect(e, "AddCasterBuff")
        if effect["buff_state"]["name"] == "lol_shen_shadow_dash_trail_window"
    ]
    assert trail_markers == [{
        "name": "lol_shen_shadow_dash_trail_window",
        "duration": {"Time": {"tick": 30}},
    }]
    assert find_effect(e, "ViewEffect", name="lol_shen_shadow_dash_impact")
    assert not find_effect(e, "RangeEffect")
    assert not find_effect(e, "Shield")

    r = shen["ult"]
    arrivals = find_effect(r, "Delayed", tick=48)
    assert len(arrivals) == 1
    assert find_effect(arrivals[0], "Teleport")
    assert not find_effect(r, "Taunt")
    assert not [
        effect
        for effect in find_effect(r, "RangeEffect")
        if effect.get("target") == "EnemyChampion"
    ]

    serialized = json.dumps(shen, ensure_ascii=False)
    for retired in ("Spirit's Refuge", "spirit_refuge", "lol_shen_w_", "shen_w"):
        assert retired not in serialized
    assert shen["view_projectiles"] == [
        {
            "type": "Animated",
            "name": "lol_shen_twilight_assault_blade_outbound",
            "anim": "asset/lol_mod/aseprite_resources/effects/shen_q",
            "tag": "outbound",
            "z": 2,
            "repeat": True,
        },
        {
            "type": "Animated",
            "name": "lol_shen_twilight_assault_blade_return",
            "anim": "asset/lol_mod/aseprite_resources/effects/shen_q",
            "tag": "return",
            "z": 2,
            "repeat": True,
        },
    ]
    assert shen["view_effects"] == [
        {
            "type": "Animation",
            "name": "lol_shen_twilight_assault_empowered_hit",
            "anim": "asset/lol_mod/aseprite_resources/effects/shen_q",
            "tag": "empowered_hit",
            "z": 2,
            "is_follow": True,
        },
        {
            "type": "Animation",
            "name": "lol_shen_twilight_assault_through_empowered_hit",
            "anim": "asset/lol_mod/aseprite_resources/effects/shen_q",
            "tag": "through_hit",
            "z": 2,
            "is_follow": True,
        },
        {
            "type": "Animation",
            "name": "lol_shen_twilight_assault_pass_through_visual",
            "anim": "asset/lol_mod/aseprite_resources/effects/shen_q",
            "tag": "pass_through",
            "z": 2,
            "is_follow": True,
        },
        {
            "type": "Animation",
            "name": "lol_shen_shadow_dash_impact",
            "anim": "asset/lol_mod/aseprite_resources/effects/shen_e",
            "tag": "impact",
            "z": 2,
            "is_follow": True,
        },
        {
            "type": "Animation",
            "name": "lol_shen_stand_united_guard_visual",
            "anim": "asset/lol_mod/aseprite_resources/effects/shen_r",
            "tag": "guard",
            "z": 1,
            "is_follow": True,
        },
        {
            "type": "Animation",
            "name": "lol_shen_stand_united_arrival_visual",
            "anim": "asset/lol_mod/aseprite_resources/effects/shen_r",
            "tag": "arrival",
            "z": 1,
            "is_follow": False,
        },
    ]
    assert shen["view_buffs"] == [
        {
            "type": "ThreePhase",
            "name": "lol_shen_shadow_dash_trail_window",
            "anim": "asset/lol_mod/aseprite_resources/effects/shen_e",
            "pre_tag": "trail_pre",
            "loop_tag": "trail_loop",
            "remove_tag": "trail_remove",
            "z": -1,
        },
        {
            "type": "ThreePhase",
            "name": "lol_shen_shadow_dash_taunted",
            "anim": "asset/lol_mod/aseprite_resources/effects/shen_e",
            "pre_tag": "taunt_pre",
            "loop_tag": "taunt_loop",
            "remove_tag": "taunt_remove",
            "z": 2,
        },
    ]

    runtime = (MOD / "src/lib.rs").read_text(encoding="utf-8")
    assert 'struct ShenShadowDashTauntNativeEffect;' in runtime
    assert 'CCState::Taunt {' in runtime
    assert 'target: caster_id' in runtime
    assert 'fn expected_cc_time(&self) -> Option<usize>' in runtime
    assert 'Some(SHEN_SHADOW_DASH_TAUNT_TICKS as usize)' in runtime
    assert '"lol_shen_shadow_dash_taunt_native"' in runtime
    assert "ShenShadowDashInput" not in runtime
    shen_native = runtime.split("impl ModEffectType for ShenShadowDashTauntNativeEffect {", 1)[1].split(
        "\nfn init(", 1
    )[0]
    assert ".unwrap(" not in shen_native
    assert ".get_entity(caster_id)" in shen_native
    assert ".get_entity(target_id)" in shen_native
    assert shen_native.count(".is_some_and(|") == 2
    assert shen_native.count("ctx.apply_cc(") == 1
    assert "ctx.apply_cc(\n            target_id,\n            CCState::Taunt {" in shen_native
    assert shen_native.count("tick: SHEN_SHADOW_DASH_TAUNT_TICKS") == 1
    assert shen_native.count("target: caster_id") == 1

    text = json.loads((MOD / "text/champion.i18n").read_text(encoding="utf-8"))
    assert "Twilight Assault" in text["en"]["description"]["lol_shen"]["skill"]
    assert "first enemy champion crossed by the returning trace" in text["en"]["description"]["lol_shen"]["skill"]
    assert "only the empowered attacks still unused" in text["en"]["description"]["lol_shen"]["skill"]
    assert "does not retain an independently positioned blade" in text["en"]["description"]["lol_shen"]["skill"]
    assert "Shadow Dash" in text["en"]["description"]["lol_shen"]["skill2"]
    assert "forced to attack Shen for 1.5 seconds" in text["en"]["description"]["lol_shen"]["skill2"]
    assert "奥义！暮临" in text["zh-hans"]["description"]["lol_shen"]["skill"]
    assert "仅将尚未使用的强化升级" in text["zh-hans"]["description"]["lol_shen"]["skill"]
    assert "奥义！影缚" in text["zh-hans"]["description"]["lol_shen"]["skill2"]
    assert "强制攻击慎1.5秒" in text["zh-hans"]["description"]["lol_shen"]["skill2"]
    assert "奧義！暮臨" in text["zh-hant"]["description"]["lol_shen"]["skill"]
    assert "奧義！影縛" in text["zh-hant"]["description"]["lol_shen"]["skill2"]

    builder = (MOD / "tools/build_lol_mod.py").read_text(encoding="utf-8")
    assert '"shen_skill2.png": SOURCE / "shen_e_icon_source_alpha.png"' in builder
    assert '"shen_e": (SOURCE / "shen_e_vfx_contact_alpha.png"' in builder
    assert "def build_shen_data() -> Path:" in builder
    assert "champion = json.loads(path.read_text" not in builder
    assert "SHEN_SHADOW_DASH_DISTANCE = 60000" in builder
    assert "SHEN_SHADOW_DASH_COLLISION_RADIUS = 10000" in builder
    assert 'zip(icons, ["Q", "E", "R"], strict=True)' in builder


def test_shen_builder_reconstructs_from_an_immutable_template(tmp_path: Path) -> None:
    path = MOD / "tools" / "build_lol_mod.py"
    sys.path.insert(0, str(path.parent))
    try:
        spec = importlib.util.spec_from_file_location("build_lol_mod_shen_determinism", path)
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(module)
    finally:
        sys.path.pop(0)
    module.MOD_ROOT = tmp_path
    first_path = module.build_shen_data()
    first = first_path.read_bytes()
    first_path.write_text('{"id":"contaminated-generated-output"}\n', encoding="utf-8")
    second_path = module.build_shen_data()
    second = second_path.read_bytes()
    assert first == second
    assert json.loads(second)["id"] == "lol_shen"


def test_official_sdk_deserializes_shen_data_champion() -> None:
    source = MOD / "tools" / "shen_data_champion_sdk_gate.rs"
    script = MOD / "tools" / "validate_shen_data_champion_sdk.ps1"
    assert "use game_core::DataChampionInfo;" in source.read_text(encoding="utf-8")
    assert "serde_json::from_str" in source.read_text(encoding="utf-8")
    assert script.is_file()
    sdk = ROOT.parent / "mod-sdk"
    if not sdk.is_dir():
        return
    result = subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(script),
            "-ChampionPath",
            str(MOD / "champion" / "lol_shen.data_champion"),
            "-SdkDir",
            str(sdk),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    assert result.returncode == 0, result.stderr or result.stdout
    assert "SDK DataChampionInfo accepted" in result.stdout


def test_shen_and_lucian_hd_surfaces_are_source_direct_and_independent() -> None:
    import sys

    sys.path.insert(0, str(ROOT / "tests"))
    from legacy_hd_assertions import (
        animation_frames,
        assert_actor_tag_scale,
        assert_legacy_hd_portrait_set,
        assert_readable_upper_detail,
    )

    builder = (MOD / "tools" / "build_lol_mod.py").read_text(encoding="utf-8")
    runtime = (MOD / "src" / "lib.rs").read_text(encoding="utf-8")
    assert "def render_source_direct_ui_subject(" in builder
    assert "def build_source_direct_portrait_set(" in builder
    assert "source_direct_actor_cell(" in builder
    assert "def pack_stable_actor_pose(" in builder
    assert "base_pose_heights = (36, 36, 36, 36, 36, 35, 35, 35, 35, 35, 36, 33)" in builder
    assert "base_pose_heights = (36, 36, 36, 36, 36, 36, 34, 34, 39, 36, 35, 14)" in builder
    assert "rewrite_shen_lucian_portrait_render_commands(state);" in runtime
    assert "let is_scoreboard_square = (14.0..=38.0)" in runtime
    assert "let is_compact_square = (39.0..=52.0)" in runtime
    assert "let is_bp_grid = (124.0..=132.0)" in runtime

    for hero, champion_id, actor_name, idle_height, run_range in (
        ("shen", "lol_shen", "shen", 36, (36, 36)),
        ("lucian", "archer", "lucian", 36, (36, 36)),
    ):
        qa = json.loads((MOD / "qa" / f"{hero}_hd_surface_qa.json").read_text(encoding="utf-8"))
        assert qa["source_route"] == "existing processed high-resolution ImageGen idle; no new generation"
        assert qa["skill_logic_changed"] is False
        assert qa["battle_actor"]["uniform_xy_scale"] is True
        assert qa["battle_actor"]["x_only_compression"] is False
        assert (
            qa["battle_actor"]["first_idle_alpha_bbox"][3]
            - qa["battle_actor"]["first_idle_alpha_bbox"][1]
            == idle_height
        )
        assert qa["runtime_routing"]["scoreboard_square_px"] == [14, 38]
        assert qa["runtime_routing"]["sidebar_square_px"] == [39, 52]

        assert_legacy_hd_portrait_set(
            MOD,
            champion_id,
            side_card_relative=f"BanPickIllust/{champion_id}.png",
        )
        actor_sheet = MOD / "aseprite_resources" / "champions" / f"{actor_name}#sheet.png"
        actor_anim = MOD / "aseprite_resources" / "champions" / f"{actor_name}#anim.fanim"
        assert_actor_tag_scale(
            actor_sheet,
            actor_anim,
            "idle",
            min_height=idle_height,
            max_height=idle_height,
            baseline=45,
            min_unique_frames=2,
        )
        assert_actor_tag_scale(
            actor_sheet,
            actor_anim,
            "run",
            min_height=run_range[0],
            max_height=run_range[1],
            baseline=45,
            min_unique_frames=9,
        )
        assert_readable_upper_detail(animation_frames(actor_sheet, actor_anim, "idle")[0])


def test_quality_runtime_uses_live_ui_paths_and_seeded_dragon_variants() -> None:
    source = (MOD / "src" / "lib.rs").read_text(encoding="utf-8")
    override = json.loads((MOD / "mod.override_info").read_text(encoding="utf-8"))

    assert "top.right.champion_info.data.champions.contents" in source
    assert "match_ui_database_from_node" in source
    assert "fn post_render(" in source
    assert "rewrite_bp_render_commands(ui, state)" in source
    assert "RenderCommand::NinePatch" in source
    assert 'ui.query("blue_picks")' in source
    assert 'ui.query("red_picks")' in source
    assert 'ui.query("header.delegate_btn")' in source
    assert 'ui.query("main.blue_picks")' not in source
    assert 'ui.query("main.red_picks")' not in source
    assert "fn bp_identity_from_pass(" in source
    assert 'pass.contains("blue_picks")' in source
    assert 'pass.contains("red_picks")' in source
    assert 'let marker = "pick_slot_"' in source
    assert '"texture_skip"' in source
    assert "fn ui_tree_contains_id(" in source
    assert 'ui_tree_contains_id(&ui.root, "blue_picks")' in source
    assert 'ui_tree_contains_id(&ui.root, "red_picks")' in source
    assert "let mut overlay = (*command).clone()" in source
    assert "overlays.push(candidate.overlay)" in source
    assert "commands.extend(overlays)" in source
    assert '"overlay_append"' in source
    assert '"version=0.10.9;root=' in source
    assert 'let marker = "/champions/"' in source
    assert "source.find(marker)? + marker.len()" in source
    assert '.strip_suffix("#sheet")' in source
    assert "for (pass, commands) in &mut state.commands" in source
    assert ".map_size" in source and ".get(pass)" in source
    assert "map_width - BP_RED_TRANSITION_EDGE_BAND" in source
    assert '"candidate_skip"' in source
    assert '"asset/lol_mod/BanPickIllust/lol_shen"' in source
    assert not any(
        key.startswith("asset/base/ui/banpick/illust/") for key in override
    )
    assert "splash_id_from_source" in source
    assert "texture_rect.w = 1.0" in source
    assert "texture_rect.h = 1.0" in source
    assert "texture_rect.w = 1420.0" not in source
    assert "texture_rect.h = 860.0" not in source
    assert "*w = BP_CARD_WIDTH" in source and "*h = BP_CARD_HEIGHT" in source
    assert "*z = 200" in source
    assert "*flip_x = side == BpRenderSide::Red" in source
    assert "done.champion.icon" not in source
    assert "sync_side(" not in source
    assert "quality_bp_runtime_telemetry.tsv" in source

    objective_packer = (MOD / "tools" / "pack_quality_objectives.py").read_text(
        encoding="utf-8"
    )
    assert 'center_on_frame=tag_name in {"base", "idle", "attack"}' in objective_packer
    assert "DRAGON_ATTACK_GROUND_OFFSET_FROM_FRAME_CENTER = 35.0" in objective_packer
    assert "bottom_from_frame_center" in objective_packer
    assert 'elif tag_name == "attack":' in objective_packer
    assert '"maximum_attack_ground_anchor_offset_px"' in objective_packer
    assert '"maximum_attack_ground_offset_error_px"' in objective_packer
    assert '"attack_body_bbox_center_y_span_px"' in objective_packer
    assert '"dragon_attack_ground_anchors_centered"' in objective_packer
    assert '"dragon_attack_ground_offsets_stable"' in objective_packer
    assert '"dragon_attack_body_vertical_span_bounded"' in objective_packer

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


def test_bp_overlay_is_card_anchored_and_deduplicated() -> None:
    source = (MOD / "src" / "lib.rs").read_text(encoding="utf-8")
    rewrite = source.split("fn rewrite_bp_render_commands", 1)[1].split(
        "\nfn texture_source", 1
    )[0]

    # Ban/Pick View Plus uses a blue left anchor at x=15 and a flipped red
    # right anchor at x=1905 on 1920px. Slot y is 98/286/474/662/850.
    assert "const BP_CARD_WIDTH: f32 = 284.0;" in source
    assert "const BP_CARD_HEIGHT: f32 = 172.0;" in source
    assert "const BP_CARD_EDGE_INSET: f32 = 15.0;" in source
    assert "const BP_CARD_TOP: f32 = 98.0;" in source
    assert "const BP_CARD_STEP_Y: f32 = 188.0;" in source
    assert "BpRenderSide::Blue => BP_CARD_EDGE_INSET" in source
    assert "BpRenderSide::Red => map_width - BP_CARD_EDGE_INSET" in source
    assert "BP_CARD_TOP + BP_CARD_STEP_Y * slot_index as f32" in source
    assert "let target_x = bp_overlay_x(side, map_width);" in rewrite
    assert "let target_y = bp_overlay_y(slot_index);" in rewrite
    assert "*w = BP_CARD_WIDTH;" in rewrite
    assert "*h = BP_CARD_HEIGHT;" in rewrite

    # Never inherit the actor's slide/scale transition geometry again.
    for old_expression in (
        "original_geometry.0 - 145.0",
        "original_geometry.0 - 6.0",
        "original_geometry.1 + 11.0",
    ):
        assert old_expression not in rewrite

    # Each pass owns ten unique candidates: blue/red x five slots. Only the
    # command nearest the settled actor rectangle produces the final overlay.
    assert "Self::Blue => 0" in source
    assert "Self::Red => PICK_SLOT_LIMIT" in source
    assert "side_offset + slot_index" in source
    assert "(0..PICK_SLOT_LIMIT * 2).map(|_| None).collect()" in rewrite
    assert "let candidate_index = side.candidate_index(slot_index);" in rewrite
    assert "score < candidate.score" in rewrite
    assert "candidates[candidate_index] = Some(BpOverlayCandidate" in rewrite
    assert "for candidate in candidates.into_iter().flatten()" in rewrite
    assert rewrite.count("overlays.push(candidate.overlay);") == 1
    assert "overlays.push(overlay);" not in rewrite

    # A pick-complete transition must replace the original actor command,
    # rather than leaving its scaled slide-in pose behind the splash.  The
    # red transition starts around x=1579 at 1920px, while 128x128 champion
    # list thumbnails remain outside the accepted actor-size contract.
    assert "const BP_RED_TRANSITION_EDGE_BAND: f32 = 430.0;" in source
    assert "const BP_TRANSITION_ACTOR_MIN_WIDTH: f32 = 120.0;" in source
    assert "const BP_TRANSITION_ACTOR_MAX_WIDTH: f32 = 140.0;" in source
    assert "const BP_TRANSITION_ACTOR_MIN_HEIGHT: f32 = 140.0;" in source
    assert "const BP_TRANSITION_ACTOR_MAX_HEIGHT: f32 = 190.0;" in source
    assert "bp_side_from_geometry(champion_id, *x, *y, *w, *h, map_width)" in " ".join(
        rewrite.split()
    )
    assert "original_actor_indices.push(command_index);" in rewrite
    assert "original_actor_counts[side.candidate_index(slot_index)] += 1;" in rewrite
    assert "for command_index in original_actor_indices.into_iter().rev()" in rewrite
    assert "commands.remove(command_index);" in rewrite
    assert "original_actor_commands_removed={removed_actor_count}" in rewrite


def test_bp_overlay_supports_xayahs_tight_native_dancer_rect_without_touching_grid_art() -> None:
    source = (MOD / "src" / "lib.rs").read_text(encoding="utf-8")
    rewrite = source.split("fn rewrite_bp_render_commands", 1)[1].split(
        "\nfn texture_source", 1
    )[0]

    # Current live telemetry proves the picked side actor settles at 81x141
    # and keeps width 81 while its transition height grows from ~125 to 141.
    # Its center exactly matches the standard 137x184 card actor.  The older
    # 54x94 geometry is the center hero grid and must stay out of this route.
    assert "const BP_DANCER_ACTOR_WIDTH: f32 = 81.0;" in source
    assert "const BP_DANCER_ACTOR_HEIGHT: f32 = 141.0;" in source
    assert "const BP_DANCER_TRANSITION_MIN_WIDTH: f32 = 80.0;" in source
    assert "const BP_DANCER_TRANSITION_MAX_WIDTH: f32 = 82.0;" in source
    assert "const BP_DANCER_TRANSITION_MIN_HEIGHT: f32 = 124.0;" in source
    assert "const BP_DANCER_TRANSITION_MAX_HEIGHT: f32 = 142.0;" in source
    assert 'if champion_id == "dancer"' in source
    assert "let contract = bp_actor_contract(champion_id);" in source
    assert "contract.min_width..=contract.max_width" in source
    assert "contract.min_height..=contract.max_height" in source
    assert "bp_actor_candidate_score( champion_id," in " ".join(rewrite.split())
    assert "bp_geometry_is_actor_sized_near_pick_edge(*x, *w, *h, map_width)" in " ".join(
        rewrite.split()
    )
    assert "near_side && width >= 40.0 && height >= 70.0" in source
    assert "native_center_x - contract.width * 0.5" in source
    assert "native_center_y - contract.height * 0.5" in source
    assert "let right_edge_start = (map_width - BP_RED_TRANSITION_EDGE_BAND).max(335.0);" in source

    # The dedicated 90x122 texture is substituted only for the center grid's
    # tight native command.  It cannot swallow the new side-card geometry.
    xayah_portrait_route = source.split("fn rewrite_xayah_portrait_render_commands", 1)[1].split(
        "\nfn match_ui_database", 1
    )[0]
    assert "(50.0..=58.0).contains(w)" in xayah_portrait_route
    assert "(88.0..=100.0).contains(h)" in xayah_portrait_route
    assert "(80.0..=82.0).contains(w)" not in xayah_portrait_route
    assert "let center_x = *x + *w * 0.5;" in xayah_portrait_route
    assert "let center_y = *y + *h * 0.5;" in xayah_portrait_route
    assert "*w = 90.0;" in xayah_portrait_route
    assert "*h = 122.0;" in xayah_portrait_route

    # Replay the newest 1920px telemetry samples against the encoded bounds.
    # Stable Dancer and the standard actor share one center at (1694.5,179).
    standard_center = (1920.0 - 294.0 + 137.0 / 2, 87.0 + 184.0 / 2)
    dancer_center = (1654.0 + 81.0 / 2, 108.5 + 141.0 / 2)
    assert dancer_center == standard_center
    for width, height in ((81.0, 125.2), (81.0, 129.3), (81.0, 136.7), (81.0, 141.0)):
        assert 80.0 <= width <= 82.0
        assert 124.0 <= height <= 142.0
    assert 1601.2 >= 1920.0 - 430.0  # first observed red transition sample
    assert not (0.0 <= 804.5 <= 335.0 or 1920.0 - 430.0 <= 804.5 <= 2100.0)

    style = json.loads(
        (MOD / "style/champion_view.champion_view").read_text(encoding="utf-8")
    )["entries"]["dancer"]
    assert style == {"face": {"x": 2, "y": -32}, "center": {"x": 0, "y": -12}}


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
    assert hit_bbox is not None and hit_bbox[2] - hit_bbox[0] <= 32
    assert dead_bbox is not None and dead_bbox[2] - dead_bbox[0] <= 44
