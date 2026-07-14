# Shen skill contract QA

Official comparison baseline:

- Riot champion page: <https://www.leagueoflegends.com/en-us/champions/shen/>
- Riot Data Dragon 16.13.1: <https://ddragon.leagueoflegends.com/cdn/16.13.1/data/en_US/champion/Shen.json>
- Riot 25.08 / 25.09 notes for current Q slow and empowered percentages.
- Riot 25.12 notes for current E bonus-health ratio.

| Design target | Engine slot | Runtime contract | Status |
| --- | --- | --- | --- |
| Basic attack | `attack` | Normal branch remains one delayed 100% Attack hit. Six nested `SwitchByBuff` branches prefer the three `through_charge` markers before the three normal charge markers. Normal Q hits add `20 + 20% Ability Power`; a blade pass-through upgrades only the normal charges still unused to `35 + 30% Ability Power`. Each attack consumes only its current marker and never refreshes the shared window. | implemented |
| Q / Twilight Assault / 奥义！暮临 | `skill` | Direction cast is still gated by an enemy champion within 55,000 engine units, so the stock AI has a target context and cannot self-cast at match start. A penetrating, non-damaging outbound spirit-blade trace travels 65,000 units; its direct `end_effects` own exactly one 130,000-unit `BackToCasterLinearProjectile`. The cast grants three normal 480-tick charges. A named `return_resolved` guard lets only the first champion crossed by the return path upgrade the charges still unused, grant 35% Attack Speed for 120 ticks, and receive a 30% slow for 90 ticks. | implemented target-directed path approximation |
| E / Shadow Dash / 奥义！影缚 | `skill2` | Direction cast has a 60,000 top-level travel distance. Its penetrating `Rush.range` is a separately named 10,000 swept collision radius, not the travel distance. Each crossed champion takes 60 physical damage and invokes `lol_shen_shadow_dash_taunt_native`; the native effect calls `apply_cc` with `CCState::Taunt { tick: 90, target: caster_id }` and reports `expected_cc_time() == Some(90)` to the engine AI. A 30-tick trail marker, impact VFX, built-in taunt state and 90-tick taunt marker provide separate dash/hit/control reads. | implemented approximation |
| W / Spirit's Refuge | no active slot | Removed from `skill2`; the active champion payload contains no refuge field, ally shield, enemy attack-speed debuff or `lol_shen_w_*` event. | intentionally omitted |
| R / Stand United | `ult` | `AllyNotSelf` target; 900 + 80% AP shield for 180 ticks; 48-tick engine-paced channel; real `Teleport`; arrival SFX/VFX. R arrival contains no `Taunt` and no circular enemy `RangeEffect`. | implemented approximation |

Named state proof:

- `lol_shen_twilight_assault_charge_3`
- `lol_shen_twilight_assault_charge_2`
- `lol_shen_twilight_assault_charge_1`
- `lol_shen_twilight_assault_through_charge_3`
- `lol_shen_twilight_assault_through_charge_2`
- `lol_shen_twilight_assault_through_charge_1`
- `lol_shen_twilight_assault_return_resolved`
- `lol_shen_twilight_assault_through_attack_speed`
- `lol_shen_twilight_assault_pull_slow`
- `lol_shen_shadow_dash_trail_window`
- `lol_shen_shadow_dash_taunted`
- `lol_shen_stand_united_channel`
- `lol_shen_stand_united_shield_window`

Native runtime proof:

- `ShenShadowDashTauntNativeEffect`
- `lol_shen_shadow_dash_taunt_native`
- `ctx.apply_cc(target_id, CCState::Taunt { tick: 90, target: caster_id })`
- `expected_cc_time() -> Some(90)`
- no Shen-specific `ModPlayerInputAi` is registered; the rejected target revalidation route is not restored.

Documented limits:

- The public data-champion surface has no persistent, independently positioned spirit-blade entity. Q therefore sends a target-directed trace and recalls it from that cast's endpoint; it does not claim a blade position retained between casts.
- The data surface cannot test whether the crossed champion is moving away from Shen. The 30% slow is therefore applied to the first enemy champion crossed by the returning trace. A named once-per-cast guard prevents later overlaps from reapplying the upgrade or refilling consumed charges; the stronger Attack Speed branch is a conservative 35% for 120 ticks rather than claiming exact live-LoL rank scaling.
- The verified `ApAttack` primitive gives safe magic damage but has no proven target-maximum-HP scaling field, so the three-hit state machine uses flat + AP magic damage rather than claiming the official percentage damage.
- All three Q markers are created together and expire together after 480 ticks. The nested switch consumes only the highest remaining marker, so spaced attacks cannot extend the official eight-second window.
- E keeps the official direction dash, path collision, physical damage and 1.5-second forced-target identity. The public data field has no verified bonus-health damage ratio or energy resource, so those parts are not claimed.
- `AllyNotSelf` uses the built-in AI target score. The public data/API surface has no `LowestHpAlly` target, so R does not claim exact lowest-health selection. Its 48-tick channel is retained as the existing engine pacing compromise instead of the official three seconds.
