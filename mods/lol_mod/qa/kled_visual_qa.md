# Kled visual QA

Status: generated-source, packed-atlas, icon, VFX, and card-art inspection passed; all in-game display and motion checks remain pending.

## Source route

- [x] Ten built-in image-gen sources are pinned in `qa/kled_imagegen_sources.json`: actor, run, defeat, Q/E VFX, W VFX, R VFX, Q icon, W icon, R icon, and BP illustration.
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

- [x] Q/E uses a distinct spear-hook, rope, trap-jaw, tether-ring, and pull silhouette in `kled_q_tether`.
- [x] The mapped W uses compact red-orange claw/slash phases, with a stronger independent fourth-hit impact read.
- [x] R uses gold dust, charge arrows/rings, trail phases, and a separate terminal impact family.
- [x] The Q, W-mapped second slot, and R icons are three independent original images with safe margins, no letters, and clearly different silhouettes.
- [x] Generated VFX contacts contain effects only; they do not bake a second Kled/Skaarl body into the animation.

## UI assets

- [x] The normalized BP source follows the 284:172 card composition and the runtime illustration is 1420x860.
- [x] A non-empty 64x64 full-body encyclopedia portrait is generated from the accepted mounted idle model.
- [x] Static contact review shows the mounted body and feet are present, but it does not prove any UI camera, crop, scale, or draw-order behavior in game.

## Pending target-visible checks

- [ ] BP illustration appears only in Kled's intended side-card slot, clears immediately after the pick state changes, and does not cover adjacent UI.
- [ ] Encyclopedia, draft card, scoreboard, side row, report, and battle HUD show a readable complete mounted body with no head/feet/weapon crop.
- [ ] Run, attack, Q/E, W, R, hit, and death remain in one stable scale class during a live match.
- [ ] The mounted run has no sliding, abrupt forward jump, frame shake, terrain intersection, or HP/name-label collision.
- [ ] Q tether/pull, W fourth hit, and R trail/impact remain centered on the intended actor/target in both facing directions.
