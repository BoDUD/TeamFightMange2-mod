# Kled E Jousting QA

Kled's Jousting approximation is folded into the Q slot because the public champion surface has three active cooldown slots. The separate second UI slot is reserved for the original W four-hit mapping.

## Static contract

- [x] The composite Q owns exactly one `Rush`; no parallel second dash or unsupported fourth active key is declared.
- [x] Rush speed is 3200, Move Speed ratio is 100%, collision range is 12000, and `penetrate=false` stops the dash on the first valid enemy-champion collision.
- [x] `lol_kled_e_cast` plays at dash start and `lol_kled_e_hit` plays on the collided target.
- [x] `lol_kled_q_dash_visual` follows Kled from the independent `kled_q_tether` effect sheet while the actor uses the native `skill1_dash` action.
- [x] The collided target then receives the composite Q latch/delayed-pull payload documented in `kled_q_tether_qa.md`.

## Intentional approximation

There is no standalone E cooldown, no second Jousting recast through the marked target, and no separate direction re-evaluation. The one non-penetrating rush is the frozen data-level approximation that joins E movement to Q's tether identity.

## Pending live checks

- [ ] Kled moves along the selected direction instead of teleporting or homing before contact.
- [ ] The dash stops on the first valid enemy champion and does not pass through that target.
- [ ] A miss completes without applying tether damage, slow, pull, bind, or hit sound.
- [ ] Left/right casts mirror correctly and keep the mounted body, weapon, dust, and dash origin aligned.
- [ ] Collision near walls, towers, or camp boundaries does not produce a large position snap or persistent effect.
