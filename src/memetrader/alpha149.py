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
from copy import deepcopy

from .dex_trajectory import Engine as _BaseEngine
from .models import iso, parse_time as _parse_time

VERSION = 'alpha149/v1'
# Round-trip friction used by the family: 4% buy + 4% sell (shared constant).
FRICTION = 1.04 / .96 - 1

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
}
EXIT_ARMS = {
    'alpha149_profit_decay_exit_v1': 'alpha149_profit_decay',
    'alpha149_liquidity_shock_exit_v1': 'alpha149_liquidity_shock',
    'alpha149_plateau_stall_exit_v1': 'alpha149_plateau_stall',
    'alpha149_peak_giveback_exit_v1': 'alpha149_peak_giveback',
    'alpha149_flat_dead_exit_v1': 'alpha149_flat_dead',
}
EXIT_KINDS = frozenset(EXIT_ARMS.values())
KINDS = tuple(kind for kind, _, _ in SPECS.values())
ALL_ARMS = tuple(SPECS) + tuple(EXIT_ARMS)

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
    'alpha149_profit_decay_exit_v1': dict(
        notional_usd=5.0, description='共享冲量冻结信号；速度与加速度同负且活动回落即退出。'),
    'alpha149_liquidity_shock_exit_v1': dict(
        notional_usd=5.0, description='共享冲量冻结信号；原池流动性单窗口骤降超过两倍摩擦即退出。'),
    'alpha149_plateau_stall_exit_v1': dict(
        notional_usd=5.0, description='共享冲量冻结信号；滞涨（平台占比升高且笔数回落）即兑现。'),
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
    if not isinstance(f, dict):
        return out
    w = _w30(f)
    if not w:
        return out
    ret = _num(w.get('return_fraction'))
    acc = _num(w.get('acceleration'))
    liq_change = _num(w.get('liquidity_change_fraction'))
    vol_ratio = _num(w.get('rolling_volume_change_ratio'))
    tx_ratio = _num(w.get('rolling_tx_change_ratio'))
    frames = _num(w.get('frames')) or 0
    liquidity = _num(f.get('liquidity_usd'))
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
    volatility = _num(w.get('realized_volatility'))
    r2 = _num(f.get('log_price_r2'))
    residual = _num(f.get('residual_dispersion'))
    turn = _num(f.get('volume_liquidity'))
    total_frames = _num(f.get('frames')) or 0
    if liquidity is None or liquidity < 1000 or ret is None:
        return out
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
        r15 = _num(w15.get('return_fraction'))
        r60 = _num(w60.get('return_fraction'))
        v30 = _num(w.get('log_velocity'))
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

    return out


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


class Engine(_BaseEngine):
    """Isolated trajectory engine for the ALPHA149 arms.

    It reuses the shared causal feature derivation (`dex_trajectory.derive` via
    the base `accept`) but emits signals ONLY for ALPHA149 arms, so the shared
    dex engine's output, coverage and dedup semantics are untouched.
    """

    def signals_for(self, token, pool, now):
        now = _parse_time(now)
        state = self.pools.get((token, pool))
        if not state:
            return {}
        f = state['features']
        if not 0 <= (now - _parse_time(f['observed_at'])).total_seconds() <= 30:
            return {}
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
        return snap
