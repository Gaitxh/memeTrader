# 安全边界与不可变规则

## 1. 交易边界

- 常驻自动策略只实现 `shadow` 与 `paper`；当前部署为 `paper`。
- `live.enabled` 必须为 `false`。配置加载会拒绝 live，Web 只显示 `LOCKED / Unavailable`。
- 网页、公开 URL、账号登录、保存 Devnet 私钥都不能改变上述状态。
- 任何 Mainnet Broker、钱包签名和自动实盘都需要独立设计审查、风险边界、小额链上验证和新的明确授权；不属于当前发布线。
- 用户要求的“真实交易测试”当前只能解释为隔离的 Solana Devnet 人工测试。没有公开可验证 signature 就不能声称成功。

## 2. 时间和证据边界

决策证据必须同时满足：

```text
observed_at <= decision_time
ingested_at <= decision_time
```

- 页面声称的 `published_at` 不能证明机器人当时已看到。
- 第一次本机看到时已超过 freshness 的 `feature/confirmation` 降级为 `identity`，attention 为 0。
- 未来发布时间、后来 ATH、最终赢家、交易所上线、未来持有人数、收益和“聪明钱”不能回填。
- `promotion` 只存档；Top/Best/100x、presale、price prediction、coins to buy/watch 等不能触发。
- `identity` 解释名称和人物背景，但不能单独买入。
- `confirmation` 是独立确认，不自动等于交易信号。
- 证据不足或主盘不确定时返回 `WAIT`；不得强选赢家。

## 3. r5 与 r6 审计边界

- `r5` 含推广榜单和通用词 Token 误关联形成的错误 Paper 入场，只作为失败证据保存，不能并入表现统计。
- 干净前向线是 `r6`。不要删除、清空、合并或改写历史证据。
- r6 Starlink 案例证明陈旧反查来源只能是 identity，不能抬高 attention 或重复触发 DEX/API。
- 新鲜的后续观察可以重新解锁判断，但不能追溯改变之前的决策资格。

## 4. Agent 边界

- 最多两个 Agent 子进程并发。
- 仅允许三类调用：全球热点侦察、免费来源发现、受控 Token 上下文。Token 上下文可以由链上动量、精确高影响力账号原帖，或新鲜高热事件与 Token 的高匹配持久化关系触发；触发只决定调查优先级，不构成背书、证据或买入信号。
- News Radar、Social Pulse、Named Account Watch、Evidence Verifier、Token Context、Source Discovery 是六个逻辑职责，不是六个并发 Agent。
- Agent 不能访问 Broker、钱包、私钥、仓位修改、项目写权限或风控绕过。
- 本地代码负责轮询、解析、去重、时间、评分、数学、仓位、风险限额和退出。
- 每类 Agent 都受调用次数、token 预算、每次预留、quiet/surge、全局/单 Token 冷却和错误退避限制；`--force` 不能绕过预算。
- 用量账本不保存 prompt、stderr、Codex 登录材料或 secret。

## 5. 账号与登录边界

- 用户可以在本机浏览器使用已经导入的密码或 Google OAuth，但 Agent 不读取、复制、展示、导出或保存密码。
- 不读取 Cookie、local storage、Session、浏览器配置文件、私信或历史记录。
- 遇到验证码、MFA、短信、手机号、CAPTCHA、风险检查、用户名选择或条款确认时，停止并让用户在浏览器中完成；不得规避反自动化机制。
- Google OAuth 不是所有平台的注册方式；不为“覆盖全部平台”强行创建账号。
- 项目只保存公开账号元数据：平台、公开 handle/显示名、公开 URL、优先级和启用状态。
- 扩展只采集用户实际打开并渲染的公开页面，不自动关注、点赞、发帖、私信、滚动或抓取隐藏内容。

## 6. Secret 与钱包边界

以下内容禁止进入 Git、项目上下文、日志、SQLite、Web 响应或 Agent prompt：

- 任何私钥、助记词、密码、Cookie、Session、验证码；
- Bridge Token、通知 token、Chat ID、API key；
- 公开入口访问口令和本机鉴权文件内容。

如果用户曾在聊天中粘贴私钥，应视为已暴露，不能复制到项目或测试中。需要测试时生成一次性 Devnet 钱包，或让用户在 loopback Wallet 页本机录入。

Wallet 限定：

- 只在 loopback 接受变更；公开入口只读脱敏。
- 私钥使用当前 Windows 用户 DPAPI 加密，不回显。
- 固定 Solana Devnet RPC 并核对 genesis hash。
- 人工发送限额与确认语由后端强制；不能连接常驻策略或解锁 Mainnet。

## 7. Web 和公开入口边界

- 默认只绑定 `127.0.0.1`；非 loopback 必须配置访问口令，否则拒绝启动。
- 推荐公开模式是 loopback 鉴权入口 + Cloudflare Quick Tunnel，不开放路由器端口。
- 公开 URL 可以读控制台和修改后端白名单内的安全参数；钱包变更始终禁止。
- API 不返回 `config.json` 全量，不返回 Bridge Token、通知 secret、Codex 会话、平台凭据或私钥。
- Settings 不提供通用 JSON 编辑器，只允许显式白名单字段。

## 8. 真实性边界

- 动态界面只能动画化真实采集状态；最后观察时间过旧时必须显示 degraded/stale。
- 零事件、零 Token、零决策、零仓位或零成交都可能是正确状态。
- Paper PNL 始终标注 Paper/模拟。
- Paper 账户点 append-only；不得在同一时间桶内用后来状态覆盖先前状态，也不得用当前/未来报价回填过去权益。
- CANDIDATE 入场与退出触发后必须重新取得精确 Token 的新鲜模拟执行报价；过期、缺失、未来、错 Token 或执行失败只追加失败尝试，不生成成交。
- 新 Paper 成交必须记录固定不利滑点、每边手续费和快照中已知的 Token 税。未知税保持未知；没有可验证路由时不得声称已覆盖链费、priority fee、gas、MEV 或部分成交。
- 添加私钥不能解锁 Live。Paper 与未来 Live 可共享策略/风险/订单意图语义，但 Mainnet Broker、路由、回执对账、失败/重试、最小资金真链验证和独立复审仍是单独发布门。
- 来源影响力只能基于可审计元数据；缺失 follower、互动或验证状态时显示未知。
- 来源排序是审查顺序，不是真理判定。Follower 多不等于权威，官方也不意味着其内容一定满足入场资格。

## 9. 持续在线学习边界

- Runtime 可持续采集、形成 WAIT/CANDIDATE、监督 Paper 仓位并追加 shadow/Paper 结果；“实时”不等于每个新结果立即修改策略。
- 优化目标使用样本外、扣除费用后的风险调整表现，并同时检查最大回撤、尾部亏损、滑点/流动性、误报、漏检和发现延迟；不得只最大化历史累计 PNL。
- 观察轮换、频率或阈值调整必须满足既定多结果、多日期、亏损多样性和前向随访门，保留固定基线与探索比例，并记录版本、应用时间和回滚依据。
- 在没有足够闭仓样本或市场阶段覆盖时，正确动作是继续 Paper 与保持基线，不是放宽门槛、回填成功案例或反复调用更强 Agent 追求非空结论。
- Token Context 结果学习必须同时保留 `no_context`、Agent 错误、未核验候选和 missing；只使用 assessment 之后本机真实快照，历史 assessment 与缺失窗口不得回填。未核验人物姓名不能成为实体标签；精确原帖实体也不表示背书。该账本固定不改变 Agent 调度、证据资格、候选、风险、Paper 或 Live。
