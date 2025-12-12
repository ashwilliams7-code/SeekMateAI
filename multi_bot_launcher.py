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
    """Start a single bot instance"""
    instances = load_instances()
    
    if instance_name not in instances:
        print(f"❌ Instance '{instance_name}' not found!")
        return False
    
    instance = instances[instance_name]
    
    # Check if already running
    if instance.get("status") == "running":
        print(f"⚠️  Instance '{instance_name}' is already running!")
        return False
    
    # Create modified main.py that uses instance-specific config
    print(f"🚀 Starting instance '{instance_name}'...")
    
    # Start bot in a subprocess
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Create a wrapper script for this instance
    # Use raw strings and proper escaping for Windows paths
    config_file_path = os.path.abspath(instance["config_file"]).replace('\\', '\\\\')
    control_file_path = os.path.abspath(instance["control_file"]).replace('\\', '\\\\')
    log_file_path = instance["log_file"].replace('\\', '\\\\')
    script_dir_path = script_dir.replace('\\', '\\\\')
    
    wrapper_script = f"""import os
import sys
import json

# Set instance-specific environment variables
os.environ['BOT_INSTANCE_NAME'] = '{instance_name}'
os.environ['BOT_CONFIG_FILE'] = r'{config_file_path}'
os.environ['BOT_CHROME_PROFILE'] = '{instance["chrome_profile"]}'
os.environ['BOT_LOG_FILE'] = r'{log_file_path}'
os.environ['BOT_CONTROL_FILE'] = r'{control_file_path}'

# Import and run main
sys.path.insert(0, r'{script_dir_path}')
import main
main.main()
"""
    
    wrapper_path = os.path.join(INSTANCES_DIR, f"{instance_name}_runner.py")
    with open(wrapper_path, "w") as f:
        f.write(wrapper_script)
    
    # Start the process
    try:
        log_file_path = os.path.join(script_dir, instance["log_file"])
        log_file = open(log_file_path, "a", encoding="utf-8")
        
        process = subprocess.Popen(
            [sys.executable, wrapper_path],
            cwd=script_dir,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        )
        
        instance["process_id"] = process.pid
        instance["status"] = "running"
        instance["start_time"] = datetime.now().isoformat()  # Track start time
        save_instances(instances)
        
        print(f"✅ Instance '{instance_name}' started (PID: {process.pid})")
        print(f"   Log file: {log_file_path}")
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

