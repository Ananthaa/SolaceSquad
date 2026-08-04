"""
sarvam_voice.py  — Sarvam AI voice layer for Emora
────────────────────────────────────────────────────
Uses the Sarvam REST API directly (not the SDK) so we have full control
over multipart file-upload content-type detection.

  stt(audio_bytes, language)  →  transcript string
  tts(text, language)         →  MP3 audio bytes
"""
import os
import base64
import logging
import requests

logger = logging.getLogger(__name__)

SARVAM_API_KEY = os.getenv("SARVAM_API_KEY", "")
STT_URL        = "https://api.sarvam.ai/speech-to-text"
TTS_URL        = "https://api.sarvam.ai/text-to-speech"

DEFAULT_LANG   = "en-IN"
TTS_SPEAKER    = "anushka"    # warm, soft — suits Emora's therapeutic persona
TTS_MODEL      = "bulbul:v2"
STT_MODEL      = "saaras:v3"

# Phrase spoken instead of reading out a URL
_LINK_PHRASE   = "I've shared the link in the chat"


def to_speech_text(text: str) -> str:
    """
    Convert Emora's full text response into a voice-friendly version:
      - Markdown links [label](url)  →  label + ", " + _LINK_PHRASE
      - Bare URLs https://...        →  _LINK_PHRASE
      - Markdown bold/italic **x**, *x*, __x__, _x_  →  plain text
      - Markdown headers ## Title   →  Title
      - Bullet dashes/asterisks     →  removed
      - Emoticons and emojis        →  removed
      - Special chars (#,*,~,<,>,etc)→ removed
      - Multiple blank lines        →  single space

    The original text (with links) is still returned as reply_text
    for the chat window — this function only affects what Emora speaks.
    """
    import re

    t = text

    # 1. Markdown links: [label](url) → "label, I've shared the link in the chat"
    t = re.sub(
        r'\[([^\]]+)\]\((https?://|[wW]{3}\.)[^\)]+\)',
        lambda m: m.group(1) + ". " + _LINK_PHRASE,
        t
    )

    # 2. Bare URLs (http://, https://, or www.)
    t = re.sub(r'(https?://\S+|[wW]{3}\.\S+)', _LINK_PHRASE, t)

    # 3. Strip out emojis (Unicode ranges for emoticons, dingbats, transport, UI symbols, etc.)
    t = re.sub(r'[\U00010000-\U0010ffff]', '', t)
    
    # 4. Strip out common text emoticons carefully (e.g. :-) :) :D), avoiding normal punctuation
    t = re.sub(r'(?:\s|^)[:;=][\-~]?[\)\]\(\[dDpP](?=\s|$|[.,!?;:\'"/\-])', '', t)

    # 5. Markdown bold/italic: **text**, *text*, __text__, _text_
    t = re.sub(r'\*{1,3}([^*]+)\*{1,3}', r'\1', t)
    t = re.sub(r'_{1,2}([^_]+)_{1,2}',   r'\1', t)

    # 6. Markdown headers: ## Title → Title
    t = re.sub(r'^#{1,6}\s+', '', t, flags=re.MULTILINE)

    # 7. Bullet points: "- item" or "* item" → "item"
    t = re.sub(r'^\s*[-*]\s+', '', t, flags=re.MULTILINE)

    # 8. Strip random special characters, strictly PRESERVING punctuation (. , ! ? ; : ' " / -)
    t = re.sub(r'[#\*~^<>\\[\]|\\_`]', ' ', t)

    # 9. Collapse multiple blank spaces/lines → single space
    t = re.sub(r'\s{2,}', ' ', t)

    return t.strip()


def stt(audio_bytes: bytes, language: str = DEFAULT_LANG) -> str:
    """
    Speech-to-Text via Sarvam REST API.
    Accepts webm audio from browser MediaRecorder.
    Returns transcript string, or "" on failure.
    """
    if not SARVAM_API_KEY:
        logger.error("[Sarvam STT] SARVAM_API_KEY not set")
        return ""
    if not audio_bytes:
        logger.warning("[Sarvam STT] Empty audio bytes received")
        return ""

    try:
        headers = {"api-subscription-key": SARVAM_API_KEY}

        # Multipart file upload — explicit content-type so Sarvam can detect format
        files = {
            "file": ("recording.webm", audio_bytes, "audio/webm")
        }
        data = {
            "model":         STT_MODEL,
            "language_code": language,
            "mode":          "transcribe",
        }

        resp = requests.post(
            STT_URL,
            headers=headers,
            files=files,
            data=data,
            timeout=30,
        )

        logger.info(f"[Sarvam STT] HTTP {resp.status_code}, body={resp.text[:300]}")
        resp.raise_for_status()

        result     = resp.json()
        transcript = (result.get("transcript") or "").strip()
        logger.info(f"[Sarvam STT] lang={language} → {transcript!r}")
        return transcript

    except requests.HTTPError as e:
        logger.error(f"[Sarvam STT] HTTP error {e.response.status_code}: {e.response.text[:200]}")
        return ""
    except Exception as e:
        logger.error(f"[Sarvam STT] Error: {e}")
        return ""


def tts(text: str, language: str = DEFAULT_LANG) -> bytes:
    """
    Text-to-Speech via Sarvam REST API.
    Returns raw MP3 bytes, or b"" on failure.
    """
    if not SARVAM_API_KEY:
        logger.error("[Sarvam TTS] SARVAM_API_KEY not set")
        return b""
    if not text:
        return b""

    try:
        safe_text = text[:500]   # Sarvam TTS max ~500 chars per call
        headers = {
            "api-subscription-key": SARVAM_API_KEY,
            "Content-Type":         "application/json",
        }
        payload = {
            "inputs":               [safe_text],
            "target_language_code": language,
            "speaker":              TTS_SPEAKER,
            "model":                TTS_MODEL,
            "pace":                 0.95,
            "loudness":             1.4,
            "enable_preprocessing": True,
        }

        resp = requests.post(
            TTS_URL,
            headers=headers,
            json=payload,
            timeout=30,
        )

        logger.info(f"[Sarvam TTS] HTTP {resp.status_code}")
        resp.raise_for_status()

        result = resp.json()
        audios = result.get("audios", [])
        if audios and audios[0]:
            audio_bytes = base64.b64decode(audios[0])
            logger.info(f"[Sarvam TTS] OK — {len(audio_bytes)} bytes")
            return audio_bytes

        logger.warning(f"[Sarvam TTS] Empty audios in response: {result}")
        return b""

    except requests.HTTPError as e:
        logger.error(f"[Sarvam TTS] HTTP error {e.response.status_code}: {e.response.text[:200]}")
        return b""
    except Exception as e:
        logger.error(f"[Sarvam TTS] Error: {e}")
        return b""
