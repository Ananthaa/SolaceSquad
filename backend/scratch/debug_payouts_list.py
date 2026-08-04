"""Check all pending payout records for is_test=False."""
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
    query = text("""
        SELECT ce.id, ce.appointment_id, ce.consultant_user_id, ce.gross_amount, ce.consultant_payout, ce.payout_status, a.status as appt_status
        FROM consultant_earnings ce
        LEFT JOIN appointments a ON a.id = ce.appointment_id
        WHERE ce.payout_status = 'pending' AND ce.is_test = False
    """)
    rows = db.execute(query).fetchall()
    print("Pending payouts (is_test=False):")
    for r in rows:
        print(f"  Earning ID={r.id}, Appt ID={r.appointment_id}, Appt Status={r.appt_status}, Payout={r.consultant_payout}")

finally:
    db.close()
    connector.close()
