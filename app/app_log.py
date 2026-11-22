"""Local diagnostic log with secret redaction.

Records go to data/logs/ai-listener.log (rotated, never uploaded). API keys
registered with register_secret() and common key shapes are replaced before
any record is written, so a log can be attached to a bug report.
"""

import logging
from logging.handlers import RotatingFileHandler
import re
import threading

LOGGER = 'ai_listener'
KEY_SHAPES = re.compile(
    r'(sk-[A-Za-z0-9_\-]{16,}'  # OpenAI-compatible, DeepSeek, Kimi, Qwen
    r'|AIza[0-9A-Za-z_\-]{30,}'  # Google
    r'|(?i:bearer)\s+[A-Za-z0-9._\-]{16,})'
)
_secrets = set()
_lock = threading.Lock()


def register_secret(value):
    """Redact this exact value from every later log record and redact() call."""
    if isinstance(value, str) and len(value.strip()) >= 8:
        with _lock:
            _secrets.add(value.strip())


def redact(text, *extra):
    """Replace registered secrets, the given values and key-shaped tokens with [KEY]."""
    text = str(text)
    with _lock:
        values = _secrets | {v.strip() for v in extra if isinstance(v, str) and len(v.strip()) >= 4}
    for value in sorted(values, key=len, reverse=True):
        text = text.replace(value, '[KEY]')
    return KEY_SHAPES.sub('[KEY]', text)


class RedactingFormatter(logging.Formatter):
    def format(self, record):
        return redact(super().format(record))


def get(name=''):
    return logging.getLogger(LOGGER + ('.' + name if name else ''))


def setup(folder, level=logging.INFO):
    """Attach the rotating file handler once. Returns the log path, or None if the folder is unwritable."""
    root = get()
    path = folder / 'ai-listener.log'
    if any(getattr(h, 'baseFilename', None) == str(path) for h in root.handlers):
        return path
    try:
        folder.mkdir(parents=True, exist_ok=True)
        handler = RotatingFileHandler(path, maxBytes=1_000_000, backupCount=3, encoding='utf-8', delay=True)
    except OSError:
        return None
    handler.setFormatter(RedactingFormatter('%(asctime)s %(levelname)s %(name)s [%(threadName)s] %(message)s'))
    root.addHandler(handler)
    root.setLevel(level)
    root.propagate = False
    return path


def install_hooks(tk_root=None):
    """Log uncaught exceptions from the main thread, worker threads and Tk callbacks."""
    import sys

    log = get('crash')
    previous = sys.excepthook

    def main_hook(kind, value, tb):
        log.error('Uncaught exception', exc_info=(kind, value, tb))
        previous(kind, value, tb)

    def thread_hook(args):
        if args.exc_type is not SystemExit:
            log.error(
                'Uncaught exception in thread %s',
                getattr(args.thread, 'name', '?'),
                exc_info=(args.exc_type, args.exc_value, args.exc_traceback),
            )

    sys.excepthook = main_hook
    threading.excepthook = thread_hook
    if tk_root is not None:
        tk_previous = tk_root.report_callback_exception

        def tk_hook(kind, value, tb):
            log.error('Exception in Tk callback', exc_info=(kind, value, tb))
            tk_previous(kind, value, tb)

        tk_root.report_callback_exception = tk_hook
