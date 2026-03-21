"""
SeekMateAI Dashboard v2 — Multi-Bot Manager
Features: stat cards, progress bars, tabbed logs, job history, speed controls,
mini charts, system tray, desktop notifications, pause/resume, auto-restart.
"""
import tkinter as tk
from tkinter import ttk, messagebox
import subprocess
import sys
import json
import os
import re
import threading
import time
from datetime import datetime, timedelta

# Run from script directory so launcher and config paths work
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if os.getcwd() != SCRIPT_DIR:
    os.chdir(SCRIPT_DIR)

INSTANCES_FILE = os.path.join(SCRIPT_DIR, "bot_instances.json")

# ── Color Palette ──────────────────────────────────────────────
C = {
    "bg":           "#0f0f1a",
    "surface":      "#1a1a2e",
    "surface2":     "#222240",
    "border":       "#2a2a4a",
    "card":         "#1e1e36",
    "accent":       "#6c63ff",
    "accent_hover": "#7f78ff",
    "green":        "#00c853",
    "green_dim":    "#1b3a2a",
    "red":          "#ff1744",
    "red_dim":      "#3e1b1b",
    "orange":       "#ff9100",
    "yellow":       "#ffd600",
    "blue":         "#448aff",
    "text":         "#e8e8f0",
    "text_dim":     "#8888aa",
    "text_muted":   "#555577",
    "header_left":  "#1a1a3e",
    "header_right": "#0f0f2e",
}

# ── Toast Notifications ────────────────────────────────────────
_toast_available = False
_toaster = None
try:
    from win10toast import ToastNotifier
    _toaster = ToastNotifier()
    _toast_available = True
except Exception:
    pass

def notify(title, msg):
    if _toast_available and _toaster:
        try:
            threading.Thread(
                target=_toaster.show_toast,
                args=(title, msg),
                kwargs={"duration": 4, "threaded": True},
                daemon=True,
            ).start()
        except Exception:
            pass

# ── System Tray ────────────────────────────────────────────────
_tray_available = False
try:
    import pystray
    from PIL import Image, ImageDraw
    _tray_available = True
except ImportError:
    pass

def _create_tray_icon_image():
    """Create a simple coloured icon for the system tray."""
    img = Image.new("RGB", (64, 64), C["accent"])
    d = ImageDraw.Draw(img)
    d.rectangle([8, 8, 56, 56], fill="#1a1a2e")
    d.text((18, 18), "SM", fill=C["accent"])
    return img


