from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from models import Base
import os

# Database configuration
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_NAME = os.getenv("DB_NAME", "solacesquad_prod")
INSTANCE_CONNECTION_NAME = os.getenv("INSTANCE_CONNECTION_NAME")
DB_HOST = os.getenv("DB_HOST")  # Set to Cloud SQL public IP for local dev

if DB_HOST:
    # LOCAL DEV — connect directly via TCP to Cloud SQL public IP
    import psycopg2
    print(f"[DB] Connecting via TCP to host={DB_HOST}, db={DB_NAME}, user={DB_USER}")

    def getconn():
        return psycopg2.connect(
            user=DB_USER,
            password=DB_PASSWORD,
            dbname=DB_NAME,
            host=DB_HOST,
            sslmode="require",
        )

    engine = create_engine(
        "postgresql+psycopg2://",
        creator=getconn,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10,
        pool_recycle=1800,
        pool_reset_on_return="rollback",  # Always ROLLBACK on return - prevents stale txn state
    )
    print("[DB] Engine created via TCP (local dev)")

elif INSTANCE_CONNECTION_NAME and DB_USER and DB_PASSWORD and DB_NAME:
    if os.name == "nt":
        # Windows local dev — connect via Cloud SQL Connector (TCP tunnel) using pg8000
        from google.cloud.sql.connector import Connector
        print(f"[DB] Connecting via Cloud SQL Connector (pg8000) for {INSTANCE_CONNECTION_NAME}")
        
        connector = Connector()
        
        def getconn():
            return connector.connect(
                INSTANCE_CONNECTION_NAME,
                "pg8000",
                user=DB_USER,
                password=DB_PASSWORD,
                db=DB_NAME
            )
            
        engine = create_engine(
            "postgresql+pg8000://",
            creator=getconn,
            pool_pre_ping=True,
            pool_size=5,
            max_overflow=10,
            pool_recycle=1800,
            pool_reset_on_return="rollback",
        )
        print("[DB] Engine created via Cloud SQL Connector (pg8000)")
    else:
        # CLOUD RUN — connect via Unix socket mounted by Cloud SQL proxy sidecar
        import psycopg2
        socket_dir = f"/cloudsql/{INSTANCE_CONNECTION_NAME}"
        print(f"[DB] Connecting via Unix socket: {socket_dir}, db={DB_NAME}, user={DB_USER}")

        def getconn():
            return psycopg2.connect(
                user=DB_USER,
                password=DB_PASSWORD,
                dbname=DB_NAME,
                host=socket_dir,
            )

        engine = create_engine(
            "postgresql+psycopg2://",
            creator=getconn,
            pool_pre_ping=True,
            pool_size=5,
            max_overflow=10,
            pool_recycle=1800,
            pool_reset_on_return="rollback",  # Always ROLLBACK on return - prevents stale txn state
        )
        print("[DB] Engine created via Unix socket (Cloud Run)")

