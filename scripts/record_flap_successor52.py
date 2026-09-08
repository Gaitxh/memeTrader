"""Record the fixed-block, independently verified held Flap links; no market data replay."""
import json, sqlite3, hashlib
from datetime import datetime, timezone
from pathlib import Path
from memetrader.flap_successor import KEY, PORTAL
ROOT=Path(__file__).resolve().parents[1]
p=ROOT/"data/research/flap_migration52"
r=json.loads((p/"probe.json").read_text())
assert r["chain"]["result"]=="0x38"
block=r["block"]["result"]; header=r["header"]["result"]
assert header["number"]==block
originals=json.loads((ROOT/"data/research/bsc_original_pool49/decoded_probe.json").read_text())
cfg=json.loads((ROOT/"config.json").read_text(encoding="utf-8"));assert not cfg.get("live",{}).get("enabled")
db=Path(cfg["database"]);db=db if db.is_absolute() else ROOT/db
c=sqlite3.connect(db.as_uri()+"?mode=rw",uri=True,timeout=5);c.row_factory=sqlite3.Row
c.execute("BEGIN IMMEDIATE")
now=datetime.now(timezone.utc).isoformat();links=[]
for item,old in zip(r["tokens"],originals):
    words=item["words"];assert len(words)==15 and int(words[0],16)==4
    token="bsc:"+item["token"]
    assert item["token"][2:] in [old[x]["result"][-40:] for x in ("token0","token1")]
    assert c.execute("SELECT count(*) FROM chain_meme_trader_positions WHERE token_id=? AND status='open'",(token,)).fetchone()[0]>0
    link=dict(kind="OFFICIAL_MIGRATION_SUCCESSOR",portal=PORTAL,chain_id=56,status=4,token_id=token,original_pool=old["pool"],successor_pool="0x"+words[13][-40:],block_number=block,block_hash=header["hash"],observed_at=datetime.fromtimestamp(int(header["timestamp"],16),timezone.utc).isoformat(),ingested_at=item["received_at"],recorded_at=now,rpc_response=item["response"],evidence_sha256=hashlib.sha256((p/"probe.json").read_bytes()).hexdigest())
    key=KEY+token+":"+old["pool"]
    prior=c.execute("SELECT value_json FROM kv WHERE key=?",(key,)).fetchone()
    if prior:
        assert json.loads(prior[0])["successor_pool"]==link["successor_pool"]
        link=json.loads(prior[0])
    else:
        c.execute("INSERT INTO kv(key,value_json,updated_at) VALUES(?,?,?)",(key,json.dumps(link),now))
    links.append(link)
c.commit();(p/"links.json").write_text(json.dumps(links,indent=2),encoding="utf-8");print(json.dumps({"links":len(links),"recorded_at":now}))
