
# predict_rerank_validate_nodes.py
from typing import List, Literal, Dict, Any
from datetime import datetime
from app.schemas_new.agentic_state import MissingInfoItem, ServiceCodeState, AgenticState
from app.core.search_service_codes import search_service_codes
from app.core.rerank_gemini import rerank_gemini
from app.core.validate_note_requirements.engine import validate_soap_against_rules

# ----------------------------
# Helpers
# ----------------------------
def timestamped(msg: str) -> str:
    """Helper to add a timestamp to log messages."""
    print(">>>> inside decorator")
    return f"[{datetime.now().strftime('%H:%M:%S')}] {msg}"

def log_state(state: AgenticState, label: str):
    """Logs the key state variables for debugging purposes."""
    print(timestamped(f"[STATE LOG] {label}"))
    predicted = state.predicted_service_codes
    print(f"predicted_service_codes: {[s.code for s in predicted] if predicted else []}")
    print(f"waiting_for_user: {state.waiting_for_user}")
    print(f"question: {state.question}")
    print(f"loop_count: {state.loop_count}")
    print(f"reasoning_trail length: {len(state.reasoning_trail)}")
    print("-" * 80)

# ----------------------------
# Node functions
# ----------------------------
def predict_service_codes_node(state: AgenticState) -> Dict[str, Any]:
    """
    1. Searches for service codes based on the SOAP text.
    2. Stores all candidates in the state.
    3. Initializes the predicted_service_codes with the top candidate.
    """
    candidates = search_service_codes(state.soap_text)

    # Initialize the reasoning trail
    state.reasoning_trail.append(timestamped("Starting initial service code prediction."))

    if not candidates:
        state.reasoning_trail.append(timestamped("No candidate codes found from initial search."))
        log_state(state, "After predict_service_codes_node - no candidates")
        return {
            "candidates": [],
            "predicted_service_codes": [],
            "reasoning_trail": state.reasoning_trail
        }

    top_candidate = candidates[0]
    initial_service_code_state = ServiceCodeState(
        code=top_candidate.get("code", "UNKNOWN"),
        severity="fail",
        missing_terms=[],
        suggestions=[]
    )
    predicted_service_codes = [initial_service_code_state]

    state.reasoning_trail.append(timestamped(
        f"Predicted candidate codes: {[c.get('code', 'UNKNOWN') for c in candidates]}"
    ))

    log_state(state, "After predict_service_codes_node")
    return {
        "candidates": candidates,
        "predicted_service_codes": predicted_service_codes,
        "reasoning_trail": state.reasoning_trail
    }

def rerank_service_codes_node(state: AgenticState) -> Dict[str, Any]:
    """
    1. Reranks candidate codes using the Gemini model.
    2. Sets the best one as the main predicted code.
    """
    if not state.candidates:
        state.reasoning_trail.append(timestamped("[rerank_service_codes_node] No candidate codes found."))
        log_state(state, "After rerank_service_codes_node - no candidates")
        return {
            "reranked_code": None,
            "reasoning_trail": state.reasoning_trail
        }

    # Rerank using Gemini
    try:
        reranked = rerank_gemini(state.soap_text, state.candidates)
    except Exception as e:
        state.reasoning_trail.append(timestamped(f"[rerank_service_codes_node] Gemini failed: {e}"))
        reranked = None

    # Fallback to the top candidate from the initial search if Gemini fails
    if not reranked or not reranked.get("code"):
        reranked = state.candidates[0]
        state.reasoning_trail.append(timestamped(f"[rerank_service_codes_node] Using fallback: {reranked.get('code', 'UNKNOWN')}"))

    # Update the predicted_service_codes with the reranked code
    if state.predicted_service_codes:
        state.predicted_service_codes[0].code = reranked.get("code", "UNKNOWN")
    else:
        state.predicted_service_codes = [ServiceCodeState(code=reranked.get("code", "UNKNOWN"))]

    state.reasoning_trail.append(timestamped(f"Reranked code selected: {reranked.get('code', 'UNKNOWN')}"))

    log_state(state, "After rerank_service_codes_node")
    return {
        "reranked_code": reranked,
        "predicted_service_codes": state.predicted_service_codes,
        "reasoning_trail": state.reasoning_trail
    }


