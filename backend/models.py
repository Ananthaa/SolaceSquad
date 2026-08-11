from sqlalchemy import create_engine, Column, Integer, String, DateTime, Float, Boolean, ForeignKey, Text, Date
from sqlalchemy.sql import func
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship, deferred
from datetime import datetime, date
import bcrypt
import os

def _is_test_mode_default():
    return os.getenv("RAZORPAY_KEY_ID", "").startswith("rzp_test_")

# Create base class for models
Base = declarative_base()


class User(Base):
    """User model for authentication and profile data"""
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=True)
    name = Column(String(255), nullable=False)
    password_hash = Column(String(255), nullable=True)   # nullable: Google OAuth users have no password
    user_type = Column(String(50), nullable=False, default="user")  # 'user' or 'consultant'
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    first_login = Column(DateTime, nullable=True)  # Track first login for "Active since"
    last_login = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    phone_number = Column(String(20), unique=True, index=True, nullable=True)
    email_verified = Column(Boolean, default=False, nullable=False)  # Email OTP confirmed at signup
    timezone = Column(String(100), nullable=True, default='UTC')  # User's detected timezone

    # DPDPA Consent Fields
    consent_account      = Column(Boolean, default=True,  nullable=False, server_default='true')
    consent_health       = Column(Boolean, default=False, nullable=False, server_default='false')
    consent_recording    = Column(Boolean, default=False, nullable=False, server_default='false')
    consent_note_sharing = Column(Boolean, default=False, nullable=False, server_default='false')
    consent_prompted     = Column(Boolean, default=False, nullable=False, server_default='false')

    # Google OAuth fields
    oauth_provider           = Column(String(20),  nullable=True, index=True)   # 'google' or NULL
    google_id                = Column(String(255), nullable=True, unique=True, index=True)
    google_fit_refresh_token = Column(Text, nullable=True)   # stored for background Fit sync
    fitbit_refresh_token     = Column(Text, nullable=True)   # Fitbit OAuth refresh token
    strava_refresh_token     = Column(Text, nullable=True)   # Strava OAuth refresh token
    
    # Relationships
    vitals_records = relationship("VitalsRecord", back_populates="user", cascade="all, delete-orphan")
    mood_entries = relationship("MoodEntry", back_populates="user", cascade="all, delete-orphan")
    reset_tokens = relationship("PasswordResetToken", back_populates="user", cascade="all, delete-orphan")
    
    # For consultant interactions (as client)
    client_interactions = relationship(
        "ConsultantInteraction",
        foreign_keys="ConsultantInteraction.user_id",
        back_populates="client",
        cascade="all, delete-orphan"
    )
    
    # For consultant interactions (as consultant)
    consultant_interactions = relationship(
        "ConsultantInteraction",
        foreign_keys="ConsultantInteraction.consultant_id",
        back_populates="consultant",
        cascade="all, delete-orphan"
    )
    
    def set_password(self, password: str):
        """Hash and set the user's password"""
        # Truncate password to 72 bytes to comply with bcrypt limitations
        password_bytes = password.encode('utf-8')[:72]
        # Generate salt and hash the password
        salt = bcrypt.gensalt()
        hashed = bcrypt.hashpw(password_bytes, salt)
        # Store as string
        self.password_hash = hashed.decode('utf-8')
    
    def verify_password(self, password: str) -> bool:
        """Verify a password against the hash. Returns False for OAuth-only users."""
        if not self.password_hash:
            return False  # Google-only account — no password set
        # Truncate password to 72 bytes to comply with bcrypt limitations
        password_bytes = password.encode('utf-8')[:72]
        # Compare with stored hash
        hash_bytes = self.password_hash.encode('utf-8')
        return bcrypt.checkpw(password_bytes, hash_bytes)
    
    def update_last_login(self):
        """Update the last login timestamp"""
        self.last_login = datetime.utcnow()


class OTPVerification(Base):
    """OTP verification store"""
    __tablename__ = "otp_verification"
    
    id = Column(Integer, primary_key=True, index=True)
    phone_number = Column(String(20), index=True, nullable=True)  # nullable: email-only OTPs have no phone
    otp_email = Column(String(255), index=True, nullable=True)    # key for email-based OTPs
    otp_code = Column(String(6), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)
    is_verified = Column(Boolean, default=False)


