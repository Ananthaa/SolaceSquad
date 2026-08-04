
# ============================================================================
# EXERCISE VIDEO LIBRARY ROUTES
# ============================================================================

@app.get("/exercises", response_class=HTMLResponse)
async def exercises_library(request: Request, db: Session = Depends(get_db)):
    """Exercise Library - Browse video folders"""
    from sqlalchemy import func
    
    user_id = request.session.get("user_id")
    if not user_id:
        return RedirectResponse(url="/login", status_code=303)
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return RedirectResponse(url="/login", status_code=303)
    
    # Get all video folders with video count
    folders = db.query(
        VideoFolder,
        func.count(Video.id).label('video_count')
    ).outerjoin(Video).group_by(VideoFolder.id).order_by(VideoFolder.created_at.desc()).all()
    
    # Format folders with video count
    folders_data = []
    for folder, count in folders:
        folders_data.append({
            'id': folder.id,
            'name': folder.name,
            'description': folder.description,
            'thumbnail_url': folder.thumbnail_url,
            'video_count': count
        })
    
    return templates.TemplateResponse(
        "pages/video_library.html",
        {
            "request": request,
            "page_title": "Exercise Library - SolaceSquad",
            "user": user,
            "user_name": user.name,
            "user_initials": get_initials(user.name),
            "user_type": user.user_type,
            "active_page": "exercises",
            "nav_items": get_nav_items(user.user_type),
            "folders": folders_data
        }
    )


@app.get("/exercises/folder/{folder_id}", response_class=HTMLResponse)
async def exercises_folder(folder_id: int, request: Request, db: Session = Depends(get_db)):
    """View videos in a specific folder"""
    user_id = request.session.get("user_id")
    if not user_id:
        return RedirectResponse(url="/login", status_code=303)
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return RedirectResponse(url="/login", status_code=303)
    
    # Get folder
    folder = db.query(VideoFolder).filter(VideoFolder.id == folder_id).first()
    if not folder:
        return HTMLResponse("Folder not found", status_code=404)
    
    # Get all videos in folder
    videos = db.query(Video).filter(Video.folder_id == folder_id).order_by(Video.created_at.desc()).all()
    
    return templates.TemplateResponse(
        "pages/video_folder.html",
        {
            "request": request,
            "page_title": f"{folder.name} - Exercise Library",
            "user": user,
            "user_name": user.name,
            "user_initials": get_initials(user.name),
            "user_type": user.user_type,
            "active_page": "exercises",
            "nav_items": get_nav_items(user.user_type),
            "folder": folder,
            "videos": videos
        }
    )


@app.get("/exercises/watch/{video_id}", response_class=HTMLResponse)
async def exercises_watch(video_id: int, request: Request, db: Session = Depends(get_db)):
    """Watch a specific video"""
    user_id = request.session.get("user_id")
    if not user_id:
        return RedirectResponse(url="/login", status_code=303)
    
    video = db.query(Video).filter(Video.id == video_id).first()
    if not video:
        return HTMLResponse("Video not found", status_code=404)
    
    # Get completion status
    log = db.query(UserExerciseLog).filter(
        UserExerciseLog.user_id == user_id,
        UserExerciseLog.video_id == video_id
    ).first()
    is_completed = log.completed if log else False
    
    # Related videos (same folder)
    related = db.query(Video).filter(
        Video.folder_id == video.folder_id,
        Video.id != video_id
    ).limit(5).all()
    
    related_list = [{
        "id": v.id,
        "title": v.title,
        "thumbnail_url": v.thumbnail_url,
        "duration_formatted": f"{v.duration_seconds // 60}:{v.duration_seconds % 60:02d}"
    } for v in related]
    
    video_data = {
        "id": video.id,
        "folder_id": video.folder_id,
        "folder": video.folder,
        "title": video.title,
        "description": video.description,
        "video_url": video.video_url,
        "thumbnail_url": video.thumbnail_url,
        "is_youtube": video.is_youtube,
        "created_at": video.created_at,
        "duration_formatted": f"{video.duration_seconds // 60}:{video.duration_seconds % 60:02d}",
        "duration_seconds": video.duration_seconds
    }
    
    user_name = request.session.get("user_name", "User")
    return templates.TemplateResponse(
        "pages/video_player.html",
        {
            "request": request,
            "page_title": f"{video.title} - SolaceSquad",
            "user_name": user_name,
            "user_initials": get_initials(user_name),
            "user_type": request.session.get("user_type", "user"),
            "active_page": "exercise",
            "nav_items": get_nav_items(request.session.get("user_type", "user")),
            "video": video_data,
            "is_completed": is_completed,
            "related_videos": related_list
        }
    )


@app.post("/api/exercises/{video_id}/complete")
async def toggle_exercise_completion(video_id: int, request: Request, db: Session = Depends(get_db)):
    """Toggle video completion status"""
    user_id = request.session.get("user_id")
    if not user_id:
        return {"success": False, "error": "Not logged in"}
    
    try:
        log = db.query(UserExerciseLog).filter(
            UserExerciseLog.user_id == user_id,
            UserExerciseLog.video_id == video_id
        ).first()
        
        if not log:
            log = UserExerciseLog(
                user_id=user_id,
                video_id=video_id,
                watched_seconds=0,
                completed=True
            )
            db.add(log)
        else:
            log.completed = not log.completed
        
        db.commit()
        return {"success": True, "is_completed": log.completed}
    except Exception as e:
        print(f"Error toggling completion: {e}")
        return {"success": False, "error": str(e)}
