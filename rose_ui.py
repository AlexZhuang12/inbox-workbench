import ctypes
from ctypes import wintypes
import sys
import tkinter as tk
from tkinter import font, ttk

BACKGROUND = "#fff1f6"
SURFACE = "#fffafd"
BORDER = "#efd3e1"
INK = "#4b273e"
MUTED = "#77536a"
ACCENT = "#92385f"
FONT = "Microsoft JhengHei UI"


def style_window(window):
    window.configure(bg=BACKGROUND)

    def paint_caption(event):
        if event.widget is not window or sys.platform != "win32":
            return
        user32 = ctypes.WinDLL("user32")
        get_ancestor = user32.GetAncestor
        get_ancestor.argtypes = (wintypes.HWND, wintypes.UINT)
        get_ancestor.restype = wintypes.HWND
        set_attribute = ctypes.WinDLL("dwmapi").DwmSetWindowAttribute
        set_attribute.argtypes = (wintypes.HWND, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD)
        hwnd = get_ancestor(window.winfo_id(), 2)
        colors = {34: BORDER, 35: BACKGROUND, 36: INK}
        for attribute, color in colors.items():
            red, green, blue = bytes.fromhex(color[1:])
            value = wintypes.DWORD(red | green << 8 | blue << 16)
            set_attribute(hwnd, attribute, ctypes.byref(value), ctypes.sizeof(value))
        round_corners = wintypes.DWORD(2)
        set_attribute(hwnd, 33, ctypes.byref(round_corners), ctypes.sizeof(round_corners))

    window.bind("<Map>", paint_caption, add="+")


def rounded(canvas, x, y, width, height, radius, **style):
    right, bottom = x + width, y + height
    radius = min(radius, width / 2, height / 2)
    return canvas.create_polygon(
        x+radius, y, right-radius, y, right, y, right, y+radius,
        right, bottom-radius, right, bottom, right-radius, bottom,
        x+radius, bottom, x, bottom, x, bottom-radius, x, y+radius, x, y,
        smooth=True, splinesteps=16, **style,
    )


class RoseButton(tk.Canvas):
    def __init__(self, parent, text, command, *, primary=False, background=SURFACE):
        self.label = text
        self.command = command
        self.primary = primary
        self.disabled = self.hovered = self.pressed = False
        self.text_font = font.Font(root=parent, family=FONT, size=10)
        super().__init__(parent, width=self.text_font.measure(text)+32, height=self.text_font.metrics("linespace")+18,
                         bg=background, highlightthickness=0, bd=0, takefocus=True)
        for event in ("<Configure>", "<FocusIn>", "<FocusOut>"):
            self.bind(event, self.draw)
        self.bind("<Enter>", self.enter)
        self.bind("<Leave>", self.leave)
        self.bind("<ButtonPress-1>", self.press)
        self.bind("<ButtonRelease-1>", self.release)
        self.bind("<Key-space>", self.activate)
        self.bind("<Return>", self.activate)

    def state(self, flags):
        self.disabled = "disabled" in flags
        self.configure(takefocus=not self.disabled, cursor="" if self.disabled else "hand2")
        self.draw()

    def draw(self, event=None):
        self.delete("all")
        width, height = self.winfo_width(), self.winfo_height()
        if min(width, height) < 8:
            return
        if self.disabled:
            fill, text = "#f7eaf0", "#926b80"
        elif self.primary:
            fill, text = ("#742647" if self.hovered else ACCENT), "#ffffff"
        else:
            fill, text = ("#f2d5e4" if self.hovered else "#f9e6f0"), INK
        outline = ACCENT if self.focus_get() == self else BORDER
        rounded(self, 2, 2, width-4, height-4, 12, fill=fill, outline=outline)
        self.create_text(width/2, height/2, text=self.label, font=self.text_font, fill=text)

    def enter(self, event):
        self.hovered = True
        self.draw()

    def leave(self, event):
        self.hovered = False
        self.draw()

    def press(self, event):
        self.pressed = not self.disabled
        if self.pressed:
            self.focus_set()

    def release(self, event):
        pressed, self.pressed = self.pressed, False
        if pressed and 0 <= event.x < self.winfo_width() and 0 <= event.y < self.winfo_height():
            self.activate()

    def activate(self, event=None):
        if not self.disabled:
            self.command()
        return "break"


