"""Linear / Raycast inspired minimalist graphite design system with gamma-correct subpixel anti-aliasing."""
import sys
import tkinter as tk
from tkinter import ttk

# Precomputed sRGB <-> Linear (gamma 2.2) lookup tables for true subpixel anti-aliasing without dark fringes
_SRGB_TO_LIN = [(i / 255.0) ** 2.2 for i in range(256)]
_LIN_STEPS = 1024
_LIN_TO_SRGB = [int(((i / _LIN_STEPS) ** (1.0 / 2.2)) * 255.0 + 0.5) for i in range(_LIN_STEPS + 1)]

# 4x4 Rotated Grid Supersampling (RGSS) subpixel offsets within [-0.5, +0.5]
_RGSS_OFFSETS = (
    (-0.375, -0.125),
    ( 0.125, -0.375),
    (-0.125,  0.375),
    ( 0.375,  0.125),
)


def _hex_to_lin(color):
    r = int(color[1:3], 16)
    g = int(color[3:5], 16)
    b = int(color[5:7], 16)
    return (_SRGB_TO_LIN[r], _SRGB_TO_LIN[g], _SRGB_TO_LIN[b])


def _lin_to_hex(lr, lg, lb):
    ir = _LIN_TO_SRGB[min(_LIN_STEPS, max(0, int(lr * _LIN_STEPS + 0.5)))]
    ig = _LIN_TO_SRGB[min(_LIN_STEPS, max(0, int(lg * _LIN_STEPS + 0.5)))]
    ib = _LIN_TO_SRGB[min(_LIN_STEPS, max(0, int(lb * _LIN_STEPS + 0.5)))]
    return f'#{ir:02x}{ig:02x}{ib:02x}'


def _smoothstep(edge0, edge1, x):
    if x <= edge0:
        return 0.0
    if x >= edge1:
        return 1.0
    t = (x - edge0) / (edge1 - edge0)
    return t * t * (3.0 - 2.0 * t)


def _blend_lin(c_fg, c_bg, alpha):
    if alpha <= 0.0:
        return c_bg
    if alpha >= 1.0:
        return c_fg
    inv = 1.0 - alpha
    return (
        c_fg[0] * alpha + c_bg[0] * inv,
        c_fg[1] * alpha + c_bg[1] * inv,
        c_fg[2] * alpha + c_bg[2] * inv,
    )


