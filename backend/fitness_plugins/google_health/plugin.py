"""
Google Health Plugin — FitnessPlugin implementation
Wraps the Google Fitness REST API OAuth + sync routes.
"""
from typing import Optional
from fastapi import APIRouter
from sqlalchemy.orm import Session

from fitness_plugins.base import FitnessPlugin, SyncResult


class GoogleHealthPlugin(FitnessPlugin):
    provider_id          = "google_health"
    display_name         = "Google Health"
    description          = "Sync your Google Fit data — steps, workouts, heart rate and more."
    logo_filename        = "google_health.svg"
    color                = "#4285F4"
    supported_platforms  = ["web", "android", "ios"]
    required_env_vars    = ["GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET"]

    def get_router(self) -> APIRouter:
        from .oauth import router
        return router

    def sync(self, user_id: int, db: Session) -> SyncResult:
        """Delegate to the sync route logic in oauth.py."""
        try:
            from fitness_plugins.registry import get_token, store_token
            from .oauth import _get_access_token, _ACTIVITY_MAP, _DISTANCE_ACTIVITY_TYPES, _FITNESS_BASE, _extract_fp_val
            from models import WorkoutLog, User
            from datetime import date, datetime, timedelta, timezone
            import requests as _req

            user = db.query(User).filter(User.id == user_id).first()
            token = get_token(db, user_id, "google_health")
            if not token:
                # Fallback to check legacy User.google_fit_refresh_token
                if user and user.google_fit_refresh_token:
                    store_token(db, user_id, "google_health", user.google_fit_refresh_token)
                    db.commit()
                    token = get_token(db, user_id, "google_health")

            if not token:
                return SyncResult(success=False, error="Not connected")

            from zoneinfo import ZoneInfo
            tz_name = user.timezone if user else "UTC"
            try:
                user_tz = ZoneInfo(tz_name)
            except Exception:
                user_tz = ZoneInfo("UTC")

            # Load user weight (default 70kg) and MET configurations
            from models import UserProfile
            profile = db.query(UserProfile).filter(UserProfile.user_id == user_id).first()
            user_weight = profile.weight if (profile and profile.weight) else 70.0

            _WL_MET = {
                'Running': 9.8,
                'Walking': 3.5,
                'Cycling': 7.5,
                'Swimming': 7.0,
                'Yoga': 2.5,
                'Strength': 5.0,
                'HIIT': 10.0,
                'Pilates': 3.0,
                'Dancing': 5.5,
                'Meditation': 1.3,
                'Sports': 6.0,
                'Rowing': 7.0,
                'Boxing': 9.0,
                'Climbing': 8.0,
                'Stretching': 2.3,
                'Other': 4.0,
            }

            access_token = _get_access_token(token.refresh_token)
            if not access_token:
                return SyncResult(success=False, error="Token refresh failed")

            headers  = {"Authorization": f"Bearer {access_token}"}
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
                act_date    = datetime.fromtimestamp(start_ms / 1000, user_tz).date() if start_ms else datetime.now(user_tz).date()
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

                # Estimate calories if Google Fit doesn't have it
                if calories <= 0:
                    met = _WL_MET.get(workout_type, 4.0)
                    calories = round(met * user_weight * (duration_min / 60.0))

                # Only attach distance for distance-based activities
                if act_type not in _DISTANCE_ACTIVITY_TYPES:
                    dist_km = None

                db.add(WorkoutLog(
                    user_id      = user_id,
                    log_date     = act_date,
                    workout_type = workout_type,
                    duration_min = duration_min,
                    calories     = calories,
                    step_count   = steps if steps > 0 else 0,
                    distance_km  = dist_km,
                    source       = "google_health",
                    external_id  = external_id,
                    notes        = f"Synced from Google Fit: {s.get('name', workout_type)}",
                ))
                saved += 1

            # ── 2. Daily total steps (sync all days in range) ────────────────────
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

                for bucket in step_resp.json().get("bucket", []):
                    start_ms_bucket = int(bucket.get("startTimeMillis", 0))
                    if not start_ms_bucket:
                        continue
                    b_date = datetime.fromtimestamp(start_ms_bucket / 1000, user_tz).date()
                    steps = int(_extract_fp_val(bucket.get("dataset", []), "step_count.delta"))
                    if steps < 1:
                        continue
                    
                    # Calculate Walking calories & duration: 100 steps per min, MET = 3.5
                    effective_dur = steps / 100.0
                    step_calories = round(3.5 * user_weight * (effective_dur / 60.0))
                    duration_min = round(effective_dur)

                    existing = db.query(WorkoutLog).filter(
                        WorkoutLog.user_id  == user_id,
                        WorkoutLog.log_date == b_date,
                        WorkoutLog.source   == "google_health",
                        WorkoutLog.notes.like("Google Fit daily steps%"),
                    ).first()
                    if existing:
                        if existing.step_count != steps or existing.calories != step_calories:
                            existing.step_count = steps
                            existing.calories = step_calories
                            existing.duration_min = duration_min
                            if b_date == datetime.now(user_tz).date():
                                saved += 1
                    else:
                        db.add(WorkoutLog(
                            user_id      = user_id,
                            log_date     = b_date,
                            workout_type = "Walking",
                            duration_min = duration_min,
                            step_count   = steps,
                            calories     = step_calories,
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

            return SyncResult(success=True, workouts_saved=saved)

        except Exception as e:
            return SyncResult(success=False, error=str(e))

    def is_connected(self, user_id: int, db: Session) -> bool:
        from fitness_plugins.registry import get_token
        if get_token(db, user_id, "google_health") is not None:
            return True
        from models import User
        user = db.query(User).filter(User.id == user_id).first()
        return bool(user and user.google_fit_refresh_token)

    def disconnect(self, user_id: int, db: Session) -> None:
        from fitness_plugins.registry import delete_token
        delete_token(db, user_id, "google_health")
        from models import User
        user = db.query(User).filter(User.id == user_id).first()
        if user:
            user.google_fit_refresh_token = None
            db.commit()

    def get_last_sync(self, user_id: int, db: Session) -> Optional[str]:
        from fitness_plugins.registry import get_token
        token = get_token(db, user_id, "google_health")
        if token and token.last_sync_at:
            return token.last_sync_at.isoformat()
        return None
