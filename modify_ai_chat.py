with open(r'c:\Anantha\Projects\Soul Squad\backend\main.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Modify AI chat function signature
old_ai_chat = '''@app.get("/app/ai-chat", response_class=HTMLResponse)
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
    )'''

new_ai_chat = '''@app.get("/app/ai-chat", response_class=HTMLResponse)
async def ai_chat_page(request: Request, mood: str = None):
    """AI Chat page with optional mood context"""
    user_name = request.session.get("user_name", "User")

    # Generate initials
    name_parts = user_name.split()
    if len(name_parts) >= 2:
        initials = f"{name_parts[0][0]}{name_parts[-1][0]}".upper()
    elif len(name_parts) == 1:
        initials = name_parts[0][:2].upper()
    else:
        initials = "U"
    
    # Generate mood context message for AI
    mood_context = ""
    if mood:
        mood_messages = {
            "1": "The user is feeling terrible and really struggling. Please be extra compassionate and supportive.",
            "2": "The user is having a very bad day. Please offer comfort and understanding.",
            "3": "The user is feeling bad and not doing well. Please be empathetic and encouraging.",
            "4": "The user is feeling okay, just getting by. Please be supportive.",
            "5": "The user is feeling good and positive. Please maintain their positive mood.",
            "6": "The user is feeling great and having a wonderful day. Please celebrate with them.",
            "7": "The user is feeling excellent and on top of the world. Please share their joy."
        }
        mood_context = mood_messages.get(mood, "")

    return templates.TemplateResponse(
        "pages/ai_chat.html",
        {
            "request": request,
            "page_title": "AI Assistant - SolaceSquad",
            "user_name": user_name,
            "user_initials": initials,
            "user_type": "user",
            "active_page": "ai-chat",
            "nav_items": get_nav_items("user"),
            "mood_context": mood_context
        }
    )'''

content = content.replace(old_ai_chat, new_ai_chat)

with open(r'c:\Anantha\Projects\Soul Squad\backend\main.py', 'w', encoding='utf-8') as f:
    f.write(content)

print('Successfully modified AI chat to accept mood context')
