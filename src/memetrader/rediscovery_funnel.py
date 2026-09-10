"""Prospective bounded rediscovery diagnostics; no admission authority or I/O."""
from collections import Counter, OrderedDict, deque
from threading import RLock
from datetime import timedelta
import math
from .models import utcnow, iso, parse_time

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


class CohortFlow:
    """Common Paper receipts, once per cohort/stage; no queries or authority.

    Starts at a real admitted cohort, not a fabricated discovery association.
    Old/untracked cohorts remain untracked, including after process restart.
    """
    def __init__(self):
        self.started=utcnow();self.members=OrderedDict();self.counts=Counter()
        self.by_arm={};self.latest_by_arm={};self.windows={'startup_30m':Counter(),'steady':Counter()}
        self.recent=deque(maxlen=32);self.evicted=0;self.unlinked=Counter()
        self.lock=RLock()
        self.opportunities=OrderedDict();self.opportunity_counts=Counter();self.opportunity_evicted=0

    def opportunity(self,version,arm,key,stage,at):
        """Bounded prospective signal/key denominator, including old claims.

        This is separate from cohorts: a repeated signal is not a fresh BUY.
        """
        with self.lock:
            if parse_time(at)<self.started:return
            identity=(version,arm,key)
            if identity not in self.opportunities:
                if len(self.opportunities)>=1024:
                    self.opportunities.popitem(last=False);self.opportunity_evicted+=1
                self.opportunities[identity]=set()
            seen=self.opportunities[identity]
            if stage not in seen:
                seen.add(stage);self.opportunity_counts[stage]+=1

    def admit(self,version,cohort,token,pool,arms,at):
        at=parse_time(at)
        with self.lock:
            key=(version,int(cohort))
            if at<self.started or key in self.members:return
            if len(self.members)>=2048:
                self.members.popitem(last=False);self.evicted+=1
            phase='startup_30m' if (at-self.started).total_seconds()<1800 else 'steady'
            self.members[key]=dict(token=token,pool=pool,arms=set(arms),seen=set(),arm_seen=set(),at=at,phase=phase)
            self.hit(version,cohort,'admitted_after_next_frame',at)

    def hit(self,version,cohort,stage,at,arm=None,reason=None):
        with self.lock:
            key=(version,int(cohort));member=self.members.get(key)
            if member is None:
                self.unlinked[stage]+=1;return
            if (utcnow()-member['at']).total_seconds()>21600:
                del self.members[key];self.evicted+=1;self.unlinked[stage]+=1;return
            if stage not in member['seen']:
                member['seen'].add(stage);self.counts[stage]+=1;self.windows[member['phase']][stage]+=1
                self.recent.append(dict(cohort_id=cohort,token_id=member['token'],pair_address=member['pool'],
                    stage=stage,at=iso(at) if hasattr(at,'timestamp') else at))
            for a in ({arm} if arm else member['arms']):
                if a in member['arms']:
                    self.latest_by_arm[a]={'cohort_id':cohort,'stage':stage,'at':iso(at) if hasattr(at,'timestamp') else at,
                        'block_reason':reason if stage.startswith(('WAIT','REJECT')) else None}
                if a not in member['arms'] or (a,stage) in member['arm_seen']:continue
                member['arm_seen'].add((a,stage));self.by_arm.setdefault(a,Counter())[stage]+=1

    def snapshot(self):
        with self.lock:
            return dict(started_at=iso(self.started),scope='common market and native Paper cohorts admitted in this process',
                unit='unique cohort per stage; per-arm figures must not be summed',counts=dict(self.counts),
                by_arm={a:dict(v) for a,v in self.by_arm.items()},
                latest_by_arm=self.latest_by_arm,
                admission_windows={k:dict(v) for k,v in self.windows.items()},
                current_unique_tokens=len({m['token'] for m in self.members.values()}),
                retained_cohorts=len(self.members),limit=2048,ttl_seconds=21600,evicted=self.evicted,
                unlinked_receipts=dict(self.unlinked),recent=list(self.recent),
                signal_opportunities=dict(unit='unique arm+decision key per stage in bounded process generation; not independent tokens',
                    retained=len(self.opportunities),limit=1024,evicted=self.opportunity_evicted,counts=dict(self.opportunity_counts)),
                unknown=['signals never reaching Store','discovery-to-signal association',
                    'legacy non-market entry and exit paths','old/expired cohorts'],decision_eligible=False,affects='none')
