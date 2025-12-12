#!/usr/bin/env python3
"""
WhatsApp Scheduled Summary Sender
Sends daily summaries at 9 AM (overnight) and 6 PM (end of day)
"""

import os
import sys
import json
import time
import re
import threading
import subprocess
from datetime import datetime, timedelta
import urllib.request
import urllib.parse
import base64

# Load config
CONFIG_FILE = "config.json"
if len(sys.argv) > 1:
    CONFIG_FILE = sys.argv[1]

def load_config():
    """Load configuration"""
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    return {}

CONFIG = load_config()

# Twilio settings
TWILIO_ACCOUNT_SID = CONFIG.get("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN = CONFIG.get("TWILIO_AUTH_TOKEN", "")
TWILIO_WHATSAPP_FROM = CONFIG.get("TWILIO_WHATSAPP_FROM", "whatsapp:+14155238886")
WHATSAPP_NOTIFICATIONS = CONFIG.get("WHATSAPP_NOTIFICATIONS", True)

# Profile phone numbers
PROFILE_PHONES = {
    "Ash Williams": "+61490077979",
    "Jennifer Berrio": "+61491723617",
    "Rafael Hurtado": "+6411557289",
}

# Default phone number (use first available or primary)
DEFAULT_PHONE = PROFILE_PHONES.get("Ash Williams", "")

def get_jobs_applied_from_log(log_file):
    """Extract jobs applied count from log file"""
    if not os.path.exists(log_file):
        return 0
    
    try:
        with open(log_file, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
            # Look for "Successful submissions: X" pattern
            matches = re.findall(r'Successful submissions:\s*(\d+)', content)
            if matches:
                return max(int(m) for m in matches)
            # Also check for "Successfully submitted X REAL applications"
            final_match = re.search(r'Successfully submitted\s+(\d+)', content)
            if final_match:
                return int(final_match.group(1))
    except Exception:
        pass
    return 0

def check_bot_health(name, info):
    """Check bot health status - returns (status_icon, status_text, needs_attention)"""
    status = info.get("status", "stopped")
    
    if status != "running":
        return ("🔴", "Stopped", True)
    
    # Check if process is actually running
    process_id = info.get("process_id")
    if process_id:
        try:
            if sys.platform == "win32":
                result = subprocess.run(
                    ["tasklist", "/FI", f"PID eq {process_id}"],
                    capture_output=True,
                    timeout=2
                )
                if str(process_id) not in result.stdout.decode():
                    return ("🔴", "Process Not Found", True)
            else:
                # Unix: check if process exists
                try:
                    os.kill(process_id, 0)
                except OSError:
                    return ("🔴", "Process Not Found", True)
        except:
            pass  # Continue with log file check
    
    # Check if log file is being updated (bot is active)
    log_file = info.get("log_file", f"log_{name}.txt")
    if os.path.exists(log_file):
        try:
            # Check last modification time
            mod_time = os.path.getmtime(log_file)
            time_since_update = (time.time() - mod_time) / 60  # minutes
            
            # Check for recent errors in log
            has_errors = False
            error_count = 0
            try:
                with open(log_file, "r", encoding="utf-8", errors="ignore") as f:
                    lines = f.readlines()
                    # Check last 50 lines for errors
                    recent_lines = lines[-50:] if len(lines) > 50 else lines
                    error_count = sum(1 for line in recent_lines[-20:] 
                                     if "ERROR" in line or "Traceback" in line or "Failed" in line)
                    has_errors = error_count > 0
            except:
                pass
            
            # Determine health status
            if time_since_update > 30:  # No update in 30+ minutes
                return ("⚠️", f"Stuck/Frozen ({int(time_since_update)}m ago)", True)
            elif time_since_update > 15:  # No update in 15+ minutes
                return ("🟡", f"Slow/Idle ({int(time_since_update)}m ago)", False)
            elif has_errors:
                return ("⚠️", f"Has Errors ({error_count} recent)", True)
            else:
                return ("🟢", "Running Well", False)
        except Exception as e:
            return ("🟡", "Unknown", False)
    else:
        # Log file doesn't exist - bot might not have started properly
        return ("⚠️", "No Log File", True)
    
    return ("🟢", "Running", False)

def get_all_bot_summaries():
    """Get job counts from all bot instances"""
    summaries = []
    
    # Load bot instances
    instances_file = "bot_instances.json"
    if not os.path.exists(instances_file):
        return summaries
    
    try:
        with open(instances_file, "r") as f:
            instances = json.load(f)
        
        for name, info in instances.items():
            log_file = info.get("log_file", f"log_{name}.txt")
            jobs_applied = get_jobs_applied_from_log(log_file)
            
            # Get config to find profile name
            config_file = info.get("config_file", "")
            profile_name = name
            if os.path.exists(config_file):
                try:
                    with open(config_file, "r") as cf:
                        config = json.load(cf)
                        profile_name = config.get("FULL_NAME", name)
                except:
                    pass
            
            # Check bot health
            health_icon, health_text, needs_attention = check_bot_health(name, info)
            
            summaries.append({
                "name": name,
                "profile": profile_name,
                "jobs": jobs_applied,
                "status": info.get("status", "stopped"),
                "health_icon": health_icon,
                "health_text": health_text,
                "needs_attention": needs_attention
            })
    except Exception as e:
        print(f"[WhatsApp Scheduler] Error loading instances: {e}")
    
    return summaries

# Track last summary times and job counts
SUMMARY_STATE_FILE = "whatsapp_summary_state.json"

def load_summary_state():
    """Load last summary state"""
    if os.path.exists(SUMMARY_STATE_FILE):
        try:
            with open(SUMMARY_STATE_FILE, "r") as f:
                return json.load(f)
        except:
            pass
    return {
        "last_9am": None,
        "last_6pm": None,
        "jobs_at_9am": {},
        "jobs_at_6pm": {}
    }

def save_summary_state(state):
    """Save summary state"""
    try:
        with open(SUMMARY_STATE_FILE, "w") as f:
            json.dump(state, f, indent=2)
    except Exception as e:
        print(f"[WhatsApp Scheduler] Error saving state: {e}")

def send_whatsapp_message(phone, message):
    """Send WhatsApp message via Twilio"""
    if not WHATSAPP_NOTIFICATIONS:
        return False
    
    if not TWILIO_ACCOUNT_SID or not TWILIO_AUTH_TOKEN:
        print("[WhatsApp Scheduler] Twilio credentials not configured")
        return False
    
    if not phone:
        phone = DEFAULT_PHONE
    
    if not phone:
        print("[WhatsApp Scheduler] No phone number configured")
        return False
    
    try:
        url = f"https://api.twilio.com/2010-04-01/Accounts/{TWILIO_ACCOUNT_SID}/Messages.json"
        
        to_number = f"whatsapp:{phone}" if not phone.startswith("whatsapp:") else phone
        
        data = urllib.parse.urlencode({
            'From': TWILIO_WHATSAPP_FROM,
            'To': to_number,
            'Body': message
        }).encode('utf-8')
        
        request = urllib.request.Request(url, data=data)
        credentials = f"{TWILIO_ACCOUNT_SID}:{TWILIO_AUTH_TOKEN}"
        encoded_credentials = base64.b64encode(credentials.encode()).decode()
        request.add_header('Authorization', f'Basic {encoded_credentials}')
        
        with urllib.request.urlopen(request, timeout=30) as response:
            if response.status == 201:
                print(f"[WhatsApp Scheduler] ✅ Message sent to {phone}")
                return True
            else:
                print(f"[WhatsApp Scheduler] Failed: Status {response.status}")
                return False
    except Exception as e:
        print(f"[WhatsApp Scheduler] Error sending message: {e}")
        return False

def send_daily_summary(is_morning=False):
    """Send daily summary of all bot instances"""
    summaries = get_all_bot_summaries()
    state = load_summary_state()
    
    if not summaries:
        print("[WhatsApp Scheduler] No bot instances found")
        return
    
    # Calculate jobs since last summary
    if is_morning:
        # Overnight: jobs since last 6 PM (or all if first time)
        last_key = "jobs_at_6pm"
        title = "🌅 *Morning Summary - Overnight Results*"
        period = "overnight"
    else:
        # End of day: jobs since last 9 AM (or all if first time)
        last_key = "jobs_at_9am"
        title = "🌆 *End of Day Summary*"
        period = "today"
    
    last_jobs = state.get(last_key, {})
    total_new_jobs = 0
    total_all_jobs = sum(s["jobs"] for s in summaries)
    running_bots = [s for s in summaries if s["status"] == "running"]
    
    # Build message
    message = f"""{title}

📊 *Jobs Applied {period.capitalize()}:* """
    
    # Calculate new jobs per instance
    new_jobs_list = []
    for summary in summaries:
        instance_name = summary["name"]
        current_jobs = summary["jobs"]
        last_jobs_count = last_jobs.get(instance_name, 0)
        new_jobs = max(0, current_jobs - last_jobs_count)
        total_new_jobs += new_jobs
        new_jobs_list.append((summary, new_jobs))
    
    message += f"{total_new_jobs}\n"
    message += f"📈 *Total Jobs (All Time):* {total_all_jobs}\n"
    message += f"🤖 *Active Bots:* {len(running_bots)}/{len(summaries)}\n"
    
    # Check for bots needing attention
    attention_bots = [s for s in summaries if s.get("needs_attention", False)]
    if attention_bots:
        message += f"⚠️ *Bots Needing Attention:* {len(attention_bots)}\n"
    
    message += "\n"
    
    # Add per-bot breakdown with health status
    for summary, new_jobs in new_jobs_list:
        health_icon = summary.get("health_icon", "🟡")
        health_text = summary.get("health_text", "Unknown")
        message += f"{health_icon} *{summary['profile']}* ({summary['name']}):\n"
        message += f"   • Status: {health_text}\n"
        message += f"   • {period.capitalize()}: {new_jobs} jobs\n"
        message += f"   • Total: {summary['jobs']} jobs\n\n"
    
    message += f"📅 {datetime.now().strftime('%I:%M %p, %d %b %Y')}"
    message += "\n\nKeep up the great work! 💪"
    
    # Update state
    now = datetime.now().isoformat()
    if is_morning:
        state["last_9am"] = now
        state["jobs_at_9am"] = {s["name"]: s["jobs"] for s in summaries}
    else:
        state["last_6pm"] = now
        state["jobs_at_6pm"] = {s["name"]: s["jobs"] for s in summaries}
    save_summary_state(state)
    
    # Send to all configured phones
    sent = False
    for phone in PROFILE_PHONES.values():
        if send_whatsapp_message(phone, message):
            sent = True
    
    # Also send to default phone if not in profile phones
    if not sent and DEFAULT_PHONE:
        send_whatsapp_message(DEFAULT_PHONE, message)

def scheduler_loop():
    """Main scheduler loop - checks time and sends summaries"""
    last_9am = None
    last_6pm = None
    
    print("[WhatsApp Scheduler] Started - Will send summaries at 9 AM and 6 PM")
    
    while True:
        now = datetime.now()
        current_hour = now.hour
        current_minute = now.minute
        
        # Check for 9 AM (morning summary)
        if current_hour == 9 and current_minute == 0:
            if last_9am is None or (now - last_9am).total_seconds() > 3600:  # At least 1 hour since last
                print(f"[WhatsApp Scheduler] Sending morning summary at {now.strftime('%I:%M %p')}")
                send_daily_summary(is_morning=True)
                last_9am = now
        
        # Check for 6 PM (evening summary)
        elif current_hour == 18 and current_minute == 0:
            if last_6pm is None or (now - last_6pm).total_seconds() > 3600:  # At least 1 hour since last
                print(f"[WhatsApp Scheduler] Sending evening summary at {now.strftime('%I:%M %p')}")
                send_daily_summary(is_morning=False)
                last_6pm = now
        
        # Sleep for 1 minute
        time.sleep(60)

def run_scheduler():
    """Run the scheduler in a background thread"""
    thread = threading.Thread(target=scheduler_loop, daemon=True)
    thread.start()
    print("[WhatsApp Scheduler] Background thread started")
    return thread

if __name__ == "__main__":
    # Run scheduler
    scheduler_loop()

