"""
Test Reminders API - For testing reminder functionality directly
"""

from typing import Optional
from datetime import datetime, date, timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from pydantic import BaseModel, EmailStr

from app.database import get_db
from app.models import Customer, Policy, RenewalReminder, ReminderStatus, ReminderChannel
from app.services.communication import CommunicationGateway, EmailService, SMSService, WhatsAppService

router = APIRouter()


# ===========================================
# Test Request Models
# ===========================================

class TestEmailRequest(BaseModel):
    """Test email request."""
    to_email: EmailStr
    customer_name: str = "Test Customer"
    policy_number: str = "TEST-001"
    renewal_date: str = (date.today() + timedelta(days=7)).isoformat()
    renewal_amount: float = 1500.00
    days_until_renewal: int = 7


class TestSMSRequest(BaseModel):
    """Test SMS request."""
    to_phone: str  # E.164 format: +1234567890
    customer_name: str = "Test Customer"
    policy_number: str = "TEST-001"
    renewal_date: str = (date.today() + timedelta(days=7)).isoformat()
    days_until_renewal: int = 7


class TestWhatsAppRequest(BaseModel):
    """Test WhatsApp request."""
    to_phone: str  # Phone number without whatsapp: prefix
    customer_name: str = "Test Customer"
    policy_number: str = "TEST-001"
    renewal_date: str = (date.today() + timedelta(days=7)).isoformat()
    renewal_amount: float = 1500.00
    days_until_renewal: int = 7


class TestReminderRequest(BaseModel):
    """Test reminder via any channel."""
    channel: ReminderChannel
    to_email: Optional[str] = None
    to_phone: Optional[str] = None
    customer_name: str = "Test Customer"
    policy_number: str = "TEST-001"
    renewal_date: str = (date.today() + timedelta(days=7)).isoformat()
    renewal_amount: float = 1500.00
    days_until_renewal: int = 7


# ===========================================
# Test Endpoints
# ===========================================

@router.post("/email")
async def test_send_email(request: TestEmailRequest):
    """
    Test sending a renewal reminder email.
    
    This endpoint sends a test email immediately without requiring
    a customer or policy in the database.
    """
    email_service = EmailService()
    
    result = await email_service.send_renewal_reminder(
        to_email=request.to_email,
        customer_name=request.customer_name,
        policy_number=request.policy_number,
        renewal_date=request.renewal_date,
        renewal_amount=request.renewal_amount,
        days_until_renewal=request.days_until_renewal
    )
    
    return {
        "test_type": "email",
        "recipient": request.to_email,
        "result": result
    }


@router.post("/sms")
async def test_send_sms(request: TestSMSRequest):
    """
    Test sending a renewal reminder SMS.
    
    Phone number should be in E.164 format (e.g., +1234567890).
    """
    sms_service = SMSService()
    
    result = await sms_service.send_renewal_reminder(
        to_number=request.to_phone,
        customer_name=request.customer_name,
        policy_number=request.policy_number,
        renewal_date=request.renewal_date,
        days_until_renewal=request.days_until_renewal
    )
    
    return {
        "test_type": "sms",
        "recipient": request.to_phone,
        "result": result
    }


@router.post("/whatsapp")
async def test_send_whatsapp(request: TestWhatsAppRequest):
    """
    Test sending a renewal reminder via WhatsApp.
    
    Phone number should be in E.164 format (e.g., +1234567890).
    Note: WhatsApp Business API requires pre-approved templates for
    outbound messages to users who haven't messaged you first.
    """
    whatsapp_service = WhatsAppService()
    
    result = await whatsapp_service.send_renewal_reminder(
        to_number=request.to_phone,
        customer_name=request.customer_name,
        policy_number=request.policy_number,
        renewal_date=request.renewal_date,
        renewal_amount=request.renewal_amount,
        days_until_renewal=request.days_until_renewal
    )
    
    return {
        "test_type": "whatsapp",
        "recipient": request.to_phone,
        "result": result
    }


