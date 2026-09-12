# 第108-109轮：保留观察名额改为候选流投放；复活静默停摆的持有人数据源

**日期**：2026-09-12  
**模式**：paper（`live.enabled=false`），epoch `chain-meme-trader/funding-20260906-v002-final-1000`  
**本轮性质**：工程修复（不新增策略、不改动任何既有策略的参数与逻辑）

---

## 一、第108轮：保留名额的根因修复（第101轮诊断 → 第104轮助手 → 本轮接线）

### 1.1 被修复的观测事实

第101轮的测量结论：mover 规则标记集合与观察器实际持有的租约**重叠 0/24**。

原因是结构性的：保留名额（`MOVER_RESERVED_SLOTS=8`，用户于第88轮批准）只挂在**拒绝路径**上——
只有当一个被标记代币**已经**作为候选进入准入循环、并且恰好因为 `(chain,bucket)` 桶满而被拒绝时，
`mover_reserved_admit()` 才会被调用。而被标记代币几乎从不作为候选出现，于是：

| 指标 | 修复前实测 | 设计值 |
|---|---|---|
| 标记集合 ∩ 观察器持有 | 0 / 24 | — |
| 保留名额录取速率 | ≈ 6 次/小时 | ≈ 32 次/小时 |
| 保留名额内代币的观测帧数 | 1 帧 / 整段窗口 | ≈ 30 帧 |

### 1.2 修复方式：从候选流头部投放，而不是放宽上限

第101轮的因果结论是"名额挂错了路径"，不是"名额不够"。因此本轮**没有**增加名额、没有增加请求预算：

1. `Registry.consider()` 在代币**首次观测**时给出标记结果，那一刻它的行情帧就在手上。
   运行时把这一帧缓存进 `_mover_first_quote`（有界，最新 64 条）。
2. pattern-observer 每 15 秒一次的准入步改为 `_remember_pattern_quotes({}, reserved_movers=True)`；
   内部调用新增的 `_reserved_mover_quotes()`，把"注册表中仍活跃、且观察器尚未持有"的被标记代币
   （最多 `8 - 已持有数` 个）**注入候选流头部**。
3. 注入的帧**不新增任何 HTTP 请求**——它就是那次已经付费的抓取；超过 300 秒的缓存帧会被丢弃，
   而不是当作现价塞进观察窗口。
4. 注入发生在被动 cohort 批次快照**之后**，因此这些帧不会变成 cohort 证据；此后它们与普通行情完全同权：
   同一个准入循环、同一套上限与资金门槛、同一套漏斗记录。
5. 新增 `mover_reserved_injections`（投放次数）与 `mover_injected_tokens`（投放了哪些代币），
   使"投放（reach）"与"录取（outcome）"可以分开度量。

### 1.3 上线后实测（重启于 11:00:05Z，源码哈希与磁盘逐字节一致）

| 指标 | 修复前 | 修复后（前 3.6 分钟） |
|---|---|---|
| 投放次数 | 0（路径不可达） | **4** |
| 被标记代币帧数 | 1 帧/整段窗口 | 20 个被标记代币中 **9 个 ≥2 帧、3 个 ≥10 帧**（最高 19 / 17 / 17 帧） |
| 同窗口未标记代币 | — | 160 个中仅 4 个 ≥10 帧 |
| 保留名额分支录取 | ≈6 次/小时 | 0（**正确**：桶内尚有空位时以普通 base 候选录取，名额留给真正越限的情形） |

**结论**：第101轮的根因判断成立，修复点在候选流而非上限。被标记代币现在能在 4 分钟内拿到
19 帧（约每 12-20 秒一帧），而第101轮基线是整段窗口 1 帧。

---

## 二、第109轮：唯一持有人数据源自 2026-09-03 起静默停摆，已复活

### 2.1 发现过程

用户的第 5 项要求（链上数据层）明确包含**持有人集中度、前十大持有人变化、新增持有人增长**。
核对时发现 `token_snapshots.holders` 在全部行中为 NULL，于是追查唯一可能的来源
`solana_holder_shadow_*`：

