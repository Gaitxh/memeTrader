# R3 ADVERSARIAL_RISK

Source Chat: 6a9d94dd-2eb8-83e8-ac4b-bdfc14bd49a1

Actual response; model/reasoning not independently verified. Snapshot review, not deployment certification.

[GXH_C2C_V3]
MESSAGE_ID: C2C-20260907-R3-ADVERSARIAL_RISK-RESULT
REPLY_TO: C2C-20260907-R3-ADVERSARIAL_RISK
TYPE: RESULT
CYCLE_ID: ALL_HISTORY_20260907
ROLE: ADVERSARIAL_RISK
DISPOSITION: **REVISE_BEFORE_DEPLOY / BLOCK_ALPHA_PROMOTION**
BLOCKS_RELEASE: true
MODEL: GPT-5.6 Sol；实际 reasoning 档位无法由项目侧独立核验，**不声称 GPT-6/xhigh**。
SENSITIVE_DATA: NONE

## 总裁决

当前 **5既有 + 3新entry + 4新exit + 1 exit baseline** 的收敛方向明显优于已撤销的“8+8”草案；我撤回 R2 中 migration/participation/profit-lock 的旧解释。

但**当前代码不建议直接部署新增8账户**。不是机制本身被否决，而是我实际读代码后发现退出五臂实验还缺两个影响因果解释的最小闭环，其中一个是明确代码问题。

### 一、明确撤回的旧结论

1. **migration/participation 旧解释撤回。**
   当前 V002 的 `migration_amount_rate_absorption_v1` 已是 `young_absorption` L0 代理；`experiment_participation_candidate_v1` 已是 `early_quality` L0 强度代理。不能继续写成“真实迁移金额吸收/钱包扩散”。

2. **profit-lock 负 paired delta 不能当正确锁利机制反证。**
   `l0_profit_lock` 要求 `principal_recovered/cost_covered`，而当前 adapter 没有让该状态对这个 exit family 可达；93仓全部 principal=0、0 次真正 L0 profit-lock。历史差值主要是半卖/全卖合同差异。

3. R2旧16机制草案已被 `FINAL_CONTRACT.md` 正式替代，不再作为实施对象。

---

# 二、13个重点账户逐项裁决

### 已有5个

**190 rolling L0 decay — 只限证据解释 / 继续原运行。**
代码与有效合同匹配；已有自然触发。只能称“少亏候选退出线索”，不能称盈利。

**187 volatility — 只限证据解释 / 继续原运行。**
当前确实是波动归一化 L0 机制；`pressure` 是 volume/count/liquidity 代理，不是真实资金流。

**196 relative resilience — 只限证据解释 / 条件型。**
实际是冻结局部3–4成员集合；仅1 BUY。不能写“市场 regime 已证”。

**185 cycle reset — 只限证据解释 / 条件型。**
规则需要 ≥720秒跨度；observer 仅最近80帧/20分钟，密集采样时80帧可能覆盖不到720秒。代码会 WAIT，没有把缺数据当静默，这是正确的；但覆盖未证。

**194 symbol liquidity leader — 只限证据解释 / 条件型。**
实际是同链/生命周期/规范化 symbol 的局部冻结集合，不是语义“同题材”。当前0 BUY，不能扩大解释。

---

### 新3个 entry

**6 boundary retest — 可部署小额Paper，但先补最小Store后帧接线测试。**
纯函数实现基本忠实：A冻结上沿→B突破→C真实回访→再升；来源、原池、future frame、NULL/负liq、gap 都有拒绝。

**7 seller absorption — 可部署小额Paper，但同样先补Store后帧测试。**
代码实际是“卖笔占比→趋均衡→买笔占优+价格恢复”，没有冒充金额流，符合冻结合同。

**8 price-then-depth — 可部署小额Paper，但必须继续只叫“报告liq追认”。**
代码要求价格先动、B阶段liq没有先涨、C阶段价格稳定后同来源liq抬升。它没有证明LP注资/真实深度。外部/本地证据都不支持升级该语义。

