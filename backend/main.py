from fastapi import FastAPI, Request, Depends, HTTPException
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse
from starlette.middleware.sessions import SessionMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from sqlalchemy.orm import Session
import os
import secrets
import uuid
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import database and models
from database import init_db, get_db, get_db_session
from models import User, PasswordResetToken, VitalsRecord, ConsultantProfile, ConsultantSchedule, Appointment, Message, AIChatHistory, CallSession, MoodEntry, Prescription, PrescriptionItem, PatientNote, OTPVerification, UserProfile
from email_utils import send_password_reset_email, send_welcome_email
from openai_chat import openai_chat  # Using OpenAI for initial deployment, will switch to Vertex AI in next update
from audit_logging import AuditLogger

# Import Socket.IO for WebRTC signaling
from call_signaling import sio, get_socket_app

# Initialize FastAPI app
app = FastAPI(
    title="SolaceSquad - Wellbeing Platform",
    description="Professional wellbeing consultants platform with voice calling",
    version="1.0.0"
)

# Add cache control middleware to prevent browser caching
class NoCacheMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        # Don't cache HTML pages (but allow caching of static assets)
        if "text/html" in response.headers.get("content-type", ""):
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
        return response

app.add_middleware(NoCacheMiddleware)

# Initialize database on startup
@app.on_event("startup")
async def startup_event():
    """Initialize database on application startup"""
    init_db()
    print("[OK] Database initialized")

# Add session middleware for user data storage
# In production, use a secure secret key from environment variables
SECRET_KEY = os.getenv("SECRET_KEY", secrets.token_urlsafe(32))
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY)

# Get the directory of this file
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Mount static files (CSS, JS, images)
app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")

# Setup Jinja2 templates
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))

# PWA Routes
@app.get("/sw.js", include_in_schema=False)
async def get_service_worker():
    return FileResponse(os.path.join(BASE_DIR, "static", "sw.js"), media_type="application/javascript")

@app.get("/manifest.json", include_in_schema=False)
async def get_manifest():
    return FileResponse(os.path.join(BASE_DIR, "static", "manifest.json"), media_type="application/json")

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def get_initials(name: str) -> str:
    """Generate initials from a name"""
    name_parts = name.split()
    if len(name_parts) >= 2:
        return f"{name_parts[0][0]}{name_parts[-1][0]}".upper()
    elif len(name_parts) == 1:
        return name_parts[0][:2].upper()
    else:
        return "U"

def get_nav_items(user_type: str) -> list:
    """Get navigation items based on user type"""
    if user_type == "consultant":
        return [
            {'icon': 'layout-dashboard', 'label': 'Dashboard', 'href': '/consultant', 'key': 'dashboard'},
            {'icon': 'users', 'label': 'Clients', 'href': '/consultant/clients', 'key': 'clients'},
            {'icon': 'calendar', 'label': 'Schedule', 'href': '/consultant/schedule', 'key': 'schedule'},
            {'icon': 'message-circle', 'label': 'Messages', 'href': '/consultant/messages', 'key': 'messages'},
            {'icon': 'file-text', 'label': 'Wellness Summary Report', 'href': '/consultant/prescriptions', 'key': 'prescriptions'},
            {'icon': 'user', 'label': 'Profile', 'href': '/consultant/profile', 'key': 'profile'}
        ]
    else:  # user
        return [
            {'icon': 'layout-dashboard', 'label': 'Dashboard', 'href': '/app', 'key': 'dashboard'},
            {'icon': 'activity', 'label': 'Vitals & Scan', 'href': '/app/vitals', 'key': 'vitals'},
            {'icon': 'message-circle', 'label': 'Messages', 'href': '/app/messages', 'key': 'messages'},
            {'icon': 'book-open', 'label': 'Daily Journal', 'href': '/app/journal', 'key': 'journal'},
            {'icon': 'calendar', 'label': 'Grooming', 'href': '/app/grooming', 'key': 'grooming'},
            {'icon': 'message-square', 'label': 'AI Assistant', 'href': '/app/ai-chat', 'key': 'ai-chat'},
            {'icon': 'dumbbell', 'label': 'Exercise', 'href': '/app/exercise', 'key': 'exercise'},
            {'icon': 'file-text', 'label': 'Wellness Summary Report', 'href': '/prescriptions', 'key': 'prescriptions'},
            {'icon': 'mic', 'label': 'Call Recordings', 'href': '/recordings', 'key': 'recordings'},
            {'icon': 'sparkles', 'label': 'Find Consultant', 'href': '/app/consultants', 'key': 'consultants'},
            {'icon': 'user', 'label': 'Profile', 'href': '/app/profile', 'key': 'profile'}
        ]

