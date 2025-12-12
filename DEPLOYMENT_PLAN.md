# SeekMateAI VPS Deployment Plan - Option A

## 📋 Overview
This guide will help you deploy SeekMateAI on a Linux VPS for 24/7 automated operation.

---

## 🎯 Prerequisites

### VPS Requirements
- **OS**: Ubuntu 22.04 LTS (recommended) or Debian 11+
- **RAM**: Minimum 2GB (4GB recommended)
- **CPU**: 2 vCPU cores minimum
- **Storage**: 20GB+ SSD
- **Network**: Stable internet connection

### Recommended VPS Providers
1. **DigitalOcean** - $12/month (2GB RAM, 1 vCPU)
2. **Linode** - $12/month (2GB RAM, 1 vCPU)
3. **Vultr** - $12/month (2GB RAM, 1 vCPU)
4. **AWS EC2** - t3.small instance
5. **Hetzner** - €5.83/month (2GB RAM, 1 vCPU)

---

## 📦 Phase 1: Initial VPS Setup

### Step 1.1: Provision Your VPS
1. Sign up with your chosen VPS provider
2. Create a new droplet/server with Ubuntu 22.04 LTS
3. Note your server IP address
4. Set up SSH key authentication (recommended) or note root password

### Step 1.2: Initial Server Configuration
```bash
# Connect to your server
ssh root@YOUR_SERVER_IP

# Update system packages
apt update && apt upgrade -y

# Create a non-root user (recommended for security)
adduser seekmate
usermod -aG sudo seekmate

# Switch to new user
su - seekmate
```

### Step 1.3: Install Required System Packages
```bash
# Install essential tools
sudo apt install -y \
    python3 \
    python3-pip \
    python3-venv \
    git \
    wget \
    curl \
    gnupg \
    ca-certificates \
    fonts-liberation \
    libasound2 \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libatspi2.0-0 \
    libcups2 \
    libdbus-1-3 \
    libdrm2 \
    libgbm1 \
    libgtk-3-0 \
    libnspr4 \
    libnss3 \
    libwayland-client0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxkbcommon0 \
    libxrandr2 \
    xdg-utils \
    unzip

# Install Chrome browser
wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | sudo apt-key add -
echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" | sudo tee /etc/apt/sources.list.d/google-chrome.list
sudo apt update
sudo apt install -y google-chrome-stable

# Verify Chrome installation
google-chrome --version
```

---

## 📂 Phase 2: Deploy SeekMateAI Code

### Step 2.1: Prepare Code Locally (On Your Computer)

**Option A: Using SCP (Secure Copy)**
```bash
# From your local machine, compress the project (excluding unnecessary files)
cd /path/to/SeekMateAI
tar -czf seekmateai.tar.gz \
    --exclude='__pycache__' \
    --exclude='*.pyc' \
    --exclude='build' \
    --exclude='dist' \
    --exclude='.git' \
    --exclude='chrome_*_profile' \
    *.py *.json *.txt *.png *.ico *.spec requirements.txt

# Upload to server
scp seekmateai.tar.gz seekmate@YOUR_SERVER_IP:~/
```

**Option B: Using Git (Recommended)**
```bash
# If your code is in a Git repository
# On server:
cd ~
git clone YOUR_REPOSITORY_URL seekmateai
cd seekmateai
```

### Step 2.2: Extract and Setup on Server
```bash
# If using SCP/compressed file
cd ~
mkdir -p seekmateai
cd seekmateai
tar -xzf ~/seekmateai.tar.gz

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install Python dependencies
pip install --upgrade pip
pip install -r requirements.txt

# Verify installation
python --version
pip list
```

### Step 2.3: Configure Application

```bash
# Copy your config files (if you uploaded them)
# Or create them manually:

# Create config.json with your settings
nano config.json
# Paste your configuration from local machine

# Create control.json
echo '{"pause": false, "stop": false}' > control.json

# Set proper permissions
chmod 644 config.json control.json
```

---

## 🔧 Phase 3: Setup Continuous Runner

### Step 3.1: Verify Code Changes
The deployment includes:
- ✅ Headless mode support in `main.py`
- ✅ Headless mode support in `indeed_bot.py`
- ✅ `run_continuous.py` script for 24/7 operation

### Step 3.2: Test Headless Mode
```bash
cd ~/seekmateai
source venv/bin/activate

# Test run in headless mode
export RUN_HEADLESS=true
python main.py

# If it works, you're good to proceed
```

---

## 🚀 Phase 4: Setup Systemd Service (Auto-start on Boot)

### Step 4.1: Create Service File
```bash
sudo nano /etc/systemd/system/seekmateai.service
```

**Paste the following (adjust paths to match your setup):**
```ini
[Unit]
Description=SeekMateAI Continuous Runner - 24/7 Job Application Bot
After=network.target

[Service]
Type=simple
User=seekmate
Group=seekmate
WorkingDirectory=/home/seekmate/seekmateai
Environment="PATH=/home/seekmate/seekmateai/venv/bin:/usr/local/bin:/usr/bin:/bin"
Environment="RUN_HEADLESS=true"
Environment="DISPLAY=:99"

ExecStart=/home/seekmate/seekmateai/venv/bin/python /home/seekmate/seekmateai/run_continuous.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

# Security settings
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
```

