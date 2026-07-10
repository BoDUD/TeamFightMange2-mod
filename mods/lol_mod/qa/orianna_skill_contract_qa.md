# Orianna same-id official 003 skill contract

Orianna reworks the native `barrier_magician` ID through the official same-ID `.data_champion` path. The official 003 roster position, references and save identity remain stable, while combat uses Orianna's data-defined attack/Q/E/R contract instead of the hard-coded Barrier Mage actions.

| Design target | Engine slot | Frozen runtime contract | Status |
| --- | --- | --- | --- |
| Basic attack / Clockwork Windup | `attack` | ImageGen v3 mechanical energy-dart target projectile; `100% Attack` physical damage plus `10 + 15% Ability Power` magic damage; official OnCast + MissileLaunch + OnHit audio identity | required |
| Q / Command: Attack | `skill` | `EnemyChampion` target; `ParabolicProjectile`, 15-tick travel; 26,000 impact radius for `50 + 55% AP`; fixed 30,000-radius field for 180 ticks; allies +18% move speed, enemies -22%; `SwitchByLevel3` adds ally +15% and enemy -15% attack speed | required |
| E / Command: Protect | `skill2` | `AllyChampion` target, including self; `TargetProjectile` speed 6000; `180 + 55% AP` shield for 180 ticks; a `WithShield` buff grants +12 Defence/Magic Resistance, 15% skill-damage reduction and 10% basic-attack reduction | required |
| R / Command: Shockwave | `ult` | `EnemyChampion` target; 60,000-to-18,000 shrinking ring over 60 ticks with an 8-tick edge Bind; after 60 ticks, the same target-point context applies a 42,000-radius `130 + 100% AP` hit, `Pull {speed:3200,tick:12}` and 24-tick Airborne | required |

Critical location rule:

- R first uses a one-tick `ParabolicProjectile` to capture the selected enemy's current position; the ring then stays fixed at that landing point.
- The delayed damage, Pull and Airborne must resolve at that same fixed point through the projectile-end/range-projectile context.
- A caster-centered `RangeEffect` would pull enemies toward Orianna and is a contract failure even if the damage numbers match.

Named data-state and hitbox proof:

- Basic projectile: `lol_orianna_attack_dart` (a large elongated mechanical energy bolt, never the Ball); `lol_orianna_attack_cast` layers the official OnCast and MissileLaunch clips before target-side `lol_orianna_attack_hit`
- Q travel/field: `lol_orianna_q_ball`, `lol_orianna_q_field_visual`, `lol_orianna_q_field_enemy_logic`
- Q field buffs: `lol_orianna_q_ally_move`, `lol_orianna_q_enemy_move`, `lol_orianna_q_ally_attack_speed`, `lol_orianna_q_enemy_attack_speed`
- E travel/protection: `lol_orianna_e_ball`, `lol_orianna_protect`; the latter must use `duration: WithShield`
- R logic: `lol_orianna_r_ring_logic` followed by `lol_orianna_r_burst_hitbox`; neither logic-only name may be registered as a visible projectile
- R visuals: `lol_orianna_r_ring_visual` and `lol_orianna_r_burst_visual` both resolve at the captured landing point and must not follow the enemy after placement

Documented three-slot compromise:

- The public data champion surface exposes Q, E and R as the three active UI slots; Orianna's W identity is folded into Q's fixed landing field.
- The Ball is deliberately non-persistent. Q leaves only a timed landing field, E's attachment/protection marker lasts only with its shield, and R targets an enemy champion rather than querying a stored Ball entity.
- Text and QA must not claim a persistent Ball, free-standing cross-cast Ball state, or a fourth active W cooldown.

Required data/visibility chain:

- `champion/barrier_magician.data_champion` with `id: barrier_magician`
- `description.barrier_magician` in all five maintained locales
- `entries.barrier_magician` in `style/champion_view`
- direct Q/E/R `skill_icons` ordering and original Orianna actor/effect assets
