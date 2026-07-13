import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MOD = ROOT / "mods" / "lol_mod"
CHAMPION_PATH = MOD / "champion" / "demon.data_champion"
RUST_PATH = MOD / "src" / "lib.rs"


def load_json(relative: str):
    return json.loads((MOD / relative).read_text(encoding="utf-8"))


def find_effect(node, effect_type: str, **fields):
    found = []

    def visit(value):
        if isinstance(value, dict):
            if value.get("type") == effect_type and all(
                value.get(key) == expected for key, expected in fields.items()
            ):
                found.append(value)
            for child in value.values():
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)

    visit(node)
    return found


def test_all_champion_categories_use_engine_enum_values():
    valid_categories = {"Melee", "Range", "Magician", "Util", "Assassin"}
    invalid = {}
    for path in sorted((MOD / "champion").glob("*.data_champion")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        category = payload.get("category")
        if category not in valid_categories:
            invalid[path.name] = category

    assert invalid == {}


def test_urgot_is_the_single_official_008_demon_replacement():
    champion = load_json("champion/demon.data_champion")
    demon_files = []
    for path in sorted((MOD / "champion").glob("*.data_champion")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("id") == "demon":
            demon_files.append(path.name)

    assert demon_files == ["demon.data_champion"]
    assert champion["id"] == "demon"
    assert champion["sprite"] == "asset/lol_mod/aseprite_resources/champions/demon"
    assert not (MOD / "champion/lol_urgot.data_champion").exists()
    assert not (MOD / "champion/urgot.data_champion").exists()
    assert "replace_champion" not in RUST_PATH.read_text(encoding="utf-8")


def test_urgot_stats_attack_contract_and_wer_only_slots():
    champion = load_json("champion/demon.data_champion")
    assert champion["category"] == "Melee"
    assert {"AD", "Melee", "Tank", "CC"}.issubset(champion["tags"])
    assert "Range" not in champion["tags"]
    assert champion["stat"] == {
        "attack": 100,
        "magic_power": 0,
        "hp": 1050,
        "defence": 35,
        "magic_resistance": 25,
        "move_speed": 900,
        "hp_regen": 3,
        "stack": 0,
        "crit_chance": 0,
    }
    assert champion["growth"]["attack"] == 18
    assert champion["growth"]["hp"] == 105
    assert champion["growth"]["defence"] == 7
    assert champion["growth"]["magic_resistance"] == 4
    assert champion["growth"]["move_speed"] == 4

    attack = champion["attack"]
    assert attack["range"] == 40000
    assert attack["cooltime"] == 72
    projectiles = find_effect(
        attack, "TargetProjectile", name="lol_urgot_attack_projectile"
    )
    assert len(projectiles) == 1
    assert projectiles[0]["speed"] == 7600
    hits = find_effect(projectiles[0], "Attack")
    assert hits == [{"type": "Attack", "damage": 0, "attack_ratio": 100}]
    assert len(
        find_effect(attack, "Native", effect_ref="lol_urgot_passive_native")
    ) == 1
    assert len(
        find_effect(
            attack,
            "CasterViewEffect",
            name="lol_urgot_attack_muzzle_visual",
        )
    ) == 1
    assert len(
        find_effect(
            attack,
            "ViewEffect",
            name="lol_urgot_attack_impact_visual",
        )
    ) == 1

    assert champion["skill_icons"] == [
        "asset/lol_mod/icons/urgot_w",
        "asset/lol_mod/icons/urgot_e",
        "asset/lol_mod/icons/urgot_r",
    ]
    assert [champion[key]["description"] for key in ("skill", "skill2", "ult")] == [
        "#asset/base/text/champion?description.demon.skill",
        "#asset/base/text/champion?description.demon.skill2",
        "#asset/base/text/champion?description.demon.ult",
    ]
    forbidden_active_slots = {"q", "w", "e", "r", "skill3", "skill4"}
    assert forbidden_active_slots.isdisjoint(champion)

    i18n = load_json("text/champion.i18n")
    for locale in ("en", "zh-hans", "zh-hant", "ja"):
        text = i18n[locale]["description"]["demon"]
        assert text["name"]
        assert text["skill"].lstrip().startswith("W")
        assert text["skill2"].lstrip().startswith("E")
        assert text["ult"].lstrip().startswith("R")
        assert not text["skill"].lstrip().startswith("Q")


def test_echoing_flames_is_a_real_native_two_second_shotgun_cooldown():
    champion = load_json("champion/demon.data_champion")
    native = find_effect(
        champion["attack"], "Native", effect_ref="lol_urgot_passive_native"
    )
    assert len(native) == 1

    source = RUST_PATH.read_text(encoding="utf-8")
    assert "const URGOT_PASSIVE_COOLDOWN_TICKS: usize = 120;" in source
    assert "const URGOT_PASSIVE_FLAT_DAMAGE: usize = 20;" in source
    assert "const URGOT_PASSIVE_ATTACK_RATIO_PERCENT: usize = 30;" in source
    assert "const URGOT_PASSIVE_TARGET_MAX_HP_PERCENT: usize = 2;" in source
    assert "struct UrgotPassiveCooldown" in source
    assert "if now < cooldown.ready_tick" in source
    assert "target_max_hp.saturating_mul(URGOT_PASSIVE_TARGET_MAX_HP_PERCENT)" in source
    assert "ctx.deal_damage(caster_id, target_id, damage, 0, AttackType::Skill);" in source


def test_w_keeps_all_twelve_delayed_shots_inside_a_cancelable_240_tick_action():
    champion = load_json("champion/demon.data_champion")
    w = champion["skill"]
    assert w["cooltime"] == 600
    assert w["duration"] == 240
    assert w["cancelable"] is True
    assert w["can_use_with_move"] is True
    assert (w["range"], w["casting_type"], w["casting_target"]) == (
        0,
        "None",
        "AllyOnlySelf",
    )
    assert not find_effect(w, "Native")
    cast_animations = find_effect(w, "CasterAnimation")
    assert cast_animations == [{
        "type": "CasterAnimation",
        "name": "skill1",
        "tick": 8,
    }]

    purge = find_effect(w, "AddCasterBuff")
    assert len(purge) == 1
    buff = purge[0]["buff_state"]
    assert buff["name"] == "lol_urgot_w_purge"
    assert buff["duration"]["Time"]["tick"] == 240
    assert buff["move_speed_mult"] == -12
    assert buff["defence"] == 20
    assert buff["magic_resistance"] == 10

    delayed = find_effect(w, "Delayed")
    assert sorted(effect["tick"] for effect in delayed) == list(range(1, 222, 20))
    assert max(effect["tick"] for effect in delayed) < w["duration"]
    projectiles = find_effect(
        w, "AutoTargetProjectile", name="lol_urgot_w_cannon_projectile"
    )
    assert len(projectiles) == 12
    assert not find_effect(w, "TargetProjectile", name="lol_urgot_w_cannon_projectile")
    for pulse in delayed:
        assert len(
            find_effect(
                pulse,
                "AutoTargetProjectile",
                name="lol_urgot_w_cannon_projectile",
            )
        ) == 1
        assert not find_effect(pulse, "SwitchByBuff")
        assert not find_effect(pulse, "CasterAnimation")
        assert not find_effect(pulse, "Native")
    assert not find_effect(w, "CasterViewEffect", name="lol_urgot_w_muzzle_visual")
    for projectile in projectiles:
        assert projectile["speed"] == 7000
        assert projectile["range"] == 60000
        assert projectile["applied_target"] == "EnemyWithoutTower"
        hits = find_effect(projectile, "Attack")
        assert len(hits) == 1
        assert hits[0]["damage"] == 8
        assert hits[0]["attack_ratio"] == 20
        assert len(
            find_effect(
                projectile,
                "ViewEffect",
                name="lol_urgot_w_impact_visual",
            )
        ) == 1

    source = RUST_PATH.read_text(encoding="utf-8")
    assert "const URGOT_W_CHANNEL_TICKS" not in source
    assert "URGOT_W_CHANNELS" not in source
    assert "const URGOT_W_SHOT_LOCK_TICKS" not in source
    assert "const URGOT_W_BLOCK_ATTACK_TICKS" not in source
    assert "struct UrgotWChannelState" not in source
    assert "UrgotWNativeEffect" not in source
    assert "UrgotWCancelNativeEffect" not in source
    assert "UrgotWShotGateNativeEffect" not in source
    assert "lol_urgot_w_native" not in source
    assert "lol_urgot_w_cancel_native" not in source
    assert "lol_urgot_w_shot_gate_native" not in source
    assert "lol_urgot_w_shot_ready" not in source

    builder = (MOD / "tools/build_urgot.py").read_text(encoding="utf-8")
    assert "for tick in range(1, 222, 20):" in builder
    assert "def _urgot_w_projectile()" in builder
    assert "gameplay_data = build_gameplay_data()" in builder

    # Purge is represented by twelve firing poses/single projectiles, not a
    # giant persistent aura or an incorrectly body-centred muzzle effect.
    assert champion["view_buffs"] == []
    assert not any(
        effect.get("name") == "lol_urgot_w_muzzle_visual"
        for effect in champion["view_effects"]
    )


def test_urgot_ai_promotes_legal_attacks_to_learned_r_then_w():
    source = RUST_PATH.read_text(encoding="utf-8")
    gate = re.search(
        r"impl ModPlayerInputAi for UrgotAbilityInputGate \{(?P<body>.*?)\n\}",
        source,
        re.DOTALL,
    )
    assert gate
    body = gate.group("body")
    assert '"demon" | "Urgot" | "厄加特" | "アーゴット" | "우르곳"' in body
    recall = body.index("matches!(base_input, Some(Input::Return))")
    attack_gate = body.index("let Some(Input::Attack { target }) = base_input")
    assert recall < attack_gate
    assert "urgot_w_active_target_for_ai" not in body
    assert "urgot_w_cancel_for_ai" not in body
    assert "let ultimate = Input::Ult { target };" in body
    assert "ctx.is_valid_input(&ultimate)" in body
    assert "let purge = Input::Skill {" in body
    assert "target: InputTarget::None" in body
    assert "ctx.is_valid_input(&purge)" in body
    assert body.index("Input::Ult") < body.index("Input::Skill")
    assert "registration.add_player_input_ai(UrgotAbilityInputGate);" in source


def test_r_clears_persistent_purge_before_launching():
    champion = load_json("champion/demon.data_champion")
    r = champion["ult"]
    top_level = r["effect"]["effects"]
    assert top_level[0] == {"type": "RemoveCasterBuff", "name": "lol_urgot_w_purge"}
    assert "lol_urgot_w_cancel_native" not in json.dumps(r)
    assert "lol_urgot_w_shot_ready" not in json.dumps(r)


def test_e_restores_the_first_reviewed_rush_behind_and_flip_contract():
    champion = load_json("champion/demon.data_champion")
    e = champion["skill2"]
    assert e["cooltime"] == 420
    assert e["action_name"] == "transform"
    assert e["duration"] == 30
    assert e["range"] == 45000
    assert e["casting_target"] == "EnemyChampion"
    assert find_effect(e, "CasterAnimation") == [
        {"type": "CasterAnimation", "name": "transform", "tick": 30}
    ]

    shields = find_effect(e, "Shield")
    assert len(shields) == 1
    assert shields[0]["amount"] == 160
    assert shields[0]["attack_ratio"] == 70
    assert shields[0]["tick"] == 180

    rushes = find_effect(e, "RushMoveToBack")
    assert len(rushes) == 1
    rush = rushes[0]
    assert rush["speed"] == 4500
    hit = find_effect(rush, "Attack")
    assert len(hit) == 1
    assert hit[0]["damage"] == 70
    assert hit[0]["attack_ratio"] == 90
    assert len(find_effect(rush, "Native", effect_ref="lol_urgot_e_native")) == 1
    assert find_effect(rush, "Knockback") == [
        {"type": "Knockback", "speed": 2600, "tick": 8}
    ]
    assert not find_effect(e, "Grab")

    source = RUST_PATH.read_text(encoding="utf-8")
    assert "const URGOT_E_STUN_TICKS: u64 = 60;" in source
    assert re.search(
        r"impl ModEffectType for UrgotENativeEffect.*?get_entity\(target_id\).*?"
        r"is_some_and\(\|target\| target\.is_alive\(\)\).*?CCState::Stun\s*\{\s*"
        r"tick: URGOT_E_STUN_TICKS",
        source,
        re.DOTALL,
    )


def test_r_is_non_piercing_pull_and_true_25_percent_execute_check():
    champion = load_json("champion/demon.data_champion")
    r = champion["ult"]
    assert r["cooltime"] == 3000
    assert r["range"] == 90000
    assert r["duration"] == 30
    assert r["casting_type"] == "Targeting"
    assert find_effect(r, "CasterAnimation") == [
        {"type": "CasterAnimation", "name": "ult", "tick": 30}
    ]
    projectile = find_effect(r, "LinearProjectile", name="lol_urgot_r_chain_projectile")
    assert len(projectile) == 1
    projectile = projectile[0]
    assert projectile["penetrate"] is False
    assert projectile["speed"] == 7000
    assert projectile["range"] == 90000
    assert len(
        find_effect(
            r,
            "CasterViewEffect",
            name="lol_urgot_r_launch_visual",
        )
    ) == 1

    first_hit = find_effect(projectile, "Attack")[0]
    assert first_hit["damage"] == 80
    assert first_hit["attack_ratio"] == 60
    slow = find_effect(projectile, "AddBuff",)
    slow = [effect for effect in slow if effect["buff_state"]["name"] == "lol_urgot_r_slow"]
    assert len(slow) == 1
    assert slow[0]["buff_state"]["move_speed_mult"] == -35
    assert slow[0]["buff_state"]["duration"]["Time"]["tick"] == 90

    delayed = [effect for effect in find_effect(projectile, "Delayed") if effect["tick"] == 45]
    assert len(delayed) == 1
    assert len(
        find_effect(
            delayed[0],
            "Native",
            effect_ref="lol_urgot_r_check_native",
        )
    ) == 1
    ready_switches = find_effect(
        delayed[0], "SwitchByBuff", buff_name="lol_urgot_r_execute_ready"
    )
    assert len(ready_switches) == 1
    ready_switch = ready_switches[0]
    assert not find_effect(ready_switch["effect_none"], "Grab")
    assert find_effect(ready_switch["effect_buff"], "Grab") == [
        {"type": "Grab", "speed": 7000, "tick": 12}
    ]
    execute_delays = [
        effect
        for effect in find_effect(ready_switch["effect_buff"], "Delayed")
        if effect["tick"] == 12
    ]
    assert len(execute_delays) == 1
    assert len(
        find_effect(
            execute_delays[0],
            "Native",
            effect_ref="lol_urgot_r_execute_native",
        )
    ) == 1

    source = RUST_PATH.read_text(encoding="utf-8")
    assert "const URGOT_R_EXECUTE_THRESHOLD_PERCENT: usize = 25;" in source
    assert "target_hp.current > execute_limit" in source
    assert ".saturating_mul(URGOT_R_EXECUTE_THRESHOLD_PERCENT)" in source
    assert "target_hp.current" in source and "target_hp.max" in source
    assert "target_shield" in source


def test_r_fear_and_splash_exist_only_on_confirmed_successful_execution():
    champion = load_json("champion/demon.data_champion")
    r = champion["ult"]
    switches = find_effect(
        r, "SwitchByBuff", buff_name="lol_urgot_r_execute_success"
    )
    assert len(switches) == 1
    switch = switches[0]
    assert not find_effect(switch["effect_none"], "Fear")
    assert not find_effect(switch["effect_none"], "Attack")

    fear = find_effect(switch["effect_buff"], "Fear")
    assert fear == [{"type": "Fear", "tick": 45}]
    ranges = find_effect(switch["effect_buff"], "RangeEffect")
    assert len(ranges) == 1
    assert ranges[0]["shape"]["Circle"]["radius"] == 32000
    splash = find_effect(ranges[0], "Attack")
    assert splash == [{"type": "Attack", "damage": 30, "attack_ratio": 30}]
    assert len(
        find_effect(
            switch["effect_buff"],
            "CasterViewEffect",
            name="lol_urgot_r_execute_visual",
        )
    ) == 1

    source = RUST_PATH.read_text(encoding="utf-8")
    check_impl = re.search(
        r"impl ModEffectType for UrgotRCheckNativeEffect \{(?P<body>.*?)\n\}",
        source,
        re.DOTALL,
    )
    assert check_impl
    check_body = check_impl.group("body")
    assert "target_hp.current > execute_limit" in check_body
    assert 'ready.name = "lol_urgot_r_execute_ready"' in check_body
    assert "ctx.add_buff(caster_id, ready);" in check_body

    execute_impl = re.search(
        r"impl ModEffectType for UrgotRExecuteNativeEffect \{(?P<body>.*?)\n\}",
        source,
        re.DOTALL,
    )
    assert execute_impl
    body = execute_impl.group("body")
    confirm = body.index(".is_some_and(|target| !target.is_alive())")
    reject = body.index("if !executed")
    marker = body.index('success.name = "lol_urgot_r_execute_success"')
    add_buff = body.index("ctx.add_buff(caster_id, success);")
    assert confirm < reject < marker < add_buff


def test_all_four_urgot_native_effects_are_registered_without_replacing_champion():
    source = RUST_PATH.read_text(encoding="utf-8")
    expected = {
        "lol_urgot_passive_native": "UrgotPassiveNativeEffect",
        "lol_urgot_e_native": "UrgotENativeEffect",
        "lol_urgot_r_check_native": "UrgotRCheckNativeEffect",
        "lol_urgot_r_execute_native": "UrgotRExecuteNativeEffect",
    }
    for effect_ref, implementation in expected.items():
        assert re.search(
            rf'registration\.add_native_effect\(\s*"{effect_ref}",\s*'
            rf"{implementation}\s*,?\s*\);",
            source,
        )
        assert f"struct {implementation};" in source
    assert "replace_champion" not in source


def test_urgot_localization_view_style_and_vfx_routes_are_wired():
    i18n = load_json("text/champion.i18n")
    assert i18n["en"]["description"]["demon"]["name"] == "Urgot"
    assert i18n["zh-hans"]["description"]["demon"]["name"] == "厄加特"
    assert i18n["zh-hant"]["description"]["demon"]["name"] == "厄加特"
    assert i18n["ja"]["description"]["demon"]["name"] == "アーゴット"

    style = load_json("style/champion_view.champion_view")
    assert style["entries"]["demon"]["face"] == {"x": 0, "y": -34}
    assert style["entries"]["demon"]["center"] == {"x": 0, "y": -12}

    champion = load_json("champion/demon.data_champion")
    serialized = json.dumps(champion, ensure_ascii=False)
    for effect_asset in (
        "asset/lol_mod/aseprite_resources/effects/urgot_attack",
        "asset/lol_mod/aseprite_resources/effects/urgot_w_cannon",
        "asset/lol_mod/aseprite_resources/effects/urgot_e_disdain",
        "asset/lol_mod/aseprite_resources/effects/urgot_r_chain",
        "asset/lol_mod/aseprite_resources/effects/urgot_r_execute",
    ):
        assert effect_asset in serialized

    expected_sfx = {
        "lol_urgot_attack_cast",
        "lol_urgot_attack_hit",
        "lol_urgot_w_cast",
        "lol_urgot_w_shot",
        "lol_urgot_e_cast",
        "lol_urgot_e_hit",
        "lol_urgot_r_cast",
        "lol_urgot_r_latch",
        "lol_urgot_r_pull",
        "lol_urgot_r_execute",
        "lol_urgot_r_fear",
    }
    assert expected_sfx.issubset(
        {effect["name"] for effect in find_effect(champion, "Sfx")}
        | {effect["name"] for effect in find_effect(champion, "TargetSfx")}
    )

    for binding in [*champion["view_projectiles"], *champion["view_effects"]]:
        anim_path = (
            MOD
            / (
                binding["anim"].removeprefix("asset/lol_mod/")
                + "#anim.fanim"
            )
        )
        anim = json.loads(anim_path.read_text(encoding="utf-8"))
        assert binding["tag"] in anim["anims"], binding
