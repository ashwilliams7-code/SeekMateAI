#!/usr/bin/env python3
"""
Slack Bot Responder for SeekMateAI
Chat with your multi-bot dashboard through Slack.

Commands (send in the configured channel):
  status / dashboard    — Show all instance statuses
  start <name>          — Start an instance
  stop <name>           — Stop an instance
  restart <name>        — Restart an instance
  start all             — Start all instances
  stop all              — Stop all instances
  log <name>            — Show last 20 log lines for an instance
  jobs                  — Show job stats across all instances
  help                  — Show available commands

Uses Slack Incoming Webhook for responses and Web API for reading messages.
"""
import os
import sys
import json
import re
import subprocess
import time
import urllib.request
import urllib.parse
from datetime import datetime
from threading import Thread
from dotenv import load_dotenv
load_dotenv()

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
INSTANCES_FILE = os.path.join(SCRIPT_DIR, "bot_instances.json")
BOT_CONFIG_FILE = os.path.join(SCRIPT_DIR, "slack_bot_config.json")


def load_bot_config():
    if os.path.exists(BOT_CONFIG_FILE):
        with open(BOT_CONFIG_FILE, "r") as f:
            return json.load(f)
    return {}


def save_bot_config(config):
    with open(BOT_CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)


def load_instances():
    if not os.path.exists(INSTANCES_FILE):
        return {}
    try:
        with open(INSTANCES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def check_process_alive(pid):
    if not pid:
        return False
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.OpenProcess(0x1000, False, pid)
        if handle:
            exit_code = ctypes.c_ulong()
            kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code))
            kernel32.CloseHandle(handle)
            return exit_code.value == 259
        return False
    except Exception:
        return False


