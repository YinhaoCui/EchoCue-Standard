"""HTTP answer clients (Gemini and OpenAI-compatible APIs) and the Codex CLI entry point."""
from app_paths import WORK
import base64
import json
import os
from pathlib import Path
import re
import shutil
import urllib.error
import urllib.parse
import urllib.request
from audio_capture import wav_bytes
from model_catalog import CATALOG, describe, thinking_options
import providers
from reasoning_support import parameters as reasoning_parameters
from session_support import Cancelled, streaming_events, local_base

GEMINI_MODELS = {model: describe('Gemini', model) for model in CATALOG['Gemini']}
API_PROVIDERS = {name: {'base': providers.get(name).base, 'env': providers.get(name).env} for name in providers.API_NAMES}
for name, config in API_PROVIDERS.items():
    config['models'] = {model: describe(name, model) for model in CATALOG.get(name, {})}

def find_codex():
    found = shutil.which('codex.exe')
    if found:
        return found
    folders = Path(os.environ.get('LOCALAPPDATA', '')) / 'OpenAI' / 'Codex' / 'bin'
    matches = sorted(folders.glob('*/codex.exe'), key=lambda x: x.stat().st_mtime, reverse=True)
    if matches:
        return str(matches[0])
    raise RuntimeError('找不到 Codex CLI。请安装 Codex 并通过 codex login 登录。')

def codex_answer(transcript, instructions, cancel, on_usage=None, total_timeout=600, model="", effort="自动", on_text=None, image_paths=(), session_key=None, prompt_override=None):
    from codex_service import get_service
    if effort not in ('自动','服务默认','none','minimal','low','medium','high','xhigh','max','ultra'):
        raise ValueError('无效的 Codex 思考强度')
    from prompt_language import system_prompt
    prompt = (system_prompt('Codex') + '\nAnswer only; do not use tools or read files.\nUser requirements: ' + instructions
              + '\nASR transcript (may contain errors):\n<transcript>\n'
              + transcript + '\n</transcript>')
    return get_service(find_codex(),WORK).answer(prompt_override if prompt_override is not None else prompt,model.strip(),effort,cancel,
        on_text or (lambda text:None),on_usage,timeout=total_timeout,images=image_paths,session_key=session_key)


def sse_events(response):
    data = []
    for raw in response:
        line = raw.decode('utf-8').rstrip('\r\n')
        if not line:
            if data:
                yield json.loads('\n'.join(data))
                data.clear()
        elif line.startswith('data:'):
            value = line[5:].lstrip()
            if value != '[DONE]':
                data.append(value)
    if data:
        yield json.loads('\n'.join(data))

def gemini_http_error(exc):
    # Inspect structured error codes without echoing response bodies or credentials.
    try:
        error = json.loads(exc.read(65536)).get('error', {})
    except (ValueError, OSError, AttributeError):
        error = {}
    reasons = {detail.get('reason') for detail in error.get('details', []) if isinstance(detail, dict)}
    message = error.get('message', '').lower()
    if context_capacity_error(message): return CONTEXT_CAPACITY_MESSAGE
    if 'API_KEY_INVALID' in reasons or 'API_KEY_EXPIRED' in reasons or 'api key not valid' in message:
        return 'API Key 无效或已过期，请重新复制或创建 Key。'
    if 'API_KEY_SERVICE_BLOCKED' in reasons or 'API_KEY_HTTP_REFERRER_BLOCKED' in reasons:
        return 'Key 的应用/API 限制阻止了访问，请检查 Google 项目的 Key 限制。'
    return {
        400: '请求被拒绝；请检查模型/音频支持、地区或项目设置，不能仅据此判断 Key 无效。',
        400: '请求参数或输入类型不支持；请切换文字模式，检测模型权限并重试。',
        500: 'Google 服务内部错误，请稍后重试或换模型。',
        503: 'Google 服务繁忙，请稍后重试或换平台。',
        401: '身份验证失败，请检查 API Key。',
        403: '访问被拒绝：可能是 Key 限制、项目权限或地区限制，不一定是 Key 错误。',
        404: '模型不存在或当前项目不可用，请换一个模型。',
        429: '额度或速率限制：可能免费额度已用完，请稍后重试；这不代表 Key 无效。',
    }.get(exc.code, 'Google 服务暂时不可用，请稍后重试。')

