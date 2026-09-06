# R3争议裁决与实际定向验证

六个独立用户项目Chat的R1/R2/R3均实际返回，原文按role归档。用户7条链接去重后为6个不同聊天。工具未暴露可核验Chat模型/推理设置，部分回复自报GPT-5.6 Sol；不能把它写成已选择GPT-6 xhigh。关键本地只读审查子agent实际指定GPT-6 Astra xhigh，普通证据整理使用较经济配置。浏览器内核资产路径故障阻止UI模型选择，不另造或假称模型能力。

所有询问均以“继续。”开头。R3初始请求里角色名占位替换也改到了ROLE字段名；MESSAGE_ID和目标Chat正确，六回复均回传正确ROLE与RESULT，未因此丢评审。无需重做无关往返。

## 已裁决的问题

| 问题/评审 | 根代理核验与动作 | 结果 |
|---|---|---|
| R1/R2按旧名字解释migration、participation、profit-lock | 冻结当前policy/hash + 实际dispatcher +93仓回本flag核验；修订证据报告，拒绝把锁利负delta当正确实现的反证 | 旧原始账本/代码保留，新profit-budget不依赖故障布尔路径 |
| 外部论文旧版本夸大 | 原论文v3核验并写EXTERNAL_CORRECTIONS；R3六角色采用纠偏 | 不以旧毕业率/钱包倍增解释当前策略 |
| Token研究iid cohort bootstrap忽略重复Token | 移除脚本/报告/离线产物全部iid CI，保留描述性中位差与分层方向 | 未重新查询生产DB；不宣称显著性 |
| 5臂pair旧代码只能恰好2臂 | 新字段paired_entry_size=5；旧默认2不变；同锁内全组slot/cash控制 | 三链4机会×5仓，超4仓全组拒绝 |
| EVM校验和大小写导致新exit身份不匹配 | 仅新EXIT_KINDS adapter canonical化position pair | 混合大小写BSC真实Store退出通过 |
| NULL中间帧跨越累计恶化 | 必需字段缺失清accepted/streak，次个有效帧重新基线 | 专门反例通过 |
| R3 Strategy：未知provider仍推进exit | 空provider WAIT并断证据 | 专门反例通过 |
| R3 Risk：跨provider沿用利润峰 | gap/source重置profit基线及clock/streak | 旧源6U峰不用于新源5.4U回吐判断 |
| R3 Data/Risk：paired现金拒绝静默 | 在既有entry_evaluations.feature_json写逐臂paired_rejections；无新表/请求 | cash blocked五个原因；slot/eligibility有分组拒绝+outcomes |
| 后续接收旧观察可被称后帧 | 新8臂require_post_decision_observation=True，entry/exit两路径都检查observation>decision | 触发后收到但之前观测的报价不能成交；旧臂不改 |
| 各Chat要求实际接线而不只pure PASS | 新3 entry实际Store入场；四exit实际Store pending→next observed SELL并保留baseline | 19项新测试通过 |
| 旧cycle测试仍100美元/旧reason | 按当前已生效1000美元/configured floor更新四个陈旧断言 | 四项重跑通过；没有降低实际门槛 |

## 已运行验证（不是自然收益）

- `tests/test_research_finalists.py`：最终19项通过。因果/未来/重复/稠密采样、缺字段/原池/来源、3阶段正反例、账户独立、5U按4%买成本、4仓限额、注册幂等/旧定义保留、五臂资金拒绝、三链entry、四exit与后观察成交、baseline不被candidate退出影响。
- 相邻 `tests/test_l0_store.py` 已通过；既有cycle/volatility数值测试通过。首次相邻测试出现4个陈旧100美元断言失败，原因和改动如表，四个对应断言重跑通过，没有隐藏失败。
- 本地1000次synthetic bundle微基准（3个entry+4个exit，含测试侧构建策略开销）：P50=1.05465ms、P95=1.1643ms、max=2.0072ms；无API、SQL。它不是实际后台端到端延迟，也不证明实盘速度。
- 部署前17:38:21Z后台仍运行：主循环间隔P95=1.23385s，持仓fetch P95=3.30726s、apply/exit P95=.08543s，pattern间隔P95=15.14616s。持仓任务设置1s，实际间隔P95=4.53703s，不能把配置频率写成真实频率。
- 当时RH原池覆盖缺口82/90、数据年龄P95约1552.79s；SOL数据失败54/136。这些既存免费源/覆盖缺口没有因新增纯函数消失。新实验遇缺完整原池资料WAIT，不能报告“后台所有币完全实时”。

部署与自然观察另记实际时间/frontier/计数，不提前声明完成。既有L0 profit-lock接线缺口本轮记为当前未修旧臂问题，不把它纳入已工作的最终代表，不偷偷改变旧策略。
