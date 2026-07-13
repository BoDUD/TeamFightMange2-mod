# Urgot W/R runtime QA

## Diagnosed causes

- The first W data contract used `casting_type: None` together with
  `casting_target: None` and a non-zero action range. Every proven self-cast
  action in this mod (Shen W and Sivir E) uses `None + AllyOnlySelf + range 0`.
  The original combination gave the stock Demon AI no valid self target, so it
  could continue basic-attacking without selecting Purge.
- The supplied battle evidence shows Urgot at level 2 and level 4. The third
  active slot is learned at level 5, so those captures cannot prove an R cast
  failure. The R projectile/pull/execute tree remains a level-5 action.
- The old basic attack was instant damage, and W only bound its projectile
  tag. The generated attack sheet and W `muzzle`, `impact`, and sustained buff
  phases were therefore unreachable even if damage occurred.

## Runtime contract after the fix

- Urgot is a ranged champion. His basic attack is a real
  `TargetProjectile` with caster muzzle, travelling projectile, target impact,
  official cast/hit audio, and Echoing Flames on the projectile hit.
- W is `None + AllyOnlySelf + range 0`; its 240-tick Purge buff has a
  `ThreePhase` presentation, and each of the twelve 20-tick shots has exactly
  one muzzle and one impact event.
- `UrgotAbilityInputGate` only promotes an ordinary Demon attack to R, then W,
  when `PlayerAiContext::is_valid_input` accepts that action. Level, cooldown,
  range, crowd-control and target legality therefore remain engine-owned.
- R retains its non-piercing directional projectile, delayed pull, 25% execute
  recheck and success-only fear, with an explicit caster launch effect.

## Automated gates

- `tests/test_urgot_mod.py` checks the self-cast tuple, one muzzle/impact per W
  shot, the ranged basic projectile, R launch/pull/execute, Native registrations
  and the legality-gated AI priority.
- `tests/test_urgot_visual.py` checks that every referenced animation tag is
  present in the generated effect contracts.
- `mods/lol_mod/tools/build_native_dll.ps1` compiles the AI and Native effect
  chain against Mod API 0.8.

Live acceptance still requires a fresh battle capture with Urgot at level 5 or
higher, showing one W channel and one R launch/hit. A level-4 capture is not R
evidence.
