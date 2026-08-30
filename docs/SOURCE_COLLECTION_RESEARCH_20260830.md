# 信息采集开源项目与 Telegram 来源调研（2026-08-30）

## 结论

本轮只采用 GitHub 仓库、项目官方文档、所有者官网和 Telegram 公共页面作为证据。适合当前 `Python + SQLite + 单机 Windows` 架构的最小方案不是再部署一套聚合平台，而是：

1. **默认不自动抓取、索引或聚合 Telegram 内容。** Telegram 当前官方条款把数据抓取和 AI/ML 使用列为受限行为；`t.me/s` 只用于人工核验频道身份和寻找其指向的官网/RSS/原始文章；
2. 优先摄取发布者官网、官方 RSS、公告页和原始文章。保留现有轻量 `ElementTree` RSS 解析器、浏览器桥、PumpPortal、GeckoTerminal 和 DexScreener；只有真实兼容性缺口出现后，才重新评估 `feedparser` 或 `Trafilatura`，不为项目数量增加依赖；
3. X 继续使用本机浏览器桥。`Twikit`、`Nitter`、`snscrape` 等非官方客户端不应成为常驻主链路；
4. 保留现有无登录 Bluesky 搜索轮询。Jetstream 只在存在很小的明确 DID 白名单时评估；它不支持服务端关键词过滤，不适合个人电脑订阅全网帖子后本地筛词；
5. 只借鉴 TrendRadar、NewsNow、DailyHotApi 的热榜、排名轨迹和适配器设计，不把 GPL/AGPL 代码复制进项目，也不引入另一套 Web 控制台；
6. Telegram 搜索机器人只用于人工发现候选频道。机器人运营方能看到查询和账号信息，其返回结果不能进入交易证据链，也不能被自动送给 Agent；
7. 新采集器都是本地确定性任务，不增加 Agent 数量。Agent 并发仍最多为 2，信息搜集的覆盖面靠轻量采集器扩大，而不是堆叠模型进程。

Telegram 自动摄取默认没有项目级例外。频道所有者单方许可并不明显解除 Telegram 平台条款；只有 Telegram/独立法律审查确认该具体用途可行，并且所有相关作者对指定内容、用途、保存范围和 AI/ML 使用给出明确、持续、可撤销的同意后，才可另行评审。默认配置始终关闭；转发、评论、群聊和第三方投稿不能由频道所有者代为许可。

## 一、开源项目与官方数据接口矩阵

维护状态是 2026-08-30 的快照。“原始字段”表示能否保留原发布时间、作者/发布账号和原始 URL；字段是否存在仍取决于上游页面。

### RSS、新闻正文和网页变更

