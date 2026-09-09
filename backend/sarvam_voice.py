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
TTS_SPEAKER    = "priya"      # authentic Indian female voice (bulbul:v3)
TTS_MODEL      = "bulbul:v3"  # Sarvam bulbul:v3
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
    "od-IN": "Odia",
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
    "odia": "od-IN",
    "oriya": "od-IN",
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


# ─────────────────────────────────────────────────────────────────────────────
# INDIC NUMBER-TO-WORDS CONVERTERS
# ─────────────────────────────────────────────────────────────────────────────
KANNADA_ONES = {
    0: "ಸೊನ್ನೆ", 1: "ಒಂದು", 2: "ಎರಡು", 3: "ಮೂರು", 4: "ನಾಲ್ಕು", 5: "ಐದು",
    6: "ಆರು", 7: "ಏಳು", 8: "ಎಂಟು", 9: "ಒಂಬತ್ತು", 10: "ಹತ್ತು",
    11: "ಹನ್ನೊಂದು", 12: "ಹನ್ನೆರಡು", 13: "ಹದಿಮೂರು", 14: "ಹದಿನಾಲ್ಕು", 15: "ಹದಿನೈದು",
    16: "ಹದಿನಾರು", 17: "ಹದಿನೇಳು", 18: "ಹದಿನೆಂಟು", 19: "ಹತ್ತೊಂಬತ್ತು",
    20: "ಇಪ್ಪತ್ತು", 30: "ಮೂವತ್ತು", 40: "ನಲವತ್ತು", 50: "ಐವತ್ತು",
    60: "ಅರವತ್ತು", 70: "ಎಪ್ಪತ್ತು", 80: "ಎಂಬತ್ತು", 90: "ತೊಂಬತ್ತು"
}
KANNADA_TENS_PREFIX = {
    20: "ಇಪ್ಪತ್ತ", 30: "ಮೂವತ್ತ", 40: "ನಲವತ್ತ", 50: "ಐವತ್ತ",
    60: "ಅರವತ್ತ", 70: "ಎಪ್ಪತ್ತ", 80: "ಎಂಬತ್ತ", 90: "ತೊಂಬತ್ತ"
}
KANNADA_HUNDREDS = {
    1: "ನೂರು", 2: "ಇನ್ನೂರು", 3: "ಮುನ್ನೂರು", 4: "ನಾನ್ನೂರು", 5: "ಐನೂರು",
    6: "ಆರನೂರು", 7: "ಎಳನೂರು", 8: "ಎಂಟುನೂರು", 9: "ಒಂಬೈನೂರು"
}
KANNADA_ORDINALS = {
    1: "ಮೊದಲನೇ", 2: "ಎರಡನೇ", 3: "ಮೂರನೇ", 4: "ನಾಲ್ಕನೇ", 5: "ಐದನೇ",
    6: "ಆರನೇ", 7: "ಏಳನೇ", 8: "ಎಂಟನೇ", 9: "ಒಂಬತ್ತನೇ", 10: "ಹತ್ತನೇ"
}

