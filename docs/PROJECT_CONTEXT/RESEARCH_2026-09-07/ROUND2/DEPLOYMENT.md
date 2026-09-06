# 第二轮发布与验收

当前为逐阶段实际记录，最终结果见末尾追加。不是alpha或全系统无故障声明。

## 发布记录

- `274195c`：普通主入场使用首个合格后帧、独立receipt身份、零投影终结失败、SELL毛净字段修复。2026-09-06T19:25:25.323327Z/frontier1272816生效，原资金期与旧214定义未重置。详见 EXECUTION_REPAIR.md。
- `a9940c1`：客户端缓存只使用max-age，避免错误使用共享s-maxage额外等待；4项最近缓存测试通过。保留429退避、额度和原observed，不保证免费源秒级。
- `9ab555f`：五机制10新臂，2026-09-06T19:51:52.750975Z/frontier1287042实际注册，214→224；每新账户1000U/5U/最多4仓。13项本批测试通过；此前相邻34项通过。原资金activation、127 base JSON摘要、87个已有addition policy摘要逐项不变，旧交易主键460112→460159继续增长。

五组control/candidate按注册顺序：246/247 chase；248/249 slow_grace；250/251 giveback_duration；252/253 response_exhaustion；254/255 runner_requalification。这些是数据库addition ID，不冒充Web显示编号。

## 发布核验额外发现并修正

首次注册后，chase candidate与control的behavior fingerprint相同：摘要字段白名单漏了新的entry_chase_budget_fraction。规则与账户独立，实际candidate veto已有测试，但该派生摘要会误导行为去重。已把预算加入摘要，并在读取带预算策略时重新派生当前摘要；**原注册行、policy JSON、历史交易与账户不改写**。旧214无该字段，摘要不受影响。最近单项旧摘要夹具测试通过：不可变注册保持原值，有效candidate/control摘要不同。初版测试尝试更新夹具被immutability trigger拒绝，随后改为模拟旧摘要生成器注册，而非移除数据库保护。

## 独立评审与根裁决

六项目Chat分别做R1/R2/R3，另两角色做R4定向争议核验；原文逐一归档。Web模型自述GPT-5.6 Sol，实际UI模型/推理选择无法独立核验，UNKNOWN；关键本地agents为用户授权GPT-6 Astra xhigh。没有宣称已操作到Chat GPT-6 xhigh。

- R2真实receipt身份/零投影blocker和本地DS parser NULL接线问题均修复并出现自然receipt。
- R3一些Chat声称旧profit control保留lifetime peak，实际 research_finalists.py:174–180在gap/source时重置段内peak。保留新旧对照同样的segment规则并补卡/测试；R4外部与反方明确承认误读并撤回blocker。公共trailing生命周期高水位不改。
- chase继承普通Broad的一Token/原池一次入场，非Wave Reset；R4反方撤回“误杀第二合法episode”指控。
- slow_grace保持V不低于progress anchor，不接受恢复型亏仓延期的额外机制；response增加唯一固定首段1%可辨识门，不做参数矩阵。
- 所有PASS只涉及小额Paper合同可运行，不涉及经济有效性。候选/对照共同容量受限，不能外推独立账户资本周转优势。

## 仍存在的实际限制

缺原池/缺liq、GT429及Demo本地240日预算耗尽仍有证据，见 DATA_ROUTING_INCREMENT.md；不是未知行情=0或池死亡。重查缓存不能保证上游产生新代际。普通Paper仍为已接受原池价格与4%/4%成本模拟，没有完整amount-specific impact或真实链上可卖保证。旧同帧/工程污染记录保留并按合同隔离，不作为新epoch无偏收益。无重置、回填、退款、自动Live或恢复暂停自动复盘。
