# SeekMateAI Deployment - Complete Step-by-Step Guide

Follow these steps in order. Check off each step as you complete it.

---

## 📍 STEP 1: Create DigitalOcean Account (if not done)

- [ ] Go to https://www.digitalocean.com
- [ ] Click "Sign Up" 
- [ ] Enter your email and create account
- [ ] Verify your email
- [ ] Add payment method (credit card or PayPal)
- [ ] You should see the DigitalOcean dashboard

---

## 📍 STEP 2: Create a Droplet (VPS)

- [ ] On DigitalOcean dashboard, click **"Create"** button (top right)
- [ ] Select **"Droplets"** from dropdown
- [ ] On the Create Droplet page, configure:

### 2.1 Choose an image
- [ ] Click **"Ubuntu"** tab
- [ ] Select **"Ubuntu 22.04 (LTS) x64"** ✅

### 2.2 Choose a plan
- [ ] Click **"Basic"** tab (should be selected by default)
- [ ] Select **"Regular Intel with SSD"**
- [ ] Choose **$12/month** plan:
  - 2 GB RAM / 1 vCPU
  - 50 GB SSD Disk
  - 3 TB Transfer
- [ ] *(Optional: Choose $18/month for better performance)*

### 2.3 Choose a datacenter region
- [ ] Select region closest to you (e.g., New York, San Francisco, London)

### 2.4 Authentication
- [ ] **Option A (Recommended):** Select SSH key if you have one
  - If you don't have one, we'll use password (Option B)
- [ ] **Option B (Simpler):** Select "Password"
  - Set a strong password (save it somewhere safe!)
  - You'll receive it by email

### 2.5 Finalize
- [ ] **Droplet hostname:** `seekmateai-vps` (or leave default)
- [ ] Leave other options as default
- [ ] Click **"Create Droplet"** button at bottom

### 2.6 Wait for creation
- [ ] Wait 60-90 seconds for Droplet to be created
- [ ] Status will show "Active" with green checkmark when ready

### 2.7 Note your information
- [ ] **Copy your IP address** (e.g., `157.230.123.45`)
  - Found on the Droplet page
- [ ] **Note your password** (if using password auth - check email)

---

## 📍 STEP 3: Connect to Your Server

### On Windows (using PowerShell or Command Prompt):

- [ ] Open **PowerShell** or **Command Prompt**
- [ ] Type this command (replace with YOUR IP):
  ```bash
  ssh root@YOUR_IP_ADDRESS
  ```
- [ ] Example: `ssh root@157.230.123.45`
- [ ] First time: Type `yes` when asked about security
- [ ] Enter password when prompted (if using password auth)
- [ ] You should see: `root@seekmateai-vps:~#`

✅ **You're now connected to your server!**

---

## 📍 STEP 4: Run Setup Script

While connected via SSH, run these commands:

- [ ] Update system packages:
  ```bash
  apt update && apt upgrade -y
  ```

- [ ] Install essential tools:
  ```bash
  apt install -y python3 python3-pip python3-venv git wget curl gnupg ca-certificates fonts-liberation libasound2 libatk-bridge2.0-0 libatk1.0-0 libatspi2.0-0 libcups2 libdbus-1-3 libdrm2 libgbm1 libgtk-3-0 libnspr4 libnss3 libwayland-client0 libxcomposite1 libxdamage1 libxfixes3 libxkbcommon0 libxrandr2 xdg-utils unzip htop
  ```

- [ ] Install Google Chrome:
  ```bash
  wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | apt-key add -
  echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" | tee /etc/apt/sources.list.d/google-chrome.list
  apt update
  apt install -y google-chrome-stable
  ```

- [ ] Verify Chrome installed:
  ```bash
  google-chrome --version
  ```
  - [ ] Should show Chrome version number

- [ ] Create application directory:
  ```bash
  mkdir -p ~/seekmateai
  cd ~/seekmateai
  ```

- [ ] Create Python virtual environment:
  ```bash
  python3 -m venv venv
  source venv/bin/activate
  ```

- [ ] Upgrade pip:
  ```bash
  pip install --upgrade pip
  ```

✅ **Server is now set up!**

---

## 📍 STEP 5: Upload Your Code

### Option A: Using SCP (from your local Windows computer)

**Open a NEW PowerShell/Command Prompt window** (keep SSH session open):

- [ ] Navigate to your SeekMateAI folder:
  ```bash
  cd C:\Users\user\Documents\SeekMateAI
  ```

- [ ] Upload all necessary files:
  ```bash
  scp *.py root@YOUR_IP_ADDRESS:~/seekmateai/
  scp *.json root@YOUR_IP_ADDRESS:~/seekmateai/
  scp *.txt root@YOUR_IP_ADDRESS:~/seekmateai/
  scp requirements.txt root@YOUR_IP_ADDRESS:~/seekmateai/
  scp run_continuous.py root@YOUR_IP_ADDRESS:~/seekmateai/
  scp seekmateai.service root@YOUR_IP_ADDRESS:~/seekmateai/
  ```
  Replace `YOUR_IP_ADDRESS` with your actual IP

- [ ] Enter password when prompted (if using password auth)

### Option B: Manual file creation (if SCP doesn't work)

Go back to your SSH session:

- [ ] Create files one by one using nano editor:
  ```bash
  cd ~/seekmateai
  nano main.py
  ```
  - Paste your main.py content
  - Press `Ctrl+X`, then `Y`, then `Enter` to save
  - Repeat for each file needed

