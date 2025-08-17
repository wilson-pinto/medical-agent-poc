# app/core/predict_rerank_validate_nodes.py

from typing import List, Dict, Any, Optional, Callable
from datetime import datetime
from app.schemas_new.agentic_state import MissingInfoItem, ServiceCodeState, AgenticState, StageEvent
from app.core.search_service_codes import search_service_codes
from app.core.rerank_gemini import rerank_gemini
from app.core.validate_note_requirements.engine import validate_soap_against_rules
from app.utils.logging import get_logger
import asyncio

logger = get_logger(__name__)


# ----------------------------
# Helpers
# ----------------------------
def timestamped(msg: str) -> str:
    return f"[{datetime.now().strftime('%H:%M:%S')}] {msg}"


async def safe_ws_send(ws_send: Optional[Callable[[Dict], Any]], payload: Dict[str, Any]):
    """Safely send WebSocket event if ws_send exists."""
    if ws_send:
        if asyncio.iscoroutinefunction(ws_send):
            await ws_send(payload)
        else:
            loop = asyncio.get_running_loop()
            loop.create_task(ws_send(payload))


# ----------------------------
# Node: Prediction
# ----------------------------
async def predict_service_codes_node(state: AgenticState, ws_send: Optional[Callable[[Dict], Any]] = None) -> Dict[str, Any]:
    if state.predicted_service_codes:
        summary = f"Skipped — already have {len(state.predicted_service_codes)} codes"
        stage_data = {"predicted_codes": [s.code for s in state.predicted_service_codes]}
        state.reasoning_trail.append(timestamped("[predict_service_codes_node] Skipped prediction (codes exist)"))
    else:
        state.reasoning_trail.append(timestamped("Starting initial service code prediction."))
        candidates = search_service_codes(state.soap_text) or []
        if not candidates:
            summary = "No candidate codes found"
            stage_data = {"predicted_codes": []}
            state.stages.append(StageEvent(code="predict_service_codes", description="Search complete", data=stage_data))
            return {
                "candidates": [], "predicted_service_codes": [],
                "reasoning_trail": state.reasoning_trail, "stages": state.stages
            }
        top = candidates[0]
        state.candidates = candidates
        state.predicted_service_codes = [ServiceCodeState(code=top.get("code", "UNKNOWN"), severity="fail",
                                                          missing_terms=[], suggestions=[])]
        summary = f"Predicted {top.get('code')}"
        stage_data = {"predicted_codes": [c.code for c in state.predicted_service_codes]}

    state.stages.append(StageEvent(code="predict_service_codes", description="Predicted service codes",
                                   data={**stage_data, "summary": summary}))

    await safe_ws_send(ws_send, {"event_type": "node_update", "node": "predict_service_codes", "payload": state.dict()})
    return {"candidates": state.candidates, "predicted_service_codes": state.predicted_service_codes,
            "reasoning_trail": state.reasoning_trail, "stages": state.stages}


# ----------------------------
# Node: Rerank
# ----------------------------
async def rerank_service_codes_node(state: AgenticState, ws_send: Optional[Callable[[Dict], Any]] = None) -> Dict[str, Any]:
    if not state.candidates:
        summary = "No candidates to rerank"
        state.stages.append(StageEvent(code="rerank_service_codes", description="Skipped rerank", data={"summary": summary}))
    elif state.reranked_code:
        summary = f"Already ranked — {state.reranked_code}"
        state.stages.append(StageEvent(code="rerank_service_codes", description="Skipped rerank", data={"summary": summary}))
    else:
        try:
            reranked = rerank_gemini(state.soap_text, state.candidates)
        except Exception as e:
            reranked = state.candidates[0]
            summary = f"Fallback ({reranked.get('code')}) due to error"
        else:
            summary = f"Selected {reranked.get('code')}"

        state.reranked_code = reranked.get("code", "UNKNOWN")
        if not state.predicted_service_codes:
            state.predicted_service_codes = [ServiceCodeState(code=state.reranked_code)]
        else:
            state.predicted_service_codes[0].code = state.reranked_code

        state.stages.append(StageEvent(code="rerank_service_codes", description="Reranked service code",
                                       data={"reranked_code": state.reranked_code, "summary": summary}))

    await safe_ws_send(ws_send, {"event_type": "node_update", "node": "rerank_service_codes", "payload": state.dict()})
    return {"predicted_service_codes": state.predicted_service_codes, "reranked_code": state.reranked_code,
            "reasoning_trail": state.reasoning_trail, "stages": state.stages}


