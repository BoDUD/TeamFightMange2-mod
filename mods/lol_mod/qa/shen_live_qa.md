# Shen live QA

Static/build checks are automated. These live checks are release gates:

- [x] Game log reaches `asset loading done!` with no data champion, asset, or sound errors.
- [ ] Shen is visible in encyclopedia/draft with the correct localized name and Q/E/R icons.
- [ ] Card, weekly report, scoreboard, side list, and battle HUD show a readable full-body/compact portrait.
- [ ] A current battle screenshot visibly contains Shen; draft telemetry alone is not accepted.
- [ ] Idle, run, attack, Q, E, R, hit, and death animations play without scale jumps or terrain clipping.
- [ ] Q is not cast at match start or into empty space; the stock AI waits until a valid enemy champion is within 550 range before choosing the direction cast.
- [ ] Q first sends one invisible, no-damage `lol_shen_twilight_assault_blade_anchor` to establish the selected enemy-side endpoint. Only `lol_shen_twilight_assault_blade_recall` is rendered: the cyan spirit blade must visibly travel from that endpoint back to Shen, flash on arrival, then grant exactly three normal 20 + 20% AP empowered attacks.
- [ ] `lol_shen_twilight_assault_empowered_window` keeps a clear foreground spirit-blade/weapon glow on Shen from recall arrival through the first and second empowered attacks, then disappears with the third attack or the shared 480-tick timeout. Q has no fabricated visible outbound blade, pass-through upgrade, slow, or attack-speed branch.
- [ ] E visibly covers the chosen 600-distance direction, can cross multiple enemy champions, and each crossed champion takes one hit plus a true 1.5-second forced-target taunt toward Shen.
- [ ] E shows the foreground `lol_shen_shadow_dash_cast_flash` immediately on cast, followed by the bright cyan 30-tick caster-follow wake, separate hit flash, and persistent taunt marker/built-in CC read. The old W refuge circle never appears from the active second slot.
- [ ] Repeated AI matches include E casts when enemy champions can be crossed. `lol_shen_shadow_dash_ai_hint_native` must remain apply-time no-op while reporting exactly 90 ticks of expected CC at the action root; only the Rush collision's `lol_shen_shadow_dash_taunt_native` may apply the real taunt.
- [ ] R applies the shield before the 0.8-second teleport and does not taunt enemies on arrival.
- [ ] Multiple unequal-health ally scenarios record which ally the built-in `AllyNotSelf` AI selects; do not upgrade the lowest-health claim without repeated proof.
- [ ] Official attack/Q/R audio is audible and correctly timed; E currently reuses the verified attack cast/hit events and must not trigger the retired W events.

Latest automated startup smoke: 2026-07-10 09:18 JST, after the canonical cross-platform asset encoding pass. The game reached `asset loading done!` with zero Shen/`lol_mod` errors and zero panic/fatal lines. The remaining `network asset load error: UnexpectedEof` default-banpick fallback and Workshop item 3736031680 warning are unrelated to this mod.
