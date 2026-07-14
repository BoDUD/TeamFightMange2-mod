# Yone visual QA

- [x] Same-ID visual replacement targets `dual_blader` (official project hero 009).
- [x] Actor canvas is exactly `3502x88`; all 13 native tags, frame counts, durations, rectangles, and insertion order are preserved.
- [x] `hit_effect_area` reuses the official `ult[1..11]` atlas rectangles without conflicting pixels.
- [x] Idle/run/attack/Q/E+W/R/dead bodies retain one stable battle scale.
- [x] Q3 has a dedicated vertical airborne cue.
- [x] E uses approved-body spirit silhouettes for outbound/return plus a fixed body anchor; it never swaps the real actor body.
- [x] E+W binds runtime `CasterAnimation` to the five-frame `skill2_attack` tag; the QA contact displays that same tag.
- [x] W uses aligned data hitboxes: one broad crescent damages every non-tower enemy once, while a champion-only probe drives the capped shield and never attacks.
- [x] Compact portrait is face-focused with transparent safety margins.
- [x] BP-grid portrait is full body and ends at `y<=86`, ten pixels above the native name band.
- [x] BP illustration is `1420x860`; the three active-slot icons are independent `64x64` assets.

Runtime effect IDs and sheet tags are recorded in `qa/yone_visual_contract.json`.
