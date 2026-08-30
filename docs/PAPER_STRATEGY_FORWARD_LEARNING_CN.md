# Paper 策略前向学习框架

## 1. 要解决的问题

长期需要研究的不是一个“热度分”，而是以下条件组合在真实前向样本中的差异：

- 事件热度、传播速度、舆论方向和独立来源结构；
- 公众人物、机构或社区关联的类型、原始性和可核验程度；
- Token 创建时间、流动性、成交量、买卖结构、momentum、安全状态和事件映射强度；
- 首次买入金额、是否允许第二段确认入场、止损、分批止盈、移动退出、叙事衰减和 runner 留仓；
- 报价年龄、模拟执行差、场地费、Token 税、失败成交和不可卖状态。

公众人物或高热度只能作为研究分层，不能直接放大仓位、增加买入次数、跳过 canonical/safety 门或解释为背书。仓位始终受确定性风险预算、现金、流动性、当日 exposure、最大仓位数和安全门约束。

## 2. 当前基线

- 一次 CANDIDATE 最多一次入场；已有仓位不加仓，避免早期样本用 DCA 隐藏错误判断。
- 买入金额由权益风险、现金比例、单币上限、流动性占比、当日 exposure 和最大持仓数的最小值决定。
- 最多四层止盈，`sell_fraction` 作用于当时剩余仓位；安全恶化、流动性紧急、硬止损、叙事/买盘衰减、移动退出或最长持仓触发时全仓退出。
- 每侧 4% 为保守不利执行压力；通用场地费估计每笔 60 bps，明确识别 PumpSwap 时用 125 bps 上限。它们不是 Mainnet 回执，链费与 priority fee 在没有可验证路由时保持未建模。
- Live 永久锁定；本框架只适用于 Paper/Shadow。

## 3. Phase 1：只记录，不改变策略

新增前向 cohort 时必须覆盖所有最终 `WAIT / REJECT / CANDIDATE`，以及风险拒绝、报价拒绝、未成交和成交，不能只保存赢家或已买入样本。建议追加式结构：

1. `paper_strategy_decision_cohorts`：冻结 decision、事件、Token、当时价格、基线 action/notional/exit plan、执行状态和稳定 reason code。
2. `paper_strategy_cohort_labels`：只冻结决策前本机可用数据。包含 topic、attention/freshness/独立来源桶、F/C/I/P 数量、社区状态、公众人物关联类型、流动性/量/买卖比/momentum/Token 年龄/安全桶及执行成本桶。人物姓名不能成为仓位特征。
3. `paper_strategy_outcomes`：按 15/60/240 分钟记录后来真实观察到的 price/high/low 或 missing；真实成交完全平仓后再记录扣除手续费、滑点和已知税的净结果、持有时间、退出原因。

固定时点只能在 `target_at` 到达后选本机后来真实采集的快照。历史不回填，missing 不用当前价格补值；失败和零产出保留在分母中。高低点随访只能描述市场路径，不能伪装成某个反事实止盈方案已经成交。

## 4. Phase 2：预注册 Paper 对照实验

只有 Phase 1 样本成熟后，才可按稳定 hash 在入场前把通过全部现有门槛的 cohort 分到 baseline 或一个 challenger；assignment、版本、参数和上限必须在看见结果前追加保存，不能事后改组。

一次实验只比较一个维度，例如：

- 一次入场 vs. 预先规定、只在新证据仍合格时触发的两段入场；
- 当前四层止盈 vs. 较早回本后保留固定 runner 的退出计划；
- 当前 position cap vs. 只允许更保守下调的金额计划；
- 当前最长持仓 vs. 针对叙事仍活跃且链上买盘持续的延长计划。

所有 arm 共用相同的 canonical、安全、报价年龄、现金/流动性/日限、最大仓位、费用/税和 Live lock。Agent/LLM 不直接选择仓位、止盈或 runner；公众人物/社区关联不参与随机分配或金额放大。

## 5. 成熟门与变更边界

Phase 1 描述性分层至少要求：每标签 30 个独立 decision cohort、10 个决策日、固定时点 missing 低于 20%，并同时展示 WAIT、REJECT、CANDIDATE 和 failed fill 分母。

Phase 2 每个实验 arm 至少要求：50 个真实完成平仓、20 个决策日、20 个不同事件、至少 15 个非正向结果、完整成本/报价字段，且 topic 与链上质量分层没有严重失衡。达到门槛也只能提交人工复核的新版 Paper plan；新版本还要经过独立 holdout，不能直接推广到 Live。

禁止：历史回填 cohort、根据后来 ATH 选择 runner、同时优化金额/次数/退出、删除亏损或 failed fill、把同一事件重复转载当独立样本、逐笔自我改写参数、因为短期盈利放宽安全门。

## 6. 当前实现状态

Phase 1 已复用现有 `shadow_event_*` 账本前向运行，没有另建一套脱离 Runtime 的模拟链：

- 每个独立事件的首次 `WAIT / REJECT / CANDIDATE` 分别形成一个 event-action cohort；每一次最终决策无论是否建成 cohort 都进入 admission 分母并保存明确跳过原因，避免用高频重试伪造独立样本。
- event-action cohort 全部保留用于动作审计，但平台、人物、题材和链上分层的成熟度只使用每个事件时间上最早的 cohort；同一事件从 WAIT 演化到 REJECT/CANDIDATE 不会被当成多个独立市场样本。
- cohort 冻结当时平台、信息类型、人物/实体、事件主题、热度、新鲜度、合格来源组合、公众人物关联状态、链、Token 年龄、流动性、市值、5 分钟量、买卖压力、安全状态、评分层、canonical margin、请求仓位和拒绝原因。
- `token_snapshots` 从本版本起额外保存本机 `ingested_at`。entry 必须在决策时已经入库；15/60/240 分钟 outcome 必须在对应 target 之后才入库。升级前没有入库时间证明的旧快照不会被回填成新 cohort 或 outcome。
- Paper 买卖执行尝试同时保存 `decision_id/cohort_id`；成功成交、报价拒绝和执行拒绝可沿同一链审计。旧的无链接尝试继续标为 unlinked，不能借用后来 cohort。
- Token Context 的重复 assessment 仍完整保存，但描述统计和成熟度每个 Token 只采用最早的前向 cohort，且普通标签至少需要 30 个不同 Token；同一价格路径不能重复抬高样本量。
- `watch-attention/v2-exact-entity` 只接受具体账号明确映射人物的市场证据，不再用平台总体表现作为账号回退。Overview 直接显示当前版本独立事件、W/R/C、固定时点缺失、独立 Token、精确 Paper 链和 Phase 2 数据门。

仍未实现的是 Phase 2 的预注册 assignment、challenger 执行器和完整闭仓策略对照实验；也不会因为 Phase 1 某个分层短期上涨就自动改变金额、入场次数或退出。现有确定性 Paper 基线继续运行。
