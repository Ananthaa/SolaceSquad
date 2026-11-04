# SolaceSquad Production Release Checklist & Quality Assurance SOP

Before submitting any build to Google Cloud Run or App Store Connect / Play Store, run through this checklist to prevent regressions.

---

## 1. Automated Pre-Deployment Verification

Always run the automated verification suite before triggering `gcloud builds submit`:

```powershell
python scripts/pre_deploy_test.py
```

This verifies:
- [x] **Guideline 4.8 (Login Services)**: Google Login button and panel are completely excluded when accessed via iOS/iPadOS user-agents or inside the WKWebView app.
- [x] **Guideline 1.4.1 (Physical Harm / Medical Exemption)**: Medical disclaimers ("Not a Medical Device", "Always seek a doctor’s advice") are strictly present on the pre-scan modal, during scanning, and on the post-scan results card.
- [x] **No Clinical Diagnostic Claims**: Verifies that user-facing labels say "Wellness Guide" and "Wellness Synthesis" (exempt under FDA General Wellness Policy Section V) rather than "Clinical".
- [x] **Navigation & Route Integrity**: Verifies core routes and model imports (`ConsultantWebinar`, etc.) to prevent 500 server errors.

---

## 2. Manual Pre-Release Sanity Checks

### A. Authentication & Apple App Store Exemption (Guideline 4.8)
- [ ] On an iOS device or Safari with User-Agent set to iPad/iPhone:
  - Visit `/login` -> Verify **only** Email/Password and Mobile Phone OTP are shown. Google Login must **not** appear.
  - Visit `/signup` -> Verify only Email and Mobile OTP options are shown.
- [ ] On a Desktop browser (Chrome / Edge / Firefox):
  - Visit `/login` -> Verify Google Login tab and button are visible and operational.

### B. Vitals Scanner & Wellness Disclaimers (Guideline 1.4.1)
- [ ] Navigate to `/app/vitals`:
  - Verify the **Before You Scan** modal pops up with the mandatory amber warning:
    > "⚠️ **Not a Medical Device**: Results are estimates intended for general fitness and wellness purposes only. They are not intended for clinical use, medical diagnosis, or treatment. Always seek a doctor’s advice in addition to using this app and before making any medical decisions."
  - Click **Continue Scanning** -> Verify camera stream initializes MediaPipe Face Mesh mesh landmarks.
  - Complete a 45-second scan -> Verify results card displays the non-medical disclaimer banner above the metrics.
  - Verify the guide button reads **Wellness Guide**.

### C. Consultant & Admin Interfaces
- [ ] Log in as a Consultant -> Verify `/consultant/webinars` loads without 500 errors and displays the Webinar Library.
- [ ] Verify Bookings / Reschedule modals load properly without JavaScript errors.

---

## 3. Deployment Protocol (Production)

Deployments to Production must always be executed using **sg@solacesquad.com**:

```powershell
# 1. Switch to production branch
git checkout prod-deploy-appointments

# 2. Run automated test
python scripts/pre_deploy_test.py

# 3. Ensure sg@solacesquad.com is the active GCP identity
$env:CLOUDSDK_PYTHON = "python"
gcloud config set account sg@solacesquad.com
gcloud config set project abiding-idea-485817-k2

# 4. Commit and submit Cloud Build
git add .
git commit -m "fix(release): <release notes>"
git push origin prod-deploy-appointments
gcloud builds submit --config=cloudbuild.yaml .

# 5. Live Verification
python scripts/pre_deploy_test.py --live
```