def int_to_kannada_words(n: int) -> str:
    if n in KANNADA_ONES:
        return KANNADA_ONES[n]
    if n < 100:
        ten = (n // 10) * 10
        rem = n % 10
        return KANNADA_TENS_PREFIX.get(ten, "") + KANNADA_ONES.get(rem, str(rem))
    if n < 1000:
        h = n // 100
        rem = n % 100
        if rem == 0:
            return KANNADA_HUNDREDS.get(h, f"{int_to_kannada_words(h)} ನೂರು")
        h_word = KANNADA_HUNDREDS.get(h, "")
        if h == 1:
            h_word = "ನೂರ"
        elif h_word.endswith("ರು"):
            h_word = h_word[:-1] + "ರ"
        return f"{h_word} {int_to_kannada_words(rem)}"
    if n < 100000:
        k = n // 1000
        rem = n % 1000
        k_word = "ಒಂದು ಸಾವಿರ" if k == 1 else f"{int_to_kannada_words(k)} ಸಾವಿರ"
        if rem == 0:
            return k_word
        return f"{k_word}ದ {int_to_kannada_words(rem)}"
    return str(n)


HINDI_ONES = {
    0: "शून्य", 1: "एक", 2: "दो", 3: "तीन", 4: "चार", 5: "पाँच",
    6: "छह", 7: "सात", 8: "आठ", 9: "नौ", 10: "दस",
    11: "ग्यारह", 12: "बारह", 13: "तेरह", 14: "चौदह", 15: "पंद्रह",
    16: "सोलह", 17: "सत्रह", 18: "अठारह", 19: "उन्नीस", 20: "बीस",
    21: "इक्कीस", 22: "बाईस", 23: "तेईस", 24: "चौबीस", 25: "पच्चीस",
    26: "छब्बीस", 27: "सत्ताईस", 28: "अट्ठाईस", 29: "उनतीस", 30: "तीस",
    31: "इकतीस", 32: "बत्तीस", 33: "तैंतीस", 34: "चौंतीस", 35: "पैंतीस",
    36: "छत्तीस", 37: "सैंतीस", 38: "अड़तीस", 39: "उनतालीस", 40: "चालीस",
    41: "इकतालीस", 42: "बयालीस", 43: "तैंतालीस", 44: "चवालीस", 45: "पैंतालीस",
    46: "छियालीस", 47: "सैंतालीस", 48: "अड़तालीस", 49: "उनचास", 50: "पचास",
    51: "इक्यावन", 52: "बावन", 53: "तिरपन", 54: "चौवन", 55: "पचपन",
    56: "छप्पन", 57: "सत्तावन", 58: "अट्ठावन", 59: "उनसठ", 60: "साठ",
    61: "इकसठ", 62: "बासठ", 63: "तिरसठ", 64: "चौंसठ", 65: "पैंसठ",
    66: "छियासठ", 67: "सरसठ", 68: "अड़सठ", 69: "उनहत्तर", 70: "सत्तर",
    71: "इकहत्तर", 72: "बहत्तर", 73: "तिहत्तर", 74: "चौहत्तर", 75: "पचहत्तर",
    76: "छिहत्तर", 77: "सतहत्तर", 78: "अठहत्तर", 79: "उन्नासी", 80: "अस्सी",
    81: "इक्यासी", 82: "बयासी", 83: "तिरासी", 84: "चौरासी", 85: "पचासी",
    86: "छियासी", 87: "सत्तासी", 88: "अट््ठासी", 89: "नवासी", 90: "नब्बे",
    91: "इक्यानवे", 92: "बानवे", 93: "तिरानवे", 94: "चौरानवे", 95: "पचानवे",
    96: "छियानवे", 97: "संतानवे", 98: "अट्ठानवे", 99: "निन्यानवे", 100: "सौ"
}

def int_to_hindi_words(n: int) -> str:
    if n in HINDI_ONES:
        return HINDI_ONES[n]
    if n < 1000:
        h = n // 100
        rem = n % 100
        h_word = f"{HINDI_ONES.get(h, str(h))} सौ"
        return h_word if rem == 0 else f"{h_word} {int_to_hindi_words(rem)}"
    if n < 100000:
        k = n // 1000
        rem = n % 1000
        k_word = f"{HINDI_ONES.get(k, str(k))} हज़ार"
        return k_word if rem == 0 else f"{k_word} {int_to_hindi_words(rem)}"
    return str(n)


TELUGU_ONES = {
    0: "సున్నా", 1: "ఒకటి", 2: "రెండు", 3: "మూడు", 4: "నాలుగు", 5: "ఐదు",
    6: "ఆరు", 7: "ఏడు", 8: "ఎనిమిది", 9: "తొమ్మిది", 10: "పది",
    11: "పదకొండు", 12: "పన్నెండు", 13: "పదమూడు", 14: "పద్నాలుగు", 15: "పదిహేను",
    16: "పదహారు", 17: "పదిహేడు", 18: "పద్దెనిమిది", 19: "పంతొమ్మిది", 20: "ఇరవై",
    30: "ముప్పై", 40: "నలభై", 50: "యాభై", 60: "అరవై", 70: "డెబ్బై", 80: "ఎనభై", 90: "తొంభై",
    100: "వంద", 200: "రెండు వందలు", 300: "మూడు వందలు", 400: "నాలుగు వందలు", 500: "ఐదు వందలు",
    1000: "ఒక వెయ్యి"
}

def int_to_telugu_words(n: int) -> str:
    if n in TELUGU_ONES:
        return TELUGU_ONES[n]
    if n < 100:
        ten = (n // 10) * 10
        rem = n % 10
        return f"{TELUGU_ONES.get(ten, str(ten))} {TELUGU_ONES.get(rem, str(rem))}"
    if n < 1000:
        h = n // 100
        rem = n % 100
        h_word = f"{TELUGU_ONES.get(h, str(h))} వందల" if h > 1 else "వంద"
        return f"{h_word} {int_to_telugu_words(rem)}"
    if n < 100000:
        k = n // 1000
        rem = n % 1000
        k_word = "ఒక వెయ్యి" if k == 1 else f"{int_to_telugu_words(k)} వేల"
        return k_word if rem == 0 else f"{k_word} {int_to_telugu_words(rem)}"
    return str(n)


TAMIL_ONES = {
    0: "பூஜ்ஜியம்", 1: "ஒன்று", 2: "இரண்டு", 3: "மூன்று", 4: "நான்கு", 5: "ஐந்து",
    6: "ஆறு", 7: "ஏழு", 8: "எட்டு", 9: "ஒன்பது", 10: "பத்து",
    11: "பதினொன்று", 12: "பன்னிரண்டு", 13: "பதின்மூன்று", 14: "பதினான்கு", 15: "பதினைந்து",
    16: "பதினாறு", 17: "பதினேழு", 18: "பதினெட்டு", 19: "பத்தொன்பது", 20: "இருபது",
    30: "முப்பது", 40: "நாற்பது", 50: "ஐம்பது", 60: "அறுபது", 70: "எழுபது", 80: "எண்பது", 90: "தொண்ணூறு",
    100: "நூறு", 200: "இருநூறு", 300: "முந்நூறு", 400: "நாநூறு", 500: "ஐந்நூறு",
    1000: "ஆயிரம்"
}

def int_to_tamil_words(n: int) -> str:
    if n in TAMIL_ONES:
        return TAMIL_ONES[n]
    if n < 100:
        ten = (n // 10) * 10
        rem = n % 10
        return f"{TAMIL_ONES.get(ten, str(ten))} {TAMIL_ONES.get(rem, str(rem))}"
    if n < 1000:
        h = n // 100
        rem = n % 100
        h_word = TAMIL_ONES.get(h * 100, f"{TAMIL_ONES.get(h, str(h))} நூறு")
        return f"{h_word} {int_to_tamil_words(rem)}"
    if n < 100000:
        k = n // 1000
        rem = n % 1000
        k_word = "ஒரு ஆயிரம்" if k == 1 else f"{int_to_tamil_words(k)} ஆயிரம்"
        return k_word if rem == 0 else f"{k_word} {int_to_tamil_words(rem)}"
    return str(n)


def convert_indic_numbers(text: str, language_code: str = "en-IN") -> str:
    """Convert ASCII digits to natural spoken regional words in Indic languages."""
    if not text:
        return ""
    import re
    lang = (language_code or "en-IN").lower()
    t = text

    # Kannada
    if "kn" in lang or re.search(r'[\u0C80-\u0CFF]', t):
        t = re.sub(r'(\d{1,2}):00\s*(AM|PM|am|pm)', lambda m: f"{int_to_kannada_words(int(m.group(1)))} {m.group(2).upper()}", t)
        t = re.sub(r'(\d{1,2}):(\d{2})\s*(AM|PM|am|pm)', lambda m: f"{int_to_kannada_words(int(m.group(1)))} {int_to_kannada_words(int(m.group(2)))} {m.group(3).upper()}", t)
        t = re.sub(r'\b(\d+)\s*(?:st|nd|rd|th|ನೇ)\b', lambda m: KANNADA_ORDINALS.get(int(m.group(1)), f"{int_to_kannada_words(int(m.group(1)))}ನೇ") if int(m.group(1)) <= 10 else f"{int_to_kannada_words(int(m.group(1)))}ನೇ", t)
        t = re.sub(r'₹\s*(\d+)(?:\s*(?:/|ಪ್ರತಿ)?\s*(?:hr|hour|ಗಂಟೆ))?', 
                   lambda m: f"{int_to_kannada_words(int(m.group(1)))} ರೂಪಾಯಿ" + (" ಪ್ರತಿ ಗಂಟೆಗೆ" if "/hr" in m.group(0).lower() or "hr" in m.group(0).lower() or "hour" in m.group(0).lower() else ""), 
                   t, flags=re.IGNORECASE)
        t = re.sub(r'Rs\.?\s*(\d+)(?:\s*(?:/|ಪ್ರತಿ)?\s*(?:hr|hour|ಗಂಟೆ))?', 
                   lambda m: f"{int_to_kannada_words(int(m.group(1)))} ರೂಪಾಯಿ" + (" ಪ್ರತಿ ಗಂಟೆಗೆ" if "/hr" in m.group(0).lower() or "hr" in m.group(0).lower() or "hour" in m.group(0).lower() else ""), 
                   t, flags=re.IGNORECASE)
        t = re.sub(r'\b(\d+)\b', lambda m: int_to_kannada_words(int(m.group(1))) if int(m.group(1)) <= 99999 else m.group(1), t)

    # Hindi / Marathi
    elif "hi" in lang or "mr" in lang or re.search(r'[\u0900-\u097F]', t):
        t = re.sub(r'(\d{1,2}):00\s*(AM|PM|am|pm)', lambda m: f"{int_to_hindi_words(int(m.group(1)))} {m.group(2).upper()}", t)
        t = re.sub(r'(\d{1,2}):(\d{2})\s*(AM|PM|am|pm)', lambda m: f"{int_to_hindi_words(int(m.group(1)))} {int_to_hindi_words(int(m.group(2)))} {m.group(3).upper()}", t)
        t = re.sub(r'₹\s*(\d+)(?:\s*(?:/|प्रति)?\s*(?:hr|hour|घंटे|घंटा|तास))?', 
                   lambda m: f"{int_to_hindi_words(int(m.group(1)))} रुपये" + (" प्रति घंटे" if "/hr" in m.group(0).lower() or "hr" in m.group(0).lower() or "hour" in m.group(0).lower() else ""), 
                   t, flags=re.IGNORECASE)
        t = re.sub(r'Rs\.?\s*(\d+)(?:\s*(?:/|प्रति)?\s*(?:hr|hour|घंटे|घंटा|तास))?', 
                   lambda m: f"{int_to_hindi_words(int(m.group(1)))} रुपये" + (" प्रति घंटे" if "/hr" in m.group(0).lower() or "hr" in m.group(0).lower() or "hour" in m.group(0).lower() else ""), 
                   t, flags=re.IGNORECASE)
        t = re.sub(r'\b(\d+)\b', lambda m: int_to_hindi_words(int(m.group(1))) if int(m.group(1)) <= 99999 else m.group(1), t)

    # Telugu
    elif "te" in lang or re.search(r'[\u0C00-\u0C7F]', t):
        t = re.sub(r'(\d{1,2}):00\s*(AM|PM|am|pm)', lambda m: f"{int_to_telugu_words(int(m.group(1)))} {m.group(2).upper()}", t)
        t = re.sub(r'(\d{1,2}):(\d{2})\s*(AM|PM|am|pm)', lambda m: f"{int_to_telugu_words(int(m.group(1)))} {int_to_telugu_words(int(m.group(2)))} {m.group(3).upper()}", t)
        t = re.sub(r'₹\s*(\d+)(?:\s*(?:/|ಪ್ರತಿ)?\s*(?:hr|hour|గంట))?', 
                   lambda m: f"{int_to_telugu_words(int(m.group(1)))} రూపాయలు" + (" ప్రతి గంటకు" if "/hr" in m.group(0).lower() or "hr" in m.group(0).lower() or "hour" in m.group(0).lower() else ""), 
                   t, flags=re.IGNORECASE)
        t = re.sub(r'Rs\.?\s*(\d+)(?:\s*(?:/|ಪ್ರತಿ)?\s*(?:hr|hour|గంట))?', 
                   lambda m: f"{int_to_telugu_words(int(m.group(1)))} రూపాయలు" + (" ప్రతి గంటకు" if "/hr" in m.group(0).lower() or "hr" in m.group(0).lower() or "hour" in m.group(0).lower() else ""), 
                   t, flags=re.IGNORECASE)
        t = re.sub(r'\b(\d+)\b', lambda m: int_to_telugu_words(int(m.group(1))) if int(m.group(1)) <= 99999 else m.group(1), t)

    # Tamil
    elif "ta" in lang or re.search(r'[\u0B80-\u0BFF]', t):
        t = re.sub(r'(\d{1,2}):00\s*(AM|PM|am|pm)', lambda m: f"{int_to_tamil_words(int(m.group(1)))} {m.group(2).upper()}", t)
        t = re.sub(r'(\d{1,2}):(\d{2})\s*(AM|PM|am|pm)', lambda m: f"{int_to_tamil_words(int(m.group(1)))} {int_to_tamil_words(int(m.group(2)))} {m.group(3).upper()}", t)
        t = re.sub(r'₹\s*(\d+)(?:\s*(?:/|ஒரு)?\s*(?:hr|hour|மணி))?', 
                   lambda m: f"{int_to_tamil_words(int(m.group(1)))} ரூபாய்" + (" ஒரு மணி நேரத்திற்கு" if "/hr" in m.group(0).lower() or "hr" in m.group(0).lower() or "hour" in m.group(0).lower() else ""), 
                   t, flags=re.IGNORECASE)
        t = re.sub(r'Rs\.?\s*(\d+)(?:\s*(?:/|ஒரு)?\s*(?:hr|hour|மணி))?', 
                   lambda m: f"{int_to_tamil_words(int(m.group(1)))} ரூபாய்" + (" ஒரு மணி நேரத்திற்கு" if "/hr" in m.group(0).lower() or "hr" in m.group(0).lower() or "hour" in m.group(0).lower() else ""), 
                   t, flags=re.IGNORECASE)
        t = re.sub(r'\b(\d+)\b', lambda m: int_to_tamil_words(int(m.group(1))) if int(m.group(1)) <= 99999 else m.group(1), t)

    # Malayalam
    elif "ml" in lang or re.search(r'[\u0D00-\u0D7F]', t):
        t = re.sub(r'₹\s*(\d+)', r'\1 രൂപ', t)
        t = re.sub(r'Rs\.?\s*(\d+)', r'\1 രൂപ', t, flags=re.IGNORECASE)

    # Bengali
    elif "bn" in lang or re.search(r'[\u0980-\u09FF]', t):
        t = re.sub(r'₹\s*(\d+)', r'\1 টাকা', t)
        t = re.sub(r'Rs\.?\s*(\d+)', r'\1 টাকা', t, flags=re.IGNORECASE)

    # Gujarati
    elif "gu" in lang or re.search(r'[\u0A80-\u0AFF]', t):
        t = re.sub(r'₹\s*(\d+)', r'\1 રૂપિયા', t)
        t = re.sub(r'Rs\.?\s*(\d+)', r'\1 રૂપિયા', t, flags=re.IGNORECASE)

    # Punjabi
    elif "pa" in lang or re.search(r'[\u0A00-\u0A7F]', t):
        t = re.sub(r'₹\s*(\d+)', r'\1 ਰੁਪਏ', t)
        t = re.sub(r'Rs\.?\s*(\d+)', r'\1 ਰੁਪਏ', t, flags=re.IGNORECASE)

    # Odia
    elif "od" in lang or "or" in lang or re.search(r'[\u0B00-\u0B7F]', t):
        t = re.sub(r'₹\s*(\d+)', r'\1 ଟଙ୍କା', t)
        t = re.sub(r'Rs\.?\s*(\d+)', r'\1 ଟଙ୍କା', t, flags=re.IGNORECASE)

    else:
        # Default English
        t = re.sub(r'₹\s*(\d+)', r'\1 Rupees', t)
        t = re.sub(r'Rs\.?\s*(\d+)', r'\1 Rupees', t, flags=re.IGNORECASE)

    return t


def to_speech_text(text: str, language: str = "en-IN") -> str:
    """
    Convert Emora's full text response into a clean, voice-friendly version:
      - Converts numbers to spoken regional words in Indic languages (e.g. Kannada, Hindi, Telugu, Tamil)
      - Strips all emojis (astral & BMP)
      - Strips text emoticons (:), :-), :D, <3, etc.)
      - Strips roleplay actions (*smiles*, *sighs*, etc.)
      - Converts currency ₹ to regional currency word
      - Preserves English technical terms and names as is
      - Strips markdown formatting, symbols (#, *, _, ~, `, |, <, >, [, ], {, }, etc.)
      - Normalizes smart quotes and dashes
      - Normalizes whitespace and punctuation
    """
    import re

    if not text:
        return ""

    t = text

    # Auto-detect language script if default en-IN was supplied but Indic script is present
    target_lang = language or "en-IN"
    if target_lang == "en-IN":
        detected_lang, _ = detect_text_language(t)
        if detected_lang != "en-IN":
            target_lang = detected_lang

    # 1. Convert regional numbers & currency first
    t = convert_indic_numbers(t, target_lang)

    # 2. Markdown links: [label](url) -> label + ". " + _LINK_PHRASE
    t = re.sub(
        r'\[([^\]]+)\]\((https?://|[wW]{3}\.)[^\)]+\)',
        lambda m: m.group(1) + ". " + _LINK_PHRASE,
        t
    )

    # 3. Bare URLs (http://, https://, or www.)
    t = re.sub(r'(https?://\S+|[wW]{3}\.\S+)', _LINK_PHRASE, t)

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


DEFAULT_SARVAM_API_KEY = "sk_f9d5krj6_zkw9uIg9o4gUFIcy0yjkCM3B"

def get_sarvam_api_key() -> str:
    return os.getenv("SARVAM_API_KEY", "").strip() or SARVAM_API_KEY.strip() or DEFAULT_SARVAM_API_KEY


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
    if lang_code == "or-IN":
        lang_code = "od-IN"
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
