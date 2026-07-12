# Kled Q/E/R skill contract QA

Status: static data, generated-resource, and native-animation-contract inspection passed on 2026-07-12; fresh installed-build and target-visible game verification remain pending.

## Identity and slot mapping

- [x] Project order is 006 and the same-ID replacement is `cavalry_knight`.
- [x] The occupied engine slot is the zero-based native index `17`; project order 006 is not a force-pick index.
- [x] The replacement keeps exactly the public three active slots: `skill=Q+E composite`, `skill2=E UI slot / original W mapping`, and `ult=R`.
- [x] Kled is intentionally always mounted on Skaarl in this data-only release.
- [x] No Courage, dismount, remount, separate Pocket Pistol, or fourth active cooldown is claimed.

## Base attack and Violent Tendencies state

- [x] A normal attack deals 100% Attack physical damage and uses Kled-specific cast/hit audio.
- [x] When `lol_kled_violent_haste` is absent, the attack follows the normal payload and does not advance a W stage.
- [x] When the W window is active, named stage buffs advance through `lol_kled_violent_stage1` to `lol_kled_violent_stage4` one attack at a time.
- [x] The fourth staged attack adds `20 + 35% AD + 4% target maximum HP`, plays its own hit/VFX event, and clears the haste and every stage marker.

## Q slot: Bear Trap on a Rope + Jousting composite

- [x] `skill.action_name=skill1` is a 65000-range directional cast with a 360-tick cooldown.
- [x] The embedded Jousting movement is one non-penetrating `Rush`: speed 3200, Move Speed ratio 100%, collision range 12000, enemy-champion target filter.
- [x] The first collision deals `30 + 80% AD`, slows the target by 20% for 45 ticks, grants Kled 20% Move Speed for 60 ticks, and starts the named tether visual/audio state.
- [x] One 45-tick delayed payload deals `20 + 40% AD`, then applies `Grab` at speed 2200 for 8 ticks and `Bind` for 30 ticks.
- [x] Q and the embedded E dash use independent Kled audio events while sharing the one public Q cooldown slot.

## E UI slot: original W mapping

- [x] `skill2.action_name=skill2` is the user-visible second active slot and its localized title begins with E to preserve this project's Q/E/R panel convention.
- [x] Mechanically this slot activates Kled's original W, Violent Tendencies: +60% Attack Speed for 240 ticks and a four-basic-attack state machine.
- [x] Activation clears stale stage markers before installing haste plus stage 1; a 240-tick cleanup removes every remaining W marker.
- [x] This mapping is stated explicitly in localization and QA instead of claiming that a second independent Jousting cooldown exists.

## R slot: Chaaaaaaaarge!!!

- [x] `ult.action_name=ult` is a 120000-range position cast with a 3600-tick cooldown and 120-tick cast duration.
- [x] Kled receives `200 + 80% AD` shield for 180 ticks, +50% Move Speed for 120 ticks, and crowd-control immunity for 90 ticks.
- [x] One 22000-wide, 120000-long `LineRangeProjectile` persists for 240 ticks and refreshes the same +25% allied Move Speed buff for 30 ticks on `AllyNotSelf`.
- [x] The terminal non-penetrating rush uses speed 4200, Move Speed ratio 150%, and collision range 14000.
- [x] The first collision deals `80 + 100% AD + 2% target maximum HP`, knocks back at speed 2400 for 8 ticks, and applies 18 ticks of Airborne.

## Frozen data-layer limitations

- Always mounted: no dismount/remount or Courage resource is implemented.
- The Q tether schedules its delayed pull after the initial collision and does not perform a second distance check before the pull.
- E is folded into the Q rush; the second UI slot is the W four-hit state machine.
- R uses a straight data-defined route and does not provide navigation, turning, homing, or a second direction-validity check.

Required live observations are intentionally kept in `kled_live_qa.md` and remain unchecked until the user tests the installed build.
