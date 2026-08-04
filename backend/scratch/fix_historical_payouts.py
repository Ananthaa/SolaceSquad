"""Fix historical payout status for cancelled appointments."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = r"c:\Anantha\Projects\Soul Squad\backend\service-account.json"

from google.cloud.sql.connector import Connector
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

INSTANCE_CONNECTION_NAME = "abiding-idea-485817-k2:us-central1:solacesquad-login-data1"
DB_USER = "Admin"
DB_PASSWORD = "SoulSquad2024x"
DB_NAME = "solacesquad_prod"

connector = Connector()
def getconn():
    return connector.connect(INSTANCE_CONNECTION_NAME, "pg8000", user=DB_USER, password=DB_PASSWORD, db=DB_NAME)

engine = create_engine("postgresql+pg8000://", creator=getconn)
Session = sessionmaker(bind=engine)
db = Session()

try:
    # 1. Update live/production environment first (is_test=False)
    query_update_live = text("""
        UPDATE consultant_earnings ce
        SET payout_status = 'on_hold',
            admin_notes = 'Payout frozen automatically: linked appointment is cancelled.'
        FROM appointments a
        WHERE a.id = ce.appointment_id
          AND a.status = 'cancelled'
          AND ce.payout_status = 'pending'
          AND ce.is_test = False
    """)
    res_live = db.execute(query_update_live)
    print(f"Updated {res_live.rowcount} live payout records to on_hold.")

    # 2. Also update mirror/test environment (is_test=True)
    query_update_test = text("""
        UPDATE consultant_earnings ce
        SET payout_status = 'on_hold',
            admin_notes = 'Payout frozen automatically: linked appointment is cancelled.'
        FROM appointments a
        WHERE a.id = ce.appointment_id
          AND a.status = 'cancelled'
          AND ce.payout_status = 'pending'
          AND ce.is_test = True
    """)
    res_test = db.execute(query_update_test)
    print(f"Updated {res_test.rowcount} test payout records to on_hold.")

    db.commit()
    print("Changes committed successfully!")

finally:
    db.close()
    connector.close()
