from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import JSONResponse
from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel
import motor.motor_asyncio
import os
from bson import ObjectId

router = APIRouter()

# MongoDB connection
MONGODB_URL = os.getenv("MONGODB_URL", "mongodb://localhost:27017")
client = motor.motor_asyncio.AsyncIOMotorClient(MONGODB_URL)
db = client.hexagon
jobs_collection = db.jobs

# Pydantic models
class JobCreate(BaseModel):
    title: str
    company: str
    location: str
    experience: str
    skills: List[str]
    description: str
    user_id: str

class JobUpdate(BaseModel):
    title: Optional[str] = None
    company: Optional[str] = None
    location: Optional[str] = None
    experience: Optional[str] = None
    skills: Optional[List[str]] = None
    description: Optional[str] = None

class Job(BaseModel):
    id: str
    title: str
    company: str
    location: str
    experience: str
    skills: List[str]
    description: str
    user_id: str
    created_at: datetime
    updated_at: datetime

# Helper function to convert ObjectId to string
def job_helper(job) -> dict:
    return {
        "id": str(job["_id"]),
        "title": job["title"],
        "company": job["company"],
        "location": job["location"],
        "experience": job["experience"],
        "skills": job["skills"],
        "description": job["description"],
        "user_id": job["user_id"],
        "created_at": job["created_at"],
        "updated_at": job["updated_at"]
    }

@router.get("/", response_model=List[Job])
async def get_jobs(user_id: Optional[str] = None, skip: int = 0, limit: int = 100):
    """Get all jobs, optionally filtered by user_id"""
    try:
        query = {}
        if user_id:
            query["user_id"] = user_id
        
        cursor = jobs_collection.find(query).skip(skip).limit(limit).sort("created_at", -1)
        jobs = []
        
        async for job in cursor:
            jobs.append(job_helper(job))
        
        return jobs
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching jobs: {str(e)}")

@router.get("/{job_id}", response_model=Job)
async def get_job(job_id: str):
    """Get a specific job by ID"""
    try:
        job = await jobs_collection.find_one({"_id": ObjectId(job_id)})
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        
        return job_helper(job)
    except Exception as e:
        if "not found" in str(e):
            raise HTTPException(status_code=404, detail="Job not found")
        raise HTTPException(status_code=500, detail=f"Error fetching job: {str(e)}")

@router.post("/", response_model=Job)
async def create_job(job_data: JobCreate):
    """Create a new job"""
    try:
        job_dict = job_data.dict()
        job_dict["created_at"] = datetime.utcnow()
        job_dict["updated_at"] = datetime.utcnow()
        
        result = await jobs_collection.insert_one(job_dict)
        
        # Fetch the created job
        created_job = await jobs_collection.find_one({"_id": result.inserted_id})
        return job_helper(created_job)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating job: {str(e)}")

@router.put("/{job_id}", response_model=Job)
async def update_job(job_id: str, job_data: JobUpdate):
    """Update a job"""
    try:
        update_dict = {k: v for k, v in job_data.dict().items() if v is not None}
        if not update_dict:
            raise HTTPException(status_code=400, detail="No fields to update")
        
        update_dict["updated_at"] = datetime.utcnow()
        
        result = await jobs_collection.update_one(
            {"_id": ObjectId(job_id)},
            {"$set": update_dict}
        )
        
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Job not found")
        
        # Fetch the updated job
        updated_job = await jobs_collection.find_one({"_id": ObjectId(job_id)})
        return job_helper(updated_job)
        
    except Exception as e:
        if "not found" in str(e):
            raise HTTPException(status_code=404, detail="Job not found")
        raise HTTPException(status_code=500, detail=f"Error updating job: {str(e)}")

@router.delete("/{job_id}")
async def delete_job(job_id: str):
    """Delete a job"""
    try:
        result = await jobs_collection.delete_one({"_id": ObjectId(job_id)})
        
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Job not found")
        
        return {"message": "Job deleted successfully"}
        
    except Exception as e:
        if "not found" in str(e):
            raise HTTPException(status_code=404, detail="Job not found")
        raise HTTPException(status_code=500, detail=f"Error deleting job: {str(e)}")

@router.get("/user/{user_id}", response_model=List[Job])
async def get_jobs_by_user(user_id: str, skip: int = 0, limit: int = 100):
    """Get all jobs for a specific user"""
    try:
        cursor = jobs_collection.find({"user_id": user_id}).skip(skip).limit(limit).sort("created_at", -1)
        jobs = []
        
        async for job in cursor:
            jobs.append(job_helper(job))
        
        return jobs
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching user jobs: {str(e)}")

@router.get("/search/", response_model=List[Job])
async def search_jobs(
    q: Optional[str] = None,
    experience: Optional[str] = None,
    location: Optional[str] = None,
    skip: int = 0,
    limit: int = 100
):
    """Search jobs with filters"""
    try:
        query = {}
        
        if q:
            query["$or"] = [
                {"title": {"$regex": q, "$options": "i"}},
                {"company": {"$regex": q, "$options": "i"}},
                {"skills": {"$regex": q, "$options": "i"}}
            ]
        
        if experience:
            query["experience"] = {"$regex": experience, "$options": "i"}
        
        if location:
            query["location"] = {"$regex": location, "$options": "i"}
        
        cursor = jobs_collection.find(query).skip(skip).limit(limit).sort("created_at", -1)
        jobs = []
        
        async for job in cursor:
            jobs.append(job_helper(job))
        
        return jobs
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error searching jobs: {str(e)}")

@router.post("/bulk", response_model=List[Job])
async def create_bulk_jobs(jobs_data: List[JobCreate]):
    """Create multiple jobs at once"""
    try:
        jobs_list = []
        current_time = datetime.utcnow()
        
        for job_data in jobs_data.dict():
            job_dict = job_data
            job_dict["created_at"] = current_time
            job_dict["updated_at"] = current_time
            jobs_list.append(job_dict)
        
        result = await jobs_collection.insert_many(jobs_list)
        
        # Fetch the created jobs
        created_jobs = []
        for inserted_id in result.inserted_ids:
            job = await jobs_collection.find_one({"_id": inserted_id})
            created_jobs.append(job_helper(job))
        
        return created_jobs
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating bulk jobs: {str(e)}")

@router.get("/stats/overview")
async def get_job_stats():
    """Get job statistics overview"""
    try:
        total_jobs = await jobs_collection.count_documents({})
        
        # Count by experience level
        experience_stats = {}
        experience_levels = ["entry", "mid", "senior"]
        
        for level in experience_levels:
            count = await jobs_collection.count_documents({"experience": {"$regex": level, "$options": "i"}})
            experience_stats[level] = count
        
        # Count by location (top 10)
        pipeline = [
            {"$group": {"_id": "$location", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
            {"$limit": 10}
        ]
        
        location_stats = []
        async for doc in jobs_collection.aggregate(pipeline):
            location_stats.append({"location": doc["_id"], "count": doc["count"]})
        
        return {
            "total_jobs": total_jobs,
            "experience_distribution": experience_stats,
            "top_locations": location_stats
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching job stats: {str(e)}")
