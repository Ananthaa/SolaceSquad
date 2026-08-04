import os
from sqlalchemy import create_engine, text

# Get DB credentials from environment (like Cloud Run)
DB_USER = "Admin"
DB_PASS = "SoulSquad2024x"
DB_NAME = "solacesquad_prod"
INSTANCE_CONNECTION_NAME = "abiding-idea-485817-k2:us-central1:solacesquad-login-data1"

# Create connection string for Cloud SQL Connector (local testing usually needs proxy)
# But here I'll just try to connect via public IP if possible, or assume I'm running in an environment that has access.
# Actually, I'll use the same logic as the app.

db_url = f"postgresql+psycopg2://{DB_USER}:{DB_PASS}@34.47.239.160/{DB_NAME}"
engine = create_engine(db_url)

with engine.connect() as conn:
    result = conn.execute(text("SELECT id, email, user_type, is_active FROM users WHERE id = 2"))
    user = result.fetchone()
    print(f"User ID 2: {user}")

    result = conn.execute(text("SELECT id, email, user_type FROM users WHERE user_type = 'admin'"))
    admins = result.fetchall()
    print(f"Admins: {admins}")
