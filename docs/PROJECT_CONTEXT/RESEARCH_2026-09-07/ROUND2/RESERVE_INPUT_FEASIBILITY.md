# R2轴9/11：报告两侧数量与可见多池输入可行性

日期：2026-09-07。范围：只读追踪collector→observer→`token_snapshots.raw_json`，一次最多30条PK尾部抽样，并查官方文档。没有新采API行情、调用链RPC、扫描大表、修改应用/策略/数据库/Runtime或安装依赖。Windows项目操作技能约束了本次`mode=ro`、2秒中止和显式E盘路径。

## 结论

**轴9可做“供应商报告两侧数量同步扩张”的有界Paper假设，但不能直接称为链上reserve已验证、真实LP净存入或有效可执行深度。轴11在collector确有输入，但当前pattern observer的持久化链路并未保留可见多池集合，尚不能直接用旧observer历史运行该机制。**

本次30条快照中，12条有两侧正数数量，其中8条的DEX标识为PumpSwap；2条明确CLMM仍有两侧数量，是“字段存在≠CPMM”的实际反例。剩余2条为Orca `wp`和FluxBeam，不能因未写CLMM就放行。样本全为Solana，不能外推BSC/RH覆盖或策略触发频率。

应区分两个证据级别：

- **供应商标记级**：`dexId=pumpswap`或明确版本标签，仅支持“报告为某池型”的proxy实验。未知/冲突池型排除，不声称程序owner已核验。
- **链上身份级**：已有、当时可得的原池program-owner/布局/两mint或V2 factory证明，才能称池型被链上核验。本次抽样的指定raw字段不含这些证明；已有PumpSwap原生surface代码具备这种核验能力，但没有为本任务额外查它的DB覆盖或启动采集。

若根代理要求轴9一定使用第二级，而已有原生身份事实无法在当前路径零新增请求取得，则应WAIT/条件储备。若接受第一级独立Paper，名称与介绍须明确“reported quantities / provider-classified PumpSwap”，不是“LP注资确认”。

## 1. 当前代码真实保留了什么

行号为本次读取时版本；根代理并行修改可能使之后行号移动。

|链路|事实与定位|对提案的影响|
|Dex单pair转快照|`DexScreenerClient._snapshot`在[collectors.py](/E:/memeTrader/src/memetrader/collectors.py:1978)只把USD liq提升为标准字段，但`raw={"pair": pair}`保留完整pair对象。|`liquidity.base/quote`若上游有，就仍在raw；TokenSnapshot没有专门两侧reserve列。|
|Dex批量token报价|[batch_quote](/E:/memeTrader/src/memetrader/collectors.py:2024)收集`pools_by_token`，选liq最大的主pair；[2071行](/E:/memeTrader/src/memetrader/collectors.py:2071)将该token响应中的pair列表写入`snapshot.raw["pairs"]`。|批量collector确实曾拿到同token的可见多池，不需为此另请求行情。不是全链完整池集合。|
|Dex search / 单token quote|[search](/E:/memeTrader/src/memetrader/collectors.py:1992)和[quote](/E:/memeTrader/src/memetrader/collectors.py:2003)仅返回所选快照，不像batch显式追加`raw.pairs`。|不能假定所有provider路径都带集合；缺失不等于只有一个池。|
|Gecko补源标准化|[market_api.py](/E:/memeTrader/src/memetrader/market_api.py:154)读取`reserve_in_usd`；[178行](/E:/memeTrader/src/memetrader/market_api.py:178)构造`liquidity={"usd": reserve}`，保留源pool于内层raw。|标准pair没有两侧数量；也没有在这里推导/伪造数量。本任务未证明内层源pool另有可用两侧reserve，因此Gecko不能无缝接替轴9。|
|内存pattern watch|[_remember_pattern_quotes](/E:/memeTrader/src/memetrader/runtime.py:6984)保留传入snapshot引用、更新watch，未主动做额外I/O。|在被裁剪之前，可复用已有响应。|
|pattern observer第一处丢集合|[runtime.py](/E:/memeTrader/src/memetrader/runtime.py:7184)从`raw.pairs`寻找原池，随后[7188行](/E:/memeTrader/src/memetrader/runtime.py:7188)调用`_snapshot(exact)`重建单pair快照。|原池整个pair仍保留，但外层`pairs`已不在observation中。|
|observer第二处丢集合|[Store.observe_chain_meme_pattern](/E:/memeTrader/src/memetrader/store.py:26642)检查身份和时间；[26665行](/E:/memeTrader/src/memetrader/store.py:26665)重建isolated raw，仅保留`pair/upstream_provider/cohort_observer`。|只改Store并不能追回Runtime已丢的集合；只改Runtime也会在Store再丢。|
|实际入库|[Store.add_snapshot](/E:/memeTrader/src/memetrader/store.py:12035)将`snap.raw`整体JSON存储；[schema](/E:/memeTrader/src/memetrader/store.py:1044)已有`raw_json`。|不是DB列能力缺失；若未来新增有界投影，可继续用既有raw字段，无需新表/大扫描。|
|已有持仓多池用途|[runtime.py](/E:/memeTrader/src/memetrader/runtime.py:6813)针对expected原池遍历`raw_pairs`，只认相同token与原池。|证明已有响应确有多池消费点，但不证明新pattern机制已接通；不应改成兄弟池代成交。|

