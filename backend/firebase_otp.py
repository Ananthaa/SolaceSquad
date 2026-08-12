"""
Firebase OTP Authentication Integration
Provides phone number OTP verification using Firebase
FREE tier: 10,000 verifications/month
"""
import os
import secrets
import string
import requests
from datetime import datetime, timedelta
from typing import Optional, Dict
from sqlalchemy.orm import Session
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

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
        credentials_json = os.getenv("FIREBASE_CREDENTIALS_JSON")
        
        if credentials_path and os.path.exists(credentials_path):
            try:
                # Initialize Firebase Admin SDK from file
                cred = credentials.Certificate(credentials_path)
                firebase_admin.initialize_app(cred)
                self.initialized = True
                self.use_firebase = True
                print("[Firebase] Initialized successfully from file")
            except Exception as e:
                print(f"[Firebase] Initialization from file failed: {e}")
                print("[Firebase] Using fallback OTP system")
        elif credentials_json:
            try:
                # Initialize Firebase Admin SDK from JSON string
                import json
                cred_dict = json.loads(credentials_json)
                cred = credentials.Certificate(cred_dict)
                firebase_admin.initialize_app(cred)
                self.initialized = True
                self.use_firebase = True
                print("[Firebase] Initialized successfully from JSON env var")
            except Exception as e:
                print(f"[Firebase] Initialization from JSON failed: {e}")
                print("[Firebase] Using fallback OTP system")
        else:
            # Try to use Application Default Credentials (ADC)
            # This works automatically on Cloud Run if the service account has permission
            try:
                print("[Firebase] No explicit credentials. Attempting Application Default Credentials (ADC)...")
                firebase_admin.initialize_app()
                self.initialized = True
                self.use_firebase = True
                print("[Firebase] Initialized successfully using ADC")
            except Exception as e:
                print(f"[Firebase] ADC Initialization failed: {e}")
                print("[Firebase] Credentials not found. Set FIREBASE_CREDENTIALS_PATH or FIREBASE_CREDENTIALS_JSON")
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


class MSG91Provider:
    """
    MSG91 SMS provider for sending OTP via SMS
    Cost-effective solution for Indian phone numbers
    """
    
    def __init__(self):
        print("[MSG91] Starting initialization...")
        self.auth_key = os.getenv("MSG91_AUTH_KEY")
        # TXTIND is pre-approved for all MSG91 accounts
        self.sender_id = os.getenv("MSG91_SENDER_ID", "TXTIND")
        self.template_id = os.getenv("MSG91_TEMPLATE_ID")
        self.route = os.getenv("MSG91_ROUTE", "4")  # 4 = Transactional
        self.base_url = "https://api.msg91.com/api/v5"
        
        print(f"[MSG91] Auth key present: {bool(self.auth_key)}")
        if self.auth_key:
            print(f"[MSG91] Auth key length: {len(self.auth_key)}")
            print(f"[MSG91] Auth key starts with: {self.auth_key[:10]}...")
        
        if self.auth_key:
            print("[MSG91] ✅ Initialized successfully")
            print(f"[MSG91] Sender ID: {self.sender_id}")
            print(f"[MSG91] Template ID: {self.template_id if self.template_id else 'Not set (will use simple SMS)'}")
            print(f"[MSG91] Route: {self.route}")
            self.available = True
        else:
            print("[MSG91] ❌ Auth key not found. Set MSG91_AUTH_KEY environment variable")
            self.available = False
    
    def send_otp(self, phone_number: str, otp_code: str) -> Dict:
        """
        Send OTP via MSG91 SMS
        
        Args:
            phone_number: Phone number in international format (e.g., +919876543210)
            otp_code: The OTP code to send
            
        Returns:
            Dict with success status and message
        """
        if not self.available:
            print("[MSG91] ❌ Cannot send - MSG91 not available")
            return {
                "success": False,
                "message": "MSG91 not configured"
            }
        
        try:
            print(f"[MSG91] 📤 Attempting to send OTP to {phone_number}")
            
            # Clean phone number (remove + and spaces)
            clean_phone = phone_number.replace("+", "").replace(" ", "").replace("-", "")
            
            # Remove leading 0 if present (common input pattern)
            if clean_phone.startswith("0") and len(clean_phone) == 11:
                clean_phone = clean_phone[1:]
            
            # Add country code if not present (assuming India)
            if len(clean_phone) == 10:
                clean_phone = "91" + clean_phone
                print(f"[MSG91] Added country code: {clean_phone}")
            else:
                print(f"[MSG91] Cleaned phone number: {clean_phone}")
            
            # Use MSG91 OTP API (not SMS API!)
            # This is the correct endpoint for OTP delivery
            print("[MSG91] Using OTP API endpoint")
            url = f"{self.base_url}/otp"
            
            headers = {
                "authkey": self.auth_key,
                "content-type": "application/json"
            }
            
            payload = {
                "mobile": clean_phone,
                "otp": otp_code,
                "otp_expiry": "5"  # 5 minutes
            }
            
            # Add template_id if available
            if self.template_id:
                payload["template_id"] = self.template_id
                print(f"[MSG91] Using template ID: {self.template_id}")
            
            print(f"[MSG91] API URL: {url}")
            print(f"[MSG91] Payload: {payload}")
            
            # Send request
            print("[MSG91] Sending OTP API request...")
            response = requests.post(url, json=payload, headers=headers, timeout=10)
            print(f"[MSG91] Response status: {response.status_code}")
            print(f"[MSG91] Response body: {response.text}")
            
            if response.status_code == 200:
                try:
                    result = response.json()
                    print(f"[MSG91] ✅ OTP sent successfully to {phone_number}")
                    return {
                        "success": True,
                        "message": "OTP sent successfully",
                        "provider": "MSG91",
                        "request_id": result.get("request_id", result.get("type", ""))
                    }
                except Exception as e:
                    # Response might not be JSON
                    print(f"[MSG91] ✅ OTP sent (non-JSON response): {response.text}")
                    return {
                        "success": True,
                        "message": "OTP sent successfully",
                        "provider": "MSG91",
                        "request_id": response.text
                    }
            else:
                print(f"[MSG91] ❌ Failed to send OTP: {response.status_code} - {response.text}")
                return {
                    "success": False,
                    "message": f"Failed to send OTP: {response.text}"
                }
                
        except Exception as e:
            print(f"[MSG91] ❌ Error sending OTP: {e}")
            import traceback
            traceback.print_exc()
            return {
                "success": False,
                "message": f"Error: {str(e)}"
            }
    
    def is_available(self) -> bool:
        """Check if MSG91 is configured and available"""
        return self.available


