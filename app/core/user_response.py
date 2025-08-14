# app/core/user_response.py
from typing import Dict
from app.schemas.agentic_state import AgenticState

def apply_user_response(state: AgenticState, responses: Dict[str, str]):
    for sc in state.predicted_service_codes:
        for m in sc.missing_terms:
            if m.term in responses:
                m.user_input = responses[m.term]
                m.answered = True
        # Update severity
        if all(m.answered for m in sc.missing_terms):
            sc.severity = "pass"
        elif any(m.answered for m in sc.missing_terms):
            sc.severity = "warn"
        else:
            sc.severity = "fail"
    state.waiting_for_user = False
