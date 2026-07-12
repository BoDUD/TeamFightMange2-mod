# Kled compact portrait QA

## Fixed contract

- Replacement id: `cavalry_knight` (official native index 17; project hero 006).
- Native Cavalry camera: `face = {x: 1, y: -44}`, `center = {x: 0, y: -12}`.
- Kled camera after this fix: `face = {x: 1, y: -36}`, `center = {x: 0, y: -12}`.
- Reason: the native `face.y=-44` crops above the generated rider, while reusing the full-body `center.y=-12` compresses the entire mounted silhouette into compact rows. The Kled-only midpoint focuses the rider's head and upper body without changing the accepted battle/card scale.

## Packed-frame evidence

The current first `idle` frame keeps the native `45x61` canvas. Its alpha bbox is `(3, 5, 42, 45)`, which is `39x40` visible pixels with a center at `(22.5, 25.0)`. No actor rescale or repack is required; only the compact face camera changes.

Automated gates now require:

- exact Kled-only `face = {x: 1, y: -36}` with independent `center = {x: 0, y: -12}`;
- a non-empty first idle frame;
- visible mounted width and height within `36..44px`;
- alpha top at or above `y=6` and bottom at or above the accepted `y=46` baseline.

## Manual runtime checklist

The supplied screenshots prove both `face = {x: 1, y: -44}` and `face = center = {x: 0, y: -12}` fail in opposite directions. The rider-focused camera has not yet been proven in a newly launched game, so these remain manual checks rather than claimed passes:

- [ ] Battle HUD left/right side list shows Kled's readable head and upper body, not a miniature full mount.
- [ ] In-match scoreboard row shows the same rider-focused compact portrait.
- [ ] Weekly report/analysis row shows the mounted silhouette without top or bottom clipping.
- [ ] Standings, post-match news/MVP, and team-stat rows use the corrected crop.
- [ ] Ban/pick side cards remain readable, while the encyclopedia continues to use its dedicated `64x64` full-body asset.

No other champion's `face` coordinates are changed by this fix.
