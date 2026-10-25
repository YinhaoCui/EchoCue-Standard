"""Styles remain non-secret preferences; built-in prompts use the real request path."""
import unittest
import audio_answer as a
import test_sessions
from glass_bridge import GlassBridge, listen_layout
from prompt_templates import builtin_prompts
from settings_state import presentation_value


class PresentationValidationTests(unittest.TestCase):
    def test_valid_choices_and_split_limits(self):
        self.assertEqual(presentation_value('ui_theme', 'midnight'), 'midnight')
        self.assertEqual(presentation_value('midnight_split', 65), '65')
        self.assertEqual(listen_layout('0,0,0,280,400'), '0,0,0,280,400')
        for key, value in [('ui_theme', 'other'), ('midnight_split', 'nan'),
                           ('midnight_split', 24), ('midnight_split', 66)]:
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                presentation_value(key, value)

    def test_builtin_catalog_is_complete_and_returns_independent_entries(self):
        prompts = builtin_prompts()
        self.assertEqual({p['id'] for p in prompts},
                         {'general', 'coding', 'interview', 'translate', 'meeting', 'learning', 'writing'})
        self.assertEqual(len(prompts), 7)
        for entry in prompts:
            self.assertTrue(entry['name'] and entry['name_zh'] and entry['text'])
            self.assertIn('selected answer language', entry['text'])
        prompts[0]['text'] = 'changed'
        self.assertNotEqual(builtin_prompts()[0]['text'], 'changed')


class PresentationSavingTests(unittest.TestCase):
    setUp = test_sessions.UITests.setUp
    tearDown = test_sessions.UITests.tearDown

    def test_theme_saved_without_credentials_and_restored(self):
        bridge = GlassBridge.__new__(GlassBridge)
        bridge.app = self.ui
        bridge.window_state = {}
        self.ui.remember_keys.set(False)
        bridge.settings({'ui_theme': 'midnight', 'midnight_split': '47'})
        payload = a.save_settings.call_args.args[1]
        self.assertNotIn('apis', payload)
        self.assertEqual(payload['layout']['ui_theme'], 'midnight')
        self.assertEqual(payload['layout']['midnight_split'], '47')
        self.ui.saved = payload
        self.ui.init_advanced()
        self.assertEqual(self.ui.advanced['ui_theme'].get(), 'midnight')
        self.assertEqual(self.ui.advanced['midnight_split'].get(), '47')

    def test_invalid_style_does_not_apply_other_changes(self):
        bridge = GlassBridge.__new__(GlassBridge)
        bridge.app = self.ui
        bridge.window_state = {}
        with self.assertRaises(ValueError):
            bridge.settings({'ui_theme': 'unknown', 'midnight_split': '50'})
        self.assertEqual(self.ui.advanced['ui_theme'].get(), 'classic')
        self.assertEqual(self.ui.advanced['midnight_split'].get(), '40')
        self.ui.saved = {'layout': {'ui_theme': 'broken', 'midnight_split': 'inf'}}
        self.ui.init_advanced()
        self.assertEqual(self.ui.advanced['ui_theme'].get(), 'classic')
        self.assertEqual(self.ui.advanced['midnight_split'].get(), '40')

    def test_every_builtin_prompt_reaches_both_prompt_builders(self):
        from answer_jobs import build_prompt
        from generation_context import ContextPrompt
        bridge = GlassBridge(self.ui)
        try:
            self.ui.provider.set('Codex')
            self.assertEqual(len(bridge.snapshot()['prompt_presets']), 7)
            for preset in builtin_prompts():
                with self.subTest(preset=preset['id']):
                    bridge.command(dict(action='apply_context', id=preset['id'], version=self.ui.context_version,
                                        values=dict(instructions=preset['text'])))
                    inputs, error = self.ui.request_inputs()
                    self.assertIsNone(error)
                    self.assertIn(preset['text'], build_prompt(inputs, 'question'))
                    self.assertIn(preset['text'], ContextPrompt(inputs, 'question', 'SYSTEM').state['instructions'])
        finally:
            bridge.close()
