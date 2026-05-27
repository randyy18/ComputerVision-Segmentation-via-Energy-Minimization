"""GrabCut interactive web demo — FastAPI application."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routes import leaderboard, sessions

app = FastAPI(title="GrabCut Demo API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(sessions.router)
app.include_router(leaderboard.router)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