class PasswordResetToken(Base):
    """Password reset token model"""
    __tablename__ = "password_reset_tokens"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    token = Column(String(255), unique=True, index=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    used = Column(Boolean, default=False, nullable=False)
    
    # Relationship
    user = relationship("User", back_populates="reset_tokens")


class VitalsRecord(Base):
    """Vitals record model for storing comprehensive health measurements"""
    __tablename__ = "vitals_records"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Vital measurements
    heart_rate = Column(Integer, nullable=True)             # BPM
    spo2 = Column(Integer, nullable=True)                   # Oxygen saturation % (0-100)
    respiratory_rate = Column(Integer, nullable=True)       # Breaths per minute
    temperature = Column(Float, nullable=True)              # Celsius
    blood_pressure_systolic = Column(Integer, nullable=True)   # mmHg
    blood_pressure_diastolic = Column(Integer, nullable=True)  # mmHg

    # Ratings (gender/age-specific, per SolaceSquad reference table)
    hr_rating  = Column(String(20), nullable=True)  # Poor / Good / Better / Best
    hr_score   = Column(Integer,    nullable=True)  # 50 / 60 / 80 / 100
    bp_rating  = Column(String(20), nullable=True)  # Poor / Good / Better / Best
    bp_score   = Column(Integer,    nullable=True)  # 50 / 60 / 80 / 100
    spo2_rating = Column(String(20), nullable=True) # Poor / Good / Better / Best
    spo2_score  = Column(Integer,    nullable=True) # 50 / 60 / 80 / 100
    rr_rating   = Column(String(20), nullable=True) # Poor / Good / Better / Best
    rr_score    = Column(Integer,    nullable=True) # 50 / 60 / 80 / 100
    temp_rating = Column(String(20), nullable=True) # Poor / Good / Better / Best
    temp_score  = Column(Integer,    nullable=True) # 50 / 60 / 80 / 100

    # Metadata
    confidence = Column(Float, default=0.0, nullable=False)
    scan_duration = Column(Integer, default=0, nullable=False)  # seconds
    method = Column(String(50), default="camera", nullable=False)
    health_score = Column(Float, nullable=True)  # Overall health score (0-100)
    
    # Relationship
    user = relationship("User", back_populates="vitals_records")



class MoodEntry(Base):
    """Mood entry model for tracking user's emotional state"""
    __tablename__ = "mood_entries"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
    mood_rating = Column(String(50), nullable=False)  # HAPPY / NEUTRAL / SAD / ANXIOUS / ANGRY
    notes = Column(Text, nullable=True)
    emotional_wellness_score = Column(Integer, nullable=True)  # 50-100 per mood table
    
    # Relationship
    user = relationship("User", back_populates="mood_entries")



class JournalEntry(Base):
    """Journal/Diary entry model for daily reflections"""
    __tablename__ = "journal_entries"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    entry_date = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    title = Column(String(255), nullable=True)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationship
    user = relationship("User", backref="journal_entries")


class ConsultantInteraction(Base):
    """Consultant interaction model for tracking sessions"""
    __tablename__ = "consultant_interactions"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)  # The client
    consultant_id = Column(Integer, ForeignKey("users.id"), nullable=False)  # The consultant
    interaction_date = Column(DateTime, default=datetime.utcnow, nullable=False)
    session_type = Column(String(100), nullable=True)  # e.g., "video call", "chat", "in-person"
    notes = Column(Text, nullable=True)  # Session notes (consultant-only)
    duration_minutes = Column(Integer, nullable=True)
    
    # Relationships
    client = relationship("User", foreign_keys=[user_id], back_populates="client_interactions")
    consultant = relationship("User", foreign_keys=[consultant_id], back_populates="consultant_interactions")


class UserProfile(Base):
    """Extended user profile model for detailed personal information"""
    __tablename__ = "user_profiles"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, unique=True)
    
    # Personal Information
    full_name = Column(String(255), nullable=True)
    preferred_name = Column(String(255), nullable=True)  # How they want to be known
    age = Column(Integer, nullable=True)
    gender = Column(String(50), nullable=True)  # Male, Female, Other, Prefer not to say
    height = Column(Float, nullable=True)  # in cm
    weight = Column(Float, nullable=True)  # in kg
    
    # Contact Details
    address = Column(Text, nullable=True)
    contact_email = Column(String(255), nullable=True)  # Alternative email
    
    # Professional Information
    occupation = Column(String(255), nullable=True)
    
    # Health Information
    medical_history = Column(Text, nullable=True)  # Lifestyle diseases, conditions
    wellness_habits = Column(Text, nullable=True)  # Physical workouts, Yoga, Running, swimming JSON
    wellness_frequency_per_week = Column(Integer, nullable=True)  # How many days/week they do wellness activities
    wellness_minutes_per_day = Column(Integer, nullable=True)  # Average minutes per day spent on wellness
    about_me = Column(Text, nullable=True)  # Short bio or description
    
    # Metadata
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationship
    user = relationship("User", backref="profile")


class ConsultantProfile(Base):
    """Consultant profile with specialization and details"""
    __tablename__ = "consultant_profiles"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, unique=True)
    specialization = Column(String(255), nullable=True)  # e.g., "Emotional Wellbeing", "Nutrition"
    bio = Column(Text, nullable=True)
    experience_years = Column(Integer, default=0)
    rating = Column(Float, default=0.0)
    hourly_rate = Column(Float, nullable=True)
    consultation_fee = Column(Float, default=0.0)  # Per consultation fee (what user pays)
    consultant_payout = Column(Float, default=0.0)  # What the consultant receives per session (fixed)
    # fee split is managed by admin via consultation_fee (user pays) and consultant_payout (consultant receives)
    calls_scheduled = Column(Integer, default=0, nullable=False)   # Total appointments ever scheduled
    calls_completed = Column(Integer, default=0, nullable=False)   # Total calls that reached 'completed'

    is_available = Column(Boolean, default=True)
    is_approved = Column(Boolean, default=False)
    is_profile_completed = Column(Boolean, default=False)
    
    # Extended profile fields for consultants
    full_name = Column(String(255), nullable=True)
    age = Column(Integer, nullable=True)
    gender = Column(String(50), nullable=True)
    height = Column(Float, nullable=True)  # in cm
    weight = Column(Float, nullable=True)  # in kg
    contact_details = Column(Text, nullable=True)  # JSON: address, phone, email
    education = Column(Text, nullable=True)  # Education details
    
    # Relationship
    user = relationship("User", backref="consultant_profile")
    schedules = relationship("ConsultantSchedule", back_populates="consultant", cascade="all, delete-orphan")
    breaks = relationship("ScheduleBreak", back_populates="consultant", cascade="all, delete-orphan")
    appointments = relationship("Appointment", back_populates="consultant", cascade="all, delete-orphan")

    # --- Onboarding questionnaire fields (stored in Cloud DB) ---
    date_of_birth = Column(Date, nullable=True)           # From onboarding form
    languages = Column(Text, nullable=True)               # JSON array e.g. ["English", "Hindi"]
    linkedin_url = Column(String(500), nullable=True)     # Optional profile URL
    availability_notes = Column(Text, nullable=True)      # Preferred days/times text

    # ── New application form fields (from SolaceSquad Consultant Application PDF) ──
    city                  = Column(String(100),  nullable=True)  # S1: Location / city
    highest_qualification = Column(String(255),  nullable=True)  # S2: Structured degree level
    referral_source       = Column(String(100),  nullable=True)  # S2: How they found SolaceSquad
    preferred_time        = Column(String(100),  nullable=True)  # S3: Morning/Afternoon/Evening/Any
    preferred_days        = Column(String(100),  nullable=True)  # S3: Weekdays/Weekends/Any Day
    engagement_type       = Column(String(100),  nullable=True)  # S3: Full/Part/Contractual
    intended_hours        = Column(String(100),  nullable=True)  # S3: Hours per week range
    counselling_methods   = Column(Text,         nullable=True)  # S4: JSON — CBT, DBT, REBT, etc.
    expertise_areas       = Column(Text,         nullable=True)  # S5: JSON — Anxiety, Stress, etc.
    qacp_certified        = Column(Boolean,      nullable=True)  # S6: Queer Affirmative cert
    target_audience       = Column(String(255),  nullable=True)  # S6: Individual/Minor/Family etc.
    delivery_methods      = Column(String(255),  nullable=True)  # S7: Video/Phone/In-person etc.
    psychometric_tests    = Column(Boolean,      nullable=True)  # S7: Administers tests
    clinical_experience   = Column(String(50),   nullable=True)  # S7: 0-2/2-4/4-8/8+ yrs range
    recommendations       = Column(Text,         nullable=True)  # S9: JSON — referee name+contact
    cv_url                = Column(String(1000), nullable=True)  # GCS URL of uploaded CV (PDF)
    photo_url             = Column(String(1000), nullable=True)  # GCS URL of profile photo

    # ── Wellness classification ──
    # deferred = excluded from bulk SELECT. Column may not exist in DB if migration
    # was skipped (insufficient ALTER TABLE permissions). Never access unless certain.
    wellness_category     = deferred(Column(String(20), nullable=True))

    # ── Payout / bank details ──
    # deferred = excluded from bulk SELECT (newer columns, may not exist in all envs)
    bank_account_name     = deferred(Column(String(255),  nullable=True))
    bank_account_number   = deferred(Column(String(50),   nullable=True))
    bank_ifsc             = deferred(Column(String(20),   nullable=True))
    bank_name             = deferred(Column(String(100),  nullable=True))
    upi_id                = deferred(Column(String(100),  nullable=True))

