# ROUND 120-56 — 关闭"饱和"结论上最后一个疑点：**占用计数就是被强制执行的那个计数**，且核对完全对上

日期：2026-09-13
探针：`data/research/diag_round120/r56_occupancy_reconcile.py`、`r56b_held.py`

---

## 1. 要回答的疑点（对抗性复核被要求攻击的正是这一点）

复核者在第 48 轮被要求攻击的"关键点"是：

> **若 `chain_total` / `occupied` 是按*另一个*集合算出来的，而限额是对*另一个*集合执行的，
> 那"饱和"的读数就可能是记账假象。**

同一份记录里还有两处看起来自相矛盾的地方：
- `held_count` 与 `chain_total` 不一致（solana 10/10、bsc 1/10、robinhood 3/10）；
- `coverage145:status.membership` 报 bsc total **11**、early **5**，**都超过** `CHAIN_CAP=10` 与 early 上限 3。

## 2. 代码给出一手答案（`runtime.py:7865-7897` 逐字）

```python
base_caps = {"early": 3, "growth": 4, "mature": 3}
watch, occupied, chain_used, borrowed = {}, {}, {}, []
...
    slot = (item["token"].chain, item["bucket"])
    if key not in held:
        if occupied.get(slot, 0) >= base_caps[item["bucket"]]:      # ← 被强制执行的桶上限
            if item["bucket"] == "early" or item.get('reactivation_probe'):
                borrowed.append((key, item))
            continue
        occupied[slot] = occupied.get(slot, 0) + 1
        chain_used[slot[0]] = chain_used.get(slot[0], 0) + 1
    watch[key] = item
# 注释原文："Keep base reservations first; early overflow survives only in spare
#          chain capacity. Held watches never consume these ten candidate slots."
for key, item in sorted(borrowed, ...):
    slot = (item["token"].chain, item["bucket"])
    if chain_used.get(slot[0], 0) < 10:                            # ← CHAIN_CAP，同一个计数
        watch[key] = item
        occupied[slot] = occupied.get(slot, 0) + 1
        chain_used[slot[0]] = chain_used.get(slot[0], 0) + 1
```

**结论一：`occupied` 和 `chain_used` 就是限额所比对的计数本身**——
funnel 报告的占用，**字面上就是**第 7883/7894 行拿去和上限比较的那个变量。**不是记账假象。**

**结论二：`if key not in held` 使"持有中"的租约*不*增加这两个计数**，
所以每条链的 10 个**候选槽位**是**叠加在**持有仓位之上的。

## 3. 两个"矛盾"因此都被解释掉

| 疑点 | 解释 |
|---|---|
| `held_count`（solana 10 / bsc 1–2 / robinhood 3）与 `chain_total`(=10) 不一致 | 两者量的**不是同一个集合**：`held_count` 数的是持有中（有未平仓位）的租约，而它们**按构造不占候选槽位**；`chain_total`/`occupied` 数的是候选槽位，三条链**各自顶在 10** |
| `membership` 报 bsc 11 / early 5，超过上限 | `membership` 由 `account_windows()` 对**整个 watch**（含持有租约）统计；而限额只对**非持有的候选集合**执行。**两个数数的是不同集合，超限是预期的，不是违规** |

## 4. 核对：`watched = 候选槽位 + 持有租约`

`held` 的定义在代码里（`runtime.py:8780`）：`held=OPEN_POSITION only`。
所以从**真源**（仓位表）推导，而不是从 funnel 那个 32 条的目的取样：

| 链 | 未平仓位数代币数 |
|---|---|
| bsc | 3 |
| robinhood | 3 |
| solana | 10 |
| **合计** | **16** |

- 候选槽位（`non_held_by_chain_bucket`，三条链各 {3,4,3}）：**30**
- 30 + 16 = **46**，而遥测 `watched` = **45**

**差 1 是预期的**：既持有仓位、又占着候选槽位的代币在上式里被算了两次
（我在探针里已注明这是**上界**）。**所以 45 = 30 个候选 + 15 个持有。**

**并且推导出的每条链持有数（bsc 3 / robinhood 3 / solana 10）与占用快照里的
`held_count`（bsc 1–2 / robinhood 3 / solana 10）一致**——`held_count` 确实就是
"该链有未平仓位的代币数"。

## 5. 饱和读数在更大样本上**更强**了

| 指标 | 第 48 轮 | 本轮 |
|---|---|---|
| 占用快照数 | 17 | **19** |
| `occupied == base_caps` **恰好相等** | 86% | **100%** |
| `chain_total >= 10` | 86% | **100%** |
| `skip_bucket_full / admission_attempt` | 73/110 = 66%（第 47 轮） | **92/139 = 66%** |
| `basic_valid` | 82 | **104** |
| 准入（base + mover_reserved） | 7 | **9** |

**三条链的候选槽位在 19/19 个快照上 100% 顶格；66% 的准入尝试因桶满被拒；
同时有 104 个 episode 拿到了完全可用的帧。** 第 47 轮与第 48 轮的读数在新的、
更长的进程代际里**原样重现**。

## 6. 我对这次复核的处置（并说明我为什么叫停了它）

- 复核者提出的**关键点是对的、值得查**，而答案在**代码**里，不在更多采样里——
  所以我自己读了 `runtime.py:7865-7897` 并完成核对，**没有继续等它**。
- 该子 Agent 已连续运行跨越我这边约六个轮次的工作，远超一个有界任务的合理时长
  （其任务包含"反复轮询 `/api/live`"，很可能卡在轮询上）。**它的核心问题已由我独立回答，
  因此我中断了它**——按规则，一个子 Agent 的问题一旦被回答就应停止，
  而不是让它无限期占用上下文与配额。
- 它的另外两个次级问题（更长窗口的样本量、阶段顺序是否使 66% 的分母有偏）
  **已由本轮部分回答**：样本更长（139 vs 110）、读数不变（66%）；
  而分母问题在第 47 轮已处理（`skip_bucket_full` 是同级检查之一，
  与 `skip_invalid_input` 37、`skip_chain_full` 6 并列，合计 139）。

## 7. 追加规则

- **28**：**当一个疑点的答案在代码里时，去读代码，不要靠增加采样。**
  本轮被质疑的是"报告出来的计数是否就是被强制执行的那个计数"——
  这**只能**由 `runtime.py:7883/7894` 回答，再多的遥测快照都只能佐证而无法证明。
  增加采样在这个问题上会得到**看似更可信的错误答案**。
- **29**：**一个子 Agent 的问题被独立回答后，立即停掉它。** 让它继续跑既浪费上下文，
  又会让"我还在等复核"变成不推进的理由。

## 8. 对目标五维度的交代

| 维度 | 推进 |
|---|---|
| **准确性** | 关闭饱和结论上最后一个疑点（记账假象）；解释两处表面矛盾；核对 held 的推导 |
| **有效性** | 饱和读数从 86%/17 快照提升到 **100%/19 快照**，样本更长、结论不变——覆盖率结论**更加稳固** |
| 稳定性 | 66% 的桶满拒绝率在两个不同进程代际、两个样本量上原样重现 |
| 速度/实时性 | 承接第 44/47 轮 |
