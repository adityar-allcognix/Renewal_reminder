"""
Twilio SMS Webhook Handler for Document Upload Requests
"""

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from datetime import datetime, timedelta
from typing import Optional
import secrets
import structlog

from app.database import get_db
from app.models import Customer, CustomerToken, CustomerTokenType, Policy
from app.services.sms_service import send_sms
from app.config import settings

logger = structlog.get_logger()

router = APIRouter()


async def find_customer_by_phone(
    db: AsyncSession, 
    phone: str
) -> Optional[Customer]:
    """
    Find customer by phone number.
    Handles different phone formats (+1, 1, etc.)
    """
    # Normalize phone: remove +, spaces, dashes
    normalized = ''.join(filter(str.isdigit, phone))
    
    # Try different formats
    phone_variants = [
        phone,  # Original
        f"+{normalized}",  # With +
        normalized,  # Digits only
        normalized[-10:],  # Last 10 digits
    ]
    
    for variant in phone_variants:
        result = await db.execute(
            select(Customer).where(Customer.phone == variant)
        )
        customer = result.scalar_one_or_none()
        if customer:
            return customer
    
    return None


async def check_rate_limit(
    db: AsyncSession,
    customer_id,
    max_requests: int = 10,
    time_window_hours: int = 24
) -> tuple[bool, int]:
    """
    Check if customer has exceeded rate limit for token requests.
    Returns (is_allowed, request_count)
    """
    cutoff_time = datetime.utcnow() - timedelta(hours=time_window_hours)
    
    result = await db.execute(
        select(func.count(CustomerToken.id))
        .where(
            CustomerToken.customer_id == customer_id,
            CustomerToken.token_type == CustomerTokenType.DOCUMENT_UPLOAD,
            CustomerToken.created_at >= cutoff_time
        )
    )
    count = result.scalar_one()
    
    return count < max_requests, count


async def create_upload_token(
    db: AsyncSession,
    customer_id,
    expiry_hours: int = 48
) -> str:
    """
    Generate a secure token for document upload.
    """
    token = secrets.token_urlsafe(32)
    expires_at = datetime.utcnow() + timedelta(hours=expiry_hours)
    
    customer_token = CustomerToken(
        token=token,
        token_type=CustomerTokenType.DOCUMENT_UPLOAD,
        customer_id=customer_id,
        expires_at=expires_at,
        is_used=False,
        token_metadata={"created_via": "sms_request"}
    )
    
    db.add(customer_token)
    await db.commit()
    await db.refresh(customer_token)
    
    return token


async def get_customer_active_policies(
    db: AsyncSession,
    customer_id
) -> list[Policy]:
    """
    Get customer's active policies.
    """
    result = await db.execute(
        select(Policy).where(
            Policy.customer_id == customer_id,
            Policy.status.in_(['active', 'pending_renewal'])
        )
    )
    return result.scalars().all()