def list_gemini_models(key):
    if not key.strip():
        raise RuntimeError('请先填写 Gemini API Key。')
    models, page, seen = set(), '', set()
    while True:
        query = urllib.parse.urlencode({'pageSize': 1000, **({'pageToken': page} if page else {})})
        request = urllib.request.Request('https://generativelanguage.googleapis.com/v1beta/models?' + query,
                                         headers={'x-goog-api-key': key.strip()})
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                payload = json.load(response)
        except urllib.error.HTTPError as exc:
            raise RuntimeError(f'HTTP {exc.code}：' + gemini_http_error(exc)) from None
        except (urllib.error.URLError, TimeoutError):
            raise RuntimeError('网络连接失败或超时，尚不能判断 Key 是否有效。') from None
        if not isinstance(payload, dict) or 'models' not in payload:
            raise RuntimeError('Google 返回的模型列表格式异常，检测未完成。')
        for model in payload['models']:
            if 'generateContent' in model.get('supportedGenerationMethods', []):
                models.add(model['name'].removeprefix('models/'))
        page = payload.get('nextPageToken', '')
        if not page:
            return models
        if page in seen or len(seen) >= 20:
            raise RuntimeError('模型列表分页异常，检测未完成。')
        seen.add(page)

def context_capacity_error(message):
    text = str(message).lower()
    return any(marker in text for marker in ('context_length_exceeded', 'maximum context length',
        'context window', 'input token count exceeds', 'input is too long', 'prompt is too long',
        'input length exceeds', 'too many tokens', '上下文长度', '输入长度超'))

CONTEXT_CAPACITY_MESSAGE = '已超过所选模型的上下文容量；本次完整记录仍保留，未自动删减。请换更大上下文模型，或自行调整要带入的资料和历史。'


def compatible_error(exc):
    try:
        payload = json.loads(exc.read(65536)).get('error', {})
        if context_capacity_error(payload): return CONTEXT_CAPACITY_MESSAGE
    except (ValueError, OSError, AttributeError): pass
    return {
        400: '请求或模型参数不支持，不能据此判断 Key 无效。',
        401: '鉴权失败：Key 无效，或 Key 与地域不匹配（千问需北京地域 Key）。',
        402: '账号余额不足，请检查余额；不代表 Key 无效。',
        403: '没有访问权限，请检查项目、Key 限制及服务开通状态。',
        404: '模型或接口不可用；若是目录检测失败，可用“测试所选模型”直接验证。',
        429: '余额/额度或速率受限，请检查账号或稍后重试，不代表 Key 无效。',
    }.get(exc.code, '服务暂时不可用，请稍后重试。')

def list_provider_models(provider, key, base=None):
    if provider == 'Gemini':
        return list_gemini_models(key)
    request = urllib.request.Request((local_base(base or API_PROVIDERS[provider]['base']) if provider == 'LM Studio' else API_PROVIDERS[provider]['base']) + '/models',
                                     headers={'Authorization': 'Bearer ' + key} if key else {})
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            payload = json.load(response)
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f'HTTP {exc.code}：' + compatible_error(exc)) from None
    except (urllib.error.URLError, TimeoutError):
        raise RuntimeError('网络连接失败或超时，尚不能判断 Key 是否有效。') from None
    if not isinstance(payload, dict) or not isinstance(payload.get('data'), list):
        raise RuntimeError('模型目录格式异常，尚不能确认 Key 状态。')
    if any(not isinstance(model, dict) or not isinstance(model.get('id'), str) or not model['id'].strip()
           for model in payload['data']):
        raise RuntimeError('模型目录格式异常，尚不能确认 Key 状态。')
    return {model['id'] for model in payload['data']}

