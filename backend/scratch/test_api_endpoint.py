import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = r"c:\Anantha\Projects\Soul Squad\backend\service-account.json"
os.environ['TEST_MODE'] = 'True' # simulate mirror first

from google.cloud.sql.connector import Connector
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
import datetime

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

# Replicate route logic:
try:
    consultant_user_id = None
    user_id = None
    appt_status = ""
    date_from = ""
    date_to = ""
    page = 1
    per_page = 50
    is_test = False # Test both False and True

    for is_test in [False, True]:
        print(f"\n--- Testing with is_test={is_test} ---")
        now = datetime.datetime.utcnow()
        where_parts = ["a.is_test = :is_test"]
        params = {"is_test": is_test, "now": now}
        where_sql = " AND ".join(where_parts)
        
        base_sql = f"""
            FROM appointments a
            JOIN users u ON u.id = a.user_id
            JOIN consultant_profiles cp ON cp.id = a.consultant_id
            JOIN users cu ON cu.id = cp.user_id
            LEFT JOIN consultant_earnings ce ON ce.appointment_id = a.id
            LEFT JOIN payment_transactions pt ON pt.id = ce.payment_transaction_id
            LEFT JOIN call_sessions cs ON cs.appointment_id = a.id
            WHERE {where_sql}
        """

        count_result = db.execute(text(f"SELECT COUNT(*) {base_sql}"), params)
        total = count_result.scalar() or 0
        print(f"Total: {total}")

        select_sql = f"""
            SELECT
                a.id              AS appointment_id,
                a.appointment_date,
                a.status          AS appointment_status,
                a.duration_minutes,
                a.user_id,
                u.name            AS user_name,
                u.email           AS user_email,
                cp.user_id        AS consultant_user_id,
                cu.name           AS consultant_name,
                cu.email          AS consultant_email,
                cp.specialization AS consultant_specialization,
                ce.id             AS earning_id,
                COALESCE(ce.gross_amount, 0)          AS gross_amount,
                COALESCE(ce.consultant_payout, 0)     AS consultant_payout,
                COALESCE(ce.platform_fee, 0)          AS platform_fee,
                ce.payout_status,
                pt.invoice_number,
                cs.actual_start   AS call_started,
                cs.duration_seconds AS call_duration_sec
            {base_sql}
            ORDER BY a.appointment_date DESC
            LIMIT :limit OFFSET :offset
        """
        params["limit"]  = per_page
        params["offset"] = (page - 1) * per_page

        rows = db.execute(text(select_sql), params).fetchall()
        print(f"Fetched {len(rows)} rows.")
        
        # Test loop logic for potential errors
        result = []
        for r in rows:
            appt_date = r.appointment_date
            if hasattr(appt_date, 'replace'):
                is_past = appt_date < now
            else:
                is_past = True

            status = r.appointment_status
            if status == "completed":
                derived = "completed"
            elif status == "cancelled":
                derived = "cancelled"
            elif status == "scheduled" and not is_past:
                derived = "upcoming"
            elif status == "scheduled" and is_past:
                if r.call_started and r.call_duration_sec and r.call_duration_sec > 60:
                    derived = "completed"
                else:
                    derived = "no_show_both"
            else:
                derived = status

            gross = float(r.gross_amount or 0)
            payout = float(r.consultant_payout or 0)
            is_free = (gross == 0 and r.invoice_number is None and r.earning_id is None)

            result.append({
                "appointment_id":             r.appointment_id,
                "appointment_date":           r.appointment_date.isoformat() if r.appointment_date else None,
                "appointment_status":         r.appointment_status,
                "derived_status":             derived,
                "duration_minutes":           r.duration_minutes or 60,
                "user_id":                    r.user_id,
                "user_name":                  r.user_name or "Unknown",
                "user_email":                 r.user_email or "",
                "consultant_user_id":         r.consultant_user_id,
                "consultant_name":            r.consultant_name or "Unknown",
                "consultant_email":           r.consultant_email or "",
                "consultant_specialization":  r.consultant_specialization or "",
                "is_free":                    is_free,
                "gross_amount":               gross,
                "consultant_payout":          payout,
                "platform_fee":               float(r.platform_fee or 0),
                "payout_status":              r.payout_status,
                "invoice_number":             r.invoice_number,
                "call_started":               r.call_started.isoformat() if r.call_started else None,
                "call_duration_sec":          r.call_duration_sec,
            })
        print("Loop completed successfully for is_test =", is_test)

except Exception as e:
    import traceback
    traceback.print_exc()
finally:
    db.close()
    connector.close()
