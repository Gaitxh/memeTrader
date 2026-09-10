"""Bounded causal DEX mechanisms for the independent 144 Paper cohort.

This module deliberately does not alter the frozen trajectory139/141 contracts.
It consumes only already observed rows and emits envelopes for the runtime owner.
"""
from collections import OrderedDict, Counter, deque
from copy import deepcopy
from math import isfinite, log
import re

from .models import iso, parse_time

VERSION = "trajectory144/v1"
MAX_POOLS, MAX_ROWS, TTL_SECONDS = 256, 192, 900
MIN_WINDOW_SECONDS, MIN_POINTS, MAX_GAP_SECONDS = 30, 3, 60
FRICTION = 1.04 / .96 - 1.0
ARMS = (
    "trajectory144_early_activity_fast_v1", "trajectory144_sparse_peer_hot_fast_v1",
    "trajectory144_absorption_reclaim_v1", "trajectory144_trend_runner_v1",
    "trajectory144_second_wave_v1", "trajectory144_adaptive_selector_v1",
)


def _num(value):
    if value is None or isinstance(value, bool): return None
    try: value = float(value)
    except (TypeError, ValueError): return None
    return value if isfinite(value) else None


def _activity(row):
    buys, sells = _num(row.get("buys_5m")), _num(row.get("sells_5m"))
    return buys + sells if buys is not None and sells is not None and buys >= 0 and sells >= 0 else None