**共同缺口：** `tests/test_research_finalists.py` 对三者有纯函数正反例，但我看到的 Store 集成“三链后帧”测试实际上覆盖的是 **5个exit账户的 conditional_runner 配对入口**，并没有证明这3个新 entry 在 Store 中经历“9帧触发 → 后一独立原池帧 → 5U position”。
最小修正：每个新 entry 至少一条真实 Store-path fixture，三者无需再做巨大矩阵。

---

# 三、五臂 exit 实验：当前阻止部署

9 `profit_budget`
10 `progress_clock`
11 `depth_divergence`
12 `activity_failure`
baseline

纯 evaluator 本身总体清楚：

- `_begin()` 拒 future/out-of-order/duplicate；
- stale >15s WAIT；
- source/gap 对连续确认进行切断；
- `progress_clock` 在长断流后重置时钟，因此**没有数据不会被误认成横盘**；
- economic value 使用已实现回款 + 剩余数量按当前 Paper sell terms 的净值；
- position `stake_usd` 在 market-entry 创建时等于 `buy_terms.total_cost_usd`，因此以后额外买费非0时也不是只拿裸 notional 作成本基准。

但有两个 deployment blocker：

### BLOCKER A — paired group 的现金失败会丢失研究分母

`paired_entry_size=5` 本身实现正确，旧 pair 默认仍为2；slot-limit 也在 paired gate 之前检查。

但**现金检查发生在更后面**：

当五臂信号都满足后，如果其中某一个账户因之前退出差异造成 cash < 本次所需金额，代码会把整个五臂组从 `by_notional` 删除。

此时该共同机会可能：

- 五臂确实都不成交——符合合同；
- **但没有为五臂产生明确的 paired-cash rejection entry decision。**

这会让“由于某一臂没钱导致全组错过”的机会从实验 denominator 中静默消失，后续很容易错误比较只剩下的共同成交样本。

这是实际研究因果问题，不是 UI 小问题。

**最小必要修正：**保留一个持久的共同拒绝记录/原因，明确 `paired_group_cash_unavailable`（以及由单臂slot导致的共同阻断），不用新增表/平台，复用现有 cohort/decision 路径即可。

---

### BLOCKER B — profit-budget 跨来源仍保留旧来源 peak

`evaluate_finalist_exit()` 在 source 改变或 gap>60s 时会：

- 断开 prior；
- 清 bad_streak；
- 重置 progress baseline。

但 `peak_profit` **不会重置**。

于是可能出现反例：

1. DexScreener 给出曾经 +30% peak；
2. provider 切 Gecko，两个 provider mark 水平存在系统差；
3. 新来源连续两帧只有 +10%；
4. 即使新来源内部没有出现“从30%回吐到10%”的市场过程，旧 provider 的 peak 仍可武装 profit-budget。

这违反“不跨来源拼接状态”的精神。

**最小修正：**source boundary 时，profit-budget 的 comparable peak 也应从当前 frame 重新建立；至少不能拿旧 provider peak 与新 provider value 做回吐确认。

在这两个点修正并通过实际 Store exit 接线测试前，我对 **9–12+baseline = BLOCK DEPLOYMENT**。

---

# 四、通用 exit 遮蔽：不是bug，但必须限定结论

Store 当前顺序是：

**公共 hard stop / trailing / max-hold / TP → finalist capital exit**

而 finalist 只有在公共 `action is None` 时才能接管。

因此四个 finalist exit 不可能“独立拥有所有终局”；公共 -20% stop、+30%激活的15% trailing、30分钟 max-hold 可能先退出。

五臂公共合同一致，所以这**不破坏配对公平性**，但报告只能说：

> 在共同公共退出未先终止的存活区间，新增 exit 的边际作用。

不能说所有 PNL 差异都是 finalist exit 造成。

