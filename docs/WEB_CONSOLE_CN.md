# memeTrader 本机 Web 控制台

Web 控制台是现有 memeTrader Runtime 与 SQLite 的观察、审计和安全配置界面。它不复制策略、不生成演示交易。常驻策略保持 Paper；另设与策略隔离的 Solana Devnet 真链测试页，Mainnet 永久锁定。

顶部提供“中文 / English”即时切换。语言偏好只保存在浏览器 `localStorage`，不会写入机器人配置或发送到外部服务；事件、Token 与来源的原始文本保持原文。

界面所有工作区都会动态更新当前页：Overview 约 10 秒、Live Events 约 12 秒、Token/Decisions/Paper Portfolio/Wallet 约 15 秒、Agent Operations/Sources 约 20 秒、Audit 约 30 秒、Settings 约 60 秒。页面隐藏、存在未保存设置或正在编辑钱包时会暂停自动请求；重新回到页面时立即刷新。当前实现是对本机 API 的低成本轮询，不需要新增 WebSocket、Redis 或消息队列；右上角的刷新时间每秒更新显示，但只有实际 API 请求才改变数据快照。

## 数据仍保存在本机

权威运行数据继续保存在 `config.json -> database` 指定的 SQLite 文件中。Web 层用短连接和只读查询访问 WAL 数据库，不会清空、迁移或回写 r5/r6 历史证据。

本机目录分工：

```text
data/
├── memetrader_forward_*.sqlite3     事件、Token、决策、Paper 仓位与成交
├── notifications.jsonl             结构化运行通知
├── logs/                            机器人、Web 与公开隧道日志
└── web_console/
    ├── console_settings.json        平台、公开账号和主题观察偏好
    ├── wallet.dpapi                 当前 Windows 用户 DPAPI 加密的 Devnet 私钥
    ├── wallet.json                  不含私钥的 Devnet 钱包元数据
    ├── devnet_transactions.jsonl    脱敏的 Devnet 操作与回执
    ├── public_access_token.txt      公开入口随机口令；只留在本机
    └── PUBLIC_ACCESS.txt            临时公开 URL 与本机登录提示
```

`data/`、`config.json`、数据库、日志、会话和访问口令都被 Git 忽略。

不含敏感信息的长期产品上下文保存在版本控制内的 [PROJECT_CONTEXT/START_HERE.md](PROJECT_CONTEXT/START_HERE.md) 及其配套文档。它用于跨聊天窗口延续需求、架构、安全边界、操作和验收背景，但不能代替当前代码、本机配置、SQLite 或 `/api/health` 的运行事实。

## 本机启动

双击：

```text
E:\memeTrader\OPEN_WEB_CONSOLE.cmd
```

或运行：

```powershell
Set-Location E:\memeTrader
powershell -ExecutionPolicy Bypass -File .\scripts\open_web_console.ps1
```

本机地址：

```text
http://127.0.0.1:8787/
```

启动脚本先检查现有 Web 进程，已有实例时直接复用。它只启动控制台，不会启动第二个交易机器人。

## 受保护的公开 HTTPS 地址

双击：

```text
E:\memeTrader\SHARE_WEB_CONSOLE.cmd
```

控制台后端仍只监听 `127.0.0.1:8788`；已安装的 `cloudflared` 在它前面建立 Cloudflare Quick Tunnel，不开放路由器入站端口。公开入口强制随机访问口令，口令不进入 URL、API、日志或 Git。

脚本会：

1. 生成或复用本机随机访问口令；
2. 启动带鉴权的独立 Web 入口；
3. 建立临时 `https://*.trycloudflare.com` 地址；
4. 在本机 `data\web_console\PUBLIC_ACCESS.txt` 保存地址和登录提示；
5. 打开公开页面和本机登录提示文件。

隧道存在时，Settings 的 **Access & storage** 也会显示可点击的公开地址，但不会显示用户名、口令或口令文件路径。

Quick Tunnel 地址在隧道重建后会变化，适合个人临时远程查看，不是有 SLA 的固定域名。固定域名应使用用户自己的 Cloudflare Tunnel 与 Access 策略，仍只把流量转到 loopback Web 入口。

公开 URL 通过随机口令保护，可读取控制台数据并修改后端明确列入白名单的安全 Settings。钱包区域始终是脱敏只读视图：不能录入或删除私钥、申请 Devnet 测试币、发起交易。所有钱包变更接口还会在服务端验证 loopback 来源，不能靠修改网页绕过。

