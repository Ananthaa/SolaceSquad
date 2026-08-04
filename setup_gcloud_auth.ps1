# ============================================================================
# Setup Google Cloud Authentication for Local Development
# ============================================================================
# This script helps you authenticate with Google Cloud to connect to Cloud SQL
# from your local machine.

Write-Host "=== Google Cloud Authentication Setup ===" -ForegroundColor Cyan
Write-Host ""
Write-Host "To connect to Cloud SQL from localhost, you need to:" -ForegroundColor Yellow
Write-Host "1. Install Google Cloud SDK (gcloud CLI)" -ForegroundColor White
Write-Host "2. Authenticate with your Google Cloud account" -ForegroundColor White
Write-Host ""

# Check if gcloud is installed
$gcloudInstalled = Get-Command gcloud -ErrorAction SilentlyContinue

if (!$gcloudInstalled) {
    Write-Host "ERROR: Google Cloud SDK (gcloud) is not installed!" -ForegroundColor Red
    Write-Host ""
    Write-Host "Please install it from:" -ForegroundColor Yellow
    Write-Host "https://cloud.google.com/sdk/docs/install" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "After installation:" -ForegroundColor Yellow
    Write-Host "1. Restart PowerShell" -ForegroundColor White
    Write-Host "2. Run this script again" -ForegroundColor White
    Write-Host ""
    
    # Ask if user wants to open the download page
    $response = Read-Host "Open download page in browser? (y/n)"
    if ($response -eq "y") {
        Start-Process "https://cloud.google.com/sdk/docs/install"
    }
    
    exit 1
}

Write-Host "Google Cloud SDK is installed!" -ForegroundColor Green
Write-Host ""

# Authenticate with Google Cloud
Write-Host "Authenticating with Google Cloud..." -ForegroundColor Cyan
Write-Host "This will open a browser window for you to sign in." -ForegroundColor Yellow
Write-Host ""

gcloud auth application-default login

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "Authentication successful!" -ForegroundColor Green
    Write-Host ""
    Write-Host "Setting default project..." -ForegroundColor Cyan
    gcloud config set project abiding-idea-485817-k2
    
    Write-Host ""
    Write-Host "=== Setup Complete! ===" -ForegroundColor Green
    Write-Host ""
    Write-Host "You can now run your application with:" -ForegroundColor Yellow
    Write-Host "  .\start_local.ps1" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Your localhost will connect to Cloud SQL database:" -ForegroundColor White
    Write-Host "  - Instance: solacesquad-login-data1" -ForegroundColor Gray
    Write-Host "  - Database: solacesquad_prod" -ForegroundColor Gray
    Write-Host ""
}
else {
    Write-Host ""
    Write-Host "Authentication failed!" -ForegroundColor Red
    Write-Host "Please try again or contact support." -ForegroundColor Yellow
    exit 1
}
