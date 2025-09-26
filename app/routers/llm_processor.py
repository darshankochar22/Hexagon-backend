from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import StreamingResponse
import json
import base64
import asyncio
from datetime import datetime
from typing import List, Dict, Any
from google import genai
import os
from PIL import Image
import io
import PyPDF2

router = APIRouter()

# Gemini Client (new SDK per docs)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "your-gemini-api-key")
client = genai.Client(api_key=GEMINI_API_KEY)  # https://ai.google.dev/gemini-api/docs

# WebSocket connection manager for LLM processing
class LLMConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.llm_sessions: dict = {}
        self.analysis_queue: dict = {}

    async def connect(self, websocket: WebSocket, session_id: str, analysis_type: str = "general"):
        await websocket.accept()
        self.active_connections.append(websocket)
        
        if session_id not in self.llm_sessions:
            self.llm_sessions[session_id] = {
                "connections": [],
                "analysis_type": analysis_type,
                "created_at": datetime.now(),
                "insights": [],
                "video_analysis": [],
                "audio_analysis": [],
                "screen_analysis": []
            }
        
        self.llm_sessions[session_id]["connections"].append(websocket)

    def disconnect(self, websocket: WebSocket, session_id: str):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        if session_id in self.llm_sessions:
            if websocket in self.llm_sessions[session_id]["connections"]:
                self.llm_sessions[session_id]["connections"].remove(websocket)

    async def send_llm_analysis(self, analysis: dict, websocket: WebSocket):
        await websocket.send_text(json.dumps(analysis))
        
        # Also send to voice feedback system if available
        try:
            from .voice_feedback import voice_manager
            
            # Generate voice feedback based on analysis
            feedback_message = await voice_manager.generate_interview_feedback(analysis)
            
            # Send voice feedback
            await websocket.send_text(json.dumps({
                "type": "voice_feedback",
                "message": feedback_message
            }))
            
        except Exception as voice_error:
            print(f"Voice feedback error: {voice_error}")

    async def broadcast_analysis(self, analysis: dict, session_id: str):
        if session_id in self.llm_sessions:
            for connection in self.llm_sessions[session_id]["connections"]:
                try:
                    await connection.send_text(json.dumps(analysis))
                except:
                    self.llm_sessions[session_id]["connections"].remove(connection)

llm_manager = LLMConnectionManager()

@router.websocket("/llm/stream/{session_id}")
async def llm_video_stream(websocket: WebSocket, session_id: str):
    """WebSocket endpoint for real-time video/audio streaming to LLM"""
    await llm_manager.connect(websocket, session_id, "video_analysis")
    
    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            
            if message["type"] == "video_frame":
                # Process video frame with LLM
                analysis = await analyze_video_frame(
                    message["data"], 
                    session_id, 
                    message.get("timestamp")
                )
                
                # Store analysis
                if session_id in llm_manager.llm_sessions:
                    llm_manager.llm_sessions[session_id]["video_analysis"].append(analysis)
                
                # Send analysis back to client
                await llm_manager.send_llm_analysis(analysis, websocket)
            
            elif message["type"] == "audio_chunk":
                # Process audio with LLM
                analysis = await analyze_audio_chunk(
                    message["data"], 
                    session_id, 
                    message.get("timestamp")
                )
                
                # Store analysis
                if session_id in llm_manager.llm_sessions:
                    llm_manager.llm_sessions[session_id]["audio_analysis"].append(analysis)
                
                # Send analysis back to client
                await llm_manager.send_llm_analysis(analysis, websocket)
    
    except WebSocketDisconnect:
        llm_manager.disconnect(websocket, session_id)

@router.websocket("/llm/screen/{session_id}")
async def llm_screen_stream(websocket: WebSocket, session_id: str):
    """WebSocket endpoint for real-time screen share analysis"""
    await llm_manager.connect(websocket, session_id, "screen_analysis")
    
    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            
            if message["type"] == "screen_share":
                # Process screen share with LLM
                analysis = await analyze_screen_share(
                    message["data"], 
                    session_id, 
                    message.get("timestamp")
                )
                
                # Store analysis
                if session_id in llm_manager.llm_sessions:
                    llm_manager.llm_sessions[session_id]["screen_analysis"].append(analysis)
                
                # Send analysis back to client
                await llm_manager.send_llm_analysis(analysis, websocket)
    
    except WebSocketDisconnect:
        llm_manager.disconnect(websocket, session_id)

