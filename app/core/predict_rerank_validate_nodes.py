# # app/core/predict_rerank_validate_nodes.py
# from typing import List, Literal, Dict, Any
# from datetime import datetime
# from app.schemas_new.agentic_state import MissingInfoItem, ServiceCodeState, AgenticState
# from app.core.search_service_codes import search_service_codes
# from app.core.rerank_gemini import rerank_gemini
# from app.core.validate_note_requirements.engine import validate_soap_against_rules
#
# # ----------------------------
# # Helpers
# # ----------------------------
# def timestamped(msg: str) -> str:
#     return f"[{datetime.now().strftime('%H:%M:%S')}] {msg}"
#
# def log_state(state: AgenticState, label: str):
#     print(timestamped(f"[STATE LOG] {label}"))
#     predicted = getattr(state, "predicted_service_codes", []) or []
#     print(f"predicted_service_codes: {[s.code for s in predicted]}")
#     print(f"waiting_for_user: {getattr(state, 'waiting_for_user', None)}")
#     print(f"question: {getattr(state, 'question', None)}")
#     print(f"loop_count: {getattr(state, 'loop_count', 0)}")
#     print(f"reasoning_trail length: {len(getattr(state, 'reasoning_trail', []))}")
#     print("-" * 80)
#
# # ----------------------------
# # Node functions
# # ----------------------------
# def predict_service_codes_node(state: AgenticState) -> Dict[str, Any]:
#     """
#     Search for service codes and populate the state.
#     """
#     candidates = search_service_codes(state.soap_text) or []
#     reasoning_trail = getattr(state, "reasoning_trail", [])
#
#     if not candidates:
#         predicted_service_codes = []
#         reasoning_trail.append(timestamped("No candidate codes found from initial search."))
#
#         log_state(state, "After predict_service_codes_node - no candidates")
#         return {
#             "candidates": candidates,
#             "predicted_service_codes": predicted_service_codes,
#             "reasoning_trail": reasoning_trail
#         }
#
#     top_candidate = candidates[0]
#     initial_service_code_state = ServiceCodeState(
#         code=top_candidate.get("code", "UNKNOWN"),
#         severity="fail",
#         missing_terms=[],
#         suggestions=[]
#     )
#     predicted_service_codes = [initial_service_code_state]
#
#     reasoning_trail.append(timestamped(
#         f"Predicted candidate codes: {[c.get('code', 'UNKNOWN') for c in candidates]}"
#     ))
#
#     log_state(state, "After predict_service_codes_node")
#     return {
#         "candidates": candidates,
#         "predicted_service_codes": predicted_service_codes,
#         "reasoning_trail": reasoning_trail
#     }
#
# def rerank_service_codes_node(state: AgenticState) -> Dict[str, Any]:
#     """
#     Reranks candidate codes and sets the best one.
#     """
#     candidates = getattr(state, "candidates", []) or []
#     reasoning_trail = getattr(state, "reasoning_trail", [])
#     predicted_service_codes = getattr(state, "predicted_service_codes", [])
#
#     if not candidates:
#         reasoning_trail.append(timestamped("[rerank_service_codes_node] No candidate codes"))
#         log_state(state, "After rerank_service_codes_node - empty candidates")
#         return {
#             "reranked_code": None,
#             "reasoning_trail": reasoning_trail
#         }
#
#     candidates_sorted = sorted(candidates, key=lambda x: x.get("similarity", 0), reverse=True)
#     try:
#         reranked = rerank_gemini(state.soap_text, candidates_sorted)
#     except Exception as e:
#         reasoning_trail.append(timestamped(f"[rerank_service_codes_node] Gemini failed: {e}"))
#         reranked = None
#
#     if not reranked or not reranked.get("code"):
#         reranked = candidates_sorted[0]
#         reasoning_trail.append(timestamped(f"[rerank_service_codes_node] Using fallback: {reranked.get('code', 'UNKNOWN')}"))
#
#     if predicted_service_codes:
#         predicted_service_codes[0].code = reranked.get("code", "UNKNOWN")
#     else:
#         predicted_service_codes = [ServiceCodeState(code=reranked.get("code", "UNKNOWN"))]
#
#     reasoning_trail.append(timestamped(f"Reranked code selected: {reranked.get('code', 'UNKNOWN')}"))
#
#     log_state(state, "After rerank_service_codes_node")
#     return {
#         "reranked_code": reranked,
#         "predicted_service_codes": predicted_service_codes,
#         "reasoning_trail": reasoning_trail
#     }
#
#
# def validate_soap_node(state: AgenticState) -> Dict[str, Any]:
#     """
#     Validates the SOAP note against requirements for the reranked code.
#     """
#     predicted_service_codes = getattr(state, "predicted_service_codes", [])
#     reasoning_trail = getattr(state, "reasoning_trail", [])
#
#     if not predicted_service_codes or not predicted_service_codes[0].code:
#         reasoning_trail.append(timestamped("[validate_soap_node] No service codes to validate."))
#         log_state(state, "After validate_soap_node - no codes")
#         return {"reasoning_trail": reasoning_trail}
#
#     service_code_to_validate = predicted_service_codes[0].code
#
#     try:
#         results = validate_soap_against_rules(state.soap_text, [service_code_to_validate])
#     except Exception as e:
#         reasoning_trail.append(timestamped(f"[validate_soap_node] Validation failed: {e}"))
#         results = []
#
#     if results:
#         res = results[0]
#         missing_terms = [
#             MissingInfoItem(term=t) for t in (res.get("missing_terms") or [])
#         ]
#         severity = "fail" if missing_terms else "pass"
#         suggestions = res.get("suggestions") or []
#
#         predicted_service_codes[0].missing_terms = missing_terms
#         predicted_service_codes[0].severity = severity
#         predicted_service_codes[0].suggestions = suggestions
#
#         reasoning_trail.append(timestamped(
#             f"Validation results for {res.get('service_code') or res.get('code')}: severity='{severity}'"
#         ))
#     else:
#         predicted_service_codes[0].severity = "pass"
#         reasoning_trail.append(timestamped(
#             f"No validation rules found or validation passed for code {service_code_to_validate}."
#         ))
#
#     log_state(state, "After validate_soap_node")
#     return {
#         "predicted_service_codes": predicted_service_codes,
#         "reasoning_trail": reasoning_trail
#     }
#
# def question_generation_node(state: AgenticState) -> Dict[str, Any]:
#     """
#     Generates a question for the user if there are missing terms.
#     """
#     question_lines = []
#     reasoning_trail = getattr(state, "reasoning_trail", [])
#
#     for sc in getattr(state, "predicted_service_codes", []):
#         missing = [m.term for m in sc.missing_terms if not getattr(m, "answered", False)]
#         if missing:
#             question_lines.append(f"For service code {sc.code}, please provide: {', '.join(missing)}")
#             reasoning_trail.append(timestamped(f"Missing terms for {sc.code}: {missing}"))
#
#     waiting_for_user = bool(question_lines)
#     question = "\n".join(question_lines) if waiting_for_user else None
#
#     log_state(state, "After question_generation_node")
#     return {
#         "waiting_for_user": waiting_for_user,
#         "question": question,
#         "reasoning_trail": reasoning_trail
#     }
#
# def user_response_node(state: AgenticState) -> Dict[str, Any]:
#     """
#     Processes user responses to update the state and validation status.
#     """
#     user_responses = getattr(state, "user_responses", {}) or {}
#     predicted_service_codes = getattr(state, "predicted_service_codes", [])
#     reasoning_trail = getattr(state, "reasoning_trail", [])
#
#     for sc in predicted_service_codes:
#         for m in sc.missing_terms:
#             if m.term in user_responses:
#                 m.user_input = user_responses[m.term]
#                 m.answered = True
#                 reasoning_trail.append(timestamped(f"User input for {m.term}: {user_responses[m.term]}"))
#
#         if all(getattr(m, "answered", False) for m in sc.missing_terms):
#             sc.severity = "pass"
#         elif any(getattr(m, "answered", False) for m in sc.missing_terms):
#             sc.severity = "warn"
#         else:
#             sc.severity = "fail"
#
#     waiting_for_user = any(
#         not getattr(m, "answered", False)
#         for sc in predicted_service_codes
#         for m in sc.missing_terms
#     )
#
#     log_state(state, "After user_response_node")
#     return {
#         "predicted_service_codes": predicted_service_codes,
#         "waiting_for_user": waiting_for_user,
#         "reasoning_trail": reasoning_trail
#     }
#
# def output_node(state: AgenticState):
#     """
#     Final node to produce the output.
#     """
#     log_state(state, "At output_node")
#     return state
#
# # ----------------------------
# # Loop guard
# # ----------------------------
# def should_continue(state: AgenticState) -> Literal["user_response", "output"]:
#     """
#     Determines if the workflow should continue to the user response step or proceed to output.
#     """
#     loop_count = getattr(state, "loop_count", 0) + 1
#     max_loops = getattr(state, "max_loops", 10)
#
#     if loop_count > max_loops:
#         state.reasoning_trail.append(timestamped(f"[SAFE EXIT] Max loops reached {max_loops}"))
#         log_state(state, "During should_continue - max loops reached")
#         return "output"
#
#     has_missing = any(
#         not getattr(m, "answered", False)
#         for sc in getattr(state, "predicted_service_codes", [])
#         for m in sc.missing_terms
#     )
#
#     # Update loop_count in a separate dictionary to avoid state corruption
#     updated_state = {"loop_count": loop_count}
#     # This is a temporary solution to update the state before the next node is called.
#     # In a real LangGraph setup, you would typically have a separate node for this.
#     # We will assume a merge happens here for the sake of the fix.
#
#     log_state(state, "During should_continue")
#
#     return "user_response" if has_missing else "output"
# app/core/predict_rerank_validate_nodes.py
# from typing import List, Literal, Dict, Any
# from datetime import datetime
# from app.schemas_new.agentic_state import MissingInfoItem, ServiceCodeState, AgenticState
# from app.core.search_service_codes import search_service_codes
# from app.core.rerank_gemini import rerank_gemini
# from app.core.validate_note_requirements.engine import validate_soap_against_rules
#
# # ----------------------------
# # Helpers
# # ----------------------------
# def timestamped(msg: str) -> str:
#     """Helper to add a timestamp to log messages."""
#     return f"[{datetime.now().strftime('%H:%M:%S')}] {msg}"
#
# def log_state(state: AgenticState, label: str):
#     """Logs the key state variables for debugging purposes."""
#     print(timestamped(f"[STATE LOG] {label}"))
#     predicted = state.predicted_service_codes
#     print(f"predicted_service_codes: {[s.code for s in predicted] if predicted else []}")
#     print(f"waiting_for_user: {state.waiting_for_user}")
#     print(f"question: {state.question}")
#     print(f"loop_count: {state.loop_count}")
#     print(f"reasoning_trail length: {len(state.reasoning_trail)}")
#     print("-" * 80)
#
# # ----------------------------
# # Node functions
# # ----------------------------
# def predict_service_codes_node(state: AgenticState) -> Dict[str, Any]:
#     """
#     1. Searches for service codes based on the SOAP text.
#     2. Stores all candidates in the state.
#     3. Initializes the predicted_service_codes with the top candidate.
#     """
#     candidates = search_service_codes(state.soap_text)
#
#     # Initialize the reasoning trail
#     state.reasoning_trail.append(timestamped("Starting initial service code prediction."))
#
#     if not candidates:
#         state.reasoning_trail.append(timestamped("No candidate codes found from initial search."))
#         log_state(state, "After predict_service_codes_node - no candidates")
#         return {
#             "candidates": [],
#             "predicted_service_codes": [],
#             "reasoning_trail": state.reasoning_trail
#         }
#
#     top_candidate = candidates[0]
#     initial_service_code_state = ServiceCodeState(
#         code=top_candidate.get("code", "UNKNOWN"),
#         severity="fail",
#         missing_terms=[],
#         suggestions=[]
#     )
#     predicted_service_codes = [initial_service_code_state]
#
#     state.reasoning_trail.append(timestamped(
#         f"Predicted candidate codes: {[c.get('code', 'UNKNOWN') for c in candidates]}"
#     ))
#
#     log_state(state, "After predict_service_codes_node")
#     return {
#         "candidates": candidates,
#         "predicted_service_codes": predicted_service_codes,
#         "reasoning_trail": state.reasoning_trail
#     }
#
# def rerank_service_codes_node(state: AgenticState) -> Dict[str, Any]:
#     """
#     1. Reranks candidate codes using the Gemini model.
#     2. Sets the best one as the main predicted code.
#     """
#     if not state.candidates:
#         state.reasoning_trail.append(timestamped("[rerank_service_codes_node] No candidate codes found."))
#         log_state(state, "After rerank_service_codes_node - no candidates")
#         return {
#             "reranked_code": None,
#             "reasoning_trail": state.reasoning_trail
#         }
#
#     # Rerank using Gemini
#     try:
#         reranked = rerank_gemini(state.soap_text, state.candidates)
#     except Exception as e:
#         state.reasoning_trail.append(timestamped(f"[rerank_service_codes_node] Gemini failed: {e}"))
#         reranked = None
#
#     # Fallback to the top candidate from the initial search if Gemini fails
#     if not reranked or not reranked.get("code"):
#         reranked = state.candidates[0]
#         state.reasoning_trail.append(timestamped(f"[rerank_service_codes_node] Using fallback: {reranked.get('code', 'UNKNOWN')}"))
#
#     # Update the predicted_service_codes with the reranked code
#     if state.predicted_service_codes:
#         state.predicted_service_codes[0].code = reranked.get("code", "UNKNOWN")
#     else:
#         state.predicted_service_codes = [ServiceCodeState(code=reranked.get("code", "UNKNOWN"))]
#
#     state.reasoning_trail.append(timestamped(f"Reranked code selected: {reranked.get('code', 'UNKNOWN')}"))
#
#     log_state(state, "After rerank_service_codes_node")
#     return {
#         "reranked_code": reranked,
#         "predicted_service_codes": state.predicted_service_codes,
#         "reasoning_trail": state.reasoning_trail
#     }
#
#
# def validate_soap_node(state: AgenticState) -> Dict[str, Any]:
#     """
#     1. Validates the SOAP note against requirements for the predicted code.
#     2. Updates the predicted service code with validation results (missing terms, suggestions).
#     """
#     if not state.predicted_service_codes or not state.predicted_service_codes[0].code:
#         state.reasoning_trail.append(timestamped("[validate_soap_node] No service codes to validate."))
#         log_state(state, "After validate_soap_node - no codes")
#         return {"reasoning_trail": state.reasoning_trail}
#
#     service_code_to_validate = state.predicted_service_codes[0].code
#
#     try:
#         results = validate_soap_against_rules(state.soap_text, [service_code_to_validate])
#     except Exception as e:
#         state.reasoning_trail.append(timestamped(f"[validate_soap_node] Validation failed: {e}"))
#         results = []
#
#     if results:
#         res = results[0]
#         missing_terms = [
#             MissingInfoItem(term=t) for t in (res.get("missing_terms") or [])
#         ]
#         severity = "fail" if missing_terms else "pass"
#         suggestions = res.get("suggestions") or []
#
#         state.predicted_service_codes[0].missing_terms = missing_terms
#         state.predicted_service_codes[0].severity = severity
#         state.predicted_service_codes[0].suggestions = suggestions
#
#         state.reasoning_trail.append(timestamped(
#             f"Validation results for {res.get('service_code') or res.get('code')}: severity='{severity}'"
#         ))
#     else:
#         state.predicted_service_codes[0].severity = "pass"
#         state.reasoning_trail.append(timestamped(
#             f"No validation rules found or validation passed for code {service_code_to_validate}."
#         ))
#
#     log_state(state, "After validate_soap_node")
#     return {
#         "predicted_service_codes": state.predicted_service_codes,
#         "reasoning_trail": state.reasoning_trail
#     }
#
# def question_generation_node(state: AgenticState) -> Dict[str, Any]:
#     """
#     Generates a question for the user if there are missing terms that haven't been answered.
#     """
#     question_lines = []
#
#     for sc in state.predicted_service_codes:
#         # Find missing terms that have not been answered by the user yet
#         missing = [m.term for m in sc.missing_terms if not m.answered]
#         if missing:
#             question_lines.append(f"For service code {sc.code}, please provide: {', '.join(missing)}")
#             state.reasoning_trail.append(timestamped(f"Missing terms for {sc.code}: {missing}"))
#
#     waiting_for_user = bool(question_lines)
#     question = "\n".join(question_lines) if waiting_for_user else None
#
#     log_state(state, "After question_generation_node")
#     return {
#         "waiting_for_user": waiting_for_user,
#         "question": question,
#         "reasoning_trail": state.reasoning_trail
#     }
#
# def output_node(state: AgenticState):
#     """
#     Final node to produce the output.
#     """
#     log_state(state, "At output_node")
#     return state
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

#
# def validate_soap_node(state: AgenticState) -> Dict[str, Any]:
#     """
#     1. Validates the SOAP note against requirements for the predicted code.
#     2. Updates the predicted service code with validation results (missing terms, suggestions).
#     """
#     if not state.predicted_service_codes or not state.predicted_service_codes[0].code:
#         state.reasoning_trail.append(timestamped("[validate_soap_node] No service codes to validate."))
#         log_state(state, "After validate_soap_node - no codes")
#         return {"reasoning_trail": state.reasoning_trail}
#
#     service_code_to_validate = state.predicted_service_codes[0].code
#
#     try:
#         results = validate_soap_against_rules(state.soap_text, [service_code_to_validate])
#     except Exception as e:
#         state.reasoning_trail.append(timestamped(f"[validate_soap_node] Validation failed: {e}"))
#         results = []
#
#     if results:
#         res = results[0]
#         missing_terms = [
#             MissingInfoItem(term=t, answered=False, user_input=None) for t in (res.get("missing_terms") or [])
#         ]
#
#         # Check if terms have already been answered
#         if state.predicted_service_codes[0].missing_terms:
#             existing_missing_terms = {item.term for item in state.predicted_service_codes[0].missing_terms}
#             for term_item in missing_terms:
#                 if term_item.term in existing_missing_terms:
#                     # Keep the answered status from previous state
#                     for existing_item in state.predicted_service_codes[0].missing_terms:
#                         if existing_item.term == term_item.term:
#                             term_item.answered = existing_item.answered
#                             term_item.user_input = existing_item.user_input
#                             break
#
#         severity = "fail" if [t for t in missing_terms if not t.answered] else "pass"
#         suggestions = res.get("suggestions") or []
#
#         state.predicted_service_codes[0].missing_terms = missing_terms
#         state.predicted_service_codes[0].severity = severity
#         state.predicted_service_codes[0].suggestions = suggestions
#
#         state.reasoning_trail.append(timestamped(
#             f"Validation results for {res.get('service_code') or res.get('code')}: severity='{severity}'"
#         ))
#     else:
#         state.predicted_service_codes[0].severity = "pass"
#         state.reasoning_trail.append(timestamped(
#             f"No validation rules found or validation passed for code {service_code_to_validate}."
#         ))
#
#     log_state(state, "After validate_soap_node")
#     return {
#         "predicted_service_codes": state.predicted_service_codes,
#         "reasoning_trail": state.reasoning_trail
#     }

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
    if state.user_responses:
        print("user responses is triggered")
        # Create a new string with the combined information
        combined_text = state.soap_text
        for term, response in state.user_responses.items():
            # Append the new information to the SOAP text
            combined_text += f" {term}: {response}."
            state.reasoning_trail.append(timestamped(f"[validate_soap_node] Merged user response for '{term}'. New SOAP text: {combined_text}"))
        state.soap_text = combined_text
        # Clear the user_responses after processing them to avoid re-merging
