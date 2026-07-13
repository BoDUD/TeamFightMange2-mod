# Sivir live QA

Status: pending fresh installed-build startup and target-visible match capture.

The 2026-07-13 legacy-HD pass adds a new pending live gate for the current v0.8.2 build: confirm the 44px battle actor, 43-45px run cycle, independent BP-grid/side-list/scoreboard/encyclopedia crops, ten-pixel BP name-band clearance, and stable R command body scale. Static tests and generated contacts pass; this document does not claim a new live capture.

Required force-pick identity: `LOL_QA_FORCE_CHAMPION_ID=26` (`boomerang_hunter`). Project number 005 must not be used as the engine index.

Acceptance evidence must show the current installed v0.6.0 build and Sivir visibly present in the actual draft/battle/HUD. A generic successful match or telemetry-only row is not sufficient.

- [x] Fresh installed v0.6.0 startup at 2026-07-11 04:48 JST reached `asset loading done!` with no data-champion, sound, sprite, duplicate-ID, panic or fatal error while only `lol_mod` was enabled.
- [ ] Encyclopedia search shows “希维尔” with readable face, complete feet, and centered compact crossblade.
- [ ] Pick/ban, scoreboard, side row, report, and battle HUD show a readable compact avatar.
- [ ] Actor scale matches the accepted Shen/Briar class and stays stable across attack/Q/E/R/hit/dead.
- [ ] Run motion has clear alternating stride and no slide, terrain cut, or weapon jump.
- [x] Basic attack projectile leaves the hand, shows no detached actor pixels or second baked weapon in either facing direction, and plays only the distinct League launch/hit audio.
- [ ] Q leaves in the selected direction, returns once, can hit heroes/minions on both passes, excludes towers, and shows no duplicate held weapon.
- [x] E shows one complete head-to-feet shield ring, reduces skill damage during the window, heals once, and ends cleanly.
- [x] R affects nearby allied champions once, plays only its League command sound once, deals no damage, and keeps the gold speed trail strictly at the feet.

Startup evidence is stored outside the active mod at `sivir_evidence/postfix_startup.png`. The only startup diagnostics were the pre-existing Workshop item 3736031680 missing-metadata warning and default-banpick network `UnexpectedEof` fallback; neither references `lol_mod` or Sivir. Other target-visible surfaces and exhaustive Q-path gates remain intentionally unchecked.

The user reviewed the 2026-07-11 correction build and explicitly accepted the native-audio isolation, left/right attack cleanup, full-body E ring and foot-only R speed trail before PR publication. Unrelated unchecked gates remain future exhaustive-match coverage and are not claimed by that acceptance.
