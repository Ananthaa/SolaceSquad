"""
finance_routes.py — Finance module for SolaceSquad.

Covers:
  - Admin: full payment ledger, per-consultant earnings, payout management
  - User: personal billing history + invoice view/print-PDF
  - Consultant: earnings overview and per-session breakdown

Registration:
  from finance_routes import register_finance_routes
  register_finance_routes(app, templates, get_db)
"""

from __future__ import annotations

import os
import hmac
import hashlib
import json
from datetime import datetime, date, timedelta
from typing import Optional
import timezone_utils

# Date production went live with real Razorpay keys.
# All ConsultantEarning records before this date are test data.
_LIVE_GO_DATE = datetime(2026, 6, 16, 17, 45, 0)  # UTC

from fastapi import FastAPI, Request, Depends, HTTPException, Form
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_, desc

# ── helpers ───────────────────────────────────────────────────────────────────

def _razorpay_client():
    """Return an initialised Razorpay client, or None if keys are missing."""
    key_id     = os.getenv("RAZORPAY_KEY_ID")
    key_secret = os.getenv("RAZORPAY_KEY_SECRET")
    if not (key_id and key_secret):
        return None, None
    try:
        import razorpay
        return razorpay.Client(auth=(key_id, key_secret)), key_secret
    except Exception:
        return None, None


def _freeze_payout(db: Session, appointment_id: int, reason: str):
    from models import ConsultantEarning
    earning = (
        db.query(ConsultantEarning)
        .filter(ConsultantEarning.appointment_id == appointment_id)
        .first()
    )
    if earning and earning.payout_status == "pending":
        earning.payout_status = "on_hold"
        earning.admin_notes = f"Payout frozen: {reason}"
        db.commit()


def process_appointment_refund(db: Session, appointment_id: int, reason: str = "Appointment cancelled") -> dict:
    """
    Issue a full Razorpay refund for a paid appointment and update the ledger.

    Steps:
      1. Find the PaymentTransaction linked to this appointment.
      2. Skip if already refunded, free, or no Razorpay payment ID exists.
      3. Call Razorpay refund API (full amount).
      4. Mark PaymentTransaction.status = 'refunded'.
      5. Set ConsultantEarning.payout_status = 'on_hold' so admin doesn't pay out.

    Returns:
      {"refunded": True/False, "refund_id": str|None, "message": str}
    """
    from models import PaymentTransaction, ConsultantEarning

    txn = (
        db.query(PaymentTransaction)
        .filter(
            PaymentTransaction.related_entity_type == "appointment",
            PaymentTransaction.related_entity_id   == appointment_id,
            PaymentTransaction.status              == "completed",
            PaymentTransaction.transaction_type    == "consultation",
        )
        .first()
    )

    if not txn:
        _freeze_payout(db, appointment_id, "No completed payment found")
        return {"refunded": False, "refund_id": None, "message": "No completed payment found — no refund needed."}

    if txn.status == "refunded":
        _freeze_payout(db, appointment_id, "Already refunded")
        return {"refunded": False, "refund_id": None, "message": "Already refunded."}

    if not txn.razorpay_payment_id:
        _freeze_payout(db, appointment_id, "No Razorpay payment ID")
        return {"refunded": False, "refund_id": None, "message": "No Razorpay payment ID — free booking, no refund needed."}

    client, _ = _razorpay_client()
    if not client:
        return {"refunded": False, "refund_id": None, "message": "Payment gateway not configured — refund skipped."}


    try:
        amount_paise = int(txn.amount * 100)
        refund = client.payment.refund(txn.razorpay_payment_id, {
            "amount": amount_paise,
            "speed":  "normal",  # 'normal' (5-7 days) or 'optimum'
            "notes":  {"reason": reason, "appointment_id": str(appointment_id)},
        })
        refund_id = refund.get("id")

        # Mark transaction as refunded
        txn.status        = "refunded"
        txn.refunded_at   = datetime.utcnow()
        txn.refund_reason = reason

        # Freeze consultant payout — admin should not disburse
        earning = (
            db.query(ConsultantEarning)
            .filter(ConsultantEarning.appointment_id == appointment_id)
            .first()
        )
        if earning and earning.payout_status == "pending":
            earning.payout_status = "on_hold"
            earning.admin_notes   = f"Appointment #{appointment_id} cancelled — refund {refund_id} issued."

        db.commit()
        return {
            "refunded":  True,
            "refund_id": refund_id,
            "amount":    txn.amount,
            "message":   f"Refund of ₹{txn.amount:.2f} initiated. Ref: {refund_id}",
        }

    except Exception as e:
        db.rollback()
        print(f"[Refund] Razorpay refund failed for appointment {appointment_id}: {e}")
        return {"refunded": False, "refund_id": None, "message": f"Refund failed: {str(e)}"}


def _parse_appt_date(raw: str, tz_name: str = "UTC") -> datetime:
    """
    Parse appointment date from UI (datetime-local = 'YYYY-MM-DDTHH:MM', no seconds).
    Converts from user's local timezone to UTC for storage.
    """
    import timezone_utils
    # Normalise: add :00 seconds if missing
    raw = raw.strip()
    if "T" in raw and len(raw.split("T")[1]) == 5:
        raw += ":00"
    
    # Parse as naive first (as it comes from datetime-local)
    try:
        dt_naive = datetime.fromisoformat(raw.replace("Z", ""))
    except Exception:
        # Fallback for weird formats
        dt_naive = datetime.strptime(raw[:19], "%Y-%m-%dT%H:%M:%S")

    # Localise to user's timezone and convert to UTC
    return timezone_utils.parse_local_to_utc(dt_naive, tz_name)



def _find_next_available(from_dt, duration_minutes, consultant_id, db):
    """Find the next available 30-min aligned slot for this consultant."""
    from models import Appointment, ConsultantSchedule
    from datetime import timedelta
    candidate = from_dt
    BUFFER = 15
    for _ in range(48):  # check up to 24 hours ahead in 30-min steps
        candidate = candidate + timedelta(minutes=30)
        cand_end = candidate + timedelta(minutes=duration_minutes)
        cand_block_s = candidate - timedelta(minutes=BUFFER)
        cand_block_e = cand_end  + timedelta(minutes=BUFFER)
        conflicts = db.query(Appointment).filter(
            Appointment.consultant_id    == consultant_id,
            Appointment.status           == "scheduled",
            Appointment.appointment_date >= cand_block_s - timedelta(hours=2),
            Appointment.appointment_date <  cand_block_e + timedelta(hours=2),
        ).all()
        has_conflict = False
        for c in conflicts:
            c_start = c.appointment_date
            c_end   = c_start + timedelta(minutes=c.duration_minutes or 60)
            c_bs    = c_start - timedelta(minutes=BUFFER)
            c_be    = c_end   + timedelta(minutes=BUFFER)
            if max(c_bs, cand_block_s) < min(c_be, cand_block_e):
                has_conflict = True
                break
        if not has_conflict:
            return candidate.strftime("%H:%M")
    return None


