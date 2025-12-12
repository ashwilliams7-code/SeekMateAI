import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import threading
import json
import os
import subprocess
import sys
import time
import webbrowser
import re
import urllib.request
import urllib.error
import tempfile
import shutil

try:
    import openpyxl
    OPENPYXL_AVAILABLE = True
except ImportError:
    OPENPYXL_AVAILABLE = False

try:
    from plyer import notification
    NOTIFICATIONS_AVAILABLE = True
except ImportError:
    NOTIFICATIONS_AVAILABLE = False

# ================================
# APP VERSION
# ================================
APP_VERSION = "2.2.0"
GITHUB_REPO = "ashwilliams7-code/SeekMateAI"
GITHUB_API_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"

# ================================
# PREMIUM COLOR PALETTES
# ================================
COLORS_DARK = {
    # Backgrounds - Deep charcoal with subtle warmth
    "bg_dark": "#0d0d12",
    "bg_card": "#16161d",
    "bg_card_hover": "#1e1e28",
    "bg_input": "#1a1a24",
    "bg_elevated": "#202030",
    
    # Premium accents - Elegant teal & gold
    "accent_primary": "#4fd1c5",      # Sophisticated teal
    "accent_secondary": "#f6ad55",     # Warm gold
    "accent_gradient_start": "#4fd1c5",
    "accent_gradient_end": "#38b2ac",
    "accent_gold": "#d69e2e",          # Premium gold
    "accent_purple": "#9f7aea",        # Soft purple
    
    # Status colors
    "success": "#48bb78",
    "warning": "#ed8936",
    "danger": "#fc8181",
    
    # Text hierarchy
    "text_primary": "#f7fafc",
    "text_secondary": "#a0aec0",
    "text_muted": "#718096",
    
    # Borders & tracks
    "border": "#2d3748",
    "border_light": "#4a5568",
    "money_green": "#68d391",
    "slider_track": "#2d3748",
    "slider_fill": "#4fd1c5",
    "gpt_highlight": "#f687b3",
    
    # Tab colors
    "tab_active": "#4fd1c5",
    "tab_inactive": "#2d3748",
    "tab_hover": "#38b2ac",
}

COLORS_LIGHT = {
    "bg_dark": "#f7fafc",
    "bg_card": "#ffffff",
    "bg_card_hover": "#edf2f7",
    "bg_input": "#e2e8f0",
    "bg_elevated": "#ffffff",
    "accent_primary": "#319795",
    "accent_secondary": "#dd6b20",
    "accent_gradient_start": "#319795",
    "accent_gradient_end": "#2c7a7b",
    "accent_gold": "#d69e2e",
    "accent_purple": "#805ad5",
    "success": "#38a169",
    "warning": "#dd6b20",
    "danger": "#e53e3e",
    "text_primary": "#1a202c",
    "text_secondary": "#4a5568",
    "text_muted": "#718096",
    "border": "#e2e8f0",
    "border_light": "#cbd5e0",
    "money_green": "#38a169",
    "slider_track": "#cbd5e0",
    "slider_fill": "#319795",
    "gpt_highlight": "#d53f8c",
    "tab_active": "#319795",
    "tab_inactive": "#e2e8f0",
    "tab_hover": "#2c7a7b",
}

# Default to dark theme
COLORS = COLORS_DARK.copy()

# ================================
# PREMIUM FONTS
# ================================
FONT_FAMILY = "Segoe UI"  # Fallback: "Inter", "SF Pro Display"
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
FONT_TAB = (FONT_FAMILY, 11, "bold")
FONT_CHIP = (FONT_FAMILY, 9, "bold")

try:
    from PIL import Image, ImageTk, ImageDraw, ImageFilter
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False


# ================================
# RESOURCE PATH FIX (WORKS IN EXE)
# ================================
def resource_path(relative_path):
    """ Get absolute path for PyInstaller """
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)


def get_data_dir():
    """Get a consistent, user-writable data directory for logs and data files"""
    if sys.platform == "darwin":  # macOS
        data_dir = os.path.expanduser("~/Library/Application Support/SeekMateAI")
    elif sys.platform == "win32":  # Windows
        data_dir = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "SeekMateAI")
    else:  # Linux
        data_dir = os.path.expanduser("~/.seekmateai")
    
    os.makedirs(data_dir, exist_ok=True)
    return data_dir


LOG_FILE = os.path.join(get_data_dir(), "log.txt")


# Check for config file from command line argument (for multi-bot instances)
if len(sys.argv) > 1:
    CONFIG_FILE = sys.argv[1]
    # Derive control file from config file name
    config_dir = os.path.dirname(os.path.abspath(CONFIG_FILE))
    script_dir = os.path.dirname(os.path.abspath(__file__))
    config_name = os.path.basename(CONFIG_FILE).replace("_config.json", "").replace("config.json", "")
    if config_name:
        CONTROL_FILE = os.path.join(script_dir, f"control_{config_name}.json")
    else:
        CONTROL_FILE = os.path.join(script_dir, "control.json")
    print(f"[INSTANCE] Using config file: {CONFIG_FILE}")
    print(f"[INSTANCE] Using control file: {CONTROL_FILE}")
else:
    CONFIG_FILE = resource_path("config.json")
    CONTROL_FILE = resource_path("control.json")


# ============================================
# CONFIG MANAGEMENT
# ============================================
def load_config():
    if not os.path.exists(CONFIG_FILE):
        return {}
    with open(CONFIG_FILE, "r") as f:
        return json.load(f)


def save_config(data):
    with open(CONFIG_FILE, "w") as f:
        json.dump(data, f, indent=4)


def write_control(pause=None, stop=None, recommended=None):
    data = {"pause": False, "stop": False, "recommended": False}
    if os.path.exists(CONTROL_FILE):
        try:
            with open(CONTROL_FILE, "r") as f:
                existing = json.load(f)
                data.update(existing)
        except:
            pass

    if pause is not None:
        data["pause"] = pause
    if stop is not None:
        data["stop"] = stop
    if recommended is not None:
        data["recommended"] = recommended

    with open(CONTROL_FILE, "w") as f:
        json.dump(data, f)


# ============================================
# CHROME DETECTION
# ============================================
def is_chrome_installed():
    """Check if Google Chrome is installed on the system"""
    if sys.platform == "win32":
        # Windows - check common Chrome paths
        chrome_paths = [
            os.path.join(os.environ.get("PROGRAMFILES", ""), "Google", "Chrome", "Application", "chrome.exe"),
            os.path.join(os.environ.get("PROGRAMFILES(X86)", ""), "Google", "Chrome", "Application", "chrome.exe"),
            os.path.join(os.environ.get("LOCALAPPDATA", ""), "Google", "Chrome", "Application", "chrome.exe"),
        ]
        return any(os.path.exists(path) for path in chrome_paths if path)
    elif sys.platform == "darwin":
        # macOS - check Applications folder
        return os.path.exists("/Applications/Google Chrome.app")
    else:
        # Linux - check if chrome command exists
        import shutil
        return shutil.which("google-chrome") is not None or shutil.which("chromium-browser") is not None


def get_chrome_download_url():
    """Get the appropriate Chrome download URL for the current platform"""
    if sys.platform == "darwin":
        return "https://www.google.com/chrome/"
    elif sys.platform == "win32":
        return "https://www.google.com/chrome/"
    else:
        return "https://www.google.com/chrome/"


# ============================================
# AUTO-UPDATE SYSTEM
# ============================================
def get_platform_info():
    """Get current platform info for update matching"""
    if sys.platform == "win32":
        return {"os": "windows", "extensions": [".exe"], "keywords": ["windows"]}
    elif sys.platform == "darwin":
        return {"os": "macos", "extensions": [".zip"], "keywords": ["macos", "mac"]}
    else:
        return {"os": "linux", "extensions": [""], "keywords": ["linux"]}

def check_for_updates():
    """Check GitHub for latest release version"""
    try:
        request = urllib.request.Request(
            GITHUB_API_URL,
            headers={"Accept": "application/vnd.github.v3+json", "User-Agent": "SeekMateAI"}
        )
        with urllib.request.urlopen(request, timeout=10) as response:
            data = json.loads(response.read().decode())
            latest_version = data.get("tag_name", "").lstrip("v")
            download_url = None
            release_notes = data.get("body", "")
            
            # Get platform-specific download URL
            platform_info = get_platform_info()
            
            for asset in data.get("assets", []):
                asset_name = asset["name"].lower()
                # Check for platform keywords
                for keyword in platform_info["keywords"]:
                    if keyword in asset_name:
                        download_url = asset["browser_download_url"]
                        break
                # Also check file extension as fallback
                if not download_url:
                    for ext in platform_info["extensions"]:
                        if ext and asset_name.endswith(ext):
                            download_url = asset["browser_download_url"]
                            break
                if download_url:
                    break
            
            return {
                "latest_version": latest_version,
                "current_version": APP_VERSION,
                "update_available": compare_versions(latest_version, APP_VERSION) > 0,
                "download_url": download_url,
                "release_notes": release_notes,
                "platform": platform_info["os"]
            }
    except Exception as e:
        print(f"Update check failed: {e}")
        return None

def compare_versions(v1, v2):
    """Compare two version strings. Returns 1 if v1 > v2, -1 if v1 < v2, 0 if equal"""
    try:
        v1_parts = [int(x) for x in v1.split(".")]
        v2_parts = [int(x) for x in v2.split(".")]
        
        for i in range(max(len(v1_parts), len(v2_parts))):
            v1_val = v1_parts[i] if i < len(v1_parts) else 0
            v2_val = v2_parts[i] if i < len(v2_parts) else 0
            if v1_val > v2_val:
                return 1
            elif v1_val < v2_val:
                return -1
        return 0
    except:
        return 0

def download_update(url, progress_callback=None):
    """Download update file and return path to downloaded file"""
    try:
        # Create temp file with platform-appropriate name
        temp_dir = tempfile.gettempdir()
        
        if sys.platform == "win32":
            temp_file = os.path.join(temp_dir, "SeekMate_AI_update.exe")
        elif sys.platform == "darwin":
            temp_file = os.path.join(temp_dir, "SeekMate_AI_update.zip")
        else:
            temp_file = os.path.join(temp_dir, "SeekMate_AI_update")
        
        request = urllib.request.Request(url, headers={"User-Agent": "SeekMateAI"})
        
        with urllib.request.urlopen(request, timeout=120) as response:  # 2 min timeout for larger files
            total_size = int(response.headers.get('content-length', 0))
            downloaded = 0
            chunk_size = 8192
            
            with open(temp_file, 'wb') as f:
                while True:
                    chunk = response.read(chunk_size)
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)
                    if progress_callback and total_size:
                        progress_callback(downloaded / total_size * 100)
        
        return temp_file
    except Exception as e:
        print(f"Download failed: {e}")
        return None


