# Shen skill contract QA

Official comparison baseline:

- Riot champion page: <https://www.leagueoflegends.com/en-us/champions/shen/>
- Riot Data Dragon 16.13.1: <https://ddragon.leagueoflegends.com/cdn/16.13.1/data/en_US/champion/Shen.json>
- Riot 25.08 / 25.09 notes for current Q slow and empowered percentages.
- Riot 25.12 notes for current E bonus-health ratio.

| Design target | Engine slot | Runtime contract | Status |
| --- | --- | --- | --- |
| Basic attack | `attack` | Normal branch remains one delayed 100% Attack hit. Three nested `SwitchByBuff` branches consume `lol_shen_twilight_assault_charge_3 -> _2 -> _1`; each empowered hit keeps the normal strike and adds `20 + 20% Ability Power` magic damage plus the Q hit visual. Attacks never create or refresh a charge marker. | implemented |
| Q / Twilight Assault / 奥义！暮临 | `skill` | Safe self cast, 360-tick cooldown and one shared 480-tick window. It removes stale charge states, recalls the spirit-blade visual to Shen and grants all three independently consumed markers at cast time. It contains no damage projectile, target callback, direct Q hit, slow or Q-owned shield. | implemented stable approximation |
| E / Shadow Dash / 奥义！影缚 | `skill2` | Direction cast with 60,000 action range. One penetrating `Rush` uses speed 4,000, Move Speed ratio 100% and 10,000 collision radius against enemy champions. Every champion crossed takes 60 physical damage, receives `Taunt(90)` and `lol_shen_shadow_dash_taunted`, then plays the independent impact VFX. | implemented approximation |
| W / Spirit's Refuge | no active slot | Removed from `skill2`; the active champion payload contains no refuge field, ally shield, enemy attack-speed debuff or `lol_shen_w_*` event. | intentionally omitted |
| R / Stand United | `ult` | `AllyNotSelf` target; 900 + 80% AP shield for 180 ticks; 48-tick engine-paced channel; real `Teleport`; arrival SFX/VFX. R arrival contains no `Taunt` and no circular enemy `RangeEffect`. | implemented approximation |

Named state proof:

- `lol_shen_twilight_assault_charge_3`
- `lol_shen_twilight_assault_charge_2`
- `lol_shen_twilight_assault_charge_1`
- `lol_shen_shadow_dash_taunted`
- `lol_shen_stand_united_channel`
- `lol_shen_stand_united_shield_window`

Documented limits:

- The public data-champion surface has no persistent, independently positioned spirit-blade entity. Q therefore cannot prove whether the recall path crossed a champion, cannot apply the official slow only while that champion moves away from Shen, and cannot conditionally grant the stronger 50% Attack Speed branch. A visual-only caster effect is used instead of an unstable projectile callback.
- The verified `ApAttack` primitive gives safe magic damage but has no proven target-maximum-HP scaling field, so the three-hit state machine uses flat + AP magic damage rather than claiming the official percentage damage.
- All three Q markers are created together and expire together after 480 ticks. The nested switch consumes only the highest remaining marker, so spaced attacks cannot extend the official eight-second window.
- E keeps the official direction dash, path collision, physical damage and 1.5-second taunt identity. The public data field has no verified bonus-health damage ratio or energy resource, so those parts are not claimed.
- `AllyNotSelf` uses the built-in AI target score. The public data/API surface has no `LowestHpAlly` target, so R does not claim exact lowest-health selection. Its 48-tick channel is retained as the existing engine pacing compromise instead of the official three seconds.
