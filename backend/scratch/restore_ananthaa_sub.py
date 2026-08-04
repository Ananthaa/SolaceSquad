import sys
import os
from datetime import datetime, timedelta

# Set environment variables for import path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import Base, User, UserSubscription, UsagePlan
from google.cloud.sql.connector import Connector
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

def get_session():
    os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = r"c:\Anantha\Projects\Soul Squad\backend\service-account.json"
    
    INSTANCE_CONNECTION_NAME = "abiding-idea-485817-k2:us-central1:solacesquad-login-data1"
    DB_USER = "Admin"
    DB_PASSWORD = "SoulSquad2024x"
    DB_NAME = "solacesquad_prod"
    
    print(f"[DB] Connecting to remote Cloud SQL: {INSTANCE_CONNECTION_NAME}")
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

def restore_sub(session, sub_id, new_status=None):
    sub = session.query(UserSubscription).filter_by(id=sub_id).first()
    if not sub:
        print(f"[ERROR] Sub ID {sub_id} not found!")
        return
    
    old_expires = sub.expires_at
    old_status = sub.status
    
    # Calculate correct 1-year expiry from started_at
    correct_expiry = sub.started_at + timedelta(days=365)
    sub.expires_at = correct_expiry
    
    if new_status:
        sub.status = new_status
        
    if sub.auto_renew:
        sub.next_renewal_at = correct_expiry
        
    print(f"[RESTORE] Sub ID {sub_id} ({sub.plan.name}):")
    print(f"  Status: {old_status} -> {sub.status}")
    print(f"  Expires: {old_expires} -> {sub.expires_at}")
    print(f"  Next Renewal: {sub.next_renewal_at}")
    
def cancel_temp_free_subs(session, user_id, start_time):
    # Find any active free plans created for this user since the expiration time
    free_subs = session.query(UserSubscription).filter(
        UserSubscription.user_id == user_id,
        UserSubscription.plan_id == 6, # Free plan
        UserSubscription.status == "active",
        UserSubscription.created_at >= start_time
    ).all()
    
    for fs in free_subs:
        fs.status = "cancelled"
        print(f"[CANCEL] Temp Free Sub ID {fs.id} marked as cancelled.")

def main():
    session, connector = get_session()
    
    try:
        # 1. Restore ananthaa@gmail.com (Sub ID 70)
        # Started: 2026-06-09 11:17:36
        print("\n--- Restoring ananthaa@gmail.com ---")
        restore_sub(session, 70, new_status="active")
        # Cancel the auto-created Free plan from today
        cancel_temp_free_subs(session, 1, datetime(2026, 7, 9, 0, 0, 0))
        
        # 2. Restore silvertossindia@gmail.com (Sub ID 60)
        # Started: 2026-06-08 13:54:48
        print("\n--- Restoring silvertossindia@gmail.com ---")
        restore_sub(session, 60, new_status="active")
        
        # 3. Restore info@passionpropel.com (Sub ID 4)
        # Started: 2026-04-21 15:15:30
        print("\n--- Restoring info@passionpropel.com ---")
        restore_sub(session, 4, new_status="active")
        
        # 4. Restore test user solacesquad2027@gmail.com (Sub ID 119 and 135)
        print("\n--- Restoring test user solacesquad2027@gmail.com ---")
        restore_sub(session, 119) # Keep cancelled status, just fix expiry
        restore_sub(session, 135, new_status="active")
        
        session.commit()
        print("\n[SUCCESS] Database updates committed successfully!")
        
    except Exception as e:
        session.rollback()
        print(f"\n[ERROR] Transaction rolled back: {e}")
        
    finally:
        connector.close()

if __name__ == "__main__":
    main()
