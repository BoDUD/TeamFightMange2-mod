# Kled compact portrait QA

## Root cause

- The accepted ImageGen source is not blurry: Kled's face is clear in `source/processed/kled_actor_contact_alpha.png`.
- Native 006 packs the first mounted idle pose into a `45x61` frame with a roughly `39x40` visible body.
- Runtime telemetry proves compact UI surfaces reuse that full mounted frame at `18x18`, `26x26`, `34x34`, and `46x46`. At those sizes Kled's rider face becomes only a few pixels because Skaarl and the weapon still occupy the icon.
- `champion_view.face` only changes the camera offset. It cannot increase the number of source pixels, and the earlier `{x:1,y:-36}` offset therefore could not solve facial clarity by itself.
- The encyclopedia had a second loss: its 64px portrait was enlarged from the already reduced 40px battle frame instead of being sampled directly from the accepted high-resolution source.

## Fixed contract

- Replacement id: `cavalry_knight` (official native index 17; project hero 006).
- Battle atlas and all 24 native animation tags/rectangles/durations remain unchanged.
- `ui/champion_portrait/cavalry_knight_compact.png` is a source-direct 64x64 Kled rider head/shoulders/upper-body portrait for square `14..52px` HUD, scoreboard, report, and footer commands. Its subject bbox is capped at `50x50` with at least 6px transparent clearance on all four sides, preventing the live row from reading as a hard crop.
- `ui/champion_portrait/cavalry_knight_grid.png` is a source-direct 90x122 full mounted portrait for the BP hero grid geometry proven by telemetry (`86..90 x 114..126` during its small scale transition). Its alpha bottom is capped at `y=86`, leaving a visible 10px gap before the lower name band begins at `y=96`.
- `ui/champion_fullbody/cavalry_knight.png` remains a complete mounted 64x64 encyclopedia portrait, now downsampled once from the high-resolution source instead of enlarged from the battle atlas.
- Picked left/right BP cards continue to use `BanPickIllust/cavalry_knight.png`; the portrait route runs after the side-card splash replacement and does not alter it.
- `style/champion_view` keeps the Kled-only fallback `face={x:1,y:-36}` and `center={x:0,y:-12}`. No other champion camera changes.

## Automated gates

- The three portrait files must exist at exact sizes `64x64`, `90x122`, and `64x64` and have hard alpha with non-empty coverage. Compact bbox width/height must be at most 50px and every canvas margin at least 6px; grid alpha must end at or above `y=86`, preserving the 10px name-band safety gap.
- Compact and full-body assets must have different hashes: compact surfaces are rider-focused; grid and encyclopedia retain the full mount.
- The native Kled actor sheet hash/animation geometry checks still run, preventing this UI fix from changing skills or battle motion.
- The DLL source must contain the Kled-only base/mod actor texture aliases, compact/grid texture paths, square-geometry gate, BP-grid gate, normalized UV rewrite, and nearest sampling.
- `qa/kled_portrait_surface_final.png` shows 18/26/34/46px compact samples, the exact 90x122 BP grid asset, and the 64px encyclopedia asset.

## Manual runtime checklist

- [ ] BP hero grid shows the complete Kled/Skaarl model with a readable rider face.
- [ ] Picked left/right lineup cards still show Kled's illustration and do not flash the compact portrait.
- [ ] Battle HUD, scoreboard, reports, standings, MVP/news rows, and 18px BP footer show the rider-focused portrait.
- [ ] Encyclopedia shows the complete mounted silhouette from head to Skaarl's feet with a cleaner face.
- [ ] Battle actor, Q/E/R, run, hit, and death are unchanged by the UI-only render route.
