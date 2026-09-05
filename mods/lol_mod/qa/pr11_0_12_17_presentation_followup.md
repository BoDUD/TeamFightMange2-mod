# PR11 0.12.17 — presentation feedback follow-up

## User evidence and requested change

2026-09-05 screenshots confirm 0.12.16 BP splashes are restored and Yone/Xayah
encyclopedia models show legs. Remaining complaints: encyclopedia figures sit
too high, and BP should show only the full illustration, not the athlete name,
position icon, Mastery Bonus/+0% or favourite-hero portraits.

## Encyclopedia

Only the two existing encyclopedia image nodes move down 12 logical UI pixels:
destination bottom 76 -> 88. Width/height, source texture, UV, alpha, model PNGs,
all other heroes, card/control geometry, skills and battle animations stay
unchanged. The offline native model reports head Y=19.375 for both, compared
with native Briar's Y=20.5. Whole-body heights remain 57/58.5 pixels; sampled
source clipping stays zero. It is no longer required that every actor pixel
sit above the tier button: that requirement caused the rejected top alignment.
Native buttons remain in front and may overlap shoe pixels, as on other cards.

Candidate offsets 76/84/88/90/94 were inspected before choosing 88; larger
downward offsets increasingly hide feet behind the tier selector. Diagnostic
only: `.tmp_tools/encyclopedia_position_candidates.png`.

## BP illustration-only display

Move the fully opaque 284x172 illustration group to the FINAL child of each
verified native done-card leaf, after the name, position, proficiency widgets,
centre divider and native actor. Remove the extra dark tint. The full image
now covers those earlier details without changing their native paths or
visibility state. Some existing PNG edges have alpha 249 rather than 255, so
an opaque matte UNDER the art guarantees full coverage without darkening it
with an overlaid tint. Tests require all 18 composited cards to be opaque, so
native details cannot leak through transparent holes. Blue/red edge indication and
noninteractive input behaviour are preserved.

This is deliberately confined to selected mod heroes whose illustration is
ready. Empty/active pick slots, non-mod heroes and swap fallback retain their
native information. Full/global draft layout and champion grid are untouched.

## Gait remains separate and unresolved

Read-only inspection of the user's specified Workshop pack confirmed its Yone
uses five run frames at 0.1s; Viktor uses ten at 0.065s. Only implementation
and motion measurements were used, not copied art. Our contract stays eight
frames at 0.080000006s.

Two further native ImageGen requests in the existing Work task produced a
single opposite-support attempt and another eight-frame sheet. The sheet adds
closed/crossing leg silhouettes but does not clearly reverse support at frames
1/5. Neither is production-approved or installed. A direct built-in ImageGen
attempt still returned HTTP 404, with no image. Existing unsent Work editor
text was preserved; no user draft, API billing or credential was changed.

## Validation status

Stable ABI 8 DLL build succeeded. Final offline regression: 230 passed (21.40s).
The first run found semitransparent legacy PNG edges; the opaque backing fix
was added before the passing run. Source body/animation assets are unchanged.
Installed runtime closure: 470 files, individually SHA-256 verified. Previous
installed mod and mods.json were backed up and hash-verified at
`D:/steam/steamapps/common/Teamfight Manager2/mod_backups/lol_mod_pre_0.12.17_20260905`.
The game was not running and was not launched; no saves were touched. No fresh
live rendering claim is made solely from the generator, manifest, or tests.
