# TeamFightMange2-mod

《团战经理 2》的 League 风格英雄模组，当前模组目录为 `mods/lol_mod`。

## v0.3.0：卢锡安同 ID 重做官方 002

- 使用官方支持的同 ID 数据英雄机制，以 `archer` 覆盖官方英雄 002，保留原有排序、引用和存档兼容性。
- 技能组为被动圣光银弹、Q 透体圣光、E 冷酷追击、R 圣枪洗礼；没有 W，也不再调用弓箭手的硬编码动作。
- Q/E/R 后，下一次普攻在第 4、10 tick 发射两发子弹，伤害分别为 100% 和 45% 攻击力。
- v10 角色模型由 image-gen 在统一 7×3、21 帧序列上重绘双眼脸型；待机、九帧交叉步跑动、单枪/双枪攻击、Q/E/R、受击和死亡均使用同一角色设计，不再混用旧跑步模型。运行时以 35 像素身高打包，保证两只眼在同一行分别保留一个独立亮像素。
- Q 使用 image-gen 生成的 v3 金白八帧光束，直接嵌入以角色中心为翻转轴的 192×64 施法帧；伤害独立使用瞬时固定直线区域，因此光束从枪口出现、不会追踪、不会往身后释放，并与青色平 A 明显区分。
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

本模组为同人作品。League of Legends、Shen、Lucian 及相关原始音频素材归原权利人所有；模型、图标和 VFX 是为本模组生成的原创像素素材。
