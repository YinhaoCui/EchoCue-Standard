"""Verify the actual bundled runtime, GUI toolkit, dependencies and model files."""
import hashlib
import json
import re
from pathlib import Path
import sys


def main():
    release = Path(sys.argv[1]).resolve()
    internal = release / '_internal'
    if not Path(sys.executable).resolve().is_relative_to(internal / 'runtime/python'):
        raise RuntimeError('Run this check with the bundled Python executable')
    for private in ('data', 'work', '.env', '.git'):
        if (release / private).exists() or (internal / private).exists():
            raise RuntimeError('Unexpected private payload: ' + private)
    sys.path[:0] = [str(internal / 'app'), str(internal / 'vendor')]
    import tkinter as tk
    import audio_answer
    import numpy
    import sherpa_onnx
    import pypdf
    import webrtcvad
    import webview
    import clr
    for asset in ('index.html', 'style.css', 'app.js'):
        if not (internal / 'app/web' / asset).is_file():
            raise RuntimeError('Missing desktop interface asset: ' + asset)
    web = internal / 'app/web'
    for icon in re.findall(r'/icons/([\w-]+\.svg)', (web / 'style.css').read_text(encoding='utf-8')):
        if not (web / 'icons' / icon).is_file():
            raise RuntimeError('Missing interface icon: ' + icon)
    if not (web / 'icons/LICENSE.txt').is_file():
        raise RuntimeError('Missing icon license')
    root = tk.Tk()
    root.withdraw()
    root.update()
    root.destroy()
    manifest = json.loads((release / 'asr_models.json').read_text(encoding='utf-8'))
    for name, entry in manifest.items():
        with (internal / name).open('rb') as stream:
            if hashlib.file_digest(stream, 'sha256').hexdigest() != entry['sha256']:
                raise RuntimeError('Model checksum mismatch: ' + name)
    from streaming_asr import ASR_MODELS, load_recognizer
    for name in ASR_MODELS:
        recognizer = load_recognizer(internal, name)
        del recognizer
    print('Portable runtime, Tk, WebView imports/assets and all three ASR models passed.')


if __name__ == '__main__':
    main()
