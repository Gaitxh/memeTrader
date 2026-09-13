# 第 71 轮记录：全链路漏斗实测（首次），以及我一次性走错了三条代码路径

日期：2026-09-13
前置：`ROUND120_68_RECORD.md`、`ROUND120_69_RECORD.md`
本轮性质：**首次做出用户要求的完整漏斗测量（结论有效）；归因部分我先错了三次，已全部更正并划清边界。**
没有改任何策略、阈值或运行时行为。

---

## 0. 一句话结论

1. **用户要的漏斗测出来了，这是本轮唯一但重要的净新增结果：**

   | 环节 | 数量 | 占发现量 |
   |---|---|---|
   | 发现的不同 token | 17,634 | 100% |
   | 进入入场评估 | 16,583 | **94.04%** |
   | 观测深度 ≥3 帧（合格候选） | 2,259 | 12.8% |
   | 观测深度 ≥50 帧 | 106 | 0.60% |
   | **曾经开过仓的 token** | **77** | **0.44%** |

   **发现环节几乎不漏（94% 都进了评估）。断崖在"合格候选 → 开仓"：2,259 → 77。**
   而 **77 个里有 55 个（71%）来自那 106 个观测 ≥50 帧的 token**（该档开仓率 **51.89%**，
   其余各档 0–0.88%）。

2. **开仓决策本身不是闸门。** `chain_meme_trader_entry_decisions` 全部 7,154 行的
   `status` **全是 `admitted`、`reason` 全是 `pattern_next_observation`**——**一条拒绝都没有**。
   所以损失发生在"候选能否走到开仓那一步"之**前**，不在这条决策语句里。

3. **我这一轮连续走错了三条代码路径**，必须明确记录，因为它们决定了哪些结论不可信：
   - **错误 1**：我按 `store.py:29404-29895`（`historical_fidelity_mode` 分支）归因，
     但本 epoch `definition['historical_fidelity_mode']` 是 **None**，**那个块根本不执行**。
     我用它算出的"325/330 个策略被排除、0 个可达"**全部作废**。
   - **错误 2**：我按 `store.py:30677-30715`（`entry_gate` 五闸门）归因，
     但生产数据里**没有一条** `*_pass` / `*_not_pass` 原因，**那条路径也没跑**。
   - **错误 3**：`Store.chain_meme_trader_policies()` 返回的是**另一套 12 个策略的旧 schema**，
     与运行时的 330 个策略不是同一个集合，我一度据此推理。
4. **正确的入口已经找到**：本 epoch 的 `entry_decisions` 由
   **`store.py:28366-28404`** 写入（`pattern_next_observation`），
   而且**策略级的 1,654 个 `entry_filter` 字段在准入点确实被读取**——
   `store.py:28270` 按 `entry_filter["max_concurrent_positions"]` 分组、`:28295` 按
   `entry_filter["single_token_lifetime_entry"]` 过滤。**所以第 71 轮早先"过滤字段未生效"的说法是错的。**
   真正的准入规则集中在 `28366` 之前的 `ready` / `by_notional` 构造里，**下一轮从那里读**。

---

## 1. 全链路漏斗（实测，全 epoch，n 为不同 token）

| 环节 | 数量 | 占发现量 | 占上一环节 |
|---|---|---|---|
| 发现的不同 token（`tokens`） | 17,634 | 100% | — |
| 出现在发现曝光里 | 19,214 | — | — |
| 拿到原始快照 | 16,583 | **94.04%** | 94.0% |
| 进入入场评估 | 16,583 | 94.04% | **100%** |
| 观测深度 ≥2 帧 | 7,901 | 44.8% | 47.6% |
| 观测深度 ≥3 帧 | **2,259** | 12.8% | 28.6% |
| 观测深度 ≥50 帧 | 106 | 0.60% | — |
| **曾经开过仓** | **77** | **0.44%** | 3.4% |

**观测深度 ↔ 开仓率（实测）：**

| 观测帧数 | token 数 | 曾有仓位 | 比例 |
|---|---|---|---|
| 1 | 10,613 | 12 | 0.11% |
| 2 | 3,743 | 7 | 0.19% |
| 3 | 733 | 1 | 0.14% |
| 4–5 | 332 | 0 | 0.00% |
| 6–9 | 615 | 0 | 0.00% |
| 10–19 | 245 | 0 | 0.00% |
| 20–49 | 227 | 2 | 0.88% |
| **50+** | **106** | **55** | **51.89%** |

**限定（必须一起引用）**：引擎**只记录上行的 running high，没有下行的 running low 列**，
所以 4–19 帧区间的 **0 命中无法用引擎侧的量交叉验证**，
**不作为结论**，只作为待查项。

---

## 2. 合格候选（≥3 帧，n = 2,259）的损失分解

按引擎自己记录的原因字符串分区（一个 token 可带多个原因，取优先级）：