class ConsultantSchedule(Base):
    """Consultant availability schedule"""
    __tablename__ = "consultant_schedules"
    
    id = Column(Integer, primary_key=True, index=True)
    consultant_id = Column(Integer, ForeignKey("consultant_profiles.id"), nullable=False)
    day_of_week = Column(Integer, nullable=False)  # 0=Monday, 6=Sunday
    start_time = Column(String(10), nullable=False)  # Format: "HH:MM"
    end_time = Column(String(10), nullable=False)  # Format: "HH:MM"
    is_active = Column(Boolean, default=True)
    
    # Relationship
    consultant = relationship("ConsultantProfile", back_populates="schedules")


class ScheduleBreak(Base):
    """Break periods within a consultant's working day"""
    __tablename__ = "consultant_schedule_breaks"

    id = Column(Integer, primary_key=True, index=True)
    consultant_id = Column(Integer, ForeignKey("consultant_profiles.id"), nullable=False)
    day_of_week = Column(Integer, nullable=False)   # 0=Monday, 6=Sunday
    break_start = Column(String(10), nullable=False)  # "HH:MM"
    break_end   = Column(String(10), nullable=False)  # "HH:MM"

    # Relationship
    consultant = relationship("ConsultantProfile", back_populates="breaks")



class Appointment(Base):
    """Appointment booking between user and consultant"""
    __tablename__ = "appointments"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    consultant_id = Column(Integer, ForeignKey("consultant_profiles.id"), nullable=False)
    appointment_date = Column(DateTime, nullable=False)
    duration_minutes = Column(Integer, default=60)
    status = Column(String(50), default="scheduled")  # scheduled, completed, cancelled
    notes = Column(Text, nullable=True)
    consent_to_record = Column(Boolean, default=False, nullable=True)
    consent_to_share_data = Column(Boolean, default=False, nullable=True)
    is_test = Column(Boolean, nullable=False, default=False, server_default='false')
    reminder_sent = Column(Boolean, default=False, nullable=False, server_default='false')
    mirror_reminder_sent = Column(Boolean, default=False, nullable=False, server_default='false')
    push_30m_sent = Column(Boolean, default=False, nullable=False, server_default='false')
    mirror_push_30m_sent = Column(Boolean, default=False, nullable=False, server_default='false')
    reschedule_free = Column(Boolean, default=False, nullable=False, server_default='false')
    refund_status = Column(String(50), nullable=True)
    red_flagged = Column(Boolean, default=False, nullable=False, server_default='false')
    red_flag_reason = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    user = relationship("User", backref="appointments")
    consultant = relationship("ConsultantProfile", back_populates="appointments")


