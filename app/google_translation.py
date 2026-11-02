"""Official Cloud Translation Basic API, independent of answer providers."""
import html
import json
import urllib.error
import urllib.request

PROVIDER = 'Google Cloud Translation'


def translate(text, language, key, cancel):
    from session_support import streaming_events, Cancelled
    if cancel.is_set():
        raise Cancelled()
    if not key:
        raise ValueError('请配置 Google Cloud Translation API Key。')
    def one(target):
        request = urllib.request.Request(
            'https://translation.googleapis.com/language/translate/v2',
            data=json.dumps(dict(q=text, target=target, format='text', model='nmt')).encode('utf-8'),
            headers={'Content-Type': 'application/json; charset=utf-8', 'X-Goog-Api-Key': key})
        def parse(response):
            yield json.load(response)
        try:
            payload = list(streaming_events(request, parse, cancel, total_timeout=30, idle_timeout=25))[-1]
            value = payload['data']['translations'][0]['translatedText']
            if not isinstance(value, str) or not value.strip():
                raise ValueError()
            if cancel.is_set():
                raise Cancelled()
            return html.unescape(value)
        except urllib.error.HTTPError as exc:
            messages = {400: '请检查 API Key 和翻译请求。', 401: 'API Key 无效。',
                        403: '请检查 API Key 权限、Cloud Translation API 是否启用及结算设置。',
                        429: '请求过多或额度不足，请稍后重试。'}
            raise RuntimeError('Google Translation HTTP ' + str(exc.code) + '：' +
                               messages.get(exc.code, '服务暂时不可用，请稍后重试。')) from None
        except Cancelled:
            raise
        except (KeyError, IndexError, TypeError, ValueError, StopIteration):
            raise RuntimeError('Google Translation 返回的翻译内容无效。') from None
        except Exception:
            raise RuntimeError('Google Translation 请求失败，请检查网络后重试。') from None
    if language == 'bilingual':
        return '中文：' + one('zh-CN') + '\nEnglish: ' + one('en')
    if language not in ('zh', 'en'):
        raise ValueError('不支持的翻译语言。')
    return one('zh-CN' if language == 'zh' else 'en')
