"""ALPHA149: additive entry/exit mechanisms for the shared observed-trajectory engine.

Design contract
---------------
* This module ONLY adds new strategy arms. It never changes an existing arm's
  thresholds, exits, sizing or account contract.
* Every mechanism is a pure function of the already-computed causal feature
  vector produced by ``dex_trajectory.derive``. No extra acquisition, no SQL,
  no wall-clock backfill, no peer/percentile state, no trading authority here.
* Missing values stay unknown: a mechanism returns False when its inputs are
  absent instead of substituting zero.
* All thresholds are frozen experimental definitions, not profitability claims.

Integration is a purely additive merge performed in ``dex_trajectory``:
``SPECS``/``EXIT_ARMS`` receive the new arms, ``mechanisms`` gains the new
flags, ``exit_reason`` delegates the new kinds, and ``policies`` applies the
per-arm sizing declared in ``OVERRIDES``.
"""
from collections import deque
from copy import deepcopy

from .dex_trajectory import Engine as _BaseEngine
from .models import iso, parse_time as _parse_time

VERSION = 'alpha149/v1'
# Round-trip friction used by the family: 4% buy + 4% sell (shared constant).
FRICTION = 1.04 / .96 - 1

# Volatility-scaled stop parameters. The multiple, floor and cap are frozen
# experimental definitions calibrated on the live distribution of the 30-second
# realized volatility (600 samples: p50 3.7%, p90 18.9%) against the shared
# fixed -20% stop this family has been measuring since wave 1.
VOL_STOP_MULTIPLE = 4.0
VOL_STOP_FLOOR = .22
VOL_STOP_CAP = .50

# Wave 12 regime throttle. The measured cross-section is mostly red: over 1,228
# minutes of live data only 13.3% of pools were rising on their latest frame at
# the median (p75 17.1%, max 37.8%), so an absolute breadth threshold would
# never fire. The gate is therefore RELATIVE to the engine's own recent breadth:
# the fast window's rising share must exceed the trailing share by 20% and stay
# above 15%, i.e. the tape has to be improving, not merely positive.
REGIME_RATIO_MIN = 1.2
REGIME_FAST_MIN = .15
REGIME_FAST_SAMPLES = 40
REGIME_MIN_SAMPLES = 120
REGIME_MAX_SAMPLES = 400

# Wave 14. The parent mechanism `resource_age_rate` fires when the current
# 5-minute rate is at least 3x the PRIOR 55-minute rate. The shared vector
# publishes the comparable whole-hour ratio, and old_rate = 11*a/(12-a), so the
# parent's 3x rule is a >= 36/14. Kept as the parent's own threshold.
AGE_RATE_MIN = 3.0
AGE_RATE_RATIO_EQUIVALENT = 36.0 / 14.0  # 2.5714..., only for tests/documentation

# Wave 16: stop scheduling. Measured over 12,773 settled hard stops, the realised
# loss lands deeper than its own threshold as the holding time grows:
#   <1m  p50 -5.05 points | 1-5m -6.25 | 5-30m -10.82 | 30-120m -11.36
# so a price stop late in a hold is the expensive kind, while max-hold and
# trailing exits are the only positive exit families. Two schedules are frozen
# here for testing: a price stop that is only armed during the first minutes, and
# one whose allowed drawdown shrinks as the hold extends.
EARLY_STOP_MINUTES = 5.0
EARLY_STOP_DISTANCE = .20
TIME_DECAY_CAP = .30
TIME_DECAY_SLOPE_PER_MINUTE = .006  # 30% at entry -> 12% after 30 minutes
TIME_DECAY_FLOOR = .12

# arm_id -> (mechanism kind, Chinese label, max_hold_minutes)
SPECS = {
    'alpha149_uncrowded_first_frame_v1': ('uncrowded_first_frame', '最早帧·无同伴依赖', 15),
    'alpha149_age_normalized_ignition_v1': ('age_normalized_ignition', '池龄归一化活动加速', 15),
    'alpha149_liquidity_expansion_lead_v1': ('liquidity_expansion_lead', '流动性扩张领先价格', 15),
    'alpha149_plateau_ignition_v1': ('plateau_ignition', '长平台后首次放量', 15),
    'alpha149_step_pump_fast_v1': ('step_pump_fast', '规律阶梯快进快出', 5),
    'alpha149_buy_share_extreme_v1': ('buy_share_extreme', '极端买盘占比吸筹', 15),
    'alpha149_liquidity_add_dip_recovery_v1': ('liquidity_add_dip_recovery', '回撤中加池承接', 15),
    'alpha149_gap_repair_continuation_v1': ('gap_repair_continuation', '断流补帧后延续', 5),
    'alpha149_friction_multiple_escape_v1': ('friction_multiple_escape', '成本倍数与池深前提', 10),
    'alpha149_multiframe_trend_confirm_v1': ('multiframe_trend_confirm', '多帧平滑趋势确认', 15),
    'alpha149_organic_short_burst_v1': ('organic_short_burst', '15秒极短有机放量', 5),
    'alpha149_writeoff_structure_avoid_v1': ('writeoff_structure_avoid', '薄池高FDV结构规避', 15),
    'alpha149_mature_revival_v1': ('mature_revival', '老池新一波（≥6小时）', 30),
    'alpha149_turnover_surge_v1': ('turnover_surge', '周转率上升而价格未动', 15),
    'alpha149_multi_horizon_agreement_v1': ('multi_horizon_agreement', '多尺度同向加速', 15),
    'alpha149_shallow_drawdown_impulse_v1': ('shallow_drawdown_impulse', '浅回撤强冲量', 15),
    'alpha149_elasticity_anomaly_fast_v1': ('elasticity_anomaly_fast', '薄池弹性异常快打', 5),
    'alpha149_squeeze_release_v1': ('squeeze_release', '波动压缩后释放', 15),
    'alpha149_smooth_organic_trend_v1': ('smooth_organic_trend', '平滑自然趋势（非阶梯）', 15),
    # wave 3: measured blockers -> add-only alternatives (see design doc §8)
    'alpha149_goldendog_early_impulse_v1': ('goldendog_early_impulse', '金狗·早期强冲量持有', 120),
    'alpha149_goldendog_shallow_stack_v1': ('goldendog_shallow_stack', '金狗·多尺度加速浅回撤', 60),
    'alpha149_goldendog_second_leg_v1': ('goldendog_second_leg', '金狗·浅整理后第二腿', 60),
    'alpha149_young_fast_lane_v1': ('young_fast_lane', '极早池快速通道', 5),
    'alpha149_two_frame_quick_entry_v1': ('two_frame_quick_entry', '双帧最快入场', 5),
    'alpha149_live_flow_revival_v1': ('live_flow_revival', '休眠流量族的在线替代路径', 15),
    'alpha149_baseline_free_absolute_v1': ('baseline_free_absolute', '免横截基线绝对条件', 15),
    'alpha149_depth_first_mature_v1': ('depth_first_mature', '老池深度优先（免池龄门）', 15),
    # wave 4: mechanisms that do NOT need a multi-frame window. The measured
    # supply gives p50 = 1 frame per pool and no 30-second window ever forms,
    # so these read single-frame state or a two-frame difference. Thresholds are
    # taken from the observed distribution (design doc §11).
    'alpha149_sf_deep_low_fdv_v1': ('sf_deep_low_fdv', '单帧·深池低FDV', 15),
    'alpha149_sf_extreme_buy_pressure_v1': ('sf_extreme_buy_pressure', '单帧·极端买压', 15),
    'alpha149_sf_young_turnover_v1': ('sf_young_turnover', '单帧·年轻池换手', 10),
    'alpha149_sf_quiet_absorption_v1': ('sf_quiet_absorption', '单帧·静默吸筹', 20),
    'alpha149_df_price_up_liquidity_up_v1': ('df_price_up_liquidity_up', '两帧·价涨且加池', 15),
    'alpha149_df_activity_jump_v1': ('df_activity_jump', '两帧·成交额跳增', 15),
    # wave 5: fill the entry/exit speed matrix with controlled same-fill pairs.
    # The three *_hold_* arms reuse an ALREADY FIRING mechanism kind and only
    # change the holding/exit contract, so fast-vs-slow exits are compared on
    # literally the same frozen signal. No new mechanism code.
    'alpha149_df_price_up_liquidity_up_hold_v1': ('df_price_up_liquidity_up', '两帧·价涨加池·慢出对照', 60),
    'alpha149_df_activity_jump_hold_v1': ('df_activity_jump', '两帧·成交额跳增·慢出对照', 45),
    'alpha149_sf_extreme_buy_pressure_hold_v1': ('sf_extreme_buy_pressure', '单帧·极端买压·慢出对照', 60),
    # two genuinely new kinds for the uncovered quadrants
    'alpha149_df_mature_price_up_fast_v1': ('df_mature_price_up', '老池两帧上涨·快出', 5),
    'alpha149_sf_goldendog_deep_base_v1': ('sf_goldendog_deep_base', '金狗·深池低FDV慢出', 120),
    # wave 6: designed from the measured golden-dog profile (design doc §13).
    'alpha149_righttail_lottery_v1': ('righttail_lottery', '右尾彩票·小额宽追踪', 180),
    'alpha149_dense_watch_breakout_v1': ('dense_watch_breakout', '高密度观测池的突破', 60),
    'alpha149_goldendog_liquidity_band_v1': ('goldendog_liquidity_band', '金狗·深度带内慢出', 120),
    # wave 7: revive still-viable hypotheses from paused/retired arms, expressed
    # with the now-feasible sequence machinery (frames per pool p50 is ~44).
    'alpha149_revival_inventory_contraction_v1': ('inv_contraction', '复活·库存收缩而价格持稳', 20),
    'alpha149_seq_price_then_depth_v1': ('seq_price_then_depth', '序列·价格先动深度随后', 30),
    'alpha149_seq_two_step_rise_v1': ('seq_two_step_rise', '序列·两步连续上行', 30),
    'alpha149_mature_two_step_slow_v1': ('mature_two_step_slow', '慢进慢出·老池两步上行长持', 90),
    # wave 8: the measured whipsaw defect. Of 383 hard stops in 48 hours (median
    # holding time at the stop: 1.1 minutes) 81.8% of the tokens traded above our
    # exit price within the next hour and the median best price afterwards was
    # +20.2% (p75 +86.5%), while trailing exits and max-hold exits were the only
    # positive exit families. These arms keep the ENTRY signal frozen and change
    # only the exit contract (grace period, mark confirmation, wider stop, later
    # trailing), so old and new exits are compared on literally the same signals.
    'alpha149_survive_noise_wide_v1': ('df_price_up_liquidity_up', '抗洗·同信号宽止损慢出', 120),
    'alpha149_survive_noise_confirm_v1': ('df_price_up_liquidity_up', '抗洗·同信号仅加确认', 60),
    'alpha149_merged_multi_setup_v1': ('merged_multi_setup', '合并·多形态宽止损慢出', 120),
    'alpha149_merged_multi_setup_fast_v1': ('merged_multi_setup', '合并·多形态快出对照', 15),
    'alpha149_goldendog_deep_hold_v1': ('sf_goldendog_deep_base', '金狗·深池极宽容忍长持', 240),
    # wave 9: the two conclusions of the washout measurement. (a) 81.8% of the
    # hard-stopped tokens traded above our exit within the next hour, so a pool
    # that has already been washed out and is reclaiming is a *different*
    # opportunity from a fresh breakout: `washout_reclaim` enters the reclaim,
    # not the washout. (b) the fixed -20% stop is ~5.4x the median observed 30s
    # realized volatility (p50 3.7%, p90 18.9% from 600 live samples) - for a
    # high-volatility pool it is barely one sigma - so `alpha149_vol_scaled_stop`
    # scales the stop with the pool's own measured volatility instead.
    'alpha149_washout_reclaim_v1': ('washout_reclaim', '洗出后回收·快出对照', 15),
    'alpha149_washout_reclaim_hold_v1': ('washout_reclaim', '洗出后回收·宽容忍慢出', 120),
    'alpha149_vol_scaled_merged_v1': ('merged_multi_setup', '波动率自适应止损·合并入场', 120),
    'alpha149_vol_scaled_goldendog_v1': ('sf_goldendog_deep_base', '波动率自适应止损·金狗深池', 240),
    # wave 10: entry survivability. Measured on 41,182 real closed positions
    # (7 days, active period) the write-off rate is 44.1% when the entry market
    # cap is below the pool depth (FDV/depth < 1) but 1.9% in the 5-20 band, and
    # the effect holds inside every chain (solana 31.9% -> 0.4%, bsc 53.1% ->
    # 8.8%, robinhood 11.2% -> 0.3%). Pool age at entry separates just as hard:
    # 22-23% write-off below 30 minutes versus 1.5% at 30-180 minutes, and the
    # worst cell of all is FDV/depth < 1 with a 5-30 minute pool at 54.0%.
    # Every previous wave selected FOR young pools and low FDV/depth, i.e. into
    # that cell; these arms select the measured survivable cells instead.
    'alpha149_survivable_core_v1': ('survivable_core', '存活带核心·快出对照', 60),
    'alpha149_survivable_core_scaled_v1': ('survivable_core', '存活带核心·自适应止损', 120),
    'alpha149_survivable_core_depthexit_v1': ('survivable_core', '存活带核心·深度衰减早退', 60),
    'alpha149_survivable_deep_v1': ('survivable_band_deep', '存活带深池·自适应止损', 120),
    # wave 11: consolidation + revival, both measured. The best arm in the whole
    # active period (resource_age_rate_candidate_v1, +634.96U over 220 positions)
    # earns its money with a SHORT hold: 110 max-hold exits at 30 minutes made
    # +767.61U, its 81 stops lost only -155.05U (-1.91U each, versus -4.85U
    # system-wide) and it took just 4 write-offs. The paused-arm audit found only
    # two paused arms with a positive record: market_regime_throttle_v1 (+19.62U,
    # n=9) and early_impulse_profit_lock_control_v1 (+18.56U, n=47). Wave 11
    # therefore re-expresses the measured survivable entries under that proven
    # short-hold exit profile, and re-expresses the paused early-impulse
    # hypothesis as a new id under its profitable control contract rather than
    # the +40% profit-lock treatment that lost -6.80U.
    'alpha149_survivable_fast30_v1': ('survivable_core', '存活带·30分钟快兑现', 30),
    'alpha149_survivable_deep_fast30_v1': ('survivable_band_deep', '存活带深池·30分钟1U', 30),
    'alpha149_merged_survivable_v1': ('merged_survivable', '合并×存活带·30分钟', 30),
    'alpha149_goldendog_revival_control_v1': ('goldendog_early_impulse', '复活·金狗早冲量对照合同', 60),
    # wave 12: revive the paused positive hypothesis market_regime_throttle_v1
    # (+19.62U over 9 positions, no write-offs) inside this family. The gate is a
    # causal breadth measure computed from frames the engine already accepted -
    # no new request, no absolute market claim, and no look-ahead.
    'alpha149_regime_throttle_revival_v1': ('regime_risk_on', '复活·市场宽度改善节流', 30),
    'alpha149_merged_regime_v1': ('merged_regime', '合并×宽度改善', 30),
    'alpha149_survivable_regime_v1': ('survivable_regime', '存活带×宽度改善', 30),
    # wave 13: buy after confirmation instead of tolerating afterwards.
    'alpha149_confirmed_survivable_v1': ('confirmed_survivable', '存活带×连续两步确认入场', 30),
    # wave 14: re-express the highest-PnL entry of the whole system inside this
    # family. resource_age_rate_candidate_v1 (+634.96U / 220 positions) and its
    # 15-minute sibling age_rate_horizon_fast_v1 (+109.91U / 75) share one frozen
    # age-rate entry; here that entry is rebuilt on the shared feature vector so
    # it can be paired with the measured best exit and with the survivability /
    # breadth filters that already exist.
    'alpha149_age_rate_accel_v1': ('age_rate_acceleration', '池龄归一化加速·30分钟', 30),
    'alpha149_age_rate_accel_fast_v1': ('age_rate_acceleration', '池龄归一化加速·15分钟', 15),
    # wave 15: the exit-contract experiment. Measured over 12,773 settled hard
    # stops (7 days, each compared against its OWN arm threshold): the settlement
    # frame is the same price as the trigger frame (gap p50 0.00%), but the
    # realised loss still lands a median 6.4 POINTS deeper than the threshold and
    # 87.4% of stops land deeper (26.1% more than 20 points deeper). The stop is
    # therefore not a level, it is a level plus gap risk. Three arms share one
    # frozen high-supply entry and differ only in that contract, so the question
    # "may a price stop be removed or pre-compensated?" becomes measurable.
    'alpha149_no_price_stop_v1': ('merged_multi_setup', '退出实验·不用价格止损', 30),
    'alpha149_precomp_stop_v1': ('merged_multi_setup', '退出实验·预补偿止损', 30),
    'alpha149_nominal_stop_control_v1': ('merged_multi_setup', '退出实验·名义止损对照', 30),
    # wave 16: stop scheduling. Measured overshoot grows with holding time, so a
    # price stop late in a hold is the expensive kind. Two schedules, same frozen
    # entry and same trailing/horizon as the wave-15 control.
    'alpha149_early_stop_only_v1': ('merged_multi_setup', '退出实验·仅前5分钟价格止损', 30),
    'alpha149_time_decay_stop_v1': ('merged_multi_setup', '退出实验·止损随时间收紧', 30),
    # wave 17: the measured safest sub-band (FDV/depth 5-20) with the measured
    # loss-dominant exit (the hard stop) removed, and its control.
    'alpha149_mid_band_nodeadstop_v1': ('survivable_band_mid', '安全带中段·不用价格止损', 60),
    'alpha149_mid_band_control_v1': ('survivable_band_mid', '安全带中段·原止损对照', 60),
}
EXIT_ARMS = {
    'alpha149_profit_decay_exit_v1': 'alpha149_profit_decay',
    'alpha149_liquidity_shock_exit_v1': 'alpha149_liquidity_shock',
    'alpha149_plateau_stall_exit_v1': 'alpha149_plateau_stall',
    'alpha149_peak_giveback_exit_v1': 'alpha149_peak_giveback',
    'alpha149_flat_dead_exit_v1': 'alpha149_flat_dead',
    'alpha149_righttail_wide_exit_v1': 'alpha149_righttail_wide',
    'alpha149_momentum_floor_exit_v1': 'alpha149_momentum_floor',
    # wave 9: same-signal carrier for the volatility-scaled stop.
    'alpha149_vol_scaled_exit_v1': 'alpha149_vol_scaled_stop',
    # wave 10: leave a dying pool before it breaches the write-off floor.
    'alpha149_depth_decay_exit_v1': 'alpha149_depth_decay',
    # wave 16: two stop schedules on the same frozen entry.
    'alpha149_early_stop_only_exit_v1': 'alpha149_early_stop_only',
    'alpha149_time_decay_stop_exit_v1': 'alpha149_time_decay_stop',
}
EXIT_KINDS = frozenset(EXIT_ARMS.values())
KINDS = tuple(kind for kind, _, _ in SPECS.values())
ALL_ARMS = tuple(SPECS) + tuple(EXIT_ARMS)
# Wave 8: the anti-whipsaw arms. They are ordinary new arms; they are also the
# only arms allowed to declare the opt-in exit guards in the shared evaluator.
WAVE8_ARMS = frozenset({
    'alpha149_survive_noise_wide_v1',
    'alpha149_survive_noise_confirm_v1',
    'alpha149_merged_multi_setup_v1',
    'alpha149_merged_multi_setup_fast_v1',
    'alpha149_goldendog_deep_hold_v1',
})
WAVE8_ENTRY_KINDS = {
    'alpha149_survive_noise_wide_v1': 'df_price_up_liquidity_up',
    'alpha149_survive_noise_confirm_v1': 'df_price_up_liquidity_up',
    'alpha149_merged_multi_setup_v1': 'merged_multi_setup',
    'alpha149_merged_multi_setup_fast_v1': 'merged_multi_setup',
    'alpha149_goldendog_deep_hold_v1': 'sf_goldendog_deep_base',
}
# Wave 9: washout re-entry and the volatility-scaled stop.
WAVE9_ARMS = frozenset({
    'alpha149_washout_reclaim_v1',
    'alpha149_washout_reclaim_hold_v1',
    'alpha149_vol_scaled_merged_v1',
    'alpha149_vol_scaled_goldendog_v1',
    'alpha149_vol_scaled_exit_v1',
})
# Arms that legitimately declare the opt-in exit guards; every other arm must
# stay untouched by them.
GUARD_ARMS = WAVE8_ARMS | {'alpha149_washout_reclaim_hold_v1'}

