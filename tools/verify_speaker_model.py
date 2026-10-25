"""Smoke-test the real speaker model using official sherpa-onnx sample WAVs."""
from pathlib import Path
import sys
import time
import wave

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'app'))
import app_paths
import audioop
from meeting_audio import LocalSpeakers


def main():
    folder = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / 'work/speaker-verification'
    started = time.monotonic()
    speakers = LocalSpeakers(ROOT)
    labels = []
    for name in ('fangjun-sr-1.wav', 'fangjun-test-sr-1.wav', 'leijun-sr-1.wav', 'leijun-test-sr-1.wav'):
        with wave.open(str(folder / name), 'rb') as reader:
            assert reader.getsampwidth() == 2 and reader.getnchannels() == 1
            pcm = reader.readframes(reader.getnframes())
            rate = reader.getframerate()
        if rate != 16000:
            pcm, _ = audioop.ratecv(pcm, 2, 1, rate, 16000, None)
        before = time.monotonic()
        label = speakers.identify('电脑', pcm, 16000)
        labels.append(label)
        print(name, label, round(time.monotonic() - before, 3), 'seconds')
    assert labels[0] and labels[0] == labels[1], labels
    assert labels[2] and labels[2] == labels[3] and labels[2] != labels[0], labels
    print('Verified two distinct speakers across four recordings in', round(time.monotonic() - started, 3), 'seconds')


if __name__ == '__main__':
    main()
