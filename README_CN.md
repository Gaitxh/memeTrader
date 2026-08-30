# memeTrader 0.6.1：个人电脑上的自主信息源 Meme 机器人

`memeTrader` 常驻运行在普通 Windows 电脑上，目标不是全网毫秒级抢跑，而是以现实可行的**几十秒到几分钟**速度完成：

```text
国际社交/新闻/社区出现新事件          Pump/新池先出现 Token
             ↓                              ↓
        事件 → 找币                    Token → 反查事件
             └────────── 双向汇合 ──────────┘
                              ↓
              主叙事币识别 + 链上动量 + 安全门槛
                              ↓
                 Shadow / Paper 自主买入与仓位
                              ↓
          持续报价 → 止损 / 分批止盈 / 移动止盈 / 到期退出
```

项目刻意保持简单：**一个 Python 进程、一个 SQLite 数据库、一个 JSON 配置、一个可选浏览器扩展**。默认不调用付费 API；会启用有严格频率和额度上限的自主搜索 Agent，但交易语义平局 Agent 默认关闭，系统不接触真实资金。

## 关键规则

- 生产运行只使用本机从现在开始记录的 `observed_at`。
- 网页声称的 `published_at` 不能倒推为“机器人当时已经看到”。
- 首次轮询或首次打开页面时发现的旧内容会保留为 `identity` 资料，但注意力记为 0，不能触发买入。
- PNUT、TRUMP、MOODENG、LUCE、Broccoli、TST 等历史案例只测试匹配、主盘选择、等待和未来信息隔离；不会加载为生产别名、阈值或赢家先验。
- 只有 Token/价格拉升、还没有独立新闻、社交或官方触发时，机器人只观察，不买入。
- 当前 Live 模式在代码层锁死，只支持 Shadow/Paper。

## 免费信息源

### 快车道

1. **登录态浏览器扩展**：被动读取你已打开页面中新渲染的公开帖子，支持 X、Truth Social、Bluesky、Reddit、Threads、Instagram、TikTok、YouTube 和 `t.me` 公开频道页。
2. **PumpPortal 免费 WebSocket**：只订阅新 Token 和迁移事件，不使用付费交易流。
3. **GeckoTerminal 新池**：分钟级发现 Solana、BSC 新池。

### 候选确认

- DexScreener：关键词找币、按 CA 报价、流动性、成交和买卖方向。
- GoPlus + Honeypot.is：EVM/BSC 候选的合约权限、可卖性、税率和 honeypot 交叉检查。默认至少要求一个 EVM 安全报告；显式要求交易模拟时 Honeypot.is 仍是硬门。
- GoPlus + RugCheck：Solana 候选的权限和风险交叉检查，默认至少要求一个报告可用。
- CoinDesk、Cointelegraph、BBC、Google News 专题 RSS 与 Mastodon 公共时间线：补足国际事件证据。
- Token→新闻反查只处理名称足够独特且已有真实流动性/成交动量的 Token；名称命中后仍要求独立来源确认，避免把 `Gang`、`Bees` 之类通用名称连接到无关新闻。

Bluesky 公共搜索接口在部分网络会返回 403。本机配置遇到这种情况时应关闭 API 轮询，继续通过已登录浏览器页面采集，不让常驻进程反复报错。

浏览器扩展不读取 Cookie、密码、私信或浏览器历史，不自动滚动、点赞、发帖或登录。它只能看到实际打开并加载的公开页面。因此实际使用时，建议常驻少量高价值页面：名人/项目官方账号、X Lists、Truth Social 账号页、Reddit/Bluesky 重点社区、公共 Telegram 频道页。

## Windows 安装

```powershell
Set-Location E:\memeTrader
powershell -ExecutionPolicy Bypass -File .\scripts\install_windows.ps1
```

安装脚本会建立 `.venv`、安装项目和测试依赖，并在缺少 `config.json` 时生成一个带随机本地桥令牌的配置。

运行测试：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run_tests.ps1
```

检查本机配置和免费端点：

```powershell
.\.venv\Scripts\python.exe -m memetrader doctor --config config.json --online
```

运行一次采集：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run_once.ps1
```

安装为当前 Windows 用户登录后启动的单一计划任务，并立即启动常驻 Paper：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\install_scheduled_task.ps1
```

兼容入口 `install_startup.ps1` 会调用同一个计划任务安装器。`run_paper.ps1` 以前台附着方式监督 Python；子进程异常退出后会等待 5 秒重启。计划任务使用 `IgnoreNew`，程序内部仍有文件锁，因此不会同时运行两个交易实例。运行日志位于 `data\logs`。

仅手工前台启动：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run_paper.ps1
```

移除计划任务并停止机器人：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\remove_scheduled_task.ps1
```

兼容入口 `remove_startup.ps1` 会调用同一个移除脚本。

查看事件、决策、仓位和成交：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\status.ps1
```

