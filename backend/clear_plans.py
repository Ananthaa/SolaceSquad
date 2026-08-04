"""
clear_plans.py — Wipes all subscription plan data from the database.

Effect: No plans exist → check_feature_limit() returns allowed=True for
        every feature → all users get unlimited access automatically.

Run on Mirror:
  gcloud builds submit --config ../cloudbuild-clear-plans.yaml \
    --project abiding-idea-485817-k2 --no-source
"""
import os
import sys

# ── DB connection (mirrors what main.py / database.py does) ──────────────────
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

INSTANCE_CONNECTION_NAME = os.environ.get("INSTANCE_CONNECTION_NAME")
DB_USER     = os.environ.get("DB_USER", "Admin")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "SoulSquad2024x")
DB_NAME     = os.environ.get("DB_NAME", "solacesquad_mirror")

if INSTANCE_CONNECTION_NAME:
    # Cloud SQL (Mirror / Prod)
    from google.cloud.sql.connector import Connector
    connector = Connector()

    def getconn():
        return connector.connect(
            INSTANCE_CONNECTION_NAME,
            "pg8000",
            user=DB_USER,
            password=DB_PASSWORD,
            db=DB_NAME,
        )

    engine = create_engine("postgresql+pg8000://", creator=getconn)
else:
    # Local SQLite fallback
    engine = create_engine("sqlite:///soul_squad.db")

Session = sessionmaker(bind=engine)
db = Session()

# ── Delete in FK-safe order ───────────────────────────────────────────────────
TABLES = [
    "feature_usage_top_ups",
    "feature_usage_logs",
    "user_subscriptions",
    "plan_feature_caps",
    "usage_plans",
]

print("Clearing all subscription plan data...")
for table in TABLES:
    try:
        result = db.execute(text(f"DELETE FROM {table}"))
        db.commit()
        print(f"  ✓ Cleared {table} ({result.rowcount} rows deleted)")
    except Exception as e:
        db.rollback()
        print(f"  ⚠ Could not clear {table}: {e}")

db.close()
print("\nDone. No plans exist → all users now have unlimited access.")
