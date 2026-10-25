import copy
import json
import queue
import subprocess
import sys
import threading
import unittest
from pathlib import Path
from unittest.mock import patch,Mock
import audio_answer as a
import generation_context as g
import claude_support as claude
import antigravity_support as agy
import lmstudio_support as lm
from answer_jobs import Speculation,AnswerJobs
import test_codex_service
import test_sessions


def inputs():
    return dict(profile='PROFILE',documents='REFERENCE '*1000,summary='',terms='',instructions='',history=[],context_records=[],images=[],analysis=False)

def payload(text):return json.loads(text.splitlines()[-1])

class DeltaTests(unittest.TestCase):
    def test_updates_reconstruct_complete_snapshot_without_resending_document(self):
        data=inputs();first=g.ContextPrompt(data,'old transcript','SYSTEM')
        data['history']=[{'转录':'old transcript','回答':'answer'}]
        second=g.ContextPrompt(data,'old transcript new question','SYSTEM')
        update=payload(second.render(first.state))
        self.assertEqual(update['mode'],'patch');self.assertNotIn('documents',update['set'])
        restored=copy.deepcopy(first.state);restored.update(update['set'])
        for key,value in update['append'].items():restored[key]+=value
        self.assertEqual(restored,second.state)
        self.assertLess(len(second.render(first.state)),len(str(second))/5)
    def test_edits_removal_and_reordered_history_replace_fields(self):
        data=inputs();data['history']=[{'回答':'one'},{'回答':'two'}]
        first=g.ContextPrompt(data,'old','SYSTEM')
        data['documents']='';data['history'].reverse()
        second=g.ContextPrompt(data,'different','SYSTEM')
        delta=payload(second.render(first.state))
        self.assertEqual(delta['set']['documents'],'')
        self.assertEqual(delta['set']['history'],data['history'])
        self.assertEqual(delta['set']['transcript'],'different')
        self.assertEqual(payload(second.render())['mode'],'full')
    def test_unchanged_images_skipped_but_same_length_new_images_are_sent(self):
        data=inputs();data['images']=[{'data':'abc','title':'x','created':'today'}]
        first=g.ContextPrompt(data,'q','SYSTEM')
        self.assertFalse(g.send_images(first,first.state))
        data['images'][0]['data']='xyz';second=g.ContextPrompt(data,'q','SYSTEM')
        self.assertTrue(g.send_images(second,first.state))

class LaneTests(unittest.TestCase):
    def test_busy_lane_not_reused_and_failed_lane_discarded(self):
        pool=g.GenerationLanes()
        with patch.object(g,'discard_lane') as discard:
            one=pool.take('group');two=pool.take('group');self.assertNotEqual(one,two)
            pool.release(one);self.assertEqual(pool.take('group'),one)
            pool.release(one,False);discard.assert_called_with(one)
            pool.close();pool.release(two);discard.assert_called_with(two)
            self.assertEqual(pool.available('group'),0)
    def test_speculation_kept_only_after_adoption(self):
        spec=Speculation(queue.Queue(),(),1,'q');release=Mock()
        spec.release_when_decided(release);release.assert_not_called()
        spec.adopt(1,0);release.assert_called_once_with(True)
        other=Speculation(queue.Queue(),(),1,'q');release=Mock()
        other.release_when_decided(release);other.discard();release.assert_called_once_with(False)
    def test_cancel_before_worker_completion_discards_late_lane(self):
        spec=Speculation(queue.Queue(),(),1,'q');spec.discard();release=Mock()
        spec.release_when_decided(release);release.assert_called_once_with(False)

class CodexDeltaTests(unittest.TestCase):
    setUp=test_codex_service.ServiceTests.setUp
    def answer(self,prompt):return self.service.answer(prompt,'test','low',threading.Event(),lambda _:None,timeout=5,session_key='s')
    def test_only_confirmed_live_thread_receives_delta(self):
        first=g.ContextPrompt(inputs(),'q1','SYSTEM');second=g.ContextPrompt(inputs(),'q1 q2','SYSTEM')
        self.assertEqual(json.loads(self.answer(first).splitlines()[-1].removesuffix(':last'))['mode'],'full')
        self.assertEqual(json.loads(self.answer(second).splitlines()[-1].removesuffix(':last'))['mode'],'patch')
        saved=self.service.sessions['s'];self.service.sessions['s']=(saved[0],'expired',saved[2])
        self.assertEqual(json.loads(self.answer(second).splitlines()[-1].removesuffix(':last'))['mode'],'full')

class CliDeltaTests(unittest.TestCase):
    def tearDown(self):agy.close_service();claude.close_service()
    def test_claude_and_agy_keep_process_and_only_send_delta_to_that_process(self):
        for provider in ('claude','agy'):
            script="""import sys,json
sys.stdin.reconfigure(encoding="utf-8")
sys.stdout.reconfigure(encoding="utf-8")
for line in sys.stdin:
 m=json.loads(line)
 text=m['message']['content']
 if isinstance(text,list):text=text[0]['text']
 result={'type':'result','subtype':'success','result':text,'usage':{}} if 'type' in m else {'event':'result','result':{'status':'SUCCESS','response':text}}
 print(json.dumps(result),flush=True)
"""
            original=subprocess.Popen;processes=[]
            def launch(args,**kwargs):
                process=original([sys.executable,'-u','-c',script],**kwargs);processes.append(process);return process
            module=claude if provider=='claude' else agy
            find='find_claude' if provider=='claude' else 'find_antigravity'
            answer=claude.claude_answer if provider=='claude' else agy.antigravity_answer
            with patch.object(module,find,return_value='fixture.exe'),patch.object(module.subprocess,'Popen',side_effect=launch):
                def call(prompt):return answer(a.ROOT,prompt,'model',threading.Event(),lambda _:None,total_timeout=3,session_key=provider)
                self.assertEqual(payload(call(g.ContextPrompt(inputs(),'q1','S')))['mode'],'full')
                self.assertEqual(payload(call(g.ContextPrompt(inputs(),'q1 q2','S')))['mode'],'patch')
                self.assertEqual(len(processes),1)
                module.discard_session(provider)
                self.assertEqual(payload(call(g.ContextPrompt(inputs(),'q1 q2','S')))['mode'],'full')
                self.assertEqual(len(processes),2)

