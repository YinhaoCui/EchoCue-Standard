import unittest
from hotkey_settings import parse,validate,DEFAULTS
class HotkeyValidationTests(unittest.TestCase):
    pass
    def test_rejects_unsafe_or_incomplete_keys(self):
        for key in ('P','Ctrl','Ctrl+Ctrl+P','Ctrl+A+B','Ctrl+F25','Alt++'):
            with self.subTest(key=key),self.assertRaises(ValueError):parse(key)


import test_sessions
import audio_answer as a
from unittest.mock import patch
class HotkeySavingTests(unittest.TestCase):
    setUp=test_sessions.UITests.setUp
    tearDown=test_sessions.UITests.tearDown
    def test_page_save_updates_preferences_and_requests_registration_without_a_dialog(self):
        children=list(self.root.winfo_children())
        self.ui.hotkey_thread_id=123
        with patch('hotkey_settings.ctypes.windll.user32.PostThreadMessageW',return_value=1) as register:
            self.ui.apply_hotkeys(dict(DEFAULTS,hotkey='Ctrl+Shift+F8'))
            register.assert_called_once_with(123,0x8001,0,0)
        self.assertEqual(self.ui.hotkeys['hotkey'],'Ctrl+Shift+F8')
        self.assertEqual(a.save_settings.call_args.args[1]['hotkeys']['hotkey'],'Ctrl+Shift+F8')
        self.assertEqual(list(self.root.winfo_children()),children)

    def test_invalid_values_and_failed_save_keep_previous_shortcuts(self):
        previous=dict(self.ui.hotkeys)
        with self.assertRaises(ValueError):self.ui.apply_hotkeys(dict(DEFAULTS,hotkey=DEFAULTS['topmost']))
        self.assertEqual(self.ui.hotkeys,previous)
        with patch.object(self.ui,'save_preferences',return_value=False):
            with self.assertRaises(ValueError):self.ui.apply_hotkeys(dict(DEFAULTS,hotkey='Ctrl+Shift+F8'))
        self.assertEqual(self.ui.hotkeys,previous)

    def test_bridge_navigates_to_settings_and_reports_confirmed_save(self):
        from glass_bridge import GlassBridge
        bridge=GlassBridge(self.ui)
        try:
            children=list(self.root.winfo_children())
            bridge.command(dict(action='hotkeys'))
            self.assertEqual(bridge.snapshot()['navigation_request']['section'],'shortcuts')
            self.assertEqual(list(self.root.winfo_children()),children)
            bridge.command(dict(action='save_hotkeys',id='save',values=dict(DEFAULTS,hotkey='Ctrl+Shift+F8')))
            self.assertEqual(bridge.hotkey_result,dict(id='save',ok=True))
            bridge.command(dict(action='save_hotkeys',id='invalid',values=dict(DEFAULTS,hotkey=DEFAULTS['topmost'])))
            self.assertFalse(bridge.hotkey_result['ok'])
            self.assertEqual(self.ui.hotkeys['hotkey'],'Ctrl+Shift+F8')
        finally:bridge.close()
    def test_shortcuts_saved_without_keys(self):
        self.ui.remember_keys.set(False)
        self.ui.save_preferences()
        payload=a.save_settings.call_args.args[1]
        self.assertIn('hotkeys',payload)
        self.assertNotIn('apis',payload)
        self.assertFalse(payload['remember_keys'])
