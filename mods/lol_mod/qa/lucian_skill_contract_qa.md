# Lucian same-id 002 skill contract

Lucian reworks the existing `archer` ID through the official same-ID `.data_champion` path. The public 002 ordering and references stay stable, while combat no longer calls the Archer hard-coded action contract.

- Passive — Lightslinger: Q, E, and completed R add `lol_lucian_lightslinger_ready` for 240 ticks. The next attack fires at ticks 4 and 10 for `100% Attack` and `45% Attack`, then removes the marker.
- Basic attack: one dedicated image-gen `lol_lucian_light_bolt` target projectile for `100% Attack` at 620 range.
- Q — Piercing Light: champion-targeted cast, 650 cast range, 760 penetrating line, `55 + 85% Attack`, excluding towers.
- E — Relentless Pursuit: direction cast with `RushTime` at 3000 units/tick for 10 ticks, 300 total range and no damage. It intentionally spawns no release VFX, trail or afterimage.
- R — The Culling: stationary and cancelable, 15 non-piercing direction projectiles at ticks 12 through 124, each `8 + 18% Attack`, 1200 range and 45 hit radius.

The three active UI slots are Q, E, and R. There is no W slot or Archer backstep/interrupt behavior.
