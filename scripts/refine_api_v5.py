#!/usr/bin/env python3
"""Apply the supervisor's research vocabulary at the interpretation stage."""
import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from swarm_pipeline.db import connect,atomic_json
from swarm_pipeline import engine
RUN=ROOT/'runs/api-v5';c=connect(RUN/'state/pipeline.sqlite');path=RUN/'refinement-log.json';log=json.loads(path.read_text()) if path.exists() else []
seen={x['prior_job_id'] for x in log}
guide='''SUPERVISOR PRESENTATION AND INTERPRETATION REQUIREMENTS:
Roles and behaviors are compact labels, not sentences. Roles describe what the agent contributes: scout (reports a firsthand observation useful to peers), observer (watches peers or signals), requester, coordinator, information provider, validator, parallel preparer. A handle containing Scout is not evidence of scouting. A requester asking someone else to scout is not itself a scout. Preserve offered versus performed roles through the observation status.
Use 1-4 of these short behavior labels where supported: scouting, observing, sharing information, requesting information, responding, coordinating, preparing, validating, correcting, delegating, accepting delegation, redirecting, signaling, waiting, testing, protecting shared evidence. If these miss a distinct behavior, use a new label of at most four words. Functions are also compact labels such as advance warning, shared situational awareness, parallel preparation, evidence repair, clock alignment, conversation continuity, or endpoint testing. Put explanations in the summaries and rules.
Do not force protocols. An ordinary request is not a protocol. Send the key observation quickly requires urgency or ordering (send the key observation before a full explanation or lookup); asking for an update alone is insufficient. Signal before a final answer can end the session requires an explicit concern about final-answer termination or a stated pre-answer ordering; a signal before the NEXT question alone does not fit. Agree on controls before interpreting a survival test requires actual experimental controls, not merely wondering whether a later round exists. Observed use is an instance following the rule, not proof that participants agreed to a convention. A promise or hypothetical remains proposed/commitment. A page named after an agent is still a place unless the quote actually addresses that agent.
For summaries: explain the task using the available page heading and content, and distinguish what is stated from reasonable interpretation. STATE5-XX can be explained as the requested fifth-question state signal if the page supports that; do not pretend the task is unknowable because a glossary is absent. Do not invent wages, employment units, or measures if absent. Avoid raw observation IDs in prose, unexplained cohort jargon, and repetitive caveats. A task clock is a run's own clock; an external UTC clock lets different runs compare timing. Explain why the cooperation helps.
Return summary links=[]; the dashboard derives navigation from approved records. Keep evidence_observation_ids.
'''
for row in c.execute("SELECT j.*,p.entity_id,p.payload FROM jobs j JOIN packets p ON p.id=j.packet_id WHERE p.dataset='nightingale' AND j.stage='interpret' AND j.status IN ('ready','done') ORDER BY j.created_at").fetchall():
 packet=json.loads(row['payload']);reason=packet.get('revision_request',{}).get('reason','')
 if c.execute("SELECT 1 FROM dependencies d JOIN jobs j ON j.id=d.job_id WHERE d.depends_on=? AND j.status='leased'",(row['id'],)).fetchone():continue
 if 'SUPERVISOR PRESENTATION AND INTERPRETATION REQUIREMENTS' in reason or row['id'] in seen:continue
 answer=engine.reprocess(c,row['id'],reason+'\n'+guide);log.append({'entity_id':row['entity_id'],'prior_job_id':row['id'],'created':answer['created']})
atomic_json(path,log);c.close();print('Interpretation refinements scheduled:',len(log))
