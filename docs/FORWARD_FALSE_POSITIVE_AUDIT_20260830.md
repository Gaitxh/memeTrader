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

## 验证

新增测试覆盖：

- 推广榜单会存档但不能产生热点分；
- `Coins` 与 `Attention` 被判为通用名称；
- 通用名称不能劫持无关新闻事件；
- `Luce`、`Neiro` 等短而有辨识度的名称仍可进入核验；
- 官方精确 CA 可以让 `Test/TST` 这类通用名称进入后续安全门，而不是被名称过滤器误杀。

这次失败被当作前向实验结果，而不是通过调低门槛或删除亏损样本来掩盖。
