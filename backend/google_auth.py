"""
Google OAuth 2.0 — Login + Google Fit Sync
Routes:
  GET /auth/google/login                → redirect to Google consent
  GET /auth/google/callback             → exchange code, create/login user
  GET /auth/google/fit-connect          → re-request Fit scopes (for existing users)
  GET /api/google-fit/sync              → pull today's Fit data into WorkoutLog/VitalsRecord
"""

import os
import json
import secrets
import urllib.parse
from datetime import datetime, date, timedelta

import requests as _req
from fastapi import APIRouter, Request, Depends
from fastapi.responses import RedirectResponse, JSONResponse
from sqlalchemy.orm import Session

from database import get_db
from models import User, UserProfile, WorkoutLog, VitalsRecord, DailyWellnessScore

router = APIRouter()

# ── Config ────────────────────────────────────────────────────────────────────
_GOOGLE_AUTH_URL  = "https://accounts.google.com/o/oauth2/v2/auth"
_GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
_GOOGLE_USER_URL  = "https://www.googleapis.com/oauth2/v3/userinfo"
_GOOGLE_FIT_URL   = "https://fitness.googleapis.com/fitness/v1/users/me/dataset:aggregate"

_CLIENT_ID     = os.getenv("GOOGLE_CLIENT_ID", "")
_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
_BASE_URL      = os.getenv("APP_BASE_URL", "https://www.solacesquad.in").rstrip("/")

# ── Privacy: we collect ONLY name and email from Google.
# 'profile' scope is required to get the user's display name (name field).
# 'picture', 'locale', 'given_name', 'family_name' are received but deliberately NOT stored.
# Phone number is not available via Google OAuth — must be collected in-app.
_LOGIN_SCOPES = "openid email profile"
_FIT_SCOPES   = (
    "openid email profile "
    "https://www.googleapis.com/auth/fitness.activity.read "
    "https://www.googleapis.com/auth/fitness.heart_rate.read"
)


def _redirect_uri(request: Request) -> str:
    """Build redirect URI dynamically from the incoming request host.
    Fixes CSRF/session mismatch when accessed via multiple domains
    (solacesquad.com, solacesquad.in, mirror). Cloud Run sets
    X-Forwarded-Proto and X-Forwarded-Host automatically.
    """
    forwarded_host  = request.headers.get("x-forwarded-host", "")
    forwarded_proto = request.headers.get("x-forwarded-proto", "https")
    host = forwarded_host or request.headers.get("host", "")
    if host:
        host = host.split(":")[0]  # strip port if present
        return f"{forwarded_proto}://{host}/auth/google/callback"
    return f"{_BASE_URL}/auth/google/callback"  # fallback to APP_BASE_URL


def _build_auth_url(redirect_uri: str, state: str, scopes: str, include_fit: bool = False) -> str:
    chosen_scopes = _FIT_SCOPES if include_fit else _LOGIN_SCOPES
    params = {
        "client_id":     _CLIENT_ID,
        "redirect_uri":  redirect_uri,
        "response_type": "code",
        "scope":         chosen_scopes,
        "state":         state,
        "access_type":   "offline",     # get refresh_token
        "prompt":        "select_account consent",
    }
    return f"{_GOOGLE_AUTH_URL}?{urllib.parse.urlencode(params)}"


def _exchange_code(code: str, redirect_uri: str) -> dict:
    """Exchange auth code for tokens. Returns token dict or raises."""
    resp = _req.post(_GOOGLE_TOKEN_URL, data={
        "code":          code,
        "client_id":     _CLIENT_ID,
        "client_secret": _CLIENT_SECRET,
        "redirect_uri":  redirect_uri,
        "grant_type":    "authorization_code",
    }, timeout=10)
    resp.raise_for_status()
    return resp.json()


def _get_user_info(access_token: str) -> dict:
    resp = _req.get(_GOOGLE_USER_URL, headers={"Authorization": f"Bearer {access_token}"}, timeout=10)
    resp.raise_for_status()
    return resp.json()


