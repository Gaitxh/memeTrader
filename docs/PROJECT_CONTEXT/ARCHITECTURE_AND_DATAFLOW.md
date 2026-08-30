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
        Token Context（动量 / 浏览器桥实收精确名人原帖 / 高热事件关系触发，且受预算限制）
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
          ├─ BUY 时冻结最终 decision_id + admitted cohort_id
          ├─ SELL 时扣除记录的手续费与已知 Token 税
          └─ 只归因 cohort 决策时冻结的最早合格 Observation：discovery_lead
                 └─ 精确链成熟后才可作为观察轮换的 Paper 次级验证

Trend Scout 主题通道基线 round-robin / 受限选择性分配
          │
          ▼
每轮通道暴露 / 完成 / 失败 / 空结果账本
          │
          └─ 仅可调整 Trend Scout 通道分配；不进入证据、决策、风险、仓位、退出或 Live

首次有效 Event→Token WAIT/CANDIDATE
          │
          ▼
冻结决策时价格 + 最早合格来源
          │
          ▼
15 / 60 / 240 分钟本机真实快照随访
          │
          └─ 仅作选择偏差和市场延续研究；不回填、不参与策略

每次新 Token Context assessment（含空结果与错误）
          │
          ▼
冻结触发 / 项目声明 / 社区 / 人物候选 / 独立报道 + 当时价格
          │
          ▼
15 / 60 / 240 分钟本机真实快照随访
          │
          └─ 只描述哪些调查语境值得继续研究；不改 Agent 调度、证据或交易
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
- `token_discovery_rounds` / `token_discovery_exposures`：PumpPortal、GeckoTerminal 与 DexScreener 的真实发现轮次、空窗口、错误、重复、本机首次 Token、链接、hydration 快照及 no-pair 前向分母；只作人工覆盖复核。
- `decisions`：action、score、match、canonical margin、理由、拒绝理由和 Paper 仓位金额。
- `paper_account` / `positions` / `trades`：Paper 现金、持仓、退出和历史成交；新持仓/成交冻结最终 `decision_id/cohort_id`，并保存报价、执行价、报价/请求时间、滑点、手续费和已知 Token 税。
- `paper_account_snapshots`：append-only 账户曲线；普通运行最多五分钟追加一次，买卖后强制追加，缺少新鲜报价时权益为 `null`。
- `paper_execution_attempts`：CANDIDATE 入场或退出触发后的模拟执行尝试；过期/缺失/错 Token 报价和执行失败不得伪造成交。
- `source_utility_outcomes`：完全平仓后的追加式、费后 Paper 结果归因；新版本只接受 `decision_id → admitted cohort_id → position/trades → close` 的精确链，并仅归因 cohort 冻结的 `discovery_lead`。旧事件时间窗行保留但不进入学习。
- `paper_source_attribution_attempts`：每个完全平仓 round 的归因覆盖账本；精确归因或缺 decision/cohort、主键不匹配、无合格来源等跳过原因都会保存，避免只看到成功归因样本。
- `trend_lane_runs` / `trend_lane_run_lanes`：每次 Trend Scout 的版本化通道选择、运行状态、空结果、事件与 Observation 产出；不含凭据。
- `trend_watch_account_exposures`：每轮实际账号选择、选择角色、完成/失败、精确原帖命中与零产出；不回填旧轮次，不含凭据。
- `browser_watch_account_exposures`：浏览器桥精确匹配配置公开账号页后形成的 30 分钟前向暴露窗口；主页、搜索页、登录页和 Telegram 不写入。
- `browser_watch_observation_links`：把本机收到的精确原帖 Observation 与暴露窗口、event ID 和当时的决策证据资格关联；只用于同源学习审计，不改变事件或交易规则。
- `shadow_event_cohorts` / `shadow_event_cohort_labels` / `shadow_event_outcomes`：首次 WAIT/CANDIDATE 的冻结价格、来源标签和固定时点市场随访；结果角色与交易策略完全隔离。
- `token_context_outcome_cohorts` / `token_context_outcome_labels` / `token_context_outcomes`：新 Token Context assessment 的冻结价格、安全语境标签与 15/60/240 分钟结果；历史不回填、missing 不改写，仅作描述性研究。
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
| DexScreener Profile/CTO/Ads/Boost | 90 秒；每面最多 40 条，每轮最多补全 180 个 CA，并按官方端点每批最多 30 个地址 |
| Token→Google News 调度 | 45 秒；单 Token 另有冷却 |
| 事件重新判断 | 10 秒 |
| Paper 持仓监督 | 15 秒 |
| 来源健康 | 30 秒 |
| 浏览器扩展 | DOM 触发；30 秒心跳 |
| Trend Scout 普通/surge/quiet | 12 / 3 / 30 分钟 |
| Source Discovery | 24 小时 |
| Token Context | 动量、浏览器桥本机实收且精确归因的高影响力账号原帖，或新鲜高热事件高匹配 WAIT/CANDIDATE 关系触发；全局 5 分钟、同 Token 240 分钟 |

