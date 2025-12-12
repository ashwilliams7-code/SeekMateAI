# SeekMateAI VPS Deployment - Complete Guide

## 📚 Documentation Overview

This deployment package includes everything you need to run SeekMateAI 24/7 on a Linux VPS.

### Files Included

1. **DEPLOYMENT_PLAN.md** - Comprehensive step-by-step deployment guide
2. **QUICK_START.md** - Fast 5-step deployment guide
3. **DEPLOYMENT_CHECKLIST.md** - Checklist to track your progress
4. **seekmateai.service** - Systemd service file template
5. **server_setup.sh** - Automated server setup script
6. **run_continuous.py** - Continuous runner script for 24/7 operation

### Code Changes Made

The following files have been updated to support headless mode:

- ✅ `main.py` - Added headless browser support
- ✅ `indeed_bot.py` - Added headless browser support  
- ✅ `gmail_cleanup.py` - Added headless browser support

## 🚀 Quick Start

1. Read **QUICK_START.md** for fastest deployment
2. Use **DEPLOYMENT_CHECKLIST.md** to track progress
3. Refer to **DEPLOYMENT_PLAN.md** for detailed explanations

## 📋 Deployment Steps Summary

### 1. Get a VPS
- Minimum: 2GB RAM, 2 vCPU, Ubuntu 22.04 LTS
- Cost: ~$12/month (DigitalOcean, Linode, Vultr)

### 2. Run Setup Script
```bash
bash server_setup.sh
```

### 3. Upload Code
Upload all files to `~/seekmateai/` on your VPS

### 4. Configure
- Copy your `config.json` with settings
- Create `control.json`

### 5. Test
```bash
export RUN_HEADLESS=true
python main.py
```

### 6. Enable Service
```bash
sudo cp seekmateai.service /etc/systemd/system/
sudo systemctl enable seekmateai
sudo systemctl start seekmateai
```

### 7. Monitor
```bash
sudo journalctl -u seekmateai -f
```

## 🔧 How It Works

### Headless Mode
- Set via `RUN_HEADLESS=true` environment variable
- Chrome runs without display (required for servers)
- All browser functionality preserved

### Continuous Runner
- `run_continuous.py` runs bot in infinite loop
- Automatic restarts on completion
- Handles crashes gracefully
- Respects `control.json` for pause/stop

### Systemd Service
- Auto-starts on server boot
- Auto-restarts on crash (10 second delay)
- Logs to systemd journal
- Runs in background

## 📊 Monitoring

### View Logs
```bash
# Real-time
sudo journalctl -u seekmateai -f

# Last 100 lines
sudo journalctl -u seekmateai -n 100

# Since today
sudo journalctl -u seekmateai --since today
```

### Control Bot
```bash
# Pause (keeps service running)
echo '{"pause": true, "stop": false}' > ~/seekmateai/control.json

# Resume
echo '{"pause": false, "stop": false}' > ~/seekmateai/control.json

# Restart service
sudo systemctl restart seekmateai
```

## 🔄 Maintenance

### Update Code
```bash
cd ~/seekmateai
# Pull latest code or upload new files
sudo systemctl restart seekmateai
```

### Update Dependencies
```bash
cd ~/seekmateai
source venv/bin/activate
pip install --upgrade -r requirements.txt
sudo systemctl restart seekmateai
```

### Backup
```bash
# Backup config and logs
cp ~/seekmateai/config.json ~/backups/
cp ~/seekmateai/job_log.xlsx ~/backups/
```

## ⚙️ Configuration

### Cycle Wait Time
Edit `run_continuous.py`:
```python
CYCLE_WAIT_TIME = 3600  # Seconds between cycles (default: 1 hour)
```

### Service Settings
Edit `/etc/systemd/system/seekmateai.service`:
- Update `User=` to your username
- Update paths if different from `~/seekmateai`

## 🛠️ Troubleshooting

### Service Won't Start
```bash
# Check logs
sudo journalctl -u seekmateai -n 50

# Test manually
cd ~/seekmateai
source venv/bin/activate
export RUN_HEADLESS=true
python main.py
```

### Chrome Issues
```bash
# Test Chrome
google-chrome --headless --no-sandbox --disable-gpu --dump-dom https://www.google.com

# Reinstall if needed
sudo apt remove google-chrome-stable
sudo apt install google-chrome-stable
```

### Permission Issues
```bash
# Fix ownership
sudo chown -R $USER:$USER ~/seekmateai

# Fix permissions
chmod 755 ~/seekmateai
chmod 644 ~/seekmateai/*.json
```

## 📞 Support

- Check logs first: `sudo journalctl -u seekmateai -f`
- Verify all dependencies installed
- Test headless mode manually
- Review DEPLOYMENT_PLAN.md for detailed troubleshooting

## ✅ Verification

Your deployment is successful when:
- ✅ Service status shows "active (running)"
- ✅ Logs show "Starting cycle #1", "#2", etc.
- ✅ No errors in logs
- ✅ Bot processes jobs (check job_log.xlsx)
- ✅ Service survives server reboot

---

**Ready to deploy?** Start with **QUICK_START.md** or follow **DEPLOYMENT_PLAN.md** for detailed instructions!