# Per-arm sizing / exit overrides. Anything not listed keeps the family default
# produced by dex_trajectory.policies (5U, max 2, hard stop -20%, trail 30/15).
OVERRIDES = {
    'alpha149_step_pump_fast_v1': dict(
        notional_usd=1.0, max_concurrent_positions=1, absolute_max_hold_seconds=300,
        trailing_activate_return=.20, trailing_drawdown=.12,
        description='仅按路径规律性（单调阶梯+规律跳涨间隔）的1U单仓5分钟Paper实验；'
                    '人工拉升随时可能反向，非已证Alpha，硬风险退出优先。'),
    'alpha149_friction_multiple_escape_v1': dict(
        notional_usd=5.0, max_concurrent_positions=2,
        hard_stop_return=-.12, trailing_activate_return=.25, trailing_drawdown=.10,
        description='仅在30秒位移≥3倍往返摩擦且原池深度≥3000U时入场；'
                    '以可回收空间为前提，收紧硬止损与追踪兑现。'),
    'alpha149_gap_repair_continuation_v1': dict(
        notional_usd=2.0, max_concurrent_positions=2,
        description='观察断流（>30秒无合格帧）后连续性重建的首段；2U最多2仓5分钟。'),
    'alpha149_multiframe_trend_confirm_v1': dict(
        notional_usd=2.0, max_concurrent_positions=2,
        description='要求≥5个独立帧、对数价格R²≥0.8且残差离散度低；2U最多2仓15分钟。'),
    'alpha149_organic_short_burst_v1': dict(
        notional_usd=2.0, max_concurrent_positions=2,
        description='只看最近15秒的真实连续放量（≥3个独立帧）：涨幅过半个摩擦、'
                    '买笔占比过半、笔数上升；2U最多2仓5分钟。'),
    'alpha149_writeoff_structure_avoid_v1': dict(
        notional_usd=2.0, max_concurrent_positions=2, hard_stop_return=-.15,
        description='先规避最易核销的结构：原池深度≥5000U且FDV/流动性≤500，'
                    '再要求30秒上涨与流动性不降；2U最多2仓15分钟。'),
    'alpha149_mature_revival_v1': dict(
        notional_usd=2.0, max_concurrent_positions=2,
        description='池龄≥6小时的老池出现按龄归一化活动加速与30秒上涨；'
                    '不依赖回撤叙事，2U最多2仓30分钟。'),
    'alpha149_turnover_surge_v1': dict(
        notional_usd=2.0, max_concurrent_positions=2,
        description='成交额/流动性周转率>2而价格仍在半个摩擦内：关注度先起、价格未反映；'
                    '2U最多2仓15分钟。'),
    'alpha149_multi_horizon_agreement_v1': dict(
        notional_usd=2.0, max_concurrent_positions=2,
        description='15/30/60秒三个尺度收益同为正且短尺度速度高于长尺度；'
                    '2U最多2仓15分钟。'),
    'alpha149_shallow_drawdown_impulse_v1': dict(
        notional_usd=2.0, max_concurrent_positions=2,
        description='上涨中回撤始终浅于四分之一摩擦（强势不回头）；2U最多2仓15分钟。'),
    'alpha149_elasticity_anomaly_fast_v1': dict(
        notional_usd=1.0, max_concurrent_positions=1, absolute_max_hold_seconds=300,
        trailing_activate_return=.20, trailing_drawdown=.12,
        description='薄池（<20k）中成交额撬动异常大涨幅，弹性代理≥10；'
                    '1U单仓5分钟快打，人工盘随时反向。'),
    'alpha149_squeeze_release_v1': dict(
        notional_usd=2.0, max_concurrent_positions=2,
        description='长窗口波动压缩（≤1个摩擦）后短窗口波动放大且价格上涨；'
                    '2U最多2仓15分钟。'),
    'alpha149_smooth_organic_trend_v1': dict(
        notional_usd=2.0, max_concurrent_positions=2,
        description='低平台占比+高单调性+对数价格R²≥0.6（自然趋势，与阶梯盘相反）；'
                    '2U最多2仓15分钟。'),
    'alpha149_peak_giveback_exit_v1': dict(
        notional_usd=5.0, description='共享冲量冻结信号；相对已观察到的运行高点回撤≥25%即退出。'),
    'alpha149_flat_dead_exit_v1': dict(
        notional_usd=5.0, description='共享冲量冻结信号；平台占比高、笔数腰斩且无上行速度时释放资金。'),
    # ---- wave 3 overrides ----
    'alpha149_goldendog_early_impulse_v1': dict(
        notional_usd=5.0, max_concurrent_positions=2,
        trailing_activate_return=.25, trailing_drawdown=.18,
        description='金狗画像的早期强冲量：池龄≤10分钟、30秒涨幅≥2倍摩擦、买笔占比>55%、'
                    '原池深度≥2000U且回撤浅；延长持有到120分钟以保留右尾，硬风险与追踪优先。'),
    'alpha149_goldendog_shallow_stack_v1': dict(
        notional_usd=5.0, max_concurrent_positions=2,
        trailing_activate_return=.25, trailing_drawdown=.18,
        description='金狗画像的多尺度加速：15/30/60秒速度递增且回撤浅、流动性保持≥1.0；'
                    '持有至60分钟，用追踪而非固定止盈保留右尾。'),
    'alpha149_goldendog_second_leg_v1': dict(
        notional_usd=5.0, max_concurrent_positions=2,
        trailing_activate_return=.20, trailing_drawdown=.15,
        description='第一腿≥2倍摩擦后仅做浅整理（回撤<1倍摩擦）再加速；按新episode入场，'
                    '持有至60分钟；不靠扛旧仓等待反弹。'),
    'alpha149_young_fast_lane_v1': dict(
        notional_usd=2.0, max_concurrent_positions=2,
        description='池龄≤120秒的极早通道：只用15秒窗口与真实连续帧，深度≥1500U即可；'
                    '2U最多2仓5分钟。目的是让信号在池子极早期成立，从而更早等到下一帧成交。'),
    'alpha149_two_frame_quick_entry_v1': dict(
        notional_usd=2.0, max_concurrent_positions=2,
        description='最少帧入场：15秒窗口≥2个独立帧且涨幅>半个摩擦、深度≥2000U；'
                    '信号尽早成立以缩短“等下一帧”的等待。'),
    'alpha149_live_flow_revival_v1': dict(
        notional_usd=2.0, max_concurrent_positions=2,
        description='为已休眠的流量族提供在线替代路径：直接用现有连续原池特征表达'
                    '“成交额与笔数加速+买笔占比过半+流动性不降”，不依赖已停产的采集面。'),
    'alpha149_baseline_free_absolute_v1': dict(
        notional_usd=2.0, max_concurrent_positions=2,
        description='不依赖横截基线/共识：只用绝对条件（30秒涨幅≥1倍摩擦、周转率>1、深度≥3000U）；'
                    '用于绕开“等待共同基线/可比正样本”这类可能长期不成立的等待。'),
    'alpha149_depth_first_mature_v1': dict(
        notional_usd=2.0, max_concurrent_positions=2,
        description='老池（≥30分钟）深度优先：深度≥10000U、30秒上涨、周转率>0.5；'
                    '不设池龄上限，用于被“池龄未达/等待成熟池”长期拒绝的机会。'),
    'alpha149_righttail_wide_exit_v1': dict(
        notional_usd=5.0, description='共享冻结信号；仅在相对运行高点回撤≥35%或流动性冲击时退出，'
                                      '给右尾更宽的容忍度。'),
    'alpha149_momentum_floor_exit_v1': dict(
        notional_usd=5.0, description='共享冻结信号；速度与加速度同负且周转率<1即退出（动量地板）。'),
    'alpha149_profit_decay_exit_v1': dict(
        notional_usd=5.0, description='共享冲量冻结信号；速度与加速度同负且活动回落即退出。'),
    'alpha149_liquidity_shock_exit_v1': dict(
        notional_usd=5.0, description='共享冲量冻结信号；原池流动性单窗口骤降超过两倍摩擦即退出。'),
    'alpha149_plateau_stall_exit_v1': dict(
        notional_usd=5.0, description='共享冲量冻结信号；滞涨（平台占比升高且笔数回落）即兑现。'),
    # ---- wave 4: no-window mechanisms, thresholds from the measured supply ----
    'alpha149_sf_deep_low_fdv_v1': dict(
        notional_usd=2.0, max_concurrent_positions=2,
        description='单帧结构：深度≥5000U、FDV/深度≤0.7（实测p10）、买笔占比≥0.58（实测p50）；'
                    '不需要多帧窗口。2U最多2仓15分钟。'),
    'alpha149_sf_extreme_buy_pressure_v1': dict(
        notional_usd=2.0, max_concurrent_positions=2, hard_stop_return=-.15,
        description='单帧买压：买笔占比≥0.9（实测p50=0.58、p90=1.0）且深度≥2000U、换手>0.1；'
                    '2U最多2仓15分钟。'),
    'alpha149_sf_young_turnover_v1': dict(
        notional_usd=2.0, max_concurrent_positions=2,
        description='单帧年轻池：池龄≤900秒、换手≥0.3（实测p90=0.41）、深度≥1500U；'
                    '2U最多2仓10分钟。'),
    'alpha149_sf_quiet_absorption_v1': dict(
        notional_usd=2.0, max_concurrent_positions=2,
        description='单帧静默吸筹：价格处于运行高点（回撤=0，实测p50=0）、买笔占比≥0.65、'
                    '深度≥3000U、FDV/深度≤1.2；2U最多2仓20分钟。'),
    'alpha149_df_price_up_liquidity_up_v1': dict(
        notional_usd=2.0, max_concurrent_positions=2,
        description='两帧差分：本帧价格高于上一帧且深度同时增加；在实测供给下这是可用的最短真实信号'
                    '（不需要30秒窗口）。2U最多2仓15分钟。'),
    'alpha149_df_activity_jump_v1': dict(
        notional_usd=2.0, max_concurrent_positions=2,
        description='两帧差分：本帧成交额≥上一帧1.5倍且价格不跌、买笔占比≥0.5；'
                    '2U最多2仓15分钟。'),
    # ---- wave 5: controlled same-fill entry/exit speed pairs -----------------
    'alpha149_df_price_up_liquidity_up_hold_v1': dict(
        notional_usd=2.0, max_concurrent_positions=2,
        trailing_activate_return=.20, trailing_drawdown=.15,
        description='与 df_price_up_liquidity_up 完全同一冻结信号，仅把持有期从15分钟延长到60分钟；'
                    '用于在同一入场上的快出/慢出受控对照（不是新入场条件）。'),
    'alpha149_df_activity_jump_hold_v1': dict(
        notional_usd=2.0, max_concurrent_positions=2,
        trailing_activate_return=.20, trailing_drawdown=.15,
        description='与 df_activity_jump 完全同一冻结信号，仅把持有期从15分钟延长到45分钟；'
                    '同入场快出/慢出对照。'),
    'alpha149_sf_extreme_buy_pressure_hold_v1': dict(
        notional_usd=2.0, max_concurrent_positions=2,
        trailing_activate_return=.20, trailing_drawdown=.15,
        description='与 sf_extreme_buy_pressure 完全同一冻结信号，持有期延长到60分钟；'
                    '同入场快出/慢出对照。'),
    'alpha149_df_mature_price_up_fast_v1': dict(
        notional_usd=2.0, max_concurrent_positions=2,
        description='慢进快出象限：池龄≥30分钟的老池出现两帧价涨且加池，只做5分钟快出；'
                    '2U最多2仓。'),
    'alpha149_sf_goldendog_deep_base_v1': dict(
        notional_usd=2.0, max_concurrent_positions=2,
        trailing_activate_return=.25, trailing_drawdown=.20,
        description='金狗慢出象限：池龄≤15分钟、深度≥8000U、FDV/深度≤0.8、买笔占比≥0.55、'
                    '价格处于运行高点；持有至120分钟并用较宽追踪保留右尾。'),
    # ---- wave 6: right-tail design from the measured golden-dog profile -------
    'alpha149_righttail_lottery_v1': dict(
        notional_usd=1.0, max_concurrent_positions=2,
        trailing_activate_return=.30, trailing_drawdown=.40, absolute_max_hold_seconds=10800,
        description='右尾彩票：实测金狗 73% 达到≥5x、对照仅 3%，但中位新币只有 1.01x，'
                    '因此用 1U 小额 + 180 分钟 + 40% 宽追踪换取尾部暴露，接受多数小额亏损。'),
    'alpha149_dense_watch_breakout_v1': dict(
        notional_usd=2.0, max_concurrent_positions=2,
        trailing_activate_return=.25, trailing_drawdown=.20,
        description='使用实测最强判别特征（本机观测帧数：金狗 p50=74 vs 对照 p50=6）：'
                    '该池已有≥8帧且本帧价涨、深度不降；持有至60分钟。'),
    'alpha149_goldendog_liquidity_band_v1': dict(
        notional_usd=2.0, max_concurrent_positions=2,
        trailing_activate_return=.25, trailing_drawdown=.20,
        description='金狗首帧深度带（实测 p50≈19.4k、p90≈56.8k）：深度 10k–100k、池龄≤2小时、'
                    '买笔占比≥0.55、FDV/深度≤2；持有至120分钟。'),
    # ---- wave 7: revived hypotheses, sequence-based ---------------------------
    'alpha149_revival_inventory_contraction_v1': dict(
        notional_usd=2.0, max_concurrent_positions=2,
        description='复活"库存收缩"假设（原臂从未成交）：两帧内深度收缩而价格持稳、买笔≥0.5，'
                    '表示供给被抽走；持有至20分钟。'),
    'alpha149_seq_price_then_depth_v1': dict(
        notional_usd=2.0, max_concurrent_positions=2,
        description='复活"价格先行、深度随后"假设（原 finalist_price_then_depth 从未成交）：'
                    '三帧序列，上一步价涨且深度未增，本步深度跟进；持有至30分钟。'),
    'alpha149_seq_two_step_rise_v1': dict(
        notional_usd=2.0, max_concurrent_positions=2,
        description='持续而非单点：连续两步价格上行且深度≥3000U；用于区分"真趋势"与"单帧尖峰"。'
                    '持有至30分钟。'),
    'alpha149_mature_two_step_slow_v1': dict(
        notional_usd=2.0, max_concurrent_positions=2,
        trailing_activate_return=.20, trailing_drawdown=.15,
        description='最后一个空象限（慢进×慢出）：老池（≥30分钟）连续两步上行、深度≥5000U、'
                    '买笔≥0.5；持有至90分钟，追踪退出优先。'),
    # ---- wave 8: hold through normal amplitude --------------------------------
    # Measured defect (48h, 383 hard stops): median holding time at the stop was
    # 1.1 minutes, yet 81.8% of those tokens traded above our exit within the next
    # hour (median best +20.2%). A -20% stop inside the first minutes therefore
    # sells normal memecoin amplitude. The three new fields are opt-in and read
    # only by arms that declare them:
    #   hard_stop_grace_seconds            - no price stop before N seconds
    #   hard_stop_confirm_marks            - N consecutive marks below the level
    #   hard_stop_liquidity_veto_usd/share - a still-deep pool with buy dominance
    #                                        is a dip, not a breakdown
    # Liquidity/rug exits are deliberately NOT gated: those remain immediate.
    'alpha149_survive_noise_wide_v1': dict(
        notional_usd=2.0, max_concurrent_positions=2,
        excess_return_vs_arm='alpha149_df_price_up_liquidity_up_v1',
        hard_stop_return=-.45, hard_stop_grace_seconds=180, hard_stop_confirm_marks=2,
        hard_stop_liquidity_veto_usd=3000., hard_stop_liquidity_veto_min_buy_share=.5,
        trailing_activate_return=.45, trailing_drawdown=.25,
        description='抗洗对照：入场信号与 df_price_up_liquidity_up 完全相同，只改退出合同——'
                    '前180秒不用价格止损、需连续2帧跌破-45%、池深≥3000U且买盘占优时不因下跌离场；'
                    '追踪在+45%激活、回撤25%离场，持有至120分钟。'),
    'alpha149_survive_noise_confirm_v1': dict(
        notional_usd=2.0, max_concurrent_positions=2,
        excess_return_vs_arm='alpha149_df_price_up_liquidity_up_v1',
        hard_stop_grace_seconds=60, hard_stop_confirm_marks=2,
        description='抗洗对照（只加确认，不放宽止损）：同一入场信号，仍保留-20%止损，但前60秒不触发、'
                    '且必须连续2帧跌破才卖出；用于把"确认延迟"与"放宽止损"两个因素分开。'),
    'alpha149_merged_multi_setup_v1': dict(
        notional_usd=2.0, max_concurrent_positions=2,
        excess_return_vs_arm='alpha149_merged_multi_setup_fast_v1',
        hard_stop_return=-.45, hard_stop_grace_seconds=180, hard_stop_confirm_marks=2,
        hard_stop_liquidity_veto_usd=3000., hard_stop_liquidity_veto_min_buy_share=.5,
        trailing_activate_return=.45, trailing_drawdown=.25,
        description='合并整合：把两帧价涨加池、两帧成交额跳增、单帧极端买压、金狗早期冲量、'
                    '高密度观测突破五个独立设定合成一个入场（任一成立即入场，成员标记仍逐项记录），'
                    '覆盖更多市场情形；退出用抗洗合同并持有至120分钟。'),
    'alpha149_merged_multi_setup_fast_v1': dict(
        notional_usd=2.0, max_concurrent_positions=2,
        excess_return_vs_arm='alpha149_merged_multi_setup_v1',
        description='合并入场的快出对照：与 merged_multi_setup 同一入场，保持原-20%止损、无宽限期、'
                    '持有至15分钟；与慢出臂构成同一入场上的受控比较。'),
    'alpha149_goldendog_deep_hold_v1': dict(
        notional_usd=1.0, max_concurrent_positions=2,
        excess_return_vs_arm='alpha149_sf_goldendog_deep_base_v1',
        hard_stop_return=-.55, hard_stop_grace_seconds=300, hard_stop_confirm_marks=3,
        hard_stop_liquidity_veto_usd=5000., hard_stop_liquidity_veto_min_buy_share=.5,
        trailing_activate_return=.60, trailing_drawdown=.30,
        description='金狗最大容忍实验：入场与 sf_goldendog_deep_base 相同，退出改为前300秒不设价格止损、'
                    '连续3帧跌破-55%才离场、深池买盘占优时容忍回撤，追踪+60%激活、回撤30%离场，'
                    '持有至240分钟；1U小额换取右尾保留。'),
    # ---- wave 9: washout re-entry + volatility-scaled stop --------------------
    'alpha149_washout_reclaim_v1': dict(
        notional_usd=2.0, max_concurrent_positions=2,
        excess_return_vs_arm='alpha149_washout_reclaim_hold_v1',
        description='洗出后回收（快出对照）：池已从本段高点回撤≥12%、当前帧重新上行、深度不流失、'
                    '买盘占比≥50%、深度≥2000U、本池已有≥4帧时入场；保留原-20%止损、持有15分钟。'),
    'alpha149_washout_reclaim_hold_v1': dict(
        notional_usd=2.0, max_concurrent_positions=2,
        excess_return_vs_arm='alpha149_washout_reclaim_v1',
        hard_stop_return=-.45, hard_stop_grace_seconds=180, hard_stop_confirm_marks=2,
        hard_stop_liquidity_veto_usd=3000., hard_stop_liquidity_veto_min_buy_share=.5,
        trailing_activate_return=.45, trailing_drawdown=.25,
        description='洗出后回收（慢出）：与快出臂完全同一入场信号，退出改为宽限180秒、连续2帧跌破-45%、'
                    '深池买盘占优时容忍；追踪+45%激活/回撤25%，持有至120分钟。'),
    'alpha149_vol_scaled_merged_v1': dict(
        notional_usd=2.0, max_concurrent_positions=2,
        excess_return_vs_arm='alpha149_merged_multi_setup_v1',
        trajectory_exit='alpha149_vol_scaled_stop',
        hard_stop_return=-.90, trailing_activate_return=.45, trailing_drawdown=.25,
        description='波动率自适应止损（合并入场）：入场与 merged_multi_setup 相同，价格止损改为'
                    '4倍本池30秒实现波动率（下限22%、上限50%），-90%仅作灾难兜底；'
                    '追踪+45%激活/回撤25%，持有至120分钟。'),
    'alpha149_vol_scaled_goldendog_v1': dict(
        notional_usd=1.0, max_concurrent_positions=2,
        excess_return_vs_arm='alpha149_goldendog_deep_hold_v1',
        trajectory_exit='alpha149_vol_scaled_stop',
        hard_stop_return=-.90, trailing_activate_return=.60, trailing_drawdown=.30,
        description='波动率自适应止损（金狗深池）：入场与 sf_goldendog_deep_base 相同，'
                    '价格止损改为4倍本池30秒实现波动率（下限22%/上限50%），追踪+60%激活、'
                    '回撤30%离场，持有至240分钟；1U小额。'),
    'alpha149_vol_scaled_exit_v1': dict(
        notional_usd=2.0, max_concurrent_positions=2,
        excess_return_vs_arm='alpha149_righttail_wide_exit_v1',
        trajectory_exit='alpha149_vol_scaled_stop',
        hard_stop_return=-.90, trailing_activate_return=.45, trailing_drawdown=.25,
        description='波动率自适应止损（同信号载体臂）：与其它退出臂一样搭载本池第一条ALPHA149入场信号，'
                    '只用自适应止损+追踪退出，用于在同一机会上比较固定止损与自适应止损。'),
    # ---- wave 10: entry survivability ---------------------------------------
    # The measured write-off rate is dominated by two entry-time facts, and both
    # are available before the trade: FDV/depth below 1 (44.1% write-off versus
    # 1.9% in the 5-20 band) and a pool younger than 30 minutes (22-23% versus
    # 1.5% at 30-180 minutes). The previous waves selected FOR both.
    'alpha149_survivable_core_v1': dict(
        notional_usd=2.0, max_concurrent_positions=2,
        excess_return_vs_arm='alpha149_survivable_core_depthexit_v1',
        hard_stop_return=-.35, trailing_activate_return=.30, trailing_drawdown=.15,
        description='存活带核心（快出对照）：池龄30-180分钟、FDV/深度1-20、深度≥5000U、'
                    '当前帧价涨且深度不流失、买盘≥50%；原止损-35%、持有60分钟。'),
    'alpha149_survivable_core_scaled_v1': dict(
        notional_usd=2.0, max_concurrent_positions=2,
        excess_return_vs_arm='alpha149_survivable_core_v1',
        trajectory_exit='alpha149_vol_scaled_stop',
        hard_stop_return=-.90, trailing_activate_return=.45, trailing_drawdown=.25,
        description='存活带核心（自适应止损）：与快出对照完全同一入场，价格止损改为'
                    '4倍本池30秒实现波动率（下限22%/上限50%），追踪+45%→25%，持有120分钟。'),
    'alpha149_survivable_core_depthexit_v1': dict(
        notional_usd=2.0, max_concurrent_positions=2,
        excess_return_vs_arm='alpha149_survivable_core_v1',
        trajectory_exit='alpha149_depth_decay',
        hard_stop_return=-.35, trailing_activate_return=.30, trailing_drawdown=.15,
        description='存活带核心（深度衰减早退）：与快出对照同一入场，但在“深度30秒收缩≥15% '
                    '且换手<0.1 且深度保留≤0.8”时提前离场，用于检验能否在跌破写销底线前退出。'),
    'alpha149_survivable_deep_v1': dict(
        notional_usd=1.0, max_concurrent_positions=2,
        excess_return_vs_arm='alpha149_survivable_core_scaled_v1',
        trajectory_exit='alpha149_vol_scaled_stop',
        hard_stop_return=-.90, trailing_activate_return=.45, trailing_drawdown=.25,
        description='存活带深池：池龄30-180分钟、FDV/深度≥5（实测1.9%-4.1%写销带）、深度≥10000U、'
                    '当前帧价涨、买盘≥55%；自适应止损+追踪，1U小额。'),
    # ---- wave 11: consolidation with the measured best exit profile -----------
    # Short-hold contract: hold 30 minutes, -20% stop, trailing 30/15. This is the
    # profile that made the money for the strongest arm of the period, so it is
    # reused verbatim on the measured survivable entries instead of inventing a
    # new exit.
    'alpha149_survivable_fast30_v1': dict(
        notional_usd=2.0, max_concurrent_positions=2,
        excess_return_vs_arm='alpha149_survivable_core_v1',
        hard_stop_return=-.20, trailing_activate_return=.30, trailing_drawdown=.15,
        description='存活带×30分钟兑现：入场与 survivable_core 相同，退出改用实测最强臂的合同'
                    '（-20%止损、+30%激活追踪、回撤15%离场、持有30分钟），'
                    '用于检验"存活入场+短兑现"的合并是否优于长持有。'),
    'alpha149_survivable_deep_fast30_v1': dict(
        notional_usd=1.0, max_concurrent_positions=2,
        excess_return_vs_arm='alpha149_survivable_deep_v1',
        hard_stop_return=-.20, trailing_activate_return=.30, trailing_drawdown=.15,
        description='存活带深池×30分钟（1U）：入场与 survivable_band_deep 相同，退出用短兑现合同。'),
    'alpha149_merged_survivable_v1': dict(
        notional_usd=2.0, max_concurrent_positions=2,
        excess_return_vs_arm='alpha149_merged_multi_setup_v1',
        hard_stop_return=-.20, trailing_activate_return=.30, trailing_drawdown=.15,
        description='合并×存活带：入场=五形态合并 且 同时满足存活带（池龄30-180分钟、FDV/深度1-20、'
                    '深度≥5000U、买盘≥50%），只在两个独立条件同时成立时入场；退出用短兑现合同。'),
    'alpha149_goldendog_revival_control_v1': dict(
        notional_usd=2.0, max_concurrent_positions=2,
        excess_return_vs_arm='alpha149_goldendog_early_impulse_v1',
        hard_stop_return=-.20, trailing_activate_return=.30, trailing_drawdown=.15,
        description='复活已暂停的正收益假设：入场沿用 goldendog_early_impulse，但退出采用该假设当年'
                    '盈利的对照合同（-20%止损、追踪30/15、持有60分钟），而不是亏损的固定+40%锁利；'
                    '全部以新ID加入，原臂保持暂停与历史不变。'),
    # ---- wave 12: the paused market-regime hypothesis, revived --------------
    'alpha149_regime_throttle_revival_v1': dict(
        notional_usd=2.0, max_concurrent_positions=2,
        excess_return_vs_arm='alpha149_survivable_fast30_v1',
        hard_stop_return=-.20, trailing_activate_return=.30, trailing_drawdown=.15,
        description='复活市场状态节流（原 market_regime_throttle_v1 为 +19.62U/9笔/0写销）：'
                    '只在引擎自身观测到的市场宽度相对改善时入场（近40帧上涨占比≥全程×1.2且≥15%），'
                    '退出用实测最强短兑现合同。宽度只用已接受的帧计算，不新增请求、无前视。'),
    'alpha149_merged_regime_v1': dict(
        notional_usd=2.0, max_concurrent_positions=2,
        excess_return_vs_arm='alpha149_merged_multi_setup_v1',
        hard_stop_return=-.20, trailing_activate_return=.30, trailing_drawdown=.15,
        description='合并×宽度改善：五形态合并 与 市场宽度改善 同时成立才入场；短兑现合同。'),
    'alpha149_survivable_regime_v1': dict(
        notional_usd=2.0, max_concurrent_positions=2,
        excess_return_vs_arm='alpha149_survivable_fast30_v1',
        hard_stop_return=-.20, trailing_activate_return=.30, trailing_drawdown=.15,
        description='存活带×宽度改善：实测存活带 与 市场宽度改善 同时成立；短兑现合同。'
                    '用于检验"好池子"与"好时机"是否需要同时满足。'),
    # ---- wave 13: confirmation on the entry side ----------------------------
    'alpha149_confirmed_survivable_v1': dict(
        notional_usd=2.0, max_concurrent_positions=2,
        excess_return_vs_arm='alpha149_survivable_fast30_v1',
        hard_stop_return=-.20, trailing_activate_return=.30, trailing_drawdown=.15,
        description='存活带×连续两步确认：在实测存活带之内，还要求本池已连续两个观测帧上行'
                    '（相当于把成交推迟一帧，先确认再买入）；退出用实测最强短兑现合同。'
                    '依据：前向数据显示对照臂在入场后23秒与25秒即触发硬止损，'
                    '即单帧入场买在回撤里、由噪音付费。'),
    # ---- wave 14: the system's best entry, rebuilt on the shared vector -------
    'alpha149_age_rate_accel_v1': dict(
        notional_usd=2.0, max_concurrent_positions=2,
        excess_return_vs_arm='alpha149_age_rate_accel_fast_v1',
        hard_stop_return=-.20, trailing_activate_return=.30, trailing_drawdown=.15,
        description='池龄归一化加速（30分钟）：池龄15分钟-6小时、深度≥5000U、'
                    '5分钟活动率≥其自身按龄归一小时率的3倍（成交额或笔数取强者）、'
                    '有真实活动且买盘≥50%；复刻本系统收益最高入场机制（resource_age_rate，'
                    '+634.96U/220笔）的判据，并用实测最强短兑现合同持有至30分钟。'),
    'alpha149_age_rate_accel_fast_v1': dict(
        notional_usd=2.0, max_concurrent_positions=2,
        excess_return_vs_arm='alpha149_age_rate_accel_v1',
        description='池龄归一化加速（15分钟）：与30分钟臂完全同一入场信号，只把持有期改为15分钟，'
                    '复刻系统已验证的15/30分钟配对（age_rate_horizon_fast_v1 +109.91U）。'),
    # ---- wave 15: the exit-contract experiment ---------------------------------
    # One frozen entry (the highest-supply merge), three exit contracts. Measured
    # basis: settled stops land a median 6.4 points deeper than their own
    # threshold and 87.4% of them land deeper, while trailing and max-hold exits
    # are the only positive exit families. -0.90 is only a catastrophe backstop.
    'alpha149_no_price_stop_v1': dict(
        notional_usd=2.0, max_concurrent_positions=2,
        excess_return_vs_arm='alpha149_nominal_stop_control_v1',
        hard_stop_return=-.90, trailing_activate_return=.30, trailing_drawdown=.15,
        description='退出实验·不用价格止损：与对照臂完全同一入场，但-90%仅作灾难兜底，'
                    '实际退出只走追踪(+30%激活/回撤15%)、最长持有30分钟与流动性/写销规则；'
                    '用于检验"价格止损本身是否在制造亏损"（实测止损单笔中位比阈值深6.4个点）。'),
    'alpha149_precomp_stop_v1': dict(
        notional_usd=2.0, max_concurrent_positions=2,
        excess_return_vs_arm='alpha149_nominal_stop_control_v1',
        hard_stop_return=-.136, trailing_activate_return=.30, trailing_drawdown=.15,
        description='退出实验·预补偿止损：入场同上，但止损线前移到-13.6%，'
                    '使实测中位结算深度（阈值+6.4个点）落在原本想要的-20%附近。'),
    'alpha149_nominal_stop_control_v1': dict(
        notional_usd=2.0, max_concurrent_positions=2,
        excess_return_vs_arm='alpha149_no_price_stop_v1',
        hard_stop_return=-.20, trailing_activate_return=.30, trailing_drawdown=.15,
        description='退出实验·名义止损对照：入场同上，保持系统默认-20%止损与追踪30/15、持有30分钟，'
                    '作为另两条退出合同的同入场基准。'),
    # ---- wave 16: stop scheduling --------------------------------------------
    'alpha149_early_stop_only_v1': dict(
        notional_usd=2.0, max_concurrent_positions=2,
        excess_return_vs_arm='alpha149_nominal_stop_control_v1',
        trajectory_exit='alpha149_early_stop_only',
        hard_stop_return=-.90, trailing_activate_return=.30, trailing_drawdown=.15,
        description='退出实验·仅前5分钟价格止损：与wave15对照臂完全同一入场与追踪合同，'
                    '但价格止损只在入场后头5分钟内以-20%触发，之后不再用价格止损，'
                    '由追踪(+30%→15%)、最长持有30分钟与流动性规则退出。'
                    '依据：实测止损越深幅度随持仓时间增长（<1分钟中位-5.05点 vs 5-30分钟-10.82点）。'),
    'alpha149_time_decay_stop_v1': dict(
        notional_usd=2.0, max_concurrent_positions=2,
        excess_return_vs_arm='alpha149_nominal_stop_control_v1',
        trajectory_exit='alpha149_time_decay_stop',
        hard_stop_return=-.90, trailing_activate_return=.30, trailing_drawdown=.15,
        description='退出实验·止损随时间收紧：同一入场与追踪合同，允许回撤从入场时的30%'
                    '按每分钟0.6个点线性收紧到下限12%（30分钟≈12%）；'
                    '用于检验"晚发生的止损应当更早触发"是否符合实测越深分布。'),
    # ---- wave 17: safest band + no loss-dominant stop --------------------------
    'alpha149_mid_band_nodeadstop_v1': dict(
        notional_usd=2.0, max_concurrent_positions=2,
        excess_return_vs_arm='alpha149_mid_band_control_v1',
        trajectory_exit='alpha149_depth_decay',
        hard_stop_return=-.90, trailing_activate_return=.30, trailing_drawdown=.15,
        description='安全带中段·不用价格止损：入场限定 FDV/深度 5-20（实测写销最低，'
                    '且排除了越深中位-65点的>20断崖档）、池龄30-180分钟、深度≥10000U、价涨、买盘≥55%；'
                    '退出以深度衰减早退+追踪(+30%→15%)+最长持有60分钟为主，-90%仅灾难兜底。'
                    '依据：修复后队列中硬止损39笔占全部净亏损（-31.1U/247笔），而追踪退出31笔+1.04U/笔。'),
    'alpha149_mid_band_control_v1': dict(
        notional_usd=2.0, max_concurrent_positions=2,
        excess_return_vs_arm='alpha149_mid_band_nodeadstop_v1',
        hard_stop_return=-.20, trailing_activate_return=.30, trailing_drawdown=.15,
        description='安全带中段·原止损对照：与上一条完全同一入场，保留系统默认-20%止损，'
                    '用于把"换池子"与"去掉价格止损"两个效应分开。'),
}


