"""
Emora AI Chat — HIPAA-Compliant, Vertex AI Only
  Tier 1: Vertex AI (GCP, HIPAA-eligible under Cloud BAA) — primary
  Tier 2: Simple rule-based bot (local, no data leaves instance) — last resort

IMPORTANT — HIPAA NOTE:
  The direct Gemini API (google.generativeai / api.google.com) is intentionally
  NOT used here. It is not covered under Google Cloud's HIPAA BAA.
  Only Vertex AI (a GCP service) is covered by the BAA for PHI-adjacent data.

  GCP_LOCATION must be set to "global" for gemini-2.5-flash on Vertex AI.
  If it is set to "us-central1", Vertex AI will fail and fall to simple_bot.
"""
import os
import time
from typing import List, Dict

# ── Vertex AI (HIPAA-eligible, primary) ──────────────────────────────────────
try:
    import vertexai
    from vertexai.generative_models import GenerativeModel as _VXModel, Content, Part
    _VERTEX_AVAILABLE = True
except ImportError:
    _VERTEX_AVAILABLE = False

_GCP_PROJECT  = os.getenv("GCP_PROJECT_ID", "abiding-idea-485817-k2")
_GCP_LOCATION = os.getenv("GCP_LOCATION",   "global")   # must be "global" for gemini-2.5-flash
_VERTEX_MODEL = "gemini-2.5-flash"


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
            "If you get confused or are unsure about how to spell a user's name, address them as 'pal', ask how they would like you to address them (say by first or last name), and invite them to speak their name on the mic so you can hear and pronounce it the same way."
        )


class GeminiChat:
    def __init__(self):
        self.system_prompt = _load_system_prompt()
        self.vertex_model  = None
        self.available     = False

        # ── Vertex AI (HIPAA-eligible) ────────────────────────────────────────
        if _VERTEX_AVAILABLE:
            try:
                vertexai.init(project=_GCP_PROJECT, location=_GCP_LOCATION)
                self.vertex_model = _VXModel(
                    _VERTEX_MODEL,
                    system_instruction=self.system_prompt,
                )
                # Warm-up: raises immediately on bad model name / missing access
                self.vertex_model.generate_content(
                    "hi",
                    generation_config={"max_output_tokens": 5},
                )
                self.available = True
                print(f"[Emora] [OK] Vertex AI ready: {_VERTEX_MODEL} "
                      f"(project={_GCP_PROJECT}, location={_GCP_LOCATION})")
            except Exception as e:
                print(f"[Emora] [WARN] Vertex AI failed: {e}")
                self.vertex_model = None

        if not self.available:
            print("[Emora] [WARN] Vertex AI unavailable — falling back to simple_bot "
                  "(direct Gemini API intentionally disabled: not HIPAA-eligible)")

    def _build_history(self, conversation_history: List[Dict]):
        """Convert conversation history to Vertex AI Content list."""
        history = []
        if conversation_history:
            for msg in conversation_history[-20:]:
                role    = "user" if msg.get("is_user") else "model"
                content = msg.get("content", "")
                if content:
                    history.append(Content(role=role, parts=[Part.from_text(content)]))
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

        # ── Tier 1: Vertex AI (HIPAA-eligible) ───────────────────────────────
        if self.vertex_model:
            try:
                history = self._build_history(conversation_history)
                session = self.vertex_model.start_chat(history=history)
                def _call():
                    return session.send_message(message, generation_config=gen_cfg).text.strip()
                result = self._call_with_retry(_call)
                if result:
                    print(f"[Emora] Vertex AI response: {len(result)} chars")
                    return result
            except Exception as e:
                print(f"[Emora] Vertex AI chat error: {e} — falling back to simple_bot")

        # ── Vertex AI unavailable: return a graceful message ─────────────────
        # Never fall back to simple_bot — a clear message is better than a
        # broken rule-based response that misunderstands the user.
        print("[Emora] Vertex AI unavailable — returning service-unavailable message")
        return (
            "I'm sorry, I'm having a little trouble connecting right now. "
            "Please try again in a moment. If you need immediate support, "
            "you can book a session with one of our SolaceSquad consultants."
        )

    def is_available(self) -> bool:
        return self.available


# Global instance imported by main.py
gemini_chat = GeminiChat()
