# ── SolaceSquad Local Dev Server Startup ─────────────────────────────────────
# Double-click this file OR run:  .\start_server.ps1
# DO NOT use "python main.py" directly — uvicorn is required.
# ─────────────────────────────────────────────────────────────────────────────

$env:PYTHONIOENCODING = "utf-8"
$env:ENVIRONMENT = "production"
$env:INSTANCE_CONNECTION_NAME = "abiding-idea-485817-k2:us-central1:solacesquad-login-data1"
$env:DB_NAME = "solacesquad_prod"
$env:DB_USER = "solacesquad_user"
$env:DB_PASSWORD = "SolaceSquad2026"

Write-Host ""
Write-Host "  SolaceSquad Dev Server" -ForegroundColor Cyan
Write-Host "  http://127.0.0.1:8000" -ForegroundColor Green
Write-Host ""

Set-Location "$PSScriptRoot\backend"
python -m uvicorn main:app --port 8000
