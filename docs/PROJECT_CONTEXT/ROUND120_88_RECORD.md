# 第 88 轮记录：诊断注册表已满并**静默重置计数器**——我差点又一次用它的"缺席"下结论

日期：2026-09-13
前置：`ROUND120_87_RECORD.md`（本轮对其**输入描述**作了更正）
本轮性质：**先更正上一轮的一处机制描述；再修掉一个使整条可观测性链不可信的缺陷；
最后把一个失败的测试从"store 的 bug"归因到正确的层。**
交易路径、策略与阈值**一律未改**；唯一的代码改动在诊断计时器（`runtime_timing.py`）。

---

## 0. 一句话结论

1. **更正第 87 轮**：`shared_batch148.offer` 有**两个**调用点，不是一个。
   第 87 轮只写了 `runtime.py:8134-8137`（被拒堆）。第二个是
   **`runtime.py:8538-8550`**——一条专门的 **ALPHA149 帧供给环**：遍历本批报价，
   挑出 `trajectory149` 池**帧数 < 3**、**池龄 ≤ 900 秒**的身份，每批最多 6 个去 `offer()`，
   目的就是给"引擎几乎还没观测过的年轻池"补上策略窗口需要的独立帧。
   **机制与量级不受影响**（两个入口共用同一个 `offer()` 门，来源名条件仍挡掉约 91 倍）。

2. **本轮真正修掉的缺陷：诊断注册表（`RuntimeTiming`）已结构性超订，并且会静默重置计数器。**

   | 项 | 实测 |
   |---|---|
   | 注册表容量 `MAX_COMPONENTS` | **32** |
   | 运行时注册的名字 | **43 个周期环 + 12 个临时观测器 = 55** |
   | 任一瞬间可见 | 32 |
   | **当前不在 payload 里的周期环** | **25 个** |
   | 其中包含 | **`position_monitor`、`dexscreener_discovery`、`source_health`、`external_sources`、`reverse_news`、`event_evaluation`、`shadow_event_followup`、`token_information_watch` …** |

   而且**淘汰会把计数清零**——3 分钟内直接实测到两次下降：
   **`pattern_token_compute` `items` 415 → 22**、**`learning145_flush` 5 → 0**。
   （`observe()` 是 `items += n`，所以下降**只能**来自 `runtime_timing.py:101-102` 的
   淘汰重建——新建条目从 0 开始。）

3. **我差点因此发布一个假结论。** 本轮我先看到 `alpha149_coverage_offers` **不在 32 个组件里**，
   正要写"这条通道从未成功过一次"。**先查了容量**，发现正好 32/32——
   **满载之下，缺席什么都不能证明**。这与第 86 轮"面板被截断"是同一类错误，第二次遇到。

4. **修法不是把上限调大。** payload 现在是 **109,148 字符、每 10 秒写一次**
   （`runtime.py:9769`）；把 32 提到 96 会把这份写入**变成约三倍**去换回同样那 55 个名字。
   **改用一个永不被淘汰的单调账本**：`snapshot()["activity"]` 记录**每一个出现过的名字**的
   `calls` / `items` / `failures`，并且顺带回答了"这条环到底跑过没有"——这正是本轮卡住的问题。

   **成本实测（我先估错了一次，见 §1 错误 2）**：`activity` 块 **56.7 字符/名字**，
   55 个名字约 **3.1 KB**，即 payload **约 +2.9%**；而把上限提到 96 是 **约 +190%**。

5. **顺带把一个失败测试归因到正确的层。**
   `test_first_pool_failure_then_same_pool_quote_side_recovery` 在本轮开始前就已失败
   （用 `git stash` 验证过：**改动前同样失败**）。我没有直接猜，而是**把 store 单独拿出来实测**：
   - 失败后 → `UNKNOWN`
   - **观察到更新的报价 → `VISIBLE`（恢复路径正常）**
   - 再次失败时状态**保持 `VISIBLE`**——因为失败的 `CASE` 只把 `MISSING` 降级为 `UNKNOWN`

   **∴ store 无罪，问题在 runtime 的 `complementary_market_data_once` 路由/门控。**
   这是一个**已定位未修**的 P0，下一步是插桩 `chunk` / `usable()` / `applied` 三者哪一个丢了该身份。

