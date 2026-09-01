# Orianna same-id official 003 visual QA

| Surface / action | Original source route | Acceptance gate |
| --- | --- | --- |
| Face / actor | `source/imagegen/orianna_actor_contact.png` | reviewed 38px battle silhouette and y=42 exclusive baseline remain unchanged; the final palette budget rises from 48 to 96 colors so the porcelain plane, cyan eyes, brass crown/joints and both boots survive the final downsample |
| Run | `source/imagegen/orianna_run_contact.png` using the accepted actor identity | nine unique alternating-contact mechanical run phases; corrected 38px head/body scale, full separated boots and y=42 exclusive foot baseline |
| Basic attack | actor command pose plus built-in ImageGen v3 `source/imagegen/orianna_attack_vfx_contact.png` | high-contrast 25-28px cyan/ivory/brass mechanical energy dart with violet trail and separate 24px contact spark; clearly visible on dark battle terrain and never a miniature copy of the mechanical Ball |
| Q | `source/imagegen/orianna_q_vfx_contact.png` | traveling Ball and fixed landing field are visually distinct; the field reads as timed/non-persistent rather than a permanent second actor |
| E | `source/imagegen/orianna_e_vfx_contact.png` | fast ally-bound travel plus hollow clockwork shield ring; allied body remains visible and the effect can end with `WithShield` |
| R | `source/imagegen/orianna_r_vfx_contact.png` | clear inward contraction and target-point impact; motion reads toward the selected enemy point, not toward Orianna |
| Skill icons | independent `orianna_q/e/r_icon_source.png` files | exact UI order Q, E, R; each remains readable at 24x24 and has a different silhouette |
| BP grid | source-direct first idle to `ui/champion_portrait/barrier_magician_grid.png` | independent 90x122 full-body crop; alpha bbox ends at y=86, leaving 10 transparent pixels before name-band y=96 |
| Picked side card | `BanPickIllust/barrier_magician.png` | independent 1420x860 illustration; never reused as a battle or compact portrait |
| Side list / HUD | source-direct face/upper-torso crop to `barrier_magician_compact.png` | 64x64 master routed only to 39-52px square UI commands, with at least 6px transparent margins |
| Scoreboard / report | tighter source-direct face crop to `barrier_magician_scoreboard.png` | distinct from the side-list crop and routed to 14-38px square commands |
| Encyclopedia | source-direct complete body to `ui/champion_fullbody/barrier_magician.png` | complete head-to-boots 64x64 crop; it is no longer a nearest-neighbor enlargement of the packed 38px actor |

Native actor-contract gate:

- Preserve official `barrier_magician` action keys and timing shape: `idle` 4, `run` 8, `attack` 5, `skill1` 5, `skill2` 5, `ult` 4, `hit` 1 and `dead` 9 frames.
- Large Ball travel, shield rings, fields and shockwaves belong in separate effect/projectile sheets, not in clean idle/run/hit/dead body frames.
- Core body actions must keep the corrected model in one scale class, preserve its clear face, and keep every non-transparent foot pixel above the card crop.
- Every future rebuild must keep UI surfaces source-direct and independent. The shared gate in `tests/legacy_hd_assertions.py` rejects reused compact/scoreboard crops and any BP-grid alpha below y=86.

HD audit evidence:

- `qa/orianna_hd_surface_qa.json` records the accepted high-resolution source hash, per-action battle bboxes, face contrast, all five UI surface hashes and runtime routing bands.
- `qa/orianna_portrait_surface_final.png` reviews the battle idle, actual 46px side-list crop, actual 34px scoreboard crop, BP name clearance, encyclopedia body and picked side card together.
- Existing processed ImageGen information was sufficient; no new image generation or model replacement was needed.

Source provenance:

- All nine source PNG hashes are recorded in `orianna_imagegen_sources.json`; the attack entry additionally pins its processed-alpha hash and green-key route.
- The source/process art is original image generation. No official Barrier Mage sheet, League client art, Workshop Reimu art, Workshop animation rectangles, icons or audio may be copied into the runtime assets.
