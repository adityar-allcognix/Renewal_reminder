"""
Reminder Tasks - Celery tasks for renewal reminder processing
"""

import asyncio
from datetime import datetime, date, timedelta
import structlog

from app.celery_app import celery_app
from app.database import AsyncSessionLocal
from app.models import Policy, PolicyStatus, RenewalReminder, ReminderStatus, Customer
from app.config import settings

logger = structlog.get_logger()


def run_async(coro):
    """Helper to run async functions in Celery tasks."""
    loop = asyncio.get_event_loop()
    if loop.is_running():
        return asyncio.ensure_future(coro)
    return loop.run_until_complete(coro)


@celery_app.task(bind=True, max_retries=3)
def check_and_create_reminders(self):
    """
    Check for policies due for renewal and create reminder records.
    """
    logger.info("Celery: Starting renewal reminder check")
    
    async def _check():
        from sqlalchemy import select, and_
        from sqlalchemy.orm import selectinload
        
        async with AsyncSessionLocal() as db:
            try:
                reminder_windows = settings.reminder_window_days
                reminders_created = 0
                
                for days in reminder_windows:
                    target_date = date.today() + timedelta(days=days)
                    
                    query = (
                        select(Policy)
                        .options(selectinload(Policy.customer))
                        .where(
                            and_(
                                Policy.renewal_date == target_date,
                                Policy.status == PolicyStatus.ACTIVE
                            )
                        )
                    )
                    
                    result = await db.execute(query)
                    policies = result.scalars().all()
                    
                    for policy in policies:
                        existing = await db.execute(
                            select(RenewalReminder).where(
                                and_(
                                    RenewalReminder.policy_id == policy.id,
                                    RenewalReminder.reminder_type == days
                                )
                            )
                        )
                        
                        if existing.scalar_one_or_none():
                            continue
                        
                        customer = policy.customer
                        reminder = RenewalReminder(
                            policy_id=policy.id,
                            reminder_type=days,
                            channel=customer.preferred_channel,
                            scheduled_date=datetime.utcnow(),
                            status=ReminderStatus.PENDING
                        )
                        
                        db.add(reminder)
                        reminders_created += 1
                
                await db.commit()
                return reminders_created
                
            except Exception as e:
                logger.error("Celery: Error in reminder check", error=str(e))
                await db.rollback()
                raise
    
    try:
        result = run_async(_check())
        logger.info("Celery: Reminder check complete", reminders_created=result)
        return {"status": "success", "reminders_created": result}
    except Exception as e:
        logger.error("Celery: Task failed", error=str(e))
        self.retry(exc=e, countdown=60)


@celery_app.task(bind=True, max_retries=3)
def send_pending_reminders(self):
    """
    Send all pending reminders that are due.
    """
    logger.info("Celery: Starting to send pending reminders")
    
    async def _send():
        from sqlalchemy import select, and_
        from sqlalchemy.orm import selectinload
        from app.services.communication import CommunicationGateway
        
        async with AsyncSessionLocal() as db:
            try:
                gateway = CommunicationGateway()
                
                query = (
                    select(RenewalReminder)
                    .options(
                        selectinload(RenewalReminder.policy)
                        .selectinload(Policy.customer)
                    )
                    .where(
                        and_(
                            RenewalReminder.status == ReminderStatus.PENDING,
                            RenewalReminder.scheduled_date <= datetime.utcnow()
                        )
                    )
                    .limit(50)
                )
                
                result = await db.execute(query)
                reminders = result.scalars().all()
                
                sent = 0
                failed = 0
                
                for reminder in reminders:
                    policy = reminder.policy
                    customer = policy.customer
                    
                    customer_data = {
                        "name": customer.full_name,
                        "email": customer.email,
                        "phone": customer.phone
                    }
                    
                    policy_data = {
                        "policy_number": policy.policy_number,
                        "renewal_date": policy.renewal_date.isoformat(),
                        "renewal_amount": float(policy.premium_amount) * 1.03,
                        "days_until_renewal": reminder.reminder_type
                    }
                    
                    send_result = await gateway.send_reminder(
                        channel=reminder.channel.value,
                        customer_data=customer_data,
                        policy_data=policy_data
                    )
                    
                    if send_result.get("status") in ["sent", "skipped"]:
                        reminder.status = ReminderStatus.SENT
                        reminder.sent_at = datetime.utcnow()
                        reminder.external_id = (
                            send_result.get("message_id") or 
                            send_result.get("message_sid")
                        )
                        sent += 1
                    else:
                        reminder.status = ReminderStatus.FAILED
                        reminder.error_message = send_result.get("error")
                        reminder.retry_count += 1
                        if reminder.retry_count < 3:
                            reminder.status = ReminderStatus.PENDING
                        failed += 1
                
                await db.commit()
                return {"sent": sent, "failed": failed}
                
            except Exception as e:
                logger.error("Celery: Error sending reminders", error=str(e))
                await db.rollback()
                raise
    
    try:
        result = run_async(_send())
        logger.info("Celery: Send complete", **result)
        return {"status": "success", **result}
    except Exception as e:
        logger.error("Celery: Task failed", error=str(e))
        self.retry(exc=e, countdown=60)


