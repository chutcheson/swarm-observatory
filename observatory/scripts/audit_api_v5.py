#!/usr/bin/env python3
"""Validate the actual publishable snapshot and retain complete call accounting."""
import collections,json,re,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from swarm_pipeline.db import connect,atomic_json
from swarm_pipeline.contracts import literal_name
RUN=ROOT/'runs/api-v5';c=connect(RUN/'state/pipeline.sqlite');reconciled=0
for path in (RUN/'state/attempts').glob('*/receipt.json'):
 r=json.loads(path.read_text());usage=r.get('usage')
 if usage:
  cur=c.execute('UPDATE attempts SET usage=? WHERE id=? AND usage IS NULL',(json.dumps(usage),path.parent.name));reconciled+=cur.rowcount
baseline=json.loads((ROOT/'runs/network-v4/snapshot.json').read_text());d=json.loads((RUN/'snapshot.json').read_text());new=[x for x in d['cases'] if x.get('api_provenance')];bycase={x['id']:x for x in d['cases']};actors={x['id']:x for x in d['social']['actors']};events={x['id']:x for x in d['social']['events']}
for old in baseline['cases']:assert bycase[old['id']]==old,old['id']
assert len(bycase)==len(d['cases']);assert len({(x['dataset'],x['source_id']) for x in d['cases']})==len(d['cases'])
quotes=0;links=0
for case in new:
 for ep in case['episodes']:
  for e in ep['evidence']:assert e['quote'] and e['quote'] in d['evidence'][e['source_id']]['text'];quotes+=1
 for stage,jid in case['api_provenance']['jobs'].items():
  j=c.execute('SELECT stage,status FROM jobs WHERE id=?',(jid,)).fetchone();assert tuple(j)==(stage,'done'),jid
for e in d['social']['events']:
 if not e['id'].startswith('event-'):continue
 if e['audience']=='direct':
  assert e['actor_id'] in actors and e['recipient_ids'];text='\n'.join(q['quote'] for q in e['evidence'])
  assert literal_name(e['actor'],text)
  for rid in e['recipient_ids']:assert rid in actors and rid!=e['actor_id'];assert literal_name(actors[rid]['name'],text)
for edge in d['social']['edges']:
 if not edge['id'].startswith('edge-api-'):continue
 for eid in edge['event_ids']:
  e=events[eid];assert e['actor_id']==edge['source'] and edge['target'] in e['recipient_ids'];assert bycase[e['case_id']]['dataset']=='nightingale';links+=1
usage=collections.Counter()
for row in c.execute('SELECT usage FROM attempts WHERE usage IS NOT NULL'):usage.update(json.loads(row[0]))
unknown=c.execute("SELECT count(*) FROM attempts WHERE usage IS NULL AND status NOT IN ('running','invalidated')").fetchone()[0]
report={'baseline_cases_unchanged':len(baseline['cases']),'new_cases':len(new),'new_exact_quotes':quotes,'new_directed_edge_evidence_checks':links,'all_source_and_graph_checks_passed':True,'usage':dict(usage),'attempts_without_usage':unknown,'reconciled_stale_attempts':reconciled,'note':'Exact quotes and graph provenance checked; model interpretations remain provisional.'}
atomic_json(RUN/'validation.json',report);print(json.dumps(report,indent=2));c.close()
