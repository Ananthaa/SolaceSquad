"""
Emora AI Chat — 3-Tier Fallback Strategy
  Tier 1: Vertex AI (HIPAA-eligible, preferred for production with signed BAA)
  Tier 2: Direct Gemini API (google-generativeai + GEMINI_API_KEY) — reliable fallback
  Tier 3: Simple rule-based bot (offline, last resort only)

NOTE: gemini-2.5-flash on Vertex AI requires location="global".
      If GCP_LOCATION env var is set to anything else (e.g. us-central1),
      Vertex AI will fail and Tier 2 (direct Gemini API) is used automatically.
"""
import os
import time
from typing import List, Dict

# ── Vertex AI (Tier 1, HIPAA-eligible) ───────────────────────────────────────
try:
    import vertexai
    from vertexai.generative_models import GenerativeModel as _VXModel, Content, Part
    _VERTEX_AVAILABLE = True
except ImportError:
    _VERTEX_AVAILABLE = False

# ── Direct Gemini API (Tier 2, reliable fallback) ────────────────────────────
try:
    import google.generativeai as genai
    _GENAI_AVAILABLE = True
except ImportError:
    _GENAI_AVAILABLE = False

_GCP_PROJECT   = os.getenv("GCP_PROJECT_ID", "abiding-idea-485817-k2")
_GCP_LOCATION  = os.getenv("GCP_LOCATION",   "global")   # gemini-2.5-flash requires "global"
_VERTEX_MODEL  = "gemini-2.5-flash"
_GEMINI_MODEL  = "gemini-2.0-flash"                       # Used for direct API tier
_GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")


def _load_system_prompt() -> str:
    """Read system_prompt.md — fall back to inline prompt if file not found."""
    try:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        prompt_path = os.path.join(base_dir, "prompts", "system_prompt.md")
        with open(prompt_path, "r", encoding="utf-8") as f:
            text = f.read()
        print(f"[Emora] Loaded system prompt ({len(text)} chars) from {prompt_path}")
        return text
    except Exception as e:
        print(f"[Emora] Could not load system_prompt.md: {e} — using inline fallback")
        return (
            "You are Emora — a warm, caring AI wellness companion on the SolaceSquad platform. "
            "Always respond with empathy and keep replies short (1-3 sentences). "
            "Never give generic positive responses when someone expresses a negative emotion — "
            "acknowledge their difficulty first. "
            "Never mention external helplines. If someone needs urgent help, "
            "direct them to book a SolaceSquad consultant. "
            "If you get confused or are unsure about how to spell a user's name, address them as 'pal', ask how they would like you to address them (say by first or last name), and invite them to speak their name on the mic so you can hear and pronounce it the same way. "
            "AUTOMATICALLY detect the language the user is speaking in, and ALWAYS respond accordingly in that exact same language. AT THE END of your response, ALWAYS append a tag in the format `[LANG: xx-IN]` indicating the language you are replying in. Use Sarvam language codes like hi-IN (Hindi), ta-IN (Tamil), bn-IN (Bengali), mr-IN (Marathi), gu-IN (Gujarati), pa-IN (Punjabi), te-IN (Telugu), kn-IN (Kannada), ml-IN (Malayalam), or-IN (Odia), or en-IN (English)."
        )


