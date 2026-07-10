# Sivir Q/E/R skill contract QA

Status: static contract and real SDK deserialization/build probe passed; live target-visible verification pending.

## Identity and slots

- Project order: 005.
- Same-ID native replacement: `boomerang_hunter`.
- Engine zero-based native index for forced QA: `26`.
- Active slots are exactly `skill=Q`, `skill2=E`, `ult=R`; W and fourth/fifth active slots are absent.

## Attack / Fleet of Foot

- One `TargetProjectile` named `lol_sivir_attack_blade` deals 100% Attack physical damage.
- On any enemy hit, one named `lol_sivir_fleet_of_foot` buff grants 12% Move Speed for 90 ticks.
- Reapplication uses the same buff name, so the state refreshes rather than stacking multiple named buffs.

## Q — Boomerang Blade

- One outbound `LinearProjectile` named `lol_sivir_q_outgoing` uses `penetrate=true`, 75000 range, 4200 speed, 7000 radius, and `EnemyWithoutTower`.
- Its `end_effects` contain exactly one `BackToCasterLinearProjectile` named `lol_sivir_q_return`; the return is not a parallel delayed projectile.
- Return range is 120000 to tolerate caster movement, speed is 5200, and it uses the same non-tower target filter.
- Each pass owns one independent `30 + 55% AD` payload and one independent hit event, allowing a target to be hit once outbound and once returning.
- The actor enters `idle_no_boomerang` for the expected flight window so the held weapon is not duplicated beside the projectile.

## E — Spell Shield approximation

- Public data/mod API hooks cannot inspect and consume the next incoming enemy skill while mutating that damage event.
- The released contract is therefore explicit and testable: 90 ticks of `skill_damaged_reduce=100`, immediate `60 + 15% AD` healing, and 20% Move Speed for 120 ticks.
- E deals no damage and creates no normal absorb shield.
- Player-facing text states that this is a timed skill-damage guard, is not consumed by the first spell, and cannot block crowd control or non-damage effects.

## R — On The Hunt

- One top-level cast SFX and one caster-follow cast pulse are dispatched once.
- Exactly one `RangeEffect` around Sivir affects `AllyChampion` in a 100000 radius.
- That range effect adds exactly one `lol_sivir_on_the_hunt_speed` buff: +25% Move Speed for 300 ticks.
- No extra `AddCasterBuff` exists, so Sivir cannot receive a second self-only copy.
- R has no damage, shield, or crowd-control effect.

Automated coverage: `tests/test_sivir_mod.py` plus the Sivir gates in `tools/validate_lol_mod.py`.

## Real SDK probe

- Tested against the installed Teamfight Manager 2 mod SDK with the game's native libraries.
- The full `DataChampionInfo` payload deserialized without ignored input keys.
- All attack, Q, E and R effects built successfully across 40 typed effect/view variants.
- Applying the same-ID overlay kept the native champion map at 60 entries, retained exactly one `boomerang_hunter`, and preserved engine index `26`.
- The overlay replaced the native attack and did not retain native passive, secondary-passive or ultimate-passive fields.
- Probe result: `PROBE_OK`.
