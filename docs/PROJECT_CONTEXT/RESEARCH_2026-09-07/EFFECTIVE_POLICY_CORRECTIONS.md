# 当前有效策略合同纠偏

只读结论；未改运行代码、数据库或部署。依据 `data/research/20260907/extract.json.gz` 中最终资金期 `chain-meme-trader/funding-20260906-v002-final-1000` 的冻结 registration + policy_additions，以及当前 effective-definition / revision / dispatcher 实现。样本截止 `2026-09-06T16:46:50.205259Z`，不是旧 factory 默认策略。当前资金期内既有策略仍可能是 V001，不能因为资金期名字含 V002 就全称 V002。

## 八个拟复用代表

| ID / stage / 已存 hash | 当前实际机制 | 已有输入/自然路径证据 | R2 必须如何修订 |
|---|---|---|---|
| `l0_continuation_failure_candidate_v1` / 190 / `cdaa283649dca221` | V002。Broad 同入场；`capital_exit_kind=l0_loss_deterioration`。持有≥60秒后设基线，至少两次价格下降且 liquidity 不增、相邻接受帧间隔≥5秒、帧龄≤30秒、剩余净回收<剩余成本则下一帧退出。candidate/control 都有10分钟经济收益未转正退出、30分钟 max-hold。 | 115 BUY；98闭环，3次实际 `l0_loss_deterioration_armed`，30次 `market_mark_runner_not_profitable`。原池L0路径确实运行。 | **保留但改称“滚动 L0 衰退退出”**，删除“60/120秒固定承接检查”。这是退出对照，不是新入场alpha。 |
| `l0_profit_lock_candidate_v1` / 192 / `270a792accb4cddd` | V002。净经济收益25%时卖一半，control卖全部；60分钟max-hold，追踪在经济收益≥100%激活、15%回撤。仍分派到L0 profit-lock，但回本门没有可用状态写入，见下。 | 93 BUY、15次第一档部分兑现、`principal_recovered=0` 全部93仓；0次 `l0_two_frame_profit_lock`。有半仓兑现，不等于L0锁利已生效。 | **暂不作为已正常运行的L0锁利代表**；统计差异包含“半卖 vs 全卖”，不能归因连续恶化锁利。 |
| `observed_cycle_reset_reacceleration_v1` / 185 / `3e9fea28ba32b990` | 仍是V001 `cycle_reset`。≥16帧、总跨度≥720秒，gap≤90秒，池龄≥1800秒；已观察首波≥1.35倍、峰距今360–900秒、低点/峰0.50–0.75；距今60–300秒的基线≥6帧且跨度≥180秒，基线价宽≤1.08倍、量≤峰附近中位量0.5倍；重启价/基线1.12–1.35且≤旧峰0.9，量加速≥1.5，liquidity保留≥0.8，买占比≥0.6、count≥6。 | 机制未替换，但当前0 BUY。observer只有最近80帧/20分钟；密集采样可能使80帧不足720秒，缺帧也不得当静默。 | 原机制描述成立；只能列**覆盖待证的条件型**，不能据“已有L0”宣称自然首波/重置历史已可用。 |
| `volatility_scaled_depth_flow_momentum_v1` / 187 / `31658fe46dc92702` | 仍是V001 `volatility_flow`。最近9帧跨度120–600秒，gap≤90秒，池龄900–21600秒；前6个按√时间归一化log-return用MAD估σ（floor0.005、scale1.4826）；最后3帧位移1.04–1.25、z≥2；末两帧买占比≥0.6，count≥8；pressure=`(2*buy_ratio-1)*volume/liquidity`为正并增至≥0.02，末3帧liquidity≥前7帧中位数85%。 | 当前15 BUY，14闭环；L0序列能够在部分自然token中满足。 | **可保留为L0波动归一化动量代表**，明确pressure是聚合代理，不是观察到的带方向金额流、链上净流或盘口OFI。 |
| `clone_liquidity_leader_v1` / 194 / `068cc41bc1d9de3b` | 仍是V001 cohort。冻结同链、同lifecycle、同规范化symbol的5–25候选，发现跨度≤600秒、帧龄≤30秒，选唯一liquidity最高者，等下一独立原池帧；并非语义模型判断“同题材”。 | 当前0 BUY。需要自然出现可冻结的完整候选集；代码中有入口不代表候选集合实际可用。 | **条件型储备**。将“同题材”改为“同规范化symbol的局部候选集”，不得从当前全部市场事后选leader。 |
| `observed_set_relative_resilience_candidate_v1` / 196 / `a878132931458493` | 仍是V001 cohort。实际passive pilot用同链/lifecycle的3–4成员集合（不是通用纯函数默认5–25）；冻结初始目标后，连续2轮、轮间≥5秒、轮内skew≤5秒，≥60%成员负回报且中位数<0，目标不破自己前低且liquidity return≥0，才等下一原池帧入场。 | 当前1 BUY/1闭环；路径有自然入口，覆盖仍非常稀疏。 | **可保留为稀疏条件型代表**，只能称已观察局部集合，不称全市场regime或已获充分验证。 |
| `migration_amount_rate_absorption_v1` / 182 / `9d8b4534851356fb` | **V002已替换**为 `evidence_extension_l0 / young_absorption`：池龄≤2400秒，至少3帧/20秒，count≥10、m5volume≥1200、末帧买占比≥0.6；价格/基线1.04–1.22，所有窗口liquidity≥基线，末2帧买占比≥0.5。5U，15分钟max-hold。 | 51 BUY、48闭环，证明的是年轻池L0三帧承接；不需要原migration receipt/相邻真实金额窗。 | 删除“精确迁移+金额吸收代表”。若讨论它，只能叫**年轻池三帧L0承接**，并用于核对新增候选同质化。 |
| `experiment_participation_candidate_v1` / 143 / `66086392a85c39f9` | **V002已替换**为 `evidence_extension_l0 / early_quality`：池龄≤900秒，聚合count≥12、m5volume≥1000、volume/count≥40、买占比≥0.6；没有独立钱包扩散门。15分钟max-hold，+30%半卖/+80%清仓、30%激活15%回撤追踪。 | 68 BUY、64闭环，证明的是公开交易强度/买方count倾斜代理，不能将这些BUY算作钱包扩散已接通。 | 删除“真实已解析买方地址扩散代表”。若复用，名称必须是**早期L0参与强度代理**。 |

