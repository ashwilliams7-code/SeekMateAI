import tkinter as tk
from tkinter import ttk, messagebox
import subprocess
import sys
import json
import os
import re
import threading
from datetime import datetime, timedelta

# Run from script directory so launcher and config paths work
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if os.getcwd() != SCRIPT_DIR:
    os.chdir(SCRIPT_DIR)

INSTANCES_FILE = os.path.join(SCRIPT_DIR, "bot_instances.json")

def _apply_dark_style(root):
    style = ttk.Style(root)
    style.theme_use("clam")
    style.configure("Treeview", background="#252530", foreground="#e0e0e0", fieldbackground="#252530",
                    rowheight=28, font=("Segoe UI", 10))
    style.configure("Treeview.Heading", background="#2d2d3a", foreground="#fff", font=("Segoe UI", 10, "bold"))
    style.map("Treeview", background=[("selected", "#1e3a5f")], foreground=[("selected", "#fff")])
    style.map("Treeview.Heading", background=[("active", "#3d3d4a")])
    style.configure("Vertical.TScrollbar", background="#2d2d3a", troughcolor="#1a1a2e")

class MultiBotGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("SeekMateAI — Dashboard")
        self.root.geometry("1600x840")
        self.root.minsize(1000, 620)
        self.root.configure(bg="#1a1a2e")
        
        self.selected_instance_for_log = None
        self.log_tail_lines = 100
        
        _apply_dark_style(root)
        self.load_instances()
        self.create_ui()
        self.refresh_list()
        
        self.auto_refresh_running = True
        self.auto_refresh()
        self.log_preview_running = True
        self.schedule_log_preview()
        
        self.start_whatsapp_scheduler()
        
        self.root.bind("<F5>", lambda e: self.refresh_list())
        self.root.bind("<Control-r>", lambda e: self.refresh_list())
    
    def load_instances(self):
        if os.path.exists(INSTANCES_FILE):
            try:
                with open(INSTANCES_FILE, "r", encoding="utf-8") as f:
                    self.instances = json.load(f)
            except Exception:
                self.instances = {}
        else:
            self.instances = {}
    
    def check_process_alive(self, pid):
        """Check if a process with given PID is still running"""
        if not pid:
            return False
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            handle = kernel32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
            if handle:
                exit_code = ctypes.c_ulong()
                kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code))
                kernel32.CloseHandle(handle)
                return exit_code.value == 259  # STILL_ACTIVE
            return False
        except Exception:
            return False

    def create_ui(self):
        # ----- Top: Summary bar -----
        summary_frame = tk.Frame(self.root, bg="#1a1a2e", height=48)
        summary_frame.pack(fill=tk.X, side=tk.TOP)
        summary_frame.pack_propagate(False)
        
        self.summary_label = tk.Label(
            summary_frame, text="—", font=("Segoe UI", 11), fg="#eee", bg="#1a1a2e"
        )
        self.summary_label.pack(side=tk.LEFT, padx=16, pady=10)
        
        self.updated_label = tk.Label(
            summary_frame, text="", font=("Segoe UI", 9), fg="#666", bg="#1a1a2e"
        )
        self.updated_label.pack(side=tk.RIGHT, padx=8, pady=10)
        
        tk.Label(summary_frame, text="SeekMateAI Dashboard", font=("Segoe UI", 12, "bold"),
                 fg="#aaa", bg="#1a1a2e").pack(side=tk.RIGHT, padx=16, pady=10)
        
        # ----- Toolbar -----
        toolbar = tk.Frame(self.root, pady=8, padx=12, bg="#1a1a2e")
        toolbar.pack(fill=tk.X)
        
        tk.Button(toolbar, text="➕ Add instance", command=self.add_instance,
                  width=14, bg="#2e7d32", fg="white", font=("Segoe UI", 10),
                  relief=tk.FLAT, cursor="hand2").pack(side=tk.LEFT, padx=4)
        tk.Button(toolbar, text="▶ Start all", command=self.start_all,
                  width=12, bg="#1565c0", fg="white", font=("Segoe UI", 10),
                  relief=tk.FLAT, cursor="hand2").pack(side=tk.LEFT, padx=4)
        tk.Button(toolbar, text="⏹ Stop all", command=self.stop_all,
                  width=12, bg="#c62828", fg="white", font=("Segoe UI", 10),
                  relief=tk.FLAT, cursor="hand2").pack(side=tk.LEFT, padx=4)
        tk.Button(toolbar, text="🔄 Refresh", command=self.refresh_list,
                  width=10, font=("Segoe UI", 10), relief=tk.FLAT,
                  cursor="hand2").pack(side=tk.LEFT, padx=4)
        tk.Button(toolbar, text="💬 Slack", command=self.open_slack_settings,
                  width=10, font=("Segoe UI", 10), relief=tk.FLAT, cursor="hand2",
                  bg="#611f69", fg="white").pack(side=tk.LEFT, padx=4)
        tk.Button(toolbar, text="🔄 Restart crashed", command=self.restart_crashed,
                  width=16, font=("Segoe UI", 10), relief=tk.FLAT, cursor="hand2",
                  bg="#e65100", fg="white").pack(side=tk.LEFT, padx=4)

        # ----- Main content: paned (table left, log right) -----
        paned = tk.PanedWindow(self.root, orient=tk.HORIZONTAL, sashwidth=6, bg="#333")
        paned.pack(fill=tk.BOTH, expand=True, padx=12, pady=(0, 8))
        
        # ----- Left: Instance table -----
        left_frame = tk.Frame(paned, bg="#1a1a2e")
        paned.add(left_frame, minsize=440)
        
        table_frame = tk.Frame(left_frame, bg="#252530", padx=2, pady=2)
        table_frame.pack(fill=tk.BOTH, expand=True)
        
        columns = ("Name", "Status", "API", "Scanned", "Jobs", "Time", "Jobs/Hr", "Last log")
        self.tree = ttk.Treeview(table_frame, columns=columns, show="headings", height=16, selectmode="browse")
        self.tree.tag_configure("running", background="#1b2e1b")
        self.tree.tag_configure("stopped", background="#252530")
        self.tree.tag_configure("crashed", background="#3e1b1b")

        for col in columns:
            self.tree.heading(col, text=col)
            w = 100 if col == "Name" else (78 if col in ("Status", "Scanned", "Jobs", "Time", "Jobs/Hr") else (40 if col == "API" else 220))
            self.tree.column(col, width=w)
        
        tree_scroll = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=tree_scroll.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tree_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.bind("<<TreeviewSelect>>", self._on_select_instance)
        self.tree.bind("<Double-1>", self._on_double_click_row)
        
        # Action row under table
        action_frame = tk.Frame(left_frame, pady=6, bg="#1a1a2e")
        action_frame.pack(fill=tk.X)
        
        tk.Button(action_frame, text="▶ Start", command=self.start_selected,
                  width=10, bg="#2e7d32", fg="white", font=("Segoe UI", 9),
                  relief=tk.FLAT, cursor="hand2").pack(side=tk.LEFT, padx=2)
        tk.Button(action_frame, text="⏹ Stop", command=self.stop_selected,
                  width=10, bg="#c62828", fg="white", font=("Segoe UI", 9),
                  relief=tk.FLAT, cursor="hand2").pack(side=tk.LEFT, padx=2)
        tk.Button(action_frame, text="📋 Log", command=self.view_log,
                  width=8, font=("Segoe UI", 9), relief=tk.FLAT,
                  cursor="hand2").pack(side=tk.LEFT, padx=2)
        tk.Button(action_frame, text="⚙ Config", command=self.open_config,
                  width=8, font=("Segoe UI", 9), relief=tk.FLAT, cursor="hand2",
                  bg="#e65100", fg="white").pack(side=tk.LEFT, padx=2)
        tk.Button(action_frame, text="🗑 Remove", command=self.remove_selected,
                  width=8, font=("Segoe UI", 9), relief=tk.FLAT,
                  cursor="hand2").pack(side=tk.LEFT, padx=2)
        
        # ----- Right: Log preview -----
        right_frame = tk.Frame(paned, bg="#1e1e1e")
        paned.add(right_frame, minsize=380)
        
        log_header = tk.Frame(right_frame, bg="#2d2d2d", height=36)
        log_header.pack(fill=tk.X)
        log_header.pack_propagate(False)
        self.log_preview_title = tk.Label(
            log_header, text="Log preview — select an instance",
            font=("Segoe UI", 10), fg="#bbb", bg="#2d2d2d"
        )
        self.log_preview_title.pack(side=tk.LEFT, padx=12, pady=8)
        
        log_btn_frame = tk.Frame(log_header, bg="#2d2d2d")
        log_btn_frame.pack(side=tk.RIGHT, padx=8, pady=4)
        tk.Button(log_btn_frame, text="Open full log", command=self.view_log,
                  font=("Segoe UI", 9), fg="#90caf9", bg="#2d2d2d", relief=tk.FLAT,
                  cursor="hand2").pack(side=tk.RIGHT, padx=4)
        
        self.log_text = tk.Text(
            right_frame, wrap=tk.WORD, font=("Consolas", 10), bg="#1e1e1e", fg="#d4d4d4",
            insertbackground="#d4d4d4", relief=tk.FLAT, padx=10, pady=10
        )
        self.log_text.tag_configure("error", foreground="#f48771")
        self.log_text.tag_configure("warn", foreground="#dcdcaa")
        log_scroll = ttk.Scrollbar(right_frame, orient=tk.VERTICAL, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=log_scroll.set)
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        log_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        
        # ----- Status bar -----
        status_frame = tk.Frame(self.root, bg="#16161d", height=24)
        status_frame.pack(fill=tk.X, side=tk.BOTTOM)
        status_frame.pack_propagate(False)
        tk.Label(status_frame, text=" F5 Refresh  ·  Double-click: Config  ·  Slack: Live job notifications",
                 font=("Segoe UI", 9), fg="#666", bg="#16161d").pack(side=tk.LEFT, padx=12, pady=4)
    
    def _on_select_instance(self, event):
        sel = self.tree.selection()
        if sel:
            item = self.tree.item(sel[0])
            self.selected_instance_for_log = item["values"][0] if item["values"] else None
        else:
            self.selected_instance_for_log = None
        self.update_log_preview_title()
        self.update_log_preview()
    
    def _on_double_click_row(self, event):
        sel = self.tree.selection()
        if sel:
            self.open_config()
    
    def update_log_preview_title(self):
        if self.selected_instance_for_log:
            self.log_preview_title.config(
                text=f"Log: {self.selected_instance_for_log}",
                fg="#fff"
            )
        else:
            self.log_preview_title.config(
                text="Log preview — select an instance",
                fg="#bbb"
            )
    
    def get_log_path_for_instance(self, name):
        if name not in self.instances:
            return None
        path = self.instances[name].get("log_file", os.path.join(SCRIPT_DIR, f"log_{name}.txt"))
        return path if os.path.isabs(path) else os.path.join(SCRIPT_DIR, path)
    
    def update_log_preview(self):
        if not self.selected_instance_for_log:
            self.log_text.delete("1.0", tk.END)
            self.log_text.insert(tk.END, "Select an instance to see its log here.")
            return
        path = self.get_log_path_for_instance(self.selected_instance_for_log)
        if not path or not os.path.exists(path):
            self.log_text.delete("1.0", tk.END)
            self.log_text.insert(tk.END, f"No log file yet for '{self.selected_instance_for_log}'.")
            return
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()
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
            self.log_text.see(tk.END)
        except Exception:
            self.log_text.delete("1.0", tk.END)
            self.log_text.insert(tk.END, "Could not read log file.")
    
    def schedule_log_preview(self):
        if getattr(self, "log_preview_running", True):
            self.update_log_preview()
            self.root.after(2000, self.schedule_log_preview)
    
    def update_summary(self):
        total = len(self.instances)
        running = sum(1 for i in self.instances.values() if i.get("status") == "running")
        crashed = sum(1 for i in self.instances.values() if i.get("status") == "crashed")
        total_jobs = 0
        total_scanned = 0
        for name, info in self.instances.items():
            log_path = info.get("log_file", os.path.join(SCRIPT_DIR, f"log_{name}.txt"))
            if not os.path.isabs(log_path):
                log_path = os.path.join(SCRIPT_DIR, log_path)
            total_jobs += int(self.get_jobs_applied(log_path) or 0)
            total_scanned += int(self.get_jobs_scanned(log_path) or 0)
        crashed_text = f"  ·  {crashed} crashed" if crashed else ""
        self.summary_label.config(
            text=f"  {total} instance(s)  ·  {running} running{crashed_text}  ·  {total_scanned} scanned  ·  {total_jobs} applied"
        )
        self.updated_label.config(text=f"Updated {datetime.now().strftime('%H:%M:%S')}")
    
    def add_instance(self):
        """Open dialog to add new instance"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Add Bot Instance")
        dialog.geometry("450x250")
        dialog.transient(self.root)
        dialog.grab_set()
        
        # Center the dialog
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() // 2) - (450 // 2)
        y = (dialog.winfo_screenheight() // 2) - (250 // 2)
        dialog.geometry(f"450x250+{x}+{y}")
        
        tk.Label(dialog, text="Instance Name:", font=("Arial", 10)).pack(pady=5)
        name_entry = tk.Entry(dialog, width=50, font=("Arial", 10))
        name_entry.pack(pady=5)
        name_entry.focus()
        
        tk.Label(dialog, text="SEEK Email:", font=("Arial", 10)).pack(pady=5)
        email_entry = tk.Entry(dialog, width=50, font=("Arial", 10))
        email_entry.pack(pady=5)
        
        tk.Label(dialog, text="Full Name:", font=("Arial", 10)).pack(pady=5)
        fullname_entry = tk.Entry(dialog, width=50, font=("Arial", 10))
        fullname_entry.pack(pady=5)
        
        def save():
            name = name_entry.get().strip()
            email = email_entry.get().strip()
            fullname = fullname_entry.get().strip()
            
            if not name:
                messagebox.showerror("Error", "Instance name is required!")
                return
            
            # Call launcher script
            cmd = [sys.executable, "multi_bot_launcher.py", "add", name]
            if email:
                cmd.extend(["--email", email])
            if fullname:
                cmd.extend(["--name", fullname])
            
            try:
                result = subprocess.run(
                    cmd, capture_output=True, text=True, timeout=10, cwd=SCRIPT_DIR,
                )
                if "✅" in result.stdout or result.returncode == 0:
                    messagebox.showinfo("Success", f"Instance '{name}' added.")
                    self.load_instances()
                    self.refresh_list()
                    dialog.destroy()
                else:
                    error_msg = result.stdout + result.stderr
                    messagebox.showerror("Error", f"Failed to add instance:\n{error_msg}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to add instance: {e}")
        
        btn_frame = tk.Frame(dialog)
        btn_frame.pack(pady=15)
        tk.Button(btn_frame, text="Add", command=save, width=15, 
                 bg="#4CAF50", fg="white", font=("Arial", 10, "bold")).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="Cancel", command=dialog.destroy, width=15,
                 font=("Arial", 10)).pack(side=tk.LEFT, padx=5)
        
        # Bind Enter key
        dialog.bind('<Return>', lambda e: save())
    
    def open_slack_settings(self):
        """Open Slack settings dialog - manage webhook and enable/disable per instance or all."""
        self.load_instances()
        if not self.instances:
            messagebox.showinfo("Info", "Add at least one instance first.")
            return
        
        dialog = tk.Toplevel(self.root)
        dialog.title("Slack Notifications")
        dialog.geometry("520x280")
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.configure(bg="#1a1a2e")
        
        x = (dialog.winfo_screenwidth() // 2) - 260
        y = (dialog.winfo_screenheight() // 2) - 140
        dialog.geometry(f"520x280+{x}+{y}")
        
        tk.Label(dialog, text="💬 Slack — Live job notifications", font=("Segoe UI", 12, "bold"),
                 fg="#eee", bg="#1a1a2e").pack(pady=(10, 5))
        tk.Label(dialog, text="Get a message in Slack each time a bot applies to a job",
                 font=("Segoe UI", 9), fg="#999", bg="#1a1a2e").pack(pady=(0, 12))
        
        tk.Label(dialog, text="Webhook URL", font=("Segoe UI", 10), fg="#ccc", bg="#1a1a2e").pack(anchor="w", padx=20, pady=(0, 4))
        webhook_entry = tk.Entry(dialog, width=62, font=("Segoe UI", 10), relief=tk.FLAT, bg="#252530", fg="#fff",
                                 insertbackground="#fff")
        webhook_entry.pack(padx=20, pady=(0, 4), ipady=6, ipadx=8)
        
        tk.Label(dialog, text="Create an Incoming Webhook in Slack: Apps → Incoming Webhooks → Add to Slack",
                 font=("Segoe UI", 8), fg="#666", bg="#1a1a2e").pack(anchor="w", padx=20, pady=(2, 8))
        
        # Load current values from first instance
        first_name = list(self.instances.keys())[0]
        first_config = self.instances[first_name].get("config_file", "")
        if not os.path.isabs(first_config):
            first_config = os.path.join(SCRIPT_DIR, first_config)
        if os.path.exists(first_config):
            try:
                with open(first_config, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                    webhook_entry.insert(0, cfg.get("SLACK_WEBHOOK_URL", ""))
                    slack_var = tk.BooleanVar(value=cfg.get("SLACK_NOTIFICATIONS_ENABLED", False))
            except Exception:
                slack_var = tk.BooleanVar(value=False)
        else:
            tk.Checkbutton(dialog, text="Enable Slack notifications", variable=slack_var,
                      font=("Segoe UI", 10), fg="#ccc", bg="#1a1a2e", selectcolor="#252530",
                      activebackground="#1a1a2e", activeforeground="#ccc").pack(anchor="w", padx=20, pady=(4, 8))
        
        apply_var = tk.StringVar(value="all")
        frame = tk.Frame(dialog, bg="#1a1a2e")
        frame.pack(fill=tk.X, padx=20, pady=(0, 12))
        tk.Radiobutton(frame, text="Apply to all instances", variable=apply_var, value="all",
                       font=("Segoe UI", 10), fg="#ccc", bg="#1a1a2e", selectcolor="#252530",
                       activebackground="#1a1a2e", activeforeground="#ccc").pack(side=tk.LEFT, padx=(0, 20))
        tk.Radiobutton(frame, text="Apply to selected instance only", variable=apply_var, value="selected",
                       font=("Segoe UI", 10), fg="#ccc", bg="#1a1a2e", selectcolor="#252530",
                       activebackground="#1a1a2e", activeforeground="#ccc").pack(side=tk.LEFT)
        
        def save():
            webhook = webhook_entry.get().strip()
            enabled = slack_var.get()
            targets = []
            if apply_var.get() == "all":
                targets = list(self.instances.keys())
            else:
                sel = self.tree.selection()
                if not sel:
                    messagebox.showwarning("Warning", "Select an instance to apply to selected only.")
                    return
                item = self.tree.item(sel[0])
                name = item["values"][0] if item["values"] else None
                if name and name in self.instances:
                    targets = [name]
                else:
                    messagebox.showwarning("Warning", "Select an instance first.")
                    return
            
            if not targets:
                messagebox.showwarning("Warning", "No instances to update.")
                return
            
            for name in targets:
                config_path = self.instances[name].get("config_file", "")
                if not os.path.isabs(config_path):
                    config_path = os.path.join(SCRIPT_DIR, config_path)
                if not os.path.exists(config_path):
                    continue
                try:
                    with open(config_path, "r", encoding="utf-8") as f:
                        cfg = json.load(f)
                    cfg["SLACK_WEBHOOK_URL"] = webhook
                    cfg["SLACK_NOTIFICATIONS_ENABLED"] = enabled
                    with open(config_path, "w", encoding="utf-8") as f:
                        json.dump(cfg, f, indent=4)
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to update {name}: {e}")
                    return
            
            msg = f"Slack settings saved for {len(targets)} instance(s)."
            if enabled and webhook:
                msg += " Notifications are ON."
            elif not enabled:
                msg += " Notifications are OFF."
            messagebox.showinfo("Saved", msg)
            dialog.destroy()
        
        btn_frame = tk.Frame(dialog, bg="#1a1a2e")
        btn_frame.pack(pady=10)
        tk.Button(btn_frame, text="Save", command=save, width=12, bg="#611f69", fg="white",
                 font=("Segoe UI", 10), relief=tk.FLAT, cursor="hand2").pack(side=tk.LEFT, padx=4)
        tk.Button(btn_frame, text="Cancel", command=dialog.destroy, width=12,
                 font=("Segoe UI", 10), relief=tk.FLAT, cursor="hand2").pack(side=tk.LEFT, padx=4)
    
    def get_jobs_applied(self, log_file):
        """Extract jobs applied count from log file, summing across restarts"""
        if not os.path.exists(log_file):
            return "0"

        try:
            with open(log_file, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
                # Find all "Successful submissions: X" values
                matches = re.findall(r'Successful submissions:\s*(\d+)', content)
                if matches:
                    # The counter resets on each restart, so sum the peak of each run
                    # A reset is when the value drops (e.g. 3, 1 means new run started)
                    total = 0
                    prev = 0
                    for m in matches:
                        val = int(m)
                        if val <= prev:
                            # Counter reset — add the previous peak
                            total += prev
                        prev = val
                    total += prev  # Add the last run's count
                    return str(total)
                # Also check for "Successfully submitted X REAL applications"
                final_match = re.search(r'Successfully submitted\s+(\d+)\s+REAL applications', content)
                if final_match:
                    return final_match.group(1)
        except Exception:
            pass
        return "0"

    def get_jobs_scanned(self, log_file):
        """Count total jobs scanned/considered from log file"""
        if not os.path.exists(log_file):
            return "0"
        try:
            with open(log_file, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
                # Count lines like "[*] Job X:" or "[*] 🎯 Job X:"
                matches = re.findall(r'\[\*\].*?Job \d+:', content)
                return str(len(matches))
        except Exception:
            pass
        return "0"

    def get_last_log_line(self, log_file):
        """Get the last non-empty line from log file"""
        if not os.path.exists(log_file):
            return "—"
        
        try:
            with open(log_file, "r", encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()
                # Get last non-empty line, strip whitespace
                for line in reversed(lines):
                    stripped = line.strip()
                    if stripped and not stripped.startswith("Traceback"):
                        # Truncate long lines
                        if len(stripped) > 80:
                            return stripped[:77] + "..."
                        return stripped
        except Exception:
            pass
        return "—"
    
    def get_api_key_status(self, info):
        """Return ✓ if OPENAI_API_KEY is set, ✗ otherwise"""
        config_path = info.get("config_file", "")
        if not config_path or not os.path.exists(config_path):
            return "✗"
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            key = (cfg.get("OPENAI_API_KEY") or "").strip()
            return "✓" if key else "✗"
        except Exception:
            return "✗"
    
    def get_elapsed_time(self, start_time_str, log_file=None):
        """Calculate elapsed time from start time"""
        start_time = None
        
        # Try to use provided start_time
        if start_time_str:
            try:
                start_time = datetime.fromisoformat(start_time_str)
            except Exception:
                pass
        
        # Fallback: estimate from log file modification time if running
        if not start_time and log_file and os.path.exists(log_file):
            try:
                mod_time = os.path.getmtime(log_file)
                start_time = datetime.fromtimestamp(mod_time)
            except Exception:
                pass
        
        if not start_time:
            return "—"
        
        try:
            elapsed = datetime.now() - start_time
            
            # Format as HH:MM:SS
            total_seconds = int(elapsed.total_seconds())
            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            seconds = total_seconds % 60
            
            if hours > 0:
                return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
            else:
                return f"{minutes:02d}:{seconds:02d}"
        except Exception:
            return "—"
    
    def get_jobs_per_hour(self, jobs_applied, start_time_str, log_file=None):
        """Calculate jobs per hour"""
        if jobs_applied == "0" or jobs_applied == 0:
            return "0.0"
        
        start_time = None
        
        # Try to use provided start_time
        if start_time_str:
            try:
                start_time = datetime.fromisoformat(start_time_str)
            except Exception:
                pass
        
        # Fallback: estimate from log file modification time if running
        if not start_time and log_file and os.path.exists(log_file):
            try:
                mod_time = os.path.getmtime(log_file)
                start_time = datetime.fromtimestamp(mod_time)
            except Exception:
                pass
        
        if not start_time:
            return "—"
        
        try:
            elapsed = datetime.now() - start_time
            hours = elapsed.total_seconds() / 3600.0
            
            if hours > 0:
                jobs = int(jobs_applied) if isinstance(jobs_applied, str) else jobs_applied
                rate = jobs / hours
                return f"{rate:.1f}"
            else:
                return "0.0"
        except Exception:
            return "—"
    
    def refresh_list(self):
        self.load_instances()

        # Health check: verify running instances are actually alive, auto-restart crashed
        instances_changed = False
        crashed_names = []
        for name, info in self.instances.items():
            if info.get("status") == "running":
                pid = info.get("process_id")
                if not self.check_process_alive(pid):
                    info["status"] = "crashed"
                    instances_changed = True
                    crashed_names.append(name)
        if instances_changed:
            with open(INSTANCES_FILE, "w", encoding="utf-8") as f:
                json.dump(self.instances, f, indent=4)
            # Auto-restart crashed instances
            for name in crashed_names:
                print(f"[Dashboard] Auto-restarting crashed instance: {name}")
                self.instances[name]["status"] = "stopped"
                if "process_id" in self.instances[name]:
                    del self.instances[name]["process_id"]
                with open(INSTANCES_FILE, "w", encoding="utf-8") as f:
                    json.dump(self.instances, f, indent=4)
                try:
                    subprocess.run(
                        [sys.executable, "multi_bot_launcher.py", "start", name],
                        capture_output=True, text=True, timeout=10, cwd=SCRIPT_DIR,
                        creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
                    )
                    print(f"[Dashboard] Auto-restarted: {name}")
                except Exception as e:
                    print(f"[Dashboard] Auto-restart failed for {name}: {e}")
                self.load_instances()  # Reload after restart

        selection = self.tree.selection()
        selected_name = None
        if selection:
            item = self.tree.item(selection[0])
            selected_name = item["values"][0] if item["values"] else None
        
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        if not self.instances:
            self.tree.insert("", tk.END, values=("No instances yet", "—", "—", "—", "—", "—", "—", "Click «Add instance» to get started"))
            self.update_summary()
            return
        
        for name, info in self.instances.items():
            status = info.get("status", "stopped")
            if status == "running":
                status_display = "● Running"
                tag = "running"
            elif status == "crashed":
                status_display = "● Crashed"
                tag = "crashed"
            else:
                status_display = "● Stopped"
                tag = "stopped"
            
            log_file = info.get("log_file", os.path.join(SCRIPT_DIR, f"log_{name}.txt"))
            if not os.path.isabs(log_file):
                log_file = os.path.join(SCRIPT_DIR, log_file)
            jobs_applied = self.get_jobs_applied(log_file)
            jobs_scanned = self.get_jobs_scanned(log_file)
            last_log = self.get_last_log_line(log_file)

            start_time = info.get("start_time", "")
            elapsed_time = self.get_elapsed_time(start_time, log_file) if status == "running" else "—"
            jobs_per_hour = self.get_jobs_per_hour(jobs_applied, start_time, log_file) if status == "running" else "—"
            api_status = self.get_api_key_status(info)

            item_id = self.tree.insert("", tk.END, values=(
                name,
                status_display,
                api_status,
                jobs_scanned,
                jobs_applied,
                elapsed_time,
                jobs_per_hour,
                (last_log[:62] + "…") if len(last_log) > 62 else last_log,
            ), tags=(tag,))
            if selected_name == name:
                self.tree.selection_set(item_id)
        
        self.update_summary()
    
    def auto_refresh(self):
        """Auto-refresh the list every 3 seconds"""
        if self.auto_refresh_running:
            self.refresh_list()
            self.root.after(3000, self.auto_refresh)  # Refresh every 3 seconds
    
    def start_whatsapp_scheduler(self):
        """Start the WhatsApp scheduler in background thread"""
        try:
            # Check if scheduler thread already exists
            if hasattr(self, 'whatsapp_scheduler_thread') and self.whatsapp_scheduler_thread.is_alive():
                return  # Already running
            
            # Import scheduler functions
            import whatsapp_scheduler
            
            # Start scheduler in background thread
            self.whatsapp_scheduler_thread = threading.Thread(
                target=whatsapp_scheduler.scheduler_loop, 
                daemon=True
            )
            self.whatsapp_scheduler_thread.start()
            print("[Multi-Bot] WhatsApp scheduler started (embedded)")
        except Exception as e:
            print(f"[Multi-Bot] Failed to start WhatsApp scheduler: {e}")
            import traceback
            traceback.print_exc()
    
    def start_selected(self):
        """Start selected instance"""
        selection = self.tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select an instance")
            return
        
        item = self.tree.item(selection[0])
        name = item["values"][0]
        
        # Check if already running
        if name in self.instances and self.instances[name].get("status") == "running":
            messagebox.showwarning("Warning", f"Instance '{name}' is already running!")
            return
        
        try:
            result = subprocess.run(
                [sys.executable, "multi_bot_launcher.py", "start", name],
                capture_output=True, text=True, timeout=10, cwd=SCRIPT_DIR,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
            )
            if "✅" in result.stdout or result.returncode == 0:
                messagebox.showinfo("Success", f"Instance '{name}' started.")
            else:
                error_msg = result.stdout + result.stderr
                messagebox.showerror("Error", f"Failed to start instance:\n{error_msg}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to start instance: {e}")
        
        self.refresh_list()
    
    def stop_selected(self):
        """Stop selected instance"""
        selection = self.tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select an instance")
            return
        
        item = self.tree.item(selection[0])
        name = item["values"][0]
        
        # Check if already stopped
        if name in self.instances and self.instances[name].get("status") != "running":
            messagebox.showwarning("Warning", f"Instance '{name}' is not running!")
            return
        
        try:
            result = subprocess.run(
                [sys.executable, "multi_bot_launcher.py", "stop", name],
                capture_output=True, text=True, timeout=10, cwd=SCRIPT_DIR,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
            )
            if "✅" in result.stdout or result.returncode == 0:
                messagebox.showinfo("Success", f"Instance '{name}' stopped.")
            else:
                error_msg = result.stdout + result.stderr
                messagebox.showerror("Error", f"Failed to stop instance:\n{error_msg}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to stop instance: {e}")
        
        self.refresh_list()
    
    def remove_selected(self):
        """Remove selected instance"""
        selection = self.tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select an instance")
            return
        
        item = self.tree.item(selection[0])
        name = item["values"][0]
        
        if messagebox.askyesno("Confirm", f"Remove instance '{name}'? (Config removed; log files kept.)"):
            subprocess.Popen(
                [sys.executable, "multi_bot_launcher.py", "remove", name],
                cwd=SCRIPT_DIR,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
            )
            self.load_instances()
            self.refresh_list()
            messagebox.showinfo("Info", f"Instance '{name}' removed")
    
    def view_log(self):
        """View log file for selected instance"""
        selection = self.tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select an instance")
            return
        
        item = self.tree.item(selection[0])
        name = item["values"][0]
        
        if name not in self.instances:
            messagebox.showerror("Error", "Instance not found")
            return
        
        log_file = self.instances[name].get("log_file", os.path.join(SCRIPT_DIR, f"log_{name}.txt"))
        if not os.path.isabs(log_file):
            log_file = os.path.join(SCRIPT_DIR, log_file)
        
        if not os.path.exists(log_file):
            messagebox.showinfo("Info", f"Log file not found: {log_file}")
            return
        
        # Open log file in notepad (Windows) or default text editor
        try:
            if sys.platform == "win32":
                os.startfile(log_file)
            elif sys.platform == "darwin":
                subprocess.run(["open", log_file])
            else:
                subprocess.run(["xdg-open", log_file])
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open log file: {e}")
    
    def open_config(self):
        """Open SeekMate Config GUI for this instance (speed, API, job titles, etc.)."""
        selection = self.tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select an instance")
            return
        
        item = self.tree.item(selection[0])
        name = item["values"][0]
        
        if name not in self.instances:
            messagebox.showerror("Error", "Instance not found")
            return
        
        config_file = self.instances[name].get("config_file", "")
        if not os.path.isabs(config_file):
            config_file = os.path.join(SCRIPT_DIR, config_file)
        if not config_file or not os.path.exists(config_file):
            messagebox.showerror("Error", f"Config file not found: {config_file}")
            return
        
        config_gui_path = os.path.join(SCRIPT_DIR, "config_gui.py")
        if not os.path.exists(config_gui_path):
            messagebox.showerror("Error", "config_gui.py not found in SeekMateAI folder.")
            return
        
        try:
            subprocess.Popen(
                [sys.executable, config_gui_path, config_file],
                cwd=SCRIPT_DIR,
            )
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open config: {e}")
    
    def start_all(self):
        """Start all instances"""
        if not self.instances:
            messagebox.showwarning("Warning", "No instances configured")
            return
        
        if messagebox.askyesno("Confirm", f"Start all {len(self.instances)} instance(s)?"):
            subprocess.Popen(
                [sys.executable, "multi_bot_launcher.py", "start-all"],
                cwd=SCRIPT_DIR,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
            )
            messagebox.showinfo("Info", "Starting all instances...")
            self.refresh_list()
    
    def restart_crashed(self):
        """Restart any crashed instances"""
        self.load_instances()
        crashed = [name for name, info in self.instances.items() if info.get("status") == "crashed"]
        if not crashed:
            messagebox.showinfo("Info", "No crashed instances to restart.")
            return

        if messagebox.askyesno("Confirm", f"Restart {len(crashed)} crashed instance(s)?\n" + "\n".join(crashed)):
            for name in crashed:
                # Reset status so start_instance will work
                self.instances[name]["status"] = "stopped"
                if "process_id" in self.instances[name]:
                    del self.instances[name]["process_id"]
            with open(INSTANCES_FILE, "w", encoding="utf-8") as f:
                json.dump(self.instances, f, indent=4)

            for name in crashed:
                try:
                    subprocess.run(
                        [sys.executable, "multi_bot_launcher.py", "start", name],
                        capture_output=True, text=True, timeout=10, cwd=SCRIPT_DIR,
                        creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
                    )
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to restart {name}: {e}")

            messagebox.showinfo("Info", f"Restarted {len(crashed)} instance(s)")
            self.refresh_list()

    def stop_all(self):
        """Stop all instances"""
        if not self.instances:
            messagebox.showwarning("Warning", "No instances configured")
            return
        
        if messagebox.askyesno("Confirm", f"Stop all {len(self.instances)} instance(s)?"):
            subprocess.Popen(
                [sys.executable, "multi_bot_launcher.py", "stop-all"],
                cwd=SCRIPT_DIR,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
            )
            messagebox.showinfo("Info", "Stopping all instances...")
            self.refresh_list()

if __name__ == "__main__":
    root = tk.Tk()
    app = MultiBotGUI(root)
    
    # Cleanup on close
    def on_closing():
        app.auto_refresh_running = False
        # Note: WhatsApp scheduler thread is daemon, will stop automatically
        root.destroy()
    
    root.protocol("WM_DELETE_WINDOW", on_closing)
    root.mainloop()

