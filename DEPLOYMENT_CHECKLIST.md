# SeekMateAI VPS Deployment Checklist

Use this checklist to ensure you complete all necessary steps for deployment.

## Pre-Deployment

- [ ] Read `DEPLOYMENT_PLAN.md` thoroughly
- [ ] Selected and provisioned VPS (Ubuntu 22.04 LTS recommended)
- [ ] Have SSH access to the VPS
- [ ] Have your `config.json` file ready with all settings
- [ ] Have your API keys (OpenAI, etc.) ready

## Phase 1: Initial Setup

- [ ] Connected to VPS via SSH
- [ ] Created non-root user (optional but recommended)
  ```bash
  adduser seekmate
  usermod -aG sudo seekmate
  ```
- [ ] Updated system packages
  ```bash
  sudo apt update && sudo apt upgrade -y
  ```

## Phase 2: Install Dependencies

- [ ] Ran `server_setup.sh` script OR manually installed:
  - [ ] Python 3 and pip
  - [ ] Google Chrome browser
  - [ ] All system dependencies
- [ ] Verified Chrome installation
  ```bash
  google-chrome --version
  ```

## Phase 3: Deploy Code

- [ ] Created application directory: `~/seekmateai`
- [ ] Uploaded all application files to server
  - [ ] All `.py` files
  - [ ] `requirements.txt`
  - [ ] `config.json` (with your settings)
  - [ ] `run_continuous.py`
  - [ ] `seekmateai.service`
- [ ] Created Python virtual environment
  ```bash
  python3 -m venv venv
  source venv/bin/activate
  ```
- [ ] Installed Python dependencies
  ```bash
  pip install -r requirements.txt
  ```

## Phase 4: Configuration

- [ ] Created/uploaded `config.json` with all settings:
  - [ ] SEEK_EMAIL
  - [ ] JOB_TITLE
  - [ ] CV_PATH (or uploaded resume file)
  - [ ] OPENAI_API_KEY
  - [ ] MAX_JOBS
  - [ ] LOCATION
  - [ ] All other required settings
- [ ] Created `control.json`
  ```bash
  echo '{"pause": false, "stop": false}' > control.json
  ```
- [ ] Set proper file permissions
  ```bash
  chmod 644 config.json control.json
  chmod 755 *.py
  ```

## Phase 5: Testing

- [ ] Tested headless mode manually
  ```bash
  cd ~/seekmateai
  source venv/bin/activate
  export RUN_HEADLESS=true
  python main.py
  ```
- [ ] Verified bot starts and runs without errors
- [ ] Checked that Chrome runs in headless mode
- [ ] Verified config.json is being read correctly

## Phase 6: Systemd Service Setup

- [ ] Edited `seekmateai.service` to match your setup:
  - [ ] Updated `User=` to your username
  - [ ] Updated `WorkingDirectory=` path
  - [ ] Updated `ExecStart=` path
- [ ] Copied service file to systemd directory
  ```bash
  sudo cp seekmateai.service /etc/systemd/system/
  ```
- [ ] Reloaded systemd daemon
  ```bash
  sudo systemctl daemon-reload
  ```
- [ ] Enabled service to start on boot
  ```bash
  sudo systemctl enable seekmateai
  ```
- [ ] Started the service
  ```bash
  sudo systemctl start seekmateai
  ```
- [ ] Checked service status
  ```bash
  sudo systemctl status seekmateai
  ```
- [ ] Verified service is running (should show "active (running)")

## Phase 7: Verification

- [ ] Service starts automatically on server reboot
- [ ] Bot logs are being written
  ```bash
  sudo journalctl -u seekmateai -f
  ```
- [ ] Bot is running cycles (check for "Starting cycle #" in logs)
- [ ] No errors in logs
- [ ] Job applications are being processed (check job_log.xlsx if applicable)

## Phase 8: Security

- [ ] Configured firewall (optional but recommended)
  ```bash
  sudo ufw allow 22/tcp  # SSH
  sudo ufw enable
  ```
- [ ] Set up SSH key authentication (optional but recommended)
- [ ] Secured config.json with proper permissions
  ```bash
  chmod 600 config.json  # Only owner can read/write
  ```
- [ ] Verified no sensitive data in logs

## Phase 9: Monitoring Setup

- [ ] Know how to view logs
  ```bash
  sudo journalctl -u seekmateai -f
  ```
- [ ] Know how to check status
  ```bash
  sudo systemctl status seekmateai
  ```
- [ ] Know how to restart service
  ```bash
  sudo systemctl restart seekmateai
  ```
- [ ] Know how to pause/resume bot (using control.json)

## Post-Deployment

- [ ] Monitored bot for first 24 hours
- [ ] Verified bot restarts after crashes (systemd Restart=always)
- [ ] Set up regular backup schedule for:
  - [ ] config.json
  - [ ] control.json
  - [ ] job_log.xlsx
  - [ ] Log files
- [ ] Documented any custom configurations
- [ ] Tested pause/resume functionality
- [ ] Tested stop functionality

## Troubleshooting Preparedness

- [ ] Know how to access VPS logs
- [ ] Know how to manually test the bot
- [ ] Know how to check resource usage (htop)
- [ ] Have backup of config.json
- [ ] Understand service restart behavior

---

## Quick Reference Commands

```bash
# View logs
sudo journalctl -u seekmateai -f

# Restart service
sudo systemctl restart seekmateai

# Check status
sudo systemctl status seekmateai

# Pause bot (keeps service running)
cd ~/seekmateai && echo '{"pause": true, "stop": false}' > control.json

# Resume bot
cd ~/seekmateai && echo '{"pause": false, "stop": false}' > control.json
```

---

**Deployment Date**: ________________

**VPS Provider**: ________________

**Server IP**: ________________

**Notes**:
- 
- 
- 

