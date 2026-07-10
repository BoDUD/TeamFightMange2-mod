# Lucian live QA

Automated/build gates:

- [x] Builder and static validator pass.
- [x] Game log reaches `asset loading done!` with no `lol_lucian`, data-champion, asset, or sound errors.
- [x] Installed runtime files match every hash in `build_manifest.json`.

Visual/gameplay review gates for the PR reviewer:

- [ ] Lucian appears in encyclopedia and draft with the correct localized name and Q/E/R icons.
- [ ] Encyclopedia, draft card, scoreboard, side list, battle HUD and minimap show a centered, correctly scaled portrait/model.
- [ ] The nine-frame run loop visibly alternates legs and shows passing/cross-step poses.
- [ ] Basic attack and Lightslinger use the right/left/double-shot poses; the second passive projectile lands six ticks after the first.
- [ ] Q penetrates non-tower enemies on the target line and activates Lightslinger.
- [ ] E moves exactly one 30000-unit dash, deals no damage, keeps the active actor centered, and layers the afterimage behind/following him.
- [ ] R keeps Lucian stationary, can be interrupted, and produces 15 discrete non-piercing shots before activating Lightslinger.
- [ ] Official attack/passive/Q/E/R audio is audible and correctly timed in battle.

Latest automated startup smoke: 2026-07-10 11:38 JST. The game reached `asset loading done!` in roughly one second with zero Lucian/`lol_mod` errors and zero panic/fatal lines. The existing `network asset load error: UnexpectedEof` default-banpick fallback and Workshop item 3736031680 warning are unrelated to this mod.
