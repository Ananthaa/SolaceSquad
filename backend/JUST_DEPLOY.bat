@echo off
echo ========================================================
echo   Soul Squad - Final Deployment (Interactive Mode)
echo ========================================================
echo.
echo This script uses your active terminal credentials.
echo.

set SERVICE_NAME=solacesquad-backend
set REGION=us-central1
set GEMINI_KEY=<REDACTED_API_KEY>

echo [1/1] Deploying with Gemini API Key update...
echo.

call gcloud run deploy %SERVICE_NAME% ^
    --source . ^
    --platform managed ^
    --region %REGION% ^
    --allow-unauthenticated ^
    --update-env-vars "GEMINI_API_KEY=%GEMINI_KEY%"

if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Deployment failed.
    echo Please ensure you are logged in by running: gcloud auth login
    pause
    exit /b %errorlevel%
)

echo.
echo [SUCCESS] Integration Complete!
pause
