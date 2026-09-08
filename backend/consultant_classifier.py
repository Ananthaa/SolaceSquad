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
    try:
        unclassified = db.query(ConsultantProfile).filter(
            ConsultantProfile.wellness_category.is_(None)
        ).all()
        for p in unclassified:
            p.wellness_category = classify_consultant(p)
        if unclassified:
            db.commit()
        return len(unclassified)
    except Exception:
        return 0


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
    Enforces minimum 24-hour advance booking for paid appointments.
    """
    try:
        from models import Appointment
        import timezone_utils

        now_utc = datetime.utcnow()
        now_ist = timezone_utils.to_local(now_utc, "Asia/Kolkata")
        today_ist = now_ist.date()

        active_slots = [s for s in (getattr(consultant, "schedules", None) or []) if getattr(s, "is_active", True)]
        if not active_slots:
            return "Availability on request"

        # Paid consultants require at least 24 hours advance notice
        min_booking_ist = now_ist.replace(tzinfo=None) + timedelta(hours=24)

        future_cutoff_utc = now_utc + timedelta(days=14)
        existing_appts = db.query(Appointment).filter(
            Appointment.consultant_id == consultant.id,
            Appointment.appointment_date >= now_utc,
            Appointment.appointment_date <= future_cutoff_utc,
            Appointment.status.in_(["scheduled", "pending"]),
        ).all()

        # booked_slots: set of (date, "HH:MM") in IST
        booked_slots = set()
        for appt in existing_appts:
            if appt.appointment_date:
                try:
                    appt_ist = timezone_utils.to_local(appt.appointment_date, "Asia/Kolkata")
                    booked_slots.add((appt_ist.date(), appt_ist.strftime("%H:%M")))
                except Exception:
                    pass

        # Start search from day_offset = 1 (Tomorrow) up to 14 days ahead
        for day_offset in range(1, 15):
            check_date = today_ist + timedelta(days=day_offset)
            weekday = check_date.weekday()

            day_slots = sorted(
                [s for s in active_slots if s.day_of_week == weekday],
                key=lambda s: s.start_time
            )

            for slot in day_slots:
                slot_time_str = slot.start_time  # "HH:MM"
                if (check_date, slot_time_str) in booked_slots:
                    continue

                try:
                    sh, sm = map(int, slot_time_str.split(":"))
                    slot_dt = datetime.combine(check_date, dtime(sh, sm))
                    if slot_dt < min_booking_ist:
                        continue

                    time_part = slot_dt.strftime("%I:%M %p")
                    days_diff = (check_date - today_ist).days
                    if days_diff == 1:
                        return f"Tomorrow at {time_part}"
                    else:
                        return f"{slot_dt.strftime('%a, %d %b')} at {time_part}"
                except Exception:
                    days_diff = (check_date - today_ist).days
                    if days_diff == 1:
                        return f"Tomorrow at {slot_time_str}"
                    return f"{check_date.strftime('%a, %d %b')} at {slot_time_str}"

        return "Check availability on the platform"
    except Exception as _slot_err:
        print(f"[EarliestSlot] non-fatal error: {_slot_err}")
        return "Availability on request"


# ─────────────────────────────────────────────────────────────────────────────
# 4. CONSULTANT RECOMMENDER
# ─────────────────────────────────────────────────────────────────────────────
CATEGORY_EMOJI = {"Mental": "🧠", "Physical": "💪", "Professional": "💼"}


def get_recommended_consultants(category: str, db, limit: int = 3, tz_name: str = "Asia/Kolkata") -> list:
    """
    Return up to `limit` approved+active consultants for a wellness category.
    Falls back to all categories if none found for the specific one.
    """
    from models import ConsultantProfile, User

    def _query(cat):
        q = db.query(ConsultantProfile, User).join(
            User, User.id == ConsultantProfile.user_id
        ).filter(
            User.user_type == "consultant",
            User.is_active == True,
            ConsultantProfile.is_approved == True,
        )
        if cat:
            q = q.filter(ConsultantProfile.wellness_category == cat)
        return q.order_by(ConsultantProfile.rating.desc(), ConsultantProfile.experience_years.desc()).limit(limit * 2).all()

    consultant_rows = _query(category)
    # Fallback: if none in the specific category, return best across all
    if not consultant_rows and category:
        consultant_rows = _query(None)

    results = []
    for c, user in consultant_rows:
        name = user.name or c.full_name or "Our Consultant"
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
        f"Mention 1–2 of these real SolaceSquad consultants by their exact names below. "
        f"NEVER invent or make up any names not in this list. "
        f"Keep it conversational — do NOT use a robotic numbered list. "
        f"Include their earliest availability and warmly encourage them to connect with them.]"
    ]
    for c in consultants:
        lines.append(
            f"  • {c['emoji']} {c['name']} ({c['specialization']}) "
            f"— next available: {c['earliest_slot']}"
        )
    lines.append("[END_CONSULTANT_RECOMMENDATION]")
    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# 5. 75-KEYWORD TAXONOMY & DATABASE CONSULTANT MATCHER
# ─────────────────────────────────────────────────────────────────────────────
SEARCH_KEYWORD_TAXONOMY = [
    {"keyid": 1,  "term": "Anxiety",                     "focus_areas": ["Anxiety & Panic Attacks"]},
    {"keyid": 2,  "term": "Panic Attacks",               "focus_areas": ["Anxiety & Panic Attacks"]},
    {"keyid": 3,  "term": "Overthinking",                "focus_areas": ["Anxiety & Panic Attacks", "Stress Management"]},
    {"keyid": 4,  "term": "Excessive Worry",             "focus_areas": ["Anxiety & Panic Attacks", "Stress Management"]},
    {"keyid": 5,  "term": "Stress",                      "focus_areas": ["Stress Management"]},
    {"keyid": 6,  "term": "Feeling Overwhelmed",         "focus_areas": ["Stress Management"]},
    {"keyid": 7,  "term": "Feeling Low",                 "focus_areas": ["Depression & Mood Disorders"]},
    {"keyid": 8,  "term": "Sadness",                     "focus_areas": ["Depression & Mood Disorders"]},
    {"keyid": 9,  "term": "Emotionally Drained",         "focus_areas": ["Depression & Mood Disorders"]},
    {"keyid": 10, "term": "Depression",                  "focus_areas": ["Depression & Mood Disorders"]},
    {"keyid": 11, "term": "Mood Problems",               "focus_areas": ["Depression & Mood Disorders"]},
    {"keyid": 12, "term": "Anger Issues",                "focus_areas": ["Anger Management"]},
    {"keyid": 13, "term": "Emotional Regulation",        "focus_areas": ["Anger Management"]},
    {"keyid": 14, "term": "Low Self-esteem",             "focus_areas": ["Low Self-esteem"]},
    {"keyid": 15, "term": "Lack of Confidence",          "focus_areas": ["Low Self-esteem", "Career & Life Coaching"]},
    {"keyid": 16, "term": "Body Image Issues",           "focus_areas": ["Body Image Issues", "Nutrition & Wellness"]},
    {"keyid": 17, "term": "Trauma",                      "focus_areas": ["Abuse & Trauma (including Childhood)", "Abuse & Trauma (incl. Childhood)"]},
    {"keyid": 18, "term": "Difficult Past Experiences",  "focus_areas": ["Abuse & Trauma (including Childhood)", "Abuse & Trauma (incl. Childhood)"]},
    {"keyid": 19, "term": "Grief, Bereavement & Loss",   "focus_areas": ["Grief & Bereavement"]},
    {"keyid": 20, "term": "Crisis Situation",            "focus_areas": ["Crisis Intervention"]},
    {"keyid": 21, "term": "Severe Emotional Distress",   "focus_areas": ["Crisis Intervention"]},
    {"keyid": 22, "term": "Procrastination",             "focus_areas": ["Motivation & Goal Setting"]},
    {"keyid": 23, "term": "Low Motivation",              "focus_areas": ["Motivation & Goal Setting"]},
    {"keyid": 24, "term": "Feeling Stuck",               "focus_areas": ["Motivation & Goal Setting"]},
    {"keyid": 25, "term": "Sleep Problems",              "focus_areas": ["Anxiety & Panic Attacks", "Stress Management"]},
    {"keyid": 26, "term": "Mindfulness",                 "focus_areas": ["Mindfulness & Meditation"]},
    {"keyid": 27, "term": "Managing Thoughts & Emotions","focus_areas": ["Mindfulness & Meditation"]},
    {"keyid": 28, "term": "Addiction",                   "focus_areas": ["Addiction & Substance Use"]},
    {"keyid": 29, "term": "Substance Use",               "focus_areas": ["Addiction & Substance Use"]},
    {"keyid": 30, "term": "Relationship Problems",       "focus_areas": ["Relationship Counselling"]},
    {"keyid": 31, "term": "Breakup",                     "focus_areas": ["Relationship Counselling"]},
    {"keyid": 32, "term": "Separation",                  "focus_areas": ["Relationship Counselling"]},
    {"keyid": 33, "term": "Family Problems & Conflicts", "focus_areas": ["Family Issues / Conflicts"]},
    {"keyid": 34, "term": "Parenting Challenges",        "focus_areas": ["Parenting Challenges"]},
    {"keyid": 35, "term": "Sexual & Intimacy Issues",    "focus_areas": ["Sexual & Intimacy Problems"]},
    {"keyid": 36, "term": "LGBTQIA+",                    "focus_areas": ["LGBTQIA+ Affirmative Counselling"]},
    {"keyid": 37, "term": "Neurodiversity",              "focus_areas": ["Neurodiversity (ADHD, Autism, etc.)"]},
    {"keyid": 38, "term": "ADHD",                        "focus_areas": ["Neurodiversity (ADHD, Autism, etc.)"]},
    {"keyid": 39, "term": "Autism-related Challenges",   "focus_areas": ["Neurodiversity (ADHD, Autism, etc.)"]},
    {"keyid": 40, "term": "Personality-related Difficulties", "focus_areas": ["Personality Disorders"]},
    {"keyid": 41, "term": "Work Stress",                 "focus_areas": ["Work-related Stress"]},
    {"keyid": 42, "term": "Burnout",                     "focus_areas": ["Work-related Stress"]},
    {"keyid": 43, "term": "Work-Life Balance",           "focus_areas": ["Work-life Balance"]},
    {"keyid": 44, "term": "Career Decisions",            "focus_areas": ["Career & Life Coaching"]},
    {"keyid": 45, "term": "Workplace Problems",          "focus_areas": ["Career & Life Coaching", "Work-related Stress"]},
    {"keyid": 46, "term": "Career Growth",               "focus_areas": ["Career & Life Coaching", "Work-related Stress"]},
    {"keyid": 47, "term": "Academic Pressure",           "focus_areas": ["Stress Management"]},
    {"keyid": 48, "term": "Exam Stress",                 "focus_areas": ["Stress Management"]},
    {"keyid": 49, "term": "Performance Anxiety",         "focus_areas": ["Anxiety & Panic Attacks", "Career & Life Coaching"]},
    {"keyid": 50, "term": "Goal Setting",                "focus_areas": ["Motivation & Goal Setting"]},
    {"keyid": 51, "term": "Personal Growth",             "focus_areas": ["Motivation & Goal Setting"]},
    {"keyid": 52, "term": "Life Transitions",            "focus_areas": ["Stress Management"]},
    {"keyid": 53, "term": "Life Changes",                "focus_areas": ["Stress Management"]},
    {"keyid": 54, "term": "Gut Health",                  "focus_areas": ["Nutrition & Wellness"]},
    {"keyid": 55, "term": "Digestive Wellness",          "focus_areas": ["Nutrition & Wellness"]},
    {"keyid": 56, "term": "Weight Management",           "focus_areas": ["Nutrition & Wellness"]},
    {"keyid": 57, "term": "Weight Loss",                 "focus_areas": ["Nutrition & Wellness"]},
    {"keyid": 58, "term": "Nutrition",                   "focus_areas": ["Nutrition & Wellness"]},
    {"keyid": 59, "term": "Physical Fitness",            "focus_areas": ["Physical Fitness & Wellness"]},
    {"keyid": 60, "term": "Yoga",                        "focus_areas": ["Physical Fitness & Wellness", "Mindfulness & Meditation"]},
    {"keyid": 61, "term": "Meditation",                  "focus_areas": ["Mindfulness & Meditation"]},
    {"keyid": 62, "term": "General Physical Wellness",   "focus_areas": ["Physical Fitness & Wellness"]},
    {"keyid": 63, "term": "Loneliness",                  "focus_areas": ["Depression & Mood Disorders"]},
    {"keyid": 64, "term": "Social Isolation",            "focus_areas": ["Depression & Mood Disorders"]},
    {"keyid": 65, "term": "Emotional Exhaustion",        "focus_areas": ["Stress Management", "Work-related Stress"]},
    {"keyid": 66, "term": "Fear & Phobias",              "focus_areas": ["Anxiety & Panic Attacks"]},
    {"keyid": 67, "term": "Obsessive Thoughts",          "focus_areas": ["Depression & Mood Disorders"]},
    {"keyid": 68, "term": "Compulsive Behaviour",        "focus_areas": ["Depression & Mood Disorders"]},
    {"keyid": 69, "term": "Eating-related Concerns",     "focus_areas": ["Nutrition & Wellness", "Body Image Issues"]},
    {"keyid": 70, "term": "Emotional Eating",            "focus_areas": ["Nutrition & Wellness", "Body Image Issues"]},
    {"keyid": 71, "term": "Confidence Issues",           "focus_areas": ["Low Self-esteem", "Career & Life Coaching"]},
    {"keyid": 72, "term": "Communication Problem",       "focus_areas": ["Low Self-esteem", "Career & Life Coaching"]},
    {"keyid": 73, "term": "Assertiveness",               "focus_areas": ["Low Self-esteem", "Career & Life Coaching"]},
    {"keyid": 74, "term": "Purpose of Life",             "focus_areas": ["Career & Life Coaching"]},
    {"keyid": 75, "term": "Life Direction",              "focus_areas": ["Career & Life Coaching"]}
]


# Common multi-word phrase patterns mapped directly to canonical terms and focus areas
PHRASE_SYNONYMS = {
    # Concentration & Focus
    "lack of concentration": ("ADHD & Focus", ["Neurodiversity (ADHD, Autism, etc.)", "Motivation & Goal Setting"]),
    "loss of concentration": ("ADHD & Focus", ["Neurodiversity (ADHD, Autism, etc.)", "Motivation & Goal Setting"]),
    "poor concentration": ("ADHD & Focus", ["Neurodiversity (ADHD, Autism, etc.)", "Motivation & Goal Setting"]),
    "cannot concentrate": ("ADHD & Focus", ["Neurodiversity (ADHD, Autism, etc.)", "Motivation & Goal Setting"]),
    "cant concentrate": ("ADHD & Focus", ["Neurodiversity (ADHD, Autism, etc.)", "Motivation & Goal Setting"]),
    "hard to concentrate": ("ADHD & Focus", ["Neurodiversity (ADHD, Autism, etc.)", "Motivation & Goal Setting"]),
    "trouble concentrating": ("ADHD & Focus", ["Neurodiversity (ADHD, Autism, etc.)", "Motivation & Goal Setting"]),
    "difficulty concentrating": ("ADHD & Focus", ["Neurodiversity (ADHD, Autism, etc.)", "Motivation & Goal Setting"]),
    "lack of focus": ("ADHD & Focus", ["Neurodiversity (ADHD, Autism, etc.)", "Motivation & Goal Setting"]),
    "focus issue": ("ADHD & Focus", ["Neurodiversity (ADHD, Autism, etc.)", "Motivation & Goal Setting"]),
    "focus issues": ("ADHD & Focus", ["Neurodiversity (ADHD, Autism, etc.)", "Motivation & Goal Setting"]),
    "trouble focusing": ("ADHD & Focus", ["Neurodiversity (ADHD, Autism, etc.)", "Motivation & Goal Setting"]),
    "difficulty focusing": ("ADHD & Focus", ["Neurodiversity (ADHD, Autism, etc.)", "Motivation & Goal Setting"]),
    "attention issue": ("ADHD & Focus", ["Neurodiversity (ADHD, Autism, etc.)", "Motivation & Goal Setting"]),
    "attention issues": ("ADHD & Focus", ["Neurodiversity (ADHD, Autism, etc.)", "Motivation & Goal Setting"]),
    "attention span": ("ADHD & Focus", ["Neurodiversity (ADHD, Autism, etc.)", "Motivation & Goal Setting"]),
    # Confidence & Esteem
    "lack of confidence": ("Lack of Confidence", ["Low Self-esteem", "Career & Life Coaching"]),
    "low confidence": ("Lack of Confidence", ["Low Self-esteem", "Career & Life Coaching"]),
    "self confidence": ("Lack of Confidence", ["Low Self-esteem", "Career & Life Coaching"]),
    "self-confidence": ("Lack of Confidence", ["Low Self-esteem", "Career & Life Coaching"]),
    "low self esteem": ("Low Self-esteem", ["Low Self-esteem"]),
    "low self-esteem": ("Low Self-esteem", ["Low Self-esteem"]),
    # Motivation & Procrastination
    "lack of motivation": ("Low Motivation", ["Motivation & Goal Setting"]),
    "low motivation": ("Low Motivation", ["Motivation & Goal Setting"]),
    "no motivation": ("Low Motivation", ["Motivation & Goal Setting"]),
    # Sleep
    "lack of sleep": ("Sleep Problems", ["Anxiety & Panic Attacks", "Stress Management"]),
    "trouble sleeping": ("Sleep Problems", ["Anxiety & Panic Attacks", "Stress Management"]),
    "can't sleep": ("Sleep Problems", ["Anxiety & Panic Attacks", "Stress Management"]),
    "cannot sleep": ("Sleep Problems", ["Anxiety & Panic Attacks", "Stress Management"]),
    # Energy / Burnout
    "lack of energy": ("Burnout", ["Stress Management", "Nutrition & Wellness"]),
    "low energy": ("Burnout", ["Stress Management", "Nutrition & Wellness"]),
    # Relationships
    "toxic relationship": ("Relationship Problems", ["Relationship Counselling"]),
    "relationship issue": ("Relationship Problems", ["Relationship Counselling"]),
    "relationship issues": ("Relationship Problems", ["Relationship Counselling"]),
}

KEYWORD_SYNONYMS = {
    "focus": ["ADHD", "Neurodiversity (ADHD, Autism, etc.)", "Motivation & Goal Setting"],
    "focusing": ["ADHD", "Neurodiversity (ADHD, Autism, etc.)", "Motivation & Goal Setting"],
    "concentration": ["ADHD", "Neurodiversity (ADHD, Autism, etc.)", "Motivation & Goal Setting"],
    "concentrate": ["ADHD", "Neurodiversity (ADHD, Autism, etc.)", "Motivation & Goal Setting"],
    "concentrating": ["ADHD", "Neurodiversity (ADHD, Autism, etc.)", "Motivation & Goal Setting"],
    "distracted": ["ADHD", "Neurodiversity (ADHD, Autism, etc.)", "Motivation & Goal Setting"],
    "distraction": ["ADHD", "Neurodiversity (ADHD, Autism, etc.)", "Motivation & Goal Setting"],
    "distractions": ["ADHD", "Neurodiversity (ADHD, Autism, etc.)", "Motivation & Goal Setting"],
    "attention": ["ADHD", "Neurodiversity (ADHD, Autism, etc.)", "Motivation & Goal Setting"],
    "adhd": ["ADHD", "Neurodiversity (ADHD, Autism, etc.)"],
    "autism": ["Autism-related Challenges", "Neurodiversity (ADHD, Autism, etc.)"],
    "sleepy": ["Sleep Problems", "Stress Management"],
    "sleep": ["Sleep Problems"],
    "insomnia": ["Sleep Problems"],
    "tired": ["Burnout", "Stress Management", "Nutrition & Wellness"],
    "exhausted": ["Burnout", "Stress Management"],
    "burnout": ["Burnout", "Work-related Stress"],
    "burnt": ["Burnout", "Work-related Stress"],
    "stressed": ["Stress", "Stress Management"],
    "stress": ["Stress", "Stress Management"],
    "anxious": ["Anxiety", "Anxiety & Panic Attacks"],
    "anxiety": ["Anxiety", "Anxiety & Panic Attacks"],
    "worried": ["Excessive Worry", "Anxiety & Panic Attacks"],
    "worry": ["Excessive Worry", "Anxiety & Panic Attacks"],
    "overthinking": ["Overthinking", "Anxiety & Panic Attacks", "Stress Management"],
    "sad": ["Sadness", "Depression & Mood Disorders"],
    "sadness": ["Sadness", "Depression & Mood Disorders"],
    "depressed": ["Depression", "Depression & Mood Disorders"],
    "depression": ["Depression", "Depression & Mood Disorders"],
    "low": ["Feeling Low", "Depression & Mood Disorders"],
    "breakup": ["Breakup", "Relationship Counselling"],
    "divorce": ["Separation", "Relationship Counselling"],
    "partner": ["Relationship Problems", "Relationship Counselling"],
    "relationship": ["Relationship Problems", "Relationship Counselling"],
    "relationships": ["Relationship Problems", "Relationship Counselling"],
    "marriage": ["Relationship Problems", "Relationship Counselling"],
    "sex": ["Sexual & Intimacy Issues", "Sexual & Intimacy Problems"],
    "sexual": ["Sexual & Intimacy Issues", "Sexual & Intimacy Problems"],
    "intimacy": ["Sexual & Intimacy Issues", "Sexual & Intimacy Problems"],
    "diet": ["Nutrition", "Nutrition & Wellness"],
    "food": ["Nutrition", "Nutrition & Wellness"],
    "gut": ["Gut Health", "Nutrition & Wellness"],
    "digestion": ["Digestive Wellness", "Nutrition & Wellness"],
    "weight": ["Weight Management", "Nutrition & Wellness"],
    "fat": ["Weight Management", "Nutrition & Wellness"],
    "confidence": ["Confidence Issues", "Low Self-esteem"],
    "esteem": ["Low Self-esteem"],
    "anger": ["Anger Issues", "Anger Management"],
    "angry": ["Anger Issues", "Anger Management"],
    "trauma": ["Trauma", "Abuse & Trauma (including Childhood)"],
    "grief": ["Grief, Bereavement & Loss", "Grief & Bereavement"],
    "loss": ["Grief, Bereavement & Loss", "Grief & Bereavement"],
    "lost": ["Grief, Bereavement & Loss", "Career & Life Coaching"],
    "career": ["Career Decisions", "Career & Life Coaching"],
    "job": ["Workplace Problems", "Work-related Stress"],
    "work": ["Work Stress", "Work-related Stress"],
    "procrastination": ["Procrastination", "Motivation & Goal Setting"],
    "procrastinating": ["Procrastination", "Motivation & Goal Setting"],
    "lazy": ["Low Motivation", "Motivation & Goal Setting"],
    "lonely": ["Loneliness", "Depression & Mood Disorders"],
    "loneliness": ["Loneliness", "Depression & Mood Disorders"],
    "alone": ["Social Isolation", "Depression & Mood Disorders"],
    "panic": ["Panic Attacks", "Anxiety & Panic Attacks"],
}


FOCUS_AREA_CATEGORY_MAP = {
    # Physical
    "Nutrition & Wellness": "Physical",
    "Physical Fitness & Wellness": "Physical",
    "Body Image Issues": "Physical",
    # Professional
    "Work-related Stress": "Professional",
    "Work-life Balance": "Professional",
    "Career & Life Coaching": "Professional",
    # Mental (Default for other focus areas)
    "Anxiety & Panic Attacks": "Mental",
    "Stress Management": "Mental",
    "Depression & Mood Disorders": "Mental",
    "Anger Management": "Mental",
    "Low Self-esteem": "Mental",
    "Abuse & Trauma (including Childhood)": "Mental",
    "Grief & Bereavement": "Mental",
    "Crisis Intervention": "Mental",
    "Mindfulness & Meditation": "Mental",
    "Addiction & Substance Use": "Mental",
    "Relationship Counselling": "Mental",
    "Family Issues / Conflicts": "Mental",
    "Parenting Challenges": "Mental",
    "Sexual & Intimacy Problems": "Mental",
    "LGBTQIA+ Affirmative Counselling": "Mental",
    "Neurodiversity (ADHD, Autism, etc.)": "Mental",
    "Personality Disorders": "Mental",
}


SUPPORTED_LANGUAGES = {
    "kannada": "Kannada",
    "kanada": "Kannada",
    "kannad": "Kannada",
    "kannda": "Kannada",
    "ಕನ್ನಡ": "Kannada",
    "hindi": "Hindi",
    "hind": "Hindi",
    "हिंदी": "Hindi",
    "tamil": "Tamil",
    "tamizh": "Tamil",
    "தமிழ்": "Tamil",
    "telugu": "Telugu",
    "telegu": "Telugu",
    "తెలుగు": "Telugu",
    "malayalam": "Malayalam",
    "malyalam": "Malayalam",
    "malayali": "Malayalam",
    "മലയാളം": "Malayalam",
    "english": "English",
    "marathi": "Marathi",
    "marati": "Marathi",
    "मराठी": "Marathi",
    "bengali": "Bengali",
    "bangla": "Bengali",
    "বাংলা": "Bengali",
    "gujarati": "Gujarati",
    "gujrati": "Gujarati",
    "ગુજરાતી": "Gujarati",
    "punjabi": "Punjabi",
    "panjabi": "Punjabi",
    "ਪੰਜਾਬੀ": "Punjabi",
    "odia": "Odia",
    "oriya": "Odia",
    "ଓଡ଼ಿଆ": "Odia",
    "urdu": "Urdu",
    "assamese": "Assamese",
    "bhojpuri": "Bhojpuri",
    "konkani": "Konkani",
    "sanskrit": "Sanskrit",
    "french": "French",
    "german": "German",
    "spanish": "Spanish",
}

GENDER_PATTERNS = {
    "female": "Female",
    "woman": "Female",
    "women": "Female",
    "lady": "Female",
    "male": "Male",
    "man": "Male",
    "men": "Male",
    "guy": "Male",
}


def match_consultants_for_user_query(
    user_message: str, db, limit: int = 3, tz_name: str = "Asia/Kolkata", detected_language: str = None
) -> dict:
    """
    Given a user message, extract multi-dimensional filters:
      1. Matching topics / focus areas from SEARCH_KEYWORD_TAXONOMY & synonyms
      2. Requested language preferences (e.g., Kannada, Hindi, Tamil, English)
      3. Requested gender preferences (e.g., Female, Male)
    Query the DB for approved & active consultants and rank them strictly based on
    their database profile (expertise_areas, languages, specialization, bio, rating, availability).
    """
    from models import ConsultantProfile, User
    import re
    from sarvam_voice import detect_text_language, SARVAM_LANG_TO_NAME

    msg_lower = user_message.lower().strip()

    STOP_TOKENS = {
        "lack", "loss", "having", "trouble", "facing", "feeling", "issues", "problems",
        "related", "challenges", "general", "situation", "difficulties", "concerns",
        "problem", "difficult", "past", "help", "need", "life", "time", "managing",
        "management", "wellness", "issue", "poor", "hard", "high", "offlate", "lately",
        "often", "always", "some", "very", "much", "want", "find", "looking", "good"
    }

    # 1. Extract requested languages from keywords in query
    matched_languages = []
    for lang_key, canon_lang in SUPPORTED_LANGUAGES.items():
        if re.search(r'(?:\b|^)' + re.escape(lang_key) + r'(?:\b|$)', msg_lower):
            if canon_lang not in matched_languages:
                matched_languages.append(canon_lang)

    # If no explicit language keyword was found, but a non-English language was detected from audio LID or script
    if not matched_languages:
        if detected_language:
            canon_from_lid = SARVAM_LANG_TO_NAME.get(detected_language, detected_language)
            if canon_from_lid and canon_from_lid != "English" and canon_from_lid not in matched_languages:
                matched_languages.append(canon_from_lid)
        else:
            _, auto_script_lang = detect_text_language(user_message)
            if auto_script_lang and auto_script_lang != "English" and auto_script_lang not in matched_languages:
                matched_languages.append(auto_script_lang)

    # 2. Extract requested gender
    matched_gender = None
    for g_key, canon_g in GENDER_PATTERNS.items():
        if re.search(r'\b' + re.escape(g_key) + r'\b', msg_lower):
            matched_gender = canon_g
            break

    # 3. Detect experience or budget/pricing preference cues in query
    is_exp_requested = bool(re.search(r'\b(experienced|senior|veteran|seasoned|years of exp|expert|specialist)\b', msg_lower))
    is_budget_requested = bool(re.search(r'\b(affordable|budget|cheap|low cost|economical|inexpensive|pocket friendly|reasonable fee|low fee|low rate|price)\b', msg_lower))

    matched_items = []
    matched_focus_areas = []
    matched_terms = []

    # 3. Check Phrase Synonyms first (e.g. 'lack of concentration', 'focus issue', 'lack of sleep')
    for phrase, (canon_term, focus_list) in PHRASE_SYNONYMS.items():
        if phrase in msg_lower:
            if canon_term not in matched_terms:
                matched_terms.append(canon_term)
            for fa in focus_list:
                if fa not in matched_focus_areas:
                    matched_focus_areas.append(fa)

    # 4. Check exact taxonomy phrases
    for item in SEARCH_KEYWORD_TAXONOMY:
        term_lower = item["term"].lower()
        if term_lower in msg_lower:
            matched_items.append(item)
            if item["term"] not in matched_terms:
                matched_terms.append(item["term"])
            for fa in item["focus_areas"]:
                if fa not in matched_focus_areas:
                    matched_focus_areas.append(fa)

    # 5. Check colloquial synonyms (e.g., 'concentration', 'focus', 'sleepy', 'partner', 'diet')
    words = re.findall(r'\b\w+\b', msg_lower)
    for word in words:
        if word in KEYWORD_SYNONYMS:
            for syn in KEYWORD_SYNONYMS[word]:
                tax_item = next((it for it in SEARCH_KEYWORD_TAXONOMY if it["term"].lower() == syn.lower()), None)
                if tax_item:
                    if tax_item["term"] not in matched_terms:
                        matched_terms.append(tax_item["term"])
                    for fa in tax_item["focus_areas"]:
                        if fa not in matched_focus_areas:
                            matched_focus_areas.append(fa)
                else:
                    if syn not in matched_focus_areas:
                        matched_focus_areas.append(syn)
                    if syn not in matched_terms:
                        matched_terms.append(syn)

    # 6. Check meaningful single-word tokens from taxonomy only if nothing matched yet
    if not matched_terms:
        for item in SEARCH_KEYWORD_TAXONOMY:
            term_lower = item["term"].lower()
            tokens = [t for t in re.split(r'[\s&,/()-]+', term_lower) if len(t) > 3 and t not in STOP_TOKENS]
            if tokens and any(re.search(r'\b' + re.escape(t) + r'\b', msg_lower) for t in tokens):
                matched_items.append(item)
                if item["term"] not in matched_terms:
                    matched_terms.append(item["term"])
                for fa in item["focus_areas"]:
                    if fa not in matched_focus_areas:
                        matched_focus_areas.append(fa)

    # 7. Fallback to intent classification if nothing matched
    if not matched_focus_areas:
        intent = detect_intent(user_message)
        if intent.get("category") == "Mental":
            matched_focus_areas = ["Anxiety & Panic Attacks", "Stress Management", "Depression & Mood Disorders"]
            matched_terms = ["Mental Wellbeing"]
        elif intent.get("category") == "Physical":
            matched_focus_areas = ["Nutrition & Wellness", "Physical Fitness & Wellness"]
            matched_terms = ["Physical Wellness & Nutrition"]
        elif intent.get("category") == "Professional":
            matched_focus_areas = ["Work-related Stress", "Career & Life Coaching", "Work-life Balance"]
            matched_terms = ["Career & Work Stress"]
        else:
            matched_focus_areas = ["Stress Management", "Career & Life Coaching"]
            matched_terms = ["General Wellbeing"]

    primary_keyword = matched_terms[0] if matched_terms else (matched_focus_areas[0] if matched_focus_areas else "General Wellbeing")
    target_categories = {FOCUS_AREA_CATEGORY_MAP.get(fa, "Mental") for fa in matched_focus_areas} if matched_focus_areas else set()

    # 8. Query all approved & active consultants from database
    consultant_rows = db.query(ConsultantProfile, User).join(
        User, User.id == ConsultantProfile.user_id
    ).filter(
        User.user_type == "consultant",
        User.is_active == True,
        ConsultantProfile.is_approved == True
    ).all()

    # Fallback if user_type condition is too strict
    if not consultant_rows:
        consultant_rows = db.query(ConsultantProfile, User).join(
            User, User.id == ConsultantProfile.user_id
        ).filter(
            User.is_active == True,
            ConsultantProfile.is_approved == True
        ).all()

    def evaluate_consultant(c, user):
        # Parse consultant expertise areas
        eas = []
        if getattr(c, "expertise_areas", None):
            try:
                eas = json.loads(c.expertise_areas) if isinstance(c.expertise_areas, str) and c.expertise_areas.startswith("[") else [str(c.expertise_areas)]
            except Exception:
                eas = [str(c.expertise_areas)]
        eas_lower = [str(a).lower() for a in eas if a]
        eas_str = " ".join(eas_lower)

        # Parse consultant languages
        langs = []
        if getattr(c, "languages", None):
            raw_l = c.languages
            try:
                if isinstance(raw_l, list):
                    langs = [str(l) for l in raw_l]
                elif isinstance(raw_l, str):
                    raw_str = raw_l.strip()
                    if raw_str.startswith("["):
                        try:
                            langs = json.loads(raw_str)
                        except Exception:
                            try:
                                import ast
                                langs = ast.literal_eval(raw_str)
                            except Exception:
                                langs = [w for w in re.findall(r'[a-zA-Z]+', raw_str) if w.lower() not in ['true', 'false', 'none']]
                    else:
                        langs = [l.strip() for l in raw_str.split(",") if l.strip()]
            except Exception:
                langs = [str(raw_l)]
        if not langs:
            langs = ["English"]
        langs_lower = [str(l).lower() for l in langs]
        langs_str = ", ".join(langs)

        spec_lower = (getattr(c, "specialization", "") or "").lower()
        bio_lower = (getattr(c, "bio", "") or "").lower()

        w_cat = "Mental"
        try:
            w_cat = getattr(c, "wellness_category", None) or classify_consultant(c)
        except Exception:
            w_cat = "Mental"

        # Check category mismatch
        if target_categories == {"Physical"} and w_cat == "Professional":
            if not any(k in eas_str or k in spec_lower or k in bio_lower for k in ["nutrition", "diet", "gut", "fitness", "physio"]):
                return None
        elif target_categories == {"Professional"} and w_cat == "Physical":
            if not any(k in eas_str or k in spec_lower or k in bio_lower for k in ["career", "leadership", "executive", "workplace"]):
                return None

        relevance_score = 0.0
        matched_areas_for_c = []
        for fa in matched_focus_areas:
            fa_lower = fa.lower()
            if any(fa_lower in a or a in fa_lower for a in eas_lower):
                relevance_score += 25.0
                matched_areas_for_c.append(fa)
            elif fa_lower in spec_lower:
                relevance_score += 18.0
                matched_areas_for_c.append(fa)
            elif fa_lower in bio_lower:
                relevance_score += 10.0
                matched_areas_for_c.append(fa)

        # Check matched specific terms in profile
        for t in matched_terms:
            t_lower = t.lower()
            if t_lower in eas_str:
                relevance_score += 15.0
                if t not in matched_areas_for_c:
                    matched_areas_for_c.append(t)
            elif t_lower in spec_lower:
                relevance_score += 12.0
                if t not in matched_areas_for_c:
                    matched_areas_for_c.append(t)
            elif t_lower in bio_lower:
                relevance_score += 6.0

        # Category match bonus
        if target_categories and w_cat in target_categories:
            relevance_score += 10.0

        if relevance_score <= 0.0:
            return None

        # Check language match boolean
        has_lang = True
        if matched_languages:
            langs_unified = " ".join(langs_lower)
            has_lang = any(
                req_l.lower() in langs_lower
                or req_l.lower() in langs_unified
                or any(req_l.lower() in l for l in langs_lower)
                for req_l in matched_languages
            )

        # Check gender match boolean
        has_gender = True
        if matched_gender:
            c_gender = (getattr(c, "gender", "") or "").lower()
            has_gender = (c_gender == matched_gender.lower())

        # ── Experience Weightage (Up to 10.0 points baseline) ──
        exp_years = float(getattr(c, "experience_years", 2) or 2)
        exp_score = min(10.0, max(0.0, exp_years * 0.5))
        if is_exp_requested and exp_years >= 5:
            exp_score += min(8.0, exp_years * 0.5)

        # ── Pricing / Amount Charged Weightage (Up to 8.0 points baseline) ──
        fee = float(getattr(c, "consultation_fee", None) or getattr(c, "hourly_rate", 500) or 500)
        price_score = max(0.0, min(8.0, (2500.0 - fee) / 250.0))
        if is_budget_requested:
            price_score += max(0.0, min(10.0, (2000.0 - fee) / 150.0))

        # ── Rating & Schedule Availability ──
        rating_score = float(getattr(c, "rating", 0.0) or 0.0) * 2.0
        schedule_score = 3.0 if getattr(c, "schedules", None) else 0.0

        total_score = relevance_score + exp_score + price_score + rating_score + schedule_score

        name = getattr(user, "name", None) or getattr(c, "full_name", None) or "Consultant"
        earliest = get_earliest_slot(c, db, tz_name=tz_name)

        # Sexual wellness flag
        is_sw = (
            "sexual" in eas_str or "intimacy" in eas_str or
            "sexual" in spec_lower or "intimacy" in spec_lower or
            "sexual wellness" in bio_lower or "sexual health" in bio_lower or "sexologist" in bio_lower or "sex therapy" in bio_lower
        )

        return {
            "score":                  total_score,
            "has_requested_lang":     has_lang,
            "has_requested_gender":   has_gender,
            "data": {
                "id":                     c.id,
                "user_id":                user.id,
                "name":                   name,
                "specialization":         getattr(c, "specialization", None) or "Wellbeing Consultant",
                "rating":                 float(getattr(c, "rating", 0.0) or 0.0),
                "experience_years":       getattr(c, "experience_years", 2) or 2,
                "hourly_rate":            getattr(c, "consultation_fee", None) or getattr(c, "hourly_rate", 500) or 500,
                "photo_url":              f"/api/profile-photo/{user.id}" if getattr(c, "photo_url", None) else "",
                "wellness_category":      w_cat,
                "languages":              langs,
                "languages_str":          langs_str,
                "earliest_slot":          earliest,
                "matched_areas":          matched_areas_for_c or (eas[:2] if eas else [getattr(c, "specialization", "General")]),
                "offers_sexual_wellness": is_sw,
                "has_requested_lang":     has_lang,
            }
        }

    # Evaluate all consultants for topic matching
    evaluated_candidates = []
    for c, user in consultant_rows:
        try:
            res = evaluate_consultant(c, user)
            if res:
                evaluated_candidates.append(res)
        except Exception as _c_err:
            print(f"[Matcher] error processing consultant {getattr(c, 'id', '?')}: {_c_err}")

    # Step 1: Filter by language condition (STRICT AND CONDITION)
    language_matched = True
    if matched_languages:
        lang_filtered = [item for item in evaluated_candidates if item["has_requested_lang"]]
        if lang_filtered:
            # STRICT MATCH: Only keep consultants who speak the requested language!
            evaluated_candidates = lang_filtered
            language_matched = True
        else:
            # No consultant in DB speaks the requested language for this topic -> fallback to topic experts
            language_matched = False

    # Step 2: Filter by gender condition (STRICT AND CONDITION)
    if matched_gender:
        gender_filtered = [item for item in evaluated_candidates if item["has_requested_gender"]]
        if gender_filtered:
            # STRICT MATCH: Only keep consultants matching requested gender!
            evaluated_candidates = gender_filtered

    # Sort remaining candidates strictly by score descending
    evaluated_candidates.sort(key=lambda x: x["score"], reverse=True)
    all_matched_ids = [item["data"]["id"] for item in evaluated_candidates]
    top_consultants = [item["data"] for item in evaluated_candidates[:limit]]

    return {
        "matched_keyword":     primary_keyword,
        "matched_focus_areas": matched_focus_areas,
        "matched_languages":   matched_languages,
        "matched_gender":      matched_gender,
        "language_matched":    language_matched,
        "all_matched_ids":     all_matched_ids,
        "total_matches":       len(all_matched_ids),
        "consultants":         top_consultants,
    }


def format_matcher_prompt_context(
    consultants: list,
    matched_keyword: str,
    focus_areas: list,
    matched_languages: list = None,
    matched_gender: str = None,
    language_matched: bool = True
) -> str:
    """Build context for Emora in consultant matcher mode with multi-filter awareness."""
    matched_languages = matched_languages or []
    if not consultants:
        lang_clause = f" speaking {', '.join(matched_languages)}" if matched_languages else ""
        gender_clause = f" ({matched_gender})" if matched_gender else ""
        return (
            f"[CONSULTANT_MATCHER_RECOMMENDATION]\n"
            f"The user is looking for help regarding: '{matched_keyword}'{lang_clause}{gender_clause}.\n"
            f"You are currently assisting them directly on the Find Consultants page.\n"
            f"CRITICAL: DO NOT tell them to visit '/app/consultants' or go to any link.\n"
            f"Warmly ask them 1 short question about what specific support they are looking for so you can help find the right expert.\n"
            f"[END_CONSULTANT_MATCHER_RECOMMENDATION]"
        )

    lang_note = ""
    if matched_languages:
        if language_matched:
            lang_note = f" Requested Language: {', '.join(matched_languages)} (CONFIRMED: All matched consultants speak {', '.join(matched_languages)}!)."
        else:
            lang_note = f" Requested Language: {', '.join(matched_languages)} (NOTE: None of our {matched_keyword} specialists currently list {', '.join(matched_languages)} on their profile. Matched experts converse in English/Hindi)."

    gender_note = f" Requested Gender: {matched_gender}." if matched_gender else ""

    lines = [
        f"[CONSULTANT_MATCHER_RECOMMENDATION]\n"
        f"The user is looking for help regarding: '{matched_keyword}' (Focus Areas: {', '.join(focus_areas)}).{lang_note}{gender_note}\n"
        f"You have matched these real SolaceSquad consultants from our database (their recommendation cards are already filtered and presented directly below your message to the user):\n"
    ]
    for c in consultants:
        areas_text = ", ".join(c.get("matched_areas", [])) or c["specialization"]
        langs_text = ", ".join(c.get("languages", []))
        lines.append(
            f"  • {c['name']} ({c['specialization']}, {c['experience_years']} yrs exp) — Next available: {c['earliest_slot']} (Fee: ₹{c['hourly_rate']}/hr). Speaks: {langs_text}. Expertise: {areas_text}"
        )
    lines.append(
        f"\nCRITICAL INSTRUCTIONS FOR EMORA IN MATCHER MODE:\n"
        f"1. You are talking to the user DIRECTLY ON the Find Consultants page. NEVER tell them to 'go to /app/consultants', 'visit the consultants section', or navigate anywhere.\n"
        f"2. DO NOT conduct grounding exercises, breathing exercises, or live sensory therapy techniques (e.g. 5-4-3-2-1 grounding or 'tell me 3 things you hear'). Your sole role is to introduce the matched expert(s).\n"
        f"3. Acknowledge and validate what they are experiencing (e.g., {matched_keyword}) in 1 warm, empathetic sentence.\n"
    )

    names_list = ", ".join(c["name"] for c in consultants)
    if matched_languages and language_matched:
        lines.append(f"4. Explicitly confirm to the user that {names_list} speaks {', '.join(matched_languages)} as requested, and introduce them BY EXACT NAME explaining briefly how their expertise can support them.\n")
    elif matched_languages and not language_matched:
        lines.append(f"4. Transparently let the user know that while our {matched_keyword} specialists currently converse in {consultants[0].get('languages_str', 'English/Hindi')}, introduce {names_list} BY EXACT NAME as our top verified specialists for this concern.\n")
    else:
        lines.append(f"4. Introduce {names_list} BY EXACT NAME, explaining briefly how their specific expertise can support them.\n")

    lines.append(
        f"5. Direct them to the card(s) shown right below to view their profile or click 'Book Session'.\n"
        f"6. Keep your response concise (2-4 sentences max), warm, and supportive.\n"
        f"[END_CONSULTANT_MATCHER_RECOMMENDATION]"
    )
    return "\n".join(lines)

