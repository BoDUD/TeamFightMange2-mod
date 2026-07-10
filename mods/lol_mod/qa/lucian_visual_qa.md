# Lucian native-002 visual QA

| Surface / ability | Route | Acceptance |
| --- | --- | --- |
| Actor model | native `archer#sheet` replacement | 64x64 safe frames, y=45 foot baseline, 34-37 px standing height |
| Run | native `run` tag | eight unique phases with alternating contacts and visible cross-steps |
| Attacks | native `attack`, `skill_attack`, `skill`, `skill2` tags | centered actor; readable pistol poses without edge crop |
| R | native `ult_pre`, `ult_loop`, `ult_end`, `ult_projectile` tags | all native frame counts and timings preserved |
| Skill icons | five patched `archer_0` through `archer_4` cells in the base 4096x49 atlas | generated E/Q/R art appears in every 002 UI slot |
| Portrait | `archer` style offsets `face {x:0,y:-34}` and `center {x:0,y:-12}` | centered in compact HUD, scoreboard, cards and battle list |

Generated contact sheets remain `lucian_actor_contact_final.png`, `lucian_skill_icons_final.png`, and `lucian_vfx_contact_final.png`.
