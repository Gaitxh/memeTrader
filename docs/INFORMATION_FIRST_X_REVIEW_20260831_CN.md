# 信息先行与 X 账号候选：2026-08-31 客观审阅

这份记录审阅用户补充的 X 账号、历史 Meme 案例和“信息可能早于价格”的研究方向。它保存的是**待前向验证的假设**，不是账号收益榜、交易建议或现成 alpha。

## 可采纳的结论

- 新闻、人物原帖、社区传播和突发事件有时确实先于明显价格/成交变化；因此事件入口不应只由链上 momentum 启动。
- 同一账号既有强反应案例，也有无反应、反向、删帖、否认或被盗案例。必须保留所有 assignment、空结果、失败和未上涨反例，不能只统计成功故事。
- 交易所上币、当事人原帖和政府/机构公告的权威范围不同。账号只对其自身行为或职责范围具有一手性；高影响力不等于事实正确，也不等于 Token 背书。
- `token_created_before_event`、首个合格信息到市场异动的时间差、同名竞争、独立来源广度和扣除成本后的固定时点结果都值得前向记录，但在样本成熟前不进入仓位或退出公式。

## 必须纠正的主张

- 用户给出的 S+/S/A 级别没有完整前向分母支持，不能写成永久权重。它们只转化为候选目录、角色限制和随机观察实验。
- “事件前已存在的 Token 通常更好”不是已证实规律。历史案例同时包含事件前 Token 和事件后部署 Token；方向关系只能作为 shadow 特征，不能作为硬门。
- “精确语义匹配”不等于 canonical CA。通用名称、后发仿盘、项目方自报、诱导 bot 提及和原作者否认都会产生貌似精确但错误的关系。
- 交易次数不是 unique buyer breadth。当前生产库没有可靠的独立买家、资金来源聚类或 holder 历史；相关字段必须显示 `unknown/not_available`，不能填零或用 buys 次数冒充。
- “异常社交注意力预测收益”的论文证据是日频相关性研究，不足以证明秒级 Meme 微盘策略在滑点、费用、MEV 和 rug 后盈利，更不是因果保证。
- ILG、attention acceleration、memeability 和乘法评分公式目前是研究草案；没有预注册量纲、阈值和前向验证，不得直接接入交易。

## 账号处理

目录新增的是有限候选，不继承用户给出的等级：

- 官方交易所/机构入口用于发现或确认其自身公告；官网公告和精确 CA 仍须交叉核验。Coinbase 2025 年已把上市信息迁移到 `@CoinbaseMarkets`，所以不启用旧 `@CoinbaseAssets`。Upbit 韩国和新加坡账号分别保存为 `@Official_Upbit` 与 `@UpbitGlobal`，不混用区域语义。
- `@elonmusk`、`@cz_binance`、`@WhiteHouse`、`@TheRoaringKitty` 等只作为高影响稀疏事件候选；普通帖、重复梗和人物关联不能直接买入。
- `@truth_terminal`、`@aixbt_agent` 和 Crypto KOL 只能证明发现或圈内传播，不能作为独立事实确认。
- 项目方、发行方和持仓利益相关账号默认是 `identity/promotion`。Portnoy、Milei、MELANIA、Iggy Azalea、Andrew Tate 等还需突出操纵、利益冲突、否认和快速回吐风险，不能贡献正向 source authority。
- 原作者/当事人的否认、版权声明或账号失窃确认应成为负面验证线索；但“账号被盗”只能由跨渠道事实或人工隔离确认，不能让 LLM 自行猜测。

## 已做的安全修正

- 语义 Agent 仍可重排和解释接近候选，但不能把原始 canonical 分差抬到通过线；原始歧义继续 `WAIT`。
- 事件后才创建的 Token 不再获得“与事件时间接近”的对称奖励。事件前 Token 仅保留一个有限的描述性接近奖励；这不表示长期旧币必然更优。
- 账号目录新增候选时保留 `feature/confirmation/identity/promotion` 角色，默认不进入 critical，也不提高证据权重。

## 已实现但必须等待前向样本

- `information-first-shadow/v1` 已上线：在最终决策后按事件与 Token 首写冻结，保留信号时点基线缺失的分母，并做 15/60/240 分钟不可回填随访。它只提供描述性市场活动分层，`affects=none`。详细规则见 [Information-first Shadow 前向研究](INFORMATION_FIRST_SHADOW_CN.md)。
- `information-first-ilg/v1` 已预注册：只对上线后的新 cohort 计算“首次本机耐久记录的同交易对活动越界”上界；使用 5 分钟成交量/成交笔数，不把混合 market cap/FDV 的字段冒充活动，旧快照与旧 cohort 均排除。

## 尚未实现、需要前向数据能力的部分

- 真正的 ILG：首个合格信息本机入库时间到预注册市场阈值首次越界的时间差。
- attention 历史、速度与加速度；当前只有累计 attention 单值。
- 追加式 event-token 关系类型、canonical CA 独立核验状态和账号 compromise/quarantine 时间窗。
- 资金聚类后的独立买家、持仓集中度、开发者集群和不可篡改图像相似度。

这些缺口不妨碍继续运行现有 Paper，但它们说明系统现在只能说“具备部分信息先行入口”，不能宣称已经学会在市场定价前稳定获利。

## 主要核验入口

- [Coinbase 上市公告账号迁移](https://www.coinbase.com/blog/coinbase-markets-on-x-your-new-home-for-all-listings)
- [Robinhood 官方社交账号](https://robinhood.com/us/en/support/articles/robinhood-social-media/)
- [Upbit 官方 SNS 清单](https://support.upbit.com/hc/ko/articles/49617343307289-%EC%97%85%EB%B9%84%ED%8A%B8-%EA%B3%B5%EC%8B%9D-SNS-%EC%95%88%EB%82%B4)
- [JBF 论文：Investor attention and cryptocurrency returns](https://www.sciencedirect.com/science/article/pii/S0378426625001384)
- [CZ/TST 案例](https://www.theblock.co/news/business/2025-02-06-bnb-chain-test-memecoin-tst-surged-cz-339228)
- [Musk/DOGE 无反应反例](https://www.coindesk.com/markets/2026/02/03/attention-dogecoin-bulls-musk-says-spacex-may-put-doge-on-the-moon-next-year)
- [Robinhood 2024-11-13 上币公告](https://robinhood.com/us/en/newsroom/robinhood-crypto-expands-offering-with-solana-sol-pepe-pepe-cardano-ada-amp-xrp-xrp-for-u-s-customers/)
- [Milei/LIBRA 调查](https://apnews.com/article/3f572a5f294d7c25437a08151798b917)
