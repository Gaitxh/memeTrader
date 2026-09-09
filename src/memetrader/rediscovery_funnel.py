"""Prospective bounded rediscovery diagnostics; no admission authority or I/O."""
from collections import Counter, OrderedDict, deque
from threading import RLock
from datetime import timedelta
import math
from .models import utcnow, iso

class RediscoveryFunnel:
    def __init__(self):
        self.started = utcnow()
        self.members = OrderedDict()
        self.counts = Counter()
        self.examples = deque(maxlen=32)
        self.lock = RLock()
        self.last_flush = 0.0

    def _expire(self, now):
        while self.members and next(iter(self.members.values()))['expires'] <= now:
            self.members.popitem(last=False)
            self.counts['membership_expired'] += 1

    def episode(self, token_id, at, baseline=None):
        with self.lock:
            self._expire(at)
            self.members.pop(token_id, None)
            if len(self.members) >= 256:
                self.members.popitem(last=False)
                self.counts['membership_evicted'] += 1
            self.members[token_id] = {'at':at, 'expires':at+timedelta(hours=1), 'seen':set(), 'baseline':baseline}
            self.hit(token_id, 'episode', at)

    def hit(self, token_id, stage, at, *, recent=True):
        with self.lock:
            self._expire(at)
            member = self.members.get(token_id)
            if member is None or at < member['at']:
                return
            if stage not in member['seen']:
                member['seen'].add(stage)
                self.counts[stage] += 1
                if recent:
                    self.examples.append({'token_id':token_id, 'episode_at':iso(member['at']),
                                          'stage':stage, 'at':iso(at)})
            if ('temporary_slot' in member['seen'] and stage in (
                    'pattern_observation','reactivation_ready','safety_stage','BUY')):
                linked='temporary_slot_'+stage
                if linked not in member['seen']:
                    member['seen'].add(linked);self.counts[linked]+=1

    def quote(self, token, snapshot, reason, now, floor, occupancy=None):
        with self.lock:
            self._expire(now)
            if token.token_id not in self.members:
                return
            self.hit(token.token_id, 'admission_attempt', now, recent=False)
            self.hit(token.token_id, reason, now, recent=False)
            if reason=='skip_bucket_full' and occupancy is not None:
                self.hit(token.token_id, 'bucket_full_chain_spare' if occupancy['chain_total']<10
                         else 'bucket_full_chain_full', now, recent=False)
            self.examples.append({'token_id':token.token_id,'episode_at':iso(self.members[token.token_id]['at']),
                                  'stage':'admission_attempt','at':iso(now),'reason':reason,
                                  'occupancy':occupancy})
            self.basic(token.token_id, snapshot, now, snapshot.ingested_at, floor)

    def basic(self, token_id, snapshot, now, ingestion, floor):
        with self.lock:
            self._expire(now)
            if token_id not in self.members:
                return
            raw = snapshot.raw or {}
            pair = raw.get('pair', raw)
            price, liquidity = snapshot.price_usd, snapshot.liquidity_usd
            # Diagnostics only: don't substitute receipt clocks or missing values.
            if (price is not None and math.isfinite(price) and price > 0
                    and liquidity is not None and math.isfinite(liquidity) and liquidity >= floor
                    and pair.get('pairAddress') and ingestion is not None
                    and self.members[token_id]['at'] <= snapshot.observed_at <= ingestion <= now
                    and (now-snapshot.observed_at).total_seconds() <= 30):
                self.hit(token_id, 'basic_valid', now)

    def snapshot(self):
        with self.lock:
            self._expire(utcnow())
            return {'generation_started_at':iso(self.started), 'scope':'prospective_process_generation',
                    'decision_eligible':False, 'affects':'none', 'unit':'unique episode per stage/reason',
                    'association':'token membership after local episode receipt; not proof that episode caused later work',
                    'membership_limit':256, 'membership_ttl_seconds':3600,
                    'members':len(self.members), 'counts':dict(self.counts),
                    'recent':list(self.examples), 'unknown':['expired/untracked episode downstream stages',
                    'BUY paths other than common market-entry projection', 'safety verdict beyond common guard allow/wait']}
