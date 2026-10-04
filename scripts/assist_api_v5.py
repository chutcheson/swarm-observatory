#!/usr/bin/env python3
"""Add bounded workers to the same durable queue; enforce shared usage ceiling."""
import concurrent.futures,json,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from swarm_pipeline.db import connect
from swarm_pipeline.worker import run_once
RUN=ROOT/'runs/api-v5/state';DB=RUN/'pipeline.sqlite'
def work(n):
 deadline=time.monotonic()+3600
 for _ in range(150):
  if time.monotonic()>deadline:return
  c=connect(DB)
  used=sum(json.loads(r[0]).get('total_tokens',0) for r in c.execute('SELECT usage FROM attempts WHERE usage IS NOT NULL'));c.close()
  if used>=5000000:return
  result=run_once(DB,RUN,worker=f'api-v5-assist-{n}')
  print(json.dumps(result),flush=True)
  if result.get('status')=='idle' or result.get('fatal') or result.get('usage_unknown'):return
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:list(pool.map(work,range(3)))