# ============================================================================
# MARKETING ROUTES
# ============================================================================

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Marketing home page with hero, services, testimonials"""
    return templates.TemplateResponse(
        "pages/home.html",
        {
            "request": request,
            "page_title": "SolaceSquad - Your Wellbeing Partner",
            "active_page": "home"
        }
    )

# ============================================================================
# USER DASHBOARD ROUTES
# ============================================================================

@app.get("/app", response_class=HTMLResponse)
async def user_dashboard(request: Request, db: Session = Depends(get_db)):
    """User dashboard - main authenticated area"""
    # TODO: Add authentication check
    # Get user data from session, fallback to default
    print(f"DEBUG: Session data: {dict(request.session)}")
    user_name = request.session.get("user_name", "User")
    user_id = request.session.get("user_id")
    
    # Enforce authentication
    if not user_id:
        return RedirectResponse(url="/login", status_code=303)
        
    # Initialize variables with defaults
    heart_rate_display = "N/A"
    journal_entries_count = 0
    sessions_count = 0
    wellbeing_status = "Good"
    physical_health_score = 0
        
    try:
        user_id = int(str(user_id))
    except (ValueError, TypeError):
        # Invalid user_id format
        request.session.clear()
        return RedirectResponse(url="/login", status_code=303)

    # Fetch user details from database
    current_user = db.query(User).filter(User.id == user_id).first()
    
    # If user not found (e.g. deleted account), force logout
    if not current_user:
        request.session.clear()
        return RedirectResponse(url="/login", status_code=303)
        
    # Update display name from database (Primary: Preferred Name, Secondary: Full Name, Fallback: Account Name)
    user_name = current_user.name
    
    user_profile = db.query(UserProfile).filter(UserProfile.user_id == user_id).first()
    if user_profile:
        if user_profile.preferred_name:
            user_name = user_profile.preferred_name
        elif user_profile.full_name:
            user_name = user_profile.full_name
            
    # Sync session with latest name
    request.session["user_name"] = user_name
            
    # Recompute initials with updated name
    initials = get_initials(user_name)

    # Get latest vitals record
    latest_vitals = db.query(VitalsRecord).filter(
        VitalsRecord.user_id == user_id
    ).order_by(VitalsRecord.timestamp.desc()).first()
        
    print(f"DEBUG: latest_vitals = {latest_vitals}")
    if latest_vitals:
        heart_rate_display = latest_vitals.heart_rate
        print(f"DEBUG: Setting heart_rate_display = {heart_rate_display}")
    else:
        print(f"DEBUG: No vitals found for user_id={user_id}")
    
    # Get count of mood entries (journal entries)
    from models import MoodEntry, ConsultantInteraction
    journal_entries_count = db.query(MoodEntry).filter(
        MoodEntry.user_id == user_id
    ).count()
    
    # Get count of consultant sessions
    sessions_count = db.query(ConsultantInteraction).filter(
        ConsultantInteraction.user_id == user_id
    ).count()
    
    physical_health_score = 0
    if user_id and latest_vitals and latest_vitals.health_score:
        physical_health_score = int(latest_vitals.health_score)

    user_data = {
        "name": user_name,
        "initials": initials,
        "stats": {
            "heart_rate": heart_rate_display,
            "journal_entries": journal_entries_count,
            "sessions": sessions_count,
            "wellbeing": wellbeing_status,
            "health_score": physical_health_score
        }
    }
    
    # AUDIT LOG: Dashboard Access
    if user_id:
        AuditLogger.log_event(
            db, 
            event_type="view_dashboard", 
            user_id=user_id, 
            details="User viewed main dashboard with health summary",
            request=request
        )
    
    return templates.TemplateResponse(
        "pages/user_dashboard.html",
        {
            "request": request,
            "page_title": "Dashboard - SolaceSquad",
            "user": user_data,
            "user_name": user_name,
            "user_initials": initials,
            "user_type": "user",
            "active_page": "dashboard",
            "nav_items": get_nav_items("user")
        }
    )

@app.get("/api/patients/{patient_id}/history")
async def get_patient_history(patient_id: int, request: Request, db: Session = Depends(get_db)):
    """Get summarized patient history for consultant"""
    user_id = request.session.get("user_id")
    # Verify requester is a consultant
    consultant = db.query(ConsultantProfile).filter(ConsultantProfile.user_id == user_id).first()
    if not consultant:
         return {"success": False, "error": "Unauthorized"}
         
    patient = db.query(User).filter(User.id == patient_id).first()
    if not patient:
        return {"success": False, "error": "Patient not found"}
        
    # Gather data
    # 1. Past Wellness Summary Reports
    prescriptions = db.query(Prescription).filter(Prescription.user_id == patient_id).order_by(Prescription.created_at.desc()).all()
    rx_summary = []
    for rx in prescriptions:
        rx_summary.append({
            "date": rx.created_at.strftime("%Y-%m-%d"),
            "diagnosis": rx.diagnosis,
            "medications": [item.medication_name for item in rx.items]
        })
        
    # 2. Past Appointments & Notes
    appointments = db.query(Appointment).filter(
        Appointment.user_id == patient_id, 
        Appointment.status == "completed"
    ).order_by(Appointment.appointment_date.desc()).limit(5).all()
    
    appt_summary = []
    for appt in appointments:
        consultant_name = appt.consultant.user.name if appt.consultant else "Unknown"
        appt_summary.append({
            "date": appt.appointment_date.strftime("%Y-%m-%d"),
            "consultant": consultant_name,
            "notes": appt.notes
        })
        
    # 3. Recent Vitals (Last 3)
    vitals = db.query(VitalsRecord).filter(VitalsRecord.user_id == patient_id).order_by(VitalsRecord.timestamp.desc()).limit(3).all()
    vitals_summary = []
    for v in vitals:
        vitals_summary.append({
            "date": v.timestamp.strftime("%Y-%m-%d %H:%M"),
            "heart_rate": v.heart_rate,
            "condition": "Normal" # Placeholder logic
        })

    return {
        "success": True,
        "patient": {"name": patient.name, "age": 30}, # Age is placeholder as we don't have DOB
        "prescriptions": rx_summary,
        "appointments": appt_summary,
        "vitals": vitals_summary
    }

@app.get("/app/vitals", response_class=HTMLResponse)
async def vitals(request: Request):
    """Camera-based vitals scanning page"""
    # Get user info from session
    user_name = request.session.get("user_name", "User")
    name_parts = user_name.split()
    if len(name_parts) >= 2:
        initials = name_parts[0][0].upper() + name_parts[1][0].upper()
    elif len(name_parts) == 1:
        initials = name_parts[0][:2].upper()
    else:
        initials = "U"
    
    # Get vitals history from session
    vitals_history = request.session.get("vitals_history", [])
    
    return templates.TemplateResponse(
        "pages/vitals.html",
        {
            "request": request,
            "page_title": "Vitals Scanner - SolaceSquad",
            "user_name": user_name,
            "user_initials": initials,
            "user_type": "user",
            "active_page": "vitals",
            "nav_items": get_nav_items("user"),
            "vitals_history": vitals_history
        }
    )

@app.get("/app/vitals/latest-json")
async def get_latest_vitals_json(request: Request, db: Session = Depends(get_db)):
    """API to get latest vitals for JS fallback"""
    user_id = request.session.get("user_id")
    if not user_id:
        return {}
    
    # We want to find the latest non-null value for each vital
    # This is expensive to do perfectly, so we'll grab the last 20 records and merge them
    records = db.query(VitalsRecord).filter(
        VitalsRecord.user_id == user_id
    ).order_by(VitalsRecord.timestamp.desc()).limit(20).all()
    
    latest_vitals = {
        "heart_rate": None,
        "spo2": None,
        "respiratory_rate": None,
        "temperature": None,
        "blood_pressure_systolic": None,
        "blood_pressure_diastolic": None,
        "health_score": None
    }
    
    for r in records:
        if latest_vitals["heart_rate"] is None and r.heart_rate: latest_vitals["heart_rate"] = r.heart_rate
        if latest_vitals["spo2"] is None and r.spo2: latest_vitals["spo2"] = r.spo2
        if latest_vitals["respiratory_rate"] is None and r.respiratory_rate: latest_vitals["respiratory_rate"] = r.respiratory_rate
        if latest_vitals["temperature"] is None and r.temperature: latest_vitals["temperature"] = r.temperature
        if latest_vitals["blood_pressure_systolic"] is None and r.blood_pressure_systolic: latest_vitals["blood_pressure_systolic"] = r.blood_pressure_systolic
        if latest_vitals["blood_pressure_diastolic"] is None and r.blood_pressure_diastolic: latest_vitals["blood_pressure_diastolic"] = r.blood_pressure_diastolic
        if latest_vitals["health_score"] is None and r.health_score: latest_vitals["health_score"] = r.health_score
        
    return latest_vitals

def calculate_health_score(vitals_data: dict, db: Session = None, user_id: int = None) -> float:
    """
    Calculate an overall health score (0-100) based on vitals data.
    Uses standard adult reference ranges.
    If db and user_id are provided, fetches missing data from history.
    """
    # Merge with historical data if missing
    merged_data = vitals_data.copy()
    
    if db and user_id:
        try:
            # Check for missing keys or None values
            missing_keys = [k for k in ["heart_rate", "spo2", "respiratory_rate", "temperature", "blood_pressure_systolic"] 
                           if k not in merged_data or merged_data[k] is None]
            
            if missing_keys:
                # Get recent history to fill gaps
                records = db.query(VitalsRecord).filter(
                    VitalsRecord.user_id == user_id
                ).order_by(VitalsRecord.timestamp.desc()).limit(20).all()
                
                for r in records:
                    if merged_data.get("heart_rate") is None and r.heart_rate: merged_data["heart_rate"] = r.heart_rate
                    if merged_data.get("spo2") is None and r.spo2: merged_data["spo2"] = r.spo2
                    if merged_data.get("respiratory_rate") is None and r.respiratory_rate: merged_data["respiratory_rate"] = r.respiratory_rate
                    if merged_data.get("temperature") is None and r.temperature: merged_data["temperature"] = r.temperature
                    if merged_data.get("blood_pressure_systolic") is None and r.blood_pressure_systolic: merged_data["blood_pressure_systolic"] = r.blood_pressure_systolic
                    if merged_data.get("blood_pressure_diastolic") is None and r.blood_pressure_diastolic: merged_data["blood_pressure_diastolic"] = r.blood_pressure_diastolic
        except Exception as e:
            print(f"Error fetching historical vitals for score: {e}")

    scores = []
    
    # Heart Rate (Normal: 60-100)
    hr = merged_data.get("heart_rate")
    if hr:
        hr = int(hr)
        if 60 <= hr <= 100:
            scores.append(100)
        elif 50 <= hr < 60 or 100 < hr <= 110:
            scores.append(80)
        elif 40 <= hr < 50 or 110 < hr <= 120:
            scores.append(60)
        else:
            scores.append(40)
            
    # SpO2 (Normal: 95-100)
    spo2 = merged_data.get("spo2")
    if spo2:
        spo2 = int(spo2)
        if spo2 >= 95:
            scores.append(100)
        elif 90 <= spo2 < 95:
            scores.append(80)
        elif 85 <= spo2 < 90:
            scores.append(60)
        else:
            scores.append(40)
            
    # Respiratory Rate (Normal: 12-20)
    rr = merged_data.get("respiratory_rate")
    if rr:
        rr = int(rr)
        if 12 <= rr <= 20:
            scores.append(100)
        elif 8 <= rr < 12 or 20 < rr <= 25:
            scores.append(80)
        else:
            scores.append(60)
            
    # Temperature (Normal: 36.1-37.2)
    temp = merged_data.get("temperature")
    if temp:
        temp = float(temp)
        if 36.1 <= temp <= 37.5:
            scores.append(100)
        elif 35.5 <= temp < 36.1 or 37.5 < temp <= 38.3:
            scores.append(80)
        else:
            scores.append(60)
            
    # Blood Pressure (Normal: <120 and <80)
    sys = merged_data.get("blood_pressure_systolic")
    dia = merged_data.get("blood_pressure_diastolic")
    if sys and dia:
        sys = int(sys)
        dia = int(dia)
        if 90 <= sys <= 120 and 60 <= dia <= 80:
            scores.append(100)
        elif (120 < sys <= 130) or (80 < dia <= 85): # Elevated
            scores.append(85)
        elif (130 < sys <= 140) or (85 < dia <= 90): # Stage 1
            scores.append(70)
        elif (sys > 140) or (dia > 90): # Stage 2
            scores.append(50)
        elif sys < 90 or dia < 60: # Low
            scores.append(60)
        else:
            scores.append(100)
            
    if not scores:
        return 0.0
        
    return float(sum(scores) / len(scores))

@app.post("/app/vitals/save")
async def save_vitals(request: Request, db: Session = Depends(get_db)):
    """Save comprehensive vitals reading to database"""
    try:
        # Check if user is logged in
        user_id = request.session.get("user_id")
        if not user_id:
            return {"success": False, "error": "User not logged in"}
        
        data = await request.json()
        
        # Create vitals record in database with all available measurements
        vitals_record = VitalsRecord(
            user_id=user_id,
            heart_rate=int(data.get("heart_rate")) if data.get("heart_rate") else None,
            spo2=int(data.get("spo2")) if data.get("spo2") else None,
            respiratory_rate=int(data.get("respiratory_rate")) if data.get("respiratory_rate") else None,
            temperature=float(data.get("temperature")) if data.get("temperature") else None,
            blood_pressure_systolic=int(data.get("blood_pressure_systolic")) if data.get("blood_pressure_systolic") else None,
            blood_pressure_diastolic=int(data.get("blood_pressure_diastolic")) if data.get("blood_pressure_diastolic") else None,
            confidence=float(data.get("confidence", 0.0)),
            scan_duration=int(data.get("scan_duration", 0)),
            method=data.get("method", "manual"),
            health_score=calculate_health_score(data, db, user_id)
        )
        
        db.add(vitals_record)
        db.commit()
        db.refresh(vitals_record)
        
        # AUDIT LOG: Vitals Recorded
        AuditLogger.log_event(
            db, 
            event_type="create_vitals", 
            user_id=user_id,
            resource_type="vitals_record",
            resource_id=str(vitals_record.id),
            details=f"Method: {vitals_record.method}, Confidence: {vitals_record.confidence}",
            request=request
        )
        
        # Return vitals entry
        vitals_entry = {
            "timestamp": vitals_record.timestamp.isoformat(),
            "heart_rate": vitals_record.heart_rate,
            "spo2": vitals_record.spo2,
            "respiratory_rate": vitals_record.respiratory_rate,
            "temperature": vitals_record.temperature,
            "blood_pressure_systolic": vitals_record.blood_pressure_systolic,
            "blood_pressure_diastolic": vitals_record.blood_pressure_diastolic,
            "confidence": vitals_record.confidence,
            "scan_duration": vitals_record.scan_duration,
            "method": vitals_record.method,
            "health_score": vitals_record.health_score
        }
        
        return {"success": True, "entry": vitals_entry}
    except Exception as e:
        print(f"Error saving vitals: {str(e)}")
        import traceback
        traceback.print_exc()
        db.rollback()
        return {"success": False, "error": str(e)}

@app.get("/app/vitals/history")
async def get_vitals_history(request: Request, db: Session = Depends(get_db)):
    """Get comprehensive vitals history from database"""
    try:
        # Check if user is logged in
        user_id = request.session.get("user_id")
        if not user_id:
            return {"success": False, "error": "User not logged in", "history": []}
        
        # Query vitals records for this user (last 50, most recent first)
        vitals_records = db.query(VitalsRecord).filter(
            VitalsRecord.user_id == user_id
        ).order_by(VitalsRecord.timestamp.desc()).limit(50).all()
        
        # AUDIT LOG: Vitals History View
        AuditLogger.log_event(
            db, 
            event_type="view_vitals_history", 
            user_id=user_id,
            resource_type="vitals_record",
            details=f"User viewed {len(vitals_records)} vitals history records",
            request=request
        )
        
        # Convert to list of dictionaries with all vitals
        vitals_history = [
            {
                "timestamp": record.timestamp.isoformat(),
                "heart_rate": record.heart_rate,
                "spo2": record.spo2,
                "respiratory_rate": record.respiratory_rate,
                "temperature": record.temperature,
                "blood_pressure_systolic": record.blood_pressure_systolic,
                "blood_pressure_diastolic": record.blood_pressure_diastolic,
                "confidence": record.confidence,
                "scan_duration": record.scan_duration,
                "method": record.method,
                "health_score": record.health_score
            }
            for record in vitals_records
        ]
        
        return {"success": True, "history": vitals_history}
    except Exception as e:
        print(f"Error getting vitals history: {str(e)}")
        import traceback
        traceback.print_exc()
        return {"success": False, "error": str(e), "history": []}

# ============================================================================
# MOOD TRACKING ROUTES
# ============================================================================

@app.post("/app/mood/save")
async def save_mood(request: Request, db: Session = Depends(get_db)):
    """Save mood entry to database"""
    try:
        # Check if user is logged in
        user_id = request.session.get("user_id")
        if not user_id:
            return {"success": False, "error": "User not logged in"}
        
        data = await request.json()
        
        # Validate required fields
        if "mood" not in data:
            return {"success": False, "error": "Mood is required"}
        
        # Create mood entry in database
        from models import MoodEntry
        mood_entry = MoodEntry(
            user_id=user_id,
            mood_rating=data.get("mood"),
            notes=data.get("notes", "")
        )
        
        db.add(mood_entry)
        db.commit()
        db.refresh(mood_entry)
        
        # AUDIT LOG: Mood Recorded
        AuditLogger.log_event(
            db, 
            event_type="create_mood", 
            user_id=user_id,
            resource_type="mood_entry",
            resource_id=str(mood_entry.id),
            details=f"Mood rating: {mood_entry.mood_rating}",
            request=request
        )
        
        return {
            "success": True, 
            "entry": {
                "timestamp": mood_entry.timestamp.isoformat(),
                "mood": mood_entry.mood_rating,
                "notes": mood_entry.notes
            }
        }
    except Exception as e:
        print(f"Error saving mood: {str(e)}")
        db.rollback()
        return {"success": False, "error": str(e)}

@app.get("/app/mood/latest")
async def get_latest_mood(request: Request, db: Session = Depends(get_db)):
    """Get latest mood entry for the user"""
    try:
        # Check if user is logged in
        user_id = request.session.get("user_id")
        if not user_id:
            return {"success": False, "error": "User not logged in", "mood": None}
        
        # Query latest mood entry
        from models import MoodEntry
        latest_mood = db.query(MoodEntry).filter(
            MoodEntry.user_id == user_id
        ).order_by(MoodEntry.timestamp.desc()).first()
        
        if latest_mood:
            return {
                "success": True,
                "mood": {
                    "timestamp": latest_mood.timestamp.isoformat(),
                    "mood_rating": latest_mood.mood_rating,
                    "notes": latest_mood.notes
                }
            }
        else:
            return {"success": True, "mood": None}
    except Exception as e:
        print(f"Error getting latest mood: {str(e)}")
        return {"success": False, "error": str(e), "mood": None}

@app.get("/app/messages", response_class=HTMLResponse)
async def user_messages(request: Request):
    """User messages page"""
    user_name = request.session.get("user_name", "User")
    
    # Generate initials
    name_parts = user_name.split()
    if len(name_parts) >= 2:
        initials = f"{name_parts[0][0]}{name_parts[-1][0]}".upper()
    elif len(name_parts) == 1:
        initials = name_parts[0][:2].upper()
    else:
        initials = "U"
    
    return templates.TemplateResponse(
        "pages/user_messages.html",
        {
            "request": request,
            "page_title": "Messages - SolaceSquad",
            "user_name": user_name,
            "user_initials": initials,
            "user_type": "user",
            "active_page": "messages",
            "nav_items": get_nav_items("user")
        }
    )

@app.get("/app/ai-chat", response_class=HTMLResponse)
async def ai_chat_page(request: Request):
    """AI Chat page"""
    user_name = request.session.get("user_name", "User")
    
    # Generate initials
    name_parts = user_name.split()
    if len(name_parts) >= 2:
        initials = f"{name_parts[0][0]}{name_parts[-1][0]}".upper()
    elif len(name_parts) == 1:
        initials = name_parts[0][:2].upper()
    else:
        initials = "U"
    
    return templates.TemplateResponse(
        "pages/ai_chat.html",
        {
            "request": request,
            "page_title": "AI Assistant - SolaceSquad",
            "user_name": user_name,
            "user_initials": initials,
            "user_type": "user",
            "active_page": "ai-chat",
            "nav_items": get_nav_items("user")
        }
    )

@app.get("/app/profile", response_class=HTMLResponse)
async def user_profile(request: Request, db: Session = Depends(get_db)):
    """User profile page"""
    # Check authentication
    user_id = request.session.get("user_id")
    if not user_id:
        return RedirectResponse(url="/login", status_code=303)
    
    user_name = request.session.get("user_name", "User")
    
    # Generate initials
    initials = get_initials(user_name)
    
    # Get or create user profile
    profile = db.query(UserProfile).filter(UserProfile.user_id == user_id).first()
    if not profile:
        profile = UserProfile(user_id=user_id)
        db.add(profile)
        db.commit()
        db.refresh(profile)
    
    # Get user for email
    user = db.query(User).filter(User.id == user_id).first()
    user_email = user.email if user else ""
    
    # Calculate active since (account creation date)
    active_since = "N/A"
    if user and user.first_login:
        active_since = user.first_login.strftime("%B %d, %Y")
    elif user and user.created_at:
        active_since = user.created_at.strftime("%B %d, %Y")
    
    # Get sessions count (appointments)
    sessions_count = db.query(Appointment).filter(
        Appointment.user_id == user_id
    ).count()
    
    return templates.TemplateResponse(
        "pages/user_profile.html",
        {
            "request": request,
            "page_title": "My Profile - SolaceSquad",
            "user_name": user_name,
            "user_initials": initials,
            "user_type": "user",
            "active_page": "profile",
            "nav_items": get_nav_items("user"),
            "profile": profile,
            "user_email": user_email,
            "active_since": active_since,
            "sessions_count": sessions_count
        }
    )

@app.post("/app/profile/save")
async def save_user_profile(request: Request, db: Session = Depends(get_db)):
    """Save user profile data"""
    try:
        user_id = request.session.get("user_id")
        if not user_id:
            return {"success": False, "error": "User not logged in"}
        
        data = await request.json()
        
        # Get or create profile
        profile = db.query(UserProfile).filter(UserProfile.user_id == user_id).first()
        if not profile:
            profile = UserProfile(user_id=user_id)
            db.add(profile)
        
        # Update profile fields
        profile.full_name = data.get("full_name")
        profile.preferred_name = data.get("preferred_name")
        profile.age = int(data.get("age")) if data.get("age") else None
        profile.gender = data.get("gender")
        profile.height = float(data.get("height")) if data.get("height") else None
        profile.weight = float(data.get("weight")) if data.get("weight") else None
        profile.address = data.get("address")
        profile.contact_email = data.get("alt_email")
        profile.occupation = data.get("occupation")
        profile.medical_history = data.get("medical_history")
        profile.wellness_habits = data.get("wellness_habits")
        profile.about_me = data.get("about_me")
        
        db.commit()
        
        # Update session name if preferred name is set
        if profile.preferred_name:
            request.session["user_name"] = profile.preferred_name
        
        return {"success": True}
    except Exception as e:
        print(f"Error saving user profile: {str(e)}")
        import traceback
        traceback.print_exc()
        db.rollback()
        return {"success": False, "error": str(e)}


# ============================================================================
# CONSULTANT DASHBOARD ROUTES
# ============================================================================

@app.get("/consultant", response_class=HTMLResponse)
async def consultant_dashboard(request: Request):
    """Consultant dashboard - main authenticated area"""
    # TODO: Add authentication check
    # Get consultant data from session, fallback to default
    consultant_name = request.session.get("user_name", "Consultant")
    
    # Generate initials from name
    name_parts = consultant_name.split()
    if len(name_parts) >= 2:
        initials = f"{name_parts[0][0]}{name_parts[-1][0]}".upper()
    elif len(name_parts) == 1:
        initials = name_parts[0][:2].upper()
    else:
        initials = "C"
    
    consultant_data = {
        "name": consultant_name,
        "initials": initials,
        "stats": {
            "active_clients": 24,
            "sessions_scheduled": 12,
            "earnings": "₹45,000",
            "rating": 4.9
        }
    }
    
    return templates.TemplateResponse(
        "pages/consultant_dashboard.html",
        {
            "request": request,
            "page_title": "Consultant Dashboard - SolaceSquad",
            "consultant": consultant_data,
            "user_name": consultant_name,
            "user_initials": initials,
            "user_type": "consultant",
            "active_page": "dashboard",
            "nav_items": get_nav_items("consultant")
        }
    )

@app.get("/consultant/schedule", response_class=HTMLResponse)
async def consultant_schedule(request: Request, db: Session = Depends(get_db)):
    """Consultant schedule management page"""
    consultant_name = request.session.get("user_name", "Consultant")
    user_id = request.session.get("user_id")
    
    # Generate initials
    name_parts = consultant_name.split()
    if len(name_parts) >= 2:
        initials = f"{name_parts[0][0]}{name_parts[-1][0]}".upper()
    elif len(name_parts) == 1:
        initials = name_parts[0][:2].upper()
    else:
        initials = "C"
    
    # Get consultant profile
    consultant_profile = db.query(ConsultantProfile).filter(
        ConsultantProfile.user_id == user_id
    ).first()
    
    # Get schedule if exists
    schedules = []
    if consultant_profile:
        schedules = db.query(ConsultantSchedule).filter(
            ConsultantSchedule.consultant_id == consultant_profile.id
        ).all()
    
    return templates.TemplateResponse(
        "pages/consultant_schedule.html",
        {
            "request": request,
            "page_title": "My Schedule - SolaceSquad",
            "user_name": consultant_name,
            "user_initials": initials,
            "user_type": "consultant",
            "active_page": "schedule",
            "nav_items": get_nav_items("consultant"),
            "schedules": schedules,
            "consultant_profile": consultant_profile
        }
    )

@app.get("/consultant/clients", response_class=HTMLResponse)
async def consultant_clients(request: Request, db: Session = Depends(get_db)):
    """Consultant clients list page"""
    consultant_name = request.session.get("user_name", "Consultant")
    user_id = request.session.get("user_id")
    
    # Generate initials
    name_parts = consultant_name.split()
    if len(name_parts) >= 2:
        initials = f"{name_parts[0][0]}{name_parts[-1][0]}".upper()
    elif len(name_parts) == 1:
        initials = name_parts[0][:2].upper()
    else:
        initials = "C"
    
    # Get consultant profile
    consultant_profile = db.query(ConsultantProfile).filter(
        ConsultantProfile.user_id == user_id
    ).first()
    
    # Get unique clients from appointments
    clients = []
    if consultant_profile:
        appointments = db.query(Appointment).filter(
            Appointment.consultant_id == consultant_profile.id,
            Appointment.status.in_(['scheduled', 'completed'])
        ).all()
        
        # Get unique client IDs
        client_ids = list(set([appt.user_id for appt in appointments]))
        
        # Get client details
        for client_id in client_ids:
            user = db.query(User).filter(User.id == client_id).first()
            if user:
                # Count appointments
                total_sessions = len([a for a in appointments if a.user_id == client_id and a.status == 'completed'])
                upcoming_sessions = len([a for a in appointments if a.user_id == client_id and a.status == 'scheduled'])
                
                clients.append({
                    "id": user.id,
                    "name": user.name,
                    "email": user.email,
                    "total_sessions": total_sessions,
                    "upcoming_sessions": upcoming_sessions
                })
    
    return templates.TemplateResponse(
        "pages/consultant_clients.html",
        {
            "request": request,
            "page_title": "My Clients - SolaceSquad",
            "user_name": consultant_name,
            "user_initials": initials,
            "user_type": "consultant",
            "active_page": "clients",
            "nav_items": get_nav_items("consultant"),
            "clients": clients
        }
    )

@app.get("/consultant/messages", response_class=HTMLResponse)
async def consultant_messages(request: Request):
    """Consultant messages page"""
    consultant_name = request.session.get("user_name", "Consultant")
    
    # Generate initials
    name_parts = consultant_name.split()
    if len(name_parts) >= 2:
        initials = f"{name_parts[0][0]}{name_parts[-1][0]}".upper()
    elif len(name_parts) == 1:
        initials = name_parts[0][:2].upper()
    else:
        initials = "C"
    
    return templates.TemplateResponse(
        "pages/consultant_messages.html",
        {
            "request": request,
            "page_title": "Messages - SolaceSquad",
            "user_name": consultant_name,
            "user_initials": initials,
            "user_type": "consultant",
            "active_page": "messages",
            "nav_items": get_nav_items("consultant")
        }
    )

@app.get("/consultant/profile", response_class=HTMLResponse)
async def consultant_profile_page(request: Request, db: Session = Depends(get_db)):
    """Consultant profile page"""
    consultant_name = request.session.get("user_name", "Consultant")
    user_id = request.session.get("user_id")
    
    # Generate initials
    initials = get_initials(consultant_name)
    
    # Get or create consultant profile
    consultant_profile = db.query(ConsultantProfile).filter(
        ConsultantProfile.user_id == user_id
    ).first()
    
    if not consultant_profile:
        consultant_profile = ConsultantProfile(user_id=user_id)
        db.add(consultant_profile)
        db.commit()
        db.refresh(consultant_profile)
    
    return templates.TemplateResponse(
        "pages/consultant_profile.html",
        {
            "request": request,
            "page_title": "My Profile - SolaceSquad",
            "user_name": consultant_name,
            "user_initials": initials,
            "user_type": "consultant",
            "active_page": "profile",
            "nav_items": get_nav_items("consultant"),
            "consultant_profile": consultant_profile
        }
    )

@app.post("/consultant/profile/save")
async def save_consultant_profile(request: Request, db: Session = Depends(get_db)):
    """Save consultant profile data"""
    try:
        user_id = request.session.get("user_id")
        if not user_id:
            return {"success": False, "error": "User not logged in"}
        
        data = await request.json()
        
        # Get or create profile
        consultant_profile = db.query(ConsultantProfile).filter(
            ConsultantProfile.user_id == user_id
        ).first()
        
        if not consultant_profile:
            consultant_profile = ConsultantProfile(user_id=user_id)
            db.add(consultant_profile)
        
        # Update profile fields
        consultant_profile.full_name = data.get("full_name")
        consultant_profile.age = int(data.get("age")) if data.get("age") else None
        consultant_profile.gender = data.get("gender")
        consultant_profile.height = float(data.get("height")) if data.get("height") else None
        consultant_profile.weight = float(data.get("weight")) if data.get("weight") else None
        consultant_profile.contact_details = data.get("contact_details")
        consultant_profile.education = data.get("education")
        consultant_profile.specialization = data.get("specialization")
        consultant_profile.experience_years = int(data.get("experience_years", 0))
        consultant_profile.bio = data.get("bio")
        
        db.commit()
        
        return {"success": True}
    except Exception as e:
        print(f"Error saving consultant profile: {str(e)}")
        import traceback
        traceback.print_exc()
        db.rollback()
        return {"success": False, "error": str(e)}


@app.get("/login", response_class=HTMLResponse)
async def login(request: Request):
    """Login page"""
    return templates.TemplateResponse(
        "pages/auth/login.html",
        {
            "request": request,
            "page_title": "Login - SolaceSquad"
        }
    )

@app.post("/login")
async def login_post(request: Request, db: Session = Depends(get_db)):
    """Handle login form submission with password validation"""
    try:
        # Get form data
        form_data = await request.form()
        user_email = form_data.get("email", "").strip()
        user_password = form_data.get("password", "")
        
        # Validate inputs
        if not user_email or not user_password:
            return templates.TemplateResponse(
                "pages/auth/login.html",
                {
                    "request": request,
                    "page_title": "Login - SolaceSquad",
                    "error": "Please provide both email and password"
                }
            )
        
        # Query database for user
        user = db.query(User).filter(User.email == user_email).first()
        

        # Check if user exists and password is correct
        if not user or not user.verify_password(user_password):
            # AUDIT LOG: Failed Login
            AuditLogger.log_event(
                db, 
                event_type="login_failed", 
                details=f"Failed login attempt for email: {user_email}",
                status="failure",
                request=request
            )
            
            return templates.TemplateResponse(
                "pages/auth/login.html",
                {
                    "request": request,
                    "page_title": "Login - SolaceSquad",
                    "error": "Invalid email or password"
                }
            )
        
        # Check if account is active
        if not user.is_active:
            return templates.TemplateResponse(
                "pages/auth/login.html",
                {
                    "request": request,
                    "page_title": "Login - SolaceSquad",
                    "error": "Your account has been deactivated. Please contact support."
                }
            )
        
        # Update last login timestamp and set first_login if null
        if not user.first_login:
            user.first_login = datetime.utcnow()
        user.update_last_login()
        db.commit()
        
        # AUDIT LOG: Successful Login
        AuditLogger.log_event(
            db, 
            event_type="login_success", 
            user_id=user.id,
            details="User logged in successfully",
            request=request
        )
        
        # Store user data in session
        request.session["user_id"] = user.id
        request.session["user_name"] = user.name
        request.session["user_email"] = user.email
        request.session["user_type"] = user.user_type
        
        # Redirect based on user type
        if user.user_type == "consultant":
            return RedirectResponse(url="/consultant", status_code=303)
        elif user.user_type == "admin":
            return RedirectResponse(url="/admin", status_code=303)
        else:
            return RedirectResponse(url="/app", status_code=303)
            
    except Exception as e:
        print(f"Login error: {str(e)}")
        return templates.TemplateResponse(
            "pages/auth/login.html",
            {
                "request": request,
                "page_title": "Login - SolaceSquad",
                "error": "An error occurred during login. Please try again."
            }
        )


import random
import string

@app.get("/signup", response_class=HTMLResponse)
async def signup(request: Request):
    """Signup page"""
    return templates.TemplateResponse(
        "pages/auth/signup_with_otp.html",
        {
            "request": request,
            "page_title": "Sign Up - SolaceSquad"
        }
    )

@app.post("/api/auth/otp/send")
async def send_otp(request: Request, db: Session = Depends(get_db)):
    """Send OTP to phone number if account doesn't exist - HIPAA Compliant"""
    try:
        data = await request.json()
        phone = data.get("phone_number")
        
        # Validate phone number format
        if not phone or len(phone) < 10:
             return {"success": False, "error": "Invalid phone number"}
             
        # HIPAA: Audit log for OTP request
        AuditLogger.log_event(
            db, 
            event_type="otp_requested", 
            details=f"OTP requested for phone number ending in {phone[-4:]}",
            request=request
        )
             
        # Check if user exists
        existing_user = db.query(User).filter(User.phone_number == phone).first()
        if existing_user:
            # HIPAA: Audit failed attempt
            AuditLogger.log_event(
                db, 
                event_type="otp_denied_existing_user", 
                details=f"OTP denied - account exists for phone ending in {phone[-4:]}",
                status="failure",
                request=request
            )
            return {"success": False, "error": "Account with this phone number already exists. Please login.", "code": "ACCOUNT_EXISTS"}
            
        # Generate cryptographically secure OTP
        # Using secrets module for HIPAA-compliant random generation
        import secrets as crypto_secrets
        otp = ''.join([str(crypto_secrets.randbelow(10)) for _ in range(6)])
        
        # Store in DB (invalidate old OTP for this phone)
        db.query(OTPVerification).filter(OTPVerification.phone_number == phone).delete()
        
        # Create new OTP entry
        new_otp = OTPVerification(
            phone_number=phone,
            otp_code=otp,
            expires_at=datetime.utcnow() + timedelta(minutes=10)  # 10 minute expiry for security
        )
        db.add(new_otp)
        db.commit()
        
        # HIPAA: Audit log OTP generation (never log actual OTP)
        AuditLogger.log_event(
            db, 
            event_type="otp_generated", 
            details=f"OTP generated for phone ending in {phone[-4:]}, expires in 10 minutes",
            request=request
        )
        
        # TODO: Integrate with HIPAA-compliant SMS gateway (Twilio, AWS SNS with encryption)
        # For now, print to server console for development
        import sys
        print(f"\n{'='*60}", flush=True, file=sys.stderr)
        print(f"🔐 OTP for {phone}: {otp}", flush=True, file=sys.stderr)
        print(f"   Expires: {(datetime.utcnow() + timedelta(minutes=10)).strftime('%H:%M:%S')}", flush=True, file=sys.stderr)
        print(f"{'='*60}\n", flush=True, file=sys.stderr)
        
        # In production, remove otp_debug to comply with HIPAA
        # Never expose sensitive data in API responses
        is_development = os.getenv("ENVIRONMENT", "development") == "development"
        response_data = {"success": True}
        
        if is_development:
            response_data["otp_debug"] = otp  # Only for dev/testing
            response_data["note"] = "OTP visible only in development mode"
        
        return response_data
        
    except Exception as e:
        # HIPAA: Audit log error
        AuditLogger.log_event(
            db, 
            event_type="otp_error", 
            details=f"Error during OTP generation: {str(e)}",
            status="failure",
            request=request
        )
        print(f"Error sending OTP: {e}", flush=True, file=sys.stderr)
        import traceback
        traceback.print_exc()
        return {"success": False, "error": "Internal server error"}

