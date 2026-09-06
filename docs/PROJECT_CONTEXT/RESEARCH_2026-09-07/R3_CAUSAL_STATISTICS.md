# R3 CAUSAL_STATISTICS

Source Chat: 6a9d94b1-0a10-83ee-ad29-cb5abbb949c8

Actual response; model/reasoning not independently verified. Snapshot review, not deployment certification.

[GXH_C2C_V3]
MESSAGE_ID: C2C-20260907-R3-CAUSAL_STATISTICS-RESULT
REPLY_TO: C2C-20260907-R3-CAUSAL_STATISTICS
TYPE: RESULT
CYCLE_ID: ALL_HISTORY_20260907
ROLE: CAUSAL_STATISTICS
BLOCKS_RELEASE: true
DISPOSITION: **APPROVE_WITH_MINIMAL_FIX_AND_VALIDATION / BLOCK_ALPHA_CLAIM**
MODEL: GPT-5.6 Sol；实际推理配置/档位 **未核验**
SENSITIVE_DATA: NONE

## R3结论

当前合同已经实质替代 R2 的“8复用+8新”。我撤回 R2 中基于旧草案的以下判断：

- 撤回“migration amount absorption/participation wallet 作为最终代表”：当前 V002 实际已是 L0 替代。
- 撤回“`l0_profit_lock` 的 -62.54U paired delta 可反证正常锁利机制”：`EFFECTIVE_POLICY_CORRECTIONS.md` 与代码证明其 `principal_recovered/cost_covered` 状态不可达，历史差值主要是半卖/全卖合同差异，**不能归因于正确工作的 L0 profit-lock**。
- 撤回“新增约3–5 entry”的旧建议。当前实际是 **3新 entry + 4新 exit + 1 exit baseline = 8新增账户**，结构更干净。

**12个重点机制 + 1个退出基线的总体设计可以进入小额Paper，但在部署前还缺一个最小的Store级退出接线验证。** 不支持因此增加新平台、API、DB或大规模审计。

---

## 逐项裁决

### 既有5代表

1. **stage190 rolling L0 deterioration** — **可继续Paper**
真实接线与描述一致；属于退出机制，不是entry alpha。

2. **stage187 volatility-scaled momentum** — **可继续Paper**
代码/纠偏材料支持。`pressure`只能解释为 rolling count/volume/liquidity 代理，不是金额净流。

3. **stage196 relative resilience** — **可继续但只限证据解释**
1 BUY，自然覆盖极稀疏。机制存在，但不得称市场regime或已验证相对强度。

4. **stage185 cycle reset** — **条件型Paper，不阻止部署**
合同要求≥16帧、≥720秒；当前observer仅最近80帧/20分钟。高频市场中80帧可能覆盖不到720秒，因此0 BUY首先是coverage，不是机制失败。**不得通过缩短720秒门来制造交易。**

5. **stage194 same-symbol liquidity leader** — **条件型Paper**
真实语义是同链/lifecycle/规范化symbol局部集合，不是语义“同题材”。0 BUY同样不得解释为失败。

---

### 3个新entry

6. **`finalist_boundary_retest_v1`** — **可部署5U Paper**
代码确有A→B→C三阶段，A冻结上沿；trigger后仍等下一独立原池观察成交。与旧峰值reclaim有行为差异。

7. **`finalist_seller_absorption_v1`** — **可部署5U Paper，解释受限**
实际是 buy/sell **笔数份额**翻转+价格承接，不是金额吸收。名称虽保留 absorption，但报告必须使用“卖笔多数后的承接/份额翻转”，不能写大户吸收、净买流。

8. **`finalist_price_then_depth_v1`** — **可部署5U Paper，强解释限制**
实现确实是**价格先脉冲，随后同来源 reported liquidity 追认**，与旧 liquidity-leading 假说方向相反。不得解释为 LP 注资、真实深度或净流。

三者共同的时序实现总体正确：

- 9个至少15秒间隔帧；
- 120–600秒跨度；
- 最新≤30秒；
- 中间任何缺字段/NULL/负liq都拒绝；
- token/pool/source一致；
- `observed <= ingested <= recorded <= decision`；
- 最大中间gap 60秒；
- provider切换不能拼接，必须等新provider形成完整新序列。

**80帧足以形成这三个新entry所需的120秒序列，只要真实帧跨度达到120秒；不足就WAIT。**

---

### 4新exit + baseline

9. **profit budget** — **可部署，但只估计“公共安全壳上的增量退出”**
净经济值使用已实现回款 + 剩余数量按实际Paper sell terms计算，成本口径正确。
但公共 +30% trailing/hard-stop/max-hold 在 capital exit 前判定；合同自己已承认峰值较高时公共trailing可能先触发。因此不能宣传为“纯profit-budget结果”。

10. **progress clock** — **可部署**
实现不是“每帧必须涨1%”，而是累计新高超过stake 1%才刷新；180秒无实质进展退出。>60秒观测断层会reset，因此**数据缺口不会被当成横盘静默**。测试对此已有明确反例。

11. **price↓ + liquidity↑ divergence** — **可部署，解释受限**
连续两次 price/value下降且reported liquidity每次>1%增长。只能说报告流动性背离，不能称真实LP行为。

