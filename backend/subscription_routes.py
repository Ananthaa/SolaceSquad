"""
Subscription / Monetisation Routes
Imported and registered in main.py at startup.
"""
from __future__ import annotations
import hashlib
import hmac
import os
from datetime import datetime, timedelta

from fastapi import Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from sqlalchemy.orm import Session


def _local_get_initials(name: str) -> str:
    parts = name.split()
    if len(parts) >= 2:
        return (parts[0][0] + parts[-1][0]).upper()
    return name[:2].upper()


# ──────────────────────────────────────────────────────────────────────────────────────────────────

def _razorpay_client():
    """Return a Razorpay client if keys are set, else None (graceful no-op)."""
    key_id     = os.environ.get("RAZORPAY_KEY_ID")
    key_secret = os.environ.get("RAZORPAY_KEY_SECRET")
    if not key_id or not key_secret:
        return None, None
    try:
        import razorpay
        client = razorpay.Client(auth=(key_id, key_secret))
        return client, key_secret
    except ImportError:
        return None, None


def get_active_subscription(user_id: int, db: Session):
    """Return the user's current active UserSubscription or None.

    If the active subscription is a free plan, also check for a paused paid
    subscription and return that instead. This ensures that quota logic,
    first-week bonus, and plan caps all correctly reflect the user's paid
    plan while it is paused — so resuming continues from exactly where
    they left off.
    """
    from models import UserSubscription
    now = datetime.utcnow()
    sub = (
        db.query(UserSubscription)
        .filter(
            UserSubscription.user_id == user_id,
            UserSubscription.status == "active",
        )
        .order_by(UserSubscription.started_at.desc())
        .first()
    )
    if sub and sub.expires_at and sub.expires_at < now:
        sub.status = "expired"
        db.commit()
        sub = None

    # If no active sub, or the active sub is a free plan, check for a paused
    # paid subscription so quota / caps / first-week logic stays correct.
    if not sub or (sub.plan and sub.plan.is_free):
        paused_paid = (
            db.query(UserSubscription)
            .filter(
                UserSubscription.user_id == user_id,
                UserSubscription.status  == "paused",
            )
            .order_by(UserSubscription.started_at.desc())
            .first()
        )
        if paused_paid and paused_paid.plan and not paused_paid.plan.is_free:
            # Paused but not expired — treat as the effective subscription
            if not (paused_paid.expires_at and paused_paid.expires_at < now):
                return paused_paid

    return sub


def get_user_plan_caps(user_id: int, db: Session) -> dict:
    """
    Return a dict: { feature_key: PlanFeatureCap } for the user's active plan.
    Falls back to an unlimited virtual plan if the user has no subscription.
    """
    from models import UsagePlan, PlanFeatureCap, UserSubscription
    sub = get_active_subscription(user_id, db)
    if sub:
        caps = db.query(PlanFeatureCap).filter(PlanFeatureCap.plan_id == sub.plan_id).all()
    else:
        # Use default plan caps
        default_plan = db.query(UsagePlan).filter(
            UsagePlan.is_default == True, UsagePlan.is_active == True
        ).first()
        caps = db.query(PlanFeatureCap).filter(
            PlanFeatureCap.plan_id == default_plan.id
        ).all() if default_plan else []
    return {c.feature_key: c for c in caps}


def _get_period_key(feature_key: str = None) -> str:
    """
    Returns the period key for the usage log.
    - ai_chat → daily key 'YYYY-MM-DD'  (limit resets every day; unused msgs expire)
    - everything else → monthly key 'YYYY-MM'
    """
    now = datetime.utcnow()
    if feature_key == "ai_chat":
        return now.strftime("%Y-%m-%d")
    return now.strftime("%Y-%m")


def check_feature_limit(user_id: int, feature_key: str, db: Session) -> dict:
    """
    Check whether the user has remaining quota for feature_key.

    Returns:
      { allowed: bool, used: int, limit: int, cap: PlanFeatureCap | None,
        message: str, can_extend: bool, extend_price: float, extend_quota: int }
    """
    from models import FeatureUsageLog, FeatureUsageTopUp, UserSubscription

    caps = get_user_plan_caps(user_id, db)
    cap  = caps.get(feature_key)

    # No cap configured â†’ unlimited
    if cap is None:
        return {"allowed": True, "used": 0, "limit": -1, "cap": None,
                "message": "", "can_extend": False, "extend_price": 0, "extend_quota": 0}

    # ── ai_chat two-phase quota logic ────────────────────────────────────────
    if feature_key == "ai_chat":
        active_sub = get_active_subscription(user_id, db)
        in_first_week = False
        bonus_eligible = True
        if active_sub:
            days_on_plan = (datetime.utcnow() - active_sub.started_at).days
            bonus_eligible = getattr(active_sub, "is_first_week_bonus_eligible", True)
            in_first_week = (days_on_plan < 7) and bonus_eligible

        # ── Stable week1 key: always anchored to the user's FIRST EVER subscription
        # date, not the current active sub's started_at.  This prevents the counter
        # from silently resetting whenever ensure_default_subscription creates a new
        # subscription row (which would otherwise produce a new key and hide old usage).
        first_ever_sub = db.query(UserSubscription).filter(
            UserSubscription.user_id == user_id,
        ).order_by(UserSubscription.started_at.asc()).first()
        _anchor_date = (
            first_ever_sub.started_at if first_ever_sub
            else (active_sub.started_at if active_sub else datetime.utcnow())
        )
        week1_key = "week1-" + _anchor_date.strftime("%Y-%m-%d")

        # Lifetime pack: total purchased - total used from pack bucket
        lt_topups = db.query(FeatureUsageTopUp).filter(
            FeatureUsageTopUp.user_id     == user_id,
            FeatureUsageTopUp.feature_key == feature_key,
            FeatureUsageTopUp.month_key   == "lifetime",
            FeatureUsageTopUp.status      == "paid",
        ).all()
        pack_purchased = sum(t.quota_added for t in lt_topups)
        lt_usage_log = db.query(FeatureUsageLog).filter(
            FeatureUsageLog.user_id     == user_id,
            FeatureUsageLog.feature_key == feature_key,
            FeatureUsageLog.month_key   == "lifetime",
        ).first()
        pack_used = lt_usage_log.usage_count if lt_usage_log else 0
        pack_balance = max(0, pack_purchased - pack_used)

        # ── PHASE 1: First-week welcome pool (500 msgs, no daily sub-cap) ──────
        if in_first_week:
            first_week_limit = cap.limit_first_week if cap.limit_first_week is not None else 500
            if first_week_limit == -1:
                return {"allowed": True, "used": 0, "limit": -1, "cap": cap,
                        "message": "", "can_extend": False, "extend_price": 0, "extend_quota": 0,
                        "daily_remaining": -1, "pack_balance": pack_balance, "in_first_week": True,
                        "_week1_key": week1_key}
            w1_log = db.query(FeatureUsageLog).filter(
                FeatureUsageLog.user_id     == user_id,
                FeatureUsageLog.feature_key == feature_key,
                FeatureUsageLog.month_key   == week1_key,
            ).first()
            week1_used = w1_log.usage_count if w1_log else 0
            
            first_week_remaining = max(0, first_week_limit - week1_used)
            total_remaining = first_week_remaining + pack_balance
            allowed = total_remaining > 0
            message = cap.limit_hit_message or (
                "You've used all your Emora welcome messages. Your daily 20 messages start from day 8. Or top up with an Emora pack!"
                if not allowed else ""
            )
            return {
                "allowed": allowed,
                "used": week1_used,
                "limit": first_week_limit,
                "cap": cap,
                "message": message,
                "can_extend": (not allowed) and cap.extend_price > 0,
                "extend_price": cap.extend_price,
                "extend_quota": cap.extend_quota,
                "daily_remaining": total_remaining,
                "pack_balance": pack_balance,
                "in_first_week": True,
                "_week1_key": week1_key,
            }

        # ── PHASE 2: Post-week daily (20/day) + lifetime pack overflow ────────
        daily_limit = cap.limit_post_week if cap.limit_post_week is not None else 20
        if daily_limit == -1:
            return {"allowed": True, "used": 0, "limit": -1, "cap": cap,
                    "message": "", "can_extend": False, "extend_price": 0, "extend_quota": 0,
                    "daily_remaining": -1, "pack_balance": pack_balance, "in_first_week": False}

        # Always use DAILY key so 20 messages reset every 24 hours (for all plan types)
        today_key = datetime.utcnow().strftime("%Y-%m-%d")

        day_log = db.query(FeatureUsageLog).filter(
            FeatureUsageLog.user_id     == user_id,
            FeatureUsageLog.feature_key == feature_key,
            FeatureUsageLog.month_key   == today_key,
        ).first()
        daily_used = day_log.usage_count if day_log else 0
        daily_remaining = max(0, daily_limit - daily_used)

        total_remaining = daily_remaining + pack_balance
        allowed = total_remaining > 0
        can_extend = (not allowed) and cap.extend_price > 0 and cap.extend_quota > 0
        message = cap.limit_hit_message or (
            "You've used today's Emora messages. They'll refresh tomorrow — or top up with an Emora pack for instant access!"
            if not allowed else ""
        )
        return {
            "allowed": allowed,
            "used": daily_used,
            "limit": daily_limit,
            "cap": cap,
            "message": message,
            "can_extend": can_extend,
            "extend_price": cap.extend_price,
            "extend_quota": cap.extend_quota,
            "daily_remaining": daily_remaining,
            "pack_balance": pack_balance,
            "in_first_week": False,
            "_period_key": today_key,   # always today's daily key
        }

    # ── All other features (non-ai_chat) ──────────────────────────────────────
    effective_limit = cap.limit_value
    if effective_limit == -1:
        return {"allowed": True, "used": 0, "limit": -1, "cap": cap,
                "message": "", "can_extend": False, "extend_price": 0, "extend_quota": 0}

    period_key = _get_period_key(feature_key)

    # Base usage
    log = db.query(FeatureUsageLog).filter(
        FeatureUsageLog.user_id == user_id,
        FeatureUsageLog.feature_key == feature_key,
        FeatureUsageLog.month_key == period_key,
    ).first()
    base_used = log.usage_count if log else 0

    # Top-up quota already purchased in this period (including lifetime packs)
    top_ups = db.query(FeatureUsageTopUp).filter(
        FeatureUsageTopUp.user_id    == user_id,
        FeatureUsageTopUp.feature_key == feature_key,
        FeatureUsageTopUp.status     == "paid",
    ).filter(
        (FeatureUsageTopUp.month_key == period_key) |
        (FeatureUsageTopUp.month_key == "lifetime"),
    ).all()
    bonus = sum(t.quota_added for t in top_ups)

    total_limit = effective_limit + bonus
    allowed = base_used < total_limit

    can_extend = (not allowed) and (cap.extend_price > 0) and (cap.extend_quota > 0)
    message = cap.limit_hit_message or (
        f"You've reached your {cap.feature_name} limit for this month." if not allowed else ""
    )

    return {
        "allowed": allowed,
        "used": base_used,
        "limit": total_limit,
        "cap": cap,
        "message": message,
        "can_extend": can_extend,
        "extend_price": cap.extend_price,
        "extend_quota": cap.extend_quota,
    }


def increment_feature_usage(user_id: int, feature_key: str, db: Session):
    """
    Deduct one unit of quota for a feature.

    For ai_chat — consumption order:
      1. Week-1 welcome pool (days 1-7, 500-1000 msgs, expires after 7 days)
      2. Today's daily bucket (20/day, resets every 24 hours, starts from day 8)
      3. Lifetime pack bucket (non-expiring, used ONLY when daily is exhausted)
    For all other features — monthly counter.
    """
    from models import FeatureUsageLog, FeatureUsageTopUp

    if feature_key == "ai_chat":
        # Re-use check_feature_limit to determine which bucket to deduct from
        quota = check_feature_limit(user_id, feature_key, db)
        in_first_week = quota.get("in_first_week", False)

        if in_first_week:
            first_week_limit = quota.get("limit", 500)
            week1_used = quota.get("used", 0)
            if first_week_limit == -1 or week1_used < first_week_limit:
                # Deduct from week-1 pool using the stable key from check_feature_limit.
                # Fall back: anchor to the first-ever subscription date (never the current
                # active sub's started_at, which changes when a new sub row is created).
                week1_key = quota.get("_week1_key")
                if not week1_key:
                    first_ever_sub = db.query(UserSubscription).filter(
                        UserSubscription.user_id == user_id,
                    ).order_by(UserSubscription.started_at.asc()).first()
                    if first_ever_sub:
                        week1_key = "week1-" + first_ever_sub.started_at.strftime("%Y-%m-%d")
                    else:
                        active_sub = get_active_subscription(user_id, db)
                        week1_key = "week1-" + active_sub.started_at.strftime("%Y-%m-%d") if active_sub else "week1-unknown"
                log = db.query(FeatureUsageLog).filter(
                    FeatureUsageLog.user_id     == user_id,
                    FeatureUsageLog.feature_key == feature_key,
                    FeatureUsageLog.month_key   == week1_key,
                ).first()
                if log:
                    log.usage_count += 1
                else:
                    log = FeatureUsageLog(
                        user_id=user_id, feature_key=feature_key,
                        month_key=week1_key, usage_count=1
                    )
                    db.add(log)
            else:
                # Welcome pool exhausted - deduct from lifetime pack
                lt_log = db.query(FeatureUsageLog).filter(
                    FeatureUsageLog.user_id     == user_id,
                    FeatureUsageLog.feature_key == feature_key,
                    FeatureUsageLog.month_key   == "lifetime",
                ).first()
                if lt_log:
                    lt_log.usage_count += 1
                else:
                    lt_log = FeatureUsageLog(
                        user_id=user_id, feature_key=feature_key,
                        month_key="lifetime", usage_count=1
                    )
                    db.add(lt_log)
        else:
            daily_remaining = quota.get("daily_remaining", 0)
            # Always use today's daily key — period_key from quota is already today
            period_key = quota.get("_period_key") or datetime.utcnow().strftime("%Y-%m-%d")

            if daily_remaining > 0:
                # Deduct from today's daily bucket
                log = db.query(FeatureUsageLog).filter(
                    FeatureUsageLog.user_id     == user_id,
                    FeatureUsageLog.feature_key == feature_key,
                    FeatureUsageLog.month_key   == period_key,
                ).first()
                if log:
                    log.usage_count += 1
                else:
                    log = FeatureUsageLog(
                        user_id=user_id, feature_key=feature_key,
                        month_key=period_key, usage_count=1
                    )
                    db.add(log)
            else:
                # Daily exhausted — deduct from lifetime pack
                lt_log = db.query(FeatureUsageLog).filter(
                    FeatureUsageLog.user_id     == user_id,
                    FeatureUsageLog.feature_key == feature_key,
                    FeatureUsageLog.month_key   == "lifetime",
                ).first()
                if lt_log:
                    lt_log.usage_count += 1
                else:
                    lt_log = FeatureUsageLog(
                        user_id=user_id, feature_key=feature_key,
                        month_key="lifetime", usage_count=1
                    )
                    db.add(lt_log)
        db.commit()
        return

    # ── All other features: monthly counter ─────────────────────────────────
    period_key = _get_period_key(feature_key)
    log = db.query(FeatureUsageLog).filter(
        FeatureUsageLog.user_id     == user_id,
        FeatureUsageLog.feature_key == feature_key,
        FeatureUsageLog.month_key   == period_key,
    ).first()
    if log:
        log.usage_count += 1
    else:
        log = FeatureUsageLog(
            user_id=user_id, feature_key=feature_key,
            month_key=period_key, usage_count=1
        )
        db.add(log)
    db.commit()


def ensure_default_subscription(user_id: int, db: Session):
    """
    If user has no active subscription, auto-enrol them in the default (free) plan.
    Called at login / first dashboard load.

    Existing users (those who had a prior subscription) are NOT granted the
    first-week welcome pool — they only get 20 msgs/day.
    """
    from models import UsagePlan, UserSubscription
    if get_active_subscription(user_id, db):
        return
    default_plan = db.query(UsagePlan).filter(
        UsagePlan.is_default == True, UsagePlan.is_active == True
    ).first()
    if not default_plan:
        return

    # Check if this user has ever had a subscription (even cancelled/expired)
    any_prior = db.query(UserSubscription).filter(
        UserSubscription.user_id == user_id,
    ).order_by(UserSubscription.started_at.asc()).first()

    if any_prior:
        # Returning user — no welcome pool; use the original subscription date
        # so (now - started_at).days is large and in_first_week stays False
        is_new_user = False
        original_start = any_prior.started_at
    else:
        # Brand-new user — grant welcome pool
        is_new_user = True
        original_start = datetime.utcnow()

    sub = UserSubscription(
        user_id=user_id,
        plan_id=default_plan.id,
        status="active",
        started_at=original_start,
        expires_at=None,
        payment_status="free",
        is_first_week_bonus_eligible=is_new_user,
    )
    db.add(sub)
    db.commit()



# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Registration helper â€” called from main.py
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def _compute_expiry(billing_cycle: str):
    """Return expiry datetime based on billing cycle."""
    now = datetime.utcnow()
    if not billing_cycle:
        return None
    bc = billing_cycle.lower()
    if bc in ("yearly", "annual"):
        return now + timedelta(days=365)
    elif bc == "monthly":
        return now + timedelta(days=30)
    elif bc == "weekly":
        return now + timedelta(days=7)
    return None  # free / one_time


def register_subscription_routes(app, templates, get_db):
    """Attach all subscription routes to the FastAPI app."""

    from models import (
        UsagePlan, PlanFeatureCap, UserSubscription,
        FeatureUsageLog, FeatureUsageTopUp, User, Voucher,
    )

    # â”€â”€ helpers reused inside routes â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    def _admin_check(request: Request, db: Session):
        uid = request.session.get("user_id")
        user = db.query(User).filter(User.id == uid).first() if uid else None
        if not user or user.user_type != "admin":
            raise HTTPException(status_code=403, detail="Forbidden")
        return user

    def _user_check(request: Request, db: Session):
        uid = request.session.get("user_id")
        if not uid:
            raise HTTPException(status_code=401, detail="Not authenticated")
        return uid

    def _plan_to_dict(plan: UsagePlan) -> dict:
        return {
            "id": plan.id, "name": plan.name, "description": plan.description,
            "price": plan.price, "billing_cycle": plan.billing_cycle,
            "is_free": plan.is_free, "is_default": plan.is_default,
            "is_active": plan.is_active, "colour": plan.colour,
            "display_order": plan.display_order,
            "caps": [_cap_to_dict(c) for c in plan.caps],
        }

    def _cap_to_dict(cap: PlanFeatureCap) -> dict:
        return {
            "id": cap.id, "plan_id": cap.plan_id,
            "feature_key": cap.feature_key, "feature_name": cap.feature_name,
            "limit_value": cap.limit_value,
            "limit_first_week": cap.limit_first_week,
            "limit_post_week": cap.limit_post_week,
            "limit_hit_message": cap.limit_hit_message,
            "extend_price": cap.extend_price, "extend_quota": cap.extend_quota,
        }

    # â”€â”€ Admin: plans page â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    @app.get("/admin/plans", response_class=HTMLResponse)
    async def admin_plans_page(request: Request, db: Session = Depends(get_db)):
        _admin_check(request, db)
        plans_orm = db.query(UsagePlan).order_by(UsagePlan.display_order).all()
        # subscription count per plan
        from sqlalchemy import func as sql_func
        counts = dict(
            db.query(UserSubscription.plan_id, sql_func.count(UserSubscription.id))
            .filter(UserSubscription.status == "active")
            .group_by(UserSubscription.plan_id)
            .all()
        )
        # Convert to dicts so Jinja tojson filter works (SQLAlchemy objects aren't JSON-serialisable)
        plans = [_plan_to_dict(p) for p in plans_orm]
        return templates.TemplateResponse("pages/admin_plans.html", {
            "request": request, "plans": plans,
            "sub_counts": counts,
            "page_title": "Usage Plans | Admin",
            "user_type": "admin",
        })

    # â”€â”€ Admin API: list plans â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    # ── Public API: list active plans (no auth required) ──────────────────────

    @app.get("/api/plans/public")
    async def api_public_list_plans(db: Session = Depends(get_db)):
        plans = db.query(UsagePlan).filter(UsagePlan.is_active == True).order_by(UsagePlan.display_order).all()
        public_fields = []
        for p in plans:
            public_fields.append({
                "id": p.id,
                "plan_name": p.name,
                "description": p.description,
                "price": float(p.price),
                "billing_cycle": p.billing_cycle,
                "is_free": p.is_free,
                "is_popular": getattr(p, "is_popular", False),
                "colour": p.colour or "#0d9488",
            })
        return JSONResponse({"success": True, "plans": public_fields})

    @app.get("/api/admin/plans")
    async def api_admin_list_plans(request: Request, db: Session = Depends(get_db)):
        _admin_check(request, db)
        plans = db.query(UsagePlan).order_by(UsagePlan.display_order).all()
        return JSONResponse({"success": True, "plans": [_plan_to_dict(p) for p in plans]})

    # â”€â”€ Admin API: create plan â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    @app.post("/api/admin/plans")
    async def api_admin_create_plan(request: Request, db: Session = Depends(get_db)):
        _admin_check(request, db)
        data = await request.json()
        if data.get("is_default"):
            db.query(UsagePlan).filter(UsagePlan.is_default == True).update({"is_default": False})
        plan = UsagePlan(
            name=data["name"],
            description=data.get("description", ""),
            price=float(data.get("price", 0)),
            billing_cycle=data.get("billing_cycle", "monthly"),
            is_free=bool(data.get("is_free", True)),
            is_default=bool(data.get("is_default", False)),
            is_active=bool(data.get("is_active", True)),
            colour=data.get("colour", "#0d9488"),
            display_order=int(data.get("display_order", 0)),
        )
        db.add(plan)
        db.commit()
        db.refresh(plan)
        return JSONResponse({"success": True, "plan": _plan_to_dict(plan)})

    # ── Admin API: update plan ─────────────────────────────────────────────────

    @app.patch("/api/admin/plans/{plan_id}")
    async def api_admin_update_plan(plan_id: int, request: Request, db: Session = Depends(get_db)):
        _admin_check(request, db)
        data = await request.json()
        plan = db.query(UsagePlan).filter(UsagePlan.id == plan_id).first()
        if not plan:
            return JSONResponse({"success": False, "error": "Plan not found"}, status_code=404)

        if "name"          in data: plan.name          = data["name"]
        if "description"   in data: plan.description   = data["description"]
        if "price"         in data: plan.price          = float(data["price"])
        if "billing_cycle" in data: plan.billing_cycle  = data["billing_cycle"]
        if "is_free"       in data: plan.is_free        = bool(data["is_free"])
        if "is_active"     in data: plan.is_active      = bool(data["is_active"])
        if "colour"        in data: plan.colour         = data["colour"]
        if "display_order" in data: plan.display_order  = int(data["display_order"])
        if data.get("is_default"):
            db.query(UsagePlan).filter(UsagePlan.id != plan_id, UsagePlan.is_default == True).update({"is_default": False})
            plan.is_default = True
        elif "is_default" in data:
            plan.is_default = bool(data["is_default"])

        db.commit()
        db.refresh(plan)
        return JSONResponse({"success": True, "plan": _plan_to_dict(plan)})

    # â”€â”€ Admin API: update plan â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    @app.put("/api/admin/plans/{plan_id}")
    async def api_admin_update_plan(plan_id: int, request: Request, db: Session = Depends(get_db)):
        _admin_check(request, db)
        plan = db.query(UsagePlan).filter(UsagePlan.id == plan_id).first()
        if not plan:
            raise HTTPException(status_code=404, detail="Plan not found")
        data = await request.json()
        if data.get("is_default") and not plan.is_default:
            db.query(UsagePlan).filter(UsagePlan.is_default == True).update({"is_default": False})
        for field in ("name", "description", "price", "billing_cycle",
                      "is_free", "is_default", "is_active", "colour", "display_order"):
            if field in data:
                setattr(plan, field, data[field])
        db.commit()
        db.refresh(plan)
        return JSONResponse({"success": True, "plan": _plan_to_dict(plan)})

    # â”€â”€ Admin API: delete plan â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    @app.delete("/api/admin/plans/{plan_id}")
    async def api_admin_delete_plan(plan_id: int, request: Request, db: Session = Depends(get_db)):
        _admin_check(request, db)
        plan = db.query(UsagePlan).filter(UsagePlan.id == plan_id).first()
        if not plan:
            raise HTTPException(status_code=404, detail="Plan not found")
        active_subs = db.query(UserSubscription).filter(
            UserSubscription.plan_id == plan_id,
            UserSubscription.status == "active",
        ).count()
        if active_subs:
            plan.is_active = False
            db.commit()
            return JSONResponse({"success": True, "message": f"Plan deactivated ({active_subs} active subscribers)"})
        db.delete(plan)
        db.commit()
        return JSONResponse({"success": True})

    # â”€â”€ Admin API: upsert feature caps â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    @app.post("/api/admin/plans/{plan_id}/caps")
    async def api_admin_upsert_caps(plan_id: int, request: Request, db: Session = Depends(get_db)):
        _admin_check(request, db)
        data = await request.json()   # list of cap objects
        caps_data = data if isinstance(data, list) else data.get("caps", [])
        for c in caps_data:
            existing = db.query(PlanFeatureCap).filter(
                PlanFeatureCap.plan_id == plan_id,
                PlanFeatureCap.feature_key == c["feature_key"],
            ).first()
            if existing:
                existing.feature_name      = c.get("feature_name", existing.feature_name)
                existing.limit_value       = int(c.get("limit_value", existing.limit_value))
                existing.limit_first_week  = c.get("limit_first_week")
                existing.limit_post_week   = c.get("limit_post_week")
                existing.limit_hit_message = c.get("limit_hit_message")
                existing.extend_price      = float(c.get("extend_price", 0))
                existing.extend_quota      = int(c.get("extend_quota", 0))
            else:
                cap = PlanFeatureCap(
                    plan_id=plan_id,
                    feature_key=c["feature_key"],
                    feature_name=c.get("feature_name", c["feature_key"]),
                    limit_value=int(c.get("limit_value", -1)),
                    limit_first_week=c.get("limit_first_week"),
                    limit_post_week=c.get("limit_post_week"),
                    limit_hit_message=c.get("limit_hit_message"),
                    extend_price=float(c.get("extend_price", 0)),
                    extend_quota=int(c.get("extend_quota", 0)),
                )
                db.add(cap)
        db.commit()
        caps = db.query(PlanFeatureCap).filter(PlanFeatureCap.plan_id == plan_id).all()
        return JSONResponse({"success": True, "caps": [_cap_to_dict(c) for c in caps]})

    @app.delete("/api/admin/plans/{plan_id}/caps/{cap_id}")
    async def api_admin_delete_cap(plan_id: int, cap_id: int, request: Request, db: Session = Depends(get_db)):
        _admin_check(request, db)
        cap = db.query(PlanFeatureCap).filter(
            PlanFeatureCap.id == cap_id,
            PlanFeatureCap.plan_id == plan_id,
        ).first()
        if cap:
            db.delete(cap)
            db.commit()
        return JSONResponse({"success": True})

    # â”€â”€ Admin API: subscriptions overview â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    @app.get("/api/admin/subscriptions")
    async def api_admin_subscriptions(request: Request, db: Session = Depends(get_db)):
        _admin_check(request, db)
        subs = (
            db.query(UserSubscription, User, UsagePlan)
            .join(User, UserSubscription.user_id == User.id)
            .join(UsagePlan, UserSubscription.plan_id == UsagePlan.id)
            .order_by(UserSubscription.created_at.desc())
            .limit(200)
            .all()
        )
        return JSONResponse({"success": True, "subscriptions": [
            {
                "id": s.id, "user_id": s.user_id, "user_name": u.name, "user_email": u.email,
                "plan_name": p.name, "plan_id": p.id,
                "status": s.status, "payment_status": s.payment_status,
                "started_at": s.started_at.isoformat() if s.started_at else None,
                "expires_at": s.expires_at.isoformat() if s.expires_at else None,
            }
            for s, u, p in subs
        ]})

    # â”€â”€ User: plans page â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    def _make_page_token(uid: int) -> str:
        """HMAC token for cookie-independent auth fallback."""
        import hmac as _h, hashlib as _hs, os as _os, time as _t
        ts = str(int(_t.time()) // 60)
        secret = _os.getenv("SECRET_KEY", "fallback-dev-key").encode()
        sig = _h.new(secret, f"{uid}:{ts}".encode(), _hs.sha256).hexdigest()[:16]
        return f"{uid}:{ts}:{sig}"

    def _verify_page_token(token: str):
        """Return uid int if token valid, else None."""
        import hmac as _h, hashlib as _hs, os as _os, time as _t
        try:
            parts = token.split(":")
            if len(parts) != 3: return None
            uid_str, ts_str, sig = parts
            if abs(int(_t.time()) // 60 - int(ts_str)) > 30: return None
            secret = _os.getenv("SECRET_KEY", "fallback-dev-key").encode()
            expected = _h.new(secret, f"{uid_str}:{ts_str}".encode(), _hs.sha256).hexdigest()[:16]
            return int(uid_str) if _h.compare_digest(sig, expected) else None
        except Exception:
            return None

    @app.get("/app/plans", response_class=HTMLResponse)
    async def user_plans_page(request: Request, db: Session = Depends(get_db)):
        uid = request.session.get("user_id")
        if not uid:
            return RedirectResponse("/login", status_code=303)
        user_name = request.session.get("user_name", "User")
        page_token = _make_page_token(uid)
        return templates.TemplateResponse("pages/plans.html", {
            "request": request,
            "page_title": "Choose a Plan - SolaceSquad",
            "user_name": user_name,
            "user_initials": _local_get_initials(user_name),
            "user_type": "user",
            "active_page": "plans",
            "page_token": page_token,
        })


    # â”€â”€ User API: list plans â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    @app.get("/api/plans")
    async def api_list_plans(request: Request, db: Session = Depends(get_db)):
        uid = request.session.get("user_id")
        if not uid:
            # Fallback: token sent in header
            _token = request.headers.get("X-Page-Token", "")
            if _token:
                uid = _verify_page_token(_token)
        if not uid:
            return JSONResponse({"success": False}, status_code=401)

        ensure_default_subscription(uid, db)
        sub = get_active_subscription(uid, db)

        plans = db.query(UsagePlan).filter(UsagePlan.is_active == True).order_by(UsagePlan.display_order).all()
        rz_key = os.environ.get("RAZORPAY_KEY_ID", "")

        # Calculate prorated discount from current active paid subscription
        prorated_discount = 0.0
        if sub and sub.plan and not sub.plan.is_free:
            now = datetime.utcnow()
            if sub.expires_at and sub.expires_at > now:
                cycle = sub.plan.billing_cycle or "monthly"
                if cycle == "weekly":
                    cycle_days = 7
                elif cycle in ("yearly", "annual"):
                    cycle_days = 365
                else:
                    cycle_days = 30
                daily_rate = sub.plan.price / cycle_days
                remaining_seconds = (sub.expires_at - now).total_seconds()
                remaining_days = max(0.0, remaining_seconds / 86400.0)
                remaining_days = min(float(cycle_days), remaining_days)
                prorated_discount = round(remaining_days * daily_rate, 2)

        return JSONResponse({
            "success": True,
            "plans": [_plan_to_dict(p) for p in plans],
            "current_plan_id": sub.plan_id if sub else None,
            "razorpay_key_id": rz_key,
            "prorated_discount": prorated_discount,
        })

    # â”€â”€ User API: get my usage â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    @app.get("/api/plans/my-usage")
    async def api_my_usage(request: Request, db: Session = Depends(get_db)):
        uid = request.session.get("user_id")
        if not uid:
            return JSONResponse({"success": False}, status_code=401)
        ensure_default_subscription(uid, db)
        caps = get_user_plan_caps(uid, db)
        sub  = get_active_subscription(uid, db)
        plan = sub.plan if sub else None

        # ── Build per-feature usage + effective limit (respects week-1 logic & lifetime packs) ──
        caps_out   = {}
        usage_dict = {}

        # Batch-fetch all logs and paid top-ups for the user to optimize performance
        from models import FeatureUsageLog, FeatureUsageTopUp
        all_logs = db.query(FeatureUsageLog).filter(FeatureUsageLog.user_id == uid).all()
        logs_lookup = {(l.feature_key, l.month_key): l.usage_count for l in all_logs}

        all_topups = db.query(FeatureUsageTopUp).filter(
            FeatureUsageTopUp.user_id == uid,
            FeatureUsageTopUp.status == "paid"
        ).all()
        
        topups_lookup = {}
        for t in all_topups:
            key = (t.feature_key, t.month_key)
            if key not in topups_lookup:
                topups_lookup[key] = []
            topups_lookup[key].append(t)

        for feature_key, cap in caps.items():
            pk  = _get_period_key(feature_key)

            # Retrieve cached usage log value
            used = logs_lookup.get((feature_key, pk), 0)
            usage_dict[feature_key] = used

            # ── ai_chat: use check_feature_limit which handles all period/phase logic ──
            if feature_key == "ai_chat":
                quota = check_feature_limit(uid, feature_key, db)
                in_first_week   = quota.get("in_first_week", False)
                pack_balance    = quota.get("pack_balance", 0)
                daily_remaining = quota.get("daily_remaining", 0)

                if in_first_week:
                    # Week-1: show how many of the 500 welcome messages have been used
                    fw_limit      = quota.get("limit", 500)          # e.g. 500
                    fw_used       = quota.get("used", 0)             # messages used so far
                    display_limit = fw_limit
                    display_used  = fw_used
                else:
                    # Post-week: daily allowance (e.g. 20)
                    daily_limit   = quota.get("limit", 20)           # e.g. 20/day
                    daily_used    = quota.get("used", 0)             # messages used today
                    display_limit = daily_limit                      # daily subscription allowance only
                    display_used  = daily_used                       # daily subscription used only

                caps_out[feature_key] = {
                    "feature_key":       feature_key,
                    "feature_name":      cap.feature_name,
                    "limit":             display_limit,    # Subscription quota limit only
                    "used":              display_used,     # Subscription quota used only
                    "daily_remaining":   daily_remaining,  # total remaining (first week) or daily remaining (post-week)
                    "pack_balance":      pack_balance,
                    "in_first_week":     in_first_week,
                    "extend_price":      cap.extend_price,
                    "extend_quota":      cap.extend_quota,
                    "limit_hit_message": cap.limit_hit_message,
                }
                continue


            # ── All other features ────────────────────────────────────────────
            eff_limit = cap.limit_value
            # Add lifetime pack bonus to the display balance from cache
            lifetime_bonus = 0
            if eff_limit != -1:
                lt_rows = topups_lookup.get((feature_key, "lifetime"), [])
                lifetime_bonus = sum(r.quota_added for r in lt_rows)

            # Period top-ups from cache
            period_bonus = 0
            if eff_limit != -1:
                pt_rows = topups_lookup.get((feature_key, pk), [])
                period_bonus = sum(r.quota_added for r in pt_rows)

            total_limit = (eff_limit + lifetime_bonus + period_bonus) if eff_limit != -1 else -1

            caps_out[feature_key] = {
                "feature_key":   feature_key,
                "feature_name":  cap.feature_name,
                "limit":         total_limit,          # -1 = unlimited
                "used":          used,
                "extend_price":  cap.extend_price,
                "extend_quota":  cap.extend_quota,
                "limit_hit_message": cap.limit_hit_message,
            }

        return JSONResponse({
            "success":        True,
            "plan_name":      plan.name  if plan else "Free",
            "plan_colour":    plan.colour if plan else "#6b7280",
            "plan_price":     plan.price  if plan else 0,
            "original_price": plan.original_price if plan else None,
            "billing_cycle":  plan.billing_cycle if plan else "monthly",
            "caps":           caps_out,
            "usage":          usage_dict,
        })

    # â”€â”€ User API: subscribe (free plan or initiate paid) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    @app.get("/api/plans/session-debug")
    async def api_session_debug(request: Request):
        """Temporary debug endpoint — shows what is in the current session."""
        return JSONResponse({
            "session_keys": list(request.session.keys()),
            "user_id": request.session.get("user_id"),
            "user_email": request.session.get("user_email"),
            "user_type": request.session.get("user_type"),
            "cookies": list(request.cookies.keys()),
        })

    @app.post("/api/plans/subscribe")
    async def api_subscribe(request: Request, db: Session = Depends(get_db)):
        import traceback as _tb, hmac as _hmac, hashlib as _hs, time as _t

        # ── Auth layer 1: session cookie ────────────────────────────────────
        uid = request.session.get("user_id")
        print(f"[subscribe] session uid={uid}, cookies={list(request.cookies.keys())}")

        # ── Auth layer 2: HMAC page token (handles PWA/mobile cookie issues) ──
        if not uid:
            try:
                _raw_body = await request.body()
                import json as _j
                _body_data = _j.loads(_raw_body) if _raw_body else {}
                _token = _body_data.get("page_token", "")
                print(f"[subscribe] no session, token='{_token[:20] if _token else ''}'")
                if _token:
                    _parts = _token.split(":")
                    if len(_parts) == 3:
                        _uid_str, _ts_str, _sig = _parts
                        _now_min = int(_t.time()) // 60
                        _age = abs(_now_min - int(_ts_str))
                        print(f"[subscribe] token uid={_uid_str} age={_age}min")
                        if _age <= 30:
                            _secret = os.getenv("SECRET_KEY", "fallback-dev-key").encode()
                            _expected = _hmac.new(_secret, f"{_uid_str}:{_ts_str}".encode(), _hs.sha256).hexdigest()[:16]
                            if _hmac.compare_digest(_sig, _expected):
                                uid = int(_uid_str)
                                print(f"[subscribe] token auth OK, uid={uid}")
                            else:
                                print(f"[subscribe] token sig mismatch: got={_sig} expected={_expected}")
                        else:
                            print(f"[subscribe] token expired: age={_age}min")
                    else:
                        print(f"[subscribe] token bad format: {len(_parts)} parts")
            except Exception as _te:
                print(f"[subscribe] token parse error: {_te}")

        if not uid:
            return JSONResponse({
                "success": False,
                "error": f"Not authenticated (session empty, token invalid). Cookies: {list(request.cookies.keys())}"
            }, status_code=401)

        try:
            # Re-parse body (already cached by Starlette after request.body() call above)
            data = await request.json()
            plan_id = int(data.get("plan_id", 0))
            plan = db.query(UsagePlan).filter(UsagePlan.id == plan_id, UsagePlan.is_active == True).first()
            if not plan:
                return JSONResponse({"success": False, "error": "Plan not found"}, status_code=404)

            # Cancel any current active subscription
            try:
                current_sub = get_active_subscription(uid, db)
                old_plan_price = current_sub.plan.price if current_sub and current_sub.plan else 0
                is_upgrade = plan.price > old_plan_price
            except Exception:
                old_plan_price = 0
                is_upgrade = True

            # Calculate prorated discount from current active paid subscription BEFORE we cancel it
            prorated_discount = 0.0
            if is_upgrade and current_sub and current_sub.plan and not current_sub.plan.is_free:
                now = datetime.utcnow()
                if current_sub.expires_at and current_sub.expires_at > now:
                    cycle = current_sub.plan.billing_cycle or "monthly"
                    if cycle == "weekly":
                        cycle_days = 7
                    elif cycle in ("yearly", "annual"):
                        cycle_days = 365
                    else:
                        cycle_days = 30
                    daily_rate = current_sub.plan.price / cycle_days
                    remaining_seconds = (current_sub.expires_at - now).total_seconds()
                    remaining_days = max(0.0, remaining_seconds / 86400.0)
                    remaining_days = min(float(cycle_days), remaining_days)
                    prorated_discount = round(remaining_days * daily_rate, 2)

            final_price = max(0.0, plan.price - prorated_discount)

            # Apply Voucher if present
            voucher_code = data.get("voucher_code")
            voucher_discount = 0.0
            if voucher_code:
                voucher_res = _validate_voucher_internal(db, uid, voucher_code, "plan", plan.id, final_price)
                if not voucher_res["valid"]:
                    return JSONResponse({"success": False, "error": voucher_res["error"]}, status_code=400)
                voucher_discount = voucher_res["discount_amount"]
                final_price = voucher_res["final_price"]

            try:
                db.query(UserSubscription).filter(
                    UserSubscription.user_id == uid,
                    UserSubscription.status == "active",
                ).update({"status": "cancelled"})
                db.commit()
            except Exception as _ce:
                db.rollback()
                print(f"[WARN] Could not cancel existing sub: {_ce}")

            if plan.is_free or final_price == 0:
                try:
                    expires_at = None if plan.is_free else _compute_expiry(plan.billing_cycle)
                    sub = UserSubscription(
                        user_id=uid, plan_id=plan.id, status="active",
                        started_at=datetime.utcnow(), expires_at=expires_at,
                        payment_status="free" if plan.is_free else "paid",
                    )
                    try:
                        sub.voucher_code = voucher_code
                    except Exception:
                        pass
                    # Try setting bonus field — may not exist on old schema
                    try:
                        sub.is_first_week_bonus_eligible = is_upgrade
                    except Exception:
                        pass
                    db.add(sub)
                    db.commit()

                    if not plan.is_free:
                        # Log to unified payment ledger
                        try:
                            from finance_routes import log_payment_transaction
                            cycle_label = "Yearly" if plan.name.lower() == "blue" else plan.billing_cycle.title()
                            log_payment_transaction(
                                db                  = db,
                                user_id             = uid,
                                transaction_type    = "subscription",
                                amount              = 0.0,
                                status              = "completed",
                                related_entity_type = "subscription",
                                related_entity_id   = sub.id,
                                description         = f"{plan.name} Plan ({cycle_label}) — Switch Promo Discount 100%",
                            )
                        except Exception as _log_err:
                            print(f"[WARN] Could not log payment transaction: {_log_err}")

                    return JSONResponse({"success": True, "activated": True})
                except Exception as _fe:
                    db.rollback()
                    return JSONResponse({"success": False, "error": f"DB error: {_fe}"})

            # Paid plan — create Razorpay order
            client, _ = _razorpay_client()
            if not client:
                return JSONResponse({
                    "success": False,
                    "error": "Payment gateway not configured. Please contact support.",
                }, status_code=503)

            # Read enable_auto_renew from request body (already parsed above)
            enable_auto_renew = bool(data.get("enable_auto_renew", False))

            amount_paise = int(round(final_price * 1.18, 2) * 100)
            order = client.order.create({
                "amount": amount_paise,
                "currency": "INR",
                "notes": {"plan_id": str(plan.id), "user_id": str(uid),
                          "auto_renew": str(enable_auto_renew)},
            })

            # Build subscription row — guard against missing columns
            sub_kwargs = dict(
                user_id=uid, plan_id=plan.id, status="pending_payment",
                started_at=datetime.utcnow(),
                expires_at=_compute_expiry(plan.billing_cycle),
                payment_status="pending",
            )
            try:
                sub = UserSubscription(**sub_kwargs)
                try:
                    sub.voucher_code = voucher_code
                except Exception:
                    pass
                try:
                    sub.razorpay_order_id = order["id"]
                except Exception:
                    pass
                try:
                    sub.is_first_week_bonus_eligible = is_upgrade
                except Exception:
                    pass
                # Store auto-renew intent — will be confirmed in payment_verify
                try:
                    sub.auto_renew = enable_auto_renew
                except Exception:
                    pass
                db.add(sub)
                db.commit()
            except Exception as _dbe:
                db.rollback()
                return JSONResponse({"success": False, "error": f"DB error saving subscription: {_dbe}"})

            return JSONResponse({
                "success": True, "activated": False,
                "order_id": order["id"],
                "amount": amount_paise,
                "currency": "INR",
                "plan_name": plan.name,
                "enable_auto_renew": enable_auto_renew,
            })

        except Exception as _ex:
            db.rollback()
            _trace = _tb.format_exc()
            print(f"[ERROR] api_subscribe: {_trace}")
            return JSONResponse({"success": False, "error": str(_ex), "detail": _trace[-300:]})

    # ── User API: verify payment ──────────────────────────────────────────────────

    @app.post("/api/plans/payment-verify")
    async def api_payment_verify(request: Request, db: Session = Depends(get_db)):
        uid = request.session.get("user_id")
        if not uid:
            return JSONResponse({"success": False}, status_code=401)
        data = await request.json()
        order_id   = data.get("razorpay_order_id")
        payment_id = data.get("razorpay_payment_id")
        signature  = data.get("razorpay_signature")

        _, key_secret = _razorpay_client()
        if not key_secret:
            return JSONResponse({"success": False, "error": "Gateway not configured"}, status_code=503)

        expected = hmac.new(key_secret.encode(), f"{order_id}|{payment_id}".encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, signature or ""):
            return JSONResponse({"success": False, "error": "Payment verification failed"}, status_code=400)

        sub = db.query(UserSubscription).filter(
            UserSubscription.user_id == uid,
            UserSubscription.razorpay_order_id == order_id,
        ).first()
        if sub:
            sub.status = "active"
            sub.payment_status = "paid"
            sub.razorpay_payment_id = payment_id
            # If auto_renew was opted in, set next_renewal_at
            try:
                if getattr(sub, "auto_renew", False) and sub.expires_at:
                    sub.next_renewal_at = sub.expires_at
                    print(f"[AUTO-RENEW] next_renewal_at set to {sub.next_renewal_at} for sub {sub.id}")
            except Exception as _are:
                print(f"[AUTO-RENEW] Could not set next_renewal_at: {_are}")
            db.commit()
            # Log to unified payment ledger
            try:
                from finance_routes import log_payment_transaction
                plan = sub.plan
                
                # Fetch actual amount from Razorpay to handle prorated discounts
                try:
                    client, _ = _razorpay_client()
                    order_info = client.order.fetch(order_id)
                    actual_amount = float(order_info["amount"]) / 100.0
                except Exception as _ord_err:
                    print(f"[WARN] Could not fetch Razorpay order details: {_ord_err}")
                    actual_amount = round(plan.price * 1.18, 2) if plan else 0

                cycle_label = "Yearly" if plan.name.lower() == "blue" else plan.billing_cycle.title()
                log_payment_transaction(
                    db                  = db,
                    user_id             = uid,
                    transaction_type    = "subscription",
                    amount              = actual_amount,
                    status              = "completed",
                    razorpay_order_id   = order_id,
                    razorpay_payment_id = payment_id,
                    razorpay_signature  = signature,
                    related_entity_type = "subscription",
                    related_entity_id   = sub.id,
                    description         = f"{plan.name} Plan ({cycle_label}) — {datetime.utcnow().strftime('%B %Y')}" if plan else "Plan Subscription",
                )
            except Exception as _log_err:
                print(f"[WARN] Could not log payment transaction: {_log_err}")
        return JSONResponse({"success": True})

    # ─────────────────────────────────────────────────────────────────────────
    # Auto-Renewal: Subscription Management Endpoints
    # ─────────────────────────────────────────────────────────────────────────

    @app.get("/api/subscription/status")
    async def api_subscription_status(request: Request, db: Session = Depends(get_db)):
        """Return full subscription status for the dashboard card."""
        uid = request.session.get("user_id")
        if not uid:
            return JSONResponse({"success": False}, status_code=401)
        ensure_default_subscription(uid, db)
        sub = get_active_subscription(uid, db)

        # If active sub is free (or missing), check for a paused PAID subscription.
        # This handles the case where ensure_default_subscription creates a free
        # subscription after the user pauses a paid plan.
        if not sub or (sub.plan and sub.plan.is_free):
            paused_paid = db.query(UserSubscription).filter(
                UserSubscription.user_id == uid,
                UserSubscription.status == "paused",
            ).order_by(UserSubscription.started_at.desc()).first()
            if paused_paid and paused_paid.plan and not paused_paid.plan.is_free:
                sub = paused_paid  # show paused paid plan so user can Resume

        if not sub:
            return JSONResponse({"success": True, "subscription": None})

        plan = sub.plan
        return JSONResponse({"success": True, "subscription": {
            "id":                   sub.id,
            "plan_id":              sub.plan_id,
            "plan_name":            plan.name if plan else "Unknown",
            "plan_price":           plan.price if plan else 0,
            "billing_cycle":        plan.billing_cycle if plan else "monthly",
            "is_free":              plan.is_free if plan else True,
            "status":               sub.status,
            "payment_status":       sub.payment_status,
            "started_at":           sub.started_at.isoformat() if sub.started_at else None,
            "expires_at":           sub.expires_at.isoformat() if sub.expires_at else None,
            "auto_renew":           bool(getattr(sub, "auto_renew", False)),
            "next_renewal_at":      sub.next_renewal_at.isoformat() if getattr(sub, "next_renewal_at", None) else None,
            "grace_period_used":    bool(getattr(sub, "grace_period_used", False)),
            "grace_period_ends_at": sub.grace_period_ends_at.isoformat() if getattr(sub, "grace_period_ends_at", None) else None,
            "pause_started_at":     sub.pause_started_at.isoformat() if getattr(sub, "pause_started_at", None) else None,
            "cancelled_at":         sub.cancelled_at.isoformat() if getattr(sub, "cancelled_at", None) else None,
        }})

    @app.post("/api/subscription/toggle-autorenew")
    async def api_toggle_autorenew(request: Request, db: Session = Depends(get_db)):
        """Toggle auto-renewal on/off."""
        uid = request.session.get("user_id")
        if not uid:
            return JSONResponse({"success": False}, status_code=401)
        sub = get_active_subscription(uid, db)
        if not sub:
            return JSONResponse({"success": False, "error": "No active subscription"}, status_code=404)
        if sub.plan and sub.plan.is_free:
            return JSONResponse({"success": False, "error": "Auto-renew is not available for free plans"}, status_code=400)
        try:
            current = bool(getattr(sub, "auto_renew", False))
            sub.auto_renew = not current
            if sub.auto_renew and sub.expires_at:
                sub.next_renewal_at = sub.expires_at
            else:
                sub.next_renewal_at = None
            db.commit()
            print(f"[AUTO-RENEW] User {uid} toggled auto_renew to {sub.auto_renew}")
            return JSONResponse({
                "success": True,
                "auto_renew": bool(sub.auto_renew),
                "next_renewal_at": sub.next_renewal_at.isoformat() if getattr(sub, "next_renewal_at", None) else None,
            })
        except Exception as e:
            db.rollback()
            return JSONResponse({"success": False, "error": str(e)}, status_code=500)

    @app.post("/api/subscription/pause")
    async def api_pause_subscription(request: Request, db: Session = Depends(get_db)):
        """Pause subscription. Access continues until billing cycle ends."""
        uid = request.session.get("user_id")
        if not uid:
            return JSONResponse({"success": False}, status_code=401)
        sub = get_active_subscription(uid, db)
        if not sub:
            return JSONResponse({"success": False, "error": "No active subscription to pause"}, status_code=404)
        if sub.plan and sub.plan.is_free:
            return JSONResponse({"success": False, "error": "Free plan cannot be paused"}, status_code=400)
        try:
            sub.status = "paused"
            sub.auto_renew = False
            sub.next_renewal_at = None
            try:
                sub.pause_started_at = datetime.utcnow()
            except Exception:
                pass
            db.commit()
            print(f"[AUTO-RENEW] User {uid} paused subscription {sub.id}")
            return JSONResponse({
                "success": True,
                "message": "Subscription paused. Your access continues until your billing cycle ends.",
                "expires_at": sub.expires_at.isoformat() if sub.expires_at else None,
            })
        except Exception as e:
            db.rollback()
            return JSONResponse({"success": False, "error": str(e)}, status_code=500)

    @app.post("/api/subscription/resume")
    async def api_resume_subscription(request: Request, db: Session = Depends(get_db)):
        """Resume a paused subscription."""
        uid = request.session.get("user_id")
        if not uid:
            return JSONResponse({"success": False}, status_code=401)
        sub = db.query(UserSubscription).filter(
            UserSubscription.user_id == uid,
            UserSubscription.status == "paused",
        ).order_by(UserSubscription.started_at.desc()).first()
        if not sub:
            return JSONResponse({"success": False, "error": "No paused subscription found"}, status_code=404)
        if sub.expires_at and sub.expires_at < datetime.utcnow():
            sub.status = "expired"
            db.commit()
            return JSONResponse({"success": False, "error": "Subscription has already expired. Please subscribe again."}, status_code=400)
        try:
            sub.status = "active"
            try:
                sub.pause_started_at = None
            except Exception:
                pass
            db.commit()
            print(f"[AUTO-RENEW] User {uid} resumed subscription {sub.id}")
            return JSONResponse({"success": True, "message": "Subscription resumed successfully."})
        except Exception as e:
            db.rollback()
            return JSONResponse({"success": False, "error": str(e)}, status_code=500)

    @app.post("/api/subscription/cancel")
    async def api_cancel_subscription(request: Request, db: Session = Depends(get_db)):
        """Cancel auto-renewal. Access continues until billing cycle ends."""
        uid = request.session.get("user_id")
        if not uid:
            return JSONResponse({"success": False}, status_code=401)
        sub = get_active_subscription(uid, db)
        if not sub:
            return JSONResponse({"success": False, "error": "No active subscription"}, status_code=404)
        if sub.plan and sub.plan.is_free:
            return JSONResponse({"success": False, "error": "Free plan cannot be cancelled"}, status_code=400)
        try:
            sub.auto_renew = False
            sub.next_renewal_at = None
            try:
                sub.cancelled_at = datetime.utcnow()
            except Exception:
                pass
            db.commit()
            print(f"[AUTO-RENEW] User {uid} cancelled auto-renew for subscription {sub.id}")
            return JSONResponse({
                "success": True,
                "message": "Auto-renewal cancelled. You retain access until your plan expires.",
                "expires_at": sub.expires_at.isoformat() if sub.expires_at else None,
            })
        except Exception as e:
            db.rollback()
            return JSONResponse({"success": False, "error": str(e)}, status_code=500)

    # ─────────────────────────────────────────────────────────────────────────
    # Plan Downgrade with Pro-Rated Refund
    # ─────────────────────────────────────────────────────────────────────────

    def _compute_downgrade_refund(current_sub, current_plan, new_plan, db):
        """
        Compute pro-rated refund for a plan downgrade (all amounts include 18% GST).

        Formula:
          deduction     = actual_amount_paid / billing_days × days_used  (min 1 day)
          refund_amount = actual_amount_paid − deduction − new_plan_price_with_gst
        """
        GST = 0.18
        billing_days = 365 if current_plan.billing_cycle in ("yearly", "annual") else 30
        days_used = max(1, (datetime.utcnow() - current_sub.started_at).days)

        # Prefer actual amount paid (with GST) from PaymentTransaction ledger
        from models import PaymentTransaction as _PT
        ptxn = None
        if current_sub.razorpay_payment_id:
            ptxn = db.query(_PT).filter(
                _PT.razorpay_payment_id == current_sub.razorpay_payment_id,
                _PT.status == "completed",
            ).first()

        if ptxn and ptxn.amount:
            previous_plan_paid = float(ptxn.amount)
        else:
            previous_plan_paid = round(current_plan.price * (1 + GST), 2)

        amount_to_deduct = round(previous_plan_paid / billing_days * days_used, 2)
        new_plan_cost_with_gst = round(new_plan.price * (1 + GST), 2) if not new_plan.is_free else 0.0
        refund_amount = round(previous_plan_paid - amount_to_deduct - new_plan_cost_with_gst, 2)
        refund_amount = max(0.0, refund_amount)

        return {
            "previous_plan_paid": previous_plan_paid,
            "billing_days": billing_days,
            "days_used": days_used,
            "amount_to_deduct": amount_to_deduct,
            "new_plan_cost_with_gst": new_plan_cost_with_gst,
            "refund_amount": refund_amount,
            "ptxn": ptxn,
        }

    @app.get("/api/plans/downgrade/preview")
    async def api_downgrade_preview(request: Request, plan_id: int, db: Session = Depends(get_db)):
        """Preview the pro-rated refund for a downgrade — no side effects."""
        uid = request.session.get("user_id")
        if not uid:
            return JSONResponse({"success": False, "error": "Not authenticated"}, status_code=401)
        try:
            current_sub = get_active_subscription(uid, db)
            if not current_sub or not current_sub.plan:
                return JSONResponse({"success": False, "error": "No active subscription found"}, status_code=400)

            current_plan = current_sub.plan
            new_plan = db.query(UsagePlan).filter(UsagePlan.id == plan_id, UsagePlan.is_active == True).first()
            if not new_plan:
                return JSONResponse({"success": False, "error": "Plan not found"}, status_code=404)

            if new_plan.price >= current_plan.price:
                return JSONResponse({"success": False, "error": "Target plan must be cheaper than current plan"}, status_code=400)

            b = _compute_downgrade_refund(current_sub, current_plan, new_plan, db)
            return JSONResponse({
                "success": True,
                "current_plan_name": current_plan.name,
                "new_plan_name": new_plan.name,
                "days_used": b["days_used"],
                "billing_days": b["billing_days"],
                "previous_plan_paid": b["previous_plan_paid"],
                "amount_to_deduct": b["amount_to_deduct"],
                "new_plan_cost_with_gst": b["new_plan_cost_with_gst"],
                "refund_amount": b["refund_amount"],
                "has_payment": bool(current_sub.razorpay_payment_id),
            })
        except Exception as _e:
            import traceback as _tb
            print(f"[ERROR] downgrade_preview: {_tb.format_exc()}")
            return JSONResponse({"success": False, "error": str(_e)}, status_code=500)

    @app.post("/api/plans/downgrade")
    async def api_plan_downgrade(request: Request, db: Session = Depends(get_db)):
        """
        Downgrade to a cheaper plan with a pro-rated Razorpay partial refund.
        New plan is activated immediately — its cost is deducted from the refund.
        """
        uid = request.session.get("user_id")
        if not uid:
            return JSONResponse({"success": False, "error": "Not authenticated"}, status_code=401)

        try:
            data = await request.json()
            new_plan_id = int(data.get("plan_id", 0))

            current_sub = get_active_subscription(uid, db)
            if not current_sub or not current_sub.plan:
                return JSONResponse({"success": False, "error": "No active subscription found"}, status_code=400)

            current_plan = current_sub.plan
            new_plan = db.query(UsagePlan).filter(
                UsagePlan.id == new_plan_id, UsagePlan.is_active == True
            ).first()
            if not new_plan:
                return JSONResponse({"success": False, "error": "Plan not found"}, status_code=404)

            if new_plan.price >= current_plan.price:
                return JSONResponse({"success": False, "error": "Target plan is not a downgrade"}, status_code=400)

            b = _compute_downgrade_refund(current_sub, current_plan, new_plan, db)
            refund_amount = b["refund_amount"]

            # ── Issue Razorpay partial refund ────────────────────────────────
            razorpay_refund_id = None
            refund_status = "skipped"
            if refund_amount > 0 and current_sub.razorpay_payment_id:
                try:
                    client, _ = _razorpay_client()
                    if client:
                        rz_resp = client.payment.refund(
                            current_sub.razorpay_payment_id,
                            {
                                "amount": int(refund_amount * 100),  # paise
                                "speed": "normal",
                                "notes": {
                                    "reason": f"Plan downgrade: {current_plan.name} → {new_plan.name}",
                                    "days_used": str(b["days_used"]),
                                    "amount_deducted": str(b["amount_to_deduct"]),
                                    "new_plan_cost": str(b["new_plan_cost_with_gst"]),
                                    "user_id": str(uid),
                                },
                            }
                        )
                        razorpay_refund_id = rz_resp.get("id")
                        refund_status = "completed"
                        print(f"[DOWNGRADE] Razorpay refund {razorpay_refund_id} — ₹{refund_amount} for user {uid}")

                        # Mark original PaymentTransaction as refunded
                        if b["ptxn"]:
                            b["ptxn"].status = "refunded"
                            b["ptxn"].refunded_at = datetime.utcnow()
                            b["ptxn"].refund_reason = (
                                f"Plan downgrade to {new_plan.name}. "
                                f"Days used: {b['days_used']}/{b['billing_days']}. "
                                f"Deducted: ₹{b['amount_to_deduct']}. "
                                f"New plan: ₹{b['new_plan_cost_with_gst']} (incl. GST). "
                                f"RZ Refund: {razorpay_refund_id}."
                            )
                except Exception as _rz_err:
                    print(f"[ERROR] Razorpay refund failed: {_rz_err}")
                    return JSONResponse(
                        {"success": False, "error": f"Refund processing failed: {str(_rz_err)}"},
                        status_code=500
                    )

            # ── Cancel current subscription ──────────────────────────────────
            current_sub.status = "cancelled"
            db.flush()

            # ── Activate new plan immediately ────────────────────────────────
            new_sub = None
            if new_plan.is_free:
                ensure_default_subscription(uid, db)
            else:
                new_sub = UserSubscription(
                    user_id=uid,
                    plan_id=new_plan.id,
                    status="active",
                    started_at=datetime.utcnow(),
                    expires_at=_compute_expiry(new_plan.billing_cycle),
                    auto_renew=True,
                    razorpay_payment_id=None,  # cost deducted from refund
                )
                db.add(new_sub)
                db.flush()

            # ── Log refund in PaymentTransaction ledger ──────────────────────
            try:
                from finance_routes import log_payment_transaction
                log_payment_transaction(
                    db=db,
                    user_id=uid,
                    transaction_type="refund",
                    amount=-round(refund_amount, 2),   # negative = money out to user
                    status=refund_status,
                    razorpay_payment_id=current_sub.razorpay_payment_id,
                    related_entity_type="subscription",
                    related_entity_id=current_sub.id,
                    description=(
                        f"Pro-rated refund: {current_plan.name} → {new_plan.name}. "
                        f"Days used: {b['days_used']}/{b['billing_days']}. "
                        f"Deducted: ₹{b['amount_to_deduct']}. "
                        f"New plan: ₹{b['new_plan_cost_with_gst']} (incl. GST). "
                        f"RZ Refund ID: {razorpay_refund_id or 'N/A'}."
                    ),
                )
            except Exception as _log_err:
                print(f"[WARN] Could not log downgrade refund transaction: {_log_err}")

            db.commit()

            return JSONResponse({
                "success": True,
                "new_plan": new_plan.name,
                "refund_amount": refund_amount,
                "razorpay_refund_id": razorpay_refund_id,
                "days_used": b["days_used"],
                "amount_deducted": b["amount_to_deduct"],
                "new_plan_cost": b["new_plan_cost_with_gst"],
                "message": (
                    f"Downgraded to {new_plan.name} plan. ₹{refund_amount:.2f} refund initiated."
                    if refund_amount > 0
                    else f"Downgraded to {new_plan.name} plan."
                ),
            })

        except Exception as _e:
            db.rollback()
            import traceback as _tb
            print(f"[ERROR] api_plan_downgrade: {_tb.format_exc()}")
            return JSONResponse({"success": False, "error": str(_e)}, status_code=500)

    # ─────────────────────────────────────────────────────────────────────────
    # Auto-Renewal: Daily Cron Endpoint (GCP Cloud Scheduler → 9 AM IST daily)
    # ─────────────────────────────────────────────────────────────────────────

    def _downgrade_to_free_inner(user_id: int, db):
        """Cancel active subscription and enrol user in default free plan."""
        try:
            db.query(UserSubscription).filter(
                UserSubscription.user_id == user_id,
                UserSubscription.status.in_(["active", "paused"]),
            ).update({"status": "cancelled"}, synchronize_session=False)
            db.commit()
        except Exception as _ce:
            db.rollback()
            print(f"[AUTO-RENEW] Could not cancel sub on downgrade: {_ce}")
        ensure_default_subscription(user_id, db)

    @app.post("/api/internal/daily-renewal-check")
    async def api_daily_renewal_check(request: Request, db: Session = Depends(get_db)):
        """
        Called by GCP Cloud Scheduler at 03:30 UTC (09:00 AM IST) every day.
        Secret auth via INTERNAL_CRON_SECRET env var in request body.
        """
        import os as _os
        try:
            body = await request.json()
        except Exception:
            body = {}
        secret = body.get("secret", "")
        expected_secret = _os.getenv("INTERNAL_CRON_SECRET", "")
        if not expected_secret or secret != expected_secret:
            return JSONResponse({"success": False, "error": "Forbidden"}, status_code=403)

        now = datetime.utcnow()
        today = now.date()
        tomorrow = today + timedelta(days=1)
        results = {
            "reminders_sent": 0, "renewals_attempted": 0,
            "renewals_succeeded": 0, "renewals_failed": 0,
            "downgrades": 0, "grace_periods_started": 0,
            "recordings_deleted": 0,
        }

        try:
            from models import User as UserModel
            from sendgrid_email import (
                send_renewal_reminder_email,
                send_payment_receipt_email,
                send_renewal_failed_email,
            )
        except ImportError as _ie:
            print(f"[AUTO-RENEW] Import error: {_ie}")
            return JSONResponse({"success": False, "error": str(_ie)}, status_code=500)

        # ── Step 1: Renewal reminders (next_renewal_at = tomorrow) ───────────
        try:
            all_active = db.query(UserSubscription).filter(
                UserSubscription.status == "active",
            ).all()
            for sub in all_active:
                try:
                    if not getattr(sub, "auto_renew", False):
                        continue
                    nra = getattr(sub, "next_renewal_at", None)
                    if not nra or nra.date() != tomorrow:
                        continue
                    user = db.query(UserModel).filter(UserModel.id == sub.user_id).first()
                    plan = sub.plan
                    if not user or not plan or plan.is_free:
                        continue
                    try:
                        renewal_str = nra.strftime("%d %B %Y").lstrip("0")
                    except Exception:
                        renewal_str = str(nra.date())
                    send_renewal_reminder_email(
                        to_email=user.email, user_name=user.name,
                        plan_name=plan.name, amount=round(plan.price * 1.18, 2),
                        renewal_date=renewal_str,
                    )
                    results["reminders_sent"] += 1
                    print(f"[AUTO-RENEW] Reminder → {user.email}")
                except Exception as _re:
                    print(f"[AUTO-RENEW] Reminder error sub {sub.id}: {_re}")
        except Exception as _e:
            print(f"[AUTO-RENEW] Reminder loop: {_e}")

        # ── Step 2: Process renewals due today ────────────────────────────────
        try:
            for sub in db.query(UserSubscription).filter(UserSubscription.status == "active").all():
                try:
                    if not getattr(sub, "auto_renew", False):
                        continue
                    nra = getattr(sub, "next_renewal_at", None)
                    if not nra or nra.date() != today:
                        continue
                    user = db.query(UserModel).filter(UserModel.id == sub.user_id).first()
                    plan = sub.plan
                    if not user or not plan or plan.is_free:
                        continue

                    results["renewals_attempted"] += 1
                    client, _ = _razorpay_client()
                    charged = False
                    new_order_id = None
                    if client:
                        try:
                            new_order = client.order.create({
                                "amount": int(round(plan.price * 1.18, 2) * 100), "currency": "INR",
                                "notes": {"type": "auto_renewal", "sub_id": str(sub.id), "user_id": str(user.id)},
                            })
                            new_order_id = new_order["id"]
                            charged = True  # order created; actual debit via mandate/webhook
                        except Exception as _rze:
                            print(f"[AUTO-RENEW] Razorpay order error {user.email}: {_rze}")

                    if charged:
                        sub.expires_at = _compute_expiry(plan.billing_cycle)
                        sub.next_renewal_at = sub.expires_at
                        sub.renewal_fail_count = 0
                        sub.started_at = datetime.utcnow()
                        sub.razorpay_order_id = new_order_id
                        db.commit()
                        results["renewals_succeeded"] += 1
                        try:
                            from models import PaymentTransaction as PT
                            count = db.query(PT).count()
                            invoice_num = f"SS-{datetime.utcnow().year}-{count + 1:05d}"
                            next_str = sub.next_renewal_at.strftime("%d %B %Y").lstrip("0")
                            send_payment_receipt_email(
                                to_email=user.email, user_name=user.name,
                                plan_name=plan.name, amount=round(plan.price * 1.18, 2),
                                invoice_number=invoice_num, next_renewal_date=next_str,
                            )
                        except Exception as _re:
                            print(f"[AUTO-RENEW] Receipt email error: {_re}")
                    else:
                        results["renewals_failed"] += 1
                        grace_used = bool(getattr(sub, "grace_period_used", False))
                        if not grace_used:
                            grace_end = datetime.utcnow() + timedelta(days=3)
                            try:
                                sub.grace_period_used = True
                                sub.grace_period_ends_at = grace_end
                                sub.renewal_fail_count = 1
                            except Exception:
                                pass
                            db.commit()
                            results["grace_periods_started"] += 1
                            try:
                                grace_str = grace_end.strftime("%d %B %Y").lstrip("0")
                                send_renewal_failed_email(
                                    to_email=user.email, user_name=user.name,
                                    plan_name=plan.name, grace_period_ends=grace_str,
                                    is_final_notice=False,
                                )
                            except Exception as _me:
                                print(f"[AUTO-RENEW] Grace email error: {_me}")
                            print(f"[AUTO-RENEW] Grace started for {user.email}")
                        else:
                            _downgrade_to_free_inner(sub.user_id, db)
                            results["downgrades"] += 1
                            try:
                                send_renewal_failed_email(
                                    to_email=user.email, user_name=user.name,
                                    plan_name=plan.name, grace_period_ends="",
                                    is_final_notice=True,
                                )
                            except Exception:
                                pass
                            print(f"[AUTO-RENEW] Downgraded {user.email} (no grace left)")
                except Exception as _se:
                    print(f"[AUTO-RENEW] Sub {sub.id} error: {_se}")
        except Exception as _e:
            print(f"[AUTO-RENEW] Renewal loop: {_e}")

        # ── Step 3: Grace period expiry ───────────────────────────────────────
        try:
            for sub in db.query(UserSubscription).filter(UserSubscription.status == "active").all():
                try:
                    gpe = getattr(sub, "grace_period_ends_at", None)
                    if not gpe or gpe.date() != today:
                        continue
                    if getattr(sub, "auto_renew", False):
                        continue  # handled above in renewal loop
                    user = db.query(UserModel).filter(UserModel.id == sub.user_id).first()
                    plan = sub.plan
                    if not user or not plan or plan.is_free:
                        continue
                    _downgrade_to_free_inner(sub.user_id, db)
                    results["downgrades"] += 1
                    try:
                        send_renewal_failed_email(
                            to_email=user.email, user_name=user.name,
                            plan_name=plan.name, grace_period_ends="",
                            is_final_notice=True,
                        )
                    except Exception:
                        pass
                    print(f"[AUTO-RENEW] Grace expired → downgraded {user.email}")
                except Exception as _ge:
                    print(f"[AUTO-RENEW] Grace expiry error sub {sub.id}: {_ge}")
        except Exception as _e:
            print(f"[AUTO-RENEW] Grace loop: {_e}")

        # ── Step 4: GCS Call Recording Retention Policy ───────────────────────────
        try:
            print("[RETENTION] Starting GCS call recording retention check...")
            from models import CallSession
            
            # Fetch all call sessions with a recording
            sessions = db.query(CallSession).filter(CallSession.recording_url.isnot(None)).all()
            deleted_count = 0
            
            for session in sessions:
                try:
                    # Resolve active plan
                    sub = get_active_subscription(session.user_id, db)
                    plan_name = sub.plan.name if (sub and sub.plan) else "Free"
                    
                    # Blue plans get 365 days; Green plans get 30 days; Free / White / others get 0 days (deleted immediately)
                    if plan_name == "Blue":
                        retention_days = 365
                    elif plan_name == "Green":
                        retention_days = 30
                    else:
                        retention_days = 0
                    
                    session_date = session.actual_start or session.created_at
                    age = now - session_date
                    
                    if age.days >= retention_days:
                        # Expired, let's delete
                        print(f"[RETENTION] CallSession {session.id} (user {session.user_id}, plan {plan_name}) recording is {age.days} days old (limit: {retention_days} days) - deleting...")
                        
                        url = session.recording_url
                        success = False
                        try:
                            if url.startswith("gs://"):
                                parts = url[5:].split("/", 1)
                                b_name = parts[0]
                                bl_name = parts[1]
                            elif "storage.googleapis.com/" in url:
                                after = url.split("storage.googleapis.com/", 1)[1]
                                parts = after.split("/", 1)
                                b_name = parts[0]
                                bl_name = parts[1]
                            else:
                                b_name, bl_name = None, None
                                
                            if b_name and bl_name:
                                from google.cloud import storage
                                client = storage.Client()
                                bucket = client.bucket(b_name)
                                blob = bucket.blob(bl_name)
                                if blob.exists():
                                    blob.delete()
                                    print(f"[RETENTION] Deleted blob {bl_name} from bucket {b_name}")
                                success = True
                            else:
                                print(f"[RETENTION] Could not parse GCS URL: {url}")
                        except Exception as _gcs_err:
                            print(f"[RETENTION] GCS deletion error for session {session.id}: {_gcs_err}")
                            # Proceed to clear DB columns anyway if blob doesn't exist/can't delete
                            success = True
                        
                        if success:
                            session.recording_url = None
                            session.recording_size_bytes = None
                            db.commit()
                            deleted_count += 1
                except Exception as _sess_err:
                    print(f"[RETENTION] Error processing session {session.id}: {_sess_err}")
            
            results["recordings_deleted"] = deleted_count
            print(f"[RETENTION] Finished retention check. Deleted {deleted_count} recording(s).")
        except Exception as _ret_err:
            print(f"[RETENTION] Main loop error: {_ret_err}")

        print(f"[AUTO-RENEW] Daily check done: {results}")
        return JSONResponse({"success": True, "results": results})



    @app.post("/api/internal/hourly-appointment-reminder")
    async def api_hourly_appointment_reminder(request: Request, db: Session = Depends(get_db)):
        """
        Called by GCP Cloud Scheduler every hour to check for upcoming appointments today.
        Sends email reminders to user, consultant, and admin when local time enters the day of the appointment.
        """
        import os as _os
        from datetime import datetime
        try:
            body = await request.json()
        except Exception:
            body = {}
        secret = body.get("secret", "")
        expected_secret = _os.getenv("INTERNAL_CRON_SECRET", "")
        if not expected_secret or secret != expected_secret:
            return JSONResponse({"success": False, "error": "Forbidden"}, status_code=403)

        now_utc = datetime.utcnow()
        reminders_sent = 0

        try:
            from models import Appointment as AppointmentModel, User as UserModel, ConsultantProfile as ConsultantProfileModel
            from sendgrid_email import send_appointment_reminder_email
            import timezone_utils
        except ImportError as _ie:
            print(f"[REMINDER] Import error: {_ie}")
            return JSONResponse({"success": False, "error": str(_ie)}, status_code=500)

        try:
            is_mirror = _os.getenv("ENVIRONMENT") == "mirror"
            # Query all scheduled future appointments based on environment
            if is_mirror:
                appointments = db.query(AppointmentModel).filter(
                    AppointmentModel.status == "scheduled",
                    AppointmentModel.is_test == True,
                    AppointmentModel.mirror_reminder_sent == False,
                    AppointmentModel.appointment_date > now_utc
                ).all()
            else:
                from sqlalchemy import or_
                appointments = db.query(AppointmentModel).filter(
                    AppointmentModel.status == "scheduled",
                    AppointmentModel.reminder_sent == False,
                    AppointmentModel.appointment_date > now_utc,
                    or_(
                        AppointmentModel.is_test == False,
                        AppointmentModel.is_test == None,
                        AppointmentModel.mirror_reminder_sent == True
                    )
                ).all()

            for appt in appointments:
                try:
                    # Get user and consultant profile
                    user = db.query(UserModel).filter(UserModel.id == appt.user_id).first()
                    consultant_profile = db.query(ConsultantProfileModel).filter(ConsultantProfileModel.id == appt.consultant_id).first()
                    if not user or not consultant_profile:
                        continue
                    
                    consultant_user = db.query(UserModel).filter(UserModel.id == consultant_profile.user_id).first()
                    if not consultant_user:
                        continue

                    # Get user's timezone (default to India/IST or UTC)
                    user_tz = getattr(user, "timezone", "Asia/Kolkata") or "Asia/Kolkata"

                    # Convert now_utc and appointment_date to user's local timezone
                    now_local = timezone_utils.to_local(now_utc, user_tz)
                    appt_local = timezone_utils.to_local(appt.appointment_date, user_tz)

                    # Send reminder if now_local has entered the day of the appointment
                    if now_local.date() == appt_local.date():
                        # Send emails
                        # 1. To User
                        send_appointment_reminder_email(
                            recipient_type="user",
                            to_email="admin@solacesquad.com" if is_mirror else user.email,
                            user_name=user.name,
                            consultant_name=consultant_user.name,
                            appointment_date_utc=appt.appointment_date,
                            duration_minutes=appt.duration_minutes,
                            appointment_id=appt.id,
                            user_timezone=user_tz
                        )

                        # 2. To Consultant
                        send_appointment_reminder_email(
                            recipient_type="consultant",
                            to_email="admin@solacesquad.com" if is_mirror else consultant_user.email,
                            user_name=user.name,
                            consultant_name=consultant_user.name,
                            appointment_date_utc=appt.appointment_date,
                            duration_minutes=appt.duration_minutes,
                            appointment_id=appt.id,
                            user_timezone=user_tz
                        )

                        # 3. To Admin (admin@solacesquad.com)
                        send_appointment_reminder_email(
                            recipient_type="admin",
                            to_email="admin@solacesquad.com",
                            user_name=user.name,
                            consultant_name=consultant_user.name,
                            appointment_date_utc=appt.appointment_date,
                            duration_minutes=appt.duration_minutes,
                            appointment_id=appt.id,
                            user_timezone=user_tz
                        )

                        if not is_mirror:
                            appt.reminder_sent = True
                            db.commit()
                            reminders_sent += 1
                            print(f"[REMINDER] Sent reminder for appointment {appt.id} between {user.email} and {consultant_user.email}")
                        else:
                            appt.mirror_reminder_sent = True
                            db.commit()
                            reminders_sent += 1
                            print(f"[REMINDER - REVIEW MODE] Sent review copies to admin for appointment {appt.id}")
                except Exception as _appt_err:
                    db.rollback()
                    print(f"[REMINDER] Error processing appointment {appt.id}: {_appt_err}")

        except Exception as _run_err:
            print(f"[REMINDER] Main scan loop error: {_run_err}")
            return JSONResponse({"success": False, "error": str(_run_err)}, status_code=500)

        return JSONResponse({"success": True, "reminders_sent": reminders_sent})

    @app.post("/api/internal/send-push-reminders")
    async def api_send_push_reminders(request: Request, db: Session = Depends(get_db)):
        """
        Called by Cloud Scheduler every 10 minutes to process push reminders:
        Matches delivery time boundaries against user's local timezone and executes conditional alerts.
        """
        import os as _os
        from datetime import datetime, timedelta
        from sqlalchemy import or_, func
        try:
            body = await request.json()
        except Exception:
            body = {}
        secret = body.get("secret", "")
        expected_secret = _os.getenv("INTERNAL_CRON_SECRET", "")
        if not expected_secret or secret != expected_secret:
            return JSONResponse({"success": False, "error": "Forbidden"}, status_code=403)

        force = bool(body.get("force", False))

        from push_utils import send_push_notification
        from models import (
            Appointment as AppointmentModel, 
            User as UserModel, 
            VitalsRecord as VitalsModel, 
            MoodEntry as MoodModel, 
            WorkoutLog as WorkoutModel,
            PushNotificationSchedule,
            UserDeviceToken
        )
        import timezone_utils

        now_utc = datetime.utcnow()
        is_mirror = _os.getenv("ENVIRONMENT") == "mirror"
        pushes_sent = 0

        # Load configuration schedules
        schedules_list = db.query(PushNotificationSchedule).all()
        schedules = {s.notification_type: s for s in schedules_list}

        # Helper to match timing
        def is_matching_time(now_local, schedule):
            if not schedule or not schedule.is_enabled:
                return False
            if force:
                return True
            
            cycle = schedule.repeat_cycle.lower()
            
            # Parse delivery time
            d_hour, d_minute = 9, 0
            if schedule.delivery_time:
                try:
                    d_hour, d_minute = map(int, schedule.delivery_time.split(":"))
                except Exception:
                    pass
                    
            if cycle == "hourly":
                return now_local.minute < 15
            elif cycle == "daily":
                return now_local.hour == d_hour and now_local.minute < 15
            elif cycle == "weekly":
                target_day = schedule.day_of_week if schedule.day_of_week is not None else 0
                return now_local.weekday() == target_day and now_local.hour == d_hour and now_local.minute < 15
            elif cycle == "monthly":
                target_day = schedule.day_of_month if schedule.day_of_month is not None else 1
                return now_local.day == target_day and now_local.hour == d_hour and now_local.minute < 15
                
            return False

        # -------------------------------------------------------------
        # 1. 30-Minute Appointment Reminders
        # -------------------------------------------------------------
        appt_sched = schedules.get("appointment_reminder")
        if appt_sched and appt_sched.is_enabled:
            time_limit = now_utc + timedelta(minutes=35)
            if is_mirror:
                appointments = db.query(AppointmentModel).filter(
                    AppointmentModel.status == "scheduled",
                    AppointmentModel.is_test == True,
                    AppointmentModel.mirror_push_30m_sent == False,
                    AppointmentModel.appointment_date > now_utc,
                    AppointmentModel.appointment_date <= time_limit
                ).all()
            else:
                appointments = db.query(AppointmentModel).filter(
                    AppointmentModel.status == "scheduled",
                    AppointmentModel.push_30m_sent == False,
                    AppointmentModel.appointment_date > now_utc,
                    AppointmentModel.appointment_date <= time_limit,
                    or_(
                        AppointmentModel.is_test == False,
                        AppointmentModel.is_test == None,
                        AppointmentModel.mirror_push_30m_sent == True
                    )
                ).all()

            for appt in appointments:
                try:
                    user = db.query(UserModel).filter(UserModel.id == appt.user_id).first()
                    if user:
                        title = appt_sched.title
                        body_text = appt_sched.body
                        path = "/app/appointments"
                        sent = send_push_notification(db, user.id, title, body_text, path)
                        if sent:
                            pushes_sent += 1
                    
                    if is_mirror:
                        appt.mirror_push_30m_sent = True
                    else:
                        appt.push_30m_sent = True
                    db.commit()
                except Exception as e:
                    db.rollback()
                    print(f"[Push Scheduler] Error sending appt push: {e}")

        # -------------------------------------------------------------
        # 2. Dynamic Configured Check-ins & Warnings
        # -------------------------------------------------------------
        users_with_devices = db.query(UserModel).join(UserDeviceToken).distinct().all()
        for user in users_with_devices:
            try:
                user_tz = getattr(user, "timezone", "Asia/Kolkata") or "Asia/Kolkata"
                now_local = timezone_utils.to_local(now_utc, user_tz)
                today_local = now_local.date()

                # A. Mood Check-ins
                mood_sched = schedules.get("mood_checkin")
                if is_matching_time(now_local, mood_sched):
                    mood_today = db.query(MoodModel).filter(
                        MoodModel.user_id == user.id,
                        func.date(MoodModel.timestamp) == today_local
                    ).first()
                    if not mood_today:
                        send_push_notification(db, user.id, mood_sched.title, mood_sched.body, "/mood")
                        pushes_sent += 1

                # B. Vital Scan Check-ins
                vital_sched = schedules.get("vital_scan")
                if is_matching_time(now_local, vital_sched):
                    vitals_today = db.query(VitalsModel).filter(
                        VitalsModel.user_id == user.id,
                        func.date(VitalsModel.timestamp) == today_local
                    ).first()
                    if not vitals_today:
                        send_push_notification(db, user.id, vital_sched.title, vital_sched.body, "/vitals")
                        pushes_sent += 1

                # C. Workout Logs
                workout_sched = schedules.get("workout_log")
                if is_matching_time(now_local, workout_sched):
                    workout_today = db.query(WorkoutModel).filter(
                        WorkoutModel.user_id == user.id,
                        WorkoutModel.log_date == today_local
                    ).first()
                    if not workout_today:
                        send_push_notification(db, user.id, workout_sched.title, workout_sched.body, "/workout")
                        pushes_sent += 1

                # D. Recharge Reminders (Plan expiry)
                recharge_sched = schedules.get("recharge_reminder")
                if recharge_sched and recharge_sched.is_enabled:
                    if force or (now_local.hour == 10 and now_local.minute < 15):
                        active_sub = get_active_subscription(user.id, db)
                        if active_sub and active_sub.expires_at:
                            days_left = (active_sub.expires_at - now_utc).days
                            threshold = recharge_sched.threshold_value or 3
                            if days_left == threshold:
                                send_push_notification(db, user.id, recharge_sched.title, recharge_sched.body, "/app/plans")
                                pushes_sent += 1

                # E. Emora Low Balance Warnings
                emora_sched = schedules.get("emora_low_balance")
                if emora_sched and emora_sched.is_enabled:
                    if force or (now_local.hour == 11 and now_local.minute < 15):
                        quota_res = check_feature_limit(user.id, "ai_chat", db)
                        limit = quota_res.get("limit", 0)
                        used = quota_res.get("used", 0)
                        if limit > 0:
                            rem = limit - used
                            thresh = emora_sched.threshold_value or 5
                            if 0 < rem <= thresh:
                                send_push_notification(db, user.id, emora_sched.title, emora_sched.body, "/app/plans")
                                pushes_sent += 1

            except Exception as u_err:
                print(f"[Push Scheduler] Error processing user schedules: {u_err}")

        return JSONResponse({"success": True, "pushes_sent": pushes_sent})


    # ── User API: top-up (pay to extend) ──────────────────────────────────────────

    @app.post("/api/plans/top-up")
    async def api_top_up(request: Request, db: Session = Depends(get_db)):
        uid = request.session.get("user_id")
        if not uid:
            return JSONResponse({"success": False}, status_code=401)
        data = await request.json()
        feature_key = data.get("feature_key")

        caps = get_user_plan_caps(uid, db)
        cap  = caps.get(feature_key)
        if not cap or cap.extend_price <= 0:
            return JSONResponse({"success": False, "error": "Top-up not available"}, status_code=400)

        client, _ = _razorpay_client()
        if not client:
            return JSONResponse({"success": False, "error": "Payment gateway not configured"}, status_code=503)

        # ── Plan-based top-up discount (e.g. Blue plan: 25% off Emora packs) ──
        base_price   = cap.extend_price
        disc_pct     = 0
        disc_amount  = 0.0
        disc_cap     = caps.get("emora_pack_discount")
        if disc_cap and disc_cap.limit_value > 0 and feature_key == "ai_chat":
            disc_pct    = int(disc_cap.limit_value)
            disc_amount = round(base_price * disc_pct / 100, 2)
            base_price  = round(base_price - disc_amount, 2)

        # Add 18% GST
        gst_amount_topup = round(base_price * 0.18, 2)
        base_price_with_gst = round(base_price + gst_amount_topup, 2)
        amount_paise = int(base_price_with_gst * 100)

        period_key = _get_period_key(feature_key)
        order = client.order.create({
            "amount": amount_paise, "currency": "INR",
            "notes": {"feature_key": feature_key, "user_id": str(uid), "period_key": period_key},
        })
        top_up = FeatureUsageTopUp(
            user_id=uid, feature_key=feature_key, month_key=period_key,
            quota_added=cap.extend_quota, amount_paid=base_price_with_gst,
            razorpay_order_id=order["id"], status="pending",
        )
        db.add(top_up)
        db.commit()
        return JSONResponse({
            "success": True, "order_id": order["id"],
            "amount": amount_paise, "currency": "INR",
            "quota_to_add": cap.extend_quota,
            "discount_pct": disc_pct,
            "discount_amount": disc_amount,
            "original_amount": int(round(cap.extend_price * 1.18, 2) * 100),
        })

    @app.post("/api/plans/top-up/verify")
    async def api_top_up_verify(request: Request, db: Session = Depends(get_db)):
        uid = request.session.get("user_id")
        if not uid:
            return JSONResponse({"success": False}, status_code=401)
        data = await request.json()
        order_id   = data.get("razorpay_order_id")
        payment_id = data.get("razorpay_payment_id")
        signature  = data.get("razorpay_signature")

        _, key_secret = _razorpay_client()
        if not key_secret:
            return JSONResponse({"success": False, "error": "Gateway not configured"}, status_code=503)

        expected = hmac.new(key_secret.encode(), f"{order_id}|{payment_id}".encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, signature or ""):
            return JSONResponse({"success": False, "error": "Payment verification failed"}, status_code=400)

        top_up = db.query(FeatureUsageTopUp).filter(
            FeatureUsageTopUp.user_id == uid,
            FeatureUsageTopUp.razorpay_order_id == order_id,
        ).first()
        if top_up:
            top_up.status = "paid"
            top_up.razorpay_payment_id = payment_id
            db.commit()
            # Log to unified payment ledger
            try:
                from finance_routes import log_payment_transaction
                feat_labels = {
                    "ai_chat": "Emora Chat Buddy",
                    "consultant_sessions": "Consultant Sessions",
                    "vitals_scans": "Vitals Scans",
                    "journal_entries": "Journal Entries",
                }
                feat_label = feat_labels.get(top_up.feature_key, top_up.feature_key.replace("_", " ").title())
                log_payment_transaction(
                    db                  = db,
                    user_id             = uid,
                    transaction_type    = "top_up",
                    amount              = top_up.amount_paid,
                    status              = "completed",
                    razorpay_order_id   = order_id,
                    razorpay_payment_id = payment_id,
                    razorpay_signature  = signature,
                    related_entity_type = "top_up",
                    related_entity_id   = top_up.id,
                    description         = f"{feat_label} Top-Up — +{top_up.quota_added} units",
                )
            except Exception as _log_err:
                print(f"[WARN] Could not log top-up transaction: {_log_err}")
        return JSONResponse({"success": True})

    # ── Emora Pack Store (S / M / L) ───────────────────────────────────────────────────
    #
    # Lifetime Emora message packs — purchased once, never expire.
    # Blue plan users automatically get 25% off via emora_pack_discount cap.
    # month_key is set to "lifetime" in FeatureUsageTopUp so check_feature_limit
    # always includes these messages in the user’s balance.
    # ─────────────────────────────────────────────────────────────────

    _EMORA_PACKS = {
        "S": {"name": "Emora Pack S", "messages": 5_000,   "price": 500,  "colour": "#0d9488"},
        "M": {"name": "Emora Pack M", "messages": 25_000,  "price": 2000, "colour": "#7c3aed"},
        "L": {"name": "Emora Pack L", "messages": 100_000, "price": 5000, "colour": "#dc2626"},
    }

    @app.get("/api/emora-packs")
    async def api_list_emora_packs(request: Request, db: Session = Depends(get_db)):
        """Return available Emora packs with the authenticated user’s discounted prices."""
        uid = request.session.get("user_id")
        disc_pct = 0
        if uid:
            try:
                caps     = get_user_plan_caps(uid, db)
                disc_cap = caps.get("emora_pack_discount")
                if disc_cap and disc_cap.limit_value > 0:
                    disc_pct = int(disc_cap.limit_value)
            except Exception:
                pass

        packs = []
        for key, p in _EMORA_PACKS.items():
            orig   = p["price"]
            saving = round(orig * disc_pct / 100)
            final  = orig - saving
            packs.append({
                "pack_id":        key,
                "name":           p["name"],
                "messages":       p["messages"],
                "original_price": orig,
                "price":          final,
                "discount_pct":   disc_pct,
                "saving":         saving,
                "colour":         p["colour"],
            })
        return JSONResponse({"success": True, "packs": packs, "currency": "INR"})

    @app.post("/api/emora-packs/buy")
    async def api_buy_emora_pack(request: Request, db: Session = Depends(get_db)):
        """Create a Razorpay order for an Emora pack. Applies Blue-plan discount automatically."""
        uid = request.session.get("user_id")
        if not uid:
            return JSONResponse({"success": False, "error": "Not authenticated"}, status_code=401)

        data    = await request.json()
        pack_id = (data.get("pack_id") or "").upper()
        pack    = _EMORA_PACKS.get(pack_id)
        if not pack:
            return JSONResponse({"success": False, "error": f"Unknown pack '{pack_id}'. Valid: S, M, L"}, status_code=400)

        # Apply Blue-plan discount if applicable
        base_price = float(pack["price"])
        disc_pct   = 0
        disc_amount= 0.0
        try:
            caps     = get_user_plan_caps(uid, db)
            disc_cap = caps.get("emora_pack_discount")
            if disc_cap and disc_cap.limit_value > 0:
                disc_pct    = int(disc_cap.limit_value)
                disc_amount = round(base_price * disc_pct / 100, 2)
                base_price  = round(base_price - disc_amount, 2)
        except Exception:
            pass

        # Apply Voucher if present
        voucher_code = data.get("voucher_code")
        voucher_discount = 0.0
        if voucher_code:
            voucher_res = _validate_voucher_internal(db, uid, voucher_code, "package", pack_id, base_price)
            if not voucher_res["valid"]:
                return JSONResponse({"success": False, "error": voucher_res["error"]}, status_code=400)
            voucher_discount = voucher_res["discount_amount"]
            base_price = voucher_res["final_price"]

        # Add 18% GST
        gst_amount_pack = round(base_price * 0.18, 2)
        base_price_with_gst = round(base_price + gst_amount_pack, 2)
        amount_paise = int(base_price_with_gst * 100)

        if amount_paise == 0:
            top_up = FeatureUsageTopUp(
                user_id           = uid,
                feature_key       = "ai_chat",
                month_key         = "lifetime",
                quota_added       = pack["messages"],
                amount_paid       = 0.0,
                status            = "paid",
                voucher_code      = voucher_code,
            )
            db.add(top_up)
            db.commit()

            # Log to unified payment ledger
            try:
                from finance_routes import log_payment_transaction
                log_payment_transaction(
                    db                  = db,
                    user_id             = uid,
                    transaction_type    = "emora_pack",
                    amount              = 0.0,
                    status              = "completed",
                    related_entity_type = "feature_top_up",
                    related_entity_id   = top_up.id,
                    description         = f"Emora Pack — +{top_up.quota_added:,} lifetime messages (Voucher 100% discount)",
                )
            except Exception as _e:
                print(f"[WARN] Could not log emora pack transaction: {_e}")

            return JSONResponse({
                "success":           True,
                "activated":         True,
                "messages_credited": top_up.quota_added,
                "validity":          "lifetime",
            })

        client, _ = _razorpay_client()
        if not client:
            return JSONResponse({"success": False, "error": "Payment gateway not configured"}, status_code=503)

        order = client.order.create({
            "amount":   amount_paise,
            "currency": "INR",
            "receipt":  f"ep-{pack_id}-{uid}-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}",
            "notes":    {"pack_id": pack_id, "user_id": str(uid), "messages": str(pack["messages"])},
        })

        # Pre-create a pending FeatureUsageTopUp with month_key="lifetime"
        top_up = FeatureUsageTopUp(
            user_id           = uid,
            feature_key       = "ai_chat",
            month_key         = "lifetime",
            quota_added       = pack["messages"],
            amount_paid       = base_price_with_gst,
            razorpay_order_id = order["id"],
            status            = "pending",
            voucher_code      = voucher_code,
        )
        db.add(top_up)
        db.commit()

        return JSONResponse({
            "success":         True,
            "order_id":        order["id"],
            "amount":          amount_paise,
            "currency":        "INR",
            "pack_id":         pack_id,
            "pack_name":       pack["name"],
            "messages":        pack["messages"],
            "discount_pct":    disc_pct,
            "discount_amount": disc_amount,
            "original_amount": int(round(pack["price"] * 1.18, 2) * 100),
        })

    @app.post("/api/emora-packs/verify")

    async def api_verify_emora_pack(request: Request, db: Session = Depends(get_db)):
        """Verify Razorpay payment and credit lifetime Emora messages to the user’s balance."""
        uid = request.session.get("user_id")
        if not uid:
            return JSONResponse({"success": False, "error": "Not authenticated"}, status_code=401)

        data       = await request.json()
        order_id   = data.get("razorpay_order_id")
        payment_id = data.get("razorpay_payment_id")
        signature  = data.get("razorpay_signature")

        _, key_secret = _razorpay_client()
        if not key_secret:
            return JSONResponse({"success": False, "error": "Gateway not configured"}, status_code=503)

        expected = hmac.new(key_secret.encode(), f"{order_id}|{payment_id}".encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, signature or ""):
            return JSONResponse({"success": False, "error": "Payment verification failed"}, status_code=400)

        top_up = db.query(FeatureUsageTopUp).filter(
            FeatureUsageTopUp.user_id           == uid,
            FeatureUsageTopUp.razorpay_order_id == order_id,
            FeatureUsageTopUp.month_key         == "lifetime",
        ).first()
        if not top_up:
            return JSONResponse({"success": False, "error": "Order not found"}, status_code=404)

        top_up.status              = "paid"
        top_up.razorpay_payment_id = payment_id
        db.commit()

        # Log to unified payment ledger
        try:
            from finance_routes import log_payment_transaction
            log_payment_transaction(
                db                  = db,
                user_id             = uid,
                transaction_type    = "emora_pack",
                amount              = top_up.amount_paid,
                status              = "completed",
                razorpay_order_id   = order_id,
                razorpay_payment_id = payment_id,
                razorpay_signature  = signature,
                related_entity_type = "feature_top_up",
                related_entity_id   = top_up.id,
                description         = f"Emora Pack — +{top_up.quota_added:,} lifetime messages",
            )
        except Exception as _e:
            print(f"[WARN] Could not log emora pack transaction: {_e}")

        return JSONResponse({
            "success":    True,
            "messages_credited": top_up.quota_added,
            "validity":   "lifetime",
        })



    @app.post("/api/admin/plan-assistant")
    async def api_plan_assistant(request: Request, db: Session = Depends(get_db)):
        _admin_check(request, db)
        data = await request.json()
        messages = data.get("messages", [])

        try:
            import google.generativeai as genai_mod
            import re, json as _json

            GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
            contents = [{"role": ("user" if m["role"] == "user" else "model"),
                         "parts": [{"text": m["parts"][0]["text"] if m.get("parts") else m.get("text", "")}]}
                        for m in messages]

            if GEMINI_API_KEY:
                genai_mod.configure(api_key=GEMINI_API_KEY)
                model = genai_mod.GenerativeModel(
                    model_name="gemini-2.0-flash",
                    system_instruction=_PLAN_ASSISTANT_SYSTEM,
                )
                resp = model.generate_content(contents)
                reply = resp.text
            else:
                return JSONResponse({"success": False, "error": "AI not configured"}, status_code=503)

            action_data = None
            json_match = re.search(r"```json\s*(\{.*?\})\s*```", reply, re.DOTALL)
            if json_match:
                try:
                    action_data = _json.loads(json_match.group(1))
                    if action_data.get("action") != "create_plan":
                        action_data = None
                except Exception:
                    action_data = None

            return JSONResponse({"success": True, "reply": reply, "action": action_data})

        except Exception as e:
            print(f"[plan-assistant] error: {e}")
            return JSONResponse({"success": False, "error": str(e)}, status_code=500)

    @app.post("/api/admin/plan-assistant/create")
    async def api_plan_assistant_create(request: Request, db: Session = Depends(get_db)):
        _admin_check(request, db)
        data = await request.json()
        plan_data = data.get("plan", {})
        caps_data = data.get("caps", [])

        if plan_data.get("is_default"):
            db.query(UsagePlan).filter(UsagePlan.is_default == True).update({"is_default": False})

        plan = UsagePlan(
            name=plan_data.get("name", "New Plan"),
            description=plan_data.get("description", ""),
            price=float(plan_data.get("price", 0)),
            billing_cycle=plan_data.get("billing_cycle", "monthly"),
            is_free=bool(plan_data.get("is_free", True)),
            is_default=bool(plan_data.get("is_default", False)),
            is_active=bool(plan_data.get("is_active", True)),
            colour=plan_data.get("colour", "#0d9488"),
            display_order=int(plan_data.get("display_order", 0)),
        )
        db.add(plan)
        db.commit()
        db.refresh(plan)

        for c in caps_data:
            cap = PlanFeatureCap(
                plan_id=plan.id,
                feature_key=c.get("feature_key", "custom"),
                feature_name=c.get("feature_name", "Feature"),
                limit_value=int(c.get("limit_value", -1)),
                limit_first_week=c.get("limit_first_week"),
                limit_post_week=c.get("limit_post_week"),
                limit_hit_message=c.get("limit_hit_message"),
                extend_price=float(c.get("extend_price", 0)),
                extend_quota=int(c.get("extend_quota", 0)),
            )
            db.add(cap)
        db.commit()
        return JSONResponse({"success": True, "plan_id": plan.id, "plan_name": plan.name})

    # ── Admin API: import plan from JSON template ─────────────────────────────

    @app.post("/api/admin/plans/import")
    async def api_admin_import_plan(request: Request, db: Session = Depends(get_db)):
        """
        Accept a plan JSON template (same schema as the downloadable template) and
        create the plan + all feature caps in one shot. Idempotent: if a plan with
        the same name already exists, returns a conflict error rather than duplicating.
        """
        _admin_check(request, db)
        data = await request.json()

        plan_data = data.get("plan", data)   # support both {plan:{...},caps:[...]} and flat shape
        caps_data = data.get("caps", [])

        plan_name = (plan_data.get("name") or "").strip()
        if not plan_name:
            return JSONResponse({"success": False, "error": "Plan name is required"}, status_code=400)

        # Conflict check
        existing = db.query(UsagePlan).filter(UsagePlan.name == plan_name).first()
        if existing:
            return JSONResponse(
                {"success": False, "error": f"A plan named \"{plan_name}\" already exists (id={existing.id}). "
                 "Delete or rename it first."},
                status_code=409,
            )

        if plan_data.get("is_default"):
            db.query(UsagePlan).filter(UsagePlan.is_default == True).update({"is_default": False})

        plan = UsagePlan(
            name=plan_name,
            description=plan_data.get("description", ""),
            price=float(plan_data.get("price", 0)),
            billing_cycle=plan_data.get("billing_cycle", "monthly"),
            is_free=bool(plan_data.get("is_free", False)),
            is_default=bool(plan_data.get("is_default", False)),
            is_active=bool(plan_data.get("is_active", True)),
            colour=plan_data.get("colour", "#0d9488"),
            display_order=int(plan_data.get("display_order", 0)),
        )
        db.add(plan)
        db.commit()
        db.refresh(plan)

        created_caps = []
        for c in caps_data:
            if not c.get("feature_key"):
                continue
            cap = PlanFeatureCap(
                plan_id=plan.id,
                feature_key=c["feature_key"],
                feature_name=c.get("feature_name", c["feature_key"].replace("_", " ").title()),
                limit_value=int(c.get("limit_value", -1)),
                limit_first_week=c.get("limit_first_week"),
                limit_post_week=c.get("limit_post_week"),
                limit_hit_message=c.get("limit_hit_message"),
                extend_price=float(c.get("extend_price", 0)),
                extend_quota=int(c.get("extend_quota", 0)),
            )
            db.add(cap)
            created_caps.append(cap)
        db.commit()
        return JSONResponse({
            "success": True,
            "plan_id": plan.id,
            "plan_name": plan.name,
            "caps_created": len(created_caps),
        })

    # ── Admin API: seed Free + White default plans ────────────────────────────

    @app.post("/api/admin/plans/seed-defaults")
    async def api_admin_seed_defaults(request: Request, db: Session = Depends(get_db)):
        """
        Idempotently seeds the Free (default) and White (₹300/month) plans.
        Plans that already exist by name are skipped. Safe to call multiple times.

        THRYVEQ bitmask:
          1 = Latest,  2 = This Week,  4 = This Month,  8 = This Year
          Free  → 1  (Latest only)
          White → 7  (Latest + This Week + This Month; Annual locked)
        """
        _admin_check(request, db)

        _PLANS = [
            {
                "plan": {
                    "name": "Free",
                    "description": "Get started with core wellness features — no payment required.",
                    "price": 0,
                    "billing_cycle": "free",
                    "is_free": True,
                    "is_default": True,
                    "is_active": True,
                    "colour": "#6b7280",
                    "display_order": 0,
                },
                "caps": [
                    {"feature_key": "mood_tracker",      "feature_name": "Mood Tracker",         "limit_value": -1},
                    {"feature_key": "vital_scan",        "feature_name": "Vital Scan",            "limit_value": -1},
                    {"feature_key": "journal",           "feature_name": "Daily Journal",         "limit_value": -1},
                    {"feature_key": "workout_log",       "feature_name": "Workout Log",           "limit_value": -1},
                    {"feature_key": "google_fit_sync",   "feature_name": "Google Fit Sync",       "limit_value": 0,
                     "limit_hit_message": "Google Fit sync is available on the White plan and above. You can still log workouts manually."},
                    {"feature_key": "thryveq_access",    "feature_name": "THRYVEQ Score Access",   "limit_value": 1,
                     "limit_hit_message": "Upgrade to the White plan to unlock weekly and monthly THRYVEQ scores."},
                    {"feature_key": "free_consultation", "feature_name": "Free 15 mins consultations", "limit_value": 1,
                     "limit_hit_message": "Your complimentary 20-min consultation has been used. You can still book more at standard rates."},
                    {"feature_key": "ai_chat",           "feature_name": "Emora Chat Buddy",     "limit_value": 20,
                     "limit_first_week": 500, "limit_post_week": 20,
                     "limit_hit_message": "You've used all your Emora messages for today. You'll get 20 more tomorrow."},
                    {"feature_key": "recording_access",  "feature_name": "Call Recording Access", "limit_value": 0,
                     "limit_hit_message": "Upgrade to the White plan to access your call recordings."},
                    {"feature_key": "live_chat",         "feature_name": "Live Chat with Consultant", "limit_value": 0,
                     "limit_hit_message": "Live chat is available on the White plan and above."},
                ],
            },
            {
                "plan": {
                    "name": "White",
                    "description": "The essential wellness plan with AI chat, ThryvQ history, and a free first consultation.",
                    "price": 300,
                    "billing_cycle": "monthly",
                    "is_free": False,
                    "is_default": False,
                    "is_active": True,
                    "colour": "#0d9488",
                    "display_order": 1,
                },
                "caps": [
                    {"feature_key": "mood_tracker",      "feature_name": "Mood Tracker",         "limit_value": -1},
                    {"feature_key": "vital_scan",        "feature_name": "Vital Scan",            "limit_value": -1},
                    {"feature_key": "journal",           "feature_name": "Daily Journal",         "limit_value": -1},
                    {"feature_key": "workout_log",       "feature_name": "Workout Log",           "limit_value": -1},
                    {"feature_key": "google_fit_sync",   "feature_name": "Google Fit Sync",       "limit_value": -1},
                    # THRYVEQ: Latest(1) + This Week(2) + This Month(4) = 7; Annual(8) locked
                    {"feature_key": "thryveq_access",    "feature_name": "THRYVEQ Score Access",   "limit_value": 7,
                     "limit_hit_message": "Upgrade to a higher plan to unlock your annual THRYVEQ score."},
                    # 1 free consultation lifetime slot
                    {"feature_key": "free_consultation", "feature_name": "Free 15 mins consultations", "limit_value": 1,
                     "limit_hit_message": "Your complimentary consultation has been used. You can still book more at standard rates."},
                    {"feature_key": "ai_chat",           "feature_name": "Emora Chat Buddy",     "limit_value": 20,
                     "limit_first_week": 500, "limit_post_week": 20,
                     "limit_hit_message": "You've used all your Emora messages for today. You'll get 20 more tomorrow."},
                    {"feature_key": "recording_access",  "feature_name": "Call Recording Access", "limit_value": 0,
                     "limit_hit_message": "Call recording access is not included in the White plan. Upgrade to unlock."},
                    {"feature_key": "live_chat",         "feature_name": "Live Chat with Consultant", "limit_value": 0,
                     "limit_hit_message": "Live chat is not included in the White plan. Upgrade to unlock."},
                ],
            },
        ]

        results = []
        for entry in _PLANS:
            pd = entry["plan"]
            name = pd["name"]
            existing = db.query(UsagePlan).filter(UsagePlan.name == name).first()
            if existing:
                results.append({"name": name, "status": "skipped", "reason": "already exists", "id": existing.id})
                continue

            if pd.get("is_default"):
                db.query(UsagePlan).filter(UsagePlan.is_default == True).update({"is_default": False})

            plan = UsagePlan(
                name=name,
                description=pd.get("description", ""),
                price=float(pd.get("price", 0)),
                billing_cycle=pd.get("billing_cycle", "monthly"),
                is_free=bool(pd.get("is_free", False)),
                is_default=bool(pd.get("is_default", False)),
                is_active=True,
                colour=pd.get("colour", "#0d9488"),
                display_order=int(pd.get("display_order", 0)),
            )
            db.add(plan)
            db.commit()
            db.refresh(plan)

            for c in entry["caps"]:
                cap = PlanFeatureCap(
                    plan_id=plan.id,
                    feature_key=c["feature_key"],
                    feature_name=c.get("feature_name", c["feature_key"]),
                    limit_value=int(c.get("limit_value", -1)),
                    limit_first_week=c.get("limit_first_week"),
                    limit_post_week=c.get("limit_post_week"),
                    limit_hit_message=c.get("limit_hit_message"),
                    extend_price=float(c.get("extend_price", 0)),
                    extend_quota=int(c.get("extend_quota", 0)),
                )
                db.add(cap)
            db.commit()
            results.append({"name": name, "status": "created", "id": plan.id, "caps": len(entry["caps"])})

        return JSONResponse({"success": True, "results": results})

    # ── Vouchers System Endpoints ─────────────────────────────────────────────

    # Helper function inside closure
    def _validate_voucher_internal(db: Session, uid: int, code: str, applies_type: str, target_id, current_price: float):
        code = (code or "").strip().upper()
        if not code:
            return {"valid": False, "error": "Voucher code cannot be empty"}
        
        voucher = db.query(Voucher).filter(Voucher.code == code).first()
        if not voucher:
            return {"valid": False, "error": "Invalid voucher code"}
        
        if not voucher.is_active:
            return {"valid": False, "error": "Voucher is inactive"}
            
        if voucher.valid_until and datetime.utcnow() > voucher.valid_until:
            return {"valid": False, "error": "Voucher code has expired"}
            
        # Check assigned user emails
        if voucher.assigned_user_emails:
            user = db.query(User).filter(User.id == uid).first()
            if not user or not user.email:
                return {"valid": False, "error": "User email not found for validation"}
            allowed_emails = [e.strip().lower() for e in voucher.assigned_user_emails.split(",") if e.strip()]
            if user.email.strip().lower() not in allowed_emails:
                return {"valid": False, "error": "This voucher is not valid for your account"}
                
        # Check single-use restriction
        is_test_env = os.getenv("RAZORPAY_KEY_ID", "").startswith("rzp_test_")
        sub_exists = db.query(UserSubscription).filter(
            UserSubscription.user_id == uid,
            UserSubscription.voucher_code == code,
            UserSubscription.status.in_(["active", "paused", "grace"]),
            UserSubscription.is_test == is_test_env
        ).first()
        topup_exists = db.query(FeatureUsageTopUp).filter(
            FeatureUsageTopUp.user_id == uid,
            FeatureUsageTopUp.voucher_code == code,
            FeatureUsageTopUp.status == "paid",
            FeatureUsageTopUp.is_test == is_test_env
        ).first()
        if sub_exists or topup_exists:
            return {"valid": False, "error": "You have already used this voucher code"}
            
        # Check applicability
        if voucher.applies_to == "plan":
            if applies_type != "plan" or str(voucher.applies_to_id) != str(target_id):
                return {"valid": False, "error": "This voucher is not applicable to the selected plan"}
        elif voucher.applies_to == "package":
            if applies_type != "package" or str(voucher.applies_to_id).upper() != str(target_id).upper():
                return {"valid": False, "error": "This voucher is not applicable to the selected package"}
                
        # Calculate discount
        if voucher.discount_type == "percentage":
            discount_amount = round(current_price * (voucher.discount_value / 100.0), 2)
        else: # flat
            discount_amount = round(voucher.discount_value, 2)
            
        discount_amount = min(discount_amount, current_price)
        final_price = round(current_price - discount_amount, 2)
        
        return {
            "valid": True,
            "voucher": voucher,
            "discount_amount": discount_amount,
            "final_price": final_price
        }

    @app.get("/admin/vouchers", response_class=HTMLResponse)
    async def admin_vouchers_page(request: Request, db: Session = Depends(get_db)):
        user = _admin_check(request, db)
        vouchers = db.query(Voucher).order_by(Voucher.created_at.desc()).all()
        # Pre-calculate usage counts and expiration status
        is_test_env = os.getenv("RAZORPAY_KEY_ID", "").startswith("rzp_test_")
        now_utc = datetime.utcnow()
        for v in vouchers:
            v.is_expired = v.valid_until and v.valid_until < now_utc
            sub_count = db.query(UserSubscription).filter(
                UserSubscription.voucher_code == v.code,
                UserSubscription.status == 'active',
                UserSubscription.is_test == is_test_env
            ).count()
            topup_count = db.query(FeatureUsageTopUp).filter(
                FeatureUsageTopUp.voucher_code == v.code,
                FeatureUsageTopUp.status == 'paid',
                FeatureUsageTopUp.is_test == is_test_env
            ).count()
            v.usage_count = sub_count + topup_count

        active_plans = db.query(UsagePlan).filter(UsagePlan.is_active == True).all()

        return templates.TemplateResponse(
            "pages/admin_vouchers.html",
            {
                "request": request,
                "page_title": "Voucher Management | Admin",
                "user": user,
                "user_type": "admin",
                "vouchers": vouchers,
                "active_plans": active_plans,
                "active_page": "vouchers",
            }
        )

    @app.post("/api/admin/vouchers/create")
    async def api_create_voucher(request: Request, db: Session = Depends(get_db)):
        _admin_check(request, db)
        data = await request.json()
        
        code = (data.get("code") or "").strip().upper()
        if not code:
            return JSONResponse({"success": False, "error": "Voucher code is required"}, status_code=400)
            
        existing = db.query(Voucher).filter(Voucher.code == code).first()
        if existing:
            return JSONResponse({"success": False, "error": "Voucher code already exists"}, status_code=400)
            
        discount_type = data.get("discount_type") or "percentage"
        if discount_type not in ["percentage", "flat"]:
            return JSONResponse({"success": False, "error": "Invalid discount type"}, status_code=400)
            
        try:
            discount_value = float(data.get("discount_value") or 0.0)
        except ValueError:
            return JSONResponse({"success": False, "error": "Invalid discount value"}, status_code=400)
            
        applies_to = data.get("applies_to") or "all"
        if applies_to not in ["all", "plan", "package"]:
            return JSONResponse({"success": False, "error": "Invalid applies_to value"}, status_code=400)
            
        applies_to_id = data.get("applies_to_id")
        if applies_to != "all" and not applies_to_id:
            return JSONResponse({"success": False, "error": "applies_to_id is required for specific target"}, status_code=400)
            
        assigned_user_emails = data.get("assigned_user_emails") or None
        
        valid_until = None
        valid_until_str = data.get("valid_until")
        if valid_until_str:
            try:
                if "T" in valid_until_str:
                    valid_until = datetime.fromisoformat(valid_until_str)
                else:
                    valid_until = datetime.strptime(valid_until_str, "%Y-%m-%d")
            except Exception:
                return JSONResponse({"success": False, "error": "Invalid expiration date format"}, status_code=400)
                
        is_active = bool(data.get("is_active", True))
        
        voucher = Voucher(
            code=code,
            discount_type=discount_type,
            discount_value=discount_value,
            applies_to=applies_to,
            applies_to_id=str(applies_to_id) if applies_to_id else None,
            assigned_user_emails=assigned_user_emails,
            valid_until=valid_until,
            is_active=is_active
        )
        db.add(voucher)
        db.commit()
        
        return JSONResponse({"success": True})

    @app.post("/api/admin/vouchers/toggle")
    async def api_toggle_voucher(request: Request, db: Session = Depends(get_db)):
        _admin_check(request, db)
        data = await request.json()
        voucher_id = data.get("voucher_id")
        voucher = db.query(Voucher).filter(Voucher.id == voucher_id).first()
        if not voucher:
            return JSONResponse({"success": False, "error": "Voucher not found"}, status_code=404)
            
        voucher.is_active = not voucher.is_active
        db.commit()
        return JSONResponse({"success": True, "is_active": voucher.is_active})

    @app.post("/api/admin/vouchers/delete")
    async def api_delete_voucher(request: Request, db: Session = Depends(get_db)):
        _admin_check(request, db)
        data = await request.json()
        voucher_id = data.get("voucher_id")
        voucher = db.query(Voucher).filter(Voucher.id == voucher_id).first()
        if not voucher:
            return JSONResponse({"success": False, "error": "Voucher not found"}, status_code=404)
            
        db.delete(voucher)
        db.commit()
        return JSONResponse({"success": True})

    @app.get("/api/admin/vouchers/report/{voucher_id}")
    async def api_voucher_report(voucher_id: int, request: Request, db: Session = Depends(get_db)):
        _admin_check(request, db)
        
        voucher = db.query(Voucher).filter(Voucher.id == voucher_id).first()
        if not voucher:
            return JSONResponse({"success": False, "error": "Voucher not found"}, status_code=404)
            
        usages = []
        total_discount = 0.0
        
        is_test_env = os.getenv("RAZORPAY_KEY_ID", "").startswith("rzp_test_")
        
        # 1. Fetch Subscriptions
        subs = db.query(UserSubscription).filter(
            UserSubscription.voucher_code == voucher.code,
            UserSubscription.status.in_(["active", "paused", "grace", "expired", "cancelled"]),
            UserSubscription.is_test == is_test_env
        ).order_by(UserSubscription.started_at.desc()).all()
        
        for sub in subs:
            original_price = sub.plan.price
            if voucher.discount_type == "percentage":
                discount = round(original_price * (voucher.discount_value / 100.0), 2)
            else:
                discount = round(voucher.discount_value, 2)
            discount = min(discount, original_price)
            final_price = round(original_price - discount, 2)
            
            usages.append({
                "date": sub.started_at.strftime("%Y-%m-%d %H:%M:%S"),
                "date_only": sub.started_at.strftime("%Y-%m-%d"),
                "user_email": sub.user.email if sub.user else "Unknown",
                "user_name": sub.user.name if sub.user else "Unknown",
                "item_name": f"{sub.plan.name} Plan",
                "original_price": original_price,
                "discount_amount": discount,
                "final_price": final_price,
                "type": "Subscription"
            })
            total_discount += discount

        # 2. Fetch Top-ups
        topups = db.query(FeatureUsageTopUp).filter(
            FeatureUsageTopUp.voucher_code == voucher.code,
            FeatureUsageTopUp.status == "paid",
            FeatureUsageTopUp.is_test == is_test_env
        ).order_by(FeatureUsageTopUp.created_at.desc()).all()
        
        for tu in topups:
            # Look up pack original price by quota
            original_price = 0.0
            pack_name = "Emora Chat Pack"
            for pk_id, pk_info in _EMORA_PACKS.items():
                if pk_info["messages"] == tu.quota_added:
                    original_price = pk_info["price"]
                    pack_name = pk_info["name"]
                    break
            if original_price == 0.0:
                original_price = tu.amount_paid
                
            if voucher.discount_type == "percentage":
                discount = round(original_price * (voucher.discount_value / 100.0), 2)
            else:
                discount = round(voucher.discount_value, 2)
            discount = min(discount, original_price)
            final_price = round(original_price - discount, 2)
            
            usages.append({
                "date": tu.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                "date_only": tu.created_at.strftime("%Y-%m-%d"),
                "user_email": tu.user.email if tu.user else "Unknown",
                "user_name": tu.user.name if tu.user else "Unknown",
                "item_name": pack_name,
                "original_price": original_price,
                "discount_amount": discount,
                "final_price": final_price,
                "type": "Emora Pack"
            })
            total_discount += discount

        # Sort all usages by date descending
        usages.sort(key=lambda x: x["date"], reverse=True)
        
        # Group by date for daily usage summary
        daily_summary = {}
        for u in usages:
            d_key = u["date_only"]
            if d_key not in daily_summary:
                daily_summary[d_key] = {"count": 0, "discount": 0.0}
            daily_summary[d_key]["count"] += 1
            daily_summary[d_key]["discount"] += u["discount_amount"]
            
        daily_list = [
            {"date": k, "count": v["count"], "discount": round(v["discount"], 2)}
            for k, v in sorted(daily_summary.items(), reverse=True)
        ]
        
        return JSONResponse({
            "success": True,
            "voucher_code": voucher.code,
            "total_uses": len(usages),
            "total_discount": round(total_discount, 2),
            "usages": usages,
            "daily_summary": daily_list
        })

    @app.post("/api/vouchers/apply")
    async def api_apply_voucher(request: Request, db: Session = Depends(get_db)):
        uid = request.session.get("user_id")
        if not uid:
            return JSONResponse({"success": False, "error": "Authentication required"}, status_code=401)
            
        data = await request.json()
        code = data.get("code")
        applies_type = data.get("type") # "plan" / "package"
        target_id = data.get("target_id")
        
        if applies_type not in ["plan", "package"]:
            return JSONResponse({"success": False, "error": "Invalid voucher type check"}, status_code=400)
            
        # Get current base price
        if applies_type == "plan":
            plan = db.query(UsagePlan).filter(UsagePlan.id == int(target_id), UsagePlan.is_active == True).first()
            if not plan:
                return JSONResponse({"success": False, "error": "Plan not found"}, status_code=404)
            
            # Prorated discount calculation
            prorated_discount = 0.0
            try:
                current_sub = get_active_subscription(uid, db)
                old_plan_price = current_sub.plan.price if current_sub and current_sub.plan else 0
                is_upgrade = plan.price > old_plan_price
                if is_upgrade and current_sub and current_sub.plan and not current_sub.plan.is_free:
                    now = datetime.utcnow()
                    if current_sub.expires_at and current_sub.expires_at > now:
                        cycle = current_sub.plan.billing_cycle or "monthly"
                        cycle_days = 7 if cycle == "weekly" else (365 if cycle in ("yearly", "annual") else 30)
                        daily_rate = current_sub.plan.price / cycle_days
                        remaining_days = max(0.0, (current_sub.expires_at - now).total_seconds() / 86400.0)
                        remaining_days = min(float(cycle_days), remaining_days)
                        prorated_discount = round(remaining_days * daily_rate, 2)
            except Exception:
                pass
            
            base_price = max(0.0, plan.price - prorated_discount)
        else: # package
            pack = _EMORA_PACKS.get(str(target_id).upper())
            if not pack:
                return JSONResponse({"success": False, "error": "Package not found"}, status_code=404)
            
            # Apply Blue plan discount if applicable
            base_price = float(pack["price"])
            try:
                caps = get_user_plan_caps(uid, db)
                disc_cap = caps.get("emora_pack_discount")
                if disc_cap and disc_cap.limit_value > 0:
                    disc_pct = int(disc_cap.limit_value)
                    disc_amount = round(base_price * disc_pct / 100, 2)
                    base_price = round(base_price - disc_amount, 2)
            except Exception:
                pass
                
        res = _validate_voucher_internal(db, uid, code, applies_type, target_id, base_price)
        if not res["valid"]:
            return JSONResponse({"success": False, "error": res["error"]}, status_code=400)
            
        return JSONResponse({
            "success": True,
            "discount_type": res["voucher"].discount_type,
            "discount_value": res["voucher"].discount_value,
            "discount_amount": res["discount_amount"],
            "final_price": res["final_price"]
        })


# Duplicate _compute_expiry function removed to use the unified definition.


# ── Plan Assistant System Prompt ─────────────────────────────────────────────

_PLAN_ASSISTANT_SYSTEM = """You are a smart plan creation assistant for SolaceSquad, a mental health and wellness platform. Help admins create plans through a friendly, conversational flow — ONE question at a time.

─────────────────────────────────────────────────────────
STEP 1 — Ask the plan type (always first):
─────────────────────────────────────────────────────────
1. **Feature Extender** — lets users buy extra quota for ONE specific feature when they hit their daily/monthly limit
2. **Subscription Plan** — a full plan tier with pricing, multiple feature caps, and ThryvQ/Recording access controls

─────────────────────────────────────────────────────────
FEATURE EXTENDER FLOW:
─────────────────────────────────────────────────────────
Ask which feature this extender is for. Offer these choices:
  a) Emora Chat Buddy (extra daily messages)
  b) Consultant Bookings (extra sessions this month)
  c) Vitals Scans (extra scans this month)
  d) Journal Entries (extra entries this month)

Then ask questions **specific to the chosen feature**:

**If Emora Chat Buddy:**
  - How many extra messages per day does the user get with this extender?
  - Price in ₹
  - Message to show when base limit is hit (e.g. "You've used all your Emora messages today. Tap here to get more.")

**If Consultant Bookings / Vitals Scans / Journal Entries:**
  - How many extra units does this extender add?
  - Price in ₹
  - Message to show when limit is hit

Store as: feature_key matching the feature, limit_value=-1 (unlimited after top-up), extend_quota=number of extra units, extend_price=₹ price.

─────────────────────────────────────────────────────────
SUBSCRIPTION PLAN FLOW:
─────────────────────────────────────────────────────────
Collect these plan basics:
  - Plan name (e.g. "White", "Green", "Blue")
  - Description (one sentence)
  - Price in ₹ (0 = free plan)
  - Billing cycle: monthly / annual / free
  - Badge colour (suggest a nice hex if they don't have one, e.g. #0d9488 for teal)

Then ask about each feature ONE BY ONE, using **feature-specific questions**:

━━━ EMORA CHAT BUDDY ━━━
  Ask: "How many Emora messages can users send per day?"
  - Has two limits: First week (new users), and post-first-week (ongoing)
  - Ask both separately: "In the **first week**, how many messages per day? (e.g. 5)"
  - Then: "After the first week, how many messages per day? (e.g. 10)"
  - Ask: "What message should appear when the daily limit is hit?"
  - Store as: feature_key="ai_chat", limit_value=-1, limit_first_week=X, limit_post_week=Y

━━━ CONSULTANT BOOKINGS ━━━
  Ask: "How many consultant sessions can users book per month? (enter -1 for unlimited)"
  - Ask only if limited: "What message should appear when the booking limit is hit?"
  - Store as: feature_key="consultant_sessions", limit_value=N

━━━ VITALS SCANS ━━━
  Ask: "How many vitals scans can users do per month? (enter -1 for unlimited)"
  - Store as: feature_key="vitals_scans", limit_value=N

━━━ JOURNAL ENTRIES ━━━
  Ask: "How many journal entries can users create per month? (enter -1 for unlimited)"
  - Store as: feature_key="journal_entries", limit_value=N

━━━ THRYVEQ SCORE ACCESS ━━━
  Context: "Latest" THRYVEQ score is **always free** for every user on every plan.
  Weekly, Monthly and Annual scores are **locked by default** and must be explicitly unlocked per plan.
  Ask the admin: "Which THRYVEQ score periods should this plan unlock? (Latest is always included)"
  Present as clear options:
    1. Latest only — no extra THRYVEQ access (free/basic plans)
    2. Latest + This Week unlocked
    3. Latest + This Week + This Month unlocked
    4. All unlocked (Latest, This Week, This Month, This Year) — for premium plans
  Also ask: "What message should appear on the tiles that are still locked? (e.g. 'Upgrade to see your weekly ThryvQ score')"
  Store as: feature_key="thryveq_access", limit_value = bitmask sum:
    Latest=1, This Week=2, This Month=4, This Year=8
    Examples: Latest only=1, Latest+Week=3, Latest+Week+Month=7, All=15
  For free/basic plans, choice 1 (limit_value=1) means only Latest is visible; rest stay locked.

━━━ CALL RECORDING ACCESS ━━━
  Ask: "Should users on this plan be able to view and listen to their consultation call recordings? (Yes / No)"
  If No: Ask "What message should appear on the locked recordings page?"
  Store as: feature_key="recording_access", limit_value=1 (Yes) or 0 (No)
  DO NOT ask about limits, quotas or pricing for this feature — it's purely an access control.

─────────────────────────────────────────────────────────
FINISHING UP:
─────────────────────────────────────────────────────────
When all details are collected, show a clear summary and ask:
  "Here's the plan I've designed — shall I create it?"

Only after confirmation, output EXACTLY this JSON block and nothing else:
```json
{"action":"create_plan","plan_type":"feature_extender OR subscription","plan":{"name":"...","description":"...","price":0,"billing_cycle":"monthly","is_free":true,"is_default":false,"is_active":true,"colour":"#0d9488","display_order":0},"caps":[{"feature_key":"ai_chat","feature_name":"Emora AI Chat Messages","limit_value":-1,"limit_first_week":null,"limit_post_week":null,"limit_hit_message":null,"extend_price":0,"extend_quota":0}]}
```

Rules:
- limit_value -1 = unlimited
- For feature_extender: only ONE cap entry; top-up price in extend_price, units in extend_quota
- For subscription: include a cap entry for every feature discussed
- thryveq_access and recording_access caps must always be included in subscription plans
- NEVER ask for a bitmask number directly — present human-friendly choices and compute the bitmask yourself
"""

