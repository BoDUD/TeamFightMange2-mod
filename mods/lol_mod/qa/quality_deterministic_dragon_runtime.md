# Deterministic elemental dragon runtime QA

## Implemented contract

- Each match selects exactly one base elemental dragon from `infernal`, `ocean`, `mountain`, `cloud`, and `hextech`.
- Elder Dragon is deliberately excluded from this normal-match pool.
- Selection is `SplitMix64(authoritative_match_seed) % 5`; it does not use process randomness, wall-clock time, or mutable global RNG state.
- The server sends the same versioned `running_id:set:seed` payload separately to both participating teams. Concurrent hidden matches therefore cannot overwrite another match through a broadcast.
- Live clients derive the asset locally from that server seed. Replay clients derive it from `MatchReplayData.seed`, so recorded matches reproduce the same variant.
- `post_update` stores the authoritative live/replay selection only. It never mutates `EntityView.view_name`: that field is consumed before the mod callback and is refreshed by the server on the next tick, which previously left every visible model on the default Infernal sheet.
- `post_render` is gated by the live/replay `MatchUIRunner` and rewrites final `RenderCommand::Sprite` texture keys from native/direct-mod `serpen#sheet` to `asset/lol_mod/aseprite_resources/ingame/dragon_variants/<selected>#sheet`.
- The five elemental sheets have the same 1861x226 canvas and byte-identical animation metadata. Reusing the native Serpen UV/timing contract while replacing only the final sheet therefore preserves attack and idle animation geometry.
- Until a valid seed is available, both sprite and text passes conservatively select Infernal Drake.
- Native objective notifications read `asset/base/text/ui`, not `asset/base/text/object`. The mod merges the correct Baron/Infernal fallback names there, then rewrites final `RenderCommand::Text` labels inside the same `MatchUIRunner` gate and from the same stored seed used by the sprite pass. This guarantees the visible model, in-match top notice, and event log agree on Infernal, Ocean, Mountain, Cloud, or Hextech Drake without leaking the previous match's element into management screens. Result-page dynamic naming remains a live gate because its runner lifetime is not exposed by API 0.8; its static labels still use the correct Baron/Infernal fallback rather than Morgard/Serpen.

This is visual per-match selection. The public API 0.8 surface does not expose a safe per-objective-respawn replacement hook, so this does not claim LoL's rotating drake sequence, Dragon Soul, or automatic Elder transition.

## Static asset routing

`mod.override_info` still exposes the five elemental sheet and animation assets. The runtime sprite rewrite uses direct `asset/lol_mod/...#sheet` keys, avoiding the native neutral-monster path prefix that made a relative `EntityView.view_name` unsafe. Elder assets remain available for future mechanics but are not selected by this runtime.

## Optional telemetry

Set `LOL_QA_DRAGON_VARIANT_TELEMETRY=1` before launching the game. The mod appends:

`ModData/lol_mod/quality_dragon_variant_runtime_telemetry.tsv`

Fields are timestamp, origin, running ID, set, seed, variant index, relative view name, and detail. Telemetry is disabled by default and contains no player data. A `render_apply` row is emitted only after at least one real Serpen sprite command is replaced; its detail records `old`, `new`, and `rewrite_count`.

Expected live sequence for both participants:

1. `server_select` has identical seed and view name.
2. `client_event` accepts the versioned authoritative seed.
3. `render_apply` resolves the same sheet when a real `serpen#sheet` sprite command appears.
4. Killing Baron displays the maintained locale's Baron Nashor name; killing the selected dragon displays the element matching the selected sheet rather than native Morgard/Serpen text.

Expected replay sequence:

1. `render_apply` records source `replay` in its telemetry detail column.
2. Its seed and sheet name match the original live match.
3. Replayed in-match objective notices use the same recorded element name.

Manual result-view gate:

- [ ] If the result graph is still hosted below `MatchUIRunner`, its dragon label matches the recorded element; otherwise it safely shows the maintained Infernal fallback and never native Morgard/Serpen text.

If a replay is opened before any public `MatchUIRunner`/`ClientDatabase` handle becomes available, the extension cannot reach replay metadata through API 0.8 and safely retains default `serpen`. Direct replay startup without that runner is therefore a documented manual QA gate rather than an unsupported global hook.

## Build validation

Compile with the game's API 0.8 SDK using `mod-sdk/build_mod_cargo.ps1`. Do not validate this code against the obsolete API 0.7 loader.
