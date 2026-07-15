# 永恩 009 三主动槽技能契约

`dual_blader` 只使用三个真实主动槽：`skill=Q`、`skill2=E`、`ult=R`。第二主动槽是 E-only；不会拼接、展示或结算其他主动技能。

## Q — 错玉切

- [x] Q 使用 `Q1 → Q2 → Q3` 三段状态。
- [x] Q1 命中后才添加 `lol_yone_mortal_steel_stack_1`，持续 360 tick；空放不叠层。
- [x] Q2 命中后才移除第一层并添加 `lol_yone_mortal_steel_stack_2`，持续 360 tick；空放不推进。
- [x] Q1/Q2 的穿透命中 payload 含同状态防重；一次穿透多个目标也只推进一次层数。
- [x] 第二层同时注册 `ThreePhase` 风状态，使用独立 `lol_yone_q3_ready_wind` 动画；获得第二层后持续可见，消耗或超时后移除。
- [x] Q3 施法时立即消耗第二层，并沿施法方向执行一次无伤害 `RushTime`。
- [x] Q3 同时发射独立蓝白旋风弹道 `lol_yone_q_empowered_projectile`；其动画为 `lol_yone_q3_tornado`，不得复用 Q1/Q2 的窄剑气动画。
- [x] Q3 弹道只结算一次 `25 + 80% AD` 物理伤害与一次 45 tick `Airborne`；冲刺本身不附带伤害。
- [x] `lol_yone_q3_airborne_cue` 使用同一蓝白风系素材中的独立向上风柱，目标击飞方向必须清晰可读。

## 第二主动槽 — E 破障之锋

- [x] `skill2` 是 E-only，以敌方英雄为施法目标，原生 AI 能正常选择与释放。
- [x] `lol_yone_e_body_anchor` 是固定本体标记；视觉灵体离开时，真实演员仍保持稳定体型并播放五帧 `skill2_attack`。
- [x] `lol_yone_e_spirit_outbound` 是无直接伤害的可见灵体弹道；240 tick 灵体作战窗口结束后，只生成一个 `BackToCasterLinearProjectile`：`lol_yone_e_spirit_return`。
- [x] `lol_yone_e_start_native` 在施法开始建立一次伤害账本；`lol_yone_e_settle_native` 只在返回结束时结算并清理一次。
- [x] 普攻、Q1/Q2/Q3 与 R 的每个实际伤害载荷都严格由 `lol_yone_e_damage_pre_native` 和 `lol_yone_e_damage_post_native` 前后包住；灵体窗口外两者为空操作，窗口内只累计该次真实伤害。
- [x] 四个 Native 节点只负责建立、记录并结算本次灵体伤害窗口；不得混入额外直线斩击、护盾或击飞。
- [x] 数据树绝无 `Rush` / `Teleport` / `RushTime` / `RushMoveToBack`，不会移动真实演员，也不宣称真实坐标回溯。
- [x] `Delayed tick=240` 内只安排一次返回；返回结束只播放 `lol_yone_e_return_burst`，并执行 settle/清理，不得生成第二次灵体或循环返回。

## AI 与卡死回归门禁

- [x] E 不注册自定义输入 AI，不保存可失效的目标实体引用，也不对旧目标做二次输入校验。
- [x] 每次 E 只有一组 start/settle；pre/post 与每个真实伤害点一一成对，所有状态必须在 settle 后清理；死亡、目标消失和连续对局不得遗留状态。
- [x] 压力测试必须证明模拟时间持续推进，施法者能恢复移动、普攻与后续技能。

## 文案与原生面板门禁

- [x] 原生技能行是 `624x95`，说明区最多 4 行；Q、E、R 的五种语言文案都必须通过保守字宽换行预算。
- [x] 玩家文案只说明可见玩法，不出现内部 API、引擎类型、坐标接口、Native 名称或实现限制。
- [x] 第二主动槽文案只描述 E，不出现组合技能、月牙斩、护盾或内部投射物名称。

## R — 封尘绝念斩

- [x] R 保留一次到达击飞、六次交替物理斩击和一次固定伤害灵魂回响。
- [x] 延迟节点为 `8/16/24/32/40/48/60`；最坏路径仍小于 96 tick 动作时长。

## 待人工实机确认

- [ ] 连续空放与命中 Q1/Q2，确认只有命中才叠层，第二层风状态可见且不会覆盖身体。
- [ ] Q3 朝不同方向释放，确认演员只突进一次、蓝白旋风只生成一条、命中目标只被击飞和结算一次。
- [ ] 观察 E 的固定本体、灵体离体、返回与结算闪光是否连续可读，且没有其他主动技能的伤害、护盾或特效。
- [ ] 连续施放 E 50 次以上并跨死亡、目标消失和下一场对局，确认不卡死且无残留状态。
