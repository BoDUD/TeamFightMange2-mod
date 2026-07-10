# Lucian same-id 002 live QA

Automated/build gates:

- [x] `champion/archer.data_champion` has id `archer`; no duplicate `lol_lucian` registration exists.
- [x] The three active icons and descriptions are ordered Q, E, R with no W.
- [x] Lightslinger contains exactly two generated projectiles six ticks apart and consumes its marker.
- [x] Q is unit-targeted, contains no delayed/one-tick line, and binds damage plus a forward-pivoted gold visual to one penetrating `LinearProjectile`; every frame stays a 60-80px beam and cannot end as a tracking spark. E is a damage-free directional dash with no release VFX; R emits exactly 15 non-piercing shots.
- [x] Actor skill frames are body-only 64x64 frames; the rejected 192px actor-embedded Q beam cannot return.
- [x] The v3 actor, v2 run master, attack/Q/R visual sources, and Q/E/R icons are image-gen assets with recorded hashes.
- [x] Hit and defeated frames use compact one-pistol silhouettes; rejected duplicated/floating-pistol poses are absent.
- [x] The v2 run gate matches Shen's 36px/y=44 scale class and rejects missing-lower-body, residual-anchor, horizontal-flight and abrupt-stride frames.
- [ ] Builder, static validator and tests pass; installed runtime files match `build_manifest.json`.
- [ ] A fresh startup after installing v2 reaches `asset loading done!` without a mod diagnostic.

Reviewer/live gates:

- [ ] Search the encyclopedia for Lucian / 卢锡安; the official 002 position appears once and has Q/E/R icons.
- [ ] The v2 face, body, separate arms/pistols, separated legs and complete boots read clearly in encyclopedia, draft, scoreboard and battle HUD at a size comparable to Shen.
- [ ] The nine-frame upright run has clear alternating contacts without sliding, horizontal flying, size jumps or terrain clipping.
- [ ] A normal basic attack shows one cyan generated light bolt; after Q or E, the next basic attack visibly produces a second bolt shortly after the first.
- [ ] Q is tested left, right, diagonally up and diagonally down with a champion target and a minion target; the selected target loses HP exactly once, aligned units behind it are pierced, off-line units and towers are not hit, the gold beam begins at the pistol muzzle, and no residual spark looks like a second tracking skill.
- [ ] E moves 300 range without spawning a trail or afterimage.
- [ ] R keeps Lucian stationary, can be interrupted, and emits 15 discrete shots.
- [ ] Official Lucian attack/passive/Q/E/R audio is audible and correctly timed.

The old v10 card plus rejected v10/v1/v2 actor sources were deleted because they are not evidence for this rebuild. Record the next startup timestamp and target-visible v3 card/battle capture here only after the installed runtime is verified.
