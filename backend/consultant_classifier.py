"""
consultant_classifier.py — Wellness category classifier + Emora recommendation engine
======================================================================================
Provides:
  classify_consultant(profile)                  → 'Mental' | 'Physical' | 'Professional'
  detect_intent(message)                        → SOS / explicit request / recommended category
  get_earliest_slot(consultant, db)             → human-readable next available slot
  get_recommended_consultants(category, db)     → list of consultant dicts
  format_consultant_context(consultants, …)     → context string injected into Emora prompt
"""
from datetime import datetime, timedelta, date, time as dtime
import json

# ─────────────────────────────────────────────────────────────────────────────
# 1. KEYWORD MAPS FOR AUTO-CLASSIFICATION
# ─────────────────────────────────────────────────────────────────────────────
MENTAL_KEYWORDS = {
    "anxiety", "anxious", "depression", "depressed", "mental health",
    "counselling", "counseling", "therapy", "therapist", "cbt", "dbt", "rebt",
    "trauma", "ptsd", "ocd", "bipolar", "stress", "panic", "grief", "emotional",
    "mindfulness", "self-harm", "suicide", "crisis", "mood", "phobia",
    "psychotherapy", "psychological", "wellbeing", "emotional wellbeing",
    "mental", "insomnia", "sleep disorder", "addiction", "behavioural",
}

PHYSICAL_KEYWORDS = {
    "nutrition", "nutritionist", "dietitian", "diet", "fitness", "physiotherapy",
    "physiotherapist", "exercise", "weight", "yoga", "pilates", "lifestyle",
    "chronic pain", "breathing", "rehabilitation", "physical health",
    "sports", "sleep", "posture", "ergonomics", "strength", "cardio",
    "physical wellness", "health coach", "wellness coach", "body", "massage",
}

PROFESSIONAL_KEYWORDS = {
    "career", "leadership", "executive", "work-life", "performance",
    "productivity", "professional", "coaching", "job", "workplace",
    "interview", "resume", "management", "entrepreneur", "business",
    "corporate", "professional development", "work stress",
    "professional wellness", "professional coaching", "burnout coaching",
}


def classify_consultant(profile) -> str:
    """Auto-classify a ConsultantProfile → 'Mental' | 'Physical' | 'Professional'."""
    parts = []
    if profile.specialization:
        parts.append(profile.specialization.lower())
    if profile.bio:
        parts.append(profile.bio.lower())
    if profile.expertise_areas:
        try:
            areas = json.loads(profile.expertise_areas)
            parts.extend([a.lower() for a in areas if isinstance(a, str)])
        except Exception:
            parts.append(profile.expertise_areas.lower())
    if profile.counselling_methods:
        try:
            methods = json.loads(profile.counselling_methods)
            parts.extend([m.lower() for m in methods if isinstance(m, str)])
        except Exception:
            parts.append(profile.counselling_methods.lower())

    text = " ".join(parts)
    scores = {
        "Mental":       sum(1 for kw in MENTAL_KEYWORDS       if kw in text),
        "Physical":     sum(1 for kw in PHYSICAL_KEYWORDS     if kw in text),
        "Professional": sum(1 for kw in PROFESSIONAL_KEYWORDS if kw in text),
    }
    # Highest score wins; Mental is default on tie/zero
    best = max(scores, key=lambda k: (scores[k], k == "Mental"))
    return best


def bulk_classify(db) -> int:
    """Classify ALL consultants without a wellness_category. Returns count updated."""
    from models import ConsultantProfile
    unclassified = db.query(ConsultantProfile).filter(
        ConsultantProfile.wellness_category.is_(None)
    ).all()
    for p in unclassified:
        p.wellness_category = classify_consultant(p)
    if unclassified:
        db.commit()
    return len(unclassified)


# ─────────────────────────────────────────────────────────────────────────────
# 2. SOS / INTENT DETECTION
# ─────────────────────────────────────────────────────────────────────────────
# Proactive SOS triggers (emotional crisis / severe distress)
SOS_PHRASES = [
    "want to die", "kill myself", "end my life", "can't go on", "cannot go on",
    "no reason to live", "hopeless", "worthless", "suicidal", "self harm",
    "self-harm", "hurt myself", "falling apart", "losing my mind",
    "panic attack", "severe anxiety", "severe depression", "can't function",
    "cannot function", "can't cope", "cannot cope", "complete breakdown",
    "mental breakdown", "breaking down", "want to end it",
    "can't take it anymore", "cannot take it anymore", "i give up",
    "totally burnt out", "complete burnout", "career crisis",
    "eating disorder", "anorexia", "bulimia", "chronic pain unbearable",
    "unbearable pain",
]