def _window(rows, seconds=MIN_WINDOW_SECONDS):
    if len(rows) < MIN_POINTS: return None
    end = rows[-1]["t"]
    prior = [r for r in rows if r["t"] <= end - seconds]
    if not prior: return None
    start = prior[-1]
    eligible = [r for r in rows if start["t"] <= r["t"] <= end]
    if len(eligible) < MIN_POINTS or eligible[-1]["t"] - eligible[0]["t"] > seconds + MAX_GAP_SECONDS: return None
    if any(b["t"] - a["t"] > MAX_GAP_SECONDS for a, b in zip(eligible, eligible[1:])): return None
    first, last = eligible[0], eligible[-1]
    if not first["price_usd"] or not last["price_usd"]: return None
    span = last["t"] - first["t"]
    mid = eligible[len(eligible)//2]
    tx0, tx1, tx2 = _activity(first), _activity(mid), _activity(last)
    v0, v1, v2 = _num(first.get("volume_5m_usd")), _num(mid.get("volume_5m_usd")), _num(last.get("volume_5m_usd"))
    left, right = mid["t"]-first["t"], last["t"]-mid["t"]
    return {"start_at": first["observed_at"], "end_at": last["observed_at"], "span_seconds": span,
            "return_fraction": last["price_usd"] / first["price_usd"] - 1.0,
            "log_slope": log(last["price_usd"] / first["price_usd"]) / span,
            "activity_change": _ratio(_activity(last), _activity(first)),
            "volume_change": _ratio(last.get("volume_5m_usd"), first.get("volume_5m_usd")),
            "liquidity_change": _ratio(last.get("liquidity_usd"), first.get("liquidity_usd")),
            "activity_acceleration": ((tx2-tx1)/right - (tx1-tx0)/left) if None not in (tx0,tx1,tx2) and left and right else None,
            "volume_acceleration": ((v2-v1)/right - (v1-v0)/left) if None not in (v0,v1,v2) and left and right else None}


def _ratio(a, b):
    a, b = _num(a), _num(b)
    return a / b if a is not None and b not in (None, 0) else None


def _canonical(row):
    chain, token, pool = str(row.get("chain") or "").lower(), str(row.get("token_id") or ""), str(row.get("pair_address") or "")
    evm = re.compile(r"^0x[0-9a-fA-F]{40}$")
    evm_pool = re.compile(r"^0x(?:[0-9a-fA-F]{40}|[0-9a-fA-F]{64})$")
    sol = re.compile(r"^[1-9A-HJ-NP-Za-km-z]{32,44}$")
    if not token.startswith(chain+":"): return False
    return bool((chain in {"bsc", "ethereum", "base", "arbitrum", "polygon", "avalanche", "optimism", "robinhood"} and evm.fullmatch(token.split(":")[-1]) and evm_pool.fullmatch(pool)) or (chain == "solana" and sol.fullmatch(token.split(":")[-1]) and sol.fullmatch(pool)))


class Engine:
    def __init__(self, started):
        self.started = parse_time(started); self.pools = OrderedDict(); self.counts = Counter()

    def accept(self, row, now):
        now, row = parse_time(now), dict(row)
        try:
            observed, ingested, recorded = (parse_time(row[k]) for k in ("observed_at", "ingested_at", "recorded_at"))
        except (KeyError, TypeError, ValueError): self.counts["invalid_clock"] += 1; return None
        for key in ("price_usd", "liquidity_usd", "volume_5m_usd", "buys_5m", "sells_5m", "pool_age_seconds"):
            row[key] = _num(row.get(key))
        if not (self.started <= observed <= ingested <= recorded <= now and (now-observed).total_seconds() <= MAX_GAP_SECONDS
                and str(row.get("provider") or "").startswith("dexscreener") and _canonical(row) and row["price_usd"] and row["price_usd"] > 0
                and row["liquidity_usd"] is not None and row["liquidity_usd"] >= 1000):
            self.counts["invalid_or_missing"] += 1; return None
        if row["chain"] != "solana":
            row["token_id"]=row["token_id"].lower(); row["pair_address"]=row["pair_address"].lower()
        identity = (str(row["token_id"]), str(row["pair_address"])); row["t"] = observed.timestamp()
        while self.pools and (now - parse_time(next(iter(self.pools.values()))["last_at"])).total_seconds() > TTL_SECONDS:
            self.pools.popitem(last=False); self.counts["expired"] += 1
        state = self.pools.get(identity)
        if state and observed <= parse_time(state["last_at"]): self.counts["noncausal"] += 1; return None
        if state is None:
            if len(self.pools) >= MAX_POOLS: self.pools.popitem(last=False); self.counts["evicted"] += 1
            state = {"rows": deque(maxlen=MAX_ROWS), "emitted": set(), "episodes": 0, "phase": "idle"}; self.pools[identity] = state
        if state["rows"] and row["t"] - state["rows"][-1]["t"] > MAX_GAP_SECONDS:
            state.update(rows=deque(maxlen=MAX_ROWS), signals={}, phase="idle"); self.counts["gap_episode_reset"] += 1
        state["rows"].append(row); state["last_at"] = row["recorded_at"]
        # Preserve real older observations for the 300s runner window while
        # retaining every short-window point; no interpolation or replay.
        retained=[];last_bucket=None
        for old in state["rows"]:
            elapsed=row["t"]-old["t"]
            if elapsed>660:continue
            bucket=int(old["t"]//15)
            if elapsed<=90 or bucket!=last_bucket:retained.append(old)
            last_bucket=bucket
        state["rows"]=deque(retained,maxlen=MAX_ROWS)
        state["features"] = self._features(identity, state)
        self.pools.move_to_end(identity); self.counts["accepted"] += 1
        for name,ok in (("tx",_activity(row) is not None),("volume",row.get("volume_5m_usd") is not None),("age",row.get("pool_age_seconds") is not None),("window30",state["features"]["window_30"] is not None)):
            self.counts[("input_ready:" if ok else "input_unknown:")+name]+=1
        return deepcopy(state["features"])

    def _features(self, identity, state):
        rows = list(state["rows"]); current = rows[-1]; win = _window(rows)
        prices = [r["price_usd"] for r in rows]; high = max(prices); drawdown = current["price_usd"] / high - 1
        first = rows[0]; early_slope = log(current["price_usd"] / first["price_usd"]) / max(current["t"]-first["t"], 1)
        # At ages below five minutes m5 and h1 cover the same life: no ratio is exposed.
        age = current.get("pool_age_seconds")
        degenerate = age is not None and age < 300
        high_row = max(rows[:-1], key=lambda r:r["price_usd"], default=current); after_high = [r for r in rows if r["t"] > high_row["t"]]
        trough_row = min(after_high, key=lambda r:r["price_usd"], default=current)
        recovered = bool(after_high and trough_row["t"] < current["t"] and trough_row["price_usd"] <= high_row["price_usd"]*(1-FRICTION)
                         and current["price_usd"] >= max(trough_row["price_usd"]*(1+FRICTION),high_row["price_usd"]*(1-FRICTION/2))
                         and min(r["liquidity_usd"] for r in after_high) >= high_row["liquidity_usd"]*(1-FRICTION))
        impulse = bool(win and win["return_fraction"] > FRICTION and win["activity_change"] and win["activity_change"] > 1)
        phase = state.get("phase", "idle"); cool = base = new_start = False
        # One transition per observed frame prevents a fabricated same-frame cycle.
        if phase == "idle" and impulse: state.update(phase="impulse", impulse_at=current["observed_at"])
        elif phase == "impulse" and drawdown <= -FRICTION: state.update(phase="cool", cool_at=current["observed_at"]); cool = True
        elif phase == "cool" and win and abs(win["return_fraction"]) <= FRICTION/2: state.update(phase="base", base_at=current["observed_at"]); base = True
        elif phase == "base" and win and abs(win["return_fraction"]) <= FRICTION/2: base = True
        elif phase == "base" and win and current["t"]-parse_time(state["base_at"]).timestamp() >= 60 and win["return_fraction"] > FRICTION and (win["activity_change"] or 0) > 1: new_start = True
        return {"version": VERSION, "token_id": identity[0], "pair_address": identity[1], "observed_at": current["observed_at"],
                "recorded_at": current["recorded_at"], "pool_age_seconds": age, "frames": len(rows), "window_30": win,
                "windows": {"30": win,"300":_window(rows,300)}, "ingested_at":current["ingested_at"],
                "current":{k:current.get(k) for k in ("price_usd","liquidity_usd","volume_5m_usd","buys_5m","sells_5m")}, "continuity_started_at": first["observed_at"],
                "chain": current.get("chain"), "early_m5_h1_degenerate": degenerate, "early_actual_log_slope": early_slope,
                "drawdown": drawdown, "absorption_recovery": recovered, "observed_impulse": phase in {"impulse", "cool", "base"},
                "cooldown": cool, "base": base, "new_start": new_start, "second_wave_phase": state.get("phase"),
                "buy_count_share": _ratio(current.get("buys_5m"), _activity(current))}

    def signals_for(self, token, pool, now):
        now = parse_time(now); state = self.pools.get((str(token), str(pool)))
        if not state: return {}
        f = state["features"]
        if not 0 <= (now-parse_time(f["observed_at"])).total_seconds() <= MAX_GAP_SECONDS: return {}
        w = f["window_30"]
        if not w: self.counts["missing_actual_window"] += 1; return {}
        band = int(f["pool_age_seconds"] // 300) if f["pool_age_seconds"] is not None else None
        peers = [s["features"] for s in self.pools.values() if s["features"].get("window_30") and s["features"].get("chain") == f.get("chain") and band is not None and s["features"].get("pool_age_seconds") is not None and int(s["features"]["pool_age_seconds"] // 300) == band and 0 <= (now-parse_time(s["features"]["observed_at"])).total_seconds() <= MAX_GAP_SECONDS]
        rank = None if len(peers) < 3 else sum(x["window_30"]["log_slope"] <= w["log_slope"] for x in peers) / len(peers)
        common = w["return_fraction"] > FRICTION and (w["liquidity_change"] or 0) >= 1 and (w["activity_change"] or 0)>1 and (w["volume_change"] or 0)>1
        flags = {
            ARMS[0]: common and f["early_m5_h1_degenerate"] and f["early_actual_log_slope"] > 0 and (w["activity_acceleration"] or 0) > 0 and (w["volume_acceleration"] or 0) > 0,
            ARMS[1]: common and f["pool_age_seconds"] is not None and 0<=f["pool_age_seconds"]<=900 and ((rank is not None and rank >= .75) or (rank is None and (w["activity_change"] or 0) > 1 and f["drawdown"] > -FRICTION)),
            ARMS[2]: f["absorption_recovery"] and (w["liquidity_change"] or 0) >= 1,
            ARMS[3]: flags_early if (flags_early := (common and f["early_m5_h1_degenerate"] and f["early_actual_log_slope"] > 0 and (w["activity_acceleration"] or 0) > 0 and (w["volume_acceleration"] or 0) > 0)) else False,
            ARMS[4]: f["new_start"] and state["episodes"] < 2,
            ARMS[5]: common and (w["activity_change"] or 0) > 1,
        }
        out = {}
        self.counts["sparse_peer" if rank is None else "peer_rank_available"]+=1
        for arm, passed in flags.items():
            if passed:self.counts["ready:"+arm]+=1
            emitted_key = arm if arm != ARMS[4] else arm+":"+str(state["episodes"])
            if passed and emitted_key not in state["emitted"]:
                state["emitted"].add(emitted_key)
                if arm == ARMS[4]: state["episodes"] += 1
                if arm == ARMS[4]: state["phase"] = "idle"
                envelope = {"episode_id": f"{VERSION}:{token}:{pool}:{state['episodes']}", "decision_key": f"{VERSION}:{token}:{pool}:{arm}:{state['episodes']}",
                            "selected": {"token_id": token, "pair_address": pool}, "observed_at": f["observed_at"], "recorded_at": f["recorded_at"],
                            "decision_evidence": {"mode": arm, "feature_vector": deepcopy(f), "activation_at": iso(self.started), "peer_count": len(peers), "peer_rank": rank,
                                                  "sparse_peer_mode": rank is None, "friction": FRICTION}}
                if arm == ARMS[3] and ARMS[0] in state.get("signals", {}):
                    envelope = deepcopy(state["signals"][ARMS[0]])
                    envelope["decision_evidence"]["mode"] = arm
                state.setdefault("signals", {})[arm] = envelope; self.counts["signal:"+arm] += 1
            if arm in state.get("signals", {}) and 0 <= (now-parse_time(state["signals"][arm]["recorded_at"])).total_seconds()<=60:
                out[arm] = deepcopy(state["signals"][arm])
        return out

    def snapshot(self):
        return {"version": VERSION, "pools": len(self.pools), "counts": dict(self.counts), "limits": {"max_pools": MAX_POOLS, "max_rows": MAX_ROWS, "ttl_seconds": TTL_SECONDS}}

    def state_payload(self):
        pools = []
        for (token, pool), state in self.pools.items():
            pools.append({"token_id": token, "pair_address": pool, "rows": list(state["rows"]), "features": state.get("features"), "signals": state.get("signals", {}),
                          "emitted": sorted(state.get("emitted", set())), "episodes": state.get("episodes", 0), "phase": state.get("phase", "idle"),
                          "impulse_at": state.get("impulse_at"), "cool_at": state.get("cool_at"), "base_at": state.get("base_at"), "last_at": state["last_at"]})
        return {"version": VERSION, "started_at": iso(self.started), "pools": pools, "counts": dict(self.counts)}

    def load_state(self, payload):
        if payload.get("version") != VERSION or parse_time(payload.get("started_at")) < self.started: return False
        rebuilt = OrderedDict()
        for item in payload.get("pools") or []:
            rows = deque(item.get("rows") or [], maxlen=MAX_ROWS)
            if not rows or len(rebuilt) >= MAX_POOLS: continue
            identity = (str(item["token_id"]), str(item["pair_address"]))
            state = {"rows": rows, "signals": item.get("signals") or {}, "emitted": set(item.get("emitted") or []), "episodes": min(int(item.get("episodes") or 0), 2),
                     "phase": item.get("phase") or "idle", "last_at": item["last_at"]}
            for key in ("impulse_at", "cool_at", "base_at"):
                if item.get(key): state[key] = item[key]
            state["features"] = item.get("features") or self._features(identity, state); rebuilt[identity] = state
        self.pools = rebuilt; self.counts = Counter(payload.get("counts") or {}); return True


def short_fast_failure_exit(features, opened_at, now):
    """Causal short-fast decay; the caller supplies the actual SELL policy."""
    if not features or parse_time(opened_at) >= parse_time(features["observed_at"]) or parse_time(features["recorded_at"]) > parse_time(now): return False
    w = features.get("window_30")
    return bool(w and 0<=(parse_time(now)-parse_time(features["observed_at"])).total_seconds()<=30 and parse_time(w["start_at"])>=parse_time(opened_at) and w["return_fraction"] < 0 and (w["activity_change"] or 1) < 1 and (w["liquidity_change"] or 1) < 1)


def trend_extension(features, opened_at, now):
    """30-to-120 minutes needs a fully observed healthy 300-second path."""
    if not features:return False
    observed,recorded,current=(parse_time(v) for v in (features["observed_at"],features["recorded_at"],now))
    if not parse_time(opened_at)<observed<=recorded<=current or not 0<=(current-observed).total_seconds()<=30:return False
    w = features.get("windows",{}).get("300")
    return bool(w and parse_time(w["start_at"])>=parse_time(opened_at) and w["log_slope"] > 0 and (w["activity_change"] or 0) >= 1 and (w["liquidity_change"] or 0) >= 1-FRICTION and features["drawdown"] > -FRICTION)


def policies(base):
    names = ("早龄真实活动脉冲·快进快出", "稀疏同龄HOT·自身轨迹", "卖压回撤承接·再收复", "同脉冲入口·纯量价趋势长持", "首波冷却后·独立第二波", "有限在线学习·可用模式选择")
    result = []
    for arm, name in zip(ARMS, names):
        p = {k:v for k,v in deepcopy(base).items() if k not in {"source_arm_ids", "paired_opportunity_group", "entry_alias_of", "trajectory_exit"}}
        p.update(arm_id=arm, canonical_id=arm, name=name, entry_family=arm, notional_usd=2.0,
            max_hold_minutes=30 if arm in (ARMS[3], ARMS[4]) else 5, feature_contract=VERSION, trajectory_engine="v144", requires_distinct_trajectory_frame=True,
            signal_origin_clock="activation_at", entry_filter={"direction": arm, "max_concurrent_positions": 2, "include_pending_in_limit": True, "single_token_open_or_reserved": True, "requires_actual_window_seconds": 30, "min_distinct_frames": 3, "max_gap_seconds": 60},
            trajectory144_exit="trend" if arm == ARMS[3] else "decay",
            description="独立2U/max2前向实验；Dex滚动活动变化不是签名净资金；统一安全、严格后帧成交，无Agent。",
            assessment_status="INSUFFICIENT", paired_opportunity_group=VERSION, paired_opportunity_semantics="same frozen source where shared; independent bounded accounts", affects="paper_only", decision_eligible=True,
            observer_only=False, required_window_seconds=30, hard_stop_return=-.20, trailing_activate_return=.30, trailing_drawdown=.15, take_profit=[])
        p['data_contract']=dict(provider='Dexscreener exact original pool',min_liquidity_usd=1000,
            min_distinct_points=3,minimum_span_seconds=30,maximum_span_seconds=90,max_gap_seconds=60,
            max_feature_age_seconds=30,missing='UNKNOWN, no fabricated 5s/15s windows',
            activity='changes/slopes of reported rolling aggregates, not signed capital')
        p['entry_rules144']={
            ARMS[0]:'池龄小于300秒；实际30–90秒价格位移超过4%双边摩擦，两个半窗笔数/成交额变化率加速且总活动增加、流动性不降；不使用退化m5/h1。',
            ARMS[1]:'池龄不超过900秒；价格与活动前进、流动性不降；同链同龄至少3币时取速度上四分位，否则明确用自身轨迹及回撤约束。',
            ARMS[2]:'实际先高点、超过摩擦尺度回撤、后收复到前高附近；回撤流动性保持，恢复帧流动性不降，不要求买入笔数超过卖出。',
            ARMS[3]:'与早龄脉冲相同冻结信号及后帧，独立2U；默认30分钟；300秒实际价格趋势与活动、流动性健康才续至绝对120分钟。',
            ARMS[4]:'依次观察首波、显著回落、至少60秒底部及后来的新活动脉冲；每原池最多2个独立新阶段，间断不补历史。',
            ARMS[5]:'仅从实际可用的新第二波/承接/早龄/稀疏HOT选择一支；冷启动固定优先级；成熟成本/覆盖/独立样本门通过后最多2个模型发布，只影响新订单。'}[arm]
        if arm == ARMS[5]:
            p["router_exit_profiles"]={a:{"max_hold_minutes":30 if a==ARMS[4] else 15 if a==ARMS[2] else 5} for a in (ARMS[0],ARMS[1],ARMS[2],ARMS[4])}
            p["model_contract"]="mode-learning144/v3: fixed priority cold start; maximum two causal coverage-cost-aware releases; existing positions retain frozen mode"
        if arm == ARMS[2]: p["max_hold_minutes"] = 15
        if arm == ARMS[3]: p.update(trajectory_trend_runner=True, source_arm_ids=[ARMS[0]], entry_alias_of=ARMS[0], trend_base_hold_minutes=30, trend_max_hold_minutes=120)
        result.append(p)
    return result