def _num(value):
    if value is None or isinstance(value, bool):
        return None
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None
    return value if value == value and value not in (float('inf'), float('-inf')) else None


def _w30(f):
    windows = f.get('windows') or {}
    feature = windows.get('30') if isinstance(windows, dict) else None
    return feature if isinstance(feature, dict) else None


def mechanisms(f):
    """Return {kind: bool} for the ALPHA149 mechanisms only.

    A missing 30-minute... (30-second) window, a missing price or a pool below
    the shared 1000U depth floor yields all-False; nothing is inferred.
    """
    out = {kind: False for kind in KINDS}

    def _finish(result):
        """Wave 8 merged entry: an OR of already-frozen member mechanisms.

        Applied on every return path so the two-frame members stay visible even
        when the 30-second window is absent. No new threshold is introduced here,
        and each member flag stays individually recorded for attribution.
        """
        result['merged_multi_setup'] = bool(
            result['df_price_up_liquidity_up'] or result['df_activity_jump']
            or result['sf_extreme_buy_pressure'] or result['goldendog_early_impulse']
            or result['dense_watch_breakout'])
        # Wave 11 consolidation: the merged multi-setup entry AND the measured
        # survivable band. Both members stay individually recorded, so the
        # attribution of this arm is the intersection, not a new threshold.
        result['merged_survivable'] = bool(
            result['merged_multi_setup'] and result['survivable_core'])
        # Wave 12: breadth intersections. The regime flag is computed before every
        # return path so the intersections are always evaluable.
        result['merged_regime'] = bool(
            result['merged_multi_setup'] and result['regime_risk_on'])
        result['survivable_regime'] = bool(
            result['survivable_core'] and result['regime_risk_on'])
        # Wave 13: confirm before buying. Live forward data shows the control arms
        # taking hard stops 23s and 25s after entry, i.e. the single-frame entry
        # buys into a dip and pays the noise. This intersection demands that the
        # pool has ALREADY risen for two consecutive observed frames inside the
        # measured survivable band, which delays the fill by one frame by
        # construction - no new threshold, no look-ahead.
        result['confirmed_survivable'] = bool(
            result['survivable_core'] and result['seq_two_step_rise'])
        return result

    if not isinstance(f, dict):
        return out
    w = _w30(f)
    frame = f.get('current') if isinstance(f.get('current'), dict) else {}
    # `dex_trajectory.derive` publishes the current pool depth under `current`
    # and never sets a top-level `liquidity_usd`. Reading only the top-level key
    # left every depth-guarded mechanism permanently False in the live engine
    # (and made `inv_contraction` raise), so both shapes are accepted here; the
    # current frame is the causal value and matters is never inferred.
    liquidity = _num(f.get('liquidity_usd'))
    if liquidity is None:
        liquidity = _num(frame.get('liquidity_usd'))
    pool_age = _num(f.get('pool_age_seconds'))
    buy_share = _num(f.get('buy_count_share'))
    vol_age_acc = _num(f.get('volume_acceleration_age_normalized'))
    tx_age_acc = _num(f.get('tx_acceleration_age_normalized'))
    drawdown = _num(f.get('drawdown'))
    plateau = _num(f.get('plateau_fraction'))
    monotonic = _num(f.get('monotonic_up_fraction'))
    jitter_interval = _num(f.get('jump_interval_cv'))
    jitter_size = _num(f.get('jump_size_cv'))
    retention = _num(f.get('liquidity_retention'))
    r2 = _num(f.get('log_price_r2'))
    residual = _num(f.get('residual_dispersion'))
    turn = _num(f.get('volume_liquidity'))
    fdv_liq = _num(f.get('fdv_liquidity'))
    total_frames = _num(f.get('frames')) or 0

    # ---- wave 4: single-frame / two-frame mechanisms -----------------------
    # Deliberately evaluated BEFORE the 30-second-window guard: measured data
    # supplies p50 = 1 frame per pool and no window ever forms, so a mechanism
    # that needs the window can never fire. These read only the current frame
    # (plus the immediately preceding frame of the same pool when available).
    current = f.get('current') if isinstance(f.get('current'), dict) else {}
    price_now = _num(current.get('price_usd'))
    liq_now = _num(current.get('liquidity_usd'))
    vol_now = _num(current.get('volume_5m_usd'))
    if liquidity is not None and liquidity >= 1000 and price_now:
        out['sf_deep_low_fdv'] = bool(
            liquidity >= 5000 and fdv_liq is not None and fdv_liq <= .7
            and buy_share is not None and buy_share >= .58)
        out['sf_extreme_buy_pressure'] = bool(
            buy_share is not None and buy_share >= .9 and liquidity >= 2000
            and turn is not None and turn > .1)
        out['sf_young_turnover'] = bool(
            pool_age is not None and pool_age <= 900 and liquidity >= 1500
            and turn is not None and turn >= .3)
        out['sf_quiet_absorption'] = bool(
            drawdown is not None and drawdown >= 0
            and buy_share is not None and buy_share >= .65
            and liquidity >= 3000 and fdv_liq is not None and fdv_liq <= 1.2)
        # wave 5: golden-dog slow-out quadrant (young, deep, low FDV/depth).
        out['sf_goldendog_deep_base'] = bool(
            pool_age is not None and pool_age <= 900 and liquidity >= 8000
            and fdv_liq is not None and fdv_liq <= .8
            and buy_share is not None and buy_share >= .55
            and drawdown is not None and drawdown >= 0)
        # wave 6: calibrated on the measured golden-dog profile (n=37 cases vs
        # 132 controls: cases reach >=5x 24x more often, first-frame depth
        # p50 ~19.4k, local frames p50 74 vs 6). High recall by design.
        out['righttail_lottery'] = bool(
            liquidity >= 10000 and pool_age is not None and pool_age <= 3600
            and buy_share is not None and buy_share >= .5
            and drawdown is not None and drawdown >= 0)
        out['goldendog_liquidity_band'] = bool(
            liquidity >= 10000 and liquidity <= 100000
            and pool_age is not None and pool_age <= 7200
            and buy_share is not None and buy_share >= .55
            and fdv_liq is not None and fdv_liq <= 2)
        # The strongest measured discriminator (frames per pool) is evaluated
        # with the two-frame block below, where `previous` is available.
    previous = f.get('prev') if isinstance(f.get('prev'), dict) else None
    if previous:
        prev_price = _num(previous.get('price_usd'))
        prev_liq = _num(previous.get('liquidity_usd'))
        prev_vol = _num(previous.get('volume_5m_usd'))
        out['df_price_up_liquidity_up'] = bool(
            price_now and prev_price and price_now > prev_price
            and liq_now is not None and prev_liq is not None and liq_now > prev_liq)
        out['df_activity_jump'] = bool(
            price_now and prev_price and price_now >= prev_price
            and vol_now is not None and prev_vol is not None and prev_vol > 0
            and vol_now >= prev_vol * 1.5
            and buy_share is not None and buy_share >= .5)
        # wave 9: reclaim after a real washout. The pool must already be off its
        # episode high (measured drawdown p10 = -28.3%, p50 = -0.08%), must be
        # reclaiming on the current frame, and depth must not be leaving - the
        # measured population that recovered above our own exits (81.8%).
        out['washout_reclaim'] = bool(
            drawdown is not None and drawdown <= -.12
            and price_now and prev_price and price_now > prev_price
            and liq_now is not None and prev_liq is not None and liq_now >= prev_liq * .98
            and liquidity is not None and liquidity >= 2000
            and buy_share is not None and buy_share >= .5
            and total_frames >= 4)
        # wave 10: measured survivable cells. Write-off rate by entry FDV/depth
        # is 44.1% (<1), 12.8% (1-2), 6.0% (2-5), 1.9% (5-20), 4.1% (>20); pool
        # age adds: 22-23% below 30 minutes versus 1.5% at 30-180 minutes, and
        # the FDV/depth<1 x 5-30 minute cell reaches 54.0% (avg -6.51U).
        survivable_age = (
            pool_age is not None and 1800 <= pool_age <= 10800)
        survivable_depth = (
            fdv_liq is not None and 1.0 <= fdv_liq <= 20.0)
        out['survivable_core'] = bool(
            survivable_age and survivable_depth
            and liquidity is not None and liquidity >= 5000
            and price_now and prev_price and price_now > prev_price
            and liq_now is not None and prev_liq is not None and liq_now >= prev_liq * .98
            and buy_share is not None and buy_share >= .5)
        out['survivable_band_deep'] = bool(
            survivable_age
            and fdv_liq is not None and fdv_liq >= 5.0
            and liquidity is not None and liquidity >= 10000
            and price_now and prev_price and price_now > prev_price
            and liq_now is not None and prev_liq is not None and liq_now >= prev_liq * .98
            and buy_share is not None and buy_share >= .55)
        # wave 17: the measured safest sub-band. FDV/depth 5-20 has the lowest
        # write-off rate (1.9% overall, 2.0% in the newer half), while the far
        # side of it is a cliff: FDV/depth > 20 shows a median stop overshoot of
        # -65 points against -5 to -10 elsewhere, and depth > 200k the same. This
        # mechanism therefore keeps the upper bound that `survivable_band_deep`
        # deliberately does not have, so the cliff tier is excluded by design.
        out['survivable_band_mid'] = bool(
            survivable_age
            and fdv_liq is not None and 5.0 <= fdv_liq <= 20.0
            and liquidity is not None and liquidity >= 10000
            and price_now and prev_price and price_now > prev_price
            and liq_now is not None and prev_liq is not None and liq_now >= prev_liq * .98
            and buy_share is not None and buy_share >= .55)
        # wave 14: re-expression of the system's highest-PnL entry mechanism
        # (`resource_age_rate`, parent of resource_age_rate_candidate_v1 at
        # +634.96U over 220 positions) on the shared vector. The original compares
        # the current 5 minutes against the prior 55 minutes and scales by
        # available age; the shared vector already publishes that comparison
        # age-normalised, so the frozen rule is a 3x acceleration on the stronger
        # of the two rates, inside a 15-minute to 6-hour pool, with real activity.
        # It needs no previous frame and no window, so it is evaluated below
        # before both guards.
        # wave 5: mature-pool two-frame rise (slow-in x fast-out quadrant).
        out['df_mature_price_up'] = bool(
            pool_age is not None and pool_age >= 1800
            and price_now and prev_price and price_now > prev_price
            and liq_now is not None and prev_liq is not None and liq_now >= prev_liq)
        # wave 6: the strongest measured discriminator is how densely the pool is
        # observed locally (cases p50 = 74 frames vs controls p50 = 6).
        out['dense_watch_breakout'] = bool(
            (_num(f.get('pair_frames')) or 0) >= 8
            and price_now and prev_price and price_now > prev_price
            and liq_now is not None and prev_liq is not None and liq_now >= prev_liq)
        # wave 7: sequence mechanisms, possible now that pools carry ~44 frames.
        # Inventory contraction while price holds: supply squeezing, not dumping.
        out['inv_contraction'] = bool(
            liquidity is not None and liquidity >= 5000
            and liq_now is not None and prev_liq is not None
            and liq_now < prev_liq and price_now and prev_price and price_now >= prev_price
            and buy_share is not None and buy_share >= .5)
        before = f.get('prev2') if isinstance(f.get('prev2'), dict) else None
        if before:
            earlier_price = _num(before.get('price_usd'))
            earlier_liq = _num(before.get('liquidity_usd'))
            # Price moves first, depth follows: earlier step flat or down, latest
            # step adds depth with price still rising.
            out['seq_price_then_depth'] = bool(
                earlier_price and prev_price and price_now
                and prev_price >= earlier_price and price_now > prev_price
                and earlier_liq is not None and prev_liq is not None and liq_now is not None
                and prev_liq <= earlier_liq * 1.02 and liq_now > prev_liq)
            # Two consecutive rising steps: sustained rather than a single spike.
            out['seq_two_step_rise'] = bool(
                earlier_price and prev_price and price_now
                and prev_price > earlier_price and price_now > prev_price
                and liquidity is not None and liquidity >= 3000)
            # wave 8: the last empty quadrant - slow entry AND slow exit.
            out['mature_two_step_slow'] = bool(
                pool_age is not None and pool_age >= 1800
                and earlier_price and prev_price and price_now
                and prev_price > earlier_price and price_now > prev_price
                and liquidity is not None and liquidity >= 5000
                and buy_share is not None and buy_share >= .5)

    # Wave 14: the highest-PnL entry mechanism of the system, rebuilt on the
    # shared vector. `resource_age_rate` (parent of resource_age_rate_candidate_v1,
    # +634.96U over 220 positions) compares the current 5 minutes against the
    # PRIOR 55 minutes: old_rate = (m5/5) / (prior55/55) with
    # prior55 = hour - m5, and fires at old_rate >= 3.
    #
    # The shared vector does not publish the prior window, but it does publish the
    # same comparison against the whole hour (m5 x 12 / hour). Since
    # hour = m5 + prior55, that ratio a = 12*m5/hour implies
    # prior55 = m5*(12/a - 1), hence old_rate = 11*a/(12 - a): the parent's
    # frozen 3x threshold is exactly a >= 36/14 = 2.5714. A ratio a >= 12 means the
    # hour no longer contains the 5 minutes (negative prior window), which the
    # parent rejects as "no comparable positive baseline", so it is excluded
    # rather than treated as infinite.
    age_rate_candidates = []
    for ratio_5m_1h in (_num(f.get('volume_acceleration_5m_1h')),
                        _num(f.get('tx_acceleration_5m_1h'))):
        if ratio_5m_1h is None or ratio_5m_1h <= 0 or ratio_5m_1h >= 12.0:
            continue
        age_rate_candidates.append(11.0 * ratio_5m_1h / (12.0 - ratio_5m_1h))
    old_rate = max(age_rate_candidates) if age_rate_candidates else None
    out['age_rate_acceleration'] = bool(
        pool_age is not None and 900 < pool_age < 21600
        and liquidity is not None and liquidity >= 5000
        and old_rate is not None and old_rate >= AGE_RATE_MIN
        and ((vol_now is not None and vol_now >= 1000)
             or (turn is not None and turn >= .1))
        and buy_share is not None and buy_share >= .5)

    # Wave 12: breadth-based regime throttle. Computed before every return path
    # (including the missing-window one) so the intersections in `_finish` are
    # always evaluable, and False whenever the engine has not supplied a regime.
    regime = f.get('regime') if isinstance(f.get('regime'), dict) else None
    regime_ratio = _num(regime.get('ratio')) if regime else None
    regime_fast = _num(regime.get('fast')) if regime else None
    out['regime_risk_on'] = bool(
        regime_ratio is not None and regime_ratio >= REGIME_RATIO_MIN
        and regime_fast is not None and regime_fast >= REGIME_FAST_MIN)

    if not w:
        return _finish(out)
    ret = _num(w.get('return_fraction'))
    acc = _num(w.get('acceleration'))
    liq_change = _num(w.get('liquidity_change_fraction'))
    vol_ratio = _num(w.get('rolling_volume_change_ratio'))
    tx_ratio = _num(w.get('rolling_tx_change_ratio'))
    frames = _num(w.get('frames')) or 0
    volatility = _num(w.get('realized_volatility'))
    if liquidity is None or liquidity < 1000 or ret is None:
        return _finish(out)
    rising = (vol_ratio or 0) > 1 and (tx_ratio or 0) > 1
    stable = liq_change is not None and liq_change >= 0

    # 1. Earliest eligible frame of a pool; no peer/percentile requirement.
    out['uncrowded_first_frame'] = bool(
        total_frames <= 5 and ret > 0 and stable and frames >= 3)

    # 2. Activity acceleration normalised by real pool age (avoids the
    #    volume_5m/volume_1h identity for pools younger than 300s).
    out['age_normalized_ignition'] = bool(
        ret > FRICTION / 2 and vol_age_acc is not None and tx_age_acc is not None
        and vol_age_acc > 1 and tx_age_acc > 1 and stable)

    # 3. Depth (liquidity) expands before price reflects it.
    out['liquidity_expansion_lead'] = bool(
        liq_change is not None and liq_change > FRICTION and ret <= FRICTION / 2
        and buy_share is not None and buy_share > .5)

    # 4. Long platform then the first genuine expansion.
    out['plateau_ignition'] = bool(
        ret > 0 and plateau is not None and plateau >= .5
        and volatility is not None and volatility <= FRICTION and rising)

    # 5. Regular step-shaped ramp: monotone staircase with even jump spacing.
    out['step_pump_fast'] = bool(
        monotonic is not None and monotonic >= .7 and jitter_interval is not None
        and jitter_interval <= .8 and jitter_size is not None and jitter_size <= 1.0
        and retention is not None and retention >= 1 - FRICTION
        and pool_age is not None and pool_age <= 3600 and stable)

    # 6. Extreme buy-count share with age-normalised activity acceleration.
    out['buy_share_extreme'] = bool(
        buy_share is not None and buy_share > .75 and stable
        and ((tx_age_acc is not None and tx_age_acc > 1) or rising))

    # 7. Liquidity was ADDED through the first dip, and recovery was faster
    #    than the decline with rising activity.
    dip = f.get('first_dip') if isinstance(f.get('first_dip'), dict) else None
    if dip:
        dip_retention = _num(dip.get('liquidity_retention'))
        dip_volume = _num(dip.get('volume_ratio'))
        recovery = _num(dip.get('recovery_seconds'))
        decline = _num(dip.get('decline_seconds'))
        out['liquidity_add_dip_recovery'] = bool(
            dip_retention is not None and dip_retention > 1.0
            and recovery is not None and decline is not None and recovery <= decline
            and dip_volume is not None and dip_volume >= 1.2 and ret > 0)

    # 8. Continuity rebuilt after an observation gap; first段 must still rise.
    continuity_started = f.get('continuity_started_at')
    observed_at = f.get('observed_at')
    if continuity_started and observed_at:
        try:
            rebuilt = (_parse_time(observed_at) - _parse_time(continuity_started)).total_seconds()
        except (ValueError, TypeError):
            rebuilt = None
        out['gap_repair_continuation'] = bool(
            rebuilt is not None and rebuilt <= 90 and ret > 0
            and drawdown is not None and drawdown > -FRICTION)

    # 9. Only enter when the 30s displacement covers several round trips and the
    #    pool is deep enough to exit into.
    out['friction_multiple_escape'] = bool(
        ret >= 3 * FRICTION and liquidity >= 3000
        and turn is not None and turn > 1
        and drawdown is not None and drawdown > -FRICTION)

    # 10. Multi-frame smooth trend: more independent frames, high log-price R²,
    #     small residual dispersion.
    out['multiframe_trend_confirm'] = bool(
        frames >= 5 and r2 is not None and r2 >= .8 and residual is not None
        and residual <= FRICTION / 2 and ret > FRICTION and stable)

    # 11. Very short organic burst: only the trailing 15 seconds of real,
    #     continuous, independent frames.
    windows = f.get('windows') if isinstance(f.get('windows'), dict) else {}
    w15 = windows.get('15') if isinstance(windows.get('15'), dict) else None
    w60 = windows.get('60') if isinstance(windows.get('60'), dict) else None
    w180 = windows.get('180') if isinstance(windows.get('180'), dict) else None
    # Window-derived locals are bound once, to None when that window never
    # formed: a mechanism may only fire on genuinely observed evidence, never on
    # an unbound local and never on a substituted zero.
    r15 = _num(w15.get('return_fraction')) if w15 else None
    r60 = _num(w60.get('return_fraction')) if w60 else None
    r180 = _num(w180.get('return_fraction')) if w180 else None
    v30 = _num(w.get('log_velocity'))
    if w15:
        short_ret = _num(w15.get('return_fraction'))
        short_tx = _num(w15.get('rolling_tx_change_ratio'))
        short_frames = _num(w15.get('frames')) or 0
        out['organic_short_burst'] = bool(
            short_frames >= 3 and short_ret is not None and short_ret > FRICTION / 2
            and buy_share is not None and buy_share > .5
            and (short_tx is None or short_tx > 1))

    # 12. Structures that historically avoid write-offs: deep pool and a low
    #     FDV-to-depth ratio (not a thin pool priced far above its liquidity).
    fdv_liq = _num(f.get('fdv_liquidity'))
    out['writeoff_structure_avoid'] = bool(
        liquidity >= 5000 and fdv_liq is not None and fdv_liq <= 500
        and ret > 0 and stable)

    # 13. A mature pool (>=6h) receiving a genuine, age-normalised new wave.
    out['mature_revival'] = bool(
        pool_age is not None and pool_age >= 21600 and ret > FRICTION and stable
        and vol_age_acc is not None and vol_age_acc > 1)

    # 14. Turnover surge while price is still inside half a friction unit.
    out['turnover_surge'] = bool(
        turn is not None and turn > 2 and abs(ret) <= FRICTION / 2 and rising)

    # 15. Agreement across 15s/30s/60s with short-horizon acceleration above the
    #     long-horizon velocity.
    w60 = windows.get('60') if isinstance(windows.get('60'), dict) else None
    if w15 and w60:
        v60 = _num(w60.get('log_velocity'))
        out['multi_horizon_agreement'] = bool(
            r15 is not None and r60 is not None and r15 > 0 and r60 > 0 and ret > 0
            and v30 is not None and v60 is not None and v30 > v60 and stable)

    # 16. Impulse that never gives ground: shallowest observed drawdown.
    out['shallow_drawdown_impulse'] = bool(
        ret > FRICTION and drawdown is not None and drawdown > -FRICTION / 4
        and stable and frames >= 3)

    # 17. Thin-pool elasticity anomaly: a small notional moves price a lot.
    elasticity = _num(f.get('price_elasticity_proxy'))
    out['elasticity_anomaly_fast'] = bool(
        elasticity is not None and elasticity >= 10 and liquidity < 20000
        and ret > FRICTION and buy_share is not None and buy_share > .5)

    # 18. Volatility squeeze then release: long window compressed, short window
    #     expanding, price up.
    w180 = windows.get('180') if isinstance(windows.get('180'), dict) else None
    if w15 and w180:
        v_short = _num(w15.get('realized_volatility'))
        v_long = _num(w180.get('realized_volatility'))
        out['squeeze_release'] = bool(
            v_short is not None and v_long is not None and v_long <= FRICTION
            and v_short > v_long and ret > 0 and stable)

    # 19. Smooth natural trend: low plateau share, high monotonicity, decent fit.
    out['smooth_organic_trend'] = bool(
        plateau is not None and plateau <= .2 and monotonic is not None
        and monotonic >= .6 and r2 is not None and r2 >= .6
        and residual is not None and residual <= FRICTION and ret > 0 and stable)

    # ---- wave 3: alternatives for the measured blockers -------------------
    # 20. Golden-dog early profile: young pool, strong early impulse, shallow
    #     drawdown, real depth. Right-tail retention is the exit contract.
    out['goldendog_early_impulse'] = bool(
        pool_age is not None and pool_age <= 600 and ret >= 2 * FRICTION
        and buy_share is not None and buy_share > .55 and liquidity >= 2000
        and drawdown is not None and drawdown > -FRICTION and stable)

    # 21. Golden-dog multi-scale acceleration with shallow drawdown.
    if w15 and w60:
        v15s = _num(w15.get('log_velocity'))
        v60s = _num(w60.get('log_velocity'))
        out['goldendog_shallow_stack'] = bool(
            v15s is not None and v30 is not None and v60s is not None
            and v15s > v30 > v60s > 0 and ret > 0
            and drawdown is not None and drawdown > -FRICTION / 2
            and retention is not None and retention >= 1.0)

    # 22. Golden-dog second leg: first leg up, shallow consolidation, then
    #     re-acceleration inside the same observed episode.
    if w15 and w60 and w180:
        r60 = _num(w60.get('return_fraction'))
        r180 = _num(w180.get('return_fraction'))
        v15s = _num(w15.get('log_velocity'))
        out['goldendog_second_leg'] = bool(
            r180 is not None and r180 >= 2 * FRICTION
            and r60 is not None and r60 <= FRICTION
            and v15s is not None and v15s > 0 and r15 is not None and r15 > 0)

    # 23. Very young pool fast lane: earliest possible signal so the next
    #     distinct frame arrives sooner (effective entry acceleration).
    out['young_fast_lane'] = bool(
        pool_age is not None and pool_age <= 120 and liquidity >= 1500
        and w15 is not None and (_num(w15.get('frames')) or 0) >= 3
        and r15 is not None and r15 > 0)

    # 24. Minimal-frame quick entry: two independent frames are enough.
    out['two_frame_quick_entry'] = bool(
        liquidity >= 2000 and w15 is not None
        and (_num(w15.get('frames')) or 0) >= 2
        and r15 is not None and r15 > FRICTION / 2 and stable)

    # 25. Live replacement path for the dormant flow families (no dependency on
    #     retired collectors or on cross-sectional consensus).
    out['live_flow_revival'] = bool(
        rising and buy_share is not None and buy_share > .6 and stable and ret > 0)

    # 26. Baseline-free absolute conditions (no comparable-baseline waiting).
    out['baseline_free_absolute'] = bool(
        ret >= FRICTION and turn is not None and turn > 1 and liquidity >= 3000)

    # 27. Depth-first mature pool: no pool-age ceiling, depth decides.
    out['depth_first_mature'] = bool(
        pool_age is not None and pool_age >= 1800 and liquidity >= 10000
        and ret > 0 and turn is not None and turn > .5)

    # 28. Merged multi-setup entry (wave 8) is applied by `_finish` on every
    #     return path, so the two-frame members remain visible without a window.
    return _finish(out)


