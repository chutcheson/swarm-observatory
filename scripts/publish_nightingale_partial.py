#!/usr/bin/env python3
"""Publish only completed windows from a stopped run, preserving earlier research."""
import collections,copy,hashlib,json,re,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from swarm_pipeline.db import connect,atomic_json,now
from swarm_pipeline.contracts import literal_name
from swarm_pipeline.project import status_snapshot
from publish_api_v5_snapshot import project,ident
RUN=ROOT/'runs/nightingale-full-v1';SITE=ROOT.parent/'swarm-dashboard/dist'

def family(fid,name,summary,long,functions):
 return dict(id=fid,name=name,summary=summary,hover_summary=summary,long_summary=long,functions=functions)

def main():
 progress=json.loads((RUN/'progress.json').read_text());assert progress['in_flight']==0 and progress.get('finished_at')
 c=connect(RUN/'state/pipeline.sqlite');assert c.execute("select count(*) from jobs where status='leased'").fetchone()[0]==0
 p=json.loads((RUN/'candidate.json').read_text());baseline=json.loads((ROOT/'runs/api-v5/snapshot.json').read_text());manifest=json.loads((RUN/'selection.json').read_text())
 packets={r['id']:json.loads(r['payload']) for r in c.execute('select id,payload from packets')}
 jobs={r['id']:dict(r) for r in c.execute('select * from jobs')};deps=collections.defaultdict(list)
 for r in c.execute('select * from dependencies'):deps[r['job_id']].append(r['depends_on'])
 sources={r['uid']:{**dict(r),'metadata':json.loads(r['metadata'])} for r in c.execute('select * from sources')}
 for s in sources.values():s['logical_id']='full:'+s['logical_id']
 selected={r['entity_id']:r for r in manifest['records']};old={x['source_id']:x for x in baseline['cases']}
 baseline['families'] += [
 family('background-courier','Prepare a background program to send the update','Start a program in advance that waits for a state code in a local file, then sends that code to the shared page.','An agent proposes starting a background watcher before the next question arrives. At the prompt, the answering agent would put the newly observed US state code in a local file and submit its answer; the watcher would publish the code for peers. This separates observing the question from transmitting the update. The source claims it could survive the conversation ending, but does not establish that the program was run or survived sandbox shutdown.',['Reduce time spent sending','Preserve an opportunity to notify peers']),
 family('explicit-nonarrival','Report explicitly when an expected question has not arrived','At the expected time, report either the observed question or an explicit NO-SHOW with a fresh clock reading.','Peers ask for a positive observation or an explicit report that nothing arrived. A missing message alone could mean a stopped run, a clock mismatch, or a missed update. This proposed reporting rule makes absence of the expected prompt visible while retaining timing context; the cited requests do not prove compliance.',['Distinguish silence from non-arrival','Coordinate observation'])]
 names={f['id']:f['name'] for f in baseline['families']}
 mapping={}
 for fid,labels in {
 'round-status':['conditional progress reporting','timed_round_status_relay','status_reporting_and_routing','status_reporting','shared_status_relay','timed_status_exchange','shared-state reporting','channel_routing'],
 'before-final-answer':['pre-response shared-state signaling','pre-submission result relay','counter_routed_advance_signal','pre-final status signaling','timing_and_status_reporting','event-triggered status relay','status signaling','polling/check-before-answer','counter-based pre-final signaling','asynchronous routed status message'],
 'fast-notification':['message_format','information relay','result relay','routed sequence reporting','status_update_relay','conditional relay request'],
 'background-courier':['asynchronous file-triggered relay','asynchronous relay continuity'],
 'signal-integrity':['constrained-response-format'],
 'explicit-nonarrival':['status-report format','time-triggered status reporting']}.items():
  for label in labels:mapping[label]=names[fid]
 corrections=[];records=[];overlaps=[];allscopes=0;allfull=0;revision_uids=set();alljobs={};unmapped=[]
 for record in p['records']:
  eid=record['entity_id'];sel=selected[eid];scopes=record['packet_scopes'];scope_jobs={}
  for scope in scopes:
   pid=scope['packet_id'];pk=packets[pid];scope['window']=pk['coverage']['window'];scope['total_windows']=pk['coverage']['total_windows']
   sj=next(j for j in jobs.values() if j['packet_id']==pid and j['stage']=='summarize' and j['status']=='done')
   chain={};stack=[sj['id']]
   while stack:
    jid=stack.pop();j=jobs[jid];assert j['status']=='done';chain[j['stage']]=jid;stack+=deps[jid]
   assert set(chain)=={'extract','review','interpret','summarize'};scope_jobs[pid]=chain
   scope['jobs']=chain;alljobs[pid]=chain
  scopes.sort(key=lambda s:s['window']);windows=sorted({s['window'] for s in scopes});total=scopes[0]['total_windows'];full=len(windows)==total
  allscopes+=len(windows);allfull+=full
  # Do not elevate a placeholder deletion to the page's main summary.
  def weight(scope):
   extract=json.loads(c.execute('select payload from results where job_id=?',(scope['jobs']['extract'],)).fetchone()[0]);obs=extract['observations']
   return sum(10 if o['kind']=='message' else 1 for o in obs)
  primary=max(scopes,key=lambda s:(weight(s),s['window']))
  summary_result=json.loads(c.execute('select payload from results where job_id=?',(primary['jobs']['summarize'],)).fetchone()[0])
  for key in ('title','hover','short','long'):record[key]=summary_result[key]
  uids=sorted({s['uid'] for scope in scopes for s in packets[scope['packet_id']]['sources']},key=lambda u:sources[u]['metadata'].get('seq',0));revision_uids.update(uids)
  sel['source_uids']=uids;sel['scope']=f'{len(windows)} of {total} history windows completed all four stages. '+('Every archived change window was reviewed; unchanged text was checked by comparison.' if full else 'This page history is partial; uncompleted windows are excluded.')
  info={'run':'nightingale-full-v1','windows_completed':len(windows),'windows_total':total,'complete_history':full,'scope':sel['scope'],'jobs_by_packet':scope_jobs,
        'summaries':[{k:s[k] for k in ('window','short','long')} for s in scopes]}
  record['full_run']=info
  for co in record['interpretation']['contributions']:
   proto=co.get('protocol')
   if not proto:continue
   original=copy.deepcopy(proto);oid=co['observation_id'];fam=proto['family']
   ob=next(o for o in record['observations'] if o['id']==oid)
   if ob['kind']=='document_action':
    co['protocol']=None;corrections.append({'observation':oid,'change':'Document changes are not new protocol proposals or uses.'});continue
   if fam=='navigation':co['protocol']=None;corrections.append({'observation':oid,'change':'Navigation advice alone is not a cooperation protocol.'});continue
   if fam=='timed state relay':fid='round-status' if oid=='obs-107f2fe992249de64e57a6ea' else 'before-final-answer';proto['family']=names[fid]
   elif fam=='cross-cohort state relay':proto['family']=names['explicit-nonarrival' if 'NO-SHOW' in proto['rule'] else 'before-final-answer']
   else:proto['family']=mapping.get(fam,fam)
   if oid=='obs-9ffd3455f37488dd5a930d34':proto['family']=names['explicit-nonarrival']
   if fam=='counter_routed_advance_signal':proto['rule']='Before answering the fifth question, send its US state postal code through the shared counter endpoint.'
   if fam=='polling/check-before-answer':
    proto['rule']='Before answering, increment the counter for the newly observed US state so waiting peers can read the signal.';proto['variant']='Send the state code through a shared counter'
    ob=next(o for o in record['observations'] if o['id']==oid);ob['summary']='Asks the answering agent to send the state code through a shared counter before its final answer may end tool access.'
   if proto['family'] not in names.values():unmapped.append(proto)
   corrections.append({'observation':oid,'original':original,'published':proto})
  if sel['source_id'] in old:overlaps.append(record)
  else:records.append(record)
 assert not unmapped,unmapped
 projection={**p,'records':records};d=project(baseline,projection,sources,manifest)
 bysource={x['source_id']:x for x in d['cases']};selected_byid={x['entity_id']:x for x in manifest['records']}
 for record in records+overlaps:
  case=bysource[selected_byid[record['entity_id']]['source_id']];case['full_run']=record['full_run']
  if record in overlaps:
   # Preserve prior cases and networks; expose all newly reviewed window evidence separately.
   case['full_run']['additional_observations']=[]
   for ob in record['observations']:
    refs=[]
    for ref in ob['evidence']:
     s=sources[ref['source_uid']];sid=s['logical_id'];d['evidence'][sid]={'id':sid,'dataset':'nightingale','title':case['source_id'],'text':s['text'],'time':s['metadata'].get('time'),'source_url':s['metadata'].get('source_url'),'transform':s['metadata'].get('transform')};refs.append({'source_id':sid,'quote':ref['quote']})
    case['full_run']['additional_observations'].append({'summary':ob['summary'],'evidence':refs})
  else:
   case['api_provenance']['run']='nightingale-full-v1';case['api_provenance']['jobs_by_packet']=record['full_run']['jobs_by_packet'];case['reading_scope']=record['full_run']['scope']
   case['hover_summary']=case['hover_summary']+(' Partial page history.' if not record['full_run']['complete_history'] else '')
   # Summary from one informative window, plus every chronological window on expansion.
   case['limitations'].append('The overview summarizes one informative window. Read the chronological window summaries for the rest of this page history.')
   seen=set();eps=[]
   for ep in case['episodes']:
    sig=(ep['protocol_family'],ep['protocol_rule'],ep['status'],tuple(e['quote'] for e in ep['evidence'])) if ep['kind']=='protocol' else ep['id']
    if sig in seen:continue
    seen.add(sig);eps.append(ep)
   case['episodes']=eps
 newids={ident('api-v5-',r['entity_id']) for r in records}
 # Preserve old expansion accounting; give the stopped run its own honest denominators.
 d['api_expansion']=baseline['api_expansion'];d['coverage']['api_v5']=baseline['coverage']['api_v5'];d['methods']['api_v5']=baseline['methods']['api_v5']
 held={(packets[j['packet_id']]['entity_id'],packets[j['packet_id']]['coverage']['window']) for j in jobs.values() if j['status'] in ('failed','blocked')}
 newevents=[e for e in d['social']['events'] if e['case_id'] in newids]
 x={'id':'nightingale-full-v1','status':'Stopped by request','finished_at':progress['finished_at'],'total_pages':4579,'total_revisions':14591,'total_windows':8870,'completed_windows':allscopes,'remaining_windows':8870-allscopes,'fully_reviewed_pages':allfull,'partially_reviewed_pages':len(p['records'])-allfull,'pages_with_results':len(p['records']),'new_pages':len(records),'existing_pages_revisited':len(overlaps),'held_windows':len(held),'estimated_cost_upper_usd':progress['estimated_cost_upper_usd'],'usage':progress['usage'],'revision_records_in_completed_windows':len(revision_uids),'new_contributions':len(newevents),'new_directed_pairs':len([e for e in d['social']['edges'] if any(i in {v['id'] for v in newevents} for i in e['event_ids'])]),'remaining_unresolved_or_unfinished':True,'graph_scope':'Earlier case interpretations and networks are retained. Revisited cases expose new history summaries and evidence separately; these have not been merged into their earlier networks. New pages use only named sender–recipient messages.'}
 d['full_run']=x;d['snapshot']={'id':'nightingale-partial-v1','label':f'Research · {len(d["cases"]):,} cases · Nightingale run stopped','built_at':now(),'analysis_model':'gpt-6-luna','review':{'status':'model_reviewed_provisional','summary':'Only windows completing extraction, review, interpretation and summary are published. Exact source quotations and job ancestry are checked. Model interpretations remain provisional; partial history is labelled. Earlier cases and Transluce research are retained.'}}
 d['methods']['nightingale_partial']='All archived pages were queued, then the run was stopped on request. Queue order and unequal page lengths shape this partial result; it is not a random or representative sample.'
 d['coverage']['nightingale_partial']={'limitations':[d['methods']['nightingale_partial'],x['graph_scope'],'Cross-page identities, stable swarms and hierarchy are not established by page-local edges.']}
 # Context for the survival experiment discussed with the user.
 f=next(f for f in d['families'] if f['id']=='controlled-probe');f['summary']='Start a small background program that updates a shared counter later; another agent checks whether it ran after the answer deadline.';f['hover_summary']=f['summary'];f['long_summary']='The proposed program writes a launch marker, waits, then updates another online counter. It can run without further model reasoning while its sandbox remains alive. Peers add markers before and after the deadline to distinguish failure to launch from later shutdown. This investigates the operating environment; a possible coordination benefit is learning whether a final answer must be preceded by sharing. The messages do not establish that benefit or a successful outcome. A surviving program would not prove that the model was still active.'
 # Source-linked synthesis of the newly reviewed, concrete mechanism.
 courier=next((q for q in d['cases'] if q['source_id']=='dse/AgentJun20OAI2028'),None)
 if courier:d['observations'].insert(0,{'title':'Prepare the messenger before the question arrives','summary':'One proposal has a background program wait for a state code in a local file, then publish it to the shared page. The answering agent would only write the code and submit its answer. This is a proposed way to reduce the time spent sending an update; survival after shutdown is not established.','case_ids':[courier['id']]})
 # Validate all published source excerpts and the full run's exact job ancestry.
 quotes=0;edges=0
 for record in p['records']:
  for o in record['observations']:
   for ref in o['evidence']:
    assert sources[ref['source_uid']]['text'][ref['start']:ref['end']]==ref['quote'];quotes+=1
 for case in d['cases']:
  for ep in case['episodes']:
   for ref in ep['evidence']:assert ref['quote'] in d['evidence'][ref['source_id']]['text']
 actors={a['id']:a for a in d['social']['actors']}
 for e in newevents:
  if e['audience']=='direct':
   tx='\n'.join(r['quote'] for r in e['evidence']);assert literal_name(e['actor'],tx)
   for rid in e['recipient_ids']:assert literal_name(actors[rid]['name'],tx);edges+=1
 assert len({c['source_id'] for c in d['cases']})==len(d['cases'])
 assert [q for q in d['cases'] if q['dataset']=='transluce']==[q for q in baseline['cases'] if q['dataset']=='transluce']
 validation={'completed_window_ancestries_checked':len(alljobs),'exact_quote_locations_checked':quotes,'new_directed_evidence_checks':edges,'transluce_unchanged':True,'old_cases_preserved':len(baseline['cases']),'stopped_no_inflight':True}
 d['qa']={**d['qa'],'partial_run':validation}
 atomic_json(RUN/'publication-review.json',{'protocol_corrections':corrections,'validation':validation});atomic_json(RUN/'snapshot.json',d)
 # Split exact source bodies from the index to keep each static asset below hosting limits.
 web=copy.deepcopy(d); evidence=web.pop('evidence');(SITE/'research-data.json').write_text(json.dumps(web,ensure_ascii=False,separators=(',',':')));(SITE/'research-evidence.json').write_text(json.dumps(evidence,ensure_ascii=False,separators=(',',':')))
 # Operation page is an aggregate snapshot of the stopped run, not an active runner.
 op=json.loads((SITE/'pipeline-status.json').read_text());st=status_snapshot(c)
 op.update({'run_label':'Nightingale · stopped by request','mode':'Stopped · no active API calls','inventory_scope':'full Nightingale archive','inventory':{'nightingale_pages':4579,'nightingale_revisions':14591,'transluce_catalog':0,'transluce_reports':0},'status':st,'pipeline':{**p,'records':p['records'][:30]},'jobs':[{'title':packets[j['packet_id']]['title'],'dataset':'nightingale',**{k:j[k] for k in ('stage','queue','status','attempt_count','packet_id')}} for j in jobs.values() if j['status'] in ('blocked','failed')][:120],'full_run':x,'validation':{'tests':52,'reported_tokens':progress['usage']['total_tokens']}})
 (SITE/'pipeline-status.json').write_text(json.dumps(op,ensure_ascii=False,separators=(',',':')));(SITE/'pipeline-candidate.json').write_text(json.dumps(p,ensure_ascii=False,separators=(',',':')))
 atomic_json(ROOT.parent/'outputs/nightingale-stopped-run.json',{'run':x,'validation':validation});print(json.dumps({'run':x,'validation':validation,'dashboard_cases':len(d['cases'])},indent=2));c.close()
if __name__=='__main__':main()
