# Urgot W/R runtime QA

## Diagnosed regressions

- The target-bound lifecycle pass added a Rust channel table, native cancel
  hook, per-pulse shot marker and target-handle validation to a skill whose
  projectiles already support engine-native automatic targeting. Live builds
  either stopped the sequence early or stalled battle progression.
- A later replacement shortened the parent action to 22 ticks while retaining
  callbacks through tick 221. Extending the parent to 240 ticks fixed that
  lifetime mismatch, but the target/native/SwitchByBuff stack still reproduced
  the stall at champion level one. E was not learned and is excluded.
- Generic `Option::unwrap(None)` messages also exist before Urgot and during
  startup, so they are not used as a skill-specific stack trace.

## Safe W contract

- W is again a pure data-driven self-cast: `casting_type=None`,
  `casting_target=AllyOnlySelf`, and no W native Rust effect or shared channel
  state.
- Its 240-tick cancelable parent action owns twelve direct
  `AutoTargetProjectile` rounds at ticks `1, 21, ... 221`. The maximum delayed
  tick is strictly less than the parent duration.
- W has one eight-tick opening pose, no per-shot body animation, no
  `BlockAttack`, no shot-ready marker and no `SwitchByBuff` wrapper. The actor
  can move for the whole action.
- AI only promotes W from a real engine-selected Attack target, but casts W as
  `InputTarget::None`. Therefore it does not start in an empty camp. R is
  checked first; because W is cancelable, replacing it with R cancels the
  parent action and its owned delayed rounds.
- R removes `lol_urgot_w_purge` before its cast SFX. E retains the first
  reviewed rush-behind/flip data contract unchanged.

## Automated gates

- `tests/test_urgot_mod.py` locks the self-cast shape, exactly twelve direct
  auto-target rounds, `max(Delayed.tick) < duration`, one opening animation and
  the total absence of every W Rust channel/cancel/shot-gate symbol.
- The same test requires the AI's R-before-W order and the self-cast
  `InputTarget::None`, while recall and movement pass through unchanged.
- `tests/test_urgot_visual.py` keeps the approved compact W projectile and
  impact tags and forbids the rejected body-centred cannon overlay.

Live acceptance requires a fresh restarted battle: confirm all twelve rounds
fire without freezing or body stutter; clear or leave a jungle camp and confirm
Urgot walks normally; then confirm a legal R replaces W without late rounds.