所有历史 BUY 数都只说明截止前存在自然路径，既不是输入全面覆盖，也不是盈利证据。原池未知/陈旧仍须WAIT，现行共同执行设置4%/4%/0U/1000USD保持原有边界。

## L0 profit-lock 回本状态不可达的精确原因

`l0_experiments.py:234–235` 要求 `principal_recovered or cost_covered`，否则直接 `WAIT: cost_not_yet_recovered`。`store.py:31554–31556` 的 adapter 只复制position并派生remaining_cost，不按已实现回款派生cost_covered。position的principal标志在schema默认0（`store.py:2815`）；唯一置1路径 `store.py:32786–32802` 要求 **exit_family == principal_lock_runner** 且非全平TAKE_PROFIT。

当前候选exit_family是 **l0_profit_lock**，所以普通半仓成交即便已实现回款足够也不进入这个setter；没有Store写cost_covered的另一条路径。离线93仓、15次半卖、全部principal=0、无L0锁利原因，和代码断路吻合。不能把它弱化成“只是触发概率低”。正常+25%时半卖理论回款约12.5U < 原20U还构成第二层经济限制，但**首要工程断点是状态从不设置**。

在修复并定向验证前，应把它从“已经可工作的回本后L0锁利”名单移出。现有结果可描述半卖与全卖的差别，不能作为已正常生效的连续恶化锁利成败证据；本次没有实施该修复。

## 源码路由定位

- `store.py:25199–25216`：新资金期prepare_policy执行revision并冻结hash/历史；`store.py:7333–7340`：effective definition仅注入执行设置，不能用原factory覆盖已冻结的revision。
- `strategy_revisions.py:360–383`：当前两组L0 V002修订；`strategy_revisions.py:386–455`：滚动loss evaluator；`store.py:31532–31563`：按实际capital_exit_kind分派。
- `revision_evidence_extensions.py:78–87,112–165,245–334`：migration/participation替换规格、元数据与L0 evaluator；`store.py:26959–26968`：entry_revision_kind优先于capital_experiment/旧pattern分支。
- `forward_patterns.py:109–214,217–239,289`：cycle/volatility合同、实际计算和因果输入门；`store.py:26664–26673`：20分钟/80帧同原池读取上限。
- `cohort_experiments.py:31–66,284–356,378–402,437–547`：clone与相对韧性合同；`cohort_experiments.py:962–1014`：实际passive入口使用3–4成员规则和冻结集合。
- `store.py:33646–33709`：10分钟runner review、当前take-profit档位、附加退出分派；退出触发之后仍由现有下一独立原池帧结算。

## 对最终既有代表的裁决

这八个中，**优先保留两个自然输入已出现且当前机制匹配的代表**：滚动L0衰退退出、波动归一化L0动量。第三个相对韧性可作为明确标注稀疏覆盖的条件型代表。cycle-reset与clone-leader机制存在但当前自然候选覆盖未证；profit-lock有具体阻断；两个旧名字已变为其他机制。不能强凑四个“已按原机制正常运行”的代表。

若根代理选择复用migration/participation当前L0替代机制，必须按本表改称、说明与新增L0序列的重叠，并承认它不是原金额流/钱包代表。未因此关闭或修改任何旧策略。
