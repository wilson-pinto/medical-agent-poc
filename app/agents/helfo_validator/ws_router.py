# app/agents/helfo_validator/ws_router.py
import asyncio
import uuid
import os
import json
from typing import List, Dict, Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import JSONResponse

from app.agents.helfo_validator.orchestrator import HelFoAgentOrchestrator, SESSION_STORE
from app.schemas_new.agentic_state import RespondRequest, SubmitSOAPRequest
from app.agents.helfo_validator import live_events

router = APIRouter()
agent_orchestrator = HelFoAgentOrchestrator()

@router.websocket("/agentic-workflow/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    await live_events.connect(session_id, websocket)
    try:
        while True:
            data = await websocket.receive_json()
            print(f"[WS {session_id}] Received: {data}")

            # Handle user responses
            if "responses" in data:
                request = RespondRequest(responses=data["responses"])
                state = SESSION_STORE.get(session_id)
                if state:
                    state.user_responses = {r.service_code: r.answers for r in request.responses}
                    # Resume workflow and send live updates via the callback
                    await agent_orchestrator.resume_flow(
                        session_id=session_id,
                        user_responses=state.user_responses,
                        event_callback=lambda etype, payload: live_events.push_update(session_id, {"event_type": etype, "payload": payload})
                    )

    except WebSocketDisconnect:
        live_events.disconnect(session_id, websocket)

@router.post("/submit_soap")
async def submit_soap(request: SubmitSOAPRequest):
    print("\n[DEBUG] /submit_soap endpoint called")
    session_id = request.session_id or str(uuid.uuid4())
    print(f"[DEBUG] Using session_id: {session_id}")

    # Simple approach: wait for WebSocket connection with polling
    max_attempts = 25  # 5 seconds total (25 * 200ms)
    for attempt in range(max_attempts):
        if session_id in live_events.SESSION_CONNECTIONS:
            print(f"[DEBUG] WebSocket connection found for session {session_id} after {attempt * 200}ms")
            break
        print(f"[DEBUG] Attempt {attempt + 1}/{max_attempts}: Waiting for WebSocket connection...")
        await asyncio.sleep(0.2)
    else:
        raise HTTPException(
            status_code=408,
            detail=f"Timeout waiting for WebSocket connection for session {session_id}. "
                   f"Please ensure the WebSocket connects before making the HTTP request."
        )

    try:
        print("[DEBUG] Starting agent flow...")
        await agent_orchestrator.start_flow(
            soap_text=request.soap_text,
            session_id=session_id,
            event_callback=lambda etype, payload: live_events.push_update(session_id, {"event_type": etype, "payload": payload})
        )
        print("[DEBUG] Agent flow started successfully")
    except Exception as e:
        print(f"[ERROR] Exception while starting flow: {e}")
        raise HTTPException(status_code=500, detail=f"Error starting session: {e}")

    # Retrieve and return the initial state
    state = SESSION_STORE.get(session_id)
    if not state:
        raise HTTPException(status_code=500, detail="Session state not found after starting flow.")

    response_payload = {
        "session_id": session_id,
        "question": getattr(state, "question", None),
        "waiting_for_user": getattr(state, "waiting_for_user", False),
        "predicted_service_codes": [sc.dict() for sc in getattr(state, "predicted_service_codes", [])],
        "reasoning_trail": getattr(state, "reasoning_trail", []),
    }
    print(f"[DEBUG] Returning response: {response_payload}")
    return response_payload

@router.post("/respond")
async def respond(session_id: str, request: RespondRequest):
    state = SESSION_STORE.get(session_id)
    if not state:
        raise HTTPException(status_code=404, detail="Session not found")

    state.user_responses = {r.service_code: r.answers for r in request.responses}
    await agent_orchestrator.resume_flow(
        session_id=session_id,
        user_responses=state.user_responses,
        event_callback=lambda etype, payload: live_events.push_update(session_id, {"event_type": etype, "payload": payload})
    )

    return JSONResponse(content={
        "session_id": session_id,
        "question": getattr(state, "question", None),
        "waiting_for_user": getattr(state, "waiting_for_user", False),
        "predicted_service_codes": [sc.dict() for sc in getattr(state, "predicted_service_codes", [])],
        "reasoning_trail": getattr(state, "reasoning_trail", []),
    })

@router.get("/state/{session_id}")
async def get_state(session_id: str):
    state = SESSION_STORE.get(session_id)
    if not state:
        raise HTTPException(status_code=404, detail="Session not found")

    state_dict = state.dict()
    state_dict.update({
        "question": getattr(state, "question", None),
        "waiting_for_user": getattr(state, "waiting_for_user", False),
        "loop_count": getattr(state, "loop_count", 0),
        "max_loops": getattr(state, "max_loops", 5),
        "user_responses": getattr(state, "user_responses", {}),
    })
    return JSONResponse(content=state_dict)

@router.get("/_ws/debug")
async def ws_debug():
    return JSONResponse(content={
        "pid": os.getpid(),
        "sessions": {k: len(v) for k, v in live_events.SESSION_CONNECTIONS.items()},
        "total_sessions": len(live_events.SESSION_CONNECTIONS),
        "keys": list(live_events.SESSION_CONNECTIONS.keys()),
    })