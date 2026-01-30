# ngrok Quick Setup Script
# Run this in PowerShell

Write-Host "=== ngrok Setup for Soul Squad ===" -ForegroundColor Cyan
Write-Host ""

# Step 1: Download ngrok
Write-Host "Step 1: Downloading ngrok..." -ForegroundColor Yellow
$ngrokUrl = "https://bin.equinox.io/c/bNyj1mQVY4c/ngrok-v3-stable-windows-amd64.zip"
$downloadPath = "$env:USERPROFILE\Downloads\ngrok.zip"
$extractPath = "C:\ngrok"

try {
    Invoke-WebRequest -Uri $ngrokUrl -OutFile $downloadPath
    Write-Host "✓ Downloaded successfully!" -ForegroundColor Green
} catch {
    Write-Host "✗ Download failed. Please download manually from: https://ngrok.com/download" -ForegroundColor Red
    exit
}

# Step 2: Extract ngrok
Write-Host ""
Write-Host "Step 2: Extracting ngrok..." -ForegroundColor Yellow
try {
    if (Test-Path $extractPath) {
        Remove-Item $extractPath -Recurse -Force
    }
    Expand-Archive -Path $downloadPath -DestinationPath $extractPath -Force
    Write-Host "✓ Extracted to C:\ngrok\" -ForegroundColor Green
} catch {
    Write-Host "✗ Extraction failed: $_" -ForegroundColor Red
    exit
}

# Step 3: Add to PATH
Write-Host ""
Write-Host "Step 3: Adding ngrok to PATH..." -ForegroundColor Yellow
try {
    $currentPath = [Environment]::GetEnvironmentVariable("Path", [EnvironmentVariableTarget]::User)
    if ($currentPath -notlike "*$extractPath*") {
        [Environment]::SetEnvironmentVariable("Path", "$currentPath;$extractPath", [EnvironmentVariableTarget]::User)
        $env:Path += ";$extractPath"
        Write-Host "✓ Added to PATH!" -ForegroundColor Green
    } else {
        Write-Host "✓ Already in PATH!" -ForegroundColor Green
    }
} catch {
    Write-Host "⚠ Could not add to PATH. You can still use: C:\ngrok\ngrok.exe" -ForegroundColor Yellow
}

# Step 4: Instructions
Write-Host ""
Write-Host "=== Setup Complete! ===" -ForegroundColor Cyan
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "1. Sign up for free ngrok account: https://dashboard.ngrok.com/signup" -ForegroundColor White
Write-Host "2. Get your auth token: https://dashboard.ngrok.com/get-started/your-authtoken" -ForegroundColor White
Write-Host "3. Run: ngrok config add-authtoken YOUR_TOKEN" -ForegroundColor White
Write-Host "4. Start your server: cd backend && python main.py" -ForegroundColor White
Write-Host "5. Start ngrok: ngrok http 8000" -ForegroundColor White
Write-Host ""
Write-Host "Opening ngrok signup page..." -ForegroundColor Yellow
Start-Sleep -Seconds 2
Start-Process "https://dashboard.ngrok.com/signup"

Write-Host ""
Write-Host "Press any key to exit..." -ForegroundColor Gray
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