@app.post("/signup")
async def signup_post(request: Request, db: Session = Depends(get_db)):
    """Handle signup form submission with OTP verification"""
    try:
        # Get form data
        form_data = await request.form()
        user_name = form_data.get("name", "").strip()
        user_email = form_data.get("email", "").strip().lower()
        user_password = form_data.get("password", "")
        phone_number = form_data.get("phone_number", "").strip()
        otp_input = form_data.get("otp", "").strip()
        user_type = form_data.get("user_type", "user")
        
        # Validate inputs
        if not user_name or not user_email or not user_password or not phone_number or not otp_input:
            return templates.TemplateResponse(
                "pages/auth/signup_with_otp.html",
                {
                    "request": request,
                    "page_title": "Sign Up - SolaceSquad",
                    "error": "All fields including OTP are required"
                }
            )
        
        # 1. Verify OTP
        otp_record = db.query(OTPVerification).filter(
            OTPVerification.phone_number == phone_number,
            OTPVerification.otp_code == otp_input,
            OTPVerification.expires_at > datetime.utcnow()
        ).first()
        
        if not otp_record:
             return templates.TemplateResponse(
                "pages/auth/signup_with_otp.html",
                {
                    "request": request,
                    "page_title": "Sign Up - SolaceSquad",
                    "error": "Invalid or expired OTP"
                }
            )
            
        # 2. Check uniqueness
        if db.query(User).filter(User.email == user_email).first():
            return templates.TemplateResponse(
                "pages/auth/signup_with_otp.html",
                {
                    "request": request,
                    "page_title": "Sign Up - SolaceSquad",
                    "error": "Email is already registered"
                }
            )
            
        if db.query(User).filter(User.phone_number == phone_number).first():
            return templates.TemplateResponse(
                "pages/auth/signup_with_otp.html",
                {
                    "request": request,
                    "page_title": "Sign Up - SolaceSquad",
                    "error": "Phone number is already registered"
                }
            )
        
        # 3. Create User
        new_user = User(
            email=user_email,
            name=user_name,
            user_type=user_type,
            phone_number=phone_number,
            is_active=True
        )
        new_user.set_password(user_password)
        
        db.add(new_user)
        # Mark OTP as verified/used (delete it)
        db.delete(otp_record)
        
        db.commit()
        db.refresh(new_user)
        
        # AUDIT LOG: User Registration
        AuditLogger.log_event(
            db, 
            event_type="user_signup", 
            user_id=new_user.id,
            details=f"New user registration via OTP. Phone: {phone_number}",
            request=request
        )

        
        # Send welcome email (optional, non-blocking)
        try:
            send_welcome_email(user_email, user_name)
        except Exception as e:
            print(f"Failed to send welcome email: {str(e)}")
        
        # Store user data in session
        request.session["user_id"] = new_user.id
        request.session["user_name"] = new_user.name
        request.session["user_email"] = new_user.email
        request.session["user_type"] = new_user.user_type
        
        # Redirect based on user type
        if user_type == "consultant":
            return RedirectResponse(url="/consultant", status_code=303)
        else:
            return RedirectResponse(url="/app", status_code=303)
            
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"Signup error: {str(e)}")
        db.rollback()
        return templates.TemplateResponse(
            "pages/auth/signup_with_otp.html",
            {
                "request": request,
                "page_title": "Sign Up - SolaceSquad",
                "error": str(e)
            }
        )