class AntigravityImageTests(unittest.TestCase):
    def test_new_screenshots_become_files_the_prompt_mentions(self):
        import base64, tempfile
        png = base64.b64encode(b'\x89PNG fake image').decode()
        images = [{'created': '10:00', 'title': 'Slide', 'data': png}]
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            text = agy.attach_images(work, 'question', None, images)
            files = list(work.glob('shot-*.png'))
            self.assertEqual(len(files), 1)
            self.assertEqual(files[0].read_bytes(), b'\x89PNG fake image')
            self.assertIn('@' + files[0].name, text)
            self.assertIn('Slide', text)
            self.assertEqual(agy.attach_images(work, 'question', None, []), '')

    def test_screenshots_already_sent_in_this_session_are_not_sent_again(self):
        import base64, tempfile
        data = base64.b64encode(b'png').decode()
        state = inputs(); state['images'] = [{'created': '1', 'title': 't', 'data': data}]
        prompt = g.ContextPrompt(state, 'q', 'S')
        with tempfile.TemporaryDirectory() as tmp:
            self.assertTrue(agy.attach_images(Path(tmp), prompt, None, state['images']))
            self.assertEqual(agy.attach_images(Path(tmp), prompt, g.checkpoint(prompt), state['images']), '')


class LMDeltaTests(unittest.TestCase):
    def test_antigravity_effort_matches_verified_variant(self):
        self.assertEqual(agy.resolve_model('gemini-3.8-flash-high','low'),'gemini-3.8-flash-low')
        self.assertEqual(agy.resolve_model('gemini-3.8-flash-high','自动'),'gemini-3.8-flash-high')
        self.assertEqual(agy.quick_effort('gpt-oss-120b-medium'),'自动')
        with self.assertRaises(ValueError):agy.resolve_model('gpt-oss-120b-medium','low')

    def test_previous_id_and_delta_are_used_together(self):
        lm._sessions.clear();sent=[]
        def stream(request,*args,**kwargs):
            sent.append(json.loads(request.data))
            return iter([{'type':'chat.end','result':{'response_id':'resp_ok','output':[{'type':'message','content':'OK'}]}}])
        with patch.object(lm,'capabilities',return_value=('http://localhost/api/v1',[])),patch.object(lm,'streaming_events',side_effect=stream):
            for text in ('q1','q1 q2'):
                lm.answer('http://localhost/v1','','model',g.ContextPrompt(inputs(),text,'S'),'S',threading.Event(),lambda _:None,None,5,None,session_key='s')
        self.assertEqual(payload(sent[0]['input'])['mode'],'full')
        self.assertEqual(payload(sent[1]['input'])['mode'],'patch')
        self.assertEqual(sent[1]['previous_response_id'],'resp_ok')
        lm._sessions.clear()

class SparePreparationTests(unittest.TestCase):
    setUp=test_sessions.UITests.setUp
    tearDown=test_sessions.UITests.tearDown
    def test_only_one_conversation_prepared_even_with_legacy_spare_enabled(self):
        self.ui.provider.set('Codex');self.ui.update_provider();self.ui.advanced['spare_session'].set('开启')
        with patch.object(a,'codex_answer',return_value='已准备') as answer:
            AnswerJobs.prepare_model_context(self.ui);self.ui.context_warm_worker.join(3)
        self.assertEqual(answer.call_count,1)
        keys=[call.kwargs['session_key'] for call in answer.call_args_list]
        self.assertEqual(len(keys),1)
        self.assertEqual(self.ui.generation_lanes.available(self.ui.request_inputs()[0]['session_key']),1)
        self.assertEqual(self.ui.history,[])
    def test_preparation_failure_does_not_retry_on_second_spare(self):
        self.ui.provider.set('Codex');self.ui.update_provider();self.ui.advanced['spare_session'].set('开启')
        with patch.object(a,'codex_answer',side_effect=RuntimeError('auth')) as answer:
            AnswerJobs.prepare_model_context(self.ui);self.ui.context_warm_worker.join(3)
        self.assertEqual(answer.call_count,1)
        self.assertEqual(self.ui.generation_lanes.available(self.ui.request_inputs()[0]['session_key']),0)

    def test_legacy_lm_preparation_is_not_duplicated_as_fake_session(self):
        self.ui.provider.set('LM Studio');self.ui.update_provider();self.ui.model.set('test-model')
        self.ui.advanced['spare_session'].set('开启')
        with patch.object(lm,'capabilities',return_value=('http://localhost/api/v1',None)),patch.object(a,'compatible_answer',side_effect=lambda *args,**kwargs:args[6]('已准备')) as answer:
            AnswerJobs.prepare_model_context(self.ui);self.ui.context_warm_worker.join(3)
        self.assertEqual(answer.call_count,1)
        self.assertFalse(any(self.ui.generation_lanes.idle.values()))
