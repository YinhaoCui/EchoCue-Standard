import io
import json
import pathlib
import shutil
import sys
import threading
import time
import unittest
import uuid
from unittest.mock import patch, MagicMock
import audio_answer as a
import test_sessions
from session_data import SessionStore, SessionWriter, compact_context, record_text
from speech_activity import SpeechActivity, apply_terms
from codex_stream import stream_process


def segment(i, body=None):
    body=body or ('段落'+str(i)+' 重要资料'*20)
    return dict(sequence=i,source='电脑',generation=i,body=body,text='[12:00:00 电脑]\n'+body,ok=True)


class ProductDataTests(unittest.TestCase):
    def setUp(self):
        self.folder=a.WORK/('product-test-'+uuid.uuid4().hex);self.folder.mkdir()
    def tearDown(self):
        assert self.folder.resolve().is_relative_to(a.WORK.resolve())
        shutil.rmtree(self.folder)

    def test_context_keeps_sixty_turns_without_repeating_prefixes(self):
        records=[segment(i) for i in range(1,61)]
        current=record_text(records)
        history=[{'转录截止段':i,'回答':'答案'+str(i)} for i in range(1,61)]
        text=compact_context('profile','document','summary',history,current,records)
        data=json.loads(text.split('\n',1)[1])
        self.assertEqual(len(data['本次会话全部对话']),60)
        self.assertEqual(data['补充转录'],{})
        for i,turn in enumerate(data['本次会话全部对话'],1):
            left,right=turn['转录引用']['字符起止']
            self.assertEqual(current[left:right],record_text(records,i))
        raw=''.join(record_text(records,i) for i in range(1,61))
        self.assertLess(len(text)+len(current),len(raw)/4)

    def test_context_retains_nonoverlapping_old_transcripts_once(self):
        history=[{'转录':'旧资料不能丢','回答':'A'},{'转录':'旧资料不能丢','回答':'B'}]
        data=json.loads(compact_context('','','',history,'新问题').split('\n',1)[1])
        self.assertEqual(list(data['补充转录'].values()),['旧资料不能丢'])
        self.assertEqual(len(data['本次会话全部对话']),2)

    def test_reanswer_one_segment_keeps_history_without_cumulative_duplicates(self):
        records=[segment(i) for i in range(1,61)]
        history=[{'转录截止段':i,'回答':'答案'+str(i)} for i in range(1,61)]
        data=json.loads(compact_context('','','',history,'单独重答',records).split('\n',1)[1])
        self.assertEqual(len(data['补充转录']),1)
        for i,turn in enumerate(data['本次会话全部对话'],1):
            reference=turn['转录引用'];start,end=reference['字符起止']
            self.assertEqual(data['补充转录'][reference['编号']][start:end],record_text(records,i))

    def test_dpapi_store_roundtrip_incremental_write_and_delete(self):
        store=SessionStore(self.folder/'sessions.sqlite3')
        payload={'title':'private title','segment:1':segment(1,'private speech'),'job:1':{'answer':'private answer'}}
        store.save('session',payload)
        self.assertEqual(store.load('session'),payload)
        raw=store.path.read_bytes()
        self.assertNotIn(b'private speech',raw)
        self.assertNotIn(b'private answer',raw)
        with patch('session_data.protect',side_effect=AssertionError('unchanged entries must not be encrypted again')):
            store.save('session',payload)
        self.assertEqual(store.list()[0][0],'session')
        store.delete('session');self.assertEqual(store.list(),[])

    def test_writer_finishes_latest_checkpoint_on_close(self):
        store=SessionStore(self.folder/'sessions.sqlite3');reports=[]
        writer=SessionWriter(store,reports.append)
        for i in range(20): writer.submit('s',{'title':'fixture','value':i})
        writer.close()
        self.assertEqual(store.load('s')['value'],19)
        self.assertFalse(writer.thread.is_alive())

    def test_vad_silence_and_non_cascading_term_corrections(self):
        detector=SpeechActivity(16000)
        self.assertFalse(detector.voiced(b'\0\0'*16000))
        self.assertEqual(apply_terms('派森 uses API','派森 => Python\nPython => WRONG\nAPI => API client'),'Python uses API client')

    def test_codex_emits_before_turn_completion_without_repeating_full_item(self):
        script="import json,time; print(json.dumps({'type':'item.updated','item':{'id':'a','type':'agent_message','text':'Hello'}}),flush=True); time.sleep(.3); print(json.dumps({'type':'item.completed','item':{'id':'a','type':'agent_message','text':'Hello world'}}),flush=True); print(json.dumps({'type':'turn.completed','usage':{'output_tokens':2}}),flush=True)"
        received=[];usage=[];start=time.monotonic()
        answer=stream_process([sys.executable,'-u','-c',script],'prompt',threading.Event(),self.folder,5,
                              lambda text:received.append((time.monotonic()-start,text)),usage.append)
        self.assertEqual(answer,'Hello world');self.assertEqual(''.join(t for _,t in received),'Hello world')
        self.assertGreater(received[-1][0]-received[0][0],.2)
        self.assertEqual(usage,[{'output_tokens':2}])

    def test_codex_partial_failure_is_not_reported_as_success(self):
        script="import json; print(json.dumps({'type':'item.completed','item':{'id':'a','type':'agent_message','text':'Partial'}}),flush=True)"
        chunks=[]
        with self.assertRaisesRegex(RuntimeError,'中断'):
            stream_process([sys.executable,'-u','-c',script],'q',threading.Event(),self.folder,5,chunks.append)
        self.assertEqual(chunks,['Partial'])

    def test_capture_close_releases_audio_even_if_stop_raises(self):
        capture=object.__new__(a.Capture)
        capture.audio=MagicMock();capture.stop=MagicMock(side_effect=RuntimeError('driver'))
        with self.assertRaises(RuntimeError): capture.close()
        capture.audio.terminate.assert_called_once()

    def test_capture_close_does_not_call_app_methods(self):
        capture=object.__new__(a.Capture)
        capture.audio=MagicMock();capture.stream=None
        capture.close()
        capture.audio.terminate.assert_called_once()


