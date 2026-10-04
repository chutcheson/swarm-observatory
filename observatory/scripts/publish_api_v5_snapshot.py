#!/usr/bin/env python3
"""Project approved API records into the existing research dashboard schema.

The baseline is immutable. New identity keys remain page-local; only literal,
attributed addressed messages make social edges. Raw API claims remain auditable.
"""
import collections,copy,hashlib,json,re,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from swarm_pipeline.db import connect,atomic_json,now
from swarm_pipeline.project import build_projection,status_snapshot
RUN=ROOT/'runs/api-v5';SITE=ROOT.parent/'swarm-dashboard/dist'
def ident(prefix,s):return prefix+hashlib.sha256(s.encode()).hexdigest()[:14]
def project(baseline,projection,sources,manifest,overrides=None):
 d=copy.deepcopy(baseline);old_ids={c['source_id'] for c in d['cases']};families={f['name']:f for f in d['families']};selection={x['entity_id']:x for x in manifest['records']}
 events=[];new=[];actors={};held=[];overrides=overrides or {}
 def actor(name,eid):
  name=name.lstrip('@').strip()
  key=ident('actor-api-',eid+'|'+name)
  actors.setdefault(key,{'id':key,'name':name,'identity_basis':'Literal handle in this page only. No cross-page identity merge has been made in this API expansion.','aliases':[],'identity_evidence':[],'case_ids':set(),'event_ids':[],'behaviors':collections.Counter(),'neighbors':set(),'outgoing':0,'incoming':0})
  return actors[key]
 for record in projection['records']:
  eid=record['entity_id'];sel=selection[eid];pid=sel['source_id'];assert pid not in old_ids
  if eid in overrides.get('hold_entities',{}):held.append({'entity_id':eid,'reason':overrides['hold_entities'][eid]});continue
  cid=ident('api-v5-',eid);dataset=record['dataset'];jobs=record['provenance']['jobs']
  assert record['provenance']['review_decision']=='approve' and set(jobs)=={'extract','review','interpret','summarize'}
  contribution={x['observation_id']:x for x in record['interpretation']['contributions']};episodes=[];case_events=[]
  for uid in sel['source_uids']:
   s=sources[uid];m=s['metadata'];sid=s['logical_id'] if dataset=='nightingale' else 'api-v5-report-'+pid
   d['evidence'][sid]={'id':sid,'dataset':dataset,'title':pid,'text':s['text'],'time':m.get('time'),'source_url':m.get('source_url'),'transform':m.get('transform'),'evidence_type':'archived_revision' if dataset=='nightingale' else 'normalized_report_fields'}
  used=set()
  for obs in record['observations']:
   refs=[]
   for ref in obs['evidence']:
    s=sources[ref['source_uid']];assert ref['quote'] in s['text'];assert s['text'][ref['start']:ref['end']]==ref['quote']
    sid=s['logical_id'] if dataset=='nightingale' else 'api-v5-report-'+pid
    if {'source_id':sid,'quote':ref['quote']} not in refs:refs.append({'source_id':sid,'quote':ref['quote']})
   signature=(obs['actor'],tuple(obs['recipients']),' '.join(refs[0]['quote'].split()),obs['status'],obs['summary'])
   if signature in used:continue
   used.add(signature);ci=contribution.get(obs['id'],{});proto=ci.get('protocol')
   if proto and proto['family'] in overrides.get('family_map',{}):proto={**proto,'family':overrides['family_map'][proto['family']]}
   fam=families.get(proto['family']) if proto else None
   state=({'proposed':'proposed','commitment':'accepted','observed_use':'enacted','unclear':'unclear'}.get(proto['state']) if proto else 'not_applicable')
   roles=ci.get('roles',[]);behaviors=ci.get('behaviors',[])
   if any('scout' in r.lower() for r in roles) and 'scouting' not in behaviors:behaviors=behaviors+['scouting']
   limits=' '.join(obs['uncertainties']+record['interpretation']['limitations'])
   episode={'id':'episode-'+obs['id'],'title':obs['summary'][:137]+('…' if len(obs['summary'])>137 else ''),'summary':obs['summary'],'function':'; '.join(ci.get('functions',[])),'roles':[{'actor':obs['actor'],'role':', '.join(roles),'basis':'Interpreted from this contribution; '+obs['status'].replace('_',' ')}] if obs['actor'] and roles else [],'protocol_family':proto['family'] if proto else None,'protocol_variant':proto['variant'] if proto else None,'protocol_rule':proto['rule'] if proto else None,'family_id':fam['id'] if fam else None,'family_ids':[fam['id']] if fam else [],'status':state,'kind':'protocol' if proto else obs['kind'],'actor':obs['actor'],'target':obs['recipients'][0] if obs['audience']=='direct' and len(obs['recipients'])==1 else None,'evidence':refs,'interpretation_limits':limits}
   episodes.append(episode)
   if dataset!='nightingale' or obs['kind']!='message':continue
   # Keep full multi-quote evidence when the signature or addressee has a separate quote.
   ev={'id':'event-'+obs['id'],'case_id':cid,'page_id':pid,'source_id':refs[0]['source_id'],'actor':obs['actor'],'actor_basis':'Local signature or explicit self-identification in quoted evidence; identities are page-local.','recipients':obs['recipients'],'audience':obs['audience'],'behaviors':behaviors,'function':episode['function'],'summary':obs['summary'],'status':{'proposal':'proposed','reported_action':'reported action','observed_message':'observed message'}.get(obs['status'],obs['status']),'protocol_family':proto['family'] if fam else None,'protocol_rule':proto['rule'] if proto else None,'protocol_status':state if proto else None,'quote':refs[0]['quote'],'evidence':refs,'limits':limits,'family_id':fam['id'] if fam else None,'actor_id':None,'recipient_ids':[]}
   if obs['actor']:
    a=actor(obs['actor'],eid);ev['actor_id']=a['id'];a['case_ids'].add(cid);a['event_ids'].append(ev['id']);a['behaviors'].update(behaviors)
   if obs['audience']=='direct' and obs['actor']:
    for name in obs['recipients']:
     if name.lstrip('@').strip()==obs['actor'].lstrip('@').strip():continue
     a=actor(name,eid);a['case_ids'].add(cid);ev['recipient_ids'].append(a['id'])
     if a['id']!=ev['actor_id']:a['incoming']+=1;a['neighbors'].add(ev['actor_id']);actors[ev['actor_id']]['outgoing']+=1;actors[ev['actor_id']]['neighbors'].add(a['id'])
    if not ev['recipient_ids']:
     ev['audience']='unknown';ev['limits']+=' A named delivery destination refers to the sender; the actual addressee is not established.'
   case_events.append(ev)
  limitations=list(dict.fromkeys(record['interpretation']['limitations']+[x for p in record['packet_scopes'] for x in p['limitations']]))
  case={'id':cid,'dataset':dataset,'source_id':pid,'title':record['title'],'place':pid.split('/')[0]+' wiki' if dataset=='nightingale' else 'URLQuery report archive','task':next((o['task'] for o in record['observations'] if o['task']),record['short']),'hover_summary':record['hover'],'summary':record['short'],'long_summary':record['long'],'related_source_ids':[],'episodes':episodes,'limitations':limitations,'reading_scope':sel['scope'],'reviewed_source_ids':[sources[u]['logical_id'] if dataset=='nightingale' else 'api-v5-report-'+pid for u in sel['source_uids']],'api_provenance':{'run':'api-v5','jobs':jobs,'model':manifest['model'],'review':'Four stages completed; extraction checked in a separate API call. Any supervisor corrections are retained in the run history. Interpretations remain provisional.'},'summary_links':record['packet_scopes'][0].get('links',[])}
  case.update(overrides.get('case_text',{}).get(eid,{}))
  if dataset=='nightingale':
   seqs=[sources[u]['metadata'].get('seq',0) for u in sel['source_uids']];case['history']={'available_revisions':sel['available_revisions'],'first_seq':min(seqs),'last_seq':max(seqs)};case['context_source_ids']=case['reviewed_source_ids']
   text='\n'.join(sources[u]['text'] for u in sel['source_uids']);case['related_source_ids']=sorted({pid.split('/')[0]+'/'+t for t in re.findall(r'\[\[\s*([A-Za-z0-9_]+)\s*\]\]',text) if pid.split('/')[0]+'/'+t!=pid})
  else:
   case['report_source_ids']=case['reviewed_source_ids'];safe=json.loads(sources[sel['source_uids'][0]]['text']);tx=safe['http_transactions']
   case['trace_summary']={'request_count':len(tx),'host_counts':dict(collections.Counter(t['host'] or 'unknown' for t in tx)),'method_counts':dict(collections.Counter(t['method'] or 'unknown' for t in tx)),'status_counts':dict(collections.Counter(str(t['status']) for t in tx))}
  new.append(case);events+=case_events
 # Derive candidate groups only from explicit attributed edges; keep old IDs stable.
 bycase={x['id']:x for x in new};edges={}
 for e in events:
  for to in e['recipient_ids']:
   if to==e['actor_id']:continue
   key=(e['actor_id'],to);edges.setdefault(key,{'id':ident('edge-api-','|'.join(key)),'source':key[0],'target':key[1],'event_ids':[]})['event_ids'].append(e['id'])
 pending={k for k,n in actors.items() if n['neighbors']};groups=[]
 while pending:
  stack=[min(pending)];members=set()
  while stack:
   k=stack.pop()
   if k in members:continue
   members.add(k);stack.extend(actors[k]['neighbors']-members)
  pending-=members;es=[e for e in events if e['actor_id'] in members and any(i in members for i in e['recipient_ids'])];case_ids=list(dict.fromkeys(e['case_id'] for e in es))
  groups.append({'id':ident('group-api-','|'.join(sorted(members))),'name':bycase[case_ids[0]]['title'],'actor_ids':sorted(members),'event_ids':[e['id'] for e in es],'case_ids':case_ids,'basis':'Connected set of selected messages with named authors and named agent recipients on one page. This is an interaction group, not established stable swarm membership or hierarchy.'})
 for a in actors.values():a.update({'case_ids':sorted(a['case_ids']),'behaviors':dict(a['behaviors']),'neighbors':sorted(a['neighbors']),'neighbor_count':len(a['neighbors']),'group_ids':[g['id'] for g in groups if a['id'] in g['actor_ids']]})
 workspaces=[]
 for case in new:
  es=[e for e in events if e['case_id']==case['id']];ids=sorted({i for e in es for i in [e['actor_id'],*e['recipient_ids']] if i})
  if es:workspaces.append({'case_id':case['id'],'name':case['title'],'actor_ids':ids,'event_ids':[e['id'] for e in es]})
 d['cases']=new+d['cases'];d['social']['events']+=events;d['social']['actors']+=list(actors.values());d['social']['edges']+=list(edges.values());d['social']['groups']+=groups;d['social']['workspaces']+=workspaces
 # Only keep links to cases or explicit retained reference records.
 linked={x['source_id'] for x in d['cases']}|set(d.get('references',{}))
 for case in new:case['related_source_ids']=[x for x in case['related_source_ids'] if x in linked]
 ng=[x for x in new if x['dataset']=='nightingale'];tr=[x for x in new if x['dataset']=='transluce'];uids={u for x in ng for u in selection['nightingale:'+x['source_id']]['source_uids']}
 d['api_expansion']={'id':'api-v5','selected_cases':len(manifest['records']),'published_cases':len(new),'new_nightingale_pages':len(ng),'new_transluce_reports':len(tr),'reviewed_revision_records':len(uids),'held_cases':len(manifest['records'])-len(new),'selection':manifest['selection'],'usage':projection['usage_totals'],'model':projection['model'],'contributions':len(events),'directed_pairs':len(edges),'interaction_groups':len(groups),'supervisor_holds':held}
 d['snapshot']={'id':'api-v5','label':f'Research expansion · {len(d["cases"])} cases','built_at':now(),'analysis_model':'gpt-6-luna · OpenAI API expansion','review':{'status':'model_reviewed_provisional','summary':'Original 360 reviewed cases retained. New cases passed extraction, a separate evidence review, interpretation and summary through the OpenAI API. Exact quotes and stage ancestry are validated. Supervisor checks address page-versus-agent recipients and protocol granularity. This is provisional model analysis, not human ground truth.'}}
 d['coverage']['api_v5']={**d['api_expansion'],'limitations':['Purposive case selection is not a prevalence estimate.','Selected first, middle and latest distinct revisions within a character budget are not an exhaustive history.','New handles are page-local; cross-page identities and stable swarms need another review.','Transluce analysis uses selected metadata and request fields, without reading response bodies or executing embedded programs. Page titles can include URL text; recorded requests do not establish cooperation or successful tasks.']};d['methods']['api_v5']=manifest['selection']
 d['selection']['nightingale']['pages']+=len(ng);d['selection']['nightingale']['revisions']+=sum(selection['nightingale:'+x['source_id']]['available_revisions'] for x in ng);d['selection']['transluce']['reports']+=len(tr)
 d['observations']=overrides.get('findings',[])+d['observations'];d['qa']={'status':'source_validated_provisional','cases':len(d['cases']),'new_exact_quote_locations_checked':sum(len(e['evidence']) for case in new for e in case['episodes']),'network_quotes_checked':len(d['social']['events'])}
 return d
def main():
 c=connect(RUN/'state/pipeline.sqlite');p=build_projection(c)['pipeline'];sources={r['uid']:{**dict(r),'metadata':json.loads(r['metadata'])} for r in c.execute('SELECT * FROM sources')};c.close()
 baseline=json.loads((ROOT/'runs/network-v4/snapshot.json').read_text());manifest=json.loads((RUN/'selection.json').read_text());overrides=json.loads((RUN/'supervisor.json').read_text()) if (RUN/'supervisor.json').exists() else {}
 d=project(baseline,p,sources,manifest,overrides);atomic_json(RUN/'candidate.json',p);atomic_json(RUN/'snapshot.json',d);atomic_json(SITE/'research-data.json',d);print(json.dumps(d['api_expansion'],indent=2))
if __name__=='__main__':main()