# ============================================================================
# PASSWORD RECOVERY ROUTES
# ============================================================================

@app.get("/forgot-password", response_class=HTMLResponse)
async def forgot_password(request: Request):
    """Forgot password page"""
    return templates.TemplateResponse(
        "pages/auth/forgot_password.html",
        {
            "request": request,
            "page_title": "Forgot Password - SolaceSquad"
        }
    )

@app.post("/forgot-password")
async def forgot_password_post(request: Request, db: Session = Depends(get_db)):
    """Handle forgot password form submission"""
    try:
        form_data = await request.form()
        user_email = form_data.get("email", "").strip().lower()
        
        if not user_email:
            return templates.TemplateResponse(
                "pages/auth/forgot_password.html",
                {
                    "request": request,
                    "page_title": "Forgot Password - SolaceSquad",
                    "error": "Please provide your email address"
                }
            )
        
        # Look up user (but don't reveal if email exists for security)
        user = db.query(User).filter(User.email == user_email).first()
        
        if user:
            # Generate unique reset token
            reset_token = str(uuid.uuid4())
            
            # Create password reset token record
            token_record = PasswordResetToken(
                user_id=user.id,
                token=reset_token,
                expires_at=datetime.utcnow() + timedelta(hours=24)
            )
            db.add(token_record)
            db.commit()
            
            # Send password reset email
            try:
                send_password_reset_email(user_email, reset_token, user.name)
            except Exception as e:
                print(f"Failed to send reset email: {str(e)}")
        
        # Always show success message (security best practice)
        return templates.TemplateResponse(
            "pages/auth/forgot_password.html",
            {
                "request": request,
                "page_title": "Forgot Password - SolaceSquad",
                "success": "If an account exists with that email, you will receive password reset instructions."
            }
        )
        
    except Exception as e:
        print(f"Forgot password error: {str(e)}")
        return templates.TemplateResponse(
            "pages/auth/forgot_password.html",
            {
                "request": request,
                "page_title": "Forgot Password - SolaceSquad",
                "error": "An error occurred. Please try again."
            }
        )

@app.get("/reset-password/{token}", response_class=HTMLResponse)
async def reset_password(request: Request, token: str, db: Session = Depends(get_db)):
    """Reset password page with token validation"""
    try:
        # Find token in database
        token_record = db.query(PasswordResetToken).filter(
            PasswordResetToken.token == token,
            PasswordResetToken.used == False,
            PasswordResetToken.expires_at > datetime.utcnow()
        ).first()
        
        if not token_record:
            return templates.TemplateResponse(
                "pages/auth/reset_password.html",
                {
                    "request": request,
                    "page_title": "Reset Password - SolaceSquad",
                    "error": "Invalid or expired reset link",
                    "token": None
                }
            )
        
        return templates.TemplateResponse(
            "pages/auth/reset_password.html",
            {
                "request": request,
                "page_title": "Reset Password - SolaceSquad",
                "token": token
            }
        )
        
    except Exception as e:
        print(f"Reset password GET error: {str(e)}")
        return templates.TemplateResponse(
            "pages/auth/reset_password.html",
            {
                "request": request,
                "page_title": "Reset Password - SolaceSquad",
                "error": "An error occurred",
                "token": None
            }
        )

@app.post("/reset-password/{token}")
async def reset_password_post(request: Request, token: str, db: Session = Depends(get_db)):
    """Handle password reset form submission"""
    try:
        form_data = await request.form()
        new_password = form_data.get("password", "")
        confirm_password = form_data.get("confirm_password", "")
        
        # Validate passwords
        if not new_password or not confirm_password:
            return templates.TemplateResponse(
                "pages/auth/reset_password.html",
                {
                    "request": request,
                    "page_title": "Reset Password - SolaceSquad",
                    "error": "Please provide both password fields",
                    "token": token
                }
            )
        
        if new_password != confirm_password:
            return templates.TemplateResponse(
                "pages/auth/reset_password.html",
                {
                    "request": request,
                    "page_title": "Reset Password - SolaceSquad",
                    "error": "Passwords do not match",
                    "token": token
                }
            )
        
        if len(new_password) < 8:
            return templates.TemplateResponse(
                "pages/auth/reset_password.html",
                {
                    "request": request,
                    "page_title": "Reset Password - SolaceSquad",
                    "error": "Password must be at least 8 characters long",
                    "token": token
                }
            )
        
        # Find and validate token
        token_record = db.query(PasswordResetToken).filter(
            PasswordResetToken.token == token,
            PasswordResetToken.used == False,
            PasswordResetToken.expires_at > datetime.utcnow()
        ).first()
        
        if not token_record:
            return templates.TemplateResponse(
                "pages/auth/reset_password.html",
                {
                    "request": request,
                    "page_title": "Reset Password - SolaceSquad",
                    "error": "Invalid or expired reset link",
                    "token": None
                }
            )
        
        # Get user and update password
        user = db.query(User).filter(User.id == token_record.user_id).first()
        if not user:
            return templates.TemplateResponse(
                "pages/auth/reset_password.html",
                {
                    "request": request,
                    "page_title": "Reset Password - SolaceSquad",
                    "error": "User not found",
                    "token": None
                }
            )
        
        # Update password
        user.set_password(new_password)
        
        # Mark token as used
        token_record.used = True
        
        db.commit()
        
        # Redirect to login with success message
        return templates.TemplateResponse(
            "pages/auth/login.html",
            {
                "request": request,
                "page_title": "Login - SolaceSquad",
                "success": "Password reset successful! Please login with your new password."
            }
        )
        
    except Exception as e:
        print(f"Reset password POST error: {str(e)}")
        db.rollback()
        return templates.TemplateResponse(
            "pages/auth/reset_password.html",
            {
                "request": request,
                "page_title": "Reset Password - SolaceSquad",
                "error": "An error occurred. Please try again.",
                "token": token
            }
        )

# ============================================================================
# TEST ENDPOINTS
# ============================================================================

@app.get("/test-session")
async def test_session(request: Request):
    """Test endpoint to verify session is working"""
    # Set a test value
    request.session["test_key"] = "test_value"
    request.session["user_name"] = "Test Session User"
    
    # Read it back
    return {
        "session_data": dict(request.session),
        "test_key": request.session.get("test_key"),
        "user_name": request.session.get("user_name")
    }

# ============================================================================
# APPOINTMENT SCHEDULING ROUTES
# ============================================================================

