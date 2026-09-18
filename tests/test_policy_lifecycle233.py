import math
from scripts.review_policy_lifecycle233 import stats, disposition

def row(token,pnl,status='closed',proceeds=None):
    return dict(token_id=token,stake_usd=20.,realized_pnl_usd=pnl,status=status,
                realized_proceeds_usd=(20.+pnl if isinstance(pnl,(int,float)) else None) if proceeds is None else proceeds)

def test_correlated_positions_do_not_become_independent_tokens():
    result=stats([row('a',2),row('a',3),row('b',-4)])
    assert result['terminal_positions']==3 and result['terminal_tokens']==2
    assert result['net_usd']==1 and result['net_without_best_token']==-4
    assert result['median_token_pnl']==.5

def test_partial_writeoff_is_not_necessarily_full_loss():
    result=stats([row('a',-20,'written_off',0),row('b',4,'written_off',24)])
    assert result['written_off_positions']==2
    assert result['full_loss_writeoffs']==1 and result['positive_pnl_writeoffs']==1

def test_open_and_unknown_states_do_not_enter_terminal_results():
    result=stats([row('a',100,'open'),row('b',200,'ineligible'),row('c',0)])
    assert result['open_positions']==1 and result['terminal_positions']==1
    assert result['net_usd']==0 and result['net_without_best_token'] is None

def test_invalid_terminal_money_is_flagged_not_ranked():
    result=stats([row('a',math.nan),row('b',None)])
    assert result['invalid_terminals']==2
    assert disposition({},result,{})=='REVIEW_INVALID_MONEY_NOT_RANKABLE'

def test_pause_is_preserved_even_for_positive_old_results():
    result=stats([row('a',100)])
    assert disposition({'entry_paused':True},result,{})=='PRESERVE_EXISTING_PAUSE_AND_EXITS'

def test_chain_mix_does_not_generate_blanket_failed_claim():
    sol=stats([row('solana:'+str(i),1) for i in range(30)])
    bsc=stats([row('bsc:'+str(i),-2) for i in range(30)])
    result=stats([row(str(i),-1) for i in range(60)])
    assert disposition({},result,{'solana':sol,'bsc':bsc})=='MIXED_CHAIN_EVIDENCE_NO_BLANKET_CONCLUSION'

def test_positive_tail_and_small_sample_stay_unproven():
    small=stats([row('a',1000)])
    assert disposition({},small,{})=='FORWARD_SAMPLE_INSUFFICIENT'
    tail=stats([row(str(i),-1) for i in range(30)]+[row('winner',1000)])
    assert disposition({},tail,{})=='POSITIVE_TAIL_DEPENDENT_UNPROVEN'

def test_losses_and_ties_remain_in_denominator():
    result=stats([row('a',0),row('b',0),row('c',-3),row('d',1)])
    assert result['terminal_positions']==4
    assert result['mean_position_pnl']==-.5
    assert result['winning_positions']==1 and result['losing_positions']==1
