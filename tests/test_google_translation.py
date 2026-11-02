import io
import json
import threading
import unittest
import urllib.error
from unittest.mock import patch

import app_paths
from google_translation import PROVIDER, translate
from session_support import Cancelled
import audio_answer as a
import test_sessions
from glass_bridge import GlassBridge
from caption_translation import translate as caption_translate


def response(text):
    return io.BytesIO(json.dumps({'data': {'translations': [{'translatedText': text}]}}).encode())


class GoogleTranslationTests(unittest.TestCase):
    def test_official_request_and_plain_text_response(self):
        with patch('urllib.request.urlopen', return_value=response('你好 &amp; 世界')) as post:
            result = translate('Hello & world', 'zh', 'test-secret', threading.Event())
        self.assertEqual(result, '你好 & 世界')
        request = post.call_args.args[0]
        self.assertEqual(request.full_url, 'https://translation.googleapis.com/language/translate/v2')
        self.assertNotIn('test-secret', request.full_url)
        self.assertEqual(request.get_header('X-goog-api-key'), 'test-secret')
        self.assertEqual(json.loads(request.data), dict(q='Hello & world', target='zh-CN', model='nmt', format='text'))

    def test_mixed_language_bilingual_has_both_complete_versions(self):
        with patch('urllib.request.urlopen', side_effect=[response('中文全文'), response('Complete English')]) as post:
            self.assertEqual(translate('Hello 你好', 'bilingual', 'key', threading.Event()),
                             '中文：中文全文\nEnglish: Complete English')
        self.assertEqual([json.loads(call.args[0].data)['target'] for call in post.call_args_list], ['zh-CN', 'en'])

    def test_errors_explain_configuration_without_echoing_secret(self):
        for code in (400, 401, 403, 429, 500):
            with self.subTest(code=code), patch('urllib.request.urlopen', side_effect=urllib.error.HTTPError(
                    'https://example.test/?key=test-secret', code, 'test-secret', None, None)):
                with self.assertRaises(RuntimeError) as raised:
                    translate('Hello', 'zh', 'test-secret', threading.Event())
                self.assertIn(str(code), str(raised.exception))
                self.assertNotIn('test-secret', str(raised.exception))

    def test_cancelled_request_and_missing_credentials(self):
        cancel = threading.Event(); cancel.set()
        with patch('urllib.request.urlopen', return_value=response('hello')):
            with self.assertRaises(Cancelled):
                translate('你好', 'en', 'key', cancel)
        with self.assertRaises(ValueError):
            translate('Hello', 'zh', '', threading.Event())

    def test_malformed_or_empty_response_is_not_success(self):
        for raw in (b'{}', b'{invalid', b'{"data":{"translations":[]}}'):
            with patch('urllib.request.urlopen', return_value=io.BytesIO(raw)):
                with self.assertRaisesRegex(RuntimeError, '无效'):
                    translate('Hello', 'zh', 'key', threading.Event())


class GoogleTranslationIntegrationTests(unittest.TestCase):
    setUp = test_sessions.UITests.setUp
    tearDown = test_sessions.UITests.tearDown

    def test_provider_selection_key_privacy_and_answer_independence(self):
        bridge = GlassBridge(self.ui)
        answer = self.ui.provider.get()
        bridge.settings({'caption_provider': PROVIDER, 'google_translation_key': 'private-test-key'})
        inputs, error = self.ui.caption_models.inputs()
        self.assertIsNone(error)
        self.assertEqual((inputs['provider'], inputs['model'], inputs['key']), (PROVIDER, 'nmt', 'private-test-key'))
        self.assertEqual(self.ui.provider.get(), answer)
        self.assertNotIn(PROVIDER, bridge.snapshot()['providers'])
        self.assertIn(PROVIDER, bridge.snapshot()['caption_translation']['providers'])
        self.assertNotIn('private-test-key', str(bridge.snapshot()))
        with patch.object(a, 'save_settings') as save:
            self.ui.remember_keys.set(True); self.ui.save_preferences()
            self.assertEqual(save.call_args.args[1]['google_translation_key'], 'private-test-key')
            self.ui.remember_keys.set(False); self.ui.save_preferences()
            self.assertNotIn('google_translation_key', save.call_args.args[1])

    def test_switching_backend_cancels_old_requests_and_invalidates_cache(self):
        key = ('bilingual', 'Hello')
        cancel = threading.Event()
        self.ui.captions.workers[key] = cancel
        self.ui.captions.cache[key] = 'Old provider result'
        GlassBridge(self.ui).settings({'caption_provider': PROVIDER})
        self.assertTrue(cancel.is_set())
        self.assertFalse(self.ui.captions.cache)
        self.assertIn('Key', self.ui.caption_models.inputs()[1])

    def test_google_route_does_not_send_translation_to_answer_model(self):
        self.ui.google_translation_key.set('test-key')
        self.ui.advanced['caption_provider'].set(PROVIDER)
        inputs, _ = self.ui.caption_models.inputs()
        pieces = []
        with patch('urllib.request.urlopen', return_value=response('你好')), patch.object(a, 'compatible_answer') as llm:
            self.assertEqual(caption_translate(inputs, 'Hello', 'zh', threading.Event(), self.ui, on_partial=pieces.append), '你好')
        self.assertEqual(pieces, ['你好'])
        llm.assert_not_called()


class GoogleTranslationRestoreTests(unittest.TestCase):
    tearDown = test_sessions.UITests.tearDown

    def test_restore_separate_key_and_provider(self):
        self.initial_settings = {'caption_translation': {'caption_provider': PROVIDER, 'caption_model': ''},
                                 'google_translation_key': 'saved-test-key'}
        test_sessions.UITests.setUp(self)
        self.assertEqual(self.ui.caption_models.inputs()[0]['key'], 'saved-test-key')
