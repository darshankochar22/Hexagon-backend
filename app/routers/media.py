from fastapi import APIRouter, UploadFile, File, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import StreamingResponse
import aiofiles
import os
import uuid
import json
import asyncio
from datetime import datetime
from typing import List, Optional
import cv2
import numpy as np
import base64

router = APIRouter()

# Create media storage directory
MEDIA_DIR = "media_storage"
os.makedirs(MEDIA_DIR, exist_ok=True)

# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.media_sessions: dict = {}

    async def connect(self, websocket: WebSocket, session_id: str):
        await websocket.accept()
        self.active_connections.append(websocket)
        if session_id not in self.media_sessions:
            self.media_sessions[session_id] = {
                "connections": [],
                "recordings": [],
                "created_at": datetime.now()
            }
        self.media_sessions[session_id]["connections"].append(websocket)

    def disconnect(self, websocket: WebSocket, session_id: str):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        if session_id in self.media_sessions:
            if websocket in self.media_sessions[session_id]["connections"]:
                self.media_sessions[session_id]["connections"].remove(websocket)

    async def send_personal_message(self, message: str, websocket: WebSocket):
        await websocket.send_text(message)

    async def broadcast_to_session(self, message: str, session_id: str):
        if session_id in self.media_sessions:
            for connection in self.media_sessions[session_id]["connections"]:
                try:
                    await connection.send_text(message)
                except:
                    # Remove broken connections
                    self.media_sessions[session_id]["connections"].remove(connection)

manager = ConnectionManager()

@router.post("/upload/video")
async def upload_video(
    file: UploadFile = File(...),
    session_id: str = None,
    user_id: str = None
):
    """Upload video file (webcam or screen recording)"""
    if not session_id:
        session_id = str(uuid.uuid4())
    
    # Create session directory
    session_dir = os.path.join(MEDIA_DIR, session_id)
    os.makedirs(session_dir, exist_ok=True)
    
    # Generate unique filename
    file_extension = file.filename.split('.')[-1] if '.' in file.filename else 'mp4'
    filename = f"video_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{file_extension}"
    file_path = os.path.join(session_dir, filename)
    
    # Save file
    async with aiofiles.open(file_path, 'wb') as f:
        content = await file.read()
        await f.write(content)
    
    # Process video metadata
    video_info = {
        "filename": filename,
        "file_path": file_path,
        "file_size": len(content),
        "upload_time": datetime.now().isoformat(),
        "user_id": user_id,
        "session_id": session_id,
        "type": "video"
    }
    
    # Store metadata
    metadata_path = os.path.join(session_dir, f"{filename}.json")
    async with aiofiles.open(metadata_path, 'w') as f:
        await f.write(json.dumps(video_info, indent=2))
    
    return {
        "status": "success",
        "session_id": session_id,
        "filename": filename,
        "file_size": len(content),
        "message": "Video uploaded successfully"
    }

@router.post("/upload/audio")
async def upload_audio(
    file: UploadFile = File(...),
    session_id: str = None,
    user_id: str = None
):
    """Upload audio file (voice recording)"""
    if not session_id:
        session_id = str(uuid.uuid4())
    
    # Create session directory
    session_dir = os.path.join(MEDIA_DIR, session_id)
    os.makedirs(session_dir, exist_ok=True)
    
    # Generate unique filename
    file_extension = file.filename.split('.')[-1] if '.' in file.filename else 'wav'
    filename = f"audio_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{file_extension}"
    file_path = os.path.join(session_dir, filename)
    
    # Save file
    async with aiofiles.open(file_path, 'wb') as f:
        content = await file.read()
        await f.write(content)
    
    # Process audio metadata
    audio_info = {
        "filename": filename,
        "file_path": file_path,
        "file_size": len(content),
        "upload_time": datetime.now().isoformat(),
        "user_id": user_id,
        "session_id": session_id,
        "type": "audio"
    }
    
    # Store metadata
    metadata_path = os.path.join(session_dir, f"{filename}.json")
    async with aiofiles.open(metadata_path, 'w') as f:
        await f.write(json.dumps(audio_info, indent=2))
    
    return {
        "status": "success",
        "session_id": session_id,
        "filename": filename,
        "file_size": len(content),
        "message": "Audio uploaded successfully"
    }

