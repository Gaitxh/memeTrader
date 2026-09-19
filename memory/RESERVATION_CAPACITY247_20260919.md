# 续作247恢复入口

本轮从 246 的长期停滞证据继续。主报告：`docs/PROJECT_CONTEXT/RESERVATION_CAPACITY247_20260919.md`。

- 246 已实际注册/加载：525 条，激活 06:28:36.722785Z/快照1746620；1605 条判断、91 Token、0 准入。45→60秒只读回放仍0最终准入，未追参或复制新策略。
- 明确工程断点：`dex_regime_recovered_runner_v1` 在2981个新cohort帧全部报容量满，但真实0开放仓；8条2026-09-12无仓无终态claim永久占满8仓。
- 共享修复：只有仍在注册成交截止窗口内的无仓claim占容量；旧claim保留不改写。观察/成交均传明确as-of。
- 4项claim回归通过。opening141另4条旧测试仍断言5U/2仓等过时合同，未计通过；当前冻结合同20U/8仓。
- 已受控重载：wrapper22696/runtime38644，07:02:50.440064Z，525策略、原资金期、Paper、Live locked；三份关键源码manifest hash匹配。
- 部署后55条自然判断从`strategy_open_or_reserved_limit`恢复为`wait_passive_cohort_opportunity`，0新信号/成交/盈利。修复的是阻断，不是alpha证明。

下一步优先跟踪该臂新的自然signal→安全→下一帧BUY及净结果，并继续解释其他cohort臂为何没有上游信号；不要重做本轮claim测试、恢复旧预留、降低原池/时钟真实性或把等待信号记为盈利改善。
