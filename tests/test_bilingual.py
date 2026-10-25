"""Bilingual presentation retains source speech and independent output choices."""
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from caption_translation import CaptionPresenter
from prompt_language import output_rule, translation_prompt
from glass_bridge import GlassBridge
import test_sessions


class BilingualCaptionTests(unittest.TestCase):
    def setUp(self):
        self.app = SimpleNamespace(content_language=lambda _: 'bilingual',
                                   locale=SimpleNamespace(language='en'), closing=False)
        self.presenter = CaptionPresenter(self.app)

    def test_drafts_and_pending_translation_keep_original_speech(self):
        text = 'Please explain 这个算法.'
        with patch.object(self.presenter, 'start_next') as start:
            self.assertEqual(self.presenter.body(text, draft=True), text)
            start.assert_not_called()
            self.assertIn(text, self.presenter.body(text))
            self.assertIn(text, self.presenter.body(text))
            start.assert_called_once()

    def test_cached_translation_is_reused_and_failure_keeps_original(self):
        key = ('bilingual', 'Hello')
        self.presenter.cache[key] = '中文：你好\nEnglish: Hello'
        with patch.object(self.presenter, 'start_next') as start:
            self.assertEqual(self.presenter.body('Hello'), self.presenter.cache[key])
            start.assert_not_called()
        self.presenter.failed.add(key)
        self.presenter.cache[key] = '[Translation failed]'
        self.assertEqual(self.presenter.body('Hello'), 'Hello\n[Translation failed]')

    def test_both_provider_instruction_languages_support_bilingual_output(self):
        self.assertIn('Chinese and English', output_rule('en', 'bilingual'))
        self.assertIn('中英双语', output_rule('zh', 'bilingual'))
        self.assertIn('mixes languages', translation_prompt('en', 'bilingual'))
        self.assertIn('不回答', translation_prompt('zh', 'bilingual'))


class BilingualSettingsTests(unittest.TestCase):
    setUp = test_sessions.UITests.setUp
    tearDown = test_sessions.UITests.tearDown

    def test_choices_are_independent_of_interface_and_survive_loading(self):
        bridge = GlassBridge(self.ui)
        try:
            bridge.settings({'caption': '中英双语', 'answer': 'English'})
            self.assertEqual(self.ui.content_language('caption'), 'bilingual')
            self.assertEqual(self.ui.content_language('answer'), 'en')
            bridge.settings({'answer': '中英双语'})
            self.assertEqual(self.ui.request_inputs()[0]['answer_language'], 'bilingual')
            self.ui.change_ui_language('en')
            self.assertEqual(self.ui.content_language('caption'), 'bilingual')
            self.assertEqual(self.ui.content_language('answer'), 'bilingual')
            with self.assertRaises(ValueError):
                bridge.settings({'answer': 'original'})
        finally:
            bridge.close()

class BilingualRestoreTests(unittest.TestCase):
    tearDown = test_sessions.UITests.tearDown

    def setUp(self):
        self.initial_settings = {'ui_language': 'en', 'caption_language': 'bilingual', 'answer_language': 'bilingual'}
        test_sessions.UITests.setUp(self)

    def test_restore(self):
        self.assertEqual(self.ui.content_language('caption'), 'bilingual')
        self.assertEqual(self.ui.content_language('answer'), 'bilingual')
