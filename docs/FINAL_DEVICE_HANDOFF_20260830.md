# memeTrader 最终设备交接（2026-08-30）

## 权威入口

继续本项目时，以以下文件和工作区最新字节为准：

1. `E:\memeTrader\AGENTS.md`
2. `E:\memeTrader\docs\FINAL_DEVICE_HANDOFF_20260830.md`
3. `E:\memeTrader\docs\DEVICE_VALIDATION_20260830.md`
4. 私有且被 Git 忽略的 `E:\memeTrader\config.json`
5. `config.json` 的 `database` 字段指向的 SQLite 文件

不要用聊天摘要覆盖工作区事实。

## 当前冻结状态

- 项目版本：`0.5.1`
- GitHub：`https://github.com/Gaitxh/memeTrader`
- 分支：`main`
- 已核对的首次代码提交：`0c9afb56e3542b12c593104f0a96d150bfccec3c`
- 模式：`paper`
- Live：锁定
- Agent：默认关闭
- 本机目录：`E:\memeTrader`
- 当前权威前向库：`data\memetrader_forward_20260830_r3.sqlite3`
- 浏览器桥：`127.0.0.1:8765`
- Windows 常驻任务：`memeTrader Paper Bot`

## 已通过门禁

- 41 项 Pytest；
- 9 个 PowerShell 脚本解析；
- Python 全源码编译；
- Wheel 构建；
- 全新虚拟环境安装；
- `pip check`；
- 包版本与 CLI；
- 未来数据隔离回放；
- SQLite 完整性；
- DexScreener、GeckoTerminal、Honeypot.is、RugCheck、CoinDesk、Cointelegraph、Google News 在线诊断；
- 计划任务 `IgnoreNew` 和电池设置；
- 强制终止监听 Python 后自动恢复；
- 一个完整轮询窗口内新闻、Token 和快照继续增长；
- 提交前私有路径和 bridge token 扫描；
- GitHub 本地/远端 SHA 核对。

## 当前运行数据快照

设备验收时权威库：

- observations：67
- events：62
- tokens：773
- token_snapshots：398
- decisions：0
- positions：0
- trades：0
- active source errors：0

这些只是验收时快照，继续运行后应增长。`decisions=0` 或无交易不是故障；系统必须在事件、主叙事、链上动量、流动性和安全门槛同时成立时才进入 Paper。

## 已知边界

- Reddit 官方 RSS 在实际轮询中出现 403/429，默认停用；使用已登录浏览器的公开 Reddit 页面。
- Bluesky 公共搜索可能因公共端点策略返回 403；当前设备配置未启用 Bluesky 查询。
- Codex 只读 Medium 审查因当月 Agent 额度耗尽未执行；确定性本地流程不受影响。
- 远程 MCP 环境可能在工具调用结束后清理后台任务。真实跨登录常驻应在普通 Windows 用户会话中继续确认。
- 当前没有真实资金 Broker、钱包签名或经过小额链上成交验证的 Live 路径。
- 历史案例只测试身份、时序、歧义和未来数据隔离，不能作为盈利证明。

## 唯一人工待办

Chrome/Edge 必须人工加载：

```text
E:\memeTrader\browser-extension
```

随后把被 Git 忽略的 `config.json` 中 `bridge.token` 复制到扩展选项，并打开希望持续观察的公共社交页面。验收时 `browser_source_count=0`，所以这一步尚未完成。

## 日常检查

```powershell
Set-Location E:\memeTrader

.\.venv\Scripts\python.exe -m memetrader status --config config.json --limit 30
.\.venv\Scripts\python.exe -m memetrader doctor --config config.json --online

Get-ScheduledTask -TaskName "memeTrader Paper Bot"
Get-ScheduledTaskInfo -TaskName "memeTrader Paper Bot"
Invoke-RestMethod http://127.0.0.1:8765/health
```

安装或恢复常驻任务：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\install_scheduled_task.ps1
```

停止并删除：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\remove_scheduled_task.ps1
```

## 下一阶段

不要继续扩架构。下一阶段只做真实 Forward Shadow/Paper 观察：

1. 完成浏览器扩展人工加载；
2. 检查公开页面心跳；
3. 让系统持续积累首次可见的事件、Token 和快照；
4. 复核 `WAIT / REJECT / CANDIDATE` 的真实样本；
5. 在足够前向样本后再评估阈值和是否值得开发 Live Broker。
