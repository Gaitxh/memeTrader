# 独立 Agent 正文核验

`agent-fact-verification/v1` 是 Trend Scout 与 Token Context 的第二阶段核验账本。第一阶段只负责发现候选事件和候选来源；候选通过 URL、公网 DNS、HTTP、时间与来源域名门后，第二个全新 Codex 上下文才会打开这些精确 URL，判断正文对明确主张是 `supports`、`contradicts`、`context_only` 还是 `inaccessible`。

## 运行方式

- Trend Scout 每轮把通过本地门的候选一次性批量核验，不按事件逐个启动 Agent。
- Token Context 每个已准入 Token 最多核验一个事件语境。
- 核验阶段不是新定时任务或常驻进程，继续共享现有 `max_concurrent_agents <= 2` 信号量。
- 默认路由为 Terra / medium，失败后回退 Sol / medium；调用和 token 按 `fact_verifier + model + reasoning_effort` 单独记账。
- 只处理上线后新候选，不扫描或回填旧事件、旧 Observation 或旧 Token Context。

## 本地确定性结论

Agent 的自报 verdict 不直接成为最终状态。本机根据逐来源 stance 重新生成：

- 两个或以上不同域名支持且没有反对：`cross_source_supported`；
- 同时出现支持与反对：`conflicted`；
- 只有反对：`contradicted`；
- 其余：`insufficient`；
- 禁用、额度门、Agent 错误和结构错误分别保留真实终态。

不同域名只表示“不同最终 host 的下界”，转载仍可能共享同一 wire 或原始报道；因此 `cross_source_supported` 也不是绝对事实。社交原帖只能证明该账号发布了该内容，不能自动证明帖子里的底层事实。

## 永久边界

- 所有结果固定 `decision_eligible=false / affects=none`。
- Trend Scout 与 Token Context 生成的 Observation 仍为 `identity/context-only`，不会变成 `feature/confirmation`。
- 核验结果不改变 WAIT/CANDIDATE、安全检查、canonical margin、Paper 仓位、退出或 Live。
- Web 只返回安全的状态、来源 stance、正文依据摘要、模型、推理强度和 token；不返回 prompt、完整 run id、parent run id、subject id、claim hash、Cookie 或登录材料。
- Mainnet Live 仍不可用。

SQLite 使用不可更新、不可删除的 `agent_fact_verifications` 与版本注册表。每个有终态的候选保存来源支持/反对/仅语境计数、不同支持域名下界、模型与 token；进程在写入终态前中断时不会伪造完成记录。
