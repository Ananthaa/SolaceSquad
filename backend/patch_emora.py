"""One-shot patch: upgrade send_ai_chat to use 15-message history + user context."""
path = r"c:\Anantha\Projects\Soul Squad\backend\main.py"

with open(path, "r", encoding="utf-8") as f:
    content = f.read()

# --- OLD BLOCK (exact text from clean git state) ---
old_marker = "        # Get recent conversation history for context\n        recent_chats = db.query(AIChatHistory).filter(\n            AIChatHistory.user_id == user_id\n        ).order_by(AIChatHistory.timestamp.desc()).limit(5).all()"
if old_marker not in content:
    print("ERROR: old marker not found. Aborting.")
    exit(1)

# Find start and end of the block we want to replace inside send_ai_chat
# End marker: just before "        # Get AI response using Gemini API"
old_end = "        # Get AI response using Gemini API\n        from gemini_chat import gemini_chat\n        ai_response = gemini_chat.chat(message, conversation_history)\n        \n        # Save to database (use empty string for greeting trigger so it's invisible in history)\n        saved_message = \"\" if is_greeting else message"

start_idx = content.find(old_marker)
end_idx   = content.find(old_end, start_idx)
if start_idx == -1 or end_idx == -1:
    print(f"ERROR: markers not found. start={start_idx} end={end_idx}")
    exit(1)

end_idx += len(old_end)  # include old end in replacement range
old_section = content[start_idx:end_idx]

new_section = (
    "        # Get recent conversation history -- 15 exchanges for richer memory\n"
    "        recent_chats = db.query(AIChatHistory).filter(\n"
    "            AIChatHistory.user_id == user_id\n"
    "        ).order_by(AIChatHistory.timestamp.desc()).limit(15).all()\n"
    "\n"
    "        # Build history oldest-first, skip empty greeting rows\n"
    "        conversation_history = []\n"
    "        for chat in reversed(recent_chats):\n"
    "            if chat.message:\n"
    "                conversation_history.append({\"content\": chat.message, \"is_user\": True})\n"
    "            if chat.response:\n"
    "                conversation_history.append({\"content\": chat.response, \"is_user\": False})\n"
    "\n"
    "        # -- User context enrichment --\n"
    "        user_display_name = \"there\"\n"
    "        user_context_note = \"\"\n"
    "        try:\n"
    "            user_obj = db.query(User).filter(User.id == user_id).first()\n"
    "            if user_obj:\n"
    "                user_display_name = user_obj.preferred_name or user_obj.first_name or \"there\"\n"
    "            user_context_note = f\"The user's name is {user_display_name}.\"\n"
    "        except Exception:\n"
    "            pass\n"
    "        try:\n"
    "            from sqlalchemy import desc as _desc\n"
    "            mood_entry = db.query(MoodEntry).filter(\n"
    "                MoodEntry.user_id == user_id\n"
    "            ).order_by(_desc(MoodEntry.date)).first()\n"
    "            if mood_entry:\n"
    "                user_context_note += f\" Their most recently logged mood is '{mood_entry.mood}'.\"\n"
    "        except Exception:\n"
    "            pass\n"
    "\n"
    "        # -- Message handling --\n"
    "        original_message = message\n"
    "        is_greeting = message.startswith(\"__GREET__:\")\n"
    "        if is_greeting:\n"
    "            name = message.split(\"__GREET__:\", 1)[-1].strip() or user_display_name\n"
    "            message = (\n"
    "                f\"[CONTEXT: {user_context_note}] \"\n"
    "                f\"Greet {name} warmly in 1-2 sentences. \"\n"
    "                f\"Start with 'Hi {name}!' then ask how they're feeling today. \"\n"
    "                f\"Be casual and friendly.\"\n"
    "            )\n"
    "        else:\n"
    "            if user_context_note:\n"
    "                message = f\"[CONTEXT: {user_context_note}] {message}\"\n"
    "\n"
    "        # Get AI response using Gemini API\n"
    "        from gemini_chat import gemini_chat\n"
    "        ai_response = gemini_chat.chat(message, conversation_history)\n"
    "\n"
    "        # Save original message (not the enriched version)\n"
    "        saved_message = \"\" if is_greeting else original_message"
)

new_content = content[:start_idx] + new_section + content[end_idx:]

with open(path, "w", encoding="utf-8") as f:
    f.write(new_content)

print("SUCCESS: send_ai_chat upgraded.")
print(f"  Replaced {len(old_section)} chars with {len(new_section)} chars")
