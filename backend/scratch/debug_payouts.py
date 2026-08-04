"""Debug script to find ConsultantEarning records for cancelled appointments."""
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
    # 1. Let's find all ConsultantEarning records where the linked appointment is cancelled,
    # but payout_status is still 'pending'.
    query = text("""
        SELECT ce.id, ce.appointment_id, a.status as appt_status, ce.consultant_payout, ce.payout_status, ce.is_test
        FROM consultant_earnings ce
        JOIN appointments a ON a.id = ce.appointment_id
        WHERE a.status = 'cancelled'
    """)
    rows = db.execute(query).fetchall()
    print(f"Found {len(rows)} consultant_earnings for cancelled appointments:")
    for r in rows:
        print(f"  Earning ID={r.id}, Appt ID={r.appointment_id}, Appt Status={r.appt_status}, Payout={r.consultant_payout}, Payout Status={r.payout_status}, Is Test={r.is_test}")

    # 2. Let's calculate what the sum of pending payouts is right now in production environment (is_test=False)
    query_sum = text("""
        SELECT SUM(consultant_payout)
        FROM consultant_earnings
        WHERE payout_status = 'pending' AND is_test = False
    """)
    print(f"\nSum of pending payouts (is_test=False): {db.execute(query_sum).scalar()}")

    # 3. What about is_test=True?
    query_sum_test = text("""
        SELECT SUM(consultant_payout)
        FROM consultant_earnings
        WHERE payout_status = 'pending' AND is_test = True
    """)
    print(f"Sum of pending payouts (is_test=True): {db.execute(query_sum_test).scalar()}")

finally:
    db.close()
    connector.close()