def exit_reason(kind, f, opened_at, current):
    """ALPHA149 trajectory exits. Same causal guards as the shared family."""
    if kind not in EXIT_KINDS or not f:
        return None
    try:
        if not (_parse_time(opened_at) < _parse_time(f['observed_at'])
                <= _parse_time(f['recorded_at']) <= current):
            return None
        if (current - _parse_time(f['observed_at'])).total_seconds() > 15:
            return None
        w = _w30(f)
        if not w or _parse_time(w.get('start_at')) < _parse_time(opened_at):
            return None
    except (KeyError, ValueError, TypeError):
        return None
    velocity = _num(w.get('log_velocity'))
    acceleration = _num(w.get('acceleration'))
    vol_ratio = _num(w.get('rolling_volume_change_ratio'))
    tx_ratio = _num(w.get('rolling_tx_change_ratio'))
    liq_change = _num(w.get('liquidity_change_fraction'))
    plateau = _num(f.get('plateau_fraction'))
    if kind == 'alpha149_profit_decay':
        if (velocity is not None and velocity < 0 and acceleration is not None
                and acceleration < 0 and vol_ratio is not None and vol_ratio < 1):
            return 'alpha149_profit_velocity_decay'
    elif kind == 'alpha149_liquidity_shock':
        if liq_change is not None and liq_change <= -2 * FRICTION:
            return 'alpha149_liquidity_shock_withdrawal'
    elif kind == 'alpha149_plateau_stall':
        if (plateau is not None and plateau >= .5 and tx_ratio is not None
                and tx_ratio < 1 and velocity is not None and velocity <= 0):
            return 'alpha149_plateau_stall'
    elif kind == 'alpha149_peak_giveback':
        drawdown = _num(f.get('drawdown'))
        if drawdown is not None and drawdown <= -.25:
            return 'alpha149_peak_giveback'
    elif kind == 'alpha149_flat_dead':
        if (plateau is not None and plateau >= .5 and tx_ratio is not None
                and tx_ratio < .5 and velocity is not None and velocity <= 0):
            return 'alpha149_flat_dead'
    elif kind == 'alpha149_righttail_wide':
        drawdown = _num(f.get('drawdown'))
        if drawdown is not None and drawdown <= -.35:
            return 'alpha149_righttail_wide_giveback'
        if liq_change is not None and liq_change <= -2 * FRICTION:
            return 'alpha149_righttail_liquidity_withdrawal'
    elif kind == 'alpha149_momentum_floor':
        turn = _num(f.get('volume_liquidity'))
        if (velocity is not None and velocity < 0 and acceleration is not None
                and acceleration < 0 and turn is not None and turn < 1):
            return 'alpha149_momentum_floor'
    elif kind == 'alpha149_vol_scaled_stop':
        # Volatility-scaled stop: the allowed drawdown grows with the pool's own
        # measured 30s realized volatility, bounded so it can never become an
        # unlimited hold. Calibration (600 live samples): volatility_30 p50 =
        # 3.7%, p90 = 18.9%, while the shared fixed stop is -20%; the floor keeps
        # a -22% backstop and the cap refuses to hold beyond -50%.
        drawdown = _num(f.get('drawdown'))
        sigma = _num(w.get('realized_volatility'))
        if sigma is None or drawdown is None:
            return None
        limit = max(VOL_STOP_FLOOR, min(VOL_STOP_CAP, VOL_STOP_MULTIPLE * sigma))
        if drawdown <= -limit:
            return 'alpha149_vol_scaled_stop'
    elif kind == 'alpha149_depth_decay':
        # Leave a dying pool before it breaches the write-off floor. Measured:
        # write-off positions lose -12.94U on average at the floor, so an earlier
        # exit is worth testing against a same-entry control. Both conditions are
        # required: depth leaving the pool AND activity already dead.
        turn = _num(f.get('volume_liquidity'))
        retention = _num(f.get('liquidity_retention'))
        if (liq_change is not None and liq_change <= -.15
                and turn is not None and turn < .1
                and retention is not None and retention <= .8):
            return 'alpha149_depth_decay_exit'
    elif kind == 'alpha149_early_stop_only':
        # Wave 16: the measured overshoot grows with holding time (p50 -5.05
        # points inside one minute versus -10.82 at 5-30 minutes), so a price stop
        # is only armed during the first minutes; afterwards the position is left
        # to trailing, the horizon and the liquidity rules.
        drawdown = _num(f.get('drawdown'))
        elapsed_minutes = (current - _parse_time(opened_at)).total_seconds() / 60.0
        if (drawdown is not None and elapsed_minutes <= EARLY_STOP_MINUTES
                and drawdown <= -EARLY_STOP_DISTANCE):
            return 'alpha149_early_stop_only'
    elif kind == 'alpha149_time_decay_stop':
        # Wave 16: the allowed drawdown shrinks as the hold extends, capped and
        # floored so it can never become an unlimited hold or an instant stop.
        drawdown = _num(f.get('drawdown'))
        if drawdown is not None:
            elapsed_minutes = (current - _parse_time(opened_at)).total_seconds() / 60.0
            limit = max(TIME_DECAY_FLOOR,
                        min(TIME_DECAY_CAP,
                            TIME_DECAY_CAP - TIME_DECAY_SLOPE_PER_MINUTE * elapsed_minutes))
            if drawdown <= -limit:
                return 'alpha149_time_decay_stop'
    return None