@app.get("/app/consultants", response_class=HTMLResponse)
async def list_consultants(request: Request, db: Session = Depends(get_db)):
    """List available consultants for booking"""
    # 1. Get User Context (Robust Name Resolution)
    user_id = request.session.get("user_id")
    if not user_id:
        return RedirectResponse(url="/login", status_code=303)
        
    try:
        user_id = int(str(user_id))
    except (ValueError, TypeError):
        request.session.clear()
        return RedirectResponse(url="/login", status_code=303)

    user_name = request.session.get("user_name", "User")
    
    current_user = db.query(User).filter(User.id == user_id).first()
    if not current_user:
        request.session.clear()
        return RedirectResponse(url="/login", status_code=303)
        
    # Update name from DB
    user_name = current_user.name
    user_profile = db.query(UserProfile).filter(UserProfile.user_id == user_id).first()
    if user_profile:
        if user_profile.preferred_name:
            user_name = user_profile.preferred_name
        elif user_profile.full_name:
            user_name = user_profile.full_name
            
    initials = get_initials(user_name)
    
    # 2. Get Consultants (Safer Query)
    # Query Profile directly and join User
    consultant_profiles = db.query(ConsultantProfile, User).join(
        User, ConsultantProfile.user_id == User.id
    ).filter(
        User.user_type == "consultant",
        User.is_active == True,
        ConsultantProfile.is_available == True
    ).all()
    
    # Format consultant data
    consultant_list = []
    for profile, user in consultant_profiles:
        consultant_list.append({
            "id": profile.id,
            "user_id": user.id,
            "name": user.name,
            "specialization": profile.specialization or "General Wellbeing",
            "bio": profile.bio or "Experienced wellbeing consultant",
            "experience_years": profile.experience_years,
            "rating": profile.rating,
            "hourly_rate": profile.hourly_rate or 0
        })

    
    return templates.TemplateResponse(
        "pages/consultants.html",
        {
            "request": request,
            "page_title": "Find a Consultant - SolaceSquad",
            "user_name": user_name,
            "user_initials": initials,
            "user_type": "user",
            "active_page": "consultants",
            "consultants": consultant_list
        }
    )


@app.get("/api/consultants/{consultant_id}/schedule")
async def get_consultant_schedule(consultant_id: int, db: Session = Depends(get_db)):
    """Get consultant's availability schedule"""
    try:
        # Get consultant profile
        consultant = db.query(ConsultantProfile).filter(
            ConsultantProfile.id == consultant_id
        ).first()
        
        if not consultant:
            return {"success": False, "error": "Consultant not found"}
        
        # Get schedule
        schedules = db.query(ConsultantSchedule).filter(
            ConsultantSchedule.consultant_id == consultant_id,
            ConsultantSchedule.is_active == True
        ).all()
        
        # Format schedule data
        schedule_data = []
        for schedule in schedules:
            schedule_data.append({
                "id": schedule.id,
                "day_of_week": schedule.day_of_week,
                "start_time": schedule.start_time,
                "end_time": schedule.end_time
            })
        
        # Get existing appointments for the next 30 days
        start_date = datetime.utcnow()
        end_date = start_date + timedelta(days=30)
        
        appointments = db.query(Appointment).filter(
            Appointment.consultant_id == consultant_id,
            Appointment.appointment_date >= start_date,
            Appointment.appointment_date <= end_date,
            Appointment.status == "scheduled"
        ).all()
        
        booked_slots = [
            {
                "date": appt.appointment_date.isoformat(),
                "duration": appt.duration_minutes
            }
            for appt in appointments
        ]
        
        return {
            "success": True,
            "consultant_name": consultant.user.name,
            "schedule": schedule_data,
            "booked_slots": booked_slots
        }
    except Exception as e:
        print(f"Error getting consultant schedule: {str(e)}")
        return {"success": False, "error": str(e)}

@app.post("/api/appointments/book")
async def book_appointment(request: Request, db: Session = Depends(get_db)):
    """Book an appointment with a consultant"""
    try:
        user_id = request.session.get("user_id")
        if not user_id:
            return {"success": False, "error": "User not logged in"}
        
        data = await request.json()
        
        # Validate required fields
        if not all(k in data for k in ["consultant_id", "appointment_date"]):
            return {"success": False, "error": "Missing required fields"}
        
        # Parse appointment date
        appointment_date = datetime.fromisoformat(data["appointment_date"].replace("Z", "+00:00"))
        
        # Check if consultant exists
        consultant = db.query(ConsultantProfile).filter(
            ConsultantProfile.id == data["consultant_id"]
        ).first()
        
        if not consultant:
            return {"success": False, "error": "Consultant not found"}
        
        # Check if slot is available
        existing_appointment = db.query(Appointment).filter(
            Appointment.consultant_id == data["consultant_id"],
            Appointment.appointment_date == appointment_date,
            Appointment.status == "scheduled"
        ).first()
        
        if existing_appointment:
            return {"success": False, "error": "This time slot is already booked"}
        
        # Create appointment
        appointment = Appointment(
            user_id=user_id,
            consultant_id=data["consultant_id"],
            appointment_date=appointment_date,
            duration_minutes=data.get("duration_minutes", 60),
            notes=data.get("notes", "")
        )
        
        db.add(appointment)
        db.commit()
        db.refresh(appointment)
        
        return {
            "success": True,
            "appointment": {
                "id": appointment.id,
                "consultant_name": consultant.user.name,
                "appointment_date": appointment.appointment_date.isoformat(),
                "duration_minutes": appointment.duration_minutes,
                "status": appointment.status
            }
        }
    except Exception as e:
        print(f"Error booking appointment: {str(e)}")
        db.rollback()
        return {"success": False, "error": str(e)}

@app.get("/api/appointments/user")
async def get_user_appointments(request: Request, db: Session = Depends(get_db)):
    """Get all appointments for the logged-in user"""
    try:
        user_id = request.session.get("user_id")
        if not user_id:
            return {"success": False, "error": "User not logged in", "appointments": []}
        
        appointments = db.query(Appointment).filter(
            Appointment.user_id == user_id
        ).order_by(Appointment.appointment_date.desc()).all()
        
        appointment_list = []
        for appt in appointments:
            appointment_list.append({
                "id": appt.id,
                "consultant_name": appt.consultant.user.name,
                "consultant_specialization": appt.consultant.specialization,
                "appointment_date": appt.appointment_date.isoformat(),
                "duration_minutes": appt.duration_minutes,
                "status": appt.status,
                "notes": appt.notes
            })
        
        return {"success": True, "appointments": appointment_list}
    except Exception as e:
        print(f"Error getting user appointments: {str(e)}")
        return {"success": False, "error": str(e), "appointments": []}

@app.get("/api/appointments/consultant")
async def get_consultant_appointments(request: Request, db: Session = Depends(get_db)):
    """Get all appointments for the logged-in consultant"""
    try:
        user_id = request.session.get("user_id")
        user_type = request.session.get("user_type")
        
        if not user_id or user_type != "consultant":
            return {"success": False, "error": "Not authorized", "appointments": []}
        
        # Get consultant profile
        consultant_profile = db.query(ConsultantProfile).filter(
            ConsultantProfile.user_id == user_id
        ).first()
        
        if not consultant_profile:
            return {"success": False, "error": "Consultant profile not found", "appointments": []}
        
        appointments = db.query(Appointment).filter(
            Appointment.consultant_id == consultant_profile.id
        ).order_by(Appointment.appointment_date.desc()).all()
        
        appointment_list = []
        for appt in appointments:
            appointment_list.append({
                "id": appt.id,
                "client_name": appt.user.name,
                "client_email": appt.user.email,
                "appointment_date": appt.appointment_date.isoformat(),
                "duration_minutes": appt.duration_minutes,
                "status": appt.status,
                "notes": appt.notes
            })
        
        return {"success": True, "appointments": appointment_list}
    except Exception as e:
        print(f"Error getting consultant appointments: {str(e)}")
        return {"success": False, "error": str(e), "appointments": []}

@app.post("/api/appointments/{appointment_id}/cancel")
async def cancel_appointment(appointment_id: int, request: Request, db: Session = Depends(get_db)):
    """Cancel an appointment"""
    try:
        user_id = request.session.get("user_id")
        if not user_id:
            return {"success": False, "error": "User not logged in"}
        
        appointment = db.query(Appointment).filter(
            Appointment.id == appointment_id
        ).first()
        
        if not appointment:
            return {"success": False, "error": "Appointment not found"}
        
        # Check if user is authorized to cancel
        consultant_profile = db.query(ConsultantProfile).filter(
            ConsultantProfile.user_id == user_id
        ).first()
        
        is_client = appointment.user_id == user_id
        is_consultant = consultant_profile and appointment.consultant_id == consultant_profile.id
        
        if not (is_client or is_consultant):
            return {"success": False, "error": "Not authorized to cancel this appointment"}
        
        appointment.status = "cancelled"
        db.commit()
        
        return {"success": True, "message": "Appointment cancelled successfully"}
    except Exception as e:
        print(f"Error cancelling appointment: {str(e)}")
        db.rollback()
        return {"success": False, "error": str(e)}

@app.post("/api/appointments/{appointment_id}/notes")
async def update_appointment_notes(appointment_id: int, request: Request, db: Session = Depends(get_db)):
    """Update notes for an appointment"""
    try:
        user_id = request.session.get("user_id")
        user_type = request.session.get("user_type")
        
        if not user_id or user_type != "consultant":
            return {"success": False, "error": "Not authorized"}
        
        data = await request.json()
        notes = data.get("notes", "")
        
        # Get appointment
        appointment = db.query(Appointment).filter(
            Appointment.id == appointment_id
        ).first()
        
        if not appointment:
            return {"success": False, "error": "Appointment not found"}
        
        # Verify consultant owns this appointment
        consultant_profile = db.query(ConsultantProfile).filter(
            ConsultantProfile.user_id == user_id
        ).first()
        
        if not consultant_profile or appointment.consultant_id != consultant_profile.id:
            return {"success": False, "error": "Not authorized using this appointment"}
        
        appointment.notes = notes
        db.commit()
        
        return {"success": True}
    except Exception as e:
        print(f"Error updating notes: {str(e)}")
        return {"success": False, "error": str(e)}

# ============================================================================
# MESSAGING API ENDPOINTS
# ============================================================================

@app.post("/api/messages/send")
async def send_message(request: Request, db: Session = Depends(get_db)):
    """Send a message to another user"""
    try:
        user_id = request.session.get("user_id")
        if not user_id:
            return {"success": False, "error": "Not authenticated"}
        
        data = await request.json()
        receiver_id = data.get("receiver_id")
        content = data.get("content", "").strip()
        
        if not receiver_id or not content:
            return {"success": False, "error": "Receiver and content are required"}
        
        # Create message
        message = Message(
            sender_id=user_id,
            receiver_id=receiver_id,
            content=content
        )
        
        db.add(message)
        db.commit()
        db.refresh(message)
        
        return {
            "success": True,
            "message": {
                "id": message.id,
                "content": message.content,
                "timestamp": message.timestamp.isoformat(),
                "is_read": message.is_read
            }
        }
    except Exception as e:
        print(f"Error sending message: {str(e)}")
        db.rollback()
        return {"success": False, "error": str(e)}

@app.get("/api/messages/conversations")
async def get_conversations(request: Request, db: Session = Depends(get_db)):
    """Get list of conversations for the current user"""
    try:
        user_id = request.session.get("user_id")
        if not user_id:
            return {"success": False, "error": "Not authenticated"}
        
        # Get all users the current user has messaged with
        from sqlalchemy import or_, and_, func
        
        # Subquery to get the latest message for each conversation
        latest_messages = db.query(
            Message.sender_id,
            Message.receiver_id,
            func.max(Message.timestamp).label('latest_timestamp')
        ).filter(
            or_(Message.sender_id == user_id, Message.receiver_id == user_id)
        ).group_by(
            Message.sender_id, Message.receiver_id
        ).subquery()
        
        # Get unique conversation partners
        sent_to = db.query(Message.receiver_id).filter(Message.sender_id == user_id).distinct()
        received_from = db.query(Message.sender_id).filter(Message.receiver_id == user_id).distinct()
        
        partner_ids = set()
        for row in sent_to:
            partner_ids.add(row[0])
        for row in received_from:
            partner_ids.add(row[0])
        
        conversations = []
        for partner_id in partner_ids:
            # Get partner details
            partner = db.query(User).filter(User.id == partner_id).first()
            if not partner:
                continue
            
            # Get latest message
            latest_msg = db.query(Message).filter(
                or_(
                    and_(Message.sender_id == user_id, Message.receiver_id == partner_id),
                    and_(Message.sender_id == partner_id, Message.receiver_id == user_id)
                )
            ).order_by(Message.timestamp.desc()).first()
            
            # Count unread messages from this partner
            unread_count = db.query(Message).filter(
                Message.sender_id == partner_id,
                Message.receiver_id == user_id,
                Message.is_read == False
            ).count()
            
            conversations.append({
                "partner_id": partner.id,
                "partner_name": partner.name,
                "partner_type": partner.user_type,
                "latest_message": latest_msg.content if latest_msg else "",
                "latest_timestamp": latest_msg.timestamp.isoformat() if latest_msg else None,
                "unread_count": unread_count
            })
        
        # Sort by latest message timestamp
        conversations.sort(key=lambda x: x["latest_timestamp"] or "", reverse=True)
        
        return {"success": True, "conversations": conversations}
    except Exception as e:
        print(f"Error getting conversations: {str(e)}")
        return {"success": False, "error": str(e)}

