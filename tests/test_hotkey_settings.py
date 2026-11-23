import unittest
from hotkey_settings import parse, validate, DEFAULTS, taken_elsewhere, PROBE_ID


class HotkeyValidationTests(unittest.TestCase):
    pass

    def test_rejects_unsafe_or_incomplete_keys(self):
        for key in ('P', 'Ctrl', 'Ctrl+Ctrl+P', 'Ctrl+A+B', 'Ctrl+F25', 'Alt++'):
            with self.subTest(key=key), self.assertRaises(ValueError):
                parse(key)

    def test_function_key_alone_and_unused_actions_are_allowed(self):
        self.assertEqual(parse('f8'), ('F8', 0x4000, 119))
        for key in ('F', 'F0x', 'F25'):
            with self.subTest(key=key), self.assertRaises(ValueError):
                parse(key)
        values = validate(dict(DEFAULTS, hotkey='F8', topmost='', transcription=' ', capture_screen=''))
        self.assertEqual((values['hotkey'], values['topmost'], values['transcription']), ('F8', '', ''))
        # Several unused actions are not "the same shortcut".
        self.assertEqual(values['capture_screen'], '')
        with self.assertRaises(ValueError):
            validate(dict(DEFAULTS, hotkey=None))

    @unittest.skipUnless('passthrough' in DEFAULTS, 'this edition has no click-through')
    def test_click_through_needs_a_way_back(self):
        with self.assertRaises(ValueError):
            validate(dict(DEFAULTS, restore=''))
        self.assertEqual(validate(dict(DEFAULTS, restore='', passthrough=''))['restore'], '')


import test_sessions
import audio_answer as a
from unittest.mock import patch


class HotkeySavingTests(unittest.TestCase):
    setUp = test_sessions.UITests.setUp
    tearDown = test_sessions.UITests.tearDown

    def test_page_save_updates_preferences_and_requests_registration_without_a_dialog(self):
        children = list(self.root.winfo_children())
        self.ui.hotkey_thread_id = 123
        with patch('hotkey_settings.ctypes.windll.user32.PostThreadMessageW', return_value=1) as register:
            self.ui.apply_hotkeys(dict(DEFAULTS, hotkey='Ctrl+Shift+F8'))
            register.assert_called_once_with(123, 0x8001, 0, 0)
        self.assertEqual(self.ui.hotkeys['hotkey'], 'Ctrl+Shift+F8')
        self.assertEqual(a.save_settings.call_args.args[1]['hotkeys']['hotkey'], 'Ctrl+Shift+F8')
        self.assertEqual(list(self.root.winfo_children()), children)

    def test_invalid_values_and_failed_save_keep_previous_shortcuts(self):
        previous = dict(self.ui.hotkeys)
        with self.assertRaises(ValueError):
            self.ui.apply_hotkeys(dict(DEFAULTS, hotkey=DEFAULTS['topmost']))
        self.assertEqual(self.ui.hotkeys, previous)
        with patch.object(self.ui, 'save_preferences', return_value=False):
            with self.assertRaises(ValueError):
                self.ui.apply_hotkeys(dict(DEFAULTS, hotkey='Ctrl+Shift+F8'))
        self.assertEqual(self.ui.hotkeys, previous)

    def test_bridge_navigates_to_settings_and_reports_confirmed_save(self):
        from glass_bridge import GlassBridge

        bridge = GlassBridge(self.ui)
        try:
            children = list(self.root.winfo_children())
            bridge.command(dict(action='hotkeys'))
            self.assertEqual(bridge.snapshot()['navigation_request']['section'], 'shortcuts')
            self.assertEqual(list(self.root.winfo_children()), children)
            bridge.command(dict(action='save_hotkeys', id='save', values=dict(DEFAULTS, hotkey='Ctrl+Shift+F8')))
            self.assertEqual(bridge.hotkey_result, dict(id='save', ok=True))
            bridge.command(dict(action='save_hotkeys', id='invalid', values=dict(DEFAULTS, hotkey=DEFAULTS['topmost'])))
            self.assertFalse(bridge.hotkey_result['ok'])
            self.assertEqual(self.ui.hotkeys['hotkey'], 'Ctrl+Shift+F8')
        finally:
            bridge.close()

    def test_reports_shortcuts_held_by_another_program(self):
        with patch('hotkey_settings.ctypes.windll.user32') as api:
            api.RegisterHotKey.return_value = 0
            self.assertTrue(taken_elsewhere('ctrl+shift+f8'))
            api.UnregisterHotKey.assert_not_called()
            api.RegisterHotKey.return_value = 1
            self.assertFalse(taken_elsewhere('Ctrl+Shift+F8'))
            api.UnregisterHotKey.assert_called_once_with(None, PROBE_ID)
            # This app's own shortcuts are not probed: the page reports duplicates.
            api.RegisterHotKey.reset_mock()
            self.assertFalse(taken_elsewhere(DEFAULTS['hotkey'], DEFAULTS.values()))
            api.RegisterHotKey.assert_not_called()

    def test_bridge_checks_a_shortcut_and_releases_shortcuts_while_recording(self):
        from glass_bridge import GlassBridge

        bridge = GlassBridge(self.ui)
        self.ui.hotkey_thread_id = 123
        try:
            with patch('glass_bridge.taken_elsewhere', return_value=True) as probe:
                bridge.command(dict(action='check_hotkey', id='c1', value='Ctrl+Shift+F8'))
                self.assertEqual(probe.call_args.args[0], 'Ctrl+Shift+F8')
            self.assertEqual(bridge.snapshot()['hotkey_check'], dict(id='c1', taken=True))
            bridge.command(dict(action='check_hotkey', id='c2', value='not a shortcut'))
            self.assertEqual(bridge.hotkey_check, dict(id='c2', taken=False))
            self.assertEqual(bridge.snapshot()['hotkey_failed'], [])
            with patch('hotkey_settings.ctypes.windll.user32.PostThreadMessageW', return_value=1) as post:
                bridge.command(dict(action='hotkey_recording', value=True))
                bridge.command(dict(action='hotkey_recording', value=True))
                self.assertTrue(self.ui.hotkeys_paused)
                bridge.command(dict(action='hotkey_recording', value=False))
                self.assertFalse(self.ui.hotkeys_paused)
                self.assertEqual(post.call_count, 2)
        finally:
            bridge.close()

    def test_shortcuts_saved_without_keys(self):
        self.ui.remember_keys.set(False)
        self.ui.save_preferences()
        payload = a.save_settings.call_args.args[1]
        self.assertIn('hotkeys', payload)
        self.assertNotIn('apis', payload)
        self.assertFalse(payload['remember_keys'])
