"""
Scheduler Module - APScheduler for Renewal Reminder Scheduling
"""

from datetime import datetime, date, timedelta
from typing import Optional
import structlog

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy import select, and_
from sqlalchemy.orm import selectinload

from app.config import settings
from app.database import AsyncSessionLocal
from app.models import Policy, PolicyStatus, RenewalReminder, ReminderStatus, Customer

logger = structlog.get_logger()

# Global scheduler instance
scheduler: Optional[AsyncIOScheduler] = None


def start_scheduler():
    """Initialize and start the scheduler."""
    global scheduler
    
    scheduler = AsyncIOScheduler()
    
    # Job 1: Check for policies due for renewal and create reminders
    scheduler.add_job(
        check_and_create_reminders,
        trigger=IntervalTrigger(minutes=settings.REMINDER_CHECK_INTERVAL_MINUTES),
        id="check_renewals",
        name="Check policies for renewal reminders",
        replace_existing=True
    )
    
    # Job 2: Send pending reminders
    scheduler.add_job(
        send_pending_reminders,
        trigger=IntervalTrigger(minutes=5),
        id="send_reminders",
        name="Send pending renewal reminders",
        replace_existing=True
    )
    
    # Job 3: Update policy statuses (daily at midnight)
    scheduler.add_job(
        update_policy_statuses,
        trigger=CronTrigger(hour=0, minute=0),
        id="update_statuses",
        name="Update policy statuses daily",
        replace_existing=True
    )
    
    # Job 4: Calculate engagement scores (daily at 2 AM)
    scheduler.add_job(
        calculate_engagement_scores,
        trigger=CronTrigger(hour=2, minute=0),
        id="engagement_scores",
        name="Calculate customer engagement scores",
        replace_existing=True
    )
    
    scheduler.start()
    logger.info("Scheduler started", jobs=len(scheduler.get_jobs()))


def stop_scheduler():
    """Stop the scheduler."""
    global scheduler
    if scheduler:
        scheduler.shutdown()
        logger.info("Scheduler stopped")


async def check_and_create_reminders():
    """
    Check for policies due for renewal and create reminder records.
    Runs periodically based on REMINDER_CHECK_INTERVAL_MINUTES.
    """
    logger.info("Starting renewal reminder check")
    
    async with AsyncSessionLocal() as db:
        try:
            reminder_windows = settings.reminder_window_days
            reminders_created = 0
            
            for days in reminder_windows:
                # Find policies due in exactly 'days' days
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
                    # Check if reminder already exists
                    existing = await db.execute(
                        select(RenewalReminder).where(
                            and_(
                                RenewalReminder.policy_id == policy.id,
                                RenewalReminder.reminder_type == days
                            )
                        )
                    )
                    
                    if existing.scalar_one_or_none():
                        continue  # Skip if already exists
                    
                    # Create reminder
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
            logger.info(
                "Renewal reminder check complete",
                reminders_created=reminders_created
            )
            
        except Exception as e:
            logger.error("Error in renewal reminder check", error=str(e))
            await db.rollback()


async def send_pending_reminders():
    """
    Send all pending reminders that are due.
    Runs every 5 minutes.
    """
    logger.info("Starting to send pending reminders")
    
    async with AsyncSessionLocal() as db:
        try:
            from app.services.communication import CommunicationGateway
            
            gateway = CommunicationGateway()
            
            # Get pending reminders
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
                .limit(100)  # Process in batches
            )
            
            result = await db.execute(query)
            reminders = result.scalars().all()
            
            sent_count = 0
            failed_count = 0
            
            for reminder in reminders:
                policy = reminder.policy
                customer = policy.customer
                
                # Prepare data for communication
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
                
                # Send reminder
                result = await gateway.send_reminder(
                    channel=reminder.channel.value,
                    customer_data=customer_data,
                    policy_data=policy_data
                )
                
                # Update reminder status
                if result.get("status") == "sent":
                    reminder.status = ReminderStatus.SENT
                    reminder.sent_at = datetime.utcnow()
                    reminder.external_id = result.get("message_id") or result.get("message_sid")
                    sent_count += 1
                elif result.get("status") == "skipped":
                    # Channel not configured, mark as sent anyway in dev
                    reminder.status = ReminderStatus.SENT
                    reminder.sent_at = datetime.utcnow()
                    sent_count += 1
                else:
                    reminder.status = ReminderStatus.FAILED
                    reminder.error_message = result.get("error", "Unknown error")
                    reminder.retry_count += 1
                    failed_count += 1
                    
                    # Reset to pending if under retry limit
                    if reminder.retry_count < 3:
                        reminder.status = ReminderStatus.PENDING
            
            await db.commit()
            
            logger.info(
                "Reminder send complete",
                sent=sent_count,
                failed=failed_count
            )
            
        except Exception as e:
            logger.error("Error sending reminders", error=str(e))
            await db.rollback()


