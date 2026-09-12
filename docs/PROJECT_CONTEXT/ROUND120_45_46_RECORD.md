# ROUND 120-45/46 — 风控过滤专项审计：我的两个数字都对，只是量的不是同一件事；"闸门过严"假设第三次被证伪

日期：2026-09-13
探针：`data/research/diag_round120/r45_risk_stage.py`、`r46_clause.py`、`r46b_curve_lane.py`

---

## 1. 起因：我自己的记录里有两个互相矛盾的数

目标要求逐环节报告**风控过滤**的拒绝原因与通过率。但我的记录里同一环节有两个数：

- 合并版漏斗：`invalid-asof` 占 57,290 次评估的 **4.78%**
- 第 28 轮检查点："新鲜度规则不构成约束（`entry_snapshot_too_old` 占评估的 **0.03%**，上限 90s）"

**4.78% vs 0.03% 是同一环节上 160 倍的矛盾。** 必须查清。

## 2. 对账：两个数都正确，量的是**两道不同的检查**

61,862 次评估的**全部** reason 字符串（实测，逐字）：

| reason | status | n | 占比 |
|---|---|---|---|
| `cohort_observation` | rejected | 21,263 | 34.37% |
| `pattern_observation` | rejected | 16,614 | 26.86% |
| `no_active_matching_entry_policy` | rejected | 14,210 | 22.97% |
| `entry_pool_liquidity_absent_curve_stage` | rejected | 4,388 | 7.09% |
| **`invalid_exact_asof_market_snapshot`** | rejected | **2,899** | **4.69%** |
| `entry_pool_liquidity_below_configured_floor` | rejected | 1,747 | 2.82% |
| `entry_pool_liquidity_unknown` | rejected | 551 | 0.89% |
| `cohort_observation` | **admitted** | 174 | 0.28% |
| `entry_snapshot_too_old` | rejected | **12** | **0.02%** |
| `pattern_observation` | admitted | 4 | 0.01% |

拒绝 61,684（99.71%），准入 178（0.29%）。

- **第 28 轮的 0.03% 是对的**，而且能从数据独立复现：决策时快照年龄 >30s 的是 **19/61,862 = 0.031%**，
  >90s（第 28 轮记的上限）的是 12 个 = 0.019%。它量的是**陈旧度**。
- **漏斗的 4.69% 也是对的**，但它是 `invalid_exact_asof_market_snapshot`——一道**身份/有效性**检查，
  与陈旧度无关。

> **两个数都对，`invalid-asof` 这个过短的标签是我自己制造的混淆。**
> 这是本 session 第四次"两个数字看起来矛盾、实际只是标签太短"。（新规则 16）

## 3. 风控类拒绝的完整分解（15.51%）

| reason | n | 占比 | 性质 |
|---|---|---|---|
| `entry_pool_liquidity_absent_curve_stage` | 4,401 | 7.11% | 曲线阶段池，无可测流动性 |
| `invalid_exact_asof_market_snapshot` | 2,901 | 4.69% | 身份/有效性 |
| `entry_pool_liquidity_below_configured_floor` | 1,747 | 2.82% | 已配置下限（**入场侧已经在用**） |
| `entry_pool_liquidity_unknown` | 551 | 0.89% | 流动性未知 |
| `entry_snapshot_too_old` | 12 | 0.02% | 陈旧度 |
| **合计** | **9,612** | **15.51%** | |

**全部基于新鲜证据**：各原因在决策时的平均快照年龄为 0.28–5.86 秒、最大 30 秒；
只有那 12 个 `entry_snapshot_too_old` 平均 164 秒。**178 个准入评估中，0 个建立在 >30 秒的快照上。**

顺带**加强了第 42 轮**：`entry_pool_liquidity_below_configured_floor` 在**入场侧**已经生效并拒绝了 1,747 次——
它只是从未对"后来死掉的那些仓位"生效，因为那些仓位入场时流动性完全正常。

## 4. "闸门过严"假设：**第三次被证伪**

`store.py:29442-29461` 用 7 个时点有效性条件的**合取**拒绝。我怀疑最可能失败的是两条**单调性护栏**
（`h1_trades ≥ m5_trades`、`h1_volume ≥ m5_volume`，DexScreener 的滚动窗口字段），
因为 m5 比 h1 刷新更快，滞后可能使 m5 超过 h1，从而丢掉本来有效的候选。

