# PR11 0.12.14: encyclopedia ownership and Yone support-foot repair

Date: 2026-09-04. Target: base 0.5.8, stable ABI 8.

## Scope and evidence

- User-reported failures: Yone/Xayah encyclopedia images become blank, and Yone appears to move with one fixed or floating leg.
- Installed version before this repair was 0.12.13. Its last encyclopedia telemetry claimed `bound=true`, `positioned=true`, and `visible=true`; the user's screenshot still showed empty cards. API return values are therefore not accepted as rendered-image proof.
- Finished installed Silver and Touhou mods use the stock champion-info image route. This repair removes all encyclopedia traversal, image rebinding, resize, visibility and overlay code from the compiled stable runtime. It does not override the stock champion-slot template.
- Both champion definitions, matching sheet/animation mappings, and individual `champion_view` cameras remain in the runtime closure. Offline fullbody PNGs and experimental champion-info templates are excluded.

## Run repair

- Keep the approved Yone model, native eight-frame timing/boxes and each frame's authored upper body and sword pixels.
- Use grounded authored lower-body phases 4/5/6/7 for the first half-cycle, with whole-patch horizontal mirrors for the second. No drawn substitute legs, resizing, shear, alpha blending or extra sword pixels are added by this repair.
- Native game facing remains the sole world-direction mirror. No new direction animation rows or runtime movement controls were introduced.
- Independent final-PNG tests require both lower-body halves to have real pixel density, four changing phases per half-cycle, exact mirrored phase pairs, alternating 4/4 support, and ground contact in every frame. The floating-by-one-pixel negative test must fail. Each sword must remain a single connected component.

## Verification

- Native DLL build against the installed 0.5.8 stable SDK: passed; required ABI 8.
- `cargo fmt -- --check` and `cargo check --locked`: passed.
- Full repository pytest: 225 passed.
- Pack validator: passed; 353/353 override targets discoverable.
- Yone V7 validator: passed; 67 frames and 8px offline card-divider clearance.
- Runtime installation uses the exact manifest and verifies all file hashes. Previous installed package and enabled-mod config are backed up outside the active mod directory.
- No skill data, saves or custom database were changed. The game was not launched or operated for this repair.

## Acceptance boundary

This is an installed repair candidate, not a claimed live visual pass. The next real game session still needs to confirm both encyclopedia cards are visible at normal size and that Yone's full run loop looks coordinated in both directions. An offline pixel gate or contact sheet cannot substitute for that evidence.
