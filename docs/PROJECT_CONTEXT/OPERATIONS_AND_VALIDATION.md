# 运行、验证与发布手册

## 1. 常用入口

安装依赖与本机配置：

```powershell
Set-Location E:\memeTrader
powershell -ExecutionPolicy Bypass -File .\scripts\install_windows.ps1
```

安装或恢复单一 Paper 常驻任务：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\install_scheduled_task.ps1
```

计划任务 `memeTrader Paper Bot` 使用 `IgnoreNew`。`run_paper.ps1` 保持 Python 子进程附着，异常退出后等待 5 秒重启；Runtime 自身还有 OS 文件锁。不要手工再启动第二个机器人实例。

查看状态：

```powershell
.\.venv\Scripts\python.exe -m memetrader status --config config.json --limit 30
Get-ScheduledTask -TaskName "memeTrader Paper Bot"
Invoke-RestMethod http://127.0.0.1:8765/health
```

## 2. Web 控制台

本机：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\open_web_console.ps1
```

访问：`http://127.0.0.1:8787/`

临时受保护公开地址：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\share_web_console.ps1
```

Quick Tunnel 地址和口令只保存在被 Git 忽略的本机文件中。不要把地址凭据复制进文档、Issue、提交或 Agent prompt。隧道重建后地址会变化；需要固定域名时应使用用户自己的 Cloudflare Tunnel/Access，origin 仍保持 loopback。

## 3. 浏览器社交采集

一次性人工设置：

1. Chrome/Edge 加载未打包扩展 `E:\memeTrader\browser-extension`；
2. 用户自己把本机 `config.json` 的 Bridge Token 填入扩展选项；
3. 用户在专用浏览器配置中完成平台登录；
4. 打开高价值账号页、X Lists、搜索页和允许浏览器观察的公开社区；Telegram 仅作人工目录，不由扩展或 Agent 自动读取；
5. 在 Sources 确认平台 heartbeat、access state 和最近产出。

Agent 可以在用户明确授权下操作普通登录 UI 和 Google OAuth，但不能读取已保存密码。CAPTCHA、短信、MFA、手机号、条款和高风险确认必须交还用户。账号创建成功也不代表采集成功，必须检查扩展实际看到的页面内容和 heartbeat。

## 4. 修改频率与观察清单

优先使用 Web Settings 的后端白名单，不直接编辑任意 JSON。Runtime 字段保存后会返回 `restart_required=true`；平台、公开账号和主题偏好写入本地 `console_settings.json`，不会启动第二个机器人。

调整时记录：旧值、新值、原因、预计 Agent 调用/Token 上限和回退行为。遵循：

- Agent 并发只能 1–2；
- 不取消每日调用/token 双预算；
- 不取消 quiet、fallback、高 token 和 error backoff；
- 页面自动刷新频率不是采集频率；
- 重启用计划任务监督流程，并确认只有一个 Runtime。

## 5. 最小改动检查

针对代码改动先跑最接近的测试。例如 Web 变更：

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests\test_web_backend.py
```

发布或 push 前完整检查：

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m compileall -q src tests
.\.venv\Scripts\python.exe -m memetrader doctor --config config.json --online
node --check src\memetrader\web_static\app.js
node --check src\memetrader\web_static\detail-request-state.js
node --check browser-extension\background.js
node --check browser-extension\content.js
node tests\web_detail_request_state.test.js
git diff --check
git status --short
```

Web 还要实际在浏览器检查桌面和窄屏：

- Overview 动态更新且使用真实时间窗；无数据/陈旧时不显示假 LIVE；
- 空数据库和有数据都不崩溃；
- Events 显示 platform、author、影响力事实、角色、freshness、eligibility 和全部链接；
- `identity/promotion/future` 不进入可用证据；
- Token 双向证据链完整；
- `WAIT` 不被美化；
- Paper 金额始终标为模拟；
- Agent token 分模型/推理强度正确；
- Settings 只接受白名单路径，`max_concurrent_agents > 2` 被拒绝；
- API 不返回 Bridge Token、通知 secret、平台凭据、私钥、公开入口口令；
- 本机 Wallet 可写，公开入口钱包变更为 403；
- Live 无按钮、无 API、配置仍为 false。

## 6. Resident 变更额外检查

如果修改调度、Runtime、配置或脚本：

1. 检查计划任务状态和 `MultipleInstances=IgnoreNew`；
2. 检查端口 8765 与 `/health`；
3. 做一次受控子进程终止并确认监督器只恢复一个子进程；
4. 检查 SQLite `integrity_check`，不要长事务锁库；
5. 确认 observations/tokens/snapshots 在真实窗口内按来源预期增长；
6. 确认采集缺失不会被当成安全或交易信号。

## 7. 提交边界

只提交源码、测试、文档和前端静态资源。提交前检查 Git 未跟踪内容，确保没有：

```text
config.json
data/
*.sqlite*
logs
wallet material
browser/session material
tokens or credentials
```

Push 后记录真实 SHA，并用远端引用核对。不要在报告中虚构测试、登录、交易签名、运行数据或公开 URL 持久性。
