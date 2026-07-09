# TeamFightMange2-mod

这个仓库目前提供一个可独立安装的《团战经理 2》数据英雄模组：`lol_mod`。

## v0.1：暮光之眼·慎

- 新增唯一英雄 ID `lol_shen`，不会覆盖原生 Android。
- Q「暮光斩」：穿透灵刃、魔法伤害、减速、命中后自盾。
- W「灵佑领域」：范围友军护盾、敌方攻击速度降低。
- R「慈悲度魂落」：远距离友军护盾、0.8 秒后传送、落地嘲讽。
- 模型、Q/W/R 图标和 Q/W/R 特效均由内置 image-gen 生成，并保留原图、最终提示词和 SHA-256 审计记录。
- 攻击、Q、W、R 音效直接从本机 League of Legends 的 Shen Base Wwise 资源提取，并保留 Riot 事件名、media ID、WEM/WAV 哈希。

当前公开数据英雄接口不能静态保证 R 永远选择绝对最低生命值友军；首版使用引擎的 `AllyNotSelf` 目标评分，限制已写进中英文技能文案和 QA。

## 构建与验证

```powershell
python -m pip install -r .\requirements-dev.txt
python .\mods\lol_mod\tools\build_lol_mod.py
python .\mods\lol_mod\tools\validate_lol_mod.py
python -m pytest -q
```

## 安装到本机游戏

安装脚本只同步运行时目录，不会把 image-gen 原图、QA 图或工具复制进活动模组目录；同时会把 `config/game/mods.json` 调整为只启用 `lol_mod`。

```powershell
powershell -ExecutionPolicy Bypass -File .\mods\lol_mod\tools\install_lol_mod.ps1
```

## 从本机 LoL 重新提取 Shen 音效

提取脚本会先校验当前 `Shen.wad.client`、内部 BNK 和每个 WEM 的固定哈希，再调用 `vgmstream-cli` 解码成 44.1 kHz 单声道 16-bit PCM WAV。

```powershell
python .\mods\lol_mod\tools\extract_shen_audio.py `
  --wad "D:\Riot Games\League of Legends\Game\DATA\FINAL\Champions\Shen.wad.client" `
  --vgmstream "C:\path\to\vgmstream-cli.exe"
```

这是非商业同人模组。League of Legends、Shen 及相关音效归其权利人所有；仓库中的角色模型、图标和 VFX 是为本模组生成的原创像素素材。
