import pg8000
from google.cloud.sql.connector import Connector

# Database configuration
INSTANCE_CONNECTION_NAME = "abiding-idea-485817-k2:us-central1:solacesquad-login-data1"
DB_USER = "postgres"
DB_PASSWORD = "postgres123"
DB_NAME = "solacesquad_prod"

print("Connecting to Cloud SQL...")

# Initialize Cloud SQL Python Connector
connector = Connector()

def getconn():
    conn = connector.connect(
        INSTANCE_CONNECTION_NAME,
        "pg8000",
        user=DB_USER,
        password=DB_PASSWORD,
        db=DB_NAME
    )
    return conn

try:
    # Get connection
    conn = getconn()
    cursor = conn.cursor()
    
    # Check users table
    print("\n=== USERS TABLE ===")
    cursor.execute("SELECT id, email, phone_number, created_at FROM users ORDER BY created_at DESC LIMIT 10")
    users = cursor.fetchall()
    
    if users:
        print(f"Found {len(users)} users:")
        for user in users:
            print(f"  ID: {user[0]}, Email: {user[1]}, Phone: {user[2]}, Created: {user[3]}")
    else:
        print("ERROR: No users found in database!")
    
    # Check total count
    cursor.execute("SELECT COUNT(*) FROM users")
    total = cursor.fetchone()[0]
    print(f"\nTotal users in database: {total}")
    
    # Check consultant_profiles
    print("\n=== CONSULTANT PROFILES ===")
    cursor.execute("SELECT id, user_id, name, specialization FROM consultant_profiles LIMIT 10")
    consultants = cursor.fetchall()
    
    if consultants:
        print(f"Found {len(consultants)} consultants:")
        for consultant in consultants:
            print(f"  ID: {consultant[0]}, User ID: {consultant[1]}, Name: {consultant[2]}, Spec: {consultant[3]}")
    else:
        print("No consultants found")
    
    cursor.close()
    conn.close()
    connector.close()
    
    print("\nERROR Database connection successful!")
    print(f"SUCCESS Your data is safe - {total} users found")
    
except Exception as e:
    print(f"\nERROR: {e}")
    import traceback
    traceback.print_exc()