RULES = {
    'common': '独立观察间隔≤30秒；原池流动性≥1000U；严格后帧成交；共同安全门；缺失不补零。',
    'uncrowded_first_frame': '该池在本引擎内累计帧数≤5即视为最早机会；不要求同龄同伴存在。',
    'age_normalized_ignition': '30秒涨幅>半个摩擦，且成交额与笔数按真实池龄归一的加速均>1（避开池龄<300秒时m5/h1恒等于1的陷阱）。',
    'liquidity_expansion_lead': '30秒原池深度扩张超过一个摩擦，而价格位移仍在半个摩擦内，买笔占比过半。',
    'plateau_ignition': '此前平台占比≥50%且窗口波动≤一个摩擦，随后出现>0的上涨与成交额/笔数双增。',
    'step_pump_fast': '单调上行步占比≥70%，跳涨间隔与幅度变异系数均≤1.0，流动性保持；1U单仓5分钟绝对上限。',
    'buy_share_extreme': '买笔占比>75%，且按龄归一笔数加速>1或成交额与笔数双增，流动性不降。',
    'liquidity_add_dip_recovery': '首个回撤期间流动性不降反增（>1.0倍），恢复快于下跌且恢复期成交额≥1.2倍。',
    'gap_repair_continuation': '观察断流后连续性重建≤90秒内的首个上涨段；5分钟期限。',
    'friction_multiple_escape': '30秒位移≥3倍往返摩擦且原池深度≥3000U、周转率>1；以可回收空间为前提。',
    'multiframe_trend_confirm': '30秒窗口≥5个独立帧、对数价格R²≥0.8、残差离散度≤半个摩擦。',
    'organic_short_burst': '15秒内≥3个独立帧、涨幅>半个摩擦、买笔占比过半、笔数不降。',
    'writeoff_structure_avoid': '原池深度≥5000U且FDV/流动性≤500，再看30秒上涨与流动性不降。',
    'mature_revival': '池龄≥6小时且按龄归一成交额加速>1、30秒涨幅超过一个摩擦。',
    'turnover_surge': '成交额/流动性周转率>2而价格仍在半个摩擦内，成交额与笔数双增。',
    'multi_horizon_agreement': '15/30/60秒收益同为正，且30秒速度高于60秒速度。',
    'shallow_drawdown_impulse': '30秒涨幅超过一个摩擦且全程回撤浅于四分之一摩擦。',
    'elasticity_anomaly_fast': '薄池（<20k）中弹性代理≥10且买笔占比过半；1U单仓5分钟。',
    'squeeze_release': '180秒窗口波动≤一个摩擦，而15秒波动放大且价格上涨。',
    'smooth_organic_trend': '平台占比≤20%、单调上行≥60%、R²≥0.6、残差≤一个摩擦。',
    # wave 3
    'goldendog_early_impulse': '池龄≤10分钟；30秒涨幅≥2倍摩擦；买笔占比>55%；原池深度≥2000U；回撤浅于一个摩擦；流动性不降。',
    'goldendog_shallow_stack': '15/30/60秒速度递增且均为正（多尺度加速）；回撤浅于半个摩擦；流动性保持≥1.0倍。',
    'goldendog_second_leg': '180秒累计涨幅≥2倍摩擦，随后60秒整理幅度≤1倍摩擦，当前15秒重新加速为正。',
    'young_fast_lane': '池龄≤120秒、深度≥1500U、15秒窗口≥3个独立帧且涨幅为正（让信号在极早期成立）。',
    'two_frame_quick_entry': '15秒窗口≥2个独立帧、涨幅>半个摩擦、深度≥2000U、流动性不降（最少帧入场）。',
    'live_flow_revival': '成交额与笔数双增、买笔占比>60%、流动性不降、涨幅为正（不依赖已休眠采集面）。',
    'baseline_free_absolute': '只用绝对量：30秒涨幅≥1倍摩擦、周转率>1、深度≥3000U（不等横截基线）。',
    'depth_first_mature': '池龄≥30分钟、深度≥10000U、30秒上涨、周转率>0.5（不设池龄上限）。',
    # wave 4: single/two-frame rules, calibrated on the measured distribution
    'sf_deep_low_fdv': '单帧即可：深度≥5000U 且 FDV/深度≤0.7、买笔占比≥0.58。',
    'sf_extreme_buy_pressure': '单帧即可：买笔占比≥0.9、深度≥2000U、换手>0.1。',
    'sf_young_turnover': '单帧即可：池龄≤900秒、换手≥0.3、深度≥1500U。',
    'sf_quiet_absorption': '单帧即可：价格处于运行高点、买笔占比≥0.65、深度≥3000U、FDV/深度≤1.2。',
    'df_price_up_liquidity_up': '仅用最近两帧：本帧价格高于上一帧且深度增加（不需要30秒窗口）。',
    'df_activity_jump': '仅用最近两帧：本帧成交额≥上一帧1.5倍、价格不跌、买笔占比≥0.5。',
    'df_mature_price_up': '仅用最近两帧：池龄≥30分钟的老池，本帧价涨且深度不降（慢进快出象限）。',
    'sf_goldendog_deep_base': '单帧即可：池龄≤15分钟、深度≥8000U、FDV/深度≤0.8、'
                              '买笔占比≥0.55、价格处于运行高点（金狗慢出象限）。',
    'righttail_lottery': '高召回右尾：深度≥10000U（实测金狗首帧中位≈19.4k）、池龄≤1小时、'
                         '买笔占比≥0.5、价格处于运行高点；1U小额、持有至180分钟、宽追踪。',
    'goldendog_liquidity_band': '金狗深度带：深度10000–100000U、池龄≤2小时、买笔占比≥0.55、'
                                'FDV/深度≤2；持有至120分钟。',
    'dense_watch_breakout': '观测密度（实测最强判别：金狗74帧 vs 对照6帧）：本池已有≥8帧，'
                            '且本帧价涨、深度不降。',
    'inv_contraction': '两帧：深度收缩但价格持稳（供给被抽走而非抛售），深度≥5000U、买笔≥0.5；'
                       '复活已暂停臂的库存收缩假设。',
    'seq_price_then_depth': '三帧序列：上一步价格已涨且深度未增，本步深度跟进且价格继续上行。',
    'seq_two_step_rise': '三帧序列：连续两步价格上行（持续而非单点尖峰），深度≥3000U。',
    'mature_two_step_slow': '慢进慢出象限：池龄≥30分钟的老池连续两步上行、深度≥5000U、买笔≥0.5；'
                            '持有至90分钟并用追踪退出。',
    # wave 8
    'merged_multi_setup': '合并入场：两帧价涨加池 / 两帧成交额跳增 / 单帧极端买压 / 金狗早期冲量 / '
                          '高密度观测突破，任一成立即入场（成员标记逐项保留，便于归因）。',
    # wave 9
    'washout_reclaim': '洗出后回收：本段回撤≥12%（实测 drawdown p10=-28.3%、p50=-0.08%）、'
                       '当前帧重新上行、深度不流失（≥前帧98%）、买盘占比≥50%、深度≥2000U、本池≥4帧。',
    'alpha149_vol_scaled_stop': '波动率自适应止损：允许回撤=4×本池30秒实现波动率，'
                                '下限22%、上限50%（实测波动率 p50=3.7%、p90=18.9%，固定-20%对高波动池仅约1σ）。',
    # wave 10
    'survivable_core': '存活带：池龄30-180分钟（实测写销22-23% <30分钟 vs 1.5% 30-180分钟）、'
                       'FDV/深度1-20（实测写销44.1% <1 vs 1.9% 5-20）、深度≥5000U、'
                       '当前帧价涨且深度≥前帧98%、买盘占比≥50%。',
    'survivable_band_deep': '存活带深池：池龄30-180分钟、FDV/深度≥5、深度≥10000U、'
                            '当前帧价涨且深度不流失、买盘占比≥55%。',
    'survivable_band_mid': '安全带中段：与深池带同条件但FDV/深度限定在5-20，'
                           '排除实测越深中位-65点的>20断崖档；写销率最低的实测区间。',
    'alpha149_depth_decay_exit': '深度衰减早退：30秒深度收缩≥15% 且换手<0.1 且深度保留≤0.8 时离场，'
                                 '目标是在跌破写销底线（平均-12.94U）之前退出。',
    # wave 11
    'merged_survivable': '合并×存活带：五形态合并（价涨加池/成交额跳增/极端买压/金狗早冲量/高密度突破）'
                         '与存活带（池龄30-180分钟、FDV/深度1-20、深度≥5000U、买盘≥50%、深度不流失）'
                         '必须同时成立。',
    # wave 12
    'regime_risk_on': '市场宽度改善节流：近40帧上涨占比≥全程占比×1.2 且 ≥15%'
                      '（实测横截面中位仅13.3%的池在上涨，故用相对改善而非绝对阈值）；'
                      '复活的假设来自已暂停的 market_regime_throttle_v1（+19.62U/9笔/0写销）。',
    'merged_regime': '合并×宽度改善：五形态合并 与 市场宽度改善 必须同时成立。',
    'survivable_regime': '存活带×宽度改善：存活带 与 市场宽度改善 必须同时成立。',
    # wave 13
    'confirmed_survivable': '存活带×连续两步确认：存活带成立且本池已连续两个观测帧上行'
                            '（成交因此推迟一帧，先确认再买入）；退出用实测最强短兑现合同。',
    # wave 14
    'age_rate_acceleration': '池龄归一化加速：池龄15分钟-6小时、深度≥5000U、'
                             '5分钟活动率≥自身按龄归一小时率的3倍（成交额/笔数取强者）、'
                             '有真实活动（5分钟成交额≥1000U或换手≥0.1）、买盘占比≥50%；'
                             '复刻系统收益最高入场机制 resource_age_rate。',
}


