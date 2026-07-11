# TeamFightMange2-mod

《团战经理 2》的 League 风格英雄模组，当前模组目录为 `mods/lol_mod`。

## v0.7.4：BP 实际卡槽资源与普通野怪可读性修复

- BP 插画不再只依赖 `MatchUIRunner` 快照；每帧同时读取卡槽 `done.champion.icon` 的真实 `ImageRunner` 资源，直接确定五个 LOL 英雄并显示对应插画。
- 加入限频 BP 运行时记录，可直接证明 runner、卡槽路径、实际头像资源与最终显示状态，避免再用静态结构代替实机结果。
- 绯红印记树怪、苍蓝雕纹魔像与三狼恢复更清晰的可见尺寸，同时继续保持每帧居中、脚底锚点和原生动画时长。

## v0.7.3：BP 递归定位与野怪尺寸校准

- BP 插画改为递归查找任意深度的 `MatchUIRunner` 及真实 `blue_picks` / `red_picks` 卡槽，兼容外层 wrapper、overlay 重建和红蓝方换位。
- 三狼可见宽度从 24 提高到 32，元素龙从 54 提高到 68；同时保持原生动画时长、帧序和脚底锚点，避免抽搐与前后摆动回归。
- 绯红印记树怪和苍蓝雕纹魔像的可见主体重新居中，每帧保持原生脚底位置；未修改野怪刷新坐标。
- 新增跨平台 LF 规则，使资源清单哈希在 Windows 与 GitHub CI 中保持一致。

## v0.7.2：BP、野怪动画、Nexus 与随机元素龙修复

- 修复游戏 0.5.0 实际 UI 树位于 `main` 子节点导致的 BP 插画失效，并按选手换位顺序映射五张 LOL 英雄插画；百科全身图也改用真实节点路径。
- 修正两个错误的 `.sprite_data` 资源后缀为引擎实际注册的 `.sprite_sheet`，消除 `Only 165/167 asset override(s) were applied` 警告并恢复史诗野怪血条图集坐标。
- 三狼、小龙和纳什男爵重新遵循官方 sheet 尺寸、逐帧矩形、锚点与动画时长；缩小可见模型并稳定每帧质心，清理元素龙边缘的洋红键色。
- 使用 API 0.8 的权威对局 seed，在每局开始时固定选择炼狱、海洋、山脉、云端或海克斯科技亚龙；双方和录像结果一致。公开 API 仍不支持每次刷新轮换、龙魂和自动远古龙转场。
- 使用内置 imagegen 生成并接入蓝红双方 Nexus 水晶及核心，保持官方图集尺寸和动画契约。
- 新增逐项覆盖资源可发现性与可加载性验证；任何缺失资源都会直接使构建验证失败。

## v0.7.1：游戏 0.5.0 / Mod API 0.8 兼容修复

- 使用 Team Samoyed 官方 `0.5.0_hotfix2` SDK 和固定工具链 `nightly-2026-05-24` 重新编译原生 DLL，导出 API 版本由 0.7 更新为 0.8。
- 新增原生 DLL 构建脚本与 API 导出校验，旧 SDK 会直接报错，避免再次把 0.7 DLL 打进运行包。
- 模组版本提升到 0.7.1；美术、技能和品质升级内容保持不变。

## v0.7.0：BP、百科、野区与装备品质升级

