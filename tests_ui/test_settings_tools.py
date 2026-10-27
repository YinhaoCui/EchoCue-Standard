"""Settings organization, inline diagnostics and full-size image navigation."""
import unittest
from pathlib import Path
import test_listen_page as listen


@unittest.skipIf(listen.sync_playwright is None, 'Playwright is not installed')
class SettingsToolsTests(unittest.TestCase):
    theme = 'workbench'
    setUpClass = classmethod(listen.ListenPageTests.setUpClass.__func__)
    tearDownClass = classmethod(listen.ListenPageTests.tearDownClass.__func__)
    setUp = listen.ListenPageTests.setUp
    tearDown = listen.ListenPageTests.tearDown

    def settings(self, name):
        self.page.click('button.nav[data-view="settings"]')
        self.page.click('[data-section="'+name+'"]')

    def test_appearance_only_shows_in_its_own_section_and_restores_listening_controls(self):
        self.settings('models')
        self.assertFalse(self.page.is_visible('#ui_theme'))
        self.assertEqual(self.page.locator('.intro .appearance-controls').count(), 0)
        nav=self.page.locator('#settings aside [data-section]').evaluate_all('(els)=>els.map(e=>e.dataset.section)')
        self.assertEqual(nav[nav.index('usage-settings')-1], 'interface-settings')
        self.page.click('[data-section="interface-settings"]')
        self.assertEqual(self.page.locator('#settings [data-section].active').get_attribute('data-section'),'interface-settings')
        for selector in ['#ui_theme','#settings-listen-frost','#listen_text_color','#listen_panel_color','#listen_transparency']:
            self.assertTrue(self.page.is_visible(selector),selector)
        self.page.locator('#listen_transparency').fill('72')
        self.page.locator('#listen_transparency').dispatch_event('change')
        self.page.wait_for_function("current.options.listen_transparency === '72'")
        self.page.screenshot(path=str(Path(listen.WEB).parents[1]/'work/ui-redesign/interface-settings.png'))
        self.page.click('button.nav[data-view="listen"]')
        self.assertTrue(self.page.is_visible('.listen-toolbar #listen_transparency'))
        self.page.click('#layout-button')
        self.assertTrue(self.page.is_visible('#layout-menu #listen_text_color'))
        self.assertEqual(self.page.input_value('#listen_transparency'), '72')

    def test_diagnostics_share_usage_tab_and_render_results_without_windows(self):
        result=dict(time='12:00:00',provider='DeepSeek',model='test-model',effort='auto',first=.2,elapsed=1.1,
                    chars_per_second=30,output_tokens=12,status='完成',error='',text='def example(): pass')
        with self.bridge.lock:
            self.bridge.state['diagnostics']=dict(speed=dict(provider='DeepSeek',model='test-model',models=['test-model'],
                efforts=['auto'],effort='auto',mode='Coding',fast=False,busy=False,status='完成',results=[result]),
                api=dict(busy=False,report='DeepSeek: available'),quota=dict(codex='Quota fixture',deepseek='',kimi='',legacy='Legacy fixture'))
            self.bridge.publish()
        self.settings('usage-settings')
        self.assertEqual(self.page.locator('#settings .side-bottom [data-action]').count(),0)
        for selector in ['#speed-start','#api-start','#quota-refresh']:
            self.assertTrue(self.page.is_visible(selector))
        self.page.click('#speed-start')
        self.page.wait_for_timeout(150)
        sent=next(c for c in self.bridge.commands if c.get('action')=='speed_start')
        self.assertEqual(sent['model'],'test-model')
        self.page.click('#api-start')
        self.page.wait_for_timeout(150)
        self.assertTrue(any(c.get('action')=='check_apis' for c in self.bridge.commands))
        self.assertIn('test-model',self.page.locator('#speed-results').inner_text())
        self.assertEqual(self.page.locator('#speed-detail').inner_text(),'def example(): pass')
        self.assertEqual(self.page.locator('#api-report').inner_text(),'DeepSeek: available')
        self.assertEqual(len(self.page.context.pages),1)
        self.page.screenshot(path=str(Path(listen.WEB).parents[1]/'work/ui-redesign/usage-diagnostics.png'))

    def test_chinese_appearance_labels_icons_and_color_previews(self):
        with self.bridge.lock:
            self.bridge.state['language']='zh'
            self.bridge.publish()
        self.page.wait_for_function("language === 'zh'")
        self.settings('interface-settings')
        self.assertEqual(self.page.locator('[data-i="Interface language"]').inner_text(),'界面语言')
        self.assertNotEqual(self.page.locator('[data-section="interface-settings"]').get_attribute('data-icon'),
                            self.page.locator('[data-section="preferences"]').get_attribute('data-icon'))
        self.page.locator('#listen_transparency').fill('99')
        self.page.locator('#listen_transparency').dispatch_event('change')
        for field,color,rgb in [('listen_text_color','#7e57c2','rgb(126, 87, 194)'),('listen_panel_color','#ffffff','rgb(255, 255, 255)')]:
            self.page.click('#'+field,force=True)
            self.page.fill('.color-list .hex',color)
            self.page.keyboard.press('Enter')
            self.page.wait_for_function('(args)=>current.options[args[0]]===args[1]',arg=[field,color])
            self.page.wait_for_function("""([field, rgb]) =>
                getComputedStyle(document.querySelector('label.color-control:has(#' + field + ')')).backgroundColor === rgb
            """, arg=[field, rgb])
            preview=self.page.locator('label.color-control:has(#'+field+')')
            self.assertEqual(preview.evaluate('el=>getComputedStyle(el).backgroundColor'),rgb)
            box=preview.bounding_box()
            self.assertEqual((box['width'],box['height']),(36,36))
            self.assertFalse(preview.locator('.color-glyph').is_visible())
        self.page.mouse.move(1050,100)
        self.page.wait_for_timeout(200)
        self.page.screenshot(path=str(Path(listen.WEB).parents[1]/('work/ui-redesign/interface-fixed-'+self.theme+'.png')))

    def test_double_click_opens_full_image_with_zoom_and_escape(self):
        self.page.route('**/image/*',lambda route:route.fulfill(content_type='image/svg+xml',body='<svg xmlns="http://www.w3.org/2000/svg" width="1800" height="1200"><rect width="1800" height="1200" fill="lightblue"/></svg>'))
        with self.bridge.lock:
            self.bridge.state['images']=[dict(id='full-size',title='Large screenshot')]
            self.bridge.publish()
        self.page.click('#context-toggle')
        self.page.locator('#context-images img').dblclick()
        self.page.wait_for_function('document.querySelector("#full-image").naturalWidth === 1800')
        self.assertTrue(self.page.is_visible('#image-viewer'))
        self.page.click('#image-actual')
        self.assertEqual(self.page.locator('#full-image').bounding_box()['width'],1800)
        self.page.click('#image-plus')
        self.assertEqual(self.page.locator('#full-image').bounding_box()['width'],2250)
        self.page.click('#image-fit')
        self.assertLess(self.page.locator('#full-image').bounding_box()['width'],1180)
        self.page.keyboard.press('Escape')
        self.assertFalse(self.page.is_visible('#image-viewer'))
        self.assertFalse(self.page.locator('.shell').evaluate('el=>el.inert'))
        self.assertEqual(len(self.page.context.pages),1)

    def test_all_settings_sections_fit_and_controls_do_not_overlap(self):
        self.page.click('button.nav[data-view="settings"]')
        for width in (760,1180):
            self.page.set_viewport_size(dict(width=width,height=820))
            for section in ('models','audio','meeting-settings','context','preferences','interface-settings','usage-settings','shortcuts'):
                self.page.click('[data-section="'+section+'"]')
                self.page.locator('#'+section+' details').evaluate_all('(els)=>els.forEach(el=>el.open=true)')
                self.page.wait_for_timeout(60)
                with self.subTest(width=width,section=section):
                    result=self.page.evaluate('''() => {
                        const host=document.querySelector('.settings-content'),clip=host.getBoundingClientRect();
                        const els=[...document.querySelectorAll('#settings input:not([type=color]),#settings select,#settings textarea,#settings button')]
                          .filter(e=>host.contains(e)&&!e.closest('details:not([open])')&&e.getClientRects().length&&getComputedStyle(e).visibility!=='hidden')
                          .map(e=>({id:e.id||e.textContent,r:e.getBoundingClientRect()}))
                          .filter(e=>e.r.top>=clip.top&&e.r.bottom<=clip.bottom);
                        const overlap=[];
                        for(let i=0;i<els.length;i++)for(let j=i+1;j<els.length;j++){
                          const a=els[i],b=els[j];
                          if(Math.min(a.r.right,b.r.right)-Math.max(a.r.left,b.r.left)>2&&Math.min(a.r.bottom,b.r.bottom)-Math.max(a.r.top,b.r.top)>2)overlap.push([a.id,b.id]);
                        }
                        return {overflow:host.scrollWidth-host.clientWidth,overlap};
                    }''')
                    self.assertLessEqual(result['overflow'],1)
                    self.assertEqual(result['overlap'],[])

    def test_template_layout_spacing_and_language_changes_keep_drafts(self):
        self.settings('context')
        self.page.fill('#instructions','Keep this user draft exactly')
        for lang in ('zh','en','zh'):
            with self.bridge.lock:
                self.bridge.state['language']=lang;self.bridge.publish()
            self.page.wait_for_function('(lang)=>language===lang',arg=lang)
            self.assertEqual(self.page.input_value('#instructions'),'Keep this user draft exactly')
            text=self.page.locator('#settings-footer .context-settings-save').inner_text()
            self.assertIn('未应用' if lang=='zh' else 'Unapplied',text)
        self.assertEqual(self.page.locator('#model').get_attribute('placeholder'),'默认模型')
        self.assertEqual(self.page.locator('#caption option:checked').inner_text(),'英语')
        self.assertEqual(self.page.input_value('#caption'),'English')
        self.assertEqual(self.page.locator('#hotkey-status').inner_text(),'快捷键已就绪')
        self.assertEqual(self.page.evaluate("[...document.querySelectorAll('[data-i]')].filter(e=>!translations[e.dataset.i]).map(e=>e.dataset.i)"),[])
        for width in (760,1180):
            self.page.set_viewport_size(dict(width=width,height=820))
            self.page.locator('#prompt-name').scroll_into_view_if_needed()
            for field,button in [('#prompt-name','#prompt-save'),('#scene-name','[data-meeting="save_scene"]')]:
                f=self.page.locator(field).bounding_box();b=self.page.locator(button).bounding_box()
                self.assertGreaterEqual(b['y']-(f['y']+f['height']),8)
            self.assertLess(self.page.locator('.workbench-template-bar').bounding_box()['y'],self.page.locator('.workbench-context-main').bounding_box()['y'])
        self.page.locator('.settings-content').evaluate('el=>el.scrollTop=0')
        self.page.screenshot(path=str(Path(listen.WEB).parents[1]/('work/ui-redesign/context-polished-'+self.theme+'.png')))


class GoldSettingsToolsTests(SettingsToolsTests):
    theme='cosmic'
