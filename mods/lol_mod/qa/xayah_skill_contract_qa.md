# Xayah / official 007 data contract

## Replacement and active-slot contract

- [x] The replacement uses the official `dancer` id exactly once; no additive `lol_xayah` data champion is registered.
- [x] Public active slots are strictly Q/E/R: `skill -> skill1`, `skill2 -> skill2`, `ult -> ult`.
- [x] No W, fourth active, `skill3`, or `skill4` key is exposed.
- [x] The replacement actor path is `asset/lol_mod/aseprite_resources/champions/xayah` and the native `dancer#sheet/#anim` paths are remapped to it.

## Passive / Clean Cuts

- [x] `lol_xayah_clean_cuts_3`, `_2`, and `_1` form a three-attack countdown.
- [x] A normal attack uses one targeted feather for `100% Attack` physical damage.
- [x] An empowered attack splits the selected-target hit into `65% Attack` and a penetrating `35% Attack` line so the primary target still receives `100% Attack` while enemies behind it receive the passive line.
- [x] Each empowered attack advances exactly one singular Feather-count state among `lol_xayah_feathers_1..5`, capped at five.
- [x] Q, E, and R clear old Clean Cuts counters and prepare `lol_xayah_clean_cuts_3`.

## Q / Double Daggers

- [x] Q launches exactly two penetrating `lol_xayah_q_feather` projectiles.
- [x] The second projectile is inside one `Delayed(tick=6)` block.
- [x] Each projectile has 720 range, speed 8000, radius 70, excludes towers, and deals `25 + 45% Attack` physical damage.
- [x] Q advances the singular Feather counter by two and caps it at five.
- [x] Each Q projectile endpoint creates one damage-free `lol_xayah_ground_single` marker. The marker has a hard 180-tick TTL, no applied/end effect, a non-repeating animation, and a transparent terminal frame; it is visual-only and is not an E target.
- [x] Q still contains no `BackToCasterLinearProjectile`, Bind, E/R sound, or E/R damage.

## E / Bladecaller

- [x] E is the separate native `skill2` action and chooses one of five mutually exclusive Feather-count branches only when E itself is cast.
- [x] Each branch launches a speed-30000 invisible `lol_xayah_e_anchor`; damage is not attached to the outbound anchor.
- [x] The anchor's `end_effects` launches a penetrating `BackToCasterLinearProjectile` at speed 12000. One Feather uses the small single-feather silhouette, two use the double-feather silhouette, and three or more use the Bladecaller cluster silhouette.
- [x] Return damage scales by stored count: `(20 + 25% AD)`, `(35 + 35% AD)`, `(50 + 45% AD)`, `(65 + 55% AD)`, `(80 + 65% AD)`.
- [x] Only the three-, four-, and five-Feather branches add `lol_xayah_e_third_feather_root`; the separate radius-65 center line lasts 45 ticks and owns the root visual/audio.
- [x] E consumes every Feather-count state after branch selection and does not leave an attached or persistent fake ground Feather entity.
- [x] Audio dispatch is split into cast, launch, hit, catch, and three-plus-Feather root events.
- [x] Mod API 0.8 has no data-action buff predicate, so `lol_xayah_ai_feather_add_1`, `_add_2`, `_set_5`, and `_clear` mirror the caster count with a 600-tick TTL. `XayahFeatherInputGate` intercepts only built-in-AI `Skill2` and admits E at two or more mirrored Feathers; a one-/zero-Feather AI E is replaced before cooldown/SFX/action dispatch.
- [x] Native state is keyed by `EntityHandle` and records player/team/position. The AI context lacks running id and unit handle, so strict cross-simulation running-id isolation is explicitly not claimed; expiry and E clear bound stale state.

## R / Featherstorm

- [x] R is outbound only: one delayed, wide, penetrating `lol_xayah_r_fan` projectile for `80 + 70% Attack` physical damage.
- [x] R release has two independently wired visual cues: the cast immediately follows Xayah with `lol_xayah_r_guard_visual`, while the non-repeating fan projectile starts from the single `Delayed(tick=12)` block. The actor atlas itself keeps the five-frame rise/apex/descent motion, so the ground ring is not the only cast cue.
- [x] R contains no `BackToCasterLinearProjectile`, no Bind, and no E audio/event; it cannot automatically recall Feathers.
- [x] R clears the old Feather count, sets `lol_xayah_feathers_5`, and prepares three Clean Cuts.
- [x] The R fan endpoint creates one aggregate `lol_xayah_ground_fan` visual representing five Feathers. It has the same 180-tick, no-damage, non-repeating, transparent-terminal lifecycle and does not call E, return, root, or create five addressable entities.
- [x] A 60-tick `lol_xayah_r_safety_window` grants 100% basic/skill damage reduction and crowd-control immunity. This is a documented data-only approximation of LoL untargetability: Xayah is not removed from the battlefield and can still be selected by systems that ignore those reductions.

## Audio isolation

- [x] Custom event set: attack cast/hit, Q cast/hit, E cast/launch/hit/catch/root, R cast.
- [x] There is deliberately no `lol_xayah_r_hit` event because the pinned official media audit found no suitable mono R-hit clip.
- [x] Native event keys `dancer_attack`, `dancer_skill1`, `dancer_skill2`, and `dancer_ult` route to `xayah_native_silence`.
- [x] Native clip keys `dancer_attack0`, `dancer_skill_resource`, `dancer_skill2_resource`, and `dancer_ult_resource` route to the 50 ms physical silence clip.

## Automated proof

`tests/test_xayah_mod.py` statically verifies replacement uniqueness, strict Q/E/R mapping, passive/Feather transitions, the two-shot Q delay, bounded Q/R endpoint visuals, E recall/root thresholds, the Mod API 0.8 AI input gate, outbound-only R behavior, localization, compact style, encyclopedia UI registration, VFX identity, and native-audio isolation. `qa/xayah_ground_feather_api_limitations.md` records the exact marker, AI-gate, cleanup, and public-API limits.