def validate_soap_node(state: AgenticState) -> Dict[str, Any]:
    """
    1. Validates the SOAP note against requirements for the predicted code.
    2. Updates the predicted service code with validation results (missing terms, suggestions).
    3. Returns `waiting_for_user=True` if validation fails.
    """
    # Initialize waiting_for_user to False by default
    print("validate_soap_node is called in predict_rerank_validate_nodes")
    waiting_for_user = False

    print("state user responses check")
    print(state)

    # Process user responses if they exist
    if state.user_responses:
        print("user responses is triggered")
        # Update the missing_terms with the user's input
        if state.predicted_service_codes and state.predicted_service_codes[0].missing_terms:
            missing_items = state.predicted_service_codes[0].missing_terms

            for term, response in state.user_responses.items():
                state.reasoning_trail.append(timestamped(f"[validate_soap_node] Processing user response for '{term}': '{response}'"))
                # Find the corresponding missing item and update it
                for item in missing_items:
                    if item.term == term:
                        # Use a more sophisticated check here. For example, a simple check for 'no', 'none', 'n/a'
                        # could be done, but a better approach is to rely on the next validation step.
                        item.answered = True
                        item.user_input = response
                        state.reasoning_trail.append(timestamped(f"[validate_soap_node] Marked term '{term}' as answered."))
                        break
            # Now, clear the user responses dictionary to prevent re-processing in the next loop
            state.user_responses = {}
    else:
        print("⚠️ state.user_responses is empty or None.")

    if not state.predicted_service_codes or not state.predicted_service_codes[0].code:
        state.reasoning_trail.append(timestamped("[validate_soap_node] No service codes to validate."))
        log_state(state, "After validate_soap_node - no codes")
        return {"reasoning_trail": state.reasoning_trail, "waiting_for_user": waiting_for_user}

    service_code_to_validate = state.predicted_service_codes[0].code

    # Construct the full SOAP note with all information, including past user inputs
    full_soap_text = state.soap_text
    if state.predicted_service_codes and state.predicted_service_codes[0].missing_terms:
        for item in state.predicted_service_codes[0].missing_terms:
            if item.user_input is not None:
                full_soap_text += f" {item.term}: {item.user_input}."

    try:
        results = validate_soap_against_rules(full_soap_text, [service_code_to_validate])
    except Exception as e:
        state.reasoning_trail.append(timestamped(f"[validate_soap_node] Validation failed: {e}"))
        results = []

    if results:
        res = results[0]
        missing_terms_from_rules = res.get("missing_terms") or []

        # Merge the new missing terms from the rules with the existing ones from the state
        # preserving the "answered" status of terms already addressed by the user
        existing_missing_terms_map = {item.term: item for item in state.predicted_service_codes[0].missing_terms}
        new_missing_terms = []

        for term in missing_terms_from_rules:
            if term in existing_missing_terms_map:
                new_missing_terms.append(existing_missing_terms_map[term])
            else:
                new_missing_terms.append(MissingInfoItem(term=term, answered=False, user_input=None))

        severity = "fail" if [t for t in new_missing_terms if not t.answered] else "pass"
        suggestions = res.get("suggestions") or []

        state.predicted_service_codes[0].missing_terms = new_missing_terms
        state.predicted_service_codes[0].severity = severity
        state.predicted_service_codes[0].suggestions = suggestions

        state.reasoning_trail.append(timestamped(
            f"Validation results for {res.get('service_code') or res.get('code')}: severity='{severity}'"
        ))

        # IMPORTANT: Set the waiting_for_user flag here based on severity
        if severity == "fail":
            waiting_for_user = True
    else:
        state.predicted_service_codes[0].severity = "pass"
        state.reasoning_trail.append(timestamped(
            f"No validation rules found or validation passed for code {service_code_to_validate}."
        ))

    log_state(state, "After validate_soap_node")
    return {
        "predicted_service_codes": state.predicted_service_codes,
        "reasoning_trail": state.reasoning_trail,
        "waiting_for_user": waiting_for_user
    }


from app.utils.logging import get_logger

logger = get_logger(__name__)

def question_generation_node(state: AgenticState) -> Dict[str, Any]:
    """
    Generates a question for the user if there are missing terms that haven't been answered.
    Returns an empty string for 'question' when no user input is required.
    """
    state.reasoning_trail.append(timestamped("[question_generation_node] Starting question generation."))
    logger.info(f"[question_generation_node] State predicted_service_codes: {state.predicted_service_codes}")

    question_lines = []

    for sc in state.predicted_service_codes:
        logger.info(f"[question_generation_node] Processing code: {sc.code}")
        logger.info(f"[question_generation_node] Missing terms on state for this code: {sc.missing_terms}")

        # Find missing terms that have not been answered by the user yet
        missing = [m.term for m in sc.missing_terms if not m.answered]
        logger.info(f"[question_generation_node] Found unanswered missing terms: {missing}")

        if missing:
            question_lines.append(f"For service code {sc.code}, please provide: {', '.join(missing)}")
            state.reasoning_trail.append(timestamped(f"Missing terms for {sc.code}: {missing}"))

    logger.info(f"[question_generation_node] Final question lines list: {question_lines}")

    waiting_for_user = bool(question_lines)
    question = "\n".join(question_lines) if waiting_for_user else ""

    state.reasoning_trail.append(timestamped(f"[question_generation_node] Waiting for user: {waiting_for_user}"))
    state.reasoning_trail.append(timestamped(f"[question_generation_node] Generated question: '{question}'"))

    log_state(state, "After question_generation_node")
    return {
        "waiting_for_user": waiting_for_user,
        "question": question,
        "reasoning_trail": state.reasoning_trail
    }


def output_node(state: AgenticState) -> Dict[str, Any]:
    log_state(state, "At output_node")
    print(">>>> output_node will return a noop update")
    # return a NON-empty dict so LangGraph doesn’t convert to None
    return {"_noop": True}






