# Shen motion and retired-W regression QA

This file preserves the accepted run-cycle evidence and records that the former Spirit's Refuge experiment is no longer part of Shen's active Q/E/R payload.

## Run cycle

- Source: built-in image-gen 3x3 refinement using the accepted Shen actor as the exact character reference.
- Runtime: nine unique frames, each 0.08 seconds, ordered once with no repeated first frame at the loop boundary.
- Every generated frame ends at the y=45 foot baseline and has a 36 px visible height.
- Lower-body opaque-pixel counts: `173, 179, 194, 206, 236, 176, 163, 190, 177`.
- Consecutive lower-body difference/union ratios, including the loop boundary: `0.429, 0.465, 0.367, 0.399, 0.534, 0.408, 0.452, 0.464, 0.380`.

The validator requires all nine poses to remain unique, rejects a repeated first/last pose, rejects lower-body detail collapse, and constrains adjacent gait changes.

## Retired Spirit's Refuge experiment

- The old `shen_w` source/effect is historical only. `lol_shen.data_champion` must not reference `shen_w`, `spirit_refuge`, or any `lol_shen_w_*` event.
- Active `skill2` is Shadow Dash. It uses the independent `shen_e` dash/impact sheet, a 30-tick dash-trail marker, a 90-tick taunt marker, and the native `CCState::Taunt` callback.
- The validator now rejects any reintroduction of the former caster-centered refuge field into Q, E, or R.

The historical W frame geometry is not a release gate because that asset is no longer loaded by the active champion contract.
