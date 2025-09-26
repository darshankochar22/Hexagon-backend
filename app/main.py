from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routers import auth, users, polls, media, llm_processor, pdf_processor, voice_feedback, jobs

app = FastAPI(title="Professional Interview System API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "https://hexagon-eran.vercel.app"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(users.router, prefix="/users", tags=["users"])
app.include_router(polls.router, prefix="/polls", tags=["polls"])
app.include_router(media.router, prefix="/media", tags=["media"])
app.include_router(llm_processor.router, prefix="/media", tags=["analysis"])
app.include_router(pdf_processor.router, prefix="/interview", tags=["interview-prep"])
app.include_router(voice_feedback.router, prefix="/interview", tags=["voice-feedback"])
app.include_router(jobs.router, prefix="/jobs", tags=["jobs"])

@app.get("/")
def root():
    return {"status": "ok"}
