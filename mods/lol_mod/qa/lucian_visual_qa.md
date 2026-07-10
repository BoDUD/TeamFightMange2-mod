# Lucian same-id 002 visual QA

| Surface / action | Source route | Acceptance |
| --- | --- | --- |
| Face / actor | image-gen v10 unified 7x3 model with final-scale face redesign | one consistent face, hairstyle, coat, body scale, two complete boots and two separate pistols across all 21 poses; both idle eyes pack to separate x=30/x=34 pixels on one row at 35px height and y=45 baseline |
| Run | the same v10 unified actor source | nine unique alternating-contact gunslinger phases with two passing/cross steps; no separately generated model or Shen-derived gait |
| Basic/passive attack | v10 single/double muzzle poses plus dedicated image-gen `lucian_attack` projectile | one bolt normally; two separate arms, pistols and bolts under Lightslinger |
| Q | image-gen v3 gold-white eight-phase beam embedded in Q wide frames | one 1-tick fixed damage line; visual frames are centered on Lucian and mirror with his facing, begin at the pistol muzzle, remain visibly distinct from cyan attacks and cannot track a target |
| E | actor dash animation only | 300-range movement with no release VFX, trail or afterimage |
| R | independent image-gen compact bullet | 15 discrete non-piercing projectiles, no baked multi-hit cluster |
| Skill icons | direct `skill_icons` paths | exact order Q, E, R; no W or native Archer atlas cells |
| Compact portrait | `archer` style offsets `face {x:0,y:-34}` and `center {x:0,y:-12}` | centered in compact HUD, scoreboard, cards and battle list |

Generated review sheets are `lucian_actor_contact_final.png`, `lucian_skill_icons_final.png`, and `lucian_vfx_contact_final.png`.
