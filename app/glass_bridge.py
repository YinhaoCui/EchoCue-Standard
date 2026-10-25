"""Loopback-only web presentation adapter. Tk operations stay on the UI thread."""
import base64
import json
import mimetypes
from pathlib import Path
import queue
import re
import secrets
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from state_feed import StateFeed
from prompt_templates import builtin_prompts
from hotkey_settings import DEFAULTS as HOTKEY_DEFAULTS

ASSETS = Path(__file__).with_name('web')
FONT_RANGE = (12, 40)
COLOR = re.compile(r'#[0-9a-f]{6}')
STATE_WAIT = 1.0  # longest a /state read waits for a change, in seconds


def state_query(path):
    """Read rev, boot, text versions and wait from a /state URL. Bad values mean 'send everything'."""
    from urllib.parse import parse_qs, urlsplit
    query = {k: v[-1] for k, v in parse_qs(urlsplit(path).query).items()}

    def number(name, default):
        try:
            return int(query[name])
        except (KeyError, ValueError):
            return default
    try:
        wait = min(STATE_WAIT, max(0.0, float(query.get('wait', 0))))
    except ValueError:
        wait = 0.0
    if wait != wait:  # NaN
        wait = 0.0
    versions = {key: number(name, None) for key, name in (('transcript', 'tv'), ('output', 'ov'))}
    return dict(rev=number('rev', -1), boot=query.get('boot', '')[:16], versions=versions, wait=wait)


def listen_layout(value):
    """Validate 'toolbar,transcript,toolbarW,transcriptW,answerW' pixel sizes.

    0 keeps a default; empty resets all. Older 2- and 3-part values (one shared
    width) are still accepted and expanded.
    """
    if value in ('', None):
        return ''
    parts = str(value).split(',')
    if len(parts) not in (2, 3, 5):
        raise ValueError('Invalid panel layout')
    try:
        sizes = [int(float(part)) for part in parts]
    except (ValueError, OverflowError):
        raise ValueError('Invalid panel layout') from None
    if len(sizes) == 2:
        sizes += [0, 0, 0]
    elif len(sizes) == 3:
        sizes += [sizes[2]] * 2
    toolbar, transcript, *widths = sizes
    if not ((toolbar == 0 or 56 <= toolbar <= 200) and (transcript == 0 or 100 <= transcript <= 4000)
            and all(width == 0 or 240 <= width <= 10000 for width in widths)):
        raise ValueError('Invalid panel layout')
    return '' if not any(sizes) else ','.join(map(str, sizes))


def layout_value(key, value):
    """Validate one Listen-page look setting and return its stored text."""
    if key == 'listen_transparency':
        value = int(value)
        if not 1 <= value <= 99:
            raise ValueError('Transparency must be between 1 and 99')
        return str(value)
    if key in ('transcript_font_size', 'answer_font_size'):
        value = int(value)
        if not FONT_RANGE[0] <= value <= FONT_RANGE[1]:
            raise ValueError('Font size must be between %d and %d' % FONT_RANGE)
        return str(value)
    if key == 'listen_layout':
        return listen_layout(value)
    if key in ('listen_text_color', 'listen_panel_color'):
        value = str(value).lower()
        if not COLOR.fullmatch(value):
            raise ValueError('Colors must be #rrggbb')
        return value
    if key in ('listen_text_bold', 'listen_text_outline'):
        if value not in ('0', '1'):
            raise ValueError('Text options must be on or off')
        return value
    raise ValueError('Unknown layout setting')


MAX_PRESETS, PRESET_NAME = 5, 40


def listen_presets(value):
    """Validate saved layout presets: a JSON list of {name, values}."""
    from settings_state import LAYOUT_KEYS
    if value in ('', None, []):
        return ''
    items = json.loads(value) if isinstance(value, str) else value
    if not isinstance(items, list) or len(items) > MAX_PRESETS:
        raise ValueError('Up to %d layout presets can be saved' % MAX_PRESETS)
    clean, names = [], set()
    for item in items:
        if not isinstance(item, dict) or not isinstance(item.get('values'), dict):
            raise ValueError('Invalid layout preset')
        name = str(item.get('name', '')).strip()
        if not 0 < len(name) <= PRESET_NAME or name.casefold() in names:
            raise ValueError('Preset names must be 1-%d characters and unique' % PRESET_NAME)
        names.add(name.casefold())
        values = item['values']
        if set(values) - set(LAYOUT_KEYS):
            raise ValueError('Invalid layout preset')
        clean.append(dict(name=name, values={k: layout_value(k, values[k]) for k in LAYOUT_KEYS if k in values}))
    return json.dumps(clean, ensure_ascii=False, separators=(',', ':')) if clean else ''


