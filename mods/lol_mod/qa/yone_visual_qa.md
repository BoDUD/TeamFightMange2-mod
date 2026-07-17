# Yone visual QA

- [x] Same-ID visual replacement targets `dual_blader` (official project hero 009).
- [x] Actor canvas is exactly `3502x88`; all 13 native tags, frame counts, durations, rectangles, and insertion order are preserved.
- [x] `hit_effect_area` reuses the official `ult[1..11]` atlas rectangles without conflicting pixels.
- [x] Idle/run/attack/Q/W/R/dead bodies retain one stable battle scale.
- [x] All 54 visible battle-body frames plus the focused UI faces use a warm three-tone plane and exactly one two-pixel eye/brow cue; the idempotent pass changes RGB only and preserves every alpha bbox.
- [x] Q3 uses a dedicated horizontal tornado, a vertical blue-white airborne cue, and a small ready-wind state.
- [x] Active champion data and release resources do not reference Soul Unbound. Exactly five retired Yone E names plus two retired Shen dash names remain registered only as no-op saved-season compatibility aliases.
- [x] W keeps at most 128 ledgers, matches caster/player/team/position to the nearest eligible `started_tick`, and does not call opaque `ModService` APIs across the base 0.5.0 SDK / base 0.5.1 host boundary.
- [x] W keeps Yone planted, plays one full caster-following crescent, resolves one instant wide forward hitbox, and settles exactly one shield from that same deduplicated target set.
- [x] Minions and monsters qualify for the base shield; every enemy champion hit increases its tier through the normal five-champion team limit.
- [x] W has no dash, spirit clone, anchor, tether, forced return, recall override, or teleport path.
- [x] Compact portrait is face-focused with transparent safety margins.
- [x] Scoreboard portrait is an independent source-direct `48x64` crop for native `18x26` and `30x38` rectangles; runtime geometry must remain unchanged.
- [x] BP-grid portrait is full body and ends at `y<=86`, ten pixels above the native name band.
- [x] BP illustration is `1420x860`; the three active-slot icons are independent `64x64` assets.

Runtime effect IDs and sheet tags are recorded in `qa/yone_visual_contract.json`.