class ProductUITests(unittest.TestCase):
    def setUp(self):
        test_sessions.UITests.setUp(self)
        self.folder=a.WORK/('product-ui-'+uuid.uuid4().hex);self.folder.mkdir()
        self.ui.session_store=SessionStore(self.folder/'sessions.sqlite3')
    def tearDown(self):
        if self.ui.session_writer:self.ui.session_writer.close()
        test_sessions.UITests.tearDown(self)
        shutil.rmtree(self.folder)

    def test_live_render_keeps_long_confirmed_text_and_replaces_drafts(self):
        self.ui.live_text='确认文字 '*20000
        self.ui.live_drafts={'电脑':{'text':'草稿一','generation':1}}
        self.ui.render_live_transcript()
        self.ui.live_drafts['电脑']['text']='草稿二';self.ui.render_live_transcript()
        content=self.ui.transcript_view
        self.assertTrue(content.startswith(self.ui.live_text))
        self.assertNotIn('草稿一',content);self.assertIn('草稿二',content)
        self.ui.live_text+='新定稿';self.ui.live_drafts={};self.ui.render_live_transcript()
        self.assertEqual(self.ui.transcript_view,self.ui.live_text)

    def test_edited_segment_updates_future_snapshots_and_persisted_original(self):
        self.ui.live.records=[segment(1,'错词')];self.ui.live.submitted=self.ui.live.completed=1
        self.ui.remember_transcript(self.ui.live.records[0]['text'],-1)
        record=self.ui.transcript_records[0]
        self.ui.update_transcript(record,'[12:00:00 电脑]\n正确词')
        self.assertIn('正确词',self.ui.live.snapshot(1,threading.Event()))
        self.assertIn('错词',self.ui.session_payload()['segment:1']['original'])

    def test_restore_retains_full_context_answer_regions_and_interrupted_answers(self):
        payload={'segment:1':segment(1),'history':[{'转录截止段':1,'回答':'历史答案'}],
                 'profile':'用户资料','documents':'完整文档','summary':'摘要',
                 'job:1':dict(id=1,label='任务一',answer='尚未完成',target=1,done=False,elapsed=3)}
        self.ui.events.put(('live_segment',segment(999,'旧窗口待处理事件')))
        self.ui.restore_payload(payload)
        self.ui.poll()
        self.assertTrue(self.ui.jobs[1]['done'])
        self.assertIn('已中断',self.ui.jobs[1]['state'])
        self.assertEqual(self.ui.documents,'完整文档')
        self.assertIn(1,self.ui.job_regions)
        self.assertIn('段落1',self.ui.job_transcript(self.ui.jobs[1]))
        self.assertEqual(self.ui.live.submitted,1)
        self.assertNotIn('旧窗口待处理事件',self.ui.live_text)
        self.assertIn('尚未完成',self.ui.output_text)
        self.ui.job_text(1,'，续写')
        self.assertIn('尚未完成，续写\n',self.ui.output_text)

    def test_poll_budget_does_not_cancel_answers_under_large_event_backlog(self):
        for i in range(3000): self.ui.events.put(('live_partial',{'source':'电脑','generation':1,'text':str(i)}))
        start=time.monotonic();self.ui.poll()
        self.assertLess(time.monotonic()-start,.5)
        self.assertFalse(self.ui.closed)

    def test_answer_latency_records_first_reply_and_completion(self):
        self.ui.provider.set('LM Studio');self.ui.update_provider();self.ui.model.set('fixture')
        def answer(*args,**kwargs):
            time.sleep(.03);args[6]('第一段');time.sleep(.03);args[6]('第二段')
        with patch.object(a,'compatible_answer',side_effect=answer):
            self.ui.ask(transcript_override='测试问题');self.ui.worker.join(2);self.ui.poll()
        job=self.ui.jobs[self.ui.ask_revision];timing=job['timing']
        self.assertGreaterEqual(timing['first_reply'],.025)
        self.assertGreaterEqual(timing['generation'],.025)
        self.assertGreaterEqual(timing['first_total'],timing['first_reply'])
        from session_control import latency_summary
        self.assertIn('模型首字',latency_summary(job))

    def test_pause_setting_changes_live_segmentation_immediately(self):
        self.assertEqual(self.ui.live.silence,.35)
        self.ui.advanced['asr_pause'].set('均衡 · 0.65 秒')
        self.assertEqual(self.ui.live.silence,.65)

    def test_shutdown_keeps_tk_responsive_during_driver_and_save_waits(self):
        release_audio=threading.Event();release_save=threading.Event();saving=threading.Event()
        self.ui.capture=MagicMock();self.ui.mic=MagicMock()
        self.ui.capture.stop.side_effect=lambda:release_audio.wait(3)
        self.ui.mic.stop.side_effect=RuntimeError('device unavailable')
        writer=self.ui.session_writer=MagicMock()
        def slow_save():
            saving.set();release_save.wait(3)
        writer.close.side_effect=slow_save
        beats=[]
        def beat():
            beats.append(time.monotonic())
            self.root.after(10,beat)
        def pump_until(predicate):
            deadline=time.monotonic()+2
            while not predicate() and time.monotonic()<deadline:
                self.root.update();time.sleep(.01)
            self.assertTrue(predicate())
        try:
            with patch.object(self.root,'destroy') as destroy, patch.object(self.ui,'save_session') as checkpoint:
                self.root.after(10,beat)
                start=time.monotonic();self.ui.close();self.ui.close()
                self.assertLess(time.monotonic()-start,.2)
                pump_until(lambda:len(beats)>=5)
                self.assertFalse(destroy.called)
                release_audio.set();pump_until(saving.is_set)
                count=len(beats);pump_until(lambda:len(beats)>=count+5)
                self.assertFalse(destroy.called)
                release_save.set();pump_until(lambda:destroy.called)
                checkpoint.assert_called_once()
                writer.close.assert_called_once()
        finally:
            release_audio.set();release_save.set();self.ui.session_writer=None

    def test_shutdown_saves_final_session_before_destroy(self):
        self.ui.live.records=[segment(1,'退出前的最终内容')]
        self.ui.live.submitted=self.ui.live.completed=1
        with patch.object(self.root,'destroy') as destroy:
            self.ui.close()
            deadline=time.monotonic()+3
            while not destroy.called and time.monotonic()<deadline:
                self.root.update();time.sleep(.01)
            self.assertTrue(destroy.called)
            payload=self.ui.session_store.load(self.ui.session_id)
            self.assertEqual(payload['segment:1']['body'],'退出前的最终内容')
            self.assertFalse(self.ui.session_writer.thread.is_alive())

if __name__=='__main__':unittest.main()
