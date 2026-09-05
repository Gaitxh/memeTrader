from memetrader.capital_entry import capital_entry_signal
D="2026-09-05T12:00:00Z"; A="2026-09-05T10:00:00Z"
H=[{"token_id":"t","pair_address":"p","observed_at":"2026-09-05T11:59:50Z","ingested_at":"2026-09-05T11:59:51Z","recorded_at":"2026-09-05T11:59:52Z"}]
def ev(**x): return {"observed_at":"2026-09-05T11:59:50Z","recorded_at":"2026-09-05T11:59:51Z",**x}
def call(direction,context,**thresholds): return capital_entry_signal(H,{"entry_filter":{"direction":direction,**thresholds}},D,A,{"token_id":"t","pair_address":"p",**context})
def test_wave_and_migration_require_forward_evidence():
 c={"first_wave":ev(status="closed",closed_at="2026-09-05T11:40:00Z"),"new_episode":ev(fresh_flow=True,depth_rebuilt=True,structure_reclaimed=True)}
 assert call("wave_reset_reentry",c,min_gap_seconds=600,max_gap_seconds=14400)[0]
 m=ev(flush_confirmed=True,absorption_frame_count=2,sell_pressure_decayed=True,depth_rebuilt=True,buy_absorption=True)
 assert call("migration_absorption",{"migration":m},min_absorption_frames=2)[0]
def test_amountful_directions_use_policy_thresholds():
 f=ev(capital_velocity_usd_per_second=5,effective_breadth=4,top3_notional_share=.5,median_trade_notional_usd=2,dust_notional_share=.1,net_quote_flow_usd=10,top1_notional_share=.3)
 assert call("capital_velocity",{"amountful_flow":f},min_capital_velocity_usd_per_second=3,min_effective_breadth=3,max_top3_notional_share=.8)[0]
 assert call("effective_breadth",{"amountful_flow":f},min_effective_breadth=3,max_top1_notional_share=.6)[0]
 assert call("churn_resistant",{"amountful_flow":f},min_median_trade_notional_usd=1,max_dust_notional_share=.2)[0]
 assert call("capital_velocity",{"amountful_flow":f},min_capital_velocity_usd_per_second=6,min_effective_breadth=3,max_top3_notional_share=.8)[1].startswith("capital_velocity_")
def test_bundle_ranker_regime_and_risk_require_provenance():
 assert call("bundle_adjusted_breadth",{"coordination":ev(evidence_complete=True,same_slot_only=False,adjusted_effective_breadth=3)},min_adjusted_effective_breadth=2)[0]
 r=ev(all_asof=True,candidates=[ev(token_id="t",score=.8),ev(token_id="other",score=.4)],remaining_slots=1)
 assert call("finite_capital_ranker",{"ranker":r},max_selected_rank=1)[0]
 assert call("market_regime_throttle",{"regime":ev(throttle="allow",cross_section_breadth=.7,depth_health=.8)},min_breadth=.5,min_depth_health=.6)[0]
 risk=ev(sealed=True,cutoff_at="2026-09-05T11:00:00Z",trained_at="2026-09-05T11:30:00Z",sealed_sample_ids=[1,2],sample_status="sufficient_sample",p_profit=.6,p_death=.2,p_no_route=.1)
 assert call("competing_risk",{"competing_risk":risk},min_sealed_samples=2)[0]
def test_missing_future_stale_and_nonfinite_wait():
 assert call("effective_breadth",{"amountful_flow":{"observed_at":D,"recorded_at":D}},min_effective_breadth=1,max_top1_notional_share=.5)[1].startswith("wait_")
 assert not capital_entry_signal([],{"entry_filter":{"direction":"effective_breadth"}},D,A,{})[0]
 bad=ev(effective_breadth=float("inf"),top1_notional_share=.1)
 assert call("effective_breadth",{"amountful_flow":bad},min_effective_breadth=1,max_top1_notional_share=.5)[1].startswith("wait_")

def test_historical_migration_is_valid_but_current_evidence_stays_fresh():
 m={"observed_at":"2026-09-05T10:10:00Z","recorded_at":"2026-09-05T10:10:01Z",
    "flush_confirmed":True,"absorption_frame_count":2,"sell_pressure_decayed":True,
    "depth_rebuilt":True,"buy_absorption":True}
 assert call("migration_absorption",{"migration":m},min_absorption_frames=2)[0]
 stale={"observed_at":"2026-09-05T11:00:00Z","recorded_at":"2026-09-05T11:00:01Z",
        "fresh_flow":True,"depth_rebuilt":True,"structure_reclaimed":True}
 assert call("wave_reset_reentry",{"first_wave":{"observed_at":"2026-09-05T10:10:00Z","recorded_at":"2026-09-05T10:10:01Z","status":"closed","closed_at":"2026-09-05T10:20:00Z"},"new_episode":stale},min_gap_seconds=600,max_gap_seconds=14400)[1] == "wait_wave_reset_provenance"

def test_ranker_is_cross_token_and_risk_training_is_not_future():
 r=ev(all_asof=True,candidates=[ev(token_id="t",score=.2),ev(token_id="other",score=.9)],remaining_slots=1)
 assert call("finite_capital_ranker",{"ranker":r},max_selected_rank=1)[1] == "finite_capital_ranker_not_selected"
 risk=ev(sealed=True,cutoff_at="2026-09-05T11:30:00Z",trained_at="2026-09-05T11:00:00Z",sealed_sample_ids=[1,2],sample_status="sufficient_sample",p_profit=.6,p_death=.2,p_no_route=.1)
 assert call("competing_risk",{"competing_risk":risk},min_sealed_samples=2)[1] == "wait_competing_risk_maturity"
