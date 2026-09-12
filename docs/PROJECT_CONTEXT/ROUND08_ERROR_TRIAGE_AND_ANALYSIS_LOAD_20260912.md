# 第 8 轮：错误分诊（无本目标回归）+ 重分析查询与写锁的相关性

- 记录时间：2026-09-12T03:45Z（北京时间 11:45）
- 约束不变：`mode=paper`、`live.enabled=false`、现有策略规则零改动；policy additions 278

## 1. 错误分诊：`#267`–`#276` 全部与策略/退出无关

| id | 组件 | 类型 | 次数 | 状态 |
|---|---|---|---|---|
| 267 | dexscreener:profile_updates | ReadTimeout | 1 | fixed |
| 268 | capital_quote | OperationalError: **database is locked** | 3 | new |
| 269 | chain_meme_trader | OperationalError: **database is locked** | 2 | new |
| 270 | chain_meme_cohort_observer | OperationalError: **database is locked** | 3 | new |
| 271/273 | pumpportal:metadata | IPFS 网关超时 | 1/1 | new |
| 272 | multichain_meme_data | database is locked | 1 | new |
| 274/275/276 | geckoterminal / dexscreener | ReadError / RemoteProtocolError | 1/1/1 | fixed |

- **结论**：没有一条来自本目标新增的代码路径（机制、守卫、账本）；冻结的 `#265`/`#266` 亦未增长。
  网络类属外部探测失败（项目规则：挂起的外部探测既不是 PASS 也不是本地缺陷证明）。

## 2. 新发现：`database is locked` 与"重分析查询"时间相关

`#268`/`#269`/`#270`/`#272` 共 9 次 `database is locked`，最后发生时间与本轮密集运行只读分析脚本
（监督快照、交易上下文账本、复盘、尘埃报价窗口统计）的时段重合。机理：39 GB 数据库运行在 WAL 模式，
**长事务读者不会直接阻塞写者，但会阻止 WAL 检查点回收**，进而让写者在检查点/文件增长时短暂拿不到锁。
本目标的诊断脚本大量使用 `julianday(...)` 窗口与窗口函数（无法走索引），单次可能扫描数十万行。

**缓解（不改运行时代码，仅约束我们自己的诊断方式）**：
1. 诊断脚本继续以 **id 前沿 + LIMIT** 为主（监督快照已如此），避免全表 `julianday` 扫描；
2. 同一时段不要连续背靠背跑多个重扫描脚本（本轮曾串行运行 4 个）；
3. 需要长窗口统计时优先用 id 前沿采样 + 精确跨度换算速率，而不是对全表做时间过滤；
4. 若 `database is locked` 频率继续上升，下一步考虑把重统计改到数据库**副本**上执行
   （`VACUUM INTO` 或 `sqlite3 .backup`）而不是活库。

## 3. 本轮其余观测

- **尘埃报价**：近 60 分钟 2,004 条标记中 4 条为尘埃离群报价；守卫 `kv['mark-outlier-vetos']` 尚未写入
  （节流为每 25 次一条，说明累计 veto < 25，与偶发频率一致）。
- **第 28 波臂已开始产生自然样本**：`alpha149_long_hold_open_band_v1` 与 `alpha149_long_hold_control_v1`
  各有 2 笔开仓（同入场、不同合同，A/B 已配对）；`alpha149_thin_depth_tier_v1` 就绪 0 次、
  暂无样本（该档需要 1000–5000U 深度且池龄 30–180 分钟，后续继续观察是否可达）。
- 当前进程机制就绪：`survivable_open_band` 197、`open_band_scored` 61、`mom_persistence` 19。

## 4. 下一轮计划

1. 继续累积第 28 波 A/B 自然样本（各需 ≥20 笔）；
2. 实现"死池前兆提前离场"额外臂（深度净流出速度 + 换手枯竭，同入场 A/B）；
3. 若 `thin_depth_tier` 在下一轮仍为 0 就绪，按"不可达"单独诊断（而不是调阈值）；
4. 把"重统计改到副本"作为诊断侧的可选项落实，避免影响写入进程。
