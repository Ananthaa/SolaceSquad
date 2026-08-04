"""
Patch script: Fix Emora message quota system
- Fixes the #1 bug: increment_feature_usage was never called in send_ai_chat
- Adds is_first_week_bonus_eligible column to user_subscriptions
- Fixes two-bucket deduction (daily first, lifetime pack second)
- Adds correct defaults for limit_first_week (500) and limit_post_week (20)
"""
import re

MAIN_PATH = r"c:\Anantha\Projects\Soul Squad\backend\main.py"
SUB_PATH  = r"c:\Anantha\Projects\Soul Squad\backend\subscription_routes.py"
MDL_PATH  = r"c:\Anantha\Projects\Soul Squad\backend\models.py"

# ─────────────────────────────────────────────────────────────────────────────
# 1. models.py — add is_first_week_bonus_eligible to UserSubscription
# ─────────────────────────────────────────────────────────────────────────────
with open(MDL_PATH, "r", encoding="utf-8") as f:
    models = f.read()

OLD_SUB = "    razorpay_order_id   = Column(String(100), nullable=True)\n    razorpay_payment_id = Column(String(100), nullable=True)\n    created_at      = Column(DateTime, default=datetime.utcnow)"
NEW_SUB = """    razorpay_order_id   = Column(String(100), nullable=True)
    razorpay_payment_id = Column(String(100), nullable=True)
    # True for new users and plan UPGRADES; False for downgrades/renewals
    # Controls whether the user receives the 500-message first-week welcome pool
    is_first_week_bonus_eligible = Column(Boolean, nullable=False, default=True)
    created_at      = Column(DateTime, default=datetime.utcnow)"""

if OLD_SUB in models:
    models = models.replace(OLD_SUB, NEW_SUB, 1)
    with open(MDL_PATH, "w", encoding="utf-8") as f:
        f.write(models)
    print("OK: models.py - added is_first_week_bonus_eligible")
else:
    print("WARN: models.py - could not find target block, check manually")

# ─────────────────────────────────────────────────────────────────────────────
# 2. main.py — add DB migration at startup + quota gate in send_ai_chat
# ─────────────────────────────────────────────────────────────────────────────
with open(MAIN_PATH, "r", encoding="utf-8") as f:
    main = f.read()

# 2a. Add migration for the new column in the startup migration block
OLD_MIGRATE = '(\"original_price on usage_plans\",\n                   \"ALTER TABLE usage_plans ADD COLUMN IF NOT EXISTS original_price FLOAT\"),'
NEW_MIGRATE = '''("original_price on usage_plans",
                   "ALTER TABLE usage_plans ADD COLUMN IF NOT EXISTS original_price FLOAT"),
                # Emora quota: first-week bonus eligibility flag on subscriptions
                ("is_first_week_bonus_eligible on user_subscriptions",
                 "ALTER TABLE user_subscriptions ADD COLUMN IF NOT EXISTS is_first_week_bonus_eligible BOOLEAN NOT NULL DEFAULT TRUE"),'''

if OLD_MIGRATE in main:
    main = main.replace(OLD_MIGRATE, NEW_MIGRATE, 1)
    print("OK: main.py - added is_first_week_bonus_eligible migration")
else:
    print("WARN: main.py - migration block not found, check manually")

# 2b. Add quota gate + increment to send_ai_chat
OLD_SEND = """        # Get AI response using Gemini API
        from gemini_chat import gemini_chat
        ai_response = gemini_chat.chat(message, conversation_history)

        # Save original message (not the enriched version)
        saved_message = \"\" if is_greeting else original_message
        chat_entry = AIChatHistory(
            user_id=user_id,
            message=saved_message,
            response=ai_response
        )
        db.add(chat_entry)
        db.commit()
        db.refresh(chat_entry)
        
        return {
            \"success\": True,
            \"response\": ai_response,
            \"timestamp\": chat_entry.timestamp.isoformat()
        }"""

