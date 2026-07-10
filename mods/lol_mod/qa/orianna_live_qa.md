# Orianna same-id official 003 live QA

Static/build release gates:

- [ ] `champion/barrier_magician.data_champion` has id `barrier_magician`; no duplicate `lol_orianna` registration exists.
- [ ] English, Simplified Chinese, Traditional Chinese, Japanese and Korean all expose the short localized name plus attack/Q/E/R descriptions.
- [ ] The three active icons are ordered Q, E, R and no unsupported fourth W slot is advertised.
- [ ] Actor tags, frame counts and durations preserve the official Barrier Mage animation contract.
- [ ] The nine original image-gen sources match `orianna_imagegen_sources.json`; runtime sheets do not contain Workshop or extracted official art.
- [ ] JSON, builder, static validator and tests pass, then the installed runtime hashes match `build_manifest.json`.
- [ ] Startup reaches `asset loading done!` with no data champion, duplicate-id, asset, localization or sound error while only `lol_mod` is enabled.

Reviewer/live gates:

- [ ] In Simplified Chinese search the encyclopedia for the actual short display name “奥利安娜”; in the other maintained locales search “Orianna”, “オリアナ” and “오리아나”. Official 003 must appear exactly once.
- [ ] Existing Classic saves may keep native Barrier Mage unavailable. For visibility QA, use Options → Gameplay → Custom champion pool and enable `barrier_magician` (or unlock all); this must reveal the same official 003 entry, never an extra `lol_orianna` entry.
- [ ] Card, draft, weekly report, scoreboard, side list and battle HUD show a readable full-body/compact portrait at provisional `face(0,-34)` / `center(0,-12)` offsets.
- [ ] A current battle screenshot visibly contains Orianna; another champion or draft telemetry alone is not accepted.
- [ ] Idle, run, attack, Q, E, R, hit and death preserve actor scale and avoid terrain/UI clipping.
- [ ] Basic attacks visibly launch the ImageGen v3 cyan/ivory/brass mechanical dart and its separate contact spark on dark terrain, while dealing the physical hit plus small AP clockwork bonus without spawning a second actor-sized Ball.
- [ ] Every basic attack audibly contains the official three-stage identity: mechanical `OnCast`, missile launch, then target-side `OnHit`; the first two layers must remain clear in a normal teamfight mix.
- [ ] Q reaches an enemy champion after 15 ticks, hits the 26,000 area and leaves a fixed 30,000-radius field for 180 ticks; the Ball does not persist after the field lifecycle.
- [ ] Q field gives allies +18% and enemies -22% move speed; at skill level 3 it additionally applies ally +15% and enemy -15% attack speed.
- [ ] E can target Orianna or an allied champion, travels at 6000, grants the 180-tick shield, and removes its +12 dual-resist / damage-reduction state when the shield ends or breaks.
- [ ] R captures the selected enemy's initial position, keeps its shrinking ring fixed there, applies the short edge Bind, and after 60 ticks damages, pulls and knocks up enemies at that same fixed point even if the original target moves.
- [ ] R target-point proof uses two separated test positions: Orianna must remain away from the target, and affected enemies must move toward the target point rather than toward Orianna.
- [ ] No test or UI text claims a persistent Ball, ally-attached Ball after E, or a fourth W cooldown.

No complete live pass is recorded yet. Populate this file only with timestamped startup logs, target-visible screenshots and target-point telemetry from the v0.4.1 attack-feedback build.
