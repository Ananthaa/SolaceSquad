import os
import json
import firebase_admin
from firebase_admin import messaging, credentials
from sqlalchemy.orm import Session
from models import UserDeviceToken

def initialize_firebase():
    """Safely initialize Firebase Admin SDK if not already done"""
    if not firebase_admin._apps:
        credentials_path = os.getenv("FIREBASE_CREDENTIALS_PATH")
        credentials_json = os.getenv("FIREBASE_CREDENTIALS_JSON")
        if credentials_path and os.path.exists(credentials_path):
            try:
                cred = credentials.Certificate(credentials_path)
                firebase_admin.initialize_app(cred)
                print("[Firebase Push] Initialized from credentials path")
            except Exception as e:
                print(f"[Firebase Push] Failed to initialize from path: {e}")
                firebase_admin.initialize_app()
        elif credentials_json:
            try:
                cred_dict = json.loads(credentials_json)
                cred = credentials.Certificate(cred_dict)
                firebase_admin.initialize_app(cred)
                print("[Firebase Push] Initialized from credentials JSON env")
            except Exception as e:
                print(f"[Firebase Push] Failed to initialize from JSON: {e}")
                firebase_admin.initialize_app()
        else:
            try:
                firebase_admin.initialize_app()
                print("[Firebase Push] Initialized using default credentials (ADC)")
            except Exception as e:
                print(f"[Firebase Push] Failed to initialize using default credentials: {e}")
                raise e

def send_push_notification(db: Session, user_id: int, title: str, body: str, path: str = ""):
    """Send push notifications to all registered devices of a user via FCM"""
    try:
        initialize_firebase()
    except Exception as e:
        print(f"[Push] Firebase initialization failed: {e}")
        return False

    # Get tokens
    tokens = db.query(UserDeviceToken).filter(UserDeviceToken.user_id == user_id).all()
    if not tokens:
        print(f"[Push] No registered FCM tokens for user_id={user_id}")
        return False

    success = False
    for t in tokens:
        try:
            # Construct message for FCM v1 API
            message = messaging.Message(
                notification=messaging.Notification(
                    title=title,
                    body=body
                ),
                data={
                    "title": title,
                    "body": body,
                    "path": path,
                    "click_action": path
                },
                token=t.fcm_token
            )
            # Send message
            response = messaging.send(message)
            print(f"[Push] Push sent successfully to user_id={user_id}, token_id={t.id}. Response: {response}")
            success = True
        except Exception as e:
            print(f"[Push] Failed to send push to token_id={t.id}: {e}")
            # If the token is invalid or unregistered, clean it up from the database
            err_str = str(e).lower()
            if "not-found" in err_str or "unregistered" in err_str or "invalid-argument" in err_str or "requested entity was not found" in err_str:
                try:
                    db.delete(t)
                    db.commit()
                    print(f"[Push] Deleted stale FCM token_id={t.id}")
                except Exception as db_err:
                    db.rollback()
                    print(f"[Push] Failed to delete stale token: {db_err}")
    return success

def send_broadcast_push(db: Session, title: str, body: str, path: str = ""):
    """Send push notifications to all registered devices in the database (Broadcast/Offers)"""
    try:
        initialize_firebase()
    except Exception as e:
        print(f"[Push] Firebase initialization failed: {e}")
        return False

    tokens = db.query(UserDeviceToken).all()
    if not tokens:
        print("[Push] No registered FCM tokens found for broadcast")
        return False

    print(f"[Push] Starting broadcast of '{title}' to {len(tokens)} tokens...")
    success_count = 0
    for t in tokens:
        try:
            message = messaging.Message(
                notification=messaging.Notification(
                    title=title,
                    body=body
                ),
                data={
                    "title": title,
                    "body": body,
                    "path": path,
                    "click_action": path
                },
                token=t.fcm_token
            )
            messaging.send(message)
            success_count += 1
        except Exception as e:
            print(f"[Push] Broadcast failed to token_id={t.id}: {e}")
            err_str = str(e).lower()
            if "not-found" in err_str or "unregistered" in err_str or "invalid-argument" in err_str or "requested entity was not found" in err_str:
                try:
                    db.delete(t)
                    db.commit()
                except Exception:
                    db.rollback()
    print(f"[Push] Broadcast finished. Successful deliveries: {success_count}/{len(tokens)}")
    return success_count > 0