# Explicit user request for a consultant
EXPLICIT_PHRASES = [
    "suggest a consultant", "recommend a consultant", "find a consultant",
    "book a consultant", "book an appointment", "book a session",
    "need a therapist", "need a consultant", "suggest a therapist",
    "who can help me", "talk to someone", "see someone professional",
    "schedule a session", "schedule an appointment", "find me a therapist",
    "recommend someone", "suggest someone",
]

# Category signals in user messages
MENTAL_SIGNALS    = {"anxious", "anxiety", "depressed", "depression", "stressed",
                     "panic", "trauma", "grief", "sad", "lonely", "overwhelmed",
                     "ocd", "ptsd", "mood", "mental", "emotional", "burnout",
                     "therapist", "therapy", "counsellor", "counselor"}

PHYSICAL_SIGNALS  = {"fitness", "diet", "nutrition", "weight", "exercise", "pain",
                     "sleep", "physiotherapy", "posture", "yoga", "lifestyle",
                     "health", "physical", "chronic", "fatigue"}

PROFESSIONAL_SIGNALS = {"career", "job", "work", "professional", "leadership",
                        "productivity", "interview", "business", "corporate",
                        "performance", "burnout", "fired", "laid off"}


def detect_intent(message: str) -> dict:
    """
    Analyse user message and return:
      is_sos          : bool — severe distress → proactive consultant recommendation
      is_explicit     : bool — user explicitly asked for a consultant
      should_recommend: bool — either of the above
      category        : 'Mental' | 'Physical' | 'Professional' | None
    """
    msg = message.lower()

    is_sos      = any(phrase in msg for phrase in SOS_PHRASES)
    is_explicit = any(phrase in msg for phrase in EXPLICIT_PHRASES)

    mental_score       = sum(1 for s in MENTAL_SIGNALS       if s in msg)
    physical_score     = sum(1 for s in PHYSICAL_SIGNALS     if s in msg)
    professional_score = sum(1 for s in PROFESSIONAL_SIGNALS if s in msg)

    total = mental_score + physical_score + professional_score
    if total == 0:
        category = None
    elif mental_score >= physical_score and mental_score >= professional_score:
        category = "Mental"
    elif physical_score >= professional_score:
        category = "Physical"
    else:
        category = "Professional"

    # SOS with no clear category → default Mental
    if is_sos and not category:
        category = "Mental"

    return {
        "is_sos":           is_sos,
        "is_explicit":      is_explicit,
        "should_recommend": is_sos or is_explicit,
        "category":         category,
    }


