"""Screenshot text for providers with no image input, using Windows' built-in OCR.

Text is cached per image, so each screenshot is read once per run of the app.
"""
import base64
import hashlib
from pathlib import Path
import subprocess
import tempfile
import threading

SCRIPT = Path(__file__).with_name('ocr_image.ps1')
_cache, _lock = {}, threading.Lock()


def _read(data, work):
    with tempfile.TemporaryDirectory(dir=work) as folder:
        path = Path(folder) / 'shot.png'
        path.write_bytes(data)
        result = subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass',
                                 '-File', str(SCRIPT), '-Path', str(path)],
                                capture_output=True, timeout=60, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    if result.returncode != 0:
        raise RuntimeError('Windows OCR could not read a screenshot.')
    return result.stdout.decode('utf-8', errors='replace').strip()


def screenshot_text(images, work, reader=None):
    """Reference text listing what OCR read from each screenshot, in order."""
    parts = []
    for number, item in enumerate(images, 1):
        data = base64.b64decode(item['data'], validate=True)
        digest = hashlib.sha256(data).hexdigest()
        with _lock:
            text = _cache.get(digest)
        if text is None:
            text = (reader or _read)(data, work)
            with _lock:
                _cache[digest] = text
        title = f"{item.get('created', '')} · {item.get('title', 'Screenshot')}".strip(' ·')
        parts.append(f'[Screenshot {number}: {title}]\n' + (text or '(no text found)'))
    return '\n\n'.join(parts)