@celery_app.task(bind=True)
def update_policy_statuses(self):
    """
    Update policy statuses based on renewal dates.
    """
    logger.info("Celery: Updating policy statuses")
    
    async def _update():
        from sqlalchemy import select, and_
        
        async with AsyncSessionLocal() as db:
            try:
                today = date.today()
                threshold = today + timedelta(days=30)
                
                # Mark as pending renewal
                pending_q = (
                    select(Policy)
                    .where(
                        and_(
                            Policy.status == PolicyStatus.ACTIVE,
                            Policy.renewal_date <= threshold,
                            Policy.renewal_date >= today
                        )
                    )
                )
                
                result = await db.execute(pending_q)
                pending_policies = result.scalars().all()
                
                pending_count = 0
                for policy in pending_policies:
                    policy.status = PolicyStatus.PENDING_RENEWAL
                    pending_count += 1
                
                # Mark overdue as lapsed
                lapsed_q = (
                    select(Policy)
                    .where(
                        and_(
                            Policy.status.in_([
                                PolicyStatus.ACTIVE,
                                PolicyStatus.PENDING_RENEWAL
                            ]),
                            Policy.renewal_date < today
                        )
                    )
                )
                
                result = await db.execute(lapsed_q)
                lapsed_policies = result.scalars().all()
                
                lapsed_count = 0
                for policy in lapsed_policies:
                    policy.status = PolicyStatus.LAPSED
                    lapsed_count += 1
                
                await db.commit()
                return {"pending": pending_count, "lapsed": lapsed_count}
                
            except Exception as e:
                logger.error("Celery: Error updating statuses", error=str(e))
                await db.rollback()
                raise
    
    result = run_async(_update())
    logger.info("Celery: Status update complete", **result)
    return {"status": "success", **result}


@celery_app.task(bind=True)
def calculate_engagement_scores(self):
    """
    Calculate engagement scores for all customers.
    """
    logger.info("Celery: Calculating engagement scores")
    
    async def _calculate():
        from sqlalchemy import select, func, and_
        from app.models import InteractionLog
        
        async with AsyncSessionLocal() as db:
            try:
                customers = (await db.execute(select(Customer))).scalars().all()
                updated = 0
                
                for customer in customers:
                    score = 50.0
                    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
                    
                    # Interactions
                    int_q = select(func.count(InteractionLog.id)).where(
                        and_(
                            InteractionLog.customer_id == customer.id,
                            InteractionLog.created_at >= thirty_days_ago
                        )
                    )
                    int_count = (await db.execute(int_q)).scalar() or 0
                    score += min(int_count * 2, 20)
                    
                    # Renewals
                    ren_q = select(func.count(Policy.id)).where(
                        and_(
                            Policy.customer_id == customer.id,
                            Policy.status == PolicyStatus.RENEWED
                        )
                    )
                    ren_count = (await db.execute(ren_q)).scalar() or 0
                    score += min(ren_count * 5, 15)
                    
                    # No lapsed
                    lap_q = select(func.count(Policy.id)).where(
                        and_(
                            Policy.customer_id == customer.id,
                            Policy.status == PolicyStatus.LAPSED
                        )
                    )
                    lap_count = (await db.execute(lap_q)).scalar() or 0
                    if lap_count == 0:
                        score += 15
                    else:
                        score -= min(lap_count * 10, 30)
                    
                    customer.engagement_score = max(0, min(100, score))
                    updated += 1
                
                await db.commit()
                return updated
                
            except Exception as e:
                logger.error("Celery: Error calculating scores", error=str(e))
                await db.rollback()
                raise
    
    result = run_async(_calculate())
    logger.info("Celery: Engagement calculation complete", updated=result)
    return {"status": "success", "customers_updated": result}
