# How to View Your Bot's Activity (Logs)

Since your bot runs in **headless mode** on the VPS (no visible browser), you see its activity through **logs**.

## Real-Time Log Viewing

### In your SSH session, run:

```bash
sudo journalctl -u seekmateai -f
```

This shows:
- ✅ Real-time activity as it happens
- ✅ Which city it's searching (Brisbane → Gold Coast → Sydney → Melbourne)
- ✅ Which jobs it's finding and applying to
- ✅ Daily job count
- ✅ Any errors or issues

**Press `Ctrl+C` to stop viewing** (the bot keeps running)

---

## Other Useful Log Commands

### View last 100 lines:
```bash
sudo journalctl -u seekmateai -n 100
```

### View logs from today:
```bash
sudo journalctl -u seekmateai --since today
```

### View logs from last hour:
```bash
sudo journalctl -u seekmateai --since "1 hour ago"
```

### Export logs to file:
```bash
sudo journalctl -u seekmateai > ~/bot_logs.txt
```

---

## What You'll See in Logs

- **City rotation:** `[*] 🌍 Searching in: Brisbane, Australia`
- **Job applications:** `[*] Job 1: Director | Company Name`
- **Progress:** `Progress: 5/100 applications`
- **Daily count:** `Daily jobs so far: 15/100`
- **Mode:** `⚡ LOOSE MODE` messages
- **Errors:** Any issues will appear here

---

## Alternative: Check Log File

The bot also writes to a local log file:

```bash
cd ~/seekmateai
tail -f continuous_runner.log
```

Or view the main bot log:

```bash
cat ~/.local/share/SeekMateAI/log.txt
# or
cat log.txt
```

