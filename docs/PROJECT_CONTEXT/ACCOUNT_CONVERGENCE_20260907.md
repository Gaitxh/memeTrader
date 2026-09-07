# 策略账户收敛：仅执行第一项

生效时间：2026-09-07T15:24:42.781106Z。用户明确授权第一项与移除重复账户。

59个重复账户退役并从策略页/概览默认列表隐藏；6个账户暂停新入场。默认显示171账户，其中165保留新入场资格、6个暂停。勾选“查看退役账户”可访问59个账户的历史。

不删除数据库账户或交易，不归并资金，不重置1000U，不新增策略。已有仓位仍沿原退出规则处理；激活时这些账户共有 42 个开放仓位。没有执行建议第二至第四项，没有新增采集、模型或后台研究。

实现使用一次性、按资金期隔离的kv操作状态；原策略定义与注册保持原文。主入口/独立observer停止新入场，排队已admitted的市场投影也禁止向这些账户生成BUY。退出路径保留全部策略定义。Web保留全部账户和持仓API，正常列表隐藏重复账户，暂停不冒充缺少行情。

验证：8个resource-bound Store定向用例、1个Web缓存/账户保留用例通过；JS生命周期测试及语法检查通过。Web原测试包含旧默认资金期和零交易回报空值预期，本轮按其明确V22测试期与当前资金合同纠正。已有持仓退役后仍严格后帧卖出的Solana/BSC用例通过。

部署验收：health running；原资金期、注册/103追加合同/v6 activation摘要相同；Live仍锁定。检查时新增交易11条，正常BUY 2，目标65账户新增BUY 0。该短窗没有目标账户自然SELL，不以测试冒充自然退出；已有持仓继续受原退出逻辑管理。

Paper与8790 Web按原脚本进行一次局部重启。/health、/api/live、/api/performance、/api/strategy-universe均实际返回。没有声称速度提升或盈利改进；重启前后短窗负载不同，不作同条件速度对比。浏览器交互未另行验收，实际服务返回的账户状态和静态前端代码已核验。

原始激活前沿与65账户名单：data/research/account_convergence_20260907/activation.json；原文摘要、API与验收：before.json、after_apis.json、acceptance.json。

