import pg8000
from google.cloud.sql.connector import Connector

# Database configuration
INSTANCE_CONNECTION_NAME = "abiding-idea-485817-k2:us-central1:solacesquad-login-data1"
DB_USER = "postgres"
DB_PASSWORD = "postgres123"
DB_NAME = "solacesquad_prod"

print("Connecting to Cloud SQL as postgres...")

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
    
    print("Granting permissions to postgres user...")
    
    # Grant all privileges on all tables
    cursor.execute("GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO postgres")
    cursor.execute("GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO postgres")
    cursor.execute("GRANT ALL PRIVILEGES ON SCHEMA public TO postgres")
    
    conn.commit()
    
    print("SUCCESS: Permissions granted!")
    
    # Now try to query users
    print("\nChecking users table...")
    cursor.execute("SELECT COUNT(*) FROM users")
    total = cursor.fetchone()[0]
    print(f"Total users in database: {total}")
    
    cursor.execute("SELECT id, email FROM users LIMIT 5")
    users = cursor.fetchall()
    print(f"\nFirst 5 users:")
    for user in users:
        print(f"  ID: {user[0]}, Email: {user[1]}")
    
    cursor.close()
    conn.close()
    connector.close()
    
    print("\nSUCCESS: Your data is safe!")
    
except Exception as e:
    print(f"\nERROR: {e}")
    import traceback
    traceback.print_exc()
