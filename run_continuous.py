#!/usr/bin/env python3
"""
SeekMateAI Continuous Runner
Runs the bot 24/7 with automatic restarts on completion or errors.
Tracks daily job count (max 100 per 24 hours).

Usage:
    export RUN_HEADLESS=true
    python run_continuous.py
"""

import os
import sys
import time
import subprocess
import signal
from datetime import datetime, timedelta

# Set headless mode for server deployment if not already set
if "RUN_HEADLESS" not in os.environ:
    os.environ["RUN_HEADLESS"] = "true"

# Add current directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Configuration
CYCLE_WAIT_TIME = 3600  # Wait time between cycles in seconds (1 hour default)
LOG_FILE = "continuous_runner.log"
DAILY_JOB_LIMIT = 100  # Max jobs per 24 hours
DAILY_COUNT_FILE = "daily_job_count.json"

def log(message, level="INFO"):
    """Log message with timestamp to both console and file"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_message = f"[{timestamp}] [{level}] {message}"
    
    # Print to console
    print(log_message, flush=True)
    
    # Write to log file
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(log_message + "\n")
    except Exception as e:
        print(f"Warning: Could not write to log file: {e}", flush=True)

def get_daily_job_count():
    """Get current daily job count, reset if new day"""
    try:
        import json
        if os.path.exists(DAILY_COUNT_FILE):
            with open(DAILY_COUNT_FILE, "r") as f:
                data = json.load(f)
                last_date = data.get("date", "")
                count = data.get("count", 0)
                
                # Check if it's a new day
                today = datetime.now().strftime("%Y-%m-%d")
                if last_date == today:
                    return count
                else:
                    # New day, reset count
                    log(f"New day detected ({today}). Resetting daily job count.")
                    return 0
    except Exception as e:
        log(f"Error reading daily count: {e}", "WARNING")
    return 0

def save_daily_job_count(count):
    """Save daily job count"""
    try:
        import json
        today = datetime.now().strftime("%Y-%m-%d")
        with open(DAILY_COUNT_FILE, "w") as f:
            json.dump({"date": today, "count": count}, f)
    except Exception as e:
        log(f"Error saving daily count: {e}", "WARNING")

def check_daily_limit():
    """Check if daily limit reached"""
    current_count = get_daily_job_count()
    if current_count >= DAILY_JOB_LIMIT:
        log(f"Daily job limit reached: {current_count}/{DAILY_JOB_LIMIT}. Waiting until tomorrow...", "WARNING")
        return True
    return False

def update_daily_count(jobs_applied):
    """Update daily job count"""
    if jobs_applied > 0:
        current_count = get_daily_job_count()
        new_count = current_count + jobs_applied
        save_daily_job_count(new_count)
        log(f"Daily job count updated: {new_count}/{DAILY_JOB_LIMIT}", "INFO")

def check_control_file():
    """Check if control.json says to stop"""
    try:
        control_file = "control.json"
        if os.path.exists(control_file):
            import json
            with open(control_file, "r") as f:
                data = json.load(f)
                if data.get("stop", False):
                    return True
    except Exception:
        pass
    return False

def run_bot_cycle():
    """Run one cycle of the bot"""
    try:
        # Check daily limit before starting
        if check_daily_limit():
            return False, "daily_limit_reached"
        
        log("Starting bot cycle...")
        
        # Run main.py as subprocess
        result = subprocess.run(
            [sys.executable, "main.py"],
            cwd=os.path.dirname(os.path.abspath(__file__)),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            universal_newlines=True
        )
        
        # Log output
        if result.stdout:
            for line in result.stdout.splitlines():
                if line.strip():
                    log(f"Bot: {line}", "OUTPUT")
        
        # Try to extract job count from output (look for "Successfully submitted X")
        jobs_applied = 0
        if result.stdout:
            import re
            # Look for pattern like "Successfully submitted X REAL applications"
            match = re.search(r'Successfully submitted (\d+)', result.stdout, re.IGNORECASE)
            if match:
                jobs_applied = int(match.group(1))
                update_daily_count(jobs_applied)
        
        success = result.returncode == 0
        return success, result.returncode
        
    except KeyboardInterrupt:
        log("Bot cycle interrupted by user", "WARNING")
        return False, -1
    except Exception as e:
        log(f"Error running bot: {e}", "ERROR")
        import traceback
        log(traceback.format_exc(), "ERROR")
        return False, -2

def main():
    """Main loop - runs bot continuously"""
    log("=" * 60)
    log("SeekMateAI Continuous Runner started")
    log(f"Running in HEADLESS mode: {os.getenv('RUN_HEADLESS', 'false')}")
    log(f"Daily job limit: {DAILY_JOB_LIMIT} per 24 hours")
    log(f"Cycle wait time: {CYCLE_WAIT_TIME} seconds ({CYCLE_WAIT_TIME/60:.1f} minutes)")
    log("=" * 60)
    
    # Handle shutdown gracefully
    shutdown = False
    def signal_handler(sig, frame):
        nonlocal shutdown
        log("Shutdown signal received, finishing current cycle...", "WARNING")
        shutdown = True
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    cycle_count = 0
    
    while not shutdown:
        cycle_count += 1
        log("")
        log("=" * 60)
        log(f"Starting cycle #{cycle_count}")
        current_daily_count = get_daily_job_count()
        log(f"Daily jobs so far: {current_daily_count}/{DAILY_JOB_LIMIT}")
        log("=" * 60)
        
        # Check control file for stop signal
        if check_control_file():
            log("Stop signal detected in control.json, shutting down...", "WARNING")
            break
        
        # Check daily limit
        if check_daily_limit():
            # Wait until tomorrow (midnight)
            now = datetime.now()
            tomorrow = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
            wait_seconds = (tomorrow - now).total_seconds()
            wait_hours = wait_seconds / 3600
            log(f"Daily limit reached. Waiting {wait_hours:.1f} hours until midnight reset...")
            
            # Check every hour for shutdown/control signals
            while wait_seconds > 0 and not shutdown:
                sleep_time = min(3600, wait_seconds)  # Check every hour
                waited = 0
                while waited < sleep_time and not shutdown:
                    if check_control_file():
                        shutdown = True
                        break
                    time.sleep(60)  # Check every minute
                    waited += 60
                    wait_seconds -= 60
                
                # Reset check after hour
                if not shutdown:
                    current_daily_count = get_daily_job_count()  # Re-check in case day changed
                    if current_daily_count < DAILY_JOB_LIMIT:
                        log("Daily limit reset (new day detected). Resuming...")
                        break
            
            if shutdown:
                break
            continue  # Start new cycle after limit reset
        
        # Run bot cycle
        success, return_code = run_bot_cycle()
        
        if success:
            log(f"Bot cycle #{cycle_count} completed successfully")
        else:
            if return_code == "daily_limit_reached":
                log(f"Daily limit reached during cycle, will wait until tomorrow")
            else:
                log(f"Bot cycle #{cycle_count} encountered an error (exit code: {return_code})", "WARNING")
        
        if shutdown:
            break
        
        # Wait before next cycle (with shutdown checks)
        log(f"Waiting {CYCLE_WAIT_TIME/60:.1f} minutes before next cycle...")
        log("(Press Ctrl+C to stop)")
        
        # Check for shutdown every 10 seconds during wait
        wait_interval = 10
        waited = 0
        while waited < CYCLE_WAIT_TIME and not shutdown:
            if check_control_file():
                log("Stop signal detected in control.json during wait, shutting down...", "WARNING")
                shutdown = True
                break
            time.sleep(min(wait_interval, CYCLE_WAIT_TIME - waited))
            waited += wait_interval
    
    log("")
    log("=" * 60)
    log("Continuous runner stopped")
    log("=" * 60)

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        log(f"Fatal error in continuous runner: {e}", "ERROR")
        import traceback
        log(traceback.format_exc(), "ERROR")
        sys.exit(1)
