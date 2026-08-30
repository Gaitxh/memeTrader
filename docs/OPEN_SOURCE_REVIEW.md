# 免费接口与开源项目采用审查

本文件记录“直接采用什么、只借鉴什么、拒绝什么”。任何仓库在复制代码前仍要逐文件核对许可证、提交历史、依赖和密钥处理。

## 已直接采用的公开接口

### DexScreener

用途：

- 事件别名/CA 搜索 Token；
- 候选重新报价；
- 选择更深流动性池；
- 价格、流动性、成交量、5 分钟买卖数、社交链接。
- 低频读取官方 Token Profile、Community Takeover、Ads、Latest Boost、Top Boost，保存展示面和附带链接。

使用方式：报价只查询晋级事件、活动 Token 和每轮有上限的展示面 CA；不扫全网所有地址。展示面的“首次看到”不等于链上首次创建，Boost/Ads 是付费 promotion，Profile/Takeover/pair info 是 identity 种子。所有附带 URL 都需要回到独立原文验证；Telegram URL 只作人工目录。主机限速、TTL 缓存、429 退避。

旧 `D:\P5_completeSystem` model1/model3 只作为设计输入：model1 的展示面发现不等于全量新币，model3 也不是发现器；旧脚本的扁平 pair 误解析、多池混写、伪造币龄和丢失链接来源均未采用。详细记录见 [DexScreener 链接溯源与前向来源学习](DEXSCREENER_PROVENANCE_AND_SOURCE_LEARNING_CN.md)。

### GeckoTerminal

用途：

- Solana、BSC 新池分钟级补充；
- 第一次真实运行时建立 Token 与池快照；
- Pump WebSocket 丢线时保留较慢的发现通道。

### PumpPortal Data API

用途：

- 免费 `subscribeNewToken`；
- 免费迁移事件；
- 只获得创建线索和元数据。

不使用其按消息计费的指定 Token/账户交易流；不接 Trade API；不提交私钥。

### GoPlus + Honeypot.is + RugCheck

用途：只对已经晋级的短名单候选做免费外部安全交叉检查。

- GoPlus：EVM 合约权限、税率、黑名单/暂停/隐藏所有者等标志，以及 Solana authority 风险；
- Honeypot.is：EVM/BSC 交易模拟、税率和可卖性；
- RugCheck：Solana 风险摘要。

当前默认要求每个链族至少有一个外部安全报告。Honeypot.is 单独故障时，GoPlus 可继续承担 EVM 基础安全门；若配置显式要求交易模拟，则 Honeypot.is 仍为硬门。所有提供商都不可用时失败关闭，不把“未返回风险”当作绝对安全。

### Bluesky AppView

用途：少量查询词的公共帖子搜索。优先公共缓存端点，失败时回退主 AppView。由于部分 CDN/IP 可能返回 403，它始终是可选来源。

### Mastodon-compatible API

用途：用户指定实例的公开账号或标签端点。不同实例可能关闭匿名访问；较新的实时流接口通常需要用户令牌，因此默认轮询公开 JSON。

### RSS/Atom

用途：Google News、Reddit、YouTube、媒体、RSSHub/SearXNG 输出。解析器使用 Python 标准库，避免额外依赖。

## 浏览器登录态桥

不是通用“Cookie 爬虫”。它是本项目自有的 Chrome/Edge Manifest V3 扩展：

- 只在用户已经打开的公开页面读取 DOM；
- 不导出 Cookie；
- 不访问私信/设置路径；
- 只向 `127.0.0.1` 发送；
- 使用随机本地令牌；
- 消息队列持久化到扩展本地存储；
- 发送来源心跳，发现标签页冻结或 selector 失效。

这种方式比依赖长期不稳定的匿名 X 抓取器更适合已有登录账号的个人电脑，但仍需遵守各平台条款，页面改版后也需要维护 selector。

## 值得借鉴、暂不 vendoring 的项目

### slightlyuseless/memecoin-trading-bot

值得借鉴：

- 简单单进程配置；
- discovery / safety / strategy / position 分层；
- 短观察窗；
- 插件式策略；
- 自动退出。

不直接合并原因：Solana、TypeScript 和特定 RPC/交易执行依赖较重；本项目当前核心是事件证据与跨链 Paper，不是低延迟实盘 sniper。

### UselessParadox/meme-coins-analyzer

值得借鉴：多链、Launchpad、Smart Money、社交提醒的模块边界。

不直接合并原因：NestJS、PostgreSQL/TimescaleDB、Redis、Prometheus、Grafana、Docker 对个人电脑 MVP 过重；其中 Nitter/twscrape 路线稳定性和平台合规性也需要单独验证。

### MayurK-cmd/4Meme-Pilot

值得借鉴：Four.meme bonding curve、Holder/流动性、dry-run、决策日志。

不直接合并原因：依赖第三方社交情绪和 Gemini；项目的官方性、测试深度和交易合约调用需要独立审计。BSC Launchpad 可在后续从只读事件监听开始接入。

### hoodpumps/Grok-The-Trencher-4.5

值得借鉴：Pump 新币→DexScreener→多信号评分→持仓状态的流水线。

不直接合并原因：对每个新币调用商业模型会快速消耗额度；该路线也没有解决现实事件、历史首次可见时间和同名主盘问题。

### TrendRadar、DailyHotApi、TrendSonar、RSSHub、SearXNG

值得借鉴/可作本地 sidecar：

- 中文热榜；
- RSS 转换；
- 正文抽取；
- 新闻去重和事件聚类；
- 自建搜索。

当前不作为强依赖：生产重点是国际一手社交和链上新币；这些服务可通过现有 RSS/JSON/本地桥接入，无须把整个工程复制进来。

### PumpKit、Chainstack 等 Pump SDK/监听示例

值得借鉴：bonding curve、迁移状态、报价、事件结构和测试样例。

暂不合并真实交易：需要 RPC、交易构造、签名、优先费、失败恢复和小额链上验收；当前版本硬锁 Live。

## 明确拒绝

以下代码不进入主仓库：

- 刷量、假交易、多钱包伪造活跃度；
- 创建 Token 后诱导外部买家再砸盘；
- sandwich、抢跑或恶意 MEV；
- 编译二进制但不提供源码的所谓 sniper；
- 把私钥、助记词或浏览器 Cookie 上传到远端；
- 未说明许可证、只有几次提交、夸大“production ready”的仓库；
- 要求把 API Key/私钥写入源码的示例；
- 用后来上涨名单训练后再回测同一时期的代码。

## 依赖控制

当前运行时只强制依赖：

```text
httpx
websockets
```

原因：

- SQLite、RSS/XML、HTTP Bridge、状态机都使用标准库；
- 浏览器扩展无第三方 JavaScript；
- Agent 为可选本地命令；
- Telegram 自动监听不接入；仅保留人工来源目录；
- 未来接入真实链上执行时再单独增加链 SDK，不提前污染 Paper 核心。

## 采用判断标准

每个新资源需回答：

1. 是否免费或能在免费额度内长期运行？
2. 是否提供首次观察时间，还是只提供当前状态？
3. 能否离线保存原始响应？
4. 是否允许按候选调用，而非全量扫描？
5. 许可证是否允许使用？
6. 是否要求托管私钥？
7. 失败时能否降级？
8. 对“新闻↔Token”和“主叙事选择”提供了什么真实增量？
9. 是否会让个人电脑架构明显变复杂？
10. 能否写出无网络、无真实资金的测试？
