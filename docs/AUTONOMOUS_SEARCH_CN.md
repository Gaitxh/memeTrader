# 自主信息源与全球热点搜索

memeTrader 不要求用户预先列完所有信息源。常驻机器人会同时运行三类有明确边界的搜索任务，并把通过本地验证的结果写入 SQLite。

## 三类 Agent 任务

### 1. 全球热点侦察（Trend Scout）

这是主动搜索，不依赖用户手工添加账号或关键词。Agent 使用实时网页搜索覆盖：

- 突发国际新闻、政治与公众人物；
- 名人、娱乐、体育瞬间；
- 动物、网络文化和社区舆论；
- AI、游戏与科技梗；
- Crypto 原生社区事件。

候选事件必须满足：

1. 发生或显著升温于配置的回看窗口内；
2. Agent 给出的事件置信度和 Meme 化潜力达到阈值；
3. 至少两个独立域名提供可访问的原始页面；
4. 页面时间带明确，且本机实际在决策前验证到页面；
5. 不是币价页、上所公告、价格预测、付费喊单或事后总结。

通过的页面以 `agent_search_verified` 写入事件流。网页声明的发布时间不会替代本机 `observed_at`。

### 2. 信息源发现（Source Discovery）

Agent 定期寻找无需付费 API Key 的公开 RSS/Atom 源。候选源不会直接启用，而要经过本地程序验证：

- URL 必须是公开 HTTP/HTTPS；
- DNS 不能解析到本地或私有网络；
- 必须能被实际访问和解析；
- 必须含近期、带时区的条目；
- 不能与已有域名重复；
- 不能是币价、交易所或推广站。

验证通过后写入动态源注册表，下一轮采集会自动使用，不需要修改 `config.json`。

RSS 默认不继承系统代理。若电脑只能通过本机 SOCKS5 出网，可选配置
`sources.rss_proxy_url`，例如 `socks5://127.0.0.1:7890`。这里只接受无账号密码、
无路径/参数的 literal loopback IP；目标 RSS 仍先在本机解析并校验为公网地址，再以
批准后的 IP 通过 SOCKS5 连接，同时保留原域名的 Host 与 TLS SNI。留空即直接连接。

### 3. Token 反向事件搜索（Token Context）

只有新 Token 已出现真实流动性、成交量、买卖笔数和买盘优势时，系统才调用 Agent 反查名称背后的现实事件。结果同样要求两个独立、近期、可访问来源。

验证成功后，Agent 返回的 `token_id` 会直接进入主叙事候选排序。四字母名称（例如人物姓氏或短昵称）允许进入 Token Context 搜证，但不能仅凭文本重合直接连接新闻；必须有精确 CA 或 Agent 的双来源绑定。最终仍要通过报价、流动性、税率、可卖性、GoPlus/Honeypot、GoPlus/RugCheck 和仓位限制。当前 Paper 对 EVM 与 Solana 均默认要求至少一个外部安全报告；同一链族的报告全部不可用时失败关闭，而不是当作安全。

## 默认 Agent 数量与模型路由

普通个人电脑默认最多同时运行 **2 个 Agent 槽位**。这不是固定开启两个重复搜索进程，而是允许“全球侦察”和“Token 专项核验/信息源发现”在必要时并行。更多并发通常只会增加重复网页、限频和额度消耗；配置允许在 `1–4` 之间调整。

全球侦察不会每次把所有主题都塞给一个 Agent。普通状态下每次轮换搜索 5 个主题中的 3 个，下一次接着搜索剩余主题；重大信号期间覆盖全部 5 个主题。这样在约 24 分钟内完成一轮普通全覆盖，同时降低单次上下文和搜索成本。

| 任务 | 首选模型与推理 | 回退 | 原因 |
|---|---|---|---|
| 全球热点侦察 | `gpt-5.3-codex-spark`, low | `gpt-5.6-luna`, low | 高频、广覆盖、结构化筛选 |
| 新信息源发现 | `gpt-5.3-codex-spark`, low | `gpt-5.6-luna`, low | 低频、主要是搜索和 URL 核验 |
| Token 事件核验 | `gpt-5.6-luna`, low | `gpt-5.6-terra`, medium；最后 `gpt-5.6-sol`, medium | 需要较强的名称、人物、文化梗和身份判断 |
| 主叙事近似平局 | 原有语义 Agent（默认关闭） | 本地规则返回 `WAIT` | 不允许 Agent 硬选不确定主盘 |

