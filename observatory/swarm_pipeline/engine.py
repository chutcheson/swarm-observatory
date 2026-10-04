"""Durable dependency queue with leases, review gates and targeted invalidation."""
import json,time,uuid
from .db import now,canonical,digest,transaction,setting,set_setting
from .contracts import STAGES,SCHEMAS,INSTRUCTIONS,VERSION,validate_result,InvalidResult

DEFAULT_CONFIG={'backend':'openai','max_output_tokens':8000,'model':'gpt-6-luna','reasoning':'high','contract_version':VERSION,'max_attempts':3,'lease_seconds':960,'max_packet_chars':40000}

def configure(c,config=None):
 cfg={**DEFAULT_CONFIG,**(config or {})}
 if cfg['backend'] not in ('openai','codex'):raise ValueError('Backend must be openai or codex')
 if not 256<=cfg['max_output_tokens']<=32000:raise ValueError('Output token cap must be 256–32000')
 cfg['prompt_hash']=digest(INSTRUCTIONS);cfg['schema_hash']=digest(SCHEMAS)
 h=digest(cfg);cfg['instructions']=INSTRUCTIONS;cfg['schemas']=SCHEMAS;set_setting(c,'config:'+h,cfg);set_setting(c,'active_config_hash',h);return h

def enqueue(c,packet_ids,queue='coverage',config_hash=None):
 if queue not in ['coverage','investigation']:raise ValueError('Unknown queue')
 h=config_hash or setting(c,'active_config_hash') or configure(c);cfg=setting(c,'config:'+h)
 created=[]
 with transaction(c):
  for pid in packet_ids:
   if not c.execute('SELECT 1 FROM packets WHERE id=?',(pid,)).fetchone():raise ValueError('Unknown packet '+pid)
   prev=None
   for stage in STAGES:
    jid='job-'+digest([pid,stage,h])[:24]
    cur=c.execute('INSERT OR IGNORE INTO jobs(id,stage,packet_id,queue,status,config_hash,max_attempts,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?)',(jid,stage,pid,queue,'ready',h,cfg['max_attempts'],now(),now()))
    if queue=='investigation':c.execute("UPDATE jobs SET queue='investigation' WHERE id=? AND status='ready'",(jid,))
    if prev:c.execute('INSERT OR IGNORE INTO dependencies VALUES(?,?)',(jid,prev))
    if cur.rowcount:created.append(jid)
    prev=jid
 return created

def _recover(c,stamp):
 rows=c.execute("SELECT * FROM jobs WHERE status='leased' AND lease_until<?",(stamp,)).fetchall()
 for j in rows:
  state='failed' if j['attempt_count']>=j['max_attempts'] else 'ready'
  c.execute('UPDATE jobs SET status=?,lease_token=NULL,lease_until=NULL,error=?,updated_at=? WHERE id=?',(state,'Worker lease expired',now(),j['id']))
  c.execute("UPDATE attempts SET status='expired',finished_at=?,error='Worker lease expired' WHERE job_id=? AND lease_token=? AND status='running'",(now(),j['id'],j['lease_token']))
 return len(rows)

def recover(c):
 with transaction(c):return _recover(c,time.time())

def claim(c,worker,queue=None,stage=None,job_id=None,lease_seconds=None):
 with transaction(c):
  stamp=time.time();_recover(c,stamp)
  query="SELECT j.* FROM jobs j WHERE j.status='ready' AND j.available_at<=? AND j.attempt_count<j.max_attempts AND NOT EXISTS (SELECT 1 FROM dependencies d LEFT JOIN jobs p ON p.id=d.depends_on WHERE d.job_id=j.id AND (p.id IS NULL OR p.status!='done'))";args=[stamp]
  active=setting(c,'active_config_hash')
  if active:query+=' AND j.config_hash=?';args.append(active)
  for col,val in [('queue',queue),('stage',stage),('id',job_id)]:
   if val:query+=' AND j.'+col+'=?';args.append(val)
  # Fair alternation prevents follow-up work from starving coverage.
  preferred='coverage' if setting(c,'last_queue')=='investigation' else 'investigation'
  query+=" ORDER BY CASE WHEN j.queue=? THEN 0 ELSE 1 END,j.created_at,j.id LIMIT 1";args.append(preferred)
  j=c.execute(query,args).fetchone()
  if not j:return None
  token=uuid.uuid4().hex;aid='attempt-'+uuid.uuid4().hex;cfg=setting(c,'config:'+j['config_hash'])
  c.execute("UPDATE jobs SET status='leased',attempt_count=attempt_count+1,lease_token=?,lease_until=?,updated_at=? WHERE id=?",(token,stamp+(lease_seconds or cfg['lease_seconds']),now(),j['id']))
  c.execute("INSERT INTO attempts(id,job_id,worker,lease_token,started_at,status) VALUES(?,?,?,?,?,'running')",(aid,j['id'],worker,token,now()))
  set_setting(c,'last_queue',j['queue'])
 return job_input(c,j['id'],token,aid)

