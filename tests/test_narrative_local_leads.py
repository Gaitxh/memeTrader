import sqlite3
from datetime import timedelta
from memetrader.models import utcnow,iso
from memetrader.narrative_hold import local_social_leads,aggregate


def fixture():
    db=sqlite3.connect(':memory:');db.row_factory=sqlite3.Row
    db.executescript('''
    CREATE TABLE token_source_links(id,token_id,last_observed_at,first_observed_at,link_kind,normalized_url,role,verification_status,provider);
    CREATE INDEX token_source_links_token_idx ON token_source_links(token_id,last_observed_at DESC);
    CREATE TABLE provider_post_ambiguity_episodes(id INTEGER PRIMARY KEY,status_id,claimed_handle,post_published_at,recorded_at);
    CREATE TABLE provider_post_ambiguity_memberships(id,token_id,episode_id,candidate_recorded_at,recorded_at,role,verification_status,provider);
    CREATE INDEX provider_post_ambiguity_memberships_token_idx ON provider_post_ambiguity_memberships(token_id,candidate_recorded_at DESC,id DESC);
    CREATE INDEX provider_post_ambiguity_memberships_episode_idx ON provider_post_ambiguity_memberships(episode_id,candidate_recorded_at,id);
    ''')
    return db


def test_local_fanout_and_single_news_are_only_untrusted_readonly_hints():
    db=fixture();now=utcnow();at=iso(now-timedelta(seconds=1));since=now-timedelta(minutes=2)
    for eid,handle in [(1,'elonmusk'),(2,'Reuters')]:
        db.execute('INSERT INTO provider_post_ambiguity_episodes VALUES(?,?,?,?,?)',(eid,str(eid),handle,at,at))
    for i,token,eid in [(1,'solana:A',1),(2,'solana:B',1),(3,'solana:A',2),(4,'solana:Future',1)]:
        stamp=iso(now+timedelta(seconds=1)) if i==4 else at
        db.execute('INSERT INTO provider_post_ambiguity_memberships VALUES(?,?,?,?,?,?,?,?)',(i,token,eid,stamp,stamp,'provider_metadata','unverified','dex'))
    db.commit();writes=db.total_changes;queries=[];db.set_trace_callback(queries.append)
    leads=local_social_leads(db,'solana:A',since,now)
    by_handle={x['claimed_handle']:x for x in leads}
    assert by_handle['elonmusk']['member_count']==2 and by_handle['Reuters']['member_count']==1
    assert by_handle['elonmusk']['ambiguity']=='MULTI_TOKEN_FANOUT'
    assert all(not x['verified_origin'] and not x['verified_binding'] for x in leads)
    assert aggregate(leads,{},None,'solana:A',now)['state']=='UNKNOWN'
    assert db.total_changes==writes and all(q.startswith('SELECT') for q in queries)
    assert any('memberships_token_idx' in r[3] for r in db.execute('EXPLAIN QUERY PLAN SELECT * FROM provider_post_ambiguity_memberships WHERE token_id=? ORDER BY candidate_recorded_at DESC,id DESC LIMIT 16',('solana:A',)))


def test_arrival_after_checkpoint_is_later_hint_not_refreshed_old_metadata():
    db=fixture();now=utcnow();previous=now-timedelta(minutes=1);later=iso(now-timedelta(seconds=1))
    for i,first in [(1,iso(previous-timedelta(seconds=1))),(2,later),(3,iso(now+timedelta(seconds=1)))]:
        db.execute('INSERT INTO token_source_links VALUES(?,?,?,?,?,?,?,?,?)',(i,'solana:A',later,first,'social_post',f'https://x.com/project/status/{i}','provider_metadata','unverified','pump'))
    assert local_social_leads(db,'solana:A',previous,previous)==[]
    leads=local_social_leads(db,'solana:A',previous,now)
    assert len(leads)==1 and leads[0]['status_id']=='2'
    assert leads[0]['post_published_at'] is None
    assert aggregate(leads,{},None,'solana:A',now)['state']=='UNKNOWN'
