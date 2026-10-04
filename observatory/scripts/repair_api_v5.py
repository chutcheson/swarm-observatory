#!/usr/bin/env python3
"""One bounded repair pass per entity, preserving every original attempt."""
import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from swarm_pipeline.db import connect,atomic_json
from swarm_pipeline import engine
RUN=ROOT/'runs/api-v5';c=connect(RUN/'state/pipeline.sqlite')
path=RUN/'repair-log.json';log=json.loads(path.read_text()) if path.exists() else []
seen={(x['entity_id'],x['stage']) for x in log}
rules=('Follow the original extraction contract: recipients must be named AGENTS, not destination pages, relays, links, or generic groups such as ahead runners. Direct communication requires BOTH an attributable author and literal named recipient supported in the quotes. If authorship is unknown, keep actor=null and audience=unknown/group even if a watcher is named. Do not infer the author from a revision writer or page name. Quote the entire local signature when needed; preserve literal question marks or other uncertainty. A reviewer suggestion is fallible: do not follow a suggestion that contradicts these rules or the supplied evidence. Separate reports from requests/commitments when consequential. A selected-case scope is not exhaustive census; prioritize material distinct information, not trivial rewordings. ')
for row in c.execute("SELECT j.*,p.entity_id,p.payload as packet_payload,r.payload as result_payload FROM jobs j JOIN packets p ON p.id=j.packet_id LEFT JOIN results r ON r.job_id=j.id WHERE j.status IN ('blocked','failed') ORDER BY j.created_at").fetchall():
 eid=row['entity_id'];stage=row['stage']
 if (eid,stage) in seen:continue
 packet=json.loads(row['packet_payload']);original=packet.get('revision_request',{}).get('reason','')
 if stage=='review':
  if any(x['entity_id']==eid and x.get('restart')=='extract' for x in log):continue
  job=c.execute('SELECT depends_on FROM dependencies WHERE job_id=?',(row['id'],)).fetchone()[0];restart='extract'
  reason=original+'\nSUPERVISED REPAIR\n'+rules+'Address material supported issues in this fallible review. Include missed task details only if actually in the packet: '+(row['result_payload'] or row['error'] or '')
 elif stage=='summarize':
  job=row['id'];restart=stage;reason=original+'\nSUPERVISED REPAIR\nWrite the requested plain-English summaries and evidence IDs. Return links=[]; the dashboard derives navigable agent, page, protocol and evidence links from the approved records. Do not invent link labels.'
 elif stage=='extract':
  job=row['id'];restart=stage;reason=original+'\nSUPERVISED REPAIR\n'+rules+'Prior validation issue: '+str(row['error'])
 else:continue
 result=engine.reprocess(c,job,reason);log.append({'entity_id':eid,'stage':stage,'restart':restart,'prior_job_id':job,'created':result['created']});seen.add((eid,stage));print(eid,stage,'->',restart,flush=True)
atomic_json(path,log);c.close()
