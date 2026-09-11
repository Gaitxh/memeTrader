# 2026-09-12 全面审查第 1 轮：可达性缺陷修复 + 抗洗（hold-through-noise）新臂

对应目标：全面审查交易系统、定位“交易少/已发现代币未进入策略判断”的逻辑缺陷并立即修复；对“金狗持仓能力不足、被正常振幅洗出”做系统性买卖逻辑研究并新增退出机制，全部以**额外策略**形式加入，不改动任何现有策略。

本轮结论分三块：两个已确认的**真实缺陷**（均已修复并加载）、一项**量化证据**（洗出现象成立）、一批**新增策略臂**（5 条，全部新 ID）。

---

## 1. 缺陷 A（严重）：ALPHA149 家族的策略判断在实盘路径上几乎不可达

### 现象
- 全系统 `mechanism_ready` 长期只有 4 种机制触发（`dense_watch_breakout`、`df_price_up_liquidity_up`、`df_mature_price_up`、`df_activity_jump`），其余机制计数恒为 0。
- `system_error_cases` #266：`chain_meme_cohort_observer` 抛 **TypeError: '>=' not supported between instances of 'NoneType' and 'int'**，自 2026-09-11T13:19:19Z 起累计 **398 次**。

### 根因
`dex_trajectory.derive()` 把当前池深发布在 `feature['current']['liquidity_usd']`，**从不发布顶层 `liquidity_usd`**；而 `alpha149.mechanisms()` 读取的是顶层键：

```python
liquidity = _num(f.get('liquidity_usd'))          # 实盘恒为 None
...
if liquidity is None or liquidity < 1000 or ret is None:
    return _finish(out)                            # 每一帧都在此提前返回
```

后果有两层：

1. 编号机制 1–27（wave 1–3 的全部原始arm、wave 5/6/7 的多数）**从未在实盘执行过**——每一帧都在该 guard 提前返回；只有 guard 之前的 wave 4 两帧/单帧块有机会运行。
2. wave 7 新增的 `inv_contraction` 写的是 `liquidity >= 5000`（未判空），位于 guard 之前、`if previous:` 块内 → 任何**同一池已有 ≥2 帧**的帧都会抛 TypeError，把**剩下的两帧机制也一并打死**，并在 `chain_meme_cohort_observer` 周期里中断后续信号采集（每小时约 55 次）。

### 量化
用测试里 43 条已标定的机制向量，对比“实盘特征形状（无顶层 depth）”与修复后：

| 形状 | 可触发向量 |
|---|---|
| 修复前（实盘形状） | **1 / 43** |
| 修复后 | **39 / 43** |

### 修复（`src/memetrader/alpha149.py`，仅本家族）
- depth 缺失时回落到**当前帧**的 `current['liquidity_usd']`（因果值，不推断、不补零）。
- `inv_contraction`、`seq_two_step_rise`、`mature_two_step_slow` 增加 `liquidity is not None` 判空。
- 把窗口派生变量（`w15/w60/w180`、`r15/r60/r180`、`v30`）在首次使用前**统一绑定一次**（缺失即 None），消除 `UnboundLocalError`（这类错误此前被 guard 掩盖，修复后立即暴露并被本项修掉）。

### 加载后证据（20:21:07Z 重启）
- `mechanism_ready` 非零机制：**4 → 14**，含此前从未触发的 `righttail_lottery`(18)、`sf_quiet_absorption`(13)、`sf_young_turnover`(11)、`goldendog_liquidity_band`(9)、`sf_deep_low_fdv`(6)、`sf_goldendog_deep_base`(6)、`sf_extreme_buy_pressure`(4)、`merged_multi_setup`(5)、`inv_contraction`(1)。
- `signals` 非零臂：**20 条**（修复前同一进程为 0）。
- 错误计数 #266 在重启时刻**停止增长**（最后一条 20:21:00Z）。

---

## 2. 缺陷 B（严重，本会话早期 commit `4ed7101` 引入的回归）：信号循环被重新嵌套

### 根因
`4ed7101`（ALPHA149 年轻池覆盖）在 `runtime.py` 的 `for identity in quotes:` 循环与紧随其后的 `if identity in fresh144:` 之间插入了新的 `if batch_manager149 ...:` 块。Python 按缩进归属，原先属于 `for identity in quotes:` 的 `fresh144` / recipe145 / 微观结构 / event-clone 信号块（16 空格）被**重新嵌套**进新块：