| 去向 | 数量 | 占比 |
|---|---|---|
| 流动性闸门 | 1,242 | 55.0% |
| 无可受理策略 | 901 | 39.9% |
| 无效快照（asof） | 58 | 2.6% |
| **成功转化** | **58** | **2.6%** |

**但"无可受理策略"这个原因字符串本身不可信**（见 §3 错误 1）：它只表示代码里的
`family_arms` 为空，并且会**覆盖**更具体的原因
（`family_episode_already_enrolled_or_cooldown_active`）。所以这张表的第二行
**需要下一轮重新归因**。

**逐小时转化率（同一批合格候选，最终是否开过仓）：**

| 小时（UTC） | 合格候选 | 转化 | 转化率 | cohorts/合格 |
|---|---|---|---|---|
| 18 | 455 | 5 | 1.10% | 0.086 |
| 19 | 447 | 4 | 0.89% | **0.043** |
| 20 | 463 | 15 | 3.24% | 0.184 |
| 21 | 382 | 13 | 3.40% | 0.563 |
| 22 | 209 | 6 | 2.87% | 0.608 |
| 23 | 208 | 14 | **6.73%** | **0.745** |

**早期（19 时）447 个合格候选只产出 19 个 cohort；近期（23 时）208 个产出 155 个。**
约束在**移动**，不是一个恒定闸门。
（转化率按全 epoch 统计，晚出现的 token 观察期更短，故末小时是**上界**，已注明。）

---

## 3. 三条错误代码路径（本轮最重要的教训）

我在同一轮里连续把**三段不同的代码**当成生产路径，并据此得出过三个**错误结论**。

### 错误 1：`historical_fidelity_mode` 分支（`store.py:29404-29895`）

我读了这个块，并算出：
"330 个策略 → 219 个未暂停 → 排除三种观察者模式后 **0 个** → 因此 `market_visible`
（49% 的候选）和 `flow_burst` 结构上不可能被受理 → 98.5% 的策略不参与入场决策"。

**这段推理的每一步都成立，但前提是错的：该分支不执行。**
实测 `definition['historical_fidelity_mode'] = None`。
**上面那些数字全部作废。**

我为什么会走进去：那个块里有一个原因字符串
`no_active_matching_entry_policy`，而我在评估表里看到 **17,591 行**带着它，
就假定写它的是那个块。**实际不是。**（该字符串在 `store.py` 里只出现在 `:29806`，
所以它确实只能由那个块写出——但它写出的那 17,591 行属于**另一个 version / 另一条路径**，
不是本 epoch 的 330 个策略。这一点我还没查清，列为本轮遗留问题。）

### 错误 2：`entry_gate` 五闸门（`store.py:30677-30715`）

这是 `enroll_chain_meme_trader` 里的循环，用 `entry_gate`
（`two_way_route` / `economic_route` / `rug_safety` / `solana_focus` / `shadow_momentum`）
判定，并写 `*_pass` / `*_not_pass` 原因。

**实测：7,154 条 `entry_decisions` 里，`*_pass` 和 `*_not_pass` 各 0 条。那条路径也没跑。**

### 错误 3：`chain_meme_trader_policies()` 的 schema

在空库上调用它返回 **12 个策略**，键是
`family` / `entry_gate` / `take_profit` / `hard_stop_return`…
**没有** `entry_family` / `entry_filter` / `entry_match_mode`。
而运行时的有效定义有 **330 个策略**，两套 schema 完全不同。
我一度按那 12 个推理。**作废。**

### 更正：`entry_filter` 在准入点**确实**被读取

我早先写过"`entry_filter` 的 1,648 个键不被读取"。**这个说法是错的**，实测：

```
store.py:28270   按 entry_filter["max_concurrent_positions"] 分组
store.py:28295   按 entry_filter["single_token_lifetime_entry"] 过滤
```

正确表述：`Store.chain_meme_trader_entry_filter_matches`（`:24304-24366`）
这个**函数**只覆盖 8 个字段名，但**准入逻辑还在别处读 `entry_filter`**。
"某字段是否生效"必须逐个在准入点确认，**不能由单个函数的覆盖面推断**。

---

## 4. 正确的入口（本轮找到，下一轮从这里开始）

**本 epoch 的 `entry_decisions` 由 `store.py:28366-28404` 写入**，特征：

```
28366  for group_index, (notional, cohort_arms) in enumerate(by_notional.items()):
28380      INSERT INTO chain_meme_trader_v6_cohorts(... entry_family='broad_launch' ...)
28394      INSERT INTO chain_meme_trader_entry_decisions(
               ..., "admitted" if enough else "rejected",
               "pattern_next_observation" if enough else
               "ranker_concurrent_slot_limit" if slots >= 3 else "entry_cash_below_order_size")
```

**关键含义：**
- 每条 cohort 的 `entry_family` 被**硬编码成 `'broad_launch'`**（`28380`），
  与前面读到的 `market_visible` / `flow_burst` 家族分派**不是同一条路径**。
