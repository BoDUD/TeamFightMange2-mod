from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import wave

from PIL import Image

from legacy_hd_assertions import (
    animation_frames,
    assert_actor_tag_scale,
    assert_legacy_hd_portrait_set,
    assert_readable_upper_detail,
    assert_uniform_aspect_ratio,
)


ROOT = Path(__file__).resolve().parents[1]
MOD = ROOT / "mods" / "lol_mod"


def load_json(relative: str):
    return json.loads((MOD / relative).read_text(encoding="utf-8"))


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


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def alpha_component_count(image: Image.Image) -> int:
    alpha = image.convert("RGBA").getchannel("A")
    remaining = {
        (x, y)
        for y in range(image.height)
        for x in range(image.width)
        if alpha.getpixel((x, y)) >= 128
    }
    count = 0
    while remaining:
        count += 1
        stack = [remaining.pop()]
        while stack:
            x, y = stack.pop()
            for neighbor in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
                if neighbor in remaining:
                    remaining.remove(neighbor)
                    stack.append(neighbor)
    return count


def test_sivir_replaces_official_005_once_and_exposes_only_q_e_r() -> None:
    champions = [
        (path.name, json.loads(path.read_text(encoding="utf-8")))
        for path in sorted((MOD / "champion").glob("*.data_champion"))
    ]
    assert [name for name, champion in champions if champion.get("id") == "boomerang_hunter"] == [
        "boomerang_hunter.data_champion"
    ]
    assert all(champion.get("id") != "lol_sivir" for _, champion in champions)
    assert not (MOD / "champion/lol_sivir.data_champion").exists()

    sivir = load_json("champion/boomerang_hunter.data_champion")
    assert sivir["id"] == "boomerang_hunter"
    assert sivir["sprite"] == "asset/lol_mod/aseprite_resources/champions/sivir"
    assert sivir["anim_prefix"] == ""
    assert sivir["category"] == "Range"
    assert set(sivir["tags"]) == {"AD", "Range", "Heal"}
    assert sivir["skill_icons"] == [
        "asset/lol_mod/icons/sivir_skill",
        "asset/lol_mod/icons/sivir_skill2",
        "asset/lol_mod/icons/sivir_ult",
    ]
    assert [sivir[key]["action_name"] for key in ("skill", "skill2", "ult")] == [
        "skill",
        "skill2",
        "ult",
    ]
    assert not {"w", "skill3", "skill4"}.intersection(sivir)


def test_sivir_stats_and_native_action_slots_match_contract() -> None:
    sivir = load_json("champion/boomerang_hunter.data_champion")
    assert sivir["stat"] == {
        "attack": 100,
        "magic_power": 0,
        "hp": 900,
        "defence": 20,
        "magic_resistance": 20,
        "move_speed": 900,
        "hp_regen": 2,
        "stack": 0,
        "crit_chance": 0,
    }
    assert sivir["growth"] == {
        "attack": 18,
        "magic_power": 0,
        "hp": 90,
        "defence": 7,
        "magic_resistance": 3,
        "move_speed": 9,
        "hp_regen": 1,
        "stack": 0,
        "crit_chance": 0,
    }
    assert [
        (
            sivir[key]["range"],
            sivir[key]["cooltime"],
            sivir[key]["duration"],
            sivir[key]["start_timing"],
            sivir[key]["casting_type"],
            sivir[key]["casting_target"],
        )
        for key in ("attack", "skill", "skill2", "ult")
    ] == [
        (60000, 60, 26, 20, "Targeting", "Enemy"),
        (75000, 360, 26, 18, "Targeting", "EnemyWithoutTower"),
        (0, 720, 25, 20, "None", "AllyOnlySelf"),
        (85000, 3000, 28, 20, "Targeting", "EnemyChampion"),
    ]


