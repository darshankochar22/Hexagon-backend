from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
import uuid
from ..core.db import get_db

router = APIRouter()

# Pydantic models
class PollOption(BaseModel):
    id: str
    text: str
    votes: int = 0

class PollCreate(BaseModel):
    question: str
    options: List[str]
    is_active: bool = True

class PollResponse(BaseModel):
    id: str
    question: str
    options: List[PollOption]
    is_active: bool
    created_at: datetime
    total_votes: int = 0

class VoteRequest(BaseModel):
    poll_id: str
    option_id: str

# In-memory storage (in production, use database)
polls_db = {}

@router.post("/create", response_model=PollResponse)
async def create_poll(poll_data: PollCreate, db=Depends(get_db)):
    """Create a new poll with multiple choice options"""
    try:
        poll_id = str(uuid.uuid4())
        
        # Create poll options
        options = []
        for i, option_text in enumerate(poll_data.options):
            option = PollOption(
                id=str(uuid.uuid4()),
                text=option_text,
                votes=0
            )
            options.append(option)
        
        # Create poll
        poll = {
            "id": poll_id,
            "question": poll_data.question,
            "options": [option.dict() for option in options],
            "is_active": poll_data.is_active,
            "created_at": datetime.utcnow(),
            "total_votes": 0
        }
        
        polls_db[poll_id] = poll
        
        return PollResponse(**poll)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create poll: {str(e)}")

@router.get("/", response_model=List[PollResponse])
async def get_all_polls(db=Depends(get_db)):
    """Get all polls"""
    try:
        polls = []
        for poll_data in polls_db.values():
            poll_data["total_votes"] = sum(option["votes"] for option in poll_data["options"])
            polls.append(PollResponse(**poll_data))
        
        return polls
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get polls: {str(e)}")

@router.get("/active", response_model=List[PollResponse])
async def get_active_polls(db=Depends(get_db)):
    """Get all active polls"""
    try:
        active_polls = []
        for poll_data in polls_db.values():
            if poll_data["is_active"]:
                poll_data["total_votes"] = sum(option["votes"] for option in poll_data["options"])
                active_polls.append(PollResponse(**poll_data))
        
        return active_polls
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get active polls: {str(e)}")

@router.get("/{poll_id}", response_model=PollResponse)
async def get_poll(poll_id: str, db=Depends(get_db)):
    """Get a specific poll by ID"""
    try:
        if poll_id not in polls_db:
            raise HTTPException(status_code=404, detail="Poll not found")
        
        poll_data = polls_db[poll_id]
        poll_data["total_votes"] = sum(option["votes"] for option in poll_data["options"])
        
        return PollResponse(**poll_data)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get poll: {str(e)}")

@router.post("/vote")
async def vote_on_poll(vote_data: VoteRequest, db=Depends(get_db)):
    """Vote on a poll option"""
    try:
        poll_id = vote_data.poll_id
        option_id = vote_data.option_id
        
        if poll_id not in polls_db:
            raise HTTPException(status_code=404, detail="Poll not found")
        
        poll = polls_db[poll_id]
        
        if not poll["is_active"]:
            raise HTTPException(status_code=400, detail="Poll is not active")
        
        # Find and update the option
        option_found = False
        for option in poll["options"]:
            if option["id"] == option_id:
                option["votes"] += 1
                option_found = True
                break
        
        if not option_found:
            raise HTTPException(status_code=404, detail="Option not found")
        
        # Update total votes
        poll["total_votes"] = sum(option["votes"] for option in poll["options"])
        
        return {"message": "Vote recorded successfully", "total_votes": poll["total_votes"]}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to vote: {str(e)}")

@router.put("/{poll_id}/toggle")
async def toggle_poll_status(poll_id: str, db=Depends(get_db)):
    """Toggle poll active status"""
    try:
        if poll_id not in polls_db:
            raise HTTPException(status_code=404, detail="Poll not found")
        
        poll = polls_db[poll_id]
        poll["is_active"] = not poll["is_active"]
        
        return {"message": f"Poll {'activated' if poll['is_active'] else 'deactivated'}", "is_active": poll["is_active"]}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to toggle poll: {str(e)}")

@router.delete("/{poll_id}")
async def delete_poll(poll_id: str, db=Depends(get_db)):
    """Delete a poll"""
    try:
        if poll_id not in polls_db:
            raise HTTPException(status_code=404, detail="Poll not found")
        
        del polls_db[poll_id]
        
        return {"message": "Poll deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete poll: {str(e)}")

@router.get("/{poll_id}/results")
async def get_poll_results(poll_id: str, db=Depends(get_db)):
    """Get detailed poll results"""
    try:
        if poll_id not in polls_db:
            raise HTTPException(status_code=404, detail="Poll not found")
        
        poll = polls_db[poll_id]
        total_votes = sum(option["votes"] for option in poll["options"])
        
        results = {
            "poll_id": poll_id,
            "question": poll["question"],
            "total_votes": total_votes,
            "options": []
        }
        
        for option in poll["options"]:
            percentage = (option["votes"] / total_votes * 100) if total_votes > 0 else 0
            results["options"].append({
                "id": option["id"],
                "text": option["text"],
                "votes": option["votes"],
                "percentage": round(percentage, 1)
            })
        
        return results
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get poll results: {str(e)}")
