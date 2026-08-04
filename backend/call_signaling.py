"""
WebRTC Signaling Server using Socket.IO
Handles real-time communication for voice calling
"""

import socketio
from datetime import datetime
import uuid
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def log_call_activity(user_id: int, room_id: str, event_type: str, details: str):
    try:
        from database import get_db_session
        from audit_logging import AuditLogger
        
        with get_db_session() as db:
            from models import CallSession
            session = db.query(CallSession).filter(CallSession.room_id == room_id).first()
            appointment_id = None
            if session:
                appointment_id = session.appointment_id
                
            AuditLogger.log_event(
                db=db,
                user_id=user_id,
                event_type=event_type,
                resource_type="appointment",
                resource_id=str(appointment_id) if appointment_id else room_id,
                details=details
            )
    except Exception as e:
        logger.error(f"Failed to log call activity to DB: {e}")

# Create Socket.IO server
sio = socketio.AsyncServer(
    async_mode='asgi',
    cors_allowed_origins='*',  # Allow all origins — CORS restricted at the nginx/CDN layer
    ping_timeout=60,      # disconnect dead socket after 60s no response
    ping_interval=25,     # send keepalive ping every 25s (well under Cloud Run 3600s timeout)
    logger=False,         # reduce log noise in production
    engineio_logger=False
)

# Store active rooms and participants
active_rooms = {}
# Format: {room_id: {'user': sid, 'consultant': sid, 'created_at': datetime}}

@sio.event
async def connect(sid, environ):
    """Handle client connection"""
    logger.info(f"Client connected: {sid}")
    await sio.emit('connected', {'sid': sid}, room=sid)

@sio.event
async def disconnect(sid):
    """Handle client disconnection"""
    logger.info(f"Client disconnected: {sid}")
    
    # Remove from any active rooms
    for room_id, participants in list(active_rooms.items()):
        if sid in participants.values():
            user_type = 'user' if participants.get('user') == sid else 'consultant'
            user_id = participants.get(f'{user_type}_id')
            user_name = participants.get(f'{user_type}_name', 'Unknown')
            
            log_call_activity(
                user_id=user_id,
                room_id=room_id,
                event_type="appointment_call_disconnect",
                details=f"{user_type.capitalize()} '{user_name}' disconnected from call room."
            )

            # Notify other participant
            for role, participant_sid in list(participants.items()):
                if participant_sid != sid and role in ['user', 'consultant']:
                    await sio.emit('peer_disconnected', {
                        'message': 'Other participant disconnected'
                    }, room=participant_sid)
            
            # Clean up only this participant
            if participants.get('user') == sid:
                participants.pop('user', None)
                participants.pop('user_name', None)
                participants.pop('user_id', None)
            if participants.get('consultant') == sid:
                participants.pop('consultant', None)
                participants.pop('consultant_name', None)
                participants.pop('consultant_id', None)
            
            # Delete room if no participants are left
            if 'user' not in participants and 'consultant' not in participants:
                del active_rooms[room_id]
                logger.info(f"Room {room_id} cleaned up")

@sio.event
async def join_call(sid, data):
    """
    Join a call room
    data: {
        'room_id': str,
        'user_type': 'user' or 'consultant',
        'user_name': str,
        'user_id': int
    }
    """
    try:
        room_id = data.get('room_id')
        user_type = data.get('user_type')  # 'user' or 'consultant'
        user_name = data.get('user_name', 'Unknown')
        user_id = data.get('user_id')
        
        logger.info(f"Join call request: {sid} -> {room_id} as {user_type} (user_id: {user_id})")
        
        # Create room if it doesn't exist
        if room_id not in active_rooms:
            active_rooms[room_id] = {
                'created_at': datetime.now(),
                'recording_active': False  # Track recording state
            }
        
        # Add participant to room
        active_rooms[room_id][user_type] = sid
        active_rooms[room_id][f'{user_type}_name'] = user_name
        if user_id:
            active_rooms[room_id][f'{user_type}_id'] = int(user_id)
        
        # Log join activity to AuditLog
        log_call_activity(
            user_id=int(user_id) if user_id else None,
            room_id=room_id,
            event_type="appointment_call_join",
            details=f"{user_type.capitalize()} '{user_name}' joined call room."
        )

        # Join Socket.IO room
        await sio.enter_room(sid, room_id)
        
        # Notify this client
        await sio.emit('room_joined', {
            'room_id': room_id,
            'user_type': user_type,
            'message': f'Joined room as {user_type}',
            'recording': active_rooms[room_id].get('recording_active', False)
        }, room=sid)
        
        # Check if both participants are present
        if 'user' in active_rooms[room_id] and 'consultant' in active_rooms[room_id]:
            # Notify both that peer is ready
            user_sid = active_rooms[room_id]['user']
            consultant_sid = active_rooms[room_id]['consultant']
            
            await sio.emit('peer_joined', {
                'peer_type': 'consultant',
                'peer_name': active_rooms[room_id].get('consultant_name', 'Consultant'),
                'message': 'Consultant joined'
            }, room=user_sid)
            
            await sio.emit('peer_joined', {
                'peer_type': 'user',
                'peer_name': active_rooms[room_id].get('user_name', 'User'),
                'message': 'User joined'
            }, room=consultant_sid)
            
            logger.info(f"Both participants in room {room_id}")
            
            # If recording is active, ensure late joiner knows (handled by room_joined recording flag, but let's be explicit)
            if active_rooms[room_id].get('recording_active'):
                 await sio.emit('recording_started', {'status': 'active'}, room=room_id)
        
    except Exception as e:
        logger.error(f"Error in join_call: {e}")
        await sio.emit('error', {'message': str(e)}, room=sid)

