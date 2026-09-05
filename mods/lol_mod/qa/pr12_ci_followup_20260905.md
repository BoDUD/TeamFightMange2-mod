# PR 12 build/CI follow-up

The first GitHub run (33962331124) compiled the stable DLL successfully, then
failed in Xayah packing: computed bottom 11px conflicted with native 8px.

Fixes:

- Keep the single run-source scale but restore the eight measured native foot
  anchors. Verify each packed run frame against its shared-scale source. Keep
  the old 12–15% enlargement gate on unchanged non-run actions, explicitly
  identifying that measurement scope in the report.
- Make BP builds independent of the local proprietary game bundle. Commit only
  52 native compact portrait inputs, native roster/styles and hash/crop records.
  Mod-owned actor crops still come from current mod sheets, not cached copies.
- Refresh version/provenance checks for 0.12.21 and hand-authored Yone legs;
  use alpha bytes for the check that incorrectly required Pillow 12 in a CI
  environment pinned to Pillow 11.3.0.
- Pin the already-committed dancer BP camera change in the five-legacy-actor
  preservation audit. Do not relax the general camera hash gate.
- Include new BP atlases in the committed-generated-files CI gate.

Offline evidence in `tmp/pr12-ci-20260905` (not committed): complete build and
355/355 override-reference validation passed; pytest **244 passed, 1 skipped**.
The skipped test explicitly requires proprietary `bundle.game_data`, which is
intentionally absent from CI. Reproduction used Windows Python 3.12 with the
CI-pinned Pillow 11.3.0 and pytest 8.4.1 in an isolated repository copy.

BP PNG compressed bytes were refreshed under the pinned Pillow version; all
61 decoded RGBA images were identical to the prior PR candidate. Xayah run
output now matches the submitted shared-scale builder. Yone frames were not
redrawn in this follow-up. Generated manifests/reports were synchronized.

No installed mod assets, DLL or saves were overwritten; no game was launched.
This evidence is build/asset correctness, not user-visible live acceptance.
