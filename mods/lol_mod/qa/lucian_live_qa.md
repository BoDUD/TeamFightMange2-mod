# Lucian same-id 002 live QA

Automated/build gates:

- [x] `champion/archer.data_champion` has id `archer`; no duplicate `lol_lucian` registration exists.
- [x] The three active icons and descriptions are ordered Q, E, R with no W.
- [x] Lightslinger contains exactly two generated projectiles six ticks apart and consumes its marker.
- [x] Q uses one frozen damage line and eight actor-centered wide visual frames with no moving/target projectile; E is a damage-free directional dash with no release VFX; R emits exactly 15 non-piercing shots.
- [x] The unified v10 actor (including all run and combat poses), attack bolt, Q/R visual sources and Q/E/R icons are image-gen assets with recorded hashes.
- [x] Builder, static validator and tests pass; all 58 installed runtime files match `build_manifest.json`.
- [x] Installed v10 reaches the encyclopedia without a mod-load diagnostic; the live card shows two separate eyes and is preserved as `lucian_v10_live_card.png`.

Reviewer gates:

- [ ] Search the encyclopedia for “卢锡安”; the official 002 position appears once and has Q/E/R icons.
- [ ] The v10 same-row two-eye face, consistent body, separate arms/pistols, separated legs and complete boots read clearly in encyclopedia, draft, scoreboard and battle HUD.
- [ ] The nine-frame low forward dual-pistol sprint is visibly different from Shen's upright ninja gait.
- [ ] A normal basic attack shows one cyan generated light bolt.
- [ ] After Q or E, the next basic attack visibly produces a second bolt shortly after the first.
- [ ] Q flashes once as a non-tracking gold-white penetrating line from the forward pistol muzzle in both facing directions; E moves 300 range without spawning a trail or afterimage.
- [ ] R keeps Lucian stationary, can be interrupted, and emits 15 discrete shots.
- [ ] Official Lucian attack/passive/Q/E/R audio is audible and correctly timed.

Latest startup smoke: 2026-07-10 18:18 JST. The BOM-free installer kept only `lol_mod` enabled, v0.3.0 loaded without a mod diagnostic, and the encyclopedia rendered the v10 actor card with two visible eyes at 35px runtime height. Q v3 is structurally fixed (one `LineRangeProjectile`, eight embedded 192x64 beam frames, no moving/target visual projectile) but still requires the reviewer-facing battle check in both directions. The existing Workshop item 3736031680 warning and network default-banpick fallback are unrelated to this mod.
