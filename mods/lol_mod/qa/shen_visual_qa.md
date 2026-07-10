# Shen visual QA

| Surface / ability | Source route | Result |
| --- | --- | --- |
| Actor model | built-in image-gen 4x3 accepted character anchor, chroma-keyed and packed to 64x64 frames at the proven ~35 px body-height class with the official y=45 foot baseline | generated; oversize and 17 px low-anchor regressions fixed |
| Idle/run/attack | accepted actor anchor plus an image-gen 3x3 run refinement; stable 36 px scale and y=45 baseline | nine unique 0.08 s run phases; no loop-end duplicate |
| Q | separate spectral blade projectile sheet | distinct |
| W | separate image-gen refuge-field sheet, packed to a 104x30 ground ellipse centered at (56, 43.5) | distinct; caster foot point and field center aligned |
| R | separate target shield / teleport arrival sheet | distinct |
| Skill icons | three independent built-in image-gen sources, ordered Q/W/R | distinct |
| Compact portrait | measured `face {x:6,y:-34}` camera over the y=45 actor baseline; `center {x:0,y:-12}` remains the full-body/BP/battle camera | source-to-screen match removes the 12 px right shift; live recheck required |

Acceptance rule: generated cast effects may be masked out of actor cells because Q/W/R have dedicated VFX sheets. No code-drawn substitute body is allowed. The accepted actor sources are `source/imagegen/shen_actor_contact.png` and its model-consistent `source/imagegen/shen_run_contact.png` refinement.
