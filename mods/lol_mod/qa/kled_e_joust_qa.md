# Kled E Jousting QA

Kled's second public active is a standalone Jousting dash. It does not activate an attack-speed state and it does not share Q's projectile, tether, delayed pull, or crowd control.

## Static contract

- [x] `skill2.action_name=skill2` is a directional E cast with a 480-tick cooldown, 13-tick action, and 55000 AI cast range.
- [x] E owns exactly one non-penetrating `Rush`: speed 3200, Move Speed ratio 100%, collision radius 12000, enemy-champion target filter.
- [x] The first enemy champion hit takes `30 + 80% AD` exactly once.
- [x] A successful hit grants only Kled `lol_kled_e_hit_speed` for 60 ticks with +20% Move Speed.
- [x] `lol_kled_e_cast` plays at dash start and `lol_kled_e_hit` plays once on the collided target.
- [x] The independent `kled_e_joust` effect sheet supplies `dash` and `impact`; E does not reuse the Q rope sheet.
- [x] E contains no `LinearProjectile`, `Delayed`, `Grab`, `Bind`, Q tether state, or attack-speed/four-hit state machine.

## Intentional approximation

This data-only E stops on the first enemy-champion collision and has one cast. It does not implement League Kled's second recast through a marked target.

## Pending live checks

- [ ] Kled moves along the selected direction instead of teleporting or homing before contact.
- [ ] The dash stops on the first valid enemy champion and does not pass through that target.
- [ ] A miss completes without damage, hit audio, speed buff, Q rope, pull, or bind.
- [ ] Left/right casts mirror correctly and keep the mounted body, dash trail, and impact origin aligned.
- [ ] Collision near walls, towers, or camp boundaries does not produce a position snap or persistent effect.
