"""Lossless token optimizations and independent transcription controls."""
import copy
import json
import threading
import unittest
from types import SimpleNamespace
from unittest.mock import Mock,patch
import audio_answer as a
import test_sessions
from answer_jobs import AnswerJobs
from caption_translation import CaptionPresenter
from generation_context import ContextPrompt,image_indices
from test_generation_context import inputs


class ContextEfficiencyTests(unittest.TestCase):
    def test_only_new_images_are_sent_and_new_sessions_receive_all(self):
        state=inputs();state['images']=[dict(data='old',title='A',created='now')]
        first=ContextPrompt(state,'question','system')
        state['images'].append(dict(data='new',title='B',created='later'))
        second=ContextPrompt(state,'question','system')
        self.assertEqual(image_indices(second,first.state,2),[1])
        self.assertEqual(image_indices(second,None,2),[0,1])
        state['images'][0]['created']='recaptured'
        third=ContextPrompt(state,'question','system')
        self.assertEqual(image_indices(third,second.state,2),[])
        state['images'].append(dict(state['images'][0]))
        self.assertEqual(image_indices(ContextPrompt(state,'question','system'),None,3),[0,1])

    def test_history_references_preserve_complete_original_input(self):
        text='A long transcript with 中文 and code.'
        state=inputs();state['history']=[{'转录':text,'回答':'answer'}]
        original=copy.deepcopy(state)
        prompt=ContextPrompt(state,text+' Next question.','system')
        entry=prompt.state['history'][0]
        start,end=entry['transcript_ref']['range']
        self.assertEqual(prompt.state['transcript'][start:end],text)
        self.assertEqual(state,original)
        changed=ContextPrompt(state,'Different transcript','system')
        self.assertEqual(changed.state['history'][0]['转录'],text)

    def test_translation_cache_survives_language_switch_and_failed_entries_retry(self):
        app=SimpleNamespace(content_language=lambda _: 'en',locale=SimpleNamespace(language='en'),closing=False)
        presenter=CaptionPresenter(app)
        presenter.cache[('en','你好')]='Hello'
        presenter.cache[('en','失败')]='failed';presenter.failed.add(('en','失败'))
        presenter.active=threading.Event();presenter.active_key=('en','pending');presenter.pending.add(presenter.active_key)
        presenter.reset()
        self.assertEqual(presenter.body('  你好  '),'Hello')
        self.assertNotIn(('en','失败'),presenter.cache)
        self.assertFalse(presenter.active.is_set())
        self.assertEqual(presenter.pending,{('en','pending')})


class UIEfficiencyTests(unittest.TestCase):
    setUp=test_sessions.UITests.setUp
    tearDown=test_sessions.UITests.tearDown

    def test_context_edits_and_explicit_reset_start_fresh_lanes(self):
        self.ui.provider.set('Codex');self.ui.update_provider()
        first=self.ui.request_inputs()[0]['session_key']
        self.ui.context_version+=1;self.ui.profile='Changed'
        second=self.ui.request_inputs()[0]['session_key']
        self.assertNotEqual(second,first)
        self.ui.history_epoch+=1
        self.assertNotEqual(self.ui.request_inputs()[0]['session_key'],second)

    def test_quick_mode_uses_low_effort_without_overriding_manual_choice(self):
        self.ui.provider.set('Codex');self.ui.update_provider()
        self.ui.answer_mode.set('快速');self.ui.reasoning_selection.set('自动')
        self.ui.advanced['thinking_policy'].set('自动')
        self.assertEqual(self.ui.request_inputs()[0]['effort'],'low')
        self.ui.reasoning_selection.set('high')
        self.assertEqual(self.ui.request_inputs()[0]['effort'],'high')

    def test_repeated_preparation_uses_one_retained_conversation(self):
        self.ui.provider.set('Codex');self.ui.update_provider()
        with patch.object(a,'codex_answer',return_value='Ready') as answer:
            AnswerJobs.prepare_model_context(self.ui);self.ui.context_warm_worker.join(3)
            AnswerJobs.prepare_model_context(self.ui)
            self.assertEqual(answer.call_count,1)

    def test_pause_keeps_reading_view_text_and_inflight_answer(self):
        self.ui.put_text('Existing answer',replace=True)
        self.ui.put_text('Existing transcript',replace=True,target='transcript')
        self.ui.capture.active.return_value=True
        self.ui.capture.stop.side_effect=lambda:setattr(self.ui.capture.active,'return_value',False)
        cancel=threading.Event()
        self.ui.jobs[99]=dict(done=False,cancel=cancel,started=0,timeout=float('inf'))
        with patch.object(self.ui,'cancel_context_preparation') as preparation,patch.object(self.ui.live,'flush') as flush:
            self.ui.toggle_listen()
            flush.assert_called_once();preparation.assert_not_called()
        self.assertTrue(self.ui.transcription_paused)
        self.assertFalse(cancel.is_set())
        self.assertIn('Existing answer',self.ui.output_text)
        self.assertIn('Existing transcript',self.ui.transcript_view)
        self.ui.jobs.clear()

    def test_duplicate_screenshot_does_not_invalidate_context(self):
        item=dict(data='pixels',id='first',title='Window',created='now')
        self.ui.context_images=[item]
        version=self.ui.context_version
        self.ui.receive_screenshot((version,dict(item,id='second',created='later'),''))
        self.assertEqual(len(self.ui.context_images),1)
        self.assertEqual(self.ui.context_version,version)

    def test_transcription_shortcut_dispatches_without_triggering_answer(self):
        with patch.object(self.ui,'toggle_listen') as toggle,patch.object(self.ui,'ask') as answer:
            self.ui.events.put(('transcription',0));self.ui.poll()
            toggle.assert_called_once();answer.assert_not_called()


class ImageTransportTests(unittest.TestCase):
    def setUp(self):
        import test_codex_service
        test_codex_service.ServiceTests.setUp(self)

    def test_confirmed_codex_session_sends_new_image_only(self):
        state=inputs();state['images']=[dict(data='one',title='A',created='now')]
        first=ContextPrompt(state,'q1','system')
        with patch.object(self.service,'rpc',wraps=self.service.rpc) as rpc:
            self.service.answer(first,'fixture','low',threading.Event(),lambda _:None,timeout=5,images=['a.png'],session_key='images')
            state['images'].append(dict(data='two',title='B',created='later'))
            second=ContextPrompt(state,'q1 q2','system')
            self.service.answer(second,'fixture','low',threading.Event(),lambda _:None,timeout=5,images=['a.png','b.png'],session_key='images')
        turns=[call.args[1]['input'] for call in rpc.call_args_list if call.args[0]=='turn/start']
        self.assertEqual([item['path'] for item in turns[0] if item['type']=='localImage'],['a.png'])
        self.assertEqual([item['path'] for item in turns[1] if item['type']=='localImage'],['b.png'])
