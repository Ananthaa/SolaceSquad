"""
blog_routes.py — Blog platform routes for SolaceSquad
- Public: /blog, /blog/{slug}, /api/blogs, /api/blogs/featured, /api/blogs/{slug}
- Admin:  /admin/blogs, /api/admin/blogs (CRUD), /api/admin/blogs/ai-assist
"""
from __future__ import annotations

import json
import math
import os
import re
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, Request, Depends, HTTPException
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from models import BlogPost


# ── Helpers ───────────────────────────────────────────────────────────────────

def _slugify(text: str) -> str:
    """Convert title to URL-safe slug."""
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_-]+", "-", text)
    text = re.sub(r"^-+|-+$", "", text)
    return text[:200]


def _unique_slug(db: Session, base: str, exclude_id: int | None = None) -> str:
    slug = base
    counter = 1
    while True:
        q = db.query(BlogPost).filter(BlogPost.slug == slug)
        if exclude_id:
            q = q.filter(BlogPost.id != exclude_id)
        if not q.first():
            return slug
        slug = f"{base}-{counter}"
        counter += 1


def _read_time(content: str) -> int:
    """Estimate reading time in minutes (200 wpm)."""
    if not content:
        return 1
    words = len(re.sub(r"<[^>]+>", " ", content).split())
    return max(1, math.ceil(words / 200))


def _post_dict(post: BlogPost) -> dict:
    return {
        "id":               post.id,
        "slug":             post.slug,
        "title":            post.title,
        "excerpt":          post.excerpt or "",
        "content":          post.content or "",
        "cover_image_url":  post.cover_image_url or "",
        "category":         post.category,
        "tags":             json.loads(post.tags) if post.tags else [],
        "author_name":      post.author_name,
        "author_avatar_url":post.author_avatar_url or "",
        "status":           post.status,
        "published_at":     post.published_at.isoformat() if post.published_at else None,
        "read_time_minutes":post.read_time_minutes or 1,
        "view_count":       post.view_count,
        "created_at":       post.created_at.isoformat() if post.created_at else None,
        "updated_at":       post.updated_at.isoformat() if post.updated_at else None,
    }


