"""Measure streaming transcription cost per decoder thread count.

python tools/benchmark_asr_threads.py speech.wav [more.wav ...]

Feeds 16 kHz mono 16-bit WAV files to each local model in capture-sized blocks
(1024 frames, as audio_capture does) and reports how long decoding takes.
Lower is better; a real-time factor below 1 keeps up with live speech.
"""

from pathlib import Path
import statistics
import sys
import time
import wave

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'app'))
import app_paths  # noqa: E402,F401  (puts the bundled vendor packages on sys.path)
import numpy as np  # noqa: E402
import sherpa_onnx  # noqa: E402
from streaming_asr import ASR_MODELS, MODEL_FILES, validate_model  # noqa: E402

BLOCK = 1024
THREADS = (1, 2, 4, 8)


def recognizer(selection, threads):
    folder, kind = validate_model(ROOT, selection), ASR_MODELS[selection]
    files = MODEL_FILES[kind]
    common = dict(tokens=str(folder / 'tokens.txt'), num_threads=threads, provider='cpu')
    if kind == 'zip-zh':
        return sherpa_onnx.OnlineRecognizer.from_zipformer2_ctc(model=str(folder / files[1]), **common)
    if kind == 'zip-en':
        return sherpa_onnx.OnlineRecognizer.from_transducer(
            encoder=str(folder / files[1]), decoder=str(folder / files[2]), joiner=str(folder / files[3]), **common
        )
    return sherpa_onnx.OnlineRecognizer.from_paraformer(
        encoder=str(folder / files[1]), decoder=str(folder / files[2]), **common
    )


def run(rec, samples, rate):
    """Return (total decode seconds, per-block seconds, finalize seconds, text)."""
    stream, blocks = rec.create_stream(), []
    for start in range(0, len(samples), BLOCK):
        began = time.perf_counter()
        stream.accept_waveform(rate, samples[start : start + BLOCK])
        while rec.is_ready(stream):
            rec.decode_stream(stream)
        rec.get_result(stream)
        blocks.append(time.perf_counter() - began)
    began = time.perf_counter()
    stream.accept_waveform(rate, np.zeros(int(0.66 * rate), dtype=np.float32))
    stream.input_finished()
    while rec.is_ready(stream):
        rec.decode_stream(stream)
    text = rec.get_result(stream).strip()
    return sum(blocks), blocks, time.perf_counter() - began, text


def main(paths):
    for path in paths:
        with wave.open(path) as reader:
            assert reader.getframerate() == 16000 and reader.getnchannels() == 1 and reader.getsampwidth() == 2, path
            rate = reader.getframerate()
            samples = np.frombuffer(reader.readframes(reader.getnframes()), dtype=np.int16).astype(np.float32) / 32768
        seconds = len(samples) / rate
        print(f'\n{Path(path).name}: {seconds:.1f} s of audio')
        print(f'{"model":<12}{"threads":>8}{"RTF":>8}{"block ms p50":>14}{"p95":>8}{"max":>8}{"final ms":>10}')
        for selection in ASR_MODELS:
            for threads in THREADS:
                rec = recognizer(selection, threads)
                run(rec, samples[: rate * 2], rate)  # warm up
                rows = [run(rec, samples, rate) for _ in range(3)]
                total = statistics.median(row[0] for row in rows)
                blocks = sorted(ms for row in rows for ms in row[1])
                final = statistics.median(row[2] for row in rows)
                print(
                    f'{ASR_MODELS[selection]:<12}{threads:>8}{total / seconds:>8.3f}'
                    f'{statistics.median(blocks) * 1000:>14.2f}{blocks[int(len(blocks) * 0.95)] * 1000:>8.1f}'
                    f'{blocks[-1] * 1000:>8.1f}{final * 1000:>10.1f}'
                )


if __name__ == '__main__':
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    main(sys.argv[1:])
