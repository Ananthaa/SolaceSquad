from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from models import Base
import os

# Database configuration
DB_USER = os.getenv("DB_USER", "solacesquad_user")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_NAME = os.getenv("DB_NAME", "solacesquad")
INSTANCE_CONNECTION_NAME = os.getenv("INSTANCE_CONNECTION_NAME")

if os.getenv("DATABASE_URL"):
    # Allow explicit override
    DATABASE_URL = os.getenv("DATABASE_URL")
elif DB_PASSWORD and INSTANCE_CONNECTION_NAME:
    # Google Cloud SQL (PostgreSQL)
    # Ensure pg8000 driver is used
    socket_path = f"/cloudsql/{INSTANCE_CONNECTION_NAME}"
    DATABASE_URL = f"postgresql+pg8000://{DB_USER}:{DB_PASSWORD}@/{DB_NAME}?unix_sock={socket_path}"
else:
    # Fallback to SQLite (Local Development)
    DATABASE_URL = "sqlite:///./soul_squad.db"

# Connection arguments
connect_args = {}

# Configure for SQLite vs PostgreSQL
if "sqlite" in DATABASE_URL:
    connect_args = {"check_same_thread": False}
else:
    # PostgreSQL configuration
    pass

# Create engine
engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
    echo=False,  # Set to True for SQL query logging
    pool_pre_ping=True,  # Enable connection health checks
    pool_size=5,        # Reasonable pool size for Cloud Run
    max_overflow=10
)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db():
    """Initialize the database by creating all tables"""
    Base.metadata.create_all(bind=engine)
    print("Database initialized successfully!")


def get_db() -> Session:
    """
    Dependency function to get database session.
    Use with FastAPI Depends() for automatic session management.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_db_session() -> Session:
    """
    Get a database session for manual use.
    Remember to close the session when done.
    """
    return SessionLocal()
