"""Standard edition shortcut, desktop menu and installed data boundaries."""
import unittest
from hotkey_settings import DEFAULTS, validate
from tray_menu import menu_entries


class StandardEditionTests(unittest.TestCase):
    def test_shortcuts_cover_the_three_desktop_actions(self):
        self.assertEqual(set(DEFAULTS), {'hotkey', 'topmost', 'transcription'})
        self.assertEqual(validate(DEFAULTS), DEFAULTS)

    def test_tray_actions_and_pin_state(self):
        entries = [entry for entry in menu_entries({'native': {'topmost': True}}) if entry]
        self.assertEqual([entry[0] for entry in entries], ['show', 'listen', 'settings', 'start', 'topmost', 'quit'])
        self.assertTrue(next(entry for entry in entries if entry[0] == 'topmost')[3])
