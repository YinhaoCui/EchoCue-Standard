"""Keep mouse-only desktop controls from activating over a fullscreen app."""
import ctypes
from ctypes import wintypes as w


NOACTIVATE = 0x08000000


class MouseActivationGuard:
    """Update on the HWND's UI thread, without replacing its window procedure."""

    def __init__(self, hwnd):
        self.hwnd = hwnd
        self.enabled = False
        self.topmost = None
        self.user = ctypes.WinDLL('user32', use_last_error=True)
        self.user.GetWindowLongPtrW.argtypes = [w.HWND, ctypes.c_int]
        self.user.GetWindowLongPtrW.restype = ctypes.c_ssize_t
        self.user.SetWindowLongPtrW.argtypes = [w.HWND, ctypes.c_int, ctypes.c_ssize_t]
        self.user.SetWindowLongPtrW.restype = ctypes.c_ssize_t
        self.user.SetWindowPos.argtypes = [w.HWND, w.HWND, ctypes.c_int, ctypes.c_int,
                                          ctypes.c_int, ctypes.c_int, w.UINT]
        self.user.SetWindowPos.restype = w.BOOL

    def set_topmost(self, enabled):
        # WinForms can report TopMost=True while the HWND is still non-topmost.
        flags = self.user.GetWindowLongPtrW(self.hwnd, -20)
        if self.topmost == bool(enabled) and bool(flags & 8) == bool(enabled):
            return
        if enabled:
            # A stale extended-style bit can disagree with the native z-order band.
            if not self.user.SetWindowPos(self.hwnd, w.HWND(-2), 0, 0, 0, 0, 0x13):
                raise ctypes.WinError(ctypes.get_last_error())
        if not self.user.SetWindowPos(self.hwnd, w.HWND(-1 if enabled else -2),
                                      0, 0, 0, 0, 0x13):
            raise ctypes.WinError(ctypes.get_last_error())
        self.topmost = bool(enabled)

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
