# Orianna same-id official 003 visual QA

| Surface / action | Original source route | Acceptance gate |
| --- | --- | --- |
| Face / actor | `source/imagegen/orianna_actor_contact.png` | enlarged readable porcelain face plane, separated cyan eye pixels, connected brass crown, simplified clockwork joints and complete boots across all packed poses |
| Run | `source/imagegen/orianna_run_contact.png` using the accepted actor identity | nine unique alternating-contact mechanical run phases; corrected 38px head/body scale, full separated boots and y=42 exclusive foot baseline |
| Basic attack | actor command pose plus built-in ImageGen v3 `source/imagegen/orianna_attack_vfx_contact.png` | high-contrast 25-28px cyan/ivory/brass mechanical energy dart with violet trail and separate 24px contact spark; clearly visible on dark battle terrain and never a miniature copy of the mechanical Ball |
| Q | `source/imagegen/orianna_q_vfx_contact.png` | traveling Ball and fixed landing field are visually distinct; the field reads as timed/non-persistent rather than a permanent second actor |
| E | `source/imagegen/orianna_e_vfx_contact.png` | fast ally-bound travel plus hollow clockwork shield ring; allied body remains visible and the effect can end with `WithShield` |
| R | `source/imagegen/orianna_r_vfx_contact.png` | clear inward contraction and target-point impact; motion reads toward the selected enemy point, not toward Orianna |
| Skill icons | independent `orianna_q/e/r_icon_source.png` files | exact UI order Q, E, R; each remains readable at 24x24 and has a different silhouette |
| Compact portrait | `barrier_magician` style offsets `face {x:0,y:-34}` and `center {x:0,y:-12}` | provisional centered face/full-body framing in cards, compact rows, scoreboard, reports and battle HUD; tune only this champion after live evidence |

Native actor-contract gate:

- Preserve official `barrier_magician` action keys and timing shape: `idle` 4, `run` 8, `attack` 5, `skill1` 5, `skill2` 5, `ult` 4, `hit` 1 and `dead` 9 frames.
- Large Ball travel, shield rings, fields and shockwaves belong in separate effect/projectile sheets, not in clean idle/run/hit/dead body frames.
- Core body actions must keep the corrected model in one scale class, preserve its clear face, and keep every non-transparent foot pixel above the card crop.

Source provenance:

- All nine source PNG hashes are recorded in `orianna_imagegen_sources.json`; the attack entry additionally pins its processed-alpha hash and green-key route.
- The source/process art is original image generation. No official Barrier Mage sheet, League client art, Workshop Reimu art, Workshop animation rectangles, icons or audio may be copied into the runtime assets.
