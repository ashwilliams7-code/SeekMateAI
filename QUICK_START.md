# SeekMateAI VPS Quick Start Guide

## 🚀 Fast Deployment (5 Steps)

### Step 1: Get Your VPS
- Sign up with DigitalOcean/Linode/Vultr
- Create Ubuntu 22.04 LTS server (2GB RAM minimum)
- Note your server IP address

**📘 For DigitalOcean users:** See `DIGITALOCEAN_SETUP.md` for detailed step-by-step Droplet creation guide

### Step 2: Connect to Server
```bash
ssh root@YOUR_SERVER_IP
# Or if using a user:
ssh your_username@YOUR_SERVER_IP
```

### Step 3: Run Setup Script
```bash
# Download and run the setup script
wget https://raw.githubusercontent.com/YOUR_REPO/SeekMateAI/main/server_setup.sh
chmod +x server_setup.sh
bash server_setup.sh
```

### Step 4: Upload Your Code

**Option A: Using SCP (from your local machine)**
```bash
cd /path/to/SeekMateAI
scp -r *.py *.json *.txt requirements.txt seekmateai.service run_continuous.py user@SERVER_IP:~/seekmateai/
```

**Option B: Using Git**
```bash
cd ~/seekmateai
git clone YOUR_REPO_URL .
```

### Step 5: Configure & Start

```bash
cd ~/seekmateai

# Activate virtual environment
source venv/bin/activate

# Install dependencies (if not already done)
pip install -r requirements.txt

# Create/edit config.json with your settings
nano config.json

# Test headless mode
export RUN_HEADLESS=true
python main.py

# If test works, set up systemd service
sudo cp seekmateai.service /etc/systemd/system/
# Edit the service file to match your username:
sudo nano /etc/systemd/system/seekmateai.service

# Enable and start
sudo systemctl daemon-reload
sudo systemctl enable seekmateai
sudo systemctl start seekmateai

# Check status
sudo systemctl status seekmateai
```

## 📊 Monitor Your Bot

```bash
# View logs in real-time
sudo journalctl -u seekmateai -f

# Check status
sudo systemctl status seekmateai

# Pause bot (keeps service running)
cd ~/seekmateai
echo '{"pause": true, "stop": false}' > control.json

# Resume bot
echo '{"pause": false, "stop": false}' > control.json
```

## 🛠️ Common Commands

```bash
# Restart service
sudo systemctl restart seekmateai

# Stop service
sudo systemctl stop seekmateai

# Start service
sudo systemctl start seekmateai

# View last 50 log lines
sudo journalctl -u seekmateai -n 50
```

## ✅ Verify It's Working

1. Check service status: `sudo systemctl status seekmateai`
2. Check logs: `sudo journalctl -u seekmateai -f`
3. Look for "Starting bot cycle..." messages
4. Check job_log.xlsx for new entries

---

For detailed instructions, see `DEPLOYMENT_PLAN.md`

