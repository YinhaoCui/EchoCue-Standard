"""Browser tests for popups.js: select lists, the color picker, tooltips and the
right-click menu are drawn in the page, so no WebView2 popup window is opened."""
import os
import unittest

from test_listen_page import FakeBridge, sync_playwright


@unittest.skipIf(sync_playwright is None, 'playwright is not installed (pip install -r requirements-dev.txt)')
class PopupTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.playwright = sync_playwright().start()
        channel = os.environ.get('ECHOCUE_UI_BROWSER', 'msedge')
        cls.browser = cls.playwright.chromium.launch(channel=channel or None, headless=True)

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.playwright.stop()

    def setUp(self):
        self.bridge = FakeBridge()
        self.page = self.browser.new_page(viewport={'width': 1180, 'height': 760})
        self.errors = []
        self.page.on('pageerror', lambda error: self.errors.append(str(error)))
        self.page.goto(self.bridge.url)
        self.page.wait_for_function("document.querySelector('#model-badge').textContent.includes('deepseek')")

    def tearDown(self):
        self.page.close()
        self.bridge.close()
        self.assertEqual(self.errors, [])

    def wait_sent(self, key, value):
        for _ in range(30):
            if any(sent.get(key) == value for sent in self.bridge.settings_sent()):
                return
            self.page.wait_for_timeout(100)
        self.fail(f'{key}={value!r} was never saved: {self.bridge.settings_sent()}')

    def test_native_select_list_is_blocked(self):
        prevented = self.page.evaluate("""() => {
            const e = new MouseEvent('mousedown', {bubbles: true, cancelable: true, button: 0});
            document.querySelector('#provider').dispatchEvent(e);
            return e.defaultPrevented;
        }""")
        self.assertTrue(prevented)

    def test_select_opens_an_in_page_list_and_saves_the_choice(self):
        self.page.click('#provider')
        items = self.page.locator('.select-list button')
        labels = self.page.eval_on_selector('#provider', 'el => [...el.options].map(o => o.textContent)')
        second = self.page.eval_on_selector('#provider', 'el => el.options[1].value')
        self.assertEqual(items.all_text_contents(), labels)
        self.assertEqual(self.page.locator('.select-list button.selected').text_content(), labels[0])
        self.assertTrue(self.page.evaluate("document.querySelector('.select-list').classList.contains('menu')"))
        items.nth(1).click()
        self.assertEqual(self.page.locator('.select-list').count(), 0)
        self.assertEqual(self.page.eval_on_selector('#provider', 'el => el.value'), second)
        self.wait_sent('provider', second)

    def test_select_works_from_the_keyboard(self):
        self.page.focus('#language')
        self.page.keyboard.press('Enter')
        self.assertEqual(self.page.locator('.select-list').count(), 1)
        self.page.keyboard.press('Escape')
        self.assertEqual(self.page.locator('.select-list').count(), 0)
        self.assertEqual(self.page.evaluate('document.activeElement.id'), 'language')
        self.page.keyboard.press('Alt+ArrowDown')
        self.page.keyboard.press('ArrowDown')
        self.page.keyboard.press('Enter')
        self.assertEqual(self.page.eval_on_selector('#language', 'el => el.value'), 'zh')
        self.wait_sent('language', 'zh')

    def test_outside_press_closes_the_list(self):
        self.page.click('#provider')
        self.page.mouse.click(5, 740)
        self.assertEqual(self.page.locator('.select-list').count(), 0)

    def test_color_input_uses_an_in_page_picker(self):
        self.page.click('button.nav[data-view="listen"]')
        self.page.click('#layout-button')
        self.page.click('#listen_text_color', force=True)
        self.assertEqual(self.page.locator('.color-list .swatch').count(), 30)
        self.page.click('.color-list .swatch[aria-label="#fdd835"]')
        self.assertEqual(self.page.locator('.color-list').count(), 0)
        self.assertFalse(self.page.locator('#layout-menu').is_hidden())  # its menu stays open
        self.assertEqual(self.page.eval_on_selector('#listen_text_color', 'el => el.value'), '#fdd835')
        self.wait_sent('listen_text_color', '#fdd835')

    def test_color_picker_accepts_a_typed_hex(self):
        self.page.click('button.nav[data-view="listen"]')
        self.page.click('#layout-button')
        self.page.click('#listen_panel_color', force=True)
        self.page.fill('.color-list .hex', '#123456')
        self.page.keyboard.press('Enter')
        self.assertEqual(self.page.eval_on_selector('#listen_panel_color', 'el => el.value'), '#123456')

    def test_no_title_attributes_remain_and_tips_show_in_page(self):
        self.page.click('button.nav[data-view="listen"]')
        self.page.wait_for_timeout(50)
        left = self.page.evaluate("[...document.body.querySelectorAll('[title]')].map(el => el.outerHTML.slice(0, 80))")
        self.assertEqual(left, [])
        self.page.hover('#pin')
        tip = self.page.locator('.tip')
        tip.wait_for(state='visible', timeout=2000)
        self.assertEqual(tip.text_content(), self.page.eval_on_selector('#pin', 'el => el.dataset.tip'))
        self.page.mouse.move(5, 740)
        self.page.wait_for_timeout(50)
        self.assertTrue(tip.is_hidden())

    def test_titles_set_later_are_moved_too(self):
        moved = self.page.evaluate("""async () => {
            const el = document.querySelector('#pin');
            el.title = 'late';
            await new Promise(r => setTimeout(r));
            return [el.hasAttribute('title'), el.dataset.tip];
        }""")
        self.assertEqual(moved, [False, 'late'])

    def test_right_click_menu_is_blocked(self):
        prevented = self.page.evaluate("""() => {
            const e = new MouseEvent('contextmenu', {bubbles: true, cancelable: true});
            document.body.dispatchEvent(e);
            return e.defaultPrevented;
        }""")
        self.assertTrue(prevented)


if __name__ == '__main__':
    unittest.main()
