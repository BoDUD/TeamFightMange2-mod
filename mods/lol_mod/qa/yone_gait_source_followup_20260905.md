# Yone gait follow-up, after 0.12.17

Status: NOT FIXED / no replacement gait installed.

## Concrete diagnosis

The original motion sheet repeats a foreground-forward leg. The legacy
generator takes lower-body donors 4/5/6/7 and mirrors those patches for the
second half-cycle. This changes screen-space contacts but does not prove
that the hips, thighs, knees and feet belong to a coherent alternating gait.
The upper body remains independently sourced, which can produce the visual
disconnection reported by the user. This is not a skill/UI regression.

`run_foot_geometry` labels pixels left/right solely by x relative to pelvis.
Its historical `support_leg` field is therefore a screen-side contact label,
not anatomical identity. The function now explicitly reports
`support_screen_side` and `anatomical_leg_identity_verified: false`, retains
the old field for compatibility, and documents the limitation. A regression
test exercises all eight current frames. Passing this geometry test must not
be described as a natural-gait acceptance.

## Source attempts in this turn

Built-in ImageGen returned HTTP 404 before generating an image. The user had
already authorized Work generation, so the existing task was continued:
https://chatgpt.com/c/6a9b85a5-337c-83ee-8249-90c0596bc597

Only our original `yone_v7_motion_contact.png` and outputs derived from it
were image references. Workshop Yone/Viktor were inspected read-only for
motion structure; their art was neither copied into the mod nor uploaded.

- Attempt 6, "错步双刃剑士": single opposite contact. Still mostly a standing
  V-shaped leg pose; rejected. Retrieved to
  `output/imagegen/rejected/yone-work-v8-sixth.png`.
- Attempt 7, "双剑武者侧视步行循环": stronger side-facing request and eight
  phases. Contact A/B still repeat foreground leg ownership; rejected.
  Retrieved to `output/imagegen/yone-work-v8-seventh.png`.
- Attempt 8, "青黄双腿步态验证像素图": temporary cyan/yellow identity markers
  in four key poses. Mostly recolors rather than anatomical occlusion changes;
  diagnostic only. Retrieved to
  `output/imagegen/yone-work-v8-eighth-diagnostic.png`.
- Attempt 9, "交叉步态像素武士": targeted hip-to-rear-foot crossover. The
  cyan foreground thigh crosses the yellow thigh more clearly. This is ONE
  diagnostic key pose, not an accepted cycle. Available in Work; not retrieved
  locally. Browser asset inventory did not expose it; the signed image URL
  also returned 403 without the browser session. No credentials were copied.
- Attempt 10, "双剑战士八帧行走循环": restore original colors and expand the
  A/B references to eight phases. Frame 5 loses the corrected crossover again;
  rejected after visual inspection. Available in Work, not retrieved locally.

All requests required the same original model, compact steps, coherent hip
connections, unchanged sword identity, no trails, no extra limbs, full feet,
and no half-body mirroring. Diagnostic colors were explicitly temporary and
never used in game. The user's unsent image-editor draft was preserved.

## Verification and remaining work

Full repository regression: 231 passed (22.41s); diff whitespace check clean.
Only generator audit semantics, its regression test, and this report changed.
No source/native frames, runtime assets, DLL, skills, encyclopedia or BP UI
were changed or reinstalled. Installed game remains 0.12.17.

The usable outcome needed next is a complete hand-authored/edited sequence
with persistent near/far leg identity through both contact and passing poses.
ImageGen did not reliably provide that sequence. Do not install one of these
rejected sheets, claim the current mirror route is accepted, or increase the
stride threshold until malformed legs pass. A switch from ImageGen to direct
pixel editing needs the user's explicit method choice under imagegen rules.
