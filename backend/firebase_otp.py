"""
Firebase OTP Authentication Integration
Provides phone number OTP verification using Firebase
FREE tier: 10,000 verifications/month
"""
import os
import secrets
import string
from datetime import datetime, timedelta
from typing import Optional, Dict
from sqlalchemy.orm import Session

try:
    import firebase_admin
    from firebase_admin import credentials, auth
    FIREBASE_AVAILABLE = True
except ImportError:
    FIREBASE_AVAILABLE = False
    print("[Firebase] Package not installed. Run: pip install firebase-admin")

class FirebaseOTP:
    def __init__(self):
        """
        Initialize Firebase Admin SDK
        Requires FIREBASE_CREDENTIALS_PATH environment variable
        """
        self.initialized = False
        self.use_firebase = False
        
        if not FIREBASE_AVAILABLE:
            print("[Firebase] firebase-admin not installed")
            print("[Firebase] Using fallback OTP system")
            return
        
        credentials_path = os.getenv("FIREBASE_CREDENTIALS_PATH")
        
        if credentials_path and os.path.exists(credentials_path):
            try:
                # Initialize Firebase Admin SDK
                cred = credentials.Certificate(credentials_path)
                firebase_admin.initialize_app(cred)
                self.initialized = True
                self.use_firebase = True
                print("[Firebase] Initialized successfully")
            except Exception as e:
                print(f"[Firebase] Initialization failed: {e}")
                print("[Firebase] Using fallback OTP system")
        else:
            print("[Firebase] Credentials not found. Set FIREBASE_CREDENTIALS_PATH")
            print("[Firebase] Using fallback OTP system")
    
    def verify_phone_token(self, id_token: str) -> Optional[Dict]:
        """
        Verify Firebase ID token from client
        Returns user info if valid, None otherwise
        """
        if not self.use_firebase:
            return None
            
        try:
            # Verify the ID token
            decoded_token = auth.verify_id_token(id_token)
            
            return {
                "uid": decoded_token.get("uid"),
                "phone_number": decoded_token.get("phone_number"),
                "email": decoded_token.get("email")
            }
        except Exception as e:
            print(f"[Firebase] Token verification failed: {e}")
            return None
    
    def get_user_by_phone(self, phone_number: str) -> Optional[Dict]:
        """
        Get Firebase user by phone number
        """
        if not self.use_firebase:
            return None
            
        try:
            user = auth.get_user_by_phone_number(phone_number)
            return {
                "uid": user.uid,
                "phone_number": user.phone_number,
                "email": user.email
            }
        except Exception as e:
            print(f"[Firebase] Get user failed: {e}")
            return None
    
    def is_available(self) -> bool:
        """Check if Firebase is available"""
        return self.use_firebase


class FallbackOTP:
    """
    Fallback OTP system for development/testing
    Stores OTPs in database temporarily
    NOT for production use - use Firebase instead!
    """
    
    def __init__(self):
        self.otp_storage = {}  # In-memory storage for dev
        print("[Fallback OTP] Using development OTP system")
        print("[Fallback OTP] WARNING: Not suitable for production!")
    
    def generate_otp(self, length: int = 6) -> str:
        """Generate a random OTP"""
        return ''.join(secrets.choice(string.digits) for _ in range(length))
    
    def send_otp(self, phone_number: str, db: Session = None) -> Dict:
        """
        Generate and 'send' OTP (actually just stores it)
        In production, this would use Firebase
        """
        # Generate OTP
        otp_code = self.generate_otp()
        
        # Store with expiry (5 minutes)
        expiry = datetime.now() + timedelta(minutes=5)
        
        self.otp_storage[phone_number] = {
            "code": otp_code,
            "expiry": expiry,
            "attempts": 0
        }
        
        # In development, print OTP to console
        print(f"[Fallback OTP] OTP for {phone_number}: {otp_code}")
        print(f"[Fallback OTP] Expires at: {expiry}")
        
        return {
            "success": True,
            "message": "OTP sent successfully (check console in dev mode)",
            "otp_for_testing": otp_code  # Only in dev!
        }
    
    def verify_otp(self, phone_number: str, otp_code: str) -> Dict:
        """
        Verify OTP code
        """
        if phone_number not in self.otp_storage:
            return {
                "success": False,
                "error": "No OTP found for this number"
            }
        
        stored = self.otp_storage[phone_number]
        
        # Check expiry
        if datetime.now() > stored["expiry"]:
            del self.otp_storage[phone_number]
            return {
                "success": False,
                "error": "OTP expired"
            }
        
        # Check attempts
        if stored["attempts"] >= 3:
            del self.otp_storage[phone_number]
            return {
                "success": False,
                "error": "Too many attempts"
            }
        
        # Verify code
        if stored["code"] == otp_code:
            del self.otp_storage[phone_number]
            return {
                "success": True,
                "message": "OTP verified successfully"
            }
        else:
            stored["attempts"] += 1
            return {
                "success": False,
                "error": "Invalid OTP"
            }


# Global instances
firebase_otp = FirebaseOTP()
fallback_otp = FallbackOTP()

# Use Firebase if available, otherwise fallback
otp_service = firebase_otp if firebase_otp.is_available() else fallback_otp
