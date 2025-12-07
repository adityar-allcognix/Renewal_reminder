
import asyncio
import os
import sys
from datetime import datetime, timedelta
import uuid
import httpx

# Add current directory to path to import app modules
sys.path.append(os.getcwd())

from app.database import AsyncSessionLocal
from app.models import Customer, Policy, PolicyStatus, CustomerToken, CustomerTokenType
from app.api.customer_public import generate_secure_token

async def setup_test_data():
    """Create a test customer, policy, and token."""
    async with AsyncSessionLocal() as db:
        # 1. Create Customer
        customer_id = uuid.uuid4()
        customer = Customer(
            id=customer_id,
            first_name="Test",
            last_name="User",
            email=f"test_{customer_id}@example.com",
            phone="+1234567890",
            preferred_channel="email"
        )
        db.add(customer)
        
        # 2. Create Policy
        policy_id = uuid.uuid4()
        policy = Policy(
            id=policy_id,
            customer_id=customer_id,
            policy_number=f"POL-{str(customer_id)[:8]}",
            policy_type="Auto",
            start_date=datetime.now().date(),
            end_date=datetime.now().date() + timedelta(days=30),
            renewal_date=datetime.now().date() + timedelta(days=30),
            premium_amount=1000.00,
            status=PolicyStatus.ACTIVE
        )
        db.add(policy)
        await db.flush()  # Ensure policy is created before token
        
        # 3. Create Token
        token_str = generate_secure_token()
        token = CustomerToken(
            token=token_str,
            token_type=CustomerTokenType.POLICY_VIEW, # Using POLICY_VIEW for now as generic access
            customer_id=customer_id,
            policy_id=policy_id,
            expires_at=datetime.utcnow() + timedelta(hours=24),
            is_used=False
        )
        db.add(token)
        
        await db.commit()
        print(f"✅ Created Test Data:")
        print(f"   Customer ID: {customer_id}")
        print(f"   Policy ID:   {policy_id}")
        print(f"   Token:       {token_str}")
        
        return token_str

async def test_endpoints(token):
    """Test the public endpoints with the generated token."""
    base_url = "http://localhost:8080/api/public"
    
    async with httpx.AsyncClient() as client:
        # 1. Test Verify Token
        print(f"\nTesting GET {base_url}/verify/{token}...")
        response = await client.get(f"{base_url}/verify/{token}")
        
        if response.status_code == 200:
            print("✅ Verify Endpoint: SUCCESS")
            print(f"   Response: {response.json()}")
        else:
            print(f"❌ Verify Endpoint: FAILED ({response.status_code})")
            print(f"   Response: {response.text}")
            return

        # 2. Test Document Upload
        print(f"\nTesting POST {base_url}/upload-document/{token}...")
        
        # Create a dummy PDF file
        files = {'file': ('test_doc.pdf', b'%PDF-1.4 test content', 'application/pdf')}
        
        response = await client.post(f"{base_url}/upload-document/{token}", files=files)
        
        if response.status_code == 200:
            print("✅ Upload Endpoint: SUCCESS")
            print(f"   Response: {response.json()}")
        else:
            print(f"❌ Upload Endpoint: FAILED ({response.status_code})")
            print(f"   Response: {response.text}")

async def main():
    try:
        token = await setup_test_data()
        await test_endpoints(token)
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
