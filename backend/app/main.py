from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .config import settings

import logging
from contextlib import asynccontextmanager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("lenny_assistant")

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"Lenny Growth Assistant backend started. Provider: {settings.MODEL_PROVIDER}")
    yield
    logger.info("Lenny Growth Assistant backend shutting down.")

app = FastAPI(
    title="The Lenny Growth Assistant",
    description="Backend API for the Lenny Growth Assistant",
    version="0.1.0",
    lifespan=lifespan
)

# CORS setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify exact origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from app.api import sessions
from app.api import knowledge
from app.api import artifacts
app.include_router(sessions.router, prefix="/api/sessions", tags=["sessions"])
app.include_router(knowledge.router, prefix="/api/knowledge", tags=["knowledge"])
app.include_router(artifacts.router, prefix="/api/artifacts", tags=["artifacts"])


from sqlalchemy.orm import Session
from sqlalchemy import text
from app.db.session import get_db
from fastapi import Depends

import httpx

@app.get("/health")
async def health_check(db: Session = Depends(get_db)):
    db_status = "connected"
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        db_status = "unhealthy"

    provider = settings.MODEL_PROVIDER.lower()
    ollama_status = "not_applicable"

    if provider == "ollama":
        try:
            # Quick ping to local Ollama with a 1.5-second timeout
            with httpx.Client(timeout=1.5) as client:
                res = client.get(f"{settings.OLLAMA_BASE_URL}/api/tags")
                ollama_status = "reachable" if res.status_code == 200 else "unreachable"
        except Exception:
            ollama_status = "unreachable"

    is_healthy = db_status == "connected" and (
        ollama_status != "unreachable" if provider == "ollama" else True
    )

    return {
        "status": "healthy" if is_healthy else "degraded",
        "database": db_status,
        "provider": provider,
        "ollama": ollama_status,
    }
