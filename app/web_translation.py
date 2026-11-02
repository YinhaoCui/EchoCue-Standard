"""Built-in anonymous translation clients; protocol references in docs/TRANSLATION_SERVICES.md."""
import json
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

DEEPL = 'DeepL (built-in)'
GOOGLE = 'Google Translate (built-in)'
MICROSOFT = 'Microsoft Translator (built-in)'
PROVIDERS = (DEEPL, GOOGLE, MICROSOFT)
_instance = str(uuid.uuid4())
_session = str(uuid.uuid4())
_cooldown = {}
_lock = threading.Lock()


def _request(provider, request, cancel):
    from session_support import streaming_events, Cancelled
    if cancel.is_set():
        raise Cancelled()
    with _lock:
        remaining = _cooldown.get(provider, 0) - time.monotonic()
    if remaining > 0:
        raise RuntimeError(f'{provider}：服务限流，请约 {int(remaining) + 1} 秒后重试或切换翻译平台。')
    def parse(response):
        raw = response.read(1024 * 1024 + 1)
        if len(raw) > 1024 * 1024:
            raise ValueError('response too large')
        yield json.loads(raw)
    try:
        return list(streaming_events(request, parse, cancel, total_timeout=30, idle_timeout=25))[-1]
    except urllib.error.HTTPError as exc:
        if exc.code == 429:
            try:
                seconds = max(60, int(exc.headers.get('Retry-After', '60')))
            except (ValueError, TypeError, AttributeError):
                seconds = 60
            with _lock:
                _cooldown[provider] = time.monotonic() + seconds
            raise RuntimeError(f'{provider} HTTP 429：服务限流，暂停请求，请稍后重试或切换翻译平台。') from None
        raise RuntimeError(f'{provider} HTTP {exc.code}：网页翻译接口不可用，请稍后重试或切换翻译平台。') from None
    except Cancelled:
        raise
    except Exception:
        raise RuntimeError(f'{provider}：翻译请求失败，请检查网络或切换翻译平台。') from None


def _one(provider, text, language, cancel):
    headers = {'Content-Type': 'application/json', 'Accept': 'application/json'}
    if provider == GOOGLE:
        url = 'https://translate.googleapis.com/translate_a/single'
        body = urllib.parse.urlencode(dict(client='gtx', sl='auto', tl='zh-CN' if language == 'zh' else 'en',
                                           dt='t', q=text)).encode('utf-8')
        headers['Content-Type'] = 'application/x-www-form-urlencoded; charset=utf-8'
    elif provider == MICROSOFT:
        query = urllib.parse.urlencode(dict(to='zh-Hans' if language == 'zh' else 'en', isEnterpriseClient='false'))
        url = 'https://edge.microsoft.com/translate/translatetext?' + query
        body = json.dumps([text]).encode('utf-8')
    else:
        # DLX's oneshot payload/profile, carried over the application's normal HTTPS transport.
        # Attribution and upstream MIT license are bundled in docs/DLX_LICENSE.txt.
        url = 'https://oneshot-free.www.deepl.com/v1/translate'
        headers.update({'Authorization': 'None', 'User-Agent': 'DeepL/26.52 CFNetwork/3826.600.41 Darwin/25.0.0',
                        'x-app-os-version': '26.0', 'x-app-instance-id': _instance, 'x-app-session-id': _session})
        body = json.dumps(dict(text=[text], target_lang='zh-Hans' if language == 'zh' else 'en-US',
                               usage_type='translate', app_information=dict(os='iOS', os_version='26.0',
                               app_version='26.52', app_build='5443737', instance_id=_instance))).encode('utf-8')
    request = urllib.request.Request(url, data=body, headers=headers)
    payload = _request(provider, request, cancel)
    try:
        if provider == GOOGLE:
            if not isinstance(payload, list) or not payload or not isinstance(payload[0], list):
                raise ValueError()
            if not all(isinstance(piece, list) and piece for piece in payload[0]):
                raise ValueError()
            parts = [piece[0] for piece in payload[0]]
            if not parts or not all(isinstance(piece, str) for piece in parts):
                raise ValueError()
            result = ''.join(parts)
        elif provider == MICROSOFT:
            if not isinstance(payload, list) or len(payload) != 1 or len(payload[0]['translations']) != 1:
                raise ValueError()
            result = payload[0]['translations'][0]['text']
        else:
            if len(payload['translations']) != 1:
                raise ValueError()
            result = payload['translations'][0]['text']
        if not isinstance(result, str) or not result.strip():
            raise ValueError()
        return result
    except (KeyError, IndexError, TypeError, ValueError):
        raise RuntimeError(f'{provider}：翻译返回内容无效，接口可能已变化。') from None


def translate(provider, text, language, cancel):
    from dlx_translation import chunks
    from session_support import Cancelled
    if cancel.is_set():
        raise Cancelled()
    if provider not in PROVIDERS or language not in ('zh', 'en', 'bilingual'):
        raise ValueError('不支持的翻译平台或语言。')
    def one(target):
        result = []
        for part in chunks(text):
            if cancel.is_set():
                raise Cancelled()
            result.append(_one(provider, part, target, cancel) if part.strip() else part)
        return '\n'.join(result)
    if language == 'bilingual':
        return '中文：' + one('zh') + '\nEnglish: ' + one('en')
    return one(language)
