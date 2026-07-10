# Briar same-id official 004 visual QA

Static contact-sheet inspection was performed against the exact source, processed-alpha, runtime and QA-composite hashes recorded in `briar_imagegen_sources.json`. This is static evidence only; compact UI framing and battle readability remain live gates.

| Surface / action | Original source route | Static result and live acceptance gate |
| --- | --- | --- |
| Face / actor | `source/imagegen/briar_actor_contact.png` | The same pale-haired, red-eyed Briar identity is retained across idle, normal attacks, Snack, Q break, E, R, hit and death. The face remains distinct in the 2x contact sheet; the provisional compact camera still requires live proof. |
| Full body / feet | processed actor source to `aseprite_resources/champions/briar#sheet.png` | Core body cells are hard-alpha and fit above the exclusive y=46 foot baseline. Both feet remain present in standing and running poses; cards, selection and HUD must not crop them. |
| Run | `source/imagegen/briar_run_contact.png` | The 3x3 source contains nine independent phases. Native same-ID compatibility remains eight frames per runtime tag: `run` samples source-atlas indexes 16-23 and `berserk_run` samples 17-24. Their offset union uses all nine phases while preserving the original eight-frame, 0.640000048-second tag contract. Live QA checks flow and stutter; it must not change either native tag to nine frames. |
| Normal / Snack attack | actor windup, strike, lunge and bite poses | Normal attack and empowered Snack have different silhouettes and official audio routes. Snack must appear once per Q empowerment, without leaving a duplicate body or restraint prop behind. |
| Q / Blood Frenzy | actor restraint-break poses plus `briar_frenzy` ThreePhase VFX | Four-frame pre, two-frame loop and two-frame removal are separate, hard-alpha phases. The live-review correction enlarges the canvas to 96x96, caps the ring at 88x84 and moves its hollow center six pixels downward so the added size grows around Briar's chest/feet instead of into her hair and health bar. |
| E / Chilling Scream | `source/imagegen/briar_e_vfx_contact.png` | Eight hard-alpha 112x64 forward phases clearly expand along one horizontal direction. The visual projectile must align with the directional 50,000x24,000 logic hitbox rather than appearing caster-centered or angled away. |
| Passive / Crimson Curse | `source/imagegen/briar_bleed_vfx_contact.png` | Eight 48x48 hard-alpha slash/blood phases form a short 0.52-second target-following tick. It must remain visible on dark terrain without becoming an actor-sized red cloud. |
| R / Certain Death | `source/imagegen/briar_r_vfx_contact.png` | Target mark, chase trail and arrival/fear ring use separate sheets and tags. The mark follows the selected target, the trail follows Briar, and the arrival ring is non-following at the resolved endpoint. |
| Skill icons | three independent Q/E/R ImageGen sources | Runtime order is `briar_skill`, `briar_skill2`, `briar_ult`; all are opaque 64x64 images with different silhouettes and remain readable in the 24x24 HUD. No fourth W slot is advertised. |
| Compact portrait | `berserker` style offsets `face {x:5,y:-32}` and `center {x:0,y:-12}` | The live scoreboard crop showed the first face camera five pixels right and four pixels low. The corrected face target moves five pixels toward Briar's actual face and four pixels downward in camera space, centering the red eyes and lower face while leaving the full-body camera unchanged. |

Runtime alpha and packing proof:

- Actor sheet: 1792x64, 28 cells of 64x64; global nonzero alpha bounds `(21,2)-(1718,46)`.
- All core actor cells are binary alpha. The only 928 partial-alpha pixels belong to the intentional 58% and 28% death-fade cells; the terminal death cell is transparent.
- Icons are fully opaque. Every runtime VFX sheet is hard alpha with zero partial-alpha pixels.
- The actor, icons and VFX use separate runtime sheets, so Q/E/R effects do not introduce a second actor body.
- `qa/briar_actor_contact_final.png`, `qa/briar_skill_icons_final.png` and `qa/briar_vfx_contact_final.png` were visually inspected at original resolution. Static composition is accepted for live testing, not yet for final in-game framing.

Provenance rule:

- The nine original ImageGen PNGs, six processed-alpha intermediates, runtime PNGs, animation files and contact-sheet hashes are frozen in `briar_imagegen_sources.json`.
- No native Berserker sheet, League client art, Workshop art, animation rectangles or icons are used as Briar's visual source.
