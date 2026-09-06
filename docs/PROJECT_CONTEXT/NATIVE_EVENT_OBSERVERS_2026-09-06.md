# 原生场所、补充官方源与本阶段边界

## D18 / D19

- Four.meme仅TokenManager2创建及加池事件，真实topic/ABI严格解码；不将管理合约当池、不虚构价格或流动性。Pons仅官方V1 active/legacy factory TokenLaunched，保留dex/pool/version身份。共用现有只读RPC，无私钥、新依赖或重型订阅。
- 每30秒轮换一链；最多100块/200日志、持久化并排队8个身份、每轮总超时4秒。首次只设实时frontier，不扫历史；落后跳到最新有界窗口，显式记录skipped_blocks。3确认不称最终确定性。退出事件优先，失败退避5分钟。
- 实际公开RPC：2026-09-06 12:24Z Pons chain4663正确，后一次日志窗口55975246–55975345返回OK/0事件；这证明接口可用，不是已有自然触发。BSC chain56正确，但getLogs返回-32005 limit exceeded；12:26附近缩到单个block仍同错误。解码/接线已实现，BSC原生日志覆盖受限，既有Dex/GT多链发现仍在。没有靠增加请求绕过额度。
- Pons V2文档在当前网络跳转country=GB限制页，缓存部署地址相互冲突，不强行部署V2。后续需要可核验官方部署/ABI，不能复制不可靠地址。

## D10

- 保留OKX既有120秒频率。新增低优先级240秒轮换Kraken官方RSS与Coinbase官方状态RSS，各源实际480秒；一方来源、时间窗和官方host验证，单次4秒/512KiB有界。
- Kraken真实HTTP200、RSS含“SOFID is available for trading”等条目；无精确CA仅冻结搜索集合，等待已有市场确认。严格标题提取搜索符号只是检索键，不是官方合约身份。
- Coinbase真实HTTP200但内容是服务incident，只记观察，不伪称上市信号。故当前是2个可形成上市事件的第一方源+1个纯状态源，未达到3–5个上市源。
- Coinbase listings实际403、Binance公告页202空响应；不绕过访问限制、不用未核验私有端点。KOL/X、GMGN外部完整钱包履历仍缺对应账号/预算，不安装或购买。现有链上钱包观察不依赖它们。

## D16 / S08

新注册outcome可显式启用迁移60/120秒轨迹，锚定当时已可见的原始migration时刻，而非事后观测。普通0/15/60/240不变；旧注册定义不改，最终新资金期首次注册启用。未知仍未知，无补抓、无回填。

## 工程污染与性能修正

f932ddd在约12:12–12:20Z运行时，新S03/S05的broad-family孤立观察策略被普通Broad入口误收，四个标称5U臂产生20U BUY，S03 20U对照也走了不正确观察入口。32c08e3在12:21:14Z部署后已排除isolated入口，不再产生此类BUY。旧错误流水保留，整个这五臂的旧资金期样本不用于风险规模/策略优劣比较；按用户最新要求最终统一新账期，而非本轮追补/VOID。

新cohort单轮重复投影曾达约24秒；现在同身份单轮一次、最多8次/0.25秒Store预算并轮换尾部；sealed wallet只读不再进入数据库提交上下文，退出批次共享名单。12:23附近122不重复持仓下，held_apply_exit P95 .0536秒、held_fetch 2.178秒，cohort实际调度P95 10.12秒。整轮观察包含让路等待，不能误作纯CPU耗时；也不能把心跳正常当逐币源覆盖正常。

## 定向检查

Four真实topic/ABI4项，Pons/Four有界poller7项，Runtime事件→最多8个hydration且不交易1项，官方源5项，D16真实表时序/旧定义边界3项通过。主程序编译通过。其余基础账本、UI/ledger frontier一致性与零交易归因见最终执行表。

来源：[Four官方事件接口](https://github.com/four-meme-community/four-meme-ai/blob/main/skills/four-meme-integration/references/event-listening.md)、[Pons官方V1文档](https://docs.ponsfamily.com/)、[Kraken官方RSS](https://blog.kraken.com/feed)、[Coinbase官方状态RSS](https://status.exchange.coinbase.com/history.rss)。
