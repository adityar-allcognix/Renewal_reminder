"""
Reminders API Routes
"""

from typing import List, Optional
from uuid import UUID
from datetime import datetime, date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models import RenewalReminder, Policy, ReminderStatus, ReminderChannel
from app.schemas import ReminderCreate, ReminderUpdate, ReminderResponse

router = APIRouter()


@router.get("/", response_model=List[ReminderResponse])
async def list_reminders(
    status: Optional[ReminderStatus] = None,
    policy_id: Optional[UUID] = None,
    channel: Optional[ReminderChannel] = None,
    from_date: Optional[datetime] = None,
    to_date: Optional[datetime] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, le=500),
    db: AsyncSession = Depends(get_db)
):
    """List reminders with optional filters."""
    query = select(RenewalReminder)
    
    if status:
        query = query.where(RenewalReminder.status == status)
    if policy_id:
        query = query.where(RenewalReminder.policy_id == policy_id)
    if channel:
        query = query.where(RenewalReminder.channel == channel)
    if from_date:
        query = query.where(RenewalReminder.scheduled_date >= from_date)
    if to_date:
        query = query.where(RenewalReminder.scheduled_date <= to_date)
    
    query = query.order_by(RenewalReminder.scheduled_date).offset(skip).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/pending", response_model=List[ReminderResponse])
async def get_pending_reminders(
    db: AsyncSession = Depends(get_db)
):
    """Get all pending reminders that should be sent."""
    now = datetime.utcnow()
    
    query = (
        select(RenewalReminder)
        .where(
            and_(
                RenewalReminder.status == ReminderStatus.PENDING,
                RenewalReminder.scheduled_date <= now
            )
        )
        .order_by(RenewalReminder.scheduled_date)
    )
    
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/{reminder_id}", response_model=ReminderResponse)
async def get_reminder(
    reminder_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    """Get a specific reminder by ID."""
    reminder = await db.get(RenewalReminder, reminder_id)
    if not reminder:
        raise HTTPException(status_code=404, detail="Reminder not found")
    return reminder


@router.post("/", response_model=ReminderResponse, status_code=201)
async def create_reminder(
    reminder_data: ReminderCreate,
    db: AsyncSession = Depends(get_db)
):
    """Create a new reminder."""
    # Verify policy exists
    policy = await db.get(Policy, reminder_data.policy_id)
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")
    
    reminder = RenewalReminder(**reminder_data.model_dump())
    db.add(reminder)
    await db.commit()
    await db.refresh(reminder)
    
    return reminder


@router.post("/schedule-for-policy/{policy_id}")
async def schedule_reminders_for_policy(
    policy_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    """Schedule all renewal reminders for a policy."""
    from app.config import settings
    
    # Get policy with customer
    query = (
        select(Policy)
        .options(selectinload(Policy.customer))
        .where(Policy.id == policy_id)
    )
    result = await db.execute(query)
    policy = result.scalar_one_or_none()
    
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")
    
    # Schedule reminders for each window
    created_reminders = []
    for days in settings.reminder_window_days:
        scheduled_date = datetime.combine(
            policy.renewal_date - timedelta(days=days),
            datetime.min.time()
        )
        
        # Skip if scheduled date is in the past
        if scheduled_date < datetime.utcnow():
            continue
        
        reminder = RenewalReminder(
            policy_id=policy.id,
            reminder_type=days,
            channel=policy.customer.preferred_channel,
            scheduled_date=scheduled_date,
            status=ReminderStatus.PENDING
        )
        db.add(reminder)
        created_reminders.append(reminder)
    
    await db.commit()
    
    return {
        "message": f"Scheduled {len(created_reminders)} reminders",
        "policy_id": str(policy_id),
        "reminders_created": len(created_reminders)
    }


@router.patch("/{reminder_id}", response_model=ReminderResponse)
async def update_reminder(
    reminder_id: UUID,
    reminder_data: ReminderUpdate,
    db: AsyncSession = Depends(get_db)
):
    """Update a reminder."""
    reminder = await db.get(RenewalReminder, reminder_id)
    if not reminder:
        raise HTTPException(status_code=404, detail="Reminder not found")
    
    update_data = reminder_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(reminder, field, value)
    
    await db.commit()
    await db.refresh(reminder)
    
    return reminder


@router.post("/{reminder_id}/send")
async def send_reminder(
    reminder_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    """Trigger sending of a specific reminder."""
    reminder = await db.get(RenewalReminder, reminder_id)
    if not reminder:
        raise HTTPException(status_code=404, detail="Reminder not found")
    
    if reminder.status != ReminderStatus.PENDING:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot send reminder with status: {reminder.status}"
        )
    
    # Import and call the communication service
    from app.services.communication import send_reminder_message
    
    success = await send_reminder_message(reminder, db)
    
    if success:
        reminder.status = ReminderStatus.SENT
        reminder.sent_at = datetime.utcnow()
    else:
        reminder.status = ReminderStatus.FAILED
        reminder.retry_count += 1
    
    await db.commit()
    await db.refresh(reminder)
    
    return {
        "success": success,
        "reminder_id": str(reminder_id),
        "status": reminder.status.value
    }


@router.delete("/{reminder_id}", status_code=204)
async def cancel_reminder(
    reminder_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    """Cancel a pending reminder."""
    reminder = await db.get(RenewalReminder, reminder_id)
    if not reminder:
        raise HTTPException(status_code=404, detail="Reminder not found")
    
    if reminder.status != ReminderStatus.PENDING:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot cancel reminder with status: {reminder.status}"
        )
    
    reminder.status = ReminderStatus.CANCELLED
    await db.commit()
