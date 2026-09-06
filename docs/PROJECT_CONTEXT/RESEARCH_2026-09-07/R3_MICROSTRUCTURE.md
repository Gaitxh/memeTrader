# R3 MICROSTRUCTURE

Source Chat: 6a9d94bd-ef58-83ee-836b-36251dadab7a

Actual response; model/reasoning not independently verified. Snapshot review, not deployment certification.

[GXH_C2C_V3]
MESSAGE_ID: C2C-20260907-R3-MICROSTRUCTURE-RESULT
REPLY_TO: C2C-20260907-R3-MICROSTRUCTURE
TYPE: RESULT
CYCLE_ID: ALL_HISTORY_20260907
ROLE: MICROSTRUCTURE
DISPOSITION: **CONDITIONAL_GO_SMALL_PAPER / BLOCK_ALPHA_PROMOTION**
MODEL_STATUS: **未核验实际 Chat 模型/推理档位**
SENSITIVE_DATA: NONE

R3 已按要求只读检查最终合同、纠错、前置证据和实际代码接线；未运行大 SQL、未写代码/DB/Runtime、未读 secret。

## 一、先撤回我此前两项结论

**撤回 R2 对现有 `l0_profit_lock_candidate_v1` 的负 delta 作为“正确 profit-lock 实现反证”的解释。**
`EFFECTIVE_POLICY_CORRECTIONS.md` 与代码已经证明：其 L0 回本状态不可达，93 仓 `principal_recovered=0`，15 次部分兑现并没有进入真正 `l0_two_frame_profit_lock`。所以 `-62.54U` 只能描述当前“半卖/全卖等混合合同”的历史差异，**不能证伪正确接线后的锁利机制**。

**撤回把当前 migration / participation V002 解释为金额迁移吸收、买家扩散。**
当前实际分别是 young-absorption L0 三帧代理和 early-quality L0 活跃度代理，不是钱包/amount-flow机制。FINAL_CONTRACT 已正确不把二者放入最终5代表。

---

# 二、最终 13 个重点账户逐项裁决

### 复用5个

1. **190 rolling continuation failure — 可继续小额Paper**
真实L0路径已运行；主要是退出实验，不称入场alpha。

2. **187 volatility-scaled momentum — 可继续小额Paper**
代码/纠偏一致；`pressure`只能解释为聚合量代理，不是净资金流/OFI。

3. **196 local relative resilience — 可继续但仅限证据解释**
机制接线存在，但仅1 BUY，局部3–4成员集合≠全市场regime。覆盖不足阻止推广，不阻止运行。

4. **185 cycle reset — 条件型继续，不应为零交易放宽**
合同要求≥16帧、跨度≥720秒，而 Store 只取最近80帧/20分钟。若实际采样太密，80帧可能覆盖不到720秒，所以0 BUY可能纯属**历史容量/采样密度限制**。这是 coverage risk，不是机制失败。

5. **194 same-symbol liquidity leader — 条件型继续**
只能称“同规范化 symbol、同链/lifecycle冻结局部集合”，不称语义同题材赢家。0 BUY 不构成失败。

### 新3 entry

6. **boundary retest — 可部署5U Paper**
三阶段 A/B/C 真正不同；旧上沿由A冻结，触发后仍要求下一独立原池帧成交。代码检查了 activation、observed≤ingested≤recorded≤decision、同pair、同provider、≤60秒gap、9个≥15秒独立帧。未见未来frame泄漏。

7. **seller absorption — 可部署，但只能叫卖笔份额翻转/承接**
代码使用 buy/sell count share，不是金额。当前合同表述已经收敛，不再冒充“大额卖压被吸收”。允许Paper。

8. **price-then-depth — 可部署，但只限“报告liquidity追认”解释**
同provider连续序列可避免直接跨源拼接；代码要求B价格先动而liq≤A×1.05，C价盘整后liq≥A×1.20。不能解释为LP净注资或真实深度增加。

