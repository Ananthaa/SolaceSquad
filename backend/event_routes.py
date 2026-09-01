import os
import re
import json
import mimetypes
from datetime import datetime, date
from typing import Optional, List
from fastapi import FastAPI, Request, Depends, HTTPException, File, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from models import EventWorkshop, EventGalleryItem, ConsultantEarning, ConsultantProfile
from gcs_uploads import upload_to_gcs

def _is_test_mode() -> bool:
    """Return True when Razorpay is configured with a test key."""
    key_id = os.getenv("RAZORPAY_KEY_ID", "")
    return key_id.startswith("rzp_test_")

def sync_event_earning(db: Session, event: EventWorkshop):
    """Sync the ConsultantEarning table with the event's payout info."""
    # Find existing earning for this event
    earning = db.query(ConsultantEarning).filter(ConsultantEarning.event_workshop_id == event.id).first()
    
    if event.consultant_id and event.payout_amount and event.payout_amount > 0:
        # We need an earning record
        # Find the User.id for the given ConsultantProfile.id
        profile = db.query(ConsultantProfile).filter(ConsultantProfile.id == event.consultant_id).first()
        if not profile:
            if earning:
                db.delete(earning)
            return
            
        consultant_user_id = profile.user_id
        is_test = _is_test_mode()
        
        if not earning:
            earning = ConsultantEarning(
                consultant_user_id=consultant_user_id,
                event_workshop_id=event.id,
                gross_amount=float(event.payout_amount),
                platform_fee_pct=0.0,
                platform_fee=0.0,
                consultant_payout=float(event.payout_amount),
                payout_status="pending",
                is_test=is_test,
                taxes=0.0,
                discount_amount=0.0,
                discount_pct=0.0
            )
            db.add(earning)
        else:
            earning.consultant_user_id = consultant_user_id
            earning.gross_amount = float(event.payout_amount)
            earning.consultant_payout = float(event.payout_amount)
            earning.platform_fee_pct = 0.0
            earning.is_test = is_test
            earning.taxes = 0.0
            earning.discount_amount = 0.0
            earning.discount_pct = 0.0
    else:
        # No consultant or zero payout: remove any existing earning record
        if earning:
            db.delete(earning)
            
    db.commit()

def _event_dict(event: EventWorkshop) -> dict:
    """Helper to serialize an EventWorkshop object with its gallery items."""
    return {
        "id": event.id,
        "type": event.type,
        "title": event.title,
        "slug": event.slug,
        "short_summary": event.short_summary,
        "full_content": event.full_content,
        "author_name": event.author_name,
        "author_bio": event.author_bio,
        "author_image": event.author_image,
        "expert_name": event.expert_name,
        "expert_bio": event.expert_bio,
        "ai_assisted_content": event.ai_assisted_content,
        "featured_image": event.featured_image,
        "event_date": event.event_date.isoformat() if event.event_date else None,
        "start_time": event.start_time,
        "end_time": event.end_time,
        "venue": event.venue,
        "event_mode": event.event_mode,
        "registration_link": event.registration_link,
        "show_registration": event.show_registration,
        "show_date_time": event.show_date_time,
        "show_location": event.show_location,
        "status": event.status,
        "sort_order": event.sort_order,
        "created_at": event.created_at.isoformat() if event.created_at else None,
        "updated_at": event.updated_at.isoformat() if event.updated_at else None,
        "consultant_id": event.consultant_id,
        "payout_amount": event.payout_amount,
        "sponsor_config": event.sponsor_config,
        "gallery_items": [
            {
                "id": item.id,
                "media_type": item.media_type,
                "source": item.source,
                "thumbnail": item.thumbnail,
                "caption": item.caption,
                "alt_text": item.alt_text,
                "sort_order": item.sort_order
            } for item in event.gallery_items
        ]
    }

