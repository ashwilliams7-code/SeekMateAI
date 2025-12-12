import tkinter as tk
from tkinter import ttk, messagebox
import subprocess
import sys
import json
import os
import re
import threading
from datetime import datetime, timedelta

class MultiBotGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("SeekMateAI - Multi-Bot Manager")
        self.root.geometry("1400x700")
        
        # Load instances
        self.load_instances()
        
        # Create UI
        self.create_ui()
        self.refresh_list()
        
        # Start auto-refresh for live updates
        self.auto_refresh_running = True
        self.auto_refresh()
        
        # Start WhatsApp scheduler
        self.start_whatsapp_scheduler()
    
    def load_instances(self):
        """Load bot instances"""
        if os.path.exists("bot_instances.json"):
            with open("bot_instances.json", "r") as f:
                self.instances = json.load(f)
        else:
            self.instances = {}
    
    def create_ui(self):
        # Header
        header = tk.Label(self.root, text="SeekMateAI - Multi-Bot Manager", 
                         font=("Arial", 18, "bold"))
        header.pack(pady=10)
        
        # Buttons frame
        btn_frame = tk.Frame(self.root)
        btn_frame.pack(pady=10)
        
        tk.Button(btn_frame, text="➕ Add Instance", 
                 command=self.add_instance, width=18, bg="#4CAF50", fg="white",
                 font=("Arial", 10, "bold")).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="▶️ Start All", 
                 command=self.start_all, width=18, bg="#2196F3", fg="white",
                 font=("Arial", 10, "bold")).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="⏹️ Stop All", 
                 command=self.stop_all, width=18, bg="#f44336", fg="white",
                 font=("Arial", 10, "bold")).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="🔄 Refresh", 
                 command=self.refresh_list, width=18,
                 font=("Arial", 10)).pack(side=tk.LEFT, padx=5)
        
        # List frame
        list_frame = tk.Frame(self.root)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        # Treeview for instances
        columns = ("Name", "Status", "Jobs", "Time", "Jobs/Hr", "Last Log", "Config", "Profile")
        self.tree = ttk.Treeview(list_frame, columns=columns, show="headings", height=18)
        
        for col in columns:
            self.tree.heading(col, text=col)
            if col == "Name":
                self.tree.column(col, width=100)
            elif col == "Status":
                self.tree.column(col, width=90)
            elif col == "Jobs":
                self.tree.column(col, width=60)
            elif col == "Time":
                self.tree.column(col, width=100)
            elif col == "Jobs/Hr":
                self.tree.column(col, width=80)
            elif col == "Last Log":
                self.tree.column(col, width=250)
            else:
                self.tree.column(col, width=120)
        
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Action buttons frame
        action_frame = tk.Frame(self.root)
        action_frame.pack(pady=10)
        
        tk.Button(action_frame, text="▶️ Start Selected", 
                 command=self.start_selected, width=18, bg="#4CAF50", fg="white",
                 font=("Arial", 10)).pack(side=tk.LEFT, padx=5)
        tk.Button(action_frame, text="⏹️ Stop Selected", 
                 command=self.stop_selected, width=18, bg="#f44336", fg="white",
                 font=("Arial", 10)).pack(side=tk.LEFT, padx=5)
        tk.Button(action_frame, text="🗑️ Remove Selected", 
                 command=self.remove_selected, width=18,
                 font=("Arial", 10)).pack(side=tk.LEFT, padx=5)
        tk.Button(action_frame, text="📋 View Log", 
                 command=self.view_log, width=18,
                 font=("Arial", 10)).pack(side=tk.LEFT, padx=5)
        tk.Button(action_frame, text="⚙️ Open Config", 
                 command=self.open_config, width=18,
                 font=("Arial", 10), bg="#FF9800", fg="white").pack(side=tk.LEFT, padx=5)
    
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
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
                
                if "✅" in result.stdout or result.returncode == 0:
                    messagebox.showinfo("Success", f"Instance '{name}' added successfully!")
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
    
    def get_jobs_applied(self, log_file):
        """Extract jobs applied count from log file"""
        if not os.path.exists(log_file):
            return "0"
        
        try:
            with open(log_file, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
                # Look for "Successful submissions: X" pattern
                matches = re.findall(r'Successful submissions:\s*(\d+)', content)
                if matches:
                    return str(max(int(m) for m in matches))
                # Also check for "Successfully submitted X REAL applications"
                final_match = re.search(r'Successfully submitted\s+(\d+)\s+REAL applications', content)
                if final_match:
                    return final_match.group(1)
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
        """Refresh the instances list"""
        self.load_instances()
        
        # Store current selection
        selection = self.tree.selection()
        selected_name = None
        if selection:
            item = self.tree.item(selection[0])
            selected_name = item["values"][0] if item["values"] else None
        
        # Clear tree
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        # Add instances with live data
        for name, info in self.instances.items():
            status = info.get("status", "stopped")
            status_display = "🟢 Running" if status == "running" else "🔴 Stopped"
            
            # Get jobs applied and last log line
            log_file = info.get("log_file", f"log_{name}.txt")
            jobs_applied = self.get_jobs_applied(log_file)
            last_log = self.get_last_log_line(log_file)
            
            # Get elapsed time and jobs per hour
            start_time = info.get("start_time", "")
            elapsed_time = self.get_elapsed_time(start_time, log_file) if status == "running" else "—"
            jobs_per_hour = self.get_jobs_per_hour(jobs_applied, start_time, log_file) if status == "running" else "—"
            
            item_id = self.tree.insert("", tk.END, values=(
                name,
                status_display,
                jobs_applied,
                elapsed_time,
                jobs_per_hour,
                last_log,
                os.path.basename(info.get("config_file", "")),
                info.get("chrome_profile", "")
            ))
            
            # Restore selection
            if selected_name == name:
                self.tree.selection_set(item_id)
    
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
                capture_output=True,
                text=True,
                timeout=10,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
            )
            
            if "✅" in result.stdout or result.returncode == 0:
                messagebox.showinfo("Success", f"Instance '{name}' started successfully!")
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
                capture_output=True,
                text=True,
                timeout=10,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
            )
            
            if "✅" in result.stdout or result.returncode == 0:
                messagebox.showinfo("Success", f"Instance '{name}' stopped successfully!")
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
        
        if messagebox.askyesno("Confirm", f"Are you sure you want to remove instance '{name}'?\n\nThis will delete the instance configuration but keep the log files."):
            subprocess.Popen([sys.executable, "multi_bot_launcher.py", "remove", name],
                           creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0)
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
        
        log_file = self.instances[name].get("log_file", f"log_{name}.txt")
        
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
        """Open config GUI for selected instance"""
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
        if not config_file or not os.path.exists(config_file):
            messagebox.showerror("Error", f"Config file not found: {config_file}")
            return
        
        # Open config GUI with the instance's config file
        try:
            subprocess.Popen(
                [sys.executable, "config_gui.py", config_file],
                creationflags=subprocess.CREATE_NEW_CONSOLE if sys.platform == "win32" else 0
            )
            messagebox.showinfo("Success", f"Opening config GUI for '{name}'...")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open config GUI: {e}")
    
    def start_all(self):
        """Start all instances"""
        if not self.instances:
            messagebox.showwarning("Warning", "No instances configured")
            return
        
        if messagebox.askyesno("Confirm", f"Start all {len(self.instances)} instance(s)?"):
            subprocess.Popen([sys.executable, "multi_bot_launcher.py", "start-all"],
                           creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0)
            messagebox.showinfo("Info", "Starting all instances...")
            self.refresh_list()
    
    def stop_all(self):
        """Stop all instances"""
        if not self.instances:
            messagebox.showwarning("Warning", "No instances configured")
            return
        
        if messagebox.askyesno("Confirm", f"Stop all {len(self.instances)} instance(s)?"):
            subprocess.Popen([sys.executable, "multi_bot_launcher.py", "stop-all"],
                           creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0)
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

