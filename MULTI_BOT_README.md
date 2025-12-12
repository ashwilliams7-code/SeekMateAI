# Multi-Bot Setup Guide

This guide explains how to run multiple SeekMateAI bots simultaneously on the same PC, each with its own:
- ✅ Chrome profile
- ✅ Config file
- ✅ Seek account
- ✅ Log file

## Quick Start

### Option 1: Using the GUI (Recommended)

1. **Launch the Multi-Bot Manager:**
   - Double-click `Run_Multi_Bot_Manager.bat` (Windows)
   - Or run: `python multi_bot_gui.py`

2. **Add Bot Instances:**
   - Click "➕ Add Instance"
   - Enter:
     - **Instance Name**: A unique name (e.g., "bot1", "bot2")
     - **SEEK Email**: The Seek account email for this bot
     - **Full Name**: The name to use in applications
   - Click "Add"

3. **Start Bots:**
   - Select an instance and click "▶️ Start Selected"
   - Or click "▶️ Start All" to start all instances

4. **Monitor:**
   - View status in the list (🟢 Running / 🔴 Stopped)
   - Click "📋 View Log" to see the log file for any instance

### Option 2: Using Command Line

1. **Add a bot instance:**
   ```bash
   python multi_bot_launcher.py add bot1 --email user1@example.com --name "John Doe"
   python multi_bot_launcher.py add bot2 --email user2@example.com --name "Jane Smith"
   ```

2. **List all instances:**
   ```bash
   python multi_bot_launcher.py list
   ```

3. **Start instances:**
   ```bash
   # Start a specific instance
   python multi_bot_launcher.py start bot1
   
   # Start all instances
   python multi_bot_launcher.py start-all
   ```

4. **Stop instances:**
   ```bash
   # Stop a specific instance
   python multi_bot_launcher.py stop bot1
   
   # Stop all instances
   python multi_bot_launcher.py stop-all
   ```

5. **Remove an instance:**
   ```bash
   python multi_bot_launcher.py remove bot1
   ```

## How It Works

Each bot instance has:

1. **Separate Config File**: `bot_instances/{instance_name}_config.json`
   - Copy of your base `config.json` with instance-specific settings
   - Edit this file to customize each bot's behavior

2. **Separate Chrome Profile**: `chrome_profile_{instance_name}/`
   - Each bot uses its own Chrome profile
   - Logged-in sessions are preserved per instance
   - No conflicts between multiple Chrome instances

3. **Separate Log File**: `log_{instance_name}.txt`
   - Each bot writes to its own log file
   - Easy to track what each bot is doing

4. **Separate Control File**: `control_{instance_name}.json`
   - Pause/stop controls are per-instance
   - You can pause one bot while others continue

## File Structure

```
SeekMateAI/
├── multi_bot_launcher.py      # Command-line launcher
├── multi_bot_gui.py           # GUI launcher
├── Run_Multi_Bot_Manager.bat  # Windows launcher
├── bot_instances.json         # Instance registry
├── bot_instances/             # Instance configs
│   ├── bot1_config.json
│   └── bot2_config.json
├── chrome_profile_bot1/       # Chrome profile for bot1
├── chrome_profile_bot2/        # Chrome profile for bot2
├── log_bot1.txt               # Log file for bot1
├── log_bot2.txt               # Log file for bot2
└── control_bot1.json          # Control file for bot1
```

## Tips

1. **Different Seek Accounts**: Each instance should use a different Seek account email to avoid conflicts.

2. **Resource Usage**: Running multiple bots will use more:
   - CPU
   - RAM (each Chrome instance uses ~200-500MB)
   - Network bandwidth

3. **Chrome Windows**: Each bot opens its own Chrome window. Make sure you have enough screen space or run in headless mode.

4. **Config Customization**: After creating an instance, you can edit `bot_instances/{instance_name}_config.json` to customize:
   - Job titles
   - Location
   - Max jobs
   - Speed settings
   - etc.

5. **Monitoring**: Check log files regularly to ensure bots are running correctly:
   - `log_bot1.txt`
   - `log_bot2.txt`
   - etc.

## Troubleshooting

**Problem**: Bot instance won't start
- **Solution**: Check the log file for errors. Make sure the config file exists and is valid JSON.

**Problem**: Chrome profile conflicts
- **Solution**: Each instance uses a separate profile directory. If you see conflicts, make sure instance names are unique.

**Problem**: Can't stop a bot
- **Solution**: Use Task Manager (Windows) to kill the Python process, or use `python multi_bot_launcher.py stop-all`

**Problem**: Multiple Chrome windows open but bots aren't working
- **Solution**: Make sure each instance has a valid Seek account email configured and the account is logged in.

## Advanced Usage

### Running in Headless Mode

Set the `RUN_HEADLESS` environment variable:
```bash
# Windows
set RUN_HEADLESS=true
python multi_bot_launcher.py start-all

# Linux/Mac
export RUN_HEADLESS=true
python multi_bot_launcher.py start-all
```

### Custom Config Per Instance

1. Create the instance normally
2. Edit `bot_instances/{instance_name}_config.json`
3. Modify any settings (job titles, location, etc.)
4. Restart the instance

### Running Specific Instances Only

```bash
# Start only bot1 and bot3
python multi_bot_launcher.py start bot1
python multi_bot_launcher.py start bot3
```

## Support

If you encounter issues:
1. Check the log files for error messages
2. Verify each instance has a unique name
3. Ensure config files are valid JSON
4. Make sure Chrome is installed and up to date

