"""
Password Reset Script for Cloud SQL
Resets password for a specific user in the production database
"""
import os
import sys
from sqlalchemy import create_engine, text
from passlib.context import CryptContext
from google.cloud.sql.connector import Connector

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(password: str) -> str:
    """Hash a password using bcrypt"""
    return pwd_context.hash(password)

def reset_password(email: str, new_password: str):
    """Reset password for a user in Cloud SQL"""
    
    # Cloud SQL connection details
    project_id = "abiding-idea-485817-k2"
    region = "us-central1"
    instance_name = "solacesquad-login-data1"
    database_name = "solacesquad_db"
    db_user = "postgres"
    db_password = "Solace@2025"
    
    print(f"Connecting to Cloud SQL...")
    print(f"   Instance: {instance_name}")
    print(f"   Database: {database_name}")
    
    # Initialize Cloud SQL Python Connector
    connector = Connector()
    
    def getconn():
        conn = connector.connect(
            f"{project_id}:{region}:{instance_name}",
            "pg8000",
            user=db_user,
            password=db_password,
            db=database_name,
        )
        return conn
    
    # Create SQLAlchemy engine
    engine = create_engine(
        "postgresql+pg8000://",
        creator=getconn,
    )
    
    try:
        with engine.connect() as conn:
            # Check if user exists
            result = conn.execute(
                text("SELECT id, email, name FROM users WHERE email = :email"),
                {"email": email}
            )
            user = result.fetchone()
            
            if not user:
                print(f"ERROR: User not found: {email}")
                return False
            
            print(f"SUCCESS: User found:")
            print(f"   ID: {user[0]}")
            print(f"   Email: {user[1]}")
            print(f"   Name: {user[2]}")
            
            # Hash the new password
            hashed_password = hash_password(new_password)
            print(f"\nHashing new password...")
            
            # Update password
            conn.execute(
                text("UPDATE users SET password_hash = :password WHERE email = :email"),
                {"password": hashed_password, "email": email}
            )
            conn.commit()
            
            print(f"SUCCESS: Password updated successfully!")
            print(f"\nNew login credentials:")
            print(f"   Email: {email}")
            print(f"   Password: {new_password}")
            print(f"\nYou can now login with these credentials!")
            
            return True
            
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        connector.close()

if __name__ == "__main__":
    print("=" * 60)
    print("Password Reset Script for SolaceSquad")
    print("=" * 60)
    
    # User to reset
    email = "test@test.com"
    
    # Get new password from user
    print(f"\nResetting password for: {email}")
    new_password = input("Enter new password: ").strip()
    
    if not new_password:
        print("ERROR: Password cannot be empty!")
        sys.exit(1)
    
    if len(new_password) < 8:
        print("ERROR: Password must be at least 8 characters!")
        sys.exit(1)
    
    # Confirm
    confirm = input(f"\nWARNING: Reset password for {email}? (yes/no): ").strip().lower()
    
    if confirm != "yes":
        print("Cancelled.")
        sys.exit(0)
    
    # Reset password
    print()
    success = reset_password(email, new_password)
    
    if success:
        print("\n" + "=" * 60)
        print("SUCCESS! Password has been reset.")
        print("=" * 60)
    else:
        print("\n" + "=" * 60)
        print("FAILED! Could not reset password.")
        print("=" * 60)
        sys.exit(1)