# ─────────────────────────────────────────────────────────────────────────────
# 3. EARLIEST AVAILABILITY CALCULATOR
# ─────────────────────────────────────────────────────────────────────────────
def get_earliest_slot(consultant, db, tz_name: str = "Asia/Kolkata") -> str:
    """
    Return human-readable earliest available slot in next 14 days (Local).
    Checks ConsultantSchedule vs existing Appointments status∈{scheduled,pending}.
    """
    from models import Appointment
    import timezone_utils

    now_utc = datetime.utcnow()
    # Schedules are in IST. 
    now_ist = timezone_utils.to_local(now_utc, "Asia/Kolkata")
    today_ist = now_ist.date()

    active_slots = [s for s in (consultant.schedules or []) if s.is_active]
    if not active_slots:
        return "Availability on request"

    future_cutoff_utc = now_utc + timedelta(days=14)
    existing_appts = db.query(Appointment).filter(
        Appointment.consultant_id == consultant.id,
        Appointment.appointment_date >= now_utc,
        Appointment.appointment_date <= future_cutoff_utc,
        Appointment.status.in_(["scheduled", "pending"]),
    ).all()

    # booked_slots: set of (weekday_int, "HH:MM") in IST
    booked_slots = set()
    for appt in existing_appts:
        appt_ist = timezone_utils.to_local(appt.appointment_date, "Asia/Kolkata")
        booked_slots.add((appt_ist.weekday(), appt_ist.strftime("%H:%M")))

    for day_offset in range(14):
        check_date = today_ist + timedelta(days=day_offset)
        weekday = check_date.weekday()

        day_slots = sorted(
            [s for s in active_slots if s.day_of_week == weekday],
            key=lambda s: s.start_time
        )

        for slot in day_slots:
            slot_time_str = slot.start_time  # "HH:MM"
            if (weekday, slot_time_str) in booked_slots:
                continue

            # If today, need at least 1 hour notice
            if day_offset == 0:
                try:
                    sh, sm = map(int, slot_time_str.split(":"))
                    slot_dt = datetime.combine(check_date, dtime(sh, sm))
                    if slot_dt <= now_ist.replace(tzinfo=None) + timedelta(hours=1):
                        continue
                except Exception:
                    pass

            # Format
            try:
                sh, sm = map(int, slot_time_str.split(":"))
                # Combine IST date with IST time
                ist_dt = datetime.combine(check_date, dtime(sh, sm))
                # Convert to target local timezone for the label
                formatted = timezone_utils.format_dt_local(ist_dt, "%I:%M %p", tz_name, src_tz="Asia/Kolkata")
            except Exception:
                formatted = slot_time_str

            # Label (Today/Tomorrow/Date)
            if day_offset == 0:
                # We should check if "Today" is still today in the target timezone
                target_now = timezone_utils.get_now_local(tz_name)
                # This is getting complicated, let's just use the target timezone's date formatting
                label = "Today" 
                # Actually, format_dt_local already handles the heavy lifting if we pass the right format
                full_label = timezone_utils.format_dt_local(ist_dt, "%a, %d %b at %I:%M %p", tz_name, src_tz="Asia/Kolkata")
                # If it's today in target timezone, we can simplify
                if ist_dt.date() == timezone_utils.to_local(now_utc, "Asia/Kolkata").date(): # Simplification
                     pass # keep full_label for now
                return full_label

            label = timezone_utils.format_dt_local(ist_dt, "%a, %d %b at %I:%M %p", tz_name, src_tz="Asia/Kolkata")
            return label

    return "Check availability on the platform"


# ─────────────────────────────────────────────────────────────────────────────
# 4. CONSULTANT RECOMMENDER
# ─────────────────────────────────────────────────────────────────────────────
CATEGORY_EMOJI = {"Mental": "🧠", "Physical": "💪", "Professional": "💼"}


def get_recommended_consultants(category: str, db, limit: int = 3, tz_name: str = "Asia/Kolkata") -> list:
    """
    Return up to `limit` approved+available consultants for a wellness category.
    Falls back to all categories if none found for the specific one.
    """
    from models import ConsultantProfile

    def _query(cat):
        q = db.query(ConsultantProfile).filter(
            ConsultantProfile.is_approved  == True,
            ConsultantProfile.is_available == True,
        )
        if cat:
            q = q.filter(ConsultantProfile.wellness_category == cat)
        return q.order_by(ConsultantProfile.rating.desc()).limit(limit * 2).all()

    consultants = _query(category)
    # Fallback: if none in the specific category, return best across all
    if not consultants and category:
        consultants = _query(None)

    results = []
    for c in consultants:
        name = (c.full_name
                or (c.user.name if c.user else None)
                or "Our Consultant")
        earliest = get_earliest_slot(c, db, tz_name=tz_name)
        results.append({
            "name":          name,
            "category":      c.wellness_category or category or "Wellness",
            "specialization": c.specialization or "Wellness Consultant",
            "earliest_slot": earliest,
            "emoji":         CATEGORY_EMOJI.get(c.wellness_category or category, "⭐"),
        })
        if len(results) >= limit:
            break

    return results


def format_consultant_context(consultants: list, is_sos: bool, category: str) -> str:
    """
    Build the [CONSULTANT_RECOMMENDATION] context block injected before the
    user's message when Emora should recommend consultants.
    """
    if not consultants:
        return ""

    urgency_note = (
        "The user is showing signs of serious distress or a crisis. "
        "Express genuine care first, then warmly guide them toward booking."
        if is_sos else
        "The user is looking for a professional consultant. "
        "Present options clearly and encourage them to book."
    )

    lines = [
        f"[CONSULTANT_RECOMMENDATION: {urgency_note} "
        f"Mention 1–3 of these real SolaceSquad consultants by name in your response. "
        f"Keep it conversational — do NOT use a robotic numbered list. "
        f"Always include their earliest availability and end with an invitation to "
        f"book at /app/consultants]"
    ]
    for c in consultants:
        lines.append(
            f"  • {c['emoji']} {c['name']} ({c['specialization']}) "
            f"— next available: {c['earliest_slot']}"
        )
    lines.append("[END_CONSULTANT_RECOMMENDATION]")
    return "\n".join(lines)
