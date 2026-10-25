"""Headless controller behind the web interface: audio, live captions and answer jobs.

All state lives in plain attributes and Tk variables; no state is kept in
widgets. Tk remains as the event loop and for the small native dialogs
(usage, speed test, sessions, screenshots, transcript and glossary).
"""
from app_paths import ROOT, WORK, SETTINGS_FILE, data_path
import ctypes
import os
import queue
import threading
import time
import tkinter as tk
from tkinter import messagebox
import uuid
from session_support import Cancelled, streaming_events, local_base, cli_answer
from account_support import load_settings, save_settings, UsageLedger, read_codex_account, format_codex_account
from live_transcription import append_transcript
from streaming_asr import StreamingLiveTranscriber, ASR_MODELS, validate_model
from token_usage import TokenLedger
from antigravity_support import antigravity_answer
from claude_support import claude_answer
from kiro_support import kiro_answer
from model_catalog import CATALOG, CATEGORIES, describe, select_models, thinking_options
import providers
from audio_capture import RATE, wav_bytes, AudioBuffer, Capture, run_process, transcribe
from api_clients import (API_PROVIDERS, GEMINI_MODELS, CONTEXT_CAPACITY_MESSAGE, find_codex, codex_answer,
                         sse_events, gemini_http_error, list_gemini_models, context_capacity_error,
                         compatible_error, list_provider_models, compatible_answer, gemini_answer)
from answer_jobs import AnswerJobs
from cli_models import CliModels
from hotkey_settings import HotkeySettings
from reasoning_support import ReasoningState, parameters as reasoning_parameters
from screenshot_context import Screenshots
from session_control import SessionControl
from settings_state import SettingsState, SAVED_LAYOUT_KEYS
from speed_test import SpeedTestUI
from usage_ui import UsageUI

SPECIAL_PROVIDERS = providers.CLI_PROVIDERS
HOTKEY_ID = 0x4411


from meeting_assistance import MeetingAssistance


