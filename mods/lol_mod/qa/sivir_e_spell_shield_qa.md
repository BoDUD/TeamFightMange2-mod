# Sivir E Spell Shield QA

The released public-data approximation is a short skill-damage guard, not a claim of exact League one-spell consumption.

- `lol_sivir_spell_shield_window`: 90 ticks, 100% skill-damage reduction.
- `lol_sivir_spell_shield_speed`: 120 ticks, +20% Move Speed.
- One immediate heal: 60 + 15% Attack.
- One official buff-activation SFX.
- One compact three-phase visual with hollow center; no second character, opaque dome, or foot-covering effect.
- No Attack/ApAttack/FixedAttack/Shield payload exists.

Known limitation: public hooks cannot reliably distinguish, cancel, and consume exactly one incoming enemy ability or suppress its non-damage crowd-control payload. Exact parity requires a deeper mutable damage/skill event hook.
