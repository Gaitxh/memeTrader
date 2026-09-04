# ERR-20260905-003：DexScreener 极低流动性池导致 Paper PNL 虚高

状态：`FIXED`

代码修复已由提交 `51c0ab0`、`016a1b4` 完成；生产 correction/contamination 记录已追加，Runtime 与 8790 Web 已重启并完成最终运行态验收。

## 1. 错误指纹与时间

- 07 错误编号：`6`
- 组件：Paper 市场标记、持仓估值与 PNL 汇总
- 错误：DexScreener 屏幕价格在极低流动性池上直接乘以 synthetic Paper 数量，产生百万级或数万级虚假 PNL。
- 发现时间：2026-09-05（Asia/Shanghai）。
- 影响范围：生产历史估值、派生权益、策略排名及部分后续交易资格判断。

## 2. 用户影响

受影响的历史展示、账户权益和 PNL 统计可能被极低流动性池的屏幕价格严重放大，进而污染策略排名和结果解释。原始交易、Fill、行情快照和审计证据未被删除；该问题属于估值/结算语义错误，不是用户真实资产增加。

## 3. 根因

Paper 数量是 synthetic unit，不能在池子几乎没有可承接流动性的情况下，按 DexScreener 的屏幕价格无条件估算全仓价值。历史案例中池流动性降至 `0.04`、`0.24` 等数量级，仍将屏幕价格乘以 synthetic 数量，形成数万至百万级假 PNL。该计算忽略了池子的实际流动性容量和池是否仍可作为有效卖出依据。

## 4. 证据

- 受影响 Token 的同一池曾出现正常价格/流动性，随后 DexScreener 返回极低流动性（例如 `0.04`、`0.24`）。
- 异常 PNL 与 synthetic Paper 数量相乘产生，和可回收池容量不相称。
- 原始 ledger、市场标记和 Fill 证据仍保留；新增 correction 层用于记录纠正，不直接改写原账。
- 该证据支持“极低流动性估值不可作为正常可卖回收额”，但不等同于所有流动性异常的最终判定。
- Web 中出现的百万级 PNL 已确认属于该污染链路的展示/派生结果，不是实际账户收益。

## 5. 修复架构

- 新增不可变 correction 层，保存原始交易/Fill、纠正结果、原因和 supersession 关系，原始证据只读保留。
- 当 DexScreener 发现池仍存在且 `liquidity.usd >= 1` 时，按用户定义的 Paper 语义视为可卖；卖出时间点前后的池存在性按既定前向规则判断。
- 当 `liquidity.usd < 1` 时，剩余仓位按全部亏损处理，估值归零，不再用屏幕价格制造可回收权益。
- 汇总、快照和策略展示读取有效纠正结果，避免已确认的 dust-pool 异常继续进入正式 PNL；原始记录仍可追溯。
- synthetic Paper 数量不再被当作真实链上 mint raw amount 使用。
- 生产 correction ledger 采用 append-only 语义：共 `123` 条 base corrections；其中 `69` 条因 DexScreener `liquidity.usd < 1` 作为 `WRITEOFF`，`54` 条因 `liquidity.usd >= 1` 且同一池在卖出前后仍可见，恢复为原始 `SELL`。
- contamination ledger 共保留 `446` 条原始记录，其中 `212` 条已由最新有效 replay 解析为有效历史交易；剩余 `234` 条由旧版虚拟现金约束污染的 BUY 不再作为有效策略表现。该数字不是 dust-pool 后代数量，也不与 correction 数量相加。
- 无限 Paper funding activation 已记录在 snapshot `822722`；该时间点之后不再因虚拟现金不足拒绝 BUY，之前的历史规则和结果保持不变。

## 6. 验证

- 已增加并通过极低流动性池立即全损、异常估值不放大、纠正层保留原始证据等定向测试。
- 已对历史异常 Fill 建立 correction 记录并核对纠正后的汇总口径。
- 已在生产分析中识别 123 条 base corrections、69 条 dust writeoff、54 条 same-pair SELL restoration；446 条原始 legacy-cash contamination 中 212 条已解析、234 条仍为有效污染记录。
- 提交 `51c0ab0`、`016a1b4` 的定向测试与编译检查通过；完整 pytest、`compileall`、SQLite integrity 及在线 doctor 均通过。
- Runtime v22 与 8790 Web 重启后保持 127 个策略；Web 当前最大绝对已实现 PNL 约 `1243U`，百万级异常已从有效汇总和排名中消失。

## 7. 回退方法

如需回退展示层，只能切换 overlay 读取开关或回退对应代码提交；不得删除或覆盖 correction、contamination、原始交易、Fill 和市场快照。若重启后发现异常，先停止新派生结算并回到 `51c0ab0`/`016a1b4` 前一可验证提交，保留数据库追加记录。

## 8. 再次发生时的快速处理

1. 先按 Token、pair、采样时间检查 DexScreener 的 `liquidity.usd` 与价格原始证据。
2. 若流动性 `<1`，立即将剩余仓位按全损处理，并写入不可变 correction，不改原账。
3. 比对纠正前后 PNL、权益和策略排名，确认异常大数已从有效汇总中移除。
4. 若流动性不低于 `1` 但屏幕估值看似异常，只记录为观察性诊断；按当前 Paper 规则不得因此新增容量 veto、改变卖出资格或改写 PNL。

## 9. 遗留风险

DexScreener 的价格和流动性是屏幕市场数据，可能短暂滞后或与真实可执行回收额不同。`liquidity.usd >= 1` 是当前 Paper 的用户约定口径，不是对真实成交的保证。`234` 条 legacy-cash 污染记录已从有效统计排除。原始证据永久保留，污染记录不得作为策略优劣依据。
