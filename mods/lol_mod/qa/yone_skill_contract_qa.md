# 永恩 009 三主动槽技能契约

本文件记录 `dual_blader` 的静态安全门禁。公开 Mod API 只提供 Q、第二主动槽和 R，因此当前实现严格保留三个主动按钮：`skill=Q`、`skill2=E+W 组合近似`、`ult=R`，不会伪造第四个按钮。

## Q — 错玉切

- [x] Q 使用清晰的 `Q1 → Q2 → Q3` 三段状态，而不是旧版两段循环。
- [x] Q1 命中后才添加 `lol_yone_mortal_steel_stack_1`，持续 360 tick；未命中不会叠层。
- [x] Q2 命中后才移除第一层并添加 `lol_yone_mortal_steel_stack_2`，持续 360 tick；未命中不会推进。
- [x] Q1/Q2 的穿透命中 payload 各有内层 `SwitchByBuff` 同状态防重；多目标命中只允许首个目标推进层数。
- [x] Q3 在施法开始立即移除第二层，即使命中失败也不会保留强化状态。
- [x] Q3 只执行一次 `RushTime`，其 `applied_effects` 为空，因此冲刺本身无伤害。
- [x] Q3 只生成一条 `lol_yone_q_empowered_projectile` 风道；命中只包含一次 `25 + 80% AD` 攻击与一次 45 tick `Airborne`。
- [x] `lol_yone_q3_airborne_cue` 使用独立竖向击飞动画，目标身上会出现明显上升提示。
- [x] Q 不含 `Delayed`、`Native` 或第二条强化风道。

## 第二主动槽 — E 灵体 + W 月牙组合近似

- [x] `skill2` 仍以 `EnemyChampion` 为目标，让游戏原生 AI 可以稳定选择并释放，不依赖自定义输入 AI；施法范围 `48000` 与 W 唯一含伤害的命中体长度一致，不会在无伤区间施放。
- [x] `lol_yone_e_body_anchor` 是不跟随的固定本体标记，留在施法点。
- [x] `lol_yone_e_spirit_outbound` 是无伤害的可见灵体投射物；抵达终点后只生成一个 `BackToCasterLinearProjectile`：`lol_yone_e_spirit_return`。
- [x] 灵体往返投射物的 `applied_effects` 都为空，返回结束只播放 `lol_yone_e_return_burst`，不会重复伤害或控制。
- [x] 公开数据 API 没有可写英雄坐标与安全位置快照，所以真实英雄坐标不会被伪造回溯；永恩本人留在本体标记处。文案明确说明这不是 LoL E 的真实位置回溯。
- [x] 真实技能树使用五帧 `skill2_attack` 作为 42 tick `CasterAnimation`，QA contact 也展示同一 tag，不再用单帧 `skill2` 冻结身体。
- [x] 同一组合动作创建两个完全同形状的短宽 `LineRangeProjectile`：均为宽 42000、长 48000、`apply=1`。
- [x] `lol_yone_w_sweep_hitbox` 使用 `EnemyWithoutTower`，只包含一次 `45 + 90% AD` 攻击和命中 SFX；英雄、小兵与野怪都会受伤，防御塔除外。
- [x] `lol_yone_w_champion_shield_probe` 使用 `EnemyChampion`，不含 `Attack` 或伤害命中 SFX，只负责护盾、计数和护盾视觉；第一名英雄命中获得 `70 + 20% AD` 护盾，第二名最多再增加 `35 + 10% AD`，之后不再增长。
- [x] 英雄同时经过两个命中体但只由伤害体受到一次伤害；小兵与野怪只经过伤害体，不会触发护盾档位。
- [x] W 无击飞：整个 `skill2` 不含 `Airborne`、`Knockback`、`Rush`、`RushTime` 或 `RushMoveToBack`。
- [x] 已删除旧追背 W 的锁定、背后位移、交叉斩与击飞视觉命名；护盾只使用小型开放月牙，不覆盖英雄身体。

## AI 与卡死回归门禁

- [x] Rust 中不得恢复 `YoneWInputGate`、`lol_yone_w_input_gate` 或 `registration.add_player_input_ai(YoneWInputGate)`。
- [x] Rust 中不得恢复 `ctx.is_valid_input(&sealed_pursuit)` 或任何对过期目标实体的二次校验。
- [x] E/W 组合仅使用数据层投射物、范围命中与护盾，不新增 Rust 状态、互斥锁、实体缓存或解包路径。

## R — 封尘绝念斩（数据近似）

- [x] R 保留一次到达击飞、六次交替物理斩击和一次固定伤害灵魂回响。
- [x] 延迟节点仍为 `8/16/24/32/40/48/60`；最坏路径 `start 4 + travel 8 + delayed 60 = 72 < duration 96`。
- [x] R 不使用自动换目标、范围随机目标或 `Native` 效果。

## 待人工实机确认

- [ ] 连续观察 Q1/Q2 命中层数和 Q3 竖向击飞，确认风道只结算一次伤害。
- [ ] 观察 E 的固定本体标记、蓝色灵体离体、红色灵体返回与返回闪光是否连续可读。
- [ ] 在英雄、小兵与野怪目标下观察 W 月牙：三者各只受一次伤害，且只有前两名英雄触发两档封顶护盾；确认没有旧背后位移、击飞或身体覆盖特效。
- [ ] 以 50 次以上第二主动槽/R 压力测试确认模拟时间持续推进，AI 能恢复移动与普攻。