- 每个周期**最多只对最后一个 identity** 执行一次（而不是每个 identity 各一次）；
- 且仅当 `batch_manager149.enabled` 时才执行；
- 当该周期 `frames`/`quotes` 为空时，`identity` 未绑定 → `UnboundLocalError: cannot access local variable 'identity'`（`system_error_cases` #265，自 13:12:50Z 起 **392 次**），直接中断该周期剩余工作。

### 修复
把覆盖报价块整块移动到 `for identity in quotes:` 循环**之后**，循环变量改名 `offer_identity/offer_token/offer_snapshot`，并加注释禁止再次嵌套或遮蔽该循环。

### 加载后证据
- #265、#266 两条错误在重启后均**不再新增**；`chain_meme_cohort_observer` 的 `fail=0`。

> 影响范围说明：缺陷 A 只影响本会话新增的 ALPHA149 家族（其机制读的是自造的顶层键）。共享 `dex_trajectory.mechanisms` 用的是窗口级字段（`liquidity_change_fraction`、`liquidity_retention`、`age` 等），**不受影响**；缺陷 B 影响的是 runtime 的信号采集循环，与策略定义无关，修复即恢复原有逐 identity 行为。

---

## 3. 量化证据：现有退出机制确实在“正常振幅”里被洗出

### 3.1 事后价格路径（最近 48h，活跃资金周期，383 次硬止损）
数据源：`token_snapshots(token_id, observed_at)`，与退出通道同族报价。

| 指标 | 数值 |
|---|---|
| 硬止损持仓时长 | p25 **0.6 分钟** / p50 **1.1 分钟** / p75 4.7 分钟 |
| 退出时相对运行高点的回撤 | p25 −29.2% / p50 **−18.7%** / p75 −11.3% |
| 退出后 15 分钟价格中位数 | **+13.7%** |
| 退出后 30 分钟价格中位数 | **+15.1%** |
| 退出后 60 分钟价格中位数 | **+20.2%**（p75 最优价 +86.5%，p90 +193%） |
| 60 分钟内曾高于我方卖出价 | **81.8%** |
| 60 分钟内曾高于卖出价 ≥25% / ≥50% / ≥100% | **47.5% / 33.1% / 21.0%** |
| 60 分钟内曾回到入场价之上 | 56% |

对照：`dex_pool_liquidity_below_configured_floor_writeoff` 的 112 次退出中只有 6% 事后回到入场价之上——**真正的死亡盘与噪音回撤可区分**，因此流动性/貔貅类退出必须保持立即生效，不能一起放宽。

### 3.2 退出族经济性（最近 7 天，活跃周期，41,085 条已平仓）

| 退出原因 | 次数 | 平均 | 合计 |
|---|---|---|---|
| `market_mark_hard_stop` | 12,697 | **−4.85U** | **−61,540U** |
| `dex_pool_liquidity_below_configured_floor_writeoff` | 7,910 | −12.94U | −102,354U |
| `market_mark_max_hold` | 11,379 | **+0.63U** | +7,115U |
| `market_mark_trailing_exit` | 4,345 | **+4.74U** | +20,584U |
| `market_mark_take_profit_1 / _2` | 636 / 317 | +13.24U / +13.39U | +8,420U / +4,243U |

即：**固定 −20% 硬止损是最大的可控亏损来源，而时间型/追踪型退出是仅有的正期望族**，与用户“被正常振幅洗出”的判断一致。

---

## 4. 新增策略（wave 8，全部新 ID，未改动任何现有策略）

### 4.1 新增的退出合同字段（共享退出评估器，opt-in，默认不生效）
`Store._whipsaw_guard_allows_stop()` / `Store._reset_whipsaw_streak()`：

- `hard_stop_grace_seconds`：入场后 N 秒内不执行价格止损；
- `hard_stop_confirm_marks`：必须连续 N 个 5 秒 mark 都跌破止损线才卖出；
- `hard_stop_liquidity_veto_usd` + `hard_stop_liquidity_veto_min_buy_share`：池深仍 ≥ 阈值且买盘占比达标时，不因价格下跌离场。

只有声明这些字段的臂才受影响；**流动性/貔貅退出永不被这些 guard 延迟**。已核验：全部既有 343 条策略臂**没有任何一条**意外获得新字段（`leaked: []`）。

### 4.2 五条新臂

