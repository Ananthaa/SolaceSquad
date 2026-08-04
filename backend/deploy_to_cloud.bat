
@echo off
echo ========================================================
echo        Deploying Soul Squad Backend to Cloud Run
echo ========================================================

:: Configuration
set SERVICE_NAME=solacesquad-backend
set REGION=us-central1
set PROJECT_ID=abiding-idea-485817-k2

:: Secrets
set DB_CONNECTION=abiding-idea-485817-k2:us-central1:solacesquad-login-data1
set DB_USER=solacesquad_user
set DB_NAME=solacesquad_prod
set DB_PASS=solacePassword123!
set SECRET=super-secret-fixed-key-for-development-12345
set BYPASS_OTP=true
set GEMINI_KEY=<REDACTED_API_KEY>

echo.
echo [1/1] Building and Deploying from Source...
call gcloud run deploy %SERVICE_NAME% ^
    --source . ^
    --platform managed ^
    --region %REGION% ^
    --allow-unauthenticated ^
    --set-env-vars INSTANCE_CONNECTION_NAME=%DB_CONNECTION% ^
    --set-env-vars DB_USER=%DB_USER% ^
    --set-env-vars DB_NAME=%DB_NAME% ^
    --set-env-vars DB_PASSWORD=%DB_PASS% ^
    --set-env-vars SECRET_KEY=%SECRET% ^
    --set-env-vars ENVIRONMENT=production ^
    --set-env-vars BYPASS_OTP_VERIFICATION=%BYPASS_OTP% ^
    --set-env-vars GEMINI_API_KEY=%GEMINI_KEY%

if %errorlevel% neq 0 (
    echo [ERROR] Deployment failed!
    exit /b %errorlevel%
)

echo.
echo ========================================================
echo [SUCCESS] Deployment Complete!
echo Your service is live at the URL above.
echo ========================================================
pause
