import json
import subprocess
import sys
import threading
import time
import unittest
from unittest.mock import patch
import audio_answer as a
import claude_support as c
from session_support import Cancelled
from test_screenshots import attachment
import test_product


class ClaudeTransportTests(unittest.TestCase):
    def test_model_catalog_uses_control_request_without_user_turn(self):
        import io,queue
        from unittest.mock import Mock
        process=Mock();process.stdin=io.BytesIO();events=queue.Queue()
        events.put({'type':'control_response','response':{'request_id':'other','subtype':'success'}})
        events.put({'type':'control_response','response':{'request_id':'model-catalog','subtype':'success',
                    'response':{'models':[{'value':'opus','resolvedModel':'claude-opus-test'},
                                          {'value':'opus'},None,{'value':'custom-model'}]}}})
        state=(process,events,[],{})
        with patch.object(c,'_start',return_value=state),patch.object(c,'_dispose') as dispose:
            self.assertEqual(c.read_model_catalog(a.ROOT),['opus','claude-opus-test','custom-model'])
            request=json.loads(process.stdin.getvalue())
            self.assertEqual(request['type'],'control_request')
            self.assertEqual(request['request']['subtype'],'initialize')
            dispose.assert_called_once_with(state)

    def test_model_catalog_timeout_disposes_process(self):
        import io,queue
        from unittest.mock import Mock
        process=Mock();process.stdin=io.BytesIO();state=(process,queue.Queue(),[],{})
        with patch.object(c,'_start',return_value=state),patch.object(c,'_dispose') as dispose:
            with self.assertRaisesRegex(RuntimeError,'timed out'):c.read_model_catalog(a.ROOT,timeout=.01)
            dispose.assert_called_once_with(state)

    def run_fixture(self,script,cancel=None,emit=None,usage=None):
        popen=subprocess.Popen
        def launch(args,**kwargs):
            self.assertIn('--safe-mode',args)
            self.assertEqual(args[args.index('--tools')+1],'')
            self.assertEqual(args[args.index('--effort')+1],'high')
            return popen([sys.executable,'-u','-c',script],**kwargs)
        with patch.object(c,'find_claude',return_value='claude.exe'),patch.object(c.subprocess,'Popen',side_effect=launch):
            return c.claude_answer(a.ROOT,'问题','sonnet',cancel or threading.Event(),emit or (lambda _:None),
                                   on_usage=usage,effort='high',images=[attachment()],total_timeout=3)

    def test_inline_image_stream_deduplication_and_usage(self):
        script="""
import sys,json,time
m=json.loads(sys.stdin.readline())
assert m['message']['content'][2]['source']['media_type']=='image/png'
assert m['message']['content'][2]['source']['data']
def send(x):print(json.dumps(x),flush=True)
send({'type':'stream_event','event':{'type':'content_block_delta','delta':{'type':'text_delta','text':'Hello'}}})
time.sleep(.2)
send({'type':'assistant','message':{'content':[{'type':'text','text':'Hello'}]}})
send({'type':'result','subtype':'success','result':'Hello','usage':{'input_tokens':12,'output_tokens':1,'cache_read_input_tokens':3}})
"""
        pieces=[];usage=[]
        self.assertEqual(self.run_fixture(script,emit=pieces.append,usage=usage.append),'Hello')
        self.assertEqual(pieces,['Hello']);self.assertEqual(usage[0]['input_tokens'],12)

    def test_result_error_preserves_partial_output(self):
        script="import json; print(json.dumps({'type':'assistant','message':{'content':[{'type':'text','text':'partial'}]}})); print(json.dumps({'type':'result','subtype':'error_max_turns','is_error':True}))"
        pieces=[]
        with self.assertRaisesRegex(RuntimeError,'未完成'):self.run_fixture(script,emit=pieces.append)
        self.assertEqual(pieces,['partial'])

    def test_cancel_does_not_wait_for_child(self):
        cancel=threading.Event();timer=threading.Timer(.15,cancel.set);timer.start()
        start=time.monotonic()
        try:
            with self.assertRaises(Cancelled):self.run_fixture('import time;time.sleep(10)',cancel=cancel)
            self.assertLess(time.monotonic()-start,1.5)
        finally:timer.join()


class ClaudeUITests(unittest.TestCase):
    setUp=test_product.ProductUITests.setUp
    tearDown=test_product.ProductUITests.tearDown

    def test_provider_uses_claude_model_and_screenshot_snapshot(self):
        self.ui.provider.set(c.PROVIDER);self.ui.update_provider()
        self.ui.advanced['claude_model'].set('sonnet')
        self.ui.reasoning_selection.set('high')
        self.ui.context_images=[attachment()]
        with patch.object(a,'claude_answer',return_value='OK') as answer:
            self.ui.ask();self.ui.worker.join(2)
        self.assertEqual(answer.call_count,1)
        self.assertEqual(answer.call_args.args[2],'sonnet')
        self.assertEqual(answer.call_args.kwargs['images'],[attachment()])
        self.assertEqual(answer.call_args.kwargs['effort'],'high')
        self.assertEqual(self.ui.jobs[1]['model'],'sonnet')


if __name__=='__main__':unittest.main()
