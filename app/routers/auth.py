from datetime import datetime, timedelta
from typing import Optional
import os
import glob
import json
from dotenv import load_dotenv

from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.responses import RedirectResponse
import jwt
import requests
from ..core.db import get_db
from fastapi import BackgroundTasks

# Load environment variables from .env file
load_dotenv()

JWT_SECRET = "dev-secret-change"  # TODO: load from env
JWT_ALG = "HS256"

router = APIRouter()


def create_token(sub: str, expires_minutes: int = 60) -> str:
    now = datetime.utcnow()
    payload = {"sub": sub, "iat": now, "exp": now + timedelta(minutes=expires_minutes)}
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALG)


def verify_token(token: str) -> Optional[str]:
    try:
        data = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG])
        return data.get("sub")
    except Exception:
        return None


@router.post("/login")
async def login(form: OAuth2PasswordRequestForm = Depends(), db=Depends(get_db)):
    # Very basic: if user exists, issue token; else reject
    user = await db.users.find_one({"username": form.username})
    if not user:
        raise HTTPException(400, detail="Invalid credentials")
    # NOTE: For brevity we are not hashing here; replace with hashed pw check
    token = create_token(sub=form.username)
    return {"access_token": token, "token_type": "bearer"}


@router.post("/signup")
async def signup(username: str, password: str, db=Depends(get_db)):
    existing = await db.users.find_one({"username": username})
    if existing:
        raise HTTPException(400, detail="User already exists")
    await db.users.insert_one({"username": username, "password": password, "provider": "local"})
    token = create_token(sub=username)
    return {"access_token": token, "token_type": "bearer"}


# --- Google OAuth (simple) ---
GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "")
BACKEND_BASE_URL = os.environ.get("BACKEND_BASE_URL", "http://localhost:8000")
FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://localhost:5173")
GOOGLE_REDIRECT_URI = os.environ.get("GOOGLE_REDIRECT_URI", f"{BACKEND_BASE_URL}/auth/google/callback")

# Fallback: read Google client JSON placed in backend/ if env not provided
if not (GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET):
    try:
        candidates = glob.glob(os.path.join(os.path.dirname(__file__), "..", "..", "client_secret_*.json"))
        if not candidates:
            candidates = glob.glob(os.path.join(os.path.dirname(__file__), "..", "..", "*.json"))
        for path in candidates:
            with open(path, "r") as f:
                data = json.load(f)
                web = data.get("web") or {}
                GOOGLE_CLIENT_ID = GOOGLE_CLIENT_ID or web.get("client_id", "")
                GOOGLE_CLIENT_SECRET = GOOGLE_CLIENT_SECRET or web.get("client_secret", "")
                # Try to infer redirect
                if not os.environ.get("GOOGLE_REDIRECT_URI"):
                    GOOGLE_REDIRECT_URI = f"{BACKEND_BASE_URL}/auth/google/callback"
                break
    except Exception:
        pass


@router.get("/google/url")
def google_url():
    if not GOOGLE_CLIENT_ID:
        raise HTTPException(500, detail="Google OAuth not configured")
    scope = "openid email profile"
    url = (
        "https://accounts.google.com/o/oauth2/v2/auth?"
        f"client_id={GOOGLE_CLIENT_ID}&"
        f"redirect_uri={GOOGLE_REDIRECT_URI}&"
        "response_type=code&"
        f"scope={requests.utils.quote(scope)}&"
        "include_granted_scopes=true&"
        "prompt=consent"
    )
    return RedirectResponse(url)


@router.get("/google/callback")
async def google_callback(code: str, db=Depends(get_db)):
    if not (GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET):
        raise HTTPException(500, detail="Google OAuth not configured")
    # exchange code
    token_res = requests.post(
        "https://oauth2.googleapis.com/token",
        data={
            "code": code,
            "client_id": GOOGLE_CLIENT_ID,
            "client_secret": GOOGLE_CLIENT_SECRET,
            "redirect_uri": GOOGLE_REDIRECT_URI,
            "grant_type": "authorization_code",
        },
        timeout=15,
    )
    if token_res.status_code != 200:
        raise HTTPException(400, detail="Google token exchange failed")
    token_json = token_res.json()
    id_token = token_json.get("id_token")
    email = None
    if id_token:
        info_res = requests.get(
            "https://www.googleapis.com/oauth2/v3/tokeninfo",
            params={"id_token": id_token},
            timeout=15,
        )
        if info_res.status_code == 200:
            email = info_res.json().get("email")

    sub = email or "google_user"
    # upsert user
    await db.users.update_one({"username": sub}, {"$set": {"username": sub, "provider": "google"}}, upsert=True)
    jwt_token = create_token(sub=sub)
    # redirect back to frontend with token
    return RedirectResponse(f"{FRONTEND_URL}/login?token={jwt_token}")