@sio.event
async def start_recording(sid, data):
    """
    Signal that call recording has started
    """
    try:
        room_id = data.get('room_id')
        if room_id and room_id in active_rooms:
            active_rooms[room_id]['recording_active'] = True
            
            room = active_rooms[room_id]
            user_type = 'user' if room.get('user') == sid else 'consultant'
            user_id = room.get(f'{user_type}_id')
            user_name = room.get(f'{user_type}_name', 'Unknown')

            log_call_activity(
                user_id=user_id,
                room_id=room_id,
                event_type="appointment_call_recording_started",
                details=f"{user_type.capitalize()} '{user_name}' started audio/video call recording."
            )

            # Broadcast to everyone in the room
            await sio.emit('recording_started', {'status': 'active'}, room=room_id)
            logger.info(f"Recording started for room {room_id}")
    except Exception as e:
        logger.error(f"Error in start_recording: {e}")

@sio.event
async def offer(sid, data):
    """
    Forward WebRTC offer to peer
    data: {
        'room_id': str,
        'sdp': str (SDP offer)
    }
    """
    try:
        room_id = data.get('room_id')
        sdp = data.get('sdp')
        
        logger.info(f"Offer from {sid} in room {room_id}")
        
        if room_id not in active_rooms:
            raise Exception("Room not found")
        
        # Find the peer (other participant)
        room = active_rooms[room_id]
        peer_sid = None
        
        if room.get('user') == sid:
            peer_sid = room.get('consultant')
        elif room.get('consultant') == sid:
            peer_sid = room.get('user')
        
        if peer_sid:
            # Forward offer to peer
            await sio.emit('offer', {
                'sdp': sdp
            }, room=peer_sid)
            logger.info(f"Offer forwarded to {peer_sid}")
        else:
            raise Exception("Peer not found in room")
            
    except Exception as e:
        logger.error(f"Error in offer: {e}")
        await sio.emit('error', {'message': str(e)}, room=sid)

@sio.event
async def answer(sid, data):
    """
    Forward WebRTC answer to peer
    data: {
        'room_id': str,
        'sdp': str (SDP answer)
    }
    """
    try:
        room_id = data.get('room_id')
        sdp = data.get('sdp')
        
        logger.info(f"Answer from {sid} in room {room_id}")
        
        if room_id not in active_rooms:
            raise Exception("Room not found")
        
        # Find the peer
        room = active_rooms[room_id]
        peer_sid = None
        
        if room.get('user') == sid:
            peer_sid = room.get('consultant')
        elif room.get('consultant') == sid:
            peer_sid = room.get('user')
        
        if peer_sid:
            # Forward answer to peer
            await sio.emit('answer', {
                'sdp': sdp
            }, room=peer_sid)
            logger.info(f"Answer forwarded to {peer_sid}")
        else:
            raise Exception("Peer not found in room")
            
    except Exception as e:
        logger.error(f"Error in answer: {e}")
        await sio.emit('error', {'message': str(e)}, room=sid)

@sio.event
async def ice_candidate(sid, data):
    """
    Forward ICE candidate to peer
    data: {
        'room_id': str,
        'candidate': object (ICE candidate)
    }
    """
    try:
        room_id = data.get('room_id')
        candidate = data.get('candidate')
        
        if room_id not in active_rooms:
            return  # Silently ignore if room doesn't exist
        
        # Find the peer
        room = active_rooms[room_id]
        peer_sid = None
        
        if room.get('user') == sid:
            peer_sid = room.get('consultant')
        elif room.get('consultant') == sid:
            peer_sid = room.get('user')
        
        if peer_sid:
            # Forward ICE candidate to peer
            await sio.emit('ice_candidate', {
                'candidate': candidate
            }, room=peer_sid)
            
    except Exception as e:
        logger.error(f"Error in ice_candidate: {e}")

@sio.event
async def video_stopped(sid, data):
    """
    Notify peer that this participant turned off their camera.
    data: {
        'room_id': str
    }
    """
    try:
        room_id = data.get('room_id')

        if room_id not in active_rooms:
            return

        room = active_rooms[room_id]
        peer_sid = None

        if room.get('user') == sid:
            peer_sid = room.get('consultant')
        elif room.get('consultant') == sid:
            peer_sid = room.get('user')

        if peer_sid:
            await sio.emit('video_stopped', {}, room=peer_sid)
            logger.info(f"video_stopped forwarded from {sid} to {peer_sid}")

    except Exception as e:
        logger.error(f"Error in video_stopped: {e}")

