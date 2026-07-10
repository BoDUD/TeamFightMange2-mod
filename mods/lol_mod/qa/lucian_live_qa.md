# Lucian native-002 live QA

Automated/build gates:

- [x] The replacement sheet preserves every required official champion entry and changes only native `archer`.
- [x] No `champion/lol_lucian.data_champion` registration file exists.
- [x] Native Archer text, actor animation, icon-atlas cells, stats and sound events are remapped to Lucian assets.
- [x] Builder, static validator and tests pass.
- [x] Installed runtime files match `build_manifest.json`.

Reviewer gates:

- [ ] Search the encyclopedia for “卢锡安”; native champion 002 appears under that name and no extra Archer/Lucian duplicate exists.
- [ ] Encyclopedia, draft card, scoreboard, side list, battle HUD and minimap show a centered, correctly scaled portrait/model.
- [ ] The eight-frame native run loop visibly alternates the legs and includes passing/cross-step poses.
- [ ] E dashes in the chosen direction and follows with the native 45% shot from the centered actor.
- [ ] Q fires from the centered actor, deals the documented damage and does not perform the old Archer backstep.
- [ ] R is interruptible and produces exactly 15 shots.
- [ ] Official Lucian attack/E/Q/R audio is audible and correctly timed.

The game must be fully closed before installing v0.2.2 so cached older assets cannot remain in memory.

Latest startup smoke: 2026-07-10 13:27 JST. The installed v0.2.1 build reached `asset loading done!` in under one second with no missing champion fields and no Lucian/`lol_mod` asset errors. All 59 installed runtime files matched the build manifest. The existing Workshop item 3736031680 warning and network default-banpick fallback are unrelated to this mod.

Override warning regression: v0.2.2 changes the complete `champion_info` remap from `merge` to `override`. The 2026-07-10 13:34 JST startup reached `asset loading done!` with no `Cannot read target ... champion_info` message and no unapplied mod override warning. Static validation now rejects `merge` for this complete native sheet.