class Message(Base):
    """Message model for communication between users and consultants"""
    __tablename__ = "messages"
    
    id = Column(Integer, primary_key=True, index=True)
    sender_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    receiver_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    content = Column(Text, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
    is_read = Column(Boolean, default=False, nullable=False)
    
    # Relationships
    sender = relationship("User", foreign_keys=[sender_id], backref="sent_messages")
    receiver = relationship("User", foreign_keys=[receiver_id], backref="received_messages")


class AIChatHistory(Base):
    """AI Chat history model for storing conversations with AI assistant"""
    __tablename__ = "ai_chat_history"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    message = Column(Text, nullable=False)
    response = Column(Text, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationship
    user = relationship("User", backref="ai_chats")


class CallSession(Base):
    """Call session model for tracking voice calls between users and consultants"""
    __tablename__ = "call_sessions"
    
    id = Column(Integer, primary_key=True, index=True)
    appointment_id = Column(Integer, ForeignKey("appointments.id"), nullable=False, unique=True)
    room_id = Column(String(255), unique=True, nullable=False, index=True)
    
    # Participants
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    consultant_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Call timing
    scheduled_start = Column(DateTime, nullable=False)
    scheduled_end = Column(DateTime, nullable=False)
    actual_start = Column(DateTime, nullable=True)
    actual_end = Column(DateTime, nullable=True)
    duration_seconds = Column(Integer, nullable=True)  # Actual call duration
    
    # Call status
    status = Column(String(50), default="pending")  # pending, active, completed, cancelled, failed
    
    # Recording info
    recording_url = Column(String(500), nullable=True)  # Path to audio file
    recording_size_bytes = Column(Integer, nullable=True)
    has_video = Column(Boolean, default=False, nullable=True)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    appointment = relationship("Appointment", backref="call_session")
    user = relationship("User", foreign_keys=[user_id], backref="user_call_sessions")
    consultant = relationship("User", foreign_keys=[consultant_id], backref="consultant_call_sessions")
    transcription = relationship("CallTranscription", back_populates="call_session", uselist=False, cascade="all, delete-orphan")


class CallTranscription(Base):
    """Call transcription and summary model"""
    __tablename__ = "call_transcriptions"
    
    id = Column(Integer, primary_key=True, index=True)
    call_session_id = Column(Integer, ForeignKey("call_sessions.id"), nullable=False, unique=True)
    
    # Participants (denormalized for easy access)
    user_name = Column(String(255), nullable=False)
    consultant_name = Column(String(255), nullable=False)
    consultation_time = Column(DateTime, nullable=False)
    
    # Transcription
    full_transcription = Column(Text, nullable=True)  # Complete word-for-word transcription
    transcription_status = Column(String(50), default="pending")  # pending, processing, completed, failed
    
    # AI Summary
    summary = Column(Text, nullable=True)  # AI-generated summary of conversation
    summary_status = Column(String(50), default="pending")  # pending, processing, completed, failed
    
    # Key insights (optional structured data)
    key_points = Column(Text, nullable=True)  # JSON array of key discussion points
    action_items = Column(Text, nullable=True)  # JSON array of action items
    sentiment = Column(String(50), nullable=True)  # overall, positive, neutral, negative
    
    # Processing metadata
    transcription_engine = Column(String(100), nullable=True)  # e.g., "whisper", "google-speech"
    summary_engine = Column(String(100), nullable=True)  # e.g., "gpt-4", "claude"
    processing_time_seconds = Column(Float, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    transcription_completed_at = Column(DateTime, nullable=True)
    summary_completed_at = Column(DateTime, nullable=True)
    
    # Relationship
    call_session = relationship("CallSession", back_populates="transcription")


class AuditLog(Base):
    """
    Audit Log model for HIPAA compliance.
    Tracks all access to PHI (Protected Health Information).
    """
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)  # Nullable for failed logins
    event_type = Column(String(100), nullable=False)  # e.g., "login", "view_vitals", "export_data"
    resource_type = Column(String(100), nullable=True)  # e.g., "vitals_record", "appointment"
    resource_id = Column(String(100), nullable=True)  # ID of the resource accessed
    details = Column(Text, nullable=True)  # Additional details (JSON or text)
    ip_address = Column(String(45), nullable=True)  # IPv4 or IPv6
    user_agent = Column(String(255), nullable=True)
    status = Column(String(50), default="success")  # success, failure
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationship
    user = relationship("User", foreign_keys=[user_id])


class Prescription(Base):
    """Prescription model for consultant prescriptions"""
    __tablename__ = "prescriptions"

    id = Column(Integer, primary_key=True, index=True)
    consultant_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    appointment_id = Column(Integer, ForeignKey("appointments.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    diagnosis = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)

    # Relationships
    consultant = relationship("User", foreign_keys=[consultant_id], backref="issued_prescriptions")
    user = relationship("User", foreign_keys=[user_id], backref="received_prescriptions")
    appointment = relationship("Appointment", backref="prescription")
    items = relationship("PrescriptionItem", back_populates="prescription", cascade="all, delete-orphan")


class PrescriptionItem(Base):
    """Individual medication items in a prescription"""
    __tablename__ = "prescription_items"

    id = Column(Integer, primary_key=True, index=True)
    prescription_id = Column(Integer, ForeignKey("prescriptions.id"), nullable=False)
    medication_name = Column(String(255), nullable=False)
    dosage = Column(String(100), nullable=True) # e.g. "500mg"
    frequency = Column(String(100), nullable=True) # e.g. "Twice daily"
    duration = Column(String(100), nullable=True) # e.g. "5 days"
    instructions = Column(Text, nullable=True) # e.g. "Take after food"

    # Relationship
    prescription = relationship("Prescription", back_populates="items")


class PatientNote(Base):
    __tablename__ = "patient_notes"
    
    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("users.id"))
    consultant_id = Column(Integer, ForeignKey("users.id"))
    content = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    patient = relationship("User", foreign_keys=[patient_id], backref="notes")
    consultant = relationship("User", foreign_keys=[consultant_id], backref="authored_notes")


class ConsultantRating(Base):
    """Rating given by a user to a consultant after a session"""
    __tablename__ = "consultant_ratings"
    
    id = Column(Integer, primary_key=True, index=True)
    appointment_id = Column(Integer, ForeignKey("appointments.id"), nullable=False, unique=True) # One rating per appointment
    consultant_id = Column(Integer, ForeignKey("consultant_profiles.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    rating = Column(Float, nullable=False) # 1.0 to 5.0
    feedback = Column(Text, nullable=True)
    is_anonymous = Column(Boolean, default=False, nullable=False)  # User chose to post anonymously
    display_name = Column(String(255), nullable=True)  # Resolved name: real name or 'Anonymous User'
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    appointment = relationship("Appointment", backref="rating_entry")
    consultant = relationship("ConsultantProfile", backref="ratings")
    user = relationship("User", backref="given_ratings")


class VideoFolder(Base):
    """Folders for organizing exercise videos"""
    __tablename__ = "video_folders"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    thumbnail_url = Column(String(500), nullable=True) # Cover image for the folder tile
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    videos = relationship("Video", back_populates="folder", cascade="all, delete-orphan")


class Video(Base):
    """Individual exercise videos"""
    __tablename__ = "videos"
    
    id = Column(Integer, primary_key=True, index=True)
    folder_id = Column(Integer, ForeignKey("video_folders.id"), nullable=False)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    video_url = Column(String(500), nullable=False) # GCS URL or YouTube Link
    thumbnail_url = Column(String(500), nullable=True)
    duration_seconds = Column(Integer, default=0)
    is_youtube = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    folder = relationship("VideoFolder", back_populates="videos")
    logs = relationship("UserExerciseLog", back_populates="video", cascade="all, delete-orphan")


class UserExerciseLog(Base):
    """Tracking user watch time for videos"""
    __tablename__ = "user_exercise_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    video_id = Column(Integer, ForeignKey("videos.id"), nullable=False)
    watched_seconds = Column(Integer, default=0)
    completed = Column(Boolean, default=False)
    last_watched_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    user = relationship("User", backref="exercise_logs")
    video = relationship("Video", back_populates="logs")


class DemoVideo(Base):
    """Admin-managed demo/explainer videos shared with users and/or consultants"""
    __tablename__ = "demo_videos"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    video_url = Column(String(500), nullable=False)  # GCS URL or YouTube link
    is_youtube = Column(Boolean, default=False, nullable=False, server_default='false')
    # "users", "consultants", or "both"
    share_with = Column(String(20), nullable=False, default="both", server_default="'both'")
    created_at = Column(DateTime, default=datetime.utcnow)



class HomePageSection(Base):
    """Model for storing dynamic homepage sections"""
    __tablename__ = "homepage_sections"

    
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)  # Section title/name
    html_content = Column(Text, nullable=False)  # HTML content
    css_content = Column(Text, nullable=True)  # Optional CSS
    order_index = Column(Integer, default=0)  # Display order
    is_published = Column(Boolean, default=False)  # Draft or live
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    
    # Relationship
    creator = relationship("User", backref="homepage_sections")


class WorkoutLog(Base):
    """Daily workout log entries submitted by users"""
    __tablename__ = "workout_logs"

    id           = Column(Integer, primary_key=True, index=True)
    user_id      = Column(Integer, ForeignKey("users.id"), nullable=False)
    log_date     = Column(Date, nullable=False)
    workout_type = Column(String(100), nullable=False)
    duration_min = Column(Integer, default=0)
    step_count   = Column(Integer, default=0)
    calories     = Column(Integer, default=0)
    notes        = Column(Text, nullable=True)
    created_at   = Column(DateTime, default=datetime.utcnow)
    lifestyle_score = Column(Integer, nullable=True)  # 0/25/50/75/100 per daily total minutes
    distance_km  = Column(Float, nullable=True)        # distance in km (walking/running/cycling)
    source       = Column(String(50), nullable=True)   # e.g. "google_health", "apple_health"
    external_id  = Column(String(255), nullable=True)  # provider's activity ID for dedup

    user = relationship("User", backref="workout_logs")


class DailyWellnessScore(Base):
    """
    Daily composite wellness score — upserted every time the user does a vital
    scan, mood update, or workout log entry.

    Overall Wellness = 50% * Health + 35% * Emotional Wellness + 15% * Lifestyle
    """
    __tablename__ = "daily_wellness_scores"

    id                      = Column(Integer, primary_key=True, index=True)
    user_id                 = Column(Integer, ForeignKey("users.id"), nullable=False)
    score_date              = Column(Date, nullable=False)           # date of the score (UTC)
    health_score            = Column(Float,   nullable=True)         # latest vitals health score
    emotional_wellness_score= Column(Integer, nullable=True)         # latest mood score
    lifestyle_score         = Column(Integer, nullable=True)         # today's workout score (0 if none)
    overall_wellness_score  = Column(Float,   nullable=True)         # weighted composite
    updated_at              = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", backref="daily_wellness_scores")


class SiteSettings(Base):
    """
    Admin-controlled site-wide feature flags and settings.
    Uses a simple key/value store pattern (one row per setting).
    """
    __tablename__ = "site_settings"

    id         = Column(Integer, primary_key=True, index=True)
    key        = Column(String(100), unique=True, nullable=False, index=True)
    value      = Column(String(500), nullable=False, default="true")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    updated_by = Column(Integer, ForeignKey("users.id"), nullable=True)


# ─────────────────────────────────────────────────────────────────────────────
# Subscription / Monetisation Models
# ─────────────────────────────────────────────────────────────────────────────

class UsagePlan(Base):
    """
    A subscription plan that admin can create (Free, White, Green, Blue, …).
    is_free=True → no payment required to subscribe.
    is_default=True → new users are auto-enrolled in this plan.
    """
    __tablename__ = "usage_plans"

    id            = Column(Integer, primary_key=True, index=True)
    name          = Column(String(100), nullable=False)         # e.g. "Free", "White"
    description   = Column(Text, nullable=True)
    price         = Column(Float, nullable=False, default=0.0)  # ₹ per billing cycle (discounted / actual price)
    original_price= Column(Float, nullable=True)               # pre-discount price (shown crossed out); None = no discount
    billing_cycle = Column(String(20), nullable=False, default="monthly")  # monthly / annual / one_time
    is_free       = Column(Boolean, nullable=False, default=True)
    is_default    = Column(Boolean, nullable=False, default=False)  # one plan should be default
    is_active     = Column(Boolean, nullable=False, default=True)
    colour        = Column(String(20), nullable=True, default="#0d9488")  # hex for UI badge
    display_order = Column(Integer, nullable=False, default=0)
    created_at    = Column(DateTime, default=datetime.utcnow)
    updated_at    = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    caps          = relationship("PlanFeatureCap",   back_populates="plan", cascade="all, delete-orphan")
    subscriptions = relationship("UserSubscription", back_populates="plan")


class PlanFeatureCap(Base):
    """
    A single feature's limits within a given plan.

    For ai_chat:
      limit_first_week  — messages allowed during the user's first 7 days on the plan
      limit_post_week   — messages allowed per calendar month after the first week
      (for all other features these two fields equal limit_value)

    limit_value = -1  means unlimited.
    extend_price = 0  means no pay-to-extend option.
    """
    __tablename__ = "plan_feature_caps"

    id                = Column(Integer, primary_key=True, index=True)
    plan_id           = Column(Integer, ForeignKey("usage_plans.id"), nullable=False)
    feature_key       = Column(String(100), nullable=False)    # e.g. "ai_chat"
    feature_name      = Column(String(200), nullable=False)    # display label
    # Standard limit (used for non-ai_chat features; equals limit_post_week for ai_chat)
    limit_value       = Column(Integer, nullable=False, default=-1)   # -1 = unlimited
    # Two-tier AI chat limits
    limit_first_week  = Column(Integer, nullable=True)   # NULL = use limit_value
    limit_post_week   = Column(Integer, nullable=True)   # NULL = use limit_value
    # Custom message when limit is hit
    limit_hit_message = Column(Text, nullable=True)
    # Pay-to-extend top-up
    extend_price      = Column(Float, nullable=False, default=0.0)    # 0 = no top-up option
    extend_quota      = Column(Integer, nullable=False, default=0)    # messages / sessions added

    # Relationship
    plan = relationship("UsagePlan", back_populates="caps")


class UserSubscription(Base):
    """
    Tracks which plan a user is currently subscribed to.
    Only one ACTIVE subscription per user at a time.
    """
    __tablename__ = "user_subscriptions"

    id              = Column(Integer, primary_key=True, index=True)
    user_id         = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    plan_id         = Column(Integer, ForeignKey("usage_plans.id"), nullable=False)
    status          = Column(String(30), nullable=False, default="active")
    # active / expired / cancelled / pending_payment
    started_at      = Column(DateTime, nullable=False, default=datetime.utcnow)
    expires_at      = Column(DateTime, nullable=True)  # NULL = no expiry (lifetime / free)
    payment_status  = Column(String(30), nullable=True)  # paid / free / pending
    razorpay_order_id   = Column(String(100), nullable=True)
    razorpay_payment_id = Column(String(100), nullable=True)
    # True for new users and plan UPGRADES; False for downgrades/renewals
    # Controls whether the user receives the 500-message first-week welcome pool
    is_first_week_bonus_eligible = Column(Boolean, nullable=False, default=True)
    created_at      = Column(DateTime, default=datetime.utcnow)

    # ── Auto-renewal fields (added for recurring billing) ──────────────────
    auto_renew           = Column(Boolean, nullable=False, default=False)  # opt-in: off by default
    next_renewal_at      = Column(DateTime, nullable=True)   # scheduled renewal date
    renewal_fail_count   = Column(Integer,  nullable=False, default=0)  # consecutive failures
    grace_period_used    = Column(Boolean,  nullable=False, default=False)  # one lifetime grace only
    grace_period_ends_at = Column(DateTime, nullable=True)   # 3-day grace window end
    cancelled_at         = Column(DateTime, nullable=True)   # when user cancelled auto-renew
    pause_started_at     = Column(DateTime, nullable=True)   # when subscription was paused
    voucher_code         = Column(String(50), nullable=True)
    is_test              = Column(Boolean, nullable=False, default=_is_test_mode_default, server_default='false')

    # Relationships
    user = relationship("User", backref="subscriptions")
    plan = relationship("UsagePlan", back_populates="subscriptions")


class FeatureUsageLog(Base):
    """
    Monthly counter: how many times a user used a feature in a given month.
    month_key format: "YYYY-MM"
    """
    __tablename__ = "feature_usage_logs"

    id          = Column(Integer, primary_key=True, index=True)
    user_id     = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    feature_key = Column(String(100), nullable=False)
    month_key   = Column(String(25),  nullable=False)   # "YYYY-MM" | "YYYY-MM-DD" | "week1-YYYY-MM-DD" | "lifetime"
    usage_count = Column(Integer,     nullable=False, default=0)
    updated_at  = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", backref="feature_usage_logs")


class FeatureUsageTopUp(Base):
    """
    Logs each pay-to-extend quota top-up purchase.
    Quota is credited when payment is verified.
    """
    __tablename__ = "feature_usage_top_ups"

    id                  = Column(Integer, primary_key=True, index=True)
    user_id             = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    feature_key         = Column(String(100), nullable=False)
    month_key           = Column(String(25),  nullable=False)
    quota_added         = Column(Integer, nullable=False)
    amount_paid         = Column(Float,   nullable=False)
    razorpay_order_id   = Column(String(100), nullable=True)
    razorpay_payment_id = Column(String(100), nullable=True)
    status              = Column(String(30), nullable=False, default="pending")  # pending / paid
    created_at          = Column(DateTime, default=datetime.utcnow)
    voucher_code         = Column(String(50), nullable=True)
    is_test              = Column(Boolean, nullable=False, default=_is_test_mode_default, server_default='false')

    user = relationship("User", backref="feature_top_ups")


class Voucher(Base):
    """
    Vouchers / Discount codes created by admin.
    """
    __tablename__ = "vouchers"

    id                   = Column(Integer, primary_key=True, index=True)
    code                 = Column(String(50), unique=True, index=True, nullable=False)
    discount_type        = Column(String(20), nullable=False, default="percentage")  # percentage / flat
    discount_value       = Column(Float, nullable=False, default=0.0)
    applies_to           = Column(String(20), nullable=False, default="all")  # all / plan / package
    applies_to_id        = Column(String(50), nullable=True)  # Plan ID or Pack ID (e.g. "S", "M", "L")
    assigned_user_emails = Column(Text, nullable=True)  # comma-separated list of allowed user emails (null = all)
    valid_until          = Column(DateTime, nullable=True)  # expiration date
    is_active            = Column(Boolean, nullable=False, default=True)
    created_at           = Column(DateTime, default=datetime.utcnow)
    updated_at           = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# ══════════════════════════════════════════════════════════════════════════════
# FINANCE MODULE
# ══════════════════════════════════════════════════════════════════════════════

class PaymentTransaction(Base):
    """
    Unified payment ledger — every Razorpay payment on the platform.
    Covers subscriptions, feature top-ups, and consultation bookings.
    """
    __tablename__ = "payment_transactions"

    id                   = Column(Integer, primary_key=True, index=True)
    user_id              = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    transaction_type     = Column(String(50), nullable=False)
    # "subscription" | "top_up" | "consultation" | "refund"

    amount               = Column(Float, nullable=False)
    currency             = Column(String(5), nullable=False, default="INR")
    status               = Column(String(30), nullable=False, default="pending")
    # "pending" | "completed" | "failed" | "refunded"

    razorpay_order_id    = Column(String(100), nullable=True, index=True)
    razorpay_payment_id  = Column(String(100), nullable=True, index=True)
    razorpay_signature   = Column(String(300), nullable=True)

    # What this payment is for
    related_entity_type  = Column(String(50), nullable=True)   # "subscription" | "top_up" | "appointment"
    related_entity_id    = Column(Integer, nullable=True)       # FK to that table's id

    # Human-readable description
    description          = Column(Text, nullable=True)   # e.g. "White Plan (Monthly) — April 2026"

    # Unique sequential invoice number (SS-YYYY-NNNNN)
    invoice_number       = Column(String(30), nullable=True, unique=True, index=True)

    # Refund tracking
    refunded_at          = Column(DateTime, nullable=True)
    refund_reason        = Column(Text, nullable=True)
    voucher_code         = Column(String(50), nullable=True)

    created_at           = Column(DateTime, default=datetime.utcnow)
    updated_at           = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Test vs Live Razorpay mode flag
    # True  = transaction created while Razorpay was in TEST mode (no real money)
    # False = transaction created in LIVE mode (real money)
    is_test              = Column(Boolean, nullable=False, default=False, server_default='false')

    # Relationships
    user = relationship("User", backref="payment_transactions")


class ConsultantEarning(Base):
    """
    Per-session earnings record for a consultant.
    Created when a consultation payment is successfully verified.
    Tracks the gross amount, platform fee, and consultant's payout.
    """
    __tablename__ = "consultant_earnings"

    id                     = Column(Integer, primary_key=True, index=True)
    consultant_user_id     = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    appointment_id         = Column(Integer, ForeignKey("appointments.id"), nullable=True)
    payment_transaction_id = Column(Integer, ForeignKey("payment_transactions.id"), nullable=True)

    gross_amount           = Column(Float, nullable=False)   # Amount user paid
    platform_fee_pct       = Column(Float, nullable=True)    # legacy — nullable; fee split tracked via gross_amount and consultant_payout
    platform_fee           = Column(Float, nullable=False)   # Actual fee amount
    consultant_payout      = Column(Float, nullable=False)   # gross_amount - platform_fee

    payout_status          = Column(String(30), nullable=False, default="pending")
    # "pending" | "processing" | "paid" | "on_hold"
    payout_date            = Column(DateTime, nullable=True)
    payout_reference       = Column(String(100), nullable=True)  # Bank transfer ref / UPI UTR
    admin_notes            = Column(Text, nullable=True)

    # True if this earning was generated through the Mirror/test environment
    is_test                = Column(Boolean, nullable=False, default=False)

    created_at             = Column(DateTime, default=datetime.utcnow)
    updated_at             = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    event_workshop_id      = Column(Integer, ForeignKey("event_workshops.id"), nullable=True)

    # Relationships
    consultant = relationship("User", backref="consultant_earnings")
    appointment = relationship("Appointment", backref="earning")
    transaction = relationship("PaymentTransaction", backref="earning")
    event_workshop = relationship("EventWorkshop", backref="earnings")


# ── Blog Platform ─────────────────────────────────────────────────────────────

class BlogPost(Base):
    """Wellness blog posts authored and published by admins."""
    __tablename__ = "blog_posts"

    id                = Column(Integer, primary_key=True, index=True)
    slug              = Column(String(220), unique=True, nullable=False, index=True)
    title             = Column(String(300), nullable=False)
    excerpt           = Column(Text, nullable=True)          # 2-sentence teaser for cards
    content           = Column(Text, nullable=True)          # Full HTML body
    cover_image_url   = Column(String(1000), nullable=True)  # Unsplash or any image URL
    category          = Column(String(60), nullable=False, default="General")
    # Mental | Physical | Professional | General
    tags              = Column(Text, nullable=True)           # JSON array: '["anxiety","sleep"]'
    author_name       = Column(String(150), nullable=False, default="SolaceSquad Team")
    author_avatar_url = Column(String(500), nullable=True)
    status            = Column(String(20), nullable=False, default="draft")
    # draft | published
    published_at      = Column(DateTime, nullable=True)
    read_time_minutes = Column(Integer, nullable=True, default=3)
    view_count        = Column(Integer, nullable=False, default=0)

    created_at        = Column(DateTime, default=datetime.utcnow)
    updated_at        = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# ── Sync-X: Fitness Plugin Integration Tokens ─────────────────────────────────

class FitnessIntegration(Base):
    """
    Stores OAuth tokens for all Sync-X fitness provider integrations.
    One row per (user, provider). Replaces per-column tokens on User model.
    Providers: google_health | strava | garmin | samsung_health | apple_health
    """
    __tablename__ = "fitness_integrations"

    id               = Column(Integer, primary_key=True, index=True)
    user_id          = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    provider         = Column(String(50), nullable=False)
    # e.g. "google_health" | "strava" | "garmin" | "samsung_health"

    refresh_token    = Column(Text, nullable=True)
    access_token     = Column(Text, nullable=True)
    token_expires_at = Column(DateTime, nullable=True)

    is_connected     = Column(Boolean, default=True)
    connected_at     = Column(DateTime, default=datetime.utcnow)

    last_sync_at     = Column(DateTime, nullable=True)
    last_sync_status = Column(String(50), nullable=True)   # "success" | "error" | "partial"
    last_sync_error  = Column(Text, nullable=True)

    metadata_json    = Column(Text, nullable=True)         # provider-specific extras (JSON)

    # Note: workout_logs.source, workout_logs.external_id,
    #       vitals_records.source are added via migrate_sync_x.py


class DiagnosisReport(Base):
    """User diagnosis and lab reports"""
    __tablename__ = "diagnosis_reports"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    file_path = Column(String(512), nullable=False)  # GCS URL
    file_name = Column(String(255), nullable=False)  # Original filename
    description = Column(Text, nullable=True)
    test_date = Column(Date, nullable=False)  # Date when the tests were done
    tag = Column(String(100), nullable=True)  # Category tag
    is_shared = Column(Boolean, default=False, nullable=False)  # Share status with scheduled consultants
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationship
    user = relationship("User", backref="reports")


class EventWorkshop(Base):
    """Events and Workshops published by admins for the wellness community."""
    __tablename__ = "event_workshops"

    id                  = Column(Integer, primary_key=True, index=True)
    type                = Column(String(50), nullable=False)  # 'event' or 'workshop'
    title               = Column(String(255), nullable=False)
    slug                = Column(String(255), unique=True, nullable=False, index=True)
    short_summary       = Column(Text, nullable=True)
    full_content        = Column(Text, nullable=True)         # HTML / formatted rich text
    author_name         = Column(String(255), nullable=False, default="SolaceSquad Team")
    author_bio          = Column(Text, nullable=True)
    author_image        = Column(String(500), nullable=True)
    expert_name         = Column(String(255), nullable=True)
    expert_bio          = Column(Text, nullable=True)
    ai_assisted_content = Column(Boolean, default=False, nullable=False)
    featured_image      = Column(String(500), nullable=True)
    event_date          = Column(Date, nullable=False)
    start_time          = Column(String(50), nullable=True)   # e.g., "18:00"
    end_time            = Column(String(50), nullable=True)     # e.g., "19:30"
    venue               = Column(String(255), nullable=True)
    event_mode          = Column(String(50), nullable=False, default="online")  # 'online' | 'offline' | 'hybrid'
    registration_link   = Column(String(500), nullable=True)
    show_registration   = Column(Boolean, default=True, nullable=False)
    show_date_time      = Column(Boolean, default=True, nullable=False)
    show_location       = Column(Boolean, default=True, nullable=False)
    status              = Column(String(50), nullable=False, default="draft")  # 'draft' | 'published' | 'archived'
    sort_order          = Column(Integer, nullable=False, default=0)
    created_at          = Column(DateTime, default=datetime.utcnow)
    updated_at          = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    consultant_id       = Column(Integer, ForeignKey("consultant_profiles.id"), nullable=True)
    payout_amount       = Column(Float, default=0.0, nullable=True)

    # Relationships
    gallery_items = relationship("EventGalleryItem", backref="event", cascade="all, delete-orphan", order_by="EventGalleryItem.sort_order")
    consultant = relationship("ConsultantProfile", backref="events_workshops")


class EventGalleryItem(Base):
    """Media assets (images or videos) associated with an event or workshop."""
    __tablename__ = "event_gallery_items"

    id         = Column(Integer, primary_key=True, index=True)
    event_id   = Column(Integer, ForeignKey("event_workshops.id", ondelete="CASCADE"), nullable=False, index=True)
    media_type = Column(String(50), nullable=False)  # 'image' or 'video'
    source     = Column(String(500), nullable=False)  # URL or GCS path
    thumbnail  = Column(String(500), nullable=True)   # GCS URL for video poster image
    caption    = Column(String(255), nullable=True)
    alt_text   = Column(String(255), nullable=True)
    sort_order = Column(Integer, nullable=False, default=0)


class UserDeviceToken(Base):
    """User device token for push notifications (FCM)"""
    __tablename__ = "user_device_tokens"
    
    id          = Column(Integer, primary_key=True, index=True)
    user_id     = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    fcm_token   = Column(String(500), unique=True, nullable=False, index=True)
    device_type = Column(String(50), default="android", nullable=False)
    updated_at  = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class PushNotificationSchedule(Base):
    """Configuration table for scheduled remote push notifications"""
    __tablename__ = "push_notification_schedules"

    id = Column(Integer, primary_key=True, index=True)
    notification_type = Column(String(100), unique=True, nullable=False, index=True) # mood_checkin, vital_scan, workout_log, appointment_reminder, recharge_reminder, emora_low_balance
    title = Column(String(200), nullable=False)
    body = Column(String(500), nullable=False)
    is_enabled = Column(Boolean, default=True, nullable=False, server_default='true')
    repeat_cycle = Column(String(50), default="daily", nullable=False) # hourly, daily, weekly, monthly
    delivery_time = Column(String(50), nullable=True) # e.g. "09:00"
    day_of_week = Column(Integer, nullable=True) # 0-6 (Sunday-Saturday) for weekly
    day_of_month = Column(Integer, nullable=True) # 1-31 for monthly
    threshold_value = Column(Integer, nullable=True) # e.g. 5 messages, 3 days before recharge
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