async def analyze_video_frame(frame_data: str, session_id: str, timestamp: str = None) -> dict:
    """Analyze video frame using Gemini"""
    try:
        # Decode base64 image
        image_data = base64.b64decode(frame_data)
        image = Image.open(io.BytesIO(image_data))
        
        # Prepare prompt for Gemini
        prompt = """Analyze this interview video frame and provide insights on:
1) Facial expressions and emotions
2) Body language and posture
3) Professional appearance
4) Engagement level
5) Any concerning behaviors

Keep response concise and actionable. Format as JSON with these fields:
- analysis: main analysis text
- emotions: detected emotions
- body_language: posture and gestures
- engagement: level of engagement (1-10)
- concerns: any red flags or concerns"""

        # Call Gemini API (new client) with inline image (compressed as PNG)
        image_b64 = base64.b64encode(image_data).decode('utf-8')
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[
                {
                    "parts": [
                        {"text": prompt},
                        {"inline_data": {"mime_type": "image/png", "data": image_b64}}
                    ]
                }
            ]
        )
        
        analysis_text = response.text
        
        # Try to parse as JSON, fallback to plain text
        try:
            analysis_json = json.loads(analysis_text)
            return {
                "type": "video_analysis",
                "session_id": session_id,
                "timestamp": timestamp or datetime.now().isoformat(),
                "analysis": analysis_json.get("analysis", analysis_text),
                "emotions": analysis_json.get("emotions", []),
                "body_language": analysis_json.get("body_language", ""),
                "engagement": analysis_json.get("engagement", 5),
                "concerns": analysis_json.get("concerns", []),
                "confidence": 0.9,  # Gemini is quite reliable
                "insights": extract_key_insights(analysis_text)
            }
        except json.JSONDecodeError:
            # Fallback to plain text analysis
            return {
                "type": "video_analysis",
                "session_id": session_id,
                "timestamp": timestamp or datetime.now().isoformat(),
                "analysis": analysis_text,
                "confidence": 0.9,
                "insights": extract_key_insights(analysis_text)
            }
        
    except Exception as e:
        return {
            "type": "video_analysis",
            "session_id": session_id,
            "timestamp": timestamp or datetime.now().isoformat(),
            "error": str(e),
            "analysis": "Analysis failed"
        }

async def analyze_audio_chunk(audio_data: str, session_id: str, timestamp: str = None) -> dict:
    """Analyze audio chunk using LLM"""
    try:
        # For audio analysis, you might want to use Whisper API first
        # This is a simplified version - you'd need to implement audio transcription
        
        # Placeholder for audio analysis
        # In real implementation, you'd:
        # 1. Convert audio to text using Whisper
        # 2. Analyze the text with GPT
        
        return {
            "type": "audio_analysis",
            "session_id": session_id,
            "timestamp": timestamp or datetime.now().isoformat(),
            "analysis": "Audio analysis placeholder - implement Whisper + GPT integration",
            "transcript": "Transcribed text would go here",
            "sentiment": "neutral",
            "confidence": 0.8
        }
        
    except Exception as e:
        return {
            "type": "audio_analysis",
            "session_id": session_id,
            "timestamp": timestamp or datetime.now().isoformat(),
            "error": str(e),
            "analysis": "Audio analysis failed"
        }

