# memeTrader 自主检索验收 — 2026-08-30

## 结论

**PASS_WITH_FAIL_CLOSED_EXTERNAL_PROVIDER_OUTAGE**

机器人已经能够在用户不维护热点关键词和信息源列表的情况下，自主执行：

```text
Agent 主动搜索当前国际热点
→ Agent 自动寻找可轮询的新信息源
→ 本地程序验证 URL、RSS、时效与内容质量
→ 自动启用、暂停和补充动态源
→ 高动量 Token 自动反查现实事件
→ 新闻/事件与 Token 双向汇合
→ 确定性评分、风险门、Paper 买卖与退出
```

当前仍为 `paper`，`live.enabled=false`。搜索 Agent 没有 Broker、钱包、私钥、仓位修改或风控绕过权限。

## Agent 数量与路由

普通个人电脑默认最多同时运行 **2 个 Agent 槽位**。这是并发上限，不是永久运行两个重复搜索进程。

| 任务 | 首选 | 回退 | 推理 |
|---|---|---|---|
| 全球热点侦察 | `gpt-5.3-codex-spark` | `gpt-5.6-luna` | low |
| 信息源发现 | `gpt-5.3-codex-spark` | `gpt-5.6-luna` | low |
| Token→事件核验 | `gpt-5.6-luna` | `gpt-5.6-terra`、`gpt-5.6-sol` | low，回退 medium |

公式计算、时间过滤、去重、流动性、仓位、止损和分批退出全部由本地代码完成，不调用 Agent。

## 默认频率、覆盖与额度

| 任务 | 默认值 |
|---|---:|
| 普通热点侦察 | 12 分钟；每次轮换 5 个主题中的 3 个 |
| 重大信号期间 | 3 分钟；覆盖全部 5 个主题 |
| 连续 3 次空结果 | 退避到 30 分钟 |
| Spark 不可用 | 普通最短 30 分钟；重大信号最短 10 分钟 |
| 单次超过 18,000 tokens | 普通最短 30 分钟；重大信号最短 10 分钟 |
| 单次热点搜索 | 最多 4 次网页搜索、3 个候选事件 |
| 自动搜源 | 24 小时；错误或空结果按状态缩短重试周期 |
| Token Context | 动量分≥80；全局 5 分钟；同 Token 240 分钟 |
| 最大并行 Agent | 2 |
| Trend Scout | 64 次/日，500,000 tokens/日 |
| Source Discovery | 2 次/日，100,000 tokens/日 |
| Token Context | 8 次/日，250,000 tokens/日 |

调用次数和 Codex 返回的 `tokens used` 分开写入 SQLite。任一上限达到后，当天停止该类 Agent；免费 RSS、浏览器桥、Pump 流、新池和 Paper 监督继续运行。

## 真实 Agent 冒烟

### 最新全球热点侦察

在真实设备和真实 Codex 登录态下执行：

- Spark 当日额度不可用，自动回退 `gpt-5.6-luna / low`；
- 本轮仅搜索轮换到的 3 个主题，而不是把 5 个主题全部塞入一次调用；
- 实际使用 `13,385 tokens`；
- 没有找到满足“近期、两条独立可访问来源、足够 Meme 化”的事件；
- 正确返回空列表，没有为了活跃而编造热点；
- 下一次间隔自动拉长到 30 分钟。

此前同类 Luna 全主题调用使用 `30,636 tokens`。本轮下降约 **56.3%**，同时由下一轮继续覆盖剩余主题。

当天累计：

| 类别 | 调用 | tokens |
|---|---:|---:|
| Trend Scout | 2 | 38,206 |
| Source Discovery | 2 | 58,851 |
| Token Context | 8 | 171,802 |

Token Context 的 8 次主要暴露于全局冷却固化之前。现在已经有 5 分钟全局冷却、240 分钟同 Token 冷却、动量门、8 次/日和 250,000 tokens/日双重限制。

## Agent 自己发现并维护信息源

真实 Source Discovery 已自行发现、验证并加入动态注册表。当前活跃动态源：

- Ars Technica All News；
- Tagesschau International News；
- CBS News Entertainment；
- RTHK World News；
- RTHK Sport News。

这些源已由常驻进程真实轮询，SQLite 中存在新的 `last_ok_at` 和 `last_item_at`，不是仅停留在 Agent 推荐清单。

系统还自动暂停了：

- TokenInsight News；
- NorriWire English News。

原因不是网络故障，而是近期样本中市场日报、价格更新等低价值内容占比过高。动态源还会在连续 3 次真实轮询失败后自动暂停；后续 Source Discovery 会继续补充或重新验证。静态配置源不会被擅自改写。

## 信息源本地验证门

Agent 返回的来源不会直接进入生产。动态 RSS 必须通过：

1. 公网 HTTP/HTTPS 和公网 DNS；
2. 实际 HTTP 成功；
3. RSS/Atom 可解析；
4. 存在近期且带时区的条目；
5. 内容不能主要是 Market Wrap、价格更新、技术分析、Presale 或 Top/Best/100x 榜单；
6. 与现有活跃域名不重复；
7. 币价、交易所和纯推广站不能作为事件来源。

## 前向数据状态

当前干净前向库：

```text
data/memetrader_forward_20260830_r6.sqlite3
```

截至 `2026-08-30T04:24:00Z`：

| 指标 | 数量 |
|---|---:|
| observations | 542 |
| events | 366 |
| tokens | 1170 |
| token_snapshots | 470 |
| decisions | 0 |
| positions | 0 |
| trades | 0 |

没有为了展示成交而降低阈值。`r5` 中由推广榜单与通用 Token 名造成的两次错误 Paper 入场已被永久排除于绩效统计，详见 `FORWARD_FALSE_POSITIVE_AUDIT_20260830.md`。

## 测试与打包

- `72/72` 自动测试通过；
- `compileall` 通过；
- Wheel：`dist/memetrader-0.6.1-py3-none-any.whl`；
- Wheel SHA-256：`5a86154a93d47ad730657c8fbb36d8a7bf18a749b813a0da0c9f6de60e5235e2`；
- 全新虚拟环境安装通过；
- `pip check` 通过；
- 安装后导入、CLI 帮助和未来数据隔离回放通过；
- Windows 计划任务 `memeTrader Paper Bot` 为 `Running`；
- `127.0.0.1:8765/health` 为 `ok=true`。

覆盖测试包括主题轮换、模型回退、调用和 token 双预算、动态源暂停、低质量内容暂停、Agent 结果本地验证、未来数据隔离、中英文推广榜单过滤、通用名称劫持、官方精确 CA、Paper 仓位和退出。

## 当前外部阻塞：Honeypot.is

最终在线诊断中：

- DexScreener：PASS；
- GeckoTerminal：PASS；
- RugCheck：PASS；
- Codex CLI：PASS；
- 已启用 RSS：PASS；
- Honeypot.is：HTTP 500 / 超时。

实际 `config.json` 设定：

```json
"require_evm_simulation": true
```

因此 `doctor --online` 正确返回非零，BSC 候选在 Honeypot.is 不可用时会**失败关闭**，不会把缺失结果伪装成安全。Solana、新闻采集、Agent 搜索、新池观察和常驻 Paper 进程继续运行。这是外部安全供应商故障，不是把代码门禁伪装成通过。
