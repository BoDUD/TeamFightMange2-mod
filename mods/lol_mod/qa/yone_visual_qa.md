# Yone visual QA

- [x] Same-ID visual replacement targets `dual_blader` (official project hero 009).
- [x] Actor canvas is exactly `3502x88`; all 13 native tags, frame counts, durations, rectangles, and insertion order are preserved.
- [x] `hit_effect_area` reuses the official `ult[1..11]` atlas rectangles without conflicting pixels.
- [x] Idle/run/attack/Q/W/R/dead bodies retain one stable battle scale.
- [x] All 54 visible battle-body frames preserve their source hairline, cheek, jaw and alpha silhouette while receiving one visible profile eye; no rectangular face template remains.
- [x] Idle/run/attack/hit keep the official Dual Blader bottom clearances, and the 2x card/BP camera is restored to y=-12 so legs and weapons remain above the black divider.
- [x] Q3 uses a dedicated horizontal tornado, a vertical blue-white airborne cue, and a small ready-wind state.
- [x] Active champion data and release resources do not reference Soul Unbound. Exactly five retired Yone E names plus two retired Shen dash names remain registered only as no-op saved-season compatibility aliases.
- [x] W has no process-global ledger: one native callback scans only its current `GameCtx`, resolves an 80-degree forward cone, damages that snapshot, counts champion hits, and emits one shield tier marker.
- [x] W keeps Yone planted, plays one full caster-following crescent, and reuses one final-scale actor subject across all five native frames so transparent padding cannot create an E-like body jump.
- [x] Minions and monsters qualify for the base shield; every enemy champion hit increases its tier through the normal five-champion team limit.
- [x] W has no dash, spirit clone, anchor, tether, forced return, recall override, or teleport path.
- [x] Compact portrait is face-focused with transparent safety margins.
- [x] Default-runtime scoreboard QA replays the observed `idle[0]` source crop `(15,4,15,15)` at 2x nearest; the eye and source-derived jaw are fully inside the 30x30 slot.
- [x] BP-grid portrait is full body and ends at `y<=86`, ten pixels above the native name band.
- [x] BP illustration is `1420x860`; the three active-slot icons are independent `64x64` assets.

Runtime effect IDs and sheet tags are recorded in `qa/yone_visual_contract.json`.
