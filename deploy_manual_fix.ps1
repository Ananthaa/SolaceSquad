# Manual Deployment Script
# This uses the simple Dockerfile to deploy only the template fixes

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "MANUAL FIX DEPLOYMENT" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Step 1: Backup current Dockerfile
Write-Host "Step 1: Backing up current Dockerfile..." -ForegroundColor Yellow
Copy-Item "backend\Dockerfile" "backend\Dockerfile.backup" -Force
Write-Host "✓ Backup created" -ForegroundColor Green
Write-Host ""

# Step 2: Use simple Dockerfile
Write-Host "Step 2: Using simplified Dockerfile..." -ForegroundColor Yellow
Copy-Item "backend\Dockerfile.simple" "backend\Dockerfile" -Force
Write-Host "✓ Simple Dockerfile activated" -ForegroundColor Green
Write-Host ""

# Step 3: Deploy to Cloud Run
Write-Host "Step 3: Deploying to Cloud Run..." -ForegroundColor Yellow
Write-Host "This will take 5-10 minutes..." -ForegroundColor Gray
Write-Host ""

Set-Location backend

gcloud run deploy solacesquad `
    --source . `
    --platform managed `
    --region us-central1 `
    --allow-unauthenticated `
    --project abiding-idea-485817-k2 `
    --add-cloudsql-instances=abiding-idea-485817-k2:us-central1:solacesquad-login-data1 `
    --update-secrets=DB_PASSWORD=db-password:latest `
    --update-env-vars=DB_USER=Admin, DB_NAME=solacesquad_prod, INSTANCE_CONNECTION_NAME=abiding-idea-485817-k2:us-central1:solacesquad-login-data1, BYPASS_OTP_VERIFICATION=true, GCP_PROJECT_ID=abiding-idea-485817-k2, GCP_LOCATION=us-central1, GEMINI_API_KEY=AIzaSyDzlEfQKdWv08Ar-SC4Mw5y9DlxPaZ34HA `
    --memory=1Gi `
    --cpu=1 `
    --timeout=300

$exitCode = $LASTEXITCODE

Set-Location ..

# Step 4: Restore original Dockerfile
Write-Host ""
Write-Host "Step 4: Restoring original Dockerfile..." -ForegroundColor Yellow
Copy-Item "backend\Dockerfile.backup" "backend\Dockerfile" -Force
Remove-Item "backend\Dockerfile.backup" -Force
Write-Host "✓ Original Dockerfile restored" -ForegroundColor Green
Write-Host ""

if ($exitCode -eq 0) {
    Write-Host "========================================" -ForegroundColor Green
    Write-Host "DEPLOYMENT SUCCESSFUL!" -ForegroundColor Green
    Write-Host "========================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "The call room fixes are now live!" -ForegroundColor Green
    Write-Host "Test the calls at: https://solacesquad-sf52cc6tnq-uc.a.run.app" -ForegroundColor Cyan
}
else {
    Write-Host "========================================" -ForegroundColor Red
    Write-Host "DEPLOYMENT FAILED" -ForegroundColor Red
    Write-Host "========================================" -ForegroundColor Red
    Write-Host ""
    Write-Host "The simple Dockerfile also failed." -ForegroundColor Red
    Write-Host "We need to investigate the Cloud Run logs." -ForegroundColor Yellow
}
