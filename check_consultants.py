import os
import sys

# Set environment variables
os.environ['ENVIRONMENT'] = 'production'
os.environ['DB_USER'] = 'Admin'
os.environ['DB_PASSWORD'] = 'AdminPass2024!'
os.environ['DB_NAME'] = 'solacesquad_prod'
os.environ['INSTANCE_CONNECTION_NAME'] = 'abiding-idea-485817-k2:us-central1:solacesquad-login-data1'

# Change to backend directory
os.chdir('backend')
sys.path.insert(0, os.getcwd())

# Import database and models
from database import SessionLocal
from models import User
from sqlalchemy import text

# Create session
db = SessionLocal()

print("=" * 60)
print("CHECKING USERS IN DATABASE")
print("=" * 60)
print()

# Get all users
users = db.query(User).all()

print(f"Total users: {len(users)}")
print()

# Show all users
for user in users:
    print(f"ID: {user.id}")
    print(f"Name: {user.name}")
    print(f"Email: {user.email}")
    print(f"Phone: {user.phone_number}")
    print(f"Type: {user.user_type}")
    if user.user_type == 'consultant':
        print(f"Is Active: {user.is_active}")
    print("-" * 60)

print()
print("=" * 60)
print("CONSULTANT ACCOUNTS")
print("=" * 60)
print()

consultants = db.query(User).filter(User.user_type == 'consultant').all()
print(f"Total consultants: {len(consultants)}")
print()

if consultants:
    for consultant in consultants:
        print(f"ID: {consultant.id}")
        print(f"Name: {consultant.name}")
        print(f"Email: {consultant.email}")
        print(f"Is Active: {consultant.is_active}")
        print("-" * 60)
else:
    print("No consultants found!")

print()
print("=" * 60)
print("ACTIONS")
print("=" * 60)
print()

# Ask if user wants to activate a consultant
if consultants:
    inactive_consultants = [c for c in consultants if not c.is_active]
    if inactive_consultants:
        print("Found inactive consultants:")
        for c in inactive_consultants:
            print(f"  - {c.email} (ID: {c.id})")
        print()
        print("Do you want to activate them? (This script will activate all)")
        response = input("Type 'yes' to activate: ")
        if response.lower() == 'yes':
            for c in inactive_consultants:
                c.is_active = True
                print(f"Activated: {c.email}")
            db.commit()
            print()
            print("All consultants activated!")
    else:
        print("All consultants are already active!")
        print()
        print("You can log in with:")
        for c in consultants:
            print(f"  Email: {c.email}")

db.close()
