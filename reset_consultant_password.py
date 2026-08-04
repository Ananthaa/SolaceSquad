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

# Create session
db = SessionLocal()

print("=" * 60)
print("RESETTING CONSULTANT PASSWORD")
print("=" * 60)
print()

# Get consultant
consultant = db.query(User).filter(User.email == 'test@test.com').first()

if consultant:
    print(f"Found consultant: {consultant.name} ({consultant.email})")
    print()
    
    # Set new password
    new_password = "consultant123"
    consultant.set_password(new_password)
    db.commit()
    
    print(f"Password reset successfully!")
    print()
    print("=" * 60)
    print("LOGIN CREDENTIALS")
    print("=" * 60)
    print(f"Email: {consultant.email}")
    print(f"Password: {new_password}")
    print("=" * 60)
else:
    print("Consultant not found!")

db.close()
