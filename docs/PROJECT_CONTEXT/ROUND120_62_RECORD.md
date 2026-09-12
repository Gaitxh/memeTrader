# ROUND 120-62 — 我在两轮内**三次**犯了同一个错误：把"注册的策略"当成"生效的策略"

日期：2026-09-13
探针：`data/research/diag_round120/r62_concurrency.py`、`r62b_correction.py`、`r62c_effective.py`、`r62d_notional_effective.py`
改动：改写第 61 轮我加进 `exits150.py` / `exit_ladder150.py` 的注释（它们断言了错误结论）
更正：`ROUND120_61_RECORD.md` 加更正横幅 + 检查点 §61 条目更正

---

## 1. 起因与三次错误

**错误 1（第 62 轮 r62）**：我看到 `exit150_widestop_v1` 峰值并发 **9**、各退出臂 **8**，
而注册的 `max_concurrent_positions` 是 2（entry_filter）或 4（顶层），
于是断定"**每臂并发上限未被强制执行**"。**我只看了观测峰值，没有读执行路径。**

**错误 2（第 62 轮 r62b）**：读到 `store.py:301 CHAIN_MEME_TRADER_CONCURRENCY_CAP_FLOOR = 8`
与 `store.py:27799` 的执行点后，我改用"峰值 vs 生效上限"比较——
**但我取的"生效上限"来自 `policy_additions.policy_json`**，而那是**注册值**，
于是得出"89 个臂超出上限"。**又错了，且错在同一个地方。**

**错误 3（第 61 轮，回溯发现）**：我断定"每臂 `notional_usd` 是**死字段**、运行时从不读取"。
**错误 2 让我意识到必须去读生效定义**——一读就发现生效定义里有一块
**`uniform_notional_usd`**，它**正是读了 `notional_usd` 并把它统一改写为 20U**。

## 2. 正确答案：**生效定义**才有权威，注册 JSON 是草稿

`Store._chain_meme_trader_effective_definition(version, definition_json)` 在加载时重建定义，
并应用**有记录、有授权依据**的修订。实测（本账期）：

| 生效定义中的块 | 内容 |
|---|---|
| **`concurrency_cap_floor`** | `{"floor": 8, "raised_policies": 240, "filled_uncapped_policies": 78, "authorized_at": "2026-09-12", "basis": "user instruction: every strategy gets a cap of 8 - values below it are raised and arms that registered no cap are given one"}` |
| **`uniform_notional_usd`** | `{"notional_usd": 20.0, "changed_policies": 280, "authorized_at": "2026-09-12", "basis": "user instruction: one uniform 20U per trade so strategies can be compared fairly; policies without the field already resolve to the definition default, which is this same size"}` |

**生效分布（457 个策略）：**

- `max_concurrent_positions` = **{8: 457}** —— **全部统一为 8**；445 个臂带 `concurrency_cap_revision`
- `notional_usd` = **{20.0: 311, None: 146}** —— None 落到定义默认 `policy_notional_usd = 20.0`

**逐臂实例（我此前读错的那些）：**

| 臂 | 注册 notional → 生效 | 注册 cap → 生效 |
|---|---|---|
| `exit150_full15_v1` | 1.0 → **20.0** | 2 → **8** |
| `exit150_widestop_v1` | 1.0 → **20.0** | 2 → **8** |
| `exit_ladder150_t10_v1` | 1.0 → **20.0** | 2 → **8** |
| `activity_floor150_t30_v1` | 2.0 → **20.0** | 2 → **8** |
| `organic_early_flow_v1` | 2.0 → **20.0** | 2 → **8** |

## 3. 修正后的正确结论

**（a）并发上限是被强制执行的，生效值统一为 8。**

- 执行点：`store.py:27799` `if arm in limited and occupied[arm] >= limited[arm]:
  entry_blocked[arm] = "strategy_open_slot_limit"`，其中 `occupied[arm]` = 该臂 `status='open'` 的计数。
- **它确实在触发**：13,679 次评估的 `feature_json` 里出现该理由。
- **峰值 vs 生效上限**：182 个可比臂中，**12 个恰好停在 8（上限在起作用）**、
  169 个低于 8、**只有 1 个超出（`exit150_widestop_v1` 峰值 9，+1）**。
- 那 +1 与"上限在每次观测上检查、多个观测在提交前都看到余量"一致，属于边界效应。

**（b）每仓 20U 是刻意统一的结果，不是字段失效。**

- 每臂并发暴露 **8 × 20U = 160U**；对 1,000U 起始资金是 **16%**。
- 这是一个**刻意统一、可解释、有授权记录的设计**（"让各策略可以公平比较"），不是缺陷。

**（c）我在第 61 轮加进源码的注释是错的，已改写。**

我写的是"`notional_usd` 是死字段、运行时从不读取"。实际是：**运行时读了它，并把低于统一值的部分抬高**。
两处注释已改写为正确表述，并附上"注册 JSON 是草稿"这一通用教训。
`ROUND120_61_RECORD.md` 加了更正横幅。

**（d）仍然成立的部分**：第 61 轮 §2 的结论——**我报告过的四组对比与检查点表格全部同规模（20U），
因而可比、无需更正**——不受影响。描述里的 "1U×4仓" 相对生效契约确实过时，但**原因不是"死字段"**。

## 4. 追加规则（本次是两轮内第三次同类错误，规则要写得更硬）

- **37**：**`policy_additions.policy_json` 是草稿；生效的是加载时重建的生效定义。**
  在依据**任何**限额、规模、阈值或契约字段推理之前，必须先调用
  `Store._chain_meme_trader_effective_definition(...)` 并读**生效值**。
  本 session 因为读草稿而错了三次（r61 notional、r62 并发"未执行"、r62b "89 臂超限"），
  **其中两次是在我已经写下"先验证再推理"这条规则之后犯的**。
- **38**：**"未被强制执行"这个结论只能由执行路径的代码得出，不能由观测峰值反推。**
  峰值既可以因为"没有上限"而高，也可以因为"上限更高"而高；
  本轮的 9/8 峰值正是因为生效上限是 8（而非注册的 2）。**先读执行点，再读生效值，最后才比峰值。**

## 5. 对目标五维度的交代

| 维度 | 推进 |
|---|---|
| **准确性** | 更正了三个错误结论（含我自己刚写进源码的注释）；确立"注册 vs 生效"的正确读数路径 |
| **风控**（任务书点名视角） | 给出**正确的**每臂风险画像：统一 20U/仓、上限 8、**每臂最多 160U 并发暴露 = 起始资金 16%**；并确认上限确实在触发（13,679 次） |
| 稳定性/有效性 | 未触碰任何行为：本轮只有注释与文档更正 |