def _refresh_access_token(refresh_token: str) -> str | None:
    """Use stored refresh_token to get a fresh access_token."""
    try:
        resp = _req.post(_GOOGLE_TOKEN_URL, data={
            "client_id":     _CLIENT_ID,
            "client_secret": _CLIENT_SECRET,
            "refresh_token": refresh_token,
            "grant_type":    "refresh_token",
        }, timeout=10)
        resp.raise_for_status()
        return resp.json().get("access_token")
    except Exception as e:
        print(f"[GoogleFit] Token refresh failed: {e}")
        return None


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("/auth/google/login")
def google_login(request: Request):
    """Start the Google OAuth flow (login + optional Fit scopes)."""
    if not _CLIENT_ID:
        return RedirectResponse("/login?error=Google+login+not+configured+yet")

    include_fit = request.query_params.get("scope") == "fit"
    role = request.query_params.get("role")  # No default!
    if role not in ("user", "consultant"):
        role = None

    state = secrets.token_urlsafe(16)
    request.session["google_oauth_state"] = state
    request.session["google_oauth_include_fit"] = include_fit
    if role:
        request.session["google_oauth_role"] = role  # Store role for callback
    else:
        request.session.pop("google_oauth_role", None)

    redirect_uri = _redirect_uri(request)
    auth_url = _build_auth_url(redirect_uri, state, _LOGIN_SCOPES, include_fit=include_fit)
    print(f"[GoogleAuth] Redirecting to Google. include_fit={include_fit}, role={role}")
    return RedirectResponse(auth_url)


