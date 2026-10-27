"""Browser tests for the Listen page, run in headless Microsoft Edge.

A small fake bridge serves the real files in app/web and answers /state and
/command the way glass_bridge does. Look settings go through the real
validators, so a bad value the page sends fails here too.
"""
import json
import os
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

try:
    from playwright.sync_api import sync_playwright
except ImportError:  # optional dev dependency, see requirements-dev.txt
    sync_playwright = None

WEB = Path(__file__).resolve().parent.parent / 'app' / 'web'
TOKEN = 'ui-test-token'


def fixture_state():
    from settings_state import DEFAULT_OPTIONS
    from prompt_templates import builtin_prompts
    from hotkey_settings import DEFAULTS as HOTKEY_DEFAULTS
    return dict(
        language='en', hotkeys=dict(HOTKEY_DEFAULTS), hotkey_defaults=dict(HOTKEY_DEFAULTS), hotkey_status='Shortcuts ready', hotkey_result=None, navigation_request=None,
        providers=['DeepSeek', 'Kiro（本机登录）'], provider='DeepSeek', model='deepseek-chat',
        models=['deepseek-chat'], model_status='', efforts=['auto'], effort='auto', cli=False, has_key=True,
        options=dict(DEFAULT_OPTIONS), engines=['英文 · Zipformer'], caption='English', answer='English',
        history=True, history_count=0, context_version=0, context_edit=None,
        prompt_templates={}, prompt_templates_version=0, prompt_templates_error='', prompt_result=None, prompt_presets=builtin_prompts(),
        meeting=dict(scenes=[], answers=[], scene_version=0, scenes_error='', result=None, recap_pending=False), speaker_note='',
        profile='', documents='', summary='', instructions='', answer_mode='快速',
        devices=['Speakers'], device=0, microphones=[], microphone='', images=[], listening=False,
        preparing=False, status='Ready', transcript='Hello there. ' * 40, output='An answer. ' * 60,
        usage='—', jobs=[], native=dict(topmost=False), closing=False)


class FakeBridge:
    def __init__(self, theme='classic'):
        from glass_bridge import layout_value, listen_presets
        from settings_state import LAYOUT_KEYS
        from glass_bridge import state_query
        from state_feed import StateFeed
        self.state, self.commands, self.lock = fixture_state(), [], threading.Lock()
        self.state['options']['ui_theme'] = theme
        self.feed = StateFeed()
        self.publish()
        bridge = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_):
                pass

            def reply(self, status, body, mime='application/json'):
                self.send_response(status)
                self.send_header('Content-Type', mime)
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                try:
                    self.wfile.write(body)
                except ConnectionError:  # the page closed during a waiting read
                    pass

            def do_GET(self):
                if self.path.split('?', 1)[0] == '/state':
                    bridge.reads += 1
                    return self.reply(200, bridge.feed.read(**state_query(self.path)))
                name = {'/': 'index.html', '/app.js': 'app.js', '/context_editor.js': 'context_editor.js', '/meeting.js': 'meeting.js', '/markdown.js': 'markdown.js', '/popups.js': 'popups.js', '/style.css': 'style.css'}.get(self.path)
                if self.path == '/workbench.js':
                    name = 'workbench.js'
                if self.path == '/settings_tools.js':
                    name = 'settings_tools.js'
                if self.path.startswith('/icons/'):
                    name = 'icons/' + Path(self.path).name
                path = WEB / name if name else None
                if not path or not path.is_file():
                    return self.reply(404, b'{}')
                mime = {'html': 'text/html', 'js': 'text/javascript', 'css': 'text/css', 'svg': 'image/svg+xml'}
                self.reply(200, path.read_bytes(), mime[path.suffix[1:]] + '; charset=utf-8')

            def do_POST(self):
                data = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                with bridge.lock:
                    bridge.commands.append(data)
                    if data.get('action')=='save_hotkeys':
                        from hotkey_settings import validate
                        try:
                            bridge.state['hotkeys']=validate(data['values'])
                            bridge.state['hotkey_result']=dict(id=data['id'],ok=True)
                        except ValueError as exc:
                            bridge.state['hotkey_result']=dict(id=data['id'],ok=False,error=str(exc))
                    if data.get('action') in ('save_prompt_template', 'delete_prompt_template'):
                        from prompt_templates import updated_templates
                        try:
                            if data['version'] != bridge.state['prompt_templates_version']:
                                raise ValueError('stale library')
                            bridge.state['prompt_templates'] = updated_templates(bridge.state['prompt_templates'],data['name'],data.get('text'),delete=data['action']=='delete_prompt_template',overwrite=data.get('overwrite',False))
                            bridge.state['prompt_templates_version'] += 1
                            bridge.state['prompt_result'] = dict(id=data['id'],ok=True)
                        except ValueError:
                            bridge.state['prompt_result'] = dict(id=data['id'],ok=False,error='invalid template')
                    if data.get('action') == 'apply_context':
                        ok = data.get('version') == bridge.state['context_version']
                        bridge.state['context_edit'] = dict(id=data['id'], ok=ok)
                        if ok:
                            bridge.state.update(data['values'])
                            bridge.state['summary'] = ''
                            bridge.state['context_version'] += 1
                    if data.get('action') == 'clear_history':
                        bridge.state['history_count'] = 0
                    if data.get('action') == 'settings':
                        values = data.get('values', {})
                        try:
                            look = {k: layout_value(k, values[k]) for k in LAYOUT_KEYS if k in values}
                            from settings_state import PRESENTATION_DEFAULTS, presentation_value
                            look.update({k: presentation_value(k, values[k]) for k in PRESENTATION_DEFAULTS if k in values})
                            if 'listen_presets' in values:
                                look['listen_presets'] = listen_presets(values['listen_presets'])
                        except ValueError as exc:
                            bridge.state['status'] = 'rejected: %s' % exc
                            return self.reply(400, b'{}')
                        bridge.state['options'].update(look)
                        from meeting_assistance import OPTIONS
                        bridge.state['options'].update({k: v for k, v in values.items() if k in OPTIONS and v in OPTIONS[k]})
                        if 'history' in values:
                            bridge.state['history'] = values['history']
                    bridge.publish()
                self.reply(202, b'{"queued":true}')

        self.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        self.url = 'http://127.0.0.1:%d/#%s' % (self.server.server_port, TOKEN)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    reads = 0

    def publish(self):
        self.feed.publish(json.loads(json.dumps(self.state)))

    def settings_sent(self):
        with self.lock:
            return [c['values'] for c in self.commands if c.get('action') == 'settings']

    def option(self, key):
        with self.lock:
            return self.state['options'][key]

    def close(self):
        self.server.shutdown()
        self.server.server_close()


