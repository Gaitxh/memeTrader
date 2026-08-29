# memeTrader 0.5.1 设备配置与验收

验收日期：2026-08-30（Asia/Shanghai）

## 结论

`E:\memeTrader` 已在本机完成 Paper 模式配置、免费公开源联网验证、完整发布门禁和 Windows 常驻任务验证。

当前状态：

- 模式：`paper`
- Live：硬锁定，`live.enabled=false`
- Agent：默认关闭，`agent.enabled=false`
- 工作目录：`E:\memeTrader`
- 权威前向数据库：从私有 `config.json` 的 `database` 字段解析；本机当前为 `data\memetrader_forward_20260830_r3.sqlite3`
- 浏览器桥：`127.0.0.1:8765`
- 常驻入口：Windows 计划任务 `memeTrader Paper Bot`

## 发布门禁

以下步骤均在本机实际执行并通过：

| 检查 | 结果 |
|---|---|
| PowerShell 语法解析 | 9 个脚本 PASS |
| Pytest | 41 passed |
| Python `compileall` | PASS |
| `git diff --check` | PASS |
| Wheel 构建 | `memetrader-0.5.1-py3-none-any.whl` |
| Wheel SHA-256 | `377152b0f9d2145e83c2116f39a467cfe224d80160fad36be894bc6d6c6e191b` |
| 全新 Windows 虚拟环境 | PASS |
| Wheel 全新安装 | PASS |
| `pip check` | PASS |
| 包导入与版本核对 | `0.5.1` PASS |
| CLI 启动 | PASS |
| 未来数据隔离回放 | PASS |
| SQLite `integrity_check` | `ok` |

## 免费公开源联网检查

本机在线诊断取得 HTTP 200：

- DexScreener
- GeckoTerminal
- Honeypot.is
- RugCheck
- CoinDesk RSS
- Cointelegraph RSS
- Google News viral RSS
- Google News memecoin RSS

Reddit 官方 RSS 在实际常驻轮询中返回过 403/429，因此已在默认设备配置和示例配置中停用。Reddit 改由用户已登录浏览器中的公开页面接入，避免无效轮询和错误刷屏。

## 常驻与故障恢复

计划任务实际配置：

- 当前交互用户登录时启动；
- `MultipleInstances=IgnoreNew`；
- 允许使用电池时启动；
- 切换到电池时不停止；
- 无执行时限；
- `run_paper.ps1` 以前台附着方式启动 Python，并在异常退出后等待 5 秒重启；
- Python 内部仍使用操作系统文件锁，防止第二个交易实例。

故障注入结果：

1. 强制终止真正监听 8765 的内层 Python PID；
2. 附着式 PowerShell 监督器检测到退出；
3. 18 秒内创建新监听 PID；
4. 计划任务继续保持 `Running`；
5. `/health` 再次返回 `ok=true`。

远程 MCP 执行环境有时会在工具调用结束后清理或禁用后台进程，这是外部执行环境行为。为避免误判，常驻逻辑同时通过了同一命令内的故障恢复测试和受控前台采集测试；真正跨登录重启仍应在用户正常 Windows 会话中继续观察。

## 前向采集实测

当前权威库在一个完整轮询观察窗口内从：

- Token：149 → 509；随后继续增长到 773；
- Token 快照：71 → 282；随后继续增长到 398；
- 新闻/社交观察：63 → 67；
- 事件：58 → 62。

最后一次设备巡检：

- SQLite：`integrity_check=ok`
- 活动来源错误：0
- 计划任务：`Running`
- 浏览器桥：健康
- 持仓：0
- 实际交易：0

没有交易不是故障。当前门槛要求独立事件证据、主叙事优势、可用报价、流动性、近期成交和安全检查共同通过；证据不足时保持 `WAIT`。

## 时间与未来信息边界

生产判断只允许使用本机已经观察到的信息：

```text
observed_at <= decision_time
ingested_at <= decision_time
```

历史案例只用于测试身份匹配、主盘歧义、时序与未来数据拒绝。后来的 ATH、最终赢家、交易所上线、最终持有人数、未来收益和事后聪明钱标签不能回填到更早决策。

## Agent 额度

常规抓取、去重、时间门、评分、仓位、止损和分批卖出均由本地确定性代码完成，不消耗 Agent 额度。

一次只读 Medium Codex 审查尝试因当前账户本月 Agent 额度已耗尽而未执行。机器人按设计继续使用本地规则，这不影响常驻采集和 Paper 流程。Agent 仍默认关闭。

## GitHub 同步

代码已推送到 `https://github.com/Gaitxh/memeTrader` 的 `main` 分支。首次代码提交：

```text
0c9afb56e3542b12c593104f0a96d150bfccec3c
```

推送后使用 `git ls-remote` 核对，本地与远端 SHA 相同。私有 `config.json`、数据库、日志、虚拟环境、Session 和 bridge token 均未进入提交。

## 唯一人工步骤

当前数据库中浏览器来源数量为 0，说明扩展尚未由用户在 Chrome/Edge 中加载。需要人工完成一次：

1. Chrome/Edge 打开扩展管理；
2. 开启开发者模式；
3. 加载已解压扩展 `E:\memeTrader\browser-extension`；
4. 把本机私有 `config.json` 中的 `bridge.token` 填入扩展选项；
5. 打开需要持续观察的公开 X List、官方账号、Truth Social、Reddit、Bluesky、YouTube 或 Telegram 公共页面。

不要把 `config.json`、数据库、日志、Cookie、Session、钱包材料或 bridge token 提交到 GitHub。
