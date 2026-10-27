"""Pause-based local speech segmentation; never silently drops queued speech."""
from collections import deque
import audioop
import queue
import threading
import time
from session_support import Cancelled

def append_transcript(current, previous_source, record, separator=' '):
    source = (record.get('source'), record['speaker']) if record.get('speaker') else record.get('source')
    body = record.get('body')
    if body is None:
        body = record['text'].split('\n', 1)[-1]
    if current and source == previous_source:
        return current + separator + body, source
    return current + ('\n\n' if current else '') + record['text'], source

class LiveTranscriber:
    def __init__(self, transcribe, emit, rate=16000, silence=.65, max_seconds=15, threshold=100):
        self.transcribe, self.emit = transcribe, emit
        self.rate, self.silence, self.max_seconds, self.threshold = rate, silence, max_seconds, threshold
        self.lock = threading.RLock()
        self.condition = threading.Condition(self.lock)
        self.sources, self.records = {}, []
        self.drafts = {}
        self.submitted = self.completed = 0
        self.queue = queue.Queue()
        self.cancel = threading.Event()
        self.language, self.model = 'auto', None
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def configure(self, language, model):
        with self.lock:
            self.language, self.model = language, model

    def feed(self, source, pcm):
        if self.cancel.is_set():
            return
        with self.lock:
            state = self.sources.setdefault(source, {'pre': b'', 'data': bytearray(), 'quiet': 0, 'stamp': '', 'generation': 0, 'preview_bytes': 0})
            voiced = audioop.rms(pcm, 2) >= self.threshold
            if not state['data']:
                if not voiced:
                    state['pre'] = (state['pre'] + pcm)[-int(self.rate*.3)*2:]
                    return
                state['data'].extend(state['pre'])
                state['pre'] = b''
                state['stamp'] = time.strftime('%H:%M:%S')
                state['generation'] += 1
                state['preview_bytes'] = 0
            state['data'].extend(pcm)
            state['quiet'] = 0 if voiced else state['quiet'] + len(pcm)
            if state['quiet'] >= self.rate*2*self.silence or len(state['data']) >= self.rate*2*self.max_seconds:
                self._submit(source, state)
            elif len(state['data']) - state['preview_bytes'] >= self.rate*2:
                state['preview_bytes'] = len(state['data'])
                # Replace pending previews, never queue obsolete partial hypotheses.
                self.drafts[source] = (state['generation'], bytes(state['data']), self.language, self.model)

    def _submit(self, source, state):
        if not state['data']:
            return
        self.submitted += 1
        self.queue.put((self.submitted, source, state['stamp'], bytes(state['data']), self.language, self.model, state['generation']))
        self.drafts.pop(source, None)
        state['data'].clear(); state['quiet'] = 0
        self.emit('live_pending', self.submitted-self.completed)

    def flush(self):
        with self.lock:
            for source, state in self.sources.items():
                self._submit(source, state)
            return self.submitted

    def snapshot(self, target, cancel):
        with self.condition:
            while self.completed < target:
                if cancel.is_set() or self.cancel.is_set():
                    raise Cancelled()
                self.condition.wait(.1)
            text, source = '', None
            for record in self.records:
                if record['sequence'] <= target:
                    text, source = append_transcript(text, source, record)
            return text

    def _run(self):
        while not self.cancel.is_set():
            try:
                sequence, source, stamp, pcm, language, model, generation = self.queue.get(timeout=.1)
            except queue.Empty:
                with self.lock:
                    preview = next(iter(self.drafts.items()), None)
                    if preview: self.drafts.pop(preview[0])
                if preview:
                    source, (generation, pcm, language, model) = preview
                    try:
                        text = self.transcribe(pcm, language, self.cancel, model)
                        with self.lock:
                            state = self.sources[source]
                            if state['generation'] == generation and state['data']:
                                self.emit('live_partial', {'source':source, 'generation':generation, 'text':text})
                    except Cancelled: return
                    except Exception: pass  # Final transcription reports actionable errors.
                continue
            try:
                body = self.transcribe(pcm, language, self.cancel, model)
                text = f'[{stamp} {source}]\n{body}'
                ok = True
            except Cancelled:
                return
            except Exception as exc:
                body = f'[转录失败] {exc}'
                text, ok = f'[{stamp} {source}]\n{body}', False
            with self.condition:
                record = {'sequence': sequence, 'text': text, 'body': body, 'ok': ok, 'source':source, 'generation':generation}
                self.records.append(record)
                self.completed = sequence
                self.condition.notify_all()
            self.emit('live_segment', record)
            self.emit('live_pending', self.submitted-self.completed)

    def close(self):
        self.cancel.set()
        with self.condition:
            self.condition.notify_all()
