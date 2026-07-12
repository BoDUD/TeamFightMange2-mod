# Kled W four-hit state-machine QA

The second public active is labeled as the E UI slot to preserve this project's Q/E/R panel convention, but its gameplay mapping is Kled's original W, Violent Tendencies.

## Static contract

- [x] Casting `skill2` first removes every stale `lol_kled_violent_*` marker.
- [x] It adds `lol_kled_violent_haste` for 240 ticks with +60% Attack Speed and installs `lol_kled_violent_stage1` for the same window.
- [x] While haste is active, normal attacks advance stage 1 to 2, 2 to 3, and 3 to 4 one attack at a time.
- [x] Hits one through three use distinct `lol_kled_w_hit1`, `lol_kled_w_hit2`, and `lol_kled_w_hit3` audio/VFX events.
- [x] The stage-4 attack keeps the normal 100% AD attack and adds `20 + 35% AD + 4% target maximum HP` with `lol_kled_w_hit4` and `lol_kled_w_fourth_visual`.
- [x] The fourth hit removes haste and every numbered stage marker, so a fifth attack cannot reuse the bonus.
- [x] A delayed cleanup at tick 240 removes every remaining W marker if four attacks were not completed.

## Intentional approximation

League Kled's W is normally an automatic passive window. This three-slot release exposes it through the second active button so the four-hit sequence is controllable and testable. The UI title states that this is the W mapping rather than pretending it is a second Jousting implementation.

## Pending live checks

- [ ] The first three attacks show escalating but compact feedback and the fourth hit is clearly stronger without covering the target.
- [ ] Exactly four staged attacks occur even at high Attack Speed; no attack skips a stage or triggers two stage transitions.
- [ ] The target-maximum-HP bonus is applied only on the fourth staged attack.
- [ ] Finishing the fourth attack clears the speed/VFX state immediately; timing out clears it at 240 ticks.
- [ ] Recasting after cleanup starts a fresh stage-1 sequence with no stale stage or double fourth-hit event.
