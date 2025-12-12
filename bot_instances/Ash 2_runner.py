import os
import sys
import json

# Set instance-specific environment variables
os.environ['BOT_INSTANCE_NAME'] = 'Ash 2'
os.environ['BOT_CONFIG_FILE'] = r'C:\\Users\\user\\Documents\\SeekMateAI\\bot_instances\\Ash 2_config.json'
os.environ['BOT_CHROME_PROFILE'] = 'chrome_profile_Ash 2'
os.environ['BOT_LOG_FILE'] = r'C:\\Users\\user\\Documents\\SeekMateAI\\log_Ash 2.txt'
os.environ['BOT_CONTROL_FILE'] = r'C:\\Users\\user\\Documents\\SeekMateAI\\control_Ash 2.json'

# Import and run main
sys.path.insert(0, r'C:\\Users\\user\\Documents\\SeekMateAI')
import main
main.main()
