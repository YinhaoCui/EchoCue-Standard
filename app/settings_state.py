"""Saved answer options and reference context. Holds state only; the web UI edits it."""
import tkinter as tk
from account_support import load_settings
import providers
from meeting_assistance import DEFAULTS as MEETING_DEFAULTS, OPTIONS as MEETING_OPTIONS
from streaming_asr import ASR_MODELS, DEFAULT_ASR

PRESENTATION_DEFAULTS = {'ui_theme': 'classic', 'midnight_split': '40'}


def presentation_value(key, value):
    """Validate non-secret interface choices shared by loading and the web bridge."""
    if key == 'ui_theme':
        if value not in ('classic', 'midnight'):
            raise ValueError('Unknown interface style')
        return value
    if key == 'midnight_split':
        value = int(value)
        if not 25 <= value <= 65:
            raise ValueError('Transcript width must be between 25 and 65 percent')
        return str(value)
    raise ValueError('Unknown presentation setting')


DEFAULT_OPTIONS = {
    **PRESENTATION_DEFAULTS,
    **MEETING_DEFAULTS,
    'source': '电脑', 'asr_engine': DEFAULT_ASR, 'asr_pause': '快速 · 0.35 秒',
    'gemini_route': '文字（先转录）', 'lm_base': 'http://127.0.0.1:1234/v1',
    **{option: '' for option in providers.MODEL_OPTIONS},
    'deadline': '不限时', 'max_output': '服务默认', 'content_policy': 'unrestricted',
    'question_mode': '长问题', 'speculate': '仅疑问句', 'warm_context': '开启', 'thinking_policy': '自动',
    'incremental_context': '开启', 'spare_session': '关闭', 'background_mode': 'frosted',
    'listen_transparency': '12', 'transcript_font_size': '21', 'answer_font_size': '21', 'listen_layout': '',
    'listen_text_color': '#ffffff', 'listen_panel_color': '#213953', 'listen_text_bold': '0', 'listen_text_outline': '0',
    'listen_presets': '',
}
# Listen-page look. Saved on every exit, even when 'Remember keys' is off,
# because none of it is secret. A preset stores these same keys.
LAYOUT_KEYS = ('listen_transparency', 'transcript_font_size', 'answer_font_size', 'listen_layout',
               'listen_text_color', 'listen_panel_color', 'listen_text_bold', 'listen_text_outline')
SAVED_LAYOUT_KEYS = LAYOUT_KEYS + ('listen_presets', *PRESENTATION_DEFAULTS)


class SettingsState:
    def init_advanced(self):
        import audio_answer as a
        self.mic = a.Capture()
        self.history = []
        self.history_epoch = 0
        self.profile = self.documents = self.context_summary = ''
        self.context_images = []
        self.context_version = 0
        self.saved_prompt = ''
        self.prompt_templates = {}
        self.prompt_templates_version = 0
        self.prompt_templates_error = ''
        try:
            from prompt_templates import validate_templates
            self.prompt_templates = validate_templates(load_settings(a.data_path(a.ROOT, 'prompt_templates.dpapi')))
        except Exception:
            self.prompt_templates_error = '模板文件读取失败；为保护已有内容，未覆盖原文件。'
        options = dict(self.saved.get('advanced', {}))
        layout = self.saved.get('layout')
        if isinstance(layout, dict):
            options.update({key: str(layout[key]) for key in SAVED_LAYOUT_KEYS if key in layout})
        for key, default in PRESENTATION_DEFAULTS.items():
            try:
                options[key] = presentation_value(key, options.get(key, default))
            except (ValueError, TypeError, OverflowError):
                options[key] = default
        if options.get('content_policy') != 'unrestricted':
            options.update(deadline='不限时', max_output='服务默认')
        if options.get('asr_engine') not in ASR_MODELS:
            options['asr_engine'] = DEFAULT_ASR
        options['spare_session'] = '关闭'
        for key, values in MEETING_OPTIONS.items():
            if options.get(key) not in values:
                options[key] = MEETING_DEFAULTS[key]
        self.advanced = {key: tk.StringVar(value=options.get(key, value)) for key, value in DEFAULT_OPTIONS.items()}
        self.advanced['question_mode'].trace_add('write', self.change_question_mode)
        self.use_history = tk.BooleanVar(value=self.saved.get('use_history', True))
        self.mic_index = None
        try:
            data = load_settings(a.data_path(a.ROOT, 'context.dpapi'))
            self.profile = data.get('profile', '')
            self.documents = data.get('documents', '')
            self.context_summary = data.get('summary', '')
            self.context_images = data.get('images', [])
            self.saved_prompt = data.get('instructions', '')
            if not isinstance(self.saved_prompt, str):
                self.saved_prompt = ''
        except Exception:
            pass

    def context_changed(self):
        """Invalidate derived material and in-flight memory after a source edit."""
        self.context_version += 1
        if hasattr(self, 'auto_answers'):
            self.auto_answers.pending = None
        self.context_summary = ''
        self.history_epoch += 1
        self.cancel_context_preparation()
        self.change_question_mode()  # Discard unclaimed predictions only.

    def clear_history(self):
        """Forget Q&A memory while retaining source material and visible output."""
        self.history.clear()
        self.history_epoch += 1
        self.cancel_context_preparation()
        self.change_question_mode()
        self.save_session()
        self.status.set('问答记忆已清空；资料、转录和已有回答仍保留。')

    def clear_context(self):
        import audio_answer as a
        self.context_changed()
        self.profile = self.documents = self.context_summary = ''
        self.context_images.clear()
        self.update_screenshot_note()
        self.history.clear()
        a.data_path(a.ROOT, 'context.dpapi').unlink(missing_ok=True)
        self.status.set('资料、历史和已保存的上下文已清空。')

    def context_instructions(self):
        from session_data import compact_context, record_text
        from prompt_language import language
        with self.live.lock: records = list(self.live.records)
        return compact_context(self.profile, self.documents, self.context_summary,
                               self.history if self.use_history.get() else [], record_text(records), records,
                               language=language(self.provider.get(), self.model.get()))

    def start_analysis(self):
        if not (self.profile.strip() or self.documents.strip() or self.context_images):
            self.status.set('请先在“资料与上下文”导入文件或填写个人资料，并应用。'); return
        self.ask(analysis=True)
