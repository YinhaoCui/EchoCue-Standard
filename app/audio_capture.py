"""System-audio and microphone capture, and one-shot whisper transcription."""
from app_paths import ROOT, WORK
import audioop
from collections import deque
import io
import os
from pathlib import Path
import subprocess
import threading
import time
import uuid
import wave
import pyaudiowpatch as pa
from session_support import Cancelled

RATE = 16000

def wav_bytes(pcm):
    output = io.BytesIO()
    with wave.open(output, 'wb') as writer:
        writer.setnchannels(1)
        writer.setsampwidth(2)
        writer.setframerate(RATE)
        writer.writeframes(pcm)
    return output.getvalue()

class AudioBuffer:
    def __init__(self, seconds=120):
        self.seconds = seconds
        self.blocks = deque()
        self.lock = threading.Lock()

    def append(self, pcm, now=None):
        now = time.monotonic() if now is None else now
        with self.lock:
            self.blocks.append((now, pcm))
            while self.blocks and self.blocks[0][0] < now - self.seconds:
                self.blocks.popleft()

    def snapshot(self, seconds, now=None):
        now = time.monotonic() if now is None else now
        with self.lock:
            blocks = [data for stamp, data in self.blocks if stamp >= now - seconds]
        return b''.join(blocks)[-int(seconds * RATE * 2):]

    def clear(self):
        with self.lock:
            self.blocks.clear()

class Capture:
    def __init__(self):
        self.audio = pa.PyAudio()
        self.buffer = AudioBuffer()
        self.stream = None
        self.on_pcm = None
        self.level = 0
        self.error = ''
        self.dropped = 0

    def devices(self):
        return list(self.audio.get_loopback_device_info_generator())

    def start(self, device):
        self.stop()
        self.buffer.clear()
        self.error = ''
        self.dropped = 0
        channels = min(2, int(device['maxInputChannels']))
        source_rate = int(device['defaultSampleRate'])
        state = None

        def receive(data, count, timing, flags):
            nonlocal state
            try:
                if flags:
                    self.dropped += 1
                if channels == 2:
                    data = audioop.tomono(data, 2, 0.5, 0.5)
                data, state = audioop.ratecv(data, 2, 1, source_rate, RATE, state)
                self.level = min(100, audioop.rms(data, 2) / 80)
                self.buffer.append(data)
                if self.on_pcm:
                    self.on_pcm(data)
                return (None, pa.paContinue)
            except Exception as exc:
                self.error = str(exc)
                return (None, pa.paAbort)

        self.stream = self.audio.open(format=pa.paInt16, channels=channels,
                                      rate=source_rate, input=True,
                                      input_device_index=int(device['index']),
                                      frames_per_buffer=1024, stream_callback=receive)

    def active(self):
        try:
            return self.stream is not None and self.stream.is_active()
        except (OSError, RuntimeError):
            self.error = '音频设备已断开，请重新选择设备。'
            return False

    def stop(self):
        stream, self.stream = self.stream, None
        if stream:
            try:
                stream.stop_stream()
            except (OSError, RuntimeError):
                pass
            try:
                stream.close()
            except (OSError, RuntimeError):
                pass
        self.level = 0

    def close(self):
        try:
            self.stop()
        finally:
            self.audio.terminate()

def run_process(args, cancel, *, stdin=None, timeout=180):
    proc = subprocess.Popen(args, stdin=subprocess.PIPE if stdin is not None else subprocess.DEVNULL,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            creationflags=subprocess.CREATE_NO_WINDOW, cwd=WORK)
    deadline = time.monotonic() + timeout
    sent = False
    try:
        while True:
            if cancel.is_set():
                raise Cancelled()
            if time.monotonic() > deadline:
                raise RuntimeError('处理超时。请缩短音频时长后重试。')
            try:
                out, err = proc.communicate(input=stdin if not sent else None, timeout=0.15)
                break
            except subprocess.TimeoutExpired:
                sent = True
        if proc.returncode:
            raise RuntimeError(err.decode('utf-8', errors='replace')[-1800:] or '子程序运行失败')
        return out.decode('utf-8', errors='replace')
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.communicate()

def transcribe(pcm, language, cancel, model_path=None):
    executables = list((ROOT / 'runtime').rglob('whisper-cli.exe'))
    model = Path(model_path) if model_path else ROOT / 'runtime' / 'ggml-base.bin'
    if not executables or not model.exists():
        raise RuntimeError('缺少本地识别模型，请先运行 setup.cmd。')
    stem = WORK / ('clip-' + uuid.uuid4().hex)
    audio = stem.with_suffix('.wav')
    text = stem.with_suffix('.txt')
    try:
        audio.write_bytes(wav_bytes(pcm))
        run_process([str(executables[0]), '-m', str(model), '-f', str(audio),
                     '-l', language, '-otxt', '-of', str(stem), '-nt',
                     '-t', str(min(8, os.cpu_count() or 4))], cancel)
        result = text.read_text(encoding='utf-8-sig').strip()
        if not result:
            raise RuntimeError('没有识别到语音，请检查音频来源和输入音量。')
        return result
    finally:
        audio.unlink(missing_ok=True)
        text.unlink(missing_ok=True)
