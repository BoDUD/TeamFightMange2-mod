# Kled Q tether QA

Bear Trap on a Rope is an independent directional projectile. Q never moves Kled and never invokes E's dash effects or audio.

## Static contract

- [x] `skill.action_name=skill1` is directional, enemy-champion-targeted, 65000 range, 360-tick cooldown, and 36-tick duration.
- [x] Q launches exactly one `LinearProjectile` named `lol_kled_q_beartrap_projectile` at speed 6500 over 72000 projectile range with a 10000-radius circle; the AI/action range stays 65000.
- [x] `penetrate=false` and `applied_target=EnemyChampion` make the trap stop on the first valid enemy champion; Q contains no `Rush`.
- [x] The first hit deals `30 + 80% AD` and applies `lol_kled_q_tethered` for 45 ticks with -20% Move Speed.
- [x] The travelling trap, latch, and pull use independent `projectile`, `latch`, and `pull` tags from `kled_q_tether`.
- [x] The tether buff owns `tether_pre`, `tether_loop`, and `tether_remove` phases.
- [x] Exactly one delayed block runs at tick 45 and deals `20 + 40% AD` before `Grab(speed=2200,tick=8)` and `Bind(duration=30)`.
- [x] Initial latch and delayed pull use distinct audio events: `lol_kled_q_tether_on` and `lol_kled_q_pull`.
- [x] Q contains no E cast audio, E Move Speed buff, or retired four-hit state.

## Intentional approximation

The public data layer schedules the delayed payload on the initially hit target. It does not re-measure the distance between Kled and that target at tick 45, so moving beyond a League-like tether radius cannot break this approximation.

## Pending live checks

- [ ] The trap visibly leaves Kled's weapon and travels in the selected direction instead of emerging as a body-sized aura.
- [ ] It stops on the intended first enemy champion and cannot pass through into another target.
- [ ] Moving enemy champions remain hittable at close, medium, and the 65000 action-range edge without changing Q into a lock-on cast.
- [ ] A miss ends cleanly without latch, damage, slow, delayed pull, or hit audio.
- [ ] The rope/trap visual remains readable without covering Kled or the target and removes cleanly.
- [ ] The delayed damage, pull, and bind occur once and do not duplicate under repeated ticks.
- [ ] Casting left and right keeps the projectile, latch, rope, and pull centered without actor-scale jumps.
