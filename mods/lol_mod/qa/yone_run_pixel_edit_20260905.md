# 0.12.18 — authorized Yone leg-only edit

The user explicitly authorized direct frame-by-frame leg pixel edits while
retaining the original model. This supersedes the earlier generation-only
restriction for this Yone edit. No Work or API generation was used.

- Eight separately authored near/far pant/boot clusters use the original palette.
- The near leg retains foreground identity as the feet pass. The far leg stays
  behind it. No whole-lower-body mirroring, sprite resize or line/bone renderer.
- Both legs have four stance and four swing frames, with 1–3 native pixels of
  swing clearance. Adjacent foot positions, including 7→0, move at most 4 pixels.
- The original waist, head, torso and all sword-color pixels are retained.
  The edit clears the previous lower-body ROI before drawing; no old/new limb
  alpha stacking is used. All other actions are byte-identical to their sources.
- Native frame rectangles, eight 0.080000006-second durations, bottom anchors,
  native facing mirroring, skill mechanics and encyclopedia fit are unchanged.

The immutable `source/native/yone_v7` frames retain the rejected mirrored gait as
provenance. Its `generation_qa.json` and mirror validator are NOT acceptance of
the new packed run. `tools/yone_run_pixel_edit.py` is the explicit, independently
tested override. Current packed evidence is `qa/yone_run_pixel_edit.json` and
`output/yone_leg_edit/{contact.png,run.gif}` outside the shipped mod.

Status: offline authored-pixel and packing verification; live battle acceptance
is still pending. Do not call this a visually accepted final gait from tests.

Outstanding separate user requests: Xayah BP-grid offset, exchange-stage splash
fallback, Xayah action-size/gait and LoL-style skill mechanics/descriptions.
They are not changed by this isolated Yone patch. Encyclopedia placement was
confirmed fixed by the user and is locked.

## Verification and installation

- Full suite: **235 passed** (25.82 s); `git diff --check` passed.
- Stable DLL compiled successfully, required ABI remains 8 / base 0.5.8.
- Runtime closure remains 470 files. Compared with 0.12.17, only the two Yone
  compatibility atlas PNGs, version metadata and version-rebuilt DLL changed.
- Installed 0.12.18 after confirming the game was not running. Installer checked
  every runtime file hash after copying. Only `lol_mod` remains enabled.
- Complete verified pre-install backup:
  `D:/steam/steamapps/common/Teamfight Manager2/mod_backups/lol_mod_pre_0.12.18_20260905`
  (470 runtime files plus mods.json). No saves/custom database modified.
- No live game was started for this pass. Visual acceptance remains pending.
