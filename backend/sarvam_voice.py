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

# Reuse persistent HTTP connection session to minimize TCP/TLS handshake latency
_sarvam_session = requests.Session()

DEFAULT_LANG   = "en-IN"
TTS_SPEAKER    = "anushka"    # warm, soft — suits Emora's therapeutic persona
TTS_MODEL      = "bulbul:v2"
STT_MODEL      = "saaras:v3"

# Phrase spoken instead of reading out a URL
_LINK_PHRASE   = "I've shared the link in the chat"

SARVAM_LANG_TO_NAME = {
    "en-IN": "English",
    "hi-IN": "Hindi",
    "kn-IN": "Kannada",
    "te-IN": "Telugu",
    "ta-IN": "Tamil",
    "mr-IN": "Marathi",
    "bn-IN": "Bengali",
    "ml-IN": "Malayalam",
    "gu-IN": "Gujarati",
    "pa-IN": "Punjabi",
    "or-IN": "Odia",
}

NAME_TO_SARVAM_LANG = {
    "english": "en-IN",
    "hindi": "hi-IN",
    "kannada": "kn-IN",
    "telugu": "te-IN",
    "tamil": "ta-IN",
    "marathi": "mr-IN",
    "bengali": "bn-IN",
    "malayalam": "ml-IN",
    "gujarati": "gu-IN",
    "punjabi": "pa-IN",
    "odia": "or-IN",
}


def detect_text_language(text: str) -> tuple:
    """
    Detect language from Unicode script or vocabulary.
    Returns (sarvam_lang_code, language_name), e.g. ('kn-IN', 'Kannada').
    """
    if not text:
        return "en-IN", "English"

    import re
    # Check Unicode script blocks for Indic scripts
    if re.search(r'[\u0C80-\u0CFF]', text):
        return "kn-IN", "Kannada"
    if re.search(r'[\u0C00-\u0C7F]', text):
        return "te-IN", "Telugu"
    if re.search(r'[\u0B80-\u0BFF]', text):
        return "ta-IN", "Tamil"
    if re.search(r'[\u0D00-\u0D7F]', text):
        return "ml-IN", "Malayalam"
    if re.search(r'[\u0980-\u09FF]', text):
        return "bn-IN", "Bengali"
    if re.search(r'[\u0A80-\u0AFF]', text):
        return "gu-IN", "Gujarati"
    if re.search(r'[\u0A00-\u0A7F]', text):
        return "pa-IN", "Punjabi"
    if re.search(r'[\u0B00-\u0B7F]', text):
        return "or-IN", "Odia"
    if re.search(r'[\u0900-\u097F]', text):
        if any(w in text.lower() for w in ["आहे", "नाही", "कसं", "मला", "तुम्ही", "होय", "नमस्कार"]):
            return "mr-IN", "Marathi"
        return "hi-IN", "Hindi"

    return "en-IN", "English"