def compatible_answer(provider, transcript, key, model, instructions, cancel, on_text, probe=False, reasoning=False, base=None, total_timeout=600, on_usage=None, max_output=16384, effort="自动", images=(), system_prompt=None):
    if not model or not re.fullmatch(r'[A-Za-z0-9._/:@+-]+', model):
        raise RuntimeError('请填写有效模型名称。')
    from prompt_language import language, choose, system_prompt as model_system
    lang=language(provider,model)
    payload = {'model': model, 'stream': True, 'max_tokens': 16 if probe else max_output,
               'messages': [{'role': 'system', 'content': choose(lang,'只回复 OK。','Reply only OK.') if probe else (system_prompt or model_system(provider,model))},
                            {'role': 'user', 'content': choose(lang,'连通性测试','Connectivity test') if probe else
                             choose(lang,'补充要求：','Requirements: ') + instructions + choose(lang,'\n音频转录资料：\n','\nTranscript data:\n') + transcript}]}
    if images and not probe:
        content=[{'type':'text','text':payload['messages'][1]['content']}]
        for item in images:
            content.extend([{'type':'text','text':item['created']+' · '+item['title']},
                            {'type':'image_url','image_url':{'url':'data:image/png;base64,'+item['data']}}])
        payload['messages'][1]['content']=content
    payload.update(thinking_options(provider, model, reasoning) if effort == '自动' else reasoning_parameters(provider,model,effort))
    if reasoning or provider == 'Kimi':
        payload['max_tokens'] = 4096 if probe else max_output
    if not probe and max_output is None: payload.pop('max_tokens', None)
    if provider == 'Meta Muse':
        payload['messages'][0]['role']='developer'
        if probe:
            payload['reasoning_effort']='minimal'
            payload['max_tokens']=1024
        if 'max_tokens' in payload:payload['max_completion_tokens']=payload.pop('max_tokens')
    if on_usage:
        payload['stream_options'] = {'include_usage': True}
    request = urllib.request.Request((local_base(base or API_PROVIDERS[provider]['base']) if provider == 'LM Studio' else API_PROVIDERS[provider]['base']) + '/chat/completions',
                                     data=json.dumps(payload).encode('utf-8'),
                                     headers={'Content-Type': 'application/json', **({'Authorization': 'Bearer ' + key} if key else {})})
    chunks = []
    finished = False
    try:
        for event in streaming_events(request, sse_events, cancel, total_timeout=total_timeout, idle_timeout=min(total_timeout, 90) if provider == 'LM Studio' else 30):
            if cancel.is_set():
                raise Cancelled()
            if event.get('error'):
                raise RuntimeError('服务返回错误，请检查当前模型和项目额度。')
            if on_usage and isinstance(event.get('usage'), dict):
                on_usage(event['usage'])
            for choice in event.get('choices', []):
                text = choice.get('delta', {}).get('content')
                if text:
                    chunks.append(text)
                    on_text(text)
                finish = choice.get('finish_reason')
                if finish: finished = True
                if finish == 'length':
                    on_text('\n[达到模型输出上限，答案尚未完成；可选择本任务点击继续回答。]')
                elif finish and finish != 'stop':
                    raise RuntimeError('服务未正常完成回答，请检查内容或更换模型。')
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f'{provider} HTTP {exc.code}：' + compatible_error(exc)) from None
    except (urllib.error.URLError, TimeoutError):
        raise RuntimeError('网络连接失败或超时，请检查网络后重试。') from None
    if not chunks:
        raise RuntimeError('模型未返回回答文字，测试不能判为成功。')
    if not finished:
        raise RuntimeError('连接已结束但未收到完成标记；答案可能不全，可继续此回答。')
    return ''.join(chunks)