def test_sivir_attack_uses_crossblade_and_nonstacking_fleet_buff() -> None:
    attack = load_json("champion/boomerang_hunter.data_champion")["attack"]
    projectiles = find_effect(attack, "TargetProjectile", name="lol_sivir_attack_blade")
    assert len(projectiles) == 1
    assert projectiles[0]["speed"] == 6000
    assert find_effect(projectiles[0], "Attack", damage=0, attack_ratio=100)
    fleet = [
        effect["buff_state"]
        for effect in find_effect(projectiles[0], "AddCasterBuff")
        if effect["buff_state"]["name"] == "lol_sivir_fleet_of_foot"
    ]
    assert fleet == [
        {
            "name": "lol_sivir_fleet_of_foot",
            "duration": {"Time": {"tick": 90}},
            "move_speed_mult": 12,
        }
    ]
    assert len(find_effect(attack, "Sfx", name="lol_sivir_attack_cast")) == 1
    assert len(find_effect(attack, "TargetSfx", name="lol_sivir_attack_hit")) == 1


def test_sivir_q_is_one_outbound_projectile_with_one_nested_return() -> None:
    q = load_json("champion/boomerang_hunter.data_champion")["skill"]
    outgoing = find_effect(q, "LinearProjectile", name="lol_sivir_q_outgoing")
    returning = find_effect(q, "BackToCasterLinearProjectile", name="lol_sivir_q_return")
    assert len(outgoing) == len(returning) == 1
    out = outgoing[0]
    back = returning[0]
    assert [effect for effect in out["end_effects"] if effect.get("type") == "BackToCasterLinearProjectile"] == [back]
    assert (out["penetrate"], out["speed"], out["range"], out["shape"], out["applied_target"]) == (
        True,
        4200,
        75000,
        {"Circle": {"radius": 7000}},
        "EnemyWithoutTower",
    )
    assert (back["penetrate"], back["speed"], back["range"], back["shape"], back["applied_target"]) == (
        True,
        5200,
        120000,
        {"Circle": {"radius": 7000}},
        "EnemyWithoutTower",
    )
    for projectile in (out, back):
        damage = find_effect(projectile["applied_effects"], "Attack")
        assert [(effect["damage"], effect["attack_ratio"]) for effect in damage] == [(30, 55)]
        assert len(find_effect(projectile["applied_effects"], "TargetSfx", name="lol_sivir_q_hit")) == 1
    assert len(find_effect(q, "CasterAnimation", name="idle_no_boomerang", tick=42)) == 1
    assert len(find_effect(q, "Sfx", name="lol_sivir_q_out")) == 1
    assert len(find_effect(q, "Sfx", name="lol_sivir_q_return")) == 1


def test_sivir_e_is_an_honest_timed_damage_guard_not_a_fake_exact_spell_consume() -> None:
    sivir = load_json("champion/boomerang_hunter.data_champion")
    e = sivir["skill2"]
    states = {
        effect["buff_state"]["name"]: effect["buff_state"]
        for effect in find_effect(e, "AddCasterBuff")
    }
    assert states == {
        "lol_sivir_spell_shield_window": {
            "name": "lol_sivir_spell_shield_window",
            "duration": {"Time": {"tick": 90}},
            "skill_damaged_reduce": 100,
        },
        "lol_sivir_spell_shield_speed": {
            "name": "lol_sivir_spell_shield_speed",
            "duration": {"Time": {"tick": 120}},
            "move_speed_mult": 20,
        },
    }
    assert len(find_effect(e, "Heal", amount=60, attack_ratio=15, ap_ratio=0, heal_type="Caster")) == 1
    assert not find_effect(e, "Attack")
    assert not find_effect(e, "ApAttack")
    assert not find_effect(e, "FixedAttack")
    assert not find_effect(e, "Shield")
    english = load_json("text/champion.i18n")["en"]["description"]["boomerang_hunter"]["skill2"]
    assert "timed damage guard" in english
    assert "not consumed by the first spell" in english
    assert "cannot block crowd control" in english


