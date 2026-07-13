# Shen visual QA

| Surface / ability | Source route | Result |
| --- | --- | --- |
| Actor model | accepted built-in image-gen 4x3 high-resolution character anchor, chroma-keyed and uniformly packed to 64x64 frames at a 40 px idle target with the official y=45 foot baseline | x/y scale is identical for every source pose; 96-color finish preserves helmet, eyeslit and armor separation without changing the model |
| Idle/run/attack | accepted actor anchor plus the accepted image-gen 3x3 run refinement, all using the same actor scale | nine unique 0.08 s run phases; no per-frame squeeze, no loop-end duplicate |
| Q | separate spectral blade projectile sheet | distinct |
| W | separate image-gen refuge-field sheet, packed to a 104x30 ground ellipse centered at (56, 43.5) | distinct; caster foot point and field center aligned |
| R | separate target shield / teleport arrival sheet | distinct |
| Skill icons | three independent built-in image-gen sources, ordered Q/W/R | distinct |
| UI surfaces | accepted high-resolution idle source, never the reduced battle atlas | independent 64x64 encyclopedia full-body, 64x64 side-list crop, 64x64 scoreboard crop and 90x122 BP-grid crop; grid pixels end at y=86 before the name band; picked side-card keeps the independent 1420x860 splash |

Acceptance rule: generated cast effects may be masked out of actor cells because Q/W/R have dedicated VFX sheets. No code-drawn substitute body is allowed. The accepted actor sources are `source/imagegen/shen_actor_contact.png` and its model-consistent `source/imagegen/shen_run_contact.png` refinement. Source quality was sufficient, so this HD pass did not generate a new model or alter skill logic.
