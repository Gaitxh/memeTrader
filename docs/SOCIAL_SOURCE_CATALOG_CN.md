# 社交信息源目录

`SOCIAL_SOURCE_CATALOG.json` 是 memeTrader 的公开社交信息源候选目录。当前 `v3` 版本在 2026-08-30 复核，共 82 条，覆盖 X、Truth Social、YouTube、Instagram、TikTok、Threads、Bluesky、Telegram 和 Reddit。文件只保存公开账号、公开 URL、实体映射、类别、优先级、观察轮换标签与非敏感自动化策略，不包含登录账号、密码、Cookie、会话、邮箱、API Key、Bot Token 或其他私密信息。

此目录是研究和采集入口，不会替代现有的时间门、安全门、候选币排序、`WAIT` 结论或 Paper 风控。账号进入目录也不表示其内容自动具备决策资格。

## 优先级

项目现有语义是 `5` 最高、`1` 最低，不能按常见的“1 最高”方式理解：

- `priority = 5`：机构、项目、媒体或官方组织的原始账号。具体帖子可按内容承担 `feature` 或 `confirmation`，但仍必须满足本地 `observed_at`、`ingested_at`、新鲜度和独立性要求。
- `priority = 4`：公众人物、创作者或高影响力原始账号。默认作为 `identity`；只有当该账号自己的帖子就是事件本身时，才能升级为 `feature`。
- `priority = 3`：当前目录暂未使用，留给经过验证但权威性低于官方源的专业或垂直来源。
- `priority = 2`：社区或 Meme 趋势源，只能用于发现线索和衡量注意力，不能单独作为交易决策证据。
- `priority = 1`：讽刺或高噪声发现源，只能用于发现，不得用于独立确认。The Onion 必须始终带有讽刺内容标记。

官方身份不等于 Token 关联。名人发布一句话只能证明该名人发布了内容，不能证明同名 Token 与该内容有关。Event→Token 或 Token→Event 仍需明确名称、CA、时间和独立来源证据。

## 关键观察频率

`watch_cadence = critical` 表示该账号应在浏览器观察清单和账号轮换中获得更短的回访间隔。当前只用于 Donald Trump、Elon Musk 和 CZ 三个高影响人物实体；Donald Trump 的 X 与 Truth Social 是同一实体的两个观察入口，因此共有 4 个 critical 账号。运行时和 Settings 都把 critical 上限固定为 4；更多账号会回到常规候选池。

这个字段只影响**观察轮换优先级**，不是权威度或交易信号。它不会改变 `priority`、帖子角色（`feature`、`confirmation`、`identity`、`promotion`）、新鲜度时间门、来源独立性、Event→Token 关联要求或决策资格，也不能让一条内容绕过 `WAIT`、安全检查和 Paper 风控。JSON 顶层的 `watch_cadence_policy` 以机器可读方式固定这些否定语义。

## 跨平台去重

同一实体在不同平台上的账号必须归并为一个来源实体。例如 NASA 在 X、YouTube、Instagram、TikTok 和 Threads 上的内容仍然属于同一个 NASA，不能把五个平台计算成五个独立来源。Donald Trump 的 X 与 Truth Social 均使用 `entity_id = donald_trump`，也只能计算为一个发布实体；个人实体 `donald_trump` 与机构实体 `white_house` 必须保持独立，不能因为任职关系合并。Reuters、AP、OpenAI、NVIDIA、MrBeast 等跨平台账号同理。

每条记录现在都带有稳定的 `entity_id`。同一组织或人物的跨平台账号共用同一个值；平台特有社区保持独立，例如 `r/solana` 使用 `reddit_solana_community`，不能与 Solana 自己的账号合并。计算 `source_count`、独立确认数量和可信度时应按 `entity_id` 去重。跨平台转发、同文案同步发布或媒体自身的二次剪辑也不能增加独立来源数。

`entity_id` 只解决“这些账号是否属于同一个发布实体”的独立来源去重问题，**不是权威度、官方身份、真实性或决策资格信号**。这些维度仍由账号核验、具体帖子角色、时间门和独立证据分别决定；不能因为两个账号共享或拥有一个 `entity_id` 就提高分数。

目录记录只有在用户导入本机观察清单、浏览器采集时精确匹配平台与 handle、并由 Runtime 用同一清单再次核验后，才会把 `entity_id` 写入该条 observation。旧 observation、没有 `entity_id` 的用户自定义账号、未精确匹配的显示名继续按原始 `platform:handle` 计算来源，系统不会依据新版目录追溯改写历史来源数。

