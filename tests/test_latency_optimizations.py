import queue
import threading
import time
import unittest
from unittest.mock import patch
import audio_answer as a
from answer_jobs import Speculation
from generation_context import GenerationLanes,ContextPrompt
from session_control import latency_statistics
from test_generation_context import inputs
import test_sessions


class LatencyTests(unittest.TestCase):
    def test_adoption_wakes_debounce_and_cancel_does_not_generate(self):
        spec=Speculation(queue.Queue(),(),1,'q');finished=threading.Event();result=[]
        def wait():result.append(spec.wait_to_generate());finished.set()
        worker=threading.Thread(target=wait);worker.start()
        spec.adopt(1,time.monotonic())
        self.assertTrue(finished.wait(.2));worker.join(1);self.assertEqual(result,[True])
        cancelled=Speculation(queue.Queue(),(),1,'q');cancelled.discard()
        self.assertFalse(cancelled.wait_to_generate())

    def test_lane_selection_prefers_smallest_delta_then_latest(self):
        pool=GenerationLanes();old=ContextPrompt(inputs(),'first','S');new=ContextPrompt(inputs(),'first second','S')
        with patch('generation_context.discard_lane'):
            one=pool.take('g');two=pool.take('g')
            pool.release(one,snapshot=old.state);pool.release(two,snapshot=new.state)
            self.assertEqual(pool.take('g',target=new),two)
            pool.release(two,snapshot=new.state)
            # A newly completed concurrent request replaces the oldest spare.
            third=pool.take('g',fresh=True);pool.release(third,snapshot=new.state)
            self.assertNotIn(one,pool.idle['g'])
            self.assertEqual(pool.take('g',target=new),third)
            pool.release(third,False);pool.close()

    def test_statistics_separate_models_and_prediction_and_ignore_missing(self):
        jobs={1:dict(provider='A',model='m',prediction_eligible=True,timing={'first_display':1.,'speculative':False}),
              2:dict(provider='A',model='m',prediction_eligible=True,timing={'first_display':3.,'speculative':False}),
              3:dict(provider='A',model='m',prediction_eligible=True,timing={'first_display':.1,'speculative':True}),
              4:dict(provider='B',model='n',timing={'first_display':8.}),
              5:dict(provider='B',model='n',timing={})}
        result=latency_statistics(jobs)
        self.assertIn('2 次 · 按键到显示中位 2.00s / P95 3.00s',result)
        self.assertIn('预生成 · 1 次',result);self.assertIn('1/3（33%）',result)
        self.assertIn('B / n · 实时生成 · 1 次',result)


class LatencyUITests(unittest.TestCase):
    setUp=test_sessions.UITests.setUp
    tearDown=test_sessions.UITests.tearDown

    def test_prepare_starts_listening_once_and_never_answers(self):
        with patch.object(self.ui,'toggle_listen') as start,patch.object(self.ui,'ask') as answer:
            self.ui.prepare_listening();self.ui.prepare_listening()
            start.assert_not_called()
            self.root.update_idletasks();start.assert_called_once();answer.assert_not_called()
            self.ui.capture.active.return_value=True
            self.ui.prepare_listening();self.root.update_idletasks();start.assert_called_once()

    def test_worker_dispatch_precedes_answer_region_and_does_not_save_synchronously(self):
        self.ui.provider.set('LM Studio');self.ui.update_provider();self.ui.model.set('fixture')
        began=threading.Event();original=self.ui.add_answer_region
        def answer(*args,**kwargs):began.set();args[6]('正文')
        def region(identity,text=''):
            self.assertTrue(began.wait(1));original(identity,text)
        pressed=time.monotonic()-.1
        with patch.object(a,'compatible_answer',side_effect=answer),patch.object(self.ui,'save_preferences') as save,patch.object(self.ui,'add_answer_region',side_effect=region):
            self.ui.ask(transcript_override='q',pressed_at=pressed)
            save.assert_not_called();self.ui.worker.join(2);self.ui.poll();self.root.update_idletasks()
        job=self.ui.jobs[self.ui.ask_revision]
        self.assertGreaterEqual(job['timing']['dispatch'],.1)
        self.assertGreaterEqual(job['timing']['first_display'],job['timing']['first_total'])
        self.assertGreaterEqual(job['timing']['display_queue'],0)
        self.assertIn('正文',job['answer'])

    def test_hotkey_keeps_arrival_timestamp(self):
        pressed=time.monotonic()-.2
        with patch.object(self.ui,'ask') as ask:
            self.ui.events.put(('hotkey',pressed));self.ui.poll()
            ask.assert_called_once_with(pressed_at=pressed)
