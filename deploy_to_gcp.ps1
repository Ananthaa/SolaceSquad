# Quick GCP Deployment Script
# Run this to deploy SolaceSquad to GCP in one go
# Make sure you've completed the prerequisites first!

Write-Host "=== SolaceSquad GCP Deployment ===" -ForegroundColor Cyan
Write-Host ""

# Configuration
$PROJECT_ID = Read-Host "Enter your GCP Project ID (e.g., solacesquad-prod)"
$REGION = "us-central1"
$DB_PASSWORD = Read-Host "Enter database password" -AsSecureString
$SESSION_SECRET = Read-Host "Enter session secret key" -AsSecureString

Write-Host ""
Write-Host "Configuration:" -ForegroundColor Yellow
Write-Host "  Project ID: $PROJECT_ID"
Write-Host "  Region: $REGION"
Write-Host ""

$confirm = Read-Host "Continue with deployment? (yes/no)"
if ($confirm -ne "yes") {
    Write-Host "Deployment cancelled" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "Step 1: Setting up GCP project..." -ForegroundColor Cyan
gcloud config set project $PROJECT_ID

Write-Host ""
Write-Host "Step 2: Enabling required APIs..." -ForegroundColor Cyan
gcloud services enable `
    run.googleapis.com `
    sql-component.googleapis.com `
    sqladmin.googleapis.com `
    aiplatform.googleapis.com `
    storage.googleapis.com `
    cloudbuild.googleapis.com `
    secretmanager.googleapis.com

Write-Host ""
Write-Host "Step 3: Creating Cloud SQL instance..." -ForegroundColor Cyan
Write-Host "(This takes 5-10 minutes...)" -ForegroundColor Yellow

$dbPasswordPlain = [Runtime.InteropServices.Marshal]::PtrToStringAuto(
    [Runtime.InteropServices.Marshal]::SecureStringToBSTR($DB_PASSWORD)
)

gcloud sql instances create solacesquad-db `
    --database-version=POSTGRES_15 `
    --tier=db-f1-micro `
    --region=$REGION `
    --root-password=$dbPasswordPlain `
    --storage-type=SSD `
    --storage-size=10GB `
    --backup-start-time=03:00

Write-Host ""
Write-Host "Step 4: Creating database and user..." -ForegroundColor Cyan
gcloud sql databases create solacesquad --instance=solacesquad-db
gcloud sql users create solacesquad_user `
    --instance=solacesquad-db `
    --password=$dbPasswordPlain

Write-Host ""
Write-Host "Step 5: Storing secrets..." -ForegroundColor Cyan
echo -n $dbPasswordPlain | gcloud secrets create db-password --data-file=-

$sessionSecretPlain = [Runtime.InteropServices.Marshal]::PtrToStringAuto(
    [Runtime.InteropServices.Marshal]::SecureStringToBSTR($SESSION_SECRET)
)
echo -n $sessionSecretPlain | gcloud secrets create session-secret --data-file=-

Write-Host ""
Write-Host "Step 6: Deploying to Cloud Run..." -ForegroundColor Cyan
Write-Host "(This takes 5-10 minutes...)" -ForegroundColor Yellow

cd backend

gcloud run deploy solacesquad `
    --source . `
    --platform managed `
    --region $REGION `
    --allow-unauthenticated `
    --set-env-vars="GCP_PROJECT_ID=$PROJECT_ID,GCP_LOCATION=$REGION,ENVIRONMENT=production" `
    --add-cloudsql-instances="${PROJECT_ID}:${REGION}:solacesquad-db" `
    --memory=512Mi `
    --cpu=1 `
    --min-instances=0 `
    --max-instances=10 `
    --timeout=300

Write-Host ""
Write-Host "Step 7: Getting service URL..." -ForegroundColor Cyan
$SERVICE_URL = gcloud run services describe solacesquad `
    --region=$REGION `
    --format="value(status.url)"

Write-Host ""
Write-Host "=== Deployment Complete! ===" -ForegroundColor Green
Write-Host ""
Write-Host "Your app is live at:" -ForegroundColor Cyan
Write-Host "  $SERVICE_URL" -ForegroundColor Yellow
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Cyan
Write-Host "1. Set up Firebase (see GCP_DEPLOYMENT_GUIDE.md Phase 3)"
Write-Host "2. Run database migrations"
Write-Host "3. Test your deployment"
Write-Host "4. Configure custom domain (optional)"
Write-Host ""
Write-Host "View logs:" -ForegroundColor Cyan
Write-Host "  gcloud run services logs read solacesquad --region=$REGION" -ForegroundColor Yellow
Write-Host ""
Write-Host "Monitor costs:" -ForegroundColor Cyan
Write-Host "  https://console.cloud.google.com/billing" -ForegroundColor Yellow
Write-Host ""
