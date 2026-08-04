import sys
import os
from sqlalchemy import text

# Add current directory to path
sys.path.append(os.getcwd())

from database import engine

def migrate():
    print("Connecting to database...")
    with engine.connect() as conn:
        print("Checking for 'timezone' column in 'users' table...")
        try:
            # Check if column exists first (PostgreSQL specific check)
            check_sql = text("SELECT column_name FROM information_schema.columns WHERE table_name='users' AND column_name='timezone'")
            result = conn.execute(check_sql).fetchone()
            
            if not result:
                print("Adding 'timezone' column...")
                conn.execute(text("ALTER TABLE users ADD COLUMN timezone VARCHAR(100) DEFAULT 'UTC'"))
                conn.commit()
                print("Column 'timezone' added successfully.")
            else:
                print("Column 'timezone' already exists.")
                
        except Exception as e:
            print(f"Error during migration: {e}")

if __name__ == "__main__":
    migrate()
