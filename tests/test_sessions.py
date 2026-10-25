import urllib.request
import io
import json
from pathlib import Path
import threading
import time
import tkinter as tk
import unittest
import uuid
import zipfile
import shutil
from unittest.mock import patch
import audio_answer as a
import settings_state
from session_support import streaming_events, Cancelled, read_document, local_base, context_prompt, gemini_command
import session_support as support

class SessionTests(unittest.TestCase):
    def test_cli_failure_redacts_credentials_and_explains_quota(self):
        message = support.cli_failure('429 quota exceeded\nAuthorization: Bearer supersecret\nrefresh_token="verysecret"\nhttps://example.test/?key=secret\nme@example.test', 1)
        self.assertIn('额度', message)
        for secret in ('supersecret', 'verysecret', 'key=secret', 'me@example.test'):
            self.assertNotIn(secret, message)

    def test_cli_result_does_not_wait_for_process_exit(self):
        release = threading.Event()
        class Stream:
            def __iter__(self):
                yield b'{"type":"message","role":"assistant","content":"OK"}\n'
                yield b'{"type":"result","status":"success"}\n'
                release.wait(3)
        class Process:
            stdin = io.BytesIO()
            stdout = Stream()
            stderr = io.BytesIO()
            def poll(self): return None
            def kill(self): release.set()
            def wait(self, timeout=None): return 0
        root = a.WORK / ('cli-test-' + uuid.uuid4().hex)
        root.mkdir()
        try:
            with patch.object(support, 'gemini_command', return_value=['node', 'fake.js']), patch.object(support.subprocess, 'Popen', return_value=Process()) as launch:
                started = time.monotonic()
                self.assertEqual(support.cli_answer(root, '@file is literal', '', threading.Event(), lambda _: None), 'OK')
                self.assertLess(time.monotonic()-started, 1)
            env = launch.call_args.kwargs['env']
            self.assertEqual(env['GEMINI_CLI_TRUST_WORKSPACE'], 'true')
            self.assertIn('--policy', launch.call_args.args[0])
            self.assertTrue((root/'work/gemini-qa/.gemini/settings.json').exists())
        finally:
            release.set()
            self.assertTrue(root.resolve().is_relative_to(a.WORK.resolve()))
            shutil.rmtree(root)

    def test_cancel_while_connect_is_blocked(self):
        release, cancel = threading.Event(), threading.Event()
        def blocked(*args, **kwargs):
            release.wait(2)
            return io.BytesIO(b'')
        with patch.object(urllib.request, 'urlopen', side_effect=blocked):
            timer = threading.Timer(.05, cancel.set); timer.start()
            started = time.monotonic()
            try:
                with self.assertRaises(Cancelled):
                    list(streaming_events(None, a.sse_events, cancel))
                self.assertLess(time.monotonic()-started, .7)
            finally:
                release.set(); timer.join()

    def test_keepalives_cannot_extend_total_deadline(self):
        def events(_):
            while True:
                time.sleep(.015)
                yield {'choices': []}
        with patch.object(urllib.request, 'urlopen', return_value=io.BytesIO()):
            with self.assertRaisesRegex(RuntimeError, '总时限'):
                list(streaming_events(None, events, threading.Event(), total_timeout=.08))

    def test_gemini_text_mode_does_not_upload_audio(self):
        event = {'candidates': [{'content': {'parts': [{'text': 'answer'}]}, 'finishReason': 'STOP'}]}
        with patch.object(urllib.request, 'urlopen', return_value=io.BytesIO(('data: '+json.dumps(event)+'\n\n').encode())) as post:
            a.gemini_answer(None, 'fake', 'gemini-3.5-flash-lite', '资料', threading.Event(), lambda _: None, transcript='[麦克风] 问题')
        body = json.loads(post.call_args.args[0].data)
        self.assertNotIn('inlineData', str(body))
        self.assertIn('[麦克风]', body['contents'][0]['parts'][0]['text'])

    def test_local_endpoint_and_no_empty_authorization(self):
        self.assertEqual(local_base('http://localhost:1234'), 'http://localhost:1234/v1')
        for url in ('https://example.com/v1', 'http://user:pass@localhost/v1', 'http://localhost/v1?key=a'):
            with self.assertRaises(ValueError): local_base(url)
        with patch.object(urllib.request, 'urlopen', return_value=io.BytesIO(b'{"data":[{"id":"model@q4"}]}')) as get:
            self.assertEqual(a.list_provider_models('LM Studio', '', base='http://localhost:4321'), {'model@q4'})
        self.assertEqual(get.call_args.args[0].full_url, 'http://localhost:4321/v1/models')
        self.assertIsNone(get.call_args.args[0].get_header('Authorization'))

    def test_context_document_extraction_and_limits(self):
        path = a.WORK / ('fixture-'+uuid.uuid4().hex+'.docx')
        try:
            with zipfile.ZipFile(path, 'w') as z:
                z.writestr('word/document.xml', '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:p><w:r><w:t>个人资料</w:t></w:r></w:p></w:document>')
            self.assertEqual(read_document(path), '个人资料')
            with self.assertRaises(ValueError): read_document(path, limit=2)
        finally:
            path.unlink(missing_ok=True)
        prompt = context_prompt('profile', 'documents', 'summary', list(range(10)))
        payload = json.loads(prompt.split('\n', 1)[1])
        self.assertEqual(payload['本次会话全部对话'], list(range(10)))
        self.assertEqual(payload['资料分析'], 'summary')

