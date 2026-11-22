import unittest
from unittest.mock import patch

import providers
from model_catalog import arrange, select_models


class ModelOrderTests(unittest.TestCase):
    def test_effort_variants_run_low_to_high_in_every_family(self):
        listed = [
            'gemini-4-neon-high',
            'gemini-4-neon-xhigh',
            'gemini-4-neon-medium',
            'gemini-4-neon-low',
            'gemini-4-argon-medium',
            'gemini-4-argon-high',
            'gemini-4-argon-low',
            'gemini-3.8-flash-high',
            'gemini-3.8-flash-low',
        ]
        self.assertEqual(
            arrange(listed),
            [
                'gemini-4-neon-low',
                'gemini-4-neon-medium',
                'gemini-4-neon-high',
                'gemini-4-neon-xhigh',
                'gemini-4-argon-low',
                'gemini-4-argon-medium',
                'gemini-4-argon-high',
                'gemini-3.8-flash-low',
                'gemini-3.8-flash-high',
            ],
        )

    def test_families_keep_provider_order_and_newest_version_leads(self):
        listed = [
            'claude-fable-5-2',
            'claude-opus-5-5',
            'claude-sonnet-5',
            'claude-haiku-4-5-20251001',
            'claude-fable-5-1',
            'claude-sonnet-5-5',
            'claude-haiku-5-5',
            'claude-haiku-4-5',
        ]
        self.assertEqual(
            arrange(listed),
            [
                'claude-fable-5-2',
                'claude-fable-5-1',
                'claude-opus-5-5',
                'claude-sonnet-5-5',
                'claude-sonnet-5',
                'claude-haiku-5-5',
                'claude-haiku-4-5',
                'claude-haiku-4-5-20251001',
            ],
        )

    def test_blanks_duplicates_and_dropped_ids_are_removed(self):
        self.assertEqual(arrange(['default', ' a-1 ', 'a-1', '', None, 7, 'b'], drop=('default',)), ['a-1', 'b'])
        self.assertEqual(arrange(None), [])

    def test_arranging_twice_changes_nothing(self):
        once = arrange(['x-2-high', 'y', 'x-10-low', 'x-2-low', 'y-1.5'])
        self.assertEqual(arrange(once), once)
        self.assertEqual(once, ['x-10-low', 'x-2-low', 'x-2-high', 'y-1.5', 'y'])

    def test_api_lists_keep_presets_first_then_the_shared_order(self):
        models = select_models('Kimi', ['new-2', 'kimi-k3', 'new-10', 'kimi-k2.6'])
        self.assertEqual(models, ['kimi-k2.6', 'kimi-k3', 'new-10', 'new-2'])
        self.assertEqual(
            select_models('DeepSeek', ['z-1', 'a-2-high', 'a-2-low', 'a-3']), ['a-3', 'a-2-low', 'a-2-high', 'z-1']
        )

    def test_cli_catalogs_use_the_shared_order_without_default(self):
        raw = ['default', 'claude-opus-5-5', 'claude-fable-5-1', 'claude-fable-5-2']
        with patch.object(providers, '_read_cli_models', return_value=(raw, None)):
            models, extra = providers.read_cli_models(providers.CLAUDE)
        self.assertEqual(models, ['claude-opus-5-5', 'claude-fable-5-2', 'claude-fable-5-1'])
        self.assertIsNone(extra)


if __name__ == '__main__':
    unittest.main()
