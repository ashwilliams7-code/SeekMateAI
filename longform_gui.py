"""
SeekMate Long-Form Bot Dashboard — Standalone GUI.

Independent dashboard for the long-form external application bot.
Provides Start/Stop/Pause controls, live activity log, application stats,
job history, and configuration management.

Usage:
    python longform_gui.py
"""

import tkinter as tk
from tkinter import ttk, filedialog
import json
import os
import sys
import time
import threading
import subprocess
import webbrowser


# ================================
# PREMIUM COLOR PALETTES
# ================================
COLORS_DARK = {
    "bg_dark": "#0d0d12",
    "bg_card": "#16161d",
    "bg_card_hover": "#1e1e28",
    "bg_input": "#1a1a24",
    "bg_elevated": "#202030",
    "accent_primary": "#4fd1c5",
    "accent_secondary": "#f6ad55",
    "accent_gold": "#d69e2e",
    "accent_purple": "#9f7aea",
    "success": "#48bb78",
    "warning": "#ed8936",
    "danger": "#fc8181",
    "text_primary": "#f7fafc",
    "text_secondary": "#a0aec0",
    "text_muted": "#718096",
    "border": "#2d3748",
    "border_light": "#4a5568",
    "money_green": "#68d391",
    "slider_track": "#2d3748",
    "slider_fill": "#4fd1c5",
    "gpt_highlight": "#f687b3",
    "tab_active": "#4fd1c5",
    "tab_inactive": "#2d3748",
    "tab_hover": "#38b2ac",
}

COLORS = COLORS_DARK.copy()

# ================================
# FONTS
# ================================
FONT_FAMILY = "Segoe UI"
FONT_NORMAL = (FONT_FAMILY, 11)
FONT_BOLD = (FONT_FAMILY, 11, "bold")
FONT_TITLE = (FONT_FAMILY, 13, "bold")
FONT_HEADER = (FONT_FAMILY, 24, "bold")
FONT_SUBHEADER = (FONT_FAMILY, 16, "bold")
FONT_CONSOLE = ("Cascadia Code", 10)
FONT_STATS = (FONT_FAMILY, 32, "bold")
FONT_LABEL = (FONT_FAMILY, 10)
FONT_LABEL_BOLD = (FONT_FAMILY, 10, "bold")
FONT_BUTTON = (FONT_FAMILY, 11, "bold")
FONT_CHIP = (FONT_FAMILY, 9, "bold")


# ================================
# PATHS
# ================================
def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)


def get_data_dir():
    if sys.platform == "darwin":
        data_dir = os.path.expanduser("~/Library/Application Support/SeekMateAI")
    elif sys.platform == "win32":
        data_dir = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "SeekMateAI")
    else:
        data_dir = os.path.expanduser("~/.seekmateai")
    os.makedirs(data_dir, exist_ok=True)
    return data_dir


CONFIG_FILE = resource_path("config.json")
LOG_FILE = os.path.join(get_data_dir(), "longform_log.txt")
CONTROL_FILE = resource_path("longform_control.json")


def load_config():
    if not os.path.exists(CONFIG_FILE):
        return {}
    with open(CONFIG_FILE, "r") as f:
        return json.load(f)


def save_config(data):
    with open(CONFIG_FILE, "w") as f:
        json.dump(data, f, indent=4)


def write_control(pause=None, stop=None):
    data = {"pause": False, "stop": False}
    if os.path.exists(CONTROL_FILE):
        try:
            with open(CONTROL_FILE, "r") as f:
                data.update(json.load(f))
        except:
            pass
    if pause is not None:
        data["pause"] = pause
    if stop is not None:
        data["stop"] = stop
    with open(CONTROL_FILE, "w") as f:
        json.dump(data, f)


# ================================
# WIDGETS (same as config_gui.py)
# ================================
class ModernEntry(tk.Frame):
    def __init__(self, parent, placeholder="", show="", **kwargs):
        super().__init__(parent, bg=COLORS["bg_card"])
        self.entry = tk.Entry(
            self, font=FONT_NORMAL, bg=COLORS["bg_input"], fg=COLORS["text_primary"],
            insertbackground=COLORS["accent_primary"], relief="flat",
            highlightthickness=2, highlightbackground=COLORS["border"],
            highlightcolor=COLORS["accent_primary"], show=show
        )
        self.entry.pack(fill="x", ipady=8, ipadx=10)

    def get(self):
        return self.entry.get()

    def insert(self, index, string):
        self.entry.insert(index, string)

    def delete(self, first, last=None):
        self.entry.delete(first, last)

    def config(self, **kwargs):
        self.entry.config(**kwargs)

    def cget(self, key):
        return self.entry.cget(key)