@router.get("/auth/google/callback")
def google_callback(request: Request, db: Session = Depends(get_db)):
    """Handle Google's redirect back. Create or log in the user."""
    code  = request.query_params.get("code")
    state = request.query_params.get("state")
    error = request.query_params.get("error")

    # ── Error from Google ──────────────────────────────────────────────────────
    if error:
        print(f"[GoogleAuth] Google returned error: {error}")
        return RedirectResponse(f"/login?error=Google+login+cancelled")

    # ── CSRF state check ───────────────────────────────────────────────────────
    expected_state = request.session.pop("google_oauth_state", None)
    include_fit    = request.session.pop("google_oauth_include_fit", False)
    signup_role    = request.session.pop("google_oauth_role", None)  # set during signup flow

    if not state or state != expected_state:
        print(f"[GoogleAuth] State mismatch. Expected={expected_state}, Got={state}")
        return RedirectResponse("/login?error=Invalid+OAuth+state")

    if not code:
        return RedirectResponse("/login?error=No+authorization+code+received")

    # ── Exchange code ──────────────────────────────────────────────────────────
    try:
        redirect_uri = _redirect_uri(request)
        tokens   = _exchange_code(code, redirect_uri)
        user_info = _get_user_info(tokens["access_token"])
    except Exception as e:
        print(f"[GoogleAuth] Token exchange failed: {e}")
        return RedirectResponse("/login?error=Google+authentication+failed")

    # ── Extract ONLY name, email, and Google ID. All other fields (picture,
    # locale, given_name, family_name, phone) are intentionally not read or stored.
    google_id     = user_info.get("sub")                        # Google's unique user ID
    email         = user_info.get("email", "").lower().strip()  # Verified by Google
    name          = user_info.get("name", email.split("@")[0])  # Display name only
    refresh_token = tokens.get("refresh_token")                 # Only present on first auth

    if not email:
        return RedirectResponse("/login?error=Could+not+get+email+from+Google")

    # ── Find or create user ────────────────────────────────────────────────────
    user = db.query(User).filter(User.email == email).first()
    is_new_user = user is None

    if user:
        # ── Existing user — check if signup role matches their actual account type ──
        if signup_role and signup_role in ("user", "consultant") and user.user_type != signup_role:
            existing_label = "Wellbeing Consultant" if user.user_type == "consultant" else "User"
            return RedirectResponse(
                f"/signup?role_mismatch=1&existing_role={user.user_type}"
                f"&msg=This+email+is+already+registered+as+a+{existing_label.replace(' ', '+')}."
                f"+Please+sign+in+to+your+{existing_label.replace(' ', '+')}+account+instead.",
                status_code=302
            )
        # Same role or no role specified — update Google ID and refresh token if needed
        if not user.google_id:
            user.google_id = google_id
        if refresh_token:
            user.google_fit_refresh_token = refresh_token
            # Auto-sync to FitnessIntegration for Sync-X
            try:
                from fitness_plugins.registry import store_token
                store_token(db, user.id, "google_health", refresh_token)
            except Exception as _tok_err:
                print(f"[GoogleAuth] Error saving FitnessIntegration token: {_tok_err}")
        if not user.oauth_provider:
            user.oauth_provider = "google"
        print(f"[GoogleAuth] Logged in existing user: {email}")
    else:
        # New user — use role from signup flow (default to 'user')
        user_type = signup_role if signup_role in ("user", "consultant") else "user"
        user = User(
            email=email,
            name=name,
            password_hash=None,          # Google users have no password
            oauth_provider="google",
            google_id=google_id,
            google_fit_refresh_token=refresh_token if include_fit else None,
            email_verified=True,         # Google already verified the email
            is_active=True,
            user_type=user_type,
        )
        db.add(user)
        db.flush()  # get user.id before creating profile

        # Auto-sync to FitnessIntegration for Sync-X
        if refresh_token and include_fit:
            try:
                from fitness_plugins.registry import store_token
                store_token(db, user.id, "google_health", refresh_token)
            except Exception as _tok_err:
                print(f"[GoogleAuth] Error saving FitnessIntegration token: {_tok_err}")

        # Auto-populate UserProfile with Google name/email
        first_name = name.split()[0] if name else name
        profile = UserProfile(
            user_id=user.id,
            full_name=name,
            preferred_name=first_name,
            contact_email=email,
        )
        db.add(profile)
        print(f"[GoogleAuth] Created new {user_type} via Google: {email}")

    user.update_last_login()
    if not user.first_login:
        user.first_login = datetime.utcnow()
    db.commit()
    db.refresh(user)

    # ── Enforce User-Only login for Mobile App ──────────────────────────────
    ua = request.headers.get("user-agent", "")
    is_mobile_app = "SolaceSquadApp" in ua or request.session.get("is_mobile_app") == "1"
    if is_mobile_app and user.user_type != "user":
        request.session.clear()
        err_msg = "The mobile app is for user accounts only. Consultants and administrators, please sign in via www.solacesquad.com."
        return RedirectResponse(f"/login?error={urllib.parse.quote(err_msg)}", status_code=303)

    # ── Set session (same keys as email/password login) ────────────────────────
    request.session["user_id"]   = user.id
    request.session["user_type"] = user.user_type
    request.session["user_email"]= user.email
    request.session["user_name"] = user.name

    next_url = request.session.pop("next_url", None)
    if not next_url:
        if user.user_type == "consultant":
            # New consultants go to onboarding; existing to their dashboard
            next_url = "/consultant/onboarding" if is_new_user else "/consultant"
        elif user.user_type == "admin":
            next_url = "/admin"
        else:
            next_url = "/app"

    # Google OAuth does not provide phone numbers, so new/existing users without phone must be prompted to update it.
    if not user.phone_number:
        request.session["google_signup_next_url"] = next_url
        print(f"[GoogleAuth] Redirecting user {user.id} to verify phone number.")
        return RedirectResponse("/auth/update-phone", status_code=302)

    print(f"[GoogleAuth] Session set for user {user.id} (type={user.user_type}, new={is_new_user}). Redirecting to {next_url}")
    return RedirectResponse(next_url, status_code=302)


@router.get("/auth/google/fit-connect")
def google_fit_connect(request: Request, db: Session = Depends(get_db)):
    """Let an existing logged-in user connect Google Fit (requests Fit scopes)."""
    user_id = request.session.get("user_id")
    if not user_id:
        return RedirectResponse("/login?next_url=/app")

    from subscription_routes import get_active_subscription
    sub = get_active_subscription(user_id, db)
    if not sub or not sub.plan or sub.plan.is_free:
        return RedirectResponse("/app/profile?error=Google+Fit+sync+requires+a+paid+plan")

    state = secrets.token_urlsafe(16)
    request.session["google_oauth_state"]      = state
    request.session["google_oauth_include_fit"] = True
    request.session["next_url"]                = "/app/profile"  # return to profile after auth

    redirect_uri = _redirect_uri(request)
    auth_url = _build_auth_url(redirect_uri, state, _FIT_SCOPES, include_fit=True)
    return RedirectResponse(auth_url)