## 页面与信息语义

- **Overview**：Paper/Live 锁、机器人/计划任务、SQLite、浏览器桥、资金、权益、当日 exposure、开放仓位和数据总量；顶部另有由 SQLite 真实写入驱动的信息/Token 双通道采集脉冲。
- **Live Events**：attention、独立来源数、freshness、来源角色、资格状态和原始链接，并显示平台、发布者和可验证的影响力维度。
- **Token Discovery**：chain、CA、创建/首次观察、流动性、5m 量、买卖笔数、momentum、双向证据链，以及 Dex/Profile 项目附带链接的独立发现种子面板。
- **Decisions**：事件、候选结果、match/candidate score、canonical margin、WAIT/CANDIDATE/REJECT、仓位金额与拒绝原因。
- **Paper Portfolio**：所有金额和 PNL 均明确为 Paper/模拟；展示止损、分批止盈、移动退出和叙事衰减状态。
- **Agent Operations**：本机 Codex CLI 的模型、推理强度、回退、调用次数、tokens、预算、上次结果和下一次到期时间。
- **Sources**：静态/动态 RSS、浏览器、PumpPortal、新池、Dex Profile/CTO/Ads/Boost、报价和安全来源的健康、产出时间、暂停原因；同时显示主题通道与具体账号的真实暴露/空结果、事件固定时点随访，以及只影响账号观察轮换的前向来源学习。
- **Audit**：r5 false-positive 排除、r6 Starlink 过期反查证据、future-data rejection 和决策时刻证据资格。
- **Settings**：仅编辑安全白名单参数、平台观察偏好、公开账号/名人清单和主题；Live 永久不可用。
- **Wallet**：本机查看 Devnet 地址、SOL/SPL 余额、近期交易与回执，人工申请测试币或发送限额 Devnet 测试交易；不连接常驻策略。

四类来源必须始终分开：

- `feature`：通过时间门后才可成为事件特征；
- `confirmation`：独立确认，不等同买入信号；
- `identity`：身份上下文，不增加注意力、不能单独触发；
- `promotion`：推广材料，只存档、不参与触发。

每条证据还单独显示 decision eligibility。角色本身不代表它在某个决策时刻一定合格。

Overview 的采集脉冲完全由已持久化数据计算。信息通道统计新闻、社交、浏览器和 Agent observation；Token 通道分别统计新 Token 与 snapshot 更新。每条通道显示最近 60 秒计数、5 分钟每分钟写入率、最近写入时间和 `active / waiting / stale` 状态。只有近期确有 SQLite 写入时动画才运行；页面计时、计划任务存在或浏览器打开本身都不会伪造 active。

事件详情中的“来源排名”依次考虑：当时决策用途、已知权威层级、来源角色、新鲜度、是否有可访问原始链接以及页面上可观察到的热度。每条来源独立展示平台、发布者、账号类型、官方/认证状态、已知关注者或覆盖、可见互动和本地策展优先级；没有证据的字段显示为“未知”，不能根据显示名或平台猜测。这个顺序只表示**证据优先级**，方便先审查最相关材料；它不是“权威真值排名”，也不会自动证明来源内容真实。`feature/confirmation` 与 `identity/promotion` 分组展示，后者明确为仅上下文；高影响力账号也不能让 identity/promotion 单独成为交易依据。全部来源仍可展开查看原始链接、发布时间、本机观察/入库时间、角色与时间线。

Token 详情把 DexScreener Profile、Community Takeover、Ads、Boost 和 pair info 的链接显示为“发现种子”。每条保留发现面、`identity/promotion`、平台、链接类型、提供方状态及本机首次/最后观察。`provider_metadata` 不等于 verified；Ads/Boost 永久是 promotion。下方事件时间线的准确标题是“已关联观察”，不是“已验证证据”。

Sources 的学习表按平台、信息类型、具体来源、已持久化人物实体和事件/热点类型显示前向统计。事件类型只在首次接受时冻结，旧数据保持 `unknown`，且当前永远只观察。早期证据、合格证据和候选关联只作描述；没有已平仓 Paper 时胜率/回报显示 `—`。满足多结果、多天和亏损多样性门槛的平台/来源/实体标签只成为联合策略的次级验证，不能单独改变轮换。12 个候选观察槽位中至少 40% 保留探索，critical 最多 4 个。学习不改变证据权重、WAIT/CANDIDATE、canonical margin、安全门或仓位。

