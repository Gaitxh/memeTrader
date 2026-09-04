# ChatGPT ↔ Codex 双向通信运行手册

状态：`ACTIVE / DETAILED_COMPANION`
协议：`GXH_C2C_V3`
快速联系卡：[`../../CHATGPT_CONTACT.md`](../../CHATGPT_CONTACT.md)
更新时间：`2026-09-03T08:48:19Z`

发生冲突时，以根目录 `CHATGPT_CONTACT.md` 的当前端点和 `CHATGPT_CODEX_SYNC_STATE.json` 的当前路由为准；本文只补充详细状态机、故障转移、多聊天和需求治理规则，不建立第二套协议。

## 1. 目的与边界

本通道只用于让 Codex 与指定的主协调 ChatGPT 互相发起、续接、审查和确认信息。它不能改变项目目的、当前 P0/P1、固化规则、实验定义、Paper/Live 边界或代码写入权。

- Codex 主线程仍是唯一代码、测试、SQLite、部署和受控重启写入者。
- 主协调 ChatGPT 负责目标守护、研究、因果/统计与交易经济性复核、跨聊天去重和冲突综合。
- 独立 reviewer 默认只读，结论先回主协调 ChatGPT；不得直接形成互相竞争的实现指令。
- 当前代码、r6 SQLite、测试、进程和权威计划始终高于聊天、邮件箱与本手册。

## 2. 快速联系卡

Codex 每次联系前只需先读：

1. `docs/PROJECT_CONTEXT/CHATGPT_CODEX_SYNC_STATE.json`
2. 其中 `coordination_mode.review_coordinator.conversation_id`
3. 当前 `active_cycle` 与相关 `open_groups`

当前项目标识：`g-p-6a6ae7ab5ba88191a99ff26a42f446e8`
当前 Codex 执行线程：`01a0514b-bbb5-7400-baf9-d9feb4dc603d`

主协调 ChatGPT 会话 ID 不在本手册中固化为长期常量；以同步指针中的当前值为准，避免换会话后继续向旧会话发送。

## 3. Codex 怎样“启动”或唤醒 ChatGPT

ChatGPT 不是需要在本机另起的常驻进程。对现有主协调会话发送一条消息，就是启动/唤醒/继续该 ChatGPT 的正常方式。

### 主路径

1. 读取同步指针，取得当前主协调会话 ID。
2. 使用 `codex_app.send_message_to_thread` 向该会话发送一个通常小于 2 KB 的结构化消息。
3. 不重复发送同一个 `MESSAGE_ID`。
4. 使用 `codex_app.read_thread` 从同一会话读取回答；回答尚在生成时只继续读取，不重发问题。
5. Codex核对回答后，才把被接受的决定写入代码、计划、需求台账或同步邮箱。

示例调用形态：

```text
send_message_to_thread(
  threadId = SYNC_STATE.coordination_mode.review_coordinator.conversation_id,
  prompt   = <C2C envelope>
)

read_thread(
  threadId = same_thread_id,
  turnLimit = 2,
  includeOutputs = false
)
```

禁止为了注入一条消息而运行第二个 `codex exec resume`、启动第二个写入者、重开同一工作树，或另起浏览器自动化流程。

## 4. Codex 可以发送哪些消息

允许的主要类型：

- `PING`：唤醒主协调会话并确认当前目标/周期。
- `QUESTION`：请求一个小范围判断、研究或替代路径。
- `CHECKPOINT`：报告 Codex 已核验和完成的事实增量。
- `BLOCKER`：报告阻塞发布或可能污染前向分母/生产的事实。
- `DEPLOY_GATE`：请求部署前后的因果、交易经济性或运行门复核。
- `NATURAL_SAMPLE`：首个会改变解释的自然 cohort、terminal 或 Paper 结果。
- `HANDOFF`：仅在主协调会话失效或达到上下文边界时转移最小上下文。

需要独立 reviewer 时，仍以 `QUESTION` 或 `DEPLOY_GATE` 发给主协调 ChatGPT，由主协调者决定是否开启角色化 reviewer；Codex 不并行创建互相竞争的实施指令。

正式双向消息使用同一信封：

