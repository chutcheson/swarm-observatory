import importlib.util
import unittest
from pathlib import Path
from swarm_pipeline.contracts import InvalidResult, validate_result

spec=importlib.util.spec_from_file_location('full_prepare',Path(__file__).resolve().parents[1]/'scripts/prepare_nightingale_full.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

class FullCorpusTests(unittest.TestCase):
 def test_carried_lines_are_context(self):
  before='First message -- A\n';after=before+'Reply -- B\n'
  inserted,deleted=m.changes(before,after)
  self.assertEqual(inserted,[(len(before),len(after))]);self.assertEqual(deleted,[])
 def test_replacement_retains_removed_evidence(self):
  inserted,deleted=m.changes('old\n','new\n')
  self.assertEqual(inserted,[(0,4)]);self.assertEqual(deleted,[(0,4)])
 def test_large_source_focus_is_covered_once(self):
  text='x'*25001;s={'uid':'s','logical_id':'r','text':text,'metadata':{}}
  parts=list(m.slices(s,[(0,len(text))]));spans=[]
  for p in parts:
   source=p['source'];start=source['metadata']['source_start']
   self.assertEqual(source['text'],text[start:source['metadata']['source_end']])
   spans += [(f['start']+start,f['end']+start) for f in p['focus']]
  self.assertEqual(spans,[(0,10000),(10000,20000),(20000,25001)])
 def test_removed_message_is_not_new_communication(self):
  o={'id':'o','kind':'message','actor':'A','recipients':[],'audience':'broadcast','summary':'A wrote hello','task':'Unknown','status':'observed_message','evidence':[{'source_uid':'s','quote':'hello -- A'}],'uncertainties':[]}
  result={'status':'complete','context_requests':[],'scope_summary':'Deletion','reviewed_source_uids':['s'],'observations':[o],'limitations':[]}
  packet={'sources':[{'uid':'s','text':'hello -- A','metadata':{'role':'deleted_text'}}],'focus':[{'source_uid':'s','start':0,'end':10}]}
  with self.assertRaisesRegex(InvalidResult,'Removed text'):validate_result('extract',result,packet)
  o.update(kind='document_action',actor=None,summary='The passage was removed',status='unclear')
  self.assertEqual(validate_result('extract',result,packet),result)

if __name__=='__main__':unittest.main()