建议补一个 Store-level fixture 验证：
- finalist trigger 能持久化 state；
- 生成 pending mark；
- 必须等下一独立原池 frame 才成交；
- 同帧公共 stop 与 finalist 同时满足时，公共规则按合同优先。

这是必要接线验收，不是新系统。

---

# 五、80帧 / 静默 / future / source 检查

**三新entry：PASS。**

`finalist_signal`：

- 需要9个至少相隔15秒的选择帧；
- 总跨度120–600秒；
- 中间坏帧不能被删掉制造漂亮路径；
- gap>60拒绝；
- source变化拒绝整个窗口；
- `observed <= ingested <= recorded <= decision`；
- identity必须同Token/同原池；
- 缺liq/负liq/交易字段缺失均不进入信号。

所以**没有把断采当压缩/静默**。

**185 cycle-reset：覆盖待证，不是逻辑假静默。**
它需要720秒而80帧可能不够；应继续 WAIT，不放宽门槛来制造交易。

---

# 六、TOKEN_PRECURSOR / 外部论文裁决

`TOKEN_PRECURSOR_EVIDENCE.md` 已完成，但只支持继续假设研究：

- universe 12k样本中可60m四分类约4,412；
- chain-meme h60 observed仅506，UNKNOWN/PENDING远多；
- 活跃度/buy-ratio等边际差异在 chain/time/age/liq 分层后方向并不稳定；
- 暴涨vs失败甚至没有满足双方各≥3样本的共同分层。

所以**不能用它给 finalist 阈值“背书”**。当前阈值只能叫预注册假设。

我同意 `R2_CAUSAL_STATISTICS` 关于“小额Paper可启动而非等待历史显著性”的观点；但与 `R2_DATA_ENGINEERING` 的一处实质分歧是：后者旧R2认为原8代表均可保留，包括 participation/migration/profit-lock。现在 `EFFECTIVE_POLICY_CORRECTIONS.md` 已有更强的实际合同证据：前二者机制已经被 V002 替换、profit-lock状态不可达，因此该旧结论应被**撤销**，不能再用“保留负对照”掩盖机制身份错误。

外部 v3 纠错我采用 `EXTERNAL_CORRECTIONS.md` 的冻结结论：

- 0.198%不能叫完整24h毕业率；
- wallet论文最新版资金关联区间包含0；
- BONK日期仍不作为本地策略t0。

本R3没有重新打开网页独立复核这些论文，因此这里只把它们作为**已冻结外部纠错材料**，不冒充新的web核验。

---

## 最终行动裁决

**立即可继续原运行、但仅限证据解释：** 190、187、196、185、194。

**补最小 Store 后帧接线测试后可部署5U：** 新entry 6、7、8。

**当前阻止部署：** exit 9、10、11、12 + baseline。
解除条件仅三项：

1. paired cash/slot共同拒绝进入可审计分母；
2. profit-budget source switch 不跨源沿用 peak；
3. 4 exit 各至少一个 Store → state → pending → next-frame SELL 接线测试，并验证公共exit优先级。

不需要新API、新表、新平台、大SQL或架构重构。

### 实际读取路径

- `.../FINAL_CONTRACT.md`
- `.../EFFECTIVE_POLICY_CORRECTIONS.md`
- `.../TOKEN_PRECURSOR_EVIDENCE.md`
- `.../EXTERNAL_CORRECTIONS.md`
- `src/memetrader/research_finalists.py`
- `tests/test_research_finalists.py`
- `src/memetrader/store.py`：finalist register、80帧history、slot/paired-entry、cash projection、market entry、capital-exit adapter、通用exit优先级必要段
- `src/memetrader/forward_patterns.py`：finalist dispatch / conditional_runner合同
- `src/memetrader/capital_exits.py`：`_begin()` causal/fresh/source基础
- `R2_CAUSAL_STATISTICS.md`
- `R2_DATA_ENGINEERING.md`

未写代码/DB/Runtime，未运行大SQL，未读secret，未部署。