```text
[GXH_C2C_V3]
MESSAGE_ID: C2C-YYYYMMDD-HHMMSS-CODEX
REPLY_TO: <message id, or NONE>
TYPE: QUESTION | RESEARCH | REVIEW | IMPLEMENT | CHECKPOINT | NATURAL_SAMPLE | BLOCKER | DEPLOY_GATE | ACK | RESULT
PRIORITY: NORMAL | HIGH | URGENT
CYCLE_ID: <active cycle>
FACT_CUTOFF_UTC: <timestamp>
ISSUE_ID: <stable dedupe key>
SENDER: CODEX
TARGET: CHATGPT_LEAD
BLOCKS_RELEASE: true | false

ARTIFACT_POINTERS:
- <small list of paths, methods and test ids; no pasted logs/diffs>

SUMMARY:
<only new facts>

ACTION_REQUESTED:
<one precise question or ACK_ONLY>

NEXT_SYNC_EVENT: <event that warrants another message>
SENSITIVE_DATA: NONE
```

`IMMUTABLE` 指 registration、activation、definition hash 和 append-only 行；`SNAPSHOT` 指当前 ID、计数、PID 和 health，相关写入、部署或重启后必须重新读取。敏感数据一律不发送。

如需明确回复通道，可在 `DELTA` 末尾写：

```text
REPLY_CHANNEL: direct-if-available + durable-mailbox
SENSITIVE_DATA: NONE
```

同一 `CYCLE_ID + ISSUE_ID` 没有更新的事实截止点或实质新证据时，不得再发一条重复实现请求。

## 5. ChatGPT 怎样把信息交还给 Codex

### 对 Codex 主动发起的问题

ChatGPT 在同一会话中回答，并带回：

```text
[GXH_C2C_V3]
MESSAGE_ID: <new ChatGPT message id>
REPLY_TO: <Codex MESSAGE_ID>
TYPE: ACK
SENDER: CHATGPT
TARGET: CODEX_THREAD
ISSUE_ID: <same issue id>
ACK_STATUS: RECEIVED | PROCESSING | DEFERRED | BLOCKED | REJECTED
UNDERSTANDING: <one-sentence understanding>
NEXT_ACTION: <next action>
NEXT_SYNC_EVENT: <event>
```

研究或执行完成后另发 `TYPE: RESULT`，沿用同一 `ISSUE_ID` 并 `REPLY_TO` 原请求；必须给出 `DISPOSITION`、结果、验证证据、真正变化、未变化边界、开放项和下一建议动作。ACK 不等于 RESULT。

Codex 通过 `read_thread` 收取，不需要用户复制粘贴。

### ChatGPT 主动发现的新问题或需要唤醒 Codex

主协调 ChatGPT 可以使用 Codex Desktop 当前暴露的 `codex_app.send_message_to_thread`，向同步指针中的精确 Codex 执行线程 ID 发送同一 `[GXH_C2C_V3]` 信封。这会把消息交给现有主线程，不启动第二个 Codex、不创建第二个 writer，也不要求用户复制粘贴。用户已明确授权在必要时强制提醒/插队，因此方向偏移、遗漏高优先级用户规则或明显更优路径可使用 `PRIORITY: URGENT`；普通局部意见仍按事件驱动门槛发送。Common Space、mailbox 和 `attention_required` 只提供耐久可见性，**不等同于实时送达**。

同时，ChatGPT 将需要持久保存的决定或未解决冲突追加到：

- `docs/PROJECT_CONTEXT/CHATGPT_CODEX_SYNC.md`
- 并更新 `CHATGPT_CODEX_SYNC_STATE.json` 的 `open_groups`、`attention_required` 和事实截止点。

Codex 在重大周期开始/结束、部署前和 `attention_required=true` 时读取。紧急项只有在明确标记 `BLOCKS_RELEASE=true` 且给出当前代码/数据证据时才阻塞相关发布；正常 Paper 运行不因此停止。直接消息用于及时唤醒，邮箱和指针用于耐久恢复，两者不是相互竞争的真相源。

## 6. 收件、确认与状态机

每条需要回答的消息按以下状态处理：

```text
CREATED → SEND_ACCEPTED → DELIVERED → ACKNOWLEDGED → PROCESSING
        → RESULT_SENT → RESULT_ACKNOWLEDGED → CLOSED
```

异常状态为 `SEND_FAILED`、`DELIVERY_UNVERIFIED`、`ACK_TIMEOUT`、`BLOCKED`、`SUPERSEDED`、`REJECTED`。

规则：

