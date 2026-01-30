# Deploy SolaceSquad to Cloud Run
# Run this after prepare_deployment.ps1

Write-Host "=== Deploying SolaceSquad to Cloud Run ===" -ForegroundColor Cyan
Write-Host ""

# Set gcloud path
$gcloudPath = "$env:LOCALAPPDATA\Google\Cloud SDK\google-cloud-sdk\bin\gcloud.cmd"

# Configuration
$PROJECT_ID = "abiding-idea-485817-k2"
$SERVICE_NAME = "solacesquad"
$REGION = "us-central1"

Write-Host "Deploying to:" -ForegroundColor Yellow
Write-Host "  Project: $PROJECT_ID"
Write-Host "  Service: $SERVICE_NAME"
Write-Host "  Region: $REGION"
Write-Host ""

$confirm = Read-Host "Continue with deployment? (yes/no)"
if ($confirm -ne "yes") {
    Write-Host "Deployment cancelled" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "Starting deployment..." -ForegroundColor Cyan
Write-Host "(This will take 5-10 minutes...)" -ForegroundColor Yellow
Write-Host ""

# Change to backend directory
Set-Location backend

# Deploy to Cloud Run
& $gcloudPath run deploy $SERVICE_NAME `
    --source . `
    --platform managed `
    --region $REGION `
    --allow-unauthenticated `
    --set-env-vars="GCP_PROJECT_ID=$PROJECT_ID,GCP_LOCATION=$REGION,ENVIRONMENT=production,DEBUG=False" `
    --memory=512Mi `
    --cpu=1 `
    --min-instances=0 `
    --max-instances=10 `
    --timeout=300

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "=== Deployment Successful! ===" -ForegroundColor Green
    Write-Host ""
    
    # Get service URL
    Write-Host "Getting service URL..." -ForegroundColor Cyan
    $SERVICE_URL = & $gcloudPath run services describe $SERVICE_NAME `
        --region=$REGION `
        --format="value(status.url)"
    
    Write-Host ""
    Write-Host "Your app is live at:" -ForegroundColor Cyan
    Write-Host "  $SERVICE_URL" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Test it:" -ForegroundColor Cyan
    Write-Host "  curl $SERVICE_URL/health" -ForegroundColor White
    Write-Host ""
    Write-Host "View logs:" -ForegroundColor Cyan
    Write-Host "  & `"$gcloudPath`" run services logs read $SERVICE_NAME --region=$REGION" -ForegroundColor White
    Write-Host ""
    Write-Host "Monitor in console:" -ForegroundColor Cyan
    Write-Host "  https://console.cloud.google.com/run/detail/$REGION/$SERVICE_NAME" -ForegroundColor White
    Write-Host ""
}
else {
    Write-Host ""
    Write-Host "=== Deployment Failed ===" -ForegroundColor Red
    Write-Host ""
    Write-Host "Check the error messages above." -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Common issues:" -ForegroundColor Cyan
    Write-Host "  - Missing dependencies in requirements.txt"
    Write-Host "  - Syntax errors in code"
    Write-Host "  - Docker build errors"
    Write-Host ""
    Write-Host "View build logs:" -ForegroundColor Cyan
    Write-Host "  & `"$gcloudPath`" builds list --limit=5" -ForegroundColor White
    Write-Host ""
}

# Return to root directory
Set-Location ..
