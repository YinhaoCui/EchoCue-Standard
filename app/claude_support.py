"""Claude Code JSONL transport, including inline image attachments."""
import json
import os
from pathlib import Path
import queue
import shutil
import subprocess
import threading
import time
from session_support import Cancelled
from generation_context import render, checkpoint, send_images, image_indices

PROVIDER='Claude Code（本机登录）'
MODELS=['sonnet','opus','haiku']

def find_claude():
    found=shutil.which('claude.exe')
    if found:return found
    path=Path.home()/'.local/bin/claude.exe'
    if path.is_file():return str(path)
    raise RuntimeError('未找到 Claude Code，请安装并运行 claude auth login。')

def _start(root,model,effort,thinking_policy):
    args=[find_claude(),'-p','--input-format','stream-json','--output-format','stream-json',
          '--verbose','--include-partial-messages','--no-session-persistence','--safe-mode',
          '--tools','','--strict-mcp-config','--setting-sources','','--disable-slash-commands',
          '--system-prompt',Path(__file__).with_name('cli_instructions.md').read_text(encoding='utf-8')]
    if model.strip():args+=['--model',model.strip()]
    if effort not in ('自动','服务默认'):
        if effort not in ('low','medium','high','xhigh','max'):raise ValueError('无效的 Claude 思考强度')
        args+=['--effort',effort]
    folder=Path(root)/'work/claude-qa';folder.mkdir(parents=True,exist_ok=True)
    env=dict(os.environ)
    if effort not in ('自动','服务默认'): env.pop('CLAUDE_CODE_EFFORT_LEVEL',None)
    if thinking_policy=='关闭': env['MAX_THINKING_TOKENS']='0'
    elif thinking_policy=='开启':
        env.pop('CLAUDE_CODE_DISABLE_THINKING',None)
        if env.get('MAX_THINKING_TOKENS')=='0':env.pop('MAX_THINKING_TOKENS')
    process=subprocess.Popen(args,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                             creationflags=subprocess.CREATE_NO_WINDOW,cwd=folder,env=env)
    events=queue.Queue()
    def read():
        try:
            for line in process.stdout:
                try:events.put(json.loads(line))
                except (ValueError,UnicodeError):pass
        finally:events.put(None)
    def drain():
        for _ in process.stderr:pass
    threads=[threading.Thread(target=fn,daemon=True) for fn in (read,drain)]
    for thread in threads:thread.start()
    return process,events,threads,{}

_lock=threading.Lock()
_idle={}
_generation=0

def read_model_catalog(root, timeout=20):
    """Read CLI initialization metadata without submitting a user turn."""
    state=_start(root,'','自动','自动')
    process,events,_,_=state
    try:
        request={'type':'control_request','request_id':'model-catalog',
                 'request':{'subtype':'initialize'}}
        process.stdin.write((json.dumps(request)+'\n').encode('utf-8'))
        process.stdin.flush()
        deadline=time.monotonic()+timeout
        while time.monotonic()<deadline:
            try:event=events.get(timeout=min(.1,max(.001,deadline-time.monotonic())))
            except queue.Empty:continue
            if event is None:
                raise RuntimeError('Claude Code exited before returning its model catalog. Check the CLI version and login.')
            if event.get('type')!='control_response':continue
            response=event.get('response',{})
            if response.get('request_id')!='model-catalog':continue
            if response.get('subtype')!='success':
                raise RuntimeError('Claude Code rejected the model catalog request. Check the CLI version and login.')
            models=[]
            for item in response.get('response',{}).get('models',[]):
                if not isinstance(item,dict):continue
                for key in ('value','resolvedModel'):
                    value=item.get(key)
                    if isinstance(value,str) and value.strip() and value not in models:
                        models.append(value)
            if not models:raise RuntimeError('Claude Code returned an empty model catalog. You can still enter a model ID.')
            return models
        raise RuntimeError('Claude Code model catalog timed out. Check the CLI login and network.')
    finally:
        _dispose(state)

def _dispose(state):
    process,_,threads,_=state
    try:
        if process.poll() is None:process.kill()
        process.wait(timeout=5)
    except (OSError,subprocess.TimeoutExpired):pass
    for thread in threads:thread.join(timeout=1)
    for pipe in (process.stdin,process.stdout,process.stderr):
        try:pipe.close()
        except (OSError,ValueError):pass

def close_service():
    global _generation
    with _lock:
        _generation+=1;states=list(_idle.values());_idle.clear()
    for state in states:_dispose(state)

def discard_session(key):
    with _lock:states=[_idle.pop(k) for k in list(_idle) if k[-1]==key]
    for state in states:_dispose(state)

def claude_answer(root,prompt,model,cancel,on_text,on_usage=None,total_timeout=600,effort='自动',images=(),thinking_policy='自动',session_key=None):
    if cancel.is_set():raise Cancelled()
    key=(str(root),model,effort,thinking_policy,session_key) if session_key is not None else None
    with _lock:
        generation=_generation;state=_idle.pop(key,None) if key else None
    if state and state[0].poll() is not None:_dispose(state);state=None
    state=state or _start(root,model,effort,thinking_policy)
    process,events,threads,context=state
    previous=context.get('snapshot')
    content=[{'type':'text','text':render(prompt,previous)}]
    for index in image_indices(prompt,previous,len(images)):
        item=images[index]
        content.extend([{'type':'text','text':item['created']+' · '+item['title']},
                        {'type':'image','source':{'type':'base64','media_type':'image/png','data':item['data']}}])
    message={'type':'user','message':{'role':'user','content':content},'parent_tool_use_id':None}
    def write():
        try:
            process.stdin.write((json.dumps(message,ensure_ascii=False)+'\n').encode('utf-8'));process.stdin.flush()
        except (OSError,ValueError):events.put(None)
    threading.Thread(target=write,daemon=True).start()
    success=False
    started=time.monotonic();pieces=[];message_streamed=False
    def emit(text):
        if text:pieces.append(text);on_text(text)
    try:
        while True:
            if cancel.is_set():raise Cancelled()
            if time.monotonic()-started>total_timeout:raise RuntimeError('Claude Code 回答超时。')
            try:event=events.get(timeout=.1)
            except queue.Empty:continue
            if event is None:raise RuntimeError('Claude Code 输出中断，请检查登录状态和额度；已生成内容保留。')
            if event.get('parent_tool_use_id'):continue
            kind=event.get('type')
            if kind=='stream_event':
                inner=event.get('event',{})
                if inner.get('type')=='message_start':message_streamed=False
                delta=inner.get('delta',{})
                if delta.get('type')=='text_delta':
                    message_streamed=True;emit(delta.get('text',''))
            elif kind=='assistant' and not message_streamed:
                for block in event.get('message',{}).get('content',[]):
                    if block.get('type')=='text':emit(block.get('text',''))
            elif kind=='result':
                if on_usage:on_usage(event.get('usage',{}))
                if event.get('is_error') or event.get('subtype')!='success':
                    raise RuntimeError('Claude Code 未完成回答，请检查登录、额度及所选模型权限。')
                final=event.get('result','')
                current=''.join(pieces)
                if final.startswith(current):emit(final[len(current):])
                elif final and final!=current:emit('\n[最终完整回答]\n'+final)
                if not pieces:raise RuntimeError('Claude Code 未返回正文。')
                context['snapshot']=checkpoint(prompt)
                success=True
                return ''.join(pieces)
    finally:
        retained=False
        with _lock:
            if success and key and generation==_generation and not cancel.is_set() and key not in _idle and len(_idle)<8 and process.poll() is None:
                _idle[key]=state;retained=True
        if not retained:_dispose(state)