- `SEND_ACCEPTED` 只表示发送工具返回成功；只有在目标 thread 的 `read_thread`/结构化 rollout 中找到相同唯一 `MESSAGE_ID`，才能标记 `DELIVERED`。
- `DELIVERED` 仍不表示接收方已理解或执行；只有显式 `TYPE: ACK` 且 `REPLY_TO` 正确，才能标记 `ACKNOWLEDGED`。
- `ACK_STATUS: PROCESSING` 可把确认与开始处理合并；长推理期间无回复保持 `DELIVERED / WAITING_ACK`，不得重复发送。
- 完成必须由 `TYPE: RESULT`、正确 `REPLY_TO` 和真实验证证据表示；原发送方读到结果后标记 `RESULT_ACKNOWLEDGED`。只有验收满足且无 blocker 才能 `CLOSED`。
- 同一 `MESSAGE_ID` 最多正常发送一次；明确重试必须生成新 ID 并带 `RETRY_OF`。
- 发送一次后等待同一会话回答；页面慢、模型仍生成或一次读取无结果不等于失败。
- 收到回答后先核对当前代码/SQLite/测试，不因模型自述直接采纳。
- 只有被核验并写入权威计划/需求台账的结论才有执行权。
- 纯通信 ACK 不创建产品需求。
- 大日志、完整 diff、数据库 dump、聊天历史和敏感配置永远不进入消息体；只发文件/方法/测试指针。

`QUESTION`、`RESEARCH`、`REVIEW`、`IMPLEMENT`、`BLOCKER`、`DEPLOY_GATE` 和 `RESULT` 必须 ACK；会改变决策的 `NATURAL_SAMPLE` 必须 ACK；`CHECKPOINT` 可选。优先级仅按事实使用：`URGENT` 限 future-data/账本污染/错误 Paper PNL/Live 或安全风险、错误版本采样及必然失败的下一次部署；`HIGH` 在当前小步骤后处理；`NORMAL` 不打断 coherent task。

主动协作由事件触发：多个高影响方案、连续两次局部修复失败、长期零交易或异常经济结果、策略/Policy Arm/动态退出/仓位/链执行设计、晋级成熟门、因果污染风险、OSS/官方数据源取舍、新前向证据推翻假设或疑似局部最优。机械低风险代码修改无需调用 Lead。详细事实先写 Common Space，消息只发 delta 和指针；Codex等待研究时继续不冲突 tranche。根因明确、实现完成、最小测试通过且前向观察启动后，停止无新增证据的往返审查。

## 7. 会话失效、上下文上限与 Lead 换代

主协调 ChatGPT 不是永久会话。任何 Lead 都可能遇到上下文上限，因此**跨代连续性必须来自 `E:\memeTrader`，不能依赖旧聊天还能记住多少**。耐久换代状态统一读取：

- `docs/PROJECT_CONTEXT/CHATGPT_LEAD_ROLLOVER_STATE.json`
- `docs/PROJECT_CONTEXT/CHATGPT_LEAD_STATE.json`
- 以及 rollover state 中列出的 `mandatory_boot_read_set`

只有以下情况才更换主协调 ChatGPT：

- 当前会话不存在、404 或明确不可继续；
- 当前会话已接近/达到上下文边界，Lead 主动报告连续性风险；
- 当前会话明显变慢或降质，已经影响可靠推理；
- 用户明确指定更换主协调会话。

一次慢回复、一次 MCP 超时、长推理或普通网络错误不构成换代理由。

故障转移/主动 rollover 顺序：

1. 旧 Lead 在还能工作的情况下，先更新 E 盘 `CHATGPT_LEAD_STATE.json`、`CHATGPT_LEAD_JOURNAL.md` 与 `CHATGPT_LEAD_ROLLOVER_STATE.json.current_checkpoint`；只保存结论、事实指针、未解决问题和下一步，不保存私有思维链或敏感值。
2. Codex 用 `codex_app.list_threads` 确认当前 Lead 是否确实需要换代，不能只凭一次读取超时判断失效。
3. 需要换代时，使用 `codex_app.create_thread` 在同一 **GXH coin** 项目中只创建 **一个** 新主协调 ChatGPT；不得同时保留两个 implementation-facing Lead。
4. 新会话只接收小于约 2 KB 的最小 `HANDOFF`：rollover generation、旧 Lead ID、原因、fact cutoff、active cycle、完成 delta、未解决问题、下一步，以及 `CHATGPT_LEAD_ROLLOVER_STATE.json` 路径。不得粘贴代码、diff、日志、139 条历史消息或整段聊天。
5. 新 Lead 必须先通过 `@笔记本mcp...` 读取 rollover state 的 `mandatory_boot_read_set`，再从 `CHATGPT_CODEX_SYNC_STATE.json` 取得**当前** active cycle；E 盘文件与当前代码/SQLite事实高于 handoff 摘要。
6. 新 Lead 完成 boot self-check：明确 North Star、当前 P0、one-writer/Live/future-data 边界、恢复后的用户规则和唯一下一步，并核对 Codex execution thread ID。校验失败时不得修改 coordinator ID。
7. 只有 boot self-check 成功后，才把 `CHATGPT_CODEX_SYNC_STATE.json`、`CHATGPT_CONTACT.md` 与 rollover state 里的 coordinator/Lead ID 原子地从旧→新重绑，`generation += 1`；旧 Lead 加入 `superseded_lead_conversation_ids` 并标记 `SUPERSEDED`。
8. 重绑后只有新 Lead 能向 Codex 发 implementation-facing synthesis；旧会话若后来恢复，只能作为历史证据，不得重新夺回协调权。