class AWSSNSProvider:
    """
    AWS SNS SMS Provider for OTP delivery
    Uses boto3 to send SMS via AWS SNS
    """
    
    def __init__(self):
        print("[AWS SNS] Starting initialization...")
        self.access_key = os.getenv("AWS_ACCESS_KEY_ID")
        self.secret_key = os.getenv("AWS_SECRET_ACCESS_KEY")
        self.region = os.getenv("AWS_REGION", "us-east-1")
        
        print(f"[AWS SNS] Access key present: {bool(self.access_key)}")
        print(f"[AWS SNS] Region: {self.region}")
        
        if self.access_key and self.secret_key:
            try:
                import boto3
                self.sns_client = boto3.client(
                    'sns',
                    aws_access_key_id=self.access_key,
                    aws_secret_access_key=self.secret_key,
                    region_name=self.region
                )
                print("[AWS SNS] ✅ Initialized successfully")
                self.available = True
            except ImportError:
                print("[AWS SNS] ❌ boto3 not installed. Run: pip install boto3")
                self.available = False
            except Exception as e:
                print(f"[AWS SNS] ❌ Initialization failed: {e}")
                self.available = False
        else:
            print("[AWS SNS] ❌ Credentials not found. Set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY")
            self.available = False
    
    def send_otp(self, phone_number: str, otp_code: str) -> Dict:
        """
        Send OTP via AWS SNS
        
        Args:
            phone_number: Phone number in international format (e.g., +919876543210)
            otp_code: The OTP code to send
            
        Returns:
            Dict with success status and message
        """
        if not self.available:
            print("[AWS SNS] ❌ Cannot send - AWS SNS not available")
            return {
                "success": False,
                "message": "AWS SNS not configured"
            }
        
        try:
            print(f"[AWS SNS] 📤 Attempting to send OTP to {phone_number}")
            
            # Clean phone number (ensure it has + prefix)
            clean_phone = phone_number.replace(" ", "").replace("-", "")
            
            # Extract digits only to check length
            digits_only = clean_phone.replace("+", "")
            if digits_only.startswith("0") and len(digits_only) == 11:
                digits_only = digits_only[1:]
                
            if len(digits_only) == 10:
                clean_phone = "+91" + digits_only
            else:
                if not clean_phone.startswith("+"):
                    clean_phone = "+" + clean_phone
            
            print(f"[AWS SNS] Formatted phone: {clean_phone}")
            
            # Prepare message
            message = f"Your SolaceSquad verification code is {otp_code}. Valid for 5 minutes. Do not share this code with anyone."
            
            # Send SMS via SNS
            print("[AWS SNS] Sending SMS...")
            response = self.sns_client.publish(
                PhoneNumber=clean_phone,
                Message=message,
                MessageAttributes={
                    'AWS.SNS.SMS.SMSType': {
                        'DataType': 'String',
                        'StringValue': 'Transactional'
                    }
                }
            )
            
            message_id = response.get('MessageId', '')
            print(f"[AWS SNS] Response: {response}")
            print(f"[AWS SNS] ✅ OTP sent successfully to {phone_number}")
            print(f"[AWS SNS] Message ID: {message_id}")
            
            return {
                "success": True,
                "message": "OTP sent successfully",
                "provider": "AWS SNS",
                "message_id": message_id
            }
            
        except Exception as e:
            print(f"[AWS SNS] ❌ Error sending OTP: {e}")
            import traceback
            traceback.print_exc()
            return {
                "success": False,
                "message": f"Error: {str(e)}"
            }
    
    def is_available(self) -> bool:
        """Check if AWS SNS is configured and available"""
        return self.available


