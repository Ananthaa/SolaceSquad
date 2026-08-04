$PROJECT_ID = "abiding-idea-485817-k2"
$INSTANCE_NAME = "solacesquad-login-data1"
$DB_USER = "solacesquad_user"

Write-Host "=== Resetting Database Password ===" -ForegroundColor Cyan
Write-Host ""
Write-Host "We need to set a NEW, simple password for the database user."
Write-Host "Use only letters and numbers (no special characters)." -ForegroundColor Yellow
Write-Host ""

# Generate a simple password suggestion
$suggestedPassword = -join ((65..90) + (97..122) + (48..57) | Get-Random -Count 16 | % { [char]$_ })
Write-Host "Suggested password: $suggestedPassword" -ForegroundColor Green
Write-Host ""

$newPassword = Read-Host "Enter a NEW password for database user '$DB_USER' (or press Enter to use suggested)"

if ([string]::IsNullOrWhiteSpace($newPassword)) {
    $newPassword = $suggestedPassword
    Write-Host "Using suggested password" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Step 1: Updating database user password..." -ForegroundColor Cyan
$setPasswordCmd = "gcloud sql users set-password $DB_USER --instance=$INSTANCE_NAME --password=$newPassword --project=$PROJECT_ID"
cmd /c $setPasswordCmd

if ($LASTEXITCODE -ne 0) {
    Write-Host "Failed to set database password!" -ForegroundColor Red
    exit 1
}

Write-Host "Step 2: Updating secret..." -ForegroundColor Cyan
# Delete all versions and recreate
cmd /c "gcloud secrets delete db-password --project=$PROJECT_ID --quiet 2>NUL"
cmd /c "gcloud secrets create db-password --replication-policy=automatic --project=$PROJECT_ID"

# Add the new password
$command = "echo $newPassword | gcloud secrets versions add db-password --data-file=- --project=$PROJECT_ID"
cmd /c $command

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "=== Success! ===" -ForegroundColor Green
    Write-Host ""
    Write-Host "Database password has been reset and secret updated." -ForegroundColor Green
    Write-Host ""
    Write-Host "IMPORTANT: Save this password somewhere safe:" -ForegroundColor Yellow
    Write-Host "  $newPassword" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Now run: .\deploy_app.ps1" -ForegroundColor Cyan
}
else {
    Write-Host ""
    Write-Host "=== Failed ===" -ForegroundColor Red
}
