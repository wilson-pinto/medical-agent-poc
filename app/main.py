# app/main.py
import os
import redis
from typing import Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

# Import the unified API router
from app.api import router as api_router
from app.agents.helfo_validator.orchestrator import HelFoAgentOrchestrator


app = FastAPI(
    title="Norwegian GP Agentic AI",
    description="Agentic AI for HELFO billing code prediction, SOAP validation, and workflow guidance.",
    version="1.0.0"
)

# Global Redis client instance
redis_client: Optional[redis.Redis] = None

# Global orchestrator instance initialized later with the Redis client
agent_orchestrator: Optional[HelFoAgentOrchestrator] = None

# ----------------------------
# CORS
# ----------------------------
app.add_middleware(
    CORSMiddleware,
    # Be more specific with the origin to avoid conflicts with allow_credentials
    allow_origins=["http://localhost:8000", "http://127.0.0.1:8000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ----------------------------
# Mount unified API router and WebSocket router
# ----------------------------
app.include_router(api_router, prefix="/api", tags=["agentic"])
app.include_router(api_router, prefix="/ws", tags=["websocket"])


# ----------------------------
# Serve static frontend for demo
# ----------------------------
app.mount("/static", StaticFiles(directory="frontend"), name="static")


# ----------------------------
# Root endpoint
# ----------------------------
@app.get("/")
def root():
    return {"message": "Healthcare Agentic AI is live and judge-ready!"}


# ----------------------------
# Startup and Shutdown events
# ----------------------------
@app.on_event("startup")
def startup_event():
    """
    Initializes the Redis client and the Agent Orchestrator.
    """
    global redis_client, agent_orchestrator
    print("=== Norwegian GP Agentic AI is up and running! ===")

    try:
        redis_client = redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"))
        redis_client.ping()
        print("Connected to Redis successfully!")
    except redis.exceptions.ConnectionError as e:
        print(f"Failed to connect to Redis: {e}")
        redis_client = None

    agent_orchestrator = HelFoAgentOrchestrator(redis_client=redis_client)


@app.on_event("shutdown")
def shutdown_event():
    """
    Closes the Redis connection on shutdown.
    """
    if redis_client:
        redis_client.close()
        print("Disconnected from Redis.")
