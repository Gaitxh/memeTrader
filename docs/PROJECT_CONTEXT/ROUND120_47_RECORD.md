# ROUND 120-47 — 用生产计数器（而非推断）测出约束：`skip_bucket_full` 拒掉 67% 的准入尝试；并且"储备注入"修复在生产中**实测有效**

日期：2026-09-13
探针：`data/research/diag_round120/r47*_*.py`

---

## 1. 为什么做这一轮

第 44 轮把"发现→首个观测 p50 97 秒"**推断**为"排队等观测槽位"。那是推断，不是测量。

而代码里本来就有专门回答这个问题的计数器：`rediscovery_funnel.py` 按**代币 episode** 记录
`admission_attempt` 与**每次失败的原因**，以及 `basic_valid`（确实拿到可用帧）。
`mover_watchlist.py` 还带有一个已测量的失败记录和一个为修复它而写的函数。
两者都只存在于内存、按进程代际计数，因此**必须从运行中的进程/其 KV 落点读取**，数据库表里没有。

顺带说明一个我差点踩的坑：`/api/live` 的 `discovery` 块里 `returned_count` / `exposed_token_count`
看起来像"发现丢弃率"，但该块只有 **14 秒**窗口，而且 `hydration` 出现 160%（exposed > returned）——
说明这两个字段在不同 surface 上语义不同。**我没有用它下任何结论。**

## 2. 生产实测：约束是"桶满"，不是"丢弃"

`rediscovery-funnel94`（当前进程代际，`scope=prospective_process_generation`，updated_at 23:16:41Z）：

| 计数 | 值 |
|---|---|
| `episode`（进入追踪的代币 episode） | 112 |
| `admission_attempt`（准入尝试） | 109 |
| **`skip_bucket_full`（因链桶满被拒）** | **73** |
| `bucket_full_chain_full` / `bucket_full_chain_spare` | 72 / 12 |
| `skip_chain_full` | 6 |
| `skip_invalid_input` | 29 |
| **`basic_valid`（拿到完全可用帧）** | **82** |
| `admit_base`（基础准入） | **4** |
| `admit_mover_reserved`（储备准入） | **3** |
| `hydration_hydrated` / `snapshot` | 109 / 109 |
| `cohort_observation` / `pattern_observation` | 78 / 10 |

**读数（并标注限度）**：109 次准入尝试中有 **73 次（67%）**被拒的原因是**链桶已满**；
同时有 **82 个 episode 拿到了完全可用的帧**（价格>0、流动性≥下限、pairAddress 存在、
`observed_at ≤ ingested_at ≤ now` 且新鲜度 ≤30s）。而基础准入只有 4 次。

> **限度**：该 funnel 的计数单位是"每个 episode 每个 stage/reason 计一次"，
> 所以 82 与 (4+3) 不是严格同一分母上的转化率——**不能**报成"95% 的有效帧被丢弃"。
> 能站住的是：**被拒的主导原因是桶满（73/109 = 67%），不是数据无效（29 次 invalid_input）、
> 也不是没有可用帧（82 个 episode 有可用帧）。**

**这就把第 44 轮的推断换成了机制**：不是观测被采到后丢弃，而是**链桶没有空位**。
第 29 轮"约 30 个槽位"的结论、第 44 轮"延迟全部发生在首个快照之前"、
本轮的"67% 尝试因桶满被拒"——**三个独立测量指向同一个约束**。

再次确认：这条约束属于**用户决策的观测预算项**（第 79 轮否决、83/88 轮部分批准）。**本轮不触碰预算。**

## 3. 生产验证：mover-watch 储备注入**确实在工作**（第 33 轮纪律的又一次应用）

`mover_watchlist.py` 自己记录了一个已测量的失败：

> "**Round 101 measured a 0-of-24 overlap** between the flagged set and the leases the observer
> actually holds: reserved admission was only reachable from the rejection path (`skip_bucket_full`),
> and flagged tokens never reached it, so the reservation almost never fired
> (**about 6 admissions/hour against a design of 32**)."

