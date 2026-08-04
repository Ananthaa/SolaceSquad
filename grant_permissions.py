import os
import sys

# Set environment variables
os.environ['ENVIRONMENT'] = 'production'
os.environ['DB_USER'] = 'Admin'
os.environ['DB_PASSWORD'] = 'AdminPass2024!'
os.environ['DB_NAME'] = 'solacesquad_prod'
os.environ['INSTANCE_CONNECTION_NAME'] = 'abiding-idea-485817-k2:us-central1:solacesquad-login-data1'

# Change to backend directory
os.chdir('backend')
sys.path.insert(0, os.getcwd())

# Import database
from database import SessionLocal
from sqlalchemy import text

# Create session
db = SessionLocal()

print("=" * 60)
print("GRANTING PERMISSIONS TO Admin USER")
print("=" * 60)
print()

# Grant permissions on all tables
tables = [
    'users',
    'consultant_profiles',
    'appointments',
    'vitals',
    'mood_entries',
    'chat_messages',
    'notifications',
    'call_recordings',
    'consultation_notes'
]

try:
    for table in tables:
        print(f"Granting permissions on {table}...")
        db.execute(text(f'GRANT ALL PRIVILEGES ON TABLE {table} TO "Admin"'))
    
    # Grant permissions on sequences
    print()
    print("Granting permissions on sequences...")
    db.execute(text('GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO "Admin"'))
    
    db.commit()
    print()
    print("=" * 60)
    print("SUCCESS! All permissions granted to Admin user")
    print("=" * 60)
except Exception as e:
    print(f"Error: {e}")
    print()
    print("Trying alternative approach...")
    db.rollback()
    
    # Try using postgres user
    print()
    print("You may need to run this SQL command as postgres user:")
    print()
    print("GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO \"Admin\";")
    print("GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO \"Admin\";")

db.close()
