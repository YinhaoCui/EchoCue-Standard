"""Local speaker embeddings and conservative suppression of duplicated playback."""
from collections import deque
from pathlib import Path
import threading
import time

import numpy as np

MODEL = 'runtime/asr/speaker/campplus.onnx'


class EchoSuppressor:
    """Only remove near-identical echo; preserve uncertain and double-talk frames."""
    def __init__(self, rate=16000):
        self.rate = rate
        self.lock = threading.Lock()
        self.blocks = deque()

    def reset(self):
        with self.lock:
            self.blocks.clear()

    def process(self, source, pcm, enabled, now=None):
        if not enabled:
            return pcm
        now = time.monotonic() if now is None else now
        values = np.frombuffer(pcm, dtype=np.int16).astype(np.float32)
        with self.lock:
            while self.blocks and self.blocks[0][0] < now - .5:
                self.blocks.popleft()
            if source == '电脑':
                self.blocks.append((now, values))
                return pcm
            reference = np.concatenate([v for _, v in self.blocks]) if self.blocks else np.empty(0)
        if len(values) < 160 or len(reference) < len(values):
            return pcm
        energy = float(values @ values)
        if energy < len(values) * 100 ** 2:
            return pcm
        # Search at most half a second of playback; each callback stays bounded.
        dots = np.correlate(reference, values, mode='valid')
        sums = np.concatenate(([0.0], np.cumsum(reference.astype(np.float64) ** 2)))
        energies = sums[len(values):] - sums[:-len(values)]
        scores = dots / np.sqrt(np.maximum(energies * energy, 1))
        index = int(np.argmax(scores))
        gain = float(dots[index] / max(energies[index], 1))
        if scores[index] < .995 or not .02 <= gain <= 2:
            return pcm
        residual = values - gain * reference[index:index + len(values)]
        if float(residual @ residual) > energy * .01:
            return pcm  # independent near-end speech must survive
        return bytes(len(pcm))


class LocalSpeakers:
    """One dominant voice per finalized segment; embeddings never leave memory."""
    def __init__(self, root, first=1, extractor=None):
        if extractor is None:
            import sherpa_onnx
            path = Path(root) / MODEL
            if not path.is_file():
                raise RuntimeError('Speaker model missing. Run tools/setup_streaming.cmd.')
            config = sherpa_onnx.SpeakerEmbeddingExtractorConfig(
                model=str(path), num_threads=1, provider='cpu')
            if not config.validate():
                raise RuntimeError('Invalid local speaker model')
            extractor = sherpa_onnx.SpeakerEmbeddingExtractor(config)
        self.extractor = extractor
        self.voices = {}
        self.next_id = first

    def identify(self, source, pcm, rate):
        data = np.frombuffer(pcm, dtype=np.int16).astype(np.float32) / 32768
        if len(data) < rate or float(data @ data) < len(data) * .002 ** 2:
            return None
        stream = self.extractor.create_stream()
        stream.accept_waveform(sample_rate=rate, waveform=data)
        stream.input_finished()
        if not self.extractor.is_ready(stream):
            return None
        vector = np.asarray(self.extractor.compute(stream), dtype=np.float32)
        norm = float(np.linalg.norm(vector))
        if not np.isfinite(norm) or norm <= 0:
            return None
        vector = vector / norm
        known = self.voices.setdefault(source, [])
        ranked = sorted(((float(v @ vector), label, v) for label, v in known), key=lambda x: x[0], reverse=True)
        if ranked and ranked[0][0] >= .55:
            if len(ranked) > 1 and ranked[0][0] - ranked[1][0] < .08:
                return None
            return ranked[0][1]
        if (ranked and ranked[0][0] > .40) or len(known) >= 12:
            return None
        label = f'Speaker {self.next_id}'
        self.next_id += 1
        known.append((label, vector))
        return label
