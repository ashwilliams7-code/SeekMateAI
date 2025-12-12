# DigitalOcean Droplet Setup Guide

## Step-by-Step: Creating Your VPS on DigitalOcean

### 1. Create a Droplet

On the DigitalOcean welcome page you're currently viewing:

1. **Click "Create Droplet"** (under the Droplet card)
   - This is what we need for VPS deployment
   - Avoid "App Platform" - that's for containerized apps, not what we need

### 2. Choose Your Configuration

When the Droplet creation page loads:

#### **Choose an image:**
- Select **Ubuntu** tab
- Choose **Ubuntu 22.04 (LTS) x64** ✅

#### **Choose a plan:**
- **Basic** plan tab
- Select **Regular Intel with SSD**
- Minimum recommended: **$12/month** plan:
  - 2 GB RAM / 1 vCPU
  - 50 GB SSD Disk
  - 3 TB Transfer
- For better performance: **$18/month** plan:
  - 4 GB RAM / 2 vCPU
  - 80 GB SSD Disk
  - 4 TB Transfer

#### **Choose a datacenter region:**
- Select closest to you (e.g., New York, San Francisco, London, Sydney)
- Doesn't matter much for a bot, but closer = lower latency

#### **Authentication:**
- **Recommended:** SSH keys (more secure)
  - If you have an SSH key, select it
  - If not, choose "Password" and set a strong password
- **Alternative:** Password (simpler, less secure)
  - You'll set this on the next screen

#### **Finalize and create:**
- **Droplet hostname:** `seekmateai-vps` (or any name you like)
- **Project:** My first project (or create new one)
- Leave other options as default
- Click **"Create Droplet"** button

### 3. Wait for Droplet to Boot

- DigitalOcean will create your Droplet (takes ~60 seconds)
- You'll see a progress indicator
- Wait until status shows "Active" with a green checkmark

### 4. Get Your Server Information

Once the Droplet is active:

1. **Note your IP address:**
   - You'll see it on the Droplet page
   - Example: `157.230.123.45`
   - This is your `YOUR_SERVER_IP`

2. **Get root password (if using password auth):**
   - Check your email for the root password
   - Or click "Access" → "Launch Droplet Console" to see it

### 5. Connect to Your Server

From your local computer, open a terminal:

**If using SSH key:**
```bash
ssh root@YOUR_SERVER_IP
```

**If using password:**
```bash
ssh root@YOUR_SERVER_IP
# Enter password when prompted
```

**First time connecting?**
- You may see a security warning - type `yes` to continue

### 6. You're Connected! 

Once you see the command prompt like:
```
root@seekmateai-vps:~#
```

You're ready to proceed with the deployment!

### Next Steps

Now follow **QUICK_START.md** or **DEPLOYMENT_PLAN.md**:

1. ✅ **Server is ready** (you're here now)
2. Run setup script
3. Upload your code
4. Configure and start

---

## Quick Reference: Droplet Specifications

### Minimum Recommended (Budget Option)
- **Size:** $12/month
- **RAM:** 2 GB
- **CPU:** 1 vCPU
- **Storage:** 50 GB SSD
- **Bandwidth:** 3 TB

### Better Performance (Recommended)
- **Size:** $18/month  
- **RAM:** 4 GB
- **CPU:** 2 vCPU
- **Storage:** 80 GB SSD
- **Bandwidth:** 4 TB

### Cost Estimate
- Monthly: $12-18 USD
- Hourly: ~$0.018-0.027/hour (billed per hour)

---

## Security Notes

1. **SSH Keys are more secure** than passwords
2. **Save your root password** somewhere safe (if using password auth)
3. Consider setting up **firewall** later (we'll cover in deployment)

---

## Troubleshooting

### Can't connect via SSH?
- Wait a minute - Droplet might still be booting
- Check that IP address is correct
- Verify your SSH key is added (if using key auth)
- Try password authentication if key doesn't work

### Forgot root password?
- Use DigitalOcean's web console: Access → Launch Droplet Console
- You can reset password from there

---

**Ready?** Once connected via SSH, proceed to the next step in **QUICK_START.md**! 🚀

