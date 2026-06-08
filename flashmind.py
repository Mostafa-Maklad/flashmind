#!/usr/bin/env python3
"""
FlashMind - Smart Desktop Knowledge Reminder
Displays images and notes periodically without interrupting your work
github.com/Mostafa-Maklad
"""

import tkinter as tk
from tkinter import ttk, filedialog, colorchooser, messagebox
import json
import os
import random
import threading
import time
import webbrowser
from pathlib import Path

try:
    from PIL import Image, ImageTk
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

try:
    import arabic_reshaper
    from bidi.algorithm import get_display
    ARABIC_AVAILABLE = True
except ImportError:
    ARABIC_AVAILABLE = False


def fix_arabic(text):
    """Reshape Arabic text so letters connect and display correctly."""
    if not ARABIC_AVAILABLE or not text:
        return text
    try:
        reshaped = arabic_reshaper.reshape(text)
        return get_display(reshaped)
    except Exception:
        return text


def _hex_to_rgb(hex_color):
    h = hex_color.lstrip("#")
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))


# ── Config ───────────────────────────────────────────────────────────────────
CONFIG_FILE = os.path.join(os.path.expanduser("~"), ".flashmind_config.json")

DEFAULT_CONFIG = {
    "categories":          [],
    "interval_seconds":    300,
    "display_duration":    8,
    "overlay_width":       400,
    "overlay_height":      280,
    "overlay_position":    "bottom-right",
    "opacity":             0.95,
    "image_bg_opacity":    0,
    "theme":               "dark",
    "active":              True,
    "font_size":           14,
    "note_font_size":      14,
    "show_category_badge": True,
}

CATEGORY_COLORS = [
    "#4F8EF7","#F76B6B","#6BF7B4","#F7C46B",
    "#C46BF7","#F76BC4","#6BC4F7","#B4F76B",
    "#F7906B","#6BF7D4"
]

IMAGE_EXTENSIONS = {".jpg",".jpeg",".png",".gif",".bmp",".webp"}
NOTE_EXTENSIONS  = {".txt",".md",".text"}
GITHUB_URL       = "https://github.com/Mostafa-Maklad"


def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            cfg = DEFAULT_CONFIG.copy()
            cfg.update(data)
            return cfg
        except Exception:
            pass
    return DEFAULT_CONFIG.copy()


def save_config(cfg):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


def collect_items(category):
    items = []
    for raw in category.get("paths", []):
        p = Path(raw)
        if p.is_dir():
            for f in sorted(p.rglob("*")):
                ext = f.suffix.lower()
                if ext in IMAGE_EXTENSIONS:
                    items.append({"type": "image", "path": str(f)})
                elif ext in NOTE_EXTENSIONS:
                    _parse_note_file(items, f)
        elif p.is_file():
            ext = p.suffix.lower()
            if ext in IMAGE_EXTENSIONS:
                items.append({"type": "image", "path": str(p)})
            elif ext in NOTE_EXTENSIONS:
                _parse_note_file(items, p)
    for note in category.get("inline_notes", []):
        if note.strip():
            items.append({"type": "note", "text": note.strip()})
    return items


def _parse_note_file(items, path):
    try:
        text = Path(path).read_text(encoding="utf-8").strip()
        for chunk in text.split("\n\n"):
            chunk = chunk.strip()
            if chunk:
                items.append({"type": "note", "text": chunk})
    except Exception:
        pass


