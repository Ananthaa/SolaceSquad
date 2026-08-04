"""
Fitbit OAuth 2.0 — Connect + Sync
Routes:
  GET /auth/fitbit/connect    → redirect to Fitbit consent page
  GET /auth/fitbit/callback   → exchange code, store refresh token
  GET /api/fitbit/sync        → pull today's activity + HR data into WorkoutLog
"""

import os
import base64
import secrets
import urllib.parse
from datetime import date, datetime

import requests as _req
from fastapi import APIRouter, Request, Depends
from fastapi.responses import RedirectResponse, JSONResponse
from sqlalchemy.orm import Session

from database import get_db
from models import User, WorkoutLog, VitalsRecord

router = APIRouter()

# ── Config ─────────────────────────────────────────────────────────────────────
_FITBIT_AUTH_URL  = "https://www.fitbit.com/oauth2/authorize"
_FITBIT_TOKEN_URL = "https://api.fitbit.com/oauth2/token"
_FITBIT_API_BASE  = "https://api.fitbit.com/1/user/-"

_CLIENT_ID     = os.getenv("FITBIT_CLIENT_ID", "")
_CLIENT_SECRET = os.getenv("FITBIT_CLIENT_SECRET", "")
_BASE_URL      = os.getenv("APP_BASE_URL", "https://www.solacesquad.in").rstrip("/")

_SCOPES = "activity heartrate profile"
_REDIRECT_URI = f"{_BASE_URL}/auth/fitbit/callback"


def _is_configured() -> bool:
    return bool(_CLIENT_ID and _CLIENT_SECRET)


def _basic_auth_header() -> str:
    """Fitbit token endpoint requires Basic auth with client_id:client_secret."""
    creds = f"{_CLIENT_ID}:{_CLIENT_SECRET}".encode()
    return "Basic " + base64.b64encode(creds).decode()


