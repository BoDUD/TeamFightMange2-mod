# Lucian same-id 002 skill contract

Lucian reworks the existing `archer` ID through the official same-ID `.data_champion` path. The public 002 ordering and references stay stable, while combat no longer calls the Archer hard-coded action contract.

- Passive - Lightslinger: Q, E, and completed R add `lol_lucian_lightslinger_ready` for 240 ticks. The next attack fires at ticks 4 and 10 for `100% Attack` and `45% Attack`, then removes the marker.
- Basic attack: one dedicated image-gen `lol_lucian_light_bolt` target projectile for `100% Attack` at 620 range.
- Q - Piercing Light: `Targeting` accepts an `EnemyWithoutTower`, so either a champion or minion can anchor the cast. At start tick 10 it launches one `penetrate=true` `LinearProjectile` at speed 16000 for 760 range with a 100-radius hit lane, dealing `55 + 85% Attack` to every non-tower enemy hit. Damage and the 192x32 gold-white image-gen beam share `lol_lucian_q_piercing_light`; the beam is packed wholly ahead of its x=96 rotation pivot so the first pixels begin at the pistol muzzle. There is no delayed one-tick line, target-following Q visual, actor-embedded beam, or residual-spark mini projectile.
- E - Relentless Pursuit: direction cast with `RushTime` at 3000 units/tick for 10 ticks, 300 total range and no damage. It intentionally spawns no release VFX, trail or afterimage.
- R - The Culling: stationary and cancelable, 15 non-piercing direction projectiles at ticks 12 through 124, each `8 + 18% Attack`, 1200 range and 45 hit radius.

The three active UI slots are Q, E, and R. There is no W slot or Archer backstep/interrupt behavior.
