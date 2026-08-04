# Quick Restore Script for Working Version
# Run this if you need to restore the working version from 2026-02-12

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  RESTORING WORKING VERSION" -ForegroundColor Cyan
Write-Host "  Date: 2026-02-12" -ForegroundColor Cyan
Write-Host "  Git Tag: v1.0-working-2026-02-12" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Option 1: Restore from Git
Write-Host "Option 1: Restore from Git" -ForegroundColor Yellow
Write-Host "git checkout v1.0-working-2026-02-12" -ForegroundColor Gray
Write-Host ""

# Option 2: Restore Cloud Run revision
Write-Host "Option 2: Restore Cloud Run Revision" -ForegroundColor Yellow
Write-Host "gcloud run services update-traffic solacesquad --to-revisions=solacesquad-00010-fc2=100 --region=us-central1 --project=abiding-idea-485817-k2" -ForegroundColor Gray
Write-Host ""

$choice = Read-Host "Choose option (1 or 2)"

if ($choice -eq "1") {
    Write-Host "Checking out working version from Git..." -ForegroundColor Green
    git checkout v1.0-working-2026-02-12
    
    Write-Host ""
    Write-Host "Do you want to deploy to Cloud Run? (y/n)" -ForegroundColor Yellow
    $deploy = Read-Host
    
    if ($deploy -eq "y") {
        Write-Host "Deploying to Cloud Run..." -ForegroundColor Green
        cd backend
        gcloud run deploy solacesquad `
            --source . `
            --region=us-central1 `
            --platform=managed `
            --allow-unauthenticated `
            --add-cloudsql-instances=abiding-idea-485817-k2:us-central1:solacesquad-login-data1 `
            --update-secrets=DB_PASSWORD=db-password:11 `
            --set-env-vars=ENVIRONMENT=production, DB_USER=solacesquad_user, DB_NAME=solacesquad_prod, INSTANCE_CONNECTION_NAME=abiding-idea-485817-k2:us-central1:solacesquad-login-data1, BYPASS_OTP_VERIFICATION=true, GCP_PROJECT_ID=abiding-idea-485817-k2, GCP_LOCATION=us-central1, GEMINI_API_KEY=AIzaSyDzlEfQKdWv08Ar-SC4Mw5y9DlxPaZ34HA `
            --memory=1Gi `
            --cpu=1 `
            --min-instances=1 `
            --project=abiding-idea-485817-k2
        cd ..
    }
}
elseif ($choice -eq "2") {
    Write-Host "Restoring Cloud Run revision..." -ForegroundColor Green
    gcloud run services update-traffic solacesquad `
        --to-revisions=solacesquad-00010-fc2=100 `
        --region=us-central1 `
        --project=abiding-idea-485817-k2
}
else {
    Write-Host "Invalid choice. Exiting." -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "  RESTORE COMPLETE!" -ForegroundColor Green
Write-Host "  URL: https://solacesquad-312011725712.us-central1.run.app" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
