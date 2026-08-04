"""
Sync-X — Plugin Base Class
All fitness plugins inherit from FitnessPlugin.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional
from fastapi import APIRouter
from sqlalchemy.orm import Session


@dataclass
class SyncResult:
    success: bool
    workouts_saved: int = 0
    workouts_skipped: int = 0
    vitals_updated: bool = False
    thryveq_score: Optional[float] = None
    error: Optional[str] = None


class FitnessPlugin(ABC):
    """
    Abstract base for all Sync-X fitness integrations.
    Implement this class to add a new provider.
    """

    # ── Identity (set on each plugin class) ──────────────────────────────────
    provider_id:         str        # "google_health" | "strava" | ...
    display_name:        str        # "Google Health"
    description:         str        # Short user-facing text
    logo_filename:       str        # static/img/integrations/{logo_filename}
    color:               str        # Brand hex color e.g. "#4285F4"
    supported_platforms: list       # ["web", "android", "ios"]
    required_env_vars:   list       # Checked at startup to determine availability

    # ── Required implementation ───────────────────────────────────────────────
    @abstractmethod
    def get_router(self) -> APIRouter:
        """Return FastAPI router with OAuth + sync routes."""

    @abstractmethod
    def sync(self, user_id: int, db: Session) -> SyncResult:
        """Pull latest data and upsert into workout_logs / vitals_records."""

    @abstractmethod
    def is_connected(self, user_id: int, db: Session) -> bool:
        """True if user has a valid stored token for this provider."""

    @abstractmethod
    def disconnect(self, user_id: int, db: Session) -> None:
        """Remove stored tokens and mark integration as disconnected."""

    @abstractmethod
    def get_last_sync(self, user_id: int, db: Session) -> Optional[str]:
        """Return ISO timestamp of last successful sync or None."""

    # ── Built-in helpers (available to all plugins) ───────────────────────────
    def is_configured(self) -> bool:
        """True if all required env vars are set (determines if plugin is available)."""
        import os
        return all(os.getenv(v) for v in self.required_env_vars)

    def get_card_data(self, user_id: Optional[int], db: Optional[Session]) -> dict:
        """Returns all data needed to render the Sync-X UI card."""
        connected = False
        last_sync = None
        if user_id and db and self.is_configured():
            try:
                connected = self.is_connected(user_id, db)
                last_sync = self.get_last_sync(user_id, db)
            except Exception:
                pass

        return {
            "provider_id":    self.provider_id,
            "display_name":   self.display_name,
            "description":    self.description,
            "logo_filename":  self.logo_filename,
            "color":          self.color,
            "platforms":      self.supported_platforms,
            "is_configured":  self.is_configured(),
            "is_connected":   connected,
            "last_sync":      last_sync,
            "connect_url":    f"/auth/{self.provider_id}/connect",
            "sync_url":       f"/api/sync-x/sync/{self.provider_id}",
            "disconnect_url": f"/api/sync-x/disconnect/{self.provider_id}",
        }
