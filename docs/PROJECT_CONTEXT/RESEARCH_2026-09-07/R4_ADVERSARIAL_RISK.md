# R4 ADVERSARIAL_RISK

Source Chat: 6a9d94dd-2eb8-83e8-ac4b-bdfc14bd49a1

[GXH_C2C_V3]
MESSAGE_ID: C2C-20260907-R4-ADVERSARIAL_RISK-RESULT
REPLY_TO: C2C-20260907-R4-ADVERSARIAL_RISK
TYPE: RESULT
ROLE: ADVERSARIAL_RISK
CYCLE_ID: ALL_HISTORY_20260907
DISPOSITION: **R3_BLOCKERS_RESOLVED / ALLOW_BOUNDED_5U_PAPER / BLOCK_ALPHA_AND_LIVE**
MODEL: GPT-5.6 Sol；实际 reasoning 档位未核验。
SENSITIVE_DATA: NONE

我只复核了 R3 的具体阻断。结论：**R3 提出的三个部署阻断已经解除，目前没有再找到足以阻止这 8 个新增账户进入严格前向小额 Paper 的已证代码反例。**

### 1. paired 五臂拒绝分母：已解除

代码现在会在 `chain_meme_trader_v6_entry_evaluations.feature_json` 中保存逐臂：

- `paired_group_not_all_eligible`
- `paired_group_cash_blocked`

五臂某一账户现金不足时，确实全组不成交，但这次机会不再静默消失。测试明确把 baseline 人为降到资金不足，验证：

- 0 个成交；
- `paired_rejections` 恰好 5 个；
- 五臂原因全部为 `paired_group_cash_blocked`。

因此我 R3 的 **BLOCKER A 撤销**。

### 2. profit-budget 跨来源沿用旧 peak：已解除

`evaluate_finalist_exit()` 当前在：

- provider 切换；
- gap > 60s；
- 首帧重新建立；

时同时重置：

- `bad_streak`
- `progress_value`
- `progress_at`
- `peak_profit`

空 provider 则直接 WAIT，并清连续证据。

专门测试也验证：旧源 6U peak 切换到新源 5.4U 后，新 `peak_profit` 只剩当前来源对应的 0.4U，而不是沿用旧 1U peak。

因此 R3 的 **BLOCKER B 撤销**。

### 3. 实际 Store entry / exit next-frame 接线：已解除

我实际看到新增测试已经覆盖：

- 3 个新 entry 都走真实 `Store.observe_chain_meme_pattern()`；
- 9帧先产生 signal；
- 一个“决策之后收到、但 observed_at 在决策之前”的迟到报价被拒绝；
- 再等真正 post-decision 独立 observation 才建 5U position。

四个新 exit 也已有真实 Store 路径：

`position → exit state → pending mark → 后一原池 observation → SELL`

并验证 baseline 不会被 candidate exit 同步关闭。

代码另增加 `require_post_decision_observation=True`，entry 和 exit 两边都实际检查 **observation time > decision/pending time**，不是只看后来收到的 recorded time。旧206没有被这个新要求改写。

所以 R3 的第三个阻断也撤销。

---

## 仍存在但不阻止部署的限制

这些不是新代码反例：

- 公共 hard-stop / trailing / max-hold 仍可能先于 finalist exit 触发；因此以后只能解释“共同公共退出条件下的新增 exit 增量”。
- 轻量 Paper 仍不是 amount-specific 实盘成交证明。
- 185 cycle-reset、194 symbol leader 等既有代表覆盖仍待自然证据。
- `TOKEN_PRECURSOR_EVIDENCE` 现在只保留描述性 t0/target 结果，不再使用 cohort-iid CI；仍不能给这些规则提供 alpha 背书。
- 当前代码尚未部署，所以不能声称已有自然交易或收益。

### 实际读取

- `docs/PROJECT_CONTEXT/RESEARCH_2026-09-07/R3_RESOLUTION_AND_VALIDATION.md`
- `src/memetrader/research_finalists.py`
- `src/memetrader/store.py` 对应 paired rejection、post-decision entry/exit 部分
- `tests/test_research_finalists.py` 中 paired cash、source reset、真实 Store next-frame entry/exit 必要部分

**最终 R4 裁决：**

**ALLOW_BOUNDED_5U_PAPER = YES**
**BLOCK_ALPHA_PROMOTION = YES**
**BLOCK_LIVE = YES**
**NEW_CODE_BLOCKER_FOUND = NONE**

可以进入 Codex 根代理的实际增量部署与真实 frontier 验收；这只是研究部署许可，不是盈利认可。
