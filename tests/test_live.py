import io
import json
import uuid
import shutil
from contextlib import contextmanager
import threading
import unittest
from pathlib import Path
from unittest.mock import patch
import audio_answer as a
import antigravity_support as ag
from live_transcription import LiveTranscriber, append_transcript
from token_usage import TokenLedger, normalize_usage

@contextmanager
def fixture_directory():
    path=a.WORK/('fixture-'+uuid.uuid4().hex)
    path.mkdir()
    try: yield path
    finally:
        assert path.resolve().is_relative_to(a.WORK.resolve())
        shutil.rmtree(path)

class LiveTests(unittest.TestCase):
    def test_timestamp_only_on_source_change(self):
        text,previous='',None
        for stamp,source,body in [('10:00:00','电脑','first'),('10:00:15','电脑','second'),('10:00:30','麦克风','third'),('10:00:45','麦克风','fourth'),('10:01:00','电脑','fifth')]:
            text,previous=append_transcript(text,previous,{'text':f'[{stamp} {source}]\n{body}','source':source,'body':body})
        self.assertEqual(text,'[10:00:00 电脑]\nfirst second\n\n[10:00:30 麦克风]\nthird fourth\n\n[10:01:00 电脑]\nfifth')

    def test_no_application_output_limit_in_requests(self):
        event={'choices':[{'delta':{'content':'完整答案'},'finish_reason':'stop'}]}
        with patch('api_clients.streaming_events',return_value=iter([event])) as stream:
            a.compatible_answer('Kimi','q','fake','kimi-k2.6','',threading.Event(),lambda _:None,max_output=None)
        self.assertNotIn('max_tokens',json.loads(stream.call_args.args[0].data))
        event={'candidates':[{'content':{'parts':[{'text':'完整答案'}]},'finishReason':'STOP'}]}
        with patch('api_clients.streaming_events',return_value=iter([event])) as stream:
            a.gemini_answer(None,'fake','gemini-2.5-flash','',threading.Event(),lambda _:None,transcript='q',max_output=None)
        self.assertNotIn('maxOutputTokens',json.loads(stream.call_args.args[0].data)['generationConfig'])

    def test_pdf_all_pages_and_long_document_are_read(self):
        from session_support import read_document
        from unittest.mock import Mock
        pages=[Mock(extract_text=Mock(return_value=f'PAGE-{i}')) for i in range(150)]
        with patch('pypdf.PdfReader',return_value=Mock(pages=pages)):
            text=read_document('fixture.pdf')
        self.assertIn('PAGE-149',text)
        with fixture_directory() as directory:
            path=directory/'large.txt'
            content='完整资料'*30000
            path.write_text(content,encoding='utf-8')
            self.assertEqual(read_document(path),content)

    def test_caption_updates_before_pause_and_final_replaces_draft(self):
        preview_ready = threading.Event()
        events = []
        def emit(kind, value):
            events.append((kind,value))
            if kind == 'live_partial': preview_ready.set()
        live = LiveTranscriber(lambda *args:'正在说的话', emit, rate=1000)
        try:
            live.feed('电脑', b'\x00\x10'*1000)
            self.assertTrue(preview_ready.wait(2))
            self.assertEqual(live.submitted, 0)
            self.assertEqual(live.records, [])  # Drafts are not duplicated in answer context.
            target = live.flush()
            text = live.snapshot(target, threading.Event())
            self.assertEqual(text.count('正在说的话'), 1)
        finally: live.close()

    def test_pause_transcribes_before_answer_and_snapshot_keeps_every_segment(self):
        calls, emitted = [], []
        def transcribe(pcm, *args):
            calls.append(pcm); return '段落' + str(len(calls))
        live = LiveTranscriber(transcribe, lambda *x: emitted.append(x), rate=1000, max_seconds=1)
        try:
            for _ in range(4): live.feed('电脑', b'\x00\x10'*1000)
            live.feed('麦克风', b'\x00\x10'*100)
            live.feed('麦克风', b'\x00\x00'*650)
            self.assertEqual(live.submitted, 5)  # No answer-button flush required.
            text = live.snapshot(5, threading.Event())
            self.assertEqual(len(calls), 5)
            self.assertEqual(sum(map(len,calls)), 9500)
            self.assertIn('段落1',text); self.assertIn('段落5',text)
            self.assertIn('麦克风',text)
        finally: live.close()

    def test_usage_formats_dedup_unknown_and_persistence(self):
        for raw in ({'prompt_tokens':9,'completion_tokens':3}, {'input_tokens':9,'output_tokens':3},
                    {'promptTokenCount':9,'candidatesTokenCount':3}):
            self.assertEqual(normalize_usage(raw), {'input':9,'output':3})
        with fixture_directory() as tmp:
            path = Path(tmp)/'usage.json'; ledger=TokenLedger(path)
            ledger.record('same','Kimi','m',{'total_tokens':2},'完成')
            ledger.record('same','Kimi','m',{'total_tokens':7},'完成')
            ledger.record('other','Gemini','g',{},'失败')
            restored=TokenLedger(path)
            self.assertEqual(len(restored.rows),2)
            self.assertIn('总计 7',restored.summary())
            self.assertIn('0 次有报告',restored.summary())
            path.write_text('corrupt',encoding='utf-8')
            TokenLedger(path).record('new','a','b',{},'失败')
            self.assertEqual(path.read_text(),'corrupt')

    def test_premature_stream_preserves_partial_text_and_reports_incomplete(self):
        event={'choices':[{'delta':{'content':'部分答案'}}]}
        pieces=[]
        with patch('api_clients.streaming_events',return_value=iter([event])):
            with self.assertRaisesRegex(RuntimeError,'未收到完成标记'):
                a.compatible_answer('LM Studio','q','','local-model','',threading.Event(),pieces.append)
        self.assertEqual(pieces,['部分答案'])

    def test_antigravity_stream_final_suffix_and_usage(self):
        events=[{'event':'step_update','step_update':{'step_type':'agent_response','text_delta':'答'}},
                {'event':'result','result':{'status':'SUCCESS','response':'答案完整','usage':{'input_tokens':3,'output_tokens':4}}}]
        class Process:
            stdin=io.BytesIO()
            stdout=io.BytesIO(('\n'.join(json.dumps(x) for x in events)+'\n').encode())
            stderr=io.BytesIO()
            def poll(self): return 0
            def wait(self,timeout=None): return 0
        pieces=[]; usage=[]
        with fixture_directory() as tmp, patch.object(ag,'find_antigravity',return_value='agy.exe'), patch.object(ag.subprocess,'Popen',return_value=Process()) as launch:
            result=ag.antigravity_answer(Path(tmp),'问题','',threading.Event(),pieces.append,usage.append)
            self.assertEqual(result,'答案完整'); self.assertEqual(''.join(pieces),result)
            self.assertEqual(usage,[{'input_tokens':3,'output_tokens':4}])
            self.assertIn('--disable-slash-commands',launch.call_args.args[0])

if __name__=='__main__': unittest.main()
