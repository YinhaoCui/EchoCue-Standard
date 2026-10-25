"""Resident streaming recognizers with independent state for each audio source."""
import audioop
from pathlib import Path
import queue
import time

from live_transcription import LiveTranscriber
from speech_activity import SpeechActivity, apply_terms

ASR_MODELS = {
    '英文 · Zipformer': 'zip-en',
    '中文 · Zipformer': 'zip-zh',
    '中英混合 · Paraformer': 'paraformer',
}
DEFAULT_ASR = '中英混合 · Paraformer'
MODEL_FILES = {
    'zip-en': ['tokens.txt', 'encoder-epoch-99-avg-1-chunk-16-left-64.int8.onnx',
               'decoder-epoch-99-avg-1-chunk-16-left-64.int8.onnx',
               'joiner-epoch-99-avg-1-chunk-16-left-64.int8.onnx'],
    'zip-zh': ['tokens.txt', 'model.int8.onnx'],
    'paraformer': ['tokens.txt', 'encoder.int8.onnx', 'decoder.int8.onnx'],
}


def validate_model(root, selection):
    if selection not in ASR_MODELS:
        raise ValueError('请选择英文、中文或中英混合转录模型。')
    kind = ASR_MODELS[selection]
    folder = Path(root) / 'runtime' / 'asr' / kind
    missing = [name for name in MODEL_FILES[kind] if not (folder / name).is_file()]
    if missing:
        raise RuntimeError('本地转录模型不完整，请运行 setup_streaming.cmd：' + ', '.join(missing))
    return folder


def load_recognizer(root, selection):
    import sherpa_onnx
    folder = validate_model(root, selection)
    kind = ASR_MODELS[selection]
    common = dict(tokens=str(folder / 'tokens.txt'), num_threads=4, provider='cpu')
    files = MODEL_FILES[kind]
    if kind == 'zip-zh':
        return sherpa_onnx.OnlineRecognizer.from_zipformer2_ctc(model=str(folder / files[1]), **common)
    if kind == 'zip-en':
        return sherpa_onnx.OnlineRecognizer.from_transducer(
            encoder=str(folder / files[1]), decoder=str(folder / files[2]), joiner=str(folder / files[3]), **common)
    return sherpa_onnx.OnlineRecognizer.from_paraformer(
        encoder=str(folder / files[1]), decoder=str(folder / files[2]), **common)


