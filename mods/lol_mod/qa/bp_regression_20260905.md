# BP regression history and 0.12.21 candidate — not live acceptance

## 0.12.21 implementation, superseding the containment below

User explicitly requested no agent-run in-game tests; live verification belongs
to the user. This changes the normal skill QA workflow; no live pass is claimed.

- All 61 current champion IDs have a native-owned 1024x184 PNG atlas. The engine
  follows selection/manual swaps/coach swaps; the mod never assigns a source.
- Blue and red cards use exact 284x172 regions at (0,6) and (740,6). The native
  confirmation/portrait center-crop has its own middle region, so it does not
  sample the side-card copies at normal portrait aspect ratios.
- Nine authored splashes have opaque full-card regions. Remaining heroes use
  their current native idle image/camera on transparent cards at native size and
  native blue/red placement, allowing the original player labels to remain.
- `bp_full_cards.rs` updates both the child crop/size and parent placement. There
  is no size classifier, draft-index inference, raw pointer access, or engine patch.
- It checks the complete installed PNG catalog and active champion ID coverage
  before applying the layout. Incomplete packages retain the legacy fallback.
- Build only used `build_bp_full_cards.py` and the normal stable DLL builder;
  no Yone/Xayah actor builder was run. `package_bp_incremental.py` installed 64
  BP/metadata files and verified all 34 protected actor/champion/style/text files
  remained byte-identical. Six BP static tests and compilation passed.
- Installed DLL SHA256:
  `9a05507555a243992a53b03c2f53236685f880e0e21110b932e06601a7a47486`.
- Recoverable backup: game-root `mod_backups/bp_01221_20260905_185524`.
- Original save retains the SHA256 recorded below. Yone leg redraw remains open.

Remaining user verification: restart game; check both teams after selection and
manual/coach swaps, including transitions between a splash hero and a native
pixel hero. Check splash cards hide player text/dividers and non-splash cards
retain their original layout. This is an implemented candidate, not a claim of
perfect rendered output.

## Earlier containment record (historical)

User priority: fix BP first; stop Yone/Xayah art changes. New Yone short-leg drafts
are rejected and must not be staged or installed.

## Rejected route

- QA 6 resized the native image. Geometry changes persisted across source changes,
  stretching a native actor after a swap.
- QA 7 moved/enlarged the parent but left the inner 137x184 image unchanged.
  This produced a narrow left-hand illustration and moved Shen over player text.
- Native ogre and shield_bearer can also occupy 137x184. Size is not an image-kind
  or champion-identity discriminator. Never restore this classifier.

## Containment applied

- Installed DLL restored to saved production SHA256
  `A0A44195FE615A9187472C77724B0D369CC3D29C1CBDB9BA140BE254D1A2723F`.
- Experimental native auto-map images and the rejected adapter were moved to
  the game-root `mod_backups/bp_rejected_layout_20260905` archive, not deleted.
- `qa-bp-ui` now only adds observation; it no longer selects an alternate renderer.
- Builder no longer generates/packages native auto-map portraits and refuses to
  build if rejected PNGs remain in that active directory.
- Four BP tests and `cargo check --release --features qa-bp-ui` pass.
- Original save SHA256 remains
  `06B13090F8CC121607B1ED18872668585BE0BA4F2112647E9085B8C43FB333E4`.

## Still open — do not claim fixed

The production fixed-image overlay uses grid draft-order badges. It deliberately
falls back to native actors during swap, because badges do not expose the current
athlete/champion permutation. User requires full-card illustrations through swaps.

The official 0.5.8 native auto-map owns the actual assignment, but its side portrait
helper resolves a 137x184 cover crop and sets the native image on that surface.
The stable API's image state does not expose its source or crop. Do not guess from
athlete labels, mastery badges, favorite champion icons, or dimensions.

The old local classic SDK is 0.5.0, not current renderer evidence. Official 0.5.8 SDK
was separately downloaded to `.tmp_tools/sdk_058`; inspection confirms the native
`set_banpick_champion_portrait` helper uses the 137x184 cover resolver. Neither SDK
nor game binaries were modified.

Acceptance still requires target-visible live evidence: full-card Yone/Xayah art
after selection, manual swap, coach swap, and new draft; correct hero per slot;
no player text/divider above art; native/missing-art heroes retain their layout.
No new live acceptance has been claimed after the rollback. Encyclopedia and actor
assets are outside this containment change.
