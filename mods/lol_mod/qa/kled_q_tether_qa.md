# Kled Q tether QA

This file audits Bear Trap on a Rope inside the composite Q slot. Jousting movement in the same slot is audited separately in `kled_e_joust_qa.md`.

## Static contract

- [x] The public Q slot is `skill1`, directional, enemy-champion-targeted, 65000 range, 360-tick cooldown, and 36-tick duration.
- [x] The first rush collision deals `30 + 80% AD` and applies `lol_kled_q_tethered` for 45 ticks with -20% Move Speed.
- [x] Kled receives the named `lol_kled_q_hit_speed` buff for 60 ticks with +20% Move Speed.
- [x] `lol_kled_q_tether_visual` uses the independent `tether` tag and the buff owns `tether_pre`, `tether_loop`, and `tether_remove` phases.
- [x] Exactly one delayed block runs at tick 45 and deals `20 + 40% AD` before `Grab(speed=2200,tick=8)` and `Bind(duration=30)`.
- [x] Initial latch and delayed pull use distinct official-audio events: `lol_kled_q_tether_on` and `lol_kled_q_pull`.

## Intentional approximation

The public data layer schedules the delayed payload on the initially collided target. It does not re-measure the distance between Kled and that target at tick 45, so moving out of a League-like tether radius cannot break this approximation. The rope is a visual/buff state rather than a separately simulated breakable projectile.

## Pending live checks

- [ ] The initial collision selects the intended enemy champion once and never a stale target behind Kled.
- [ ] The rope/trap visual begins at the target, remains readable without covering the whole actor, and removes cleanly.
- [ ] The delayed damage, pull, and bind happen once after the visible delay and do not duplicate under repeated ticks.
- [ ] Casting left and right keeps the hook, rope, and pull centered and produces no actor-scale jump.
- [ ] Target death or invalidation during the delay does not leave a permanent tether VFX or stuck buff.