如果旧 Lead 已经突然不可读，也不需要从聊天恢复：Codex 直接使用 rollover state 的最后 E 盘 checkpoint + mandatory boot read set 创建新 Lead。创建独立 reviewer 与更换主协调会话不是一回事；Reviewer 使用角色化标题和独立问题，完成后退出实施链。

## 8. 多聊天拓扑

正常状态：

- 主协调 ChatGPT：1 个。
- Codex 执行线程：1 个。
- 临时 reviewer：0–3 个，仅在重大架构、策略、实验或部署门启用。

Reviewer 必须带角色：

- `CAUSAL_STATISTICAL`
- `TRADING_ECONOMICS`
- `MIN_ENGINEERING_RUNTIME`
- 必要时 `ADVERSARIAL_ARCHITECTURE`

主协调 ChatGPT 合并冲突后只向 Codex 发一份实现导向结论。不得让多个聊天直接对同一 dirty checkout 发不同修改指令。

## 9. 历史需求、建议与新想法

所有历史需求与建议进入三条治理通道：

- `FROZEN_CONTRACT`：最新用户明确指令、安全边界、根 `AGENTS.md` 固化规则、不可变注册定义。
- `ACTIVE_PLAN`：当前权威 P0/P1 和已在需求台账晋级的事项。
- `IDEA_INBOX`：历史建议、未证实想法和 reviewer 提案；保留但无执行权。

任何想法要改变当前范围，必须说明它改变的真实瓶颈、当前证据、可证伪前向测试、预期信息或净 EV 增益、成本风险、挤占代价和固化规则影响，并被正式处置为 `PROMOTE_NOW`。实现容易、被多次提到或听起来先进，都不构成晋级理由。

## 10. 安全与零污染

通信中禁止包含：

- 私钥、助记词、钱包材料；
- 密码、Cookie、Session、验证码、OAuth/API secret；
- `config.json` 敏感字段和 bridge token；
- 私人聊天、联系人、无关个人文件；
- SQLite dump、完整日志或大 diff。

通道不能开启 Live、改变生产证据门、增加生产 Agent 并发、修改已注册实验或绕过当前执行计划。

## 11. 当前验收状态与按需健康探针

双向主路径已经有真实使用证据。Codex→ChatGPT 此前已直接向同步指针指定的主协调 ChatGPT 会话发送结构化 `SYNC_ACK/CHECKPOINT`，并使用 `read_thread` 回读独立 ChatGPT 会话。ChatGPT→Codex 于 **2026-09-02 21:58:52 +08:00** 首次完成严格可核验的强制直投：`MESSAGE_ID=C2C-20260902-2149-LEAD-FORCE-SYNC-001` 通过 `codex_app.send_message_to_thread` 指向主执行线程 `01a0514b-bbb5-7400-baf9-d9feb4dc603d`，随后在该线程结构化 rollout 中检出完全相同的 `MESSAGE_ID` 和正文，因此先标记 `DELIVERED`。**2026-09-02 22:00:12 +08:00** Codex 在同一主 thread 显式回复 `ACK C2C-20260902-2149-LEAD-FORCE-SYNC-001`，确认六份 E: 材料已完整读取并与当前事实对齐；随后写入 `COMMON_SPACE/.../CODEX.md` 并清除 sync pointer 的 `attention_required`，因此该消息现为 `ACKED`。这一证据也纠正了此前的错误假设：Common Space/mailbox/hook 是耐久层，不证明实时投递。

只有会话 ID 重绑、直接投递失败或回读结果无法关联时，才执行一次不阻塞产品发布的健康探针：

1. 向同步指针指定的主协调会话发送 `TYPE: PING`，带唯一 `MESSAGE_ID`。
2. 请求只回复 `TYPE: CHANNEL_ACK + REPLY_TO + coordinator conversation id + active cycle`。
3. Codex 用 `read_thread` 从同一会话收到并核对相关 ID。
4. 仅在端点或状态改变时更新联系卡与同步指针；成功且无变化时不制造重复邮箱条目。

健康探针只验证通信链，不触碰代码、Runtime、数据库、Paper 或 Live。
