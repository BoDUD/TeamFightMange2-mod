# Lucian native-002 skill contract

Lucian intentionally occupies the original `archer`/002 action contract:

- Basic attack: 620 range, 100% Attack, native `archer_attack` event remapped to Lucian audio.
- E / native `skill`: 300-range directional dash followed by a 45% Attack shot at the most recently attacked enemy.
- Q / native `skill2`: nearby targeted shot for `55 + 85% Attack`; native brief interruption remains and the old Archer backstep is disabled with zero move range.
- R / native `archer_ult`: stationary, interruptible 15-shot channel; each shot deals `8 + 18% Attack`, with 1200 range and 45 hit radius.

This native replacement is deliberately different from the removed additive `lol_lucian` data-champion implementation: visibility and registration use the same official 002 path as the base game.