def register_blog_routes(app: FastAPI, templates: Jinja2Templates, get_db):

    # ── Admin guard ───────────────────────────────────────────────────────────
    def _admin_check(request: Request, allow_assistant: bool = False):
        uid = request.session.get("user_id")
        if not uid:
            raise HTTPException(status_code=401, detail="Not authenticated")
        user_type = request.session.get("user_type", "")
        admin_email = os.getenv("ADMIN_EMAIL", "admin@solacesquad.com")
        if user_type == "admin" or request.session.get("email") == admin_email:
            return  # full admin — all access granted
        if allow_assistant and user_type == "admin_assistant":
            return  # assistant — limited access granted
        raise HTTPException(status_code=403, detail="Admin access required")

    # ── Public API ────────────────────────────────────────────────────────────

    @app.get("/api/blogs/featured", tags=["Blog"])
    async def blog_featured(db: Session = Depends(get_db)):
        """Top 3 published posts by views for homepage carousel."""
        posts = (
            db.query(BlogPost)
            .filter(BlogPost.status == "published")
            .order_by(BlogPost.view_count.desc(), BlogPost.published_at.desc())
            .limit(3)
            .all()
        )
        return {"success": True, "posts": [_post_dict(p) for p in posts]}

    @app.get("/api/blogs", tags=["Blog"])
    async def blog_list_api(
        category: str = "",
        tag: str = "",
        page: int = 1,
        limit: int = 12,
        db: Session = Depends(get_db),
    ):
        """Paginated published blog posts."""
        q = db.query(BlogPost).filter(BlogPost.status == "published")
        if category and category != "All":
            q = q.filter(BlogPost.category == category)
        if tag:
            q = q.filter(BlogPost.tags.contains(f'"{tag}"'))
        total = q.count()
        posts = q.order_by(BlogPost.published_at.desc()).offset((page - 1) * limit).limit(limit).all()
        return {
            "success": True,
            "posts": [_post_dict(p) for p in posts],
            "total": total,
            "page": page,
            "pages": math.ceil(total / limit) if total else 1,
        }

    @app.get("/api/blogs/{slug}", tags=["Blog"])
    async def blog_get_api(slug: str, db: Session = Depends(get_db)):
        """Single published post — increments view count + returns prev/next."""
        post = db.query(BlogPost).filter(BlogPost.slug == slug, BlogPost.status == "published").first()
        if not post:
            raise HTTPException(status_code=404, detail="Blog post not found")

        # Increment view count
        post.view_count = (post.view_count or 0) + 1
        db.commit()
        db.refresh(post)

        # Prev / Next in same category
        prev_post = (
            db.query(BlogPost)
            .filter(
                BlogPost.status == "published",
                BlogPost.category == post.category,
                BlogPost.published_at < post.published_at,
            )
            .order_by(BlogPost.published_at.desc())
            .first()
        )
        next_post = (
            db.query(BlogPost)
            .filter(
                BlogPost.status == "published",
                BlogPost.category == post.category,
                BlogPost.published_at > post.published_at,
            )
            .order_by(BlogPost.published_at.asc())
            .first()
        )

        # Related posts (same category, excluding this one)
        related = (
            db.query(BlogPost)
            .filter(
                BlogPost.status == "published",
                BlogPost.category == post.category,
                BlogPost.id != post.id,
            )
            .order_by(BlogPost.view_count.desc())
            .limit(3)
            .all()
        )

        return {
            "success": True,
            "post": _post_dict(post),
            "prev": {"slug": prev_post.slug, "title": prev_post.title} if prev_post else None,
            "next": {"slug": next_post.slug, "title": next_post.title} if next_post else None,
            "related": [_post_dict(r) for r in related],
        }

    # ── Public Pages ──────────────────────────────────────────────────────────

    @app.get("/blog", response_class=HTMLResponse, tags=["Blog"])
    async def blog_list_page(request: Request, db: Session = Depends(get_db)):
        # Server-side render posts so Googlebot can index them without JavaScript
        posts = (
            db.query(BlogPost)
            .filter(BlogPost.status == "published")
            .order_by(BlogPost.published_at.desc())
            .limit(12)
            .all()
        )
        return templates.TemplateResponse("pages/blog_list.html", {
            "request": request,
            "ssr_posts": [_post_dict(p) for p in posts],
        })

    @app.get("/blog/{slug}", response_class=HTMLResponse, tags=["Blog"])
    async def blog_post_page(request: Request, slug: str, db: Session = Depends(get_db)):
        post = db.query(BlogPost).filter(BlogPost.slug == slug, BlogPost.status == "published").first()
        return templates.TemplateResponse("pages/blog_post.html", {
            "request": request,
            "slug": slug,
            "seo_title": post.title if post else None,
            "seo_excerpt": post.excerpt if post else None,
            "seo_author": post.author_name if post else "SolaceSquad Team",
            "seo_published_at": post.published_at.isoformat() if post and post.published_at else None,
            "seo_updated_at": post.updated_at.isoformat() if post and post.updated_at else None,
        })

    # ── Admin API ─────────────────────────────────────────────────────────────

    @app.get("/api/admin/blogs", tags=["Admin / Blog"])
    async def admin_blogs_list(request: Request, db: Session = Depends(get_db)):
        _admin_check(request, allow_assistant=True)
        posts = db.query(BlogPost).order_by(BlogPost.updated_at.desc()).all()
        return {"success": True, "posts": [_post_dict(p) for p in posts]}

    @app.post("/api/admin/blogs", tags=["Admin / Blog"])
    async def admin_blog_create(request: Request, db: Session = Depends(get_db)):
        _admin_check(request, allow_assistant=True)
        data = await request.json()

        title = data.get("title", "").strip()
        if not title:
            return JSONResponse({"success": False, "error": "Title is required"}, status_code=400)

        slug = _unique_slug(db, _slugify(title))
        tags_raw = data.get("tags", [])
        tags_json = json.dumps(tags_raw) if isinstance(tags_raw, list) else json.dumps([])
        content = data.get("content", "")

        post = BlogPost(
            slug              = slug,
            title             = title,
            excerpt           = data.get("excerpt", "").strip() or None,
            content           = content,
            cover_image_url   = data.get("cover_image_url", "").strip() or None,
            category          = data.get("category", "General"),
            tags              = tags_json,
            author_name       = data.get("author_name", "SolaceSquad Team").strip(),
            author_avatar_url = data.get("author_avatar_url", "").strip() or None,
            status            = "draft",
            read_time_minutes = _read_time(content),
        )
        db.add(post)
        db.commit()
        db.refresh(post)

        # Alert admin when an assistant creates a new draft
        try:
            _uid = request.session.get("user_id")
            _utype = request.session.get("user_type", "")
            if _utype == "admin_assistant" and _uid:
                from models import User as _User
                _asst = db.query(_User).filter(_User.id == _uid).first()
                _admin_email = os.getenv("ADMIN_EMAIL", "admin@solacesquad.com")
                from sendgrid_email import send_admin_assistant_blog_saved_alert
                import threading
                threading.Thread(
                    target=send_admin_assistant_blog_saved_alert,
                    args=(_admin_email, post.title, _asst.name if _asst else "Assistant", post.id),
                    daemon=True,
                ).start()
        except Exception as _e:
            print(f"[EMAIL] blog draft alert failed: {_e}")

        return {"success": True, "post": _post_dict(post)}

    @app.put("/api/admin/blogs/{post_id}", tags=["Admin / Blog"])
    async def admin_blog_update(post_id: int, request: Request, db: Session = Depends(get_db)):
        _admin_check(request, allow_assistant=True)
        post = db.query(BlogPost).filter(BlogPost.id == post_id).first()
        if not post:
            raise HTTPException(status_code=404, detail="Post not found")

        data = await request.json()
        if "title" in data and data["title"].strip():
            new_title = data["title"].strip()
            if new_title != post.title:
                post.slug = _unique_slug(db, _slugify(new_title), exclude_id=post.id)
            post.title = new_title
        if "excerpt" in data:
            post.excerpt = data["excerpt"].strip() or None
        if "content" in data:
            post.content = data["content"]
            post.read_time_minutes = _read_time(data["content"])
        if "cover_image_url" in data:
            post.cover_image_url = data["cover_image_url"].strip() or None
        if "category" in data:
            post.category = data["category"]
        if "tags" in data:
            t = data["tags"]
            post.tags = json.dumps(t) if isinstance(t, list) else json.dumps([])
        if "author_name" in data:
            post.author_name = data["author_name"].strip() or "SolaceSquad Team"
        if "author_avatar_url" in data:
            post.author_avatar_url = data["author_avatar_url"].strip() or None

        post.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(post)
        return {"success": True, "post": _post_dict(post)}

    @app.post("/api/admin/blogs/{post_id}/publish", tags=["Admin / Blog"])
    async def admin_blog_publish(post_id: int, request: Request, db: Session = Depends(get_db)):
        _admin_check(request)
        post = db.query(BlogPost).filter(BlogPost.id == post_id).first()
        if not post:
            raise HTTPException(status_code=404, detail="Post not found")

        if post.status == "published":
            post.status = "draft"
        else:
            post.status = "published"
            if not post.published_at:
                post.published_at = datetime.utcnow()

        post.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(post)

        # Auto-ping Google when a post is published - triggers sitemap re-crawl
        # New posts get discovered within hours, no manual Search Console work needed
        if post.status == "published":
            import asyncio as _asyncio, httpx as _httpx
            async def _ping_google_sitemap():
                try:
                    sitemap = "https://www.solacesquad.com/sitemap.xml"
                    async with _httpx.AsyncClient(timeout=5) as c:
                        await c.get(f"https://www.google.com/ping?sitemap={sitemap}")
                except Exception:
                    pass  # Non-critical - publish succeeds even if ping fails
            _asyncio.create_task(_ping_google_sitemap())

        return {"success": True, "post": _post_dict(post)}

    @app.delete("/api/admin/blogs/{post_id}", tags=["Admin / Blog"])
    async def admin_blog_delete(post_id: int, request: Request, db: Session = Depends(get_db)):
        _admin_check(request)
        post = db.query(BlogPost).filter(BlogPost.id == post_id).first()
        if not post:
            raise HTTPException(status_code=404, detail="Post not found")
        db.delete(post)
        db.commit()
        return {"success": True}

    @app.post("/api/admin/blogs/ai-assist", tags=["Admin / Blog"])
    async def admin_blog_ai_assist(request: Request, db: Session = Depends(get_db)):
        _admin_check(request, allow_assistant=True)
        data = await request.json()
        action = data.get("action", "generate_draft")
        topic = data.get("topic", "")
        existing_content = data.get("existing_content", "")
        category = data.get("category", "General")

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
                "You are a professional wellness content writer for SolaceSquad, "
                "an Indian online wellness consultancy. Write in a warm, empathetic, "
                "evidence-based tone. Content should be practical, uplifting, and "
                "suitable for Indian readers seeking mental, physical, or professional wellness guidance."
            )

            if action == "generate_draft":
                prompt = f"""{system_prompt}

Write a complete wellness blog post about: "{topic}"
Category: {category}

Return a JSON object with these exact keys:
- "title": engaging blog title (string)
- "excerpt": 2-sentence compelling teaser (string)
- "content": full HTML blog post body (use <h2>, <p>, <ul>, <li>, <strong> tags, ~600-900 words)
- "tags": array of 3-5 relevant lowercase tags (array of strings)
- "read_time_minutes": estimated reading time (integer)

Return ONLY valid JSON, no markdown fences."""

            elif action == "improve":
                prompt = f"""{system_prompt}

Improve the following wellness blog content. Make it more engaging, clearer, and better structured.
Keep the same topic but enhance the writing quality.

Original content:
{existing_content[:3000]}

Return a JSON object with:
- "content": improved full HTML content
- "excerpt": improved 2-sentence excerpt

Return ONLY valid JSON."""

            elif action == "suggest_tags":
                prompt = f"""{system_prompt}

Suggest relevant tags for a wellness blog post with this content:
Title/Topic: {topic}
Content preview: {(existing_content or topic)[:500]}

Return a JSON object with:
- "tags": array of exactly 5 relevant lowercase tags

Return ONLY valid JSON."""

            elif action == "write_intro":
                prompt = f"""{system_prompt}

Write a compelling introduction paragraph (HTML) for a wellness blog post about: "{topic}"
Category: {category}

Return a JSON object with:
- "intro": HTML paragraph(s) for the introduction (~100-150 words)

Return ONLY valid JSON."""

            elif action == "suggest_title":
                prompt = f"""{system_prompt}

Suggest 5 compelling blog post titles about: "{topic}"
Category: {category}

Return a JSON object with:
- "titles": array of 5 title strings

Return ONLY valid JSON."""

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

    # ── Admin Page ────────────────────────────────────────────────────────────

    @app.get("/admin/blogs", response_class=HTMLResponse, tags=["Admin / Blog"])
    async def admin_blogs_page(request: Request):
        uid = request.session.get("user_id")
        if not uid:
            from fastapi.responses import RedirectResponse
            return RedirectResponse("/login")
        user_type = request.session.get("user_type", "")
        # Allow both admin and admin_assistant
        if user_type not in ("admin", "admin_assistant"):
            from fastapi.responses import RedirectResponse
            return RedirectResponse("/login")
        return templates.TemplateResponse(
            "pages/admin_blogs.html",
            {"request": request, "user_type": user_type}
        )
