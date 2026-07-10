# Shen motion and W alignment regression QA

This pass responds to the live reports that the run lacked a visible cross-step and that Spirit's Refuge did not visually center on the caster.

## Run cycle

- Source: built-in image-gen 3x3 refinement using the accepted Shen actor as the exact character reference.
- Runtime: nine unique frames, each 0.08 seconds, ordered once with no repeated first frame at the loop boundary.
- Every generated frame ends at the y=45 foot baseline and has a 36 px visible height.
- Lower-body opaque-pixel counts: `173, 179, 194, 206, 236, 176, 163, 190, 177`.
- Consecutive lower-body difference/union ratios, including the loop boundary: `0.429, 0.465, 0.367, 0.399, 0.534, 0.408, 0.452, 0.464, 0.380`.

The validator requires all nine poses to remain unique, rejects a repeated first/last pose, rejects lower-body detail collapse, and constrains adjacent gait changes.

## Spirit's Refuge

- Data binding remains `CasterViewEffect`, `AroundCaster`, `is_follow: true`, and `z: -1`.
- The six image-gen field phases are packed into 112x64 frames with target alpha bounds `(4,29)-(108,59)` (the spark phase is `(7,29)-(106,59)`).
- Visible field size is approximately 104x30 px and its vertical center is y=43.5, aligned with Shen's y=45 foot point instead of the rejected y=31.5 center.

The validator rejects W frames outside the 96–106 px width, 24–34 px height, centered x=54–57/y=42–45 contract.
