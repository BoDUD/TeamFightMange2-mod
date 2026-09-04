from __future__ import annotations

import json
import re
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest


ROOT = Path(__file__).resolve().parents[1]
MOD = ROOT / "mods" / "lol_mod"
RUST_SOURCE = MOD / "src" / "stable_runtime.rs"
COMBAT_SLOTS = ("attack", "skill", "skill2", "ult")
CHAMPION_IDS = tuple(
    sorted(
        json.loads(path.read_text(encoding="utf-8"))["id"]
        for path in (MOD / "champion").glob("*.data_champion")
    )
)

# RangeProjectile and LineRangeProjectile are logical area/hitbox effects.  The
# renderer-backed projectile families carry a name that must resolve through
# view_projectiles.  The two target champions currently use the linear and
# back-to-caster linear variants, while the suffix rule also protects future
# rendered projectile variants.
LOGIC_ONLY_PROJECTILE_TYPES = {
    "RangeProjectile",
    "LineRangeProjectile",
    "RangePeriodProjectile",
}


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def walk_dicts(value: Any, path: str = "$") -> Iterator[tuple[str, dict[str, Any]]]:
    """Yield every dictionary in a nested data-champion payload."""

    if isinstance(value, dict):
        yield path, value
        for key, child in value.items():
            yield from walk_dicts(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from walk_dicts(child, f"{path}[{index}]")


def combat_effects(champion: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    effects: list[tuple[str, dict[str, Any]]] = []
    for slot in COMBAT_SLOTS:
        for path, value in walk_dicts(champion[slot], f"$.{slot}"):
            if isinstance(value.get("type"), str):
                effects.append((path, value))
    return effects


def indexed_bindings(
    champion: dict[str, Any], table: str, errors: list[str]
) -> dict[str, dict[str, Any]]:
    rows = champion.get(table)
    if rows is None:
        return {}
    if not isinstance(rows, list):
        errors.append(f"{champion['id']}: {table} must be a list")
        return {}

    indexed: dict[str, dict[str, Any]] = {}
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            errors.append(f"{champion['id']}: {table}[{index}] must be an object")
            continue
        name = row.get("name")
        if not isinstance(name, str) or not name:
            errors.append(f"{champion['id']}: {table}[{index}] has no non-empty name")
            continue
        if name in indexed:
            errors.append(f"{champion['id']}: duplicate {table} binding {name!r}")
            continue
        indexed[name] = row
    return indexed


def mod_asset_files(asset: str) -> tuple[Path, Path] | None:
    prefix = "asset/lol_mod/"
    if not asset.startswith(prefix):
        return None
    relative = asset.removeprefix(prefix)
    return MOD / f"{relative}#anim.fanim", MOD / f"{relative}#sheet.png"


def validate_view_assets(
    champion_id: str,
    table: str,
    bindings: dict[str, dict[str, Any]],
    errors: list[str],
) -> None:
    for name, binding in bindings.items():
        asset = binding.get("anim")
        if not isinstance(asset, str):
            errors.append(f"{champion_id}: {table}.{name} has no anim asset")
            continue
        files = mod_asset_files(asset)
        if files is None:
            errors.append(
                f"{champion_id}: {table}.{name} must use a mod-local anim, got {asset!r}"
            )
            continue
        fanim_path, sheet_path = files
        if not fanim_path.is_file():
            errors.append(f"{champion_id}: missing FANIM for {table}.{name}: {fanim_path}")
            continue
        if not sheet_path.is_file():
            errors.append(f"{champion_id}: missing sheet for {table}.{name}: {sheet_path}")

        anims = load_json(fanim_path).get("anims")
        if not isinstance(anims, dict):
            errors.append(f"{champion_id}: malformed FANIM anim table: {fanim_path}")
            continue

        binding_type = binding.get("type")
        required_fields = {
            "Animated": ("tag",),
            "Animation": ("tag",),
            "ThreePhase": ("pre_tag", "loop_tag", "remove_tag"),
        }.get(binding_type)
        if required_fields is None:
            errors.append(
                f"{champion_id}: unsupported renderer type {binding_type!r} for "
                f"{table}.{name}"
            )
            continue

        for field in required_fields:
            tag = binding.get(field)
            if not isinstance(tag, str) or not tag:
                errors.append(f"{champion_id}: {table}.{name} lacks {field}")
                continue
            animation = anims.get(tag)
            if not isinstance(animation, dict):
                errors.append(
                    f"{champion_id}: {table}.{name}.{field}={tag!r} is absent from "
                    f"{fanim_path.relative_to(MOD)}"
                )
                continue
            frames = animation.get("frames")
            if not isinstance(frames, list) or not frames:
                errors.append(
                    f"{champion_id}: {table}.{name}.{field}={tag!r} has no frames"
                )


def validate_caster_animations(
    champion: dict[str, Any],
    effects: list[tuple[str, dict[str, Any]]],
    errors: list[str],
) -> None:
    sprite = champion.get("sprite")
    if not isinstance(sprite, str):
        errors.append(f"{champion['id']}: sprite must be an asset path")
        return
    files = mod_asset_files(sprite)
    if files is None:
        errors.append(f"{champion['id']}: sprite must be mod-local, got {sprite!r}")
        return
    fanim_path, sheet_path = files
    if not fanim_path.is_file() or not sheet_path.is_file():
        errors.append(
            f"{champion['id']}: actor animation closure is incomplete: "
            f"{fanim_path}, {sheet_path}"
        )
        return
    anims = load_json(fanim_path).get("anims", {})
    for path, effect in effects:
        if effect.get("type") != "CasterAnimation":
            continue
        tag = effect.get("name")
        if not isinstance(tag, str) or tag not in anims:
            errors.append(
                f"{champion['id']}: {path} CasterAnimation {tag!r} is absent from "
                f"{fanim_path.relative_to(MOD)}"
            )
            continue
        frames = anims[tag].get("frames")
        if not isinstance(frames, list) or not frames:
            errors.append(f"{champion['id']}: actor animation tag {tag!r} has no frames")


def validate_audio_closure(
    champion_id: str,
    effects: list[tuple[str, dict[str, Any]]],
    override: dict[str, Any],
    errors: list[str],
) -> None:
    audio_events: set[str] = set()
    for path, effect in effects:
        if effect.get("type") not in {"Sfx", "TargetSfx"}:
            continue
        name = effect.get("name")
        if not isinstance(name, str) or not name:
            errors.append(f"{champion_id}: {path} has an empty audio event")
            continue
        audio_events.add(name)

    for event in sorted(audio_events):
        event_key = f"asset/base/sound/sfx/{event}"
        mapping = override.get(event_key)
        if not isinstance(mapping, dict):
            errors.append(f"{champion_id}: no sound remap for {event_key}")
            continue
        remapping = mapping.get("remapping")
        if mapping.get("type") != "override" or not isinstance(remapping, str):
            errors.append(f"{champion_id}: malformed sound remap for {event_key}: {mapping}")
            continue
        prefix = "asset/lol_mod/"
        if not remapping.startswith(prefix):
            errors.append(f"{champion_id}: sound event {event} is not mod-local: {remapping}")
            continue

        sound_info_path = MOD / f"{remapping.removeprefix(prefix)}.sound_info"
        if not sound_info_path.is_file():
            errors.append(f"{champion_id}: missing sound info for {event}: {sound_info_path}")
            continue
        plays = load_json(sound_info_path).get("plays")
        if not isinstance(plays, list) or not plays:
            errors.append(f"{champion_id}: {sound_info_path.relative_to(MOD)} has no plays")
            continue

        for index, play in enumerate(plays):
            if not isinstance(play, dict):
                errors.append(
                    f"{champion_id}: {sound_info_path.relative_to(MOD)} play {index} "
                    "must be an object"
                )
                continue
            clip = play.get("clip")
            if not isinstance(clip, str) or not clip:
                errors.append(
                    f"{champion_id}: {sound_info_path.relative_to(MOD)} play {index} "
                    "has no clip"
                )
                continue
            clip_key = f"asset/base/sound/sfx/{clip}"
            expected_clip_mapping = {
                "remapping": f"asset/lol_mod/sound/sfx/{clip}",
                "type": "override",
            }
            if override.get(clip_key) != expected_clip_mapping:
                errors.append(
                    f"{champion_id}: clip remap mismatch for {clip_key}: "
                    f"{override.get(clip_key)!r}"
                )
            clip_path = MOD / "sound" / "sfx" / f"{clip}.wav"
            if not clip_path.is_file() or clip_path.stat().st_size == 0:
                errors.append(f"{champion_id}: missing or empty audio clip: {clip_path}")


def validate_native_closure(
    champion_id: str,
    effects: list[tuple[str, dict[str, Any]]],
    rust_source: str,
    errors: list[str],
) -> None:
    used: set[str] = set()
    for path, effect in effects:
        if effect.get("type") != "Native":
            continue
        effect_ref = effect.get("effect_ref")
        if not isinstance(effect_ref, str) or not effect_ref:
            errors.append(f"{champion_id}: {path} has an empty Native effect_ref")
            continue
        used.add(effect_ref)

    registrations = set(
        re.findall(
            r'registration\s*\.\s*add_native_effect\(\s*"([^"]+)"',
            rust_source,
            flags=re.MULTILINE,
        )
    )
    if "for retired_name in [" in rust_source:
        retired_block = rust_source.split("for retired_name in [", 1)[1].split(
            "] {", 1
        )[0]
        registrations.update(re.findall(r'"([^"]+)"', retired_block))
    missing = used - registrations
    if missing:
        errors.append(f"{champion_id}: Native refs missing Rust registration: {sorted(missing)}")


@pytest.mark.parametrize("champion_id", CHAMPION_IDS)
def test_runtime_reference_closure(champion_id: str) -> None:
    champion = load_json(MOD / "champion" / f"{champion_id}.data_champion")
    assert champion["id"] == champion_id
    effects = combat_effects(champion)
    errors: list[str] = []

    projectile_bindings = indexed_bindings(champion, "view_projectiles", errors)
    effect_bindings = indexed_bindings(champion, "view_effects", errors)
    buff_bindings = indexed_bindings(champion, "view_buffs", errors)

    projectile_refs: set[str] = set()
    effect_refs: set[str] = set()
    runtime_buff_names: set[str] = set()
    for path, effect in effects:
        effect_type = effect.get("type")
        if (
            isinstance(effect_type, str)
            and effect_type.endswith("Projectile")
            and effect_type not in LOGIC_ONLY_PROJECTILE_TYPES
        ):
            name = effect.get("name")
            if not isinstance(name, str) or not name:
                errors.append(f"{champion_id}: {path} {effect_type} has no renderer name")
            else:
                projectile_refs.add(name)
        if effect_type in {"ViewEffect", "CasterViewEffect"}:
            name = effect.get("name")
            if not isinstance(name, str) or not name:
                errors.append(f"{champion_id}: {path} {effect_type} has no renderer name")
            else:
                effect_refs.add(name)
        buff_state = effect.get("buff_state")
        if isinstance(buff_state, dict) and isinstance(buff_state.get("name"), str):
            runtime_buff_names.add(buff_state["name"])

    missing_projectiles = projectile_refs - set(projectile_bindings)
    if missing_projectiles:
        errors.append(
            f"{champion_id}: projectile refs missing view_projectiles bindings: "
            f"{sorted(missing_projectiles)}"
        )

    missing_effects = effect_refs - set(effect_bindings)
    orphaned_effects = set(effect_bindings) - effect_refs
    if missing_effects:
        errors.append(
            f"{champion_id}: ViewEffect/CasterViewEffect refs missing view_effects "
            f"bindings: {sorted(missing_effects)}"
        )
    if orphaned_effects:
        errors.append(
            f"{champion_id}: orphaned view_effects bindings: {sorted(orphaned_effects)}"
        )

    orphaned_buffs = set(buff_bindings) - runtime_buff_names
    if orphaned_buffs:
        errors.append(
            f"{champion_id}: view_buffs never referenced by a runtime buff_state: "
            f"{sorted(orphaned_buffs)}"
        )

    for table, bindings in (
        ("view_projectiles", projectile_bindings),
        ("view_effects", effect_bindings),
        ("view_buffs", buff_bindings),
    ):
        validate_view_assets(champion_id, table, bindings, errors)

    validate_caster_animations(champion, effects, errors)
    override = load_json(MOD / "mod.override_info")
    validate_audio_closure(champion_id, effects, override, errors)
    validate_native_closure(
        champion_id, effects, RUST_SOURCE.read_text(encoding="utf-8"), errors
    )

    assert not errors, "runtime reference closure failed:\n- " + "\n- ".join(errors)


def test_all_registered_native_effects_are_referenced_by_combat_data() -> None:
    source = RUST_SOURCE.read_text(encoding="utf-8")
    registrations = set(
        re.findall(
            r'registration\s*\.\s*add_native_effect\s*\(\s*"([^"]+)"',
            source,
            flags=re.MULTILINE,
        )
    )
    retired_block = source.split("for retired_name in [", 1)[1].split("] {", 1)[0]
    retired_loop = set(re.findall(r'"([^"]+)"', retired_block))
    registrations.update(retired_loop)
    used: set[str] = set()
    for champion_id in CHAMPION_IDS:
        champion = load_json(MOD / "champion" / f"{champion_id}.data_champion")
        for _, effect in combat_effects(champion):
            if effect.get("type") == "Native" and isinstance(effect.get("effect_ref"), str):
                used.add(effect["effect_ref"])

    compatibility = set(
        re.findall(
            r'registration\.add_native_effect\(\s*"([^"]+)",\s*'
            r"LegacySavedNativeCompatibilityEffect,\s*\);",
            source,
        )
    )
    compatibility.update(retired_loop)
    assert compatibility == {
        "lol_shen_shadow_dash_ai_hint_native",
        "lol_shen_shadow_dash_taunt_native",
        "lol_yone_e_start_native",
        "lol_yone_e_begin_return_native",
        "lol_yone_e_damage_pre_native",
        "lol_yone_e_damage_post_native",
        "lol_yone_e_settle_native",
        "lol_yone_w_begin_native",
        "lol_yone_w_collect_hit_native",
        "lol_yone_w_settle_native",
        "lol_yone_w_cone_native",
    }
    assert registrations == used | compatibility, (
        f"Native effect registry/data mismatch: missing={sorted(used - registrations)}, "
        f"unexpected={sorted(registrations - used - compatibility)}"
    )


def test_combat_runtime_avoids_unsafe_service_registry_and_panicking_unwrap() -> None:
    source = RUST_SOURCE.read_text(encoding="utf-8")
    forbidden = {
        "ctx.register_service": r"\bctx\s*\.\s*register_service\s*\(",
        "ctx.query_service": r"\bctx\s*\.\s*query_service\s*\(",
        "ModService::from_raw": r"\bModService\s*::\s*from_raw\s*\(",
        ".unwrap()": r"\.\s*unwrap\s*\(\s*\)",
        ".expect()": r"\.\s*expect\s*\(",
        "panic macro": r"\b(?:panic|unreachable|todo|unimplemented)\s*!\s*\(",
    }
    violations: list[str] = []
    for label, pattern in forbidden.items():
        for match in re.finditer(pattern, source, flags=re.MULTILINE):
            line = source.count("\n", 0, match.start()) + 1
            violations.append(f"{label} at src/stable_runtime.rs:{line}")

    assert not violations, (
        "combat runtime must use bounded in-process state and non-panicking access:\n- "
        + "\n- ".join(violations)
    )


def test_replaced_first_skills_follow_the_058_ai_target_contract() -> None:
    """Base 0.5.8 first skills must provide the target shape their data route needs.

    The four legacy replacements retain their proven entity-target route.
    Reference-grounded Yone intentionally uses a Direction cast whose effect
    supplies its own rush/projectile input and must not be rewritten to E-like
    target selection.
    """
    expected_targets = {
        "lol_shen": ("Targeting", "EnemyChampion"),
        "boomerang_hunter": ("Targeting", "EnemyWithoutTower"),
        "cavalry_knight": ("Targeting", "EnemyChampion"),
        "dancer": ("Targeting", "EnemyWithoutTower"),
        "dual_blader": ("Direction", "EnemyWithoutTower"),
    }
    for champion_id, (casting_type, expected_target) in expected_targets.items():
        champion = load_json(MOD / "champion" / f"{champion_id}.data_champion")
        first_skill = champion["skill"]
        assert first_skill["casting_type"] == casting_type, champion_id
        assert first_skill["casting_target"] == expected_target, champion_id


def test_only_the_058_stable_runtime_is_compiled() -> None:
    source = RUST_SOURCE.read_text(encoding="utf-8")
    cargo = (MOD / "Cargo.toml").read_text(encoding="utf-8")
    assert 'path = "src/stable_runtime.rs"' in cargo
    assert "registration.set_extension(QualityBpExtension::default());" in source
    assert source.count("registration.set_extension(") == 1
    assert "registration.set_server_extension(" not in source
    assert "LolModExtension" not in source
    assert "YoneManagementCardExtension" not in source
    assert (
        "declare_stable_mod!(init, requires = mod_api_stable::ABI_LEVEL);" in source
    )
    assert "YoneSpiritCleaveConeNativeEffect" not in source


def test_published_dll_matches_the_non_panicking_yone_runtime_contract() -> None:
    dll = (MOD / "lol_mod.dll").read_bytes()
    for required in (
        b"tfm2_mod_entry_stable",
        b"tfm2_mod_required_abi_level",
        b"lol_mod stable ABI loaded on game",
        b"0.12.14",
        b"lol_yone_e_start_native",
        b"lol_yone_e_begin_return_native",
        b"lol_yone_e_damage_pre_native",
        b"lol_yone_e_damage_post_native",
        b"lol_yone_e_settle_native",
        b"lol_shen_shadow_dash_ai_hint_native",
        b"lol_shen_shadow_dash_taunt_native",
        b"lol_bp_runtime_illustration",
        b"corrupt 5v5 pre-tick guard active",
    ):
        assert required in dll, f"rebuilt DLL is missing {required!r}"
    assert b"tfm2_mod_api_version" not in dll
    for retired in (
        b"static card-local 64x64 full-body nodes",
        b"lol_mod_encyclopedia_ui.tsv",
        b"lol_fullbody_yone",
        b"lol_fullbody_xayah",
        b"yone_soul_unbound_context",
        b"Yone E damage mark was just inserted",
        b"Xayah state was just inserted",
        b"Urgot R ready marker fits BuffState name capacity",
        b"Urgot R success marker fits BuffState name capacity",
        b"cloned NinePatch changed variant",
    ):
        assert retired not in dll, f"DLL still contains retired panic/service path {retired!r}"