async def analyze_screen_share(screen_data: str, session_id: str, timestamp: str = None) -> dict:
    """Analyze screen share using Gemini"""
    try:
        # Decode base64 image
        image_data = base64.b64decode(screen_data)
        image = Image.open(io.BytesIO(image_data))
        
        # Prepare prompt for Gemini
        prompt = """Analyze this screen share from an interview and provide insights on:
1) Code quality and structure
2) Problem-solving approach
3) Technical skills demonstration
4) Communication clarity
5) Any red flags or concerns

Format as JSON with these fields:
- analysis: main analysis text
- code_quality: assessment of code quality (1-10)
- problem_solving: problem-solving approach rating (1-10)
- technical_skills: technical skills demonstration (1-10)
- communication: communication clarity (1-10)
- concerns: any red flags or concerns
- recommendations: specific improvement suggestions"""

        # Call Gemini API (new client) with inline image (compressed as PNG)
        image_b64 = base64.b64encode(image_data).decode('utf-8')
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[
                {
                    "parts": [
                        {"text": prompt},
                        {"inline_data": {"mime_type": "image/png", "data": image_b64}}
                    ]
                }
            ]
        )
        
        analysis_text = response.text
        
        # Try to parse as JSON, fallback to plain text
        try:
            analysis_json = json.loads(analysis_text)
            return {
                "type": "screen_analysis",
                "session_id": session_id,
                "timestamp": timestamp or datetime.now().isoformat(),
                "analysis": analysis_json.get("analysis", analysis_text),
                "code_quality": analysis_json.get("code_quality", 5),
                "problem_solving": analysis_json.get("problem_solving", 5),
                "technical_skills": analysis_json.get("technical_skills", 5),
                "communication": analysis_json.get("communication", 5),
                "concerns": analysis_json.get("concerns", []),
                "recommendations": analysis_json.get("recommendations", []),
                "confidence": 0.9,
                "insights": extract_key_insights(analysis_text)
            }
        except json.JSONDecodeError:
            # Fallback to plain text analysis
            return {
                "type": "screen_analysis",
                "session_id": session_id,
                "timestamp": timestamp or datetime.now().isoformat(),
                "analysis": analysis_text,
                "confidence": 0.9,
                "insights": extract_key_insights(analysis_text)
            }
        
    except Exception as e:
        return {
            "type": "screen_analysis",
            "session_id": session_id,
            "timestamp": timestamp or datetime.now().isoformat(),
            "error": str(e),
            "analysis": "Screen analysis failed"
        }

def extract_key_insights(analysis_text: str) -> List[str]:
    """Extract key insights from LLM analysis"""
    # Simple keyword extraction - you can make this more sophisticated
    keywords = ["excellent", "good", "poor", "concern", "improve", "strong", "weak", "recommendation"]
    insights = []
    
    for keyword in keywords:
        if keyword.lower() in analysis_text.lower():
            insights.append(keyword)
    
    return insights

@router.post("/llm/analyze/video")
async def analyze_video_endpoint(request: dict):
    """HTTP endpoint for video analysis"""
    session_id = request.get("session_id")
    frame_data = request.get("frame_data")
    timestamp = request.get("timestamp")
    
    analysis = await analyze_video_frame(frame_data, session_id, timestamp)
    return analysis

@router.post("/llm/analyze/audio")
async def analyze_audio_endpoint(request: dict):
    """HTTP endpoint for audio analysis"""
    session_id = request.get("session_id")
    audio_data = request.get("audio_data")
    timestamp = request.get("timestamp")
    
    analysis = await analyze_audio_chunk(audio_data, session_id, timestamp)
    return analysis

@router.get("/llm/insights/{session_id}")
async def get_session_insights(session_id: str):
    """Get all insights for a session"""
    if session_id not in llm_manager.llm_sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    session_data = llm_manager.llm_sessions[session_id]
    
    return {
        "session_id": session_id,
        "created_at": session_data["created_at"].isoformat(),
        "total_analyses": len(session_data["video_analysis"]) + len(session_data["audio_analysis"]) + len(session_data["screen_analysis"]),
        "video_analyses": session_data["video_analysis"][-10:],  # Last 10
        "audio_analyses": session_data["audio_analysis"][-10:],  # Last 10
        "screen_analyses": session_data["screen_analysis"][-10:],  # Last 10
        "summary": generate_session_summary(session_data)
    }

def generate_session_summary(session_data: dict) -> str:
    """Generate a summary of the session"""
    total_analyses = len(session_data["video_analysis"]) + len(session_data["audio_analysis"]) + len(session_data["screen_analysis"])
    
    return f"Session completed with {total_analyses} total analyses. Review individual analyses for detailed insights."

@router.get("/llm/sessions")
async def list_llm_sessions():
    """List all active LLM sessions"""
    sessions = []
    for session_id, session_data in llm_manager.llm_sessions.items():
        sessions.append({
            "session_id": session_id,
            "analysis_type": session_data["analysis_type"],
            "created_at": session_data["created_at"].isoformat(),
            "active_connections": len(session_data["connections"]),
            "total_analyses": len(session_data["video_analysis"]) + len(session_data["audio_analysis"]) + len(session_data["screen_analysis"])
        })
    
    return {"sessions": sessions, "total_sessions": len(sessions)}

