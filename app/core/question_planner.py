# app/core/question_planner.py
from typing import List, Dict, Any
from app.schemas_new.agentic_state import AgenticState

def plan_questions_from_missing(state: AgenticState) -> AgenticState:
    """
    Generates a question for the user based on the missing terms in the
    predicted service code.

    Args:
        state (AgenticState): The current state of the workflow.

    Returns:
        AgenticState: The updated state with a question for the user.
    """
    if not state.predicted_service_codes:
        state.reasoning_trail.append("No predicted service codes to generate questions from.")
        return state

    # We assume the first predicted code is the one we're working with.
    # The validate_soap node should have populated the missing_terms.

    # Check if the predicted_service_codes list contains dictionaries with a 'missing_terms' key
    if not isinstance(state.predicted_service_codes[0], dict) or 'missing_terms' not in state.predicted_service_codes[0]:
        state.reasoning_trail.append("Predicted service codes do not contain 'missing_terms' for question generation.")
        state.question = "Please provide additional details to help me complete the SOAP note."
        state.waiting_for_user = True
        return state

    missing_terms = [
        t['term'] for t in state.predicted_service_codes[0].get('missing_terms', [])
        if not t.get('answered', False)
    ]

    if missing_terms:
        code = state.predicted_service_codes[0].get('code', 'N/A')
        question = f"For service code {code}, please provide: {', '.join(missing_terms)}"
        state.question = question
        state.waiting_for_user = True
        state.reasoning_trail.append(f"Generated question: {question}")
    else:
        state.question = None
        state.waiting_for_user = False
        state.reasoning_trail.append("No missing terms found. Not generating a question.")

    return state
