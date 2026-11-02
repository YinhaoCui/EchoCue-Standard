"""DLX HTTP client and an optional application-owned local worker."""
import atexit
import json
import os
import subprocess
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

PROVIDER = 'DLX'
DEFAULT_URL = 'http://127.0.0.1:1188/translate'
_process = None
_token = None
_lock = threading.Lock()


def endpoint(value):
    if not isinstance(value, str):
        raise ValueError('DLX 地址必须是文本。')
    value = value.strip().rstrip('/')
    try:
        url = urllib.parse.urlsplit(value)
        _ = url.port
        if (url.scheme not in ('http', 'https') or not url.hostname or url.username or url.password
                or url.query or url.fragment or any(ord(c) < 33 for c in value)
                or (url.scheme == 'http' and url.hostname not in ('localhost', '127.0.0.1', '::1'))):
            raise ValueError()
    except ValueError:
        raise ValueError('DLX 地址需使用本机 HTTP 或 HTTPS，不能包含账号、令牌或查询参数。') from None
    return value if url.path.endswith('/translate') else value + '/translate'


def _stop_owned():
    global _process, _token
    process, _process, _token = _process, None, None
    if process is not None and process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=2)


def stop():
    with _lock:
        _stop_owned()


atexit.register(stop)


def ensure_local(url, token, cancel):
    """Only auto-start our bundled service at its default loopback address."""
    global _process, _token
    if url != DEFAULT_URL:
        return
    from app_paths import ROOT
    from session_support import Cancelled
    local_http = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    def healthy():
        try:
            with local_http.open('http://127.0.0.1:1188/', timeout=.4) as response:
                value = json.load(response)
            return any(name in value.get('message', '').lower() for name in ('dlx', 'deeplx', 'deepl free api'))
        except Exception:
            return False
    with _lock:
        if cancel.is_set():
            raise Cancelled()
        if _process is not None and _token != token:
            _stop_owned()
        if healthy():
            return
        executable = ROOT / 'runtime' / 'dlx' / 'deeplx.exe'
        if not executable.is_file():
            raise RuntimeError('缺少内置 DLX 组件；请安装包含 DLX 的版本，或填写已启动服务的地址。')
        if _process is None or _process.poll() is not None:
            env = dict(os.environ, IP='127.0.0.1', PORT='1188', TOKEN=token)
            env.pop('DL_SESSION', None)
            _process = subprocess.Popen([str(executable), '-ip', '127.0.0.1', '-port', '1188'],
                                        cwd=str(executable.parent), env=env, stdin=subprocess.DEVNULL,
                                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                        creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            _token = token
        deadline = time.monotonic() + 4
        while time.monotonic() < deadline:
            if cancel.is_set():
                raise Cancelled()
            if healthy():
                return
            if _process.poll() is not None:
                break
            cancel.wait(.1)
    raise RuntimeError('内置 DLX 启动失败，请检查本机 1188 端口或使用自定义服务地址。')


def chunks(text):
    start, units = 0, 0
    for index, char in enumerate(text):
        size = 2 if ord(char) > 0xFFFF else 1
        if units + size > 1500:
            yield text[start:index]
            start, units = index, 0
        units += size
    if start < len(text):
        yield text[start:]


def translate(text, language, url, token, cancel):
    from session_support import streaming_events, Cancelled
    if cancel.is_set():
        raise Cancelled()
    url = endpoint(url)
    ensure_local(url, token, cancel)
    def one(target):
        result = []
        for part in chunks(text):
            if not part.strip():
                result.append(part)
                continue
            request = urllib.request.Request(url, data=json.dumps(dict(text=part, source_lang='auto', target_lang=target)).encode(),
                                             headers={'Content-Type': 'application/json',
                                                      **({'Authorization': 'Bearer ' + token} if token else {})})
            def parse(response):
                yield json.load(response)
            try:
                payload = list(streaming_events(request, parse, cancel, total_timeout=30, idle_timeout=25))[-1]
                if payload.get('code') != 200 or not isinstance(payload.get('data'), str) or not payload['data'].strip():
                    raise RuntimeError('DLX 翻译失败，请检查服务日志或上游额度。')
                result.append(payload['data'])
            except urllib.error.HTTPError as exc:
                raise RuntimeError('DLX HTTP ' + str(exc.code) + '：请检查访问令牌、服务状态或限流。') from None
            except Cancelled:
                raise
            except RuntimeError:
                raise
            except Exception:
                raise RuntimeError('DLX 请求失败，请检查服务地址、连接和返回格式。') from None
        return '\n'.join(result)
    if language == 'bilingual':
        return '中文：' + one('ZH') + '\nEnglish: ' + one('EN')
    if language not in ('zh', 'en'):
        raise ValueError('不支持的翻译语言。')
    return one('ZH' if language == 'zh' else 'EN')
