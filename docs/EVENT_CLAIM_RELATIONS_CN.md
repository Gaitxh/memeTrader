# 事件主张目标与关系图

`event-claim-relation/v1` 为来源条目版本增加一个只观察、只前向的关系层，用来回答：

> 本机刚刚看到的这个版本，明确取代、纠正或撤回了哪一个此前版本？

它不回答“哪一方事实上正确”，也不会改变事件 attention、证据角色、`WAIT / CANDIDATE`、Paper 仓位或退出。

## 数据模型

- `source_item_revisions` 继续作为图节点，不复制标题、正文或版本内容。
- `event_claim_relation_registrations` 固定版本、注册时间与不回填边界。
- `event_claim_relations` 保存不可变关系断言；UPDATE 和 DELETE 均由 SQLite trigger 拒绝。
- 每条关系固定 `decision_eligible=false`、`affects=none`。

关系类型严格分开：

| 类型 | 含义 | 不代表 |
|---|---|---|
| `supersedes` | 同一稳定来源条目出现了新的版本 | 新版本事实正确 |
| `corrects` | 发布者明确标记当前版本为纠正 | 被纠正目标必然为假 |
| `retracts` | 发布者明确标记当前版本为撤回 | 原说法已经被独立核验为假 |

普通删除、访问失败、列表缺项、404、DOM 消失和未验证状态不会生成 `corrects` 或 `retracts`。删除版本仍可形成同一条目的版本顺序，但语义保持为 deletion，而不是 retraction。

## 原子前向记录

关系只在本次真实抓取确实新增 `source_item_revisions` 行时记录，并与该 revision 位于同一个 Store 锁和 SQLite 事务内。重复抓取没有新 revision，也不会查询“最新版本”后补建关系。

注册前的 observation/revision 不扫描、不回填。注册后新观察到的纠正可以指向此前已经存在的版本；这是当前纠正动作的前向证据，不是把过去的关系回填成当时已知。

## 目标解析

同一稳定条目默认只指向其直接前一版本。跨条目关系只接受采集器明确提供的 `claim_target_url`：

1. URL 先经过项目既有安全规范化；凭据和敏感 query 被移除；
2. 原始 target URL 不进入 observation、关系表或 Web API；关系表只保留安全 URL 指纹；
3. 只匹配当前关系记录时点之前已经本机观察到的完整安全 URL；
4. 按不同 `source_item_key` 计算匹配数；恰好一个稳定条目才解析；
5. 0 个为 `target_not_found`，多个为 `ambiguous_target`，均不建 resolved edge；
6. 后来目标出现时不得修改旧断言或事后补链，必须等待新的真实来源版本。

## 时间边界

以下情况会保留审计行，但关系为 `excluded_temporal`，且没有有效 target edge：

- observation 或 ingestion 时间晚于本机记录时间；
- observation 晚于 ingestion；
- 来源报告的修订时间无效或位于未来；
- 来源发布时间位于未来；
- Runtime 已标记为 `stale_first_observation` 或 `published_time_in_future`。

## Web 展示

事件详情页的“主张目标与关系图 / Claim targets & relation graph”显示：

- 前向节点数；
- resolved、unresolved 和时间排除数；
- supersede、correct、retract 数量；
- 每条关系的来源版本、目标版本、关系范围、解析状态、依据与本机记录时间。

事件列表只返回汇总；详情才返回有界节点摘要和关系。内部 source key、edge fingerprint、target URL fingerprint、原始 JSON 与敏感 query 均不返回。

## 当前研究状态

本功能完成的是工程记录层，不是事实核验成熟：

- `factual_verification_state = not_verified_by_relation_graph`
- `propagation_state = locally_observed_source_actions_only`
- `affects = none`

下一层仍需在既有 Trend Scout 和 Token Context 调用内部加入独立 verifier phase，并另外前向研究纠正/撤回前后的市场反应。关系图在这些样本成熟前不得进入交易策略。

## AGENT-003 临时复查影子层

`agent-shadow-review-trigger/v1` 从自身注册点以后，把新 `corrects / retracts` 关系作为“本应复查”的只观察输入：

- input 与 claim relation 在同一 SQLite 事务写入；处理未完成时保留 pending，后续 ingest 可补偿处理；
- 每个输入终结为 `shadow_triggered`、`coverage_gap` 或 `ineligible`；无 Token 绑定、映射歧义、缺少注册后 Token cohort、时间排除和 unresolved target 均保留在分母；
- 若触发时存在 Paper 持仓，只冻结触发时点以前的不可变 BUY trade 引用和净数量，不提高证据权重；
- 数据库强制 `dispatch_count=0`、`decision_eligible=0`、`affects=none`，不会写 Agent admission/queued/dispatch，也不会影响候选、仓位或退出；
- Audit 页显示动态中英汇总。样本成熟门达到前，真实复查 Agent 仍禁止派发。
