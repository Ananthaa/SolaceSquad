"""
Google Fitness API — OAuth 2.0 + Sync
Uses the Google Fitness REST API: www.googleapis.com/fitness/v1
Captures: workouts, steps, calories, distance (km) for walking/running/cycling.
"""
import os
import secrets
import urllib.parse
from datetime import date, datetime, timedelta, timezone
from typing import Optional

import requests as _req
from fastapi import APIRouter, Request, Depends
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from database import get_db

router = APIRouter()

# ── Config ──────────────────────────────────────────────────────────────────────
_CLIENT_ID     = os.getenv("GOOGLE_CLIENT_ID", "")
_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
_BASE_URL      = os.getenv("APP_BASE_URL", "https://www.solacesquad.com").rstrip("/")
_REDIRECT_URI  = f"{_BASE_URL}/auth/google_health/callback"

_AUTH_URL     = "https://accounts.google.com/o/oauth2/v2/auth"
_TOKEN_URL    = "https://oauth2.googleapis.com/token"
_FITNESS_BASE = "https://www.googleapis.com/fitness/v1/users/me"

# Standard Google Fitness scopes — no sensitive-data review required
_SCOPES = [
    "https://www.googleapis.com/auth/fitness.activity.read",
    "https://www.googleapis.com/auth/fitness.body.read",
    "https://www.googleapis.com/auth/fitness.heart_rate.read",
]

# Distance-based activity types (walking/running/cycling)
_DISTANCE_ACTIVITY_TYPES = {7, 8, 9, 1, 21, 15}

# Google Fit activityType ID → SolaceSquad workout type
_ACTIVITY_MAP = {
    1:   "Cycling",
    7:   "Walking",
    8:   "Running",
    9:   "Running",
    15:  "Cycling",
    17:  "HIIT",
    20:  "HIIT",
    21:  "Cycling",
    29:  "Walking",
    32:  "HIIT",
    45:  "Pilates",
    51:  "Rowing",
    57:  "Strength",
    63:  "Swimming",
    68:  "Yoga",
    74:  "Walking",
    75:  "Boxing",
    82:  "Meditation",
    87:  "Dancing",
    97:  "Strength",
    108: "Pilates",
    113: "Yoga",
}


def _is_configured() -> bool:
    return bool(_CLIENT_ID and _CLIENT_SECRET)


def _get_access_token(refresh_token: str) -> Optional[str]:
    try:
        resp = _req.post(_TOKEN_URL, data={
            "client_id":     _CLIENT_ID,
            "client_secret": _CLIENT_SECRET,
            "refresh_token": refresh_token,
            "grant_type":    "refresh_token",
        }, timeout=15)
        resp.raise_for_status()
        return resp.json().get("access_token")
    except Exception as e:
        print(f"[GoogleHealth] Token refresh failed: {e}")
        return None


def _extract_fp_val(dataset: list, label: str) -> float:
    """Extract sum of fpVal or intVal from a dataset list returned by bucketBySession."""
    total = 0.0
    for ds in dataset:
        src = ds.get("dataSourceId", "")
        if label not in src:
            continue
        for pt in ds.get("point", []):
            for v in pt.get("value", []):
                if "fpVal" in v:
                    total += v["fpVal"]
                elif "intVal" in v:
                    total += float(v["intVal"])
    return total


# ── Connect ─────────────────────────────────────────────────────────────────────

@router.get("/auth/google_health/connect")
def google_health_connect(request: Request):
    """Redirect user to Google consent page for Fitness API scopes."""
    if not _is_configured():
        return RedirectResponse("/app/sync-x?error=google_health_not_configured")

    user_id = request.session.get("user_id")
    if not user_id:
        return RedirectResponse("/login?next_url=/app/sync-x")

    state = secrets.token_urlsafe(16)
    request.session["gh_oauth_state"] = state

    params = {
        "client_id":     _CLIENT_ID,
        "redirect_uri":  _REDIRECT_URI,
        "response_type": "code",
        "scope":         " ".join(_SCOPES),
        "access_type":   "offline",
        "prompt":        "consent",
        "state":         state,
    }
    return RedirectResponse(f"{_AUTH_URL}?{urllib.parse.urlencode(params)}")


