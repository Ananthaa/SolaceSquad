
@echo off
set "GEMINI_KEY=<REDACTED_API_KEY>"

echo Deploying...
gcloud run deploy solacesquad-backend --source . --platform managed --region us-central1 --allow-unauthenticated --update-env-vars "GEMINI_API_KEY=%GEMINI_KEY%"

pause
