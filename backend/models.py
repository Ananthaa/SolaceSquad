from sqlalchemy import create_engine, Column, Integer, String, DateTime, Float, Boolean, ForeignKey, Text
from sqlalchemy.sql import func
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime
import bcrypt

# Create base class for models
Base = declarative_base()


class User(Base):
    """User model for authentication and profile data"""
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    name = Column(String(255), nullable=False)
    password_hash = Column(String(255), nullable=False)
    user_type = Column(String(50), nullable=False, default="user")  # 'user' or 'consultant'
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    first_login = Column(DateTime, nullable=True)  # Track first login for "Active since"
    last_login = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    phone_number = Column(String(20), unique=True, index=True, nullable=True)
    
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
        """Verify a password against the hash"""
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
    phone_number = Column(String(20), index=True, nullable=False)
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
    heart_rate = Column(Integer, nullable=True)  # BPM
    spo2 = Column(Integer, nullable=True)  # Oxygen saturation percentage (0-100)
    respiratory_rate = Column(Integer, nullable=True)  # Breaths per minute
    temperature = Column(Float, nullable=True)  # Celsius
    blood_pressure_systolic = Column(Integer, nullable=True)  # mmHg
    blood_pressure_diastolic = Column(Integer, nullable=True)  # mmHg
    
    # Metadata
    confidence = Column(Float, default=0.0, nullable=False)
    scan_duration = Column(Integer, default=0, nullable=False)  # in seconds
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
    mood_rating = Column(String(50), nullable=False)  # Can be numeric (1-5) or text
    notes = Column(Text, nullable=True)
    
    # Relationship
    user = relationship("User", back_populates="mood_entries")


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
    is_available = Column(Boolean, default=True)
    
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
    appointments = relationship("Appointment", back_populates="consultant", cascade="all, delete-orphan")


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