- 决策只有三种结果：`admitted`（`enough=True`）、`ranker_concurrent_slot_limit`、
  `entry_cash_below_order_size`。**实测全部是 `admitted`**，另两种 0 条。
- 所以**准入在 `28366` 之前就完成了**——决定哪些候选、哪些臂进入 `by_notional`。
  **真正的闸门在 `ready` / `by_notional` / `active` 的构造处（约 `28150-28366`）。**

**下一轮第一件事：读 `store.py:28150-28370`，把 `ready` → `by_notional` 的过滤链完整列出，
并逐条量它在生产中的命中数。** 这应该就是"候选能不能走到开仓"的真正闸门。

---

## 5. 已知可落地的修复方向（**P0-A 已撤回，其余保留**）

- ~~P0-A 为 `market_visible` / `flow_burst` 家族新增 `dex_visible` 策略~~——
  **撤回**：它建立在错误 1 的前提上，而该分支不执行。
  `dex_visible` 确实作为模式存在于代码里（`store.py:23784-85`），
  但**是否与生产路径相关尚未确认**，在确认前不得据此新增策略。
- **P0-B（保留，纯可观测性）**：`no_active_matching_entry_policy` 这个原因字符串
  会覆盖更具体的原因（`store.py:29806` 覆盖 `:29715`），而它今天让我做了三小时的错误归因。
  最小改动是**新增**一个字段记录被覆盖的原因，不动判定逻辑。
- **P1（保留）**：把 `entry_filter` 的 145 个字段名逐个映射到**真正读取它的代码位置**，
  产出"已强制 / 未强制 / 由别处强制"三类清单。这是"准确性"目标下最有价值的一项。
- **P1（保留）**：区分 `entry_pool_liquidity_absent_curve_stage`（曲线阶段判定）与
  `below_configured_floor`（正确拒绝）。实测前者的 5,398 个 token **全部**在
  `token_market_surfaces` 和 `token_snapshots` 里有记录，更像曲线阶段判定而非数据缺失。

---

## 6. 遗留问题（下一轮优先）

1. **`no_active_matching_entry_policy` 那 17,591 行属于哪条路径？**
   它只能由 `store.py:29806` 写出，而该行在 `historical_fidelity_mode` 分支内，
   本 epoch 该开关是 `None`。**必须查清是哪个 version / 哪次运行写的**，
   否则评估表的这个原因分布会继续误导。
2. **`store.py:28150-28370` 的准入过滤链**——本轮最该做但未做的事（见 §4）。
3. **12 个 vs 127 个 vs 330 个策略的确切关系**：已知
   `policy_additions` 330 行 = 有效定义 330 个（`runtime_addition_id` 全部非空）、
   `registration.definition_json` 里只有 127 个。**127 与 330 的差集是什么？**
4. 下行侧深度门槛（4–19 帧命中 0）无法用引擎侧的量验证，暂不作为结论。

---

## 7. 复现脚本

全部在 `data/research/diag_round120/`（gitignored）：

| 脚本 | 作用 | 可信度 |
|---|---|---|
| `r71_arithmetic_audit.py` | 第 70 轮算术与分母审计（发现 3 处错误） | 有效 |
| `r71b_funnel.py` | **全链路漏斗 + 每 cohort 臂数分布** | **有效** |
| `r71c_collapse.py` | 原因分布 + 深度分档 | 分布有效，归因待重做 |
| `r71d_gates.py` | 深度分档复核 + 硬闸门测试 | 有效（限定见 §1） |
| `r71e_conversion.py` | **合格候选转化率 + 逐小时** | **有效** |
| `r71f`–`r71i` | 闸门明细、谓词枚举 | **基于错误路径，作废** |
| `r71j_runtime_policies.py` | 运行时策略列表（发现 schema 不一致） | 有效（否定性证据） |
| `r71l`/`r71m`/`r71n` | 有效定义过滤器链 | **基于错误路径，作废** |
| `r71o_reconcile.py` | **发现 `historical_fidelity_mode=None`** | **有效（本轮关键更正）** |
| `r71p_live_gates.py` | **实测 7,154 条决策全部 admitted** | **有效（本轮关键更正）** |

---

## 8. 对第 70 轮结论的更正（保留）

| 第 70 轮所写 | 实测 |
|---|---|
| "960 个 cohort" | **690** 个产生了仓位（`v6_cohorts` 977 行，其中 287 个没产生仓位） |
| "每个 cohort 约 4.06 个臂" | 分布**双峰**：**42.5% 的 cohort 只有 1 个臂**，2.2% 有 41+ 个臂；均值 5.65，**均值会误导** |
| "约 160 cohorts/小时" | **116** cohorts/小时（690 / 5.93h） |

"持仓槽位利用率只有 7.08%"不受影响（171 开仓 / 330×8 = 2,640 → 6.48%）。
分母口径必须标注：`policy_additions` 330 是已注册集合，控制台 457 是引擎构建的全部策略。