def test_sivir_r_applies_one_non_damaging_team_speed_buff() -> None:
    ult = load_json("champion/boomerang_hunter.data_champion")["ult"]
    zones = find_effect(ult, "RangeEffect")
    assert len(zones) == 1
    zone = zones[0]
    assert (zone["shape"], zone["target"], zone["apply_type"]) == (
        {"Circle": {"radius": 100000}},
        "AllyChampion",
        "AroundCaster",
    )
    buffs = find_effect(zone, "AddBuff")
    assert [effect["buff_state"] for effect in buffs] == [
        {
            "name": "lol_sivir_on_the_hunt_speed",
            "duration": {"Time": {"tick": 300}},
            "move_speed_mult": 25,
        }
    ]
    assert not find_effect(ult, "AddCasterBuff")
    assert not any(find_effect(ult, effect_type) for effect_type in ("Attack", "ApAttack", "FixedAttack", "Shield"))
    assert len(find_effect(ult, "Sfx", name="lol_sivir_r_cast")) == 1
    assert not find_effect(zone, "Sfx")


def test_sivir_preserves_native_animation_tags_counts_timings_and_transparent_death_end() -> None:
    expected = {
        "idle": [0.18, 0.14, 0.14, 0.14],
        "big_boomerang": [0.1],
        "boomerang": [0.1],
        "run": [0.080000006] * 8,
        "attack": [0.060000002] * 6,
        "idle_no_boomerang": [0.18, 0.14, 0.14, 0.14],
        "skill": [0.060000002] * 7,
        "skill2": [0.060000002] * 7,
        "ult": [0.060000002] * 6,
        "hit": [0.1],
        "ult_boomerang": [0.060000002],
        "dead": [0.1] * 9,
    }
    anim = load_json("aseprite_resources/champions/sivir#anim.fanim")["anims"]
    assert set(anim) == set(expected)
    for tag, durations in expected.items():
        actual = [float(frame["duration"]) for frame in anim[tag]["frames"]]
        assert len(actual) == len(durations)
        assert all(math.isclose(a, b, abs_tol=1e-9) for a, b in zip(actual, durations))
    sheet = Image.open(MOD / "aseprite_resources/champions/sivir#sheet.png").convert("RGBA")
    assert sheet.size == (1984, 64)
    last = anim["dead"]["frames"][-1]["data"]
    frame = sheet.crop((last["x"], last["y"], last["x"] + last["w"], last["y"] + last["h"]))
    assert frame.getchannel("A").getbbox() is None
    run_hashes = []
    for row in anim["run"]["frames"]:
        data = row["data"]
        frame = sheet.crop((data["x"], data["y"], data["x"] + data["w"], data["y"] + data["h"]))
        assert frame.getchannel("A").getbbox()[3] == 45
        run_hashes.append(hashlib.sha256(frame.tobytes()).hexdigest())
    assert len(set(run_hashes)) == 8
    attack_hashes = []
    for row in anim["attack"]["frames"]:
        data = row["data"]
        frame = sheet.crop((data["x"], data["y"], data["x"] + data["w"], data["y"] + data["h"]))
        mirrored = frame.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
        assert alpha_component_count(frame) == 1
        assert alpha_component_count(mirrored) == 1
        assert mirrored.getchannel("A").getbbox()[0] >= 2
        assert mirrored.getchannel("A").getbbox()[2] <= 62
        assert all(
            frame.getpixel((pixel_x, pixel_y)) == (0, 0, 0, 0)
            for pixel_y in range(frame.height)
            for pixel_x in range(frame.width)
            if frame.getpixel((pixel_x, pixel_y))[3] == 0
        )
        attack_hashes.append(hashlib.sha256(frame.tobytes()).hexdigest())
    assert len(set(attack_hashes)) >= 4


