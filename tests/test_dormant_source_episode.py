from datetime import timedelta
from memetrader.models import TokenCandidate, iso, utcnow
from memetrader.store import Store


def test_dormant_rediscovery_is_bounded_idempotent_and_not_buy_authority(tmp_path,monkeypatch):
    now=utcnow()
    monkeypatch.setattr('memetrader.store.utcnow',lambda:now)
    store=Store(tmp_path/'rediscovery.sqlite3')
    tokens=[]
    for n in range(4):
        token=TokenCandidate('bsc','0x'+str(n)*40,'old','OLD',source='fixture')
        tokens.append(token)
        store.upsert_token(token,seen_at=now-timedelta(hours=2))
        store.enqueue_token_detail_hydration(token.chain,token.address,enqueued_at=now-timedelta(hours=2))
    with store.db:
        store.db.execute("UPDATE token_detail_hydration SET status='complete',last_attempt_at=?",(iso(now-timedelta(hours=2)),))
    first=tokens[0].token_id
    assert store.requeue_dormant_source_episode(first,received_at=now,source_key='profile')
    assert not store.requeue_dormant_source_episode(first,received_at=now,source_key='boost')
    assert store.requeue_dormant_source_episode(tokens[1].token_id,received_at=now,source_key='profile')
    assert not store.requeue_dormant_source_episode(tokens[2].token_id,received_at=now,source_key='profile')
    assert not store.requeue_dormant_source_episode(tokens[3].token_id,received_at=now+timedelta(seconds=1),source_key='future')
    assert store.db.execute("SELECT COUNT(*) FROM chain_meme_pattern_evidence WHERE kind='rediscovery_episode'").fetchone()[0]==2
    assert store.db.execute('SELECT COUNT(*) FROM chain_meme_trader_positions').fetchone()[0]==0
    store.close()
