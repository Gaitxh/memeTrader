# ERR-20260905-005：多链 Vault/Provider 瞬时错误

状态：`FIXED`

## 1. 事件

- 组件：多链数据与 v22 Vault shadow observer
- case #8：`geckoterminal:bsc` `ConnectTimeout`，发生于 `2026-09-04T19:59:08Z`；多链数据于 `2026-09-04T20:06:43Z` 恢复。
- case #9：`ReadError`，属于 v22 Vault shadow provider 瞬时错误。
- case #10：`held_account_subscription_rejected`，属于 v22 Vault shadow 订阅瞬时错误。
- 影响范围：11 个池、33 个去重订阅目标。

## 2. 恢复证据

v22 Vault shadow 的最后一份有效 frame 为 `2026-09-04T20:09:17Z`，累计记录 94 frames；相关 provider/订阅随后恢复。该 observer 仅记录池/Vault 观察结果，不产生 BUY、SELL、WRITEOFF，也没有 PNL authority。

## 3. 影响判断

当前证据支持“外部 provider/订阅瞬时故障”，不支持策略缺陷、PNL 计算错误或交易状态污染。失败期间不得把缺失 frame 当作价格、流动性或退出成交依据。

## 4. 当前处理语义

- provider 请求和订阅使用有界失败处理，下一轮重新获取。
- Vault shadow 只作为 observer 追加 frame，不改变交易、持仓或 PNL。
- 以池地址/账户身份去重订阅，33 个目标不会被重复订阅。
- 单一 provider 或订阅失败不应扩大为其他链的交易状态改变。

## 5. 复发时的快速排查

1. 查看 `source_health` 中 `geckoterminal:bsc`、多链数据和 v22 Vault shadow 的最近成功时间、错误时间及连续失败次数。
2. 区分 provider `ConnectTimeout/ReadError` 与订阅端 `subscription_rejected`，确认是否仅单池/单链受影响。
3. 核对 11 个池、33 个去重订阅目标及最后有效 frame 是否继续推进。
4. 确认失败期间没有新增交易、改变持仓、覆盖旧 frame 或参与 PNL/退出判断。
5. 只有连续失败导致 frame 长时间中断、Runtime 心跳停止，或错误进入交易/PNL 链路时，才升级为新的工程事件。

## 6. 结论

case #8、#9、#10 均属于已恢复的多链 provider/订阅瞬时故障。无需大规模重构，不应将其作为策略表现或 PNL 证据。
