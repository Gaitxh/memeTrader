import sqlite3
from datetime import timedelta
import pytest
from memetrader.models import iso,utcnow,TokenCandidate
from memetrader.prebreakout_loss_memory import prior_loss,policy,ARM,PARENT,CORE
from memetrader.resource_bound_research import resource_policies
from memetrader.capital_policies import opportunity_policies
from memetrader.revision_evidence_extensions import revise_evidence_extension
from test_resource_bound_store import setup_store,quote

@pytest.mark.parametrize('pair,status,pnl,offset,blocked',[
 ('Pool','closed',-1,-1,True),('Other','closed',-1,-1,False),
 ('Pool','closed',1,-1,False),('Pool','open',-1,-1,False),
 ('Pool','written_off',-5,-1,True),('Pool','closed',-1,1,False),('pool','closed',-1,-1,False)])
def test_loss_lookup_exact_asof(pair,status,pnl,offset,blocked):
 c=sqlite3.connect(':memory:');c.executescript('create table chain_meme_trader_registrations(definition_version);create table chain_meme_trader_v6_cohorts(id,definition_version,pair_address);create table chain_meme_trader_positions(definition_version,shadow_cohort_id,token_id,arm_id,status,closed_at,realized_pnl_usd);')
 now=utcnow();c.execute("insert into chain_meme_trader_registrations values('old')");c.execute("insert into chain_meme_trader_v6_cohorts values(1,'old',?)",(pair,));c.execute("insert into chain_meme_trader_positions values('old',1,'solana:T',?,?,?,?)",(CORE,status,iso(now+timedelta(seconds=offset)),pnl))
 assert (prior_loss(c,'solana:T','Pool',now) is not None)==blocked
 c.close()

@pytest.mark.parametrize('loss',[False,True])
def test_candidate_keeps_parent_signal_next_frame_and_old_contract(tmp_path,monkeypatch,loss):
 store,clock=setup_store(tmp_path,monkeypatch)
 core=next(p for p in resource_policies() if p['arm_id']==CORE);store.append_chain_meme_trader_policy(core,activated_at=clock[0])
 token=TokenCandidate('solana','MemoryToken','Memory');created=int((clock[0]-timedelta(minutes=90)).timestamp()*1000)
 for _ in range(2):
  clock[0]+=timedelta(seconds=16);store.observe_chain_meme_pattern(token,quote(token,'Pool',created,clock[0],age_rate=True),recorded_at=clock[0])
 assert store.db.execute('select count(*) from chain_meme_trader_positions where arm_id=?',(CORE,)).fetchone()[0]==1
 with store.db:store.db.execute('update chain_meme_trader_positions set status=?,closed_at=?,realized_pnl_usd=? where arm_id=?',('closed',iso(clock[0]),-1 if loss else 1,CORE))
 parent=revise_evidence_extension(next(p for p in opportunity_policies() if p['arm_id']==PARENT));store.append_chain_meme_trader_policy(parent,activated_at=clock[0])
 before=store.db.execute('select policy_json from chain_meme_trader_policy_additions where arm_id=?',(PARENT,)).fetchone()[0]
 assert store.register_prebreakout_loss_memory92()==1;assert store.register_prebreakout_loss_memory92()==0
 assert store.db.execute('select policy_json from chain_meme_trader_policy_additions where arm_id=?',(PARENT,)).fetchone()[0]==before
 monkeypatch.setattr('memetrader.strategy_revisions.revision_entry_signal',lambda *a,**k:(True,'fixture_existing_signal'))
 clock[0]+=timedelta(seconds=16);store.observe_chain_meme_pattern(token,quote(token,'Pool',created,clock[0]),recorded_at=clock[0])
 assert store.db.execute('select count(*) from chain_meme_trader_positions where arm_id=?',(ARM,)).fetchone()[0]==0
 clock[0]+=timedelta(seconds=16);store.observe_chain_meme_pattern(token,quote(token,'Pool',created,clock[0]),recorded_at=clock[0])
 assert store.db.execute('select count(*) from chain_meme_trader_positions where arm_id=?',(PARENT,)).fetchone()[0]==1
 assert store.db.execute('select count(*) from chain_meme_trader_positions where arm_id=?',(ARM,)).fetchone()[0]==(0 if loss else 1)
 store.close()

