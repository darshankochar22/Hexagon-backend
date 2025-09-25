from fastapi import APIRouter, HTTPException, Depends
import socketio
from ..core.db import get_db
import json
from datetime import datetime

router = APIRouter()

# In-memory storage for rooms and participants
# In production, use Redis or database
rooms = {}
participants = {}

# Create Socket.IO server
sio = socketio.AsyncServer(
    cors_allowed_origins=["http://localhost:5173"],
    logger=True,
    engineio_logger=True
)

@sio.event
async def connect(sid, environ, auth):
    print(f"Client connected: {sid}")

@sio.event
async def disconnect(sid):
    print(f"Client disconnected: {sid}")
    # Remove user from all rooms
    for room_id, room_participants in rooms.items():
        if sid in room_participants:
            room_participants.remove(sid)
            # Notify other participants
            await sio.emit("user-left", participants.get(sid, "Unknown"), room=room_id, skip_sid=sid)
            # Clean up
            if sid in participants:
                del participants[sid]
            break

@sio.event
async def join_room(sid, data):
    """Handle user joining a room"""
    try:
        room_id = data.get('room_id')
        user_id = data.get('user_id')
        
        # Store participant info
        participants[sid] = user_id
        
        # Add to room
        if room_id not in rooms:
            rooms[room_id] = []
        
        # Notify existing participants about new user
        if rooms[room_id]:
            await sio.emit("user-joined", user_id, room=room_id, skip_sid=sid)
        
        # Add user to room
        rooms[room_id].append(sid)
        
        # Join Socket.IO room
        await sio.enter_room(sid, room_id)
        
        print(f"User {user_id} joined room {room_id}")
        
    except Exception as e:
        print(f"Error joining room: {e}")
        await sio.emit("error", {"message": "Failed to join room"}, room=sid)

@sio.event
async def leave_room(sid, data):
    """Handle user leaving a room"""
    try:
        room_id = data.get('room_id')
        user_id = participants.get(sid, "Unknown")
        
        # Remove from room
        if room_id in rooms and sid in rooms[room_id]:
            rooms[room_id].remove(sid)
            
            # Notify other participants
            await sio.emit("user-left", user_id, room=room_id, skip_sid=sid)
            
            # Clean up empty rooms
            if not rooms[room_id]:
                del rooms[room_id]
        
        # Remove from Socket.IO room
        await sio.leave_room(sid, room_id)
        
        # Clean up participant info
        if sid in participants:
            del participants[sid]
            
        print(f"User {user_id} left room {room_id}")
        
    except Exception as e:
        print(f"Error leaving room: {e}")

@sio.event
async def offer(sid, data):
    """Handle WebRTC offer"""
    try:
        offer = data.get('offer')
        target_user_id = data.get('target_user_id')
        sender_id = participants.get(sid, "Unknown")
        
        # Find target user's socket ID
        target_sid = None
        for socket_id, user_id in participants.items():
            if user_id == target_user_id:
                target_sid = socket_id
                break
        
        if target_sid:
            await sio.emit("offer", {"offer": offer, "from_user_id": sender_id}, room=target_sid)
            print(f"Offer sent from {sender_id} to {target_user_id}")
        else:
            await sio.emit("error", {"message": "Target user not found"}, room=sid)
            
    except Exception as e:
        print(f"Error handling offer: {e}")
        await sio.emit("error", {"message": "Failed to send offer"}, room=sid)

@sio.event
async def answer(sid, data):
    """Handle WebRTC answer"""
    try:
        answer = data.get('answer')
        target_user_id = data.get('target_user_id')
        sender_id = participants.get(sid, "Unknown")
        
        # Find target user's socket ID
        target_sid = None
        for socket_id, user_id in participants.items():
            if user_id == target_user_id:
                target_sid = socket_id
                break
        
        if target_sid:
            await sio.emit("answer", {"answer": answer, "from_user_id": sender_id}, room=target_sid)
            print(f"Answer sent from {sender_id} to {target_user_id}")
        else:
            await sio.emit("error", {"message": "Target user not found"}, room=sid)
            
    except Exception as e:
        print(f"Error handling answer: {e}")
        await sio.emit("error", {"message": "Failed to send answer"}, room=sid)

@sio.event
async def ice_candidate(sid, data):
    """Handle ICE candidate"""
    try:
        candidate = data.get('candidate')
        target_user_id = data.get('target_user_id')
        sender_id = participants.get(sid, "Unknown")
        
        # Find target user's socket ID
        target_sid = None
        for socket_id, user_id in participants.items():
            if user_id == target_user_id:
                target_sid = socket_id
                break
        
        if target_sid:
            await sio.emit("ice-candidate", {"candidate": candidate, "from_user_id": sender_id}, room=target_sid)
            print(f"ICE candidate sent from {sender_id} to {target_user_id}")
        else:
            await sio.emit("error", {"message": "Target user not found"}, room=sid)
            
    except Exception as e:
        print(f"Error handling ICE candidate: {e}")
        await sio.emit("error", {"message": "Failed to send ICE candidate"}, room=sid)

@sio.event
async def message(sid, data):
    """Handle text messages in room"""
    try:
        message = data.get('message')
        room_id = data.get('room_id')
        user_id = participants.get(sid, "Unknown")
        message_data = {
            "user_id": user_id,
            "message": message,
            "timestamp": str(datetime.utcnow())
        }
        
        await sio.emit("message", message_data, room=room_id)
        print(f"Message from {user_id} in room {room_id}: {message}")
        
    except Exception as e:
        print(f"Error handling message: {e}")
        await sio.emit("error", {"message": "Failed to send message"}, room=sid)

# REST endpoints for room management
@router.get("/rooms")
async def get_rooms():
    """Get list of active rooms"""
    return {
        "rooms": [
            {
                "room_id": room_id,
                "participant_count": len(participants_list),
                "participants": [participants.get(sid, "Unknown") for sid in participants_list]
            }
            for room_id, participants_list in rooms.items()
        ]
    }

@router.get("/rooms/{room_id}")
async def get_room_info(room_id: str):
    """Get information about a specific room"""
    if room_id not in rooms:
        raise HTTPException(status_code=404, detail="Room not found")
    
    return {
        "room_id": room_id,
        "participant_count": len(rooms[room_id]),
        "participants": [participants.get(sid, "Unknown") for sid in rooms[room_id]]
    }

@router.delete("/rooms/{room_id}")
async def delete_room(room_id: str):
    """Delete a room (admin only)"""
    if room_id not in rooms:
        raise HTTPException(status_code=404, detail="Room not found")
    
    # Notify all participants that room is being deleted
    await socket_manager.emit("room-deleted", {"message": "Room has been deleted"}, room=room_id)
    
    # Remove all participants from room
    for sid in rooms[room_id]:
        await socket_manager.leave_room(sid, room_id)
        if sid in participants:
            del participants[sid]
    
    # Delete room
    del rooms[room_id]
    
    return {"message": f"Room {room_id} deleted successfully"}

# Export socket server for use in main app
def get_socket_server():
    return sio