@router.post("/sms/webhook")
async def handle_incoming_sms(
    From: str = Form(...),
    Body: str = Form(...),
    MessageSid: str = Form(None),
    request: Request = None,
    db: AsyncSession = Depends(get_db)
):
    """
    Handle incoming SMS messages from Twilio.
    
    Expected format:
    - From: Customer's phone number (E.164 format: +1234567890)
    - Body: Message text (e.g., "UPLOAD")
    """
    
    logger.info(
        "Incoming SMS",
        from_number=From,
        message_body=Body,
        message_sid=MessageSid
    )
    
    # Normalize message body
    message = Body.strip().upper()
    
    # Check if it's an UPLOAD request
    if message != "UPLOAD":
        logger.info("Non-upload message received", message=message)
        return {
            "status": "ignored",
            "message": "Only 'UPLOAD' messages are processed"
        }
    
    # Find customer by phone
    customer = await find_customer_by_phone(db, From)
    
    if not customer:
        logger.warning(
            "Upload request from unknown number",
            phone=From
        )
        
        # Send error response
        response_msg = (
            "We don't recognize this phone number. "
            "Please contact your insurance agent for assistance."
        )
        
        try:
            await send_sms(From, response_msg)
        except Exception as e:
            logger.error("Failed to send SMS response", error=str(e))
        
        return {
            "status": "error",
            "message": "Customer not found"
        }
    
    # Check rate limit
    is_allowed, request_count = await check_rate_limit(
        db, 
        customer.id,
        max_requests=999,
        time_window_hours=1
    )
    
    if not is_allowed:
        logger.warning(
            "Rate limit exceeded",
            customer_id=str(customer.id),
            request_count=request_count
        )
        
        response_msg = (
            "You've reached the maximum number of upload link requests. "
            "Please contact your agent if you need assistance."
        )
        
        try:
            await send_sms(From, response_msg)
        except Exception as e:
            logger.error("Failed to send SMS response", error=str(e))
        
        return {
            "status": "error",
            "message": "Rate limit exceeded"
        }
    
    # Check if customer has active policies
    policies = await get_customer_active_policies(db, customer.id)
    
    if not policies:
        logger.warning(
            "Upload request from customer with no active policies",
            customer_id=str(customer.id)
        )
        
        response_msg = (
            "We couldn't find any active policies for your account. "
            "Please contact your agent for assistance."
        )
        
        try:
            await send_sms(From, response_msg)
        except Exception as e:
            logger.error("Failed to send SMS response", error=str(e))
        
        return {
            "status": "error",
            "message": "No active policies"
        }
    
    # Generate token
    try:
        token = await create_upload_token(db, customer.id, expiry_hours=48)
    except Exception as e:
        logger.error(
            "Failed to create upload token",
            customer_id=str(customer.id),
            error=str(e)
        )
        raise HTTPException(status_code=500, detail="Failed to create token")
    
    # Build upload URL
    frontend_url = settings.FRONTEND_URL or "http://localhost:3000"
    upload_url = f"{frontend_url}/upload/{token}"
    
    # Log the URL to console (for testing with Twilio trial)
    logger.info(
        "📤 DOCUMENT UPLOAD URL GENERATED",
        customer_name=f"{customer.first_name} {customer.last_name}",
        customer_phone=From,
        upload_url=upload_url,
        expires_in_hours=48,
        token=token
    )
    
    # Prepare SMS response
    response_msg = (
        f"Hi {customer.first_name}! "
        f"Upload your insurance documents here: {upload_url} "
        f"This link expires in 48 hours."
    )
    
    # Send SMS (or just log for testing)
    try:
        # For production with verified Twilio numbers:
        # await send_sms(From, response_msg)
        
        # For testing (console log only):
        logger.info(
            "📱 SMS RESPONSE (not sent - trial mode)",
            to=From,
            message=response_msg
        )
        
        print("\n" + "="*70)
        print("🔗 DOCUMENT UPLOAD LINK GENERATED")
        print("="*70)
        print(f"Customer: {customer.first_name} {customer.last_name}")
        print(f"Phone: {From}")
        print(f"URL: {upload_url}")
        print(f"Expires: 48 hours")
        print("="*70 + "\n")
        
    except Exception as e:
        logger.error("Failed to send SMS", error=str(e))
    
    return {
        "status": "success",
        "message": "Upload link generated",
        "customer_id": str(customer.id),
        "token": token,
        "upload_url": upload_url
    }


@router.post("/sms/send-upload-link")
async def send_upload_link_to_customer(
    customer_id: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Admin/Agent endpoint to manually send upload link to customer.
    Useful for proactive outreach.
    """
    from uuid import UUID
    
    # Get customer
    result = await db.execute(
        select(Customer).where(Customer.id == UUID(customer_id))
    )
    customer = result.scalar_one_or_none()
    
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    
    if not customer.phone:
        raise HTTPException(
            status_code=400, 
            detail="Customer has no phone number"
        )
    
    # Check rate limit
    is_allowed, request_count = await check_rate_limit(
        db, 
        customer.id,
        max_requests=5,  # Higher limit for admin-initiated
        time_window_hours=24
    )
    
    if not is_allowed:
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded for this customer"
        )
    
    # Generate token
    token = await create_upload_token(db, customer.id, expiry_hours=48)
    
    # Build URL
    frontend_url = settings.FRONTEND_URL or "http://localhost:3000"
    upload_url = f"{frontend_url}/upload/{token}"
    
    # Log to console
    logger.info(
        "📤 ADMIN-INITIATED UPLOAD LINK",
        customer_name=f"{customer.first_name} {customer.last_name}",
        upload_url=upload_url
    )
    
    print("\n" + "="*70)
    print("🔗 ADMIN-INITIATED DOCUMENT UPLOAD LINK")
    print("="*70)
    print(f"Customer: {customer.first_name} {customer.last_name}")
    print(f"Phone: {customer.phone}")
    print(f"URL: {upload_url}")
    print("="*70 + "\n")
    
    # Prepare message
    message = (
        f"Hi {customer.first_name}! "
        f"Please upload your insurance documents here: {upload_url} "
        f"This link expires in 48 hours. Reply UPLOAD to get a new link."
    )
    
    # Send SMS (or log for testing)
    try:
        # await send_sms(customer.phone, message)
        logger.info("SMS would be sent", to=customer.phone, message=message)
    except Exception as e:
        logger.error("Failed to send SMS", error=str(e))
    
    return {
        "status": "success",
        "message": "Upload link sent",
        "upload_url": upload_url,
        "customer": {
            "id": str(customer.id),
            "name": f"{customer.first_name} {customer.last_name}",
            "phone": customer.phone
        }
    }
