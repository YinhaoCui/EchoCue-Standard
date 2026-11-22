import threading
import unittest
from unittest.mock import patch

import audio_answer as a
import lmstudio_support
import providers


def request(provider, **kwargs):
    values = dict(provider=provider, model='m', cancel=threading.Event(), emit=lambda _: None, key='k')
    values.update(kwargs)
    return providers.AnswerRequest(**values)


class ProviderAnswerTests(unittest.TestCase):
    def test_gemini_receives_the_same_arguments_as_before(self):
        with patch.object(a, 'gemini_answer', return_value='ok') as answer:
            providers.answer(request('Gemini', instructions='i', transcript='t', fast=True, output_limit=99))
        args, kwargs = answer.call_args
        self.assertEqual(args[:4], (None, 'k', 'm', 'i'))
        self.assertIsInstance(args[4], threading.Event)
        self.assertEqual((kwargs['fast'], kwargs['transcript'], kwargs['max_output']), (True, 't', 99))
        self.assertNotIn('images', kwargs)

    def test_compatible_providers_use_reasoning_and_base(self):
        with patch.object(a, 'compatible_answer') as answer:
            providers.answer(request('Kimi', transcript='t', reasoning=True, base='http://x', images=[{'data': ''}]))
        args, kwargs = answer.call_args
        self.assertEqual(args[:2], ('Kimi', 't'))
        self.assertTrue(kwargs['reasoning'])
        self.assertEqual(kwargs['base'], 'http://x')
        self.assertEqual(kwargs['images'], [{'data': ''}])

    def test_lm_studio_falls_back_to_compatible_mode_and_reports_it(self):
        statuses = []
        with (
            patch.object(lmstudio_support, 'answer', return_value=None) as native,
            patch.object(a, 'compatible_answer') as compatible,
        ):
            providers.answer(
                request('LM Studio', lm_native=True, reasoning=True, effort='high', on_status=statuses.append)
            )
        native.assert_called_once()
        self.assertEqual(len(statuses), 1)
        kwargs = compatible.call_args.kwargs
        self.assertEqual((kwargs['effort'], kwargs['reasoning'], kwargs['images']), ('服务默认', False, ()))

    def test_lm_studio_native_success_skips_the_fallback(self):
        with (
            patch.object(lmstudio_support, 'answer', return_value='done'),
            patch.object(a, 'compatible_answer') as compatible,
        ):
            self.assertEqual(providers.answer(request('LM Studio', lm_native=True)), 'done')
        compatible.assert_not_called()

    def test_cli_providers_go_through_cli_answer(self):
        with patch.object(providers, 'cli_answer', return_value='r') as cli:
            providers.answer(request(providers.KIRO, prompt='p', transcript='t', instructions='i'))
        self.assertEqual(cli.call_args.args[:3], (providers.KIRO, 'p', 'm'))
        self.assertEqual(cli.call_args.kwargs['image_paths'], [])


if __name__ == '__main__':
    unittest.main()
