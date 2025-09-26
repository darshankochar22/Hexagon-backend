from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse
import json
import asyncio
import io
import base64
from gtts import gTTS
from pydub import AudioSegment
from pydub.playback import play
import tempfile
import os
from typing import Dict, Any, List

router = APIRouter()

class VoiceFeedbackManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.feedback_queue = asyncio.Queue()
        self.is_speaking = False
    
    async def connect(self, websocket: WebSocket, session_id: str):
        await websocket.accept()
        self.active_connections.append(websocket)
        print(f"Voice feedback connected for session: {session_id}")
    
    def disconnect(self, websocket: WebSocket, session_id: str):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        print(f"Voice feedback disconnected for session: {session_id}")
    
    async def send_voice_feedback(self, message: str, websocket: WebSocket):
        """Send voice feedback to the candidate"""
        try:
            # Generate speech from text
            audio_data = await self.text_to_speech(message)
            
            # Send audio data to frontend
            await websocket.send_text(json.dumps({
                "type": "voice_feedback",
                "message": message,
                "audio_data": audio_data
            }))
            
        except Exception as e:
            print(f"Error sending voice feedback: {e}")
            await websocket.send_text(json.dumps({
                "type": "error",
                "message": f"Voice feedback error: {str(e)}"
            }))
    
    async def text_to_speech(self, text: str) -> str:
        """Convert text to speech and return base64 audio data"""
        try:
            # Create temporary file
            with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as temp_file:
                temp_path = temp_file.name
            
            # Generate speech
            tts = gTTS(text=text, lang='en', slow=False)
            tts.save(temp_path)
            
            # Read audio file and convert to base64
            with open(temp_path, 'rb') as audio_file:
                audio_data = base64.b64encode(audio_file.read()).decode('utf-8')
            
            # Clean up temporary file
            os.unlink(temp_path)
            
            return audio_data
            
        except Exception as e:
            print(f"TTS Error: {e}")
            return ""
    
    async def generate_interview_feedback(self, analysis_data: Dict[str, Any]) -> str:
        """Generate appropriate feedback based on analysis"""
        feedback_type = analysis_data.get("type", "general")
        
        if feedback_type == "video_analysis":
            return await self.generate_video_feedback(analysis_data)
        elif feedback_type == "screen_analysis":
            return await self.generate_screen_feedback(analysis_data)
        else:
            return await self.generate_general_feedback(analysis_data)
    
    async def generate_video_feedback(self, analysis: Dict[str, Any]) -> str:
        """Generate voice feedback for video analysis"""
        feedback_parts = []
        
        # Professional appearance feedback
        if analysis.get("engagement", 0) < 5:
            feedback_parts.append("I notice you might want to sit up a bit straighter to show more engagement.")
        
        # Body language feedback
        if analysis.get("body_language"):
            body_lang = analysis["body_language"].lower()
            if "slouching" in body_lang or "closed" in body_lang:
                feedback_parts.append("Try to maintain an open, confident posture.")
            elif "confident" in body_lang or "professional" in body_lang:
                feedback_parts.append("Your body language looks very professional and confident.")
        
        # Engagement feedback
        engagement = analysis.get("engagement", 5)
        if engagement < 4:
            feedback_parts.append("I'd like to see more enthusiasm in your responses.")
        elif engagement > 7:
            feedback_parts.append("Your energy and engagement are excellent.")
        
        # Concerns
        concerns = analysis.get("concerns", [])
        if concerns:
            feedback_parts.append(f"I notice a few areas we might want to discuss: {', '.join(concerns[:2])}.")
        
        if not feedback_parts:
            feedback_parts.append("You're presenting yourself very well. Let's continue with the next question.")
        
        return " ".join(feedback_parts)
    
    async def generate_screen_feedback(self, analysis: Dict[str, Any]) -> str:
        """Generate voice feedback for screen analysis"""
        feedback_parts = []
        
        # Code quality feedback
        code_quality = analysis.get("code_quality", 5)
        if code_quality < 4:
            feedback_parts.append("I see some areas where we could improve the code structure and organization.")
        elif code_quality > 7:
            feedback_parts.append("Your code quality and organization look very strong.")
        
        # Problem-solving feedback
        problem_solving = analysis.get("problem_solving", 5)
        if problem_solving < 4:
            feedback_parts.append("Let's think about a more systematic approach to this problem.")
        elif problem_solving > 7:
            feedback_parts.append("Your problem-solving approach is very methodical and well thought out.")
        
        # Technical skills feedback
        tech_skills = analysis.get("technical_skills", 5)
        if tech_skills < 4:
            feedback_parts.append("I'd like to explore your experience with the technologies we're using here.")
        elif tech_skills > 7:
            feedback_parts.append("Your technical skills are clearly demonstrated in this work.")
        
        # Recommendations
        recommendations = analysis.get("recommendations", [])
        if recommendations:
            feedback_parts.append(f"Here are some suggestions: {recommendations[0]}.")
        
        if not feedback_parts:
            feedback_parts.append("This looks good. Can you walk me through your thought process?")
        
        return " ".join(feedback_parts)
    
    async def generate_general_feedback(self, analysis: Dict[str, Any]) -> str:
        """Generate general voice feedback"""
        return "Thank you for that response. Let's move on to the next question."

# Global voice feedback manager
voice_manager = VoiceFeedbackManager()

@router.websocket("/voice-feedback/{session_id}")
async def voice_feedback_websocket(websocket: WebSocket, session_id: str):
    """WebSocket endpoint for real-time voice feedback"""
    await voice_manager.connect(websocket, session_id)
    
    try:
        while True:
            # Wait for analysis data from the main interview system
            data = await websocket.receive_text()
            analysis_data = json.loads(data)
            
            # Generate appropriate feedback
            feedback_message = await voice_manager.generate_interview_feedback(analysis_data)
            
            # Send voice feedback
            await voice_manager.send_voice_feedback(feedback_message, websocket)
            
    except WebSocketDisconnect:
        voice_manager.disconnect(websocket, session_id)

@router.post("/generate-feedback")
async def generate_feedback(analysis_data: Dict[str, Any]):
    """Generate text feedback for analysis data"""
    try:
        feedback_message = await voice_manager.generate_interview_feedback(analysis_data)
        
        return {
            "status": "success",
            "feedback": feedback_message
        }
        
    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }

@router.post("/text-to-speech")
async def text_to_speech_endpoint(text: str):
    """Convert text to speech and return audio data"""
    try:
        audio_data = await voice_manager.text_to_speech(text)
        
        return {
            "status": "success",
            "audio_data": audio_data
        }
        
    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }
