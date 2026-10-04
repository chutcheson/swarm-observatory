"""API authentication boundaries, structured results and shared queue transport."""
import io
import json
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch
from swarm_pipeline import db, engine, worker
from swarm_pipeline import openai_transport as api

FAKE_KEY='sk-proj-'+'x'*48
TEXT='A source note with no named participants.'
RESULT={'status':'complete','context_requests':[],'scope_summary':'One source note.',
        'reviewed_source_uids':['s1'],'observations':[],'limitations':[]}

def response(result=RESULT, **extra):
    return {'id':'resp_test','model':'gpt-6-luna','status':'completed',
            'output':[{'type':'message','content':[{'type':'output_text','text':json.dumps(result)}]}],
            'usage':{'input_tokens':100,'output_tokens':20,
                     'input_tokens_details':{'cached_tokens':10},'output_tokens_details':{'reasoning_tokens':8}},**extra}

class APITests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.key_file=self.root/'openai'
        self.key_file.write_text('OPENAI_API_KEY='+FAKE_KEY+'\n')
        self.conn=db.connect(self.root/'state.sqlite');self.addCleanup(self.conn.close)
        engine.configure(self.conn,{'backend':'openai','max_output_tokens':1024})
        db.set_setting(self.conn,'api_key_file',str(self.key_file))
        payload={'id':'p1','entity_id':'e1','dataset':'test','title':'Source note',
                 'sources':[{'uid':'s1','logical_id':'l1','text':TEXT,'metadata':{}}],
                 'focus':[{'source_uid':'s1','start':0,'end':len(TEXT)}],
                 'context_source_uids':[],'coverage':{},'links':[]}
        self.conn.execute('INSERT INTO entities VALUES(?,?,?,?,?)',('e1','test','page','Source note','{}'))
        self.conn.execute('INSERT INTO packets VALUES(?,?,?,?,?,?,?)',('p1','e1','test',db.digest(payload),db.canonical(payload),'{}',db.now()))
        engine.enqueue(self.conn,['p1'])

    def test_key_loader_never_evaluates_file_and_rejects_ambiguity(self):
        self.assertEqual(FAKE_KEY,api.load_key(self.key_file))
        marker=self.root/'not-created'
        self.key_file.write_text(f'$(touch {marker})\n'+FAKE_KEY)
        self.assertEqual(FAKE_KEY,api.load_key(self.key_file));self.assertFalse(marker.exists())
        self.key_file.write_text(FAKE_KEY+'\nsk-proj-'+'y'*48)
        with self.assertRaises(api.APIError) as got:api.load_key(self.key_file)
        self.assertNotIn(FAKE_KEY,str(got.exception))

    def test_api_worker_uses_strict_schema_no_tools_and_does_not_persist_key(self):
        calls=[]
        def request(path,payload,key_file,timeout,client_request_id):
            calls.append(payload)
            self.assertEqual('/v1/responses',path)
            self.assertEqual(str(self.key_file),str(key_file))
            self.assertTrue(client_request_id.startswith('attempt-'))
            return response(),'req_test'
        with patch.object(api,'request_json',side_effect=request),patch.object(worker.subprocess,'Popen') as cli:
            answer=worker.run_once(self.root/'state.sqlite',self.root/'attempts',timeout=5)
        cli.assert_not_called();self.assertEqual('done',answer['status'])
        p=calls[0];self.assertFalse(p['store']);self.assertEqual([],p['tools'])
        self.assertEqual('default',p['service_tier']);self.assertEqual(1024,p['max_output_tokens'])
        self.assertTrue(p['text']['format']['strict']);self.assertIn('EVIDENCE_DATA',p['input'])
        self.assertNotIn(TEXT,p['instructions'])
        self.assertEqual(8,answer['usage']['reasoning_output_tokens'])
        for f in (self.root/'attempts').rglob('*'):
            if f.is_file():self.assertNotIn(FAKE_KEY,f.read_text())
        self.assertNotIn(FAKE_KEY,'\n'.join(self.conn.iterdump()))

    def test_incomplete_and_refusal_cannot_become_results(self):
        job=engine.claim(self.conn,'test');prompt=worker.render_prompt(job)
        for data in [response(status='incomplete',incomplete_details={'reason':'max_output_tokens'}),
                     response(output=[{'type':'message','content':[{'type':'refusal','refusal':'no'}]}])]:
            with patch.object(api,'request_json',return_value=(data,'req_test')):
                with self.assertRaises(api.APIError) as got:api.complete(job,prompt,self.key_file)
            self.assertFalse(got.exception.retryable)
            self.assertEqual(100,got.exception.usage['input_tokens'])

    def test_authentication_error_is_sanitized_and_not_retried(self):
        class Broken:
            def open(self,*a,**k):
                raise urllib.error.HTTPError(api.API_ORIGIN+'/v1/responses',401,'Unauthorized',{},
                    io.BytesIO(json.dumps({'error':{'code':'invalid_api_key','message':FAKE_KEY}}).encode()))
        with patch.object(api.urllib.request,'build_opener',return_value=Broken()):
            with self.assertRaises(api.APIError) as got:
                api.request_json('/v1/responses',{},self.key_file,1,'test')
        self.assertTrue(got.exception.fatal);self.assertFalse(got.exception.retryable)
        self.assertNotIn(FAKE_KEY,str(got.exception))

    def test_transport_stops_redirects_and_only_authenticates_official_origin(self):
        class Reply:
            headers={'x-request-id':'req_test'}
            def __enter__(self):return self
            def __exit__(self,*a):pass
            def read(self,*a):return b'{}'
        class Capture:
            def open(s,request,timeout):
                self.assertEqual('https://api.openai.com/v1/responses',request.full_url)
                self.assertEqual('Bearer '+FAKE_KEY,request.get_header('Authorization'))
                return Reply()
        def opener(handler):
            self.assertIsInstance(handler,api.NoRedirect)
            self.assertIsNone(handler.redirect_request(None,None,None,None,None,None))
            return Capture()
        with patch.object(api.urllib.request,'build_opener',side_effect=opener):
            api.request_json('/v1/responses',{},self.key_file,1,'test')

if __name__=='__main__':unittest.main()
