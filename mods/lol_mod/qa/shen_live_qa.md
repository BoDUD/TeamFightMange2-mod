# Shen live QA

Static/build checks are automated. These live checks are release gates:

- [ ] Game log reaches `asset loading done!` with no data champion, asset, or sound errors.
- [ ] Shen is visible in encyclopedia/draft with the correct localized name and Q/W/R icons.
- [ ] Card, weekly report, scoreboard, side list, and battle HUD show a readable full-body/compact portrait.
- [ ] A current battle screenshot visibly contains Shen; draft telemetry alone is not accepted.
- [ ] Idle, run, attack, Q, W, R, hit, and death animations play without scale jumps or terrain clipping.
- [ ] Q projectile passes through enemies, slows, and grants Shen a shield only after a hit.
- [ ] W shields nearby allies and applies the enemy attack-speed debuff.
- [ ] R applies the shield before the 0.8-second teleport and taunts enemies on arrival.
- [ ] Multiple unequal-health ally scenarios record which ally the built-in `AllyNotSelf` AI selects; do not upgrade the lowest-health claim without repeated proof.
- [ ] Official attack/Q/W/R audio is audible and correctly timed in battle.
