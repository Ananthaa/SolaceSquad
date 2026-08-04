import sys
import os
from datetime import datetime

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
    session, connector = get_session()
    try:
        subs = session.query(UserSubscription).filter(UserSubscription.payment_status == 'paid').order_by(UserSubscription.created_at.desc()).all()
        print("\n=== PAID SUBSCRIPTIONS ===")
        for s in subs:
            user = session.query(User).filter_by(id=s.user_id).first()
            user_email = user.email if user else f"User ID {s.user_id}"
            plan = session.query(UsagePlan).filter_by(id=s.plan_id).first()
            plan_name = plan.name if plan else f"Plan ID {s.plan_id}"
            cycle = plan.billing_cycle if plan else ""
            print(f"Sub ID: {s.id} | User: {user_email} | Plan: {plan_name} ({cycle}) | Status: {s.status}")
            print(f"  Started: {s.started_at} | Expires: {s.expires_at}")
            print(f"  Created: {s.created_at}")
            print("-" * 50)
    finally:
        connector.close()

if __name__ == "__main__":
    main()
