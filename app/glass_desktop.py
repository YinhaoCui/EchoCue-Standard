"""Windows desktop host for EchoCue Standard."""
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import threading
import urllib.request
from app_paths import ROOT

MIN_SIZE = (760, 560)


def resize_size(width, height):
    """Validate a requested logical window size and keep it above the minimum."""
    try:
        width, height = float(width), float(height)
    except (TypeError, ValueError):
        return None
    if not (math.isfinite(width) and math.isfinite(height)):
        return None
    return (int(min(10000, max(MIN_SIZE[0], width))), int(min(10000, max(MIN_SIZE[1], height))))


def resize_rect(width, height, left=None, top=None):
    size = resize_size(width, height)
    if size is None:
        return None
    if left is None and top is None:
        return size
    try:
        origin = float(left), float(top)
    except (ValueError, TypeError):
        return None
    if not all(math.isfinite(value) and abs(value) <= 100000 for value in origin):
        return None
    return (*size, *(int(value) for value in origin))


def host(url, token):
    import webview
    class API:
        def drag(self):
            """Use the native Windows move loop for either toolbar."""
            import ctypes
            from ctypes import wintypes
            from System import Action

            def move():
                user = ctypes.WinDLL('user32', use_last_error=True)
                user.ReleaseCapture.argtypes = []
                user.SendMessageW.argtypes = [wintypes.HWND, wintypes.UINT,
                                             wintypes.WPARAM, wintypes.LPARAM]
                user.SendMessageW.restype = ctypes.c_ssize_t
                user.ReleaseCapture()
                user.SendMessageW(window.native.Handle.ToInt64(), 0x00A1, 2, 0)

            window.native.Invoke(Action(move))

        def resize(self, width, height, left=None, top=None):
            """Resize any edge; left/top drags also update the window origin."""
            if window.maximized:
                return False
            rect = resize_rect(width, height, left, top)
            if rect is None:
                return False
            window.resize(*rect[:2])
            if len(rect) == 4:
                window.move(*rect[2:])
            return True

        def bounds(self):
            return dict(width=window.width, height=window.height, left=window.x, top=window.y)

        def minimize(self):
            window.minimize()

        def maximize(self):
            if window.maximized:
                window.restore()
            else:
                window.maximize()

        def close(self):
            window.destroy()

    window = webview.create_window('EchoCue Standard', url + '/#' + token, js_api=API(),
                                   width=1180, height=840, min_size=MIN_SIZE, frameless=True,
                                   easy_drag=False, background_color='#18212a', text_select=True)
    stopped = threading.Event()
    tray = [None]
    latest = [{}]

    def fetch(path='/state', body=None):
        request = urllib.request.Request(url + path, data=body,
            headers={'X-Listener-Token': token, 'Content-Type': 'application/json'})
        with urllib.request.urlopen(request, timeout=3) as response:
            return json.load(response)

    def send(payload):
        def run():
            try:
                fetch('/command', json.dumps(payload).encode('utf-8'))
            except (OSError, ValueError):
                pass
        threading.Thread(target=run, daemon=True).start()

    def show_window(view=None):
        window.show()
        window.restore()
        if view:
            threading.Thread(target=lambda: window.evaluate_js(
                "document.querySelector('button[data-view=%s]').click()" % json.dumps(view)), daemon=True).start()

    def pick(key):
        if key in ('show', 'listen', 'settings'):
            show_window(None if key == 'show' else key)
        elif key in ('start', 'pause'):
            send({'action': 'listen'})
        elif key == 'topmost':
            send({'action': 'window', 'value': key})
        elif key == 'quit':
            window.destroy()

    def closed():
        stopped.set()
        try:
            fetch('/command', b'{"action":"close"}')
        except (OSError, ValueError):
            pass
        if tray[0]:
            tray[0].dispose()
    window.events.closed += closed

    def sync():
        from System import Action
        from System.Drawing import Icon
        from tray_menu import Tray
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('EchoCue-Standard.Desktop')
        def initialize():
            window.native.Icon = Icon(str(ROOT / 'app/assets/echocue.ico'))
            tray[0] = Tray(ROOT / 'app/assets/echocue.ico', lambda: latest[0], pick, show_window)
        window.native.Invoke(Action(initialize))
        failures = 0
        while not stopped.wait(.25):
            try:
                reply = fetch()
                state = reply.get('state', reply)
                latest[0] = state
                if state.get('closing'):
                    window.destroy()
                    return
                window.on_top = bool(state.get('native', {}).get('topmost'))
                failures = 0
            except (OSError, ValueError):
                failures += 1
                if failures >= 20:
                    window.destroy()
                    return
    webview.start(sync, gui='edgechromium', private_mode=True)


def main():
    import tkinter as tk
    import audio_answer as a
    from glass_bridge import GlassBridge
    root = tk.Tk()
    app = a.App(root)
    root.iconbitmap(str(ROOT / 'app/assets/echocue.ico'))
    bridge = GlassBridge(app)

    def window_hotkey(action):
        if action == 'topmost':
            bridge.window_state['topmost'] = not bridge.window_state['topmost']

    app.window_hotkey = window_hotkey
    root.withdraw()
    bridge.tick()
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')
    # Avoid putting the session bearer token in process arguments or a disk file.
    env['ECHOCUE_WEB_TOKEN'] = bridge.token
    from app_paths import WORK
    log = (WORK / 'glass-host.log').open('w', encoding='utf-8')
    child = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), '--host', bridge.url],
                             env=env, stdout=log, stderr=log, creationflags=0x08000000)
    import screenshot_context
    original_foreground = screenshot_context.foreground_window
    last_target = [None]

    def foreground():
        target = original_foreground()
        if target and target['process'] != child.pid:
            last_target[0] = target
        return last_target[0]

    screenshot_context.foreground_window = foreground

    def check_host():
        if app.closed or getattr(app, 'closing', False):
            return
        code = child.poll()
        if code is not None:
            from tkinter import messagebox
            messagebox.showerror('EchoCue', 'The desktop interface stopped. See work/glass-host.log for details.', parent=root)
            app.close()
            return
        root.after(1000, check_host)

    root.after(1500, check_host)
    try:
        root.mainloop()
    finally:
        bridge.close()
        if child.poll() is None:
            child.terminate()
        log.close()


if __name__ == '__main__':
    if '--host' in sys.argv:
        host(sys.argv[-1], os.environ.pop('ECHOCUE_WEB_TOKEN'))
    else:
        main()
