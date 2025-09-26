from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse
import PyPDF2
import io
import json
from typing import Dict, Any
import google.generativeai as genai
import os

router = APIRouter()

# Configure Gemini
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "your-gemini-api-key")
genai.configure(api_key=GEMINI_API_KEY)
gemini_model = genai.GenerativeModel('gemini-2.0-flash-exp')

async def extract_text_from_pdf(pdf_file: bytes) -> str:
    """Extract text from PDF file"""
    try:
        pdf_reader = PyPDF2.PdfReader(io.BytesIO(pdf_file))
        text = ""
        for page in pdf_reader.pages:
            text += page.extract_text() + "\n"
        return text.strip()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error extracting PDF text: {str(e)}")

async def analyze_job_description(job_text: str) -> Dict[str, Any]:
    """Analyze job description and extract key requirements"""
    try:
        prompt = f"""
        Analyze this job description and extract key information:
        
        {job_text}
        
        Please provide a structured analysis with:
        1. Job Title
        2. Company/Organization
        3. Key Skills Required (list)
        4. Experience Level (entry/mid/senior)
        5. Key Responsibilities (list)
        6. Preferred Qualifications (list)
        7. Industry/Department
        8. Location (if mentioned)
        9. Salary Range (if mentioned)
        10. Interview Focus Areas (what to assess in interviews)
        
        Format as JSON.
        """
        
        response = await gemini_model.generate_content_async(prompt)
        
        try:
            analysis = json.loads(response.text)
            return analysis
        except json.JSONDecodeError:
            # Fallback to structured text
            return {
                "raw_analysis": response.text,
                "job_title": "Unknown",
                "skills_required": [],
                "experience_level": "Unknown",
                "responsibilities": [],
                "interview_focus": []
            }
            
    except Exception as e:
        return {"error": f"Analysis failed: {str(e)}"}

async def analyze_resume(resume_text: str) -> Dict[str, Any]:
    """Analyze resume and extract candidate information"""
    try:
        prompt = f"""
        Analyze this resume and extract key information:
        
        {resume_text}
        
        Please provide a structured analysis with:
        1. Candidate Name
        2. Contact Information
        3. Professional Summary
        4. Skills (list)
        5. Work Experience (list with years)
        6. Education
        7. Certifications (if any)
        8. Years of Experience
        9. Key Strengths
        10. Potential Areas for Discussion
        
        Format as JSON.
        """
        
        response = await gemini_model.generate_content_async(prompt)
        
        try:
            analysis = json.loads(response.text)
            return analysis
        except json.JSONDecodeError:
            # Fallback to structured text
            return {
                "raw_analysis": response.text,
                "candidate_name": "Unknown",
                "skills": [],
                "experience_years": 0,
                "strengths": [],
                "discussion_areas": []
            }
            
    except Exception as e:
        return {"error": f"Analysis failed: {str(e)}"}

async def generate_interview_questions(job_analysis: Dict[str, Any], resume_analysis: Dict[str, Any]) -> Dict[str, Any]:
    """Generate tailored interview questions based on job and resume analysis"""
    try:
        prompt = f"""
        Based on this job description analysis:
        {json.dumps(job_analysis, indent=2)}
        
        And this candidate resume analysis:
        {json.dumps(resume_analysis, indent=2)}
        
        Generate a comprehensive interview plan with:
        1. Opening Questions (3-4 questions)
        2. Technical Questions (5-6 questions based on required skills)
        3. Behavioral Questions (4-5 questions)
        4. Scenario-based Questions (3-4 questions)
        5. Closing Questions (2-3 questions)
        6. Key Areas to Assess (list)
        7. Red Flags to Watch For (list)
        8. Follow-up Questions (based on responses)
        
        Format as JSON with each question having: question, category, difficulty, expected_answer_focus
        """
        
        response = await gemini_model.generate_content_async(prompt)
        
        try:
            questions = json.loads(response.text)
            return questions
        except json.JSONDecodeError:
            return {
                "raw_questions": response.text,
                "opening_questions": [],
                "technical_questions": [],
                "behavioral_questions": [],
                "assessment_areas": []
            }
            
    except Exception as e:
        return {"error": f"Question generation failed: {str(e)}"}

@router.post("/upload/job-description")
async def upload_job_description(file: UploadFile = File(...)):
    """Upload and analyze job description PDF"""
    try:
        if not file.filename.endswith('.pdf'):
            raise HTTPException(status_code=400, detail="Only PDF files are allowed")
        
        # Read file content
        content = await file.read()
        
        # Extract text
        job_text = await extract_text_from_pdf(content)
        
        # Analyze job description
        analysis = await analyze_job_description(job_text)
        
        return JSONResponse({
            "status": "success",
            "filename": file.filename,
            "analysis": analysis,
            "raw_text": job_text[:500] + "..." if len(job_text) > 500 else job_text
        })
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/upload/resume")
async def upload_resume(file: UploadFile = File(...)):
    """Upload and analyze resume PDF"""
    try:
        if not file.filename.endswith('.pdf'):
            raise HTTPException(status_code=400, detail="Only PDF files are allowed")
        
        # Read file content
        content = await file.read()
        
        # Extract text
        resume_text = await extract_text_from_pdf(content)
        
        # Analyze resume
        analysis = await analyze_resume(resume_text)
        
        return JSONResponse({
            "status": "success",
            "filename": file.filename,
            "analysis": analysis,
            "raw_text": resume_text[:500] + "..." if len(resume_text) > 500 else resume_text
        })
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/generate-interview-plan")
async def generate_interview_plan(job_analysis: Dict[str, Any], resume_analysis: Dict[str, Any]):
    """Generate interview questions based on job and resume analysis"""
    try:
        questions = await generate_interview_questions(job_analysis, resume_analysis)
        
        return JSONResponse({
            "status": "success",
            "interview_plan": questions
        })
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/interview-templates")
async def get_interview_templates():
    """Get common interview question templates"""
    templates = {
        "opening_questions": [
            "Tell me about yourself and your background.",
            "What interests you most about this position?",
            "Why are you looking for a new opportunity?",
            "What do you know about our company?"
        ],
        "technical_questions": [
            "Walk me through your experience with [specific technology].",
            "How would you approach solving [technical problem]?",
            "Describe a challenging technical project you worked on.",
            "What's your experience with [relevant tool/framework]?"
        ],
        "behavioral_questions": [
            "Tell me about a time you faced a difficult challenge at work.",
            "Describe a situation where you had to work with a difficult team member.",
            "Give me an example of a project where you had to learn something new quickly.",
            "Tell me about a time you had to meet a tight deadline."
        ],
        "closing_questions": [
            "Do you have any questions about the role or company?",
            "What are your salary expectations?",
            "When would you be available to start?",
            "Is there anything else you'd like us to know about you?"
        ]
    }
    
    return JSONResponse({
        "status": "success",
        "templates": templates
    })