def test_sivir_legacy_hd_actor_and_each_ui_surface_use_their_own_safe_crop() -> None:
    sheet_path = MOD / "aseprite_resources/champions/sivir#sheet.png"
    anim_path = MOD / "aseprite_resources/champions/sivir#anim.fanim"
    idle_bboxes = assert_actor_tag_scale(
        sheet_path,
        anim_path,
        "idle",
        min_height=36,
        max_height=36,
        baseline=45,
        min_unique_frames=2,
    )
    run_bboxes = assert_actor_tag_scale(
        sheet_path,
        anim_path,
        "run",
        min_height=35,
        max_height=37,
        baseline=45,
        min_unique_frames=8,
    )
    ult_bboxes = assert_actor_tag_scale(
        sheet_path,
        anim_path,
        "ult",
        min_height=35,
        max_height=36,
        baseline=45,
        min_unique_frames=3,
    )
    # The accepted source subjects are 179x212 (idle A) and 222x231 (run A).
    # Their packed bboxes retain those ratios: no x-only compression is used.
    assert_uniform_aspect_ratio((179, 212), idle_bboxes[0], tolerance=0.04)
    assert_uniform_aspect_ratio((222, 231), run_bboxes[0], tolerance=0.04)
    assert ult_bboxes[0][3] - ult_bboxes[0][1] == 36
    assert_readable_upper_detail(animation_frames(sheet_path, anim_path, "idle")[0])

    surfaces = assert_legacy_hd_portrait_set(
        MOD,
        "boomerang_hunter",
        side_card_relative="BanPickIllust/boomerang_hunter.png",
    )
    assert surfaces == {
        "encyclopedia": (7, 2, 56, 60),
        "compact": (9, 8, 54, 58),
        "scoreboard": (11, 8, 53, 58),
        "bp_grid": (10, 4, 79, 86),
    }

    # Sivir faces screen-right in the accepted idle source.  The old tiny-row
    # crop ended before the right edge of her head, leaving the skin/circlet
    # cluster at x=47 and making the scoreboard look like half a face.  Keep
    # that readable cluster centred after the real 18-34px nearest resize.
    scoreboard = Image.open(
        MOD / "ui/champion_portrait/boomerang_hunter_scoreboard.png"
    ).convert("RGBA")
    warm_face_pixels = []
    for y in range(8, 42):
        for x in range(scoreboard.width):
            red, green, blue, alpha = scoreboard.getpixel((x, y))
            if (
                alpha
                and red >= 105
                and 45 <= green <= 155
                and blue <= 105
                and red >= green + 20
            ):
                warm_face_pixels.append((x, y))
    assert len(warm_face_pixels) >= 240
    face_center_x = sum(x for x, _ in warm_face_pixels) / len(warm_face_pixels)
    assert 31 <= face_center_x <= 39

    qa = load_json("qa/sivir_hd_surface_qa.json")
    assert qa["champion"] == "Sivir"
    assert qa["native_id"] == "boomerang_hunter"
    assert qa["source_route"] == (
        "existing processed high-resolution ImageGen idle; no new generation"
    )
    assert qa["skill_logic_changed"] is False
    assert qa["battle_actor"]["uniform_xy_scale"] is True
    assert qa["battle_actor"]["x_only_compression"] is False
    assert qa["surfaces"]["bp_grid"]["name_band_clearance"] >= 10

    runtime = (MOD / "src/lib.rs").read_text(encoding="utf-8")
    for marker in (
        "boomerang_hunter_compact",
        "boomerang_hunter_scoreboard",
        "boomerang_hunter_grid",
        "asset/base/aseprite_resources/champions/boomerang_hunter#sheet",
        "asset/lol_mod/aseprite_resources/champions/sivir#sheet",
    ):
        assert marker in runtime


def test_sivir_e_surrounds_actor_and_r_speed_vfx_stays_at_feet() -> None:
    e_sheet = Image.open(MOD / "aseprite_resources/effects/sivir_e_shield#sheet.png").convert("RGBA")
    e_anim = load_json("aseprite_resources/effects/sivir_e_shield#anim.fanim")["anims"]
    for row in e_anim["loop"]["frames"]:
        data = row["data"]
        frame = e_sheet.crop((data["x"], data["y"], data["x"] + data["w"], data["y"] + data["h"]))
        bbox = frame.getchannel("A").getbbox()
        assert bbox[2] - bbox[0] >= 52
        assert bbox[3] - bbox[1] >= 52

    r_sheet = Image.open(MOD / "aseprite_resources/effects/sivir_hunt_buff#sheet.png").convert("RGBA")
    r_anim = load_json("aseprite_resources/effects/sivir_hunt_buff#anim.fanim")["anims"]
    for tag in ("pre", "loop", "remove"):
        for row in r_anim[tag]["frames"]:
            data = row["data"]
            frame = r_sheet.crop((data["x"], data["y"], data["x"] + data["w"], data["y"] + data["h"]))
            bbox = frame.getchannel("A").getbbox()
            assert bbox[1] >= 22
            assert bbox[3] == 32
            assert bbox[3] - bbox[1] <= 10