NEW_SEND = """        # ── Quota gate (skip for greeting auto-messages) ─────────────────────
        if not is_greeting:
            from subscription_routes import check_feature_limit
            quota = check_feature_limit(user_id, "ai_chat", db)
            if not quota["allowed"]:
                return {
                    "success": False,
                    "quota_exhausted": True,
                    "error": quota.get("message") or "You've used all your Emora messages. Your daily messages will refresh tomorrow, or you can top up with an Emora pack.",
                }

        # Get AI response using Gemini API
        from gemini_chat import gemini_chat
        ai_response = gemini_chat.chat(message, conversation_history)

        # Save original message (not the enriched version)
        saved_message = "" if is_greeting else original_message
        chat_entry = AIChatHistory(
            user_id=user_id,
            message=saved_message,
            response=ai_response
        )
        db.add(chat_entry)
        db.commit()
        db.refresh(chat_entry)

        # ── Deduct from quota (never deduct for greeting) ──────────────────────
        if not is_greeting:
            try:
                from subscription_routes import increment_feature_usage
                increment_feature_usage(user_id, "ai_chat", db)
            except Exception as _quota_err:
                print(f"[Quota] increment error (non-fatal): {_quota_err}")

        return {
            "success": True,
            "response": ai_response,
            "timestamp": chat_entry.timestamp.isoformat()
        }"""

if OLD_SEND in main:
    main = main.replace(OLD_SEND, NEW_SEND, 1)
    print("OK: main.py - added quota gate + increment to send_ai_chat")
else:
    print("WARN: main.py - send_ai_chat target not found")

with open(MAIN_PATH, "w", encoding="utf-8") as f:
    f.write(main)

# ─────────────────────────────────────────────────────────────────────────────
# 3. subscription_routes.py — rework ai_chat quota logic
# ─────────────────────────────────────────────────────────────────────────────
with open(SUB_PATH, "r", encoding="utf-8") as f:
    sub = f.read()

# 3a. Replace check_feature_limit for ai_chat (the in_first_week block)
OLD_CHECK = """    # Work out effective limit
    if feature_key == "ai_chat" and (cap.limit_first_week is not None or cap.limit_post_week is not None):
        # Determine if user is in first week of active subscription
        sub = get_active_subscription(user_id, db)
        in_first_week = False
        if sub:
            in_first_week = (datetime.utcnow() - sub.started_at).days < 7
        effective_limit = cap.limit_first_week if in_first_week else cap.limit_post_week
        if effective_limit is None:
            effective_limit = cap.limit_value
    else:
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
        # Include both current-period AND lifetime top-ups
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
    }"""

NEW_CHECK = """    # ── ai_chat two-phase quota logic ────────────────────────────────────────
    if feature_key == "ai_chat":
        active_sub = get_active_subscription(user_id, db)
        in_first_week = False
        bonus_eligible = True
        if active_sub:
            days_on_plan = (datetime.utcnow() - active_sub.started_at).days
            bonus_eligible = getattr(active_sub, "is_first_week_bonus_eligible", True)
            in_first_week = (days_on_plan < 7) and bonus_eligible

        # ── PHASE 1: First-week welcome pool (500 msgs, no daily sub-cap) ──────
        if in_first_week:
            first_week_limit = cap.limit_first_week if cap.limit_first_week is not None else 500
            if first_week_limit == -1:
                return {"allowed": True, "used": 0, "limit": -1, "cap": cap,
                        "message": "", "can_extend": False, "extend_price": 0, "extend_quota": 0,
                        "daily_remaining": -1, "pack_balance": 0, "in_first_week": True}
            # Week-1 key is unique to this subscription start date
            week1_key = "week1-" + active_sub.started_at.strftime("%Y-%m-%d")
            w1_log = db.query(FeatureUsageLog).filter(
                FeatureUsageLog.user_id     == user_id,
                FeatureUsageLog.feature_key == feature_key,
                FeatureUsageLog.month_key   == week1_key,
            ).first()
            week1_used = w1_log.usage_count if w1_log else 0
            allowed = week1_used < first_week_limit
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
                "daily_remaining": first_week_limit - week1_used,
                "pack_balance": 0,
                "in_first_week": True,
                "_week1_key": week1_key,
            }

        # ── PHASE 2: Post-week daily (20/day) + lifetime pack overflow ────────
        daily_limit = cap.limit_post_week if cap.limit_post_week is not None else 20
        if daily_limit == -1:
            return {"allowed": True, "used": 0, "limit": -1, "cap": cap,
                    "message": "", "can_extend": False, "extend_price": 0, "extend_quota": 0,
                    "daily_remaining": -1, "pack_balance": 0, "in_first_week": False}

        today_key = datetime.utcnow().strftime("%Y-%m-%d")
        day_log = db.query(FeatureUsageLog).filter(
            FeatureUsageLog.user_id     == user_id,
            FeatureUsageLog.feature_key == feature_key,
            FeatureUsageLog.month_key   == today_key,
        ).first()
        daily_used = day_log.usage_count if day_log else 0
        daily_remaining = max(0, daily_limit - daily_used)

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
    }"""