| 项目 | 用途与现成界面 | 维护/许可 | 登录、API 与 Windows 成本 | 原始字段 | 风险 | 结论 |
|---|---|---|---|---|---|---|
| [feedparser](https://github.com/kurtmckee/feedparser) | Python 解析 RSS/Atom/JSON Feed；无独立 UI | 6.0.14；活跃；BSD-2-Clause | 无账号、无服务；Python 直接安装，成本最低 | 是：取决于 feed | 恶意 XML、超大响应、错误时间；需限制大小/超时并保留本地观测时间 | **暂不接入**；当前已有小型 `ElementTree` 解析器，出现可复现兼容缺口后再评估 |
| [Trafilatura](https://github.com/adbar/trafilatura) | 新闻正文、标题、作者、日期和元数据抽取；无 UI | 2.2.0（2026-08 调研快照）；活跃；Apache-2.0 | 无账号；Python 包，Windows 低成本 | 通常可以；须把页面日期与本地 `observed_at` 分开 | 网页日期可能错误；抓取受 robots、版权和站点条款约束；公开控制台不应转载全文 | **暂缓**；只有短摘要无法完成核验时再评估，默认展示标题、短摘录和原始链接 |
| [news-please](https://github.com/fhamborg/news-please) | 完整新闻站爬虫、Common Crawl 和正文抽取；无轻量 UI | 2026-04 仍有提交，无正式 GitHub release；Apache-2.0 | Python/Scrapy，依赖含 Redis、数据库客户端等；Windows 中高成本 | 是 | 大范围爬取有条款/版权/封禁风险，依赖远超当前需要 | **拒绝整套接入**；只借鉴字段和抽取测试 |
| [changedetection.io](https://github.com/dgtlmoon/changedetection.io) | 页面变更监控、浏览器步骤和 Web UI | 0.55.8（2026-07）；活跃；Apache-2.0 | 可 pip/Docker；浏览器模式还需 Playwright，Windows 中等成本 | URL/观测时间是；通常无可靠作者 | 任意 URL 监控存在 SSRF 面；项目近期也持续修复安全问题 | **借鉴**变更指纹、退避和差异 UI；不部署第二服务 |
| [FreshRSS](https://github.com/FreshRSS/FreshRSS) | 完整自托管 RSS 阅读器、过滤和 UI | 1.29.1（2026-05）；活跃；AGPL-3.0 | PHP + Web 服务；可用 SQLite，但 Windows 常驻成本中等 | 是：取决于 feed | 新服务面、重复 UI；修改并公开提供服务涉及 AGPL 义务 | **借鉴**源健康、OPML 和未读/标签设计；不嵌入 |
| [Miniflux](https://github.com/miniflux/v2) | 极简 RSS 阅读器和 Web UI | 2.3.3（2026-07）；活跃；Apache-2.0 | 必需 PostgreSQL；Windows 需额外服务 | 是 | 明确违反当前“不引入 Postgres”原则 | **拒绝** |
| [RSSHub](https://github.com/DIYgod/RSSHub) | 数千站点到 RSS 的路由系统；文档/路由 UI，不是热度台 | 2026 年持续维护；AGPL-3.0 | Node；不少路由要 Cookie/Token，部分使用浏览器；可选 Redis | 依路由而定；通常含时间、作者/账号、URL | 路由随站点变化；X 路由已有持续失效；Cookie 泄漏和账号封禁风险；AGPL | **借鉴路由目录和测试**。若将来需要，只能作为未修改的 loopback 独立服务，不复制代码 |
| [RSS-Bridge](https://github.com/RSS-Bridge/rss-bridge) | 把无 RSS 页面转换成 Atom/JSON；有桥接表单 | 2026-08 仍有提交，最近标签较旧；Unlicense | PHP；文件/SQLite 缓存；Windows 中等成本 | 依 bridge 而定 | 站点条款、页面变更、重复服务 | **借鉴**单源 adapter + cache 结构；不部署 |

### 热榜、趋势与可视化

| 项目 | 用途与现成界面 | 维护/许可 | 登录、API 与 Windows 成本 | 原始字段 | 风险 | 结论 |
|---|---|---|---|---|---|---|
| [TrendRadar](https://github.com/sansan0/TrendRadar) | 多平台热榜、RSS、排名轨迹、时间线、AI 报告；有深色报告和可视化配置 | 6.10.0（2026-06）；活跃；GPL-3.0 | Python/SQLite 可本机运行；完整系统仍与现有控制台重复 | 平台、标题、排名、时间、链接；通常没有个人作者 | 热榜排名是发现信号，不是事实；GPL 不宜复制到当前源码 | **借鉴**排名轨迹、时间线和状态展示，不嵌入代码 |
| [NewsNow](https://github.com/ourongxing/newsnow) | 中文实时/热门新闻聚合；有网页 UI | 0.0.41（2026-06）；README 将当前版称为中文 demo、停止接受贡献并等待新版；MIT | Node 20+/pnpm 或 Docker；Windows 中等成本 | 平台、标题、时间、URL；作者依来源 | 非官方端点可能变化或限流；处于过渡维护期 | **借鉴适配器模式**；不常驻第二个前端，也不把它与引用其数据的项目算成独立来源 |
| [DailyHotApi](https://github.com/imsyy/DailyHotApi) | 大量中文平台热榜，输出 JSON/RSS；API 文档界面 | 2.0.8（2026-08）；活跃；MIT | Node/Docker/PM2；部分源要 Puppeteer；中等成本 | 平台、标题、热度/排名、URL；作者通常缺失 | 仓库明确提醒部分抓取可能违反站点规则；浏览器源成本高 | **借鉴**少量公开端点的适配器和缓存；不全量部署 |
| [pytrends](https://github.com/GeneralMills/pytrends) | 非官方 Google Trends 客户端；无 UI | 已归档/长期不稳定；Apache-2.0 | 无官方 API key，但容易限流；Windows 低成本 | 查询时间和趋势值，无发布者 URL | 非官方接口频繁失效和封禁 | **拒绝作为主链路**；Google Trends 只做人工核验 |

### 社交平台与浏览器采集

| 项目 | 用途与现成界面 | 维护/许可 | 登录、API 与 Windows 成本 | 原始字段 | 封禁/安全风险 | 结论 |
|---|---|---|---|---|---|---|
| [Playwright Python](https://github.com/microsoft/playwright-python) | Chromium/Firefox/WebKit 自动化；自带 inspector，无最终业务 UI | 1.62.0（2026-08 调研快照）；活跃；Apache-2.0 | 不要求 API；登录站点依赖用户浏览器会话；下载浏览器后成本中等 | 可从可见 DOM 保留时间、作者、URL | 自动化频率过高会触发挑战或封禁；Cookie 等同账号访问权 | **不接入**；当前桥是用户可见浏览器扩展，并未使用 Playwright |
| [Twikit](https://github.com/d60/twikit) | 非官方 X 搜索、趋势、用户和推文读取；无 UI | 2.3.1（2026-02）；活跃；MIT | 不用官方 API，但完整功能要账号登录/Cookie；Python 低成本 | 是 | 使用内部接口，结构易变；账号暂停风险高；会话是敏感材料 | **拒绝**；现有可见浏览器桥已覆盖目标，不做账号/Cookie 实验 |
| [Nitter](https://github.com/zedeus/nitter) | X 的替代前端/抓取层；有 Web UI | 2026-08-26 已归档，仓库说明收到 X 的停止侵权要求；AGPL-3.0 | 还需真实 X 账号/session、Redis/Valkey、Nim；Windows 高成本 | 历史设计上可以 | 法律、账号、会话池与封禁风险高；违反无 Redis 原则 | **禁止采用** |
| [snscrape](https://github.com/JustAnotherArchivist/snscrape) | 多社交站点抓取；CLI，无业务 UI | Twitter 抓取已明确不可用；GPL-3.0+ | 无官方 API；Python 低成本 | 设计上是，但当前 X 不可靠 | 失效、站点条款和封禁风险 | **拒绝** |
| [Instaloader](https://github.com/instaloader/instaloader) | Instagram 帖子/账号元数据下载；CLI | 4.15.3（2026-08 调研快照）；活跃；MIT | 公共内容有限，稳定读取通常需登录；Python 低成本 | 是 | Instagram 登录挑战、账号锁定和条款风险高 | **拒绝常驻采集**；需要时通过用户可见浏览器桥观察白名单账号 |
| [yt-dlp](https://github.com/yt-dlp/yt-dlp) | 多视频站点元数据/媒体抽取；CLI | 2026.08.19；非常活跃；源码 Unlicense，二进制组合许可更复杂 | 公开页面可免登录；部分站点要 Cookie；Windows 低到中成本 | 通常有上传者、发布时间和原 URL | Cookie/外部下载器/文件处理扩大攻击面，且无需下载媒体 | **借鉴/限制使用**：优先 YouTube 官方 RSS；若接入仅提元数据、禁用 Cookie 和下载 |
| [Bluesky Jetstream](https://github.com/bluesky-social/jetstream) | Bluesky 全网事件 JSON WebSocket；无最终 UI | 当前仓库 2026-07 仍活跃；MIT/Apache-2.0 双许可 | 公共服务读取不需登录；自托管全网归档成本高 | 是：DID/URI、record `createdAt`、原帖可还原 | 服务端能按 DID/collection/kind 过滤，但不能按关键词过滤；全网流不适合个人电脑；`createdAt` 是用户声明时间 | **仅在小型 DID 白名单时评估**；当前继续搜索轮询，并以本机 `observed_at` 控制决策时间 |
| [atproto Python SDK](https://github.com/MarshalX/atproto) | Bluesky/AT Protocol Python 客户端、身份解析 | 0.0.69（2026-06）；活跃；MIT | 公共读取通常无登录；Python 低成本 | 是 | 依赖面比直接 WebSocket 更大 | **可选直接接入**，仅在 DID/帖子解析需要时使用 |
| [PRAW](https://github.com/praw-dev/praw) | Reddit 官方 API Python 包；无 UI | 2026-07 仍活跃；BSD-2-Clause | 即使只读也需 client id、client secret 和 user-agent | 是 | 需要保存 API secret，且用户已要求避免 API 级接入 | **拒绝当前接入**；使用 Reddit 公共 RSS 或浏览器桥 |

### Telegram 采集与归档

| 项目 | 用途与现成界面 | 维护/许可 | 登录、API 与 Windows 成本 | 原始字段 | 封禁/安全风险 | 结论 |
|---|---|---|---|---|---|---|
| [tgfeed](https://github.com/nDmitry/tgfeed) | 把公开 `t.me` 页面输出成 RSS/Atom；HTTP 服务，无完整研究 UI | 仓库仍有活动；MIT | 公开频道不需 Telegram 账号/API；Go 单文件服务，Windows 低成本 | 是：消息 ID、时间、频道、URL | Telegram 官方 Content Licensing/AI Scraping 条款禁止把平台数据抓取、索引、聚合后用于 AI/ML；另有版权和页面变化风险 | **默认拒绝**；仅作为能力调研记录，不复刻解析器 |
| [RSSHub Telegram 路由](https://docs.rsshub.app/routes/social-media#telegram) | 公开频道转 RSS；可选 MTProto 会话 | 跟随 RSSHub；AGPL-3.0 | 公开网页模式不需账号；私有/完整模式需 `API_ID/API_HASH/SESSION` | 是 | 同样受 Telegram 内容许可条款约束；会话极敏感；完整 RSSHub 过重 | **拒绝 Telegram 路由接入** |
| [Telethon](https://github.com/LonamiWebs/Telethon) | Python MTProto 完整客户端；无最终 UI；主项目已迁移 Codeberg | 仍维护；MIT | 需要 Telegram `api_id`、`api_hash`、手机号登录和 session 文件；Windows/Python 低成本 | 是，包括转发来源和消息 ID | API 条款把使用 Telegram API 的应用纳入内容许可/AI 限制；session 等同账号访问，另有 FloodWait 和封禁风险 | **默认拒绝采集/聚合**；合法客户端用途也需单独条款评审和内容许可 |
| [TDLib](https://github.com/tdlib/td) | Telegram 官方完整客户端库 | 2026-07 仍活跃；Boost-1.0 | 需要 API ID/hash 和完整登录；C++ 构建、本地数据库，Windows 高成本 | 是 | 完整账号权限和本地会话；复杂度过高 | **拒绝**，个人电脑不需要完整客户端 |
| [Pyrogram](https://github.com/pyrogram/pyrogram) | Python MTProto 客户端 | 2024-12 已归档且明确不维护；LGPL-3.0 | 需 API ID/hash、手机号和 session | 是 | 账号/session 风险，且已停止维护 | **拒绝** |
| [python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot) | Telegram Bot API Python SDK；无最终研究 UI | 22.x，2026 仍活跃；LGPL-3.0 | 要 Bot token；机器人只能收到其被加入/订阅范围内的更新 | 对收到的 update 是 | Bot Developer Terms 禁止超出服务必需范围的数据收集，并明确禁止为数据集/AI 抓取公共群组或频道 | **拒绝作为采集器**；未来只可向主动同意的用户发送通知 |
| [Telegram-Archive](https://github.com/GeiserX/Telegram-Archive) | Telethon 实时归档、SQLite、WebSocket 和 Web viewer | 8.4.1（2026-08）；活跃；GPL-3.0 | 需 API ID/hash、手机号/session；Docker 镜像较大，也提供 Windows 鉴权脚本 | 是，含转发作者/频道 | 归档/聚合用途与当前 Telegram 内容许可限制冲突；另有完整账号会话、GPL 和重复 UI | **拒绝接入**；通用的 WAL/退避思想可独立实现，但不复制 Telegram 采集部分 |
| [telegram2rss](https://github.com/akopachov/telegram2rss) | 公开频道网页转 RSS 的 serverless 实现 | 活跃度低；GPL-3.0 | 无账号；部署低成本 | 是 | 抓取/聚合用途受 Telegram 条款限制；页面结构变化；GPL | **拒绝** |

### Crypto、新 Token 和链上数据

| 项目/接口 | 用途与现成界面 | 维护/许可 | 登录、API 与 Windows 成本 | 原始字段 | 风险 | 结论 |
|---|---|---|---|---|---|---|
| [solana-py](https://github.com/michaelhly/solana-py) | Solana RPC/WebSocket Python SDK；无 UI | 0.40.3（2026-08 调研快照）；活跃；MIT | 公共 RPC 可免账号；Python，低成本 | 链上 slot/block time、签名、账户；不是社交作者 | 公共 RPC 限流；链上时间与本地观测时间仍要并存 | **不接入**；当前使用 `solders + httpx` 已能完成 Devnet/链上核验，避免重复 SDK |
| [Yellowstone gRPC](https://github.com/rpcpool/yellowstone-grpc) | Geyser 高性能账户/交易流 | 14.2.2+solana.4.1.0（2026-07）；活跃；AGPL-3.0 | 自托管需 validator/Rust/Linux；托管端点通常需 token；Windows 高成本 | 链上原始 slot、签名、账户 | 资源和运维远超个人电脑，且需新凭据 | **拒绝自托管**；未来只有在明确购买托管服务时再评估 |
| [Raydium SDK V2](https://github.com/raydium-io/raydium-sdk-V2) | Raydium 池发现、报价和交易构造；无独立 UI | 2026-04 仍活跃；GPL-3.0 | TypeScript/Node；交易部分需要钱包签名 | 池/交易数据可以；无社交作者 | 含签名能力、GPL、与 Python 栈不一致 | **只借鉴池标识和数学**，不接入交易构造 |
| [DEX Screener API](https://docs.dexscreener.com/api/reference) | 官方公开 pair/search/token-pairs HTTP；官网有图表 UI；非开源 | 官方文档当前；服务条款适用 | 公共读取无需 key；300 req/min 类接口限制；Windows 低成本 | pair 创建、链/DEX、URL；无发布作者 | 自动索引不等于真实性；需缓存/限速，不能当安全证明 | **直接保留**，作为价格/池/成交交叉核验 |
| [PumpPortal 实时数据](https://pumpportal.fun/data-api/real-time/) | Pump.fun 第三方新币、迁移、交易 WebSocket；无完整研究 UI；非开源 | 官方文档当前 | 新币/迁移流免费；token/account trades 现在可能要求 API key、关联钱包和费用；只应维持单 WS | mint、交易/创建者相关字段、到达顺序；本地补观测时间 | 它不是 pump.fun 官方；计费流和关联钱包会增加成本与风险 | **保留免费新币/迁移流**；不启用付费交易流，不关联钱包 |
| [Solana Explorer](https://github.com/solana-foundation/explorer) | 官方链上浏览器 UI | 持续维护；Apache-2.0 | 大型前端和 RPC；Windows 中高成本 | 链上签名、时间、账户和程序 | 部署重复；不是数据源 | **借鉴深链和证据详情 UI**，不自托管 |

## 二、Telegram 官方条款边界

下列官方条款改变了技术优先级；“公开可查看”不等于“允许程序抓取并用于研究 Agent”。

- [Telegram Terms of Service](https://telegram.org/tos) 明确把 Content Licensing and AI Scraping Terms 适用于所有访问平台的用户、企业和第三方服务；
- [Terms of Service for Content Licensing](https://telegram.org/tos/content-licensing) 规定，除 Telegram 的正常、预期用户用途外，访问用户生成内容受到限制，并明确禁止为 AI/ML 抓取、索引、采集或聚合平台数据；例外要求相关用户对特定内容和特定频道/上下文给出明确、知情、持续的同意；
- [Telegram API Terms of Service](https://core.telegram.org/api/terms) 把使用 MTProto/API 的应用继续绑定到上述内容许可与 AI 限制，还要求访问频道内容的客户端支持 Telegram 官方赞助消息；
- [Bot Platform Developer Terms](https://telegram.org/tos/bot-developers) 要求 bot 只处理服务运行必需的数据，并明确禁止为大型数据集、机器学习或 AI 产品抓取公共群组/频道；还要求对自愿提交的数据取得明确、主动、可撤销的同意。

因此本项目采用以下默认规则：

1. 不定时抓取 `t.me/s`，不使用 Telethon/TDLib/Pyrogram 归档频道，不通过 Bot API 建立频道索引；
2. Telegram 链接只保存在“人工来源目录”中，用于用户点击查看和核验所有者；不复制频道正文，不投喂 Agent，不计算自动热度；
3. 对频道中出现的线索，转而采集发布者官网、官方 RSS、原始文章、链上交易或项目公告页；这些外部来源各自再按其条款处理；
4. 发布者许可本身不足以创建例外；只有 Telegram/独立法律审查确认具体用途可行，并取得所有相关作者逐一、持续、可撤销且覆盖保存、展示、自动分析和 AI/ML 的同意，才可另行评审；
5. 频道转发、评论、群聊和第三方投稿默认不可能由频道所有者单独授权，仍不得摄取。

## 三、Telegram 人工来源目录与分层

以下名单用于人工导航、所有权核验和寻找发布者官网，不是自动采集白名单。频道内容本身默认不进入 SQLite 事件表、热度计算或 Agent 上下文。

### A. 项目/平台所有者的第一方公告

人工查看时，这些频道只能证明“该项目/平台在 Telegram 发布了这句话”。它们可能是营销内容，不能自动证明叙事真实，也不能单独触发买入。系统应优先读取同一所有者的官网公告/RSS。

| 频道 | 所有权证据 | 建议角色 | 备注 |
|---|---|---|---|
| [@solana](https://t.me/solana) | 当前 [Solana 官方社区页](https://solana.com/community)链接的 Telegram 入口 | `identity` / 人工发现 | 完整内容需要 Telegram 账号；自动信息改读 Solana 官网新闻。历史 `@solanaannouncements` 已不在当前官网入口且内容陈旧，默认禁用 |
| [@jup_dev](https://t.me/jup_dev) | 频道直接链接 [dev.jup.ag](https://dev.jup.ag/) 和 Jupiter 官方账号 | `feature`（Jupiter 运行/开发变更） | 适合故障、API 和产品变更；非 Jupiter 事件只作上下文 |
| [@jup_marketing](https://t.me/jup_marketing) | 频道直接声明 Jupiter marketing 并交叉链接官方资产 | `promotion` | 明确降权，不作为独立确认 |
| [@raydium](https://t.me/raydium) | 频道直接链接 [raydium.io](https://raydium.io/) 和官方 X/讨论群 | `feature` 或 `promotion` | 上线/故障是第一方；活动宣传为 promotion |
| [@raydiumprotocol](https://t.me/raydiumprotocol) | 由 Raydium 公告频道交叉链接 | `identity` | 社区讨论，不作为确认 |
| [@pumpfun](https://t.me/pumpfun) | 频道直接链接 [pump.fun](https://pump.fun/) | `promotion`/`identity` | 项目自有 meme 文案；必须等待独立事件或链上证据 |
| [@Bybit_Announcements](https://t.me/Bybit_Announcements) | [Bybit 官方社区页](https://www.bybit.com/es-ES/promo/global/communities)直接链接 | `feature`（上币/维护）或 `promotion` | 频道混有大量促销；按帖子类型拆分角色 |
| [@OKXAnnouncements](https://t.me/OKXAnnouncements) | [OKX 官方社区页](https://www.okx.com/zh-hans/community)直接链接 | `feature`（上币/维护）或 `promotion` | 英文公告频道 |
| [@OKXAnnouncements_CN](https://t.me/OKXAnnouncements_CN) | [OKX 官方社区页](https://www.okx.com/zh-hans/community)直接链接 | `feature` 或 `promotion` | 中文公告，与英文版去重 |
| Coinbase：无全球官方 Telegram | [Coinbase 官方帮助](https://help.coinbase.com/en-au/coinbase/other-topics/other/is-coinbase-present-on-social-media)明确写明没有 Telegram 官方账号 | 黑名单规则 | 任何声称“Coinbase 官方 Telegram”的频道默认拒绝；地区例外需逐次从 Coinbase 官网核验 |

本轮未把 Binance Telegram 加入白名单：没有在本轮获得足够清晰、当前的所有者官网反向链接。宁可暂缺，也不靠频道名称、蓝勾或订阅数推断官方身份。

### B. 建立品牌的新闻媒体：人工发现后回到官网确认

| 频道 | 直接证据 | 建议角色 |
|---|---|---|
| [@cointelegraph](https://t.me/s/cointelegraph) | 频道页声明实时 Cointelegraph 新闻并链接官网 | 人工 discovery；自动化改读 Cointelegraph 官网/RSS，再标 `confirmation` |
| [@the_block_crypto](https://t.me/s/the_block_crypto) | 频道页声明 The Block 官方新闻 feed 并链接官网 | 人工 discovery；回到 The Block 原文确认 |
| [@wublockchainenglish](https://t.me/s/wublockchainenglish) | 频道页声明唯一英文 Telegram 并链接 Wu Blockchain | 人工 discovery；回到官网/原始引述确认 |
| [@ChannelPANews](https://t.me/s/ChannelPANews) | 频道页链接 [PANews 官网](https://www.panewslab.com/) | 人工 discovery；自动化改读 PANews 官网 |
| [@Odaily_News](https://t.me/s/Odaily_News) | 频道页链接 Odaily 官网和官方 X | 人工 discovery；自动化改读 Odaily 官网 |
| [@theblockbeats](https://t.me/s/theblockbeats) | 频道页链接 BlockBeats 官网 | 人工 discovery；自动化改读 BlockBeats 官网 |
| [@decryptnews](https://t.me/s/decryptnews) | 频道页链接 Decrypt 官网 | 人工 discovery；自动化改读 Decrypt 官网/RSS |

媒体可以互相转载同一通讯社或原帖。因此“7 个频道报道”不能直接算 7 个独立来源；回到官网后仍需按最终原始 URL、被引述主体和转载链聚类。

### C. 社区、链上观察和快讯：仅人工发现

| 频道 | 能提供什么 | 角色与限制 |
|---|---|---|
| [@lookonchainchannel](https://t.me/s/lookonchainchannel) | 地址/交易线索、链上叙事 | 人工 discovery；必须独立查链。`@lookonchain` 是讨论/支持入口，不是广播源 |
| [@whale_alert_io](https://t.me/whale_alert_io) | 大额转账线索 | 人工 discovery；必须核对链、签名、地址标签和时间 |
| [@unfolded](https://t.me/s/unfolded) | 手工汇编市场图表和数据 | 人工 discovery；回到图表原始数据；注意赞助和二手图表 |
| [@TreeNewsFeed](https://t.me/s/TreeNewsFeed) | 高频标题，常标注 RTRS/BBG/WSJ 等来源 | 人工 discovery；回到可访问原始出处，注意通讯社内容授权 |
| [@Breaking_News](https://t.me/s/Breaking_News) | DEGEN NEWS 式高速度标题 | 人工 discovery；标题化和煽动性较强，不能作为确认 |
| [@SolanaNewListing](https://t.me/s/SolanaNewListing) | 自动新币/池列表 | 不采集；与 PumpPortal/链上流重复，且带交易机器人/联盟动机 |

### D. 明确拒绝或拉黑的 Telegram 来源

| 频道/账号 | 原因 |
|---|---|
| [@coindesk](https://t.me/coindesk) | 页面自身标注为“Crypto news feed FAKE”；CoinDesk 名称不能作为所有权证据 |
| [@BlockBeatsOfficial](https://t.me/BlockBeatsOfficial) | 页面内容是无关 token/music portal；正确新闻频道是 `@theblockbeats` |
| [@pumpfun_pumps](https://t.me/s/pumpfun_pumps) | 明示协调 pump，属于操纵/推广线索，不得进入买入证据 |
| [@solanadexscreeneralerts](https://t.me/solanadexscreeneralerts) | 第三方提醒和打赏入口，非 DexScreener 官方，且与链上采集重复 |
| `@DexscreenerBot` / `@dexscreener_bot` | 本轮未从 DexScreener 官方文档获得所有权证明；使用官方 HTTP API 替代 |
| 任何要求导入私钥、连接钱包、转账、成为频道管理员或运行交易的“新闻/搜索 bot” | 与信息采集无关，权限过大，直接拒绝 |

## 四、Telegram 搜索/聚合机器人

互动机器人需要用户在 Telegram 中发送消息。机器人运营方至少能得到 Telegram 用户标识、查询文本、时间和聊天上下文；它们不是被动公开网页。使用它们也不构成把搜索结果抓取、保存或用于 Agent 的许可。

| Bot | 验证与用法 | 账号/API 要求 | 隐私/运营风险 | 建议 |
|---|---|---|---|---|
| [@SearcheeBot](https://t.me/searcheebot?do=open_link) | Telegram 公共页显示“Find any channel”；[TGStat 官方频道](https://t.me/s/TGStat_EN)说明其基于频道目录和实时索引 | 需要 Telegram 账号向第三方 bot 发送关键词；程序 API 另需 TGStat token | 运营方看到搜索词和用户；目录排名不证明权威 | **仅人工发现新频道**，结果进入待核验清单 |
| [@TGStat_Bot](https://t.me/TGStat_Bot) | 返回频道、聊天和帖子的统计；TGStat 官方频道说明发送 `@username`/链接即可 | 需要 Telegram 账号；自动化 API 需 TGStat token | 运营方看到查询；统计覆盖不等于真实性，异常流量可刷 | **仅人工评估 reach/增长异常**，不进入决策链 |
| [@cryptopaniccombot](https://t.me/cryptopaniccombot) | 页面和 [CryptoPanic 官方 bot 文档](https://cryptopanic.com/developers/bots/docs)相互验证；支持 `/news`、`/news BTC` | 需要 Telegram 账号；将其设为频道管理员并非必要 | 查询和账号暴露给第三方；聚合结果仍是二手新闻 | **可人工查询，不设管理员，不自动采集** |
| [@oksearchbot](https://t.me/oksearchbot) | 公共页称可搜索频道、群和内容 | 需要 Telegram 账号 | 所有者和索引规则不透明；查询会外泄 | **人工发现备选**，优先级低于 Searchee/TGStat |
| [@argosearchbot](https://t.me/argosearchbot) | 公共页称为 Telegram 搜索引擎 | 需要 Telegram 账号 | 所有者和排名规则不透明；查询会外泄 | **人工发现备选**，不自动化 |
| SolTradingBot/各种 signal 或 sniper bot | 通常提供搜索、新币提醒和交易按钮 | 常要求连接钱包、私钥或 bot 账户 | 强烈的联盟/交易利益冲突；可能导致资金损失 | **拒绝** |

不得向互动 bot 发送：私钥、钱包恢复词、邮箱/密码、浏览器 Cookie、内部关注名单、未公开的钱包地址、完整的策略关键词或 Agent 输出。不得把第三方 bot 加为管理员。

## 五、建议的最小接入设计

### 1. 官网/RSS 优先的来源路由

Telegram 只保存频道目录元数据，不保存帖子正文、消息统计或频道归档：

```text
platform = telegram
account_handle / display_name
source_tier = primary | confirmation | discovery
manual_url
ownership_evidence_url / ownership_verified_at
preferred_ingest_url = 官网 RSS | 公告页 | 原始文章索引
automation_permission = denied_by_default | explicitly_authorized
permission_scope / permission_evidence / permission_expires_at
```

人工从 Telegram 发现线索后，采集器沿 `preferred_ingest_url` 获取同一信息。官网/RSS 事件仍保存 `published_at`、`observed_at`、`ingested_at`、作者和原始 URL，并执行现有 future-data、freshness 和独立来源规则。

如果通过 Telegram/独立法律审查且取得所有相关作者有效同意，仍必须另行启用 permission-gated collector，并满足：

- 许可文字明确覆盖保存、网页展示、自动分析以及 Agent/AI 使用；
- 只处理许可指定频道由所有者原创的帖子，不处理转发、评论、群聊或第三方投稿；
- 保存许可证据、范围、到期/撤销状态，并允许立即停止及按约删除；
- 仍限制 host、响应大小、超时和重定向，避免 SSRF；
- 没有有效许可时配置校验必须拒绝启动，不能静默退回公开网页抓取。

### 2. 建议频率（不是当前设备事实）

下表是未来采集器的建议值。调研时当前设备总轮询约为 45 秒、Source Discovery 约为 12 小时；是否已实现 ETag 等能力必须以代码和最新验证快照为准。

| 类别 | 默认频率 | 说明 |
|---|---:|---|
| Telegram 自动采集 | 关闭 | 仅人工导航；有审计许可的单频道例外另行配置 |
| 发布者官网公告/RSS | 180 秒 | 使用 ETag/Last-Modified；按原始链接去重 |
| RSS | 180 秒 | 目标能力是 ETag/Last-Modified 与失败退避；未实现前不得写成已生效 |
| 热榜适配器 | 5–10 分钟 | 保存 rank、rank_delta 和首次进入榜单时间 |
| Bluesky Jetstream | 默认关闭 | 只有很小的 DID 白名单时评估；不做全网关键词本地过滤 |
| X | 继续当前浏览器桥节奏 | 用户可见会话；不要另起 Twikit/Nitter 账号池 |
| Agent source discovery | 24 小时或手工触发 | 只发现/核验源，不承担高频采集 |

这些确定性采集任务不占 Agent 槽位。Agent 并发仍最多 2。Telegram 人工目录和 bot 查询结果不进入 Agent 上下文。

### 3. 事件页面的信息组织

来源卡片建议按以下顺序，而不是按订阅数排序：

1. 所有者第一方公告；
2. 独立媒体/官方文件确认；
3. 链上原始记录；
4. 社区发现线索；
5. promotion/identity-only。

每条来源显示：

```text
[平台] [发布者] [来源层级] [证据角色]
发布时间 / 本机首次观测时间 / 新鲜度
原始链接 / 转发来源 / 独立来源组
reach 区间 / 当前 views / 互动异常提示
```

上述动态字段只来自允许自动摄取的平台。Telegram 人工目录项只显示频道名、人工链接、所有权证据和“自动采集关闭”状态，不抓取 views、正文或发布时间。

影响力不要合并成一个含糊数字。建议拆为：

- `authority`：所有权和编辑责任，0–40；
- `reach`：订阅/浏览量的对数区间，0–20；
- `engagement_quality`：互动率并对异常突增封顶，0–15；
- `freshness`：相对事件发生和本机观测时间，0–15；
- `independent_confirmation`：独立来源组数量，0–10。

`reach` 不能提高 `authority`。蓝勾、订阅数和转发数只能说明传播范围，不能证明账号所有权或消息真实性。

### 4. 决策门槛

- 第一方官网/RSS 可以证明“项目说过 X”，但宣传帖默认 `promotion`；Telegram 人工链接本身不作为机器决策证据；
- 媒体转载同一原帖/通讯社算一个来源组；
- 社区快讯和搜索 bot 返回项只能由用户人工打开；系统不自动保存正文，也不自动创建 investigation/CANDIDATE；
- 获得有效许可的 Telegram 例外才保存 `published_at`、`observed_at`、`ingested_at`，并继续执行 future-data 和 stale evidence 拒绝；
- Event→Token 和 Token→Event 优先保留官网/RSS/原始文章 URL、发布者、角色、独立确认组和本地首次观测时间；
- 缺少可验证原始时间、原始 URL 或发布账号时返回 `WAIT`，不补猜测字段。

## 六、不应做的事

- 不为信息采集购买或连接任何交易 bot，也不向 bot 提供钱包；
- 不把 Telegram/X/Instagram 的账号密码、Cookie、session、API hash 写入 `config.json`、SQLite、日志或 Web API；
- 不用用户的主 Google/邮箱账号批量注册社交平台；
- 不在 X 上高频运行非官方客户端；
- 不部署 Redis、PostgreSQL、Kafka、K8s、完整 Yellowstone validator 或完整 Bluesky 全网归档；
- 不复制 GPL/AGPL 项目的实现到当前仓库；
- 不把 Telegram 公开可见、登录后可见或 bot 可返回误认为自动抓取/聚合/AI 使用许可；
- 不把热榜、订阅数、媒体转载数或 bot 搜索排名当作真实性或买入信号。

## 七、实施优先级

1. **现在接入**：发布者官网/官方 RSS 优先路由；加固当前 RSS 获取与解析；现有链上源保持不变。Telegram 只保留人工来源目录、所有权证据和“自动采集关闭”状态。
2. **随后评估**：小型 Bluesky DID 白名单的 Jetstream；从 NewsNow/DailyHot/TrendRadar 借鉴一个经过条款核验的热榜 adapter 与排名轨迹，不能把同一底层 API 算作独立来源。
3. **人工工具**：TGStat/Searchee/CryptoPanic bot 只用于发现频道和找到其官网；结果不保存为事件、不进入 Agent。
4. **许可例外**：只有获得明确覆盖自动保存、展示和 AI/ML 用途的可审计许可，才评审单频道 collector；默认仍关闭。
5. **明确拒绝**：tgfeed/telegram2rss/RSSHub Telegram 路由、Telethon/TDLib/Pyrogram 频道归档、Twikit/Nitter/snscrape、Miniflux、Yellowstone 自托管和第三方交易/信号 bot。