def register_event_routes(app: FastAPI, templates: Jinja2Templates, get_db):

    # ── Admin check guard ───────────────────────────────────────────────────────
    def _admin_check(request: Request, allow_assistant: bool = False):
        uid = request.session.get("user_id")
        if not uid:
            raise HTTPException(status_code=401, detail="Not authenticated")
        user_type = request.session.get("user_type", "")
        admin_email = os.getenv("ADMIN_EMAIL", "admin@solacesquad.com")
        if user_type == "admin" or request.session.get("email") == admin_email:
            return  # admin access granted
        if allow_assistant and user_type == "admin_assistant":
            return  # assistant access granted
        raise HTTPException(status_code=403, detail="Admin access required")

    # ── Public Pages & API ──────────────────────────────────────────────────────

    @app.get("/events", response_class=HTMLResponse, tags=["Events"])
    async def public_events_page(request: Request, db: Session = Depends(get_db)):
        """Public Events & Workshops page. No authentication required."""
        # Query published events, ordered by sort_order then event_date
        events = (
            db.query(EventWorkshop)
            .filter(EventWorkshop.status == "published", EventWorkshop.type == "event")
            .order_by(EventWorkshop.sort_order.asc(), EventWorkshop.event_date.desc())
            .all()
        )
        workshops = (
            db.query(EventWorkshop)
            .filter(EventWorkshop.status == "published", EventWorkshop.type == "workshop")
            .order_by(EventWorkshop.sort_order.asc(), EventWorkshop.event_date.desc())
            .all()
        )
        return templates.TemplateResponse(
            "pages/events_landing.html",
            {
                "request": request,
                "events": events,
                "workshops": workshops,
                "active_page": "events"
            }
        )

    @app.get("/events/{slug}", response_class=HTMLResponse, tags=["Events"])
    async def public_event_detail_page(slug: str, request: Request, db: Session = Depends(get_db)):
        """Public Event/Workshop details page. No authentication required."""
        event = db.query(EventWorkshop).filter(EventWorkshop.slug == slug).first()
        if not event:
            raise HTTPException(status_code=404, detail="Event or Workshop not found")
        
        # If it's a draft/archived, restrict to admins
        if event.status != "published":
            try:
                _admin_check(request, allow_assistant=True)
            except HTTPException:
                raise HTTPException(status_code=404, detail="Event or Workshop not found")

        import json
        sponsor_rows = 0
        sponsor_cols = 0
        sponsor_logos = []
        if hasattr(event, "sponsor_config") and event.sponsor_config:
            try:
                config = json.loads(event.sponsor_config)
                sponsor_rows = int(config.get("rows", 0))
                sponsor_cols = int(config.get("cols", 0))
                sponsor_logos = config.get("logos", [])
                
                # Grid dimension fallback if rows/cols are unspecified (0) but logos are added
                if sponsor_logos:
                    max_r = 0
                    max_c = 0
                    for l in sponsor_logos:
                        try:
                            r_val = int(l.get("row", 0))
                            c_val = int(l.get("col", 0))
                            if r_val > max_r:
                                max_r = r_val
                            if c_val > max_c:
                                max_c = c_val
                        except (ValueError, TypeError):
                            pass
                    if sponsor_rows <= 0:
                        sponsor_rows = max_r + 1
                    if sponsor_cols <= 0:
                        sponsor_cols = max_c + 1
            except Exception as e:
                print("[SponsorConfig Error]", e)

        return templates.TemplateResponse(
            "pages/event_detail.html",
            {
                "request": request,
                "event": event,
                "active_page": "events",
                "sponsor_rows": sponsor_rows,
                "sponsor_cols": sponsor_cols,
                "sponsor_logos": sponsor_logos
            }
        )

    @app.get("/api/events/media", tags=["Events"])
    async def serve_event_media(url: str):
        """Proxy stream endpoint to serve private GCS uploaded media files to the public."""
        try:
            import asyncio
            from google.cloud import storage as gcs_storage

            if "storage.googleapis.com/" not in url:
                raise HTTPException(status_code=400, detail="Invalid media URL")

            after = url.split("storage.googleapis.com/", 1)[1]
            bucket_name, blob_path = after.split("/", 1)

            def _download():
                client = gcs_storage.Client()
                blob = client.bucket(bucket_name).blob(blob_path)
                return blob.download_as_bytes(), blob.content_type or "application/octet-stream"

            media_bytes, content_type = await asyncio.get_event_loop().run_in_executor(None, _download)
            return Response(
                content=media_bytes,
                media_type=content_type,
                headers={
                    "Cache-Control": "public, max-age=31536000",
                    "Accept-Ranges": "bytes"
                },
            )
        except Exception as e:
            print(f"[EventMediaProxy] Error serving URL {url}: {e}")
            raise HTTPException(status_code=404, detail="Media not found")

    # ── Admin CMS Page & API ────────────────────────────────────────────────────

    @app.get("/admin/events", response_class=HTMLResponse, tags=["Admin / Events"])
    async def admin_events_page(request: Request, db: Session = Depends(get_db)):
        """Admin page to manage events and workshops."""
        _admin_check(request, allow_assistant=True)
        from models import User
        consultants = db.query(ConsultantProfile).join(User).filter(
            ConsultantProfile.is_approved == True
        ).order_by(User.name.asc()).all()
        return templates.TemplateResponse(
            "pages/admin_events.html",
            {
                "request": request,
                "active_page": "events",
                "active_user_type": request.session.get("user_type"),
                "consultants": consultants
            }
        )

    @app.get("/api/admin/events", tags=["Admin / Events"])
    async def admin_list_events(db: Session = Depends(get_db), request: Request = None):
        _admin_check(request, allow_assistant=True)
        events = db.query(EventWorkshop).order_by(EventWorkshop.sort_order.asc(), EventWorkshop.created_at.desc()).all()
        return {"success": True, "events": [_event_dict(e) for e in events]}

    @app.post("/api/admin/events", tags=["Admin / Events"])
    async def admin_create_event(request: Request, db: Session = Depends(get_db)):
        _admin_check(request, allow_assistant=True)
        data = await request.json()

        # Validate unique slug
        slug = data.get("slug", "").strip()
        if not slug:
            slug = re.sub(r"[^\w\s-]", "", data.get("title", "")).strip().lower()
            slug = re.sub(r"[-\s]+", "-", slug)
        
        # Check if slug exists
        existing = db.query(EventWorkshop).filter(EventWorkshop.slug == slug).first()
        if existing:
            slug = f"{slug}-{int(datetime.utcnow().timestamp())}"

        # Parse date
        date_str = data.get("event_date")
        try:
            event_date = datetime.strptime(date_str, "%Y-%m-%d").date() if date_str else date.today()
        except ValueError:
            event_date = date.today()

        consultant_id_val = data.get("consultant_id")
        payout_amount_val = data.get("payout_amount")
        try:
            consultant_id = int(consultant_id_val) if consultant_id_val else None
        except (ValueError, TypeError):
            consultant_id = None
            
        try:
            payout_amount = float(payout_amount_val) if payout_amount_val else 0.0
        except (ValueError, TypeError):
            payout_amount = 0.0

        import json
        sponsor_conf = data.get("sponsor_config")
        if isinstance(sponsor_conf, (dict, list)):
            sponsor_conf = json.dumps(sponsor_conf)

        event = EventWorkshop(
            type=data.get("type", "event"),
            title=data.get("title", "").strip(),
            slug=slug,
            short_summary=data.get("short_summary", "").strip(),
            full_content=data.get("full_content", "").strip(),
            author_name=data.get("author_name", "SolaceSquad Team").strip(),
            author_bio=data.get("author_bio", "").strip(),
            author_image=data.get("author_image"),
            expert_name=data.get("expert_name", "").strip(),
            expert_bio=data.get("expert_bio", "").strip(),
            ai_assisted_content=bool(data.get("ai_assisted_content", False)),
            featured_image=data.get("featured_image"),
            event_date=event_date,
            start_time=data.get("start_time"),
            end_time=data.get("end_time"),
            venue=data.get("venue", "").strip(),
            event_mode=data.get("event_mode", "online"),
            registration_link=data.get("registration_link", "").strip(),
            show_registration=bool(data.get("show_registration", True)),
            show_date_time=bool(data.get("show_date_time", True)),
            show_location=bool(data.get("show_location", True)),
            status=data.get("status", "draft"),
            sort_order=int(data.get("sort_order", 0)),
            consultant_id=consultant_id,
            payout_amount=payout_amount,
            sponsor_config=sponsor_conf
        )
        db.add(event)
        db.commit()
        db.refresh(event)

        # Sync consultant earnings
        sync_event_earning(db, event)

        # Handle Gallery items
        gallery_data = data.get("gallery_items", [])
        for idx, item in enumerate(gallery_data):
            gal_item = EventGalleryItem(
                event_id=event.id,
                media_type=item.get("media_type", "image"),
                source=item.get("source"),
                thumbnail=item.get("thumbnail"),
                caption=item.get("caption", "").strip(),
                alt_text=item.get("alt_text", "").strip(),
                sort_order=int(item.get("sort_order", idx))
            )
            db.add(gal_item)
        db.commit()
        db.refresh(event)

        return {"success": True, "event": _event_dict(event)}

    @app.put("/api/admin/events/{event_id}", tags=["Admin / Events"])
    async def admin_update_event(event_id: int, request: Request, db: Session = Depends(get_db)):
        _admin_check(request, allow_assistant=True)
        event = db.query(EventWorkshop).filter(EventWorkshop.id == event_id).first()
        if not event:
            raise HTTPException(status_code=404, detail="Event not found")

        data = await request.json()

        # Update base fields
        event.type = data.get("type", event.type)
        event.title = data.get("title", event.title).strip()
        event.slug = data.get("slug", event.slug).strip()
        event.short_summary = data.get("short_summary", event.short_summary).strip()
        event.full_content = data.get("full_content", event.full_content).strip()
        event.author_name = data.get("author_name", event.author_name).strip()
        event.author_bio = data.get("author_bio", event.author_bio).strip()
        event.author_image = data.get("author_image", event.author_image)
        event.expert_name = data.get("expert_name", event.expert_name or "").strip()
        event.expert_bio = data.get("expert_bio", event.expert_bio or "").strip()
        event.ai_assisted_content = bool(data.get("ai_assisted_content", event.ai_assisted_content))
        event.featured_image = data.get("featured_image", event.featured_image)
        event.start_time = data.get("start_time", event.start_time)
        event.end_time = data.get("end_time", event.end_time)
        event.venue = data.get("venue", event.venue).strip()
        event.event_mode = data.get("event_mode", event.event_mode)
        event.registration_link = data.get("registration_link", event.registration_link).strip()
        event.show_registration = bool(data.get("show_registration", event.show_registration))
        event.show_date_time = bool(data.get("show_date_time", event.show_date_time))
        event.show_location = bool(data.get("show_location", event.show_location))
        event.status = data.get("status", event.status)
        event.sort_order = int(data.get("sort_order", event.sort_order))

        date_str = data.get("event_date")
        if date_str:
            try:
                event.event_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            except ValueError:
                pass

        # Gallery synchronization: delete old items, insert new
        db.query(EventGalleryItem).filter(EventGalleryItem.event_id == event.id).delete()
        
        gallery_data = data.get("gallery_items", [])
        for idx, item in enumerate(gallery_data):
            gal_item = EventGalleryItem(
                event_id=event.id,
                media_type=item.get("media_type", "image"),
                source=item.get("source"),
                thumbnail=item.get("thumbnail"),
                caption=item.get("caption", "").strip(),
                alt_text=item.get("alt_text", "").strip(),
                sort_order=int(item.get("sort_order", idx))
            )
            db.add(gal_item)

        # Update event consultant fields
        consultant_id_val = data.get("consultant_id")
        payout_amount_val = data.get("payout_amount")
        try:
            event.consultant_id = int(consultant_id_val) if consultant_id_val else None
        except (ValueError, TypeError):
            event.consultant_id = None
            
        try:
            event.payout_amount = float(payout_amount_val) if payout_amount_val else 0.0
        except (ValueError, TypeError):
            event.payout_amount = 0.0

        # Update sponsor matrix config
        import json
        sponsor_conf_val = data.get("sponsor_config")
        if isinstance(sponsor_conf_val, (dict, list)):
            event.sponsor_config = json.dumps(sponsor_conf_val)
        else:
            event.sponsor_config = sponsor_conf_val

        db.commit()
        db.refresh(event)

        # Sync consultant earnings
        sync_event_earning(db, event)

        return {"success": True, "event": _event_dict(event)}

    @app.delete("/api/admin/events/{event_id}", tags=["Admin / Events"])
    async def admin_delete_event(event_id: int, request: Request, db: Session = Depends(get_db)):
        _admin_check(request, allow_assistant=True)
        event = db.query(EventWorkshop).filter(EventWorkshop.id == event_id).first()
        if not event:
            raise HTTPException(status_code=404, detail="Event not found")
        # Delete linked consultant earnings
        db.query(ConsultantEarning).filter(ConsultantEarning.event_workshop_id == event_id).delete()
        db.delete(event)
        db.commit()
        return {"success": True}

    @app.post("/api/admin/events/reorder", tags=["Admin / Events"])
    async def admin_reorder_events(request: Request, db: Session = Depends(get_db)):
        _admin_check(request, allow_assistant=True)
        data = await request.json()
        ids = data.get("ids", [])
        for order, event_id in enumerate(ids):
            event = db.query(EventWorkshop).filter(EventWorkshop.id == event_id).first()
            if event:
                event.sort_order = order
        db.commit()
        return {"success": True}

    @app.post("/api/admin/events/upload", tags=["Admin / Events"])
    async def admin_upload_event_media(request: Request, file: UploadFile = File(...)):
        _admin_check(request, allow_assistant=True)
        try:
            file_bytes = await file.read()
            filename = file.filename
            content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
            
            # Determine directory prefix folder in GCS
            is_video = content_type.startswith("video")
            folder = "events/videos" if is_video else "events/images"
            
            url = upload_to_gcs(file_bytes, filename, content_type, folder)
            if not url:
                return JSONResponse({"success": False, "error": "GCS Upload returned None"}, status_code=500)
            
            return {"success": True, "url": url}
        except Exception as e:
            return JSONResponse({"success": False, "error": str(e)}, status_code=500)

    @app.post("/api/admin/events/ai-assist", tags=["Admin / Events"])
    async def admin_events_ai_assist(request: Request):
        _admin_check(request, allow_assistant=True)
        data = await request.json()
        action = data.get("action", "generate_draft")
        topic = data.get("topic", "")
        existing_content = data.get("existing_content", "")
        event_type = data.get("type", "event")

        try:
            from google import genai as _genai
            # Initialize Client using Vertex AI (HIPAA/DPDP compliant) or fallback to Developer key
            gcp_project = os.getenv("GCP_PROJECT_ID", "abiding-idea-485817-k2")
            gcp_location = os.getenv("GCP_LOCATION", "global")
            
            client = None
            vertex_err = None
            try:
                # Try Vertex AI first (uses ADC inside Cloud Run)
                client = _genai.Client(vertex=True, project=gcp_project, location=gcp_location)
                # Warm-up call to confirm permissions
                client.models.generate_content(
                    model="gemini-2.5-flash",
                    contents="Test connection",
                )
                print("[AI Assist] Successfully initialized HIPAA-eligible Vertex AI client.")
            except Exception as vx_err:
                vertex_err = vx_err
                client = None

            if not client:
                # Fallback to direct Gemini API with developer key
                api_key = os.getenv("GEMINI_API_KEY", "")
                if not api_key:
                    return JSONResponse({
                        "success": False, 
                        "error": f"Vertex AI initialization failed ({vertex_err}) and Developer GEMINI_API_KEY is not configured."
                    }, status_code=500)
                client = _genai.Client(api_key=api_key)

            system_prompt = (
                "You are an expert wellness events planner and editor for SolaceSquad. "
                "SolaceSquad is a premium wellness brand offering calm, empathetic, and professional guidance. "
                "Write in a warm, welcoming, premium, and clean tone suitable for public events and workshops."
            )

            if action == "generate_draft":
                prompt = f"""{system_prompt}

Generate a complete, engaging wellness {event_type} listing draft about: "{topic}"

Return a JSON object with these exact keys:
- "title": Clean, catchy title for the {event_type} (string)
- "slug": URL-friendly lowercase slug (string)
- "short_summary": 2-sentence captivating description (string)
- "full_content": Deep, well-structured description in HTML format (using <h2>, <p>, <ul>, <li>, <strong>, ~300-500 words. Highlight benefits, schedule, details)
- "venue": A fitting placeholder venue or "Online via SolaceSquad Call Room" (string)
- "event_mode": One of "online", "offline", "hybrid" (string)

Return ONLY valid JSON, no markdown code block formatting or fences."""

            elif action == "improve":
                prompt = f"""{system_prompt}

Improve this draft for a wellness {event_type}. Enhance clarity, vocabulary, formatting, and formatting structure.

Original Content:
{existing_content[:3000]}

Return a JSON object with these exact keys:
- "short_summary": Improved 2-sentence summary (string)
- "full_content": Improved full HTML description (using <h2>, <p>, <ul>, <li>, <strong>)

Return ONLY valid JSON, no markdown code block formatting or fences."""

            else:
                return JSONResponse({"success": False, "error": "Unknown action"}, status_code=400)

            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
            )
            raw = response.text.strip()
            # Strip markdown code fences if present
            raw = re.sub(r"^```(?:json)?\s*", "", raw)
            raw = re.sub(r"\s*```$", "", raw)

            result = json.loads(raw)
            return {"success": True, "result": result}

        except json.JSONDecodeError as e:
            return {"success": False, "error": f"AI returned invalid JSON: {e}", "raw": raw}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @app.post("/api/events/enquire")
    async def event_enquiry(request: Request, db: Session = Depends(get_db)):
        """Capture enquiry details and email them to sg@solacesquad.com via SendGrid."""
        try:
            data = await request.json()
            event_id = data.get("event_id")
            name = data.get("name")
            phone = data.get("phone")
            email = data.get("email")
            requirements = data.get("requirements")
            tentative_date = data.get("tentative_date")

            if not (event_id and name and phone and email and requirements and tentative_date):
                return JSONResponse({"success": False, "error": "All fields are required"}, status_code=400)

            event = db.query(EventWorkshop).filter(EventWorkshop.id == event_id).first()
            if not event:
                return JSONResponse({"success": False, "error": "Event/Workshop not found"}, status_code=404)

            # Build structured plain-text email body
            email_body = f"""New Wellness Session Booking Enquiry:
------------------------------------
Event/Workshop: {event.title} ({event.type.upper()})

Inquirer Contact Details:
- Name: {name}
- Email: {email}
- Phone: {phone}

Session Plan:
- Tentative Date: {tentative_date}

Brief Description of Requirements:
{requirements}
"""
            from sendgrid_email import send_plain_email
            sent = send_plain_email(
                to_email="sg@solacesquad.com",
                subject=f"New Session Enquiry: {event.title}",
                body=email_body
            )

            if not sent:
                return JSONResponse({"success": False, "error": "Failed to send email notification"}, status_code=500)

            return {"success": True, "message": "Enquiry sent successfully"}

        except Exception as e:
            return JSONResponse({"success": False, "error": str(e)}, status_code=500)