**实测：这两条护栏在 38,110 个观察者帧中触发 0 次。**

真正的原因：

| 失败的子句 | n | 占比 |
|---|---|---|
| **`price <= 0`**（`priceUsd` 缺失） | **2,871** | **98.97%** |
| `pairCreatedAt` 缺失/为零 | 30 | 1.03% |

例：`solana:FsA28Svt…pump`，`dex=pumpfun`，`priceUsd=None`，`priceNative=0.0000003415`，
`txns m5={buys:0,sells:0}`，`h1={buys:4,sells:2}`，`volume m5=0 h1=0`。
例：`bsc:0x0c782fda…`，`dex=fourmeme`，`priceUsd=0.00001243`，`pairCreatedAt=None`。

**拒绝是正确的**：拿不到美元价的池子无法定价，没有创建时间的池子没有年龄。
**假设不成立，闸门在做它该做的事。**

## 5. 曲线阶段这块最大的可寻址覆盖（11.8%）——设计上已经有通道，而且它没有优势

`invalid_exact_asof_market_snapshot` 的 99.0% 与 `entry_pool_liquidity_absent_curve_stage` 全部
是**绑定曲线阶段**的池子，DexScreener 对它们**不提供 `priceUsd`**：

| dex | `invalid_…` | `absent_curve_stage` |
|---|---|---|
| pumpfun | 913 | 3,942 |
| fourmeme | 1,932 | 330 |
| meteoradbc | 13 | 128 |
| pumpswap / 其他 | 43 | 1 |

这是继"观测槽位排队"之后**最大的单块可寻址覆盖**（合计约 11.8% 的评估）。
而系统**已经有**为它设计的通道：`pump_native_absorption_fast_v1`，入场原因
`later_observed_protocol_model_paper`。

**当前实况（第 30 轮时为 11 个仓位，现已增长）：**

- **14 个仓位，14 个不同代币，恰好 1.00 仓/代币**（协议模型通道的设计如此）
- 累计实现 **−14.05U（−1.00U/仓）**
- 退出：**hard_stop 11 个（−15.59U）**、max_hold 2 个（−1.10U）、trailing 1 个（+2.64U）
- 在拒绝记录里出现过的 **6,948 个不同曲线池地址**中，**只有 11 个代币**曾被任何臂入场，合计 −13.65U

**即：通道把这块覆盖的 0.20% 转成了仓位，并且是亏的，退出方式以硬止损为主。**

> 结论：曲线阶段不是**过滤缺陷**，而是**数据可得性**限制——提供方对绑定曲线不给美元价。
> 唯一处理它的通道在 n=14 上没有表现出任何优势，且转化率 0.20%。
> **不值得为它构造"由 `priceNative × 原生币美元价"推导价格"的新通道**：
> 曲线池同时也没有可测流动性，已配置的 1000U 池下限无法满足，仓位的定价、滑点模型与写下线逻辑
> 都会失去依据；第 30 轮已实测该通道每代币一仓且无优势。
> **不改代码。**

## 6. 追加规则

- **16**：当两个记录中的数字看似矛盾时，先检查它们是否只是**标签过短**造成的同名不同物；
  本 session 已出现四次（write-off 率、`closed` 均值、`status='written_off'`、`invalid-asof`）。
  给度量起名时要带上它**量的是什么**，而不是它**在哪一段代码里**。

## 7. 对本轮目标五个维度的交代

- **准确性**：两条风控数字对账完成；"闸门过严"假设用 38,110 帧证伪。
- **有效性**：确认最大的可寻址覆盖块（曲线阶段 11.8%）受**数据可得性**限制，而非规则限制。
- **实时性/速度**：见第 44 轮（延迟全部是排队，端到端 p50 1.30 秒）。
- **稳定性**：见第 44 轮（监督日志 483 次运行不变、崩溃日志自第 33 轮起 0 字节新增）。
- **频率**：观测吞吐 2,310 快照 / 2,311 评估 / 930 标记每 10 分钟，10 分钟开 13 仓、平 73 仓。
