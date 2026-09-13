# 第 89 轮记录：一个"只接受更新数据"的守卫，把它自己写进去的**尝试时钟**当成了数据时间

日期：2026-09-13
前置：`ROUND120_88_RECORD.md`
本轮性质：**把第 88 轮"已定位未修"的 P0 修掉——先证明机制，再量爆炸半径，最后用一行判别字段
把放宽范围围起来。**
改了 `store.py` 的一处 `WHERE` 子句；**策略、阈值、交易路径未改**。

---

## 0. 一句话结论

1. 第 88 轮把失败测试 `test_first_pool_failure_then_same_pool_quote_side_recovery`
   归因到 runtime 路由，并把 store 排除在外。**第 89 轮用逐步插桩证明：路由其实完全跑通了。**
   失败路径上每一个门都通过：

   ```
   queued gaps              : [(token, pool)]         ← gap 入队正常
   _dex_quote_low_priority_available: True
   exact_pools_fresh CALLED : chain=robinhood pools=[pool]
   apply batch CALLED       : 2 outcomes, kinds=['pool_visible','visible']
   usable() invocations     : 3     rejections: []
   ```

   **批次被应用了、`usable()` 零拒绝，但 `pool_marks` 那一行没有变。**

2. **真正的机制（已量到字节级）**：

   | | |
   |---|---|
   | 失败路径写入的行内 `observed_at`（= 它的**尝试时钟**） | `2026-09-13T02:21:21.414848Z` |
   | 恢复报价的数据时间 `excluded.observed_at` | `2026-09-13T02:21:21.414848Z` |
   | **`excluded > stored`？** | **False ⇒ 更新被跳过** |

   `record_chain_meme_trader_pool_mark_failure` 把 `attempted_at` 写进 `observed_at`
   （`store.py:32814-32815`），而 `upsert_chain_meme_trader_pool_mark` 只在
   `observed_at IS NULL OR excluded.observed_at > observed_at` 时更新
   （`store.py:32755-32756`）。**列声明是 `TEXT NOT NULL`，所以 `IS NULL` 那个分支永远不可达**——
   `>` 是唯一的通路。

3. **为什么两个时间戳会逐字节相同：本机时钟粒度很粗。**
   实测：连续 8 次 `datetime.now(UTC)` **返回 1 个不同的值**；
   紧循环要跑 336 次才跳变。**相隔几条语句的两次取时返回同一瞬间是常态，不是巧合。**

4. **但生产足迹是零——这一点必须和机制一起说。**
   线上 `chain_meme_trader_pool_marks` **1,973 行**：

   | 项 | 实测 |
   |---|---|
   | `VISIBLE` | **1,943（99.8%）** |
   | `UNKNOWN` | 3–4 |
   | **有 `last_success_at` 却不 VISIBLE 的行** | **0** |
   | **`observed_at > last_success_at`（墙钟写进数据列）的行** | **0** |

   现有的 4 条非 VISIBLE 行**不是时间戳并列的受害者**：它们的
   `observed_at != last_attempt_at`，`failure_kind` 是 `TimeoutError` /
   `DATA_REJECTED:QUOTE_USD_UNKNOWN,quote_liquidity_unavailable`，价格 0.0
   ——**是确实没拿到可用报价**。

   **∴ 这是一个"真实但潜伏"的缺陷：它确定性地产出一个失败测试，
   并且意味着"与失败同一时钟刻度内到达的第一次恢复会被静默丢弃"。**

5. **修法：放宽时用数据自己的状态把它围起来。**
   `WHERE observed_at IS NULL OR sample_sequence = 0 OR excluded.observed_at > observed_at`。
   `sample_sequence` **只有成功路径才会 +1**（失败与 miss 路径都写 0），
   所以新分支**恰好**覆盖"从未有过真实样本"的行，**已经持有数据的行保持严格的"新者胜"规则**。

   **爆炸半径（实测）**：`sample_sequence = 0` 的行 **4 / 1,973 = 0.20%**，
   其中**没有一行当前是 VISIBLE** ⇒ 未来行为可能不同的行 **4 条**；
   其余 **1,969 行**行为完全不变。

