# TeamFightMange2-mod

《团战经理 2》的 League 风格英雄模组，当前模组目录为 `mods/lol_mod`。

## v0.5.0：贝蕾亚同 ID 重做官方 004

- 通过 `champion/berserker.data_champion` 同 ID 覆盖官方 Berserker；不注册重复的 `lol_briar`，官方排序、引用和存档身份保持稳定。
- 仅保留三个主动槽：Q 血莽与一次噬击、E 固定蓄力惊吼、R 预警后的目标追击；没有第四技能槽。
- 血色诅咒由普攻、E 和 R 到达伤害施加，持续 120 tick、每 60 tick 造成 `4 + 3% AD` 物理伤害并为原施法者回复 `2 + 1% AD` 生命。
- 角色母版、九帧跑动、Q/E/R 图标、流血/狂暴/E/R 特效均由内置 imagegen 生成并保留原始来源；运行时保留原生 Berserker 的全部 24 个普通、狂暴和 R 分段动画标签。
- 普攻、狂暴普攻、Q、E、R 音效从本机 Briar Base Wwise bank 按固定事件、媒体 ID 和 SHA-256 提取。
- 数据版本无法实现强制狂暴目标、手动二段 W、按已损生命缩放、E 撞墙奖励或可放空的全图 R 弹体；游戏内文案明确说明这些限制。

## v0.4.1：奥利安娜同 ID 重做官方 003

- 以 `barrier_magician` 覆盖官方英雄 003，并在百科使用名称“奥利安娜”。
- 三个主动槽为 Q 指令：进攻与杂音、E 指令：防卫、R 指令：冲击波；魔偶使用非永久数据层近似。
- 模型、跑动、图标、平 A 与 Q/E/R 特效由 imagegen 生成；音效来自 Orianna Base Wwise 资源。

## v0.3.0：卢锡安同 ID 重做官方 002

- 使用官方支持的同 ID 数据英雄机制，以 `archer` 覆盖官方英雄 002，保留原有排序、引用和存档兼容性。
- 技能组为被动圣光银弹、Q 透体圣光、E 冷酷追击、R 圣枪洗礼；没有 W，也不再调用弓箭手的硬编码动作。
- Q/E/R 后，下一次普攻在第 4、10 tick 发射两发子弹，伤害分别为 100% 和 45% 攻击力。
- 当前角色模型和九帧跑动使用用户验收后的统一 v3/v2 素材，64×64 画布内与慎保持同一尺寸级别。
- Q 使用 imagegen 生成的 v3 金白八帧光束，以方向投射物从枪口前方发出；伤害沿锁定施法方向贯穿，不追踪目标。
- E 仅保留位移动作，不生成释放光效、拖尾或残影。
- 模型、技能图标、平 A/Q/R 特效均保留 image-gen 原始来源与 SHA-256 审计记录。
- 普攻、被动、Q、E、R 音效来自本机 League of Legends 的 Lucian Base Wwise 资源。

## v0.1：慎

- 以独立数据英雄 `lol_shen` 注册。
- 模型、Q/W/R 图标和特效素材由 image-gen 生成。
- 攻击和技能音效来自本机 League of Legends 的 Shen Base Wwise 资源。

## 构建与测试

```powershell
python -m pip install -r .\requirements-dev.txt
python .\mods\lol_mod\tools\build_lol_mod.py
python .\mods\lol_mod\tools\validate_lol_mod.py
python -m pytest -q
```

## 安装到本机游戏

安装脚本会同步模组并将 `config/game/mods.json` 设置为仅启用 `lol_mod`：

```powershell
powershell -ExecutionPolicy Bypass -File .\mods\lol_mod\tools\install_lol_mod.ps1
```

本模组为同人作品。League of Legends、Shen、Lucian、Orianna、Briar 及相关原始音频素材归原权利人所有；模型、图标和 VFX 是为本模组生成的原创像素素材。