### 新4 exit + baseline

9. **profit budget — 条件GO**
使用 `economic_value = realized proceeds + remaining × 当前卖出成本后净值`，比旧不可达principal状态干净。
但公共 trailing 在经济收益≥30%后已经生效，约当净利润峰再高时会先触发通用退出；FINAL_CONTRACT已承认遮蔽。**因此只能比较实际发生的退出原因分布，不能声称完整检验了理论profit-budget区域。**

10. **progress clock — 条件GO**
代码不是逐帧+1%，而是累计超过anchor +1% stake才更新时间；断流>60秒/provider切换重置时钟，测试也覆盖“180秒缺数据≠横盘”。语义正确。

11. **depth divergence — 条件GO**
两次连续 price↓ + economic value↓ + reported liquidity 每次>1%↑。属于有意研究“价跌、报告liq增”的反向状态。只能叫report-liquidity divergence。

12. **activity failure — 条件GO**
price/economic value↓同时buy-share与rolling m5 volume↑。这是活动无法转化为价格的代理，不能称真实资金流失败。

13. **baseline — 必须部署，非alpha**
没有它，9–12无法回答退出增量。

---

# 三、五臂 paired entry 是否会“全拒绝”

**不会结构性永久全拒，但设计上确实是 all-or-none。**

Store 实际逻辑：

- 同 `paired_entry_group` 聚成5臂；
- `paired_entry_size` 必须等于实际组大小5；
- 只要任一臂未进入 `admitted_arms`，整组全部从本机会删除；
- 资金检查时，任一臂现金不足，整组删除；
- 4仓上限在更前面通过 `max_concurrent_positions=4` 逐arm阻挡，因此任一臂满4仓同样导致整组不进；
- 测试已经验证4个不同token各形成5仓，第5个token不再进入，共享 `source_entry_fill_id`，每仓5U。

所以合同“任何一臂没资金/槽，本机会全组不进”与代码一致。

但经济解释必须严格限定为：

> **相同受限 admission 下的 exit treatment comparison**

不能用它回答：

> 某快速退出策略独立运行时能否靠更快资本周转赚更多。

这是解释限制，不是部署 blocker。

---

# 四、我发现的一个部署前必要缺口

当前 `tests/test_research_finalists.py` 已实际覆盖：

- 三entry正反例/未来时钟；
- dense sampling；
- source切换；
- 四exit纯函数；
- 成本/账户独立；
- 三链后帧；
- 5臂共同fill；
- 4仓上限。

**但我没有看到 Store → `_capital_exit_result` → pending mark → 下一原池帧正式SELL 的端到端定向测试。**

源码 adapter 已经实际接入 `EXIT_KINDS`，并把：

- mark provider
- m5 volume
- buys/sells
- 当前4%卖出净值
- realized proceeds

送入 `evaluate_finalist_exit`；随后通用 exit loop 会把 SELL 转成 `CAPITAL_EXIT`，且仍要求 next-frame/新鲜原池结算。

因此不是“代码没接”，而是**尚缺一条接线级证据**。

### 最小必要修正/验收
部署前只需补最窄测试：

**任选一个 finalist exit，在真实 Store fixture 中制造3个合法 held marks → 产生 CAPITAL_EXIT pending intent → 再一份独立原池帧完成SELL；baseline同entry不触发该原因。**

无需新平台、无需大测试、无需新DB结构。

在这条通过前，我给4exit：

**CODE EXISTS / PURE LOGIC PASS / DEPLOYMENT CONDITIONAL**

而不是“已可确认完整接线”。

---

# 五、80帧、静默、来源切换

### 没数据误认静默：当前新3entry没有这个问题
`finalist_signal`：

- <9独立帧 → WAIT；
- span不足120秒 → WAIT；
- hole >60秒 → WAIT；
- NULL/负liq/缺count/volume → WAIT；
- provider变化 → source boundary；
- activation以前帧不能用。