6. **回归证据：**
   - 修复前：`test_first_pool_failure_then_same_pool_quote_side_recovery` **失败**（第 88 轮已用
     `git stash` 证明与我的改动无关）；修复后 **通过**。
   - `tests/test_market_api_runtime.py` **32 / 32 通过**。
   - `tests/test_core.py`：**修复前后同样 11 个失败，集合完全相同**（用 `git stash` 逐次对比）
     ——**零回归**，那 11 个是仓库里既有的失败。
   - 新增 `tests/test_pool_mark_recovery.py` **4 个测试**：把 `store.py` 的改动 stash 掉之后，
     **其中 2 个失败、2 个仍通过**——恰好是"新放宽"的两个翻转，"严格规则仍然成立"的两个不动。

---

## 1. 我本轮自己错了一次，保留可见

**我的探针复用一个固定目录，于是第二次运行"通过"了。**
第一次运行复现了失败（`FINAL status='UNKNOWN'`），第二次却打印 `FINAL status='VISIBLE'`，
我一度以为"修复生效了"。真正的原因是：**第一次运行已经在库里留下了一行 VISIBLE**，
而 `record_chain_meme_trader_pool_mark_failure` 的 `CASE` **只把 `MISSING` 降级为 `UNKNOWN`**
（`store.py:32817-32818`），已 VISIBLE 的行**安然穿过失败**，
于是"失败→恢复"的断言变得平凡成立。

**∴ 那个"通过"测的是上一次运行的残留，不是代码。**
改为每次运行使用唯一目录后，失败立刻稳定复现。
**验证脚本必须从干净状态开始，否则它测的是历史。**（升级为常设规则 52。）

---

## 2. 复现脚本

| 脚本 | 作用 |
|---|---|
| `r89_why_recovery_drops.py` | **逐步插桩**：五个可能的丢弃点逐个排除，最后锁定到 upsert 的时间戳守卫 |
| `r89b_clock_and_footprint.py` | **时钟粒度**（8 次取时 1 个值）+ 线上足迹（0 条被阻塞的恢复） |
| `r89e_blast_radius.py` | **逐行爆炸半径**：`sample_sequence = 0` 的 4 行，及其失败原因 |

**测试**：新增 `tests/test_pool_mark_recovery.py`（4 个）：
- `test_first_observation_is_accepted_when_the_failure_stamp_ties`（**stash 后失败**）
- `test_a_missing_row_without_history_does_accept_its_first_quote`（**stash 后失败**）
- `test_a_row_with_history_keeps_the_strict_newest_wins_rule`（两边都通过）
- `test_a_missing_row_with_history_refuses_a_stale_quote`（两边都通过）

---

## 3. 待办

| 优先级 | 事项 | 状态 |
|---|---|---|
| **P0** | 第 87 轮的免费搭车扩宽（来源名条件挡掉约 725/小时） | **未动**，必须作为新增额外策略模块 |
| **P0** | `alpha149_coverage_offers` 可观测性 | 第 88 轮的 `activity` 账本下次重启后生效，届时可读 |
| P1 | `test_core.py` 的 11 个既有失败 | 本轮确认与本次改动无关；**未诊断** |
| P1 | 三个来源名/来源失败率不同的池（`TimeoutError`、`QUOTE_USD_UNKNOWN`） | 属数据源问题，非本缺陷 |

---

## 4. 新增常设规则（接 §10.6 同族，编号 51–53）

51. **写时间戳的路径与读时间戳的守卫，必须约定同一个时钟语义。**
    `record_chain_meme_trader_pool_mark_failure` 把**尝试时钟**写进 `observed_at`（数据时间列），
    而守卫只在 `excluded.observed_at > observed_at` 时放行；**该列还是 `NOT NULL`，
    所以守卫里的 `IS NULL` 分支永远不可达**。在时钟粒度粗的平台上（实测连续 8 次取时返回 1 个值），
    失败戳与下一次真实观测可以**逐字节相同**，恢复被静默丢弃。
    **写进"数据时间"列的必须是数据时间；如果是尝试时间，守卫就不能只说"新者胜"。**

52. **验证脚本必须从干净状态开始，否则它测的是历史。**
    我的探针复用固定目录，第二次运行"通过"——因为第一次留下的 VISIBLE 行会穿过失败路径
    （失败只把 `MISSING` 降级为 `UNKNOWN`）。**"通过"要能归因到本次代码，而不是上一次的残留。**

53. **放宽一个不变量时，用数据自身的状态把放宽范围围起来，并逐行报告爆炸半径。**
    新分支用 `sample_sequence = 0`（只有成功路径 +1）限定在"从未有过真实样本"的行，
    从而不动任何已持有数据的行；实测半径 **4 / 1,973 = 0.20%**。
    **"我放宽了一点点"不是证据，"这几行、这个比例、这些字段不变"才是。**
