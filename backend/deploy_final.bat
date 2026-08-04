
@echo off
set SERVICE_NAME=solacesquad-backend
set REGION=us-central1
set "GEMINI_KEY=<REDACTED_API_KEY>"

echo Switching account...
call gcloud config set account sg@solacesquad.com

echo Deploying update...
call gcloud run deploy %SERVICE_NAME% ^
    --source . ^
    --platform managed ^
    --region %REGION% ^
    --allow-unauthenticated ^
    --update-env-vars "GEMINI_API_KEY=%GEMINI_KEY%"