def _validate_booking(db, user_id: int, consultant_id: int,
                      appt_dt: datetime, duration: int, is_paid: bool, request: Request = None) -> dict | None:
    """
    Run all booking validation rules. Returns an error dict (for JSONResponse)
    or None if everything is valid.

    Rules:
      1. Free consultant → 15-min only (already enforced before calling, but double-check)
      2. Paid consultant → must book at least 24 hours in advance
      3. 15-min buffer on both sides of every existing appointment (overlap check)
      4. User may not double-book themselves
    """
    from datetime import timedelta
    from models import Appointment

    BUFFER = 15

    # Rule 2: 24-hour advance for paid consultants.
    # appt_dt is now UTC (naive). Compare with UTC now.
    is_impersonating = request.session.get("impersonate_user_id") is not None if request else False
    if is_paid and not is_impersonating:
        now_utc = datetime.utcnow()
        if appt_dt < now_utc + timedelta(hours=24):
            # For the error message, show the earliest time in user's local timezone
            user_tz = "Asia/Kolkata"
            if request:
                utz = request.session.get("timezone")
                if utz and utz != "UTC":
                    user_tz = utz
            
            earliest_utc = now_utc + timedelta(hours=24)
            earliest_local = timezone_utils.to_local(earliest_utc, user_tz)
            earliest_display = earliest_local.strftime('%d %b %Y %I:%M %p')

            return {
                "success":       False,
                "error":         f"Paid consultations must be booked at least 24 hours in advance. Earliest: {earliest_display}.",
                "conflict_type": "advance_booking_required",
                "earliest_date": earliest_utc.isoformat(),
            }

    appt_end          = appt_dt + timedelta(minutes=duration)

    # ── NEW: Working hours & break validation ──────────────────────────────
    from models import ConsultantSchedule, ScheduleBreak, ConsultantProfile

    # Get consultant's timezone to interpret their schedule (defaults to Asia/Kolkata)
    profile = db.query(ConsultantProfile).filter(ConsultantProfile.id == consultant_id).first()
    cons_tz = "Asia/Kolkata"
    if profile and profile.user and profile.user.timezone and profile.user.timezone != "UTC":
        cons_tz = profile.user.timezone
    
    # Convert appointment time (UTC) to consultant's local time for schedule checks
    appt_local = timezone_utils.to_local(appt_dt, cons_tz)
    day_of_week = appt_local.weekday()  # 0=Monday
    day_names   = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]

    # Get or seed schedule from onboarding
    schedule = db.query(ConsultantSchedule).filter(
        ConsultantSchedule.consultant_id == consultant_id,
        ConsultantSchedule.day_of_week   == day_of_week,
        ConsultantSchedule.is_active     == True,
    ).first()

    if not schedule:
        # Try seeding from onboarding profile
        from models import ConsultantProfile
        _profile = db.query(ConsultantProfile).filter(ConsultantProfile.id == consultant_id).first()
        if _profile:
            DAY_MAP  = {"Weekdays":[0,1,2,3,4],"Weekends":[5,6],"Any Day":[0,1,2,3,4,5,6]}
            TIME_MAP = {
                "Morning (6am\u201312pm)":("06:00","12:00"),
                "Afternoon (12pm\u20135pm)":("12:00","17:00"),
                "Evening (5pm\u201310pm)":("17:00","22:00"),
                "Any Time":("06:00","22:00"),
            }
            if _profile.preferred_days or _profile.preferred_time:
                days  = DAY_MAP.get(_profile.preferred_days, [0,1,2,3,4])
                st, en = TIME_MAP.get(_profile.preferred_time, ("09:00","17:00"))
                for d in days:
                    db.add(ConsultantSchedule(
                        consultant_id=consultant_id, day_of_week=d,
                        start_time=st, end_time=en, is_active=True
                    ))
                try:
                    db.commit()
                    schedule = db.query(ConsultantSchedule).filter(
                        ConsultantSchedule.consultant_id == consultant_id,
                        ConsultantSchedule.day_of_week   == day_of_week,
                        ConsultantSchedule.is_active     == True,
                    ).first()
                except Exception:
                    db.rollback()

    if not schedule:
        all_scheds = db.query(ConsultantSchedule).filter(
            ConsultantSchedule.consultant_id == consultant_id,
            ConsultantSchedule.is_active     == True,
        ).all()
        if all_scheds:
            working_days = sorted(set(s.day_of_week for s in all_scheds))
            days_str = ", ".join(day_names[d] for d in working_days)
            return {"success": False, "error":
                    f"This consultant is not available on {day_names[day_of_week]}. "
                    f"They work on: {days_str}."}
        else:
            # No schedule at all \u2014 still allow booking but warn
            pass  # Fall through to overlap checks
    else:
        # Check slot fits within working hours
        appt_hhmm     = appt_local.strftime("%H:%M")
        appt_end_local = appt_local + timedelta(minutes=duration)
        appt_end_hhmm = appt_end_local.strftime("%H:%M")

        if appt_hhmm < schedule.start_time:
            return {"success": False, "error":
                    f"This slot starts before the consultant's working hours "
                    f"({schedule.start_time}\u2013{schedule.end_time}). "
                    f"Please choose a time from {schedule.start_time} onwards."}

        if appt_end_hhmm > schedule.end_time:
            return {"success": False, "error":
                    f"This {duration}-minute session would end at {appt_end_hhmm}, "
                    f"past working hours ({schedule.end_time}). "
                    f"Please choose an earlier slot so the session ends by {schedule.end_time}."}

        # Check break overlap
        breaks = db.query(ScheduleBreak).filter(
            ScheduleBreak.consultant_id == consultant_id,
            ScheduleBreak.day_of_week   == day_of_week,
        ).all()
        for brk in breaks:
            if appt_hhmm < brk.break_end and appt_end_hhmm > brk.break_start:
                return {"success": False, "error":
                        f"This slot overlaps with the consultant's break "
                        f"({brk.break_start}\u2013{brk.break_end}). "
                        f"Please choose a time outside this break period."}
    # ── END: Working hours & break validation ─────────────────────────────

    new_blocked_start = appt_dt  - timedelta(minutes=BUFFER)
    new_blocked_end   = appt_end + timedelta(minutes=BUFFER)
    wide_start        = new_blocked_start - timedelta(hours=2)
    wide_end          = new_blocked_end   + timedelta(hours=2)

    # Rule 3: Consultant overlap (with row lock)
    try:
        consultant_appts = (
            db.query(Appointment)
            .filter(
                Appointment.consultant_id    == consultant_id,
                Appointment.status           == "scheduled",
                Appointment.appointment_date >= wide_start,
                Appointment.appointment_date <  wide_end,
            )
            .with_for_update()
            .all()
        )
    except Exception:
        consultant_appts = db.query(Appointment).filter(
            Appointment.consultant_id    == consultant_id,
            Appointment.status           == "scheduled",
            Appointment.appointment_date >= wide_start,
            Appointment.appointment_date <  wide_end,
        ).all()

    conflict_end = None
    for c in consultant_appts:
        c_dur   = c.duration_minutes or 60
        c_start = c.appointment_date.replace(tzinfo=None) if getattr(c.appointment_date, "tzinfo", None) else c.appointment_date
        c_end   = c_start + timedelta(minutes=c_dur)
        c_block_s = c_start - timedelta(minutes=BUFFER)
        c_block_e = c_end   + timedelta(minutes=BUFFER)
        if max(c_block_s, new_blocked_start) < min(c_block_e, new_blocked_end):
            if conflict_end is None or c_block_e > conflict_end:
                conflict_end = c_block_e

    if conflict_end is not None:
        # Try to find the next free slot
        try:
            from main import _find_next_slot
            next_slot = _find_next_slot(db, consultant_id, conflict_end, duration, BUFFER)
        except Exception:
            next_slot = None
        next_msg = f" Next available: {next_slot['label']}." if next_slot else " Please check the schedule."
        tz_name = "UTC"
        if request:
            tz_name = request.session.get("timezone", "UTC")
        return {
            "success":        False,
            "error":          f"This consultant is unavailable at {timezone_utils.format_dt_local(appt_dt, '%I:%M %p', tz_name)} (including 15-min buffer).{next_msg}",
            "conflict_type":  "consultant_busy",
            "next_available": next_slot,
        }

    # Rule 4: User double-booking
    user_appts = db.query(Appointment).filter(
        Appointment.user_id  == user_id,
        Appointment.status   == "scheduled",
        Appointment.appointment_date >= wide_start,
        Appointment.appointment_date <  wide_end,
    ).all()
    for c in user_appts:
        c_dur   = c.duration_minutes or 60
        c_start = c.appointment_date.replace(tzinfo=None) if getattr(c.appointment_date, "tzinfo", None) else c.appointment_date
        c_end   = c_start + timedelta(minutes=c_dur)
        if max(c_start, appt_dt) < min(c_end, appt_end):
            tz_name = "UTC"
            if request:
                tz_name = request.session.get("timezone", "UTC")
            return {
                "success":       False,
                "error":         f"You already have an appointment at {timezone_utils.format_dt_local(c_start, '%I:%M %p', tz_name)}–{timezone_utils.format_dt_local(c_end, '%I:%M %p', tz_name)}. Cancel it first or pick a different time.",
                "conflict_type": "user_busy",
            }

    return None  # all good



def _generate_invoice_number(db: Session) -> str:
    """Generate sequential invoice number: SS-YYYY-NNNNN."""
    from models import PaymentTransaction
    year = datetime.utcnow().year
    prefix = f"SS-{year}-"
    last = (
        db.query(PaymentTransaction)
        .filter(PaymentTransaction.invoice_number.like(f"{prefix}%"))
        .order_by(PaymentTransaction.invoice_number.desc())
        .first()
    )
    if last and last.invoice_number:
        try:
            seq = int(last.invoice_number.split("-")[-1]) + 1
        except ValueError:
            seq = 1
    else:
        seq = 1
    return f"{prefix}{seq:05d}"


def _is_test_mode() -> bool:
    """Return True when Razorpay is configured with a test key."""
    key_id = os.getenv("RAZORPAY_KEY_ID", "")
    return key_id.startswith("rzp_test_")


def log_payment_transaction(
    db: Session,
    user_id: int,
    transaction_type: str,
    amount: float,
    status: str = "completed",
    razorpay_order_id: str = None,
    razorpay_payment_id: str = None,
    razorpay_signature: str = None,
    related_entity_type: str = None,
    related_entity_id: int = None,
    description: str = None,
) -> "PaymentTransaction":
    """
    Create and persist a PaymentTransaction row.
    Returns the saved object (with invoice_number populated).
    Call this immediately after Razorpay payment verification succeeds.
    """
    from models import PaymentTransaction

    invoice_number = _generate_invoice_number(db) if status == "completed" else None

    txn = PaymentTransaction(
        user_id              = user_id,
        transaction_type     = transaction_type,
        amount               = amount,
        currency             = "INR",
        status               = status,
        razorpay_order_id    = razorpay_order_id,
        razorpay_payment_id  = razorpay_payment_id,
        razorpay_signature   = razorpay_signature,
        related_entity_type  = related_entity_type,
        related_entity_id    = related_entity_id,
        description          = description,
        invoice_number       = invoice_number,
        is_test              = _is_test_mode(),   # auto-detect from Razorpay key prefix
    )
    db.add(txn)
    db.commit()
    db.refresh(txn)

    # Trigger invoice email after successful payment completion
    if status == "completed":
        try:
            from models import User
            user = db.query(User).filter(User.id == user_id).first()
            if user and user.email:
                from sendgrid_email import send_payment_invoice_email
                send_payment_invoice_email(
                    to_email            = user.email,
                    user_name           = user.name or "Member",
                    invoice_number      = txn.invoice_number,
                    description         = txn.description or "Payment Transaction",
                    amount              = txn.amount,
                    payment_id          = txn.razorpay_payment_id,
                    txn_type            = txn.transaction_type,
                    related_entity_type = txn.related_entity_type,
                    related_entity_id   = txn.related_entity_id,
                    user_id             = user_id,
                    db_session          = db,
                )
        except Exception as _mail_err:
            print(f"[WARN] Failed to send payment invoice email: {_mail_err}")

    return txn


def log_consultant_earning(
    db: Session,
    consultant_user_id: int,
    appointment_id: int,
    payment_transaction_id: int,
    gross_amount: float,
    payout_amount: float = None,  # consultant_payout from profile; if None, full amount goes to consultant
    taxes: float = 0.0,
    discount_amount: float = 0.0,
    discount_pct: float = 0.0,
) -> "ConsultantEarning":
    """Create a ConsultantEarning row after a consultation payment."""
    from models import ConsultantEarning

    # Fee split: admin sets consultation_fee (user pays) and consultant_payout (consultant receives)
    payout = round(payout_amount, 2) if payout_amount is not None else round(gross_amount, 2)
    
    # Platform fee: 0 in case of 100% discount, else: customer paid - Taxes - Consultant payout
    if gross_amount <= 0.0 or discount_pct >= 99.9:
        fee = 0.0
        pct = 0.0
    else:
        fee = round(gross_amount - taxes - payout, 2)
        net_gross = gross_amount - taxes
        pct = round((fee / net_gross * 100), 2) if net_gross > 0.0 else 0.0

    earning = ConsultantEarning(
        consultant_user_id     = consultant_user_id,
        appointment_id         = appointment_id,
        payment_transaction_id = payment_transaction_id,
        gross_amount           = gross_amount,
        platform_fee_pct       = pct,
        platform_fee           = fee,
        consultant_payout      = payout,
        payout_status          = "pending",
        is_test                = _is_test_mode(),  # tag mirror earnings as test
        taxes                  = taxes,
        discount_amount        = discount_amount,
        discount_pct           = discount_pct,
    )
    db.add(earning)
    db.commit()
    db.refresh(earning)
    return earning


# ── main registration ─────────────────────────────────────────────────────────

