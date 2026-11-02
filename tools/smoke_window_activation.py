"""Run the real WebView2 host against synthetic data and check navigation.

Run with the project's Windows Python; requires its vendor dependencies and a
desktop session. No audio, provider requests or saved user settings are used.
"""
import ctypes
from ctypes import wintypes as w
import os
from pathlib import Path
import sys
import threading
import time

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT / name) for name in ('app', 'vendor', 'tests_ui')]
from test_listen_page import FakeBridge, TOKEN
from glass_desktop import host
import webview

bridge = FakeBridge('cosmic')
done = threading.Event()
result = [1]


def watchdog():
    if not done.wait(60):
        print('FAIL: desktop navigation timed out', flush=True)
        os._exit(2)


def check():
    try:
        deadline = time.monotonic() + 20
        while not webview.windows and time.monotonic() < deadline:
            time.sleep(.05)
        window = webview.windows[0]
        assert window.events.loaded.wait(20), 'page not loaded'
        user = ctypes.WinDLL('user32')
        user.GetWindowLongPtrW.argtypes = [w.HWND, ctypes.c_int]
        user.GetWindowLongPtrW.restype = ctypes.c_ssize_t
        user.GetForegroundWindow.restype = w.HWND
        hwnd = window.native.Handle.ToInt64()
        for index in range(20):
            page = 'listen' if index % 2 == 0 else 'settings'
            topmost = index % 3 == 0
            with bridge.lock:
                bridge.state['native'].update(topmost=topmost)
                bridge.publish()
            window.evaluate_js("view('%s'); scheduleShape();" % page)
            deadline = time.monotonic() + 2
            while time.monotonic() < deadline:
                flags = user.GetWindowLongPtrW(hwnd, -20)
                guarded = bool(flags & 0x08000000)
                if guarded == (topmost and page == 'listen') and bool(flags & 8) == topmost:
                    break
                time.sleep(.02)
            else:
                raise AssertionError('activation policy not applied: ' + page)
            assert window.evaluate_js('document.body.dataset.view') == page
        def wait_policy(mouse_only):
            deadline = time.monotonic() + 2
            while bool(user.GetWindowLongPtrW(hwnd, -20) & 0x08000000) != mouse_only:
                assert time.monotonic() < deadline, 'incorrect keyboard focus policy'
                time.sleep(.02)
        # Pin changes must refresh activation even when the page/layout is unchanged.
        window.evaluate_js("view('listen'); scheduleShape();")
        for topmost in (False, True, False, True):
            with bridge.lock:
                bridge.state['native']['topmost'] = topmost
                bridge.publish()
            wait_policy(topmost)
            assert bool(user.GetWindowLongPtrW(hwnd, -20) & 8) == topmost, 'pin style did not follow toggle'
        from System import Action
        from System.Windows.Forms import Form
        reference = []
        def create_reference():
            reference.append(Form())
            reference[0].Text = 'EchoCue activation regression reference'
            reference[0].Show()
        window.native.Invoke(Action(create_reference))
        try:
            with bridge.lock:
                bridge.state['native']['topmost'] = False
                bridge.publish()
            wait_policy(False)
            other_hwnd = reference[0].Handle.ToInt64()
            for _ in range(3):
                reference[0].Invoke(Action(reference[0].Activate))
                time.sleep(.4)  # Include at least one native state-sync tick.
                assert user.GetForegroundWindow() == other_hwnd, 'unpin still prevents the other window from taking focus'
                assert not user.GetWindowLongPtrW(hwnd, -20) & 8, 'unpin retained topmost style'
                assert not user.GetWindowLongPtrW(other_hwnd, -20) & 8, 'pin leaked to the previous window'
                window.native.Invoke(Action(window.native.Activate))
                time.sleep(.4)
                assert user.GetForegroundWindow() == hwnd, 'unpinned EchoCue cannot return to foreground'
        finally:
            reference[0].Invoke(Action(reference[0].Dispose))
        with bridge.lock:
            bridge.state['native']['topmost'] = True
            bridge.publish()
        wait_policy(True)
        for menu in ('layout-menu', 'more-menu', 'layout-menu'):
            window.evaluate_js("toggleMenu('%s',true); scheduleShape();" % menu)
            time.sleep(.1)
            wait_policy(True)
        window.evaluate_js("document.querySelector('#preset-name').focus();")
        wait_policy(False)
        window.evaluate_js("document.querySelector('#more').focus(); toggleMenu('more-menu',true);")
        wait_policy(True)
        window.evaluate_js("document.querySelector('#context-toggle').click();")
        wait_policy(True)
        window.evaluate_js("document.querySelector('#context-instructions').focus();")
        deadline = time.monotonic() + 2
        while user.GetWindowLongPtrW(hwnd, -20) & 0x08000000:
            assert time.monotonic() < deadline, 'context editor cannot receive keyboard focus'
            time.sleep(.02)
        window.evaluate_js("document.querySelector('#context-toggle').click(); document.querySelector('#meeting-refinements').open = true;")
        wait_policy(True)
        window.evaluate_js("document.querySelector('#meeting-followup').focus();")
        wait_policy(False)
        window.evaluate_js("document.querySelector('#context-toggle').focus();")
        window.evaluate_js("document.querySelector('#meeting-refinements').open = false;")
        deadline = time.monotonic() + 2
        while not user.GetWindowLongPtrW(hwnd, -20) & 0x08000000:
            assert time.monotonic() < deadline, 'reading mode did not restore no-activate policy'
            time.sleep(.02)
        window.evaluate_js("view('settings');workbench.selectSection('interface-settings');")
        assert window.evaluate_js("document.querySelector('#interface-settings #listen_transparency') !== null"), 'appearance controls missing'
        window.evaluate_js("workbench.selectSection('usage-settings');")
        assert window.evaluate_js("document.querySelector('#speed-start').getClientRects().length > 0"), 'inline benchmark missing'
        window.evaluate_js("view('listen');settingsTools.openImage();")
        wait_policy(False)
        assert window.evaluate_js("!document.querySelector('#image-viewer').hidden"), 'image preview missing'
        window.evaluate_js("document.querySelector('#image-close').click();")
        wait_policy(True)
        assert len(webview.windows)==1, 'unexpected secondary WebView window'
        print('PASS: Standard navigation, menus, editing focus, pin toggles and foreground switching', flush=True)
        result[0] = 0
    except Exception as error:
        print('FAIL: ' + repr(error), flush=True)
    finally:
        with bridge.lock:
            bridge.state['closing'] = True
            bridge.publish()
        done.set()


threading.Thread(target=watchdog, daemon=True).start()
threading.Thread(target=check, daemon=True).start()
try:
    host(bridge.url.split('/#')[0], TOKEN)
finally:
    bridge.close()
sys.exit(result[0])
