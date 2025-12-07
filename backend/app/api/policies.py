"""
Policies API Routes
"""

from typing import List, Optional
from uuid import UUID
from datetime import date, timedelta
import math

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models import Policy, Customer, PolicyStatus
from app.schemas import (
    PolicyCreate, PolicyUpdate, PolicyResponse, 
    PolicyWithCustomer, PolicyDetails, RenewalAmount, PaginatedResponse
)

router = APIRouter()


@router.get("/", response_model=PaginatedResponse[PolicyResponse])
async def list_policies(
    status: Optional[PolicyStatus] = None,
    customer_id: Optional[UUID] = None,
    renewal_within_days: Optional[int] = None,
    page: int = Query(1, ge=1),
    size: int = Query(10, ge=1, le=100),
    db: AsyncSession = Depends(get_db)
):
    """List policies with optional filters."""
    skip = (page - 1) * size
    
    query = select(Policy)
    count_query = select(func.count()).select_from(Policy)
    
    filters = []
    if status:
        filters.append(Policy.status == status)
    if customer_id:
        filters.append(Policy.customer_id == customer_id)
    if renewal_within_days:
        target_date = date.today() + timedelta(days=renewal_within_days)
        filters.append(and_(
            Policy.renewal_date <= target_date,
            Policy.renewal_date >= date.today()
        ))
    
    if filters:
        query = query.where(and_(*filters))
        count_query = count_query.where(and_(*filters))
    
    # Get total count
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0
    
    query = query.offset(skip).limit(size)
    result = await db.execute(query)
    items = result.scalars().all()
    
    pages = math.ceil(total / size) if size > 0 else 0
    
    return PaginatedResponse(
        items=items,
        total=total,
        page=page,
        size=size,
        pages=pages
    )


@router.get("/due-for-renewal", response_model=List[PolicyWithCustomer])
async def get_policies_due_for_renewal(
    days: int = Query(30, description="Days until renewal"),
    db: AsyncSession = Depends(get_db)
):
    """Get policies due for renewal within specified days."""
    target_date = date.today() + timedelta(days=days)
    
    query = (
        select(Policy)
        .options(selectinload(Policy.customer))
        .where(
            and_(
                Policy.renewal_date <= target_date,
                Policy.renewal_date >= date.today(),
                Policy.status == PolicyStatus.ACTIVE
            )
        )
        .order_by(Policy.renewal_date)
    )
    
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/{policy_id}", response_model=PolicyWithCustomer)
async def get_policy(
    policy_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    """Get a specific policy by ID."""
    query = (
        select(Policy)
        .options(selectinload(Policy.customer))
        .where(Policy.id == policy_id)
    )
    result = await db.execute(query)
    policy = result.scalar_one_or_none()
    
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")
    
    return policy


@router.get("/by-number/{policy_number}", response_model=PolicyWithCustomer)
async def get_policy_by_number(
    policy_number: str,
    db: AsyncSession = Depends(get_db)
):
    """Get a policy by policy number."""
    query = (
        select(Policy)
        .options(selectinload(Policy.customer))
        .where(Policy.policy_number == policy_number)
    )
    result = await db.execute(query)
    policy = result.scalar_one_or_none()
    
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")
    
    return policy


@router.post("/", response_model=PolicyResponse, status_code=201)
async def create_policy(
    policy_data: PolicyCreate,
    db: AsyncSession = Depends(get_db)
):
    """Create a new policy."""
    # Verify customer exists
    customer = await db.get(Customer, policy_data.customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    
    # Check for duplicate policy number
    existing = await db.execute(
        select(Policy).where(Policy.policy_number == policy_data.policy_number)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Policy number already exists")
    
    policy = Policy(**policy_data.model_dump())
    db.add(policy)
    await db.commit()
    await db.refresh(policy)
    
    return policy


@router.patch("/{policy_id}", response_model=PolicyResponse)
async def update_policy(
    policy_id: UUID,
    policy_data: PolicyUpdate,
    db: AsyncSession = Depends(get_db)
):
    """Update a policy."""
    policy = await db.get(Policy, policy_id)
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")
    
    update_data = policy_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(policy, field, value)
    
    await db.commit()
    await db.refresh(policy)
    
    return policy


@router.post("/{policy_id}/renew", response_model=PolicyResponse)
async def renew_policy(
    policy_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    """Process policy renewal."""
    policy = await db.get(Policy, policy_id)
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")
    
    if policy.status != PolicyStatus.ACTIVE and policy.status != PolicyStatus.PENDING_RENEWAL:
        raise HTTPException(
            status_code=400, 
            detail=f"Cannot renew policy with status: {policy.status}"
        )
    
    # Update dates for renewal
    policy.start_date = policy.renewal_date
    policy.end_date = policy.renewal_date + timedelta(days=365)
    policy.renewal_date = policy.end_date
    policy.status = PolicyStatus.RENEWED
    
    await db.commit()
    await db.refresh(policy)
    
    return policy


# ===========================================
# AI Agent Tool Endpoints
# ===========================================
@router.get("/{policy_id}/details", response_model=PolicyDetails)
async def get_policy_details_for_agent(
    policy_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    """Get policy details formatted for AI agent."""
    query = (
        select(Policy)
        .options(selectinload(Policy.customer))
        .where(Policy.id == policy_id)
    )
    result = await db.execute(query)
    policy = result.scalar_one_or_none()
    
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")
    
    days_until = (policy.renewal_date - date.today()).days
    
    return PolicyDetails(
        policy_number=policy.policy_number,
        customer_name=policy.customer.full_name,
        policy_type=policy.policy_type,
        coverage_type=policy.coverage_type,
        coverage_amount=policy.coverage_amount,
        premium_amount=policy.premium_amount,
        renewal_date=policy.renewal_date,
        days_until_renewal=days_until,
        status=policy.status.value
    )


@router.get("/{policy_id}/renewal-amount", response_model=RenewalAmount)
async def calculate_renewal_amount(
    policy_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    """Calculate renewal amount for a policy."""
    policy = await db.get(Policy, policy_id)
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")
    
    # Simple renewal calculation (can be enhanced with ML model)
    current_premium = policy.premium_amount
    # Example: 3% annual increase
    renewal_premium = current_premium * 1.03
    premium_change = renewal_premium - current_premium
    
    return RenewalAmount(
        policy_number=policy.policy_number,
        current_premium=current_premium,
        renewal_premium=renewal_premium,
        premium_change=premium_change,
        premium_change_percent=3.0,
        renewal_date=policy.renewal_date,
        breakdown={
            "base_premium": current_premium,
            "inflation_adjustment": premium_change,
            "discounts": 0,
            "total": renewal_premium
        }
    )
