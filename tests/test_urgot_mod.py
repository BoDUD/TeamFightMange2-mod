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
    w_copy_contract = {
        "en": ("one valid non-tower enemy", "96 + 240% Attack", "chosen direction", "12 rapid pulses"),
        "zh-hans": (
            "\u4e00\u4e2a\u5408\u6cd5\u7684\u975e\u9632\u5fa1\u5854\u654c\u4eba",
            "96 + 240%\u653b\u51fb\u529b",
            "\u9009\u5b9a\u65b9\u5411",
            "\u5feb\u901f\u653b\u51fb12\u6b21",
        ),
        "zh-hant": (
            "\u4e00\u500b\u5408\u6cd5\u7684\u975e\u9632\u79a6\u5854\u6575\u4eba",
            "96 + 240%\u653b\u64ca\u529b",
            "\u9078\u5b9a\u65b9\u5411",
            "\u5feb\u901f\u653b\u64ca12\u6b21",
        ),
        "ja": (
            "\u6709\u52b9\u306a\u30bf\u30ef\u30fc\u4ee5\u5916\u306e\u65751\u4f53",
            "96 + \u653b\u6483\u529b\u306e240%",
            "\u6307\u5b9a\u65b9\u5411",
            "\u8a0812\u56de",
        ),
        "ko": (
            "\uc720\ud6a8\ud55c \ud3ec\ud0d1\uc774 \uc544\ub2cc \uc801 \ud558\ub098",
            "96 + \uacf5\uaca9\ub825\uc758 240%",
            "\uc9c0\uc815\ud55c \ubc29\ud5a5",
            "\ucd1d 12\ud68c\uc758",
        ),
    }
    for locale, (target_copy, damage_copy, retired_direction_copy, retired_pulse_copy) in w_copy_contract.items():
        text = i18n[locale]["description"]["demon"]
        assert text["name"]
        assert text["skill"].lstrip().startswith("W")
        assert text["skill2"].lstrip().startswith("E")
        assert text["ult"].lstrip().startswith("R")
        assert not text["skill"].lstrip().startswith("Q")
        assert target_copy in text["skill"]
        assert damage_copy in text["skill"]
        assert retired_direction_copy not in text["skill"]
        assert retired_pulse_copy not in text["skill"]


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

    passive_impl = re.search(
        r"impl ModEffectType for UrgotPassiveNativeEffect \{(?P<body>.*?)\n\}",
        source,
        re.DOTALL,
    )
    assert passive_impl
    body = passive_impl.group("body")
    caster_snapshot = body.index(
        ".map(|caster| (caster.handle(), caster.stat().attack, caster.is_alive()))"
    )
    caster_reject = body.index("if !caster_alive")
    target_snapshot = body.index(
        ".map(|target| (target.hp().max, target.is_alive()))"
    )
    target_reject = body.index("if !target_alive || target_max_hp == 0")
    cooldown_write = min(
        body.index("cooldown.ready_tick ="), body.index("cooldowns.push(")
    )
    deal_damage = body.index(
        "ctx.deal_damage(caster_id, target_id, damage, 0, AttackType::Skill);"
    )
    assert (
        caster_snapshot
        < caster_reject
        < target_snapshot
        < target_reject
        < cooldown_write
        < deal_damage
    )


