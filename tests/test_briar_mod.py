from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import wave

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
MOD = ROOT / "mods" / "lol_mod"


BRIAR_NATIVE_ANIMATION: dict[str, list[float]] = {
    "idle": [0.18, 0.14, 0.14, 0.14],
    "berserk_idle": [0.18, 0.14, 0.14, 0.14],
    "run": [0.080000006] * 8,
    "berserk_run": [0.080000006] * 8,
    "attack": [0.080000006] * 5,
    "attack2": [0.080000006] * 5,
    "berserk_attack": [0.060000002] * 5,
    "skill1": [0.080000006] * 3,
    "skill2": [0.080000006] * 4,
    "skill2_berserk": [0.080000006] * 4,
    "skill2_effect": [0.080000006] * 4,
    "skill1_effect_old": [0.080000006] * 7,
    "ult": [0.080000006] * 5,
    "berserk_ult": [0.080000006] * 5,
    "ult_pre": [0.080000006],
    "berserk_ult_pre": [0.080000006],
    "ult_dash": [0.080000006],
    "berserk_ult_dash": [0.080000006],
    "ult_attack": [0.080000006] * 3,
    "berserk_ult_attack": [0.080000006] * 3,
    "hit": [0.1],
    "berserk_hit": [0.1],
    "dead": [0.1] * 10,
    "berserk_dead": [0.1] * 10,
}


BRIAR_AUDIO_EVENTS: dict[str, str] = {
    "lol_briar_attack_cast": "briar_attack_cast",
    "lol_briar_attack_hit": "briar_attack_hit",
    "lol_briar_frenzy_cast": "briar_frenzy_cast",
    "lol_briar_frenzy_hit": "briar_frenzy_hit",
    "lol_briar_q_cast": "briar_q_cast",
    "lol_briar_e_cast": "briar_e_cast",
    "lol_briar_e_hit": "briar_e_hit",
    "lol_briar_r_cast": "briar_r_cast",
    "lol_briar_r_hit": "briar_r_hit",
}


BRIAR_RUNTIME_PATHS = {
    "champion/berserker.data_champion",
    "aseprite_resources/champions/briar#sheet.png",
    "aseprite_resources/champions/briar#anim.fanim",
    "icons/briar_skill.png",
    "icons/briar_skill2.png",
    "icons/briar_ult.png",
    "aseprite_resources/effects/briar_bleed#sheet.png",
    "aseprite_resources/effects/briar_bleed#anim.fanim",
    "aseprite_resources/effects/briar_q_overhead#sheet.png",
    "aseprite_resources/effects/briar_q_overhead#anim.fanim",
    "aseprite_resources/effects/briar_frenzy#sheet.png",
    "aseprite_resources/effects/briar_frenzy#anim.fanim",
    "aseprite_resources/effects/briar_e_scream#sheet.png",
    "aseprite_resources/effects/briar_e_scream#anim.fanim",
    "aseprite_resources/effects/briar_r_mark#sheet.png",
    "aseprite_resources/effects/briar_r_mark#anim.fanim",
    "aseprite_resources/effects/briar_r_trail#sheet.png",
    "aseprite_resources/effects/briar_r_trail#anim.fanim",
    "aseprite_resources/effects/briar_r_arrival#sheet.png",
    "aseprite_resources/effects/briar_r_arrival#anim.fanim",
    "ui/champion_fullbody/berserker.png",
    "ui/champion_portrait/berserker_compact.png",
    "ui/champion_portrait/berserker_scoreboard.png",
    "ui/champion_portrait/berserker_grid.png",
    "style/champion_view.champion_view",
    "text/champion.i18n",
    "mod.mod_info",
    "mod.override_info",
    *{
        f"sound/sfx/{stem}{suffix}"
        for stem in BRIAR_AUDIO_EVENTS.values()
        for suffix in (".sound_info", "_clip.wav")
    },
}


