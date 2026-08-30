# Forward Paper 误触发审计 — 2026-08-30

## 结论

`data/memetrader_forward_20260830_r5.sqlite3` **不得进入策略收益统计**。该库保留为失败证据，不删除、不回写、不美化。

## 发现的问题

前向 Paper 运行曾把 Google News 中的推广型榜单文章聚合成事件，例如：

- `Top Altcoin News: 7 Meme Coins Enter the 2026 Spotlight...`
- `Top 100x Cryptos Before the Next Breakout...`
- 含 `presale`、`coins to watch`、`price prediction` 等表达的内容。

随后，普通词语被错误当成事件实体：

- `Coins` Token 被匹配到文章里的通用单词 `coins`；
- `Attention` Token 被匹配到文章里的通用单词 `attention`。

因此形成了两次无效的 Paper 入场。即使其中一次模拟交易最终盈利，也不能证明信号有效；它仍是错误的事件—Token 关系。

## 已实施修正

1. 推广榜单、Presale、价格预测、Top/Best coins、100x、coins to buy/watch 等内容被标为 `promotion`。
2. `promotion` 记录仍保存在证据库，但热点分为 0，不能触发候选与买入。
3. `Coins`、`Attention`、`Market`、`Hype`、`Spotlight` 等通用 Token 名称不能仅靠文字重合进入候选。
4. 通用短名称只有在以下任一条件满足时才可继续：
   - 官方或可信来源给出精确 CA；
   - Token Context Agent 已用至少两个独立、近期、可访问来源核验并绑定该 Token。
5. 通用 `google-news-memecoin` 榜单源在设备配置中默认关闭；Token→事件反查和主动 Agent 搜索仍保留。
6. 新的干净前向数据库为 `data/memetrader_forward_20260830_r6.sqlite3`。
7. BSC Honeypot 模拟和 Solana RugCheck 报告改为 Paper 默认必需；外部结论缺失时拒绝入场。
8. Agent 搜索增加每日 token 预算预留、强制调用不得越过预算、Token 搜索失败仅短退避而不是锁死完整冷却期。

## 验证

新增测试覆盖：

- 推广榜单会存档但不能产生热点分；
- `Coins` 与 `Attention` 被判为通用名称；
- 通用名称不能劫持无关新闻事件；
- `Neiro` 等五字母名称仍可直接进入名称核验；`Luce`、`Musk` 等四字母名称只能进入 Agent 搜证，不能仅凭文本重合直接绑定；
- 官方精确 CA 可以让 `Test/TST` 这类通用名称进入后续安全门，而不是被名称过滤器误杀。

这次失败被当作前向实验结果，而不是通过调低门槛或删除亏损样本来掩盖。

## r6 后续实机发现：过期反查证据形成“幽灵热点”

r6 没有产生新交易，但发现一条 `Starlink` Token-first 事件：Token 刚创建，Google News 反查找到了两篇独立报道；然而机器人第一次看到报道时，它们分别已经发布约 37 分钟和 61 分钟，超过 30 分钟入场时效门。

旧逻辑一方面在候选阶段正确拒绝这些过期证据，另一方面又让 `confirmation` 记录把事件注意力抬到 37，导致该事件在后台重复尝试 15 次。0.6.3 修正为：

1. 首次看到时已超龄的 `feature` 或 `confirmation` 一律降级为 `identity`，原始角色保存在 `raw.original_role`；
2. `identity` 资料继续保存，用于解释 Token 名称和事件关系，但注意力为 0，不能单独触发交易；
3. 对数据库中已经存在、但当前没有任何合格外部证据的高分事件，不再每几分钟调用 DEX/API；直接延后至活动窗口结束；
4. 任何新观察到的合格证据都会清除延迟并立即恢复判断。

实机验证中，`event 360` 的尝试次数稳定在 15，下一检查时间被推迟到 `2026-08-30T12:00:36.720831Z`，同时 r6 仍为 0 决策、0 仓位、0 成交。