`_held_pool_quote`还允许从同一池的quote侧给持仓定价，并把原始pair和`target_pricing.side=quote`保留：[runtime.py](/E:/memeTrader/src/memetrader/runtime.py:2259)。因此新reserve代码必须绑定**原始base/quote mint方向**；不能因为当前持仓token是quote，就把原始`liquidity.base`解释成持仓token数量。当前pattern入口要求token与pair.baseToken相同，但共享持仓路径不能假定同样方向。

## 2. 一次PK尾部抽样结果

数据库路径只从ignored配置的`database`字段解析：`E:\memeTrader\data\memetrader_forward_20260830_r6.sqlite3`。连接使用SQLite URI `mode=ro`，`PRAGMA query_only=ON`，连接等待0.2秒，progress handler每1000 VM步检查2秒deadline。查询以主键倒序`ORDER BY id DESC LIMIT 30`，没有provider过滤后向前遍历、没有COUNT全表、没有JSON扫描全表、没有构造Store。

只提取必要的pair身份/liq/labels/type/program/factory和外层pairs字段；未输出全raw。全部读取与聚合总计0.0208秒，连接已关闭。没有为了补齐BSC/PumpSwap样本再读取第二批。

- PK范围：`1262366–1262395`，30条、30个不同token/原池。
- `observed_at`范围：`2026-09-06T19:08:15.624858Z–19:08:18.420459Z`；本地为09-07凌晨。不是长期覆盖样本。
- provider：30/30为`strategy-observer:dexscreener`；chain：30/30 Solana。
- 两侧字段均为正数：12/30；其中这12条都同时有`usd/base/quote`键；其余18条的所提取liquidity键集合为空。
- `raw.pairs`非空：0/30；多池：0/30。这里只能判定“样本未保留集合”，不能判定现实里没有第二池。
- `pair.poolType / pair.type / pair.programId / pair.factory`：每项均0/30非空。`labels`非空3/30；不能用这4个缺失字段宣称已经核验链上owner。

|样本dexId / labels|行数|两侧正数量|最小处理|
|---|---:|---:|---|
|pumpswap / 无labels|8|8|可标记provider-reported PumpSwap；未由本次raw证实program owner|
|raydium / `["CLMM"]`|2|2|明确排除CPMM reserve机制|
|orca / `["wp"]`|1|1|不在CPMM正面清单，排除；无需靠猜测wp扩写后再放行|
|fluxbeam / 无labels|1|1|未知类型，排除|
|pumpfun / 无labels|16|0|bonding-curve场所不等于PumpSwap，且本样本缺数量|
|meteoradbc / 无labels|1|0|不在正面清单，且缺数量|
|bags / 无labels|1|0|不在正面清单，且缺数量|

最小可复查锚点，不披露全raw：

|PK|身份/事实|
|---|---|
|1262395|Raydium `["CLMM"]`，原池`Hsy19ovmJXN13yBzcUct7RFkY7iqkAdWf2QkRwXe5vYU`；有base/quote数量。直接反驳“有两侧数就可按CPMM理解”。|
|1262379|`pumpswap`，原池`HfqZoKVnpZng7jB7f9AY67SnS3HB8hZAzSwumu2bECBj`；有两侧数量，外层pairs未保留。|
|1262394|`meteoradbc`，原池`D62DBcusH45rTcnDw3qcmjVsptdRrRem9h593mHtfaWU`；本次选取的liquidity字段缺失。|

