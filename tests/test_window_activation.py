"""Exercise activation style updates on a real Windows HWND."""
import ctypes
from ctypes import wintypes as w
import tkinter as tk
import unittest
from unittest.mock import patch

from window_activation import MouseActivationGuard, NOACTIVATE


class MouseActivationTests(unittest.TestCase):
    def test_pin_repairs_a_stale_style_and_unpin_does_not_repeat_z_order_writes(self):
        root = tk.Tk()
        root.withdraw()
        root.update_idletasks()
        user = ctypes.WinDLL('user32')
        user.GetParent.argtypes = [w.HWND]
        user.GetParent.restype = w.HWND
        guard = MouseActivationGuard(user.GetParent(root.winfo_id()))
        try:
            guard.set_topmost(True)
            flags = guard.user.GetWindowLongPtrW(guard.hwnd, -20)
            self.assertTrue(flags & 8)
            guard.user.SetWindowLongPtrW(guard.hwnd, -20, flags & ~8)
            guard.set_topmost(True)
            self.assertTrue(guard.user.GetWindowLongPtrW(guard.hwnd, -20) & 8)
            guard.set_topmost(False)
            self.assertFalse(guard.user.GetWindowLongPtrW(guard.hwnd, -20) & 8)
            with patch.object(guard.user, 'SetWindowPos') as move:
                guard.set_topmost(False)
                move.assert_not_called()
        finally:
            root.destroy()

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
