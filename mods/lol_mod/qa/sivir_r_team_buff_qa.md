# Sivir R team-buff QA

Static contract:

- Trigger target: enemy champion within 85000.
- Effect origin: around caster.
- Ally radius: 100000.
- One `AllyChampion` range effect.
- One +25% Move Speed buff for 300 ticks.
- No damage, shield, CC, or second self-only buff.
- Cast sound remains outside the per-ally effect and therefore plays once.

Live acceptance checklist:

- R does not fire while completely out of combat.
- Sivir and nearby allied champions each receive one buff.
- Enemies, minions, and towers receive no buff.
- The low speed arcs stay behind/below actor feet and disappear after the buff.
- Orianna + Sivir and Briar + Sivir movement-speed combinations remain readable and do not create stuck pursuit behavior.
