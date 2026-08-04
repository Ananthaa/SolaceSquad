import argparse
import sys
import os
import bcrypt
from datetime import datetime

# Set environment variables for import path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Load models and database setup
from models import Base, User, UserProfile, VitalsRecord, MoodEntry, JournalEntry, WorkoutLog, UserExerciseLog, DailyWellnessScore, UserSubscription

def get_session(use_cloud_connector=False):
    """Get SQLAlchemy session. Uses Google Cloud SQL Connector if specified."""
    if use_cloud_connector:
        from google.cloud.sql.connector import Connector
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        
        # Ensure credentials env var is set
        os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = r"c:\Anantha\Projects\Soul Squad\backend\service-account.json"
        
        INSTANCE_CONNECTION_NAME = "abiding-idea-485817-k2:us-central1:solacesquad-login-data1"
        DB_USER = "Admin"
        DB_PASSWORD = "SoulSquad2024x"
        DB_NAME = "solacesquad_prod"
        
        print(f"[DB] Connecting to remote Cloud SQL: {INSTANCE_CONNECTION_NAME} as user={DB_USER}")
        connector = Connector()
        
        def getconn():
            return connector.connect(
                INSTANCE_CONNECTION_NAME,
                "pg8000",
                user=DB_USER,
                password=DB_PASSWORD,
                db=DB_NAME
            )
            
        engine = create_engine("postgresql+pg8000://", creator=getconn)
        Session = sessionmaker(bind=engine)
        return Session(), connector
    else:
        # Use standard local configuration
        from database import SessionLocal
        print("[DB] Connecting using standard database configuration...")
        return SessionLocal(), None

def clone_model(model_obj, **kwargs):
    """Clone a SQLAlchemy model instance, resetting primary keys and updating attributes."""
    table = model_obj.__table__
    non_pk_columns = [k for k in table.columns.keys() if not table.columns[k].primary_key]
    data = {c: getattr(model_obj, c) for c in non_pk_columns}
    data.update(kwargs)
    return model_obj.__class__(**data)

def main():
    parser = argparse.ArgumentParser(description="Clone user account and health metrics.")
    parser.add_argument("--source", default="ananthaa@gmail.com", help="Source user email")
    parser.add_argument("--target", default="solacesquad2027@gmail.com", help="Target user email")
    parser.add_argument("--name", default="SolaceSquad", help="Target user name")
    parser.add_argument("--password", default="DemoPWD123", help="Target user password")
    parser.add_argument("--prod", action="store_true", help="Connect to production Cloud SQL directly")
    
    args = parser.parse_args()
    
    # 1. Establish session
    session, connector = get_session(use_cloud_connector=args.prod)
    
    try:
        # 2. Lookup source user
        source = session.query(User).filter_by(email=args.source).first()
        if not source:
            print(f"[ERROR] Source user '{args.source}' not found!")
            sys.exit(1)
            
        print(f"[OK] Found source user: '{source.name}' ({source.email}) ID={source.id}")
        
        # 3. Check and clean up existing target user
        existing_target = session.query(User).filter_by(email=args.target).first()
        if existing_target:
            print(f"[INFO] Target user '{args.target}' already exists. Purging user and all associated data...")
            session.delete(existing_target)
            session.commit()
            print("[OK] Purged existing target user.")
            
        # 4. Create new target user
        print(f"[INFO] Creating new user '{args.name}' ({args.target})...")
        target_user = User(
            email=args.target,
            name=args.name,
            user_type=source.user_type,
            created_at=source.created_at, # Copy joining date!
            first_login=source.first_login,
            last_login=source.last_login,
            is_active=True,
            phone_number=None, # Set to None to avoid unique constraint conflict
            google_id=None,    # Set to None to avoid unique OAuth ID conflict
            oauth_provider=None,
            email_verified=True
        )
        target_user.set_password(args.password)
        session.add(target_user)
        session.flush() # Populate target_user.id
        
        print(f"[OK] Created new user: ID={target_user.id}")
        
        # 5. Clone UserProfile
        profile = session.query(UserProfile).filter_by(user_id=source.id).first()
        if profile:
            print("[INFO] Cloning UserProfile...")
            cloned_profile = clone_model(profile, user_id=target_user.id)
            session.add(cloned_profile)
            
        # Helper function to clone multiple records
        def clone_child_records(model_class, label, user_field="user_id"):
            records = session.query(model_class).filter(getattr(model_class, user_field) == source.id).all()
            print(f"[INFO] Cloning {len(records)} records for {label}...")
            for rec in records:
                cloned = clone_model(rec, **{user_field: target_user.id})
                session.add(cloned)
                
        # 6. Clone all child tables
        clone_child_records(VitalsRecord, "VitalsRecord")
        clone_child_records(MoodEntry, "MoodEntry")
        clone_child_records(JournalEntry, "JournalEntry")
        clone_child_records(WorkoutLog, "WorkoutLog")
        clone_child_records(UserExerciseLog, "UserExerciseLog")
        clone_child_records(DailyWellnessScore, "DailyWellnessScore")
        clone_child_records(UserSubscription, "UserSubscription")
        
        # 7. Commit transaction
        print("[INFO] Committing database transaction...")
        session.commit()
        print("[SUCCESS] User cloned successfully!")
        
    except Exception as e:
        print(f"[ERROR] An error occurred: {e}")
        import traceback
        traceback.print_exc()
        print("[INFO] Rolling back transaction...")
        session.rollback()
        sys.exit(1)
    finally:
        session.close()
        if connector:
            connector.close()

if __name__ == "__main__":
    main()