BRIAR_IMAGEGEN_SOURCES = {
    "source/imagegen/briar_actor_contact.png",
    "source/imagegen/briar_run_contact.png",
    "source/imagegen/briar_q_icon_source.png",
    "source/imagegen/briar_e_icon_source.png",
    "source/imagegen/briar_r_icon_source.png",
    "source/imagegen/briar_bleed_vfx_contact.png",
    "source/imagegen/champions/004_briar/briar_q_overhead_v1_source.png",
    "source/imagegen/briar_frenzy_vfx_contact.png",
    "source/imagegen/briar_e_vfx_contact.png",
    "source/imagegen/briar_r_vfx_contact.png",
    "source/processed/briar_actor_contact_alpha.png",
    "source/processed/briar_run_contact_alpha.png",
    "source/processed/briar_bleed_vfx_contact_alpha.png",
    "source/processed/champions/004_briar/briar_q_overhead_v1_alpha.png",
    "source/processed/briar_frenzy_vfx_contact_alpha.png",
    "source/processed/briar_e_vfx_contact_alpha.png",
    "source/processed/briar_r_vfx_contact_alpha.png",
    "qa/briar_actor_contact_final.png",
    "qa/briar_skill_icons_final.png",
    "qa/briar_vfx_contact_final.png",
    "qa/briar_hd_surface_qa.json",
    "qa/briar_portrait_surface_final.png",
}


