"""Google Translation credentials are editable without returning saved keys to the page."""
import unittest
import test_listen_page as listen


@unittest.skipIf(listen.sync_playwright is None, 'Playwright is not installed')
class GoogleTranslationUITests(unittest.TestCase):
    setUpClass = classmethod(listen.ListenPageTests.setUpClass.__func__)
    tearDownClass = classmethod(listen.ListenPageTests.tearDownClass.__func__)
    setUp = listen.ListenPageTests.setUp
    tearDown = listen.ListenPageTests.tearDown

    def test_dedicated_key_form_and_save_clear_controls(self):
        provider = 'Google Cloud Translation'
        with self.bridge.lock:
            self.bridge.state['options']['caption_provider'] = provider
            self.bridge.state['caption_translation'] = dict(
                provider=provider, providers=[provider, 'DeepSeek'], dedicated=True, has_key=True,
                models=['nmt'], resolved_model='nmt', loading=False, status='Google Cloud Translation NMT')
            self.bridge.publish()
        self.page.click('.listen-toolbar [data-view="settings"]')
        self.page.click('[data-section="audio"]')
        self.page.wait_for_selector('#google-translation-settings', state='visible')
        self.assertEqual(self.page.locator('#google-translation-key').get_attribute('type'), 'password')
        self.assertEqual(self.page.input_value('#google-translation-key'), '')
        self.assertIn('Configured', self.page.locator('#google-translation-key').get_attribute('placeholder'))
        self.assertFalse(self.page.is_visible('#caption_model'))
        self.assertFalse(self.page.is_visible('#caption-model-picker'))
        self.assertNotIn(provider, self.page.locator('#provider option').all_text_contents())
        self.page.fill('#google-translation-key', 'ui-test-key')
        self.page.click('#save-google-translation-key')
        self.page.wait_for_function("document.querySelector('#google-translation-key').value === ''")
        self.assertTrue(any(c.get('values', {}).get('google_translation_key') == 'ui-test-key' for c in self.bridge.commands))
        self.assertNotIn('ui-test-key', self.page.evaluate('JSON.stringify(current)'))
        self.page.click('#clear-google-translation-key')
        self.page.wait_for_timeout(200)
        self.assertTrue(any(c.get('values', {}).get('google_translation_key') == '' for c in self.bridge.commands))


if __name__ == '__main__':
    unittest.main()