class App(MeetingAssistance, Screenshots, SessionControl, SpeedTestUI, ReasoningState, CliModels, UsageUI, HotkeySettings,
          AnswerJobs, SettingsState):
    def __init__(self, root):
        self.root = root
        self.capture = Capture()
        self.events = queue.Queue()
        from generation_context import GenerationLanes
        self.generation_lanes = GenerationLanes()
        self.cancel = threading.Event()
        self.busy = False
        self.closed = False
        self.worker = None
        self.ask_revision = 0
        self.transcript_records = []
        self.selected_transcript = -1
        self.job_labels = {}
        self.jobs = {}
        # The answer log: text parts, with one reserved part per job that its answer streams into.
        self.output_parts = []
        self.job_regions = {}
        self.transcript_view = ''
        self.live_text = ''
        self.live_last_source = None
        self.live_drafts = {}
        self.follow_live = True
        self.session_id = uuid.uuid4().hex
        self.save_timer = None
        self.loading_settings = True
        self.preferences_error = ''
        try:
            self.saved = load_settings(SETTINGS_FILE)
        except Exception:
            self.saved = {}
            self.preferences_error = '已有配置无法解密；请重新填写 Key 并保存。'
        from localization import Locale
        self.locale = Locale(root, self.saved.get('ui_language', 'en'))
        self.caption_language = tk.StringVar(value={'en': 'English', 'zh': '中文', 'original': '原文', 'bilingual': '中英双语'}.get(
            self.saved.get('caption_language', self.locale.language), 'English'))
        self.answer_language = tk.StringVar(value={'en': 'English', 'zh': '中文', 'bilingual': '中英双语'}.get(
            self.saved.get('answer_language', self.locale.language), 'English'))
        from caption_translation import CaptionPresenter
        self.captions = CaptionPresenter(self)
        self.init_advanced()
        self.token_ledger = TokenLedger(data_path(ROOT, 'token_usage.json'))
        self.live = StreamingLiveTranscriber(ROOT, lambda kind, value: self.events.put((kind, value)))
        self.init_meeting()
        self.configure_meeting_audio()
        self.advanced['asr_pause'].trace_add('write', self.update_asr_pause)
        self.update_asr_pause()
        root.after(250, self.preload_asr)
        self.capture.on_pcm = lambda pcm: self.feed_meeting_audio('电脑', pcm)
        self.mic.on_pcm = lambda pcm: self.feed_meeting_audio('麦克风', pcm)
        self.usage_ledger = UsageLedger(data_path(ROOT, 'gemini_usage.json'))
        from ui_theme import apply_theme
        apply_theme(root)  # styles for the native dialogs
        self.init_hotkeys()
        self.init_usage()

        self.provider = tk.StringVar(value=providers.migrate(self.saved.get('provider', providers.CODEX)))
        self.api_settings = {name: {'key': os.environ.get(config['env'], ''), 'model': next(iter(config['models']), '')}
                             for name, config in API_PROVIDERS.items()}
        for name, settings_saved in self.saved.get('apis', {}).items():
            if name in self.api_settings and isinstance(settings_saved, dict):
                self.api_settings[name].update({k: v for k, v in settings_saved.items() if k in ('key', 'model') and isinstance(v, str)})
        self.discovered_models = {}
        self.refresh_busy = False
        self.refresh_pending = False
        self.api_editing = 'Gemini'
        self.provider_note = tk.StringVar()
        self.key = tk.StringVar(value=self.api_settings['Gemini']['key'])
        self.model = tk.StringVar(value=self.api_settings['Gemini']['model'])
        self.model_choices = list(GEMINI_MODELS)
        self.model_note = tk.StringVar(value=GEMINI_MODELS.get(self.model.get(), '自定义模型'))
        self.key_status = tk.StringVar(value='尚未检测')
        self.check_revision = 0
        self.check_busy = False
        self.key.trace_add('write', self.invalidate_check)
        self.model.trace_add('write', self.invalidate_check)
        self.advanced['lm_base'].trace_add('write', self.invalidate_check)
        self.remember_keys = tk.BooleanVar(value=self.saved.get('remember_keys', True))
        self.answer_mode = tk.StringVar(value=self.saved.get('answer_mode', '快速'))
        self.fast_mode = tk.BooleanVar(value=bool(self.saved.get('fast', True)))
        self.save_status = tk.StringVar(value=self.preferences_error or ('已加载本机加密配置' if self.saved else '填入 Key 后自动加密保存'))
        self.instructions = tk.StringVar(value=self.saved_prompt)
        self.live_note = tk.StringVar(value='实时转录：尚未监听')
        self.status = tk.StringVar(value='尚未监听。选择播放设备，然后点击“准备”。')
        self.hotkey_status = tk.StringVar(value='正在注册快捷键…')
        self.level = 0
        self.devices = []
        self.device_index = -1
        self.init_cli_models()
        self.init_reasoning()
        self.update_provider()
        self.init_sessions()
        self.init_screenshots()
        self.refresh_devices()
        self.hotkey_thread = threading.Thread(target=self.listen_hotkey, daemon=True)
        self.hotkey_thread.start()
        self.loading_settings = False
        self.provider.trace_add('write', lambda *_: self.schedule_save())
        root.protocol('WM_DELETE_WINDOW', self.close)
        root.after(60, self.poll)

    @property
    def output_text(self):
        return ''.join(self.output_parts)

    def window_hotkey(self, action):
        """Window shortcuts act on the web host window; glass_desktop replaces this."""

    def update_provider(self):
        self.api_settings[self.api_editing] = {'key': self.key.get().strip(), 'model': self.model.get().strip()}
        provider = self.provider.get()
        self.provider_note.set(providers.note(provider))
        if provider in API_PROVIDERS:
            self.api_editing = provider
            self.key.set(self.api_settings[provider]['key'])
            self.model.set(self.api_settings[provider]['model'])
            self.filter_models()
        else:
            self.show_cli_model(provider)
        self.update_reasoning()

    def model_catalog_key(self, provider):
        """Session-only cache identity; never exported in web state or persisted."""
        key = self.key.get().strip() if provider == self.api_editing else self.api_settings[provider]['key'].strip()
        base = self.advanced['lm_base'].get().strip() if provider == 'LM Studio' else ''
        return provider, key, base

    def filter_models(self):
        self.model_choices = select_models(self.api_editing, self.discovered_models.get(self.model_catalog_key(self.api_editing)))

    def model_catalog_note(self, provider=None):
        provider = provider or self.api_editing
        if self.model_catalog_key(provider) in self.discovered_models:
            return '目录来源：最近一次成功获取。'
        if provider == 'LM Studio':
            return '尚未获取本地模型目录，请刷新或手动填写模型 ID。'
        return '目录来源：内置预设，尚未验证可用性。'

    def refresh_models(self):
        if self.refresh_busy:
            self.refresh_pending = True
            return
        provider, key = self.api_editing, self.key.get().strip()
        if not key and provider != 'LM Studio':
            self.key_status.set('请先填写当前平台的 Key，再刷新模型目录。')
            return
        self.refresh_busy = True
        catalog_key = self.model_catalog_key(provider)
        base = self.advanced['lm_base'].get()
        self.key_status.set('正在读取官方目录，不发送生成请求…')
        def work():
            try:
                models = list_provider_models(provider, key, base=base)
                self.events.put(('models_refreshed', (provider, catalog_key, models, None)))
            except Exception as exc:
                message = str(exc).replace(key, '[KEY]') if key else str(exc)
                self.events.put(('models_refreshed', (provider, catalog_key, None, message)))
        threading.Thread(target=work, daemon=True).start()

    def invalidate_check(self, *_):
        self.check_revision += 1
        self.filter_models()
        self.key_status.set('Key 或模型已修改，请重新检测。')
        self.model_note.set(API_PROVIDERS[self.api_editing]['models'].get(self.model.get().strip(), '自定义模型：价格和能力请核对官方说明。'))
        self.schedule_save()

    def schedule_save(self):
        if self.loading_settings or self.closed:
            return
        if self.save_timer:
            self.root.after_cancel(self.save_timer)
        self.save_timer = self.root.after(700, self.save_preferences)

    def change_ui_language(self, language=None):
        if language is not None:
            self.locale.set_language('en' if language == 'en' else 'zh')
        if self.follow_live and (self.live_text or self.live_drafts): self.render_live_transcript()
        elif not self.follow_live: self.select_transcript()
        self.schedule_save()
        if getattr(self, 'quota_window', None) is not None and self.quota_window.winfo_exists(): self.render_usage()
        if getattr(self, 'speed_window', None) is not None and self.speed_window.winfo_exists(): self.render_speed_results()

    def content_language(self, kind):
        variable = self.caption_language if kind == 'caption' else self.answer_language
        return {'English': 'en', '中文': 'zh', '原文': 'original', '中英双语': 'bilingual'}.get(variable.get(), 'en')

    def change_content_language(self, kind):
        if kind == 'caption':
            self.captions.reset()
            if self.follow_live and (self.live_text or self.live_drafts): self.render_live_transcript()
            elif not self.follow_live: self.select_transcript()
        else:
            # Discard only speculative work; explicit answer jobs keep their snapshot.
            spec = getattr(self, 'speculation', None)
            if spec: spec.discard(); self.speculation = None
            self.cancel_context_preparation()
        self.schedule_save()

    def save_preferences(self):
        self.save_timer = None
        self.api_settings[self.api_editing] = {'key': self.key.get().strip(), 'model': self.model.get().strip()}
        common = {'ui_language': self.locale.language, 'caption_language': self.content_language('caption'),
                  'answer_language': self.content_language('answer'), 'hotkeys': self.hotkeys,
                  'layout': {key: self.advanced[key].get() for key in SAVED_LAYOUT_KEYS}}
        try:
            if self.remember_keys.get():
                save_settings(SETTINGS_FILE, {**common, 'apis': self.api_settings, 'terms': getattr(self, 'terms', ''),
                    'provider': self.provider.get(), 'use_history': self.use_history.get(), 'fast': self.fast_mode.get(),
                    'answer_mode': self.answer_mode.get(), 'reasoning_settings': self.reasoning_settings,
                    'advanced': {k: v.get() for k, v in self.advanced.items()}})
                self.save_status.set('已加密保存，下次打开自动填入')
            else:
                save_settings(SETTINGS_FILE, {**common, 'remember_keys': False})
                self.save_status.set('未保存 Key；快捷键和布局已保存')
        except Exception:
            self.save_status.set('保存失败，Key 仅在本次内存中；请检查目录权限')
            return False
        return True

    def check_gemini(self, probe=False, all_keys=False):
        if self.check_busy:
            return
        key, model = self.key.get().strip(), self.model.get().strip()
        self.api_settings[self.api_editing] = {'key': key, 'model': model}
        self.save_preferences()
        provider = self.api_editing
        targets = dict((name, dict(config)) for name, config in self.api_settings.items()) if all_keys else {provider: {'key': key, 'model': model}}
        if not all_keys and not key and provider != 'LM Studio':
            self.key_status.set('请先填写当前平台的 API Key。')
            return
        revision = self.check_revision
        self.check_busy = True
        self.key_status.set('正在测试所选模型…' if probe else '正在检测接口…')
        base = self.advanced['lm_base'].get()

        def check():
            results = []
            for name, config in targets.items():
                secret, selected_model = config['key'], config['model']
                if not secret and name != 'LM Studio':
                    results.append(name + '：未填写 Key，已跳过。')
                    continue
                try:
                    if probe:
                        start = time.monotonic()
                        usage, success = {}, False
                        try:
                            if name == 'Gemini':
                                gemini_answer(None, secret, selected_model, '', threading.Event(), lambda _: None,
                                              transcript='Connectivity test. Reply only OK.', fast=True,
                                              on_usage=lambda value: usage.update(value), max_output=128)
                            else:
                                compatible_answer(name, '', secret, selected_model, '', threading.Event(), lambda _: None,
                                                  probe=True, base=base, on_usage=lambda value: usage.update(value))
                            success = True
                        finally:
                            self.token_ledger.record(self.session_id + ':probe-' + uuid.uuid4().hex, name, selected_model, usage, '测试完成' if success else '测试失败')
                            self.events.put(('usage_updated', ''))
                        result = f'模型请求成功（{time.monotonic() - start:.1f} 秒），用量已记录；不代表真实问答速度或免费额度。'
                    else:
                        available = list_provider_models(name, secret, base=base)
                        selected = '所选模型已列出' if selected_model in available else '所选模型未列出'
                        result = f'Key 可访问目录；{selected}。生成权限/余额/额度请再测试模型。'
                    results.append(name + '：' + result)
                except Exception as exc:
                    results.append(name + '：检测未通过，' + (str(exc).replace(secret, '[KEY]') if secret else str(exc)))
            message = '\n'.join(results)
            self.events.put(('key_check', (revision, message)))
            if all_keys:
                self.events.put(('all_check_report', (revision, message)))
        threading.Thread(target=check, daemon=True).start()

    def refresh_devices(self):
        if self.capture.active() or self.mic.active():
            self.status.set('请先停止监听再刷新设备。')
            return
        self.devices = self.capture.devices()
        self.device_index = -1
        if self.devices:
            try:
                default = self.capture.audio.get_default_wasapi_loopback()['index']
                self.device_index = next(i for i, d in enumerate(self.devices) if d['index'] == default)
            except (OSError, LookupError, StopIteration):
                self.device_index = 0
        else:
            self.status.set('未发现播放设备，请连接耳机或扬声器后重启工具。')

    def preload_asr(self):
        if not self.closed and not getattr(self, 'closing', False):
            self.live.preload(self.advanced['asr_engine'].get())

    def warm_answer_channel(self):
        """Prepare the selected provider while speech is still arriving (throttled, never blocks Tk)."""
        if self.closed or getattr(self, 'closing', False): return
        now = time.monotonic()
        if now - getattr(self, 'last_channel_warm', -1e9) < 15: return
        self.last_channel_warm = now
        provider = self.provider.get()
        options = {name: self.advanced[name].get() for name in ('codex_model', 'lm_base', 'spare_session') if name in self.advanced}
        def run():
            try:
                if provider == 'Codex':
                    from codex_service import get_service
                    get_service(find_codex(), WORK).prewarm((options.get('codex_model') or '').strip())
                elif provider == 'Gemini':
                    import http_pool; http_pool.warm('https://generativelanguage.googleapis.com/', count=1)
                elif provider in API_PROVIDERS:
                    import http_pool
                    base = local_base(options.get('lm_base') or API_PROVIDERS[provider]['base']) if provider == 'LM Studio' else API_PROVIDERS[provider]['base']
                    http_pool.warm(base, count=1)
            except Exception:
                pass
        threading.Thread(target=run, daemon=True).start()

    def update_asr_pause(self, *_):
        self.live.silence = {'快速 · 0.35 秒': .35, '均衡 · 0.65 秒': .65, '稳妥 · 1.0 秒': 1.0}.get(self.advanced['asr_pause'].get(), .35)
        if not self.loading_settings: self.schedule_save()

    def listening(self):
        return not getattr(self, 'closing', False) and bool(self.capture.active() or self.mic.active())

    def prepare_listening(self):
        if getattr(self, 'closing', False) or getattr(self, 'preparing_listen', False): return
        if self.capture.active() or self.mic.active(): return
        self.preparing_listen = True
        self.status.set('准备中：正在启动监听，随后准备模型上下文…')
        def start():
            try: self.toggle_listen()
            finally: self.preparing_listen = False
        self.root.after_idle(start)

    def toggle_listen(self, recap=True):
        if getattr(self, 'closing', False): return
        if self.capture.active() or self.mic.active():
            self.capture.stop(); self.mic.stop()
            self.transcription_paused = True
            spec = getattr(self, 'speculation', None)
            if spec: spec.discard(); self.speculation = None
            self.live.flush()
            self.capture.buffer.clear(); self.mic.buffer.clear()
            self.status.set('转录已暂停；已有内容保留，正在生成的回答继续。')
            if recap and self.advanced.get('auto_recap') and self.advanced['auto_recap'].get() == '1':
                self.finish_recap()
        else:
            try:
                selection = self.advanced['asr_engine'].get()
                validate_model(ROOT, selection)
                self.live.configure(selection)
                if hasattr(self, 'echo_filter'):
                    self.echo_filter.reset()
                source = self.advanced['source'].get()
                if source != '麦克风':
                    if not 0 <= self.device_index < len(self.devices):
                        raise RuntimeError('请选择播放设备。')
                    self.capture.start(self.devices[self.device_index])
                if source != '电脑':
                    device = (self.mic.audio.get_device_info_by_index(self.mic_index) if self.mic_index is not None
                              else self.mic.audio.get_default_input_device_info())
                    if device.get('isLoopbackDevice'):
                        raise RuntimeError('请选择实际麦克风设备。')
                    self.mic.start(device)
                self.transcription_paused = False
                self.warm_answer_channel()
                self.prepare_model_context()
                self.status.set('实时转录中：' + source + '。说完后稍候可见文字；按快捷键只触发回答。')
            except Exception as exc:
                self.capture.stop(); self.mic.stop()
                self.status.set('无法开始监听：' + str(exc))

    def change_asr(self):
        selection = self.advanced['asr_engine'].get()
        try:
            validate_model(ROOT, selection)
            self.live.configure(selection)
        except Exception as exc:
            self.advanced['asr_engine'].set(self.live.engine)
            self.status.set('无法切换转录模型：' + str(exc))
            return
        self.schedule_save()
        self.status.set('转录已切换为 ' + selection + '；已有转录和回答继续保留。')

    def clear(self):
        self.capture.buffer.clear()
        self.mic.buffer.clear()
        self.status.set('音频缓存已清空。')

    def put_text(self, text, replace=False, target='output'):
        """Append to (or replace) the answer log, or replace the transcript view."""
        if target == 'transcript':
            self.transcript_view = text if replace else self.transcript_view + text
            return
        if replace:
            self.output_parts = []
            self.job_regions = {}
        self.output_parts.append(text)

    def render_live_transcript(self):
        pending = '\n\n'.join(self.locale.t('[' + source + ' · 识别中，文字可能修订]') + '\n' + self.captions.body(value['text'], draft=True)
                              for source, value in self.live_drafts.items())
        visible = self.captions.transcript(self.live_text)
        self.transcript_view = visible + ('\n\n' + pending if pending else '')

    def show_live_transcript(self):
        self.follow_live = True
        self.render_live_transcript()

    def select_transcript(self):
        self.follow_live = False
        index = self.selected_transcript
        if 0 <= index < len(self.transcript_records):
            self.put_text(self.captions.transcript(self.transcript_records[index]['text']), replace=True, target='transcript')

    def remember_transcript(self, text, request_id, select=True):
        record = next((r for r in self.transcript_records if r['id'] == request_id), None)
        if record:
            record['text'] = text
        else:
            record = {'id': request_id, 'text': text,
                      'label': f"{len(self.transcript_records)+1}. " + self.job_labels.get(request_id, time.strftime('%H:%M:%S'))}
            self.transcript_records.append(record)
        if select:
            self.selected_transcript = self.transcript_records.index(record)
            self.select_transcript()

    def poll(self):
        if self.closed:
            return
        closing = getattr(self, 'closing', False)
        if not closing:
            self.level = max(self.capture.level if self.capture.active() else 0, self.mic.level if self.mic.active() else 0)
        for request_id, job in self.jobs.items():
            if not job['done'] and time.monotonic()-job['started'] > job['timeout']:
                self.cancel_job(request_id, '此任务达到时限；已保留部分答案，可继续回答。')
        if not closing and self.mic.error:
            self.status.set('麦克风采集失败：' + self.mic.error)
            self.mic.error = ''
            self.mic.stop()
        if self.capture.error:
            self.status.set('音频采集已中断：' + self.capture.error)
            self.capture.error = ''
        try:
            poll_deadline = time.monotonic() + .012
            while time.monotonic() < poll_deadline:
                kind, text = self.events.get_nowait()
                self.handle_event(kind, text)
        except queue.Empty:
            pass
        except Exception as exc:
            self.cancel_answer('界面事件处理失败，已恢复回答按钮：' + type(exc).__name__)
        finally:
            if not self.closed:
                if not closing and hasattr(self, 'auto_answers'):
                    self.meeting_tick()
                self.session_tick()
                self.root.after(60, self.poll)

    def handle_event(self, kind, text):
        if kind == 'caption_result':
            self.captions.receive(text)
        elif kind == 'screenshot':
            self.receive_screenshot(text)
        elif kind == 'session_saved':
            self.session_note.set(text)
        elif kind == 'live_status':
            self.live_note.set(text)
        elif kind == 'live_pending':
            self.live_note.set(f'实时转录：待处理 {text} 段' if text else '实时转录：已跟上语音')
        elif kind == 'live_partial':
            self.live_drafts[text['source']] = text
            self.live_dirty = True
            self.warm_answer_channel()
        elif kind == 'live_segment':
            draft = self.live_drafts.get(text.get('source'))
            if draft and draft['generation'] <= text['generation']: self.live_drafts.pop(text['source'], None)
            self.live_text, self.live_last_source = append_transcript(self.live_text, self.live_last_source, text)
            self.remember_transcript(text['text'], -text['sequence'], select=False)
            if self.follow_live:
                self.selected_transcript = len(self.transcript_records)-1
                self.live_dirty = True
            if hasattr(self, 'auto_answers'):
                self.offer_auto_answer(text)
            if not self.advanced.get('auto_answers') or self.advanced['auto_answers'].get() == 'off':
                self.maybe_speculate(text)
        elif kind == 'context_warm':
            ticket, message = text
            if ticket == getattr(self, 'context_warm_ticket', None): self.context_warm_note.set(message)
        elif kind == 'job':
            self.handle_job_event(*text)
        elif kind == 'completed':
            analysis, version, transcript, answer = text
            if version == self.context_version:
                if analysis:
                    self.context_summary = answer
                else:
                    self.history.append({'转录': transcript, '回答': answer})
        elif kind == 'text':
            self.put_text(text)
        elif kind == 'transcript':
            self.remember_transcript(text, self.ask_revision)
        elif kind == 'transcript_error':
            self.put_text(text, replace=True, target='transcript')
        elif kind == 'transcript_async':
            request_id, transcript = text
            if request_id == self.ask_revision:
                self.put_text(transcript, replace=True, target='transcript')
        elif kind == 'transcript_cancelled':
            if self.transcript_view == '正在转录本次音频…':
                self.put_text('本次转录已取消。', replace=True, target='transcript')
        elif kind == 'status':
            self.status.set(text)
        elif kind == 'done':
            self.busy = False
        elif kind == 'transcription':
            self.toggle_listen()
        elif kind == 'hotkey':
            self.ask(pressed_at=text if isinstance(text, (int, float)) else None)
        elif kind == 'refill_generation':
            self.ensure_spare_context()
        elif kind == 'window_hotkey':
            self.window_hotkey(text)
        elif kind == 'hotkey_status':
            self.hotkey_status.set(text)
            self.hotkey_registration_note.set(text)
        elif kind == 'models_refreshed':
            provider, catalog_key, models, error = text
            self.refresh_busy = False
            if not error:
                self.discovered_models[catalog_key] = models
            if provider == self.api_editing and catalog_key == self.model_catalog_key(provider):
                if error:
                    self.key_status.set('刷新失败：' + error)
                else:
                    self.filter_models()
                    self.key_status.set(f'官方返回 {len(models)} 个模型；目录可见不代表能生成，仍可测试所选模型。')
            if self.refresh_pending:
                self.refresh_pending = False
                if self.provider.get() in API_PROVIDERS:
                    self.refresh_models()
        elif kind == 'key_check':
            revision, message = text
            self.check_busy = False
            if revision == self.check_revision:
                self.key_status.set(message)
        elif kind == 'all_check_report':
            revision, message = text
            if revision == self.check_revision:
                messagebox.showinfo('全部 API 检测结果', message + '\n\nCodex 使用本机登录，不在 API Key 检测范围内。')
        elif kind == 'codex_quota':
            self.quota_busy = False
            self.codex_quota_text = text
            self.render_usage()
        elif kind == 'codex_capabilities':
            self.codex_capabilities = {item['model']: [level['reasoningEffort'] for level in item.get('supportedReasoningEfforts', []) if level.get('reasoningEffort')] for item in text}
            self.update_reasoning()
        elif kind == 'speed_models':
            self.receive_speed_models(text)
        elif kind == 'speed_result':
            self.receive_speed_result(text)
        elif kind == 'cli_models':
            self.receive_cli_models(text)
        elif kind == 'provider_balance':
            provider, result = text
            self.balance_busy.discard(provider)
            setattr(self, 'deepseek_balance_text' if provider == 'DeepSeek' else 'kimi_balance_text', result)
            self.render_usage()
        elif kind == 'usage_updated':
            self.render_usage()
        elif kind == 'usage_save_error':
            self.save_status.set(text)

    def handle_job_event(self, revision, kind, text):
        job = self.jobs.get(revision)
        if not job or job['done']:
            return
        if kind == 'text':
            if text.startswith('\n[处理失败，已有内容已保留]'): text = self.locale.t(text)
            job['answer'] += text
            self.job_text(revision, text)
            if text.strip() and 'first_reply' in job.get('timing', {}) and not job.get('display_scheduled'):
                job['display_scheduled'] = True
                self.root.after_idle(lambda j=job: self.record_first_display(j))
        elif kind == 'usage':
            job['usage'] = text
        elif kind == 'timing':
            job.setdefault('timing', {}).update(text)
        elif kind == 'snapshot':
            job['transcript'] = text
            self.remember_transcript(text, revision, select=False)
        elif kind == 'status':
            job['state'] = text
            self.status.set(f'任务 #{revision}：' + text)
        elif kind == 'state':
            job['state'] = text
        elif kind == 'completed':
            analysis, version, transcript, answer = text
            job['completed'] = True
            if (analysis and version == self.context_version) or (not analysis and job.get('history_epoch', 0) == getattr(self, 'history_epoch', 0)):
                if analysis: self.context_summary = answer
                else:
                    self.history.append({'转录截止段': job['target'], '回答': answer} if job.get('target') is not None else {'转录': transcript, '回答': answer})
        elif kind == 'done':
            job['done'] = True
            job['elapsed'] = time.monotonic()-job['started']
            self.busy = any(not value['done'] for value in self.jobs.values())
            self.job_text(revision, self.locale.t('\n[此任务结束]\n'))

    def close(self):
        if self.closed: return
        if getattr(self, 'closing', False): return
        self.closing = True
        self.captions.close()
        threading.Thread(target=self.generation_lanes.close, daemon=True).start()
        from claude_support import close_service as close_claude
        threading.Thread(target=close_claude, daemon=True).start()
        from codex_service import close_service
        threading.Thread(target=close_service, daemon=True).start()
        from antigravity_support import close_service as close_agy
        threading.Thread(target=close_agy, daemon=True).start()
        import http_pool; http_pool.close_all()
        self.cancel_context_preparation()
        if getattr(self, 'speculation', None): self.speculation.discard()
        self.status.set('正在保存会话并关闭…')
        self.cancel_speed_test()
        if self.save_timer:
            self.root.after_cancel(self.save_timer)
        try:
            self.save_preferences()
        except Exception:
            self.status.set('设置保存失败，正在关闭…')
        self.cancel.set()
        for job in self.jobs.values():
            job['cancel'].set()
        if self.hotkey_thread_id:
            ctypes.windll.user32.PostThreadMessageW(self.hotkey_thread_id, 0x0012, 0, 0)
        # A stuck audio driver must not hold Tk's event loop or the other device.
        stopped = [threading.Event(), threading.Event()]
        def stop_device(device, done):
            try:
                device.stop()
            except Exception:
                pass
            finally:
                done.set()
        for device, done in zip((self.capture, self.mic), stopped):
            threading.Thread(target=stop_device, args=(device, done), daemon=True).start()
        ready = threading.Event()
        def finish_audio():
            try:
                deadline = time.monotonic()+2
                for done in stopped: done.wait(max(0, deadline-time.monotonic()))
                target = self.live.flush()
                while self.live.completed < target and time.monotonic() < deadline:
                    time.sleep(.02)
            finally:
                self.live.close()
                ready.set()
        threading.Thread(target=finish_audio, daemon=True).start()
        deadline = time.monotonic()+3
        def finish_window():
            if not ready.is_set() and time.monotonic() < deadline:
                self.root.after(40, finish_window); return
            # Drain delivered text before capturing the last encrypted checkpoint.
            self.poll()
            self.closed = True
            try:
                self.save_session()
            finally:
                writer = self.session_writer
                saved = threading.Event()
                def finish_save():
                    try:
                        if writer: writer.close()
                    finally:
                        saved.set()
                threading.Thread(target=finish_save, daemon=True).start()
                for device, done in zip((self.capture, self.mic), stopped):
                    def cleanup(device=device, done=done):
                        done.wait()
                        try: device.close()
                        except Exception: pass
                    threading.Thread(target=cleanup, daemon=True).start()
                def destroy_when_saved():
                    if saved.is_set(): self.root.destroy()
                    else: self.root.after(40, destroy_when_saved)
                destroy_when_saved()
        self.root.after(40, finish_window)
