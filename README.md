# TeamFightMange2-mod

《团战经理 2》的 League 风格英雄模组，运行时目录为 `mods/lol_mod`。

## v0.3.0：卢锡安同 ID 重做官方 002

- 卢锡安使用官方 0.5.0 支持的同 ID 数据英雄重做机制，ID 为 `archer`，保留原版 002 的百科顺序、BP、存档与补丁引用。
- 战斗逻辑不再调用弓箭手硬编码：技能槽固定为 Q（透体圣光）、E（冷酷追击）和 R（圣枪洗礼），没有 W。
- 圣光银弹在 Q/E/R 后强化下一次普攻，首发后 0.1 秒追加一发 45% 攻击力的独立圣光弹。
- 同步重做英雄数值、三语文本、模型动画、头像偏移、Q/E/R 图标与音效事件。
- 模型、跑动、Q/E/R 图标以及普攻/Q/R 特效素材来自 image-gen，并保留生成来源和 SHA-256 审计记录；E 按反馈仅保留位移，不生成释放特效。
- 普攻、E、Q、R 音效从本机 League of Legends 的 Lucian Base Wwise 资源提取。
- v0.3 使用独立的清晰脸部像素模型、九帧双枪前倾冲刺、普攻青蓝圣光弹、枪口发出的金白 Q 光束和 R 子弹；这些视觉源均由 image-gen 生成。

## v0.1：慎

- 慎以独立数据英雄 `lol_shen` 注册。
- 模型、Q/W/R 图标和特效素材来自 image-gen。
- 攻击与技能音效从本机 League of Legends 的 Shen Base Wwise 资源提取。

## 构建与验证

```powershell
python -m pip install -r .\requirements-dev.txt
python .\mods\lol_mod\tools\build_lol_mod.py
python .\mods\lol_mod\tools\validate_lol_mod.py
python -m pytest -q
```

## 安装到本机游戏

安装脚本会同步运行时文件，并将 `config/game/mods.json` 设为仅启用 `lol_mod`：

```powershell
powershell -ExecutionPolicy Bypass -File .\mods\lol_mod\tools\install_lol_mod.ps1
```

本模组为同人作品。League of Legends、Shen、Lucian 及相关原始音频素材归其权利人所有；模型、图标和 VFX 是为本模组生成的原创像素素材。