| 事实 | 值 |
|---|---|
| 注册定义 | `solana-holder-breadth-shadow/v1`（append-only，`decision_eligible=0`，`affects='none'`） |
| 已产生观测 | 541 行结果，138 个代币，horizons 0/15/60/240 分钟全部有数据 |
| 采集内容 | `unique_owner_count`、`top1_supply_share`、`top10_supply_share`、`owners_below_1bp_rate`、`balance_coverage` |
| **最后成功采集** | **2026-09-03T14:58:25Z**（此后 9 天完全静默） |
| 错误记录 | `last_error=''`——**没有任何报错** |
| 静默原因 | 游标 `solana_holder_shadow_scan_after:.../v1` 冻结在 133530，而 solana universe 已有 363,966 条、id 至 533,903 |

### 2.2 根因

`solana_holder_shadow` 定时任务只存在于 `run_forever()` 的**legacy 任务列表**中。
当前部署是 chain-meme-only，而该分支在到达 legacy 列表**之前就 `return`**：

```python
if self.chain_meme_trader_only:
    tasks = [ ...chain-meme 任务... ]
    try: await self._stop.wait()
    finally: ...
    return            # <-- 后面的 legacy 列表（含持有人通道）永不创建

tasks = [ ...external_sources, solana_holder_shadow, ... ]
```

于是：注册表完好、抽样规则完好、解析逻辑完好，**只是这个任务从未被创建**。
不抛异常、不写 error case、不触发告警——这正是它静默 9 天的原因。

### 2.3 修复与边界

把**同一个任务**（同一注册定义、同一 300 秒间隔、同一 0.2% 哈希抽样、同一 horizons、
同一每次观测 3 次 RPC）加入 chain-meme-only 分支。成本：约 12 次观测/小时，
主机 `api.mainnet-beta.solana.com` 与 DEX 通道**不同源**，不消耗 DEX 请求预算。

**语义边界未变**：该通道仍是研究用 shadow（`decision_eligible=False`、`affects='none'`、
`active_strategy=False`、不回填），**不进入任何交易决策**。恢复采集是为了先取得证据，
再判断持有人集中度是否具备预测力——而不是先把它变成硬门槛。

---

## 三、验证

| 检查 | 结果 |
|---|---|
| `tests/test_mover_reserved_wiring.py`（新增 8 项） | 全绿 |
| `tests/test_holder_shadow_scheduling.py`（新增 4 项，结构性） | 全绿 |
| `tests/test_mover_reserved_*.py` / `test_mover_watchlist*.py`（29 项） | 全绿 |
| pattern-watch 相关 8 个测试文件回归 | 失败集合与改动前**逐条一致**（各 18 项既有失败，`Compare-Object` 差异为空） |
| 部署校验 | `kv[runtime-loaded-manifest]` 中 runtime.py / store.py / observation_leases145.py 的 SHA256 与磁盘完全一致；441 条 policy arms；definition_version 未变 |
| 既有守卫 | `dust-read-vetos` / `mark-outlier-vetos` 保持工作 |

结构性测试是**有意为之**：本轮缺陷是"任务被放进哪一份列表"，所以要断言的是调度位置，而不是任务本身算什么。

---

## 四、提交

| 提交 | 内容 |
|---|---|
| `7fb34c5` | 第107轮自我纠正（写销正确；撤回第106轮的 glitch 判据与跨源修复方向） |
| `625f5f4` | 第108轮：保留名额改为候选流投放（+8 测试） |
| `60b504d` | 第108b：记录投放了哪些代币（reach 与 outcome 分离） |
| `10f3ce2` | 第109轮：在真正运行的部署中复活持有人通道（+4 测试） |

## 五、仍未决 / 下一步

1. **观察 12-24 小时**：投放与录取速率是否接近设计值（≈32 次/小时）；被投放代币能否稳定拿到 ~30 帧；
   以及这些代币进入 entry 判断层的比例（按流动性分档，与"被标记但未投放"及"未标记"对比）。
   *注：全population版的判断到达率统计在 39 GB 库上超时（`token_snapshots` 大表扫描），
   收尾时改用按 token_id 的轻量查询；该补充测量留待下一轮。*
2. **持有人通道**：先积累数据，再评估集中度/前十大变化的预测力（当前不进入决策）。
3. **仍未决的用户取舍**：观察面覆盖率（dense ready pool 仅占 ready pool 约 10-15%，
   提高覆盖意味着挤占既有策略的年轻池观察）；同代币并发上限是否从 shadow 转为强制。
4. **新增臂 A/B**：第 28/29/33-37/41/42 波均未达 `paired_arm_ab.py` 阈值（每边 20 笔已结算）。
