"""FastAPI application - REST and WebSocket endpoints."""

from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.routes import scoring, sessions, simulation

logger = structlog.get_logger()

# In-memory session store (replace with DB in production)
active_sessions: dict = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("application_starting")
    yield
    # Cleanup: stop all running simulations
    for session_id, runner in active_sessions.items():
        await runner.stop()
    logger.info("application_stopped")


app = FastAPI(
    title="防災訓練自動化システム",
    description="AI Agent-based Disaster Training Simulation",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(sessions.router, prefix="/api", tags=["sessions"])
app.include_router(simulation.router, prefix="/api", tags=["simulation"])
app.include_router(scoring.router, prefix="/api", tags=["scoring"])


@app.get("/api/health")
async def health():
    return {"status": "ok", "active_sessions": len(active_sessions)}
