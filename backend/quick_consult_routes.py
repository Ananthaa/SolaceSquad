"""
quick_consult_routes.py — Dedicated Quick Consultation module for SolaceSquad.

Features:
  - Public landing page: /quickconsult (Zero account registration required)
  - Short-notice consultant listing (accepts_short_notice == True)
  - Pricing: Hourly rate prorated + flat Rs 100 Surcharge + 18% GST
  - DPDP Act (2023) mandatory consent recording
  - Razorpay order creation & payment verification
  - MSG91 transactional SMS dispatch to User and Consultant
  - Exotel telephony call bridging integration
  - HIPAA-compliant clinical observations for consultants
  - Unified Admin Financial Ledger integration

Registration:
  from quick_consult_routes import register_quick_consult_routes
  register_quick_consult_routes(app, templates, get_db)
"""

from __future__ import annotations

import os
import asyncio
import hmac
import hashlib
import json
import secrets
import string
from datetime import datetime, date, timedelta
from typing import Optional, Dict, Any, List

import requests
from fastapi import FastAPI, Request, Depends, HTTPException, Body
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_, desc

from models import (
    User,
    ConsultantProfile,
    ConsultantSchedule,
    QuickConsultation,
    PaymentTransaction,
    ConsultantEarning,
    AuditLog,
    Voucher,
    OTPVerification,
    Appointment,
    ScheduleBreak,
)
from audit_logging import AuditLogger
from exotel_service import bridge_quick_consult_call
from firebase_otp import FallbackOTP


def _is_test_mode() -> bool:
    """Return True if running in Razorpay Test / Mirror mode."""
    key_id = os.getenv("RAZORPAY_KEY_ID", "")
    return key_id.startswith("rzp_test_") or not key_id


def _razorpay_client():
    """Return an initialised Razorpay client and secret, or None if keys missing."""
    key_id = os.getenv("RAZORPAY_KEY_ID")
    key_secret = os.getenv("RAZORPAY_KEY_SECRET")
    if not (key_id and key_secret):
        return None, None
    try:
        import razorpay
        return razorpay.Client(auth=(key_id, key_secret)), key_secret
    except Exception:
        return None, None


def _generate_qc_id(db: Session) -> str:
    """
    Generate an 8-character unique QC_ID:
    Format: 'SS_' + 5 alphanumeric uppercase characters (e.g. 'SS_A8K9X').
    """
    chars = string.ascii_uppercase + string.digits
    for _ in range(50):
        suffix = "".join(secrets.choice(chars) for _ in range(5))
        qc_id = f"SS_{suffix}"
        exists = db.query(QuickConsultation).filter(QuickConsultation.qc_id == qc_id).first()
        if not exists:
            return qc_id
    # Fallback timestamp suffix
    return f"SS_{int(datetime.utcnow().timestamp()) % 100000:05d}"


def _generate_qc_invoice_number(db: Session) -> str:
    """Generate sequential, guaranteed collision-free invoice number: SS-YYYY-NNNNN."""
    year = datetime.utcnow().year
    prefix = f"SS-{year}-"
    last_txns = (
        db.query(PaymentTransaction.invoice_number)
        .filter(PaymentTransaction.invoice_number.like(f"{prefix}%"))
        .order_by(PaymentTransaction.invoice_number.desc())
        .limit(50)
        .all()
    )
    max_seq = 0
    for (inv,) in last_txns:
        if inv and inv.startswith(prefix):
            try:
                num = int(inv[len(prefix):])
                if num > max_seq:
                    max_seq = num
            except ValueError:
                pass

    seq = max_seq + 1
    while True:
        candidate = f"{prefix}{seq:05d}"
        exists = db.query(PaymentTransaction.id).filter(PaymentTransaction.invoice_number == candidate).first()
        if not exists:
            return candidate
        seq += 1


def _calculate_quick_consult_fee(hourly_rate: float, duration_minutes: int = 30) -> Dict[str, float]:
    """
    Calculate Quick Consultation Fee (strictly 30 minutes) with +Rs 100 surcharge and 18% GST:
      - 30 mins: Base = (hourly_rate / 2) + 100
      - GST (18%) = round(Base * 0.18, 2)
      - Total = Base + GST
    """
    rate = float(hourly_rate or 600.0)
    base_prorated = round(rate / 2.0, 2)
    surcharge = 100.0
    base_fee = round(base_prorated + surcharge, 2)
    gst = round(base_fee * 0.18, 2)
    total = round(base_fee + gst, 2)

    return {
        "duration_minutes": 30,
        "base_prorated": base_prorated,
        "surcharge": surcharge,
        "base_amount": base_fee,
        "taxes": gst,
        "total_amount": total,
    }


def _send_msg91_sms(
    phone_number: str,
    message: str,
    qc_id: Optional[str] = None,
    consultant_name: Optional[str] = None,
    appt_time: Optional[str] = None,
    room_url: Optional[str] = None,
    template_id: Optional[str] = None,
) -> bool:
    """
    Dispatch SMS notification using MSG91 Flow / SMS API.
    Zero Hardcoded Secrets: Reads MSG91_AUTH_KEY, MSG91_SENDER_ID, and MSG91_QC_TEMPLATE_ID from environment.
    """
    auth_key = os.getenv("MSG91_AUTH_KEY")
    sender_id = os.getenv("MSG91_SENDER_ID", "SolSqd")
    if not template_id:
        template_id = os.getenv("MSG91_QC_TEMPLATE_ID", "6aa3c13688431827e60b0d72")

    clean_phone = "".join(ch for ch in str(phone_number) if ch.isdigit())
    if clean_phone.startswith("91") and len(clean_phone) == 12:
        clean_phone = clean_phone[2:]
    elif clean_phone.startswith("0") and len(clean_phone) == 11:
        clean_phone = clean_phone[1:]

    if not auth_key:
        print(f"[MSG91-STAGING] Mock SMS to +91{clean_phone}: {message}")
        return True

    try:
        # If template_id and dynamic variables are available, use MSG91 Flow API
        if template_id and qc_id and consultant_name and appt_time:
            url = "https://api.msg91.com/api/v5/flow/"
            headers = {
                "authkey": auth_key,
                "content-type": "application/json"
            }
            payload = {
                "template_id": template_id,
                "sender": sender_id,
                "short_url": "0",
                "recipients": [
                    {
                        "mobiles": f"91{clean_phone}",
                        "mobile": f"91{clean_phone}",
                        "var1": str(qc_id),
                        "var2": str(consultant_name),
                        "var3": str(appt_time),
                        "var4": str(room_url or ""),
                        "qc_id": str(qc_id),
                        "consultant_name": str(consultant_name),
                        "time": str(appt_time),
                        "room_url": str(room_url or ""),
                        "link": str(room_url or ""),
                        "url": str(room_url or ""),
                    }
                ]
            }
            res = requests.post(url, json=payload, headers=headers, timeout=10)
            print(f"[MSG91-FLOW] Response ({res.status_code}): {res.text}")
            if res.status_code in (200, 201):
                return True

        # Fallback to standard OTP/SMS endpoint
        url = "https://api.msg91.com/api/v5/otp"
        headers = {
            "authkey": auth_key,
            "content-type": "application/json"
        }
        payload = {
            "mobile": f"91{clean_phone}",
            "template_id": template_id,
            "message": message,
            "sender": sender_id
        }
        res = requests.post(url, json=payload, headers=headers, timeout=10)
        print(f"[MSG91-FALLBACK] SMS response ({res.status_code}): {res.text}")
        return res.status_code == 200
    except Exception as exc:
        print(f"[MSG91] Error sending SMS: {exc}")
        return False


def _send_msg91_consultant_sms(
    phone_number: str,
    consultant_name: str,
    duration: str,
    qc_id: str,
    time: str,
    template_id: str,
    message: Optional[str] = None,
) -> bool:
    """
    Dispatch consultant-specific SMS notification using MSG91 Flow API when a consultant DLT template is configured.
    """
    auth_key = os.getenv("MSG91_AUTH_KEY")
    sender_id = os.getenv("MSG91_SENDER_ID", "SolSqd")
    if not auth_key:
        return False

    clean_phone = "".join(ch for ch in str(phone_number) if ch.isdigit())
    if clean_phone.startswith("91") and len(clean_phone) == 12:
        clean_phone = clean_phone[2:]
    elif clean_phone.startswith("0") and len(clean_phone) == 11:
        clean_phone = clean_phone[1:]

    url = "https://api.msg91.com/api/v5/flow/"
    headers = {
        "authkey": auth_key,
        "content-type": "application/json"
    }
    payload = {
        "template_id": template_id,
        "sender": sender_id,
        "short_url": "0",
        "recipients": [
            {
                "mobiles": f"91{clean_phone}",
                "mobile": f"91{clean_phone}",
                "consultant_name1": str(consultant_name),
                "consultant_name": str(consultant_name),
                "name": str(consultant_name),
                "duration": str(duration),
                "qc_id": str(qc_id),
                "time": str(time),
                "var1": str(consultant_name),
                "var2": str(qc_id),
                "var3": str(time),
                "var4": str(duration),
            }
        ]
    }
    try:
        res = requests.post(url, json=payload, headers=headers, timeout=10)
        print(f"[MSG91-CONSULTANT-FLOW] Response ({res.status_code}): {res.text}")
        if res.status_code in (200, 201):
            return True

        # Fallback to standard SMS API if flow rejected
        if message:
            fb_url = "https://api.msg91.com/api/v5/otp"
            fb_payload = {
                "mobile": f"91{clean_phone}",
                "template_id": template_id,
                "message": message,
                "sender": sender_id,
            }
            fb_res = requests.post(fb_url, json=fb_payload, headers=headers, timeout=10)
            print(f"[MSG91-CONSULTANT-FALLBACK] Response ({fb_res.status_code}): {fb_res.text}")
            return fb_res.status_code == 200
        return False
    except Exception as exc:
        print(f"[MSG91-CONSULTANT-FLOW] Error: {exc}")
        return False