def to_speech_text(text: str) -> str:
    """
    Convert Emora's full text response into a clean, voice-friendly version:
      - Strips all emojis (astral & BMP)
      - Strips text emoticons (:), :-), :D, <3, etc.)
      - Strips roleplay actions (*smiles*, *sighs*, etc.)
      - Converts currency ₹ to 'Rupees'
      - Strips markdown formatting, symbols (#, *, _, ~, `, |, <, >, [, ], {, }, etc.)
      - Normalizes smart quotes and dashes
      - Normalizes whitespace and punctuation
    """
    import re

    if not text:
        return ""

    t = text

    # 1. Markdown links: [label](url) -> label + ". " + _LINK_PHRASE
    t = re.sub(
        r'\[([^\]]+)\]\((https?://|[wW]{3}\.)[^\)]+\)',
        lambda m: m.group(1) + ". " + _LINK_PHRASE,
        t
    )

    # 2. Bare URLs (http://, https://, or www.)
    t = re.sub(r'(https?://\S+|[wW]{3}\.\S+)', _LINK_PHRASE, t)

    # 3. Currency symbols conversion: ₹500 -> 500 Rupees
    t = re.sub(r'₹\s*(\d+)', r'\1 Rupees', t)
    t = re.sub(r'Rs\.?\s*(\d+)', r'\1 Rupees', t, flags=re.IGNORECASE)

    # 4. Remove roleplay actions in asterisks or parentheses: *smiles*, *gently laughs*, (pauses), etc.
    t = re.sub(r'\*[a-zA-Z\s]{2,30}\*', ' ', t)
    t = re.sub(r'\([a-zA-Z\s]{2,20}\)', ' ', t)

    # 5. Remove astral plane emojis (U+10000 to U+10FFFF)
    t = re.sub(r'[\U00010000-\U0010ffff]', ' ', t)

    # 6. Remove BMP symbols, Dingbats, Technical, Arrows, Miscellaneous symbols, variation selectors
    bmp_symbols_pattern = r'[\u200B-\u200D\uFE0E\uFE0F\u2028-\u202F\u2190-\u21FF\u2300-\u23FF\u2460-\u24FF\u2500-\u27BF\u2900-\u297F\u2B00-\u2BFF\uFE00-\uFE0F]'
    t = re.sub(bmp_symbols_pattern, ' ', t)

    # 7. Common text emoticons
    emoticon_patterns = [
        r'(?:\s|^)[:;=8][\-~o\*\']?[\)\]\(\[dDpP/\\](?=\s|$|[.,!?])', # :), :-(, :D, ;), :P
        r'(?:\s|^)[\)\]\(\[][\-~]?[:;=8](?=\s|$|[.,!?])', # (:, (-:
        r'(?:\s|^)[D][:;=](?=\s|$|[.,!?])', # D:
        r'(?:\s|^)(<3|</3|\^_\^|\^\.\^|-_-|>_<|o_o|O_O|T_T|TwT|OwO|UwU|\(y\)|\(n\)|xD|XD)(?=\s|$|[.,!?])',
    ]
    for ep in emoticon_patterns:
        t = re.sub(ep, ' ', t)

    # 8. Markdown formatting: bold, italic, strikethrough, headers
    t = re.sub(r'\*{1,3}([^*]+)\*{1,3}', r'\1', t)
    t = re.sub(r'_{1,3}([^_]+)_{1,3}',   r'\1', t)
    t = re.sub(r'~{1,2}([^~]+)~{1,2}',   r'\1', t)
    t = re.sub(r'^#{1,6}\s+', '', t, flags=re.MULTILINE)
    t = re.sub(r'^\s*[-*•+]\s+', '', t, flags=re.MULTILINE)
    t = re.sub(r'^\s*\d+\.\s+', '', t, flags=re.MULTILINE)

    # 9. Smart punctuation to plain punctuation
    t = t.replace('“', '"').replace('”', '"').replace('‘', "'").replace('’', "'")
    t = t.replace('—', ', ').replace('–', ', ').replace('…', '. ')

    # 10. Strip remaining noisy symbols: # * ~ ^ < > [ ] { } | \ ` @ $ % & + =
    t = re.sub(r'[#\*~^<>\\[\]\{\}\|\`@\$%&\+=_/]', ' ', t)

    # 11. Normalize duplicate punctuation
    t = re.sub(r'[!]{2,}', '!', t)
    t = re.sub(r'[\?]{2,}', '?', t)
    t = re.sub(r'[\.]{2,}', '.', t)
    t = re.sub(r'[,]{2,}', ',', t)

    # 12. Collapse multiple blank spaces -> single space
    t = re.sub(r'\s{2,}', ' ', t)

    return t.strip()


def get_sarvam_api_key() -> str:
    return os.getenv("SARVAM_API_KEY", "").strip() or SARVAM_API_KEY.strip()


