# 全面审查后的局部修复与验收（2026-09-07）

用户要求在全面了解、审查和回顾的基础上修正问题。本阶段修复代码为 `4686157`，2026-09-07T09:19:47.2065738Z按原Paper/Web脚本部署。完整审查基线见 `COMPREHENSIVE_REVIEW_1700.md`；该报告保留当时发现，不将后来修复回写成过去已经正确。

## 已修正

| 问题 | 改动及边界 |
|---|---|
| Gecko新池缓存重标观察时间 | 沿用HttpClient首次响应observed_at；缓存不再重标为新行情。当前通常90秒间隔大于20秒TTL，本次验证的是重复调用合同，不冒称此前生产已发生多少污染。 |
| 单轮新池挤掉passive cohort前部观察 | 每个新池响应投递一个批次，按snapshot ID保留同Token兄弟池。13条含兄弟池的回归全部进入同一批次；不扩容8批队列、不增加请求。 |
| 队列容量限制静默丢弃 | 现有cohort状态保存累计dropped_batches/dropped_quotes，重启恢复；沿用60秒持久化频率。不是全市场漏失数，突然退出可能损失最后一个保存周期的计数。 |
| DS429遗漏共享退避 | 复用既有Retry-After解析与共享deadline；并发成功或较短失败不清除尚未结束的冷却，非429行为保留。 |
| 长Retry-After使主持仓轮次长期等待 | 高优先批次返回明确本地deferred（None），释放Semaphore/active idle并排独立补源；不伪装空行情、不写失败或刷新数据。入队后才出现冷却也有覆盖。 |
| 缺池超过60秒的遗留核销 | 删除普通市场价路径的missing→RUG转换，结算拒绝缺少terminal_dust_pool证据的旧意图；新鲜原池低于门槛仍可核销。旧独立quote合同和历史记录不改写。 |
| Web把数量分组称为成熟 | 改为终结样本≥30、10–29、<10，并解释数量和相关性边界；API枚举、排序、策略规则不变。 |
| 历史台账和部署图误导 | 两份文档顶部明确8790、独立1000U、默认4%/4%/0U/1000USD、自动复盘暂停及初始化授权已使用；旧资料留档。 |

HTTP处理依据核对了 [HTTPX异常层级](https://www.python-httpx.org/exceptions/) 与 [Retry-After语义](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Retry-After)，复用现有客户端而未建立新调度系统。

## 定向验证

55个不同测试用例最终通过，未跑全套：

- `tests/test_audit_cache_20260907.py`
- `tests/test_chain_meme_pool_identity.py`
- `tests/test_market_api_runtime.py`及其本轮新增冷却/批次用例
- `tests/test_runtime_shared_writer_thread.py`
- `tests/test_runtime.py`中的既有transport/shared semaphore退避用例、本轮HTTP status并发冷却及排队期间冷却用例
- `tests/test_cohort_store.py::test_runtime_passive_cohort_consumes_received_batches_without_requests`

第一组52项为51通过、1失败，失败因新增夹具实际13条而断言12；修正计数。第二组6项为5通过、1失败，新增冷却夹具尚未创建RuntimeTiming；补齐实际运行中已有的对象后该项单独通过。后续仅重复受变更影响的用例，没有放宽生产时间/身份/成本断言。

`node --check src/memetrader/chain_web_static/app.js`、`git diff --check`通过。纯文案未增加测试框架。

## 部署边界

停止前现场解析Paper和8790 Web的监督/子进程树，只停止该树；使用现有 `scripts/run_paper.ps1`、`scripts/run_chain_web.ps1` 隐藏启动，无初始化参数。初始新监督PID19656/20816仅为当时事实。

09:20:33Z，health为running，仍224账户、97条addition；当前注册原文摘要、addition完整行摘要、资金activation逐项与部署前相同。四执行设置仍400bps/400bps/0U/1000USD，Live locked。最新账户快照09:20:25Z，说明启动后账户处理继续。两份新stderr为0字节，不代表上游不再报错。

部署前采样09:17:32Z的交易前沿479129，在09:20时为479139；这些新增交易实际发生于09:19:47重启之前，因此不能作为部署后自然交易证据。原始比较见 `REPAIR_1700_BOUNDARY.json`，自然验收另按实际created_at划分。

## 自然运行与独立账例

部署后SELL479140于09:20:41.965661Z完成：`bundle_adjusted_breadth_v1`/cohort56612的旧仓，BUY479095投入20U，终结净回款18.46153846153846U，PNL−1.53846153846154U，与positions一致；剩余数量0、累计成本分配20U。mark242876从09:20:40.821416Z触发到09:20:41.964471Z原池观察，严格晚1.143055秒；原池流动性2341.4USD。

该账户快照2137563（09:20:45.951813Z/frontier479140）内46笔净现金流及已实现PNL均−32.88008431741005U，所以现金=1000−32.88008431741005=967.11991568259U；开放仓0、权益等于现金，无corrections/contaminations/credits。独立查询为SQLite mode=ro，按账户和前沿有界抽验，没有修改账本。

截至09:22:26Z，另有新BUY479141（09:22:11.132255Z），故部署后自然窗口为1 BUY、1 SELL、0 WRITEOFF。尚未自然覆盖partial、低池核销或缺池路径；这些由对应离线Store测试验证，不声称所有224策略自然验收完成。Web实际HTTP返回新样本分组文字，未声称逐控件浏览器操作验收。

| 近期P95（秒） | 部署前 | 部署后 |
|---|---:|---:|
| 主循环实际间隔 | 1.143 | 1.159 |
| 持仓行情实际间隔 | 1.815 | 1.584 |
| 持仓fetch耗时 | 1.150 | 1.324 |
| 持仓apply/exit耗时 | .028 | .030 |
| pattern实际间隔 | 15.210 | 15.014 |
| passive cohort耗时 | 1.044 | .946 |

主/持仓最近120样本，pattern部署后10样本、cohort14样本；持仓组成和上游负载不完全相同，不能宣称因果提速或长期无回退。本窗未见明显本地处理退化，但SOL最旧所需原池观察70.94秒、RH54.92秒，部分7个SOL Token仍报行情失败。

现有cohort状态已自然保存`dropped_batches=309`、`dropped_quotes=2464`：即便整响应投递纠正，其他行情批次仍会超过8批容量。本次使容量损失可见、纠正可避免的新池逐币挤出，未扩张后台计算预算或声称全部观察进入研究。它是有界采样的残留覆盖限制，不能把丢帧记为失败交易或零收益，也不能删除原始snapshot。

## 保留的实际限制

免费源缺字段、原池覆盖、429及日预算不能靠本次本地修复全部消除。8批队列和既有每周期工作预算仍为有界采样；本轮只修正新池投递粒度并记录溢出，不声称全Token全路径覆盖。普通Paper仍是用户接受的市场价模型，未增加深度/冲击估算。

工程修复改变未来行为，不抹去历史亏损或污染，不证明策略正期望；没有新策略注册、资金重置、历史退款、Live启用或恢复自动复盘。ROUND3继续保持参考研究未集成状态，不将其当作本阶段已交付。
