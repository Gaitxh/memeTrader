# Telegram 信息源、搜索机器人与采集方案调研

调研日期：2026-08-30（Asia/Shanghai）
适用项目：memeTrader / GXH coin
状态：研究结论，不代表已安装、已登录或已自动接入任何 Telegram 来源

## 1. 结论摘要

Telegram 对 Crypto、Solana 和 Meme 社区确实有价值，但对 memeTrader 最合适的定位是**人工发现目录和原始链接入口**，不是默认自动抓取平台。

技术上，公开广播频道通常可以通过 `https://t.me/s/<handle>` 在不登录、没有 API Key 的情况下查看最近帖子，RSSHub、RSS-Bridge 等项目也能把这类页面转换成 RSS；但截至本次调研，Telegram 当前官方条款明确限制 scraping、indexing、harvesting、aggregation，并特别限制将 Telegram 内容用于 AI/ML 产品。把频道帖子自动抓取、长期保存并交给 ChatGPT Agent 做热点判断，存在实质性的服务条款、版权和账号风险，不能因为页面公开或某个开源项目能够抓取就视为已获授权。

因此，推荐基线是：

1. 在 Sources 页面保存经过官网核验的 Telegram 频道目录、handle、角色、语言、访问方式和原始链接。
2. 用户点击后在浏览器或 Telegram 客户端人工查看。
3. 自动采集优先转向同一发布者自己的官方网站、RSS/Atom、GitHub Release、状态页、公开 Bluesky 页面或其他明确允许机器读取的 feed。
4. 发布者自己在 Telegram 之外提供的机器 feed 可按该 feed 自身条款评估；发布者对频道的单方许可不足以解除 Telegram 平台条款。除非 Telegram/独立法律审查确认具体用途可行，并取得所有相关作者逐一、持续、可撤销且覆盖保存、展示、自动分析和 AI/ML 的同意，否则不直接自动摄取 Telegram 内容。
5. Telegram 搜索/统计机器人只用于发现；机器人返回结果不能直接成为独立权威证据，必须回到原始帖子、外部原文或链上交易。

## 2. Telegram 官方条款边界

以下页面均于 **2026-08-30** 访问。页面没有稳定展示可用于本报告的统一发布日期，因此本报告记录访问日期；上线前和定期运行中应重新核对最新版本。

