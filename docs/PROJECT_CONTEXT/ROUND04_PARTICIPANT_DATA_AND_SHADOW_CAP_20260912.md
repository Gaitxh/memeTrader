# 第 4 轮：数据层直观测（买家数）接入 + 同币并发影子上限证据

- 记录时间：2026-09-12T01:50Z（北京时间 09:50）
- 用户决定（本轮开始前）：① 同币并发上限先做**影子记录**，不改行为；② 授权把 `raw_json` 里的
  buyers/sellers 解析落库并接成新特征（不动任何现有策略规则）。
- 约束不变：`mode=paper`、`live.enabled=false`、单一写入进程、现有臂规则零改动；
  append-only 注册本轮 273 → **275**

---

## 1. 数据层：把"已抓取但被丢弃"的参与者数据接上

**实测（近 2 万条快照）**：`buyers_5m` 填充 0/20,000、`holders` 0/20,000，而同一批行的 `raw_json`
里 `buyers` 出现 864 次、`txns` 451 次——数据早已抓到并付费，只是从未解析进列。

**改动（三处，均为"新增"语义）**：

| 层 | 文件 | 内容 |
|---|---|---|
| 解析 | 新增 `src/memetrader/participant_flow.py` | 纯函数解析三种负载形状：geckoterminal `data.attributes.transactions.{m5,h1,h6,h24}.{buys,sells,buyers,sellers}`、dexscreener `pair.txns.*`、以及被 `raw`/`cohort_observer` 包装的嵌套形状；缺失一律 None，绝不补零 |
| 入库 | `store._add_snapshot_locked` | 采集器未提供 `buyers_5m` 时从 `snap.raw` 解析后写入**既有列**（无 schema 变更） |
| 特征 | `dex_trajectory.derive` | 新增三个**新键**：`buyers_5m`、`buyers_growth_5m`（本帧 5 分钟买家数 ÷ 前帧）、`participants_per_trade_5m`（独立买家数 ÷ 买笔数）；把 `buyers_5m` 加入 `current` 投影与 `accept` 的数值化列表。既有键（`buy_count_share`、`liquidity_retention` 等）数值不变——测试逐项断言 |

**落库实测（重载后 6 分钟）**：

| provider | 新行 | 写入 buyers_5m | 负载含 buyers 键 |
|---|---|---|---|
| geckoterminal | 240 | **120（50%）** | 240 |
| strategy-observer:geckoterminal | 148 | **96（65%）** | 148 |
| dexscreener / strategy-observer:dexscreener | 613 | 0 | 0 |

dexscreener 形状本身**不含**买家数（只有笔数），因此为 0 是正确语义而非缺陷；
geckoterminal 的 ~50–65% 说明部分行没有 5 分钟窗口的买家数（其它窗口有也不能混用），
该覆盖率本身作为可观测事实记录。

**新增两条额外臂（第 27 波）**：

| arm_id | 机制 | 条件 | U/持有 |
|---|---|---|---|
| `alpha149_participant_growth_v1` | `participant_growth` | 本帧 5 分钟买家数 ≥ 前帧 ×1.2、买盘占比 ≥55%、深度 ≥3000U 且不流失；**直观测，不再用成交额÷笔数代理** | 2 / 30 |
| `alpha149_participant_breadth_v1` | `participant_breadth` | 独立买家数 ÷ 买笔数 ≥0.6（每笔买入来自不同钱包的比例）、买盘占比 ≥60%、深度 ≥3000U 且不流失——"是否捆绑"的可实现代理 | 1 / 30 |

对照臂：`alpha149_participant_growth_v1` vs 既有 `alpha149_size_informed_flow_v1`（同一意图的代理实现），
两者同场前向比较，可判定"直观测是否比代理更有信息量"。命名与规则文本都写明
`participant_breadth` **不是钱包簇证据**，钱包簇/持有人集中度仍为缺口。

---

## 2. 同币并发：影子上限（只记录，不拦截）

`scripts/supervise_metrics.py` 新增 `shadow_cap()`：把窗口内每笔开仓按时间排序，逐币统计
"第 10 条之后的不同臂"，标记为"若限 10 条臂会被拦下"的仓位。**纯只读**：不写库、不拦截、不改变任何现有臂行为。

**近 4 小时实测（1,053 笔 alpha149 家族的等价窗口口径）**：

| 分组 | 笔数 | 已实现结果 |
|---|---|---|
| 会被上限拦下的（第 10 条臂之后） | **778（73.9%）** | **−135.09U** |
| 会被允许的（每币前 10 条臂） | 275 | **+76.16U** |
| 合计 | 1,053 | −58.93U |

