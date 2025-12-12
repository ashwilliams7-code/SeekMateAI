# WhatsApp Setup Instructions

## If you didn't receive the test message:

### For Twilio WhatsApp Sandbox Mode:

1. **Send a message TO the Twilio WhatsApp number first:**
   - Open WhatsApp on your phone (+61490077979)
   - Send a message to: **+1 415 523 8886**
   - Send the code: **join [your-sandbox-code]** (check your Twilio console for the exact code)
   - Or just send: **join** if that's your sandbox code

2. **Wait a few minutes** - Sometimes there's a delay

3. **Check your Twilio Console:**
   - Go to: https://console.twilio.com/
   - Navigate to: Messaging > Monitor > Logs
   - Check if the message shows as "delivered" or "failed"
   - Look for any error messages

### Common Issues:

- **Sandbox not joined**: You must send a message TO the Twilio number first
- **Phone number not verified**: In sandbox mode, only verified numbers can receive messages
- **Wrong phone format**: Should be +61490077979 (with country code)
- **Account limits**: Check if your Twilio account has credits

### To Test Again:

Run: `python test_whatsapp.py 2`

### Check Message Status:

The message SID was: SM084cf6778f3ad5dc74da7a5b3a598255
Check this in your Twilio console to see delivery status.

