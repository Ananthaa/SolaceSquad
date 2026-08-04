"""Deep debug: test the exact query used by the new endpoint."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = r"c:\Anantha\Projects\Soul Squad\backend\service-account.json"

from google.cloud.sql.connector import Connector
from sqlalchemy import create_engine, text, func
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
session = Session()

try:
    # 1. Check what columns Appointment table has
    result = session.execute(text("""
        SELECT column_name, data_type 
        FROM information_schema.columns 
        WHERE table_name='appointments'
        ORDER BY ordinal_position
    """))
    print("Appointments columns:")
    for row in result:
        print(f"  {row[0]}: {row[1]}")

    # 2. Full query mimicking the endpoint - check if consultant_earnings links by appointment_id
    result = session.execute(text("""
        SELECT ce.id, ce.appointment_id, ce.consultant_user_id, ce.gross_amount, ce.consultant_payout
        FROM consultant_earnings ce
        LIMIT 5
    """))
    print("\nSample consultant_earnings rows:")
    for row in result:
        print(f"  id={row[0]}, appt_id={row[1]}, cons_uid={row[2]}, gross={row[3]}, payout={row[4]}")

    # 3. Check consultant_earnings.payment_transaction_id column
    result = session.execute(text("""
        SELECT column_name FROM information_schema.columns 
        WHERE table_name='consultant_earnings'
        ORDER BY ordinal_position
    """))
    print("\nconsultant_earnings columns:")
    for row in result:
        print(f"  {row[0]}")

    # 4. The full query (mimicking the API endpoint) with LEFT JOIN
    result = session.execute(text("""
        SELECT 
            a.id, a.appointment_date, a.status, a.user_id, a.consultant_id,
            u.name as user_name, u.email as user_email,
            cp.id as cp_id, cp.user_id as consultant_user_id,
            ce.id as earning_id, ce.gross_amount,
            pt.id as txn_id, pt.invoice_number
        FROM appointments a
        JOIN users u ON u.id = a.user_id
        JOIN consultant_profiles cp ON cp.id = a.consultant_id
        LEFT JOIN consultant_earnings ce ON ce.appointment_id = a.id
        LEFT JOIN payment_transactions pt ON pt.id = ce.payment_transaction_id
        WHERE a.is_test = False
        ORDER BY a.appointment_date DESC
        LIMIT 10
    """))
    rows = result.fetchall()
    print(f"\nFull endpoint query with is_test=False: {len(rows)} rows")
    for r in rows:
        print(f"  Appt #{r[0]}: date={r[1]}, status={r[2]}, user={r[4]}, earning_id={r[9]}, gross={r[10]}, invoice={r[12]}")
    
    # 5. Check if there's a duration_minutes column
    result = session.execute(text("""
        SELECT column_name FROM information_schema.columns 
        WHERE table_name='appointments' AND column_name='duration_minutes'
    """))
    print(f"\nduration_minutes exists: {result.fetchone() is not None}")

finally:
    session.close()
    connector.close()
