# Shen skill contract QA

| Design target | Engine slot | Runtime contract | Status |
| --- | --- | --- | --- |
| Basic attack / 忍刀斩 | `attack` | 25,000 range; 100% AD; official Shen cast + hit SFX | implemented |
| Q / 暮光斩 | `skill` | selects one enemy champion for refined-AI safety, then fires the same penetrating 60,000 line projectile in that direction; 40 + 60% AP magic damage; 25% slow for 90 ticks; 120 self shield for 120 ticks on hit | implemented |
| W / 灵佑领域 | `skill2` | 35,000 caster-centered field; allies receive 150 + 40% AP shield for 150 ticks; enemy champions receive -30% attack speed for 120 ticks | implemented approximation |
| R / 慈悲度魂落 | `ult` | `AllyNotSelf` target; 900 + 80% AP shield for 180 ticks; 48-tick delay; real `Teleport`; 35,000 arrival radius; 45-tick `Taunt` | implemented approximation |

Named state proof:

- `lol_shen_twilight_assault_slow`
- `lol_shen_twilight_assault_guard`
- `lol_shen_spirit_refuge_shield_window`
- `lol_shen_spirit_refuge_as_slow`
- `lol_shen_stand_united_channel`
- `lol_shen_stand_united_shield_window`
- `lol_shen_stand_united_arrival_cc`

Documented limits:

- TFM2 exposes three active skill slots; Shen's E identity is folded into R's arrival taunt.
- W uses real ally shields plus enemy attack-speed reduction instead of exact basic-attack blocking.
- `AllyNotSelf` uses the built-in AI target score. The public data/API surface has no `LowestHpAlly` target, so the build does not claim that R always selects the absolute lowest-health ally.
- The public data champion format has no verified level-unlock field, so R is not advertised as a level-5-only unlock.
