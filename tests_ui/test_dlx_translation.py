"""DLX controls use a separate token and do not expose it in page state."""
import unittest
import test_listen_page as listen


@unittest.skipIf(listen.sync_playwright is None, 'Playwright is not installed')
class DlxTranslationUITests(unittest.TestCase):
    setUpClass = classmethod(listen.ListenPageTests.setUpClass.__func__)
    tearDownClass = classmethod(listen.ListenPageTests.tearDownClass.__func__)
    setUp = listen.ListenPageTests.setUp
    tearDown = listen.ListenPageTests.tearDown

    def test_token_and_url_controls(self):
        with self.bridge.lock:
            self.bridge.state['options']['caption_provider'] = 'DLX'
            self.bridge.state['caption_translation'] = dict(
                provider='DLX', providers=['DLX', 'Google Cloud Translation'], dedicated=True,
                has_token=True, models=['DLX'], resolved_model='DLX', loading=False, status='DLX')
            self.bridge.publish()
        self.page.click('.listen-toolbar [data-view="settings"]')
        self.page.click('[data-section="audio"]')
        self.page.wait_for_selector('#dlx-settings', state='visible')
        self.assertFalse(self.page.is_visible('#google-translation-settings'))
        self.assertFalse(self.page.is_visible('#caption_model'))
        self.assertEqual(self.page.get_attribute('#dlx-token', 'type'), 'password')
        self.assertEqual(self.page.input_value('#dlx-token'), '')
        self.assertIn('Configured', self.page.get_attribute('#dlx-token', 'placeholder'))
        self.page.fill('#dlx_url', 'http://localhost:1189/translate')
        self.page.locator('#dlx_url').blur()
        self.page.wait_for_function("current.options.dlx_url === 'http://localhost:1189/translate'")
        self.page.fill('#dlx-token', 'ui-dlx-token')
        self.page.click('#save-dlx-token')
        self.page.wait_for_function("document.querySelector('#dlx-token').value === ''")
        self.assertTrue(any(c.get('values', {}).get('dlx_token') == 'ui-dlx-token' for c in self.bridge.commands))
        self.assertNotIn('ui-dlx-token', self.page.evaluate('JSON.stringify(current)'))
        self.page.click('#clear-dlx-token')
        self.page.wait_for_timeout(200)
        self.assertTrue(any(c.get('values', {}).get('dlx_token') == '' for c in self.bridge.commands))