@app.get("/api/messages/thread/{partner_id}")
async def get_message_thread(partner_id: int, request: Request, db: Session = Depends(get_db)):
    """Get message thread with a specific user"""
    try:
        user_id = request.session.get("user_id")
        if not user_id:
            return {"success": False, "error": "Not authenticated"}
        
        from sqlalchemy import or_, and_
        
        # Get all messages between the two users
        messages = db.query(Message).filter(
            or_(
                and_(Message.sender_id == user_id, Message.receiver_id == partner_id),
                and_(Message.sender_id == partner_id, Message.receiver_id == user_id)
            )
        ).order_by(Message.timestamp.asc()).all()
        
        # Get partner details
        partner = db.query(User).filter(User.id == partner_id).first()
        
        message_list = []
        for msg in messages:
            message_list.append({
                "id": msg.id,
                "sender_id": msg.sender_id,
                "receiver_id": msg.receiver_id,
                "content": msg.content,
                "timestamp": msg.timestamp.isoformat(),
                "is_read": msg.is_read,
                "is_mine": msg.sender_id == user_id
            })
        
        return {
            "success": True,
            "partner": {
                "id": partner.id,
                "name": partner.name,
                "user_type": partner.user_type
            } if partner else None,
            "messages": message_list
        }
    except Exception as e:
        print(f"Error getting message thread: {str(e)}")
        return {"success": False, "error": str(e)}

@app.post("/api/messages/mark-read/{partner_id}")
async def mark_messages_read(partner_id: int, request: Request, db: Session = Depends(get_db)):
    """Mark all messages from a partner as read"""
    try:
        user_id = request.session.get("user_id")
        if not user_id:
            return {"success": False, "error": "Not authenticated"}
        
        # Mark all unread messages from partner as read
        db.query(Message).filter(
            Message.sender_id == partner_id,
            Message.receiver_id == user_id,
            Message.is_read == False
        ).update({"is_read": True})
        
        db.commit()
        
        return {"success": True}
    except Exception as e:
        print(f"Error marking messages as read: {str(e)}")
        db.rollback()
        return {"success": False, "error": str(e)}

# ============================================================================
# AI CHAT API ENDPOINTS
# ============================================================================

@app.post("/api/ai-chat/send")
async def send_ai_chat(request: Request, db: Session = Depends(get_db)):
    """Send a message to AI assistant and get response"""
    try:
        user_id = request.session.get("user_id")
        if not user_id:
            return {"success": False, "error": "Not authenticated"}
        
        data = await request.json()
        message = data.get("message", "").strip()
        
        if not message:
            return {"success": False, "error": "Message is required"}
        
        # Get recent conversation history for context
        recent_chats = db.query(AIChatHistory).filter(
            AIChatHistory.user_id == user_id
        ).order_by(AIChatHistory.timestamp.desc()).limit(5).all()
        
        # Build conversation history
        conversation_history = []
        for chat in reversed(recent_chats):
            conversation_history.append({"content": chat.message, "is_user": True})
            conversation_history.append({"content": chat.response, "is_user": False})
        
        # Get AI response
        ai_response = ollama_chat.chat(message, conversation_history)
        
        # Save to database
        chat_entry = AIChatHistory(
            user_id=user_id,
            message=message,
            response=ai_response
        )
        db.add(chat_entry)
        db.commit()
        db.refresh(chat_entry)
        
        return {
            "success": True,
            "response": ai_response,
            "timestamp": chat_entry.timestamp.isoformat()
        }
    except Exception as e:
        import traceback
        error_msg = f"Error in AI chat: {str(e)}\n\nTraceback:\n{traceback.format_exc()}"
        print(error_msg)
        with open("debug_error.log", "w") as f:
            f.write(error_msg)
        db.rollback()
        return {"success": False, "error": f"Failed to get AI response: {str(e)}"}

@app.get("/api/ai-chat/history")
async def get_ai_chat_history(request: Request, db: Session = Depends(get_db)):
    """Get AI chat history for current user"""
    try:
        user_id = request.session.get("user_id")
        if not user_id:
            return {"success": False, "error": "Not authenticated"}
        
        # Get chat history
        chats = db.query(AIChatHistory).filter(
            AIChatHistory.user_id == user_id
        ).order_by(AIChatHistory.timestamp.asc()).all()
        
        history = []
        for chat in chats:
            history.append({
                "id": chat.id,
                "message": chat.message,
                "response": chat.response,
                "timestamp": chat.timestamp.isoformat()
            })
        
        return {"success": True, "history": history}
    except Exception as e:
        print(f"Error getting AI chat history: {str(e)}")
        return {"success": False, "error": str(e)}

@app.get("/api/ai-chat/status")
async def get_ai_chat_status():
    """Check if AI chat service is available"""
    is_available = ollama_chat.is_available()
    return {
        "available": is_available,
        "model": ollama_chat.model if is_available else None
    }

@app.post("/api/ai-chat/reset")
async def reset_ai_chat(request: Request, db: Session = Depends(get_db)):
    """Reset AI chat history so the agent starts fresh"""
    try:
        user_id = request.session.get("user_id")
        if not user_id:
            return {"success": False, "error": "Not authenticated"}
        
        # Delete all chat history for this user
        db.query(AIChatHistory).filter(
            AIChatHistory.user_id == user_id
        ).delete()
        
        db.commit()
        
        return {"success": True}
    except Exception as e:
        print(f"Error resetting chat: {str(e)}")
        db.rollback()
        return {"success": False, "error": str(e)}

# ============================================================================
# VOICE CALLING - SOCKET.IO & CALL ROOM
# ============================================================================

# Mount Socket.IO app for WebRTC signaling
socket_app = get_socket_app()
app.mount("/socket.io", socket_app)

