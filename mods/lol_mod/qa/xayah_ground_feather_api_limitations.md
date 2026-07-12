# Xayah ground-Feather and AI-gate API audit

## Release decision

The 0.9.x Xayah release does **not** claim independently addressable LoL ground Feathers. It ships a bounded visual approximation while keeping Q, E and R mechanically separate:

- Each of Q's two `lol_xayah_q_feather` projectiles creates one damage-free `lol_xayah_ground_single` marker at its endpoint.
- R's one wide outbound fan creates one aggregate `lol_xayah_ground_fan` marker whose art represents the five-Feather fan; it is not five separately tracked entities.
- Both marker types are `RangePeriodProjectile` visuals with `tick=180`, `period=180`, empty `applied_effects`, empty `end_effects`, and non-repeating animation. Each animation ends on a transparent frame so a separately cast E cannot leave a permanently visible ghost while the bounded marker entity finishes its TTL.
- E still chooses its damage/root branch only from the caster-side `lol_xayah_feathers_1..5` counter. It never enumerates, damages through, recalls, or deletes the ground-marker projectiles.

This is intentionally a visual endpoint cue, not a claim that every Feather is an exact persistent gameplay entity.

## Bladecaller AI gate

`DataActionDef` in the installed Teamfight Manager 2 v0.5.0 / Mod API 0.8 executable has no buff-based `can_cast` predicate. Keeping only `SwitchByBuff(... effect_none=...)` inside E would still let the built-in AI select the action, spend its cooldown, and play an empty cast.

The release therefore uses the public native-effect and player-input-AI surfaces together:

- the three Clean Cuts attack branches dispatch `lol_xayah_ai_feather_add_1`;
- Q dispatches `lol_xayah_ai_feather_add_2`;
- R dispatches `lol_xayah_ai_feather_set_5`;
- E dispatches `lol_xayah_ai_feather_clear` after the action is admitted;
- the mirror is capped to `0..5` and expires after the same 600 ticks as the caster Feather buffs;
- `XayahFeatherInputGate` intercepts only the built-in AI's `Input::Skill2`; it passes E only at a mirrored count of at least two and replaces an under-threshold E before the data action begins. Manual player input is outside `ModPlayerInputAi`.

Runtime state is stored per stable `EntityHandle` and records player id, team, position, update tick, count, and expiry tick. Expired entries are pruned on native-effect updates and AI reads; E clear removes the matching unit entry.

Mod API 0.8 does **not** expose `running_id`, `game_id`, `match_id`, or the current unit handle on `PlayerAiContext`. Consequently, the AI-side lookup selects the newest unexpired unit entry matching player id, team, position, and current tick. This is the strongest public-API isolation available, but it is not described as strict `running_id + unit` isolation.

## Data-schema evidence

The 2026-07-09 game executable exposes 59 `DataEffectDef` variants. Relevant variants include:

- `LinearProjectile`
- `BackToCasterLinearProjectile`
- `TargetProjectileFromProjectile`
- `RangeProjectile`
- `RangePeriodProjectile`
- `AddBuff` / `AddCasterBuff` / `RemoveCasterBuff`
- `SwitchByBuff`
- `Native`
- `ViewEffect` / `CasterViewEffect`

There is no data variant for `SpawnEntity`, `RemoveProjectile`, projectile lookup by name, persistent-object ownership mutation, or deleting a specific projectile from another action.

The bundled native Alchemist data proves that a projectile `end_effects` block can create a timed `RangePeriodProjectile` at its endpoint. It does not provide an E-time handle that can remove that projectile. This release uses that route only for bounded, effect-free visuals and never treats it as Bladecaller gameplay state.

## Mod API 0.8 compile-probe evidence

The SDK pinned to `nightly-2026-05-24` exposes these relevant `GameCtx` reads/mutations:

- `entity_count`, `entity_at`, `get_entity`
- `player_count`, `player_at`
- `projectile_count`, `projectile_at`
- `deal_damage`, `add_buff`, `apply_cc`

It does not expose `spawn_entity`, `create_entity`, `spawn_projectile`, `add_projectile`, `remove_projectile`, `create_effect`, or `add_view_effect`.

`ProjectileRef::info()` exposes only `ProjectileInfo { x, y, caster_id, team, is_end }`. It exposes no projectile name/id/action tag, so a runtime hook cannot safely identify and delete only Xayah's Q/R marker projectiles.

`PlayerAiContext` exposes the final `base_input`, player id, team, position, champion name, tick, input validation and safe fallback helpers. Compile probes confirm it exposes no buff enumeration, unit handle, or match/running id. The native count events are therefore required; effect-internal empty branching is not accepted as an AI gate.

## Required future API for exact gameplay Feathers

A high-fidelity implementation still needs all of the following as one supported runtime contract:

1. Spawn a persistent projectile/entity at the real terminal position of each Q/passive/R Feather.
2. Store a stable handle plus caster and running-match ownership and creation tick.
3. Enumerate only that caster's live Feathers when E is cast.
4. Spawn a return projectile from each stored coordinate to that caster.
5. Count per-target intersections so Bind occurs only after the same target is crossed by at least three returning Feathers.
6. Remove each recalled/expired ground entity immediately and serialize the state for replay/spectator views.

Until those operations exist, the counter-based E plus bounded endpoint visuals is the honest stable approximation.
