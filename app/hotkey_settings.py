"""Validated, persistent global shortcut preferences.

A shortcut is modifiers plus one key, or a function key on its own. An empty
value means the action has no shortcut and nothing is registered for it.
"""

import ctypes
import time
from ctypes import wintypes
import tkinter as tk

DEFAULTS = {
    'hotkey': 'Ctrl+Alt+Space',
    'topmost': 'Ctrl+Alt+T',
    'transcription': 'Ctrl+Alt+L',
    'capture_screen': 'Ctrl+Alt+S',
}
LABELS = {'hotkey': '生成回答', 'topmost': '窗口置顶', 'transcription': '开始／暂停转录', 'capture_screen': '截取屏幕'}
KEYS = {
    'Space': 32,
    'Enter': 13,
    'Escape': 27,
    'Tab': 9,
    **{chr(k): k for k in range(65, 91)},
    **{str(k): 48 + k for k in range(10)},
    **{'F' + str(k): 111 + k for k in range(1, 25)},
}
MODIFIERS = {'Ctrl': 2, 'Alt': 1, 'Shift': 4, 'Win': 8}


def parse(value):
    parts = [p.strip() for p in value.split('+')]
    lookup = {s.lower(): s for s in [*MODIFIERS, *KEYS]}
    try:
        parts = [lookup[p.lower()] for p in parts]
    except KeyError:
        raise ValueError('使用 Ctrl/Alt/Shift/Win + 字母、数字、F1–F24 或 Space。') from None
    bare_function_key = len(parts) == 1 and parts[0].startswith('F') and parts[0][1:].isdigit()
    if not bare_function_key and (
        len(parts) < 2
        or parts[-1] not in KEYS
        or any(p not in MODIFIERS for p in parts[:-1])
        or len(set(parts)) != len(parts)
    ):
        raise ValueError('快捷键必须包含修饰键和一个主键。')
    modifiers = sum(MODIFIERS[p] for p in parts[:-1])
    normalized = '+'.join([m for m in MODIFIERS if m in parts[:-1]] + [parts[-1]])
    return normalized, modifiers | 0x4000, KEYS[parts[-1]]


def validate(values):
    result = {}
    for action in DEFAULTS:
        value = values.get(action, DEFAULTS[action])
        if not isinstance(value, str):
            raise ValueError('快捷键必须包含修饰键和一个主键。')
        result[action] = parse(value)[0] if value.strip() else ''
    used = [value for value in result.values() if value]
    if len(set(used)) != len(used):
        raise ValueError('不同功能不能使用相同快捷键。')
    if result.get('passthrough') and not result.get('restore'):
        # Click-through without a way back would leave the window unreachable.
        raise ValueError('使用鼠标穿透时必须保留“恢复操作”快捷键。')
    return result


class HotkeySettings:
    def init_hotkeys(self):
        try:
            self.hotkeys = validate(self.saved.get('hotkeys', DEFAULTS))
        except (ValueError, TypeError, AttributeError):
            self.hotkeys = dict(DEFAULTS)
        self.hotkey_registration_note = tk.StringVar(value='等待快捷键注册')
        self.hotkey_thread_id = None

    def shortcut(self, action):
        return getattr(self, 'hotkeys', DEFAULTS).get(action, DEFAULTS[action])

    def apply_hotkeys(self, values):
        """Apply page edits using the existing persistence and registration thread."""
        if not isinstance(values, dict) or set(values) != set(DEFAULTS):
            raise ValueError('Invalid shortcut settings')
        values = validate(values)
        previous = dict(self.hotkeys)
        self.hotkeys = values
        if self.save_preferences() is False:
            self.hotkeys = previous
            raise ValueError('保存失败，请检查目录写入权限。')
        if self.hotkey_thread_id:
            if not ctypes.windll.user32.PostThreadMessageW(self.hotkey_thread_id, 0x8001, 0, 0):
                self.hotkey_registration_note.set('设置已保存；快捷键线程不可用，请重启程序。')
                return
        self.hotkey_registration_note.set('设置已保存，等待快捷键重新注册。')

    def listen_hotkey(self):
        api = ctypes.windll.user32
        self.hotkey_thread_id = ctypes.windll.kernel32.GetCurrentThreadId()
        registered = {}

        def register():
            for key in registered:
                api.UnregisterHotKey(None, key)
            registered.clear()
            failed = []
            snapshot = dict(self.hotkeys)
            for index, action in enumerate(DEFAULTS):
                if not snapshot[action]:
                    continue
                label, mods, key = parse(snapshot[action])
                identity = 0x4411 + index
                if api.RegisterHotKey(None, identity, mods, key):
                    registered[identity] = action
                else:
                    failed.append(LABELS[action] + ' ' + label)
            self.events.put(
                (
                    'hotkey_status',
                    '快捷键不可用：' + '；'.join(failed)
                    if failed
                    else '快捷键已应用' + (' · ' + snapshot['hotkey'] + ' 回答' if snapshot['hotkey'] else ''),
                )
            )

        try:
            register()
            msg = wintypes.MSG()
            while api.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
                if msg.message == 0x8001:
                    register()
                elif msg.message == 0x0312 and msg.wParam in registered:
                    action = registered[msg.wParam]
                    if action in ('hotkey', 'transcription'):
                        self.events.put((action, time.monotonic()))
                    elif action == 'capture_screen':
                        self.events.put(('capture_screen_hotkey', None))
                    else:
                        self.events.put(('window_hotkey', action))
        finally:
            for key in registered:
                api.UnregisterHotKey(None, key)