def render_aa_rounded_rect(master, width, height, radius, fill_hex, border_hex, bg_hex, border_width=1.0):
    """Render a gamma-correct, 4xRGSS subpixel anti-aliased rounded rectangle into a tk.PhotoImage."""
    width = max(8, int(width))
    height = max(8, int(height))
    image = tk.PhotoImage(master=master, width=width, height=height)
    f_lin = _hex_to_lin(fill_hex)
    b_lin = _hex_to_lin(border_hex)
    bg_lin = _hex_to_lin(bg_hex)

    cx = (width - 1) * 0.5
    cy = (height - 1) * 0.5
    half_w = width * 0.5 - 0.75
    half_h = height * 0.5 - 0.75
    r = min(float(radius), half_w, half_h)
    bx = half_w - r
    by = half_h - r

    def sample_pixel(px, py):
        acc_r = acc_g = acc_b = 0.0
        for ox, oy in _RGSS_OFFSETS:
            sx = abs(px + ox - cx) - bx
            sy = abs(py + oy - cy) - by
            outside = ((max(sx, 0.0) ** 2 + max(sy, 0.0) ** 2) ** 0.5) + min(max(sx, sy), 0.0) - r
            if border_width > 0.0:
                inner_cov = 1.0 - _smoothstep(-border_width - 0.55, -border_width + 0.55, outside)
                outer_cov = 1.0 - _smoothstep(-0.55, 0.55, outside)
                col = _blend_lin(f_lin, b_lin, inner_cov)
                col = _blend_lin(col, bg_lin, outer_cov)
            else:
                outer_cov = 1.0 - _smoothstep(-0.55, 0.55, outside)
                col = _blend_lin(f_lin, bg_lin, outer_cov)
            acc_r += col[0]
            acc_g += col[1]
            acc_b += col[2]
        return _lin_to_hex(acc_r * 0.25, acc_g * 0.25, acc_b * 0.25)

    corner_span = min(width // 2, int(r + border_width + 3))
    row_span = min(height // 2, int(r + border_width + 3))

    def build_row(y):
        left = [sample_pixel(x, y) for x in range(corner_span)]
        mid_color = sample_pixel(corner_span, y) if width > 2 * corner_span else left[-1]
        mid_count = max(0, width - 2 * corner_span)
        right = list(reversed(left)) if width >= 2 * corner_span else [sample_pixel(x, y) for x in range(corner_span, width)]
        tokens = left + ([mid_color] * mid_count) + right
        return '{' + ' '.join(tokens[:width]) + '}'

    top_rows = [build_row(y) for y in range(row_span)]
    mid_row = build_row(row_span) if height > 2 * row_span else top_rows[-1]
    mid_rows_count = max(0, height - 2 * row_span)
    bottom_rows = list(reversed(top_rows)) if height >= 2 * row_span else [build_row(y) for y in range(row_span, height)]
    all_rows = top_rows + ([mid_row] * mid_rows_count) + bottom_rows
    image.put(' '.join(all_rows[:height]))
    return image


def style_window_chrome(root):
    icons = []
    bg_lin = _hex_to_lin('#111114')
    fg_lin = _hex_to_lin('#f4f4f5')
    for size in (16, 32, 48):
        icon = tk.PhotoImage(master=root, width=size, height=size)
        scale = size / 16.0
        bars = [
            ((3.0 + idx * 3.3) * scale, h * 0.5 * scale, max(0.85, 0.95 * scale))
            for idx, h in enumerate((5.5, 11.0, 8.5, 5.0))
        ]
        cy = (size - 1) * 0.5
        rows = []
        for y in range(size):
            row = []
            for x in range(size):
                acc_r = acc_g = acc_b = 0.0
                for ox, oy in _RGSS_OFFSETS:
                    px, py = x + ox, y + oy
                    col = bg_lin
                    for bx_pos, b_half, b_rad in bars:
                        dx = abs(px - bx_pos)
                        dy = max(abs(py - cy) - b_half, 0.0)
                        d = (dx * dx + dy * dy) ** 0.5 - b_rad
                        if d < 0.65:
                            cov = 1.0 - _smoothstep(-0.55, 0.55, d)
                            col = _blend_lin(fg_lin, col, cov)
                            break
                    acc_r += col[0]
                    acc_g += col[1]
                    acc_b += col[2]
                row.append(_lin_to_hex(acc_r * 0.25, acc_g * 0.25, acc_b * 0.25))
            rows.append('{' + ' '.join(row) + '}')
        icon.put(' '.join(rows))
        icons.append(icon)
    root.iconphoto(True, *icons)
    root._brand_icons = icons
    if sys.platform != 'win32':
        return

    def apply(event=None):
        if event is not None and event.widget is not root:
            return
        try:
            import ctypes
            from ctypes import wintypes
            user32 = ctypes.WinDLL('user32')
            user32.GetAncestor.argtypes = [wintypes.HWND, wintypes.UINT]
            user32.GetAncestor.restype = wintypes.HWND
            hwnd = user32.GetAncestor(root.winfo_id(), 2)
            set_attribute = ctypes.WinDLL('dwmapi').DwmSetWindowAttribute
            set_attribute.argtypes = [wintypes.HWND, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD]
            set_attribute.restype = ctypes.c_long
            # COLORREF stores 0x00BBGGRR:
            # 20: DWMWA_USE_IMMERSIVE_DARK_MODE = 1
            # 33: DWMWA_WINDOW_CORNER_PREFERENCE = 2 (DWMWCP_ROUND - hardware anti-aliased corners)
            # 34: DWMWA_BORDER_COLOR = #27272a -> 0x2a2727
            # 35: DWMWA_CAPTION_COLOR = #111114 -> 0x141111
            # 36: DWMWA_TEXT_COLOR = #f4f4f5 -> 0xf5f4f4
            values = {20: 1, 33: 2, 34: 0x2A2727, 35: 0x141111, 36: 0xF5F4F4}
            root._chrome_results = {}
            for attribute, value in values.items():
                data = wintypes.DWORD(value)
                root._chrome_results[attribute] = set_attribute(hwnd, attribute, ctypes.byref(data), ctypes.sizeof(data))
        except (OSError, AttributeError, tk.TclError):
            pass
    root.bind('<Map>', apply, add='+')
    root.after_idle(apply)


# Neutral Graphite / Zinc palette (no neon cyan or navy tint)
SURFACE = '#141417'
ELEVATED = '#1c1c21'
BACKGROUND = '#09090b'
NAV = '#111114'
BORDER = '#27272a'
ACCENT = '#e4e4e7'
PRIMARY_BG = '#f4f4f5'
PRIMARY_FG = '#09090b'
INK = '#f4f4f5'
MUTED = '#71717a'
SUCCESS = '#10b981'
WARNING = '#f59e0b'
DANGER = '#e11d48'


def apply_theme(root):
    style_window_chrome(root)
    root.configure(bg=BACKGROUND)
    for widget in ('Text','Listbox','Menu'):
        root.option_add('*'+widget+'.Font', ('Microsoft YaHei UI',10))
    for key,value in {'background':SURFACE,'foreground':INK,'selectBackground':'#27272a',
                      'selectForeground':INK}.items():
        root.option_add('*Listbox.'+key,value)
    for widget in ('Text','Menu','Canvas'):
        root.option_add('*'+widget+'.background',SURFACE)
        root.option_add('*'+widget+'.foreground',INK)
    root.option_add('*Text.insertBackground',INK)
    root.option_add('*Text.selectBackground','#27272a')
    root.option_add('*Menu.activeBackground','#27272a')
    root.option_add('*Menu.activeForeground',INK)
    root.option_add('*Toplevel.background',BACKGROUND)
    root.option_add('*Text.relief','flat')
    root.option_add('*Text.background','#0c0c0e')
    root.option_add('*Text.highlightThickness',1)
    root.option_add('*Text.highlightBackground',BORDER)
    root.option_add('*Text.highlightColor','#52525b')
    root.option_add('*Text.padX',10)
    root.option_add('*Text.padY',8)
    style=ttk.Style(root);style.theme_use('clam')
    line=BORDER
    style.configure('.',font=('Microsoft YaHei UI',10),background=SURFACE,foreground=INK,
                    bordercolor=line,lightcolor=line,darkcolor=line)
    for name,color in [('TFrame',SURFACE),('App.TFrame',BACKGROUND),('Nav.TFrame',NAV),('Elevated.TFrame',ELEVATED)]:
        style.configure(name,background=color)
    style.configure('Card.TFrame',background=SURFACE,borderwidth=1,relief='solid',
                    bordercolor=line,lightcolor=line,darkcolor=line)
    style.configure('Ticker.TFrame',background='#0c0c0e',borderwidth=1,relief='solid',
                    bordercolor=BORDER,lightcolor=BORDER,darkcolor=BORDER)
    style.configure('TLabel',background=SURFACE,foreground=INK)
    style.configure('Heading.TLabel',font=('Microsoft YaHei UI',11,'bold'),foreground=INK)
    style.configure('Eyebrow.TLabel',font=('Segoe UI',9,'bold'),foreground=MUTED)
    style.configure('TLabelframe',background=SURFACE,bordercolor=line)
    style.configure('TLabelframe.Label',background=SURFACE,foreground=INK)
    style.configure('TScale',background=SURFACE,troughcolor='#27272a')
    style.configure('TNotebook.Tab',lightcolor=SURFACE,darkcolor=SURFACE)
    style.configure('PageTitle.TLabel',font=('Microsoft YaHei UI',15,'bold'),foreground=INK)
    style.configure('Muted.TLabel',foreground=MUTED)
    style.configure('NavMuted.TLabel',background=NAV,foreground='#a1a1aa',font=('Microsoft YaHei UI',9))
    style.configure('Footer.TLabel',background=BACKGROUND,foreground=MUTED,font=('Microsoft YaHei UI',9))
    style.configure('Badge.TLabel',font=('Segoe UI',8),foreground=MUTED,background='#1c1c21',padding=(6,2))
    style.configure('TickerBadge.TLabel',font=('Microsoft YaHei UI',9,'bold'),foreground=PRIMARY_FG,background=PRIMARY_BG,padding=(6,2))
    style.configure('TickerText.TLabel',font=('Microsoft YaHei UI',10),foreground=INK,background='#0c0c0e')
    style.configure('TButton',padding=(10,6),relief='flat',borderwidth=0,foreground=INK,
                    focusthickness=1,focuscolor='#52525b')
    style.map('TButton',foreground=[('disabled','#52525b')])
    for name,fg in [('Primary.TButton',PRIMARY_FG),('Nav.TButton','#d4d4d8'),('NavSelected.TButton','#ffffff'),
                    ('Stop.TButton','#ffffff'),('Quiet.TButton','#a1a1aa')]:
        style.configure(name,foreground=fg)
        style.map(name,foreground=[('disabled','#52525b'),('!disabled',fg)])
    style.configure('Primary.TButton',font=('Microsoft YaHei UI',10,'bold'))
    style.configure('Nav.TButton',width=0)
    style.configure('NavSelected.TButton',width=0,font=('Microsoft YaHei UI',10,'bold'))
    style.configure('Nav.TMenubutton',width=0,foreground='#d4d4d8',arrowcolor='#a1a1aa',arrowsize=9)
    style.configure('TCheckbutton',padding=(0,4),indicatorbackground='#0c0c0e',indicatorforeground=PRIMARY_FG)
    style.map('TCheckbutton',background=[('active',SURFACE)],indicatorbackground=[('selected',PRIMARY_BG),('!selected','#18181c')])
    for name in ('TEntry','TCombobox'):
        style.configure(name,padding=6,fieldbackground='#0c0c0e',background='#1c1c21',
                        bordercolor=line,lightcolor=line,darkcolor=line,arrowsize=11,arrowcolor=MUTED,foreground=INK,insertcolor=INK)
        style.map(name,bordercolor=[('focus','#52525b')])
    style.map('TCombobox',fieldbackground=[('readonly','#0c0c0e')],
              selectbackground=[('readonly','#0c0c0e')],selectforeground=[('readonly',INK)],
              bordercolor=[('focus','#52525b')])
    style.configure('TNotebook',background=SURFACE,borderwidth=0,tabmargins=(0,0,0,10),
                    lightcolor=SURFACE,darkcolor=SURFACE)
    style.configure('TNotebook.Tab',padding=(12,7),background='#141417',foreground=MUTED,borderwidth=0)
    style.map('TNotebook.Tab',background=[('selected','#27272a'),('active','#1c1c21')],
              foreground=[('selected','#ffffff'),('active','#e4e4e7')])
    style.configure('Horizontal.TProgressbar',background='#e4e4e7',troughcolor='#1c1c21',borderwidth=0,thickness=4)
    style.layout('Vertical.TScrollbar',[('Vertical.Scrollbar.trough',{'sticky':'ns','children':[
        ('Vertical.Scrollbar.thumb',{'expand':'1','sticky':'nswe'})]})])
    style.configure('Vertical.TScrollbar',background='#27272a',troughcolor='#0c0c0e',borderwidth=0,
                    bordercolor='#0c0c0e',lightcolor='#27272a',darkcolor='#27272a',arrowsize=8,width=7)
    style.map('Vertical.TScrollbar',background=[('pressed','#71717a'),('active','#3f3f46')])
    style.configure('TPanedwindow',background=BACKGROUND,sashwidth=6)
    style.configure('Treeview',rowheight=32,fieldbackground=SURFACE,background=SURFACE,foreground=INK)
    style.map('Treeview',background=[('selected','#27272a')],foreground=[('selected',INK)])
    apply_rounded_buttons(root,style)


def apply_rounded_buttons(root,style):
    """Generate gamma-correct 4xRGSS anti-aliased 6px micro-rounded Nine-Patch textures."""
    images=[]
    palettes={
        'TButton':('#1c1c21','#2e2e34','#27272a','#3f3f46','#141417','#141417',SURFACE),
        'Primary.TButton':('#f4f4f5','#ffffff','#ffffff','#ffffff','#d4d4d8','#27272a',SURFACE),
        'Nav.TButton':('#16161a','#242429','#222228','#3f3f46','#111114','#141417',NAV),
        'NavSelected.TButton':('#27272a','#52525b','#303036','#71717a','#1c1c21','#18181c',NAV),
        'Stop.TButton':('#be123c','#e11d48','#e11d48','#f43f5e','#9f1239','#3f2028',NAV),
        'Quiet.TButton':('#16161a','#222228','#222228','#383842','#121215','#141417',SURFACE),
        'Nav.TMenubutton':('#16161a','#242429','#222228','#3f3f46','#111114','#141417',NAV),
    }
    size = 24
    radius = 5.5

    def micro_rect(fill, border, background):
        img = render_aa_rounded_rect(root, size, size, radius, fill, border, background, border_width=1.0)
        images.append(img)
        return img

    for name,(fn,bn,fh,bh,fp,fd,bg) in palettes.items():
        normal = micro_rect(fn, bn, bg)
        hover = micro_rect(fh, bh, bg)
        pressed = micro_rect(fp, bn, bg)
        disabled = micro_rect(fd, '#222226', bg)
        element='Pill.'+name
        style.element_create(element,'image',normal,('disabled',disabled),('pressed',pressed),('active',hover),('focus',hover),
                             border=(7,7,7,7),sticky='nsew')
        children=[('Button.padding',{'sticky':'nsew','children':[('Button.label',{'sticky':'nsew'})]})]
        if name.endswith('TMenubutton'):
            children=[('Menubutton.padding',{'sticky':'nsew','children':[
                ('Menubutton.indicator',{'side':'right','sticky':''}),('Menubutton.label',{'sticky':'nsew'})]})]
        style.layout(name,[(element,{'sticky':'nsew','children':children})])
        style.configure(name,padding=(10,6))

    tab_normal = micro_rect('#141417', '#222228', SURFACE)
    tab_selected = micro_rect('#27272a', '#46464f', SURFACE)
    tab_hover = micro_rect('#1c1c21', '#32323a', SURFACE)
    style.element_create('Segment.tab','image',tab_normal,('selected',tab_selected),('active',tab_hover),('focus',tab_hover),border=(7,7,7,7),sticky='nsew')
    style.layout('TNotebook.Tab',[('Segment.tab',{'sticky':'nsew','children':[('Notebook.padding',{'sticky':'nsew','children':[('Notebook.label',{'sticky':'nsew'})]})]})])
    style.configure('TNotebook',bordercolor=SURFACE)
    style.configure('TNotebook.Tab',padding=(11,6))
    root._button_images=images
