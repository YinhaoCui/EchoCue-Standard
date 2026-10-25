"""Context edits must not leak stale analysis or reuse an obsolete provider lane."""
import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch
import test_sessions
from glass_bridge import GlassBridge


class ContextEditorTests(unittest.TestCase):
    setUp = test_sessions.UITests.setUp
    tearDown = test_sessions.UITests.tearDown

    pass

    def test_prompt_library_is_encrypted_and_overwrite_requires_confirmation(self):
        from account_support import load_settings
        import audio_answer
        bridge = GlassBridge(self.ui)
        try:
            with tempfile.TemporaryDirectory() as folder, patch.object(audio_answer, 'ROOT', Path(folder)):
                bridge.command(dict(action='save_prompt_template', id='save', version=0, name='Interview', text='private prompt fixture'))
                self.assertTrue(bridge.prompt_result['ok'])
                path = Path(folder) / 'data/prompt_templates.dpapi'
                self.assertNotIn(b'private prompt fixture', path.read_bytes())
                self.assertEqual(load_settings(path), {'Interview': 'private prompt fixture'})
                bridge.command(dict(action='save_prompt_template', id='replace', version=1, name='Interview', text='replacement'))
                self.assertFalse(bridge.prompt_result['ok'])
                self.assertEqual(self.ui.prompt_templates['Interview'], 'private prompt fixture')
                bridge.command(dict(action='save_prompt_template', id='confirmed', version=1, name='Interview', text='replacement', overwrite=True))
                self.assertTrue(bridge.prompt_result['ok'])
                bridge.command(dict(action='delete_prompt_template', id='delete', version=2, name='Interview'))
                self.assertTrue(bridge.prompt_result['ok'])
                self.assertEqual(load_settings(path), {})
        finally:
            bridge.close()

    def test_failed_template_write_keeps_library_unchanged(self):
        bridge = GlassBridge(self.ui)
        try:
            with patch('account_support.save_settings', side_effect=OSError('disk failure')):
                bridge.command(dict(action='save_prompt_template', id='save', version=0, name='Notes', text='prompt'))
            self.assertFalse(bridge.prompt_result['ok'])
            self.assertEqual(self.ui.prompt_templates, {})
            self.assertEqual(self.ui.prompt_templates_version, 0)
        finally:
            bridge.close()

    def test_saved_context_includes_prompt_and_reload_reads_it(self):
        import settings_state
        bridge = GlassBridge(self.ui)
        try:
            self.ui.instructions.set('Answer as a tutor')
            with patch('account_support.save_settings') as save:
                bridge.command(dict(action='save_context'))
            payload = save.call_args.args[1]
            self.assertEqual(payload['instructions'], 'Answer as a tutor')
            with patch.object(settings_state, 'load_settings', side_effect=lambda path: payload if path.name == 'context.dpapi' else {}):
                self.ui.init_advanced()
            self.assertEqual(self.ui.saved_prompt, 'Answer as a tutor')
        finally:
            bridge.close()

    def test_applied_prompt_reaches_stateless_and_stateful_requests(self):
        from answer_jobs import build_prompt
        from generation_context import ContextPrompt
        bridge = GlassBridge(self.ui)
        try:
            self.ui.provider.set('Codex')
            bridge.command(dict(action='apply_context', id='apply', version=self.ui.context_version,
                                values=dict(instructions='Use three concise bullet points.')))
            inputs, error = self.ui.request_inputs()
            self.assertIsNone(error)
            self.assertIn('Use three concise bullet points.', build_prompt(inputs, 'question'))
            self.assertIn('Use three concise bullet points.', ContextPrompt(inputs, 'question', 'SYSTEM').state['instructions'])
        finally:
            bridge.close()

    def test_edit_is_atomic_and_rejects_a_stale_draft(self):
        bridge = GlassBridge(self.ui)
        try:
            version = self.ui.context_version
            self.ui.context_summary = 'old analysis'
            bridge.command(dict(action='apply_context', id='one', version=version,
                                values=dict(profile='new notes', documents='new source')))
            self.assertTrue(bridge.context_edit['ok'])
            self.assertEqual(self.ui.context_version, version + 1)
            self.assertEqual(self.ui.context_summary, '')
            bridge.command(dict(action='apply_context', id='two', version=version,
                                values=dict(profile='stale notes')))
            self.assertFalse(bridge.context_edit['ok'])
            self.assertEqual(self.ui.profile, 'new notes')
        finally:
            bridge.close()

    def test_removing_image_invalidates_analysis_and_inflight_memory(self):
        bridge = GlassBridge(self.ui)
        try:
            self.ui.context_images = [dict(id='shot', data='fixture')]
            self.ui.context_summary = 'derived from deleted image'
            epoch = self.ui.history_epoch
            with patch.object(self.ui, 'save_session'):
                bridge.command(dict(action='remove_image', id='shot'))
            self.assertEqual(self.ui.context_summary, '')
            self.assertEqual(self.ui.context_images, [])
            self.assertGreater(self.ui.history_epoch, epoch)
            version = self.ui.context_version
            bridge.command(dict(action='remove_image', id='missing'))
            self.assertEqual(self.ui.context_version, version)
        finally:
            bridge.close()

    def test_clear_memory_keeps_sources_and_blocks_late_answer(self):
        self.ui.profile = 'keep source'
        self.ui.context_summary = 'keep analysis'
        self.ui.history = [{'回答': 'old'}]
        epoch = self.ui.history_epoch
        self.ui.jobs[1] = dict(history_epoch=epoch, target=None, done=False)
        with patch.object(self.ui, 'save_session'):
            self.ui.clear_history()
        self.ui.handle_job_event(1, 'completed', (False, self.ui.context_version, 'q', 'late'))
        self.ui.jobs.clear()
        self.assertEqual(self.ui.history, [])
        self.assertEqual(self.ui.profile, 'keep source')
        self.assertEqual(self.ui.context_summary, 'keep analysis')

    def test_changed_source_and_history_toggle_use_new_provider_lane(self):
        bridge = GlassBridge(self.ui)
        try:
            self.ui.provider.set('Codex')
            first, error = self.ui.request_inputs()
            self.assertIsNone(error)
            bridge.settings(dict(profile='updated'))
            second, error = self.ui.request_inputs()
            self.assertIsNone(error)
            self.assertNotEqual(first['session_key'], second['session_key'])
            bridge.settings(dict(history=False))
            disabled, _ = self.ui.request_inputs()
            self.assertIsNone(disabled['session_key'])
            bridge.settings(dict(history=True))
            restored, _ = self.ui.request_inputs()
            self.assertNotEqual(second['session_key'], restored['session_key'])
        finally:
            bridge.close()