def _refresh_access_token(refresh_token: str) -> str | None:
    """Exchange refresh token for a new access token. Returns access token or None."""
    try:
        resp = _req.post(
            _FITBIT_TOKEN_URL,
            headers={
                "Authorization": _basic_auth_header(),
                "Content-Type": "application/x-www-form-urlencoded",
            },
            data={
                "grant_type":    "refresh_token",
                "refresh_token": refresh_token,
            },
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json().get("access_token")
    except Exception as e:
        print(f"[Fitbit] Token refresh failed: {e}")
        return None


# ── Connect ────────────────────────────────────────────────────────────────────

@router.get("/auth/fitbit/connect")
def fitbit_connect(request: Request):
    """Redirect logged-in user to Fitbit consent page."""
    if not _is_configured():
        return RedirectResponse("/app/profile?error=fitbit_not_configured")

    user_id = request.session.get("user_id")
    if not user_id:
        return RedirectResponse("/login?next_url=/app/profile")

    state = secrets.token_urlsafe(16)
    request.session["fitbit_oauth_state"] = state

    params = {
        "client_id":     _CLIENT_ID,
        "redirect_uri":  _REDIRECT_URI,
        "response_type": "code",
        "scope":         _SCOPES,
        "state":         state,
    }
    auth_url = f"{_FITBIT_AUTH_URL}?{urllib.parse.urlencode(params)}"
    return RedirectResponse(auth_url)


# ── Callback ───────────────────────────────────────────────────────────────────

@router.get("/auth/fitbit/callback")
def fitbit_callback(request: Request, db: Session = Depends(get_db)):
    """Exchange code for tokens and store fitbit_refresh_token."""
    user_id = request.session.get("user_id")
    if not user_id:
        return RedirectResponse("/login")

    code  = request.query_params.get("code")
    state = request.query_params.get("state")

    if state != request.session.pop("fitbit_oauth_state", None):
        return RedirectResponse("/app/profile?error=fitbit_state_mismatch")

    if not code:
        return RedirectResponse("/app/profile?error=fitbit_no_code")

    # Exchange code for tokens
    try:
        resp = _req.post(
            _FITBIT_TOKEN_URL,
            headers={
                "Authorization": _basic_auth_header(),
                "Content-Type": "application/x-www-form-urlencoded",
            },
            data={
                "code":         code,
                "grant_type":   "authorization_code",
                "redirect_uri": _REDIRECT_URI,
            },
            timeout=15,
        )
        resp.raise_for_status()
        tokens = resp.json()
    except Exception as e:
        print(f"[Fitbit] Code exchange failed: {e}")
        return RedirectResponse("/app/profile?error=fitbit_auth_failed")

    refresh_token = tokens.get("refresh_token")
    if not refresh_token:
        return RedirectResponse("/app/profile?error=fitbit_no_refresh_token")

    user = db.get(User, user_id)
    if not user:
        return RedirectResponse("/login")

    user.fitbit_refresh_token = refresh_token
    db.commit()
    print(f"[Fitbit] Connected for user {user_id}")

    return RedirectResponse("/app/profile?fitbit_connected=1")


# ── Sync ───────────────────────────────────────────────────────────────────────

@router.get("/api/fitbit/sync")
def sync_fitbit(request: Request, db: Session = Depends(get_db)):
    """Pull today's Fitbit activity data into WorkoutLog and VitalsRecord."""
    user_id = request.session.get("user_id")
    if not user_id:
        return {"error": "Not logged in"}

    user = db.get(User, user_id)
    if not user or not user.fitbit_refresh_token:
        return {"error": "Fitbit not connected", "connected": False}

    access_token = _refresh_access_token(user.fitbit_refresh_token)
    if not access_token:
        user.fitbit_refresh_token = None
        db.commit()
        return {"error": "Could not refresh Fitbit token. Please reconnect.", "connected": False, "need_reconnect": True}

    headers = {"Authorization": f"Bearer {access_token}"}
    today_str = date.today().isoformat()

    # ── Activities summary ─────────────────────────────────────────────────────
    steps = 0; calories = 0; active_min = 0
    try:
        acts = _req.get(f"{_FITBIT_API_BASE}/activities/date/{today_str}.json", headers=headers, timeout=15)
        acts.raise_for_status()
        summary = acts.json().get("summary", {})
        steps      = summary.get("steps", 0)
        calories   = int(summary.get("caloriesOut", 0))
        active_min = (summary.get("veryActiveMinutes", 0) +
                      summary.get("fairlyActiveMinutes", 0))
    except Exception as e:
        print(f"[Fitbit] Activities call failed: {e}")

    # ── Heart rate ─────────────────────────────────────────────────────────────
    heart_rate = None
    try:
        hr_resp = _req.get(f"{_FITBIT_API_BASE}/activities/heart/date/{today_str}/1d.json", headers=headers, timeout=15)
        hr_resp.raise_for_status()
        hr_data = hr_resp.json()
        resting = hr_data.get("activities-heart", [{}])[0].get("value", {}).get("restingHeartRate")
        if resting:
            heart_rate = int(resting)
    except Exception as e:
        print(f"[Fitbit] Heart rate call failed: {e}")

    # ── Upsert WorkoutLog ──────────────────────────────────────────────────────
    today = date.today()
    workout = db.query(WorkoutLog).filter(
        WorkoutLog.user_id == user_id,
        WorkoutLog.log_date == today,
        WorkoutLog.workout_type == "Fitbit",
    ).first()

    if workout:
        workout.step_count   = steps
        workout.calories     = calories
        workout.duration_min = active_min
    else:
        workout = WorkoutLog(
            user_id=user_id,
            log_date=today,
            workout_type="Fitbit",
            step_count=steps,
            calories=calories,
            duration_min=active_min,
        )
        db.add(workout)

    # ── Update heart rate in latest VitalsRecord ───────────────────────────────
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
        print(f"[Fitbit] Wellness score recalculation failed: {e}")

    print(f"[Fitbit] Synced for user {user_id}: steps={steps}, cal={calories}, min={active_min}, hr={heart_rate}")

    return {
        "success": True,
        "synced": {
            "steps":      steps,
            "calories":   calories,
            "active_min": active_min,
            "heart_rate": heart_rate,
            "date":       str(today),
        }
    }
