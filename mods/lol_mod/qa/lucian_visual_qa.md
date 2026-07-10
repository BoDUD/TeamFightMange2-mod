# Lucian same-id 002 visual QA

| Surface / action | Source route | Acceptance |
| --- | --- | --- |
| Face / actor | image-gen v2 4x3 chibi actor source | warm high-contrast face at the official 002 idle envelope: 31-33px high, about 25px wide, y=45 foot baseline |
| Run | image-gen v3 compact 3x3 sprint source | nine unique crouched gunslinger phases, cross/passing steps, at most 31px high/30px wide, distinct from Shen |
| Basic/passive attack | v2 actor muzzle poses plus dedicated image-gen `lucian_attack` projectile | one bolt normally; two separate bolts under Lightslinger |
| Q | independent image-gen gold-white beam | direction-aware projectile rotates around x=96 and starts at x=116, so both facings begin at the forward pistol muzzle; distinct from cyan attack/R bullets |
| E | actor dash animation only | 300-range movement with no release VFX, trail or afterimage |
| R | independent image-gen compact bullet | 15 discrete non-piercing projectiles, no baked multi-hit cluster |
| Skill icons | direct `skill_icons` paths | exact order Q, E, R; no W or native Archer atlas cells |
| Compact portrait | `archer` style offsets `face {x:0,y:-34}` and `center {x:0,y:-12}` | centered in compact HUD, scoreboard, cards and battle list |

Generated review sheets are `lucian_actor_contact_final.png`, `lucian_skill_icons_final.png`, and `lucian_vfx_contact_final.png`.
