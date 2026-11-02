"""Asynchronous caption translation; original transcripts never leave their source buffer."""
from collections import deque
import re
import threading
import time
import uuid

HEADER = re.compile(r'(?m)^(\[\d{2}:\d{2}:\d{2} (?:电脑|麦克风|System audio|Microphone)(?: · Speaker \d+)?\]\n)')
BATCH_DEADLINE = 1.5
PREVIEW_STABILITY = .5
PREVIEW_INTERVAL = 1.0
PREVIEW_MAX_CHARS = 400


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
        self.partials = {}
        self.previews = {}
        self.preview_queue = {}
        self.preview_keys = {}
        self.preview_timer = None
        self.preview_due = None

    def notice(self, english, chinese):
        return english if self.app.locale.language == 'en' else chinese

    def body(self, text, draft=False, source=None, generation=0):
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
        if draft and source is not None:
            return self.preview(text, language, source, generation)
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
        # An identical finalized segment can adopt its preview request.
        if key in self.preview_keys:
            self.preview_keys.pop(key)
            self.preview_queue = {source: queued for source, queued in self.preview_queue.items() if queued != key}
            if key not in self.workers:
                self.queue.append(key)
                self.start_next()
        if key not in self.pending and not getattr(self.app, 'closing', False):
            self.pending.add(key)
            self.queue.append(key)
            self.start_next()
        result = self.cache.get(key, self.partials.get(key, waiting))
        if language == 'bilingual' and key in self.failed:
            return text + '\n' + result
        return result

    @staticmethod
    def enough_preview(text):
        return len(re.findall(r'[A-Za-z0-9]+', text)) >= 4 or len(re.findall(r'[\u3400-\u9fff]', text)) >= 8

    def preview_refresh(self, delay):
        if getattr(self.app, 'closing', False):
            return
        due = time.monotonic() + max(.02, delay)
        if self.preview_timer is not None:
            if self.preview_due <= due:
                return
            self.app.root.after_cancel(self.preview_timer)
        self.preview_due = due
        def refresh():
            self.preview_timer = self.preview_due = None
            self.refresh()
        self.preview_timer = self.app.root.after(max(20, int(delay * 1000)), refresh)

    def discard_queued_preview(self, source):
        key = self.preview_queue.pop(source, None)
        if key is not None:
            self.preview_keys.pop(key, None)
            self.pending.discard(key)

    def sync_previews(self, drafts):
        for source, state in list(self.previews.items()):
            draft = drafts.get(source)
            if draft is None or draft.get('generation', 0) != state['generation']:
                self.discard_queued_preview(source)
                self.previews.pop(source)
        if not self.previews and self.preview_timer is not None:
            self.app.root.after_cancel(self.preview_timer)
            self.preview_timer = self.preview_due = None

    def preview(self, text, language, source, generation):
        now = time.monotonic()
        state = self.previews.get(source)
        if state is None or (state['generation'], state['language']) != (generation, language):
            self.discard_queued_preview(source)
            state = self.previews[source] = dict(generation=generation, language=language, anchor=text,
                                                  text=text, since=now, last=-1e9, key=None, shown=None,
                                                  revision=0, shown_revision=-1, submitted_anchor=None)
        elif text != state['text']:
            anchor = state['anchor']
            count = 0
            for a, b in zip(anchor, text):
                if a != b:
                    break
                count += 1
            prefix = text[:count]
            # Do not stabilize the middle of a changing English word.
            if (prefix and count < len(text) and prefix[-1].isascii() and prefix[-1].isalnum()
                    and text[count].isascii() and text[count].isalnum()):
                prefix = re.sub(r'\S+$', '', prefix)
            if prefix.strip() != anchor:
                state['anchor'], state['since'] = prefix.strip(), now
            if not self.enough_preview(state['anchor']):
                state['anchor'], state['since'] = text, now
            if state['anchor'] == state['submitted_anchor'] and text != state['anchor']:
                state['anchor'], state['since'] = text, now
            state['text'] = text
        anchor = state['anchor']
        cached_key = (language, text)
        if cached_key in self.cache and cached_key not in self.failed:
            state['key'] = cached_key
        if self.enough_preview(anchor):
            delay = max(state['since'] + PREVIEW_STABILITY, state['last'] + PREVIEW_INTERVAL) - now
            if delay <= 0:
                # Bound repeated previews; the finalized source is always translated in full.
                candidate = anchor[-PREVIEW_MAX_CHARS:]
                if (len(anchor) > PREVIEW_MAX_CHARS and anchor[-PREVIEW_MAX_CHARS - 1].isascii()
                        and anchor[-PREVIEW_MAX_CHARS - 1].isalnum()
                        and candidate[0].isascii() and candidate[0].isalnum()):
                    candidate = re.sub(r'^\S*\s*', '', candidate) or candidate
                key = (language, candidate)
                if state['key'] != key:
                    state['revision'] += 1
                state['key'] = key
                state['submitted_anchor'] = anchor
                if self.preview_queue.get(source) != key:
                    self.discard_queued_preview(source)
                if key not in self.cache and key not in self.pending:
                    self.preview_queue[source] = key
                    self.preview_keys[key] = (source, generation, state['revision'])
                    self.pending.add(key)
                    self.start_next()
                state['last'], state['anchor'], state['since'] = now, text, now
                if text != anchor:
                    self.preview_refresh(PREVIEW_INTERVAL)
            elif state['key'] is None or text != state['submitted_anchor']:
                self.preview_refresh(delay)
        key = state['key']
        result = self.cache.get(key, self.partials.get(key)) if key is not None else None
        if result and key not in self.failed:
            state['shown'] = (key, result)
            state['shown_revision'] = state['revision']
        if state['shown']:
            shown_key, result = state['shown']
            if language == 'bilingual':
                result = result.removeprefix(shown_key[1] + '\n中文：')
                return text + '\n' + self.notice('Draft translation: ', '暂译：') + result
            return self.notice('Draft translation: ', '暂译：') + result
        return text if language == 'bilingual' else self.notice('Transcribing…', '正在转录…')

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
                self.batches.append(dict(record, body=body, created_at=now, updated_at=now, caption_ready=False))
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
            if (now - batch['created_at'] >= BATCH_DEADLINE
                    or (not pending and (not listening or (source not in active and now - batch['updated_at'] >= 1.2)))):
                batch['caption_ready'] = True
                self.open_batches.pop(source)
        if self.batch_timer is not None:
            self.app.root.after_cancel(self.batch_timer)
            self.batch_timer = None
        if self.open_batches and not getattr(self.app, 'closing', False):
            delay = min(min(max(.02, BATCH_DEADLINE - (now - self.batches[index]['created_at'])),
                            max(.02, 1.2 - (now - self.batches[index]['updated_at']))
                            if source not in active and not pending else BATCH_DEADLINE)
                        for source, index in self.open_batches.items())
            def flush():
                self.batch_timer = None
                self.refresh()
            self.batch_timer = self.app.root.after(max(1, int(delay * 1000)), flush)
        return [dict(batch, text=batch['text'].split('\n', 1)[0] + '\n' + batch['body']) for batch in self.batches]

    def start_next(self):
        if len(self.workers) >= 3 or getattr(self.app, 'closing', False):
            return
        if self.queue:
            # Give new speech one in three slots while older segments keep progressing.
            key = self.queue.pop() if self.dispatches % 3 == 2 else self.queue.popleft()
        else:
            active = [owner[0] for key, owner in self.preview_keys.items() if key in self.workers]
            source = next((source for source in self.preview_queue if source not in active), None)
            if len(active) >= 2 or source is None:
                return
            key = self.preview_queue.pop(source)
        self.dispatches += 1
        inputs, error = self.app.caption_models.inputs()
        if error:
            self.preview_keys.pop(key, None)
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
        english_bilingual = key[0] == 'bilingual' and not re.search(r'[\u3400-\u9fff]', key[1])
        def formatted(text):
            return key[1] + '\n中文：' + text if english_bilingual else text
        def partial(text):
            self.app.events.put(('caption_partial', (epoch, key, formatted(text))))
        def work():
            # The English source is already visible; do not generate it a second time.
            try:
                result = formatted(translate(inputs, key[1], 'zh' if english_bilingual else key[0], cancel, self.app,
                                             on_partial=partial))
                error = None
            except Exception as exc:
                result, error = '', str(exc)
                if inputs['key']:
                    error = error.replace(inputs['key'], '[KEY]')
            self.app.events.put(('caption_result', (epoch, key, result, error)))
        threading.Thread(target=work, daemon=True, name='caption-translation').start()
        self.start_next()

    def translate_now(self):
        if self.app.content_language('caption') != 'bilingual':
            return False
        with self.app.live.lock:
            records = list(self.app.live.records)
        if not records:
            return False
        self.record_batches(records)
        if not self.open_batches:
            return False
        for index in self.open_batches.values():
            self.batches[index]['caption_ready'] = True
        self.open_batches.clear()
        if self.batch_timer is not None:
            self.app.root.after_cancel(self.batch_timer)
            self.batch_timer = None
        self.refresh()
        return True

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
        if not error:
            self.update_preview(key, text)
        self.preview_keys.pop(key, None)
        self.active_key = next(iter(self.workers), None)
        self.active = self.workers.get(self.active_key)
        self.pending.discard(key)
        partial = self.partials.pop(key, '')
        if error and partial:
            partial = partial.removeprefix(key[1] + '\n中文：')
            self.cache[key] = partial + '\n' + self.notice('[Incomplete translation; change transcript language to retry]', '[翻译未完成；切换转录语言可重试]')
        else:
            self.cache[key] = text if not error else self.notice('[Translation failed; change transcript language to retry]', '[翻译失败；切换转录语言可重试]')
        if error:
            self.failed.add(key)
            self.app.status.set(self.notice('Caption translation: ', '字幕翻译：') + error)
        self.refresh()
        self.start_next()

    def receive_partial(self, result):
        epoch, key, text = result
        if epoch != self.epoch or key not in self.workers or self.workers[key].is_set() or getattr(self.app, 'closing', False):
            return
        self.partials[key] = text
        self.update_preview(key, text)
        self.refresh()

    def update_preview(self, key, text):
        owner = self.preview_keys.get(key)
        if owner is None:
            return
        source, generation, revision = owner
        state = self.previews.get(source)
        if (state is not None and (state['generation'], state['language']) == (generation, key[0])
                and revision >= state['shown_revision']):
            state['shown'] = (key, text)
            state['shown_revision'] = revision

    def reset(self):
        # Keep successful translations and the active request across language toggles.
        for key in self.failed:self.cache.pop(key,None)
        self.failed.clear()
        self.previews.clear()
        for source in list(self.preview_queue):
            self.discard_queued_preview(source)
        if self.preview_timer is not None:
            self.app.root.after_cancel(self.preview_timer)
            self.preview_timer = self.preview_due = None
        self.queue.clear()
        self.pending=set(self.workers) or ({self.active_key} if self.active else set())

    def close(self):
        self.epoch += 1
        if self.preview_timer is not None:
            self.app.root.after_cancel(self.preview_timer)
            self.preview_timer = self.preview_due = None
        if self.batch_timer is not None:
            self.app.root.after_cancel(self.batch_timer)
            self.batch_timer = None
        if self.active:
            self.active.set()
        for cancel in self.workers.values():
            cancel.set()
        self.workers.clear()
        self.partials.clear()
        self.previews.clear()
        self.preview_queue.clear()
        self.preview_keys.clear()
        self.active = None
        self.pending.clear()
        self.queue.clear()


def translate(inputs, text, language, cancel, app, on_partial=None):
    """Use the selected transport without borrowing any answer conversation."""
    from web_translation import PROVIDERS as WEB_TRANSLATORS, translate as web_translate
    if inputs['provider'] in WEB_TRANSLATORS:
        result = web_translate(inputs['provider'], text, language, cancel)
        if on_partial is not None:
            on_partial(result)
        return result
    import audio_answer as a
    import providers
    provider, model, key = inputs['provider'], inputs['model'], inputs['key']
    options = inputs['options']
    from prompt_language import for_inputs, translation_prompt
    system = translation_prompt(for_inputs(inputs),language)
    prompt = system + '\n<transcript>\n' + text + '\n</transcript>'
    pieces, usage = [], {}
    last_partial = None
    def emit(piece):
        nonlocal last_partial
        if cancel.is_set() or not piece:
            return
        pieces.append(piece)
        now = time.monotonic()
        if on_partial is not None and (last_partial is None or now - last_partial >= .1):
            last_partial = now
            on_partial(''.join(pieces))
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
