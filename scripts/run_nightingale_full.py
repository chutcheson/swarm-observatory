#!/usr/bin/env python3
"""Resumable 32-worker API supervisor; one bounded quality repair per window."""
import argparse, collections, concurrent.futures, json, os, sys, time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from swarm_pipeline.db import connect, atomic_json, now, setting
from swarm_pipeline.worker import run_once
from swarm_pipeline import engine
RUN=ROOT/'runs/nightingale-full-v1';DB=RUN/'state/pipeline.sqlite'
def cost(u):
 return ((u.get('input_tokens',0)-u.get('cached_input_tokens',0))*.125+u.get('cached_input_tokens',0)*.01+u.get('output_tokens',0)*.5)/1e6
def stats(c):
 usage=collections.Counter()
 for r in c.execute('SELECT usage FROM attempts WHERE usage IS NOT NULL'):usage.update(json.loads(r[0]))
 counts={s:n for s,n in c.execute('SELECT status,count(*) FROM jobs GROUP BY status')}
 stage={}
 for s,status,n in c.execute("SELECT stage,status,count(*) FROM jobs WHERE status!='stale' GROUP BY stage,status"):stage.setdefault(s,{})[status]=n
 return {'updated_at':now(),'pid':os.getpid(),'workers':32,'counts':counts,'stages':stage,'usage':dict(usage),'estimated_cost_upper_usd':round(cost(usage),6),'pages_with_completed_windows':c.execute("SELECT count(distinct p.entity_id) FROM jobs j JOIN packets p ON p.id=j.packet_id WHERE j.stage='summarize' AND j.status='done'").fetchone()[0],'completed_windows':stage.get('summarize',{}).get('done',0),'attempted_pages':c.execute('SELECT count(distinct p.entity_id) FROM attempts a JOIN jobs j ON j.id=a.job_id JOIN packets p ON p.id=j.packet_id').fetchone()[0]}
def repair(c):
 logpath=RUN/'repairs.json';log=json.loads(logpath.read_text()) if logpath.exists() else [];seen={(x['entity_id'],x['window'],x['restart']) for x in log};n=0
 rows=c.execute("SELECT j.*,p.entity_id,p.payload as packet_payload,r.payload as result_payload FROM jobs j JOIN packets p ON p.id=j.packet_id LEFT JOIN results r ON r.job_id=j.id WHERE j.status IN ('blocked','failed')").fetchall()
 for row in rows:
  stage=row['stage'];p=json.loads(row['packet_payload']);window=p['coverage']['window']
  if stage=='review':
   restart='extract';jid=c.execute('SELECT depends_on FROM dependencies WHERE job_id=?',(row['id'],)).fetchone()[0]
  elif stage in ('extract','summarize'):restart=stage;jid=row['id']
  else:continue
  key=(row['entity_id'],window,restart)
  if key in seen:continue
  reason=p.get('revision_request',{}).get('reason','')+'\nBOUNDED CORRECTION: Fix the material, source-supported issue below. Preserve exact quotes, focus boundaries and unknown identities. Review feedback is fallible; do not invent evidence to comply. Return links=[] in summaries. '+str(row['result_payload'] or row['error'] or '')
  result=engine.reprocess(c,jid,reason);log.append({'entity_id':key[0],'window':window,'restart':restart,'prior_job_id':jid,'created':result['created']});seen.add(key);n+=1
 if n:atomic_json(logpath,log)
 return n
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--workers',type=int,default=32);ap.add_argument('--max-dollars',type=float,default=100);ap.add_argument('--max-seconds',type=int,default=43200);ap.add_argument('--max-attempts',type=int,default=100000);args=ap.parse_args()
 if not 1<=args.workers<=64:raise ValueError('Use 1–64 workers')
 RUN.mkdir(exist_ok=True);c=connect(DB);started=time.monotonic();done=0;pending=set();stop=None;last_report=0;unknown=0
 engine.recover(c)
 with (RUN/'progress.jsonl').open('a') as stream, concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
  while True:
   if time.monotonic()-last_report>=15:
    s=stats(c);s.update({'workers':args.workers,'in_flight':len(pending),'stop_reason':stop,'cost_cap_usd':args.max_dollars});atomic_json(RUN/'progress.json',s);stream.write(json.dumps(s)+'\n');stream.flush();last_report=time.monotonic()
    if s['estimated_cost_upper_usd']>=args.max_dollars:stop='cost ceiling reached'
    if time.monotonic()-started>=args.max_seconds:stop='time ceiling reached'
    if (RUN/'STOP').exists():stop='stop file requested'
    if not stop:repair(c)
   if done>=args.max_attempts:stop='attempt ceiling reached'
   if not stop:
    count=c.execute("SELECT count(*) FROM jobs j WHERE j.status='ready' AND j.available_at<=? AND NOT EXISTS (SELECT 1 FROM dependencies d JOIN jobs p ON p.id=d.depends_on WHERE d.job_id=j.id AND p.status!='done')",(time.time(),)).fetchone()[0]
    for _ in range(min(args.workers-len(pending),count)):
     pending.add(pool.submit(run_once,DB,RUN/'state',worker='full-corpus-api',timeout=600))
   if not pending:
    if stop:break
    if repair(c):continue
    next_ready=c.execute("SELECT min(j.available_at) FROM jobs j WHERE j.status='ready' AND NOT EXISTS (SELECT 1 FROM dependencies d JOIN jobs p ON p.id=d.depends_on WHERE d.job_id=j.id AND p.status!='done')").fetchone()[0]
    if next_ready is not None:
     time.sleep(min(5,max(.2,next_ready-time.time())));continue
    stop='all runnable windows completed; unresolved cases held';break
   finished,pending=concurrent.futures.wait(pending,timeout=2,return_when=concurrent.futures.FIRST_COMPLETED)
   for f in finished:
    try:r=f.result()
    except Exception as exc:stop='supervisor worker exception: '+type(exc).__name__;continue
    if r['status']=='idle':continue
    done+=1
    stream.write(json.dumps({'at':now(),**r})+'\n');stream.flush()
    if r.get('fatal'):stop='API authentication, quota or configuration failure'
    if not r.get('usage'):
     if 'HTTP 429' in r.get('error',''):
      # The rejected request generated no reported model tokens. Back off the
      # shared dispatcher; the durable queue retains bounded per-job retries.
      time.sleep(5)
     elif 'Prompt exceeds' not in r.get('error',''):unknown+=1
    if unknown>=3:stop='repeated calls without usage receipts; inspect before continuing'
  s=stats(c);s.update({'workers':args.workers,'in_flight':0,'stop_reason':stop,'cost_cap_usd':args.max_dollars,'finished_at':now()});atomic_json(RUN/'progress.json',s);print(json.dumps(s),flush=True)
 c.close()
if __name__=='__main__':main()
