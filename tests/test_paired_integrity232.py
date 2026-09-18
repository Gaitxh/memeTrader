from datetime import timedelta
import math
import sys
from pathlib import Path
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import paired_arm_ab as tool


def row(arm, pnl=0., status='closed', cohort=1, token='solana:T', at='2026-09-18T00:00:00Z', **kw):
    return dict(arm_id=arm, token_id=token, shadow_cohort_id=cohort,
                opened_at=at,status=status,stake_usd=20.,realized_pnl_usd=pnl,
                definition_version='period1', **kw)


def test_first_open_is_not_replaced_by_later_winner():
    rows=[row('a', status='open'),row('a',100,cohort=2,at='2026-09-18T00:01:00Z'),row('b')]
    assert tool.paired(rows,'a','b','token') == []

@pytest.mark.parametrize('status',['ineligible','cancelled','pending','unknown'])
def test_only_explicit_terminals(status):
    rows=[row('a',100,status=status),row('b')]
    assert tool.paired(rows,'a','b')==[]
    assert tool.summarise(rows,'a')['settled']==0

@pytest.mark.parametrize('value',[None,float('nan'),float('inf')])
def test_unknown_money_never_becomes_zero_or_infinite_effect(value):
    assert tool.paired([row('a',value),row('b')],'a','b')==[]


def test_duplicate_unit_is_ambiguous_not_last_wins():
    assert tool.paired([row('a'),row('a',100),row('b')],'a','b')==[]


def test_same_cohort_number_cannot_cross_token_or_period():
    assert tool.paired([row('a'),row('b',token='solana:OTHER')],'a','b')==[]
    other=row('b');other['definition_version']='period2'
    assert tool.paired([row('a'),other],'a','b')==[]


def test_source_ids_are_namespaced_and_equal_numbers_are_not_enough():
    a=row('a',source_entry_fill_id=42,source_buy_trade_id=42)
    b=row('b',source_buy_trade_id=42,entry_reason='later_observed_protocol_model_paper')
    assert tool.paired([a,b],'a','b','source_buy')==[]


def test_source_pair_equal_size_and_matching_raw_reference():
    a=row('a',1,source_entry_fill_id=42,source_buy_trade_id=42)
    b=row('b',0,cohort=2,source_entry_fill_id=42,source_buy_trade_id=42)
    assert tool.paired([a,b],'a','b','source_buy')[0]['difference']==1
    b['stake_usd']=5
    assert tool.paired([a,b],'a','b','source_buy')==[]
    b['stake_usd']=20;b['source_buy_trade_id']=43
    assert tool.paired([a,b],'a','b','source_buy')==[]

@pytest.mark.parametrize('values',[[-100,1,1],[100,-1,-1]])
def test_loo_detects_both_directions(values):
    result=tool.leave_one_token_out([dict(token_id=str(i),difference=x) for i,x in enumerate(values)])
    assert result['sign_survives'] is False
    assert result['minimum_remaining_mean'] < 0 < result['maximum_remaining_mean']

@pytest.mark.parametrize('values',[[-3,-2,-1],[1,2,3]])
def test_loo_consistent_direction(values):
    assert tool.leave_one_token_out([dict(token_id=str(i),difference=x) for i,x in enumerate(values)])['sign_survives'] is True


def test_ties_stay_in_population_and_zero_has_no_direction():
    pairs=tool.paired([row('a'),row('b')],'a','b')
    assert len(pairs)==1 and pairs[0]['difference']==0
    assert tool.leave_one_token_out([dict(token_id='x',difference=0),dict(token_id='y',difference=0)])['sign_survives'] is False


def test_time_order_uses_instants_not_timezone_text_sort():
    rows=[row('a',5,at='2026-09-18T08:00:00+09:00'),row('a',100,cohort=2,at='2026-09-18T00:00:00Z'),row('b')]
    assert tool.paired(rows,'a','b','token')[0]['a']==5


def test_invalid_time_and_duplicate_first_timestamp_are_not_guessed():
    assert tool.paired([row('a',at='invalid'),row('b')],'a','b')==[]
    assert tool.paired([row('a'),row('a',100,cohort=2),row('b')],'a','b','token')==[]
