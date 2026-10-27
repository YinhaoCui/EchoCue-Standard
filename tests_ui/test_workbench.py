"""Exercise the real workbench against the existing isolated command bridge."""
import unittest
from pathlib import Path
import test_listen_page as listen


@unittest.skipIf(listen.sync_playwright is None, 'Playwright is not installed')
class WorkbenchTests(unittest.TestCase):
    theme = 'workbench'
    setUpClass = classmethod(listen.ListenPageTests.setUpClass.__func__)
    tearDownClass = classmethod(listen.ListenPageTests.tearDownClass.__func__)
    setUp = listen.ListenPageTests.setUp
    tearDown = listen.ListenPageTests.tearDown
    meeting_ack = listen.ListenPageTests.meeting_ack
    test_context_apply = listen.ListenPageTests.test_answer_applies_context_first_without_browser_storage
    test_context_conflict = listen.ListenPageTests.test_context_conflict_keeps_draft_until_discarded
    test_templates = listen.ListenPageTests.test_prompt_templates_save_load_apply_and_delete
    test_scenes = listen.ListenPageTests.test_scene_save_applies_draft_and_load_requires_confirmation
    test_shortcuts = listen.ListenPageTests.test_shortcuts_open_in_settings_and_validate_save_and_reset
    test_menus = listen.ListenPageTests.test_menus_open_one_at_a_time_and_close
    test_focus_policy = listen.ListenPageTests.test_listening_avoids_activation_but_text_editors_allow_keyboard_focus

    def settings(self, section):
        self.page.click('button.nav[data-view=settings]')
        self.page.click(f'#settings [data-section="{section}"]')
        self.assertEqual(self.page.locator('#settings [data-section].active').get_attribute('data-section'), section)

    def test_bottom_menu_opens_above_toolbar(self):
        self.page.set_viewport_size(dict(width=1164, height=801))
        self.page.click('#layout-button')
        menu = self.page.locator('#layout-menu').bounding_box()
        button = self.page.locator('#layout-button').bounding_box()
        self.assertGreaterEqual(menu['y'], 8)
        self.assertLessEqual(menu['y'] + menu['height'], button['y'])
        self.assertEqual(self.page.locator('#layout-reset').evaluate('el=>getComputedStyle(el).color'),
                         'rgb(238, 232, 220)' if self.theme == 'cosmic' else 'rgb(32, 44, 61)')

    def test_prompt_tools_leave_space_for_focus_outline(self):
        self.settings('context')
        self.page.focus('#instructions')
        field = self.page.locator('#instructions').bounding_box()
        tools = self.page.locator('#context [data-action="import"]').bounding_box()
        self.assertGreaterEqual(tools['y'] - field['y'] - field['height'], 8)

    def test_open_menu_repositions_when_switching_from_classic(self):
        self.page.evaluate("applyTheme('classic')")
        self.page.click('#layout-button')
        self.page.select_option('#live-ui-theme', 'workbench')
        self.page.wait_for_function("document.querySelector('#layout-menu').getBoundingClientRect().bottom < document.querySelector('#layout-button').getBoundingClientRect().top")
        folder=Path(__file__).resolve().parent.parent/'work'/'ui-redesign'
        self.page.screenshot(path=str(folder/'layout-menu-fixed.png'))

    def test_gold_palette_frost_and_theme_colors(self):
        self.settings('interface-settings')
        self.assertEqual(self.page.locator('#ui_theme option').evaluate_all('(els)=>els.map(e=>e.value)'), ['workbench','cosmic','classic'])
        self.page.select_option('#ui_theme', 'cosmic')
        self.page.wait_for_function("document.body.dataset.palette === 'gold'")
        self.assertEqual(self.page.evaluate('document.body.dataset.theme'), 'workbench')
        self.page.locator('#settings-listen-frost').fill('80')
        self.page.locator('#settings-listen-frost').dispatch_event('change')
        self.page.wait_for_function("current.options.listen_frost === '80'")
        self.page.click('button.nav[data-view=listen]')
        self.assertEqual(self.page.locator('.workspace-rail').is_visible(), False)
        self.page.evaluate("window.pywebview={api:{shape:layout=>{window.__nativeFrost=layout;return Promise.resolve(true)}}};lastShape='';scheduleShape()")
        self.page.wait_for_function("window.__nativeFrost?.frost === 80")
        self.assertEqual(self.page.evaluate('window.__nativeFrost.view'), 'listen')
        self.assertEqual(self.page.locator('.transcript-panel').evaluate('el=>getComputedStyle(el).backdropFilter'), 'none')
        self.assertEqual(self.page.input_value('#listen_panel_color'), '#151619')
        self.page.click('#layout-button')
        self.page.locator('#live-theme-colors').uncheck()
        self.page.wait_for_function("current.options.listen_theme_colors === '0'")
        self.page.locator('#live-theme-colors').check()
        self.page.wait_for_function("current.options.listen_theme_colors === '1'")
        self.page.evaluate("applyTheme('workbench')")
        self.assertEqual(self.page.input_value('#listen_panel_color'), '#ffffff')
        self.page.evaluate("applyTheme('cosmic')")
        self.page.keyboard.press('Escape')
        self.page.set_viewport_size(dict(width=1440,height=960))
        with self.bridge.lock:
            self.bridge.state.update(language='zh',transcript='How should we handle retries?\n\n我们应该如何处理重试？',output='## 重试策略\n\n采用指数退避，并为请求设置幂等键。')
            self.bridge.publish()
        self.page.wait_for_function("language === 'zh'")
        folder=Path(__file__).resolve().parent.parent/'work'/'ui-redesign'
        self.page.screenshot(path=str(folder/'gold-listen.png'))
        self.settings('context')
        self.page.screenshot(path=str(folder/'gold-context.png'))

    def test_color_swatches_and_applied_colors_are_exact(self):
        self.page.locator('#listen_transparency').fill('1')
        self.page.locator('#listen_transparency').dispatch_event('change')
        self.page.click('#layout-button')
        for field, color, rgb in [('listen_text_color','#fdd835','rgb(253, 216, 53)'),
                                  ('listen_panel_color','#e7e5e4','rgba(231, 229, 228, 0.99)')]:
            self.page.click('#'+field, force=True)
            for swatch in self.page.locator('.color-list .swatch').all():
                hex_color=swatch.get_attribute('aria-label')
                expected='rgb('+', '.join(str(int(hex_color[i:i+2],16)) for i in (1,3,5))+')'
                self.assertEqual(swatch.evaluate('el=>getComputedStyle(el).backgroundColor'),expected)
            self.page.fill('.color-list .hex', color)
            self.page.keyboard.press('Enter')
            self.page.wait_for_function('(args)=>current.options[args[0]]===args[1]',arg=[field,color])
            self.assertEqual(self.page.input_value('#'+field),color)
            selector, prop=('#transcript','color') if field=='listen_text_color' else ('.transcript-panel','backgroundColor')
            self.assertEqual(self.page.locator(selector).evaluate('(el,prop)=>getComputedStyle(el)[prop]',prop),rgb)
        self.assertEqual(self.page.evaluate('current.options.listen_theme_colors'),'0')

    def test_titlebar_transparency_and_frost_are_independent(self):
        self.page.evaluate("window.pywebview={api:{shape:layout=>{window.__nativeFrost=layout;return Promise.resolve(true)}}};lastShape='';scheduleShape()")
        self.page.wait_for_function('window.__nativeFrost?.view === "listen"')
        frost=self.page.evaluate('window.__nativeFrost.frost')
        self.page.locator('#listen_transparency').fill('99')
        self.page.locator('#listen_transparency').dispatch_event('change')
        self.page.wait_for_function("current.options.listen_transparency === '99'")
        self.assertEqual(self.page.locator('.capsule').evaluate('el=>getComputedStyle(el).backgroundColor'),
                         'rgba(27, 28, 32, 0.01)' if self.theme=='cosmic' else 'rgba(245, 247, 250, 0.01)')
        self.assertEqual(self.page.locator('.capsule').evaluate('el=>getComputedStyle(el).opacity'),'1')
        self.assertEqual(self.page.evaluate('window.__nativeFrost.frost'),frost)
        self.page.click('#layout-button')
        self.page.locator('#live-listen-frost').fill('90')
        self.page.locator('#live-listen-frost').dispatch_event('change')
        self.page.wait_for_function('window.__nativeFrost?.frost === 90')
        self.assertEqual(self.page.input_value('#listen_transparency'),'99')

    def test_sections_drafts_and_theme_switch_keep_controls(self):
        self.settings('context')
        self.page.fill('#instructions', 'Keep this unsaved draft')
        self.assertTrue(self.page.is_visible('#prompt-template'))
        self.assertTrue(self.page.is_visible('#scene-picker'))
        self.settings('audio')
        self.assertTrue(self.page.is_visible('#source'))
        self.assertFalse(self.page.is_visible('#instructions'))
        self.settings('models')
        self.assertTrue(self.page.is_visible('#caption_provider'))
        self.page.click('button.nav[data-view=listen]')
        self.page.click('#context-toggle')
        self.assertEqual(self.page.input_value('#context-instructions'), 'Keep this unsaved draft')
        self.assertEqual(self.page.locator('#context-drawer #prompt-template').count(), 1)
        self.page.click('#context-close')
        self.settings('context')
        self.page.click('.context-settings-save button')
        self.page.wait_for_function("current.instructions === 'Keep this unsaved draft'")
        self.page.evaluate("applyTheme('classic')")
        self.assertEqual(self.page.locator('#context-drawer #prompt-template').count(), 1)
        self.assertEqual(self.page.input_value('#instructions'), 'Keep this unsaved draft')
        self.page.evaluate("applyTheme('workbench')")
        self.assertTrue(self.page.is_visible('#instructions'))
        self.assertEqual(self.page.locator('[id]').evaluate_all('(els)=>els.map(e=>e.id).length === new Set(els.map(e=>e.id)).size'), True)

    def test_answer_tabs_do_not_lose_output_or_change_running_tasks(self):
        with self.bridge.lock:
            self.bridge.state.update(output='First answer.\nSecond answer.', jobs=[
                dict(id=1, done=True, completed=True, span=[0, 13], model='old-model', state='Done'),
                dict(id=2, done=False, span=[14, 28], model='other-model', state='Running')])
            self.bridge.publish()
        self.page.click('#answer-tab-1')
        self.assertEqual(self.page.locator('#workbench-output').text_content(), 'First answer.')
        self.assertIn('old-model', self.page.locator('.workbench-task-info').text_content())
        with self.bridge.lock:
            self.bridge.state['output'] += ' More.'
            self.bridge.state['jobs'][1]['span'][1] += 6
            self.bridge.publish()
        self.page.wait_for_function("current.output.endsWith(' More.')")
        self.assertEqual(self.page.locator('#workbench-output').text_content(), 'First answer.')
        self.page.click('#answer-tab-2')
        self.assertIn('Second answer. More.', self.page.locator('#workbench-output').text_content())
        self.page.click('.workbench-task-info button')
        self.page.wait_for_timeout(100)
        self.assertIn({'action': 'cancel_job', 'id': 2}, self.bridge.commands)
        self.page.click('#answer-tab-all')
        self.assertIn('First answer.', self.page.locator('#workbench-output').text_content())
        self.assertIn('Second answer.', self.page.locator('#workbench-output').text_content())

    def test_all_settings_reachable_and_responsive(self):
        for width, height in [(1440, 960), (640, 820)]:
            self.page.set_viewport_size(dict(width=width, height=height))
            for section, control in [('models','#provider'),('audio','#source'),('meeting-settings','#auto_answers'),
                                     ('context','#instructions'),('preferences','#background_mode'),
                                     ('shortcuts','#hotkeys-save'),('usage-settings','#usage')]:
                self.settings(section)
                self.assertTrue(self.page.is_visible(control), (width, section))
                self.assertTrue(self.page.evaluate('document.documentElement.scrollWidth <= innerWidth'), (width, section))
        self.page.click('button.nav[data-view=listen]')
        self.page.click('#more')
        self.assertTrue(self.page.is_visible('[data-action=export_session]'))



class GoldWorkbenchTests(WorkbenchTests):
    theme = 'cosmic'


if __name__ == '__main__':
    unittest.main()