class RoseCard(tk.Canvas):
    def __init__(self, parent, padding=14):
        super().__init__(parent, bg=BACKGROUND, highlightthickness=0, bd=0, width=1, height=1)
        self.padding = padding
        self.content = tk.Frame(self, bg=SURFACE, bd=0, highlightthickness=0)
        self.content_id = self.create_window(padding, padding, window=self.content, anchor="nw")
        self.bind("<Configure>", self.draw)

    def fit(self):
        self.update_idletasks()
        self.configure(height=self.content.winfo_reqheight()+self.padding*2,
                       width=self.content.winfo_reqwidth()+self.padding*2)

    def draw(self, event):
        self.delete("surface")
        surface = rounded(self, 1, 1, event.width-2, event.height-2, 18,
                          fill=SURFACE, outline=BORDER, tags=("surface",))
        self.tag_lower(surface)
        self.itemconfigure(self.content_id, width=max(1, event.width-2*self.padding),
                           height=max(1, event.height-2*self.padding))


def dialog(parent, title, prompt, *, initial=None):
    window = tk.Toplevel(parent)
    window.withdraw()
    window.title(title)
    if parent.winfo_viewable():
        window.transient(parent)
    window.resizable(False, False)
    style_window(window)
    card = RoseCard(window, padding=20)
    card.pack(fill="both", expand=True, padx=12, pady=12)
    panel = card.content
    ttk.Label(panel, text=title, style="Section.TLabel").pack(anchor="w")
    ttk.Label(panel, text=prompt, style="Muted.TLabel", wraplength=340).pack(anchor="w", pady=(6, 12))
    entry = None
    if initial is not None:
        entry = ttk.Entry(panel, width=37, style="Rose.TEntry")
        entry.pack(fill="x", ipady=5)
        entry.insert(0, initial)
    buttons = ttk.Frame(panel)
    buttons.pack(fill="x", pady=(14, 0))
    result = None

    def accept():
        nonlocal result
        if entry is not None:
            result = entry.get()
        window.destroy()

    confirm = RoseButton(buttons, "確認" if entry is not None else "知道了", accept, primary=True)
    confirm.pack(side="right")
    if entry is not None:
        RoseButton(buttons, "取消", window.destroy).pack(side="right", padx=(0, 8))
        entry.bind("<Return>", lambda event: accept())
    window.bind("<Escape>", lambda event: window.destroy())
    card.fit()
    window.update_idletasks()
    width, height = window.winfo_reqwidth(), window.winfo_reqheight()
    x = parent.winfo_rootx() + (parent.winfo_width()-width)//2
    y = parent.winfo_rooty() + (parent.winfo_height()-height)//2
    window.geometry(f"+{max(0,x)}+{max(0,y)}")
    window.deiconify()
    window.wait_visibility()
    window.grab_set()
    if entry is not None:
        entry.selection_range(0, "end")
    (entry or confirm).focus_set()
    parent.wait_window(window)
    return result


def configure_theme(window):
    style_window(window)
    style = ttk.Style(window)
    style.theme_use("clam")
    style.configure(".", font=(FONT, 10), foreground=INK)
    style.configure("TFrame", background=SURFACE)
    style.configure("Rose.TFrame", background=BACKGROUND)
    style.configure("TLabel", background=SURFACE)
    style.configure("Title.TLabel", background=BACKGROUND, foreground=INK, font=(FONT, 24, "bold"))
    style.configure("Section.TLabel", font=(FONT, 13, "bold"))
    style.configure("Muted.TLabel", foreground=MUTED)
    style.configure("RoseStatus.TLabel", background=BACKGROUND, foreground=MUTED)
    style.configure("Rose.TEntry", fieldbackground="#fff5fa", bordercolor=BORDER, lightcolor=BORDER, darkcolor=BORDER)
    style.map("Rose.TEntry", bordercolor=[("focus", ACCENT)])
    style.layout("Treeview", [("Treeview.treearea", {"sticky": "nswe"})])
    style.configure("Treeview", background=SURFACE, fieldbackground=SURFACE, rowheight=34)
    style.configure("Treeview.Heading", background="#f6dfeb", foreground=INK,
                    borderwidth=0, relief="flat", bordercolor="#f6dfeb", lightcolor="#f6dfeb",
                    darkcolor="#f6dfeb", font=(FONT, 10, "bold"), padding=(6, 6))
    style.map("Treeview.Heading", background=[("active", "#f6dfeb")])
    style.map("Treeview", background=[("selected", "#f3cce1")], foreground=[("selected", INK)])
    style.layout("Rose.Vertical.TScrollbar", [
        ("Vertical.Scrollbar.trough", {"sticky": "ns", "children": [
            ("Vertical.Scrollbar.thumb", {"expand": "1", "sticky": "nswe"})
        ]})
    ])
    style.configure("Rose.Vertical.TScrollbar", background="#e7afcd", troughcolor=SURFACE,
                    bordercolor=SURFACE, lightcolor="#e7afcd", darkcolor="#e7afcd", width=9,
                    arrowsize=9, borderwidth=0)