# ══════════════════════════════════════════════════════════════
#  DASHBOARD
# ══════════════════════════════════════════════════════════════
class MultiBotGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("SeekMateAI — Dashboard v2")
        self.root.geometry("1700x920")
        self.root.minsize(1100, 700)
        self.root.configure(bg=C["bg"])

        # Try to set icon
        try:
            icon_path = os.path.join(SCRIPT_DIR, "icon.ico")
            if os.path.exists(icon_path):
                self.root.iconbitmap(icon_path)
        except Exception:
            pass

        # Session baselines so tallies reset each time dashboard starts
        self.session_baseline_jobs = {}
        self.session_baseline_scanned = {}

        self.selected_instance_for_log = None
        self.log_tail_lines = 150
        self.log_filter = "All"  # All | Errors | Applications | Skipped
        self.prev_notification_counts = {}  # for milestone notifications
        self.chart_data = {}  # name -> list of (timestamp, cumulative_jobs)

        self.load_instances()
        self._init_session_baselines()
        self._build_ui()
        self.refresh_list()

        self.auto_refresh_running = True
        self.auto_refresh()
        self.log_preview_running = True
        self._schedule_log_preview()

        self._start_whatsapp_scheduler()
        self._setup_tray()

        self.root.bind("<F5>", lambda e: self.refresh_list())
        self.root.bind("<Control-r>", lambda e: self.refresh_list())

    # ── Session Baselines ─────────────────────────────────────
    def _init_session_baselines(self):
        self.session_baseline_jobs = {}
        self.session_baseline_scanned = {}
        if not getattr(self, "instances", None):
            return
        for name, info in self.instances.items():
            log_path = self._log_path(name)
            self.session_baseline_jobs[name] = int(self._count_jobs_applied(log_path) or 0)
            self.session_baseline_scanned[name] = int(self._count_jobs_scanned(log_path) or 0)

    def _session_counts(self, name, abs_jobs, abs_scanned):
        if name not in self.session_baseline_jobs:
            self.session_baseline_jobs[name] = abs_jobs
        if name not in self.session_baseline_scanned:
            self.session_baseline_scanned[name] = abs_scanned
        return (
            max(0, abs_jobs - self.session_baseline_jobs.get(name, 0)),
            max(0, abs_scanned - self.session_baseline_scanned.get(name, 0)),
        )

    # ── Instance Data ─────────────────────────────────────────
    def load_instances(self):
        if os.path.exists(INSTANCES_FILE):
            try:
                with open(INSTANCES_FILE, "r", encoding="utf-8") as f:
                    self.instances = json.load(f)
            except Exception:
                self.instances = {}
        else:
            self.instances = {}

    def _log_path(self, name):
        if name in self.instances:
            p = self.instances[name].get("log_file", os.path.join(SCRIPT_DIR, f"log_{name}.txt"))
        else:
            p = os.path.join(SCRIPT_DIR, f"log_{name}.txt")
        return p if os.path.isabs(p) else os.path.join(SCRIPT_DIR, p)

    def _config_path(self, name):
        if name not in self.instances:
            return ""
        p = self.instances[name].get("config_file", "")
        return p if os.path.isabs(p) else os.path.join(SCRIPT_DIR, p)

    def _control_path(self, name):
        if name not in self.instances:
            return ""
        p = self.instances[name].get("control_file", os.path.join(SCRIPT_DIR, f"control_{name}.json"))
        return p if os.path.isabs(p) else os.path.join(SCRIPT_DIR, p)

    def _load_config(self, name):
        p = self._config_path(name)
        if p and os.path.exists(p):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    def _save_config(self, name, cfg):
        p = self._config_path(name)
        if p:
            with open(p, "w", encoding="utf-8") as f:
                json.dump(cfg, f, indent=4)

    def check_process_alive(self, pid):
        if not pid:
            return False
        try:
            if sys.platform == "win32":
                result = subprocess.run(
                    ["tasklist", "/FI", f"PID eq {pid}"],
                    capture_output=True, text=True, timeout=5,
                    creationflags=subprocess.CREATE_NO_WINDOW,
                )
                return str(pid) in result.stdout
            else:
                os.kill(int(pid), 0)
                return True
        except Exception:
            return False

    # ══════════════════════════════════════════════════════════
    #  BUILD UI
    # ══════════════════════════════════════════════════════════
    def _build_ui(self):
        # ── Header ────────────────────────────────────────────
        header = tk.Frame(self.root, bg=C["header_left"], height=56)
        header.pack(fill=tk.X, side=tk.TOP)
        header.pack_propagate(False)

        tk.Label(header, text="  SeekMateAI", font=("Segoe UI", 16, "bold"),
                 fg=C["accent"], bg=C["header_left"]).pack(side=tk.LEFT, padx=(16, 4), pady=10)
        tk.Label(header, text="Dashboard v2", font=("Segoe UI", 11),
                 fg=C["text_dim"], bg=C["header_left"]).pack(side=tk.LEFT, pady=10)

        self.clock_label = tk.Label(header, text="", font=("Segoe UI", 10),
                                    fg=C["text_muted"], bg=C["header_left"])
        self.clock_label.pack(side=tk.RIGHT, padx=16, pady=10)
        self._update_clock()

        # ── Stat Cards ────────────────────────────────────────
        cards_frame = tk.Frame(self.root, bg=C["bg"], pady=8)
        cards_frame.pack(fill=tk.X, padx=16)

        self.stat_cards = {}
        card_defs = [
            ("active_bots", "Active Bots", "0", C["blue"]),
            ("total_scanned", "Scanned", "0", C["yellow"]),
            ("total_applied", "Applied", "0", C["green"]),
            ("success_rate", "Success Rate", "0%", C["accent"]),
            ("jobs_per_hour", "Jobs/Hour", "0.0", C["orange"]),
        ]
        for key, label, default, color in card_defs:
            card = tk.Frame(cards_frame, bg=C["card"], highlightbackground=C["border"],
                           highlightthickness=1, padx=20, pady=10)
            card.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=6)

            tk.Label(card, text=label, font=("Segoe UI", 9),
                     fg=C["text_dim"], bg=C["card"]).pack(anchor="w")
            val_label = tk.Label(card, text=default, font=("Segoe UI", 22, "bold"),
                                 fg=color, bg=C["card"])
            val_label.pack(anchor="w")
            self.stat_cards[key] = val_label

        # ── Toolbar ───────────────────────────────────────────
        toolbar = tk.Frame(self.root, bg=C["bg"], pady=6)
        toolbar.pack(fill=tk.X, padx=16)

        btn_defs = [
            ("Start All",       C["green"],  "#00a844", self.start_all),
            ("Stop All",        C["red"],    "#cc1133", self.stop_all),
            ("Pause Selected",  C["orange"], "#cc7700", self._pause_selected),
            ("Resume Selected", C["blue"],   "#3377dd", self._resume_selected),
            ("Add Instance",    C["accent"], C["accent_hover"], self.add_instance),
            ("Slack Settings",  "#611f69",   "#7a2980", self.open_slack_settings),
            ("Refresh",         C["surface2"], C["border"], self.refresh_list),
        ]
        for text, bg_color, hover_color, cmd in btn_defs:
            btn = tk.Button(toolbar, text=text, command=cmd,
                           font=("Segoe UI", 9, "bold"), fg="white", bg=bg_color,
                           activebackground=hover_color, relief=tk.FLAT,
                           cursor="hand2", padx=14, pady=4)
            btn.pack(side=tk.LEFT, padx=3)
            btn.bind("<Enter>", lambda e, b=btn, c=hover_color: b.config(bg=c))
            btn.bind("<Leave>", lambda e, b=btn, c=bg_color: b.config(bg=c))

        # ── Main Paned Content ────────────────────────────────
        paned = tk.PanedWindow(self.root, orient=tk.HORIZONTAL, sashwidth=4,
                               bg=C["border"], sashrelief=tk.FLAT)
        paned.pack(fill=tk.BOTH, expand=True, padx=16, pady=(0, 8))

        # ── Left: Bot Table ───────────────────────────────────
        left = tk.Frame(paned, bg=C["bg"])
        paned.add(left, minsize=520)

        # Style the treeview
        style = ttk.Style(self.root)
        style.theme_use("clam")
        style.configure("Bot.Treeview",
                        background=C["surface"],
                        foreground=C["text"],
                        fieldbackground=C["surface"],
                        rowheight=36,
                        font=("Segoe UI", 10))
        style.configure("Bot.Treeview.Heading",
                        background=C["surface2"],
                        foreground="#ccc",
                        font=("Segoe UI", 9, "bold"),
                        relief=tk.FLAT)
        style.map("Bot.Treeview",
                  background=[("selected", "#2a3a6a")],
                  foreground=[("selected", "#fff")])
        style.map("Bot.Treeview.Heading",
                  background=[("active", C["border"])])

        table_frame = tk.Frame(left, bg=C["surface"], highlightbackground=C["border"],
                               highlightthickness=1)
        table_frame.pack(fill=tk.BOTH, expand=True)

        columns = ("Name", "Status", "Progress", "Scanned", "Applied", "Skipped", "Failed", "Time", "J/Hr", "Last Log")
        self.tree = ttk.Treeview(table_frame, columns=columns, show="headings",
                                 height=14, selectmode="browse", style="Bot.Treeview")
        self.tree.tag_configure("running", background=C["green_dim"])
        self.tree.tag_configure("stopped", background=C["surface"])
        self.tree.tag_configure("crashed", background=C["red_dim"])
        self.tree.tag_configure("paused", background="#2a2a1a")

        col_widths = {
            "Name": 140, "Status": 90, "Progress": 80, "Scanned": 70,
            "Applied": 65, "Skipped": 65, "Failed": 55, "Time": 70,
            "J/Hr": 50, "Last Log": 240,
        }
        for col in columns:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=col_widths.get(col, 80), minwidth=40)

        tree_scroll = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=tree_scroll.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tree_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.bind("<<TreeviewSelect>>", self._on_select)
        self.tree.bind("<Double-1>", lambda e: self.open_config())

        # ── Action Row ────────────────────────────────────────
        actions = tk.Frame(left, bg=C["bg"], pady=6)
        actions.pack(fill=tk.X)

        action_btns = [
            ("Start",  C["green"],   self.start_selected),
            ("Stop",   C["red"],     self.stop_selected),
            ("Config", C["orange"],  self.open_config),
            ("Log",    C["surface2"], self.view_log),
            ("Remove", C["text_muted"], self.remove_selected),
        ]
        for text, color, cmd in action_btns:
            b = tk.Button(actions, text=text, command=cmd,
                         font=("Segoe UI", 9), fg="white", bg=color,
                         relief=tk.FLAT, cursor="hand2", padx=10, pady=2)
            b.pack(side=tk.LEFT, padx=2)

        # ── Speed Controls ────────────────────────────────────
        speed_frame = tk.Frame(left, bg=C["card"], highlightbackground=C["border"],
                               highlightthickness=1, padx=12, pady=8)
        speed_frame.pack(fill=tk.X, pady=(6, 0))

        tk.Label(speed_frame, text="Speed Controls", font=("Segoe UI", 9, "bold"),
                 fg=C["text_dim"], bg=C["card"]).pack(anchor="w")

        scan_row = tk.Frame(speed_frame, bg=C["card"])
        scan_row.pack(fill=tk.X, pady=2)
        tk.Label(scan_row, text="Scan:", font=("Segoe UI", 9),
                 fg=C["text"], bg=C["card"], width=6).pack(side=tk.LEFT)
        self.scan_speed_var = tk.IntVar(value=50)
        self.scan_slider = tk.Scale(scan_row, from_=1, to=100, orient=tk.HORIZONTAL,
                                    variable=self.scan_speed_var, bg=C["card"], fg=C["text"],
                                    troughcolor=C["surface"], highlightthickness=0,
                                    sliderrelief=tk.FLAT, font=("Segoe UI", 8),
                                    command=lambda v: self._on_speed_change())
        self.scan_slider.pack(side=tk.LEFT, fill=tk.X, expand=True)

        apply_row = tk.Frame(speed_frame, bg=C["card"])
        apply_row.pack(fill=tk.X, pady=2)
        tk.Label(apply_row, text="Apply:", font=("Segoe UI", 9),
                 fg=C["text"], bg=C["card"], width=6).pack(side=tk.LEFT)
        self.apply_speed_var = tk.IntVar(value=50)
        self.apply_slider = tk.Scale(apply_row, from_=1, to=100, orient=tk.HORIZONTAL,
                                     variable=self.apply_speed_var, bg=C["card"], fg=C["text"],
                                     troughcolor=C["surface"], highlightthickness=0,
                                     sliderrelief=tk.FLAT, font=("Segoe UI", 8),
                                     command=lambda v: self._on_speed_change())
        self.apply_slider.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # ── Mini Chart ────────────────────────────────────────
        chart_frame = tk.Frame(left, bg=C["card"], highlightbackground=C["border"],
                               highlightthickness=1, padx=12, pady=8)
        chart_frame.pack(fill=tk.X, pady=(6, 0))

        tk.Label(chart_frame, text="Applications Over Time", font=("Segoe UI", 9, "bold"),
                 fg=C["text_dim"], bg=C["card"]).pack(anchor="w")

        self.chart_canvas = tk.Canvas(chart_frame, bg=C["surface"], height=80,
                                      highlightthickness=0)
        self.chart_canvas.pack(fill=tk.X, pady=(4, 0))

        # ── Energy Mode ──────────────────────────────────────
        energy_frame = tk.Frame(left, bg=C["card"], highlightbackground=C["border"],
                                highlightthickness=1, padx=12, pady=8)
        energy_frame.pack(fill=tk.X, pady=(6, 0))

        energy_header = tk.Frame(energy_frame, bg=C["card"])
        energy_header.pack(fill=tk.X)
        tk.Label(energy_header, text="Energy Mode", font=("Segoe UI", 9, "bold"),
                 fg=C["yellow"], bg=C["card"]).pack(side=tk.LEFT)

        self.energy_status_label = tk.Label(energy_header, text="",
                                             font=("Segoe UI", 8), fg=C["text_muted"],
                                             bg=C["card"])
        self.energy_status_label.pack(side=tk.RIGHT)

        energy_btns = tk.Frame(energy_frame, bg=C["card"])
        energy_btns.pack(fill=tk.X, pady=(4, 2))

        tk.Button(energy_btns, text="Screen Off Now", command=self._screen_off,
                 font=("Segoe UI", 8, "bold"), fg="white", bg="#555577",
                 relief=tk.FLAT, cursor="hand2", padx=8, pady=2).pack(side=tk.LEFT, padx=2)

        self.auto_screen_off_var = tk.BooleanVar(value=False)
        tk.Checkbutton(energy_btns, text="Auto screen off when bots run",
                       variable=self.auto_screen_off_var, font=("Segoe UI", 8),
                       fg=C["text"], bg=C["card"], selectcolor=C["surface"],
                       activebackground=C["card"], activeforeground=C["text"],
                       command=self._on_auto_screen_toggle).pack(side=tk.LEFT, padx=6)

        # Scheduled shutdown row
        shutdown_row = tk.Frame(energy_frame, bg=C["card"])
        shutdown_row.pack(fill=tk.X, pady=(4, 0))

        tk.Label(shutdown_row, text="Shutdown at:", font=("Segoe UI", 8),
                 fg=C["text"], bg=C["card"]).pack(side=tk.LEFT)

        self.shutdown_hour_var = tk.StringVar(value="23")
        self.shutdown_min_var = tk.StringVar(value="30")

        h_spin = tk.Spinbox(shutdown_row, from_=0, to=23, width=3, wrap=True,
                            textvariable=self.shutdown_hour_var, font=("Segoe UI", 9),
                            bg=C["surface"], fg=C["text"], buttonbackground=C["surface2"],
                            relief=tk.FLAT, format="%02.0f")
        h_spin.pack(side=tk.LEFT, padx=2)
        tk.Label(shutdown_row, text=":", font=("Segoe UI", 9, "bold"),
                 fg=C["text"], bg=C["card"]).pack(side=tk.LEFT)
        m_spin = tk.Spinbox(shutdown_row, from_=0, to=59, width=3, wrap=True,
                            textvariable=self.shutdown_min_var, font=("Segoe UI", 9),
                            bg=C["surface"], fg=C["text"], buttonbackground=C["surface2"],
                            relief=tk.FLAT, format="%02.0f")
        m_spin.pack(side=tk.LEFT, padx=2)

        self.shutdown_action_var = tk.StringVar(value="sleep")
        for text, val in [("Sleep", "sleep"), ("Shutdown", "shutdown")]:
            tk.Radiobutton(shutdown_row, text=text, variable=self.shutdown_action_var,
                          value=val, font=("Segoe UI", 8), fg=C["text"], bg=C["card"],
                          selectcolor=C["surface"], activebackground=C["card"]).pack(side=tk.LEFT, padx=2)

        self.shutdown_enabled_var = tk.BooleanVar(value=False)
        self.shutdown_toggle_btn = tk.Button(shutdown_row, text="Enable",
                                              command=self._toggle_shutdown_timer,
                                              font=("Segoe UI", 8, "bold"), fg="white",
                                              bg=C["text_muted"], relief=tk.FLAT,
                                              cursor="hand2", padx=8)
        self.shutdown_toggle_btn.pack(side=tk.LEFT, padx=6)

        self._shutdown_timer_id = None

        # ── Right: Tabbed Panel ───────────────────────────────
        right = tk.Frame(paned, bg=C["surface"])
        paned.add(right, minsize=420)

        # Tab bar
        tab_bar = tk.Frame(right, bg=C["surface2"], height=36)
        tab_bar.pack(fill=tk.X)
        tab_bar.pack_propagate(False)

        self.active_tab = "logs"
        self.tab_btns = {}

        for tab_id, tab_label in [("logs", "Logs"), ("history", "Job History")]:
            btn = tk.Button(tab_bar, text=tab_label, font=("Segoe UI", 10),
                           fg=C["text"], bg=C["surface2"], relief=tk.FLAT,
                           cursor="hand2", padx=16,
                           command=lambda t=tab_id: self._switch_tab(t))
            btn.pack(side=tk.LEFT, padx=1)
            self.tab_btns[tab_id] = btn

        # Log filter (right side of tab bar)
        filter_frame = tk.Frame(tab_bar, bg=C["surface2"])
        filter_frame.pack(side=tk.RIGHT, padx=8)
        tk.Label(filter_frame, text="Filter:", font=("Segoe UI", 8),
                 fg=C["text_muted"], bg=C["surface2"]).pack(side=tk.LEFT, padx=(0, 4))
        self.filter_var = tk.StringVar(value="All")
        filter_menu = ttk.Combobox(filter_frame, textvariable=self.filter_var,
                                    values=["All", "Errors", "Applications", "Skipped"],
                                    state="readonly", width=12, font=("Segoe UI", 8))
        filter_menu.pack(side=tk.LEFT)
        filter_menu.bind("<<ComboboxSelected>>", lambda e: self._on_filter_change())

        # Instance label
        self.log_instance_label = tk.Label(right, text="Select an instance",
                                            font=("Segoe UI", 10), fg=C["text_dim"],
                                            bg=C["surface"], anchor="w", padx=12, pady=4)
        self.log_instance_label.pack(fill=tk.X)

        # Log text panel
        self.log_text = tk.Text(right, wrap=tk.WORD, font=("Consolas", 9),
                                bg="#12121f", fg=C["text"], insertbackground=C["text"],
                                relief=tk.FLAT, padx=10, pady=8)
        self.log_text.tag_configure("error", foreground="#ff6b6b")
        self.log_text.tag_configure("warn", foreground="#ffd93d")
        self.log_text.tag_configure("success", foreground="#6bff6b")
        self.log_text.tag_configure("skip", foreground="#888")
        self.log_text.tag_configure("job_header", foreground=C["accent"], font=("Consolas", 9, "bold"))

        log_scroll = ttk.Scrollbar(right, orient=tk.VERTICAL, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=log_scroll.set)
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        log_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        # Job history panel (hidden by default)
        self.history_frame = tk.Frame(right, bg="#12121f")
        self.history_tree = None  # built on first show

        # ── Status Bar ────────────────────────────────────────
        status_bar = tk.Frame(self.root, bg=C["surface2"], height=26)
        status_bar.pack(fill=tk.X, side=tk.BOTTOM)
        status_bar.pack_propagate(False)
        self.status_label = tk.Label(
            status_bar,
            text=" F5 Refresh  |  Double-click row: Config  |  Slack & WhatsApp notifications active",
            font=("Segoe UI", 8), fg=C["text_muted"], bg=C["surface2"]
        )
        self.status_label.pack(side=tk.LEFT, padx=12, pady=4)

        self._style_active_tab()
        self._load_speed_from_config()

    # ── Clock ─────────────────────────────────────────────────
    def _update_clock(self):
        self.clock_label.config(text=datetime.now().strftime("%A  %H:%M:%S"))
        self.root.after(1000, self._update_clock)

    # ── Tabs ──────────────────────────────────────────────────
    def _switch_tab(self, tab_id):
        self.active_tab = tab_id
        self._style_active_tab()
        if tab_id == "logs":
            self.history_frame.pack_forget()
            self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            self._update_log_preview()
        elif tab_id == "history":
            self.log_text.pack_forget()
            self._show_job_history()

    def _style_active_tab(self):
        for tid, btn in self.tab_btns.items():
            if tid == self.active_tab:
                btn.config(bg=C["accent"], fg="white")
            else:
                btn.config(bg=C["surface2"], fg=C["text_dim"])

    def _on_filter_change(self):
        self.log_filter = self.filter_var.get()
        self._update_log_preview()

    # ── Job History ───────────────────────────────────────────
    def _show_job_history(self):
        self.history_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        # Build treeview if not yet created
        if not self.history_tree:
            cols = ("Time", "Title", "Company", "Status")
            self.history_tree = ttk.Treeview(self.history_frame, columns=cols,
                                              show="headings", style="Bot.Treeview")
            for col in cols:
                self.history_tree.heading(col, text=col)
            self.history_tree.column("Time", width=70)
            self.history_tree.column("Title", width=200)
            self.history_tree.column("Company", width=150)
            self.history_tree.column("Status", width=80)
            hs = ttk.Scrollbar(self.history_frame, orient=tk.VERTICAL,
                                command=self.history_tree.yview)
            self.history_tree.configure(yscrollcommand=hs.set)
            self.history_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            hs.pack(side=tk.RIGHT, fill=tk.Y)

        # Clear and populate
        for item in self.history_tree.get_children():
            self.history_tree.delete(item)

        name = self.selected_instance_for_log
        if not name:
            return
        log_path = self._log_path(name)
        if not os.path.exists(log_path):
            return

        try:
            with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()

            # Parse job entries: "[*] Job N: TITLE | COMPANY" followed by status lines
            job_pattern = re.compile(
                r'\[(\d{2}:\d{2}:\d{2})?\]?\s*\[\*\].*?Job \d+:\s*(.+?)\s*\|\s*(.+?)$',
                re.MULTILINE
            )
            # Simpler pattern: just find job lines and the next status line
            lines = content.split("\n")
            entries = []
            i = 0
            while i < len(lines):
                line = lines[i]
                m = re.search(r'\[\*\].*?Job \d+:\s*(.+?)\s*\|\s*(.+?)$', line)
                if m:
                    title = m.group(1).strip()
                    company = m.group(2).strip()
                    # Look ahead for status
                    status = "Opened"
                    ts = ""
                    # Try to extract timestamp
                    tm = re.match(r'\[(\d{2}:\d{2}:\d{2})\]', line)
                    if tm:
                        ts = tm.group(1)
                    for j in range(i + 1, min(i + 15, len(lines))):
                        sl = lines[j]
                        if "Successfully submitted" in sl or "SUBMITTED" in sl:
                            status = "Applied"
                            break
                        elif "SKIPPED" in sl:
                            status = "Skipped"
                            break
                        elif "No apply button" in sl:
                            status = "No Apply"
                            break
                        elif "Failed" in sl or "Error" in sl or "failed" in sl:
                            status = "Failed"
                            break
                        elif "tab may have been blocked" in sl:
                            status = "Blocked"
                            break
                        elif re.search(r'\[\*\].*?Job \d+:', sl):
                            break
                    entries.append((ts, title, company, status))
                i += 1

            # Insert in reverse (most recent first)
            for ts, title, company, status in reversed(entries[-200:]):
                tag = ""
                if status == "Applied":
                    tag = "running"
                elif status in ("Skipped", "No Apply", "Blocked"):
                    tag = "stopped"
                elif status == "Failed":
                    tag = "crashed"
                self.history_tree.insert("", tk.END, values=(ts, title, company, status), tags=(tag,))
        except Exception:
            pass

    # ── Tree Selection ────────────────────────────────────────
    def _on_select(self, event):
        sel = self.tree.selection()
        if sel:
            item = self.tree.item(sel[0])
            self.selected_instance_for_log = item["values"][0] if item["values"] else None
        else:
            self.selected_instance_for_log = None
        self.log_instance_label.config(
            text=f"Log: {self.selected_instance_for_log}" if self.selected_instance_for_log
            else "Select an instance",
            fg=C["text"] if self.selected_instance_for_log else C["text_dim"]
        )
        self._update_log_preview()
        self._load_speed_from_config()

    # ── Speed Controls ────────────────────────────────────────
    def _load_speed_from_config(self):
        name = self.selected_instance_for_log
        if not name:
            return
        cfg = self._load_config(name)
        if cfg:
            self.scan_speed_var.set(cfg.get("SCAN_SPEED", 50))
            self.apply_speed_var.set(cfg.get("APPLY_SPEED", 50))

    def _on_speed_change(self):
        name = self.selected_instance_for_log
        if not name:
            return
        cfg = self._load_config(name)
        if not cfg:
            return
        cfg["SCAN_SPEED"] = self.scan_speed_var.get()
        cfg["APPLY_SPEED"] = self.apply_speed_var.get()
        try:
            self._save_config(name, cfg)
        except Exception:
            pass

    # ── Log Preview ───────────────────────────────────────────
    def _update_log_preview(self):
        if self.active_tab != "logs":
            return
        if not self.selected_instance_for_log:
            self.log_text.delete("1.0", tk.END)
            self.log_text.insert(tk.END, "Select an instance to view logs.")
            return
        path = self._log_path(self.selected_instance_for_log)
        if not path or not os.path.exists(path):
            self.log_text.delete("1.0", tk.END)
            self.log_text.insert(tk.END, f"No log file yet for '{self.selected_instance_for_log}'.")
            return
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()

            # Apply filter
            if self.log_filter == "Errors":
                lines = [l for l in lines if any(k in l for k in
                         ["[ERROR]", "Error:", "Traceback", "Exception", "Failed", "[!]"])]
            elif self.log_filter == "Applications":
                lines = [l for l in lines if any(k in l for k in
                         ["SUBMITTED", "Successfully submitted", "Job ", "apply", "Applied"])]
            elif self.log_filter == "Skipped":
                lines = [l for l in lines if "SKIPPED" in l or "BLOCKED" in l or "blocked" in l]

            tail = lines[-self.log_tail_lines:] if len(lines) > self.log_tail_lines else lines

            self.log_text.delete("1.0", tk.END)
            for line in tail:
                start = self.log_text.index(tk.END)
                self.log_text.insert(tk.END, line)
                end = self.log_text.index(tk.END)
                if "[ERROR]" in line or "Error:" in line or "Traceback" in line or "Exception" in line:
                    self.log_text.tag_add("error", start, end)
                elif "[!]" in line or "WARN" in line or "Failed" in line:
                    self.log_text.tag_add("warn", start, end)
                elif "SUBMITTED" in line or "Successfully submitted" in line:
                    self.log_text.tag_add("success", start, end)
                elif "SKIPPED" in line or "BLOCKED" in line:
                    self.log_text.tag_add("skip", start, end)
                elif re.search(r'\[\*\].*?Job \d+:', line):
                    self.log_text.tag_add("job_header", start, end)
            self.log_text.see(tk.END)
        except Exception:
            self.log_text.delete("1.0", tk.END)
            self.log_text.insert(tk.END, "Could not read log file.")

    def _schedule_log_preview(self):
        if getattr(self, "log_preview_running", True):
            self._update_log_preview()
            self.root.after(2000, self._schedule_log_preview)

    # ── Log Parsing ───────────────────────────────────────────
    def _count_jobs_applied(self, log_file):
        if not os.path.exists(log_file):
            return "0"
        try:
            with open(log_file, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
            matches = re.findall(r'Successful submissions:\s*(\d+)', content)
            if matches:
                total = 0
                prev = 0
                for m in matches:
                    val = int(m)
                    if val <= prev:
                        total += prev
                    prev = val
                total += prev
                return str(total)
            final = re.search(r'Successfully submitted\s+(\d+)\s+REAL applications', content)
            if final:
                return final.group(1)
        except Exception:
            pass
        return "0"

    def _count_jobs_scanned(self, log_file):
        if not os.path.exists(log_file):
            return "0"
        try:
            with open(log_file, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
            matches = re.findall(r'\[\*\].*?Job \d+:', content)
            return str(len(matches))
        except Exception:
            pass
        return "0"

    def _count_skipped(self, log_file):
        if not os.path.exists(log_file):
            return 0
        try:
            with open(log_file, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
            return len(re.findall(r'SKIPPED|BLOCKED|No apply button|tab may have been blocked', content))
        except Exception:
            return 0

    def _count_failed(self, log_file):
        if not os.path.exists(log_file):
            return 0
        try:
            with open(log_file, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
            return len(re.findall(r'Failed to click apply|Error during apply|Failed to open job', content))
        except Exception:
            return 0

    def _get_last_log_line(self, log_file):
        if not os.path.exists(log_file):
            return "—"
        try:
            with open(log_file, "r", encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()
            for line in reversed(lines):
                stripped = line.strip()
                if stripped and not stripped.startswith("Traceback"):
                    return stripped[:77] + "..." if len(stripped) > 80 else stripped
        except Exception:
            pass
        return "—"

    def _get_max_jobs(self, name):
        cfg = self._load_config(name)
        return cfg.get("MAX_JOBS", 50) if cfg else 50

    def _get_elapsed(self, start_time_str, log_file=None):
        start_time = None
        if start_time_str:
            try:
                start_time = datetime.fromisoformat(start_time_str)
            except Exception:
                pass
        if not start_time and log_file and os.path.exists(log_file):
            try:
                start_time = datetime.fromtimestamp(os.path.getmtime(log_file))
            except Exception:
                pass
        if not start_time:
            return "—"
        total = int((datetime.now() - start_time).total_seconds())
        h, m, s = total // 3600, (total % 3600) // 60, total % 60
        return f"{h:02d}:{m:02d}:{s:02d}" if h > 0 else f"{m:02d}:{s:02d}"

    def _get_jobs_per_hour(self, jobs_applied, start_time_str, log_file=None):
        if int(jobs_applied or 0) == 0:
            return "0.0"
        start_time = None
        if start_time_str:
            try:
                start_time = datetime.fromisoformat(start_time_str)
            except Exception:
                pass
        if not start_time and log_file and os.path.exists(log_file):
            try:
                start_time = datetime.fromtimestamp(os.path.getmtime(log_file))
            except Exception:
                pass
        if not start_time:
            return "—"
        hours = (datetime.now() - start_time).total_seconds() / 3600.0
        return f"{int(jobs_applied) / hours:.1f}" if hours > 0 else "0.0"

    def _get_api_status(self, info):
        config_path = info.get("config_file", "")
        if not os.path.isabs(config_path):
            config_path = os.path.join(SCRIPT_DIR, config_path)
        if not config_path or not os.path.exists(config_path):
            return False
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            key = (cfg.get("OPENAI_API_KEY") or os.environ.get("OPENAI_API_KEY", "")).strip()
            return bool(key)
        except Exception:
            return False

    # ── Mini Chart ────────────────────────────────────────────
    def _update_chart(self, total_jobs):
        now = time.time()
        if "global" not in self.chart_data:
            self.chart_data["global"] = []
        self.chart_data["global"].append((now, total_jobs))
        # Keep last 60 data points
        self.chart_data["global"] = self.chart_data["global"][-60:]

        data = self.chart_data["global"]
        self.chart_canvas.delete("all")
        w = self.chart_canvas.winfo_width()
        h = self.chart_canvas.winfo_height()
        if w < 10 or h < 10 or len(data) < 2:
            return

        vals = [d[1] for d in data]
        max_val = max(vals) or 1
        min_val = min(vals)

        # Draw grid lines
        for i in range(5):
            y = h - (i / 4) * h
            self.chart_canvas.create_line(0, y, w, y, fill=C["border"], dash=(2, 4))

        # Draw line
        points = []
        for i, (_, v) in enumerate(data):
            x = (i / (len(data) - 1)) * w
            y = h - ((v - min_val) / (max_val - min_val + 1)) * (h - 10) - 5
            points.append((x, y))

        if len(points) >= 2:
            # Fill area under curve
            fill_points = [(points[0][0], h)] + points + [(points[-1][0], h)]
            flat = [coord for p in fill_points for coord in p]
            self.chart_canvas.create_polygon(flat, fill="#1a2a4a", outline="")

            # Draw the line
            line_flat = [coord for p in points for coord in p]
            self.chart_canvas.create_line(line_flat, fill=C["accent"], width=2, smooth=True)

            # Current value label
            self.chart_canvas.create_text(w - 4, 8, text=str(total_jobs),
                                           fill=C["accent"], font=("Segoe UI", 8, "bold"),
                                           anchor="ne")

    # ── Refresh List ──────────────────────────────────────────
    def refresh_list(self):
        self.load_instances()

        # Health check — auto-restart crashed
        changed = False
        for name, info in self.instances.items():
            if info.get("status") == "running":
                if not self.check_process_alive(info.get("process_id")):
                    info["status"] = "crashed"
                    changed = True
                    notify("SeekMateAI", f"Bot '{name}' crashed! Auto-restarting...")
                    # Auto-restart
                    info["status"] = "stopped"
                    info.pop("process_id", None)
                    try:
                        with open(INSTANCES_FILE, "w", encoding="utf-8") as f:
                            json.dump(self.instances, f, indent=4)
                        subprocess.run(
                            [sys.executable, "multi_bot_launcher.py", "start", name],
                            capture_output=True, text=True, timeout=10, cwd=SCRIPT_DIR,
                            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
                        )
                        self.load_instances()
                    except Exception as e:
                        print(f"[Dashboard] Auto-restart failed for {name}: {e}")

        if changed:
            try:
                with open(INSTANCES_FILE, "w", encoding="utf-8") as f:
                    json.dump(self.instances, f, indent=4)
            except Exception:
                pass

        # Preserve selection
        sel = self.tree.selection()
        selected_name = None
        if sel:
            item = self.tree.item(sel[0])
            selected_name = item["values"][0] if item["values"] else None

        for item in self.tree.get_children():
            self.tree.delete(item)

        if not self.instances:
            self.tree.insert("", tk.END, values=(
                "No instances", "—", "—", "—", "—", "—", "—", "—", "—",
                "Click Add Instance to get started"
            ))
            self._update_stat_cards(0, 0, 0, 0, 0)
            return

        total_applied = 0
        total_scanned = 0
        total_skipped = 0
        total_failed = 0
        active_count = 0
        total_jph = 0.0

        for name, info in self.instances.items():
            status = info.get("status", "stopped")

            # Check pause state
            ctrl_path = self._control_path(name)
            is_paused = False
            if ctrl_path and os.path.exists(ctrl_path):
                try:
                    with open(ctrl_path, "r") as f:
                        ctrl = json.load(f)
                    if ctrl.get("status") == "pause":
                        is_paused = True
                except Exception:
                    pass

            if status == "running" and is_paused:
                status_display = "Paused"
                tag = "paused"
            elif status == "running":
                status_display = "Running"
                tag = "running"
                active_count += 1
            elif status == "crashed":
                status_display = "Crashed"
                tag = "crashed"
            else:
                status_display = "Stopped"
                tag = "stopped"

            log_file = self._log_path(name)
            abs_jobs = int(self._count_jobs_applied(log_file) or 0)
            abs_scanned = int(self._count_jobs_scanned(log_file) or 0)
            sess_jobs, sess_scanned = self._session_counts(name, abs_jobs, abs_scanned)

            skipped = self._count_skipped(log_file)
            failed = self._count_failed(log_file)
            max_jobs = self._get_max_jobs(name)
            progress = f"{sess_jobs}/{max_jobs}"

            start_time = info.get("start_time", "")
            elapsed = self._get_elapsed(start_time, log_file) if status == "running" else "—"
            jph = self._get_jobs_per_hour(str(sess_jobs), start_time, log_file) if status == "running" else "—"
            last_log = self._get_last_log_line(log_file)

            total_applied += sess_jobs
            total_scanned += sess_scanned
            total_skipped += skipped
            total_failed += failed
            try:
                total_jph += float(jph) if jph != "—" else 0
            except ValueError:
                pass

            item_id = self.tree.insert("", tk.END, values=(
                name, status_display, progress, sess_scanned, sess_jobs,
                skipped, failed, elapsed, jph,
                (last_log[:55] + "...") if len(last_log) > 55 else last_log,
            ), tags=(tag,))

            if selected_name == name:
                self.tree.selection_set(item_id)

            # Milestone notifications (every 5 jobs)
            prev = self.prev_notification_counts.get(name, 0)
            if sess_jobs > 0 and sess_jobs != prev and sess_jobs % 5 == 0:
                notify("SeekMateAI", f"{name}: {sess_jobs} jobs applied!")
            self.prev_notification_counts[name] = sess_jobs

        # Update stat cards
        success_rate = (total_applied / total_scanned * 100) if total_scanned > 0 else 0
        self._update_stat_cards(active_count, total_scanned, total_applied, success_rate, total_jph)
        self._update_chart(total_applied)
        self._energy_auto_manage()

    def _update_stat_cards(self, active, scanned, applied, rate, jph):
        self.stat_cards["active_bots"].config(text=str(active))
        self.stat_cards["total_scanned"].config(text=str(scanned))
        self.stat_cards["total_applied"].config(text=str(applied))
        self.stat_cards["success_rate"].config(text=f"{rate:.1f}%")
        self.stat_cards["jobs_per_hour"].config(text=f"{jph:.1f}")

    def auto_refresh(self):
        if self.auto_refresh_running:
            self.refresh_list()
            self.root.after(3000, self.auto_refresh)

    # ── Pause / Resume ────────────────────────────────────────
    def _pause_selected(self):
        name = self._selected_name()
        if not name:
            return
        ctrl = self._control_path(name)
        if ctrl:
            try:
                with open(ctrl, "w") as f:
                    json.dump({"status": "pause"}, f)
                notify("SeekMateAI", f"{name} paused")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to pause: {e}")
        self.refresh_list()

    def _resume_selected(self):
        name = self._selected_name()
        if not name:
            return
        ctrl = self._control_path(name)
        if ctrl:
            try:
                with open(ctrl, "w") as f:
                    json.dump({"status": "run"}, f)
                notify("SeekMateAI", f"{name} resumed")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to resume: {e}")
        self.refresh_list()

    def _selected_name(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning("Warning", "Select an instance first")
            return None
        item = self.tree.item(sel[0])
        name = item["values"][0] if item["values"] else None
        if not name or name not in self.instances:
            messagebox.showwarning("Warning", "Invalid selection")
            return None
        return name

    # ── Start / Stop / Remove ─────────────────────────────────
    def start_selected(self):
        name = self._selected_name()
        if not name:
            return
        if self.instances[name].get("status") == "running":
            messagebox.showwarning("Warning", f"'{name}' is already running!")
            return
        try:
            result = subprocess.run(
                [sys.executable, "multi_bot_launcher.py", "start", name],
                capture_output=True, text=True, timeout=10, cwd=SCRIPT_DIR,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
            )
            if result.returncode == 0:
                notify("SeekMateAI", f"Started: {name}")
            else:
                messagebox.showerror("Error", f"Failed:\n{result.stdout}{result.stderr}")
        except Exception as e:
            messagebox.showerror("Error", str(e))
        self.refresh_list()

    def stop_selected(self):
        name = self._selected_name()
        if not name:
            return
        if self.instances[name].get("status") != "running":
            messagebox.showwarning("Warning", f"'{name}' is not running!")
            return
        try:
            subprocess.run(
                [sys.executable, "multi_bot_launcher.py", "stop", name],
                capture_output=True, text=True, timeout=10, cwd=SCRIPT_DIR,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
            )
            notify("SeekMateAI", f"Stopped: {name}")
        except Exception as e:
            messagebox.showerror("Error", str(e))
        self.refresh_list()

    def remove_selected(self):
        name = self._selected_name()
        if not name:
            return
        if messagebox.askyesno("Confirm", f"Remove '{name}'? (Logs kept)"):
            subprocess.Popen(
                [sys.executable, "multi_bot_launcher.py", "remove", name],
                cwd=SCRIPT_DIR,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
            )
            self.load_instances()
            self.refresh_list()

    def start_all(self):
        if not self.instances:
            messagebox.showwarning("Warning", "No instances configured")
            return
        if messagebox.askyesno("Confirm", f"Start all {len(self.instances)} instance(s)?"):
            subprocess.Popen(
                [sys.executable, "multi_bot_launcher.py", "start-all"],
                cwd=SCRIPT_DIR,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
            )
            notify("SeekMateAI", f"Starting {len(self.instances)} bots...")
            self.refresh_list()

    def stop_all(self):
        if not self.instances:
            return
        if messagebox.askyesno("Confirm", f"Stop all {len(self.instances)} instance(s)?"):
            subprocess.Popen(
                [sys.executable, "multi_bot_launcher.py", "stop-all"],
                cwd=SCRIPT_DIR,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
            )
            notify("SeekMateAI", "All bots stopped")
            self.refresh_list()

    # ── Add Instance ──────────────────────────────────────────
    def add_instance(self):
        dialog = tk.Toplevel(self.root)
        dialog.title("Add Bot Instance")
        dialog.geometry("480x280")
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.configure(bg=C["surface"])
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() // 2) - 240
        y = (dialog.winfo_screenheight() // 2) - 140
        dialog.geometry(f"480x280+{x}+{y}")

        fields = [("Instance Name:", "name"), ("SEEK Email:", "email"), ("Full Name:", "fullname")]
        entries = {}
        for label_text, key in fields:
            tk.Label(dialog, text=label_text, font=("Segoe UI", 10),
                     fg=C["text"], bg=C["surface"]).pack(pady=(8, 2), padx=20, anchor="w")
            e = tk.Entry(dialog, width=50, font=("Segoe UI", 10),
                        bg=C["card"], fg=C["text"], relief=tk.FLAT,
                        insertbackground=C["text"])
            e.pack(padx=20, ipady=4)
            entries[key] = e
        entries["name"].focus()

        def save():
            name = entries["name"].get().strip()
            email = entries["email"].get().strip()
            fullname = entries["fullname"].get().strip()
            if not name:
                messagebox.showerror("Error", "Name is required!")
                return
            cmd = [sys.executable, "multi_bot_launcher.py", "add", name]
            if email:
                cmd.extend(["--email", email])
            if fullname:
                cmd.extend(["--name", fullname])
            try:
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=10, cwd=SCRIPT_DIR)
                if result.returncode == 0:
                    dialog.destroy()
                    self.load_instances()
                    self.refresh_list()
                    notify("SeekMateAI", f"Added instance: {name}")
                else:
                    messagebox.showerror("Error", result.stdout + result.stderr)
            except Exception as e:
                messagebox.showerror("Error", str(e))

        btn_frame = tk.Frame(dialog, bg=C["surface"])
        btn_frame.pack(pady=16)
        tk.Button(btn_frame, text="Add", command=save, width=14,
                 bg=C["accent"], fg="white", font=("Segoe UI", 10, "bold"),
                 relief=tk.FLAT, cursor="hand2").pack(side=tk.LEFT, padx=4)
        tk.Button(btn_frame, text="Cancel", command=dialog.destroy, width=14,
                 font=("Segoe UI", 10), relief=tk.FLAT, cursor="hand2",
                 bg=C["surface2"], fg=C["text"]).pack(side=tk.LEFT, padx=4)
        dialog.bind("<Return>", lambda e: save())

    # ── View Log / Open Config ────────────────────────────────
    def view_log(self):
        name = self._selected_name()
        if not name:
            return
        log_file = self._log_path(name)
        if not os.path.exists(log_file):
            messagebox.showinfo("Info", f"No log file: {log_file}")
            return
        try:
            if sys.platform == "win32":
                os.startfile(log_file)
            elif sys.platform == "darwin":
                subprocess.run(["open", log_file])
            else:
                subprocess.run(["xdg-open", log_file])
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def open_config(self):
        name = self._selected_name()
        if not name:
            return
        config_file = self._config_path(name)
        if not config_file or not os.path.exists(config_file):
            messagebox.showerror("Error", f"Config not found: {config_file}")
            return
        gui = os.path.join(SCRIPT_DIR, "config_gui.py")
        if not os.path.exists(gui):
            messagebox.showerror("Error", "config_gui.py not found")
            return
        try:
            subprocess.Popen([sys.executable, gui, config_file], cwd=SCRIPT_DIR)
        except Exception as e:
            messagebox.showerror("Error", str(e))

    # ── Slack Settings ────────────────────────────────────────
    def open_slack_settings(self):
        self.load_instances()
        if not self.instances:
            messagebox.showinfo("Info", "Add at least one instance first.")
            return

        dialog = tk.Toplevel(self.root)
        dialog.title("Slack Notifications")
        dialog.geometry("520x300")
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.configure(bg=C["surface"])
        x = (dialog.winfo_screenwidth() // 2) - 260
        y = (dialog.winfo_screenheight() // 2) - 150
        dialog.geometry(f"520x300+{x}+{y}")

        tk.Label(dialog, text="Slack — Live Job Notifications", font=("Segoe UI", 13, "bold"),
                 fg=C["text"], bg=C["surface"]).pack(pady=(12, 4))
        tk.Label(dialog, text="Get a Slack message each time a bot applies",
                 font=("Segoe UI", 9), fg=C["text_muted"], bg=C["surface"]).pack(pady=(0, 12))

        tk.Label(dialog, text="Webhook URL", font=("Segoe UI", 10),
                 fg=C["text_dim"], bg=C["surface"]).pack(anchor="w", padx=20)
        webhook_entry = tk.Entry(dialog, width=60, font=("Segoe UI", 10),
                                 bg=C["card"], fg=C["text"], relief=tk.FLAT,
                                 insertbackground=C["text"])
        webhook_entry.pack(padx=20, ipady=6)

        # Load from first instance or env
        first_name = list(self.instances.keys())[0]
        cfg = self._load_config(first_name)
        webhook_val = cfg.get("SLACK_WEBHOOK_URL", "") or os.environ.get("SLACK_WEBHOOK_URL", "")
        webhook_entry.insert(0, webhook_val)
        slack_var = tk.BooleanVar(value=cfg.get("SLACK_NOTIFICATIONS_ENABLED", False))

        tk.Checkbutton(dialog, text="Enable Slack notifications", variable=slack_var,
                       font=("Segoe UI", 10), fg=C["text"], bg=C["surface"],
                       selectcolor=C["card"], activebackground=C["surface"],
                       activeforeground=C["text"]).pack(anchor="w", padx=20, pady=8)

        apply_var = tk.StringVar(value="all")
        rf = tk.Frame(dialog, bg=C["surface"])
        rf.pack(fill=tk.X, padx=20)
        for text, val in [("All instances", "all"), ("Selected only", "selected")]:
            tk.Radiobutton(rf, text=text, variable=apply_var, value=val,
                          font=("Segoe UI", 10), fg=C["text"], bg=C["surface"],
                          selectcolor=C["card"], activebackground=C["surface"]).pack(side=tk.LEFT, padx=(0, 16))

        def save():
            webhook = webhook_entry.get().strip()
            enabled = slack_var.get()
            targets = list(self.instances.keys()) if apply_var.get() == "all" else []
            if apply_var.get() == "selected":
                n = self._selected_name()
                targets = [n] if n else []
            if not targets:
                messagebox.showwarning("Warning", "No targets")
                return
            for n in targets:
                c = self._load_config(n)
                if c:
                    c["SLACK_WEBHOOK_URL"] = webhook
                    c["SLACK_NOTIFICATIONS_ENABLED"] = enabled
                    self._save_config(n, c)
            messagebox.showinfo("Saved", f"Updated {len(targets)} instance(s)")
            dialog.destroy()

        bf = tk.Frame(dialog, bg=C["surface"])
        bf.pack(pady=12)
        tk.Button(bf, text="Save", command=save, width=12, bg="#611f69", fg="white",
                 font=("Segoe UI", 10), relief=tk.FLAT, cursor="hand2").pack(side=tk.LEFT, padx=4)
        tk.Button(bf, text="Cancel", command=dialog.destroy, width=12,
                 font=("Segoe UI", 10), relief=tk.FLAT, cursor="hand2",
                 bg=C["surface2"], fg=C["text"]).pack(side=tk.LEFT, padx=4)

    # ── WhatsApp Scheduler ────────────────────────────────────
    # ── Energy Mode ─────────────────────────────────────────
    def _screen_off(self):
        """Turn monitor off immediately. Move mouse to wake."""
        try:
            import ctypes
            ctypes.windll.user32.SendMessageW(0xFFFF, 0x0112, 0xF170, 2)
        except Exception as e:
            messagebox.showerror("Error", f"Could not turn screen off: {e}")

    def _on_auto_screen_toggle(self):
        if self.auto_screen_off_var.get():
            # Check if any bots are running and turn screen off
            running = any(i.get("status") == "running" for i in self.instances.values())
            if running:
                self.energy_status_label.config(text="Screen will turn off in 10s...", fg=C["yellow"])
                self.root.after(10000, self._auto_screen_check)
            else:
                self.energy_status_label.config(text="Waiting for bots to start...", fg=C["text_muted"])
        else:
            self.energy_status_label.config(text="", fg=C["text_muted"])
            self._release_wake_lock()

    def _auto_screen_check(self):
        """Called periodically — turn screen off if bots running + auto mode on."""
        if not self.auto_screen_off_var.get():
            return
        running = any(i.get("status") == "running" for i in self.instances.values())
        if running:
            self._screen_off()
            self._set_wake_lock()
            self.energy_status_label.config(text="Screen off — system awake for bots", fg=C["green"])

    def _set_wake_lock(self):
        """Prevent Windows from sleeping while bots are running."""
        try:
            import ctypes
            # ES_CONTINUOUS | ES_SYSTEM_REQUIRED — keep system awake, allow screen off
            ctypes.windll.kernel32.SetThreadExecutionState(0x80000001)
            self.energy_status_label.config(text="Sleep blocked — bots running", fg=C["green"])
        except Exception:
            pass

    def _release_wake_lock(self):
        """Allow Windows to sleep again."""
        try:
            import ctypes
            # ES_CONTINUOUS only — reset to normal
            ctypes.windll.kernel32.SetThreadExecutionState(0x80000000)
            self.energy_status_label.config(text="Sleep allowed", fg=C["text_muted"])
        except Exception:
            pass

    def _toggle_shutdown_timer(self):
        if self.shutdown_enabled_var.get():
            # Disable
            self.shutdown_enabled_var.set(False)
            self.shutdown_toggle_btn.config(text="Enable", bg=C["text_muted"])
            if self._shutdown_timer_id:
                self.root.after_cancel(self._shutdown_timer_id)
                self._shutdown_timer_id = None
            # Cancel any pending Windows shutdown
            try:
                subprocess.run(["shutdown", "/a"], capture_output=True,
                              creationflags=subprocess.CREATE_NO_WINDOW)
            except Exception:
                pass
            self.energy_status_label.config(text="Timer cancelled", fg=C["text_muted"])
        else:
            # Enable
            self.shutdown_enabled_var.set(True)
            self.shutdown_toggle_btn.config(text="Cancel", bg=C["red"])
            self._check_shutdown_timer()

    def _check_shutdown_timer(self):
        """Check every 30s if it's time to sleep/shutdown."""
        if not self.shutdown_enabled_var.get():
            return
        try:
            target_h = int(self.shutdown_hour_var.get())
            target_m = int(self.shutdown_min_var.get())
        except ValueError:
            self._shutdown_timer_id = self.root.after(30000, self._check_shutdown_timer)
            return

        now = datetime.now()
        target = now.replace(hour=target_h, minute=target_m, second=0, microsecond=0)
        if target < now:
            target += timedelta(days=1)
        diff = (target - now).total_seconds()

        self.energy_status_label.config(
            text=f"{self.shutdown_action_var.get().title()} in {int(diff // 3600)}h {int((diff % 3600) // 60)}m",
            fg=C["yellow"]
        )

        if diff <= 30:
            # Time to act
            self._release_wake_lock()
            action = self.shutdown_action_var.get()
            notify("SeekMateAI", f"System will {action} now...")

            # Stop all bots first
            for name, info in self.instances.items():
                if info.get("status") == "running":
                    ctrl = self._control_path(name)
                    if ctrl:
                        try:
                            with open(ctrl, "w") as f:
                                json.dump({"status": "stop"}, f)
                        except Exception:
                            pass

            if action == "sleep":
                # Hibernate/sleep
                try:
                    subprocess.run(["rundll32.exe", "powrprof.dll,SetSuspendState", "0,1,0"],
                                  creationflags=subprocess.CREATE_NO_WINDOW)
                except Exception:
                    pass
            elif action == "shutdown":
                try:
                    subprocess.run(["shutdown", "/s", "/t", "60", "/c",
                                   "SeekMateAI scheduled shutdown"],
                                  creationflags=subprocess.CREATE_NO_WINDOW)
                except Exception:
                    pass
            self.shutdown_enabled_var.set(False)
            self.shutdown_toggle_btn.config(text="Enable", bg=C["text_muted"])
            return

        self._shutdown_timer_id = self.root.after(30000, self._check_shutdown_timer)

    def _energy_auto_manage(self):
        """Called from refresh_list — auto-manage wake lock based on bot status."""
        running = any(i.get("status") == "running" for i in self.instances.values())
        if running:
            self._set_wake_lock()
        else:
            if not self.shutdown_enabled_var.get():
                self._release_wake_lock()

    def _start_whatsapp_scheduler(self):
        try:
            if hasattr(self, '_wa_thread') and self._wa_thread.is_alive():
                return
            import whatsapp_scheduler
            self._wa_thread = threading.Thread(target=whatsapp_scheduler.scheduler_loop, daemon=True)
            self._wa_thread.start()
        except Exception:
            pass

    # ── System Tray ───────────────────────────────────────────
    def _setup_tray(self):
        if not _tray_available:
            return
        try:
            def show(icon, item):
                self.root.after(0, self._show_from_tray)

            def start_all_tray(icon, item):
                self.root.after(0, lambda: self.start_all())

            def stop_all_tray(icon, item):
                self.root.after(0, lambda: self.stop_all())

            def quit_app(icon, item):
                try:
                    icon.stop()
                except Exception:
                    pass
                self.root.after(0, self.root.destroy)

            menu = pystray.Menu(
                pystray.MenuItem("Show Dashboard", show, default=True),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("Start All Bots", start_all_tray),
                pystray.MenuItem("Stop All Bots", stop_all_tray),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("Quit", quit_app),
            )

            self.tray_icon = pystray.Icon("SeekMateAI", _create_tray_icon_image(),
                                           "SeekMateAI Dashboard", menu)

            def _run_tray():
                import ctypes
                try:
                    # Suppress WNDPROC errors on some Windows builds
                    ctypes.windll.ole32.CoInitialize(None)
                except Exception:
                    pass
                try:
                    self.tray_icon.run()
                except Exception:
                    pass

            threading.Thread(target=_run_tray, daemon=True).start()
        except Exception as e:
            print(f"[Tray] Failed: {e}")

    def _show_from_tray(self):
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()

    def _minimize_to_tray(self):
        if _tray_available and hasattr(self, 'tray_icon'):
            self.root.withdraw()
        else:
            self.root.iconify()


# ══════════════════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════════════════
if __name__ == "__main__":
    root = tk.Tk()
    app = MultiBotGUI(root)

    def on_closing():
        app.auto_refresh_running = False
        app.log_preview_running = False
        if _tray_available and hasattr(app, 'tray_icon'):
            try:
                app.tray_icon.stop()
            except Exception:
                pass
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_closing)
    root.mainloop()