---

## 1. 我本轮自己错了两次，两条都保留可见

### 错误 1：差一点又一次用"计数器缺席"下结论

本轮我先看到 `alpha149_coverage_offers` 不在 32 个组件里，正要写
"这条帧供给环从未成功过一次"。**先查了容量**：正好 32/32 满载，
而运行时注册 55 个名字 ⇒ **满载之下缺席什么都证明不了**。
这与第 86 轮"把被截断的面板当总体"是同一类错误，**三轮之内第二次**。已升级为常设规则 48。

### 错误 2：把整份 payload 除以名字数，得出"每个名字 286 字符"

收尾验证时我打印了 `snapshot JSON = 9,177 字符 / 45 个名字`，顺手写成 **286 字符/名字**，
并用它估"账本约 +2 KB"。**那 9,177 字符是整份快照（含 `components` 块）**，不是 `activity` 块。
单独量：`activity` 块 32 个名字 = **1,814 字符 = 56.7 字符/名字**，
55 个名字约 **3.1 KB（+2.9%）**。

**结论方向没变（3.1 KB ≪ 210 KB），但数字必须用实测的。**
这正是我在第 84/85 轮反复引用的规则的又一次应用：**别拿一个混合整体去除以一个局部分母。**

---

## 1.5 为什么注册表满载是**交易相关**的缺陷，不只是工具问题

用户的目标里明确要求"全链路可观测性与持续学习闭环"。注册表满载直接破坏三件事：

1. **看不到关键的环。** `position_monitor`（持仓监控）、`dexscreener_discovery`（发现）、
   `source_health`（数据源健康）、`external_sources`、`reverse_news` —— 这些正是
   "发现 → 采集"这一段的核心环，**当前全部不在 payload 里**。
   要回答"发现是否变慢/是否健康"，运行时自己的读数给不出。
2. **任何"计数为 0 / 不存在 ⇒ 该路径没跑"的推理都失效。** 本轮我自己就险些这么做。
3. **累计量对冷组件是错的。** 被淘汰重建后 `items` 从 0 重新开始，
   所以 `pattern_token_compute` 的真实累计值**大于**读数，而没人知道大多少。

---

## 2. 改动内容（唯一一处代码改动，纯仪表）

**`src/memetrader/runtime_timing.py`**

- 新增 `self._activity: dict[str, dict[str, int]]`，在 `observe()` 中**先于淘汰逻辑**更新，
  **永不被淘汰**，记录每个名字的 `calls` / `items` / `failures`。
- `snapshot()` 新增 `"activity"` 块（按名字排序，payload 字节稳定、diff 干净）。
- `"components"` 块的语义**完全不变**（仍是有界 LRU 视图），因此既有断言不受影响。
- 类 docstring 写明**为什么是两个注册表**，并把第 88 轮的实测数字留在代码里。

**没有**改 `MAX_COMPONENTS`——理由见 §0.4（成本/收益），也写进了 docstring。

生效时机：**下一次进程重启时**。本轮**没有重启运行时**（它健康，pid 34800 自 2026-09-13T07:42:10 未变）。

---

## 3. 免费搭车帧的真实去向（第 87 轮问题的补完）

顺着 `_remember_pattern_quotes(..., feature_only148=...)` 追到消费端
`chain_meme_cohort_observer_once`（`runtime.py:8443-8473`）：

| 事实 | 代码位置 |
|---|---|
| **ALPHA149 消费每一个观测帧，明确包括 feature-only 搭车帧** | `runtime.py:8454-8457`（注释原文："ALPHA149 consumes every observed frame (including feature-only spares) so its own arms see a denser, independent frame supply"） |
| 但每批**最多 6 个** feature-only 帧、或**累计计算 5 毫秒**，超出即延后 | `runtime.py:8447` |
| 而且 feature-only 帧**被排除**在 `consume_passive_cohort_batch` 之外 | `runtime.py:8473` `legacy_frames=[f for f in frames if f['token_id'] not in extra148]` |