@sio.event
async def leave_call(sid, data):
    """
    Leave a call room
    data: {
        'room_id': str
    }
    """
    try:
        room_id = data.get('room_id')
        
        logger.info(f"Leave room: {sid} from {room_id}")
        
        if room_id in active_rooms:
            room = active_rooms[room_id]
            
            user_type = 'user' if room.get('user') == sid else 'consultant'
            user_id = room.get(f'{user_type}_id')
            user_name = room.get(f'{user_type}_name', 'Unknown')
            
            log_call_activity(
                user_id=user_id,
                room_id=room_id,
                event_type="appointment_call_leave",
                details=f"{user_type.capitalize()} '{user_name}' left call room."
            )

            # Notify peer
            peer_sid = None
            if room.get('user') == sid:
                peer_sid = room.get('consultant')
            elif room.get('consultant') == sid:
                peer_sid = room.get('user')
            
            if peer_sid:
                await sio.emit('peer_left', {
                    'message': 'Other participant left the call'
                }, room=peer_sid)
            
            # Leave Socket.IO room
            await sio.leave_room(sid, room_id)
            
            # Clean up room if empty
            if room.get('user') == sid:
                room.pop('user', None)
                room.pop('user_name', None)
                room.pop('user_id', None)
            if room.get('consultant') == sid:
                room.pop('consultant', None)
                room.pop('consultant_name', None)
                room.pop('consultant_id', None)
            
            # Delete room if no participants
            if 'user' not in room and 'consultant' not in room:
                del active_rooms[room_id]
                logger.info(f"Room {room_id} deleted")
                
    except Exception as e:
        logger.error(f"Error in leave_room: {e}")


@sio.event
async def on_break(sid, data):
    """
    Notify peer that this participant is taking a short break.
    Audio is paused on the sender side; peer is shown a banner.
    data: {'room_id': str}
    """
    try:
        room_id = data.get('room_id')
        if room_id not in active_rooms:
            return
        room = active_rooms[room_id]
        user_type = 'user' if room.get('user') == sid else 'consultant'
        user_id = room.get(f'{user_type}_id')
        user_name = room.get(f'{user_type}_name', 'Unknown')

        log_call_activity(
            user_id=user_id,
            room_id=room_id,
            event_type="appointment_call_break",
            details=f"{user_type.capitalize()} '{user_name}' placed call on hold/took a break."
        )

        peer_sid = room.get('consultant') if room.get('user') == sid else room.get('user')
        if peer_sid:
            await sio.emit('peer_on_break', {
                'message': 'Other participant is on a short break'
            }, room=peer_sid)
            logger.info(f"on_break forwarded from {sid} to {peer_sid} in room {room_id}")
    except Exception as e:
        logger.error(f"Error in on_break: {e}")


@sio.event
async def rejoin_call(sid, data):
    """
    Notify peer that this participant has returned from a break.
    data: {'room_id': str}
    """
    try:
        room_id = data.get('room_id')
        if room_id not in active_rooms:
            return
        room = active_rooms[room_id]
        user_type = 'user' if room.get('user') == sid else 'consultant'
        user_id = room.get(f'{user_type}_id')
        user_name = room.get(f'{user_type}_name', 'Unknown')

        log_call_activity(
            user_id=user_id,
            room_id=room_id,
            event_type="appointment_call_rejoin",
            details=f"{user_type.capitalize()} '{user_name}' returned/rejoined call."
        )

        peer_sid = room.get('consultant') if room.get('user') == sid else room.get('user')
        if peer_sid:
            await sio.emit('peer_rejoined', {
                'message': 'Other participant has returned'
            }, room=peer_sid)
            logger.info(f"rejoin_call forwarded from {sid} to {peer_sid} in room {room_id}")
    except Exception as e:
        logger.error(f"Error in rejoin_call: {e}")


@sio.event
async def toggle_activity(sid, data):
    """
    Log room toggles (mute, camera, screen share)
    data: {
        'room_id': str,
        'activity_type': str,  # 'audio_mute', 'video_toggle', 'screen_share'
        'state': bool
    }
    """
    try:
        room_id = data.get('room_id')
        activity_type = data.get('activity_type')
        state = bool(data.get('state'))
        
        if room_id in active_rooms:
            room = active_rooms[room_id]
            user_type = 'user' if room.get('user') == sid else 'consultant'
            user_id = room.get(f'{user_type}_id')
            user_name = room.get(f'{user_type}_name', 'Unknown')
            
            details_map = {
                'audio_mute': "muted microphone" if state else "unmuted microphone",
                'video_toggle': "started video feed (camera on)" if state else "stopped video feed (camera off)"
            }
            details_str = details_map.get(activity_type, f"toggled {activity_type} to {state}")
            
            log_call_activity(
                user_id=user_id,
                room_id=room_id,
                event_type=f"appointment_call_{activity_type}",
                details=f"{user_type.capitalize()} '{user_name}' {details_str}."
            )
    except Exception as e:
        logger.error(f"Error in toggle_activity: {e}")


# Export the Socket.IO app
def get_socket_app():
    """Get the Socket.IO ASGI application"""
    return socketio.ASGIApp(sio)
