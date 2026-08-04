"""
batch_generate_bios.py
======================
Generates a Gemini professional summary for every ConsultantProfile that
has a cv_url set and saves to the DB.
Also handles image-only / scanned PDFs gracefully — still generates from
profile fields even if CV text isn't extractable.

Run from the backend directory:
    cd backend
    python batch_generate_bios.py
"""

import io
import json
import os
import time

from dotenv import load_dotenv
load_dotenv()

from database import SessionLocal
from models import ConsultantProfile

import requests
import google.generativeai as genai

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model = genai.GenerativeModel("gemini-2.0-flash-exp")


def extract_cv_text(cv_url: str) -> str:
    """Download the CV PDF and extract plain text (best-effort)."""
    try:
        import PyPDF2
        print(f"    📥 Downloading CV: {cv_url[:80]}...")
        resp = requests.get(cv_url, timeout=15)
        print(f"    📥 HTTP {resp.status_code} — {len(resp.content)} bytes")
        if resp.status_code == 200 and len(resp.content) > 0:
            reader = PyPDF2.PdfReader(io.BytesIO(resp.content))
            print(f"    📄 PDF has {len(reader.pages)} page(s)")
            pages = []
            for i, page in enumerate(reader.pages[:4]):
                text = page.extract_text() or ""
                print(f"       page {i+1}: {len(text)} chars extracted")
                pages.append(text)
            combined = "\n".join(pages)[:2000]
            return combined
        else:
            print(f"    ⚠️  Empty or failed download (status={resp.status_code})")
    except Exception as e:
        print(f"    ⚠️  CV read error: {e}")
    return ""


def safe_list(field) -> str:
    if not field:
        return ""
    try:
        items = json.loads(field)
        return ", ".join(items) if isinstance(items, list) else str(field)
    except Exception:
        return str(field)


def build_prompt(profile, cv_text: str) -> str:
    return f"""Write a crisp, professional third-person bio for a wellness consultant profile.
Maximum 150 words. Tone: warm, credible, and authoritative. No bullet points — flowing prose only.
Do not invent facts not present in the data below.

Name: {profile.full_name or 'the consultant'}
Specialization: {profile.specialization or ''}
Clinical experience: {profile.clinical_experience or ''} ({profile.experience_years or 0} years)
Highest qualification: {profile.highest_qualification or ''} — Education: {profile.education or ''}
Expertise areas: {safe_list(profile.expertise_areas)}
Therapeutic approaches: {safe_list(profile.counselling_methods)}
Serves: {profile.target_audience or ''}
Languages: {safe_list(profile.languages)}
Delivery: {profile.delivery_methods or ''}
Location: {profile.city or ''}
QACP Certified: {'Yes' if profile.qacp_certified else 'No'}
CV extract: {cv_text if cv_text else '(CV text not extractable — image-based PDF)'}"""


def generate_bio(prompt: str) -> str | None:
    try:
        result = model.generate_content(
            prompt,
            generation_config={"max_output_tokens": 300, "temperature": 0.4}
        )
        return result.text.strip()
    except Exception as e:
        print(f"    ⚠️  Gemini error: {e}")
        return None


def main():
    db = SessionLocal()
    try:
        profiles = (
            db.query(ConsultantProfile)
            .filter(ConsultantProfile.cv_url.isnot(None))
            .filter(ConsultantProfile.cv_url != "")
            .all()
        )

        print(f"\n🔍 Found {len(profiles)} consultant(s) with CVs uploaded.\n")

        updated = 0
        failed  = 0

        for p in profiles:
            name = p.full_name or f"Profile-ID={p.id}"
            print(f"\n  → {name}")

            cv_text = extract_cv_text(p.cv_url)
            if not cv_text:
                print(f"    ℹ️  No CV text extracted — generating from profile data only.")

            prompt = build_prompt(p, cv_text)
            bio = generate_bio(prompt)

            if bio:
                p.bio = bio
                db.commit()
                print(f"    ✅ Bio saved ({len(bio)} chars):\n       {bio[:120]}...")
                updated += 1
            else:
                print(f"    ❌ Bio generation failed")
                failed += 1

            time.sleep(1)

        print(f"\n{'='*50}")
        print(f"✅ Updated : {updated}")
        print(f"❌ Failed  : {failed}")
        print(f"{'='*50}\n")

    finally:
        db.close()


if __name__ == "__main__":
    main()
