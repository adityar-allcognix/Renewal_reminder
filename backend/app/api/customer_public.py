"""
Customer Public API Routes (No Authentication Required)

These endpoints allow customers to interact with the system via secure tokens
sent through email/SMS/WhatsApp, without requiring login.
"""

import secrets
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import joinedload
from pydantic import BaseModel

from app.database import get_db
from app.models import (
    Customer, Policy, CustomerToken, CustomerTokenType,
    PolicyStatus
)

router = APIRouter()


# ===========================================
# Schemas
# ===========================================
class TokenVerifyRequest(BaseModel):
    """Token verification request."""
    token: str


class CustomerPublicInfo(BaseModel):
    """Limited customer info for public view."""
    first_name: str
    last_name: str
    email_masked: str  # j***@example.com


class PolicyPublicInfo(BaseModel):
    """Limited policy info for public view."""
    policy_number: str
    policy_type: str
    end_date: str
    days_until_expiry: int
    premium_amount: float
    status: str


class RenewalConfirmationResponse(BaseModel):
    """Renewal confirmation page data."""
    customer: CustomerPublicInfo
    policy: PolicyPublicInfo
    token_type: str
    expires_at: str
    message: str


class RenewalActionRequest(BaseModel):
    """Customer action on renewal."""
    token: str
    action: str  # "confirm_renewal", "request_callback", "decline"
    notes: Optional[str] = None
    preferred_contact_time: Optional[str] = None


class ActionResponse(BaseModel):
    """Response after customer action."""
    success: bool
    message: str


# ===========================================
# Helper Functions
# ===========================================
def mask_email(email: str) -> str:
    """Mask email for privacy: john@example.com -> j***@example.com"""
    if '@' not in email:
        return '***'
    local, domain = email.split('@')
    if len(local) <= 1:
        return f"*@{domain}"
    return f"{local[0]}***@{domain}"


def generate_secure_token() -> str:
    """Generate a cryptographically secure token."""
    return secrets.token_urlsafe(32)


async def create_customer_token(
    db: AsyncSession,
    customer_id: str,
    policy_id: Optional[str],
    token_type: CustomerTokenType,
    expires_hours: int = 24
) -> CustomerToken:
    """Create a secure token for customer interaction."""
    token = CustomerToken(
        token=generate_secure_token(),
        token_type=token_type,
        customer_id=customer_id,
        policy_id=policy_id,
        expires_at=datetime.utcnow() + timedelta(hours=expires_hours),
        is_used=False
    )
    db.add(token)
    await db.commit()
    await db.refresh(token)
    return token


async def validate_token(
    db: AsyncSession,
    token: str
) -> Optional[CustomerToken]:
    """Validate a customer token and eagerly load customer relationship."""
    result = await db.execute(
        select(CustomerToken)
        .options(joinedload(CustomerToken.customer))
        .where(
            CustomerToken.token == token,
            CustomerToken.is_used.is_(False),
            CustomerToken.expires_at > datetime.utcnow()
        )
    )
    return result.scalar_one_or_none()


