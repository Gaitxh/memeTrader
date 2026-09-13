# 第 74 轮记录：观测面板自己就记录了窗口为什么失败；30 秒要求与提供方 ~30 秒更新周期结构性冲突

日期：2026-09-13
前置：`ROUND120_73_RECORD.md`
本轮性质：**发现运行时自己持久化的租约面板，用它直接读出窗口失败原因；并撤回我自己一个算错的
反事实。** 没有改任何策略、阈值或运行时行为。

---

## 0. 一句话结论

1. **运行时会把自己每个 token 的观测状态写进 `kv` 表**（`chain-meme-pattern-watch:leases145`），
   字段包括 `frame_count`、`frame2_delay_seconds`、`frame3_delay_seconds`、`window_results`、
   `window_expired`、`coverage_gap` 等。**此前 70 多轮全部在从 `token_snapshots` 反推行为，
   而调度器自己的记录一直在库里。**
2. **面板直接给出了窗口失败的原因**（`observation_leases145.expire_windows:158-164`）：
   `SOURCE_NO_UPDATE` = 到窗口截止 +30 秒仍不足 3 帧（**源没有回应**）；
   `UNKNOWN_PATH_GAP` = 帧到了但连续性/跨度/帧数不达标（**路径问题**）。
3. **关键算术**：轨迹窗口要求**三帧落在 30 秒内**（`dex_trajectory.py:50-55` 的
   `len(part) >= 3` 与跨度上限）。而面板实测 **frame2 延迟 p50 = 28.51 秒、
   frame3 延迟 p50 = 49.67 秒**。**中位数的第三帧落在 49.67 秒，
   装不进一个 30 秒的窗口——差约 1.7 倍。**
4. **独立复算**：按真实帧间隔逐帧检验，**只有 30.24% 的帧能够呈现"3 帧在 30 秒内"**，
   与第 72 轮测得的闸门占全部逐臂判定 46.41% 是同一量级。**两条独立路径指向同一个结论。**
5. **面板的比例随窗口长度单调变化**：`SOURCE_NO_UPDATE` 从 30 秒的 **53.8%** 降到 120 秒的
   **47.4%**、300 秒的 **29.9%**；`OBSERVED` 在 30 秒时最低（**28.2%**）。
   **这正是"更新周期不够"应有的形状。**
6. **但 `UNKNOWN_PATH_GAP` 不单调**（30 秒 17.9% → 300 秒 **30.9%**），
   所以"把窗口放宽"**只对"源没回应"这一半有支持，对"连续性"那一半没有证据**。
   **这句话必须一起说，不能被平均掉。**

---

## 1. 发现：调度器自己的租约面板

```
kv 表
  key  chain-meme-pattern-watch:leases145   value = {"leases":[...], "mature_window_counts":{...}, ...}
  key  chain-meme-pattern-watch             value = {mover_watching, non_held_by_chain_bucket, ...}
  key  coverage145:status                   value = {denominator, opportunities, priority_targets, ...}
```

**每个 lease item 的字段**（实测，来自真实条目）：
`admitted_at`、`bucket`、`chain`、`coverage_gap`、`coverage_start_at`、`expires_at`、
`frame_count`、`frame2_delay_seconds`、`frame3_delay_seconds`、`last_useful_at`、
`last_phase_at`、`min_observe_until`、`next_due_at`、`pair_address`、`phase`、
`pool_created_at_ms`、`token_id`、`unchanged_run`、`window_counted`、`window_expired`、
`window_results`。

**这意味着从第 64 轮起我一直在反推的东西，调度器一直在直接记录。**

---

## 2. 面板对窗口失败的判定（读源码逐行确认）