不会把缺数据补0为compression/acceptance。

### source switching
实现比合同甚至更保守：选定窗口中只要出现不同 `upstream_provider` 就整段拒绝，直到新provider自己形成完整序列。**不会跨源拼接先后关系。**

### 80帧
新3 entry 只需9帧、120–600秒，所以如果 observer 常见约15秒级帧，80帧足够；如果密到约1秒，80帧可能不足120秒，候选会WAIT。这是有意保守，不能通过放宽因果间隔“修交易数”。

185 cycle 的720秒要求更容易受该上限影响，应继续标 coverage待证。

---

# 六、外部论文与本地证据

采用 `EXTERNAL_CORRECTIONS.md`：

- Pump研究 `0.198%` **不能称24h毕业率**；
- 钱包论文修订后约+16.1%买方关联，SOL流入+6.3%且区间含0；不能作为wallet alpha；
- BONK具体t0仍未裁决，不用于本地规则。

`TOKEN_PRECURSOR_EVIDENCE.md` 的冻结本地对照更直接：当前 chain-meme 的边际 volume/buy-ratio/count 差异很大，但分层极稀疏甚至暴涨vs失败为0个可比较≥3/3 strata。因此没有证据支持把当前3个新entry阈值写成“论文/历史证明最优”。它们只能是**预注册状态机假设**。

---

# 七、与其他R2的实质分歧

我明确修正 `R2_DATA_ENGINEERING` / `R2_CAUSAL_STATISTICS` 当时对 profit-lock 的处理。

它们基于当时可见统计，把 `-62.54U` 作为当前 profit-lock 的负面机制证据，并倾向继续作为negative control。

**R3根据后来完成的 EFFECTIVE_POLICY_CORRECTIONS + Store实际setter路径裁决：不能这样解释。**

因为该 exit family 永远没有写入 `principal_recovered/cost_covered` 的可达路径，所以历史结果不是“正确L0锁利机制自然失败”，而是一个**合同没有完整接通的不同实验**。

因此 FINAL_CONTRACT 不把旧192列入最终5代表是正确的。

---

# 八、R3最终裁决

**可部署小额Paper：**
- 新3 entry；
- baseline；
- 4 exit，**前提是补1条最小Store退出接线测试通过**。

**仅限条件/证据解释：**
- 185 cycle；
- 194 clone leader；
- 196 relative resilience；
- price-then-depth 的 liquidity 语义；
- paired5臂的资本周转收益解释。

**阻止部署：**
- 当前没有发现需要永久阻止新8账户部署的机制错误；
- 若新增的端到端 exit fixture 暴露 next-frame/状态保存/正式SELL链路缺陷，则只暂缓4exit+baseline相关阶段，最小修复后再部署，不扩大范围。

**继续 BLOCK：**
- alpha/长期盈利宣称；
- 增资；
- Live；
- 用注册/测试PASS冒充经济证据；
- 用当前短窗或外部论文给阈值背书。

### 实际读取路径
- `.../FINAL_CONTRACT.md`
- `.../EFFECTIVE_POLICY_CORRECTIONS.md`
- `.../TOKEN_PRECURSOR_EVIDENCE.md`
- `.../EXTERNAL_CORRECTIONS.md`
- `.../R2_DATA_ENGINEERING.md`
- `.../R2_CAUSAL_STATISTICS.md`
- `src/memetrader/research_finalists.py`
- `tests/test_research_finalists.py`
- `src/memetrader/store.py`：finalist注册、80帧历史、max_concurrent、paired-entry admission/cash、`_capital_exit_result` adapter、通用exit优先级/next-frame结算必要段落。

**R3 MICROSTRUCTURE FINAL: `CONDITIONAL GO`。当前设计已比R2旧16草案明显收敛，最大剩余工程验收点不是再研究新机制，而是补齐四个新exit实际Store结算路径的一条最小端到端证据。**
