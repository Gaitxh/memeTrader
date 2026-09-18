# 续作238恢复记录

用户要求尽可能推进旧策略研究、修订落地和系统性能。项目仍为D:/OpenTrader/memeTrader_2；Paper-only，无重置/Live/收费/定时改策略。

主报告docs/PROJECT_CONTEXT/CONTINUATION238_20260919.md；证据data/research/continuation238_20260919/。
最后成功读取的清单：2026-09-18T18:00:23.793868Z，PID21488、520加载策略、旧基础/追加/控制保持；runtime/store/existing_revision235字节保持。运行时不重载；唯一已登记源码差异是有意修改的runtime_timing.py。237不在生产包且未注册。

## 实际完成
- 新source_pair_coverage已经接入scripts/paired_arm_ab.py的source_buy JSON/终端输出。只处理已有结果，不加SQL、请求或交易门。比较35项测试通过；6组实际冻结结果中common_terminal与原paired输出逐组一致。
- runtime_timing.py四分位数共用一次排序，逐值等价；计时17项测试通过。32组件/120样本×每版300次CPU对照，中位1.100300ms→0.453685ms。源码已正常写入，hash162b1d20f5369fb07fd6ef774973bc18b6bf70d59f1f4b6a8234646ff6d99332。未为单次不足1ms节省重启，不记为线上加速。
- 冻结17:47:06.354971Z的41784账户仓位/2053Token。235锚点18同源币-64.816870U，对照-78.163390U；差+13.346520U但15平手，去掉最大受益Token反号。支持止损18币全平手；成熟兑现1币平手；234分批2币平手。
- 非BSC买压1个共同Token+3.434554U；原版同窗口额外2个BSC分别-20和+1.021452U。新版排除了亏损也排除了盈利，不把未参与金额记作收益。
- 入场UTC日分组：187 Solana原runner9/16 +237.343510U、9/17 -122.580866U、9/18 -45.064611U；描述性，不证明星期规律或都是市场变化。

## 受限和未完成
237完整账户测试追加、17新样本本地身份读取、最后CLI输出组合读回被工具层拦截，没有重试/替换通道。已写测试准备段移为test_reawakening237_store.INCOMPLETE.txt，不能收集为通过的测试。237仍只有前轮单元测试、未交易集成/未部署/无自然结果。补充样本沿用前轮索引，不宣布新无匹配。

局部统计发布耗时不是行情延迟；基线held transport/client wait p95约1.94秒、apply/exit约0.064秒。组件LRU sample_count不是进程累计，累计activity显示pattern observer706次、token_compute11438次。没有因统计误读增加采集器或调度负担。

本轮比较工具可以直接使用。计时模块需在下一次合适的正常发布时核验加载，不为它单独重启。新旧策略合同不变，不追着这几个币再拟合参数。此前历史catalog不等于全部机制已验证，长期盈利和237集成仍未闭合。

更新历史是否成功以history_receipt238.json及API回执为准；没有成功回执不声称发布。Git提交/推送不在本记录中冒称完成。
