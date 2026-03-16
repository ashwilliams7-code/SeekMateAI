#!/usr/bin/env python3
"""
Multi-Bot Launcher for SeekMateAI
Allows running multiple bot instances simultaneously, each with its own:
- Chrome profile
- Config file
- Seek account
- Log file
"""

import os
import sys
import json
import subprocess
import time
import threading
from pathlib import Path
from datetime import datetime

# Shared job tracking database for cross-instance duplicate prevention
SHARED_JOBS_DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "shared_applied_jobs.json")

def load_shared_jobs():
    """Load the shared applied jobs registry"""
    if os.path.exists(SHARED_JOBS_DB):
        try:
            with open(SHARED_JOBS_DB, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def save_shared_jobs(jobs):
    """Save the shared applied jobs registry"""
    try:
        with open(SHARED_JOBS_DB, "w", encoding="utf-8") as f:
            json.dump(jobs, f, indent=2)
    except Exception as e:
        print(f"[SharedJobs] Failed to save: {e}")

def register_applied_job(job_url, instance_name, job_title="", company=""):
    """Register a job as applied by an instance. Returns False if already applied by another instance."""
    jobs = load_shared_jobs()
    if job_url in jobs:
        return False  # Already applied by another instance
    jobs[job_url] = {
        "instance": instance_name,
        "title": job_title,
        "company": company,
        "applied_at": datetime.now().isoformat()
    }
    save_shared_jobs(jobs)
    return True

def is_job_applied(job_url):
    """Check if a job has already been applied to by any instance"""
    jobs = load_shared_jobs()
    return job_url in jobs

# Configuration
INSTANCES_FILE = "bot_instances.json"
INSTANCES_DIR = "bot_instances"

def ensure_instances_dir():
    """Create instances directory if it doesn't exist"""
    os.makedirs(INSTANCES_DIR, exist_ok=True)

def load_instances():
    """Load bot instances configuration"""
    if os.path.exists(INSTANCES_FILE):
        with open(INSTANCES_FILE, "r") as f:
            return json.load(f)
    return {}

def save_instances(instances):
    """Save bot instances configuration"""
    with open(INSTANCES_FILE, "w") as f:
        json.dump(instances, f, indent=4)

def create_instance_config(instance_name, base_config_path="config.json"):
    """Create a config file for a specific instance"""
    ensure_instances_dir()
    
    # Load base config
    if os.path.exists(base_config_path):
        with open(base_config_path, "r") as f:
            config = json.load(f)
    else:
        # Create default config
        config = {
            "OPENAI_API_KEY": "",
            "FULL_NAME": instance_name,
            "LOCATION": "Brisbane, Australia",
            "SEEK_EMAIL": "",
            "JOB_TITLE": "director",
            "CV_PATH": "",
            "MAX_JOBS": 100,
            "EXPECTED_SALARY": 100000,
            "JOB_TITLES": ["director", "manager"],
            "SCAN_SPEED": 8,
            "APPLY_SPEED": 8,
            "COOLDOWN_DELAY": 5,
            "STEALTH_MODE": False,
            "USE_SEEK": True,
            "USE_INDEED": False,
        }
    
    # Save instance-specific config
    instance_config_path = os.path.join(INSTANCES_DIR, f"{instance_name}_config.json")
    with open(instance_config_path, "w") as f:
        json.dump(config, f, indent=4)
    
    return instance_config_path

def add_instance(instance_name, seek_email=None, full_name=None):
    """Add a new bot instance"""
    instances = load_instances()
    
    if instance_name in instances:
        print(f"❌ Instance '{instance_name}' already exists!")
        return False
    
    # Create instance config
    config_path = create_instance_config(instance_name)
    
    # Load and update config
    with open(config_path, "r") as f:
        config = json.load(f)
    
    if seek_email:
        config["SEEK_EMAIL"] = seek_email
    if full_name:
        config["FULL_NAME"] = full_name
    
    with open(config_path, "w") as f:
        json.dump(config, f, indent=4)
    
    # Add to instances registry
    script_dir = os.path.dirname(os.path.abspath(__file__))
    instances[instance_name] = {
        "config_file": os.path.abspath(config_path),
        "chrome_profile": f"chrome_profile_{instance_name}",
        "log_file": os.path.join(script_dir, f"log_{instance_name}.txt"),
        "control_file": os.path.join(script_dir, f"control_{instance_name}.json"),
        "status": "stopped"
    }
    
    save_instances(instances)
    print(f"✅ Instance '{instance_name}' created successfully!")
    print(f"   Config: {config_path}")
    print(f"   Chrome Profile: chrome_profile_{instance_name}")
    return True

def list_instances():
    """List all bot instances"""
    instances = load_instances()
    
    if not instances:
        print("No bot instances configured.")
        return
    
    print("\n" + "="*60)
    print("BOT INSTANCES")
    print("="*60)
    for name, info in instances.items():
        status = info.get("status", "unknown")
        print(f"\n📌 {name}")
        print(f"   Status: {status}")
        print(f"   Config: {info['config_file']}")
        print(f"   Chrome Profile: {info['chrome_profile']}")
        print(f"   Log: {info['log_file']}")
    print("="*60 + "\n")

def start_instance(instance_name):
    """Start a single bot instance by running main.py with env vars (no generated files)."""
    instances = load_instances()
    
    if instance_name not in instances:
        print(f"❌ Instance '{instance_name}' not found!")
        return False
    
    instance = instances[instance_name]
    
    if instance.get("status") == "running":
        print(f"⚠️  Instance '{instance_name}' is already running!")
        return False
    
    script_dir = os.path.dirname(os.path.abspath(__file__))
    main_py = os.path.join(script_dir, "main.py")
    if not os.path.exists(main_py):
        print(f"❌ main.py not found in {script_dir}")
        return False
    
    # Pass paths via environment so we never generate .py files or escape paths
    env = dict(os.environ)
    env["BOT_INSTANCE_NAME"] = instance_name
    env["BOT_CONFIG_FILE"] = os.path.abspath(instance["config_file"])
    env["BOT_CHROME_PROFILE"] = instance["chrome_profile"]
    env["BOT_LOG_FILE"] = os.path.abspath(instance["log_file"])
    env["BOT_CONTROL_FILE"] = os.path.abspath(instance["control_file"])
    
    log_path = instance["log_file"]
    if not os.path.isabs(log_path):
        log_path = os.path.join(script_dir, log_path)
    
    print(f"🚀 Starting instance '{instance_name}'...")
    try:
        log_handle = open(log_path, "a", encoding="utf-8")
        process = subprocess.Popen(
            [sys.executable, main_py],
            cwd=script_dir,
            env=env,
            stdout=log_handle,
            stderr=subprocess.STDOUT,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        )
        instance["process_id"] = process.pid
        instance["status"] = "running"
        instance["start_time"] = datetime.now().isoformat()
        save_instances(instances)
        print(f"✅ Instance '{instance_name}' started (PID: {process.pid})")
        print(f"   Log: {log_path}")
        return True
    except Exception as e:
        print(f"❌ Failed to start instance '{instance_name}': {e}")
        import traceback
        traceback.print_exc()
        return False

def stop_instance(instance_name):
    """Stop a single bot instance"""
    instances = load_instances()
    
    if instance_name not in instances:
        print(f"❌ Instance '{instance_name}' not found!")
        return False
    
    instance = instances[instance_name]
    
    if instance.get("status") != "running":
        print(f"⚠️  Instance '{instance_name}' is not running!")
        return False
    
    # Write stop signal to control file
    control_file = instance["control_file"]
    try:
        with open(control_file, "w") as f:
            json.dump({"stop": True, "pause": False}, f)
    except:
        pass
    
    # Try to kill the process
    try:
        pid = instance.get("process_id")
        if pid:
            if sys.platform == "win32":
                subprocess.run(["taskkill", "/F", "/PID", str(pid)], 
                             capture_output=True)
            else:
                os.kill(pid, 15)  # SIGTERM
    except:
        pass
    
    instance["status"] = "stopped"
    if "process_id" in instance:
        del instance["process_id"]
    if "start_time" in instance:
        del instance["start_time"]
    save_instances(instances)
    
    print(f"✅ Instance '{instance_name}' stopped")
    return True

def start_all():
    """Start all bot instances"""
    instances = load_instances()
    
    if not instances:
        print("❌ No bot instances configured!")
        return
    
    print(f"🚀 Starting {len(instances)} bot instance(s)...\n")
    
    for name in instances.keys():
        start_instance(name)
        time.sleep(2)  # Small delay between starts
    
    print("\n✅ All instances started!")

def stop_all():
    """Stop all bot instances"""
    instances = load_instances()
    
    if not instances:
        print("❌ No bot instances configured!")
        return
    
    print(f"🛑 Stopping {len(instances)} bot instance(s)...\n")
    
    for name in instances.keys():
        stop_instance(name)
        time.sleep(1)
    
    print("\n✅ All instances stopped!")

def main():
    """Main CLI interface"""
    if len(sys.argv) < 2:
        print("""
SeekMateAI Multi-Bot Launcher

Usage:
    python multi_bot_launcher.py add <instance_name> [--email <seek_email>] [--name <full_name>]
    python multi_bot_launcher.py list
    python multi_bot_launcher.py start <instance_name>
    python multi_bot_launcher.py stop <instance_name>
    python multi_bot_launcher.py start-all
    python multi_bot_launcher.py stop-all
    python multi_bot_launcher.py remove <instance_name>

Examples:
    python multi_bot_launcher.py add bot1 --email user1@example.com --name "John Doe"
    python multi_bot_launcher.py add bot2 --email user2@example.com --name "Jane Smith"
    python multi_bot_launcher.py start-all
        """)
        return
    
    command = sys.argv[1].lower()
    
    if command == "add":
        if len(sys.argv) < 3:
            print("❌ Usage: python multi_bot_launcher.py add <instance_name> [--email <email>] [--name <name>]")
            return
        
        instance_name = sys.argv[2]
        seek_email = None
        full_name = None
        
        # Parse optional arguments
        i = 3
        while i < len(sys.argv):
            if sys.argv[i] == "--email" and i + 1 < len(sys.argv):
                seek_email = sys.argv[i + 1]
                i += 2
            elif sys.argv[i] == "--name" and i + 1 < len(sys.argv):
                full_name = sys.argv[i + 1]
                i += 2
            else:
                i += 1
        
        add_instance(instance_name, seek_email, full_name)
    
    elif command == "list":
        list_instances()
    
    elif command == "start":
        if len(sys.argv) < 3:
            print("❌ Usage: python multi_bot_launcher.py start <instance_name>")
            return
        start_instance(sys.argv[2])
    
    elif command == "stop":
        if len(sys.argv) < 3:
            print("❌ Usage: python multi_bot_launcher.py stop <instance_name>")
            return
        stop_instance(sys.argv[2])
    
    elif command == "start-all":
        start_all()
    
    elif command == "stop-all":
        stop_all()
    
    elif command == "remove":
        if len(sys.argv) < 3:
            print("❌ Usage: python multi_bot_launcher.py remove <instance_name>")
            return
        
        instances = load_instances()
        instance_name = sys.argv[2]
        
        if instance_name not in instances:
            print(f"❌ Instance '{instance_name}' not found!")
            return
        
        # Stop if running
        if instances[instance_name].get("status") == "running":
            stop_instance(instance_name)
        
        # Remove from registry
        del instances[instance_name]
        save_instances(instances)
        
        print(f"✅ Instance '{instance_name}' removed")
    
    else:
        print(f"❌ Unknown command: {command}")

if __name__ == "__main__":
    main()