#         state.user_responses = None
    else:
        print("⚠️ state.user_responses is empty or None.")

    if not state.predicted_service_codes or not state.predicted_service_codes[0].code:
        state.reasoning_trail.append(timestamped("[validate_soap_node] No service codes to validate."))
        log_state(state, "After validate_soap_node - no codes")
        return {"reasoning_trail": state.reasoning_trail, "waiting_for_user": waiting_for_user}

    service_code_to_validate = state.predicted_service_codes[0].code

    try:
        results = validate_soap_against_rules(state.soap_text, [service_code_to_validate])
    except Exception as e:
        state.reasoning_trail.append(timestamped(f"[validate_soap_node] Validation failed: {e}"))
        results = []

    if results:
        res = results[0]
        missing_terms = [
            MissingInfoItem(term=t, answered=False, user_input=None) for t in (res.get("missing_terms") or [])
        ]

        # Check if terms have already been answered
        if state.predicted_service_codes[0].missing_terms:
            existing_missing_terms = {item.term for item in state.predicted_service_codes[0].missing_terms}
            for term_item in missing_terms:
                if term_item.term in existing_missing_terms:
                    # Keep the answered status from previous state
                    for existing_item in state.predicted_service_codes[0].missing_terms:
                        if existing_item.term == term_item.term:
                            term_item.answered = existing_item.answered
                            term_item.user_input = existing_item.user_input
                            break

        severity = "fail" if [t for t in missing_terms if not t.answered] else "pass"
        suggestions = res.get("suggestions") or []

        state.predicted_service_codes[0].missing_terms = missing_terms
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

