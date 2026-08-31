# memeTrader 长期需求台账

最后核验：2026-08-31 18:00（Asia/Shanghai）
当前功能基线：`main` / `b84a4894e51d39f63d382039ddbacbb99e27232c` / Paper / `live.enabled=false`

本文件是长期任务的逐项台账，不是某次发布的完成声明。运行事实仍以 `AGENTS.md`、当前代码、忽略的本机 `config.json`、当前 SQLite、实时 API、进程与端口检查为准。`CONTINUOUS` 表示工程链路存在但研究或运行验证必须持续，不能改成 `DONE`。

状态：`DONE`、`PARTIALLY_DONE`、`NOT_STARTED`、`IN_PROGRESS`、`CONTINUOUS`、`BLOCKED`、`INVALIDATED`、`NEEDS_REVALIDATION`、`SUPERSEDED`。

| requirement_id | 来源消息或文档 | 真实需求 | 当前状态 | 完成证据 | 未完成部分 | 持续任务 | 被后续要求取代 | 风险或阻塞 | 下一步行动 | 最后核验 |
|---|---|---|---|---|---|---|---|---|---|---|
| CORE-001 | 长期总 Prompt §2–5 | 单机、单进程、SQLite 的前向事件→Token→决策→Paper 系统 | CONTINUOUS | `Runtime`、`Store`、`Strategy`、47 张业务表；当前 r6 持续产生 observation/event/token/decision | 持续检查漏斗损失、延迟、zero-yield、误报和漏检 | 是 | 否 | 长期运行漂移与来源失效 | 每轮以真实数据库增量复核 | 2026-08-31 16:35 |
| SAFE-001 | AGENTS.md；长期总 Prompt §21 | Mainnet Live 永久锁定，网页/Telegram 不可解锁 | CONTINUOUS | 当前 `mode=paper`、`live.enabled=false`；Web 返回 locked/available=false | Mainnet Broker 尚不存在，且不是当前发布目标 | 是 | 否 | 私钥暴露、误广播 | 每轮测试 Live 锁与敏感字段隔离 | 2026-08-31 16:35 |
| OPS-001 | 长期总 Prompt §4、§21 | Paper Runtime 单实例、SQLite 单 writer、端口与任务可审计 | CONTINUOUS | Windows `memeTrader Paper Bot` Running/IgnoreNew；8765/8787/8788 均为单 listener；SQLite lock 被活动进程持有 | 需持续防止重复实例 | 是 | 否 | 重复实例、僵尸进程 | 每轮复核监听、任务和活动锁 | 2026-08-31 18:00 |
| OPS-002 | 长期总 Prompt §22 | 北京时间 00:00/08:00/16:00 复盘，不创建重复自动任务 | DONE | 既有 `memetrader` heartbeat 已从 09:00 更新为 `BYHOUR=0,8,16` | 无 | 否 | 旧 09:00 已 SUPERSEDED | 时区解释错误 | 后续只更新同一 automation | 2026-08-31 16:35 |
| MEM-001 | 用户“项目内保留上下文”；长期总 Prompt §3 | 持久化完整需求台账和最新断点 | IN_PROGRESS | 本文件建立；`START_HERE` 与日期快照已存在 | 每轮需同步状态、证据、下一步与新 supersession | 是 | 否 | 上下文压缩、旧报告被当成现状 | 每轮巡检更新本表和最新快照 | 2026-08-31 16:35 |
| WEB-001 | 用户网站/双语/动态要求；长期总 Prompt §20 | 深色中英控制台、动态刷新、响应式、真实数据 | CONTINUOUS | Overview/Events/Tokens/Decisions/Paper/Wallet/Agents/Sources/Audit/Settings 已实现；低成本 polling；8787/8788 与鉴权公网入口运行 | 固定公网域名仍需用户自有 Tunnel | 是 | 否 | 旧页面缓存、临时公网域名变化 | 持续做真实浏览器中英/响应式/错误日志 QA | 2026-08-31 18:00 |
| WEB-002 | 用户事件来源超链接要求 | 展示全部来源、角色、权威/热度排序与时间线 | CONTINUOUS | Event detail 有 F/C/I/P 分组、链接、透明排序、事实/局部传播/纠正三分栏；新增原始来源前向版本链、明确删除/撤回/纠正语义与 opaque 本机 ID | claim 级 supersession、可靠 origin/transport 拆分和独立内容核验未实现 | 是 | 否 | 聚合转发被误算独立来源、删除被误当事实为假、未观察被误读为否定结论 | 累积自然 revision；只接受明确 tombstone，不从缺项/404/DOM 消失推断 | 2026-08-31 18:50 |
| SRC-001 | 长期总 Prompt §10、§14 | 平台/来源/人物/主题按前向增量价值学习，保留探索 | CONTINUOUS | source learning、trend lane、watch exposure、至少 40% exploration 已实现 | 样本未成熟，不能改仓位/退出 | 是 | 否 | 幸存者偏差、过拟合 | 累积自然 exposure、失败和 fixed-horizon 结果 | 2026-08-31 16:35 |
| SRC-002 | 长期总 Prompt §5 | source-poll exposure 保存完成、空结果、重复、过滤和错误 | CONTINUOUS | `source_poll_attempts` 与 Sources 面板已实现 | 持续评估各入口覆盖和稳定性 | 是 | 否 | 为非空结果删分母 | 保留所有真实 poll 终态 | 2026-08-31 16:35 |
| TOKEN-001 | 用户 Dex/OKX/新币来源要求；长期总 Prompt §5、§7 | 多入口新 Token/池发现与 Event↔Token 证据链 | CONTINUOUS | PumpPortal、GeckoTerminal、DexScreener discovery/hydration、token discovery exposure 已实现 | OKX Premium/签名接口未接；不逆向绕过 | 是 | 否 | 推广榜单、同名币、来源竞争 | 继续比较本机首次发现与后续漏斗 | 2026-08-31 16:35 |
| TOKEN-002 | 长期总 Prompt §7 | canonical Token 竞争与 CA 置信度 | CONTINUOUS | match/candidate/canonical margin、WAIT/REJECT/CANDIDATE 已实现 | image similarity、dominant contract/buyer breadth仍不完整 | 是 | 否 | 同名币和未来赢家回填 | 只用决策时可得证据扩充特征 | 2026-08-31 16:35 |
| INFO-001 | 用户“信息可能先于价格”；长期总 Prompt §6 | 独立 information-first 前向 cohort | CONTINUOUS | `information-first-shadow/v1`，缺基线也入分母，15/60/240 追加终态 | 样本尚不成熟 | 是 | 否 | 把低活动误写成未定价 | 继续积累注册后 cohort | 2026-08-31 16:35 |
| INFO-002 | 长期总 Prompt §6 | 严格 Information Lead Gap | CONTINUOUS | `information-first-ilg/v1`；同 provider/chain/DEX/pair；Store 生成 `recorded_at` | 需更多注册后 crossing/missing 样本 | 是 | 否 | 后来快照/跨池回填 | 保持固定 240m+30m 终态 | 2026-08-31 16:35 |
| INFO-003 | 长期总 Prompt §6 | 10s/30s/1m/5m mention velocity、加速度、跨平台扩散 | PARTIAL | `event-attention-trajectory/v1` 从上线后为每个新关联 Observation 原子追加不可变分数点；API/UI 显示本机 10s/30s/1m/5m 新观察到达率下界、score velocity/acceleration、覆盖状态和 `affects=none`。旧事件不回填，覆盖不足为 null；全网 mention、稳定作者、reply/quote/repost、跨社区/原始跨平台因缺少平台分母、互动修订、稳定 actor 与 origin/transport 分离而明确 `unavailable` | 全部 | 是 | 否 | 45s 轮询不足以解析 10s/30s；现有 source_entity_id 与跨原始平台样本为 0 | 先积累注册后轨迹，再实现 origin item/actor 与 collector coverage ledger；不得将 transport 当 origin | 2026-08-31 17:08 |
| CHAIN-001 | 长期总 Prompt §8 | unique buyers、new holders、buyer breadth、集中度和 cluster | NOT_STARTED | 当前仅 buys/sells/tx/volume/liquidity 与安全服务 | 独立钱包、holder 变化、insider cluster 不可用 | 是 | 否 | RPC/索引成本、伪交易 | 先做 Solana 小样本 shadow 数据可用性实验 | 2026-08-31 16:35 |
| FACT-001 | 长期总 Prompt §9 | 分离事实真实性、传播真实性、纠错/删除/反转 | PARTIALLY_DONE | `event-claim-assessment/v1` 与 `source-item-revision/v1` 均已前向注册；来源条目 baseline/edit/明确 delete/retract/correct/restore 形成不可变链，future 标记、旧数据不回填、固定 `affects=none`；API/UI 分离评估、局部传播与来源版本 | 仍无独立内容核验、claim 级 target/supersession、可靠 origin/transport 拆分和纠正后的市场反转结果 | 是 | 否 | Agent 自报被误当事实、删除被误写为辟谣、缺项/404 被误写为删除 | 累积自然 edit/tombstone；实现独立 verifier 与 claim relation 前仍保持 shadow | 2026-08-31 18:50 |
| AGENT-001 | 长期总 Prompt §19 | 不同任务使用合适模型/推理强度，并发最多 2，完整 Token 记账 | CONTINUOUS | Trend/Source 为 Spark-low→Luna-low；Context 为 Luna-low→Terra/Sol-medium；Web 分模型/强度/Token 展示；新 Trend/Context 输出统一 identity/context-only，不再直接成为 F/C 决策证据 | 通用独立事实核验与冲突驱动质量升级未完成 | 是 | 否 | 空结果被误判失败、Agent 自报进入策略、重复升级烧额度 | 为独立内容核验设计前向 verifier；未经核验继续 context-only | 2026-08-31 18:00 |
| AGENT-002 | 用户预算补充；长期总 Prompt §19 | 本机预算不过度阻塞，但保留有限门、冷却和退避 | CONTINUOUS | 当前上限 Trend 96/50M、Source 12/10M、Context 192/50M；并发 2；Context 在 86/96 接近上限时依据真实节奏提高到 192 | 需持续检查真实用量与 zero-yield cost | 是 | “取消预算”被有限大上限替代 | 无限制循环和重复调用 | 只有真实 limiter 偏低时才提高；不移除触发门/冷却/退避 | 2026-08-31 18:00 |
| PAPER-001 | 用户 Paper 与成本要求；长期总 Prompt §18 | 前向 Paper、滑点/费率、账户曲线、分批止盈和 runner | CONTINUOUS | append-only cash/equity；4% 配置滑点、60bps、PumpSwap 125bps；两笔历史 Paper fill | 当前只有一个闭环；历史 fill 仍记录旧 2% 滑点 | 是 | 否 | 把 Paper 当真实利润、费用遗漏 | 等待新 cohort，按当时配置审计 | 2026-08-31 16:35 |
| PAPER-002 | 用户长期学习；长期总 Prompt §14、§18 | 热度/人物/社区只能先做 shadow，成熟后预注册策略 challenger | NOT_STARTED | Phase 1 学习门和 UI 已实现 | Phase 2 assignment/challenger 尚未实现 | 是 | 否 | 后验调参、样本太少 | 达到文档门前保持基线；预注册首个保守退出 challenger | 2026-08-31 16:35 |
| MISS-001 | 长期总 Prompt §17 | 系统化漏检、误报、迟发现、错映射账本 | PARTIALLY_DONE | r5 false-positive、r6 Starlink/future/stale 审计和通知已存在 | 没有统一 missed-opportunity/false-negative append-only ledger | 是 | 否 | 用未来赢家倒推规则 | 先记录发现断点，不改历史决策 | 2026-08-31 16:35 |
| X-001 | 用户 X 名单；长期总 Prompt §11 | 候选账号目录，不继承人工 S/A 评级，持续核验 handle/职责/价值 | CONTINUOUS | 107 条 v3 目录；CoinbaseAssets 已由 CoinbaseMarkets 取代；critical 只影响轮换 | 新追加的 BNO/娱乐/crypto 账号仍待逐一核验 | 是 | 人工评级已 INVALIDATED | 冒充、改名、推广利益冲突 | 分批核验并以 exposure/zero-yield 评价 | 2026-08-31 16:35 |
| TG-001 | 最新长期总 Prompt §1、§12 | 用户允许项目内 Telegram 配置和只读 allowlist | SUPERSEDED | 最新授权已写入本台账与 Web policy | 授权不等于平台许可 | 否 | 旧“因用户选择永久禁止”已被取代 | 容易误读为可绕过平台条款 | 与 TG-002 分开判断 | 2026-08-31 16:35 |
| TG-002 | Telegram 官方 Content Licensing/API 条款；长期总 Prompt 的客观判断要求 | 自动抓取、聚合并送入 AI 前必须满足平台条款 | BLOCKED | 2026-08-31 官方条款明确禁止面向 AI/ML 的 scraping/indexing/aggregation/deployment；Web 返回 `blocked_by_platform_terms` | 未取得 Telegram 及所有相关用户的明确、持续、限定同意 | 是 | 否 | 账号/API 封禁、版权与隐私 | 保持自动正文采集和 Agent 摄取关闭；定期复核官方条款 | 2026-08-31 16:35 |
| TG-003 | 长期总 Prompt §12.1–12.2 | Telegram 候选、身份、角色、替代机器源目录 | IN_PROGRESS | `SOCIAL_SOURCE_CATALOG.json` 已扩充为 13 个 Telegram 候选；未核验/非官方/transport 明确标注 | 仍需逐一核验当前 profile/运营方/活跃性 | 是 | 否 | 把搬运当官方、一源多算 | 从官网双向核验；优先使用外部原文/RSS | 2026-08-31 16:35 |
| TG-004 | 长期总 Prompt §12.3–12.9 | MTProto collector、message revision/tombstone/exposure/provenance/learning | BLOCKED | 当前 r6 无 Telegram 表/Observation/poll；Web 明确显示 0 messages/0 exposure | 全部工程链路未上线 | 是 | 否 | 与 TG-002 平台条款冲突 | 只有合规条件改变后再按严格 allowlist 设计评审 | 2026-08-31 16:35 |
| TG-005 | 用户“Telegram 失败时作备用” | 人工发现后回到官网/RSS/X/链上原始证据 | CONTINUOUS | 253 条 Dex Token Telegram 链接仅保存为 manual identity/promotion；通用 Agent/Bridge 拒绝 t.me | 需持续衡量这些链接是否带来可核验外部原文 | 是 | 否 | 项目方自报和转发污染 | 只追踪允许机器读取的 external origin | 2026-08-31 16:35 |
| DEVNET-001 | 用户真实交易测试讨论 | Devnet 可核验签名；Mainnet 仍锁定 | BLOCKED | 隔离 Devnet Wallet 工程存在 | 测试钱包无 Devnet SOL，尚无公开可核验 signature | 否 | “只接私钥即可无缝实盘”已 INVALIDATED | 用户曾暴露的私钥不可使用 | 仅用户自行充值 Devnet SOL 后做最小签名验证 | 2026-08-31 16:35 |
| PUBLIC-001 | 用户公开 URL 要求 | 受保护公网只读控制台，不暴露 loopback/secret | PARTIALLY_DONE | Quick Tunnel 脚本和口令保护已实现 | 当前 tunnel 530，8788 未监听；URL 非固定域名 | 是 | 否 | 临时域名变化、口令泄露 | 发布后恢复临时入口；固定域名需用户自有 Tunnel | 2026-08-31 16:35 |

## 当前真实运行快照

- SQLite：`quick_check=ok`、WAL；本轮未删除、清空、回填或改写 r6 历史。
- 本次核验计数：2,273 observations、1,475 events、51,730 tokens、839 decisions（831 WAIT / 6 REJECT / 2 CANDIDATE）、4 Paper fills、0 open positions。
- Paper：cash/equity `1001.4917655212 USD`，累计已实现 Paper PnL `+1.4917655212 USD`；这不是 Mainnet 利润。
- 事实账本：31 个注册后前向点 / 22 个事件，当前均为 `unassessed`；不是 31 个已证实事实，也没有历史回填。
- Agent 当日：118 calls、144 attempts、26 fallback attempts、6,937,075 已知 tokens；并发上限 2。Context 本机有限调用上限已从 96 调到 192。
- Telegram：0 专表、0 Observation、0 poll attempt、0 自动消息、0 forward exposure；253 个 Token 元数据 `telegram_manual` 链接不等于采集。
- Runtime：一个 Windows 计划任务与一个活动锁；8765/8787/8788 各单 listener。受保护 Quick Tunnel 正常，未鉴权 401、鉴权后 200。

这些数字是本次核验快照，会继续变化；后续不得直接复制为“当前状态”。
