# Docker Build and Deploy Script
# Run this after Docker Desktop is installed and running

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "DOCKER BUILD & DEPLOY - METHOD 3" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Step 1: Verify Docker is running
Write-Host "Step 1: Checking Docker..." -ForegroundColor Yellow
try {
    $dockerVersion = docker --version
    Write-Host "✓ Docker installed: $dockerVersion" -ForegroundColor Green
}
catch {
    Write-Host "✗ Docker is not running!" -ForegroundColor Red
    Write-Host "Please start Docker Desktop and try again." -ForegroundColor Yellow
    exit 1
}
Write-Host ""

# Step 2: Authenticate with Google Container Registry
Write-Host "Step 2: Authenticating with Google Container Registry..." -ForegroundColor Yellow
gcloud auth configure-docker
if ($LASTEXITCODE -eq 0) {
    Write-Host "✓ Authentication configured" -ForegroundColor Green
}
else {
    Write-Host "✗ Authentication failed" -ForegroundColor Red
    Write-Host "Run: gcloud auth login" -ForegroundColor Yellow
    exit 1
}
Write-Host ""

# Step 3: Build Docker image
Write-Host "Step 3: Building Docker image..." -ForegroundColor Yellow
Write-Host "This will take 5-10 minutes..." -ForegroundColor Gray
Write-Host ""

Set-Location backend

docker build -t gcr.io/abiding-idea-485817-k2/solacesquad:manual-fix .

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "✓ Docker image built successfully!" -ForegroundColor Green
}
else {
    Write-Host ""
    Write-Host "✗ Docker build failed" -ForegroundColor Red
    Set-Location ..
    exit 1
}
Write-Host ""

# Step 4: Push to Google Container Registry
Write-Host "Step 4: Pushing image to Google Container Registry..." -ForegroundColor Yellow
Write-Host "This will take 5-10 minutes depending on your internet speed..." -ForegroundColor Gray
Write-Host ""

docker push gcr.io/abiding-idea-485817-k2/solacesquad:manual-fix

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "✓ Image pushed successfully!" -ForegroundColor Green
}
else {
    Write-Host ""
    Write-Host "✗ Push failed" -ForegroundColor Red
    Set-Location ..
    exit 1
}
Write-Host ""

Set-Location ..

# Step 5: Deploy to Cloud Run
Write-Host "Step 5: Deploying to Cloud Run..." -ForegroundColor Yellow
Write-Host "This will take 2-3 minutes..." -ForegroundColor Gray
Write-Host ""

gcloud run deploy solacesquad `
    --image gcr.io/abiding-idea-485817-k2/solacesquad:manual-fix `
    --platform managed `
    --region us-central1 `
    --allow-unauthenticated `
    --project abiding-idea-485817-k2 `
    --add-cloudsql-instances=abiding-idea-485817-k2:us-central1:solacesquad-login-data1 `
    --update-secrets=DB_PASSWORD=db-password:latest `
    --update-env-vars=DB_USER=Admin, DB_NAME=solacesquad_prod, INSTANCE_CONNECTION_NAME=abiding-idea-485817-k2:us-central1:solacesquad-login-data1, BYPASS_OTP_VERIFICATION=true, GCP_PROJECT_ID=abiding-idea-485817-k2, GCP_LOCATION=us-central1, GEMINI_API_KEY=AIzaSyDzlEfQKdWv08Ar-SC4Mw5y9DlxPaZ34HA `
    --memory=1Gi `
    --cpu=1

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Green
    Write-Host "DEPLOYMENT SUCCESSFUL!" -ForegroundColor Green
    Write-Host "========================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "The call room fixes are now live!" -ForegroundColor Green
    Write-Host "Test at: https://solacesquad-sf52cc6tnq-uc.a.run.app" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Next steps:" -ForegroundColor Yellow
    Write-Host "1. Test the call room functionality" -ForegroundColor White
    Write-Host "2. Check for JavaScript errors in browser console (F12)" -ForegroundColor White
    Write-Host "3. Verify appointments scroll and sort correctly" -ForegroundColor White
}
else {
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Red
    Write-Host "DEPLOYMENT FAILED" -ForegroundColor Red
    Write-Host "========================================" -ForegroundColor Red
    Write-Host ""
    Write-Host "The image was built and pushed successfully," -ForegroundColor Yellow
    Write-Host "but Cloud Run deployment failed." -ForegroundColor Yellow
    Write-Host ""
    Write-Host "This means the infrastructure issue persists." -ForegroundColor Red
    Write-Host "You'll need to check Cloud Run logs in the Console." -ForegroundColor Yellow
}
