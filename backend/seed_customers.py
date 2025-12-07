import asyncio
import uuid
from datetime import datetime
import sys
import os

# Add the current directory to sys.path to allow imports from app
sys.path.append(os.getcwd())

from app.database import AsyncSessionLocal, init_db
from app.models import Customer, ReminderChannel

async def seed_customers():
    print("Initializing database...")
    await init_db()
    
    async with AsyncSessionLocal() as session:
        customers = [
            Customer(
                id=uuid.uuid4(),
                first_name="Aarav",
                last_name="Patel",
                email="aarav.patel@example.com",
                phone="+919876543210",
                address_line1="123 MG Road",
                city="Mumbai",
                state="Maharashtra",
                postal_code="400001",
                country="India",
                preferred_channel=ReminderChannel.EMAIL,
                engagement_score=8.5,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            ),
            Customer(
                id=uuid.uuid4(),
                first_name="Priya",
                last_name="Sharma",
                email="priya.sharma@example.com",
                phone="+919876543211",
                address_line1="456 Park Street",
                city="Delhi",
                state="Delhi",
                postal_code="110001",
                country="India",
                preferred_channel=ReminderChannel.WHATSAPP,
                engagement_score=9.0,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            ),
            Customer(
                id=uuid.uuid4(),
                first_name="Rohan",
                last_name="Gupta",
                email="rohan.gupta@example.com",
                phone="+919876543212",
                address_line1="789 Residency Road",
                city="Bangalore",
                state="Karnataka",
                postal_code="560025",
                country="India",
                preferred_channel=ReminderChannel.SMS,
                engagement_score=7.2,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            ),
             Customer(
                id=uuid.uuid4(),
                first_name="Ananya",
                last_name="Singh",
                email="ananya.singh@example.com",
                phone="+919876543213",
                address_line1="321 Jubilee Hills",
                city="Hyderabad",
                state="Telangana",
                postal_code="500033",
                country="India",
                preferred_channel=ReminderChannel.EMAIL,
                engagement_score=6.5,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
        ]
        
        for customer in customers:
            # Check if email exists
            from sqlalchemy import select
            result = await session.execute(select(Customer).where(Customer.email == customer.email))
            existing = result.scalar_one_or_none()
            
            if not existing:
                session.add(customer)
                print(f"Adding customer: {customer.first_name} {customer.last_name}")
            else:
                print(f"Customer already exists: {customer.email}")
        
        await session.commit()
        print("Seeding completed.")

if __name__ == "__main__":
    asyncio.run(seed_customers())