class GeminiChat:
    def __init__(self):
        self.system_prompt  = _load_system_prompt()
        self.vertex_model   = None
        self.genai_model    = None
        self.available      = False

        # ── Tier 1: Vertex AI (HIPAA-eligible) ───────────────────────────────
        if _VERTEX_AVAILABLE:
            try:
                vertexai.init(project=_GCP_PROJECT, location=_GCP_LOCATION)
                self.vertex_model = _VXModel(
                    _VERTEX_MODEL,
                    system_instruction=self.system_prompt,
                )
                # Warm-up: raises immediately on bad model/access
                self.vertex_model.generate_content(
                    "hi",
                    generation_config={"max_output_tokens": 5},
                )
                self.available = True
                print(f"[Emora] [OK] Tier 1 Vertex AI ready: {_VERTEX_MODEL} "
                      f"(project={_GCP_PROJECT}, location={_GCP_LOCATION})")
            except Exception as e:
                print(f"[Emora] [WARN] Tier 1 Vertex AI failed: {e}")
                self.vertex_model = None

        # ── Tier 2: Direct Gemini API ─────────────────────────────────────────
        if not self.available and _GENAI_AVAILABLE and _GEMINI_API_KEY:
            try:
                genai.configure(api_key=_GEMINI_API_KEY)
                self.genai_model = genai.GenerativeModel(
                    _GEMINI_MODEL,
                    system_instruction=self.system_prompt,
                )
                # Warm-up
                self.genai_model.generate_content(
                    "hi",
                    generation_config={"max_output_tokens": 5},
                )
                self.available = True
                print(f"[Emora] [OK] Tier 2 Direct Gemini API ready: {_GEMINI_MODEL}")
            except Exception as e:
                print(f"[Emora] [WARN] Tier 2 Direct Gemini API failed: {e}")
                self.genai_model = None

        if not self.available:
            print("[Emora] [WARN] Both Vertex AI and Direct Gemini API unavailable "
                  "— falling back to simple_bot (last resort)")

    def _build_vertex_history(self, conversation_history: List[Dict]):
        """Convert conversation history to Vertex AI Content list."""
        history = []
        if conversation_history:
            for msg in conversation_history[-20:]:
                role    = "user" if msg.get("is_user") else "model"
                content = msg.get("content", "")
                if content:
                    history.append(Content(role=role, parts=[Part.from_text(content)]))
        return history

    def _build_genai_history(self, conversation_history: List[Dict]):
        """Convert conversation history to google-generativeai format."""
        history = []
        if conversation_history:
            for msg in conversation_history[-20:]:
                role    = "user" if msg.get("is_user") else "model"
                content = msg.get("content", "")
                if content:
                    history.append({"role": role, "parts": [content]})
        return history

    def _call_with_retry(self, fn, retries=3, base_delay=2):
        """Call fn(), retrying on 429 Resource Exhausted with exponential back-off."""
        for attempt in range(retries):
            try:
                return fn()
            except Exception as e:
                err = str(e)
                is_rate_limit = (
                    "429" in err
                    or "resource exhausted" in err.lower()
                    or "quota" in err.lower()
                )
                if is_rate_limit and attempt < retries - 1:
                    wait = base_delay * (2 ** attempt)
                    print(f"[Emora] 429 rate limit — retry {attempt+1}/{retries} in {wait}s")
                    time.sleep(wait)
                    continue
                raise   # re-raise on non-429 or final attempt

    def chat(self, message: str, conversation_history: List[Dict] = None) -> str:
        gen_cfg = {"max_output_tokens": 600, "temperature": 0.8, "top_p": 0.92}

        # ── Tier 1: Vertex AI ────────────────────────────────────────────────
        if self.vertex_model:
            try:
                history = self._build_vertex_history(conversation_history)
                session = self.vertex_model.start_chat(history=history)
                def _call_vertex():
                    return session.send_message(message, generation_config=gen_cfg).text.strip()
                result = self._call_with_retry(_call_vertex)
                if result:
                    print(f"[Emora] Tier 1 Vertex AI response: {len(result)} chars")
                    return result
            except Exception as e:
                print(f"[Emora] Tier 1 Vertex AI chat error: {e} — trying Tier 2")

        # ── Tier 2: Direct Gemini API ────────────────────────────────────────
        if self.genai_model:
            try:
                history = self._build_genai_history(conversation_history)
                session = self.genai_model.start_chat(history=history)
                def _call_genai():
                    return session.send_message(message, generation_config=gen_cfg).text.strip()
                result = self._call_with_retry(_call_genai)
                if result:
                    print(f"[Emora] Tier 2 Direct Gemini API response: {len(result)} chars")
                    return result
            except Exception as e:
                print(f"[Emora] Tier 2 Direct Gemini API error: {e} — falling back to simple_bot")

        # ── Tier 3: simple_bot (last resort) ────────────────────────────────
        print("[Emora] Tier 3 simple_bot response")
        from simple_bot import simple_bot
        return simple_bot.get_response(message, conversation_history)

    def is_available(self) -> bool:
        return self.available


# Global instance imported by main.py
gemini_chat = GeminiChat()
