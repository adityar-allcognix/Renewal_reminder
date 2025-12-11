"""
Test Endpoint for SMS Upload Request Flow
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional
import structlog

from app.database import get_db
from app.models import Customer
from app.api.sms_webhook import (
    handle_incoming_sms,
    send_upload_link_to_customer
)

logger = structlog.get_logger()

router = APIRouter()


@router.post("/test-upload-request")
async def test_upload_request(
    customer_email: Optional[str] = None,
    customer_phone: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """
    Test endpoint to simulate a customer requesting an upload link.
    
    This bypasses Twilio and directly generates an upload link for testing.
    
    Usage:
        POST /api/test/test-upload-request
        Body: {"customer_email": "john@example.com"}
        OR
        Body: {"customer_phone": "+1234567890"}
    """
    
    if not customer_email and not customer_phone:
        raise HTTPException(
            status_code=400,
            detail="Provide either customer_email or customer_phone"
        )
    
    # Find customer
    query = select(Customer)
    if customer_email:
        query = query.where(Customer.email == customer_email)
    else:
        query = query.where(Customer.phone == customer_phone)
    
    result = await db.execute(query)
    customer = result.scalar_one_or_none()
    
    if not customer:
        raise HTTPException(
            status_code=404,
            detail="Customer not found"
        )
    
    # Simulate SMS webhook with "UPLOAD" message
    phone = customer.phone or "+1234567890"  # Fallback for testing
    
    # Call the webhook handler directly
    response = await handle_incoming_sms(
        From=phone,
        Body="UPLOAD",
        MessageSid="TEST_MESSAGE_SID",
        request=None,
        db=db
    )
    
    return {
        "status": "success",
        "message": "Upload link generated (check console logs)",
        "customer": {
            "id": str(customer.id),
            "name": f"{customer.first_name} {customer.last_name}",
            "email": customer.email,
            "phone": customer.phone
        },
        "webhook_response": response
    }


@router.post("/test-admin-upload-link/{customer_id}")
async def test_admin_upload_link(
    customer_id: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Test endpoint for admin to send upload link to specific customer.
    
    Usage:
        POST /api/test/test-admin-upload-link/{customer_id}
    """
    
    return await send_upload_link_to_customer(customer_id, db)


@router.get("/test-customer-lookup")
async def test_customer_lookup(
    phone: Optional[str] = None,
    email: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """
    Test endpoint to verify customer lookup.
    
    Usage:
        GET /api/test/test-customer-lookup?phone=+1234567890
        OR
        GET /api/test/test-customer-lookup?email=john@example.com
    """
    
    if not phone and not email:
        raise HTTPException(
            status_code=400,
            detail="Provide either phone or email"
        )
    
    query = select(Customer)
    if phone:
        query = query.where(Customer.phone == phone)
    if email:
        query = query.where(Customer.email == email)
    
    result = await db.execute(query)
    customer = result.scalar_one_or_none()
    
    if not customer:
        return {
            "found": False,
            "message": "Customer not found"
        }
    
    return {
        "found": True,
        "customer": {
            "id": str(customer.id),
            "name": f"{customer.first_name} {customer.last_name}",
            "email": customer.email,
            "phone": customer.phone,
            "preferred_channel": customer.preferred_channel
        }
    }
