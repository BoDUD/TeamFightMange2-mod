# Sivir Q return regression QA

Static gates require one outbound `LinearProjectile` whose own `end_effects` contain one `BackToCasterLinearProjectile`. Both passes are penetrating, exclude towers, own separate damage payloads, and bind distinct `out` / `return` animation tags and `q_out` / `q_return` official audio events.

Live acceptance checklist:

- Q leaves along the selected direction rather than homing to a stale target.
- The return spawns only at the outbound endpoint.
- Moving Sivir changes the practical return path and the blade still terminates.
- One enemy can take at most one hit per pass.
- Multiple enemies and minions are pierced without repeated per-tick damage.
- Towers are never hit.
- The held actor weapon is hidden while the Q blade is in flight; no double crossblade appears.
- Sivir dying during flight leaves no permanent projectile.