def _run_bank_column_migration():
    """
    Run bank/UPI column migrations using a raw psycopg2 connection.
    Supports both DATABASE_URL and Cloud Run's individual DB_* env vars.
    """
    import psycopg2

    # ── Build connection params ────────────────────────────────────────────────
    db_url  = os.getenv("DATABASE_URL", "")
    db_user = os.getenv("DB_USER", "")
    db_pass = os.getenv("DB_PASSWORD", "")
    db_name = os.getenv("DB_NAME", "")
    inst    = os.getenv("INSTANCE_CONNECTION_NAME", "")  # project:region:instance

    conn = None
    try:
        if db_url and "postgres" in db_url:
            # Standard URL (local / other environments)
            dsn = (db_url
                   .replace("postgresql+psycopg2://", "postgresql://")
                   .replace("postgresql+pg8000://", "postgresql://"))
            conn = psycopg2.connect(dsn)
        elif inst and db_name:
            # Cloud Run via Unix socket — connect as postgres superuser for DDL
            socket_dir = f"/cloudsql/{inst}"
            conn = psycopg2.connect(
                dbname=db_name,
                user="postgres",
                password=os.getenv("PG_SUPERUSER_PASSWORD", "SoulSquad2024pg"),
                host=socket_dir,
            )
        else:
            print("[BANK-MIGRATION] Skipping — no usable DB connection info")
            return {"skipped": True}
    except Exception as e:
        print(f"[BANK-MIGRATION] Connection error: {e}")
        return {"error": str(e)}

    results = []
    try:
        conn.autocommit = True   # DDL outside transaction = no rollback trap
        cur = conn.cursor()

        alters = [
            ("bank_account_name",   "ALTER TABLE consultant_profiles ADD COLUMN IF NOT EXISTS bank_account_name VARCHAR(255)"),
            ("bank_account_number", "ALTER TABLE consultant_profiles ADD COLUMN IF NOT EXISTS bank_account_number VARCHAR(50)"),
            ("bank_ifsc",           "ALTER TABLE consultant_profiles ADD COLUMN IF NOT EXISTS bank_ifsc VARCHAR(20)"),
            ("bank_name",           "ALTER TABLE consultant_profiles ADD COLUMN IF NOT EXISTS bank_name VARCHAR(100)"),
            ("upi_id",              "ALTER TABLE consultant_profiles ADD COLUMN IF NOT EXISTS upi_id VARCHAR(100)"),
        ]

        # ── is_test column on payment_transactions ────────────────────────────
        # Tag all pre-live transactions (before Razorpay went live on 2026-06-16
        # 17:45 UTC) as test so the finance dashboard can filter them.
        try:
            cur.execute(
                "ALTER TABLE payment_transactions "
                "ADD COLUMN IF NOT EXISTS is_test BOOLEAN NOT NULL DEFAULT FALSE"
            )
            # Back-fill: every transaction created before live deployment is a test
            cur.execute(
                "UPDATE payment_transactions "
                "SET is_test = TRUE "
                "WHERE created_at < '2026-06-16 17:45:00' AND is_test = FALSE"
            )
            print("[MIGRATION] is_test column ensured & back-filled on payment_transactions")
        except Exception as e:
            print(f"[MIGRATION] is_test column error: {e}")
        for col, sql in alters:
            try:
                cur.execute(sql)
                print(f"[BANK-MIGRATION] OK: {col}")
                results.append({"col": col, "status": "ok"})
            except Exception as e:
                print(f"[BANK-MIGRATION] ERROR {col}: {e}")
                results.append({"col": col, "status": "error", "detail": str(e)})

        cur.close()
        conn.close()
        print("[BANK-MIGRATION] Done")
    except Exception as e:
        print(f"[BANK-MIGRATION] Runtime error: {e}")
        results.append({"error": str(e)})

    return results


