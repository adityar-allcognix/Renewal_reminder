import asyncio
import sys
import os
from datetime import date, timedelta, datetime

# Add the current directory to sys.path
sys.path.append(os.getcwd())

from app.database import AsyncSessionLocal
from app.models import Policy, PolicyStatus, RenewalReminder, ReminderStatus, Customer
from app.config import settings
from app.services.communication import CommunicationGateway

async def manual_trigger():
    print("Starting manual reminder trigger...")
    
    # 1. Check and Create Reminders
    print("\n--- Step 1: Checking for policies due for renewal ---")
    async with AsyncSessionLocal() as db:
        reminder_windows = [30, 15, 7, 1]
        reminders_created = 0
        
        from sqlalchemy import select, and_
        from sqlalchemy.orm import selectinload
        
        for days in reminder_windows:
            target_date = date.today() + timedelta(days=days)
            print(f"Checking for policies due on {target_date} ({days} days from now)")
            
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
            print(f"Found {len(policies)} policies due in {days} days")
            
            for policy in policies:
                # Check if reminder already exists
                existing = await db.execute(
                    select(RenewalReminder).where(
                        and_(
                            RenewalReminder.policy_id == policy.id,
                            RenewalReminder.reminder_type == days # reminder_type is int
                        )
                    )
                )
                
                if existing.scalar_one_or_none():
                    print(f"Reminder already exists for policy {policy.policy_number}")
                    continue
                
                customer = policy.customer
                reminder = RenewalReminder(
                    policy_id=policy.id,
                    reminder_type=days, # Storing as int
                    channel=customer.preferred_channel,
                    scheduled_date=datetime.utcnow(), # Schedule for now
                    status=ReminderStatus.PENDING
                )
                
                db.add(reminder)
                reminders_created += 1
                print(f"Created reminder for {customer.full_name} ({customer.preferred_channel})")
        
        await db.commit()
        print(f"Total reminders created: {reminders_created}")

    # 2. Send Pending Reminders
    print("\n--- Step 2: Sending pending reminders ---")
    async with AsyncSessionLocal() as db:
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
        )
        
        result = await db.execute(query)
        reminders = result.scalars().all()
        print(f"Found {len(reminders)} pending reminders")
        
        for reminder in reminders:
            policy = reminder.policy
            customer = policy.customer
            
            print(f"Sending {reminder.channel.value} to {customer.full_name} ({customer.phone})...")
            
            customer_data = {
                "name": customer.full_name,
                "email": customer.email,
                "phone": customer.phone
            }
            
            policy_data = {
                "policy_number": policy.policy_number,
                "renewal_date": policy.renewal_date.isoformat(),
                "renewal_amount": float(policy.premium_amount) * 1.03,
                "days_until_renewal": int(reminder.reminder_type)
            }
            
            # Only send if it's one of our test users to avoid spamming real people if any
            # But here we only have test users.
            
            try:
                send_result = await gateway.send_reminder(
                    channel=reminder.channel.value,
                    customer_data=customer_data,
                    policy_data=policy_data
                )
                
                print(f"Result: {send_result}")
                
                if send_result.get("status") in ["sent", "skipped", "delivered"]:
                    reminder.status = ReminderStatus.SENT
                    reminder.sent_at = datetime.utcnow()
                    reminder.external_id = (
                        send_result.get("message_id") or 
                        send_result.get("message_sid")
                    )
                else:
                    reminder.status = ReminderStatus.FAILED
                    reminder.error_message = send_result.get("error")
            except Exception as e:
                print(f"Error sending: {e}")
                reminder.status = ReminderStatus.FAILED
                reminder.error_message = str(e)
                
        await db.commit()
        print("Sending completed.")

if __name__ == "__main__":
    asyncio.run(manual_trigger())
