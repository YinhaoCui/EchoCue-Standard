import json
import subprocess
import sys
import threading
import unittest
from unittest.mock import patch
import audio_answer as a
import antigravity_support as agy
import lmstudio_support as lm
from session_support import Cancelled
from token_usage import normalize_usage

class AntigravitySessionTests(unittest.TestCase):
    def tearDown(self): agy.close_service()

    def test_stream_process_retains_context_and_isolates_other_session(self):
        script = "import sys,json\ncount=0\nfor line in sys.stdin:\n count+=1\n print(json.dumps({'event':'result','result':{'status':'SUCCESS','response':str(count),'usage':{'input_tokens':count}}}),flush=True)"
        original=subprocess.Popen
        processes=[];reports=[]
        def launch(args,**kwargs):
            self.assertEqual(args[args.index('--effort')+1],'low')
            proc=original([sys.executable,'-u','-c',script],**kwargs);processes.append(proc);return proc
        with patch.object(agy,'find_antigravity',return_value='agy.exe'),patch.object(agy.subprocess,'Popen',side_effect=launch):
            def answer(key):return agy.antigravity_answer(a.ROOT,'test','model',threading.Event(),lambda _:None,effort='low',session_key=key,total_timeout=3,on_usage=reports.append)
            self.assertEqual(answer('one'),'1')
            self.assertEqual(answer('one'),'2')
            self.assertEqual(answer('two'),'1')
        self.assertEqual(len(processes),2)
        self.assertEqual([r["input_tokens"] for r in reports],[1,1,1])
        agy.close_service()
        self.assertTrue(all(p.poll() is not None for p in processes))

class LMStudioTests(unittest.TestCase):
    def setUp(self):
        lm._sessions.clear();lm._models.clear()
        self.payloads=[]
    def invoke(self, policy='关闭', session='s'):
        return lm.answer('http://127.0.0.1:1234/v1','','local','context','system',threading.Event(),lambda _:None,
                         lambda _:None,5,4096,policy,session)
    def stream(self,request,*args,**kwargs):
        self.payloads.append(json.loads(request.data))
        return iter([{'type':'message.delta','content':'OK'}, {'type':'chat.end','result':{
            'response_id':'resp_abc','output':[{'type':'message','content':'OK'}],
            'stats':{'input_tokens':10,'total_output_tokens':4,'reasoning_output_tokens':2}}}])
    def test_native_capabilities_and_session_continuation(self):
        rows=[{'key':'local','capabilities':{'reasoning':{'allowed_options':['off','on']}}}]
        with patch.object(lm,'capabilities',return_value=('http://localhost/api/v1',rows)),patch.object(lm,'streaming_events',side_effect=self.stream):
            self.assertTrue(self.invoke());self.assertTrue(self.invoke());self.assertTrue(self.invoke(session=None))
        self.assertEqual(self.payloads[0]['reasoning'],'off')
        self.assertNotIn('previous_response_id',self.payloads[0])
        self.assertEqual(self.payloads[1]['previous_response_id'],'resp_abc')
        self.assertFalse(self.payloads[2]['store'])
        self.assertNotIn('previous_response_id',self.payloads[2])
    def test_unsupported_thinking_is_not_sent(self):
        with patch.object(lm,'capabilities',return_value=('http://localhost/api/v1',[{'key':'local'}])),patch.object(lm,'streaming_events',side_effect=self.stream):
            self.invoke()
        self.assertNotIn('reasoning',self.payloads[0])
    def test_error_discards_branch_and_does_not_retry(self):
        with patch.object(lm,'capabilities',return_value=('http://localhost/api/v1',[])),patch.object(lm,'streaming_events',return_value=iter([{'type':'error','error':{'message':'bad'}}])) as stream:
            with self.assertRaisesRegex(RuntimeError,'bad'):self.invoke()
        self.assertEqual(stream.call_count,1);self.assertFalse(lm._sessions)
    def test_old_server_fallback_and_native_usage(self):
        with patch.object(lm,'capabilities',return_value=('http://localhost/api/v1',None)),patch.object(lm,'streaming_events') as stream:
            self.assertFalse(self.invoke());stream.assert_not_called()
        self.assertEqual(normalize_usage({'input_tokens':10,'total_output_tokens':4,'reasoning_output_tokens':2}),{'input':10,'output':4,'thinking':2})