def stt_with_lid(audio_bytes: bytes, language: str = "unknown") -> tuple:
    """
    Speech-to-Text via Sarvam REST API with automatic Language Identification (LID).
    Returns (transcript, detected_language_code).
    """
    api_key = get_sarvam_api_key()
    if not api_key:
        logger.error("[Sarvam STT] SARVAM_API_KEY not set")
        return "", ""
    if not audio_bytes:
        logger.warning("[Sarvam STT] Empty audio bytes received")
        return "", ""

    lang_code = language if (language and language.strip()) else "unknown"

    try:
        headers = {"api-subscription-key": api_key}

        # Multipart file upload — explicit content-type so Sarvam can detect format
        files = {
            "file": ("recording.webm", audio_bytes, "audio/webm")
        }
        data = {
            "model":         STT_MODEL,
            "language_code": lang_code,
            "mode":          "transcribe",
        }

        resp = _sarvam_session.post(
            STT_URL,
            headers=headers,
            files=files,
            data=data,
            timeout=25,
        )

        logger.info(f"[Sarvam STT] HTTP {resp.status_code}, body={resp.text[:300]}")
        resp.raise_for_status()

        result     = resp.json()
        transcript = (result.get("transcript") or "").strip()
        detected_lang = (result.get("language_code") or (lang_code if lang_code != "unknown" else "en-IN")).strip()
        logger.info(f"[Sarvam STT] req_lang={lang_code} → detected={detected_lang} transcript={transcript!r}")
        return transcript, detected_lang

    except requests.HTTPError as e:
        logger.error(f"[Sarvam STT] HTTP error {e.response.status_code}: {e.response.text[:200]}")
        return "", ""
    except Exception as e:
        logger.error(f"[Sarvam STT] Error: {e}")
        return "", ""


def stt(audio_bytes: bytes, language: str = "unknown") -> str:
    """
    Speech-to-Text via Sarvam REST API.
    Accepts webm audio from browser MediaRecorder.
    Returns transcript string, or "" on failure.
    """
    transcript, _ = stt_with_lid(audio_bytes, language=language)
    return transcript


def tts(text: str, language: str = DEFAULT_LANG) -> bytes:
    """
    Text-to-Speech via Sarvam REST API.
    Returns raw MP3 bytes, or b"" on failure.
    """
    api_key = get_sarvam_api_key()
    if not api_key:
        logger.error("[Sarvam TTS] SARVAM_API_KEY not set")
        return b""
    if not text:
        return b""

    # Resolve language code if name is provided (e.g. 'Kannada' -> 'kn-IN')
    lang_code = NAME_TO_SARVAM_LANG.get(language.lower(), language)
    if lang_code not in SARVAM_LANG_TO_NAME:
        lang_code = DEFAULT_LANG

    try:
        safe_text = text.strip()
        if len(safe_text) > 500:
            # Cut at the last sentence boundary before 500 chars to avoid mid-sentence audio cuts
            cut_idx = max(safe_text.rfind('. ', 0, 500), safe_text.rfind('! ', 0, 500), safe_text.rfind('? ', 0, 500))
            if cut_idx > 100:
                safe_text = safe_text[:cut_idx + 1].strip()
            else:
                space_idx = safe_text.rfind(' ', 0, 500)
                safe_text = safe_text[:space_idx].strip() if space_idx > 100 else safe_text[:500].strip()

        headers = {
            "api-subscription-key": api_key,
            "Content-Type":         "application/json",
        }
        payload = {
            "inputs":               [safe_text],
            "target_language_code": lang_code,
            "speaker":              TTS_SPEAKER,
            "model":                TTS_MODEL,
            "pace":                 0.95,
            "loudness":             1.4,
            "enable_preprocessing": True,
        }

        resp = _sarvam_session.post(
            TTS_URL,
            headers=headers,
            json=payload,
            timeout=25,
        )

        logger.info(f"[Sarvam TTS] HTTP {resp.status_code} lang={lang_code}")
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