def load_json(relative: str):
    return json.loads((MOD / relative).read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def walk_effects(value):
    if isinstance(value, dict):
        if isinstance(value.get("type"), str):
            yield value
        for child in value.values():
            yield from walk_effects(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk_effects(child)


def find_effect(root, effect_type: str, **fields):
    return [
        effect
        for effect in walk_effects(root)
        if effect.get("type") == effect_type
        and all(effect.get(key) == value for key, value in fields.items())
    ]


def direct_effects(effect: dict, effect_type: str) -> list[dict]:
    return [child for child in effect.get("effects", []) if child.get("type") == effect_type]


def buff_by_name(root, effect_type: str, name: str) -> list[dict]:
    return [
        effect
        for effect in find_effect(root, effect_type)
        if effect.get("buff_state", {}).get("name") == name
    ]


def assert_crimson_curse(casted: dict) -> None:
    assert (casted["duration"], casted["period"], casted["casted_type"]) == (
        120,
        60,
        "Bleed",
    )
    assert casted["duration"] // casted["period"] == 2
    dot_attacks = direct_effects(casted, "Attack")
    assert [(effect["damage"], effect["attack_ratio"]) for effect in dot_attacks] == [(4, 3)]
    caster_heals = direct_effects(casted, "Heal")
    assert caster_heals == [
        {
            "type": "Heal",
            "amount": 2,
            "attack_ratio": 1,
            "ap_ratio": 0,
            "heal_type": "Caster",
        }
    ]


def test_briar_replaces_same_id_berserker_once_and_exposes_only_q_e_r() -> None:
    champions = [
        (path.name, json.loads(path.read_text(encoding="utf-8")))
        for path in sorted((MOD / "champion").glob("*.data_champion"))
    ]
    assert [name for name, champion in champions if champion.get("id") == "berserker"] == [
        "berserker.data_champion"
    ]
    assert all(champion.get("id") != "lol_briar" for _, champion in champions)
    assert not (MOD / "champion/lol_briar.data_champion").exists()

    briar = load_json("champion/berserker.data_champion")
    assert briar["id"] == "berserker"
    assert briar["sprite"] == "asset/lol_mod/aseprite_resources/champions/briar"
    assert briar["anim_prefix"] == ""
    assert briar["category"] == "Melee"
    assert set(briar["tags"]) == {"AD", "Melee", "Heal", "Dot", "CC"}
    assert briar["skill_icons"] == [
        "asset/lol_mod/icons/briar_skill",
        "asset/lol_mod/icons/briar_skill2",
        "asset/lol_mod/icons/briar_ult",
    ]
    assert len(briar["skill_icons"]) == 3
    assert [briar[key]["action_name"] for key in ("skill", "skill2", "ult")] == [
        "skill1",
        "skill2",
        "ult",
    ]
    assert not {"w", "skill3", "skill4"}.intersection(briar)


def test_briar_stats_and_action_slots_match_the_approved_contract() -> None:
    briar = load_json("champion/berserker.data_champion")
    assert briar["stat"] == {
        "attack": 115,
        "magic_power": 0,
        "hp": 950,
        "defence": 25,
        "magic_resistance": 18,
        "move_speed": 1100,
        "hp_regen": 0,
        "stack": 0,
        "crit_chance": 0,
    }
    assert briar["growth"] == {
        "attack": 20,
        "magic_power": 0,
        "hp": 100,
        "defence": 7,
        "magic_resistance": 4,
        "move_speed": 10,
        "hp_regen": 0,
        "stack": 0,
        "crit_chance": 0,
    }
    assert (
        briar["attack"]["range"],
        briar["attack"]["cooltime"],
        briar["attack"]["duration"],
        briar["attack"]["start_timing"],
        briar["attack"]["casting_target"],
    ) == (25000, 50, 24, 12, "Enemy")
    assert (
        briar["skill"]["range"],
        briar["skill"]["cooltime"],
        briar["skill"]["duration"],
        briar["skill"]["start_timing"],
        briar["skill"]["casting_type"],
        briar["skill"]["casting_target"],
    ) == (45000, 360, 20, 8, "Targeting", "EnemyChampion")
    assert (
        briar["skill2"]["range"],
        briar["skill2"]["cooltime"],
        briar["skill2"]["duration"],
        briar["skill2"]["start_timing"],
        briar["skill2"]["casting_type"],
        briar["skill2"]["casting_target"],
    ) == (50000, 480, 54, 1, "Direction", "EnemyWithoutTower")
    assert (
        briar["ult"]["range"],
        briar["ult"]["cooltime"],
        briar["ult"]["duration"],
        briar["ult"]["start_timing"],
        briar["ult"]["casting_type"],
        briar["ult"]["casting_target"],
    ) == (80000, 3600, 48, 1, "Targeting", "EnemyChampion")


def test_briar_passive_bleeds_for_two_ticks_and_heals_the_original_caster() -> None:
    briar = load_json("champion/berserker.data_champion")
    attack_bleeds = find_effect(briar["attack"], "AddCasted")
    e_bleeds = find_effect(briar["skill2"], "AddCasted")
    r_bleeds = find_effect(briar["ult"], "AddCasted")
    assert (len(attack_bleeds), len(e_bleeds), len(r_bleeds)) == (2, 1, 1)
    for casted in [*attack_bleeds, *e_bleeds, *r_bleeds]:
        assert_crimson_curse(casted)

    curse_markers = [
        effect
        for effect in find_effect(briar, "AddBuff")
        if effect.get("buff_state", {}).get("name") == "lol_briar_crimson_curse"
    ]
    assert len(curse_markers) == 4
    assert all(
        marker["buff_state"]["duration"]["Time"]["tick"] == 120
        for marker in curse_markers
    )


def test_briar_attack_switches_on_snack_and_consumes_exactly_one_empowerment() -> None:
    attack = load_json("champion/berserker.data_champion")["attack"]
    switch = attack["effect"]
    assert switch["type"] == "SwitchByBuff"
    assert switch["buff_name"] == "lol_briar_snack_ready"

    normal = switch["effect_none"]
    empowered = switch["effect_buff"]
    normal_direct_attacks = direct_effects(normal, "Attack")
    empowered_direct_attacks = direct_effects(empowered, "Attack")
    assert [(effect["damage"], effect["attack_ratio"]) for effect in normal_direct_attacks] == [
        (0, 100)
    ]
    assert [
        (effect["damage"], effect["attack_ratio"], effect.get("target_hp_ratio", 0))
        for effect in empowered_direct_attacks
    ] == [(0, 100, 0), (25, 40, 2)]
    assert direct_effects(normal, "RemoveCasterBuff") == []
    assert direct_effects(empowered, "RemoveCasterBuff") == [
        {"type": "RemoveCasterBuff", "name": "lol_briar_snack_ready"}
    ]
    assert direct_effects(empowered, "Heal") == [
        {
            "type": "Heal",
            "amount": 40,
            "attack_ratio": 15,
            "ap_ratio": 0,
            "heal_type": "Caster",
        }
    ]
    assert len(find_effect(normal, "AddCasted")) == 1
    assert len(find_effect(empowered, "AddCasted")) == 1


def test_briar_q_and_r_frenzy_states_are_mutually_exclusive() -> None:
    briar = load_json("champion/berserker.data_champion")
    q_switches = find_effect(
        briar["skill"], "SwitchByBuff", buff_name="lol_briar_certain_death_frenzy"
    )
    assert len(q_switches) == 1
    q_switch = q_switches[0]

    q_base = q_switch["effect_none"]
    q_during_r = q_switch["effect_buff"]
    assert {
        effect["buff_state"]["name"]
        for effect in direct_effects(q_base, "AddCasterBuff")
    } == {"lol_briar_blood_frenzy", "lol_briar_snack_ready"}
    assert {
        effect["buff_state"]["name"]
        for effect in direct_effects(q_during_r, "AddCasterBuff")
    } == {"lol_briar_snack_ready"}
    assert not buff_by_name(q_during_r, "AddCasterBuff", "lol_briar_blood_frenzy")

    base_frenzy = buff_by_name(q_base, "AddCasterBuff", "lol_briar_blood_frenzy")
    assert len(base_frenzy) == 1
    assert base_frenzy[0]["buff_state"] == {
        "name": "lol_briar_blood_frenzy",
        "duration": {"Time": {"tick": 180}},
        "attack_speed_mult": 60,
        "move_speed_mult": 18,
        "vamp": 25,
    }

    move_to_target = find_effect(briar["ult"], "MoveToTarget")
    assert len(move_to_target) == 1
    end_effects = move_to_target[0]["end_effects"]
    removed = {
        effect["name"]
        for effect in end_effects
        if effect.get("type") == "RemoveCasterBuff"
    }
    assert removed == {
        "lol_briar_blood_frenzy",
        "lol_briar_certain_death_frenzy",
        "lol_briar_snack_ready",
    }
    added = {
        effect["buff_state"]["name"]: effect["buff_state"]
        for effect in end_effects
        if effect.get("type") == "AddCasterBuff"
    }
    assert set(added) == {"lol_briar_certain_death_frenzy", "lol_briar_snack_ready"}
    assert added["lol_briar_certain_death_frenzy"] == {
        "name": "lol_briar_certain_death_frenzy",
        "duration": {"Time": {"tick": 240}},
        "attack_speed_mult": 50,
        "move_speed_mult": 25,
        "vamp": 30,
        "defence": 20,
        "magic_resistance": 20,
        "toughness": 20,
    }


def test_briar_q_uses_a_short_target_following_overhead_vfx_without_a_body_ring() -> None:
    briar = load_json("champion/berserker.data_champion")
    q = briar["skill"]
    assert [effect["type"] for effect in q["effect"]["effects"]] == [
        "Sfx",
        "CasterAnimation",
        "ViewEffect",
        "SwitchByBuff",
    ]
    assert direct_effects(q["effect"], "ViewEffect") == [
        {"type": "ViewEffect", "name": "lol_briar_q_overhead_visual"}
    ]

    q_view = next(
        view
        for view in briar["view_effects"]
        if view["name"] == "lol_briar_q_overhead_visual"
    )
    assert q_view == {
        "type": "Animation",
        "name": "lol_briar_q_overhead_visual",
        "anim": "asset/lol_mod/aseprite_resources/effects/briar_q_overhead",
        "tag": "impact",
        "z": 2,
        "is_follow": True,
    }
    assert {buff["name"] for buff in briar["view_buffs"]} == {
        "lol_briar_certain_death_frenzy"
    }

    anim = load_json("aseprite_resources/effects/briar_q_overhead#anim.fanim")
    frames = anim["anims"]["impact"]["frames"]
    assert len(frames) == 8
    assert [frame["duration"] for frame in frames] == [
        0.04,
        0.04,
        0.05,
        0.05,
        0.06,
        0.06,
        0.07,
        0.09,
    ]
    sheet = Image.open(MOD / "aseprite_resources/effects/briar_q_overhead#sheet.png").convert(
        "RGBA"
    )
    assert sheet.size == (512, 64)
    for index in range(8):
        frame = sheet.crop((index * 64, 0, (index + 1) * 64, 64))
        bbox = frame.getchannel("A").getbbox()
        assert bbox is not None
        assert bbox[2] - bbox[0] <= 30
        assert bbox[3] - bbox[1] <= 22
        assert bbox[1] >= 2
        assert bbox[3] <= 24

    # The Q actor pose keeps the same source index and frame contract, but no
    # longer contains the generated yellow/orange bracket pixels.
    actor = Image.open(MOD / "aseprite_resources/champions/briar#sheet.png").convert("RGBA")
    q_break = actor.crop((6 * 64, 0, 7 * 64, 64))
    q_pixels = q_break.tobytes()
    assert not any(
        q_pixels[offset + 3]
        and q_pixels[offset] >= 110
        and q_pixels[offset + 1] >= 55
        and q_pixels[offset + 2] <= 80
        and q_pixels[offset + 1] * 100 >= q_pixels[offset] * 35
        for offset in range(0, len(q_pixels), 4)
    )


def test_briar_e_delays_one_heal_and_releases_one_line_hitbox() -> None:
    e = load_json("champion/berserker.data_champion")["skill2"]
    root_effects = e["effect"]["effects"]
    root_heals = [effect for effect in root_effects if effect.get("type") == "Heal"]
    assert root_heals == [
        {
            "type": "Heal",
            "amount": 50,
            "attack_ratio": 15,
            "ap_ratio": 0,
            "heal_type": "Caster",
        }
    ]
    guards = [
        effect
        for effect in root_effects
        if effect.get("type") == "AddCasterBuff"
        and effect.get("buff_state", {}).get("name") == "lol_briar_chilling_scream_guard"
    ]
    assert len(guards) == 1
    assert guards[0]["buff_state"] == {
        "name": "lol_briar_chilling_scream_guard",
        "duration": {"Time": {"tick": 30}},
        "damaged_reduce": 35,
    }

    delays = [
        effect
        for effect in root_effects
        if effect.get("type") == "Delayed" and effect.get("tick") == 30
    ]
    assert len(delays) == 1
    line_hitboxes = direct_effects(delays[0], "LineRangeProjectile")
    assert len(line_hitboxes) == 1
    line = line_hitboxes[0]
    assert (
        line["width"],
        line["length"],
        line["delay"],
        line["apply"],
        line["applied_target"],
    ) == (24000, 50000, 0, 1, "EnemyWithoutTower")
    assert len(line["applied_effects"]) == 1
    assert line["applied_effects"][0]["casting_type"] == "Targeting"
    hit = line["applied_effects"][0]["effect"]
    assert direct_effects(hit, "Attack") == [
        {"type": "Attack", "damage": 75, "attack_ratio": 100}
    ]
    assert direct_effects(hit, "Knockback") == [
        {"type": "Knockback", "speed": 3000, "tick": 12}
    ]
    assert direct_effects(hit, "Airborne") == [
        {"type": "Airborne", "duration": 18}
    ]
    assert len(find_effect(hit, "AddCasted")) == 1
    assert not direct_effects(delays[0], "Heal")


def test_briar_r_warns_then_resolves_damage_fear_and_frenzy_only_on_arrival() -> None:
    ult = load_json("champion/berserker.data_champion")["ult"]
    root_effects = ult["effect"]["effects"]
    assert [effect["type"] for effect in root_effects] == [
        "Sfx",
        "ViewEffect",
        "CasterAnimation",
        "Delayed",
    ]
    assert root_effects[2] == {"type": "CasterAnimation", "name": "ult_pre", "tick": 18}
    warning_delays = [
        effect
        for effect in root_effects
        if effect.get("type") == "Delayed" and effect.get("tick") == 18
    ]
    assert len(warning_delays) == 1
    warning = warning_delays[0]
    assert [effect["type"] for effect in warning["effects"]] == [
        "CasterAnimation",
        "CasterViewEffect",
        "MoveToTarget",
    ]

    moves = direct_effects(warning, "MoveToTarget")
    assert len(moves) == 1
    move = moves[0]
    assert (move["speed"], move["range"]) == (6000, 80000)
    arrival = move["end_effects"]
    arrival_attacks = [effect for effect in arrival if effect.get("type") == "Attack"]
    assert arrival_attacks == [{"type": "Attack", "damage": 100, "attack_ratio": 120}]
    assert len(find_effect(arrival, "AddCasted")) == 1

    fear_ranges = [effect for effect in arrival if effect.get("type") == "RangeEffect"]
    assert len(fear_ranges) == 1
    fear_range = fear_ranges[0]
    assert (
        fear_range["shape"]["Circle"]["radius"],
        fear_range["target"],
        fear_range["apply_type"],
    ) == (30000, "EnemyChampion", "AroundCaster")
    assert direct_effects(fear_range, "Fear") == [{"type": "Fear", "tick": 30}]
    assert len(buff_by_name(arrival, "AddCasterBuff", "lol_briar_certain_death_frenzy")) == 1

    assert not find_effect(root_effects[:-1], "Attack")
    assert not find_effect(root_effects[:-1], "Fear")
    assert not buff_by_name(root_effects[:-1], "AddCasterBuff", "lol_briar_certain_death_frenzy")


def test_briar_preserves_all_24_native_animation_tags_and_timings() -> None:
    anim = load_json("aseprite_resources/champions/briar#anim.fanim")
    assert len(BRIAR_NATIVE_ANIMATION) == 24
    assert set(anim["anims"]) == set(BRIAR_NATIVE_ANIMATION)
    for tag, expected_durations in BRIAR_NATIVE_ANIMATION.items():
        frames = anim["anims"][tag]["frames"]
        assert len(frames) == len(expected_durations), tag
        assert all(
            math.isclose(float(frame["duration"]), expected, rel_tol=0, abs_tol=1e-6)
            for frame, expected in zip(frames, expected_durations, strict=True)
        ), tag


def test_briar_style_localization_and_imagegen_sources_are_registered() -> None:
    style = load_json("style/champion_view.champion_view")
    assert style["entries"]["berserker"] == {
        "face": {"x": 5, "y": -32},
        "center": {"x": 0, "y": -12},
    }

    text = load_json("text/champion.i18n")
    assert text["zh-hans"]["description"]["berserker"]["name"] == "贝蕾亚"
    assert text["zh-hant"]["description"]["berserker"]["name"] == "貝蕾亞"
    assert text["en"]["description"]["berserker"]["name"] == "Briar"
    for locale in ("en", "zh-hans", "zh-hant", "ja", "ko"):
        description = text[locale]["description"]["berserker"]
        assert set(description) == {"name", "attack", "skill", "skill2", "ult"}
        assert all(isinstance(value, str) and value.strip() for value in description.values())

    for relative in BRIAR_IMAGEGEN_SOURCES:
        path = MOD / relative
        assert path.is_file() and path.stat().st_size > 0, relative
    prompt_record = MOD / "source/imagegen/PROMPTS.md"
    assert prompt_record.is_file()
    assert "Briar" in prompt_record.read_text(encoding="utf-8")


def test_briar_hd_actor_and_source_direct_surfaces_keep_face_scale_and_name_clearance() -> None:
    actor = Image.open(MOD / "aseprite_resources/champions/briar#sheet.png").convert(
        "RGBA"
    )
    anim = load_json("aseprite_resources/champions/briar#anim.fanim")["anims"]
    for tag in (
        "idle",
        "berserk_idle",
        "run",
        "berserk_run",
        "attack",
        "attack2",
        "berserk_attack",
        "skill1",
        "skill2",
        "ult",
        "hit",
    ):
        for row in anim[tag]["frames"]:
            data = row["data"]
            frame = actor.crop(
                (
                    data["x"],
                    data["y"],
                    data["x"] + data["w"],
                    data["y"] + data["h"],
                )
            )
            bbox = frame.getchannel("A").getbbox()
            assert bbox is not None, tag
            assert bbox[2] - bbox[0] <= 58, tag
            # Horizontal lunge/throw poses can be shorter in visible height,
            # but they keep the same uniform source scale and never collapse
            # into the old tiny/effect-only class.
            assert 28 <= bbox[3] - bbox[1] <= 44, tag
            assert bbox[3] <= 46, tag

    first_idle = anim["idle"]["frames"][0]["data"]
    idle = actor.crop(
        (
            first_idle["x"],
            first_idle["y"],
            first_idle["x"] + first_idle["w"],
            first_idle["y"] + first_idle["h"],
        )
    )
    idle_bbox = idle.getchannel("A").getbbox()
    assert idle_bbox is not None
    assert idle_bbox[3] - idle_bbox[1] == 42
    assert idle_bbox[3] == 46

    surfaces = {
        "encyclopedia": ("ui/champion_fullbody/berserker.png", (64, 64)),
        "sidebar": ("ui/champion_portrait/berserker_compact.png", (64, 64)),
        "scoreboard": ("ui/champion_portrait/berserker_scoreboard.png", (64, 64)),
        "bp_grid": ("ui/champion_portrait/berserker_grid.png", (90, 122)),
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

    qa = load_json("qa/briar_hd_surface_qa.json")
    assert qa["champion"] == "Briar"
    assert qa["native_id"] == "berserker"
    assert qa["accepted_source"] == "source/processed/briar_actor_contact_alpha.png"
    assert qa["battle_actor"]["uniform_xy_scale"] is True
    assert qa["battle_actor"]["x_only_compression"] is False
    assert qa["surfaces"]["bp_grid"]["alpha_bbox"][3] <= 86
    assert qa["surfaces"]["bp_grid"]["name_band_clearance"] >= 10
    assert (MOD / "qa/briar_portrait_surface_final.png").is_file()

    runtime = (MOD / "src/lib.rs").read_text(encoding="utf-8")
    assert "rewrite_orianna_briar_portrait_render_commands(state);" in runtime
    assert "BRIAR_SCOREBOARD_PORTRAIT_TEXTURE" in runtime
    assert "BRIAR_BP_GRID_PORTRAIT_TEXTURE" in runtime


def test_briar_audio_events_resolve_to_official_mono_clips() -> None:
    briar = load_json("champion/berserker.data_champion")
    override = load_json("mod.override_info")
    triggered = {
        effect["name"]
        for effect in walk_effects(briar)
        if effect.get("type") in {"Sfx", "TargetSfx"}
    }
    assert triggered == set(BRIAR_AUDIO_EVENTS)

    for event, stem in BRIAR_AUDIO_EVENTS.items():
        assert override[f"asset/base/sound/sfx/{event}"] == {
            "remapping": f"asset/lol_mod/sound/sfx/{stem}",
            "type": "override",
        }
        sound_info = load_json(f"sound/sfx/{stem}.sound_info")
        assert sound_info["plays"] == [
            {"delay": 0.0, "clip": f"{stem}_clip", "volume": 1.0}
        ]
        assert override[f"asset/base/sound/sfx/{stem}_clip"] == {
            "remapping": f"asset/lol_mod/sound/sfx/{stem}_clip",
            "type": "override",
        }
        wav_path = MOD / f"sound/sfx/{stem}_clip.wav"
        with wave.open(str(wav_path), "rb") as wav:
            assert wav.getnchannels() == 1
            assert wav.getsampwidth() == 2
            assert wav.getframerate() == 44100
            assert wav.getnframes() > 0

    sources = load_json("qa/briar_official_audio_sources.json")
    outputs = {row["event_key"]: row for row in sources["outputs"]}
    assert set(outputs) == set(BRIAR_AUDIO_EVENTS.values())
    for stem, row in outputs.items():
        assert row["sound_info"] == f"sound/sfx/{stem}.sound_info"
        assert row["clip"] == f"{stem}_clip"
        assert row["volume"] == 1.0
        wav_path = MOD / row["wav"]["path"]
        assert wav_path.is_file()
        assert wav_path.stat().st_size == row["wav"]["size_bytes"]
        assert sha256(wav_path) == row["wav"]["sha256"]


def test_briar_runtime_assets_are_current_in_the_build_manifest() -> None:
    manifest = load_json("build_manifest.json")
    rows = {row["path"]: row for row in manifest["files"]}
    assert BRIAR_RUNTIME_PATHS.issubset(rows)
    for relative in BRIAR_RUNTIME_PATHS:
        path = MOD / relative
        assert path.is_file(), relative
        assert rows[relative]["size"] == path.stat().st_size, relative
        assert rows[relative]["sha256"] == sha256(path), relative