✅ **Files uploaded!**

---

## 📍 STEP 6: Install Python Dependencies

Back in your SSH session:

- [ ] Make sure you're in the right directory:
  ```bash
  cd ~/seekmateai
  source venv/bin/activate
  ```

- [ ] Install requirements:
  ```bash
  pip install -r requirements.txt
  ```
  - [ ] Wait for installation to complete (may take 2-3 minutes)

- [ ] Verify key packages installed:
  ```bash
  pip list | grep selenium
  pip list | grep openai
  ```
  - [ ] Should show package versions

✅ **Dependencies installed!**

---

## 📍 STEP 7: Configure Your Bot

- [ ] Edit config.json:
  ```bash
  nano config.json
  ```

- [ ] Fill in all required settings:
  - [ ] SEEK_EMAIL (your Seek account email)
  - [ ] JOB_TITLE
  - [ ] CV_PATH (path to your resume)
  - [ ] OPENAI_API_KEY
  - [ ] MAX_JOBS
  - [ ] LOCATION
  - [ ] All other settings from your local config

- [ ] Save: `Ctrl+X`, then `Y`, then `Enter`

- [ ] Create control.json:
  ```bash
  echo '{"pause": false, "stop": false}' > control.json
  ```

- [ ] Set file permissions:
  ```bash
  chmod 644 config.json control.json
  chmod 755 *.py
  ```

✅ **Configuration complete!**

---

## 📍 STEP 8: Test Headless Mode

- [ ] Test the bot manually:
  ```bash
  export RUN_HEADLESS=true
  python main.py
  ```

- [ ] Watch for output - should show:
  - [ ] "[INFO] Running in HEADLESS mode"
  - [ ] Chrome launching (no visible window)
  - [ ] Bot starting operations

- [ ] If you see errors, note them down
- [ ] Press `Ctrl+C` to stop the test

✅ **Headless mode works!**

---

## 📍 STEP 9: Setup Systemd Service (Auto-Start)

- [ ] Copy service file:
  ```bash
  cp seekmateai.service /tmp/seekmateai.service
  ```

- [ ] Edit the service file:
  ```bash
  nano /tmp/seekmateai.service
  ```

- [ ] Update these lines (if your username/paths are different):
  ```ini
  User=root
  WorkingDirectory=/root/seekmateai
  ExecStart=/root/seekmateai/venv/bin/python /root/seekmateai/run_continuous.py
  ```
  *(If using default root user, these should already be correct)*

- [ ] Save: `Ctrl+X`, then `Y`, then `Enter`

- [ ] Move to systemd directory:
  ```bash
  mv /tmp/seekmateai.service /etc/systemd/system/seekmateai.service
  ```

- [ ] Reload systemd:
  ```bash
  systemctl daemon-reload
  ```

- [ ] Enable service (starts on boot):
  ```bash
  systemctl enable seekmateai
  ```

- [ ] Start the service:
  ```bash
  systemctl start seekmateai
  ```

- [ ] Check status:
  ```bash
  systemctl status seekmateai
  ```
  - [ ] Should show "active (running)" in green

✅ **Service is running!**

---

## 📍 STEP 10: Verify Everything Works

- [ ] View real-time logs:
  ```bash
  journalctl -u seekmateai -f
  ```

- [ ] Look for these messages:
  - [ ] "SeekMateAI Continuous Runner started"
  - [ ] "Running in HEADLESS mode"
  - [ ] "Starting cycle #1"
  - [ ] Bot activity messages

- [ ] Press `Ctrl+C` to stop viewing logs

- [ ] Check service is still running:
  ```bash
  systemctl status seekmateai
  ```

- [ ] Test that it restarts on crash:
  ```bash
  systemctl restart seekmateai
  systemctl status seekmateai
  ```
  - [ ] Should restart successfully

✅ **Everything is working!**

---

## 📍 STEP 11: Learn How to Control Your Bot

### View logs anytime:
```bash
journalctl -u seekmateai -f
```

### Pause bot (keeps service running):
```bash
cd ~/seekmateai
echo '{"pause": true, "stop": false}' > control.json
```

### Resume bot:
```bash
cd ~/seekmateai
echo '{"pause": false, "stop": false}' > control.json
```

### Restart service:
```bash
systemctl restart seekmateai
```

### Stop service:
```bash
systemctl stop seekmateai
```

### Start service:
```bash
systemctl start seekmateai
```

---

## 🎉 CONGRATULATIONS!

Your bot is now running 24/7 on your VPS!

### What's happening:
- ✅ Bot runs continuously in headless mode
- ✅ Automatically restarts if it crashes
- ✅ Starts automatically on server reboot
- ✅ All logs saved to systemd journal

### Next steps:
- Monitor logs regularly: `journalctl -u seekmateai -f`
- Check your job_log.xlsx for applications
- The bot will run cycles automatically (default: every 1 hour)

---

## 🆘 Troubleshooting

If something doesn't work:

1. **Check logs:**
   ```bash
   journalctl -u seekmateai -n 50
   ```

2. **Test manually:**
   ```bash
   cd ~/seekmateai
   source venv/bin/activate
   export RUN_HEADLESS=true
   python main.py
   ```

3. **Check service status:**
   ```bash
   systemctl status seekmateai
   ```

4. **Restart service:**
   ```bash
   systemctl restart seekmateai
   ```

---

**Need help?** Review `DEPLOYMENT_PLAN.md` for detailed troubleshooting!