@app.get("/app/call/{appointment_id}", response_class=HTMLResponse)
async def call_room(
    appointment_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    """Call room page for voice calling"""
    try:
        # Check if user is logged in
        user_id = request.session.get("user_id")
        if not user_id:
            return RedirectResponse(url="/login", status_code=303)
            
        try:
            user_id = int(str(user_id))
        except (ValueError, TypeError):
            request.session.clear()
            return RedirectResponse(url="/login", status_code=303)
        
        # Get user
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            request.session.clear()
            return RedirectResponse(url="/login", status_code=303)
        
        # Get appointment
        appointment = db.query(Appointment).filter(Appointment.id == appointment_id).first()
        if not appointment:
            raise HTTPException(status_code=404, detail="Appointment not found")
        
        # Verify user is part of this appointment
        if user.user_type == "user" and appointment.user_id != user_id:
            raise HTTPException(status_code=403, detail="Not authorized")
        elif user.user_type == "consultant":
            # For consultants, check if their consultant profile matches the appointment
            consultant_profile = db.query(ConsultantProfile).filter(
                ConsultantProfile.user_id == user_id
            ).first()
            if not consultant_profile or appointment.consultant_id != consultant_profile.id:
                raise HTTPException(status_code=403, detail="Not authorized")
        
        # Get or create call session
        call_session = db.query(CallSession).filter(
            CallSession.appointment_id == appointment_id
        ).first()
        
        if not call_session:
            # Get consultant profile to get user_id
            consultant_profile = db.query(ConsultantProfile).filter(
                ConsultantProfile.id == appointment.consultant_id
            ).first()
            
            if not consultant_profile:
                raise HTTPException(status_code=404, detail="Consultant not found")
            
            # Create new call session
            room_id = f"call_{appointment_id}_{uuid.uuid4().hex[:8]}"
            call_session = CallSession(
                appointment_id=appointment_id,
                room_id=room_id,
                user_id=appointment.user_id,
                consultant_id=consultant_profile.user_id,  # Use consultant's user_id, not profile id
                scheduled_start=appointment.appointment_date,
                scheduled_end=appointment.appointment_date + timedelta(minutes=appointment.duration_minutes),
                status="pending"
            )
            db.add(call_session)
            db.commit()
            db.refresh(call_session)
        
        # Get consultant info (appointment.consultant_id is the ConsultantProfile ID)
        consultant_profile_obj = db.query(ConsultantProfile).filter(
            ConsultantProfile.id == appointment.consultant_id
        ).first()
        
        # Get user info for context
        user_name = user.name
        # Check profile for name preference
        user_profile = db.query(UserProfile).filter(UserProfile.user_id == user.id).first()
        if user_profile and user_profile.preferred_name:
            user_name = user_profile.preferred_name
        elif user_profile and user_profile.full_name:
            user_name = user_profile.full_name
            
        initials = get_initials(user_name)
        
        # Get patient info
        patient = db.query(User).filter(User.id == appointment.user_id).first()
        
        # Build navigation items based on user type
        if user.user_type == "consultant":
            nav_items = [
                {"icon": "layout-dashboard", "label": "Dashboard", "href": "/app/consultant", "key": "dashboard"},
                {"icon": "calendar", "label": "Appointments", "href": "/app/consultant/appointments", "key": "appointments"},
                {"icon": "users", "label": "Patients", "href": "/app/consultant/patients", "key": "patients"},
                {"icon": "message-square", "label": "Messages", "href": "/app/messages", "key": "messages"}
            ]
        else:
            nav_items = [
                {"icon": "layout-dashboard", "label": "Dashboard", "href": "/app", "key": "dashboard"},
                {"icon": "activity", "label": "Vitals", "href": "/app/vitals", "key": "vitals"},
                {"icon": "smile", "label": "Mood", "href": "/app/mood", "key": "mood"},
                {"icon": "users", "label": "Consultants", "href": "/app/consultants", "key": "consultants"},
                {"icon": "message-square", "label": "Messages", "href": "/app/messages", "key": "messages"},
                {"icon": "bot", "label": "AI Assistant", "href": "/app/chat", "key": "chat"}
            ]
        
        return templates.TemplateResponse("pages/call_room.html", {
            "request": request,
            "user": user,
            "user_name": user_name,
            "user_initials": initials,
            "user_type": user.user_type,
            "active_page": "call",
            "nav_items": nav_items,
            "appointment": appointment,
            "call_session": call_session,
            "consultant": consultant_profile_obj,
            "patient": patient
        })
    except HTTPException:
        raise
    except Exception as e:
        print(f"ERROR in call_room: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

# ============================================================================
# PATIENT HEALTH DATA API (for Consultant Call Room)
# ============================================================================

@app.get("/api/patient/{user_id}/health-data")
async def get_patient_health_data(
    user_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    """Get patient's vitals and mood data for consultant view"""
    try:
        # Verify consultant is logged in
        consultant_user_id = request.session.get("user_id")
        user_type = request.session.get("user_type")
        
        if not consultant_user_id or user_type != "consultant":
            return {"success": False, "error": "Not authorized"}
        
        # Get last 7 vitals readings
        vitals = db.query(VitalsRecord).filter(
            VitalsRecord.user_id == user_id
        ).order_by(VitalsRecord.timestamp.desc()).limit(7).all()
        
        # Get last 7 mood entries
        moods = db.query(MoodEntry).filter(
            MoodEntry.user_id == user_id
        ).order_by(MoodEntry.timestamp.desc()).limit(7).all()
        
        # Format vitals data
        vitals_data = []
        for vital in reversed(vitals):  # Reverse to show oldest first
            vitals_data.append({
                "date": vital.timestamp.strftime("%b %d, %H:%M"),
                "heart_rate": vital.heart_rate,
                "blood_pressure_systolic": vital.blood_pressure_systolic,
                "blood_pressure_diastolic": vital.blood_pressure_diastolic,
                "temperature": vital.temperature,
                "respiratory_rate": vital.respiratory_rate,
                "oxygen_saturation": vital.spo2
            })
        
        # Format mood data
        mood_data = []
        for mood in reversed(moods):  # Reverse to show oldest first
            mood_data.append({
                "date": mood.timestamp.strftime("%b %d, %H:%M"),
                "mood": mood.mood_rating,
                "notes": mood.notes
            })
        
        return {
            "success": True,
            "vitals": vitals_data,
            "moods": mood_data
        }
        
    except Exception as e:
        print(f"Error fetching patient health data: {str(e)}")
        return {"success": False, "error": str(e)}

# ============================================================================
# API HEALTH CHECK
# ============================================================================

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "SolaceSquad"}

# ============================================================================
# RUN APPLICATION
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True  # Auto-reload on code changes
    )

# ============================================================================
# CONSULTANT PRESCRIPTION ROUTES
# ============================================================================

@app.get("/consultant/prescriptions", response_class=HTMLResponse)
async def consultant_prescriptions(request: Request, db: Session = Depends(get_db)):
    """Consultant prescription creation page"""
    user_id = request.session.get("user_id")
    if not user_id:
        return RedirectResponse(url="/login", status_code=302)
        
    user = db.query(User).filter(User.id == user_id).first()
    if not user or user.user_type != "consultant":
        return RedirectResponse(url="/app", status_code=302)
        
    user_name = request.session.get("user_name", "Consultant")
    name_parts = user_name.split()
    initials = name_parts[0][0].upper() + (name_parts[1][0].upper() if len(name_parts) > 1 else name_parts[0][:2].upper())

    # Get consultant profile
    consultant_profile = db.query(ConsultantProfile).filter(ConsultantProfile.user_id == user_id).first()
    
    clients = []
    if consultant_profile:
        # Fetch clients who have had appointments with this consultant
        clients = db.query(User).join(Appointment, Appointment.user_id == User.id)\
            .filter(Appointment.consultant_id == consultant_profile.id)\
            .group_by(User.id).all()
            
    return templates.TemplateResponse(
        "pages/consultant_prescription.html",
        {
            "request": request,
            "page_title": "Wellness Summary Reports - SolaceSquad",
            "user_name": user_name,
            "user_initials": initials,
            "user_type": "consultant",
            "active_page": "prescriptions",
            "clients": clients
        }
    )

from pydantic import BaseModel
from typing import List, Optional

class PrescriptionItemModel(BaseModel):
    medication_name: str
    dosage: Optional[str]
    frequency: Optional[str]
    duration: Optional[str]
    instructions: Optional[str]

class PrescriptionModel(BaseModel):
    user_id: int
    diagnosis: Optional[str]
    notes: Optional[str]
    items: List[PrescriptionItemModel]

@app.post("/api/consultant/prescriptions")
async def create_prescription(data: PrescriptionModel, request: Request, db: Session = Depends(get_db)):
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
        
    user = db.query(User).filter(User.id == user_id).first()
    if not user or user.user_type != "consultant":
        raise HTTPException(status_code=403, detail="Not a consultant")

    try:
        # Create prescription
        prescription = Prescription(
            consultant_id=user_id,
            user_id=data.user_id,
            diagnosis=data.diagnosis,
            notes=data.notes
        )
        db.add(prescription)
        db.flush() # get ID
        
        # Add items
        for item in data.items:
            db_item = PrescriptionItem(
                prescription_id=prescription.id,
                medication_name=item.medication_name,
                dosage=item.dosage,
                frequency=item.frequency,
                duration=item.duration,
                instructions=item.instructions
            )
            db.add(db_item)
            
        db.commit()
        
        # Audit Log
        AuditLogger.log_event(
            db,
            event_type="prescription_created",
            user_id=user_id,
            resource_type="prescription",
            resource_id=str(prescription.id),
            details=f"Prescription created for user {data.user_id}"
        )
        
        return {"success": True, "id": prescription.id}
    except Exception as e:
        db.rollback()
        print(f"Error creating prescription: {e}")
        return {"success": False, "error": str(e)}

# ============================================================================
# SAVE CONSULTATION NOTES
# ============================================================================

@app.post("/api/appointments/{appointment_id}/notes")
async def save_consultation_notes(
    appointment_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    """Save consultation notes for an appointment"""
    try:
        user_id = request.session.get("user_id")
        if not user_id:
            raise HTTPException(status_code=401, detail="Not authenticated")
        
        # Get request body
        body = await request.json()
        notes = body.get("notes", "")
        
        # Get appointment
        appointment = db.query(Appointment).filter(
            Appointment.id == appointment_id
        ).first()
        
        if not appointment:
            return {"success": False, "error": "Appointment not found"}
        
        # Verify user is the consultant for this appointment
        consultant_profile = db.query(ConsultantProfile).filter(
            ConsultantProfile.user_id == user_id
        ).first()
        
        if not consultant_profile or appointment.consultant_id != consultant_profile.id:
            return {"success": False, "error": "Unauthorized"}
        
        # Update notes
        appointment.notes = notes
        db.commit()
        
        return {"success": True, "message": "Notes saved successfully"}
    except Exception as e:
        db.rollback()
        print(f"Error saving notes: {e}")
        return {"success": False, "error": str(e)}


# ============================================================================
# VIEW PRESCRIPTIONS
# ============================================================================

@app.get("/api/prescriptions/{prescription_id}")
async def get_prescription(
    prescription_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    """Get prescription details"""
    try:
        user_id = request.session.get("user_id")
        if not user_id:
            raise HTTPException(status_code=401, detail="Not authenticated")
        
        # Get prescription with items
        prescription = db.query(Prescription).filter(
            Prescription.id == prescription_id
        ).first()
        
        if not prescription:
            return {"success": False, "error": "Prescription not found"}
        
        # Verify user is authorized (either the patient or the consultant)
        if prescription.user_id != user_id and prescription.consultant_id != user_id:
            return {"success": False, "error": "Unauthorized"}
        
        # Get consultant info
        consultant = db.query(User).filter(User.id == prescription.consultant_id).first()
        consultant_profile = db.query(ConsultantProfile).filter(
            ConsultantProfile.user_id == prescription.consultant_id
        ).first()
        
        # Get patient info
        patient = db.query(User).filter(User.id == prescription.user_id).first()
        
        # Format items
        items = []
        for item in prescription.items:
            items.append({
                "medication_name": item.medication_name,
                "dosage": item.dosage,
                "frequency": item.frequency,
                "duration": item.duration,
                "instructions": item.instructions
            })
        
        return {
            "success": True,
            "prescription": {
                "id": prescription.id,
                "created_at": prescription.created_at.isoformat(),
                "diagnosis": prescription.diagnosis,
                "notes": prescription.notes,
                "consultant_name": consultant.name if consultant else "Unknown",
                "consultant_specialization": consultant_profile.specialization if consultant_profile else "",
                "patient_name": patient.name if patient else "Unknown",
                "items": items
            }
        }
    except Exception as e:
        print(f"Error getting prescription: {e}")
        return {"success": False, "error": str(e)}


@app.get("/api/user/prescriptions")
async def get_user_prescriptions(
    request: Request,
    db: Session = Depends(get_db)
):
    """Get all prescriptions for the logged-in user"""
    try:
        user_id = request.session.get("user_id")
        if not user_id:
            raise HTTPException(status_code=401, detail="Not authenticated")
        
        # Get all prescriptions for this user
        prescriptions = db.query(Prescription).filter(
            Prescription.user_id == user_id
        ).order_by(Prescription.created_at.desc()).all()
        
        prescription_list = []
        for rx in prescriptions:
            consultant = db.query(User).filter(User.id == rx.consultant_id).first()
            consultant_profile = db.query(ConsultantProfile).filter(
                ConsultantProfile.user_id == rx.consultant_id
            ).first()
            
            prescription_list.append({
                "id": rx.id,
                "created_at": rx.created_at.strftime("%B %d, %Y"),
                "diagnosis": rx.diagnosis,
                "consultant_name": consultant.name if consultant else "Unknown",
                "consultant_specialization": consultant_profile.specialization if consultant_profile else "",
                "item_count": len(rx.items)
            })
        
        return {"success": True, "prescriptions": prescription_list}
    except Exception as e:
        print(f"Error getting user prescriptions: {e}")
        return {"success": False, "error": str(e)}

# ============================================================================
# PRESCRIPTIONS PAGE AND PDF GENERATION
# ============================================================================

@app.get("/prescriptions")
async def prescriptions_page(request: Request, db: Session = Depends(get_db)):
    """Wellness Summary Reports page for users to view their wellness reports"""
    try:
        user_id = request.session.get("user_id")
        if not user_id:
            return RedirectResponse(url="/login", status_code=302)
        
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return RedirectResponse(url="/login", status_code=302)
        
        # Get navigation items
        nav_items = get_nav_items(user.user_type)
        
        return templates.TemplateResponse("pages/prescriptions.html", {
            "request": request,
            "user": user,
            "user_name": user.name,
            "user_type": user.user_type,
            "user_initials": get_initials(user.name),
            "nav_items": nav_items,
            "active_page": "prescriptions"
        })
    except Exception as e:
        print(f"Error loading prescriptions page: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/prescriptions/{prescription_id}/pdf")
async def download_prescription_pdf(
    prescription_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    """Generate and download prescription as PDF"""
    try:
        from fastapi.responses import Response
        from pdf_generator import generate_prescription_pdf
        
        user_id = request.session.get("user_id")
        if not user_id:
            raise HTTPException(status_code=401, detail="Not authenticated")
        
        # Get prescription with items
        prescription = db.query(Prescription).filter(
            Prescription.id == prescription_id
        ).first()
        
        if not prescription:
            raise HTTPException(status_code=404, detail="Prescription not found")
        
        # Verify user is authorized (either the patient or the consultant)
        if prescription.user_id != user_id and prescription.consultant_id != user_id:
            raise HTTPException(status_code=403, detail="Unauthorized")
        
        # Get consultant info
        consultant = db.query(User).filter(User.id == prescription.consultant_id).first()
        consultant_profile = db.query(ConsultantProfile).filter(
            ConsultantProfile.user_id == prescription.consultant_id
        ).first()
        
        # Get patient info
        patient = db.query(User).filter(User.id == prescription.user_id).first()
        
        # Format items
        items = []
        for item in prescription.items:
            items.append({
                "medication_name": item.medication_name,
                "dosage": item.dosage,
                "frequency": item.frequency,
                "duration": item.duration,
                "instructions": item.instructions
            })
        
        # Prepare data for PDF
        prescription_data = {
            "id": prescription.id,
            "created_at": prescription.created_at,
            "diagnosis": prescription.diagnosis or "",
            "notes": prescription.notes or "",
            "consultant_name": consultant.name if consultant else "Unknown",
            "consultant_specialization": consultant_profile.specialization if consultant_profile else "",
            "patient_name": patient.name if patient else "Unknown",
            "items": items
        }
        
        # Generate PDF
        pdf_bytes = generate_prescription_pdf(prescription_data)
        
        # Return PDF as response
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename=prescription_{prescription_id}.pdf"
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error generating PDF: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error generating PDF: {str(e)}")

# ============================================================================
# CALL RECORDINGS API
# ============================================================================

@app.get("/recordings")
async def recordings_page(request: Request, db: Session = Depends(get_db)):
    """Recordings page for users to listen to their call recordings"""
    try:
        user_id = request.session.get("user_id")
        if not user_id:
            return RedirectResponse(url="/login", status_code=302)
        
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return RedirectResponse(url="/login", status_code=302)
        
        nav_items = get_nav_items(user.user_type)
        
        return templates.TemplateResponse("pages/recordings.html", {
            "request": request,
            "user": user,
            "user_name": user.name,
            "user_type": user.user_type,
            "user_initials": get_initials(user.name),
            "nav_items": nav_items,
            "active_page": "recordings"
        })
    except Exception as e:
        print(f"Error loading recordings page: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/user/recordings")
async def get_user_recordings(request: Request, db: Session = Depends(get_db)):
    """Get all recordings for the logged-in user"""
    try:
        user_id = request.session.get("user_id")
        if not user_id:
            raise HTTPException(status_code=401, detail="Not authenticated")
        
        # Get all call sessions for this user
        call_sessions = db.query(CallSession).filter(
            CallSession.user_id == user_id,
            CallSession.status == "completed",
            CallSession.recording_url.isnot(None)
        ).order_by(CallSession.actual_start.desc()).all()
        
        recordings = []
        for session in call_sessions:
            # Get consultant info
            consultant = db.query(User).filter(User.id == session.consultant_id).first()
            
            # Check if transcription exists
            transcription = db.query(CallTranscription).filter(
                CallTranscription.call_session_id == session.id
            ).first()
            
            recordings.append({
                "id": session.id,
                "call_date": session.actual_start.isoformat() if session.actual_start else session.scheduled_start.isoformat(),
                "duration_seconds": session.duration_seconds,
                "consultant_name": consultant.name if consultant else "Unknown",
                "has_transcription": transcription is not None and transcription.summary is not None
            })
        
        return {"success": True, "recordings": recordings}
    except Exception as e:
        print(f"Error getting user recordings: {e}")
        return {"success": False, "error": str(e)}


@app.get("/api/recordings/{session_id}")
async def get_recording_details(
    session_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    """Get recording details including URL and transcription"""
    try:
        user_id = request.session.get("user_id")
        if not user_id:
            raise HTTPException(status_code=401, detail="Not authenticated")
        
        # Get call session
        session = db.query(CallSession).filter(CallSession.id == session_id).first()
        
        if not session:
            return {"success": False, "error": "Recording not found"}
        
        # Verify user is authorized (either patient or consultant)
        if session.user_id != user_id and session.consultant_id != user_id:
            return {"success": False, "error": "Unauthorized"}
        
        # Get consultant info
        consultant = db.query(User).filter(User.id == session.consultant_id).first()
        
        # Get transcription if available
        transcription = db.query(CallTranscription).filter(
            CallTranscription.call_session_id == session.id
        ).first()
        
        recording_data = {
            "id": session.id,
            "call_date": session.actual_start.isoformat() if session.actual_start else session.scheduled_start.isoformat(),
            "duration_seconds": session.duration_seconds,
            "consultant_name": consultant.name if consultant else "Unknown",
            "status": session.status,
            "recording_url": session.recording_url or "/static/audio/sample-recording.mp3",  # Fallback for demo
            "transcription": {
                "summary": transcription.summary,
                "full_text": transcription.full_transcription
            } if transcription else None
        }
        
        return {"success": True, "recording": recording_data}
    except Exception as e:
        print(f"Error getting recording details: {e}")
        return {"success": False, "error": str(e)}


@app.get("/api/consultant/patient/{patient_id}/recordings")
async def get_patient_recordings(
    patient_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    """Get all recordings for a specific patient (consultant view)"""
    try:
        user_id = request.session.get("user_id")
        if not user_id:
            raise HTTPException(status_code=401, detail="Not authenticated")
        
        # Verify user is a consultant
        consultant_profile = db.query(ConsultantProfile).filter(
            ConsultantProfile.user_id == user_id
        ).first()
        
        if not consultant_profile:
            return {"success": False, "error": "Unauthorized"}
        
        # Get all call sessions between this consultant and patient
        call_sessions = db.query(CallSession).filter(
            CallSession.user_id == patient_id,
            CallSession.consultant_id == user_id,
            CallSession.status == "completed",
            CallSession.recording_url.isnot(None)
        ).order_by(CallSession.actual_start.desc()).all()
        
        recordings = []
        for session in call_sessions:
            recordings.append({
                "id": session.id,
                "call_date": session.actual_start.isoformat() if session.actual_start else session.scheduled_start.isoformat(),
                "duration_seconds": session.duration_seconds
            })
        
        return {"success": True, "recordings": recordings}
    except Exception as e:
        print(f"Error getting patient recordings: {e}")
        return {"success": False, "error": str(e)}


@app.get("/api/consultant/patient/{patient_id}/summaries")
async def get_patient_summaries(
    patient_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    """Get all call summaries for a specific patient"""
    try:
        user_id = request.session.get("user_id")
        if not user_id:
            raise HTTPException(status_code=401, detail="Not authenticated")
        
        # Verify user is a consultant
        consultant_profile = db.query(ConsultantProfile).filter(
            ConsultantProfile.user_id == user_id
        ).first()
        
        if not consultant_profile:
            return {"success": False, "error": "Unauthorized"}
        
        # Get all call sessions with transcriptions
        sessions = db.query(CallSession).filter(
            CallSession.user_id == patient_id,
            CallSession.consultant_id == user_id,
            CallSession.status == "completed"
        ).order_by(CallSession.actual_start.desc()).all()
        
        summaries = []
        for session in sessions:
            transcription = db.query(CallTranscription).filter(
                CallTranscription.call_session_id == session.id
            ).first()
            
            if transcription and transcription.summary:
                summaries.append({
                    "id": transcription.id,
                    "date": session.actual_start.isoformat() if session.actual_start else session.scheduled_start.isoformat(),
                    "summary": transcription.summary,
                    "status": transcription.summary_status
                })
        
        return {"success": True, "summaries": summaries}
    except Exception as e:
        print(f"Error getting patient summaries: {e}")
        return {"success": False, "error": str(e)}


@app.get("/consultant/patient/{patient_id}")
async def consultant_patient_detail(
    patient_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    """Patient detail page for consultants"""
    try:
        user_id = request.session.get("user_id")
        if not user_id:
            return RedirectResponse(url="/login", status_code=302)
        
        user = db.query(User).filter(User.id == user_id).first()
        if not user or user.user_type != "consultant":
            raise HTTPException(status_code=403, detail="Unauthorized")
        
        # Get patient info
        patient = db.query(User).filter(User.id == patient_id).first()
        if not patient:
            raise HTTPException(status_code=404, detail="Patient not found")
        
        nav_items = get_nav_items(user.user_type)
        
        return templates.TemplateResponse("pages/consultant_patient_detail.html", {
            "request": request,
            "user": user,
            "patient": patient,
            "patient_initials": get_initials(patient.name),
            "user_name": user.name,
            "user_type": user.user_type,
            "user_initials": get_initials(user.name),
            "nav_items": nav_items,
            "active_page": "clients"
        })
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error loading patient detail page: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ============================================================================
# CONSULTANT NOTES API
# ============================================================================

@app.get("/api/consultant/patient/{patient_id}/notes")
async def get_patient_notes(
    patient_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    """Get all notes for a specific patient including appointment notes"""
    try:
        user_id = request.session.get("user_id")
        if not user_id:
            raise HTTPException(status_code=401, detail="Not authenticated")
        
        # Verify user is a consultant
        consultant_profile = db.query(ConsultantProfile).filter(
            ConsultantProfile.user_id == user_id
        ).first()
        
        if not consultant_profile:
            return {"success": False, "error": "Unauthorized"}
        
        # 1. Get standalone PatientNotes
        patient_notes = db.query(PatientNote).filter(
            PatientNote.patient_id == patient_id,
            PatientNote.consultant_id == user_id
        ).all()
        
        # 2. Get notes from Appointments
        appointment_notes = db.query(Appointment).filter(
            Appointment.user_id == patient_id,
            Appointment.consultant_id == consultant_profile.id,
            Appointment.notes.isnot(None),
            Appointment.notes != ""
        ).all()
        
        notes_list = []
        
        # Add patient notes
        for note in patient_notes:
            notes_list.append({
                "id": note.id,
                "type": "general",
                "content": note.content,
                "created_at": note.created_at.isoformat(),
                "timestamp": note.created_at.timestamp()
            })
            
        # Add appointment notes
        for appt in appointment_notes:
            notes_list.append({
                "id": f"appt_{appt.id}",
                "type": "appointment",
                "content": f"Consultation Note: {appt.notes}",
                "created_at": appt.appointment_date.isoformat(),
                "timestamp": appt.appointment_date.timestamp()
            })
            
        # Sort by date descending
        notes_list.sort(key=lambda x: x["timestamp"], reverse=True)
        
        return {"success": True, "notes": notes_list}
    except Exception as e:
        print(f"Error getting patient notes: {e}")
        return {"success": False, "error": str(e)}


@app.post("/api/consultant/patient/{patient_id}/notes")
async def add_patient_note(
    patient_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    """Add a new note for a patient"""
    try:
        user_id = request.session.get("user_id")
        if not user_id:
            raise HTTPException(status_code=401, detail="Not authenticated")
        
        # Verify user is a consultant
        consultant_profile = db.query(ConsultantProfile).filter(
            ConsultantProfile.user_id == user_id
        ).first()
        
        if not consultant_profile:
            return {"success": False, "error": "Unauthorized"}
        
        # Get request body
        body = await request.json()
        content = body.get("content", "").strip()
        
        if not content:
            return {"success": False, "error": "Note content is required"}
        
        # Create new note
        note = PatientNote(
            patient_id=patient_id,
            consultant_id=user_id,
            content=content
        )
        
        db.add(note)
        db.commit()
        db.refresh(note)
        
        return {
            "success": True,
            "note": {
                "id": note.id,
                "content": note.content,
                "created_at": note.created_at.isoformat()
            }
        }
    except Exception as e:
        print(f"Error adding patient note: {e}")
        db.rollback()
        return {"success": False, "error": str(e)}


@app.delete("/api/consultant/notes/{note_id}")
async def delete_patient_note(
    note_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    """Delete a patient note"""
    try:
        user_id = request.session.get("user_id")
        if not user_id:
            raise HTTPException(status_code=401, detail="Not authenticated")
        
        # Get the note
        note = db.query(PatientNote).filter(PatientNote.id == note_id).first()
        
        if not note:
            return {"success": False, "error": "Note not found"}
        
        # Verify the note belongs to this consultant
        if note.consultant_id != user_id:
            return {"success": False, "error": "Unauthorized"}
        
        db.delete(note)
        db.commit()
        
        return {"success": True}
    except Exception as e:
        print(f"Error deleting patient note: {e}")
        db.rollback()
        return {"success": False, "error": str(e)}

# ============================================================================
# ADMIN ROUTES
# ============================================================================

@app.get("/admin", response_class=HTMLResponse)
async def admin_dashboard(request: Request, db: Session = Depends(get_db)):
    """Admin dashboard to manage users and consultants"""
    user_id = request.session.get("user_id")
    # Redirect to login if not authenticated
    if not user_id:
        return RedirectResponse(url="/")
    
    current_user = db.query(User).filter(User.id == user_id).first()
    
    # Strictly check for admin type
    if not current_user or current_user.user_type != "admin":
         # Return forbidden or redirect
         return RedirectResponse(url="/app")
         
    # Fetch all users
    users = db.query(User).filter(User.user_type == "user").all()
    # Fetch all consultants (joining with profile)
    consultants_query = db.query(User).filter(User.user_type == "consultant").all()
    
    # Process for template
    processed_users = []
    for u in users:
        processed_users.append({
            "id": u.id,
            "name": u.name,
            "email": u.email,
            "initials": get_initials(u.name),
            "created_at": u.created_at,
            "is_active": u.is_active,
            "user_type": u.user_type
        })
        
    processed_consultants = []
    for c in consultants_query:
        # Access consultant profile via backref/relationship if it exists
        profile = None
        # Handle cases where backref might return list or object depending on exact SQLA version/config
        if hasattr(c, "consultant_profile"):
            cp = c.consultant_profile
            if isinstance(cp, list) and cp:
                profile = cp[0]
            elif cp and not isinstance(cp, list):
                profile = cp
        
        processed_consultants.append({
            "id": c.id, # User ID
            "name": c.name,
            "email": c.email,
            "initials": get_initials(c.name),
            "is_active": c.is_active,
            "specialization": profile.specialization if profile else "Not Setup",
            "hourly_rate": profile.hourly_rate if profile else 0,
            "user_type": c.user_type
        })
        
    return templates.TemplateResponse(
        "pages/admin_dashboard.html",
        {
            "request": request,
            "page_title": "Admin Dashboard",
            "users": processed_users,
            "consultants": processed_consultants,
            "user_name": current_user.name,
            "user_initials": get_initials(current_user.name),
            "user_type": current_user.user_type,
            "active_page": "dashboard"
        }
    )

@app.post("/api/admin/users/{user_id}/status")
async def update_user_status(user_id: int, request: Request, db: Session = Depends(get_db)):
    # Auth check
    admin_id = request.session.get("user_id")
    if not admin_id: return {"success": False, "error": "Unauthorized"}
    admin = db.query(User).filter(User.id == admin_id).first()
    if not admin or admin.user_type != "admin": return {"success": False, "error": "Unauthorized"}
    
    data = await request.json()
    is_active = data.get("is_active")
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user: return {"success": False, "error": "User not found"}
    
    user.is_active = is_active
    db.commit()
    
    # Audit Log
    AuditLogger.log_event(
        db, 
        event_type="admin_update_status", 
        user_id=admin_id,
        resource_type="user",
        resource_id=str(user_id),
        details=f"Set active status to {is_active}",
        request=request
    )
    
    return {"success": True}

@app.delete("/api/admin/users/{user_id}")
async def delete_user_admin(user_id: int, request: Request, db: Session = Depends(get_db)):
    # Auth check
    admin_id = request.session.get("user_id")
    if not admin_id: return {"success": False, "error": "Unauthorized"}
    admin = db.query(User).filter(User.id == admin_id).first()
    if not admin or admin.user_type != "admin": return {"success": False, "error": "Unauthorized"}
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user: return {"success": False, "error": "User not found"}
    
    db.delete(user) 
    db.commit()
    
    # Audit Log
    AuditLogger.log_event(
        db, 
        event_type="admin_delete_user", 
        user_id=admin_id,
        resource_type="user",
        resource_id=str(user_id),
        details="User deleted by admin",
        request=request
    )
    
    return {"success": True}

@app.post("/api/admin/consultants/{user_id}/price")
async def update_consultant_price(user_id: int, request: Request, db: Session = Depends(get_db)):
    # Auth check
    admin_id = request.session.get("user_id")
    if not admin_id: return {"success": False, "error": "Unauthorized"}
    admin = db.query(User).filter(User.id == admin_id).first()
    if not admin or admin.user_type != "admin": return {"success": False, "error": "Unauthorized"}
    
    data = await request.json()
    hourly_rate = data.get("hourly_rate")
    
    # Look for profile
    profile = db.query(ConsultantProfile).filter(ConsultantProfile.user_id == user_id).first()
    
    if not profile:
        # Create profile if it doesn't exist (edge case)
        profile = ConsultantProfile(user_id=user_id, hourly_rate=float(hourly_rate))
        db.add(profile)
    else:
        profile.hourly_rate = float(hourly_rate)
        
    db.commit()
    
    # Audit Log
    AuditLogger.log_event(
        db, 
        event_type="admin_update_price", 
        user_id=admin_id,
        resource_type="consultant_profile",
        resource_id=str(profile.id),
        details=f"Set hourly rate to {hourly_rate}",
        request=request
    )
    
    return {"success": True}
