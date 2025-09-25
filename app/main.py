from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import socketio

from .routers import auth, users, webrtc

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
app.include_router(webrtc.router, prefix="/webrtc", tags=["webrtc"])

# Add Socket.IO to the app
sio = webrtc.get_socket_server()
socket_app = socketio.ASGIApp(sio, app)

@app.get("/")
def root():
    return {"status": "ok"}
