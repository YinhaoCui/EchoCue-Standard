"""Explicit window capture and image attachments; no automatic image collection."""
import base64
import ctypes
from ctypes import wintypes
from contextlib import contextmanager
import os
from pathlib import Path
import subprocess
import threading
import time
import tkinter as tk
from tkinter import ttk
import uuid


def foreground_window():
    api=ctypes.WinDLL('user32',use_last_error=True)
    api.GetForegroundWindow.restype=wintypes.HWND
    api.GetWindowThreadProcessId.argtypes=[wintypes.HWND,ctypes.POINTER(wintypes.DWORD)]
    api.GetWindowTextW.argtypes=[wintypes.HWND,wintypes.LPWSTR,ctypes.c_int]
    handle=api.GetForegroundWindow()
    process=wintypes.DWORD()
    api.GetWindowThreadProcessId(handle,ctypes.byref(process))
    title=ctypes.create_unicode_buffer(1024)
    api.GetWindowTextW(handle,title,len(title))
    if handle and process.value != os.getpid():
        return {'handle':int(handle),'process':process.value,'title':title.value or '未命名窗口'}


def capture_window(target):
    helper=Path(__file__).with_name('capture_window.ps1')
    executable=Path(os.environ['SystemRoot'])/'System32/WindowsPowerShell/v1.0/powershell.exe'
    try:
        result=subprocess.run([str(executable),'-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass',
                               '-File',str(helper),'-WindowHandle',str(target['handle']),
                               '-WindowProcess',str(target['process'])],capture_output=True,timeout=12,
                              creationflags=subprocess.CREATE_NO_WINDOW)
    except subprocess.TimeoutExpired:
        raise RuntimeError('截图超时，请检查目标窗口是否无响应。') from None
    if result.returncode:
        raise RuntimeError('无法截取该窗口：请保持窗口打开且未最小化；受保护窗口可能无法截图。')
    data=result.stdout.decode('ascii').strip()
    if not base64.b64decode(data,validate=True).startswith(b'\x89PNG\r\n\x1a\n'):
        raise RuntimeError('截图数据无效，请重试。')
    return dict(id=uuid.uuid4().hex,title=target['title'],created=time.strftime('%Y-%m-%d %H:%M:%S'),data=data)


@contextmanager
def image_files(images, folder):
    paths=[]
    try:
        for item in images:
            path=Path(folder)/('attached-'+uuid.uuid4().hex+'.png')
            paths.append(path)
            path.write_bytes(base64.b64decode(item['data'],validate=True))
        yield [str(path) for path in paths]
    finally:
        for path in paths:path.unlink(missing_ok=True)


class Screenshots:
    def init_screenshots(self):
        self.capture_target=None
        self.screenshot_busy=False
        self.screenshot_note=tk.StringVar()
        self.update_screenshot_note()
        self.watch_foreground()

    def watch_foreground(self):
        if self.closed:return
        try:
            target=foreground_window()
            if target:self.capture_target=target
        finally:
            self.root.after(200,self.watch_foreground)

    def update_screenshot_note(self):
        self.screenshot_note.set(f'上下文截图 {len(self.context_images)} 张 · 准备上下文或回答时发送')
        manager=getattr(self,'screenshot_manager_window',None)
        if manager is not None and manager.winfo_exists():
            self.refresh_screenshot_manager()

    def capture_screenshot(self):
        if self.screenshot_busy or getattr(self,'closing',False):return
        target=foreground_window() or self.capture_target
        if not target:
            self.status.set('请先切到需要截图的窗口，再返回点击“截取活动窗口”。');return
        self.screenshot_busy=True
        revision=self.context_version
        self.status.set('正在截取：'+target['title'])
        def run():
            try: result=capture_window(target);error=''
            except Exception as exc: result=None;error=str(exc)
            self.events.put(('screenshot',(revision,result,error)))
        threading.Thread(target=run,daemon=True).start()

    def receive_screenshot(self,payload):
        revision,item,error=payload
        self.screenshot_busy=False
        if error:self.status.set(error);return
        if revision!=self.context_version:
            self.status.set('上下文已变更，本次截图未加入，请重新截图。');return
        if any(existing['data']==item['data'] for existing in self.context_images):
            self.status.set('截图内容未变化，已复用现有截图。');return
        self.context_images.append(item)
        self.context_changed()
        self.update_screenshot_note();self.save_session()
        self.status.set('截图已加入上下文：'+item['title']+'；可点击“查看截图”检查。')

    def screenshot_manager(self):
        manager=getattr(self,'screenshot_manager_window',None)
        if manager is not None and manager.winfo_exists():
            manager.lift();return
        win=tk.Toplevel(self.root);win.title('上下文截图');win.geometry('850x650')
        self.screenshot_manager_window=win
        ttk.Label(win,text='点击截图查看；移除后不再用于新的回答。截图中如有黑屏，请移除后重试。').pack(anchor='w',padx=10,pady=8)
        listing=tk.Listbox(win,height=5);listing.pack(fill='x',padx=10)
        canvas=tk.Canvas(win,background='#101824');canvas.pack(fill='both',expand=True,padx=10,pady=8)
        def refresh():
            listing.delete(0,'end')
            canvas.delete('all')
            for item in self.context_images:listing.insert('end',item['created']+' · '+item['title'])
        self.refresh_screenshot_manager=refresh
        def preview(_=None):
            if not listing.curselection():return
            item=self.context_images[listing.curselection()[0]]
            full=tk.PhotoImage(data=item['data'],master=win)
            scale=max(1,(full.width()+max(1,canvas.winfo_width())-1)//max(1,canvas.winfo_width()),
                      (full.height()+max(1,canvas.winfo_height())-1)//max(1,canvas.winfo_height()))
            canvas.picture=full.subsample(scale);canvas.delete('all');canvas.create_image(0,0,anchor='nw',image=canvas.picture)
        def remove():
            if not listing.curselection():return
            self.context_images.pop(listing.curselection()[0]);self.context_changed()
            self.update_screenshot_note();self.save_session();canvas.delete('all');refresh()
        ttk.Button(win,text='移除所选截图',command=remove).pack(pady=5)
        listing.bind('<<ListboxSelect>>',preview);canvas.bind('<Configure>',preview)
        refresh()
        if self.context_images:listing.selection_set(0);win.after_idle(preview)