Trend Scout 与 Source Discovery 首选 Spark/low，额度不可用时 Luna/low；Token Context 首选 Luna/low，回退 Terra/medium，Sol/medium 仅最后回退。该分级已经按任务复杂度配置并逐次记账，但当前自动升级主要处理模型/额度不可用，并不能声称已根据语义冲突或输出质量动态选择推理强度。所有本地计算不消耗 Agent。

账号选择不是“全目录每轮扫描”：`critical` 账号最多保留 4 个槽位；其余先按人工 P5–P1 策展，并在 12 个候选观察槽位中始终保留至少 40%（5 个）做轮换探索。账号暴露账本记录每次被检查却无产出的情况；精确原帖命中必须匹配平台和账号 URL 路径。`watch-attention/v1` 只有在发现效率门和 60 分钟 WAIT/CANDIDATE 人物/平台随访门同时成熟时，才允许普通账号在 `0.80×–1.20×` 内改变观察轮换；已平仓 Paper 标签只是次级验证，不能单独激活。Trend Scout 的 `trend-attention/v1` 已记录每轮通道暴露、空结果和错误/失败结果；只有全局至少 20 个已接受事件，且至少两个可比较通道各自达到 20 次完成暴露、10 个运行日、5 次零产出并具有成熟的 60 分钟 WAIT/CANDIDATE 市场随访时，才可在 `0.80×–1.20×` 内调整通道分配。已平仓 Paper 结果只作可选次级验证；普通运行始终保留至少一个 round-robin 探索通道，surge 全覆盖。当前运行预计仍在收集样本，尚未启用该分配。以上值不传给 CandidateEvaluator、SafetyChecker 或 PaperPolicy，也不影响退出或 Live。

注意：`runtime.py` 的通用配置校验仍允许 `max_concurrent_agents` 到 4，但根目录 `AGENTS.md` 和 Web 安全接口把当前发布运行上限限定为 2。继续工作时必须遵守更严格的 2，不能借通用校验提高并发。

## 7. Web 实时性

当前前端使用低成本 polling，而不是 WebSocket/SSE：Overview 10 秒，Events 12 秒，Token/Decision/Portfolio/Wallet 15 秒，Agent/Sources 20 秒，Audit 30 秒，Settings 60 秒。页面重新可见时会立即刷新；网络失败会保留缓存并明确标记 `STALE`。

首页“实时采集脉冲”必须来自 SQLite 的真实 60 秒/5 分钟窗口：

- 信息通道：非链上、live capture 的 observation 数量、速率和最后时间；
- Token 通道：新 Token、Token 更新、快照更新、速率和最后时间；
- 状态：active / degraded / stale / waiting / unavailable。

CSS 动画只能在数据时间窗确实为 active 时运行。浏览器本地每秒计时不等同新的后端数据。
