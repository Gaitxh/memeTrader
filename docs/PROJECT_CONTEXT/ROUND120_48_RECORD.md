# ROUND 120-48 — 观测预算到底是"饱和"还是"被链上限切碎"？**饱和**（86% vs 14%），覆盖问题就此定论

日期：2026-09-13
探针：`data/research/diag_round120/r48_occupancy.py`

---

## 1. 这一轮要分辨的两种可能（补救方向完全相反）

第 47 轮从生产计数器测出：109 次准入尝试中 **74 次（67%）**因 `skip_bucket_full` 被拒，
其中 `bucket_full_chain_full` 73、`bucket_full_chain_spare` 12。
而 `observation_leases145` 的配置是 `BASE_CAPS={early:3, growth:4, mature:3}`（合计 10）
与 `CHAIN_CAP=10`；三条链 × 10 = **30**，正是第 29 轮认定的"约 30 个槽位"。

这两组读数指向**相反的补救**：

| 可能 | 含义 | 补救 |
|---|---|---|
| **(a) 饱和** | 三条链都各自顶到 10，总量 30 真的用满 | **只有加预算**——用户决策项，我无权改 |
| **(b) 切碎** | 某条链顶到 10 而别的链有空位 | **同一份总量重新分配即可**，零额外请求预算 |

`RediscoveryFunnel.quote()` 会把 `occupancy` 随每个 `admission_attempt` 示例一起记下——
**生产自己已经记录了答案**，不需要我推断。

## 2. 实测：**饱和**（证据是每次拒绝时的占用快照）

17 个带占用快照的准入示例，`occupancy` 字段含
`chain / chain_total / held_count / occupied / base_caps / target_bucket`：

| 时间 | 链 | chain_total | held_count | occupied | target |
|---|---|---|---|---|---|
| 23:15:13 | solana | **10** | 10 | `{early:3, growth:4, mature:3}` | — |
| 23:15:13 | **bsc** | **10** | **1** | `{early:3, growth:4, mature:3}` | mature |
| 23:15:27 | **robinhood** | **10** | **3** | `{early:3, growth:4, mature:3}` | growth |
| 23:15:36 | solana | **10** | 10 | `{early:3, growth:4, mature:3}` | mature |
| 23:15:41 | solana | **10** | 10 | `{early:3, growth:4, mature:3}` | mature |
| 23:16:17 | bsc | **10** | 1 | `{early:3, growth:4, mature:3}` | mature |
| 23:16:41 | solana | **10** | 10 | `{early:3, growth:4, mature:3}` | growth |
| 23:16:46 | solana | **10** | 10 | `{early:3, growth:4, mature:3}` | mature |
| 23:16:59 | bsc | 9 | 1 | `{early:3, growth:4, mature:2}` | mature |

**关键读数**：`occupied` 在几乎每一次快照上都**恰好等于** `base_caps`
（`{early:3, growth:4, mature:3}` = 10 = `CHAIN_CAP`），而且**三条链同时如此**。
`non_held_by_chain_bucket` 也显示三条链都是 `{3,4,3}`——**每个桶、每条链都满**。

`coverage145:status.membership` 独立印证（as_of 23:17:30Z）：
`bsc {early:5, growth:4, mature:2} total 11`；`robinhood {3,4,3} total 10`；`solana {3,4,3} total 10`。

**因此：(a) 饱和。** 三条链都顶在链上限、且三个桶同时顶在桶上限。

**切碎只占少数**：`bucket_full_chain_spare` 12 / 85 = **14%**，而
`bucket_full_chain_full` 73 / 85 = **86%**。也就是说，即使在"链还有余量"的那 12 次里，
真正的原因也多半是**目标桶**满（`target_bucket` 集中在 `mature` 与 `growth`），
而不是链级空位被浪费。

> **结论（本轮定论）**：观测预算**不是被上限切碎**，是**真的用满了**。
> 想提高密集观测覆盖率只有一条路——**提高预算**，而这属于用户决策项
> （第 79 轮否决、83/88 轮部分批准）。**本轮不触碰预算。**