if OLD_CHECK in sub:
    sub = sub.replace(OLD_CHECK, NEW_CHECK, 1)
    print("OK: subscription_routes.py - rewrote check_feature_limit ai_chat logic")
else:
    print("WARN: subscription_routes.py - check_feature_limit target not found")

# 3b. Replace increment_feature_usage with priority-aware version
OLD_INC = """def increment_feature_usage(user_id: int, feature_key: str, db: Session):
    \"\"\"Increment the period usage counter for a feature (daily for ai_chat, monthly for others).\"\"\"
    from models import FeatureUsageLog
    period_key = _get_period_key(feature_key)
    log = db.query(FeatureUsageLog).filter(
        FeatureUsageLog.user_id == user_id,
        FeatureUsageLog.feature_key == feature_key,
        FeatureUsageLog.month_key == period_key,
    ).first()
    if log:
        log.usage_count += 1
    else:
        log = FeatureUsageLog(
            user_id=user_id, feature_key=feature_key,
            month_key=period_key, usage_count=1
        )
        db.add(log)
    db.commit()"""

NEW_INC = """def increment_feature_usage(user_id: int, feature_key: str, db: Session):
    \"\"\"
    Deduct one unit of quota for a feature.

    For ai_chat — priority order:
      1. Week-1 welcome pool (if active)
      2. Today's daily bucket (20/day post-week)
      3. Lifetime pack bucket (only when daily is exhausted)
    For all other features — monthly counter.
    \"\"\"
    from models import FeatureUsageLog, FeatureUsageTopUp

    if feature_key == "ai_chat":
        # Re-use check_feature_limit to determine which bucket to deduct from
        quota = check_feature_limit(user_id, feature_key, db)
        in_first_week = quota.get("in_first_week", False)

        if in_first_week:
            # Deduct from week-1 pool
            week1_key = quota.get("_week1_key")
            if not week1_key:
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
            daily_remaining = quota.get("daily_remaining", 0)
            if daily_remaining > 0:
                # Deduct from today's daily bucket
                today_key = datetime.utcnow().strftime("%Y-%m-%d")
                log = db.query(FeatureUsageLog).filter(
                    FeatureUsageLog.user_id     == user_id,
                    FeatureUsageLog.feature_key == feature_key,
                    FeatureUsageLog.month_key   == today_key,
                ).first()
                if log:
                    log.usage_count += 1
                else:
                    log = FeatureUsageLog(
                        user_id=user_id, feature_key=feature_key,
                        month_key=today_key, usage_count=1
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
    db.commit()"""

if OLD_INC in sub:
    sub = sub.replace(OLD_INC, NEW_INC, 1)
    print("OK: subscription_routes.py - rewrote increment_feature_usage")
else:
    print("WARN: subscription_routes.py - increment_feature_usage target not found")

# 3c. Update api_my_usage ai_chat section to expose rich data
OLD_USAGE_AI = """            # Effective limit (honour week-1 / post-week for ai_chat)
            if feature_key == "ai_chat" and (cap.limit_first_week is not None or cap.limit_post_week is not None):
                in_first_week = False
                if sub:
                    in_first_week = (datetime.utcnow() - sub.started_at).days < 7
                eff_limit = cap.limit_first_week if in_first_week else cap.limit_post_week
                if eff_limit is None:
                    eff_limit = cap.limit_value
            else:
                eff_limit = cap.limit_value

            # Add lifetime pack bonus to the display balance
            lifetime_bonus = 0
            if eff_limit != -1:
                lt_rows = db.query(FeatureUsageTopUp).filter(
                    FeatureUsageTopUp.user_id     == uid,
                    FeatureUsageTopUp.feature_key == feature_key,
                    FeatureUsageTopUp.month_key   == "lifetime",
                    FeatureUsageTopUp.status      == "paid",
                ).all()
                lifetime_bonus = sum(r.quota_added for r in lt_rows)

            # Period top-ups
            period_bonus = 0
            if eff_limit != -1:
                pt_rows = db.query(FeatureUsageTopUp).filter(
                    FeatureUsageTopUp.user_id     == uid,
                    FeatureUsageTopUp.feature_key == feature_key,
                    FeatureUsageTopUp.month_key   == pk,
                    FeatureUsageTopUp.status      == "paid",
                ).all()
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
            }"""

