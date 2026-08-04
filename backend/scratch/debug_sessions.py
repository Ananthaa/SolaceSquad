"""Debug the appointment-sessions endpoint to see why no records are returned."""
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
session = Session()

try:
    # 1. How many appointments total?
    result = session.execute(text("SELECT COUNT(*) FROM appointments"))
    print(f"Total appointments: {result.scalar()}")

    # 2. What is_test values exist?
    result = session.execute(text("SELECT is_test, COUNT(*) FROM appointments GROUP BY is_test"))
    print("Appointments by is_test:")
    for row in result:
        print(f"  is_test={row[0]}: {row[1]} rows")

    # 3. Check if is_test column exists at all
    result = session.execute(text("""
        SELECT column_name, data_type 
        FROM information_schema.columns 
        WHERE table_name='appointments' AND column_name='is_test'
    """))
    col = result.fetchone()
    print(f"\nis_test column exists: {col is not None}")
    if col:
        print(f"  type: {col[1]}")

    # 4. Try the actual join query (simplified)
    result = session.execute(text("""
        SELECT a.id, a.status, a.appointment_date, a.is_test,
               u.name as user_name,
               cp.id as cp_id, cp.user_id as consultant_user_id
        FROM appointments a
        JOIN users u ON u.id = a.user_id
        JOIN consultant_profiles cp ON cp.id = a.consultant_id
        LIMIT 10
    """))
    rows = result.fetchall()
    print(f"\nJoin query returned {len(rows)} rows")
    for r in rows:
        print(f"  Appt #{r[0]}: status={r[1]}, date={r[2]}, is_test={r[3]}, user={r[4]}, cp_id={r[5]}, consultant_uid={r[6]}")

    # 5. Check production filter (is_test = False)
    result = session.execute(text("""
        SELECT COUNT(*) FROM appointments a
        JOIN consultant_profiles cp ON cp.id = a.consultant_id
        WHERE a.is_test = False
    """))
    print(f"\nAppointments with is_test=False (production): {result.scalar()}")

    # 6. Check NULL is_test
    result = session.execute(text("""
        SELECT COUNT(*) FROM appointments WHERE is_test IS NULL
    """))
    print(f"Appointments with is_test=NULL: {result.scalar()}")

    # 7. Check with no is_test filter
    result = session.execute(text("""
        SELECT COUNT(*) FROM appointments a
        JOIN users u ON u.id = a.user_id
        JOIN consultant_profiles cp ON cp.id = a.consultant_id
    """))
    print(f"Appointments with all joins (no is_test filter): {result.scalar()}")

    # 8. Check with LEFT JOIN on earnings
    result = session.execute(text("""
        SELECT COUNT(*) FROM appointments a
        JOIN users u ON u.id = a.user_id
        JOIN consultant_profiles cp ON cp.id = a.consultant_id
        LEFT JOIN consultant_earnings ce ON ce.appointment_id = a.id
        WHERE a.is_test = False OR a.is_test IS NULL
    """))
    print(f"With is_test=False OR NULL + left join earnings: {result.scalar()}")

finally:
    session.close()
    connector.close()
