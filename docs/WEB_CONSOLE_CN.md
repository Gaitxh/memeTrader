# memeTrader 本机 Web 控制台

Web 控制台是现有 memeTrader Runtime 与 SQLite 的观察、审计和安全配置界面。它不复制策略、不生成演示交易，也不接触钱包或真实资金。

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
    ├── public_access_token.txt      公开入口随机口令；只留在本机
    └── PUBLIC_ACCESS.txt            临时公开 URL 与本机登录提示
```

`data/`、`config.json`、数据库、日志、会话和访问口令都被 Git 忽略。

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

## 页面与信息语义

- **Overview**：Paper/Live 锁、机器人/计划任务、SQLite、浏览器桥、资金、权益、当日 exposure、开放仓位和数据总量。
- **Live Events**：attention、独立来源数、freshness、来源角色、资格状态和原始链接。
- **Token Discovery**：chain、CA、创建/首次观察、流动性、5m 量、买卖笔数、momentum 和双向证据链。
- **Decisions**：事件、候选结果、match/candidate score、canonical margin、WAIT/CANDIDATE/REJECT、仓位金额与拒绝原因。
- **Paper Portfolio**：所有金额和 PNL 均明确为 Paper/模拟；展示止损、分批止盈、移动退出和叙事衰减状态。
- **Agent Operations**：本机 Codex CLI 的模型、推理强度、回退、调用次数、tokens、预算、上次结果和下一次到期时间。
- **Sources**：静态/动态 RSS、浏览器、PumpPortal、新池、报价和安全来源的健康、产出时间、暂停原因。
- **Audit**：r5 false-positive 排除、r6 Starlink 过期反查证据、future-data rejection 和决策时刻证据资格。
- **Settings**：仅编辑安全白名单参数、平台观察偏好、公开账号/名人清单和主题；Live 永久不可用。

四类来源必须始终分开：

- `feature`：通过时间门后才可成为事件特征；
- `confirmation`：独立确认，不等同买入信号；
- `identity`：身份上下文，不增加注意力、不能单独触发；
- `promotion`：推广材料，只存档、不参与触发。

每条证据还单独显示 decision eligibility。角色本身不代表它在某个决策时刻一定合格。

`WAIT` 的固定含义是“未形成交易信号”，不能被渲染成机会、买入或看涨提示。`CANDIDATE` 只表示通过候选门槛，后续仍受安全、仓位和 Paper 执行约束。

## 平台与公开账号观察清单

控制台保存的账号清单只允许：

- 平台；
- 公开显示名或 handle；
- 公开主页 URL；
- 优先级；
- 是否启用。

它绝不保存平台用户名、密码、Cookie、Session、验证码或私信。X、Truth Social、Bluesky、Reddit、Threads、Instagram、TikTok、YouTube 与 Telegram 网页仍由用户在本机浏览器中登录并实际打开；扩展只读取已加载的公开页面。

“加入观察清单”不等于页面正在采集。需要浏览器页面的平台会显示 `Open page required` 和最近浏览器心跳。

## Agent 额度

自主搜索继续通过本机 `codex` 命令使用这台电脑已经登录的 Codex/ChatGPT agentic 额度，不使用 OpenAI API Key。Web API 不读取或返回 Codex 登录文件。

项目默认最多两个并发 Agent 槽位；Settings 只允许 `1–2`，默认 `2`。这是并发上限，不是永久运行的进程数量。调用次数与 token 预算的修改不会重置当日已使用量。

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
- 钱包、私钥、助记词、Broker；
- `bridge.token`；
- 通知 token、Chat ID、Cookie、Session；
- 任意 API Key、密码或验证码；
- 通用 JSON 配置编辑器。

默认 HTTP 服务只允许 loopback。非 loopback 绑定必须同时配置访问口令，否则启动失败。
