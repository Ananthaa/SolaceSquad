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
    except Exception as e:
        print(f"[Migration] Warning: Migration check/alter failed: {e}")
        
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
