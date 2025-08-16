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

def log_state(state: AgenticState, label: str):
    print(timestamped(f"[STATE LOG] {label}"))
    predicted = state.predicted_service_codes
    print(f"predicted_service_codes: {[s.code for s in predicted] if predicted else []}")
    print(f"waiting_for_user: {state.waiting_for_user}")
    print(f"question: {state.question}")
    print(f"loop_count: {getattr(state, 'loop_count', 0)}")
    print(f"reasoning_trail length: {len(state.reasoning_trail)}")
    print("-" * 80)

async def safe_ws_send(ws_send: Optional[Callable[[Dict], Any]], payload: Dict[str, Any]):
    """Safely send WebSocket event if ws_send exists."""
    if ws_send:
        if asyncio.iscoroutinefunction(ws_send):
            await ws_send(payload)
        else:
            loop = asyncio.get_running_loop()
            loop.create_task(ws_send(payload))

# ----------------------------
# Node functions (async)
# ----------------------------
async def predict_service_codes_node(state: AgenticState, ws_send: Optional[Callable[[Dict], Any]] = None) -> Dict[str, Any]:
    if state.predicted_service_codes:
        state.reasoning_trail.append(timestamped("[predict_service_codes_node] Skipped prediction (codes exist)"))
        log_state(state, "After predict_service_codes_node - skipped")
        state.stages.append(StageEvent(
            code="predict_service_codes",
            description="Skipped prediction (codes exist)",
            data={"predicted_codes": [s.code for s in state.predicted_service_codes]}
        ))
    else:
        state.reasoning_trail.append(timestamped("Starting initial service code prediction."))
#         state.candidates = search_service_codes(state.soap_text) or []
        candidates = search_service_codes(state.soap_text) or []

#         if not state.candidates:
        if not candidates:
            state.reasoning_trail.append(timestamped("No candidate codes found from initial search."))
            log_state(state, "After predict_service_codes_node - no candidates")
            state.stages.append(StageEvent(
                code="predict_service_codes",
                description="No candidate codes found",
                data={"predicted_codes": []}
            ))
            await safe_ws_send(ws_send, {
                "event_type": "node_update",
                "node": "predict_service_codes",
                "payload": state.dict()
            })
            return {"candidates": [], "predicted_service_codes": [], "reasoning_trail": state.reasoning_trail, "stages": state.stages}

#         top_candidate = state.candidates[0]
        top_candidate = candidates[0]
        state.candidates = candidates
        state.predicted_service_codes = [
            ServiceCodeState(
                code=top_candidate.get("code", "UNKNOWN"),
                severity="fail",
                missing_terms=[],
                suggestions=[]
            )
        ]
        state.reasoning_trail.append(timestamped(f"Predicted candidate codes: {[c.get('code','UNKNOWN') for c in state.candidates]}"))
        log_state(state, "After predict_service_codes_node")
        state.stages.append(StageEvent(
            code="predict_service_codes",
            description="Predicted service codes",
            data={"predicted_codes": [c.code for c in state.predicted_service_codes]}
        ))

    await safe_ws_send(ws_send, {
        "event_type": "node_update",
        "node": "predict_service_codes",
        "payload": state.dict()
    })

    return {"candidates": state.candidates,"predicted_service_codes": state.predicted_service_codes, "reasoning_trail": state.reasoning_trail, "stages": state.stages}


async def rerank_service_codes_node(state: AgenticState, ws_send: Optional[Callable[[Dict], Any]] = None) -> Dict[str, Any]:
    if not state.candidates:
        state.reasoning_trail.append(timestamped("[rerank_service_codes_node] Skipped rerank (no candidates)"))
        log_state(state, "After rerank_service_codes_node - skipped")
        state.stages.append(StageEvent(
            code="rerank_service_codes",
            description="Skipped rerank (no candidates)",
            data={"reranked_code": getattr(state, "reranked_code", None)}
        ))
    elif state.reranked_code:
        state.reasoning_trail.append(timestamped("[rerank_service_codes_node] Skipped rerank (already reranked)"))
        log_state(state, "After rerank_service_codes_node - skipped")
        state.stages.append(StageEvent(
            code="rerank_service_codes",
            description="Skipped rerank (already reranked)",
            data={"reranked_code": state.reranked_code}
        ))
    else:
        try:
            reranked = rerank_gemini(state.soap_text, state.candidates)
        except Exception as e:
            state.reasoning_trail.append(timestamped(f"[rerank_service_codes_node] Gemini failed: {e}"))
            reranked = state.candidates[0] if state.candidates else None

        if not reranked or not reranked.get("code"):
            reranked = state.candidates[0]
            state.reasoning_trail.append(timestamped(f"[rerank_service_codes_node] Using fallback: {reranked.get('code','UNKNOWN')}"))

        state.reranked_code = reranked.get("code","UNKNOWN")
        if state.predicted_service_codes:
            state.predicted_service_codes[0].code = state.reranked_code
        else:
            state.predicted_service_codes = [ServiceCodeState(code=state.reranked_code)]

        state.reasoning_trail.append(timestamped(f"Reranked code selected: {state.reranked_code}"))
        log_state(state, "After rerank_service_codes_node")
        state.stages.append(StageEvent(
            code="rerank_service_codes",
            description="Reranked service code",
            data={"reranked_code": state.reranked_code}
        ))

    await safe_ws_send(ws_send, {
        "event_type": "node_update",
        "node": "rerank_service_codes",
        "payload": state.dict()
    })

    return {"predicted_service_codes": state.predicted_service_codes, "reranked_code": state.reranked_code, "reasoning_trail": state.reasoning_trail, "stages": state.stages}


