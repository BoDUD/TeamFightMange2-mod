# Lucian same-id 002 live QA

Automated/build gates:

- [x] `champion/archer.data_champion` has id `archer`; no duplicate `lol_lucian` registration exists.
- [x] The three active icons and descriptions are ordered Q, E, R with no W.
- [x] Lightslinger contains exactly two generated projectiles six ticks apart and consumes its marker.
- [x] Q is penetrating, E is a damage-free directional dash with no release VFX, and R emits exactly 15 non-piercing shots.
- [x] Actor, run, attack-bolt and Q/R visual sources plus Q/E/R icons are image-gen assets with recorded hashes.
- [x] Builder, static validator and tests pass; all 58 installed runtime files match `build_manifest.json`.

Reviewer gates:

- [ ] Search the encyclopedia for “卢锡安”; the official 002 position appears once and has Q/E/R icons.
- [ ] The enlarged warm-tone face reads clearly in encyclopedia, draft, scoreboard and battle HUD.
- [ ] The nine-frame low forward dual-pistol sprint is visibly different from Shen's upright ninja gait.
- [ ] A normal basic attack shows one cyan generated light bolt.
- [ ] After Q or E, the next basic attack visibly produces a second bolt shortly after the first.
- [ ] Q reads as a gold-white penetrating beam starting at the forward pistol muzzle in both facing directions; E moves 300 range without spawning a trail or afterimage.
- [ ] R keeps Lucian stationary, can be interrupted, and emits 15 discrete shots.
- [ ] Official Lucian attack/passive/Q/E/R audio is audible and correctly timed.

Latest startup smoke: 2026-07-10 14:49 JST. Installed v0.3.0 reached the title screen with no diagnostics popup; all 58 runtime hashes matched. The installed Q uses the direction-aware projectile binding with no caster-only visual, and E contains no release-VFX binding or asset. The existing Workshop item 3736031680 warning and network default-banpick fallback are unrelated to this mod.
