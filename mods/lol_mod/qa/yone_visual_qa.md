# Yone visual QA

- [x] Same-ID visual replacement targets `dual_blader` (official project hero 009).
- [x] Actor canvas is exactly `3502x88`; all 13 native tags, frame counts, durations, rectangles, and insertion order are preserved.
- [x] `hit_effect_area` reuses the official `ult[1..11]` atlas rectangles without conflicting pixels.
- [x] Idle/run/attack/Q/E/R/dead bodies retain one stable battle scale.
- [x] Q3 uses a dedicated horizontal tornado, a vertical blue-white airborne cue, and a small ready-wind state.
- [x] E leaves one opaque approved-body anchor at the cast point; the real caster performs one short directional lunge and becomes the controllable spirit.
- [x] E's caster-following layer contains only a thin outline and sparse particles; no filled blue duplicate or fake humanoid projectile remains.
- [x] E binds runtime `CasterAnimation` to the five-frame `skill2_attack` leave-body motion and reserves a 60-tick fast, CC-immune return phase for the native anchor AI.
- [x] Compact portrait is face-focused with transparent safety margins.
- [x] BP-grid portrait is full body and ends at `y<=86`, ten pixels above the native name band.
- [x] BP illustration is `1420x860`; the three active-slot icons are independent `64x64` assets.

Runtime effect IDs and sheet tags are recorded in `qa/yone_visual_contract.json`.
