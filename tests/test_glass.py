"""Local transport access control and controller adapter behavior."""
import json
import unittest
import urllib.request
import urllib.error
from unittest.mock import Mock, patch
import test_sessions
from glass_bridge import GlassBridge


class GlassTests(unittest.TestCase):
    setUp = test_sessions.UITests.setUp
    tearDown = test_sessions.UITests.tearDown

    def test_state_omits_secrets_and_keeps_full_text(self):
        bridge = GlassBridge(self.ui)
        try:
            self.ui.key.set('never-export-this')
            self.ui.token_ledger.lock = __import__('threading').Lock()
            self.ui.token_ledger.rows = []
            text = 'Long question. ' * 10000
            self.ui.put_text(text, replace=True, target='transcript')
            self.ui.put_text(text, replace=True)
            state = bridge.snapshot()
            self.assertTrue(state['transcript'] == text)
            self.assertTrue(state['output'] == text)
            self.assertNotIn('never-export-this', json.dumps(state))
        finally:
            bridge.close()

    def test_state_reads_send_only_changes(self):
        bridge = GlassBridge(self.ui)
        try:
            self.ui.token_ledger.lock = __import__('threading').Lock()
            self.ui.token_ledger.rows = []
            self.ui.put_text('Long question. ' * 1000, replace=True, target='transcript')
            bridge.feed.publish(bridge.snapshot())
            headers = {'X-Listener-Token': bridge.token}

            def read(query):
                request = urllib.request.Request(bridge.url + '/state?' + query, headers=headers)
                with urllib.request.urlopen(request) as response:
                    return json.loads(response.read())
            first = read('wait=0')
            self.assertIn('provider', first['state'])
            self.assertEqual(first['transcript']['text'], 'Long question. ' * 1000)
            tv, ov = first['transcript']['v'], first['output']['v']
            again = read('rev=%d&boot=%s&tv=%d&ov=%d&wait=0' % (first['rev'], first['boot'], tv, ov))
            self.assertEqual(again, {'boot': first['boot'], 'rev': first['rev']})
        finally:
            bridge.close()

    def test_loopback_requires_token_and_rejects_cross_origin(self):
        bridge = GlassBridge(self.ui)
        try:
            for headers in ({}, {'X-Listener-Token': bridge.token, 'Origin': 'https://evil.test'}):
                with self.assertRaises(urllib.error.HTTPError) as error:
                    urllib.request.urlopen(urllib.request.Request(bridge.url + '/state', headers=headers))
                self.assertEqual(error.exception.code, 403)
                error.exception.close()
            request = urllib.request.Request(bridge.url + '/command', data=b'{"action":"answer"}',
                                             headers={'X-Listener-Token': bridge.token})
            with urllib.request.urlopen(request) as response:
                self.assertEqual(response.status, 202)
            self.assertEqual(bridge.commands.get_nowait(), {'action': 'answer'})
            with patch.object(self.ui, 'ask') as ask:
                bridge.command({'action': 'answer'})
                ask.assert_called_once()
        finally:
            bridge.close()

    def test_provider_change_preserves_saved_key_and_edits_context(self):
        bridge = GlassBridge(self.ui)
        try:
            bridge.settings({'provider': 'Codex', 'model': '', 'profile': 'New notes', 'documents': 'Full source'})
            self.assertEqual(self.ui.profile, 'New notes')
            self.assertEqual(self.ui.documents, 'Full source')
            self.assertEqual(self.ui.provider.get(), 'Codex')
            self.ui.key.set('keep-me')
            bridge.settings({'key': ''})
            self.assertEqual(self.ui.key.get(), 'keep-me')
        finally:
            bridge.close()

    def test_audio_settings_cannot_change_during_capture(self):
        bridge = GlassBridge(self.ui)
        try:
            self.ui.capture.active.return_value = True
            with self.assertRaisesRegex(ValueError, 'Pause'):
                bridge.settings({'source': '麦克风'})
            self.assertEqual(self.ui.advanced['source'].get(), '电脑')
        finally:
            bridge.close()

    def test_english_interface_keeps_canonical_reasoning_values(self):
        bridge = GlassBridge(self.ui)
        try:
            self.ui.token_ledger.lock = __import__('threading').Lock()
            self.ui.token_ledger.rows = []
            bridge.settings({'provider': 'Codex', 'language': 'en', 'effort': '自动'})
            state = bridge.snapshot()
            self.assertIn(state['effort'], state['efforts'])
            bridge.settings({'effort': 'low'})
            self.assertEqual(self.ui.reasoning_selection.get(), 'low')
        finally:
            bridge.close()

    def test_icons_are_served_and_old_interface_route_is_removed(self):
        bridge = GlassBridge(self.ui)
        try:
            with urllib.request.urlopen(bridge.url + '/icons/cpu.svg') as response:
                self.assertEqual(response.headers.get_content_type(), 'image/svg+xml')
                self.assertIn(b'<svg', response.read())
            with urllib.request.urlopen(bridge.url + '/') as response:
                self.assertNotIn(b'data-action="legacy"', response.read())
            with self.assertRaisesRegex(ValueError, 'Unknown action'):
                bridge.command({'action': 'legacy'})
        finally:
            bridge.close()

    def test_background_modes_are_saved_and_forwarded_to_host(self):
        bridge = GlassBridge(self.ui)
        try:
            for mode in ('translucent', 'frosted', 'opaque'):
                with patch.object(self.ui, 'save_preferences') as save:
                    bridge.settings({'background_mode': mode})
                    save.assert_called_once()
                self.assertEqual(self.ui.advanced['background_mode'].get(), mode)
                self.assertEqual(bridge.window_state['background'], mode)
            with self.assertRaises(ValueError):
                bridge.settings({'background_mode': 'invalid'})
            self.assertEqual(bridge.window_state['background'], 'opaque')
        finally:
            bridge.close()

    pass

    def test_transcription_engine_change_reconfigures_recognizer(self):
        bridge = GlassBridge(self.ui)
        try:
            with patch.object(self.ui, 'change_asr') as change:
                bridge.settings({'asr_engine': '英文 · Zipformer'})
                change.assert_called_once()
            with patch.object(self.ui, 'cancel_job') as cancel:
                bridge.command({'action': 'cancel_job', 'id': 12})
                cancel.assert_called_once_with(12)
        finally:
            bridge.close()

    def test_transparency_range_and_private_image_preview(self):
        bridge = GlassBridge(self.ui)
        try:
            for value in (1, 50, 99):
                bridge.settings({'listen_transparency': value})
                self.assertEqual(self.ui.advanced['listen_transparency'].get(), str(value))
            for value in (0, 100):
                with self.assertRaises(ValueError):
                    bridge.settings({'listen_transparency': value})
            bridge.image_data = {'fixture': 'aW1hZ2U='}
            with self.assertRaises(urllib.error.HTTPError) as error:
                urllib.request.urlopen(bridge.url + '/image/fixture')
            self.assertEqual(error.exception.code, 403)
            error.exception.close()
            request = urllib.request.Request(bridge.url + '/image/fixture', headers={'X-Listener-Token': bridge.token})
            with urllib.request.urlopen(request) as response:
                self.assertEqual(response.read(), b'image')
        finally:
            bridge.close()
