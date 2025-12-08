"""
Communication Tasks - Celery tasks for sending messages and retention outreach
"""

import asyncio
from datetime import datetime, date, timedelta
from typing import Dict, Any, Optional
import structlog

from app.celery_app import celery_app
from app.database import AsyncSessionLocal
from app.models import (
    Customer, Policy, PolicyStatus, 
    OutreachLog, OutreachType, ReminderChannel
)
from app.config import settings

logger = structlog.get_logger()


def run_async(coro):
    """Helper to run async functions in Celery tasks."""
    loop = asyncio.get_event_loop()
    if loop.is_running():
        return asyncio.ensure_future(coro)
    return loop.run_until_complete(coro)


@celery_app.task(bind=True, max_retries=3)
def send_email_task(
    self,
    to_email: str,
    subject: str,
    html_content: str,
    customer_id: str = None,
    policy_id: str = None
):
    """
    Send an email asynchronously.
    """
    logger.info("Celery: Sending email", to=to_email, subject=subject)
    
    async def _send():
        from app.services.communication import EmailService
        
        service = EmailService()
        result = await service.send_email(to_email, subject, html_content)
        
        # Log outreach if customer_id provided
        if customer_id:
            async with AsyncSessionLocal() as db:
                log = OutreachLog(
                    customer_id=customer_id,
                    policy_id=policy_id,
                    outreach_type=OutreachType.REMINDER,
                    channel=ReminderChannel.EMAIL,
                    subject=subject,
                    message=html_content[:500],
                    sent_at=datetime.utcnow(),
                    delivered=result.get("status") == "sent"
                )
                db.add(log)
                await db.commit()
        
        return result
    
    try:
        result = run_async(_send())
        return result
    except Exception as e:
        logger.error("Celery: Email task failed", error=str(e))
        self.retry(exc=e, countdown=60)


@celery_app.task(bind=True, max_retries=3)
def send_sms_task(
    self,
    to_number: str,
    message: str,
    customer_id: str = None,
    policy_id: str = None
):
    """
    Send an SMS asynchronously.
    """
    logger.info("Celery: Sending SMS", to=to_number)
    
    async def _send():
        from app.services.communication import SMSService
        
        service = SMSService()
        result = await service.send_sms(to_number, message)
        
        if customer_id:
            async with AsyncSessionLocal() as db:
                log = OutreachLog(
                    customer_id=customer_id,
                    policy_id=policy_id,
                    outreach_type=OutreachType.REMINDER,
                    channel=ReminderChannel.SMS,
                    message=message,
                    sent_at=datetime.utcnow(),
                    delivered=result.get("status") == "sent"
                )
                db.add(log)
                await db.commit()
        
        return result
    
    try:
        result = run_async(_send())
        return result
    except Exception as e:
        logger.error("Celery: SMS task failed", error=str(e))
        self.retry(exc=e, countdown=60)


@celery_app.task(bind=True, max_retries=3)
def send_whatsapp_task(
    self,
    to_number: str,
    message: str,
    customer_id: str = None,
    policy_id: str = None
):
    """
    Send a WhatsApp message asynchronously.
    """
    logger.info("Celery: Sending WhatsApp", to=to_number)
    
    async def _send():
        from app.services.communication import WhatsAppService
        
        service = WhatsAppService()
        result = await service.send_whatsapp(to_number, message)
        
        if customer_id:
            async with AsyncSessionLocal() as db:
                log = OutreachLog(
                    customer_id=customer_id,
                    policy_id=policy_id,
                    outreach_type=OutreachType.REMINDER,
                    channel=ReminderChannel.WHATSAPP,
                    message=message,
                    sent_at=datetime.utcnow(),
                    delivered=result.get("status") == "sent"
                )
                db.add(log)
                await db.commit()
        
        return result
    
    try:
        result = run_async(_send())
        return result
    except Exception as e:
        logger.error("Celery: WhatsApp task failed", error=str(e))
        self.retry(exc=e, countdown=60)


@celery_app.task(bind=True)
def process_retention_outreach(self):
    """
    Process retention outreach for customers who haven't responded to reminders.
    Identifies customers with pending renewals who need follow-up.
    """
    logger.info("Celery: Processing retention outreach")
    
    async def _process():
        from sqlalchemy import select, and_, func
        from sqlalchemy.orm import selectinload
        from app.models import RenewalReminder, ReminderStatus
        from app.services.communication import CommunicationGateway
        
        async with AsyncSessionLocal() as db:
            try:
                gateway = CommunicationGateway()
                today = date.today()
                
                # Find policies where:
                # 1. Status is pending renewal
                # 2. Renewal date is within 7 days
                # 3. No recent outreach in last 3 days
                
                three_days_ago = datetime.utcnow() - timedelta(days=3)
                
                # Get policies needing follow-up
                query = (
                    select(Policy)
                    .options(selectinload(Policy.customer))
                    .where(
                        and_(
                            Policy.status == PolicyStatus.PENDING_RENEWAL,
                            Policy.renewal_date <= today + timedelta(days=7),
                            Policy.renewal_date >= today
                        )
                    )
                )
                
                result = await db.execute(query)
                policies = result.scalars().all()
                
                outreach_sent = 0
                
                for policy in policies:
                    customer = policy.customer
                    
                    # Check for recent outreach
                    recent_outreach = await db.execute(
                        select(func.count(OutreachLog.id)).where(
                            and_(
                                OutreachLog.customer_id == customer.id,
                                OutreachLog.policy_id == policy.id,
                                OutreachLog.outreach_type == OutreachType.RETENTION,
                                OutreachLog.sent_at >= three_days_ago
                            )
                        )
                    )
                    
                    if (recent_outreach.scalar() or 0) > 0:
                        continue  # Skip if recently contacted
                    
                    # Determine urgency based on days until renewal
                    days_remaining = (policy.renewal_date - today).days
                    
                    # Send retention message
                    customer_data = {
                        "name": customer.full_name,
                        "email": customer.email,
                        "phone": customer.phone
                    }
                    
                    policy_data = {
                        "policy_number": policy.policy_number,
                        "renewal_date": policy.renewal_date.isoformat(),
                        "renewal_amount": float(policy.premium_amount) * 1.03,
                        "days_until_renewal": days_remaining
                    }
                    
                    # Use customer's preferred channel
                    send_result = await gateway.send_reminder(
                        channel=customer.preferred_channel.value,
                        customer_data=customer_data,
                        policy_data=policy_data
                    )
                    
                    # Log the outreach
                    log = OutreachLog(
                        customer_id=customer.id,
                        policy_id=policy.id,
                        outreach_type=OutreachType.RETENTION,
                        channel=customer.preferred_channel,
                        subject=f"Urgent: Policy {policy.policy_number} Renewal",
                        message=f"Retention follow-up for policy expiring in {days_remaining} days",
                        sent_at=datetime.utcnow(),
                        delivered=send_result.get("status") in ["sent", "skipped"]
                    )
                    db.add(log)
                    
                    if send_result.get("status") in ["sent", "skipped"]:
                        outreach_sent += 1
                
                await db.commit()
                return outreach_sent
                
            except Exception as e:
                logger.error("Celery: Error in retention outreach", error=str(e))
                await db.rollback()
                raise
    
    result = run_async(_process())
    logger.info("Celery: Retention outreach complete", sent=result)
    return {"status": "success", "outreach_sent": result}


