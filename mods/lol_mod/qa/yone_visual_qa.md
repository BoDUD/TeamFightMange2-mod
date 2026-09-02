# Yone visual QA

- [x] Current release contract is `0.10.20`; `0.10.19` is retained as partial runtime-routing history and must never identify the installed DLL or telemetry.
- [x] Same-ID visual replacement targets `dual_blader` (official project hero 009).
- [x] Actor canvas is `4262x88`; the original `3502x88` native prefix and all 13 native tags/rectangles/timings are unchanged, with five explicit semantic tags appended.
- [x] `hit_effect_area` reuses the official `ult[1..11]` atlas rectangles without conflicting pixels.
- [x] Idle/run/attack/Q/W/R/dead bodies retain one stable battle scale.
- [x] All 67 physical body poses come only from `source/native/yone_v7/frames.json`; V3/V4/V5/V6 battle-body routes are retired and cannot be selected as fallbacks.
- [x] `source/imagegen/yone_v4_action_contact.png`, `source/imagegen/yone_v4_idle_candidate_43x55.png`, and the old `source/native/yone_v4` route are retired body inputs and are never loaded by this builder.
- [x] V5 body inputs `yone_v5_idle_source.png`, `yone_v5_idle_golden_43x55.png`, `yone_v5_motion_contact.png`, `yone_v5_attack_q_w_contact.png`, `yone_v5_q5_contact.png`, `yone_v5_ult_contact.png`, and the complete `source/native/yone_v5` route are retired and never loaded.
- [x] The four hash-locked ImageGen contacts use isolated `5x4`, `6x4`, `3x2`, and `5x3` grids with explicit gutters; cell extraction cannot borrow a sword from an adjacent pose.
- [x] Every V7 pose is finalized at 1x size, palette-validated, and copied byte-for-byte; only source-to-native generation performs the controlled source resize and crop.
- [x] The V7 chibi face preserves true source-authored eye-outline cues, jaw and hair clusters without post-scale face repaint.
- [x] The body preview proves the exact idle[0] 2.2x NEAREST battle render and divider clearance; dedicated UI portraits own the right-side icon exclusion.
- [x] Idle/run keep compact silver and red swords simultaneously visible; basic attacks switch between separate six-frame steel and Azakana tags.
- [x] The fixed palette declares six mutually exclusive roles: steel dark/mid/highlight and Azakana dark/red/highlight; body colors cannot satisfy any weapon role.
- [x] Every frame records both hand anchors, both tips, both blade boxes, spans, connectedness, pixel counts, crop ratios, and source-tip survival; CI recomputes those 16 fields from the final PNG instead of trusting the manifest.
- [x] Negative tests delete a blade, inject fake red pixels, disconnect a handle/tip, share hands/tips, shorten a blade, or move it to the crop edge, and each corruption is rejected.
- [x] CI enforces per-frame neutral dual-sword visibility plus active-blade reach for alternating steel/Azakana attacks, Q/Q3, W, and R; eight long caster-follow overlays extend active weapons without replacing the actor body.
- [x] Q1/Q2 use `skill_q12`, Q3 uses a separate lowered `skill_q3`, W uses `skill_w_azakana`, and R retains thirteen dual-sword frames.
- [x] Idle/run/attack/hit keep the official Dual Blader bottom clearances, and the card/BP center camera is raised to y=-16 so legs and weapons keep a visible gap above the black divider.
- [x] Q3 uses a dedicated horizontal tornado, a vertical blue-white airborne cue, and a small ready-wind state.
- [x] Active champion data and release resources do not reference Soul Unbound. Exactly five retired Yone E names and three pre-cone W names remain registered only as no-op saved-season compatibility aliases; no retired Shen dash native remains.
- [x] W has no process-global ledger: one native callback scans only its current `GameCtx`, resolves an 80-degree forward cone, damages that snapshot, counts champion hits, and emits one shield tier marker.
- [x] W keeps Yone planted, plays one full caster-following crescent, and uses five V7 Azakana-led sweep poses; no code-drawn body is added during packing.
- [x] Minions and monsters qualify for the base shield; every enemy champion hit increases its tier through the normal five-champion team limit.
- [x] W has no dash, spirit clone, anchor, tether, forced return, recall override, or teleport path.
- [x] Compact portrait is face-focused with transparent safety margins.
- [x] Fullbody/compact/scoreboard/grid UI art comes only from the high-resolution V7 UI source through magenta-key, one uniform LANCZOS shrink, hard alpha, and a 128-color finish; no battle frame is enlarged.
- [x] The `85x93` V7 fullbody texture is pasted 1:1 into `qa/yone_v7_ui_card.png`, including the y=96 divider and right-side icon exclusion.
- [x] The card proof leaves the name band blank because localized `永恩` is drawn by the runtime engine text layer, not by the portrait texture.
- [x] QA replays the user's exact idle[0] 2.2x nearest-neighbor actor path, compares all idle/run frames, rejects near-white face blocks, and preserves source foot/card-bottom clearances.
- [x] BP-grid portrait is full body and ends at `y<=86`, ten pixels above the native name band.
- [x] BP illustration is `1420x860`; the three active-slot icons are independent `64x64` assets.

Runtime effect IDs and sheet tags are recorded in `qa/yone_visual_contract.json`.
