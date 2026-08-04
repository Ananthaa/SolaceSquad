$PROJECT_ID = "abiding-idea-485817-k2"
$INSTANCE_NAME = "solacesquad-login-data1"
$DB_USER = "solacesquad_user"

Write-Host "=== Fixing Cloud SQL Connection ===" -ForegroundColor Cyan
Write-Host ""
Write-Host "Setting a clean, simple password for the database..." -ForegroundColor Yellow
Write-Host ""

# Use a fixed, simple password
$newPassword = "SolaceSquad2026"

Write-Host "New password will be: $newPassword" -ForegroundColor Green
Write-Host ""

Write-Host "Step 1: Updating database user password..." -ForegroundColor Cyan
cmd /c "gcloud sql users set-password $DB_USER --instance=$INSTANCE_NAME --password=$newPassword --project=$PROJECT_ID"

if ($LASTEXITCODE -ne 0) {
    Write-Host "Failed to set database password!" -ForegroundColor Red
    exit 1
}

Write-Host "Step 2: Deleting old secret..." -ForegroundColor Cyan
cmd /c "gcloud secrets delete db-password --project=$PROJECT_ID --quiet 2>NUL"

Write-Host "Step 3: Creating new secret..." -ForegroundColor Cyan
cmd /c "gcloud secrets create db-password --replication-policy=automatic --project=$PROJECT_ID"

Write-Host "Step 4: Adding password to secret (using file to avoid encoding issues)..." -ForegroundColor Cyan
# Write password to a temporary file with UTF-8 encoding, no BOM, no newline
$tempFile = [System.IO.Path]::GetTempFileName()
[System.IO.File]::WriteAllText($tempFile, $newPassword, [System.Text.UTF8Encoding]::new($false))

cmd /c "gcloud secrets versions add db-password --data-file=`"$tempFile`" --project=$PROJECT_ID"
Remove-Item $tempFile

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "=== Success! ===" -ForegroundColor Green
    Write-Host ""
    Write-Host "Database password: $newPassword" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Now run: .\deploy_app.ps1" -ForegroundColor Cyan
}
else {
    Write-Host ""
    Write-Host "=== Failed ===" -ForegroundColor Red
}
