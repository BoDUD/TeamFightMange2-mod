# Briar same-id official 004 live QA

All boxes intentionally remain unchecked until timestamped logs, screenshots or combat telemetry are attached. Static asset inspection is not a substitute for an in-game pass.

Preflight and startup:

- [ ] Write the forced champion test index as exactly `12` before launch and capture the written value in the test evidence. Do not substitute roster label 004 for this forced-index value.
- [ ] Build, static validation and tests pass, then the installed `mods/lol_mod` hashes match the final `build_manifest.json` after every rebuild.
- [ ] Start with only `lol_mod` enabled and retain the complete startup log through `asset loading done!`; it contains no duplicate ID, data champion, JSON, asset, animation, localization or sound error.
- [ ] The startup evidence records mod version 0.5.0, same-ID file `champion/berserker.data_champion`, and the forced index value 12 used for this run.

Encyclopedia, disabled state and selection:

- [ ] Search the encyclopedia for `贝蕾亚` in Simplified Chinese and the maintained localized Briar names in the other locales. Official 004 appears exactly once and there is no separate `lol_briar` entry.
- [ ] In the custom champion pool, disabling `berserker` hides/prevents selection of Briar; re-enabling that same ID restores one entry without creating a duplicate.
- [ ] Disable `lol_mod`, restart and confirm native official 004 Berserker returns; re-enable `lol_mod`, restart and confirm the same roster/save identity becomes Briar.
- [ ] The champion-selection/draft screen shows Briar's Q/E/R icons in that order, the short localized name, one full-body actor and no unsupported fourth W slot.
- [ ] A current battle screenshot visibly contains Briar. Encyclopedia, draft telemetry or another champion alone is not accepted as battle proof.

Cards, HUD, face, feet and motion:

- [x] The corrected `face(5,-32)` crop was accepted after live review: both red eyes and the lower face are centered in the compact lineup/avatar surface, while the full selection card keeps the same model. Remaining encyclopedia/disabled/report surfaces are still covered by their separate unchecked gates below.
- [ ] Full-body/card/battle views at `center(0,-12)` show both feet completely above the crop; hair, restraint, hands and feet do not touch or disappear behind the card/HUD edge.
- [ ] The pale face plane, separated red eyes and dark restraint remain readable at actual compact scale rather than only in the enlarged contact sheet.
- [ ] Nine-phase source to native-eight-frame adaptation is smooth: normal `run` shows source phases 1-8, `berserk_run` shows phases 2-9, both keep eight frames and 0.640000048 seconds, and their union visibly exercises all nine unique source phases without repeated-frame stutter, sliding or size jumps.
- [ ] Idle, normal attack, Snack, Q, E, R, hit, fall, grounded, defeated and death-fade actions keep one body, one scale and the y=46 exclusive foot baseline; the transparent terminal death frame leaves no duplicate corpse.

Passive and basic attacks:

- [ ] A normal attack deals the base physical hit once, plays normal cast/hit audio once, applies the target-following bleed visual and does not use the frenzy attack pose/audio.
- [ ] Crimson Curse produces the expected two period-60 damage ticks during its 120-tick lifetime and each tick heals Briar, never the victim or an unrelated unit.
- [ ] Repeat applications on one target are measured and documented as refresh or stack behavior; the observed engine behavior matches the final tooltip and never creates runaway permanent ticks/healing.
- [ ] Passive damage/healing is verified independently on an enemy champion and a minion, including the case where the original attacked target dies before the second tick.

Q / Blood Frenzy and one Snack:

- [ ] Q is unavailable without an enemy champion inside 45,000 and becomes available with one in range; casting it does not force target lock or spawn a follow-up tracking skill.
- [ ] Q shows one short scarlet impact/stun marker above the selected target's head. No yellow/orange square remains on Briar's `skill1` pose, no 96x96 ring encloses Briar, no white contact-sheet gutter appears, and the marker follows a moving target for its eight-frame 0.46-second burst without covering the model or health bar.
- [ ] Every successful Q prepares exactly one Snack: the next basic attack uses the bite pose, extra maximum-health damage, self-heal and frenzy audio, consumes `lol_briar_snack_ready`, and the following attack is normal.
- [ ] Casting Q again replaces/refreshes the one pending Snack rather than queuing two empowered bites.
- [ ] Casting Q during `lol_briar_certain_death_frenzy` refreshes one Snack without removing or downgrading the R-enhanced frenzy.

E / Chilling Scream direction:

- [ ] E aims in the selected direction, holds the fixed 30-tick charge, then the visible scream and 50,000x24,000 hitbox travel on the same line; neither effect fires sideways, backward or caster-centered.
- [ ] Champion and minion targets inside the line each take one `75 + 100% Attack` hit, Crimson Curse, Knockback and Airborne; targets outside the width take none, and the visual-only projectile never adds a second damage event.
- [ ] Briar receives the upfront `50 + 15% Attack` heal and 30-tick 35% damage-reduction guard. Both timings are recorded separately from target impact.
- [ ] E at close, middle and maximum range keeps its visual aligned with the hitbox and does not clip into Briar's body or disappear on dark terrain.

R / Certain Death and target death:

- [ ] R marks the selected enemy champion for 18 ticks, then Briar follows with the visible trail at speed 6000 and produces one arrival impact at the resolved endpoint.
- [ ] On a living target, arrival deals one `100 + 120% Attack` hit, applies Crimson Curse, fears nearby enemy champions for 30 ticks and grants the 240-tick enhanced frenzy plus exactly one Snack.
- [ ] Kill or remove the selected target during the 18-tick warning. Briar does not hang, chase an invalid object, teleport to an unrelated unit, throw an exception or apply ghost arrival damage; the actual safe cancel/end behavior is recorded.
- [ ] Kill or remove the selected target after chase begins but before arrival. Movement and end effects terminate safely, and the startup/runtime log contains no null-target or `MoveToTarget` error.
- [ ] R with no valid enemy champion in 80,000 cannot cast. This first version never claims or visually imitates a missable global straight-line projectile.

Audio and final evidence:

- [ ] Normal cast/hit, frenzy cast/hit, Q cast, E cast/hit and R cast/hit are all audible and semantically distinct in a normal teamfight mix; no clip loops or continues after its action.
- [ ] Bleed ticks do not dispatch a guessed repeating sound, and the excluded stereo three-second Snack source is not accidentally mapped.
- [ ] Final evidence includes the forced-index-12 write, complete startup log, encyclopedia search, disabled/enabled pool state, selection screen, compact HUD/face/feet screenshots, nine-phase run capture, passive/Q/E/R combat captures and both R target-death cases.

2026-07-11 avatar correction evidence is stored outside the active mod at `briar_evidence/after_fix_avatar.png` and `briar_evidence/after_fix_card.png`. The previous 96x96 Q-ring screenshot is superseded by the 2026-07-12 overhead-marker rebuild and is not acceptance evidence for the current asset. No complete all-surface/all-mechanic live pass is claimed; every unrelated box remains unchecked.
