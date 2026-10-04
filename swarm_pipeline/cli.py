"""Command-line entrypoint. No model work occurs without explicit run/claim commands."""
import argparse,json,random,sys
from pathlib import Path
from .db import connect,canonical,atomic_json,setting,set_setting
from . import engine
ROOT=Path(__file__).resolve().parents[1]
DEFAULT_SOURCE=Path('/Users/campbellhutcheson/Projects/swarm-communication')
def show(x):print(json.dumps(x,ensure_ascii=False,indent=2))
def main(argv=None):
 p=argparse.ArgumentParser(prog='swarm-pipeline');p.add_argument('--state',type=Path,default=ROOT/'pipeline-state')
 sub=p.add_subparsers(dest='command',required=True)
 a=sub.add_parser('init');a.add_argument('--backend',choices=['openai','codex'],default='openai');a.add_argument('--api-key-file',type=Path,default=Path.home()/'.keys/openai');a.add_argument('--max-output-tokens',type=int,default=8000);a.add_argument('--model',default='gpt-6-luna');a.add_argument('--reasoning',default='high',choices=['low','medium','high'])
 a=sub.add_parser('ingest');a.add_argument('--source',type=Path,default=DEFAULT_SOURCE)
 a=sub.add_parser('packetize');a.add_argument('--entity',action='append');a.add_argument('--max-chars',type=int,default=40000)
 a=sub.add_parser('plan');a.add_argument('--coverage',type=int,default=12);a.add_argument('--investigation',type=int,default=0);a.add_argument('--seed',type=int,default=20261004);a.add_argument('--entity',action='append')
 a=sub.add_parser('enqueue');a.add_argument('packet_ids',nargs='+');a.add_argument('--queue',choices=['coverage','investigation'],default='coverage')
 a=sub.add_parser('claim');a.add_argument('--worker',required=True);a.add_argument('--stage');a.add_argument('--queue');a.add_argument('--job');a.add_argument('--output',type=Path,required=True)
 a=sub.add_parser('submit');a.add_argument('--job-file',type=Path,required=True);a.add_argument('--result',type=Path,required=True);a.add_argument('--usage',type=Path)
 a=sub.add_parser('run');a.add_argument('--max-jobs',type=int,default=4);a.add_argument('--max-seconds',type=int,default=1800);a.add_argument('--max-tokens',type=int,default=100000);a.add_argument('--concurrency',type=int,default=1);a.add_argument('--queue');a.add_argument('--stage');a.add_argument('--codex',default='codex');a.add_argument('--api-key-file',type=Path)
 a=sub.add_parser('invalidate');a.add_argument('job_id');a.add_argument('--reason',required=True)
 a=sub.add_parser('reprocess');a.add_argument('job_id');a.add_argument('--reason',required=True);a.add_argument('--source-uid',action='append')
 a=sub.add_parser('resolve-context');a.add_argument('ticket_id');a.add_argument('--source-uid',action='append',required=True);a.add_argument('--reason',required=True)
 a=sub.add_parser('dashboard');a.add_argument('--output',type=Path,required=True);a.add_argument('--tests',type=int,default=0)
 a=sub.add_parser('status');a.add_argument('--output',type=Path)
 a=sub.add_parser('inspect');a.add_argument('job_id')
 a=sub.add_parser('recover')
 a=sub.add_parser('export');a.add_argument('--output',type=Path,required=True);a.add_argument('--baseline',type=Path)
 a=sub.add_parser('search');a.add_argument('query');a.add_argument('--limit',type=int,default=15)
 args=p.parse_args(argv);args.state=args.state.resolve();db=args.state/'pipeline.sqlite';c=connect(db)
 try:
  if args.command=='init':
   if args.backend=='openai':set_setting(c,'api_key_file',str(args.api_key_file.expanduser().resolve()))
   show({'database':str(db),'backend':args.backend,'model':args.model,'config_hash':engine.configure(c,{'backend':args.backend,'model':args.model,'reasoning':args.reasoning,'max_output_tokens':args.max_output_tokens})})
  elif args.command=='ingest':
   from .ingest import ingest
   show(ingest(c,args.source,ROOT/'runs'/'network-v4'))
  elif args.command=='packetize':
   from .packets import prepare_packets
   if not 2000<=args.max_chars<=80000:raise ValueError('Packet character budget must be 2000–80000')
   show(prepare_packets(c,args.entity,args.max_chars))
  elif args.command=='plan':
   if args.coverage<0 or args.investigation<0 or args.coverage+args.investigation>1000:raise ValueError('Plan between 0 and 1000 packets per invocation')
   active=setting(c,'active_config_hash') or engine.configure(c)
   rows=c.execute("SELECT id,entity_id,payload FROM packets p WHERE NOT EXISTS(SELECT 1 FROM jobs j WHERE j.packet_id=p.id AND j.config_hash=?)",(active,)).fetchall()
   if args.entity:rows=[r for r in rows if r['entity_id'] in args.entity]
   # Stable random coverage sample; follow-up lane prioritizes linked/contextual records.
   rows=sorted(rows,key=lambda r:r['id']);random.Random(args.seed).shuffle(rows)
   cov=rows[:args.coverage];remaining=rows[args.coverage:]
   investigated=sorted(remaining,key=lambda r:(-len(json.loads(r['payload']).get('links',[])),r['id']))[:args.investigation]
   ids=engine.enqueue(c,[r['id'] for r in cov],'coverage')+engine.enqueue(c,[r['id'] for r in investigated],'investigation')
   manifest={'seed':args.seed,'coverage_packets':[r['id'] for r in cov],'investigation_packets':[r['id'] for r in investigated],'jobs_created':len(ids),'note':'Coverage is a seeded packet sample; investigation favors linked context. This is not a prevalence estimator.'};atomic_json(args.state/'last-plan.json',manifest);show(manifest)
  elif args.command=='enqueue':show({'created':engine.enqueue(c,args.packet_ids,args.queue)})
  elif args.command=='claim':
   from .worker import export_job
   job=engine.claim(c,args.worker,args.queue,args.stage,args.job)
   if job:export_job(job,args.output);show({'job_id':job['job_id'],'stage':job['stage'],'directory':str(args.output.resolve())})
   else:show({'status':'idle'})
  elif args.command=='submit':
   j=json.loads(args.job_file.read_text());r=json.loads(args.result.read_text());u=json.loads(args.usage.read_text()) if args.usage else None
   show(engine.submit(c,j['job_id'],j['lease_token'],r,u))
  elif args.command=='run':
   from .worker import run
   c.close();c=None
   show(run(db,args.state,args.max_jobs,args.max_seconds,args.max_tokens,args.concurrency,args.queue,args.stage,args.codex,on_result=lambda r:print(canonical(r),flush=True),key_file=args.api_key_file))
  elif args.command=='invalidate':show({'invalidated':engine.invalidate(c,args.job_id,args.reason)})
  elif args.command=='reprocess':show(engine.reprocess(c,args.job_id,args.reason,args.source_uid))
  elif args.command=='resolve-context':
   ticket=c.execute("SELECT * FROM tickets WHERE id=? AND status='open'",(args.ticket_id,)).fetchone()
   if not ticket:raise ValueError('Open ticket not found')
   jid=ticket['job_id'];j=c.execute('SELECT stage FROM jobs WHERE id=?',(jid,)).fetchone()
   if j['stage']=='review':
    row=c.execute("SELECT d.depends_on FROM dependencies d JOIN jobs j ON j.id=d.depends_on WHERE d.job_id=? AND j.stage='extract'",(jid,)).fetchone();jid=row[0]
   answer=engine.reprocess(c,jid,args.reason,args.source_uid);c.execute("UPDATE tickets SET status='resolved' WHERE id=?",(args.ticket_id,));show(answer)
  elif args.command=='dashboard':
   from .project import build_projection,status_snapshot
   state=status_snapshot(c);projection=build_projection(c)['pipeline']
   inventory={
    'nightingale_pages':c.execute("SELECT count(*) FROM entities WHERE dataset='nightingale'").fetchone()[0],
    'nightingale_revisions':c.execute("SELECT count(*) FROM sources WHERE dataset='nightingale' AND kind='revision'").fetchone()[0],
    'transluce_catalog':c.execute("SELECT count(*) FROM entities WHERE dataset='transluce'").fetchone()[0],
    'transluce_reports':c.execute("SELECT count(*) FROM sources WHERE kind='normalized_report'").fetchone()[0]}
   jobs=[dict(r) for r in c.execute('SELECT j.id,j.stage,j.status,j.queue,j.attempt_count,j.packet_id,p.dataset,e.title FROM jobs j JOIN packets p ON p.id=j.packet_id JOIN entities e ON e.id=p.entity_id WHERE j.config_hash=? ORDER BY j.created_at,j.id',(setting(c,'active_config_hash'),))]
   usages=[json.loads(r[0]) for r in c.execute('SELECT a.usage FROM attempts a JOIN jobs j ON j.id=a.job_id WHERE a.usage IS NOT NULL AND j.config_hash=?',(setting(c,'active_config_hash'),))]
   tokens=sum(u.get('input_tokens',0)+u.get('output_tokens',0) for u in usages)
   backend=setting(c,'config:'+setting(c,'active_config_hash'),{}).get('backend','codex')
   data={'mode':('OpenAI API' if backend=='openai' else 'Codex CLI')+' workers · exported snapshot','status':state,'pipeline':projection,'inventory':inventory,'jobs':jobs,'validation':{'tests':args.tests,'reported_tokens':tokens}}
   atomic_json(args.output,data);atomic_json(args.output.with_name('pipeline-candidate.json'),{'pipeline':projection});show({'status_path':str(args.output),'candidate_records':len(projection['records'])})
  elif args.command=='status':
   from .project import status_snapshot
   s=status_snapshot(c)
   if args.output:atomic_json(args.output,s)
   show(s)
  elif args.command=='inspect':show(engine.job_input(c,args.job_id))
  elif args.command=='recover':show({'recovered_leases':engine.recover(c)})
  elif args.command=='export':
   from .project import export_projection
   show(export_projection(c,args.output,args.baseline))
  elif args.command=='search':
   rows=c.execute('SELECT id,dataset,title FROM entities WHERE title LIKE ? OR id LIKE ? ORDER BY id LIMIT ?',('%'+args.query+'%','%'+args.query+'%',args.limit)).fetchall();show([dict(r) for r in rows])
 except (ValueError,KeyError) as exc:print('Error: '+str(exc),file=sys.stderr);return 2
 finally:
  if c:c.close()
 return 0
if __name__=='__main__':raise SystemExit(main())