# ---------------------------------------------
# Chat Completions with Context (Job + Resume)
# ---------------------------------------------
@router.post("/llm/chat")
async def llm_chat(payload: dict):
    """Chat endpoint that incorporates job description and resume context.

    Expected JSON body:
    {
      "messages": [{"role": "user"|"assistant"|"system", "content": "..."}, ...],
      "selected_job": { id, title, company, location, experience, skills, description } | null,
      "all_jobs": [ ...optional reduced list... ],
      "resume_meta": { filename, uploaded_at, file_size, content_type } | null,
      "resume_file_base64": "..." | null
    }
    """
    try:
        messages = payload.get("messages", [])
        selected_job = payload.get("selected_job")
        all_jobs = payload.get("all_jobs", [])
        resume_meta = payload.get("resume_meta")
        resume_b64 = payload.get("resume_file_base64")
        session_id = payload.get("session_id")
        session_insights_from_client = payload.get("session_insights")
        local_insights_tail = payload.get("local_insights_tail")

        system_preamble = (
            "You are an expert technical interviewer conducting a real-time interview. "
            "You have access to real-time visual analysis of the candidate including:\n"
            "- Video analysis: body language, emotions, engagement level, professionalism\n"
            "- Screen analysis: technical skills demonstration, problem-solving approach\n"
            "- Behavioral insights: communication clarity, focus, preparation\n\n"
            "Use this real-time analysis along with the job description and resume to:\n"
            "1. Acknowledge what you observe about their performance\n"
            "2. Provide targeted feedback and coaching\n"
            "3. Ask follow-up questions based on their behavior\n"
            "4. Give specific, actionable advice for improvement\n"
            "5. Reference specific observations from the visual analysis\n\n"
            "Be direct but supportive in your feedback. Help them improve their interview performance in real-time."
        )

        job_context = json.dumps(selected_job, ensure_ascii=False, indent=2) if selected_job else "None"
        jobs_summary = json.dumps(all_jobs[:10], ensure_ascii=False, indent=2) if all_jobs else "[]"

        resume_note = "Resume not provided."
        resume_text = None
        if resume_b64:
            resume_note = f"Resume provided: {resume_meta.get('filename') if resume_meta else 'unknown filename'}"
            try:
                resume_bytes = base64.b64decode(resume_b64)
                content_type = (resume_meta or {}).get('content_type', '')
                if 'pdf' in content_type.lower() or (resume_meta and str(resume_meta.get('filename','')).lower().endswith('.pdf')):
                    # Extract text from PDF
                    pdf_reader = PyPDF2.PdfReader(io.BytesIO(resume_bytes))
                    text_parts = []
                    for page in pdf_reader.pages:
                        try:
                            text_parts.append(page.extract_text() or '')
                        except Exception:
                            continue
                    extracted = "\n".join([t for t in text_parts if t])
                    resume_text = extracted.strip() if extracted else None
                else:
                    # Non-PDF resumes: pass a short note; for DOC/DOCX consider adding python-docx support later
                    resume_text = None
            except Exception:
                resume_text = None

        # Build prompt
        # Incorporate latest visual insights (video/screen) if present for session
        visual_context = ""
        try:
            # Prefer server-side session store
            if session_id and session_id in llm_manager.llm_sessions:
                sess = llm_manager.llm_sessions.get(session_id, {})
                video_tail = (sess.get("video_analysis") or [])[-3:]
                screen_tail = (sess.get("screen_analysis") or [])[-3:]
            else:
                # Fallback to client-provided snapshot
                video_tail = ((session_insights_from_client or {}).get("video_analyses") or [])[-3:]
                screen_tail = ((session_insights_from_client or {}).get("screen_analyses") or [])[-3:]

            # Keep only lightweight fields
            def slim(items: list):
                out = []
                for it in items:
                    if not isinstance(it, dict):
                        continue
                    out.append({
                        "type": it.get("type"),
                        "timestamp": it.get("timestamp"),
                        "analysis": it.get("analysis"),
                        "insights": it.get("insights"),
                    })
                return out

            # Merge any local (blue box) insights tail to maximize coverage
            try:
                if isinstance(local_insights_tail, list) and local_insights_tail:
                    screen_tail = (screen_tail or []) + [i for i in local_insights_tail if i.get("type") == "screen_analysis"]
                    video_tail = (video_tail or []) + [i for i in local_insights_tail if i.get("type") == "video_analysis"]
            except Exception:
                pass

            if video_tail or screen_tail:
                visual_context = (
                    "Recent Visual Insights (last few):\n" +
                    json.dumps({
                        "video": slim(video_tail),
                        "screen": slim(screen_tail)
                    }, ensure_ascii=False, indent=2) + "\n\n"
                )
        except Exception:
            visual_context = ""
        prompt = (
            f"System:\n{system_preamble}\n\n"
            f"Selected Job (JSON):\n{job_context}\n\n"
            f"Other Jobs (first 10, JSON):\n{jobs_summary}\n\n"
            f"Resume Meta: {json.dumps(resume_meta or {}, ensure_ascii=False)}\n"
            f"Resume Status: {resume_note}\n\n"
            + (f"Resume Text (extracted from PDF):\n{resume_text[:5000]}\n\n" if resume_text else "")
            + visual_context
            + "Conversation so far:\n" +
            "\n".join([f"{m.get('role','user').title()}: {m.get('content','')}" for m in messages]) +
            "\n\nRespond succinctly, cite specific skills/experience from resume when relevant, "
            "and align guidance to the selected job requirements."
        )

        # Call Gemini with optional resume image context
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt
        )

        text = response.text or ""
        return {"reply": text}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"LLM chat failed: {str(e)}")


