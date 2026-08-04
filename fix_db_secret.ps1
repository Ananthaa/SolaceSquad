$PROJECT_ID = "abiding-idea-485817-k2"

Write-Host "=== Fixing Database Password Secret ===" -ForegroundColor Cyan
Write-Host ""
Write-Host "The current password secret has encoding issues."
Write-Host "We need to recreate it with the correct password."
Write-Host ""

$dbPassword = Read-Host "Enter your Cloud SQL Database Password for 'solacesquad_user'" -AsSecureString
$dbPasswordPlain = [Runtime.InteropServices.Marshal]::PtrToStringAuto([Runtime.InteropServices.Marshal]::SecureStringToBSTR($dbPassword))

Write-Host ""
Write-Host "Deleting old secret version..." -ForegroundColor Yellow
cmd /c "gcloud secrets versions destroy latest --secret=db-password --project=$PROJECT_ID --quiet 2>NUL"

Write-Host "Creating new secret version..." -ForegroundColor Yellow
# Use echo to avoid encoding issues
$command = "echo $dbPasswordPlain | gcloud secrets versions add db-password --data-file=- --project=$PROJECT_ID"
cmd /c $command

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "=== Secret Updated Successfully! ===" -ForegroundColor Green
    Write-Host ""
    Write-Host "Now run: .\deploy_app.ps1" -ForegroundColor Cyan
}
else {
    Write-Host ""
    Write-Host "=== Failed to Update Secret ===" -ForegroundColor Red
    Write-Host "Please try manually in the Google Cloud Console"
}
