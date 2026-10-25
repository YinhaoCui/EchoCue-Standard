import threading
import unittest
from unittest.mock import patch

import audio_answer as a
import providers


class ProviderTableTests(unittest.TestCase):
    def test_every_provider_is_listed_once_cli_first(self):
        self.assertEqual(len(providers.NAMES), len(set(providers.NAMES)))
        self.assertEqual(providers.NAMES[:len(providers.CLI_PROVIDERS)], providers.CLI_PROVIDERS)
        self.assertEqual(list(a.API_PROVIDERS), providers.API_NAMES)
        self.assertEqual(a.SPECIAL_PROVIDERS, providers.CLI_PROVIDERS)

    def test_cli_providers_have_model_options_and_api_providers_do_not(self):
        for name in providers.CLI_PROVIDERS:
            self.assertTrue(providers.model_option(name).endswith('_model'))
        for name in providers.API_NAMES:
            with self.assertRaises(KeyError):
                providers.model_option(name)
        self.assertEqual(len(set(providers.MODEL_OPTIONS)), len(providers.MODEL_OPTIONS))

    def test_interface_strings_are_translated(self):
        from locale_catalog import EN
        for name in providers.NAMES:
            if any('\u4e00' <= ch <= '\u9fff' for ch in name):
                self.assertIn(name, EN)

    def test_old_saved_names_are_migrated(self):
        self.assertEqual(providers.migrate('DeepSeek 网页（手动粘贴）'), providers.DEEPSEEK)
        self.assertEqual(providers.migrate('Gemini CLI（本机登录）'), providers.ANTIGRAVITY)
        self.assertEqual(providers.migrate('Removed provider'), providers.CODEX)
        self.assertEqual(providers.migrate(providers.KIRO), providers.KIRO)

    def test_capabilities(self):
        self.assertTrue(providers.accepts_images(providers.KIRO))
        self.assertFalse(providers.accepts_images(providers.DEEPSEEK))
        self.assertTrue(providers.accepts_images(providers.CLAUDE))
        self.assertTrue(providers.accepts_images(providers.ANTIGRAVITY))
        self.assertNotIn(providers.KIRO, providers.STATEFUL)
        self.assertIn(providers.LM_STUDIO, providers.STATEFUL)
        self.assertIn('Kimi', providers.note('Kimi'))

    def test_cli_answer_routes_to_each_transport(self):
        for name, helper in [(providers.CLAUDE, 'claude_answer'), (providers.KIRO, 'kiro_answer'),
                             (providers.ANTIGRAVITY, 'antigravity_answer')]:
            with self.subTest(name=name), patch.object(a, helper, return_value='OK') as answer:
                providers.cli_answer(name, 'prompt', 'model', threading.Event(), lambda _: None, effort='low')
                self.assertEqual(answer.call_args.args[1:3], ('prompt', 'model'))
                self.assertEqual(answer.call_args.kwargs['effort'], 'low')
                self.assertNotIn('session_key', answer.call_args.kwargs)

    def test_codex_result_is_emitted_when_nothing_streamed(self):
        pieces = []
        with patch.object(a, 'codex_answer', return_value='Full answer') as answer:
            providers.cli_answer(providers.CODEX, 'prompt', 'm', threading.Event(), pieces.append,
                                 session_key='lane', transcript='t', instructions='i')
        self.assertEqual(pieces, ['Full answer'])
        self.assertEqual(answer.call_args.args[:2], ('t', 'i'))
        self.assertEqual(answer.call_args.kwargs['prompt_override'], 'prompt')
        self.assertEqual(answer.call_args.kwargs['session_key'], 'lane')

    def test_api_provider_is_refused(self):
        with self.assertRaises(ValueError):
            providers.cli_answer('Gemini', 'p', 'm', threading.Event(), lambda _: None)


if __name__ == '__main__':
    unittest.main()
