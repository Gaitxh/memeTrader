# Token Context 前向结果学习

## 目的

Token Context 会调查“这个 Token 为什么出现、社区是否跨平台传播、是否存在公众人物关联、是否有独立报道”。本模块回答的是另一个问题：**哪类调查入口和语境标签，长期更值得继续研究**。

它不是交易信号学习器。结果永远不会改变证据资格、候选排名、WAIT/CANDIDATE、安全检查、仓位、退出、Agent 调度或 Live。

## 冻结样本

每次新调查完成时，只在评估时点已经存在本机正价格快照的情况下建立一个 cohort，并冻结：

- assessment 状态，包括 `verified_reporting / no_context / agent_error / insufficient_verified_sources`；
- 触发类型：链上动量、浏览器精确高影响力账号原帖或新鲜高热事件关系；
- 项目附带声明状态；
- 社区扩散状态与平台；
- 公众人物关联状态与候选平台；
- 已由本地验证的独立报道域名；
- 调查时链上动量区间。

未核验的公众人物姓名不会成为实体学习标签。只有浏览器桥在本机实际接收、与配置账号 URL 和 `entity_id` 精确匹配的原帖，才可冻结 `verified_public_figure_entity`；即使如此也不推断支持或背书。

历史 assessment 不迁移、不回填。没有当时价格的 assessment 保持 untracked；以后出现价格也不能追溯建立 cohort。

## 固定时点结果

Runtime 的既有低成本随访任务会追加计算 15、60、240 分钟结果：

1. 只查本机 `token_snapshots`；
2. 只接受目标时间之后 30 分钟内最早的正价格快照；
3. 从评估时冻结价格计算原始回报、路径最高和最低回报；
4. 截止仍无快照则永久写为 `missing`；
5. 已写结果不可被后来补入的旧时间戳改写。

这些数值不含可成交性、滑点、手续费、税、链费或 MEV，因此不是 Paper PNL，更不是实盘收益。

## 样本与成熟度

Sources 页面按冻结标签和时点展示：tracked cohort、独立 Token 数、日期数、observed/missing、正/非正结果、平均/中位回报和路径区间。重复调查同一 Token 仍保留在审计账本，但统计和成熟度只使用该 Token 时间最早的前向 cohort。

普通标签至少需要 30 个不同 Token 且这 30 个独立样本均有已观察结果、15 个评估日、5 个正结果和 5 个非正结果；精确公众人物实体至少需要 50 个不同 Token 和 20 个评估日。达到门槛只显示 `descriptive_review_available`，仍不会自动生效。

`no_context`、Agent 错误、未核验候选和 missing 都保留，避免只统计成功故事的幸存者偏差。系统不会把人物帖子后的价格变化解释为因果关系或背书。

## 数据表

- `token_context_outcome_cohorts`：评估时冻结的 cohort 与入场快照；
- `token_context_outcome_labels`：安全、有限、不可事后改写的标签；
- `token_context_outcomes`：15/60/240 分钟 observed 或 missing 结果。

Web 的 Token 详情显示单次调查随访；Sources 显示跨样本描述性汇总。两处都固定返回 `decision_eligible=false`、`activation=false`、`affects=none`。