@router.post("/upload/screenshot")
async def upload_screenshot(
    file: UploadFile = File(...),
    session_id: str = None,
    user_id: str = None
):
    """Upload screenshot from screen sharing"""
    if not session_id:
        session_id = str(uuid.uuid4())
    
    # Create session directory
    session_dir = os.path.join(MEDIA_DIR, session_id)
    os.makedirs(session_dir, exist_ok=True)
    
    # Generate unique filename
    file_extension = file.filename.split('.')[-1] if '.' in file.filename else 'png'
    filename = f"screenshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{file_extension}"
    file_path = os.path.join(session_dir, filename)
    
    # Save file
    async with aiofiles.open(file_path, 'wb') as f:
        content = await file.read()
        await f.write(content)
    
    # Process image metadata
    image_info = {
        "filename": filename,
        "file_path": file_path,
        "file_size": len(content),
        "upload_time": datetime.now().isoformat(),
        "user_id": user_id,
        "session_id": session_id,
        "type": "screenshot"
    }
    
    # Store metadata
    metadata_path = os.path.join(session_dir, f"{filename}.json")
    async with aiofiles.open(metadata_path, 'w') as f:
        await f.write(json.dumps(image_info, indent=2))
    
    return {
        "status": "success",
        "session_id": session_id,
        "filename": filename,
        "file_size": len(content),
        "message": "Screenshot uploaded successfully"
    }

@router.post("/stream/start")
async def start_media_stream(
    session_id: str,
    user_id: str = None,
    stream_type: str = "video"  # video, audio, or both
):
    """Start a media streaming session"""
    if session_id not in manager.media_sessions:
        manager.media_sessions[session_id] = {
            "connections": [],
            "recordings": [],
            "created_at": datetime.now(),
            "user_id": user_id,
            "stream_type": stream_type
        }
    
    return {
        "status": "success",
        "session_id": session_id,
        "message": f"Media streaming session started for {stream_type}"
    }

@router.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    """WebSocket endpoint for real-time media streaming"""
    await manager.connect(websocket, session_id)
    
    try:
        while True:
            # Receive data from client
            data = await websocket.receive_text()
            message = json.loads(data)
            
            if message["type"] == "video_frame":
                # Process video frame
                frame_data = message["data"]
                timestamp = message.get("timestamp", datetime.now().isoformat())
                
                # Save frame if needed
                if message.get("save_frame", False):
                    frame_bytes = base64.b64decode(frame_data)
                    frame_filename = f"frame_{timestamp.replace(':', '-')}.jpg"
                    frame_path = os.path.join(MEDIA_DIR, session_id, frame_filename)
                    
                    # Ensure directory exists
                    os.makedirs(os.path.dirname(frame_path), exist_ok=True)
                    
                    async with aiofiles.open(frame_path, 'wb') as f:
                        await f.write(frame_bytes)
                
                # Broadcast to other connections in the same session
                await manager.broadcast_to_session(json.dumps({
                    "type": "video_frame",
                    "data": frame_data,
                    "timestamp": timestamp,
                    "user_id": message.get("user_id")
                }), session_id)
            
            elif message["type"] == "audio_chunk":
                # Process audio chunk
                audio_data = message["data"]
                timestamp = message.get("timestamp", datetime.now().isoformat())
                
                # Save audio chunk if needed
                if message.get("save_chunk", False):
                    audio_bytes = base64.b64decode(audio_data)
                    audio_filename = f"audio_chunk_{timestamp.replace(':', '-')}.wav"
                    audio_path = os.path.join(MEDIA_DIR, session_id, audio_filename)
                    
                    # Ensure directory exists
                    os.makedirs(os.path.dirname(audio_path), exist_ok=True)
                    
                    async with aiofiles.open(audio_path, 'wb') as f:
                        await f.write(audio_bytes)
                
                # Broadcast to other connections in the same session
                await manager.broadcast_to_session(json.dumps({
                    "type": "audio_chunk",
                    "data": audio_data,
                    "timestamp": timestamp,
                    "user_id": message.get("user_id")
                }), session_id)
            
            elif message["type"] == "screen_share":
                # Process screen share data
                screen_data = message["data"]
                timestamp = message.get("timestamp", datetime.now().isoformat())
                
                # Save screen share frame
                if message.get("save_frame", False):
                    screen_bytes = base64.b64decode(screen_data)
                    screen_filename = f"screen_{timestamp.replace(':', '-')}.png"
                    screen_path = os.path.join(MEDIA_DIR, session_id, screen_filename)
                    
                    # Ensure directory exists
                    os.makedirs(os.path.dirname(screen_path), exist_ok=True)
                    
                    async with aiofiles.open(screen_path, 'wb') as f:
                        await f.write(screen_bytes)
                
                # Broadcast to other connections in the same session
                await manager.broadcast_to_session(json.dumps({
                    "type": "screen_share",
                    "data": screen_data,
                    "timestamp": timestamp,
                    "user_id": message.get("user_id")
                }), session_id)
    
    except WebSocketDisconnect:
        manager.disconnect(websocket, session_id)