def test_sivir_views_localization_style_and_imagegen_sources_are_registered() -> None:
    sivir = load_json("champion/boomerang_hunter.data_champion")
    projectile_names = {view["name"] for view in sivir["view_projectiles"]}
    effect_names = {view["name"] for view in sivir["view_effects"]}
    buff_names = {view["name"] for view in sivir["view_buffs"]}
    assert projectile_names == {"lol_sivir_attack_blade", "lol_sivir_q_outgoing", "lol_sivir_q_return"}
    assert effect_names == {"lol_sivir_attack_hit_visual", "lol_sivir_q_hit_visual", "lol_sivir_r_cast_visual"}
    assert buff_names == {"lol_sivir_spell_shield_window", "lol_sivir_on_the_hunt_speed"}

    style = load_json("style/champion_view.champion_view")["entries"]["boomerang_hunter"]
    assert style == {"face": {"x": 5, "y": -34}, "center": {"x": 0, "y": -12}}
    text = load_json("text/champion.i18n")
    expected_names = {"en": "Sivir", "zh-hans": "希维尔", "zh-hant": "希維爾", "ja": "シヴィア", "ko": "시비르"}
    for locale, name in expected_names.items():
        description = text[locale]["description"]["boomerang_hunter"]
        assert description["name"] == name
        assert description["skill"].startswith("Q")
        assert description["skill2"].startswith("E")
        assert description["ult"].startswith("R")
        assert "lol_sivir" not in text[locale]["description"]

    audit = load_json("qa/sivir_imagegen_sources.json")
    assert audit["generator"] == "built-in image_gen"
    assert len(audit["sources"]) == 10
    assert len(audit["processed"]) == 7
    for row in [*audit["sources"], *audit["processed"], *audit["runtime_files"]]:
        path = MOD / row["path"]
        assert path.is_file()
        assert path.stat().st_size == row["size_bytes"]
        assert sha256(path) == row["sha256"]
    prompts = (MOD / "source/imagegen/PROMPTS.md").read_text(encoding="utf-8")
    assert "# Sivir image-gen prompts" in prompts
    assert "sivir_hunt_buff_vfx_contact.png" in prompts


def test_sivir_official_audio_events_resolve_to_pinned_mono_clips() -> None:
    sivir = load_json("champion/boomerang_hunter.data_champion")
    override = load_json("mod.override_info")
    source = load_json("qa/sivir_official_audio_sources.json")
    actual_events = {
        effect["name"]
        for effect in walk_effects(sivir)
        if effect["type"] in {"Sfx", "TargetSfx"}
    }
    expected_events = {
        "lol_sivir_attack_cast",
        "lol_sivir_attack_hit",
        "lol_sivir_q_out",
        "lol_sivir_q_return",
        "lol_sivir_q_hit",
        "lol_sivir_e_cast",
        "lol_sivir_r_cast",
    }
    assert actual_events == expected_events
    assert len(source["outputs"]) == 7
    for row in source["outputs"]:
        event = f"lol_{row['event_key']}"
        local = row["event_key"]
        clip = f"{local}_clip"
        assert override[f"asset/base/sound/sfx/{event}"] == {
            "remapping": f"asset/lol_mod/sound/sfx/{local}",
            "type": "override",
        }
        assert override[f"asset/base/sound/sfx/{clip}"] == {
            "remapping": f"asset/lol_mod/sound/sfx/{clip}",
            "type": "override",
        }
        plays = load_json(f"sound/sfx/{local}.sound_info")["plays"]
        assert plays == [{"delay": 0.0, "clip": clip, "volume": row["volume"]}]
        wav_path = MOD / row["wav"]["path"]
        assert wav_path.stat().st_size == row["wav"]["size_bytes"]
        assert sha256(wav_path) == row["wav"]["sha256"]
        with wave.open(str(wav_path), "rb") as decoded:
            assert (decoded.getnchannels(), decoded.getsampwidth(), decoded.getframerate()) == (1, 2, 44100)
            assert decoded.getnframes() == row["wav"]["frame_count"]


