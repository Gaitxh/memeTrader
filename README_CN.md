# memeTrader 0.5：个人电脑上的事件驱动 Meme 机器人

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

项目刻意保持简单：**一个 Python 进程、一个 SQLite 数据库、一个 JSON 配置、一个可选浏览器扩展**。默认不调用付费 API、不使用 Agent、不接触真实资金。

## 关键规则

- 生产运行只使用本机从现在开始记录的 `observed_at`。
- 网页声称的 `published_at` 不能倒推为“机器人当时已经看到”。
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
- Honeypot.is：EVM/BSC 候选的可卖性、税率和 honeypot 模拟。
- Bluesky 公共搜索、Mastodon 公共接口、RSS/Google News：补足事件证据与 Token 反向新闻搜索。

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
- 最大持仓时间退出。

买入侧限额不会阻止已有仓位卖出。

## Codex / GPT

默认 `agent.enabled=false`。常规计算、去重、时间判断、评分、仓位和卖出全部由本地代码完成。

只有前两名主叙事币接近、文化梗/谐音难以判断时，才允许低额度调用已登录的 Codex CLI。调用使用 ephemeral 会话、read-only sandbox、Low/Medium 日额度；没有钱包、Broker 或私钥访问。失败时自动退回本地规则。

## 历史测试与未来信息隔离

```powershell
.\.venv\Scripts\python.exe -m memetrader replay examples\historical\temporal_guard.synthetic.json --decision-at 2026-01-01T00:05:00Z
```

该回放只验证：决策时刻之前真正观察到的证据可用；之后的交易所上线、最高价、最终赢家和收益等必须拒绝。真正检验收益只能依赖从现在开始积累的 Forward Shadow/Paper 日志。