# ── Callback ────────────────────────────────────────────────────────────────────

@router.get("/auth/google_health/callback")
def google_health_callback(request: Request, db: Session = Depends(get_db)):
    """Exchange auth code for tokens and store refresh token."""
    user_id = request.session.get("user_id")
    if not user_id:
        return RedirectResponse("/login")

    error = request.query_params.get("error")
    if error == "access_denied":
        return RedirectResponse("/app/sync-x?error=google_health_denied")

    code  = request.query_params.get("code")
    state = request.query_params.get("state")

    if state != request.session.pop("gh_oauth_state", None):
        return RedirectResponse("/app/sync-x?error=google_health_state_mismatch")

    if not code:
        return RedirectResponse("/app/sync-x?error=google_health_no_code")

    try:
        resp = _req.post(_TOKEN_URL, data={
            "code":          code,
            "client_id":     _CLIENT_ID,
            "client_secret": _CLIENT_SECRET,
            "redirect_uri":  _REDIRECT_URI,
            "grant_type":    "authorization_code",
        }, timeout=15)
        resp.raise_for_status()
        tokens = resp.json()
    except Exception as e:
        print(f"[GoogleHealth] Code exchange failed: {e}")
        return RedirectResponse("/app/sync-x?error=google_health_auth_failed")

    refresh_token = tokens.get("refresh_token")
    if not refresh_token:
        return RedirectResponse("/app/sync-x?error=google_health_no_refresh_token")

    from fitness_plugins.registry import store_token
    store_token(db, user_id, "google_health", refresh_token)

    # Clear legacy Fitbit token if present
    try:
        from models import User
        user = db.get(User, user_id)
        if user and getattr(user, "fitbit_refresh_token", None):
            user.fitbit_refresh_token = None
            db.commit()
    except Exception:
        pass

    print(f"[GoogleHealth] Connected for user {user_id}")
    return RedirectResponse("/app/sync-x?google_health_connected=1")


# ── Sync ────────────────────────────────────────────────────────────────────────