class EmailOTPProvider:
    """
    Email OTP Provider
    Sends OTP codes via email using SMTP (Gmail)
    """
    
    def __init__(self):
        print("[Email OTP] Starting initialization...")
        self.smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
        self.smtp_port = int(os.getenv("SMTP_PORT", "587"))
        self.smtp_username = os.getenv("SMTP_USERNAME")
        self.smtp_password = os.getenv("SMTP_PASSWORD")
        self.from_email = os.getenv("SMTP_FROM_EMAIL", self.smtp_username)
        self.from_name = os.getenv("SMTP_FROM_NAME", "SolaceSquad")
        
        print(f"[Email OTP] SMTP Server: {self.smtp_server}:{self.smtp_port}")
        print(f"[Email OTP] Username present: {bool(self.smtp_username)}")
        print(f"[Email OTP] From: {self.from_name} <{self.from_email}>")
        
        if self.smtp_username and self.smtp_password:
            print("[Email OTP] ✅ Initialized successfully")
            self.available = True
        else:
            print("[Email OTP] ❌ Credentials not found. Set SMTP_USERNAME and SMTP_PASSWORD")
            self.available = False
    
    def send_otp(self, email: str, otp_code: str) -> Dict:
        """
        Send OTP via email
        
        Args:
            email: Email address to send OTP to
            otp_code: The OTP code to send
            
        Returns:
            Dict with success status and message
        """
        if not self.available:
            print("[Email OTP] ❌ Cannot send - Email OTP not configured")
            return {
                "success": False,
                "message": "Email OTP not configured"
            }
        
        try:
            print(f"[Email OTP] 📧 Attempting to send OTP to {email}")
            
            # Create message
            msg = MIMEMultipart('alternative')
            msg['Subject'] = f"Your SolaceSquad Verification Code: {otp_code}"
            msg['From'] = f"{self.from_name} <{self.from_email}>"
            msg['To'] = email
            
            # Create HTML and plain text versions
            text_content = f"""
Your SolaceSquad Verification Code

Your verification code is: {otp_code}

This code will expire in 5 minutes.

If you didn't request this code, please ignore this email.

---
SolaceSquad - Your Mental Health Companion
            """
            
            html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; text-align: center; border-radius: 10px 10px 0 0; }}
        .content {{ background: #f9f9f9; padding: 30px; border-radius: 0 0 10px 10px; }}
        .otp-box {{ background: white; border: 2px dashed #667eea; padding: 20px; text-align: center; margin: 20px 0; border-radius: 10px; }}
        .otp-code {{ font-size: 32px; font-weight: bold; color: #667eea; letter-spacing: 8px; font-family: 'Courier New', monospace; }}
        .footer {{ text-align: center; margin-top: 20px; color: #666; font-size: 12px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🔐 Verification Code</h1>
            <p>SolaceSquad</p>
        </div>
        <div class="content">
            <p>Hello!</p>
            <p>Your verification code is:</p>
            <div class="otp-box">
                <div class="otp-code">{otp_code}</div>
            </div>
            <p><strong>This code will expire in 5 minutes.</strong></p>
            <p>If you didn't request this code, please ignore this email.</p>
            <div class="footer">
                <p>SolaceSquad - Your Mental Health Companion</p>
                <p>This is an automated message, please do not reply.</p>
            </div>
        </div>
    </div>
</body>
</html>
            """
            
            # Attach both versions
            part1 = MIMEText(text_content, 'plain')
            part2 = MIMEText(html_content, 'html')
            msg.attach(part1)
            msg.attach(part2)
            
            # Send email
            print("[Email OTP] Connecting to SMTP server...")
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                print("[Email OTP] Logging in...")
                server.login(self.smtp_username, self.smtp_password)
                print("[Email OTP] Sending email...")
                server.send_message(msg)
            
            print(f"[Email OTP] ✅ OTP sent successfully to {email}")
            
            return {
                "success": True,
                "message": "OTP sent to your email",
                "provider": "Email",
                "email": email
            }
            
        except Exception as e:
            print(f"[Email OTP] ❌ Error sending OTP: {e}")
            import traceback
            traceback.print_exc()
            return {
                "success": False,
                "message": f"Error: {str(e)}"
            }
    
    def is_available(self) -> bool:
        """Check if Email OTP is configured and available"""
        return self.available


class FallbackOTP:
    """
    Fallback OTP system for development/testing
    Stores OTPs in database temporarily
    NOT for production use - use Firebase instead!
    """
    
    def __init__(self):
        self.otp_storage = {}  # In-memory storage for dev
        
        # Initialize email OTP provider
        self.email_otp = EmailOTPProvider()
        
        # Try to initialize AWS SNS first (preferred for SMS)
        self.aws_sns = AWSSNSProvider()
        
        # Then try MSG91 as backup for SMS
        self.msg91 = MSG91Provider()
        
        if self.email_otp.is_available():
            print("[OTP] Using Email for OTP delivery")
        if self.aws_sns.is_available():
            print("[OTP] Using AWS SNS for SMS delivery")
        elif self.msg91.is_available():
            print("[OTP] Using MSG91 for SMS delivery")
        
        if not self.email_otp.is_available() and not self.aws_sns.is_available() and not self.msg91.is_available():
            print("[Fallback OTP] Using development OTP system")
            print("[Fallback OTP] WARNING: Not suitable for production!")
    
    def generate_otp(self, length: int = 6) -> str:
        """Generate a random OTP"""
        return ''.join(secrets.choice(string.digits) for _ in range(length))
    
    def send_otp(self, phone_number: str, otp_code: str, email: str = None) -> Dict:
        """
        Send OTP via available providers
        Sends to BOTH email and phone if both are provided
        
        Args:
            phone_number: Phone number to send OTP to
            otp_code: The OTP code to send
            email: Optional email address to send OTP to
            
        Returns:
            Dict with success status and message
        """
        results = []
        email_sent = False
        sms_sent = False
        
        # Try to send via email first if provided
        if email and self.email_otp.is_available():
            print(f"[OTP] Sending OTP to email: {email}")
            email_result = self.email_otp.send_otp(email, otp_code)
            if email_result.get("success"):
                email_sent = True
                results.append("email")
                print(f"[OTP] ✅ Email OTP sent successfully")
            else:
                print(f"[OTP] ❌ Email OTP failed: {email_result.get('message')}")
        
        # Try to send via SMS (AWS SNS first, then MSG91)
        if phone_number:
            # Try AWS SNS first
            if self.aws_sns.is_available():
                sms_result = self.aws_sns.send_otp(phone_number, otp_code)
                if sms_result.get("success"):
                    sms_sent = True
                    results.append("SMS (AWS SNS)")
                    print(f"[OTP] ✅ SMS OTP sent via AWS SNS")
                else:
                    print(f"[OTP] AWS SNS failed: {sms_result.get('message')}")
                    print("[OTP] Falling back to MSG91...")
            
            # Try MSG91 as backup
            if not sms_sent and self.msg91.is_available():
                sms_result = self.msg91.send_otp(phone_number, otp_code)
                if sms_result.get("success"):
                    sms_sent = True
                    results.append("SMS (MSG91)")
                    print(f"[OTP] ✅ SMS OTP sent via MSG91")
                else:
                    print(f"[OTP] MSG91 failed: {sms_result.get('message')}")
        
        # If at least one method succeeded
        if email_sent or sms_sent:
            providers = " and ".join(results)
            return {
                "success": True,
                "message": f"OTP sent via {providers}",
                "providers": results,
                "email_sent": email_sent,
                "sms_sent": sms_sent
            }
        
        # Fallback to console logging (dev mode)
        print("\n" + "="*60)
        print(f"🔐 OTP for {phone_number}: {otp_code}")
        if email:
            print(f"   Email: {email}")
        print(f"   Expires: {(datetime.utcnow() + timedelta(minutes=10)).strftime('%H:%M:%S')}")
        print("="*60 + "\n")
        
        return {
            "success": True,
            "message": "OTP printed to console (dev mode)",
            "provider": "Console",
            "otp_debug": otp_code
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
otp_service = fallback_otp
