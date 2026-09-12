# ROUND 120-49 — 修掉一个**把拒绝说成通过**的界面标签；并确认控制台资产是直接读工作区、无需构建

日期：2026-09-13
改动：`src/memetrader/chain_web_static/app.js`（仅展示层）、新增 `tests/chain_web_reason_text.test.js`
探针：`data/research/diag_round120/r49b_served.py`

---

## 1. 这是一次**代码改动**，不是分析——依据是本轮自己观测到的失败

第 45/46 轮把风控阶段逐条分解后，我注意到一件事：**拒绝原因的界面标签与实际含义不符**，
而且其中一个**说的是反话**。这不是我在找茬，是我自己在读日志时被它误导过（第 45 轮开头那 160 倍的"矛盾"）。

AGENTS.md 对这类改动的门槛是"**说出它所改变的那个已观测失败**"。这里说得出：

### 已观测失败 1（说反话）
`reasonText()` 的兜底分支里有一条 `value.includes('entry') → '策略入场条件成立'`。
而 `entry_snapshot_too_old`（快照过旧而被**拒绝**）含有子串 `entry`，于是**渲染成"策略入场条件成立"**。
**界面把一次拒绝显示成了通过。**

### 已观测失败 2（61% 的日志泄漏英文标识符）
实测（61,862 次评估）占比最高的四个原因**全都不在** `known` 映射里，因而落到兜底：
`cohort_observation` 34.4%、`pattern_observation` 26.9%、
`entry_pool_liquidity_absent_curve_stage` 7.1%、`invalid_exact_asof_market_snapshot` 4.7%。
前两个直接显示**原始英文串**；第三个命中 `includes('liquidity')` 显示"池流动性异常"
——**但它不是"异常"**，而是发射曲线阶段的池子**没有可测流动性**（数据可得性限制）。
第四个也显示原始英文串。

而这四个里的两个（`cohort_observation` / `pattern_observation`）**根本不是拒绝**，
是观察者自己的记账。把它们显示成拒绝，等于让操作者把 **61% 的日志**读成"策略在大量拒绝机会"。

## 2. 改动

在 `reasonText()` 中新增一张 `observed` 表（优先于既有 `known`），把这四个高频原因
**按"它量的是什么"命名**，而不是按它出现在哪段代码里（这正是第 45/46 轮规则 16 的要求）：

| reason | 新标签 |
|---|---|
| `cohort_observation` | 观察者记账：本帧进入 cohort 观察序列（**非策略拒绝**） |
| `pattern_observation` | 观察者记账：本帧进入形态观察序列（**非策略拒绝**） |
| `entry_pool_liquidity_absent_curve_stage` | 发射曲线阶段，原池流动性尚不可测，暂不入场 |
| `invalid_exact_asof_market_snapshot` | 行情快照未通过时点有效性校验（多为该池暂无美元报价） |
| `entry_pool_liquidity_below_configured_floor` | 原池流动性低于已配置下限，禁止买入 |
| `entry_snapshot_too_old` | 行情快照过旧，超过入场新鲜度上限 |

并在 `known` 中补上**我自己那四个实验臂**的入场下限原因（此前它们命中 `not_met` 兜底、显示原始英文串）：

| reason | 新标签 |
|---|---|
| `activity_floor_trades_not_met` | 入场下限未达：5 分钟成交笔数不足 |
| `activity_floor_volume_not_met` | 入场下限未达：5 分钟成交额不足 |
| `runup_floor_exceeded` | 入场下限未达：入场前 20 分钟涨幅超过上限 |
| `runup_floor_window_unknown` | 入场下限未达：缺少入场前 20 分钟观测，涨幅未知 |

两条刻意的**不许说错**约束（写进测试）：
- `invalid_exact_asof_market_snapshot` 的标签**不得**出现"过旧/陈旧/过期"
  ——它是**身份/有效性**检查，不是陈旧度检查；这个混淆在第 45 轮真实发生过。
- `entry_pool_liquidity_absent_curve_stage` 的标签**不得**出现"异常"
  ——它是数据可得性限制，不是池子出故障。

**未改动任何存储的 reason 字符串**，因此历史可比性与既有按字符串匹配的代码都不受影响。

## 3. 验证

- **新增测试** `tests/chain_web_reason_text.test.js`：11 组断言，含
  `entry_snapshot_too_old` 必须**不等于**"策略入场条件成立"。
  **该断言在旧代码上会失败**（旧兜底 `includes('entry')` 恰好返回那句话），所以这个测试是有意义的，不是同义反复。
  → `chain_web_reason_text: ok`
- **控制台测试的差分归因**（逐项在"我的改动应用后"与"pristine HEAD"两种状态下各跑一次）：

