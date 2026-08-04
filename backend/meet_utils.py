import os
import uuid
from datetime import datetime, timedelta
from google.oauth2 import service_account
from googleapiclient.discovery import build

def create_google_meet_link(summary: str, start_time: datetime, duration_minutes: int) -> str:
    """Creates a calendar event with Google Meet link enabled.
    Falls back to a standard Jitsi room code if Google Calendar API is unavailable.
    """
    try:
        scopes = ['https://www.googleapis.com/auth/calendar']
        sa_file = os.path.abspath('backend/service-account.json')
        
        if not os.path.exists(sa_file):
            print("[Google Meet] Service account file not found. Falling back.")
            return f"jitsi_{uuid.uuid4().hex[:12]}"
            
        credentials = service_account.Credentials.from_service_account_file(sa_file, scopes=scopes)
        service = build('calendar', 'v3', credentials=credentials)
        
        end_time = start_time + timedelta(minutes=duration_minutes)
        event = {
            'summary': summary,
            'description': 'Consultation session on SolaceSquad',
            'start': {
                'dateTime': start_time.isoformat() + 'Z',
                'timeZone': 'UTC',
            },
            'end': {
                'dateTime': end_time.isoformat() + 'Z',
                'timeZone': 'UTC',
            },
            'conferenceData': {
                'createRequest': {
                    'requestId': f"ss-{uuid.uuid4().hex[:12]}",
                    'conferenceSolutionKey': {
                        'type': 'hangoutsMeet'
                    }
                }
            }
        }
        
        # Insert event into service account primary calendar
        event_result = service.events().insert(
            calendarId='primary', 
            body=event, 
            conferenceDataVersion=1
        ).execute()
        
        # Extract the video call link
        conf_data = event_result.get('conferenceData', {})
        entry_points = conf_data.get('entryPoints', [])
        for ep in entry_points:
            if ep.get('entryPointType') == 'video':
                meet_url = ep.get('uri')
                print(f"[Google Meet] Created link: {meet_url}")
                return meet_url
                
        return f"jitsi_{uuid.uuid4().hex[:12]}"
    except Exception as e:
        print(f"[Google Meet] Creation failed: {str(e)}. Using fallback room.")
        return f"jitsi_{uuid.uuid4().hex[:12]}"
