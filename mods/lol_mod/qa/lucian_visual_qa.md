# Lucian same-id 002 visual QA

| Surface / action | Source route | Acceptance |
| --- | --- | --- |
| Face / actor | image-gen master v3 4x3 actor sheet: v2 body plus image-edited hit/dead cells, with Shen used only as a scale and compactness reference | one consistent face, hairstyle, coat, body scale and complete boots; idle is 22x36px with visible skin/eye/hair clusters and y=44 foot pixels, with no code-injected face pixels; hit/dead show at most one visible pistol and no floating duplicate |
| Run | image-gen master v2 3x3 loop using the v2 actor as the identity reference and Shen only as the gait/footprint reference | nine unique upright phases, 27-32px wide and exactly 36px tall, all on y=44; body-area CV at most 8%, lower-body density at least 75% of the fullest frame, and adjacent lower-body differences between 0.15 and 0.60 |
| Basic/passive attack | body-only v2 single/double poses plus dedicated image-gen `lucian_attack` projectile | no baked muzzle flash in the actor sheet; one bolt normally and two separate arms, pistols and bolts under Lightslinger |
| Q | body-only 64x64 cast pose plus image-gen v3 gold-white beam packed on a 192x32 projectile canvas | damage and VFX share `lol_lucian_q_piercing_light`; every beam begins at x=104, eight pixels beyond the x=96 rotation pivot, so it starts at the forward pistol muzzle; residual-spark frames are excluded, and no actor-embedded beam remains |
| E | compact v2 dash start/travel bodies | 300-range movement with no release VFX, trail, afterimage, horizontal flying pose or scale jump |
| R | v2 start/fire bodies plus independent image-gen compact bullet | 15 discrete non-piercing projectiles; no baked multi-hit cluster |
| Skill icons | direct `skill_icons` paths | exact order Q, E, R; no W or native Archer atlas cells |
| Compact portrait | `archer` style offsets `face {x:0,y:-34}` and `center {x:0,y:-12}` | centered in compact HUD, scoreboard, cards and battle list at the same height class as Shen |

Generated review sheets are `lucian_actor_contact_final.png`, `lucian_skill_icons_final.png`, and `lucian_vfx_contact_final.png`.

Rejected model files from v10, master v1, and the superseded v2 actor are deleted from active source, processed and QA roots. Their failure history remains only in prompt/QA text so the bad routes cannot be selected by a future build.