JSON 顶层的 `entity_id_policy` 用机器可读方式固定上述语义。`catalog_version = 3` 表示所有记录都必须具有非空 `entity_id`，并允许用受约束的 `watch_cadence` 字段调整观察轮换。后续改名时也应保留原实体标识，除非有证据证明账号所有者已经改变。

## Telegram 自动化策略

Telegram 在本目录中只作为可点击的人工发现目录，不是默认自动采集器。顶层 `platform_automation_defaults.telegram` 与每条 Telegram 记录的 `automation` 都明确设置：

- `access_mode = manual_discovery_only`；
- `automated_capture_enabled = false`；
- `agent_processing_enabled = false`；
- `decision_eligibility = discovery_only`。

Telegram 条目还保存 `owner_verification` 和 `preferred_machine_source`。前者记录当前用于核对账号所有者的公开入口；后者优先指向发布者自己的官网、公告页或 feed。用户可点击 `t.me` 入口人工发现线索，但自动化应读取允许机器访问的首选官网来源，并回到原始公告或链上证据。目录本身不授权抓取 Telegram、保存全文或把帖子交给 Agent。

本次复核保留 Binance 公告目录，并用 Solana 官网当前明确链接的 `@solana` 取代缺少本轮所有者核验记录的 `@durov` 种子。两条均关闭自动抓取。完整的条款边界、核验依据、禁用候选与推荐替代来源见 [Telegram 信息源、搜索机器人与采集方案调研](TELEGRAM_SOURCE_RESEARCH_20260830_CN.md)。

## 登录与公开访问现实

- X、Instagram、TikTok 和 Threads 对未登录访问、连续浏览和自动化观察限制较多。可靠采集通常需要用户自己保持登录的本机浏览器会话，并通过现有浏览器桥观察公开页面。
- YouTube、Bluesky 和 Reddit 通常能提供较好的公开访问退路，但仍可能出现地区限制、同意页、限频或临时失败。Telegram 即使存在公开预览也只作人工目录；公开可读不等于允许自动抓取、聚合或用于 Agent。
- 登录材料只能留在浏览器或本机忽略的数据目录中，不得写入本目录、`config.json`、日志、SQLite 或 Git。
- 采集失败应记录为 source health 降级，不能把“未取到数据”解释成“没有热点”，也不能把安全服务缺失解释成安全。

## 使用建议

目录不要求每轮同时扫描全部 82 条。可按平台、类别和优先级轮换：先为 `watch_cadence = critical` 的账号保留更短回访间隔，再优先观察 `priority = 5`，为其他 `priority = 4` 账号保留名人、体育和创作者通道，低频使用 `priority = 1–2` 做趋势发现。账号权威度、帖子实时热度、内容角色和来源独立性应分别保存，不应合成一个模糊的“可信度”数字。

建议事件详情保留原帖永久链接、平台、作者、发布时间、本地首次观察时间、抓取时间和角色，并明确展示该证据是 `feature`、`confirmation`、`identity` 还是 `promotion`。

## 主要官方复核入口

- [Donald J. Trump 的 X 账号](https://x.com/realDonaldTrump)
- [Donald J. Trump 的 Truth Social 账号](https://truthsocial.com/@realDonaldTrump)
- [NASA 官方社交账号目录](https://www.nasa.gov/social-media/)
- [OpenAI 官方账号验证清单](https://help.openai.com/en/articles/11725090)
- [AP 官方社交数据](https://www.ap.org/about/annual-report/2025-letter-from-the-chair-and-ceo/2025-ap-by-the-numbers/)
- [Bloomberg 官方社交入口](https://www.bloomberg.com/company/press-contacts/)
- [Solana 官方社区与 Telegram 入口](https://solana.com/community)
- [Binance 官方账号验证工具](https://www.binance.com/en/official-verification)
- [Ethereum 官方社区目录](https://ethereum.org/community/online/)
- [Phantom 官方频道安全说明](https://help.phantom.com/hc/en-us/articles/40411433367187-Phantom-will-never-DM-email-or-ask-you-to-send-funds)
- [Uniswap Labs 官方链接](https://support.uniswap.org/hc/en-us/articles/17522892515341-Official-Uniswap-Labs-links)
- [联合国官方社交目录](https://www.un.org/en/get-involved/social-media)
- [美国国家气象局官方 X 账号目录](https://www.weather.gov/nws_x)
- [Guinness World Records 官方社交目录](https://www.guinnessworldrecords.com/news/social)

账号和平台可能改名、迁移或停止更新。目录版本升级时应重新从官方站点或自认证域名账号复核，不应根据搜索结果中的相似头像或名称猜测账号。
