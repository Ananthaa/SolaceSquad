# Mood-Based Routing API Endpoints
# Add these endpoints to main.py after the existing mood endpoint (around line 678)

# POST endpoint to log mood
@app.post("/api/mood/log")
async def log_mood(request: Request, db: Session = Depends(get_db)):
    """Log user's current mood"""
    try:
        user_id = request.session.get("user_id")
        if not user_id:
            return {"success": False, "error": "User not logged in"}
        
        data = await request.json()
        mood_rating = data.get("mood_rating")
        notes = data.get("notes", "")
        
        if not mood_rating:
            return {"success": False, "error": "Mood rating is required"}
        
        # Create new mood entry
        from models import MoodEntry
        from datetime import datetime
        
        mood_entry = MoodEntry(
            user_id=user_id,
            mood_rating=str(mood_rating),
            notes=notes,
            timestamp=datetime.utcnow()
        )
        
        db.add(mood_entry)
        db.commit()
        db.refresh(mood_entry)
        
        # Audit log
        AuditLogger.log_event(
            db,
            event_type="mood_logged",
            user_id=user_id,
            details=f"User logged mood: {mood_rating}",
            request=request
        )
        
        return {
            "success": True,
            "mood": {
                "id": mood_entry.id,
                "mood_rating": mood_entry.mood_rating,
                "timestamp": mood_entry.timestamp.isoformat()
            }
        }
    except Exception as e:
        print(f"Error logging mood: {str(e)}")
        return {"success": False, "error": str(e)}


# GET endpoint for free consultants
@app.get("/api/consultants/free")
async def get_free_consultants(request: Request, db: Session = Depends(get_db)):
    """Get consultants with fee = 0 (free consultation)"""
    try:
        from models import ConsultantProfile, User
        
        # Query consultants with fee = 0 and approved status
        free_consultants = db.query(ConsultantProfile, User).join(
            User, ConsultantProfile.user_id == User.id
        ).filter(
            ConsultantProfile.consultation_fee == 0,
            ConsultantProfile.status == "approved"
        ).all()
        
        consultants_data = []
        for profile, user in free_consultants:
            consultants_data.append({
                "id": profile.user_id,
                "name": user.name,
                "specialization": profile.specialization,
                "bio": profile.bio,
                "experience_years": profile.experience_years,
                "consultation_fee": 0,
                "rating": profile.rating or 0
            })
        
        return {
            "success": True,
            "consultants": consultants_data,
            "count": len(consultants_data)
        }
    except Exception as e:
        print(f"Error fetching free consultants: {str(e)}")
        return {"success": False, "error": str(e), "consultants": []}


# POST endpoint to check mood and route
@app.post("/api/mood/check-routing")
async def check_mood_routing(request: Request, db: Session = Depends(get_db)):
    """Check if user's mood requires special routing"""
    try:
        user_id = request.session.get("user_id")
        if not user_id:
            return {"success": False, "error": "User not logged in"}
        
        data = await request.json()
        mood_rating = int(data.get("mood_rating", 4))
        
        # Bottom 3 moods (1, 2, 3) require special routing
        if mood_rating <= 3:
            # Check for free consultants
            from models import ConsultantProfile
            free_consultant_count = db.query(ConsultantProfile).filter(
                ConsultantProfile.consultation_fee == 0,
                ConsultantProfile.status == "approved"
            ).count()
            
            if free_consultant_count > 0:
                return {
                    "success": True,
                    "requires_routing": True,
                    "route_to": "free_consultation",
                    "message": "We noticed you're not feeling well. You'll get a 30-minute free consultation with one of our caring professionals.",
                    "free_consultants_available": True
                }
            else:
                return {
                    "success": True,
                    "requires_routing": True,
                    "route_to": "ai_buddy",
                    "message": "We're here for you. Let's talk to SolaceSquad Buddy who can help you feel better.",
                    "free_consultants_available": False,
                    "mood_context": mood_rating
                }
        else:
            return {
                "success": True,
                "requires_routing": False,
                "message": "Great to see you! Continue to your dashboard."
            }
    except Exception as e:
        print(f"Error checking mood routing: {str(e)}")
        return {"success": False, "error": str(e)}