@unittest.skipIf(sync_playwright is None, 'playwright is not installed (pip install -r requirements-dev.txt)')
class ListenPageTests(unittest.TestCase):
    def test_listening_avoids_activation_but_text_editors_allow_keyboard_focus(self):
        self.page.evaluate("""() => {
            window.pywebview = {api: {shape: layout => {
                window.__activationLayout = layout; return Promise.resolve(true);
            }}};
            lastShape = ''; scheduleShape();
        }""")
        self.page.wait_for_function('window.__activationLayout?.mouse_only === true')
        self.page.click('#context-toggle')
        self.page.wait_for_function('window.__activationLayout?.mouse_only === true')
        self.page.fill('#context-instructions', 'Keyboard input still works')
        self.page.wait_for_function('window.__activationLayout?.mouse_only === false')
        self.assertEqual(self.page.input_value('#context-instructions'), 'Keyboard input still works')
        self.page.click('#context-toggle')
        self.page.wait_for_function('window.__activationLayout?.mouse_only === true')
        self.page.click('#listen button[data-view=settings]')
        self.page.wait_for_function('window.__activationLayout?.mouse_only === false')

    def test_toolbar_menus_keep_no_activation_until_a_text_field_is_focused(self):
        self.page.evaluate("""() => {
            window.pywebview={api:{shape:layout=>{window.__activationLayout=layout;return Promise.resolve(true)}}};
            lastShape=''; scheduleShape();
        }""")
        for button, menu in (('#layout-button','#layout-menu'),('#more','#more-menu'),('#layout-button','#layout-menu')):
            self.page.click(button)
            self.assertTrue(self.page.is_visible(menu))
            self.page.wait_for_function('window.__activationLayout?.mouse_only === true')
        self.assertFalse(self.page.evaluate('window.__activationLayout.keyboard_editing'))
        self.page.fill('#preset-name','My layout')
        self.page.wait_for_function('window.__activationLayout?.mouse_only === false')
        self.assertTrue(self.page.evaluate('window.__activationLayout.keyboard_editing'))
        self.page.click('#more')
        self.page.wait_for_function('window.__activationLayout?.mouse_only === true')

    def test_catalog_refresh_keeps_unlisted_selection_without_claiming_availability(self):
        with self.bridge.lock:
            self.bridge.state.update(model='saved-custom', models=['new-chat'],
                                     model_status='Catalog source: last successful refresh.')
            self.bridge.publish()
        self.page.wait_for_function("document.querySelector('#model-picker').value === 'saved-custom'")
        options=self.page.locator('#model-picker option')
        self.assertEqual(options.evaluate_all('(items)=>items.map(x=>x.value)'), ['', 'new-chat', 'saved-custom'])
        self.assertIn('selected, not listed', options.last.text_content())
        self.assertEqual(self.page.input_value('#model'), 'saved-custom')
        with self.bridge.lock:
            self.bridge.state['models']=[]
            self.bridge.publish()
        self.page.wait_for_function("document.querySelector('#model-picker').options.length === 2")
        self.assertEqual(self.page.input_value('#model-picker'), 'saved-custom')

    def test_prompt_templates_save_load_apply_and_delete(self):
        self.page.click('#context-toggle')
        self.page.fill('#context-instructions', 'Be a concise tutor')
        self.page.click('.prompt-library summary')
        self.page.fill('#prompt-name', 'Tutor')
        self.page.click('#prompt-save')
        self.page.wait_for_function("current.prompt_templates.Tutor === 'Be a concise tutor'")
        self.assertEqual(self.bridge.state['instructions'], '')
        self.page.fill('#context-instructions', 'unsaved alternative')
        self.page.click('#prompt-load')
        self.assertEqual(self.page.input_value('#context-instructions'), 'unsaved alternative')
        self.page.click('#prompt-load')
        self.assertEqual(self.page.input_value('#context-instructions'), 'Be a concise tutor')
        self.page.click('#context-apply')
        self.page.wait_for_function("current.instructions === 'Be a concise tutor'")
        self.page.click('#prompt-delete')
        self.assertIn('Tutor', self.bridge.state['prompt_templates'])
        self.page.click('#prompt-delete')
        self.page.wait_for_function("!Object.hasOwn(current.prompt_templates,'Tutor')")
        self.assertEqual(self.page.input_value('#context-instructions'), 'Be a concise tutor')
        self.assertNotIn('Be a concise tutor', self.page.evaluate('JSON.stringify(localStorage)+JSON.stringify(sessionStorage)'))

    def test_prompt_template_replace_needs_confirmation(self):
        with self.bridge.lock:
            self.bridge.state['prompt_templates'] = {'Tutor': 'old prompt'}
            self.bridge.publish()
        self.page.click('#context-toggle')
        self.page.fill('#context-instructions', 'new prompt')
        self.page.click('.prompt-library summary')
        self.page.fill('#prompt-name', 'Tutor')
        self.page.click('#prompt-save')
        self.assertEqual(self.bridge.state['prompt_templates']['Tutor'], 'old prompt')
        self.page.click('#prompt-save')
        self.page.wait_for_function("current.prompt_templates.Tutor === 'new prompt'")

    def test_answer_applies_context_first_without_browser_storage(self):
        self.page.click('#context-toggle')
        self.page.fill('#context-instructions', 'private draft fixture')
        self.page.click('#context-close')
        self.page.click('.listen-toolbar [data-action="answer"]')
        self.page.wait_for_function("current.instructions === 'private draft fixture'")
        self.page.wait_for_timeout(150)
        actions=[c['action'] for c in self.bridge.commands]
        self.assertLess(actions.index('apply_context'), actions.index('answer'))
        self.assertNotIn('private draft fixture', self.page.evaluate('JSON.stringify(localStorage)+JSON.stringify(sessionStorage)'))

    def test_context_editor_applies_without_losing_draft_on_refresh(self):
        self.page.click('#context-toggle')
        self.page.fill('#context-profile', 'Notes remain intact')
        with self.bridge.lock:
            self.bridge.state['status'] = 'background update'
            self.bridge.publish()
        self.page.wait_for_function("current.status === 'background update'")
        self.assertEqual(self.page.input_value('#context-profile'), 'Notes remain intact')
        self.page.click('#context-apply')
        self.page.wait_for_function("current.profile === 'Notes remain intact' && !contextEditor.isDirty('profile')")
        self.assertEqual(self.page.input_value('#profile'), 'Notes remain intact')
        self.assertTrue(self.page.is_disabled('#context-apply'))

    def test_context_conflict_keeps_draft_until_discarded(self):
        self.page.click('#context-toggle')
        self.page.fill('#context-documents', 'local draft')
        with self.bridge.lock:
            self.bridge.state.update(documents='external source', context_version=1)
            self.bridge.publish()
        self.page.wait_for_function('current.context_version === 1')
        self.page.click('#context-apply')
        self.page.wait_for_function("document.querySelector('#context-edit-status').textContent.includes('changed elsewhere')")
        self.assertEqual(self.page.input_value('#context-documents'), 'local draft')
        self.assertEqual(self.bridge.state['documents'], 'external source')
        self.page.click('#context-reload')
        self.assertEqual(self.page.input_value('#context-documents'), 'external source')

    def test_context_memory_controls_and_narrow_window(self):
        with self.bridge.lock:
            self.bridge.state['history_count'] = 3
            self.bridge.publish()
        self.page.click('#context-toggle')
        self.page.wait_for_function("document.querySelector('#context-memory-status').textContent.includes('3 Q&A')")
        self.page.locator('#context-history').uncheck()
        self.page.wait_for_function('current.history === false')
        self.page.click('#context-clear-history')
        self.assertEqual(self.bridge.state['history_count'], 3)
        self.page.click('#context-clear-history')
        self.page.wait_for_function('current.history_count === 0')
        self.page.set_viewport_size(dict(width=760, height=560))
        self.assertTrue(self.page.evaluate("""() => {
            const r=document.querySelector('#context-drawer').getBoundingClientRect();
            return r.left>=0 && r.right<=innerWidth && r.bottom<=innerHeight;
        }"""))

    @classmethod
    def setUpClass(cls):
        cls.playwright = sync_playwright().start()
        channel = os.environ.get('ECHOCUE_UI_BROWSER', 'msedge')
        cls.browser = cls.playwright.chromium.launch(channel=channel or None, headless=True,
                                                    ignore_default_args=['--hide-scrollbars'])

    def meeting_ack(self, action):
        for _ in range(60):
            with self.bridge.lock:
                commands = [c for c in self.bridge.commands if c.get('action') == action]
                if commands:
                    command = commands[-1]
                    self.bridge.state['meeting']['result'] = dict(id=command['id'], ok=True)
                    self.bridge.publish()
                    return command
            self.page.wait_for_timeout(50)
        self.fail('No meeting command: ' + action)

    def test_meeting_settings_and_audio_controls_lock_while_listening(self):
        self.page.click('.listen-toolbar [data-view="settings"]')
        self.page.select_option('#auto_answers', 'questions')
        self.wait_option('auto_answers', 'questions')
        self.page.select_option('#speaker_labels', '1')
        self.wait_option('speaker_labels', '1')
        with self.bridge.lock:
            self.bridge.state['listening'] = True
            self.bridge.publish()
        self.page.wait_for_function("document.querySelector('#speaker_labels').disabled")
        self.assertTrue(self.page.is_disabled('#echo_suppression'))
        self.assertFalse(self.page.is_disabled('#auto_answers'))
        self.assertIn('allowance', self.page.text_content('#meeting-settings'))

    def test_scene_save_applies_draft_and_load_requires_confirmation(self):
        self.page.click('#context-toggle')
        self.page.locator('#context-drawer details').first.locator('summary').click()
        self.page.fill('#context-instructions', 'Use my reference material')
        self.page.fill('#scene-name', 'Work')
        self.page.click('[data-meeting="save_scene"]')
        command = self.meeting_ack('save_scene')
        self.assertEqual(self.bridge.state['instructions'], 'Use my reference material')
        self.assertEqual(command['context_version'], self.bridge.state['context_version'])
        self.page.wait_for_function("document.querySelector('#scene-status').textContent === 'Done.'")
        with self.bridge.lock:
            self.bridge.state['meeting']['scenes'] = ['Work']
            self.bridge.state['meeting']['scene_version'] = 1
            self.bridge.publish()
        self.page.wait_for_function("document.querySelector('#scene-picker').options[0].value === 'Work'")
        self.page.select_option('#scene-picker', 'Work')
        self.page.fill('#context-instructions', 'unsaved draft')
        self.page.click('[data-meeting="load_scene"]')
        with self.bridge.lock:
            self.assertFalse(any(c.get('action') == 'load_scene' for c in self.bridge.commands))
        self.page.click('[data-meeting="load_scene"]')
        self.meeting_ack('load_scene')
        self.page.wait_for_function("document.querySelector('#context-instructions').value === 'Use my reference material'")

    def test_quick_action_keeps_selected_answer_id_and_followup(self):
        with self.bridge.lock:
            self.bridge.state['meeting']['answers'] = [dict(id=7, label='First answer'), dict(id=9, label='Second answer')]
            self.bridge.publish()
        self.page.click('#meeting-refinements summary')
        self.page.wait_for_function("document.querySelector('#meeting-answer').options.length === 2")
        self.page.select_option('#meeting-answer', '7')
        self.page.fill('#meeting-followup', 'Why is the first solution faster?')
        self.page.click('[data-refine="followup"]')
        command = self.meeting_ack('quick_answer')
        self.assertEqual(command['job'], 7)
        self.assertEqual(command['text'], 'Why is the first solution faster?')
        self.page.wait_for_function("document.querySelector('#meeting-action-status').textContent === 'Answer task created.'")
        self.page.screenshot(path=str(WEB.parent.parent / 'work/meeting-ui-listen.png'))
        self.page.click('.listen-toolbar [data-view="settings"]')
        self.page.locator('#meeting-settings').scroll_into_view_if_needed()
        self.page.screenshot(path=str(WEB.parent.parent / 'work/meeting-ui-settings.png'))

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.playwright.stop()

    def setUp(self):
        self.bridge = FakeBridge(getattr(self, 'theme', 'classic'))
        self.page = self.browser.new_page(viewport={'width': 1180, 'height': 760})
        self.errors = []
        self.page.on('pageerror', lambda error: self.errors.append(str(error)))
        self.page.goto(self.bridge.url)
        self.page.click('button.nav[data-view="listen"]')
        self.page.wait_for_function("document.querySelector('#model-badge').textContent.includes('deepseek')")

    def tearDown(self):
        self.page.close()
        self.bridge.close()
        self.assertEqual(self.errors, [])

    def wait_option(self, key, value):
        for _ in range(50):
            if self.bridge.option(key) == value:
                return
            self.page.wait_for_timeout(100)
        self.fail('%s stayed %r, expected %r' % (key, self.bridge.option(key), value))

    def drag(self, selector, dx, dy):
        box = self.page.locator(selector).first.bounding_box()
        x, y = box['x'] + box['width'] / 2, box['y'] + box['height'] / 2
        self.page.mouse.move(x, y)
        self.page.mouse.down()
        self.page.mouse.move(x + dx, y + dy, steps=8)
        self.page.mouse.up()

    def test_reading_scrollbars_drag_and_keep_position_during_updates(self):
        text = '\n\n'.join(f'Record {i}: English transcript / 中文翻译。' for i in range(90))
        with self.bridge.lock:
            self.bridge.state.update(transcript=text, output=text)
            self.bridge.publish()
        self.page.wait_for_function("current.transcript.includes('Record 89')")
        for width in (1180, 760):
            self.page.set_viewport_size({'width': width, 'height': 760})
            for selector in ('#transcript', '#output'):
                with self.subTest(width=width, pane=selector):
                    pane = self.page.locator(selector)
                    metrics = pane.evaluate('''el => {
                        el.scrollTop=0;
                        return {overflow:getComputedStyle(el).overflowY,
                                gutter:el.offsetWidth-el.clientWidth,
                                scrollable:el.scrollHeight>el.clientHeight};
                    }''')
                    self.assertEqual(metrics['overflow'], 'scroll')
                    self.assertGreaterEqual(metrics['gutter'], 10)
                    self.assertTrue(metrics['scrollable'])
                    box = pane.bounding_box()
                    self.page.mouse.move(box['x'] + box['width'] - metrics['gutter'] / 2,
                                         box['y'] + metrics['gutter'] + 8)
                    self.page.mouse.down()
                    self.page.mouse.move(box['x'] + box['width'] - metrics['gutter'] / 2,
                                         box['y'] + min(90, box['height'] - 20), steps=8)
                    self.page.mouse.up()
                    self.assertGreater(pane.evaluate('el => el.scrollTop'), 0)
                    pane.evaluate('el => el.scrollTop=120')
            with self.bridge.lock:
                self.bridge.state.update(transcript=self.bridge.state['transcript'] + '\n\nIncoming transcript',
                                         output=self.bridge.state['output'] + '\n\nIncoming answer')
                self.bridge.publish()
            self.page.wait_for_function("current.output.endsWith('Incoming answer')")
            for selector in ('#transcript', '#output'):
                self.assertAlmostEqual(self.page.locator(selector).evaluate('el => el.scrollTop'), 120, delta=2)
            self.page.screenshot(path=str(WEB.parent.parent / f'work/reading-scrollbars-{getattr(self,"theme","classic")}-{width}.png'))

    def test_toolbar_stays_on_one_row(self):
        for width in (1500, 1180, 900, 760):
            with self.subTest(width=width):
                self.page.set_viewport_size({'width': width, 'height': 760})
                self.page.wait_for_timeout(100)
                fits = self.page.evaluate("""() => {
                    const bar = document.querySelector('.listen-toolbar');
                    const tops = [...bar.querySelectorAll(':scope>.inline>*')]
                        .filter(el => el.getClientRects().length).map(el => Math.round(el.getBoundingClientRect().top / 20));
                    return bar.scrollWidth <= bar.clientWidth + 1 && new Set(tops).size <= 2;
                }""")
                self.assertTrue(fits)

    def test_narrowed_toolbar_never_overlaps_its_buttons(self):
        # Drag the toolbar's own side grip as far in as it goes.
        self.drag('.side-grip[data-panel="0"][data-edge="right"]', -400, 0)
        self.page.wait_for_timeout(100)
        overlaps = self.page.evaluate("""() => {
            const bar = document.querySelector('.listen-toolbar'), b = bar.getBoundingClientRect();
            const kids = [...bar.querySelectorAll(':scope>.inline>*')].filter(el => el.getClientRects().length)
                .map(el => el.getBoundingClientRect()).filter(r => r.width > 0).sort((a, c) => a.left - c.left);
            const bad = kids.some((r, i) => i && r.left < kids[i - 1].right - 0.5);
            return bad || kids[0].left < b.left || kids.at(-1).right > b.right; }""")
        self.assertFalse(overlaps)
        self.assertLess(self.page.evaluate('layout[2]'), 1180)  # it did get narrower

    def test_menus_open_one_at_a_time_and_close(self):
        layout, more = self.page.locator('#layout-menu'), self.page.locator('#more-menu')
        self.page.click('#layout-button')
        self.assertTrue(layout.is_visible())
        self.assertEqual(self.page.get_attribute('#layout-button', 'aria-expanded'), 'true')
        self.page.click('#more')
        self.assertTrue(more.is_visible())
        self.assertFalse(layout.is_visible())
        self.page.keyboard.press('Escape')
        self.assertFalse(more.is_visible())
        self.page.click('#layout-button')
        self.page.mouse.click(600, 500)  # inside the answer panel
        self.assertFalse(layout.is_visible())

    def test_drag_bars_change_heights_and_widths(self):
        if self.page.evaluate('midnightColumns()'):
            before = self.page.locator('.transcript-panel').bounding_box()['width']
            self.drag('.splitter[data-split="transcript"]', 60, 0)
            self.assertGreater(self.page.locator('.transcript-panel').bounding_box()['width'], before + 45)
            self.page.wait_for_function('midnightSplit > 40')
        else:
            before = self.page.locator('.transcript-panel').bounding_box()['height']
            self.drag('.splitter[data-split="transcript"]', 0, 60)
            self.assertAlmostEqual(self.page.locator('.transcript-panel').bounding_box()['height'], before + 60, delta=3)
        width = self.page.locator('.answer-panel').bounding_box()['width']
        if self.page.evaluate('midnightColumns()'):
            self.drag('.side-grip[data-panel="2"][data-edge="left"]', 60, 0)
            self.assertAlmostEqual(self.page.locator('.answer-panel').bounding_box()['width'], width - 60, delta=4)
            self.wait_option('midnight_split', self.page.evaluate('String(Math.round(midnightSplit))'))
        else:
            self.drag('.side-grip[data-panel="2"][data-edge="right"]', -100, 0)
            self.assertAlmostEqual(self.page.locator('.answer-panel').bounding_box()['width'], width - 200, delta=4)
            self.wait_option('listen_layout', self.page.evaluate('layout.join(",")'))

    def test_panel_width_targets_follow_edges_without_vertical_bars(self):
        for width in (1180, 760):
            self.page.set_viewport_size(dict(width=width, height=760))
            self.page.wait_for_timeout(100)
            edges = self.page.evaluate("""() => [...document.querySelectorAll('.side-grip')].map(grip => {
                const panel = panels[Number(grip.dataset.panel)].getBoundingClientRect();
                const target = grip.getBoundingClientRect();
                return {panelLeft: panel.left, panelRight: panel.right,
                    targetLeft: target.left, targetRight: target.right, edge: grip.dataset.edge,
                    decoration: getComputedStyle(grip, '::after').content};
            })""")
            for edge in edges:
                if edge['edge'] == 'left':
                    self.assertAlmostEqual(edge['targetLeft'], edge['panelLeft'], delta=0.5)
                else:
                    self.assertAlmostEqual(edge['targetRight'], edge['panelRight'], delta=0.5)
                self.assertIn(edge['decoration'], ('none', 'normal'))
        before = self.page.locator('.transcript-panel').bounding_box()['width']
        self.drag('.side-grip[data-panel="1"][data-edge="right"]', -40, 0)
        self.assertAlmostEqual(self.page.locator('.transcript-panel').bounding_box()['width'], before - 80, delta=3)
        self.wait_option('listen_layout', self.page.evaluate('layout.join(",")'))
        edge = self.page.locator('.side-grip[data-panel="1"][data-edge="right"]')
        edge.focus()
        self.page.keyboard.press('ArrowRight')
        self.assertAlmostEqual(self.page.locator('.transcript-panel').bounding_box()['width'], before - 70, delta=3)
        edge.dblclick()
        self.assertAlmostEqual(self.page.locator('.transcript-panel').bounding_box()['width'], before, delta=3)

    def test_window_corner_is_unpainted_but_still_resizes(self):
        self.page.evaluate("""() => {
            window.__sizes = [];
            window.pywebview = {api: {resize: (w, h) => {
                window.__sizes.push([w, h]); return Promise.resolve(true);
            }}};
        }""")
        self.page.locator('#resize-grip').hover()
        corner = self.page.evaluate("""() => {
            const el = document.querySelector('#resize-grip'), r = el.getBoundingClientRect(), s = getComputedStyle(el);
            return {background: s.backgroundColor, image: s.backgroundImage,
                right: r.right, bottom: r.bottom, width: windowFrame().right, height: windowFrame().bottom,
                initial: [outerWidth, outerHeight]};
        }""")
        self.assertLessEqual(float(corner['background'].rsplit(',',1)[1].rstrip(' )')), 0.01)
        self.assertEqual(corner['image'], 'none')
        self.assertEqual(corner['right'], corner['width'])
        self.assertEqual(corner['bottom'], corner['height'])
        self.drag('#resize-grip', -60, -40)
        self.page.wait_for_function('window.__sizes.length > 0')
        self.assertEqual(self.page.evaluate('window.__sizes.at(-1)'),
                         [corner['initial'][0] - 60, corner['initial'][1] - 40])

    def test_font_buttons(self):
        self.page.click('[data-font="answer_font_size"][data-step="1"]')
        self.wait_option('answer_font_size', '22')
        self.assertEqual(self.page.eval_on_selector('#output', 'el => getComputedStyle(el).fontSize'), '22px')

    def test_save_apply_and_delete_preset(self):
        self.page.click('[data-font="transcript_font_size"][data-step="1"]')
        self.wait_option('transcript_font_size', '22')
        self.page.click('#layout-button')
        self.page.fill('#preset-name', 'Meeting')
        self.page.click('#preset-save')
        self.page.wait_for_selector('.preset-apply[data-preset="Meeting"]')
        saved = json.loads(self.bridge.option('listen_presets'))
        self.assertEqual(saved[0]['name'], 'Meeting')
        self.assertEqual(saved[0]['values']['transcript_font_size'], '22')
        # A built-in preset changes the look; the saved one brings it back.
        self.page.click('.preset-apply[data-preset="Compact"]')
        self.wait_option('transcript_font_size', '16')
        self.assertEqual(self.bridge.option('listen_layout'), '56,140,0,0,0')
        self.page.click('#layout-button')
        self.page.click('.preset-apply[data-preset="Meeting"]')
        self.wait_option('transcript_font_size', '22')
        self.assertEqual(self.bridge.option('listen_layout'), '')
        self.page.click('#layout-button')
        self.page.click('.preset-row:has([data-preset="Meeting"]) .preset-delete')
        self.wait_option('listen_presets', '')
        self.assertEqual(self.page.locator('.preset-apply[data-preset="Meeting"]').count(), 0)

    def test_builtin_names_are_reserved(self):
        self.page.click('#layout-button')
        self.page.fill('#preset-name', 'compact')
        self.page.click('#preset-save')
        self.page.wait_for_function("document.querySelector('#status').textContent.includes('built-in')")
        self.page.wait_for_timeout(1000)  # about five polls: the message must not be overwritten
        self.assertIn('built-in', self.page.text_content('#status'))
        self.assertEqual(self.bridge.option('listen_presets'), '')

    def test_reset_layout_restores_every_default(self):
        from settings_state import DEFAULT_OPTIONS, LAYOUT_KEYS
        self.page.click('#layout-button')
        self.page.click('[data-toggle="listen_text_bold"]')
        self.wait_option('listen_text_bold', '1')
        self.drag('.splitter[data-split="transcript"]', 0, 40)
        self.page.wait_for_timeout(300)
        self.page.click('#layout-button')
        self.page.click('#layout-reset')
        for key in LAYOUT_KEYS:
            self.wait_option(key, DEFAULT_OPTIONS[key])
        self.assertEqual(self.page.evaluate('document.body.dataset.textBold'), '0')
        self.assertEqual(self.page.evaluate('layout.join(",")'), '0,0,0,0,0')

    def set_text(self, key, value):
        with self.bridge.lock:
            self.bridge.state[key] = value
        self.bridge.publish()
        self.page.wait_for_function('([id, value]) => document.getElementById(id)._mdSource === value',
                                    arg=[key, value], timeout=3000)

    def test_live_text_streams_appends_and_rewrites(self):
        base = 'Line one. ' * 2000
        self.set_text('transcript', base)
        self.set_text('transcript', base + 'draft wor')
        self.set_text('transcript', base + 'draft words, final.')  # live draft rewrites its tail
        self.set_text('transcript', 'Cleared.')  # replaced outright
        self.set_text('output', 'Answer part one.')
        self.set_text('output', 'Answer part one. Part two.')
        self.assertEqual(self.page.evaluate("document.getElementById('transcript').childNodes.length"), 1)

    def test_answer_renders_markdown(self):
        self.set_text('output', '## Plan\n\nUse **bold**, *italic*, `code` and [docs](https://example.com).\n\n'
                                '- one\n- two\n  - nested\n\n1. first\n2. second\n\n'
                                '```python\nprint("hi")\n```\n\n> quoted\n\n| A | B |\n|---|--:|\n| 1 | 2 |\n\n---\nsnake_case_name stays')
        found = self.page.evaluate("""() => { const o = document.getElementById('output'), q = s => o.querySelector(s);
            return {h: q('.md-h2')?.textContent, b: q('strong')?.textContent, i: q('em')?.textContent, c: q('p code')?.textContent,
                    link: q('.md-link')?.dataset.tip, nested: q('ul li ul li')?.textContent, ol: o.querySelectorAll('ol li').length,
                    pre: q('pre.md-code code')?.textContent, lang: q('pre.md-code code')?.dataset.lang, quote: q('blockquote p')?.textContent,
                    th: q('th')?.textContent, right: q('td:last-child')?.style.textAlign, hr: !!q('hr'),
                    snake: [...o.querySelectorAll('p')].at(-1).textContent, anchors: o.querySelectorAll('a').length}; }""")
        self.assertEqual(found, {'h': 'Plan', 'b': 'bold', 'i': 'italic', 'c': 'code', 'link': 'https://example.com',
                                 'nested': 'nested', 'ol': 2, 'pre': 'print("hi")', 'lang': 'python', 'quote': 'quoted',
                                 'th': 'A', 'right': 'right', 'hr': True, 'snake': 'snake_case_name stays', 'anchors': 0})

    def test_markdown_never_injects_markup(self):
        self.set_text('output', '<img src=x onerror="window.__pwned=1"> **<b>x</b>** `<script>`')
        self.assertIsNone(self.page.evaluate("window.__pwned ?? null"))
        self.assertEqual(self.page.evaluate("document.querySelectorAll('#output img, #output script, #output b').length"), 0)
        self.assertIn('<img src=x', self.page.text_content('#output'))

    def test_streaming_answer_redraws_only_its_last_block(self):
        self.set_text('output', 'First paragraph.\n\n```js\nlet a')
        first = self.page.evaluate_handle("document.querySelector('#output p')")
        self.set_text('output', 'First paragraph.\n\n```js\nlet a = 1;\n```')
        self.assertTrue(self.page.evaluate("p => p.isConnected && document.querySelector('#output p') === p", first))
        self.assertEqual(self.page.text_content('#output pre code'), 'let a = 1;')

    def test_copy_keeps_the_markdown_source(self):
        self.page.context.grant_permissions(['clipboard-read', 'clipboard-write'])
        self.set_text('output', '**bold** answer')
        self.page.click('[data-copy="output"]')
        self.assertEqual(self.page.evaluate('navigator.clipboard.readText()'), '**bold** answer')

    def test_idle_page_is_quiet_and_updates_fast(self):
        self.page.wait_for_timeout(300)
        before = self.bridge.reads
        self.page.wait_for_timeout(2000)
        self.assertLessEqual(self.bridge.reads - before, 4)  # was about 10 a second
        with self.bridge.lock:
            self.bridge.state['output'] = 'Fresh answer.'
        self.bridge.publish()
        self.page.wait_for_function("document.getElementById('output')._mdSource === 'Fresh answer.'", timeout=800)  # a waiting read wakes at once, not after its 1 s wait

    def test_window_shape_reports_every_surface(self):
        # Fake the native host so the page reports the click targets it wants.
        self.page.evaluate("""() => { window.pywebview = {api: {shape: layout => {
            window.__shape = layout; return Promise.resolve(true); }}};
            lastShape = ''; scheduleShape(); }""")
        self.page.wait_for_function('window.__shape && window.__shape.rects.length > 0')
        rects = [r[:4] for r in self.page.evaluate('window.__shape.rects')]
        # Drag bars report their whole bar, so a thin handle is still easy to grab.
        selectors = ['.listen-toolbar', '#listen>.splitter', '.side-grip', '.window-resize-edge']
        if self.page.evaluate('darkWorkspace()'):
            selectors += ['.capsule', '.workspace-rail']
        for selector in selectors:
            boxes = self.page.evaluate("s => [...document.querySelectorAll(s)].filter(e => e.getClientRects().length)"
                                       ".map(e => e.getBoundingClientRect()).map(r => [r.x, r.y, r.width, r.height])", selector)
            self.assertTrue(boxes, selector)
            for box in boxes:
                self.assertIn(box, rects, selector)
        thickness = self.page.evaluate("parseFloat(getComputedStyle(document.querySelector('#listen>.splitter'), '::after').height)")
        self.assertLessEqual(thickness, 4)  # the visible handle stays thin

    def test_style_switch_keeps_controls_drafts_and_running_jobs(self):
        controls = '#provider,#model-picker,#key,#effort,#thinking_policy,#source,#device,#microphone,#asr_engine,#caption,#answer,#auto_answers,#auto_pace,#speaker_labels,#echo_suppression,#auto_recap,#question_mode,#warm_context,#speculate,#history,#deadline,#max_output,#lm_base,#instructions,#profile,#documents,[data-action],[data-window],[data-meeting],[data-refine]'
        self.page.evaluate('selector => window.__originalControls = [...document.querySelectorAll(selector)]', controls)
        self.page.click('#context-toggle')
        self.page.fill('#context-instructions', 'Keep this unsaved draft across style changes')
        self.page.click('#context-close')
        with self.bridge.lock:
            self.bridge.state['jobs'] = [dict(id=19, done=False)]
            self.bridge.publish()
        for theme in ('cosmic', 'workbench', 'classic'):
            self.page.click('#layout-button')
            self.page.select_option('#live-ui-theme', theme)
            self.wait_option('ui_theme', theme)
            self.page.wait_for_function('theme => document.body.dataset.theme === theme', arg='workbench' if theme == 'cosmic' else theme)
            self.assertTrue(self.page.evaluate('window.__originalControls.every(el => el.isConnected)'))
            self.assertEqual(self.page.input_value('#context-instructions'), 'Keep this unsaved draft across style changes')
            self.assertEqual(self.bridge.state['instructions'], '')
            self.assertEqual(self.bridge.state['jobs'], [dict(id=19, done=False)])
            self.page.keyboard.press('Escape')
        self.page.click('#active-jobs button')
        # The click dispatches an asynchronous HTTP command; wait for receipt.
        for _ in range(40):
            if any(c.get('action') == 'cancel_job' and c.get('id') == 19 for c in self.bridge.commands):
                break
            self.page.wait_for_timeout(50)
        self.assertTrue(any(c.get('action') == 'cancel_job' and c.get('id') == 19 for c in self.bridge.commands))
        self.page.click('.listen-toolbar [data-view="settings"]')
        self.assertEqual(self.page.input_value('#ui_theme'), 'classic')
        self.page.select_option('#ui_theme', 'classic')
        self.wait_option('ui_theme', 'classic')

    def test_builtin_scenarios_use_confirmed_editable_drafts(self):
        self.page.click('#context-toggle')
        self.page.fill('#context-instructions', 'Keep my custom requirements')
        before = 'Keep my custom requirements'
        for preset in self.bridge.state['prompt_presets']:
            self.page.select_option('#builtin-prompt', preset['id'])
            self.page.click('#builtin-load')
            self.assertEqual(self.page.input_value('#context-instructions'), before)
            self.page.click('#builtin-load')
            self.assertEqual(self.page.input_value('#context-instructions'), preset['text'])
            self.assertEqual(self.page.input_value('#instructions'), preset['text'])
            self.assertEqual(self.bridge.state['instructions'], '')
            before = preset['text']
        self.page.click('#context-apply')
        self.page.wait_for_function('current.instructions.includes("careful editor")')
        self.assertIn('careful editor', self.bridge.state['instructions'])

    def test_lm_studio_url_only_shows_for_local_provider_and_keeps_its_value(self):
        endpoint = 'http://127.0.0.1:4321/v1'
        with self.bridge.lock:
            self.bridge.state['providers'] = ['DeepSeek', 'LM Studio', 'Kiro（本机登录）']
            self.bridge.state['options']['lm_base'] = endpoint
            self.bridge.publish()
        self.page.click('.listen-toolbar [data-view="settings"]')
        self.page.locator('#models .settings-options summary').click()
        for provider in ('DeepSeek', 'LM Studio', 'Kiro（本机登录）', 'LM Studio'):
            with self.bridge.lock:
                self.bridge.state.update(provider=provider, cli=provider.startswith('Kiro'))
                self.bridge.publish()
            self.page.wait_for_function('provider => current.provider === provider', arg=provider)
            self.assertEqual(self.page.locator('#lm_base').is_visible(), provider == 'LM Studio')
            self.assertEqual(self.page.input_value('#lm_base'), endpoint)

    def test_settings_single_column_keeps_advanced_controls_accessible(self):
        self.page.click('.listen-toolbar [data-view="settings"]')
        model = self.page.locator('#models').bounding_box()
        audio = self.page.locator('#audio').bounding_box()
        self.assertGreater(audio['y'], model['y'] + model['height'])
        self.assertAlmostEqual(model['x'], audio['x'], delta=1)
        self.page.locator('#models .settings-options summary').click()
        for selector in ('#model', '#effort', '#thinking_policy'):
            self.assertTrue(self.page.locator(selector).is_visible(), selector)
        self.assertFalse(self.page.locator('#lm_base').is_visible())
        self.page.locator('[data-section="preferences"]').click()
        self.page.locator('#preferences .settings-options').last.locator('summary').click()
        for selector in ('#answer_mode', '#deadline', '#max_output', '#warm_context', '#speculate', '#incremental_context'):
            self.assertTrue(self.page.locator(selector).is_visible(), selector)
        for width in (1180, 760):
            self.page.set_viewport_size(dict(width=width, height=760))
            self.assertTrue(self.page.evaluate('document.documentElement.scrollWidth <= innerWidth'))

    def test_shortcuts_open_in_settings_and_validate_save_and_reset(self):
        self.page.click('#more')
        self.page.click('#more-menu [data-action="hotkeys"]')
        self.assertTrue(self.page.locator('#settings').is_visible())
        self.assertTrue(self.page.locator('#shortcuts').is_visible())
        self.assertEqual(len(self.page.context.pages),1)
        self.assertFalse(any(c.get('action')=='hotkeys' for c in self.bridge.commands))
        self.page.fill('#hotkey-hotkey','ctrl+shift+f8')
        self.page.click('#hotkeys-save')
        self.page.wait_for_function("current.hotkeys.hotkey === 'Ctrl+Shift+F8'")
        self.page.wait_for_function("document.querySelector('#hotkey-hotkey').value === 'Ctrl+Shift+F8'")
        self.page.fill('#hotkey-topmost','Ctrl+Shift+F8')
        self.page.click('#hotkeys-save')
        self.page.wait_for_function('current.hotkey_result && current.hotkey_result.ok === false')
        self.assertEqual(self.bridge.state['hotkeys']['topmost'],'Ctrl+Alt+T')
        self.assertEqual(self.page.input_value('#hotkey-topmost'),'Ctrl+Shift+F8')
        self.page.click('#hotkeys-default')
        self.assertEqual(self.page.input_value('#hotkey-hotkey'),'Ctrl+Alt+Space')
        self.assertEqual(self.bridge.state['hotkeys']['hotkey'],'Ctrl+Shift+F8')
        self.page.click('#hotkeys-save')
        self.page.wait_for_function("current.hotkeys.hotkey === 'Ctrl+Alt+Space'")

    def test_transparency_reaches_controls_and_midnight_chrome_without_fading_text(self):
        self.page.focus('#listen_transparency')
        samples=[]
        for amount in (1,99):
            samples.append(self.page.evaluate("""amount => {
                const slider=document.querySelector('#listen_transparency');slider.value=amount;
                slider.dispatchEvent(new Event('input',{bubbles:true}));
                return ['#pause','#pin','#live-caption','.capsule','.workspace-rail'].map(selector=>{
                    const el=document.querySelector(selector);if(!el.getClientRects().length)return null;
                    const s=getComputedStyle(el),color=s.backgroundColor;
                    return {selector,alpha:color.startsWith('rgba')?Number(color.slice(color.lastIndexOf(',')+1,-1)):1,
                        opacity:s.opacity,text:s.color};
                }).filter(Boolean);
            }""",amount))
        for before,after in zip(*samples):
            with self.subTest(selector=before['selector']):
                self.assertGreater(before['alpha'],after['alpha']+0.01)
                self.assertEqual(after['opacity'],'1')
                self.assertEqual(before['text'],after['text'])

    def test_chinese_labels(self):
        with self.bridge.lock:
            self.bridge.state['language'] = 'zh'
        self.bridge.publish()
        self.page.wait_for_function("document.querySelector('#layout-button').textContent==='布局'")
        self.assertEqual(self.page.text_content('#meeting-refinements summary'), '继续处理回答')
        self.assertEqual(self.page.text_content('#meeting-settings h2'), '会议辅助')
        self.page.click('#layout-button')
        self.assertEqual(self.page.text_content('#layout-reset'), '恢复默认布局')
        self.assertEqual(self.page.get_attribute('#preset-name', 'placeholder'), '预设名称')


if __name__ == '__main__':
    unittest.main()
