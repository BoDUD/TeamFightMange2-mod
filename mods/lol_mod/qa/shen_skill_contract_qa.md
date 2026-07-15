# Shen skill contract QA

Official comparison baseline:

- Riot champion page: <https://www.leagueoflegends.com/en-us/champions/shen/>
- Riot Data Dragon 16.13.1: <https://ddragon.leagueoflegends.com/cdn/16.13.1/data/en_US/champion/Shen.json>
- Riot 25.08 / 25.09 notes for current Q slow and empowered percentages.
- Riot 25.12 notes for current E bonus-health ratio.

| Design target | Engine slot | Runtime contract | Status |
| --- | --- | --- | --- |
| Basic attack | `attack` | Normal branch remains one delayed 100% Attack hit. Three nested `SwitchByBuff` branches consume `charge_3`, `charge_2`, then `charge_1`; every empowered hit adds `20 + 20% Ability Power` magic damage and removes only its current marker. The shared 480-tick window is never refreshed by attacking. | implemented |
| Q / Twilight Assault / 奥义！暮临 | `skill` | Direction + enemy-champion targeting remains only as the stock AI's valid cast gate. The spell creates one visible, non-damaging `BackToCasterLinearProjectile` named `lol_shen_twilight_assault_blade_recall`, travelling from the selected cast point back to Shen; there is no fabricated outbound leg. The cast immediately clears stale Q markers, grants exactly three 480-tick empowered-attack charges, and shows `lol_shen_twilight_assault_recall_arrival` when the blade reaches Shen. It does not implement a pass-through upgrade branch. | implemented recall approximation |
| E / Shadow Dash / 奥义！影缚 | `skill2` | Direction cast has a 60,000 top-level travel distance. Its penetrating `Rush.range` is a separately named 10,000 swept collision radius, not the travel distance. Every crossed enemy champion takes 60 physical damage and invokes `lol_shen_shadow_dash_taunt_native`; the native effect calls `apply_cc` with `CCState::Taunt { tick: 90, target: caster_id }` and reports `expected_cc_time() == Some(90)` to the stock AI. A 30-tick caster-follow dash trail, one hit impact, and a separate 90-tick taunt marker make movement, collision, and forced targeting readable. | implemented approximation |
| W / Spirit's Refuge | no active slot | Removed from `skill2`; the active champion payload contains no refuge field, ally shield, enemy attack-speed debuff or `lol_shen_w_*` event. | intentionally omitted |
| R / Stand United | `ult` | `AllyNotSelf` target; 900 + 80% AP shield for 180 ticks; 48-tick engine-paced channel; real `Teleport`; arrival SFX/VFX. R arrival contains no `Taunt` and no circular enemy `RangeEffect`. | implemented approximation |

Named state proof:

- `lol_shen_twilight_assault_charge_3`
- `lol_shen_twilight_assault_charge_2`
- `lol_shen_twilight_assault_charge_1`
- `lol_shen_twilight_assault_blade_recall`
- `lol_shen_twilight_assault_recall_arrival`
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

- The public data-champion surface has no persistent, independently positioned spirit-blade entity. Q therefore renders one target-point-to-Shen recall and does not claim a blade position retained between casts. This limit belongs in QA only; player-facing skill text states the visible action and three empowered attacks without API commentary.
- The removed outbound trace, pass-through detection, slow, and stronger pass-through attack branch must not return unless a persistent blade position and reliable crossing test are implemented. A recognizable single recall is preferable to text or effects that claim unsupported precision.
- The verified `ApAttack` primitive gives safe magic damage but has no proven target-maximum-HP scaling field, so the three-hit state machine uses flat + AP magic damage rather than claiming the official percentage damage.
- All three Q markers are created together and expire together after 480 ticks. The nested switch consumes only the highest remaining marker, so spaced attacks cannot extend the official eight-second window.
- E keeps the official direction dash, path collision, physical damage and 1.5-second forced-target identity. The public data field has no verified bonus-health damage ratio or energy resource, so those parts are not claimed.
- `AllyNotSelf` uses the built-in AI target score. The public data/API surface has no `LowestHpAlly` target, so R does not claim exact lowest-health selection. Its 48-tick channel is retained as the existing engine pacing compromise instead of the official three seconds.

Player-facing localization gate:

- `en`, `zh-hans`, `zh-hant`, `ja`, and `ko` Q/E/R descriptions each fit a conservative four-line display-width budget.
- Skill descriptions contain mechanics only. Engine/API limits, implementation names, approximation notes, and target-selection caveats remain in this QA document instead of the encyclopedia.
