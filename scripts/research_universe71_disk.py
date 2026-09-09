"""Resume frozen71 normalized research projection, bounded memory/chunk."""
import json,sqlite3,time
from pathlib import Path
from datetime import datetime
R=Path(__file__).resolve().parents[1];O=R/'data/research/universe71';meta=json.loads((O/'scan.json').read_text());hi=meta['snapshot_frontier'];cut=datetime.fromisoformat(meta['cutoff']).timestamp()
src=sqlite3.connect('file:'+str(R/'data/memetrader_forward_20260830_r6.sqlite3').replace('\\','/')+'?mode=ro',uri=True)
out=sqlite3.connect(O/'normalized_identity.sqlite3');out.execute('CREATE TABLE IF NOT EXISTS progress(id INTEGER PRIMARY KEY CHECK(id=1),frontier INTEGER,invalid INTEGER)');out.execute('INSERT OR IGNORE INTO progress VALUES(1,0,0)');out.execute('CREATE TABLE IF NOT EXISTS frames(id INTEGER PRIMARY KEY,token TEXT,pool TEXT,obs REAL,rec REAL,price REAL,liq REAL,volume REAL,buys INTEGER,sells INTEGER,source TEXT,created REAL,dex TEXT,quote TEXT)');out.commit();lo,invalid=out.execute('select frontier,invalid from progress').fetchone();t=time.monotonic()
def stamp(s):
 try:return datetime.fromisoformat(s.replace('Z','+00:00')).timestamp()
 except (TypeError,ValueError,AttributeError):return None
while lo<hi:
 end=min(hi,lo+10000);beg=time.monotonic();src.set_progress_handler(lambda:int(time.monotonic()-beg>10),1000)
 rows=src.execute("select id,token_id,observed_at,ingested_at,recorded_at,price_usd,liquidity_usd,volume_5m_usd,buys_5m,sells_5m,coalesce(json_extract(raw_json,'$.upstream_provider'),provider),json_extract(raw_json,'$.pair.pairAddress'),json_extract(raw_json,'$.pair.pairCreatedAt'),json_extract(raw_json,'$.pair.dexId'),json_extract(raw_json,'$.pair.quoteToken.address'),json_extract(raw_json,'$.pair.baseToken.address'),json_extract(raw_json,'$.pair.chainId') from token_snapshots where id>? and id<=? and price_usd>0 and liquidity_usd>=1000 order by id",(lo,end)).fetchall();batch=[]
 for s in rows:
  obs,ing,rec=[stamp(v) for v in s[2:5]]
  if None in (obs,ing,rec) or not obs<=ing<=rec<=cut or not s[11]:invalid+=1;continue
  chain,address=s[1].split(':',1)
  base=s[15] if chain=='solana' else str(s[15] or '').lower()
  if base!=(address if chain=='solana' else address.lower()) or s[16]!=chain:invalid+=1;continue
  pool=s[11] if s[1].startswith('solana:') else s[11].lower()
  batch.append((s[0],s[1],pool,obs,rec,*s[5:11],s[12],s[13],s[14]))
 with out:
  out.executemany('insert or ignore into frames values(?,?,?,?,?,?,?,?,?,?,?,?,?,?)',batch);out.execute('update progress set frontier=?,invalid=? where id=1',(end,invalid))
 lo=end
 if lo%100000==0 or lo==hi:print('frontier',lo,'elapsed',round(time.monotonic()-t,1),flush=True)
 time.sleep(.02)
out.execute('create index if not exists frames_identity on frames(token,pool,rec,id)');out.commit()
r={'source_cutoff':meta['cutoff'],'source_frontier':hi,'complete':lo==hi,'valid_rows':out.execute('select count(*) from frames').fetchone()[0],'invalid':invalid,'elapsed':time.monotonic()-t,'bytes':(O/'normalized_identity.sqlite3').stat().st_size};(O/'normalized.json').write_text(json.dumps(r,indent=2));print(r,flush=True)
