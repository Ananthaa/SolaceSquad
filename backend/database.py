from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from models import Base
import os

# Database configuration
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./soul_squad.db")

# Connection arguments
connect_args = {}

# Configure for SQLite vs PostgreSQL
if "sqlite" in DATABASE_URL:
    connect_args = {"check_same_thread": False}
else:
    # PostgreSQL configuration guarantees
    # In production, we would enforce SSL here with:
    # connect_args = {"sslmode": "require"} 
    pass

# Create engine
engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
    echo=False  # Set to True for SQL query logging
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