# ── Overlay Window ────────────────────────────────────────────────────────────
class OverlayWindow:
    def __init__(self, root, config):
        self.root       = root
        self.config     = config
        self.win        = None
        self._timer     = None
        # Keep photo alive here — prevents Python GC from deleting it
        self._photo     = None

    def show(self, item, category):
        # Cancel previous
        if self._timer:
            try:
                self.root.after_cancel(self._timer)
            except Exception:
                pass
            self._timer = None
        if self.win:
            try:
                self.win.destroy()
            except Exception:
                pass
        self.win    = None
        self._photo = None

        self.win = tk.Toplevel(self.root)
        self.win.overrideredirect(True)
        self.win.attributes("-topmost", True)

        cfg      = self.config
        # These are the HARD LIMITS — user-configured, never exceeded
        max_w    = cfg["overlay_width"]
        max_h    = cfg["overlay_height"]
        CHROME_H = 36   # header + border + progress bar
        CHROME_W = 8

        if item["type"] == "image" and PIL_AVAILABLE:
            try:
                probe   = Image.open(item["path"])
                iw, ih  = probe.size
                probe.close()
                # Scale image to fit within user's configured box, keeping aspect ratio
                avail_w = max_w - CHROME_W
                avail_h = max_h - CHROME_H
                scale   = min(avail_w / iw, avail_h / ih, 1.0)   # never upscale beyond natural size
                # But if image is tiny, do allow scaling up to fill config box
                if iw < avail_w * 0.5 and ih < avail_h * 0.5:
                    scale = min(avail_w / iw, avail_h / ih)
                disp_w  = max(80, int(iw * scale))
                disp_h  = max(60, int(ih * scale))
                w       = disp_w + CHROME_W
                h       = disp_h + CHROME_H
                self._disp_size = (disp_w, disp_h)
            except Exception:
                w = max_w
                h = max_h
                self._disp_size = (max_w - CHROME_W, max_h - CHROME_H)
        else:
            # Notes: always use the exact configured width × height
            w = max_w
            h = max_h
            self._disp_size = None

        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        mg  = 20
        pos = cfg.get("overlay_position", "bottom-right")
        pos_map = {
            "bottom-right": (sw - w - mg, sh - h - mg - 48),
            "bottom-left":  (mg,          sh - h - mg - 48),
            "top-right":    (sw - w - mg, mg + 28),
            "top-left":     (mg,          mg + 28),
            "center":       ((sw-w)//2,   (sh-h)//2),
        }
        x, y = pos_map.get(pos, pos_map["bottom-right"])
        self.win.geometry(f"{w}x{h}+{x}+{y}")

        dark    = cfg["theme"] == "dark"
        bg      = "#1A1A2E" if dark else "#FFFFFF"
        fg      = "#E8E8FF" if dark else "#1A1A2E"
        cat_col = category.get("color", "#4F8EF7")

        # Border frame
        border = tk.Frame(self.win, bg=cat_col, padx=2, pady=2)
        border.pack(fill="both", expand=True)
        body = tk.Frame(border, bg=bg)
        body.pack(fill="both", expand=True)

        # Header
        hbar = tk.Frame(body, bg=bg, height=26)
        hbar.pack(fill="x")
        hbar.pack_propagate(False)

        if cfg.get("show_category_badge", True):
            badge = tk.Label(hbar, text=f"  {category.get('name','?')}  ",
                             bg=cat_col, fg="white",
                             font=("Arial", 8, "bold"), padx=2)
            badge.pack(side="left", padx=5, pady=3)

        close = tk.Label(hbar, text="✕", bg=bg, fg="#777",
                         font=("Arial", 10), cursor="hand2", padx=6)
        close.pack(side="right", pady=2)
        close.bind("<Button-1>", lambda e: self._close())

        # Content
        content = tk.Frame(body, bg=bg)
        content.pack(fill="both", expand=True, padx=4, pady=(0,3))

        if item["type"] == "image":
            dw, dh = self._disp_size if self._disp_size else (w - 8, h - 44)
            self._show_image(content, item["path"], bg, dw, dh)
        else:
            self._show_note(content, item.get("text",""), bg, fg)

        # Progress bar
        dur = cfg["display_duration"]
        pbar_bg = tk.Frame(body, bg="#252540" if dark else "#DDDDDD", height=3)
        pbar_bg.pack(fill="x", side="bottom")
        pbar = tk.Frame(pbar_bg, bg=cat_col, height=3)
        pbar.place(relx=0, rely=0, relwidth=1.0, relheight=1.0)
        self._tick_bar(pbar, dur * 1000, 0)

        # Opacity
        try:
            self.win.attributes("-alpha", cfg["opacity"])
        except Exception:
            pass

        # Click to dismiss
        self.win.bind("<Button-1>", lambda e: self._close())

        # Auto dismiss
        self._timer = self.root.after(dur * 1000, self._close)

        # Slide in
        self._slide(x, y, w, h)

    # ── Image rendering ──────────────────────────────────────────────────────
    def _show_image(self, parent, path, bg, disp_w, disp_h):
        if not PIL_AVAILABLE:
            tk.Label(parent,
                     text="Pillow not installed.\nRun: pip install pillow",
                     bg=bg, fg="#F7C46B",
                     font=("Arial", 11), justify="center").pack(expand=True)
            return
        try:
            img = Image.open(path).convert("RGBA")
            # Resize to the exact display size computed from image's own aspect ratio
            img = img.resize((disp_w, disp_h), Image.LANCZOS)

            self._photo = ImageTk.PhotoImage(img)
            lbl = tk.Label(parent, image=self._photo,
                           bg=bg, bd=0, highlightthickness=0)
            lbl.pack(expand=True, fill="both")

        except Exception as e:
            tk.Label(parent,
                     text=f"Cannot load:\n{Path(path).name}\n{e}",
                     bg=bg, fg="#F76B6B",
                     font=("Arial", 10), justify="center",
                     wraplength=300).pack(expand=True, padx=8)

    # ── Note rendering ───────────────────────────────────────────────────────
    def _show_note(self, parent, text, bg, fg):
        display = fix_arabic(text)
        fsz     = self.config.get("note_font_size", self.config.get("font_size", 14))

        # Best Arabic-capable fonts on Windows/Linux
        font_name = "Segoe UI"   # Windows — best Arabic support
        try:
            import tkinter.font as tkfont
            tkfont.Font(family="Segoe UI").actual()
        except Exception:
            font_name = "Arial"

        # Scrollbar — hidden when not needed, visible when text overflows
        sb = tk.Scrollbar(parent, orient="vertical", width=8,
                          troughcolor=bg, bg=bg)
        t  = tk.Text(parent, bg=bg, fg=fg, wrap="word",
                     font=(font_name, fsz),
                     relief="flat", bd=0, highlightthickness=0,
                     cursor="arrow",
                     spacing1=2, spacing2=1, spacing3=2,
                     yscrollcommand=sb.set)
        sb.config(command=t.yview)
        sb.pack(side="right", fill="y")
        t.pack(side="left", fill="both", expand=True, padx=8, pady=4)
        t.insert("1.0", display)
        t.configure(state="disabled")

    # ── Progress bar ─────────────────────────────────────────────────────────
    def _tick_bar(self, bar, total_ms, elapsed_ms):
        if not self.win:
            return
        ratio = max(0.0, 1.0 - elapsed_ms / total_ms)
        try:
            bar.place_configure(relwidth=ratio)
        except Exception:
            return
        if elapsed_ms < total_ms:
            self.root.after(150, lambda: self._tick_bar(bar, total_ms, elapsed_ms+150))

    # ── Slide-in animation ───────────────────────────────────────────────────
    def _slide(self, fx, fy, w, h):
        sx = self.root.winfo_screenwidth() + 10
        steps = 14
        dx = (fx - sx) / steps
        try:
            self.win.geometry(f"{w}x{h}+{sx}+{fy}")
        except Exception:
            return
        self._do_slide(float(sx), fy, fx, w, h, dx, steps)

    def _do_slide(self, cx, y, tx, w, h, dx, n):
        if not self.win or n <= 0:
            try:
                self.win.geometry(f"{w}x{h}+{tx}+{y}")
            except Exception:
                pass
            return
        cx += dx
        try:
            self.win.geometry(f"{w}x{h}+{int(cx)}+{y}")
        except Exception:
            return
        self.root.after(16, lambda: self._do_slide(cx, y, tx, w, h, dx, n-1))

    def _close(self):
        if self._timer:
            try:
                self.root.after_cancel(self._timer)
            except Exception:
                pass
            self._timer = None
        self._photo = None
        if self.win:
            try:
                self.win.destroy()
            except Exception:
                pass
            self.win = None


# ── Scheduler ────────────────────────────────────────────────────────────────
class Scheduler:
    def __init__(self, app):
        self.app      = app
        self._stop    = threading.Event()
        self._history = {}

    def start(self):
        self._stop.clear()
        threading.Thread(target=self._loop, daemon=True).start()

    def stop(self):
        self._stop.set()

    def trigger_now(self):
        threading.Thread(target=self._pick_and_show, daemon=True).start()

    def _loop(self):
        # Wait full interval BEFORE first show — no popup on startup
        while not self._stop.wait(self.app.config["interval_seconds"]):
            if self.app.config.get("active", True):
                self._pick_and_show()

    def _pick_and_show(self):
        cfg  = self.app.config
        cats = [c for c in cfg["categories"] if c.get("enabled", True)]
        if not cats:
            return
        cat   = random.choice(cats)
        items = collect_items(cat)
        if not items:
            return

        cid   = cat.get("id", cat["name"])
        seen  = self._history.setdefault(cid, [])
        avail = [i for i in range(len(items)) if i not in seen]
        if not avail:
            self._history[cid] = []
            avail = list(range(len(items)))

        idx = random.choice(avail)
        seen.append(idx)
        if len(seen) > max(1, len(items) // 2):
            self._history[cid] = seen[-3:]

        item = items[idx]
        self.app.root.after(0, lambda: self.app.overlay.show(item, cat))


# ── Main App ──────────────────────────────────────────────────────────────────
class FlashMindApp:
    def __init__(self):
        self.config    = load_config()
        self.root      = tk.Tk()
        self.root.title("FlashMind")
        self.root.geometry("720x640")
        self.root.resizable(True, True)
        self._setup_style()
        self.overlay   = OverlayWindow(self.root, self.config)
        self.scheduler = Scheduler(self)
        self._build_ui()
        self.scheduler.start()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _setup_style(self):
        dark        = self.config["theme"] == "dark"
        self._bg    = "#0F0F1A" if dark else "#F4F4F8"
        self._fg    = "#E0E0FF" if dark else "#1A1A2E"
        self._hdr   = "#14142A" if dark else "#D0D4E8"
        self._card  = "#1C1C2E" if dark else "#E8E8F0"
        self._acc   = "#4F8EF7"
        self.root.configure(bg=self._bg)
        s = ttk.Style()
        s.theme_use("clam")
        s.configure("TFrame",        background=self._bg)
        s.configure("TLabel",        background=self._bg, foreground=self._fg)
        s.configure("TButton",       background=self._acc, foreground="white",
                    font=("Arial", 10, "bold"), padding=6, relief="flat")
        s.map("TButton",             background=[("active","#3A7BEA")])
        s.configure("TNotebook",     background=self._bg, tabmargins=[2,4,2,0])
        s.configure("TNotebook.Tab", background=self._card,
                    foreground=self._fg, padding=[14,5], font=("Arial",10))
        s.map("TNotebook.Tab",
              background=[("selected", self._acc)],
              foreground=[("selected", "white")])
        # Combobox — explicit colors so dropdown list is always readable
        cb_field = "#1C1C2E" if dark else "#FFFFFF"
        cb_fg    = "#E0E0FF" if dark else "#1A1A2E"
        s.configure("TCombobox",
                    fieldbackground=cb_field,
                    background=self._card,
                    foreground=cb_fg,
                    selectbackground=self._acc,
                    selectforeground="white",
                    arrowcolor=cb_fg)
        s.map("TCombobox",
              fieldbackground=[("readonly", cb_field)],
              foreground=[("readonly", cb_fg)],
              selectbackground=[("readonly", self._acc)],
              selectforeground=[("readonly", "white")])
        # Make the dropdown listbox readable via option_add
        self.root.option_add("*TCombobox*Listbox.background",   cb_field)
        self.root.option_add("*TCombobox*Listbox.foreground",   cb_fg)
        self.root.option_add("*TCombobox*Listbox.selectBackground", self._acc)
        self.root.option_add("*TCombobox*Listbox.selectForeground", "white")

    def _build_ui(self):
        bg, fg, acc = self._bg, self._fg, self._acc

        # Header
        hdr = tk.Frame(self.root, bg=self._hdr, pady=12)
        hdr.pack(fill="x")
        tk.Label(hdr, text="⚡ FlashMind",
                 font=("Arial", 22, "bold"),
                 bg=self._hdr, fg=acc).pack(side="left", padx=20)
        tk.Label(hdr, text="Burn knowledge into memory",
                 font=("Arial", 11), bg=self._hdr,
                 fg="#8899CC").pack(side="left")

        # Control row
        ctrl = tk.Frame(self.root, bg=bg, pady=8)
        ctrl.pack(fill="x", padx=20)
        self.active_var = tk.BooleanVar(value=self.config.get("active", True))
        tk.Checkbutton(ctrl, text="Active",
                       variable=self.active_var,
                       command=self._toggle_active,
                       bg=bg, fg=fg, selectcolor=self._card,
                       activebackground=bg,
                       font=("Arial", 11, "bold")).pack(side="left")
        ttk.Button(ctrl, text="▶  Show Now",
                   command=self.scheduler.trigger_now).pack(side="right", padx=4)
        ttk.Button(ctrl, text="💾  Save",
                   command=self._save).pack(side="right", padx=4)

        # Tabs
        nb = ttk.Notebook(self.root)
        nb.pack(fill="both", expand=True, padx=16, pady=(0,4))
        self._tab_categories(nb)
        self._tab_settings(nb)
        self._tab_add_note(nb)

        # Footer
        self._build_footer()

    # ── Footer ───────────────────────────────────────────────────────────────
    def _build_footer(self):
        bg = self._hdr
        foot = tk.Frame(self.root, bg=bg, pady=4)
        foot.pack(fill="x", side="bottom")

        # Stats on the left
        n_cats  = len(self.config["categories"])
        n_items = sum(len(collect_items(c)) for c in self.config["categories"])
        tk.Label(foot,
                 text=f"{n_cats} categories  ·  {n_items} items  ·  "
                      f"every {self.config['interval_seconds']}s",
                 bg=bg, fg="#556688", font=("Arial", 9)).pack(side="left", padx=16)

        # GitHub — minimal: just the name, small, hover underline
        def open_github(e=None):
            try:
                webbrowser.open(GITHUB_URL)
            except Exception:
                pass

        gh = tk.Label(foot,
                      text="Mostafa-Maklad",
                      bg=bg, fg="#445577",
                      font=("Arial", 8),
                      cursor="hand2")
        gh.pack(side="right", padx=14)
        gh.bind("<Button-1>", open_github)
        gh.bind("<Enter>",  lambda e: gh.configure(fg="#7799CC",
                                                    font=("Arial", 8, "underline")))
        gh.bind("<Leave>",  lambda e: gh.configure(fg="#445577",
                                                    font=("Arial", 8)))

    # ── Tab: Categories ───────────────────────────────────────────────────────
    def _tab_categories(self, nb):
        frame = ttk.Frame(nb)
        nb.add(frame, text="  Categories  ")
        bg = self._bg

        tb = tk.Frame(frame, bg=bg, pady=6)
        tb.pack(fill="x", padx=8)
        tk.Button(tb, text="+  New Category",
                  bg=self._acc, fg="white",
                  font=("Arial", 10, "bold"),
                  relief="flat", cursor="hand2",
                  padx=12, pady=5,
                  activebackground="#3A7BEA",
                  activeforeground="white",
                  bd=0,
                  command=self._cat_dialog).pack(side="left")

        outer = tk.Frame(frame, bg=bg)
        outer.pack(fill="both", expand=True, padx=8, pady=4)
        cv = tk.Canvas(outer, bg=bg, highlightthickness=0)
        sb = ttk.Scrollbar(outer, orient="vertical", command=cv.yview)
        self.cat_frame = tk.Frame(cv, bg=bg)
        self.cat_frame.bind(
            "<Configure>",
            lambda e: cv.configure(scrollregion=cv.bbox("all")))
        cv.create_window((0,0), window=self.cat_frame, anchor="nw")
        cv.configure(yscrollcommand=sb.set)
        cv.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        self._redraw_cats()

    def _redraw_cats(self):
        for w in self.cat_frame.winfo_children():
            w.destroy()
        if not self.config["categories"]:
            tk.Label(self.cat_frame,
                     text="No categories yet.\nClick '＋ New Category' to get started.",
                     bg=self._bg, fg="#445566",
                     font=("Arial", 12), justify="center").pack(pady=50)
            return
        for i, cat in enumerate(self.config["categories"]):
            self._cat_row(i, cat)

    def _cat_row(self, idx, cat):
        color  = cat.get("color", CATEGORY_COLORS[idx % len(CATEGORY_COLORS)])
        items  = collect_items(cat)
        row_bg = self._card

        row = tk.Frame(self.cat_frame, bg=row_bg, pady=8, padx=10)
        row.pack(fill="x", pady=3, padx=4)

        tk.Label(row, text="●", bg=row_bg, fg=color,
                 font=("Arial", 18)).pack(side="left", padx=(0,8))

        info = tk.Frame(row, bg=row_bg)
        info.pack(side="left", fill="x", expand=True)
        tk.Label(info, text=cat["name"], bg=row_bg, fg=self._fg,
                 font=("Arial", 12, "bold")).pack(anchor="w")
        paths = cat.get("paths", [])
        names = ", ".join(Path(p).name for p in paths[:2])
        if len(paths) > 2:
            names += f" +{len(paths)-2}"
        tk.Label(info,
                 text=f"{len(items)} items  ·  {names or 'no paths yet'}",
                 bg=row_bg, fg="#667788", font=("Arial", 9)).pack(anchor="w")

        en = tk.BooleanVar(value=cat.get("enabled", True))
        _dark = self.config["theme"] == "dark"

        def _make_toggle(var, c, is_dark=_dark):
            btn_frame = tk.Frame(row, bg=row_bg)
            btn_frame.pack(side="right", padx=6)
            tog = tk.Label(btn_frame, font=("Arial", 8, "bold"),
                           padx=8, pady=3, cursor="hand2", relief="flat")
            def _refresh():
                if var.get():
                    tog.configure(bg=self._acc, fg="white", text="ON")
                else:
                    tog.configure(bg="#444455" if is_dark else "#CCCCDD",
                                  fg="#AAAACC" if is_dark else "#888899", text="OFF")
            def _toggle(e=None):
                var.set(not var.get())
                c["enabled"] = var.get()
                save_config(self.config)
                _refresh()
            tog.bind("<Button-1>", _toggle)
            _refresh()
            tog.pack()

        _make_toggle(en, cat)
        tk.Button(row, text="🗑", bg=row_bg, fg="#F76B6B",
                  relief="flat", font=("Arial", 13), cursor="hand2",
                  command=lambda i=idx: self._del_cat(i)).pack(side="right")
        tk.Button(row, text="✏", bg=row_bg, fg="#F7C46B",
                  relief="flat", font=("Arial", 13), cursor="hand2",
                  command=lambda i=idx: self._cat_dialog(i)).pack(side="right")

    def _set_enabled(self, var, cat):
        cat["enabled"] = var.get()
        save_config(self.config)

    def _del_cat(self, idx):
        name = self.config["categories"][idx]["name"]
        if messagebox.askyesno("Delete", f"Delete category '{name}'?"):
            self.config["categories"].pop(idx)
            save_config(self.config)
            self._redraw_cats()

    def _cat_dialog(self, idx=None):
        dark     = self.config["theme"] == "dark"
        dlg_bg   = "#1A1A2E" if dark else "#F0F0FA"
        dlg_fg   = "#E0E0FF" if dark else "#1A1A2E"
        ent_bg   = "#0F0F1A" if dark else "#FFFFFF"

        win = tk.Toplevel(self.root)
        win.title("New Category" if idx is None else "Edit Category")
        win.geometry("500x440")
        win.configure(bg=dlg_bg)
        win.grab_set()
        win.resizable(False, False)

        existing = self.config["categories"][idx] if idx is not None else {}

        tk.Label(win, text="Name:", bg=dlg_bg, fg=dlg_fg,
                 font=("Arial", 11)).pack(anchor="w", padx=18, pady=(16,2))
        name_var = tk.StringVar(value=existing.get("name",""))
        tk.Entry(win, textvariable=name_var, font=("Arial", 12),
                 bg=ent_bg, fg=dlg_fg, insertbackground=dlg_fg,
                 relief="flat", highlightthickness=1,
                 highlightbackground=self._acc).pack(fill="x", padx=18, ipady=4)

        color_var = tk.StringVar(
            value=existing.get("color",
                  CATEGORY_COLORS[len(self.config["categories"]) % len(CATEGORY_COLORS)]))
        cr = tk.Frame(win, bg=dlg_bg)
        cr.pack(fill="x", padx=18, pady=8)
        tk.Label(cr, text="Color:", bg=dlg_bg, fg=dlg_fg,
                 font=("Arial",11)).pack(side="left")
        prev = tk.Label(cr, bg=color_var.get(), width=5, relief="flat")
        prev.pack(side="left", padx=8)
        def pick():
            c = colorchooser.askcolor(color=color_var.get(), parent=win)
            if c[1]:
                color_var.set(c[1])
                prev.configure(bg=c[1])
        ttk.Button(cr, text="Pick Color", command=pick).pack(side="left")

        tk.Label(win, text="Folders / Files:", bg=dlg_bg, fg=dlg_fg,
                 font=("Arial",11)).pack(anchor="w", padx=18, pady=(6,2))

        pf = tk.Frame(win, bg=dlg_bg)
        pf.pack(fill="x", padx=18)
        paths_list = list(existing.get("paths", []))
        lb = tk.Listbox(pf, bg=ent_bg, fg=dlg_fg,
                        height=5, relief="flat", font=("Arial",9),
                        selectbackground=self._acc)
        lb.pack(side="left", fill="x", expand=True)
        for p in paths_list:
            lb.insert("end", p)

        bc = tk.Frame(pf, bg=dlg_bg)
        bc.pack(side="left", padx=6)

        def add_folder():
            p = filedialog.askdirectory(parent=win, title="Select Folder")
            if p and p not in paths_list:
                paths_list.append(p); lb.insert("end", p)

        def add_files():
            fs = filedialog.askopenfilenames(
                parent=win, title="Select Files",
                filetypes=[("Images & Notes",
                             "*.jpg *.jpeg *.png *.gif *.bmp *.webp *.txt *.md"),
                           ("All","*.*")])
            for f in fs:
                if f not in paths_list:
                    paths_list.append(f); lb.insert("end", f)

        def remove():
            for i in reversed(lb.curselection()):
                lb.delete(i); paths_list.pop(i)

        ttk.Button(bc, text="📁 Folder", command=add_folder).pack(pady=2, fill="x")
        ttk.Button(bc, text="📄 Files",  command=add_files ).pack(pady=2, fill="x")
        ttk.Button(bc, text="🗑 Remove", command=remove    ).pack(pady=2, fill="x")

        def save():
            name = name_var.get().strip()
            if not name:
                messagebox.showwarning("Warning","Please enter a name.",parent=win)
                return
            entry = {
                "id":           existing.get("id", str(int(time.time()))),
                "name":         name,
                "color":        color_var.get(),
                "paths":        paths_list,
                "enabled":      existing.get("enabled", True),
                "inline_notes": existing.get("inline_notes", []),
            }
            if idx is None:
                self.config["categories"].append(entry)
            else:
                self.config["categories"][idx] = entry
            save_config(self.config)
            self._redraw_cats()
            if hasattr(self, "note_cat_combo"):
                self._refresh_note_combo()
            win.destroy()

        ttk.Button(win, text="💾  Save Category", command=save).pack(pady=14)

    # ── Tab: Settings ─────────────────────────────────────────────────────────
    def _tab_settings(self, nb):
        frame = ttk.Frame(nb)
        nb.add(frame, text="  Settings  ")
        bg, fg = self._bg, self._fg
        dark = self.config["theme"] == "dark"

        def row(label, fn):
            r = tk.Frame(frame, bg=bg)
            r.pack(fill="x", padx=20, pady=5)
            tk.Label(r, text=label, bg=bg, fg=fg,
                     font=("Arial",11), width=24, anchor="w").pack(side="left")
            fn(r)

        self.v_interval = tk.IntVar(value=self.config["interval_seconds"])
        def w_int(p):
            tk.Scale(p,from_=10,to=3600,orient="horizontal",
                     variable=self.v_interval,bg=bg,fg=fg,
                     highlightthickness=0,length=260,
                     troughcolor=self._card).pack(side="left")
            tk.Label(p,textvariable=self.v_interval,bg=bg,fg=fg,width=5).pack(side="left")
            tk.Label(p,text="sec",bg=bg,fg=fg).pack(side="left")
        row("Show every:", w_int)

        self.v_dur = tk.IntVar(value=self.config["display_duration"])
        def w_dur(p):
            tk.Scale(p,from_=2,to=60,orient="horizontal",
                     variable=self.v_dur,bg=bg,fg=fg,
                     highlightthickness=0,length=260,
                     troughcolor=self._card).pack(side="left")
            tk.Label(p,textvariable=self.v_dur,bg=bg,fg=fg,width=5).pack(side="left")
            tk.Label(p,text="sec",bg=bg,fg=fg).pack(side="left")
        row("Display duration:", w_dur)

        self.v_w = tk.IntVar(value=self.config["overlay_width"])
        self.v_h = tk.IntVar(value=self.config["overlay_height"])
        def w_size(p):
            tk.Label(p,text="W:",bg=bg,fg=fg).pack(side="left")
            tk.Spinbox(p,from_=200,to=900,textvariable=self.v_w,
                       width=5,font=("Arial",11)).pack(side="left",padx=4)
            tk.Label(p,text="H:",bg=bg,fg=fg).pack(side="left")
            tk.Spinbox(p,from_=100,to=700,textvariable=self.v_h,
                       width=5,font=("Arial",11)).pack(side="left",padx=4)
        row("Window size (px):", w_size)

        self.v_pos = tk.StringVar(value=self.config["overlay_position"])
        def w_pos(p):
            ttk.Combobox(p,textvariable=self.v_pos,state="readonly",width=14,
                         values=["bottom-right","bottom-left",
                                 "top-right","top-left","center"]).pack(side="left")
        row("Position:", w_pos)

        self.v_font = tk.IntVar(value=self.config.get("font_size",14))
        def w_font(p):
            tk.Spinbox(p,from_=8,to=36,textvariable=self.v_font,
                       width=4,font=("Arial",11)).pack(side="left")
        row("Font size (UI):", w_font)

        self.v_note_font = tk.IntVar(value=self.config.get("note_font_size", 14))
        def w_note_font(p):
            tk.Scale(p, from_=8, to=42, orient="horizontal",
                     variable=self.v_note_font, bg=bg, fg=fg,
                     highlightthickness=0, length=180,
                     troughcolor=self._card).pack(side="left")
            tk.Label(p, textvariable=self.v_note_font,
                     bg=bg, fg=fg, width=3).pack(side="left")
            tk.Label(p, text="pt  (note overlay text size)",
                     bg=bg, fg=fg, font=("Arial", 9)).pack(side="left")
        row("Note font size:", w_note_font)

        self.v_opacity = tk.DoubleVar(value=self.config["opacity"])
        def w_opa(p):
            tk.Scale(p,from_=0.2,to=1.0,resolution=0.05,orient="horizontal",
                     variable=self.v_opacity,bg=bg,fg=fg,
                     highlightthickness=0,length=200,
                     troughcolor=self._card).pack(side="left")
        row("Overlay opacity:", w_opa)

        self.v_imgbg = tk.IntVar(value=self.config.get("image_bg_opacity",0))
        def w_imgbg(p):
            tk.Scale(p,from_=0,to=100,orient="horizontal",
                     variable=self.v_imgbg,bg=bg,fg=fg,
                     highlightthickness=0,length=180,
                     troughcolor=self._card).pack(side="left")
            tk.Label(p,textvariable=self.v_imgbg,bg=bg,fg=fg,width=4).pack(side="left")
            tk.Label(p,text="% (0 = no bg)",bg=bg,fg=fg,
                     font=("Arial",9)).pack(side="left")
        row("Image bg opacity:", w_imgbg)

        self.v_theme = tk.StringVar(value=self.config["theme"])
        def w_theme(p):
            ttk.Combobox(p,textvariable=self.v_theme,state="readonly",
                         width=8,values=["dark","light"]).pack(side="left")
        row("Theme:", w_theme)

        ttk.Button(frame, text="✅  Apply Settings",
                   command=self._apply_settings).pack(pady=16)

    def _apply_settings(self):
        self.config.update({
            "interval_seconds": self.v_interval.get(),
            "display_duration": self.v_dur.get(),
            "overlay_width":    self.v_w.get(),
            "overlay_height":   self.v_h.get(),
            "overlay_position": self.v_pos.get(),
            "font_size":        self.v_font.get(),
            "note_font_size":   self.v_note_font.get(),
            "opacity":          self.v_opacity.get(),
            "image_bg_opacity": self.v_imgbg.get(),
            "theme":            self.v_theme.get(),
        })
        self.overlay.config = self.config
        save_config(self.config)
        messagebox.showinfo("Saved","Settings applied!")

    # ── Tab: Add Note ─────────────────────────────────────────────────────────
    def _tab_add_note(self, nb):
        frame = ttk.Frame(nb)
        nb.add(frame, text="  Add Note  ")
        bg, fg = self._bg, self._fg
        dark   = self.config["theme"] == "dark"
        ent_bg = "#1A1A2E" if dark else "#FFFFFF"

        tk.Label(frame,
                 text="Write a note (Arabic supported). Save to category or append to file:",
                 bg=bg, fg=fg, font=("Arial",10)).pack(anchor="w", padx=16, pady=(12,4))

        self.note_text = tk.Text(frame, height=7, wrap="word",
                                 font=("Arial",13),
                                 bg=ent_bg, fg=fg,
                                 insertbackground=fg,
                                 relief="flat", bd=4)
        self.note_text.pack(fill="both", expand=True, padx=16, pady=4)

        mode_row = tk.Frame(frame, bg=bg)
        mode_row.pack(fill="x", padx=16, pady=(4,0))
        self.note_mode = tk.StringVar(value="category")
        tk.Radiobutton(mode_row, text="Save to category",
                       variable=self.note_mode, value="category",
                       command=self._toggle_note_mode,
                       bg=bg, fg=fg, selectcolor=self._card,
                       activebackground=bg,
                       font=("Arial",10)).pack(side="left")
        tk.Radiobutton(mode_row, text="Append to .txt / .md file",
                       variable=self.note_mode, value="file",
                       command=self._toggle_note_mode,
                       bg=bg, fg=fg, selectcolor=self._card,
                       activebackground=bg,
                       font=("Arial",10)).pack(side="left", padx=20)

        # Category row
        self.note_cat_row = tk.Frame(frame, bg=bg)
        self.note_cat_row.pack(fill="x", padx=16, pady=6)
        tk.Label(self.note_cat_row, text="Category:",
                 bg=bg, fg=fg, font=("Arial",11)).pack(side="left")
        self.note_cat_var   = tk.StringVar()
        self.note_cat_combo = ttk.Combobox(
            self.note_cat_row, textvariable=self.note_cat_var,
            state="readonly", width=24)
        self.note_cat_combo.pack(side="left", padx=8)
        self._refresh_note_combo()

        # File row (hidden by default)
        self.note_file_row = tk.Frame(frame, bg=bg)
        tk.Label(self.note_file_row, text="File:",
                 bg=bg, fg=fg, font=("Arial",11)).pack(side="left")
        self.note_file_var = tk.StringVar()
        tk.Entry(self.note_file_row, textvariable=self.note_file_var,
                 width=32, font=("Arial",10),
                 bg=ent_bg, fg=fg, insertbackground=fg,
                 relief="flat").pack(side="left", padx=6)
        ttk.Button(self.note_file_row, text="Browse…",
                   command=self._pick_note_file).pack(side="left")

        btn_row = tk.Frame(frame, bg=bg)
        btn_row.pack(fill="x", padx=16, pady=8)
        ttk.Button(btn_row, text="💾  Save Note",
                   command=self._save_note).pack(side="left")

    def _toggle_note_mode(self):
        if self.note_mode.get() == "category":
            self.note_file_row.pack_forget()
            self.note_cat_row.pack(fill="x", padx=16, pady=6)
        else:
            self.note_cat_row.pack_forget()
            self.note_file_row.pack(fill="x", padx=16, pady=6)

    def _pick_note_file(self):
        p = filedialog.askopenfilename(
            title="Select .txt or .md file to append to",
            filetypes=[("Text/Markdown","*.txt *.md"),("All","*.*")])
        if p:
            self.note_file_var.set(p)

    def _refresh_note_combo(self):
        names = [c["name"] for c in self.config["categories"]]
        self.note_cat_combo["values"] = names
        if names and not self.note_cat_var.get():
            self.note_cat_var.set(names[0])

    def _save_note(self):
        text = self.note_text.get("1.0","end").strip()
        if not text:
            messagebox.showwarning("Warning","Please write something first.")
            return
        if self.note_mode.get() == "file":
            target = self.note_file_var.get().strip()
            if not target:
                messagebox.showwarning("Warning","Please pick a target file.")
                return
            try:
                with open(target,"a",encoding="utf-8") as f:
                    f.write("\n\n" + text)
                self.note_text.delete("1.0","end")
                messagebox.showinfo("Saved", f"Appended to {Path(target).name}")
            except Exception as e:
                messagebox.showerror("Error", str(e))
        else:
            cat_name = self.note_cat_var.get()
            cat = next((c for c in self.config["categories"]
                        if c["name"] == cat_name), None)
            if not cat:
                messagebox.showwarning("Warning","Please select a category.")
                return
            cat.setdefault("inline_notes",[]).append(text)
            save_config(self.config)
            self.note_text.delete("1.0","end")
            messagebox.showinfo("Saved", f"Note added to '{cat_name}'")

    # ── Misc ──────────────────────────────────────────────────────────────────
    def _toggle_active(self):
        self.config["active"] = self.active_var.get()
        save_config(self.config)

    def _save(self):
        save_config(self.config)
        messagebox.showinfo("Saved","Settings saved!")

    def _on_close(self):
        save_config(self.config)
        self.scheduler.stop()
        self.root.destroy()

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    app = FlashMindApp()
    app.run()