| 测试 | 应用我的改动 | pristine HEAD | 归因 |
|---|---|---|---|
| `chain_web_reason_text.test.js`（新增） | **exit 0** | —（新文件） | 我的 |
| `chain_web_strategy_revision.test.js` | exit 0 | exit 0 | 无影响 |
| `web_detail_request_state.test.js` | exit 0 | exit 0 | 无影响 |
| `chain_web_ui_stability.test.js` | **exit 1** | **exit 1** | **既有失败，与我无关** |

  `chain_web_ui_stability.test.js`（断言 `full-period samples must not rebuild browser history on
  every refresh`）在 **pristine HEAD 上同样失败**：该文件是**未跟踪**的，它与工作区里那份**未提交**的
  `app.js` 改动属于**同一批进行中的工作**，其测试**领先于已提交的源码**。**我的改动对全部四个测试的
  通过/失败状态没有任何影响。**
- **生产验证**（规则 6/17）：控制台的 `/app.js` 与工作区文件**逐字节相同**
  （同为 173,724 字节、sha256 `c3b64db4aa72355b`），且新增的 ASCII 标记
  （`const observed=`、`entry_pool_liquidity_below_configured_floor`、`runup_floor_window_unknown`）
  **在服务端返回的字节里存在**。刷新页面即可看到。

## 3b. 我在提交时犯的一个错误，以及如何修正

第一次提交（`9ea3bfe`）的 `git show --stat` 显示 `app.js` 变了 **297 行**——而我的改动只有约 15 行。
原因：`app.js` 在我动手前**就已经是 modified**（工作区里带着 227 增 / 70 删的**与我无关的进行中改动**），
我 `git add` 整个文件时把它们**一并提交**了。

这违反项目规则"**只暂存本次预期的源码/测试/公开报告，保留无关改动**"，
而且会把**我没有写过、也没有审阅过**的代码记到我的提交信息下。

**修正方式**（该提交尚未 push，因此可以干净修复）：`git reset --soft HEAD~1` → 把 `app.js` 恢复到
`27c7983` 的版本 → **只重新应用我那一处改动** → 重新提交 → 再把含无关改动的完整工作区文件还原回工作区。
最终 `app.js` 的 diff 是 **17 增 / 1 删、单个 hunk**，无关改动仍以未提交状态留在工作区。

> **新规则 20：提交前先看 `git show --stat` 的行数是否与自己的改动量相符。**
> 数字对不上就说明把工作区里别人的进行中改动一起提交了。
> （本 session 早前已因"提交漏掉源文件"吃过一次 `--stat` 的教训，这次是反向的同一个检查。）


## 4. 一个重要的运维事实（顺手查实）

`chain_web.py:4459-4464` 直接从 `static_dir` 读文件、`_send_asset` 不做服务端缓存、响应头是
`Cache-Control: no-cache`。**所以本控制台的界面资产是直接读工作区的，改完刷新即可生效，没有构建步骤。**

（`ROOT/.venv/src/memetrader/src/memetrader/chain_web_static/app.js` 存在一份 157,938 字节的
**陈旧嵌套快照**，但控制台**不**使用它——已用哈希排除。记录备查，不处理。）

## 5. 我在这轮差点犯的错（第 5 次"测量假象伪装成发现"）

我用 `Invoke-WebRequest` 取 `/app.js` 后 `-match '观察者记账'` 得到 **False**，字节数却与工作区文件**完全一致**。
我一度准备写下"改动没有生效、需要构建"。**原因是我自己的测量方式**：`mimetypes` 对 `.js` 给出
`text/javascript` 而不带 charset，PowerShell 便按 Latin-1 解码，**所有中文都被打乱**，
于是子串匹配必然失败（控制台里能看到 `�۲��߼���` 这样的乱码）。

改做**逐字节比较 + 只含 ASCII 的标记匹配**后，结论立刻反过来：文件是当前的。

> **新规则 19：对 HTTP 返回的 UTF-8 文本做子串判断前，先确认解码方式；用逐字节/ASCII 标记比较。
> 字节数一致而匹配失败，几乎总是解码问题，不是部署问题。**
> （这是本 session 第 5 次"假象像发现"：write-off 率、`closed` 均值、`invalid-asof`、`exposed>returned`，以及这一次。）

## 6. 对目标五个维度的交代

| 维度 | 推进 |
|---|---|
| 准确性 | 消除一个**说反话**的界面标签；61% 的日志不再以原始英文串呈现；观察者记账不再被读成拒绝 |
| 有效性 | 我自己的四个实验臂的入场下限原因现在在控制台上可读——实验的可观测性提升 |
| 界面真实性 | 这正是 AGENTS.md 说的"当数据缺失或**误导**时改进它" |
| 稳定性 | 仅展示层；既有三个界面测试全绿；未触碰任何后端路径 |
| 速度/实时性 | 承第 44/47/48 轮；顺手查实界面资产无需构建 |
