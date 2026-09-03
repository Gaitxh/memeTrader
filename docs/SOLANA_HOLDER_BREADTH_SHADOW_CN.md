# Solana 持有人宽度前向 Shadow

`solana-holder-breadth-shadow/v1` 是 CHAIN-001 的低频数据可用性实验，不是交易信号。

## 研究问题

现有 `buys/sells/tx` 不能回答独立买家、持有人变化或地址集中度。该 Shadow 先验证：个人电脑能否在不引入索引器和不保存钱包地址的前提下，稳定取得一组可审计的聚合链上快照。

## 冻结设计

- 只纳入本版本注册后新出现的 Solana token-universe cohort；历史 Token 和用户提供的赢家样本不回填。
- 用 `SHA256(version + token_id)` 做固定 2/1000 抽样，时点为发现后 0、15、60、240 分钟。
- Runtime 每 5 分钟最多处理一个到期时点；不增加 Agent、线程或交易入口。
- 先以 `getAccountInfo` 确认 SPL Token / Token-2022 program，再读取 `getTokenSupply` 和带 mint filter、`dataSlice` 的 `getProgramAccounts`。
- Store 只保存：Token 账户数、正余额账户数、正余额 owner 数、余额覆盖、Top1/Top10 供应占比、低于总供应 1bp 的 owner 数/比例、slot、请求数、延迟和响应字节数。
- owner 地址只在单次内存聚合中存在，不写入 SQLite、API、日志或 Web。
- 结果表不可更新/删除，固定 `decision_eligible=false / affects=none`。

## 必须如何解释

这里的 holder 定义是“确认时点拥有正余额 Token 账户的不同 owner 字节”。它不等于：

- 真人或独立钱包；
- 独立买家或新买家；
- 聪明钱、内部人或社区成员；
- 自然形成的持有人。

池子、托管账户、机器人、尘埃空投和女巫地址都会改变计数。小样本可用性探测中，一个 5 分钟成交量仅约 173 美元的 Token 仍有约 3,014 个正余额 owner；因此 owner 数不能未经验证直接放大仓位或触发买入。

## 公共端点边界

Solana 官方公共 RPC 有速率限制，官方文档也说明其不适合生产级高流量应用。本实验采用极低抽样和有界调度；429、传输错误、mint 缺失与不支持的 program 都作为真实终态保留，不为得到非空结果而重试或删除。

参考：

- [公共 RPC 端点与限制](https://solana.com/docs/references/clusters)
- [`getProgramAccounts`](https://solana.com/docs/rpc/http/getprogramaccounts)
- [`getTokenSupply`](https://solana.com/docs/rpc/http/gettokensupply)

## 升级门

本层首先只回答可用性、成本和污染程度。若未来要研究 unique buyer、new holder、资金来源 cluster 或 smart money，必须另行预注册数据定义、地址/隐私边界、交易级去重、前向 outcome 和成熟门；现有聚合结果不得被重新解释为这些能力已经实现。
