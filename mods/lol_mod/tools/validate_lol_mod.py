#!/usr/bin/env python3
"""Static validation for the additive Shen champion and its generated assets."""

from __future__ import annotations

import hashlib
import json
import sys
import wave
from pathlib import Path
from typing import Any, Iterable

from PIL import Image


MOD_ROOT = Path(__file__).resolve().parents[1]
ERRORS: list[str] = []


def check(condition: bool, message: str) -> None:
    if not condition:
        ERRORS.append(message)


def load_json(relative: str) -> Any:
    path = MOD_ROOT / relative
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as error:  # pragma: no cover - diagnostic path
        ERRORS.append(f"{relative}: cannot parse JSON: {error}")
        return {}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def walk_effects(value: Any) -> Iterable[dict[str, Any]]:
    if isinstance(value, dict):
        if isinstance(value.get("type"), str):
            yield value
        for child in value.values():
            yield from walk_effects(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk_effects(child)


def find_effect(root: Any, effect_type: str, **fields: Any) -> list[dict[str, Any]]:
    return [
        effect
        for effect in walk_effects(root)
        if effect.get("type") == effect_type and all(effect.get(key) == value for key, value in fields.items())
    ]


def validate_data_contract(champion: dict[str, Any]) -> None:
    check(champion.get("id") == "lol_shen", "champion id must be lol_shen")
    check(champion.get("category") == "Melee", "Shen category must be Melee")
    check({"Melee", "Tank", "Shield", "CC"}.issubset(set(champion.get("tags", []))), "Shen role tags are incomplete")
    check(
        champion.get("skill_icons")
        == [
            "asset/lol_mod/icons/shen_skill",
            "asset/lol_mod/icons/shen_skill2",
            "asset/lol_mod/icons/shen_ult",
        ],
        "skill icon order must be Q/W/R",
    )
    expected_stats = {
        "hp": 1100,
        "attack": 75,
        "magic_power": 20,
        "defence": 40,
        "magic_resistance": 35,
        "move_speed": 1000,
    }
    for key, value in expected_stats.items():
        check(champion.get("stat", {}).get(key) == value, f"base stat {key} must be {value}")

    attack = champion.get("attack", {})
    check(attack.get("range") == 25000, "basic attack range must use engine units (25000)")
    check(attack.get("cooltime") == 70, "basic attack cooltime must be 70 ticks")

    q = champion.get("skill", {})
    check(q.get("range") == 60000 and q.get("cooltime") == 360, "Q range/cooltime mismatch")
    projectiles = find_effect(q, "LinearProjectile")
    check(len(projectiles) == 1, "Q must contain exactly one LinearProjectile")
    if projectiles:
        check(projectiles[0].get("penetrate") is True, "Q projectile must penetrate")
        check(projectiles[0].get("range") == 60000, "Q projectile range mismatch")
    q_slow = [
        effect
        for effect in find_effect(q, "AddBuff")
        if effect.get("buff_state", {}).get("name") == "lol_shen_twilight_assault_slow"
    ]
    check(bool(q_slow), "Q named slow marker is missing")
    if q_slow:
        check(q_slow[0]["buff_state"].get("move_speed_mult") == -25, "Q slow must be -25%")
        check(q_slow[0]["buff_state"].get("duration", {}).get("Time", {}).get("tick") == 90, "Q slow must last 90 ticks")
    q_shields = find_effect(q, "Shield", amount=120, tick=120)
    check(bool(q_shields), "Q on-hit self shield must be 120 for 120 ticks")

    w = champion.get("skill2", {})
    check(w.get("cooltime") == 480, "W cooldown must be 480 ticks")
    w_ranges = find_effect(w, "RangeEffect")
    ally_ranges = [effect for effect in w_ranges if effect.get("target") == "AllyChampion"]
    enemy_ranges = [effect for effect in w_ranges if effect.get("target") == "EnemyChampion"]
    check(len(ally_ranges) == 1 and len(enemy_ranges) == 1, "W must have one ally and one enemy range effect")
    for effect in w_ranges:
        check(effect.get("shape", {}).get("Circle", {}).get("radius") == 35000, "W radius must be 35000")
        check(effect.get("apply_type") == "AroundCaster", "W must apply around caster")
    w_shields = find_effect(ally_ranges, "Shield", amount=150, ap_ratio=40, tick=150)
    check(bool(w_shields), "W ally shield contract mismatch")
    w_slows = [
        effect
        for effect in find_effect(enemy_ranges, "AddBuff")
        if effect.get("buff_state", {}).get("name") == "lol_shen_spirit_refuge_as_slow"
    ]
    check(bool(w_slows), "W named attack-speed debuff is missing")
    if w_slows:
        check(w_slows[0]["buff_state"].get("attack_speed_mult") == -30, "W attack-speed debuff must be -30%")

    ult = champion.get("ult", {})
    check(ult.get("range") == 960000, "R range must be 960000")
    check(ult.get("cooltime") == 3000, "R cooldown must be 3000 ticks")
    check(ult.get("casting_target") == "AllyNotSelf", "R must target AllyNotSelf")
    check(bool(find_effect(ult, "Shield", amount=900, ap_ratio=80, tick=180)), "R shield contract mismatch")
    delayed = [effect for effect in find_effect(ult, "Delayed", tick=48)]
    check(len(delayed) == 1, "R must have one 48-tick arrival delay")
    if delayed:
        check(bool(find_effect(delayed[0], "Teleport")), "R delayed arrival must contain a real Teleport")
        check(bool(find_effect(delayed[0], "Taunt", duration=45)), "R delayed arrival must taunt for 45 ticks")
        arrive_sfx = [effect.get("name") for effect in find_effect(delayed[0], "Sfx")]
        check("lol_shen_r_arrive" in arrive_sfx, "R arrival SFX must be inside the 48-tick delay")

    serialized = json.dumps(champion, ensure_ascii=False)
    required_markers = {
        "lol_shen_twilight_assault_slow",
        "lol_shen_twilight_assault_guard",
        "lol_shen_spirit_refuge_shield_window",
        "lol_shen_spirit_refuge_as_slow",
        "lol_shen_stand_united_channel",
        "lol_shen_stand_united_shield_window",
        "lol_shen_stand_united_arrival_cc",
    }
    for marker in required_markers:
        check(marker in serialized, f"named state marker missing: {marker}")


def validate_animation(sheet_relative: str, anim_relative: str, required: dict[str, int]) -> None:
    sheet_path = MOD_ROOT / sheet_relative
    anim = load_json(anim_relative)
    check(sheet_path.is_file(), f"missing sheet: {sheet_relative}")
    if not sheet_path.is_file():
        return
    image = Image.open(sheet_path).convert("RGBA")
    for tag, minimum_frames in required.items():
        frames = anim.get("anims", {}).get(tag, {}).get("frames", [])
        check(len(frames) >= minimum_frames, f"{anim_relative}: tag {tag} has too few frames")
        for frame in frames:
            data = frame.get("data", {})
            x, y, width, height = (data.get("x", -1), data.get("y", -1), data.get("w", 0), data.get("h", 0))
            check(x >= 0 and y >= 0 and width > 0 and height > 0, f"{anim_relative}: invalid frame rectangle in {tag}")
            check(x + width <= image.width and y + height <= image.height, f"{anim_relative}: out-of-bounds frame in {tag}")


def validate_actor_and_icons(champion: dict[str, Any]) -> None:
    actor_path = MOD_ROOT / "aseprite_resources/champions/shen#sheet.png"
    actor = Image.open(actor_path).convert("RGBA")
    check(actor.size == (768, 64), f"actor sheet must be 768x64, got {actor.size}")
    bboxes = []
    hashes = []
    for index in range(12):
        frame = actor.crop((index * 64, 0, (index + 1) * 64, 64))
        bbox = frame.getchannel("A").getbbox()
        check(bbox is not None, f"actor frame {index} is empty")
        if bbox:
            bboxes.append(bbox)
            check(bbox[3] <= 46, f"actor frame {index} crosses the official y=45 foot baseline")
            check(bbox[0] >= 2 and bbox[2] <= 62, f"actor frame {index} touches a side edge")
        hashes.append(hashlib.sha256(frame.tobytes()).hexdigest())
    if bboxes:
        core_heights = [bbox[3] - bbox[1] for bbox in bboxes[:11]]
        check(max(core_heights) / min(core_heights) <= 1.22, "core actor body scale varies by more than 22%")
        first = bboxes[0]
        check(first[1] <= 12 and 44 <= first[3] <= 46 and first[3] - first[1] >= 34, "first idle frame does not match the official full-body baseline")
    check(len(set(hashes[2:5])) == 3, "run source poses must be visually distinct")
    check(len(set(hashes[5:8])) == 3, "attack source poses must be visually distinct")

    for icon_path in champion.get("skill_icons", []):
        relative = icon_path.removeprefix("asset/lol_mod/") + ".png"
        path = MOD_ROOT / relative
        check(path.is_file(), f"missing icon: {relative}")
        if path.is_file():
            icon = Image.open(path)
            check(icon.size == (64, 64), f"{relative} must be 64x64")
            check(icon.convert("RGBA").getchannel("A").getbbox() is not None, f"{relative} is empty")


def validate_localization() -> None:
    text = load_json("text/champion.i18n")
    for locale in ("en", "zh-hans", "zh-hant"):
        description = text.get(locale, {}).get("description", {}).get("lol_shen", {})
        check(set(description) == {"name", "attack", "skill", "skill2", "ult"}, f"{locale} Shen localization is incomplete")
    check(text.get("zh-hans", {}).get("description", {}).get("lol_shen", {}).get("name") == "慎", "zh-hans name must be 慎")
    check(text.get("zh-hant", {}).get("description", {}).get("lol_shen", {}).get("name") == "慎", "zh-hant name must be 慎")
    check("lowest-health" in text.get("en", {}).get("description", {}).get("lol_shen", {}).get("ult", ""), "English R text must disclose the target-selection limitation")


def validate_audio(champion: dict[str, Any], override: dict[str, Any]) -> None:
    sfx_names = sorted({effect.get("name") for effect in walk_effects(champion) if effect.get("type") in {"Sfx", "TargetSfx"}})
    check(len(sfx_names) == 7, f"expected 7 wired Shen sound events, got {len(sfx_names)}")
    for name in sfx_names:
        source_key = f"asset/base/sound/sfx/{name}"
        event_override = override.get(source_key, {})
        check(event_override.get("type") == "override", f"missing sound event remap: {source_key}")
        remapping = event_override.get("remapping", "")
        relative = remapping.removeprefix("asset/lol_mod/") + ".sound_info"
        event_path = MOD_ROOT / relative
        check(event_path.is_file(), f"missing sound_info for {name}: {relative}")
        if not event_path.is_file():
            continue
        sound_info = load_json(relative)
        plays = sound_info.get("plays", [])
        check(bool(plays), f"{relative} must contain plays")
        for play in plays:
            check(float(play.get("volume", 0)) >= 0.85, f"{relative} volume is below 0.85")
            clip = play.get("clip", "")
            clip_source = f"asset/base/sound/sfx/{clip}"
            clip_override = override.get(clip_source, {})
            check(clip_override.get("type") == "override", f"missing clip remap: {clip_source}")
            clip_relative = clip_override.get("remapping", "").removeprefix("asset/lol_mod/") + ".wav"
            clip_path = MOD_ROOT / clip_relative
            check(clip_path.is_file() and clip_path.stat().st_size > 1000, f"missing/empty clip: {clip_relative}")
            if clip_path.is_file():
                with wave.open(str(clip_path), "rb") as decoded:
                    check(decoded.getnchannels() == 1, f"{clip_relative} must be mono")
                    check(decoded.getsampwidth() == 2, f"{clip_relative} must be 16-bit PCM")
                    check(decoded.getframerate() == 44100, f"{clip_relative} must be 44.1 kHz")

    audio_manifest = load_json("qa/shen_official_audio_sources.json")
    check(len(audio_manifest.get("outputs", [])) == 7, "official audio QA manifest must cover 7 clips")
    for output in audio_manifest.get("outputs", []):
        wav = output.get("wav", {})
        path = MOD_ROOT / wav.get("path", "missing")
        check(path.is_file(), f"audio QA manifest references missing WAV: {wav.get('path')}")
        if path.is_file():
            check(sha256(path) == wav.get("sha256"), f"audio QA hash mismatch: {wav.get('path')}")


def validate_imagegen_sources() -> None:
    manifest = load_json("qa/shen_imagegen_sources.json")
    roles = {source.get("role") for source in manifest.get("sources", [])}
    check(roles == {"actor_model", "q_icon", "w_icon", "r_icon", "q_vfx", "w_vfx", "r_vfx"}, "image-gen source roles are incomplete")
    for source in manifest.get("sources", []):
        path = MOD_ROOT / source.get("path", "missing")
        check(path.is_file(), f"missing image-gen source: {source.get('path')}")
        if path.is_file():
            check(sha256(path) == source.get("sha256"), f"image-gen source hash mismatch: {source.get('path')}")
    processed = sorted((MOD_ROOT / "source/processed").glob("*_alpha.png"))
    check(len(processed) == 7, "processed image-gen source set must contain 7 alpha PNGs")
    for path in processed:
        image = Image.open(path).convert("RGBA")
        corners = [image.getpixel((0, 0)), image.getpixel((image.width - 1, 0)), image.getpixel((0, image.height - 1)), image.getpixel((image.width - 1, image.height - 1))]
        check(all(pixel[3] == 0 for pixel in corners), f"processed source has a non-transparent corner: {path.name}")
    check((MOD_ROOT / "source/imagegen/PROMPTS.md").is_file(), "final image-gen prompt record is missing")


def validate_manifest() -> None:
    path = MOD_ROOT / "build_manifest.json"
    check(path.is_file(), "build_manifest.json is missing; run build_lol_mod.py")
    if not path.is_file():
        return
    manifest = load_json("build_manifest.json")
    for row in manifest.get("files", []):
        file_path = MOD_ROOT / row.get("path", "missing")
        check(file_path.is_file(), f"build manifest references missing file: {row.get('path')}")
        if file_path.is_file():
            check(file_path.stat().st_size == row.get("size"), f"build manifest size mismatch: {row.get('path')}")
            check(sha256(file_path) == row.get("sha256"), f"build manifest hash mismatch: {row.get('path')}")


def main() -> int:
    champion = load_json("champion/lol_shen.data_champion")
    override = load_json("mod.override_info")
    load_json("mod.mod_info")
    load_json("style/champion_view.champion_view")
    validate_data_contract(champion)
    validate_animation(
        "aseprite_resources/champions/shen#sheet.png",
        "aseprite_resources/champions/shen#anim.fanim",
        {"idle": 7, "run": 9, "attack": 6, "skill": 7, "skill2": 5, "ult": 5, "hit": 1, "dead": 1},
    )
    validate_animation("aseprite_resources/effects/shen_q#sheet.png", "aseprite_resources/effects/shen_q#anim.fanim", {"projectile": 8})
    validate_animation("aseprite_resources/effects/shen_w#sheet.png", "aseprite_resources/effects/shen_w#anim.fanim", {"field": 6})
    validate_animation("aseprite_resources/effects/shen_r#sheet.png", "aseprite_resources/effects/shen_r#anim.fanim", {"guard": 5, "arrival": 4})
    validate_actor_and_icons(champion)
    validate_localization()
    validate_audio(champion, override)
    validate_imagegen_sources()
    validate_manifest()
    if ERRORS:
        print("Shen mod validation failed:")
        for error in ERRORS:
            print(f"- {error}")
        return 1
    print("Shen mod validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
