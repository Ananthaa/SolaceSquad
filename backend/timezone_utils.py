from datetime import datetime, timedelta, timezone
import zoneinfo

def get_now_local(tz_name: str = "UTC") -> datetime:
    """Get current time in a specific timezone."""
    try:
        tz = zoneinfo.ZoneInfo(tz_name)
    except Exception:
        tz = zoneinfo.ZoneInfo("UTC")
    
    return datetime.now(tz)

def get_today_local(tz_name: str = "UTC"):
    """Get current date in a specific timezone."""
    return get_now_local(tz_name).date()

def to_local(utc_dt: datetime, tz_name: str = "UTC") -> datetime:
    """
    Convert a UTC datetime to a local timezone.
    If naive, assumes it is UTC.
    """
    if not utc_dt:
        return None
    
    # If it's a string, try to parse it
    if isinstance(utc_dt, str):
        try:
            # Handle 'Z' suffix and other common ISO formats
            if utc_dt.endswith('Z'):
                utc_dt = utc_dt.replace('Z', '+00:00')
            utc_dt = datetime.fromisoformat(utc_dt)
        except Exception:
            return utc_dt
            
    # If it's a date object but not datetime, just return it
    if not isinstance(utc_dt, datetime):
        return utc_dt

    try:
        tz = zoneinfo.ZoneInfo(tz_name)
    except Exception:
        tz = zoneinfo.ZoneInfo("UTC")

    if utc_dt.tzinfo is None:
        # Naive datetime - treat as UTC
        utc_dt = utc_dt.replace(tzinfo=zoneinfo.ZoneInfo("UTC"))
    
    # Convert to target timezone
    return utc_dt.astimezone(tz)

def format_dt_local(utc_dt: datetime, p1: str = None, p2: str = None) -> str:
    """
    Convert UTC datetime to local and format as string.
    Automatically detects the order of timezone name and format string.
    """
    if not utc_dt:
        return "—"
        
    tz_name = "UTC"
    format_str = "%d %b %Y, %H:%M"
    
    # Smart detection of parameters
    for p in (p1, p2):
        if p is not None:
            if "%" in p:
                format_str = p
            else:
                tz_name = p
                
    local_dt = to_local(utc_dt, tz_name)
    if not local_dt:
        return "—"
    return local_dt.strftime(format_str)

def get_greeting(hour: int) -> str:
    """Return greeting based on hour (0-23)."""
    if hour < 12:
        return "Good morning"
    elif hour < 17:
        return "Good afternoon"
    else:
        return "Good evening"
def parse_local_to_utc(dt_naive: datetime, tz_name: str = "UTC") -> datetime:
    """
    Take a naive datetime (from a picker), treat it as being in tz_name, 
    and return a naive UTC datetime for DB storage.
    """
    try:
        tz = zoneinfo.ZoneInfo(tz_name)
    except Exception:
        tz = zoneinfo.ZoneInfo("UTC")
    
    # Attach local timezone info
    local_dt = dt_naive.replace(tzinfo=tz)
    # Convert to UTC
    utc_dt = local_dt.astimezone(zoneinfo.ZoneInfo("UTC"))
    # Return as naive for SQL Alchemy compatibility
    return utc_dt.replace(tzinfo=None)