# ============================================
# CUSTOM WIDGETS
# ============================================
class ModernEntry(tk.Frame):
    """Custom styled entry with rounded appearance"""
    def __init__(self, parent, placeholder="", show="", **kwargs):
        super().__init__(parent, bg=COLORS["bg_card"])
        
        self.entry = tk.Entry(
            self,
            font=FONT_NORMAL,
            bg=COLORS["bg_input"],
            fg=COLORS["text_primary"],
            insertbackground=COLORS["accent_primary"],
            relief="flat",
            highlightthickness=2,
            highlightbackground=COLORS["border"],
            highlightcolor=COLORS["accent_primary"],
            show=show
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
    """Custom styled button with gradient and hover effects"""
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
        
        # Style configurations
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
        bg_color = style["hover"] if self.is_hovered and not self.is_disabled else style["bg"]
        
        # Draw rounded rectangle
        radius = 8
        self.create_rounded_rect(2, 2, self.width-2, self.height-2, radius, bg_color)
        
        # Draw text
        self.create_text(
            self.width // 2, self.height // 2,
            text=self.text,
            font=FONT_BUTTON,
            fill=style["fg"]
        )
        
    def create_rounded_rect(self, x1, y1, x2, y2, radius, fill):
        self.create_arc(x1, y1, x1 + 2*radius, y1 + 2*radius, start=90, extent=90, fill=fill, outline=fill)
        self.create_arc(x2 - 2*radius, y1, x2, y1 + 2*radius, start=0, extent=90, fill=fill, outline=fill)
        self.create_arc(x1, y2 - 2*radius, x1 + 2*radius, y2, start=180, extent=90, fill=fill, outline=fill)
        self.create_arc(x2 - 2*radius, y2 - 2*radius, x2, y2, start=270, extent=90, fill=fill, outline=fill)
        self.create_rectangle(x1 + radius, y1, x2 - radius, y2, fill=fill, outline=fill)
        self.create_rectangle(x1, y1 + radius, x2, y2 - radius, fill=fill, outline=fill)
        
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
    """Animated status indicator"""
    def __init__(self, parent, size=12, **kwargs):
        super().__init__(parent, width=size+4, height=size+4, 
                        bg=COLORS["bg_dark"], highlightthickness=0, **kwargs)
        self.size = size
        self.color = COLORS["text_muted"]
        self.pulse_alpha = 1.0
        self.pulse_direction = -0.05
        self.is_pulsing = False
        self.draw()
        
    def draw(self):
        self.delete("all")
        cx, cy = (self.size + 4) // 2, (self.size + 4) // 2
        # Outer glow when pulsing
        if self.is_pulsing:
            glow_size = self.size // 2 + 3
            self.create_oval(cx - glow_size, cy - glow_size, 
                           cx + glow_size, cy + glow_size,
                           fill="", outline=self.color, width=2)
        # Main circle
        r = self.size // 2
        self.create_oval(cx - r, cy - r, cx + r, cy + r, fill=self.color, outline="")
        
    def set_status(self, status):
        status_colors = {
            "idle": COLORS["text_muted"],
            "running": COLORS["success"],
            "paused": COLORS["warning"],
            "stopped": COLORS["danger"],
        }
        self.color = status_colors.get(status, COLORS["text_muted"])
        self.is_pulsing = status == "running"
        self.draw()
        if self.is_pulsing:
            self.pulse()
            
    def pulse(self):
        if self.is_pulsing:
            self.draw()
            self.after(100, self.pulse)


class ModernSlider(tk.Frame):
    """Custom styled slider with value display"""
    def __init__(self, parent, label="", min_val=0, max_val=100, default=50, 
                 unit="", description="", on_change=None, **kwargs):
        super().__init__(parent, bg=COLORS["bg_card"], **kwargs)
        
        self.min_val = min_val
        self.max_val = max_val
        self.unit = unit
        self.on_change = on_change
        
        # Header row with label and value
        header = tk.Frame(self, bg=COLORS["bg_card"])
        header.pack(fill="x", pady=(0, 8))
        
        tk.Label(header, text=label, bg=COLORS["bg_card"], 
                fg=COLORS["text_primary"], font=FONT_BOLD).pack(side="left")
        
        self.value_label = tk.Label(header, text=f"{default}{unit}", 
                                   bg=COLORS["bg_card"], fg=COLORS["accent_primary"],
                                   font=FONT_BOLD)
        self.value_label.pack(side="right")
        
        # Description
        if description:
            tk.Label(self, text=description, bg=COLORS["bg_card"], 
                    fg=COLORS["text_muted"], font=FONT_LABEL,
                    wraplength=350, justify="left").pack(fill="x", pady=(0, 8))
        
        # Slider track container
        self.track_frame = tk.Frame(self, bg=COLORS["bg_card"], height=40)
        self.track_frame.pack(fill="x")
        self.track_frame.pack_propagate(False)
        
        # Canvas for custom slider
        self.canvas = tk.Canvas(self.track_frame, bg=COLORS["bg_card"], 
                               highlightthickness=0, height=40)
        self.canvas.pack(fill="x", expand=True)
        
        self.value = default
        self.dragging = False
        
        # Bind events
        self.canvas.bind("<Configure>", self.on_configure)
        self.canvas.bind("<Button-1>", self.on_click)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        
        # Speed labels
        labels_frame = tk.Frame(self, bg=COLORS["bg_card"])
        labels_frame.pack(fill="x", pady=(4, 0))
        tk.Label(labels_frame, text="Slower", bg=COLORS["bg_card"], 
                fg=COLORS["text_muted"], font=("Segoe UI", 9)).pack(side="left")
        tk.Label(labels_frame, text="Faster", bg=COLORS["bg_card"], 
                fg=COLORS["text_muted"], font=("Segoe UI", 9)).pack(side="right")
        
    def on_configure(self, event):
        self.draw_slider()
        
    def draw_slider(self):
        self.canvas.delete("all")
        
        w = self.canvas.winfo_width()
        h = self.canvas.winfo_height()
        
        if w < 10:
            return
            
        padding = 15
        track_y = h // 2
        track_height = 8
        
        # Draw track background
        self.canvas.create_rounded_rect = lambda x1, y1, x2, y2, r, **kw: self._rounded_rect(x1, y1, x2, y2, r, **kw)
        
        # Track background
        self.canvas.create_rectangle(padding, track_y - track_height//2, 
                                    w - padding, track_y + track_height//2,
                                    fill=COLORS["slider_track"], outline="")
        
        # Calculate thumb position
        ratio = (self.value - self.min_val) / (self.max_val - self.min_val)
        thumb_x = padding + ratio * (w - 2 * padding)
        
        # Draw filled portion
        self.canvas.create_rectangle(padding, track_y - track_height//2,
                                    thumb_x, track_y + track_height//2,
                                    fill=COLORS["accent_primary"], outline="")
        
        # Draw thumb
        thumb_radius = 10
        self.canvas.create_oval(thumb_x - thumb_radius, track_y - thumb_radius,
                               thumb_x + thumb_radius, track_y + thumb_radius,
                               fill=COLORS["accent_primary"], outline=COLORS["text_primary"], width=2)
        
        # Glow effect on thumb
        self.canvas.create_oval(thumb_x - thumb_radius - 3, track_y - thumb_radius - 3,
                               thumb_x + thumb_radius + 3, track_y + thumb_radius + 3,
                               fill="", outline=COLORS["accent_primary"], width=1)
        
    def _rounded_rect(self, x1, y1, x2, y2, radius, **kwargs):
        points = [
            x1 + radius, y1, x2 - radius, y1,
            x2, y1, x2, y1 + radius,
            x2, y2 - radius, x2, y2,
            x2 - radius, y2, x1 + radius, y2,
            x1, y2, x1, y2 - radius,
            x1, y1 + radius, x1, y1
        ]
        return self.canvas.create_polygon(points, smooth=True, **kwargs)
        
    def on_click(self, event):
        self.update_value_from_x(event.x)
        
    def on_drag(self, event):
        self.dragging = True
        self.update_value_from_x(event.x)
        
    def on_release(self, event):
        self.dragging = False
        
    def update_value_from_x(self, x):
        w = self.canvas.winfo_width()
        padding = 15
        
        # Calculate value from x position
        ratio = (x - padding) / (w - 2 * padding)
        ratio = max(0, min(1, ratio))
        
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


# ============================================
# COLLAPSIBLE CARD WIDGET
# ============================================
class CollapsibleCard(tk.Frame):
    """A card that can be collapsed/expanded"""
    def __init__(self, parent, title="", icon="⚙️", default_expanded=True, **kwargs):
        super().__init__(parent, bg=COLORS["bg_card"], **kwargs)
        
        self.is_expanded = default_expanded
        self.title = title
        self.icon = icon
        
        # Header (always visible)
        self.header = tk.Frame(self, bg=COLORS["bg_card"], cursor="hand2")
        self.header.pack(fill="x", padx=20, pady=(15, 0))
        
        # Toggle button
        self.toggle_btn = tk.Label(self.header, text="▼" if self.is_expanded else "▶",
                                   bg=COLORS["bg_card"], fg=COLORS["text_muted"],
                                   font=("Segoe UI", 10), cursor="hand2")
        self.toggle_btn.pack(side="left", padx=(0, 8))
        
        # Title
        tk.Label(self.header, text=f"{icon}  {title}", 
                bg=COLORS["bg_card"], fg=COLORS["text_primary"],
                font=FONT_TITLE).pack(side="left")
        
        # Content frame (collapsible)
        self.content = tk.Frame(self, bg=COLORS["bg_card"])
        if self.is_expanded:
            self.content.pack(fill="x", padx=20, pady=(15, 20))
        
        # Bind click events
        self.header.bind("<Button-1>", self.toggle)
        self.toggle_btn.bind("<Button-1>", self.toggle)
        for child in self.header.winfo_children():
            child.bind("<Button-1>", self.toggle)
            
        # Hover effect
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


# ============================================
# PREMIUM TAB BAR WIDGET
# ============================================
class PremiumTabBar(tk.Frame):
    """A premium horizontal tab bar for navigation"""
    def __init__(self, parent, tabs, on_change=None, **kwargs):
        super().__init__(parent, bg=COLORS["bg_dark"], **kwargs)
        
        self.tabs = tabs  # List of (name, icon) tuples
        self.active_tab = 0
        self.on_change = on_change
        self.tab_buttons = []
        
        # Container with subtle background
        self.container = tk.Frame(self, bg=COLORS["bg_card"], pady=4)
        self.container.pack(fill="x", padx=0, pady=(0, 15))
        
        # Inner frame for tabs
        inner = tk.Frame(self.container, bg=COLORS["bg_card"])
        inner.pack(fill="x", padx=15, pady=8)
        
        for i, (name, icon) in enumerate(tabs):
            btn = self._create_tab_button(inner, name, icon, i)
            btn.pack(side="left", padx=(0, 8))
            self.tab_buttons.append(btn)
        
        # Initial state
        self._update_tabs()
    
    def _create_tab_button(self, parent, name, icon, index):
        """Create a styled tab button"""
        btn = tk.Frame(parent, bg=COLORS["tab_inactive"], cursor="hand2")
        
        inner = tk.Frame(btn, bg=COLORS["tab_inactive"])
        inner.pack(padx=16, pady=10)
        
        label = tk.Label(inner, text=f"{icon}  {name}",
                        bg=COLORS["tab_inactive"], fg=COLORS["text_secondary"],
                        font=FONT_TAB)
        label.pack()
        
        # Store references
        btn.inner = inner
        btn.label = label
        btn.index = index
        
        # Bind events
        for widget in [btn, inner, label]:
            widget.bind("<Button-1>", lambda e, idx=index: self._on_tab_click(idx))
            widget.bind("<Enter>", lambda e, b=btn: self._on_hover(b, True))
            widget.bind("<Leave>", lambda e, b=btn: self._on_hover(b, False))
        
        return btn
    
    def _on_tab_click(self, index):
        if index != self.active_tab:
            self.active_tab = index
            self._update_tabs()
            if self.on_change:
                self.on_change(index)
    
    def _on_hover(self, btn, entering):
        if btn.index == self.active_tab:
            return
        if entering:
            bg = COLORS["bg_card_hover"]
        else:
            bg = COLORS["tab_inactive"]
        btn.config(bg=bg)
        btn.inner.config(bg=bg)
        btn.label.config(bg=bg)
    
    def _update_tabs(self):
        for i, btn in enumerate(self.tab_buttons):
            if i == self.active_tab:
                bg = COLORS["tab_active"]
                fg = COLORS["bg_dark"]
            else:
                bg = COLORS["tab_inactive"]
                fg = COLORS["text_secondary"]
            
            btn.config(bg=bg)
            btn.inner.config(bg=bg)
            btn.label.config(bg=bg, fg=fg)
    
    def get_active_tab(self):
        return self.active_tab
    
    def set_active_tab(self, index):
        if 0 <= index < len(self.tabs):
            self.active_tab = index
            self._update_tabs()


# ============================================
# CONFIG PROGRESS BAR
# ============================================
class ConfigProgressBar(tk.Frame):
    """Shows configuration completeness"""
    def __init__(self, parent, **kwargs):
        super().__init__(parent, bg=COLORS["bg_card"], **kwargs)
        
        # Header
        header = tk.Frame(self, bg=COLORS["bg_card"])
        header.pack(fill="x", padx=20, pady=(15, 10))
        
        tk.Label(header, text="📊  Configuration Status", 
                bg=COLORS["bg_card"], fg=COLORS["text_primary"],
                font=FONT_BOLD).pack(side="left")
        
        self.percent_label = tk.Label(header, text="0%", 
                                      bg=COLORS["bg_card"], fg=COLORS["accent_primary"],
                                      font=FONT_BOLD)
        self.percent_label.pack(side="right")
        
        # Progress bar container
        bar_frame = tk.Frame(self, bg=COLORS["bg_card"])
        bar_frame.pack(fill="x", padx=20, pady=(0, 10))
        
        # Background track
        self.track = tk.Frame(bar_frame, bg=COLORS["slider_track"], height=8)
        self.track.pack(fill="x")
        
        # Fill bar
        self.fill = tk.Frame(self.track, bg=COLORS["accent_primary"], height=8)
        self.fill.place(relwidth=0, relheight=1)
        
        # Status message
        self.status_label = tk.Label(self, text="Complete all fields for best results",
                                     bg=COLORS["bg_card"], fg=COLORS["text_muted"],
                                     font=FONT_LABEL)
        self.status_label.pack(padx=20, pady=(0, 15), anchor="w")
        
    def update_progress(self, fields_status):
        """Update progress based on field completion status
        fields_status: dict of {field_name: is_complete}
        """
        total = len(fields_status)
        completed = sum(1 for v in fields_status.values() if v)
        percent = int((completed / total) * 100) if total > 0 else 0
        
        # Update label
        self.percent_label.config(text=f"{percent}%")
        
        # Update fill width
        self.fill.place(relwidth=percent/100, relheight=1)
        
        # Update color based on progress
        if percent >= 100:
            color = COLORS["success"]
            status = "✅ All fields complete! You're ready to go."
        elif percent >= 75:
            color = COLORS["accent_primary"]
            status = "Almost there! Fill in the remaining fields."
        elif percent >= 50:
            color = COLORS["warning"]
            status = "Good progress. Keep filling in your details."
        else:
            color = COLORS["danger"]
            status = "Fill in required fields to get started."
            
        self.fill.config(bg=color)
        self.percent_label.config(fg=color)
        self.status_label.config(text=status)


# ============================================
# SECTION DIVIDER
# ============================================
class SectionDivider(tk.Frame):
    """Visual divider with optional label"""
    def __init__(self, parent, label="", **kwargs):
        super().__init__(parent, bg=COLORS["bg_card"], **kwargs)
        
        if label:
            # Divider with label
            left_line = tk.Frame(self, bg=COLORS["border"], height=1)
            left_line.pack(side="left", fill="x", expand=True, pady=15)
            
            tk.Label(self, text=label, bg=COLORS["bg_card"], 
                    fg=COLORS["text_muted"], font=("Segoe UI", 9)).pack(side="left", padx=10)
            
            right_line = tk.Frame(self, bg=COLORS["border"], height=1)
            right_line.pack(side="left", fill="x", expand=True, pady=15)
        else:
            # Simple line divider
            line = tk.Frame(self, bg=COLORS["border"], height=1)
            line.pack(fill="x", pady=15)


# ============================================
# LIVE CONFIG SUMMARY
# ============================================
class ConfigSummary(tk.Frame):
    """Shows a mini summary of current config"""
    def __init__(self, parent, **kwargs):
        super().__init__(parent, bg=COLORS["bg_card"], **kwargs)
        
        # Header
        header = tk.Frame(self, bg=COLORS["bg_card"])
        header.pack(fill="x", padx=20, pady=(15, 10))
        
        tk.Label(header, text="📋  Quick Summary", 
                bg=COLORS["bg_card"], fg=COLORS["text_primary"],
                font=FONT_BOLD).pack(side="left")
        
        # Summary grid
        self.summary_frame = tk.Frame(self, bg=COLORS["bg_card"])
        self.summary_frame.pack(fill="x", padx=20, pady=(0, 15))
        
        # Create summary items (will be updated)
        self.items = {}
        
    def add_item(self, key, icon, label):
        """Add a summary item"""
        item_frame = tk.Frame(self.summary_frame, bg=COLORS["bg_card"])
        item_frame.pack(fill="x", pady=2)
        
        tk.Label(item_frame, text=icon, bg=COLORS["bg_card"], 
                fg=COLORS["text_muted"], font=FONT_LABEL, width=3).pack(side="left")
        
        tk.Label(item_frame, text=label + ":", bg=COLORS["bg_card"], 
                fg=COLORS["text_secondary"], font=FONT_LABEL, width=12, anchor="w").pack(side="left")
        
        value_label = tk.Label(item_frame, text="—", bg=COLORS["bg_card"], 
                              fg=COLORS["text_primary"], font=FONT_LABEL, anchor="w")
        value_label.pack(side="left", fill="x", expand=True)
        
        self.items[key] = value_label
        
    def update_item(self, key, value, color=None):
        """Update a summary item's value"""
        if key in self.items:
            self.items[key].config(text=value)
            if color:
                self.items[key].config(fg=color)
            else:
                self.items[key].config(fg=COLORS["text_primary"])


# ============================================
# GUI CLASS
# ============================================
class SeekMateGUI:
    def __init__(self, root):
        self.root = root
        self.root.title(f"SeekMate AI v{APP_VERSION} — Professional Edition")
        self.root.geometry("1400x900")
        self.root.configure(bg=COLORS["bg_dark"])
        self.root.minsize(1200, 700)

        # DATA
        self.config = load_config()
        self.bot_process = None
        self.paused = False
        self.start_time = None
        self.timer_running = False
        self.money_running = False
        self.money_saved = 0.0

        # Configure style for ttk widgets
        self.style = ttk.Style()
        self.style.theme_use('clam')
        self.configure_ttk_styles()

        # Build UI
        self.build_header()
        self.build_controls_bar()
        self.build_main_content()
        
        # Check for updates after UI is built (non-blocking)
        self.root.after(2000, self.check_for_updates_async)

    def configure_ttk_styles(self):
        """Configure ttk styles for modern look"""
        self.style.configure("Modern.TCombobox",
            fieldbackground=COLORS["bg_input"],
            background=COLORS["bg_input"],
            foreground=COLORS["text_primary"],
            arrowcolor=COLORS["accent_primary"],
            borderwidth=0,
            relief="flat"
        )
        self.style.map("Modern.TCombobox",
            fieldbackground=[("readonly", COLORS["bg_input"])],
            background=[("readonly", COLORS["bg_input"])],
            foreground=[("readonly", COLORS["text_primary"])]
        )
        self.style.configure("Modern.Vertical.TScrollbar",
            background=COLORS["bg_card"],
            troughcolor=COLORS["bg_dark"],
            borderwidth=0,
            arrowsize=0
        )

    def build_header(self):
        """Build the top header bar"""
        header = tk.Frame(self.root, bg=COLORS["bg_dark"], height=70)
        header.pack(fill="x", padx=20, pady=(15, 0))
        header.pack_propagate(False)

        # Left side - Logo and title
        left_header = tk.Frame(header, bg=COLORS["bg_dark"])
        left_header.pack(side="left", fill="y")

        # Logo icon placeholder (cyan circle with S)
        logo_canvas = tk.Canvas(left_header, width=45, height=45, 
                               bg=COLORS["bg_dark"], highlightthickness=0)
        logo_canvas.pack(side="left", padx=(0, 12))
        logo_canvas.create_oval(2, 2, 43, 43, fill=COLORS["accent_primary"], outline="")
        logo_canvas.create_text(22, 23, text="S", font=("Segoe UI", 20, "bold"), fill="#000000")

        title_frame = tk.Frame(left_header, bg=COLORS["bg_dark"])
        title_frame.pack(side="left", fill="y")
        
        tk.Label(title_frame, text="SEEKMATE AI", 
                bg=COLORS["bg_dark"], fg=COLORS["text_primary"],
                font=FONT_HEADER).pack(anchor="w")
        tk.Label(title_frame, text="Professional Edition • by Ash", 
                bg=COLORS["bg_dark"], fg=COLORS["text_secondary"],
                font=FONT_LABEL).pack(anchor="w")

        # Right side - Status indicators
        right_header = tk.Frame(header, bg=COLORS["bg_dark"])
        right_header.pack(side="right", fill="y")

        # Status indicator
        status_frame = tk.Frame(right_header, bg=COLORS["bg_dark"])
        status_frame.pack(side="right", padx=(20, 0))
        
        self.status_indicator = PulsingIndicator(status_frame)
        self.status_indicator.pack(side="left", padx=(0, 8))
        
        self.header_status = tk.Label(status_frame, text="IDLE",
            bg=COLORS["bg_dark"], fg=COLORS["text_muted"],
            font=FONT_BOLD)
        self.header_status.pack(side="left")

        # Timer
        timer_frame = tk.Frame(right_header, bg=COLORS["bg_dark"])
        timer_frame.pack(side="right", padx=20)
        tk.Label(timer_frame, text="⏱", bg=COLORS["bg_dark"], 
                fg=COLORS["text_secondary"], font=("Segoe UI", 14)).pack(side="left")
        self.header_timer = tk.Label(timer_frame, text="00:00:00",
            bg=COLORS["bg_dark"], fg=COLORS["text_primary"],
            font=FONT_BOLD)
        self.header_timer.pack(side="left", padx=(5, 0))

        # Speed indicator
        speed_frame = tk.Frame(right_header, bg=COLORS["bg_dark"])
        speed_frame.pack(side="right", padx=20)
        tk.Label(speed_frame, text="⚡", bg=COLORS["bg_dark"], 
                fg=COLORS["accent_primary"], font=("Segoe UI", 14)).pack(side="left")
        self.header_speed = tk.Label(speed_frame, 
            text=self.config.get('SPEED', 'normal').upper(),
            bg=COLORS["bg_dark"], fg=COLORS["accent_primary"],
            font=FONT_BOLD)
        self.header_speed.pack(side="left", padx=(5, 0))

        # Theme toggle button
        theme_frame = tk.Frame(right_header, bg=COLORS["bg_dark"])
        theme_frame.pack(side="right", padx=10)
        
        self.current_theme = self.config.get("THEME", "dark")
        theme_icon = "🌙" if self.current_theme == "dark" else "☀️"
        
        self.theme_btn = tk.Button(theme_frame, text=theme_icon,
            bg=COLORS["bg_dark"], fg=COLORS["accent_primary"],
            font=("Segoe UI", 16), relief="flat", cursor="hand2",
            activebackground=COLORS["bg_dark"], command=self.toggle_theme)
        self.theme_btn.pack()

        # Divider line
        divider = tk.Frame(self.root, bg=COLORS["border"], height=1)
        divider.pack(fill="x", padx=20, pady=(15, 0))

    def build_controls_bar(self):
        """Build the fixed controls bar under the header"""
        controls_bar = tk.Frame(self.root, bg=COLORS["bg_card"], height=60)
        controls_bar.pack(fill="x", padx=20, pady=(15, 0))
        controls_bar.pack_propagate(False)
        
        # Inner frame for buttons with padding
        inner = tk.Frame(controls_bar, bg=COLORS["bg_card"])
        inner.pack(fill="both", expand=True, padx=15, pady=10)
        
        # Left side - Main action buttons
        left_btns = tk.Frame(inner, bg=COLORS["bg_card"])
        left_btns.pack(side="left", fill="y")
        
        self.start_btn = ModernButton(left_btns, text="▶  START", 
                                      command=self.start_bot, style="success", width=110)
        self.start_btn.pack(side="left", padx=(0, 8))

        self.pause_btn = ModernButton(left_btns, text="⏸  PAUSE", 
                                      command=self.pause_bot, style="warning", width=110)
        self.pause_btn.pack(side="left", padx=(0, 8))

        self.stop_btn = ModernButton(left_btns, text="⏹  STOP", 
                                     command=self.stop_bot, style="danger", width=100)
        self.stop_btn.pack(side="left")
        
        # Spacer
        tk.Frame(left_btns, bg=COLORS["bg_card"], width=20).pack(side="left")
        
        # Recommended Jobs button - special action
        self.recommended_btn = ModernButton(left_btns, text="🎯 RECOMMENDED", 
                                           command=self.start_recommended, style="primary", width=150)
        self.recommended_btn.pack(side="left")
        
        # Right side - Secondary buttons
        right_btns = tk.Frame(inner, bg=COLORS["bg_card"])
        right_btns.pack(side="right", fill="y")
        
        self.check_update_btn = ModernButton(right_btns, text="🔄 UPDATE", 
                                            command=self.manual_update_check, style="dark", width=100)
        self.check_update_btn.pack(side="right", padx=(8, 0))
        
        self.test_btn = ModernButton(right_btns, text="🔍 TEST", 
                                     command=self.run_test, style="dark", width=90)
        self.test_btn.pack(side="right", padx=(8, 0))
        
        self.update_btn = ModernButton(right_btns, text="💾 SAVE", 
                                       command=self.update_settings, style="primary", width=90)
        self.update_btn.pack(side="right")

    def build_main_content(self):
        """Build the main content area with tabbed navigation"""
        main = tk.Frame(self.root, bg=COLORS["bg_dark"])
        main.pack(fill="both", expand=True, padx=20, pady=15)

        # Left panel - Tabbed Configuration (50% width)
        left = tk.Frame(main, bg=COLORS["bg_dark"])
        left.pack(side="left", fill="both", expand=True, padx=(0, 10))

        # Tab Bar
        tabs = [
            ("Profile", "👤"),
            ("Jobs", "💼"),
            ("Speed", "⚡"),
            ("API", "🔑"),
        ]
        self.tab_bar = PremiumTabBar(left, tabs, on_change=self.on_tab_change)
        self.tab_bar.pack(fill="x")

        # Tab content container
        self.tab_container = tk.Frame(left, bg=COLORS["bg_dark"])
        self.tab_container.pack(fill="both", expand=True)
        
        # Create scrollable frame for tab content
        self.tab_canvas = tk.Canvas(self.tab_container, bg=COLORS["bg_dark"], highlightthickness=0)
        self.tab_scrollbar = ttk.Scrollbar(self.tab_container, orient="vertical", command=self.tab_canvas.yview)
        self.tab_scroll_frame = tk.Frame(self.tab_canvas, bg=COLORS["bg_dark"])
        
        self.tab_scroll_frame.bind("<Configure>", 
            lambda e: self.tab_canvas.configure(scrollregion=self.tab_canvas.bbox("all")))
        
        # Dynamic width based on canvas
        def update_scroll_width(event):
            self.tab_canvas.itemconfig(self.scroll_window_id, width=event.width - 20)
        
        self.scroll_window_id = self.tab_canvas.create_window((0, 0), window=self.tab_scroll_frame, anchor="nw")
        self.tab_canvas.bind("<Configure>", update_scroll_width)
        self.tab_canvas.configure(yscrollcommand=self.tab_scrollbar.set)
        
        self.tab_canvas.pack(side="left", fill="both", expand=True)
        self.tab_scrollbar.pack(side="right", fill="y")
        
        # Mousewheel scrolling
        def _on_mousewheel(event):
            self.tab_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        self.tab_canvas.bind_all("<MouseWheel>", _on_mousewheel)

        # Build all tab frames (hidden initially except first)
        self.tab_frames = {}
        self._build_profile_tab()
        self._build_jobs_tab()
        self._build_speed_tab()
        self._build_api_tab()
        
        # Show first tab
        self.on_tab_change(0)
        
        # Initial update
        self.update_config_status()

        # Right panel - Dashboard and Logs (50% width)
        right = tk.Frame(main, bg=COLORS["bg_dark"])
        right.pack(side="right", fill="both", expand=True, padx=(10, 0))

        self.build_stats_panel(right)
        self.build_log_panel(right)
        self.build_history_panel(right)

    def on_tab_change(self, index):
        """Handle tab change"""
        # Hide all tab frames
        for widget in self.tab_scroll_frame.winfo_children():
            widget.pack_forget()
        
        # Show the selected tab
        tab_names = ["profile", "jobs", "speed", "api"]
        if index < len(tab_names) and tab_names[index] in self.tab_frames:
            self.tab_frames[tab_names[index]].pack(fill="both", expand=True)
        
        # Scroll to top
        self.tab_canvas.yview_moveto(0)

    def _build_profile_tab(self):
        """Build Profile tab content"""
        frame = tk.Frame(self.tab_scroll_frame, bg=COLORS["bg_dark"])
        self.tab_frames["profile"] = frame
        
        # Progress bar at top
        self.progress_bar = ConfigProgressBar(frame)
        self.progress_bar.pack(fill="x", pady=(0, 15))
        
        # Config summary
        self.config_summary = ConfigSummary(frame)
        self.config_summary.pack(fill="x", pady=(0, 15))
        self.config_summary.add_item("name", "👤", "Name")
        self.config_summary.add_item("location", "📍", "Location")
        self.config_summary.add_item("jobs", "💼", "Job Titles")
        self.config_summary.add_item("max", "🎯", "Max Jobs")
        self.config_summary.add_item("salary", "💰", "Salary")
        self.config_summary.add_item("speed", "⚡", "Speed")
        
        # Personal info card
        card = tk.Frame(frame, bg=COLORS["bg_card"])
        card.pack(fill="x", pady=(0, 15))
        
        inner = tk.Frame(card, bg=COLORS["bg_card"])
        inner.pack(fill="x", padx=25, pady=20)
        
        # Section header
        header = tk.Frame(inner, bg=COLORS["bg_card"])
        header.pack(fill="x", pady=(0, 20))
        tk.Label(header, text="👤  Personal Information", 
                bg=COLORS["bg_card"], fg=COLORS["text_primary"],
                font=FONT_SUBHEADER).pack(anchor="w")
        tk.Label(header, text="Your details for job applications",
                bg=COLORS["bg_card"], fg=COLORS["text_muted"],
                font=FONT_LABEL).pack(anchor="w", pady=(5, 0))
        
        # Full Name dropdown
        tk.Label(inner, text="FULL NAME", bg=COLORS["bg_card"], 
                fg=COLORS["text_muted"], font=FONT_LABEL_BOLD).pack(anchor="w", pady=(0, 8))
        self.full_name_var = tk.StringVar()
        preset_names = ["Ash Williams", "Jennifer Berrio", "Rafael Hurtado", "Custom..."]
        self.full_name_dropdown = ttk.Combobox(inner, textvariable=self.full_name_var,
                                               values=preset_names,
                                               style="Modern.TCombobox", font=FONT_NORMAL)
        saved_name = self.config.get("FULL_NAME", "Ash Williams")
        if saved_name and saved_name not in preset_names:
            self.full_name_dropdown['values'] = preset_names[:-1] + [saved_name, "Custom..."]
            self.full_name_dropdown.set(saved_name)
        elif saved_name:
            self.full_name_dropdown.set(saved_name)
        else:
            self.full_name_dropdown.set("Ash Williams")
        self.full_name_dropdown.pack(fill="x", pady=(0, 15))
        self.full_name_dropdown.bind("<<ComboboxSelected>>", self.on_name_selected)
        
        # Location dropdown
        tk.Label(inner, text="LOCATION", bg=COLORS["bg_card"], 
                fg=COLORS["text_muted"], font=FONT_LABEL_BOLD).pack(anchor="w", pady=(0, 8))
        self.location_var = tk.StringVar()
        locations = [
            "Brisbane, Australia", "Sydney, Australia", "Melbourne, Australia",
            "Perth, Australia", "Adelaide, Australia", "Canberra, Australia",
            "Gold Coast, Australia", "Newcastle, Australia", "Hobart, Australia",
            "Darwin, Australia"
        ]
        self.location_dropdown = ttk.Combobox(inner, textvariable=self.location_var,
                                              values=locations,
                                              style="Modern.TCombobox", font=FONT_NORMAL)
        self.location_dropdown.set(self.config.get("LOCATION", "Brisbane, Australia"))
        self.location_dropdown.pack(fill="x")
        
        # Platform selection card
        platform_card = tk.Frame(frame, bg=COLORS["bg_card"])
        platform_card.pack(fill="x", pady=(0, 15))
        
        platform_inner = tk.Frame(platform_card, bg=COLORS["bg_card"])
        platform_inner.pack(fill="x", padx=25, pady=20)
        
        tk.Label(platform_inner, text="🌐  Job Platforms", 
                bg=COLORS["bg_card"], fg=COLORS["text_primary"],
                font=FONT_SUBHEADER).pack(anchor="w", pady=(0, 15))
        
        platform_row = tk.Frame(platform_inner, bg=COLORS["bg_card"])
        platform_row.pack(fill="x")
        
        self.seek_var = tk.BooleanVar(value=self.config.get("USE_SEEK", True))
        self.indeed_var = tk.BooleanVar(value=self.config.get("USE_INDEED", False))
        
        seek_check = tk.Checkbutton(platform_row, text="  SEEK.com.au", 
                                    variable=self.seek_var,
                                    bg=COLORS["bg_card"], fg=COLORS["text_primary"],
                                    selectcolor=COLORS["bg_input"],
                                    activebackground=COLORS["bg_card"],
                                    font=FONT_NORMAL)
        seek_check.pack(side="left", padx=(0, 40))
        
        indeed_check = tk.Checkbutton(platform_row, text="  Indeed.com.au", 
                                      variable=self.indeed_var,
                                      bg=COLORS["bg_card"], fg=COLORS["text_primary"],
                                      selectcolor=COLORS["bg_input"],
                                      activebackground=COLORS["bg_card"],
                                      font=FONT_NORMAL)
        indeed_check.pack(side="left")

    def _build_jobs_tab(self):
        """Build Jobs tab content"""
        frame = tk.Frame(self.tab_scroll_frame, bg=COLORS["bg_dark"])
        self.tab_frames["jobs"] = frame
        
        # Job preferences card
        card = tk.Frame(frame, bg=COLORS["bg_card"])
        card.pack(fill="x", pady=(0, 15))
        
        inner = tk.Frame(card, bg=COLORS["bg_card"])
        inner.pack(fill="x", padx=25, pady=20)
        
        # Header
        header = tk.Frame(inner, bg=COLORS["bg_card"])
        header.pack(fill="x", pady=(0, 15))
        tk.Label(header, text="🎯  Job Preferences", 
                bg=COLORS["bg_card"], fg=COLORS["text_primary"],
                font=FONT_SUBHEADER).pack(anchor="w")
        tk.Label(header, text="Configure what jobs you're looking for",
                bg=COLORS["bg_card"], fg=COLORS["text_muted"],
                font=FONT_LABEL).pack(anchor="w", pady=(5, 0))
        
        # Job Titles
        tk.Label(inner, text="TARGET JOB TITLES", bg=COLORS["bg_card"], 
                fg=COLORS["text_muted"], font=FONT_LABEL_BOLD).pack(anchor="w", pady=(15, 8))
        tk.Label(inner, text="Comma separated list of roles you want to apply for",
                bg=COLORS["bg_card"], fg=COLORS["text_muted"],
                font=FONT_LABEL).pack(anchor="w", pady=(0, 8))
        
        self.job_entry = ModernEntry(inner)
        # Job titles will be set by build_preset_chips if presets are selected
        # Otherwise, load from config
        raw = self.config.get("JOB_TITLES", [])
        if raw:
            self.job_entry.insert(0, ", ".join(raw))
        self.job_entry.pack(fill="x", pady=(0, 15))
        
        # Bind to update config when manually edited (but don't clear selected presets)
        self.job_entry.entry.bind("<KeyRelease>", self._on_job_entry_change)
        
        # Preset chips
        tk.Label(inner, text="QUICK PRESETS (Click to select multiple)", bg=COLORS["bg_card"], 
                fg=COLORS["text_muted"], font=FONT_LABEL_BOLD).pack(anchor="w", pady=(10, 10))
        
        self.build_preset_chips(inner)
        
        # Selected presets display
        self.selected_presets_frame = tk.Frame(inner, bg=COLORS["bg_card"])
        self.selected_presets_frame.pack(fill="x", pady=(15, 0))
        self._update_selected_presets_display()
        
        # Max jobs and salary row
        row = tk.Frame(inner, bg=COLORS["bg_card"])
        row.pack(fill="x", pady=(20, 0))
        
        # Max Jobs
        max_frame = tk.Frame(row, bg=COLORS["bg_card"])
        max_frame.pack(side="left", fill="x", expand=True, padx=(0, 10))
        tk.Label(max_frame, text="MAX APPLICATIONS", bg=COLORS["bg_card"], 
                fg=COLORS["text_muted"], font=FONT_LABEL_BOLD).pack(anchor="w", pady=(0, 8))
        self.max_entry = ModernEntry(max_frame, width=15)
        self.max_entry.insert(0, str(self.config.get("MAX_JOBS", 100)))
        self.max_entry.pack(fill="x")
        
        # Expected Salary
        salary_frame = tk.Frame(row, bg=COLORS["bg_card"])
        salary_frame.pack(side="left", fill="x", expand=True, padx=(10, 0))
        tk.Label(salary_frame, text="EXPECTED SALARY ($)", bg=COLORS["bg_card"], 
                fg=COLORS["text_muted"], font=FONT_LABEL_BOLD).pack(anchor="w", pady=(0, 8))
        self.salary_entry = ModernEntry(salary_frame, width=15)
        self.salary_entry.insert(0, str(self.config.get("EXPECTED_SALARY", 100000)))
        self.salary_entry.pack(fill="x")
        
        # Blocklist card
        block_card = tk.Frame(frame, bg=COLORS["bg_card"])
        block_card.pack(fill="x", pady=(0, 15))
        
        block_inner = tk.Frame(block_card, bg=COLORS["bg_card"])
        block_inner.pack(fill="x", padx=25, pady=20)
        
        tk.Label(block_inner, text="🚫  Block List", 
                bg=COLORS["bg_card"], fg=COLORS["text_primary"],
                font=FONT_SUBHEADER).pack(anchor="w", pady=(0, 5))
        tk.Label(block_inner, text="Companies and job titles to skip",
                bg=COLORS["bg_card"], fg=COLORS["text_muted"],
                font=FONT_LABEL).pack(anchor="w", pady=(0, 15))
        
        # Blocked Companies
        tk.Label(block_inner, text="BLOCKED COMPANIES", bg=COLORS["bg_card"], 
                fg=COLORS["text_muted"], font=FONT_LABEL_BOLD).pack(anchor="w", pady=(0, 8))
        self.blocked_companies_entry = ModernEntry(block_inner)
        self.blocked_companies_entry.insert(0, ", ".join(self.config.get("BLOCKED_COMPANIES", [])))
        self.blocked_companies_entry.pack(fill="x", pady=(0, 15))
        
        # Blocked Titles
        tk.Label(block_inner, text="BLOCKED JOB TITLES", bg=COLORS["bg_card"], 
                fg=COLORS["text_muted"], font=FONT_LABEL_BOLD).pack(anchor="w", pady=(0, 8))
        self.blocked_titles_entry = ModernEntry(block_inner)
        self.blocked_titles_entry.insert(0, ", ".join(self.config.get("BLOCKED_TITLES", [])))
        self.blocked_titles_entry.pack(fill="x")

    def _build_speed_tab(self):
        """Build Speed tab content"""
        frame = tk.Frame(self.tab_scroll_frame, bg=COLORS["bg_dark"])
        self.tab_frames["speed"] = frame
        
        self.build_speed_panel(frame)

    def _build_api_tab(self):
        """Build API tab content"""
        frame = tk.Frame(self.tab_scroll_frame, bg=COLORS["bg_dark"])
        self.tab_frames["api"] = frame
        
        # API Keys card
        card = tk.Frame(frame, bg=COLORS["bg_card"])
        card.pack(fill="x", pady=(0, 15))
        
        inner = tk.Frame(card, bg=COLORS["bg_card"])
        inner.pack(fill="x", padx=25, pady=20)
        
        # Header
        tk.Label(inner, text="🔑  API Configuration", 
                bg=COLORS["bg_card"], fg=COLORS["text_primary"],
                font=FONT_SUBHEADER).pack(anchor="w", pady=(0, 5))
        tk.Label(inner, text="Configure your API keys for GPT and CAPTCHA solving",
                bg=COLORS["bg_card"], fg=COLORS["text_muted"],
                font=FONT_LABEL).pack(anchor="w", pady=(0, 20))
        
        # OpenAI API Key
        tk.Label(inner, text="OPENAI API KEY", bg=COLORS["bg_card"], 
                fg=COLORS["text_muted"], font=FONT_LABEL_BOLD).pack(anchor="w", pady=(0, 8))
        
        api_frame = tk.Frame(inner, bg=COLORS["bg_card"])
        api_frame.pack(fill="x", pady=(0, 20))
        
        self.api_entry = ModernEntry(api_frame, show="•")
        self.api_entry.insert(0, self.config.get("OPENAI_API_KEY", ""))
        self.api_entry.pack(side="left", fill="x", expand=True)
        
        self.show_api_btn = ModernButton(api_frame, text="👁", command=self.toggle_api, 
                                        style="dark", width=45)
        self.show_api_btn.pack(side="right", padx=(10, 0))
        
        # 2Captcha API Key
        tk.Label(inner, text="2CAPTCHA API KEY", bg=COLORS["bg_card"], 
                fg=COLORS["text_muted"], font=FONT_LABEL_BOLD).pack(anchor="w", pady=(0, 8))
        
        captcha_frame = tk.Frame(inner, bg=COLORS["bg_card"])
        captcha_frame.pack(fill="x", pady=(0, 20))
        
        self.captcha_api_entry = ModernEntry(captcha_frame, show="•")
        self.captcha_api_entry.insert(0, self.config.get("TWOCAPTCHA_API_KEY", ""))
        self.captcha_api_entry.pack(side="left", fill="x", expand=True)
        
        self.show_captcha_btn = ModernButton(captcha_frame, text="👁", command=self.toggle_captcha_api, 
                                            style="dark", width=45)
        self.show_captcha_btn.pack(side="right", padx=(10, 0))
        
        # Notifications toggle
        notif_card = tk.Frame(frame, bg=COLORS["bg_card"])
        notif_card.pack(fill="x", pady=(0, 15))
        
        notif_inner = tk.Frame(notif_card, bg=COLORS["bg_card"])
        notif_inner.pack(fill="x", padx=25, pady=20)
        
        tk.Label(notif_inner, text="🔔  Notifications", 
                bg=COLORS["bg_card"], fg=COLORS["text_primary"],
                font=FONT_SUBHEADER).pack(anchor="w", pady=(0, 15))
        
        self.notifications_var = tk.BooleanVar(value=self.config.get("NOTIFICATIONS_ENABLED", False))
        
        notif_row = tk.Frame(notif_inner, bg=COLORS["bg_card"])
        notif_row.pack(fill="x")
        
        self.notif_btn = tk.Button(notif_row, 
            text="🔕 NOTIFICATIONS: OFF" if not self.notifications_var.get() else "🔔 NOTIFICATIONS: ON",
            font=FONT_BOLD,
            bg=COLORS["bg_input"] if not self.notifications_var.get() else COLORS["success"],
            fg=COLORS["text_secondary"] if not self.notifications_var.get() else COLORS["text_primary"],
            activebackground=COLORS["border"],
            activeforeground=COLORS["text_primary"],
            relief="flat", padx=15, pady=8, cursor="hand2",
            command=self.toggle_notifications)
        self.notif_btn.pack(side="left")
        
        tk.Label(notif_row, 
            text="  Get desktop notifications when applications are submitted",
            bg=COLORS["bg_card"], fg=COLORS["text_muted"],
            font=FONT_LABEL).pack(side="left", padx=(15, 0))
        
        # Gmail Cleanup toggle
        gmail_card = tk.Frame(frame, bg=COLORS["bg_card"])
        gmail_card.pack(fill="x", pady=(0, 15))
        
        gmail_inner = tk.Frame(gmail_card, bg=COLORS["bg_card"])
        gmail_inner.pack(fill="x", padx=25, pady=20)
        
        tk.Label(gmail_inner, text="📧  Gmail Cleanup", 
                bg=COLORS["bg_card"], fg=COLORS["text_primary"],
                font=FONT_SUBHEADER).pack(anchor="w", pady=(0, 5))
        tk.Label(gmail_inner, text="Automatically delete notification emails while preserving important ones",
                bg=COLORS["bg_card"], fg=COLORS["text_muted"],
                font=FONT_LABEL).pack(anchor="w", pady=(0, 15))
        
        self.gmail_cleanup_var = tk.BooleanVar(value=self.config.get("USE_GMAIL_CLEANUP", False))
        
        gmail_row = tk.Frame(gmail_inner, bg=COLORS["bg_card"])
        gmail_row.pack(fill="x")
        
        self.gmail_btn = tk.Button(gmail_row, 
            text="📧 GMAIL CLEANUP: OFF" if not self.gmail_cleanup_var.get() else "📧 GMAIL CLEANUP: ON",
            font=FONT_BOLD,
            bg=COLORS["bg_input"] if not self.gmail_cleanup_var.get() else COLORS["success"],
            fg=COLORS["text_secondary"] if not self.gmail_cleanup_var.get() else COLORS["text_primary"],
            activebackground=COLORS["border"],
            activeforeground=COLORS["text_primary"],
            relief="flat", padx=15, pady=8, cursor="hand2",
            command=self.toggle_gmail_cleanup)
        self.gmail_btn.pack(side="left")
        
        tk.Label(gmail_row, 
            text="  Runs continuously in background, uses GPT to identify important emails",
            bg=COLORS["bg_card"], fg=COLORS["text_muted"],
            font=FONT_LABEL).pack(side="left", padx=(15, 0))
        
        # Twilio WhatsApp Configuration
        twilio_card = tk.Frame(frame, bg=COLORS["bg_card"])
        twilio_card.pack(fill="x", pady=(0, 15))
        
        twilio_inner = tk.Frame(twilio_card, bg=COLORS["bg_card"])
        twilio_inner.pack(fill="x", padx=25, pady=20)
        
        tk.Label(twilio_inner, text="📱  WhatsApp Notifications (Twilio)", 
                bg=COLORS["bg_card"], fg=COLORS["text_primary"],
                font=FONT_SUBHEADER).pack(anchor="w", pady=(0, 5))
        tk.Label(twilio_inner, text="Get a summary on WhatsApp when run completes",
                bg=COLORS["bg_card"], fg=COLORS["text_muted"],
                font=FONT_LABEL).pack(anchor="w", pady=(0, 15))
        
        # WhatsApp toggle
        self.whatsapp_var = tk.BooleanVar(value=self.config.get("WHATSAPP_NOTIFICATIONS", True))
        
        wa_toggle_row = tk.Frame(twilio_inner, bg=COLORS["bg_card"])
        wa_toggle_row.pack(fill="x", pady=(0, 15))
        
        self.whatsapp_btn = tk.Button(wa_toggle_row, 
            text="📱 WHATSAPP: ON" if self.whatsapp_var.get() else "📱 WHATSAPP: OFF",
            font=FONT_BOLD,
            bg=COLORS["success"] if self.whatsapp_var.get() else COLORS["bg_input"],
            fg=COLORS["text_primary"] if self.whatsapp_var.get() else COLORS["text_secondary"],
            activebackground=COLORS["border"],
            activeforeground=COLORS["text_primary"],
            relief="flat", padx=15, pady=8, cursor="hand2",
            command=self.toggle_whatsapp)
        self.whatsapp_btn.pack(side="left")
        
        tk.Label(wa_toggle_row, 
            text="  Send run summary to your WhatsApp",
            bg=COLORS["bg_card"], fg=COLORS["text_muted"],
            font=FONT_LABEL).pack(side="left", padx=(15, 0))
        
        # Twilio Account SID
        tk.Label(twilio_inner, text="TWILIO ACCOUNT SID", bg=COLORS["bg_card"], 
                fg=COLORS["text_muted"], font=FONT_LABEL_BOLD).pack(anchor="w", pady=(10, 8))
        
        self.twilio_sid_entry = ModernEntry(twilio_inner, show="•")
        self.twilio_sid_entry.insert(0, self.config.get("TWILIO_ACCOUNT_SID", ""))
        self.twilio_sid_entry.pack(fill="x", pady=(0, 15))
        
        # Twilio Auth Token
        tk.Label(twilio_inner, text="TWILIO AUTH TOKEN", bg=COLORS["bg_card"], 
                fg=COLORS["text_muted"], font=FONT_LABEL_BOLD).pack(anchor="w", pady=(0, 8))
        
        twilio_token_frame = tk.Frame(twilio_inner, bg=COLORS["bg_card"])
        twilio_token_frame.pack(fill="x", pady=(0, 15))
        
        self.twilio_token_entry = ModernEntry(twilio_token_frame, show="•")
        self.twilio_token_entry.insert(0, self.config.get("TWILIO_AUTH_TOKEN", ""))
        self.twilio_token_entry.pack(side="left", fill="x", expand=True)
        
        self.show_twilio_btn = ModernButton(twilio_token_frame, text="👁", command=self.toggle_twilio_token, 
                                           style="dark", width=45)
        self.show_twilio_btn.pack(side="right", padx=(10, 0))
        
        # Twilio WhatsApp From Number
        tk.Label(twilio_inner, text="TWILIO WHATSAPP NUMBER", bg=COLORS["bg_card"], 
                fg=COLORS["text_muted"], font=FONT_LABEL_BOLD).pack(anchor="w", pady=(0, 8))
        
        self.twilio_from_entry = ModernEntry(twilio_inner)
        self.twilio_from_entry.insert(0, self.config.get("TWILIO_WHATSAPP_FROM", "whatsapp:+14155238886"))
        self.twilio_from_entry.pack(fill="x")
        
        tk.Label(twilio_inner, text="💡 Default is Twilio Sandbox: whatsapp:+14155238886",
                bg=COLORS["bg_card"], fg=COLORS["text_muted"],
                font=FONT_LABEL).pack(anchor="w", pady=(5, 0))

    def build_preset_chips(self, parent):
        """Build modern chip-style preset buttons with multi-select capability"""
        # Container for all chips
        chips_container = tk.Frame(parent, bg=COLORS["bg_card"])
        chips_container.pack(fill="x", pady=(0, 10))
        
        # Store presets as instance variable for later access
        self.presets = [
            # Row 1
            ("Director", ["director", "managing director", "executive director", "general manager",
                         "head of", "chief", "vice president", "regional manager", "country manager"]),
            ("Executive", ["ceo", "coo", "cfo", "cto", "chief officer", "executive", "c-level",
                          "managing director", "board", "principal"]),
            ("Senior Mgmt", ["senior manager", "department head", "division manager", "branch manager",
                            "area manager", "national manager", "group manager", "practice lead"]),
            ("Team Lead", ["team lead", "team leader", "supervisor", "coordinator", "shift manager",
                          "section leader", "group leader", "floor manager"]),
            # Row 2
            ("PM/Agile", ["project manager", "program manager", "delivery manager", "project lead",
                         "scrum master", "agile coach", "agile", "pmo", "portfolio manager"]),
            ("Change", ["change manager", "transformation", "business transformation", "digital transformation",
                       "organisational change", "change lead", "transition manager", "improvement"]),
            ("BA/Analysis", ["business analyst", "systems analyst", "data analyst", "requirements analyst",
                            "process analyst", "functional analyst", "technical analyst", "reporting analyst"]),
            ("Consulting", ["consultant", "management consultant", "business consultant", "strategy consultant",
                           "senior consultant", "principal consultant", "advisory", "professional services"]),
            # Row 3
            ("Operations", ["operations manager", "operations coordinator", "service manager", "facility manager",
                           "logistics manager", "supply chain", "warehouse manager", "distribution"]),
            ("Admin", ["administrator", "office manager", "executive assistant", "personal assistant",
                      "receptionist", "admin officer", "office coordinator", "secretary"]),
            ("HR/People", ["hr manager", "human resources", "people and culture", "talent acquisition",
                          "recruitment", "hr business partner", "learning and development", "payroll"]),
            ("Finance", ["finance manager", "accountant", "financial analyst", "accounts manager",
                        "bookkeeper", "financial controller", "cfo", "treasury", "credit"]),
            # Row 4
            ("IT/Tech", ["it manager", "software engineer", "developer", "systems administrator",
                        "network engineer", "devops", "cloud engineer", "infrastructure", "technical support"]),
            ("Data/AI", ["data scientist", "data engineer", "machine learning", "ai", "analytics",
                        "business intelligence", "data analyst", "statistician", "big data"]),
            ("Product", ["product manager", "product owner", "ux designer", "ui designer",
                        "product designer", "user experience", "digital product", "product lead"]),
            ("Cyber/Sec", ["cybersecurity", "security analyst", "information security", "soc analyst",
                          "penetration tester", "security engineer", "risk analyst", "compliance"]),
            # Row 5
            ("Sales", ["sales manager", "account executive", "business development", "bdm",
                      "sales representative", "key account", "territory manager", "sales director"]),
            ("Marketing", ["marketing manager", "digital marketing", "content manager", "brand manager",
                          "marketing coordinator", "social media", "seo", "communications"]),
            ("Customer", ["customer success", "client manager", "relationship manager", "account manager",
                         "customer service", "client services", "engagement manager", "partnerships"]),
            ("Retail", ["store manager", "retail manager", "assistant manager", "department manager",
                       "visual merchandiser", "buyer", "category manager", "merchandise"]),
            # Row 6
            ("Healthcare", ["registered nurse", "clinical manager", "healthcare administrator", "nurse manager",
                           "medical officer", "health services", "patient coordinator", "care manager"]),
            ("Education", ["teacher", "lecturer", "education coordinator", "training manager",
                          "curriculum developer", "instructional designer", "academic", "learning"]),
            ("Gov/APS", ["el2", "ses", "aps", "policy officer", "government", "public sector",
                        "compliance officer", "regulatory", "grants", "procurement"]),
            ("NFP/Social", ["community", "youth worker", "case manager", "ndis", "support worker",
                           "family support", "mental health", "welfare", "program officer", "grants"]),
            # Row 7 - New Anthropology/Research preset
            ("Anthropology/Research", ["anthropologist", "social anthropologist", "cultural anthropologist",
                                     "research officer", "research manager", "research analyst", "researcher",
                                     "research coordinator", "research consultant", "ethnographer",
                                     "field researcher", "qualitative researcher", "social researcher"]),
        ]
        
        # Initialize selected presets from config
        self.selected_presets = set(self.config.get("SELECTED_PRESETS", []))
        
        # Create rows of chips (4 per row) - Updated to 7 rows
        for row_idx in range(7):
            row_frame = tk.Frame(chips_container, bg=COLORS["bg_card"])
            row_frame.pack(fill="x", pady=3)
            
            for col_idx in range(4):
                idx = row_idx * 4 + col_idx
                if idx < len(self.presets):
                    name, titles = self.presets[idx]
                    chip = self._create_chip(row_frame, name, titles, name in self.selected_presets)
                    chip.pack(side="left", padx=(0, 8), pady=2)
        
        # Update job titles based on selected presets
        self._update_job_titles_from_presets()

    def _create_chip(self, parent, name, titles, is_selected=False):
        """Create a modern chip button with toggle capability"""
        chip = tk.Frame(parent, bg=COLORS["accent_primary"] if is_selected else COLORS["border"], cursor="hand2")
        
        label = tk.Label(chip, text=name, 
                        bg=COLORS["accent_primary"] if is_selected else COLORS["border"],
                        fg=COLORS["bg_dark"] if is_selected else COLORS["text_secondary"],
                        font=FONT_CHIP, padx=12, pady=6)
        label.pack()
        
        # Store chip state and references
        chip.is_selected = is_selected
        chip.name = name
        chip.titles = titles
        chip.label = label  # Store label reference for hover updates
        
        # Bind events - use chip reference directly
        def on_click(e):
            self._toggle_preset(chip, name, titles)
        
        def on_enter(e):
            self._chip_hover(chip, label, True)
        
        def on_leave(e):
            self._chip_hover(chip, label, False)
        
        for widget in [chip, label]:
            widget.bind("<Button-1>", on_click)
            widget.bind("<Enter>", on_enter)
            widget.bind("<Leave>", on_leave)
        
        return chip
    
    def _toggle_preset(self, chip, name, titles):
        """Toggle a preset on/off and update job titles"""
        chip.is_selected = not chip.is_selected
        
        if chip.is_selected:
            self.selected_presets.add(name)
            chip.config(bg=COLORS["accent_primary"])
            chip.label.config(bg=COLORS["accent_primary"], fg=COLORS["bg_dark"])
        else:
            self.selected_presets.discard(name)
            chip.config(bg=COLORS["border"])
            chip.label.config(bg=COLORS["border"], fg=COLORS["text_secondary"])
        
        # Update job titles from all selected presets
        self._update_job_titles_from_presets()
        
        # Update selected presets display
        self._update_selected_presets_display()
        
        # Save selected presets to config
        self.config["SELECTED_PRESETS"] = list(self.selected_presets)
        save_config(self.config)
    
    def _update_job_titles_from_presets(self):
        """Combine all titles from selected presets and update job entry"""
        all_titles = []
        seen = set()
        
        # Get all titles from selected presets
        for preset_name, preset_titles in self.presets:
            if preset_name in self.selected_presets:
                for title in preset_titles:
                    title_lower = title.lower().strip()
                    if title_lower not in seen:
                        seen.add(title_lower)
                        all_titles.append(title)
        
        # Update job entry
        self.job_entry.delete(0, tk.END)
        if all_titles:
            self.job_entry.insert(0, ", ".join(all_titles))
        
        # Update config
        self.config["JOB_TITLES"] = all_titles
        save_config(self.config)
    
    def _update_selected_presets_display(self):
        """Update the display showing selected presets and their titles"""
        # Clear existing display
        for widget in self.selected_presets_frame.winfo_children():
            widget.destroy()
        
        if not self.selected_presets:
            # Show message when nothing is selected
            tk.Label(self.selected_presets_frame, 
                    text="No presets selected. Click chips above to select job title categories.",
                    bg=COLORS["bg_card"], fg=COLORS["text_muted"],
                    font=("Segoe UI", 9), wraplength=600, justify="left").pack(anchor="w")
            return
        
        # Header
        header = tk.Frame(self.selected_presets_frame, bg=COLORS["bg_card"])
        header.pack(fill="x", pady=(0, 10))
        tk.Label(header, text=f"✅ Selected Presets ({len(self.selected_presets)}):", 
                bg=COLORS["bg_card"], fg=COLORS["text_primary"],
                font=FONT_LABEL_BOLD).pack(anchor="w")
        
        # Create scrollable frame for selected presets
        canvas = tk.Canvas(self.selected_presets_frame, bg=COLORS["bg_card"], 
                          highlightthickness=0, height=200)
        scrollbar = tk.Scrollbar(self.selected_presets_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg=COLORS["bg_card"])
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # Display each selected preset with its titles
        for preset_name, preset_titles in self.presets:
            if preset_name in self.selected_presets:
                # Preset name
                preset_frame = tk.Frame(scrollable_frame, bg=COLORS["bg_input"], relief="flat", bd=1)
                preset_frame.pack(fill="x", pady=(0, 8), padx=(0, 5))
                
                preset_inner = tk.Frame(preset_frame, bg=COLORS["bg_input"])
                preset_inner.pack(fill="x", padx=12, pady=10)
                
                # Preset name label
                name_label = tk.Label(preset_inner, 
                    text=f"📌 {preset_name}",
                    bg=COLORS["bg_input"], fg=COLORS["accent_primary"],
                    font=("Segoe UI", 10, "bold"), anchor="w")
                name_label.pack(fill="x", pady=(0, 5))
                
                # Titles list
                titles_text = ", ".join(preset_titles)
                titles_label = tk.Label(preset_inner,
                    text=f"   Titles: {titles_text}",
                    bg=COLORS["bg_input"], fg=COLORS["text_secondary"],
                    font=("Segoe UI", 9), anchor="w", justify="left", wraplength=700)
                titles_label.pack(fill="x")
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Update scroll region after all widgets are added
        canvas.update_idletasks()
        canvas.configure(scrollregion=canvas.bbox("all"))
        
        # Bind mousewheel
        def on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        canvas.bind_all("<MouseWheel>", on_mousewheel)
    
    def _on_job_entry_change(self, event=None):
        """Handle manual edits to job entry - update config but keep selected presets"""
        # Parse job titles from entry
        entry_text = self.job_entry.get().strip()
        if entry_text:
            titles = [t.strip() for t in entry_text.split(",") if t.strip()]
            self.config["JOB_TITLES"] = titles
            save_config(self.config)

    def _chip_hover(self, chip, label, entering):
        """Handle chip hover state"""
        if entering:
            if not chip.is_selected:
                chip.config(bg=COLORS["accent_primary"])
                label.config(bg=COLORS["accent_primary"], fg=COLORS["bg_dark"])
        else:
            if not chip.is_selected:
                chip.config(bg=COLORS["border"])
                label.config(bg=COLORS["border"], fg=COLORS["text_secondary"])

    def build_speed_panel(self, parent):
        """Build the speed sliders card with collapsible section"""
        self.speed_card = CollapsibleCard(parent, title="Speed Controls", icon="⚡", default_expanded=True)
        self.speed_card.pack(fill="x", pady=(0, 15))
        
        sliders = self.speed_card.get_content()

        # Slider 1: Page Scan Speed
        self.scan_speed_slider = ModernSlider(
            sliders,
            label="🔍 Page Scan Speed",
            min_val=1,
            max_val=100,
            default=self.config.get("SCAN_SPEED", 50),
            unit="%",
            description="How fast the bot loads pages and finds the Quick Apply button",
            on_change=self.on_speed_change
        )
        self.scan_speed_slider.pack(fill="x", pady=(0, 15))

        # Slider 2: Apply Speed
        self.apply_speed_slider = ModernSlider(
            sliders,
            label="📝 Apply Speed",
            min_val=1,
            max_val=100,
            default=self.config.get("APPLY_SPEED", 50),
            unit="%",
            description="How fast the bot fills forms, answers questions, and submits",
            on_change=self.on_speed_change
        )
        self.apply_speed_slider.pack(fill="x", pady=(0, 15))

        # Slider 3: Cooldown Delay
        self.cooldown_slider = ModernSlider(
            sliders,
            label="⏳ Cooldown Between Jobs",
            min_val=0,
            max_val=720,  # Increased to 12 minutes for 24/7 mode
            default=self.config.get("COOLDOWN_DELAY", 5),
            unit="s",
            description="Pause between each job application (reduces detection risk)",
            on_change=self.on_speed_change
        )
        self.cooldown_slider.pack(fill="x")

        # Speed preset buttons
        preset_frame = tk.Frame(sliders, bg=COLORS["bg_card"])
        preset_frame.pack(fill="x", pady=(15, 0))
        
        tk.Label(preset_frame, text="Quick Presets:", bg=COLORS["bg_card"],
                fg=COLORS["text_muted"], font=FONT_LABEL).pack(side="left", padx=(0, 10))
        
        presets = [
            ("🐢 Safe", 30, 30, 10),
            ("⚖️ Balanced", 50, 50, 5),
            ("🚀 Fast", 75, 75, 2),
            ("💨 Insane", 100, 100, 0),
        ]
        
        for name, scan, apply, cooldown in presets:
            btn = tk.Button(preset_frame, text=name, font=FONT_LABEL,
                           bg=COLORS["bg_input"], fg=COLORS["text_secondary"],
                           activebackground=COLORS["border"],
                           activeforeground=COLORS["text_primary"],
                           relief="flat", padx=10, pady=4, cursor="hand2",
                           command=lambda s=scan, a=apply, c=cooldown: self.set_speed_preset(s, a, c))
            btn.pack(side="left", padx=2)
            btn.bind("<Enter>", lambda e, b=btn: b.config(bg=COLORS["border"]))
            btn.bind("<Leave>", lambda e, b=btn: b.config(bg=COLORS["bg_input"]))
        
        # 24/7 Mode button
        self.mode_24_7_var = tk.BooleanVar(value=self.config.get("MODE_24_7", False))
        mode_24_7_btn = tk.Button(preset_frame, 
            text="🕐 24/7 MODE" if not self.mode_24_7_var.get() else "🕐 24/7: ON",
            font=FONT_LABEL,
            bg=COLORS["accent_primary"] if self.mode_24_7_var.get() else COLORS["bg_input"],
            fg=COLORS["text_primary"] if self.mode_24_7_var.get() else COLORS["text_secondary"],
            activebackground=COLORS["accent_primary"],
            activeforeground=COLORS["text_primary"],
            relief="flat", padx=10, pady=4, cursor="hand2",
            command=self.toggle_24_7_mode)
        mode_24_7_btn.pack(side="left", padx=(10, 2))
        mode_24_7_btn.bind("<Enter>", lambda e, b=mode_24_7_btn: b.config(bg=COLORS["border"] if not self.mode_24_7_var.get() else COLORS["accent_primary"]))
        mode_24_7_btn.bind("<Leave>", lambda e, b=mode_24_7_btn: b.config(bg=COLORS["accent_primary"] if self.mode_24_7_var.get() else COLORS["bg_input"]))
        self.mode_24_7_btn = mode_24_7_btn
        
        # Apply 24/7 settings if enabled
        if self.mode_24_7_var.get():
            self.scan_speed_slider.set(20)
            self.apply_speed_slider.set(20)
            self.cooldown_slider.set(720)
            if hasattr(self, 'max_entry'):
                self.max_entry.delete(0, tk.END)
                self.max_entry.insert(0, "100")
        
        # Stealth Mode toggle
        stealth_frame = tk.Frame(sliders, bg=COLORS["bg_card"])
        stealth_frame.pack(fill="x", pady=(15, 0))
        
        self.stealth_var = tk.BooleanVar(value=self.config.get("STEALTH_MODE", False))
        
        self.stealth_btn = tk.Button(stealth_frame, 
            text="🥷 STEALTH MODE: OFF",
            font=FONT_BOLD,
            bg=COLORS["bg_input"], 
            fg=COLORS["text_secondary"],
            activebackground=COLORS["accent_secondary"],
            activeforeground=COLORS["text_primary"],
            relief="flat", padx=15, pady=8, cursor="hand2",
            command=self.toggle_stealth_mode)
        self.stealth_btn.pack(side="left")
        
        # Update button state based on saved config
        if self.stealth_var.get():
            self.stealth_btn.config(
                text="🥷 STEALTH MODE: ON",
                bg=COLORS["accent_secondary"],
                fg=COLORS["text_primary"]
            )
        
        tk.Label(stealth_frame, 
            text="  Adds random scrolls, pauses & human-like behavior",
            bg=COLORS["bg_card"], fg=COLORS["text_muted"],
            font=("Segoe UI", 9)).pack(side="left", padx=(10, 0))
        
        # GPT Job Check toggle (Tight vs Loose applications)
        gpt_mode_frame = tk.Frame(sliders, bg=COLORS["bg_card"])
        gpt_mode_frame.pack(fill="x", pady=(12, 0))
        
        self.gpt_mode_var = tk.BooleanVar(value=self.config.get("GPT_JOB_CHECK", False))
        
        self.gpt_mode_btn = tk.Button(gpt_mode_frame, 
            text="🎯 TIGHT MODE",
            font=FONT_BOLD,
            bg=COLORS["gpt_highlight"], 
            fg=COLORS["text_primary"],
            activebackground=COLORS["accent_secondary"],
            activeforeground=COLORS["text_primary"],
            relief="flat", padx=15, pady=8, cursor="hand2",
            command=self.toggle_gpt_mode)
        self.gpt_mode_btn.pack(side="left")
        
        # Update button state based on saved config (default to LOOSE mode)
        if not self.gpt_mode_var.get():
            self.gpt_mode_btn.config(
                text="⚡ LOOSE MODE",
                bg=COLORS["accent_secondary"],
                fg=COLORS["text_primary"]
            )
        else:
            self.gpt_mode_btn.config(
                text="🎯 TIGHT MODE",
                bg=COLORS["bg_input"],
                fg=COLORS["text_secondary"]
            )
        
        tk.Label(gpt_mode_frame, 
            text="  TIGHT = GPT checks job relevance  |  LOOSE = Apply to everything",
            bg=COLORS["bg_card"], fg=COLORS["text_muted"],
            font=("Segoe UI", 9)).pack(side="left", padx=(10, 0))

    def set_speed_preset(self, scan, apply, cooldown):
        """Apply a speed preset to all sliders"""
        self.scan_speed_slider.set(scan)
        self.apply_speed_slider.set(apply)
        self.cooldown_slider.set(cooldown)
        self.on_speed_change(None)

    def toggle_stealth_mode(self):
        """Toggle stealth mode on/off"""
        current = self.stealth_var.get()
        new_state = not current
        self.stealth_var.set(new_state)
        
        if new_state:
            self.stealth_btn.config(
                text="🥷 STEALTH MODE: ON",
                bg=COLORS["accent_secondary"],
                fg=COLORS["text_primary"]
            )
            self.log("INFO", "🥷 Stealth Mode ENABLED - Bot will behave more human-like")
            # Also set slower speeds for stealth
            self.scan_speed_slider.set(35)
            self.apply_speed_slider.set(30)
            self.cooldown_slider.set(8)
            self.on_speed_change(None)
        else:
            self.stealth_btn.config(
                text="🥷 STEALTH MODE: OFF",
                bg=COLORS["bg_input"],
                fg=COLORS["text_secondary"]
            )
            self.log("INFO", "Stealth Mode DISABLED")
        
        # Save to config
        self.config["STEALTH_MODE"] = new_state
        save_config(self.config)

    def toggle_24_7_mode(self):
        """Toggle 24/7 mode - throttles to ~5 jobs/hour, max 100 jobs/24h"""
        current = self.mode_24_7_var.get()
        new_state = not current
        self.mode_24_7_var.set(new_state)
        
        if new_state:
            # Enable 24/7 mode: slow speeds, long cooldown
            self.mode_24_7_btn.config(
                text="🕐 24/7: ON",
                bg=COLORS["accent_primary"],
                fg=COLORS["text_primary"]
            )
            # Set to ~5 jobs/hour: 1 job every 12 minutes = 720 seconds cooldown
            self.scan_speed_slider.set(20)
            self.apply_speed_slider.set(20)
            self.cooldown_slider.set(720)  # 12 minutes
            self.on_speed_change(None)
            # Set MAX_JOBS to 100
            if hasattr(self, 'max_entry'):
                self.max_entry.delete(0, tk.END)
                self.max_entry.insert(0, "100")
            self.log("INFO", "🕐 24/7 MODE ENABLED - ~5 jobs/hour, max 100 jobs/24h")
        else:
            # Disable 24/7 mode: restore to balanced
            self.mode_24_7_btn.config(
                text="🕐 24/7 MODE",
                bg=COLORS["bg_input"],
                fg=COLORS["text_secondary"]
            )
            self.scan_speed_slider.set(50)
            self.apply_speed_slider.set(50)
            self.cooldown_slider.set(5)
            self.on_speed_change(None)
            self.log("INFO", "24/7 MODE DISABLED - Restored to balanced speeds")
        
        # Save to config
        self.config["MODE_24_7"] = new_state
        save_config(self.config)
    
    def toggle_gpt_mode(self):
        """Toggle between TIGHT (GPT checks job relevance) and LOOSE (apply to all)"""
        current = self.gpt_mode_var.get()
        new_state = not current
        self.gpt_mode_var.set(new_state)
        
        if new_state:
            self.gpt_mode_btn.config(
                text="🎯 TIGHT MODE",
                bg=COLORS["gpt_highlight"],
                fg=COLORS["text_primary"]
            )
            self.log("INFO", "🎯 TIGHT MODE - GPT will check job descriptions match your target titles")
        else:
            self.gpt_mode_btn.config(
                text="⚡ LOOSE MODE",
                bg=COLORS["bg_input"],
                fg=COLORS["text_secondary"]
            )
            self.log("INFO", "⚡ LOOSE MODE - Apply to all jobs, skip GPT relevance check")
        
        # Save to config
        self.config["GPT_JOB_CHECK"] = new_state
        save_config(self.config)

    def on_speed_change(self, value):
        """Called when any speed slider changes"""
        # Update header speed display
        avg_speed = (self.scan_speed_slider.get() + self.apply_speed_slider.get()) // 2
        if avg_speed >= 90:
            speed_text = "INSANE"
            speed_color = COLORS["danger"]
        elif avg_speed >= 70:
            speed_text = "FAST"
            speed_color = COLORS["warning"]
        elif avg_speed >= 40:
            speed_text = "NORMAL"
            speed_color = COLORS["accent_primary"]
        else:
            speed_text = "SAFE"
            speed_color = COLORS["success"]
        
        self.header_speed.config(text=speed_text, fg=speed_color)
        
        # Update config summary
        if hasattr(self, 'config_summary'):
            self.config_summary.update_item("speed", speed_text, speed_color)

    def build_stats_panel(self, parent):
        """Build the statistics dashboard"""
        stats_frame = tk.Frame(parent, bg=COLORS["bg_dark"])
        stats_frame.pack(fill="x", pady=(0, 15))

        # Money Saved card
        money_card = tk.Frame(stats_frame, bg=COLORS["bg_card"])
        money_card.pack(side="left", fill="both", expand=True, padx=(0, 8))

        money_inner = tk.Frame(money_card, bg=COLORS["bg_card"])
        money_inner.pack(fill="both", expand=True, padx=25, pady=20)

        tk.Label(money_inner, text="💰 MONEY SAVED", 
                bg=COLORS["bg_card"], fg=COLORS["text_secondary"],
                font=FONT_LABEL).pack(anchor="w")
        
        self.money_label = tk.Label(money_inner, text="$0.00",
            bg=COLORS["bg_card"], fg=COLORS["money_green"],
            font=FONT_STATS)
        self.money_label.pack(anchor="w", pady=(5, 0))
        
        # Time Saved (2 mins per application)
        time_saved_frame = tk.Frame(money_inner, bg=COLORS["bg_card"])
        time_saved_frame.pack(anchor="w", pady=(8, 0))
        
        tk.Label(time_saved_frame, text="⏱ Time Saved: ", 
                bg=COLORS["bg_card"], fg=COLORS["text_muted"],
                font=FONT_LABEL).pack(side="left")
        
        self.time_saved_label = tk.Label(time_saved_frame, text="0 mins",
            bg=COLORS["bg_card"], fg=COLORS["accent_primary"],
            font=("Segoe UI", 11, "bold"))
        self.time_saved_label.pack(side="left")

        # Jobs Applied card
        jobs_card = tk.Frame(stats_frame, bg=COLORS["bg_card"])
        jobs_card.pack(side="left", fill="both", expand=True, padx=(8, 8))

        jobs_inner = tk.Frame(jobs_card, bg=COLORS["bg_card"])
        jobs_inner.pack(fill="both", expand=True, padx=25, pady=20)

        tk.Label(jobs_inner, text="📋 JOBS APPLIED", 
                bg=COLORS["bg_card"], fg=COLORS["text_secondary"],
                font=FONT_LABEL).pack(anchor="w")
        
        self.counter_label = tk.Label(jobs_inner, text="0",
            bg=COLORS["bg_card"], fg=COLORS["accent_primary"],
            font=FONT_STATS)
        self.counter_label.pack(anchor="w", pady=(5, 0))

        # Session Time card
        time_card = tk.Frame(stats_frame, bg=COLORS["bg_card"])
        time_card.pack(side="left", fill="both", expand=True, padx=(8, 0))

        time_inner = tk.Frame(time_card, bg=COLORS["bg_card"])
        time_inner.pack(fill="both", expand=True, padx=25, pady=20)

        tk.Label(time_inner, text="⏱ SESSION TIME", 
                bg=COLORS["bg_card"], fg=COLORS["text_secondary"],
                font=FONT_LABEL).pack(anchor="w")
        
        self.time_display = tk.Label(time_inner, text="00:00:00",
            bg=COLORS["bg_card"], fg=COLORS["text_primary"],
            font=FONT_STATS)
        self.time_display.pack(anchor="w", pady=(5, 0))

    def build_log_panel(self, parent):
        """Build the log viewer panel with collapse functionality"""
        self.log_card = tk.Frame(parent, bg=COLORS["bg_card"])
        self.log_card.pack(fill="both", expand=True)
        
        self.log_expanded = True  # Track collapse state

        # Card header with controls
        header = tk.Frame(self.log_card, bg=COLORS["bg_card"])
        header.pack(fill="x", padx=20, pady=(20, 15))

        # Left side - Title and collapse button
        title_frame = tk.Frame(header, bg=COLORS["bg_card"])
        title_frame.pack(side="left")
        
        self.collapse_btn = tk.Button(title_frame, text="▼", font=("Segoe UI", 12),
                                     bg=COLORS["bg_card"], fg=COLORS["accent_primary"],
                                     activebackground=COLORS["bg_card"], 
                                     activeforeground=COLORS["text_primary"],
                                     relief="flat", padx=4, pady=0, cursor="hand2",
                                     command=self.toggle_log_collapse)
        self.collapse_btn.pack(side="left", padx=(0, 8))
        
        tk.Label(title_frame, text="📝  Activity Log", 
                bg=COLORS["bg_card"], fg=COLORS["text_primary"],
                font=FONT_TITLE).pack(side="left")
        
        # Log line count indicator
        self.log_count_label = tk.Label(title_frame, text="(0 lines)", 
                                       bg=COLORS["bg_card"], fg=COLORS["text_muted"],
                                       font=FONT_LABEL)
        self.log_count_label.pack(side="left", padx=(10, 0))

        # Log controls frame (will be hidden when collapsed)
        self.log_controls = tk.Frame(header, bg=COLORS["bg_card"])
        self.log_controls.pack(side="right")

        # Filter
        self.filter_var = tk.StringVar()
        filter_entry = tk.Entry(self.log_controls, textvariable=self.filter_var,
                               bg=COLORS["bg_input"], fg=COLORS["text_primary"],
                               insertbackground=COLORS["accent_primary"],
                               relief="flat", font=FONT_LABEL, width=15)
        filter_entry.pack(side="left", ipady=4, ipadx=8)
        filter_entry.insert(0, "Filter...")
        filter_entry.bind("<FocusIn>", lambda e: filter_entry.delete(0, tk.END) if filter_entry.get() == "Filter..." else None)
        filter_entry.bind("<FocusOut>", lambda e: filter_entry.insert(0, "Filter...") if not filter_entry.get() else None)

        filter_btn = tk.Button(self.log_controls, text="🔍", font=FONT_LABEL,
                              bg=COLORS["bg_input"], fg=COLORS["text_secondary"],
                              activebackground=COLORS["border"], relief="flat",
                              padx=8, pady=2, cursor="hand2", command=self.apply_filter)
        filter_btn.pack(side="left", padx=(5, 10))

        # Wrap toggle
        self.wrap_enabled = True
        self.wrap_btn = tk.Button(self.log_controls, text="Wrap", font=FONT_LABEL,
                                 bg=COLORS["accent_primary"], fg="#000000",
                                 activebackground=COLORS["accent_secondary"], relief="flat",
                                 padx=8, pady=2, cursor="hand2", command=self.toggle_wrap)
        self.wrap_btn.pack(side="left", padx=(0, 5))

        # Clear button
        clear_btn = tk.Button(self.log_controls, text="Clear", font=FONT_LABEL,
                             bg=COLORS["bg_input"], fg=COLORS["text_secondary"],
                             activebackground=COLORS["border"], relief="flat",
                             padx=8, pady=2, cursor="hand2", command=self.clear_log)
        clear_btn.pack(side="left")

        # Log text area (collapsible)
        self.log_frame = tk.Frame(self.log_card, bg=COLORS["bg_card"])
        self.log_frame.pack(fill="both", expand=True, padx=20, pady=(0, 20))

        self.console = tk.Text(self.log_frame, bg=COLORS["bg_dark"], fg=COLORS["text_secondary"],
                              wrap="word", font=FONT_CONSOLE, relief="flat",
                              insertbackground=COLORS["accent_primary"],
                              selectbackground=COLORS["accent_secondary"])
        self.console.pack(side="left", fill="both", expand=True)

        scrollbar = ttk.Scrollbar(self.log_frame, command=self.console.yview,
                                 style="Modern.Vertical.TScrollbar")
        scrollbar.pack(side="right", fill="y")
        self.console.configure(yscrollcommand=scrollbar.set)

        # Configure log tags
        self.console.tag_config("ERROR", foreground=COLORS["danger"])
        self.console.tag_config("SUCCESS", foreground=COLORS["success"])
        self.console.tag_config("INFO", foreground=COLORS["text_secondary"])
        self.console.tag_config("timestamp", foreground=COLORS["text_muted"])
        
        # GPT/AI tag - vibrant magenta/pink for AI-powered actions
        self.console.tag_config("GPT", foreground="#FF6EC7", font=("Cascadia Code", 10, "bold"))
        
        # Configure clickable link tag
        self.console.tag_config("link", foreground=COLORS["accent_primary"], underline=True)
        self.console.tag_bind("link", "<Enter>", lambda e: self.console.config(cursor="hand2"))
        self.console.tag_bind("link", "<Leave>", lambda e: self.console.config(cursor=""))
        self.console.tag_bind("link", "<Button-1>", self.on_link_click)
        
        # Store URLs mapped to their position
        self.link_urls = {}

    def on_link_click(self, event):
        """Handle click on a link in the log"""
        # Get the index of the click
        index = self.console.index(f"@{event.x},{event.y}")
        
        # Find all link tags at this position
        tags = self.console.tag_names(index)
        
        for tag in tags:
            if tag.startswith("link_"):
                url = self.link_urls.get(tag)
                if url:
                    webbrowser.open(url)
                    self.log("INFO", f"Opening: {url}")
                break

    def toggle_log_collapse(self):
        """Toggle the log panel collapse state"""
        self.log_expanded = not self.log_expanded
        
        if self.log_expanded:
            # Expand
            self.collapse_btn.config(text="▼")
            self.log_frame.pack(fill="both", expand=True, padx=20, pady=(0, 20))
            self.log_controls.pack(side="right")
            self.log_card.pack(fill="both", expand=True)
        else:
            # Collapse
            self.collapse_btn.config(text="▶")
            self.log_frame.pack_forget()
            self.log_controls.pack_forget()
            # Make the card smaller when collapsed
            self.log_card.pack(fill="x", expand=False)
        
        # Update line count
        self.update_log_count()

    def update_log_count(self):
        """Update the log line count indicator"""
        try:
            content = self.console.get("1.0", tk.END)
            lines = len([l for l in content.splitlines() if l.strip()])
            
            # Count errors and successes
            errors = content.upper().count("ERROR")
            successes = content.upper().count("SUCCESS")
            
            if errors > 0 and successes > 0:
                self.log_count_label.config(
                    text=f"({lines} lines • {successes} ✓ • {errors} ✗)",
                    fg=COLORS["text_secondary"]
                )
            elif errors > 0:
                self.log_count_label.config(
                    text=f"({lines} lines • {errors} errors)",
                    fg=COLORS["danger"]
                )
            elif successes > 0:
                self.log_count_label.config(
                    text=f"({lines} lines • {successes} success)",
                    fg=COLORS["success"]
                )
            else:
                self.log_count_label.config(
                    text=f"({lines} lines)",
                    fg=COLORS["text_muted"]
                )
        except:
            pass

    # ============================================================
    # APPLICATION HISTORY PANEL
    # ============================================================
    def build_history_panel(self, parent):
        """Build the application history panel with search and clickable jobs"""
        self.history_card = tk.Frame(parent, bg=COLORS["bg_card"])
        self.history_card.pack(fill="both", expand=True, pady=(10, 0))
        
        self.history_expanded = False  # Start collapsed
        self.history_data = []  # Store loaded job data
        
        # Header
        header = tk.Frame(self.history_card, bg=COLORS["bg_card"])
        header.pack(fill="x", padx=20, pady=(15, 10))
        
        # Left side - title and count
        title_frame = tk.Frame(header, bg=COLORS["bg_card"])
        title_frame.pack(side="left", fill="x", expand=True)
        
        self.history_collapse_btn = tk.Button(header, text="▶", command=self.toggle_history_collapse,
                                             bg=COLORS["bg_card"], fg=COLORS["accent_primary"],
                                             font=("Segoe UI", 12, "bold"), relief="flat",
                                             activebackground=COLORS["bg_card"], cursor="hand2")
        self.history_collapse_btn.pack(side="left", padx=(0, 10))
        
        tk.Label(title_frame, text="📋 Application History", 
                bg=COLORS["bg_card"], fg=COLORS["text_primary"],
                font=FONT_TITLE).pack(side="left")
        
        self.history_count_label = tk.Label(title_frame, text="(0 jobs)", 
                                           bg=COLORS["bg_card"], fg=COLORS["text_muted"],
                                           font=FONT_LABEL)
        self.history_count_label.pack(side="left", padx=(10, 0))
        
        # Refresh button
        self.refresh_btn = tk.Button(header, text="🔄", command=self.load_job_history,
                                    bg=COLORS["bg_card"], fg=COLORS["accent_primary"],
                                    font=("Segoe UI", 12), relief="flat",
                                    activebackground=COLORS["bg_card"], cursor="hand2")
        self.refresh_btn.pack(side="right")
        
        # History content (collapsible)
        self.history_content = tk.Frame(self.history_card, bg=COLORS["bg_card"])
        # Don't pack initially - starts collapsed
        
        # Search bar
        search_frame = tk.Frame(self.history_content, bg=COLORS["bg_card"])
        search_frame.pack(fill="x", padx=20, pady=(0, 10))
        
        tk.Label(search_frame, text="🔍", bg=COLORS["bg_card"], 
                fg=COLORS["text_muted"], font=("Segoe UI", 12)).pack(side="left", padx=(0, 5))
        
        self.history_search = tk.Entry(search_frame, font=FONT_NORMAL, bg=COLORS["bg_input"],
                                      fg=COLORS["text_primary"], insertbackground=COLORS["accent_primary"],
                                      relief="flat", highlightthickness=2,
                                      highlightbackground=COLORS["border"],
                                      highlightcolor=COLORS["accent_primary"])
        self.history_search.pack(side="left", fill="x", expand=True, ipady=6)
        self.history_search.insert(0, "Search jobs...")
        self.history_search.bind("<FocusIn>", self._history_search_focus_in)
        self.history_search.bind("<FocusOut>", self._history_search_focus_out)
        self.history_search.bind("<KeyRelease>", self._filter_history)
        self.history_search.config(fg=COLORS["text_muted"])
        
        # Job list (scrollable)
        list_frame = tk.Frame(self.history_content, bg=COLORS["bg_card"])
        list_frame.pack(fill="both", expand=True, padx=20, pady=(0, 15))
        
        self.history_canvas = tk.Canvas(list_frame, bg=COLORS["bg_dark"], 
                                       highlightthickness=0, height=200)
        history_scrollbar = ttk.Scrollbar(list_frame, orient="vertical", 
                                         command=self.history_canvas.yview)
        self.history_list_frame = tk.Frame(self.history_canvas, bg=COLORS["bg_dark"])
        
        self.history_list_frame.bind("<Configure>", 
            lambda e: self.history_canvas.configure(scrollregion=self.history_canvas.bbox("all")))
        
        self.history_canvas.create_window((0, 0), window=self.history_list_frame, anchor="nw")
        self.history_canvas.configure(yscrollcommand=history_scrollbar.set)
        
        self.history_canvas.pack(side="left", fill="both", expand=True)
        history_scrollbar.pack(side="right", fill="y")
        
        # Bind mousewheel
        self.history_canvas.bind_all("<MouseWheel>", 
            lambda e: self.history_canvas.yview_scroll(int(-1 * (e.delta / 120)), "units"))
        
        # Load initial data
        self.load_job_history()
    
    def _history_search_focus_in(self, event):
        """Clear placeholder on focus"""
        if self.history_search.get() == "Search jobs...":
            self.history_search.delete(0, tk.END)
            self.history_search.config(fg=COLORS["text_primary"])
    
    def _history_search_focus_out(self, event):
        """Restore placeholder if empty"""
        if not self.history_search.get().strip():
            self.history_search.insert(0, "Search jobs...")
            self.history_search.config(fg=COLORS["text_muted"])
    
    def _filter_history(self, event=None):
        """Filter displayed jobs based on search"""
        query = self.history_search.get().strip().lower()
        if query == "search jobs...":
            query = ""
        self._display_jobs(query)
    
    def toggle_history_collapse(self):
        """Toggle history panel collapse"""
        self.history_expanded = not self.history_expanded
        
        if self.history_expanded:
            self.history_collapse_btn.config(text="▼")
            self.history_content.pack(fill="both", expand=True)
            self.load_job_history()  # Refresh when expanding
        else:
            self.history_collapse_btn.config(text="▶")
            self.history_content.pack_forget()
    
    def load_job_history(self):
        """Load job history from job_log.xlsx"""
        self.history_data = []
        
        if not OPENPYXL_AVAILABLE:
            self.history_count_label.config(text="(openpyxl not installed)")
            return
        
        job_log_path = "job_log.xlsx"
        if not os.path.exists(job_log_path):
            self.history_count_label.config(text="(no jobs yet)")
            self._display_jobs()
            return
        
        try:
            wb = openpyxl.load_workbook(job_log_path)
            ws = wb.active
            
            # Skip header row, load all data
            for row in ws.iter_rows(min_row=2, values_only=True):
                if row[0]:  # Has timestamp
                    self.history_data.append({
                        "timestamp": str(row[0]) if row[0] else "",
                        "title": str(row[1]) if row[1] else "Unknown",
                        "company": str(row[2]) if row[2] else "Unknown",
                        "url": str(row[3]) if row[3] else ""
                    })
            
            wb.close()
            
            # Sort by timestamp descending (newest first)
            self.history_data.sort(key=lambda x: x["timestamp"], reverse=True)
            
            self.history_count_label.config(text=f"({len(self.history_data)} jobs)")
            self._display_jobs()
            
        except Exception as e:
            self.history_count_label.config(text=f"(error loading)")
            print(f"Error loading job history: {e}")
    
    def _display_jobs(self, filter_query=""):
        """Display job cards in the history list"""
        # Clear existing items
        for widget in self.history_list_frame.winfo_children():
            widget.destroy()
        
        # Filter jobs
        if filter_query:
            filtered = [j for j in self.history_data 
                       if filter_query in j["title"].lower() or filter_query in j["company"].lower()]
        else:
            filtered = self.history_data
        
        if not filtered:
            no_jobs = tk.Label(self.history_list_frame, text="No jobs found",
                              bg=COLORS["bg_dark"], fg=COLORS["text_muted"],
                              font=FONT_NORMAL)
            no_jobs.pack(pady=20)
            return
        
        # Create job cards
        for job in filtered[:100]:  # Limit to 100 for performance
            self._create_job_card(job)
    
    def _create_job_card(self, job):
        """Create a single job card in the history"""
        card = tk.Frame(self.history_list_frame, bg=COLORS["bg_card"], cursor="hand2")
        card.pack(fill="x", pady=(0, 5), padx=5)
        
        inner = tk.Frame(card, bg=COLORS["bg_card"])
        inner.pack(fill="x", padx=12, pady=10)
        
        # Job title
        title_label = tk.Label(inner, text=f"💼 {job['title'][:50]}",
                              bg=COLORS["bg_card"], fg=COLORS["text_primary"],
                              font=FONT_BOLD, anchor="w")
        title_label.pack(fill="x")
        
        # Company and date
        date_str = job["timestamp"][:10] if len(job["timestamp"]) >= 10 else job["timestamp"]
        info_label = tk.Label(inner, text=f"🏢 {job['company']} • 📅 {date_str}",
                             bg=COLORS["bg_card"], fg=COLORS["text_secondary"],
                             font=FONT_LABEL, anchor="w")
        info_label.pack(fill="x")
        
        # URL link
        if job["url"]:
            url_label = tk.Label(inner, text="🔗 Click to view job",
                                bg=COLORS["bg_card"], fg=COLORS["accent_primary"],
                                font=FONT_LABEL, anchor="w", cursor="hand2")
            url_label.pack(fill="x")
            url_label.bind("<Button-1>", lambda e, url=job["url"]: webbrowser.open(url))
            
            # Hover effects
            def on_enter(e, lbl=url_label):
                lbl.config(fg=COLORS["accent_secondary"])
            def on_leave(e, lbl=url_label):
                lbl.config(fg=COLORS["accent_primary"])
            url_label.bind("<Enter>", on_enter)
            url_label.bind("<Leave>", on_leave)
        
        # Card hover effect
        def card_enter(e, c=card, i=inner, t=title_label, inf=info_label):
            c.config(bg=COLORS["bg_card_hover"])
            i.config(bg=COLORS["bg_card_hover"])
            t.config(bg=COLORS["bg_card_hover"])
            inf.config(bg=COLORS["bg_card_hover"])
        def card_leave(e, c=card, i=inner, t=title_label, inf=info_label):
            c.config(bg=COLORS["bg_card"])
            i.config(bg=COLORS["bg_card"])
            t.config(bg=COLORS["bg_card"])
            inf.config(bg=COLORS["bg_card"])
        
        card.bind("<Enter>", card_enter)
        card.bind("<Leave>", card_leave)
        inner.bind("<Enter>", card_enter)
        inner.bind("<Leave>", card_leave)
        
        # Click anywhere on card to open URL
        if job["url"]:
            card.bind("<Button-1>", lambda e, url=job["url"]: webbrowser.open(url))
            inner.bind("<Button-1>", lambda e, url=job["url"]: webbrowser.open(url))
            title_label.bind("<Button-1>", lambda e, url=job["url"]: webbrowser.open(url))
            info_label.bind("<Button-1>", lambda e, url=job["url"]: webbrowser.open(url))

    # ============================================================
    # FORM HELPERS
    # ============================================================
    def _create_field(self, frame, label, key, default=""):
        tk.Label(frame, text=label, bg=COLORS["bg_card"], 
                fg=COLORS["text_secondary"], font=FONT_LABEL).pack(anchor="w", pady=(10, 5))
        entry = ModernEntry(frame)
        value = self.config.get(key, default)
        if value:
            entry.insert(0, str(value))
        entry.pack(fill="x")
        return entry

    def set_presets(self, titles):
        """Legacy method - now just updates job entry directly (for backward compatibility)"""
        self.job_entry.delete(0, tk.END)
        self.job_entry.insert(0, ", ".join(titles))
        # Also update config
        self.config["JOB_TITLES"] = titles
        save_config(self.config)

    def toggle_theme(self):
        """Toggle between dark and light theme and restart app"""
        global COLORS
        
        if self.current_theme == "dark":
            self.current_theme = "light"
            COLORS = COLORS_LIGHT.copy()
            self.theme_btn.config(text="☀️")
            self.log("INFO", "🌞 Switching to Light theme...")
        else:
            self.current_theme = "dark"
            COLORS = COLORS_DARK.copy()
            self.theme_btn.config(text="🌙")
            self.log("INFO", "🌙 Switching to Dark theme...")
        
        # Save preference
        self.config["THEME"] = self.current_theme
        save_config(self.config)
        
        # Auto-restart the app
        self.log("INFO", "🔄 Restarting app to apply theme...")
        self.root.after(500, self.restart_app)
    
    def restart_app(self):
        """Restart the application"""
        try:
            # Get the current executable or script
            if getattr(sys, 'frozen', False):
                # Running as compiled exe
                executable = sys.executable
                subprocess.Popen([executable])
            else:
                # Running as script
                subprocess.Popen([sys.executable, __file__])
            
            # Close current instance
            self.root.quit()
            self.root.destroy()
        except Exception as e:
            self.log("ERROR", f"Failed to restart: {e}")

    def toggle_gmail_cleanup(self):
        """Toggle Gmail cleanup on/off"""
        current = self.gmail_cleanup_var.get()
        new_state = not current
        self.gmail_cleanup_var.set(new_state)
        
        if new_state:
            self.gmail_btn.config(
                text="📧 GMAIL CLEANUP: ON",
                bg=COLORS["success"],
                fg=COLORS["text_primary"]
            )
            self.log("INFO", "Gmail cleanup enabled")
        else:
            self.gmail_btn.config(
                text="📧 GMAIL CLEANUP: OFF",
                bg=COLORS["bg_input"],
                fg=COLORS["text_secondary"]
            )
            self.log("INFO", "Gmail cleanup disabled")
        
        # Auto-save
        self.save_all_config()
    
    def toggle_notifications(self):
        """Toggle desktop notifications on/off"""
        enabled = self.notifications_var.get()
        self.config["NOTIFICATIONS_ENABLED"] = enabled
        save_config(self.config)
        
        if enabled:
            self.log("SUCCESS", "🔔 Desktop notifications enabled")
            self.send_notification("Notifications Enabled", "You'll be notified when jobs are applied!")
        else:
            self.log("INFO", "🔕 Desktop notifications disabled")

    def on_name_selected(self, event=None):
        """Handle name selection - prompt for custom name if needed"""
        selected = self.full_name_var.get()
        if selected == "Custom...":
            # Prompt for custom name
            custom_name = simpledialog.askstring("Custom Name", "Enter full name:", parent=self.root)
            if custom_name and custom_name.strip():
                self.full_name_var.set(custom_name.strip())
                # Update dropdown values to include the custom name
                current_values = list(self.full_name_dropdown['values'])
                if custom_name.strip() not in current_values:
                    current_values.insert(-1, custom_name.strip())  # Insert before "Custom..."
                    self.full_name_dropdown['values'] = current_values
            else:
                self.full_name_var.set("Ash Williams")  # Default fallback
        self.update_config_status()

    def toggle_api(self):
        current = self.api_entry.cget("show")
        self.api_entry.config(show="" if current == "•" else "•")

    def toggle_captcha_api(self):
        current = self.captcha_api_entry.cget("show")
        self.captcha_api_entry.config(show="" if current == "•" else "•")

    def toggle_twilio_token(self):
        current = self.twilio_token_entry.cget("show")
        self.twilio_token_entry.config(show="" if current == "•" else "•")

    def toggle_whatsapp(self):
        """Toggle WhatsApp notifications on/off"""
        current = self.whatsapp_var.get()
        new_state = not current
        self.whatsapp_var.set(new_state)
        
        if new_state:
            self.whatsapp_btn.config(
                text="📱 WHATSAPP: ON",
                bg=COLORS["success"],
                fg=COLORS["text_primary"]
            )
            self.log("INFO", "📱 WhatsApp notifications ENABLED")
        else:
            self.whatsapp_btn.config(
                text="📱 WHATSAPP: OFF",
                bg=COLORS["bg_input"],
                fg=COLORS["text_secondary"]
            )
            self.log("INFO", "📱 WhatsApp notifications DISABLED")
        
        # Save to config
        self.config["WHATSAPP_NOTIFICATIONS"] = new_state
        save_config(self.config)

    def show_api_help(self):
        """Show a dialog with instructions on how to get an OpenAI API key"""
        help_window = tk.Toplevel(self.root)
        help_window.title("How to Get Your API Key")
        help_window.geometry("500x400")
        help_window.configure(bg=COLORS["bg_dark"])
        help_window.transient(self.root)
        help_window.grab_set()
        
        # Center the window
        help_window.update_idletasks()
        x = (help_window.winfo_screenwidth() // 2) - (500 // 2)
        y = (help_window.winfo_screenheight() // 2) - (400 // 2)
        help_window.geometry(f"+{x}+{y}")
        
        # Main content frame
        content = tk.Frame(help_window, bg=COLORS["bg_card"], padx=25, pady=25)
        content.pack(fill="both", expand=True, padx=15, pady=15)
        
        # Title
        tk.Label(content, text="🔑 How to Get Your OpenAI API Key", 
                bg=COLORS["bg_card"], fg=COLORS["accent_primary"],
                font=FONT_TITLE).pack(anchor="w", pady=(0, 20))
        
        # Instructions
        steps = [
            "1️⃣  Go to platform.openai.com",
            "2️⃣  Sign up or Log in to your account",
            "3️⃣  Click on 'API Keys' in the left sidebar",
            "4️⃣  Click '+ Create new secret key'",
            "5️⃣  Give it a name (e.g., 'SeekMate')",
            "6️⃣  Copy the key and paste it here!",
        ]
        
        for step in steps:
            tk.Label(content, text=step, bg=COLORS["bg_card"], 
                    fg=COLORS["text_primary"], font=FONT_NORMAL,
                    anchor="w").pack(fill="x", pady=5)
        
        # Note about credits
        note_frame = tk.Frame(content, bg=COLORS["bg_input"], padx=15, pady=10)
        note_frame.pack(fill="x", pady=(20, 10))
        tk.Label(note_frame, text="💡 Note: OpenAI gives $5 free credits to new accounts!", 
                bg=COLORS["bg_input"], fg=COLORS["warning"],
                font=FONT_NORMAL).pack()
        tk.Label(note_frame, text="This is enough for thousands of cover letters.", 
                bg=COLORS["bg_input"], fg=COLORS["text_secondary"],
                font=FONT_LABEL).pack()
        
        # Buttons frame
        btn_frame = tk.Frame(content, bg=COLORS["bg_card"])
        btn_frame.pack(fill="x", pady=(20, 0))
        
        def open_openai():
            webbrowser.open("https://platform.openai.com/api-keys")
            
        open_btn = ModernButton(btn_frame, text="🔗 Open OpenAI Platform", 
                               command=open_openai, style="primary", width=200, height=40)
        open_btn.pack(side="left", padx=(0, 10))
        
        close_btn = ModernButton(btn_frame, text="Close", 
                                command=help_window.destroy, style="dark", width=100, height=40)
        close_btn.pack(side="left")

    def save_api(self):
        self.config["OPENAI_API_KEY"] = self.api_entry.get()
        save_config(self.config)
        self.log("SUCCESS", "API Key saved successfully!")

    # ============================================================
    # SILENT AUTO-UPDATE SYSTEM
    # ============================================================
    def manual_update_check(self):
        """Manually trigger update check from button"""
        self.log("INFO", "🔄 Manually checking for updates...")
        self.check_update_btn.set_text("⏳ CHECKING...")
        self.check_update_btn.set_disabled(True)
        
        def reset_button():
            self.check_update_btn.set_text("🔄  CHECK FOR UPDATES")
            self.check_update_btn.set_disabled(False)
        
        # Reset button after 5 seconds
        self.root.after(5000, reset_button)
        
        thread = threading.Thread(target=self._silent_update_thread, daemon=True)
        thread.start()
    
    def check_for_updates_async(self):
        """Check for updates in background thread - SILENT MODE"""
        self.log("INFO", "🔍 Checking for updates...")
        thread = threading.Thread(target=self._silent_update_thread, daemon=True)
        thread.start()
    
    def _silent_update_thread(self):
        """Background thread - silently check, download, and install updates"""
        try:
            update_info = check_for_updates()
            
            if not update_info:
                self.root.after(0, lambda: self.log("INFO", "✓ Update check complete"))
                return
            
            if not update_info.get("update_available"):
                self.root.after(0, lambda: self.log("SUCCESS", f"✓ You have the latest version (v{APP_VERSION})"))
                return
            
            # Update available - start silent download
            latest = update_info['latest_version']
            download_url = update_info.get('download_url')
            
            if not download_url:
                self.root.after(0, lambda: self.log("INFO", f"🆕 New version v{latest} available on GitHub"))
                return
            
            self.root.after(0, lambda: self.log("INFO", f"🔄 Downloading update v{latest}..."))
            self.root.after(0, lambda: self._update_header_status("UPDATING..."))
            
            # Download silently
            temp_file = download_update(download_url, self._silent_progress)
            
            if temp_file:
                self.root.after(0, lambda: self._silent_install(temp_file, latest))
            else:
                self.root.after(0, lambda: self.log("ERROR", "Update download failed"))
                self.root.after(0, lambda: self._update_header_status("IDLE"))
                
        except Exception as e:
            self.root.after(0, lambda: self.log("ERROR", f"Update check failed: {e}"))
    
    def _silent_progress(self, percent):
        """Update log with download progress (throttled)"""
        if int(percent) % 25 == 0:  # Only log at 0%, 25%, 50%, 75%, 100%
            self.root.after(0, lambda p=percent: self.log("INFO", f"⬇️ Downloading... {p:.0f}%"))
    
    def _update_header_status(self, text):
        """Update the header status text"""
        if hasattr(self, 'header_status'):
            color = COLORS["warning"] if "UPDATING" in text else COLORS["text_muted"]
            self.header_status.config(text=text, fg=color)
    
    def _silent_install(self, temp_file, new_version):
        """Silently install the update and restart"""
        self.log("SUCCESS", f"✓ Update v{new_version} downloaded!")
        self.log("INFO", "🔄 Installing update and restarting...")
        
        # Get current executable path
        if not getattr(sys, 'frozen', False):
            # Dev mode - just log
            self.log("INFO", f"[DEV] Update saved to: {temp_file}")
            self._update_header_status("IDLE")
            return
        
        current_exe = sys.executable
        
        if sys.platform == "win32":
            # Windows: Create batch script to replace exe
            update_script = os.path.join(tempfile.gettempdir(), "seekmate_update.bat")
            with open(update_script, 'w') as f:
                f.write(f'''@echo off
timeout /t 2 /nobreak > nul
copy /Y "{temp_file}" "{current_exe}"
start "" "{current_exe}"
del "{temp_file}"
del "%~f0"
''')
            subprocess.Popen(update_script, shell=True, 
                            creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0)
        
        elif sys.platform == "darwin":
            # macOS: Unzip and replace .app bundle
            import zipfile
            
            # Find the .app bundle path (go up from executable inside the bundle)
            # Typical path: /Applications/SeekMate AI.app/Contents/MacOS/SeekMate AI
            app_bundle = current_exe
            while app_bundle and not app_bundle.endswith('.app'):
                app_bundle = os.path.dirname(app_bundle)
            
            if not app_bundle:
                self.log("ERROR", "Could not find .app bundle path")
                self._update_header_status("IDLE")
                return
            
            app_parent = os.path.dirname(app_bundle)
            app_name = os.path.basename(app_bundle)  # e.g., "SeekMate AI.app"
            temp_extract = os.path.join(tempfile.gettempdir(), "seekmate_update_extract")
            
            # Create shell script for macOS that handles zip structure properly
            update_script = os.path.join(tempfile.gettempdir(), "seekmate_update.sh")
            with open(update_script, 'w') as f:
                f.write(f'''#!/bin/bash
sleep 2

# Clean up any previous extract
rm -rf "{temp_extract}"
mkdir -p "{temp_extract}"

# Unzip to temp location
unzip -o "{temp_file}" -d "{temp_extract}"

# Find the .app bundle inside the extracted files
NEW_APP=$(find "{temp_extract}" -name "*.app" -type d -maxdepth 2 | head -1)

if [ -z "$NEW_APP" ]; then
    echo "ERROR: Could not find .app in update package"
    exit 1
fi

# Remove old app and replace with new
rm -rf "{app_bundle}"
mv "$NEW_APP" "{app_bundle}"

# Remove quarantine attribute (allows app to run without Gatekeeper warning)
xattr -rd com.apple.quarantine "{app_bundle}" 2>/dev/null || true

# Open the updated app
open "{app_bundle}"

# Cleanup
rm -rf "{temp_extract}"
rm "{temp_file}"
rm "$0"
''')
            os.chmod(update_script, 0o755)
            subprocess.Popen(["bash", update_script])
        
        else:
            # Linux: Replace binary directly
            update_script = os.path.join(tempfile.gettempdir(), "seekmate_update.sh")
            with open(update_script, 'w') as f:
                f.write(f'''#!/bin/bash
sleep 2
cp "{temp_file}" "{current_exe}"
chmod +x "{current_exe}"
"{current_exe}" &
rm "{temp_file}"
rm "$0"
''')
            os.chmod(update_script, 0o755)
            subprocess.Popen(["bash", update_script])
        
        # Close the app
        self.root.after(500, self.root.quit)

    def update_time_saved(self, num_applications):
        """Update time saved display (2 mins per successful application)"""
        total_mins = num_applications * 2
        if total_mins >= 60:
            hours = total_mins // 60
            mins = total_mins % 60
            time_text = f"{hours}h {mins}m"
        else:
            time_text = f"{total_mins} mins"
        self.time_saved_label.config(text=time_text)

    def update_config_status(self):
        """Update the configuration progress bar and summary"""
        # Check field completion status
        fields_status = {
            "Full Name": bool(self.full_name_var.get().strip() and self.full_name_var.get() != "Custom..."),
            "Location": bool(self.location_var.get().strip()),
            "Job Titles": bool(self.job_entry.get().strip()),
            "Max Jobs": bool(self.max_entry.get().strip()),
            "Expected Salary": bool(self.salary_entry.get().strip()),
            "API Key": bool(self.api_entry.get().strip()),
        }
        
        # Update progress bar
        self.progress_bar.update_progress(fields_status)
        
        # Update config summary
        name = self.full_name_var.get().strip()
        if name == "Custom...":
            name = ""
        self.config_summary.update_item("name", name if name else "—", 
                                        COLORS["text_primary"] if name else COLORS["text_muted"])
        
        location = self.location_var.get().strip()
        location_short = location.split(",")[0] if location else "—"
        self.config_summary.update_item("location", location_short,
                                        COLORS["text_primary"] if location else COLORS["text_muted"])
        
        jobs = self.job_entry.get().strip()
        job_count = len([j for j in jobs.split(",") if j.strip()]) if jobs else 0
        self.config_summary.update_item("jobs", f"{job_count} titles" if job_count else "—",
                                        COLORS["text_primary"] if job_count else COLORS["text_muted"])
        
        max_jobs = self.max_entry.get().strip()
        self.config_summary.update_item("max", max_jobs if max_jobs else "—",
                                        COLORS["text_primary"] if max_jobs else COLORS["text_muted"])
        
        salary = self.salary_entry.get().strip()
        try:
            salary_formatted = f"${int(salary):,}" if salary else "—"
        except:
            salary_formatted = salary if salary else "—"
        self.config_summary.update_item("salary", salary_formatted,
                                        COLORS["money_green"] if salary else COLORS["text_muted"])
        
        # Speed summary based on sliders
        if hasattr(self, 'scan_speed_slider') and hasattr(self, 'apply_speed_slider'):
            avg_speed = (self.scan_speed_slider.get() + self.apply_speed_slider.get()) // 2
            if avg_speed >= 90:
                speed_text, speed_color = "INSANE", COLORS["danger"]
            elif avg_speed >= 70:
                speed_text, speed_color = "FAST", COLORS["warning"]
            elif avg_speed >= 40:
                speed_text, speed_color = "NORMAL", COLORS["accent_primary"]
            else:
                speed_text, speed_color = "SAFE", COLORS["success"]
            self.config_summary.update_item("speed", speed_text, speed_color)

    # ============================================================
    # DESKTOP NOTIFICATIONS
    # ============================================================
    def send_notification(self, title, message, timeout=5):
        """Send a desktop notification"""
        if not NOTIFICATIONS_AVAILABLE:
            return
        
        # Check if notifications are enabled
        if not self.config.get("NOTIFICATIONS_ENABLED", True):
            return
        
        try:
            notification.notify(
                title=title,
                message=message,
                app_name="SeekMate AI",
                timeout=timeout
            )
        except Exception as e:
            print(f"Notification error: {e}")

    # ============================================================
    # LOGGING SYSTEM
    # ============================================================
    def log(self, level, message):
        timestamp = time.strftime("[%H:%M:%S]")
        
        # Check if this is a GPT-related message
        is_gpt_message = any(keyword in message.lower() for keyword in [
            "gpt", "chatgpt", "asking gpt", "gpt answered", "gpt selected", 
            "gpt fix", "using gpt", "ai", "validation errors detected"
        ])
        
        # Insert timestamp with muted color
        self.console.insert(tk.END, f"{timestamp} ", "timestamp")
        
        # Insert level and message with appropriate color
        level_text = f"{level.upper()}: "
        
        if is_gpt_message:
            # Use vibrant GPT color for the entire line
            self.console.insert(tk.END, "🤖 ", "GPT")
            self.console.insert(tk.END, level_text, "GPT")
        else:
            self.console.insert(tk.END, level_text, level.upper())
        
        # Check for URLs in the message and make them clickable
        url_pattern = r'(https?://[^\s]+)'
        parts = re.split(url_pattern, message)
        
        for part in parts:
            if re.match(url_pattern, part):
                # This is a URL - make it clickable
                link_tag = f"link_{len(self.link_urls)}"
                self.link_urls[link_tag] = part
                start_index = self.console.index(tk.END)
                self.console.insert(tk.END, part, ("link", link_tag))
            else:
                # Regular text - use GPT color if it's a GPT message
                if is_gpt_message:
                    self.console.insert(tk.END, part, "GPT")
                else:
                    self.console.insert(tk.END, part)

        self.console.insert(tk.END, "\n")
        self.console.see(tk.END)
        
        # Update line count (every 10 logs to avoid slowdown)
        try:
            line_count = int(self.console.index('end-1c').split('.')[0])
            if line_count % 10 == 0:
                self.update_log_count()
        except:
            pass

    def apply_filter(self):
        keyword = self.filter_var.get().strip().lower()
        if keyword == "filter...":
            return
        content = self.console.get("1.0", tk.END)
        self.console.delete("1.0", tk.END)
        for line in content.splitlines():
            if keyword in line.lower():
                self.console.insert(tk.END, line + "\n")

    def toggle_wrap(self):
        self.wrap_enabled = not self.wrap_enabled
        self.console.config(wrap="word" if self.wrap_enabled else "none")
        self.wrap_btn.config(
            bg=COLORS["accent_primary"] if self.wrap_enabled else COLORS["bg_input"],
            fg="#000000" if self.wrap_enabled else COLORS["text_secondary"]
        )

    def clear_log(self):
        self.console.delete("1.0", tk.END)
        self.link_urls = {}  # Reset link tracking
        self.update_log_count()

    # ============================================================
    # MONEY COUNTER / TIMER
    # ============================================================
    def update_timer(self):
        if self.timer_running and self.start_time:
            elapsed = int(time.time() - self.start_time)
            hours = elapsed // 3600
            minutes = (elapsed % 3600) // 60
            seconds = elapsed % 60
            time_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
            self.header_timer.config(text=time_str)
            self.time_display.config(text=time_str)
        self.root.after(1000, self.update_timer)

    def money_loop(self):
        if self.money_running and not self.paused:
            self.money_saved += 2 / 60  # $2 per minute
            money_str = f"${self.money_saved:,.2f}"
            self.money_label.config(text=money_str)
        self.root.after(1000, self.money_loop)

    # ============================================================
    # BOT CONTROL
    # ============================================================
    def show_chrome_required(self):
        """Show a dialog prompting user to install Chrome"""
        chrome_window = tk.Toplevel(self.root)
        chrome_window.title("Chrome Required")
        chrome_window.geometry("450x280")
        chrome_window.configure(bg=COLORS["bg_dark"])
        chrome_window.transient(self.root)
        chrome_window.grab_set()
        
        # Center the window
        chrome_window.update_idletasks()
        x = (chrome_window.winfo_screenwidth() // 2) - (450 // 2)
        y = (chrome_window.winfo_screenheight() // 2) - (280 // 2)
        chrome_window.geometry(f"+{x}+{y}")
        
        # Main content frame
        content = tk.Frame(chrome_window, bg=COLORS["bg_card"], padx=25, pady=25)
        content.pack(fill="both", expand=True, padx=15, pady=15)
        
        # Warning icon and title
        tk.Label(content, text="⚠️ Google Chrome Required", 
                bg=COLORS["bg_card"], fg=COLORS["warning"],
                font=FONT_TITLE).pack(pady=(0, 15))
        
        # Message
        tk.Label(content, text="SeekMate AI uses Chrome for automation.", 
                bg=COLORS["bg_card"], fg=COLORS["text_primary"],
                font=FONT_NORMAL).pack(pady=5)
        tk.Label(content, text="Please install Google Chrome to continue.", 
                bg=COLORS["bg_card"], fg=COLORS["text_secondary"],
                font=FONT_NORMAL).pack(pady=5)
        
        # Buttons frame
        btn_frame = tk.Frame(content, bg=COLORS["bg_card"])
        btn_frame.pack(pady=(25, 0))
        
        def download_chrome():
            webbrowser.open(get_chrome_download_url())
            chrome_window.destroy()
            
        download_btn = ModernButton(btn_frame, text="📥 Download Chrome", 
                                   command=download_chrome, style="primary", width=180, height=45)
        download_btn.pack(side="left", padx=(0, 10))
        
        cancel_btn = ModernButton(btn_frame, text="Cancel", 
                                 command=chrome_window.destroy, style="dark", width=100, height=45)
        cancel_btn.pack(side="left")

    def start_bot(self):
        # Check if Chrome is installed first
        if not is_chrome_installed():
            self.show_chrome_required()
            self.log("ERROR", "Google Chrome is not installed. Please install Chrome to use SeekMate AI.")
            return
        
        # Kill any existing bot processes first
        self._kill_existing_processes()
        
        # Reset control flags BEFORE starting
        write_control(pause=False, stop=False)
        time.sleep(0.5)  # Small delay to ensure control.json is written
        
        self.save_all_config()
        self.console.delete("1.0", tk.END)
        self.money_saved = 0.0
        self.money_label.config(text="$0.00")

        self.start_btn.set_text("RUNNING...")
        self.start_btn.set_disabled(True)
        self.status_indicator.set_status("running")
        self.header_status.config(text="RUNNING", fg=COLORS["success"])

        self.start_time = time.time()
        self.timer_running = True
        self.money_running = True

        self.update_timer()
        self.money_loop()

        # Clear previous log file
        if os.path.exists(LOG_FILE):
            os.remove(LOG_FILE)

        # Check which platforms are enabled
        use_seek = self.seek_var.get()
        use_indeed = self.indeed_var.get()
        
        if not use_seek and not use_indeed:
            self.log("ERROR", "No platforms selected! Please enable SEEK or Indeed.")
            self.start_btn.set_text("▶  START")
            self.start_btn.set_disabled(False)
            return
        
        try:
            # Check if running as bundled exe or from source
            is_bundled = getattr(sys, 'frozen', False)
            
            # Check if this is an instance-specific config (multi-bot mode)
            is_instance_config = "bot_instances" in CONFIG_FILE or "_config.json" in CONFIG_FILE
            instance_env = {}
            if is_instance_config:
                # Extract instance name from config file path
                config_name = os.path.basename(CONFIG_FILE).replace("_config.json", "").replace("config.json", "")
                script_dir = os.path.dirname(os.path.abspath(__file__))
                instance_env = {
                    "BOT_CONFIG_FILE": os.path.abspath(CONFIG_FILE),
                    "BOT_CONTROL_FILE": os.path.join(script_dir, f"control_{config_name}.json"),
                    "BOT_CHROME_PROFILE": f"chrome_profile_{config_name}",
                    "BOT_LOG_FILE": os.path.join(script_dir, f"log_{config_name}.txt"),
                    "BOT_INSTANCE_NAME": config_name
                }
                self.log("INFO", f"🔧 Multi-bot instance mode: {config_name}")
            
            # Start SEEK bot if enabled
            if use_seek:
                self.log("INFO", "🔵 Starting SEEK bot...")
                if is_bundled:
                    self.bot_thread_stop = False
                    def run_seek_thread():
                        try:
                            # Set environment variables for instance if needed
                            if instance_env:
                                for key, value in instance_env.items():
                                    os.environ[key] = value
                            import main as bot_module
                            bot_module.main()
                        except Exception as e:
                            self.log("ERROR", f"SEEK bot error: {e}")
                    self.bot_thread = threading.Thread(target=run_seek_thread, daemon=True)
                    self.bot_thread.start()
                else:
                    # Create environment with instance variables
                    env = os.environ.copy()
                    env.update(instance_env)
                    self.bot_process = subprocess.Popen(
                        [sys.executable, "main.py"],
                        env=env,
                        creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
                    )
            
            # Start Indeed bot if enabled (runs separately)
            if use_indeed:
                self.log("INFO", "🟣 Starting Indeed bot...")
                if is_bundled:
                    def run_indeed_thread():
                        try:
                            # Set environment variables for instance if needed
                            if instance_env:
                                for key, value in instance_env.items():
                                    os.environ[key] = value
                            import indeed_bot
                            indeed_bot.main()
                        except Exception as e:
                            self.log("ERROR", f"Indeed bot error: {e}")
                    self.indeed_thread = threading.Thread(target=run_indeed_thread, daemon=True)
                    self.indeed_thread.start()
                else:
                    # Create environment with instance variables
                    env = os.environ.copy()
                    env.update(instance_env)
                    self.indeed_process = subprocess.Popen(
                        [sys.executable, "indeed_bot.py"],
                        env=env,
                        creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
                    )
            
            threading.Thread(target=self.tail_log, daemon=True).start()
            
            platforms = []
            if use_seek:
                platforms.append("SEEK")
            if use_indeed:
                platforms.append("Indeed")
            self.log("INFO", f"Bot(s) started: {', '.join(platforms)}")
        except Exception as e:
            self.log("ERROR", f"Bot failed to start: {e}")

    def start_recommended(self):
        """Start bot in Recommended Jobs mode - applies to 100 recommended jobs regardless of location"""
        # Check if Chrome is installed first
        if not is_chrome_installed():
            self.show_chrome_required()
            self.log("ERROR", "Google Chrome is not installed. Please install Chrome to use SeekMate AI.")
            return
        
        # Kill any existing bot processes first
        self._kill_existing_processes()
        
        # Reset control flags BEFORE starting
        write_control(pause=False, stop=False, recommended=True)
        time.sleep(0.5)  # Small delay to ensure control.json is written
        
        # Save current config first
        self.save_all_config()
        
        # Temporarily set MAX_JOBS to 100 for this session
        config = load_config()
        original_max = config.get("MAX_JOBS", 10)
        config["MAX_JOBS"] = 100
        save_config(config)
        
        self.console.delete("1.0", tk.END)
        self.money_saved = 0.0
        self.money_label.config(text="$0.00")

        self.start_btn.set_text("RUNNING...")
        self.start_btn.set_disabled(True)
        self.recommended_btn.set_text("APPLYING...")
        self.recommended_btn.set_disabled(True)
        self.status_indicator.set_status("running")
        self.header_status.config(text="RECOMMENDED", fg=COLORS["accent_primary"])

        self.start_time = time.time()
        self.timer_running = True
        self.money_running = True

        self.update_timer()
        self.money_loop()

        # Clear previous log file
        if os.path.exists(LOG_FILE):
            os.remove(LOG_FILE)

        self.log("INFO", "🎯 Starting RECOMMENDED JOBS mode - 100 applications, any location!")

        try:
            # Check if running as bundled exe or from source
            is_bundled = getattr(sys, 'frozen', False)
            
            if is_bundled:
                # Running as exe - run bot in thread
                self.log("INFO", "Starting bot (bundled mode)...")
                self.bot_thread_stop = False
                
                def run_bot_thread():
                    try:
                        import main as bot_module
                        bot_module.main()
                    except Exception as e:
                        self.log("ERROR", f"Bot error: {e}")
                
                self.bot_thread = threading.Thread(target=run_bot_thread, daemon=True)
                self.bot_thread.start()
            else:
                # Running from source - use subprocess
                self.bot_process = subprocess.Popen(
                    [sys.executable, "main.py"],
                    creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
                )
            
            threading.Thread(target=self.tail_log, daemon=True).start()
            self.log("INFO", "Bot started successfully in RECOMMENDED mode.")
        except Exception as e:
            self.log("ERROR", f"Bot failed to start: {e}")

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

    def _kill_existing_processes(self):
        """Kill any existing bot processes before starting a new one"""
        # Terminate the bot process (source mode)
        try:
            if hasattr(self, "bot_process") and self.bot_process:
                try:
                    self.bot_process.terminate()
                    self.bot_process.wait(timeout=2)
                except:
                    self.bot_process.kill()
                self.bot_process = None
        except Exception:
            pass
        
        # Stop bot thread if running in bundled mode
        if hasattr(self, "bot_thread_stop"):
            self.bot_thread_stop = True
        
        # Kill Indeed process if exists
        try:
            if hasattr(self, "indeed_process") and self.indeed_process:
                try:
                    self.indeed_process.terminate()
                    self.indeed_process.wait(timeout=2)
                except:
                    self.indeed_process.kill()
                self.indeed_process = None
        except Exception:
            pass

    def stop_bot(self):
        write_control(stop=True, recommended=False)
        self.paused = False
        self.timer_running = False
        self.money_running = False

        self.start_btn.set_text("▶  START")
        self.start_btn.set_disabled(False)
        self.recommended_btn.set_text("🎯 RECOMMENDED")
        self.recommended_btn.set_disabled(False)
        self.pause_btn.set_text("⏸  PAUSE")
        self.status_indicator.set_status("stopped")
        self.header_status.config(text="STOPPED", fg=COLORS["danger"])

        self.log("INFO", "Stop signal sent...")

        # Kill existing processes
        self._kill_existing_processes()
        
        # Force kill any remaining Chrome processes from our profile
        try:
            if sys.platform == "win32":
                # Kill Chrome processes that might be using our profile
                subprocess.run(
                    ["taskkill", "/F", "/IM", "chrome.exe", "/FI", "WINDOWTITLE eq SeekMate*"],
                    capture_output=True,
                    timeout=5
                )
                # Also try to kill chromedriver
                subprocess.run(
                    ["taskkill", "/F", "/IM", "chromedriver.exe"],
                    capture_output=True,
                    timeout=5
                )
            self.log("SUCCESS", "Chrome closed.")
        except Exception as e:
            self.log("INFO", "Chrome may need to be closed manually.")

    # ============================================================
    # LOG TAILING
    # ============================================================
    def tail_log(self):
        # Wait for log file to be created by bot
        while not os.path.exists(LOG_FILE):
            time.sleep(0.2)

        with open(LOG_FILE, "r", encoding="utf-8") as f:
            f.seek(0)
            while True:
                line = f.readline()
                if not line:
                    time.sleep(0.1)
                    continue

                clean = line.strip()
                if "ERROR" in clean.upper():
                    self.log("ERROR", clean)
                elif "SUCCESS" in clean.upper():
                    self.log("SUCCESS", clean)
                else:
                    self.log("INFO", clean)

                if "Successful submissions:" in clean:
                    try:
                        num = int(clean.split(":")[-1].strip())
                        self.counter_label.config(text=str(num))
                        # Update time saved (2 mins per application)
                        self.update_time_saved(num)
                        # Notification sounds removed per user request
                    except:
                        pass

    # ============================================================
    # SYSTEM TEST
    # ============================================================
    def run_test(self):
        self.log("INFO", "Running system test...")
        
        if not self.api_entry.get().strip():
            self.log("ERROR", "API Key missing.")
        else:
            self.log("SUCCESS", "API Key present.")

        try:
            webbrowser.open("https://www.seek.com.au", new=0)
            self.log("SUCCESS", "SEEK website reachable.")
        except:
            self.log("ERROR", "Could not reach SEEK website.")

        try:
            import main
            self.log("SUCCESS", "main.py imported successfully.")
        except Exception as e:
            self.log("ERROR", f"main.py failed to import: {e}")

    # ============================================================
    # SAVE CONFIG
    # ============================================================
    def save_all_config(self):
        """Save ALL settings to config.json"""
        # Personal Info
        name = self.full_name_var.get().strip()
        if name and name != "Custom...":
            self.config["FULL_NAME"] = name
        self.config["LOCATION"] = self.location_var.get().strip()

        # Speed settings
        self.config["SCAN_SPEED"] = self.scan_speed_slider.get()
        self.config["APPLY_SPEED"] = self.apply_speed_slider.get()
        self.config["COOLDOWN_DELAY"] = self.cooldown_slider.get()
        self.config["STEALTH_MODE"] = self.stealth_var.get()
        self.config["GPT_JOB_CHECK"] = self.gpt_mode_var.get()
        self.config["MODE_24_7"] = self.mode_24_7_var.get()

        # Job settings
        self.config["JOB_TITLES"] = [
            j.strip() for j in self.job_entry.get().split(",") if j.strip()
        ]

        try:
            self.config["MAX_JOBS"] = int(self.max_entry.get().strip())
        except:
            self.config["MAX_JOBS"] = 100
            
        try:
            self.config["EXPECTED_SALARY"] = int(self.salary_entry.get().strip())
        except:
            self.config["EXPECTED_SALARY"] = 100000

        # Blocklist
        self.config["BLOCKED_COMPANIES"] = [
            c.strip() for c in self.blocked_companies_entry.get().split(",") if c.strip()
        ]
        self.config["BLOCKED_TITLES"] = [
            t.strip() for t in self.blocked_titles_entry.get().split(",") if t.strip()
        ]

        # API & Notifications
        self.config["OPENAI_API_KEY"] = self.api_entry.get().strip()
        self.config["TWOCAPTCHA_API_KEY"] = self.captcha_api_entry.get().strip()
        self.config["NOTIFICATIONS_ENABLED"] = self.notifications_var.get()
        
        # Twilio WhatsApp settings
        if hasattr(self, 'twilio_sid_entry'):
            self.config["TWILIO_ACCOUNT_SID"] = self.twilio_sid_entry.get().strip()
        if hasattr(self, 'twilio_token_entry'):
            self.config["TWILIO_AUTH_TOKEN"] = self.twilio_token_entry.get().strip()
        if hasattr(self, 'twilio_from_entry'):
            self.config["TWILIO_WHATSAPP_FROM"] = self.twilio_from_entry.get().strip()
        if hasattr(self, 'whatsapp_var'):
            self.config["WHATSAPP_NOTIFICATIONS"] = self.whatsapp_var.get()
        
        # Platform selections
        self.config["USE_SEEK"] = self.seek_var.get()
        self.config["USE_INDEED"] = self.indeed_var.get()
        
        # Gmail cleanup setting
        if hasattr(self, 'gmail_cleanup_var'):
            self.config["USE_GMAIL_CLEANUP"] = self.gmail_cleanup_var.get()
        
        # Theme preference (already saved elsewhere, but ensure consistency)
        self.config["THEME"] = getattr(self, 'current_theme', 'dark')

        save_config(self.config)
        self.log("INFO", "💾 All settings saved!")

    def update_settings(self):
        try:
            self.save_all_config()
            self.log("SUCCESS", "Settings saved to config.json!")
        except Exception as e:
            self.log("ERROR", f"Failed to save settings: {e}")


# ============================================================
# MAIN
# ============================================================
def load_theme_on_startup():
    """Load the saved theme preference and apply it"""
    global COLORS
    try:
        config = load_config()
        saved_theme = config.get("THEME", "dark")
        if saved_theme == "light":
            COLORS.update(COLORS_LIGHT)
        else:
            COLORS.update(COLORS_DARK)
    except:
        pass  # Use default dark theme

def main():
    # Load theme before creating UI
    load_theme_on_startup()
    
    root = tk.Tk()
    
    # Set app icon if available
    try:
        if os.path.exists("seekmate_logo.png"):
            icon = tk.PhotoImage(file="seekmate_logo.png")
            root.iconphoto(True, icon)
    except:
        pass
    
    app = SeekMateGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