# ----------------------------
# Node: Validate
# ----------------------------
async def validate_soap_node(state: AgenticState, ws_send: Optional[Callable[[Dict], Any]] = None) -> Dict[str, Any]:
    state.reasoning_trail.append(timestamped("Starting validate_soap_node"))
    waiting_for_user = False
    question = None

    # If user answered follow-up questions already
    if state.user_responses and state.predicted_service_codes:
        for term, response in state.user_responses.items():
            for item in state.predicted_service_codes[0].missing_terms:
                if item.term == term:
                    item.user_input = response
                    item.answered = True
                    state.reasoning_trail.append(timestamped(f"Applied user response: {term}={response}"))
        state.user_responses = {}

    if not state.predicted_service_codes:
        summary = "No codes to validate"
        state.stages.append(StageEvent(code="validate_soap", description="No validation possible", data={"summary": summary}))
        return {"reasoning_trail": state.reasoning_trail, "waiting_for_user": waiting_for_user,
                "question": question, "stages": state.stages}

    code = state.predicted_service_codes[0].code
    full_text = state.soap_text
    for m in state.predicted_service_codes[0].missing_terms:
        if m.user_input:
            full_text += f" {m.term}: {m.user_input}"

    # run validator
    try:
        results = validate_soap_against_rules(full_text, [code])
    except Exception as e:
        results = []
        state.reasoning_trail.append(timestamped(f"Validation error: {e}"))

    if results:
        res = results[0]
        missing_terms = res.get("missing_terms") or []
        existing = {item.term: item for item in state.predicted_service_codes[0].missing_terms}
        new_missing = [existing[t] if t in existing else MissingInfoItem(term=t) for t in missing_terms]

        severity = "fail" if any(not x.answered for x in new_missing) else "pass"
        state.predicted_service_codes[0].missing_terms = new_missing
        state.predicted_service_codes[0].severity = severity
        state.predicted_service_codes[0].suggestions = res.get("suggestions") or []

        if severity == "fail":
            waiting_for_user = True
            question = f"For service code {code}, provide: {', '.join([x.term for x in new_missing if not x.answered])}"
    else:
        severity = "pass"
        state.predicted_service_codes[0].severity = severity

    summary = f"PASS for {code}" if severity == "pass" else f"FAIL — missing values"
    state.stages.append(StageEvent(code="validate_soap", description="SOAP validation completed",
                                   data={"summary": summary, "severity": severity,
                                         "missing_terms": [m.term for m in state.predicted_service_codes[0].missing_terms]}))

    await safe_ws_send(ws_send, {"event_type": "node_update", "node": "validate_soap", "payload": state.dict()})
    return {"predicted_service_codes": state.predicted_service_codes,
            "reasoning_trail": state.reasoning_trail,
            "waiting_for_user": waiting_for_user,
            "question": question,
            "stages": state.stages}


# ----------------------------
# Node: Clarification question
# ----------------------------
async def question_generation_node(state: AgenticState, ws_send: Optional[Callable[[Dict], Any]] = None) -> Dict[str, Any]:
    state.reasoning_trail.append(timestamped("Generating follow-up questions"))
    if state.question:
        question = state.question
        waiting = True
    else:
        lines = []
        for sc in state.predicted_service_codes:
            miss = [m.term for m in sc.missing_terms if not m.answered]
            if miss:
                lines.append(f"For code {sc.code}: {', '.join(miss)}")
        waiting = bool(lines)
        question = "\n".join(lines) if waiting else ""

    summary = "Needs user input" if waiting else "No questions needed"
    state.stages.append(StageEvent(code="question_generation", description="Generated questions",
                                   data={"summary": summary, "question": question, "waiting_for_user": waiting}))

    await safe_ws_send(ws_send, {"event_type": "node_update", "node": "question_generation", "payload": state.dict()})
    return {"waiting_for_user": waiting, "question": question,
            "reasoning_trail": state.reasoning_trail, "stages": state.stages}


# ----------------------------
# Node: Output
# ----------------------------
async def output_node(state: AgenticState, ws_send: Optional[Callable[[Dict], Any]] = None) -> Dict[str, Any]:
    state.reasoning_trail.append(timestamped("Completing workflow"))
    state.stages.append(StageEvent(code="output", description="Workflow finished", data={"summary": "Done"}))
    await safe_ws_send(ws_send, {"event_type": "node_update", "node": "output", "payload": state.dict()})
    return {"_noop": True, "stages": state.stages, "reasoning_trail": state.reasoning_trail}
