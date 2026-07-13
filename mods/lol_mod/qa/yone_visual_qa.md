# Yone visual QA

"
        "- [x] Same-ID visual replacement targets `dual_blader` (official project hero 009).
"
        "- [x] Actor canvas is exactly `3502x88`; all 13 native tags, frame counts, durations, rectangles, and insertion order are preserved.
"
        "- [x] `hit_effect_area` reuses the official `ult[1..11]` atlas rectangles without conflicting pixels.
"
        "- [x] Idle/run/attack/Q/W/R/dead bodies use independent generated pose groups while retaining one stable battle scale.
"
        "- [x] Q/W/R high-footprint feedback is packed into separate `yone_q`, `yone_w`, and `yone_r` sheets.
"
        "- [x] Compact portrait is face-focused with transparent safety margins.
"
        "- [x] BP-grid portrait is full body and ends at `y<=86`, ten pixels above the native name band.
"
        "- [x] BP illustration is `1420x860`; Q/W/R icons are independent `64x64` assets.
"
        "
Runtime effect IDs and sheet tags are recorded in `qa/yone_visual_contract.json`.
