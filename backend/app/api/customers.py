"""
Customers API Routes
"""

from typing import List, Optional
from uuid import UUID
import math

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models import Customer
from app.schemas import CustomerCreate, CustomerUpdate, CustomerResponse, PaginatedResponse

router = APIRouter()


@router.get("/", response_model=PaginatedResponse[CustomerResponse])
async def list_customers(
    search: Optional[str] = None,
    page: int = Query(1, ge=1),
    size: int = Query(10, ge=1, le=100),
    db: AsyncSession = Depends(get_db)
):
    """List customers with optional search."""
    skip = (page - 1) * size
    
    # Base query
    query = select(Customer)
    count_query = select(func.count()).select_from(Customer)
    
    if search:
        search_term = f"%{search}%"
        filters = (
            Customer.email.ilike(search_term) |
            Customer.first_name.ilike(search_term) |
            Customer.last_name.ilike(search_term)
        )
        query = query.where(filters)
        count_query = count_query.where(filters)
    
    # Get total count
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0
    
    # Get items
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


@router.get("/{customer_id}", response_model=CustomerResponse)
async def get_customer(
    customer_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    """Get a specific customer by ID."""
    customer = await db.get(Customer, customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    return customer


@router.get("/by-email/{email}", response_model=CustomerResponse)
async def get_customer_by_email(
    email: str,
    db: AsyncSession = Depends(get_db)
):
    """Get a customer by email."""
    query = select(Customer).where(Customer.email == email)
    result = await db.execute(query)
    customer = result.scalar_one_or_none()
    
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    return customer


@router.post("/", response_model=CustomerResponse, status_code=201)
async def create_customer(
    customer_data: CustomerCreate,
    db: AsyncSession = Depends(get_db)
):
    """Create a new customer."""
    # Check for duplicate email
    existing = await db.execute(
        select(Customer).where(Customer.email == customer_data.email)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email already registered")
    
    customer = Customer(**customer_data.model_dump())
    db.add(customer)
    await db.commit()
    await db.refresh(customer)
    
    return customer


@router.patch("/{customer_id}", response_model=CustomerResponse)
async def update_customer(
    customer_id: UUID,
    customer_data: CustomerUpdate,
    db: AsyncSession = Depends(get_db)
):
    """Update a customer."""
    customer = await db.get(Customer, customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    
    update_data = customer_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(customer, field, value)
    
    await db.commit()
    await db.refresh(customer)
    
    return customer


@router.delete("/{customer_id}", status_code=204)
async def delete_customer(
    customer_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    """Delete a customer."""
    customer = await db.get(Customer, customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    
    await db.delete(customer)
    await db.commit()


@router.get("/{customer_id}/policies")
async def get_customer_policies(
    customer_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    """Get all policies for a customer."""
    query = (
        select(Customer)
        .options(selectinload(Customer.policies))
        .where(Customer.id == customer_id)
    )
    result = await db.execute(query)
    customer = result.scalar_one_or_none()
    
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    
    return customer.policies