# ── Google Fit Activity type → app workout type map ──────────────────────────
_FIT_ACTIVITY_MAP = {
    1: "Cycling", 2: "Cycling", 3: "Cycling",        # biking variants
    9: "Cycling", 108: "Cycling", 109: "Cycling",     # more cycling
    110: "Cycling", 111: "Cycling", 112: "Cycling",
    54: "Running", 55: "Running", 56: "Running",       # running variants
    57: "Running", 77: "Running", 89: "Running",
    94: "Walking", 95: "Walking", 96: "Walking",       # walking variants
    97: "Walking", 90: "Walking",
    83: "Swimming", 84: "Swimming", 82: "Swimming",    # swimming
    52: "Rowing",  53: "Rowing",  49: "Rowing",        # rowing
    80: "Strength", 99: "Strength", 39: "Strength",   # strength/weights
    113: "Boxing",
    102: "Yoga",  47: "Pilates",
    28: "HIIT",   8: "HIIT",
    114: "Dancing",
    115: "Climbing", 51: "Climbing",
    42: "Meditation",
    44: "Other",
}
_FIT_SESSIONS_URL = "https://fitness.googleapis.com/fitness/v1/users/me/sessions"


# ── Google Fit Sync ───────────────────────────────────────────────────────────

@router.get("/api/google-fit/sync")
def sync_google_fit(request: Request, db: Session = Depends(get_db)):
    """Sync today's Google Fit data — individual workout sessions + step summary."""
    user_id = request.session.get("user_id")
    if not user_id:
        return {"error": "Not logged in"}, 401

    from subscription_routes import get_active_subscription
    sub = get_active_subscription(user_id, db)
    if not sub or not sub.plan or sub.plan.is_free:
        from fastapi import Response
        return JSONResponse({"error": "Google Fit sync is only available on the White plan and above. Upgrade your plan to unlock.", "success": False}, status_code=403)

    user = db.get(User, user_id)
    if not user or not user.google_fit_refresh_token:
        return {"error": "Google Fit not connected", "connected": False}

    access_token = _refresh_access_token(user.google_fit_refresh_token)
    if not access_token:
        return {"error": "Could not refresh Google Fit token. Please reconnect.", "connected": False}

    today    = date.today()
    start_ms = int(datetime.combine(today, datetime.min.time()).timestamp() * 1000)
    end_ms   = int(datetime.combine(today + timedelta(days=1), datetime.min.time()).timestamp() * 1000)
    headers  = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}

    # ── 1. Fetch individual workout SESSIONS ───────────────────────────────────
    sessions_synced = []
    try:
        start_iso = datetime.utcfromtimestamp(start_ms / 1000).strftime("%Y-%m-%dT%H:%M:%S.000Z")
        end_iso   = datetime.utcfromtimestamp(end_ms   / 1000).strftime("%Y-%m-%dT%H:%M:%S.000Z")
        sess_resp = _req.get(
            _FIT_SESSIONS_URL,
            headers=headers,
            params={"startTime": start_iso, "endTime": end_iso},
            timeout=15,
        )
        if sess_resp.status_code == 403:
            user.google_fit_refresh_token = None
            db.commit()
            return {
                "error": "Google Fit not authorized. Please click 'Connect Google Fit' to grant Fitness permissions.",
                "connected": False,
                "need_reconnect": True,
            }
        sess_resp.raise_for_status()

        for session in sess_resp.json().get("session", []):
            activity_type = session.get("activityType", 44)
            app_type      = _FIT_ACTIVITY_MAP.get(activity_type, "Other")
            sess_start_ms = int(session.get("startTimeMillis") or 0)
            sess_end_ms   = int(session.get("endTimeMillis")   or 0)
            duration_min  = max(1, round((sess_end_ms - sess_start_ms) / 60000)) if sess_start_ms else 0
            session_name  = (session.get("name") or "").strip() or app_type
            notes         = f"Synced from Google Fit: {session_name}"

            # Skip very short sessions (< 2 min) — likely noise
            if duration_min < 2:
                continue

            # Avoid duplicates for same type + same date + same session name
            existing = db.query(WorkoutLog).filter(
                WorkoutLog.user_id      == user_id,
                WorkoutLog.log_date     == today,
                WorkoutLog.workout_type == app_type,
                WorkoutLog.notes.like(f"%{session_name}%"),
            ).first()

            if not existing:
                db.add(WorkoutLog(
                    user_id      = user_id,
                    log_date     = today,
                    workout_type = app_type,
                    duration_min = duration_min,
                    step_count   = 0,
                    calories     = 0,
                    notes        = notes,
                ))
                sessions_synced.append({"type": app_type, "duration_min": duration_min, "name": session_name})

    except Exception as e:
        print(f"[GoogleFit] Sessions API error (non-fatal): {e}")

    # ── 2. Fetch aggregate steps / calories / heart rate ──────────────────────
    steps = 0; calories = 0; active_min = 0; heart_rate = None
    try:
        agg_resp = _req.post(
            _GOOGLE_FIT_URL,
            headers=headers,
            json={
                "aggregateBy": [
                    {"dataTypeName": "com.google.step_count.delta"},
                    {"dataTypeName": "com.google.calories.expended"},
                    {"dataTypeName": "com.google.active_minutes"},
                    {"dataTypeName": "com.google.heart_rate.bpm"},
                ],
                "bucketByTime":   {"durationMillis": 86400000},
                "startTimeMillis": start_ms,
                "endTimeMillis":   end_ms,
            },
            timeout=15,
        )
        agg_resp.raise_for_status()
        for bucket in agg_resp.json().get("bucket", []):
            for dataset in bucket.get("dataset", []):
                dtype = dataset.get("dataSourceId", "")
                for point in dataset.get("point", []):
                    val = point.get("value", [{}])[0]
                    if "step_count"    in dtype: steps      += val.get("intVal", 0)
                    elif "calories"    in dtype: calories   += int(val.get("fpVal", 0))
                    elif "active_min"  in dtype: active_min += val.get("intVal", 0)
                    elif "heart_rate"  in dtype: heart_rate  = int(val.get("fpVal", 0))
    except Exception as e:
        print(f"[GoogleFit] Aggregate API error (non-fatal): {e}")

    # ── 3. Upsert daily steps summary (Walking entry) ─────────────────────────
    if steps > 0:
        step_notes = f"Google Fit daily steps: {steps:,} steps synced"
        summary = db.query(WorkoutLog).filter(
            WorkoutLog.user_id      == user_id,
            WorkoutLog.log_date     == today,
            WorkoutLog.workout_type == "Walking",
            WorkoutLog.notes.like("%Google Fit daily steps%"),
        ).first()
        if summary:
            summary.step_count   = steps
            summary.calories     = calories if calories > 0 else summary.calories
            summary.duration_min = active_min or summary.duration_min
            summary.notes        = step_notes
        else:
            db.add(WorkoutLog(
                user_id      = user_id,
                log_date     = today,
                workout_type = "Walking",
                step_count   = steps,
                calories     = calories,
                duration_min = active_min,
                notes        = step_notes,
            ))

    # ── 4. Update VitalsRecord heart rate if available ────────────────────────
    if heart_rate:
        latest_vital = db.query(VitalsRecord).filter(
            VitalsRecord.user_id == user_id
        ).order_by(VitalsRecord.timestamp.desc()).first()
        if latest_vital:
            latest_vital.heart_rate = heart_rate

    db.commit()

    # Recalculate daily wellness/lifestyle score after sync
    try:
        from main import compute_and_save_wellness
        compute_and_save_wellness(user_id, db, for_date=today)
    except Exception as e:
        print(f"[GoogleFit] Wellness score recalculation failed: {e}")

    print(f"[GoogleFit] user={user_id}: sessions={len(sessions_synced)}, steps={steps}, cal={calories}, min={active_min}, hr={heart_rate}")

    return {
        "success": True,
        "synced": {
            "steps":         steps,
            "calories":      calories,
            "active_min":    active_min,
            "heart_rate":    heart_rate,
            "date":          str(today),
            "sessions":      sessions_synced,
            "session_count": len(sessions_synced),
        }
    }


