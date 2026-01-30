"""
Database initialization script to create/update all tables
Run this script to initialize or update the database schema
"""

from database import init_db

if __name__ == "__main__":
    print("Initializing database...")
    init_db()
    print("Database initialized successfully!")
    print("All tables have been created/updated.")
