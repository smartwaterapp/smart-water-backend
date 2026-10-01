import json
import urllib.request
import urllib.parse
from datetime import datetime
from sqlalchemy.orm import Session
from whatsapp_models import WhatsAppUser, WhatsAppMessageLog

DEFAULT_API_KEY = "pyezpulse_master_key"

def get_or_create_default_user(db: Session) -> WhatsAppUser:
    user = db.query(WhatsAppUser).filter(WhatsAppUser.api_key == DEFAULT_API_KEY).first()
    if not user:
        user = WhatsAppUser(
            username="PyezPulse Admin",
            api_key=DEFAULT_API_KEY,
            plan_name="Smart Business (10 JD)",
            monthly_limit=1000,
            messages_sent=0,
            is_active=True
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    return user

def dispatch_whatsapp_message(to_number: str, message_text: str, instance_id: str, token: str) -> dict:
    """
    Sends message silently via WhatsApp Gateway API.
    """
    # Clean up phone number (ensure international digits only)
    cleaned_number = ''.join(c for c in to_number if c.isdigit())
    if cleaned_number.startswith('00'):
        cleaned_number = cleaned_number[2:]

    url = f"https://api.ultramsg.com/{instance_id}/messages/chat"
    payload = urllib.parse.urlencode({
        "token": token,
        "to": cleaned_number,
        "body": message_text
    }).encode('utf-8')

    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST"
    )

    with urllib.request.urlopen(req, timeout=15) as resp:
        res_data = resp.read().decode('utf-8')
        return json.loads(res_data)
