import unittest
from glass_bridge import listen_layout, FONT_RANGE


class ListenLayoutTests(unittest.TestCase):
    def test_layout_accepts_pixel_sizes_and_empty_reset(self):
        self.assertEqual(listen_layout('80,240'), '80,240,0,0,0')
        self.assertEqual(listen_layout('80.6,240.2,900.9'), '80,240,900,900,900')
        self.assertEqual(listen_layout('0,0,700,0,900'), '0,0,700,0,900')
        self.assertEqual(listen_layout('0,0,0,0,0'), '')
        self.assertEqual(listen_layout(''), '')
        self.assertEqual(listen_layout(None), '')

    def test_layout_rejects_bad_values(self):
        for bad in ('80', '80,240,1,1', '80,240,0,0,0,0', 'a,b', '10,240', '80,50', 'inf,240', 'nan,240',
                    '80,99999', '80,240,100', '0,0,700,100,900'):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                listen_layout(bad)

    def test_font_range(self):
        self.assertEqual(FONT_RANGE, (12, 40))

    def test_color_format(self):
        from glass_bridge import COLOR
        for good in ('#ffffff', '#213953', '#00aa7f'):
            self.assertTrue(COLOR.fullmatch(good))
        for bad in ('ffffff', '#fff', '#12345g', 'red', '#1234567', 'url(x)'):
            self.assertIsNone(COLOR.fullmatch(bad))


if __name__ == '__main__':
    unittest.main()
