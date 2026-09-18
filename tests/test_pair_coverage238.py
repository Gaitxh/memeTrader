"""Coverage of offline analytical comparisons; no database or order execution."""
from scripts import paired_arm_ab as m
import pytest

def row(arm, token='solana:T', fill=1, state='closed', pnl=0., stake=20.):
    return dict(arm_id=arm,token_id=token,definition_version='period',
        source_entry_fill_id=fill,source_buy_trade_id=fill,shadow_cohort_id=fill,
        opened_at='2026-09-19T00:00:00Z',status=state,realized_pnl_usd=pnl,
        stake_usd=stake)

def test_open_and_one_sided_units_are_not_zero_return_pairs():
    rows=[row('A',pnl=0),row('B',pnl=0),
          row('A',fill=2,state='open'),row('B',fill=2,pnl=-2),
          row('A',fill=3),row('B',fill=4)]
    result=m.source_pair_coverage(rows,'A','B')
    assert result['counts']==dict(common_terminal=1,awaiting_terminal=1,a_only=1,b_only=1)
    assert result['source_units']==4 and result['independent_tokens_in_union']==1
    assert len(m.paired(rows,'A','B','source_buy'))==1

def test_invalid_terminal_money_is_visible_not_zero_filled():
    rows=[row('A',pnl=float('nan')),row('B')]
    result=m.source_pair_coverage(rows,'A','B')
    assert result['counts']=={'invalid_terminal_money':1}
    assert m.paired(rows,'A','B','source_buy')==[]

def test_ambiguous_duplicates_and_missing_source_are_visible():
    rows=[row('A'),row('A'),row('B'),row('A',fill=None)]
    result=m.source_pair_coverage(rows,'A','B')
    assert result['counts']=={'ambiguous_duplicate':1}
    assert result['invalid_input_positions']==1
    assert result['input_positions']==4

def test_equal_source_different_stake_is_not_comparable():
    rows=[row('A',stake=20),row('B',stake=10)]
    assert m.source_pair_coverage(rows,'A','B')['counts']=={'unequal_stake':1}

def test_source_pointer_conflicts_are_separate():
    a,b=row('A'),row('B');b['source_buy_trade_id']=99
    assert m.source_pair_coverage([a,b],'A','B')['counts']=={'source_pointer_mismatch':1}

def test_period_and_token_isolation():
    rows=[row('A'),row('B',token='bsc:T')]
    extra=row('B');extra['definition_version']='other'
    result=m.source_pair_coverage(rows+[extra],'A','B')
    assert result['source_units']==3
    assert result['counts']=={'a_only':1,'b_only':2}

def test_unsupported_status_and_irrelevant_arm_not_silenced():
    result=m.source_pair_coverage([row('A',state='void'),row('B'),row('C')],'A','B')
    assert result['counts']=={'unsupported_status':1}
    assert result['input_positions']==2

def test_losses_and_ties_all_remain_terminal_units():
    rows=[row(a,fill=f,pnl=-float(f)) for f in range(1,4) for a in ('A','B')]
    result=m.source_pair_coverage(rows,'A','B')
    assert result['counts']=={'common_terminal':3}
    assert len(m.paired(rows,'A','B','source_buy'))==3
    with pytest.raises(ValueError):m.source_pair_coverage(rows,'A','A')
