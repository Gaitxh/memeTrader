from __future__ import annotations

import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VALIDATION = json.loads((ROOT / "data" / "validation_report.json").read_text(encoding="utf-8"))
IDENTITY = json.loads((ROOT / "research" / "live_identity_probe.json").read_text(encoding="utf-8"))
PUMP = json.loads((ROOT / "research" / "pumpportal_live_smoke.json").read_text(encoding="utf-8"))
pytest_check = next(item for item in VALIDATION["checks"] if item["name"] == "pytest")
match = re.search(r"(\d+) passed", pytest_check.get("stdout", ""))
test_count = int(match.group(1)) if match else None
resolved = [item for item in IDENTITY["results"] if item.get("status") == "resolved"]
with_news = [item for item in resolved if item.get("news_observed_now")]

try:
    cp = subprocess.run(["git", "status", "--short", "--branch"], cwd=ROOT, capture_output=True, text=True, timeout=15)
    git_status = cp.stdout.strip() if cp.returncode == 0 else "not a local Git repository"
except Exception:
    git_status = "git status unavailable"

rows = []
for item in VALIDATION["checks"]:
    rows.append(f"| {item['name']} | {'PASS' if item['passed'] else 'FAIL'} | {item['returncode']} |")

lines = [
    "# memeTrader 当前权威状态",
    "",
    f"- 生成时间：`{datetime.now(timezone.utc).isoformat()}`",
    "- 项目目录：`E:\\memeTrader`",
    "- 版本：`0.5.0`",
    "- 模式：默认 `paper`；Agent 默认关闭；Live 硬锁定。",
    f"- 自动测试：`{test_count if test_count is not None else '见 validation_report.json'}` 项通过。",
    f"- 强制门禁：**{'PASS' if VALIDATION['mandatory_passed'] else 'FAIL'}**",
    f"- 免费端点在线诊断：**{'PASS' if VALIDATION['online_reachability_passed'] else 'FAIL'}**",
    f"- 当前地址身份实验：`{len(resolved)}/{len(IDENTITY['results'])}` 可解析，`{len(with_news)}/{len(IDENTITY['results'])}` 当前可检索相关文章。",
    f"- PumpPortal 免费 WebSocket：**{'PASS' if PUMP.get('received') else 'FAIL'}**。",
    f"- Git：`{git_status}`",
    "",
    "## 门禁明细",
    "",
    "| 检查 | 结果 | 退出码 |",
    "|---|---:|---:|",
    *rows,
    "",
    "## 已实现闭环",
    "",
    "```text",
    "浏览器/RSS/Bluesky/Mastodon/Google News",
    "                +",
    "PumpPortal 新币/迁移 + GeckoTerminal 新池",
    "                ↓",
    "事件聚类 ↔ Token 反向查新闻",
    "                ↓",
    "精确 CA / 名称别名 / 主叙事差距 / 链上动量",
    "                ↓",
    "安全门槛 → Shadow/Paper 自主仓位",
    "                ↓",
    "硬止损 / 四档止盈 / 移动止盈 / 最长持仓退出",
    "                ↓",
    "控制台 + JSONL + 可选 ntfy/Telegram",
    "```",
    "",
    "## 关键不变量",
    "",
    "1. 仅有 Token 动量、没有独立外部事件时不能买入。",
    "2. 历史网页今天才被抓取，不能用于过去的决策时点。",
    "3. 后来的 ATH、上线、当前市值、赢家地址和未来钱包标签不能进入历史特征。",
    "4. 第一、第二候选无法拉开差距时输出 WAIT。",
    "5. Agent 无交易、钱包、数据库修改或风控绕过权限。",
    "6. OS 文件锁和 Windows 计划任务 IgnoreNew 防止重复机器人。",
    "7. 买入约束不能阻止已有仓位卖出。",
    "",
    "## 尚未声称完成",
    "",
    "- 没有真实资金 Broker、私钥签名或小额链上成交验收；Live 仍锁定。",
    "- 当前历史案例目录是时序/身份测试目录，不是已经证明盈利的回测数据集。",
    "- 浏览器扩展需要用户在 Chrome/Edge 中手工加载，并配置重点账号/页面。",
    "- GitHub 远端为空且本机 `gh` 尚未登录，因此还不能真实 push。",
    "",
    "## 机器证据",
    "",
    "- `data/validation_report.json`",
    "- `research/live_identity_probe.json`",
    "- `research/pumpportal_live_smoke.json`",
    "- `data/notifications.jsonl`",
]
(ROOT / "PROJECT_STATUS.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
print(json.dumps({"status": str(ROOT / 'PROJECT_STATUS.md'), "tests": test_count, "mandatory": VALIDATION['mandatory_passed']}, ensure_ascii=False))