def adjust(policies):
    """Apply ALPHA149 identity, sizing and exit overrides; never touches other arms."""
    for policy in policies:
        arm = str(policy.get('arm_id') or '')
        if arm not in ALL_ARMS:
            continue
        kind, name, hold = SPECS.get(arm, ('uncrowded_first_frame', 'ALPHA149·' + arm, 15))
        policy['name'] = name
        policy['paired_opportunity_group'] = 'alpha149_v1'
        policy['feature_contract'] = VERSION
        policy['feature_hypothesis'] = kind
        policy['trajectory_engine'] = 'alpha149'
        policy.setdefault('trajectory_rules', dict(RULES))
        override = dict(OVERRIDES.get(arm) or {})
        max_concurrent = override.pop('max_concurrent_positions', None)
        if max_concurrent is not None:
            policy['entry_filter'] = {**(policy.get('entry_filter') or {}),
                                      'max_concurrent_positions': max_concurrent}
        policy.setdefault(
            'description',
            'ALPHA149新增前向实验（%s）；复用既有连续原池特征，缺失不补零、严格后帧、'
            '共同安全门；非已证Alpha。' % kind)
        policy.update(override)
    return policies


def policies(base):
    """Standalone policy list (used by tests); runtime merges via dex_trajectory."""
    result = []
    for arm in ALL_ARMS:
        kind, name, hold = SPECS.get(arm, ('uncrowded_first_frame', 'ALPHA149·' + arm, 15))
        policy = deepcopy(base)
        policy.update(
            arm_id=arm, canonical_id=arm, name=name, entry_family=arm,
            notional_usd=5., max_hold_minutes=hold, signal_origin_clock='activation_at',
            source_arm_ids=['dex_hot_impulse_v1'] if arm in EXIT_ARMS else [],
            paired_opportunity_group='alpha149_v1',
            paired_opportunity_semantics='same_frozen_signal_where_shared_no_extra_control',
            feature_contract=VERSION, feature_hypothesis=kind,
            trajectory_exit=EXIT_ARMS.get(arm), requires_distinct_trajectory_frame=True,
            entry_filter=dict(direction=arm, max_concurrent_positions=2,
                              single_token_lifetime_entry=True),
            hard_stop_return=-.20, trailing_activate_return=.30, trailing_drawdown=.15,
            take_profit=[], assessment_status='INSUFFICIENT', observer_only=False,
            decision_eligible=True, affects='paper_only',
            description='ALPHA149新增前向5U实验；复用既有连续原池特征，缺失不补零、'
                        '严格后帧成交、共同安全门；非已证Alpha。')
        result.append(policy)
    return adjust(result)