async def update_policy_statuses():
    """
    Update policy statuses based on renewal dates.
    - Mark policies as PENDING_RENEWAL if renewal date is within 30 days
    - Mark policies as LAPSED if renewal date has passed
    Runs daily at midnight.
    """
    logger.info("Updating policy statuses")
    
    async with AsyncSessionLocal() as db:
        try:
            today = date.today()
            threshold_date = today + timedelta(days=30)
            
            # Mark policies as pending renewal
            pending_query = (
                select(Policy)
                .where(
                    and_(
                        Policy.status == PolicyStatus.ACTIVE,
                        Policy.renewal_date <= threshold_date,
                        Policy.renewal_date >= today
                    )
                )
            )
            
            result = await db.execute(pending_query)
            pending_policies = result.scalars().all()
            
            pending_count = 0
            for policy in pending_policies:
                policy.status = PolicyStatus.PENDING_RENEWAL
                pending_count += 1
            
            # Mark overdue policies as lapsed
            lapsed_query = (
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
            
            result = await db.execute(lapsed_query)
            lapsed_policies = result.scalars().all()
            
            lapsed_count = 0
            for policy in lapsed_policies:
                policy.status = PolicyStatus.LAPSED
                lapsed_count += 1
            
            await db.commit()
            
            logger.info(
                "Policy status update complete",
                pending_renewal=pending_count,
                lapsed=lapsed_count
            )
            
        except Exception as e:
            logger.error("Error updating policy statuses", error=str(e))
            await db.rollback()


async def calculate_engagement_scores():
    """
    Calculate engagement scores for all customers based on:
    - Interaction frequency
    - Response to reminders
    - Policy renewals
    Runs daily at 2 AM.
    """
    logger.info("Calculating engagement scores")
    
    async with AsyncSessionLocal() as db:
        try:
            from sqlalchemy import func
            from app.models import InteractionLog, OutreachLog
            
            # Get all customers
            customers = (await db.execute(select(Customer))).scalars().all()
            
            updated_count = 0
            for customer in customers:
                score = 50.0  # Base score
                
                # Factor 1: Recent interactions (+20 max)
                thirty_days_ago = datetime.utcnow() - timedelta(days=30)
                interactions_query = select(func.count(InteractionLog.id)).where(
                    and_(
                        InteractionLog.customer_id == customer.id,
                        InteractionLog.created_at >= thirty_days_ago
                    )
                )
                interaction_count = (
                    await db.execute(interactions_query)
                ).scalar() or 0
                score += min(interaction_count * 2, 20)
                
                # Factor 2: Policy renewals (+15 max)
                renewed_policies = select(func.count(Policy.id)).where(
                    and_(
                        Policy.customer_id == customer.id,
                        Policy.status == PolicyStatus.RENEWED
                    )
                )
                renewal_count = (await db.execute(renewed_policies)).scalar() or 0
                score += min(renewal_count * 5, 15)
                
                # Factor 3: No lapsed policies (+15)
                lapsed_policies = select(func.count(Policy.id)).where(
                    and_(
                        Policy.customer_id == customer.id,
                        Policy.status == PolicyStatus.LAPSED
                    )
                )
                lapsed_count = (await db.execute(lapsed_policies)).scalar() or 0
                if lapsed_count == 0:
                    score += 15
                else:
                    score -= min(lapsed_count * 10, 30)
                
                # Clamp score between 0 and 100
                customer.engagement_score = max(0, min(100, score))
                updated_count += 1
            
            await db.commit()
            
            logger.info(
                "Engagement score calculation complete",
                customers_updated=updated_count
            )
            
        except Exception as e:
            logger.error("Error calculating engagement scores", error=str(e))
            await db.rollback()
