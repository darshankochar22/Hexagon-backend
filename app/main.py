from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routers import auth, users, polls

app = FastAPI(title="Hexagon API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(users.router, prefix="/users", tags=["users"])
app.include_router(polls.router, prefix="/polls", tags=["polls"])

@app.get("/")
def root():
    return {"status": "ok"}
