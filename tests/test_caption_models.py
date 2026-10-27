"""Independent caption credentials, model catalogs, persistence and low-effort routing."""
import threading
import time
import unittest
from unittest.mock import patch

import audio_answer as a
import providers
import test_sessions
from caption_models import fast_model
from glass_bridge import GlassBridge


class CaptionModelTests(unittest.TestCase):
    setUp = test_sessions.UITests.setUp
    tearDown = test_sessions.UITests.tearDown

    def select(self, provider, model=''):
        self.ui.advanced['caption_provider'].set(provider)
        self.ui.advanced['caption_model'].set(model)

    def test_caption_api_and_effort_are_independent_of_high_effort_answer(self):
        self.ui.provider.set('Codex'); self.ui.update_provider()
        self.ui.reasoning_selection.set('high')
        self.ui.api_settings['DeepSeek']['key'] = 'translation-test-key'
        self.select('DeepSeek', 'deepseek-flash')
        answer_before = self.ui.request_inputs()[0]
        caption, error = self.ui.caption_models.inputs()
        self.assertIsNone(error)
        self.assertEqual((caption['provider'], caption['model'], caption['key'], caption['effort']),
                         ('DeepSeek', 'deepseek-flash', 'translation-test-key', '关闭'))
        for field in ('history', 'profile', 'documents', 'images', 'session_key'):
            self.assertNotIn(field, caption)
        answer_after = self.ui.request_inputs()[0]
        for field in ('provider', 'model', 'effort', 'options', 'session_key'):
            self.assertEqual(answer_after[field], answer_before[field])

    def test_auto_uses_fast_catalog_entry_and_manual_model_is_preserved(self):
        self.ui.key.set('fixture-key')
        self.select('Gemini')
        identity = self.ui.model_catalog_key('Gemini')
        self.ui.discovered_models[identity] = ['gemini-2.5-pro', 'gemini-2.5-flash-lite']
        inputs, error = self.ui.caption_models.inputs()
        self.assertIsNone(error)
        self.assertEqual((inputs['model'], inputs['effort']), ('gemini-2.5-flash-lite', '关闭'))
        self.ui.advanced['caption_model'].set('custom-model')
        self.assertEqual(self.ui.caption_models.inputs()[0]['model'], 'custom-model')
        self.assertEqual(self.ui.advanced['caption_model'].get(), 'custom-model')

    def test_cli_model_override_and_capabilities_do_not_change_answer(self):
        self.ui.advanced['codex_model'].set('answer-model')
        self.ui.codex_capabilities['translation-model'] = ['medium', 'low']
        self.select('Codex', 'translation-model')
        inputs, error = self.ui.caption_models.inputs()
        self.assertIsNone(error)
        self.assertEqual(inputs['options']['codex_model'], 'translation-model')
        self.assertEqual(inputs['effort'], 'low')
        self.assertEqual(self.ui.advanced['codex_model'].get(), 'answer-model')
        self.select(providers.CLAUDE)
        self.assertEqual(self.ui.caption_models.inputs()[0]['model'], 'haiku')

    def test_auto_with_unknown_cli_catalog_does_not_invent_a_model(self):
        self.ui.advanced['codex_model'].set('custom-answer')
        self.select('Codex')
        self.assertEqual(self.ui.caption_models.inputs()[0]['model'], 'custom-answer')
        self.assertEqual(fast_model('Codex', []), '')

    def test_catalog_identity_changes_with_key_and_local_address(self):
        self.select('DeepSeek')
        self.ui.api_settings['DeepSeek']['key'] = 'old-key'
        self.ui.discovered_models[self.ui.model_catalog_key('DeepSeek')] = ['old-model']
        self.ui.api_settings['DeepSeek']['key'] = 'new-key'
        self.assertNotIn('old-model', self.ui.caption_models.state()['models'])
        self.select('LM Studio', 'custom-local')
        self.ui.advanced['lm_base'].set('http://127.0.0.1:1234/v1')
        old = self.ui.caption_models.identity('LM Studio')
        self.ui.discovered_models[old] = ['old-local-model']
        self.ui.advanced['lm_base'].set('http://127.0.0.1:1235/v1')
        self.assertNotEqual(old, self.ui.caption_models.identity('LM Studio'))
        self.assertNotIn('old-local-model', self.ui.caption_models.state()['models'])

    def test_missing_key_and_empty_successful_catalog_are_explicit_errors(self):
        self.select('DeepSeek')
        self.ui.api_settings['DeepSeek']['key'] = ''
        self.assertIn('Key', self.ui.caption_models.inputs()[1])
        self.ui.api_settings['DeepSeek']['key'] = 'fixture-key'
        self.ui.discovered_models[self.ui.model_catalog_key('DeepSeek')] = []
        self.assertEqual(self.ui.caption_models.state()['models'], [])
        self.assertIn('模型', self.ui.caption_models.inputs()[1])

    def test_live_key_is_used_and_never_exposed_in_web_state(self):
        self.ui.provider.set('Gemini'); self.ui.update_provider()
        self.ui.key.set('unsaved-live-key')
        self.select('Gemini', 'gemini-2.5-flash')
        self.assertEqual(self.ui.caption_models.inputs()[0]['key'], 'unsaved-live-key')
        self.assertNotIn('unsaved-live-key', str(GlassBridge(self.ui).snapshot()))

    def test_refresh_is_independent_and_stale_results_stay_in_their_identity(self):
        self.select('DeepSeek', 'custom-choice')
        self.ui.api_settings['DeepSeek']['key'] = 'fixture-key'
        old = self.ui.caption_models.identity('DeepSeek')
        answer_provider = self.ui.provider.get()
        started, release = threading.Event(), threading.Event()
        def read(*args, **kwargs):
            started.set()
            if not release.wait(3):
                raise RuntimeError('fixture timed out')
            return ['new-model']
        with patch.object(a, 'list_provider_models', side_effect=read) as request:
            self.ui.caption_models.refresh()
            self.assertTrue(started.wait(3))
            self.ui.caption_models.refresh()
            self.ui.api_settings['DeepSeek']['key'] = 'changed-key'
            release.set()
            deadline = time.monotonic() + 3
            while time.monotonic() < deadline:
                kind, result = self.ui.events.get(timeout=3)
                if kind == 'caption_models':
                    self.ui.handle_event(kind, result)
                    break
            else:
                self.fail('No caption catalog event')
            request.assert_called_once()
        self.assertEqual(self.ui.discovered_models[old], ['new-model'])
        self.assertNotIn('new-model', self.ui.caption_models.state()['models'])
        self.assertEqual(self.ui.advanced['caption_model'].get(), 'custom-choice')
        self.assertEqual(self.ui.provider.get(), answer_provider)

    def test_refresh_failure_retains_catalog_and_empty_success_replaces_it(self):
        self.select('DeepSeek'); self.ui.api_settings['DeepSeek']['key'] = 'fixture-key'
        identity = self.ui.caption_models.identity('DeepSeek')
        self.ui.discovered_models[identity] = ['previous-model']
        self.ui.caption_models.receive(('DeepSeek', identity, None, None, 'Refresh failed'))
        self.assertEqual(self.ui.caption_models.state()['models'], ['previous-model'])
        self.ui.caption_models.receive(('DeepSeek', identity, [], None, ''))
        self.assertEqual(self.ui.caption_models.state()['models'], [])

    def test_settings_validation_is_atomic_and_answers_are_unchanged(self):
        bridge = GlassBridge(self.ui)
        before = (self.ui.provider.get(), self.ui.model.get(), self.ui.reasoning_selection.get())
        bridge.settings({'caption_provider': 'DeepSeek', 'caption_model': 'custom-model'})
        self.assertEqual((self.ui.provider.get(), self.ui.model.get(), self.ui.reasoning_selection.get()), before)
        with self.assertRaises(ValueError):
            bridge.settings({'caption_provider': 'Gemini', 'caption_model': 'bad\nmodel'})
        self.assertEqual(self.ui.advanced['caption_provider'].get(), 'DeepSeek')
        with self.assertRaises(ValueError):
            bridge.settings({'caption_provider': 'Unknown provider'})

    def test_preferences_keep_nonsecret_translation_selection_without_keys(self):
        self.select('DeepSeek', 'custom-model')
        self.ui.remember_keys.set(False)
        with patch.object(a, 'save_settings') as save:
            self.assertTrue(self.ui.save_preferences())
        saved = save.call_args.args[1]
        self.assertEqual(saved['caption_translation'], {'caption_provider': 'DeepSeek', 'caption_model': 'custom-model'})
        self.assertNotIn('apis', saved)

    def test_meeting_recap_still_uses_answer_model_and_reasoning(self):
        self.ui.provider.set('Codex'); self.ui.update_provider()
        self.ui.advanced['codex_model'].set('original-answer-model')
        self.ui.reasoning_selection.set('high')
        self.ui.api_settings['DeepSeek']['key'] = 'fixture-key'
        self.select('DeepSeek', 'deepseek-flash')
        with patch.object(self.ui, 'run_request') as run:
            self.ui.ask(transcript_override='Meeting transcript', instruction_override='Summarize', purpose='recap')
            self.ui.worker.join(3)
        inputs = run.call_args.args[0]
        self.assertEqual(inputs['provider'], 'Codex')
        self.assertEqual(inputs['options']['codex_model'], 'original-answer-model')
        self.assertEqual(inputs['effort'], 'high')
        self.assertEqual(inputs['profile'], '')


class CaptionModelRestoreTests(unittest.TestCase):
    tearDown = test_sessions.UITests.tearDown

    def setUp(self):
        self.initial_settings = {'ui_language': 'zh', 'caption_translation': {
            'caption_provider': 'DeepSeek', 'caption_model': 'saved-custom-model'}}
        test_sessions.UITests.setUp(self)

    def test_restore(self):
        self.assertEqual(self.ui.advanced['caption_provider'].get(), 'DeepSeek')
        self.assertEqual(self.ui.advanced['caption_model'].get(), 'saved-custom-model')


if __name__ == '__main__':
    unittest.main()
