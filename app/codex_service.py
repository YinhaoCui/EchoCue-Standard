"""One Codex app-server per application, with independent concurrent answer turns."""
import atexit
import json
from pathlib import Path
import queue
import subprocess
import threading
import time
from session_support import Cancelled
from generation_context import render, checkpoint, send_images, image_indices


class CodexService:
    def __init__(self,executable,cwd,command=None):
        self.cwd=str(cwd)
        self.command=command or [executable,'app-server','--stdio',
            '-c','features.shell_tool=false','-c','web_search="disabled"',
            '-c','features.apps=false','-c','features.plugins=false','-c','features.hooks=false',
            '-c','mcp_servers={}', '-c','project_doc_max_bytes=0',
            '-c','features.skip_host_skill_discovery=true', '-c','features.memories=false',
            '-c','features.multi_agent=false', '-c','features.browser_use=false',
            '-c','features.computer_use=false', '-c','features.image_generation=false',
            '-c','features.goals=false', '-c','features.sleep_tool=false',
            '-c','model_instructions_file='+json.dumps(str(Path(__file__).with_name('cli_instructions.md')))]
        self.lock=threading.RLock();self.write_lock=threading.Lock()
        self.start_lock=threading.Lock();self.process=None;self.pending={};self.streams={}
        self.sequence=0;self.closed=False;self.launches=0
        self.sessions={};self.spares={};self.filling=set()  # model -> [(launch number, idle thread id)]

    def start(self):
        with self.start_lock:
            if self.closed:raise RuntimeError('Codex 服务已关闭。')
            if self.process and self.process.poll() is None:return
            if self.process:
                self.reader.join(timeout=1)
                for pipe in (self.process.stdin,self.process.stdout):
                    try:pipe.close()
                    except OSError:pass
            self.process=subprocess.Popen(self.command,cwd=self.cwd,stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,creationflags=subprocess.CREATE_NO_WINDOW)
            self.launches+=1
            self.reader=threading.Thread(target=self.read,args=(self.process,),daemon=True);self.reader.start()
            try:
                self.rpc('initialize',{'clientInfo':{'name':'audio_answer','title':'Audio Q&A','version':'2.0'}})
                self.send({'method':'initialized'})
            except Exception:
                self.process.kill();self.process.wait(timeout=3)
                raise

    def send(self,message):
        with self.write_lock:
            try:
                self.process.stdin.write((json.dumps(message,ensure_ascii=False)+'\n').encode('utf-8'))
                self.process.stdin.flush()
            except (OSError,ValueError,AttributeError) as exc:
                raise RuntimeError('Codex 常驻连接已中断；下一次回答将重新连接。') from exc

    def read(self,process):
        try:
            for line in process.stdout:
                try:event=json.loads(line)
                except (ValueError,UnicodeError):continue
                if 'id' in event and 'method' in event:
                    # This app never grants tool, permission, or interaction requests.
                    self.send({'id':event['id'],'error':{'code':-32601,'message':'Tools and user input are unavailable in audio Q&A.'}})
                elif 'id' in event:
                    with self.lock:target=self.pending.get(event['id'])
                    if target:target.put(event)
                else:
                    params=event.get('params',{})
                    with self.lock:target=self.streams.get(params.get('threadId'))
                    if target:target.put(event)
        finally:
            with self.lock:
                for target in list(self.pending.values())+list(self.streams.values()):target.put(None)

    def rpc(self,method,params=None,timeout=30,cancel=None):
        with self.lock:
            self.sequence+=1;identity=self.sequence
            target=self.pending[identity]=queue.Queue()
        try:
            self.send({'id':identity,'method':method,'params':params or {}})
            deadline=time.monotonic()+timeout
            while True:
                if cancel and cancel.is_set():raise Cancelled()
                if time.monotonic()>=deadline:raise RuntimeError('Codex 服务请求超时：'+method)
                try:event=target.get(timeout=.1)
                except queue.Empty:continue
                if event is None:raise RuntimeError('Codex 常驻进程已退出；已有回答内容保留。')
                if event.get('error'):raise RuntimeError(str(event['error'].get('message','Codex 请求失败')))
                return event.get('result',{})
        finally:
            with self.lock:self.pending.pop(identity,None)

    def thread_params(self,model):
        params={'cwd':self.cwd,'ephemeral':True,'approvalPolicy':'never','sandbox':'read-only',
                'developerInstructions':'Only answer the supplied question. Do not call tools or inspect files.',
                'config':{'features.shell_tool':False,'web_search':'disabled'}}
        if model:params['model']=model
        return params

    def new_thread(self,model,timeout=30):
        return self.rpc('thread/start',self.thread_params(model),timeout=timeout)['thread']['id']

    def take_spare(self,model):
        with self.lock:
            pool=self.spares.get(model) or []
            while pool:
                launch,thread=pool.pop()
                if launch==self.launches:return thread
        return None

    def prewarm(self,model='',count=1):
        """Start the process and keep idle threads ready so answers skip start-up round trips."""
        with self.lock:
            if self.closed or model in self.filling or self.sessions or self.streams:return
            self.filling.add(model)
        try:
            self.start()
            while True:
                with self.lock:
                    launch=self.launches
                    ready=sum(1 for owner,_ in self.spares.get(model,[]) if owner==launch)
                    if self.closed or ready>=count:return
                thread=self.new_thread(model)
                with self.lock:self.spares.setdefault(model,[]).append((launch,thread))
        finally:
            with self.lock:self.filling.discard(model)

    def refill(self,model):
        def run():
            try:self.prewarm(model)
            except Exception:pass
        threading.Thread(target=run,daemon=True).start()

    def answer(self,prompt,model,effort,cancel,emit,on_usage=None,timeout=600,images=(),session_key=None):
        if cancel.is_set():raise Cancelled()
        self.start()
        deadline=time.monotonic()+timeout
        if cancel.is_set():raise Cancelled()
        model=model or ''
        with self.lock:
            saved=self.sessions.pop(session_key,None) if session_key else None
        thread=saved[1] if saved and saved[0]==self.launches else None
        if thread is None:thread=self.take_spare(model)
        spare=thread is not None
        if thread is None:thread=self.new_thread(model,timeout=min(30,timeout))
        events=queue.Queue()
        with self.lock:self.streams[thread]=events
        turn=None;finished=False;successful=False;items={};order=[]
        try:
            previous=saved[2] if saved and saved[0]==self.launches and len(saved)>2 else None
            inputs=[{'type':'text','text':render(prompt,previous)}]+[{'type':'localImage','path':str(images[i])} for i in image_indices(prompt,previous,len(images))]
            params={'threadId':thread,'input':inputs}
            if effort not in ('自动','服务默认'):params['effort']=effort
            try:
                turn=self.rpc('turn/start',params,timeout=max(.1,min(30,deadline-time.monotonic())))['turn']['id']
            except RuntimeError as exc:
                if not spare or not any(message in str(exc).lower() for message in ('thread not found','unknown thread')):raise
                # The idle spare may have been discarded by the server; nothing ran yet, so use a fresh thread.
                with self.lock:self.streams.pop(thread,None)
                try:self.rpc('thread/unsubscribe',{'threadId':thread},timeout=3)
                except Exception:pass
                thread=self.new_thread(model,timeout=max(.1,min(30,deadline-time.monotonic())))
                with self.lock:self.streams[thread]=events
                params['threadId']=thread
                params['input']=[{'type':'text','text':render(prompt)}]+[{'type':'localImage','path':str(path)} for path in images]
                turn=self.rpc('turn/start',params,timeout=max(.1,min(30,deadline-time.monotonic())))['turn']['id']
            while True:
                if cancel.is_set():raise Cancelled()
                if time.monotonic()>deadline:raise RuntimeError('Codex 回答达到时限。')
                try:event=events.get(timeout=.1)
                except queue.Empty:continue
                if event is None:raise RuntimeError('Codex 输出中断，已有正文已保留。')
                method=event.get('method');data=event.get('params',{})
                if data.get('turnId',turn)!=turn:continue
                if method=='item/agentMessage/delta':
                    identity=data['itemId'];delta=data.get('delta','')
                    if identity not in items:
                        if order:emit('\n')
                        items[identity]='';order.append(identity)
                    items[identity]+=delta
                    if delta:emit(delta)
                elif method=='item/completed' and data.get('item',{}).get('type')=='agentMessage':
                    item=data['item'];identity=item['id'];text=item.get('text','');previous=items.get(identity,'')
                    if identity not in items:
                        if order:emit('\n')
                        order.append(identity)
                    if text.startswith(previous):
                        if text[len(previous):]:emit(text[len(previous):])
                    elif text:emit('\n[更新后的正文]\n'+text)
                    items[identity]=text
                elif method=='thread/tokenUsage/updated' and on_usage:
                    usage=data.get('tokenUsage',{}).get('last',{})
                    on_usage({target:usage[source] for source,target in [('inputTokens','input_tokens'),
                        ('outputTokens','output_tokens'),('totalTokens','total_tokens'),
                        ('cachedInputTokens','cached_input_tokens'),('cacheWriteInputTokens','cache_creation_input_tokens'),
                        ('reasoningOutputTokens','thinking_tokens')] if source in usage})
                elif method=='turn/completed':
                    finished=True
                    if data['turn']['status']!='completed':
                        raise RuntimeError((data['turn'].get('error') or {}).get('message','Codex 回答未完成。'))
                    answer='\n'.join(items[key] for key in order)
                    if not answer.strip():raise RuntimeError('Codex 没有返回正文。')
                    successful=True
                    return answer
        finally:
            if turn and not finished:
                try:self.rpc('turn/interrupt',{'threadId':thread,'turnId':turn},timeout=3)
                except Exception:pass
            with self.lock:self.streams.pop(thread,None)
            keep=False;retired=[]
            with self.lock:
                if session_key and successful and not cancel.is_set() and not self.closed and session_key not in self.sessions:
                    self.sessions[session_key]=(self.launches,thread,checkpoint(prompt));keep=True
                    while len(self.sessions)>8:
                        key=next(iter(self.sessions));retired.append(self.sessions.pop(key)[1])
            if not keep:retired.append(thread)
            for old_thread in retired:
                try:self.rpc('thread/unsubscribe',{'threadId':old_thread},timeout=3)
                except Exception:pass

    def close(self):
        with self.start_lock:
            self.closed=True
            process=self.process
            if process:
                if process.poll() is None:process.terminate()
                try:process.wait(timeout=3)
                except subprocess.TimeoutExpired:process.kill();process.wait(timeout=3)
                self.reader.join(timeout=1)
                for pipe in (process.stdin,process.stdout):
                    try:
                        if pipe:pipe.close()
                    except OSError:pass


_service=None
_lock=threading.Lock()

def get_service(executable,cwd):
    global _service
    with _lock:
        if _service is None or _service.closed:_service=CodexService(executable,cwd)
        return _service

def close_service():
    with _lock:
        service=_service
    if service:service.close()

atexit.register(close_service)


def discard_session(key):
    with _lock:service=_service
    if service:
        with service.lock:saved=service.sessions.pop(key,None)
        if saved:
            try:service.rpc('thread/unsubscribe',{'threadId':saved[1]},timeout=3)
            except Exception:pass
