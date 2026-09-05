# PR11 0.12.15 — native encyclopedia crop correction; BP diagnosis

## Scope and acceptance

This is an encyclopedia-only repair candidate. Battle animation PNGs, animation
timings, abilities, save files, and BP code are unchanged. Live acceptance is
**pending**, not established by the tests below. The user's 2026-09-05 evidence
revokes 0.12.14 encyclopedia and natural-gait acceptance.

## Encyclopedia root cause and change

Read-only disassembly of the game-bundled 0.5.8 `game_view` library proves:

- `champion_info_ui::init_champion_list` calls `set_champion_icon_center` with
  width 85, height 93, scale 2 (cgu.15, offsets 0x84f–0x874).
- `set_entity_icon_center` takes the first idle frame. Its sampled Y is
  `frame.y + max(0, (frame.h - 93/2)/2) + center.y`; its node height is
  `min(frame.h*2, 93)` (cgu.01, offsets 0x233–0x312 and 0x379–0x43b).
- Therefore a more negative `center.y` moves the UV crop upward and the actor
  **downward**. It is not a destination-position offset. The previous 2.2x,
  121px-stage model was not a valid encyclopedia test.

The new independent `qa_encyclopedia_geometry.py` reproduces the rejected
0.12.14 screenshot: Yone loses 122 opaque source pixels, Xayah loses 54; both
would extend to card Y=103.5, past the 93px image and behind the tier controls.

Per-hero center sampling offsets are now Yone -3 and Xayah 0. A narrowly scoped
stable-ABI hook changes only each existing encyclopedia image's destination
width/height/Y. It never changes source, UV, visibility, event handling, z-order,
or parent; it never spawns overlays or calls the face-icon helper. Absolute
sizes are idempotent and re-applied after search/filter rebuilding:

| Hero | Image layout | Opaque body Y | Body height | Tier clearance |
| --- | --- | --- | --- | --- |
| Yone | 63.75×69.75, bottom=76 | 7.375–64.375 | 57 | 5.625 |
| Xayah | 40.5×69.75, bottom=76 | 7.375–65.875 | 58.5 | 4.125 |

Both lose zero source pixels in the verified native crop model. Every other
champion camera and all compact `face` cameras are unchanged. The historical
Yone BP-stage approximation is isolated from this gate; it is not live proof.

## Yone gait — unresolved

The authored motion source largely keeps one knee folded back. The 0.12.14
lower-body half-cycle mirror changes support side numerically but is not a
coherent natural full-body run cycle. Do not call that visual quality fixed.
An identity-preserving ImageGen request for a new complete eight-pose cycle
failed with HTTP 404. No new art was produced or installed; no automatic CLI
fallback was authorized. No further procedural leg drawing/mirroring was added.

## BP illustrations — diagnosis, no BP modification

All 18 installed 284×172 blue/red hero illustrations exist and exactly match
the repository manifest hashes; only `lol_mod` is enabled. Current game logs
reach `asset loading done!`. This is not evidence of a missing image package.

`sync_bp_pick_container` reads `done.name` and feeds it to
`bp_champion_id_from_name`. In the bundled **0.5.8** `blue_pick_slot` layout,
`done.name` is the left-side athlete label; the hero is in the distinct
`done.champion.icon` node and has no champion-name label there. Thus an athlete
such as Oner/Faker cannot match Yone/Shen/etc. The shared function leaves the
illustration hidden for all nine heroes, explaining the roster-wide failure.

A repair must obtain the picked champion identity from the real draft state or
resolved actor asset, not the athlete label. It must then verify nonzero layout
and successful texture resolution **before** hiding the native actor. Existing
spawn/property boolean return values are not visual proof (earlier encyclopedia
probes returned true while the spawned image remained 0×0). The current request
asked to investigate the cause, so this change does not alter BP behavior.

## Validation record

- Native UV/layout regression, old-input failure and source-ownership tests added.
- Stable ABI 8 DLL compiled successfully. Full asset build completed.
- `pytest -q`: **227 passed**; includes the static mod validator and new UV tests.
- `validate_yone_v7.py`: 67-frame structural/atlas contract passes; this is not
  acceptance of natural-looking motion.
- Installed **0.12.15**, 468/468 files hash-identical with the runtime manifest;
  no extra runtime files. Only `lol_mod` enabled.
- Previous installed package and mods config backed up under
  `mod_backups/lol_mod_pre_0.12.15_20260905` before replacement.
- No game was launched, no user save/custom database modified, and no BP code
  changed for this investigation. Real encyclopedia/filter/scroll/BP rendering
  still needs current target-visible game evidence.