同页的“主题通道覆盖与影子学习”固定展示五个版本化通道。完成轮、失败轮、空结果、事件产出和最近选择来自追加式 SQLite 暴露账本；没有运行时显示“尚未观察”，不会把它画成 0% 表现。Paper 结果只有在完全平仓后才显示为条件历史。主题学习不改变实际 round-robin；即使样本成熟，也只产生人工审查用影子候选。

“账号选择性关注策略”按平台和 handle 显示完成/总暴露、失败、运行日、精确原帖命中、零产出、60 分钟市场随访、建议倍率与实际倍率。命中必须来自本轮合格事件中能精确匹配该账号 URL 路径的公开帖子；转述或同名不会归因。账号暴露门和 WAIT/CANDIDATE 60 分钟人物/平台随访门共同成熟后，普通账号才可在 `0.80×–1.20×` 内改变观察轮换；Paper 结果只是次级验证，critical 固定且探索槽位不少于 40%。

“事件影子市场随访”把首次具备 Token/价格的 WAIT 与 CANDIDATE 一并纳入，显示 15/60/240 分钟的事件数、事件日、正向延续、平均原始回报和区间最高/最低回报。页面明确区分 pending、complete 与 missing；没有结果时显示等待真实快照，不生成 0% 或演示数据。这不是 Paper PNL 或交易信号；只有成熟的 60 分钟人物/平台结果能与成熟账号暴露共同约束观察轮换。

`WAIT` 的固定含义是“未形成交易信号”，不能被渲染成机会、买入或看涨提示。`CANDIDATE` 只表示通过候选门槛，后续仍受安全、仓位和 Paper 执行约束。

## 平台与公开账号观察清单

版本控制内的 [SOCIAL_SOURCE_CATALOG.json](SOCIAL_SOURCE_CATALOG.json) 提供 82 条经过人工复核的公开候选种子，覆盖 X、Truth Social、YouTube、Instagram、TikTok、Threads、Bluesky、Telegram 和 Reddit；分类、优先级、权威语义和跨平台实体去重见 [SOCIAL_SOURCE_CATALOG_CN.md](SOCIAL_SOURCE_CATALOG_CN.md)。目录不包含任何登录身份，也不会自动等于“当前正在采集”。用户导入或选择后，当前观察清单保存在 Git 忽略的 `data/web_console/console_settings.json`，可以按本机需要增删、停用并与目录版本保持不同。每轮 Agent 只从启用清单中选择少量 critical、策展和探索账号，不会同时扫描全部 82 条。

控制台保存的账号清单只允许：

- 平台；
- 公开显示名或 handle；
- 可选的稳定 `entity_id`（仅允许 1–64 位小写字母、数字、`_`、`-`；空值表示未知）；
- 公开主页 URL；
- 优先级；
- 是否启用；
- `normal/critical` 观察轮换标签；critical 最多 4 个，只保留观察槽位。

它绝不保存平台用户名、密码、Cookie、Session、验证码或私信。X、Truth Social、Bluesky、Reddit、Threads、Instagram、TikTok 与 YouTube 的登录只发生在专用的本机 Chrome/Edge 配置中；扩展只读取已经加载的公开页面。Telegram 在设置页固定为 `manual_directory_only`，其页面正文不由扩展读取、入库或送入 Agent。项目和 Agent 不读取、导出或持久化浏览器凭据。登录失败、要求人工验证或不值得继续的平台直接跳过，Sources 如实标记降级，并继续使用公开页面、RSS、Agent 搜索及其他可访问来源，不让单个平台阻塞整套系统。

“加入观察清单”不等于页面正在采集。需要浏览器页面的平台会显示 `Open page required` 和最近浏览器心跳。

浏览器扩展只有在“平台 + 作者 handle”与已启用观察项精确匹配时，才随观察发送该项的 `entity_id`；Runtime 会再次读取本机观察清单核对，并丢弃客户端自报、格式非法、账号不匹配或清单中不存在的值。被接受的值随当次 observation 持久化，策略只按这个历史值合并独立来源。显示名、粉丝数和今天的目录都不会被用来猜测实体，也不会回写或改算旧决策。

## Agent 额度

自主搜索继续通过本机 `codex` 命令使用这台电脑已经登录的 Codex/ChatGPT agentic 额度，不使用 OpenAI API Key。Web API 不读取或返回 Codex 登录文件。