def snapshot():
    return dict(version=VERSION, arms=list(ALL_ARMS), entry_arms=list(SPECS),
                exit_arms=list(EXIT_ARMS), friction=FRICTION,
                extra_requests=0, affects='paper_only',
                note='pure mechanisms over the existing observed-trajectory features')


FEATURE_SAMPLES = 600
FEATURE_KEYS = (
    'pool_age_seconds', 'liquidity_usd', 'frames_total', 'return_30',
    'liquidity_change_30', 'volume_ratio_30', 'tx_ratio_30', 'volatility_30',
    'window_frames_30', 'buy_count_share', 'volume_age_accel', 'tx_age_accel',
    'drawdown', 'plateau_fraction', 'monotonic_up_fraction', 'log_price_r2',
    'volume_liquidity', 'fdv_liquidity', 'price_elasticity_proxy',
    'volume_acceleration_5m_1h', 'tx_acceleration_5m_1h',
)


class Engine(_BaseEngine):
    """Isolated trajectory engine for the ALPHA149 arms.

    It reuses the shared causal feature derivation (`dex_trajectory.derive` via
    the base `accept`) but emits signals ONLY for ALPHA149 arms, so the shared
    dex engine's output, coverage and dedup semantics are untouched.

    It also keeps a bounded, in-memory sample of the real feature distribution so
    thresholds can be calibrated from observed data instead of assumption. This
    is instrumentation only: no I/O, no database, no trading authority.
    """

    def __init__(self, started):
        super().__init__(started)
        self._samples = {key: deque(maxlen=FEATURE_SAMPLES) for key in FEATURE_KEYS}
        # Bounded, causal breadth record: one 0/1 per accepted frame whose 30s
        # window exists. Nothing is fetched for it and no look-ahead is possible.
        self._breadth = deque(maxlen=REGIME_MAX_SAMPLES)

    def accept(self, row, now):
        feature = super().accept(row, now)
        if feature is not None:
            window = _w30(feature) or {}
            frame_return = _num(window.get('return_fraction'))
            if frame_return is not None:
                self._breadth.append(1.0 if frame_return > 0 else 0.0)
            values = {
                'pool_age_seconds': feature.get('pool_age_seconds'),
                'liquidity_usd': feature.get('liquidity_usd'),
                'frames_total': feature.get('frames'),
                'return_30': window.get('return_fraction'),
                'liquidity_change_30': window.get('liquidity_change_fraction'),
                'volume_ratio_30': window.get('rolling_volume_change_ratio'),
                'tx_ratio_30': window.get('rolling_tx_change_ratio'),
                'volatility_30': window.get('realized_volatility'),
                'window_frames_30': window.get('frames'),
                'buy_count_share': feature.get('buy_count_share'),
                'volume_age_accel': feature.get('volume_acceleration_age_normalized'),
                'tx_age_accel': feature.get('tx_acceleration_age_normalized'),
                'drawdown': feature.get('drawdown'),
                'plateau_fraction': feature.get('plateau_fraction'),
                'monotonic_up_fraction': feature.get('monotonic_up_fraction'),
                'log_price_r2': feature.get('log_price_r2'),
                'volume_liquidity': feature.get('volume_liquidity'),
                'fdv_liquidity': feature.get('fdv_liquidity'),
                'price_elasticity_proxy': feature.get('price_elasticity_proxy'),
                'volume_acceleration_5m_1h': feature.get('volume_acceleration_5m_1h'),
                'tx_acceleration_5m_1h': feature.get('tx_acceleration_5m_1h'),
            }
            for key, value in values.items():
                number = _num(value)
                if number is not None:
                    self._samples[key].append(number)
        return feature

    def signals_for(self, token, pool, now):
        now = _parse_time(now)
        state = self.pools.get((token, pool))
        if not state:
            return {}
        f = state['features']
        if not 0 <= (now - _parse_time(f['observed_at'])).total_seconds() <= 30:
            return {}
        # Wave 12 regime view: the fast window's rising share against the engine's
        # own trailing share. Both come from frames already accepted, so the
        # measure is causal, bounded and free of extra requests.
        breadth = self._breadth
        if len(breadth) >= REGIME_MIN_SAMPLES:
            fast_samples = list(breadth)[-REGIME_FAST_SAMPLES:]
            fast = sum(fast_samples) / len(fast_samples)
            slow = sum(breadth) / len(breadth)
            f = {**f, 'regime': {
                'fast': fast, 'slow': slow, 'samples': len(breadth),
                'ratio': (fast / slow) if slow > 0 else None}}
        # Provide the two-frame view the measured supply can actually deliver:
        # the current frame plus the immediately preceding frame of this pool.
        rows = state.get('rows') or ()
        if len(rows) >= 2:
            previous = rows[-2]
            f = {**f, 'pair_frames': len(rows), 'prev': {
                'price_usd': previous.get('price_usd'),
                'liquidity_usd': previous.get('liquidity_usd'),
                'volume_5m_usd': previous.get('volume_5m_usd'),
                'observed_at': previous.get('observed_at')}}
            if len(rows) >= 3:
                before = rows[-3]
                f['prev2'] = {
                    'price_usd': before.get('price_usd'),
                    'liquidity_usd': before.get('liquidity_usd'),
                    'volume_5m_usd': before.get('volume_5m_usd'),
                    'observed_at': before.get('observed_at')}
        else:
            f = {**f, 'pair_frames': len(rows), 'prev': None}
        flags = mechanisms(f)
        self.counts['alpha149_evaluations'] += 1
        for kind, hit in flags.items():
            if hit:
                self.counts['alpha149_ready:' + kind] += 1
        output = {}
        for arm, (kind, _name, _hold) in SPECS.items():
            if flags.get(kind) and arm not in state['signals']:
                key = VERSION + ':' + token + ':' + pool + ':' + arm
                state['signals'][arm] = dict(
                    episode_id=key, decision_key=key,
                    selected=dict(token_id=token, pair_address=pool),
                    observed_at=f['observed_at'], recorded_at=f['recorded_at'],
                    decision_evidence=dict(
                        signal_at=f['recorded_at'], activation_at=iso(self.started),
                        mode=kind, feature_vector=deepcopy(f), mechanism_flags=flags))
                self.counts['signal:' + arm] += 1
                self.recent.append(dict(token_id=token, pair_address=pool,
                                        arm_id=arm, at=f['recorded_at']))
            signal = state['signals'].get(arm)
            if signal and (now - _parse_time(signal['recorded_at'])).total_seconds() <= 60:
                output[arm] = signal
        # Exit arms ride the first frozen ALPHA149 entry signal on this pool:
        # same opportunity, independent exit contract, no extra control arm.
        carrier = next((arm for arm in SPECS if arm in output), None)
        if carrier:
            for arm in EXIT_ARMS:
                signal = deepcopy(output[carrier])
                signal['decision_key'] = signal['decision_key'] + ':' + arm
                output[arm] = signal
        return output

    def snapshot(self):
        snap = super().snapshot()
        snap['version'] = VERSION
        snap['alpha149_arms'] = list(ALL_ARMS)
        snap['extra_requests'] = 0
        snap['feature_samples'] = {
            key: {
                'n': len(values),
                'p10': _percentile(values, .10),
                'p50': _percentile(values, .50),
                'p90': _percentile(values, .90),
            } for key, values in self._samples.items() if values
        }
        snap['mechanism_ready'] = {kind: self.counts['alpha149_ready:' + kind]
                                   for kind in KINDS}
        snap['signals'] = {arm: self.counts['signal:' + arm] for arm in ALL_ARMS}
        breadth = list(self._breadth)
        snap['regime'] = {
            'samples': len(breadth),
            'fast': (sum(breadth[-REGIME_FAST_SAMPLES:]) / len(breadth[-REGIME_FAST_SAMPLES:]))
            if breadth else None,
            'slow': (sum(breadth) / len(breadth)) if breadth else None,
            'ready': len(breadth) >= REGIME_MIN_SAMPLES,
        }
        return snap


def _percentile(values, quantile):
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * quantile
    lower, upper = int(position), min(len(ordered) - 1, int(position) + 1)
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight
