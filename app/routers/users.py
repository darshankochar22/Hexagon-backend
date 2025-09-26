from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel
from typing import Optional
import jwt
import base64
import os
from datetime import datetime
from ..core.db import get_db

JWT_SECRET = "dev-secret-change"
JWT_ALG = "HS256"

router = APIRouter()
bearer = HTTPBearer(auto_error=False)


class ProfileUpdate(BaseModel):
    email: Optional[str] = None
    full_name: Optional[str] = None
    avatar: Optional[str] = None
    bio: Optional[str] = None
    location: Optional[str] = None
    website: Optional[str] = None
    phone: Optional[str] = None
    resume: Optional[str] = None


def get_current_user(creds: HTTPAuthorizationCredentials = Depends(bearer)):
    if not creds:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        data = jwt.decode(creds.credentials, JWT_SECRET, algorithms=[JWT_ALG])
        return data.get("sub")
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")


@router.get("/me")
async def me(user: str = Depends(get_current_user), db=Depends(get_db)):
    # Fetch complete user details from database
    user_data = await db.users.find_one({"username": user})
    if not user_data:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Remove sensitive data and return user profile
    user_data.pop("password", None)
    user_data.pop("_id", None)
    
    return {
        "username": user_data.get("username"),
        "provider": user_data.get("provider", "local"),
        "created_at": user_data.get("created_at"),
        "profile": {
            "email": user_data.get("email", user_data.get("username")),
            "full_name": user_data.get("full_name", ""),
            "avatar": user_data.get("avatar", ""),
            "bio": user_data.get("bio", ""),
            "location": user_data.get("location", ""),
            "website": user_data.get("website", ""),
            "phone": user_data.get("phone", ""),
            "resume": user_data.get("resume", ""),
        }
    }


@router.put("/me")
async def update_profile(
    profile_data: ProfileUpdate,
    user: str = Depends(get_current_user),
    db=Depends(get_db)
):
    # Build update document with only provided fields
    update_fields = {}
    
    if profile_data.email is not None:
        update_fields["email"] = profile_data.email
    if profile_data.full_name is not None:
        update_fields["full_name"] = profile_data.full_name
    if profile_data.avatar is not None:
        update_fields["avatar"] = profile_data.avatar
    if profile_data.bio is not None:
        update_fields["bio"] = profile_data.bio
    if profile_data.location is not None:
        update_fields["location"] = profile_data.location
    if profile_data.website is not None:
        update_fields["website"] = profile_data.website
    if profile_data.phone is not None:
        update_fields["phone"] = profile_data.phone
    if profile_data.resume is not None:
        update_fields["resume"] = profile_data.resume
    
    if not update_fields:
        raise HTTPException(status_code=400, detail="No fields to update")
    
    # Update user document
    result = await db.users.update_one(
        {"username": user},
        {"$set": update_fields}
    )
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Return updated user data
    updated_user = await db.users.find_one({"username": user})
    if not updated_user:
        raise HTTPException(status_code=404, detail="User not found after update")
    
    # Remove sensitive data and return updated profile
    updated_user.pop("password", None)
    updated_user.pop("_id", None)
    
    return {
        "username": updated_user.get("username"),
        "provider": updated_user.get("provider", "local"),
        "created_at": updated_user.get("created_at"),
        "profile": {
            "email": updated_user.get("email", updated_user.get("username")),
            "full_name": updated_user.get("full_name", ""),
            "avatar": updated_user.get("avatar", ""),
            "bio": updated_user.get("bio", ""),
            "location": updated_user.get("location", ""),
            "website": updated_user.get("website", ""),
            "phone": updated_user.get("phone", ""),
            "resume": updated_user.get("resume", ""),
        }
    }


@router.post("/upload-resume")
async def upload_resume(
    file: UploadFile = File(...),
    user: str = Depends(get_current_user),
    db=Depends(get_db)
):
    """Upload resume file for the current user"""
    
    # Check file type
    if not file.filename.lower().endswith(('.pdf', '.doc', '.docx')):
        raise HTTPException(status_code=400, detail="Only PDF, DOC, and DOCX files are allowed")
    
    # Check file size (max 10MB)
    file_content = await file.read()
    if len(file_content) > 10 * 1024 * 1024:  # 10MB
        raise HTTPException(status_code=400, detail="File size too large. Maximum size is 10MB")
    
    try:
        # Convert file to base64 for storage
        file_base64 = base64.b64encode(file_content).decode('utf-8')
        
        # Create resume data
        resume_data = {
            "filename": file.filename,
            "content_type": file.content_type,
            "file_size": len(file_content),
            "uploaded_at": datetime.utcnow().isoformat(),
            "file_data": file_base64
        }
        
        # Update user document with resume
        result = await db.users.update_one(
            {"username": user},
            {"$set": {"resume": resume_data}}
        )
        
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="User not found")
        
        return {
            "message": "Resume uploaded successfully",
            "filename": file.filename,
            "file_size": len(file_content),
            "uploaded_at": resume_data["uploaded_at"]
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error uploading resume: {str(e)}")


@router.get("/download-resume")
async def download_resume(
    user: str = Depends(get_current_user),
    db=Depends(get_db)
):
    """Download the current user's resume"""
    
    user_data = await db.users.find_one({"username": user})
    if not user_data:
        raise HTTPException(status_code=404, detail="User not found")
    
    resume_data = user_data.get("resume")
    if not resume_data:
        raise HTTPException(status_code=404, detail="No resume found")
    
    try:
        # Decode base64 file data
        file_content = base64.b64decode(resume_data["file_data"])
        
        from fastapi.responses import Response
        
        return Response(
            content=file_content,
            media_type=resume_data["content_type"],
            headers={
                "Content-Disposition": f"attachment; filename={resume_data['filename']}"
            }
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error downloading resume: {str(e)}")


@router.delete("/delete-resume")
async def delete_resume(
    user: str = Depends(get_current_user),
    db=Depends(get_db)
):
    """Delete the current user's resume"""
    
    result = await db.users.update_one(
        {"username": user},
        {"$unset": {"resume": ""}}
    )
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="User not found")
    
    return {"message": "Resume deleted successfully"}
