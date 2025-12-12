# Upload Updated Files to VPS

## Quick Steps

### Step 1: Upload Updated Files

Open **PowerShell** on your Windows machine and run these commands:

```powershell
# Navigate to your SeekMateAI folder
cd C:\Users\user\Documents\SeekMateAI

# Upload the three updated files
scp config.json root@170.64.213.197:~/seekmateai/
scp main.py root@170.64.213.197:~/seekmateai/
scp run_continuous.py root@170.64.213.197:~/seekmateai/
```

**When prompted, enter password:** `1988Williams`

---

### Step 2: Verify Files on VPS

Connect to your VPS via SSH:

```powershell
ssh root@170.64.213.197
```

Enter password: `1988Williams`

Then verify files are uploaded:

```bash
cd ~/seekmateai
ls -la config.json main.py run_continuous.py
```

You should see all three files with recent timestamps.

---

### Step 3: Restart the Service

While still connected via SSH:

```bash
# Restart the systemd service to use new code
sudo systemctl restart seekmateai

# Check status
sudo systemctl status seekmateai

# View logs to verify it's working
sudo journalctl -u seekmateai -f
```

---

### Step 4: Verify New Configuration

In the logs, you should see:
- `LOOSE MODE` messages
- City rotation: Brisbane → Gold Coast → Sydney → Melbourne
- Daily job count tracking
- Speed set to 8 (safe mode)

---

## Alternative: If Service Not Set Up Yet

If you haven't set up the systemd service yet, you can test manually first:

```bash
cd ~/seekmateai
source venv/bin/activate
export RUN_HEADLESS=true
python run_continuous.py
```

Then press `Ctrl+C` to stop, and proceed with setting up the systemd service.

---

## Troubleshooting

If upload fails:
- Make sure you're in the right directory on Windows
- Check your VPS IP is correct (170.64.213.197)
- Verify SSH connection works: `ssh root@170.64.213.197`

If service won't restart:
- Check file permissions: `chmod 644 *.py *.json`
- Check service logs: `sudo journalctl -u seekmateai -n 50`