| 账户 | 操作 | 重复代表/对照 |
|---|---|---|
| canonical-0356dc612c90a689 | RETIRED_DUPLICATE | canonical-0006b989b189e0ac |
| canonical-058b868fbd1d8065 | RETIRED_DUPLICATE | canonical-0186f1e75b238e63 |
| canonical-19b9d4d442fde1ab | RETIRED_DUPLICATE | canonical-0006b989b189e0ac |
| canonical-1c2ac45bb5154011 | RETIRED_DUPLICATE | canonical-0006b989b189e0ac |
| canonical-1ef2715c090f60fb | RETIRED_DUPLICATE | canonical-035ad2cf0cb0f6a5 |
| canonical-24ac3d4a360ab98c | RETIRED_DUPLICATE | canonical-1d9647200c714796 |
| canonical-25cfdc3e9adf23df | RETIRED_DUPLICATE | canonical-18d8ce34c0112abb |
| canonical-2d3874b5b4dfe162 | RETIRED_DUPLICATE | canonical-0df3639e1824ad0f |
| canonical-3093112db36e72a6 | RETIRED_DUPLICATE | canonical-18d8ce34c0112abb |
| canonical-3c89090af7e8cd6b | RETIRED_DUPLICATE | canonical-2634d7c52e35b317 |
| canonical-427d6a31e0a2e604 | RETIRED_DUPLICATE | canonical-0186f1e75b238e63 |
| canonical-504d9582ca75a709 | RETIRED_DUPLICATE | canonical-2634d7c52e35b317 |
| canonical-53316326d5f1f7d5 | RETIRED_DUPLICATE | canonical-035ad2cf0cb0f6a5 |
| canonical-57d44c510448173c | RETIRED_DUPLICATE | canonical-035ad2cf0cb0f6a5 |
| canonical-5a16583de92bac39 | RETIRED_DUPLICATE | canonical-2634d7c52e35b317 |
| canonical-6c728fb1b79d226a | RETIRED_DUPLICATE | canonical-0006b989b189e0ac |
| canonical-707c4491ca3caf89 | RETIRED_DUPLICATE | canonical-18d8ce34c0112abb |
| canonical-744153cee3d16c08 | RETIRED_DUPLICATE | canonical-0df3639e1824ad0f |
| canonical-83fdc6be4ed5e6bf | RETIRED_DUPLICATE | canonical-0df3639e1824ad0f |
| canonical-8e0e2a5367a26beb | RETIRED_DUPLICATE | canonical-035ad2cf0cb0f6a5 |
| canonical-9e8b8ab496229059 | RETIRED_DUPLICATE | canonical-619d142075228d0e |
| canonical-9fdcf1c1c121b928 | RETIRED_DUPLICATE | canonical-18d8ce34c0112abb |
| canonical-a6741f19300d52f1 | RETIRED_DUPLICATE | canonical-4b290f4f2bba4fb4 |
| canonical-ac6059d9867697cd | RETIRED_DUPLICATE | canonical-0186f1e75b238e63 |
| canonical-addb9efa1916afbf | RETIRED_DUPLICATE | canonical-2634d7c52e35b317 |
| canonical-bcf4041ab4578717 | RETIRED_DUPLICATE | canonical-3028ef000f6df93d |
| canonical-c9204a1e7a1c45f3 | RETIRED_DUPLICATE | canonical-035ad2cf0cb0f6a5 |
| canonical-cae3a114676b9324 | RETIRED_DUPLICATE | canonical-0006b989b189e0ac |
| canonical-cca8c50b00503869 | RETIRED_DUPLICATE | canonical-0186f1e75b238e63 |
| canonical-d276043eb5aa27c2 | RETIRED_DUPLICATE | canonical-0df3639e1824ad0f |
| canonical-d785aa5181f97422 | RETIRED_DUPLICATE | canonical-22dbe223b3814f7f |
| canonical-e7b74ce032fcc5d3 | RETIRED_DUPLICATE | canonical-b1c6865d30e91ddd |
| canonical-eaaf188e7835376f | RETIRED_DUPLICATE | canonical-0df3639e1824ad0f |
| canonical-ef7bf4f71eeacb75 | RETIRED_DUPLICATE | canonical-2634d7c52e35b317 |
| canonical-efdc816cff3321dd | RETIRED_DUPLICATE | canonical-0186f1e75b238e63 |
| canonical-fddc0b4e14f1836f | RETIRED_DUPLICATE | canonical-18d8ce34c0112abb |
| dex-successor-035-3be68fb41c7f0536 | RETIRED_DUPLICATE | dex-successor-025-2509c2f13f40a238 |
| dex-successor-038-45d45a6774225417 | RETIRED_DUPLICATE | dex-successor-014-1375c87c13cb1de1 |
| dex-successor-052-62d73d37cb094974 | RETIRED_DUPLICATE | dex-successor-012-0eea3c62cb7bacc4 |
| dex-successor-058-6e2af57081e33ce0 | RETIRED_DUPLICATE | dex-successor-025-2509c2f13f40a238 |
| dex-successor-062-7726580fd0f701f1 | RETIRED_DUPLICATE | dex-successor-025-2509c2f13f40a238 |
| dex-successor-070-8a6c18233b0c33fd | RETIRED_DUPLICATE | dex-successor-019-1d5937dec4e156d4 |
| dex-successor-074-94e2a27a7c53d44c | RETIRED_DUPLICATE | dex-successor-019-1d5937dec4e156d4 |
| dex-successor-075-977f322fba28b9bc | RETIRED_DUPLICATE | dex-successor-067-842383c9376853b7 |
| dex-successor-078-9eab102528bb48c4 | RETIRED_DUPLICATE | dex-successor-069-88446f2e2831bb0d |
| dex-successor-088-b18c9c129af7fbfc | RETIRED_DUPLICATE | dex-successor-068-85b7ea76ae522727 |
| dex-successor-090-b5ad5642ccff0e2e | RETIRED_DUPLICATE | dex-successor-041-4a4be8bd60c050f5 |
| dex-successor-092-bd048c8b412c53b5 | RETIRED_DUPLICATE | dex-successor-025-2509c2f13f40a238 |
| dex-successor-094-c39421bc0ad61a44 | RETIRED_DUPLICATE | dex-successor-041-4a4be8bd60c050f5 |
| dex-successor-099-cb5e6c13704cb97a | RETIRED_DUPLICATE | dex-successor-025-2509c2f13f40a238 |
| dex-successor-101-d1cb0c9edad31cbf | RETIRED_DUPLICATE | dex-successor-026-25ad46e118f6edc9 |
| dex-successor-106-db27127f672cbae7 | RETIRED_DUPLICATE | dex-successor-019-1d5937dec4e156d4 |
| dex-successor-108-e44a1533954c80e5 | RETIRED_DUPLICATE | dex-successor-041-4a4be8bd60c050f5 |
| dex-successor-112-ea5a51ca3135e1b8 | RETIRED_DUPLICATE | dex-successor-041-4a4be8bd60c050f5 |
| dex-successor-118-f336bf0ae10004cd | RETIRED_DUPLICATE | dex-successor-032-30d85f39d76f4f18 |
| dex-successor-119-f3cf5416894220d7 | RETIRED_DUPLICATE | dex-successor-039-46f730df93b191f3 |
| dex-successor-121-fa93589262a321f9 | RETIRED_DUPLICATE | dex-successor-019-1d5937dec4e156d4 |
| dex-successor-122-fa9e8436a3a39c63 | RETIRED_DUPLICATE | dex-successor-019-1d5937dec4e156d4 |
| dex-successor-123-fdcf73ca24c18fcc | RETIRED_DUPLICATE | dex-successor-041-4a4be8bd60c050f5 |
| finalist_activity_failure_v1 | PAUSED_NEW_ENTRY | finalist_activity_failure_v1 |
| finalist_depth_divergence_v1 | PAUSED_NEW_ENTRY | finalist_depth_divergence_v1 |
| resource_profit_structure_candidate_v1 | PAUSED_NEW_ENTRY | resource_profit_structure_candidate_v1 |
| round2_response_exhaustion_candidate_v1 | PAUSED_NEW_ENTRY | round2_response_exhaustion_candidate_v1 |
| round2_runner_requalification_candidate_v1 | PAUSED_NEW_ENTRY | round2_runner_requalification_candidate_v1 |
| round2_slow_grace_candidate_v1 | PAUSED_NEW_ENTRY | round2_slow_grace_candidate_v1 |
