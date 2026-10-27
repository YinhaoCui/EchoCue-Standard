"""Exercise activation style updates on a real Windows HWND."""
import ctypes
from ctypes import wintypes as w
import tkinter as tk
import unittest

from window_activation import MouseActivationGuard, NOACTIVATE


class MouseActivationTests(unittest.TestCase):
    def test_mouse_clicks_keep_focus_policy_and_editing_can_restore_activation(self):
        root = tk.Tk()
        root.withdraw()
        button = tk.Button(root, text='Answer')
        button.pack()
        root.update_idletasks()
        user = ctypes.WinDLL('user32')
        user.GetParent.argtypes = [w.HWND]
        user.GetParent.restype = w.HWND
        hwnd = user.GetParent(root.winfo_id())
        guard = MouseActivationGuard(hwnd)
        baseline = guard.user.GetWindowLongPtrW(hwnd, -20)
        try:
            guard.set_enabled(True)
            self.assertTrue(guard.user.GetWindowLongPtrW(hwnd, -20) & NOACTIVATE)
            self.assertEqual(guard.user.GetWindowLongPtrW(hwnd, -20) & ~NOACTIVATE, baseline & ~NOACTIVATE)
            guard.set_enabled(False)
            self.assertFalse(guard.user.GetWindowLongPtrW(hwnd, -20) & NOACTIVATE)
            self.assertEqual(guard.user.GetWindowLongPtrW(hwnd, -20), baseline & ~NOACTIVATE)
        finally:
            root.destroy()
