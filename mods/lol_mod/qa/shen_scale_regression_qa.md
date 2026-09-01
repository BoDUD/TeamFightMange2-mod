# Shen scale regression QA

The first live pass was rejected after six user-supplied surfaces showed the same problem in encyclopedia, ban/pick, lineup cards, scoreboard portraits, battle side portraits, and the map actor.

| Metric | Rejected build | HD contract target |
| --- | ---: | ---: |
| Idle visible height | 54 px | 40 px inside the accepted 64 px battle frame |
| Core action visible-height range | 47–54 px | 34–42 px from natural crouch/raised-pose differences at one source scale |
| Foot baseline inside 64×64 frame | y=62 | y=45 |
| Compact surfaces | shared actor-atlas camera | source-direct 64×64 scoreboard and side-list crops |
| Full-body/BP | enlarged packed idle | source-direct 64×64 encyclopedia and 90×122 grid assets |

The HD rebuild keeps the exact same accepted image-gen actor anchor and action poses. It raises the idle target from 36 to 40 pixels, increases palette capacity from 40 to 96 colors, and applies one scale factor to idle/run/attack/skill/hit/dead sources. `validate_lol_mod.py` still fails if any actor frame crosses y=46 or leaves the battle-safe side margins.

The remaining UI blur came from enlarging the already reduced battle idle. Encyclopedia, side-list, scoreboard, and BP-grid art are now derived independently from the accepted 1448×1086 source. Grid art ends at y=86 before the name band; compact assets retain transparent safety margins. The picked side card continues to use Shen's independent 1420×860 illustration. Legacy `face` and `center` offsets remain unchanged as fallbacks.
