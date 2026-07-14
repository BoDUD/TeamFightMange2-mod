# Shen live QA

Static/build checks are automated. These live checks are release gates:

- [x] Game log reaches `asset loading done!` with no data champion, asset, or sound errors.
- [ ] Shen is visible in encyclopedia/draft with the correct localized name and Q/E/R icons.
- [ ] Card, weekly report, scoreboard, side list, and battle HUD show a readable full-body/compact portrait.
- [ ] A current battle screenshot visibly contains Shen; draft telemetry alone is not accepted.
- [ ] Idle, run, attack, Q, E, R, hit, and death animations play without scale jumps or terrain clipping.
- [ ] Q recalls the spirit-blade visual without launching a damage projectile, then exactly three basic attacks consume charge 3 -> 2 -> 1 and receive the magic-damage hit visual.
- [ ] E visibly dashes in the chosen direction, can cross multiple enemy champions, and each crossed champion takes one hit plus a 1.5-second taunt.
- [ ] E uses the new compact dash wake / taunt impact; the old W refuge circle never appears from the active second slot.
- [ ] R applies the shield before the 0.8-second teleport and does not taunt enemies on arrival.
- [ ] Multiple unequal-health ally scenarios record which ally the built-in `AllyNotSelf` AI selects; do not upgrade the lowest-health claim without repeated proof.
- [ ] Official attack/Q/R audio is audible and correctly timed; E currently reuses the verified attack cast/hit events and must not trigger the retired W events.

Latest automated startup smoke: 2026-07-10 09:18 JST, after the canonical cross-platform asset encoding pass. The game reached `asset loading done!` with zero Shen/`lol_mod` errors and zero panic/fatal lines. The remaining `network asset load error: UnexpectedEof` default-banpick fallback and Workshop item 3736031680 warning are unrelated to this mod.