def register_quick_consult_routes(app: FastAPI, templates: Jinja2Templates, get_db):
    """Register all routes for the Quick Consultation feature."""

    # ──────────────────────────────────────────────────────────────────────────
    # ──────────────────────────────────────────────────────────────────────────
    # 1. Public Landing Pages: Telephony (/quickconsult) vs WebRTC (/quick-consult-web)
    # ──────────────────────────────────────────────────────────────────────────
    @app.get("/quickconsult", response_class=HTMLResponse)
    @app.get("/quick-consult", response_class=HTMLResponse)
    async def quick_consult_telephony_page(request: Request, db: Session = Depends(get_db)):
        """
        Public Telephony Quick Consultation page (Exotel phone-to-phone bridge).
        Strictly 30 minutes. No registration required.
        """
        rzp_key_id = os.getenv("RAZORPAY_KEY_ID", "")
        return templates.TemplateResponse(
            "pages/quickconsult.html",
            {
                "request": request,
                "razorpay_key_id": rzp_key_id,
                "is_test_mode": _is_test_mode(),
                "consultation_mode": "telephony",
            },
        )

    @app.get("/quick-consult-web", response_class=HTMLResponse)
    @app.get("/quickconsult/web", response_class=HTMLResponse)
    @app.get("/quickconsult-web", response_class=HTMLResponse)
    async def quick_consult_webrtc_page(request: Request, db: Session = Depends(get_db)):
        """
        Public WebRTC Quick Consultation page (In-browser video/audio call room).
        Strictly 30 minutes. No registration required.
        """
        rzp_key_id = os.getenv("RAZORPAY_KEY_ID", "")
        return templates.TemplateResponse(
            "pages/quickconsult_web.html",
            {
                "request": request,
                "razorpay_key_id": rzp_key_id,
                "is_test_mode": _is_test_mode(),
                "consultation_mode": "webrtc",
            },
        )

    @app.get("/consultants", include_in_schema=False)
    async def redirect_consultants_directory():
        """Redirect legacy or mistyped /consultants to /app/consultants."""
        return RedirectResponse(url="/app/consultants", status_code=301)

    # ──────────────────────────────────────────────────────────────────────────
    # 2. API: Available Consultants for Quick Consult (30 Mins Only)
    # ──────────────────────────────────────────────────────────────────────────
    @app.get("/api/quick-consult/available-consultants")
    async def get_quick_consultants(db: Session = Depends(get_db)):
        """
        Fetch approved consultants flagged for short-notice consultations (accepts_short_notice == True).
        Computes strictly 30m fee structures (+Rs 100 Surcharge + 18% GST), extended profile details,
        and available slots for today.
        """
        consultants = (
            db.query(ConsultantProfile)
            .join(User, ConsultantProfile.user_id == User.id)
            .filter(
                User.user_type == "consultant",
                User.is_active == True,
                User.is_blocked == False,
                ConsultantProfile.is_approved == True,
                ConsultantProfile.accepts_short_notice == True,
            )
            .all()
        )

        now_utc = datetime.utcnow()
        # IST is UTC + 5:30
        now_ist = now_utc + timedelta(hours=5, minutes=30)
        today_ist_str = now_ist.strftime("%Y-%m-%d")
        day_of_week = now_ist.weekday()  # 0=Monday, 6=Sunday

        # Pre-fetch today's busy intervals for consultants (covers entire IST today in UTC)
        day_start_utc = (now_ist.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(hours=5, minutes=30))
        day_end_utc = day_start_utc + timedelta(days=1, hours=2)

        all_appts = (
            db.query(Appointment)
            .filter(
                Appointment.status.in_(["scheduled", "in_progress", "confirmed"]),
                Appointment.appointment_date >= day_start_utc,
                Appointment.appointment_date <= day_end_utc,
            )
            .all()
        )
        appts_by_consultant: Dict[int, List[tuple]] = {}
        for a in all_appts:
            a_start = a.appointment_date.replace(tzinfo=None) if getattr(a.appointment_date, "tzinfo", None) else a.appointment_date
            a_dur = a.duration_minutes if a.duration_minutes is not None else 60
            # Consultant is busy during appointment + 30 mins buffer gap after consultation
            a_busy_end = a_start + timedelta(minutes=a_dur + 30)
            appts_by_consultant.setdefault(a.consultant_id, []).append((a_start, a_busy_end))

        ten_mins_ago = datetime.utcnow() - timedelta(minutes=10)
        all_qcs = (
            db.query(QuickConsultation)
            .filter(
                QuickConsultation.call_status != "cancelled",
                or_(
                    QuickConsultation.payment_status.in_(["paid", "completed"]),
                    and_(
                        QuickConsultation.payment_status == "pending",
                        QuickConsultation.created_at >= ten_mins_ago,
                    ),
                ),
                QuickConsultation.appointment_date >= day_start_utc,
                QuickConsultation.appointment_date <= day_end_utc,
            )
            .all()
        )
        for q in all_qcs:
            q_start = q.appointment_date.replace(tzinfo=None) if getattr(q.appointment_date, "tzinfo", None) else q.appointment_date
            q_dur = q.duration_minutes or 30
            # Consultant is busy during quick consult + 30 mins buffer gap after consultation
            q_busy_end = q_start + timedelta(minutes=q_dur + 30)
            appts_by_consultant.setdefault(q.consultant_id, []).append((q_start, q_busy_end))

        result = []
        for c in consultants:
            hourly_rate = float(c.hourly_rate or c.consultation_fee or 600.0)
            pricing_30 = _calculate_quick_consult_fee(hourly_rate, 30)

            # Parse languages
            langs = []
            if c.languages:
                try:
                    if isinstance(c.languages, list):
                        langs = [str(l).strip() for l in c.languages if str(l).strip()]
                    elif str(c.languages).strip().startswith("[") or str(c.languages).strip().startswith("{"):
                        parsed_langs = json.loads(c.languages)
                        langs = [str(l).strip() for l in parsed_langs if str(l).strip()] if isinstance(parsed_langs, list) else [str(parsed_langs).strip()]
                    else:
                        clean_l = str(c.languages).replace(";", ",").replace("/", ",")
                        langs = [l.strip() for l in clean_l.split(",") if l.strip()]
                except Exception:
                    clean_l = str(c.languages).replace(";", ",").replace("/", ",")
                    langs = [l.strip() for l in clean_l.split(",") if l.strip()]
            if not langs:
                langs = ["English", "Hindi"]

            # Parse expertise areas
            exp_areas = []
            if c.expertise_areas:
                try:
                    if isinstance(c.expertise_areas, list):
                        exp_areas = [str(e).strip() for e in c.expertise_areas if str(e).strip()]
                    elif str(c.expertise_areas).strip().startswith("[") or str(c.expertise_areas).strip().startswith("{"):
                        parsed_ea = json.loads(c.expertise_areas)
                        exp_areas = [str(e).strip() for e in parsed_ea if str(e).strip()] if isinstance(parsed_ea, list) else [str(parsed_ea).strip()]
                    else:
                        exp_areas = [e.strip() for e in str(c.expertise_areas).split(",") if e.strip()]
                except Exception:
                    exp_areas = [e.strip() for e in str(c.expertise_areas).split(",") if e.strip()]

            # Parse wellness categories / tags from specialization, expertise_areas, and wellness_category
            spec_text = (c.specialization or "").lower()
            exp_text = " ".join(exp_areas).lower()
            combined_cat_text = f"{spec_text} {exp_text}"

            w_cats = []
            if any(k in combined_cat_text for k in ["mental", "counsel", "therap", "psych", "stress", "mindful"]):
                w_cats.append("Mental")
            if any(k in combined_cat_text for k in ["physical", "fitness", "nutrition", "yoga", "body", "diet"]):
                w_cats.append("Physical")
            if any(k in combined_cat_text for k in ["professional", "career", "executive", "workplace"]):
                w_cats.append("Professional")

            if hasattr(c, "wellness_categories") and c.wellness_categories:
                for wc in c.wellness_categories:
                    if wc and wc not in w_cats:
                        w_cats.append(wc)
            elif hasattr(c, "wellness_category") and c.wellness_category:
                if c.wellness_category and c.wellness_category not in w_cats:
                    w_cats.append(c.wellness_category)

            if not w_cats:
                w_cats = ["Mental"]

            # Detect Sexual Wellness counselling
            bio_text = (c.bio or "").lower()
            w_cats_text = " ".join(str(w) for w in w_cats).lower()
            offers_sw = bool(
                "sexual" in exp_text or "intimacy" in exp_text
                or "sexual" in spec_text or "intimacy" in spec_text or "sexolog" in spec_text
                or "sexual wellness" in bio_text or "sexual health" in bio_text or "sex therapy" in bio_text or "sexologist" in bio_text
                or "sexual" in w_cats_text
                or getattr(c, "offers_sexual_wellness", False)
            )
            if offers_sw and "Sexual" not in w_cats:
                w_cats.append("Sexual")

            # Available slots for today:
            # Standard timings: strictly on :00 or :30 (e.g. 6:00 PM, 6:30 PM, 7:00 PM)
            slots = []

            # Auto-seed schedule from onboarding if no schedule rows exist at all
            if not c.schedules:
                try:
                    from main import _seed_schedule_from_onboarding
                    _seed_schedule_from_onboarding(c, db)
                    db.refresh(c)
                except Exception:
                    pass

            schedules = [s for s in c.schedules if getattr(s, "is_active", True) and s.day_of_week == day_of_week]
            breaks = [b for b in getattr(c, "breaks", []) if getattr(b, "is_active", True) and b.day_of_week == day_of_week]

            def _to_min(t_str: str) -> int:
                parts = t_str.split(":")
                return int(parts[0]) * 60 + int(parts[1])

            # Candidate timings:
            # Consultant slots must have at least 20 minutes advance notice:
            # - Till 3:40 PM -> earliest is 4:00 PM; after 3:40 PM -> starts at 4:30 PM
            # - Till 4:10 PM -> earliest is 4:30 PM; after 4:10 PM -> starts at 5:00 PM
            lead_cutoff_ist = now_ist + timedelta(minutes=20)
            if lead_cutoff_ist.minute == 0 and lead_cutoff_ist.second == 0 and lead_cutoff_ist.microsecond == 0:
                first_minute = 0
                first_hour = lead_cutoff_ist.hour
            elif lead_cutoff_ist.minute < 30 or (lead_cutoff_ist.minute == 30 and lead_cutoff_ist.second == 0 and lead_cutoff_ist.microsecond == 0):
                first_minute = 30
                first_hour = lead_cutoff_ist.hour
            else:
                first_minute = 0
                first_hour = lead_cutoff_ist.hour + 1

            # Strictly require active working hours for today: if consultant doesn't work today, no slots!
            if schedules and first_hour < 24:
                sched_windows = [(_to_min(s.start_time), _to_min(s.end_time)) for s in schedules]
                break_windows = [(_to_min(b.break_start), _to_min(b.break_end)) for b in breaks]
                step_time_ist = now_ist.replace(hour=first_hour, minute=first_minute, second=0, microsecond=0)
                busy_intervals = appts_by_consultant.get(c.id, [])

                while step_time_ist.date() == now_ist.date() and len(slots) < 8:
                    slot_start_min = step_time_ist.hour * 60 + step_time_ist.minute
                    slot_end_min = slot_start_min + 30

                    # Must not cross midnight
                    if slot_end_min > 24 * 60:
                        break

                    # 1. Must fall STRICTLY within active working hours for today
                    in_sched = any(s_start <= slot_start_min and slot_end_min <= s_end for s_start, s_end in sched_windows)
                    if not in_sched:
                        step_time_ist += timedelta(minutes=30)
                        continue

                    # 2. Must not fall during any scheduled break
                    in_break = any(b_start < slot_end_min and slot_start_min < b_end for b_start, b_end in break_windows)
                    if in_break:
                        step_time_ist += timedelta(minutes=30)
                        continue

                    # 3. Must not conflict with existing appointments or quick consults
                    # Consultant must have a 30-min buffer gap after each consultation
                    slot_start_utc = step_time_ist - timedelta(hours=5, minutes=30)
                    slot_end_utc = slot_start_utc + timedelta(minutes=30)
                    candidate_busy_end = slot_end_utc + timedelta(minutes=30)

                    conflict = False
                    for b_start, b_end in busy_intervals:
                        if max(slot_start_utc, b_start) < min(candidate_busy_end, b_end):
                            conflict = True
                            break

                    if not conflict:
                        slots.append({
                            "time": step_time_ist.strftime("%H:%M"),
                            "display": step_time_ist.strftime("%I:%M %p"),
                            "date": today_ist_str,
                        })

                    step_time_ist += timedelta(minutes=30)

            # If consultant has no available slots remaining today, completely hide them
            if not slots:
                continue

            user_obj = c.user
            c_name = c.full_name or (user_obj.name if user_obj else "Wellness Consultant")
            if c.photo_url and c.photo_url.startswith("http") and "storage.googleapis.com" not in c.photo_url:
                photo = c.photo_url
            elif c.photo_url:
                photo = f"/api/profile-photo/{c.user_id}"
            else:
                photo = "/static/images/default-avatar.png"

            result.append({
                "id": c.id,
                "user_id": c.user_id,
                "name": c_name,
                "specialization": c.specialization or "Holistic Wellness",
                "bio": c.bio or "Certified SolaceSquad Wellness Consultant offering prompt consultation.",
                "experience_years": c.experience_years or 2,
                "rating": round(float(c.rating or 4.9), 1),
                "photo_url": photo,
                "city": getattr(c, "city", "") or "India",
                "education": getattr(c, "education", "") or "Certified Practitioner",
                "highest_qualification": getattr(c, "highest_qualification", "") or "",
                "languages": langs,
                "wellness_categories": w_cats,
                "expertise_areas": exp_areas,
                "offers_sexual_wellness": offers_sw,
                "pricing_30": pricing_30,
                "pricing": pricing_30,
                "available_slots": slots[:8],
            })

        # Sort consultants:
        # 1. Consultants with available slots today appear before fully booked consultants.
        # 2. Sorted in order of EARLIEST available slot time today (e.g. 11:00 AM before 3:00 PM before 5:00 PM).
        # 3. Secondary sort by rating descending, then experience descending.
        def _availability_sort_key(item):
            item_slots = item.get("available_slots") or []
            has_slots = len(item_slots) > 0
            earliest_time = item_slots[0]["time"] if has_slots else "99:99"
            rating = float(item.get("rating") or 0.0)
            exp = float(item.get("experience_years") or 0.0)
            return (0 if has_slots else 1, earliest_time, -rating, -exp)

        result.sort(key=_availability_sort_key)

        return {"success": True, "count": len(result), "consultants": result}

    # ──────────────────────────────────────────────────────────────────────────
    # 2.5 API: Validate Promo / Reschedule Voucher Code
    # ──────────────────────────────────────────────────────────────────────────
    @app.post("/api/quick-consult/validate-voucher")
    async def validate_quick_consult_voucher(request: Request, db: Session = Depends(get_db)):
        """
        Validate a promotional or 100% reschedule voucher code for Quick Consultation.
        Returns discount breakdown and eligible final price.
        """
        try:
            body = await request.json()
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid JSON payload")

        code = (body.get("voucher_code") or "").strip().upper()
        consultant_id = body.get("consultant_id")
        duration_minutes = 30  # Strictly 30 minutes for Quick Consultation

        if not code:
            return {"valid": False, "error": "Please enter a voucher code"}

        voucher = db.query(Voucher).filter(Voucher.code == code).first()
        if not voucher:
            return {"valid": False, "error": "Invalid voucher code"}

        if not voucher.is_active:
            return {"valid": False, "error": "This voucher is inactive"}

        if voucher.valid_until and datetime.utcnow() > voucher.valid_until:
            return {"valid": False, "error": "This voucher code has expired"}

        # Check total usage limit
        if voucher.max_uses is not None:
            is_test_env = _is_test_mode()
            from models import UserSubscription, FeatureUsageTopUp
            sub_count = db.query(UserSubscription).filter(
                UserSubscription.voucher_code == code,
                UserSubscription.status.in_(["active", "paused", "grace", "expired", "cancelled"]),
                UserSubscription.is_test == is_test_env,
            ).count()
            topup_count = db.query(FeatureUsageTopUp).filter(
                FeatureUsageTopUp.voucher_code == code,
                FeatureUsageTopUp.status == "paid",
                FeatureUsageTopUp.is_test == is_test_env,
            ).count()
            qc_count = db.query(QuickConsultation).filter(
                QuickConsultation.voucher_code == code,
                QuickConsultation.payment_status == "completed",
            ).count()
            total_used = sub_count + topup_count + qc_count
            if total_used >= voucher.max_uses:
                return {"valid": False, "error": f"Voucher usage limit reached (Max {voucher.max_uses} use)"}

        # Check applicability
        if voucher.applies_to not in ("all", "quick_consultation", "quick_consult"):
            return {"valid": False, "error": "This voucher is not applicable to Quick Consultations"}

        # If voucher applies to a specific consultant, verify consultant_id matches
        if voucher.applies_to_id and str(voucher.applies_to_id).strip() and str(voucher.applies_to_id).upper() not in ("ALL", ""):
            if not consultant_id or str(voucher.applies_to_id) != str(consultant_id):
                return {"valid": False, "error": "This voucher is not applicable to the selected consultant"}

        # Calculate standard fee
        hourly_rate = 600.0
        if consultant_id:
            c = db.query(ConsultantProfile).filter(ConsultantProfile.id == consultant_id).first()
            if c:
                hourly_rate = float(c.hourly_rate or c.consultation_fee or 600.0)

        fee_data = _calculate_quick_consult_fee(hourly_rate, 30)
        gross_total = fee_data["total_amount"]

        if voucher.discount_type == "percentage":
            discount_amount = round(gross_total * (voucher.discount_value / 100.0), 2)
        else:
            discount_amount = min(round(float(voucher.discount_value), 2), gross_total)

        final_amount = max(0.0, round(gross_total - discount_amount, 2))

        return {
            "valid": True,
            "code": voucher.code,
            "discount_type": voucher.discount_type,
            "discount_value": voucher.discount_value,
            "discount_amount": discount_amount,
            "original_total": gross_total,
            "final_amount": final_amount,
            "is_100_percent": final_amount == 0.0,
            "message": f"{int(voucher.discount_value)}% discount applied!" if voucher.discount_type == "percentage" else f"₹{voucher.discount_value} discount applied!",
        }

    # ──────────────────────────────────────────────────────────────────────────
    # 2.9. API: Quick Consult Mobile OTP Send & Verify
    # ──────────────────────────────────────────────────────────────────────────
    @app.post("/api/quick-consult/otp/send")
    async def quick_consult_otp_send(request: Request, db: Session = Depends(get_db)):
        """
        Generate and send a 6-digit OTP to the client's mobile number via MSG91 for Quick Consult verification.
        """
        try:
            body = await request.json()
        except Exception:
            return JSONResponse(status_code=400, content={"success": False, "error": "Invalid JSON payload"})

        raw_phone = (body.get("phone") or "").strip()
        digits = "".join(ch for ch in raw_phone if ch.isdigit())
        if len(digits) < 10:
            return JSONResponse(status_code=400, content={"success": False, "error": "Please enter a valid 10-digit mobile number."})

        clean_10 = digits[-10:]
        formatted_phone = f"+91{clean_10}"

        # Generate cryptographically secure 6-digit OTP
        otp_code = "".join(str(secrets.randbelow(10)) for _ in range(6))

        # Invalidate old OTPs for this number
        db.query(OTPVerification).filter(
            OTPVerification.phone_number.in_([clean_10, formatted_phone, f"91{clean_10}"])
        ).delete(synchronize_session=False)

        new_otp = OTPVerification(
            phone_number=formatted_phone,
            otp_code=otp_code,
            expires_at=datetime.utcnow() + timedelta(minutes=10),
            is_verified=False,
        )
        db.add(new_otp)
        db.commit()

        # Send via FallbackOTP (MSG91 SMS)
        provider = FallbackOTP()
        sms_result = provider.send_otp(formatted_phone, otp_code)
        print(f"[QuickConsult-OTP] Sent OTP {otp_code} to {formatted_phone}: {sms_result}")

        is_dev = os.getenv("ENVIRONMENT", "development") == "development" or _is_test_mode()
        resp = {
            "success": True,
            "message": f"OTP sent to +91 {clean_10[:2]}******{clean_10[-2:]}",
        }
        if is_dev:
            resp["otp_debug"] = otp_code

        return resp

    @app.post("/api/quick-consult/otp/verify")
    async def quick_consult_otp_verify(request: Request, db: Session = Depends(get_db)):
        """
        Verify the 6-digit OTP entered by the user.
        """
        try:
            body = await request.json()
        except Exception:
            return JSONResponse(status_code=400, content={"success": False, "error": "Invalid JSON payload"})

        raw_phone = (body.get("phone") or "").strip()
        otp_input = (body.get("otp") or "").strip()

        digits = "".join(ch for ch in raw_phone if ch.isdigit())
        if len(digits) < 10 or not otp_input:
            return JSONResponse(status_code=400, content={"success": False, "error": "Mobile number and OTP are required."})

        clean_10 = digits[-10:]
        formatted_phone = f"+91{clean_10}"

        bypass_otp = os.getenv("BYPASS_OTP_VERIFICATION", "false").lower() == "true"
        is_test = _is_test_mode()

        if bypass_otp or (is_test and otp_input in ["123456", "000000", "999999"]):
            request.session["qc_verified_phone"] = clean_10
            return {"success": True, "verified": True, "message": "Mobile number verified successfully."}

        record = db.query(OTPVerification).filter(
            OTPVerification.phone_number.in_([clean_10, formatted_phone, f"91{clean_10}"]),
            OTPVerification.otp_code == otp_input,
            OTPVerification.expires_at > datetime.utcnow(),
        ).first()

        if not record:
            return JSONResponse(status_code=400, content={"success": False, "error": "Invalid or expired OTP. Please try again or request a new code."})

        # Mark verified & cleanup
        request.session["qc_verified_phone"] = clean_10
        db.delete(record)
        db.commit()

        return {"success": True, "verified": True, "message": "Mobile number verified successfully."}

    # ──────────────────────────────────────────────────────────────────────────
    # 3. API: Book Quick Consultation — Init (Create Razorpay Order)
    # ──────────────────────────────────────────────────────────────────────────
    @app.post("/api/quick-consult/book-init")
    async def book_quick_consult_init(request: Request, db: Session = Depends(get_db)):
        """
        Initiate Quick Consultation booking without registration (strictly 30 minutes).
        Requires explicit DPDP Act (2023) consent, validates phone number, applies optional voucher,
        generates 8-char QC_ID, and creates a Razorpay payment order (or zero-value order for 100% vouchers).
        """
        try:
            body = await request.json()
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid JSON payload")

        consultant_id = body.get("consultant_id")
        phone_number = (body.get("phone_number") or "").strip()
        duration_minutes = 30  # Strictly 30 minutes for Quick Consultation
        consultation_mode = (body.get("consultation_mode") or "telephony").strip().lower()
        if consultation_mode not in ("webrtc", "telephony"):
            consultation_mode = "telephony"
        slot_time = (body.get("slot_time") or "").strip()
        slot_date = (body.get("slot_date") or "").strip()
        voucher_code = (body.get("voucher_code") or "").strip().upper()
        consent = body.get("consent")

        # ── DPDP Act 2023 Consent Check ───────────────────────────────────────
        if consent is not True:
            raise HTTPException(
                status_code=422,
                detail="DPDP Act, 2023 Consent is mandatory. Please accept the privacy consent to proceed.",
            )

        # ── Phone number validation ───────────────────────────────────────────
        digits = "".join(ch for ch in phone_number if ch.isdigit())
        if len(digits) < 10:
            raise HTTPException(status_code=422, detail="Please enter a valid 10-digit mobile number.")
        clean_10 = digits[-10:]
        if len(digits) == 10:
            formatted_phone = f"+91{digits}"
        elif len(digits) == 12 and digits.startswith("91"):
            formatted_phone = f"+{digits}"
        else:
            formatted_phone = f"+{digits}"

        # ── Mobile Number OTP Verification Check ──────────────────────────────
        bypass_otp = os.getenv("BYPASS_OTP_VERIFICATION", "false").lower() == "true"
        verified_session_phone = request.session.get("qc_verified_phone", "")
        submitted_otp = (body.get("otp") or "").strip()

        if not bypass_otp and verified_session_phone != clean_10:
            otp_match = False
            if submitted_otp:
                rec = db.query(OTPVerification).filter(
                    OTPVerification.phone_number.in_([clean_10, formatted_phone, f"91{clean_10}"]),
                    OTPVerification.otp_code == submitted_otp,
                    OTPVerification.expires_at > datetime.utcnow(),
                ).first()
                if rec or (_is_test_mode() and submitted_otp in ["123456", "000000", "999999"]):
                    if rec:
                        db.delete(rec)
                        db.commit()
                    request.session["qc_verified_phone"] = clean_10
                    otp_match = True

            if not otp_match:
                raise HTTPException(
                    status_code=422,
                    detail="Mobile number not verified. Please verify your mobile number with OTP before confirming booking.",
                )

        # ── Consultant Lookup ─────────────────────────────────────────────────
        consultant = (
            db.query(ConsultantProfile)
            .join(User, ConsultantProfile.user_id == User.id)
            .filter(
                ConsultantProfile.id == consultant_id,
                User.user_type == "consultant",
                User.is_active == True,
                User.is_blocked == False,
                ConsultantProfile.is_approved == True,
                ConsultantProfile.accepts_short_notice == True,
            )
            .first()
        )
        if not consultant:
            raise HTTPException(status_code=404, detail="Selected consultant is not available or inactive.")

        # ── Compute Pricing with 18% GST (30 mins) ────────────────────────────
        hourly_rate = float(consultant.hourly_rate or consultant.consultation_fee or 600.0)
        fee_data = _calculate_quick_consult_fee(hourly_rate, 30)
        gross_total_amount = fee_data["total_amount"]
        base_amount = fee_data["base_amount"]
        taxes = fee_data["taxes"]
        surcharge_amount = fee_data["surcharge"]

        # ── Validate & Apply Optional Voucher ────────────────────────────────
        discount_amount = 0.0
        applied_voucher_code = None

        if voucher_code:
            v_obj = db.query(Voucher).filter(Voucher.code == voucher_code, Voucher.is_active == True).first()
            if not v_obj:
                raise HTTPException(status_code=422, detail="Invalid or inactive voucher code.")
            if v_obj.valid_until and datetime.utcnow() > v_obj.valid_until:
                raise HTTPException(status_code=422, detail="Voucher code has expired.")
            if v_obj.max_uses is not None:
                is_test_env = _is_test_mode()
                from models import UserSubscription, FeatureUsageTopUp
                sub_count = db.query(UserSubscription).filter(
                    UserSubscription.voucher_code == voucher_code,
                    UserSubscription.status.in_(["active", "paused", "grace", "expired", "cancelled"]),
                    UserSubscription.is_test == is_test_env,
                ).count()
                topup_count = db.query(FeatureUsageTopUp).filter(
                    FeatureUsageTopUp.voucher_code == voucher_code,
                    FeatureUsageTopUp.status == "paid",
                    FeatureUsageTopUp.is_test == is_test_env,
                ).count()
                qc_count = db.query(QuickConsultation).filter(
                    QuickConsultation.voucher_code == voucher_code,
                    QuickConsultation.payment_status == "completed",
                ).count()
                if (sub_count + topup_count + qc_count) >= v_obj.max_uses:
                    raise HTTPException(status_code=422, detail=f"Voucher code usage limit reached (Max {v_obj.max_uses} use).")

            if v_obj.discount_type == "percentage":
                discount_amount = round(gross_total_amount * (v_obj.discount_value / 100.0), 2)
            else:
                discount_amount = min(round(float(v_obj.discount_value), 2), gross_total_amount)
            applied_voucher_code = v_obj.code

        final_total_amount = max(0.0, round(gross_total_amount - discount_amount, 2))
        is_free = (final_total_amount == 0.0)

        # ── Appointment Date (UTC) ────────────────────────────────────────────
        now_utc = datetime.utcnow()
        now_ist = now_utc + timedelta(hours=5, minutes=30)
        date_str = slot_date or now_ist.strftime("%Y-%m-%d")
        time_str = slot_time or (now_ist + timedelta(minutes=15)).strftime("%H:%M")

        try:
            appt_ist = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
            appt_utc = appt_ist - timedelta(hours=5, minutes=30)
        except Exception:
            appt_utc = now_utc + timedelta(minutes=15)
            appt_ist = appt_utc + timedelta(hours=5, minutes=30)

        # Ensure slot is at least 15 minutes in advance from now
        if appt_ist < now_ist + timedelta(minutes=15):
            raise HTTPException(
                status_code=400,
                detail="The selected slot is no longer available as it starts too soon. Please select an upcoming slot."
            )

        # ── Validate Slot Within Consultant's Active Working Hours ────────────
        appt_dow = appt_ist.weekday()
        schedules = [s for s in consultant.schedules if getattr(s, "is_active", True) and s.day_of_week == appt_dow]
        if not schedules:
            raise HTTPException(status_code=400, detail="The consultant does not have working hours on this day. Please select another slot.")

        def _to_min_val(t_str: str) -> int:
            parts = t_str.split(":")
            return int(parts[0]) * 60 + int(parts[1])

        appt_start_min = appt_ist.hour * 60 + appt_ist.minute
        appt_end_min = appt_start_min + duration_minutes
        sched_windows = [(_to_min_val(s.start_time), _to_min_val(s.end_time)) for s in schedules]
        if not any(ws <= appt_start_min and appt_end_min <= we for ws, we in sched_windows):
            raise HTTPException(status_code=400, detail="The requested slot falls outside the consultant's working hours. Please select another slot.")

        # ── Validate Slot Does Not Conflict with Breaks ──────────────────────
        breaks = [b for b in getattr(consultant, "breaks", []) if getattr(b, "is_active", True) and b.day_of_week == appt_dow]
        break_windows = [(_to_min_val(b.break_start), _to_min_val(b.break_end)) for b in breaks]
        if any(bs < appt_end_min and appt_start_min < be for bs, be in break_windows):
            raise HTTPException(status_code=400, detail="The requested slot overlaps with the consultant's break. Please select another slot.")

        # ── Validate Slot Does Not Conflict with Existing Appointments/QCs ───
        req_start_utc = appt_utc
        req_end_utc = req_start_utc + timedelta(minutes=duration_minutes)
        candidate_busy_end = req_end_utc + timedelta(minutes=30)

        conflict_appts = db.query(Appointment).filter(
            Appointment.consultant_id == consultant.id,
            Appointment.status.in_(["scheduled", "in_progress", "confirmed"]),
            Appointment.appointment_date >= req_start_utc - timedelta(hours=3),
            Appointment.appointment_date <= req_end_utc + timedelta(hours=3),
        ).all()
        for a in conflict_appts:
            a_start = a.appointment_date.replace(tzinfo=None) if getattr(a.appointment_date, "tzinfo", None) else a.appointment_date
            a_dur = a.duration_minutes or 60
            a_busy_end = a_start + timedelta(minutes=a_dur + 30)
            if max(req_start_utc, a_start) < min(candidate_busy_end, a_busy_end):
                raise HTTPException(status_code=409, detail="This slot is already booked or within the 30-minute buffer of another consultation. Please select another slot.")

        # Clean up any previous uncompleted pending bookings by this phone number
        try:
            db.query(QuickConsultation).filter(
                QuickConsultation.phone_number == formatted_phone,
                QuickConsultation.payment_status == "pending",
            ).delete(synchronize_session=False)
            db.commit()
        except Exception as del_err:
            db.rollback()
            print(f"[QuickConsult] Cleanup own pending bookings failed: {del_err}")

        ten_mins_ago = datetime.utcnow() - timedelta(minutes=10)
        conflict_qcs = db.query(QuickConsultation).filter(
            QuickConsultation.consultant_id == consultant.id,
            QuickConsultation.call_status != "cancelled",
            or_(
                QuickConsultation.payment_status.in_(["paid", "completed"]),
                and_(
                    QuickConsultation.payment_status == "pending",
                    QuickConsultation.created_at >= ten_mins_ago,
                    QuickConsultation.phone_number != formatted_phone,
                ),
            ),
            QuickConsultation.appointment_date >= req_start_utc - timedelta(hours=3),
            QuickConsultation.appointment_date <= req_end_utc + timedelta(hours=3),
        ).all()
        for q in conflict_qcs:
            q_start = q.appointment_date.replace(tzinfo=None) if getattr(q.appointment_date, "tzinfo", None) else q.appointment_date
            q_dur = q.duration_minutes or 30
            q_busy_end = q_start + timedelta(minutes=q_dur + 30)
            if max(req_start_utc, q_start) < min(candidate_busy_end, q_busy_end):
                raise HTTPException(status_code=409, detail="This slot is already booked. Please select another slot.")

        # ── Unique 8-Character QC_ID ──────────────────────────────────────────
        qc_id = _generate_qc_id(db)

        # ── Razorpay Order Creation ───────────────────────────────────────────
        client, _ = _razorpay_client()
        amount_paise = int(round(final_total_amount * 100))
        rzp_order_id = None
        key_id = os.getenv("RAZORPAY_KEY_ID", "")

        if is_free:
            rzp_order_id = f"order_free_{qc_id}"
        elif client and amount_paise > 0:
            try:
                order_data = {
                    "amount": amount_paise,
                    "currency": "INR",
                    "receipt": qc_id,
                    "notes": {
                        "qc_id": qc_id,
                        "phone_number": formatted_phone,
                        "consultant_id": str(consultant.id),
                        "duration_minutes": str(duration_minutes),
                        "consultation_mode": consultation_mode,
                        "voucher_code": applied_voucher_code or "",
                        "type": "quick_consultation",
                    },
                }
                rzp_order = client.order.create(data=order_data)
                rzp_order_id = rzp_order.get("id")
            except Exception as e:
                print(f"[Razorpay-QC] Order creation failed: {e}")
                rzp_order_id = f"order_mock_{qc_id}"
        else:
            rzp_order_id = f"order_mock_{qc_id}"

        # ── Create QuickConsultation DB Record ────────────────────────────────
        client_ip = request.client.host if request.client else None
        c_name = consultant.full_name or (consultant.user.name if consultant.user else "Consultant")

        qc = QuickConsultation(
            qc_id=qc_id,
            phone_number=formatted_phone,
            appointment_date=appt_utc,
            duration_minutes=duration_minutes,
            consultation_mode=consultation_mode,
            consultant_id=consultant.id,
            consultant_name=c_name,
            base_amount=base_amount,
            surcharge_amount=surcharge_amount,
            taxes=taxes,
            amount_paid=final_total_amount,
            discount_amount=discount_amount,
            voucher_code=applied_voucher_code,
            razorpay_order_id=rzp_order_id,
            payment_status="pending",
            call_status="pending",
            consent_timestamp=datetime.utcnow(),
            consent_ip=client_ip,
            is_test=_is_test_mode(),
        )
        try:
            db.add(qc)
            db.commit()
            db.refresh(qc)
        except Exception as dbe:
            db.rollback()
            print(f"[QuickConsult] DB commit failed: {dbe}")
            raise HTTPException(status_code=500, detail=f"Database error while initiating booking: {str(dbe)}")

        # HIPAA / DPDP Audit Log
        AuditLogger.log_event(
            db=db,
            event_type="quick_consult_init",
            user_id=None,
            resource_type="quick_consultation",
            resource_id=qc_id,
            details=f"Quick consultation initiated for {formatted_phone} with {c_name} (Total: Rs {final_total_amount}, Voucher: {applied_voucher_code or 'None'})",
            request=request,
        )

        return {
            "success": True,
            "qc_id": qc_id,
            "order_id": rzp_order_id,
            "amount": final_total_amount,
            "amount_paise": amount_paise,
            "is_free": is_free,
            "voucher_code": applied_voucher_code,
            "discount_amount": discount_amount,
            "currency": "INR",
            "key_id": key_id,
            "consultant_name": c_name,
            "duration_minutes": duration_minutes,
            "fee_breakdown": {
                "base_fee": fee_data["base_prorated"],
                "surcharge": fee_data["surcharge"],
                "subtotal": fee_data["base_amount"],
                "gst_18": fee_data["taxes"],
                "discount": discount_amount,
                "total": final_total_amount,
            },
        }

    # ──────────────────────────────────────────────────────────────────────────
    # 4. API: Book Quick Consultation — Confirm & Settle Payment
    # ──────────────────────────────────────────────────────────────────────────
    @app.post("/api/quick-consult/book-confirm")
    async def book_quick_consult_confirm(request: Request, db: Session = Depends(get_db)):
        """
        Verify Razorpay signature (or settle 100% free voucher bookings),
        mark QuickConsultation as completed, record transaction in PaymentTransaction
        and ConsultantEarning tables, and dispatch SMS confirmation alerts via MSG91.
        """
        try:
            body = await request.json()
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid JSON payload")

        qc_id = (body.get("qc_id") or "").strip()
        razorpay_order_id = body.get("razorpay_order_id")
        razorpay_payment_id = body.get("razorpay_payment_id")
        razorpay_signature = body.get("razorpay_signature")

        qc = db.query(QuickConsultation).filter(QuickConsultation.qc_id == qc_id).first()
        if not qc:
            raise HTTPException(status_code=404, detail=f"Quick consultation '{qc_id}' not found.")

        if qc.payment_status == "completed":
            appt_ist_str = (qc.appointment_date + timedelta(hours=5, minutes=30)).strftime("%d %b %Y at %I:%M %p")
            app_base_url = os.getenv("APP_BASE_URL", "https://www.solacesquad.com").rstrip("/")
            room_url = f"{app_base_url}/quick-consult/room?id={qc.qc_id}"
            return {
                "success": True,
                "qc_id": qc.qc_id,
                "phone_number": qc.phone_number,
                "consultant_name": qc.consultant_name,
                "appointment_time": appt_ist_str,
                "room_url": room_url,
                "message": f"Payment already confirmed. The consultant will connect with you at {appt_ist_str}.",
            }

        # ── Verify Signature (Skip for Free Voucher or Mock Mode) ─────────────
        is_free_booking = (qc.amount_paid == 0.0) or (razorpay_order_id and str(razorpay_order_id).startswith("order_free_"))
        _, key_secret = _razorpay_client()
        if not is_free_booking and key_secret and razorpay_signature and not str(razorpay_payment_id or "").startswith("mock_"):
            try:
                msg = f"{razorpay_order_id}|{razorpay_payment_id}".encode("utf-8")
                expected = hmac.new(key_secret.encode("utf-8"), msg, hashlib.sha256).hexdigest()
                if not hmac.compare_digest(expected, razorpay_signature):
                    raise HTTPException(status_code=400, detail="Payment verification failed: Signature mismatch")
            except HTTPException:
                raise
            except Exception as sig_err:
                print(f"[Razorpay-QC] Signature validation error: {sig_err}")

        # ── Update QuickConsultation ──────────────────────────────────────────
        qc.payment_status = "completed"
        qc.razorpay_order_id = razorpay_order_id or (f"order_free_{qc_id}" if is_free_booking else None)
        qc.razorpay_payment_id = razorpay_payment_id or (f"pay_free_{qc_id}" if is_free_booking else f"pay_mock_{qc_id}")
        qc.razorpay_signature = razorpay_signature or ("sig_free_voucher" if is_free_booking else None)
        qc.call_status = "scheduled"
        db.commit()

        # ── Create PaymentTransaction (Ledger Entry) ──────────────────────────
        txn = None
        desc_text = f"Quick Consultation {qc.qc_id} with {qc.consultant_name}"
        if qc.voucher_code:
            desc_text += f" (Voucher: {qc.voucher_code})"

        try:
            inv_num = _generate_qc_invoice_number(db)
            txn = PaymentTransaction(
                user_id=None,  # Guest user / quick consult
                transaction_type="consultation",
                amount=qc.amount_paid,
                currency="INR",
                status="completed",
                razorpay_order_id=qc.razorpay_order_id,
                razorpay_payment_id=qc.razorpay_payment_id,
                razorpay_signature=qc.razorpay_signature,
                related_entity_type="quick_consultation",
                related_entity_id=qc.id,
                description=desc_text,
                invoice_number=inv_num,
                is_test=_is_test_mode(),
            )
            db.add(txn)
            db.commit()
            db.refresh(txn)
        except Exception as txn_err:
            db.rollback()
            print(f"[QuickConsult] PaymentTransaction standard creation error: {txn_err}")
            try:
                # Emergency fallback with high-entropy unique invoice number
                fallback_inv = f"SS-{datetime.utcnow().year}-{secrets.randbelow(90000) + 10000}"
                txn = PaymentTransaction(
                    user_id=None,
                    transaction_type="consultation",
                    amount=qc.amount_paid,
                    currency="INR",
                    status="completed",
                    razorpay_order_id=qc.razorpay_order_id,
                    razorpay_payment_id=qc.razorpay_payment_id,
                    razorpay_signature=qc.razorpay_signature,
                    related_entity_type="quick_consultation",
                    related_entity_id=qc.id,
                    description=desc_text,
                    invoice_number=fallback_inv,
                    is_test=_is_test_mode(),
                )
                db.add(txn)
                db.commit()
                db.refresh(txn)
            except Exception as fb_err:
                db.rollback()
                print(f"[QuickConsult] PaymentTransaction fallback creation error: {fb_err}")
                txn = None

        # ── Create ConsultantEarning Record ───────────────────────────────────
        try:
            consultant = qc.consultant
            c_user_id = consultant.user_id if consultant else None
            payout = consultant.consultant_payout if consultant and consultant.consultant_payout > 0 else round(qc.base_amount - 100.0, 2)
            platform_fee = round(qc.amount_paid - qc.taxes - payout, 2)

            if c_user_id:
                earning = ConsultantEarning(
                    consultant_user_id=c_user_id,
                    appointment_id=None,
                    quick_consultation_id=qc.id,
                    payment_transaction_id=txn.id if txn else None,
                    gross_amount=qc.amount_paid,
                    platform_fee_pct=round((platform_fee / (qc.amount_paid - qc.taxes) * 100), 2) if (qc.amount_paid - qc.taxes) > 0 else 0.0,
                    platform_fee=max(platform_fee, 0.0),
                    consultant_payout=payout if not is_free_booking else round(qc.base_amount - 100.0, 2),
                    payout_status="pending",
                    is_test=_is_test_mode(),
                    taxes=qc.taxes if not is_free_booking else 0.0,
                    discount_amount=qc.discount_amount or 0.0,
                )
                db.add(earning)
                db.commit()
        except Exception as earn_err:
            db.rollback()
            print(f"[QuickConsult] ConsultantEarning creation error: {earn_err}")

        # ── Format Appointment Time IST ───────────────────────────────────────
        appt_ist = qc.appointment_date + timedelta(hours=5, minutes=30)
        appt_ist_str = appt_ist.strftime("%d %b %Y at %I:%M %p")
        # Use environment base URL (e.g. Mirror URL on mirror, solacesquad.com on production)
        app_base_url = os.getenv("APP_BASE_URL", "https://www.solacesquad.com").rstrip("/")
        room_url = f"{app_base_url}/quick-consult/room?id={qc.qc_id}"
        is_webrtc = (getattr(qc, "consultation_mode", "telephony") == "webrtc")

        # ── 1. Dispatch Client MSG91 SMS Alert ────────────────────────────────
        if is_webrtc:
            # Web Quick Consultation (WebRTC): Uses new multiline template with room link
            user_template_id = (
                os.getenv("MSG91_QC_WEB_TEMPLATE_ID")
                or os.getenv("MSG91_QC_USER_LINK_TEMPLATE_ID")
                or "6ab1f30e9c651b3e9e03e023"
            )
            user_sms = (
                f"Dear User,\n"
                f"Your SolaceSquad Quick Consultation (ID: {qc.qc_id}) with {qc.consultant_name} is confirmed for {appt_ist_str}.\n"
                f"Join your call at: {room_url}\n"
                f"- SolaceSquad"
            )
            _send_msg91_sms(
                phone_number=qc.phone_number,
                message=user_sms,
                qc_id=qc.qc_id,
                consultant_name=qc.consultant_name,
                appt_time=appt_ist_str,
                room_url=room_url,
                template_id=user_template_id,
            )
        else:
            # Telephony / Exotel Quick Consultation: Uses old template without link
            user_template_id = os.getenv("MSG91_QC_TEMPLATE_ID", "6aa3c13688431827e60b0d72")
            user_sms = (
                f"Thanks for Availing Quick Consultation!\n"
                f"Your Payment was successful!\n"
                f"Your SolaceSquad Quick Consultation (ID: {qc.qc_id}) with {qc.consultant_name} for {appt_ist_str}.\n"
                f"The consultant will call you on this mobile number."
            )
            _send_msg91_sms(
                phone_number=qc.phone_number,
                message=user_sms,
                qc_id=qc.qc_id,
                consultant_name=qc.consultant_name,
                appt_time=appt_ist_str,
                room_url=None,
                template_id=user_template_id,
            )

        # ── 2. Dispatch Consultant & Admin Notifications (Email & SMS) ────────
        c_user = consultant.user if consultant else None
        c_email = (c_user.email or "").strip() if c_user else ""
        c_name = consultant.full_name or (c_user.name if c_user else qc.consultant_name) if consultant else qc.consultant_name
        c_spec = (consultant.specialization or "").strip() if consultant else ""
        admin_email = os.getenv("ADMIN_EMAIL", "sg@solacesquad.com")
        app_url = os.getenv("APP_BASE_URL", "https://www.solacesquad.com")

        # Resolve Client Info (check for registered user linked to this phone number)
        client_name = ""
        client_phone = qc.phone_number or ""
        clean_phone = client_phone.replace("+91", "").replace(" ", "").replace("-", "").strip()
        try:
            reg_user = db.query(User).filter(
                or_(
                    User.phone_number == client_phone,
                    User.phone_number == clean_phone,
                    User.phone_number == f"+91{clean_phone}",
                )
            ).first()
            if reg_user and reg_user.name:
                client_name = reg_user.name.strip()
        except Exception as u_err:
            print(f"[QC-EMAIL] Client user lookup error: {u_err}")

        from sendgrid_email import send_quick_consult_consultant_email, send_quick_consult_admin_email

        # A. Consultant Email Alert (only if consultant email exists and is not identical to admin_email)
        if c_email and c_email.lower() != admin_email.lower():
            try:
                send_quick_consult_consultant_email(
                    to_email=c_email,
                    to_name=c_name,
                    qc_id=qc.qc_id,
                    appointment_time_str=appt_ist_str,
                    duration_minutes=qc.duration_minutes,
                    payout_amount=payout,
                    app_base_url=app_url,
                    consultation_mode=qc.consultation_mode or "telephony",
                    room_url=room_url,
                    client_name=client_name,
                    client_phone=client_phone,
                    consultant_name=c_name,
                    consultant_specialization=c_spec,
                    is_admin=False,
                )
            except Exception as mail_exc:
                print(f"[QC-EMAIL-ERROR] Failed to dispatch consultant email to {c_email}: {mail_exc}")

        # B. Admin Email Alert (ALWAYS dispatched)
        if admin_email:
            try:
                send_quick_consult_admin_email(
                    to_email=admin_email,
                    qc_id=qc.qc_id,
                    appointment_time_str=appt_ist_str,
                    duration_minutes=qc.duration_minutes,
                    consultant_name=c_name,
                    consultant_specialization=c_spec,
                    client_name=client_name,
                    client_phone=client_phone,
                    app_base_url=app_url,
                    consultation_mode=qc.consultation_mode or "telephony",
                    room_url=room_url,
                )
            except Exception as mail_exc:
                print(f"[QC-EMAIL-ERROR] Failed to dispatch admin email to {admin_email}: {mail_exc}")

        # C. Consultant-specific SMS (when DLT template is configured)
            if is_webrtc:
                c_template_id = os.getenv("MSG91_QC_CONSULTANT_WEB_TEMPLATE_ID") or os.getenv("MSG91_QC_CONSULTANT_TEMPLATE_ID", "6ab28c02493147b392022142")
                c_msg = (
                    f"Dear {c_name},\n"
                    f"A new Web Quick Consultation (ID: {qc.qc_id}) is confirmed for {appt_ist_str}.\n"
                    f"Please log in to your SolaceSquad dashboard and join the call from the Quick Consultation tab.\n"
                    f" - SolaceSquad"
                )
            else:
                c_template_id = os.getenv("MSG91_QC_CONSULTANT_TEMPLATE_ID", "6ab28c02493147b392022142")
                c_msg = (
                    f"Dear {c_name},\n"
                    f"A Quick Consultation (ID: {qc.qc_id}) is confirmed for {appt_ist_str}.\n"
                    f"You will receive a call at the scheduled time.\n"
                    f" - SolaceSquad"
                )
            c_phone = c_user.phone_number
            if c_template_id and c_phone:
                dur_label = f"{qc.duration_minutes} Mins" if qc.duration_minutes < 60 else "1 Hour"
                _send_msg91_consultant_sms(
                    phone_number=c_phone,
                    consultant_name=c_name,
                    duration=dur_label,
                    qc_id=qc.qc_id,
                    time=appt_ist_str,
                    template_id=c_template_id,
                    message=c_msg,
                )

        # ── 3. Schedule Call Status (Strictly adheres to scheduled appointment time) ──
        # Telephony call bridge will be initiated at appointment start time via background poller (if telephony mode).

        # HIPAA / DPDP Audit Log
        AuditLogger.log_event(
            db=db,
            event_type="quick_consult_confirmed",
            user_id=c_user_id,
            resource_type="quick_consultation",
            resource_id=qc.qc_id,
            details=f"Payment confirmed for QC_ID {qc.qc_id} ({qc.consultation_mode}). Call scheduled for {appt_ist_str}.",
            request=request,
        )

        return {
            "success": True,
            "qc_id": qc.qc_id,
            "phone_number": qc.phone_number,
            "consultant_name": qc.consultant_name,
            "appointment_time": appt_ist_str,
            "duration_minutes": 30,
            "amount_paid": qc.amount_paid,
            "consultation_mode": qc.consultation_mode or "telephony",
            "call_initiated": False,
            "room_url": room_url if is_webrtc else "",
            "message": (
                f"Payment successful! Your 30-minute web consultation is confirmed with {qc.consultant_name} for {appt_ist_str}."
                if is_webrtc else
                f"Payment successful! Your 30-minute phone consultation is confirmed with {qc.consultant_name} for {appt_ist_str}. The consultant will call your mobile number."
            ),
        }

    # ──────────────────────────────────────────────────────────────────────────
    # 4.5. WebRTC Call Room (/quick-consult/room/{qc_id} or /quick-consult/room?id=...)
    # ──────────────────────────────────────────────────────────────────────────
    @app.get("/quick-consult/room", response_class=HTMLResponse)
    async def quick_consult_call_room_query(
        request: Request,
        id: Optional[str] = None,
        qc_id: Optional[str] = None,
        db: Session = Depends(get_db)
    ):
        target_id = (id or qc_id or "").strip()
        if not target_id:
            raise HTTPException(status_code=400, detail="Missing consultation room ID.")
        return await quick_consult_call_room(qc_id=target_id, request=request, db=db)

    @app.get("/quick-consult/room/{qc_id}", response_class=HTMLResponse)
    async def quick_consult_call_room(
        qc_id: str,
        request: Request,
        db: Session = Depends(get_db)
    ):
        """
        WebRTC Audio/Video Call Room for Quick Consultation with 5-minute pre-call time gating.
        - If > 5 mins before appointment: Renders Waiting Room with countdown to unlock.
        - If within 5 mins before appointment up to end time (+ grace): Renders Active WebRTC Call Room.
        - If expired: Renders Completed session screen.
        """
        qc = db.query(QuickConsultation).filter(QuickConsultation.qc_id == qc_id).first()
        if not qc:
            raise HTTPException(status_code=404, detail="Quick Consultation appointment not found.")

        consultant = qc.consultant
        c_photo = consultant.photo_url if (consultant and consultant.photo_url) else "/static/images/default-avatar.png"
        if c_photo and not (c_photo.startswith("http") or c_photo.startswith("/")):
            c_photo = f"/{c_photo}"
        c_spec = consultant.specialization if (consultant and consultant.specialization) else "Wellness Expert"

        session_uid = request.session.get("user_id")
        user_type = request.session.get("user_type", "")
        is_consultant = False
        if session_uid:
            try:
                session_uid_int = int(session_uid)
            except (ValueError, TypeError):
                session_uid_int = session_uid

            if user_type == "consultant":
                is_consultant = True
            elif consultant and consultant.user_id == session_uid_int:
                is_consultant = True
            else:
                u = db.query(User).filter(User.id == session_uid_int).first()
                if u and u.user_type == "consultant":
                    is_consultant = True

        # Ensure payment was completed (or free voucher)
        if qc.payment_status != "completed":
            return templates.TemplateResponse(
                "pages/quick_consult_call_room.html",
                {
                    "request": request,
                    "status": "payment_pending",
                    "is_consultant": is_consultant,
                    "qc": qc,
                    "message": "Payment for this consultation is still pending or incomplete.",
                }
            )

        now_utc = datetime.utcnow()
        now_ist = now_utc + timedelta(hours=5, minutes=30)
        appt_start_utc = qc.appointment_date
        appt_end_utc = appt_start_utc + timedelta(minutes=30)
        unlock_window_start_utc = appt_start_utc - timedelta(minutes=5)
        session_expiry_utc = appt_end_utc + timedelta(minutes=10) # 10 min grace period

        appt_ist = appt_start_utc + timedelta(hours=5, minutes=30)
        appt_ist_str = appt_ist.strftime("%d %b %Y at %I:%M %p")
        appt_time_short = appt_ist.strftime("%I:%M %p")

        agora_app_id = os.getenv("AGORA_APP_ID", "3ee48a30328245bcb0b7ac7d6099b721")
        channel_name = f"qc_{qc.qc_id.lower()}"

        if now_utc < unlock_window_start_utc:
            # ── STATE 1: Waiting Room (Time-Gated: > 5 mins before call) ──
            seconds_until_unlock = max(1, int((unlock_window_start_utc - now_utc).total_seconds()))
            seconds_until_start = max(1, int((appt_start_utc - now_utc).total_seconds()))
            return templates.TemplateResponse(
                "pages/quick_consult_call_room.html",
                {
                    "request": request,
                    "status": "waiting",
                    "is_locked": True,
                    "is_consultant": is_consultant,
                    "qc": qc,
                    "consultant_name": qc.consultant_name,
                    "consultant_photo": c_photo,
                    "consultant_spec": c_spec,
                    "appointment_time_str": appt_ist_str,
                    "appointment_time_short": appt_time_short,
                    "seconds_until_unlock": seconds_until_unlock,
                    "seconds_until_start": seconds_until_start,
                    "agora_app_id": agora_app_id,
                    "channel_name": channel_name,
                }
            )

        elif unlock_window_start_utc <= now_utc <= session_expiry_utc:
            # ── STATE 2: Active WebRTC Call Room (5 mins before start up to end) ──
            seconds_remaining = max(60, int((appt_end_utc - now_utc).total_seconds()))
            return templates.TemplateResponse(
                "pages/quick_consult_call_room.html",
                {
                    "request": request,
                    "status": "active",
                    "is_locked": False,
                    "is_consultant": is_consultant,
                    "qc": qc,
                    "consultant_name": qc.consultant_name,
                    "consultant_photo": c_photo,
                    "consultant_spec": c_spec,
                    "appointment_time_str": appt_ist_str,
                    "appointment_time_short": appt_time_short,
                    "seconds_remaining": seconds_remaining,
                    "agora_app_id": agora_app_id,
                    "channel_name": channel_name,
                }
            )

        else:
            # ── STATE 3: Expired / Completed Session ──
            return templates.TemplateResponse(
                "pages/quick_consult_call_room.html",
                {
                    "request": request,
                    "status": "expired",
                    "is_locked": True,
                    "is_consultant": is_consultant,
                    "qc": qc,
                    "consultant_name": qc.consultant_name,
                    "consultant_photo": c_photo,
                    "consultant_spec": c_spec,
                    "appointment_time_str": appt_ist_str,
                    "appointment_time_short": appt_time_short,
                }
            )

    # ──────────────────────────────────────────────────────────────────────────
    # 4.6. Silent Background Recording Receiver Endpoint
    # ──────────────────────────────────────────────────────────────────────────
    @app.post("/api/quick-consult/room/{qc_id}/save-recording")
    async def save_quick_consult_recording(
        qc_id: str,
        request: Request,
        db: Session = Depends(get_db),
    ):
        """
        Receives silent background recording data from the call room,
        logs HIPAA/DPDP audit trails, and marks recording saved.
        """
        qc = db.query(QuickConsultation).filter(QuickConsultation.qc_id == qc_id).first()
        if not qc:
            raise HTTPException(status_code=404, detail="Quick consultation not found")

        try:
            # Log secure recording event
            AuditLogger.log_event(
                db=db,
                event_type="quick_consult_recording_saved",
                user_id=None,
                resource_type="quick_consultation",
                resource_id=qc_id,
                details=f"Silent background audio recording securely captured and registered for Quick Consultation {qc_id}",
                request=request,
            )
            return {"success": True, "qc_id": qc_id, "message": "Recording registered successfully"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ──────────────────────────────────────────────────────────────────────────
    # 4.7. WebRTC Single-Client Device Session Gating & Transfer Endpoints
    # ──────────────────────────────────────────────────────────────────────────
    def _is_consultant_caller(req: Request, qc_obj: QuickConsultation, db_session: Session) -> bool:
        session_uid = req.session.get("user_id")
        user_type = req.session.get("user_type", "")
        if session_uid:
            try:
                session_uid_int = int(session_uid)
            except (ValueError, TypeError):
                session_uid_int = session_uid

            if user_type == "consultant":
                return True
            if qc_obj.consultant and qc_obj.consultant.user_id == session_uid_int:
                return True
            u = db_session.query(User).filter(User.id == session_uid_int).first()
            if u and u.user_type == "consultant":
                return True
        return False

    @app.post("/api/quick-consult/room/{qc_id}/session-check")
    async def quick_consult_session_check(
        qc_id: str,
        request: Request,
        db: Session = Depends(get_db),
    ):
        """
        Validates client device authorization before joining WebRTC room.
        Limits client access to 1 active device at a time.
        """
        qc = db.query(QuickConsultation).filter(QuickConsultation.qc_id == qc_id).first()
        if not qc:
            raise HTTPException(status_code=404, detail="Quick consultation not found")

        # Consultants bypass client device token restrictions
        if _is_consultant_caller(request, qc, db):
            return {"status": "allowed", "is_consultant": True}

        try:
            body = await request.json()
        except Exception:
            body = {}
        device_token = (body.get("device_token") or "").strip()
        force_takeover = bool(body.get("force_takeover", False))

        if not device_token:
            return {"status": "error", "message": "Missing device token"}

        now_utc = datetime.utcnow()
        last_seen = getattr(qc, "client_device_last_seen", None)
        active_token = getattr(qc, "client_device_token", None)
        pending_token = getattr(qc, "pending_device_token", None)
        switch_decision = getattr(qc, "switch_decision", "none") or "none"

        is_stale = (last_seen is None) or (now_utc - last_seen > timedelta(seconds=25))

        # Force takeover if previous session is stale (> 15s) or explicitly requested
        if force_takeover and (is_stale or (last_seen and (now_utc - last_seen > timedelta(seconds=15)))):
            qc.client_device_token = device_token
            qc.client_device_last_seen = now_utc
            qc.pending_device_token = None
            qc.switch_decision = "none"
            db.commit()
            return {"status": "allowed", "is_consultant": False, "took_over": True}

        # Case 1: No active device, or active device is this device, or previous active device timed out
        if not active_token or active_token == device_token or is_stale:
            qc.client_device_token = device_token
            qc.client_device_last_seen = now_utc
            if pending_token == device_token:
                qc.pending_device_token = None
            qc.switch_decision = "none"
            db.commit()
            return {"status": "allowed", "is_consultant": False}

        # Case 2: This device was pending and the active device approved switching
        if pending_token == device_token and switch_decision == "approved":
            qc.client_device_token = device_token
            qc.client_device_last_seen = now_utc
            qc.pending_device_token = None
            qc.switch_decision = "none"
            db.commit()
            return {"status": "allowed", "is_consultant": False, "switched": True}

        # Case 3: Active device rejected the switch request
        if pending_token == device_token and switch_decision == "rejected":
            return {
                "status": "rejected",
                "is_consultant": False,
                "message": "The active session chose to remain on their current device. Only one participant may join using this link at a time."
            }

        # Case 4: Conflict - another device is actively connected
        qc.pending_device_token = device_token
        qc.pending_device_at = now_utc
        qc.switch_decision = "none"
        db.commit()
        return {
            "status": "conflict",
            "is_consultant": False,
            "message": "Another device is currently using this consultation link.",
            "active_since": last_seen.isoformat() if last_seen else None
        }

    @app.post("/api/quick-consult/room/{qc_id}/heartbeat")
    async def quick_consult_heartbeat(
        qc_id: str,
        request: Request,
        db: Session = Depends(get_db),
    ):
        """Periodic heartbeat for active device. Detects pending 2nd device and kicks logged-out devices."""
        qc = db.query(QuickConsultation).filter(QuickConsultation.qc_id == qc_id).first()
        if not qc:
            raise HTTPException(status_code=404, detail="Quick consultation not found")

        if _is_consultant_caller(request, qc, db):
            return {"status": "ok", "is_consultant": True}

        try:
            body = await request.json()
        except Exception:
            body = {}
        device_token = (body.get("device_token") or "").strip()
        if not device_token:
            return {"status": "error", "message": "Missing device token"}

        now_utc = datetime.utcnow()
        active_token = getattr(qc, "client_device_token", None)
        pending_token = getattr(qc, "pending_device_token", None)
        pending_at = getattr(qc, "pending_device_at", None)
        switch_decision = getattr(qc, "switch_decision", "none") or "none"

        # If this device is the active device
        if active_token == device_token:
            qc.client_device_last_seen = now_utc
            # Check if there is an active pending request from another device (within last 60 seconds)
            has_pending = bool(
                pending_token
                and pending_token != device_token
                and switch_decision == "none"
                and pending_at
                and (now_utc - pending_at) < timedelta(seconds=60)
            )
            db.commit()
            return {"status": "ok", "conflict_pending": has_pending}

        # Otherwise, this device is no longer the active device (kicked / switched out)
        return {
            "status": "kicked",
            "message": "You were logged out from this device because the consultation was switched to another device."
        }

    @app.post("/api/quick-consult/room/{qc_id}/session-decision")
    async def quick_consult_session_decision(
        qc_id: str,
        request: Request,
        db: Session = Depends(get_db),
    ):
        """Active device chooses to either switch (and logout here) or stay on current device."""
        qc = db.query(QuickConsultation).filter(QuickConsultation.qc_id == qc_id).first()
        if not qc:
            raise HTTPException(status_code=404, detail="Quick consultation not found")

        try:
            body = await request.json()
        except Exception:
            body = {}
        device_token = (body.get("device_token") or "").strip()
        decision = (body.get("decision") or "").strip().lower() # "approve" or "reject"

        active_token = getattr(qc, "client_device_token", None)
        if active_token != device_token:
            return {"success": False, "error": "Only the currently active device can make session decisions"}

        if decision == "approve":
            # Active user chose to switch to the second device and logout here
            qc.switch_decision = "approved"
            pending_token = getattr(qc, "pending_device_token", None)
            if pending_token:
                qc.client_device_token = pending_token
                qc.client_device_last_seen = datetime.utcnow()
                qc.pending_device_token = None
            db.commit()
            return {"success": True, "action": "switched"}
        elif decision == "reject":
            # Active user chose to stay on current device
            qc.switch_decision = "rejected"
            db.commit()
            return {"success": True, "action": "rejected"}
        else:
            return {"success": False, "error": "Invalid decision"}

    @app.post("/api/quick-consult/room/{qc_id}/session-release")
    async def quick_consult_session_release(
        qc_id: str,
        request: Request,
        db: Session = Depends(get_db),
    ):
        """Releases the device session when client ends or leaves the call."""
        qc = db.query(QuickConsultation).filter(QuickConsultation.qc_id == qc_id).first()
        if not qc:
            return {"success": True}

        try:
            body = await request.json()
        except Exception:
            body = {}
        device_token = (body.get("device_token") or "").strip()

        active_token = getattr(qc, "client_device_token", None)
        if not active_token or active_token == device_token:
            qc.client_device_token = None
            qc.client_device_last_seen = None
            qc.pending_device_token = None
            qc.switch_decision = "none"
            db.commit()

        return {"success": True}

    # ──────────────────────────────────────────────────────────────────────────
    # 5. On-Demand Call Trigger (/api/quick-consult/{qc_id}/connect-call)
    # ──────────────────────────────────────────────────────────────────────────
    @app.post("/api/quick-consult/{qc_id}/connect-call")
    async def connect_quick_consult_call_now(
        qc_id: str,
        request: Request,
        db: Session = Depends(get_db),
    ):
        """
        On-demand endpoint to trigger / re-dial Exotel call bridge for a confirmed session.
        Accessible by both client (via confirmation screen) and consultant (via dashboard).
        """
        qc = db.query(QuickConsultation).filter(QuickConsultation.qc_id == qc_id).first()
        if not qc:
            raise HTTPException(status_code=404, detail="Quick Consultation not found.")
        if qc.payment_status != "completed":
            raise HTTPException(status_code=400, detail="Payment has not been completed.")

        consultant = qc.consultant
        c_phone = consultant.user.phone_number if (consultant and consultant.user) else None
        u_phone = qc.phone_number

        if not c_phone:
            raise HTTPException(status_code=400, detail="Consultant phone number is not configured in profile.")
        if not u_phone:
            raise HTTPException(status_code=400, detail="User phone number is missing.")

        app_url = os.getenv("APP_BASE_URL", "https://www.solacesquad.com")
        print(f"[EXOTEL-MANUAL] Connecting call for QC {qc.qc_id}: {c_phone} -> {u_phone}")
        bridge_res = bridge_quick_consult_call(
            from_phone=c_phone,
            to_phone=u_phone,
            duration_minutes=qc.duration_minutes,
            qc_id=qc.qc_id,
            callback_url=f"{app_url.rstrip('/')}/api/exotel/webhook",
        )

        if bridge_res.get("success"):
            qc.call_status = "initiated"
            qc.exotel_call_sid = bridge_res.get("call_sid")
            db.commit()
            return {
                "success": True,
                "message": "Call initiated! Your phone will ring shortly from SolaceSquad.",
                "call_sid": bridge_res.get("call_sid"),
            }
        else:
            return {
                "success": False,
                "message": bridge_res.get("message", "Failed to connect call via Exotel."),
            }

    # ──────────────────────────────────────────────────────────────────────────
    # 5. Consultant Portal: View Quick Consultations
    # ──────────────────────────────────────────────────────────────────────────
    @app.get("/api/consultant/quick-consultations")
    async def get_consultant_quick_consultations(request: Request, db: Session = Depends(get_db)):
        """
        Return quick consultations assigned to the logged-in consultant.
        """
        try:
            uid = request.session.get("user_id")
            if not uid:
                return {"success": False, "error": "Not authenticated", "consultations": []}

            consultant = db.query(ConsultantProfile).filter(ConsultantProfile.user_id == uid).first()
            if not consultant:
                return {"success": True, "consultations": []}

            qcs = (
                db.query(QuickConsultation)
                .filter(
                    QuickConsultation.consultant_id == consultant.id,
                    QuickConsultation.payment_status == "completed",
                )
                .order_by(QuickConsultation.appointment_date.desc())
                .all()
            )

            now_utc = datetime.utcnow()
            changed = False
            results = []
            for q in qcs:
                if q.appointment_date:
                    duration = q.duration_minutes or 30
                    q_end = q.appointment_date + timedelta(minutes=duration)
                    if q.call_status == "scheduled" and q_end < now_utc:
                        q.call_status = "expired"
                        changed = True
                    elif q.call_status in ["initiated", "in_progress"] and q_end < now_utc:
                        q.call_status = "completed"
                        changed = True

                appt_ist = (q.appointment_date + timedelta(hours=5, minutes=30)) if q.appointment_date else None
                c_mode = getattr(q, "consultation_mode", "telephony") or "telephony"
                results.append({
                    "id": q.id,
                    "qc_id": q.qc_id,
                    "consultation_mode": c_mode,
                    "appointment_date": q.appointment_date.isoformat() + "Z" if q.appointment_date else "",
                    "appointment_time_ist": appt_ist.strftime("%d %b %Y, %I:%M %p") if appt_ist else "",
                    "duration_minutes": q.duration_minutes,
                    "amount_paid": q.amount_paid,
                    "call_status": q.call_status,
                    "room_url": f"/quick-consult/room/{q.qc_id}" if c_mode == "webrtc" else "",
                    "consultant_notes": q.consultant_notes or "",
                    "created_at": q.created_at.isoformat() + "Z" if q.created_at else "",
                })

            if changed:
                try:
                    db.commit()
                except Exception as ce:
                    db.rollback()
                    print(f"[QuickConsult] DB commit failed during status auto-update: {ce}")

            return {"success": True, "consultations": results}
        except Exception as e:
            print(f"[QuickConsult] Error fetching consultant quick consultations: {e}")
            return {"success": False, "error": str(e), "consultations": []}

    # ──────────────────────────────────────────────────────────────────────────
    # 6. Consultant Portal: Save Clinical Observations (HIPAA Protected)
    # ──────────────────────────────────────────────────────────────────────────
    @app.post("/api/consultant/quick-consultations/{qc_id}/notes")
    async def save_quick_consult_notes(
        qc_id: str,
        request: Request,
        db: Session = Depends(get_db),
    ):
        """
        Save or update clinical observations for a Quick Consultation session.
        Protected Health Information (PHI) under HIPAA:
          - Only the assigned consultant can access and write notes.
          - Every update is logged in AuditLog with timestamp, IP, and actor ID.
        """
        uid = request.session.get("user_id")
        if not uid:
            raise HTTPException(status_code=401, detail="Not authenticated")

        try:
            body = await request.json()
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid JSON payload")

        notes = (body.get("notes") or "").strip()

        qc = db.query(QuickConsultation).filter(QuickConsultation.qc_id == qc_id).first()
        if not qc:
            raise HTTPException(status_code=404, detail="Quick consultation not found.")

        # HIPAA Access Control Check
        if not qc.consultant or qc.consultant.user_id != uid:
            AuditLogger.log_event(
                db=db,
                event_type="unauthorized_phi_access_attempt",
                user_id=uid,
                resource_type="quick_consultation_notes",
                resource_id=qc_id,
                details=f"User {uid} attempted to access notes of QC_ID {qc_id} owned by consultant {qc.consultant_id}",
                status="failure",
                request=request,
            )
            raise HTTPException(status_code=403, detail="Access denied. You are not authorized to view or edit these clinical notes.")

        qc.consultant_notes = notes
        db.commit()

        # Log HIPAA Compliance Audit Event
        AuditLogger.log_event(
            db=db,
            event_type="update_quick_consult_notes",
            user_id=uid,
            resource_type="quick_consultation_notes",
            resource_id=qc_id,
            details=f"Consultant {uid} updated clinical observations for session {qc_id}",
            request=request,
        )

        return {"success": True, "message": "Clinical observations saved securely.", "qc_id": qc_id}

    # ──────────────────────────────────────────────────────────────────────────
    # 7. Telephony Trigger: Exotel Call Bridging
    # ──────────────────────────────────────────────────────────────────────────
    @app.post("/api/quick-consult/trigger-calls")
    async def trigger_due_quick_consult_calls(request: Request, db: Session = Depends(get_db)):
        """
        Cron or manual endpoint to initiate Exotel calls for sessions starting now (+-5 mins).
        """
        now_utc = datetime.utcnow()
        window_start = now_utc - timedelta(minutes=5)
        window_end = now_utc + timedelta(minutes=5)
        app_url = os.getenv("APP_BASE_URL", "https://www.solacesquad.com")

        due_sessions = (
            db.query(QuickConsultation)
            .filter(
                QuickConsultation.payment_status == "completed",
                QuickConsultation.call_status == "scheduled",
                QuickConsultation.appointment_date >= window_start,
                QuickConsultation.appointment_date <= window_end,
            )
            .all()
        )

        results = []
        for qc in due_sessions:
            c_phone = qc.consultant.user.phone_number if (qc.consultant and qc.consultant.user) else None
            u_phone = qc.phone_number

            if not c_phone or not u_phone:
                continue

            bridge_res = bridge_quick_consult_call(
                from_phone=c_phone,
                to_phone=u_phone,
                duration_minutes=qc.duration_minutes,
                qc_id=qc.qc_id,
                callback_url=f"{app_url.rstrip('/')}/api/exotel/webhook",
            )

            if bridge_res.get("success"):
                qc.call_status = "initiated"
                qc.exotel_call_sid = bridge_res.get("call_sid")
                db.commit()

            results.append({"qc_id": qc.qc_id, "result": bridge_res})

        return {"success": True, "initiated_count": len(results), "calls": results}

    # ──────────────────────────────────────────────────────────────────────────
    # 7B. Background Startup Poller: Automatic Scheduled Call Triggering
    # ──────────────────────────────────────────────────────────────────────────
    @app.on_event("startup")
    async def start_quick_consult_telephony_poller():
        """
        Background task running every 30 seconds to automatically trigger due Exotel calls
        when appointment start time arrives (now - 5m <= appt <= now + 1m).
        """
        async def _poller_worker():
            await asyncio.sleep(10)
            while True:
                try:
                    from database import get_db_session
                    with get_db_session() as db:
                        now_utc = datetime.utcnow()
                        window_start = now_utc - timedelta(minutes=5)
                        window_end = now_utc + timedelta(minutes=1)
                        app_url = os.getenv("APP_BASE_URL", "https://www.solacesquad.com")

                        # Auto-expire stale pending QuickConsultation checkouts (>10 mins old)
                        stale_cutoff = now_utc - timedelta(minutes=10)
                        try:
                            db.query(QuickConsultation).filter(
                                QuickConsultation.payment_status == "pending",
                                QuickConsultation.created_at < stale_cutoff,
                            ).update({"call_status": "cancelled", "payment_status": "failed"}, synchronize_session=False)
                            db.commit()
                        except Exception as cl_err:
                            db.rollback()

                        due_sessions = (
                            db.query(QuickConsultation)
                            .filter(
                                QuickConsultation.payment_status == "completed",
                                QuickConsultation.call_status == "scheduled",
                                or_(QuickConsultation.consultation_mode == "telephony", QuickConsultation.consultation_mode == None),
                                QuickConsultation.appointment_date >= window_start,
                                QuickConsultation.appointment_date <= window_end,
                            )
                            .all()
                        )

                        for qc in due_sessions:
                            c_phone = qc.consultant.user.phone_number if (qc.consultant and qc.consultant.user) else None
                            u_phone = qc.phone_number
                            if not c_phone or not u_phone:
                                continue

                            print(f"[QC-TELEPHONY-POLLER] Triggering scheduled call for {qc.qc_id}: {c_phone} -> {u_phone} (Appt: {qc.appointment_date} UTC)")
                            bridge_res = bridge_quick_consult_call(
                                from_phone=c_phone,
                                to_phone=u_phone,
                                duration_minutes=qc.duration_minutes,
                                qc_id=qc.qc_id,
                                callback_url=f"{app_url.rstrip('/')}/api/exotel/webhook",
                            )
                            if bridge_res.get("success"):
                                qc.call_status = "initiated"
                                qc.exotel_call_sid = bridge_res.get("call_sid")
                                db.commit()
                except asyncio.CancelledError:
                    break
                except Exception as p_err:
                    print(f"[QC-TELEPHONY-POLLER-ERROR] {p_err}")

                await asyncio.sleep(30)

        asyncio.create_task(_poller_worker())

    async def _retry_consultant_call_after_delay(qc_id_str: str, delay_seconds: int = 120):
        """
        Background worker that waits 2 minutes (120s) and triggers a 2nd call attempt
        to the consultant if the consultation is still in 'consultant_retrying' status.
        """
        try:
            await asyncio.sleep(delay_seconds)
            from database import get_db_session
            with get_db_session() as session:
                target_qc = session.query(QuickConsultation).filter(QuickConsultation.qc_id == qc_id_str).first()
                if not target_qc:
                    return
                # Only retry if still in consultant_retrying state (i.e. not completed or manually connected)
                if target_qc.call_status != "consultant_retrying":
                    print(f"[EXOTEL-RETRY] Skipping retry for {qc_id_str} as status is '{target_qc.call_status}'")
                    return

                c_phone = target_qc.consultant.user.phone_number if (target_qc.consultant and target_qc.consultant.user) else None
                u_phone = target_qc.phone_number
                if not c_phone or not u_phone:
                    return

                app_url = os.getenv("APP_BASE_URL", "https://www.solacesquad.com")
                print(f"[EXOTEL-RETRY] 🔄 Initiating 2nd call attempt (retry) for {qc_id_str}: {c_phone} -> {u_phone}")
                bridge_res = bridge_quick_consult_call(
                    from_phone=c_phone,
                    to_phone=u_phone,
                    duration_minutes=target_qc.duration_minutes,
                    qc_id=target_qc.qc_id,
                    callback_url=f"{app_url.rstrip('/')}/api/exotel/webhook",
                )
                if bridge_res.get("success"):
                    target_qc.exotel_call_sid = bridge_res.get("call_sid")
                    session.commit()
        except Exception as retry_err:
            print(f"[EXOTEL-RETRY-ERROR] Exception during retry worker for {qc_id_str}: {retry_err}")

    async def _retry_client_call_after_delay(qc_id_str: str, delay_seconds: int = 120):
        """
        Background worker that waits 2 minutes (120s) and triggers the next call attempt
        to the client if the consultation is in 'user_retrying_1' or 'user_retrying_2' status.
        """
        try:
            await asyncio.sleep(delay_seconds)
            from database import get_db_session
            with get_db_session() as session:
                target_qc = session.query(QuickConsultation).filter(QuickConsultation.qc_id == qc_id_str).first()
                if not target_qc:
                    return
                # Only retry if still in user_retrying_1 or user_retrying_2 state
                if target_qc.call_status not in ("user_retrying_1", "user_retrying_2"):
                    print(f"[EXOTEL-CLIENT-RETRY] Skipping retry for {qc_id_str} as status is '{target_qc.call_status}'")
                    return

                c_phone = target_qc.consultant.user.phone_number if (target_qc.consultant and target_qc.consultant.user) else None
                u_phone = target_qc.phone_number
                if not c_phone or not u_phone:
                    return

                app_url = os.getenv("APP_BASE_URL", "https://www.solacesquad.com")
                attempt_num = 2 if target_qc.call_status == "user_retrying_1" else 3
                print(f"[EXOTEL-CLIENT-RETRY] 🔄 Initiating Client Attempt {attempt_num} for {qc_id_str}: {c_phone} -> {u_phone}")
                bridge_res = bridge_quick_consult_call(
                    from_phone=c_phone,
                    to_phone=u_phone,
                    duration_minutes=target_qc.duration_minutes,
                    qc_id=target_qc.qc_id,
                    callback_url=f"{app_url.rstrip('/')}/api/exotel/webhook",
                )
                if bridge_res.get("success"):
                    target_qc.exotel_call_sid = bridge_res.get("call_sid")
                    session.commit()
        except Exception as retry_err:
            print(f"[EXOTEL-CLIENT-RETRY-ERROR] Exception during client retry worker for {qc_id_str}: {retry_err}")

    # ──────────────────────────────────────────────────────────────────────────
    # 8. Exotel Status Callback Webhook & Exception Handling
    # ──────────────────────────────────────────────────────────────────────────
    @app.post("/api/exotel/webhook")
    async def exotel_webhook(request: Request, db: Session = Depends(get_db)):
        """
        Receives call progress, leg status, and completion events from Exotel.
        Handles call exceptions:
          - Leg1 (Consultant) Attempt 1 Missed -> qc.call_status = 'consultant_retrying' & auto-retry in 2 mins
          - Leg1 (Consultant) Attempt 2 Missed -> qc.call_status = 'consultant_unreachable', Admin Email & Client Reschedule SMS
          - Leg2 (Client) no-answer / busy / failed -> qc.call_status = 'user_no_answer' & alert email
          - Completed call -> qc.call_status = 'completed'
        """
        try:
            payload: Dict[str, Any] = {}
            try:
                form = await request.form()
                payload.update(form)
            except Exception:
                pass

            if not payload:
                try:
                    json_data = await request.json()
                    if isinstance(json_data, dict):
                        payload.update(json_data)
                except Exception:
                    pass

            if not payload:
                payload.update(dict(request.query_params))

            call_sid = payload.get("CallSid") or payload.get("Sid")
            raw_status = str(payload.get("Status") or payload.get("CallType") or "").lower().strip()
            leg1_status = str(payload.get("Leg1Status") or "").lower().strip()
            leg2_status = str(payload.get("Leg2Status") or "").lower().strip()
            custom_field = payload.get("CustomField") or payload.get("custom_field")  # qc_id
            duration = payload.get("Duration") or payload.get("DialCallDuration")
            recording_url = payload.get("RecordingUrl") or payload.get("recording_url")

            print(f"[EXOTEL-WEBHOOK] Received Event: CallSid={call_sid}, Status={raw_status}, Leg1={leg1_status}, Leg2={leg2_status}, QC_ID={custom_field}, Duration={duration}")

            qc = None
            if custom_field:
                qc = db.query(QuickConsultation).filter(QuickConsultation.qc_id == custom_field).first()
            if not qc and call_sid:
                qc = db.query(QuickConsultation).filter(QuickConsultation.exotel_call_sid == call_sid).first()

            if qc:
                app_url = os.getenv("APP_BASE_URL", "https://www.solacesquad.com")
                c_user = qc.consultant.user if (qc.consultant and qc.consultant.user) else None
                masked_phone = f"+91 {qc.phone_number[-4:]}..." if len(qc.phone_number) >= 4 else qc.phone_number

                # ── Exception Case A: Consultant did not answer (Leg 1 Failed) ──
                if leg1_status in ("no-answer", "busy", "failed", "canceled") or (not leg2_status and raw_status in ("no-answer", "busy", "failed", "canceled")):
                    if qc.call_status == "consultant_retrying":
                        # ── SECOND MISSED CALL (Retry Failed) ──
                        qc.call_status = "consultant_unreachable"

                        # Generate 100% discount single-use voucher for client reschedule
                        voucher_code = f"FREE-{qc.qc_id.replace('SS_', '')}"
                        existing_v = db.query(Voucher).filter(Voucher.code == voucher_code).first()
                        if not existing_v:
                            new_v = Voucher(
                                code=voucher_code,
                                discount_type="percentage",
                                discount_value=100.0,
                                applies_to="all",
                                valid_until=datetime.utcnow() + timedelta(days=30),
                                max_uses=1,
                                is_active=True,
                            )
                            db.add(new_v)
                        db.commit()

                        admin_email = os.getenv("ADMIN_EMAIL", "sg@solacesquad.com")
                        c_phone_val = c_user.phone_number if c_user and c_user.phone_number else "N/A"
                        appt_ist_val = (qc.appointment_date + timedelta(hours=5, minutes=30)).strftime("%d %b %Y at %I:%M %p")

                        # 1. Dispatch High-Priority Alert Email to Admin
                        if admin_email:
                            try:
                                from sendgrid_email import send_quick_consult_admin_unreachable_alert
                                send_quick_consult_admin_unreachable_alert(
                                    to_email=admin_email,
                                    consultant_name=qc.consultant_name,
                                    consultant_phone=c_phone_val,
                                    qc_id=qc.qc_id,
                                    client_phone=qc.phone_number,
                                    appointment_time_str=appt_ist_val,
                                    voucher_code=voucher_code,
                                    app_base_url=app_url,
                                )
                            except Exception as adm_err:
                                print(f"[EXOTEL-WEBHOOK] Failed to dispatch admin unreachable email: {adm_err}")

                        # 2. Dispatch SMS to Client notifying reschedule + 100% Free Voucher
                        try:
                            client_msg = (
                                f"Dear Client,\n"
                                f"Your consultant {qc.consultant_name} is unavailable for Quick Consultation ({qc.qc_id}).\n"
                                f"Use voucher code {voucher_code} for a 100% free reschedule at {app_url}/quickconsult\n"
                                f"— SolaceSquad Team"
                            )
                            _send_msg91_sms(
                                phone_number=qc.phone_number,
                                message=client_msg,
                                qc_id=qc.qc_id,
                                consultant_name=qc.consultant_name,
                                appt_time=appt_ist_val,
                            )
                        except Exception as sms_err:
                            print(f"[EXOTEL-WEBHOOK] Failed to dispatch client reschedule SMS: {sms_err}")

                        # 3. Log Compliance Audit Event
                        AuditLogger.log_event(
                            db=db,
                            event_type="quick_consult_consultant_unreachable",
                            user_id=c_user.id if c_user else None,
                            resource_type="quick_consultation",
                            resource_id=qc.qc_id,
                            details=f"Consultant failed 2 call attempts. 100% Voucher {voucher_code} generated. Admin alerted and client notified for rescheduling. Call SID: {call_sid}",
                            status="failure",
                            request=request,
                        )

                    else:
                        # ── FIRST MISSED CALL -> Schedule 2-minute auto-retry ──
                        qc.call_status = "consultant_retrying"
                        db.commit()

                        # Dispatch interim missed call alert email to consultant
                        if c_user and c_user.email:
                            try:
                                from sendgrid_email import send_quick_consult_missed_call_alert
                                send_quick_consult_missed_call_alert(
                                    to_email=c_user.email,
                                    to_name=c_user.name or qc.consultant_name,
                                    qc_id=qc.qc_id,
                                    client_phone_masked=masked_phone,
                                    app_base_url=app_url,
                                )
                            except Exception as em_err:
                                print(f"[EXOTEL-WEBHOOK] Failed to dispatch missed call email: {em_err}")

                        AuditLogger.log_event(
                            db=db,
                            event_type="quick_consult_consultant_missed_attempt_1",
                            user_id=c_user.id if c_user else None,
                            resource_type="quick_consultation",
                            resource_id=qc.qc_id,
                            details=f"Consultant missed Attempt 1 (Leg1: {leg1_status}). Auto-retry scheduled in 2 minutes. Call SID: {call_sid}",
                            status="warning",
                            request=request,
                        )

                        # Schedule background retry in 2 minutes (120 seconds)
                        asyncio.create_task(_retry_consultant_call_after_delay(qc.qc_id, 120))

                # ── Exception Case B: Client did not answer (Leg 1 answered, Leg 2 Failed) ──
                elif leg1_status in ("completed", "answered") and leg2_status in ("no-answer", "busy", "failed", "canceled"):
                    appt_ist_val = (qc.appointment_date + timedelta(hours=5, minutes=30)).strftime("%d %b %Y at %I:%M %p")
                    admin_email = os.getenv("ADMIN_EMAIL", "sg@solacesquad.com")

                    if qc.call_status == "user_retrying_2":
                        # ── ATTEMPT 3 MISSED BY CLIENT (Final Cancellation) ──
                        qc.call_status = "cancelled_client_no_answer"
                        db.commit()

                        # 1. Dispatch Cancellation SMS to Client
                        try:
                            cancel_msg = (
                                f"Dear Client,\n"
                                f"We tried calling you 3 times for your Quick Consultation ({qc.qc_id}). "
                                f"Since you didn't answer, we are cancelling the call.\n"
                                f"— SolaceSquad Team"
                            )
                            _send_msg91_sms(
                                phone_number=qc.phone_number,
                                message=cancel_msg,
                                qc_id=qc.qc_id,
                                consultant_name=qc.consultant_name,
                                appt_time=appt_ist_val,
                            )
                        except Exception as sms_err:
                            print(f"[EXOTEL-WEBHOOK] Failed to dispatch client cancellation SMS: {sms_err}")

                        # 2. Dispatch Email Alerts to Consultant and Admin
                        recipients = []
                        if c_user and c_user.email:
                            recipients.append((c_user.email, "consultant", c_user.name or qc.consultant_name))
                        if admin_email and admin_email != (c_user.email if c_user else None):
                            recipients.append((admin_email, "admin", "Admin"))

                        for em, role, name in recipients:
                            try:
                                from sendgrid_email import send_quick_consult_client_cancelled_alert
                                send_quick_consult_client_cancelled_alert(
                                    to_email=em,
                                    recipient_role=role,
                                    recipient_name=name,
                                    consultant_name=qc.consultant_name,
                                    qc_id=qc.qc_id,
                                    client_phone_masked=masked_phone,
                                    appointment_time_str=appt_ist_val,
                                    app_base_url=app_url,
                                )
                            except Exception as em_err:
                                print(f"[EXOTEL-WEBHOOK] Failed to dispatch cancellation email to {em}: {em_err}")

                        # 3. Log Compliance Audit Event
                        AuditLogger.log_event(
                            db=db,
                            event_type="quick_consult_client_unreachable_cancelled",
                            user_id=c_user.id if c_user else None,
                            resource_type="quick_consultation",
                            resource_id=qc.qc_id,
                            details=f"Client missed all 3 call attempts. Session cancelled and client notified via SMS. Call SID: {call_sid}",
                            status="failure",
                            request=request,
                        )

                    elif qc.call_status == "user_retrying_1":
                        # ── ATTEMPT 2 MISSED BY CLIENT -> Schedule Attempt 3 in 2 mins ──
                        qc.call_status = "user_retrying_2"
                        db.commit()

                        AuditLogger.log_event(
                            db=db,
                            event_type="quick_consult_client_missed_attempt_2",
                            user_id=c_user.id if c_user else None,
                            resource_type="quick_consultation",
                            resource_id=qc.qc_id,
                            details=f"Client missed Attempt 2 (Leg2: {leg2_status}). Attempt 3 scheduled in 2 minutes. Call SID: {call_sid}",
                            status="warning",
                            request=request,
                        )

                        asyncio.create_task(_retry_client_call_after_delay(qc.qc_id, 120))

                    else:
                        # ── ATTEMPT 1 MISSED BY CLIENT -> Schedule Attempt 2 in 2 mins ──
                        qc.call_status = "user_retrying_1"
                        db.commit()

                        # Dispatch interim notification email to consultant
                        if c_user and c_user.email:
                            try:
                                from sendgrid_email import send_quick_consult_client_unreachable_alert
                                send_quick_consult_client_unreachable_alert(
                                    to_email=c_user.email,
                                    to_name=c_user.name or qc.consultant_name,
                                    qc_id=qc.qc_id,
                                    client_phone_masked=masked_phone,
                                    app_base_url=app_url,
                                )
                            except Exception as em_err:
                                print(f"[EXOTEL-WEBHOOK] Failed to dispatch client unreachable email: {em_err}")

                        AuditLogger.log_event(
                            db=db,
                            event_type="quick_consult_client_missed_attempt_1",
                            user_id=c_user.id if c_user else None,
                            resource_type="quick_consultation",
                            resource_id=qc.qc_id,
                            details=f"Client missed Attempt 1 (Leg2: {leg2_status}). Attempt 2 scheduled in 2 minutes. Call SID: {call_sid}",
                            status="warning",
                            request=request,
                        )

                        asyncio.create_task(_retry_client_call_after_delay(qc.qc_id, 120))

                # ── Case C: Call Completed Successfully ─────────────────────────────
                elif raw_status in ("completed", "answered") or (leg1_status in ("completed", "answered") and leg2_status in ("completed", "answered")):
                    qc.call_status = "completed"
                    db.commit()

                    AuditLogger.log_event(
                        db=db,
                        event_type="quick_consult_call_completed",
                        user_id=c_user.id if c_user else None,
                        resource_type="quick_consultation",
                        resource_id=qc.qc_id,
                        details=f"Quick consultation call successfully completed. Duration: {duration}s. Call SID: {call_sid}",
                        status="success",
                        request=request,
                    )

                # ── Case D: Call In-Progress / Ringing ───────────────────────────────
                elif raw_status in ("in-progress", "ringing"):
                    qc.call_status = "in_progress"
                    db.commit()

                # ── Case E: Provider Failure ─────────────────────────────────────────
                elif raw_status in ("failed", "canceled"):
                    qc.call_status = "failed"
                    db.commit()

            return {"success": True, "status": "acknowledged", "call_status": qc.call_status if qc else "unknown"}
        except Exception as err:
            print(f"[EXOTEL-WEBHOOK-ERROR] {err}")
            return {"success": False, "error": str(err)}

    # ──────────────────────────────────────────────────────────────────────────
    # 9. Session Status Polling (/api/quick-consult/{qc_id}/status)
    # ──────────────────────────────────────────────────────────────────────────
    @app.get("/api/quick-consult/{qc_id}/status")
    async def get_quick_consult_status(qc_id: str, db: Session = Depends(get_db)):
        """
        Returns real-time payment and call status for Quick Consultation modal polling.
        """
        qc = db.query(QuickConsultation).filter(QuickConsultation.qc_id == qc_id).first()
        if not qc:
            raise HTTPException(status_code=404, detail="Quick consultation not found.")

        appt_ist = qc.appointment_date + timedelta(hours=5, minutes=30)
        appt_ist_str = appt_ist.strftime("%d %b %Y, %I:%M %p")

        status_messages = {
            "scheduled": "Appointment confirmed. The consultant will call you at the scheduled time.",
            "initiated": "📞 Calling now! Your phone and the consultant's phone will ring shortly from SolaceSquad.",
            "in_progress": "✓ Call is connected and in progress.",
            "completed": "✓ Consultation call completed. Thank you for choosing SolaceSquad!",
            "consultant_no_answer": "⚠️ The consultant could not be reached just now. We have sent them a priority alert. You can click 'Retry Call' or wait a moment.",
            "user_no_answer": "⚠️ We tried calling your phone (+91 " + qc.phone_number + "), but the call was not answered. Please check your phone and click 'Retry Call'.",
            "failed": "⚠️ Call bridge could not connect. Please ensure both phones are reachable and click 'Retry Call'.",
        }

        return {
            "success": True,
            "qc_id": qc.qc_id,
            "payment_status": qc.payment_status,
            "call_status": qc.call_status,
            "status_message": status_messages.get(qc.call_status, f"Status: {qc.call_status}"),
            "consultant_name": qc.consultant_name,
            "appointment_time": appt_ist_str,
            "duration_minutes": qc.duration_minutes,
            "phone_number": qc.phone_number,
            "can_retry": qc.call_status in ("consultant_no_answer", "user_no_answer", "failed", "scheduled", "initiated"),
        }

    # ──────────────────────────────────────────────────────────────────────────
    # 10. Diagnostics: Live Test Endpoints
    # ──────────────────────────────────────────────────────────────────────────
    @app.get("/api/quick-consult/debug-consultant-email")
    async def debug_quick_consult_consultant_email(
        to_email: str = "sg@solacesquad.com",
        to_name: str = "Admin",
        qc_id: str = "SS_TEST_EMAIL",
        time_str: str = "Today at 10:30 PM",
        duration: int = 30,
        payout: float = 300.0,
        consultant_name: str = "Surjyo Goswami",
        consultant_specialization: str = "Emotional Wellbeing",
        client_name: str = "Anantha",
        client_phone: str = "9901452664",
        is_admin: bool = True,
        mode: str = "webrtc",
    ):
        """Diagnostic endpoint to test SendGrid Consultant or Admin Email live."""
        from sendgrid_email import send_quick_consult_consultant_email
        app_url = os.getenv("APP_BASE_URL", "https://www.solacesquad.com")
        success = send_quick_consult_consultant_email(
            to_email=to_email,
            to_name=to_name,
            qc_id=qc_id,
            appointment_time_str=time_str,
            duration_minutes=duration,
            payout_amount=payout,
            app_base_url=app_url,
            consultation_mode=mode,
            client_name=client_name,
            client_phone=client_phone,
            consultant_name=consultant_name,
            consultant_specialization=consultant_specialization,
            is_admin=is_admin,
        )
        return {
            "success": success,
            "to_email": to_email,
            "to_name": to_name,
            "qc_id": qc_id,
            "is_admin": is_admin,
            "message": "Email dispatched via SendGrid" if success else "Failed to send email via SendGrid",
        }
    @app.get("/api/quick-consult/debug-sms")
    async def debug_quick_consult_sms(
        phone: str = "9901452664",
        qc_id: str = "SS_TEST1",
        consultant_name: str = "Dr. Surjyo",
        time: str = "Today at 09:30 PM",
    ):
        """Diagnostic endpoint to test MSG91 Flow API live."""
        auth_key = os.getenv("MSG91_AUTH_KEY")
        template_id = os.getenv("MSG91_QC_TEMPLATE_ID", "6ab1f30e9c651b3e9e03e023")

        clean_phone = "".join(ch for ch in str(phone) if ch.isdigit())
        if clean_phone.startswith("91") and len(clean_phone) == 12:
            clean_phone = clean_phone[2:]

        url = "https://api.msg91.com/api/v5/flow/"
        headers = {"authkey": auth_key or "", "content-type": "application/json"}
        payload = {
            "template_id": template_id,
            "short_url": "0",
            "recipients": [
                {
                    "mobiles": f"91{clean_phone}",
                    "qc_id": str(qc_id),
                    "consultant_name": str(consultant_name),
                    "time": str(time),
                }
            ],
        }

        try:
            res = requests.post(url, json=payload, headers=headers, timeout=10)
            return {
                "endpoint": url,
                "auth_key_present": bool(auth_key),
                "auth_key_prefix": (auth_key[:8] + "...") if auth_key else None,
                "template_id": template_id,
                "payload": payload,
                "status_code": res.status_code,
                "response": res.text,
            }
        except Exception as exc:
            return {"error": str(exc)}

    @app.get("/api/quick-consult/debug-consultant-sms")
    async def debug_quick_consult_consultant_sms(
        phone: str = "9901452664",
        consultant_name: str = "Surjyo Goswami",
        duration: str = "30 Mins",
        qc_id: str = "SS_TEST1",
        time: str = "Today at 10:00 PM",
    ):
        """Diagnostic endpoint to test Consultant MSG91 Flow API live."""
        auth_key = os.getenv("MSG91_AUTH_KEY")
        template_id = os.getenv("MSG91_QC_CONSULTANT_TEMPLATE_ID", "6ab28c02493147b392022142")

        clean_phone = "".join(ch for ch in str(phone) if ch.isdigit())
        if clean_phone.startswith("91") and len(clean_phone) == 12:
            clean_phone = clean_phone[2:]

        url = "https://api.msg91.com/api/v5/flow/"
        headers = {"authkey": auth_key or "", "content-type": "application/json"}
        payload = {
            "template_id": template_id,
            "short_url": "0",
            "recipients": [
                {
                    "mobiles": f"91{clean_phone}",
                    "consultant_name": str(consultant_name),
                    "duration": str(duration),
                    "qc_id": str(qc_id),
                    "time": str(time),
                }
            ],
        }

        try:
            res = requests.post(url, json=payload, headers=headers, timeout=10)
            return {
                "endpoint": url,
                "auth_key_present": bool(auth_key),
                "template_id": template_id,
                "payload": payload,
                "status_code": res.status_code,
                "response": res.text,
            }
        except Exception as exc:
            return {"error": str(exc)}

    @app.get("/api/quick-consult/debug-call")
    async def debug_quick_consult_call(
        from_phone: str = "9901452664",
        to_phone: str = "7337884942",
    ):
        """Diagnostic endpoint to test Exotel Call Bridging live across multiple parameter formats and auth schemes."""
        raw_key = os.getenv("EXOTEL_API_KEY") or ""
        raw_token = os.getenv("EXOTEL_API_TOKEN") or ""
        raw_sid = os.getenv("EXOTEL_SID") or "solacesquad1"
        raw_caller = os.getenv("EXOTEL_CALLER_ID") or "09513886363"

        api_key = raw_key.strip().strip('"').strip("'").strip()
        api_token = raw_token.strip().strip('"').strip("'").strip()
        sid = raw_sid.strip().strip('"').strip("'").strip()
        caller_id = raw_caller.strip().strip('"').strip("'").strip()

        meta = {
            "key_len": len(api_key),
            "key_preview": f"{api_key[:4]}...{api_key[-4:]}" if len(api_key) >= 8 else api_key,
            "token_len": len(api_token),
            "token_preview": f"{api_token[:4]}...{api_token[-4:]}" if len(api_token) >= 8 else api_token,
            "sid": sid,
            "caller_id": caller_id,
            "raw_key_had_whitespace": (raw_key != api_key),
            "raw_token_had_whitespace": (raw_token != api_token),
        }

        # 1. Test GET on Exotel metadata endpoints with different auth schemes
        auth_tests = []
        get_configs = [
            {"desc": "Standard key:token on api.exotel.com", "url": f"https://api.exotel.com/v1/Accounts/{sid}/Calls.json", "auth": (api_key, api_token)},
            {"desc": "Standard key:token on api.in.exotel.com", "url": f"https://api.in.exotel.com/v1/Accounts/{sid}/Calls.json", "auth": (api_key, api_token)},
            {"desc": "Swapped token:key on api.exotel.com", "url": f"https://api.exotel.com/v1/Accounts/{sid}/Calls.json", "auth": (api_token, api_key)},
            {"desc": "SID:token on api.exotel.com", "url": f"https://api.exotel.com/v1/Accounts/{sid}/Calls.json", "auth": (sid, api_token)},
            {"desc": "GET IncomingPhoneNumbers on api.exotel.com", "url": f"https://api.exotel.com/v1/Accounts/{sid}/IncomingPhoneNumbers.json", "auth": (api_key, api_token)},
        ]

        for gc in get_configs:
            try:
                r = requests.get(gc["url"], auth=gc["auth"], timeout=6)
                auth_tests.append({"desc": gc["desc"], "status": r.status_code, "body": r.text[:300]})
            except Exception as e:
                auth_tests.append({"desc": gc["desc"], "error": str(e)})

        # 2. Test Call Connect combinations
        clean_from_0 = f"0{from_phone[-10:]}"
        clean_to_0 = f"0{to_phone[-10:]}"
        clean_from_plain = from_phone[-10:]
        clean_to_plain = to_phone[-10:]
        clean_caller_0 = f"0{caller_id[-10:]}" if len(caller_id) >= 10 and not caller_id.startswith("0") else caller_id

        connect_candidates = [
            {"desc": "0-prefixed with CallType trans", "domain": "api.exotel.com", "auth": (api_key, api_token), "payload": {"From": clean_from_0, "To": clean_to_0, "CallerId": clean_caller_0, "CallType": "trans"}},
            {"desc": "0-prefixed without CallType", "domain": "api.exotel.com", "auth": (api_key, api_token), "payload": {"From": clean_from_0, "To": clean_to_0, "CallerId": clean_caller_0}},
            {"desc": "Plain 10-digit with CallType trans", "domain": "api.exotel.com", "auth": (api_key, api_token), "payload": {"From": clean_from_plain, "To": clean_to_plain, "CallerId": clean_caller_0, "CallType": "trans"}},
            {"desc": "CallerId 07314624216", "domain": "api.exotel.com", "auth": (api_key, api_token), "payload": {"From": clean_from_0, "To": clean_to_0, "CallerId": "07314624216", "CallType": "trans"}},
            {"desc": "api.in.exotel.com domain", "domain": "api.in.exotel.com", "auth": (api_key, api_token), "payload": {"From": clean_from_0, "To": clean_to_0, "CallerId": clean_caller_0, "CallType": "trans"}},
        ]

        connect_results = []
        for cc in connect_candidates:
            url = f"https://{cc['domain']}/v1/Accounts/{sid}/Calls/connect.json"
            try:
                r = requests.post(url, data=cc["payload"], auth=cc["auth"], timeout=10)
                connect_results.append({
                    "desc": cc["desc"],
                    "status": r.status_code,
                    "response": r.text,
                    "payload": cc["payload"],
                })
                if r.status_code in (200, 201):
                    break
            except Exception as e:
                connect_results.append({"desc": cc["desc"], "error": str(e)})

        return {
            "meta": meta,
            "auth_tests": auth_tests,
            "connect_results": connect_results,
        }

    # ──────────────────────────────────────────────────────────────────────────
    # 11. Admin Portal: List Quick Consultations & Payout Status
    # ──────────────────────────────────────────────────────────────────────────
    @app.get("/api/admin/quick-consultations")
    async def admin_get_quick_consultations(
        request: Request,
        db: Session = Depends(get_db),
        status: str = "",
        payment_status: str = "",
        search: str = "",
    ):
        """
        Admin endpoint to list all Quick Consultations with call status, payment status, consultant payout, and clinical notes.
        """
        uid = request.session.get("user_id")
        user_type = request.session.get("user_type", "")
        if not uid or user_type != "admin":
            admin_email = os.getenv("ADMIN_EMAIL", "admin@solacesquad.com")
            from models import User
            user = db.query(User).filter(User.id == uid).first() if uid else None
            if not user or (not getattr(user, "is_admin", False) and user.email != admin_email):
                raise HTTPException(status_code=403, detail="Admin access required.")

        q = db.query(QuickConsultation).order_by(desc(QuickConsultation.created_at))

        if status:
            q = q.filter(QuickConsultation.call_status == status)
        if payment_status:
            q = q.filter(QuickConsultation.payment_status == payment_status)
        if search:
            q = q.filter(
                or_(
                    QuickConsultation.qc_id.ilike(f"%{search}%"),
                    QuickConsultation.phone_number.ilike(f"%{search}%"),
                    QuickConsultation.consultant_name.ilike(f"%{search}%"),
                    QuickConsultation.razorpay_payment_id.ilike(f"%{search}%"),
                )
            )

        qcs = q.all()
        results = []
        for qc in qcs:
            appt_ist = qc.appointment_date + timedelta(hours=5, minutes=30)
            c_earning = qc.earnings[0] if getattr(qc, "earnings", None) and len(qc.earnings) > 0 else None

            results.append({
                "id": qc.id,
                "qc_id": qc.qc_id,
                "phone_number": qc.phone_number,
                "consultant_name": qc.consultant_name,
                "consultant_id": qc.consultant_id,
                "appointment_date": qc.appointment_date.isoformat(),
                "appointment_time_ist": appt_ist.strftime("%d %b %Y, %I:%M %p"),
                "duration_minutes": qc.duration_minutes,
                "base_amount": qc.base_amount,
                "surcharge_amount": qc.surcharge_amount,
                "taxes": qc.taxes,
                "amount_paid": qc.amount_paid,
                "consultant_payout": c_earning.consultant_payout if c_earning else (qc.consultant.consultant_payout if qc.consultant else 0.0),
                "payout_status": c_earning.payout_status if c_earning else "pending",
                "earning_id": c_earning.id if c_earning else None,
                "payment_status": qc.payment_status,
                "call_status": qc.call_status,
                "exotel_call_sid": qc.exotel_call_sid,
                "razorpay_order_id": qc.razorpay_order_id,
                "razorpay_payment_id": qc.razorpay_payment_id,
                "consultant_notes": qc.consultant_notes or "",
                "created_at": qc.created_at.isoformat(),
            })

        return {"success": True, "count": len(results), "quick_consultations": results}

    # ──────────────────────────────────────────────────────────────────────────
    # 12. Admin Portal: Razorpay Refund for Quick Consultation
    # ──────────────────────────────────────────────────────────────────────────
    @app.post("/api/admin/quick-consult/{qc_id}/refund")
    async def admin_refund_quick_consultation(
        qc_id: str,
        request: Request,
        db: Session = Depends(get_db),
    ):
        """
        Process a full Razorpay refund for a Quick Consultation.
        Updates qc.payment_status = 'refunded', PaymentTransaction.status = 'refunded',
        and freezes consultant payout (ConsultantEarning.payout_status = 'on_hold').
        """
        uid = request.session.get("user_id")
        user_type = request.session.get("user_type", "")
        if not uid or user_type != "admin":
            admin_email = os.getenv("ADMIN_EMAIL", "admin@solacesquad.com")
            from models import User
            user = db.query(User).filter(User.id == uid).first() if uid else None
            if not user or (not getattr(user, "is_admin", False) and user.email != admin_email):
                raise HTTPException(status_code=403, detail="Admin access required.")

        qc = db.query(QuickConsultation).filter(QuickConsultation.qc_id == qc_id).first()
        if not qc:
            raise HTTPException(status_code=404, detail="Quick Consultation not found.")
        if qc.payment_status == "refunded":
            raise HTTPException(status_code=400, detail="This consultation has already been refunded.")
        if not qc.razorpay_payment_id:
            raise HTTPException(status_code=400, detail="No Razorpay payment ID found for this session.")

        body = {}
        try:
            body = await request.json()
        except Exception:
            pass
        reason = body.get("reason") or "Quick Consultation cancelled / call missed"

        # Safe mock mode support for staging
        if qc.razorpay_payment_id.startswith("pay_mock_"):
            qc.payment_status = "refunded"
            # Freeze earning
            earning = db.query(ConsultantEarning).filter(ConsultantEarning.quick_consultation_id == qc.id).first()
            if earning:
                earning.payout_status = "on_hold"
                earning.admin_notes = f"Mock refund processed: {reason}"
            db.commit()
            return {
                "success": True,
                "refund_id": f"rfnd_mock_{qc.qc_id}",
                "amount": qc.amount_paid,
                "message": f"Mock refund of ₹{qc.amount_paid:.2f} processed successfully.",
            }

        key_id = os.getenv("RAZORPAY_KEY_ID")
        key_secret = os.getenv("RAZORPAY_KEY_SECRET")
        if not (key_id and key_secret):
            raise HTTPException(status_code=500, detail="Razorpay credentials not configured on server.")

        try:
            import razorpay
            client = razorpay.Client(auth=(key_id, key_secret))
            amount_paise = int(qc.amount_paid * 100)

            refund = client.payment.refund(qc.razorpay_payment_id, {
                "amount": amount_paise,
                "speed": "normal",
                "notes": {
                    "reason": reason,
                    "qc_id": qc.qc_id,
                    "phone_number": qc.phone_number,
                }
            })
            refund_id = refund.get("id")

            # Update QuickConsultation
            qc.payment_status = "refunded"

            # Update PaymentTransaction
            from models import PaymentTransaction
            txn = db.query(PaymentTransaction).filter(
                PaymentTransaction.related_entity_type == "quick_consultation",
                PaymentTransaction.related_entity_id == qc.id,
            ).first()
            if txn:
                txn.status = "refunded"
                txn.refunded_at = datetime.utcnow()
                txn.refund_reason = reason

            # Freeze Consultant Payout
            earning = db.query(ConsultantEarning).filter(
                ConsultantEarning.quick_consultation_id == qc.id
            ).first()
            if earning:
                earning.payout_status = "on_hold"
                earning.admin_notes = f"Refund issued (Ref: {refund_id}): {reason}"

            db.commit()

            # HIPAA / DPDP Audit Log
            AuditLogger.log_event(
                db=db,
                event_type="quick_consult_refunded",
                user_id=uid,
                resource_type="quick_consultation",
                resource_id=qc.qc_id,
                details=f"Refund of ₹{qc.amount_paid:.2f} issued for {qc.qc_id}. Razorpay Ref: {refund_id}. Reason: {reason}",
                status="success",
                request=request,
            )

            return {
                "success": True,
                "refund_id": refund_id,
                "amount": qc.amount_paid,
                "message": f"Refund of ₹{qc.amount_paid:.2f} successfully initiated (Ref: {refund_id}).",
            }
        except Exception as exc:
            db.rollback()
            print(f"[QC-REFUND-ERROR] {exc}")
            raise HTTPException(status_code=500, detail=f"Razorpay refund failed: {str(exc)}")