| arm_id | 入场 | 退出合同 | 备注 |
|---|---|---|---|
| `alpha149_survive_noise_wide_v1` | `df_price_up_liquidity_up`（与既有臂**完全同一冻结信号**） | −45% / 宽限 180s / 连续 2 帧 / 池深≥3000U 且买盘≥50% 时容忍 / 追踪 +45%→回撤 25% / 120 分钟 | 同信号宽止损对照 |
| `alpha149_survive_noise_confirm_v1` | 同上 | 仍 −20%，但宽限 60s + 连续 2 帧 | 只加确认，用于分离“延迟”与“放宽” |
| `alpha149_merged_multi_setup_v1` | **合并**：两帧价涨加池 ∪ 两帧成交额跳增 ∪ 单帧极端买压 ∪ 金狗早期冲量 ∪ 高密度观测突破 | 同宽止损合同 / 120 分钟 | 多策略整合覆盖更多情形 |
| `alpha149_merged_multi_setup_fast_v1` | 同上（同一入场） | 原 −20%、无宽限、15 分钟 | 同入场快出对照 |
| `alpha149_goldendog_deep_hold_v1` | `sf_goldendog_deep_base`（金狗深池低 FDV） | −55% / 宽限 300s / 连续 3 帧 / 池深≥5000U 容忍 / 追踪 +60%→回撤 30% / 240 分钟 / 1U | 金狗最大容忍实验 |

### 4.3 注册与加载
- 追加方式：`scripts/register_alpha149.py --apply`（append-only；`policy_additions` 216 → **221**，`ledger_unchanged: true`，同一资金周期、同一 activation 前沿：snapshot 3,053,565 / evaluation 2,248,839）。
- 生效定义 348 条臂；新臂字段完整（grace/confirm/veto/trail/hold 全部保留）。
- 20:21:07Z 经 supervisor 重启加载。

---

## 5. 验证清单

| 项目 | 结果 |
|---|---|
| `tests/test_alpha149.py`（含新增：合并机制可触发、wave8 合同、实盘特征形状回归、引擎可达性） | 15 项 PASS |
| `tests/test_whipsaw_guard.py`（宽限/确认/流动性否决 + 未声明臂保持原行为） | 2 项 PASS |
| `tests/test_shared_batch148.py`、`tests/test_strategy_delivery144/145.py` | PASS |
| `tests/test_dex_trajectory.py` 单独运行 | PASS |
| 实盘 `mechanism_ready` 非零机制 | 4 → 14 |
| 实盘 `signals` 非零臂 | 0 → 20（含 5 条新臂） |
| 新臂自然成交（加载后 3 分钟） | 4 条臂各开 2 仓；`merged_multi_setup_fast_v1` 已 1 次止损平仓 −0.4115U，其慢出对照 `merged_multi_setup_v1` 仍持有 2 仓 |
| 错误计数 #265/#266 | 重启后停止增长 |
| Live / 资金周期 / 历史 | `paper_only=true`、`live_locked=true`、周期与激活数不变、只追加不改写 |

## 6. 诚实边界

1. 新臂的自然样本极小（4 条臂 × 2 仓、1 笔平仓），**不构成任何盈利结论**；“放宽止损是否更优”正是这两组同入场 A/B 要回答的问题，需要前向时间。
2. 事后回升统计基于 `token_snapshots` 路径，已用中位数（而非仅最大值）表述以降低单点噪音影响；但仍不排除极薄池的单笔异常价。
3. 放宽止损必然也会让部分真跌的仓位持有更久；`writeoff`/流动性退出保持立即生效正是为此。
4. `tests/test_shared_batch148.py` 与 `tests/test_dex_trajectory.py` 同一进程顺序运行时会互相影响（先跑 `test_real_tagged_callback_safety_later_buy_exit_without_legacy_fanout` 再跑 dex 文件会出现 `KeyError: 'BUY'`；两文件单独运行均全通过）；这是**测试隔离问题**，与生产路径无关，留待后续轮次定位。
5. 本轮尚未完成的原目标部分（更多新策略族：洗出后再入场、波动率自适应止损；退役/暂停臂的系统复盘；组合/整合型策略；全链路稳定性复查）留待后续轮次继续。

## 7. 关键文件
- `src/memetrader/alpha149.py`：wave 8 臂、合并机制、depth 取值与判空、窗口变量绑定。
- `src/memetrader/store.py`：opt-in 抗洗 guard（`_whipsaw_guard_allows_stop` / `_reset_whipsaw_streak`）。
- `src/memetrader/runtime.py`：信号循环嵌套回归修复 + 覆盖报价块后置。
- `tests/test_alpha149.py`、`tests/test_whipsaw_guard.py`：新增回归。
- `data/tmp/goal_washed_out.py`、`goal_recon1/2.py`、`verify_wave8*.py`、`verify_depth_fix.py`：本轮只读证据脚本。
