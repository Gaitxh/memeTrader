# 2026-09-12 全面审查第 4 轮：整合最强退出画像 + 暂停臂复盘（wave 11）

## 1. 本轮两个实测发现

### 1.1 全库最强臂靠的是「短持有」，不是「长持有」

`resource_age_rate_candidate_v1`（活跃周期 7 天 +634.96U / 220 笔）的退出结构：

| 退出原因 | 笔数 | 合计 PnL | 单笔 |
|---|---|---|---|
| `market_mark_max_hold`（30 分钟到点） | 110 | **+767.61U** | **+6.98U** |
| `market_mark_hard_stop` | 81 | −155.05U | **−1.91U** |
| `market_mark_trailing_exit` | 25 | +42.40U | +1.70U |
| 写销 | 4 | −20.0U | −5.0U |

其合同为：**notional 5U、`hard_stop_return=−0.20`、追踪 `+30%/回撤15%`、`max_hold_minutes=30`**。对照全库平均硬止损 −4.85U，该臂的止损**只有 −1.91U**——说明它止损时亏得浅，且主要利润来自"到点兑现"的短持有（`age_rate_horizon_fast_v1` 持有 15 分钟亦 +109.91U）。这与 wave 8/9 的"放宽止损、延长持有"是**两个不同方向**，需要并行实验而不是互相替代。

### 1.2 暂停/退役臂复盘：236 条中仅 2 条有正收益

| 状态 | 数量 |
|---|---|
| `PAUSED_NEW_ENTRY` | 132 |
| `RETIRED_DUPLICATE` | 59 |
| `RETIRED_DEPLETED` | 45 |

全部暂停/退役臂中**有正收益记录的只有 8 条**，去掉 2 笔样本的 6 条 `canonical-*` 后，真正值得复活的只有 2 条：
- `market_regime_throttle_v1`：**+19.62U / 9 笔 / 0 写销**（9 月 9 日后停止交易）
- `early_impulse_profit_lock_control_v1`：**+18.56U / 47 笔**（其对照组 `early_impulse_profit_lock_40_v1` 为 −6.80U，即固定 +40% 锁利是失败的变体）

另有 7 条暂停臂**从未成交**（`inventory_contraction_v1`、`finalist_price_then_depth_v1`、`competing_risk_v1`、`observed_cycle_reset_reacceleration_v1`、`inventory_baseline_v1`、`duration_competing_risk_v1`、`watched_wallet_confirmed_entry_candidate_v1`），其中前两条的假设已在 wave 7 以新机制形式复活。

## 2. 新增策略（wave 11，4 条全新 ID，既有策略零改动）

| arm_id | 入场 | 退出合同 |
|---|---|---|
| `alpha149_survivable_fast30_v1` | `survivable_core`（与 wave 10 同一冻结入场） | **实测最强画像**：−20% / 追踪 +30%→15% / **30 分钟** |
| `alpha149_survivable_deep_fast30_v1` | `survivable_band_deep`（同一冻结入场） | 同上；1U |
| `alpha149_merged_survivable_v1` | **新机制 `merged_survivable`** = 五形态合并 **且** 存活带（两个独立条件同时成立） | 同上 |
| `alpha149_goldendog_revival_control_v1` | `goldendog_early_impulse`（与既有臂同一冻结入场） | 该假设**当年盈利的对照合同**（−20%/追踪30-15/60 分钟），而非亏损的固定 +40% 锁利 |

设计意图：**整合**（把"实测存活入场"与"实测最强退出画像"合并）、**复活**（把暂停的正收益假设以新 ID 重表达）、**对照**（fast30 与 wave 10 的长持有臂共用同一入场，可直接比较"短兑现 vs 长容忍"）。

- 注册：append-only，`policy_additions` 231 → **235**，账本/资金周期/激活前沿不变；20:48:52Z 加载（有效定义 362 条臂）。
- 单测：26 项 alpha149 + 2 项 whipsaw 全 PASS（新增：`merged_survivable` 必须两个独立条件同时成立——年轻池只有信号、深度持平的帧只有存活条件，两者都不得触发合并；wave 11 合同复用实测画像且新臂不触碰原臂）。

## 3. 加载后自然证据（约 2 分钟）

- `merged_survivable` 机制 ready=3，`alpha149_merged_survivable_v1` 与 `alpha149_survivable_fast30_v1` 已各出 1 个信号；`survivable_core` ready=3。
- **alpha149 家族退出结构已明显改善**（200 笔 / 115 笔平仓 / −66.49U）：
  `max_hold` 38 笔 **+18.04U**、`trailing` 28 笔 **+18.86U**、`hard_stop` 32 笔 −21.76U、**写销 28 笔 −80.0U**。
  → 正收益退出（+36.9U）已几乎抵消硬止损（−21.8U），**全部净亏损仍来自写销**，与 wave 10 的选择方向一致。
- 错误 #265/#266 保持冻结；Live 锁定、资金周期/激活数/账本未变。

## 4. 同入场 A/B 首轮统计（样本仍极小，仅记录不作结论）

| 对照 | 结果 |
|---|---|
| 宽止损 vs 仅加确认 | −1.738U（1 平仓） vs +0.086U（2 平仓） |
| 合并慢出 vs 快出 | −1.738U（1） vs −1.490U（2） |
| 洗出回收 慢 vs 快 | 0.0U（0） vs +0.262U（1） |
| 存活带 自适应 vs 快出 vs 深度早退 | 各 1 笔持仓中 |

样本量 1–4 笔，**任何方向性结论都不可靠**；需继续累积。

## 5. 诚实边界与下一轮（5/256）

1. 短持有画像来自**单一最强臂**（220 笔），其入场族 `resource_age_rate` 运行在 pattern 通道，alpha149 无法直接复用其入场，只能复用其**退出合同**——因此 wave 11 检验的是"合同迁移"而非"整臂复制"。
2. `market_regime_throttle_v1`（+19.62U/9 笔）的复活的尚未实施：它依赖市场状态节流信号，需要在 alpha149 内构造等价的市场级状态量，留待下一轮。
3. 下一步：① `merged_survivable` 与存活带臂的自然样本累积与首轮统计；② 复活市场状态节流假设；③ 针对**写销**再做一次入场侧加固（存活带已上线，需检验其是否真的把写销率从 28 笔降下来）。
