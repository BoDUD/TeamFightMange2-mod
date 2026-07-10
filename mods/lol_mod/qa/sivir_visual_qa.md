# Sivir visual QA

## 2026-07-11 correction pass

- All 16 actor poses are cropped from full-image keep boxes rather than blind 4x4 cells, preventing adjacent-pose pixels from leaking across the 1254px contact sheet boundaries.
- Basic attack actor frames contain one connected actor component in both facing directions; the detached thrown crossblade exists only in the projectile VFX.
- E loop phases occupy at least 52x52 pixels inside the 64x64 frame so the shield surrounds the full 36px actor from head to feet.
- R ally-speed phases are constrained to the bottom 10 pixels of a 64x32 frame, mapping the gold trail to the feet rather than the torso.

Source route: accepted built-in image-gen actor and nine-frame run sources, plus independent Q/E/R icons and attack/Q/E/R effects. All actor actions are derived from the same locked model; no diagnostic or alternate body is packed.

Static acceptance:

- Native Boomerang Hunter retains all 12 tags, exact frame counts, and exact durations.
- Core body frames remain on a 64x64 canvas with an exclusive y=46 foot baseline and a 23-43px visible-height class.
- Eight native run frames use eight different generated gait phases.
- `boomerang`, `big_boomerang`, and `ult_boomerang` remain weapon-only frames.
- The ninth death frame remains transparent.
- Q outbound and return, E shield, R cast pulse, and R ally speed buff use independent named tags.
- Compact portrait starts at `face={x:5,y:-34}` and card/battle center stays `{x:0,y:-12}`.

Target-visible live checks remain required for encyclopedia/card, scoreboard/side row, battle HUD, terrain boundaries, run motion, Q direction/return, E body visibility, and R foot clearance.
