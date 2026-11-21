from array import array
import logging
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import app_log
import pcm


class RedactionTests(unittest.TestCase):
    def test_given_and_registered_values_and_key_shapes_are_removed(self):
        app_log.register_secret('registered-secret-value')
        text = app_log.redact(
            'a registered-secret-value b plain-1234 c sk-abcdefghijklmnop1234 d AIza'
            + 'x' * 35
            + ' Bearer abcdef0123456789xyz',
            'plain-1234',
        )
        for leaked in ('registered-secret-value', 'plain-1234', 'sk-abc', 'AIza', 'abcdef0123456789'):
            self.assertNotIn(leaked, text)
        self.assertEqual(text.count('[KEY]'), 5)

    def test_short_or_missing_values_do_not_erase_text(self):
        self.assertEqual(app_log.redact('a b c', '', None, 'a'), 'a b c')

    def test_log_file_never_contains_the_key(self):
        with tempfile.TemporaryDirectory() as folder:
            logger = app_log.get()
            handlers = list(logger.handlers)
            try:
                path = app_log.setup(Path(folder))
                app_log.register_secret('file-secret-0123456789')
                app_log.get('test').warning('failed with %s', 'file-secret-0123456789')
                for handler in logger.handlers:
                    handler.flush()
                self.assertIn('failed with [KEY]', path.read_text(encoding='utf-8'))
            finally:
                for handler in logger.handlers[:]:
                    if handler not in handlers:
                        handler.close()
                        logger.removeHandler(handler)
                logger.setLevel(logging.NOTSET)


class PcmTests(unittest.TestCase):
    def test_fallback_matches_audioop(self):
        samples = array('h', [0, 1200, -3400, 32767, -32768, 15, -7]).tobytes()
        native = pcm.rms(samples)
        with mock.patch.object(pcm, 'audioop', None):
            self.assertEqual(pcm.rms(samples), native)
            self.assertEqual(pcm.rms(b''), 0)
            self.assertEqual(pcm.rms(b'\x01'), 0)


if __name__ == '__main__':
    unittest.main()
