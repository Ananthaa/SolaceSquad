"""Patch subscription_routes.py to add HMAC page token auth fallback."""
import os, sys

path = r"c:\Anantha\Projects\Soul Squad\backend\subscription_routes.py"
content = open(path, encoding="utf-8").read()

# ── 1. Replace the plans page route (lines 665-679) ─────────────────────────
old = ('    @app.get("/app/plans", response_class=HTMLResponse)\n'
       '    async def user_plans_page(request: Request, db: Session = Depends(get_db)):\n'
       '        uid = request.session.get("user_id")\n'
       '        if not uid:\n'
       '            return RedirectResponse("/login", status_code=303)\n'
       '        user_name = request.session.get("user_name", "User")\n'
       '        from main import get_initials\n'
       '        return templates.TemplateResponse("pages/plans.html", {\n'
       '            "request": request,\n'
       '            "page_title": "Choose a Plan \u00e2\u20ac\u201c SolaceSquad",\n'
       '            "user_name": user_name,\n'
       '            "user_initials": _local_get_initials(user_name),\n'
       '            "user_type": "user",\n'
       '            "active_page": "plans",\n'
       '        })')

new = (
    '    def _make_page_token(uid: int) -> str:\n'
    '        """HMAC token for cookie-independent auth fallback."""\n'
    '        import hmac as _h, hashlib as _hs, os as _os, time as _t\n'
    '        ts = str(int(_t.time()) // 60)\n'
    '        secret = _os.getenv("SECRET_KEY", "fallback-dev-key").encode()\n'
    '        sig = _h.new(secret, f"{uid}:{ts}".encode(), _hs.sha256).hexdigest()[:16]\n'
    '        return f"{uid}:{ts}:{sig}"\n'
    '\n'
    '    def _verify_page_token(token: str):\n'
    '        """Return uid int if token valid, else None.\"\"\"\n'
    '        import hmac as _h, hashlib as _hs, os as _os, time as _t\n'
    '        try:\n'
    '            parts = token.split(":")\n'
    '            if len(parts) != 3: return None\n'
    '            uid_str, ts_str, sig = parts\n'
    '            if abs(int(_t.time()) // 60 - int(ts_str)) > 30: return None\n'
    '            secret = _os.getenv("SECRET_KEY", "fallback-dev-key").encode()\n'
    '            expected = _h.new(secret, f"{uid_str}:{ts_str}".encode(), _hs.sha256).hexdigest()[:16]\n'
    '            return int(uid_str) if _h.compare_digest(sig, expected) else None\n'
    '        except Exception:\n'
    '            return None\n'
    '\n'
    '    @app.get("/app/plans", response_class=HTMLResponse)\n'
    '    async def user_plans_page(request: Request, db: Session = Depends(get_db)):\n'
    '        uid = request.session.get("user_id")\n'
    '        if not uid:\n'
    '            return RedirectResponse("/login", status_code=303)\n'
    '        user_name = request.session.get("user_name", "User")\n'
    '        page_token = _make_page_token(uid)\n'
    '        return templates.TemplateResponse("pages/plans.html", {\n'
    '            "request": request,\n'
    '            "page_title": "Choose a Plan - SolaceSquad",\n'
    '            "user_name": user_name,\n'
    '            "user_initials": _local_get_initials(user_name),\n'
    '            "user_type": "user",\n'
    '            "active_page": "plans",\n'
    '            "page_token": page_token,\n'
    '        })'
)

if old in content:
    content = content.replace(old, new, 1)
    print("OK: replaced plans page route with token support")
else:
    # Try matching without the garbled em-dash — find via simpler anchor
    anchor = '        from main import get_initials\n        return templates.TemplateResponse("pages/plans.html"'
    if anchor in content:
        # Find the full block
        start = content.find('    @app.get("/app/plans"')
        end = content.find('\n    # ', start + 10)
        block = content[start:end]
        print("Block found:")
        print(repr(block[:200]))
        # Replace the whole block
        content = content[:start] + new + '\n\n' + content[end:]
        print("OK: replaced via anchor method")
    else:
        print("FAILED: could not find block")
        sys.exit(1)

# ── 2. Update api_subscribe to use token fallback (after the session check) ──
# The current code after our previous edit already has:
# uid = request.session.get("user_id")
# _auth_method = "session"
# if not uid: ...
# We need to add the token fallback between the session check and the failure

old_subscribe_auth = (
    '        # Primary: session cookie auth\n'
    '        uid = request.session.get("user_id")\n'
    '        _auth_method = "session"\n'
    '        if not uid:\n'
    '            # Fallback: page token in request body (handles PWA/mobile cookie issues)\n'
    '            try:\n'
    '                _body = await request.body()\n'
    '                import json as _json\n'
    '                _data_pre = _json.loads(_body) if _body else {}\n'
    '                _token = _data_pre.get("page_token", "")\n'
    '                if _token:\n'
    '                    uid = _verify_page_token(_token)\n'
    '                    _auth_method = "token"\n'
    '            except Exception:\n'
    '                pass\n'
    '        if not uid:\n'
    '            return JSONResponse({\n'
    '                "success": False,\n'
    '                "error": "Please log out and log back in, then try again."\n'
    '            }, status_code=401)'
)

if old_subscribe_auth in content:
    print("OK: token fallback already present in api_subscribe")
else:
    # It may not have the token fallback yet - add it
    old_simple = (
        '        uid = request.session.get("user_id")\n'
        '        if not uid:\n'
        '            return JSONResponse({\n'
        '                "success": False,\n'
        '                "error": "Please log out and log back in, then try again."\n'
        '            }, status_code=401)'
    )
    new_with_token = (
        '        # Auth: try session cookie first, fall back to page token\n'
        '        uid = request.session.get("user_id")\n'
        '        if not uid:\n'
        '            try:\n'
        '                _body = await request.body()\n'
        '                import json as _json\n'
        '                _data_pre = _json.loads(_body) if _body else {}\n'
        '                _token = _data_pre.get("page_token", "")\n'
        '                if _token:\n'
        '                    uid = _verify_page_token(_token)\n'
        '            except Exception:\n'
        '                pass\n'
        '        if not uid:\n'
        '            return JSONResponse({\n'
        '                "success": False,\n'
        '                "error": "Session expired. Please log out and log back in."\n'
        '            }, status_code=401)'
    )
    if old_simple in content:
        content = content.replace(old_simple, new_with_token, 1)
        print("OK: added token fallback to api_subscribe")
    else:
        print("WARN: could not add token fallback to api_subscribe (may already be patched differently)")

open(path, "w", encoding="utf-8").write(content)
print("Saved.")
