# PR11 0.12.16 — BP draft repair candidate and Work art handoff

## Acceptance boundary

This patch does not change battle PNGs, animation timing, skills, or Shen.
The previous 0.12.15 encyclopedia layout-only candidate is preserved. Neither
encyclopedia nor natural gait has new target-visible live acceptance.
No game or save/custom database is opened, closed, or modified by this work.

## BP cause and repair

The 0.12.15 shared BP function used `done.name` (the athlete's name) as the
champion key. Oner/Faker therefore did not resolve to any of the nine heroes.
All 18 existing 284x172 illustration PNGs were present; repacking alone could
not fix this identity error.

`src/bp_illustrations.rs` now resolves the native grid child champion ID using
the locally visible blue/red pick-number badge. Numbers are one-based; side
card IDs `pick_slot_N` are zero-based. Parent filtering/scroll visibility does
not invalidate the badge. Duplicate, missing, malformed, banned or ambiguous
claims retain the native actor instead of guessing a hero.

Only two side-card leaf templates are overridden. Removing the added image
group recovers the exact native template, checked against pinned SHA256 and
the installed 0.5.8 bundle. Full draft layout and champion grid stay native.
Nine fixed-source images per card eliminate the previous late-source binding
and late-spawn zero-rect path. The original position/name/proficiency controls
remain after the image block. There is no negative-z illustration.

The per-frame callback runs after the native update, before the chrome scan
throttle. It hides the native actor only after successful visibility updates
and a 284x172 image runner rect. That is offline readiness evidence, **not a
GPU texture/rendering success claim**. All image assets are manifest-validated.

### Remaining BP limitation

Swap/assignment order differs from draft badge order. Stable ABI 8 does not
expose that permutation. During swap, this patch deliberately restores the
stock actor and hides the splash. Full swap-stage illustration support is
unfinished. Live blue/red draft, filtered grid, repick and swap checks remain
required; this candidate must not be described as an entirely verified BP fix.

## Work ImageGen — generated and retrieved, not production-approved

User explicitly requested Work. Used the logged-in browser Work interface and
its native image-generation tool, uploading only the original Yone reference:
`source/imagegen/yone_v7_motion_contact.png`.

Work task: [生成像素行走动画 PNG](https://chatgpt.com/c/6a9b85a5-337c-83ee-8249-90c0596bc597).

Three original PNGs were retrieved into repository-relative paths outside the
active mod and release manifests:

- `output/imagegen/rejected/yone-work-v8-first.png` (1774x887): repeated forward
  leg and model/head drift; rejected.
- `output/imagegen/rejected/yone-work-v8-second.png` (1774x887): near boot stays
  forward in almost every pose; rejected.
- `output/imagegen/rejected/yone-work-v8-third.png` (1402x1122): reduced four-key
  cycle still fails the opposite contact phase; rejected.

Generation/retrieval succeeded. Production gait redraw did not pass. None was
packed into an actor atlas. No procedural leg or mirror patch was added.
Full final prompt is in `output/imagegen/WORK_PROMPTS.md`; Work retains all
iterations and source attachment. No credential was uploaded to Work.

## Offline validation

- Stable ABI 8 DLL compiled; six executable Rust resolver tests passed.
- Full build completed; subsequent `pytest -q`: **230 passed** in 21.77 seconds.
- Gates cover all nine IDs on both sides, filtered parents, unordered children,
  unknown/duplicate claims, malformed markers, unpick/swap cleanup, layout
  initialization and failed UI mutation fallback.
- An earlier test run overlapped a still-running asset build and read temporary
  CRLF files; its manifest failures were discarded and the complete suite was
  rerun only after the build finished. Do not run readers during generation.
- Installed **0.12.16**, 470/470 runtime files hash-verified by the installer;
  no extras, only `lol_mod` enabled. Prior 0.12.15 package and mods config were
  copied and hash-verified in `mod_backups/lol_mod_pre_0.12.16_20260905` before
  replacement. No game process was running; none was launched or stopped.
- Target-visible live rendering remains pending, separately from installation.
