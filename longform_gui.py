"""
SeekMate Long-Form Bot Dashboard — Premium Standalone GUI.

Complete overhaul with:
- Two-column layout (live visualization + stats/log)
- Real-time bot pipeline visualization
- Claude Code AI status panel
- Analytics with trend bars and ATS breakdown
- Color-coded activity log with filters
- Application history with search

Usage:
    python longform_gui.py
"""

import tkinter as tk
from tkinter import ttk, filedialog
import json
import os
import sys
import time
import math
import threading
import subprocess
import webbrowser
import re
from datetime import datetime


# ================================
# PREMIUM COLOR PALETTE
# ================================
COLORS = {
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
    "pipeline_bg": "#12121a",
    "pipeline_active": "#4fd1c5",
    "pipeline_done": "#48bb78",
    "pipeline_waiting": "#2d3748",
    "ai_glow": "#9f7aea",
}

FONT_FAMILY = "Segoe UI"
FONT_NORMAL = (FONT_FAMILY, 11)
FONT_BOLD = (FONT_FAMILY, 11, "bold")
FONT_TITLE = (FONT_FAMILY, 13, "bold")
FONT_HEADER = (FONT_FAMILY, 22, "bold")
FONT_SUBHEADER = (FONT_FAMILY, 15, "bold")
FONT_STATS = (FONT_FAMILY, 28, "bold")
FONT_LABEL = (FONT_FAMILY, 10)
FONT_LABEL_BOLD = (FONT_FAMILY, 10, "bold")
FONT_BUTTON = (FONT_FAMILY, 11, "bold")
FONT_CONSOLE = ("Cascadia Code", 10)
FONT_CHIP = (FONT_FAMILY, 9, "bold")
FONT_SMALL = (FONT_FAMILY, 9)
FONT_PIPELINE = (FONT_FAMILY, 9, "bold")


# ================================
# RESOURCE / CONFIG HELPERS
# ================================
def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)


def get_data_dir():
    if sys.platform == "darwin":
        d = os.path.expanduser("~/Library/Application Support/SeekMateAI")
    elif sys.platform == "win32":
        d = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "SeekMateAI")
    else:
        d = os.path.expanduser("~/.seekmateai")
    os.makedirs(d, exist_ok=True)
    return d


CONFIG_FILE = resource_path("config.json")


def load_config():
    try:
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    except:
        return {}


def save_config(cfg):
    with open(CONFIG_FILE, "w") as f:
        json.dump(cfg, f, indent=4)


