"""First-token latency features: keep-alive pool, Codex spare threads, prompt order, speculative answers."""
import http.server
import json
import pathlib
import sys
import threading
import time
import unittest
import urllib.error
import urllib.request
from unittest.mock import patch

import audio_answer as a
import answer_jobs
import http_pool
from codex_service import CodexService
from session_support import streaming_events
import test_sessions


class Handler(http.server.BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'
    ports = []
    def log_message(self, *args): pass
    def do_POST(self):
        self.rfile.read(int(self.headers.get('Content-Length', 0)))
        Handler.ports.append(self.client_address[1])
        if self.path == '/fail':
            body = b'{"error":{"message":"maximum context length"}}'
            self.send_response(400)
        else:
            body = b'data: {"n":1}\n\ndata: {"n":2}\n\n'
            self.send_response(200)
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class PoolTests(unittest.TestCase):
    def setUp(self):
        Handler.ports = []
        self.server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.base = f'http://127.0.0.1:{self.server.server_port}'
        self.patch = patch.object(urllib.request, 'getproxies', return_value={})
        self.patch.start()
        http_pool.close_all()

    def tearDown(self):
        self.patch.stop()
        http_pool.close_all()
        self.server.shutdown(); self.server.server_close()

    def request(self, path='/stream'):
        return urllib.request.Request(self.base + path, data=b'{}', headers={'Content-Type': 'application/json'})

    def test_sequential_streams_reuse_one_connection(self):
        for _ in range(3):
            events = list(streaming_events(self.request(), a.sse_events, threading.Event(), total_timeout=5))
            self.assertEqual(events, [{'n': 1}, {'n': 2}])
        self.assertEqual(len(Handler.ports), 3)
        self.assertEqual(len(set(Handler.ports)), 1)

    def test_http_error_keeps_body_for_diagnosis(self):
        with self.assertRaises(urllib.error.HTTPError) as caught:
            list(streaming_events(self.request('/fail'), a.sse_events, threading.Event(), total_timeout=5))
        self.assertEqual(caught.exception.code, 400)
        self.assertIn(a.CONTEXT_CAPACITY_MESSAGE, a.compatible_error(caught.exception))

    def test_warm_opens_connection_used_by_next_request(self):
        self.assertTrue(http_pool.warm(self.base + '/v1'))
        deadline = time.monotonic() + 3
        while not http_pool._idle.get(('http', '127.0.0.1', self.server.server_port)) and time.monotonic() < deadline:
            time.sleep(.01)
        self.assertFalse(http_pool.warm(self.base + '/v1'))  # recent idle connection exists
        list(streaming_events(self.request(), a.sse_events, threading.Event(), total_timeout=5))
        self.assertEqual(len(Handler.ports), 1)

    def test_proxy_falls_back_to_urllib(self):
        with patch.object(urllib.request, 'getproxies', return_value={'https': 'http://proxy:8080'}), \
             patch.object(urllib.request, 'proxy_bypass', return_value=False):
            self.assertIsNone(http_pool._target('https://api.deepseek.com/chat/completions'))


class CodexSpareTests(unittest.TestCase):
    def setUp(self):
        self.service = CodexService('', pathlib.Path(__file__).parent,
            command=[sys.executable, '-u', str(pathlib.Path(__file__).with_name('fake_codex_server.py'))])
        self.addCleanup(self.service.close)

    def answer(self, text):
        return self.service.answer(text, 'gpt-6-astra', 'low', threading.Event(), lambda _: None, timeout=5)

    def wait_spares(self, expected):
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            with self.service.lock:
                spares = [thread for _, thread in self.service.spares.get('gpt-6-astra', [])]
            if spares == expected: return
            time.sleep(.01)
        self.fail(f'spares {spares} != {expected}')

    def test_prewarm_creates_one_spare_without_automatic_refill(self):
        self.service.prewarm('gpt-6-astra')
        self.assertEqual(self.service.launches, 1)
        self.wait_spares(['thread1'])
        self.assertEqual(self.answer('one'), 'first:one:last')
        self.wait_spares([])
        self.assertEqual(self.service.launches, 1)

    def test_rejected_spare_falls_back_to_fresh_thread(self):
        self.service.start()
        with self.service.lock:
            self.service.spares['gpt-6-astra'] = [(self.service.launches, 'expired')]
        self.assertEqual(self.answer('two'), 'first:two:last')

    def test_spares_from_previous_process_are_ignored(self):
        self.service.start()
        with self.service.lock:
            self.service.spares['gpt-6-astra'] = [(0, 'old-process')]
        self.assertIsNone(self.service.take_spare('gpt-6-astra'))


class PromptOrderTests(unittest.TestCase):
    def test_reference_material_before_per_turn_instructions(self):
        inputs = dict(profile='P', documents='DOC', summary='', history=[], context_records=[], terms='',
                      images=[], instructions='本轮要求')
        prompt = answer_jobs.build_prompt(inputs, '转录')
        self.assertLess(prompt.index('DOC'), prompt.index('本轮要求'))
        self.assertTrue(prompt.endswith('本轮要求'))

    def test_question_heuristic(self):
        self.assertTrue(answer_jobs.looks_like_question('[10:00 电脑]\n这个函数怎么优化'))
        self.assertTrue(answer_jobs.looks_like_question('What is a closure'))
        self.assertFalse(answer_jobs.looks_like_question('好的，谢谢大家'))


class SpeculationTests(unittest.TestCase):
    setUp = test_sessions.UITests.setUp
    tearDown = test_sessions.UITests.tearDown

    def segment(self):
        from test_streaming import FakeRecognizer
        self.ui.live.factory = lambda selection: FakeRecognizer()
        self.ui.live.configure('中文 · Zipformer')
        self.ui.live.feed('电脑', b'\x00\x10' * a.RATE)
        target = self.ui.live.flush()
        self.ui.live.snapshot(target, threading.Event())
        return self.ui.live.records[-1]

    def prepare(self):
        self.ui.provider.set('LM Studio'); self.ui.update_provider(); self.ui.model.set('test-model')
        self.ui.advanced['question_mode'].set('快速问答')
        self.ui.advanced['speculate'].set('每段定稿')
        self.calls = []
        def answer(provider, transcript, key, model, instructions, cancel, emit, **kw):
            self.calls.append(instructions); emit('预生成答案')
        return patch.object(a, 'compatible_answer', side_effect=answer)

    def test_hotkey_adopts_matching_speculation(self):
        with self.prepare():
            record = self.segment()
            answer_jobs.AnswerJobs.maybe_speculate(self.ui, record)
            spec = self.ui.speculation
            spec.worker.join(2)
            self.ui.ask(); self.ui.worker.join(2); self.ui.poll()
        self.assertEqual(len(self.calls), 1)
        job = self.ui.jobs[self.ui.ask_revision]
        self.assertEqual(job['answer'], '预生成答案')
        self.assertTrue(job['timing'].get('speculative'))
        self.assertEqual(job['timing']['first_total'], 0.0)
        self.assertEqual(len(self.ui.history), 1)
        self.assertIn('预生成答案', self.ui.output_text)

    def test_changed_settings_cancel_speculation_and_request_again(self):
        with self.prepare():
            record = self.segment()
            answer_jobs.AnswerJobs.maybe_speculate(self.ui, record)
            spec = self.ui.speculation
            spec.worker.join(2)
            self.ui.instructions.set('换个要求')
            self.ui.ask(); self.ui.worker.join(2); self.ui.poll()
        self.assertTrue(spec.cancel.is_set())
        self.assertEqual(len(self.calls), 2)
        self.assertIn('换个要求', self.calls[-1])
        self.assertEqual(len(self.ui.history), 1)
        self.assertFalse(self.ui.jobs[self.ui.ask_revision].get('timing', {}).get('speculative'))

    def test_unadopted_speculation_never_reaches_history_or_output(self):
        with self.prepare():
            record = self.segment()
            answer_jobs.AnswerJobs.maybe_speculate(self.ui, record)
            self.ui.speculation.worker.join(2); self.ui.poll()
        self.assertEqual(self.ui.history, [])
        self.assertNotIn('预生成答案', self.ui.output_text)

    def test_off_and_non_question_modes_skip(self):
        with self.prepare():
            record = self.segment()
            self.ui.advanced['speculate'].set('关闭')
            answer_jobs.AnswerJobs.maybe_speculate(self.ui, record)
            self.assertIsNone(getattr(self.ui, 'speculation', None))
            self.ui.advanced['speculate'].set('仅疑问句')
            answer_jobs.AnswerJobs.maybe_speculate(self.ui, dict(record, body='好的谢谢'))
            self.assertIsNone(getattr(self.ui, 'speculation', None))
        self.assertEqual(self.calls, [])


if __name__ == '__main__':
    unittest.main()
