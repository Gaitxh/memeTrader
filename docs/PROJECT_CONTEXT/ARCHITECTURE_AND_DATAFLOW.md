# 架构、数据流与关键代码

## 1. 部署形态

保持个人电脑友好：

```text
Windows 计划任务（IgnoreNew）
  └─ scripts/run_paper.ps1 监督器
      └─ 一个 memeTrader Python Runtime
          ├─ 免费新闻/社交/链上采集
          ├─ 最多两个受控 Agent 子进程
          ├─ 确定性 Strategy / Paper 执行
          ├─ SQLite WAL
          └─ 127.0.0.1:8765 浏览器桥

独立轻量 Web 进程（127.0.0.1:8787）
  └─ SQLite 短只读查询 + 安全配置白名单

可选公开查看
  └─ 鉴权入口 127.0.0.1:8788 ← Cloudflare Quick Tunnel
```

没有 Redis、消息队列、外部数据库或容器编排。

## 2. 主数据流

```text
RSS / Mastodon / 浏览器 DOM / Trend Scout
                    │
                    ▼
              Observation
        角色分类 + 时间门 + 推广过滤
                    │
                    ▼
             EventEngine 聚类
                    │
                    ├──────────────┐
                    ▼              │
PumpPortal / Gecko 新 Token/池      │
Dex Profile/CTO/Ads/Boost           │
                    │              │
                    ▼              ▼
       TokenCandidate + 附带链接   Event aliases / CA
                    │              │
                    └──── 双向匹配 ┘
                           │
             DexScreener 报价与 5m 动量
                           │
        Token Context（仅高动量且受预算限制）
                           │
                           ▼
              CandidateEvaluator 排名
                           │
           WAIT ── SafetyChecker ── REJECT
                           │
                       CANDIDATE
                           │
               PaperPolicy 仓位与退出
                           │
                    SQLite / 通知
                           │
                    Web 只读可视化

完全平仓的 Paper 结果
          │
          ▼
最早合格 Observation 的追加式来源效用账本
          │
          └─ 仅在成熟样本后小幅调整 Agent 观察轮换；不进入策略评分/仓位
```

`Web` 不重新算交易策略、不生成演示数据，也不因页面刷新触发采集或决策。

## 3. 关键代码路径

| 路径 | 职责 |
|---|---|
| `src/memetrader/runtime.py` | 默认配置、配置校验、单实例、采集调度、浏览器桥、事件/Token 写入、评估与仓位监督 |
| `src/memetrader/store.py` | SQLite WAL schema、去重、事件/Token/快照/决策/Paper/健康/Agent 用量持久化 |
| `src/memetrader/models.py` | Observation、EventView、TokenCandidate、TokenSnapshot、CandidateDecision、Position 数据模型 |
| `src/memetrader/collectors.py` | RSS、Bluesky、Mastodon、GeckoTerminal、DexScreener、PumpPortal 客户端 |
| `src/memetrader/autonomous_search.py` | Trend Scout、Source Discovery、Token Context 的 Codex 路由、预算、验证和动态源维护 |
| `src/memetrader/strategy.py` | 聚类、时间回放门、安全检查、匹配/排名、WAIT/REJECT/CANDIDATE、Paper 仓位/退出 |
| `src/memetrader/web.py` | 轻量 HTTP API、SQLite 短查询、健康、详情、白名单 Settings、本机 Devnet 钱包接口 |
| `src/memetrader/web_static/` | 双语响应式 SPA、自动轮询、图表/状态/详情抽屉 |
| `src/memetrader/wallet.py` | Windows DPAPI、本机 Solana Devnet 状态和人工测试交易；不连接策略 |
| `browser-extension/` | 公开页面 DOM 观察、30 秒心跳、本地队列和 loopback bridge 发送 |
| `scripts/` | Windows 安装、常驻、Web、本机公开隧道、状态和测试入口 |
| `tests/` | 核心、Runtime、Agent、Bridge、历史时间门、Wallet 和 Web API 测试 |

## 4. SQLite 权威数据

数据库由本机私有 `config.json -> database` 指定。主要表：

