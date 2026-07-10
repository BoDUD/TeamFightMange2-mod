# Lucian visual QA

| Surface / ability | Source route | Acceptance |
| --- | --- | --- |
| Actor model | built-in image-gen 4x3 actor source, chroma-keyed and packed into 64x64 frames | fixed y=45 foot baseline; standing body in the same ~35–36 px class as the accepted Shen/base roster scale |
| Run | separate image-gen 3x3 refinement | nine unique 0.075 s phases with alternating left/right contacts and visible passing/cross-step poses |
| Attack/passive | independent right-shot, left-shot and double-shot actor poses plus generated cyan bullet VFX | passive second projectile is six ticks behind the first |
| Q | independent image-gen beam icon and eight-frame straight-beam VFX | fixed origin; 96x48 projectile frames |
| E | independent image-gen dash icon and eight-frame afterimage VFX | active actor remains the runtime center; follow-layer uses the same y=45 foot point |
| R | independent image-gen bullet-storm icon and eight-frame single-bullet VFX | one non-piercing projectile per shot; no baked multi-hit cluster |
| Compact portrait | measured `face {x:0,y:-34}` and `center {x:0,y:-12}` over the fixed actor baseline | head is centered without reusing full-body scale as a face crop |

Generated contact sheets are `lucian_actor_contact_final.png`, `lucian_skill_icons_final.png`, and `lucian_vfx_contact_final.png`.