## 浏览器扩展

1. 先启动机器人；
2. Chrome/Edge → 扩展管理 → 开发人员模式 → “加载已解压的扩展”；
3. 选择 `E:\memeTrader\browser-extension`；
4. 在扩展选项中填入 `config.json` 内的 `bridge.token`；
5. 打开需要长期观察的公开页面。

扩展把待发送帖子保存在 `chrome.storage.local`。浏览器 Service Worker 休眠或机器人短暂离线时，队列不会立刻丢失；恢复后会补发。扩展每 30 秒发送页面心跳。

## 机器人怎样买入

买入必须同时满足：

1. 有独立社交、新闻或官方事件；
2. 找到匹配 Token；
3. 同事件第一名超过最低分，并明显领先第二名；
4. 报价、流动性和近期交易可用；
5. 合约/税率/可卖性等硬门槛通过；
6. 账户、持仓数和流动性冲击允许。

仓位由本地公式决定：账户风险预算、止损距离、机会分数、单币上限、现金和流动性冲击上限取最小值。Agent 无权改写金额或绕过风控。

## 机器人怎样卖出

当前 Paper 退出包括：

- 硬止损；
- 四档分批止盈；
- 从峰值回撤后的移动退出；
- 流动性快速恶化或安全状态恶化时退出；
- 叙事长期没有新增证据且链上买盘转弱时退出；
- 最大持仓时间退出。

买入侧限额不会阻止已有仓位卖出。

## Codex / GPT 自主搜索

`autonomous_search.enabled=true` 时，机器人会自己完成三类工作，不要求用户事先列完信息源：

1. 主动搜索近两小时内正在加速的国际热点、名人、动物、网络文化、体育、AI、游戏和 Crypto 社区事件；
2. 定期寻找并实际验证新的免费 RSS/Atom 信息源，通过后自动加入动态源注册表；
3. 对链上动量足够强的新 Token 反向搜索现实事件，并要求至少两个独立可访问来源。

默认最多同时运行 2 个搜索 Agent 槽位。全球快搜和搜源优先使用 Spark/low，额度不可用时回退 Luna/low；复杂 Token 身份核验使用 Luna/low，必要时才升级 Terra/medium，Sol/medium 仅作为最后回退。普通状态每 12 分钟快搜一次，并轮换覆盖 5 个主题中的 3 个；重大信号期间每 3 分钟覆盖全部主题，连续三次空结果退到 30 分钟。Spark 不可用或单次调用超过 18,000 tokens 时，普通状态最短间隔自动拉长到 30 分钟，重大信号仍保留 10 分钟级回退。Token 专项 Agent 受 5 分钟全局冷却、240 分钟同 Token 冷却和动量分≥80 的限制；失败时仅进入 10 分钟短退避。调用次数、已使用 token 和下一次调用预留量共同限制预算，`--force` 也不能越过预算。自动发现的 RSS 连续 3 次失败，或近期内容至少一半是 Market Wrap、价格更新、Presale、Top/Best/100x 榜单时，会自动暂停并由后续搜源补充。全部频率、并发、模型、推理强度和上限都可在 `config.json -> autonomous_search` 修改。

常规计算、去重、时间判断、评分、仓位和卖出仍全部由本地代码完成。四字母短名称可以触发 Agent 搜证，但不能只靠文字重合直接连接新闻；证据不足时返回 `WAIT`。EVM 使用 GoPlus/Honeypot.is、Solana 使用 GoPlus/RugCheck：每个链族默认至少要有一个外部安全报告，两者都不可用时失败关闭；缺失结果不会被当作安全。语义平局 Agent 的 `agent.enabled` 继续默认关闭。

查看自主搜索状态：

```powershell
.\.venv\Scripts\python.exe -m memetrader status --config config.json --limit 10
```

手工诊断命令（常驻运行无需手工执行）：

```powershell
.\.venv\Scripts\python.exe -m memetrader scout-trends --config config.json --force
.\.venv\Scripts\python.exe -m memetrader discover-sources --config config.json --force
```

完整说明见 [docs/AUTONOMOUS_SEARCH_CN.md](docs/AUTONOMOUS_SEARCH_CN.md)。所有搜索 Agent 使用 ephemeral、只读沙箱，不接触钱包、Broker、私钥或项目写权限。

## 历史测试与未来信息隔离

```powershell
.\.venv\Scripts\python.exe -m memetrader replay examples\historical\temporal_guard.synthetic.json --decision-at 2026-01-01T00:05:00Z
```

该回放只验证：决策时刻之前真正观察到的证据可用；之后的交易所上线、最高价、最终赢家和收益等必须拒绝。真正检验收益只能依赖从现在开始积累的 Forward Shadow/Paper 日志。
