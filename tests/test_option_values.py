import unittest

import option_values as o


class OptionValueTests(unittest.TestCase):
    def test_legacy_chinese_values_migrate_to_codes(self):
        self.assertEqual(o.normalize('warm_context', '开启'), 'on')
        self.assertEqual(o.normalize('incremental_context', '关闭'), 'off')
        self.assertEqual(o.normalize('speculate', '每段定稿'), 'segments')
        self.assertEqual(o.normalize('speculate', '仅疑问句'), 'questions')
        self.assertEqual(o.normalize('deadline', '不限时'), 'unlimited')
        self.assertEqual(o.normalize('max_output', '服务默认'), 'service_default')

    def test_codes_and_custom_numbers_are_kept_and_junk_falls_back(self):
        self.assertEqual(o.normalize('speculate', 'off'), 'off')
        self.assertEqual(o.normalize('deadline', '45'), '45')
        self.assertEqual(o.normalize('deadline', '-5'), 'unlimited')
        self.assertEqual(o.normalize('max_output', None), 'service_default')
        self.assertEqual(o.normalize('warm_context', 'yes'), 'on')

    def test_validate_rejects_values_the_interface_never_sends(self):
        self.assertEqual(o.validate('speculate', 'segments'), 'segments')
        for key, value in (('speculate', '每段定稿'), ('warm_context', ''), ('max_output', '0')):
            with self.assertRaises(ValueError):
                o.validate(key, value)

    def test_conversions(self):
        self.assertEqual(o.seconds('unlimited'), float('inf'))
        self.assertEqual(o.seconds('300'), 300)
        self.assertIsNone(o.tokens('service_default'))
        self.assertEqual(o.tokens('8192'), 8192)


if __name__ == '__main__':
    unittest.main()
