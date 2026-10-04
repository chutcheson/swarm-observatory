"""Publication boundaries: source fidelity, conservative social edges, baseline stability."""
import copy,importlib.util,json,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('api_dashboard',ROOT/'scripts/publish_api_v5_snapshot.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

class DashboardBoundaryTests(unittest.TestCase):
 def fixture(self,dataset='nightingale',author='Alice',audience='direct'):
  eid=dataset+':new';text='Alice asks Bob for the current state.'
  source={'logical_id':'new@1','text':text,'metadata':{'seq':1}}
  if dataset=='transluce':source['text']=json.dumps({'http_transactions':[]});text=source['text']
  obs={'id':'obs-x','kind':'message','actor':author,'recipients':['Bob'],'audience':audience,'summary':'Requests the current state.','task':'Compare state prompts.','status':'proposal','evidence':[{'source_uid':'s','start':0,'end':len(text),'quote':text}],'uncertainties':[]}
  record={'entity_id':eid,'dataset':dataset,'title':'New case','short':'Short','hover':'Hover','long':'Long','observations':[obs],'interpretation':{'contributions':[],'limitations':[]},'packet_scopes':[{'limitations':[]}],'provenance':{'review_decision':'approve','jobs':dict.fromkeys(['extract','review','interpret','summarize'],'job')}}
  manifest={'model':'gpt-6-luna','selection':'Test','records':[{'entity_id':eid,'source_id':'new','source_uids':['s'],'scope':'Test','available_revisions':1}]}
  baseline={'cases':[{'id':'old-case','source_id':'old','dataset':'nightingale'}],'families':[],'evidence':{},'social':{'events':[],'actors':[],'edges':[],'groups':[],'workspaces':[]},'coverage':{},'methods':{},'selection':{'nightingale':{'pages':1,'revisions':1},'transluce':{'reports':0}},'observations':[]}
  return baseline,{'records':[record],'usage_totals':{},'model':'gpt-6-luna'},{'s':source},manifest
 def test_baseline_unchanged_and_literal_direct_pair(self):
  args=self.fixture();original=copy.deepcopy(args[0]);d=m.project(*args)
  self.assertEqual(args[0],original);self.assertEqual(d['cases'][-1],original['cases'][0]);self.assertEqual(len(d['social']['edges']),1)
  self.assertEqual(len(d['social']['groups']),1)
 def test_unattributed_request_never_makes_edge(self):
  d=m.project(*self.fixture(author=None,audience='unknown'));self.assertEqual(d['social']['edges'],[])
 def test_shared_page_broadcast_never_makes_edge(self):
  d=m.project(*self.fixture(audience='broadcast'));self.assertEqual(d['social']['edges'],[])
 def test_transluce_trace_never_creates_social_actors(self):
  d=m.project(*self.fixture(dataset='transluce'));self.assertEqual(d['social']['actors'],[]);self.assertEqual(d['social']['edges'],[])
 def test_broken_quote_cannot_publish(self):
  args=self.fixture();args[1]['records'][0]['observations'][0]['evidence'][0]['quote']='invented'
  with self.assertRaises(AssertionError):m.project(*args)
 def test_supervisor_hold_stays_out_of_dashboard(self):
  d=m.project(*self.fixture(),overrides={'hold_entities':{'nightingale:new':'unresolved attribution'}})
  self.assertEqual(len(d['cases']),1);self.assertEqual(d['api_expansion']['held_cases'],1)
