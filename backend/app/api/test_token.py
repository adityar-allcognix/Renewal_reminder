
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models import Customer, Policy, CustomerToken, CustomerTokenType
from app.api.customer_public import create_customer_token
from pydantic import BaseModel
import uuid

router = APIRouter()

class TestTokenRequest(BaseModel):
    customer_email: str
    policy_number: str

@router.post("/generate-token")
async def generate_test_token(
    request: TestTokenRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Generate a valid token for testing purposes.
    Requires existing customer and policy.
    """
    # Find customer
    customer_result = await db.execute(
        select(Customer).where(Customer.email == request.customer_email)
    )
    customer = customer_result.scalar_one_or_none()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    # Find policy
    policy_result = await db.execute(
        select(Policy).where(Policy.policy_number == request.policy_number)
    )
    policy = policy_result.scalar_one_or_none()
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")

    # Create token
    token = await create_customer_token(
        db=db,
        customer_id=customer.id,
        policy_id=policy.id,
        token_type=CustomerTokenType.POLICY_VIEW
    )
    
    return {"token": token.token}
