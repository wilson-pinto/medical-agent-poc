# app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Unified API router
from app.api import router as api_router

app = FastAPI(
    title="Norwegian GP Agentic AI",
    description="Agentic AI for HELFO billing code prediction, SOAP validation, and workflow guidance.",
    version="1.0.0"
)

# ----------------------------
# CORS (optional for front-end integration)
# ----------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # allow all origins for hackathon
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ----------------------------
# Include unified API router
# ----------------------------
app.include_router(api_router, prefix="/api", tags=["agentic"])

# ----------------------------
# Root endpoint
# ----------------------------
@app.get("/")
def root():
    return {"message": "Healthcare Agentic AI is live and judge-ready!"}

# ----------------------------
# Startup logging
# ----------------------------
@app.on_event("startup")
def startup_event():
    print("=== Norwegian GP Agentic AI is up and running! ===")
