# Kled visual QA

Status: generated-source, packed-atlas, icon, VFX, and card-art inspection passed; all in-game display and motion checks remain pending.

## Source route

- [x] Built-in image-gen sources are pinned in `qa/kled_imagegen_sources.json` for the mounted actor, run, defeat, independent Q/E/R VFX, three active icons, and BP illustration.
- [x] Actor, run, defeat, and VFX contacts use removable flat green-key backgrounds; their accepted processed copies have hard alpha.
- [x] Actor actions use one locked mounted Kled/Skaarl model. No alternate unmounted body or diagnostic geometry is packed.
- [x] Large skill effects are kept in independent effect sheets instead of inflating idle, run, hit, or dead body frames.

## Native actor contract

- [x] `aseprite_resources/champions/kled#sheet.png` is exactly 4096x189 and preserves the 24 native Cavalry Knight tag order, rectangles, frame counts, and durations.
- [x] The final actor contact shows full head, mounted body, Skaarl legs/feet, and weapon silhouette with stable body scale across idle, run, attack, `skill1`, `skill2`, ult, hit, and dead.
- [x] Run uses multiple distinct mounted gait poses rather than one repeated frame.
- [x] Attack and both skill bodies contain visible pose/weapon changes while retaining the locked model.
- [x] `ult_self_effect_back` remains fully transparent, and the terminal 3x3 frame of both `dead` and `fire_dead` remains transparent as required by the native contract.

## Ability readability

- [x] Q uses a travelling trap plus distinct latch, rope, and pull phases in `kled_q_tether`; no dash effect is embedded in Q.
- [x] E uses independent mounted dash and impact phases in `kled_e_joust`; it does not reuse Q's rope or R's trail.
- [x] R uses gold dust, charge arrows/rings, trail phases, and a separate terminal impact family.
- [x] The Q, E, and R icons are three independent original images with safe margins, no letters, and clearly different silhouettes.
- [x] Generated VFX contacts contain effects only; they do not bake a second Kled/Skaarl body into the animation.

## UI assets

- [x] The normalized BP source follows the 284:172 card composition and the runtime illustration is 1420x860.
- [x] The 64x64 full-body encyclopedia portrait is sampled directly from the accepted high-resolution mounted source rather than enlarged from the 40px battle atlas.
- [x] A dedicated source-direct rider portrait serves 18/26/34/46px compact commands, while a separate 90x122 full-mount texture serves the telemetry-proven BP hero grid.
- [x] `qa/kled_portrait_surface_final.png` proves the compact, BP-grid, and encyclopedia assets are distinct and non-empty; it does not claim a live UI pass.

## Pending target-visible checks

- [ ] BP illustration appears only in Kled's intended side-card slot, clears immediately after the pick state changes, and does not cover adjacent UI.
- [ ] Encyclopedia and BP grid show the readable complete mount; compact scoreboard, side-row, report, and battle-HUD surfaces show the rider-focused face portrait.
- [ ] Run, attack, Q, E, R, hit, and death remain in one stable scale class during a live match.
- [ ] The mounted run has no sliding, abrupt forward jump, frame shake, terrain intersection, or HP/name-label collision.
- [ ] Q projectile/latch/tether/pull, E dash/impact, and R trail/impact remain centered on the intended actor/target in both facing directions.
