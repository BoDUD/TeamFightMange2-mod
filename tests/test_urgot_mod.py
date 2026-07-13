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


def test_w_is_twelve_shots_over_240_ticks_with_movement_and_attack_lock():
    champion = load_json("champion/demon.data_champion")
    w = champion["skill"]
    assert w["cooltime"] == 600
    assert w["duration"] == 240
    assert w["can_use_with_move"] is True
    assert len(find_effect(w, "Native", effect_ref="lol_urgot_w_native")) == 1

    purge = find_effect(w, "AddCasterBuff")
    assert len(purge) == 1
    buff = purge[0]["buff_state"]
    assert buff["name"] == "lol_urgot_w_purge"
    assert buff["duration"]["Time"]["tick"] == 240
    assert buff["move_speed_mult"] == -12
    assert buff["defence"] == 20
    assert buff["magic_resistance"] == 10

    delayed = find_effect(w, "Delayed")
    assert sorted(effect["tick"] for effect in delayed) == list(range(0, 240, 20))
    projectiles = find_effect(
        w, "AutoTargetProjectile", name="lol_urgot_w_cannon_projectile"
    )
    assert len(projectiles) == 12
    for projectile in projectiles:
        assert projectile["speed"] == 7000
        assert projectile["range"] == 60000
        hits = find_effect(projectile, "Attack")
        assert len(hits) == 1
        assert hits[0]["damage"] == 8
        assert hits[0]["attack_ratio"] == 20

    source = RUST_PATH.read_text(encoding="utf-8")
    assert "const URGOT_W_BLOCK_ATTACK_TICKS: usize = 240;" in source
    assert "CCState::BlockAttack" in source


def test_e_shields_rushes_behind_and_flings_the_enemy_back():
    champion = load_json("champion/demon.data_champion")
    e = champion["skill2"]
    assert e["cooltime"] == 420
    assert e["casting_target"] == "EnemyChampion"

    shields = find_effect(e, "Shield")
    assert len(shields) == 1
    assert shields[0]["amount"] == 160
    assert shields[0]["attack_ratio"] == 70
    assert shields[0]["tick"] == 180

    rushes = find_effect(e, "RushMoveToBack")
    assert len(rushes) == 1
    rush = rushes[0]
    hit = find_effect(rush, "Attack")
    assert len(hit) == 1
    assert hit[0]["damage"] == 70
    assert hit[0]["attack_ratio"] == 90
    assert len(find_effect(rush, "Native", effect_ref="lol_urgot_e_native")) == 1
    knockback = find_effect(rush, "Knockback")
    assert knockback == [{"type": "Knockback", "speed": 2600, "tick": 8}]

    source = RUST_PATH.read_text(encoding="utf-8")
    assert "const URGOT_E_STUN_TICKS: u64 = 60;" in source
    assert re.search(
        r"impl ModEffectType for UrgotENativeEffect.*?CCState::Stun\s*\{\s*tick: URGOT_E_STUN_TICKS",
        source,
        re.DOTALL,
    )


def test_r_is_non_piercing_pull_and_true_25_percent_execute_check():
    champion = load_json("champion/demon.data_champion")
    r = champion["ult"]
    assert r["cooltime"] == 3000
    assert r["range"] == 90000
    projectile = find_effect(r, "LinearProjectile", name="lol_urgot_r_chain_projectile")
    assert len(projectile) == 1
    projectile = projectile[0]
    assert projectile["penetrate"] is False
    assert projectile["speed"] == 7000
    assert projectile["range"] == 90000

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
    assert find_effect(delayed[0], "Grab") == [
        {"type": "Grab", "speed": 7000, "tick": 12}
    ]
    assert len(find_effect(delayed[0], "Native", effect_ref="lol_urgot_r_native")) == 1

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
    execute_impl = re.search(
        r"impl ModEffectType for UrgotRNativeEffect \{(?P<body>.*?)\n\}",
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
        "lol_urgot_w_native": "UrgotWNativeEffect",
        "lol_urgot_e_native": "UrgotENativeEffect",
        "lol_urgot_r_native": "UrgotRNativeEffect",
    }
    for effect_ref, implementation in expected.items():
        assert (
            f'registration.add_native_effect("{effect_ref}", {implementation});'
            in source
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
