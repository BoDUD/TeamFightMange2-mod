# Shen motion and restored-W regression QA

This file preserves the accepted run-cycle evidence and prevents the retired Shadow Dash experiment from returning to Shen's active Q/W/R payload.

## Run cycle

- Source: built-in image-gen 3x3 refinement using the accepted Shen actor as the exact character reference.
- Runtime: nine unique frames, each 0.08 seconds, ordered once with no repeated first frame at the loop boundary.
- Every generated frame ends at the y=45 foot baseline and has a 36 px visible height.
- Lower-body opaque-pixel counts: `173, 179, 194, 206, 236, 176, 163, 190, 177`.
- Consecutive lower-body difference/union ratios, including the loop boundary: `0.429, 0.465, 0.367, 0.399, 0.534, 0.408, 0.452, 0.464, 0.380`.

The validator requires all nine poses to remain unique, rejects a repeated first/last pose, rejects lower-body detail collapse, and constrains adjacent gait changes.

## Restored Spirit's Refuge

- Active `skill2` is Spirit's Refuge: a 35,000 caster-centered field using `shen_w`.
- The field shields allied champions for 150 + 40% AP over 150 ticks and reduces enemy champion attack speed by 30% for 120 ticks.
- The six-frame `field` animation and independent W icon are generated from the original accepted W sources.
- The later Shadow Dash icon, VFX, data payload, runtime native effect, and input AI are retired and removed.

The validator rejects any active `lol_shen_shadow_dash` payload and requires Q/W/R to remain independently visible and audible.