| 官方页面 | 本次调研确认的关键点 |
|---|---|
| [Terms of Service for Content Licensing](https://telegram.org/tos/content-licensing) | Telegram 公共/私有聊天内容的普通合法使用不等于获得抓取和再利用许可；条款明确限制 scraping、indexing、harvesting、aggregation，并特别限制将平台数据用于训练、微调、验证、增强、基准测试或部署 AI/ML 产品。条款描述了在所有相关用户明确、知情、主动、持续且限于具体上下文同意时才可能存在例外。 |
| [Telegram Bot Platform Developer Terms](https://telegram.org/tos/bot-developers) | 第 4.3 节限制机器人收集超出服务必要范围的数据，并明确把抓取公共群组或频道、建立大型数据集或 AI 产品列为禁止用途；API ID、hash、token 等凭据必须保密。 |
| [Telegram API Terms of Service](https://core.telegram.org/api/terms) | 第三方客户端必须保护隐私、取得自己的 API ID、遵守 Content Licensing / AI Scraping 条款；Telegram 可终止违规 API 访问。 |
| [Creating your Telegram Application](https://core.telegram.org/api/obtaining_api_id) | MTProto 需要官方 Telegram 账号、`my.telegram.org` 的 `api_id`/`api_hash`；当前每个手机号只能关联一个 API ID；非官方客户端会被监控，flooding、spam、伪造浏览或订阅可能导致永久封禁。 |
| [Telegram Privacy Policy](https://telegram.org/privacy) | 用户给机器人发消息、使用 inline bot、按机器人按钮或加入有机器人的群时，会把数据交给第三方运营者；机器人可收到公开账号资料和用户发出的消息/查询，其控制的外部链接还可能获取 IP。 |
| [Bots FAQ](https://core.telegram.org/bots/faq) | Bot API 只让机器人接收与其私聊、其已成为成员的频道，以及权限允许的群消息；一个普通 bot token 不能任意读取全网公共频道。 |

### 2.1 允许、风险和默认禁止三档

#### 允许作为默认行为

- 保存官方频道 handle、`t.me` 链接、官网验证入口、语言、角色和最后人工核验时间。
- 用户点击链接，在浏览器或官方 Telegram 客户端人工查看公共频道。
- 自动读取发布者自己的官网、RSS/Atom、GitHub Release、状态页和明确允许机器访问的公开 feed。
- 使用浏览器人工打开帖子，把帖子所指向的官方外部原文、监管公告或链上交易交给现有验证流程。
- 对非敏感公开主题人工使用搜索/统计机器人，并把结果严格标记为 `discovery-only`。

#### 需要单独审查、授权或明确风险提示

- 定时读取 `t.me/s/<handle>`、RSSHub、RSS-Bridge、Telegram2RSS 或第三方 Telegram 索引站。
- 使用 Telethon、TDLib 等 MTProto 客户端读取账号已加入的频道或群。
- 长期保存全文、媒体、评论、成员资料、反应或完整频道历史。
- 把 Telegram 内容翻译、摘要、向量化、索引或交给 Agent 推理。
- 使用 TGStat、TG.ME、Junction Bot 等第三方服务：它们会看到查询或订阅列表，且其采集方式、保存期限和内容许可需要独立审查。
- 即使频道发布者表示授权，也只能进入独立法律/平台条款评审，不能直接解锁；需要确认 Telegram 对该具体用途的约束，并取得所有相关作者逐一、持续、可撤销的有效同意。转发、评论、群聊和第三方投稿不能由频道所有者代为许可。

#### 默认禁止

- 批量抓取、镜像、索引或永久存档未经授权的公共/私有 Telegram 内容。
- 把未经许可的 Telegram 内容直接用于 ChatGPT Agent、模型训练、RAG、自动摘要或交易判断。
- 使用用户密码、Cookie、验证码、2FA、Telegram session string、API hash 或 bot token 作为普通网页设置项，或写入 SQLite、日志、Git、公开 URL。
- 自动加入群、批量搜索、刷浏览量、刷反应、转发、发帖、关注或规避验证码/限流。
- 向任何机器人发送私钥、钱包恢复词、交易签名、内部策略、未公开监控词、敏感 CA 清单或账号验证码。
- 把喊单、trending、volumize、sniper 或钱包连接机器人当成可交易信号。

## 3. 证据角色和排序原则

Telegram 来源应和其他平台使用同一证据模型：

| 等级 | 类型 | 可承担角色 |
|---|---|---|
| A | 协议、交易所、项目自己的官网核验频道 | 只能证明该主体自己发布的公告、升级、维护或上币；具体帖子仍需区分 `feature`、`identity` 和 `promotion`。 |
| B | 有编辑责任的成熟媒体 | 可作为二级 `confirmation`；最终仍应保存媒体原文和其引用的一手来源。 |
| C | 专业链上分析、生态媒体、快讯聚合 | `discovery-only` 或弱确认；链上主张必须回到区块浏览器。 |
| D | 社区、喊单、搜索机器人、trending 机器人 | 仅线索；永远不能单独触发候选或买入。 |

来源排序应为：**权威性 → 是否独立 → 是否有原始链接 → 新鲜度 → 可见传播热度**。订阅量、浏览量和反应数反映传播，不证明真实性。同一篇文章被十个频道转发仍只能算一个独立来源。

## 4. 官方 Crypto、Solana、交易所和协议入口

订阅量会持续变化；表中的数量只在必要时标为“调研时约”，不能作为永久事实或权威依据。

| 入口 | 类型与访问现实 | 可贡献内容 | 角色、风险和建议 |
|---|---|---|---|
| [@solana](https://t.me/solana) | 当前 [Solana Community](https://solana.com/community) 明确链接的 Telegram 入口，调研时官网显示约 7 万成员；`/s/solana` 重定向为联系页面，查看内容需要 Telegram 账号 | Solana 官方公告和社区信息 | A，但无无登录公开帖子流。仅保存目录并人工打开；自动信息改读 Solana 官网新闻。历史 `@solanaannouncements` 已不在当前官网入口且帖子陈旧，默认禁用。 |
| [@raydium](https://t.me/raydium) / [公开预览](https://t.me/s/raydium) | Raydium Official Announcements；调研时约 4.2K 订阅 | 产品更新、维护、协议升级、安全提醒 | A；只确认 Raydium 自身动作。帖子中的营销、奖励和活动标 `promotion`。优先跟随 `raydium.io`、官方文档、GitHub 或链上状态。 |
| [@raydiumprotocol](https://t.me/raydiumprotocol) | Raydium 讨论群；完整消息需账号 | 用户反馈、社区叙事和故障线索 | C/discovery-only；群消息噪声和诈骗风险高，不进自动决策。 |
| [@jup_dev](https://t.me/jup_dev) / [公开预览](https://t.me/s/jup_dev) | Jupiter Dev Notifications；调研时约 2.4K 订阅，并链接 Jupiter 官方开发文档 | API 破坏性变更、维护、宕机、Pump.fun 路由和集成安全事项 | A/operational confirmation；对 memeTrader 后端很有价值，但自动化应优先跟随 `developers.jup.ag` 和 GitHub。 |
| [@pump_tech_updates](https://t.me/pump_tech_updates) / [公开预览](https://t.me/s/pump_tech_updates) | Pump Developer Updates；Pump 官网直接链接；调研时约 6.7K 订阅 | Pump 程序、IDL、SDK、费用、Token-2022 和破坏性集成变化 | A/operational confirmation；最终依据优先使用 [pump-public-docs](https://github.com/pump-fun/pump-public-docs)、链上程序和官方 SDK。 |
| [@pumpfun](https://t.me/pumpfun) / [公开预览](https://t.me/s/pumpfun) | Pump.fun 品牌频道；调研时约 43K 订阅 | 官方品牌语境、平台文化和社区人物 | A 身份，但大量帖子属于 `identity/promotion`；bullish 文案、社区欢迎和 Meme 口号不能形成买入信号。 |
| [@binance_announcements](https://t.me/binance_announcements) / [公开预览](https://t.me/s/binance_announcements) | Binance 已验证公告频道；调研时约 355 万订阅 | 上币、交易对、维护、暂停充提 | A/feature；必须保存同帖链接的 Binance 官方公告，促销和比赛不算独立确认。 |
| [@Bybit_Announcements](https://t.me/Bybit_Announcements) / [公开预览](https://t.me/s/Bybit_Announcements) | Bybit 已验证公告频道；调研时约 42 万订阅 | 上币、维护、产品变化 | A；交易比赛、返利和推广标 `promotion`。 |
| [@OKXAnnouncements](https://t.me/OKXAnnouncements) / [公开预览](https://t.me/s/OKXAnnouncements) | OKX 已验证公告频道；调研时约 79 万订阅，并链接 OKX 官方验证页 | 上币、钱包、DEX、维护 | A；只把 `okx.com` / `web3.okx.com` 原文作为最终可复核来源。 |
| [@Kucoin_News](https://t.me/Kucoin_News) / [公开预览](https://t.me/s/Kucoin_News) | KuCoin 官方新闻频道 | 上币和服务变化 | A；需落回 KuCoin 官方公告。 |
| [@kraken_announcements](https://t.me/kraken_announcements) / [公开预览](https://t.me/s/kraken_announcements) | Kraken 官方社媒入口关联的公告频道；调研时规模较小 | 新资产、网络支持和产品变化 | A；以 `blog.kraken.com` 原文为最终确认。不能因订阅量小就自动降为假冒，也不能只凭名称认定官方。 |
| [@CoinbaseItaliaOfficial](https://t.me/CoinbaseItaliaOfficial) | Coinbase 明确认可的意大利例外频道 | 意大利区域信息 | 非当前重点。[Coinbase Help](https://help.coinbase.com/en-gb/coinbase/privacy-and-security/avoid-scams/telegram-scams) 明确表示除此之外 Coinbase 没有 WhatsApp/Telegram 官方存在，其他英文“Coinbase 官方 Telegram”进入诈骗阻止名单。 |

身份验证应优先采用“项目官网或官方帮助中心 → 精确 `t.me` handle”的双向路径。Telegram 名称、头像、蓝勾或订阅量都不能单独证明身份。例如调研发现 `@Raydiumx` 外观和订阅量都可能迷惑用户，但未被 Raydium 官方入口核验，应排除。

## 5. 成熟新闻媒体频道

这些频道在调研时均有公开预览，但公开可读不等于允许自动抓取或交给 Agent。

| 入口 | 可贡献内容 | 角色、风险和建议 |
|---|---|---|
| [@CoinDeskGlobal](https://t.me/CoinDeskGlobal) / [预览](https://t.me/s/CoinDeskGlobal) | 加密行业新闻和快讯 | B/confirmation；保存 CoinDesk 原文，不只保存 Telegram 摘要。 |
| [@cointelegraph](https://t.me/cointelegraph) / [预览](https://t.me/s/cointelegraph) | 全球加密新闻 | B；标题传播快，必须打开文章并核验一手引用。 |
| [@the_block_crypto](https://t.me/the_block_crypto) / [预览](https://t.me/s/the_block_crypto) | 监管、交易所、融资和行业新闻 | B；注意付费墙、转载和重复文章。 |
| [@decryptnews](https://t.me/decryptnews) / [预览](https://t.me/s/decryptnews) | 加密、文化、游戏和 AI | B。 |
| [@bloomberg](https://t.me/bloomberg) / [预览](https://t.me/s/bloomberg) | 宏观、政治和金融背景 | B，高权威宏观确认，但不是 Meme 专线。 |
| [@wublockchainenglish](https://t.me/wublockchainenglish) / [预览](https://t.me/s/wublockchainenglish) | 亚洲加密、交易所和监管；频道自称唯一英文官方账号；调研时约 24.5 万订阅 | B；适合英文和亚洲时区覆盖。 |
| [@wublock](https://t.me/wublock) | 吴说中文唯一官方频道 | B；适合中文界面，仍需跟随其原文或一手来源。 |
| [@foresightnews](https://t.me/foresightnews) / [预览](https://t.me/s/foresightnews) | 中文 Web3 快讯，通常链接 Foresight News 原文；调研时约 1.9 万订阅 | B；适合中文信息层。 |

没有确认到 Reuters 的官方公共 Telegram。`@reutersworldchannel` 的页面明确声明不是 Reuters 官方；检索到的 Financial Times 相似频道也有非官方标识，应排除而不是猜测。

## 6. 社区、链上分析和趋势频道

以下来源全部为 `discovery-only`。它们适合找到“发生了什么”或“社区正在谈什么”，不能证明某个 Token 是正确映射或值得买入。

| 入口 | 用途 | 风险和建议 |
|---|---|---|
| [@lookonchain](https://t.me/lookonchain) | 鲸鱼、聪明钱和链上叙事 | 每笔交易必须回到区块浏览器；地址归属和行为解释可能错误。 |
| [@whale_alert_io](https://t.me/whale_alert_io) | 大额转账线索 | 转账不等于买入、卖出或新闻事件。 |
| [@WatcherGuru](https://t.me/WatcherGuru) / [预览](https://t.me/s/WatcherGuru) | 高速宏观和加密标题 | 快但常缺上下文，必须找原始来源。 |
| [@TreeNewsFeed](https://t.me/TreeNewsFeed) / [预览](https://t.me/s/TreeNewsFeed) | 高频新闻终端式标题 | 标有 BBG/RTRS/WSJ 不代表已提供可复核原文；无链接时只作线索。 |
| [@unfolded](https://t.me/unfolded) / [预览](https://t.me/s/unfolded) | 图表和市场洞察 | 分析、图表选择和 AI 评论不是事实确认。 |
| [@DegenerateNews](https://t.me/DegenerateNews) / [预览](https://t.me/s/DegenerateNews) | Meme 原生文化和突发舆论 | C/D；适合热点发现，不进入确定性证据。 |
| [@solananewshub](https://t.me/solananewshub) / [预览](https://t.me/s/solananewshub) | Solana 生态新闻，页面称由 Solflare 支持，常链接原始 X 帖 | C；不是 Solana Foundation 官方。 |
| [@PumpFunNewPools](https://t.me/PumpFunNewPools) / [预览](https://t.me/s/PumpFunNewPools) | 第三方新池转发 | 默认禁用；与 PumpPortal 重复，噪声、推广和操纵风险高。 |
| [@birdeye_alert_bot](https://t.me/birdeye_alert_bot) | Birdeye 官方文档列出的提醒投递机器人；需要用户在 Birdeye 先配置价格、成交量等条件 | C/discovery-only；它是通知通道，不是独立来源，不提供全网新币语境核验，也不应连接 memeTrader 钱包。 |
| [Birdeye 文档列出的 Telegram New Pairs bot](https://docs.birdeye.so/docs/birdeye-bots) | Birdeye 合作方 Waterfall 提供的新交易对提醒 | D/discovery-only；属于合作方而非 Birdeye 自有机器人，与 PumpPortal/DexScreener/GeckoTerminal 直接链上发现重复，默认不加入自动链路。 |
| [@solana_dailyann](https://t.me/solana_dailyann) | Solana 社区和项目推广 | 默认禁用；历史内容包含营销套餐、Giveaway 和付费曝光，独立性弱。 |

不要默认接入任何带 `caller`、`100x`、`sniper`、`trending volume`、`volumize` 或钱包连接功能的频道/机器人。运营者可能持仓、收广告费或直接制造成交量。

## 7. Telegram 搜索、统计和聚合机器人

所有交互机器人都需要 Telegram 账号。给机器人发送查询会向运营者披露至少查询内容、时间和账号公开资料；若使用 inline bot，正在输入的完整查询会发送给机器人。不要假设“只是搜索”就具有匿名性。

| 入口 | 功能 | 隐私、运营和证据建议 |
|---|---|---|
| [@TGStat_Bot](https://t.me/TGStat_Bot) | 查询频道统计、历史和传播指标 | 只供人工评估影响力；统计口径和数据采集方式由 TGStat 控制。 |
| [@SearcheeBot](https://t.me/SearcheeBot) | 按关键词和分类发现频道；TGStat 官方频道推荐 | 只用于发现候选 handle；查询词会披露给运营者。 |
| [@TGAlertsBot](https://t.me/TGAlertsBot) | 关键词/提及监控；TGStat 宣称覆盖大量来源并提供较低延迟 | 第三方付费服务；会知道完整监控词和目标。不要提交内部策略、敏感 CA 或钱包标识；结果必须回到原始帖子。 |
| [@TheFeedReaderBot](https://t.me/TheFeedReaderBot) / [官网](https://elite.thefeedreaderbot.com/) | 把 RSS、X、YouTube、Facebook、TikTok、Instagram 和网页变化投递到 Telegram；官网调研时称刷新约 10–30 分钟 | 它是投递工具，不是权威来源；运营者可看到全部订阅列表和社交账号。memeTrader 已有本地 RSS/浏览器采集，不需要把源清单交给它。 |
| [@junction_bot](https://t.me/junction_bot) / [文档](https://www.junctionbot.io/documentation/forwarding) | 聚合/转发公共频道、按名称搜索、相似频道发现；高级模式可连接用户账号和私密来源 | 不连接 memeTrader 专用账号、不授予管理员、不允许访问私密群或内部策略。查询和来源列表会交给第三方。 |
| [@junction_bot AI Digests](https://www.junctionbot.io/documentation/digests) | 可从多源定时生成摘要，并按关键词、重复、广告或自定义 prompt 过滤 | 功能已由官方文档核验，但免费模式使用第三方默认模型，私有源要求连接个人 Telegram 账号；不使用本机 Codex agentic 额度。仅作人工备用，不进入 memeTrader 自动证据链。 |
| [@theSummaryBot](https://t.me/theSummaryBot) | 人工提交网页、文章或视频后生成摘要/翻译 | 阅读辅助，不是信息源；摘要不能替代原文、发布时间和本机首次观察时间，也不向其提交内部策略或敏感链接。 |
| [@pumptrendingofficial_bot](https://t.me/pumptrendingofficial_bot) | Pump.fun 品牌频道链接的 `volumize` / trending 推广工具 | 高操纵和利益冲突风险；禁止连接钱包、禁止作为热度或成交证据。 |
| [TG.ME](https://tg.me/) | 非 Telegram 官方的公共频道搜索、阅读和统计网站；调研时自称无需账号并索引约 1,240 万频道 | 仅人工发现；需单独审查其隐私、条款、数据许可、索引新鲜度和运营者。 |
| [Telegram 原生全局搜索](https://core.telegram.org/api/search) | MTProto `messages.searchGlobal` | 需要登录账号和 API 凭据；查询发送给 Telegram，仍受 API/内容条款和账号限制。 |

机器人返回结果统一执行：

```text
机器人/目录找到线索
        ↓
保存原始 t.me/<handle>/<message_id>
        ↓
找到帖子指向的官网原文 / 监管公告 / 链上交易
        ↓
按本机 observed_at、发布时间、独立实体和来源角色重新验证
        ↓
没有原文或无法验证 → discovery-only / WAIT
```

## 8. GitHub 和自托管方案比较

调研时的 stars、commits 和维护状态只作为当时生态成熟度参考，不应写入运行时权威逻辑。

| 项目 | 技术和凭据 | 调研时维护/许可证 | 结论 |
|---|---|---|---|
| [DIYgod/RSSHub](https://github.com/DIYgod/RSSHub) | `/telegram/channel/:username`；无 session 时解析 `t.me/s`，也可配置 `TELEGRAM_SESSION`、API ID/hash | 活跃；调研时约 45.9K stars、17,491 commits；AGPL-3.0 | Telegram 路由最成熟，可借鉴解析和 feed schema；Node 依赖偏重，网页解析易受 Telegram 改版影响，且默认抓取/AI 使用有条款风险，不直接部署。 |
| [RSS-Bridge/rss-bridge](https://github.com/RSS-Bridge/rss-bridge) | PHP `TelegramBridge` 直接解析 `https://t.me/s/` | 活跃；调研时约 9.1K stars、4,517 commits；Unlicense | 部署较简单但引入 PHP；TelegramBridge 曾因页面/URL 变化故障；同样不解决内容许可。 |
| [akopachov/telegram2rss](https://github.com/akopachov/telegram2rss) | 无账号，把公开频道转 RSS，可部署到 Vercel、Netlify 或 Cloudflare Workers | 小型项目；调研时约 10 stars、70 commits；GPL-3.0 | 低复杂度但总线因子和维护确定性较低；不作为核心依赖。 |
| [izHaman/STC-Reader](https://github.com/izHaman/STC-Reader) | Telethon + GitHub Actions + RSSHub；下载媒体并提交到 GitHub | MIT；调研时大量 commits，但大量变更可能来自自动 feed 更新，采用度极低 | 强烈不采用：永久再发布媒体带来内容许可、版权、隐私、session secret 和 GitHub 仓库膨胀风险。 |
| [Brooksolomon/Telegram-Search-Engine](https://github.com/Brooksolomon/Telegram-Search-Engine) | FastAPI + Telethon + PostgreSQL，可选 Meilisearch/Ollama；需 API ID/hash、手机号和 session | MIT；调研时约 48 stars、42 commits，项目较年轻 | 可借鉴频道关系图、影响力和限流设计；不符合现有 Python+SQLite/低复杂度目标，并扩大索引和 AI 条款风险。 |
| [Telethon](https://github.com/LonamiWebs/Telethon) / [当前维护位置](https://codeberg.org/Lonami/Telethon) | Python MTProto；需要 `api_id`、`api_hash`、手机号、登录验证码、可能的 2FA 和 session | MIT；GitHub 于 2026-02-21 归档并迁到 Codeberg；调研时 GitHub 约 12.1K stars | 如果未来取得内容许可，技术上最贴合 Python；需固定版本、审查 Codeberg 维护状态并把 session 当作登录密钥。当前不接入。 |
| [Pyrogram](https://github.com/pyrogram/pyrogram) | Python MTProto；需要账号凭据 | LGPL-3.0 / GPL-3.0；2024-12-23 归档，README 明确停止维护 | 不用于新系统。 |
| [TDLib](https://github.com/tdlib/td) | Telegram 官方高性能客户端库；需要 API ID/hash；支持 Windows、异步更新和加密本地数据库 | 活跃；调研时约 9.1K stars、17,946 commits；Boost Software License 1.0 | 最可靠但 C++ 构建、绑定和独立本地数据库复杂；个人电脑第一阶段不值得，且不能绕过内容条款。 |
| [ESWZY/telegram-news](https://github.com/ESWZY/telegram-news) | HTML/RSS/JSON → Telegram 频道发布；BotFather token + SQL | MIT；调研时 263 commits | 方向相反，是出站新闻发布器，不是 Telegram 入站采集器；不采用。 |

## 9. 无 API Key、MTProto 和 Bot API 的现实比较

| 方式 | 登录/凭据 | 覆盖和实时性 | 复杂度 | 核心问题 |
|---|---|---|---|---|
| `t.me/s` / RSSHub / RSS-Bridge | 无 | 只覆盖有公开预览的广播频道，通常只暴露最近帖子；群和部分频道不可用 | 低 | HTML 易变、媒体和历史不完整、可能限流；公开不等于获准抓取或用于 AI。 |
| Telethon | API ID/hash、手机号、验证码、可能 2FA、session | 登录账号可见的频道/群和更新流 | 中 | 账号封禁、session 泄露、登录维护和条款风险；GitHub 已迁移。 |
| Pyrogram | 同上 | 类似 Telethon | 中 | 已停止维护。 |
| TDLib | 同上 | 最完整、更新顺序和本地状态更稳 | 高 | C++ 构建、绑定、额外数据库和运行复杂度；仍受条款限制。 |
| Bot API | BotFather token | 仅私聊、bot 所在频道和权限允许的群 | 低到中 | 不能任意发现/读取外部公共频道，不是全网采集方案。 |

如果未来经过 Telegram/独立法律审查并取得所需同意后使用 MTProto，也不应向用户索要 Telegram 密码。用户应只在本机官方登录流程中输入手机号、验证码和 2FA；session 使用 Windows DPAPI 或 Credential Manager 保存，永不进入网页 API、普通 Settings、SQLite、日志、Git 或公开 URL。

## 10. 对 memeTrader 的推荐落地

### 10.1 第一阶段：Telegram 目录，不是 Telegram 爬虫

- `telegram` 平台可以出现在 Sources、Settings 和事件来源卡中，但自动状态默认应为 `manual_directory`，不是 `active_collector`。
- 频道记录至少保存：精确 handle、入口 URL、官方验证 URL、语言、来源类型、authority tier、允许角色、公开预览是否存在、最后核验时间、条款状态和推荐替代 feed。
- 点击“查看原文”直接打开 `t.me` 或帖子 permalink；用户人工查看后，系统只自动处理其指向的官网原文、公开 RSS、GitHub、状态页、监管公告或链上交易。
- 对同一发布者同时存在 Telegram、官网和 X/Bluesky 的情况，Telegram 只作发现和身份上下文；决策证据优先使用允许机器读取且可复核的原始页面。
- 登录失败或没有 Telegram 账号不会阻塞其他采集器。

### 10.2 发布者机器 feed 与 Telegram 内容例外

发布者在 Telegram 之外通过官网明确提供 RSS/Atom/JSON、GitHub Release、Webhook、邮件订阅或其他机器可用 feed 时，可按该 feed 自身条款进入自动接入评估。

直接处理 Telegram 内容时，发布者对频道的单方许可并不充分。只有 Telegram/独立法律审查确认具体用途可行，并取得所有相关作者逐一、持续、可撤销且覆盖保存、展示、自动分析和 AI/ML 的有效同意后，才可另行评审；项目默认没有这种例外。

即使通过上述评审，也应：

- 排除转发、引用或媒体中第三方拥有的内容，除非授权同时覆盖；
- 只保存实现事件验证所需的最小字段，不镜像完整历史和媒体；
- 保存平台/法律评审、逐一同意来源、范围、开始/撤销时间和最后复核时间；
- 遵守 Telegram 当前条款、发布者条款、版权和隐私要求；
- 授权撤销或条款变化时立即暂停，而不是继续依赖旧 consent；
- 把任何需要人工或法律判断的来源标记为 `paused`，不能静默当成正常源。

### 10.3 Agent 使用

不应为每个 Telegram 频道启动一个 Agent。采集、URL 提取、去重、时间判断和角色分配应由本地确定性逻辑完成。Telegram 本身不直接喂给 Agent；当人工线索指向允许机器读取的官网/RSS原文时，才进入现有 Trend Scout 或 Token Context 流程。搜索机器人的结果只能触发“寻找原始来源”，不能直接增加 attention 或 candidate score。

## 11. 推荐频率

下列频率仅适用于**发布者官网/RSS、GitHub、状态页或已获授权的机器 feed**，不是对未授权 `t.me` 页面进行抓取的建议：

| 来源类型 | 正常频率 | 重大事件窗口 | 退避 |
|---|---:|---:|---:|
| 官方技术、协议和交易所公告 feed | 5 分钟 | 2–3 分钟 | 30 分钟 → 2 小时 → 6 小时 |
| 成熟新闻媒体 RSS | 10 分钟 | 5 分钟 | 30 分钟 → 2 小时 |
| 获授权的社区线索 feed | 20–30 分钟 | 10 分钟 | 1 小时 → 4 小时 |
| 频道 handle、官网验证和授权状态复核 | 每 24 小时 | 安全告警时立即 | 失败后 6 小时 |
| TGStat、Searchee、Junction 等交互工具 | 仅人工按需 | 不自动 surge | 不定时查询 |

Web 页面刷新只读 SQLite，不触发 Telegram 查询、Agent 或交易判断。订阅量和影响力更新不需要高频；其观察时间必须随值保存。

## 12. 可视化和审计建议

Telegram 来源卡应显示：

- 平台、频道名、精确 handle、发布者、语言；
- 官网双向验证状态和验证 URL；
- `manual_directory`、`publisher_feed`、`publisher_authorized`、`paused` 等访问状态；
- authority、reach/heat、decision eligibility 三个分离维度；
- 公开预览/需账号、最后核验、最后允许来源更新时间；
- 原始 Telegram permalink 和外部原文；
- 是否转发、是否编辑、是否删除、是否只有标题、是否缺少原始链接；
- `feature`、`confirmation`、`identity`、`promotion`、`discovery-only` 标签；
- 为什么可用于决策或为什么保持 `WAIT`。

影响力事实只能显示在某个观察时间实际看到的数据，例如调研时订阅量、单帖浏览、反应和传播速度；不可用时为 `unknown`。第三方 TGStat/TG.ME 统计应显示供应商和采集时间，不能伪装成 Telegram 官方数据。

## 13. 明确不采用或默认禁用的候选

- `@solanaannouncements`：历史频道，当前 Solana 官网改链 `@solana`，且检索到的帖子陈旧。
- `@Raydiumx`：未由 Raydium 官方入口核验的相似频道。
- `@reutersworldchannel`：页面明确声明非 Reuters 官方。
- 检索到的 Financial Times 相似频道：明确非官方。
- `@PumpFunNewPools`、`@solana_dailyann`：噪声、重复或推广属性强，默认禁用。
- `@pumptrendingofficial_bot`：即使被 Pump 品牌频道链接，功能本身与制造成交/热度有关，禁止作为证据或连接钱包。
- Pyrogram：已停止维护。
- STC-Reader：永久镜像媒体和公开仓库存储风险过高。
- Telegram-Search-Engine：PostgreSQL/索引/AI 复杂度和条款风险与本项目目标不符。

## 14. 主要核验入口

- [Solana Community](https://solana.com/community)
- [Raydium 官网](https://raydium.io/)
- [Jupiter Developer Support](https://developers.jup.ag/support)
- [Pump.fun 官网](https://pump.fun/)
- [Coinbase Telegram/WhatsApp scam guidance](https://help.coinbase.com/en-gb/coinbase/privacy-and-security/avoid-scams/telegram-scams)
- [TGStat English official channel](https://t.me/s/tgstat_en)
- [The Feed Reader Bot 官网](https://elite.thefeedreaderbot.com/)
- [Junction Bot 文档](https://www.junctionbot.io/documentation/forwarding)
- [Telegram Bot API FAQ](https://core.telegram.org/bots/faq)
- [Telegram API search documentation](https://core.telegram.org/api/search)
- [Telegram Content Licensing Terms](https://telegram.org/tos/content-licensing)
- [Telegram Bot Developer Terms](https://telegram.org/tos/bot-developers)
- [Telegram API Terms](https://core.telegram.org/api/terms)
- [Telegram Privacy Policy](https://telegram.org/privacy)