- `observations`：来源、平台文本、作者、URL、角色、发布时间、本机观察/摄入时间、原始 JSON。
- `events` / `event_observations`：聚类事件、首次接受时冻结的前向 topic 及其全部证据；迁移前记录保持 `unknown`。
- `tokens` / `token_snapshots`：Token 身份和随时间变化的价格、流动性、成交与安全字段。
- `token_source_links`：Dex/pair 附带 URL 的发现面、identity/promotion 角色、类型、平台及本机首次/最后观察。
- `decisions`：action、score、match、canonical margin、理由、拒绝理由和 Paper 仓位金额。
- `paper_account` / `positions` / `trades`：Paper 现金、持仓、退出和历史成交。
- `source_utility_outcomes`：完全平仓后对最早合格来源的追加式、费后 Paper 结果归因；只供观察轮换。
- `source_health`：来源最后成功、最后产出、最后错误。
- `agent_attempts`：按任务/模型/推理强度记录安全的 token 用量账本。
- `kv`：调度、退避、Agent 结果、浏览器平台心跳等小型运行状态。

SQLite 使用 WAL。Web 使用短连接和短查询；不得清空、迁移或重写前向 r6 证据来做界面展示。

## 5. 本地文件边界

```text
config.json                         私有运行配置，不进 Git
data/memetrader_forward_*.sqlite3   权威前向数据，不进 Git
data/notifications.jsonl            结构化通知，不进 Git
data/logs/                           运行/Web/隧道日志，不进 Git
data/web_console/console_settings.json  平台、公开账号和主题偏好，不进 Git
data/web_console/wallet.*           本机 Devnet 密文/元数据，不进 Git
docs/PROJECT_CONTEXT/               无 secret 的版本控制内项目记忆
```

## 6. 采集与 Agent 调度基线

代码基线默认值：

| 工作 | 默认 |
|---|---:|
| 外部 RSS/新池 | 60 秒 |
| DexScreener Profile/CTO/Ads/Boost | 90 秒；每面最多 40 条，每轮最多补全 8 个 CA |
| Token→Google News 调度 | 45 秒；单 Token 另有冷却 |
| 事件重新判断 | 10 秒 |
| Paper 持仓监督 | 15 秒 |
| 来源健康 | 30 秒 |
| 浏览器扩展 | DOM 触发；30 秒心跳 |
| Trend Scout 普通/surge/quiet | 12 / 3 / 30 分钟 |
| Source Discovery | 24 小时 |
| Token Context | 动量触发；全局 5 分钟、同 Token 240 分钟 |

Trend Scout 与 Source Discovery 首选 Spark/low，额度不可用时 Luna/low；Token Context 首选 Luna/low，回退 Terra/medium，Sol/medium 仅最后回退。所有本地计算不消耗 Agent。

账号选择不是“全目录每轮扫描”：`critical` 账号最多保留 4 个槽位；其余先按人工 P5–P1 策展，并在 12 个候选观察槽位中始终保留至少 40%（5 个）做轮换探索。只有达到 20 个已平仓 Paper / 10 个结果日 / 5 个亏损结果（人物要求 30 / 15 / 两个平台）的平台、来源或实体标签才允许在 `0.75×–1.25×` 内改变观察轮换。事件/热点 topic 只做前向描述，永不激活轮换。该值不传给 CandidateEvaluator、SafetyChecker 或 PaperPolicy。

注意：`runtime.py` 的通用配置校验仍允许 `max_concurrent_agents` 到 4，但根目录 `AGENTS.md` 和 Web 安全接口把当前发布运行上限限定为 2。继续工作时必须遵守更严格的 2，不能借通用校验提高并发。

## 7. Web 实时性

当前前端使用低成本 polling，而不是 WebSocket/SSE：Overview 10 秒，Events 12 秒，Token/Decision/Portfolio/Wallet 15 秒，Agent/Sources 20 秒，Audit 30 秒，Settings 60 秒。页面重新可见时会立即刷新；网络失败会保留缓存并明确标记 `STALE`。

首页“实时采集脉冲”必须来自 SQLite 的真实 60 秒/5 分钟窗口：

- 信息通道：非链上、live capture 的 observation 数量、速率和最后时间；
- Token 通道：新 Token、Token 更新、快照更新、速率和最后时间；
- 状态：active / degraded / stale / waiting / unavailable。

CSS 动画只能在数据时间窗确实为 active 时运行。浏览器本地每秒计时不等同新的后端数据。
