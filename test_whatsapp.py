"""
Test WhatsApp notification for SeekMate AI
Run this script to send a test message to Ash Williams
"""

import json
import urllib.request
import urllib.parse
import base64
from datetime import datetime

# Load config
with open("config.json", "r") as f:
    CONFIG = json.load(f)

# Twilio settings
TWILIO_ACCOUNT_SID = CONFIG.get("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN = CONFIG.get("TWILIO_AUTH_TOKEN", "")
TWILIO_WHATSAPP_FROM = CONFIG.get("TWILIO_WHATSAPP_FROM", "whatsapp:+14155238886")

# Profile phone numbers
PROFILE_PHONES = {
    "Ash Williams": "+61490077979",
    "Jennifer Berrio": "+61491723617",
    "Rafael Hurtado": "+6411557289",
}

def send_test_whatsapp(profile_name):
    """Send a test WhatsApp message"""
    
    # Check credentials
    if not TWILIO_ACCOUNT_SID:
        print("❌ ERROR: TWILIO_ACCOUNT_SID is not configured in config.json")
        print("   Add your Twilio Account SID to config.json")
        return False
    
    if not TWILIO_AUTH_TOKEN:
        print("❌ ERROR: TWILIO_AUTH_TOKEN is not configured in config.json")
        print("   Add your Twilio Auth Token to config.json")
        return False
    
    # Get phone number
    phone = PROFILE_PHONES.get(profile_name)
    if not phone:
        print(f"❌ ERROR: No phone number found for '{profile_name}'")
        return False
    
    print(f"📱 Sending test WhatsApp to {profile_name} ({phone})...")
    
    # Format the test message
    message = f"""🧪 *SeekMate AI Test Message*

👤 Profile: {profile_name}
✅ Jobs Applied: 25 (TEST)
⏱️ Duration: 45 minutes (TEST)
📅 Time: {datetime.now().strftime('%I:%M %p, %d %b %Y')}

This is a test message. If you received this, WhatsApp notifications are working! 🎉"""

    try:
        # Twilio API endpoint
        url = f"https://api.twilio.com/2010-04-01/Accounts/{TWILIO_ACCOUNT_SID}/Messages.json"
        
        # Format phone for WhatsApp
        to_number = f"whatsapp:{phone}" if not phone.startswith("whatsapp:") else phone
        
        print(f"   From: {TWILIO_WHATSAPP_FROM}")
        print(f"   To: {to_number}")
        
        # Prepare data
        data = urllib.parse.urlencode({
            'From': TWILIO_WHATSAPP_FROM,
            'To': to_number,
            'Body': message
        }).encode('utf-8')
        
        # Create request with basic auth
        request = urllib.request.Request(url, data=data)
        credentials = f"{TWILIO_ACCOUNT_SID}:{TWILIO_AUTH_TOKEN}"
        encoded_credentials = base64.b64encode(credentials.encode()).decode()
        request.add_header('Authorization', f'Basic {encoded_credentials}')
        
        # Send request
        with urllib.request.urlopen(request, timeout=30) as response:
            result = response.read().decode()
            if response.status == 201:
                print(f"✅ SUCCESS! Test message sent to {profile_name}")
                print(f"   Check WhatsApp on {phone}")
                return True
            else:
                print(f"❌ Failed: Status {response.status}")
                print(f"   Response: {result}")
                return False
                
    except urllib.error.HTTPError as e:
        error_body = e.read().decode()
        print(f"❌ HTTP Error {e.code}: {e.reason}")
        print(f"   Details: {error_body}")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def send_test_daily_summary():
    """Send a test daily summary message showing bot statuses"""
    
    # Check credentials
    if not TWILIO_ACCOUNT_SID:
        print("❌ ERROR: TWILIO_ACCOUNT_SID is not configured in config.json")
        return False
    
    if not TWILIO_AUTH_TOKEN:
        print("❌ ERROR: TWILIO_AUTH_TOKEN is not configured in config.json")
        return False
    
    # Get phone number (default to Ash Williams)
    phone = PROFILE_PHONES.get("Ash Williams")
    if not phone:
        print("❌ ERROR: No phone number found")
        return False
    
    print(f"📱 Sending test daily summary to {phone}...")
    
    # Create sample summary message (what you'll receive at 9 AM and 6 PM)
    message = """🌅 *Morning Summary - Overnight Results*

📊 *Jobs Applied Overnight:* 15
📈 *Total Jobs (All Time):* 245
🤖 *Active Bots:* 2/2
⚠️ *Bots Needing Attention:* 1

🟢 *Ash Williams* (ASH 1):
   • Status: Running Well
   • Overnight: 8 jobs
   • Total: 125 jobs

⚠️ *Jennifer Berrio* (Ash 2):
   • Status: Stuck/Frozen (45m ago)
   • Overnight: 7 jobs
   • Total: 120 jobs

📅 09:00 AM, 12 Dec 2024

Keep up the great work! 💪"""
    
    try:
        url = f"https://api.twilio.com/2010-04-01/Accounts/{TWILIO_ACCOUNT_SID}/Messages.json"
        
        to_number = f"whatsapp:{phone}" if not phone.startswith("whatsapp:") else phone
        
        print(f"   From: {TWILIO_WHATSAPP_FROM}")
        print(f"   To: {to_number}")
        
        data = urllib.parse.urlencode({
            'From': TWILIO_WHATSAPP_FROM,
            'To': to_number,
            'Body': message
        }).encode('utf-8')
        
        request = urllib.request.Request(url, data=data)
        credentials = f"{TWILIO_ACCOUNT_SID}:{TWILIO_AUTH_TOKEN}"
        encoded_credentials = base64.b64encode(credentials.encode()).decode()
        request.add_header('Authorization', f'Basic {encoded_credentials}')
        
        with urllib.request.urlopen(request, timeout=30) as response:
            result = response.read().decode()
            if response.status == 201:
                print(f"✅ SUCCESS! Test daily summary sent!")
                print(f"   Check WhatsApp on {phone}")
                # Parse response to show message SID
                try:
                    import json
                    result_json = json.loads(result)
                    if 'sid' in result_json:
                        print(f"   Message SID: {result_json['sid']}")
                    if 'status' in result_json:
                        print(f"   Status: {result_json['status']}")
                except:
                    pass
                return True
            else:
                print(f"❌ Failed: Status {response.status}")
                print(f"   Response: {result}")
                return False
                
    except urllib.error.HTTPError as e:
        error_body = e.read().decode()
        print(f"❌ HTTP Error {e.code}: {e.reason}")
        print(f"   Details: {error_body}")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    import sys
    
    print("=" * 50)
    print("🧪 SeekMate AI - WhatsApp Test")
    print("=" * 50)
    print()
    
    # Check command line argument
    if len(sys.argv) > 1:
        choice = sys.argv[1]
    else:
        print("Choose test type:")
        print("1. Simple test message")
        print("2. Daily summary (with bot statuses)")
        print()
        try:
            choice = input("Enter choice (1 or 2): ").strip()
        except EOFError:
            # Non-interactive mode, default to daily summary
            choice = "2"
    
    if choice == "2":
        send_test_daily_summary()
    else:
        # Send simple test to Ash Williams
        send_test_whatsapp("Ash Williams")

