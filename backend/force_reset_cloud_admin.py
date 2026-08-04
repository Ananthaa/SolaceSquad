
import os
from dotenv import load_dotenv
# Load env variables FIRST to ensure we connect to Cloud SQL
load_dotenv()

from database import get_db_session
from models import User
import bcrypt


def force_reset_admin():
    print("Connecting to database...")
    with get_db_session() as db:
        email = "admin@solacesquad.com"
        new_password = "adminpassword123"

        try:
            user = db.query(User).filter(User.email == email).first()

            if not user:
                print(f"User {email} not found! Creating it now...")
                password_bytes = new_password.encode('utf-8')[:72]
                salt = bcrypt.gensalt()
                hashed = bcrypt.hashpw(password_bytes, salt).decode('utf-8')

                user = User(
                    email=email,
                    name="Super Admin",
                    password_hash=hashed,
                    user_type="admin",
                    is_active=True
                )
                db.add(user)
            else:
                print(f"User {email} found.")
                print(f"Resetting password to: {new_password}")
                password_bytes = new_password.encode('utf-8')[:72]
                salt = bcrypt.gensalt()
                hashed = bcrypt.hashpw(password_bytes, salt).decode('utf-8')
                user.password_hash = hashed
                user.user_type = "admin"

            db.commit()
            print("[OK] Password reset successfully committed to Cloud SQL.")

        except Exception as e:
            print(f"[ERROR] Error: {e}")

if __name__ == "__main__":
    force_reset_admin()
