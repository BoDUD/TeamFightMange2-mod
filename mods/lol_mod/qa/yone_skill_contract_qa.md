# 永恩 009 三主动槽技能契约

`dual_blader` 只使用三个真实主动槽：`skill=Q`、`skill2=E`、`ult=R`。第二主动槽是 E-only，不混入或展示 W。

## Q — 错玉切

- [x] Q 使用 `Q1 → Q2 → Q3` 三段状态。
- [x] Q1 命中后才添加 `lol_yone_mortal_steel_stack_1`，持续 360 tick；空放不叠层。
- [x] Q2 命中后才移除第一层并添加 `lol_yone_mortal_steel_stack_2`，持续 360 tick；空放不前进。
- [x] 第二层使用独立 `lol_yone_q3_ready_wind` 三阶段风特效，移除状态时同步消失。
- [x] Q3 施法时消耗第二层，沿施法方向执行一次无伤害 `RushTime`，并发射 `lol_yone_q_empowered_projectile` / `lol_yone_q3_tornado`。
- [x] Q3 弹道只结算一次 `25 + 80% AD` 物理伤害与一次 45 tick `Airborne`；冲刺本身不带伤害。
- [x] `lol_yone_q3_airborne_cue` 在命中目标处提供可读的上挑反馈。

## E — 破障之锋 / 灵体出窍

- [x] `skill2` 是 E-only，以敌方英雄方向施法，AI 可正常使用。
- [x] `lol_yone_e_start_native` 只建立一次伤害账本并记录本体锚点。
- [x] 施法点留下一个覆盖 240 tick 作战窗口与 60 tick 返回阶段的不透明本体 `lol_yone_e_body_anchor`；锚点播放五帧 `skill2_attack`，不会跟随移动角色。
- [x] 真实施法者恰好执行一次无伤害 `RushTime` 离开本体，并在 240 tick 灵体窗口内继续移动、普攻和施放 Q/R。
- [x] 移动中的灵体只使用 `lol_yone_e_spirit_form` 稀疏轮廓和粒子，不绘制第二个完整蓝色人形，也不覆盖角色本体。
- [x] 普攻、Q1/Q2/Q3 与 R 的每个伤害载荷都由 `lol_yone_e_damage_pre_native` / `lol_yone_e_damage_post_native` 包裹，只累计灵体窗口中的真实伤害。
- [x] 240 tick 时只调用一次 `lol_yone_e_begin_return_native`，移除作战灵体轮廓并进入 `lol_yone_e_returning`。
- [x] 返回阶段限时 60 tick，以 300% 额外移速和控制免疫向记录的锚点强制寻路；300 tick 时只调用一次 `lol_yone_e_settle_native` 并清理返回状态。
- [x] 结算只播放一次 `lol_yone_e_return_burst`，不会生成第二灵体、循环返回或旧的灵体弹道。
- [x] E 不使用旧返回弹道、瞬移、背后冲刺或额外伤害弹道。

## AI 与生命周期

- [x] `YoneSoulUnboundReturnInputAi` 只在有待返回锚点时工作，并仅在受控的 60 tick 返回阶段持续发出归位移动输入。
- [x] E 账本由每个 `GameCtx` 独立服务 token 分桶；后台模拟的较低 tick 不会再清空前台对局的伤害、锚点或返回状态。
- [x] 每次 E 只有一对 start/settle；死亡、目标丢失或下一场对局不会继承旧账本、锚点或返回状态。
- [x] 返回阶段结束后恢复普通移动、普攻与主动技能决策。

## 文案与面板

- [x] 原生技能行是 `624x95`；每个本地化技能说明最多 4 行，避免重叠。
- [x] 玩家文案不出现内部 API、数据结构、AI 类型、原生函数名或引擎限制。
- [x] E 文案不出现 W、月牙、护盾或旧合并技能名。

## R — 封尘绝念斩

- [x] R 保留一次到达击飞、六次交替物理斩击与一次固定伤害灵魂回响。
- [x] 延迟点为 `8/16/24/32/40/48/60`，总运行时间落在 96 tick 动作窗口内。

## 待人工实机确认

- [ ] 连续空放与命中 Q1/Q2，确认只有命中才叠层，第二层风状态清楚但不遮挡角色。
- [ ] Q3 朝不同方向施放，确认只冲刺一次、只生成一条风、命中英雄只击飞一次。
- [ ] 施放 E 后确认不透明本体留在原地，真实可操控角色带稀疏灵体轮廓出击；240 tick 后高速寻路返回并在 300 tick 清理。公开 Mod API 不能直接写英雄坐标，因此不把该过程宣称为无视地形的瞬间传送。
- [ ] 连续施放 E 50 次并跨死亡、目标丢失和下一场对局，确认无残留状态、无卡死、无尺寸跳变。
