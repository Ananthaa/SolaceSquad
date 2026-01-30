# OpenAI Setup Script
# Run this after setting your OPENAI_API_KEY environment variable

Write-Host "=== SolaceSquad OpenAI Migration Setup ===" -ForegroundColor Cyan
Write-Host ""

# Check if OpenAI API key is set
if (-not $env:OPENAI_API_KEY) {
    Write-Host "ERROR: OPENAI_API_KEY environment variable is not set!" -ForegroundColor Red
    Write-Host ""
    Write-Host "Please set it using:" -ForegroundColor Yellow
    Write-Host '  $env:OPENAI_API_KEY="sk-your-api-key-here"' -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Or add it to your .env file:" -ForegroundColor Yellow
    Write-Host "  OPENAI_API_KEY=sk-your-api-key-here" -ForegroundColor Yellow
    Write-Host ""
    exit 1
}

Write-Host "✓ OPENAI_API_KEY is set" -ForegroundColor Green
Write-Host ""

# Install OpenAI package
Write-Host "Installing OpenAI package..." -ForegroundColor Cyan
pip install openai==1.12.0

if ($LASTEXITCODE -eq 0) {
    Write-Host "✓ OpenAI package installed successfully" -ForegroundColor Green
} else {
    Write-Host "✗ Failed to install OpenAI package" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "=== Setup Complete ===" -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Cyan
Write-Host "1. Restart your application"
Write-Host "2. Test the AI chat feature"
Write-Host "3. Monitor costs at: https://platform.openai.com/usage"
Write-Host ""
Write-Host "Estimated costs: $5-20/month for typical usage" -ForegroundColor Yellow
Write-Host ""
