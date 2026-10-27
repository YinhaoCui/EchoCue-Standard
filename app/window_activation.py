"""Keep mouse-only desktop controls from activating over a fullscreen app."""
import ctypes
from ctypes import wintypes as w


NOACTIVATE = 0x08000000


class MouseActivationGuard:
    """Update on the HWND's UI thread, without replacing its window procedure."""

    def __init__(self, hwnd):
        self.hwnd = hwnd
        self.enabled = False
        self.user = ctypes.WinDLL('user32', use_last_error=True)
        self.user.GetWindowLongPtrW.argtypes = [w.HWND, ctypes.c_int]
        self.user.GetWindowLongPtrW.restype = ctypes.c_ssize_t
        self.user.SetWindowLongPtrW.argtypes = [w.HWND, ctypes.c_int, ctypes.c_ssize_t]
        self.user.SetWindowLongPtrW.restype = ctypes.c_ssize_t

    def set_enabled(self, enabled):
        # A Python WndProc callback deadlocks when a WinForms worker holds the
        # GIL while waiting for the UI thread. Let Windows enforce the style.
        flags = self.user.GetWindowLongPtrW(self.hwnd, -20)
        if bool(flags & NOACTIVATE) == bool(enabled):
            self.enabled = bool(enabled)
            return
        ctypes.set_last_error(0)
        previous = self.user.SetWindowLongPtrW(
            self.hwnd, -20, flags | NOACTIVATE if enabled else flags & ~NOACTIVATE)
        if not previous and ctypes.get_last_error():
            raise ctypes.WinError(ctypes.get_last_error())
        self.enabled = bool(enabled)
