import sys
import os
from datetime import datetime

# Set environment variables for import path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import Base, User, UserSubscription, UsagePlan
from google.cloud.sql.connector import Connector
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

def get_session():
    # Ensure credentials env var is set
    os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = r"c:\Anantha\Projects\Soul Squad\backend\service-account.json"
    
    INSTANCE_CONNECTION_NAME = "abiding-idea-485817-k2:us-central1:solacesquad-login-data1"
    DB_USER = "Admin"
    DB_PASSWORD = "SoulSquad2024x"
    DB_NAME = "solacesquad_prod"
    
    print(f"[DB] Connecting to remote Cloud SQL: {INSTANCE_CONNECTION_NAME} as user={DB_USER}")
    connector = Connector()
    
    def getconn():
        return connector.connect(
            INSTANCE_CONNECTION_NAME,
            "pg8000",
            user=DB_USER,
            password=DB_PASSWORD,
            db=DB_NAME
        )
        
    engine = create_engine("postgresql+pg8000://", creator=getconn)
    Session = sessionmaker(bind=engine)
    return Session(), connector

def main():
    email = "ananthaa@gmail.com"
    session, connector = get_session()
    
    try:
        user = session.query(User).filter_by(email=email).first()
        if not user:
            print(f"[ERROR] User {email} not found!")
            return
            
        print("\n=== USER RECORD ===")
        print(f"ID: {user.id}")
        print(f"Name: {user.name}")
        print(f"Email: {user.email}")
        print(f"User Type: {user.user_type}")
        print(f"Created At: {user.created_at}")
        
        subs = session.query(UserSubscription).filter_by(user_id=user.id).order_by(UserSubscription.created_at.desc()).all()
        print(f"\n=== SUBSCRIPTIONS ({len(subs)}) ===")
        for s in subs:
            plan = session.query(UsagePlan).filter_by(id=s.plan_id).first()
            plan_name = plan.name if plan else f"ID {s.plan_id}"
            print(f"Sub ID: {s.id}")
            print(f"  Plan: {plan_name} (Plan ID: {s.plan_id})")
            print(f"  Status: {s.status}")
            print(f"  Payment Status: {s.payment_status}")
            print(f"  Started At: {s.started_at}")
            print(f"  Expires At: {s.expires_at}")
            print(f"  Auto Renew: {s.auto_renew}")
            print(f"  Next Renewal At: {s.next_renewal_at}")
            print(f"  Voucher Code: {s.voucher_code}")
            print(f"  Razorpay Order ID: {s.razorpay_order_id}")
            print(f"  Razorpay Payment ID: {s.razorpay_payment_id}")
            print(f"  Created At: {s.created_at}")
            print("-" * 30)
            
    finally:
        connector.close()

if __name__ == "__main__":
    main()