```python
# observation_leases145.py:156-167
first = _time(item.get('coverage_start_at')); last = _time(item.get('last_useful_at'))
results = item.setdefault('window_results', {})
for window in WINDOW_SECONDS:                       # (30, 120, 300)
    if str(window) in results: continue
    target = (first or admitted) + timedelta(seconds=window)
    if last and last >= target:
        results[str(window)] = 'OBSERVED' if (not coverage_gap
                                              and (last - target).total_seconds() <= 30
                                              and frame_count >= 3) else 'UNKNOWN_PATH_GAP'
    elif now > target + timedelta(seconds=30):
        results[str(window)] = 'SOURCE_NO_UPDATE'
    else:
        continue
```

**两种失败的含义完全不同：**
- **`SOURCE_NO_UPDATE`**：到截止 +30 秒宽限时，**连 3 帧都没凑齐** → 源没给数据。
- **`UNKNOWN_PATH_GAP`**：**帧到了**，但 `coverage_gap` 为真、或最后一帧晚于截止超过 30 秒、
  或 `frame_count < 3` → **是路径/连续性问题，不是源的问题**。

---

## 3. 累积计数（全 epoch，面板自己维护）

| 窗口 | 尝试数 | OBSERVED | SOURCE_NO_UPDATE | UNKNOWN_PATH_GAP |
|---|---|---|---|---|
| **30 秒** | 1,880 | 531（**28.2%**） | 1,012（**53.8%**） | 337（17.9%） |
| 120 秒 | 1,392 | 574（41.2%） | 660（47.4%） | 158（11.4%） |
| 300 秒 | 810 | 318（39.3%） | 242（29.9%） | **250（30.9%）** |

**必须随表携带的限定**：这些是租约面板**计过数的 (token, window) 相变次数**，
**不是不同 token 数**，而且面板只包含**被准入观测的那些 token**。
所以**列与列之间不可相加**，只有**行内比例**可比。

**行内比例读出的两件事：**
1. **`SOURCE_NO_UPDATE` 随窗口长度单调下降**（53.8% → 47.4% → 29.9%），
   `OBSERVED` 在 30 秒时最低（28.2%）。**这是更新周期限制的标准形状。**
2. **`UNKNOWN_PATH_GAP` 不单调**，在 300 秒时最高（30.9%）。

**∴ "把窗口放宽" 只获得第一件事的支持，第二件事没有证据。** 两者都写明，不取平均。

---

## 4. 机制算术：30 秒要求 vs 实测帧到达节奏

| 量 | 实测 | 来源 |
|---|---|---|
| frame2 延迟 p50 | **28.51 秒** | 租约面板 |
| frame3 延迟 p50 | **49.67 秒** | 租约面板 |
| 窗口要求 | **3 帧落在 30 秒内** | `dex_trajectory.py:50-55` |
| 逐帧能满足该要求的比例 | **30.24%** | 本轮由真实帧序列独立复算 |
| 闸门占全部逐臂判定的比例 | **46.41%** | 第 72 轮 |

**中位数第三帧落在 49.67 秒，而窗口只有 30 秒——差约 1.7 倍。**
**所以对中位数 token 而言，这个要求不是"严格"，而是"不可能"。**
而 30.24% 与 46.41% 是同一量级，**两条独立路径互证**。

**同时它也解释了第 65 轮那条"提供方每 ~30.1 秒才给一次新信息"**：
要求三帧落在 30 秒内，等于要求提供方在一个更新周期内给出三个不同的值。

---

## 5. 我撤回的一个反事实（算错了，必须记录）

我算了"如果把窗口要求放宽到 60/120/300 秒，有多少比例的帧能合格"，
得到 **60、120、300 秒三者完全相同的结果（27,753 帧 = 39.90%）**。

**这是不可能的**——放宽跨度上限不可能恰好饱和在 60 秒那个值上。
**原因是我的脚本**：我在套用规则**之前**就把序列切片到恰好 3 帧，
于是窗口长度变得无关紧要（3 个点永远不超过哪怕 30 秒的跨度上限）。
**该数字全部撤回，本轮不报告任何关于窗口长度的反事实。**