class StreamingLiveTranscriber(LiveTranscriber):
    def __init__(self, root, emit, factory=None, rate=16000, silence=.65, max_seconds=30, threshold=100):
        try:
            import numpy
        except ImportError as exc:
            raise RuntimeError('缺少本地转录依赖，请运行 setup_streaming.cmd。') from exc
        self.root = Path(root)
        self.factory = factory or (lambda selection: load_recognizer(self.root, selection))
        self.engine = DEFAULT_ASR
        self.np = numpy
        self.terms = ''
        self.queued_bytes = 0
        self.processing_lag = 0.0
        self.last_processed = time.monotonic()
        self.last_voice = time.monotonic()
        self.speaker_note = ''
        super().__init__(None, emit, rate, silence, max_seconds, threshold)

    def configure_speakers(self, enabled):
        with self.lock:
            self.flush()
            first = max((int(r['speaker'].split()[-1]) for r in self.records if r.get('speaker')), default=0) + 1
            self.queue.put(('speakers', bool(enabled), first))

    def configure(self, selection):
        if selection not in ASR_MODELS:
            raise ValueError('未知转录模型：' + str(selection))
        with self.lock:
            # Finalize all old-source streams before preparing the new model.
            self.flush()
            for state in self.sources.values():
                state['pre'] = b''
            self.engine = selection
            self.queue.put(('prepare', selection))

    def preload(self,selection):
        if not self.cancel.is_set():self.queue.put(('prepare',selection))

    def feed(self, source, pcm):
        if self.cancel.is_set() or not pcm:
            return
        with self.lock:
            if source not in self.sources:
                self.sources[source] = dict(pre=b'', data=0, quiet=0, generation=0, detector=SpeechActivity(self.rate))
            state = self.sources[source]
            voiced = state['detector'].voiced(pcm)
            if voiced:
                self.last_voice = time.monotonic()
            if not state['data']:
                if not voiced:
                    state['pre'] = (state['pre'] + pcm)[-int(self.rate * .3) * 2:]
                    return
                state['generation'] += 1
                state['stamp'] = time.strftime('%H:%M:%S')
                self.queue.put(('start', source, state['generation'], self.engine, self.terms))
                pcm = state['pre'] + pcm
                state['pre'] = b''
            state['data'] += len(pcm)
            state['quiet'] = 0 if voiced else state['quiet'] + len(pcm)
            self.queued_bytes += len(pcm)
            self.queue.put(('audio', source, pcm, time.monotonic()))
            if state['quiet'] >= self.rate * 2 * self.silence or state['data'] >= self.rate * 2 * self.max_seconds:
                self._submit(source, state)

    def _submit(self, source, state):
        if not state['data']:
            return
        self.submitted += 1
        self.queue.put(('end', source, self.submitted, state['stamp'], state['generation']))
        state['data'] = state['quiet'] = 0
        self.emit('live_pending', self.submitted - self.completed)

    def _run(self):
        np = self.np
        recognizers, streams = {}, {}
        speakers = None

        def get_recognizer(selection):
            if selection not in recognizers:
                self.emit('live_status', '正在加载本地转录模型：' + selection)
                recognizers[selection] = self.factory(selection)
                self.emit('live_status', '转录模型已就绪：' + selection)
            return recognizers[selection]

        def decode(state):
            rec, stream = state['recognizer'], state['stream']
            while rec.is_ready(stream) and not self.cancel.is_set():
                rec.decode_stream(stream)
            return rec.get_result(stream).strip()

        while not self.cancel.is_set():
            try:
                item = self.queue.get(timeout=.1)
            except queue.Empty:
                continue
            action = item[0]
            if action == 'speakers':
                speakers = None
                self.speaker_note = ''
                if item[1]:
                    try:
                        from meeting_audio import LocalSpeakers
                        speakers = LocalSpeakers(self.root, item[2])
                        self.speaker_note = 'Local speaker labels enabled / 本地说话人标注已开启'
                    except Exception as exc:
                        self.speaker_note = 'Speaker labels unavailable / 说话人标注不可用: ' + str(exc)
                        self.emit('live_status', self.speaker_note)
                continue
            if action == 'prepare':
                try:
                    get_recognizer(item[1])
                except Exception as exc:
                    self.emit('live_status', '转录模型加载失败：' + str(exc))
                continue
            source = item[1]
            if action == 'start':
                state = streams[source] = dict(generation=item[2], text='', error=None, terms=item[4], pcm=bytearray())
                try:
                    state['recognizer'] = get_recognizer(item[3])
                    state['stream'] = state['recognizer'].create_stream()
                except Exception as exc:
                    state['error'] = str(exc)
                continue
            state = streams[source]
            if action == 'audio':
                with self.lock:
                    self.queued_bytes = max(0, self.queued_bytes - len(item[2]))
                    self.processing_lag = time.monotonic() - item[3]
                    self.last_processed = time.monotonic()
                if state['error']:
                    continue
                try:
                    if speakers is not None:
                        state['pcm'].extend(item[2])
                    data = np.frombuffer(item[2], dtype=np.int16).astype(np.float32) / 32768
                    state['stream'].accept_waveform(self.rate, data)
                    text = apply_terms(decode(state), state['terms'])
                    if text and text != state['text']:
                        state['text'] = text
                        self.emit('live_partial', dict(source=source, generation=state['generation'], text=text))
                except Exception as exc:
                    state['error'] = str(exc)
                continue
            _, _, sequence, stamp, generation = item
            if not state['error']:
                try:
                    state['stream'].accept_waveform(self.rate, np.zeros(int(.66 * self.rate), dtype=np.float32))
                    state['stream'].input_finished()
                    state['text'] = apply_terms(decode(state), state['terms'])
                except Exception as exc:
                    state['error'] = str(exc)
            body = state['text']
            if state['error']:
                body += ('\n' if body else '') + '[转录失败] ' + state['error']
            record = dict(sequence=sequence, source=source, generation=generation,
                          text=f'[{stamp} {source}]\n{body}', body=body, ok=not bool(state['error']))
            if speakers is not None and not state['error'] and body.strip():
                try:
                    speaker = speakers.identify(source, state['pcm'], self.rate)
                    if speaker:
                        record.update(speaker=speaker, text=f'[{stamp} {source} · {speaker}]\n{body}')
                except Exception as exc:
                    self.speaker_note = 'Speaker identification failed / 说话人识别失败: ' + str(exc)
                    self.emit('live_status', self.speaker_note)
            with self.condition:
                self.records.append(record)
                self.completed = sequence
                self.condition.notify_all()
            self.emit('live_segment', record)
            self.emit('live_pending', self.submitted - self.completed)
            del streams[source]
