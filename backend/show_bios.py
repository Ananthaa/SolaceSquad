from dotenv import load_dotenv; load_dotenv()
from database import SessionLocal
from models import ConsultantProfile, User

db = SessionLocal()
profiles = db.query(ConsultantProfile).filter(
    ConsultantProfile.cv_url.isnot(None),
    ConsultantProfile.cv_url != ""
).all()
print(f"Consultants with CV: {len(profiles)}")
for p in profiles:
    u = db.query(User).filter(User.id == p.user_id).first()
    cv_url = p.cv_url or ""
    ext = cv_url.lower().split("?")[0].split(".")[-1]
    print("\n" + "="*60)
    print(f"Name   : {p.full_name or (u.name if u else '?')}")
    print(f"CV ext : {ext}")
    print(f"Bio    : {(p.bio or 'NONE')[:400]}")
db.close()