@celery_app.task(bind=True)
def send_renewal_confirmation(
    self,
    customer_id: str,
    policy_id: str,
    policy_number: str
):
    """
    Send renewal confirmation to customer.
    """
    logger.info("Celery: Sending renewal confirmation", policy=policy_number)
    
    async def _send():
        from sqlalchemy import select
        from app.services.communication import EmailService
        
        async with AsyncSessionLocal() as db:
            customer = await db.get(Customer, customer_id)
            policy = await db.get(Policy, policy_id)
            
            if not customer or not policy:
                return {"status": "failed", "error": "Customer or policy not found"}
            
            service = EmailService()
            
            html_content = f"""
            <html>
            <body style="font-family: Arial, sans-serif;">
                <h2>Renewal Confirmation</h2>
                <p>Dear {customer.full_name},</p>
                <p>Your policy <strong>{policy_number}</strong> has been successfully renewed.</p>
                <div style="background: #f0f9ff; padding: 20px; border-radius: 8px;">
                    <p><strong>New End Date:</strong> {policy.end_date.isoformat()}</p>
                    <p><strong>Premium Amount:</strong> ${float(policy.premium_amount):,.2f}</p>
                </div>
                <p>Thank you for continuing to trust us with your insurance needs!</p>
            </body>
            </html>
            """
            
            result = await service.send_email(
                to_email=customer.email,
                subject=f"Policy Renewed: {policy_number}",
                html_content=html_content
            )
            
            # Log the confirmation
            log = OutreachLog(
                customer_id=customer.id,
                policy_id=policy.id,
                outreach_type=OutreachType.CONFIRMATION,
                channel=ReminderChannel.EMAIL,
                subject=f"Policy Renewed: {policy_number}",
                message="Renewal confirmation sent",
                sent_at=datetime.utcnow(),
                delivered=result.get("status") == "sent"
            )
            db.add(log)
            await db.commit()
            
            return result
    
    return run_async(_send())

# -------------------------------------------------------------------------
# User Requested Tasks (Adapted)
# -------------------------------------------------------------------------

@celery_app.task(
    name="tasks.send_email_sendgrid",
    bind=True,
    max_retries=3,
    default_retry_delay=60 * 2,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=60 * 10,
    retry_jitter=True,
    acks_late=True
)
def send_email_sendgrid_task(
    self,
    to_email: str,
    subject: str,
    html_content: str,
    from_email: Optional[str] = None,
    app_name: Optional[str] = None,
    plain_content: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None
):
    """Send email via SendGrid (Adapted from user request)."""
    task_id = self.request.id
    logger.info(f"Task {task_id}: Sending email to {to_email}")
    
    async def _send():
        from app.services.communication import EmailService
        service = EmailService()
        # Note: Ignoring from_email override for now as Service uses config default
        # Ignoring app_name and metadata as Service doesn't use them yet
        result = await service.send_email(
            to_email=to_email,
            subject=subject,
            html_content=html_content,
            plain_content=plain_content
        )
        return result

    try:
        result = run_async(_send())
        return result
    except Exception as e:
        logger.error(f"Task {task_id} failed: {str(e)}")
        raise self.retry(exc=e)


@celery_app.task(
    name="tasks.send_sms_twilio",
    bind=True,
    max_retries=3,
    default_retry_delay=60 * 2,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=60 * 10,
    retry_jitter=True,
    acks_late=True
)
def send_sms_twilio_task(
    self,
    to_number: str,
    message_body: str,
    from_number: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None
):
    """Send SMS via Twilio (Adapted from user request)."""
    task_id = self.request.id
    logger.info(f"Task {task_id}: Sending SMS to {to_number}")
    
    async def _send():
        from app.services.communication import SMSService
        service = SMSService()
        # Note: Ignoring from_number override for now as Service uses config default
        result = await service.send_sms(to_number, message_body)
        return result

    try:
        result = run_async(_send())
        return result
    except Exception as e:
        logger.error(f"Task {task_id} failed: {str(e)}")
        raise self.retry(exc=e)