界面将工作分为 6 个逻辑角色：News Radar（新闻热点）、Social Pulse（舆论热度）、Named Account Watch（名人/指定账号）、Evidence Verifier（独立证据核验）、Token Context（Token 反查事件）和 Source Discovery（新来源发现）。这些是共享队列中的职责，不是 6 个永久进程。

项目默认最多两个并发 Agent 槽位；6 个逻辑角色共同共享该上限。Settings 只允许 `1–2`，默认 `2`。调用次数与 token 预算的修改不会重置当日已使用量。

不同复杂度采用固定路由：高频整理与普通热点侦察优先 Spark/low，失败时 Luna/low；Token Context 优先 Luna/low，复杂核验再回退 Terra/medium，Sol/medium 只作最后回退。来源学习、URL 分类、去重、时间判断、轮换、评分和 Paper 风控全部在本地确定性执行，不为这些工作调用 Agent。

每次 Agent 尝试都会记录安全的用量账本；Agent Operations 按任务、模型与推理强度分别汇总调用次数、输入 token、缓存输入 token、输出 token、推理 token、回退结果和当日/七日预算。账本不保存 prompt、stderr、Codex 登录材料或任何 secret。

源码示例仍保留面向普通电脑的保守默认值；本机 2026-08-30 已通过安全 Settings 应用一个适度加快的运行配置：

| 项目 | 源码示例默认 | 当前本机运行值 |
|---|---:|---:|
| 主采集轮询 | 60 秒 | 45 秒 |
| Token 反向新闻 | 45 秒 | 30 秒 |
| Trend Scout 普通 / 热点 / 空结果退避 | 12 / 3 / 30 分钟 | 8 / 3 / 20 分钟 |
| Source Discovery | 24 小时 | 12 小时 |
| Token Context 全局 / 同 Token 冷却 | 5 / 240 分钟 | 4 / 180 分钟 |

本机运行值保存在 Git 忽略的 `config.json`，不会反向修改仓库中的默认值；实际值应以 Settings/API 读取结果为准。Runtime 设置保存后需要安全重启单一常驻任务才生效。无论额度或频率怎样调整，并发仍限制为最多 2 个 Agent 子进程。

## Paper、Devnet 与 Mainnet 边界

- **Paper**：唯一的常驻自动策略执行模式，持续记录模拟持仓、退出和 PNL；所有收益均标为 Paper，不冒充真实利润。
- **Devnet 真链测试**：只允许用户在本机 Wallet 页人工操作 Solana Devnet，使用固定 Devnet RPC、金额上限和确认短语；它不会启用自动策略。
- **Mainnet Live**：永久锁定，没有网页开启接口；保存 Devnet 私钥不会改变 `mode` 或 `live.enabled=false`。

Wallet 只在回环地址接受私钥。私钥不会回显、不会进入 URL、浏览器存储、SQLite、日志或 Git；它仅通过当前 Windows 用户的 DPAPI 加密后写入 `data\web_console\wallet.dpapi`，通常只有同一台电脑上的同一 Windows 用户可以解密。公开 URL 只返回脱敏地址和只读状态。

2026-08-30 的真实 Devnet 验证中，钱包连接与集群身份校验成功，但官方 faucet 返回 RPC unavailable，因而没有测试 SOL、没有发送交易，也没有公开 signature；详见 [WALLET_DEVNET_VALIDATION_20260830.md](WALLET_DEVNET_VALIDATION_20260830.md)。这项外部阻塞不会被写成交易成功。

## 可修改与不可修改

安全白名单包括：

- RSS/新池、事件、持仓和健康检查频率；
- Trend Scout、Source Discovery、Token Context 的周期和预算；
- Agent 并发槽位 `1–2`；
- 事件、候选、匹配、安全和 Paper 风控阈值；
- 平台开关、公开账号/名人和主题观察偏好。

Runtime 配置保存后返回 `restart_required=true`，常驻机器人在下次安全重启后采用新值。平台/账号界面偏好保存到本地 Web 文件，可立即显示。

下列内容没有网页编辑接口，也不会出现在 API 响应中：

- `live.enabled`、`mode=live`；
- Mainnet 钱包、助记词、Broker，以及任何 Live 交易开关；
- `bridge.token`；
- 通知 token、Chat ID、Cookie、Session；
- 任意 API Key、密码或验证码；
- 通用 JSON 配置编辑器。

默认 HTTP 服务只允许 loopback。非 loopback 绑定必须同时配置访问口令，否则启动失败。
