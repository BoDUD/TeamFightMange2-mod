# Shen scale regression QA

The first live pass was rejected after six user-supplied surfaces showed the same problem in encyclopedia, ban/pick, lineup cards, scoreboard portraits, battle side portraits, and the map actor.

| Metric | Rejected build | Accepted contract target |
| --- | ---: | ---: |
| Idle visible height | 54 px | 36 px (reference additive contract: ~35 px) |
| Core action visible-height range | 47–54 px | 31–36 px |
| Foot baseline inside 64×64 frame | y=62 | y=45 |
| Compact camera | shared/experimental | `face {x:6,y:-34}` |
| Full-body/BP/battle camera | `center {x:0,y:-12}` | `center {x:0,y:-12}` |

The accepted rebuild keeps the exact same image-gen actor anchor and action poses. It changes only the uniform packing scale and frame placement. `validate_lol_mod.py` now fails if any actor frame crosses y=46, if the first idle does not end at y=44–46, or if core scale varies by more than 22%.

A second user screenshot pass proved that compact portrait scale and vertical placement were already in the official range, but the floating blade pulled Shen's helmet 12 rendered pixels to the right. Source-to-screen pixel matching established a fixed 2x render, so `face.x=6` is the measured per-champion correction; `face.y=-34` and the battle `center` remain unchanged.
