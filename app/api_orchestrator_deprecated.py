from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from typing import Dict
import uuid

from app.agents.helfo_validator.orchestrator import HelFoAgentOrchestrator, SESSION_STORE

router = APIRouter()
agent_orchestrator = HelFoAgentOrchestrator()


# ----------------------------
# Start workflow with SOAP note (stops at first missing info)
# ----------------------------
@router.post("/submit_soap")
async def submit_soap(soap_text: str):
    session_id = str(uuid.uuid4())
    try:
        output = agent_orchestrator.start_flow(soap_text, session_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Workflow failed: {e}")

    state = SESSION_STORE.get(session_id)
    return JSONResponse(
        content={
            "session_id": session_id,
            "question": getattr(state, "question", None),
            "waiting_for_user": getattr(state, "waiting_for_user", False),
            "predicted_service_codes": [sc.dict() for sc in getattr(state, "predicted_service_codes", [])],
            "reasoning_trail": getattr(state, "reasoning_trail", []),
        }
    )


# ----------------------------
# Submit user responses and continue workflow
# ----------------------------
@router.post("/respond")
async def respond(session_id: str, responses: Dict[str, str]):
    state = SESSION_STORE.get(session_id)
    if not state:
        raise HTTPException(status_code=404, detail="Session not found")

    try:
        output = agent_orchestrator.resume_flow(session_id, responses)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Workflow resume failed: {e}")

    state = SESSION_STORE.get(session_id)
    return JSONResponse(
        content={
            "session_id": session_id,
            "question": getattr(state, "question", None),
            "waiting_for_user": getattr(state, "waiting_for_user", False),
            "predicted_service_codes": [sc.dict() for sc in getattr(state, "predicted_service_codes", [])],
            "reasoning_trail": getattr(state, "reasoning_trail", []),
        }
    )


# ----------------------------
# Get current session state
# ----------------------------
@router.get("/state/{session_id}")
async def get_state(session_id: str):
    state = SESSION_STORE.get(session_id)
    if not state:
        raise HTTPException(status_code=404, detail="Session not found")

    return JSONResponse(
        content={
            "session_id": session_id,
            "soap_text": getattr(state, "soap_text", ""),
            "question": getattr(state, "question", None),
            "waiting_for_user": getattr(state, "waiting_for_user", False),
            "predicted_service_codes": [sc.dict() for sc in getattr(state, "predicted_service_codes", [])],
            "reasoning_trail": getattr(state, "reasoning_trail", []),
            "loop_count": getattr(state, "loop_count", 0),
            "max_loops": getattr(state, "max_loops", 5),
        }
    )