def job_input(c,jid,lease_token=None,attempt_id=None):
 j=dict(c.execute('SELECT * FROM jobs WHERE id=?',(jid,)).fetchone());p=json.loads(c.execute('SELECT payload FROM packets WHERE id=?',(j['packet_id'],)).fetchone()[0])
 previous={}
 for r in c.execute('''WITH RECURSIVE ancestors(id) AS (SELECT depends_on FROM dependencies WHERE job_id=? UNION SELECT d.depends_on FROM dependencies d JOIN ancestors a ON d.job_id=a.id) SELECT j.stage,r.payload FROM ancestors a JOIN jobs j ON j.id=a.id JOIN results r ON r.job_id=j.id''',(jid,)):previous[r['stage']]=json.loads(r['payload'])
 cfg=setting(c,'config:'+j['config_hash'])
 links=[{'type':'page','id':p['entity_id'],'label':p['title']}]
 for o in previous.get('extract',{}).get('observations',[]):
  links.append({'type':'observation','id':o['id'],'label':o['summary'][:100]})
  for n in [o['actor'],*o['recipients']]:
   if n:links.append({'type':'agent','id':p['entity_id']+'#'+n,'label':n})
 for item in previous.get('interpret',{}).get('contributions',[]):
  if item['protocol']:links.append({'type':'protocol','id':item['protocol']['family'],'label':item['protocol']['family']})
 return {'job_id':jid,'attempt_id':attempt_id,'lease_token':lease_token,'stage':j['stage'],'config':cfg,'validation_feedback':j['error'],'packet':p,'previous':previous,'allowed_links':links,'instructions':cfg.get('instructions',INSTRUCTIONS)[j['stage']],'schema':cfg.get('schemas',SCHEMAS)[j['stage']]}

def _leased(c,jid,token):
 j=c.execute('SELECT * FROM jobs WHERE id=?',(jid,)).fetchone()
 if not j or j['status']!='leased' or j['lease_token']!=token or j['lease_until']<=time.time():raise ValueError('Lease no longer valid; stale worker output rejected')
 return j

def heartbeat(c,jid,token,seconds=960):
 with transaction(c):_leased(c,jid,token);c.execute('UPDATE jobs SET lease_until=? WHERE id=?',(time.time()+seconds,jid))

def ticket(c,jid,kind,payload):
 tid='ticket-'+digest([jid,kind,payload])[:24]
 c.execute("INSERT OR IGNORE INTO tickets(id,job_id,kind,status,payload,created_at) VALUES(?,?,?,'open',?,?)",(tid,jid,kind,canonical(payload),now()));return tid

def submit(c,jid,token,result,usage=None):
 inputs=job_input(c,jid);validate_result(inputs['stage'],result,inputs['packet'],inputs['previous'],inputs['allowed_links'],inputs['schema'])
 with transaction(c):
  j=_leased(c,jid,token);state='done'
  for req in result['context_requests']:ticket(c,jid,'context',req);state='blocked'
  if result['status']=='needs_context':state='blocked'
  if j['stage']=='review' and result['decision']!='approve':
   state='blocked';ticket(c,jid,'review',{'decision':result['decision'],'findings':result['findings'],'missing_observations':result['missing_observations']})
  c.execute('INSERT INTO results(job_id,content_hash,payload,created_at) VALUES(?,?,?,?)',(jid,digest(result),canonical(result),now()))
  c.execute('UPDATE jobs SET status=?,lease_token=NULL,lease_until=NULL,error=NULL,updated_at=? WHERE id=?',(state,now(),jid))
  c.execute('UPDATE attempts SET status=?,finished_at=?,output=?,usage=? WHERE job_id=? AND lease_token=?',(state,now(),canonical(result),canonical(usage) if usage else None,jid,token))
 return {'job_id':jid,'status':state,'content_hash':digest(result)}

