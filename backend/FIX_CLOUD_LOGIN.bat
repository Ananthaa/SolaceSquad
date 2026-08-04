
@echo off
echo ========================================================
echo   Soul Squad - Fix Admin Login (Cloud SQL)
echo ========================================================
echo.
echo This script will update the admin password in the PRODUCTION database.
echo.

:: Activate Python Virtual Environment
if exist venv\Scripts\activate.bat (
    call venv\Scripts\activate.bat
) else (
    echo [WARNING] venv not found, using global python...
)

:: Secrets
set INSTANCE_CONNECTION_NAME=abiding-idea-485817-k2:us-central1:solacesquad-login-data1
set DB_USER=solacesquad_user
set DB_NAME=solacesquad_prod
set DB_PASSWORD=solacePassword123!
set GOOGLE_APPLICATION_CREDENTIALS=

echo Connecting to Cloud SQL...
python fix_admin_login.py

if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Script failed. ensure you have run 'gcloud auth login' and dependencies are installed.
    pause
    exit /b %errorlevel%
)

echo.
echo [SUCCESS] Admin password reset on Cloud SQL!
pause
