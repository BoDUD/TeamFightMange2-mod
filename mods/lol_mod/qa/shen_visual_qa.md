# Shen visual QA

| Surface / ability | Source route | Result |
| --- | --- | --- |
| Actor model | built-in image-gen 4x3 accepted character anchor, chroma-keyed and packed to 64x64 frames at the proven ~35 px body-height class with the official y=45 foot baseline | generated; oversize and 17 px low-anchor regressions fixed |
| Idle/run/attack | exact accepted actor anchor; stable global scale; no replacement model | generated; live map check required |
| Q | separate spectral blade projectile sheet | distinct |
| W | separate elliptical refuge-field sheet | distinct |
| R | separate target shield / teleport arrival sheet | distinct |
| Skill icons | three independent built-in image-gen sources, ordered Q/W/R | distinct |
| Compact portrait | independent `face {x:0,y:-34}` camera over the y=45 actor baseline; `center {x:0,y:-12}` remains the full-body/BP/battle camera | static contract aligned; six supplied live surfaces require recheck |

Acceptance rule: generated cast effects may be masked out of actor cells because Q/W/R have dedicated VFX sheets. No code-drawn substitute body is allowed. The accepted actor source is `source/imagegen/shen_actor_contact.png`; all runtime actor frames are derived only from that file.
