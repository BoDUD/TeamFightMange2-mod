# Briar same-id official 004 skill contract

Briar replaces official champion 004 through the native `berserker` ID and `champion/berserker.data_champion`. This preserves the official roster position, save identity and references. There must be no additive `lol_briar.data_champion` registration. The public UI exposes exactly three active slots labelled Q, E and R.

| Design target | Engine slot | Frozen runtime contract | Status |
| --- | --- | --- | --- |
| Basic attack / Crimson Curse | `attack` | `Enemy` target, range 25,000; `100% Attack` physical hit. Each application requests a 120-tick Bleed with period 60; every tick deals `4 + 3% Attack`, heals the caster for `2 + 1% Attack`, and plays the short bleed visual. | required |
| Empowered Snack | `attack` through `SwitchByBuff(lol_briar_snack_ready)` | Next attack keeps the base `100% Attack` hit, adds `25 + 40% Attack + 2% target maximum HP`, heals Briar for `40 + 15% Attack`, applies Crimson Curse, plays frenzy attack audio, then removes `lol_briar_snack_ready`. | required |
| Q / Blood Frenzy | `skill` | `EnemyChampion` target gate, range 45,000, cooldown 360, 20-tick action. For 180 ticks grants +60% attack speed, +18% move speed and 25 Vamp, and creates exactly one `lol_briar_snack_ready`. If R frenzy is active, Q refreshes only the one Snack and does not replace the enhanced R state. One 0.46-second `lol_briar_q_overhead_visual` follows the selected target above its head; the state no longer uses a persistent body-enclosing ring. | required |
| E / Chilling Scream | `skill2` | Direction cast against `EnemyWithoutTower`, 50,000 length and 24,000 width; 30-tick fixed charge within a 54-tick action. On cast Briar gets 35% damage reduction for 30 ticks and heals `50 + 15% Attack`; release deals `75 + 100% Attack`, applies Crimson Curse, Knockback `{speed:3000,tick:12}` and 18-tick Airborne. | required |
| R / Certain Death | `ult` | `EnemyChampion` target, range 80,000, cooldown 3600. Shows the target mark and waits 18 ticks, then `MoveToTarget` at speed 6000. Arrival deals `100 + 120% Attack`, applies Crimson Curse, fears enemy champions within 30,000 for 30 ticks, and grants 240 ticks of enhanced frenzy: +50% attack speed, +25% move speed, 30 Vamp, +20 Defence, +20 Magic Resistance and +20 Toughness, plus one Snack. | required |

Named state, VFX and audio proof:

- Passive marker and tick: `lol_briar_crimson_curse`, `lol_briar_bleed_tick_visual`.
- Q states: `lol_briar_blood_frenzy`, `lol_briar_snack_ready`; the short target-following marker is `lol_briar_q_overhead_visual`, and Q cast audio is `lol_briar_q_cast`.
- Normal and empowered attacks route through `lol_briar_attack_cast/hit` and `lol_briar_frenzy_cast/hit` respectively.
- E visual-only travel is `lol_briar_e_scream_projectile`; damage and control come from `lol_briar_e_hitbox`, preventing the visual projectile from double-hitting.
- E protection state is `lol_briar_chilling_scream_guard`; audio is `lol_briar_e_cast/hit`.
- R uses `lol_briar_r_mark_visual`, `lol_briar_r_trail_visual`, `lol_briar_r_arrival_visual` and `lol_briar_certain_death_frenzy`; audio is `lol_briar_r_cast/hit`.

Documented public-data limitations:

- Q uses an enemy-champion target only as an in-range cast gate. Public data does not force Briar to attack that target, change AI aggro, or expose League's manual second W cast; the next ordinary attack consumes the single Snack.
- The Bleed contract has fixed duration and period. Public data has no missing-health scaling, current-health branch, kill trigger or exact heal-from-damage primitive. Whether repeated applications refresh or stack, and whether every delayed Heal retains the original caster context, are mandatory live tests.
- E is a fixed 30-tick charge. It has no player-controlled early release, charge-ratio damage curve, wall collision query, wall bonus or stun-on-wall behavior. Its heal is a fixed caster heal rather than League's missing-health heal.
- R v0.5.0 is a warned targeted chase, not a missable global linear projectile or first-enemy collision. Public data does not guarantee a new target if the selected target dies during the warning/chase; that lifecycle must fail safely in live QA.
- Public data cannot force the R target as Briar's subsequent attack target or recreate the full berserk AI. Enhanced frenzy is represented by timed stats, Vamp, defences, Toughness and one Snack.

Required same-ID and visibility chain:

- `champion/berserker.data_champion` with `id: berserker`.
- `description.berserker` in every maintained locale and `entries.berserker` in `style/champion_view`.
- `skill_icons` ordered Q, E, R: `briar_skill`, `briar_skill2`, `briar_ult`.
- Actor sprite `asset/lol_mod/aseprite_resources/champions/briar` and separate passive/Q/E/R effect sheets.
- Exactly one official 004 entry in encyclopedia, custom champion pool, draft and saves; no duplicate additive Briar ID.