class ModernButton(tk.Canvas):
    def __init__(self, parent, text="", command=None, style="primary", width=150, height=42, **kwargs):
        super().__init__(parent, width=width, height=height, bg=COLORS["bg_card"],
                         highlightthickness=0, **kwargs)
        self.command = command
        self.text = text
        self.width = width
        self.height = height
        self.style = style
        self.is_hovered = False
        self.is_disabled = False
        self.styles = {
            "primary": {"bg": COLORS["accent_primary"], "hover": "#00b8e6", "fg": "#000000"},
            "success": {"bg": COLORS["success"], "hover": "#00cc6a", "fg": "#000000"},
            "warning": {"bg": COLORS["warning"], "hover": "#e69500", "fg": "#000000"},
            "danger": {"bg": COLORS["danger"], "hover": "#ff3344", "fg": "#ffffff"},
            "dark": {"bg": "#2a2a4a", "hover": "#3a3a5a", "fg": "#ffffff"},
            "disabled": {"bg": "#3a3a4a", "hover": "#3a3a4a", "fg": "#6a6a7a"},
        }
        self.draw_button()
        self.bind("<Enter>", self.on_enter)
        self.bind("<Leave>", self.on_leave)
        self.bind("<Button-1>", self.on_click)

    def draw_button(self):
        self.delete("all")
        style = self.styles.get("disabled" if self.is_disabled else self.style, self.styles["primary"])
        bg = style["hover"] if self.is_hovered and not self.is_disabled else style["bg"]
        r = 8
        self.create_arc(2, 2, 2 + 2*r, 2 + 2*r, start=90, extent=90, fill=bg, outline=bg)
        self.create_arc(self.width-2 - 2*r, 2, self.width-2, 2 + 2*r, start=0, extent=90, fill=bg, outline=bg)
        self.create_arc(2, self.height-2 - 2*r, 2 + 2*r, self.height-2, start=180, extent=90, fill=bg, outline=bg)
        self.create_arc(self.width-2 - 2*r, self.height-2 - 2*r, self.width-2, self.height-2, start=270, extent=90, fill=bg, outline=bg)
        self.create_rectangle(2 + r, 2, self.width-2 - r, self.height-2, fill=bg, outline=bg)
        self.create_rectangle(2, 2 + r, self.width-2, self.height-2 - r, fill=bg, outline=bg)
        self.create_text(self.width // 2, self.height // 2, text=self.text, font=FONT_BUTTON, fill=style["fg"])

    def on_enter(self, e):
        if not self.is_disabled:
            self.is_hovered = True
            self.config(cursor="hand2")
            self.draw_button()

    def on_leave(self, e):
        self.is_hovered = False
        self.config(cursor="")
        self.draw_button()

    def on_click(self, e):
        if self.command and not self.is_disabled:
            self.command()

    def set_disabled(self, disabled):
        self.is_disabled = disabled
        self.draw_button()

    def set_text(self, text):
        self.text = text
        self.draw_button()

    def set_style(self, style):
        self.style = style
        self.draw_button()


class PulsingIndicator(tk.Canvas):
    def __init__(self, parent, size=12, **kwargs):
        super().__init__(parent, width=size+4, height=size+4,
                         bg=COLORS["bg_dark"], highlightthickness=0, **kwargs)
        self.size = size
        self.color = COLORS["text_muted"]
        self.is_pulsing = False
        self.draw()

    def draw(self):
        self.delete("all")
        cx, cy = (self.size + 4) // 2, (self.size + 4) // 2
        if self.is_pulsing:
            g = self.size // 2 + 3
            self.create_oval(cx - g, cy - g, cx + g, cy + g, fill="", outline=self.color, width=2)
        r = self.size // 2
        self.create_oval(cx - r, cy - r, cx + r, cy + r, fill=self.color, outline="")

    def set_status(self, status):
        colors = {"idle": COLORS["text_muted"], "running": COLORS["success"],
                  "paused": COLORS["warning"], "stopped": COLORS["danger"]}
        self.color = colors.get(status, COLORS["text_muted"])
        self.is_pulsing = status == "running"
        self.draw()
        if self.is_pulsing:
            self.pulse()

    def pulse(self):
        if self.is_pulsing:
            self.draw()
            self.after(100, self.pulse)


class ModernSlider(tk.Frame):
    def __init__(self, parent, label="", min_val=0, max_val=100, default=50,
                 unit="", description="", on_change=None, **kwargs):
        super().__init__(parent, bg=COLORS["bg_card"], **kwargs)
        self.min_val = min_val
        self.max_val = max_val
        self.unit = unit
        self.on_change = on_change

        header = tk.Frame(self, bg=COLORS["bg_card"])
        header.pack(fill="x", pady=(0, 8))
        tk.Label(header, text=label, bg=COLORS["bg_card"],
                 fg=COLORS["text_primary"], font=FONT_BOLD).pack(side="left")
        self.value_label = tk.Label(header, text=f"{default}{unit}",
                                    bg=COLORS["bg_card"], fg=COLORS["accent_primary"], font=FONT_BOLD)
        self.value_label.pack(side="right")

        if description:
            tk.Label(self, text=description, bg=COLORS["bg_card"],
                     fg=COLORS["text_muted"], font=FONT_LABEL,
                     wraplength=350, justify="left").pack(fill="x", pady=(0, 8))

        self.track_frame = tk.Frame(self, bg=COLORS["bg_card"], height=40)
        self.track_frame.pack(fill="x")
        self.track_frame.pack_propagate(False)
        self.canvas = tk.Canvas(self.track_frame, bg=COLORS["bg_card"],
                                highlightthickness=0, height=40)
        self.canvas.pack(fill="x", expand=True)
        self.value = default
        self.dragging = False
        self.canvas.bind("<Configure>", lambda e: self.draw_slider())
        self.canvas.bind("<Button-1>", self.on_click)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", lambda e: setattr(self, 'dragging', False))

        lf = tk.Frame(self, bg=COLORS["bg_card"])
        lf.pack(fill="x", pady=(4, 0))
        tk.Label(lf, text="Less", bg=COLORS["bg_card"],
                 fg=COLORS["text_muted"], font=("Segoe UI", 9)).pack(side="left")
        tk.Label(lf, text="More", bg=COLORS["bg_card"],
                 fg=COLORS["text_muted"], font=("Segoe UI", 9)).pack(side="right")

    def draw_slider(self):
        self.canvas.delete("all")
        w = self.canvas.winfo_width()
        h = self.canvas.winfo_height()
        if w < 10: return
        pad = 15
        ty = h // 2
        th = 8
        self.canvas.create_rectangle(pad, ty - th // 2, w - pad, ty + th // 2,
                                     fill=COLORS["slider_track"], outline="")
        ratio = (self.value - self.min_val) / (self.max_val - self.min_val)
        tx = pad + ratio * (w - 2 * pad)
        self.canvas.create_rectangle(pad, ty - th // 2, tx, ty + th // 2,
                                     fill=COLORS["accent_primary"], outline="")
        tr = 10
        self.canvas.create_oval(tx - tr, ty - tr, tx + tr, ty + tr,
                                fill=COLORS["accent_primary"], outline=COLORS["text_primary"], width=2)
        self.canvas.create_oval(tx - tr - 3, ty - tr - 3, tx + tr + 3, ty + tr + 3,
                                fill="", outline=COLORS["accent_primary"], width=1)

    def on_click(self, event):
        self._update(event.x)

    def on_drag(self, event):
        self.dragging = True
        self._update(event.x)

    def _update(self, x):
        w = self.canvas.winfo_width()
        pad = 15
        ratio = max(0, min(1, (x - pad) / (w - 2 * pad)))
        self.value = int(self.min_val + ratio * (self.max_val - self.min_val))
        self.value_label.config(text=f"{self.value}{self.unit}")
        self.draw_slider()
        if self.on_change:
            self.on_change(self.value)

    def get(self):
        return self.value

    def set(self, value):
        self.value = max(self.min_val, min(self.max_val, value))
        self.value_label.config(text=f"{self.value}{self.unit}")
        self.draw_slider()


class CollapsibleCard(tk.Frame):
    def __init__(self, parent, title="", icon="", default_expanded=True, **kwargs):
        super().__init__(parent, bg=COLORS["bg_card"], **kwargs)
        self.is_expanded = default_expanded
        self.header = tk.Frame(self, bg=COLORS["bg_card"], cursor="hand2")
        self.header.pack(fill="x", padx=20, pady=(15, 0))
        self.toggle_btn = tk.Label(self.header, text="▼" if self.is_expanded else "▶",
                                    bg=COLORS["bg_card"], fg=COLORS["text_muted"],
                                    font=("Segoe UI", 10), cursor="hand2")
        self.toggle_btn.pack(side="left", padx=(0, 8))
        tk.Label(self.header, text=f"{icon}  {title}",
                 bg=COLORS["bg_card"], fg=COLORS["text_primary"],
                 font=FONT_TITLE).pack(side="left")
        self.content = tk.Frame(self, bg=COLORS["bg_card"])
        if self.is_expanded:
            self.content.pack(fill="x", padx=20, pady=(15, 20))
        self.header.bind("<Button-1>", self.toggle)
        self.toggle_btn.bind("<Button-1>", self.toggle)
        for c in self.header.winfo_children():
            c.bind("<Button-1>", self.toggle)
        self.header.bind("<Enter>", lambda e: self.toggle_btn.config(fg=COLORS["accent_primary"]))
        self.header.bind("<Leave>", lambda e: self.toggle_btn.config(fg=COLORS["text_muted"]))

    def toggle(self, event=None):
        self.is_expanded = not self.is_expanded
        self.toggle_btn.config(text="▼" if self.is_expanded else "▶")
        if self.is_expanded:
            self.content.pack(fill="x", padx=20, pady=(15, 20))
        else:
            self.content.pack_forget()

    def get_content(self):
        return self.content


# ================================
# MAIN DASHBOARD
# ================================
class LongFormDashboard:
    def __init__(self, root):
        self.root = root
        self.root.title("SeekMate — Long-Form Bot")
        self.root.geometry("900x900")
        self.root.configure(bg=COLORS["bg_dark"])
        self.root.minsize(750, 700)

        self.config = load_config()
        self.bot_process = None
        self.paused = False
        self.start_time = None
        self.timer_running = False
        self.run_counter = 0

        self.build_ui()
        self.refresh_stats()
        self.refresh_history()

    def build_ui(self):
        # Main scrollable container
        outer = tk.Frame(self.root, bg=COLORS["bg_dark"])
        outer.pack(fill="both", expand=True)

        canvas = tk.Canvas(outer, bg=COLORS["bg_dark"], highlightthickness=0)
        scrollbar = ttk.Scrollbar(outer, orient="vertical", command=canvas.yview)
        self.scroll_frame = tk.Frame(canvas, bg=COLORS["bg_dark"])

        self.scroll_frame.bind("<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=self.scroll_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Mouse wheel scrolling
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        canvas.bind_all("<MouseWheel>", _on_mousewheel)

        self.build_header(self.scroll_frame)
        self.build_controls(self.scroll_frame)
        self.build_stats_panel(self.scroll_frame)
        self.build_log_panel(self.scroll_frame)
        self.build_history_panel(self.scroll_frame)
        self.build_settings_panel(self.scroll_frame)

    # --- HEADER ---
    def build_header(self, parent):
        header = tk.Frame(parent, bg=COLORS["bg_dark"])
        header.pack(fill="x", padx=25, pady=(20, 10))

        left = tk.Frame(header, bg=COLORS["bg_dark"])
        left.pack(side="left")

        self.status_indicator = PulsingIndicator(left, size=14)
        self.status_indicator.pack(side="left", padx=(0, 12))

        tk.Label(left, text="LONG-FORM BOT", bg=COLORS["bg_dark"],
                 fg=COLORS["text_primary"], font=FONT_HEADER).pack(side="left")

        self.header_status = tk.Label(header, text="STOPPED", bg=COLORS["bg_dark"],
                                       fg=COLORS["danger"], font=FONT_SUBHEADER)
        self.header_status.pack(side="right")

    # --- CONTROLS ---
    def build_controls(self, parent):
        frame = tk.Frame(parent, bg=COLORS["bg_dark"])
        frame.pack(fill="x", padx=25, pady=(5, 15))

        self.start_btn = ModernButton(frame, text="▶  START", command=self.start_bot,
                                       style="success", width=160, height=44)
        self.start_btn.pack(side="left", padx=(0, 10))

        self.pause_btn = ModernButton(frame, text="⏸  PAUSE", command=self.pause_bot,
                                       style="warning", width=160, height=44)
        self.pause_btn.pack(side="left", padx=(0, 10))

        self.stop_btn = ModernButton(frame, text="■  STOP", command=self.stop_bot,
                                      style="danger", width=160, height=44)
        self.stop_btn.pack(side="left")

    # --- STATS PANEL ---
    def build_stats_panel(self, parent):
        stats_frame = tk.Frame(parent, bg=COLORS["bg_dark"])
        stats_frame.pack(fill="x", padx=25, pady=(0, 15))

        # 4 stat cards
        cards_row = tk.Frame(stats_frame, bg=COLORS["bg_dark"])
        cards_row.pack(fill="x")

        self.stat_submitted = self._build_stat_card(cards_row, "SUBMITTED", "0", COLORS["success"])
        self.stat_submitted.pack(side="left", fill="both", expand=True, padx=(0, 6))

        self.stat_failed = self._build_stat_card(cards_row, "FAILED", "0", COLORS["danger"])
        self.stat_failed.pack(side="left", fill="both", expand=True, padx=(6, 6))

        self.stat_rate = self._build_stat_card(cards_row, "SUCCESS %", "0%", COLORS["accent_primary"])
        self.stat_rate.pack(side="left", fill="both", expand=True, padx=(6, 6))

        self.stat_duration = self._build_stat_card(cards_row, "AVG DURATION", "0s", COLORS["accent_secondary"])
        self.stat_duration.pack(side="left", fill="both", expand=True, padx=(6, 0))

        # Session info row
        session_row = tk.Frame(stats_frame, bg=COLORS["bg_card"])
        session_row.pack(fill="x", pady=(10, 0))

        session_inner = tk.Frame(session_row, bg=COLORS["bg_card"])
        session_inner.pack(fill="x", padx=20, pady=12)

        tk.Label(session_inner, text="⏱ Session:", bg=COLORS["bg_card"],
                 fg=COLORS["text_muted"], font=FONT_LABEL).pack(side="left")
        self.session_time_label = tk.Label(session_inner, text="00:00:00",
                                            bg=COLORS["bg_card"], fg=COLORS["text_primary"],
                                            font=FONT_BOLD)
        self.session_time_label.pack(side="left", padx=(5, 20))

        tk.Label(session_inner, text="This Run:", bg=COLORS["bg_card"],
                 fg=COLORS["text_muted"], font=FONT_LABEL).pack(side="left")
        self.run_counter_label = tk.Label(session_inner, text="0/100",
                                           bg=COLORS["bg_card"], fg=COLORS["accent_primary"],
                                           font=FONT_BOLD)
        self.run_counter_label.pack(side="left", padx=(5, 20))

        # Refresh button
        tk.Button(session_inner, text="🔄 Refresh", command=self._refresh_all,
                  bg=COLORS["bg_card"], fg=COLORS["accent_primary"],
                  font=FONT_LABEL, relief="flat", cursor="hand2",
                  activebackground=COLORS["bg_card"]).pack(side="right")

    def _build_stat_card(self, parent, title, value, color):
        card = tk.Frame(parent, bg=COLORS["bg_card"])
        inner = tk.Frame(card, bg=COLORS["bg_card"])
        inner.pack(fill="both", expand=True, padx=15, pady=15)
        tk.Label(inner, text=title, bg=COLORS["bg_card"],
                 fg=COLORS["text_muted"], font=FONT_LABEL).pack(anchor="w")
        lbl = tk.Label(inner, text=value, bg=COLORS["bg_card"],
                       fg=color, font=(FONT_FAMILY, 26, "bold"))
        lbl.pack(anchor="w", pady=(4, 0))
        card._value_label = lbl
        return card

    # --- LOG PANEL ---
    def build_log_panel(self, parent):
        self.log_card = tk.Frame(parent, bg=COLORS["bg_card"])
        self.log_card.pack(fill="both", expand=True, padx=25, pady=(0, 15))
        self.log_expanded = True

        header = tk.Frame(self.log_card, bg=COLORS["bg_card"])
        header.pack(fill="x", padx=20, pady=(15, 10))

        left = tk.Frame(header, bg=COLORS["bg_card"])
        left.pack(side="left")

        self.log_collapse_btn = tk.Button(left, text="▼", font=("Segoe UI", 12),
                                           bg=COLORS["bg_card"], fg=COLORS["accent_primary"],
                                           activebackground=COLORS["bg_card"],
                                           relief="flat", padx=4, cursor="hand2",
                                           command=self.toggle_log)
        self.log_collapse_btn.pack(side="left", padx=(0, 8))

        tk.Label(left, text="Activity Log", bg=COLORS["bg_card"],
                 fg=COLORS["text_primary"], font=FONT_TITLE).pack(side="left")

        self.log_count_label = tk.Label(left, text="(0 lines)", bg=COLORS["bg_card"],
                                         fg=COLORS["text_muted"], font=FONT_LABEL)
        self.log_count_label.pack(side="left", padx=(10, 0))

        # Controls
        ctrl = tk.Frame(header, bg=COLORS["bg_card"])
        ctrl.pack(side="right")

        tk.Button(ctrl, text="Clear", bg=COLORS["bg_card"], fg=COLORS["text_muted"],
                  font=FONT_LABEL, relief="flat", cursor="hand2",
                  activebackground=COLORS["bg_card"],
                  command=lambda: self.console.delete("1.0", tk.END)).pack(side="right", padx=(8, 0))

        # Log text area
        self.log_frame = tk.Frame(self.log_card, bg=COLORS["bg_card"])
        self.log_frame.pack(fill="both", expand=True, padx=20, pady=(0, 15))

        self.console = tk.Text(self.log_frame, bg=COLORS["bg_dark"], fg=COLORS["text_secondary"],
                               wrap="word", font=FONT_CONSOLE, relief="flat",
                               insertbackground=COLORS["accent_primary"],
                               selectbackground=COLORS["accent_secondary"],
                               height=15)
        self.console.pack(side="left", fill="both", expand=True)

        scrollbar = ttk.Scrollbar(self.log_frame, command=self.console.yview)
        scrollbar.pack(side="right", fill="y")
        self.console.configure(yscrollcommand=scrollbar.set)

        # Color tags
        self.console.tag_config("ERROR", foreground=COLORS["danger"])
        self.console.tag_config("SUCCESS", foreground=COLORS["success"])
        self.console.tag_config("INFO", foreground=COLORS["text_secondary"])
        self.console.tag_config("timestamp", foreground=COLORS["text_muted"])
        self.console.tag_config("GPT", foreground="#FF6EC7", font=("Cascadia Code", 10, "bold"))
        self.console.tag_config("ATS", foreground=COLORS["accent_primary"])
        self.console.tag_config("LONGFORM", foreground=COLORS["accent_secondary"])

    def toggle_log(self):
        self.log_expanded = not self.log_expanded
        self.log_collapse_btn.config(text="▼" if self.log_expanded else "▶")
        if self.log_expanded:
            self.log_frame.pack(fill="both", expand=True, padx=20, pady=(0, 15))
            self.log_card.pack(fill="both", expand=True, padx=25, pady=(0, 15))
        else:
            self.log_frame.pack_forget()
            self.log_card.pack(fill="x", expand=False, padx=25, pady=(0, 15))

    # --- HISTORY PANEL ---
    def build_history_panel(self, parent):
        card = CollapsibleCard(parent, title="Application History", icon="📋", default_expanded=False)
        card.pack(fill="x", padx=25, pady=(0, 15))
        content = card.get_content()

        # Search
        search_frame = tk.Frame(content, bg=COLORS["bg_card"])
        search_frame.pack(fill="x", pady=(0, 10))

        self.history_search = tk.Entry(search_frame, font=FONT_NORMAL, bg=COLORS["bg_input"],
                                        fg=COLORS["text_primary"], insertbackground=COLORS["accent_primary"],
                                        relief="flat", highlightthickness=2,
                                        highlightbackground=COLORS["border"],
                                        highlightcolor=COLORS["accent_primary"])
        self.history_search.pack(side="left", fill="x", expand=True, ipady=6)
        self.history_search.insert(0, "Search jobs...")
        self.history_search.bind("<FocusIn>", lambda e: self.history_search.delete(0, tk.END)
                                  if self.history_search.get() == "Search jobs..." else None)
        self.history_search.bind("<KeyRelease>", lambda e: self.refresh_history())

        tk.Button(search_frame, text="🔄", command=self.refresh_history,
                  bg=COLORS["bg_card"], fg=COLORS["accent_primary"],
                  font=("Segoe UI", 12), relief="flat", cursor="hand2",
                  activebackground=COLORS["bg_card"]).pack(side="right", padx=(10, 0))

        # Scrollable job list
        list_frame = tk.Frame(content, bg=COLORS["bg_card"])
        list_frame.pack(fill="both", expand=True)

        self.history_canvas = tk.Canvas(list_frame, bg=COLORS["bg_dark"],
                                         highlightthickness=0, height=200)
        h_scroll = ttk.Scrollbar(list_frame, orient="vertical", command=self.history_canvas.yview)
        self.history_list_frame = tk.Frame(self.history_canvas, bg=COLORS["bg_dark"])
        self.history_list_frame.bind("<Configure>",
            lambda e: self.history_canvas.configure(scrollregion=self.history_canvas.bbox("all")))
        self.history_canvas.create_window((0, 0), window=self.history_list_frame, anchor="nw")
        self.history_canvas.configure(yscrollcommand=h_scroll.set)
        self.history_canvas.pack(side="left", fill="both", expand=True)
        h_scroll.pack(side="right", fill="y")

    # --- SETTINGS PANEL ---
    def build_settings_panel(self, parent):
        card = CollapsibleCard(parent, title="Settings", icon="⚙️", default_expanded=False)
        card.pack(fill="x", padx=25, pady=(0, 25))
        content = card.get_content()

        # Documents section
        tk.Label(content, text="📁 DOCUMENTS", bg=COLORS["bg_card"],
                 fg=COLORS["text_secondary"], font=FONT_LABEL_BOLD).pack(anchor="w", pady=(0, 8))

        docs_row = tk.Frame(content, bg=COLORS["bg_card"])
        docs_row.pack(fill="x", pady=(0, 8))
        tk.Label(docs_row, text="Documents Directory:", bg=COLORS["bg_card"],
                 fg=COLORS["text_muted"], font=FONT_LABEL).pack(anchor="w")
        dir_row = tk.Frame(docs_row, bg=COLORS["bg_card"])
        dir_row.pack(fill="x")
        self.docs_dir_entry = ModernEntry(dir_row)
        self.docs_dir_entry.pack(side="left", fill="x", expand=True)
        self.docs_dir_entry.insert(0, self.config.get("DOCUMENTS_DIR", "./documents"))
        tk.Button(dir_row, text="Browse", command=self._browse_docs_dir,
                  bg=COLORS["bg_elevated"], fg=COLORS["text_primary"],
                  font=FONT_LABEL, relief="flat", cursor="hand2",
                  padx=12, pady=4).pack(side="right", padx=(8, 0))

        tk.Label(content, text="Default Resume:", bg=COLORS["bg_card"],
                 fg=COLORS["text_muted"], font=FONT_LABEL).pack(anchor="w", pady=(4, 0))
        self.resume_entry = ModernEntry(content)
        self.resume_entry.pack(fill="x", pady=(0, 12))
        self.resume_entry.insert(0, self.config.get("DEFAULT_RESUME", ""))

        # Separator
        tk.Frame(content, bg=COLORS["border"], height=1).pack(fill="x", pady=12)

        # Email section
        tk.Label(content, text="📧 EMAIL VERIFICATION", bg=COLORS["bg_card"],
                 fg=COLORS["text_secondary"], font=FONT_LABEL_BOLD).pack(anchor="w", pady=(0, 8))

        tk.Label(content, text="IMAP Server:", bg=COLORS["bg_card"],
                 fg=COLORS["text_muted"], font=FONT_LABEL).pack(anchor="w")
        self.imap_entry = ModernEntry(content)
        self.imap_entry.pack(fill="x", pady=(0, 8))
        self.imap_entry.insert(0, self.config.get("EMAIL_IMAP_SERVER", "imap.gmail.com"))

        tk.Label(content, text="App Password:", bg=COLORS["bg_card"],
                 fg=COLORS["text_muted"], font=FONT_LABEL).pack(anchor="w")
        pw_row = tk.Frame(content, bg=COLORS["bg_card"])
        pw_row.pack(fill="x", pady=(0, 12))
        self.email_pw_entry = ModernEntry(pw_row, show="*")
        self.email_pw_entry.pack(side="left", fill="x", expand=True)
        self.email_pw_entry.insert(0, self.config.get("EMAIL_APP_PASSWORD", ""))
        self.email_pw_visible = False
        tk.Button(pw_row, text="👁", command=self.toggle_email_pw,
                  bg=COLORS["bg_card"], fg=COLORS["text_muted"],
                  font=("Segoe UI", 12), relief="flat", cursor="hand2",
                  activebackground=COLORS["bg_card"]).pack(side="right", padx=(8, 0))

        # Separator
        tk.Frame(content, bg=COLORS["border"], height=1).pack(fill="x", pady=12)

        # Profile section
        tk.Label(content, text="👤 MASTER PROFILE", bg=COLORS["bg_card"],
                 fg=COLORS["text_secondary"], font=FONT_LABEL_BOLD).pack(anchor="w", pady=(0, 8))

        prof_row = tk.Frame(content, bg=COLORS["bg_card"])
        prof_row.pack(fill="x", pady=(0, 8))
        tk.Label(prof_row, text="Profile Path:", bg=COLORS["bg_card"],
                 fg=COLORS["text_muted"], font=FONT_LABEL).pack(anchor="w")
        self.profile_entry = ModernEntry(prof_row)
        self.profile_entry.pack(fill="x")
        self.profile_entry.insert(0, self.config.get("MASTER_PROFILE_PATH", "./master_profile.json"))

        self.profile_preview = tk.Label(content, text="", bg=COLORS["bg_card"],
                                         fg=COLORS["text_muted"], font=FONT_LABEL,
                                         wraplength=500, justify="left")
        self.profile_preview.pack(anchor="w", pady=(4, 12))
        self._refresh_profile_preview()

        # Separator
        tk.Frame(content, bg=COLORS["border"], height=1).pack(fill="x", pady=12)

        # Advanced section
        tk.Label(content, text="⚙️ ADVANCED", bg=COLORS["bg_card"],
                 fg=COLORS["text_secondary"], font=FONT_LABEL_BOLD).pack(anchor="w", pady=(0, 8))

        self.max_pages_slider = ModernSlider(content, label="Max Pages per Application",
                                              min_val=1, max_val=20,
                                              default=self.config.get("LONGFORM_MAX_PAGES", 10))
        self.max_pages_slider.pack(fill="x", pady=(0, 12))

        self.retry_slider = ModernSlider(content, label="Retry Limit",
                                          min_val=1, max_val=5,
                                          default=self.config.get("LONGFORM_RETRY_LIMIT", 3))
        self.retry_slider.pack(fill="x", pady=(0, 12))

        self.timeout_slider = ModernSlider(content, label="Timeout (seconds)",
                                            min_val=30, max_val=600,
                                            default=self.config.get("LONGFORM_TIMEOUT", 180), unit="s")
        self.timeout_slider.pack(fill="x", pady=(0, 12))

        tk.Label(content, text="Database Path:", bg=COLORS["bg_card"],
                 fg=COLORS["text_muted"], font=FONT_LABEL).pack(anchor="w")
        self.db_path_entry = ModernEntry(content)
        self.db_path_entry.pack(fill="x")
        self.db_path_entry.insert(0, self.config.get("LONGFORM_DB_PATH", "./seekmate.db"))

    # ================================
    # BOT CONTROL
    # ================================
    def start_bot(self):
        self.save_config()

        # Clear log file
        try:
            if os.path.exists(LOG_FILE):
                os.remove(LOG_FILE)
        except:
            pass

        # Reset control
        write_control(pause=False, stop=False)
        time.sleep(0.3)

        # Clear console
        self.console.delete("1.0", tk.END)
        self.run_counter = 0

        # Update UI
        self.start_btn.set_text("RUNNING...")
        self.start_btn.set_disabled(True)
        self.status_indicator.set_status("running")
        self.header_status.config(text="RUNNING", fg=COLORS["success"])

        # Start timer
        self.start_time = time.time()
        self.timer_running = True
        self.update_timer()

        # Launch bot subprocess
        try:
            bot_script = resource_path("longform_bot.py")
            if sys.platform == "win32":
                self.bot_process = subprocess.Popen(
                    [sys.executable, bot_script],
                    creationflags=subprocess.CREATE_NO_WINDOW
                )
            else:
                self.bot_process = subprocess.Popen(
                    [sys.executable, bot_script]
                )
            self.log("INFO", f"Long-form bot started (PID: {self.bot_process.pid})")
        except Exception as e:
            self.log("ERROR", f"Failed to start bot: {e}")
            self._reset_ui()
            return

        # Start log tailing
        threading.Thread(target=self.tail_log, daemon=True).start()

        # Start stats refresh loop
        self._auto_refresh_stats()

    def pause_bot(self):
        self.paused = not self.paused
        write_control(pause=self.paused)

        if self.paused:
            self.log("INFO", "Bot paused.")
            self.status_indicator.set_status("paused")
            self.header_status.config(text="PAUSED", fg=COLORS["warning"])
            self.pause_btn.set_text("▶  RESUME")
        else:
            self.log("INFO", "Bot resumed.")
            self.status_indicator.set_status("running")
            self.header_status.config(text="RUNNING", fg=COLORS["success"])
            self.pause_btn.set_text("⏸  PAUSE")

    def stop_bot(self):
        write_control(stop=True)
        self.paused = False
        self.timer_running = False

        self.log("INFO", "Stop signal sent...")

        # Kill process
        if self.bot_process:
            try:
                self.bot_process.terminate()
                self.bot_process.wait(timeout=5)
            except:
                try:
                    self.bot_process.kill()
                except:
                    pass
            self.bot_process = None

        # Kill Chrome (longform profile)
        if sys.platform == "win32":
            try:
                subprocess.run(["taskkill", "/F", "/IM", "chromedriver.exe"],
                               capture_output=True, timeout=5)
            except:
                pass

        self._reset_ui()
        self.refresh_stats()
        self.refresh_history()

    def _reset_ui(self):
        self.start_btn.set_text("▶  START")
        self.start_btn.set_disabled(False)
        self.pause_btn.set_text("⏸  PAUSE")
        self.status_indicator.set_status("stopped")
        self.header_status.config(text="STOPPED", fg=COLORS["danger"])

    # ================================
    # LOG TAILING
    # ================================
    def tail_log(self):
        # Wait for log file
        timeout = 30
        start = time.time()
        while not os.path.exists(LOG_FILE):
            if time.time() - start > timeout:
                self.log("ERROR", "Log file not created — bot may have failed to start")
                return
            time.sleep(0.2)

        line_count = 0
        with open(LOG_FILE, "r", encoding="utf-8") as f:
            while True:
                line = f.readline()
                if not line:
                    # Check if process still alive
                    if self.bot_process and self.bot_process.poll() is not None:
                        self.log("INFO", "Bot process has exited.")
                        self.root.after(0, self._reset_ui)
                        self.root.after(0, self.refresh_stats)
                        self.root.after(0, self.refresh_history)
                        break
                    time.sleep(0.1)
                    continue

                clean = line.strip()
                if not clean:
                    continue

                line_count += 1

                # Determine tag
                tag = "INFO"
                upper = clean.upper()
                if "ERROR" in upper or "FAILED" in upper or "[-]" in clean:
                    tag = "ERROR"
                elif "SUCCESS" in upper or "[+]" in clean or "SUBMITTED" in upper:
                    tag = "SUCCESS"
                elif "GPT" in upper:
                    tag = "GPT"
                elif "[ATS]" in clean:
                    tag = "ATS"
                elif "[LongForm]" in clean:
                    tag = "LONGFORM"

                # Parse submission counter
                if "Successful submissions:" in clean:
                    try:
                        num = int(clean.split(":")[-1].strip())
                        self.run_counter = num
                        max_jobs = self.config.get("MAX_JOBS", 100)
                        self.root.after(0, lambda n=num, m=max_jobs:
                                         self.run_counter_label.config(text=f"{n}/{m}"))
                    except:
                        pass

                # Insert into console
                self.root.after(0, lambda c=clean, t=tag, lc=line_count:
                                 self._insert_log(c, t, lc))

    def _insert_log(self, text, tag, line_count):
        self.console.insert(tk.END, text + "\n", tag)
        self.console.see(tk.END)
        self.log_count_label.config(text=f"({line_count} lines)")

    def log(self, level, message):
        ts = time.strftime("%H:%M:%S")
        self.console.insert(tk.END, f"[{ts}] {message}\n", level)
        self.console.see(tk.END)

    # ================================
    # TIMER
    # ================================
    def update_timer(self):
        if self.timer_running and self.start_time:
            elapsed = int(time.time() - self.start_time)
            h, m, s = elapsed // 3600, (elapsed % 3600) // 60, elapsed % 60
            self.session_time_label.config(text=f"{h:02d}:{m:02d}:{s:02d}")
            self.root.after(1000, self.update_timer)

    # ================================
    # STATS & HISTORY
    # ================================
    def refresh_stats(self):
        try:
            from longform.database import Database
            db_path = self.config.get("LONGFORM_DB_PATH", "./seekmate.db")
            if not os.path.exists(db_path):
                return
            db = Database(db_path)
            stats = db.get_stats()
            db.close()

            submitted = stats.get("total_submitted", 0)
            failed = stats.get("total_failed", 0)
            total = submitted + failed
            rate = f"{int(submitted / total * 100)}%" if total > 0 else "0%"
            avg_dur = stats.get("avg_duration_seconds", 0)
            dur_str = f"{avg_dur:.0f}s" if avg_dur else "0s"

            self.stat_submitted._value_label.config(text=str(submitted))
            self.stat_failed._value_label.config(text=str(failed))
            self.stat_rate._value_label.config(text=rate)
            self.stat_duration._value_label.config(text=dur_str)
        except Exception as e:
            pass

    def refresh_history(self):
        try:
            from longform.database import Database
            db_path = self.config.get("LONGFORM_DB_PATH", "./seekmate.db")
            if not os.path.exists(db_path):
                return
            db = Database(db_path)
            jobs = db.get_recent_jobs(limit=50)
            db.close()
        except Exception:
            jobs = []

        # Filter by search
        search_text = self.history_search.get().strip().lower()
        if search_text and search_text != "search jobs...":
            jobs = [j for j in jobs if search_text in (j.get("title", "") + " " + j.get("company", "")).lower()]

        # Clear existing
        for w in self.history_list_frame.winfo_children():
            w.destroy()

        if not jobs:
            tk.Label(self.history_list_frame, text="No applications yet",
                     bg=COLORS["bg_dark"], fg=COLORS["text_muted"],
                     font=FONT_LABEL).pack(pady=20)
            return

        for job in jobs:
            self._build_history_card(job)

    def _build_history_card(self, job):
        card = tk.Frame(self.history_list_frame, bg=COLORS["bg_card"])
        card.pack(fill="x", pady=(0, 4), padx=4)
        inner = tk.Frame(card, bg=COLORS["bg_card"])
        inner.pack(fill="x", padx=12, pady=8)

        # Title row
        title_row = tk.Frame(inner, bg=COLORS["bg_card"])
        title_row.pack(fill="x")

        title = job.get("title", "Unknown")
        tk.Label(title_row, text=title, bg=COLORS["bg_card"],
                 fg=COLORS["text_primary"], font=FONT_BOLD).pack(side="left")

        # Status badge
        status = job.get("status", "unknown")
        status_colors = {"applied": COLORS["success"], "failed": COLORS["danger"],
                         "attempted": COLORS["warning"], "opened": COLORS["accent_primary"],
                         "discovered": COLORS["text_muted"]}
        badge_color = status_colors.get(status, COLORS["text_muted"])
        tk.Label(title_row, text=f" {status.upper()} ", bg=badge_color,
                 fg="#000000", font=FONT_CHIP).pack(side="right", padx=2)

        # Detail row
        detail_row = tk.Frame(inner, bg=COLORS["bg_card"])
        detail_row.pack(fill="x", pady=(2, 0))

        company = job.get("company", "")
        ats = job.get("ats_portal", "")
        dur = job.get("duration_seconds")
        pages = job.get("pages_completed")

        detail_parts = [company]
        if ats:
            detail_parts.append(f"ATS: {ats}")
        if dur:
            detail_parts.append(f"{dur:.0f}s")
        if pages:
            detail_parts.append(f"{pages} pages")

        detail_text = "  |  ".join(filter(None, detail_parts))
        tk.Label(detail_row, text=detail_text, bg=COLORS["bg_card"],
                 fg=COLORS["text_muted"], font=FONT_LABEL).pack(side="left")

        # Make card clickable
        url = job.get("job_url", "")
        if url:
            card.bind("<Button-1>", lambda e, u=url: webbrowser.open(u))
            card.config(cursor="hand2")
            for child in card.winfo_children():
                child.bind("<Button-1>", lambda e, u=url: webbrowser.open(u))

    def _auto_refresh_stats(self):
        if self.timer_running:
            self.refresh_stats()
            self.root.after(10000, self._auto_refresh_stats)  # Every 10s

    def _refresh_all(self):
        self.refresh_stats()
        self.refresh_history()

    # ================================
    # SETTINGS HELPERS
    # ================================
    def toggle_email_pw(self):
        self.email_pw_visible = not self.email_pw_visible
        self.email_pw_entry.config(show="" if self.email_pw_visible else "*")

    def _browse_docs_dir(self):
        d = filedialog.askdirectory()
        if d:
            self.docs_dir_entry.delete(0, tk.END)
            self.docs_dir_entry.insert(0, d)

    def _refresh_profile_preview(self):
        try:
            path = self.config.get("MASTER_PROFILE_PATH", "./master_profile.json")
            if os.path.exists(path):
                with open(path, "r") as f:
                    profile = json.load(f)
                personal = profile.get("personal", {})
                name = personal.get("full_name", "Not set")
                loc = personal.get("location", "")
                work = len(profile.get("work_history", []))
                skills = len(profile.get("skills", {}).get("technical", []))
                self.profile_preview.config(
                    text=f"Name: {name} | Location: {loc} | Work History: {work} entries | Skills: {skills}")
            else:
                self.profile_preview.config(text="Profile file not found")
        except Exception:
            self.profile_preview.config(text="Could not load profile")

    def save_config(self):
        self.config["DOCUMENTS_DIR"] = self.docs_dir_entry.get()
        self.config["DEFAULT_RESUME"] = self.resume_entry.get()
        self.config["EMAIL_IMAP_SERVER"] = self.imap_entry.get()
        self.config["EMAIL_APP_PASSWORD"] = self.email_pw_entry.get()
        self.config["MASTER_PROFILE_PATH"] = self.profile_entry.get()
        self.config["LONGFORM_MAX_PAGES"] = self.max_pages_slider.get()
        self.config["LONGFORM_RETRY_LIMIT"] = self.retry_slider.get()
        self.config["LONGFORM_TIMEOUT"] = self.timeout_slider.get()
        self.config["LONGFORM_DB_PATH"] = self.db_path_entry.get()
        self.config["ENABLE_LONGFORM"] = True
        save_config(self.config)


# ================================
# ENTRY POINT
# ================================
def main():
    root = tk.Tk()

    # Set dark title bar on Windows
    try:
        import ctypes
        root.update()
        hwnd = ctypes.windll.user32.GetParent(root.winfo_id())
        DWMWA_USE_IMMERSIVE_DARK_MODE = 20
        ctypes.windll.dwmapi.DwmSetWindowAttribute(
            hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE,
            ctypes.byref(ctypes.c_int(1)), ctypes.sizeof(ctypes.c_int))
    except:
        pass

    app = LongFormDashboard(root)
    root.mainloop()


if __name__ == "__main__":
    main()
