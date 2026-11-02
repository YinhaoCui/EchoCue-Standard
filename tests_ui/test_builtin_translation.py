import unittest
import test_listen_page as listen
from web_translation import PROVIDERS


@unittest.skipIf(listen.sync_playwright is None, 'Playwright is not installed')
class BuiltinTranslationUITests(unittest.TestCase):
    setUpClass = classmethod(listen.ListenPageTests.setUpClass.__func__)
    tearDownClass = classmethod(listen.ListenPageTests.tearDownClass.__func__)
    setUp = listen.ListenPageTests.setUp
    tearDown = listen.ListenPageTests.tearDown

    def test_native_providers_need_no_key_or_server_controls(self):
        with self.bridge.lock:
            self.bridge.state['options']['caption_provider'] = PROVIDERS[0]
            self.bridge.state['caption_translation'] = dict(provider=PROVIDERS[0], providers=list(PROVIDERS),
                dedicated=True, builtin=True, models=[], loading=False, resolved_model='web', status='No API key or DLX needed.')
            self.bridge.publish()
        self.page.click('.listen-toolbar [data-view="settings"]')
        self.page.click('[data-section="audio"]')
        self.page.wait_for_function("document.querySelector('#caption_provider').value === 'DeepL (built-in)'")
        for provider in PROVIDERS:
            self.page.select_option('#caption_provider', provider)
            self.page.wait_for_function('(p)=>current.options.caption_provider === p', arg=provider)
            self.assertFalse(self.page.is_visible('#google-translation-settings'))
            self.assertFalse(self.page.is_visible('#dlx-settings'))
            self.assertFalse(self.page.is_visible('#caption_model'))
            self.assertNotIn(provider, self.page.locator('#provider option').all_text_contents())
        self.assertTrue(all('google_translation_key' not in c.get('values', {}) and
                            'dlx_token' not in c.get('values', {}) for c in self.bridge.commands))
