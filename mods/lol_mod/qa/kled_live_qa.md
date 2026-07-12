# Kled live QA

Status: pending user testing of a fresh installed build. No item below is treated as passed by static files, tests, contact sheets, or telemetry alone.

Required identity: `LOL_QA_FORCE_CHAMPION_ID=17` (`cavalry_knight`). Project order 006 must not be used as the engine index.

- [ ] A fresh launch with only `lol_mod` enabled reaches `asset loading done!` with no Kled data-champion, animation, sound, sprite, duplicate-ID, panic, or fatal error.
- [ ] The encyclopedia finds Kled/克烈 and shows a centered complete mounted body from head through Skaarl's feet.
- [ ] Draft cards, BP side illustration, compact rows, scoreboard, reports, and battle HUD all show Kled's current model without crop, stale art, or temporary splash residue.
- [ ] Idle, run, attack, Q/E, mapped-W second slot, R, hit, and death stay in one stable mounted scale class.
- [ ] Run has clear stride and forward momentum without sliding, violent jitter, unexpected facing lock, terrain clipping, or name/HP-bar overlap.
- [ ] Normal attacks use Kled's intended cast/hit audio and do not leak Cavalry Knight native audio.
- [ ] The Q slot rushes in the selected direction, collides once, creates the visible tether, waits for the intended delay, then damages and pulls/binds the same target once.
- [ ] The Q delayed pull follows the documented data limitation: it does not cancel because the target moved beyond a second distance threshold.
- [ ] The second UI slot activates the original W mapping: four staged basic attacks occur within the window, the fourth has a stronger impact, and no fifth staged hit is produced.
- [ ] W stages clear cleanly after the fourth hit or the 240-tick timeout, with no permanent Attack Speed or lingering VFX.
- [ ] R follows one straight selected route, keeps Kled shielded/accelerated/CC-immune for the intended windows, and does not steer or home after cast.
- [ ] R's ground trail grants nearby allies the one refreshing speed buff without applying a second self-only trail buff.
- [ ] R stops on its first enemy-champion collision and shows the complete impact, damage, knockback, and Airborne response in either facing direction.
- [ ] Death shows exactly one mounted Kled/Skaarl defeated model, no duplicated rider/mount/weapon, and a clean terminal fade.

Always-mounted/no-remount, no second Q distance check, folded E-in-Q, mapped W-in-second-slot, and straight-route R are frozen data-layer limitations, not pending parity claims.