- 为慎、卢锡安、奥利安娜、贝蕾亚和希维尔加入选人完成后的独立插画；不依赖 Ban/Pick View Plus，未覆盖英雄仍回退到官方头像。
- 百科为这 5 个英雄使用独立全身立绘，从头到脚完整显示；比赛 HUD、计分板和小头像继续使用原有紧凑 `face` 资源。
- 以 imagegen 生成并替换本体全部 6 个中立演员家族：纳什男爵、元素龙、绯红印记树怪、苍蓝雕纹魔像、魔沼蛙和暗影狼；目标位置、刷新槽和原生数值保持不变。
- 额外生成锋喙鸟和石甲虫两套完整动作美术，补齐 League 的 6 类普通野区营地素材。TFM2 本体只有 `rhino/tree/mushroom/bee` 四个普通营地槽，因此这两套暂存为未映射备用资源，不能虚假宣称已作为第 5、6 个营地实际刷新。
- 元素龙包内包含炼狱、海洋、山脉、云端、海克斯科技和远古龙六套模型。公开模组 SDK 没有可重放同步的“每次刷新换资源/龙魂后切远古龙”状态接口，当前运行时安全地使用炼狱亚龙；完整动态轮换仍需底层目标物刷新钩子。
- 纳什男爵拥有独立攻击/命中特效、目标 HUD、贴纸和增益图标；攻击与死亡音效从本机 League of Legends Map11 Wwise 资源按固定 bank、事件、媒体 ID 和 SHA-256 提取。
- 蓝红双方防御塔替换为 imagegen 生成的 League 风格塔身，并同步替换塔芯、攻击弹体、命中特效和塔图标；严格保留官方 581×64 / 357×64 图集尺寸、动作时长、锚点和独立地图阴影。
- 原生 30 件装备图标和名称全部替换为 League 风格等价物，保留 TFM2 原有属性、价格与升级树，避免纯美术改动影响平衡。

## v0.6.0：希维尔同 ID 重做官方 005

- 通过 `champion/boomerang_hunter.data_champion` 同 ID 覆盖官方 Boomerang Hunter；项目编号 005 不会误作引擎编号，实机强制测试使用 native index 26。
- 仅提供 Q/E/R 三个主动槽：Q 是真正嵌套的飞出与返回投射物；E 是 1.5 秒技能伤害防护窗口、即时回复与短暂加速；R 只给范围内友方英雄提供 5 秒团队加速且不造成伤害。
- E 的公开数据接口无法识别并消耗“下一次敌方技能”，因此没有虚假宣称完整 LoL 法术护盾；百科文案明确说明它不能阻挡控制或无伤害效果。
- 角色母版、九帧跑动、Q/E/R 图标、普攻/Q/E/R 独立特效均由内置 imagegen 生成；角色图集完整保留原生 12 个动作标签、帧数与时长，包括三个武器标签、`idle_no_boomerang` 和死亡透明末帧。
- 普攻发射/命中、Q 飞出/返回/命中、E 启动和 R 号令音效按固定 Sivir Base Wwise 事件、媒体 ID 与 SHA-256 提取。
- 原生 Boomerang Hunter 自动动作事件与 18 个旧音频 clip 全部隔离到物理静音资产，避免原英雄声音和 Sivir 音效叠播。
- 角色动作改用全图 keep-box 裁切，清除左右普攻的跨格像素/双武器；E 护盾完整包裹模型，R 加速轨迹只显示在脚下。

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
powershell -ExecutionPolicy Bypass -File .\mods\lol_mod\tools\build_native_dll.ps1
python .\mods\lol_mod\tools\build_lol_mod.py --rebuild-quality
python .\mods\lol_mod\tools\validate_lol_mod.py
python -m pytest -q
```

男爵官方音频只在需要重新提取时单独执行 `python .\mods\lol_mod\tools\extract_baron_audio.py`；普通构建直接使用已提交且带 SHA-256 来源记录的 WAV，避免要求每位构建者都安装 League of Legends。

## 安装到本机游戏

安装脚本会同步模组并将 `config/game/mods.json` 设置为仅启用 `lol_mod`：

```powershell
powershell -ExecutionPolicy Bypass -File .\mods\lol_mod\tools\install_lol_mod.ps1
```

本模组为同人作品。League of Legends、Shen、Lucian、Orianna、Briar、Sivir 及相关原始音频素材归原权利人所有；模型、图标和 VFX 是为本模组生成的原创像素素材。

TeamFightMange2-mod was created under Riot Games' "Legal Jibber Jabber" policy using assets owned by Riot Games. Riot Games does not endorse or sponsor this project.
