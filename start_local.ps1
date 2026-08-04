# Start Local Development Server
# This script runs the SolaceSquad backend with OTP bypass enabled

Write-Host "=== Starting SolaceSquad Local Development Server ===" -ForegroundColor Cyan
Write-Host ""
Write-Host "Configuration:" -ForegroundColor Yellow
Write-Host "  - OTP Verification: BYPASSED (for local development)" -ForegroundColor Green
Write-Host "  - Database: Cloud SQL (PostgreSQL)" -ForegroundColor Green
Write-Host "  - Environment: Production mode (to use Cloud SQL)" -ForegroundColor Green
Write-Host ""

# Change to backend directory
Set-Location backend

# Check if .env file exists
if (!(Test-Path ".env")) {
    Write-Host "ERROR: .env file not found!" -ForegroundColor Red
    Write-Host "Please make sure .env file exists in the backend directory" -ForegroundColor Yellow
    exit 1
}

Write-Host "Starting server on http://localhost:8000" -ForegroundColor Cyan
Write-Host "Press Ctrl+C to stop the server" -ForegroundColor Yellow
Write-Host ""

# Run the server
python main.py
