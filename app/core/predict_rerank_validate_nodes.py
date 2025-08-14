from typing import List, Literal, Dict
from datetime import datetime
from langgraph.graph import StateGraph, END
from app.schemas_new.agentic_state import MissingInfoItem, ServiceCodeState, AgenticState
from app.core.search_service_codes import search_service_codes
from app.core.rerank_gemini import rerank_gemini
from app.core.validate_note_requirements.engine import validate_soap_against_rules

# ----------------------------
# Helper
# ----------------------------
def timestamped(msg: str) -> str:
    """Adds a timestamp to a message for the reasoning trail."""
    return f"[{datetime.now().strftime('%H:%M:%S')}] {msg}"

def log_state(state: AgenticState, label: str):
    """Logs key state attributes for debugging."""
    print(f"{timestamped(f'[STATE LOG] {label}')}")
    print(f"soap_text: {getattr(state, 'soap_text', None)}")
    print(f"candidates: {getattr(state, 'candidates', None)}")
    print(f"reranked_code: {getattr(state, 'reranked_code', None)}")
    print(f"predicted_service_codes: {[s.code for s in getattr(state, 'predicted_service_codes', [])]}")
    print(f"waiting_for_user: {getattr(state, 'waiting_for_user', None)}")
    print(f"question: {getattr(state, 'question', None)}")
    print(f"loop_count: {getattr(state, 'loop_count', 0)}")
    print(f"reasoning_trail: {getattr(state, 'reasoning_trail', [])}")

# ----------------------------
# Node functions
# ----------------------------
def predict_service_codes_node(state: AgenticState):
    candidates = search_service_codes(state.soap_text)
    state.reasoning_trail.append(timestamped(f"Predicted candidate codes: {[c.get('code', 'UNKNOWN') for c in candidates]}"))
    state.candidates = candidates or []
    log_state(state, "After predict_service_codes_node")
    return {"candidates": state.candidates}

def rerank_service_codes_node(state: AgenticState):
    candidates = getattr(state, "candidates", [])
    if not candidates:
        state.reasoning_trail.append(timestamped("[rerank_service_codes_node] No candidate codes to rerank."))
        state.reranked_code = None
        log_state(state, "After rerank_service_codes_node - empty candidates")
        return {"reranked_code": None}

    candidates_sorted = sorted(candidates, key=lambda x: x.get("similarity", 0), reverse=True)
    try:
        reranked = rerank_gemini(state.soap_text, candidates_sorted)
    except Exception as e:
        print(f"[DEBUG] [rerank_service_codes_node] Gemini call failed: {e}")
        reranked = None

    if not reranked or not reranked.get("code"):
        fallback = candidates_sorted[0]
        state.reasoning_trail.append(timestamped(
            f"[rerank_service_codes_node] Gemini rerank failed. Using top similarity fallback: {fallback.get('code', 'UNKNOWN')}"
        ))
        reranked = fallback

    state.reranked_code = reranked
    state.reasoning_trail.append(timestamped(f"Reranked code selected: {reranked.get('code', 'UNKNOWN')}"))
    log_state(state, "After rerank_service_codes_node")
    return {"reranked_code": reranked}

def validate_soap_node(state: AgenticState):
    service_codes = [state.reranked_code.get("code")] if getattr(state, "reranked_code", None) else []
    results = validate_soap_against_rules(state.soap_text, service_codes)
    new_sc_states = []

    for res in results:
        existing_terms = {m.term for sc in state.predicted_service_codes for m in sc.missing_terms}
        new_missing = [t for t in (res.get("missing_terms") or []) if t not in existing_terms]
        missing_items = [MissingInfoItem(term=t) for t in new_missing]
        severity = "fail" if missing_items else "pass"
        suggestions = res.get("suggestions") or []

        sc_state = ServiceCodeState(
            code=res.get("service_code") or res.get("code", "UNKNOWN"),
            severity=severity,
            missing_terms=missing_items,
            suggestions=suggestions
        )
        new_sc_states.append(sc_state)

    state.predicted_service_codes = state.predicted_service_codes + new_sc_states
    state.reasoning_trail.append(timestamped(f"Validation results summary: {[(s.code, s.severity) for s in new_sc_states]}"))
    log_state(state, "After validate_soap_node")
    return {"predicted_service_codes": state.predicted_service_codes}

def question_generation_node(state: AgenticState):
    question_lines = []
    for sc in state.predicted_service_codes:
        missing = [m.term for m in sc.missing_terms if not m.answered]
        if missing:
            question_lines.append(f"For service code {sc.code}, please provide: {', '.join(missing)}")
            state.reasoning_trail.append(timestamped(f"Missing terms for {sc.code}: {missing}"))

    state.waiting_for_user = bool(question_lines)
    state.question = "\n".join(question_lines) if state.waiting_for_user else None
    log_state(state, "After question_generation_node")
    return {"question": state.question, "waiting_for_user": state.waiting_for_user}

def user_response_node(state: AgenticState):
    user_responses = getattr(state, "user_responses", {}) or {}
    for sc in state.predicted_service_codes:
        for m in sc.missing_terms:
            if m.term in user_responses:
                m.user_input = user_responses[m.term]
                m.answered = True
                state.reasoning_trail.append(timestamped(f"User input for {m.term}: {user_responses[m.term]}"))
        # Update severity based on answered status
        if all(m.answered for m in sc.missing_terms):
            sc.severity = "pass"
        elif any(m.answered for m in sc.missing_terms):
            sc.severity = "warn"
        else:
            sc.severity = "fail"

    state.waiting_for_user = any(not m.answered for sc in state.predicted_service_codes for m in sc.missing_terms)
    log_state(state, "After user_response_node")
    return {"waiting_for_user": state.waiting_for_user, "predicted_service_codes": state.predicted_service_codes}

def output_node(state: AgenticState):
    log_state(state, "At output_node")
    return {
        "predicted_service_codes": [sc.dict() for sc in state.predicted_service_codes],
        "reasoning_trail": state.reasoning_trail
    }

# ----------------------------
# Loop guard
# ----------------------------
def should_continue(state: AgenticState) -> Literal["user_response", "output"]:
    state.loop_count = getattr(state, "loop_count", 0) + 1
    if state.loop_count >= getattr(state, "max_loops", 5):
        state.reasoning_trail.append(f"[SAFE EXIT] Reached max loop count {state.max_loops}")
        return "output"

    has_missing = any(
        not m.answered
        for sc in getattr(state, "predicted_service_codes", [])
        for m in sc.missing_terms
    )
    log_state(state, "During should_continue")
    return "user_response" if has_missing else "output"

# ----------------------------
# Workflow setup
# ----------------------------
workflow = StateGraph(AgenticState)
workflow.add_node("predict_service_codes", predict_service_codes_node)
workflow.add_node("rerank_service_codes", rerank_service_codes_node)
workflow.add_node("validate_soap", validate_soap_node)
workflow.add_node("question_generation", question_generation_node)
workflow.add_node("user_response", user_response_node)
workflow.add_node("output", output_node)

workflow.set_entry_point("predict_service_codes")
workflow.add_edge("predict_service_codes", "rerank_service_codes")
workflow.add_edge("rerank_service_codes", "validate_soap")
workflow.add_edge("validate_soap", "question_generation")
workflow.add_conditional_edges(
    "question_generation",
    should_continue,
    {"user_response": "user_response", "output": "output"}
)
workflow.add_edge("user_response", "question_generation")
workflow.add_edge("output", END)

compiled_workflow = workflow.compile()
