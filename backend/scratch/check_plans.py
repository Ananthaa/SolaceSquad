import sys
import os
from datetime import datetime

# Set environment variables for import path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import Base, UsagePlan
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
        plans = session.query(UsagePlan).order_by(UsagePlan.id.asc()).all()
        print("\n=== USAGE PLANS ===")
        for p in plans:
            print(f"Plan ID: {p.id}")
            print(f"  Name: {p.name}")
            print(f"  Price: {p.price}")
            print(f"  Billing Cycle: {p.billing_cycle}")
            print(f"  Is Free: {p.is_free}")
            print(f"  Is Default: {p.is_default}")
            print(f"  Is Active: {p.is_active}")
            print("-" * 30)
            
    finally:
        connector.close()

if __name__ == "__main__":
    main()
