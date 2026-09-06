# R3 EXTERNAL_RESEARCH

Source Chat: 6a9d94ca-7b7c-83ee-885b-1cad2a17c7c6

Actual response; model/reasoning not independently verified. Snapshot review, not deployment certification.

[GXH_C2C_V3]
MESSAGE_ID: C2C-20260907-R3-EXTERNAL_RESEARCH-RESULT
REPLY_TO: C2C-20260907-R3-EXTERNAL_RESEARCH
TYPE: RESULT
CYCLE_ID: ALL_HISTORY_20260907
ROLE: EXTERNAL_RESEARCH
BLOCKS_RELEASE: true
SENSITIVE_DATA: NONE

**DISPOSITION: REVISE_BEFORE_DEPLOY_FOR_EXIT_ARMS / ALLOW_ENTRY_PAPER_AFTER_MINIMAL_INTEGRATION_CHECK / BLOCK_ALPHA_PROMOTION**

### 1. 实际读取

已复用指定工作区 `ws_48a6e004-f632-48ad-8449-778cde693505`，只读：

- `docs/PROJECT_CONTEXT/RESEARCH_2026-09-07/FINAL_CONTRACT.md`
- `EFFECTIVE_POLICY_CORRECTIONS.md`
- `TOKEN_PRECURSOR_EVIDENCE.md`
- `EXTERNAL_CORRECTIONS.md`
- `R2_CAUSAL_STATISTICS.md`
- `R2_MICROSTRUCTURE.md`
- `src/memetrader/research_finalists.py`
- `src/memetrader/forward_patterns.py` 必要段
- `src/memetrader/store.py` 注册、4仓门、paired admission、market-entry、finalist exit adapter/通用exit优先级必要段
- `tests/test_research_finalists.py`

未跑 SQL、未写代码/DB/Runtime、未部署、未读 secret。Chat 实际模型/推理配置：**项目侧未核验**。

---

## 2. 撤回我此前的结论

明确撤回 R2 中两点：

1. **撤回“migration/participation 是金额吸收/真实参与扩散代表”。**
   `EFFECTIVE_POLICY_CORRECTIONS.md` 已证实当前 V002：
   - migration → `young_absorption` L0 三帧代理；
   - participation → `early_quality` L0 强度代理。
   不能再拿当前自然结果证明真实钱包、金额净流或 migration receipt 机制。

2. **撤回把 `l0_profit_lock -62.54U paired delta` 当成“正确实现的L0锁利机制失败”证据。**
   当前 `principal_recovered/cost_covered` 状态实际不可达，93 仓全部 principal=0、0 次 `l0_two_frame_profit_lock`。该结果只能比较现有半卖/全卖行为，不能反证本来设计的“回本后连续恶化锁利”。

这点我与 `R2_CAUSAL_STATISTICS` 有实质分歧；以当前代码和冻结仓位事实裁决，**EFFECTIVE_POLICY_CORRECTIONS 胜出**。

---

# 3. 五个既有代表

| 机制 | R3 |
|---|---|
| 190 `l0_continuation_failure` | **可继续小额Paper**。实际滚动L0衰退退出已接线；只称少亏实验。 |
| 187 volatility | **可继续小额Paper**。pressure只能叫 volume/count/liquidity 聚合代理，不叫净资金流。 |
| 196 relative resilience | **可继续，但只限稀疏条件型证据**。1 BUY，不能称全市场regime。 |
| 185 cycle reset | **只限条件型证据解释/现有策略继续**。80帧理论可覆盖720秒，但采样过密时可能不足；缺历史绝不能解释为静默。 |
| 194 same-symbol liq leader | **只限条件型证据解释/现有策略继续**。冻结的是同规范symbol局部集合，不是语义同题材，当前0 BUY。 |

不修改这5个旧账户。

---

# 4. 三个真正新 entry

### `finalist_boundary_retest_v1`
**可部署5U Paper，但部署前补1个 Store 级正路径检查。**

代码确实实现了 A 冻结上沿 → B 突破 → C 回踩旧边界 → 再升；纯连续上涨反例会拒绝。中间缺值、不同池、来源切换、未来 `recorded_at` 都拒绝。机制与旧单纯 pullback/reclaim 有实际状态差。

### `finalist_seller_absorption_v1`
**可部署5U Paper，同上。**

名字解释目前合格：使用的是 rolling buy/sell **笔数份额**，没有冒称真实金额吸收。外部和本地 precursor 证据都只允许把 buy-ratio/count 当待证代理，不支持“已找到赢家阈值”。

### `finalist_price_then_depth_v1`
**可部署5U Paper，同上。**

和旧 `liquidity_leads_price` 方向相反：这里明确价格先行，再等待**同一 provider 的 reported liquidity**追认。代码禁止跨 provider 拼接。不能称 LP 注资、净流或可执行深度。

**共同最小修正/验收：**当前测试已经验证三种 signal 的纯函数、因果反例，但我实际看到的 Store 集成 next-frame 三链测试主要证明的是5臂 paired exit group。部署前至少应有一次真实 Store 路径验证这3个 entry 各自：

`trigger frame → READY → 后一个独立同池frame → BUY`

不是新增平台，只补当前接线边界的最小验收。

---

# 5. 四个新 exit：发现一个部署前必须修的真实合同缺口

### Profit budget
机制和净值计算本身正确：
`economic_value = realized proceeds + remaining qty × current mark，经实际Paper sell cost`

而不是毛市值。

### Progress clock
算法也正确实现“累计超过锚点1% stake才重置时钟”，不是每帧都必须+1%。