@router.get("/api/google_health/sync")
def sync_google_health(request: Request, db: Session = Depends(get_db)):
    """
    Pull activity sessions + per-session calories, distance, and daily steps
    from the Google Fitness REST API.
    """
    user_id = request.session.get("user_id")
    if not user_id:
        return {"error": "Not logged in"}

    from fitness_plugins.registry import get_token
    token = get_token(db, user_id, "google_health")
    if not token:
        return {"error": "Google Health not connected", "connected": False}

    access_token = _get_access_token(token.refresh_token)
    if not access_token:
        return {
            "error": "Token refresh failed. Please reconnect.",
            "connected": False,
            "need_reconnect": True,
        }

    headers  = {"Authorization": f"Bearer {access_token}"}
    from models import WorkoutLog
    saved    = 0
    now_utc  = datetime.now(timezone.utc)
    start_dt = now_utc - timedelta(days=14)
    now_ms   = int(now_utc.timestamp() * 1000)
    ago_ms   = int(start_dt.timestamp() * 1000)

    # ── 1. Fetch per-session calories + distance via bucketBySession ──────────
    try:
        agg_resp = _req.post(
            f"{_FITNESS_BASE}/dataset:aggregate",
            headers={**headers, "Content-Type": "application/json"},
            json={
                "aggregateBy": [
                    {"dataTypeName": "com.google.calories.expended"},
                    {"dataTypeName": "com.google.distance.delta"},
                    {"dataTypeName": "com.google.step_count.delta"},
                ],
                "bucketBySession": {"minDurationMillis": "60000"},
                "startTimeMillis": ago_ms,
                "endTimeMillis":   now_ms,
            },
            timeout=20,
        )
        agg_resp.raise_for_status()
        session_buckets = agg_resp.json().get("bucket", [])
    except Exception as e:
        print(f"[GoogleHealth] Session aggregate failed: {e}")
        session_buckets = []

    for bucket in session_buckets:
        s           = bucket.get("session", {})
        act_type    = s.get("activityType", 4)
        workout_type = _ACTIVITY_MAP.get(act_type, "Other")
        start_ms    = int(s.get("startTimeMillis", bucket.get("startTimeMillis", 0)))
        end_ms      = int(s.get("endTimeMillis",   bucket.get("endTimeMillis",   0)))
        act_date    = date.fromtimestamp(start_ms / 1000) if start_ms else date.today()
        duration_min = max(0, int((end_ms - start_ms) / 60000))
        external_id = s.get("id", "")

        if duration_min < 2:
            continue  # skip sub-2-minute noise

        # Dedup by external_id
        if external_id and db.query(WorkoutLog).filter(
            WorkoutLog.user_id    == user_id,
            WorkoutLog.external_id == external_id,
            WorkoutLog.source     == "google_health",
        ).first():
            continue

        dataset     = bucket.get("dataset", [])
        calories    = round(_extract_fp_val(dataset, "calories.expended"))
        dist_m      = _extract_fp_val(dataset, "distance.delta")
        dist_km     = round(dist_m / 1000, 2) if dist_m > 0 else None
        steps       = int(_extract_fp_val(dataset, "step_count.delta"))

        # Only attach distance for distance-based activities
        if act_type not in _DISTANCE_ACTIVITY_TYPES:
            dist_km = None

        db.add(WorkoutLog(
            user_id      = user_id,
            log_date     = act_date,
            workout_type = workout_type,
            duration_min = duration_min,
            calories     = calories if calories > 0 else 0,
            step_count   = steps if steps > 0 else 0,
            distance_km  = dist_km,
            source       = "google_health",
            external_id  = external_id,
            notes        = f"Synced from Google Fit: {s.get('name', workout_type)}",
        ))
        saved += 1

    # ── 2. Today's total steps (if no session covered it) ────────────────────
    try:
        step_resp = _req.post(
            f"{_FITNESS_BASE}/dataset:aggregate",
            headers={**headers, "Content-Type": "application/json"},
            json={
                "aggregateBy":  [{"dataTypeName": "com.google.step_count.delta"}],
                "bucketByTime": {"durationMillis": 86400000},
                "startTimeMillis": ago_ms,
                "endTimeMillis":   now_ms,
            },
            timeout=15,
        )
        step_resp.raise_for_status()
        today_str = date.today().isoformat()

        for bucket in step_resp.json().get("bucket", []):
            b_date = date.fromtimestamp(
                int(bucket.get("startTimeMillis", 0)) / 1000
            ).isoformat()
            if b_date != today_str:
                continue
            steps = int(_extract_fp_val(bucket.get("dataset", []), "step_count.delta"))
            if steps < 1:
                continue
            existing = db.query(WorkoutLog).filter(
                WorkoutLog.user_id  == user_id,
                WorkoutLog.log_date == date.today(),
                WorkoutLog.source   == "google_health",
                WorkoutLog.notes.like("Google Fit daily steps%"),
            ).first()
            if existing:
                existing.step_count = steps
            else:
                db.add(WorkoutLog(
                    user_id      = user_id,
                    log_date     = date.today(),
                    workout_type = "Walking",
                    step_count   = steps,
                    source       = "google_health",
                    notes        = f"Google Fit daily steps: {steps:,} steps synced",
                ))
                saved += 1
    except Exception as e:
        print(f"[GoogleHealth] Step aggregate error: {e}")

    db.commit()

    # Update last_sync timestamp
    try:
        token.last_sync_at     = datetime.utcnow()
        token.last_sync_status = "success"
        db.commit()
    except Exception:
        pass

    # Recalculate wellness score
    try:
        from main import compute_and_save_wellness
        compute_and_save_wellness(user_id, db, for_date=date.today())
    except Exception as e:
        print(f"[GoogleHealth] Wellness recalc failed: {e}")

    print(f"[GoogleHealth] Synced {saved} new entries for user {user_id}")
    return {
        "success":        True,
        "workouts_saved": saved,
        "sessions_found": len(session_buckets),
    }
