import asyncio
import uuid
from datetime import datetime, date, timedelta
import sys
import os
from decimal import Decimal

# Add the current directory to sys.path to allow imports from app
sys.path.append(os.getcwd())

from app.database import AsyncSessionLocal, init_db
from app.models import Customer, Policy, ReminderChannel, PolicyStatus

async def seed_specific_users():
    print("Initializing database...")
    await init_db()
    
    users_to_add = [
        {
            "first_name": "Vikram",
            "last_name": "Malhotra",
            "email": "vikram.malhotra@example.com",
            "phone": "+919049316949",
            "preferred_channel": ReminderChannel.WHATSAPP,
            "city": "Pune",
            "state": "Maharashtra"
        },
        {
            "first_name": "Sneha",
            "last_name": "Patil",
            "email": "sneha.patil@example.com",
            "phone": "+917030616494",
            "preferred_channel": ReminderChannel.SMS,
            "city": "Mumbai",
            "state": "Maharashtra"
        },
        {
            "first_name": "Arjun",
            "last_name": "Deshmukh",
            "email": "arjun.deshmukh@example.com",
            "phone": "+918007991799",
            "preferred_channel": ReminderChannel.WHATSAPP,
            "city": "Nagpur",
            "state": "Maharashtra"
        },
        {
            "first_name": "Meera",
            "last_name": "Iyer",
            "email": "meera.iyer@example.com",
            "phone": "+919421647050",
            "preferred_channel": ReminderChannel.SMS,
            "city": "Chennai",
            "state": "Tamil Nadu"
        }
    ]

    async with AsyncSessionLocal() as session:
        for user_data in users_to_add:
            # Check if customer exists by phone
            from sqlalchemy import select
            result = await session.execute(select(Customer).where(Customer.phone == user_data["phone"]))
            existing_customer = result.scalar_one_or_none()
            
            if existing_customer:
                print(f"Customer with phone {user_data['phone']} already exists. Skipping creation.")
                customer = existing_customer
            else:
                customer = Customer(
                    id=uuid.uuid4(),
                    first_name=user_data["first_name"],
                    last_name=user_data["last_name"],
                    email=user_data["email"],
                    phone=user_data["phone"],
                    address_line1="123 Test Street",
                    city=user_data["city"],
                    state=user_data["state"],
                    postal_code="400001",
                    country="India",
                    preferred_channel=user_data["preferred_channel"],
                    engagement_score=8.0,
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow()
                )
                session.add(customer)
                print(f"Adding customer: {customer.first_name} {customer.last_name}")
                # Flush to get the ID if needed (though we set it manually)
                await session.flush()

            # Check if active policy exists for this customer
            result = await session.execute(select(Policy).where(Policy.customer_id == customer.id))
            existing_policy = result.scalars().first()

            if not existing_policy:
                # Create a policy due for renewal in 30 days
                renewal_date = date.today() + timedelta(days=30)
                start_date = renewal_date - timedelta(days=365)
                
                policy = Policy(
                    id=uuid.uuid4(),
                    policy_number=f"POL-{uuid.uuid4().hex[:8].upper()}",
                    customer_id=customer.id,
                    policy_type="Auto Insurance",
                    coverage_type="Comprehensive",
                    coverage_amount=Decimal("500000.00"),
                    premium_amount=Decimal("15000.00"),
                    payment_frequency="Annual",
                    start_date=start_date,
                    end_date=renewal_date,
                    renewal_date=renewal_date,
                    status=PolicyStatus.ACTIVE,
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow()
                )
                session.add(policy)
                print(f"Added policy {policy.policy_number} for {customer.first_name}")
            else:
                print(f"Policy already exists for {customer.first_name}")
        
        await session.commit()
        print("Seeding completed.")

if __name__ == "__main__":
    asyncio.run(seed_specific_users())
