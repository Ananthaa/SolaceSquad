"""
Sync-X — Plugin Registry
Central store for all registered fitness plugins.
Exposes the combined FastAPI router with hub API endpoints.
"""
from typing import Optional
from fastapi import APIRouter, Request, Depends
from sqlalchemy.orm import Session
from database import get_db
from fitness_plugins.base import FitnessPlugin


class PluginRegistry:
    _plugins: dict[str, FitnessPlugin] = {}

    @classmethod
    def register(cls, plugin: FitnessPlugin):
        cls._plugins[plugin.provider_id] = plugin
        print(f"[Sync-X] Registered: {plugin.display_name}")

    @classmethod
    def get_all(cls) -> list[FitnessPlugin]:
        return list(cls._plugins.values())

    @classmethod
    def get_configured(cls) -> list[FitnessPlugin]:
        return [p for p in cls._plugins.values() if p.is_configured()]

    @classmethod
    def get(cls, provider_id: str) -> Optional[FitnessPlugin]:
        return cls._plugins.get(provider_id)

    @classmethod
    def build_router(cls) -> APIRouter:
        """Build the combined Sync-X API router."""
        router = APIRouter()

        # Mount each configured plugin's own OAuth/sync routes
        for plugin in cls.get_configured():
            try:
                router.include_router(plugin.get_router())
            except Exception as e:
                print(f"[Sync-X] Router error for {plugin.provider_id}: {e}")

        # ── Sync-X Hub API ────────────────────────────────────────────────────

        @router.get("/api/sync-x/providers")
        def list_providers(request: Request, db: Session = Depends(get_db)):
            """List all providers with connection status for the logged-in user."""
            user_id = request.session.get("user_id")
            return {
                "providers": [
                    p.get_card_data(user_id, db)
                    for p in cls.get_all()
                ]
            }

        @router.post("/api/sync-x/sync/{provider_id}")
        def trigger_sync(provider_id: str, request: Request, db: Session = Depends(get_db)):
            """Trigger a manual sync for a specific provider."""
            user_id = request.session.get("user_id")
            if not user_id:
                return {"success": False, "error": "Not logged in"}
            plugin = cls.get(provider_id)
            if not plugin:
                return {"success": False, "error": "Unknown provider"}
            if not plugin.is_configured():
                return {"success": False, "error": "Provider not configured"}
            result = plugin.sync(user_id, db)
            return result.__dict__

        @router.post("/api/sync-x/disconnect/{provider_id}")
        def disconnect_provider(provider_id: str, request: Request, db: Session = Depends(get_db)):
            """Disconnect a provider for the logged-in user."""
            user_id = request.session.get("user_id")
            if not user_id:
                return {"success": False, "error": "Not logged in"}
            plugin = cls.get(provider_id)
            if not plugin:
                return {"success": False, "error": "Unknown provider"}
            plugin.disconnect(user_id, db)
            return {"success": True, "message": f"{plugin.display_name} disconnected"}

        @router.post("/api/sync-x/push")
        async def mobile_push(request: Request, db: Session = Depends(get_db)):
            """
            Universal mobile push endpoint.
            Android/iOS apps post health data here after reading from
            Samsung Health SDK or Apple HealthKit.
            """
            user_id = request.session.get("user_id")
            if not user_id:
                return {"success": False, "error": "Not logged in"}

            data = await request.json()
            source   = data.get("source", "mobile_push")
            workouts = data.get("workouts", [])
            vitals   = data.get("vitals", {})

            from models import WorkoutLog, VitalsRecord
            from datetime import date, datetime
            from workout_overlap_utils import detect_and_merge_workout
            saved = 0
            touched_dates = set()

            for w in workouts:
                sync_d_str = w.get("sync_date") or w.get("log_date")
                try:
                    w_date = date.fromisoformat(sync_d_str) if sync_d_str else date.today()
                except Exception:
                    w_date = date.today()

                start_dt = None
                end_dt = None
                if w.get("start_time"):
                    try:
                        start_dt = datetime.fromisoformat(str(w["start_time"])[:19])
                    except Exception:
                        pass
                if w.get("end_time"):
                    try:
                        end_dt = datetime.fromisoformat(str(w["end_time"])[:19])
                    except Exception:
                        pass

                rec, is_new = detect_and_merge_workout(
                    db           = db,
                    user_id      = user_id,
                    log_date     = w_date,
                    workout_type = w.get("workout_type", "Other"),
                    duration_min = int(w.get("duration_min", 0)),
                    step_count   = int(w.get("step_count", 0)),
                    calories     = int(w.get("calories", 0)),
                    distance_km  = float(w.get("distance_km")) if w.get("distance_km") is not None else None,
                    source       = source,
                    external_id  = w.get("external_id"),
                    start_time   = start_dt,
                    end_time     = end_dt,
                    notes        = w.get("notes", f"Mobile push from {source}"),
                )
                if is_new:
                    saved += 1
                touched_dates.add(w_date)

            if vitals:
                v = VitalsRecord(
                    user_id=user_id,
                    timestamp=datetime.utcnow(),
                    heart_rate=vitals.get("heart_rate"),
                    spo2=vitals.get("spo2"),
                    method=source,
                )
                db.add(v)

            db.commit()

            # Recalculate daily wellness / lifestyle score
            try:
                from main import compute_and_save_wellness
                touched_dates.add(date.today())
                for td in touched_dates:
                    compute_and_save_wellness(user_id, db, for_date=td)
            except Exception as we:
                print(f"[MobilePush] Wellness recalculation failed: {we}")

            return {
                "success": True,
                "workouts_saved": saved,
                "vitals_updated": bool(vitals),
            }

        return router


# ── Token helpers used by plugins ─────────────────────────────────────────────

def get_token(db: Session, user_id: int, provider: str):
    """Fetch FitnessIntegration token record for a user+provider."""
    try:
        from models import FitnessIntegration
        return db.query(FitnessIntegration).filter(
            FitnessIntegration.user_id == user_id,
            FitnessIntegration.provider == provider,
            FitnessIntegration.is_connected == True,
        ).first()
    except Exception:
        return None


def store_token(db: Session, user_id: int, provider: str, refresh_token: str):
    """Upsert a FitnessIntegration token record."""
    from models import FitnessIntegration
    from datetime import datetime
    existing = db.query(FitnessIntegration).filter(
        FitnessIntegration.user_id == user_id,
        FitnessIntegration.provider == provider,
    ).first()
    if existing:
        existing.refresh_token = refresh_token
        existing.is_connected = True
        existing.last_sync_at = None
        existing.last_sync_error = None
    else:
        db.add(FitnessIntegration(
            user_id=user_id,
            provider=provider,
            refresh_token=refresh_token,
            is_connected=True,
            connected_at=datetime.utcnow(),
        ))
    db.commit()


def delete_token(db: Session, user_id: int, provider: str):
    """Remove a FitnessIntegration token record."""
    from models import FitnessIntegration
    db.query(FitnessIntegration).filter(
        FitnessIntegration.user_id == user_id,
        FitnessIntegration.provider == provider,
    ).delete()
    db.commit()