def get_jobs_applied(log_file):
    if not log_file or not os.path.exists(log_file):
        return 0
    try:
        with open(log_file, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
            matches = re.findall(r"Successful submissions:\s*(\d+)", content)
            if matches:
                total = 0
                prev = 0
                for m in matches:
                    val = int(m)
                    if val <= prev:
                        total += prev
                    prev = val
                total += prev
                return total
    except Exception:
        pass
    return 0


def get_jobs_scanned(log_file):
    if not log_file or not os.path.exists(log_file):
        return 0
    try:
        with open(log_file, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
            matches = re.findall(r'\[\*\].*?Job \d+:', content)
            return len(matches)
    except Exception:
        return 0


def get_log_path(info, name):
    log_file = info.get("log_file", os.path.join(SCRIPT_DIR, f"log_{name}.txt"))
    if not os.path.isabs(log_file):
        log_file = os.path.join(SCRIPT_DIR, log_file)
    return log_file


def get_elapsed_time(start_time_str):
    if not start_time_str:
        return "—"
    try:
        start_time = datetime.fromisoformat(start_time_str)
        elapsed = datetime.now() - start_time
        s = int(elapsed.total_seconds())
        h, s = divmod(s, 3600)
        m, s = divmod(s, 60)
        return f"{h:02d}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"
    except Exception:
        return "—"


def find_instance(instances, query):
    query_lower = query.strip().lower()
    for name in instances:
        if name.lower() == query_lower:
            return name
    for name in instances:
        if query_lower in name.lower():
            return name
    return None


def run_launcher(args):
    try:
        result = subprocess.run(
            [sys.executable, os.path.join(SCRIPT_DIR, "multi_bot_launcher.py")] + args,
            capture_output=True, text=True, timeout=15, cwd=SCRIPT_DIR,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        )
        return result.stdout.strip() or result.stderr.strip() or "Done."
    except Exception as e:
        return f"Error: {e}"


def send_webhook(webhook_url, text):
    """Send a message via Slack webhook."""
    payload = json.dumps({"text": text}).encode("utf-8")
    try:
        req = urllib.request.Request(
            webhook_url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=10):
            pass
    except Exception as e:
        print(f"[Slack Bot] Webhook send failed: {e}")


def slack_api(token, method, params=None):
    """Call Slack Web API."""
    url = f"https://slack.com/api/{method}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    try:
        req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        print(f"[Slack API] {method} failed: {e}")
        return {}


# ── Command handlers ─────────────────────────────────────────

def cmd_status():
    instances = load_instances()
    if not instances:
        return "No instances configured."
    lines = ["*SeekMateAI Dashboard*\n"]
    total_applied = 0
    total_scanned = 0
    for name, info in instances.items():
        status = info.get("status", "stopped")
        pid = info.get("process_id")
        if status == "running" and not check_process_alive(pid):
            status = "crashed"
        emoji = {"running": "🟢", "crashed": "🔴", "stopped": "⚪"}.get(status, "⚪")
        log_file = get_log_path(info, name)
        applied = get_jobs_applied(log_file)
        scanned = get_jobs_scanned(log_file)
        elapsed = get_elapsed_time(info.get("start_time", "")) if status == "running" else "—"
        total_applied += applied
        total_scanned += scanned
        lines.append(f"{emoji} *{name}* — {status.capitalize()}")
        lines.append(f"    Scanned: {scanned} | Applied: {applied} | Time: {elapsed}")
    lines.append(f"\n*Totals:* {total_scanned} scanned · {total_applied} applied")
    return "\n".join(lines)


def cmd_start(args):
    if not args:
        return "Usage: `start <instance name>` or `start all`"
    if args.lower() == "all":
        return run_launcher(["start-all"])
    instances = load_instances()
    name = find_instance(instances, args)
    if not name:
        names = ", ".join(instances.keys())
        return f"Instance not found: _{args}_\nAvailable: {names}"
    return run_launcher(["start", name])


def cmd_stop(args):
    if not args:
        return "Usage: `stop <instance name>` or `stop all`"
    if args.lower() == "all":
        return run_launcher(["stop-all"])
    instances = load_instances()
    name = find_instance(instances, args)
    if not name:
        names = ", ".join(instances.keys())
        return f"Instance not found: _{args}_\nAvailable: {names}"
    return run_launcher(["stop", name])


def cmd_restart(args):
    if not args:
        return "Usage: `restart <instance name>`"
    instances = load_instances()
    name = find_instance(instances, args)
    if not name:
        names = ", ".join(instances.keys())
        return f"Instance not found: _{args}_\nAvailable: {names}"
    run_launcher(["stop", name])
    time.sleep(2)
    return run_launcher(["start", name])


def cmd_log(args):
    if not args:
        return "Usage: `log <instance name>`"
    instances = load_instances()
    name = find_instance(instances, args)
    if not name:
        names = ", ".join(instances.keys())
        return f"Instance not found: _{args}_\nAvailable: {names}"
    log_file = get_log_path(instances[name], name)
    if not os.path.exists(log_file):
        return f"No log file for _{name}_."
    try:
        with open(log_file, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
        tail = lines[-20:] if len(lines) > 20 else lines
        text = "".join(tail).strip()
        if len(text) > 2900:
            text = text[-2900:]
        return f"*Log: {name}* (last 20 lines)\n```\n{text}\n```"
    except Exception as e:
        return f"Error reading log: {e}"


def cmd_jobs():
    instances = load_instances()
    if not instances:
        return "No instances configured."
    lines = ["*Job Stats*\n"]
    grand_applied = 0
    grand_scanned = 0
    for name, info in instances.items():
        log_file = get_log_path(info, name)
        applied = get_jobs_applied(log_file)
        scanned = get_jobs_scanned(log_file)
        rate = "—"
        if info.get("status") == "running" and info.get("start_time"):
            try:
                start = datetime.fromisoformat(info["start_time"])
                hours = (datetime.now() - start).total_seconds() / 3600
                if hours > 0:
                    rate = f"{applied / hours:.1f}/hr"
            except Exception:
                pass
        grand_applied += applied
        grand_scanned += scanned
        lines.append(f"• *{name}*: {scanned} scanned, {applied} applied ({rate})")
    lines.append(f"\n*Totals:* {grand_scanned} scanned · {grand_applied} applied")
    return "\n".join(lines)


def cmd_help():
    return """*SeekMateAI Slack Commands*

• `status` — Show all instances
• `start <name>` — Start an instance
• `stop <name>` — Stop an instance
• `restart <name>` — Restart an instance
• `start all` / `stop all` — Start/stop all
• `log <name>` — Last 20 log lines
• `jobs` — Job stats for all instances
• `help` — This message

_Instance names support partial matching (e.g. "main" matches "Ash Williams Main")_"""


def handle_message(text):
    text = text.strip()
    text = re.sub(r"<@[A-Z0-9]+>\s*", "", text).strip()
    if not text:
        return cmd_status()
    parts = text.split(None, 1)
    command = parts[0].lower()
    args = parts[1] if len(parts) > 1 else ""
    commands = {
        "status": lambda: cmd_status(),
        "dashboard": lambda: cmd_status(),
        "start": lambda: cmd_start(args),
        "stop": lambda: cmd_stop(args),
        "restart": lambda: cmd_restart(args),
        "log": lambda: cmd_log(args),
        "logs": lambda: cmd_log(args),
        "jobs": lambda: cmd_jobs(),
        "stats": lambda: cmd_jobs(),
        "help": lambda: cmd_help(),
        "hi": lambda: f"Hey! 👋 I'm your SeekMateAI bot.\n\n{cmd_status()}",
        "hello": lambda: f"Hey! 👋 I'm your SeekMateAI bot.\n\n{cmd_status()}",
    }
    handler = commands.get(command)
    if handler:
        return handler()
    return f"Unknown command: _{command}_\n\nType `help` to see available commands."


def poll_loop(token, webhook_url, channel_id):
    """Poll a Slack channel for new messages and respond via webhook."""
    print(f"[Slack Bot] Polling channel {channel_id} every 3s...")
    last_ts = str(time.time())

    while True:
        try:
            result = slack_api(token, "conversations.history", {
                "channel": channel_id,
                "oldest": last_ts,
                "limit": 5
            })

            if not result.get("ok"):
                err = result.get("error", "unknown")
                if err == "not_in_channel":
                    # Try to join the channel
                    slack_api(token, "conversations.join", {"channel": channel_id})
                print(f"[Slack Bot] API error: {err}")
                time.sleep(5)
                continue

            messages = result.get("messages", [])
            for msg in reversed(messages):
                # Skip bot messages and subtypes
                if msg.get("bot_id") or msg.get("subtype"):
                    continue

                text = msg.get("text", "")
                ts = msg.get("ts", "")

                if float(ts) > float(last_ts):
                    last_ts = ts

                print(f"[Slack Bot] Received: {text}")
                response = handle_message(text)
                send_webhook(webhook_url, response)

            if messages:
                newest_ts = max(m.get("ts", "0") for m in messages)
                if float(newest_ts) > float(last_ts):
                    last_ts = newest_ts

        except Exception as e:
            print(f"[Slack Bot] Poll error: {e}")

        time.sleep(3)


def main():
    config = load_bot_config()
    # Prefer environment variables; fall back to slack_bot_config.json values
    token = os.getenv("SLACK_BOT_TOKEN") or config.get("token", "").strip()
    webhook_url = os.getenv("SLACK_WEBHOOK_URL") or config.get("webhook_url", "").strip()
    channel_id = os.getenv("SLACK_CHANNEL_ID") or config.get("channel_id", "").strip()

    if not token or not webhook_url or not channel_id:
        print("[Slack Bot] Missing config. Set SLACK_BOT_TOKEN, SLACK_WEBHOOK_URL, SLACK_CHANNEL_ID")
        print("  env vars or edit slack_bot_config.json")
        return

    print("[Slack Bot] Starting polling responder...")
    print(f"[Slack Bot] Channel: {channel_id}")
    print(f"[Slack Bot] Webhook: {webhook_url[:50]}...")

    poll_loop(token, webhook_url, channel_id)


if __name__ == "__main__":
    main()
