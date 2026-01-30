from sqlalchemy.orm import Session
from models import AuditLog
from fastapi import Request
import datetime

class AuditLogger:
    """
    Helper class to create audit logs for HIPAA compliance.
    Logs who did what, when, and from where (IP).
    """
    
    @staticmethod
    def log_event(
        db: Session, 
        event_type: str, 
        user_id: int = None, 
        resource_type: str = None, 
        resource_id: str = None, 
        details: str = None,
        status: str = "success", 
        ip_address: str = None,
        request: Request = None
    ):
        """
        Create a new audit log entry.
        
        Args:
            db: Database session
            event_type: Type of event (e.g., "login", "view_record", "create_appointment")
            user_id: ID of the user performing the action (optional for anon events like failed login)
            resource_type: Type of resource accessed (e.g., "vitals", "user_profile")
            resource_id: ID of the specific resource (e.g., vitals_record_id)
            details: Human-readable details
            status: "success" or "failure"
            ip_address: IP address of the client
            request: FastAPI request object (to auto-extract IP if not provided)
        """
        try:
            # Extract IP from request if not explicitly provided
            if not ip_address and request:
                ip_address = request.client.host
            
            # Create log entry
            log_entry = AuditLog(
                user_id=user_id,
                event_type=event_type,
                resource_type=resource_type,
                resource_id=resource_id,
                details=details,
                ip_address=ip_address,
                status=status,
                timestamp=datetime.datetime.utcnow()
            )
            
            db.add(log_entry)
            db.commit()
            
            # Also print to console for development visibility (but structured logging is better for prod)
            print(f"[AUDIT] {event_type} | User: {user_id} | Status: {status} | IP: {ip_address}")
            
        except Exception as e:
            # Fallback logging if DB write fails - CRITICAL for audit systems
            print(f"CRITICAL: Failed to write audit log! {str(e)}")
            # In a real production system, this should alert the admin immediately
