# Kled Q/E/R skill contract QA

Status: the independent Q/E/R data contract is statically defined; fresh installed-build and target-visible game verification remain pending.

## Identity and slot mapping

- [x] Project order is 006 and the same-ID replacement is `cavalry_knight`.
- [x] The occupied engine slot is the zero-based native index `17`; project order 006 is not a force-pick index.
- [x] The three public active slots are exactly `skill=Q`, `skill2=E`, and `ult=R`.
- [x] Q and E have separate cooldowns, effects, audio, VFX resources, and hit payloads; neither is folded into the other.
- [x] No unsupported fourth active slot, automatic four-hit state machine, or user-visible skill mapping is declared.
- [x] Kled remains mounted on Skaarl; Courage, dismount, remount, and Pocket Pistol are outside this data-only version.

## Basic attack

- [x] A normal attack deals one `100% AD` physical hit with Kled-specific cast and hit audio.
- [x] The attack is a plain `Combine`; the champion contains no `SwitchByBuff` and no `lol_kled_violent_*` marker.

## Q: Bear Trap on a Rope

- [x] `skill.action_name=skill1` is a 65000-range directional cast with a 360-tick cooldown.
- [x] Q launches one non-penetrating `LinearProjectile` at speed 3600, range 65000, and collision radius 8000, targeting enemy champions.
- [x] Q never uses `Rush`; the cast cannot drag Kled forward.
- [x] The first champion hit takes `30 + 80% AD`, is slowed by 20% for 45 ticks, and receives the named tether state.
- [x] One 45-tick delayed payload deals `20 + 40% AD`, then applies `Grab` at speed 2200 for 8 ticks and `Bind` for 30 ticks.
- [x] The data layer intentionally does not perform a second distance check before the delayed pull.

## E: Jousting

- [x] `skill2.action_name=skill2` is a 55000-range directional cast with a 480-tick cooldown.
- [x] E uses one non-penetrating `Rush`: speed 3200, Move Speed ratio 100%, collision radius 12000, enemy-champion target filter.
- [x] The first collision deals `30 + 80% AD` exactly once and grants Kled +20% Move Speed for 60 ticks.
- [x] E has independent `dash` and `impact` visuals from `kled_e_joust` and independent cast/hit audio.
- [x] E contains no Q projectile, tether, delayed damage, pull, bind, or four-hit state.
- [x] This data-only E has one dash and no second recast.

## R: Chaaaaaaaarge!!!

- [x] `ult.action_name=ult` is a 120000-range position cast with a 3600-tick cooldown and 120-tick cast duration.
- [x] Kled receives `200 + 80% AD` shield for 180 ticks, +50% Move Speed for 120 ticks, and crowd-control immunity for 90 ticks.
- [x] One 22000-wide, 120000-long `LineRangeProjectile` persists for 240 ticks and refreshes the same +25% allied Move Speed buff for 30 ticks on `AllyNotSelf`.
- [x] The terminal non-penetrating rush uses speed 4200, Move Speed ratio 150%, and collision radius 14000.
- [x] The first collision deals `80 + 100% AD + 2% target maximum HP`, knocks back at speed 2400 for 8 ticks, and applies 18 ticks of Airborne.

## Frozen data-layer limitations

- Kled is always mounted; Courage, dismount, and remount are not implemented.
- Q schedules its delayed pull after the initial projectile hit and does not perform a second distance check.
- E has one dash and no marked-target recast.
- R uses a straight data-defined route and does not navigate, turn, home, or perform a second direction-validity check.

Required live observations remain unchecked in `kled_live_qa.md` until the user tests the installed build.
