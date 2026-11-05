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

        def _extract_user_id(req: Request) -> Optional[int]:
            uid = req.session.get("user_id")
            if uid:
                try:
                    return int(str(uid))
                except (ValueError, TypeError):
                    pass
            try:
                from main import get_auth_user_id
                return get_auth_user_id(req)
            except Exception:
                pass
            return None

        # ── Sync-X Hub API ────────────────────────────────────────────────────

        @router.get("/api/sync-x/providers")
        def list_providers(request: Request, db: Session = Depends(get_db)):
            """List all providers with connection status for the logged-in user."""
            user_id = _extract_user_id(request)
            return {
                "providers": [
                    p.get_card_data(user_id, db)
                    for p in cls.get_all()
                ]
            }

        @router.post("/api/sync-x/sync/{provider_id}")
        def trigger_sync(provider_id: str, request: Request, db: Session = Depends(get_db)):
            """Trigger a manual sync for a specific provider."""
            user_id = _extract_user_id(request)
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
            user_id = _extract_user_id(request)
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
            user_id = _extract_user_id(request)
            if not user_id:
                return {"success": False, "error": "Not logged in"}

            data = await request.json()
            source   = data.get("source", "mobile_push")
            workouts = data.get("workouts", [])
            vitals   = data.get("vitals", {})

            from models import WorkoutLog, VitalsRecord
            from datetime import date, datetime
            from workout_overlap_utils import derive_effective_duration
            saved = 0
            affected_dates = set()

            for w in workouts:
                ext_id = str(w.get("external_id", "") or "").strip()
                sync_date_str = w.get("sync_date")
                try:
                    log_date = date.fromisoformat(sync_date_str) if sync_date_str else date.today()
                except Exception:
                    log_date = date.today()

                raw_dur = int(w.get("duration_min", 0) or 0)
                raw_steps = int(w.get("step_count", 0) or 0)
                raw_cals = int(w.get("calories", 0) or 0)
                w_type = w.get("workout_type", "Walking" if raw_steps > 0 else "Other")
                notes = w.get("notes", "")

                eff_duration = derive_effective_duration(raw_dur, raw_steps, w_type)
                if raw_cals <= 0 and eff_duration > 0:
                    raw_cals = round(3.5 * 70.0 * (eff_duration / 60.0))

                # Dedup check
                existing = None
                if ext_id:
                    existing = db.query(WorkoutLog).filter(
                        WorkoutLog.user_id == user_id,
                        WorkoutLog.external_id == ext_id,
                        WorkoutLog.source == source,
                    ).first()

                if not existing and ("daily steps" in (w_type or "").lower() or "daily steps" in (notes or "").lower()):
                    existing = db.query(WorkoutLog).filter(
                        WorkoutLog.user_id == user_id,
                        WorkoutLog.log_date == log_date,
                        WorkoutLog.source == source,
                        WorkoutLog.notes.like("%daily steps%"),
                    ).first()

                if existing:
                    # Update with higher telemetry
                    if raw_steps > (existing.step_count or 0):
                        existing.step_count = raw_steps
                    if eff_duration > (existing.duration_min or 0):
                        existing.duration_min = eff_duration
                    if raw_cals > (existing.calories or 0):
                        existing.calories = raw_cals
                    if notes and not existing.notes:
                        existing.notes = notes
                    existing.is_duplicate = False
                    saved += 1
                else:
                    entry = WorkoutLog(
                        user_id=user_id,
                        log_date=log_date,
                        workout_type=w_type,
                        duration_min=eff_duration,
                        step_count=raw_steps,
                        calories=raw_cals,
                        notes=notes,
                        source=source,
                        external_id=ext_id if ext_id else None,
                        is_duplicate=False,
                    )
                    db.add(entry)
                    saved += 1

                affected_dates.add(log_date)

            if vitals:
                v = VitalsRecord(
                    user_id=user_id,
                    date=date.today(),
                    heart_rate=vitals.get("heart_rate"),
                    spo2=vitals.get("spo2"),
                    source=source,
                )
                db.add(v)
                affected_dates.add(date.today())

            db.commit()

            # Recalculate daily wellness / lifestyle score for all affected dates
            try:
                from main import compute_and_save_wellness
                for d in affected_dates:
                    compute_and_save_wellness(user_id, db, for_date=d)
            except Exception as _we:
                print(f"[Sync-X] Wellness score computation error: {_we}")

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