def test_w_is_one_short_data_attack_without_scheduler_native_or_body_overlay():
    champion = load_json("champion/demon.data_champion")
    w = champion["skill"]
    assert w["cooltime"] == 600
    assert (
        w["action_name"],
        w["duration"],
        w["start_timing"],
        w["cancelable"],
        w["range"],
        w["casting_type"],
        w["casting_target"],
        w["can_use_with_move"],
    ) == (
        "attack",
        16,
        1,
        False,
        60000,
        "Targeting",
        "EnemyWithoutTower",
        False,
    )
    assert not find_effect(w, "CasterAnimation")
    assert not find_effect(w, "CasterViewEffect")
    assert not find_effect(w, "ViewEffect")
    assert not find_effect(w, "TargetSfx")

    purge = find_effect(w, "AddCasterBuff")
    assert len(purge) == 1
    buff = purge[0]["buff_state"]
    assert buff["name"] == "lol_urgot_w_purge"
    assert buff["duration"]["Time"]["tick"] == 240
    assert buff["move_speed_mult"] == -12
    assert buff["defence"] == 20
    assert buff["magic_resistance"] == 10

    # Every scheduled/native/projectile W route froze in live play. The stable
    # fallback compresses the old twelve 8 + 20% pulses into one engine-owned
    # 96 + 240% Attack hit against the action's validated non-tower target.
    serialized_w = json.dumps(w)
    assert "Projectile" not in serialized_w
    for forbidden_type in (
        "RangePeriod",
        "RangePeriodProjectile",
        "AddCasted",
        "Delayed",
        "Native",
    ):
        assert not find_effect(w, forbidden_type)
    assert find_effect(w, "Attack") == [
        {"type": "Attack", "damage": 96, "attack_ratio": 240}
    ]
    assert find_effect(w, "Sfx") == [
        {"type": "Sfx", "name": "lol_urgot_w_cast"},
        {"type": "Sfx", "name": "lol_urgot_w_shot"},
    ]

    source = RUST_PATH.read_text(encoding="utf-8")
    for retired_symbol in (
        "URGOT_W_CHANNEL_TICKS",
        "URGOT_W_CHANNELS",
        "URGOT_W_SHOT_LOCK_TICKS",
        "URGOT_W_BLOCK_ATTACK_TICKS",
        "UrgotWChannelState",
        "UrgotWNativeEffect",
        "UrgotWCancelNativeEffect",
        "UrgotWShotGateNativeEffect",
        "lol_urgot_w_cancel_native",
        "lol_urgot_w_shot_gate_native",
        "lol_urgot_w_shot_ready",
        "URGOT_W_RANGE",
        "URGOT_W_FLAT_DAMAGE",
        "URGOT_W_ATTACK_RATIO_PERCENT",
        "UrgotWPulseNativeEffect",
        "lol_urgot_w_pulse_native",
        "UrgotAbilityInputGate",
    ):
        assert retired_symbol not in source

    # No runtime W projectile/effect binding or skill1 animation may resurrect
    # the rejected body-covering machine-gun presentation.
    assert champion["view_buffs"] == []
    runtime_views = [*champion["view_projectiles"], *champion["view_effects"]]
    assert all(not view.get("name", "").startswith("lol_urgot_w_") for view in runtime_views)
    assert "asset/lol_mod/aseprite_resources/effects/urgot_w_cannon" not in json.dumps(runtime_views)


def test_urgot_uses_engine_data_ai_without_the_panicking_input_gate():
    source = RUST_PATH.read_text(encoding="utf-8")
    # Mod API Input::Attack can carry Target, Dir, Pos or None. Reusing that
    # value in a Targeting Ult/Skill validity call produced the first-contact
    # Option::unwrap(None) path, so Urgot no longer has a Rust input AI at all.
    for retired_gate_token in (
        "struct UrgotAbilityInputGate",
        "impl ModPlayerInputAi for UrgotAbilityInputGate",
        "registration.add_player_input_ai(UrgotAbilityInputGate);",
        '"lol_urgot_ability_input_gate"',
    ):
        assert retired_gate_token not in source


def test_r_clears_persistent_purge_before_launching():
    champion = load_json("champion/demon.data_champion")
    r = champion["ult"]
    top_level = r["effect"]["effects"]
    assert top_level[0] == {"type": "RemoveCasterBuff", "name": "lol_urgot_w_purge"}
    assert "lol_urgot_w_cancel_native" not in json.dumps(r)
    assert "lol_urgot_w_shot_ready" not in json.dumps(r)


