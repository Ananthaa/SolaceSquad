
@echo off
echo ========================================================
echo   Soul Squad - Update Cloud Database Schema
echo ========================================================
echo.
echo This script will add the new 'Video Library' tables to Cloud SQL.
echo (VideoFolder, Video, UserExerciseLog)
echo.

echo [1/3] Checking dependencies...
pip install --upgrade cloud-sql-python-connector pg8000 sqlalchemy google-auth

echo.
echo [2/3] Checking Google Cloud Authentication...
call gcloud auth application-default login
if %errorlevel% neq 0 (
    echo.
    echo [WARNING] 'gcloud auth application-default login' failed.
    echo Please make sure you are logged in.
)

echo.
echo [3/3] Connecting to Cloud SQL...

:: Secrets
set INSTANCE_CONNECTION_NAME=abiding-idea-485817-k2:us-central1:solacesquad-login-data1
set DB_USER=solacesquad_user
set DB_NAME=solacesquad_prod
set DB_PASSWORD=solacePassword123!
set GOOGLE_APPLICATION_CREDENTIALS=

python init_cloud_db.py

if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Migration failed.
    pause
    exit /b %errorlevel%
)

echo.
echo [SUCCESS] Database updated! You can now deploy.
pause
