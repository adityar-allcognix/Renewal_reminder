import os
import sys
from dotenv import load_dotenv
from twilio.rest import Client

# Load environment variables
load_dotenv()

account_sid = os.getenv("TWILIO_ACCOUNT_SID")
auth_token = os.getenv("TWILIO_AUTH_TOKEN")
from_whatsapp = os.getenv("TWILIO_WHATSAPP_NUMBER")
to_number = "9209793522"  # The number from the database

print(f"Account SID: {account_sid}")
print(f"From WhatsApp: {from_whatsapp}")
print(f"To Number: {to_number}")

if not account_sid or not auth_token:
    print("Error: Twilio credentials not found in .env")
    sys.exit(1)

client = Client(account_sid, auth_token)

# Try sending with +91
try:
    print("\nAttempting to send to +91" + to_number)
    message = client.messages.create(
        body="Test message from Renewal Reminders (Backend Check) - +91",
        from_=f"whatsapp:{from_whatsapp}",
        to=f"whatsapp:+91{to_number}"
    )
    print(f"Success! Message SID: {message.sid}")
except Exception as e:
    print(f"Failed with +91: {e}")

# Try sending with +1
try:
    print("\nAttempting to send to +1" + to_number)
    message = client.messages.create(
        body="Test message from Renewal Reminders (Backend Check) - +1",
        from_=f"whatsapp:{from_whatsapp}",
        to=f"whatsapp:+1{to_number}"
    )
    print(f"Success! Message SID: {message.sid}")
except Exception as e:
    print(f"Failed with +1: {e}")

# Try sending as is (if it already has country code, which it doesn't)
try:
    print("\nAttempting to send to " + to_number)
    message = client.messages.create(
        body="Test message from Renewal Reminders (Backend Check) - Raw",
        from_=f"whatsapp:{from_whatsapp}",
        to=f"whatsapp:{to_number}"
    )
    print(f"Success! Message SID: {message.sid}")
except Exception as e:
    print(f"Failed with Raw: {e}")
