# Kled R charge and trail QA

## Static contract

- [x] R is a 120000-range position cast with a 3600-tick cooldown and a 120-tick charge action.
- [x] Kled receives a `200 + 80% AD` shield for 180 ticks, +50% Move Speed for 120 ticks, and `cc_immune=true` for 90 ticks.
- [x] One `LineRangeProjectile` named `lol_kled_r_trail` is 22000 wide, 120000 long, has a 240-tick apply window, and targets `AllyNotSelf`.
- [x] The trail repeatedly refreshes one named `lol_kled_r_trail_speed` buff at +25% Move Speed for 30 ticks; it does not add a second trail copy to Kled.
- [x] R's terminal `Rush` uses speed 4200, Move Speed ratio 150%, collision range 14000, and `penetrate=false` against enemy champions.
- [x] The first collision deals `80 + 100% AD + 2% target maximum HP`, then applies `Knockback(speed=2400,tick=8)` and 18 ticks of Airborne.
- [x] Charge, allied trail, and impact have independent generated tags and `lol_kled_r_cast` / `lol_kled_r_impact` audio events.

## Frozen route limitation

The current data contract represents R as a straight selected route plus a non-penetrating collision rush. It does not navigate around terrain, turn after cast, home along a changing target path, or perform a second direction-validity check. Kled remains mounted throughout.

## Pending live checks

- [ ] R starts in the selected direction and keeps the same straight route in both horizontal facings.
- [ ] Kled's charge body, shield, dust, and trail remain aligned without forward drift, size jumps, or missing effect frames.
- [ ] Nearby allies gain one refreshing speed state while enemies, minions, towers, and Kled do not receive the ally-trail copy.
- [ ] The first enemy-champion collision stops the rush and shows the complete impact, damage, knockback, and Airborne response.
- [ ] A missed charge ends cleanly with no permanent line, speed buff, CC immunity, shield, or audio loop.
- [ ] R near terrain boundaries stays readable and does not place the mounted body inside walls, towers, or objective pits.