@router.post("/channel")
async def test_send_via_channel(request: TestReminderRequest):
    """
    Test sending a reminder via any specified channel.
    
    - For email: provide to_email
    - For SMS/WhatsApp: provide to_phone in E.164 format
    """
    gateway = CommunicationGateway()
    
    customer_data = {
        "name": request.customer_name,
        "email": request.to_email,
        "phone": request.to_phone
    }
    
    policy_data = {
        "policy_number": request.policy_number,
        "renewal_date": request.renewal_date,
        "renewal_amount": request.renewal_amount,
        "days_until_renewal": request.days_until_renewal
    }
    
    result = await gateway.send_reminder(
        channel=request.channel.value,
        customer_data=customer_data,
        policy_data=policy_data
    )
    
    return {
        "test_type": "channel",
        "channel": request.channel.value,
        "recipient": request.to_email or request.to_phone,
        "result": result
    }


@router.post("/policy/{policy_id}")
async def test_send_for_policy(
    policy_id: UUID,
    channel: Optional[ReminderChannel] = None,
    db: AsyncSession = Depends(get_db)
):
    """
    Test sending a reminder for an existing policy in the database.
    
    This uses real customer and policy data from the database.
    If channel is not specified, uses the customer's preferred channel.
    """
    query = (
        select(Policy)
        .options(selectinload(Policy.customer))
        .where(Policy.id == policy_id)
    )
    result = await db.execute(query)
    policy = result.scalar_one_or_none()
    
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")
    
    customer = policy.customer
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found for policy")
    
    # Use specified channel or customer's preferred channel
    use_channel = channel or customer.preferred_channel
    
    gateway = CommunicationGateway()
    
    customer_data = {
        "name": customer.full_name,
        "email": customer.email,
        "phone": customer.phone
    }
    
    days_until = (policy.renewal_date - date.today()).days
    
    policy_data = {
        "policy_number": policy.policy_number,
        "renewal_date": policy.renewal_date.isoformat(),
        "renewal_amount": float(policy.premium_amount) * 1.03,  # 3% increase estimate
        "days_until_renewal": days_until
    }
    
    send_result = await gateway.send_reminder(
        channel=use_channel.value,
        customer_data=customer_data,
        policy_data=policy_data
    )
    
    return {
        "test_type": "policy",
        "policy_id": str(policy_id),
        "policy_number": policy.policy_number,
        "customer_name": customer.full_name,
        "channel": use_channel.value,
        "days_until_renewal": days_until,
        "result": send_result
    }


@router.get("/config")
async def get_communication_config():
    """
    Get current communication configuration status.
    
    Shows which channels are properly configured and ready to send.
    """
    from app.config import settings
    
    return {
        "email": {
            "provider": "SendGrid",
            "configured": bool(settings.SENDGRID_API_KEY and settings.SENDGRID_API_KEY != "your_sendgrid_api_key"),
            "from_email": settings.SENDGRID_FROM_EMAIL,
            "from_name": settings.SENDGRID_FROM_NAME
        },
        "sms": {
            "provider": "Twilio",
            "configured": bool(settings.TWILIO_ACCOUNT_SID and settings.TWILIO_AUTH_TOKEN),
            "from_number": settings.TWILIO_PHONE_NUMBER,
            "note": "Phone number must be purchased from Twilio"
        },
        "whatsapp": {
            "provider": "Twilio",
            "configured": bool(settings.TWILIO_ACCOUNT_SID and settings.TWILIO_AUTH_TOKEN and settings.TWILIO_WHATSAPP_NUMBER),
            "from_number": settings.TWILIO_WHATSAPP_NUMBER,
            "note": "Requires WhatsApp Business API approval"
        },
        "reminder_windows": settings.reminder_window_days
    }


@router.post("/all-channels")
async def test_all_channels(
    to_email: str,
    to_phone: str,
    customer_name: str = "Test Customer",
    policy_number: str = "TEST-001"
):
    """
    Test sending reminders through ALL channels at once.
    
    Useful for verifying all integrations are working.
    """
    gateway = CommunicationGateway()
    
    customer_data = {
        "name": customer_name,
        "email": to_email,
        "phone": to_phone
    }
    
    policy_data = {
        "policy_number": policy_number,
        "renewal_date": (date.today() + timedelta(days=7)).isoformat(),
        "renewal_amount": 1500.00,
        "days_until_renewal": 7
    }
    
    results = {}
    
    for channel in ["email", "sms", "whatsapp"]:
        result = await gateway.send_reminder(
            channel=channel,
            customer_data=customer_data,
            policy_data=policy_data
        )
        results[channel] = result
    
    return {
        "test_type": "all_channels",
        "results": results
    }