async def validate_soap_node(state: AgenticState, ws_send: Optional[Callable[[Dict], Any]] = None) -> Dict[str, Any]:
    state.reasoning_trail.append(timestamped("Starting validate_soap_node"))
    waiting_for_user = False
    question = None

    if state.user_responses and state.predicted_service_codes:
        missing_items = state.predicted_service_codes[0].missing_terms
        for term, response in state.user_responses.items():
            for item in missing_items:
                if item.term == term:
                    item.user_input = response
                    item.answered = True
                    state.reasoning_trail.append(timestamped(f"[validate_soap_node] Applied user response: {term}={response}"))
        state.user_responses = {}

    if not state.predicted_service_codes or not state.predicted_service_codes[0].code:
        state.reasoning_trail.append(timestamped("[validate_soap_node] No service codes to validate."))
        log_state(state, "After validate_soap_node - no codes")
        state.stages.append(StageEvent(
            code="validate_soap",
            description="No service codes to validate",
            data={}
        ))
        await safe_ws_send(ws_send, {
            "event_type": "node_update",
            "node": "validate_soap",
            "payload": state.dict()
        })
        return {"reasoning_trail": state.reasoning_trail, "waiting_for_user": waiting_for_user, "question": question, "stages": state.stages}

    code_to_validate = state.predicted_service_codes[0].code
    full_soap_text = state.soap_text
    for item in state.predicted_service_codes[0].missing_terms:
        if item.user_input:
            full_soap_text += f" {item.term}: {item.user_input}."

    try:
        results = validate_soap_against_rules(full_soap_text, [code_to_validate])
    except Exception as e:
        state.reasoning_trail.append(timestamped(f"[validate_soap_node] Validation failed: {e}"))
        results = []

    if results:
        res = results[0]
        missing_terms_from_rules = res.get("missing_terms") or []
        existing_map = {item.term: item for item in state.predicted_service_codes[0].missing_terms}
        new_missing_terms = [
            existing_map[term] if term in existing_map else MissingInfoItem(term=term)
            for term in missing_terms_from_rules
        ]
        severity = "fail" if any(not t.answered for t in new_missing_terms) else "pass"
        state.predicted_service_codes[0].missing_terms = new_missing_terms
        state.predicted_service_codes[0].severity = severity
        state.predicted_service_codes[0].suggestions = res.get("suggestions") or []

        if severity == "fail":
            waiting_for_user = True
            missing_terms_list = [t.term for t in new_missing_terms if not t.answered]
            question = f"For service code {code_to_validate}, please provide: {', '.join(missing_terms_list)}"
    else:
        state.predicted_service_codes[0].severity = "pass"
        state.reasoning_trail.append(timestamped(f"No validation rules found or validation passed for code {code_to_validate}"))

    state.question = question
    log_state(state, "After validate_soap_node")
    state.stages.append(StageEvent(
        code="validate_soap",
        description="Validation completed",
        data={
            "missing_terms": [m.term for m in state.predicted_service_codes[0].missing_terms],
            "severity": state.predicted_service_codes[0].severity,
            "question": question
        }
    ))

    await safe_ws_send(ws_send, {
        "event_type": "node_update",
        "node": "validate_soap",
        "payload": state.dict()
    })

    return {"predicted_service_codes": state.predicted_service_codes, "reasoning_trail": state.reasoning_trail, "waiting_for_user": waiting_for_user, "question": question, "stages": state.stages}


async def question_generation_node(state: AgenticState, ws_send: Optional[Callable[[Dict], Any]] = None) -> Dict[str, Any]:
    state.reasoning_trail.append(timestamped("[question_generation_node] Generating questions if missing terms exist"))

    if state.question:
        question = state.question
        waiting_for_user = True
        state.reasoning_trail.append(timestamped(f"[question_generation_node] Using existing question from state: '{question}'"))
    else:
        question_lines = []
        for sc in state.predicted_service_codes:
            missing = [m.term for m in sc.missing_terms if not m.answered]
            if missing:
                question_lines.append(f"For service code {sc.code}, please provide: {', '.join(missing)}")
                state.reasoning_trail.append(timestamped(f"Missing terms for {sc.code}: {missing}"))

        waiting_for_user = bool(question_lines)
        question = "\n".join(question_lines) if waiting_for_user else ""

    state.reasoning_trail.append(timestamped(f"[question_generation_node] Waiting for user: {waiting_for_user}"))
    state.reasoning_trail.append(timestamped(f"[question_generation_node] Generated question: '{question}'"))
    log_state(state, "After question_generation_node")

    state.stages.append(StageEvent(
        code="question_generation",
        description="Generated questions for user input",
        data={"question": question, "waiting_for_user": waiting_for_user}
    ))

    await safe_ws_send(ws_send, {
        "event_type": "node_update",
        "node": "question_generation",
        "payload": state.dict()
    })

    return {"waiting_for_user": waiting_for_user, "question": question, "reasoning_trail": state.reasoning_trail, "stages": state.stages}


async def output_node(state: AgenticState, ws_send: Optional[Callable[[Dict], Any]] = None) -> Dict[str, Any]:
    state.reasoning_trail.append(timestamped("[output_node] Finalizing workflow output"))
    log_state(state, "At output_node")
    state.stages.append(StageEvent(
        code="output",
        description="Workflow finished",
        data={}
    ))

    await safe_ws_send(ws_send, {
        "event_type": "node_update",
        "node": "output",
        "payload": state.dict()
    })

    return {"_noop": True, "stages": state.stages, "reasoning_trail": state.reasoning_trail}
