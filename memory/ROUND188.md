# Round 188 记忆

- 81 地址本轮范围只有冻结总量（65 匹配）；可复算文件是 92 地址超集（76 匹配），严禁替换分母。
- 92 超集路径：52 评估未准入、4 准入未持仓、20 曾持仓。806 仓是跨臂投影，不是独立交易样本。
- 未早买需按发现、首个有效原池、窗口形成、信号、准入、安全、下一帧 fill 七个时钟定位；later ATH 不得进入任何前置判断。
- core183 快/慢两臂成熟负期望，保持暂停。trajectory144 runner 的正收益约 98% 来自单一 Solana 赢家，不能称稳定 Alpha。
- trajectory187 当前小样正收益继续观察，不新增策略。成熟门：按链与共同 source fill 配对，至少 30 个独立成熟 Token、两个日期、120 分钟共同窗口，并报告剔除最大赢家结果。
- `trajectory187_armed_runner_v1` 真实语义是成本后曾达保本才启用 15% trailing，不是入场即启用；旧合同不改写。
- held 总取数长尾尚未归因。本轮只增加 Runtime 槽等待、transport-with-client-wait、apply/exit 三段计时；不增加并发、请求或数据源。
- PID 76880 部署后的首批自然样本已初步归因：held 总取数 p95 5.86 秒，其中槽等待 1.41 秒、transport-with-client-wait 4.53 秒、apply/exit 0.10 秒。主尾在传输/客户端内部等待，本地计算不是瓶颈；短样本下不扩并发。
- 旧 `mv_flow_demand_v1` 持仓的 exact entry pool 长期陈旧；同 Token 其他池不得借用。超时/陈旧不证明全亏。
