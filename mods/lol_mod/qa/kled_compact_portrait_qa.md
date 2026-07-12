# Kled compact portrait QA

## Fixed contract

- Replacement id: `cavalry_knight` (official native index 17; project hero 006).
- Native Cavalry camera: `face = {x: 1, y: -44}`, `center = {x: 0, y: -12}`.
- Kled camera after this fix: `face = center = {x: 0, y: -12}`.
- Reason: the native `face` camera was authored for Cavalry's rider-head crop.  The accepted Kled actor is a single mounted Kled-and-Skaarl silhouette, so reusing `y=-44` pushes Kled and Skaarl above the compact clip and leaves only the bottom of Skaarl visible, matching the reported side-list and scoreboard screenshots.

## Packed-frame evidence

The current first `idle` frame keeps the native `45x61` canvas.  Its alpha bbox is `(3, 5, 42, 45)`, which is `39x40` visible pixels with a center at `(22.5, 25.0)`.  The full mounted silhouette is therefore already within the native frame and the normal mounted scale class; no actor rescale or repack is required for this defect.  The compact camera must use the full-body `center` placement.

Automated gates now require:

- exact Kled-only `face = center = {x: 0, y: -12}`;
- a non-empty first idle frame;
- visible mounted width and height within `36..44px`;
- alpha top at or above `y=6` and bottom at or above the accepted `y=46` baseline.

## Manual runtime checklist

The supplied screenshots prove the old `face = {x: 1, y: -44}` path failed.  The updated camera has not yet been proven in a newly launched game, so these remain manual checks rather than claimed passes:

- [ ] Battle HUD left/right side list shows readable Kled and Skaarl, not only Skaarl's lower body.
- [ ] In-match scoreboard row shows the same readable compact portrait.
- [ ] Weekly report/analysis row shows the mounted silhouette without top or bottom clipping.
- [ ] Standings, post-match news/MVP, and team-stat rows use the corrected crop.
- [ ] Ban/pick side cards remain readable, while the encyclopedia continues to use its dedicated `64x64` full-body asset.

No other champion's `face` coordinates are changed by this fix.
