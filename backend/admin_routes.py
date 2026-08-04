# Admin Routes for Video Library and User Management
# This file contains all admin-specific routes

from fastapi import Request, Depends, Form, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from sqlalchemy.orm import Session
from models import User, VideoFolder, Video, VitalsRecord, Appointment
from typing import Optional

# ============================================================================
# ADMIN VIDEO LIBRARY ROUTES
# ============================================================================

async def admin_videos_list(request: Request, db: Session):
    """Admin video library management page"""
    user_id = request.session.get("user_id")
    if not user_id:
        return RedirectResponse(url="/login", status_code=303)
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user or user.user_type != "admin":
        return RedirectResponse(url="/app", status_code=303)
    
    # Get all folders with video count
    folders = db.query(VideoFolder).all()
    for folder in folders:
        folder.video_count = len(folder.videos)
    
    from main import templates
    return templates.TemplateResponse(
        "pages/admin_videos_list.html",
        {
            "request": request,
            "page_title": "Video Library - Admin",
            "user": user,
            "folders": folders
        }
    )


async def admin_folder_detail(request: Request, folder_id: int, db: Session):
    """Admin folder detail page with videos"""
    user_id = request.session.get("user_id")
    if not user_id:
        return RedirectResponse(url="/login", status_code=303)
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user or user.user_type != "admin":
        return RedirectResponse(url="/app", status_code=303)
    
    folder = db.query(VideoFolder).filter(VideoFolder.id == folder_id).first()
    if not folder:
        return RedirectResponse(url="/admin/videos", status_code=303)
    
    from main import templates
    return templates.TemplateResponse(
        "pages/admin_folder_detail.html",
        {
            "request": request,
            "page_title": f"{folder.name} - Admin",
            "user": user,
            "folder": folder
        }
    )


async def create_folder(
    request: Request,
    name: str = Form(...),
    description: str = Form(""),
    thumbnail_url: str = Form(""),
    db: Session = Depends()
):
    """Create a new video folder"""
    user_id = request.session.get("user_id")
    user = db.query(User).filter(User.id == user_id).first()
    if not user or user.user_type != "admin":
        return JSONResponse({"success": False, "error": "Unauthorized"}, status_code=403)
    
    folder = VideoFolder(
        name=name,
        description=description,
        thumbnail_url=thumbnail_url if thumbnail_url else None
    )
    db.add(folder)
    db.commit()
    db.refresh(folder)
    
    return JSONResponse({"success": True, "folder_id": folder.id})


async def delete_folder(request: Request, folder_id: int, db: Session):
    """Delete a video folder"""
    user_id = request.session.get("user_id")
    user = db.query(User).filter(User.id == user_id).first()
    if not user or user.user_type != "admin":
        return JSONResponse({"success": False, "error": "Unauthorized"}, status_code=403)
    
    folder = db.query(VideoFolder).filter(VideoFolder.id == folder_id).first()
    if folder:
        db.delete(folder)
        db.commit()
        return JSONResponse({"success": True})
    
    return JSONResponse({"success": False, "error": "Folder not found"}, status_code=404)


async def create_video(
    request: Request,
    folder_id: int = Form(...),
    title: str = Form(...),
    description: str = Form(""),
    video_url: str = Form(...),
    thumbnail_url: str = Form(""),
    duration_seconds: int = Form(0),
    is_youtube: bool = Form(False),
    db: Session = Depends()
):
    """Create a new video in a folder"""
    user_id = request.session.get("user_id")
    user = db.query(User).filter(User.id == user_id).first()
    if not user or user.user_type != "admin":
        return JSONResponse({"success": False, "error": "Unauthorized"}, status_code=403)
    
    video = Video(
        folder_id=folder_id,
        title=title,
        description=description,
        video_url=video_url,
        thumbnail_url=thumbnail_url if thumbnail_url else None,
        duration_seconds=duration_seconds,
        is_youtube=is_youtube
    )
    db.add(video)
    db.commit()
    db.refresh(video)
    
    return JSONResponse({"success": True, "video_id": video.id})


async def delete_video(request: Request, video_id: int, db: Session):
    """Delete a video"""
    user_id = request.session.get("user_id")
    user = db.query(User).filter(User.id == user_id).first()
    if not user or user.user_type != "admin":
        return JSONResponse({"success": False, "error": "Unauthorized"}, status_code=403)
    
    video = db.query(Video).filter(Video.id == video_id).first()
    if video:
        db.delete(video)
        db.commit()
        return JSONResponse({"success": True})
    
    return JSONResponse({"success": False, "error": "Video not found"}, status_code=404)


# ============================================================================
# ADMIN USER MANAGEMENT ROUTES
# ============================================================================

async def admin_users_list(request: Request, db: Session):
    """Admin users management page"""
    user_id = request.session.get("user_id")
    if not user_id:
        return RedirectResponse(url="/login", status_code=303)
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user or user.user_type != "admin":
        return RedirectResponse(url="/app", status_code=303)
    
    # Get all users
    users = db.query(User).all()
    
    # Add stats for each user
    for u in users:
        u.vitals_count = db.query(VitalsRecord).filter(VitalsRecord.user_id == u.id).count()
        u.appointments_count = db.query(Appointment).filter(Appointment.user_id == u.id).count()
    
    from main import templates
    return templates.TemplateResponse(
        "pages/admin_users.html",
        {
            "request": request,
            "page_title": "Users Management - Admin",
            "user": user,
            "users": users
        }
    )


async def toggle_user_status(request: Request, user_id: int, db: Session):
    """Toggle user active/inactive status"""
    admin_id = request.session.get("user_id")
    admin = db.query(User).filter(User.id == admin_id).first()
    if not admin or admin.user_type != "admin":
        return JSONResponse({"success": False, "error": "Unauthorized"}, status_code=403)
    
    target_user = db.query(User).filter(User.id == user_id).first()
    if target_user:
        target_user.is_active = not target_user.is_active
        db.commit()
        return JSONResponse({"success": True, "is_active": target_user.is_active})
    
    return JSONResponse({"success": False, "error": "User not found"}, status_code=404)


async def delete_user(request: Request, user_id: int, db: Session):
    """Delete a user"""
    admin_id = request.session.get("user_id")
    admin = db.query(User).filter(User.id == admin_id).first()
    if not admin or admin.user_type != "admin":
        return JSONResponse({"success": False, "error": "Unauthorized"}, status_code=403)
    
    # Don't allow deleting yourself
    if user_id == admin_id:
        return JSONResponse({"success": False, "error": "Cannot delete yourself"}, status_code=400)
    
    target_user = db.query(User).filter(User.id == user_id).first()
    if target_user:
        db.delete(target_user)
        db.commit()
        return JSONResponse({"success": True})
    
    return JSONResponse({"success": False, "error": "User not found"}, status_code=404)