def test_sivir_native_boomerang_hunter_audio_is_fully_isolated() -> None:
    override = load_json("mod.override_info")
    source = load_json("qa/sivir_official_audio_sources.json")
    isolation = source["native_audio_isolation"]
    silence_event = "asset/lol_mod/sound/sfx/sivir_native_silence"
    silence_clip = "asset/lol_mod/sound/sfx/sivir_native_silence_clip"
    for name in isolation["native_events"]:
        assert override[f"asset/base/sound/sfx/{name}"] == {
            "remapping": silence_event,
            "type": "override",
        }
    for name in isolation["native_clips"]:
        assert override[f"asset/base/sound/sfx/{name}"] == {
            "remapping": silence_clip,
            "type": "override",
        }
    assert load_json("sound/sfx/sivir_native_silence.sound_info") == {
        "plays": [{"delay": 0.0, "clip": "sivir_native_silence_clip", "volume": 1.0}]
    }
    path = MOD / "sound/sfx/sivir_native_silence_clip.wav"
    assert path.stat().st_size == 4454
    assert sha256(path) == "73b42ab23be05ebeada04e01d7a8b903a1cdd1753a090c5032983da1066bacc2"
    with wave.open(str(path), "rb") as decoded:
        assert (decoded.getnchannels(), decoded.getsampwidth(), decoded.getframerate(), decoded.getnframes()) == (1, 2, 44100, 2205)
        assert decoded.readframes(decoded.getnframes()) == b"\x00" * 4410


def test_sivir_runtime_assets_are_current_in_build_manifest() -> None:
    manifest = load_json("build_manifest.json")
    files = {row["path"]: row for row in manifest["files"]}
    required = {
        "champion/boomerang_hunter.data_champion",
        "aseprite_resources/champions/sivir#sheet.png",
        "aseprite_resources/champions/sivir#anim.fanim",
        "icons/sivir_skill.png",
        "icons/sivir_skill2.png",
        "icons/sivir_ult.png",
        *{
            f"aseprite_resources/effects/{name}#{suffix}"
            for name in ("sivir_attack", "sivir_q", "sivir_e_shield", "sivir_r_cast", "sivir_hunt_buff")
            for suffix in ("sheet.png", "anim.fanim")
        },
        *{f"sound/sfx/{name}.{suffix}" for name in (
            "sivir_attack_cast", "sivir_attack_hit", "sivir_q_out", "sivir_q_return",
            "sivir_q_hit", "sivir_e_cast", "sivir_r_cast"
        ) for suffix in ("sound_info",)},
        *{f"sound/sfx/{name}_clip.wav" for name in (
            "sivir_attack_cast", "sivir_attack_hit", "sivir_q_out", "sivir_q_return",
            "sivir_q_hit", "sivir_e_cast", "sivir_r_cast"
        )},
        "sound/sfx/sivir_native_silence.sound_info",
        "sound/sfx/sivir_native_silence_clip.wav",
        "ui/champion_fullbody/boomerang_hunter.png",
        "ui/champion_portrait/boomerang_hunter_compact.png",
        "ui/champion_portrait/boomerang_hunter_scoreboard.png",
        "ui/champion_portrait/boomerang_hunter_grid.png",
        "BanPickIllust/boomerang_hunter.png",
    }
    assert required.issubset(files)
    for relative in required:
        path = MOD / relative
        assert path.stat().st_size == files[relative]["size"]
        assert sha256(path) == files[relative]["sha256"]
