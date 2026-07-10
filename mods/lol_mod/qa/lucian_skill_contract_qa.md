# Lucian skill contract QA

- Passive marker: `lol_lucian_lightslinger_ready`, 240 ticks after Q/E and after R completes.
- Empowered attack: first projectile at tick 4 for 100% Attack, second at tick 10 for 45% Attack, then consumes the marker.
- Q: enemy-champion targeting, 65000 cast range, 76000 penetrating line, `55 + 85% Attack`, `EnemyWithoutTower` application.
- E: direction cast, `RushTime` at 3000 units/tick for 10 ticks (30000 total), no damage effect, fixed-follow afterimage layer.
- R: direction channel, stationary and cancelable, 15 delayed projectiles at ticks 12 through 124 in eight-tick increments. Every shot is non-piercing, 9000 speed, 120000 range, 4500 radius, and `8 + 18% Attack`.

The builder generates the repeated R entries deterministically so bullet count and cadence cannot drift in hand-edited JSON.
