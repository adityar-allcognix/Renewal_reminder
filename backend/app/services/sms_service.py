"""
SMS Service Wrapper
"""

from app.services.communication import SMSService


async def send_sms(to_number: str, message: str) -> dict:
    """
    Send SMS via Twilio.
    
    Args:
        to_number: Recipient phone number
        message: SMS message content
        
    Returns:
        dict with status and message_id
    """
    sms_service = SMSService()
    return await sms_service.send_sms(to_number, message)
