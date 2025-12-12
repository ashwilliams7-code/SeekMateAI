import os
import sys
import json

# Set instance-specific environment variables
os.environ['BOT_INSTANCE_NAME'] = 'ASH 1'
os.environ['BOT_CONFIG_FILE'] = r'C:\\Users\\user\\Documents\\SeekMateAI\\bot_instances\\ASH 1_config.json'
os.environ['BOT_CHROME_PROFILE'] = 'chrome_profile_ASH 1'
os.environ['BOT_LOG_FILE'] = r'C:\\Users\\user\\Documents\\SeekMateAI\\log_ASH 1.txt'
os.environ['BOT_CONTROL_FILE'] = r'C:\\Users\\user\\Documents\\SeekMateAI\\control_ASH 1.json'

# Import and run main
sys.path.insert(0, r'C:\\Users\\user\\Documents\\SeekMateAI')
import main
main.main()