NEW_USAGE_AI = """            # ── ai_chat: rich quota using check_feature_limit ─────────────────
            if feature_key == "ai_chat":
                quota = check_feature_limit(uid, feature_key, db)
                daily_remaining = quota.get("daily_remaining", 0)
                pack_balance    = quota.get("pack_balance", 0)
                in_first_week   = quota.get("in_first_week", False)
                if in_first_week:
                    # Week-1 pool: show remaining out of 500
                    fw_limit = cap.limit_first_week if cap.limit_first_week is not None else 500
                    display_limit = fw_limit
                    display_used  = quota.get("used", 0)
                    display_remaining = max(0, display_limit - display_used)
                else:
                    # Post-week: daily + pack
                    display_limit     = (cap.limit_post_week or 20) + pack_balance
                    display_used      = used   # today's usage
                    display_remaining = daily_remaining + pack_balance

                caps_out[feature_key] = {
                    "feature_key":       feature_key,
                    "feature_name":      cap.feature_name,
                    "limit":             display_remaining,   # total msgs remaining (what frontend shows)
                    "used":              display_used,
                    "daily_remaining":   daily_remaining,
                    "pack_balance":      pack_balance,
                    "in_first_week":     in_first_week,
                    "extend_price":      cap.extend_price,
                    "extend_quota":      cap.extend_quota,
                    "limit_hit_message": cap.limit_hit_message,
                }
                continue

            # ── All other features ────────────────────────────────────────────
            eff_limit = cap.limit_value
            # Add lifetime pack bonus to the display balance
            lifetime_bonus = 0
            if eff_limit != -1:
                lt_rows = db.query(FeatureUsageTopUp).filter(
                    FeatureUsageTopUp.user_id     == uid,
                    FeatureUsageTopUp.feature_key == feature_key,
                    FeatureUsageTopUp.month_key   == "lifetime",
                    FeatureUsageTopUp.status      == "paid",
                ).all()
                lifetime_bonus = sum(r.quota_added for r in lt_rows)

            # Period top-ups
            period_bonus = 0
            if eff_limit != -1:
                pt_rows = db.query(FeatureUsageTopUp).filter(
                    FeatureUsageTopUp.user_id     == uid,
                    FeatureUsageTopUp.feature_key == feature_key,
                    FeatureUsageTopUp.month_key   == pk,
                    FeatureUsageTopUp.status      == "paid",
                ).all()
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
            }"""

if OLD_USAGE_AI in sub:
    sub = sub.replace(OLD_USAGE_AI, NEW_USAGE_AI, 1)
    print("OK: subscription_routes.py - rewrote api_my_usage ai_chat section")
else:
    print("WARN: subscription_routes.py - api_my_usage ai_chat section not found")

# 3d. Update subscribe route to set is_first_week_bonus_eligible on upgrades
OLD_SUB_ROUTE = """        # Cancel any current active subscription
        db.query(UserSubscription).filter(
            UserSubscription.user_id == uid,
            UserSubscription.status == "active",
        ).update({"status": "cancelled"})
        db.commit()

        if plan.is_free or plan.price == 0:
            # Immediate activation
            expires = None
            sub = UserSubscription(
                user_id=uid, plan_id=plan.id, status="active","""

NEW_SUB_ROUTE = """        # Cancel any current active subscription; remember old plan price to detect upgrade
        current_sub     = get_active_subscription(uid, db)
        old_plan_price  = current_sub.plan.price if current_sub and current_sub.plan else 0
        is_upgrade      = plan.price > old_plan_price   # True for new users too (old=0)
        db.query(UserSubscription).filter(
            UserSubscription.user_id == uid,
            UserSubscription.status == "active",
        ).update({"status": "cancelled"})
        db.commit()

        if plan.is_free or plan.price == 0:
            # Immediate activation
            expires = None
            sub = UserSubscription(
                user_id=uid, plan_id=plan.id, status="active",
                is_first_week_bonus_eligible=is_upgrade,"""

if OLD_SUB_ROUTE in sub:
    sub = sub.replace(OLD_SUB_ROUTE, NEW_SUB_ROUTE, 1)
    print("OK: subscription_routes.py - added is_first_week_bonus_eligible to subscribe route")
else:
    print("WARN: subscription_routes.py - subscribe route target not found")

with open(SUB_PATH, "w", encoding="utf-8") as f:
    f.write(sub)

print("\nAll patches applied. Check warnings above if any.")
