"""
Strava OAuth 2.0 — Connect + Sync
Routes:
  GET /auth/strava/connect    → redirect to Strava consent page
  GET /auth/strava/callback   → exchange code, store refresh token
  GET /api/strava/sync        → pull recent activities into WorkoutLog
"""

import os
import secrets
import urllib.parse
from datetime import date, datetime, timezone

import requests as _req
from fastapi import APIRouter, Request, Depends
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from database import get_db
from models import User, WorkoutLog

router = APIRouter()

# ── Config ─────────────────────────────────────────────────────────────────────
_STRAVA_AUTH_URL  = "https://www.strava.com/oauth/authorize"
_STRAVA_TOKEN_URL = "https://www.strava.com/oauth/token"
_STRAVA_API_BASE  = "https://www.strava.com/api/v3"

_CLIENT_ID     = os.getenv("STRAVA_CLIENT_ID", "")
_CLIENT_SECRET = os.getenv("STRAVA_CLIENT_SECRET", "")
_BASE_URL      = os.getenv("APP_BASE_URL", "https://www.solacesquad.in").rstrip("/")

_REDIRECT_URI = f"{_BASE_URL}/auth/strava/callback"

# Strava sport type → our workout type mapping
_STRAVA_TYPE_MAP = {
    "Run":         "Running",
    "Walk":        "Walking",
    "Ride":        "Cycling",
    "Swim":        "Swimming",
    "WeightTraining": "Strength",
    "Yoga":        "Yoga",
    "Workout":     "HIIT",
    "Hike":        "Walking",
    "Rowing":      "Rowing",
    "Boxing":      "Boxing",
    "Dance":       "Dancing",
    "Pilates":     "Pilates",
    "Meditation":  "Meditation",
}


def _is_configured() -> bool:
    return bool(_CLIENT_ID and _CLIENT_SECRET)