def gemini_answer(pcm, key, model, instructions, cancel, on_text, *, fast=False, on_usage=None, transcript=None, total_timeout=600, max_output=16384, effort="自动", images=(), system_prompt=None):
    if not re.fullmatch(r'[A-Za-z0-9._-]+', model):
        raise RuntimeError('模型名称格式不正确。')
    from prompt_language import system_prompt as model_system
    payload = {'systemInstruction': {'parts': [{'text': system_prompt or model_system('Gemini',model)}]},
               'contents': [{'role': 'user', 'parts': [
                   {'text': 'Answer the last complete question in this audio.\nRequirements: ' + instructions},
                   {'inlineData': {'mimeType': 'audio/wav',
                                   'data': base64.b64encode(wav_bytes(pcm or b'')).decode('ascii')}}]}],
               'generationConfig': {'maxOutputTokens': max_output}}
    if max_output is None: payload['generationConfig'].pop('maxOutputTokens', None)
    if transcript is not None:
        payload['contents'][0]['parts'] = [{'text': 'Requirements: ' + instructions + '\nCurrent task and transcript data:\n' + transcript}]
    for item in images:
        payload['contents'][0]['parts'].extend([{'text':item['created']+' · '+item['title']},
            {'inlineData':{'mimeType':'image/png','data':item['data']}}])
    if fast:
        payload['contents'][0]['parts'][0]['text'] += '\nAnswer directly; cover all questions and necessary steps without omitting content for speed.'
        if model in ('gemini-2.5-flash-lite', 'gemini-2.5-flash'):
            payload['generationConfig']['thinkingConfig'] = {'thinkingBudget': 0}
        elif model == 'gemini-3.5-flash-lite':
            payload['generationConfig']['thinkingConfig'] = {'thinkingLevel': 'minimal'}
        elif model == 'gemini-3.8-flash':
            payload['generationConfig']['thinkingConfig'] = {'thinkingLevel': 'low'}
    if effort != '自动':
        payload['generationConfig'].pop('thinkingConfig',None)
        config=reasoning_parameters('Gemini',model,effort)
        if config: payload['generationConfig']['thinkingConfig']=config
    request = urllib.request.Request(
        f'https://generativelanguage.googleapis.com/v1beta/models/{model}:streamGenerateContent?alt=sse',
        data=json.dumps(payload).encode('utf-8'),
        headers={'Content-Type': 'application/json', 'x-goog-api-key': key}, method='POST')
    chunks = []
    finished = False
    try:
        for event in streaming_events(request, sse_events, cancel, total_timeout=total_timeout):
            if on_usage and isinstance(event.get('usageMetadata'), dict):
                on_usage(event['usageMetadata'])
            if cancel.is_set():
                raise Cancelled()
            if event.get('error'):
                raise RuntimeError(event['error'].get('message', 'Gemini 返回错误'))
            if event.get('promptFeedback', {}).get('blockReason'):
                raise RuntimeError('Gemini 未处理该请求：' + event['promptFeedback']['blockReason'])
            for candidate in event.get('candidates', []):
                for part in candidate.get('content', {}).get('parts', []):
                    if part.get('text') and not part.get('thought'):
                        chunks.append(part['text'])
                        on_text(part['text'])
                reason = candidate.get('finishReason')
                if reason: finished = True
                if reason and reason not in ('STOP', 'MAX_TOKENS'):
                    raise RuntimeError('Gemini 结束原因：' + reason)
                if reason == 'MAX_TOKENS':
                    on_text('\n\n[达到模型输出上限，答案尚未完成；可选择本任务点击继续回答。]')
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f'Gemini HTTP {exc.code}：' + gemini_http_error(exc)) from None
    if not chunks:
        raise RuntimeError('Gemini 未返回文字，请检查音频内容或更换模型。')
    if not finished:
        raise RuntimeError('连接已结束但未收到完成标记；答案可能不全，可继续此回答。')
    return ''.join(chunks)
