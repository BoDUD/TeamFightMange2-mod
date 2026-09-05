# Yone leg-only asset update — 2026-09-05

Status: installed candidate for the user's own in-game review. No live test,
game launch, save edit, or claim of natural/perfect motion was made.

- Eight independently drawn 19 × 12 native-pixel leg cels, using the original
  navy cloth/brown leather palette, waist trim, knees, cuffs and boots.
- Alternating near/far support and recovery poses; no procedural thickening,
  scanline displacement, limb stretching, ghost/trail overlay or generated body.
- Original upper-body/protected weapon pixels retained exactly. Unmodified
  original eight frame boxes and 0.080000006-second duration per frame.
- Editable art: `source/native/yone_run_handdrawn/legs.pixel.json`.
- Reproducer: `tools/compile_yone_run_handdrawn.py --output <review directory>`.
  Compilation alone does not authorize installing a new revision.
- Six focused asset checks passed, including native-source reproduction,
  protected-body equality, packed-frame equality and non-run preservation.
  These checks do not establish subjective gait quality in game.

Only the run rectangles of `yone_v7#sheet.png` and `yone#sheet.png` were replaced
in the installed mod; every pixel outside them was retained. 530 other runtime
files remained unchanged. BP 0.12.21, its DLL, Xayah, encyclopedia positions,
skills, version metadata and animation tables were not rebuilt or copied.

Recoverable pre-update atlas/manifest backup:
`D:/steam/steamapps/common/Teamfight Manager2/mod_backups/yone_run_20260905_194708`.

The previous generated-leg route is superseded, not an accepted reference.
This turn's Work outputs repeated one support leg or changed model identity;
none were installed. The native hand-drawn candidate and preview are under
`output/yone_leg_identity_20260905/hand-cels`. Future edits must retain this
source distinction; an asset check must never turn an unreviewed generated
sheet or the previously rejected thin/widened legs into a claimed live pass.
