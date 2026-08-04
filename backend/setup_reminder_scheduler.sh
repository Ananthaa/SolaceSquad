#!/usr/bin/env bash
# =============================================================================
# setup_reminder_scheduler.sh
# Creates a GCP Cloud Scheduler job to call the hourly appointment reminder endpoint.
#
# Prerequisites:
#   - gcloud CLI authenticated with sufficient permissions
#   - INTERNAL_CRON_SECRET set in Cloud Run environment variables
#
# Usage:
#   chmod +x setup_reminder_scheduler.sh
#   ./setup_reminder_scheduler.sh
# =============================================================================

set -euo pipefail

# ── Configuration ─────────────────────────────────────────────────────────────
PROJECT_ID="${GCP_PROJECT_ID:-your-gcp-project-id}"
REGION="${GCP_REGION:-asia-south1}"                  # Mumbai
JOB_NAME="solacesquad-hourly-appointment-reminders"
SCHEDULE="0 * * * *"                                 # Every hour on the hour
TIMEZONE="UTC"
APP_URL="${APP_BASE_URL:-https://solacesquad.in}"
CRON_SECRET="${INTERNAL_CRON_SECRET:-}"

if [[ -z "$CRON_SECRET" ]]; then
  echo "❌ ERROR: INTERNAL_CRON_SECRET environment variable must be set"
  echo "   Set it with: export INTERNAL_CRON_SECRET=your-secret-here"
  exit 1
fi

ENDPOINT="${APP_URL}/api/internal/hourly-appointment-reminder"
BODY="{\"secret\":\"${CRON_SECRET}\"}"

echo "======================================================"
echo " SolaceSquad — Hourly Appointment Reminders Setup"
echo "======================================================"
echo " Project  : ${PROJECT_ID}"
echo " Region   : ${REGION}"
echo " Job name : ${JOB_NAME}"
echo " Schedule : ${SCHEDULE}"
echo " Endpoint : ${ENDPOINT}"
echo "======================================================"

# Enable required APIs (idempotent)
echo ""
echo "➡️  Enabling Cloud Scheduler API..."
gcloud services enable cloudscheduler.googleapis.com --project="${PROJECT_ID}"

# Create or update the job
if gcloud scheduler jobs describe "${JOB_NAME}" \
    --project="${PROJECT_ID}" \
    --location="${REGION}" &>/dev/null; then
  echo ""
  echo "🔄 Job already exists — updating..."
  gcloud scheduler jobs update http "${JOB_NAME}" \
    --project="${PROJECT_ID}" \
    --location="${REGION}" \
    --schedule="${SCHEDULE}" \
    --time-zone="${TIMEZONE}" \
    --uri="${ENDPOINT}" \
    --http-method=POST \
    --headers="Content-Type=application/json" \
    --message-body="${BODY}" \
    --attempt-deadline=300s
else
  echo ""
  echo "✅ Creating new scheduler job..."
  gcloud scheduler jobs create http "${JOB_NAME}" \
    --project="${PROJECT_ID}" \
    --location="${REGION}" \
    --schedule="${SCHEDULE}" \
    --time-zone="${TIMEZONE}" \
    --uri="${ENDPOINT}" \
    --http-method=POST \
    --headers="Content-Type=application/json" \
    --message-body="${BODY}" \
    --attempt-deadline=300s
fi

echo ""
echo "======================================================"
echo " ✅ Scheduler job configured successfully!"
echo "======================================================"