**∴ 零成本搭车帧只能产出 ALPHA149 的信号**——恰好是那个 `dense_watch_breakout`
要求 **`pair_frames ≥ 8`** 的引擎（`alpha149.py:1346-1349`），也正是它自己注释里写的
"实测最强判别：金狗 74 帧 vs 对照 6 帧"。

**同时要给出量级边界**：`alpha149_features` 累计 **90,783** 帧、`trajectory144_features` 同为 90,783，
而搭车车道的 `BATCH_EXTRA_IDENTITIES` 只有 **243** 个身份（每个 8–13 帧）——
**搭车帧只占 ALPHA149 帧供给的很小一部分**。它的价值不在"总量"，而在
**为被它租下的少数代币凑够 ≥8 帧的深度**。

---

## 4. 复现脚本

| 脚本 | 作用 |
|---|---|
| `r88_components.py` | **注册表容量 vs 成员**：32/32 满载 ⇒ 缺席不可解读 |
| `r88b_registry_thrash.py` | **淘汰的直接证明**：逐 20 秒采样，抓到 `items` 下降（415→22、5→0） |
| `r88c_component_names.py` | 源码字面量计数（第一版正则不全，**不作为结论**） |
| `r88d_periodic_count.py` | **43 个周期环 + 12 个观测器 = 55 个名字**，25 个环当前不可见 |
| `r88e_pool_recovery.py` | **store 单独实测**：恢复路径正常 ⇒ 失败测试不在 store 层 |

**测试**：`tests/test_runtime_timing.py` **6 → 8 个**，新增
`test_activity_ledger_survives_eviction_and_never_decreases`（先断言该组件**确实被淘汰**，
再断言账本单调，否则测试本身没有意义）与
`test_activity_ledger_names_every_component_ever_observed`。

---

## 5. 待办（本轮定位、未修）

| 优先级 | 事项 | 已知证据 | 下一步 |
|---|---|---|---|
| **P0** | `complementary_market_data_once` 的同池恢复**没有更新 pool mark**（测试在 HEAD 即失败） | store 已实测无罪；失败路径的 `CASE` 只降级 `MISSING`，所以不是"状态机拒绝升级" | 插桩 `chunk` / `usable()` / `applied` / `_market_pool_gaps`，看身份在哪一步被丢 |
| P0 | 第 87 轮的免费搭车扩宽 | 8 通过 vs 725 只因来源名被拒 | **必须作为新增额外策略模块**落地 |
| P1 | 注册表改动的落地观测 | 本轮改的是仪表，需重启才生效 | 下次重启后确认 `activity` 块出现且 `alpha149_coverage_offers` 可读 |

---

## 6. 新增常设规则（接 §10.6 同族，编号 48–50）

48. **满载的注册表里，"缺席"不是证据。**
    诊断注册表容量 32，运行时注册 55 个名字，25 个周期环因此不可见；
    我据此差点写下"这条路径从未成功"。**读任何"计数器缺席/为 0"之前，先读那张表的容量与淘汰策略。**
    （与第 86 轮"面板被截断"同类，这是我第二次犯。）

49. **一个会淘汰条目的表，其累计计数不是累计量。**
    `items += n` 只在**同一条目生命周期内**单调；淘汰重建从 0 开始。
    实测 `pattern_token_compute` 415 → 22、`learning145_flush` 5 → 0。
    **要么把总量放在不受淘汰影响的账本里，要么别把它叫累计值。**

50. **提高一个上限之前，先算它的写入代价。**
    把 `MAX_COMPONENTS` 32 → 96 会把一份 **109 KB / 10 秒**的 payload 写入变成三倍，
    只为换回同样 55 个名字；而单调账本只要 **+2 KB** 就同时解决可见性与计数重置。
    **上限不是唯一的旋钮——先问"我真正缺的是容量，还是缺一个不受容量影响的地方"。**