**要做对需要**：为每个窗口长度重建 `dex_trajectory.window` 的**多点**构造
（`end - part[0]` 可以横跨整个窗口，而不是只取 3 个点），再套用跨度与间隔规则。
**本轮未做。**

---

## 6. 我本轮另一个读错（记录）

第 74 轮第一版脚本假定 `leases145` 的顶层是 `{token: item}` 映射，于是报告
"lease items found: 0"。**实际 `leases` 是一个列表。** 修正后读到 12 个活跃租约。

**并且我没有把 12 个活跃租约的统计当作总体**——`mature_window_counts` 才是累积量，
所以本文的窗口分布取自后者，12 条只用于确认字段结构。

---

## 7. 对用户四个排查重点的当前回答

| 用户问 | 答案 | 轮次 |
|---|---|---|
| 哪一环节数据缺失 / 延迟 / 质量？ | **观测覆盖**：86.4% 的 token 只取到 ≤2 帧 | 73 |
| 哪一环节阈值过严？ | **没有大规模过严的过滤器**；主导闸门拦下的 token 转化率 1.03% **高于**基准 0.46% | 72 |
| 各环节通过率 / 失败原因分布？ | 逐臂 5.96M 判定 / 74 原因（`outcomes_readout.py`）；窗口失败 53.8% 源无回应、17.9% 路径断裂（本轮） | 72/74 |
| **速度与频率是否瓶颈？** | **频率不是**（压节流只值 +0.9%）；**但"3 帧 / 30 秒"这个要求与提供方 ~30 秒更新周期结构性冲突** | 73/74 |

---

## 8. 可落地方向（**含一条边界声明**）

### P0（保留）：把租约面板纳入常规可观测性

`leases145` / `coverage145:status` / `chain-meme-pattern-watch` 三个 key 携带调度器的一手状态，
但没有任何命令读取它们。**建议**：在已有的 `scripts/outcomes_readout.py` 与
`scripts/frame_window_readout.py` 之外，加一个只读面板读数。零行为变更。

### P1：窗口长度这一参数——**本轮只完成了一半的论证**

- **已建立**：`SOURCE_NO_UPDATE` 随窗口长度单调下降（53.8% → 29.9%），
  且中位第三帧 49.67 秒装不进 30 秒。**所以 30 秒这个要求本身，在实测节奏下对中位数 token
  不可满足。**
- **未建立**：`UNKNOWN_PATH_GAP` 在长窗口下反而最高（30.9%），
  且**我没有做出一个可信的窗口长度反事实**（§5）。
- **因此本轮不建议改任何参数。** 若将来要做，用户的原则已经很明确：
  **必须是额外策略模块**，不得修改现有策略；而且需要它自己的前向证据，
  因为"窗口更长是否更赚钱"本轮完全没有回答。

### 不再重开

节流（第 73 轮否证）、入库上限（第 73 轮否证）、租约长度（第 65 轮）、
入场流动性下限（第 42 轮）、硬止损阶梯（第 69 轮）。

---

## 9. 复现脚本

| 脚本 | 作用 | 可信度 |
|---|---|---|
| `r74_lease_state.py` | 定位三个 kv key；**第一版误判结构** | 部分（结构发现有效） |
| `r74b_window_results.py` | **租约面板字段、window_results、frame 延迟** | **有效** |
| `r74c_window_requirement.py` | 逐帧复算 30.24% + 面板比例读法 | 有效（**反事实部分已撤回**） |

**新增常设规则 27**（接 §10.6 同族）：
**在从产物反推一个系统的行为之前，先找它自己有没有写状态。**
本项目从第 64 轮到第 73 轮一直在从 `token_snapshots` 推断观测行为，
而 `kv` 表里的租约面板从那时起就一直在直接记录 `frame_count`、`frame2/frame3_delay`、
`window_results` 与失败分类。**反推不仅更慢，而且第 73 轮那次反推只能得出"帧数不足"，
无法区分"源没回应"与"路径断裂"——这个区分只有面板能给。**
