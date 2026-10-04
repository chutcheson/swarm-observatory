"""Apply eight source-checked supervisor corrections, then require fresh API review."""
import json, re, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from swarm_pipeline.db import connect, atomic_json
from swarm_pipeline import engine

IDS = ['e6e715fe-2b9b-4b6f-ac4d-d1899896eb12', '3c5db3f7-dc13-44cc-a887-c911f5235e71',
       '9e4a9857-526d-4808-9bd1-5dff5960473d', '09ef2d3b-6152-4319-a7d1-f16f9c43479b',
       'ed7a5991-0be3-4992-b848-ef397e9c080e', '585a1950-f523-414b-9c91-1993fe00aed9',
       '30b9013b-823f-45ac-86b7-44ce80d82380', '19a67538-824f-4062-9dca-ae52838b3eb3']
RUN = ROOT / 'runs/api-v5'
logpath = RUN / 'supervisor-trace-corrections.json'
log = json.loads(logpath.read_text()) if logpath.exists() else []
c = connect(RUN / 'state/pipeline.sqlite')
for rid in IDS:
    eid = 'transluce:' + rid
    if any(x['entity_id'] == eid for x in log): continue
    review = c.execute("SELECT j.* FROM jobs j JOIN packets p ON p.id=j.packet_id WHERE p.entity_id=? AND j.stage='review' AND j.status='blocked'", (eid,)).fetchone()
    if not review: continue
    oldid = c.execute('SELECT depends_on FROM dependencies WHERE job_id=?', (review['id'],)).fetchone()[0]
    old = engine.job_input(c, oldid)
    result = json.loads(c.execute('SELECT payload FROM results WHERE job_id=?', (oldid,)).fetchone()[0])
    assert len(result['observations']) == 1
    o = result['observations'][0]
    before = json.loads(json.dumps(o))
    o['kind'] = o['status'] = 'technical_trace'
    o['summary'] = o['summary'].replace('an annotation about the report', 'a technical request trace').replace('report annotation', 'request trace').replace('trace annotation', 'request trace')
    source = old['packet']['sources'][0]
    if rid in IDS[1:2] + IDS[3:4]:
        # Include the literal endpoint, method, status and body metadata from the first transaction.
        m = re.search(r'"host":.*?"body_bytes":\s*\d+', source['text'], re.S)
        assert m
        o['evidence'].append({'source_uid': source['uid'], 'quote': m.group()})
    if rid == IDS[5]:
        line = next(x.strip().rstrip(',') for x in source['text'].splitlines() if '"final_title"' in x)
        o['evidence'].append({'source_uid': source['uid'], 'quote': line})
        o['summary'] += ' The report title includes an encoded URL pointing to an anemia configuration endpoint at vizhub.healthdata.org; the title does not establish the returned contents or request purpose.'
    reason = 'Supervisor correction after reading the raw archived fields: classify HTTP request metadata as technical_trace; attach literal endpoint/title evidence where missing. Preserve unknown identities and outcome limitations. Independently review this corrected extraction against the packet; do not assume approval. Summaries should return links=[] because the dashboard derives links.'
    restarted = engine.reprocess(c, oldid, reason)
    claimed = engine.claim(c, 'supervisor-source-correction', job_id=restarted['created'][0])
    submitted = engine.submit(c, claimed['job_id'], claimed['lease_token'], result, usage={'input_tokens': 0, 'output_tokens': 0, 'total_tokens': 0, 'supervisor_correction': True})
    log.append({'entity_id': eid, 'prior_job_id': oldid, 'new_job_id': claimed['job_id'], 'before': before, 'after': o, 'status': submitted['status']})
    atomic_json(logpath, log)
    print(eid, submitted['status'])
c.close()
