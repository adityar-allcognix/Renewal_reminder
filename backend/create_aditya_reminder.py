import requests
import json
from datetime import date, datetime, timedelta

BASE_URL = "http://localhost:8080/api"

def create_customer():
    customer_data = {
        "first_name": "Aditya",
        "last_name": "Raut",
        "email": "souladityaftw@gmail.com",
        "phone": "9209793522",
        "address_line1": "123 Tech Street",
        "city": "San Francisco",
        "state": "CA",
        "postal_code": "94105",
        "country": "USA",
        "preferred_channel": "whatsapp"
    }
    
    print("Creating customer...")
    # Try to create
    response = requests.post(f"{BASE_URL}/customers/", json=customer_data)
    if response.status_code == 200 or response.status_code == 201:
        print("Customer created.")
        return response.json()
    elif response.status_code == 400 and "already exists" in response.text:
        print("Customer already exists, fetching...")
        # Fetch all and filter (not efficient but works for this test)
        response = requests.get(f"{BASE_URL}/customers/?size=100")
        if response.status_code == 200:
            customers = response.json().get("items", [])
            for c in customers:
                if c["email"] == "souladityaftw@gmail.com":
                    return c
    else:
        print(f"Failed to create customer: {response.text}")
        return None

def create_policy(customer_id):
    policy_number = f"POL-ADITYA-{datetime.now().strftime('%H%M%S')}"
    policy_data = {
        "policy_number": policy_number,
        "policy_type": "Term Life",
        "coverage_type": "Standard",
        "coverage_amount": 500000,
        "premium_amount": 1200,
        "payment_frequency": "yearly",
        "start_date": str(date.today() - timedelta(days=360)),
        "end_date": str(date.today() + timedelta(days=5)),
        "renewal_date": str(date.today() + timedelta(days=5)),
        "customer_id": customer_id
    }
    
    print(f"Creating policy {policy_number}...")
    response = requests.post(f"{BASE_URL}/policies/", json=policy_data)
    if response.status_code == 200 or response.status_code == 201:
        print("Policy created.")
        return response.json()
    else:
        print(f"Failed to create policy: {response.text}")
        return None

def create_reminder(policy_id):
    reminder_data = {
        "policy_id": policy_id,
        "reminder_type": 5, # 5 days before
        "channel": "whatsapp",
        "scheduled_date": str(datetime.now() + timedelta(minutes=10)), # Scheduled for soon
        "message_content": "Dear Aditya, your policy is up for renewal."
    }
    
    print("Creating reminder...")
    response = requests.post(f"{BASE_URL}/reminders/", json=reminder_data)
    if response.status_code == 200 or response.status_code == 201:
        print("Reminder created.")
        return response.json()
    else:
        print(f"Failed to create reminder: {response.text}")
        return None

def main():
    customer = create_customer()
    if not customer:
        # If creation failed, maybe fetch the first customer with that email?
        # For this task, let's assume we can create it.
        # Or list customers and find him.
        response = requests.get(f"{BASE_URL}/customers/")
        if response.status_code == 200:
            customers = response.json().get("items", [])
            for c in customers:
                if c["email"] == "souladityaftw@gmail.com":
                    customer = c
                    print("Found existing customer.")
                    break
    
    if not customer:
        print("Could not get customer.")
        return

    policy = create_policy(customer["id"])
    if not policy:
        print("Could not create policy.")
        return

    reminder = create_reminder(policy["id"])
    if reminder:
        print(f"Successfully created reminder for Aditya Raut.")
        print(f"Policy Number: {policy['policy_number']}")
        print(f"Reminder ID: {reminder['id']}")

if __name__ == "__main__":
    main()