def fail(c,jid,token,error,retryable=True,usage=None):
 with transaction(c):
  j=_leased(c,jid,token);state='ready' if retryable and j['attempt_count']<j['max_attempts'] else 'failed'
  c.execute('UPDATE jobs SET status=?,available_at=?,lease_token=NULL,lease_until=NULL,error=?,updated_at=? WHERE id=?',(state,time.time()+min(60,2**j['attempt_count']),str(error)[:3000],now(),jid))
  c.execute("UPDATE attempts SET status='failed',finished_at=?,usage=?,error=? WHERE job_id=? AND lease_token=?",(now(),canonical(usage) if usage else None,str(error)[:3000],jid,token))
  if state=='failed':ticket(c,jid,'failure',{'reason':str(error)[:1000]})
 return state

def invalidate(c,jid,reason):
 if not reason.strip():raise ValueError('Reason required')
 with transaction(c):
  rows=c.execute('''WITH RECURSIVE affected(id) AS (SELECT id FROM jobs WHERE id=? UNION SELECT d.job_id FROM dependencies d JOIN affected a ON d.depends_on=a.id) SELECT id FROM affected''',(jid,)).fetchall()
  if not rows:raise ValueError('Unknown job')
  for r in rows:
   c.execute("UPDATE attempts SET status='invalidated',finished_at=? WHERE job_id=? AND status='running'",(now(),r['id']))
   c.execute("UPDATE jobs SET status='stale',lease_token=NULL,lease_until=NULL,updated_at=? WHERE id=?",(now(),r['id']))
   c.execute("UPDATE tickets SET status='superseded' WHERE job_id=? AND status='open'",(r['id'],))
   c.execute('INSERT INTO invalidations VALUES(?,?,?,?)',('invalid-'+uuid.uuid4().hex,r['id'],reason,now()))
 return [r['id'] for r in rows]

def reprocess(c,jid,reason,extra_sources=None):
 # New packet/input revision; original jobs/results remain auditable.
 old=c.execute('SELECT * FROM jobs WHERE id=?',(jid,)).fetchone()
 if not old:raise ValueError('Unknown job')
 p=json.loads(c.execute('SELECT payload FROM packets WHERE id=?',(old['packet_id'],)).fetchone()[0]);p['revision_request']={'reason':reason,'prior_job_id':jid}
 if extra_sources:
  for uid in extra_sources:
   s=c.execute('SELECT * FROM sources WHERE uid=?',(uid,)).fetchone()
   if not s:raise ValueError('Unknown additional source')
   if uid not in {v['uid'] for v in p['sources']}:p['sources'].append({'uid':s['uid'],'logical_id':s['logical_id'],'text':s['text'],'metadata':json.loads(s['metadata'])});p.setdefault('context_source_uids',[]).append(uid)
 cfg=setting(c,'config:'+old['config_hash']);limit=cfg.get('max_packet_chars',40000)
 if sum(len(s['text']) for s in p['sources'])>limit:raise ValueError('Enriched packet exceeds context budget; split it before reprocessing')
 p.pop('id',None);h=digest(p);p['id']='packet-'+h[:24]
 c.execute('INSERT OR IGNORE INTO packets(id,entity_id,dataset,content_hash,payload,coverage,created_at) VALUES(?,?,?,?,?,?,?)',(p['id'],p['entity_id'],p['dataset'],h,canonical(p),canonical(p['coverage']),now()))
 # Restart affected stage only, preserve upstream reviewed work for interpretation/summary corrections.
 affected=invalidate(c,jid,reason)
 created=[];prev=None
 ancestors=c.execute('SELECT depends_on FROM dependencies WHERE job_id=?',(jid,)).fetchall()
 for r in ancestors:prev=r['depends_on']
 start=STAGES.index(old['stage'])
 with transaction(c):
  for stage in STAGES[start:]:
   key='job-'+digest([p['id'],stage,old['config_hash']])[:24]
   c.execute('INSERT OR IGNORE INTO jobs(id,stage,packet_id,queue,status,config_hash,max_attempts,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?)',(key,stage,p['id'],'investigation','ready',old['config_hash'],cfg['max_attempts'],now(),now()))
   if prev:c.execute('INSERT OR IGNORE INTO dependencies VALUES(?,?)',(key,prev))
   created.append(key);prev=key
  c.execute("UPDATE tickets SET status='resolved' WHERE job_id=? AND status='open'",(jid,))
 return {'invalidated':affected,'created':created,'packet_id':p['id']}
