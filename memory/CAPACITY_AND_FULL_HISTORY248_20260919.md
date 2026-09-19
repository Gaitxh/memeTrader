# 248 恢复入口

用户要求完整继承 `Chat CMT_20260918-1` 并继续全链路/策略自回归工作，同时把普通 Paper 有效并发仓位 8→16、PNL 曲线改为自交易以来全历史。

已实现并部署：有效定义525/525策略cap=16（447抬升、78补齐）；单笔20U、资金期、历史、旧仓退出、Paper/Live锁不变。Web后端全区间曲线保持，浏览器不再裁成首点+最近599点，而以`full_period_sampled`全区间样本为权威。16项Python和2项Node检查通过。Paper PID9664、Web PID40368，runtime manifest 525且store hash匹配；健康/API正常。短窗0新交易，不宣称盈利。

主报告：`docs/PROJECT_CONTEXT/CAPACITY_AND_FULL_HISTORY248_20260919.md`。下一步继续按独立Token/同源对照观察16仓是否增加有效机会或只是扩大亏损，并处理其余长期停滞策略的上游原因；不重复本阶段测试、不重置、不启用Live。
