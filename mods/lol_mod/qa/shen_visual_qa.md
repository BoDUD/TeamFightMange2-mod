# Shen visual QA

| Surface / ability | Source route | Result |
| --- | --- | --- |
| Actor model | accepted built-in image-gen 4x3 high-resolution character anchor, chroma-keyed and uniformly packed to 64x64 frames at the current Shen battle scale | x/y scale remains identical for every source pose; no actor-model or terrain-envelope change is part of the Q/E rework |
| Idle/run/attack | accepted actor anchor plus accepted 3x3 run refinement | unchanged; nine unique run phases and stable foot baseline |
| Q | existing separate spectral-blade sheet, repacked into independent `outbound`, `return`, `empowered_hit`, `through_hit`, and `pass_through` tags | distinct moving soul-blade trace; the outbound pass is non-damaging, while the visible return path can upgrade only the unused attacks once per cast |
| E | accepted built-in image-gen 3x2 source: three cyan-violet dash-wake phases plus three taunt-impact phases, additionally exposed through `trail_pre/loop/remove` and `taunt_pre/loop/remove` tags | distinct; the caster-follow trail lasts for the dash window, the hit flashes separately, and the 90-tick marker sustains the taunt read without restoring W's refuge circle |
| R | existing separate target shield / teleport arrival sheet | distinct; arrival visual no longer carries an unrelated taunt |
| Skill icons | independent Q source, new E dash/taunt source, independent R source, ordered Q/E/R | distinct |
| UI surfaces | accepted high-resolution idle source, never the reduced battle atlas | unchanged; encyclopedia, side-list, scoreboard, BP-grid and side-card routes remain independent |

Accepted E generation records:

- Icon: `exec-50b58747-dec1-41d1-9494-f321d174200f` -> `source/imagegen/shen_e_icon_source.png` -> `source/processed/shen_e_icon_source_alpha.png`.
- VFX: `exec-7537fd9a-649e-4628-b972-8cabb7ea6505` -> `source/imagegen/shen_e_vfx_contact.png` -> `source/processed/shen_e_vfx_contact_alpha.png`.
- Both sources used the built-in image generation path and the installed chroma-key helper; no code-drawn body or VFX substitute is accepted.

Acceptance rule: Q, E and R must remain visually distinguishable at native scale. The active `lol_shen.data_champion` must route Q through `lol_shen_twilight_assault_blade_outbound` and its owned `lol_shen_twilight_assault_blade_return`, route E through the independent trail/impact/taunt markers, reference `shen_q`, `shen_e`, and `shen_r`, and contain neither `shen_w` nor the old refuge-field view name.