最拥挤的代币：`solana:E48e1En3…` 77 笔、`robinhood:0xb8471f9d…` 67 笔、`solana:4y4rbYoG…` 65 笔、
`solana:9tGPd2C5…` 63 笔、`solana:QB4EQ8mT…` 52 笔。

**结论（以及必须说明的限度）**：同一批入场里，被"第 10 条臂之后"这一分组完全吸收了全部亏损，
而前 10 条臂是正收益——这与"单币崩塌时几十条臂同时被击中"的机理一致（历史最坏单币：30 笔中 28 笔写销、−79U）。
但这是**同一批入场的分组对比，不是组合模拟**：被拦下的资金会改投别处，且"前 10 条"的顺序按开仓时间排列，
并非最优选择规则。因此该数字用于支持决策，不能当作"加上限就能多赚 135U"的收益承诺。

触发告警：`shadow_cap_would_block_large_share`（当被拦比例 >20% 时提示），本轮 73.9%，已触发。

---

## 3. 覆盖率与实时状态（本轮快照）

| 指标 | 值 | 说明 |
|---|---|---|
| 发现 | **2,554 新币/小时** | 有界测量（id 前沿 5.2 万秒跨度） |
| 采集 | 9,521 快照行/小时（7,232 行深度 ≥1000U） | 采集非瓶颈 |
| 代币级信号率 | **0.83%**（21/2,523，60 分钟窗口） | 仍是全链最大断点；开放带供应已放出但需要时间转化 |
| 开仓 | 384 笔/小时 / 15 币 = **25.6 笔/币** | 拥挤加剧（说明开放带把更多臂推到同一批币上） |
| 开放带供应 | `survivable_open_band` 就绪 210 次 vs 安全带 50 次 | 第 3 轮修复生效 |
| 月亮袋 | 首笔真实部分成交 + 本金锁定（见第 3 轮报告） | 机制可用 |
| 24h | 硬止损 498 笔 −578.64U；写销 124 笔 −394.0U | 与第 3 轮同量级 |

---

## 4. 监控与下一步

| 观察项 | 指标 | 判定 |
|---|---|---|
| 直观测 vs 代理 | `participant_growth` 臂 vs `size_informed_flow` 臂 | 各 ≥20 笔自然样本后比较；若直观测不优于代理，则不予推广 |
| 买家数覆盖率 | geckoterminal 行 `buyers_5m` 填充率 | <40% 说明负载形状识别不全，需补形状；当前 50–65% |
| 影子上限 | `shadow_cap.blocked_share_pct` 与两组 realized | 持续 >50% 且被拦组持续为负 → 建议用户授权真实上限 |
| 代币级信号率 | `coverage.signal_rate_pct` | 目标 >2%；开放带与参与度臂需要 ≥1 小时窗口观察趋势 |
| 单币爆炸半径 | `coverage.concurrent_tokens` | 单币 ≥12 条臂告警；当前最高 35 条臂 / 118U |

**待用户下一步决定**（本轮已给足证据）：是否把影子上限升级为真实生效的**新风险层**（仅对新臂生效，
或经授权对所有臂生效）。按当前数据，若只对新臂生效，爆炸半径仍由 100+ 条旧臂决定，效果有限。

---

## 5. 状态分离

- **implemented**：新增 `src/memetrader/participant_flow.py`；`store._add_snapshot_locked` 解析落库；
  `dex_trajectory.derive` 三个新键 + `current`/`accept` 携带 `buyers_5m`；`alpha149.py` 第 27 波
  2 条臂 + 规则文本；`scripts/supervise_metrics.py` 新增 `shadow_cap()` 与
  `shadow_cap_would_block_large_share` 触发。
- **tested**：`test_participant_flow.py` 5 项（三种负载形状、缺失不推断、净新增参与者、
  derive 新键与既有键数值不变、两条臂条件）+ 既有 64 项 = **69 项全通过**；
  另跑 `test_dex_trajectory.py`、`test_shared_batch148.py` 全通过（共享文件改动后）。
- **deployed**：policy_additions 273 → **275**；运行进程重载（PID 36160/20424）；
  重载后 6 分钟内 geckoterminal 行 buyers_5m 填充率 50%/65%（此前为 0）。
- **naturally observed**：两条参与者臂在前 411 帧内 `ready=0`（需要"连续两帧都有买家数"的池子），
  **不作有效性结论**；开放带两臂已自然开仓 9 笔；月亮袋首笔部分成交已记录。
