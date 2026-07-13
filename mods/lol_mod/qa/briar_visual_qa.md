# Briar same-id official 004 visual QA

Static contact-sheet inspection was performed against the exact source, processed-alpha, runtime and QA-composite hashes recorded in `briar_imagegen_sources.json`. This is static evidence only; compact UI framing and battle readability remain live gates.

| Surface / action | Original source route | Static result and live acceptance gate |
| --- | --- | --- |
| Face / actor | `source/imagegen/briar_actor_contact.png` | The same pale-haired, red-eyed Briar identity is retained across idle, normal attacks, Snack, Q break, E, R, hit and death. One uniform aspect-preserving scale now gives the primary idle and every run phase a 42px visible height, with a 96-color final palette; the accepted body/model is unchanged. |
| Full body / feet | processed actor source to `aseprite_resources/champions/briar#sheet.png` | Core body cells remain hard-alpha and end at the exclusive y=46 foot baseline. Standing/run frames retain complete feet; horizontal lunge/throw poses may be shorter but never use a smaller body scale or x-only compression. |
| Run | `source/imagegen/briar_run_contact.png` | The 3x3 source contains nine independent phases. Native same-ID compatibility remains eight frames per runtime tag: `run` samples source-atlas indexes 16-23 and `berserk_run` samples 17-24. Their offset union uses all nine phases while preserving the original eight-frame, 0.640000048-second tag contract. Live QA checks flow and stutter; it must not change either native tag to nine frames. |
| Normal / Snack attack | actor windup, strike, lunge and bite poses | Normal attack and empowered Snack have different silhouettes and official audio routes. Snack must appear once per Q empowerment, without leaving a duplicate body or restraint prop behind. |
| Q / Blood Frenzy | cleaned actor restraint-break poses plus `briar_q_overhead` target-following impact | Q keeps the native `skill1` three-frame/0.08-second-per-frame actor contract and 20-tick cast. The generated yellow/orange bracket pixels are removed from the first pose, while one eight-frame, 0.46-second scarlet impact follows the selected target at `z:2`. Its runtime sheet uses 64x64 cells but confines visible pixels to at most 30x22 in y=2..24, leaving the lower 40 pixels transparent so it reads above the target's head rather than as a body-sized square/ring. The 180-tick Blood Frenzy logic remains unchanged and has no persistent enclosing view-buff. |
| E / Chilling Scream | `source/imagegen/briar_e_vfx_contact.png` | Eight hard-alpha 112x64 forward phases clearly expand along one horizontal direction. The visual projectile must align with the directional 50,000x24,000 logic hitbox rather than appearing caster-centered or angled away. |
| Passive / Crimson Curse | `source/imagegen/briar_bleed_vfx_contact.png` | Eight 48x48 hard-alpha slash/blood phases form a short 0.52-second target-following tick. It must remain visible on dark terrain without becoming an actor-sized red cloud. |
| R / Certain Death | `source/imagegen/briar_r_vfx_contact.png` plus the retained `briar_frenzy` ThreePhase aura | Target mark, chase trail and arrival/fear ring use separate sheets and tags. The mark follows the selected target, the trail follows Briar, and the arrival ring is non-following at the resolved endpoint. The old 96x96 frenzy aura now belongs only to `lol_briar_certain_death_frenzy`, so Q cannot display it. |
| Skill icons | three independent Q/E/R ImageGen sources | Runtime order is `briar_skill`, `briar_skill2`, `briar_ult`; all are opaque 64x64 images with different silhouettes and remain readable in the 24x24 HUD. No fourth W slot is advertised. |
| BP grid | source-direct first idle to `ui/champion_portrait/berserker_grid.png` | independent 90x122 full-body crop with alpha bottom y=86; the lower 36px stay transparent and provide 10px clearance before name-band y=96 |
| Picked side card | `BanPickIllust/berserker.png` | independent 1420x860 illustration; it is not reused for the grid or battle actor |
| Side list / HUD | source-direct face/upper-restraint crop to `berserker_compact.png` | 64x64 master for 39-52px square commands; red eyes, hair silhouette and pillory remain visible |
| Scoreboard / report | tighter source-direct face/crystal crop to `berserker_scoreboard.png` | separate file/crop routed only to 14-38px square commands rather than sharing the side-list portrait |
| Encyclopedia | source-direct complete body to `ui/champion_fullbody/berserker.png` | complete 64x64 head-to-feet portrait instead of enlarging the packed 42px actor |

Runtime alpha and packing proof:

- Actor sheet: 1792x64, 28 cells of 64x64; global nonzero alpha bounds `(20,2)-(1720,46)`.
- All core actor cells are binary alpha. The only 1,154 partial-alpha pixels belong to the intentional 58% and 28% death-fade cells after the 42px rebuild; the terminal death cell is transparent.
- Icons are fully opaque. Every runtime VFX sheet is hard alpha with zero partial-alpha pixels.
- The Q overhead source's white 4x2 separators are removed by an 18-pixel per-cell inset before alpha bounding; all eight runtime cells have transparent corners and no white gutter pixels.
- The actor, icons and VFX use separate runtime sheets, so Q/E/R effects do not introduce a second actor body.
- `qa/briar_actor_contact_final.png`, `qa/briar_skill_icons_final.png` and `qa/briar_vfx_contact_final.png` were visually inspected at original resolution. Static composition is accepted for live testing, not yet for final in-game framing.
- `qa/briar_hd_surface_qa.json` records the accepted HD source hash, per-action battle bboxes, face contrast, all five UI surface hashes and routing bands. `qa/briar_portrait_surface_final.png` reviews the actual 46px side-list and 34px scoreboard crops beside the BP-grid name clearance.
- The shared regression gate in `tests/legacy_hd_assertions.py` fails future rebuilds if BP alpha extends past y=86, compact/scoreboard become the same crop, or UI art falls back to an enlarged battle frame.

Provenance rule:

- The ten original ImageGen PNGs, seven processed-alpha intermediates, runtime PNGs, animation files and contact-sheet hashes are frozen in `briar_imagegen_sources.json`.
- The accepted processed actor source already contained sufficient face/body information, so this HD pass reused it and did not invoke new image generation.
- No native Berserker sheet, League client art, Workshop art, animation rectangles or icons are used as Briar's visual source.