# ===========================================
# Public Routes (No Auth Required)
# ===========================================
@router.get("/verify/{token}", response_model=RenewalConfirmationResponse)
async def verify_customer_token(
    token: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Verify a customer token and return relevant information.
    This is the endpoint customers reach via links in emails/SMS.
    
    Example URL: https://yourdomain.com/c/verify/{token}
    """
    # Validate token
    customer_token = await validate_token(db, token)
    if not customer_token:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invalid or expired link. Please contact support."
        )
    
    # Get customer
    customer_result = await db.execute(
        select(Customer).where(Customer.id == customer_token.customer_id)
    )
    customer = customer_result.scalar_one_or_none()
    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Customer not found"
        )
    
    # Get policy if associated
    policy = None
    if customer_token.policy_id:
        policy_result = await db.execute(
            select(Policy).where(Policy.id == customer_token.policy_id)
        )
        policy = policy_result.scalar_one_or_none()
    
    # Build response with limited info
    customer_info = CustomerPublicInfo(
        first_name=customer.first_name,
        last_name=customer.last_name,
        email_masked=mask_email(customer.email)
    )
    
    policy_info = None
    if policy:
        days_until = (policy.end_date - datetime.now().date()).days
        policy_info = PolicyPublicInfo(
            policy_number=policy.policy_number,
            policy_type=policy.policy_type,
            end_date=policy.end_date.isoformat(),
            days_until_expiry=days_until,
            premium_amount=float(policy.premium_amount),
            status=policy.status.value
        )
    
    # Message based on token type
    messages = {
        CustomerTokenType.RENEWAL_CONFIRMATION: 
            "Please review your policy and confirm renewal.",
        CustomerTokenType.POLICY_VIEW: 
            "Here are your policy details.",
        CustomerTokenType.CONTACT_UPDATE: 
            "Update your contact information.",
        CustomerTokenType.UNSUBSCRIBE: 
            "Manage your communication preferences."
    }
    
    return RenewalConfirmationResponse(
        customer=customer_info,
        policy=policy_info,
        token_type=customer_token.token_type.value,
        expires_at=customer_token.expires_at.isoformat(),
        message=messages.get(
            customer_token.token_type,
            "Welcome to your secure page."
        )
    )


@router.post("/action", response_model=ActionResponse)
async def customer_action(
    action_request: RenewalActionRequest,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Process a customer action (confirm renewal, request callback, etc.)
    This doesn't require login - just a valid token.
    """
    # Validate token
    customer_token = await validate_token(db, action_request.token)
    if not customer_token:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invalid or expired link"
        )
    
    # Get customer and policy
    customer_result = await db.execute(
        select(Customer).where(Customer.id == customer_token.customer_id)
    )
    customer = customer_result.scalar_one_or_none()
    
    policy = None
    if customer_token.policy_id:
        policy_result = await db.execute(
            select(Policy).where(Policy.id == customer_token.policy_id)
        )
        policy = policy_result.scalar_one_or_none()
    
    # Process action
    action = action_request.action.lower()
    
    if action == "confirm_renewal":
        if policy:
            # Mark token as used
            customer_token.is_used = True
            customer_token.used_at = datetime.utcnow()
            customer_token.token_metadata = {
                "action": "confirm_renewal",
                "notes": action_request.notes,
                "ip": request.client.host if request.client else None
            }
            
            # Update policy status (in real system, this would trigger workflow)
            # policy.status = PolicyStatus.PENDING_RENEWAL
            
            await db.commit()
            
            return ActionResponse(
                success=True,
                message=f"Thank you {customer.first_name}! "
                        f"Your renewal confirmation has been received. "
                        f"Our team will contact you shortly."
            )
    
    elif action == "request_callback":
        # Mark token as used and record callback request
        customer_token.is_used = True
        customer_token.used_at = datetime.utcnow()
        customer_token.token_metadata = {
            "action": "request_callback",
            "preferred_time": action_request.preferred_contact_time,
            "notes": action_request.notes,
            "ip": request.client.host if request.client else None
        }
        await db.commit()
        
        return ActionResponse(
            success=True,
            message=f"Thank you {customer.first_name}! "
                    f"We will call you back soon."
        )
    
    elif action == "decline":
        customer_token.is_used = True
        customer_token.used_at = datetime.utcnow()
        customer_token.token_metadata = {
            "action": "decline",
            "notes": action_request.notes,
            "ip": request.client.host if request.client else None
        }
        await db.commit()
        
        return ActionResponse(
            success=True,
            message="We've recorded your response. "
                    "If you change your mind, please contact us."
        )
    
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown action: {action}"
        )


@router.post("/unsubscribe/{token}")
async def unsubscribe(
    token: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Allow customer to unsubscribe from communications.
    Token-based, no login required.
    """
    customer_token = await validate_token(db, token)
    if not customer_token:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invalid or expired link"
        )
    
    if customer_token.token_type != CustomerTokenType.UNSUBSCRIBE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid token type"
        )
    
    # Update customer preferences
    customer_result = await db.execute(
        select(Customer).where(Customer.id == customer_token.customer_id)
    )
    customer = customer_result.scalar_one_or_none()
    
    if customer:
        prefs = customer.communication_preferences or {}
        prefs["unsubscribed"] = True
        prefs["unsubscribed_at"] = datetime.utcnow().isoformat()
        customer.communication_preferences = prefs
        
        customer_token.is_used = True
        customer_token.used_at = datetime.utcnow()
        
        await db.commit()
    
    return {"message": "You have been unsubscribed from communications."}