def _refresh_access_token(refresh_token: str) -> str | None:
    """Exchange Strava refresh token for a new access token."""
    try:
        resp = _req.post(
            _STRAVA_TOKEN_URL,
            data={
                "client_id":     _CLIENT_ID,
                "client_secret": _CLIENT_SECRET,
                "grant_type":    "refresh_token",
                "refresh_token": refresh_token,
            },
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json().get("access_token")
    except Exception as e:
        print(f"[Strava] Token refresh failed: {e}")
        return None


# ── Connect ────────────────────────────────────────────────────────────────────

@router.get("/auth/strava/connect")
def strava_connect(request: Request):
    """Redirect logged-in user to Strava consent page."""
    if not _is_configured():
        return RedirectResponse("/app/profile?error=strava_not_configured")

    user_id = request.session.get("user_id")
    if not user_id:
        return RedirectResponse("/login?next_url=/app/profile")

    state = secrets.token_urlsafe(16)
    request.session["strava_oauth_state"] = state

    params = {
        "client_id":     _CLIENT_ID,
        "redirect_uri":  _REDIRECT_URI,
        "response_type": "code",
        "approval_prompt": "auto",
        "scope":         "activity:read_all",
        "state":         state,
    }
    auth_url = f"{_STRAVA_AUTH_URL}?{urllib.parse.urlencode(params)}"
    return RedirectResponse(auth_url)


# ── Callback ───────────────────────────────────────────────────────────────────

@router.get("/auth/strava/callback")
def strava_callback(request: Request, db: Session = Depends(get_db)):
    """Exchange code for tokens and store strava_refresh_token."""
    user_id = request.session.get("user_id")
    if not user_id:
        return RedirectResponse("/login")

    # Check for access_denied
    if request.query_params.get("error") == "access_denied":
        return RedirectResponse("/app/profile?error=strava_denied")

    code  = request.query_params.get("code")
    state = request.query_params.get("state")

    if state != request.session.pop("strava_oauth_state", None):
        return RedirectResponse("/app/profile?error=strava_state_mismatch")

    if not code:
        return RedirectResponse("/app/profile?error=strava_no_code")

    # Exchange code for tokens
    try:
        resp = _req.post(
            _STRAVA_TOKEN_URL,
            data={
                "client_id":     _CLIENT_ID,
                "client_secret": _CLIENT_SECRET,
                "code":          code,
                "grant_type":    "authorization_code",
            },
            timeout=15,
        )
        resp.raise_for_status()
        tokens = resp.json()
    except Exception as e:
        print(f"[Strava] Code exchange failed: {e}")
        return RedirectResponse("/app/profile?error=strava_auth_failed")

    refresh_token = tokens.get("refresh_token")
    if not refresh_token:
        return RedirectResponse("/app/profile?error=strava_no_refresh_token")

    user = db.get(User, user_id)
    if not user:
        return RedirectResponse("/login")

    user.strava_refresh_token = refresh_token
    db.commit()
    print(f"[Strava] Connected for user {user_id}")

    return RedirectResponse("/app/profile?strava_connected=1")


# ── Sync ───────────────────────────────────────────────────────────────────────

@router.get("/api/strava/sync")
def sync_strava(request: Request, db: Session = Depends(get_db)):
    """Pull the last 7 days of Strava activities into WorkoutLog."""
    user_id = request.session.get("user_id")
    if not user_id:
        return {"error": "Not logged in"}

    user = db.get(User, user_id)
    if not user or not user.strava_refresh_token:
        return {"error": "Strava not connected", "connected": False}

    access_token = _refresh_access_token(user.strava_refresh_token)
    if not access_token:
        user.strava_refresh_token = None
        db.commit()
        return {"error": "Could not refresh Strava token. Please reconnect.", "connected": False, "need_reconnect": True}

    # Fetch last 7 days of activities
    from datetime import timedelta
    after_ts = int((datetime.now(timezone.utc) - timedelta(days=7)).timestamp())
    try:
        resp = _req.get(
            f"{_STRAVA_API_BASE}/athlete/activities",
            headers={"Authorization": f"Bearer {access_token}"},
            params={"after": after_ts, "per_page": 30},
            timeout=15,
        )
        resp.raise_for_status()
        activities = resp.json()
    except Exception as e:
        print(f"[Strava] Activities fetch failed: {e}")
        return {"error": f"Strava API error: {str(e)}"}

    synced_count = 0
    for act in activities:
        act_date = date.fromisoformat(act["start_date_local"][:10])
        strava_type = act.get("sport_type") or act.get("type", "Workout")
        workout_type = _STRAVA_TYPE_MAP.get(strava_type, "Other")

        duration_min = int(act.get("elapsed_time", 0) / 60)
        calories     = int(act.get("calories", 0))
        # Strava gives distance in metres — convert steps roughly for running
        distance_m   = act.get("distance", 0)
        steps = int(distance_m * 1.31) if strava_type in ("Run", "Walk", "Hike") else 0

        # Upsert — one Strava entry per (user, date, type=Strava)
        # Use the activity ID in notes to avoid exact-duplicate imports
        existing = db.query(WorkoutLog).filter(
            WorkoutLog.user_id == user_id,
            WorkoutLog.log_date == act_date,
            WorkoutLog.workout_type == "Strava",
            WorkoutLog.notes.like(f"%strava:{act['id']}%"),
        ).first()

        if not existing:
            entry = WorkoutLog(
                user_id=user_id,
                log_date=act_date,
                workout_type="Strava",
                duration_min=duration_min,
                step_count=steps,
                calories=calories,
                notes=f"{act.get('name', strava_type)} [strava:{act['id']}]",
            )
            db.add(entry)
            synced_count += 1
        else:
            # Update in case Strava data changed
            existing.duration_min = duration_min
            existing.calories     = calories
            existing.step_count   = steps

    db.commit()
    print(f"[Strava] Synced {synced_count} new activities for user {user_id}")

    # Recalculate daily wellness/lifestyle score after sync for all synced dates
    try:
        from main import compute_and_save_wellness
        synced_dates = {date.fromisoformat(act["start_date_local"][:10]) for act in activities}
        synced_dates.add(date.today())
        for d in synced_dates:
            compute_and_save_wellness(user_id, db, for_date=d)
    except Exception as e:
        print(f"[Strava] Wellness score recalculation failed: {e}")

    return {
        "success": True,
        "synced_count": synced_count,
        "total_fetched": len(activities),
    }
