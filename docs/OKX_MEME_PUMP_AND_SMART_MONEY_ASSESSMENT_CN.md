# OKX Meme Pump 与“聪明钱”来源评估

更新时间：2026-08-31。

## 结论

OKX Web3 Meme Pump 对 memeTrader 有潜在的**补充研究价值**，但当前不直接接入。公开产品页不是稳定、匿名、许可清晰的数据接口；官方 Meme Pump 详情能力需要签名凭据，费用表将核心接口列为 Premium。项目不得逆向依赖网页内部请求、绕过登录或访问控制。

现有 `PumpPortal + DexScreener + GeckoTerminal` 继续承担免费基础发现：PumpPortal 提供 Pump.fun 新币/迁移实时订阅，DexScreener 提供 pair/profile/CTO/boost/链接与批量报价，GeckoTerminal 提供跨 DEX 新池补充。OKX 的独特价值主要是 launchpad 阶段、开发者历史、bundler、creator、社交字段和同车钱包标签，不是替代现有发现链。

官方依据：

- [OKX Meme Pump 产品页](https://web3.okx.com/zh-hans/meme-pump)
- [OKX OnchainOS Skills 官方仓库](https://github.com/okx/onchainos-skills)
- [Meme Pump Token List](https://web3.okx.com/zh-hans/onchainos/dev-docs/market/market-memepump-get-token-list)
- [Token Details](https://web3.okx.com/zh-hans/onchainos/dev-docs/market/market-memepump-get-token-details)
- [Developer Info](https://web3.okx.com/zh-hans/onchainos/dev-docs/market/market-memepump-get-token-developer-info)
- [Bundle Details](https://web3.okx.com/zh-hans/onchainos/dev-docs/market/market-memepump-get-token-bundle-details)
- [Aped Wallet Details](https://web3.okx.com/zh-hans/onchainos/dev-docs/market/market-memepump-get-token-aped-wallet-details)
- [OKX Market API Fee](https://web3.okx.com/tr/onchainos/dev-docs/market/market-api-fee)
- [PumpPortal 实时数据](https://pumpportal.fun/data-api/real-time/) 与 [费用说明](https://pumpportal.fun/fees/)

## 若未来明确授权接入

只有在用户明确提供独立的 OKX API 凭据、确认费用/配额和适用条款后，才增加默认关闭的只读适配器；凭据只保存在本机 secret 存储，不进入网页 API、日志、SQLite、Git 或 Agent prompt。第一阶段仅低频调用官方 `tokenList` / `tokenDetails`，不先接全量 WebSocket、开发者、bundle 和同车钱包接口。

OKX 返回的 X、Telegram、网站和项目描述必须写为 `provider_metadata`，角色只能是 `identity` 或 `promotion`，默认 `decision_eligible=false`。它们可以触发后续本机访问和独立来源核验，但不能自行证明社区热度、名人背书或真实新闻关联。

## “聪明钱”只能怎样使用

`SMART_MONEY`、`INFLUENCER`、PnL 或同车钱包标签存在定义不透明、地址聚类误差、幸存者偏差、事后信息、机器人/做市/自交易和拥挤复制等问题。地址买入不等于真实社区认可，也不构成因果预测。

若未来接入，只冻结决策时已经观察到的计数、持仓比例区间、bundle/bot/dev 字段和 provider 标签，进入 `context_only` 与 shadow 分层；不得回填后来 PnL、最终持仓或成功标签。任何结果都不能直接改变 WAIT/CANDIDATE、canonical ranking、安全门、仓位、退出或 Live。只有跨 Token、跨日期并用独立链上数据验证后的前向描述性结果，才可供人工判断是否值得继续观察。