@router.post("/initialize-interviewer")
async def initialize_interviewer(request: Dict[str, Any]):
    """
    Initialize AI interviewer session
    """
    try:
        job_description = request.get("job_description", "")
        job_title = request.get("job_title", "")
        job_company = request.get("job_company", "")
        job_skills = request.get("job_skills", [])
        resume_base64 = request.get("resume_base64")
        user_id = request.get("user_id", "anonymous")

        # Extract resume text if provided
        resume_text = ""
        if resume_base64:
            try:
                resume_bytes = base64.b64decode(resume_base64)
                pdf_reader = PyPDF2.PdfReader(io.BytesIO(resume_bytes))
                resume_text = "\n".join([page.extract_text() for page in pdf_reader.pages])
            except Exception as e:
                print(f"Failed to extract resume text: {e}")

        # Create system prompt for AI interviewer
        system_prompt = """You are an experienced technical interviewer conducting a 30-minute interview. Your role is to:

1. Ask exactly 5 tailored questions based on the job description and candidate's resume
2. Keep responses short and specific (1-2 sentences max)
3. Create a conversational flow
4. Focus on technical skills, experience, and cultural fit
5. Ask questions one by one dynamically based on responses
6. Be professional but friendly
7. Adapt questions based on candidate's behavior and responses

You will be asked to generate questions one at a time during the interview.
Each question should be tailored to the specific role and candidate profile.
Questions should be appropriate for 30-second responses."""

        # Build context
        job_context = f"""
Job Title: {job_title}
Company: {job_company}
Required Skills: {', '.join(job_skills) if job_skills else 'Not specified'}
Job Description: {job_description[:2000]}
"""

        resume_context = ""
        if resume_text:
            resume_context = f"""
Candidate Resume (first 3000 chars):
{resume_text[:3000]}
"""

        prompt = f"""{system_prompt}

Job Context:
{job_context}

{resume_context}

You are now ready to conduct the interview. Provide a welcoming message to the candidate.
"""

        # Call Gemini
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt
        )

        response_text = response.text or ""
        
        return {
            "ai_response": response_text or f"Hello! I'm your AI interviewer for the {job_title} position at {job_company}. I'll be asking you 5 questions today, each with a 30-second time limit. Let's begin!"
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to initialize interviewer: {str(e)}")


@router.post("/generate-next-question")
async def generate_next_question(request: Dict[str, Any]):
    """
    Generate the next interview question dynamically
    """
    try:
        job_description = request.get("job_description", "")
        job_title = request.get("job_title", "")
        job_company = request.get("job_company", "")
        job_skills = request.get("job_skills", [])
        resume_base64 = request.get("resume_base64")
        user_id = request.get("user_id", "anonymous")
        current_question_index = request.get("current_question_index", 0)
        total_questions = request.get("total_questions", 5)
        previous_questions = request.get("previous_questions", [])
        llm_insights = request.get("llm_insights", [])

        # Extract resume text if provided
        resume_text = ""
        if resume_base64:
            try:
                resume_bytes = base64.b64decode(resume_base64)
                pdf_reader = PyPDF2.PdfReader(io.BytesIO(resume_bytes))
                resume_text = "\n".join([page.extract_text() for page in pdf_reader.pages])
            except Exception as e:
                print(f"Failed to extract resume text: {e}")

        # Create system prompt for dynamic question generation
        system_prompt = f"""You are an experienced technical interviewer conducting a 30-minute interview. 

Current Status:
- Question {current_question_index + 1} of {total_questions}
- Previous questions asked: {previous_questions}

Your task is to generate the next question that:
1. Is tailored to the job role and candidate profile
2. Builds on previous questions (don't repeat)
3. Tests different aspects (technical, behavioral, cultural)
4. Can be answered in 30 seconds
5. Is appropriate for the candidate's experience level
6. Considers any behavioral insights from video/audio analysis

Question categories to cover:
- Technical skills and experience
- Problem-solving abilities
- Cultural fit and motivation
- Career goals and growth
- Specific job-related scenarios

Generate a single, focused question with a brief AI response."""

        # Build context
        job_context = f"""
Job Title: {job_title}
Company: {job_company}
Required Skills: {', '.join(job_skills) if job_skills else 'Not specified'}
Job Description: {job_description[:2000]}
"""

        resume_context = ""
        if resume_text:
            resume_context = f"""
Candidate Resume (first 3000 chars):
{resume_text[:3000]}
"""

        insights_context = ""
        if llm_insights:
            insights_context = f"""
Recent Behavioral Insights:
{json.dumps(llm_insights, indent=2)}
"""

        prompt = f"""{system_prompt}

Job Context:
{job_context}

{resume_context}

{insights_context}

Generate the next interview question. Format your response as JSON:
{{
  "question": "Your question here",
  "category": "Technical/Behavioral/Cultural/Motivational",
  "ai_response": "Brief AI response or transition"
}}"""

        # Call Gemini
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt
        )

        response_text = response.text or ""
        
        # Try to parse JSON response
        try:
            # Extract JSON from response if it's wrapped in markdown
            if "```json" in response_text:
                json_start = response_text.find("```json") + 7
                json_end = response_text.find("```", json_start)
                json_text = response_text[json_start:json_end].strip()
            else:
                json_text = response_text.strip()
            
            parsed_response = json.loads(json_text)
            
            # Ensure we have the right structure
            if "question" not in parsed_response:
                # Fallback questions based on index
                fallback_questions = [
                    "Tell me about yourself and your relevant experience for this role.",
                    f"What interests you most about the {job_title} position at {job_company}?",
                    "Describe a challenging project you've worked on recently and how you overcame obstacles.",
                    "How do you stay updated with the latest technologies and trends in your field?",
                    "Where do you see yourself in 5 years, and how does this role fit into your career goals?"
                ]
                
                parsed_response = {
                    "question": fallback_questions[current_question_index] if current_question_index < len(fallback_questions) else "Do you have any questions for us about the role or company?",
                    "category": "General",
                    "ai_response": "Let's continue with the next question."
                }
            
            return parsed_response
            
        except json.JSONDecodeError:
            # Fallback if JSON parsing fails
            fallback_questions = [
                "Tell me about yourself and your relevant experience for this role.",
                f"What interests you most about the {job_title} position at {job_company}?",
                "Describe a challenging project you've worked on recently and how you overcame obstacles.",
                "How do you stay updated with the latest technologies and trends in your field?",
                "Where do you see yourself in 5 years, and how does this role fit into your career goals?"
            ]
            
            return {
                "question": fallback_questions[current_question_index] if current_question_index < len(fallback_questions) else "Do you have any questions for us about the role or company?",
                "category": "General",
                "ai_response": "Let's continue with the next question."
            }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate next question: {str(e)}")
