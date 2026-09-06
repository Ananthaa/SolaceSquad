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


def match_consultants_for_user_query(user_message: str, db, limit: int = 3, tz_name: str = "Asia/Kolkata") -> dict:
    """
    Given a user message, extract matching keywords from SEARCH_KEYWORD_TAXONOMY,
    query the DB for approved & available consultants, and rank them strictly based on
    their database profile (expertise_areas, specialization, bio, rating, availability).
    """
    from models import ConsultantProfile, User
    import re

    msg_lower = user_message.lower().strip()

    # 1. Identify matched search terms and focus areas (exact terms first, then meaningful keyword tokens)
    STOP_TOKENS = {
        "wellness", "feeling", "managing", "issues", "problems", "related",
        "challenges", "general", "situation", "difficulties", "concerns", "problem"
    }

    matched_items = []
    matched_focus_areas = []
    matched_terms = []

    # Check exact phrases first
    for item in SEARCH_KEYWORD_TAXONOMY:
        term_lower = item["term"].lower()
        if term_lower in msg_lower:
            matched_items.append(item)
            matched_terms.append(item["term"])
            for fa in item["focus_areas"]:
                if fa not in matched_focus_areas:
                    matched_focus_areas.append(fa)

    # Check meaningful multi-word tokens
    for item in SEARCH_KEYWORD_TAXONOMY:
        if item["term"] in matched_terms:
            continue
        term_lower = item["term"].lower()
        tokens = [t for t in re.split(r'[\s&,/()-]+', term_lower) if len(t) > 3 and t not in STOP_TOKENS]
        if tokens and any(re.search(r'\b' + re.escape(t) + r'\b', msg_lower) for t in tokens):
            matched_items.append(item)
            matched_terms.append(item["term"])
            for fa in item["focus_areas"]:
                if fa not in matched_focus_areas:
                    matched_focus_areas.append(fa)

    primary_keyword = matched_terms[0] if matched_terms else ""

    # Fallback to category signals if no specific keyword matched
    if not matched_focus_areas:
        intent = detect_intent(user_message)
        if intent.get("category") == "Mental":
            matched_focus_areas = ["Anxiety & Panic Attacks", "Stress Management", "Depression & Mood Disorders"]
            primary_keyword = "Mental Wellbeing"
        elif intent.get("category") == "Physical":
            matched_focus_areas = ["Nutrition & Wellness", "Physical Fitness & Wellness"]
            primary_keyword = "Physical Wellness & Nutrition"
        elif intent.get("category") == "Professional":
            matched_focus_areas = ["Work-related Stress", "Career & Life Coaching", "Work-life Balance"]
            primary_keyword = "Career & Work Stress"
        else:
            primary_keyword = "General Wellbeing"

    # 2. Query all approved & available consultants from database
    consultants = db.query(ConsultantProfile).join(
        User, User.id == ConsultantProfile.user_id
    ).filter(
        ConsultantProfile.is_approved == True,
        ConsultantProfile.is_available == True,
        User.is_active == True
    ).all()

    scored = []
    for c in consultants:
        score = 0.0
        # Parse consultant expertise areas
        eas = []
        if c.expertise_areas:
            try:
                eas = json.loads(c.expertise_areas) if isinstance(c.expertise_areas, str) else c.expertise_areas
            except Exception:
                eas = [str(c.expertise_areas)]
        eas_lower = [str(a).lower() for a in eas]
        eas_str = " ".join(eas_lower)

        spec_lower = (c.specialization or "").lower()
        bio_lower = (c.bio or "").lower()

        matched_areas_for_c = []
        for fa in matched_focus_areas:
            fa_lower = fa.lower()
            if any(fa_lower in a or a in fa_lower for a in eas_lower):
                score += 15.0
                matched_areas_for_c.append(fa)
            elif fa_lower in spec_lower:
                score += 10.0
                matched_areas_for_c.append(fa)
            elif fa_lower in bio_lower:
                score += 6.0
                matched_areas_for_c.append(fa)

        # Check matched terms in profile
        for t in matched_terms:
            t_lower = t.lower()
            if t_lower in eas_str:
                score += 8.0
            if t_lower in spec_lower:
                score += 6.0
            if t_lower in bio_lower:
                score += 3.0

        # Base rating and schedule bonus
        score += float(c.rating or 0.0) * 2.0
        if c.schedules:
            score += 3.0

        name = c.user.name if c.user else (c.full_name or "Consultant")
        earliest = get_earliest_slot(c, db, tz_name=tz_name)

        # Sexual wellness flag
        is_sw = (
            "sexual" in eas_str or "intimacy" in eas_str or
            "sexual" in spec_lower or "intimacy" in spec_lower or
            "sexual wellness" in bio_lower
        )

        scored.append((score, {
            "id":                     c.id,
            "user_id":                c.user_id,
            "name":                   name,
            "specialization":         c.specialization or "Wellbeing Consultant",
            "rating":                 float(c.rating or 0.0),
            "experience_years":       c.experience_years or 2,
            "hourly_rate":            c.consultation_fee or c.hourly_rate or 500,
            "photo_url":              f"/api/profile-photo/{c.user_id}" if c.photo_url else "",
            "wellness_category":      c.wellness_category or "Mental",
            "earliest_slot":          earliest,
            "matched_areas":          matched_areas_for_c or (eas[:2] if eas else [c.specialization or "General"]),
            "offers_sexual_wellness": is_sw,
        }))

    scored.sort(key=lambda x: x[0], reverse=True)
    top_consultants = [item[1] for item in scored[:limit]]

    return {
        "matched_keyword":     primary_keyword,
        "matched_focus_areas": matched_focus_areas,
        "consultants":         top_consultants,
    }


def format_matcher_prompt_context(consultants: list, matched_keyword: str, focus_areas: list) -> str:
    """Build context for Emora in consultant matcher mode."""
    if not consultants:
        return (
            f"[CONSULTANT_MATCHER_RECOMMENDATION]\n"
            f"The user is asking about: '{matched_keyword}'.\n"
            f"No specific consultant was matched. Express warmth and empathy, and invite them to browse all consultants at /app/consultants.\n"
            f"[END_CONSULTANT_MATCHER_RECOMMENDATION]"
        )

    lines = [
        f"[CONSULTANT_MATCHER_RECOMMENDATION]\n"
        f"The user is looking for help regarding: '{matched_keyword}' (Focus Areas: {', '.join(focus_areas)}).\n"
        f"You have matched these real SolaceSquad consultants from our database:\n"
    ]
    for c in consultants:
        areas_text = ", ".join(c.get("matched_areas", [])) or c["specialization"]
        lines.append(
            f"  • {c['name']} ({c['specialization']}, {c['experience_years']} yrs exp, ⭐ {c['rating']:.1f}) — Next available: {c['earliest_slot']} (Fee: ₹{c['hourly_rate']}/hr). Expertise: {areas_text}"
        )
    lines.append(
        f"\nInstructions for Emora:\n"
        f"1. Acknowledge and validate the user's specific feelings in 1-2 empathetic, warm sentences.\n"
        f"2. Mention 1-2 of the matched consultants above by name, explaining briefly why their expertise fits what the user is experiencing.\n"
        f"3. Invite them to view their profile or click the booking / filter buttons shown below.\n"
        f"4. Keep your total response concise (2-4 sentences max), warm, and natural.\n"
        f"[END_CONSULTANT_MATCHER_RECOMMENDATION]"
    )
    return "\n".join(lines)

