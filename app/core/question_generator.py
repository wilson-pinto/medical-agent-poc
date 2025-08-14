# app/core/question_generator.py
from app.schemas.agentic_state import AgenticState

def generate_question(state: AgenticState) -> str:
    question_lines = []
    for sc in state.predicted_service_codes:
        missing = [m.term for m in sc.missing_terms if not m.answered]
        if missing:
            question_lines.append(
                f"For service code {sc.code}, please provide: {', '.join(missing)}"
            )
    state.waiting_for_user = True
    return "\n".join(question_lines)