Agent 全部使用：

```text
--search
--ephemeral
--ignore-user-config
--sandbox read-only
```

它们没有 Broker、钱包、私钥、仓位或项目写权限。

## 默认频率

| 工作 | 默认频率 |
|---|---:|
| Pump 新币 WebSocket | 持续流式 |
| 已登录浏览器公共页面 | DOM 新内容触发，30 秒心跳 |
| 事件重新判断 | 10 秒 |
| 持仓监督 | 15 秒 |
| 免费 RSS/新池 | 60 秒 |
| Token→Google News 初筛 | 45 秒调度，单 Token 有冷却 |
| 全球热点侦察：普通 | 12 分钟；每次轮换 3/5 主题 |
| 全球热点侦察：已有重大信号 | 3 分钟；覆盖全部主题 |
| 全球热点侦察：连续 3 次无结果 | 30 分钟 |
| Spark 不可用并回退到 Luna | 普通最短 30 分钟；重大信号最短 10 分钟 |
| 上一次调用超过 18,000 tokens | 普通最短 30 分钟；重大信号最短 10 分钟 |
| 新信息源发现 | 24 小时 |
| Token 专项 Agent | 事件触发；全局最短 5 分钟；同 Token 240 分钟冷却；失败仅退避 10 分钟；动量分≥80 |

全球侦察线程每 30 秒只检查“是否到期”，不会每 30 秒调用 Agent。

## 额度上限

默认值：

```json
{
  "max_concurrent_agents": 2,
  "trend_scout_daily_limit": 64,
  "trend_scout_daily_token_budget": 500000,
  "trend_scout_token_reserve_per_call": 40000,
  "source_discovery_daily_limit": 2,
  "source_discovery_daily_token_budget": 100000,
  "source_discovery_token_reserve_per_call": 30000,
  "context_search_daily_limit": 8,
  "token_context_daily_token_budget": 250000,
  "token_context_token_reserve_per_call": 30000
}
```

调用次数是硬上限；token 预算使用“已记录用量 + 下一次保留额度”的保守门槛。这样不会在只剩少量预算时再启动一次大搜索，但单次 Codex 调用的实际内部 token 数无法事先精确控制，因此最终一次仍可能高于保留估计。所有用量会持久化；`--force` 只绕过时间到期检查，不能绕过调用或 token 预算。失败调用退还项目内部“调用次数”，但会触发 10 分钟错误退避；CLI 平台已经消耗的额度无法由程序退回。

自动发现的 RSS 源连续 3 次真实轮询失败后会自动暂停；即使技术上可访问，若近期样本中至少一半是 Daily Market Wrap、BTC/ETH 价格更新、技术分析、Presale、Top/Best/100x 榜单等低价值市场摘要，也会自动暂停。下一轮信息源发现会补充或重新验证来源。静态配置源不会被这一机制擅自改写。

## 可调整配置

全部位于 `config.json -> autonomous_search`：

- `max_concurrent_agents`：最大并行 Agent，范围 1–4；
- `profiles`：每类任务的模型、回退模型和推理强度；
- `trend_scout_*`：主动热点侦察的频率、主题轮换、阈值、搜索数、调用上限和 token 上限；
- `source_discovery_*`：自动发现新源的周期、上限与失败自动暂停阈值；
- `source_quality_*` / `source_max_market_digest_ratio`：动态 RSS 的内容质量门；
- `context_*`：Token 反向检索的动量门槛、全局冷却、失败退避、同 Token 冷却、置信度与每日上限；
- `*_token_reserve_per_call`：在启动下一次调用前预留的 token 预算；
- `topics`：搜索覆盖面，不是固定关键词清单。

手工触发仅用于诊断：

```powershell
.\.venv\Scripts\python.exe -m memetrader scout-trends --config config.json --force
.\.venv\Scripts\python.exe -m memetrader discover-sources --config config.json --force
```

常驻运行时无需用户执行这两个命令。

## 状态查看

```powershell
.\.venv\Scripts\python.exe -m memetrader status --config config.json --limit 10
```

输出包含：

- `autonomous_search_usage`：分别显示三类任务的调用次数与 token 用量；
- `autonomous_trend_last_result`；
- `autonomous_source_last_result`；
- `autonomous_context_last_result`；
- `autonomous_sources` 动态注册表。

Agent 找不到足够证据时返回空结果或 `WAIT`。空结果是正确行为，不会为了“保持活跃”而杜撰热点或关联 Token。