def register_finance_routes(app: FastAPI, templates: Jinja2Templates, get_db):
    # ── Run bank column migration at startup (raw connection, no session traps) ─
    try:
        _run_bank_column_migration()
    except Exception as _me:
        print(f"[BANK-MIGRATION] Startup call failed: {_me}")

    # ── Reliable SQLAlchemy fallback: ensure is_test column exists ────────────
    # (psycopg2 migration above can silently fail on Cloud Run cold starts)
    try:
        from sqlalchemy import text as _sa_text
        from database import get_db_session
        with get_db_session() as _db:
            # payment_transactions.is_test
            _db.execute(_sa_text(
                "ALTER TABLE payment_transactions "
                "ADD COLUMN IF NOT EXISTS is_test BOOLEAN NOT NULL DEFAULT FALSE"
            ))
            _db.execute(_sa_text(
                "UPDATE payment_transactions "
                "SET is_test = TRUE "
                "WHERE created_at < '2026-06-16 17:45:00'"
            ))
            # consultant_earnings.is_test — backfill via JOIN to payment_transactions
            _db.execute(_sa_text(
                "ALTER TABLE consultant_earnings "
                "ADD COLUMN IF NOT EXISTS is_test BOOLEAN NOT NULL DEFAULT FALSE"
            ))
            _db.execute(_sa_text(
                """
                UPDATE consultant_earnings ce
                SET    is_test = TRUE
                FROM   payment_transactions pt
                WHERE  ce.payment_transaction_id = pt.id
                AND    pt.is_test = TRUE
                """
            ))
            # Fallback for earnings without a payment_transaction link: use date cutoff
            _db.execute(_sa_text(
                "UPDATE consultant_earnings "
                "SET is_test = TRUE "
                "WHERE payment_transaction_id IS NULL "
                "AND   created_at < '2026-06-16 17:45:00'"
            ))
            # ensure appointments has is_test column
            _db.execute(_sa_text(
                "ALTER TABLE appointments "
                "ADD COLUMN IF NOT EXISTS is_test BOOLEAN NOT NULL DEFAULT FALSE"
            ))
            # backfill appointments.is_test = TRUE if there is a corresponding test payment or test earning
            _db.execute(_sa_text(
                """
                UPDATE appointments
                SET    is_test = TRUE
                WHERE  id IN (
                    SELECT appointment_id FROM consultant_earnings WHERE is_test = TRUE AND appointment_id IS NOT NULL
                ) OR id IN (
                    SELECT related_entity_id FROM payment_transactions WHERE related_entity_type = 'appointment' AND is_test = TRUE AND related_entity_id IS NOT NULL
                )
                """
            ))
            _db.commit()
        print("[MIGRATION-SA] is_test columns ensured on payment_transactions, consultant_earnings, and appointments")
    except Exception as _sa_me:
        print(f"[MIGRATION-SA] is_test via SQLAlchemy: {_sa_me}")


    # ── Shared admin guard ────────────────────────────────────────────────────
    def _admin_check(request: Request, db: Session):
        uid = request.session.get("user_id")
        if not uid:
            raise HTTPException(status_code=401, detail="Not authenticated")
        # Prefer session-based role check (fastest, set at login)
        user_type = request.session.get("user_type", "")
        if user_type == "admin":
            from models import User
            user = db.query(User).filter(User.id == uid).first()
            if user:
                return user
        # Fallback: check DB is_admin flag or ADMIN_EMAIL match
        from models import User
        user = db.query(User).filter(User.id == uid).first()
        admin_email = os.getenv("ADMIN_EMAIL", "admin@solacesquad.com")
        if not user or (not getattr(user, "is_admin", False) and user.email != admin_email):
            raise HTTPException(status_code=403, detail="Admin only")
        return user

    def _user_check(request: Request, db: Session):
        uid = request.session.get("user_id")
        if not uid:
            raise HTTPException(status_code=401, detail="Not authenticated")
        return uid

    # ══════════════════════════════════════════════════════════════════════════
    # CONSULTATION BOOKING — Razorpay payment gate
    # ══════════════════════════════════════════════════════════════════════════

    @app.post("/app/appointments/book-init")
    async def appointment_book_init(
        request: Request,
        consultant_id: int = Form(...),
        appointment_date: str = Form(...),
        duration_minutes: int = Form(60),
        notes: str = Form(""),
        consent_to_record: str = Form("false"),
        consent_to_share_data: str = Form("false"),
        db: Session = Depends(get_db),
    ):
        """Create a Razorpay order for a consultation booking."""
        session_uid = request.session.get("user_id")
        if not session_uid:
            return JSONResponse({"success": False, "error": "Not authenticated"}, status_code=401)

        uid = session_uid
        is_admin_booking = False
        impersonate_id = request.session.get("impersonate_user_id")
        if impersonate_id:
            from models import User
            caller = db.query(User).filter(User.id == session_uid).first()
            if caller and caller.user_type == "admin":
                uid = int(str(impersonate_id))
                is_admin_booking = True

        from models import ConsultantProfile
        profile = db.query(ConsultantProfile).filter(ConsultantProfile.id == consultant_id).first()
        if not profile:
            return JSONResponse({"success": False, "error": "Consultant not found"}, status_code=404)

        # ── Safe date parse (datetime-local sends "2026-04-16T10:00" — no seconds) ──
        user_tz = request.session.get("timezone")
        if not user_tz or user_tz == "UTC":
            from models import User
            user = db.query(User).filter(User.id == uid).first()
            user_tz = user.timezone if (user and user.timezone and user.timezone != "UTC") else "Asia/Kolkata"
        try:
            appt_dt = _parse_appt_date(appointment_date, user_tz)
        except Exception:
            return JSONResponse({"success": False, "error": "Invalid date format. Please re-select the date and time."}, status_code=400)

        # ── Run all booking validation rules ──────────────────────────────────
        is_paid = (profile.consultation_fee or 0) > 0 and not is_admin_booking
        if is_admin_booking:
            eff_duration = duration_minutes if duration_minutes in (30, 60, 90) else 60
        else:
            eff_duration = 15 if not is_paid else (duration_minutes if duration_minutes in (30, 60, 90) else 60)

        err = _validate_booking(db, uid, consultant_id, appt_dt, eff_duration, is_paid, request=request)
        if err:
            return JSONResponse(err, status_code=200)  # structured error for UI

        fee = profile.consultation_fee or 0.0
        if fee <= 0 or is_admin_booking:
            # Free consultation — book directly, no payment
            from models import Appointment, User
            appt = Appointment(
                user_id          = uid,
                consultant_id    = consultant_id,
                appointment_date = appt_dt,
                duration_minutes = eff_duration,
                notes            = notes,
                consent_to_record = consent_to_record.lower() == "true",
                consent_to_share_data = consent_to_share_data.lower() == "true",
                status           = "scheduled",
            )
            db.add(appt)
            db.commit()
            db.refresh(appt)

            # -- Confirmation emails (non-fatal) ----------------------------------
            try:
                from sendgrid_email import send_appointment_email
                user = db.query(User).filter(User.id == uid).first()
                user_email       = user.email if user else ""
                user_name        = user.name if user else "User"
                consultant_email = profile.user.email if profile and profile.user else ""
                consultant_name  = profile.user.name if profile and profile.user else "Consultant"
                admin_email = "admin@solacesquad.com"
                shared_kwargs = dict(
                    action="booked", appointment_id=appt.id,
                    user_name=user_name, consultant_name=consultant_name,
                    appointment_date=appt_dt, duration_minutes=eff_duration,
                    notes=notes,
                    organiser_email=user_email, organiser_name=user_name,
                    attendee_emails=[e for e in [user_email, consultant_email, admin_email] if e],
                    admin_booked=is_admin_booking,
                )
                if user_email:
                    send_appointment_email(to_email=user_email, to_name=user_name, **shared_kwargs)
                if consultant_email:
                    send_appointment_email(to_email=consultant_email, to_name=consultant_name, **shared_kwargs)
                send_appointment_email(to_email=admin_email, to_name="SolaceSquad Admin", **shared_kwargs)
            except Exception as mail_err:
                print(f"[Appointment email confirmation - Free] non-fatal error: {mail_err}")

            return JSONResponse({
                "success": True,
                "free": True,
                "appointment_id": appt.id,
                "redirect": "/app/consultants?booked=1",
            })

        # Calculate free 30-min waiver if first consultation
        from models import Appointment
        is_first_consultation = db.query(Appointment).filter(
            Appointment.user_id == uid,
            Appointment.status.in_(["scheduled", "completed", "in_progress"]),
            Appointment.is_test == False
        ).count() == 0

        chargeable_duration = max(0, eff_duration - 30) if is_first_consultation else eff_duration
        prorated_fee = round(fee * (chargeable_duration / 60), 2)

        if prorated_fee <= 0:
            # Free consultation because of first session 30-min waiver — book directly, no payment
            from models import User
            appt = Appointment(
                user_id          = uid,
                consultant_id    = consultant_id,
                appointment_date = appt_dt,
                duration_minutes = eff_duration,
                notes            = notes,
                consent_to_record = consent_to_record.lower() == "true",
                consent_to_share_data = consent_to_share_data.lower() == "true",
                status           = "scheduled",
            )
            db.add(appt)
            db.flush()

            # Log consultant earning (gross_amount = 0, no txn)
            std_base = fee * (eff_duration / 60.0)
            std_gross = round(std_base * 1.18, 2)
            log_consultant_earning(
                db                     = db,
                consultant_user_id     = profile.user_id,
                appointment_id         = appt.id,
                payment_transaction_id = None,
                gross_amount           = 0.0,
                payout_amount          = round((profile.consultant_payout or fee) * (eff_duration / 60), 2),
                taxes                  = 0.0,
                discount_amount        = std_gross,
                discount_pct           = 100.0,
            )
            db.commit()
            db.refresh(appt)

            # -- Confirmation emails (non-fatal) ----------------------------------
            try:
                from sendgrid_email import send_appointment_email
                user = db.query(User).filter(User.id == uid).first()
                user_email       = user.email if user else ""
                user_name        = user.name if user else "User"
                consultant_email = profile.user.email if profile and profile.user else ""
                consultant_name  = profile.user.name if profile and profile.user else "Consultant"
                admin_email = "admin@solacesquad.com"
                shared_kwargs = dict(
                    action="booked", appointment_id=appt.id,
                    user_name=user_name, consultant_name=consultant_name,
                    appointment_date=appt_dt, duration_minutes=eff_duration,
                    notes=notes,
                    organiser_email=user_email, organiser_name=user_name,
                    attendee_emails=[e for e in [user_email, consultant_email, admin_email] if e],
                    admin_booked=is_admin_booking,
                )
                if user_email:
                    send_appointment_email(to_email=user_email, to_name=user_name, **shared_kwargs)
                if consultant_email:
                    send_appointment_email(to_email=consultant_email, to_name=consultant_name, **shared_kwargs)
                send_appointment_email(to_email=admin_email, to_name="SolaceSquad Admin", **shared_kwargs)
            except Exception as mail_err:
                print(f"[Appointment email confirmation - Free Waiver] non-fatal error: {mail_err}")

            return JSONResponse({
                "success": True,
                "free": True,
                "appointment_id": appt.id,
                "redirect": "/app/consultants?booked=1",
            })

        client, _ = _razorpay_client()
        if not client:
            return JSONResponse({"success": False, "error": "Payment gateway not configured"}, status_code=503)

        # ── Plan-based consultation discount ─────────────────────────────────
        discount_pct    = 0
        discount_amount = 0.0
        try:
            from subscription_routes import get_user_plan_caps
            p_caps   = get_user_plan_caps(uid, db)
            disc_cap = p_caps.get("consultation_discount")
            if disc_cap and disc_cap.limit_value > 0:
                discount_pct    = int(disc_cap.limit_value)          # e.g. 25
                discount_amount = round(prorated_fee * discount_pct / 100, 2)
                prorated_fee    = round(prorated_fee - discount_amount, 2)
        except Exception:
            pass

        # Add 18% GST
        gst_amount = round(prorated_fee * 0.18, 2)
        prorated_fee = round(prorated_fee + gst_amount, 2)

        amount_paise = int(prorated_fee * 100)
        from models import User
        user = db.query(User).filter(User.id == uid).first()
        order = client.order.create({
            "amount": amount_paise,
            "currency": "INR",
            "receipt": f"appt-{uid}-{consultant_id}-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}",
            "notes": {
                "user_id": str(uid),
                "consultant_id": str(consultant_id),
                "appointment_date": appointment_date,
            },
        })

        return JSONResponse({
            "success": True,
            "free": False,
            "razorpay_order_id": order["id"],
            "razorpay_key_id": os.getenv("RAZORPAY_KEY_ID"),
            "amount": amount_paise,
            "currency": "INR",
            "discount_pct":    discount_pct,
            "discount_amount": discount_amount,
            "original_amount": int(round(fee * (chargeable_duration / 60) * 1.18, 2) * 100),  # paise before plan discount including GST
            "consultant_name": profile.full_name or "Consultant",
            "user_name": user.name if user else "",
            "user_email": user.email if user else "",
            "appointment_date": appointment_date,
            "duration": eff_duration,
            "hourly_rate": fee,          # for display: "₹X/hr" in description
            "prorated_fee": prorated_fee, # actual charge for this session (with GST)
            "notes": notes,
            "consultant_id": consultant_id,
            "platform_fee_pct": 0.0,
        })

    @app.post("/app/appointments/book-confirm")
    async def appointment_book_confirm(
        request: Request,
        razorpay_order_id: str = Form(...),
        razorpay_payment_id: str = Form(...),
        razorpay_signature: str = Form(...),
        consultant_id: int = Form(...),
        appointment_date: str = Form(...),
        duration_minutes: int = Form(60),
        notes: str = Form(""),
        consent_to_record: str = Form("false"),
        consent_to_share_data: str = Form("false"),
        db: Session = Depends(get_db),
    ):
        """Verify Razorpay payment, save appointment, log PaymentTransaction and ConsultantEarning."""
        uid = request.session.get("user_id")
        if not uid:
            return JSONResponse({"success": False, "error": "Not authenticated"}, status_code=401)

        _, key_secret = _razorpay_client()
        if not key_secret:
            return JSONResponse({"success": False, "error": "Payment gateway not configured"}, status_code=503)

        # HMAC verification
        expected = hmac.new(
            key_secret.encode(),
            f"{razorpay_order_id}|{razorpay_payment_id}".encode(),
            hashlib.sha256,
        ).hexdigest()
        if not hmac.compare_digest(expected, razorpay_signature):
            return JSONResponse({"success": False, "error": "Payment verification failed"}, status_code=400)

        from models import ConsultantProfile, Appointment, User
        profile = db.query(ConsultantProfile).filter(ConsultantProfile.id == consultant_id).first()
        user    = db.query(User).filter(User.id == uid).first()
        if not profile:
            return JSONResponse({"success": False, "error": "Consultant not found"}, status_code=404)

        # ── Safe date parse ───────────────────────────────────────────────────
        user_tz = request.session.get("timezone")
        if not user_tz or user_tz == "UTC":
            user_tz = user.timezone if (user and user.timezone and user.timezone != "UTC") else "Asia/Kolkata"
        try:
            appt_dt = _parse_appt_date(appointment_date, user_tz)
        except Exception:
            return JSONResponse({"success": False, "error": "Invalid appointment date"}, status_code=400)

        is_paid      = (profile.consultation_fee or 0) > 0
        eff_duration = duration_minutes if duration_minutes in (30, 60, 90) else 60

        # Re-validate (guards race conditions between order creation and confirm)
        err = _validate_booking(db, uid, consultant_id, appt_dt, eff_duration, is_paid, request=request)
        if err:
            return JSONResponse(err, status_code=200)

        # Prorate the hourly rate by booked duration
        hourly_rate  = profile.consultation_fee or 0.0

        is_first_consultation = db.query(Appointment).filter(
            Appointment.user_id == uid,
            Appointment.status.in_(["scheduled", "completed", "in_progress"]),
            Appointment.is_test == False
        ).count() == 0

        chargeable_duration = max(0, eff_duration - 30) if is_first_consultation else eff_duration
        prorated_fee = round(hourly_rate * (chargeable_duration / 60), 2)

        # ── Plan-based consultation discount ─────────────────────────────────
        try:
            from subscription_routes import get_user_plan_caps
            p_caps   = get_user_plan_caps(uid, db)
            disc_cap = p_caps.get("consultation_discount")
            if disc_cap and disc_cap.limit_value > 0:
                discount_pct    = int(disc_cap.limit_value)          # e.g. 25
                discount_amount = round(prorated_fee * discount_pct / 100, 2)
                prorated_fee    = round(prorated_fee - discount_amount, 2)
        except Exception:
            pass

        # Add 18% GST
        gst_amount = round(prorated_fee * 0.18, 2)
        prorated_fee = round(prorated_fee + gst_amount, 2)

        consultant_name  = profile.full_name or "Consultant"

        # 1. Save appointment
        appt = Appointment(
            user_id          = uid,
            consultant_id    = consultant_id,
            appointment_date = appt_dt,
            duration_minutes = eff_duration,
            notes            = notes,
            consent_to_record = consent_to_record.lower() == "true",
            consent_to_share_data = consent_to_share_data.lower() == "true",
            status           = "scheduled",
        )
        db.add(appt)
        db.flush()  # get appt.id before commit

        # 2. Log payment transaction (prorated amount actually charged)
        txn = log_payment_transaction(
            db                  = db,
            user_id             = uid,
            transaction_type    = "consultation",
            amount              = prorated_fee,
            status              = "completed",
            razorpay_order_id   = razorpay_order_id,
            razorpay_payment_id = razorpay_payment_id,
            razorpay_signature  = razorpay_signature,
            related_entity_type = "appointment",
            related_entity_id   = appt.id,
            description         = f"Consultation with {consultant_name} on {appointment_date[:10]} ({eff_duration} min @ ₹{hourly_rate}/hr)",
        )

        # Calculate gross, taxes, and discounts
        gross_val = prorated_fee
        taxes_val = round(prorated_fee - (prorated_fee / 1.18), 2)
        std_base  = hourly_rate * (eff_duration / 60.0)
        std_gross = round(std_base * 1.18, 2)
        disc_amt  = max(0.0, round(std_gross - prorated_fee, 2))
        disc_pct  = round((disc_amt / std_gross * 100), 2) if std_gross > 0 else 0.0

        log_consultant_earning(
            db                     = db,
            consultant_user_id     = profile.user_id,
            appointment_id         = appt.id,
            payment_transaction_id = txn.id,
            gross_amount           = gross_val,
            payout_amount          = round((profile.consultant_payout or hourly_rate) * (eff_duration / 60), 2),
            taxes                  = taxes_val,
            discount_amount        = disc_amt,
            discount_pct           = disc_pct,
        )

        db.commit()

        # -- Confirmation emails (non-fatal) ----------------------------------
        try:
            from sendgrid_email import send_appointment_email
            user_email       = user.email if user else ""
            user_name        = user.name if user else "User"
            consultant_email = profile.user.email if profile and profile.user else ""
            consultant_name  = profile.user.name if profile and profile.user else "Consultant"
            admin_email = "admin@solacesquad.com"
            shared_kwargs = dict(
                action="booked", appointment_id=appt.id,
                user_name=user_name, consultant_name=consultant_name,
                appointment_date=appt_dt, duration_minutes=eff_duration,
                notes=notes,
                organiser_email=user_email, organiser_name=user_name,
                attendee_emails=[e for e in [user_email, consultant_email, admin_email] if e],
            )
            if user_email:
                send_appointment_email(to_email=user_email, to_name=user_name, **shared_kwargs)
            if consultant_email:
                send_appointment_email(to_email=consultant_email, to_name=consultant_name, **shared_kwargs)
            send_appointment_email(to_email=admin_email, to_name="SolaceSquad Admin", **shared_kwargs)
        except Exception as mail_err:
            print(f"[Appointment email confirmation] non-fatal error: {mail_err}")

        return JSONResponse({
            "success": True,
            "appointment_id": appt.id,
            "invoice_number": txn.invoice_number,
            "redirect": f"/app/consultants?booked=1",
        })

    # ══════════════════════════════════════════════════════════════════════════
    # ADMIN — Finance Dashboard
    # ══════════════════════════════════════════════════════════════════════════

    @app.get("/admin/finance", response_class=HTMLResponse)
    async def admin_finance_page(request: Request, db: Session = Depends(get_db)):
        try:
            _admin_check(request, db)
        except HTTPException:
            return HTMLResponse('<script>location="/login"</script>', status_code=302)
        return templates.TemplateResponse("pages/admin_finance.html", {
            "request":      request,
            "page_title":   "Finance — SolaceSquad Admin",
            "is_live_mode": not _is_test_mode(),   # True in production
        })

    @app.get("/api/admin/consultants")
    async def get_admin_consultants_list(
        request: Request,
        db: Session = Depends(get_db),
        page: int = 1,
        per_page: int = 200,
    ):
        _admin_check(request, db)
        from models import ConsultantProfile, User
        # Query all approved consultants
        q = db.query(ConsultantProfile, User).join(User, ConsultantProfile.user_id == User.id).filter(
            ConsultantProfile.is_approved == True
        )

        total = q.count()
        rows = q.offset((page - 1) * per_page).limit(per_page).all()

        consultants_list = []
        for cp, u in rows:
            consultants_list.append({
                "id": cp.id,
                "user_id": cp.user_id,
                "name": u.name or u.email,
                "email": u.email,
            })

        return {
            "total": total,
            "page": page,
            "per_page": per_page,
            "consultants": consultants_list,
        }


    @app.get("/api/admin/finance/summary")
    async def admin_finance_summary(request: Request, db: Session = Depends(get_db)):
        _admin_check(request, db)
        from models import PaymentTransaction, ConsultantEarning
        now = datetime.utcnow()
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        live_mode   = not _is_test_mode()   # True in production
        mirror_mode = _is_test_mode()        # True in mirror/dev

        # Base filter: always scope to the correct environment
        def _base(q):
            if live_mode:
                return q.filter(PaymentTransaction.is_test == False)
            elif mirror_mode:
                return q.filter(PaymentTransaction.is_test == True)
            return q

        # ConsultantEarning base filter
        def _ce_base(q):
            if live_mode:
                return q.filter(ConsultantEarning.is_test == False)
            elif mirror_mode:
                return q.filter(ConsultantEarning.is_test == True)
            return q

        total_revenue    = _base(db.query(func.sum(PaymentTransaction.amount)).filter(PaymentTransaction.status == "completed")).scalar() or 0.0
        mtd_revenue      = _base(db.query(func.sum(PaymentTransaction.amount))).filter(
            PaymentTransaction.status == "completed",
            PaymentTransaction.created_at >= month_start,
        ).scalar() or 0.0
        total_txns       = _base(db.query(func.count(PaymentTransaction.id)).filter(PaymentTransaction.status == "completed")).scalar() or 0
        # Pending payouts: scope to current environment
        pending_payouts = _ce_base(
            db.query(func.sum(ConsultantEarning.consultant_payout)).filter(
                ConsultantEarning.payout_status == "pending"
            )
        ).scalar() or 0.0
        total_subs       = _base(db.query(func.sum(PaymentTransaction.amount)).filter(
            PaymentTransaction.transaction_type == "subscription",
            PaymentTransaction.status == "completed",
        )).scalar() or 0.0
        total_consult    = _base(db.query(func.sum(PaymentTransaction.amount)).filter(
            PaymentTransaction.transaction_type == "consultation",
            PaymentTransaction.status == "completed",
        )).scalar() or 0.0

        live_revenue     = db.query(func.sum(PaymentTransaction.amount)).filter(
            PaymentTransaction.status  == "completed",
            PaymentTransaction.is_test == False,
        ).scalar() or 0.0
        test_revenue     = (0.0 if live_mode else (
            db.query(func.sum(PaymentTransaction.amount)).filter(
                PaymentTransaction.status  == "completed",
                PaymentTransaction.is_test == True,
            ).scalar() or 0.0
        ))
        live_txns        = db.query(func.count(PaymentTransaction.id)).filter(
            PaymentTransaction.status  == "completed",
            PaymentTransaction.is_test == False,
        ).scalar() or 0
        test_txns        = (0 if live_mode else (
            db.query(func.count(PaymentTransaction.id)).filter(
                PaymentTransaction.status  == "completed",
                PaymentTransaction.is_test == True,
            ).scalar() or 0
        ))
        mtd_live         = db.query(func.sum(PaymentTransaction.amount)).filter(
            PaymentTransaction.status     == "completed",
            PaymentTransaction.is_test    == False,
            PaymentTransaction.created_at >= month_start,
        ).scalar() or 0.0

        return {
            "total_revenue":         round(total_revenue, 2),
            "live_revenue":          round(live_revenue, 2),
            "test_revenue":          round(test_revenue, 2),
            "mtd_revenue":           round(mtd_revenue, 2),
            "mtd_live_revenue":      round(mtd_live, 2),
            "total_transactions":    total_txns,
            "live_transactions":     live_txns,
            "test_transactions":     test_txns,
            "pending_payouts":       round(pending_payouts, 2),
            "subscription_revenue":  round(total_subs, 2),
            "consultation_revenue":  round(total_consult, 2),
        }

    @app.get("/api/admin/finance/transactions")
    async def admin_finance_transactions(
        request: Request,
        db: Session = Depends(get_db),
        page: int = 1,
        per_page: int = 50,
        txn_type: str = "",
        status: str = "",
        user_id: Optional[int] = None,
        date_from: str = "",
        date_to: str = "",
        search: str = "",
        mode: str = "",    # "live" | "test" | "" (all)
    ):
        _admin_check(request, db)
        from models import PaymentTransaction, User

        # Force mode based on environment — production sees only live; mirror sees only test
        if not _is_test_mode():
            mode = "live"
        else:
            mode = "test"

        q = db.query(PaymentTransaction, User).join(User, PaymentTransaction.user_id == User.id)

        if txn_type:
            q = q.filter(PaymentTransaction.transaction_type == txn_type)
        if status:
            q = q.filter(PaymentTransaction.status == status)
        if user_id:
            q = q.filter(PaymentTransaction.user_id == user_id)
        if date_from:
            try:
                q = q.filter(PaymentTransaction.created_at >= datetime.fromisoformat(date_from))
            except ValueError:
                pass
        if date_to:
            try:
                q = q.filter(PaymentTransaction.created_at <= datetime.fromisoformat(date_to + "T23:59:59"))
            except ValueError:
                pass
        if search:
            q = q.filter(or_(
                User.name.ilike(f"%{search}%"),
                User.email.ilike(f"%{search}%"),
                PaymentTransaction.invoice_number.ilike(f"%{search}%"),
                PaymentTransaction.razorpay_payment_id.ilike(f"%{search}%"),
            ))
        try:
            if mode == "live":
                q = q.filter(PaymentTransaction.is_test == False)
            elif mode == "test":
                q = q.filter(PaymentTransaction.is_test == True)

            total = q.count()
            rows  = q.order_by(desc(PaymentTransaction.created_at)).offset((page - 1) * per_page).limit(per_page).all()
        except Exception as _qe:
            # is_test column may not exist yet — fall back to unfiltered query
            print(f"[FINANCE] is_test filter failed ({_qe}), falling back to unfiltered query")
            q2 = db.query(PaymentTransaction, User).join(User, PaymentTransaction.user_id == User.id)
            if txn_type:
                q2 = q2.filter(PaymentTransaction.transaction_type == txn_type)
            if status:
                q2 = q2.filter(PaymentTransaction.status == status)
            total = q2.count()
            rows  = q2.order_by(desc(PaymentTransaction.created_at)).offset((page - 1) * per_page).limit(per_page).all()

        return {
            "total": total,
            "page": page,
            "per_page": per_page,
            "transactions": [
                {
                    "id":                   t.id,
                    "invoice_number":       t.invoice_number,
                    "user_id":              t.user_id,
                    "user_name":            u.name,
                    "user_email":           u.email,
                    "transaction_type":     t.transaction_type,
                    "amount":               t.amount,
                    "currency":             t.currency,
                    "status":               t.status,
                    "description":          t.description,
                    "razorpay_order_id":    t.razorpay_order_id,
                    "razorpay_payment_id":  t.razorpay_payment_id,
                    "related_entity_type":  t.related_entity_type,
                    "related_entity_id":    t.related_entity_id,
                    "refunded_at":          t.refunded_at.isoformat() if t.refunded_at else None,
                    "created_at":           t.created_at.isoformat(),
                    "is_test":              bool(getattr(t, 'is_test', False)),
                }
                for t, u in rows
            ],
        }

    @app.get("/api/admin/finance/consultant/{consultant_user_id}/earnings")
    async def admin_consultant_earnings(
        request: Request,
        consultant_user_id: int,
        db: Session = Depends(get_db),
        date_from: str = "",
        date_to: str = "",
        payout_status: str = "",
    ):
        _admin_check(request, db)
        from models import ConsultantEarning, Appointment, User, PaymentTransaction

        q = (
            db.query(ConsultantEarning, PaymentTransaction, Appointment, User)
            .outerjoin(PaymentTransaction, ConsultantEarning.payment_transaction_id == PaymentTransaction.id)
            .outerjoin(Appointment,        ConsultantEarning.appointment_id == Appointment.id)
            .outerjoin(User,               Appointment.user_id == User.id)
            .filter(ConsultantEarning.consultant_user_id == consultant_user_id)
        )
        # Scope to current environment (production=live only, mirror=test only)
        if not _is_test_mode():
            q = q.filter(ConsultantEarning.is_test == False)
        else:
            q = q.filter(ConsultantEarning.is_test == True)
        if payout_status:
            q = q.filter(ConsultantEarning.payout_status == payout_status)
        if date_from:
            try:
                q = q.filter(ConsultantEarning.created_at >= datetime.fromisoformat(date_from))
            except ValueError:
                pass
        if date_to:
            try:
                q = q.filter(ConsultantEarning.created_at <= datetime.fromisoformat(date_to + "T23:59:59"))
            except ValueError:
                pass

        rows = q.order_by(desc(ConsultantEarning.created_at)).all()

        # Consultant info
        from models import ConsultantProfile
        cp = db.query(ConsultantProfile).filter(ConsultantProfile.user_id == consultant_user_id).first()
        cu = db.query(User).filter(User.id == consultant_user_id).first()

        # Prepare rows list and calculate summaries
        earnings_list = []
        total_gross = 0.0
        total_payout = 0.0
        total_fee = 0.0
        pending = 0.0

        for e, txn, appt, client in rows:
            # 1. customer_paid (Gross amount)
            if appt:
                # If we have a transaction, use the transaction amount (which includes GST).
                # For legacy records, gross_amount was stored without GST, so txn.amount is the true amount paid.
                # If no transaction (free first session), customer paid 0.0.
                customer_paid = txn.amount if txn else 0.0
            else:
                customer_paid = e.gross_amount

            # 2. taxes
            # For new entries, e.taxes is saved.
            # For legacy paid appointments, e.taxes was migrated as 0.0. Compute it dynamically if there is a payment.
            if getattr(e, "taxes", 0.0) is not None and getattr(e, "taxes", 0.0) > 0.0:
                taxes_val = e.taxes
            elif txn and customer_paid > 0.0:
                taxes_val = round(customer_paid - (customer_paid / 1.18), 2)
            else:
                taxes_val = 0.0

            # 3. discount_amount and discount_pct
            # For new entries, e.discount_amount is saved.
            # For legacy paid appointments, it was migrated as 0.0. Compute it dynamically if there is a payment.
            if getattr(e, "discount_amount", 0.0) is not None and getattr(e, "discount_amount", 0.0) > 0.0:
                disc_amt = e.discount_amount
                disc_pct = e.discount_pct
            elif appt:
                # Legacy record approximation
                profile = appt.consultant
                base_rate = profile.consultation_fee or profile.hourly_rate or 500.0
                standard_base = base_rate * (appt.duration_minutes / 60.0)
                standard_gross = round(standard_base * 1.18, 2)
                if customer_paid < standard_gross:
                    disc_amt = max(0.0, round(standard_gross - customer_paid, 2))
                    disc_pct = round((disc_amt / standard_gross * 100), 2) if standard_gross > 0 else 0.0
                else:
                    disc_amt = 0.0
                    disc_pct = 0.0
            else:
                disc_amt = 0.0
                disc_pct = 0.0

            # 4. platform_fee
            # Requirement 3: platform fee is 0 in case of 100% discount, else: customer paid - Taxes - Consultant payout
            is_hundred_percent = (customer_paid == 0.0 and e.consultant_payout > 0.0) or (disc_pct >= 99.9)
            if is_hundred_percent:
                platform_fee_val = 0.0
                platform_fee_pct_val = 0.0
            else:
                platform_fee_val = round(customer_paid - taxes_val - e.consultant_payout, 2)
                net_gross = customer_paid - taxes_val
                platform_fee_pct_val = round((platform_fee_val / net_gross * 100), 2) if net_gross > 0.0 else 0.0

            # Increment totals
            total_gross += customer_paid
            total_payout += e.consultant_payout
            total_fee += platform_fee_val
            if e.payout_status == "pending":
                pending += e.consultant_payout

            earnings_list.append({
                "id":               e.id,
                "appointment_id":   e.appointment_id,
                "appointment_date": appt.appointment_date.isoformat() if appt else (e.event_workshop.event_date.isoformat() if e.event_workshop else None),
                "client_name":      client.name if client else (f"Event: {e.event_workshop.title}" if e.event_workshop else "Unknown"),
                "fee_tag":          "consultation fee" if e.appointment_id else (f"{e.event_workshop.event_mode} {'webinar' if e.event_workshop.type == 'event' else e.event_workshop.type} fee" if e.event_workshop else "financial entry"),
                "gross_amount":     round(customer_paid, 2),
                "taxes":            round(taxes_val, 2),
                "discount_amount":  round(disc_amt, 2),
                "discount_pct":     round(disc_pct, 2),
                "platform_fee_pct": round(platform_fee_pct_val, 2),
                "platform_fee":     round(platform_fee_val, 2),
                "consultant_payout":round(e.consultant_payout, 2),
                "payout_status":    e.payout_status,
                "payout_date":      e.payout_date.isoformat() if e.payout_date else None,
                "payout_reference": e.payout_reference,
                "admin_notes":      e.admin_notes,
                "invoice_number":   txn.invoice_number if txn else None,
                "created_at":       e.created_at.isoformat(),
            })

        return {
            "consultant_user_id": consultant_user_id,
            "consultant_name":  cu.name  if cu else "Unknown",
            "consultant_email": cu.email if cu else "",
            "platform_fee_pct": 0.0,
            "bank_details": {
                "bank_account_name":   cp.bank_account_name   if cp else None,
                "bank_account_number": cp.bank_account_number if cp else None,
                "bank_ifsc":           cp.bank_ifsc           if cp else None,
                "bank_name":           cp.bank_name           if cp else None,
                "upi_id":              cp.upi_id              if cp else None,
            },
            "summary": {
                "total_gross":             round(total_gross,  2),
                "total_platform_fee":      round(total_fee,    2),
                "total_consultant_payout": round(total_payout, 2),
                "pending_payout":          round(pending,      2),
                "session_count":           len(rows),
            },
            "earnings": earnings_list,
        }

    # ── Admin: Appointment Sessions itemized ledger ─────────────────────────────
    @app.get("/api/admin/finance/appointment-sessions")
    async def admin_appointment_sessions(
        request: Request,
        db: Session = Depends(get_db),
        consultant_user_id: Optional[int] = None,
        user_id: Optional[int] = None,
        appt_status: str = "",    # upcoming|completed|cancelled|no_show_both
        date_from: str = "",
        date_to: str = "",
        page: int = 1,
        per_page: int = 50,
    ):
        _admin_check(request, db)

        from sqlalchemy import text
        now = datetime.utcnow()
        is_test = _is_test_mode()

        # Auto-complete past in_progress appointments in database
        try:
            db.execute(
                text(
                    "UPDATE appointments "
                    "SET status = 'completed' "
                    "WHERE status = 'in_progress' AND appointment_date < :now - (duration_minutes * INTERVAL '1 minute')"
                ),
                {"now": now}
            )
            db.commit()
        except Exception as _sync_err:
            db.rollback()
            print(f"[Sync-Appointments] Warning: Auto-completing past in_progress failed: {_sync_err}")

        # Build dynamic WHERE clauses
        where_parts = ["a.is_test = :is_test"]
        params: dict = {"is_test": is_test, "now": now}

        if consultant_user_id:
            where_parts.append("cp.user_id = :consultant_user_id")
            params["consultant_user_id"] = consultant_user_id
        if user_id:
            where_parts.append("a.user_id = :user_id")
            params["user_id"] = user_id
        if date_from:
            try:
                datetime.fromisoformat(date_from)
                where_parts.append("a.appointment_date >= :date_from")
                params["date_from"] = date_from
            except ValueError:
                pass
        if date_to:
            try:
                datetime.fromisoformat(date_to)
                where_parts.append("a.appointment_date <= :date_to")
                params["date_to"] = date_to + "T23:59:59"
            except ValueError:
                pass

        if appt_status == "upcoming":
            where_parts.append("a.status = 'scheduled' AND a.appointment_date >= :now")
        elif appt_status == "completed":
            where_parts.append("a.status = 'completed'")
        elif appt_status == "cancelled":
            where_parts.append("a.status = 'cancelled'")
        elif appt_status == "no_show_both":
            where_parts.append("a.status = 'scheduled' AND a.appointment_date < :now")

        where_sql = " AND ".join(where_parts)

        base_sql = f"""
            FROM appointments a
            JOIN users u ON u.id = a.user_id
            JOIN consultant_profiles cp ON cp.id = a.consultant_id
            JOIN users cu ON cu.id = cp.user_id
            LEFT JOIN consultant_earnings ce ON ce.appointment_id = a.id
            LEFT JOIN payment_transactions pt ON pt.id = ce.payment_transaction_id
            LEFT JOIN call_sessions cs ON cs.appointment_id = a.id
            WHERE {where_sql}
        """

        # Count
        count_result = db.execute(text(f"SELECT COUNT(*) {base_sql}"), params)
        total = count_result.scalar() or 0

        # Fetch page
        select_sql = f"""
            SELECT
                a.id              AS appointment_id,
                a.appointment_date,
                a.status          AS appointment_status,
                a.duration_minutes,
                a.user_id,
                u.name            AS user_name,
                u.email           AS user_email,
                cp.user_id        AS consultant_user_id,
                cu.name           AS consultant_name,
                cu.email          AS consultant_email,
                cp.specialization AS consultant_specialization,
                ce.id             AS earning_id,
                COALESCE(ce.gross_amount, 0)          AS gross_amount,
                COALESCE(ce.consultant_payout, 0)     AS consultant_payout,
                COALESCE(ce.platform_fee, 0)          AS platform_fee,
                ce.payout_status,
                pt.invoice_number,
                pt.status         AS txn_status,
                cs.actual_start   AS call_started,
                cs.duration_seconds AS call_duration_sec
            {base_sql}
            ORDER BY a.appointment_date DESC, a.id DESC
            LIMIT :limit OFFSET :offset
        """
        params["limit"]  = per_page
        params["offset"] = (page - 1) * per_page

        rows = db.execute(text(select_sql), params).fetchall()

        result = []
        for r in rows:
            # Compute derived status
            appt_date = r.appointment_date
            if hasattr(appt_date, 'replace'):
                is_past = appt_date < now
            else:
                is_past = True

            status = r.appointment_status
            if status == "completed":
                derived = "completed"
            elif status == "cancelled":
                derived = "cancelled"
            elif status == "scheduled" and not is_past:
                derived = "upcoming"
            elif status == "scheduled" and is_past:
                if r.call_started and r.call_duration_sec and r.call_duration_sec > 60:
                    derived = "completed"
                else:
                    derived = "no_show_both"
            else:
                derived = status

            # Skip if filtering by no_show and derived doesn't match
            if appt_status == "no_show_both" and derived != "no_show_both":
                continue

            gross = float(r.gross_amount or 0)
            payout = float(r.consultant_payout or 0)
            payout_status = r.payout_status

            if derived == "cancelled":
                payout = 0.0
                payout_status = "on_hold"

            is_free = (gross == 0 and r.invoice_number is None and r.earning_id is None)

            result.append({
                "appointment_id":             r.appointment_id,
                "appointment_date":           r.appointment_date.isoformat() if r.appointment_date else None,
                "appointment_status":         r.appointment_status,
                "derived_status":             derived,
                "duration_minutes":           r.duration_minutes or 60,
                "user_id":                    r.user_id,
                "user_name":                  r.user_name or "Unknown",
                "user_email":                 r.user_email or "",
                "consultant_user_id":         r.consultant_user_id,
                "consultant_name":            r.consultant_name or "Unknown",
                "consultant_email":           r.consultant_email or "",
                "consultant_specialization":  r.consultant_specialization or "",
                "is_free":                    is_free,
                "gross_amount":               gross,
                "consultant_payout":          payout,
                "platform_fee":               float(r.platform_fee or 0),
                "payout_status":              payout_status,
                "invoice_number":             r.invoice_number,
                "txn_status":                 r.txn_status,
                "call_started":               r.call_started.isoformat() if r.call_started else None,
                "call_duration_sec":          r.call_duration_sec,
            })


        return {
            "total":    total,
            "page":     page,
            "per_page": per_page,
            "sessions": result,
        }




    @app.post("/api/admin/finance/consultant-earnings/{earning_id}/mark-paid")
    async def admin_mark_earning_paid(
        request: Request,
        earning_id: int,
        payout_reference: str = Form(""),
        admin_notes: str = Form(""),
        db: Session = Depends(get_db),
    ):

        _admin_check(request, db)
        from models import ConsultantEarning, ConsultantProfile, User
        earning = db.query(ConsultantEarning).filter(ConsultantEarning.id == earning_id).first()
        if not earning:
            return JSONResponse({"success": False, "error": "Not found"}, status_code=404)
        if earning.payout_status == "paid":
            return JSONResponse({"success": False, "error": "This earning has already been marked paid."}, status_code=400)
        if not payout_reference.strip():
            return JSONResponse({"success": False, "error": "Payout reference (UTR/transaction ID) is required before marking as paid."}, status_code=400)

        earning.payout_status    = "paid"
        earning.payout_date      = datetime.utcnow()
        earning.payout_reference = payout_reference.strip()
        earning.admin_notes      = admin_notes
        db.commit()

        # Fetch consultant info for confirmation
        consultant = db.query(User).filter(User.id == earning.consultant_user_id).first()
        profile    = db.query(ConsultantProfile).filter(ConsultantProfile.user_id == earning.consultant_user_id).first()
        return {
            "success":            True,
            "consultant_name":    consultant.name if consultant else "",
            "payout_amount":      earning.consultant_payout,
            "payout_reference":   payout_reference,
            "upi_id":             profile.upi_id if profile else None,
            "bank_account_number": profile.bank_account_number if profile else None,
        }

    @app.post("/api/admin/finance/consultant-earnings/{earning_id}/mark-free")
    async def admin_mark_earning_free(
        request: Request,
        earning_id: int,
        db: Session = Depends(get_db),
    ):
        _admin_check(request, db)
        from models import ConsultantEarning
        earning = db.query(ConsultantEarning).filter(ConsultantEarning.id == earning_id).first()
        if not earning:
            return JSONResponse({"success": False, "error": "Not found"}, status_code=404)

        # Store original payout amount in admin_notes before setting to 0, just in case we need to restore it
        if earning.consultant_payout > 0:
            original_payout = earning.consultant_payout
            if not earning.admin_notes:
                earning.admin_notes = f"original_payout:{original_payout}"
            elif "original_payout:" not in earning.admin_notes:
                earning.admin_notes += f" | original_payout:{original_payout}"

        earning.payout_status = "free"
        earning.consultant_payout = 0.0
        db.commit()
        return {"success": True}

    @app.post("/api/admin/finance/consultant-earnings/{earning_id}/restore-pending")
    async def admin_restore_earning_pending(
        request: Request,
        earning_id: int,
        db: Session = Depends(get_db),
    ):
        _admin_check(request, db)
        from models import ConsultantEarning, Appointment, ConsultantProfile
        earning = db.query(ConsultantEarning).filter(ConsultantEarning.id == earning_id).first()
        if not earning:
            return JSONResponse({"success": False, "error": "Not found"}, status_code=404)

        # Restore original payout
        original_payout = None
        if earning.admin_notes and "original_payout:" in earning.admin_notes:
            try:
                parts = earning.admin_notes.split("original_payout:")
                original_payout = float(parts[-1].split(" ")[0].split("|")[0].strip())
            except Exception:
                pass

        if original_payout is None:
            # Recompute based on profile and duration
            if earning.appointment_id:
                appt = db.query(Appointment).filter(Appointment.id == earning.appointment_id).first()
                if appt:
                    profile = db.query(ConsultantProfile).filter(ConsultantProfile.id == appt.consultant_id).first()
                    if profile:
                        rate = profile.consultant_payout or profile.consultation_fee or profile.hourly_rate or 500.0
                        original_payout = round(rate * (appt.duration_minutes / 60.0), 2)
            if original_payout is None:
                original_payout = 500.0  # Fallback

        earning.consultant_payout = original_payout
        earning.payout_status = "pending"
        db.commit()
        return {"success": True}

    # ── Consultant: get/save payout bank details ───────────────────────────────
    @app.get("/api/consultant/payout-details")
    async def consultant_get_payout_details(request: Request, db: Session = Depends(get_db)):
        uid = request.session.get("user_id")
        if not uid or request.session.get("user_type") != "consultant":
            return JSONResponse({"success": False}, status_code=401)
        from models import ConsultantProfile
        profile = db.query(ConsultantProfile).filter(ConsultantProfile.user_id == uid).first()
        return {
            "success":            True,
            "bank_account_name":  profile.bank_account_name  if profile else None,
            "bank_account_number": profile.bank_account_number if profile else None,
            "bank_ifsc":          profile.bank_ifsc           if profile else None,
            "bank_name":          profile.bank_name           if profile else None,
            "upi_id":             profile.upi_id              if profile else None,
        }

    @app.post("/api/consultant/payout-details")
    async def consultant_save_payout_details(request: Request, db: Session = Depends(get_db)):
        uid = request.session.get("user_id")
        if not uid or request.session.get("user_type") != "consultant":
            return JSONResponse({"success": False}, status_code=401)
        from models import ConsultantProfile
        data    = await request.json()
        profile = db.query(ConsultantProfile).filter(ConsultantProfile.user_id == uid).first()
        if not profile:
            return JSONResponse({"success": False, "error": "Profile not found"}, status_code=404)
        profile.bank_account_name   = data.get("bank_account_name",   profile.bank_account_name)
        profile.bank_account_number = data.get("bank_account_number", profile.bank_account_number)
        profile.bank_ifsc           = data.get("bank_ifsc",           profile.bank_ifsc)
        profile.bank_name           = data.get("bank_name",           profile.bank_name)
        profile.upi_id              = data.get("upi_id",              profile.upi_id)
        db.commit()
        return {"success": True}

    @app.post("/api/admin/finance/transactions/{txn_id}/refund")
    async def admin_mark_refund(
        request: Request,
        txn_id: int,
        refund_reason: str = Form(""),
        db: Session = Depends(get_db),
    ):
        _admin_check(request, db)
        from models import PaymentTransaction
        txn = db.query(PaymentTransaction).filter(PaymentTransaction.id == txn_id).first()
        if not txn:
            return JSONResponse({"success": False, "error": "Transaction not found"}, status_code=404)

        if txn.status == "refunded":
            return JSONResponse({"success": False, "error": "This transaction has already been refunded."}, status_code=400)

        if not txn.razorpay_payment_id:
            return JSONResponse({"success": False, "error": "No Razorpay payment ID on record — cannot process refund automatically. Please refund manually via the Razorpay dashboard."}, status_code=400)

        # ── Call Razorpay Refunds API ──────────────────────────────────────────
        try:
            import razorpay as rzp_sdk
            rz_key    = os.environ.get("RAZORPAY_KEY_ID", "")
            rz_secret = os.environ.get("RAZORPAY_KEY_SECRET", "")
            if not rz_key or not rz_secret:
                raise ValueError("Razorpay keys not configured")

            client = rzp_sdk.Client(auth=(rz_key, rz_secret))
            amount_paise = int(txn.amount * 100)   # Razorpay expects paise

            refund_resp = client.payment.refund(
                txn.razorpay_payment_id,
                {
                    "amount": amount_paise,
                    "notes": {
                        "reason":     refund_reason or "Refunded by admin",
                        "txn_id":     str(txn.id),
                        "invoice":    txn.invoice_number or "",
                    },
                },
            )

            rzp_refund_id = refund_resp.get("id", "")
            print(f"[REFUND OK] TxnID={txn.id}  PaymentID={txn.razorpay_payment_id}  RefundID={rzp_refund_id}  Amount=₹{txn.amount}")

        except Exception as exc:
            err_msg = str(exc)
            print(f"[REFUND ERROR] TxnID={txn.id}  Error={err_msg}")
            return JSONResponse(
                {"success": False, "error": f"Razorpay refund failed: {err_msg}"},
                status_code=502,
            )

        # ── Update DB only after Razorpay confirms ─────────────────────────────
        txn.status        = "refunded"
        txn.refunded_at   = datetime.utcnow()
        txn.refund_reason = refund_reason
        db.commit()

        return {"success": True, "invoice_number": txn.invoice_number, "razorpay_refund_id": rzp_refund_id}

    # ══════════════════════════════════════════════════════════════════════════
    # USER — Billing History
    # ══════════════════════════════════════════════════════════════════════════

    @app.get("/app/billing", response_class=HTMLResponse)
    async def user_billing_page(request: Request, db: Session = Depends(get_db)):
        uid = request.session.get("user_id")
        if not uid:
            return HTMLResponse('<script>location="/login"</script>', status_code=302)
        user_name = request.session.get("user_name", "User")
        from main import get_initials, get_nav_items  # noqa: import from main
        return templates.TemplateResponse("pages/user_billing.html", {
            "request": request,
            "page_title": "Billing & Payments — SolaceSquad",
            "user_name": user_name,
            "user_initials": get_initials(user_name),
            "user_type": request.session.get("user_type", "user"),
            "active_page": "billing",
            "nav_items": get_nav_items(request.session.get("user_type", "user")),
        })

    @app.get("/api/user/billing/history")
    async def user_billing_history(request: Request, db: Session = Depends(get_db)):
        uid = request.session.get("user_id")
        if not uid:
            return JSONResponse({"success": False, "error": "Unauthorized"}, status_code=401)
        from models import PaymentTransaction
        txns = (
            db.query(PaymentTransaction)
            .filter(PaymentTransaction.user_id == uid)
            .order_by(desc(PaymentTransaction.created_at))
            .all()
        )
        return {
            "success": True,
            "transactions": [
                {
                    "id":                  t.id,
                    "invoice_number":      t.invoice_number,
                    "transaction_type":    t.transaction_type,
                    "amount":              t.amount,
                    "currency":            t.currency,
                    "status":              t.status,
                    "description":         t.description,
                    "razorpay_payment_id": t.razorpay_payment_id,
                    "created_at":          t.created_at.isoformat() + "Z",
                    "refunded_at":         t.refunded_at.isoformat() + "Z" if t.refunded_at else None,
                }
                for t in txns
            ],
        }

    @app.get("/app/billing/invoice/{txn_id}", response_class=HTMLResponse)
    async def user_invoice_view(request: Request, txn_id: int, db: Session = Depends(get_db)):
        uid = request.session.get("user_id")
        if not uid:
            return HTMLResponse('<script>location="/login"</script>', status_code=302)
        from models import PaymentTransaction, User
        txn = db.query(PaymentTransaction).filter(
            PaymentTransaction.id == txn_id,
            PaymentTransaction.user_id == uid,
        ).first()
        if not txn:
            raise HTTPException(status_code=404, detail="Invoice not found")
        user = db.query(User).filter(User.id == uid).first()
        return templates.TemplateResponse("pages/invoice.html", {
            "request": request,
            "txn": txn,
            "user": user,
            "pdf_mode": False,
            "parent_template": "base.html",
            "page_title": f"Invoice {txn.invoice_number} — SolaceSquad",
        })

    @app.get("/app/billing/invoice/{txn_id}/pdf", response_class=HTMLResponse)
    async def user_invoice_pdf(request: Request, txn_id: int, db: Session = Depends(get_db)):
        uid = request.session.get("user_id")
        if not uid:
            return HTMLResponse('<script>location="/login"</script>', status_code=302)
        from models import PaymentTransaction, User
        txn = db.query(PaymentTransaction).filter(
            PaymentTransaction.id == txn_id,
            PaymentTransaction.user_id == uid,
        ).first()
        if not txn:
            raise HTTPException(status_code=404, detail="Invoice not found")
        user = db.query(User).filter(User.id == uid).first()
        # Returns print-optimised HTML; browser handles PDF conversion
        return templates.TemplateResponse("pages/invoice.html", {
            "request": request,
            "txn": txn,
            "user": user,
            "pdf_mode": True,   # template auto-triggers window.print()
            "parent_template": "layouts/blank_invoice.html",
            "page_title": f"Invoice {txn.invoice_number}",
        })

    # ══════════════════════════════════════════════════════════════════════════
    # CONSULTANT — Earnings
    # ══════════════════════════════════════════════════════════════════════════

    @app.get("/consultant/earnings", response_class=HTMLResponse)
    async def consultant_earnings_page(request: Request, db: Session = Depends(get_db)):
        uid = request.session.get("user_id")
        if not uid or request.session.get("user_type") != "consultant":
            return HTMLResponse('<script>location="/login"</script>', status_code=302)
        user_name = request.session.get("user_name", "Consultant")
        from main import get_initials, get_nav_items  # noqa
        return templates.TemplateResponse("pages/consultant_earnings.html", {
            "request": request,
            "page_title": "My Earnings — SolaceSquad",
            "user_name": user_name,
            "user_initials": get_initials(user_name),
            "user_type": "consultant",
            "active_page": "earnings",
            "nav_items": get_nav_items("consultant"),
        })

    @app.get("/api/consultant/earnings/summary")
    async def consultant_earnings_summary(request: Request, db: Session = Depends(get_db)):
        uid = request.session.get("user_id")
        if not uid or request.session.get("user_type") != "consultant":
            return JSONResponse({"success": False, "error": "Unauthorized"}, status_code=401)
        from models import ConsultantEarning, Appointment, User

        q = (
            db.query(ConsultantEarning, Appointment, User)
            .outerjoin(Appointment, ConsultantEarning.appointment_id == Appointment.id)
            .outerjoin(User,        Appointment.user_id == User.id)
            .filter(ConsultantEarning.consultant_user_id == uid)
        )
        # Scope to current environment
        if not _is_test_mode():
            q = q.filter(ConsultantEarning.is_test == False)
        else:
            q = q.filter(ConsultantEarning.is_test == True)
        rows = q.order_by(desc(ConsultantEarning.created_at)).all()

        total_earned  = sum(e.consultant_payout for e, *_ in rows if e.payout_status == "paid")
        pending       = sum(e.consultant_payout for e, *_ in rows if e.payout_status == "pending")
        processing    = sum(e.consultant_payout for e, *_ in rows if e.payout_status == "processing")
        pending_count = sum(1 for e, *_ in rows if e.payout_status == "pending")
        total_gross   = sum(e.gross_amount for e, *_ in rows)

        return {
            "success": True,
            "summary": {
                "total_earned":      round(total_earned, 2),
                "pending_payout":    round(pending, 2),
                "processing_amount": round(processing, 2),
                "pending_count":     pending_count,
                "total_gross":       round(total_gross, 2),
                "session_count":     len(rows),
            },

            "earnings": [
                {
                    "id":               e.id,
                    "appointment_date": appt.appointment_date.isoformat() if appt else (e.event_workshop.event_date.isoformat() if e.event_workshop else None),
                    "client_name":      client.name if client else (f"Event: {e.event_workshop.title}" if e.event_workshop else "Unknown"),
                    "fee_tag":          "consultation fee" if e.appointment_id else (f"{e.event_workshop.event_mode} {'webinar' if e.event_workshop.type == 'event' else e.event_workshop.type} fee" if e.event_workshop else "financial entry"),
                    "my_payout":        e.consultant_payout,
                    "payout_status":    e.payout_status,
                    "payout_date":      e.payout_date.isoformat() if e.payout_date else None,
                    "payout_reference": e.payout_reference,
                    "created_at":       e.created_at.isoformat(),
                }
                for e, appt, client in rows
            ],
        }

    @app.post("/api/consultant/earnings/request-payout")
    async def consultant_request_payout(request: Request, db: Session = Depends(get_db)):
        """Consultant self-service payout request � marks pending earnings as 'processing'."""
        uid = request.session.get("user_id")
        if not uid or request.session.get("user_type") != "consultant":
            return JSONResponse({"success": False, "error": "Unauthorized"}, status_code=401)

        from models import ConsultantEarning, User
        from sqlalchemy import and_

        filters = [
            ConsultantEarning.consultant_user_id == uid,
            ConsultantEarning.payout_status == "pending",
            ConsultantEarning.is_test == _is_test_mode(),  # scope to current environment
        ]

        pending_rows = (
            db.query(ConsultantEarning)
            .filter(and_(*filters))
            .all()
        )

        if not pending_rows:
            return JSONResponse({"success": False, "error": "No pending earnings to request payout for."}, status_code=400)

        total_amount = round(sum(e.consultant_payout for e in pending_rows), 2)
        ref = f"REQ-{uid}-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"

        for e in pending_rows:
            e.payout_status    = "processing"
            e.payout_reference = ref
        db.commit()

        consultant = db.query(User).filter(User.id == uid).first()
        print(f"[PAYOUT REQUEST] {consultant.name if consultant else uid} requested payout Rs.{total_amount} for {len(pending_rows)} sessions. Ref: {ref}")

        return JSONResponse({
            "success":       True,
            "total_amount":  total_amount,
            "session_count": len(pending_rows),
            "reference":     ref,
            "message":       f"Payout request of Rs.{total_amount:,.2f} for {len(pending_rows)} session(s) submitted. The SolaceSquad team will process it within 3-5 business days.",
        })
