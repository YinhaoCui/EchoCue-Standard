"""Validated, persistent global shortcut preferences."""
import ctypes
import time
from ctypes import wintypes
import tkinter as tk

DEFAULTS={'hotkey':'Ctrl+Alt+Space','topmost':'Ctrl+Alt+T','transcription':'Ctrl+Alt+L'}
LABELS={'hotkey':'生成回答','topmost':'窗口置顶','transcription':'开始／暂停转录'}
KEYS={'Space':32,'Enter':13,'Escape':27,'Tab':9,**{chr(k):k for k in range(65,91)},**{str(k):48+k for k in range(10)},**{'F'+str(k):111+k for k in range(1,25)}}
MODIFIERS={'Ctrl':2,'Alt':1,'Shift':4,'Win':8}

def parse(value):
    parts=[p.strip() for p in value.split('+')]
    lookup={s.lower():s for s in [*MODIFIERS,*KEYS]}
    try:parts=[lookup[p.lower()] for p in parts]
    except KeyError:raise ValueError('使用 Ctrl/Alt/Shift/Win + 字母、数字、F1–F24 或 Space。') from None
    if len(parts)<2 or parts[-1] not in KEYS or any(p not in MODIFIERS for p in parts[:-1]) or len(set(parts))!=len(parts):
        raise ValueError('快捷键必须包含修饰键和一个主键。')
    modifiers=sum(MODIFIERS[p] for p in parts[:-1])
    normalized='+'.join([m for m in MODIFIERS if m in parts[:-1]]+[parts[-1]])
    return normalized,modifiers|0x4000,KEYS[parts[-1]]

def validate(values):
    result={action:parse(values.get(action,DEFAULTS[action]))[0] for action in DEFAULTS}
    if len(set(result.values()))!=len(result):raise ValueError('不同功能不能使用相同快捷键。')
    return result

class HotkeySettings:
    def init_hotkeys(self):
        try:self.hotkeys=validate(self.saved.get('hotkeys',DEFAULTS))
        except (ValueError,TypeError,AttributeError):self.hotkeys=dict(DEFAULTS)
        self.hotkey_registration_note=tk.StringVar(value='等待快捷键注册')
        self.hotkey_thread_id=None

    def shortcut(self,action):return getattr(self,'hotkeys',DEFAULTS).get(action,DEFAULTS[action])

    def apply_hotkeys(self, values):
        """Apply page edits using the existing persistence and registration thread."""
        if not isinstance(values, dict) or set(values) != set(DEFAULTS):
            raise ValueError('Invalid shortcut settings')
        values=validate(values)
        previous=dict(self.hotkeys);self.hotkeys=values
        if self.save_preferences() is False:
            self.hotkeys=previous
            raise ValueError('保存失败，请检查目录写入权限。')
        if self.hotkey_thread_id:
            if not ctypes.windll.user32.PostThreadMessageW(self.hotkey_thread_id,0x8001,0,0):
                self.hotkey_registration_note.set('设置已保存；快捷键线程不可用，请重启程序。')
                return
        self.hotkey_registration_note.set('设置已保存，等待快捷键重新注册。')

    def listen_hotkey(self):
        api=ctypes.windll.user32
        self.hotkey_thread_id=ctypes.windll.kernel32.GetCurrentThreadId()
        registered={}
        def register():
            for key in registered:api.UnregisterHotKey(None,key)
            registered.clear();failed=[]
            snapshot=dict(self.hotkeys)
            for index,action in enumerate(DEFAULTS):
                label,mods,key=parse(snapshot[action]);identity=0x4411+index
                if api.RegisterHotKey(None,identity,mods,key):registered[identity]=action
                else:failed.append(LABELS[action]+' '+label)
            self.events.put(('hotkey_status','快捷键不可用：'+'；'.join(failed) if failed else '快捷键已应用 · '+snapshot['hotkey']+' 回答'))
        try:
            register();msg=wintypes.MSG()
            while api.GetMessageW(ctypes.byref(msg),None,0,0)>0:
                if msg.message==0x8001:register()
                elif msg.message==0x0312 and msg.wParam in registered:
                    action=registered[msg.wParam]
                    self.events.put((action,time.monotonic()) if action in ('hotkey','transcription') else ('window_hotkey',action))
        finally:
            for key in registered:api.UnregisterHotKey(None,key)
