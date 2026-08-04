@echo off
echo Setting environment variables for local Cloud SQL connection...

set ENVIRONMENT=production
set DB_USER=Admin
set DB_PASSWORD=AdminPass2024!
set DB_NAME=solacesquad_prod
set INSTANCE_CONNECTION_NAME=abiding-idea-485817-k2:us-central1:solacesquad-login-data1
set BYPASS_OTP_VERIFICATION=true
set GCP_PROJECT_ID=abiding-idea-485817-k2
set GCP_LOCATION=us-central1
set GEMINI_API_KEY=AIzaSyDzlEfQKdWv08Ar-SC4Mw5y9DlxPaZ34HA

echo.
echo Environment variables set!
echo.
echo Starting FastAPI server...
echo.

cd backend
python -m uvicorn main:app --host 0.0.0.0 --port 8080 --reload