def cli_provider(name):
    """Local-login CLI providers store their model in a per-provider option."""
    import providers
    return providers.is_cli(name)


class GlassBridge:
    def __init__(self, app):
        self.app = app
        self.token = secrets.token_urlsafe(32)
        self.commands = queue.Queue(maxsize=100)
        self.feed = StateFeed()
        self.image_data = {}
        self.window_state = dict(topmost=False, background=app.advanced['background_mode'].get())
        try:
            self.microphones = [app.mic.audio.get_device_info_by_index(i)
                                for i in range(app.mic.audio.get_device_count())]
            self.microphones = [d for d in self.microphones
                                if d.get('maxInputChannels', 0) > 0 and not d.get('isLoopbackDevice')]
        except Exception:
            self.microphones = []
        bridge = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_):
                pass

            def reply(self, status, body, mime='application/json'):
                self.send_response(status)
                self.send_header('Content-Type', mime)
                self.send_header('Content-Length', str(len(body)))
                self.send_header('Cache-Control', 'no-store')
                self.send_header('X-Content-Type-Options', 'nosniff')
                self.send_header('Content-Security-Policy',
                                 "default-src 'self'; script-src 'self'; style-src 'self'; "
                                 "img-src 'self' data: blob:; connect-src 'self'; frame-ancestors 'none'")
                self.end_headers()
                try:
                    self.wfile.write(body)
                except ConnectionError:  # page closed mid-reply, e.g. during a waiting /state read
                    pass

            def authorized(self):
                host = f'127.0.0.1:{bridge.server.server_port}'
                return (self.headers.get('Host') == host
                        and self.headers.get('Origin', 'http://' + host) == 'http://' + host
                        and secrets.compare_digest(self.headers.get('X-Listener-Token', ''), bridge.token))

            def do_GET(self):
                if self.path.startswith('/image/'):
                    if not self.authorized():
                        self.reply(403, b'{}')
                        return
                    data = bridge.image_data.get(self.path[len('/image/'):])
                    if not data:
                        self.reply(404, b'{}')
                        return
                    try:
                        self.reply(200, base64.b64decode(data, validate=True), 'image/png')
                    except ValueError:
                        self.reply(404, b'{}')
                    return
                if self.path.split('?', 1)[0] == '/state':
                    if not self.authorized():
                        self.reply(403, b'{}')
                    else:
                        self.reply(200, bridge.read_state(self.path))
                    return
                files = {'/': 'index.html', '/app.js': 'app.js', '/context_editor.js': 'context_editor.js', '/meeting.js': 'meeting.js', '/markdown.js': 'markdown.js', '/popups.js': 'popups.js', '/style.css': 'style.css'}
                files.update({'/icons/' + p.name: 'icons/' + p.name
                              for p in (ASSETS / 'icons').glob('*.svg')})
                name = files.get(self.path)
                if not name:
                    self.reply(404, b'{}')
                    return
                self.reply(200, (ASSETS / name).read_bytes(),
                           {'html': 'text/html', 'js': 'text/javascript', 'css': 'text/css',
                            'svg': 'image/svg+xml'}[name.rsplit('.', 1)[1]] + '; charset=utf-8')

            def do_POST(self):
                if self.path != '/command' or not self.authorized():
                    self.reply(403, b'{}')
                    return
                try:
                    size = int(self.headers.get('Content-Length', '0'))
                    if not 0 < size <= 4_000_000:
                        raise ValueError('Invalid request size')
                    data = json.loads(self.rfile.read(size))
                    if not isinstance(data, dict) or not isinstance(data.get('action'), str):
                        raise ValueError('Invalid command')
                    bridge.commands.put_nowait(data)
                    self.reply(202, b'{"queued":true}')
                except (ValueError, queue.Full):
                    self.reply(400, b'{"error":"Invalid or busy request"}')

        self.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        self.server.daemon_threads = True
        self.url = f'http://127.0.0.1:{self.server.server_port}'
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def snapshot(self):
        a = self.app
        self.image_data = {i.get('id', str(n)): i.get('data', '') for n, i in enumerate(a.context_images)}
        provider = a.provider.get()
        cli = cli_provider(provider)
        model = a.advanced[a.cli_key()].get() if cli else a.model.get()
        import providers
        from streaming_asr import ASR_MODELS
        from usage_ui import usage_lines
        from reasoning_support import choices
        with a.token_ledger.lock:
            rows = list(a.token_ledger.rows)
        return dict(
            meeting=a.meeting_state() if hasattr(a, 'scenes') else {},
            speaker_note=getattr(getattr(a, 'live', None), 'speaker_note', ''),
            language=a.locale.language, providers=providers.NAMES,
            provider=provider, model=model, models=a.cli_models() if cli else list(a.model_choices),
            model_status=a.locale.t(a.cli_model_note.get() if cli else a.model_catalog_note() + ' ' + a.key_status.get()),
            efforts=choices(provider, model, a.codex_capabilities), effort=a.reasoning_selection.get(), cli=cli,
            has_key=bool(a.key.get()), options={k: v.get() for k, v in a.advanced.items()},
            engines=list(ASR_MODELS), caption=a.caption_language.get(), answer=a.answer_language.get(),
            history=a.use_history.get(), profile=a.profile, documents=a.documents, summary=a.context_summary,
            context_version=a.context_version, history_count=len(a.history),
            context_edit=getattr(self, 'context_edit', None),
            prompt_templates=a.prompt_templates, prompt_templates_version=a.prompt_templates_version,
            prompt_templates_error=a.prompt_templates_error, prompt_result=getattr(self, 'prompt_result', None),
            prompt_presets=builtin_prompts(),
            hotkeys=dict(a.hotkeys), hotkey_defaults=dict(HOTKEY_DEFAULTS),
            hotkey_status=a.locale.t(a.hotkey_registration_note.get()),
            hotkey_result=getattr(self, 'hotkey_result', None),
            navigation_request=getattr(self, 'navigation_request', None),
            instructions=a.instructions.get(), answer_mode=a.answer_mode.get(),
            devices=[d['name'] for d in a.devices], device=a.device_index,
            microphones=[dict(value=str(d['index']), text=d['name']) for d in self.microphones],
            microphone=str(a.mic_index) if a.mic_index is not None else '',
            images=[dict(id=i.get('id', str(n)), title=i.get('title', 'Screenshot')) for n, i in enumerate(a.context_images)],
            listening=bool(a.capture.active() or a.mic.active()), preparing=getattr(a, 'preparing_listen', False),
            status=a.locale.t(a.status.get()), transcript=a.transcript_view,
            output=a.output_text, usage=a.locale.t(usage_lines(rows, a.session_id)),
            jobs=[dict(id=k, done=j.get('done', False)) for k, j in a.jobs.items()],
            native=self.window_state, closing=getattr(a, 'closing', False))

    def settings(self, data):
        a = self.app
        from settings_state import PRESENTATION_DEFAULTS, presentation_value
        presentation = {key: presentation_value(key, data[key]) for key in PRESENTATION_DEFAULTS if key in data}
        from meeting_assistance import OPTIONS
        for key in OPTIONS.keys() & data.keys():
            if data[key] not in OPTIONS[key]:
                raise ValueError('Invalid meeting setting: ' + key)
            if key in ('speaker_labels', 'echo_suppression') and (a.capture.active() or a.mic.active()):
                if data[key] != a.advanced[key].get():
                    raise ValueError('Pause transcription before changing audio processing. / 请先暂停转录再修改音频处理。')
        audio_changed = any(key in data and data[key] != a.advanced[key].get()
                            for key in ('speaker_labels', 'echo_suppression'))
        for key in OPTIONS.keys() & data.keys():
            a.advanced[key].set(data[key])
        if OPTIONS.keys() & data.keys():
            a.change_question_mode()
            a.auto_answers.pending = None
        if audio_changed:
            a.configure_meeting_audio()
        from settings_state import LAYOUT_KEYS
        # Check every look value first, so a preset applies whole or not at all.
        look = {key: layout_value(key, data[key]) for key in LAYOUT_KEYS if key in data}
        if 'listen_presets' in data:
            look['listen_presets'] = listen_presets(data['listen_presets'])
        for key, value in look.items():
            a.advanced[key].set(value)
        for key, value in presentation.items():
            a.advanced[key].set(value)
        if 'background_mode' in data:
            if data['background_mode'] not in ('translucent', 'frosted', 'opaque'):
                raise ValueError('Unknown background mode')
            a.advanced['background_mode'].set(data['background_mode'])
            self.window_state['background'] = data['background_mode']
        if 'microphone' in data:
            if a.capture.active() or a.mic.active():
                raise ValueError('Pause transcription before changing the microphone.')
            value = data['microphone']
            if value and value not in [str(d['index']) for d in self.microphones]:
                raise ValueError('Unknown microphone')
            a.mic_index = int(value) if value else None
        if 'provider' in data:
            import providers
            if data['provider'] not in providers.NAMES:
                raise ValueError('Unknown provider')
            if a.provider.get() != data['provider']:
                a.provider.set(data['provider'])
                a.update_provider()
        if 'model' in data:
            if cli_provider(a.provider.get()):
                a.advanced[a.cli_key()].set(data['model'])
            else:
                a.model.set(data['model'])
        if data.get('key'):
            a.key.set(data['key'])
        allowed = {'source', 'asr_engine', 'asr_pause', 'question_mode', 'thinking_policy', 'warm_context', 'speculate', 'lm_base',
                   'incremental_context', 'deadline', 'max_output'}
        for key in allowed & data.keys():
            if key in ('source', 'asr_engine') and (a.capture.active() or a.mic.active()):
                if data[key] != a.advanced[key].get():
                    raise ValueError('Pause transcription before changing the audio source or engine.')
            a.advanced[key].set(data[key])
            if key == 'asr_engine':
                a.change_asr()
        if 'device' in data and int(data['device']) != a.device_index:
            if a.capture.active() or a.mic.active():
                raise ValueError('Pause transcription before changing the device.')
            index = int(data['device'])
            if not 0 <= index < len(a.devices):
                raise ValueError('Invalid audio device')
            a.device_index = index
        if 'effort' in data:
            from reasoning_support import choices
            provider, model = a.reasoning_identity()
            if data['effort'] not in choices(provider, model, a.codex_capabilities):
                raise ValueError('Unsupported reasoning effort')
            a.reasoning_selection.set(data['effort'])
            a.save_reasoning()
        for key in ('caption', 'answer'):
            if key in data:
                allowed = {'English', '中文', '中英双语'}
                if key == 'caption':
                    allowed.add('原文')
                if data[key] not in allowed:
                    raise ValueError('Unsupported content language')
                var = a.caption_language if key == 'caption' else a.answer_language
                var.set(data[key])
                a.change_content_language(key)
        if 'history' in data:
            enabled = bool(data['history'])
            if enabled != a.use_history.get():
                a.history_epoch += 1
                a.cancel_context_preparation()
                a.change_question_mode()
                a.use_history.set(enabled)
        if 'answer_mode' in data:
            a.answer_mode.set(data['answer_mode'])
        if 'language' in data:
            a.change_ui_language(data['language'])
        context_changed = False
        for key in ('profile', 'documents'):
            if key in data and data[key] != getattr(a, key):
                setattr(a, key, data[key])
                context_changed = True
        if 'instructions' in data:
            context_changed |= data['instructions'] != a.instructions.get()
            a.instructions.set(data['instructions'])
        if context_changed:
            a.context_changed()
        a.save_preferences()

    def command(self, data):
        a = self.app
        action = data['action']
        if action == 'visual_warning':
            a.status.set('Desktop blur is unavailable on this Windows configuration; transparency remains enabled.')
        elif action == 'settings':
            self.settings(data.get('values', {}))
        elif action == 'hotkeys':
            self.navigation_request=dict(id=secrets.token_hex(8), section='shortcuts')
        elif action == 'save_hotkeys':
            try:
                a.apply_hotkeys(data.get('values'))
                self.hotkey_result=dict(id=data.get('id'), ok=True)
            except (ValueError, TypeError, AttributeError) as exc:
                self.hotkey_result=dict(id=data.get('id'), ok=False, error=a.locale.t(str(exc)))
        elif action == 'apply_context':
            # Return a correlated outcome in the state feed; HTTP 202 only queues work.
            try:
                if data.get('version') != a.context_version:
                    raise ValueError('Context changed. Reload current context before applying your draft.')
                values = data.get('values', {})
                if not isinstance(values, dict) or any(k not in ('profile', 'documents', 'instructions') or not isinstance(v, str) for k, v in values.items()):
                    raise ValueError('Invalid context fields')
                self.settings(values)
                self.context_edit = dict(id=data.get('id'), ok=True)
                a.status.set('上下文已应用；后续回答使用最新资料。')
            except (ValueError, TypeError) as exc:
                self.context_edit = dict(id=data.get('id'), ok=False, error=str(exc))
        elif action == 'clear_history':
            a.clear_history()
        elif action in ('save_prompt_template', 'delete_prompt_template'):
            from account_support import save_settings
            from audio_answer import ROOT
            from prompt_templates import updated_templates
            try:
                if a.prompt_templates_error:
                    raise ValueError(a.prompt_templates_error)
                if data.get('version') != a.prompt_templates_version:
                    raise ValueError('Templates changed. Try again with the current library.')
                templates = updated_templates(a.prompt_templates, data.get('name'), data.get('text'),
                    delete=action == 'delete_prompt_template', overwrite=data.get('overwrite') is True)
                from app_paths import data_path
                save_settings(data_path(ROOT, 'prompt_templates.dpapi'), templates)
                a.prompt_templates = templates
                a.prompt_templates_version += 1
                self.prompt_result = dict(id=data.get('id'), ok=True)
            except (ValueError, TypeError, OSError) as exc:
                self.prompt_result = dict(id=data.get('id'), ok=False, error=str(exc))
        elif action == 'prepare':
            a.prepare_listening()
        elif action == 'listen':
            a.toggle_listen()
        elif action == 'answer':
            a.ask()
        elif action in ('quick_answer', 'save_scene', 'load_scene', 'delete_scene', 'finish_recap'):
            a.meeting_command(data)
        elif action == 'cancel':
            a.cancel_answer()
        elif action == 'cancel_job':
            a.cancel_job(int(data['id']))
        elif action == 'check_apis':
            a.check_gemini(all_keys=True)
        elif action in ('edit_transcript', 'edit_terms', 'export_session', 'clear_context'):
            getattr(a, action)()
        elif action == 'capture':
            a.capture_screenshot()
        elif action == 'analyze':
            a.start_analysis()
        elif action == 'refresh':
            (a.refresh_cli_models if cli_provider(a.provider.get()) else a.refresh_models)()
        elif action == 'import':
            from tkinter import filedialog
            from session_support import read_document
            for path in filedialog.askopenfilenames(parent=a.root, title='Add reference files'):
                a.documents += '\n\n--- ' + Path(path).name + ' ---\n' + read_document(path)
                a.context_changed()
        elif action == 'save_context':
            from account_support import save_settings
            from audio_answer import ROOT
            from app_paths import data_path
            save_settings(data_path(ROOT, 'context.dpapi'), dict(profile=a.profile, documents=a.documents,
                          summary=a.context_summary, images=a.context_images, instructions=a.instructions.get()))
            a.status.set('上下文已加密保存到本机。')
        elif action == 'remove_image':
            remaining = [i for n, i in enumerate(a.context_images) if i.get('id', str(n)) != data.get('id')]
            if len(remaining) != len(a.context_images):
                a.context_images[:] = remaining
                a.context_changed()
                a.update_screenshot_note()
                a.save_session()
        elif action == 'window':
            if data.get('value') != 'topmost':
                raise ValueError('Unknown window action')
            a.window_hotkey('topmost')
        elif action in ('usage', 'speed', 'sessions', 'screenshots'):
            getattr(a, dict(usage='show_usage', speed='show_speed_test',
                            sessions='session_browser', screenshots='screenshot_manager')[action])()
        elif action == 'close':
            a.close()
        else:
            raise ValueError('Unknown action')

    def tick(self):
        if getattr(self.app, 'closed', False):
            return
        for _ in range(8):
            try:
                command = self.commands.get_nowait()
            except queue.Empty:
                break
            try:
                self.command(command)
            except Exception as exc:
                self.app.status.set(str(exc))
        try:
            self.feed.publish(self.snapshot())
        except Exception as exc:
            self.app.status.set('Interface sync error: ' + str(exc))
        finally:
            if not getattr(self.app, 'closed', False):
                self.app.root.after(100, self.tick)

    def read_state(self, path):
        return self.feed.read(**state_query(path))

    def close(self):
        self.feed.wake()
        self.server.shutdown()
        self.server.server_close()
