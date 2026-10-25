"""Read Codex JSONL while the child is running, with cancellable pipe I/O."""
import json
import queue
import subprocess
import threading
import time
from session_support import Cancelled


def stream_process(args, prompt, cancel, cwd, timeout, emit, on_usage=None):
    process = subprocess.Popen(args, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               creationflags=subprocess.CREATE_NO_WINDOW, cwd=cwd)
    events = queue.Queue()
    errors = []
    def read():
        try:
            for line in process.stdout: events.put(line)
        finally: events.put(None)
    def write():
        try:
            process.stdin.write(prompt.encode('utf-8')); process.stdin.close()
        except (OSError,ValueError): pass
    def stderr():
        for line in process.stderr:
            errors.append(line)
            if len(errors)>20: errors.pop(0)
    threads = [threading.Thread(target=fn,daemon=True) for fn in (read,write,stderr)]
    for thread in threads: thread.start()
    start = time.monotonic()
    items, ordered, finished = {}, [], False
    try:
        while True:
            if cancel.is_set(): raise Cancelled()
            if time.monotonic()-start > timeout: raise RuntimeError('Codex 回答达到时限。')
            try: line=events.get(timeout=.1)
            except queue.Empty: continue
            if line is None: break
            try: event=json.loads(line)
            except (ValueError,UnicodeError): continue
            if event.get('type') in ('turn.failed','error'):
                raise RuntimeError('Codex 未正常完成回答，请检查登录和额度。')
            item=event.get('item',{})
            if event.get('type') in ('item.updated','item.completed') and item.get('type')=='agent_message':
                key=item.get('id','message')
                text=item.get('text','')
                previous=items.get(key,'')
                if key not in items:
                    if ordered and text: emit('\n')
                    ordered.append(key)
                if text.startswith(previous):
                    delta=text[len(previous):]
                    if delta: emit(delta)
                elif event['type']=='item.completed':
                    emit('\n[更新后的正文]\n'+text)
                items[key]=text
            if event.get('type')=='turn.completed':
                if on_usage: on_usage(event.get('usage',{}))
                finished=True
                break
        if not finished: raise RuntimeError('Codex 输出中断，已有正文已保留。')
        answer='\n'.join(items[key] for key in ordered)
        if not answer.strip(): raise RuntimeError('Codex 没有返回正文。')
        return answer
    finally:
        if process.poll() is None: process.kill()
        process.wait(timeout=5)
        for thread in threads: thread.join(timeout=1)
        for pipe in (process.stdin,process.stdout,process.stderr):
            if pipe: pipe.close()
