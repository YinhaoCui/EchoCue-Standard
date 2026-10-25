"""Independent interface, caption and answer language preferences."""
import unittest
from unittest.mock import patch
import audio_answer as a
import test_sessions


class ContentLanguages(unittest.TestCase):
    setUp = test_sessions.UITests.setUp
    tearDown = test_sessions.UITests.tearDown

    def test_ui_switch_preserves_content_preferences_and_translation_cache(self):
        self.ui.caption_language.set('English')
        self.ui.answer_language.set('中文')
        self.ui.captions.cache[('en','你好')]='Hello'
        epoch=self.ui.captions.epoch
        for language in ('en','zh'):
            self.ui.change_ui_language(language)
            self.assertEqual(self.ui.content_language('caption'),'en')
            self.assertEqual(self.ui.content_language('answer'),'zh')
            self.assertEqual(self.ui.captions.body('你好'),'Hello')
            self.assertEqual(self.ui.captions.epoch,epoch)

    def test_original_captions_skip_translation_and_preferences_save_without_keys(self):
        self.ui.caption_language.set('原文')
        self.ui.answer_language.set('English')
        self.ui.remember_keys.set(False)
        self.ui.save_preferences()
        saved=a.save_settings.call_args.args[1]
        self.assertEqual(saved['caption_language'],'original')
        self.assertEqual(saved['answer_language'],'en')
        with patch('caption_translation.translate') as translation:
            self.assertEqual(self.ui.captions.body('你好 Hello'),'你好 Hello')
            translation.assert_not_called()

    def test_answer_language_is_snapshotted_and_reaches_api_system_prompt(self):
        self.ui.provider.set('LM Studio');self.ui.update_provider();self.ui.model.set('fixture')
        self.ui.answer_language.set('English')
        inputs,error=self.ui.request_inputs()
        self.assertIsNone(error)
        self.ui.answer_language.set('中文')
        self.ui.change_content_language('answer')
        self.assertEqual(inputs['answer_language'],'en')
        self.assertIn('Answer language: English',inputs['instructions'])
        import threading,time
        with patch.object(a,'compatible_answer') as answer:
            answer.side_effect=lambda *args,**kw:args[6]('An English answer.')
            self.ui.run_request(inputs,'Question',None,threading.Event(),lambda *args:None,{'start':time.monotonic()},lambda:'fixture')
            self.assertIn('Answer language: English',answer.call_args.kwargs['system_prompt'])
            self.assertNotIn('用中文回答',answer.call_args.kwargs['system_prompt'])

class RestoredLanguages(unittest.TestCase):
    setUp = test_sessions.UITests.setUp
    tearDown = test_sessions.UITests.tearDown
    initial_settings={'ui_language':'en','caption_language':'original','answer_language':'zh'}

    def test_saved_preferences_restore_independently(self):
        self.assertEqual(self.ui.locale.language,'en')
        self.assertEqual(self.ui.content_language('caption'),'original')
        self.assertEqual(self.ui.content_language('answer'),'zh')


if __name__=='__main__':unittest.main()
