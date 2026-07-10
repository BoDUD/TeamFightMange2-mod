# TeamFightMange2-mod

《团战经理 2》的 League 风格英雄模组，运行时目录为 `mods/lol_mod`。

## v0.2.2：卢锡安覆盖官方 002

- 卢锡安直接覆盖官方英雄 002（原生键 `archer`），因此会出现在原版弓箭手所在的百科、BP、阵容和比赛槽位。
- 不再注册额外的 `lol_lucian` 数据英雄；构建和测试会阻止该旧文件重新出现。
- 同步覆盖 002 的英雄数值、三语文本、模型动画、头像偏移、五个原生技能图标格和音效事件。
- 模型、跑动、Q/E/R 图标与特效素材来自 image-gen，并保留生成来源和 SHA-256 审计记录。
- 普攻、E、Q、R 音效从本机 League of Legends 的 Lucian Base Wwise 资源提取。
- 002 的原生技能执行器有限：E 使用原生位移后追射，Q 使用原生单目标射击并保留短打断，R 使用原生 15 发引导射击；文本明确描述实际效果。

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