# def question_generation_node(state: AgenticState) -> Dict[str, Any]:
#     """
#     Generates a question for the user if there are missing terms that haven't been answered.
#     """
#     question_lines = []
#
#     for sc in state.predicted_service_codes:
#         # Find missing terms that have not been answered by the user yet
#         missing = [m.term for m in sc.missing_terms if not m.answered]
#         if missing:
#             question_lines.append(f"For service code {sc.code}, please provide: {', '.join(missing)}")
#             state.reasoning_trail.append(timestamped(f"Missing terms for {sc.code}: {missing}"))
#
#     waiting_for_user = bool(question_lines)
#     question = "\n".join(question_lines) if waiting_for_user else None
#
#     log_state(state, "After question_generation_node")
#     return {
#         "waiting_for_user": waiting_for_user,
#         "question": question,
#         "reasoning_trail": state.reasoning_trail
#     }
from app.utils.logging import get_logger

logger = get_logger(__name__)

def question_generation_node(state: AgenticState) -> Dict[str, Any]:
    """
    Generates a question for the user if there are missing terms that haven't been answered.
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
    question = "\n".join(question_lines) if waiting_for_user else None

    state.reasoning_trail.append(timestamped(f"[question_generation_node] Waiting for user: {waiting_for_user}"))
    state.reasoning_trail.append(timestamped(f"[question_generation_node] Generated question: '{question}'"))

    log_state(state, "After question_generation_node")
    return {
        "waiting_for_user": waiting_for_user,
        "question": question,
        "reasoning_trail": state.reasoning_trail
    }

def output_node(state: AgenticState):
    """
    Final node to produce the output.
    """
    log_state(state, "At output_node")
    return state