CONTROL_FILE = resource_path("longform_control.json")


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
# CUSTOM WIDGETS
# ================================
class ModernButton(tk.Canvas):
    """Canvas-based button with rounded corners and hover effects."""

    def __init__(self, parent, text="", command=None, style="primary", width=140, height=40):
        super().__init__(parent, width=width, height=height, bg=COLORS["bg_dark"],
                         highlightthickness=0, cursor="hand2")
        self.text = text
        self.command = command
        self.style = style
        self.w = width
        self.h = height
        self.is_hovered = False
        self.is_disabled = False
        self.styles = {
            "primary": {"bg": COLORS["accent_primary"], "hover": "#38b2ac", "fg": "#000"},
            "success": {"bg": COLORS["success"], "hover": "#38a169", "fg": "#000"},
            "warning": {"bg": COLORS["warning"], "hover": "#dd6b20", "fg": "#000"},
            "danger": {"bg": COLORS["danger"], "hover": "#e53e3e", "fg": "#fff"},
            "dark": {"bg": "#2a2a4a", "hover": "#3a3a5a", "fg": "#fff"},
            "purple": {"bg": COLORS["accent_purple"], "hover": "#805ad5", "fg": "#fff"},
            "disabled": {"bg": "#3a3a4a", "hover": "#3a3a4a", "fg": "#6a6a7a"},
        }
        self.draw_button()
        self.bind("<Enter>", self.on_enter)
        self.bind("<Leave>", self.on_leave)
        self.bind("<Button-1>", self.on_click)

    def _rounded_rect(self, x1, y1, x2, y2, r, **kw):
        self.create_arc(x1, y1, x1 + 2 * r, y1 + 2 * r, start=90, extent=90, **kw)
        self.create_arc(x2 - 2 * r, y1, x2, y1 + 2 * r, start=0, extent=90, **kw)
        self.create_arc(x1, y2 - 2 * r, x1 + 2 * r, y2, start=180, extent=90, **kw)
        self.create_arc(x2 - 2 * r, y2 - 2 * r, x2, y2, start=270, extent=90, **kw)
        self.create_rectangle(x1 + r, y1, x2 - r, y2, **kw)
        self.create_rectangle(x1, y1 + r, x2, y2 - r, **kw)

    def draw_button(self):
        self.delete("all")
        s = self.styles.get("disabled" if self.is_disabled else self.style, self.styles["dark"])
        bg = s["hover"] if self.is_hovered and not self.is_disabled else s["bg"]
        self._rounded_rect(2, 2, self.w - 2, self.h - 2, 8, fill=bg, outline=bg)
        self.create_text(self.w // 2, self.h // 2, text=self.text, font=FONT_BUTTON, fill=s["fg"])

    def on_enter(self, e):
        if not self.is_disabled:
            self.is_hovered = True
            self.draw_button()

    def on_leave(self, e):
        self.is_hovered = False
        self.draw_button()

    def on_click(self, e):
        if self.command and not self.is_disabled:
            self.command()

    def set_disabled(self, disabled):
        self.is_disabled = disabled
        self.config(cursor="" if disabled else "hand2")
        self.draw_button()

    def set_text(self, text):
        self.text = text
        self.draw_button()

    def set_style(self, style):
        self.style = style
        self.draw_button()


class ModernEntry(tk.Frame):
    """Styled text input."""

    def __init__(self, parent, placeholder="", show="", width=30, **kwargs):
        super().__init__(parent, bg=COLORS["bg_card"])
        self.entry = tk.Entry(self, bg=COLORS["bg_input"], fg=COLORS["text_primary"],
                              insertbackground=COLORS["accent_primary"], font=FONT_NORMAL,
                              relief="flat", highlightthickness=2,
                              highlightbackground=COLORS["border"],
                              highlightcolor=COLORS["accent_primary"],
                              width=width, show=show)
        self.entry.pack(fill="x", ipady=8, ipadx=10)

    def get(self):
        return self.entry.get()

    def insert(self, idx, val):
        self.entry.insert(idx, val)

    def delete(self, start, end):
        self.entry.delete(start, end)


class PulsingIndicator(tk.Canvas):
    """Animated status dot."""

    def __init__(self, parent, size=14):
        super().__init__(parent, width=size + 8, height=size + 8,
                         bg=COLORS["bg_dark"], highlightthickness=0)
        self.size = size
        self.color = COLORS["text_muted"]
        self.pulse_on = False
        self.pulse_phase = 0
        self.draw()

    def draw(self):
        self.delete("all")
        cx, cy = (self.size + 8) // 2, (self.size + 8) // 2
        r = self.size // 2
        if self.pulse_on:
            glow_r = r + 3 + int(2 * math.sin(self.pulse_phase))
            self.create_oval(cx - glow_r, cy - glow_r, cx + glow_r, cy + glow_r,
                             fill="", outline=self.color, width=1)
        self.create_oval(cx - r, cy - r, cx + r, cy + r, fill=self.color, outline="")

    def set_status(self, status):
        colors = {"idle": COLORS["text_muted"], "running": COLORS["success"],
                  "paused": COLORS["warning"], "stopped": COLORS["danger"]}
        self.color = colors.get(status, COLORS["text_muted"])
        self.pulse_on = status == "running"
        self.pulse_phase = 0
        self.draw()
        if self.pulse_on:
            self._pulse()

    def _pulse(self):
        if not self.pulse_on:
            return
        self.pulse_phase += 0.3
        self.draw()
        self.after(80, self._pulse)


class ModernSlider(tk.Frame):
    """Custom slider with value display."""

    def __init__(self, parent, label="", min_val=0, max_val=100, default=50,
                 unit="", on_change=None, width=300):
        super().__init__(parent, bg=COLORS["bg_card"])
        self.min_val = min_val
        self.max_val = max_val
        self.value = default
        self.unit = unit
        self.on_change = on_change

        top = tk.Frame(self, bg=COLORS["bg_card"])
        top.pack(fill="x")
        tk.Label(top, text=label, bg=COLORS["bg_card"], fg=COLORS["text_secondary"],
                 font=FONT_LABEL).pack(side="left")
        self.val_label = tk.Label(top, text=f"{default}{unit}", bg=COLORS["bg_card"],
                                  fg=COLORS["accent_primary"], font=FONT_LABEL_BOLD)
        self.val_label.pack(side="right")

        self.canvas = tk.Canvas(self, width=width, height=30, bg=COLORS["bg_card"],
                                highlightthickness=0, cursor="hand2")
        self.canvas.pack(fill="x", pady=(4, 0))
        self.canvas.bind("<Button-1>", self._on_click)
        self.canvas.bind("<B1-Motion>", self._on_drag)
        self.after(10, self._draw)

    def _draw(self):
        c = self.canvas
        c.delete("all")
        w = c.winfo_width() or 300
        pad = 12
        ty = 15
        th = 6
        ratio = (self.value - self.min_val) / max(1, self.max_val - self.min_val)
        thumb_x = pad + ratio * (w - 2 * pad)
        c.create_rectangle(pad, ty - th // 2, w - pad, ty + th // 2,
                           fill=COLORS["slider_track"], outline="")
        c.create_rectangle(pad, ty - th // 2, thumb_x, ty + th // 2,
                           fill=COLORS["slider_fill"], outline="")
        tr = 8
        c.create_oval(thumb_x - tr, ty - tr, thumb_x + tr, ty + tr,
                       fill=COLORS["accent_primary"], outline=COLORS["text_primary"], width=2)

    def _on_click(self, e):
        self._update(e.x)

    def _on_drag(self, e):
        self._update(e.x)

    def _update(self, x):
        w = self.canvas.winfo_width() or 300
        pad = 12
        ratio = max(0, min(1, (x - pad) / (w - 2 * pad)))
        self.value = int(self.min_val + ratio * (self.max_val - self.min_val))
        self.val_label.config(text=f"{self.value}{self.unit}")
        self._draw()
        if self.on_change:
            self.on_change(self.value)

    def get(self):
        return self.value

    def set(self, val):
        self.value = max(self.min_val, min(self.max_val, val))
        self.val_label.config(text=f"{self.value}{self.unit}")
        self._draw()


class CollapsibleCard(tk.Frame):
    """Expandable section card."""

    def __init__(self, parent, title="", icon="", default_expanded=True):
        super().__init__(parent, bg=COLORS["bg_card"])
        self.is_expanded = default_expanded

        header = tk.Frame(self, bg=COLORS["bg_card"], cursor="hand2")
        header.pack(fill="x", padx=15, pady=(12, 0))
        header.bind("<Button-1>", lambda e: self.toggle())

        self.arrow = tk.Label(header, text="▼" if default_expanded else "▶",
                              bg=COLORS["bg_card"], fg=COLORS["text_muted"],
                              font=FONT_LABEL, cursor="hand2")
        self.arrow.pack(side="left")
        self.arrow.bind("<Button-1>", lambda e: self.toggle())

        tk.Label(header, text=f" {icon}  {title}", bg=COLORS["bg_card"],
                 fg=COLORS["text_primary"], font=FONT_TITLE,
                 cursor="hand2").pack(side="left", padx=(4, 0))

        self.content = tk.Frame(self, bg=COLORS["bg_card"])
        if default_expanded:
            self.content.pack(fill="x", padx=15, pady=(10, 15))

    def toggle(self):
        self.is_expanded = not self.is_expanded
        self.arrow.config(text="▼" if self.is_expanded else "▶")
        if self.is_expanded:
            self.content.pack(fill="x", padx=15, pady=(10, 15))
        else:
            self.content.pack_forget()

    def get_content(self):
        return self.content


# ================================
# PIPELINE STEP WIDGET
# ================================
class PipelineStep(tk.Frame):
    """Single step in the bot pipeline visualization."""

    def __init__(self, parent, icon, label):
        super().__init__(parent, bg=COLORS["pipeline_bg"])
        self.status = "waiting"  # waiting, active, done, error
        self.icon_text = icon
        self.label_text = label

        self.dot = tk.Canvas(self, width=32, height=32, bg=COLORS["pipeline_bg"],
                             highlightthickness=0)
        self.dot.pack()
        self.label = tk.Label(self, text=label, bg=COLORS["pipeline_bg"],
                              fg=COLORS["text_muted"], font=FONT_PIPELINE)
        self.label.pack(pady=(2, 0))
        self._draw()

    def _draw(self):
        self.dot.delete("all")
        colors = {
            "waiting": COLORS["pipeline_waiting"],
            "active": COLORS["pipeline_active"],
            "done": COLORS["pipeline_done"],
            "error": COLORS["danger"],
        }
        c = colors.get(self.status, COLORS["pipeline_waiting"])
        self.dot.create_oval(4, 4, 28, 28, fill=c, outline="")
        self.dot.create_text(16, 16, text=self.icon_text, font=(FONT_FAMILY, 10), fill="#fff")
        fg = COLORS["text_primary"] if self.status in ("active", "done") else COLORS["text_muted"]
        self.label.config(fg=fg)

    def set_status(self, status):
        self.status = status
        self._draw()


class PipelineConnector(tk.Canvas):
    """Arrow connector between pipeline steps."""

    def __init__(self, parent, width=30):
        super().__init__(parent, width=width, height=32, bg=COLORS["pipeline_bg"],
                         highlightthickness=0)
        self.active = False
        self._draw()

    def _draw(self):
        self.delete("all")
        c = COLORS["pipeline_active"] if self.active else COLORS["pipeline_waiting"]
        self.create_line(2, 16, 24, 16, fill=c, width=2)
        self.create_polygon(22, 10, 28, 16, 22, 22, fill=c, outline=c)

    def set_active(self, active):
        self.active = active
        self._draw()


# ================================
# MAIN DASHBOARD
# ================================
class LongFormDashboard:
    def __init__(self, root):
        self.root = root
        self.root.title("SeekMate — Long-Form Bot")
        self.root.geometry("1200x900")
        self.root.minsize(1000, 700)
        self.root.configure(bg=COLORS["bg_dark"])

        # State
        self.config = load_config()
        self.bot_process = None
        self.is_running = False
        self.is_paused = False
        self.session_start = None
        self.log_thread = None
        self.cc_poll_thread = None
        self.current_job = {"title": "", "company": "", "portal": "", "fields_total": 0,
                            "fields_filled": 0}
        self.session_stats = {"submitted": 0, "failed": 0, "scanned": 0, "skipped_quick": 0}
        self.cc_stats = {"questions": 0, "answers": 0, "pending": False}
        self.log_lines = 0
        self.log_filter = "all"

        self.build_ui()
        self._auto_refresh()

    # ================================
    # UI BUILDING
    # ================================
    def build_ui(self):
        # Scrollable main container
        outer = tk.Frame(self.root, bg=COLORS["bg_dark"])
        outer.pack(fill="both", expand=True)

        canvas = tk.Canvas(outer, bg=COLORS["bg_dark"], highlightthickness=0)
        scrollbar = ttk.Scrollbar(outer, orient="vertical", command=canvas.yview)
        self.main = tk.Frame(canvas, bg=COLORS["bg_dark"])

        self.main.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=self.main, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        # Mouse wheel scrolling
        def _on_mousewheel(e):
            canvas.yview_scroll(int(-1 * (e.delta / 120)), "units")
        canvas.bind_all("<MouseWheel>", _on_mousewheel)
        self.canvas = canvas

        self.build_header()
        self.build_controls()
        self.build_two_column()

    def build_header(self):
        header = tk.Frame(self.main, bg=COLORS["bg_dark"])
        header.pack(fill="x", padx=25, pady=(20, 0))

        left = tk.Frame(header, bg=COLORS["bg_dark"])
        left.pack(side="left")

        tk.Label(left, text="LONG-FORM BOT", bg=COLORS["bg_dark"],
                 fg=COLORS["text_primary"], font=FONT_HEADER).pack(side="left")

        self.status_indicator = PulsingIndicator(left, size=12)
        self.status_indicator.pack(side="left", padx=(15, 5))

        self.status_label = tk.Label(left, text="STOPPED", bg=COLORS["bg_dark"],
                                     fg=COLORS["text_muted"], font=FONT_LABEL_BOLD)
        self.status_label.pack(side="left")

        right = tk.Frame(header, bg=COLORS["bg_dark"])
        right.pack(side="right")

        self.timer_label = tk.Label(right, text="00:00:00", bg=COLORS["bg_dark"],
                                    fg=COLORS["text_secondary"], font=(FONT_FAMILY, 14, "bold"))
        self.timer_label.pack(side="right")
        tk.Label(right, text="⏱ ", bg=COLORS["bg_dark"], fg=COLORS["text_muted"],
                 font=FONT_NORMAL).pack(side="right")

    def build_controls(self):
        bar = tk.Frame(self.main, bg=COLORS["bg_dark"])
        bar.pack(fill="x", padx=25, pady=(15, 0))

        self.btn_start = ModernButton(bar, text="▶  START", command=self.start_bot,
                                      style="success", width=140, height=42)
        self.btn_start.pack(side="left", padx=(0, 8))

        self.btn_pause = ModernButton(bar, text="⏸  PAUSE", command=self.pause_bot,
                                      style="warning", width=140, height=42)
        self.btn_pause.pack(side="left", padx=(0, 8))
        self.btn_pause.set_disabled(True)

        self.btn_stop = ModernButton(bar, text="■  STOP", command=self.stop_bot,
                                     style="danger", width=140, height=42)
        self.btn_stop.pack(side="left", padx=(0, 8))
        self.btn_stop.set_disabled(True)

        # Right side: run counter
        right = tk.Frame(bar, bg=COLORS["bg_dark"])
        right.pack(side="right")
        tk.Label(right, text="This Run:", bg=COLORS["bg_dark"],
                 fg=COLORS["text_muted"], font=FONT_LABEL).pack(side="left", padx=(0, 5))
        max_jobs = self.config.get("MAX_JOBS", 100)
        self.run_counter = tk.Label(right, text=f"0/{max_jobs}", bg=COLORS["bg_dark"],
                                    fg=COLORS["accent_primary"], font=FONT_BOLD)
        self.run_counter.pack(side="left")

    def build_two_column(self):
        """Two-column layout: left = live viz + AI panel, right = stats + log + history."""
        cols = tk.Frame(self.main, bg=COLORS["bg_dark"])
        cols.pack(fill="both", expand=True, padx=25, pady=(15, 20))

        # Left column (45%)
        left = tk.Frame(cols, bg=COLORS["bg_dark"])
        left.pack(side="left", fill="both", expand=True, padx=(0, 10))

        self.build_pipeline_panel(left)
        self.build_current_job_panel(left)
        self.build_claude_code_panel(left)
        self.build_settings_panel(left)

        # Right column (55%)
        right = tk.Frame(cols, bg=COLORS["bg_dark"])
        right.pack(side="right", fill="both", expand=True, padx=(10, 0))

        self.build_stats_panel(right)
        self.build_analytics_panel(right)
        self.build_log_panel(right)
        self.build_history_panel(right)

    # ================================
    # LEFT COLUMN: Pipeline
    # ================================
    def build_pipeline_panel(self, parent):
        card = tk.Frame(parent, bg=COLORS["pipeline_bg"])
        card.pack(fill="x", pady=(0, 10))

        tk.Label(card, text="  BOT PIPELINE", bg=COLORS["pipeline_bg"],
                 fg=COLORS["text_secondary"], font=FONT_LABEL_BOLD).pack(anchor="w", padx=15, pady=(12, 8))

        row = tk.Frame(card, bg=COLORS["pipeline_bg"])
        row.pack(padx=10, pady=(0, 15))

        steps = [("🔍", "Scan"), ("📋", "Filter"), ("🌐", "Portal"),
                 ("📝", "Fill"), ("✅", "Submit")]

        self.pipeline_steps = []
        self.pipeline_connectors = []

        for i, (icon, label) in enumerate(steps):
            step = PipelineStep(row, icon, label)
            step.pack(side="left")
            self.pipeline_steps.append(step)
            if i < len(steps) - 1:
                conn = PipelineConnector(row, width=25)
                conn.pack(side="left", pady=(0, 18))
                self.pipeline_connectors.append(conn)

    def set_pipeline_stage(self, stage_idx):
        """Highlight the current pipeline stage (0-4)."""
        for i, step in enumerate(self.pipeline_steps):
            if i < stage_idx:
                step.set_status("done")
            elif i == stage_idx:
                step.set_status("active")
            else:
                step.set_status("waiting")
        for i, conn in enumerate(self.pipeline_connectors):
            conn.set_active(i < stage_idx)

    # ================================
    # LEFT COLUMN: Current Job
    # ================================
    def build_current_job_panel(self, parent):
        card = tk.Frame(parent, bg=COLORS["bg_card"])
        card.pack(fill="x", pady=(0, 10))

        tk.Label(card, text="  CURRENT JOB", bg=COLORS["bg_card"],
                 fg=COLORS["text_secondary"], font=FONT_LABEL_BOLD).pack(anchor="w", padx=15, pady=(12, 5))

        inner = tk.Frame(card, bg=COLORS["bg_card"])
        inner.pack(fill="x", padx=15, pady=(0, 15))

        self.job_title_label = tk.Label(inner, text="Waiting for bot to start...",
                                        bg=COLORS["bg_card"], fg=COLORS["text_primary"],
                                        font=FONT_BOLD, wraplength=350, anchor="w", justify="left")
        self.job_title_label.pack(anchor="w")

        self.job_company_label = tk.Label(inner, text="",
                                          bg=COLORS["bg_card"], fg=COLORS["accent_secondary"],
                                          font=FONT_NORMAL)
        self.job_company_label.pack(anchor="w", pady=(2, 0))

        self.job_portal_label = tk.Label(inner, text="",
                                         bg=COLORS["bg_card"], fg=COLORS["text_muted"],
                                         font=FONT_SMALL)
        self.job_portal_label.pack(anchor="w", pady=(2, 0))

        # Progress bar for form filling
        prog_frame = tk.Frame(inner, bg=COLORS["bg_card"])
        prog_frame.pack(fill="x", pady=(8, 0))

        self.field_progress_bg = tk.Canvas(prog_frame, height=8, bg=COLORS["slider_track"],
                                           highlightthickness=0)
        self.field_progress_bg.pack(fill="x")

        self.field_progress_label = tk.Label(inner, text="", bg=COLORS["bg_card"],
                                             fg=COLORS["text_muted"], font=FONT_SMALL)
        self.field_progress_label.pack(anchor="w", pady=(3, 0))

    def update_current_job(self, title="", company="", portal="", fields_filled=0, fields_total=0):
        self.job_title_label.config(text=title or "Scanning...")
        self.job_company_label.config(text=company)
        self.job_portal_label.config(text=f"Portal: {portal}" if portal else "")

        # Update progress bar
        self.field_progress_bg.delete("all")
        w = self.field_progress_bg.winfo_width() or 300
        if fields_total > 0:
            ratio = min(1, fields_filled / fields_total)
            fill_w = int(w * ratio)
            self.field_progress_bg.create_rectangle(0, 0, fill_w, 8,
                                                     fill=COLORS["accent_primary"], outline="")
            self.field_progress_label.config(
                text=f"Fields: {fields_filled}/{fields_total} ({int(ratio * 100)}%)")
        else:
            self.field_progress_label.config(text="")

    # ================================
    # LEFT COLUMN: Claude Code AI Panel
    # ================================
    def build_claude_code_panel(self, parent):
        card = tk.Frame(parent, bg=COLORS["bg_card"])
        card.pack(fill="x", pady=(0, 10))

        header = tk.Frame(card, bg=COLORS["bg_card"])
        header.pack(fill="x", padx=15, pady=(12, 5))

        self.cc_dot = tk.Canvas(header, width=12, height=12, bg=COLORS["bg_card"],
                                highlightthickness=0)
        self.cc_dot.pack(side="left")
        self.cc_dot.create_oval(2, 2, 10, 10, fill=COLORS["text_muted"], outline="")

        tk.Label(header, text="  CLAUDE CODE AI", bg=COLORS["bg_card"],
                 fg=COLORS["text_secondary"], font=FONT_LABEL_BOLD).pack(side="left")

        self.cc_status_label = tk.Label(header, text="Idle", bg=COLORS["bg_card"],
                                        fg=COLORS["text_muted"], font=FONT_SMALL)
        self.cc_status_label.pack(side="right")

        inner = tk.Frame(card, bg=COLORS["bg_card"])
        inner.pack(fill="x", padx=15, pady=(0, 12))

        self.cc_question_label = tk.Label(inner, text="No active questions",
                                          bg=COLORS["bg_card"], fg=COLORS["text_muted"],
                                          font=FONT_SMALL, wraplength=300, anchor="w", justify="left")
        self.cc_question_label.pack(anchor="w")

        stats_row = tk.Frame(inner, bg=COLORS["bg_card"])
        stats_row.pack(fill="x", pady=(6, 0))

        self.cc_q_count = tk.Label(stats_row, text="Questions: 0", bg=COLORS["bg_card"],
                                   fg=COLORS["text_secondary"], font=FONT_SMALL)
        self.cc_q_count.pack(side="left")

        self.cc_a_count = tk.Label(stats_row, text="Answers: 0", bg=COLORS["bg_card"],
                                   fg=COLORS["accent_primary"], font=FONT_SMALL)
        self.cc_a_count.pack(side="left", padx=(15, 0))

    def update_cc_status(self, status="idle", question=""):
        colors = {"idle": COLORS["text_muted"], "waiting": COLORS["warning"],
                  "answering": COLORS["ai_glow"], "done": COLORS["success"]}
        labels = {"idle": "Idle", "waiting": "Waiting for answer...",
                  "answering": "Generating answer...", "done": "Answer sent"}

        c = colors.get(status, COLORS["text_muted"])
        self.cc_dot.delete("all")
        self.cc_dot.create_oval(2, 2, 10, 10, fill=c, outline="")
        self.cc_status_label.config(text=labels.get(status, ""), fg=c)

        if question:
            short = question[:80] + "..." if len(question) > 80 else question
            self.cc_question_label.config(text=short, fg=COLORS["text_secondary"])
        elif status == "idle":
            self.cc_question_label.config(text="No active questions", fg=COLORS["text_muted"])

        self.cc_q_count.config(text=f"Questions: {self.cc_stats['questions']}")
        self.cc_a_count.config(text=f"Answers: {self.cc_stats['answers']}")

    # ================================
    # LEFT COLUMN: Settings
    # ================================
    def build_settings_panel(self, parent):
        card = CollapsibleCard(parent, title="Settings", icon="⚙️", default_expanded=False)
        card.pack(fill="x", pady=(0, 10))
        content = card.get_content()

        # Max jobs
        self.max_jobs_slider = ModernSlider(content, label="Max Applications",
                                            min_val=1, max_val=200,
                                            default=self.config.get("MAX_JOBS", 100), unit="")
        self.max_jobs_slider.pack(fill="x", pady=(0, 8))

        # Cooldown
        self.cooldown_slider = ModernSlider(content, label="Cooldown Delay",
                                            min_val=0, max_val=30,
                                            default=self.config.get("COOLDOWN_DELAY", 5), unit="s")
        self.cooldown_slider.pack(fill="x", pady=(0, 8))

        # Stealth toggle
        stealth_frame = tk.Frame(content, bg=COLORS["bg_card"])
        stealth_frame.pack(fill="x", pady=(0, 8))
        tk.Label(stealth_frame, text="Stealth Mode", bg=COLORS["bg_card"],
                 fg=COLORS["text_secondary"], font=FONT_LABEL).pack(side="left")
        self.stealth_var = tk.BooleanVar(value=self.config.get("STEALTH_MODE", False))
        tk.Checkbutton(stealth_frame, variable=self.stealth_var, bg=COLORS["bg_card"],
                       fg=COLORS["accent_primary"], selectcolor=COLORS["bg_input"],
                       activebackground=COLORS["bg_card"]).pack(side="right")

        # Claude Code toggle
        cc_frame = tk.Frame(content, bg=COLORS["bg_card"])
        cc_frame.pack(fill="x", pady=(0, 8))
        tk.Label(cc_frame, text="Use Claude Code AI (free)", bg=COLORS["bg_card"],
                 fg=COLORS["text_secondary"], font=FONT_LABEL).pack(side="left")
        self.use_cc_var = tk.BooleanVar(value=self.config.get("USE_CLAUDE_CODE", True))
        tk.Checkbutton(cc_frame, variable=self.use_cc_var, bg=COLORS["bg_card"],
                       fg=COLORS["accent_primary"], selectcolor=COLORS["bg_input"],
                       activebackground=COLORS["bg_card"]).pack(side="right")

        # Save button
        ModernButton(content, text="Save Settings", command=self.save_settings,
                     style="primary", width=140, height=36).pack(anchor="w", pady=(8, 0))

    def save_settings(self):
        self.config["MAX_JOBS"] = self.max_jobs_slider.get()
        self.config["COOLDOWN_DELAY"] = self.cooldown_slider.get()
        self.config["STEALTH_MODE"] = self.stealth_var.get()
        self.config["USE_CLAUDE_CODE"] = self.use_cc_var.get()
        save_config(self.config)
        self.log("INFO", "Settings saved")

    # ================================
    # RIGHT COLUMN: Stats
    # ================================
    def build_stats_panel(self, parent):
        row = tk.Frame(parent, bg=COLORS["bg_dark"])
        row.pack(fill="x", pady=(0, 10))

        self.stat_cards = {}
        stats_def = [
            ("submitted", "SUBMITTED", COLORS["success"], "0"),
            ("failed", "FAILED", COLORS["danger"], "0"),
            ("rate", "SUCCESS %", COLORS["accent_primary"], "0%"),
            ("duration", "AVG TIME", COLORS["accent_secondary"], "0s"),
        ]
        for key, label, color, default in stats_def:
            card = tk.Frame(row, bg=COLORS["bg_card"])
            card.pack(side="left", fill="both", expand=True, padx=(0, 6))
            inner = tk.Frame(card, bg=COLORS["bg_card"])
            inner.pack(fill="both", expand=True, padx=12, pady=12)
            tk.Label(inner, text=label, bg=COLORS["bg_card"], fg=COLORS["text_muted"],
                     font=FONT_CHIP).pack(anchor="w")
            val = tk.Label(inner, text=default, bg=COLORS["bg_card"], fg=color,
                           font=FONT_STATS)
            val.pack(anchor="w", pady=(2, 0))
            self.stat_cards[key] = val

    def refresh_stats(self):
        try:
            db_path = self.config.get("LONGFORM_DB_PATH", resource_path("seekmate.db"))
            if not os.path.exists(db_path):
                return
            from longform.database import Database
            db = Database(db_path)
            stats = db.get_stats()
            sub = stats.get("submitted", 0)
            fail = stats.get("failed", 0)
            total = sub + fail
            rate = int(sub / total * 100) if total > 0 else 0
            avg_dur = stats.get("avg_duration", 0) or 0

            self.stat_cards["submitted"].config(text=str(sub))
            self.stat_cards["failed"].config(text=str(fail))
            self.stat_cards["rate"].config(text=f"{rate}%")
            self.stat_cards["duration"].config(text=f"{avg_dur:.0f}s")
        except:
            pass

    # ================================
    # RIGHT COLUMN: Analytics
    # ================================
    def build_analytics_panel(self, parent):
        card = tk.Frame(parent, bg=COLORS["bg_card"])
        card.pack(fill="x", pady=(0, 10))

        tk.Label(card, text="  ANALYTICS", bg=COLORS["bg_card"],
                 fg=COLORS["text_secondary"], font=FONT_LABEL_BOLD).pack(anchor="w", padx=15, pady=(12, 8))

        inner = tk.Frame(card, bg=COLORS["bg_card"])
        inner.pack(fill="x", padx=15, pady=(0, 15))

        # ATS breakdown
        tk.Label(inner, text="ATS Portals", bg=COLORS["bg_card"],
                 fg=COLORS["text_secondary"], font=FONT_SMALL).pack(anchor="w")

        self.ats_frame = tk.Frame(inner, bg=COLORS["bg_card"])
        self.ats_frame.pack(fill="x", pady=(4, 8))

        # Hourly submissions bar chart
        tk.Label(inner, text="Submissions (last 8 hours)", bg=COLORS["bg_card"],
                 fg=COLORS["text_secondary"], font=FONT_SMALL).pack(anchor="w")

        self.chart_canvas = tk.Canvas(inner, height=60, bg=COLORS["bg_card"],
                                      highlightthickness=0)
        self.chart_canvas.pack(fill="x", pady=(4, 0))

        # Scanned counter
        scan_row = tk.Frame(inner, bg=COLORS["bg_card"])
        scan_row.pack(fill="x", pady=(8, 0))
        tk.Label(scan_row, text="Jobs Scanned:", bg=COLORS["bg_card"],
                 fg=COLORS["text_muted"], font=FONT_SMALL).pack(side="left")
        self.scanned_label = tk.Label(scan_row, text="0", bg=COLORS["bg_card"],
                                      fg=COLORS["text_secondary"], font=FONT_SMALL)
        self.scanned_label.pack(side="left", padx=(5, 15))

        tk.Label(scan_row, text="Quick Apply Skipped:", bg=COLORS["bg_card"],
                 fg=COLORS["text_muted"], font=FONT_SMALL).pack(side="left")
        self.skipped_label = tk.Label(scan_row, text="0", bg=COLORS["bg_card"],
                                      fg=COLORS["text_secondary"], font=FONT_SMALL)
        self.skipped_label.pack(side="left", padx=(5, 0))

    def refresh_analytics(self):
        """Update ATS breakdown and chart from database."""
        try:
            db_path = self.config.get("LONGFORM_DB_PATH", resource_path("seekmate.db"))
            if not os.path.exists(db_path):
                return

            import sqlite3
            conn = sqlite3.connect(db_path, timeout=5)
            cursor = conn.cursor()

            # ATS breakdown
            try:
                cursor.execute("""
                    SELECT ats_portal, COUNT(*) as cnt FROM applications
                    WHERE ats_portal IS NOT NULL AND ats_portal != ''
                    GROUP BY ats_portal ORDER BY cnt DESC LIMIT 5
                """)
                rows = cursor.fetchall()
                for w in self.ats_frame.winfo_children():
                    w.destroy()

                ats_colors = [COLORS["accent_primary"], COLORS["accent_secondary"],
                              COLORS["accent_purple"], COLORS["success"], COLORS["warning"]]
                total = sum(r[1] for r in rows) if rows else 1

                for i, (portal, cnt) in enumerate(rows):
                    row = tk.Frame(self.ats_frame, bg=COLORS["bg_card"])
                    row.pack(fill="x", pady=1)
                    c = ats_colors[i % len(ats_colors)]
                    tk.Label(row, text=f"  {portal or 'Unknown'}", bg=COLORS["bg_card"],
                             fg=c, font=FONT_SMALL, width=18, anchor="w").pack(side="left")
                    # Mini bar
                    bar = tk.Canvas(row, height=10, bg=COLORS["slider_track"],
                                    highlightthickness=0, width=100)
                    bar.pack(side="left", padx=(5, 5))
                    ratio = cnt / total
                    bar.create_rectangle(0, 0, int(100 * ratio), 10, fill=c, outline="")
                    tk.Label(row, text=str(cnt), bg=COLORS["bg_card"],
                             fg=COLORS["text_secondary"], font=FONT_SMALL).pack(side="left")

                if not rows:
                    tk.Label(self.ats_frame, text="No data yet", bg=COLORS["bg_card"],
                             fg=COLORS["text_muted"], font=FONT_SMALL).pack(anchor="w")
            except:
                pass

            # Hourly chart
            try:
                cursor.execute("""
                    SELECT strftime('%H', created_at) as hour, COUNT(*) as cnt
                    FROM applications WHERE submission_status='submitted'
                    AND created_at >= datetime('now', '-8 hours')
                    GROUP BY hour ORDER BY hour
                """)
                hourly = cursor.fetchall()
                self.chart_canvas.delete("all")
                w = self.chart_canvas.winfo_width() or 300
                if hourly:
                    max_cnt = max(r[1] for r in hourly)
                    bar_w = max(8, (w - 20) // max(len(hourly), 1) - 4)
                    for i, (hour, cnt) in enumerate(hourly):
                        x = 10 + i * (bar_w + 4)
                        h = int(45 * cnt / max(max_cnt, 1))
                        self.chart_canvas.create_rectangle(
                            x, 55 - h, x + bar_w, 55,
                            fill=COLORS["accent_primary"], outline="")
                        self.chart_canvas.create_text(
                            x + bar_w // 2, 55 - h - 6, text=str(cnt),
                            font=FONT_SMALL, fill=COLORS["text_secondary"])
                else:
                    self.chart_canvas.create_text(
                        w // 2, 30, text="No submissions yet",
                        font=FONT_SMALL, fill=COLORS["text_muted"])
            except:
                pass

            conn.close()
        except:
            pass

    # ================================
    # RIGHT COLUMN: Activity Log
    # ================================
    def build_log_panel(self, parent):
        card = CollapsibleCard(parent, title="Activity Log", icon="📝", default_expanded=True)
        card.pack(fill="x", pady=(0, 10))
        content = card.get_content()

        # Filter buttons
        filter_row = tk.Frame(content, bg=COLORS["bg_card"])
        filter_row.pack(fill="x", pady=(0, 5))

        filters = [("All", "all"), ("Errors", "error"), ("AI", "ai"), ("Success", "success")]
        self.filter_btns = {}
        for label, key in filters:
            btn = tk.Label(filter_row, text=f" {label} ", bg=COLORS["bg_elevated"],
                           fg=COLORS["text_secondary"], font=FONT_CHIP, cursor="hand2",
                           padx=8, pady=2)
            btn.pack(side="left", padx=(0, 4))
            btn.bind("<Button-1>", lambda e, k=key: self._set_log_filter(k))
            self.filter_btns[key] = btn

        self.filter_btns["all"].config(bg=COLORS["accent_primary"], fg="#000")

        self.line_count_label = tk.Label(filter_row, text="(0 lines)", bg=COLORS["bg_card"],
                                         fg=COLORS["text_muted"], font=FONT_SMALL)
        self.line_count_label.pack(side="right")

        # Clear button
        clear_btn = tk.Label(filter_row, text="Clear", bg=COLORS["bg_card"],
                             fg=COLORS["text_muted"], font=FONT_SMALL, cursor="hand2")
        clear_btn.pack(side="right", padx=(0, 8))
        clear_btn.bind("<Button-1>", lambda e: self._clear_log())

        # Console
        log_frame = tk.Frame(content, bg=COLORS["bg_input"])
        log_frame.pack(fill="x")

        self.console = tk.Text(log_frame, height=14, bg=COLORS["bg_input"],
                               fg=COLORS["text_secondary"], font=FONT_CONSOLE,
                               relief="flat", wrap="word", state="disabled",
                               insertbackground=COLORS["accent_primary"],
                               selectbackground=COLORS["border_light"])
        scroll = ttk.Scrollbar(log_frame, command=self.console.yview)
        self.console.config(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self.console.pack(side="left", fill="both", expand=True, padx=5, pady=5)

        # Tag colors
        self.console.tag_config("ERROR", foreground=COLORS["danger"])
        self.console.tag_config("SUCCESS", foreground=COLORS["success"])
        self.console.tag_config("INFO", foreground=COLORS["text_secondary"])
        self.console.tag_config("AI", foreground=COLORS["ai_glow"])
        self.console.tag_config("ATS", foreground=COLORS["accent_secondary"])
        self.console.tag_config("EXTERNAL", foreground=COLORS["accent_primary"])
        self.console.tag_config("SKIP", foreground=COLORS["text_muted"])
        self.console.tag_config("LONGFORM", foreground=COLORS["accent_gold"])

    def _set_log_filter(self, key):
        self.log_filter = key
        for k, btn in self.filter_btns.items():
            if k == key:
                btn.config(bg=COLORS["accent_primary"], fg="#000")
            else:
                btn.config(bg=COLORS["bg_elevated"], fg=COLORS["text_secondary"])

    def _clear_log(self):
        self.console.config(state="normal")
        self.console.delete("1.0", "end")
        self.console.config(state="disabled")
        self.log_lines = 0
        self.line_count_label.config(text="(0 lines)")

    def log(self, level, text):
        """Insert a log line into the console."""
        # Check filter
        if self.log_filter != "all":
            level_lower = level.lower()
            if self.log_filter == "error" and level_lower not in ("error",):
                return
            if self.log_filter == "ai" and level_lower not in ("ai", "cc", "gpt"):
                return
            if self.log_filter == "success" and level_lower not in ("success",):
                return

        timestamp = datetime.now().strftime("%H:%M:%S")
        tag = level.upper()
        if tag not in ("ERROR", "SUCCESS", "INFO", "AI", "ATS", "EXTERNAL", "SKIP", "LONGFORM"):
            tag = "INFO"

        self.console.config(state="normal")
        self.console.insert("end", f"[{timestamp}] ", "INFO")
        self.console.insert("end", f"{text}\n", tag)
        self.console.see("end")
        self.console.config(state="disabled")
        self.log_lines += 1
        self.line_count_label.config(text=f"({self.log_lines} lines)")

    def _insert_log_line(self, line):
        """Parse a raw log line and insert with appropriate coloring."""
        line = line.strip()
        if not line:
            return

        tag = "INFO"
        if "[!]" in line or "ERROR" in line or "error" in line.lower() or "Traceback" in line:
            tag = "ERROR"
        elif "[+]" in line or "SUBMITTED" in line or "submitted" in line.lower():
            tag = "SUCCESS"
        elif "[CC]" in line or "Claude Code" in line or "GPT" in line:
            tag = "AI"
        elif "[ATS]" in line or "ATS" in line:
            tag = "ATS"
        elif "EXTERNAL" in line or "portal" in line.lower():
            tag = "EXTERNAL"
        elif "SKIP" in line or "skipping" in line.lower() or "Quick Apply" in line:
            tag = "SKIP"
        elif "[LongForm]" in line:
            tag = "LONGFORM"

        # Apply filter
        if self.log_filter != "all":
            if self.log_filter == "error" and tag != "ERROR":
                return
            if self.log_filter == "ai" and tag != "AI":
                return
            if self.log_filter == "success" and tag != "SUCCESS":
                return

        self.console.config(state="normal")
        self.console.insert("end", line + "\n", tag)
        self.console.see("end")
        self.console.config(state="disabled")
        self.log_lines += 1
        self.line_count_label.config(text=f"({self.log_lines} lines)")

        # Parse pipeline state from log
        self._parse_log_for_state(line)

    def _parse_log_for_state(self, line):
        """Update pipeline and current job based on log output."""
        if "Searching in:" in line or "SEARCHING:" in line:
            self.set_pipeline_stage(0)
        elif "Job " in line and "|" in line:
            self.set_pipeline_stage(1)
            # Extract title and company
            m = re.search(r'Job \d+: (.+?) \| (.+)', line)
            if m:
                self.update_current_job(title=m.group(1).strip(), company=m.group(2).strip())
        elif "EXTERNAL APPLICATION" in line or "EXTERNAL PORTAL" in line:
            self.set_pipeline_stage(2)
        elif "portal" in line.lower() and "http" in line:
            m = re.search(r'(https?://\S+)', line)
            if m:
                self.job_portal_label.config(text=f"Portal: {m.group(1)[:60]}")
        elif "[LongForm]" in line and "Page" in line:
            self.set_pipeline_stage(3)
        elif "fields on page" in line:
            m = re.search(r'(\d+) fields', line)
            if m:
                total = int(m.group(1))
                self.current_job["fields_total"] = total
                self.update_current_job(
                    title=self.job_title_label.cget("text"),
                    company=self.job_company_label.cget("text"),
                    fields_total=total, fields_filled=0)
        elif "Filled" in line and "fields" in line:
            m = re.search(r'Filled (\d+) fields', line)
            if m:
                filled = int(m.group(1))
                self.update_current_job(
                    title=self.job_title_label.cget("text"),
                    company=self.job_company_label.cget("text"),
                    fields_total=self.current_job["fields_total"],
                    fields_filled=filled)
        elif "SUBMITTED" in line or "submitted" in line.lower():
            self.set_pipeline_stage(4)
            self.session_stats["submitted"] += 1
            max_jobs = self.config.get("MAX_JOBS", 100)
            self.run_counter.config(text=f"{self.session_stats['submitted']}/{max_jobs}")
        elif "FAILED" in line:
            self.session_stats["failed"] += 1
        elif "Quick Apply" in line and "SKIPPING" in line:
            self.session_stats["skipped_quick"] += 1
            self.skipped_label.config(text=str(self.session_stats["skipped_quick"]))

        # Update scanned count
        if "Found" in line and "jobs" in line:
            m = re.search(r'Found (\d+) jobs', line)
            if m:
                self.session_stats["scanned"] += int(m.group(1))
                self.scanned_label.config(text=str(self.session_stats["scanned"]))

        # Claude Code activity
        if "[CC]" in line:
            if "Question written" in line:
                self.cc_stats["questions"] += 1
                self.update_cc_status("waiting")
            elif "Answer received" in line:
                self.cc_stats["answers"] += 1
                self.update_cc_status("done")

    # ================================
    # RIGHT COLUMN: History
    # ================================
    def build_history_panel(self, parent):
        card = CollapsibleCard(parent, title="Application History", icon="📋",
                               default_expanded=False)
        card.pack(fill="x", pady=(0, 10))
        content = card.get_content()

        # Search
        search_frame = tk.Frame(content, bg=COLORS["bg_card"])
        search_frame.pack(fill="x", pady=(0, 8))
        tk.Label(search_frame, text="🔍", bg=COLORS["bg_card"],
                 font=FONT_NORMAL).pack(side="left")
        self.history_search = ModernEntry(search_frame, placeholder="Search jobs...", width=30)
        self.history_search.pack(side="left", fill="x", expand=True, padx=(5, 0))
        self.history_search.entry.bind("<KeyRelease>", lambda e: self.refresh_history())

        self.history_frame = tk.Frame(content, bg=COLORS["bg_card"])
        self.history_frame.pack(fill="x")

    def refresh_history(self):
        """Rebuild history cards from database."""
        for w in self.history_frame.winfo_children():
            w.destroy()

        try:
            db_path = self.config.get("LONGFORM_DB_PATH", resource_path("seekmate.db"))
            if not os.path.exists(db_path):
                tk.Label(self.history_frame, text="No history yet", bg=COLORS["bg_card"],
                         fg=COLORS["text_muted"], font=FONT_SMALL).pack(pady=10)
                return

            from longform.database import Database
            db = Database(db_path)
            jobs = db.get_recent_jobs(limit=30)
            search = self.history_search.get().lower().strip()

            count = 0
            for job in jobs:
                title = job.get("title", "") or ""
                company = job.get("company", "") or ""
                if search and search not in title.lower() and search not in company.lower():
                    continue

                self._build_history_card(job)
                count += 1
                if count >= 20:
                    break

            if count == 0:
                tk.Label(self.history_frame, text="No matching jobs", bg=COLORS["bg_card"],
                         fg=COLORS["text_muted"], font=FONT_SMALL).pack(pady=10)
        except:
            pass

    def _build_history_card(self, job):
        card = tk.Frame(self.history_frame, bg=COLORS["bg_elevated"], cursor="hand2")
        card.pack(fill="x", pady=2)

        inner = tk.Frame(card, bg=COLORS["bg_elevated"])
        inner.pack(fill="x", padx=10, pady=6)

        title = job.get("title", "Unknown")[:50]
        company = job.get("company", "")[:30]
        status = job.get("status", "unknown")

        top = tk.Frame(inner, bg=COLORS["bg_elevated"])
        top.pack(fill="x")

        tk.Label(top, text=title, bg=COLORS["bg_elevated"], fg=COLORS["text_primary"],
                 font=FONT_BOLD, anchor="w").pack(side="left")

        # Status badge
        badge_colors = {
            "submitted": (COLORS["success"], "APPLIED"),
            "applied": (COLORS["success"], "APPLIED"),
            "failed": (COLORS["danger"], "FAILED"),
            "opened": (COLORS["warning"], "OPENED"),
            "discovered": (COLORS["text_muted"], "FOUND"),
        }
        badge_color, badge_text = badge_colors.get(status, (COLORS["text_muted"], status.upper()))
        tk.Label(top, text=f" {badge_text} ", bg=badge_color, fg="#000",
                 font=FONT_CHIP).pack(side="right")

        if company:
            tk.Label(inner, text=company, bg=COLORS["bg_elevated"],
                     fg=COLORS["text_muted"], font=FONT_SMALL, anchor="w").pack(anchor="w")

        url = job.get("job_url", "")
        if url:
            card.bind("<Button-1>", lambda e, u=url: webbrowser.open(u))

    # ================================
    # BOT CONTROL
    # ================================
    def start_bot(self):
        if self.is_running:
            return

        self.save_settings()
        write_control(pause=False, stop=False)

        script = resource_path("longform_bot.py")
        try:
            kwargs = {}
            if sys.platform == "win32":
                kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
            self.bot_process = subprocess.Popen(
                [sys.executable, script],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                **kwargs
            )
        except Exception as e:
            self.log("ERROR", f"Failed to start bot: {e}")
            return

        self.is_running = True
        self.is_paused = False
        self.session_start = time.time()
        self.session_stats = {"submitted": 0, "failed": 0, "scanned": 0, "skipped_quick": 0}
        self.cc_stats = {"questions": 0, "answers": 0, "pending": False}

        self.status_indicator.set_status("running")
        self.status_label.config(text="RUNNING", fg=COLORS["success"])
        self.btn_start.set_disabled(True)
        self.btn_pause.set_disabled(False)
        self.btn_stop.set_disabled(False)
        self.set_pipeline_stage(0)

        self.log("SUCCESS", "Bot started")

        # Start log tailing thread
        self.log_thread = threading.Thread(target=self._tail_log, daemon=True)
        self.log_thread.start()

        # Start CC polling
        self.cc_poll_thread = threading.Thread(target=self._poll_cc_bridge, daemon=True)
        self.cc_poll_thread.start()

        self._update_timer()

    def pause_bot(self):
        if not self.is_running:
            return
        self.is_paused = not self.is_paused
        write_control(pause=self.is_paused)
        if self.is_paused:
            self.status_indicator.set_status("paused")
            self.status_label.config(text="PAUSED", fg=COLORS["warning"])
            self.btn_pause.set_text("▶  RESUME")
            self.btn_pause.set_style("success")
            self.log("INFO", "Bot paused")
        else:
            self.status_indicator.set_status("running")
            self.status_label.config(text="RUNNING", fg=COLORS["success"])
            self.btn_pause.set_text("⏸  PAUSE")
            self.btn_pause.set_style("warning")
            self.log("INFO", "Bot resumed")

    def stop_bot(self):
        if not self.is_running:
            return
        write_control(stop=True)
        self.is_running = False
        self.is_paused = False

        if self.bot_process:
            try:
                self.bot_process.terminate()
                self.bot_process.wait(timeout=5)
            except:
                try:
                    self.bot_process.kill()
                except:
                    pass

        # Kill chromedriver on Windows
        if sys.platform == "win32":
            try:
                subprocess.run(["taskkill", "/F", "/IM", "chromedriver.exe"],
                               capture_output=True, timeout=5)
            except:
                pass

        self.status_indicator.set_status("stopped")
        self.status_label.config(text="STOPPED", fg=COLORS["danger"])
        self.btn_start.set_disabled(False)
        self.btn_pause.set_disabled(True)
        self.btn_stop.set_disabled(True)
        self.btn_pause.set_text("⏸  PAUSE")
        self.btn_pause.set_style("warning")

        self.log("INFO", "Bot stopped")
        self.update_current_job(title="Bot stopped")
        self.update_cc_status("idle")

    # ================================
    # BACKGROUND THREADS
    # ================================
    def _tail_log(self):
        """Tail the bot's log file for live updates."""
        log_file = os.path.join(get_data_dir(), "longform_log.txt")

        # Wait for log file to appear
        for _ in range(30):
            if os.path.exists(log_file) or not self.is_running:
                break
            time.sleep(1)

        if not os.path.exists(log_file):
            return

        try:
            with open(log_file, "r", encoding="utf-8", errors="replace") as f:
                # Seek to end
                f.seek(0, 2)
                while self.is_running:
                    line = f.readline()
                    if line:
                        self.root.after(0, self._insert_log_line, line)
                    else:
                        time.sleep(0.2)
        except:
            pass

    def _poll_cc_bridge(self):
        """Poll Claude Code bridge files for AI activity status."""
        bridge_dir = os.path.dirname(os.path.abspath(resource_path("cc_ai_bridge.py")))
        q_file = os.path.join(bridge_dir, "cc_question.json")
        bq_file = os.path.join(bridge_dir, "cc_batch_question.json")

        while self.is_running:
            try:
                pending = os.path.exists(q_file) or os.path.exists(bq_file)
                if pending and not self.cc_stats.get("pending"):
                    self.cc_stats["pending"] = True
                    question = ""
                    try:
                        f_path = q_file if os.path.exists(q_file) else bq_file
                        with open(f_path, "r") as f:
                            data = json.load(f)
                            question = data.get("user_prompt", "")[:80]
                    except:
                        pass
                    self.root.after(0, self.update_cc_status, "waiting", question)
                elif not pending and self.cc_stats.get("pending"):
                    self.cc_stats["pending"] = False
                    self.root.after(0, self.update_cc_status, "idle")
            except:
                pass
            time.sleep(2)

    def _update_timer(self):
        if not self.is_running or not self.session_start:
            return
        elapsed = int(time.time() - self.session_start)
        h, m, s = elapsed // 3600, (elapsed % 3600) // 60, elapsed % 60
        self.timer_label.config(text=f"{h:02d}:{m:02d}:{s:02d}")
        self.root.after(1000, self._update_timer)

    def _auto_refresh(self):
        """Auto-refresh stats and analytics every 15 seconds."""
        self.refresh_stats()
        self.refresh_analytics()
        self.root.after(15000, self._auto_refresh)


# ================================
# DARK TITLE BAR (Windows)
# ================================
def set_dark_title_bar(root):
    if sys.platform == "win32":
        try:
            import ctypes
            hwnd = ctypes.windll.user32.GetParent(root.winfo_id())
            DWMWA_USE_IMMERSIVE_DARK_MODE = 20
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE,
                ctypes.byref(ctypes.c_int(1)), ctypes.sizeof(ctypes.c_int))
        except:
            pass


# ================================
# ENTRY POINT
# ================================
def main():
    root = tk.Tk()
    root.withdraw()
    set_dark_title_bar(root)
    root.deiconify()

    app = LongFormDashboard(root)
    root.mainloop()


if __name__ == "__main__":
    main()
