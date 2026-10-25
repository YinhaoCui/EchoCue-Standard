import ctypes
from pathlib import Path
import runpy
import sys
import os
try:
    try:
        ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
    except Exception:
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except Exception:
            pass
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    entry = 'glass_desktop.py'
    runpy.run_path(str(Path(__file__).with_name(entry)), run_name='__main__')
except Exception as exc:
    import tkinter as tk
    from tkinter import messagebox
    root=tk.Tk(); root.withdraw()
    messagebox.showerror('启动失败', '启动遇到 '+type(exc).__name__+'：'+str(exc)+'。请确认已完整解压安装包，并保留 _internal 文件夹。', parent=root)
    root.destroy()
