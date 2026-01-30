# SolaceSquad GCP Deployment Script
# Quick deployment to Google Cloud Run

Write-Host "=== SolaceSquad GCP Deployment ===" -ForegroundColor Cyan
Write-Host ""

# Set gcloud path
$gcloudPath = "$env:LOCALAPPDATA\Google\Cloud SDK\google-cloud-sdk\bin\gcloud.cmd"

# Configuration
$PROJECT_ID = "abiding-idea-485817-k2"
$SERVICE_NAME = "solacesquad"
$REGION = "us-central1"

Write-Host "Configuration:" -ForegroundColor Yellow
Write-Host "  Project: $PROJECT_ID"
Write-Host "  Service: $SERVICE_NAME"
Write-Host "  Region: $REGION"
Write-Host ""

# Set project
Write-Host "Setting project..." -ForegroundColor Cyan
& $gcloudPath config set project $PROJECT_ID

# Set region
Write-Host "Setting default region..." -ForegroundColor Cyan
& $gcloudPath config set run/region $REGION

# Enable required APIs
Write-Host ""
Write-Host "Enabling required APIs..." -ForegroundColor Cyan
Write-Host "(This may take a few minutes...)" -ForegroundColor Yellow

& $gcloudPath services enable run.googleapis.com
& $gcloudPath services enable cloudbuild.googleapis.com
& $gcloudPath services enable aiplatform.googleapis.com
& $gcloudPath services enable secretmanager.googleapis.com

Write-Host ""
Write-Host "APIs enabled successfully!" -ForegroundColor Green

Write-Host ""
Write-Host "=== Ready to Deploy ===" -ForegroundColor Green
Write-Host ""
Write-Host "Next step: Deploy your application" -ForegroundColor Cyan
Write-Host ""
Write-Host "Run this command to deploy:" -ForegroundColor Yellow
Write-Host "  cd backend" -ForegroundColor White
Write-Host "  & `"$gcloudPath`" run deploy $SERVICE_NAME --source . --region $REGION --allow-unauthenticated --set-env-vars=`"GCP_PROJECT_ID=$PROJECT_ID,GCP_LOCATION=$REGION,ENVIRONMENT=production`"" -ForegroundColor White
Write-Host ""
Write-Host "Or run: .\deploy_app.ps1" -ForegroundColor Yellow
Write-Host ""
