# Lucian same-id 002 visual QA

| Surface / action | Source route | Acceptance |
| --- | --- | --- |
| Face / actor | image-gen master v3 4x3 high-resolution actor sheet: v2 body plus image-edited hit/dead cells | one consistent face, hairstyle, coat, body scale and complete boots; idle is 24-25x40px with a 96-color finish and visible skin/eye/hair clusters, with no code-injected face pixels; every action uses the same uniform source scale |
| Run | image-gen master v2 3x3 loop using the accepted v3 actor as identity and scale reference | nine unique upright phases, 30-35px wide and 38-40px tall on y=44; natural pose-height differences remain, but no frame is independently squeezed or enlarged |
| Basic/passive attack | body-only v2 single/double poses plus dedicated image-gen `lucian_attack` projectile | no baked muzzle flash in the actor sheet; one bolt normally and two separate arms, pistols and bolts under Lightslinger |
| Q | body-only 64x64 cast pose plus image-gen v3 gold-white beam packed on a 192x32 projectile canvas | damage and VFX share `lol_lucian_q_piercing_light`; every beam begins at x=104, eight pixels beyond the x=96 rotation pivot, so it starts at the forward pistol muzzle; residual-spark frames are excluded, and no actor-embedded beam remains |
| E | compact v2 dash start/travel bodies | 300-range movement with no release VFX, trail, afterimage, horizontal flying pose or scale jump |
| R | v2 start/fire bodies plus independent image-gen compact bullet | 15 discrete non-piercing projectiles; no baked multi-hit cluster |
| Skill icons | direct `skill_icons` paths | exact order Q, E, R; no W or native Archer atlas cells |
| UI surfaces | accepted high-resolution idle source, never the reduced battle atlas | independent 64x64 encyclopedia full-body, 64x64 side-list crop, 64x64 scoreboard crop and 90x122 BP-grid crop; grid pixels end at y=86 before the name band; picked side-card keeps the independent 1420x860 splash |

Generated review sheets are `lucian_actor_contact_final.png`, `lucian_skill_icons_final.png`, and `lucian_vfx_contact_final.png`.

Rejected model files from v10, master v1, and the superseded v2 actor are deleted from active source, processed and QA roots. Their failure history remains only in prompt/QA text so the bad routes cannot be selected by a future build. The accepted v3 source already contained readable facial information, so this HD pass reused it and did not change skills, silhouette identity, or audio.