def test_e_uses_a_pure_data_cross_then_knockback_flip_contract():
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
    assert find_effect(rush, "Knockback") == [
        {"type": "Knockback", "speed": 2600, "tick": 8}
    ]
    assert find_effect(rush, "Airborne") == [
        {"type": "Airborne", "duration": 60}
    ]
    assert [effect["type"] for effect in rush["applied_effects"]] == [
        "Attack",
        "Knockback",
        "Airborne",
        "ViewEffect",
        "TargetSfx",
    ]
    assert not find_effect(e, "Native")
    assert not find_effect(e, "Delayed")
    assert not find_effect(e, "Grab")

    source = RUST_PATH.read_text(encoding="utf-8")
    assert "URGOT_E_STUN_TICKS" not in source
    assert "UrgotENativeEffect" not in source
    assert "lol_urgot_e_native" not in source


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
    assert 'let Ok(name) = "lol_urgot_r_execute_ready".try_into()' in check_body
    assert "ready.name = name;" in check_body
    assert "ctx.add_buff(caster_id, ready);" in check_body
    threshold_reject = check_body.index("if target_hp.current > execute_limit")
    check_caster = check_body.index(".get_entity(caster_id)")
    check_caster_alive = check_body.index(
        ".is_some_and(|caster| caster.is_alive())"
    )
    ready_marker = check_body.index(
        'let Ok(name) = "lol_urgot_r_execute_ready".try_into()'
    )
    ready_add_buff = check_body.index("ctx.add_buff(caster_id, ready);")
    assert (
        threshold_reject
        < check_caster
        < check_caster_alive
        < ready_marker
        < ready_add_buff
    )

    execute_impl = re.search(
        r"impl ModEffectType for UrgotRExecuteNativeEffect \{(?P<body>.*?)\n\}",
        source,
        re.DOTALL,
    )
    assert execute_impl
    body = execute_impl.group("body")
    caster_lookups = [
        match.start() for match in re.finditer(r"\.get_entity\(caster_id\)", body)
    ]
    caster_alive_checks = [
        match.start()
        for match in re.finditer(
            r"\.is_some_and\(\|caster\| caster\.is_alive\(\)\)", body
        )
    ]
    assert len(caster_lookups) == 2
    assert len(caster_alive_checks) == 2
    deal_damage = body.index(
        "ctx.deal_damage(caster_id, target_id, lethal_damage, 0, AttackType::Skill);"
    )
    confirm = body.index(".is_some_and(|target| !target.is_alive())")
    reject = body.index("if !executed")
    marker = body.index(
        'let Ok(name) = "lol_urgot_r_execute_success".try_into()'
    )
    add_buff = body.index("ctx.add_buff(caster_id, success);")
    assert (
        caster_lookups[0]
        < caster_alive_checks[0]
        < deal_damage
        < confirm
        < reject
        < caster_lookups[1]
        < caster_alive_checks[1]
        < marker
        < add_buff
    )


def test_only_passive_and_r_urgot_native_effects_remain_registered():
    source = RUST_PATH.read_text(encoding="utf-8")
    expected = {
        "lol_urgot_passive_native": "UrgotPassiveNativeEffect",
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
    assert "lol_urgot_w_pulse_native" not in source
    assert "UrgotWPulseNativeEffect" not in source
    assert "lol_urgot_e_native" not in source
    assert "UrgotENativeEffect" not in source
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
        "asset/lol_mod/aseprite_resources/effects/urgot_e_disdain",
        "asset/lol_mod/aseprite_resources/effects/urgot_r_chain",
        "asset/lol_mod/aseprite_resources/effects/urgot_r_execute",
    ):
        assert effect_asset in serialized
    assert "asset/lol_mod/aseprite_resources/effects/urgot_w_cannon" not in serialized

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
    # The stable fallback has one cast cue and one immediate shot cue; neither
    # is dispatched from a delayed/native/projectile callback.
    assert len(find_effect(champion["skill"], "Sfx", name="lol_urgot_w_shot")) == 1

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
