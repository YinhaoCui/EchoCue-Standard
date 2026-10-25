"""LM Studio native chat with capability-checked reasoning and isolated branches."""
import json
import threading
import time
import urllib.error
import urllib.request
from session_support import local_base, streaming_events, Cancelled
from generation_context import render, checkpoint, send_images, image_indices

_lock = threading.Lock()
_models = {}
_sessions = {}


def capabilities(base, key):
    endpoint = local_base(base).removesuffix('/v1') + '/api/v1'
    cache_key = (endpoint, key)
    with _lock:
        cached = _models.get(cache_key)
    if cached and time.monotonic() - cached[0] < 30: return endpoint, cached[1]
    headers = {'Authorization': 'Bearer ' + key} if key else {}
    try:
        with urllib.request.urlopen(urllib.request.Request(endpoint+'/models',headers=headers),timeout=3) as response:
            data = json.load(response)
    except urllib.error.HTTPError as exc:
        if exc.code not in (404,405,501): raise
        data = None
    rows = data.get('models') if isinstance(data,dict) else None
    with _lock: _models[cache_key] = (time.monotonic(),rows)
    return endpoint, rows


def answer(base,key,model,prompt,system,cancel,on_text,on_usage,timeout,max_output,policy='自动',session_key=None,images=()):
    from audio_answer import sse_events
    endpoint, rows = capabilities(base,key)
    if rows is None: return False
    if cancel.is_set(): raise Cancelled()
    selected = next((r for r in rows if r.get('key')==model or any(i.get('id')==model for i in r.get('loaded_instances',[]))),{})
    allowed = selected.get('capabilities',{}).get('reasoning',{}).get('allowed_options',[])
    payload = {'model':model,'input':prompt,'system_prompt':system,'stream':True,'store':session_key is not None}
    if max_output is not None: payload['max_output_tokens']=max_output
    preference = ('off','low') if policy=='关闭' else (('on','medium','high','low') if policy=='开启' else ())
    setting = next((v for v in preference if v in allowed),None)
    if setting: payload['reasoning']=setting
    if images:
        payload['input']=[{'type':'text','content':prompt}]+[{'type':'image','data_url':'data:image/png;base64,'+i['data']} for i in images]
    slot=(endpoint,key,model,policy,session_key) if session_key is not None else None
    with _lock: previous=_sessions.pop(slot,None) if slot else None
    prior=previous[1] if isinstance(previous,tuple) else None
    if previous: payload['previous_response_id']=previous[0] if isinstance(previous,tuple) else previous
    text=render(prompt,prior)
    images=[images[i] for i in image_indices(prompt,prior,len(images))]
    payload['input']=([{'type':'text','content':text}]+[{'type':'image','data_url':'data:image/png;base64,'+i['data']} for i in images]) if images and send_images(prompt,prior) else text
    headers={'Content-Type':'application/json'}
    if key: headers['Authorization']='Bearer '+key
    request=urllib.request.Request(endpoint+'/chat',data=json.dumps(payload).encode('utf-8'),headers=headers)
    pieces=[]
    for event in streaming_events(request,sse_events,cancel,total_timeout=timeout,idle_timeout=min(timeout,90)):
        kind=event.get('type')
        if kind=='error': raise RuntimeError(str(event.get('error',{}).get('message','LM Studio 请求失败')))
        if kind=='message.delta':
            text=event.get('content','');pieces.append(text);on_text(text)
        if kind=='chat.end':
            result=event.get('result',{})
            if on_usage: on_usage(result.get('stats',{}))
            final=''.join(i.get('content','') for i in result.get('output',[]) if i.get('type')=='message')
            streamed=''.join(pieces)
            if final.startswith(streamed):
                if final[len(streamed):]:on_text(final[len(streamed):])
            elif final: on_text('\n[服务返回的完整最终版本]\n'+final)
            if not (streamed or final): raise RuntimeError('LM Studio 未返回文字答案。')
            if cancel.is_set(): raise Cancelled()
            response_id=result.get('response_id','')
            if slot and response_id.startswith('resp_'):
                with _lock:
                    if len(_sessions)>=32: _sessions.pop(next(iter(_sessions)))
                    _sessions.setdefault(slot,(response_id,checkpoint(prompt)))
            return True
    raise RuntimeError('LM Studio 流提前结束；已有内容已保留。')


def discard_session(key):
    with _lock:
        for slot in list(_sessions):
            if slot[-1]==key:_sessions.pop(slot,None)
