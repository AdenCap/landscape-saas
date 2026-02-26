"""SMS utilities using Twilio."""
from django.conf import settings
from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException


def send_sms(to_phone, message, business=None):
    """
    Send SMS message using Twilio.
    
    Args:
        to_phone: Phone number to send to (E.164 format, e.g. +15551234567)
        message: Message text
        business: Business object (optional, for future per-business Twilio accounts)
    
    Returns:
        tuple: (success: bool, message_sid: str or error_message: str)
    """
    account_sid = getattr(settings, "TWILIO_ACCOUNT_SID", None)
    auth_token = getattr(settings, "TWILIO_AUTH_TOKEN", None)
    from_number = getattr(settings, "TWILIO_PHONE_NUMBER", None)
    
    if not all([account_sid, auth_token, from_number]):
        return False, "Twilio not configured"
    
    try:
        client = Client(account_sid, auth_token)
        
        # Format phone number (ensure E.164 format)
        if not to_phone.startswith('+'):
            # Assume US number, add +1
            to_phone = '+1' + to_phone.replace('-', '').replace(' ', '').replace('(', '').replace(')', '')
        
        message_obj = client.messages.create(
            body=message,
            from_=from_number,
            to=to_phone
        )
        
        return True, message_obj.sid
    except TwilioRestException as e:
        return False, str(e)
    except Exception as e:
        return False, f"Error sending SMS: {str(e)}"
