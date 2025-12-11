#!/usr/bin/env python3
"""
Test Document Upload Flow

This script tests the complete document upload flow:
1. Find a test customer
2. Generate an upload token
3. Print the upload URL
4. Optionally simulate the SMS webhook
"""

import asyncio
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from sqlalchemy import select
from app.database import async_session_maker
from app.models import Customer
from app.api.sms_webhook import (
    create_upload_token,
    find_customer_by_phone,
    get_customer_active_policies
)
from app.config import settings


async def test_upload_flow():
    """Test the document upload flow."""
    
    print("\n" + "="*70)
    print("DOCUMENT UPLOAD FLOW TEST")
    print("="*70 + "\n")
    
    async with async_session_maker() as db:
        # Find a test customer
        result = await db.execute(
            select(Customer).limit(1)
        )
        customer = result.scalar_one_or_none()
        
        if not customer:
            print("❌ No customers found in database.")
            print("   Please seed some test customers first.")
            return
        
        print(f"✅ Found test customer:")
        print(f"   Name: {customer.first_name} {customer.last_name}")
        print(f"   Email: {customer.email}")
        print(f"   Phone: {customer.phone or 'N/A'}")
        print()
        
        # Check for active policies
        policies = await get_customer_active_policies(db, customer.id)
        print(f"✅ Active policies: {len(policies)}")
        for policy in policies:
            print(f"   - {policy.policy_type} (#{policy.policy_number})")
        print()
        
        # Generate token
        print("🔑 Generating upload token...")
        token = await create_upload_token(db, customer.id, expiry_hours=48)
        print(f"   Token: {token[:20]}...{token[-10:]}")
        print()
        
        # Build URL
        frontend_url = settings.FRONTEND_URL or "http://localhost:3000"
        upload_url = f"{frontend_url}/upload/{token}"
        
        print("="*70)
        print("🔗 UPLOAD URL GENERATED")
        print("="*70)
        print(f"\nCustomer: {customer.first_name} {customer.last_name}")
        print(f"URL: {upload_url}")
        print(f"\nExpires: 48 hours")
        print("="*70 + "\n")
        
        # Test phone lookup if customer has phone
        if customer.phone:
            print("📱 Testing phone number lookup...")
            found_customer = await find_customer_by_phone(db, customer.phone)
            if found_customer:
                print(f"   ✅ Customer found by phone: {found_customer.email}")
            else:
                print(f"   ❌ Customer not found by phone")
            print()
        
        print("✅ Test completed successfully!")
        print("\nNext steps:")
        print("1. Copy the URL above and open in browser")
        print("2. Try uploading a test PDF, JPEG, or PNG file")
        print("3. Check backend logs for upload confirmation")
        print("\nOr test via API:")
        print(f"   curl -X POST 'http://localhost:8000/api/test/test-upload-request' \\")
        print(f"        -H 'Content-Type: application/json' \\")
        print(f"        -d '{{\"customer_email\": \"{customer.email}\"}}'")
        print()


async def test_sms_webhook_simulation():
    """Simulate the SMS webhook."""
    
    print("\n" + "="*70)
    print("SMS WEBHOOK SIMULATION")
    print("="*70 + "\n")
    
    async with async_session_maker() as db:
        # Find customer with phone
        result = await db.execute(
            select(Customer).where(Customer.phone.isnot(None)).limit(1)
        )
        customer = result.scalar_one_or_none()
        
        if not customer:
            print("❌ No customers with phone numbers found.")
            return
        
        print(f"📱 Simulating SMS from: {customer.phone}")
        print(f"   Customer: {customer.first_name} {customer.last_name}")
        print()
        
        # Import here to avoid circular dependency
        from app.api.sms_webhook import handle_incoming_sms
        
        # Simulate webhook call
        response = await handle_incoming_sms(
            From=customer.phone,
            Body="UPLOAD",
            MessageSid="TEST_SIM_" + str(customer.id)[:8],
            request=None,
            db=db
        )
        
        print("\n📤 Webhook Response:")
        print(f"   Status: {response['status']}")
        print(f"   Message: {response['message']}")
        if response['status'] == 'success':
            print(f"   URL: {response['upload_url']}")
        print()


if __name__ == "__main__":
    print("\n🧪 Document Upload Test Suite\n")
    print("Select test:")
    print("1. Test upload flow (generate token)")
    print("2. Simulate SMS webhook")
    print("3. Run both tests")
    
    choice = input("\nEnter choice (1-3): ").strip()
    
    if choice == "1":
        asyncio.run(test_upload_flow())
    elif choice == "2":
        asyncio.run(test_sms_webhook_simulation())
    elif choice == "3":
        asyncio.run(test_upload_flow())
        asyncio.run(test_sms_webhook_simulation())
    else:
        print("Invalid choice. Exiting.")