class UITests(unittest.TestCase):
    def setUp(self):
        self.patches = [patch('caption_translation.translate', return_value='Translated fixture'), patch('lmstudio_support.capabilities',return_value=('http://127.0.0.1:1234/api/v1',None)), patch.object(a, 'load_settings', return_value=getattr(self,'initial_settings',{'ui_language':'zh'})), patch.object(settings_state, 'load_settings', return_value={}),
                        patch.object(a, 'save_settings'), patch.object(a, 'Capture'), patch.object(a, 'TokenLedger'),
                        patch.object(a.App, 'refresh_devices'), patch.object(a.App, 'listen_hotkey'), patch.object(a.App,'preload_asr'),
                        patch.object(a.App,'prepare_model_context'), patch.object(a.App,'warm_answer_channel'), patch.object(a.App,'maybe_speculate')]
        for p in self.patches: p.start()
        self.root = tk.Tk(); self.root.withdraw()
        self.ui = a.App(self.root)
        self.ui.advanced['spare_session'].set('关闭')
        self.ui.capture.active.return_value = False
        self.ui.mic.active.return_value = False
        self.ui.capture.error = self.ui.mic.error = ''

    def tearDown(self):
        self.ui.cancel_answer()
        self.ui.captions.close()
        self.ui.generation_lanes.close()
        self.ui.live.close()
        self.ui.closed = True
        for identifier in self.root.tk.call('after', 'info'):
            self.root.after_cancel(identifier)
        self.root.destroy()
        for p in reversed(self.patches): p.stop()

    def test_cancel_and_late_worker_cannot_overwrite_new_job(self):
        self.ui.busy = True
        old = self.ui.ask_revision
        self.ui.cancel_answer()
        self.assertFalse(self.ui.busy)
        self.ui.busy = True
        self.ui.job_started = time.monotonic()
        self.ui.put_text('new', replace=True)
        self.ui.events.put(('job', (old, 'text', 'obsolete')))
        self.ui.events.put(('job', (old, 'done', '')))
        self.ui.poll()
        self.assertEqual(self.ui.output_text, 'new')
        self.assertTrue(self.ui.busy)

    def test_watchdog_recovers_without_worker_finishing(self):
        cancel = threading.Event()
        self.ui.jobs[9] = {'done':False, 'started':time.monotonic()-500, 'timeout':1, 'cancel':cancel}
        self.ui.busy = True
        self.ui.poll()
        self.assertFalse(self.ui.busy)
        self.assertTrue(cancel.is_set())
        self.assertIn('达到时限', self.ui.output_text)

    def test_analysis_attaches_to_future_context(self):
        self.ui.provider.set('LM Studio'); self.ui.update_provider()
        self.ui.model.set('test-model')
        self.ui.profile = '学生，学习 Python'
        self.ui.documents = '参考：只使用标准库'
        def answer(provider, transcript, key, model, instructions, cancel, emit, **kw):
            self.assertIn('学生', instructions)
            self.assertIn('只使用标准库', instructions)
            emit('分析结果：注意标准库约束')
        with patch.object(a, 'compatible_answer', side_effect=answer):
            self.ui.ask(analysis=True)
            self.ui.worker.join(2)
            self.ui.poll()
        self.assertFalse(self.ui.busy)
        self.assertIn('标准库约束', self.ui.context_summary)
        self.assertIn('标准库约束', self.ui.context_instructions())

    def test_provider_error_releases_answer_and_allows_retry(self):
        self.ui.provider.set('LM Studio'); self.ui.update_provider(); self.ui.model.set('test-model')
        self.ui.profile = 'test context'
        with patch.object(a, 'compatible_answer', side_effect=RuntimeError('模拟服务超时')):
            self.ui.ask(analysis=True)
            self.ui.worker.join(2)
            self.ui.poll()
        self.assertFalse(self.ui.busy)
        self.assertIn('模拟服务超时', self.ui.output_text)
        def answer(*args, **kwargs):
            args[6]('重试成功')
        with patch.object(a, 'compatible_answer', side_effect=answer):
            self.ui.ask(analysis=True)
            self.ui.worker.join(2)
            self.ui.poll()
        self.assertEqual(self.ui.context_summary, '重试成功')

    def test_two_audio_sources_and_selected_asr_model(self):
        self.ui.provider.set('LM Studio'); self.ui.update_provider(); self.ui.model.set('test-model')
        for capture in (self.ui.capture, self.ui.mic):
            capture.active.return_value = True
            capture.buffer.snapshot.return_value = b'\x20\x00'*a.RATE
            capture.level = 0
        self.ui.advanced['asr_engine'].set('中文 · Zipformer')
        def answer(provider, transcript, key, model, instructions, cancel, emit, **kw):
            self.assertIn('电脑]', transcript); self.assertIn('麦克风]', transcript)
            emit('answer')
        from test_streaming import FakeRecognizer
        with patch.object(self.ui.live, 'factory', return_value=FakeRecognizer()) as asr, patch.object(a, 'compatible_answer', side_effect=answer):
            self.ui.live.configure('中文 · Zipformer')
            for source in ('电脑','麦克风'): self.ui.live.feed(source, b'\x00\x10'*a.RATE)
            self.ui.ask(); self.ui.worker.join(2); self.ui.poll()
        asr.assert_called_once_with('中文 · Zipformer')
        self.assertEqual(len(self.ui.history), 1)
        self.assertFalse(self.ui.busy)

    def test_streaming_selection_persists_and_keeps_text(self):
        from test_streaming import FakeRecognizer
        self.ui.live_text='已有转录'
        self.ui.put_text('已有回答',replace=True)
        with patch.object(self.ui.live,'factory',return_value=FakeRecognizer()), patch.object(a,'save_settings') as save:
            self.ui.advanced['asr_engine'].set('英文 · Zipformer')
            self.ui.change_asr()
            self.ui.save_preferences()
            self.assertEqual(save.call_args.args[1]['advanced']['asr_engine'],'英文 · Zipformer')
        self.assertEqual(self.ui.live.engine,'英文 · Zipformer')
        self.assertEqual(self.ui.live_text,'已有转录')
        self.assertEqual(self.ui.output_text,'已有回答')

    def test_parallel_answers_keep_separate_regions_and_first_continues(self):
        self.ui.provider.set('LM Studio'); self.ui.update_provider()
        self.ui.remember_transcript('共同问题', 88)
        first_started, release = threading.Event(), threading.Event()
        def answer(provider, transcript, key, model, instructions, cancel, emit, **kw):
            if model == 'first':
                emit('FIRST-BEGIN'); first_started.set(); release.wait(2)
                self.assertFalse(cancel.is_set()); emit('FIRST-END')
            else: emit('SECOND-ONLY')
        try:
            with patch.object(a, 'compatible_answer', side_effect=answer):
                self.ui.model.set('first'); self.ui.ask(reuse=True); first_worker = self.ui.worker
                self.assertTrue(first_started.wait(1))
                self.ui.model.set('second'); self.ui.ask(reuse=True); self.ui.worker.join(2)
                self.ui.poll()
                self.assertFalse(self.ui.jobs[1]['done'])
                self.assertTrue(self.ui.jobs[2]['done'])
                release.set(); first_worker.join(2); self.ui.poll()
            text = self.ui.output_text
            self.assertLess(text.index('FIRST-END'), text.index('SECOND-ONLY'))
            self.assertEqual(self.ui.jobs[1]['answer'], 'FIRST-BEGINFIRST-END')
            self.assertFalse(self.ui.busy)
            self.assertEqual(self.ui.token_ledger.record.call_count, 2)
        finally: release.set()

    def test_listening_keeps_text_and_opens_no_windows(self):
        self.ui.put_text('保留的答案', replace=True)
        self.ui.put_text('保留的转录', replace=True, target='transcript')
        children = tuple(self.root.winfo_children())
        self.ui.advanced['source'].set('麦克风')
        self.ui.mic.audio.get_default_input_device_info.return_value = {'index':0,'isLoopbackDevice':False}
        self.ui.toggle_listen()
        self.ui.mic.start.assert_called_once()
        self.assertIn('实时转录中', self.ui.status.get())
        self.assertEqual(tuple(self.root.winfo_children()), children)
        self.assertEqual(self.ui.output_text, '保留的答案')
        self.assertEqual(self.ui.transcript_view, '保留的转录')

    def test_full_hour_history_is_retained_and_sent(self):
        self.ui.provider.set('LM Studio'); self.ui.update_provider(); self.ui.model.set('test-model')
        for i in range(60):
            self.ui.events.put(('completed', (False, self.ui.context_version, f'第{i}分钟的问题', f'第{i}分钟的回答')))
        self.ui.poll()
        self.assertEqual(len(self.ui.history), 60)
        self.ui.remember_transcript('最后一个问题', 999)
        def answer(provider, transcript, key, model, instructions, cancel, emit, **kw):
            self.assertIn('第0分钟的问题', instructions)
            self.assertIn('第59分钟的回答', instructions)
            emit('完整历史已收到')
        with patch.object(a, 'compatible_answer', side_effect=answer):
            self.ui.ask(reuse=True); self.ui.worker.join(2); self.ui.poll()
        self.assertEqual(len(self.ui.history), 61)
        self.assertIn('完整历史已收到', self.ui.history[-1]['回答'])

    def test_cli_model_selection_is_independent_and_used_by_request(self):
        self.ui.advanced['codex_model'].set('selected-codex')
        self.ui.advanced['antigravity_model'].set('selected-antigravity')
        self.ui.profile='context'
        self.ui.provider.set('Codex'); self.ui.update_provider()
        self.assertEqual(self.ui.cli_models(),['selected-codex'])
        with patch.object(a,'codex_answer',return_value='OK') as answer:
            self.ui.ask(analysis=True); self.ui.worker.join(2); self.ui.poll()
        self.assertEqual(answer.call_args.kwargs['model'],'selected-codex')
        self.ui.provider.set('Antigravity（本机登录）'); self.ui.update_provider()
        self.assertEqual(self.ui.cli_models(),['selected-antigravity'])
        self.ui.default_cli_model()
        self.assertEqual(self.ui.advanced['antigravity_model'].get(),'')
        self.assertEqual(self.ui.advanced['codex_model'].get(),'selected-codex')

    def test_reasoning_saved_per_model_and_forwarded(self):
        self.ui.provider.set('Codex'); self.ui.update_provider()
        self.ui.advanced['codex_model'].set('codex-model')
        self.ui.reasoning_selection.set('high'); self.ui.save_reasoning()
        self.ui.provider.set('Kimi'); self.ui.update_provider(); self.ui.model.set('kimi-k3')
        self.ui.reasoning_selection.set('max'); self.ui.save_reasoning()
        self.ui.provider.set('Codex'); self.ui.update_provider()
        self.assertEqual(self.ui.reasoning_selection.get(),'high')
        self.ui.profile='context'
        with patch.object(a,'codex_answer',return_value='OK') as answer:
            self.ui.ask(analysis=True); self.ui.worker.join(2); self.ui.poll()
        self.assertEqual(answer.call_args.kwargs['effort'],'high')
        self.ui.provider.set('Kimi'); self.ui.update_provider()
        self.assertEqual(self.ui.reasoning_selection.get(),'max')

    def test_speed_test_isolated_from_context_and_records_usage(self):
        self.ui.provider.set('LM Studio'); self.ui.update_provider(); self.ui.model.set('speed-model')
        self.ui.profile='PRIVATE PROFILE'; self.ui.documents='PRIVATE DOCUMENT'
        self.ui.show_speed_test()
        def answer(provider,transcript,key,model,instructions,cancel,emit,**kw):
            self.assertEqual(instructions,'')
            self.assertNotIn('PRIVATE',transcript)
            self.assertIn('unique_in_order(items)',transcript)
            self.assertIn('assert',transcript)
            emit('测试答案'); kw['on_usage']({'prompt_tokens':20,'completion_tokens':5,'total_tokens':25})
        with patch.object(a,'compatible_answer',side_effect=answer):
            self.ui.start_speed_test(); self.ui.speed_worker.join(2); self.ui.poll()
        self.assertFalse(self.ui.speed_busy)
        self.assertEqual(len(self.ui.speed_results),1)
        self.assertEqual(self.ui.speed_results[0]['output_tokens'],5)
        self.assertEqual(len(self.ui.jobs),0)
        self.assertEqual(self.ui.history,[])
        self.assertEqual(self.ui.token_ledger.record.call_count,1)
        self.ui.speed_window.destroy(); self.ui.show_speed_test()
        self.assertEqual(len(self.ui.speed_table.get_children()),1)

    def test_speed_window_selection_does_not_change_main_answer_settings(self):
        self.ui.provider.set('LM Studio'); self.ui.update_provider(); self.ui.model.set('main-local')
        self.ui.key.set('local-key')
        self.ui.api_settings['Kimi']={'key':'kimi-test-key','model':'kimi-k3'}
        self.ui.show_speed_test()
        self.ui.speed_provider.set('Kimi'); self.ui.change_speed_provider()
        self.ui.speed_model.set('kimi-k3'); self.ui.speed_effort.set('max')
        def answer(provider,transcript,key,model,instructions,cancel,emit,**kw):
            self.assertEqual((provider,key,model),('Kimi','kimi-test-key','kimi-k3'))
            self.assertEqual(kw['effort'],'max')
            emit('code')
        with patch.object(a,'compatible_answer',side_effect=answer):
            self.ui.start_speed_test(); self.ui.speed_worker.join(2); self.ui.poll()
        self.assertEqual(self.ui.provider.get(),'LM Studio')
        self.assertEqual(self.ui.model.get(),'main-local')
        self.assertEqual(self.ui.key.get(),'local-key')
        self.assertEqual(self.ui.speed_results[-1]['model'],'kimi-k3')
        self.assertEqual(self.ui.speed_results[-1]['status'],'完成')

    def test_clear_context_removes_profile_documents_and_history(self):
        self.ui.profile, self.ui.documents = '测试资料', '参考文档'
        self.ui.history.append({'转录':'q','回答':'a'})
        version = self.ui.context_version
        self.ui.clear_context()
        self.assertEqual((self.ui.profile, self.ui.documents, self.ui.history), ('', '', []))
        self.assertGreater(self.ui.context_version, version)

    def test_switch_model_reanswers_selected_transcript_and_keeps_visible_history(self):
        self.ui.provider.set('LM Studio'); self.ui.update_provider()
        self.ui.remember_transcript('[电脑] 第一个问题', 70)
        self.ui.remember_transcript('[麦克风] 第二个问题', 71)
        self.ui.selected_transcript = 0; self.ui.select_transcript()
        self.ui.put_text('已有回复，不应清空', replace=True)
        calls = []
        def answer(provider, transcript, key, model, instructions, cancel, emit, **kw):
            calls.append((transcript, model))
            emit('回复来自 ' + model)
        with patch.object(a, 'compatible_answer', side_effect=answer), patch.object(a, 'transcribe', side_effect=AssertionError('不应再次转录')):
            for model in ('local-one', 'local-two'):
                self.ui.model.set(model)
                self.ui.ask(reuse=True); self.ui.worker.join(2); self.ui.poll()
        self.assertEqual(calls, [('[电脑] 第一个问题', 'local-one'), ('[电脑] 第一个问题', 'local-two')])
        display = self.ui.output_text
        for text in ('已有回复，不应清空', '回复来自 local-one', '回复来自 local-two'):
            self.assertIn(text, display)
        self.assertGreaterEqual(len(self.ui.transcript_records), 2)
        self.assertFalse(self.ui.busy)

if __name__ == '__main__':
    unittest.main()