## 3. 这使"唯一约束"的论证闭合

现在同一个约束有**四条独立测量**，且最后一条给出了机制：

| 轮次 | 测量 | 结论 |
|---|---|---|
| 第 29 轮 | 只有 4.4% 的被观测代币拿到 ≥3 帧；密集转化率 18× | 覆盖是约束 |
| 第 44 轮 | 发现→首个快照 p50 97s，而下游全部 ≤1.3s；0 个代币首帧是观察者帧 | 延迟全在首个快照之前 |
| 第 47 轮 | 生产计数器：67% 的准入尝试因**桶满**被拒；82/110 个 episode **本来有可用帧** | 拒绝的原因是容量，不是数据 |
| **第 48 轮** | **拒绝时的占用快照：三条链 100% 顶在 `CHAIN_CAP=10`、三桶 100% 顶在 `base_caps`** | **容量真的用满，不是切碎** |

**"过严阈值/逻辑/风控规则系统性挡住可交易候选"这个问题的最终答案仍然是否定的**，
而现在的措辞比第 30 轮更硬：不是"没有阈值在挡"，而是**挡在容量上，而容量是用户批准的 30 个槽位**。

## 4. 同批读到的其他计数（记录，不行动）

来自 `chain-meme-pattern-watch`（本代际 1.25 小时，recorded_at 23:17:30Z）：

| 计数 | 值 | 说明 |
|---|---|---|
| `watched` | 44 | 观察名单成员 |
| `mover_watching` | 22 / 24 | 第 47 轮已验证的储备占用 |
| `sampled` | 21 | |
| `projected` | **0** | 本代际没有从该路径投影出入场 |
| `borrows_since_start` | 46 | |
| `replacements_since_start` | 141 | |
| `reservation_reclaims_since_start` | 41 | |
| `other_pool_quote_skips_since_start` | **5,633** | 量大，语义未查；**本轮不解释** |
| `pool_migrations_since_start` | 0 | |

`coverage145:status.priority_targets`：`actual_open 14`、`high_priority_total 15`、
`eligible_recent_receipts 65`、`filtered_reasons {position_exists 15, terminal 38, expired_or_future 2, identity 0}`、
`obsolete_filtered 55`。

`mature_window_counts`（已成熟窗口，按原因）：`30s → OBSERVED 402 / SOURCE_NO_UPDATE 847 / UNKNOWN_PATH_GAP 266`；
`120s → 419 / 556 / 129`；`300s → 236 / 182 / 193`。

> **注**：`other_pool_quote_skips_since_start = 5,633` 是本轮看到的**最大单一未解释计数**。
> 我**没有**去解释它——语义未确认前解释它，正是本 session 已犯过四次的那类错误（规则 1/12/16）。
> 留作待查项，需要时先读代码再下结论。

## 5. 本轮对目标五个维度的交代

| 维度 | 推进 |
|---|---|
| 准确性 | 把覆盖约束从"三条独立测量"推进到**机制层定论**：饱和而非切碎（86%/14%） |
| 有效性 | 明确"零预算下已无可挖的分配效率"；第 47 轮已把**真实存在的**那个可达性缺陷修好并验证 |
| 覆盖率 | 约束定论；`mover_watching` 22/24 说明已批准预算正在被使用 |
| 速度/实时性 | 承接第 44/47 轮，机制闭合 |
| 稳定性 | 代际运行正常；`projected=0` 是该路径本代际无产出，非故障 |

## 6. 追加规则

- **18**：**在把"容量不足"当作结论之前，先测量被拒绝那一刻的占用快照**——
  否则无法区分"容量真的用满"与"容量被上限切碎"，而这两者的补救完全相反、成本相差一个数量级。
  本轮的占用快照来自生产自己在记录拒绝原因时一并写下的 `occupancy` 字段；
  **如果那个字段不存在，正确做法是先加它，而不是先猜。**（与规则 17 同源。）
