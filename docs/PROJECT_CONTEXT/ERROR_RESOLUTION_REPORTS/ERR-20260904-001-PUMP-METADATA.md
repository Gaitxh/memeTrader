# ERR-20260904-001：Pump Token 元数据请求失败

## 1. 错误指纹与时间

- 07 错误编号：`1`、`2`
- 组件：`pumpportal:metadata`
- 错误：`HTTPStatusError`、`ReadTimeout`
- 编号 1：2026-09-04 19:50:58 至 20:23:10（Asia/Shanghai），07 聚合 14 次。
- 编号 2：2026-09-04 19:53:31（Asia/Shanghai），1 次。

## 2. 用户影响

失败只影响个别新 Token 的首发描述、网站及社交链接补全。PumpPortal 新币发现、DexScreener 行情、策略买卖、仓位 PNL 和退出判断继续运行。失败 Token 后续仍可由 DexScreener 补充市场数据。

## 3. 根因

Pump Token 的元数据主要位于公开 IPFS 网关。公开网关是 best-effort 服务，可能限流或短时超时；IPFS 官方也明确说明公共网关没有 SLA，且共享限流。参考：[IPFS 公共服务说明](https://docs.ipfs.tech/concepts/public-utilities/) 和 [替换公共网关指南](https://docs.ipfs.tech/how-to/replace-public-gateways-with-self-hosted-ipfs/)。

旧实现还有三个放大问题：

1. 每个 URI 只请求一次，429、5xx 或网络超时不会重试；
2. HTTP 状态码、请求网关和尝试次数没有保存；
3. 单个 Token 的无效或暂时不可用文档被提升为整个系统的07错误。

历史记录只保存了异常类型，因此不能事后准确恢复每一次 HTTP 状态。代表性失败 URI 曾复现公开网关限流，稍后再次请求恢复成功。

## 4. 证据

- 错误前后 Pump 元数据均持续成功，不是 PumpPortal 流或 worker 停止。
- 失败 Token 后续仍获得 DexScreener 快照和来源链接，部分继续进入策略仓位。
- 2026-09-04 20:28:31 部署修复后，截至 20:29:35 已自然完成 17 次元数据补全，07 原错误计数未增加。

## 5. 代码修复

- 对 HTTP 408、425、429、5xx 和传输超时最多重试一次。
- 对 IPFS CID 在 `ipfs.io` 与 `gateway.pinata.cloud` 两个独立后端间进行一次有界切换。
- 尊重 `Retry-After`，等待最多 5 秒，避免无限重试和请求放大。
- 400、401、404、410、422 等单文档永久失败只写入该 Token 的证据账本，不再冒充系统故障。
- 在逐 Token 结果中保存安全的 `document_host`、`retrieval_host`、`http_status` 和 `attempt_count`。
- 只有重试耗尽的暂时性上游故障或未知程序错误才进入07。

## 6. 验证

- 定向测试覆盖：503 后备用网关成功、404 单 Token 不可用但不产生系统错误、原有成功补全流程。
- 全量 Python 测试通过。
- Python 编译检查和前端 JavaScript 语法检查通过。
- 运行态版本保持 `chain-meme-trader/v20-market-only-accounting-corrected-clean-forward`，124 个策略继续运行，账户和仓位未重置。

## 7. 回退方法

如修复本身导致元数据 worker 异常，只需回退 `Runtime._hydrate_pump_metadata` 的有界重试与分类代码；数据库结构、策略账户、交易和历史记录均未改变。

## 8. 再次发生时的快速处理

1. 在07详情查看新的错误类型、网关、HTTP 状态和尝试次数。
2. `404/410` 且只影响单个 Token：属于内容不存在，无需停止系统。
3. `429/5xx/ReadTimeout` 且已尝试两个网关：检查最近是否仍有成功的 `metadata_hydration_result`。
4. 仍有连续成功：记录覆盖缺口，继续运行。
5. 两个网关持续失败且长时间没有任何成功：切换到专用或本机 IPFS gateway，再进行一次受控重启。
6. 不得因为元数据失败重置策略账户，也不得把旧描述回填到更早决策。

## 9. 遗留风险

两个公共网关都可能同时限流，无法提供生产 SLA。如果元数据覆盖成为交易核心依赖，应部署专用或本机 IPFS gateway；当前它仍是附加身份/介绍信息，不影响行情和卖出计算。
