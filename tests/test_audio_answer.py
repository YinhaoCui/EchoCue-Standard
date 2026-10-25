import urllib.request
import io
import json
import threading
import unittest
import urllib.error
import wave
from pathlib import Path
import uuid
from account_support import UsageLedger, format_codex_account
from unittest.mock import patch
import audio_answer as app


class Tests(unittest.TestCase):
    def test_catalog_categories_and_media_filter(self):
        from model_catalog import select_models
        self.assertIn('kimi-k2.7-code-highspeed', select_models('Kimi', category='Coding'))
        self.assertNotIn('kimi-k3', select_models('Kimi', category='快速 / 省钱'))
        self.assertEqual(select_models('Gemini', ['new-model', 'gemini-flash-image', 'gemini-live', 'gemini-omni-1'], '未分类'), ['new-model'])

    def test_kimi_payloads_and_reasoning(self):
        from model_catalog import thinking_options
        self.assertEqual(thinking_options('Kimi', 'kimi-k3'), {'reasoning_effort': 'low'})
        self.assertEqual(thinking_options('Kimi', 'kimi-k2.7-code-highspeed'), {})
        self.assertEqual(thinking_options('Kimi', 'kimi-k2.6', True), {'thinking': {'type': 'enabled'}})
        self.assertEqual(thinking_options('通义千问（北京）', 'qwen3.8-flash', True), {'enable_thinking': True})
        self.assertEqual(thinking_options('DeepSeek', 'deepseek-v4-pro', True), {'thinking': {'type': 'enabled'}})
        event = {'choices': [{'delta': {'content': 'OK'}, 'finish_reason': 'stop'}]}
        with patch.object(urllib.request, 'urlopen', return_value=io.BytesIO(('data: '+json.dumps(event)+'\n\n').encode())) as post:
            app.compatible_answer('Kimi', '文字', 'fake-key', 'kimi-k3', '', threading.Event(), lambda _: None, reasoning=True)
        req = post.call_args.args[0]
        body = json.loads(req.data)
        self.assertEqual(req.full_url, 'https://api.moonshot.cn/v1/chat/completions')
        self.assertEqual(body['reasoning_effort'], 'high')
        self.assertNotIn('thinking', body)
        self.assertGreaterEqual(body['max_tokens'], 8192)

    def test_quota_percentages_and_missing_values(self):
        text = format_codex_account({'rateLimitsByLimitId': {'codex': {'primary': {
            'usedPercent': 37, 'windowDurationMins': 300, 'resetsAt': None}, 'secondary': None}}}, {})
        self.assertIn('已用 37%', text)
        self.assertIn('剩余 63%', text)
        self.assertIn('5 小时', text)
        self.assertIn('未提供', text)
        self.assertIn('剩余未知', format_codex_account({}, {}))

    def test_usage_ledger_tracks_failures_without_inventing_tokens(self):
        path = app.WORK / ('test-usage-' + uuid.uuid4().hex + '.json')
        try:
            ledger = UsageLedger(path)
            ledger.record('test-model', {'promptTokenCount': 100, 'candidatesTokenCount': 20,
                                        'thoughtsTokenCount': 5, 'totalTokenCount': 125}, True)
            ledger.record('test-model', {}, False)
            restored = UsageLedger(path).data['models']['test-model']
            self.assertEqual(restored['total'], 125)
            self.assertEqual(restored['requests'], 2)
            self.assertEqual(restored['completed'], 1)
            self.assertEqual(restored['reported'], 1)
        finally:
            path.unlink(missing_ok=True)

    def test_fast_mode_and_usage_callback(self):
        event = {'candidates': [{'content': {'parts': [{'text': 'answer'}]}, 'finishReason':'STOP'}],
                 'usageMetadata': {'promptTokenCount': 10, 'totalTokenCount': 12}}
        seen = []
        with patch.object(urllib.request, 'urlopen', return_value=io.BytesIO(('data: '+json.dumps(event)+'\n\n').encode())) as request:
            app.gemini_answer(b'00', 'key', 'gemini-2.5-flash-lite', '', threading.Event(), lambda _: None,
                              fast=True, on_usage=seen.append)
        self.assertEqual(seen, [event['usageMetadata']])
        self.assertEqual(json.loads(request.call_args.args[0].data)['generationConfig']['thinkingConfig'], {'thinkingBudget': 0})

    def test_gemini_model_list_paginates_and_filters(self):
        pages = [{'models': [{'name': 'models/a', 'supportedGenerationMethods': ['generateContent']}], 'nextPageToken': 'next'},
                 {'models': [{'name': 'models/b', 'supportedGenerationMethods': ['embedContent']},
                             {'name': 'models/c', 'supportedGenerationMethods': ['generateContent']}]}]
        with patch.object(urllib.request, 'urlopen', side_effect=[io.BytesIO(json.dumps(p).encode()) for p in pages]) as get:
            self.assertEqual(app.list_gemini_models('secret'), {'a', 'c'})
        self.assertIn('pageToken=next', get.call_args.args[0].full_url)
        self.assertNotIn('secret', get.call_args.args[0].full_url)

    def test_invalid_key_is_distinct_from_quota_or_access_denied(self):
        invalid = urllib.error.HTTPError('', 400, '', {}, io.BytesIO(json.dumps({'error': {'details': [{'reason': 'API_KEY_INVALID'}]}}).encode()))
        self.assertIn('无效', app.gemini_http_error(invalid))
        quota = urllib.error.HTTPError('', 429, '', {}, io.BytesIO(b'{}'))
        self.assertIn('不代表', app.gemini_http_error(quota))
        denied = urllib.error.HTTPError('', 403, '', {}, io.BytesIO(b'{}'))
        self.assertIn('不一定', app.gemini_http_error(denied))

    def test_chinese_provider_sends_own_key_and_only_transcript(self):
        for provider, host in [('DeepSeek', 'api.deepseek.com'), ('通义千问（北京）', 'dashscope.aliyuncs.com')]:
            event = {'choices': [{'delta': {'content': '回答'}, 'finish_reason': 'stop'}]}
            stream = ('data: ' + json.dumps(event) + '\n\ndata: [DONE]\n\n').encode()
            with patch.object(urllib.request, 'urlopen', return_value=io.BytesIO(stream)) as post:
                self.assertEqual(app.compatible_answer(provider, '转录文字', 'own-key', next(iter(app.API_PROVIDERS[provider]['models'])), '', threading.Event(), lambda _: None), '回答')
            request = post.call_args.args[0]
            self.assertIn(host, request.full_url)
            self.assertEqual(request.get_header('Authorization'), 'Bearer own-key')
            body = json.loads(request.data)
            self.assertIn('转录文字', body['messages'][1]['content'])
            self.assertNotIn('inlineData', str(body))
            if provider == 'DeepSeek':
                self.assertEqual(body['thinking'], {'type': 'disabled'})

    def test_empty_compatible_output_is_not_success(self):
        with patch.object(urllib.request, 'urlopen', return_value=io.BytesIO(b'data: {"choices":[]}\n\n')):
            with self.assertRaisesRegex(RuntimeError, '未返回'):
                app.compatible_answer('DeepSeek', '', 'key', 'deepseek-flash', '', threading.Event(), lambda _: None, probe=True)

    def test_rolling_window_discards_stale_audio_and_caps_length(self):
        ring = app.AudioBuffer(seconds=120)
        ring.append(b'a' * 32000, now=1)
        ring.append(b'b' * 64000, now=100)
        self.assertEqual(ring.snapshot(1, now=100), b'b' * 32000)
        self.assertEqual(ring.snapshot(30, now=140), b'')
        ring.clear()
        self.assertEqual(ring.snapshot(120, now=100), b'')

    def test_wav_is_mono_16khz_and_preserves_pcm(self):
        pcm = b'\x01\x02' * 16000
        with wave.open(io.BytesIO(app.wav_bytes(pcm))) as reader:
            self.assertEqual((reader.getnchannels(), reader.getsampwidth(), reader.getframerate()), (1, 2, 16000))
            self.assertEqual(reader.readframes(16000), pcm)

    def test_sse_parses_utf8_and_ignores_comments(self):
        raw = ': ping\n\ndata: {"text":"中文"}\n\ndata: {"text":"next"}\n\n'
        self.assertEqual(list(app.sse_events(io.BytesIO(raw.encode()))), [{'text': '中文'}, {'text': 'next'}])

    def test_gemini_request_has_header_key_and_audio_no_thought_output(self):
        event = {'candidates': [{'content': {'parts': [{'text': 'private', 'thought': True}, {'text': '答案'}]}, 'finishReason': 'STOP'}]}
        received = []
        with patch.object(urllib.request, 'urlopen', return_value=io.BytesIO(('data: ' + json.dumps(event) + '\n\n').encode())) as request:
            result = app.gemini_answer(b'\x00\x01' * 16000, 'secret-test-key', 'gemini-3.8-flash', '', threading.Event(), received.append)
        self.assertEqual(result, '答案')
        self.assertEqual(received, ['答案'])
        sent = request.call_args.args[0]
        self.assertNotIn('secret-test-key', sent.full_url)
        self.assertEqual(sent.get_header('X-goog-api-key'), 'secret-test-key')
        self.assertEqual(json.loads(sent.data)['contents'][0]['parts'][1]['inlineData']['mimeType'], 'audio/wav')

    def test_rate_limit_is_actionable_without_echoing_key(self):
        error = urllib.error.HTTPError('https://example.com', 429, 'secret', {}, None)
        with patch.object(urllib.request, 'urlopen', side_effect=error):
            with self.assertRaisesRegex(RuntimeError, '免费额度'):
                app.gemini_answer(b'00', 'secret', 'gemini-3.8-flash', '', threading.Event(), lambda _: None)

    def test_codex_receives_transcript_through_persistent_service(self):
        with patch('api_clients.find_codex',return_value='codex.exe'),patch('codex_service.get_service') as service:
            service.return_value.answer.return_value='答案'
            result=app.codex_answer('问题是什么？','简短',threading.Event(),model='selected-model')
        self.assertEqual(result,'答案')
        args=service.return_value.answer.call_args.args
        self.assertIn('问题是什么？',args[0])
        self.assertEqual(args[1],'selected-model')


if __name__ == '__main__':
    unittest.main()
