"""System tray icon with a right-click menu of window and session settings.

``menu_entries`` is the plain menu model, so it can be tested without Windows.
``Tray`` turns it into a WinForms NotifyIcon; build it on the window's UI thread.
Menu icons are glyphs from the Windows icon font, drawn into small bitmaps.
"""

# Segoe Fluent Icons (Windows 11) / Segoe MDL2 Assets (Windows 10) code points.
GLYPHS = {
    'quit': '\uE7E8',
    'topmost': '\uE718',
    'show': '\uE8A7', 'listen': '\uE720', 'settings': '\uE713', 'start': '\uE768', 'pause': '\uE769',
}

TEXT = {
    'quit': ('Quit EchoCue Standard', '退出 EchoCue Standard'),
    'show': ('Show window', '显示窗口'), 'listen': ('Open Listen', '打开监听页'),
    'settings': ('Open Settings', '打开设置'), 'start': ('Start transcription', '开始转录'),
    'pause': ('Pause transcription', '暂停转录'), 'topmost': ('Pin on top', '窗口置顶'),
}


def menu_entries(state):
    """[(key, label, glyph, checked)] for a /state snapshot; None marks a separator."""
    state = state if isinstance(state, dict) else {}
    native = state.get('native') if isinstance(state.get('native'), dict) else {}
    zh = state.get('language') == 'zh'

    def item(key, checked=None):
        return key, TEXT[key][1 if zh else 0], GLYPHS[key], checked

    listen_key = 'pause' if state.get('listening') else 'start'
    return [
        item('show'), item('listen'), item('settings'), None,
        item(listen_key), None,
        item('topmost', bool(native.get('topmost'))), None,
        item('quit'),
    ]


class Tray:
    """A NotifyIcon whose menu is rebuilt from the latest state each time it opens."""

    def __init__(self, icon_path, current_state, on_pick, on_click):
        from System.Drawing import Icon, Size
        from System.Windows.Forms import ContextMenuStrip, NotifyIcon
        self.current_state, self.on_pick, self.images = current_state, on_pick, {}
        self.menu = ContextMenuStrip()
        self.size = max(16, round(16 * self.menu.DeviceDpi / 96))  # sharp icons at 125-200% scaling
        self.menu.ImageScalingSize = Size(self.size, self.size)
        self.menu.Opening += lambda sender, event: self.rebuild()
        self.rebuild()
        self.icon = NotifyIcon()
        self.icon.Icon = Icon(str(icon_path))
        self.icon.Text = 'EchoCue'
        self.icon.ContextMenuStrip = self.menu
        self.icon.MouseClick += lambda sender, event: on_click() if str(event.Button) == 'Left' else None
        self.icon.Visible = True

    def glyph(self, char, on=False):
        """A bitmap of one icon-font glyph, cached; blue when its mode is on."""
        if (char, on) not in self.images:
            from System.Drawing import Bitmap, Color, Font, Graphics, GraphicsUnit, SolidBrush, StringFormat, StringAlignment, RectangleF
            from System.Drawing.Text import TextRenderingHint
            size = self.size
            bitmap = Bitmap(size, size)
            graphics = Graphics.FromImage(bitmap)
            graphics.TextRenderingHint = TextRenderingHint.AntiAliasGridFit
            font = Font('Segoe Fluent Icons', size * .72, GraphicsUnit.Pixel)
            if font.Name != 'Segoe Fluent Icons':  # Windows 10 has the older icon font
                font = Font('Segoe MDL2 Assets', size * .72, GraphicsUnit.Pixel)
            layout = StringFormat()
            layout.Alignment = layout.LineAlignment = StringAlignment.Center
            color = Color.FromArgb(255, 0, 103, 192) if on else Color.FromArgb(255, 40, 52, 66)
            graphics.DrawString(char, font, SolidBrush(color), RectangleF(0, 0, size, size), layout)
            graphics.Dispose()
            self.images[char, on] = bitmap
        return self.images[char, on]

    def rebuild(self):
        from System.Windows.Forms import ToolStripMenuItem, ToolStripSeparator
        self.menu.Items.Clear()
        for entry in menu_entries(self.current_state()):
            if entry is None:
                self.menu.Items.Add(ToolStripSeparator())
                continue
            key, label, char, checked = entry
            item = ToolStripMenuItem(label)
            item.Image = self.glyph(char, bool(checked))
            if checked is not None:
                item.Checked = checked
            item.Click += (lambda chosen: lambda sender, event: self.on_pick(chosen))(key)
            self.menu.Items.Add(item)

    def show(self, visible):
        self.icon.Visible = bool(visible)

    def dispose(self):
        self.icon.Visible = False
        self.icon.Dispose()