else:
    # No valid PostgreSQL credentials — crash immediately.
    # SQLite is NOT allowed: data would be lost on every container restart.
    raise RuntimeError(
        "[DB] FATAL: No PostgreSQL connection details found.\n"
        "  Set DB_HOST (local dev) OR INSTANCE_CONNECTION_NAME + DB_USER + DB_PASSWORD + DB_NAME (Cloud Run).\n"
        "  SQLite is not permitted — all data must live in Cloud SQL PostgreSQL."
    )


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db():
    Base.metadata.create_all(bind=engine)
    
    # Run dynamic DPDPA consent migrations
    from sqlalchemy import text
    try:
        with engine.begin() as conn:
            # Check existing columns
            result = conn.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name = 'users'"))
            columns = [row[0] for row in result.fetchall()]
            
            if "timezone" not in columns:
                conn.execute(text("ALTER TABLE users ADD COLUMN timezone VARCHAR(100) DEFAULT 'UTC'"))
                print("[Migration] Added column timezone to users table")

            if "consent_account" not in columns:
                conn.execute(text("ALTER TABLE users ADD COLUMN consent_account BOOLEAN DEFAULT TRUE"))
                conn.execute(text("UPDATE users SET consent_account = TRUE"))
                print("[Migration] Added column consent_account to users table")
                
            if "consent_health" not in columns:
                conn.execute(text("ALTER TABLE users ADD COLUMN consent_health BOOLEAN DEFAULT FALSE"))
                conn.execute(text("UPDATE users SET consent_health = FALSE"))
                print("[Migration] Added column consent_health to users table")
                
            if "consent_recording" not in columns:
                conn.execute(text("ALTER TABLE users ADD COLUMN consent_recording BOOLEAN DEFAULT FALSE"))
                conn.execute(text("UPDATE users SET consent_recording = FALSE"))
                print("[Migration] Added column consent_recording to users table")
                
            if "consent_note_sharing" not in columns:
                conn.execute(text("ALTER TABLE users ADD COLUMN consent_note_sharing BOOLEAN DEFAULT FALSE"))
                conn.execute(text("UPDATE users SET consent_note_sharing = FALSE"))
                print("[Migration] Added column consent_note_sharing to users table")
                
            if "consent_prompted" not in columns:
                conn.execute(text("ALTER TABLE users ADD COLUMN consent_prompted BOOLEAN DEFAULT FALSE"))
                conn.execute(text("UPDATE users SET consent_prompted = FALSE"))
                print("[Migration] Added column consent_prompted to users table")

            # Make email column nullable in database (either email or phone signup)
            try:
                conn.execute(text("ALTER TABLE users ALTER COLUMN email DROP NOT NULL"))
                print("[Migration] Altered email column to be nullable (DROP NOT NULL)")
            except Exception as _em_err:
                print(f"[Migration] Note: Altering email column (non-fatal): {_em_err}")

            # Clean up accidental consultant profiles for non-consultant accounts (admins/users)
            try:
                result_del = conn.execute(text("DELETE FROM consultant_profiles WHERE user_id IN (SELECT id FROM users WHERE user_type != 'consultant')"))
                if result_del.rowcount > 0:
                    print(f"[Migration] Cleaned up {result_del.rowcount} accidental consultant profiles from admin/user accounts")
            except Exception as _del_err:
                print(f"[Migration] Note: Clean up non-consultant profiles failed (non-fatal): {_del_err}")

            # Add columns to event_workshops table
            try:
                result_ew = conn.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name = 'event_workshops'"))
                columns_ew = [row[0] for row in result_ew.fetchall()]
                
                if "consultant_id" not in columns_ew:
                    conn.execute(text("ALTER TABLE event_workshops ADD COLUMN consultant_id INTEGER REFERENCES consultant_profiles(id) ON DELETE SET NULL"))
                    print("[Migration] Added column consultant_id to event_workshops table")
                    
                if "payout_amount" not in columns_ew:
                    conn.execute(text("ALTER TABLE event_workshops ADD COLUMN payout_amount FLOAT DEFAULT 0.0"))
                    print("[Migration] Added column payout_amount to event_workshops table")
            except Exception as _ew_err:
                print(f"[Migration] Note: Adding event_workshops columns failed (non-fatal): {_ew_err}")

            # Add event_workshop_id, taxes, discount_amount, discount_pct columns to consultant_earnings table
            try:
                result_ce = conn.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name = 'consultant_earnings'"))
                columns_ce = [row[0] for row in result_ce.fetchall()]
                
                if "event_workshop_id" not in columns_ce:
                    conn.execute(text("ALTER TABLE consultant_earnings ADD COLUMN event_workshop_id INTEGER REFERENCES event_workshops(id) ON DELETE SET NULL"))
                    print("[Migration] Added column event_workshop_id to consultant_earnings table")
                
                if "taxes" not in columns_ce:
                    conn.execute(text("ALTER TABLE consultant_earnings ADD COLUMN taxes FLOAT DEFAULT 0.0"))
                    print("[Migration] Added column taxes to consultant_earnings table")
                    
                if "discount_amount" not in columns_ce:
                    conn.execute(text("ALTER TABLE consultant_earnings ADD COLUMN discount_amount FLOAT DEFAULT 0.0"))
                    print("[Migration] Added column discount_amount to consultant_earnings table")
                    
                if "discount_pct" not in columns_ce:
                    conn.execute(text("ALTER TABLE consultant_earnings ADD COLUMN discount_pct FLOAT DEFAULT 0.0"))
                    print("[Migration] Added column discount_pct to consultant_earnings table")
            except Exception as _ce_err:
                print(f"[Migration] Note: Adding consultant_earnings columns failed (non-fatal): {_ce_err}")
    except Exception as e:
        print(f"[Migration] Warning: Migration check/alter failed: {e}")
        
    # Backfill calories and duration for existing Google Health logs
    try:
        db_session = SessionLocal()
        from models import WorkoutLog, UserProfile
        _WL_MET = {
            'Running': 9.8,
            'Walking': 3.5,
            'Cycling': 7.5,
            'Swimming': 7.0,
            'Yoga': 2.5,
            'Strength': 5.0,
            'HIIT': 10.0,
            'Pilates': 3.0,
            'Dancing': 5.5,
            'Meditation': 1.3,
            'Sports': 6.0,
            'Rowing': 7.0,
            'Boxing': 9.0,
            'Climbing': 8.0,
            'Stretching': 2.3,
            'Other': 4.0,
        }
        logs = db_session.query(WorkoutLog).filter(WorkoutLog.source == "google_health").all()
        updated = 0
        for log in logs:
            profile = db_session.query(UserProfile).filter(UserProfile.user_id == log.user_id).first()
            user_weight = profile.weight if (profile and profile.weight) else 70.0
            needs_update = False
            
            if log.notes and log.notes.startswith("Google Fit daily steps"):
                steps = log.step_count or 0
                if steps > 0:
                    effective_dur = steps / 100.0
                    step_calories = round(3.5 * user_weight * (effective_dur / 60.0))
                    duration_min = round(effective_dur)
                    if not log.calories or log.calories <= 0 or not log.duration_min or log.duration_min <= 0:
                        log.calories = step_calories
                        log.duration_min = duration_min
                        needs_update = True
            else:
                if not log.calories or log.calories <= 0:
                    duration_min = log.duration_min or 0
                    if duration_min > 0:
                        met = _WL_MET.get(log.workout_type, 4.0)
                        log.calories = round(met * user_weight * (duration_min / 60.0))
                        needs_update = True
            if needs_update:
                updated += 1
        if updated > 0:
            db_session.commit()
            print(f"[Migration] Backfilled {updated} existing Google Health logs with calories/duration.")
        db_session.close()
    except Exception as e:
        print(f"[Migration] Google Health backfill failed: {e}")

    print("Database initialized successfully!")


def get_db() -> Session:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


from contextlib import contextmanager

@contextmanager
def get_db_session():
    """Context-manager session for use outside FastAPI request scope (e.g. migrations)."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