@router.get("/session/{session_id}/files")
async def get_session_files(session_id: str):
    """Get all files for a specific session"""
    session_dir = os.path.join(MEDIA_DIR, session_id)
    
    if not os.path.exists(session_dir):
        raise HTTPException(status_code=404, detail="Session not found")
    
    files = []
    for filename in os.listdir(session_dir):
        if filename.endswith('.json'):
            # Skip metadata files
            continue
        
        file_path = os.path.join(session_dir, filename)
        file_stat = os.stat(file_path)
        
        files.append({
            "filename": filename,
            "file_size": file_stat.st_size,
            "created_at": datetime.fromtimestamp(file_stat.st_ctime).isoformat(),
            "file_type": filename.split('.')[-1]
        })
    
    return {
        "session_id": session_id,
        "files": files,
        "total_files": len(files)
    }

@router.get("/session/{session_id}/download/{filename}")
async def download_file(session_id: str, filename: str):
    """Download a specific file from a session"""
    file_path = os.path.join(MEDIA_DIR, session_id, filename)
    
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")
    
    def iterfile():
        with open(file_path, mode="rb") as file_like:
            yield from file_like
    
    return StreamingResponse(iterfile(), media_type="application/octet-stream")

@router.delete("/session/{session_id}")
async def delete_session(session_id: str):
    """Delete a session and all its files"""
    session_dir = os.path.join(MEDIA_DIR, session_id)
    
    if not os.path.exists(session_dir):
        raise HTTPException(status_code=404, detail="Session not found")
    
    # Remove all files in the session directory
    import shutil
    shutil.rmtree(session_dir)
    
    # Remove from active sessions
    if session_id in manager.media_sessions:
        del manager.media_sessions[session_id]
    
    return {
        "status": "success",
        "message": f"Session {session_id} deleted successfully"
    }

@router.get("/sessions")
async def list_sessions():
    """List all active sessions"""
    sessions = []
    for session_id, session_data in manager.media_sessions.items():
        sessions.append({
            "session_id": session_id,
            "user_id": session_data.get("user_id"),
            "created_at": session_data["created_at"].isoformat(),
            "active_connections": len(session_data["connections"]),
            "stream_type": session_data.get("stream_type", "video")
        })
    
    return {
        "sessions": sessions,
        "total_sessions": len(sessions)
    }
