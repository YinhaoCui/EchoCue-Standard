import threading
import time
import unittest
from unittest.mock import patch
import audio_answer as a
from answer_jobs import AnswerJobs
from reasoning_support import thinking_policy
import test_sessions
import test_codex_service


class RetainedServiceTests(unittest.TestCase):
    setUp = test_codex_service.ServiceTests.setUp

    def test_completed_turn_reuses_thread(self):
        def answer(prompt):
            return self.service.answer(prompt,'test','low',threading.Event(),lambda _:None,timeout=5,session_key='session')
        answer('context')
        thread=self.service.sessions['session'][1]
        answer('followup')
        self.assertEqual(self.service.sessions['session'][1],thread)
        self.assertEqual(self.service.launches,1)

    def test_parallel_turn_does_not_take_busy_thread(self):
        self.service.answer('ready','test','low',threading.Event(),lambda _:None,timeout=5,session_key='session')
        first=threading.Event();cancel=threading.Event();errors=[]
        def run():
            try:self.service.answer('slow','test','low',cancel,lambda _:first.set(),timeout=5,session_key='session')
            except Exception as exc:errors.append(exc)
        worker=threading.Thread(target=run);worker.start()
        self.assertTrue(first.wait(3))
        result=self.service.answer('parallel','test','low',threading.Event(),lambda _:None,timeout=5,session_key='session')
        worker.join(3)
        self.assertEqual(result,'first:parallel:last')
        self.assertFalse(errors)
        self.assertEqual(len(self.service.sessions),1)


class ContextPreparationTests(unittest.TestCase):
    setUp = test_sessions.UITests.setUp
    tearDown = test_sessions.UITests.tearDown

    def test_preparation_sends_context_without_polluting_history(self):
        self.ui.provider.set('Codex');self.ui.update_provider()
        self.ui.documents='reference fact'
        called=threading.Event();seen={}
        def fake(transcript,instructions,cancel,**kw):
            seen.update(instructions=instructions,key=kw.get('session_key'))
            kw['on_usage']({'input_tokens':20,'output_tokens':2})
            called.set()
            return '已准备'
        with patch.object(a,'codex_answer',side_effect=fake):
            AnswerJobs.prepare_model_context(self.ui)
            self.assertTrue(called.wait(2))
            deadline=time.monotonic()+2
            while time.monotonic()<deadline:
                self.ui.poll()
                if '已准备' in self.ui.context_warm_note.get():break
                time.sleep(.01)
        self.assertIn('reference fact',seen['instructions'])
        self.assertTrue(seen['key'])
        self.assertEqual(self.ui.history,[])
        self.assertEqual(self.ui.jobs,{})
        self.ui.token_ledger.record.assert_called()

    def test_disabled_preparation_does_not_call_provider(self):
        self.ui.advanced['warm_context'].set('关闭')
        with patch.object(a,'codex_answer') as request:
            AnswerJobs.prepare_model_context(self.ui)
            request.assert_not_called()

    def test_completed_history_is_in_next_snapshot(self):
        self.ui.history=[{'转录':'first question','回答':'first answer'}]
        inputs,error=self.ui.request_inputs()
        self.assertIsNone(error)
        self.assertEqual(inputs['history'],self.ui.history)
        self.ui.history.append({'转录':'later','回答':'later answer'})
        self.assertEqual(len(inputs['history']),1)
        self.ui.use_history.set(False)
        inputs,error=self.ui.request_inputs()
        self.assertEqual(inputs['history'],[])
        self.assertIsNone(inputs['session_key'])

    def test_cancel_all_cancels_preparation(self):
        self.ui.context_warm_cancel=threading.Event()
        self.ui.cancel_answer()
        self.assertTrue(self.ui.context_warm_cancel.is_set())


class ThinkingPolicyTests(unittest.TestCase):
    def test_disabled_uses_real_off_only_when_supported(self):
        self.assertEqual(thinking_policy('Codex','m','high','关闭',True,{'m':['none','low','high']})[:2],('none',False))
        self.assertEqual(thinking_policy('Codex','m','high','关闭',True,{'m':['low','high']})[:2],('low',False))
        self.assertEqual(thinking_policy('Gemini','gemini-2.5-flash','high','关闭',True)[:2],('关闭',False))

    def test_enabled_does_not_keep_disabled_effort(self):
        self.assertEqual(thinking_policy('Kimi','kimi-k2.6','关闭','开启',False)[:2],('开启',True))
