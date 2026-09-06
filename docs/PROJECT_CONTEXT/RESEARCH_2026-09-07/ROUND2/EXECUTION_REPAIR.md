# 第二轮：实际后帧入场与成交字段修正

状态：代码完成、定向测试通过；本文件初稿时尚未部署。部署事实随后单独追加。

## 已确认的问题与改变

1. 旧普通主入口把信号帧直接用于 Paper BUY；孤立 pattern 的后观察合同不同。新增独立 `market-entry-post-observation/v1` 执行 epoch：冻结真实信号及参与账户，既有 pending 原池采集收到首个合格后帧才成交。必须 decision < observed <= ingested <= received，报价年龄 <=15秒、链/Token/原池一致、有效价格与当前池阈值；90秒未确认终结失败。没有新 API/RPC 任务；复用最多8个 pending 目标及旧现金预留。
2. 首次实现中 receipt 价格与 entry_snapshot_id 不一致，独立 Chat 评审准确指出。现同事务追加真实 receipt 快照并写不可覆盖的 cohort receipt 引用；信号ID独立保留，仓位/entry fill指向实际成交快照。receipt provider命名空间不进入主入场扫描，避免额外机会。
3. 0个可投影账户不能标全体成交：intent终结 failed，不晚等更好价格；已有 participant outcomes逐账户记录现金不足和成功投影。cohort filled仅代表至少一个账户成功，不代表全部账户。
4. 实际DS parser不设置ingested_at。独立本地评审发现最初判空会导致永远不买；现于实际接收边界补本地received时间，不刷新observed时间。真实parser形状已加入三链生命周期测试。
5. 非零额外手续费时 SELL gross 曾写成net。现gross/output raw记录毛回款，现金/累计回款/PNL记录net；amount-specific路径不重复扣费。当前fee=0数值不变，历史不回写。

## 保护与诚实边界

- 旧214（包含上轮8）策略规则、hash、资金期、历史和开放仓保留。**未来普通主入口执行行为改变**，不能声称所有旧行为完全不变；比较必须按执行epoch分层。
- 不升级为真实链上成交证明，不引入price-impact估计；维持现行原池价格模拟+4%/4%成本、额外0U和1000USD池门。provider本地观察时间也不等于链上最后一笔成交时间。
- 旧同帧记录保留并标执行合同边界，不作为新后帧实验的无偏对照。
- 没有重启全实验、初始化账户、回填、退款、自动Live、恢复周期复盘。

## 已实际验证

- `tests/test_paper_execution.py`：6通过，涵盖三链真实DS parser/首次原池后帧、信号与receipt身份、重复/陈旧/NULL/错池拒绝、过期、资金在等待期间耗尽而0投影、不得稍后重放、非零手续费毛净字段。
- 较早相邻验证：paper_execution + research_finalists + chain_meme_pool_identity 共30通过；之后receipt修订重跑最邻近6项通过，不夸称整个系统无缺陷。
- 六独立Chat R2都指出receipt身份/零投影问题；本地独立工程agent追加parser实接线核验。模型与证据限制详见本轮各角色原文。
