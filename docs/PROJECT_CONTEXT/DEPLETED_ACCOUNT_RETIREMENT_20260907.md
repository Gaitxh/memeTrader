# 资金接近耗尽账户退役

生效：2026-09-07T15:52:15.292170Z。用户要求移除接近亏光的账户并停止浪费计算资源。

本次按当前可见账户、可完整估值总权益低于50U/初始1000U（亏损超过95%）选出45个，并于部署前再次核验。余额不足但持仓较多、估值未知的账户不按零值退役。原来隐藏的65个不重复处理；默认可见165→120，历史账户仍共230。

使用新增按资金期隔离的loss-retirement操作记录，保留此前65账户收敛记录。停止主入口与独立observer的入场评估，排队投影沿用暂停拦截；界面隐藏，历史入口显示资金接近耗尽已退役。没有删除原账户/流水/合同，没有补款、重置资金或启用Live。

无持仓且收支/估值状态不变的退役账户不再周期性写入重复账户快照；已有持仓继续估值退出，最后退出、收支或校正变化仍写新快照。共享历史聚合与历史查询仍保留，不声称所有历史计算成本归零。

验证：10个Python定向用例通过，包含排队买入拦截、Solana/BSC已有持仓退役后退出、闲置快照停止与Web状态缓存；JS生命周期测试通过。只按现有脚本重启Paper及8790 Web一次。

实测验收：health running、原资金期/注册/追加合同/资金activation摘要一致。默认120、隐藏110，其中新退役45。观察窗新增交易9条，目标账户BUY=0；仅1个目标持仓账户产生1条新快照，44个空仓账户没有新快照，其他账户产生193条快照。没有跨退役/活动账户的主通道配对受影响。

不能据这次资源处置认证负alpha或推断实盘可成交。没有新增持续自动淘汰任务。原始选择、前沿和验收保留在 data/research/account_loss_retirement_20260907/。

| 账户 | 核验权益U | 当时持仓数 |
|---|---:|---:|
| canonical-0006b989b189e0ac | 15.460953 | 0 |
| canonical-05005fdaa932d3d0 | 10.425190 | 0 |
| canonical-0cd0f3c790d85ca5 | 15.337188 | 0 |
| canonical-0d7caccf76779d74 | 15.257705 | 0 |
| canonical-0df3639e1824ad0f | 7.113923 | 0 |
| dex-successor-012-0eea3c62cb7bacc4 | 19.136955 | 0 |
| canonical-195049e27d177b1f | 5.373594 | 0 |
| canonical-22dbe223b3814f7f | 7.113923 | 0 |
| canonical-2390fb342a6e90b6 | 18.226255 | 0 |
| dex-successor-032-30d85f39d76f4f18 | 19.136955 | 0 |
| dex-successor-039-46f730df93b191f3 | 19.136955 | 0 |
| canonical-4a27a58cc5902ea9 | 15.253002 | 0 |
| canonical-4b290f4f2bba4fb4 | 15.460953 | 0 |
| dex-successor-046-546560b93b10c79c | 13.448195 | 0 |
| dex-successor-049-5ce40de1d93304fb | 12.690290 | 0 |
| canonical-63e62a12e74b6320 | 19.512821 | 0 |
| canonical-75dadf52fc0cdd9e | 17.897475 | 0 |
| canonical-7c7c863ffc06fdf6 | 18.742221 | 0 |
| canonical-831b37e3aaeaa64d | 3.240595 | 0 |
| dex-successor-067-842383c9376853b7 | 19.136955 | 0 |
| dex-successor-068-85b7ea76ae522727 | 19.136955 | 0 |
| canonical-a0b46b71b30d8575 | 15.253002 | 0 |
| canonical-aa5d0c9d6721fb48 | 18.472053 | 0 |
| dex-successor-095-c78ed4ffa4877807 | 19.136955 | 0 |
| canonical-ca8f32cf0d565e07 | 48.562125 | 2 |
| canonical-ddd57b024d84a00b | 3.742275 | 0 |
| dex-successor-120-f98e117baa206954 | 16.443308 | 0 |
| broad_principal_lock_runner_v1 | 2.874685 | 0 |
| broad_flash_tail_first_mover_v1 | 9.768956 | 0 |
| broad_mature_continuity_control_v1 | 14.665292 | 0 |
| broad_cost_coverage_scaleout_v1 | 17.572330 | 0 |
| experiment_sustained_breakout_candidate_v1 | 4.677507 | 0 |
| experiment_sustained_breakout_control_v1 | 15.781028 | 0 |
| experiment_pullback_reclaim_control_v1 | 17.364502 | 0 |
| experiment_conditional_runner_candidate_v1 | 18.640418 | 0 |
| experiment_participation_candidate_v1 | 1.993712 | 0 |
| experiment_narrative_candidate_v1 | 17.510192 | 0 |
| experiment_narrative_control_v1 | 9.531769 | 0 |
| finite_capital_ranker_v1 | 18.655027 | 0 |
| authoritative_event_shock_v1 | 11.621801 | 0 |
| l0_continuation_failure_candidate_v1 | 16.300265 | 0 |
| l0_continuation_failure_control_v1 | 15.959372 | 0 |
| l0_profit_lock_candidate_v1 | 2.430893 | 0 |
| l0_profit_lock_control_v1 | 29.100736 | 0 |
| staged_probe_20u_once_control_v1 | 17.428190 | 0 |
