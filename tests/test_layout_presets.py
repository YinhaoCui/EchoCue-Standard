import json
import unittest

from glass_bridge import layout_value, listen_presets, MAX_PRESETS
from settings_state import DEFAULT_OPTIONS, LAYOUT_KEYS


class LayoutValueTests(unittest.TestCase):
    def test_accepts_and_normalizes(self):
        self.assertEqual(layout_value('listen_transparency', '40'), '40')
        self.assertEqual(layout_value('answer_font_size', 30), '30')
        self.assertEqual(layout_value('listen_text_color', '#AABBCC'), '#aabbcc')
        self.assertEqual(layout_value('listen_layout', '0,0,0,0,0'), '')
        self.assertEqual(layout_value('listen_text_bold', '1'), '1')

    def test_rejects_bad_values(self):
        for key, value in (('listen_transparency', '0'), ('transcript_font_size', '99'),
                           ('listen_panel_color', 'red'), ('listen_text_outline', 'yes'),
                           ('listen_layout', '1,2'), ('provider', 'x')):
            with self.subTest(key=key), self.assertRaises(ValueError):
                layout_value(key, value)

    def test_defaults_are_valid(self):
        for key in LAYOUT_KEYS:
            with self.subTest(key=key):
                self.assertEqual(layout_value(key, DEFAULT_OPTIONS[key]), DEFAULT_OPTIONS[key])


class PresetTests(unittest.TestCase):
    def test_round_trip(self):
        raw = json.dumps([{'name': ' Meeting ', 'values': {'listen_transparency': '30', 'listen_text_color': '#FFEE00'}}])
        self.assertEqual(json.loads(listen_presets(raw)),
                         [{'name': 'Meeting', 'values': {'listen_transparency': '30', 'listen_text_color': '#ffee00'}}])
        self.assertEqual(listen_presets(''), '')
        self.assertEqual(listen_presets('[]'), '')

    def test_rejects_bad_presets(self):
        good = {'name': 'A', 'values': {}}
        bad = [
            'not json', '{}', [good] * 2,  # duplicate names
            [{'name': '', 'values': {}}], [{'name': 'x' * 41, 'values': {}}],
            [{'name': 'A', 'values': {'api_key': 'x'}}],
            [{'name': 'A', 'values': {'listen_transparency': '500'}}],
            [{'name': str(n), 'values': {}} for n in range(MAX_PRESETS + 1)],
        ]
        for value in bad:
            with self.subTest(value=value), self.assertRaises(ValueError):
                listen_presets(value if isinstance(value, str) else json.dumps(value))


import test_sessions
import audio_answer as a


class LayoutSavingTests(unittest.TestCase):
    setUp = test_sessions.UITests.setUp
    tearDown = test_sessions.UITests.tearDown

    def test_layout_saved_without_keys(self):
        self.ui.advanced['listen_transparency'].set('44')
        self.ui.advanced['listen_presets'].set('[{"name":"A","values":{}}]')
        self.ui.remember_keys.set(False)
        self.ui.save_preferences()
        payload = a.save_settings.call_args.args[1]
        self.assertNotIn('apis', payload)
        self.assertEqual(payload['layout']['listen_transparency'], '44')
        self.assertEqual(payload['layout']['listen_presets'], '[{"name":"A","values":{}}]')

    def test_bridge_applies_preset_whole_or_not_at_all(self):
        from glass_bridge import GlassBridge
        bridge = GlassBridge.__new__(GlassBridge)
        bridge.app = self.ui
        bridge.window_state = {}
        with self.assertRaises(ValueError):
            bridge.settings({'listen_transparency': '50', 'answer_font_size': '99'})
        self.assertNotEqual(self.ui.advanced['listen_transparency'].get(), '50')
        bridge.settings({'listen_transparency': '50', 'answer_font_size': '30'})
        self.assertEqual(self.ui.advanced['listen_transparency'].get(), '50')
        self.assertEqual(self.ui.advanced['answer_font_size'].get(), '30')


class LayoutLoadingTests(unittest.TestCase):
    initial_settings = {'ui_language': 'zh', 'remember_keys': False,
                        'advanced': {'listen_transparency': '20'},
                        'layout': {'listen_transparency': '33', 'listen_text_bold': '1',
                                   'listen_presets': '[{"name":"A","values":{}}]'}}
    setUp = test_sessions.UITests.setUp
    tearDown = test_sessions.UITests.tearDown

    def test_saved_layout_overrides_advanced(self):
        options = self.ui.advanced
        self.assertEqual(options['listen_transparency'].get(), '33')
        self.assertEqual(options['listen_text_bold'].get(), '1')
        self.assertEqual(options['listen_presets'].get(), '[{"name":"A","values":{}}]')
        self.assertEqual(options['answer_font_size'].get(), DEFAULT_OPTIONS['answer_font_size'])


if __name__ == '__main__':
    unittest.main()
