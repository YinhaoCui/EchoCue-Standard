import io
import json
import threading
import unittest
import urllib.error
import urllib.parse
from unittest.mock import patch

import app_paths
import web_translation as web
from caption_translation import translate as caption_translate
from session_support import Cancelled
from glass_bridge import GlassBridge
import test_sessions


def response(payload):
    return io.BytesIO(json.dumps(payload, ensure_ascii=False).encode('utf-8'))


def payload(provider, text='你好'):
    if provider == web.GOOGLE:
        return [[[text, 'Hello'], ['！', '!']], None, 'en']
    if provider == web.MICROSOFT:
        return [{'translations': [{'text': text, 'to': 'zh-Hans'}]}]
    return {'translations': [{'text': text}]}


class BuiltinTranslationTests(unittest.TestCase):
    def setUp(self):
        self.cooldown = patch.object(web, '_cooldown', {})
        self.cooldown.start(); self.addCleanup(self.cooldown.stop)

    def test_three_native_protocols_and_no_child_process(self):
        for provider in web.PROVIDERS:
            with self.subTest(provider=provider), patch('urllib.request.urlopen', return_value=response(payload(provider))) as post, \
                    patch('subprocess.Popen') as spawn:
                result = web.translate(provider, 'Hello!', 'zh', threading.Event())
                self.assertEqual(result, '你好！' if provider == web.GOOGLE else '你好')
                request = post.call_args.args[0]
                self.assertNotIn('Hello', request.full_url)
                if provider == web.GOOGLE:
                    form = urllib.parse.parse_qs(request.data.decode())
                    self.assertEqual((form['q'], form['tl'], form['client'], form['sl']),
                                     (['Hello!'], ['zh-CN'], ['gtx'], ['auto']))
                    self.assertIsNone(request.get_header('X-goog-api-key'))
                elif provider == web.MICROSOFT:
                    self.assertTrue(request.full_url.startswith('https://edge.microsoft.com/translate/translatetext?'))
                    self.assertEqual(json.loads(request.data), ['Hello!'])
                    self.assertIn('to=zh-Hans', request.full_url)
                    self.assertIsNone(request.get_header('Authorization'))
                else:
                    body = json.loads(request.data)
                    self.assertEqual((body['text'], body['target_lang'], body['usage_type']),
                                     (['Hello!'], 'zh-Hans', 'translate'))
                    self.assertEqual(request.get_header('Authorization'), 'None')
                    self.assertNotIn('source_lang', body)
                spawn.assert_not_called()

    def test_long_unicode_input_is_complete_and_each_part_fits(self):
        source = 'text 世界🙂 ' * 600
        def translate(request, **kwargs):
            body = json.loads(request.data)
            part = body['text'][0]
            self.assertLessEqual(len(part.encode('utf-16-le')) // 2, 1500)
            return response(payload(web.DEEPL, part))
        with patch('urllib.request.urlopen', side_effect=translate) as post:
            result = web.translate(web.DEEPL, source, 'en', threading.Event())
        self.assertEqual(''.join(json.loads(call.args[0].data)['text'][0] for call in post.call_args_list), source)
        self.assertEqual(result.replace('\n', ''), source)
        self.assertGreater(post.call_count, 1)

    def test_bilingual_has_two_complete_target_versions(self):
        with patch('urllib.request.urlopen', side_effect=[response(payload(web.MICROSOFT, '中文全文')),
                                                         response(payload(web.MICROSOFT, 'Complete English'))]) as post:
            result = web.translate(web.MICROSOFT, 'Hello 世界', 'bilingual', threading.Event())
        self.assertEqual(result, '中文：中文全文\nEnglish: Complete English')
        self.assertIn('to=zh-Hans', post.call_args_list[0].args[0].full_url)
        self.assertIn('to=en', post.call_args_list[1].args[0].full_url)

    def test_429_honors_retry_after_and_does_not_retry_or_affect_other_provider(self):
        error = urllib.error.HTTPError('https://example.test/?secret', 429, 'secret', {'Retry-After': '120'}, None)
        with patch.object(web.time, 'monotonic', return_value=100), patch('urllib.request.urlopen', side_effect=error) as post:
            with self.assertRaisesRegex(RuntimeError, 'HTTP 429') as raised:
                web.translate(web.DEEPL, 'Hello', 'zh', threading.Event())
            self.assertNotIn('secret', str(raised.exception))
            with self.assertRaisesRegex(RuntimeError, '121 秒'):
                web.translate(web.DEEPL, 'Hello again', 'zh', threading.Event())
            post.assert_called_once()
            self.assertNotIn(web.GOOGLE, web._cooldown)
            self.assertEqual(web._cooldown[web.DEEPL], 220)

    def test_invalid_or_empty_response_is_not_success(self):
        for provider in web.PROVIDERS:
            empty = [[['', 'Hello']]] if provider == web.GOOGLE else payload(provider, '')
            for data in ({}, [], 'not a translation', [['invalid segment']], empty,
                         {'translations': [{'text': 'one'}, {'text': 'extra'}]}):
                with self.subTest(provider=provider, data=data), patch('urllib.request.urlopen', return_value=response(data)):
                    with self.assertRaises(RuntimeError):
                        web.translate(provider, 'Hello', 'zh', threading.Event())

    def test_cancelled_invalid_and_oversized_requests_do_not_succeed(self):
        cancel = threading.Event(); cancel.set()
        with patch('urllib.request.urlopen') as request:
            with self.assertRaises(Cancelled):
                web.translate(web.GOOGLE, 'Hello', 'zh', cancel)
            with self.assertRaises(ValueError):
                web.translate('unknown', 'Hello', 'zh', threading.Event())
            request.assert_not_called()
        with patch('urllib.request.urlopen', return_value=io.BytesIO(b' ' * (1024 * 1024 + 1))):
            with self.assertRaises(RuntimeError):
                web.translate(web.GOOGLE, 'Hello', 'zh', threading.Event())


class BuiltinCaptionIntegrationTests(unittest.TestCase):
    setUp = test_sessions.UITests.setUp
    tearDown = test_sessions.UITests.tearDown

    def test_selection_credentials_route_and_answer_isolation(self):
        import audio_answer
        answer = self.ui.provider.get()
        bridge = GlassBridge(self.ui)
        for provider in web.PROVIDERS:
            with self.subTest(provider=provider):
                bridge.settings(dict(caption_provider=provider, caption_model=''))
                inputs, error = self.ui.caption_models.inputs()
                self.assertIsNone(error)
                self.assertEqual((inputs['key'], inputs['options']), ('', {}))
                state = bridge.snapshot()['caption_translation']
                self.assertTrue(state['dedicated']); self.assertTrue(state['builtin'])
                self.assertNotIn(provider, bridge.snapshot()['providers'])
                pieces = []
                with patch('urllib.request.urlopen', return_value=response(payload(provider))) as request, \
                        patch.object(audio_answer, 'compatible_answer') as llm:
                    result = caption_translate(inputs, 'Hello', 'zh', threading.Event(), self.ui, pieces.append)
                self.assertEqual(pieces, [result])
                llm.assert_not_called()
                self.assertNotIn('must-not-send', str(request.call_args))
                self.assertEqual(self.ui.provider.get(), answer)
                with patch.object(audio_answer, 'save_settings') as save:
                    self.ui.save_preferences()
                    self.assertEqual(save.call_args.args[1]['caption_translation']['caption_provider'], provider)


class BuiltinCaptionRestoreTests(unittest.TestCase):
    tearDown = test_sessions.UITests.tearDown

    def restore_removed(self, provider, replacement):
        self.initial_settings = {'caption_translation': {'caption_provider': provider, 'caption_model': 'old-model'},
                                 'google_translation_key': 'obsolete-key', 'dlx_token': 'obsolete-token'}
        test_sessions.UITests.setUp(self)
        inputs, error = self.ui.caption_models.inputs()
        self.assertIsNone(error)
        self.assertEqual((inputs['provider'], inputs['model'], inputs['key'], inputs['options']),
                         (replacement, 'web', '', {}))
        self.assertEqual(self.ui.advanced['caption_model'].get(), '')
        with patch('audio_answer.save_settings') as save:
            self.ui.save_preferences()
        saved = save.call_args.args[1]
        for key in ('dlx_token', 'dlx_url', 'google_translation_key'):
            self.assertNotIn(key, saved)
            self.assertNotIn(key, saved['caption_translation'])

    def test_migrate_removed_dlx_to_native_deepl(self):
        self.restore_removed('DLX', web.DEEPL)

    def test_migrate_removed_cloud_to_native_google(self):
        self.restore_removed('Google Cloud Translation', web.GOOGLE)

    def test_restore_native_provider_without_keys(self):
        self.initial_settings = {'caption_translation': {'caption_provider': web.MICROSOFT, 'caption_model': ''}}
        test_sessions.UITests.setUp(self)
        inputs, error = self.ui.caption_models.inputs()
        self.assertIsNone(error)
        self.assertEqual((inputs['provider'], inputs['key']), (web.MICROSOFT, ''))
