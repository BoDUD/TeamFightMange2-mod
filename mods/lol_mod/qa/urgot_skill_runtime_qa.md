# Urgot W/E/R runtime QA

## Latest reproduced freeze: 2026-07-14 15:25

- In a fresh live battle, Urgot reached first contact at match time `00:25` and
  battle simulation stopped again. `log.log` added exactly three new panics:
  `15:25:40.948056300`, `15:25:41.007559900`, and
  `15:25:41.022697400`, each `called Option::unwrap() on a None value`.
- The window remained responsive and the process continued rendering. Repeated
  post-failure stack samples did not leave a thread inside `lol_mod.dll`; busy
  samples were in `TeamfightManager2.exe`, and idle samples were in OpenGL
  `SwapBuffers`. This is a simulation abort after caught panics, not evidence of
  a permanent loop inside the mod DLL.
- The captured diagnostic dump is
  `tfm2_urgot_freeze_20260714_152541_thread.dmp`. It is local diagnostic
  evidence and is not a shipped mod artifact.

## Native/API audit conclusions

- Exact Mod API 0.8 rustdoc shows that `Input::Attack` contains a generic
  `InputTarget`, whose variants are `Target`, `Dir`, `Pos`, and `None`. The
  retired `UrgotAbilityInputGate` accepted any stock `Attack` target and passed
  it unchanged to targeted `Input::Ult` and `Input::Skill` validity checks.
  `PlayerAiContext::is_valid_input` forwards directly to the game and adds no
  target-variant or entity-existence guard. This gives the engine a direct
  `Option::unwrap(None)` path at first contact. The whole Urgot input gate is
  therefore removed, including its registration; merely removing source-Attack
  validation is not sufficient.
- `ModEffectType::on_caster()` means that an effect fires at the caster's
  position. It does not mean that a delayed native callback receives its caster.
  The retired W native used `on_caster=true` for the wrong reason.
- `GameCtx::entity_count/entity_at` form a finite enumeration and the audited
  SDK wrappers match their declared ABI. No W mutex exists, and the passive
  releases its mutex before damage, so neither an obvious enumeration loop nor
  a W lock deadlock was found.
- `GameCtx::deal_damage` forwards raw attacker/target IDs to the game without an
  atomic validity guarantee. Calling it after custom enumeration from a delayed
  native callback remained an unnecessary re-entry/lifecycle risk.
- `DelayedEffect::apply` clones its child effect list into scheduler-owned
  storage. The old belief that a 240-tick parent action was required to keep a
  tick-221 callback alive is not supported by the engine implementation.
- The rejected W was also the only combined-mod action using the risky mixture
  `duration=240`, `cancelable=true`, `can_use_with_move=true`, and twelve delayed
  callbacks while an input AI repeatedly promoted stock attacks. Even without a
  single proved infinite loop, that lifecycle is no longer accepted.

## Remaining native-effect lifecycle hardening

- `lol_urgot_passive_native` is evaluated after the engine-owned base `Attack`
  in the projectile hit payload. That attack can already kill/remove the target,
  and retaliation or combat resolution can invalidate the caster. The callback
  now reacquires the caster handle, Attack stat and alive state in one snapshot,
  and the target maximum HP and alive state in a second snapshot. It returns
  before touching the passive cooldown table or calling `deal_damage` unless
  both entities still exist and are alive (and target max HP is non-zero).
- `lol_urgot_r_check_native` now confirms that the caster still exists and is
  alive after the target threshold check and immediately before adding the
  short `lol_urgot_r_execute_ready` marker.
- `lol_urgot_r_execute_native` now confirms a live caster before lethal damage,
  then reacquires and confirms the caster again after target death is verified
  and before adding `lol_urgot_r_execute_success`. A dead or removed caster can
  no longer be passed to either `deal_damage` or `add_buff` by these callbacks.
- This is a lifecycle-only guard pass. Passive/R damage values, cooldowns,
  target threshold, effect order, VFX/SFX and skill-selection behavior are
  unchanged. W, E displacement and all Yone paths are outside this change.

## Rejected live routes

- Rust channel table, native cancel hook, shot-ready marker, target handle, and
  `SwitchByBuff`: stopped early or stalled.
- Twelve `AutoTargetProjectile` hits: new unwrap panics and a freeze near
  `00:30`, even after the hit payload was reduced to one `Attack`.
- Explicit source `Attack` validity inside the AI gate: three pre-contact unwrap
  panics around `00:03`.
- Targeted `AddCasted/Bleed`: unrelated white presentation and a freeze around
  `02:22` without a new panic.
- Direction plus twelve delayed `LinearProjectile` shots: battle stopped near
  `00:43` while CPU stayed high.