修复函数 `reserved_candidates()` 已写好、**已接线**（`runtime.py:7746-7747`，且有
`tests/test_mover_reserved_wiring.py`）。但**接线+单测通过 ≠ 生产里会触发**（第 31/33 轮的教训），
所以必须看生产计数。运行时把专门为此写的计数器落进 KV `chain-meme-pattern-watch`：

| 计数（23:16:43Z，进程代际 22:01:47Z 起，历时 **1.25 小时**） | 值 |
|---|---|
| `mover_watching`（已用槽位 / 上限） | **22 / 24** |
| `mover_reserved_injections`（**reach**：真的递到候选流） | **261** |
| `mover_reserved_admissions`（**outcome**：最终准入） | **69** |
| 记录到的注入代币 id / 准入代币 id | 27 / 39 |
| overlap(注入, 当前 flagged) | 6 / 27（22%） |

**换算成速率（第 101 轮的同一量纲）：**

| | 准入/小时 |
|---|---|
| 第 101 轮实测（修复前） | **6** |
| **本轮实测（修复后）** | **55.3** |
| 设计目标 | 32 |

**即：修复后是失败基线的 9.2 倍、设计目标的 1.7 倍；flagged∩held 从 0-of-24 变为 22%（6/27）。**

这个修复的方向正是目标关心的**有效性/覆盖率**：`mover_watchlist.py` 自带的测量依据是
"12 个槽位时新增采集量只有 +5.7%（批准 +13~14%），而同一窗口里 67 个 ready 池中 **59 个仍然稀疏、
转化率 0.0%**，密集的转化率 **62.5%**"。储备注入把**已经批准的 24 个槽位**导向 mover 规则标出的候选，
从而在**不增加任何预算**的前提下提高密集度。

> 结论：**已批准预算的使用效率被一个真实的接线/可达性缺陷压住了；该缺陷已被修复并在生产验证。**

## 4. 顺带发现的两个记账项（非交易缺陷）

- **`pattern-admission-shadow`**：`status=DROPPED_AUDIT`、`audit_discontinuous=true`、
  `receipts=47,474` / `written=47,347` / `dropped_audit=98`、
  `bytes=104,795,802`（**约 100 MB / 进程代际**）。它标注 `affects="none"`、`decision_eligible=0`，
  所以不影响交易；但**每代际 100 MB 且已丢弃 98 条回执**，属于研究产物的卫生问题。
  本轮只记录，不修（它不改变任何已观测的交易失败）。
- **`cohort-flow:v1`**（本代际）：`startup_30m` BUY 68 / REJECT 8、
  `steady` BUY 64 / REJECT 10；`TERMINAL_SELL` 52+46、`TERMINAL_WRITEOFF` 16+15。
  按臂：`activity_floor150_t30_v1` BUY 5 / 写下线 1；`v5k` BUY 6 / 写下线 1。

## 5. 本轮对目标五个维度的交代

| 维度 | 本轮的推进 |
|---|---|
| 准确性 | 把"约束=观测槽位"从推断升级为**生产计数器实测**（67% 尝试因桶满被拒）；否定了 discovery 块比例字段可作为丢弃率的用法 |
| 有效性 | **验证并量化了储备注入修复**：6/小时 → **55.3/小时**（设计 32），槽位占用 22/24 |
| 覆盖率 | 同一约束的第三个独立测量；并确认 82/109 的尝试**本来有可用帧** |
| 速度/实时性 | 承接第 44 轮：延迟发生在首个快照之前，机制即本条 |
| 稳定性 | 承接第 44 轮：监督日志与崩溃日志均无新增；本代际运行 1.25 小时正常 |

## 6. 追加规则

- **17**：**接线 + 单测通过，不等于生产里会触发。** 一个机制必须有一个**生产计数器**证明它真的发生了；
  本轮正是靠 `mover_reserved_injections`/`mover_reserved_admissions` 这组"reach vs outcome"计数器
  才能判定修复有效，而不是靠 `tests/test_mover_reserved_wiring.py` 通过。
  （与规则 6 同源，但更强：规则 6 说"上线后要验证"，规则 17 说"**必须先有可验证的计数器**"。）