### Step 4.2: Enable and Start Service
```bash
# Reload systemd
sudo systemctl daemon-reload

# Enable service to start on boot
sudo systemctl enable seekmateai

# Start the service
sudo systemctl start seekmateai

# Check status
sudo systemctl status seekmateai

# View logs
sudo journalctl -u seekmateai -f
```

---

## 📊 Phase 5: Monitoring & Management

### View Logs
```bash
# Real-time logs
sudo journalctl -u seekmateai -f

# Last 100 lines
sudo journalctl -u seekmateai -n 100

# Logs since today
sudo journalctl -u seekmateai --since today

# Export logs to file
sudo journalctl -u seekmateai > ~/seekmateai_logs.txt
```

### Control the Service
```bash
# Start
sudo systemctl start seekmateai

# Stop
sudo systemctl stop seekmateai

# Restart
sudo systemctl restart seekmateai

# Check status
sudo systemctl status seekmateai

# Disable auto-start
sudo systemctl disable seekmateai
```

### Pause/Resume Bot (Without Stopping Service)
```bash
# Pause the bot
cd ~/seekmateai
echo '{"pause": true, "stop": false}' > control.json

# Resume the bot
echo '{"pause": false, "stop": false}' > control.json

# Stop current cycle (will restart)
echo '{"pause": false, "stop": true}' > control.json
```

---

## 🔄 Phase 6: Maintenance & Updates

### Update Application Code
```bash
cd ~/seekmateai
source venv/bin/activate

# If using Git
git pull origin main

# If using SCP, upload new files and extract

# Restart service to apply changes
sudo systemctl restart seekmateai
```

### Update Dependencies
```bash
cd ~/seekmateai
source venv/bin/activate
pip install --upgrade -r requirements.txt
sudo systemctl restart seekmateai
```

### Backup Configuration
```bash
# Create backup directory
mkdir -p ~/backups

# Backup config files
cp ~/seekmateai/config.json ~/backups/config_$(date +%Y%m%d).json
cp ~/seekmateai/control.json ~/backups/control_$(date +%Y%m%d).json
cp ~/seekmateai/job_log.xlsx ~/backups/job_log_$(date +%Y%m%d).xlsx 2>/dev/null || true
```

---

## 🛠️ Troubleshooting

### Service Won't Start
```bash
# Check service status
sudo systemctl status seekmateai

# Check logs for errors
sudo journalctl -u seekmateai -n 50

# Verify Python and dependencies
cd ~/seekmateai
source venv/bin/activate
python --version
python -c "import selenium; print('Selenium OK')"
```

### Chrome Issues
```bash
# Test Chrome installation
google-chrome --version

# Test headless Chrome
google-chrome --headless --no-sandbox --disable-gpu --dump-dom https://www.google.com

# Reinstall Chrome if needed
sudo apt remove google-chrome-stable
sudo apt install google-chrome-stable
```

### Permission Issues
```bash
# Fix ownership
sudo chown -R seekmate:seekmate ~/seekmateai

# Fix permissions
chmod 755 ~/seekmateai
chmod 644 ~/seekmateai/*.json
```

### High Memory Usage
```bash
# Monitor resource usage
htop

# Check bot logs for memory leaks
sudo journalctl -u seekmateai | grep -i "memory\|error"
```

---

## 🔐 Security Considerations

1. **Firewall Setup**
   ```bash
   sudo ufw allow 22/tcp    # SSH
   sudo ufw enable
   ```

2. **SSH Key Authentication** (Recommended)
   ```bash
   # On local machine
   ssh-keygen -t ed25519
   ssh-copy-id seekmate@YOUR_SERVER_IP
   ```

3. **Regular Updates**
   ```bash
   sudo apt update && sudo apt upgrade -y
   ```

4. **Secure API Keys**
   - Never commit API keys to Git
   - Use environment variables for sensitive data
   - Restrict file permissions: `chmod 600 config.json`

---

## 📈 Performance Tuning

### Adjust Cycle Wait Time
Edit `run_continuous.py`:
```python
wait_time = 3600  # Change from 3600 (1 hour) to your preferred interval
```

### Optimize Chrome for VPS
The headless configuration already includes optimizations:
- `--headless=new`: New headless mode (faster)
- `--no-sandbox`: Required for Docker/VPS
- `--disable-dev-shm-usage`: Prevents crashes
- `--disable-gpu`: Not needed headless

---

## ✅ Deployment Checklist

- [ ] VPS provisioned and accessible via SSH
- [ ] System packages installed (Python, Chrome, etc.)
- [ ] Application code uploaded to server
- [ ] Virtual environment created and dependencies installed
- [ ] Config files created/uploaded
- [ ] Headless mode tested successfully
- [ ] Systemd service file created
- [ ] Service enabled and started
- [ ] Logs checked and verified working
- [ ] Firewall configured
- [ ] Backup strategy in place

---

## 🆘 Support

If you encounter issues:
1. Check logs: `sudo journalctl -u seekmateai -f`
2. Test manually: `cd ~/seekmateai && source venv/bin/activate && RUN_HEADLESS=true python main.py`
3. Verify all dependencies are installed
4. Check file permissions

---

## 📝 Notes

- The bot will restart automatically if it crashes (thanks to systemd)
- Service starts automatically on server reboot
- Logs are managed by systemd journal
- Chrome profiles are stored in temp directory (cleared on reboot)
- For persistent Chrome profiles, modify the profile path in code

---

**Last Updated**: 2025-01-27
**Version**: 1.0

