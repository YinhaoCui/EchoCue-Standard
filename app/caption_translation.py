"""Asynchronous caption translation; original transcripts never leave their source buffer."""
from collections import deque
import re
import threading
import time
import uuid

HEADER = re.compile(r'(?m)^(\[\d{2}:\d{2}:\d{2} (?:电脑|麦克风|System audio|Microphone)(?: · Speaker \d+)?\]\n)')


def display_transcript(text):
    """Hide capture-device labels in the reading view, retaining saved source metadata."""
    return re.sub(r'(?m)^(\[\d{2}:\d{2}:\d{2}) (?:电脑|麦克风|System audio|Microphone)((?: · Speaker \d+)?\])',
                  r'\1\2', text)


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
        self.workers = {}
        self.dispatches = 0
        self.batch_records = []
        self.batches = []
        self.open_batches = {}
        self.batch_timer = None

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
        # Translate stable sentence groups, rather than each short ASR endpoint.
        from live_transcription import append_transcript
        with self.app.live.lock:
            records = list(self.app.live.records)
        original, translated, source, translated_source = '', '', None, None
        if records:
            for index, record in enumerate(records):
                original, source = append_transcript(original, source, record)
                if original == text and getattr(self.app, 'follow_live', True):
                    # ASR may have finalized more records than the UI has consumed.
                    records = records[:index + 1]
                    break
            if original == text:
                grouped = records if self.app.content_language('caption') == 'original' else self.record_batches(records)
                for record in grouped:
                    body = self.body(record.get('body', record['text'].split('\n', 1)[-1]),
                                     draft=not record.get('caption_ready', True))
                    header = record['text'].split('\n', 1)[0]
                    view = dict(record, body=body, text=self.app.locale.t(header)+'\n'+body)
                    separator = '\n\n' if self.app.content_language('caption') == 'bilingual' else ' '
                    translated, translated_source = append_transcript(translated, translated_source, view, separator=separator)
                return translated
        parts = HEADER.split(text)
        return ''.join(self.app.locale.t(part) if HEADER.fullmatch(part) else self.body(part) for part in parts)

    def record_batches(self, records):
        now = time.monotonic()
        signatures = [(r.get('source'), r.get('speaker'), r['text'], r.get('body')) for r in records]
        # Edits and session restores invalidate grouping, never the source records.
        if signatures[:len(self.batch_records)] != self.batch_records:
            self.batches.clear()
            self.open_batches.clear()
            self.batch_records.clear()
        for record in records[len(self.batch_records):]:
            source = record.get('source')
            body = record.get('body', record['text'].split('\n', 1)[-1]).strip()
            index = self.open_batches.get(source)
            if index is not None and self.batches[index].get('speaker') != record.get('speaker'):
                self.batches[index]['caption_ready'] = True
                self.open_batches.pop(source)
                index = None
            if index is None:
                index = len(self.batches)
                self.batches.append(dict(record, body=body, updated_at=now, caption_ready=False))
                self.open_batches[source] = index
            else:
                batch = self.batches[index]
                batch['body'] = (batch['body'] + ' ' + body).strip()
                batch['updated_at'] = now
            batch = self.batches[index]
            value = batch['body']
            if (re.search(r'[.!?。！？][\s\"\'”’）)]*$', value)
                    or len(re.findall(r'[A-Za-z0-9]+', value)) >= 14
                    or len(re.findall(r'[\u3400-\u9fff]', value)) >= 40
                    or len(value) >= 400 or not record.get('ok', True)):
                batch['caption_ready'] = True
                self.open_batches.pop(source)
        self.batch_records = signatures
        with self.app.live.lock:
            active = {source for source, state in getattr(self.app.live, 'sources', {}).items() if state.get('data')}
            pending = (getattr(self.app.live, 'submitted', 0) > getattr(self.app.live, 'completed', 0)
                       or len(records) < len(self.app.live.records))
        active.update(getattr(self.app, 'live_drafts', {}))
        listening = any(device.active() for device in (getattr(self.app, 'capture', None), getattr(self.app, 'mic', None))
                        if device is not None)
        for source, index in list(self.open_batches.items()):
            batch = self.batches[index]
            if not pending and (not listening or (source not in active and now - batch['updated_at'] >= 1.2)):
                batch['caption_ready'] = True
                self.open_batches.pop(source)
        if self.batch_timer is not None:
            self.app.root.after_cancel(self.batch_timer)
            self.batch_timer = None
        if self.open_batches and not getattr(self.app, 'closing', False):
            delay = min(max(.05, 1.2 - (now - self.batches[index]['updated_at']))
                        if source not in active and not pending else 1.2
                        for source, index in self.open_batches.items())
            def flush():
                self.batch_timer = None
                self.refresh()
            self.batch_timer = self.app.root.after(max(1, int(delay * 1000)), flush)
        return [dict(batch, text=batch['text'].split('\n', 1)[0] + '\n' + batch['body']) for batch in self.batches]

    def start_next(self):
        if len(self.workers) >= 3 or not self.queue or getattr(self.app, 'closing', False):
            return
        # Give new speech one in three slots while older segments keep progressing.
        key = self.queue.pop() if self.dispatches % 3 == 2 else self.queue.popleft()
        self.dispatches += 1
        inputs, error = self.app.caption_models.inputs()
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
        self.workers[key] = cancel
        def work():
            # The English source is already visible; do not generate it a second time.
            english_bilingual = key[0] == 'bilingual' and not re.search(r'[\u3400-\u9fff]', key[1])
            try:
                result = translate(inputs, key[1], 'zh' if english_bilingual else key[0], cancel, self.app)
                if english_bilingual:
                    result = key[1] + '\n中文：' + result
                error = None
            except Exception as exc:
                result, error = '', str(exc)
                if inputs['key']:
                    error = error.replace(inputs['key'], '[KEY]')
            self.app.events.put(('caption_result', (epoch, key, result, error)))
        threading.Thread(target=work, daemon=True, name='caption-translation').start()

    def refresh(self):
        if self.app.follow_live:
            self.app.live_dirty = True
        else:
            self.app.select_transcript()

    def receive(self, result):
        epoch, key, text, error = result
        if epoch != self.epoch or getattr(self.app, 'closing', False):
            return
        self.workers.pop(key, None)
        self.active_key = next(iter(self.workers), None)
        self.active = self.workers.get(self.active_key)
        self.pending.discard(key)
        self.cache[key] = text if not error else self.notice('[Translation failed; change transcript language to retry]', '[翻译失败；切换转录语言可重试]')
        if error:
            self.failed.add(key)
            self.app.status.set(self.notice('Caption translation: ', '字幕翻译：') + error)
        self.refresh()
        self.start_next()

    def reset(self):
        # Keep successful translations and the active request across language toggles.
        for key in self.failed:self.cache.pop(key,None)
        self.failed.clear()
        self.queue.clear()
        self.pending=set(self.workers) or ({self.active_key} if self.active else set())

    def close(self):
        self.epoch += 1
        if self.batch_timer is not None:
            self.app.root.after_cancel(self.batch_timer)
            self.batch_timer = None
        if self.active:
            self.active.set()
        for cancel in self.workers.values():
            cancel.set()
        self.workers.clear()
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
    def emit(piece):
        if cancel.is_set():
            return
        pieces.append(piece)
    report = lambda value: usage.update(value or {})
    kwargs = dict(on_usage=report, total_timeout=60, effort=inputs['effort'])
    success = False
    try:
        if providers.is_cli(provider):
            providers.cli_answer(provider, prompt, options[providers.model_option(provider)], cancel, emit,
                                 transcript=text, instructions=system, **kwargs)
        elif provider == 'Gemini':
            a.gemini_answer(None, key, model, system, cancel, emit, transcript=text,
                            system_prompt=system, max_output=None, fast=True, **kwargs)
        else:
            a.compatible_answer(provider, text, key, model, system, cancel, emit,
                                base=options['lm_base'], system_prompt=system, max_output=None, reasoning=False, **kwargs)
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
