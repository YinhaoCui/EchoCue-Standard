"""Catalog refresh behavior across API, CLI, and speed-test selectors."""
import io
import json
import threading
import unittest
from unittest.mock import patch

import audio_answer as a
import providers
import test_sessions
from model_catalog import CATALOG, select_models


class CatalogTests(unittest.TestCase):
    def test_success_replaces_presets_including_empty_catalog(self):
        for provider in a.API_PROVIDERS:
            with self.subTest(provider=provider):
                discovered = 'muse-spark-future' if provider == providers.META else 'new-chat-model'
                self.assertEqual(select_models(provider, [discovered]), [discovered])
                self.assertEqual(select_models(provider, []), [])
                self.assertEqual(select_models(provider), list(CATALOG.get(provider, {})))
        self.assertEqual(select_models('LM Studio'), [])

    def test_success_keeps_descriptions_order_but_only_for_returned_models(self):
        self.assertEqual(select_models('DeepSeek', ['z-new', 'deepseek-v4-pro', 'a-new']),
                         ['deepseek-v4-pro', 'a-new', 'z-new'])

    def test_malformed_response_does_not_replace_cache_with_empty_catalog(self):
        for rows in ([{}], [{'id': None}], [{'id': []}], [{'id': ''}], ['not-a-model']):
            with self.subTest(rows=rows), patch('urllib.request.urlopen', return_value=io.BytesIO(json.dumps({'data': rows}).encode())):
                with self.assertRaisesRegex(RuntimeError, '格式异常'):
                    a.list_provider_models('DeepSeek', 'fixture-key')
        with patch('urllib.request.urlopen', return_value=io.BytesIO(b'{"data":[]}')):
            self.assertEqual(a.list_provider_models('DeepSeek', 'fixture-key'), set())


class DiscoveryUITests(unittest.TestCase):
    setUp = test_sessions.UITests.setUp
    tearDown = test_sessions.UITests.tearDown

    def select_provider(self, provider):
        self.ui.provider.set(provider)
        self.ui.update_provider()
        self.ui.key.set('fixture-key')

    def refresh(self, models=None, error=None, during=None):
        # Stop at the real HTTP seam, so model/key edits happen while a refresh is in flight.
        started, release = threading.Event(), threading.Event()
        def read(*args, **kwargs):
            started.set()
            if not release.wait(3): raise RuntimeError('test timed out')
            if error: raise RuntimeError(error)
            return models
        with patch.object(a, 'list_provider_models', side_effect=read):
            self.ui.refresh_models()
            try:
                self.assertTrue(started.wait(2))
                if during: during()
            finally:
                release.set()
            kind, result = self.ui.events.get(timeout=3)
            self.assertEqual(kind, 'models_refreshed')
            self.ui.handle_event(kind, result)

    def test_model_edit_during_refresh_preserves_selection_and_accepts_catalog(self):
        self.select_provider('DeepSeek')
        self.refresh({'new-deepseek'}, during=lambda: self.ui.model.set('my-custom-model'))
        self.assertEqual(self.ui.model_choices, ['new-deepseek'])
        self.assertEqual(self.ui.model.get(), 'my-custom-model')
        self.refresh(error='fixture offline')
        self.assertEqual(self.ui.model_choices, ['new-deepseek'])
        self.assertIn('刷新失败', self.ui.key_status.get())
        self.refresh(set())
        self.assertEqual(self.ui.model_choices, [])
        self.assertEqual(self.ui.model.get(), 'my-custom-model')

    def test_failure_before_success_labels_unverified_presets(self):
        self.select_provider('DeepSeek')
        self.refresh(error='fixture offline')
        self.assertEqual(self.ui.model_choices, list(CATALOG['DeepSeek']))
        self.assertIn('内置预设', self.ui.model_catalog_note())

    def test_key_and_local_endpoint_changes_do_not_reuse_another_catalog(self):
        self.select_provider('DeepSeek')
        self.refresh({'old-account'}, during=lambda: self.ui.key.set('new-key'))
        self.assertNotIn('old-account', self.ui.model_choices)
        self.refresh({'new-account'})
        self.ui.key.set('fixture-key')
        self.assertEqual(self.ui.model_choices, ['old-account'])
        self.select_provider('LM Studio')
        self.refresh({'local-one'})
        self.ui.advanced['lm_base'].set('http://localhost:4321/v1')
        self.assertEqual(self.ui.model_choices, [])
        self.refresh(error='fixture offline')
        self.assertEqual(self.ui.model_choices, [])

    def test_cli_refresh_replaces_fallback_and_retains_cache_on_error(self):
        self.select_provider(providers.CLAUDE)
        self.assertIn('内置预设', self.ui.cli_catalog_note(providers.CLAUDE))
        self.ui.receive_cli_models((providers.CLAUDE, ['account-model'], '', ''))
        self.assertEqual(self.ui.cli_models(), ['account-model'])
        self.ui.receive_cli_models((providers.CLAUDE, [], '', 'fixture offline'))
        self.assertEqual(self.ui.cli_models(), ['account-model'])

    def test_claude_speed_refresh_reads_cli_instead_of_fixed_aliases(self):
        self.select_provider(providers.CLAUDE)
        self.ui.show_speed_test()
        with patch.object(providers, 'read_cli_models', return_value=(['account-opus'], None)) as read:
            self.ui.refresh_speed_models()
            kind, result = self.ui.events.get(timeout=3)
            self.assertEqual(kind, 'speed_models')
            self.ui.handle_event(kind, result)
        read.assert_called_once_with(providers.CLAUDE)
        self.assertEqual(tuple(self.ui.speed_model_box['values']), ('account-opus',))

    def test_speed_api_catalog_filters_media_and_isolates_keys(self):
        self.select_provider('Gemini')
        self.ui.show_speed_test()
        with patch.object(a, 'list_provider_models', return_value={'new-chat', 'new-embedding'}):
            self.ui.refresh_speed_models()
            kind, result = self.ui.events.get(timeout=3)
            self.ui.handle_event(kind, result)
        self.assertEqual(tuple(self.ui.speed_model_box['values']), ('new-chat',))
        self.ui.key.set('different-key')
        with patch.object(a, 'list_provider_models', side_effect=RuntimeError('fixture offline')):
            self.ui.refresh_speed_models()
            kind, result = self.ui.events.get(timeout=3)
            self.ui.handle_event(kind, result)
        self.assertNotIn('new-chat', self.ui.speed_model_box['values'])


if __name__ == '__main__':
    unittest.main()