### Price↓ / liquidity↑
行为确实与旧“价格坏+liq不增”相反，机制独立。

### Activity↑ / price↓
只使用 rolling volume 与 buy-share，命名没有越界为真实资金流。

**但是四臂目前全部：阻止部署，直到修一个很小但真实的连续性错误。**

`evaluate_finalist_exit()` 在 exit frame 缺：

- price、
- liquidity、
- economic value、
- original pool 等

时直接：

`WAIT + 原 state`

这会**保留此前 bad_streak / progress clock continuity**。

因此出现：

`坏帧1 → 已知缺字段帧 → 坏帧2`

时，只要前后已接受 frame 的时间差没有超过60秒，缺字段 observation 可能被跳过去，仍形成“两次连续确认”。

这与 FINAL_CONTRACT 明确要求的：

> “连续中性帧/缺少字段必须断开计数”
> “180秒连续可观察”

不一致。

对 `progress_clock` 更明显：已知出现不完整市场观察时，目前不会立即打断“连续可观察时间”。

**最小必要修正：**

不需要新 DB、不需要新框架。只需让已知 incomplete exit frame 显式打断 continuity，例如：

- reset `bad_streak`；
- 标记 continuity broken，使下一完整帧重新建立 `accepted/progress` 基线。

然后补一个 fixture：

`bad → incomplete → bad != SELL`
以及 progress-clock 中 incomplete 不得累计为180秒静默。

修后四退出臂可进入5U Paper。

---

# 6. 共同 baseline

`finalist_baseline_v1`：**可部署，且必要。**

不是第13个 alpha，只是退出比较基线。

---

# 7. 五臂 paired admission

代码核验后，**不存在“结构上永远全拒绝”的 bug**。

当前顺序是：

1. 每臂先执行4仓限制；
2. 所有5臂必须同时进入 `admitted_arms`；
3. `paired_entry_size` 必须精确等于组大小5；
4. 任一臂现金不足 → 整组从本机会撤销；
5. 同一5U source receipt / entry fill 投影给5臂；
6. 各账户退出和现金独立。

所以设计能实现共同入口。

但有一个必须保持在报告里的 estimand 限制：

**它测的是“共同受限入口下哪种退出更好”。**

因为某个快退出臂即使先释放仓位，只要另一个臂仍占满4仓，下一机会整组仍拒绝。不能把 paired 结果外推成“5个退出分别独立运行时的自由资本周转收益”。

这是设计限制，不是部署 blocker。

---

# 8. 通用 exit 遮蔽

Store 中公共 hard stop / trailing / max-hold 先于 finalist capital exit 决定最终 action；四臂 `take_profit=[]`，但仍共享：

- -20% stop；
- +30% 激活、15%整价值 trailing；
- 30min max-hold。

这符合 FINAL_CONTRACT。

因此 profit-budget 在较高盈利阶段确实可能先被公共 trailing 遮蔽。**不是代码错**，因为 baseline 同样使用公共 exit；但统计必须区分：

- finalist trigger actually armed；
- common exit won competing trigger。

不能看到“没有 finalist SELL”就说机制没触发。

---

# 9. 80帧、来源、未来数据

**新3 entry：PASS。**

9个选择帧要求≥15秒间隔、总跨度120–600秒；80帧容量足够形成序列。代码还检查选定窗口里的所有中间 observation，因此不能删掉坏中间帧制造漂亮路径。

**Cycle reset：仍 COVERAGE_UNPROVEN。**

它要求≥720秒。80帧×约15秒正常情况下够，但密采/重复帧多时不保证。因此现有0 BUY不能解释为市场没有cycle机会。

**来源切换：PASS。**

entry 要求整个序列 same `upstream_provider`；exit provider切换重置确认状态。

**未来 frame：PASS at pure-function boundary。**

entry 强制：

`activated <= observed <= ingested <= recorded <= decision`

exit 测试覆盖 `recorded_at > now → WAIT`。

实际 Store next-frame 对三新entry仍建议按上面的最小集成检查收口。

---

# 10. 外部论文与本地 precursor 对当前12机制意味着什么

`EXTERNAL_CORRECTIONS.md` 已纠正两项 R1 夸大：

- Pump.fun 0.198%不是完整24h毕业率，而是约6分钟采集造成的下界；
- 钱包论文最新版关联已大幅缩小，SOL流入区间包含0。

所以这些都**不能**拿来给12候选加“外部验证alpha”标签。

本地 `TOKEN_PRECURSOR_EVIDENCE.md` 更直接：

- universe 12,000 hash样本中60m可分类仅4,412；
- 当前chain-meme 2,729 h0 中60m只有506 observed；
- 240m **0个成熟**；
- volume/buy-ratio/count 的边际方向跨分层不稳定；
- 暴涨vs失败甚至没有一个冻结分层能达到双方各≥3。

因此当前阈值只能解释为**一次性预注册机制参数**，不能说是本地历史优化所得。

---

## R3最终裁决

**立即可保留/继续：**5个既有账户，按上述证据等级解释。
**3个新entry：** `ALLOW_SMALL_PAPER_AFTER_MINIMAL_STORE_NEXT_FRAME_CHECK`。
**共同baseline：** `ALLOW_SMALL_PAPER`。
**4个新exit：** `BLOCK_DEPLOYMENT_UNTIL_INCOMPLETE_FRAME_BREAKS_CONTINUITY`，修复后允许5U严格前向Paper。

除此之外**不需要新平台、不需要新增API、不需要大SQL、不需要更多策略。**

注册通过、fixture通过、自然成交都仍只证明工程接通；当前没有任何一项获得 alpha、增资或 Live 资格。
