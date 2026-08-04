"""
fix_incomplete_profile_flags.py
--------------------------------
Ensure the newly created consultant profiles for Sanjay Tewari,
Subha shri Rajamahendran, and Sushil Chander have
is_profile_completed = FALSE so they appear in the admin
Incomplete Profiles list.
"""
import sys
from google.cloud.sql.connector import Connector
import sqlalchemy
from sqlalchemy import text

TARGET_EMAILS = [
    "sanjay.ortho@gmail.com",
    "subhashrirajamahendran@gmail.com",
    "sushilqm@gmail.com",
]

connector = Connector()
def getconn():
    return connector.connect(
        "abiding-idea-485817-k2:us-central1:solacesquad-login-data1",
        "pg8000", user="Admin", password="SoulSquad2024x", db="solacesquad_prod",
    )
engine = sqlalchemy.create_engine("postgresql+pg8000://", creator=getconn)

print("\n=== Fix Incomplete Profile Flags ===\n")

with engine.begin() as conn:
    for email in TARGET_EMAILS:
        user = conn.execute(text(
            "SELECT id, name, user_type FROM users WHERE email = :e"
        ), {"e": email}).fetchone()

        if not user:
            print(f"  [NOT FOUND]  {email}")
            continue

        uid, name, utype = user
        print(f"  User: ID={uid}  name={name!r}  type={utype!r}")

        # Ensure user_type = consultant
        if utype != "consultant":
            conn.execute(text(
                "UPDATE users SET user_type='consultant' WHERE id=:uid"
            ), {"uid": uid})
            print(f"    Fixed user_type → consultant")

        # Check profile
        prof = conn.execute(text(
            "SELECT id, is_profile_completed, is_approved FROM consultant_profiles WHERE user_id=:uid"
        ), {"uid": uid}).fetchone()

        if prof:
            pid, completed, approved = prof
            print(f"    Profile ID={pid}  is_profile_completed={completed}  is_approved={approved}")
            # Force is_profile_completed = FALSE, is_approved = FALSE
            conn.execute(text("""
                UPDATE consultant_profiles
                SET is_profile_completed = FALSE,
                    is_approved = FALSE
                WHERE id = :pid
            """), {"pid": pid})
            print(f"    Updated → is_profile_completed=FALSE, is_approved=FALSE")
        else:
            # Insert fresh profile with explicit FALSE
            conn.execute(text("""
                INSERT INTO consultant_profiles
                    (user_id, specialization, bio, experience_years,
                     hourly_rate, is_approved, is_profile_completed,
                     consultation_fee, consultant_payout)
                VALUES
                    (:uid, '', '', 0, 0, FALSE, FALSE, 0, 0)
            """), {"uid": uid})
            print(f"    Created new profile with is_profile_completed=FALSE")

        print(f"  → {name} will now appear in Admin Incomplete Profiles.\n")

print("=== Done ===")
connector.close()
sys.exit(0)
