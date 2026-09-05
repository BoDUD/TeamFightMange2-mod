# Legacy saved-skill compatibility

## Scope

Older saves and `custom_database.tfm2db` snapshots can embed a previous
`.data_champion` action tree. Updating `champion/lol_shen.data_champion` or
`champion/dual_blader.data_champion` does not rewrite that embedded tree.

The stable runtime therefore keeps an exact load-only allowlist bound to
`LegacySavedNativeCompatibilityEffect`:

- `lol_shen_shadow_dash_ai_hint_native`
- `lol_shen_shadow_dash_taunt_native`
- the five retired Yone E names
- the three retired pre-cone Yone W names

The compatibility effect has an empty `apply` body. It cannot deal damage,
add buffs, apply crowd control, move/teleport an entity, queue another effect,
or spawn a projectile. Current champion data references none of the retired
Shen/Yone E names.

## Important limit

This shim resolves missing-Native load/runtime warnings and neutralizes the
old native callbacks only. It cannot remove the other non-Native nodes that an
old save already embedded (for example an old `Rush` or data-driven damage
node). Exact Q/W/R behavior therefore still requires a save/custom database
created from the current champion data.

## Why same-ID `StableChampion` is not used as a migration shortcut

The bundled stable API does allow `StableMod::add_champion` to reuse an
existing id. However, `StableChampion` replaces the complete action set, and
`StableAction` exposes only one `StableEffectSpec`/`StableEffectType` callback.
The stable action/simulation surface has no delegation back to a loaded
`.data_champion` action tree and no `ViewEffect`, `CasterViewEffect`, `Sfx`, or
`TargetSfx` dispatch API.

Registering same-id native Shen/Yone champions would therefore migrate the
mechanical action table at the cost of replacing the current data-driven VFX,
SFX, projectile, animation, and composed effect trees. That is not a safe
compatibility fix for this mod, so it is deliberately rejected until the
stable ABI exposes data-action delegation or equivalent presentation hooks.

## Static proof

- `tests/test_shen_mod.py` checks that both Shen aliases are bound only to the
  no-op shim in the classic and stable runtime sources, while active Shen data
  contains no Shadow Dash payload.
- `tests/test_yone_mod.py` and
  `tests/test_runtime_reference_closure.py` keep the complete compatibility
  allowlist exact and reject any unregistered or unexpectedly active native
  effect.
- `mods/lol_mod/tools/validate_lol_mod.py` rejects restoration of the retired
  Shen implementation, input AI, or taunt constants while requiring both
  load-only aliases.
