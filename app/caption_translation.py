"""Asynchronous caption translation; original transcripts never leave their source buffer."""
from collections import deque
import re
import threading
import uuid

HEADER = re.compile(r'(?m)^(\[\d{2}:\d{2}:\d{2} (?:电脑|麦克风|System audio|Microphone)(?: · Speaker \d+)?\]\n)')


class CaptionPresenter:
    def __init__(self, app):
        self.app = app
        self.cache = {}
        self.pending = set()
        self.queue = deque()
        self.active = None
        self.epoch = 0
        self.failed = set()
        self.active_key = None

    def notice(self, english, chinese):
        return english if self.app.locale.language == 'en' else chinese

    def body(self, text, draft=False):
        if not text.strip():
            return text
        language = self.app.content_language('caption')
        if language == 'original':return text
        has_chinese = bool(re.search(r'[\u3400-\u9fff]', text))
        # ASR may leave product names in Chinese speech; keep those intact.
        if (language == 'en' and not has_chinese) or (language == 'zh' and has_chinese and len(re.findall(r'[A-Za-z]+', text)) < 4):
            return text
        if not re.search(r'[A-Za-z\u3400-\u9fff]', text):
            return text
        text=text.strip()
        key = (language, text)
        if key in self.cache:
            if language == 'bilingual' and key in self.failed:
                return text + '\n' + self.cache[key]
            return self.cache[key]
        waiting = self.notice('Translating…', '正在翻译…')
        if language == 'bilingual':
            waiting = text + '\n' + waiting
        if draft:
            if language == 'bilingual':
                return text
            return self.notice('Transcribing…', '正在转录…')
        if key not in self.pending and not getattr(self.app, 'closing', False):
            self.pending.add(key)
            self.queue.append(key)
            self.start_next()
        result = self.cache.get(key, waiting)
        if language == 'bilingual' and key in self.failed:
            return text + '\n' + result
        return result

    def transcript(self, text):
        # Prefer stable ASR segments so extending a source paragraph does not
        # translate the entire preceding conversation again.
        from live_transcription import append_transcript
        with self.app.live.lock:
            records = list(self.app.live.records)
        original, translated, source, translated_source = '', '', None, None
        if records:
            for record in records:
                original, source = append_transcript(original, source, record)
            if original == text:
                for record in records:
                    body = self.body(record.get('body', record['text'].split('\n', 1)[-1]))
                    header = record['text'].split('\n', 1)[0]
                    view = dict(record, body=body, text=self.app.locale.t(header)+'\n'+body)
                    translated, translated_source = append_transcript(translated, translated_source, view)
                return translated
        parts = HEADER.split(text)
        return ''.join(self.app.locale.t(part) if HEADER.fullmatch(part) else self.body(part) for part in parts)

    def start_next(self):
        if self.active or not self.queue or getattr(self.app, 'closing', False):
            return
        key = self.queue.popleft()
        inputs, error = self.app.request_inputs(caption=True)
        if error:
            self.pending.discard(key)
            self.failed.add(key)
            self.cache[key] = self.notice('[Translation unavailable: configure a model in Settings]', '[翻译不可用：请在设置中配置模型]')
            self.app.root.after_idle(self.start_next)
            return
        cancel = threading.Event()
        epoch = self.epoch
        self.active = cancel
        self.active_key = key
        def work():
            try:
                result = translate(inputs, key[1], key[0], cancel, self.app)
                error = None
            except Exception as exc:
                result, error = '', str(exc)
                if inputs['key']:
                    error = error.replace(inputs['key'], '[KEY]')
            self.app.events.put(('caption_result', (epoch, key, result, error)))
        threading.Thread(target=work, daemon=True, name='caption-translation').start()

    def receive(self, result):
        epoch, key, text, error = result
        if epoch != self.epoch or getattr(self.app, 'closing', False):
            return
        self.active = None
        self.pending.discard(key)
        self.cache[key] = text if not error else self.notice('[Translation failed; change transcript language to retry]', '[翻译失败；切换转录语言可重试]')
        if error:
            self.failed.add(key)
            self.app.status.set(self.notice('Caption translation: ', '字幕翻译：') + error)
        if self.app.follow_live:
            self.app.live_dirty = True
        else:
            self.app.select_transcript()
        self.start_next()

    def reset(self):
        # Keep successful translations and the active request across language toggles.
        for key in self.failed:self.cache.pop(key,None)
        self.failed.clear()
        self.queue.clear()
        self.pending={self.active_key} if self.active else set()

    def close(self):
        self.epoch += 1
        if self.active:
            self.active.set()
        self.active = None
        self.pending.clear()
        self.queue.clear()


def translate(inputs, text, language, cancel, app):
    """Use the selected transport without borrowing any answer conversation."""
    import audio_answer as a
    import providers
    provider, model, key = inputs['provider'], inputs['model'], inputs['key']
    options = inputs['options']
    from prompt_language import for_inputs, translation_prompt
    system = translation_prompt(for_inputs(inputs),language)
    prompt = system + '\n<transcript>\n' + text + '\n</transcript>'
    pieces, usage = [], {}
    report = lambda value: usage.update(value or {})
    kwargs = dict(on_usage=report, total_timeout=60, effort=inputs['effort'])
    success = False
    try:
        if providers.is_cli(provider):
            providers.cli_answer(provider, prompt, options[providers.model_option(provider)], cancel, pieces.append,
                                 transcript=text, instructions=system, **kwargs)
        elif provider == 'Gemini':
            a.gemini_answer(None, key, model, system, cancel, pieces.append, transcript=text,
                            system_prompt=system, max_output=None, **kwargs)
        else:
            a.compatible_answer(provider, text, key, model, system, cancel, pieces.append,
                                base=options['lm_base'], system_prompt=system, max_output=None, **kwargs)
        result = ''.join(pieces).strip()
        if not result or cancel.is_set():
            raise RuntimeError('Translation cancelled or empty')
        if '[达到模型输出上限' in result:
            raise RuntimeError('Translation exceeded the model output limit')
        success = True
        return result
    finally:
        try:
            app.token_ledger.record(app.session_id+':caption-'+uuid.uuid4().hex, provider,
                                    inputs['display_model'], usage, 'Caption translation' if success else 'Caption translation failed')
            app.events.put(('usage_updated', ''))
        except Exception:
            app.events.put(('usage_save_error', 'Token 用量保存失败，本次统计仅在内存。'))