- Twelve delayed caster-owned native pulses with
  `entity_count/entity_at/distance_sq/deal_damage`: the latest first-contact
  failure at `00:25` with three unwrap panics.

## Crash-safe fallback contract (live-stability accepted)

- W remains `action_name=attack`, `cooltime=600`, `range=60000`,
  `casting_type=Targeting`, and `casting_target=EnemyWithoutTower`. It now uses
  `duration=16`, `start_timing=1`, `cancelable=false`, and
  `can_use_with_move=false`.
- The former twelve shots' total listed damage is compressed into exactly one
  engine data `Attack`: `damage=96`, `attack_ratio=240`. This is a deliberate
  stability fallback, not a claim that the presentation still reproduces LoL's
  rapid-fire cadence.
- The effect tree contains only one `lol_urgot_w_cast` SFX, one
  `lol_urgot_w_shot` SFX, one 240-tick `lol_urgot_w_purge` self buff, and the
  single data `Attack`. The buff keeps Move Speed `-12%`, Defence `+20`, and
  Magic Resistance `+10` for four seconds.
- W contains zero `Delayed`, `Native`, projectile, `RangePeriod`, `AddCasted`,
  actor animation, caster/target view effect, target-side SFX, or body-covering
  view buff. Its old cannon projectile/impact bindings remain unreachable.
- Rust contains no `UrgotAbilityInputGate`, `UrgotWPulseNativeEffect`, W native
  constants, `lol_urgot_w_pulse_native` registration, or W native effect ref.
  Stock engine data AI owns W target selection and action validity.
- Five-language text describes one stable compressed hit on a legal non-tower
  enemy for `96 + 240% Attack` physical damage and the four-second self buff. It
  does not claim twelve shots, target reacquisition, or movement while casting.
- R still removes `lol_urgot_w_purge` before launch and is otherwise unchanged
  by this stabilization pass.

## E flip correction (pending fresh live acceptance)

- The user confirmed that E casts, but the victim was not visibly thrown behind
  Urgot. The retired arrival order was `Attack -> Native Stun -> Knockback`.
  Applying a hard Stun before the movement effect is the strongest structural
  explanation for the victim remaining at its contact position.
- E keeps its existing targeted `EnemyChampion`, `transform`, shield and
  `RushMoveToBack(speed=4500)` contract. The rush still carries Urgot beyond the
  selected target; only its arrival payload changes.
- Arrival is now fully engine-owned data in this exact order:
  `Attack(70 + 90% Attack) -> Knockback(speed=2600,tick=8) -> Airborne(60) ->`
  impact VFX/SFX. This combines the already-used Yone back-cross primitive with
  the Kled/Briar `Knockback -> Airborne` displacement order.
- E contains no `Native`, `Delayed`, `Grab`, custom position write, entity scan,
  stored target handle or new AI gate. `UrgotENativeEffect`,
  `URGOT_E_STUN_TICKS` and the `lol_urgot_e_native` registration are removed.
  W and R data are not part of this correction.

## Automated gates

- `tests/test_urgot_mod.py` locks the exact short targeted action, the one data
  `Attack`, the two SFX cues, the 240-tick self buff, and the total absence of
  delayed/native/projectile/overlay routes. It also requires complete removal of
  the Urgot input gate and W native implementation/registration. It additionally
  locks the passive's alive snapshots before cooldown/damage, the R-check caster
  guard before its marker, and both R-execute caster guards around lethal damage.
- `tests/test_yone_mod.py` and `validate_lol_mod.py` delimit the independent Yone
  gate with the following Urgot passive constants, because the Urgot gate no
  longer exists.
- `validate_lol_mod.py` independently enforces the final data, Rust, runtime
  binding, five-language W copy, exact pure-data E arrival order, and native
  lifecycle-guard ordering for full-pack builds.

## Live acceptance status

- After a fresh process restart, a battle containing both Urgot and Yone
  progressed through `07:02`, well beyond every earlier `00:25`–`02:22` stall
  point. The window stayed responsive, combat continued, and the current
  `log.log` contained zero panic entries. The user also confirmed that W now
  behaves normally. This accepts the W stability route and the removal of the
  rejected machine-gun body overlay; extended manual balance/presentation
  review remains welcome.
- Exact E rear-placement remains a manual acceptance item because overlapping
  units made the captured sequence inconclusive. A visible cast must show Urgot
  crossing the target, the victim travelling away from Urgot during the
  eight-tick knockback and finishing on Urgot's rear/origin side, after which
  both units resume normal simulation.
- Repeat E once near open terrain and once near a wall; a lethal E hit must also
  end without a delayed callback, stuck CC state or new log panic.
