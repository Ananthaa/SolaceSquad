import os
import sys

# Force stdout/stderr to UTF-8 to prevent Unicode/charmap print crashes in Windows command environments
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')
os.environ['PYTHONIOENCODING'] = 'utf-8'

# Set environment variables
os.environ['ENVIRONMENT'] = 'production'
os.environ['HTTPS_ONLY'] = 'false'
os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = os.path.abspath('backend/service-account.json')
os.environ['DB_USER'] = 'Admin'
os.environ['DB_PASSWORD'] = 'SoulSquad2024x'
os.environ['DB_NAME'] = 'solacesquad_prod'
os.environ['INSTANCE_CONNECTION_NAME'] = 'abiding-idea-485817-k2:us-central1:solacesquad-login-data1'
os.environ['BYPASS_OTP_VERIFICATION'] = 'true'
os.environ['GCP_PROJECT_ID'] = 'abiding-idea-485817-k2'
os.environ['GCP_LOCATION'] = 'us-central1'
os.environ['GEMINI_API_KEY'] = 'AIzaSyDzlEfQKdWv08Ar-SC4Mw5y9DlxPaZ34HA'

print("Environment variables set!")
print(f"ENVIRONMENT: {os.environ['ENVIRONMENT']}")
print(f"DB_USER: {os.environ['DB_USER']}")
print(f"DB_NAME: {os.environ['DB_NAME']}")
print()

# Change to backend directory
os.chdir('backend')
sys.path.insert(0, os.getcwd())

print("Testing database connection...")
try:
    import database
    print("[OK] Database module imported successfully!")
    print(f"Database engine: {database.engine}")
except Exception as e:
    print(f"[ERROR] Error importing database: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print()
print("Starting uvicorn on port 8081...")
import uvicorn
uvicorn.run("main:app", host="0.0.0.0", port=8081)