这次抽样只证明**字段/标识存在率**；没有比较同池前后数量、检测双边增长、验证数值单位稳定或计算潜在交易数。

## 3. 官方资料允许怎样解释这些数

### DexScreener：schema有字段，没有链上reserve审计承诺

[官方API reference](https://docs.dexscreener.com/api/reference)展示pair的`dexId`、可空`labels`、两mint、`liquidity.usd/base/quote`以及token多池响应；`labels`为自由字符串数组，不是有固定枚举保证的链上池型字段。本文采用“供应商报告的两侧数量”称谓。其schema没有在这些字段上给出区块/slot、同步vault证明、手续费/PnL扣除、raw/effective reserve选择或CLMM active-liquidity承诺。官方文档本次搜索索引可返回完整schema，直接页面抓取曾失败；未调用行情endpoint补证。

因此，观察数量的同源相对变化是可提出的代理假设；不能据此计算真实LP净流入、把数量再任意按decimals缩放，或从两数精确重建成交价格/冲击。未知单位/来源变更应中断序列，而不是自动换算。

### PumpSwap：有两侧vault，但有效报价reserve有额外字段

[Pump官方公开文档](https://github.com/pump-fun/pump-public-docs/blob/main/docs/PUMP_SWAP_README.md)明确PumpSwap是constant-product AMM，program为`pAMMBay6oceH9fJKBRHGP5D4bD4sWpmSwMn52FMfXEA`，pool指定base/quote mint和两个token account。现行文档要求报价用`effective_quote_reserves = quote_vault.amount + virtual_quote_reserves`，并称文档当时该附加量为0。不能把这句“当时为0”当所有未来快照的永恒事实，也不能推定DEXScreener字段是否已经包括它。

已有[pool_surface._pool](/E:/memeTrader/src/memetrader/pool_surface.py:40)验证program owner、mint、pool PDA与LP mint PDA；[classify_pumpswap_pool_surface](/E:/memeTrader/src/memetrader/pool_surface.py:71)另核同一bundle的vault和mint，并输出`base_vault_raw/quote_vault_raw/decimals`。这是更强但不同的现成原生证据；不等同provider raw.quantity，不能无版本/单位说明混成连续序列。本任务没有调查该native路径当前覆盖率。

### Raydium：dexId是场所，不是池型

[官方介绍](https://docs.raydium.io/introduction/what-is-raydium)及[CPMM math](https://docs.raydium.io/products/cpmm/math)、[CLMM overview](https://docs.raydium.io/products/clmm/overview)区分constant-product与按tick/range工作的集中流动性。官方[program addresses](https://docs.raydium.io/reference/program-addresses)提供不同program身份。`dexId=raydium`本身不能判CPMM；必须有明确正向池型/已得program事实，遇CLMM或未知一律不使用轴9的CPMM解释。

AMM v4与CPMM也不应无说明混同。对于已有v4池，供应商两侧量可作其报告库存变化，但不能假定供应商是否已处理旧式池的vault、订单簿余额和费用口径。轴9最小范围可先不含AMM v4，省去其特殊核验；这是范围选择，不表示v4不交易。

### Pancake：V2、V3、Infinity必须分开

[Pancake官方V2 factory说明](https://developer.pancakeswap.finance/contracts/v2/factory-v2)基于Uniswap V2，factory可确定实际pair；[官方V2地址](https://developer.pancakeswap.finance/contracts/v2/addresses)给出各链factory，例如BSC `0xcA143Ce32Fe78f1f7019d7d551a6402fC5350c73`。不能只认名称包含“pancake”。

[官方V3 FAQ](https://developer.pancakeswap.finance/contracts/v3/faq)描述tick/集中流动性，并明确pool总余额/TVL可能包括未领取费用，可能高于实际active liquidity。因此V3/Infinity集中池、bin/liquidity-book、StableSwap、未知版本不能套同一双reserve恒定乘积解释。本次未抽到BSC/RH样本，不声称其`labels=v2`覆盖充足或factory已验证。

## 4. 最小严格分类/时序合同建议

这些是提案，不是已改代码。

1. **先正面分类，再计算**：不得用“不是CLMM”作为CPMM充分条件。按`chain + provider + dexId + 明确版本/池型证据`正面清单；若有原生已核验证据，则必须绑定同原池和两mint。未识别类型、互相冲突标签、新DEX/新版本一律WAIT。
2. **硬排除已知非目标**：`CLMM`、V3、DLMM/bin、Infinity、whirlpool类、StableSwap以及未毕业bonding curve不进入轴9。正面清单优先于标签字符串猜测；`pumpfun`不等于`pumpswap`，`raydium`不等于CPMM，`pancakeswap`不等于V2。
3. **字段必须真的存在**：两侧为有限正数，base/quote地址非空且不同；原池、原始base/quote方向、provider和解释版本连续。缺数量不补0；不得用`liquidity.usd / priceUsd / 2`制造base/quote——那会把新机制退化成原有价格与USD流动性的代数重写。
4. **只做相对报告数量**：同一单位下比较两側变化，不直接以数量乘价格估真实深度，不把`x*y`增长命名真实LP流入。单侧价格计价可以导致USD liq变化；两侧数提供额外维度，但仍可能受交易费、捐赠、重基、供应商修订影响。
5. **时间遵守原有因果合同**：引用同一真实收到的pair观察；`observed_at ≤ ingested_at ≤ decision_at`，新独立帧才推进状态。Provider没有slot，不能声称双侧是同链上slot。换源/方向/池型证据变化/缺字段断开序列，不跨两个池拼增长。

**确定性反例：两侧一起增，不必发生LP deposit。** 一个示意constant-product池初始`x=y=1000`，示例交易费1%（不是当前任何协议费率声明）。先输入100单位quote，池变成`x≈909.918107、y=1100`；再做反向swap输入`90.581893`单位base，池变成`x=1000.5、y≈1001.316271`。两侧均比最初多，价格仅约变0.0816%，全过程没有LP存款，来自两次swap及留在池内的费用。此反例按公式当场代数计算，没有链行情输入。故“两侧扩张且价格平稳”最多是库存支持代理，不是LP事件检测器。

## 5. 轴11最低接线条件与不可声称的结论

**已有payload可复用，但需要同时穿过两处裁剪。** 若根代理决定实施，最小位置是Runtime构造原池observation时附加一个有界、明确标为同响应可见集合的投影，并让Store isolated raw保留该投影。只保留计算需要的`chain/pair/mints/dex/labels/price/liquidity/volume/source/received`，不复制不需要的宣传/图片/社交字段。现有`raw_json`足以存储，不需要新表、全链扫描或额外API行情请求。

但在未实际实施前，不能给轴11写“raw.pairs已在observer历史中可用”。本次没有修改这两处。普通token_snapshots可能在其他路径保存完整raw，但本次30条全为observer，没有证据宣布其他路径全有或全无。

最少还需满足：

- 同一响应的**可见集合**不是全链所有池；collector会按目标base token过滤，搜索/单quote/补源各自能力不同。把“API这次没返回某池”解释为0 liq/0 volume会制造假迁移。
- 先冻结原池和固定比较集合S；每个新观察中S的所有成员都仍明确出现、身份一致，才能比较S内份额。增减成员单独记录；不要把分母改变当资金迁移。
- 基于USD volume/liq只能称报告份额；不同quote资产下的token quantity不能直接相加。跨池价格必须统一目标token方向，原池不在集合时WAIT，不借兄弟池成交。
- 同响应也不等于同链上时点；DEXScreener pair不带可验证slot。可以做供应商同步返回级别的价差代理，不可称无风险套利/真实可执行价差。
- 只有1个可见池、集合字段缺失、提供者换路、成员不稳定时不计算迁移。不得向后补采旧快照替代部署后新观察。

## 裁决摘要

- **可以支持的最小轴9**：从已有Dex raw.pair读取报告base/quote相对变化；先限明示的provider-classified PumpSwap或已核验原生CPMM身份，CLMM/未知排除，命名为报告库存proxy。已有字段不等于行为已经接通，也不是盈利证据。
- **还缺的轴11**：Runtime和Store双处保留有界同响应可见池投影；当前observer样本没有它。免费接口多池列表本来已有，不应新增行情请求来补这一工程缺口。
- **不能升级的解释**：真实LP净存入、全链份额、精确可执行深度、同slot同步reserve、CLMM active liquidity、可卖保证。更强解释需要已有原生证据真实接通；本次没有为它扩大采集或扫描范围。