12. **activity↑ + price↓ failure** — **可部署，解释受限**
buy-count share和rolling m5 volume上升同时price/value下降。rolling窗口不能解释成逐笔新增资金流。

13. **baseline** — **必须保留**
与9–12共享完全相同受限入口和公共exit，没有四个附加退出；这是因果比较所必需，不是第13个alpha。

---

## 五臂配对：代码核验

**配对不会因为实现错误“天然全拒绝”。**

`store.py` 当前逻辑：

- 五臂均有 `paired_entry_group=finalist_exit_matched_v1`
- `paired_entry_size=5`
- 必须五臂全部进入 `admitted_arms`
- 任一臂因现金不足/4仓满/其他entry block失败，整组本机会全部取消
- 随后再次检查五账户现金；任一不足同样全组取消
- 相同5U notional进入同一 cohort/fill
- 每账户独立position/cash/exit state

`tests/test_research_finalists.py` 已在 Solana/BSC/Robinhood 验证：

- 前4个token各产生5仓；
- 第5个因4仓限制整组不进；
- 每组5仓共享同一个 `source_entry_fill_id`；
- 每仓5U；
- 数量为 `5/1.04`；
- 各账户现金流独立为-20U。

所以这是**有意的共同受限入口 estimand**，不是自由周转收益。以后不得拿快退出臂因更早释放槽位而产生的额外机会优势混入这组paired效果。

---

## 唯一建议的部署前最小必要补项

当前测试文件验证了：

- 纯函数正反例；
- future/duplicate；
- provider切换；
- 进展时钟缺数；
- 三链共同entry；
- 成本和4仓。

但我实际读到的测试**尚没有Store级证明四种capital exit在真实持仓mark适配后产生 pending `CAPITAL_EXIT`，再由既有下一原池帧结算**。

代码接线本身存在：

`_capital_exit_result → evaluate_finalist_exit → capital action → pending mark`

但“代码可达”仍弱于实际集成验证。

因此部署前只要求一个最小补测：
**至少把四exit各触发一次经过Store适配器，确认生成正确pending mark/next-frame语义，并确认baseline无该附加trigger。**

这是本轮唯一会让我暂缓8个新增账户部署的事项；补过即可，不要求扩大测试平台。

---

## 与其他R2的实质分歧

我与 `R2_DATA_ENGINEERING` / `R2_MICROSTRUCTURE` 对旧 profit-lock 的处理现在有实质分歧。

它们基于当时证据主张：

> 保留 `l0_profit_lock` 为负向/受控退出实验，-62.54U 是现有反证。

**R3裁决：该解释必须撤回。**

`EFFECTIVE_POLICY_CORRECTIONS.md` 已用实际代码路径证明：

- evaluator要求 `principal_recovered or cost_covered`
- adapter没有写 `cost_covered`
- principal flag只对 `principal_lock_runner` 特定TP写1
- 当前 `l0_profit_lock` 不属于该exit_family
- 93仓全部 principal=0
- 15次部分卖出
- 0次 `l0_two_frame_profit_lock`

所以 -62.54U 不能反证“正确实现的回本后连续恶化锁利”；它只能描述**现有错误/不完整合同下的半卖vs全卖结果**。当前最终设计改用“净利润预算”，不依赖这个不可达布尔状态，是更干净的修正。

---

## 外部论文与本地前置证据

采用 `EXTERNAL_CORRECTIONS.md`：

- Pump.fun **0.198%不是完整24h毕业率**，v3约6分钟采集，只能作下界；
- 钱包论文v3修正后 buyer关联约+16.1%，SOL inflow约+6.3%且区间含0；旧132%/136%结论撤回；
- BONK日期仍不作为策略t0；
- Chat内部 `turn...` citation不作为本地独立证据。

本地 `TOKEN_PRECURSOR_EVIDENCE.md` 更关键：

- universe 12,000 hash cohort只有4,412可做60m四分类；
- chain-meme 2,729 h0中60m observed只有506；
- current chain-meme的暴涨vs失败在冻结分层下**0个层同时两边≥3**；
- volume/buy-ratio/count的边际差异方向跨层不稳定。

因此当前12机制只能被称作**预注册假设**。没有任何本地或外部证据允许把这些阈值宣传成alpha或“历史验证最优”。

---

## 实际读取路径

- `docs/PROJECT_CONTEXT/RESEARCH_2026-09-07/FINAL_CONTRACT.md`
- `.../EFFECTIVE_POLICY_CORRECTIONS.md`
- `.../TOKEN_PRECURSOR_EVIDENCE.md`
- `.../EXTERNAL_CORRECTIONS.md`
- `.../R2_MICROSTRUCTURE.md`
- `.../R2_DATA_ENGINEERING.md`
- `src/memetrader/research_finalists.py`
- `src/memetrader/forward_patterns.py` 必要模板段
- `src/memetrader/capital_exits.py::_begin`
- `src/memetrader/store.py` finalist注册、80帧history、4仓、paired-size/cash、entry projection、capital-exit适配及公共exit优先级必要段
- `tests/test_research_finalists.py`

未运行大SQL、未修改代码/DB/Runtime、未部署、未访问secret。

**最终：12机制合同本身可接受；8新增账户在补齐一个最小Store级退出接线测试后可增量5U Paper部署。阻止alpha/资本晋级，不卡严格前向研究。**
