# Sivir visual QA

## 2026-07-13 legacy-HD correction pass

- Reused the accepted 1254x1254 ImageGen actor and run sources; no replacement model was generated.
- Battle idle now occupies 44 visible pixels, run frames occupy 43-45 pixels, and every accepted action uses one aspect-preserving x/y scale with a 96-color final palette.
- R's oversized overhead crossblade is removed from the actor body before packing. The dedicated R cast sheet carries the ability flourish, so the command pose no longer shrinks against the other actions.
- Encyclopedia, BP grid, picked side card, side list, and scoreboard now use independent assets. UI crops come directly from the high-resolution idle source and never upscale the battle atlas.
- The 90x122 BP-grid portrait ends at exclusive y=86, leaving ten transparent pixels before the native y=96 hero-name band.
- Q/E/R data, timing, damage, targeting, audio and VFX bindings are unchanged by this HD-only pass.

Automated evidence: `qa/sivir_hd_surface_qa.json`, `qa/sivir_portrait_surface_final.png`, and the reusable gates in `tests/legacy_hd_assertions.py`.

## 2026-07-11 correction pass

- All 16 actor poses are cropped from full-image keep boxes rather than blind 4x4 cells, preventing adjacent-pose pixels from leaking across the 1254px contact sheet boundaries.
- Basic attack actor frames contain one connected actor component in both facing directions; the detached thrown crossblade exists only in the projectile VFX.
- E loop phases occupy at least 52x52 pixels inside the 64x64 frame so the shield surrounds the full actor from head to feet.
- R ally-speed phases are constrained to the bottom 10 pixels of a 64x32 frame, mapping the gold trail to the feet rather than the torso.

Source route: accepted built-in image-gen actor and nine-frame run sources, plus independent Q/E/R icons and attack/Q/E/R effects. All actor actions are derived from the same locked model; no diagnostic or alternate body is packed.

Static acceptance:

- Native Boomerang Hunter retains all 12 tags, exact frame counts, and exact durations.
- Core body frames remain on a 64x64 canvas with an exclusive y=46 foot baseline. HD idle is 44px, run is 43-45px, and naturally crouched actions remain in the 33-44px band without per-pose stretching.
- Eight native run frames use eight different generated gait phases.
- `boomerang`, `big_boomerang`, and `ult_boomerang` remain weapon-only frames.
- The ninth death frame remains transparent.
- Q outbound and return, E shield, R cast pulse, and R ally speed buff use independent named tags.
- The legacy `face={x:5,y:-34}` entry remains as a fallback, while runtime UI surfaces use their dedicated source-direct crops. Card/battle center stays `{x:0,y:-12}`.

Target-visible live checks remain required for encyclopedia/card, scoreboard/side row, battle HUD, terrain boundaries, run motion, Q direction/return, E body visibility, and R foot clearance.
