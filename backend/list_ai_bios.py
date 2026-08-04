from dotenv import load_dotenv; load_dotenv()
from database import SessionLocal
from models import ConsultantProfile, User

db = SessionLocal()
profiles = (
    db.query(ConsultantProfile)
    .filter(ConsultantProfile.cv_url.isnot(None))
    .filter(ConsultantProfile.cv_url != '')
    .filter(ConsultantProfile.bio.isnot(None))
    .filter(ConsultantProfile.bio != '')
    .all()
)
print(f"\nConsultants with AI bios: {len(profiles)}\n" + "="*60)
for i, p in enumerate(profiles, 1):
    user = db.query(User).filter(User.id == p.user_id).first()
    name  = p.full_name or (user.name if user else 'Unknown')
    email = user.email if user else 'N/A'
    bio   = (p.bio[:120] + "...") if p.bio and len(p.bio) > 120 else p.bio
    print(f"\n{i}. {name}")
    print(f"   Email : {email}")
    print(f"   Bio   : {bio}")
db.close()
print("\n" + "="*60)
