
$PROJECT_ID = "abiding-idea-485817-k2"
$REGION = "us-central1"

Write-Host "=== Setting up Secrets ===" -ForegroundColor Cyan

# Check/Create session-secret
Write-Host "Creating session-secret..."
$sessionSecret = -join ((65..90) + (97..122) + (48..57) | Get-Random -Count 32 | % { [char]$_ })
$secretBytes = [System.Text.Encoding]::UTF8.GetBytes($sessionSecret)
$tmpFile = [System.IO.Path]::GetTempFileName()
[System.IO.File]::WriteAllBytes($tmpFile, $secretBytes)

try {
    # Try to create if it doesn't exist
    cmd /c "gcloud secrets create session-secret --replication-policy=automatic --project=$PROJECT_ID 2>NUL"
}
catch {}

# Add version
cmd /c "gcloud secrets versions add session-secret --data-file=`"$tmpFile`" --project=$PROJECT_ID"
Remove-Item $tmpFile

Write-Host "session-secret created." -ForegroundColor Green


# Check/Create db-password
Write-Host ""
$dbPassword = Read-Host "Enter your Cloud SQL Database Password (the one you set for 'solacesquad_user')" -AsSecureString
$dbPasswordPlain = [Runtime.InteropServices.Marshal]::PtrToStringAuto([Runtime.InteropServices.Marshal]::SecureStringToBSTR($dbPassword))

$secretBytes = [System.Text.Encoding]::UTF8.GetBytes($dbPasswordPlain)
$tmpFile = [System.IO.Path]::GetTempFileName()
[System.IO.File]::WriteAllBytes($tmpFile, $secretBytes)

try {
    cmd /c "gcloud secrets create db-password --replication-policy=automatic --project=$PROJECT_ID 2>NUL"
}
catch {}

cmd /c "gcloud secrets versions add db-password --data-file=`"$tmpFile`" --project=$PROJECT_ID"
Remove-Item $tmpFile

Write-Host "db-password created." -ForegroundColor Green
Write-Host ""
Write-Host "=== Secrets Ready! ===" -ForegroundColor Cyan
Write-Host "Now run .\deploy_app.ps1 again."
