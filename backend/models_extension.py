
from sqlalchemy import Column, Integer, String, DateTime, Float, ForeignKey, Text
from sqlalchemy.orm import relationship
from datetime import datetime
from models import Base

class ConsultantRating(Base):
    """Rating given by a user to a consultant after a session"""
    __tablename__ = "consultant_ratings"
    
    id = Column(Integer, primary_key=True, index=True)
    appointment_id = Column(Integer, ForeignKey("appointments.id"), nullable=False, unique=True) # One rating per appointment
    consultant_id = Column(Integer, ForeignKey("consultant_profiles.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    rating = Column(Float, nullable=False) # 1.0 to 5.0
    feedback = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    appointment = relationship("Appointment", backref="rating_entry")
    consultant = relationship("ConsultantProfile", backref="ratings")
    user = relationship("User", backref="given_ratings")
